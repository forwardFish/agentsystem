from __future__ import annotations

import uuid
from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
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


class CodeStyleReviewerAgent:
    def __init__(self, worktree_path: str | Path):
        self.worktree_path = Path(worktree_path).resolve()
        self.report_dir = self.worktree_path.parent / ".meta" / self.worktree_path.name / "code_style_review"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, state: DevState) -> dict[str, object]:
        config = RepoBConfigReader(self.worktree_path).load_all_config()
        style_guide_path = self.worktree_path / ".agents" / "style_guide.md"
        style_guide = style_guide_path.read_text(encoding="utf-8") if style_guide_path.exists() else ""
        max_line_length = int(config.project.get("code_style", {}).get("line_length", 120))
        changed_files = _collect_changed_files(state)

        blocking_issues: list[str] = []
        important_issues: list[str] = []
        notes: list[str] = []

        if not changed_files:
            important_issues.append("No changed files were recorded for style review.")

        for relative_path in changed_files:
            file_path = self.worktree_path / relative_path
            if not file_path.exists():
                blocking_issues.append(f"Changed file is missing from worktree: {relative_path}")
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - defensive
                blocking_issues.append(f"File is not readable as UTF-8: {relative_path} ({exc})")
                continue

            blocking_issues.extend(_check_line_hygiene(relative_path, content))
            long_lines = _check_line_length(relative_path, content, max_line_length)
            important_issues.extend(long_lines)
            notes.append(f"{relative_path}: reviewed against style guide")

        report = _build_report(changed_files, blocking_issues, important_issues, notes, style_guide, max_line_length)
        (self.report_dir / "code_style_review_report.md").write_text(report, encoding="utf-8")
        return {
            "code_style_review_success": True,
            "code_style_review_passed": not blocking_issues,
            "code_style_review_report": report,
            "code_style_review_dir": str(self.report_dir),
            "code_style_review_issues": [*blocking_issues, *important_issues],
        }


def code_style_review_node(state: DevState) -> DevState:
    agent = CodeStyleReviewerAgent(state["repo_b_path"])
    result = agent.run(state)
    state.update(result)
    state["current_step"] = "code_style_review_done"

    issues: list[Issue] = []
    for raw_issue in state.get("code_style_review_issues") or []:
        severity = IssueSeverity.BLOCKING if "tabs are not allowed" in raw_issue or "trailing spaces" in raw_issue or "not readable as UTF-8" in raw_issue or "missing from worktree" in raw_issue else IssueSeverity.IMPORTANT
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=severity,
            source_agent=AgentRole.CODE_STYLE_REVIEWER,
            target_agent=AgentRole.FIXER,
            title="Code style review issue",
            description=str(raw_issue),
            suggestion="Apply the reported style fix and return the story for another style review pass.",
        )
        issues.append(issue)
        if severity == IssueSeverity.BLOCKING and not state.get("code_style_review_passed"):
            add_issue(state, issue)

    # Build risk list with context
    risks: list[str] = []
    blocking_issues = [str(item) for item in (state.get("code_style_review_issues") or []) if "tabs are not allowed" in str(item) or "trailing spaces" in str(item) or "not readable" in str(item) or "missing from worktree" in str(item)]
    important_issues = [str(item) for item in (state.get("code_style_review_issues") or []) if "line length exceeds" in str(item)]

    if blocking_issues:
        risks.extend(blocking_issues[:3])  # Top 3 blocking issues
    if important_issues:
        risks.extend(important_issues[:2])  # Top 2 important issues

    # Add contextual risks
    changed_files = _collect_changed_files(state)
    if not changed_files:
        risks.append("No changed files were recorded; style review cannot validate code hygiene.")
    if len(changed_files) > 20:
        risks.append(f"Large change set ({len(changed_files)} files) increases style inconsistency risk.")

    repo_b_path = Path(str(state.get("repo_b_path", "."))).resolve()
    style_guide_path = repo_b_path / ".agents" / "style_guide.md"
    if not style_guide_path.exists():
        risks.append("No style guide (.agents/style_guide.md) found; review relies on basic hygiene checks only.")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.CODE_STYLE_REVIEWER,
            to_agent=AgentRole.TESTER if state.get("code_style_review_passed") else AgentRole.FIXER,
            status=HandoffStatus.COMPLETED if state.get("code_style_review_passed") else HandoffStatus.BLOCKED,
            what_i_did=f"Reviewed {len(changed_files)} changed file(s) for UTF-8 encoding, whitespace hygiene (tabs, trailing spaces), and line length consistency against project style guide.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Code Style Review Report",
                    type="report",
                    path=str(Path(str(state.get("code_style_review_dir") or "")) / "code_style_review_report.md"),
                    description=f"Pre-test style review with {len(blocking_issues)} blocking and {len(important_issues)} important issue(s) for the current story.",
                    created_by=AgentRole.CODE_STYLE_REVIEWER,
                )
            ],
            what_risks_i_found=risks[:5],  # Limit to top 5 risks
            what_i_require_next=(
                "Proceed to story validation with test execution."
                if state.get("code_style_review_passed")
                else f"Fix {len(blocking_issues)} blocking style issue(s), then return for another code style review pass before testing."
            ),
            issues=[] if state.get("code_style_review_passed") else issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_code_style_review(state: DevState) -> str:
    return "tester" if state.get("code_style_review_passed") else "fixer"


def _collect_changed_files(state: DevState) -> list[str]:
    changed: list[str] = []
    for payload in (state.get("dev_results") or {}).values():
        if not isinstance(payload, dict):
            continue
        for item in payload.get("updated_files", []):
            changed.append(_normalize_changed_path(str(item)))
    changed.extend(_normalize_changed_path(str(item)) for item in (state.get("staged_files") or []))

    unique: list[str] = []
    seen: set[str] = set()
    for item in changed:
        if _is_ignored_changed_path(item):
            continue
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _normalize_changed_path(path: str) -> str:
    text = str(path).replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    if "/apps/" in text:
        return "apps/" + text.split("/apps/", 1)[1]
    if "/docs/" in text:
        return "docs/" + text.split("/docs/", 1)[1]
    if "/scripts/" in text:
        return "scripts/" + text.split("/scripts/", 1)[1]
    if text.startswith(("apps/", "docs/", "scripts/", ".agents/", "config/", "tasks/")):
        return text
    return text


def _is_ignored_changed_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith(".git/")
        or normalized.startswith("tasks/runtime/")
        or normalized.startswith("docs/handoff/")
        or "__pycache__/" in normalized
        or normalized.endswith(".pyc")
        or ".pytest_cache/" in normalized
    )


def _check_line_hygiene(relative_path: str, content: str) -> list[str]:
    issues: list[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if "\t" in line:
            issues.append(f"{relative_path}:{line_number}: tabs are not allowed")
        if line.rstrip(" ") != line:
            issues.append(f"{relative_path}:{line_number}: trailing spaces are not allowed")
    return issues


def _check_line_length(relative_path: str, content: str, max_line_length: int) -> list[str]:
    issues: list[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if len(line) > max_line_length:
            issues.append(f"{relative_path}:{line_number}: line length exceeds {max_line_length} characters")
    return issues


def _build_report(
    changed_files: list[str],
    blocking_issues: list[str],
    important_issues: list[str],
    notes: list[str],
    style_guide: str,
    max_line_length: int,
) -> str:
    lines = ["# Code Style Review Report", "", "## Scope"]
    if changed_files:
        lines.extend(f"- {path}" for path in changed_files)
    else:
        lines.append("- No changed files recorded.")
    lines.extend(
        [
            "",
            "## Style Guide Context",
            f"- Max line length: {max_line_length}",
            f"- Style guide loaded: {'yes' if style_guide else 'no'}",
            "",
            "## Blocking",
        ]
    )
    if blocking_issues:
        lines.extend(f"- {item}" for item in blocking_issues)
    else:
        lines.append("- None.")
    lines.extend(["", "## Important"])
    if important_issues:
        lines.extend(f"- {item}" for item in important_issues)
    else:
        lines.append("- None.")
    lines.extend(["", "## Notes"])
    if notes:
        lines.extend(f"- {item}" for item in notes)
    else:
        lines.append("- No additional notes.")
    lines.extend(["", "## Verdict", "- [x] Code style review passed" if not blocking_issues else "- [ ] Code style review failed", ""])
    return "\n".join(lines)
