from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    Issue,
    IssueSeverity,
    add_executed_mode,
    add_handoff_packet,
    add_issue,
)
from agentsystem.runtime.browser_session_manager import BrowserSessionManager
from agentsystem.runtime.playwright_browser_runtime import BrowserTarget, run_browser_capture


def browser_qa_node(state: DevState) -> DevState:
    print("[Browser QA Agent] Running browser-facing verification")

    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    qa_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "browser_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    qa_mode = str(
        state.get("browser_qa_mode")
        or task_payload.get("browser_qa_mode")
        or task_payload.get("qa_mode")
        or "quick"
    ).strip() or "quick"
    report_only = bool(state.get("browser_qa_report_only", task_payload.get("browser_qa_report_only"))) or str(
        qa_mode
    ).lower() in {"report_only", "qa_only"}

    targets = _extract_browser_targets(task_payload)
    manager = BrowserSessionManager(repo_b_path, str(state.get("task_id") or repo_b_path.name))
    capture_result = run_browser_capture(manager, targets)
    snapshot = capture_result["snapshot"]
    observations = capture_result["results"]

    current_observations = [item for item in observations if item.get("kind") == "current"]
    reference_observations = [item for item in observations if item.get("kind") == "reference"]

    blocking_findings = _collect_findings(current_observations, "blocking_findings")
    important_findings = _collect_findings(current_observations, "important_findings")
    reference_warnings = _collect_findings(reference_observations, "important_findings")

    health_score = max(0, 100 - len(blocking_findings) * 25 - len(important_findings) * 6)
    ship_readiness = "ready" if not blocking_findings else "needs_fix"
    if report_only and blocking_findings:
        ship_readiness = "report_only_attention"

    current_summary = _page_summary_lines(current_observations)
    reference_summary = _page_summary_lines(reference_observations)
    screenshot_refs = [
        str(item.get("screenshot_path") or "").strip()
        for item in observations
        if str(item.get("screenshot_path") or "").strip()
    ]
    observation_refs = [
        str(item.get("observation_path") or "").strip()
        for item in observations
        if str(item.get("observation_path") or "").strip()
    ]
    console_refs = [
        str(item.get("console_log_path") or "").strip()
        for item in observations
        if str(item.get("console_log_path") or "").strip()
    ]

    report_lines = [
        "# Browser QA Report",
        "",
        f"- Mode: {qa_mode}",
        f"- Report only: {'yes' if report_only else 'no'}",
        f"- Session ID: {snapshot.session_id}",
        f"- Health score: {health_score}",
        f"- Ship readiness: {ship_readiness}",
        "",
        "## Session Runtime",
        f"- Runtime dir: {manager.runtime_dir}",
        f"- Session manifest: {manager.session_file}",
        f"- Step log: {manager.steps_file}",
        "",
        "## Current Surface Summary",
    ]
    report_lines.extend([f"- {item}" for item in current_summary] or ["- No current-surface targets were configured."])
    report_lines.extend(["", "## Reference Surface Summary"])
    report_lines.extend([f"- {item}" for item in reference_summary] or ["- No reference targets were configured."])
    report_lines.extend(["", "## Blocking Findings"])
    report_lines.extend([f"- {item}" for item in blocking_findings] or ["- None."])
    report_lines.extend(["", "## Important Findings"])
    report_lines.extend([f"- {item}" for item in important_findings] or ["- None."])
    report_lines.extend(["", "## Reference Notes"])
    report_lines.extend([f"- {item}" for item in reference_warnings] or ["- None."])
    report_lines.extend(["", "## Evidence"])
    report_lines.extend([f"- Observation: {item}" for item in observation_refs] or ["- No observation artifacts recorded."])
    report_lines.extend([f"- Screenshot: {item}" for item in screenshot_refs] or ["- No screenshots captured."])
    report_lines.extend([f"- Console log: {item}" for item in console_refs] or ["- No console logs captured."])
    report = "\n".join(report_lines).strip() + "\n"
    report_path = qa_dir / "browser_qa_report.md"
    report_path.write_text(report, encoding="utf-8")

    mode_id = str(task_payload.get("skill_mode") or "").strip()
    if mode_id in {"browse", "qa", "qa-only", "design-review"}:
        add_executed_mode(state, mode_id)
    else:
        add_executed_mode(state, str(state.get("effective_qa_mode") or "qa-only"))

    state["browser_runtime_dir"] = str(manager.runtime_dir)
    state["browser_session_id"] = snapshot.session_id
    state["browse_observations"] = current_observations
    state["reference_observations"] = reference_observations
    state["browser_qa_success"] = True
    state["browser_qa_passed"] = not blocking_findings
    state["browser_qa_report"] = report
    state["browser_qa_dir"] = str(qa_dir)
    state["browser_qa_findings"] = blocking_findings
    state["browser_qa_warnings"] = important_findings + [f"Reference note: {item}" for item in reference_warnings]
    state["browser_qa_health_score"] = health_score
    state["browser_qa_ship_readiness"] = ship_readiness
    state["browser_qa_mode"] = qa_mode
    state["browser_qa_report_only"] = report_only
    state["current_step"] = "browser_qa_done"
    state["error_message"] = None if not blocking_findings or report_only else "; ".join(blocking_findings)

    if mode_id == "design-review":
        if not state.get("before_screenshot_paths"):
            state["before_screenshot_paths"] = screenshot_refs
        else:
            state["after_screenshot_paths"] = screenshot_refs

    issues: list[Issue] = []
    if blocking_findings and not report_only:
        target_file = _primary_target_file(task_payload)
        for finding in blocking_findings:
            issue = Issue(
                issue_id=str(uuid.uuid4()),
                severity=IssueSeverity.BLOCKING,
                source_agent=AgentRole.BROWSER_QA,
                target_agent=AgentRole.FIXER,
                title="Browser QA blocking issue",
                description=finding,
                file_path=target_file,
                suggestion="Fix the browser-facing issue, then rerun Browser QA.",
            )
            add_issue(state, issue)
            issues.append(issue)

    task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.BROWSER_QA,
            to_agent=AgentRole.FIXER if issues else (AgentRole.QA_DESIGN_REVIEW if _should_enter_design_review(state) else AgentRole.SECURITY_SCANNER),
            status=HandoffStatus.BLOCKED if issues else HandoffStatus.COMPLETED,
            what_i_did=(
                "Used real Chromium captures across current and reference surfaces, then recorded screenshots, "
                "DOM snapshots, console logs, and structured browse observations."
            ),
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Browser QA Report",
                    type="report",
                    path=f".meta/{task_scope_name}/browser_qa/browser_qa_report.md",
                    description="Structured browser QA report with screenshots, observations, and risk summary.",
                    created_by=AgentRole.BROWSER_QA,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Browser Session Manifest",
                    type="report",
                    path=f".meta/{task_scope_name}/browser_runtime/session.json",
                    description="Persistent browser runtime session manifest and artifact index.",
                    created_by=AgentRole.BROWSER_QA,
                ),
            ],
            what_risks_i_found=blocking_findings or important_findings or reference_warnings,
            what_i_require_next=(
                "Fix blocking browser issues, then rerun Browser QA."
                if issues
                else "Continue into design review or the downstream QA chain with the recorded evidence."
            ),
            issues=issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print("[Browser QA Agent] Verification completed")
    return state


def route_after_browser_qa(state: DevState) -> str:
    if not state.get("browser_qa_success"):
        return "security_scanner"
    if (
        not state.get("browser_qa_passed")
        and (
            (not state.get("browser_qa_report_only") and state.get("fixer_allowed", True))
            or state.get("auto_upgrade_to_qa")
        )
        and state.get("fix_attempts", 0) < 3
    ):
        state["browser_qa_report_only"] = False
        state["fixer_allowed"] = True
        state["effective_qa_mode"] = "qa"
        state["browser_qa_mode"] = "quick"
        add_executed_mode(state, "qa")
        return "fixer"
    if str(state.get("stop_after") or "").strip() == "browser_qa":
        return "__end__"
    if _should_enter_design_review(state) and state.get("browser_qa_passed"):
        return "qa_design_review"
    return "security_scanner"


def _should_enter_design_review(state: DevState) -> bool:
    return bool(state.get("needs_qa_design_review")) or str(state.get("skill_mode") or "").strip() == "design-review"


def _extract_browser_targets(task_payload: dict[str, Any]) -> list[BrowserTarget]:
    reference_urls = _clean_urls(task_payload.get("reference_urls"))
    current_urls = _clean_urls(task_payload.get("browser_urls"))
    if not current_urls:
        current_urls = _clean_urls(task_payload.get("qa_urls"))
    if not current_urls:
        current_urls = _clean_urls(task_payload.get("preview_urls"))
    if not current_urls:
        current_urls = _clean_urls(task_payload.get("runtime_urls"))
    if not current_urls:
        preview_base = str(task_payload.get("preview_base_url") or "").strip()
        route = str(task_payload.get("preview_route") or "").strip()
        if preview_base and route:
            current_urls = [preview_base.rstrip("/") + "/" + route.lstrip("/")]

    browser_actions = task_payload.get("browser_actions")
    actions_by_url = _normalize_actions(browser_actions)
    targets: list[BrowserTarget] = []

    for index, url in enumerate(current_urls, start=1):
        targets.append(
            BrowserTarget(
                url=url,
                name=f"current-{index}-{_route_token(url)}",
                kind="current",
                actions=actions_by_url.get(url) or actions_by_url.get(_route_token(url)) or actions_by_url.get("*") or [],
            )
        )
    for index, url in enumerate(reference_urls, start=1):
        targets.append(
            BrowserTarget(
                url=url,
                name=f"reference-{index}-{_route_token(url)}",
                kind="reference",
                actions=actions_by_url.get(url) or actions_by_url.get(_route_token(url)) or actions_by_url.get("*") or [],
            )
        )
    return targets


def _clean_urls(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_actions(raw_actions: Any) -> dict[str, list[dict[str, Any]]]:
    if isinstance(raw_actions, list):
        return {"*": [item for item in raw_actions if isinstance(item, dict)]}
    if not isinstance(raw_actions, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for key, value in raw_actions.items():
        if isinstance(value, list):
            result[str(key).strip()] = [item for item in value if isinstance(item, dict)]
    return result


def _page_summary_lines(observations: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in observations:
        url = str(item.get("final_url") or item.get("url") or "").strip()
        title = str(item.get("title") or "(missing)").strip() or "(missing)"
        viewport_name = str(item.get("viewport_name") or "unknown").strip()
        card_count = int(item.get("card_count") or 0)
        search_present = "yes" if item.get("search_present") else "no"
        headings = ", ".join((item.get("headings") or [])[:2]) or "no headings"
        lines.append(
            f"{viewport_name} | {url} | title={title} | cards={card_count} | search={search_present} | headings={headings}"
        )
    return lines


def _collect_findings(observations: list[dict[str, Any]], key: str) -> list[str]:
    findings: list[str] = []
    for item in observations:
        for finding in item.get(key) or []:
            text = str(finding).strip()
            if text:
                findings.append(text)
    return findings


def _route_token(url: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    return path.replace("/", "-")


def _primary_target_file(task_payload: dict[str, Any]) -> str | None:
    for key in ("primary_files", "related_files"):
        value = task_payload.get(key)
        if isinstance(value, list):
            for item in value:
                candidate = str(item).strip()
                if candidate:
                    return candidate
    return None
