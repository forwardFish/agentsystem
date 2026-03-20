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
    edge_cases = _build_edge_cases(acceptance, constraints, not_do, primary_files)
    test_plan = _build_test_plan(verification_basis, acceptance, primary_files, subtasks, edge_cases)

    report_lines = [
        "# Architecture Review",
        "",
        f"- Goal: {goal or 'n/a'}",
        "",
        "## Proposed Execution Shape",
        *[f"- {item}" for item in architecture_summary],
        "",
        "## Data Flow",
        *[f"- {item}" for item in data_flow],
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

    shared_blackboard = dict(state.get("shared_blackboard") or {})
    shared_blackboard["architecture_review"] = {
        "summary": architecture_summary,
        "data_flow": data_flow,
        "edge_cases": edge_cases,
        "test_plan_ref": str(test_plan_path),
    }

    state["architecture_review_success"] = True
    state["architecture_review_dir"] = str(review_dir)
    state["architecture_review_report"] = report
    state["architecture_review_summary"] = architecture_summary[0] if architecture_summary else ""
    state["architecture_test_plan"] = test_plan
    state["shared_blackboard"] = shared_blackboard
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
            ],
            what_risks_i_found=edge_cases,
            what_i_require_next="Implement against the approved file scope, cover the identified edge cases, and keep the suggested test layers in mind for validation.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print("[Architecture Review Agent] Plan recorded")
    return state


def route_after_architecture_review(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "architecture_review":
        return "__end__"
    if state.get("needs_design_review"):
        return "plan_design_review"
    return "workspace_prep"


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


def _flatten_test_layers(test_plan: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for label in ("unit_checks", "integration_checks", "manual_checks", "risk_checks"):
        values = test_plan.get(label) if isinstance(test_plan, dict) else []
        if isinstance(values, list):
            lines.extend(f"{label}: {item}" for item in values[:3])
    return lines or ["No structured test layers were generated."]
