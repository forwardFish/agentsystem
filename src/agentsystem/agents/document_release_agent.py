from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_executed_mode,
    add_handoff_packet,
)


def generate_document_release_artifacts(
    repo_b_path: str | Path,
    state: dict[str, Any],
    task_payload: dict[str, Any],
) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    document_release_dir = repo_path.parent / ".meta" / repo_path.name / "document_release"
    document_release_dir.mkdir(parents=True, exist_ok=True)

    targets = _resolve_doc_targets(repo_path, state, task_payload)
    checklist = _build_doc_checklist(repo_path, targets, state, task_payload)
    stale_sections = [item["detail"] for item in checklist if item["status"] != "current"]
    sync_actions = _build_sync_actions(checklist, stale_sections)
    applied_changes, skipped_targets = _apply_doc_sync(repo_path, checklist, state, task_payload)
    diff_summary = _build_doc_diff_summary(applied_changes, skipped_targets)

    report_lines = [
        "# Document Release Report",
        "",
        f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
        f"- Repo: {repo_path.name}",
        "",
        "## Release Scope",
        *([f"- {item}" for item in (task_payload.get("release_scope") or state.get("release_scope") or []) if str(item).strip()] or ["- No explicit release scope declared."]),
        "",
        "## Documentation Checklist",
    ]
    for item in checklist:
        report_lines.append(f"- {item['target']}: {item['status']} - {item['detail']}")
    report_lines.extend(
        [
        "",
        "## Stale Sections Or Required Updates",
        *([f"- {item}" for item in stale_sections] or ["- None identified."]),
        "",
        "## Sync Actions",
        *([f"- {item}" for item in sync_actions] or ["- None."]),
        "",
        "## Applied Changes",
        *([f"- {item['target']}: appended release sync note." for item in applied_changes] or ["- None."]),
        "",
        "## Skipped Targets",
        *([f"- {item['target']}: {item['reason']}" for item in skipped_targets] or ["- None."]),
        "",
        "## Carry Into Retro",
        f"- Doc targets: {', '.join(targets) if targets else 'n/a'}",
        f"- Stale sections count: {len(stale_sections)}",
        "",
        "## Sync Guidance",
        "- Keep README, handoff, runbook, and release-facing docs aligned with what actually shipped.",
        "- Planning assets should be updated conservatively; do not rewrite manual planning history just to match code.",
            "",
        ]
    )
    report = "\n".join(report_lines)

    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "doc_targets": targets,
        "checklist": checklist,
        "stale_sections": stale_sections,
        "sync_actions": sync_actions,
        "applied_changes": applied_changes,
        "skipped_targets": skipped_targets,
    }
    report_path = document_release_dir / "document_release_report.md"
    report_path.write_text(report, encoding="utf-8")
    plan_path = document_release_dir / "doc_sync_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    stale_path = document_release_dir / "stale_sections.json"
    stale_path.write_text(json.dumps(stale_sections, ensure_ascii=False, indent=2), encoding="utf-8")
    applied_changes_path = document_release_dir / "applied_doc_changes.json"
    applied_changes_path.write_text(json.dumps(applied_changes, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_summary_path = document_release_dir / "doc_diff_summary.json"
    diff_summary_path.write_text(json.dumps(diff_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    skipped_targets_path = document_release_dir / "skipped_doc_targets.json"
    skipped_targets_path.write_text(json.dumps(skipped_targets, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "dir": str(document_release_dir),
        "report": report,
        "report_path": str(report_path),
        "targets": targets,
        "plan_path": str(plan_path),
        "stale_path": str(stale_path),
        "checklist": checklist,
        "sync_actions": sync_actions,
        "stale_sections": stale_sections,
        "applied_changes": applied_changes,
        "skipped_targets": skipped_targets,
        "applied_changes_path": str(applied_changes_path),
        "diff_summary_path": str(diff_summary_path),
        "skipped_targets_path": str(skipped_targets_path),
    }


def document_release_node(state: DevState) -> DevState:
    task_payload = state.get("task_payload") or {}
    artifacts = generate_document_release_artifacts(state["repo_b_path"], state, task_payload)
    state["document_release_success"] = True
    state["document_release_dir"] = artifacts["dir"]
    state["document_release_report"] = artifacts["report"]
    state["document_release_targets"] = artifacts["targets"]
    state["document_release_stale_sections"] = artifacts["stale_sections"]
    state["document_release_sync_actions"] = artifacts["sync_actions"]
    state["document_release_applied_changes"] = artifacts["applied_changes"]
    state["document_release_skipped_targets"] = artifacts["skipped_targets"]
    state["current_step"] = "document_release_done"
    state["error_message"] = None
    add_executed_mode(state, "document-release")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.DOCUMENT_RELEASE,
            to_agent=AgentRole.RETRO,
            status=HandoffStatus.COMPLETED,
            what_i_did="Checked release-facing documentation targets and packaged the drift list for closeout.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Document Release Report",
                    type="report",
                    path=str(artifacts["report_path"]),
                    description="Documentation sync report for shipped scope and release-facing docs.",
                    created_by=AgentRole.DOCUMENT_RELEASE,
                )
            ],
            what_risks_i_found=[item["detail"] for item in artifacts["checklist"] if item["status"] != "current"],
            what_i_require_next="Carry the documentation drift list into retro and close the remaining release-facing gaps.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_document_release(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "document_release":
        return "__end__"
    return "retro"


def _resolve_doc_targets(repo_path: Path, state: dict[str, Any], task_payload: dict[str, Any]) -> list[str]:
    declared = [str(item).strip() for item in (task_payload.get("doc_targets") or state.get("doc_targets") or []) if str(item).strip()]
    if declared:
        return declared
    candidates: list[Path] = []
    for relative in ("README.md", "docs/handoff/current_handoff.md", "docs", "tasks/runtime"):
        candidate = repo_path / relative
        if candidate.exists():
            candidates.append(candidate)
    return [str(path.relative_to(repo_path)) for path in candidates]


def _build_doc_checklist(
    repo_path: Path,
    targets: list[str],
    state: dict[str, Any],
    task_payload: dict[str, Any],
) -> list[dict[str, str]]:
    release_scope = [str(item).strip() for item in (task_payload.get("release_scope") or state.get("release_scope") or []) if str(item).strip()]
    checklist: list[dict[str, str]] = []
    for target in targets:
        path = repo_path / target
        if not path.exists():
            checklist.append({"target": target, "status": "missing", "detail": "Declared doc target does not exist."})
            continue
        if path.is_dir():
            checklist.append({"target": target, "status": "review", "detail": "Directory target exists; review changed docs inside it."})
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if release_scope and not any(scope in text for scope in release_scope[:3]):
            checklist.append({"target": target, "status": "review", "detail": "Release scope is not clearly reflected in this document yet."})
            continue
        if state.get("browser_qa_health_score") is not None and "browser" not in text.lower() and "qa" not in text.lower():
            checklist.append({"target": target, "status": "review", "detail": "Runtime or QA evidence may need to be reflected here."})
            continue
        checklist.append({"target": target, "status": "current", "detail": "No obvious drift detected from current release scope."})
    if not checklist:
        checklist.append({"target": "README.md", "status": "review", "detail": "No explicit targets found; at least README or handoff should be reviewed."})
    return checklist


def _build_sync_actions(checklist: list[dict[str, str]], stale_sections: list[str]) -> list[str]:
    actions: list[str] = []
    for item in checklist:
        if item["status"] == "missing":
            actions.append(f"Create or restore the declared documentation target `{item['target']}`.")
        elif item["status"] == "review":
            actions.append(f"Review `{item['target']}` against the shipped scope and QA evidence.")
    if stale_sections:
        actions.append("Carry unresolved documentation drift into retro and the next planning cycle.")
    return actions


def _apply_doc_sync(
    repo_path: Path,
    checklist: list[dict[str, str]],
    state: dict[str, Any],
    task_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    applied_changes: list[dict[str, Any]] = []
    skipped_targets: list[dict[str, Any]] = []
    release_scope = [str(item).strip() for item in (task_payload.get("release_scope") or state.get("release_scope") or []) if str(item).strip()]
    qa_summary = str(state.get("browser_qa_ship_readiness") or state.get("browser_qa_health_score") or "").strip()
    sync_note = _build_sync_note(release_scope, qa_summary)
    for item in checklist:
        target = str(item.get("target") or "").strip()
        status = str(item.get("status") or "").strip()
        path = repo_path / target
        if not target or not path.exists() or path.is_dir():
            skipped_targets.append({"target": target, "reason": "Missing or directory target cannot be edited in-place."})
            continue
        if status == "current":
            continue
        if not _is_safe_doc_target(target):
            skipped_targets.append({"target": target, "reason": "Target is outside the auto-sync allowlist."})
            continue
        original = path.read_text(encoding="utf-8", errors="ignore")
        if sync_note in original:
            continue
        updated = original.rstrip() + "\n\n" + sync_note
        path.write_text(updated, encoding="utf-8")
        applied_changes.append(
            {
                "target": target,
                "previous_length": len(original),
                "updated_length": len(updated),
                "sync_note": sync_note.splitlines()[0],
            }
        )
    return applied_changes, skipped_targets


def _build_sync_note(release_scope: list[str], qa_summary: str) -> str:
    scope_text = ", ".join(release_scope) if release_scope else "current shipped scope"
    qa_text = qa_summary or "available QA evidence"
    return (
        "## Release Sync Note\n"
        f"- Scope: {scope_text}\n"
        f"- QA evidence: {qa_text}\n"
        "- This note was appended by document-release to keep release-facing docs aligned.\n"
    )


def _build_doc_diff_summary(
    applied_changes: list[dict[str, Any]],
    skipped_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "applied_count": len(applied_changes),
        "skipped_count": len(skipped_targets),
        "updated_targets": [item["target"] for item in applied_changes],
        "skipped_targets": [item["target"] for item in skipped_targets],
    }


def _is_safe_doc_target(target: str) -> bool:
    normalized = target.replace("\\", "/")
    return normalized == "README.md" or normalized.startswith("docs/")
