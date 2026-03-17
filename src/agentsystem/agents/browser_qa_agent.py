from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import requests

from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    Issue,
    IssueSeverity,
    add_handoff_packet,
    add_issue,
)
from agentsystem.runtime.browser_session_manager import BrowserSessionManager


def browser_qa_node(state: DevState) -> DevState:
    print("[Browser QA Agent] Running browser-facing verification")

    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    qa_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "browser_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    urls = _extract_browser_targets(task_payload)
    qa_mode = str(task_payload.get("browser_qa_mode") or task_payload.get("qa_mode") or "quick").strip() or "quick"
    report_only = bool(task_payload.get("browser_qa_report_only")) or str(qa_mode).lower() in {"report_only", "qa_only"}

    manager = BrowserSessionManager(repo_b_path, str(state.get("task_id") or repo_b_path.name))
    snapshot = manager.ensure_session(target_url=urls[0] if urls else None)

    blocking_findings: list[str] = []
    important_findings: list[str] = []
    probe_refs: list[str] = []
    screenshot_refs: list[str] = []
    page_summaries: list[str] = []

    if not urls:
        important_findings.append("No browser targets were configured, so Browser QA only verified runtime scaffolding.")
    else:
        for index, url in enumerate(urls, start=1):
            probe = _probe_url(url)
            probe_refs.append(manager.record_probe(f"page-{index}", probe))
            screenshot_refs.append(
                manager.write_placeholder_screenshot(
                    f"page-{index}",
                    "\n".join(
                        [
                            f"URL: {url}",
                            f"Status: {probe['status_code']}",
                            f"Title: {probe['title'] or '(missing)'}",
                            f"Outcome: {'blocking' if probe['blocking_findings'] else 'ok'}",
                        ]
                    ),
                )
            )
            page_summaries.append(
                f"{url} -> status {probe['status_code']}, title={probe['title'] or '(missing)'}"
            )
            blocking_findings.extend(str(item) for item in probe["blocking_findings"])
            important_findings.extend(str(item) for item in probe["important_findings"])

    health_score = max(0, 100 - len(blocking_findings) * 35 - len(important_findings) * 10)
    ship_readiness = "ready" if not blocking_findings else "needs_fix"
    if report_only and blocking_findings:
        ship_readiness = "report_only_attention"

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
        "",
        "## Page Summary",
    ]
    report_lines.extend([f"- {item}" for item in page_summaries] or ["- No target URLs were configured."])
    report_lines.extend(["", "## Blocking Findings"])
    report_lines.extend([f"- {item}" for item in blocking_findings] or ["- None."])
    report_lines.extend(["", "## Important Findings"])
    report_lines.extend([f"- {item}" for item in important_findings] or ["- None."])
    report_lines.extend(["", "## Evidence"])
    report_lines.extend([f"- Probe: {item}" for item in probe_refs] or ["- No probe artifacts recorded."])
    report_lines.extend([f"- Screenshot placeholder: {item}" for item in screenshot_refs])
    report = "\n".join(report_lines).strip() + "\n"
    report_path = qa_dir / "browser_qa_report.md"
    report_path.write_text(report, encoding="utf-8")

    state["browser_runtime_dir"] = str(manager.runtime_dir)
    state["browser_session_id"] = snapshot.session_id
    state["browser_qa_success"] = True
    state["browser_qa_passed"] = not blocking_findings
    state["browser_qa_report"] = report
    state["browser_qa_dir"] = str(qa_dir)
    state["browser_qa_findings"] = blocking_findings
    state["browser_qa_warnings"] = important_findings
    state["browser_qa_health_score"] = health_score
    state["browser_qa_ship_readiness"] = ship_readiness
    state["browser_qa_mode"] = qa_mode
    state["browser_qa_report_only"] = report_only
    state["current_step"] = "browser_qa_done"
    state["error_message"] = None if not blocking_findings or report_only else "; ".join(blocking_findings)

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
                suggestion="Fix the runtime/browser regression and re-run Browser QA.",
            )
            add_issue(state, issue)
            issues.append(issue)

    task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.BROWSER_QA,
            to_agent=AgentRole.FIXER if issues else AgentRole.SECURITY_SCANNER,
            status=HandoffStatus.BLOCKED if issues else HandoffStatus.COMPLETED,
            what_i_did="Probed configured browser targets, captured lightweight page evidence, and scored ship-readiness.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Browser QA Report",
                    type="report",
                    path=f".meta/{task_scope_name}/browser_qa/browser_qa_report.md",
                    description="Runtime-facing verification summary with health score and findings.",
                    created_by=AgentRole.BROWSER_QA,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Browser Session Manifest",
                    type="report",
                    path=f".meta/{task_scope_name}/browser_runtime/session.json",
                    description="File-backed browser session state for reuse across QA passes.",
                    created_by=AgentRole.BROWSER_QA,
                ),
            ],
            what_risks_i_found=blocking_findings or important_findings,
            what_i_require_next=(
                "Resolve every blocking browser issue, then send the story back through Browser QA."
                if issues
                else "Continue the verification chain with security and review checks."
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
        and not state.get("browser_qa_report_only")
        and state.get("fixer_allowed", True)
        and state.get("fix_attempts", 0) < 2
    ):
        return "fixer"
    if str(state.get("stop_after") or "").strip() == "browser_qa":
        return "__end__"
    return "security_scanner"


def _extract_browser_targets(task_payload: dict[str, Any]) -> list[str]:
    for key in ("browser_urls", "qa_urls", "preview_urls", "runtime_urls"):
        value = task_payload.get(key)
        if isinstance(value, list):
            targets = [str(item).strip() for item in value if str(item).strip()]
            if targets:
                return targets
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    preview_base = str(task_payload.get("preview_base_url") or "").strip()
    route = str(task_payload.get("preview_route") or "").strip()
    if preview_base and route:
        return [preview_base.rstrip("/") + "/" + route.lstrip("/")]
    return []


def _probe_url(url: str) -> dict[str, Any]:
    session = requests.Session()
    session.trust_env = False
    blocking_findings: list[str] = []
    important_findings: list[str] = []
    status_code = 0
    title = ""
    content_type = ""
    excerpt = ""

    try:
        response = session.get(url, timeout=15)
        status_code = response.status_code
        content_type = response.headers.get("content-type", "")
        body = response.text[:4000]
        excerpt = body[:400]
        title = _extract_title(body)

        if status_code >= 400:
            blocking_findings.append(f"{url} returned HTTP {status_code}.")
        if any(token in body.lower() for token in ("traceback", "unhandled exception", "something went wrong")):
            blocking_findings.append(f"{url} exposes an application error signature in the response body.")
        if "text/html" in content_type.lower() and not title:
            important_findings.append(f"{url} did not expose a HTML <title> tag.")
    except requests.RequestException as exc:
        blocking_findings.append(f"{url} could not be reached: {exc}")
        excerpt = str(exc)

    return {
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "title": title,
        "excerpt": excerpt,
        "blocking_findings": blocking_findings,
        "important_findings": important_findings,
    }


def _extract_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _primary_target_file(task_payload: dict[str, Any]) -> str | None:
    for key in ("primary_files", "related_files"):
        value = task_payload.get(key)
        if isinstance(value, list):
            for item in value:
                candidate = str(item).strip()
                if candidate:
                    return candidate
    return None
