from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.graph.dev_workflow import DevWorkflow
from agentsystem.core.state import build_mode_coverage
from agentsystem.core.task_card import normalize_runtime_task_payload
from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy
from agentsystem.orchestration.continuity import (
    ContinuityGuardError,
    assert_continuity_ready,
    inject_continuity_into_task,
    load_continuity_bundle,
    sync_continuity,
)
from agentsystem.orchestration.runtime_memory import (
    collect_mode_artifact_paths,
    ensure_runtime_layout,
    locate_story_context,
    read_resume_state,
    update_agent_coverage_report,
    update_story_acceptance_review,
    update_story_status,
    write_current_handoff,
    write_resume_state,
    write_story_failure,
    write_story_handoff,
)
from agentsystem.orchestration.workflow_admission import build_story_admission, write_story_admission
from agentsystem.orchestration.workspace_manager import SnapshotSyncConflictError, WorkspaceLockError, WorkspaceManager
from agentsystem.utils.logger import get_logger


def _coverage_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = state if isinstance(state, dict) else {}
    return snapshot.get("agent_mode_coverage") or build_mode_coverage(
        snapshot.get("required_modes"),
        snapshot.get("advisory_modes"),
        snapshot.get("executed_modes"),
    )


def _review_findings_summary(state: dict[str, Any] | None) -> dict[str, list[str]]:
    snapshot = state if isinstance(state, dict) else {}
    return {
        "blocking": list(snapshot.get("blocking_issues") or []),
        "important": list(snapshot.get("important_issues") or []),
        "nice_to_haves": list(snapshot.get("nice_to_haves") or []),
    }


def _load_workspace_execution_context(workspace_manager: WorkspaceManager, task_id: str, worktree_path: Path) -> dict[str, Any]:
    context: dict[str, Any] = {
        "workspace_mode": "worktree",
        "snapshot_reason": None,
        "snapshot_state_path": None,
        "worktree_path": str(worktree_path),
    }
    meta_dir = getattr(workspace_manager, "meta_dir", None)
    if meta_dir is None:
        return context
    snapshot_path = Path(meta_dir) / task_id / "snapshot_state.json"
    if not snapshot_path.exists():
        return context
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return context
    context.update(
        {
            "workspace_mode": str(payload.get("mode") or "snapshot"),
            "snapshot_reason": payload.get("snapshot_reason"),
            "snapshot_state_path": str(snapshot_path),
        }
    )
    return context


def _normalize_failure_state(
    *,
    state: dict[str, Any] | None,
    task: dict[str, Any],
    branch_name: str,
    worktree_path: Path,
    error_message: str | None,
    default_failure_type: str,
    resume_state: dict[str, Any] | None,
) -> dict[str, Any]:
    snapshot = dict(state or {})
    persisted = resume_state or {}

    task_payload = snapshot.get("task_payload")
    if not isinstance(task_payload, dict):
        snapshot["task_payload"] = dict(task)
    snapshot.setdefault("branch_name", branch_name)
    snapshot.setdefault("repo_b_path", str(worktree_path))

    for key in (
        "workflow_plugin_id",
        "workflow_manifest_path",
        "workflow_agent_manifest_ids",
        "workflow_agent_manifest_paths",
        "story_kind",
        "risk_level",
        "workflow_enforcement_policy",
        "upstream_agent_parity",
        "qa_strategy",
        "effective_qa_mode",
        "required_modes",
        "advisory_modes",
        "next_recommended_actions",
        "agent_activation_plan",
    ):
        if snapshot.get(key) not in (None, "", []):
            continue
        candidate = task.get(key)
        if candidate not in (None, "", []):
            snapshot[key] = candidate

    if snapshot.get("current_step") in (None, ""):
        snapshot["current_step"] = persisted.get("current_step")
    if snapshot.get("last_node") in (None, ""):
        snapshot["last_node"] = persisted.get("current_node")
    if snapshot.get("fix_attempts") in (None, ""):
        snapshot["fix_attempts"] = persisted.get("fix_attempts") or 0
    if snapshot.get("failure_type") in (None, ""):
        snapshot["failure_type"] = persisted.get("failure_type") or default_failure_type
    if snapshot.get("interruption_reason") in (None, ""):
        snapshot["interruption_reason"] = (
            persisted.get("interruption_reason")
            or snapshot.get("failure_type")
            or default_failure_type
        )
    if error_message and not snapshot.get("error_message"):
        snapshot["error_message"] = error_message

    snapshot["mode_artifact_paths"] = snapshot.get("mode_artifact_paths") or collect_mode_artifact_paths(snapshot)
    snapshot["agent_mode_coverage"] = _coverage_from_state(snapshot)
    snapshot["blocker_class"] = snapshot.get("blocker_class") or _derive_blocker_class(snapshot, task)
    return snapshot


def _non_empty_paths(*paths: object) -> list[str]:
    values: list[str] = []
    for item in paths:
        marker = str(item or "").strip()
        if marker:
            values.append(marker)
    return values


def _handle_story_failure(
    *,
    repo_b_path: Path,
    project_id: str,
    task: dict[str, Any],
    task_id: str,
    branch_name: str,
    worktree_path: Path,
    workspace_manager: WorkspaceManager,
    env: str,
    state: dict[str, Any] | None,
    error_message: str | None,
    default_failure_type: str,
    workspace_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_resume = read_resume_state(repo_b_path)
    failure_state = _normalize_failure_state(
        state=state,
        task=task,
        branch_name=branch_name,
        worktree_path=worktree_path,
        error_message=error_message,
        default_failure_type=default_failure_type,
        resume_state=existing_resume,
    )
    coverage = _coverage_from_state(failure_state)
    story_id = str(task.get("story_id") or task.get("task_id") or task_id)
    summary_error = (
        error_message
        or str(failure_state.get("error_message") or "").strip()
        or str(failure_state.get("failure_type") or default_failure_type)
    )
    workspace_context = workspace_context or {}

    workspace_manager.update_task_state(
        task_id,
        {
            "status": "failed",
            "error": summary_error,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )

    audit_log = _build_audit_log(
        task_id=task_id,
        project_id=project_id,
        task=task,
        branch_name=branch_name,
        commit_hash=None,
        success=False,
        status_label="failed",
        result_state=failure_state,
        error=summary_error,
    )
    audit_path = _write_audit_log(task_id, audit_log)
    artifact_dir = _archive_task_artifacts(task_id, failure_state)
    if artifact_dir:
        audit_log["artifact_dir"] = str(artifact_dir)
        audit_path.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")

    failure_snapshot_path = write_story_failure(
        repo_b_path,
        story_id,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "task_id": task_id,
            "task_name": task.get("task_name") or task.get("goal"),
            "failure_type": failure_state.get("failure_type") or default_failure_type,
            "last_node": failure_state.get("last_node"),
            "fix_attempts": failure_state.get("fix_attempts"),
            "review_findings_summary": _review_findings_summary(failure_state),
            "changed_files": _collect_changed_files_from_state(failure_state),
            "recommended_recovery_action": "Resume from the failed story after fixing the workflow blocker.",
            "blocker_class": failure_state.get("blocker_class"),
            "error_message": summary_error,
            "audit_path": str(audit_path),
            "artifact_dir": str(artifact_dir) if artifact_dir else None,
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
        },
    )
    handoff_paths = write_current_handoff(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "sprint_label": task.get("sprint"),
            "story_id": story_id,
            "task_name": task.get("task_name") or task.get("goal"),
            "current_node": failure_state.get("last_node"),
            "status": "interrupted",
            "last_success_story": existing_resume.get("last_success_story"),
            "resume_from_story": story_id,
            "interruption_reason": failure_state.get("interruption_reason") or failure_state.get("failure_type") or default_failure_type,
            "root_cause": summary_error,
            "next_action": "Resume automatic delivery from the failed story after the blocker is fixed.",
            "resume_command": f"python cli.py auto-deliver --project {project_id} --env {env} --prefix {task.get('backlog_id') or 'backlog_v1'} --auto-run",
            "evidence_paths": _non_empty_paths(audit_path, failure_snapshot_path, artifact_dir),
            "cleanup_note": "Inspect the failed worktree and rerun from the checkpoint.",
            "blocker_class": failure_state.get("blocker_class"),
            "execution_policy": failure_state.get("execution_policy") or task.get("execution_policy"),
            "interaction_policy": failure_state.get("interaction_policy") or task.get("interaction_policy"),
            "pause_policy": failure_state.get("pause_policy") or task.get("pause_policy"),
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
    )
    story_handoff_path = write_story_handoff(
        repo_b_path,
        story_id,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": story_id,
            "task_name": task.get("task_name") or task.get("goal"),
            "current_node": failure_state.get("last_node"),
            "status": "failed",
            "last_success_story": existing_resume.get("last_success_story"),
            "resume_from_story": story_id,
            "interruption_reason": failure_state.get("interruption_reason") or failure_state.get("failure_type") or default_failure_type,
            "root_cause": summary_error,
            "next_action": "Repair the workflow blocker, then resume from this story.",
            "resume_command": f"python cli.py auto-deliver --project {project_id} --env {env} --prefix {task.get('backlog_id') or 'backlog_v1'} --auto-run",
            "evidence_paths": _non_empty_paths(audit_path, failure_snapshot_path, handoff_paths["project_handoff"]),
            "blocker_class": failure_state.get("blocker_class"),
            "execution_policy": failure_state.get("execution_policy") or task.get("execution_policy"),
            "interaction_policy": failure_state.get("interaction_policy") or task.get("interaction_policy"),
            "pause_policy": failure_state.get("pause_policy") or task.get("pause_policy"),
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
    )

    update_story_status(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": story_id,
            "task_id": task_id,
            "status": "failed",
            "branch": branch_name,
            "commit": None,
            "started_at": failure_state.get("collaboration_started_at"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "verified_at": datetime.now().isoformat(timespec="seconds"),
            "last_node": failure_state.get("last_node"),
            "audit_path": str(audit_path),
            "resume_token": story_id,
            "source": "agentsystem_runtime",
            "summary": summary_error,
            "blocker_class": failure_state.get("blocker_class"),
            "validation_summary": str(failure_state.get("test_results") or ""),
            "evidence": _non_empty_paths(audit_path, failure_snapshot_path, story_handoff_path),
            "formal_entry": bool(task.get("formal_entry", True)),
            "required_modes": list(failure_state.get("required_modes") or []),
            "executed_modes": list(failure_state.get("executed_modes") or []),
            "advisory_modes": list(failure_state.get("advisory_modes") or []),
            "agent_mode_coverage": coverage,
            "formal_acceptance_reviewer": None,
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
            "implemented": False,
            "verified": False,
            "agentized": False,
            "accepted": False,
            "repository": project_id,
        },
    )
    update_story_acceptance_review(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": story_id,
            "reviewer": "agentsystem",
            "review_type": "machine",
            "verdict": "rejected",
            "acceptance_status": "rejected",
            "summary": summary_error,
            "review_findings_summary": _review_findings_summary(failure_state),
            "notes": str(failure_snapshot_path),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "agent_mode_coverage": coverage,
            "evidence_paths": _non_empty_paths(audit_path, failure_snapshot_path, story_handoff_path),
            "formal_entry": bool(task.get("formal_entry", True)),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
            "implemented": False,
            "verified": False,
            "agentized": False,
            "accepted": False,
        },
    )
    update_agent_coverage_report(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": story_id,
            "required_modes": list(failure_state.get("required_modes") or []),
            "executed_modes": list(failure_state.get("executed_modes") or []),
            "advisory_modes": list(failure_state.get("advisory_modes") or []),
            "mode_execution_order": list(failure_state.get("mode_execution_order") or []),
            "mode_artifact_paths": failure_state.get("mode_artifact_paths") or {},
            "agent_mode_coverage": coverage,
            "status": "failed",
            "audit_path": str(audit_path),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
        },
    )
    write_resume_state(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "backlog_root": task.get("backlog_root"),
            "sprint_id": task.get("sprint_id"),
            "sprint_label": task.get("sprint"),
            "story_id": story_id,
            "task_name": task.get("task_name") or task.get("goal"),
            "task_id": task_id,
            "current_node": failure_state.get("last_node"),
            "current_step": failure_state.get("current_step"),
            "branch_name": branch_name,
            "status": "interrupted",
            "blocker_class": failure_state.get("blocker_class"),
            "execution_policy": failure_state.get("execution_policy") or task.get("execution_policy"),
            "interaction_policy": failure_state.get("interaction_policy") or task.get("interaction_policy"),
            "pause_policy": failure_state.get("pause_policy") or task.get("pause_policy"),
            "failure_type": failure_state.get("failure_type") or default_failure_type,
            "interruption_reason": failure_state.get("interruption_reason") or failure_state.get("failure_type") or default_failure_type,
            "error_message": summary_error,
            "resume_from_story": story_id,
            "failure_snapshot_path": str(failure_snapshot_path),
            "last_success_story": existing_resume.get("last_success_story"),
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
        clear_keys=["commit"],
    )
    return {
        "task_id": task_id,
        "project": project_id,
        "branch": branch_name,
        "worktree_path": str(worktree_path),
        "success": False,
        "error": summary_error,
        "audit_path": str(audit_path),
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "state": failure_state,
    }


def run_prod_task(
    task_file: str | Path,
    env: str = "test",
    project: str | None = None,
    task_overrides: dict[str, Any] | None = None,
) -> dict:
    logger = get_logger("main_production", ROOT_DIR / "logs" / "agent_system.log")
    logger.info("Starting production task", extra={"task_id": "bootstrap", "agent_type": "system"})

    config_name = "test.yaml" if env == "test" else "production.yaml"
    config = SystemConfigReader().load(ROOT_DIR / "config" / config_name)
    task_path = Path(task_file).resolve()
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    if not isinstance(task, dict):
        raise ValueError(f"{task_path} must contain a mapping")
    task = normalize_runtime_task_payload(task)
    if task_overrides:
        task.update({str(key): value for key, value in task_overrides.items() if value is not None})
    project_id = _resolve_project_id(task, config, project)
    repo_b_path = _resolve_repo_path(config, project_id)
    story_context = locate_story_context(task_path, repo_b_path)
    ensure_runtime_layout(repo_b_path)

    git = GitAdapter(repo_b_path)
    git.checkout_main_and_pull("main")

    workspace_manager = WorkspaceManager(repo_b_path, ROOT_DIR / "repo-worktree")
    task["project"] = project_id
    task["project_repo_root"] = str(repo_b_path)
    task.update(story_context)
    task["backlog_root"] = str(repo_b_path / "tasks" / str(story_context.get("backlog_id") or ""))
    if task.get("auto_run") is None:
        task["auto_run"] = True
    if task.get("formal_entry") is None:
        task["formal_entry"] = bool(task.get("auto_run"))
    if not str(task.get("run_policy") or "").strip():
        task["run_policy"] = "single_pass_to_completion"
    if not str(task.get("execution_policy") or "").strip():
        task["execution_policy"] = "continuous_full_sprint"
    if not str(task.get("interaction_policy") or "").strip():
        task["interaction_policy"] = "non_interactive_auto_run" if bool(task.get("auto_run")) else "direct_run_task"
    if not str(task.get("pause_policy") or "").strip():
        task["pause_policy"] = "story_boundary_or_shared_blocker_only"
    if not str(task.get("acceptance_policy") or "").strip():
        task["acceptance_policy"] = "must_pass_all_required_runs"
    if not str(task.get("retry_policy") or "").strip():
        task["retry_policy"] = "auto_repair_until_green"
    task["acceptance_attempt"] = int(task.get("acceptance_attempt") or 0)
    task["repair_iteration"] = int(task.get("repair_iteration") or 0)
    if task.get("final_green_required") is None:
        task["final_green_required"] = True
    if not str(task.get("authoritative_attempt") or "").strip():
        task["authoritative_attempt"] = ""
    task = apply_agent_activation_policy(task, repo_b_path)
    admission = build_story_admission(task, repo_b_path, story_file=task_path)
    admission_path = write_story_admission(
        repo_b_path,
        str(task.get("story_id") or task.get("task_id") or task_path.stem),
        admission,
    )
    task = dict(admission["task_payload"])
    if not admission.get("admitted"):
        raise ValueError(
            "Workflow admission failed: " + "; ".join(str(item) for item in (admission.get("errors") or []) if str(item).strip())
        )

    task_id = workspace_manager.generate_task_id(task_path.read_text(encoding="utf-8"))
    branch_name = f"agent/l1-{task_id}"
    try:
        worktree_path = workspace_manager.create_worktree(task_id, branch_name)
    except WorkspaceLockError:
        worktree_path = workspace_manager.worktree_root / task_id
    workspace_context = _load_workspace_execution_context(workspace_manager, task_id, worktree_path)
    if not str(task.get("authoritative_attempt") or "").strip():
        task["authoritative_attempt"] = str(task.get("story_id") or task.get("task_id") or task_id)
    workspace_manager.update_task_state(
        task_id,
        {
            "status": "running",
            "project": project_id,
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_name": task.get("task_name") or task.get("goal"),
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    write_resume_state(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "backlog_root": task.get("backlog_root"),
            "sprint_id": task.get("sprint_id"),
            "sprint_label": task.get("sprint"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_name": task.get("task_name") or task.get("goal"),
            "task_id": task_id,
            "branch_name": branch_name,
            "status": "running",
            "resume_from_story": task.get("story_id") or task.get("task_id"),
            "run_policy": task.get("run_policy"),
            "execution_policy": task.get("execution_policy"),
            "interaction_policy": task.get("interaction_policy"),
            "pause_policy": task.get("pause_policy"),
            "acceptance_policy": task.get("acceptance_policy"),
            "retry_policy": task.get("retry_policy"),
            "acceptance_attempt": task.get("acceptance_attempt"),
            "repair_iteration": task.get("repair_iteration"),
            "final_green_required": task.get("final_green_required"),
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
        clear_keys=["failure_type", "interruption_reason", "error_message", "failure_snapshot_path", "commit"],
    )
    continuity_story_path = str(task_path)
    continuity_trigger = str(task.get("continuity_trigger") or "").strip()
    if not continuity_trigger:
        resume_state = read_resume_state(repo_b_path)
        continuity_trigger = "resume_interrupt" if str(resume_state.get("status") or "") == "interrupted" else "fresh_start"
    continuity_sprint_artifact_refs = [str(item) for item in (task.get("continuity_sprint_artifact_refs") or []) if str(item).strip()]
    continuity_artifact_refs = [str(item) for item in (task.get("continuity_artifact_refs") or []) if str(item).strip()]
    continuity_decision_refs = [str(item) for item in (task.get("continuity_decision_refs") or []) if str(item).strip()]

    try:
        sync_continuity(
            continuity_trigger,
            project_id,
            repo_b_path,
            task_payload=task,
            current_story_path=continuity_story_path,
            sprint_artifact_refs=continuity_sprint_artifact_refs,
            artifact_refs=continuity_artifact_refs,
            decision_refs=continuity_decision_refs,
        )
        continuity_bundle = load_continuity_bundle(
            continuity_trigger,
            project_id,
            repo_b_path,
            current_story_path=continuity_story_path,
            strict=False,
        )
        assert_continuity_ready(continuity_bundle, strict=True)
        task = inject_continuity_into_task(task, continuity_bundle)
    except ContinuityGuardError as exc:
        logger.error(
            "Continuity guard blocked task execution",
            extra={"task_id": task_id, "agent_type": "system"},
        )
        return _handle_story_failure(
            repo_b_path=repo_b_path,
            project_id=project_id,
            task=task,
            task_id=task_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            workspace_manager=workspace_manager,
            env=env,
            state=None,
            error_message=str(exc),
            default_failure_type="continuity_guard_blocked",
            workspace_context=workspace_context,
        )
    logger.info(
        "Workspace created",
        extra={"task_id": task_id, "agent_type": "system"},
    )
    _prepare_local_dependencies(repo_b_path, worktree_path, task)

    workflow = DevWorkflow(config, str(worktree_path), task, task_id=task_id)
    try:
        result = workflow.run()
    except Exception as exc:
        logger.error(
            "Workflow execution raised an exception",
            extra={"task_id": task_id, "agent_type": "system"},
        )
        return _handle_story_failure(
            repo_b_path=repo_b_path,
            project_id=project_id,
            task=task,
            task_id=task_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            workspace_manager=workspace_manager,
            env=env,
            state=None,
            error_message=str(exc),
            default_failure_type="run_prod_task_exception",
            workspace_context=workspace_context,
        )
    if not result["success"]:
        logger.error(
            "Workflow execution failed",
            extra={"task_id": task_id, "agent_type": "system"},
        )
        return _handle_story_failure(
            repo_b_path=repo_b_path,
            project_id=project_id,
            task=task,
            task_id=task_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            workspace_manager=workspace_manager,
            env=env,
            state=result.get("state"),
            error_message=result.get("error"),
            default_failure_type=str((result.get("state") or {}).get("failure_type") or "workflow_failed"),
            workspace_context=workspace_context,
        )

    try:
        git_worktree = GitAdapter(worktree_path)
        repo_b_config = RepoBConfigReader(worktree_path).load_all_config()
        format_commands = repo_b_config.commands.get("format", [])
        if format_commands and git_worktree.is_dirty():
            shell = ShellExecutor(worktree_path)
            format_success, format_output = shell.run_commands(format_commands)
            if not format_success:
                raise RuntimeError(f"Format failed: {format_output}")

        sync_report: dict[str, Any] | None = None
        if git_worktree.is_dirty():
            changed_files = git_worktree.get_working_tree_files()
            if getattr(git_worktree, "snapshot_mode", False):
                sync_report = workspace_manager.materialize_snapshot_changes(
                    task_id,
                    target_repo_path=repo_b_path,
                    changed_files=changed_files,
                )
            else:
                sync_report = workspace_manager.materialize_worktree_changes(
                    task_id,
                    target_repo_path=repo_b_path,
                    changed_files=changed_files,
                )
            result["state"]["snapshot_sync_report"] = sync_report
            result["state"]["snapshot_sync_report_path"] = sync_report.get("report_path")
            result["state"]["materialized_changed_files"] = list(sync_report.get("applied_files") or [])
            result["state"]["materialized_deleted_files"] = list(sync_report.get("deleted_files") or [])

        commit_hash = git_worktree.get_current_commit()
        if git_worktree.is_dirty():
            git_worktree.add_all()
            commit_message = str(result["state"].get("commit_msg") or f"feat(auto-dev): {str(task.get('goal', 'task'))[:50]}")
            git_worktree.commit(commit_message)
            commit_hash = git_worktree.get_current_commit()
        if sync_report:
            workspace_context["materialized_to_repo"] = True
            workspace_context["materialized_report_path"] = sync_report.get("report_path")
    except Exception as exc:
        if isinstance(exc, SnapshotSyncConflictError):
            result["state"]["snapshot_sync_conflicts"] = list(exc.conflicts)
        logger.error(
            "Post-workflow task finalization failed",
            extra={"task_id": task_id, "agent_type": "system"},
        )
        return _handle_story_failure(
            repo_b_path=repo_b_path,
            project_id=project_id,
            task=task,
            task_id=task_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            workspace_manager=workspace_manager,
            env=env,
            state=result.get("state"),
            error_message=str(exc),
            default_failure_type="run_prod_task_exception",
            workspace_context=workspace_context,
        )

    workspace_manager.update_task_state(
        task_id,
        {
            "status": "completed",
            "commit": commit_hash,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    audit_log = _build_audit_log(
        task_id=task_id,
        project_id=project_id,
        task=task,
        branch_name=branch_name,
        commit_hash=commit_hash,
        success=True,
        status_label="success",
        result_state=result["state"],
    )
    audit_path = _write_audit_log(task_id, audit_log)

    artifact_dir = _archive_task_artifacts(task_id, result["state"])
    audit_log["artifact_dir"] = str(artifact_dir) if artifact_dir else None
    audit_path.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")
    coverage = result["state"].get("agent_mode_coverage") or build_mode_coverage(
        result["state"].get("required_modes"),
        result["state"].get("advisory_modes"),
        result["state"].get("executed_modes"),
    )
    story_handoff_path = write_story_handoff(
        repo_b_path,
        str(task.get("story_id") or task.get("task_id") or task_id),
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_name": task.get("task_name") or task.get("goal"),
            "current_node": result["state"].get("last_node") or "doc_writer",
            "status": "done",
            "last_success_story": task.get("story_id") or task.get("task_id"),
            "resume_from_story": task.get("story_id") or task.get("task_id"),
            "root_cause": "Story completed successfully.",
            "next_action": "Continue to the next story in the execution order.",
            "resume_command": f"python cli.py auto-deliver --project {project_id} --env {env} --prefix {task.get('backlog_id') or 'backlog_v1'} --auto-run",
            "evidence_paths": [str(audit_path), str(artifact_dir), str(result["state"].get("delivery_dir") or "")],
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
    )
    handoff_paths = write_current_handoff(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "sprint_label": task.get("sprint"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_name": task.get("task_name") or task.get("goal"),
            "current_node": result["state"].get("last_node") or "doc_writer",
            "status": "running",
            "last_success_story": task.get("story_id") or task.get("task_id"),
            "resume_from_story": task.get("story_id") or task.get("task_id"),
            "root_cause": "Latest story completed successfully.",
            "next_action": "Continue to the next queued story automatically.",
            "resume_command": f"python cli.py auto-deliver --project {project_id} --env {env} --prefix {task.get('backlog_id') or 'backlog_v1'} --auto-run",
            "evidence_paths": [str(audit_path), str(story_handoff_path)],
            "cleanup_note": "No cleanup required before the next story.",
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
    )
    accepted = bool(result["state"].get("acceptance_passed"))
    update_story_status(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_id": task_id,
            "status": "done",
            "branch": branch_name,
            "commit": commit_hash,
            "started_at": result["state"].get("collaboration_started_at"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "verified_at": datetime.now().isoformat(timespec="seconds"),
            "last_node": result["state"].get("last_node") or "doc_writer",
            "audit_path": str(audit_path),
            "resume_token": str(task.get("story_id") or task.get("task_id")),
            "source": "agentsystem_runtime",
            "summary": "Story completed successfully.",
            "validation_summary": str(result["state"].get("test_results") or ""),
            "delivery_report": str(result["state"].get("delivery_dir") or ""),
            "evidence": [str(audit_path), str(story_handoff_path), str(handoff_paths["project_handoff"]), str(admission_path)],
            "formal_entry": bool(task.get("formal_entry", True)),
            "required_modes": list(result["state"].get("required_modes") or []),
            "executed_modes": list(result["state"].get("executed_modes") or []),
            "advisory_modes": list(result["state"].get("advisory_modes") or []),
            "agent_mode_coverage": coverage,
            "formal_acceptance_reviewer": "acceptance_gate" if accepted else None,
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
            "implemented": True,
            "verified": bool(result["state"].get("test_passed")) or bool(result["state"].get("test_results")),
            "agentized": bool(coverage.get("all_required_executed")),
            "accepted": accepted,
            "repository": project_id,
        },
    )
    update_story_acceptance_review(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "reviewer": "acceptance_gate",
            "review_type": "machine",
            "verdict": "approved" if coverage.get("all_required_executed") else "needs_followup",
            "acceptance_status": "approved" if coverage.get("all_required_executed") else "needs_followup",
            "summary": "Automatic acceptance passed." if coverage.get("all_required_executed") else "Automatic acceptance passed with mode coverage follow-up.",
            "notes": str(story_handoff_path),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "agent_mode_coverage": coverage,
            "review_findings_summary": {"blocking": [], "important": [], "nice_to_haves": []},
            "evidence_paths": [str(audit_path), str(story_handoff_path), str(admission_path)],
            "formal_entry": bool(task.get("formal_entry", True)),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
            "implemented": True,
            "verified": bool(result["state"].get("test_passed")) or bool(result["state"].get("test_results")),
            "agentized": bool(coverage.get("all_required_executed")),
            "accepted": accepted,
        },
    )
    update_agent_coverage_report(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "sprint_id": task.get("sprint_id"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "required_modes": list(result["state"].get("required_modes") or []),
            "executed_modes": list(result["state"].get("executed_modes") or []),
            "advisory_modes": list(result["state"].get("advisory_modes") or []),
            "mode_execution_order": list(result["state"].get("mode_execution_order") or []),
            "mode_artifact_paths": collect_mode_artifact_paths(result["state"]),
            "agent_mode_coverage": coverage,
            "status": "done",
            "audit_path": str(audit_path),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "attempt_status": "authoritative" if task.get("formal_entry", True) else "evidence_only",
        },
    )
    write_resume_state(
        repo_b_path,
        {
            "project": project_id,
            "backlog_id": task.get("backlog_id"),
            "backlog_root": task.get("backlog_root"),
            "sprint_id": task.get("sprint_id"),
            "sprint_label": task.get("sprint"),
            "story_id": task.get("story_id") or task.get("task_id"),
            "task_name": task.get("task_name") or task.get("goal"),
            "task_id": task_id,
            "current_node": "doc_writer",
            "current_step": result["state"].get("current_step"),
            "branch_name": branch_name,
            "commit": commit_hash,
            "status": "running",
            "last_success_story": task.get("story_id") or task.get("task_id"),
            "resume_from_story": task.get("story_id") or task.get("task_id"),
            "evidence_paths": [str(audit_path), str(story_handoff_path)],
            "workspace_mode": workspace_context.get("workspace_mode"),
            "snapshot_reason": workspace_context.get("snapshot_reason"),
            "authoritative_attempt": task.get("authoritative_attempt"),
            "sprint_rerun_policy": task.get("sprint_rerun_policy"),
        },
        clear_keys=["failure_type", "interruption_reason", "error_message", "failure_snapshot_path"],
    )

    cleanup_mode = str(config.get("agent", {}).get("cleanup_on_success", "true")).lower()
    if cleanup_mode in {"1", "true", "yes", "on"}:
        try:
            workspace_manager.cleanup_task_resources(task_id)
        except Exception as exc:
            logger.warning(
                "Workspace cleanup failed after successful task",
                extra={"task_id": task_id, "agent_type": "system"},
            )
            audit_log["cleanup_warning"] = str(exc)
            audit_path.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Production task finished",
        extra={"task_id": task_id, "agent_type": "system"},
    )
    return {
        "task_id": task_id,
        "project": project_id,
        "branch": branch_name,
        "worktree_path": str(worktree_path),
        "commit": commit_hash,
        "audit_path": str(audit_path),
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "pr_prep_dir": result["state"].get("pr_prep_dir"),
        "success": True,
        "state": result["state"],
    }


def _prepare_local_dependencies(repo_b_path: Path, worktree_path: Path, task: dict[str, object] | None = None) -> None:
    if not _should_prepare_local_dependencies(task):
        return
    source_web = repo_b_path / "apps" / "web"
    target_web = worktree_path / "apps" / "web"
    if not source_web.exists() or not target_web.exists():
        return
    install_command = _resolve_frontend_install_command(source_web)
    if not install_command:
        return
    if not (source_web / "node_modules").exists():
        return
    if (target_web / "node_modules").exists():
        return
    shell = ShellExecutor(worktree_path)
    success, output = shell.run_command(install_command)
    if not success:
        raise RuntimeError(f"Failed to prepare local frontend dependencies: {output}")


def _should_prepare_local_dependencies(task: dict[str, object] | None) -> bool:
    if not isinstance(task, dict):
        return True
    story_kind = str(task.get("story_kind") or "").strip().lower()
    qa_strategy = str(task.get("qa_strategy") or "").strip().lower()
    has_browser_surface = bool(task.get("has_browser_surface"))
    explicit_browser_mode = str(task.get("skill_mode") or "").strip().lower() in {"browse", "qa", "qa-only"}
    return has_browser_surface or story_kind in {"ui", "mixed"} or qa_strategy == "browser" or explicit_browser_mode


def _resolve_frontend_install_command(source_web: Path) -> str | None:
    lockfile_commands = (
        ("pnpm-lock.yaml", "pnpm --dir apps/web install --frozen-lockfile"),
        ("package-lock.json", "npm --prefix apps/web ci"),
        ("npm-shrinkwrap.json", "npm --prefix apps/web ci"),
        ("yarn.lock", "yarn --cwd apps/web install --frozen-lockfile"),
    )
    for filename, command in lockfile_commands:
        if (source_web / filename).exists():
            return command
    return None


def _archive_task_artifacts(task_id: str, state: dict) -> Path | None:
    artifact_root = ROOT_DIR / "runs" / "artifacts" / task_id
    artifact_root.mkdir(parents=True, exist_ok=True)
    copied = False

    for source_key, target_name in (
        ("office_hours_dir", "office_hours"),
        ("plan_ceo_review_dir", "plan_ceo_review"),
        ("architecture_review_dir", "architecture_review"),
        ("investigate_dir", "investigate"),
        ("browse_dir", "browse"),
        ("plan_design_review_dir", "plan_design_review"),
        ("setup_browser_cookies_dir", "setup_browser_cookies"),
        ("browser_qa_dir", "browser_qa"),
        ("browser_runtime_dir", "browser_runtime"),
        ("runtime_qa_dir", "runtime_qa"),
        ("qa_design_review_dir", "qa_design_review"),
        ("pr_prep_dir", "pr_prep"),
        ("review_dir", "review"),
        ("code_acceptance_dir", "code_acceptance"),
        ("acceptance_dir", "acceptance"),
        ("delivery_dir", "delivery"),
        ("ship_dir", "ship"),
        ("document_release_dir", "document_release"),
        ("retro_dir", "retro"),
    ):
        source = state.get(source_key)
        if not source:
            continue
        source_path = Path(str(source))
        if not source_path.exists():
            continue
        shutil.copytree(source_path, artifact_root / target_name, dirs_exist_ok=True)
        copied = True

    return artifact_root if copied else None


def _build_audit_log(
    *,
    task_id: str,
    project_id: str,
    task: dict[str, object],
    branch_name: str,
    commit_hash: str | None,
    success: bool,
    status_label: str,
    result_state: dict[str, object],
    error: str | None = None,
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project": project_id,
        "task_name": task.get("task_name") or task.get("goal"),
        "branch": branch_name,
        "commit": commit_hash,
        "success": success,
        "status": status_label,
        "error": error,
        "blast_radius": task.get("blast_radius"),
        "execution_mode": task.get("mode") or task.get("execution_mode"),
        "story_kind": result_state.get("story_kind"),
        "risk_level": result_state.get("risk_level"),
        "workflow_enforcement_policy": result_state.get("workflow_enforcement_policy"),
        "upstream_agent_parity": result_state.get("upstream_agent_parity"),
        "qa_strategy": result_state.get("qa_strategy"),
        "required_modes": list(result_state.get("required_modes") or []),
        "executed_modes": list(result_state.get("executed_modes") or []),
        "advisory_modes": list(result_state.get("advisory_modes") or []),
        "next_recommended_actions": list(result_state.get("next_recommended_actions") or []),
        "effective_qa_mode": result_state.get("effective_qa_mode"),
        "agent_activation_plan": result_state.get("agent_activation_plan"),
        "agent_mode_coverage": result_state.get("agent_mode_coverage"),
        "pr_prep_dir": result_state.get("pr_prep_dir"),
        "review_dir": result_state.get("review_dir"),
        "pr_desc": result_state.get("pr_desc"),
        "commit_msg": result_state.get("commit_msg"),
        "result": result_state,
    }


def _write_audit_log(task_id: str, audit_log: dict[str, object]) -> Path:
    audit_path = ROOT_DIR / "runs" / f"prod_audit_{task_id}.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


def _resolve_project_id(task: dict[str, object], config: dict[str, object], project_override: str | None) -> str:
    candidate = str(project_override or task.get("project") or "versefina").strip() or "versefina"
    repo_map = config.get("repo", {}) if isinstance(config, dict) else {}
    if not isinstance(repo_map, dict) or candidate not in repo_map:
        raise KeyError(f"Unknown project {candidate!r}; available repos: {sorted(repo_map.keys())}")
    return candidate


def _resolve_repo_path(config: dict[str, object], project_id: str) -> Path:
    repo_map = config.get("repo", {}) if isinstance(config, dict) else {}
    if not isinstance(repo_map, dict):
        raise KeyError("System config must define repo mappings")
    return Path(str(repo_map[project_id])).resolve()


def _collect_changed_files_from_state(state: dict[str, object]) -> list[str]:
    changed: list[str] = []
    dev_results = state.get("dev_results") if isinstance(state, dict) else {}
    if isinstance(dev_results, dict):
        for payload in dev_results.values():
            if not isinstance(payload, dict):
                continue
            for item in payload.get("updated_files", []) or []:
                changed.append(_normalize_changed_file_path(str(item)))
    for item in state.get("staged_files", []) or []:
        changed.append(_normalize_changed_file_path(str(item)))
    seen: set[str] = set()
    unique: list[str] = []
    for item in changed:
        if _is_ignored_changed_file_path(item):
            continue
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _derive_blocker_class(state: dict[str, object], task: dict[str, Any]) -> str:
    explicit = str(state.get("blocker_class") or task.get("blocker_class") or "").strip()
    if explicit in {"story_local_blocker", "shared_dependency_blocker"}:
        return explicit

    failure_type = str(state.get("failure_type") or "").strip()
    if failure_type in {"workflow_bug", "run_prod_task_exception", "story_card_missing"}:
        return "shared_dependency_blocker"

    candidate_paths = [
        *_collect_changed_files_from_state(state),
        *(str(item).strip() for item in (task.get("primary_files") or []) if str(item).strip()),
        *(str(item).strip() for item in (task.get("secondary_files") or []) if str(item).strip()),
        *(str(item).strip() for item in (task.get("related_files") or []) if str(item).strip()),
    ]
    shared_markers = (
        "config/workflows/",
        "config/skill_modes/",
        "config/platform/",
        "src/agentsystem/runtime/",
        "src/agentsystem/orchestration/",
        "src/agentsystem/graph/",
        "src/agentsystem/core/",
        "packages/schemas/",
        "workflows/",
        "graphs/",
        "vendors/gstack/",
        "scripts/init_schema.sql",
    )
    if any(marker in path.replace("\\", "/") for path in candidate_paths for marker in shared_markers):
        return "shared_dependency_blocker"
    return "story_local_blocker"


def _normalize_changed_file_path(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    if "/.agents/" in normalized:
        return ".agents/" + normalized.split("/.agents/", 1)[1]
    if "/apps/" in normalized:
        return "apps/" + normalized.split("/apps/", 1)[1]
    if "/docs/" in normalized:
        return "docs/" + normalized.split("/docs/", 1)[1]
    if "/scripts/" in normalized:
        return "scripts/" + normalized.split("/scripts/", 1)[1]
    if normalized.startswith((".agents/", "apps/", "docs/", "scripts/", "config/", "tasks/")):
        return normalized
    return normalized


def _is_ignored_changed_file_path(path: str) -> bool:
    normalized = str(path).replace("\\", "/")
    return (
        normalized.startswith("tasks/runtime/")
        or normalized.startswith("docs/handoff/")
        or "__pycache__/" in normalized
        or normalized.endswith(".pyc")
        or ".pytest_cache/" in normalized
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main_production.py <task_file> [env]")
        raise SystemExit(1)
    task_file = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) > 2 else "test"
    output = run_prod_task(task_file, env)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
