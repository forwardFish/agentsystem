from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.core.state import build_mode_coverage


_FORMAL_FLOW_SUCCESS_STATUSES = {"done", "accepted"}
_FORMAL_FLOW_APPROVED_STATUSES = {"approved"}
_FORMAL_ACCEPTANCE_REVIEWER = "acceptance_gate"


def locate_story_context(task_path: Path, repo_b_path: Path) -> dict[str, str]:
    tasks_root = repo_b_path / "tasks"
    try:
        relative = task_path.resolve().relative_to(tasks_root.resolve())
    except Exception:
        return {
            "tasks_root": str(tasks_root),
            "backlog_id": "",
            "sprint_id": "",
            "story_file": str(task_path.resolve()),
        }

    parts = relative.parts
    backlog_id = parts[0] if len(parts) >= 1 else ""
    sprint_id = parts[1] if len(parts) >= 2 else ""
    return {
        "tasks_root": str(tasks_root),
        "backlog_id": backlog_id,
        "sprint_id": sprint_id,
        "story_file": str(task_path.resolve()),
    }


def ensure_runtime_layout(repo_b_path: Path) -> dict[str, Path]:
    workspace_root = repo_b_path.parent
    workspace_meta_root = workspace_root / ".meta"
    tasks_root = repo_b_path / "tasks"
    runtime_root = tasks_root / "runtime"
    docs_handoff_root = repo_b_path / "docs" / "handoff"
    story_failures_root = runtime_root / "story_failures"
    story_handoffs_root = runtime_root / "story_handoffs"

    for directory in (
        workspace_meta_root,
        docs_handoff_root,
        runtime_root,
        story_failures_root,
        story_handoffs_root,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return {
        "workspace_root": workspace_root,
        "workspace_meta_root": workspace_meta_root,
        "tasks_root": tasks_root,
        "runtime_root": runtime_root,
        "docs_handoff_root": docs_handoff_root,
        "story_failures_root": story_failures_root,
        "story_handoffs_root": story_handoffs_root,
    }


def read_resume_state(repo_b_path: Path) -> dict[str, Any]:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    return _read_json(runtime_paths["runtime_root"] / "auto_resume_state.json", {})


def write_resume_state(repo_b_path: Path, updates: dict[str, Any], *, clear_keys: list[str] | None = None) -> Path:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    path = runtime_paths["runtime_root"] / "auto_resume_state.json"
    payload = _read_json(path, {})
    payload.update({key: value for key, value in updates.items() if value is not None})
    for key in clear_keys or []:
        payload.pop(str(key), None)
    payload["last_checkpoint_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(path, payload)
    return path


def write_node_checkpoint(
    repo_b_path: Path,
    *,
    project: str,
    task_payload: dict[str, Any] | None,
    task_id: str | None,
    node_name: str,
    phase: str,
    current_step: str | None,
    branch_name: str | None,
    fix_attempts: int | None,
    error_message: str | None,
    extra: dict[str, Any] | None = None,
) -> Path:
    task_payload = task_payload or {}
    updates = {
        "project": project,
        "backlog_id": task_payload.get("backlog_id"),
        "backlog_root": task_payload.get("backlog_root"),
        "sprint_id": task_payload.get("sprint_id"),
        "sprint_label": task_payload.get("sprint"),
        "story_id": task_payload.get("story_id") or task_payload.get("task_id"),
        "task_name": task_payload.get("task_name") or task_payload.get("goal"),
        "task_id": task_id,
        "current_node": node_name,
        "current_phase": phase,
        "current_step": current_step,
        "branch_name": branch_name,
        "fix_attempts": fix_attempts,
        "error_message": error_message,
        "resume_from_story": task_payload.get("story_id") or task_payload.get("task_id"),
        "status": "running" if not error_message else "interrupted",
    }
    if extra:
        updates.update(extra)
    return write_resume_state(repo_b_path, updates)


def update_story_status(repo_b_path: Path, entry: dict[str, Any]) -> Path:
    registry_path = repo_b_path / "tasks" / "story_status_registry.json"
    payload = _read_json(registry_path, {"stories": []})
    stories = payload.get("stories") if isinstance(payload, dict) else []
    if not isinstance(stories, list):
        stories = []
    entry = _normalize_story_status_entry(entry)

    updated: list[dict[str, Any]] = []
    replaced = False
    for item in stories:
        if not isinstance(item, dict):
            continue
        if _story_registry_key(item) == _story_registry_key(entry):
            merged = dict(item)
            merged.update(entry)
            updated.append(merged)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(entry)

    _write_json(registry_path, {"stories": updated})
    return registry_path


def update_story_acceptance_review(repo_b_path: Path, review: dict[str, Any]) -> Path:
    registry_path = repo_b_path / "tasks" / "story_acceptance_reviews.json"
    payload = _read_json(registry_path, {"reviews": []})
    reviews = payload.get("reviews") if isinstance(payload, dict) else []
    if not isinstance(reviews, list):
        reviews = []
    review = _normalize_story_acceptance_review(review)

    updated: list[dict[str, Any]] = []
    replaced = False
    for item in reviews:
        if not isinstance(item, dict):
            continue
        if _review_registry_key(item) == _review_registry_key(review):
            merged = dict(item)
            merged.update(review)
            updated.append(merged)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(review)

    _write_json(registry_path, {"reviews": updated})
    return registry_path


def update_agent_coverage_report(repo_b_path: Path, entry: dict[str, Any]) -> tuple[Path, Path]:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    report_path = runtime_paths["runtime_root"] / "agent_coverage_report.json"
    payload = _read_json(report_path, {"stories": []})
    stories = payload.get("stories") if isinstance(payload, dict) else []
    if not isinstance(stories, list):
        stories = []

    updated: list[dict[str, Any]] = []
    replaced = False
    for item in stories:
        if not isinstance(item, dict):
            continue
        if _story_registry_key(item) == _story_registry_key(entry):
            merged = dict(item)
            merged.update(entry)
            updated.append(merged)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(entry)

    complete = 0
    partial = 0
    missing = 0
    for item in updated:
        coverage = item.get("agent_mode_coverage") if isinstance(item, dict) else {}
        missing_required = list((coverage or {}).get("missing_required") or [])
        if missing_required:
            partial += 1
        elif coverage:
            complete += 1
        else:
            missing += 1

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "coverage_status": "complete" if partial == 0 and missing == 0 and updated else ("partial" if updated else "missing"),
        "summary": {
            "story_count": len(updated),
            "complete_count": complete,
            "partial_count": partial,
            "missing_count": missing,
        },
        "stories": updated,
    }
    _write_json(report_path, payload)

    markdown_path = runtime_paths["runtime_root"] / "agent_coverage_report.md"
    lines = [
        "# Agent Coverage Report",
        "",
        f"- Updated at: {payload['updated_at']}",
        f"- Coverage status: {payload['coverage_status']}",
        f"- Stories tracked: {len(updated)}",
        "",
        "## Stories",
    ]
    for item in sorted(updated, key=lambda current: (str(current.get("sprint_id") or ""), str(current.get("story_id") or ""))):
        coverage = item.get("agent_mode_coverage") if isinstance(item, dict) else {}
        missing_required = list((coverage or {}).get("missing_required") or [])
        lines.extend(
            [
                f"### {item.get('story_id') or 'unknown'}",
                f"- Sprint: {item.get('sprint_id') or 'unknown'}",
                f"- Executed: {', '.join(item.get('executed_modes') or []) or 'none'}",
                f"- Required: {', '.join(item.get('required_modes') or []) or 'none'}",
                f"- Missing required: {', '.join(missing_required) or 'none'}",
                "",
            ]
        )
    markdown_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return report_path, markdown_path


def write_story_failure(repo_b_path: Path, story_id: str, payload: dict[str, Any]) -> Path:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    failure_path = runtime_paths["story_failures_root"] / f"{story_id}.json"
    snapshot = dict(payload)
    snapshot["story_id"] = story_id
    snapshot["captured_at"] = datetime.now().isoformat(timespec="seconds")
    _write_json(failure_path, snapshot)
    return failure_path


def write_story_handoff(repo_b_path: Path, story_id: str, payload: dict[str, Any]) -> Path:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    handoff_path = runtime_paths["story_handoffs_root"] / f"{story_id}.md"
    handoff_path.write_text(_build_handoff_markdown(payload), encoding="utf-8")
    return handoff_path


def write_current_handoff(repo_b_path: Path, payload: dict[str, Any]) -> dict[str, Path]:
    runtime_paths = ensure_runtime_layout(repo_b_path)
    handoff_text = _build_handoff_markdown(payload)
    handoff_path = runtime_paths["workspace_meta_root"] / "handoff.md"
    task_path = runtime_paths["workspace_meta_root"] / "TASK.md"
    project_handoff_path = runtime_paths["docs_handoff_root"] / "current_handoff.md"
    task_text = _build_task_markdown(payload)

    handoff_path.write_text(handoff_text, encoding="utf-8")
    project_handoff_path.write_text(handoff_text, encoding="utf-8")
    task_path.write_text(task_text, encoding="utf-8")
    return {
        "workspace_handoff": handoff_path,
        "workspace_task": task_path,
        "project_handoff": project_handoff_path,
    }


def collect_mode_artifact_paths(state: dict[str, Any]) -> dict[str, str]:
    mapping = {
        "office-hours": state.get("office_hours_dir"),
        "plan-ceo-review": state.get("plan_ceo_review_dir"),
        "plan-eng-review": state.get("architecture_review_dir"),
        "investigate": state.get("investigate_dir"),
        "browse": state.get("browse_dir") or state.get("browser_qa_dir"),
        "plan-design-review": state.get("plan_design_review_dir"),
        "design-consultation": state.get("design_consultation_dir"),
        "qa": state.get("runtime_qa_dir") or state.get("browser_qa_dir"),
        "qa-only": state.get("runtime_qa_dir") or state.get("browser_qa_dir"),
        "design-review": state.get("qa_design_review_dir"),
        "setup-browser-cookies": state.get("setup_browser_cookies_dir") or state.get("browser_runtime_dir"),
        "review": state.get("review_dir"),
        "ship": state.get("ship_dir"),
        "document-release": state.get("document_release_dir"),
        "retro": state.get("retro_dir"),
    }
    return {key: str(value) for key, value in mapping.items() if value}


def _story_registry_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("backlog_id") or ""),
        str(entry.get("sprint_id") or ""),
        str(entry.get("story_id") or ""),
    )


def _review_registry_key(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(entry.get("backlog_id") or ""),
        str(entry.get("sprint_id") or ""),
        str(entry.get("story_id") or ""),
        str(entry.get("reviewer") or ""),
    )


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_story_status_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    evidence_paths = _coerce_paths(normalized.get("evidence"))
    if not evidence_paths:
        evidence_paths = _coerce_paths(normalized.get("evidence_paths"))
    if evidence_paths:
        normalized["evidence"] = evidence_paths

    coverage = normalized.get("agent_mode_coverage") if isinstance(normalized.get("agent_mode_coverage"), dict) else {}
    required_modes = [str(item).strip() for item in (normalized.get("required_modes") or coverage.get("required") or []) if str(item).strip()]
    executed_modes = [str(item).strip() for item in (normalized.get("executed_modes") or coverage.get("executed") or []) if str(item).strip()]
    advisory_modes = [str(item).strip() for item in (normalized.get("advisory_modes") or coverage.get("advisory") or []) if str(item).strip()]
    if required_modes and not coverage:
        coverage = build_mode_coverage(required_modes, advisory_modes, executed_modes)
    if coverage:
        normalized["agent_mode_coverage"] = coverage
    if required_modes:
        normalized["required_modes"] = required_modes
    if executed_modes:
        normalized["executed_modes"] = executed_modes
    if advisory_modes:
        normalized["advisory_modes"] = advisory_modes

    if normalized.get("formal_entry") is True and not str(normalized.get("attempt_status") or "").strip():
        normalized["attempt_status"] = "authoritative"

    status = str(normalized.get("status") or "").strip().lower()
    attempt_status = str(normalized.get("attempt_status") or "").strip().lower()
    if attempt_status == "stale_attempt":
        reasons = _formal_flow_gap_reasons(normalized, coverage, evidence_paths)
        if "superseded_by_authoritative_rerun" not in reasons:
            reasons.append("superseded_by_authoritative_rerun")
        normalized["formal_flow_gap_reasons"] = reasons
        normalized["formal_flow_complete"] = False
        normalized["status"] = "stale_attempt"
        return normalized
    if status in _FORMAL_FLOW_SUCCESS_STATUSES:
        reasons = _formal_flow_gap_reasons(normalized, coverage, evidence_paths)
        normalized["formal_flow_gap_reasons"] = reasons
        normalized["formal_flow_complete"] = not reasons
        if reasons:
            normalized["status"] = "evidence_incomplete" if evidence_paths else "implemented_without_formal_flow"
    return normalized


def _normalize_story_acceptance_review(review: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(review)
    evidence_paths = _coerce_paths(normalized.get("evidence_paths"))
    if evidence_paths:
        normalized["evidence_paths"] = evidence_paths

    coverage = normalized.get("agent_mode_coverage") if isinstance(normalized.get("agent_mode_coverage"), dict) else {}
    verdict = str(normalized.get("verdict") or "").strip().lower()
    acceptance_status = str(normalized.get("acceptance_status") or "").strip().lower()
    if normalized.get("formal_entry") is True and not str(normalized.get("attempt_status") or "").strip():
        normalized["attempt_status"] = "authoritative"
    if str(normalized.get("attempt_status") or "").strip().lower() == "stale_attempt":
        reasons = _formal_flow_gap_reasons(normalized, coverage, evidence_paths)
        if "superseded_by_authoritative_rerun" not in reasons:
            reasons.append("superseded_by_authoritative_rerun")
        normalized["formal_flow_gap_reasons"] = reasons
        normalized["formal_flow_complete"] = False
        normalized["verdict"] = "needs_followup"
        normalized["acceptance_status"] = "needs_followup"
        note = str(normalized.get("notes") or "").strip()
        gap_line = "Formal flow gaps: " + "; ".join(reasons)
        normalized["notes"] = f"{note}\n{gap_line}".strip()
        return normalized
    if verdict in _FORMAL_FLOW_APPROVED_STATUSES or acceptance_status in _FORMAL_FLOW_APPROVED_STATUSES:
        reasons = _formal_flow_gap_reasons(normalized, coverage, evidence_paths)
        normalized["formal_flow_gap_reasons"] = reasons
        normalized["formal_flow_complete"] = not reasons
        if reasons:
            normalized["verdict"] = "needs_followup"
            normalized["acceptance_status"] = "needs_followup"
            note = str(normalized.get("notes") or "").strip()
            gap_line = "Formal flow gaps: " + "; ".join(reasons)
            normalized["notes"] = f"{note}\n{gap_line}".strip()
    return normalized


def _formal_flow_gap_reasons(
    payload: dict[str, Any],
    coverage: dict[str, Any] | None,
    evidence_paths: list[str],
) -> list[str]:
    reasons: list[str] = []
    if str(payload.get("attempt_status") or "").strip().lower() == "stale_attempt":
        reasons.append("superseded_by_authoritative_rerun")
    if not bool(payload.get("formal_entry")):
        reasons.append("formal_entry_missing")
    if not evidence_paths:
        reasons.append("evidence_missing")
    if coverage:
        if not bool(coverage.get("all_required_executed")):
            reasons.append("required_modes_missing")
    elif payload.get("required_modes"):
        reasons.append("coverage_missing")

    reviewer = str(payload.get("formal_acceptance_reviewer") or payload.get("reviewer") or "").strip().lower()
    if (
        str(payload.get("status") or "").strip().lower() in _FORMAL_FLOW_SUCCESS_STATUSES
        or str(payload.get("verdict") or "").strip().lower() in _FORMAL_FLOW_APPROVED_STATUSES
        or str(payload.get("acceptance_status") or "").strip().lower() in _FORMAL_FLOW_APPROVED_STATUSES
        or payload.get("accepted") is True
    ) and reviewer != _FORMAL_ACCEPTANCE_REVIEWER:
        reasons.append("acceptance_gate_missing")

    flags = {
        "implemented": payload.get("implemented"),
        "verified": payload.get("verified"),
        "agentized": payload.get("agentized"),
        "accepted": payload.get("accepted"),
    }
    for key, value in flags.items():
        if value is not True:
            reasons.append(f"{key}_missing")
    return reasons


def _coerce_paths(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    marker = str(value or "").strip()
    return [marker] if marker else []


def _build_handoff_markdown(payload: dict[str, Any]) -> str:
    evidence = [str(item) for item in (payload.get("evidence_paths") or []) if str(item).strip()]
    lines = [
        "# Current Handoff",
        "",
        f"- Updated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Project: {payload.get('project') or 'unknown'}",
        f"- Backlog: {payload.get('backlog_id') or 'unknown'}",
        f"- Sprint: {payload.get('sprint_id') or payload.get('sprint_label') or 'unknown'}",
        f"- Story: {payload.get('story_id') or 'unknown'}",
        f"- Node: {payload.get('current_node') or 'unknown'}",
        f"- Status: {payload.get('status') or 'unknown'}",
        f"- Last success story: {payload.get('last_success_story') or 'none'}",
        f"- Resume from story: {payload.get('resume_from_story') or payload.get('story_id') or 'unknown'}",
        f"- Interruption reason: {payload.get('interruption_reason') or 'none'}",
        f"- Execution policy: {payload.get('execution_policy') or 'unspecified'}",
        f"- Interaction policy: {payload.get('interaction_policy') or 'unspecified'}",
        f"- Pause policy: {payload.get('pause_policy') or 'unspecified'}",
        f"- Blocker class: {payload.get('blocker_class') or 'none'}",
        "",
        "## Root Cause",
        str(payload.get("root_cause") or payload.get("error_message") or "No confirmed root cause recorded."),
        "",
        "## Next Action",
        str(payload.get("next_action") or "Resume from the recorded story and continue execution."),
        "",
        "## Recovery Command",
        str(payload.get("resume_command") or "python cli.py auto-deliver --project agentHire --env test --prefix backlog_v1 --auto-run"),
        "",
        "## Evidence",
    ]
    if evidence:
        lines.extend(f"- {item}" for item in evidence)
    else:
        lines.append("- No evidence paths recorded.")
    lines.extend(
        [
            "",
            "## Cleanup",
            str(payload.get("cleanup_note") or "No cleanup required."),
            "",
        ]
    )
    return "\n".join(lines)


def _build_task_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Active Task",
        "",
        f"- Project: {payload.get('project') or 'unknown'}",
        f"- Objective: {payload.get('task_name') or payload.get('goal') or 'Continue automatic story delivery'}",
        f"- Backlog: {payload.get('backlog_id') or 'unknown'}",
        f"- Sprint: {payload.get('sprint_id') or payload.get('sprint_label') or 'unknown'}",
        f"- Story: {payload.get('story_id') or 'unknown'}",
        f"- Node: {payload.get('current_node') or 'unknown'}",
        f"- Status: {payload.get('status') or 'unknown'}",
        f"- Execution policy: {payload.get('execution_policy') or 'unspecified'}",
        f"- Interaction policy: {payload.get('interaction_policy') or 'unspecified'}",
        f"- Pause policy: {payload.get('pause_policy') or 'unspecified'}",
        f"- Blocker class: {payload.get('blocker_class') or 'none'}",
        "",
        "## Immediate Next Step",
        str(payload.get("next_action") or "Continue the next story from the current resume checkpoint."),
        "",
    ]
    return "\n".join(lines)
