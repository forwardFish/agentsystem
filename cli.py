from __future__ import annotations

import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import click
import uvicorn
import yaml

# Fix stdout encoding for Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32" and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main_production import run_prod_task
from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import build_mode_coverage
from agentsystem.core.task_card import TaskCard, normalize_runtime_task_payload
from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy
from agentsystem.orchestration.continuity import (
    ContinuityGuardError,
    assert_continuity_ready,
    load_continuity_bundle,
    resolve_continuity_paths,
    sync_continuity,
)
from agentsystem.orchestration.gstack_parity_audit import write_gstack_parity_audit
from agentsystem.orchestration.sprint_hooks import run_sprint_post_hooks, run_sprint_pre_hooks
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
from agentsystem.dashboard.main import app as dashboard_app
from agentsystem.orchestration.workspace_manager import WorkspaceManager
from agentsystem.agents.plan_ceo_review_agent import generate_plan_ceo_review_package
from agentsystem.agents.requirements_analyst_agent import analyze_requirement, split_requirement_file
from scripts.fix_encoding import fix_tree_encoding
from scripts.render_agent_skills import render_agent_skill, render_all_agent_skills, validate_rendered_agent_package
from scripts.validate_skill import validate_all_skills, validate_skill_file


def _load_env_config(env: str) -> dict:
    config_name = "test.yaml" if env == "test" else "production.yaml"
    return SystemConfigReader().load(ROOT_DIR / "config" / config_name)


def _resolve_project_repo_path(config: dict, project: str) -> Path:
    repo_map = config.get("repo", {}) if isinstance(config, dict) else {}
    if not isinstance(repo_map, dict) or project not in repo_map:
        raise KeyError(f"Unknown project {project!r}; available repos: {sorted(repo_map.keys()) if isinstance(repo_map, dict) else []}")
    return Path(str(repo_map[project])).resolve()


def _resolve_tasks_root(repo_b_path: Path, project: str) -> Path:
    if project in {"versefina", "finahunt", "agentHire"}:
        return repo_b_path / "tasks"
    if (repo_b_path / "tasks").exists():
        return repo_b_path / "tasks"
    return ROOT_DIR / "tasks"


def _resolve_requirement_input(requirement: str | None, requirement_file: str | None) -> tuple[str | None, Path | None]:
    inline_text = str(requirement or "").strip() or None
    file_path = Path(requirement_file).resolve() if requirement_file else None
    if inline_text and file_path:
        raise click.ClickException("Use either --requirement or --requirement-file, not both.")
    if not inline_text and not file_path:
        raise click.ClickException("Either --requirement or --requirement-file is required.")
    if file_path and not file_path.exists():
        raise click.ClickException(f"Requirement file does not exist: {file_path}")
    return inline_text, file_path


def _find_default_requirement_file(repo_b_path: Path, project: str) -> Path | None:
    requirements_dir = repo_b_path / "docs" / "requirements"
    if not requirements_dir.exists():
        return None

    project_key = str(project).strip().lower()
    patterns_by_project = {
        "agenthire": [
            "*phase_1_execution_requirement*.md",
            "*mvp_v0_1_phase_1_execution_requirement*.md",
            "*phase_1_requirement*.md",
            "*.md",
        ],
    }
    patterns = patterns_by_project.get(project_key, ["*.md"])
    for pattern in patterns:
        matches = sorted(
            (path for path in requirements_dir.glob(pattern) if path.is_file()),
            key=lambda item: (item.stat().st_mtime, item.name),
            reverse=True,
        )
        if matches:
            return matches[0].resolve()
    return None


def _resolve_requirement_input_for_project(
    repo_b_path: Path,
    project: str,
    requirement: str | None,
    requirement_file: str | None,
) -> tuple[str | None, Path | None]:
    inline_text = str(requirement or "").strip() or None
    file_path = Path(requirement_file).resolve() if requirement_file else None
    if inline_text and file_path:
        raise click.ClickException("Use either --requirement or --requirement-file, not both.")
    if file_path and not file_path.exists():
        raise click.ClickException(f"Requirement file does not exist: {file_path}")
    if inline_text or file_path:
        return inline_text, file_path

    default_requirement = _find_default_requirement_file(repo_b_path, project)
    if default_requirement:
        return None, default_requirement

    raise click.ClickException("Either --requirement or --requirement-file is required.")


def _build_backlog_from_requirement(
    *,
    env: str,
    project: str,
    prefix: str,
    sprint: str,
    requirement: str | None,
    requirement_file: str | None,
) -> tuple[dict[str, object], Path, Path]:
    config = _load_env_config(env)
    repo_b_path = _resolve_project_repo_path(config, project)
    tasks_root = _resolve_tasks_root(repo_b_path, project)
    inline_text, file_path = _resolve_requirement_input_for_project(repo_b_path, project, requirement, requirement_file)
    if inline_text:
        result = analyze_requirement(repo_b_path, tasks_root, inline_text, sprint=sprint, prefix=prefix)
    else:
        result = split_requirement_file(repo_b_path, tasks_root, str(file_path), prefix=prefix)
    return result, repo_b_path, tasks_root


def _sort_sprint_paths(paths: list[Path]) -> list[Path]:
    def sort_key(path: Path) -> tuple[int, str]:
        return (_extract_sprint_number(path.name), path.name)

    return sorted(paths, key=sort_key)


def _extract_sprint_number(name: str) -> int:
    for pattern in (r"(?:^|_)sprint_(\d+)(?:_|$)", r"(?:^|_)sprint(\d+)(?:_|$)"):
        match = re.search(pattern, name)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 10**6
    return 10**6


def _read_execution_story_ids(execution_file: Path) -> list[str]:
    if not execution_file.exists():
        return []
    return [line.strip() for line in execution_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve_story_card_paths(sprint_dir: Path) -> list[Path]:
    execution_file = sprint_dir / "execution_order.txt"
    story_ids = _read_execution_story_ids(execution_file)
    ordered: list[Path] = []
    seen: set[Path] = set()
    for story_id in story_ids:
        story_file = next(sprint_dir.rglob(f"{story_id}_*.yaml"), None)
        if story_file is None:
            continue
        story_file = story_file.resolve()
        if story_file in seen:
            continue
        seen.add(story_file)
        ordered.append(story_file)
    if ordered:
        return ordered
    return sorted(path.resolve() for path in sprint_dir.rglob("*.yaml") if path.is_file())


def _derive_backlog_context_from_sprint_dir(
    sprint_dir: Path,
    repo_b_path: Path,
    *,
    backlog_id_override: str | None = None,
    backlog_root_override: str | None = None,
) -> tuple[str, str]:
    if str(backlog_id_override or "").strip() and str(backlog_root_override or "").strip():
        return str(backlog_id_override), str(backlog_root_override)

    tasks_root = repo_b_path / "tasks"
    sprint_path = sprint_dir.resolve()
    if sprint_path.parent.resolve() == tasks_root.resolve() and "_sprint_" in sprint_path.name:
        derived_backlog_id = sprint_path.name.split("_sprint_", 1)[0].strip() or tasks_root.name
        return (
            str(backlog_id_override or derived_backlog_id),
            str(backlog_root_override or tasks_root),
        )

    derived_backlog_id = sprint_path.parent.name
    derived_backlog_root = str(sprint_path.parent)
    return (
        str(backlog_id_override or derived_backlog_id),
        str(backlog_root_override or derived_backlog_root),
    )


def _build_roadmap_resume_command(
    *,
    project: str,
    env: str,
    tasks_root: Path,
    roadmap_prefix: str,
    release: bool,
) -> str:
    command = (
        f'python cli.py run-roadmap --project {project} --env {env} '
        f'--tasks-root "{tasks_root}" --roadmap-prefix {roadmap_prefix} --resume'
    )
    if release:
        command += " --release"
    return command


def _load_existing_backlog_result(repo_b_path: Path, project: str, prefix: str) -> tuple[dict[str, object], Path, Path]:
    tasks_root = _resolve_tasks_root(repo_b_path, project)
    backlog_root = tasks_root / prefix
    if not backlog_root.exists() or not (backlog_root / "sprint_overview.md").exists():
        raise click.ClickException(f"Existing backlog does not exist: {backlog_root}")
    sprint_dirs = _sort_sprint_paths([path for path in backlog_root.iterdir() if path.is_dir() and path.name.startswith("sprint_")])
    story_cards = [str(path) for sprint_dir in sprint_dirs for path in _resolve_story_card_paths(sprint_dir)]
    return (
        {
            "backlog_root": str(backlog_root),
            "overview_path": str(backlog_root / "sprint_overview.md"),
            "sprint_dirs": [str(path) for path in sprint_dirs],
            "story_cards": story_cards,
        },
        repo_b_path,
        tasks_root,
    )


def _resolve_backlog_for_auto_delivery(
    *,
    env: str,
    project: str,
    prefix: str,
    sprint: str,
    requirement: str | None,
    requirement_file: str | None,
) -> tuple[dict[str, object], Path, Path]:
    config = _load_env_config(env)
    repo_b_path = _resolve_project_repo_path(config, project)
    if not requirement and not requirement_file:
        existing_backlog = _resolve_tasks_root(repo_b_path, project) / prefix
        if existing_backlog.exists() and (existing_backlog / "sprint_overview.md").exists():
            return _load_existing_backlog_result(repo_b_path, project, prefix)
    return _build_backlog_from_requirement(
        env=env,
        project=project,
        prefix=prefix,
        sprint=sprint,
        requirement=requirement,
        requirement_file=requirement_file,
    )


def _load_successful_story_index(project: str) -> dict[str, dict[str, object]]:
    audit_dir = ROOT_DIR / "runs"
    index: dict[str, dict[str, object]] = {}
    for audit_path in sorted(audit_dir.glob("prod_audit_*.json")):
        try:
            payload = json.loads(audit_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("project") != project or not payload.get("success"):
            continue
        result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
        task_payload = result.get("task_payload", {}) if isinstance(result.get("task_payload"), dict) else {}
        story_id = str(task_payload.get("story_id") or task_payload.get("task_id") or "").strip()
        if not story_id:
            continue
        created_at = str(payload.get("created_at") or "")
        existing = index.get(story_id)
        if existing and str(existing.get("created_at") or "") >= created_at:
            continue
        index[story_id] = {
            "story_id": story_id,
            "task_id": payload.get("task_id"),
            "branch": payload.get("branch"),
            "commit": payload.get("commit"),
            "audit_path": str(audit_path),
            "created_at": created_at,
            "backlog_id": task_payload.get("backlog_id"),
            "sprint_id": task_payload.get("sprint_id"),
            "artifact_dir": payload.get("artifact_dir"),
            "audit_payload": payload,
            "result_payload": result,
            "task_payload": task_payload,
            "source": "existing_success_audit",
            "skipped": True,
        }
    return index


def _load_backlog_story_specs(backlog_root: Path) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    if not backlog_root.exists():
        return specs
    for sprint_dir in _sort_sprint_paths([path for path in backlog_root.iterdir() if path.is_dir() and path.name.startswith("sprint_")]):
        execution_file = sprint_dir / "execution_order.txt"
        if not execution_file.exists():
            continue
        story_ids = [line.strip() for line in execution_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        for position, story_id in enumerate(story_ids):
            story_file = next(sprint_dir.rglob(f"{story_id}_*.yaml"), None)
            specs.append(
                {
                    "backlog_id": backlog_root.name,
                    "sprint_id": sprint_dir.name,
                    "story_id": story_id,
                    "story_file": story_file,
                    "position": position,
                }
            )
    return specs


def _is_finahunt_sprint5_authoritative_rerun(project: str, sprint_dir: Path) -> bool:
    return project == "finahunt" and "low_position_one_shot_workbench" in sprint_dir.name


def _build_authoritative_attempt(sprint_dir: Path) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{sprint_dir.name}-attempt-{timestamp}"


def _read_registry_entries(path: Path, key: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = payload.get(key) if isinstance(payload, dict) else []
    return entries if isinstance(entries, list) else []


def _runtime_story_key(backlog_id: str | None, sprint_id: str | None, story_id: str | None) -> tuple[str, str, str]:
    return (str(backlog_id or ""), str(sprint_id or ""), str(story_id or ""))


def _runtime_task_from_story_spec(spec: dict[str, object], repo_b_path: Path, project: str, audit_task_payload: dict[str, object] | None) -> dict[str, object]:
    story_file = spec.get("story_file")
    raw_payload: dict[str, object]
    if isinstance(story_file, Path) and story_file.exists():
        parsed = yaml.safe_load(story_file.read_text(encoding="utf-8"))
        raw_payload = parsed if isinstance(parsed, dict) else {}
        task = normalize_runtime_task_payload(raw_payload)
        task.update(locate_story_context(story_file, repo_b_path))
        task["story_file"] = str(story_file)
    else:
        raw_payload = dict(audit_task_payload or {})
        try:
            task = normalize_runtime_task_payload(raw_payload)
        except Exception:
            task = dict(raw_payload)
        task.setdefault("tasks_root", str(repo_b_path / "tasks"))
        task.setdefault("backlog_id", spec.get("backlog_id"))
        task.setdefault("sprint_id", spec.get("sprint_id"))
        task.setdefault("story_id", spec.get("story_id"))
    task["project"] = project
    task["project_repo_root"] = str(repo_b_path)
    task["backlog_root"] = str(repo_b_path / "tasks" / str(task.get("backlog_id") or spec.get("backlog_id") or ""))
    if task.get("auto_run") is None:
        task["auto_run"] = True
    if not str(task.get("execution_policy") or "").strip():
        task["execution_policy"] = "continuous_full_sprint"
    if not str(task.get("interaction_policy") or "").strip():
        task["interaction_policy"] = "non_interactive_auto_run"
    if not str(task.get("pause_policy") or "").strip():
        task["pause_policy"] = "story_boundary_or_shared_blocker_only"
    if not str(task.get("run_policy") or "").strip():
        task["run_policy"] = "single_pass_to_completion"
    if not str(task.get("acceptance_policy") or "").strip():
        task["acceptance_policy"] = "must_pass_all_required_runs"
    if not str(task.get("retry_policy") or "").strip():
        task["retry_policy"] = "auto_repair_until_green"
    if task.get("acceptance_attempt") is None:
        task["acceptance_attempt"] = 0
    if task.get("repair_iteration") is None:
        task["repair_iteration"] = 0
    if task.get("final_green_required") is None:
        task["final_green_required"] = True
    return apply_agent_activation_policy(task, repo_b_path)


def _load_story_payload(story_file: Path, repo_b_path: Path, project: str) -> dict[str, object]:
    payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise click.ClickException(f"Story card must contain a mapping: {story_file}")
    task = normalize_runtime_task_payload(payload)
    task.update(locate_story_context(story_file, repo_b_path))
    task["story_file"] = str(story_file)
    task["project"] = project
    task["project_repo_root"] = str(repo_b_path)
    task["backlog_root"] = str(repo_b_path / "tasks" / str(task.get("backlog_id") or ""))
    return task


def _admit_story_file(
    story_file: Path,
    repo_b_path: Path,
    project: str,
    task_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    task = _load_story_payload(story_file, repo_b_path, project)
    if task_overrides:
        task.update({str(key): value for key, value in task_overrides.items() if value is not None})
    admission = build_story_admission(task, repo_b_path, story_file=story_file)
    story_id = str(task.get("story_id") or task.get("task_id") or story_file.stem)
    admission_path = write_story_admission(repo_b_path, story_id, admission)
    admission["admission_path"] = str(admission_path)
    return admission


def _build_reconciled_coverage(audit_snapshot: dict[str, object], runtime_task: dict[str, object]) -> dict[str, object]:
    result_payload = audit_snapshot.get("result_payload") if isinstance(audit_snapshot.get("result_payload"), dict) else {}
    task_payload = audit_snapshot.get("task_payload") if isinstance(audit_snapshot.get("task_payload"), dict) else {}
    executed_modes = list(result_payload.get("executed_modes") or [])
    required_modes = list(runtime_task.get("required_modes") or result_payload.get("required_modes") or task_payload.get("required_modes") or [])
    advisory_modes = list(runtime_task.get("advisory_modes") or result_payload.get("advisory_modes") or task_payload.get("advisory_modes") or [])
    mode_execution_order = list(result_payload.get("mode_execution_order") or executed_modes)
    mode_artifact_paths = result_payload.get("mode_artifact_paths") if isinstance(result_payload.get("mode_artifact_paths"), dict) else {}
    if not mode_artifact_paths:
        mode_artifact_paths = collect_mode_artifact_paths(result_payload)
    coverage = build_mode_coverage(required_modes, advisory_modes, executed_modes)
    return {
        "required_modes": required_modes,
        "executed_modes": executed_modes,
        "advisory_modes": advisory_modes,
        "mode_execution_order": mode_execution_order,
        "mode_artifact_paths": mode_artifact_paths,
        "agent_mode_coverage": coverage,
    }


def _reconcile_success_story(
    *,
    repo_b_path: Path,
    project: str,
    spec: dict[str, object],
    audit_snapshot: dict[str, object],
) -> dict[str, object]:
    runtime_task = _runtime_task_from_story_spec(spec, repo_b_path, project, audit_snapshot.get("task_payload") if isinstance(audit_snapshot, dict) else None)
    coverage_payload = _build_reconciled_coverage(audit_snapshot, runtime_task)
    story_id = str(spec.get("story_id") or "")
    backlog_id = str(spec.get("backlog_id") or runtime_task.get("backlog_id") or "")
    sprint_id = str(spec.get("sprint_id") or runtime_task.get("sprint_id") or "")
    audit_path = str(audit_snapshot.get("audit_path") or "")
    artifact_dir = str(audit_snapshot.get("artifact_dir") or "")
    task_id = str(audit_snapshot.get("task_id") or "")
    commit = str(audit_snapshot.get("commit") or "") or None
    created_at = str(audit_snapshot.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    result_payload = audit_snapshot.get("result_payload") if isinstance(audit_snapshot.get("result_payload"), dict) else {}
    story_handoff_path = write_story_handoff(
        repo_b_path,
        story_id,
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": sprint_id,
            "story_id": story_id,
            "task_name": runtime_task.get("task_name") or runtime_task.get("goal"),
            "current_node": result_payload.get("last_node") or "doc_writer",
            "status": "done",
            "last_success_story": story_id,
            "resume_from_story": story_id,
            "root_cause": "Story completed successfully (reconciled from historical success audit).",
            "next_action": "Continue to the next story in the execution order.",
            "resume_command": f"python cli.py auto-deliver --project {project} --env test --prefix {backlog_id or 'backlog_v1'} --auto-run",
            "evidence_paths": [item for item in (audit_path, artifact_dir) if item],
        },
    )
    update_story_status(
        repo_b_path,
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": sprint_id,
            "story_id": story_id,
            "task_id": task_id,
            "status": "done",
            "branch": audit_snapshot.get("branch"),
            "commit": commit,
            "started_at": result_payload.get("collaboration_started_at") or created_at,
            "finished_at": result_payload.get("collaboration_ended_at") or created_at,
            "verified_at": created_at,
            "last_node": result_payload.get("last_node") or "doc_writer",
            "audit_path": audit_path,
            "resume_token": story_id,
            "source": "agentsystem_reconciled_success_audit",
            "summary": "Reconciled from historical success audit.",
            "validation_summary": str(result_payload.get("test_results") or ""),
            "delivery_report": str(result_payload.get("delivery_dir") or ""),
            "evidence": [item for item in (audit_path, artifact_dir, str(story_handoff_path)) if item],
            "formal_entry": True,
            "formal_acceptance_reviewer": "acceptance_gate",
            "attempt_status": "authoritative",
            "required_modes": coverage_payload["required_modes"],
            "executed_modes": coverage_payload["executed_modes"],
            "advisory_modes": coverage_payload["advisory_modes"],
            "agent_mode_coverage": coverage_payload["agent_mode_coverage"],
            "implemented": True,
            "verified": True,
            "agentized": bool(coverage_payload["agent_mode_coverage"].get("all_required_executed")),
            "accepted": bool(coverage_payload["agent_mode_coverage"].get("all_required_executed")),
            "repository": project,
        },
    )
    update_story_acceptance_review(
        repo_b_path,
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": sprint_id,
            "story_id": story_id,
            "reviewer": "acceptance_gate",
            "review_type": "machine",
            "verdict": "approved" if coverage_payload["agent_mode_coverage"].get("all_required_executed") else "needs_followup",
            "acceptance_status": "approved" if coverage_payload["agent_mode_coverage"].get("all_required_executed") else "needs_followup",
            "summary": "Reconciled automatic acceptance from historical success audit.",
            "review_findings_summary": {"blocking": [], "important": [], "nice_to_haves": []},
            "notes": str(story_handoff_path),
            "checked_at": created_at,
            "agent_mode_coverage": coverage_payload["agent_mode_coverage"],
            "evidence_paths": [item for item in (audit_path, artifact_dir, str(story_handoff_path)) if item],
            "formal_entry": True,
            "attempt_status": "authoritative",
            "implemented": True,
            "verified": True,
            "agentized": bool(coverage_payload["agent_mode_coverage"].get("all_required_executed")),
            "accepted": bool(coverage_payload["agent_mode_coverage"].get("all_required_executed")),
        },
    )
    update_agent_coverage_report(
        repo_b_path,
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": sprint_id,
            "story_id": story_id,
            "required_modes": coverage_payload["required_modes"],
            "executed_modes": coverage_payload["executed_modes"],
            "advisory_modes": coverage_payload["advisory_modes"],
            "mode_execution_order": coverage_payload["mode_execution_order"],
            "mode_artifact_paths": coverage_payload["mode_artifact_paths"],
            "agent_mode_coverage": coverage_payload["agent_mode_coverage"],
            "status": "done",
            "audit_path": audit_path,
            "attempt_status": "authoritative",
        },
    )
    return {
        **audit_snapshot,
        "backlog_id": backlog_id,
        "sprint_id": sprint_id,
        "story_id": story_id,
        "status": "done",
        "required_modes": coverage_payload["required_modes"],
        "executed_modes": coverage_payload["executed_modes"],
        "advisory_modes": coverage_payload["advisory_modes"],
        "mode_execution_order": coverage_payload["mode_execution_order"],
        "mode_artifact_paths": coverage_payload["mode_artifact_paths"],
        "agent_mode_coverage": coverage_payload["agent_mode_coverage"],
        "handoff_path": str(story_handoff_path),
    }


def _reconcile_backlog_successes(project: str, repo_b_path: Path, backlog_root: Path) -> dict[str, dict[str, object]]:
    ensure_runtime_layout(repo_b_path)
    successful_audits = _load_successful_story_index(project)
    reconciled: dict[str, dict[str, object]] = {}
    for spec in _load_backlog_story_specs(backlog_root):
        story_id = str(spec.get("story_id") or "")
        audit_snapshot = successful_audits.get(story_id)
        if not audit_snapshot:
            continue
        snapshot_backlog_id = str(audit_snapshot.get("backlog_id") or "")
        if snapshot_backlog_id and snapshot_backlog_id != backlog_root.name:
            continue
        reconciled[story_id] = _reconcile_success_story(
            repo_b_path=repo_b_path,
            project=project,
            spec=spec,
            audit_snapshot=audit_snapshot,
        )
    return reconciled


def _refresh_auto_delivery_counts(payload: dict[str, object]) -> None:
    sprints = payload.get("sprints") or []
    if not isinstance(sprints, list):
        payload["completed_story_count"] = 0
        payload["failed_story_count"] = 0
        return
    payload["completed_story_count"] = sum(len(item.get("completed_stories") or []) for item in sprints if isinstance(item, dict))
    payload["failed_story_count"] = sum(len(item.get("failed_stories") or []) for item in sprints if isinstance(item, dict))


def _resolve_resume_cursor(
    repo_b_path: Path,
    backlog_root: str,
    successful_story_index: dict[str, dict[str, object]],
) -> tuple[str | None, str | None, str | None, str | None]:
    backlog_path = Path(backlog_root)
    resume_state = read_resume_state(repo_b_path)
    interruption_reason = None
    if str(resume_state.get("status") or "") == "interrupted":
        if not str(resume_state.get("backlog_root") or "") or str(resume_state.get("backlog_root") or "") == str(backlog_path):
            interruption_reason = str(resume_state.get("interruption_reason") or "").strip() or None

    last_success_story: str | None = None
    for spec in _load_backlog_story_specs(backlog_path):
        story_id = str(spec.get("story_id") or "")
        if story_id in successful_story_index:
            last_success_story = story_id
            continue
        return (
            str(spec.get("sprint_id") or "").strip() or None,
            story_id or None,
            last_success_story,
            interruption_reason,
        )
    return None, None, last_success_story, interruption_reason


def _persist_auto_delivery_runtime(
    repo_b_path: Path,
    summary_path: Path,
    payload: dict[str, object],
    *,
    next_action: str,
    cleanup_note: str,
) -> None:
    checkpoint_at = datetime.now().isoformat(timespec="seconds")
    payload["last_updated_at"] = checkpoint_at
    payload["last_checkpoint_at"] = checkpoint_at
    _refresh_auto_delivery_counts(payload)
    _write_auto_delivery_summary(payload, summary_path)
    clear_keys = (
        ["current_story", "current_node", "resume_from_story", "interruption_reason", "error_message", "failure_snapshot_path"]
        if str(payload.get("status") or "") == "completed"
        else []
    )
    write_resume_state(
        repo_b_path,
        {
            "project": payload.get("project"),
            "backlog_id": Path(str(payload.get("backlog_root") or "")).name if payload.get("backlog_root") else None,
            "backlog_root": payload.get("backlog_root"),
            "sprint_id": payload.get("current_sprint"),
            "story_id": payload.get("current_story") or payload.get("last_success_story"),
            "current_node": payload.get("current_node"),
            "status": payload.get("status"),
            "last_success_story": payload.get("last_success_story"),
            "resume_from_story": payload.get("resume_from_story"),
            "interruption_reason": payload.get("interruption_reason"),
            "execution_policy": payload.get("execution_policy"),
            "interaction_policy": payload.get("interaction_policy"),
            "pause_policy": payload.get("pause_policy"),
            "run_policy": payload.get("run_policy"),
            "acceptance_policy": payload.get("acceptance_policy"),
            "retry_policy": payload.get("retry_policy"),
            "acceptance_attempt": payload.get("acceptance_attempt"),
            "acceptance_failure_class": payload.get("acceptance_failure_class"),
            "repair_iteration": payload.get("repair_iteration"),
            "final_green_required": payload.get("final_green_required"),
        },
        clear_keys=clear_keys,
    )
    write_current_handoff(
        repo_b_path,
        {
            "project": payload.get("project"),
            "backlog_id": Path(str(payload.get("backlog_root") or "")).name if payload.get("backlog_root") else None,
            "sprint_id": payload.get("current_sprint"),
            "story_id": payload.get("current_story") or payload.get("resume_from_story") or payload.get("last_success_story"),
            "current_node": payload.get("current_node"),
            "status": payload.get("status"),
            "last_success_story": payload.get("last_success_story"),
            "resume_from_story": payload.get("resume_from_story"),
            "interruption_reason": payload.get("interruption_reason"),
            "root_cause": payload.get("error_message")
            or payload.get("interruption_reason")
            or ("Automatic delivery completed." if str(payload.get("status") or "") == "completed" else "Auto delivery state persisted."),
            "next_action": next_action,
            "resume_command": f"python cli.py auto-deliver --project {payload.get('project')} --env {payload.get('env')} --prefix {Path(str(payload.get('backlog_root') or '')).name or 'backlog_v1'} --auto-run",
            "evidence_paths": [str(summary_path)],
            "cleanup_note": cleanup_note,
            "execution_policy": payload.get("execution_policy"),
            "interaction_policy": payload.get("interaction_policy"),
            "pause_policy": payload.get("pause_policy"),
            "run_policy": payload.get("run_policy"),
            "acceptance_policy": payload.get("acceptance_policy"),
            "retry_policy": payload.get("retry_policy"),
            "acceptance_attempt": payload.get("acceptance_attempt"),
            "acceptance_failure_class": payload.get("acceptance_failure_class"),
            "repair_iteration": payload.get("repair_iteration"),
            "final_green_required": payload.get("final_green_required"),
        },
    )


def _write_roadmap_summary(payload: dict[str, object], summary_path: Path | None = None) -> Path:
    output_dir = ROOT_DIR / "runs" / "roadmaps"
    output_dir.mkdir(parents=True, exist_ok=True)
    if summary_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        roadmap_prefix = str(payload.get("roadmap_prefix") or "roadmap").replace("\\", "_").replace("/", "_")
        summary_path = output_dir / f"{roadmap_prefix}_{timestamp}.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def _refresh_roadmap_counts(payload: dict[str, object]) -> None:
    sprints = payload.get("sprints") or []
    if not isinstance(sprints, list):
        payload["completed_story_count"] = 0
        payload["failed_story_count"] = 0
        return
    payload["completed_story_count"] = sum(len(item.get("completed_stories") or []) for item in sprints if isinstance(item, dict))
    payload["failed_story_count"] = sum(len(item.get("failed_stories") or []) for item in sprints if isinstance(item, dict))


def _load_successful_story_status_index(repo_b_path: Path, backlog_id: str) -> dict[str, dict[str, object]]:
    registry_path = repo_b_path / "tasks" / "story_status_registry.json"
    index: dict[str, dict[str, object]] = {}
    for entry in _read_registry_entries(registry_path, "stories"):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("backlog_id") or "").strip() != str(backlog_id).strip():
            continue
        if str(entry.get("status") or "").strip() != "done":
            continue
        story_id = str(entry.get("story_id") or "").strip()
        if not story_id:
            continue
        index[story_id] = {
            "story_id": story_id,
            "task_id": entry.get("task_id"),
            "commit": entry.get("commit"),
            "branch": entry.get("branch"),
            "status": "done",
        }
    return index


def _discover_roadmap_result(tasks_root: Path, roadmap_prefix: str) -> dict[str, object]:
    tasks_path = tasks_root.resolve()
    sprint_dirs = _sort_sprint_paths(
        [path for path in tasks_path.iterdir() if path.is_dir() and path.name.startswith(f"{roadmap_prefix}_sprint_")]
    )
    if not sprint_dirs:
        raise click.ClickException(f"No sprint directories found for roadmap prefix: {roadmap_prefix}")
    story_cards = [str(path) for sprint_dir in sprint_dirs for path in _resolve_story_card_paths(sprint_dir)]
    return {
        "roadmap_prefix": roadmap_prefix,
        "tasks_root": str(tasks_path),
        "sprint_dirs": [str(path) for path in sprint_dirs],
        "story_cards": story_cards,
    }


def _preflight_story_file(
    story_file: Path,
    *,
    repo_b_path: Path,
    project: str,
    backlog_id: str,
    backlog_root: str,
    sprint_id: str,
) -> dict[str, object]:
    try:
        task = _load_story_payload(story_file, repo_b_path, project)
        task.update(
            {
                "backlog_id": backlog_id,
                "backlog_root": backlog_root,
                "sprint_id": sprint_id,
                "auto_run": True,
                "formal_entry": True,
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "office_hours_path": "preflight://office-hours",
                "plan_ceo_review_path": "preflight://plan-ceo-review",
                "sprint_framing_path": "preflight://sprint-framing",
                "gstack_parity_manifest_path": "preflight://gstack-parity",
                "gstack_acceptance_checklist_path": "preflight://gstack-checklist",
            }
        )
        admission = build_story_admission(task, repo_b_path, story_file=story_file)
    except Exception as exc:
        return {
            "story_id": story_file.stem,
            "story_file": str(story_file),
            "admitted": False,
            "errors": [str(exc)],
        }
    return {
        "story_id": str(task.get("story_id") or task.get("task_id") or story_file.stem),
        "story_file": str(story_file),
        "admitted": bool(admission.get("admitted")),
        "errors": list(admission.get("errors") or []),
        "warnings": list(admission.get("warnings") or []),
        "required_modes": list(admission.get("required_modes") or []),
        "advisory_modes": list(admission.get("advisory_modes") or []),
    }


def _preflight_roadmap(
    *,
    repo_b_path: Path,
    project: str,
    tasks_root: Path,
    roadmap_result: dict[str, object],
) -> dict[str, object]:
    roadmap_prefix = str(roadmap_result.get("roadmap_prefix") or "").strip()
    sprint_dirs = [Path(item).resolve() for item in (roadmap_result.get("sprint_dirs") or [])]
    preflight: dict[str, object] = {
        "roadmap_prefix": roadmap_prefix,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "story_count": len(roadmap_result.get("story_cards") or []),
        "passed": True,
        "errors": [],
        "sprints": [],
    }
    for sprint_dir in sprint_dirs:
        sprint_errors: list[str] = []
        sprint_execution_file = sprint_dir / "execution_order.txt"
        sprint_plan_path = sprint_dir / "sprint_plan.md"
        if not sprint_plan_path.exists():
            sprint_errors.append(f"Missing sprint_plan.md: {sprint_plan_path}")
        if not sprint_execution_file.exists():
            sprint_errors.append(f"Missing execution_order.txt: {sprint_execution_file}")
        story_ids = _read_execution_story_ids(sprint_execution_file)
        if not story_ids:
            sprint_errors.append(f"No stories declared in execution_order.txt: {sprint_execution_file}")
        sprint_summary = {
            "sprint_dir": str(sprint_dir),
            "sprint_id": sprint_dir.name,
            "story_count": len(story_ids),
            "stories": [],
            "errors": sprint_errors,
        }
        for story_id in story_ids:
            matches = [path.resolve() for path in sprint_dir.rglob(f"{story_id}_*.yaml")]
            if len(matches) != 1:
                sprint_errors.append(
                    f"Story {story_id} must resolve to exactly one YAML, found {len(matches)} in {sprint_dir}"
                )
                sprint_summary["stories"].append(
                    {
                        "story_id": story_id,
                        "admitted": False,
                        "errors": [f"Ambiguous or missing story file for {story_id}"],
                    }
                )
                continue
            sprint_summary["stories"].append(
                _preflight_story_file(
                    matches[0],
                    repo_b_path=repo_b_path,
                    project=project,
                    backlog_id=roadmap_prefix,
                    backlog_root=str(tasks_root),
                    sprint_id=sprint_dir.name,
                )
            )
        story_errors = [
            error
            for story in sprint_summary["stories"]
            if isinstance(story, dict)
            for error in (story.get("errors") or [])
            if str(error).strip()
        ]
        sprint_summary["errors"] = sprint_errors + story_errors
        if sprint_summary["errors"]:
            preflight["passed"] = False
            preflight["errors"].extend(sprint_summary["errors"])
        preflight["sprints"].append(sprint_summary)
    return preflight


def _resolve_roadmap_resume_cursor(
    repo_b_path: Path,
    *,
    roadmap_prefix: str,
    sprint_dirs: list[Path],
    successful_story_index: dict[str, dict[str, object]],
) -> tuple[str | None, str | None, str | None, str | None]:
    resume_state = read_resume_state(repo_b_path)
    resume_backlog_id = str(resume_state.get("backlog_id") or resume_state.get("roadmap_prefix") or "").strip()
    interruption_reason = None
    if str(resume_state.get("status") or "").strip() == "interrupted" and resume_backlog_id == roadmap_prefix:
        sprint_id = str(resume_state.get("sprint_id") or "").strip() or None
        story_id = str(resume_state.get("resume_from_story") or resume_state.get("story_id") or "").strip() or None
        interruption_reason = str(resume_state.get("interruption_reason") or "").strip() or None
        last_success_story = str(resume_state.get("last_success_story") or "").strip() or None
        if sprint_id and any(item.name == sprint_id for item in sprint_dirs):
            return sprint_id, story_id, last_success_story, interruption_reason

    last_success_story: str | None = None
    for sprint_dir in sprint_dirs:
        for story_id in _read_execution_story_ids(sprint_dir / "execution_order.txt"):
            if story_id in successful_story_index:
                last_success_story = story_id
                continue
            return sprint_dir.name, story_id, last_success_story, interruption_reason
    return None, None, last_success_story, interruption_reason


def _build_roadmap_verification(
    *,
    repo_b_path: Path,
    project: str,
    roadmap_summary: dict[str, object],
) -> dict[str, object]:
    continuity_paths = resolve_continuity_paths(repo_b_path, project)
    continuity = {
        "now_md_exists": continuity_paths["now_md"].exists(),
        "state_md_exists": continuity_paths["state_md"].exists(),
        "decisions_md_exists": continuity_paths["decisions_md"].exists(),
        "manifest_exists": continuity_paths["manifest_json"].exists(),
    }
    gstack: list[dict[str, object]] = []
    for sprint in (roadmap_summary.get("sprints") or []):
        if not isinstance(sprint, dict):
            continue
        pre_hook = sprint.get("pre_hook") if isinstance(sprint.get("pre_hook"), dict) else {}
        gstack.append(
            {
                "sprint_id": sprint.get("sprint_id") or Path(str(sprint.get("sprint_dir") or "")).name,
                "office_hours_ready": Path(str(pre_hook.get("office_hours_path") or "")).exists(),
                "plan_ceo_review_ready": Path(str(pre_hook.get("plan_ceo_review_path") or "")).exists(),
                "sprint_framing_ready": Path(str(pre_hook.get("sprint_framing_path") or "")).exists(),
                "parity_manifest_ready": Path(str(pre_hook.get("parity_manifest_path") or "")).exists(),
                "acceptance_checklist_ready": Path(str(pre_hook.get("acceptance_checklist_path") or "")).exists(),
            }
        )
    return {"continuity": continuity, "gstack": gstack}


def _persist_roadmap_runtime(
    repo_b_path: Path,
    summary_path: Path,
    payload: dict[str, object],
    *,
    next_action: str,
    cleanup_note: str,
) -> None:
    checkpoint_at = datetime.now().isoformat(timespec="seconds")
    payload["last_updated_at"] = checkpoint_at
    payload["last_checkpoint_at"] = checkpoint_at
    payload["verification"] = _build_roadmap_verification(repo_b_path=repo_b_path, project=str(payload.get("project") or ""), roadmap_summary=payload)
    _refresh_roadmap_counts(payload)
    _write_roadmap_summary(payload, summary_path)
    clear_keys = (
        ["current_story", "current_node", "resume_from_story", "interruption_reason", "error_message", "failure_snapshot_path"]
        if str(payload.get("status") or "") == "completed"
        else []
    )
    write_resume_state(
        repo_b_path,
        {
            "project": payload.get("project"),
            "backlog_id": payload.get("roadmap_prefix"),
            "backlog_root": payload.get("tasks_root"),
            "sprint_id": payload.get("current_sprint"),
            "story_id": payload.get("current_story") or payload.get("last_success_story"),
            "current_node": payload.get("current_node"),
            "status": payload.get("status"),
            "last_success_story": payload.get("last_success_story"),
            "resume_from_story": payload.get("resume_from_story"),
            "interruption_reason": payload.get("interruption_reason"),
            "error_message": payload.get("error_message"),
            "execution_policy": payload.get("execution_policy"),
            "interaction_policy": payload.get("interaction_policy"),
            "pause_policy": payload.get("pause_policy"),
            "run_policy": payload.get("run_policy"),
            "acceptance_policy": payload.get("acceptance_policy"),
            "retry_policy": payload.get("retry_policy"),
            "acceptance_attempt": payload.get("acceptance_attempt"),
            "acceptance_failure_class": payload.get("acceptance_failure_class"),
            "repair_iteration": payload.get("repair_iteration"),
            "final_green_required": payload.get("final_green_required"),
            "roadmap_prefix": payload.get("roadmap_prefix"),
            "roadmap_summary_path": str(summary_path),
        },
        clear_keys=clear_keys,
    )
    write_current_handoff(
        repo_b_path,
        {
            "project": payload.get("project"),
            "backlog_id": payload.get("roadmap_prefix"),
            "sprint_id": payload.get("current_sprint"),
            "story_id": payload.get("current_story") or payload.get("resume_from_story") or payload.get("last_success_story"),
            "current_node": payload.get("current_node"),
            "status": payload.get("status"),
            "last_success_story": payload.get("last_success_story"),
            "resume_from_story": payload.get("resume_from_story"),
            "interruption_reason": payload.get("interruption_reason"),
            "root_cause": payload.get("error_message")
            or payload.get("interruption_reason")
            or ("Roadmap execution completed." if str(payload.get("status") or "") == "completed" else "Roadmap execution state persisted."),
            "next_action": next_action,
            "resume_command": _build_roadmap_resume_command(
                project=str(payload.get("project") or ""),
                env=str(payload.get("env") or "test"),
                tasks_root=Path(str(payload.get("tasks_root") or "")),
                roadmap_prefix=str(payload.get("roadmap_prefix") or ""),
                release=bool(payload.get("release")),
            ),
            "evidence_paths": [str(summary_path)],
            "cleanup_note": cleanup_note,
            "execution_policy": payload.get("execution_policy"),
            "interaction_policy": payload.get("interaction_policy"),
            "pause_policy": payload.get("pause_policy"),
            "run_policy": payload.get("run_policy"),
            "acceptance_policy": payload.get("acceptance_policy"),
            "retry_policy": payload.get("retry_policy"),
            "acceptance_attempt": payload.get("acceptance_attempt"),
            "acceptance_failure_class": payload.get("acceptance_failure_class"),
            "repair_iteration": payload.get("repair_iteration"),
            "final_green_required": payload.get("final_green_required"),
        },
    )


def _execute_roadmap(
    *,
    roadmap_result: dict[str, object],
    repo_b_path: Path,
    tasks_root: Path,
    env: str,
    project: str,
    release: bool,
    echo: Callable[[str], Any] | None = None,
) -> Path:
    printer = echo or click.echo
    roadmap_prefix = str(roadmap_result.get("roadmap_prefix") or "").strip()
    sprint_dirs = [Path(item).resolve() for item in (roadmap_result.get("sprint_dirs") or [])]
    resume_command = _build_roadmap_resume_command(
        project=project,
        env=env,
        tasks_root=tasks_root,
        roadmap_prefix=roadmap_prefix,
        release=release,
    )
    successful_story_index = _load_successful_story_status_index(repo_b_path, roadmap_prefix)
    resume_sprint_id, resume_story_id, last_success_story, interruption_reason = _resolve_roadmap_resume_cursor(
        repo_b_path,
        roadmap_prefix=roadmap_prefix,
        sprint_dirs=sprint_dirs,
        successful_story_index=successful_story_index,
    )
    roadmap_summary: dict[str, object] = {
        "project": project,
        "env": env,
        "repo_path": str(repo_b_path),
        "tasks_root": str(tasks_root),
        "roadmap_prefix": roadmap_prefix,
        "story_count": len(roadmap_result.get("story_cards") or []),
        "release": release,
        "status": "running",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "execution_policy": "continuous_full_sprint",
        "interaction_policy": "non_interactive_auto_run",
        "pause_policy": "story_boundary_or_shared_blocker_only",
        "run_policy": "single_pass_to_completion",
        "acceptance_policy": "must_pass_all_required_runs",
        "retry_policy": "auto_repair_until_green",
        "acceptance_attempt": 0,
        "acceptance_failure_class": None,
        "repair_iteration": 0,
        "final_green_required": True,
        "sprint_count": len(sprint_dirs),
        "sprint_dirs": [str(path) for path in sprint_dirs],
        "sprints": [],
        "current_sprint": resume_sprint_id,
        "current_story": resume_story_id,
        "current_node": None,
        "last_success_story": last_success_story,
        "resume_from_story": resume_story_id,
        "interruption_reason": interruption_reason,
        "error_message": None,
    }
    summary_path = _write_roadmap_summary(roadmap_summary)
    _persist_roadmap_runtime(
        repo_b_path,
        summary_path,
        roadmap_summary,
        next_action="Run roadmap execution from the current safe point.",
        cleanup_note="No cleanup required before roadmap execution continues.",
    )

    def upsert_sprint_result(sprint_payload: dict[str, object]) -> None:
        sprint_id = Path(str(sprint_payload.get("sprint_dir") or "")).name
        sprint_payload = {**sprint_payload, "sprint_id": sprint_id}
        existing = roadmap_summary.get("sprints")
        if not isinstance(existing, list):
            existing = []
            roadmap_summary["sprints"] = existing
        for index, current in enumerate(existing):
            if isinstance(current, dict) and str(current.get("sprint_id") or "") == sprint_id:
                existing[index] = sprint_payload
                break
        else:
            existing.append(sprint_payload)

    start_index = 0
    if resume_sprint_id:
        for index, sprint_dir in enumerate(sprint_dirs):
            if sprint_dir.name == resume_sprint_id:
                start_index = index
                break

    try:
        for sprint_dir in sprint_dirs[start_index:]:
            current_resume_story = resume_story_id if sprint_dir.name == resume_sprint_id else None
            sprint_success_index = {
                story_id: snapshot
                for story_id, snapshot in successful_story_index.items()
                if story_id in _read_execution_story_ids(sprint_dir / "execution_order.txt")
            }

            def progress_callback(progress: dict[str, object], *, sprint_name: str = sprint_dir.name) -> None:
                current_payload = dict(progress)
                current_payload["sprint_id"] = sprint_name
                upsert_sprint_result(current_payload)
                roadmap_summary["current_sprint"] = sprint_name
                roadmap_summary["current_story"] = current_payload.get("current_story")
                roadmap_summary["current_node"] = current_payload.get("current_node")
                roadmap_summary["last_success_story"] = current_payload.get("last_success_story") or roadmap_summary.get("last_success_story")
                roadmap_summary["resume_from_story"] = current_payload.get("resume_from_story")
                roadmap_summary["interruption_reason"] = current_payload.get("interruption_reason")
                roadmap_summary["error_message"] = current_payload.get("error_message")
                _persist_roadmap_runtime(
                    repo_b_path,
                    summary_path,
                    roadmap_summary,
                    next_action=f"Continue sprint {sprint_name} from the recorded safe point.",
                    cleanup_note="Inspect the current sprint evidence before resuming if a blocker remains.",
                )

            roadmap_summary["current_sprint"] = sprint_dir.name
            roadmap_summary["current_story"] = current_resume_story
            roadmap_summary["resume_from_story"] = current_resume_story
            _persist_roadmap_runtime(
                repo_b_path,
                summary_path,
                roadmap_summary,
                next_action=f"Execute sprint {sprint_dir.name}.",
                cleanup_note="No cleanup required before the next sprint starts.",
            )
            sprint_result = _run_sprint_directory(
                sprint_dir,
                repo_b_path=repo_b_path,
                env=env,
                project=project,
                release=release,
                start_story_id=current_resume_story,
                continue_on_failure=False,
                echo=printer,
                successful_story_index=sprint_success_index,
                progress_callback=progress_callback,
                backlog_id_override=roadmap_prefix,
                backlog_root_override=str(tasks_root),
                resume_command_override=resume_command,
            )
            upsert_sprint_result(sprint_result)
            roadmap_summary["last_success_story"] = sprint_result.get("last_success_story") or roadmap_summary.get("last_success_story")
            roadmap_summary["current_story"] = None
            roadmap_summary["current_node"] = sprint_result.get("current_node")
            roadmap_summary["resume_from_story"] = None
            roadmap_summary["interruption_reason"] = None
            roadmap_summary["error_message"] = None
            _persist_roadmap_runtime(
                repo_b_path,
                summary_path,
                roadmap_summary,
                next_action=f"Move to the next sprint after {sprint_dir.name}.",
                cleanup_note="No cleanup required before continuing to the next sprint.",
            )

        roadmap_summary["status"] = "completed"
        roadmap_summary["completed_at"] = datetime.now().isoformat(timespec="seconds")
        roadmap_summary["current_sprint"] = None
        roadmap_summary["current_story"] = None
        roadmap_summary["current_node"] = "doc_writer"
        roadmap_summary["resume_from_story"] = None
        roadmap_summary["interruption_reason"] = None
        roadmap_summary["error_message"] = None
        _persist_roadmap_runtime(
            repo_b_path,
            summary_path,
            roadmap_summary,
            next_action="Roadmap execution completed.",
            cleanup_note="No cleanup required.",
        )
        printer(f"Roadmap summary: {summary_path}")
        printer(f"Completed stories: {roadmap_summary.get('completed_story_count')}")
        printer(f"Failed stories: {roadmap_summary.get('failed_story_count')}")
        return summary_path
    except click.ClickException as exc:
        roadmap_summary["status"] = "interrupted"
        roadmap_summary["completed_at"] = datetime.now().isoformat(timespec="seconds")
        roadmap_summary["error_message"] = str(exc)
        roadmap_summary["interruption_reason"] = str(roadmap_summary.get("interruption_reason") or exc)
        _persist_roadmap_runtime(
            repo_b_path,
            summary_path,
            roadmap_summary,
            next_action="Inspect the last failed story and resume roadmap execution from the safe point.",
            cleanup_note="A failed worktree or sprint artifact may need inspection before retry.",
        )
        raise


def _sync_and_assert_continuity(
    *,
    trigger: str,
    project: str,
    repo_b_path: Path,
    task_payload: dict[str, Any] | None = None,
    current_story_path: Path | None = None,
    sprint_artifact_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    decision_refs: list[str] | None = None,
) -> dict[str, Any]:
    sync_continuity(
        trigger,
        project,
        repo_b_path,
        task_payload=task_payload,
        current_story_path=current_story_path,
        sprint_artifact_refs=sprint_artifact_refs,
        artifact_refs=artifact_refs,
        decision_refs=decision_refs,
    )
    bundle = load_continuity_bundle(
        trigger,
        project,
        repo_b_path,
        current_story_path=current_story_path,
        strict=False,
    )
    assert_continuity_ready(bundle, strict=True)
    return bundle


def _story_boundary_overrides(
    *,
    project: str,
    repo_b_path: Path,
    story_file: Path,
    pre_hook: dict[str, Any] | None = None,
    backlog_id: str | None = None,
    backlog_root: str | None = None,
    sprint_id: str | None = None,
) -> dict[str, Any]:
    sprint_refs = [
        str(item)
        for item in (
            (pre_hook or {}).get("office_hours_path"),
            (pre_hook or {}).get("plan_ceo_review_path"),
            (pre_hook or {}).get("sprint_framing_path"),
            (pre_hook or {}).get("parity_manifest_path"),
            (pre_hook or {}).get("acceptance_checklist_path"),
        )
        if str(item or "").strip()
    ]
    story_payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
    if not isinstance(story_payload, dict):
        story_payload = {}
    if backlog_id is not None:
        story_payload["backlog_id"] = backlog_id
    if backlog_root is not None:
        story_payload["backlog_root"] = backlog_root
    if sprint_id is not None:
        story_payload["sprint_id"] = sprint_id
    _sync_and_assert_continuity(
        trigger="story_boundary",
        project=project,
        repo_b_path=repo_b_path,
        task_payload=story_payload,
        current_story_path=story_file,
        sprint_artifact_refs=sprint_refs,
    )
    return {
        "continuity_trigger": "story_boundary",
        "continuity_story_path": str(story_file),
        "continuity_sprint_artifact_refs": sprint_refs,
        "gstack_parity_manifest_path": (pre_hook or {}).get("parity_manifest_path"),
        "gstack_acceptance_checklist_path": (pre_hook or {}).get("acceptance_checklist_path"),
    }


def _execute_auto_delivery(
    *,
    backlog_result: dict[str, object],
    repo_b_path: Path,
    tasks_root: Path,
    env: str,
    project: str,
    release: bool,
    echo: Callable[[str], Any] | None = None,
) -> Path:
    printer = echo or click.echo
    sprint_dirs = [Path(item).resolve() for item in (backlog_result.get("sprint_dirs") or [])]
    backlog_root_path = Path(str(backlog_result["backlog_root"])).resolve()
    backlog_root = str(backlog_root_path)
    successful_story_index = _reconcile_backlog_successes(project, repo_b_path, backlog_root_path)
    if project == "finahunt":
        for sprint_dir in sprint_dirs:
            if not _is_finahunt_sprint5_authoritative_rerun(project, sprint_dir):
                continue
            for story_id in [line.strip() for line in (sprint_dir / "execution_order.txt").read_text(encoding="utf-8").splitlines() if line.strip()]:
                successful_story_index.pop(story_id, None)
    resume_sprint_id, resume_story_id, last_success_story, interruption_reason = _resolve_resume_cursor(
        repo_b_path,
        backlog_root,
        successful_story_index,
    )
    if resume_sprint_id and not any(sprint_dir.name == resume_sprint_id for sprint_dir in sprint_dirs):
        resume_sprint_id = None
        resume_story_id = None
        last_success_story = None
        interruption_reason = None
    backlog_summary: dict[str, object] = {
        "project": project,
        "env": env,
        "repo_path": str(repo_b_path),
        "tasks_root": str(tasks_root),
        "backlog_root": backlog_root,
        "story_count": len(backlog_result["story_cards"]),
        "auto_run": True,
        "execution_policy": "continuous_full_sprint",
        "interaction_policy": "non_interactive_auto_run",
        "pause_policy": "story_boundary_or_shared_blocker_only",
        "run_policy": "single_pass_to_completion",
        "acceptance_policy": "must_pass_all_required_runs",
        "retry_policy": "auto_repair_until_green",
        "release": release,
        "status": "running",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "acceptance_attempt": 0,
        "acceptance_failure_class": None,
        "repair_iteration": 0,
        "final_green_required": True,
        "current_sprint": resume_sprint_id,
        "current_story": resume_story_id,
        "current_node": None,
        "last_success_story": last_success_story,
        "resume_from_story": resume_story_id,
        "interruption_reason": interruption_reason,
        "sprints": [],
    }
    summary_path = _write_auto_delivery_summary(backlog_summary)

    if resume_story_id is None:
        backlog_summary["status"] = "completed"
        backlog_summary["current_sprint"] = None
        backlog_summary["current_story"] = None
        backlog_summary["current_node"] = None
        backlog_summary["resume_from_story"] = None
        backlog_summary["interruption_reason"] = None
        backlog_summary["error_message"] = None
        _persist_auto_delivery_runtime(
            repo_b_path,
            summary_path,
            backlog_summary,
            next_action="Automatic delivery already matches the current backlog state.",
            cleanup_note="No cleanup required.",
        )
        printer(f"Auto delivery summary: {summary_path}")
        printer(f"Completed stories: {backlog_summary['completed_story_count']}")
        printer(f"Failed stories: {backlog_summary['failed_story_count']}")
        return summary_path

    _persist_auto_delivery_runtime(
        repo_b_path,
        summary_path,
        backlog_summary,
        next_action="Resume or continue automatic story delivery from the recorded cursor.",
        cleanup_note="No cleanup required before continuing.",
    )

    try:
        for sprint_dir in sprint_dirs:
            printer(f"Running sprint: {sprint_dir.name}")
            sprint_snapshot: dict[str, object] = {
                "sprint_dir": str(sprint_dir),
                "story_count": 0,
                "completed_stories": [],
                "failed_stories": [],
                "pre_hook": None,
                "post_hook": None,
                "status": "running",
            }
            backlog_summary["sprints"].append(sprint_snapshot)
            backlog_summary["current_sprint"] = sprint_dir.name
            _persist_auto_delivery_runtime(
                repo_b_path,
                summary_path,
                backlog_summary,
                next_action=f"Execute sprint {sprint_dir.name}.",
                cleanup_note="No cleanup required before continuing.",
            )

            def progress_callback(current: dict[str, object]) -> None:
                sprint_snapshot.clear()
                sprint_snapshot.update(current)
                backlog_summary["current_sprint"] = sprint_dir.name
                backlog_summary["current_story"] = current.get("current_story")
                backlog_summary["current_node"] = current.get("current_node")
                backlog_summary["last_success_story"] = current.get("last_success_story") or backlog_summary.get("last_success_story")
                backlog_summary["resume_from_story"] = current.get("resume_from_story") or backlog_summary.get("resume_from_story")
                backlog_summary["interruption_reason"] = current.get("interruption_reason") or backlog_summary.get("interruption_reason")
                backlog_summary["error_message"] = current.get("error_message") or backlog_summary.get("error_message")
                backlog_summary["status"] = current.get("status") or backlog_summary.get("status")
                _persist_auto_delivery_runtime(
                    repo_b_path,
                    summary_path,
                    backlog_summary,
                    next_action="Continue with the current sprint cursor.",
                    cleanup_note="No cleanup required before continuing.",
                )

            sprint_result = _run_sprint_directory(
                sprint_dir,
                repo_b_path=repo_b_path,
                env=env,
                project=project,
                release=release,
                start_story_id=resume_story_id if sprint_dir.name == resume_sprint_id else None,
                continue_on_failure=True,
                echo=printer,
                successful_story_index=successful_story_index,
                progress_callback=progress_callback,
            )
            progress_callback(sprint_result)
            resume_story_id = None
        backlog_summary["status"] = "completed"
        backlog_summary["current_story"] = None
        backlog_summary["current_node"] = None
        backlog_summary["resume_from_story"] = None
        backlog_summary["interruption_reason"] = None
        backlog_summary["error_message"] = None
    except click.ClickException:
        backlog_summary["status"] = "interrupted"
        _persist_auto_delivery_runtime(
            repo_b_path,
            summary_path,
            backlog_summary,
            next_action="Inspect the last failed story and resume from the checkpoint.",
            cleanup_note="A failed worktree may need inspection before retry.",
        )
        raise
    except Exception as exc:
        backlog_summary["status"] = "interrupted"
        backlog_summary["interruption_reason"] = str(backlog_summary.get("interruption_reason") or "auto_delivery_exception")
        backlog_summary["error_message"] = backlog_summary.get("error_message") or str(exc)
        _persist_auto_delivery_runtime(
            repo_b_path,
            summary_path,
            backlog_summary,
            next_action="Inspect the last failed story and resume from the checkpoint.",
            cleanup_note="A failed worktree may need inspection before retry.",
        )
        raise click.ClickException(str(exc)) from exc

    _persist_auto_delivery_runtime(
        repo_b_path,
        summary_path,
        backlog_summary,
        next_action="Automatic delivery completed or reached the end of the current backlog.",
        cleanup_note="No cleanup required.",
    )
    printer(f"Auto delivery summary: {summary_path}")
    printer(f"Completed stories: {backlog_summary['completed_story_count']}")
    printer(f"Failed stories: {backlog_summary['failed_story_count']}")
    return summary_path


def _run_sprint_directory(
    sprint_dir: Path,
    *,
    repo_b_path: Path,
    env: str,
    project: str,
    release: bool,
    start_from: int = 0,
    start_story_id: str | None = None,
    continue_on_failure: bool = False,
    echo: callable | None = None,
    successful_story_index: dict[str, dict[str, object]] | None = None,
    progress_callback: Callable[[dict[str, object]], Any] | None = None,
    backlog_id_override: str | None = None,
    backlog_root_override: str | None = None,
    resume_command_override: str | None = None,
) -> dict[str, object]:
    printer = echo or click.echo
    target_dir = sprint_dir.resolve()
    execution_file = target_dir / "execution_order.txt"
    if not target_dir.exists() or not execution_file.exists():
        raise click.ClickException(f"Sprint directory or execution_order.txt is missing: {target_dir}")

    story_ids = _read_execution_story_ids(execution_file)
    if start_story_id and start_story_id in story_ids:
        start_from = story_ids.index(start_story_id)
    if start_from < 0 or start_from >= len(story_ids):
        raise click.ClickException(f"start-from is out of range: {start_from}")
    effective_backlog_id, effective_backlog_root = _derive_backlog_context_from_sprint_dir(
        target_dir,
        repo_b_path,
        backlog_id_override=backlog_id_override,
        backlog_root_override=backlog_root_override,
    )
    effective_resume_command = resume_command_override or (
        f"python cli.py auto-deliver --project {project} --env {env} --prefix {effective_backlog_id or 'backlog_v1'} --auto-run"
    )

    baseline = _capture_sprint_registry_baseline(repo_b_path, target_dir)
    authoritative_attempt = _build_authoritative_attempt(target_dir)
    pre_hook = run_sprint_pre_hooks(target_dir, project=project, release=release)
    try:
        _sync_and_assert_continuity(
            trigger="sprint_boundary",
            project=project,
            repo_b_path=repo_b_path,
            sprint_artifact_refs=[
                str(item)
                for item in (
                    pre_hook.get("office_hours_path"),
                    pre_hook.get("plan_ceo_review_path"),
                    pre_hook.get("sprint_framing_path"),
                    pre_hook.get("parity_manifest_path"),
                    pre_hook.get("acceptance_checklist_path"),
                )
                if str(item or "").strip()
            ],
        )
    except ContinuityGuardError as exc:
        raise click.ClickException(str(exc)) from exc
    if _is_finahunt_sprint5_authoritative_rerun(project, target_dir):
        _mark_existing_sprint_attempts_stale(
            repo_b_path=repo_b_path,
            target_dir=target_dir,
            authoritative_attempt=authoritative_attempt,
            baseline=baseline,
        )
    printer(f"Sprint advisory saved: {pre_hook['advice_path']}")
    if pre_hook.get("sprint_framing_path"):
        printer(f"Sprint framing saved: {pre_hook['sprint_framing_path']}")

    completed: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    successful_story_index = successful_story_index or {}

    def publish_progress(
        *,
        status: str = "running",
        current_story: str | None = None,
        current_node: str | None = None,
        resume_from_story: str | None = None,
        interruption_reason: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "sprint_dir": str(target_dir),
                "story_count": len(story_ids[start_from:]),
                "completed_stories": list(completed),
                "failed_stories": list(failed),
                "pre_hook": pre_hook,
                "post_hook": None,
                "authoritative_attempt": authoritative_attempt,
                "status": status,
                "current_story": current_story,
                "current_node": current_node,
                "last_success_story": completed[-1].get("story_id") if completed else None,
                "resume_from_story": resume_from_story if resume_from_story is not None else (failed[-1].get("story_id") if failed else None),
                "interruption_reason": interruption_reason if interruption_reason is not None else (failed[-1].get("error") if failed else None),
                "error_message": error_message if error_message is not None else (failed[-1].get("error") if failed else None),
            }
        )

    def persist_interruption(
        story_id: str,
        reason: str,
        message: str,
        evidence_paths: list[str],
        current_node: str | None = None,
        blocker_class: str | None = None,
    ) -> None:
        write_resume_state(
            repo_b_path,
            {
                "project": project,
                "backlog_root": effective_backlog_root,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "current_node": current_node,
                "status": "interrupted",
                "resume_from_story": story_id,
                "interruption_reason": reason,
                "error_message": message,
                "blocker_class": blocker_class,
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "pause_policy": "story_boundary_or_shared_blocker_only",
                "run_policy": "single_pass_to_completion",
                "acceptance_policy": "must_pass_all_required_runs",
                "retry_policy": "auto_repair_until_green",
                "acceptance_attempt": 0,
                "acceptance_failure_class": "shared_dependency_blocker" if blocker_class == "shared_dependency_blocker" else "story_local_blocker",
                "repair_iteration": 0,
                "final_green_required": True,
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
            },
        )
        write_current_handoff(
            repo_b_path,
            {
                "project": project,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "current_node": current_node,
                "status": "interrupted",
                "resume_from_story": story_id,
                "interruption_reason": reason,
                "root_cause": message,
                "next_action": f"Fix the blocker for {story_id}, then resume automatic delivery from this story.",
                "resume_command": effective_resume_command,
                "evidence_paths": evidence_paths,
                "cleanup_note": "Inspect the failed story and rerun from the latest checkpoint.",
                "blocker_class": blocker_class,
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "pause_policy": "story_boundary_or_shared_blocker_only",
                "run_policy": "single_pass_to_completion",
                "acceptance_policy": "must_pass_all_required_runs",
                "retry_policy": "auto_repair_until_green",
                "acceptance_attempt": 0,
                "acceptance_failure_class": "shared_dependency_blocker" if blocker_class == "shared_dependency_blocker" else "story_local_blocker",
                "repair_iteration": 0,
                "final_green_required": True,
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
            },
        )

    for index, story_id in enumerate(story_ids[start_from:], start=start_from + 1):
        successful_snapshot = successful_story_index.get(story_id)
        if successful_snapshot:
            completed.append(dict(successful_snapshot))
            printer(f"[{index}/{len(story_ids)}] Skipping {story_id} (reconciled success audit)")
            write_resume_state(
                repo_b_path,
                {
                    "project": project,
                    "backlog_root": effective_backlog_root,
                    "backlog_id": effective_backlog_id,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "status": "running",
                    "last_success_story": story_id,
                    "resume_from_story": story_ids[index] if index < len(story_ids) else story_id,
                },
                clear_keys=["interruption_reason", "error_message", "failure_type", "failure_snapshot_path"],
            )
            publish_progress()
            continue

        story_file = next(target_dir.rglob(f"{story_id}_*.yaml"), None)
        if story_file is None:
            message = f"Story card not found for {story_id}"
            failed.append({"story_id": story_id, "error": message})
            printer(f"[{index}/{len(story_ids)}] {story_id} failed: {message}")
            persist_interruption(story_id, "story_card_missing", message, [], blocker_class="shared_dependency_blocker")
            publish_progress(
                status="interrupted",
                current_story=story_id,
                resume_from_story=story_id,
                interruption_reason="story_card_missing",
                error_message=message,
            )
            if continue_on_failure:
                continue
            raise click.ClickException(message)

        admission = _admit_story_file(
            story_file,
            repo_b_path,
            project,
            {
                "office_hours_path": pre_hook.get("office_hours_path"),
                "plan_ceo_review_path": pre_hook.get("plan_ceo_review_path"),
                "sprint_framing_path": pre_hook.get("sprint_framing_path"),
                "gstack_parity_manifest_path": pre_hook.get("parity_manifest_path"),
                "gstack_acceptance_checklist_path": pre_hook.get("acceptance_checklist_path"),
                "backlog_id": effective_backlog_id,
                "backlog_root": effective_backlog_root,
                "sprint_id": target_dir.name,
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
                "formal_entry": True,
            },
        )
        if not admission.get("admitted"):
            message = "; ".join(str(item) for item in (admission.get("errors") or []) if str(item).strip()) or "workflow admission failed"
            blocker_class = "shared_dependency_blocker"
            failed.append({"story_id": story_id, "error": message, "blocker_class": blocker_class})
            printer(f"[{index}/{len(story_ids)}] {story_id} rejected at admission: {message}")
            write_story_failure(
                repo_b_path,
                story_id,
                {
                    "project": project,
                    "backlog_id": target_dir.parent.name,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "task_name": story_id,
                    "failure_type": "workflow_admission_failed",
                    "blocker_class": blocker_class,
                    "recommended_recovery_action": "Add the missing story metadata or required workflow scope, then rerun this story.",
                    "error_message": message,
                    "admission_path": admission.get("admission_path"),
                },
            )
            persist_interruption(
                story_id,
                "workflow_admission_failed",
                message,
                [str(story_file), str(admission.get("admission_path") or "")],
                blocker_class=blocker_class,
            )
            publish_progress(
                status="interrupted",
                current_story=story_id,
                resume_from_story=story_id,
                interruption_reason="workflow_admission_failed",
                error_message=message,
            )
            if continue_on_failure:
                continue
            raise click.ClickException(message)

        printer(f"[{index}/{len(story_ids)}] Running {story_id}")
        try:
            continuity_overrides = _story_boundary_overrides(
                project=project,
                repo_b_path=repo_b_path,
                story_file=story_file,
                pre_hook=pre_hook,
                backlog_id=effective_backlog_id,
                backlog_root=effective_backlog_root,
                sprint_id=target_dir.name,
            )
        except ContinuityGuardError as exc:
            message = str(exc)
            failed.append({"story_id": story_id, "error": message, "blocker_class": "shared_dependency_blocker"})
            persist_interruption(
                story_id,
                "continuity_guard_blocked",
                message,
                [str(story_file)],
                blocker_class="shared_dependency_blocker",
            )
            raise click.ClickException(message) from exc
        update_story_status(
            repo_b_path,
            {
                "project": project,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "status": "running",
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "source": "agentsystem_runtime",
                "required_modes": list(admission.get("required_modes") or []),
                "advisory_modes": list(admission.get("advisory_modes") or []),
                "repository": project,
            },
        )
        write_resume_state(
            repo_b_path,
            {
                "project": project,
                "backlog_root": effective_backlog_root,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "status": "running",
                "resume_from_story": story_id,
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "pause_policy": "story_boundary_or_shared_blocker_only",
                "run_policy": "single_pass_to_completion",
                "acceptance_policy": "must_pass_all_required_runs",
                "retry_policy": "auto_repair_until_green",
                "acceptance_attempt": 0,
                "acceptance_failure_class": None,
                "repair_iteration": 0,
                "final_green_required": True,
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
            },
        )
        write_current_handoff(
            repo_b_path,
            {
                "project": project,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "status": "running",
                "resume_from_story": story_id,
                "root_cause": "Story execution in progress.",
                "next_action": f"Execute story {story_id}.",
                "resume_command": effective_resume_command,
                "evidence_paths": [str(story_file)],
                "cleanup_note": "No cleanup required before continuing.",
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "pause_policy": "story_boundary_or_shared_blocker_only",
                "run_policy": "single_pass_to_completion",
                "acceptance_policy": "must_pass_all_required_runs",
                "retry_policy": "auto_repair_until_green",
                "acceptance_attempt": 0,
                "acceptance_failure_class": None,
                "repair_iteration": 0,
                "final_green_required": True,
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
            },
        )
        try:
            output = run_prod_task(
                story_file,
                env,
                project=project,
                task_overrides={
                    "auto_run": True,
                    "execution_policy": "continuous_full_sprint",
                    "interaction_policy": "non_interactive_auto_run",
                    "pause_policy": "story_boundary_or_shared_blocker_only",
                    "run_policy": "single_pass_to_completion",
                    "acceptance_policy": "must_pass_all_required_runs",
                    "retry_policy": "auto_repair_until_green",
                    "acceptance_attempt": 0,
                    "repair_iteration": 0,
                    "final_green_required": True,
                    "formal_entry": True,
                    "backlog_id": effective_backlog_id,
                    "backlog_root": effective_backlog_root,
                    "sprint_id": target_dir.name,
                    "office_hours_path": pre_hook.get("office_hours_path"),
                    "plan_ceo_review_path": pre_hook.get("plan_ceo_review_path"),
                    "sprint_framing_path": pre_hook.get("sprint_framing_path"),
                    "gstack_parity_manifest_path": pre_hook.get("parity_manifest_path"),
                    "gstack_acceptance_checklist_path": pre_hook.get("acceptance_checklist_path"),
                    **continuity_overrides,
                    "authoritative_attempt": authoritative_attempt,
                    "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
                },
            )
        except Exception as exc:
            blocker_class = "shared_dependency_blocker"
            failed.append({"story_id": story_id, "error": str(exc), "blocker_class": blocker_class})
            printer(f"  Failed: {exc}")
            write_story_failure(
                repo_b_path,
                story_id,
                {
                    "project": project,
                    "backlog_id": effective_backlog_id,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "task_name": story_id,
                    "failure_type": "run_prod_task_exception",
                    "blocker_class": blocker_class,
                    "recommended_recovery_action": "Inspect the shared execution blocker, then resume from this story.",
                    "error_message": str(exc),
                },
            )
            persist_interruption(story_id, "run_prod_task_exception", str(exc), [str(story_file)], blocker_class=blocker_class)
            publish_progress(
                status="interrupted",
                current_story=story_id,
                resume_from_story=story_id,
                interruption_reason="run_prod_task_exception",
                error_message=str(exc),
            )
            if not continue_on_failure or blocker_class == "shared_dependency_blocker":
                raise click.ClickException(f"Task execution failed for {story_id}: {exc}") from exc
            continue

        if output.get("success"):
            completed.append({"story_id": story_id, "task_id": output.get("task_id"), "commit": output.get("commit")})
            printer(f"  Branch: {output['branch']}")
            printer(f"  Commit: {output['commit']}")
            write_resume_state(
                repo_b_path,
                {
                    "project": project,
                    "backlog_root": effective_backlog_root,
                    "backlog_id": effective_backlog_id,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "status": "running",
                    "last_success_story": story_id,
                    "resume_from_story": story_ids[index] if index < len(story_ids) else story_id,
                    "current_node": "doc_writer",
                    "error_message": None,
                    "interruption_reason": None,
                    "run_policy": "single_pass_to_completion",
                    "acceptance_policy": "must_pass_all_required_runs",
                    "retry_policy": "auto_repair_until_green",
                    "acceptance_attempt": 0,
                    "acceptance_failure_class": None,
                    "repair_iteration": 0,
                    "final_green_required": True,
                    "authoritative_attempt": authoritative_attempt,
                    "sprint_rerun_policy": "isolation_snapshot_full_rerun" if _is_finahunt_sprint5_authoritative_rerun(project, target_dir) else None,
                },
                clear_keys=["interruption_reason", "error_message", "failure_type", "failure_snapshot_path"],
            )
            publish_progress()
            continue

        failure_message = str(output.get("error") or "workflow_failed")
        failure_reason = str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("interruption_reason") or failure_message)
        blocker_class = _classify_story_blocker(output)
        failed.append({"story_id": story_id, "error": failure_message, "task_id": output.get("task_id"), "blocker_class": blocker_class})
        printer(f"  Failed: {failure_message}")
        write_story_failure(
            repo_b_path,
            story_id,
            {
                "project": project,
                "backlog_id": effective_backlog_id,
                "sprint_id": target_dir.name,
                "story_id": story_id,
                "task_id": output.get("task_id"),
                "task_name": story_id,
                "failure_type": str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("failure_type") or failure_reason),
                "blocker_class": blocker_class,
                "last_node": str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("last_node") or "") or None,
                "recommended_recovery_action": "Resume from the failed story after the recorded blocker is addressed.",
                "error_message": failure_message,
                "audit_path": str(output.get("audit_path") or "") or None,
            },
        )
        persist_interruption(
            story_id,
            failure_reason,
            failure_message,
            [item for item in (str(story_file), str(output.get("audit_path") or "")) if item],
            current_node=str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("last_node") or "") or None,
            blocker_class=blocker_class,
        )
        publish_progress(
            status="interrupted",
            current_story=story_id,
            current_node=str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("last_node") or "") or None,
            resume_from_story=story_id,
            interruption_reason=failure_reason,
            error_message=failure_message,
        )
        can_continue, resolved_blocker_class = _should_continue_after_story_failure(
            target_dir=target_dir,
            story_ids=story_ids,
            failed_story_id=story_id,
            current_index=index - 1,
            blocker_class=blocker_class,
        )
        if resolved_blocker_class != blocker_class:
            blocker_class = resolved_blocker_class
            failed[-1]["blocker_class"] = blocker_class
            persist_interruption(
                story_id,
                failure_reason,
                failure_message,
                [item for item in (str(story_file), str(output.get("audit_path") or "")) if item],
                current_node=str(((output.get("state") or {}) if isinstance(output.get("state"), dict) else {}).get("last_node") or "") or None,
                blocker_class=blocker_class,
            )
        if continue_on_failure and can_continue:
            continue
        raise click.ClickException(f"Task execution failed for {story_id}: {failure_message}")

    post_hook = run_sprint_post_hooks(target_dir, project=project, release=release)
    try:
        _sync_and_assert_continuity(
            trigger="sprint_boundary",
            project=project,
            repo_b_path=repo_b_path,
            sprint_artifact_refs=[
                str(item)
                for item in (
                    post_hook.get("document_release_path"),
                    post_hook.get("retro_path"),
                    post_hook.get("ship_advice_path"),
                    post_hook.get("sprint_close_bundle_path"),
                )
                if str(item or "").strip()
            ],
        )
    except ContinuityGuardError as exc:
        raise click.ClickException(str(exc)) from exc
    report_path = _write_sprint_special_acceptance_report(
        target_dir=target_dir,
        repo_b_path=repo_b_path,
        project=project,
        pre_hook=pre_hook,
        post_hook=post_hook,
        completed=completed,
        failed=failed,
        baseline=baseline,
        authoritative_attempt=authoritative_attempt,
    )
    printer(f"Sprint document-release report: {post_hook['document_release_path']}")
    printer(f"Sprint retro report: {post_hook['retro_path']}")
    if post_hook.get("ship_report_path"):
        printer(f"Sprint ship report: {post_hook['ship_report_path']}")
    if post_hook.get("ship_advice_path"):
        printer(f"Sprint ship advice: {post_hook['ship_advice_path']}")
    printer(f"Sprint special acceptance report: {report_path}")

    return {
        "sprint_dir": str(target_dir),
        "story_count": len(story_ids[start_from:]),
        "completed_stories": completed,
        "failed_stories": failed,
        "pre_hook": pre_hook,
        "post_hook": post_hook,
        "authoritative_attempt": authoritative_attempt,
        "special_acceptance_report_path": str(report_path),
        "backlog_id": effective_backlog_id,
        "backlog_root": effective_backlog_root,
        "status": "completed",
        "current_story": None,
        "current_node": "doc_writer" if not failed else None,
        "last_success_story": completed[-1].get("story_id") if completed else None,
        "resume_from_story": failed[-1].get("story_id") if failed else None,
        "interruption_reason": failed[-1].get("error") if failed else None,
        "error_message": failed[-1].get("error") if failed else None,
    }


def _classify_story_blocker(output: dict[str, object]) -> str:
    state = output.get("state") if isinstance(output.get("state"), dict) else {}
    explicit = str((state or {}).get("blocker_class") or "").strip()
    if explicit in {"story_local_blocker", "shared_dependency_blocker"}:
        return explicit
    failure_type = str((state or {}).get("failure_type") or "").strip()
    if failure_type in {"workflow_bug", "run_prod_task_exception", "story_card_missing"}:
        return "shared_dependency_blocker"
    return "story_local_blocker"


def _parse_story_dependencies(story_file: Path | None) -> set[str]:
    if story_file is None or not story_file.exists():
        return set()
    try:
        payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(payload, dict):
        return set()
    raw_dependencies = payload.get("dependencies")
    if isinstance(raw_dependencies, list):
        items = raw_dependencies
    elif raw_dependencies in (None, ""):
        items = []
    else:
        items = [raw_dependencies]

    resolved: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            candidate = item.get("story_id") or item.get("task_id") or item.get("id")
        else:
            candidate = item
        normalized = str(candidate or "").strip()
        if normalized:
            resolved.add(normalized)
    return resolved


def _resolve_story_file(target_dir: Path, story_id: str) -> Path | None:
    return next(target_dir.rglob(f"{story_id}_*.yaml"), None)


def _should_continue_after_story_failure(
    *,
    target_dir: Path,
    story_ids: list[str],
    failed_story_id: str,
    current_index: int,
    blocker_class: str,
) -> tuple[bool, str]:
    if blocker_class == "shared_dependency_blocker":
        return False, blocker_class
    for downstream_story_id in story_ids[current_index + 1 :]:
        dependencies = _parse_story_dependencies(_resolve_story_file(target_dir, downstream_story_id))
        if failed_story_id in dependencies:
            return False, "shared_dependency_blocker"
    return True, blocker_class


def _capture_sprint_registry_baseline(repo_b_path: Path, target_dir: Path) -> dict[str, dict[str, object]]:
    status_entries = _read_registry_entries(repo_b_path / "tasks" / "story_status_registry.json", "stories")
    review_entries = _read_registry_entries(repo_b_path / "tasks" / "story_acceptance_reviews.json", "reviews")
    status_index = {
        str(item.get("story_id") or ""): item
        for item in status_entries
        if isinstance(item, dict) and str(item.get("sprint_id") or "") == target_dir.name
    }
    review_index = {
        str(item.get("story_id") or ""): item
        for item in review_entries
        if isinstance(item, dict) and str(item.get("sprint_id") or "") == target_dir.name
    }
    baseline: dict[str, dict[str, object]] = {}
    for story_id in [line.strip() for line in (target_dir / "execution_order.txt").read_text(encoding="utf-8").splitlines() if line.strip()]:
        status_entry = status_index.get(story_id) or {}
        review_entry = review_index.get(story_id) or {}
        baseline[story_id] = {
            "status_exists": story_id in status_index,
            "acceptance_exists": story_id in review_index,
            "status_value": str(status_entry.get("status") or ""),
            "acceptance_status": str(review_entry.get("acceptance_status") or review_entry.get("verdict") or ""),
            "formal_flow_complete": bool(status_entry.get("formal_flow_complete")) and bool(review_entry.get("formal_flow_complete")),
            "attempt_status": str(status_entry.get("attempt_status") or review_entry.get("attempt_status") or ""),
            "authoritative_attempt": str(status_entry.get("authoritative_attempt") or review_entry.get("authoritative_attempt") or ""),
            "handoff_exists": (repo_b_path / "tasks" / "runtime" / "story_handoffs" / f"{story_id}.md").exists(),
            "failure_exists": (repo_b_path / "tasks" / "runtime" / "story_failures" / f"{story_id}.json").exists(),
        }
    return baseline


def _mark_existing_sprint_attempts_stale(
    *,
    repo_b_path: Path,
    target_dir: Path,
    authoritative_attempt: str,
    baseline: dict[str, dict[str, object]],
) -> None:
    story_ids = [line.strip() for line in (target_dir / "execution_order.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    for story_id in story_ids:
        story_baseline = baseline.get(story_id) or {}
        if story_baseline.get("status_exists"):
            update_story_status(
                repo_b_path,
                {
                    "backlog_id": target_dir.parent.name,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "status": "stale_attempt",
                    "attempt_status": "stale_attempt",
                    "superseded_by_attempt": authoritative_attempt,
                    "superseded_at": datetime.now().isoformat(timespec="seconds"),
                    "superseded_reason": "authoritative_sprint_rerun",
                    "formal_flow_complete": False,
                    "formal_flow_gap_reasons": ["superseded_by_authoritative_rerun"],
                    "accepted": False,
                    "agentized": False,
                    "formal_acceptance_reviewer": None,
                },
            )
        if story_baseline.get("acceptance_exists"):
            update_story_acceptance_review(
                repo_b_path,
                {
                    "backlog_id": target_dir.parent.name,
                    "sprint_id": target_dir.name,
                    "story_id": story_id,
                    "reviewer": "acceptance_gate",
                    "verdict": "needs_followup",
                    "acceptance_status": "needs_followup",
                    "attempt_status": "stale_attempt",
                    "superseded_by_attempt": authoritative_attempt,
                    "superseded_at": datetime.now().isoformat(timespec="seconds"),
                    "superseded_reason": "authoritative_sprint_rerun",
                    "formal_flow_complete": False,
                    "formal_flow_gap_reasons": ["superseded_by_authoritative_rerun"],
                    "accepted": False,
                    "agentized": False,
                },
            )


def _load_agent_coverage_index(repo_b_path: Path) -> dict[tuple[str, str, str], dict[str, object]]:
    report_path = repo_b_path / "tasks" / "runtime" / "agent_coverage_report.json"
    if not report_path.exists():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    stories = payload.get("stories") if isinstance(payload, dict) else []
    if not isinstance(stories, list):
        return {}
    index: dict[tuple[str, str, str], dict[str, object]] = {}
    for item in stories:
        if not isinstance(item, dict):
            continue
        index[_story_registry_key(item)] = item
    return index


def _story_registry_key(entry: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(entry.get("backlog_id") or ""),
        str(entry.get("sprint_id") or ""),
        str(entry.get("story_id") or ""),
    )


def _collect_finahunt_sprint5_runtime_evidence(post_hook: dict[str, object]) -> dict[str, object]:
    runtime_validation_path = Path(str(post_hook.get("runtime_validation_path") or "")).resolve() if post_hook.get("runtime_validation_path") else None
    if not runtime_validation_path or not runtime_validation_path.exists():
        return {"validation_status": "missing"}
    try:
        payload = json.loads(runtime_validation_path.read_text(encoding="utf-8"))
    except Exception:
        return {"validation_status": "failed", "parse_error": "runtime validation payload is unreadable"}
    return payload if isinstance(payload, dict) else {"validation_status": "failed"}


def _write_sprint_special_acceptance_report(
    *,
    target_dir: Path,
    repo_b_path: Path,
    project: str,
    pre_hook: dict[str, object],
    post_hook: dict[str, object],
    completed: list[dict[str, object]],
    failed: list[dict[str, object]],
    baseline: dict[str, dict[str, object]],
    authoritative_attempt: str,
) -> Path:
    output_dir = ROOT_DIR / "runs" / "sprints" / project / target_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    status_entries = _read_registry_entries(repo_b_path / "tasks" / "story_status_registry.json", "stories")
    review_entries = _read_registry_entries(repo_b_path / "tasks" / "story_acceptance_reviews.json", "reviews")
    status_index = {
        _story_registry_key(item): item
        for item in status_entries
        if isinstance(item, dict)
    }
    review_index = {
        _story_registry_key(item): item
        for item in review_entries
        if isinstance(item, dict)
    }
    coverage_index = _load_agent_coverage_index(repo_b_path)
    story_ids = [line.strip() for line in (target_dir / "execution_order.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    story_reports: list[dict[str, object]] = []
    overall_missing: list[str] = []

    for story_id in story_ids:
        story_file = _resolve_story_file(target_dir, story_id)
        admission = _admit_story_file(
            story_file,
            repo_b_path,
            project,
            {
                "office_hours_path": pre_hook.get("office_hours_path"),
                "plan_ceo_review_path": pre_hook.get("plan_ceo_review_path"),
                "sprint_framing_path": pre_hook.get("sprint_framing_path"),
                "authoritative_attempt": authoritative_attempt,
                "sprint_rerun_policy": "isolation_snapshot_full_rerun",
                "formal_entry": True,
            },
        ) if story_file else None
        key = (target_dir.parent.name, target_dir.name, story_id)
        status_entry = status_index.get(key) or {}
        review_entry = review_index.get(key) or {}
        coverage_entry = coverage_index.get(key) or {}
        mode_coverage = coverage_entry.get("agent_mode_coverage") if isinstance(coverage_entry.get("agent_mode_coverage"), dict) else {}
        required_modes = list((coverage_entry.get("required_modes") or (admission or {}).get("required_modes") or []))
        executed_modes = list((coverage_entry.get("executed_modes") or []))
        missing_required = list((mode_coverage or {}).get("missing_required") or [])
        handoff_path = repo_b_path / "tasks" / "runtime" / "story_handoffs" / f"{story_id}.md"
        failure_path = repo_b_path / "tasks" / "runtime" / "story_failures" / f"{story_id}.json"
        status_ok = str(status_entry.get("status") or "") == "done"
        acceptance_ok = str(review_entry.get("acceptance_status") or review_entry.get("verdict") or "") == "approved"
        evidence_ok = bool(status_entry.get("audit_path")) and (handoff_path.exists() or failure_path.exists())
        report = {
            "story_id": story_id,
            "completed_before_rerun": bool((baseline.get(story_id) or {}).get("status_exists") and (baseline.get(story_id) or {}).get("acceptance_exists")),
            "supplemented_in_rerun": not bool((baseline.get(story_id) or {}).get("status_exists") and (baseline.get(story_id) or {}).get("acceptance_exists")),
            "superseded_old_attempt": bool((baseline.get(story_id) or {}).get("status_exists") or (baseline.get(story_id) or {}).get("acceptance_exists")),
            "old_attempt_status": str((baseline.get(story_id) or {}).get("status_value") or ""),
            "old_attempt_acceptance_status": str((baseline.get(story_id) or {}).get("acceptance_status") or ""),
            "status_recorded": status_ok,
            "acceptance_recorded": acceptance_ok,
            "handoff_exists": handoff_path.exists(),
            "failure_exists": failure_path.exists(),
            "audit_path": str(status_entry.get("audit_path") or ""),
            "authoritative_attempt": authoritative_attempt,
            "attempt_status": str(status_entry.get("attempt_status") or review_entry.get("attempt_status") or ""),
            "required_modes": required_modes,
            "executed_modes": executed_modes,
            "missing_required_modes": missing_required,
            "mode_coverage_summary": {
                "required_count": len(required_modes),
                "executed_required_count": len(required_modes) - len(missing_required),
                "missing_required_modes": missing_required,
            },
            "mode_coverage_complete": not missing_required,
            "admission_path": str((admission or {}).get("admission_path") or ""),
            "evidence_complete": evidence_ok,
            "formal_flow_complete": status_ok and acceptance_ok and evidence_ok and not missing_required,
        }
        if not report["formal_flow_complete"]:
            overall_missing.append(story_id)
        story_reports.append(report)

    sprint_level = {
        "office_hours_path": str(pre_hook.get("office_hours_path") or ""),
        "plan_ceo_review_path": str(pre_hook.get("plan_ceo_review_path") or ""),
        "sprint_framing_path": str(pre_hook.get("sprint_framing_path") or ""),
        "ship_report_path": str(post_hook.get("ship_report_path") or ""),
        "document_release_path": str(post_hook.get("document_release_path") or ""),
        "retro_path": str(post_hook.get("retro_path") or ""),
        "sprint_close_bundle_path": str(post_hook.get("sprint_close_bundle_path") or ""),
    }
    sprint_level["complete"] = all(Path(path).exists() for path in sprint_level.values() if path)
    runtime_evidence: dict[str, object] | None = None
    if project == "finahunt" and "low_position_one_shot_workbench" in target_dir.name:
        runtime_evidence = _collect_finahunt_sprint5_runtime_evidence(post_hook)
        if runtime_evidence.get("validation_status") != "passed":
            overall_missing.append("runtime_validation")

    verdict = not failed and not overall_missing and sprint_level["complete"]
    report_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": project,
        "sprint_id": target_dir.name,
        "authoritative_attempt": authoritative_attempt,
        "story_count": len(story_ids),
        "completed_story_count": len(completed),
        "failed_story_count": len(failed),
        "formal_flow_complete": verdict,
        "final_verdict": "完整按标准流程跑过" if verdict else "未完整跑过，缺失点如下",
        "missing_items": overall_missing,
        "story_reports": story_reports,
        "sprint_level": sprint_level,
        "runtime_evidence": runtime_evidence,
    }
    report_path = output_dir / "special_acceptance_report.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _write_auto_delivery_summary(payload: dict[str, object], summary_path: Path | None = None) -> Path:
    output_dir = ROOT_DIR / "runs" / "auto_delivery"
    output_dir.mkdir(parents=True, exist_ok=True)
    if summary_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = output_dir / f"auto_delivery_{timestamp}.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


@click.group()
def cli() -> None:
    """AgentSystem command line tool."""


@cli.command("run-task")
@click.option("--task-file", required=True, help="Task card file path")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", help="Target project/repository id, for example versefina or finahunt")
@click.option("--resume", is_flag=True, help="Resume from checkpoint (reserved)")
def run_task(task_file: str, env: str, project: str | None, resume: bool) -> None:
    task_path = Path(task_file)
    if not task_path.exists():
        click.echo(f"Task card file does not exist: {task_file}", err=True)
        raise SystemExit(1)

    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        normalize_runtime_task_payload(payload)
    except Exception as exc:
        click.echo(f"Task card validation failed: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"Running task: {task_file}")
    click.echo(f"Environment: {env}")
    if resume:
        click.echo("resume is reserved; the current local workflow always starts from the task card.")

    try:
        output = run_prod_task(
            task_path,
            env,
            project=project,
            task_overrides={
                "auto_run": False,
                "formal_entry": False,
                "interaction_policy": "direct_run_task",
            },
        )
    except Exception as exc:
        click.echo(f"Task execution failed: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("Task completed")
    click.echo(f"  Branch: {output['branch']}")
    if 'commit' in output:
        click.echo(f"  Commit: {output['commit']}")
    click.echo(f"  Audit log: {output['audit_path']}")


@cli.command("analyze")
@click.option("--requirement", "-r", required=True, help="Large natural-language requirement")
@click.option("--sprint", "-s", default="1", show_default=True, help="Fallback sprint number for generic requirements")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
def analyze(requirement: str, sprint: str, env: str, project: str, prefix: str) -> None:
    """Analyze a large requirement and generate backlog artifacts."""
    result, _repo_b_path, tasks_root = _build_backlog_from_requirement(
        env=env,
        project=project,
        prefix=prefix,
        sprint=sprint,
        requirement=requirement,
        requirement_file=None,
    )
    click.echo("Requirement analysis completed")
    click.echo(f"  Project: {project}")
    click.echo(f"  Tasks root: {tasks_root}")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Overview: {result['overview_path']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")


@cli.command("split_requirement")
@click.option(
    "--requirement-file",
    "-f",
    default=r"D:\lyh\agent\agent-frame\versefina\docs\需求文档\需求分析.md",
    show_default=True,
    help="Requirement markdown file path",
)
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
def split_requirement(requirement_file: str, env: str, project: str, prefix: str) -> None:
    """Split a requirement markdown file into formal backlog_v1 sprint artifacts."""
    result, _repo_b_path, tasks_root = _build_backlog_from_requirement(
        env=env,
        project=project,
        prefix=prefix,
        sprint="1",
        requirement=None,
        requirement_file=requirement_file,
    )
    click.echo("Requirement split completed")
    click.echo(f"  Project: {project}")
    click.echo(f"  Tasks root: {tasks_root}")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Overview: {result['overview_path']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")


@cli.command("run-sprint")
@click.option("--sprint-dir", help="Sprint directory path, for example tasks/backlog_v1/sprint_0_contract_foundation")
@click.option("--sprint", help="Legacy sprint number, for example 1")
@click.option("--start-from", default=0, show_default=True, help="Story index to start from")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--release", is_flag=True, help="Mark this sprint run as a release candidate and emit ship advice")
def run_sprint(sprint_dir: str | None, sprint: str | None, start_from: int, env: str, project: str, release: bool) -> None:
    """Run all story cards in a generated sprint directory."""
    if not sprint_dir and not sprint:
        click.echo("Either --sprint-dir or --sprint is required.", err=True)
        raise SystemExit(1)

    repo_b_path = _resolve_project_repo_path(_load_env_config(env), project)

    if sprint_dir:
        target_dir = Path(sprint_dir).resolve()
    else:
        target_dir = ROOT_DIR / "tasks" / f"sprint_{sprint}"
    _run_sprint_directory(
        target_dir,
        repo_b_path=repo_b_path,
        env=env,
        project=project,
        release=release,
        start_from=start_from,
        continue_on_failure=False,
        echo=click.echo,
    )
    click.echo(f"Sprint completed: {target_dir}")


@cli.command("auto-deliver")
@click.option("--requirement", "-r", help="Large natural-language requirement")
@click.option("--requirement-file", "-f", help="Requirement markdown file path")
@click.option("--sprint", "-s", default="1", show_default=True, help="Fallback sprint number for generic requirements")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
@click.option("--auto-run", is_flag=True, help="After backlog generation, immediately execute every sprint/story until completion")
@click.option("--release", is_flag=True, help="Mark sprint runs as release candidates and emit ship advice")
def auto_deliver(
    requirement: str | None,
    requirement_file: str | None,
    sprint: str,
    env: str,
    project: str,
    prefix: str,
    auto_run: bool,
    release: bool,
) -> None:
    """Generate backlog artifacts from a requirement and optionally execute the full delivery chain."""
    result, repo_b_path, tasks_root = _resolve_backlog_for_auto_delivery(
        env=env,
        project=project,
        prefix=prefix,
        sprint=sprint,
        requirement=requirement,
        requirement_file=requirement_file,
    )
    click.echo("Auto delivery backlog generation completed")
    click.echo(f"  Project: {project}")
    click.echo(f"  Repo: {repo_b_path}")
    click.echo(f"  Tasks root: {tasks_root}")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")

    if not auto_run:
        click.echo("Auto-run is off; backlog generation stopped here.")
        click.echo("Re-run with --auto-run to execute every sprint and story automatically.")
        return

    _execute_auto_delivery(
        backlog_result=result,
        repo_b_path=repo_b_path,
        tasks_root=tasks_root,
        env=env,
        project=project,
        release=release,
        echo=click.echo,
    )


@cli.command("run-roadmap")
@click.option("--tasks-root", required=True, help="Tasks root directory, for example D:\\lyh\\agent\\agent-frame\\versefina\\tasks")
@click.option("--roadmap-prefix", required=True, help="Roadmap prefix, for example roadmap_1_6")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--resume", is_flag=True, help="Resume from the recorded roadmap safe point")
@click.option("--release", is_flag=True, help="Mark roadmap sprint runs as release candidates and emit ship advice")
@click.option("--preflight-only", is_flag=True, help="Only validate roadmap structure and workflow admission without executing stories")
def run_roadmap(
    tasks_root: str,
    roadmap_prefix: str,
    env: str,
    project: str,
    resume: bool,
    release: bool,
    preflight_only: bool,
) -> None:
    """Run every sprint inside a roadmap prefix with roadmap-level persistence and verification."""
    repo_b_path = _resolve_project_repo_path(_load_env_config(env), project)
    tasks_root_path = Path(tasks_root).resolve()
    if not tasks_root_path.exists():
        raise click.ClickException(f"Tasks root does not exist: {tasks_root_path}")

    roadmap_result = _discover_roadmap_result(tasks_root_path, roadmap_prefix)
    preflight = _preflight_roadmap(
        repo_b_path=repo_b_path,
        project=project,
        tasks_root=tasks_root_path,
        roadmap_result=roadmap_result,
    )
    preflight_output = ROOT_DIR / "runs" / "roadmaps" / f"{roadmap_prefix}_preflight.json"
    preflight_output.parent.mkdir(parents=True, exist_ok=True)
    preflight_output.write_text(json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8")
    click.echo(f"Roadmap preflight report: {preflight_output}")
    if not preflight.get("passed"):
        raise click.ClickException("Roadmap preflight failed. Inspect the generated preflight report before execution.")
    if preflight_only:
        click.echo("Roadmap preflight passed.")
        return
    if resume:
        click.echo("Roadmap resume mode enabled; the latest safe point will be reused when available.")

    summary_path = _execute_roadmap(
        roadmap_result=roadmap_result,
        repo_b_path=repo_b_path,
        tasks_root=tasks_root_path,
        env=env,
        project=project,
        release=release,
        echo=click.echo,
    )
    click.echo(f"Roadmap completed: {summary_path}")


@cli.command("plan-ceo-review")
@click.option("--requirement", "-r", help="Natural-language requirement input")
@click.option("--requirement-file", "-f", help="Requirement markdown file path")
@click.option("--title", help="Optional requirement title override")
@click.option("--user-problem", help="Explicit user problem statement")
@click.option("--constraints", help="Optional constraints, separated by newlines or semicolons")
@click.option("--success-signal", help="Optional success signals, separated by newlines or semicolons")
@click.option("--audience", help="Optional target audience")
@click.option("--delivery-mode", type=click.Choice(["interactive", "auto"]), default="interactive", show_default=True)
@click.option("--sprint", "-s", default="1", show_default=True, help="Fallback sprint number for generic requirements")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--project", default="versefina", show_default=True, help="Target project/repository id")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
@click.option("--release", is_flag=True, help="Mark sprint runs as release candidates and emit ship advice")
def plan_ceo_review(
    requirement: str | None,
    requirement_file: str | None,
    title: str | None,
    user_problem: str | None,
    constraints: str | None,
    success_signal: str | None,
    audience: str | None,
    delivery_mode: str,
    sprint: str,
    env: str,
    project: str,
    prefix: str,
    release: bool,
) -> None:
    """Generate a product-level requirement document, then optionally continue into auto delivery."""
    config = _load_env_config(env)
    repo_b_path = _resolve_project_repo_path(config, project)
    inline_text, file_path = _resolve_requirement_input_for_project(repo_b_path, project, requirement, requirement_file)
    requirement_text = inline_text or Path(file_path).read_text(encoding="utf-8")

    package = generate_plan_ceo_review_package(
        repo_b_path,
        project=project,
        requirement_text=requirement_text,
        title=title,
        user_problem=user_problem,
        constraints=constraints,
        success_signal=success_signal,
        audience=audience,
        delivery_mode=delivery_mode,
        source_requirement_path=file_path,
    )

    click.echo("Plan CEO review completed")
    click.echo(f"  Project: {project}")
    click.echo(f"  Requirement doc: {package['requirement_doc_path']}")
    click.echo(f"  Review report: {package['review_report_path']}")
    click.echo(f"  Opportunity map: {package['opportunity_map_path']}")

    if delivery_mode != "auto":
        click.echo("Delivery mode is interactive; stopped after requirement document generation.")
        for action in package.get("next_recommended_actions") or []:
            click.echo(f"  Next: {action}")
        return

    result, resolved_repo_b_path, tasks_root = _build_backlog_from_requirement(
        env=env,
        project=project,
        prefix=prefix,
        sprint=sprint,
        requirement=None,
        requirement_file=str(package["requirement_doc_path"]),
    )
    click.echo("Plan CEO review handoff accepted; starting auto delivery.")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")
    _execute_auto_delivery(
        backlog_result=result,
        repo_b_path=resolved_repo_b_path,
        tasks_root=tasks_root,
        env=env,
        project=project,
        release=release,
        echo=click.echo,
    )


@cli.command("list-tasks")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def list_tasks(env: str) -> None:
    config = _load_env_config(env)
    repo_b_path = config["repo"]["versefina"]
    git = GitAdapter(repo_b_path)
    branches = [branch for branch in git.get_branches() if branch.startswith("agent/")]
    click.echo("Local agent branches:")
    if not branches:
        click.echo("  (none)")
        return
    for branch in branches:
        click.echo(f"  - {branch}")


@cli.command("validate-skill")
@click.option("--file", "skill_file", help="Validate a single skill file")
def validate_skill(skill_file: str | None) -> None:
    click.echo("Validating skill files...")
    if skill_file:
        if validate_skill_file(skill_file):
            click.echo("Skill file is valid.")
            return
        click.echo("Skill file validation failed.", err=True)
        raise SystemExit(1)

    results = validate_all_skills(ROOT_DIR / "skills")
    if results and all(results.values()):
        click.echo("All skill files are valid.")
        return
    if not results:
        click.echo("No .skill.md files found.")
        return
    click.echo("Some skill files failed validation.", err=True)
    raise SystemExit(1)


@cli.command("render-agent-skills")
@click.option("--mode-id", help="Render only one skill mode package")
@click.option("--validate/--no-validate", default=True, show_default=True, help="Validate rendered packages after writing")
def render_agent_skills(mode_id: str | None, validate: bool) -> None:
    click.echo("Rendering agent skill packages...")
    if mode_id:
        rendered = [render_agent_skill(mode_id, ROOT_DIR)]
    else:
        rendered = render_all_agent_skills(ROOT_DIR)
    if validate:
        for item in rendered:
            validate_rendered_agent_package(Path(item["skill_path"]).resolve().parent)
    for item in rendered:
        click.echo(f"  - {item['mode_id']}: {item['skill_path']}")
    click.echo("Agent skill packages rendered.")


@cli.command("audit-gstack-parity")
@click.option("--project", help="Optional project id for dogfood context, for example finahunt")
@click.option("--sprint-dir", help="Optional sprint directory to evaluate as the formal dogfood target")
@click.option("--output-dir", help="Optional output directory override")
def audit_gstack_parity(project: str | None, sprint_dir: str | None, output_dir: str | None) -> None:
    resolved_sprint_dir = sprint_dir
    if not resolved_sprint_dir and str(project or "").strip().lower() == "finahunt":
        default_sprint = ROOT_DIR.parent / "finahunt" / "tasks" / "backlog_v1" / "sprint_3_linkage_and_ranking"
        if default_sprint.exists():
            resolved_sprint_dir = str(default_sprint)

    target_dir = Path(output_dir).resolve() if output_dir else ROOT_DIR / "runs" / "parity"
    result = write_gstack_parity_audit(target_dir, sprint_dir=resolved_sprint_dir, project=project)
    click.echo("gstack parity audit completed")
    click.echo(f"  Manifest: {result['parity_manifest_path']}")
    click.echo(f"  Checklist: {result['acceptance_checklist_path']}")
    if resolved_sprint_dir:
        click.echo(f"  Dogfood target: {resolved_sprint_dir}")


@cli.command("fix-encoding")
@click.option("--root", default=str(ROOT_DIR), show_default=True, help="Root directory to normalize")
def fix_encoding(root: str) -> None:
    click.echo("Fixing text encoding...")
    fix_tree_encoding(root)
    click.echo("Encoding normalization completed.")


@cli.command("cleanup")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--task-id", help="Specific task id to clean")
@click.option("--branches", is_flag=True, help="Remove local agent task branches")
@click.option("--full", "full_cleanup", is_flag=True, help="Remove task worktrees, meta, and branches")
def cleanup(env: str, task_id: str | None, branches: bool, full_cleanup: bool) -> None:
    config = _load_env_config(env)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()
    workspace_manager = WorkspaceManager(repo_b_path, ROOT_DIR / "repo-worktree")
    git = GitAdapter(repo_b_path)
    cleaned: list[str] = []

    if task_id:
        workspace_manager.cleanup_task_resources(task_id)
        branch_name = f"agent/l1-{task_id}"
        if branch_name in git.get_branches():
            git.delete_branch(branch_name, force=True)
            cleaned.append(branch_name)

    if branches or full_cleanup:
        for branch_name in list(git.get_branches()):
            if not branch_name.startswith("agent/l1-task-"):
                continue
            task_key = branch_name.removeprefix("agent/l1-")
            workspace_manager.cleanup_task_resources(task_key)
            git.delete_branch(branch_name, force=True)
            cleaned.append(branch_name)

    if full_cleanup:
        workspace_manager.cleanup_orphaned_state()

    if cleaned:
        click.echo("Removed resources:")
        for item in cleaned:
            click.echo(f"  - {item}")
    else:
        click.echo("No matching resources to clean.")


@cli.command("dashboard")
@click.option("--host", default="127.0.0.1", show_default=True, help="Dashboard host")
@click.option("--port", default=8000, show_default=True, help="Dashboard port")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True, help="Open browser automatically")
def dashboard(host: str, port: int, open_browser: bool) -> None:
    url = f"http://{host}:{port}"
    if open_browser:
        webbrowser.open(url)
    click.echo(f"Dashboard started at {url}")
    uvicorn.run(dashboard_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
