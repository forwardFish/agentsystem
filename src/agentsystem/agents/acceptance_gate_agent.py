from __future__ import annotations

import re
from pathlib import Path

from agentsystem.core.state import DevState


def acceptance_gate_node(state: DevState) -> DevState:
    _safe_print("[Acceptance Gate] Evaluating acceptance criteria")

    task_payload = state.get("task_payload") or {}
    acceptance_items = [str(item).strip() for item in task_payload.get("acceptance_criteria", []) if str(item).strip()]
    related_files = [str(item).strip() for item in task_payload.get("related_files", []) if str(item).strip()]
    repo_b_path = Path(state["repo_b_path"]).resolve()

    changed_files = _collect_changed_files(state)
    criteria_results: list[str] = []
    blocking_issues: list[str] = list(state.get("blocking_issues") or [])

    for criterion in acceptance_items:
        satisfied, detail = _evaluate_criterion(criterion, task_payload, related_files, changed_files, repo_b_path, state)
        status = "已满足" if satisfied else "未满足"
        criteria_results.append(f"- {criterion}: {status} ({detail})")
        if not satisfied:
            blocking_issues.append(f"Acceptance unmet: {criterion}")

    if related_files and changed_files:
        allowed = {path.replace("\\", "/") for path in related_files}
        unexpected = [path for path in changed_files if path.replace("\\", "/") not in allowed]
        if unexpected:
            blocking_issues.append(f"Changes exceed task scope: {', '.join(unexpected)}")

    review_passed = bool(state.get("review_passed"))
    if not review_passed:
        blocking_issues.append("Reviewer did not pass the change set.")

    report_lines = [
        "# Acceptance Gate Report",
        "",
        "## Checklist",
        "\n".join(criteria_results) if criteria_results else "- No acceptance criteria defined.",
        "",
        "## Scope Check",
        f"- Changed files: {', '.join(changed_files) if changed_files else 'None recorded'}",
        f"- Related files: {', '.join(related_files) if related_files else 'None recorded'}",
        "",
        "## Verdict",
        "- [x] Acceptance passed" if not blocking_issues else "- [ ] Acceptance failed",
    ]

    state["acceptance_report"] = "\n".join(report_lines).strip() + "\n"
    state["acceptance_passed"] = not blocking_issues
    state["acceptance_success"] = True
    state["blocking_issues"] = blocking_issues
    state["current_step"] = "acceptance_done"

    for line in state["acceptance_report"].splitlines():
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
                normalized = normalized.split("/apps/", 1)[1]
                normalized = f"apps/{normalized}"
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
    if "副标题" in criterion or "subtitle" in lowered:
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=True)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text:
                    if target_text in content:
                        return True, f"Found subtitle '{target_text}' in {raw_path}"
                elif "text-slate-500" in content or "<p" in content:
                    return True, f"Subtitle markup found in {raw_path}"
        return False, "Subtitle content not found"
    if "标题" in criterion or re.search(r"\btitle\b", lowered):
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=False)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text:
                    if target_text in content:
                        return True, f"Found title '{target_text}' in {raw_path}"
                elif "<h1" in content:
                    return True, f"Heading found in {raw_path}"
        return False, "Heading content not found"
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

    if subtitle:
        patterns = [
            r"加(?:一个|个)?副标题[:：]?\s*(.+)$",
            r"添加(?:一个|个)?副标题[:：]?\s*(.+)$",
            r"副标题(?:为|是)?[:：]?\s*(.+)$",
            r"add\s+(?:a\s+)?subtitle[:：]?\s*(.+)$",
        ]
    else:
        patterns = [
            r"加(?:一个|个)?标题[:：]?\s*(.+)$",
            r"添加(?:一个|个)?标题[:：]?\s*(.+)$",
            r"标题(?:为|是)?[:：]?\s*(.+)$",
            r"add\s+(?:a\s+)?title[:：]?\s*(.+)$",
        ]

    cleaned = goal.strip(" ，。：；!?\"'“”‘’「」『』")
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(" ，。：；!?\"'“”‘’「」『』")
    return None


def _safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass
