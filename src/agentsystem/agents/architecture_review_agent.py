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
    add_executed_mode,
    add_handoff_packet,
)


def architecture_review_node(state: DevState) -> DevState:
    print("[Architecture Review Agent] Building implementation plan")

    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    review_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "architecture_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    goal = str(state.get("parsed_goal") or state.get("user_requirement") or "").strip()
    acceptance = _clean_lines(state.get("acceptance_checklist"))
    constraints = _clean_lines(state.get("parsed_constraints"))
    not_do = _clean_lines(state.get("parsed_not_do"))
    verification_basis = _clean_lines(state.get("verification_basis"))
    primary_files = _clean_lines(state.get("primary_files"))
    secondary_files = _clean_lines(state.get("secondary_files"))
    story_inputs = _clean_lines(state.get("story_inputs"))
    story_process = _clean_lines(state.get("story_process"))
    story_outputs = _clean_lines(state.get("story_outputs"))
    subtasks = _normalize_subtasks(state.get("subtasks"))

    architecture_summary = _build_architecture_summary(subtasks, primary_files, secondary_files)
    data_flow = _build_data_flow(story_inputs, subtasks, story_outputs, primary_files)
    architecture_diagram = _build_architecture_diagram(story_inputs, subtasks, story_outputs, primary_files)
    boundaries = _build_boundaries(primary_files, secondary_files, constraints, not_do)
    edge_cases = _build_edge_cases(acceptance, constraints, not_do, primary_files)
    test_plan = _build_test_plan(verification_basis, acceptance, primary_files, subtasks, edge_cases)
    failure_modes = _build_failure_modes(data_flow, edge_cases, test_plan)
    qa_handoff_lines = _build_qa_handoff(acceptance, verification_basis, edge_cases, failure_modes)
    open_questions = _build_open_planning_questions(
        goal=goal,
        acceptance=acceptance,
        verification_basis=verification_basis,
        primary_files=primary_files,
        story_inputs=story_inputs,
        story_outputs=story_outputs,
    )
    non_interactive_auto_run = _is_non_interactive_auto_run(state)
    auto_resolved_questions = _auto_resolve_open_planning_questions(
        open_questions,
        goal=goal,
        acceptance=acceptance,
        verification_basis=verification_basis,
        primary_files=primary_files,
        story_inputs=story_inputs,
        story_outputs=story_outputs,
    ) if non_interactive_auto_run else []
    if auto_resolved_questions:
        open_questions = []
    next_question = dict(open_questions[0]) if open_questions else None
    planning_decision_state = {
        "mode": "plan-eng-review",
        "goal": goal or None,
        "required_inputs": {
            "acceptance_checklist": bool(acceptance),
            "verification_basis": bool(verification_basis),
            "primary_files": bool(primary_files),
            "story_outputs": bool(story_outputs),
        },
        "open_questions": open_questions,
        "qa_handoff": qa_handoff_lines,
        "builder_handoff": {
            "file_scope": {
                "primary_files": primary_files,
                "secondary_files": secondary_files,
            },
            "risk_focus": [item["failure"] for item in failure_modes],
            "test_strategy": test_plan,
        },
        "auto_resolved_questions": auto_resolved_questions,
    }

    report_lines = [
        "# Architecture Review",
        "",
        f"- Goal: {goal or 'n/a'}",
        "",
        "## Scope Challenge",
        *[f"- {item}" for item in _build_scope_challenge(primary_files, secondary_files, subtasks)],
        "",
        "## Proposed Execution Shape",
        *[f"- {item}" for item in architecture_summary],
        "",
        "## Architecture Diagram",
        "```text",
        *architecture_diagram,
        "```",
        "",
        "## Data Flow",
        *[f"- {item}" for item in data_flow],
        "",
        "## Boundaries",
        *[f"- {item}" for item in boundaries],
        "",
        "## File Scope",
    ]
    report_lines.extend([f"- {item}" for item in primary_files] or ["- No primary files declared."])
    report_lines.extend(
        [
            "",
            "## Secondary Context",
        ]
    )
    report_lines.extend([f"- {item}" for item in secondary_files] or ["- No secondary files declared."])
    report_lines.extend(
        [
            "",
            "## Edge Cases",
            *[f"- {item}" for item in edge_cases],
            "",
            "## Failure Modes",
        ]
    )
    report_lines.extend(
        [
            f"- {item['path']}: {item['failure']} | handling={item['handling']} | verify={item['verification']}"
            for item in failure_modes
        ]
        or ["- No explicit failure modes were inferred."]
    )
    report_lines.extend(
        [
            "",
            "## Verification Plan",
        ]
    )
    report_lines.extend(
        [f"- {item}" for item in verification_basis]
        or ["- Verification basis not specified; rely on acceptance criteria and workflow defaults."]
    )
    report_lines.extend(
        [
            "",
            "## Suggested Test Layers",
            *[f"- {item}" for item in _flatten_test_layers(test_plan)],
            "",
            "## QA Handoff",
            *[f"- {item}" for item in qa_handoff_lines],
            "",
            "## Open Planning Questions",
            *(
                [f"- {item['question']} | why={item['why_it_matters']}" for item in open_questions]
                or ["- None."]
            ),
            "",
            "## Auto-Resolved Assumptions",
            *(
                [f"- {item['id']}: {item['assumption']}" for item in auto_resolved_questions]
                or ["- None."]
            ),
            "",
            "## Approval / Resume",
            (
                f"- Next question: {next_question['question']}"
                if next_question
                else "- Planning package is ready to hand to builder and QA."
            ),
            "- Resume mode: plan-eng-review",
            "- Handoff target: builder",
            "",
            "## Builder Guidance",
            "- Keep edits inside the declared primary files unless a missing dependency blocks acceptance.",
            "- Preserve current repository patterns before introducing new abstractions.",
            "- Hand every risky assumption forward through review artifacts and acceptance notes.",
        ]
    )
    report = "\n".join(report_lines).strip() + "\n"

    report_path = review_dir / "architecture_review_report.md"
    report_path.write_text(report, encoding="utf-8")
    test_plan_path = review_dir / "test_plan.json"
    test_plan_path.write_text(json.dumps(test_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    failure_modes_path = review_dir / "failure_modes.json"
    failure_modes_path.write_text(json.dumps(failure_modes, ensure_ascii=False, indent=2), encoding="utf-8")
    qa_test_plan_path = review_dir / "qa_test_plan.md"
    qa_test_plan_path.write_text(
        _render_qa_test_plan(
            goal=goal,
            primary_files=primary_files,
            story_outputs=story_outputs,
            verification_basis=verification_basis,
            edge_cases=edge_cases,
            failure_modes=failure_modes,
        ),
        encoding="utf-8",
    )
    planning_decision_state_path = review_dir / "planning_decision_state.json"
    planning_decision_state_path.write_text(
        json.dumps(planning_decision_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    shared_blackboard = dict(state.get("shared_blackboard") or {})
    shared_blackboard["architecture_review"] = {
        "summary": architecture_summary,
        "data_flow": data_flow,
        "boundaries": boundaries,
        "edge_cases": edge_cases,
        "failure_modes_ref": str(failure_modes_path),
        "test_plan_ref": str(test_plan_path),
        "qa_test_plan_ref": str(qa_test_plan_path),
        "planning_decision_state_ref": str(planning_decision_state_path),
        "open_questions": open_questions,
    }

    state["architecture_review_success"] = True
    state["architecture_review_dir"] = str(review_dir)
    state["architecture_review_report"] = report
    state["architecture_review_summary"] = architecture_summary[0] if architecture_summary else ""
    state["architecture_test_plan"] = {
        **test_plan,
        "boundaries": boundaries,
        "failure_modes": failure_modes,
        "qa_handoff": qa_handoff_lines,
    }
    state["qa_test_plan_path"] = str(qa_test_plan_path)
    state["shared_blackboard"] = shared_blackboard
    state["awaiting_user_input"] = bool(open_questions)
    state["dialogue_state"] = planning_decision_state
    state["next_question"] = next_question
    state["approval_required"] = bool(open_questions)
    state["handoff_target"] = "builder"
    state["resume_from_mode"] = "plan-eng-review" if open_questions else None
    state["decision_state"] = planning_decision_state
    state["interaction_round"] = len(open_questions)
    state["current_step"] = "architecture_review_done"
    state["error_message"] = None
    add_executed_mode(state, "plan-eng-review")

    task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.ARCHITECTURE_REVIEW,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did="Converted the parsed story requirement into an implementation-oriented architecture review, edge-case list, and test plan.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Architecture Review Report",
                    type="report",
                    path=f".meta/{task_scope_name}/architecture_review/architecture_review_report.md",
                    description="Implementation-oriented architecture and risk review for the current story.",
                    created_by=AgentRole.ARCHITECTURE_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Architecture Test Plan",
                    type="report",
                    path=f".meta/{task_scope_name}/architecture_review/test_plan.json",
                    description="Structured test layers and risk checks for downstream validation.",
                    created_by=AgentRole.ARCHITECTURE_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="QA Test Plan",
                    type="report",
                    path=f".meta/{task_scope_name}/architecture_review/qa_test_plan.md",
                    description="Route and interaction-focused QA handoff derived from the engineering review.",
                    created_by=AgentRole.ARCHITECTURE_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Planning Decision State",
                    type="report",
                    path=f".meta/{task_scope_name}/architecture_review/planning_decision_state.json",
                    description="Pause/resume state for unresolved plan-eng-review questions and builder/QA handoff context.",
                    created_by=AgentRole.ARCHITECTURE_REVIEW,
                ),
            ],
            what_risks_i_found=[item["failure"] for item in failure_modes] or edge_cases,
            what_i_require_next=(
                "Answer the unresolved plan-eng-review question(s), then resume engineering planning before build starts."
                if open_questions
                else "Implement against the approved file scope, preserve the stated boundaries, and treat the QA test plan as mandatory input for test and QA verification."
            ),
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print("[Architecture Review Agent] Plan recorded")
    return state


def route_after_architecture_review(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "architecture_review":
        return "__end__"
    if state.get("awaiting_user_input") and str(state.get("resume_from_mode") or "").strip() == "plan-eng-review":
        return "__end__"
    if str(state.get("bug_scope") or "").strip() and not state.get("investigate_success"):
        return "investigate"
    if _should_setup_browser_session(state):
        return "setup_browser_cookies"
    if state.get("has_browser_surface") and str(state.get("story_kind") or "") in {"ui", "mixed"}:
        return "browse"
    if state.get("needs_design_review"):
        return "plan_design_review"
    return "workspace_prep"


def _is_non_interactive_auto_run(state: DevState) -> bool:
    task_payload = state.get("task_payload") or {}
    interaction_policy = str(state.get("interaction_policy") or task_payload.get("interaction_policy") or "").strip().lower()
    return bool(state.get("auto_run") or task_payload.get("auto_run")) or interaction_policy == "non_interactive_auto_run"


def _auto_resolve_open_planning_questions(
    open_questions: list[dict[str, str]],
    *,
    goal: str,
    acceptance: list[str],
    verification_basis: list[str],
    primary_files: list[str],
    story_inputs: list[str],
    story_outputs: list[str],
) -> list[dict[str, str]]:
    if not open_questions:
        return []
    defaults = {
        "goal": goal or "Deliver the smallest implementation that satisfies the declared story goal without widening scope.",
        "acceptance": "; ".join(acceptance) if acceptance else "Use the current acceptance checklist and do not expand it automatically.",
        "verification_basis": "; ".join(verification_basis) if verification_basis else "Capture deterministic test evidence and QA artifacts for the declared primary files.",
        "file_scope": ", ".join(primary_files) if primary_files else "Stay inside the files already listed in the story card or generated plan artifacts.",
        "flow_contract": "; ".join([*(story_inputs or []), *(story_outputs or [])]) if story_inputs or story_outputs else "Preserve existing inputs and only add the smallest output surface needed for acceptance.",
    }
    return [
        {
            "id": str(item.get("id") or "").strip(),
            "question": str(item.get("question") or "").strip(),
            "why_it_matters": str(item.get("why_it_matters") or "").strip(),
            "assumption": defaults.get(str(item.get("id") or "").strip(), "Apply the most conservative assumption and keep scope narrow."),
        }
        for item in open_questions
    ]


def _should_setup_browser_session(state: DevState) -> bool:
    return bool(
        state.get("requires_auth")
        and state.get("has_browser_surface")
        and not state.get("setup_browser_cookies_success")
    )


def _clean_lines(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _normalize_subtasks(raw_subtasks: Any) -> list[dict[str, Any]]:
    subtasks: list[dict[str, Any]] = []
    if not isinstance(raw_subtasks, list):
        return subtasks
    for item in raw_subtasks:
        if hasattr(item, "model_dump"):
            subtasks.append(dict(item.model_dump(mode="json")))
        elif isinstance(item, dict):
            subtasks.append(dict(item))
    return subtasks


def _build_architecture_summary(
    subtasks: list[dict[str, Any]],
    primary_files: list[str],
    secondary_files: list[str],
) -> list[str]:
    summary: list[str] = []
    if subtasks:
        kinds = sorted({str(item.get("type") or "unknown") for item in subtasks})
        summary.append(f"Decompose the story into {len(subtasks)} execution tracks: {', '.join(kinds)}.")
    if primary_files:
        summary.append(f"Primary change scope stays within {len(primary_files)} declared file targets.")
    if secondary_files:
        summary.append(f"Secondary context is read-only by default and should only be touched if acceptance is blocked.")
    if not summary:
        summary.append("No explicit execution tracks were declared; keep the implementation narrow and evidence-driven.")
    return summary


def _build_scope_challenge(
    primary_files: list[str],
    secondary_files: list[str],
    subtasks: list[dict[str, Any]],
) -> list[str]:
    scope_lines: list[str] = []
    if primary_files:
        scope_lines.append(f"Keep the implementation inside these primary files first: {', '.join(primary_files[:4])}.")
    if secondary_files:
        scope_lines.append("Treat secondary files as read-only context until a hard blocker proves otherwise.")
    if subtasks:
        scope_lines.append(f"Existing execution already decomposes into {len(subtasks)} task tracks; reuse those tracks instead of inventing new ones.")
    if not scope_lines:
        scope_lines.append("No file scope was declared, so the plan must stay minimal and evidence-driven.")
    return scope_lines


def _build_data_flow(
    story_inputs: list[str],
    subtasks: list[dict[str, Any]],
    story_outputs: list[str],
    primary_files: list[str],
) -> list[str]:
    flow: list[str] = []
    if story_inputs:
        flow.append(f"Inputs enter through: {', '.join(story_inputs)}.")
    if subtasks:
        flow.append(
            "Execution fans out through role-specific tracks: "
            + ", ".join(f"{item.get('type')}[{', '.join(item.get('files_to_modify') or []) or 'unspecified'}]" for item in subtasks)
            + "."
        )
    elif primary_files:
        flow.append(f"Execution stays linear against the declared file scope: {', '.join(primary_files)}.")
    if story_outputs:
        flow.append(f"Expected outputs converge into: {', '.join(story_outputs)}.")
    if not flow:
        flow.append("No explicit input/output map was declared; validate output shape directly against the acceptance checklist.")
    return flow


def _build_architecture_diagram(
    story_inputs: list[str],
    subtasks: list[dict[str, Any]],
    story_outputs: list[str],
    primary_files: list[str],
) -> list[str]:
    input_label = ", ".join(story_inputs[:2]) or "story input"
    track_label = ", ".join(str(item.get("type") or "track") for item in subtasks[:3]) or "implementation track"
    file_label = ", ".join(primary_files[:2]) or "primary files"
    output_label = ", ".join(story_outputs[:2]) or "accepted output"
    return [
        f"[ {input_label} ]",
        "        |",
        "        v",
        f"[ {track_label} ]",
        "        |",
        "        v",
        f"[ {file_label} ]",
        "        |",
        "        v",
        f"[ {output_label} ]",
    ]


def _build_boundaries(
    primary_files: list[str],
    secondary_files: list[str],
    constraints: list[str],
    not_do: list[str],
) -> list[str]:
    boundaries: list[str] = []
    if primary_files:
        boundaries.append("Only the declared primary files should be modified during the first implementation pass.")
    if secondary_files:
        boundaries.append("Secondary files may be read for context but should not be edited unless acceptance is blocked.")
    for item in constraints[:3]:
        boundaries.append(f"Constraint boundary: {item}")
    for item in not_do[:2]:
        boundaries.append(f"Do-not-cross boundary: {item}")
    if not boundaries:
        boundaries.append("Do not expand scope without new evidence that the requested outcome is blocked.")
    return boundaries


def _build_edge_cases(
    acceptance: list[str],
    constraints: list[str],
    not_do: list[str],
    primary_files: list[str],
) -> list[str]:
    edge_cases: list[str] = []
    for item in acceptance[:4]:
        edge_cases.append(f"Acceptance edge case: {item}")
    for item in constraints[:3]:
        edge_cases.append(f"Constraint must hold: {item}")
    for item in not_do[:2]:
        edge_cases.append(f"Explicitly avoid: {item}")
    if primary_files and any(path.endswith((".tsx", ".jsx", ".html")) for path in primary_files):
        edge_cases.append("Frontend changes should guard against blank states, missing data, and layout breakage.")
    if primary_files and any(path.endswith((".py", ".ts", ".sql")) for path in primary_files):
        edge_cases.append("Code changes should preserve import paths, data contracts, and existing command entrypoints.")
    if not edge_cases:
        edge_cases.append("Keep the blast radius limited to the declared scope and verify no hidden dependency was introduced.")
    return edge_cases


def _build_failure_modes(
    data_flow: list[str],
    edge_cases: list[str],
    test_plan: dict[str, Any],
) -> list[dict[str, str]]:
    failure_modes: list[dict[str, str]] = []
    for index, item in enumerate(edge_cases[:4], start=1):
        verification_candidates = test_plan.get("integration_checks") if isinstance(test_plan, dict) else []
        verification = (
            verification_candidates[index - 1]
            if isinstance(verification_candidates, list) and len(verification_candidates) >= index
            else "Re-run the acceptance path and inspect the resulting artifact."
        )
        failure_modes.append(
            {
                "path": f"path-{index}",
                "failure": item,
                "handling": "Catch in build review, then verify with QA before acceptance.",
                "verification": str(verification),
            }
        )
    if not failure_modes:
        for index, item in enumerate(data_flow[:2], start=1):
            failure_modes.append(
                {
                    "path": f"flow-{index}",
                    "failure": f"Data flow could break at: {item}",
                    "handling": "Check the transition manually and keep the blast radius narrow.",
                    "verification": "Confirm the expected output still matches the acceptance checklist.",
                }
            )
    return failure_modes


def _build_test_plan(
    verification_basis: list[str],
    acceptance: list[str],
    primary_files: list[str],
    subtasks: list[dict[str, Any]],
    edge_cases: list[str],
) -> dict[str, Any]:
    file_targets = primary_files or [item for task in subtasks for item in task.get("files_to_modify") or []]
    unit_checks = [f"Validate targeted behavior in {path}." for path in file_targets[:4]]
    integration_checks = [f"Confirm the end-to-end requirement for: {item}" for item in acceptance[:4]]
    manual_checks = [f"Use acceptance evidence to inspect: {item}" for item in verification_basis[:4]]
    risk_checks = edge_cases[:5]
    return {
        "unit_checks": unit_checks or ["No file-specific unit checks were declared."],
        "integration_checks": integration_checks or ["No explicit integration checks were declared."],
        "manual_checks": manual_checks or ["Review downstream artifacts and workflow reports for requirement fit."],
        "risk_checks": risk_checks or ["No additional risk checks were inferred."],
    }


def _build_qa_handoff(
    acceptance: list[str],
    verification_basis: list[str],
    edge_cases: list[str],
    failure_modes: list[dict[str, str]],
) -> list[str]:
    handoff: list[str] = []
    for item in acceptance[:3]:
        handoff.append(f"Acceptance path to verify: {item}")
    for item in verification_basis[:3]:
        handoff.append(f"QA evidence to capture: {item}")
    for item in edge_cases[:2]:
        handoff.append(f"Edge case to force during QA: {item}")
    for item in failure_modes[:2]:
        handoff.append(f"Failure mode to guard: {item['failure']}")
    if not handoff:
        handoff.append("QA should validate the primary story outcome and the highest-risk boundary.")
    return handoff


def _build_open_planning_questions(
    *,
    goal: str,
    acceptance: list[str],
    verification_basis: list[str],
    primary_files: list[str],
    story_inputs: list[str],
    story_outputs: list[str],
) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    if not goal:
        questions.append(
            {
                "id": "goal",
                "question": "What is the single engineering outcome this story must guarantee before build starts?",
                "why_it_matters": "Without a stable engineering target, file scope and QA handoff will drift.",
            }
        )
    if not acceptance:
        questions.append(
            {
                "id": "acceptance",
                "question": "Which acceptance criteria are mandatory for this story to count as done?",
                "why_it_matters": "Plan-eng-review should lock done conditions before the builder starts changing code.",
            }
        )
    if not verification_basis:
        questions.append(
            {
                "id": "verification_basis",
                "question": "What concrete verification evidence should QA and acceptance capture for this story?",
                "why_it_matters": "A missing verification basis weakens QA handoff and later acceptance gates.",
            }
        )
    if not primary_files:
        questions.append(
            {
                "id": "file_scope",
                "question": "Which primary files are approved for the first implementation pass?",
                "why_it_matters": "The builder needs an approved change boundary before touching the repo.",
            }
        )
    if not story_outputs and not story_inputs:
        questions.append(
            {
                "id": "flow_contract",
                "question": "What are the key inputs and outputs this story must preserve or produce?",
                "why_it_matters": "Data flow and failure-mode analysis are weaker until the story contract is explicit.",
            }
        )
    return questions


def _render_qa_test_plan(
    *,
    goal: str,
    primary_files: list[str],
    story_outputs: list[str],
    verification_basis: list[str],
    edge_cases: list[str],
    failure_modes: list[dict[str, str]],
) -> str:
    affected_routes = _infer_routes_from_files(primary_files)
    lines = [
        "# QA Test Plan",
        "",
        "Generated by /plan-eng-review",
        f"Goal: {goal or 'n/a'}",
        "",
        "## Affected Pages/Routes",
        *([f"- {item}" for item in affected_routes] or ["- No route could be inferred from the current file scope."]),
        "",
        "## Key Interactions to Verify",
        *([f"- {item}" for item in verification_basis] or ["- Re-run the main user-facing flow and capture evidence."]),
        "",
        "## Edge Cases",
        *([f"- {item}" for item in edge_cases] or ["- No explicit edge cases were inferred."]),
        "",
        "## Critical Paths",
        *([f"- {item}" for item in story_outputs] or ["- Validate that the final story output matches the acceptance checklist."]),
        "",
        "## Failure Modes",
        *([f"- {item['failure']}" for item in failure_modes] or ["- No explicit failure modes were inferred."]),
        "",
    ]
    return "\n".join(lines)


def _infer_routes_from_files(primary_files: list[str]) -> list[str]:
    routes: list[str] = []
    for path in primary_files:
        normalized = str(path).replace("\\", "/")
        if "page.tsx" in normalized:
            fragment = normalized.split("/src/", 1)[-1]
            route = fragment.replace("/page.tsx", "").replace("/app", "").replace("(dashboard)", "").strip("/")
            route = "/" + route if route else "/"
            if route not in routes:
                routes.append(route)
        elif normalized.endswith(".html"):
            route = "/" + Path(normalized).stem
            if route not in routes:
                routes.append(route)
    return routes


def _flatten_test_layers(test_plan: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for label in ("unit_checks", "integration_checks", "manual_checks", "risk_checks"):
        values = test_plan.get(label) if isinstance(test_plan, dict) else []
        if isinstance(values, list):
            lines.extend(f"{label}: {item}" for item in values[:3])
    return lines or ["No structured test layers were generated."]
