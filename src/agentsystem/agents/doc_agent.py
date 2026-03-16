from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet


STORY_COMPLETION_STANDARD = """# Story Completion Standard

## Purpose
A Story is the smallest execution and acceptance unit in the system. A Story is only considered complete when the planned contract, implementation, validation, review, code acceptance, final acceptance, and delivery reporting all succeed with evidence.

## Planned Story Contract
- Before execution starts, every Story must declare explicit input, process, output, and verification basis.
- The planned contract must be readable from the task card or the requirement intent confirmation artifact.
- Agents must stay inside the declared scope and keep the implementation aligned with the planned output.

## Definition of Done
- The task card is valid and passes TaskCard schema validation.
- The execution scope is explicit and limited to files allowed by the Story.
- The expected output artifacts are written into the target repository and can be reused by downstream stories.
- Code Style Reviewer reports no blocking style-consistency issues before tests start.
- Configured project checks and Story-specific validation both pass.
- Reviewer reports no blocking issues.
- Code Acceptance Agent reports no style-consistency or file-hygiene blockers.
- Acceptance Gate passes all checklist items and confirms there is no out-of-scope change.
- A delivery report and a result report are generated and archived.

## Acceptance OK
- Every acceptance criterion has explicit evidence recorded in the delivery report.
- The result report shows the actual input, key process evidence, actual output, and verification outcome.
- The test report contains no failing checks.
- Code Style Review, Review, Code Acceptance, and Acceptance Gate all pass.
- Output artifacts, reports, and logs are readable UTF-8 content.
"""


def doc_node(state: DevState) -> DevState:
    repo_b_path = Path(state["repo_b_path"]).resolve()
    delivery_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)

    standard_path = delivery_dir / "story_completion_standard.md"
    report_path = delivery_dir / "story_delivery_report.md"
    result_report_path = delivery_dir / "story_result_report.md"

    standard_path.write_text(STORY_COMPLETION_STANDARD, encoding="utf-8")

    task_payload = state.get("task_payload") or {}
    acceptance_items = _clean_items(task_payload.get("acceptance_criteria"))
    story_inputs = _clean_items(task_payload.get("story_inputs"))
    story_process = _clean_items(task_payload.get("story_process"))
    story_outputs = _clean_items(task_payload.get("story_outputs"))
    verification_basis = _clean_items(task_payload.get("verification_basis"))

    result_report = "\n".join(
        [
            "# Story Result Report",
            "",
            "## Story Summary",
            f"- Story ID: {task_payload.get('story_id') or task_payload.get('task_id') or 'n/a'}",
            f"- Story Name: {task_payload.get('task_name') or task_payload.get('goal') or 'n/a'}",
            f"- Sprint: {task_payload.get('sprint') or 'n/a'}",
            f"- Epic: {task_payload.get('epic') or 'n/a'}",
            "",
            "## Planned Story Contract",
            "### Input",
            *_render_list_block(story_inputs, empty_text="No planned story input recorded."),
            "",
            "### Process",
            *_render_list_block(story_process, empty_text="No planned story process recorded."),
            "",
            "### Output",
            *_render_list_block(story_outputs, empty_text="No planned story output recorded."),
            "",
            "### Verification Basis",
            *_render_list_block(verification_basis, empty_text="No verification basis recorded."),
            "",
            "## Actual Input Used",
            *_render_list_block(_collect_actual_inputs(state, task_payload), empty_text="No actual input trace recorded."),
            "",
            "## Process Evidence",
            *_render_list_block(_collect_process_evidence(state), empty_text="No process evidence recorded."),
            "",
            "## Actual Output Produced",
            *_render_list_block(
                _collect_actual_outputs(state, standard_path, report_path, result_report_path),
                empty_text="No actual output recorded.",
            ),
            "",
            "## Verification Outcome",
            *_render_list_block(
                _collect_verification_outcome(state, acceptance_items, verification_basis),
                empty_text="No verification outcome recorded.",
            ),
            "",
            "## Final Acceptance Signal",
            "- [x] Story result is archived and ready for human review"
            if _is_story_fully_accepted(state)
            else "- [ ] Story result is not yet fully accepted",
            "",
        ]
    )
    result_report_path.write_text(result_report, encoding="utf-8")

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
        "## Planned Story Contract",
        "### Input",
        *_render_list_block(story_inputs, empty_text="No planned story input recorded."),
        "",
        "### Process",
        *_render_list_block(story_process, empty_text="No planned story process recorded."),
        "",
        "### Output",
        *_render_list_block(story_outputs, empty_text="No planned story output recorded."),
        "",
        "### Verification Basis",
        *_render_list_block(verification_basis, empty_text="No verification basis recorded."),
        "",
        "## Validation Summary",
        f"- Code Style Review: {'PASS' if state.get('code_style_review_passed') else 'FAIL'}",
        f"- Tests: {'PASS' if state.get('test_passed') else 'FAIL'}",
        f"- Reviewer: {'PASS' if state.get('review_passed') else 'FAIL'}",
        f"- Code Acceptance: {'PASS' if state.get('code_acceptance_passed') else 'FAIL'}",
        f"- Acceptance Gate: {'PASS' if state.get('acceptance_passed') else 'FAIL'}",
        "",
        "## Acceptance Criteria",
        *_render_list_block(acceptance_items, empty_text="No acceptance criteria recorded."),
        "",
        "## Acceptance Evidence",
        f"- Story-specific validation: {state.get('test_results') or 'n/a'}",
        f"- Blocking issues remaining: {len(state.get('issues_to_fix') or [])}",
        f"- Fix attempts: {state.get('fix_attempts') or 0}",
        "",
        "## Reports",
        f"- Code style review report: {state.get('code_style_review_dir') or 'n/a'}",
        f"- Test results: {state.get('test_results') or 'n/a'}",
        f"- Review report: {state.get('review_dir') or 'n/a'}",
        f"- Code acceptance report: {state.get('code_acceptance_dir') or 'n/a'}",
        f"- Acceptance report: {state.get('acceptance_dir') or 'n/a'}",
        f"- Result report: {result_report_path.name}",
        "",
        "## Final Verdict",
        "- [x] Story completed and accepted" if _is_story_fully_accepted(state) else "- [ ] Story is not fully accepted",
        "",
    ]
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
            what_i_did="Compiled the story completion standard, the delivery report, and the result report for archival and human sign-off.",
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
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Story Result Report",
                    type="report",
                    path=str(result_report_path),
                    description="Actual input, process evidence, output, and verification outcome for human acceptance.",
                    created_by=AgentRole.DOC_WRITER,
                ),
            ],
            what_risks_i_found=[],
            what_i_require_next="Archive the delivery artifacts and expose both the planned contract and the actual result report through the dashboard.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def _clean_items(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _render_list_block(items: list[str], *, empty_text: str) -> list[str]:
    if not items:
        return [f"- {empty_text}"]
    return [f"- {item}" for item in items]


def _collect_actual_inputs(state: DevState, task_payload: dict[str, object]) -> list[str]:
    items: list[str] = []
    items.extend(_clean_items(task_payload.get("story_inputs")))

    primary_files = [str(item).strip() for item in (task_payload.get("primary_files") or []) if str(item).strip()]
    secondary_files = [str(item).strip() for item in (task_payload.get("secondary_files") or []) if str(item).strip()]
    if primary_files:
        items.append(f"Primary files used during execution: {', '.join(primary_files)}")
    if secondary_files:
        items.append(f"Secondary reference files: {', '.join(secondary_files)}")

    shared_blackboard = state.get("shared_blackboard") or {}
    for key, label in (
        ("story_inputs", "Requirement agent input contract"),
        ("current_goal", "Parsed goal"),
    ):
        value = shared_blackboard.get(key)
        if isinstance(value, list) and value:
            items.append(f"{label}: {', '.join(str(entry) for entry in value)}")
        elif isinstance(value, str) and value.strip():
            items.append(f"{label}: {value.strip()}")
    return _dedupe(items)


def _collect_process_evidence(state: DevState) -> list[str]:
    evidence = [
        f"Requirement analysis: {'completed' if state.get('current_step') else 'not recorded'}",
        f"Code Style Review: {'PASS' if state.get('code_style_review_passed') else 'FAIL'}",
        f"Tests: {'PASS' if state.get('test_passed') else 'FAIL'}",
        f"Reviewer: {'PASS' if state.get('review_passed') else 'FAIL'}",
        f"Code Acceptance: {'PASS' if state.get('code_acceptance_passed') else 'FAIL'}",
        f"Acceptance Gate: {'PASS' if state.get('acceptance_passed') else 'FAIL'}",
    ]
    test_results = str(state.get("test_results") or "").strip()
    if test_results:
        evidence.append(f"Test evidence: {test_results}")
    handoff_packets = state.get("handoff_packets") or []
    if handoff_packets:
        evidence.append(f"Completed handoff packets: {len(handoff_packets)}")
    return evidence


def _collect_actual_outputs(
    state: DevState,
    standard_path: Path,
    report_path: Path,
    result_report_path: Path,
) -> list[str]:
    outputs: list[str] = []
    dev_results = state.get("dev_results") or {}
    for payload in dev_results.values():
        if not isinstance(payload, dict):
            continue
        updated_files = [str(item).strip() for item in payload.get("updated_files", []) if str(item).strip()]
        if updated_files:
            outputs.append(f"Updated files: {', '.join(updated_files)}")

    outputs.extend(
        [
            f"Completion standard archived at {standard_path.name}",
            f"Delivery report archived at {report_path.name}",
            f"Result report archived at {result_report_path.name}",
        ]
    )
    return _dedupe(outputs)


def _collect_verification_outcome(
    state: DevState,
    acceptance_items: list[str],
    verification_basis: list[str],
) -> list[str]:
    outcomes: list[str] = []
    for item in acceptance_items:
        status = "PASS" if state.get("acceptance_passed") else "PENDING"
        outcomes.append(f"Acceptance criterion [{status}]: {item}")
    for item in verification_basis:
        outcomes.append(f"Verification basis reviewed: {item}")
    blocking_issues = state.get("issues_to_fix") or []
    outcomes.append(f"Open issues remaining: {len(blocking_issues)}")
    return outcomes


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _is_story_fully_accepted(state: DevState) -> bool:
    return bool(
        state.get("code_style_review_passed")
        and state.get("test_passed")
        and state.get("review_passed")
        and state.get("code_acceptance_passed")
        and state.get("acceptance_passed")
    )
