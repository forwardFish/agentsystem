from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

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
            "review_findings": [],
            "review_checklist": [],
            "blocking_issues": [],
            "important_issues": [],
            "nice_to_haves": [],
            "awaiting_user_input": False,
            "dialogue_state": None,
            "next_question": None,
            "approval_required": False,
            "handoff_target": None,
            "resume_from_mode": None,
            "decision_state": None,
            "interaction_round": 0,
            "error_message": None,
        }

        try:
            changed_files = self._collect_review_scope_paths(state)

            diff = self._build_review_diff(changed_files)

            analysis = self._build_review_analysis(diff, changed_files, state)
            report = self._render_review_report(analysis)
            blocking_issues = [item["summary"] for item in analysis["findings"] if item["severity"] == "blocking"]
            important_issues = [item["summary"] for item in analysis["findings"] if item["severity"] == "important"]
            nice_to_haves = [item["summary"] for item in analysis["findings"] if item["severity"] == "nice_to_have"]

            result["review_findings"] = analysis["findings"]
            result["review_checklist"] = analysis["checklist"]
            result["review_report"] = report
            result["blocking_issues"] = blocking_issues
            result["important_issues"] = important_issues
            result["nice_to_haves"] = nice_to_haves
            result["awaiting_user_input"] = analysis["awaiting_user_input"]
            result["dialogue_state"] = analysis["dialogue_state"]
            result["next_question"] = analysis["next_question"]
            result["approval_required"] = analysis["approval_required"]
            result["handoff_target"] = analysis["handoff_target"]
            result["resume_from_mode"] = analysis["resume_from_mode"]
            result["decision_state"] = analysis["decision_state"]
            result["interaction_round"] = analysis["interaction_round"]
            result["review_passed"] = not blocking_issues
            result["review_success"] = True

            (self.review_dir / "review_report.md").write_text(report, encoding="utf-8")
            (self.review_dir / "review_findings.json").write_text(
                json.dumps(analysis["findings"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (self.review_dir / "review_checklist.json").write_text(
                json.dumps(analysis["checklist"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (self.review_dir / "risk_register.json").write_text(
                json.dumps(
                    {
                        "scope_status": analysis["scope_status"],
                        "repo_profile": analysis["repo_profile"],
                        "story_kind": analysis["story_kind"],
                        "findings": analysis["findings"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (self.review_dir / "review_decision_state.json").write_text(
                json.dumps(analysis["decision_state"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - defensive
            result["error_message"] = f"Review failed: {exc}"

        return result

    def _collect_review_scope_paths(self, state: DevState) -> list[str]:
        if getattr(self.git, "snapshot_mode", False):
            scoped = _review_scope_paths(self.task, state)
            if scoped:
                return scoped
        staged_files = _filter_review_paths(self.git.get_staged_files())
        working_tree_files = _filter_review_paths(self.git.get_working_tree_files())
        changed_files = list(dict.fromkeys([*staged_files, *working_tree_files]))
        if changed_files:
            return changed_files
        return _filter_review_paths([str(path) for path in (state.get("staged_files") or [])])

    def _build_review_diff(self, changed_files: list[str]) -> str:
        if not changed_files:
            return ""
        if getattr(self.git, "snapshot_mode", False):
            return "\n".join(f"- {path}" for path in changed_files[:50])

        diff_parts = [self.git.get_diff(), self.git.get_working_tree_diff()]
        diff = "\n".join(part for part in diff_parts if str(part).strip()).strip()
        if diff:
            return diff
        current_commit = self.git.get_current_commit()
        if current_commit:
            try:
                return self.git.repo.git.show("--stat", "--format=", "HEAD")
            except Exception:
                return ""
        return ""

    def _build_review_analysis(self, diff: str, changed_files: list[str], state: DevState) -> dict[str, object]:
        task_payload = _merge_review_task_payload(self.task, state)
        task_goal = str(task_payload.get("goal", "")).strip() or str(state.get("user_requirement", "")).strip()
        acceptance = (
            task_payload.get("acceptance_criteria", [])
            if isinstance(task_payload.get("acceptance_criteria"), list)
            else list(state.get("acceptance_checklist") or [])
        )
        protected_paths = RepoBConfigReader(self.worktree_path).load_all_config().rules.get("protected_paths", [])
        validation = str(state.get("test_results") or "Validation pending").strip()
        story_kind = str(state.get("story_kind") or "").strip().lower() or "unknown"
        repo_profile = _review_repo_profile(self.worktree_path, task_payload, state)
        release_sensitive = bool(state.get("release_scope")) or str(state.get("workflow_enforcement_policy") or "").strip() in {
            "release",
            "sprint_closeout",
            "closeout",
        }
        declared_scope = _filter_review_paths(
            [
                *(str(item).strip() for item in (state.get("primary_files") or []) if str(item).strip()),
                *(str(item).strip() for item in (state.get("secondary_files") or []) if str(item).strip()),
                *(str(item).strip() for item in (task_payload.get("primary_files") or []) if str(item).strip()),
                *(str(item).strip() for item in (task_payload.get("secondary_files") or []) if str(item).strip()),
                *(str(item).strip() for item in (task_payload.get("related_files") or []) if str(item).strip()),
                *(str(item).strip() for item in (task_payload.get("contract_scope_paths") or []) if str(item).strip()),
                *(
                    str(item).strip()
                    for item in (
                        (task_payload.get("implementation_contract") or {}).get("contract_scope_paths")
                        if isinstance(task_payload.get("implementation_contract"), dict)
                        else []
                    )
                    if str(item).strip()
                ),
            ]
        )
        docs_changed = any(Path(path).suffix.lower() == ".md" for path in changed_files)
        changed_outside_scope = [
            path
            for path in changed_files
            if declared_scope and path not in declared_scope and not path.startswith(("docs/handoff/", "tasks/runtime/"))
        ]
        sensitive_surface_changed = any(
            token in " ".join(changed_files).lower()
            for token in ("config/", "schema", "contract", "workflow", "graph", ".sql", "migration", "infra/", "prompt")
        )
        scope_status = _derive_scope_status(changed_files, changed_outside_scope, acceptance, validation)
        resolved_items = [
            str(item.get("description") or "").strip()
            for item in (state.get("resolved_issues") or [])
            if isinstance(item, dict) and str(item.get("description") or "").strip()
        ]

        findings: list[dict[str, str]] = []
        checklist: list[dict[str, str]] = [
            {
                "band": "critical",
                "name": "Protected path discipline",
                "status": "failed" if protected_paths and any(_matches_protected_path(path, protected_paths) for path in changed_files) else "passed",
                "detail": "No protected path appears in the review scope." if not protected_paths else "Protected paths were checked against the change set.",
            },
            {
                "band": "critical",
                "name": "Validation baseline",
                "status": "failed" if "FAIL" in validation.upper() else "passed",
                "detail": validation or "Validation output was not provided.",
            },
            {
                "band": "informational",
                "name": "Declared file scope",
                "status": "warn" if changed_outside_scope else "passed",
                "detail": "Changed files stayed inside the declared story scope." if not changed_outside_scope else f"Out-of-scope files: {', '.join(changed_outside_scope)}",
            },
            {
                "band": "informational",
                "name": "Documentation freshness",
                "status": "warn" if changed_files and not docs_changed and any(Path(path).suffix.lower() != ".md" for path in changed_files) else "passed",
                "detail": "Root or handoff docs were updated alongside code changes." if docs_changed else "No doc update detected for this diff.",
            },
        ]
        checklist.extend(
            _repo_specific_checklist(
                repo_profile=repo_profile,
                story_kind=story_kind,
                changed_files=changed_files,
                sensitive_surface_changed=sensitive_surface_changed,
                release_sensitive=release_sensitive,
                docs_changed=docs_changed,
            )
        )

        if not changed_files and "StoryValidation: PASS" not in validation:
            findings.append(
                _finding(
                    "blocking",
                    "ASK",
                    "No code changes were available for review.",
                    "The review step could not locate staged or unstaged repository changes while validation still indicates unresolved work.",
                    "Capture the intended diff before re-running review.",
                    evidence_refs=changed_files,
                )
            )
        if protected_paths and any(_matches_protected_path(path, protected_paths) for path in changed_files):
            findings.append(
                _finding(
                    "blocking",
                    "ASK",
                    "A protected path appears in the review scope.",
                    "This diff touches files that the repo rules mark as protected, so the blast radius is higher than the task card allows.",
                    "Move the change out of the protected area or secure explicit approval before landing it.",
                    evidence_refs=changed_files,
                )
            )
        if "FAIL" in validation.upper():
            findings.append(
                _finding(
                    "blocking",
                    "AUTO-FIX",
                    "Validation still reports failing checks.",
                    "The current branch has not cleared the configured validation baseline, so landing it would bypass the workflow gate.",
                    "Fix the failing validation step, then rerun test and review.",
                    evidence_refs=changed_files,
                )
            )
        if changed_outside_scope:
            findings.append(
                _finding(
                    "important",
                    "ASK",
                    "The diff expands beyond the declared story scope.",
                    f"Files outside the declared scope were changed: {', '.join(changed_outside_scope)}.",
                    "Either narrow the diff or explain why the extra files are required for acceptance.",
                    evidence_refs=changed_outside_scope,
                )
            )
        if sensitive_surface_changed and not _has_explicit_verification_evidence(validation, state, task_payload):
            findings.append(
                _finding(
                    "important",
                    "ASK",
                    "The change touches production-sensitive runtime or contract surfaces.",
                    "Config, schema, contract, workflow, SQL, or infrastructure-adjacent files changed in this diff, which increases rollout risk.",
                    "Add explicit verification evidence for the affected runtime surfaces before acceptance.",
                    evidence_refs=changed_files,
                )
            )
        if acceptance and "StoryValidation: PASS" not in validation:
            findings.append(
                _finding(
                    "important",
                    "ASK",
                    "Acceptance criteria were not matched by story-specific validation evidence.",
                    "The task card defines acceptance criteria, but the validation log does not show a strong story-level pass.",
                    "Tie at least one validation or QA artifact directly to the requested acceptance criteria.",
                    evidence_refs=changed_files,
                )
            )
        if not docs_changed and any(Path(path).suffix.lower() != ".md" for path in changed_files):
            findings.append(
                _finding(
                    "nice_to_have",
                    "AUTO-FIX",
                    "Documentation may be stale after the current code changes.",
                    "Code changed in this branch without any corresponding root or handoff documentation update.",
                    "Run document-release or update the relevant docs before shipping.",
                    evidence_refs=changed_files,
                )
            )
        if not acceptance:
            findings.append(
                _finding(
                    "nice_to_have",
                    "AUTO-FIX",
                    "The task card does not declare acceptance criteria explicitly.",
                    "Without explicit acceptance criteria, downstream QA and acceptance have to infer what done means.",
                    "Add explicit acceptance criteria to the story card or preserve that contract in the architecture review.",
                    evidence_refs=[],
                )
            )
        for description in resolved_items[:5]:
            findings.append(
                _finding(
                    "nice_to_have",
                    "already-fixed",
                    "A previously reported issue has already been resolved in this workflow.",
                    description,
                    "Keep the fix evidence attached to the current review artifact.",
                    evidence_refs=changed_files,
                )
            )

        ask_findings = [
            item
            for item in findings
            if str(item.get("disposition") or "") == "ASK" and str(item.get("severity") or "") in {"blocking", "important"}
        ]
        next_question = (
            {
                "kind": "review_decision",
                "question": str(ask_findings[0].get("recommendation") or "").strip(),
                "finding_summary": str(ask_findings[0].get("summary") or "").strip(),
            }
            if ask_findings
            else None
        )
        decision_state = {
            "mode": "review",
            "repo_profile": repo_profile,
            "story_kind": story_kind,
            "scope_status": scope_status,
            "ask_findings": ask_findings,
            "protected_paths": list(protected_paths or []),
            "changed_files": changed_files,
        }
        analysis = {
            "task_goal": task_goal or "Local agent-generated change.",
            "repo_profile": repo_profile,
            "story_kind": story_kind,
            "scope_status": scope_status,
            "intent_summary": task_goal or "Review the current task diff against its stated goal.",
            "delivered_summary": _delivered_summary(changed_files),
            "acceptance": acceptance,
            "validation": validation,
            "changed_files": changed_files,
            "diff_excerpt": diff[:2000],
            "checklist": checklist,
            "findings": findings,
            "awaiting_user_input": bool(ask_findings),
            "dialogue_state": decision_state,
            "next_question": next_question,
            "approval_required": bool(ask_findings),
            "handoff_target": "review_decision" if ask_findings else ("fixer" if findings else "code_acceptance"),
            "resume_from_mode": "review" if ask_findings else None,
            "decision_state": decision_state,
            "interaction_round": len(ask_findings),
        }
        if _is_non_interactive_auto_run(state):
            _auto_resolve_review_interaction(analysis)
        return analysis

    def _render_review_report(self, analysis: dict[str, object]) -> str:
        findings = analysis["findings"] if isinstance(analysis.get("findings"), list) else []
        checklist = analysis["checklist"] if isinstance(analysis.get("checklist"), list) else []
        verdict = (
            "- [x] Review passed for local iteration"
            if not any(item.get("severity") == "blocking" for item in findings)
            else "- [ ] Blocking issues must be fixed"
        )
        return "\n".join(
            [
                "# Review Report",
                "",
                "## Scope Check",
                f"- Status: {analysis.get('scope_status')}",
                f"- Intent: {analysis.get('intent_summary')}",
                f"- Delivered: {analysis.get('delivered_summary')}",
                "",
                "## Production Risk Focus",
                "Prefer issues that can pass CI yet still fail in production, runtime, or real user flows.",
                "",
                "## Acceptance Coverage",
                _format_bullets(analysis.get("acceptance") if isinstance(analysis.get("acceptance"), list) else [], fallback="No acceptance criteria recorded."),
                "",
                "## Validation",
                str(analysis.get("validation") or "Validation pending").strip(),
                "",
                "## Changed Files",
                _format_bullets(analysis.get("changed_files") if isinstance(analysis.get("changed_files"), list) else [], fallback="No changed files recorded."),
                "",
                "## Checklist Findings",
                "### Critical",
                _format_checklist(checklist, "critical"),
                "",
                "### Informational",
                _format_checklist(checklist, "informational"),
                "",
                "## Findings",
                "### Blocking",
                _format_finding_lines(findings, "blocking"),
                "",
                "### Important",
                _format_finding_lines(findings, "important"),
                "",
                "### Nice to have",
                _format_finding_lines(findings, "nice_to_have"),
                "",
                "### Already Fixed",
                _format_finding_lines(findings, "already-fixed", use_disposition=True),
                "",
                "## Decision Ceremony",
                _format_review_decision_block(analysis),
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
        fallback_message = str(
            state.get("error_message") or "Reviewer rejected the story without structured findings."
        ).strip()
        state["failure_type"] = "workflow_bug"
        state["interruption_reason"] = "reviewer_missing_findings"
        state["error_message"] = fallback_message
        state["blocking_issues"] = [fallback_message]
        fallback_issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.BLOCKING,
            source_agent=AgentRole.REVIEWER,
            target_agent=AgentRole.FIXER,
            title="Review workflow fallback issue",
            description=fallback_message,
            suggestion="Treat the missing review finding output as a fix-loop blocker and continue the validation repair cycle.",
        )
        add_issue(state, fallback_issue)
        issues.append(fallback_issue)
        review_items_present = True
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
                        path=f".meta/{Path(str(state['repo_b_path'])).name}/review/review_report.md",
                        description="Structured review output for the current story iteration.",
                        created_by=AgentRole.REVIEWER,
                    ),
                    Deliverable(
                        deliverable_id=str(uuid.uuid4()),
                        name="Review Findings",
                        type="report",
                        path=f".meta/{Path(str(state['repo_b_path'])).name}/review/review_findings.json",
                        description="Structured review findings with severity, disposition, and recommended actions.",
                        created_by=AgentRole.REVIEWER,
                    ),
                    Deliverable(
                        deliverable_id=str(uuid.uuid4()),
                        name="Risk Register",
                        type="report",
                        path=f".meta/{Path(str(state['repo_b_path'])).name}/review/risk_register.json",
                        description="Structured risk register for repo-specific review depth and finding evidence.",
                        created_by=AgentRole.REVIEWER,
                    ),
                ],
                what_risks_i_found=[str(item) for item in (state.get("blocking_issues") or [])],
                what_i_require_next=(
                    "Capture the required review decision, then resume the review or fix loop."
                    if state.get("awaiting_user_input")
                    else (
                        "Run code style acceptance on the current files."
                        if state.get("review_passed")
                        else "Resolve every blocking review issue, then re-run validation and review."
                    )
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
        return "fixer"
    if (
        state.get("awaiting_user_input")
        and str(state.get("resume_from_mode") or "").strip() == "review"
        and (
            str(state.get("skill_mode") or "").strip() == "review"
            or str(state.get("stop_after") or "").strip() == "reviewer"
        )
    ):
        return "__end__"
    return "code_acceptance" if state.get("review_passed") else "fixer"


def _is_non_interactive_auto_run(state: DevState) -> bool:
    task_payload = state.get("task_payload") or {}
    interaction_policy = str(state.get("interaction_policy") or task_payload.get("interaction_policy") or "").strip().lower()
    return bool(state.get("auto_run") or task_payload.get("auto_run")) or interaction_policy == "non_interactive_auto_run"


def _auto_resolve_review_interaction(analysis: dict[str, object]) -> None:
    findings = analysis.get("findings")
    if not isinstance(findings, list):
        return
    auto_blockers: list[dict[str, Any]] = []
    for item in findings:
        if not isinstance(item, dict) or str(item.get("disposition") or "") != "ASK":
            continue
        summary = str(item.get("summary") or "").lower()
        detail = str(item.get("detail") or "").lower()
        if any(marker in f"{summary} {detail}" for marker in ("protected path", "runtime or contract surfaces", "expands beyond the declared story scope")):
            item["disposition"] = "AUTO-FIX"
            item["auto_blocker"] = True
            auto_blockers.append(item)
            continue
        item["disposition"] = "AUTO-FIX"
        item["detail"] = f"{item.get('detail')} Auto-resolved conservatively during non-interactive auto-run.".strip()
    blocking_findings = [item for item in findings if str(item.get("severity") or "") == "blocking"]
    analysis["awaiting_user_input"] = False
    analysis["dialogue_state"] = {
        **(analysis.get("dialogue_state") or {}),
        "auto_resolved": True,
        "auto_blockers": auto_blockers,
    }
    analysis["next_question"] = None
    analysis["approval_required"] = False
    analysis["handoff_target"] = "fixer" if blocking_findings else "code_acceptance"
    analysis["resume_from_mode"] = None
    analysis["decision_state"] = analysis["dialogue_state"]
    analysis["interaction_round"] = 0


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


def _finding(
    severity: str,
    disposition: str,
    summary: str,
    detail: str,
    recommendation: str,
    *,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "disposition": disposition,
        "summary": summary,
        "detail": detail,
        "recommendation": recommendation,
        "evidence_refs": [item for item in (evidence_refs or []) if str(item).strip()],
    }


def _derive_scope_status(
    changed_files: list[str],
    changed_outside_scope: list[str],
    acceptance: list[str],
    validation: str,
) -> str:
    if changed_outside_scope:
        return "DRIFT DETECTED"
    if acceptance and "StoryValidation: PASS" not in validation:
        return "REQUIREMENTS MISSING"
    if changed_files:
        return "CLEAN"
    return "UNKNOWN"


def _delivered_summary(changed_files: list[str]) -> str:
    if not changed_files:
        return "No changed files were available in the current review scope."
    return f"The diff currently touches {len(changed_files)} file(s): {', '.join(changed_files[:4])}."


def _format_checklist(items: list[dict[str, str]], band: str) -> str:
    lines = []
    for item in items:
        if str(item.get("band") or "") != band:
            continue
        status = str(item.get("status") or "pending")
        lines.append(f"- [{status}] {item.get('name')}: {item.get('detail')}")
    return "\n".join(lines) if lines else "- None."


def _format_finding_lines(
    findings: list[dict[str, Any]],
    target: str,
    *,
    use_disposition: bool = False,
) -> str:
    lines: list[str] = []
    for item in findings:
        comparator = str(item.get("disposition") if use_disposition else item.get("severity") or "")
        if comparator != target:
            continue
        evidence_refs = [str(ref).strip() for ref in (item.get("evidence_refs") or []) if str(ref).strip()]
        evidence_suffix = f" | Evidence: {', '.join(evidence_refs[:3])}" if evidence_refs else ""
        lines.append(
            f"- [{item.get('disposition')}] {item.get('summary')}: {item.get('detail')} | Next: {item.get('recommendation')}{evidence_suffix}"
        )
    return "\n".join(lines) if lines else "- None."


def _format_review_decision_block(analysis: dict[str, object]) -> str:
    state = analysis.get("decision_state")
    if not isinstance(state, dict):
        return "- No staged review decision is required."
    ask_findings = state.get("ask_findings")
    if not isinstance(ask_findings, list) or not ask_findings:
        return "- No staged review decision is required."
    lines = [
        f"- Repo profile: {state.get('repo_profile')}",
        f"- Story kind: {state.get('story_kind')}",
        f"- Scope status: {state.get('scope_status')}",
    ]
    for item in ask_findings:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- ASK: {item.get('summary')} | decision={item.get('recommendation')}"
        )
    return "\n".join(lines)


def _merge_review_task_payload(task: dict[str, object] | None, state: DevState) -> dict[str, object]:
    payload = dict(state.get("task_payload") or {})
    for key, value in (task or {}).items():
        if value not in (None, "", [], {}):
            payload[key] = value

    for key in ("primary_files", "secondary_files"):
        if not payload.get(key) and isinstance(state.get(key), list):
            payload[key] = list(state.get(key) or [])

    implementation_contract = payload.get("implementation_contract")
    contract_scope = _coalesce_path_lists(
        payload.get("contract_scope_paths"),
        implementation_contract.get("contract_scope_paths") if isinstance(implementation_contract, dict) else [],
    )
    if contract_scope:
        payload["contract_scope_paths"] = contract_scope
    return payload


def _review_scope_paths(task: dict[str, object] | None, state: DevState) -> list[str]:
    payload = _merge_review_task_payload(task, state)
    implementation_contract = payload.get("implementation_contract")
    return _filter_review_paths(
        _coalesce_path_lists(
            payload.get("primary_files"),
            payload.get("secondary_files"),
            payload.get("related_files"),
            payload.get("contract_scope_paths"),
            implementation_contract.get("contract_scope_paths") if isinstance(implementation_contract, dict) else [],
            (
                implementation_contract.get("artifact_inventory", {}).get("supporting_code")
                if isinstance(implementation_contract, dict)
                and isinstance(implementation_contract.get("artifact_inventory"), dict)
                else []
            ),
            (
                implementation_contract.get("artifact_inventory", {}).get("docs")
                if isinstance(implementation_contract, dict)
                and isinstance(implementation_contract.get("artifact_inventory"), dict)
                else []
            ),
            state.get("primary_files"),
            state.get("secondary_files"),
            state.get("staged_files"),
        )
    )


def _review_repo_profile(worktree_path: Path, task_payload: dict[str, object], state: DevState) -> str:
    project = str(task_payload.get("project") or state.get("project") or "").strip().lower()
    if project in {"agentsystem", "finahunt", "versefina"}:
        return project
    repo_root = str(task_payload.get("project_repo_root") or "").strip()
    if repo_root:
        repo_name = Path(repo_root).name.lower()
        if repo_name in {"agentsystem", "finahunt", "versefina"}:
            return repo_name
    name = worktree_path.name.lower()
    if name in {"agentsystem", "finahunt", "versefina"}:
        return name
    return "generic"


def _has_explicit_verification_evidence(
    validation: str,
    state: DevState,
    task_payload: dict[str, object],
) -> bool:
    if "STORYVALIDATION: PASS" in validation.upper():
        return True
    evidence_values = [
        state.get("runtime_qa_report"),
        state.get("browser_qa_report"),
        state.get("qa_design_review_report"),
        state.get("test_results"),
        task_payload.get("delivery_evidence"),
        task_payload.get("runtime_qa_report"),
        task_payload.get("browser_qa_report"),
    ]
    return any(str(item or "").strip() for item in evidence_values)


def _coalesce_path_lists(*values: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            marker = str(item).strip()
            if not marker or marker in seen:
                continue
            seen.add(marker)
            merged.append(marker)
    return merged


def _repo_specific_checklist(
    *,
    repo_profile: str,
    story_kind: str,
    changed_files: list[str],
    sensitive_surface_changed: bool,
    release_sensitive: bool,
    docs_changed: bool,
) -> list[dict[str, str]]:
    changed_text = " ".join(path.replace("\\", "/").lower() for path in changed_files)
    items: list[dict[str, str]] = []
    if repo_profile == "agentsystem":
        items.append(
            {
                "band": "critical",
                "name": "Workflow and agent parity surfaces",
                "status": "warn" if any(token in changed_text for token in ("config/workflows/", "config/skill_modes/", "parity", "workflow_registry", "agent_activation")) else "passed",
                "detail": "Workflow-manifest and parity-touching changes need matching runtime and doc evidence.",
            }
        )
    if repo_profile == "finahunt":
        items.append(
            {
                "band": "critical",
                "name": "Runtime artifact contract",
                "status": "warn" if any(token in changed_text for token in ("graphs/", "workflows/", "packages/", "workspace/artifacts/runtime")) else "passed",
                "detail": "Ranking, linkage, and runtime artifacts should stay explainable and schema-stable.",
            }
        )
    if repo_profile == "versefina":
        items.append(
            {
                "band": "critical",
                "name": "API and storage contract discipline",
                "status": "warn" if any(token in changed_text for token in ("apps/api/", "swagger", "storage", "metadata")) else "passed",
                "detail": "API-facing changes should preserve request/response and storage semantics.",
            }
        )
    if story_kind in {"runtime_data", "api", "mixed"}:
        items.append(
            {
                "band": "informational",
                "name": "Runtime failure-mode evidence",
                "status": "warn" if sensitive_surface_changed else "passed",
                "detail": "Runtime/data stories should carry explicit failure-mode and verification evidence into QA.",
            }
        )
    if story_kind in {"ui", "mixed"}:
        items.append(
            {
                "band": "informational",
                "name": "UI evidence chain",
                "status": "warn" if not docs_changed and any(path.endswith((".tsx", ".jsx", ".css", ".scss", ".html")) for path in changed_files) else "passed",
                "detail": "UI stories should keep browse/design-review evidence and visible notes aligned.",
            }
        )
    if release_sensitive:
        items.append(
            {
                "band": "critical",
                "name": "Release-sensitive review depth",
                "status": "warn",
                "detail": "Release-closeout changes need stronger review rationale and document sync evidence.",
            }
        )
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
