from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet


STORY_COMPLETION_STANDARD = """# Story Completion Standard

## Definition of Done
- Task card schema is valid and the execution scope is explicit.
- Required files are created or updated in the target repository.
- Validation passes for story-specific checks and configured project checks.
- Reviewer passes with no blocking issues.
- Code acceptance passes for style consistency and artifact hygiene.
- Acceptance Gate passes all checklist items and scope checks.
- Delivery report is generated and archived with the run artifacts.

## Acceptance OK
- All acceptance criteria are marked as passed.
- No blocking issue remains in review, code acceptance, or acceptance gate.
- The latest commit references only story-scoped changes.
- Output artifacts are readable and stored in UTF-8.
"""


def doc_node(state: DevState) -> DevState:
    repo_b_path = Path(state["repo_b_path"]).resolve()
    delivery_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)

    standard_path = delivery_dir / "story_completion_standard.md"
    report_path = delivery_dir / "story_delivery_report.md"

    standard_path.write_text(STORY_COMPLETION_STANDARD, encoding="utf-8")

    task_payload = state.get("task_payload") or {}
    report_lines = [
        "# Story Delivery Report",
        "",
        "## Story Summary",
        f"- Story ID: {task_payload.get('story_id') or task_payload.get('task_id') or 'n/a'}",
        f"- Story Name: {task_payload.get('task_name') or task_payload.get('goal') or 'n/a'}",
        f"- Sprint: {task_payload.get('sprint') or 'n/a'}",
        f"- Epic: {task_payload.get('epic') or 'n/a'}",
        "",
        "## Completion Standard",
        f"- Standard file: {standard_path.name}",
        "",
        "## Validation Summary",
        f"- Tests: {'PASS' if state.get('test_passed') else 'FAIL'}",
        f"- Reviewer: {'PASS' if state.get('review_passed') else 'FAIL'}",
        f"- Code Acceptance: {'PASS' if state.get('code_acceptance_passed') else 'FAIL'}",
        f"- Acceptance Gate: {'PASS' if state.get('acceptance_passed') else 'FAIL'}",
        "",
        "## Acceptance Criteria",
    ]
    acceptance_items = [str(item) for item in (task_payload.get("acceptance_criteria") or []) if str(item).strip()]
    if acceptance_items:
        report_lines.extend(f"- {item}" for item in acceptance_items)
    else:
        report_lines.append("- None recorded.")
    report_lines.extend(
        [
            "",
            "## Reports",
            f"- Test results: {state.get('test_results') or 'n/a'}",
            f"- Review report: {state.get('review_dir') or 'n/a'}",
            f"- Code acceptance report: {state.get('code_acceptance_dir') or 'n/a'}",
            f"- Acceptance report: {state.get('acceptance_dir') or 'n/a'}",
            "",
            "## Final Verdict",
            "- [x] Story completed and accepted"
            if state.get("test_passed") and state.get("review_passed") and state.get("code_acceptance_passed") and state.get("acceptance_passed")
            else "- [ ] Story is not fully accepted",
            "",
        ]
    )
    report = "\n".join(report_lines)

    report_path.write_text(report, encoding="utf-8")
    state["doc_result"] = report
    state["delivery_dir"] = str(delivery_dir)
    state["current_step"] = "doc_done"
    state["collaboration_ended_at"] = datetime.now().isoformat(timespec="seconds")
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.DOC_WRITER,
            to_agent=AgentRole.DOC_WRITER,
            status=HandoffStatus.COMPLETED,
            what_i_did="Compiled the story completion standard and the final delivery report for archival and human sign-off.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Story Completion Standard",
                    type="report",
                    path=str(standard_path),
                    description="Definition of done used for story completion checks.",
                    created_by=AgentRole.DOC_WRITER,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Story Delivery Report",
                    type="report",
                    path=str(report_path),
                    description="Final delivery summary for the completed story.",
                    created_by=AgentRole.DOC_WRITER,
                ),
            ],
            what_risks_i_found=[],
            what_i_require_next="Archive the delivery artifacts and expose them through the dashboard for human review.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state
