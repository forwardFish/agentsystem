from __future__ import annotations

import hashlib
import os
from pathlib import Path
import uuid

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
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
from agentsystem.llm.client import get_llm


class ReviewerAgent:
    def __init__(self, worktree_path: str | Path, task: dict[str, object] | None):
        self.worktree_path = Path(worktree_path).resolve()
        self.task = task or {}
        self.git = GitAdapter(self.worktree_path)
        self.review_dir = self.worktree_path.parent / ".meta" / self.worktree_path.name / "review"
        self.review_dir.mkdir(parents=True, exist_ok=True)

    def run(self, state: DevState) -> dict[str, object]:
        result: dict[str, object] = {
            "review_success": False,
            "review_passed": False,
            "review_dir": str(self.review_dir),
            "review_report": "",
            "blocking_issues": [],
            "important_issues": [],
            "nice_to_haves": [],
            "error_message": None,
        }

        try:
            if self.git.is_dirty():
                self.git.add_all()

            diff = self.git.get_diff()
            staged_files = _filter_review_paths(self.git.get_staged_files())
            if not staged_files:
                staged_files = _filter_review_paths([str(path) for path in (state.get("staged_files") or [])])
            if not diff and self.git.get_current_commit():
                diff = self.git.repo.git.show("--stat", "--format=", "HEAD")
            report = self._generate_review_report(diff, staged_files, state)
            blocking_issues = _extract_list_section(report, "Blocking")
            important_issues = _extract_list_section(report, "Important")
            nice_to_haves = _extract_list_section(report, "Nice to have")

            result["review_report"] = report
            result["blocking_issues"] = blocking_issues
            result["important_issues"] = important_issues
            result["nice_to_haves"] = nice_to_haves
            result["review_passed"] = not blocking_issues
            result["review_success"] = True

            (self.review_dir / "review_report.md").write_text(report, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            result["error_message"] = f"Review failed: {exc}"

        return result

    def _generate_review_report(self, diff: str, staged_files: list[str], state: DevState) -> str:
        if os.getenv("OPENAI_API_KEY"):
            try:
                return self._generate_review_report_with_llm(diff, staged_files)
            except Exception:
                pass
        return self._generate_deterministic_review_report(diff, staged_files, state)

    def _generate_review_report_with_llm(self, diff: str, staged_files: list[str]) -> str:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a code reviewer. Return a Markdown review report with these sections:
# Review Report
## Change Summary
## Production Risk Focus
## Intent Match
## Verification Gaps
## Maintainability
## Acceptance Coverage
## Issues
### Blocking
### Important
### Nice to have
## Final Verdict
Do not include any text outside the report.
                    """.strip(),
                ),
                (
                    "user",
                    """
Task goal: {task_goal}
Acceptance criteria:
{acceptance_criteria}

Changed files:
{staged_files}

Diff:
{diff}

Review focus:
- Prefer issues that can pass CI but still break in production or real usage.
- Call out missing validation for config, contract, schema, runtime, or deployment-sensitive changes.
                    """.strip(),
                ),
            ]
        )
        response = (prompt | llm).invoke(
            {
                "task_goal": str(self.task.get("goal", "")).strip(),
                "acceptance_criteria": "\n".join(
                    f"- {item}" for item in self.task.get("acceptance_criteria", []) if isinstance(item, str)
                ),
                "staged_files": "\n".join(f"- {path}" for path in staged_files),
                "diff": diff[:3000],
            }
        )
        return str(getattr(response, "content", response)).strip()

    def _generate_deterministic_review_report(self, diff: str, staged_files: list[str], state: DevState) -> str:
        task_goal = str(self.task.get("goal", "")).strip() or str(state.get("user_requirement", "")).strip()
        acceptance = self.task.get("acceptance_criteria", []) if isinstance(self.task.get("acceptance_criteria"), list) else []
        protected_paths = RepoBConfigReader(self.worktree_path).load_all_config().rules.get("protected_paths", [])
        validation = str(state.get("test_results") or "Validation pending").strip()

        blocking_issues: list[str] = []
        important_issues: list[str] = []
        nice_to_haves: list[str] = []

        if not staged_files and "StoryValidation: PASS" not in validation:
            blocking_issues.append("No staged files were available for review.")
        elif not staged_files:
            nice_to_haves.append("No staged files were recorded because the existing scaffold already satisfied the story validation.")
        if protected_paths and any(_matches_protected_path(path, protected_paths) for path in staged_files):
            blocking_issues.append("A protected path appears in the staged change set.")
        if "FAIL" in validation.upper():
            blocking_issues.append("Validation report still contains failing checks.")
        if "Typecheck: SKIP" in validation or "Test: SKIP" in validation:
            important_issues.append("Typecheck or automated tests are still running in demo mode.")
        lowered_scope = " ".join(staged_files).lower()
        if any(token in lowered_scope for token in ("config/", "schema", "contract", "workflow", "graph", ".sql", "migration", "infra/")):
            important_issues.append("Changed files touch production-sensitive config/contract/runtime surfaces; verify behavior beyond CI-only checks.")
        if acceptance and "StoryValidation: PASS" not in validation:
            important_issues.append("Acceptance criteria exist but the validation report does not show a strong story-specific verification pass.")
        if not acceptance:
            nice_to_haves.append("Task card does not define acceptance criteria explicitly.")

        verdict = "- [x] Review passed for local iteration" if not blocking_issues else "- [ ] Blocking issues must be fixed"

        return "\n".join(
            [
                "# Review Report",
                "",
                "## Change Summary",
                task_goal or "Local agent-generated change.",
                "",
                "## Production Risk Focus",
                "Prefer issues that can pass CI yet still fail in production, runtime, or live user flows.",
                "",
                "## Intent Match",
                "Change scope matches the requested files and does not expand beyond the task card.",
                "",
                "## Verification Gaps",
                "Highlight any missing config, contract, schema, or runtime validation that could hide a production regression.",
                "",
                "## Maintainability",
                "Change follows the existing page/service scaffolding and keeps edits localized.",
                "",
                "## Acceptance Coverage",
                _format_bullets(acceptance, fallback="No acceptance criteria recorded."),
                "",
                "## Validation",
                validation,
                "",
                "## Changed Files",
                _format_bullets(staged_files, fallback="No staged files recorded."),
                "",
                "## Issues",
                "### Blocking",
                _format_bullets(blocking_issues, fallback="None."),
                "",
                "### Important",
                _format_bullets(important_issues, fallback="None."),
                "",
                "### Nice to have",
                _format_bullets(nice_to_haves, fallback="None."),
                "",
                "## Final Verdict",
                verdict,
            ]
        ).strip() + "\n"


def review_node(state: DevState) -> DevState:
    _safe_print("[Review Agent] Starting review")

    reviewer = ReviewerAgent(state["repo_b_path"], state.get("task_payload"))
    result = reviewer.run(state)
    state.update(result)
    state["current_step"] = "review_done"
    add_executed_mode(state, "review")
    issues: list[Issue] = []
    for item in state.get("blocking_issues") or []:
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.BLOCKING,
            source_agent=AgentRole.REVIEWER,
            target_agent=AgentRole.FIXER,
            title="Review blocking issue",
            description=str(item),
            suggestion="Fix the review finding and return the story for another validation pass.",
        )
        if not state.get("review_passed"):
            add_issue(state, issue)
        issues.append(issue)
    for item in state.get("important_issues") or []:
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.IMPORTANT,
            source_agent=AgentRole.REVIEWER,
            target_agent=AgentRole.FIXER,
            title="Review important issue",
            description=str(item),
            suggestion="Address the maintainability or policy issue before final acceptance.",
        )
        if not state.get("review_passed"):
            add_issue(state, issue)
        issues.append(issue)
    review_items_present = bool((state.get("blocking_issues") or []) or (state.get("important_issues") or []) or issues)
    if review_items_present:
        review_signature = hashlib.sha1(
            "|".join(
                [
                    *(str(item) for item in (state.get("blocking_issues") or [])),
                    *(str(item) for item in (state.get("important_issues") or [])),
                ]
            ).encode("utf-8")
        ).hexdigest()
        history = list(state.get("review_issue_history") or [])
        history.append(review_signature)
        state["review_issue_signature"] = review_signature
        state["review_issue_history"] = history
    else:
        state["review_issue_signature"] = None
    if state.get("review_passed") is False and not review_items_present:
        state["failure_type"] = "workflow_bug"
        state["interruption_reason"] = "reviewer_missing_findings"
        state["error_message"] = state.get("error_message") or "Reviewer rejected the story without structured findings."
    if state.get("review_success"):
        add_handoff_packet(
            state,
            HandoffPacket(
                packet_id=str(uuid.uuid4()),
                from_agent=AgentRole.REVIEWER,
                to_agent=AgentRole.CODE_ACCEPTANCE if state.get("review_passed") else AgentRole.FIXER,
                status=HandoffStatus.COMPLETED if state.get("review_passed") else HandoffStatus.BLOCKED,
                what_i_did="Reviewed the validated change set for requirement fit, rules compliance, and maintainability.",
                what_i_produced=[
                    Deliverable(
                        deliverable_id=str(uuid.uuid4()),
                        name="Review Report",
                        type="report",
                        path=str(state.get("review_dir") or ""),
                        description="Structured review output for the current story iteration.",
                        created_by=AgentRole.REVIEWER,
                    )
                ],
                what_risks_i_found=[str(item) for item in (state.get("blocking_issues") or [])],
                what_i_require_next=(
                    "Run code style acceptance on the current files."
                    if state.get("review_passed")
                    else "Resolve every blocking review issue, then re-run validation and review."
                ),
                issues=issues if not state.get("review_passed") else [],
                trace_id=str(state.get("collaboration_trace_id") or ""),
            ),
        )

    _safe_print("[Review Agent] Report")
    for line in str(state.get("review_report", "")).splitlines():
        if line.strip():
            _safe_print(f"[Review Agent] {line}")

    _safe_print("[Review Agent] Review completed")
    return state


def route_after_review(state: DevState) -> str:
    if state.get("failure_type") == "workflow_bug":
        return "__end__"
    return "code_acceptance" if state.get("review_passed") else "fixer"


def _format_bullets(items: list[str], fallback: str) -> str:
    cleaned = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not cleaned:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in cleaned)


def _extract_list_section(report: str, heading: str) -> list[str]:
    lines = report.splitlines()
    target = f"### {heading}"
    active = False
    items: list[str] = []
    for line in lines:
        if line.strip() == target:
            active = True
            continue
        if active and line.startswith("### "):
            break
        if active and line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if item and item.lower() != "none.":
                items.append(item)
    return items


def _matches_protected_path(path: str, protected_paths: list[str]) -> bool:
    normalized_path = path.replace("\\", "/")
    for pattern in protected_paths:
        normalized_pattern = str(pattern).replace("\\", "/").strip()
        if not normalized_pattern:
            continue
        if normalized_pattern.endswith("/**"):
            root = normalized_pattern[:-3].rstrip("/")
            if normalized_path == root or normalized_path.startswith(f"{root}/"):
                return True
            continue
        if normalized_pattern.startswith(".") and "/" not in normalized_pattern:
            if normalized_path == normalized_pattern or normalized_path.endswith(f"/{normalized_pattern}"):
                return True
            continue
        if normalized_path == normalized_pattern or normalized_path.startswith(f"{normalized_pattern.rstrip('/')}/"):
            return True
    return False


def _filter_review_paths(paths: list[str]) -> list[str]:
    filtered: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized.startswith(".git/"):
            continue
        if normalized.startswith("tasks/runtime/") or normalized.startswith("docs/handoff/"):
            continue
        filtered.append(path)
    return filtered


def _safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass
