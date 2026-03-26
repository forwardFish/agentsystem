from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

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
from agentsystem.orchestration.quality_sentry import evaluate_quality_sentry_for_state


class CodeAcceptanceAgent:
    def __init__(self, worktree_path: str | Path):
        self.worktree_path = Path(worktree_path).resolve()
        self.report_dir = self.worktree_path.parent / ".meta" / self.worktree_path.name / "code_acceptance"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, state: DevState) -> dict[str, object]:
        changed_files = _collect_changed_files(state)
        blocking_issues: list[str] = []
        notes: list[str] = []
        quality = evaluate_quality_sentry_for_state(state, self.worktree_path, changed_files=changed_files)
        blocking_issues.extend(_format_quality_issues(quality))

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

            line_issues = _check_line_hygiene(relative_path, content)
            blocking_issues.extend(line_issues)

            suffix = file_path.suffix.lower()
            if suffix == ".json":
                try:
                    json.loads(content)
                    notes.append(f"{relative_path}: valid JSON")
                except Exception as exc:
                    blocking_issues.append(f"{relative_path}: invalid JSON ({exc})")
            elif suffix in {".md", ".yaml", ".yml", ".py", ".ts", ".tsx", ".js", ".jsx", ".sql"}:
                notes.append(f"{relative_path}: style hygiene checked")

        report = _build_report(changed_files, blocking_issues, notes)
        (self.report_dir / "code_acceptance_report.md").write_text(report, encoding="utf-8")
        return {
            "code_acceptance_success": True,
            "code_acceptance_passed": not blocking_issues,
            "code_acceptance_report": report,
            "code_acceptance_dir": str(self.report_dir),
            "code_acceptance_issues": blocking_issues,
        }


def code_acceptance_node(state: DevState) -> DevState:
    agent = CodeAcceptanceAgent(state["repo_b_path"])
    result = agent.run(state)
    state.update(result)
    state["current_step"] = "code_acceptance_done"
    issues: list[Issue] = []
    for raw_issue in state.get("code_acceptance_issues") or []:
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.BLOCKING,
            source_agent=AgentRole.CODE_ACCEPTANCE,
            target_agent=AgentRole.FIXER,
            title="Code acceptance issue",
            description=str(raw_issue),
            suggestion="Apply the reported code hygiene fix and rerun code acceptance.",
        )
        add_issue(state, issue)
        issues.append(issue)
    # Build risk list with context
    risks: list[str] = []
    blocking_issues = state.get("code_acceptance_issues") or []
    if blocking_issues:
        risks.extend(str(item) for item in blocking_issues[:5])  # Limit to top 5
    else:
        # Even if passed, note potential risks
        changed_files = _collect_changed_files(state)
        if len(changed_files) > 20:
            risks.append(f"Large change set ({len(changed_files)} files) increases merge conflict risk.")
        json_files = [f for f in changed_files if f.endswith('.json')]
        if json_files:
            risks.append(f"Modified {len(json_files)} JSON config file(s); runtime validation recommended.")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.CODE_ACCEPTANCE,
            to_agent=AgentRole.ACCEPTANCE_GATE if state.get("code_acceptance_passed") else AgentRole.FIXER,
            status=HandoffStatus.COMPLETED if state.get("code_acceptance_passed") else HandoffStatus.BLOCKED,
            what_i_did="Verified UTF-8 encoding, whitespace hygiene, and JSON parseability across all changed files before final acceptance gate.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Code Acceptance Report",
                    type="report",
                    path=str(Path(str(state.get('code_acceptance_dir') or '')) / 'code_acceptance_report.md'),
                    description="Final code hygiene report confirming delivery readiness for the current story.",
                    created_by=AgentRole.CODE_ACCEPTANCE,
                )
            ],
            what_risks_i_found=risks,
            what_i_require_next=(
                "Proceed to final acceptance gate and verify all story criteria are satisfied."
                if state.get("code_acceptance_passed")
                else "Fix the reported hygiene issues, then return for another code acceptance pass before final gate."
            ),
            issues=issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_code_acceptance(state: DevState) -> str:
    return "acceptance_gate" if state.get("code_acceptance_passed") else "fixer"


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
        normalized.startswith("tasks/runtime/")
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


def _build_report(changed_files: list[str], blocking_issues: list[str], notes: list[str]) -> str:
    lines = ["# Code Acceptance Report", "", "## Scope"]
    if changed_files:
        lines.extend(f"- {path}" for path in changed_files)
    else:
        lines.append("- No changed files recorded.")
    lines.extend(
        [
            "",
            "## Style Consistency",
            "- Checked UTF-8 readability, tab usage, trailing spaces, and JSON parseability where applicable.",
            "",
            "## Findings",
        ]
    )
    if blocking_issues:
        lines.append("### Blocking")
        lines.extend(f"- {item}" for item in blocking_issues)
    else:
        lines.extend(["### Blocking", "- None."])
    lines.extend(["", "### Notes"])
    if notes:
        lines.extend(f"- {item}" for item in notes)
    else:
        lines.append("- No additional notes.")
    lines.extend(
        [
            "",
            "## Verdict",
            "- [x] Code acceptance passed" if not blocking_issues else "- [ ] Code acceptance failed",
            "",
        ]
    )
    return "\n".join(lines)


def _format_quality_issues(quality: dict[str, object]) -> list[str]:
    issues = quality.get("issues") if isinstance(quality.get("issues"), list) else []
    return [
        f"{item.get('file') or 'story'}: {item.get('issue_type')}: {item.get('detail')}"
        for item in issues
        if isinstance(item, dict)
    ]
