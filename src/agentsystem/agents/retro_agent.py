from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from git import Repo

from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_executed_mode,
    add_handoff_packet,
)


def generate_retro_artifacts(repo_b_path: str | Path, state: dict[str, Any], task_payload: dict[str, Any]) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    retro_dir = repo_path.parent / ".meta" / repo_path.name / "retro"
    retro_dir.mkdir(parents=True, exist_ok=True)

    positives = _positives(state)
    pain_points = _pain_points(state)
    next_actions = _next_actions(state, task_payload)
    closeout_linkage = _closeout_linkage(state)
    previous_snapshot = _load_previous_snapshot(retro_dir)
    metrics = {
        "mode_execution_order": list(state.get("mode_execution_order") or []),
        "deliverable_count": len(state.get("all_deliverables") or []),
        "open_issue_count": len(state.get("issues_to_fix") or []),
        "resolved_issue_count": len(state.get("resolved_issues") or []),
        "browser_qa_health_score": state.get("browser_qa_health_score"),
        "test_passed": bool(state.get("test_passed")),
        "acceptance_passed": bool(state.get("acceptance_passed")),
    }
    trend_analysis = _build_trend_analysis(previous_snapshot, metrics)
    git_activity_summary = _build_git_activity_summary(repo_path)
    contributors = [
        {
            "name": "agentsystem",
            "wins": positives[:2] or ["The workflow completed with reusable artifacts."],
            "growth": pain_points[:2] or ["Keep shrinking the amount of manual evidence stitching required."],
        }
    ]
    report_lines = [
        "# Retro Report",
        "",
        f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
        f"- Window: {state.get('retro_window') or task_payload.get('retro_window') or 'current cycle'}",
        "",
        "## Metrics",
        f"- Deliverables: {metrics['deliverable_count']}",
        f"- Open issues: {metrics['open_issue_count']}",
        f"- Resolved issues: {metrics['resolved_issue_count']}",
        f"- Browser QA health score: {metrics['browser_qa_health_score'] if metrics['browser_qa_health_score'] is not None else '-'}",
        f"- Tests passed: {'yes' if metrics['test_passed'] else 'no'}",
        f"- Acceptance passed: {'yes' if metrics['acceptance_passed'] else 'no'}",
        f"- Modes executed: {', '.join(metrics['mode_execution_order']) if metrics['mode_execution_order'] else 'n/a'}",
        "",
        "## Wins",
        *([f"- {item}" for item in positives] or ["- None recorded."]),
        "",
        "## Pain Points",
        *([f"- {item}" for item in pain_points] or ["- None recorded."]),
        "",
        "## Closeout Linkage",
        *([f"- {item}" for item in closeout_linkage] or ["- None recorded."]),
        "",
        "## Trend Analysis",
        f"- Deliverable delta: {trend_analysis['deliverable_delta']}",
        f"- Open issue delta: {trend_analysis['open_issue_delta']}",
        f"- Resolved issue delta: {trend_analysis['resolved_issue_delta']}",
        f"- Browser health delta: {trend_analysis['browser_health_delta']}",
        "",
        "## Git Activity",
        f"- Recent commits: {git_activity_summary['commit_count']}",
        f"- Authors: {', '.join(git_activity_summary['authors']) if git_activity_summary['authors'] else 'n/a'}",
        "",
        "## Next Actions",
        *([f"- {item}" for item in next_actions] or ["- None recorded."]),
        "",
    ]
    report = "\n".join(report_lines)
    report_path = retro_dir / "retro_report.md"
    report_path.write_text(report, encoding="utf-8")
    contributor_path = retro_dir / "contributor_notes.json"
    contributor_path.write_text(json.dumps({"contributors": contributors}, ensure_ascii=False, indent=2), encoding="utf-8")
    closeout_path = retro_dir / "closeout_linkage.json"
    closeout_path.write_text(json.dumps({"items": closeout_linkage}, ensure_ascii=False, indent=2), encoding="utf-8")
    previous_snapshot_path = retro_dir / "previous_snapshot.json"
    previous_snapshot_path.write_text(json.dumps(previous_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    trend_analysis_path = retro_dir / "trend_analysis.json"
    trend_analysis_path.write_text(json.dumps(trend_analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    git_activity_summary_path = retro_dir / "git_activity_summary.json"
    git_activity_summary_path.write_text(json.dumps(git_activity_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path = retro_dir / "retro_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "window": state.get("retro_window") or task_payload.get("retro_window") or "current cycle",
                "metrics": metrics,
                "positives": positives,
                "pain_points": pain_points,
                "closeout_linkage": closeout_linkage,
                "next_actions": next_actions,
                "trend_analysis": trend_analysis,
                "git_activity_summary": git_activity_summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "dir": str(retro_dir),
        "report": report,
        "report_path": str(report_path),
        "contributors_path": str(contributor_path),
        "closeout_path": str(closeout_path),
        "snapshot_path": str(snapshot_path),
        "previous_snapshot_path": str(previous_snapshot_path),
        "trend_analysis_path": str(trend_analysis_path),
        "git_activity_summary_path": str(git_activity_summary_path),
    }


def retro_node(state: DevState) -> DevState:
    task_payload = state.get("task_payload") or {}
    artifacts = generate_retro_artifacts(state["repo_b_path"], state, task_payload)
    state["retro_success"] = True
    state["retro_dir"] = artifacts["dir"]
    state["retro_report"] = artifacts["report"]
    state["retro_closeout_linkage_path"] = artifacts["closeout_path"]
    state["retro_previous_snapshot_path"] = artifacts["previous_snapshot_path"]
    state["retro_trend_analysis_path"] = artifacts["trend_analysis_path"]
    state["retro_git_activity_summary_path"] = artifacts["git_activity_summary_path"]
    state["current_step"] = "retro_done"
    state["error_message"] = None
    add_executed_mode(state, "retro")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.RETRO,
            to_agent=AgentRole.RETRO,
            status=HandoffStatus.COMPLETED,
            what_i_did="Summarized the cycle into wins, pain points, next actions, and a reusable retro snapshot.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Retro Report",
                    type="report",
                    path=str(artifacts["report_path"]),
                    description="Cycle retrospective with metrics, wins, pain points, and next actions.",
                    created_by=AgentRole.RETRO,
                )
            ],
            what_risks_i_found=_pain_points(state),
            what_i_require_next="Fold the next actions back into the workflow standard or the next sprint planning cycle.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_retro(state: DevState) -> str:
    return "__end__"


def _positives(state: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if state.get("test_passed"):
        items.append("Validation evidence passed and the build has a clear automated signal.")
    if state.get("acceptance_passed"):
        items.append("Acceptance gate passed, so the result and process both reached a sign-off state.")
    if state.get("mode_execution_order"):
        items.append(f"Executed modes: {', '.join(str(item) for item in state.get('mode_execution_order') or [])}.")
    return items


def _pain_points(state: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if state.get("blocking_issues"):
        items.append(f"Blocking review issues still appeared: {len(state.get('blocking_issues') or [])} item(s).")
    if int(state.get("fix_attempts") or 0) > 0:
        items.append(f"The fixer loop triggered {state.get('fix_attempts')} time(s), so rework is still too high.")
    if state.get("browser_qa_health_score") is not None and int(state.get("browser_qa_health_score") or 0) < 90:
        items.append("Browser QA health is still below the ideal release confidence threshold.")
    return items


def _next_actions(state: dict[str, Any], task_payload: dict[str, Any]) -> list[str]:
    actions = [str(item).strip() for item in (task_payload.get("next_recommended_actions") or []) if str(item).strip()]
    if not actions:
        actions.append("Fold this cycle's pain points back into the unified Story and Sprint workflow standard.")
    if state.get("document_release_targets"):
        actions.append("Finish the doc targets identified by document-release before calling the sprint fully closed.")
    return actions


def _closeout_linkage(state: dict[str, Any]) -> list[str]:
    linkage: list[str] = []
    ship_package = state.get("ship_release_package") or {}
    blockers = ship_package.get("blockers") or []
    if blockers:
        linkage.append(f"Ship blockers carried into retro: {len(blockers)} item(s).")
    doc_targets = [str(item).strip() for item in (state.get("document_release_targets") or []) if str(item).strip()]
    if doc_targets:
        linkage.append(f"Document-release targets reviewed: {', '.join(doc_targets)}.")
    stale_sections = [str(item).strip() for item in (state.get("document_release_stale_sections") or []) if str(item).strip()]
    if stale_sections:
        linkage.append(f"Documentation drift remains in {len(stale_sections)} section(s).")
    if state.get("ship_closeout_checklist"):
        linkage.append("Ship closeout checklist was captured before retro.")
    return linkage


def _load_previous_snapshot(retro_dir: Path) -> dict[str, Any]:
    candidates = sorted(retro_dir.glob("retro_snapshot*.json"))
    for candidate in reversed(candidates):
        if candidate.name == "retro_snapshot.json":
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    baseline = retro_dir / "retro_snapshot.json"
    if baseline.exists():
        try:
            payload = json.loads(baseline.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            return payload
    return {"baseline": True, "metrics": {}}


def _build_trend_analysis(previous_snapshot: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    previous_metrics = previous_snapshot.get("metrics") if isinstance(previous_snapshot, dict) else {}
    if not isinstance(previous_metrics, dict):
        previous_metrics = {}
    return {
        "baseline": bool(previous_snapshot.get("baseline")) if isinstance(previous_snapshot, dict) else True,
        "deliverable_delta": int(metrics.get("deliverable_count") or 0) - int(previous_metrics.get("deliverable_count") or 0),
        "open_issue_delta": int(metrics.get("open_issue_count") or 0) - int(previous_metrics.get("open_issue_count") or 0),
        "resolved_issue_delta": int(metrics.get("resolved_issue_count") or 0) - int(previous_metrics.get("resolved_issue_count") or 0),
        "browser_health_delta": int(metrics.get("browser_qa_health_score") or 0) - int(previous_metrics.get("browser_qa_health_score") or 0),
        "mode_delta": len(metrics.get("mode_execution_order") or []) - len(previous_metrics.get("mode_execution_order") or []),
    }


def _build_git_activity_summary(repo_path: Path) -> dict[str, Any]:
    try:
        repo = Repo(repo_path)
    except Exception:
        return {"commit_count": 0, "authors": [], "recent_commits": []}
    commits = list(repo.iter_commits(max_count=10))
    authors = []
    seen: set[str] = set()
    for commit in commits:
        name = str(getattr(commit.author, "name", "") or "").strip()
        if name and name not in seen:
            seen.add(name)
            authors.append(name)
    return {
        "commit_count": len(commits),
        "authors": authors,
        "recent_commits": [commit.summary for commit in commits[:5]],
    }
