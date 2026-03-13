from __future__ import annotations

import re
import uuid
from pathlib import Path

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


def acceptance_gate_node(state: DevState) -> DevState:
    _safe_print("[Acceptance Gate] Evaluating acceptance criteria")

    task_payload = state.get("task_payload") or {}
    acceptance_items = [str(item).strip() for item in task_payload.get("acceptance_criteria", []) if str(item).strip()]
    related_files = [str(item).strip() for item in task_payload.get("related_files", []) if str(item).strip()]
    repo_b_path = Path(state["repo_b_path"]).resolve()
    report_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "acceptance"
    report_dir.mkdir(parents=True, exist_ok=True)

    changed_files = _collect_changed_files(state)
    checklist_lines: list[str] = []
    blocking_issues: list[str] = list(state.get("blocking_issues") or [])

    for criterion in acceptance_items:
        satisfied, detail = _evaluate_criterion(criterion, task_payload, related_files, changed_files, repo_b_path, state)
        checklist_lines.append(f"- {'[x]' if satisfied else '[ ]'} {criterion} - {detail}")
        if not satisfied:
            blocking_issues.append(f"Acceptance unmet: {criterion}")

    if related_files and changed_files:
        allowed = {path.replace("\\", "/") for path in related_files}
        unexpected = [path for path in changed_files if path.replace("\\", "/") not in allowed]
        if unexpected:
            blocking_issues.append(f"Changes exceed task scope: {', '.join(unexpected)}")

    if not state.get("review_passed"):
        blocking_issues.append("Reviewer did not pass the change set.")
    if not state.get("code_acceptance_passed"):
        blocking_issues.append("Code acceptance did not pass the change set.")

    report_lines = [
        "# Acceptance Gate Report",
        "",
        "## Checklist",
        *(checklist_lines or ["- No acceptance criteria defined."]),
        "",
        "## Scope Check",
        f"- Changed files: {', '.join(changed_files) if changed_files else 'None recorded'}",
        f"- Related files: {', '.join(related_files) if related_files else 'None recorded'}",
        "",
        "## Review Gates",
        f"- Reviewer passed: {'yes' if state.get('review_passed') else 'no'}",
        f"- Code acceptance passed: {'yes' if state.get('code_acceptance_passed') else 'no'}",
        "",
        "## Verdict",
        "- [x] Acceptance passed" if not blocking_issues else "- [ ] Acceptance failed",
    ]

    report = "\n".join(report_lines).strip() + "\n"
    (report_dir / "acceptance_report.md").write_text(report, encoding="utf-8")

    state["acceptance_report"] = report
    state["acceptance_passed"] = not blocking_issues
    state["acceptance_success"] = True
    state["acceptance_dir"] = str(report_dir)
    state["blocking_issues"] = blocking_issues
    state["current_step"] = "acceptance_done"
    issues: list[Issue] = []
    for item in blocking_issues:
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.BLOCKING,
            source_agent=AgentRole.ACCEPTANCE_GATE,
            target_agent=AgentRole.FIXER,
            title="Acceptance gate blocking issue",
            description=str(item),
            suggestion="Resolve the failed acceptance item or scope violation and return the story for validation.",
        )
        if not state.get("acceptance_passed"):
            add_issue(state, issue)
        issues.append(issue)
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.ACCEPTANCE_GATE,
            to_agent=AgentRole.DOC_WRITER if state.get("acceptance_passed") else AgentRole.FIXER,
            status=HandoffStatus.COMPLETED if state.get("acceptance_passed") else HandoffStatus.BLOCKED,
            what_i_did="Cross-checked acceptance criteria, task scope, reviewer status, and code acceptance status for the story.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Acceptance Gate Report",
                    type="report",
                    path=str(report_dir / "acceptance_report.md"),
                    description="Final acceptance checklist and scope-verification report.",
                    created_by=AgentRole.ACCEPTANCE_GATE,
                )
            ],
            what_risks_i_found=[str(item) for item in blocking_issues],
            what_i_require_next="If accepted, generate the delivery report. If blocked, fix the outstanding acceptance issues before trying again.",
            issues=issues if not state.get("acceptance_passed") else [],
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    for line in report.splitlines():
        if line.strip():
            _safe_print(f"[Acceptance Gate] {line}")

    return state


def route_after_acceptance(state: DevState) -> str:
    return "doc_writer" if state.get("acceptance_passed") else "fixer"


def _collect_changed_files(state: DevState) -> list[str]:
    changed: list[str] = []
    dev_results = state.get("dev_results") or {}
    for payload in dev_results.values():
        if not isinstance(payload, dict):
            continue
        for item in payload.get("updated_files", []):
            normalized = str(item).replace("\\", "/")
            if "/apps/" in normalized:
                normalized = "apps/" + normalized.split("/apps/", 1)[1]
            elif "/docs/" in normalized:
                normalized = "docs/" + normalized.split("/docs/", 1)[1]
            elif "/scripts/" in normalized:
                normalized = "scripts/" + normalized.split("/scripts/", 1)[1]
            changed.append(normalized)
    if not changed:
        changed.extend(str(item) for item in (state.get("staged_files") or []))
    unique: list[str] = []
    seen: set[str] = set()
    for item in changed:
        normalized = item.replace("\\", "/")
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _evaluate_criterion(
    criterion: str,
    task_payload: dict[str, object],
    related_files: list[str],
    changed_files: list[str],
    repo_b_path: Path,
    state: DevState,
) -> tuple[bool, str]:
    lowered = criterion.lower()
    if "subtitle" in lowered or "副标题" in criterion:
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=True)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text and target_text in content:
                    return True, f"Found subtitle '{target_text}' in {raw_path}"
                if not target_text and ("text-slate-500" in content or "<p" in content):
                    return True, f"Subtitle markup found in {raw_path}"
        return False, "Subtitle content not found"
    if "title" in lowered or "标题" in criterion:
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=False)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text and target_text in content:
                    return True, f"Found title '{target_text}' in {raw_path}"
                if not target_text and "<h1" in content:
                    return True, f"Heading found in {raw_path}"
        return False, "Heading content not found"
    if "schema" in lowered:
        for raw_path in related_files:
            if not raw_path.endswith(".json"):
                continue
            candidate = repo_b_path / raw_path
            if candidate.exists():
                return True, f"Schema artifact exists: {raw_path}"
        return False, "Schema artifact not found"
    if "prettier" in lowered or "格式化" in criterion:
        report = str(state.get("test_results") or "")
        if "FAIL" in report.upper():
            return False, "Validation report still contains failing checks"
        return True, "Validation report has no failing formatting checks"
    if "只修改" in criterion or "only modify" in lowered:
        allowed = {path.replace("\\", "/") for path in related_files}
        unexpected = [path for path in changed_files if path.replace("\\", "/") not in allowed]
        if unexpected:
            return False, f"Unexpected files changed: {', '.join(unexpected)}"
        return True, "Changed files stayed within declared scope"
    return True, "No deterministic rule required for this criterion"


def _infer_target_text(goal: str, *, subtitle: bool) -> str | None:
    quote_match = re.search(r"[\"'“”‘’「」『』](.*?)[\"'“”‘’「」『』]", goal)
    if quote_match:
        return quote_match.group(1).strip()

    patterns = (
        [r"加(?:一个)?副标题[:：]?\s*(.+)$", r"subtitle[:：]?\s*(.+)$"]
        if subtitle
        else [r"加(?:一个)?标题[:：]?\s*(.+)$", r"title[:：]?\s*(.+)$"]
    )
    cleaned = goal.strip(" ，。：:!?\"'“”‘’「」『』")
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(" ，。：:!?\"'“”‘’「」『』")
    return None


def _safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass
