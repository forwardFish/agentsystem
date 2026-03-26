from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy
from agentsystem.orchestration.story_contracts import enrich_task_with_story_contracts


def build_story_admission(
    task: dict[str, Any],
    repo_b_path: str | Path,
    *,
    story_file: str | Path | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    runtime_task = dict(task)
    if not runtime_task.get("agent_activation_plan") or not runtime_task.get("required_modes"):
        runtime_task = apply_agent_activation_policy(runtime_task, repo_path)
    elif not runtime_task.get("implementation_contract") or not runtime_task.get("agent_execution_contract"):
        runtime_task = enrich_task_with_story_contracts(runtime_task)

    related_files = [str(item).strip() for item in (runtime_task.get("related_files") or []) if str(item).strip()]
    acceptance_criteria = [
        str(item).strip() for item in (runtime_task.get("acceptance_criteria") or []) if str(item).strip()
    ]
    required_modes = [str(item).strip() for item in (runtime_task.get("required_modes") or []) if str(item).strip()]
    advisory_modes = [str(item).strip() for item in (runtime_task.get("advisory_modes") or []) if str(item).strip()]
    story_kind = str(runtime_task.get("story_kind") or "").strip() or "unknown"
    formal_execution_requested = bool(runtime_task.get("auto_run")) or bool(runtime_task.get("formal_entry")) or (
        str(runtime_task.get("interaction_policy") or "").strip() == "non_interactive_auto_run"
    )

    errors: list[str] = []
    warnings: list[str] = []

    if not related_files:
        errors.append("Story must declare in-scope files before formal execution can start.")
    if not acceptance_criteria:
        errors.append("Story must declare acceptance_criteria before formal execution can start.")
    if not required_modes:
        errors.append("Workflow admission could not resolve required modes for this story.")
    if not runtime_task.get("implementation_contract"):
        errors.append("Workflow admission is missing implementation_contract.")
    if not runtime_task.get("agent_execution_contract"):
        errors.append("Workflow admission is missing agent_execution_contract.")
    if not runtime_task.get("expanded_required_agents"):
        errors.append("Workflow admission is missing expanded_required_agents.")
    if not runtime_task.get("mode_to_agent_map"):
        errors.append("Workflow admission is missing mode_to_agent_map.")
    if not runtime_task.get("parity_evidence_contract"):
        errors.append("Workflow admission is missing parity_evidence_contract.")

    has_browser_urls = any(
        str(item).strip()
        for key in ("browser_urls", "qa_urls", "preview_urls", "runtime_urls")
        for item in (
            runtime_task.get(key)
            if isinstance(runtime_task.get(key), list)
            else [runtime_task.get(key)]
        )
    )
    has_browser_surface = has_browser_urls or bool(str(runtime_task.get("preview_base_url") or "").strip())
    if story_kind in {"ui", "mixed"} and not has_browser_surface:
        message = "UI/browser story must declare browser_urls/qa_urls/preview_urls before formal execution can start."
        if formal_execution_requested:
            errors.append(message)
        else:
            warnings.append(message)

    if formal_execution_requested and str(runtime_task.get("execution_policy") or "").strip() == "continuous_full_sprint":
        missing_sprint_artifacts = [
            key
            for key in ("office_hours_path", "plan_ceo_review_path", "sprint_framing_path")
            if not str(runtime_task.get(key) or "").strip()
        ]
        if missing_sprint_artifacts:
            errors.append(
                "Sprint admission is missing required pre-hook artifacts: " + ", ".join(missing_sprint_artifacts)
            )

    admission = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "story_id": str(runtime_task.get("story_id") or runtime_task.get("task_id") or "").strip(),
        "story_file": str(Path(story_file).resolve()) if story_file else None,
        "story_kind": story_kind,
        "required_modes": required_modes,
        "advisory_modes": advisory_modes,
        "expanded_required_agents": list(runtime_task.get("expanded_required_agents") or []),
        "mode_to_agent_map": dict(runtime_task.get("mode_to_agent_map") or {}),
        "parity_evidence_contract": dict(runtime_task.get("parity_evidence_contract") or {}),
        "implementation_contract": dict(runtime_task.get("implementation_contract") or {}),
        "required_artifact_types": list(runtime_task.get("required_artifact_types") or []),
        "agent_execution_contract": list(runtime_task.get("agent_execution_contract") or []),
        "blocking_issue_types": list(runtime_task.get("blocking_issue_types") or []),
        "related_files": related_files,
        "acceptance_criteria_count": len(acceptance_criteria),
        "has_browser_urls": has_browser_surface,
        "formal_execution_requested": formal_execution_requested,
        "admitted": not errors,
        "errors": errors,
        "warnings": warnings,
        "task_payload": runtime_task,
    }
    return admission


def write_story_admission(
    repo_b_path: str | Path,
    story_id: str,
    admission: dict[str, Any],
) -> Path:
    repo_path = Path(repo_b_path).resolve()
    runtime_dir = repo_path / "tasks" / "runtime" / "story_admissions"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / f"{story_id}.json"
    path.write_text(json.dumps(admission, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
