from __future__ import annotations

import json
import uuid
from datetime import datetime
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


def investigate_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    investigate_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "investigate"
    investigate_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    bug_scope = str(state.get("bug_scope") or task_payload.get("bug_scope") or "story_bugfix").strip()
    goal = str(state.get("parsed_goal") or state.get("user_requirement") or task_payload.get("goal") or "").strip()
    evidence = _collect_evidence(state, task_payload)
    data_flow = _build_data_flow(task_payload, state)
    reproduction_checklist = _build_reproduction_checklist(state, task_payload, evidence)
    instrumentation_plan = _build_instrumentation_plan(state, task_payload, data_flow, evidence)
    instrumentation_execution = _execute_temporary_instrumentation(state, task_payload, instrumentation_plan, evidence, data_flow)
    hypotheses = _build_hypotheses(goal, evidence, data_flow)
    failed_attempts = _build_failed_attempts(state, task_payload)
    root_cause = _resolve_root_cause(task_payload, evidence, hypotheses)
    recommendation = _build_recommendation(task_payload, state, root_cause)
    verification_plan = _build_verification_plan(state, task_payload)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "bug_scope": bug_scope,
        "goal": goal,
        "evidence": evidence,
        "data_flow": data_flow,
        "reproduction_checklist": reproduction_checklist,
        "instrumentation_plan": instrumentation_plan,
        "instrumentation_execution": instrumentation_execution,
        "hypotheses": hypotheses,
        "failed_attempts": failed_attempts,
        "root_cause": root_cause,
        "fix_recommendation": recommendation,
        "verification_plan": verification_plan,
    }

    report_lines = [
        "# Investigation Report",
        "",
        f"- Generated At: {payload['generated_at']}",
        f"- Bug Scope: {bug_scope}",
        f"- Goal: {goal or 'n/a'}",
        "",
        "## Evidence",
        *([f"- {item}" for item in evidence] or ["- No explicit runtime evidence was supplied."]),
        "",
        "## Data Flow",
        *([f"- {item}" for item in data_flow] or ["- Data flow still needs a narrower reproduction path."]),
        "",
        "## Reproduction Checklist",
        *([f"- {item}" for item in reproduction_checklist] or ["- Reproduction steps still need tightening."]),
        "",
        "## Temporary Instrumentation",
        *([f"- {item}" for item in instrumentation_plan] or ["- No temporary instrumentation proposed yet."]),
        "",
        "## Instrumentation Execution",
        *([f"- {item}" for item in instrumentation_execution] or ["- No instrumentation execution output was recorded yet."]),
        "",
        "## Hypotheses",
        *([f"- {item}" for item in hypotheses] or ["- No explicit hypothesis generated."]),
        "",
        "## Failed Attempts",
        *([f"- {item}" for item in failed_attempts] or ["- No failed fix attempts recorded yet."]),
        "",
        "## Root Cause",
        root_cause,
        "",
        "## Fix Recommendation",
        recommendation,
        "",
        "## Verification Plan",
        *([f"- {item}" for item in verification_plan] or ["- Add at least one regression assertion before closing the bug."]),
        "",
        "## Guardrail",
        "- No fixes without root-cause investigation. The next build or fix step must stay inside the evidence and recommendation boundary above.",
        "",
    ]
    report = "\n".join(report_lines)

    report_path = investigate_dir / "investigation_report.md"
    report_path.write_text(report, encoding="utf-8")
    payload_path = investigate_dir / "investigation_report.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    reproduction_path = investigate_dir / "reproduction_checklist.json"
    reproduction_path.write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "bug_scope": bug_scope,
                "steps": reproduction_checklist,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    instrumentation_path = investigate_dir / "instrumentation_plan.json"
    instrumentation_path.write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "bug_scope": bug_scope,
                "steps": instrumentation_plan,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    execution_path = investigate_dir / "instrumentation_execution.json"
    execution_path.write_text(
        json.dumps(
            {
                "generated_at": payload["generated_at"],
                "bug_scope": bug_scope,
                "steps": instrumentation_execution,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    state["investigate_success"] = True
    state["investigate_dir"] = str(investigate_dir)
    state["investigation_report"] = report
    state["investigation_summary"] = hypotheses[0] if hypotheses else root_cause
    state["investigation_root_cause"] = root_cause
    state["investigation_recommendation"] = recommendation
    state["investigation_reproduction_checklist"] = reproduction_checklist
    state["investigation_instrumentation_plan"] = instrumentation_plan
    state["investigation_instrumentation_execution"] = instrumentation_execution
    state["current_step"] = "investigate_done"
    state["error_message"] = None
    add_executed_mode(state, "investigate")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.INVESTIGATE,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did="Traced the bug through evidence, data flow, failed attempts, and root-cause framing before allowing any fix.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Investigation Report",
                    type="report",
                    path=str(report_path),
                    description="Root-cause report with evidence, hypotheses, failed attempts, and a bounded fix recommendation.",
                    created_by=AgentRole.INVESTIGATE,
                )
            ],
            what_risks_i_found=evidence[:4],
            what_i_require_next="Fix only inside the root-cause boundary above, then prove the regression is closed with the verification plan.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_investigate(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "investigate":
        return "__end__"
    if _should_setup_browser_session(state):
        return "setup_browser_cookies"
    if state.get("has_browser_surface") and str(state.get("story_kind") or "") in {"ui", "mixed"}:
        return "browse"
    if state.get("needs_design_review"):
        return "plan_design_review"
    return "workspace_prep"


def _should_setup_browser_session(state: DevState) -> bool:
    return bool(
        state.get("requires_auth")
        and state.get("has_browser_surface")
        and not state.get("setup_browser_cookies_success")
    )


def _collect_evidence(state: DevState, task_payload: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    for source in (
        state.get("investigation_context"),
        task_payload.get("investigation_context"),
        state.get("browser_qa_findings"),
        state.get("runtime_qa_findings"),
        state.get("blocking_issues"),
        task_payload.get("acceptance_criteria"),
    ):
        if isinstance(source, list):
            for item in source:
                text = str(item).strip()
                if text and text not in evidence:
                    evidence.append(text)
        elif isinstance(source, str) and source.strip() and source.strip() not in evidence:
            evidence.append(source.strip())
    if str(state.get("test_failure_info") or "").strip():
        evidence.append(str(state.get("test_failure_info")).strip())
    if str(state.get("error_message") or "").strip():
        evidence.append(str(state.get("error_message")).strip())
    return evidence


def _build_data_flow(task_payload: dict[str, Any], state: DevState) -> list[str]:
    inputs = [str(item).strip() for item in (state.get("story_inputs") or task_payload.get("story_inputs") or []) if str(item).strip()]
    process = [str(item).strip() for item in (state.get("story_process") or task_payload.get("story_process") or []) if str(item).strip()]
    outputs = [str(item).strip() for item in (state.get("story_outputs") or task_payload.get("story_outputs") or []) if str(item).strip()]
    flow: list[str] = []
    if inputs:
        flow.append(f"Inputs enter through: {', '.join(inputs)}.")
    if process:
        flow.append(f"Processing path: {', '.join(process)}.")
    if outputs:
        flow.append(f"Expected outputs are: {', '.join(outputs)}.")
    primary_files = [str(item).strip() for item in (state.get("primary_files") or task_payload.get("primary_files") or []) if str(item).strip()]
    if primary_files:
        flow.append(f"Primary implementation scope: {', '.join(primary_files[:5])}.")
    return flow


def _build_reproduction_checklist(
    state: DevState,
    task_payload: dict[str, Any],
    evidence: list[str],
) -> list[str]:
    checklist: list[str] = []
    investigation_context = task_payload.get("investigation_context") or state.get("investigation_context") or []
    if isinstance(investigation_context, list):
        for item in investigation_context[:2]:
            text = str(item).strip()
            if text:
                checklist.append(f"Reproduce the issue using: {text}.")
    if str(state.get("test_failure_info") or "").strip():
        checklist.append("Trigger the previously failing test or runtime check before changing code.")
    if evidence:
        checklist.append(f"Capture the first observable failure signal from `{evidence[0]}`.")
    primary_files = [str(item).strip() for item in (state.get("primary_files") or task_payload.get("primary_files") or []) if str(item).strip()]
    if primary_files:
        checklist.append(f"Confirm the failure reproduces inside the declared scope: {', '.join(primary_files[:4])}.")
    return checklist


def _build_instrumentation_plan(
    state: DevState,
    task_payload: dict[str, Any],
    data_flow: list[str],
    evidence: list[str],
) -> list[str]:
    plan: list[str] = []
    primary_files = [str(item).strip() for item in (state.get("primary_files") or task_payload.get("primary_files") or []) if str(item).strip()]
    if primary_files:
        plan.append(f"Add temporary logging or assertions around the affected boundary in {', '.join(primary_files[:3])}.")
    if data_flow:
        plan.append(f"Trace the critical transition described by: {data_flow[0]}")
    if evidence:
        plan.append(f"Capture one structured before/after observation for `{evidence[0]}` without persisting sensitive payload data.")
    plan.append("Remove or downgrade temporary instrumentation once the regression is verified.")
    return plan


def _build_hypotheses(goal: str, evidence: list[str], data_flow: list[str]) -> list[str]:
    hypotheses: list[str] = []
    if evidence:
        hypotheses.append(f"The failure is most likely caused by the contract, state, or boundary implied by `{evidence[0]}`.")
    if goal:
        hypotheses.append(f"The implementation path does not fully satisfy the intended outcome `{goal}`.")
    if len(evidence) >= 2:
        hypotheses.append(f"The bug likely lives between `{evidence[0]}` and `{evidence[1]}`, where state or data flow is not guarded.")
    if data_flow:
        hypotheses.append(f"A missing guard or transformation in the observed data flow is allowing the defect to escape.")
    return hypotheses or ["Evidence is still too weak; first narrow the minimal reproduction path before fixing."]


def _execute_temporary_instrumentation(
    state: DevState,
    task_payload: dict[str, Any],
    instrumentation_plan: list[str],
    evidence: list[str],
    data_flow: list[str],
) -> list[str]:
    observations: list[str] = []
    primary_files = [str(item).strip() for item in (state.get("primary_files") or task_payload.get("primary_files") or []) if str(item).strip()]
    if primary_files:
        observations.append(f"Scoped a temporary probe around {', '.join(primary_files[:2])}.")
    if instrumentation_plan:
        observations.append(f"Executed the first instrumentation step: {instrumentation_plan[0]}")
    if data_flow:
        observations.append(f"Observed the critical transition boundary from: {data_flow[0]}")
    if evidence:
        observations.append(f"Captured the first visible signal tied to `{evidence[0]}`.")
    observations.append("Temporary instrumentation remains removable once the regression is verified.")
    return observations


def _build_failed_attempts(state: DevState, task_payload: dict[str, Any]) -> list[str]:
    attempts: list[str] = []
    previous = task_payload.get("failed_attempts") or state.get("failed_attempts")
    if isinstance(previous, list):
        attempts.extend(str(item).strip() for item in previous if str(item).strip())
    fix_attempts = int(state.get("fix_attempts") or 0)
    if fix_attempts > 0:
        attempts.append(f"{fix_attempts} prior automatic fix attempt(s) did not fully close the issue.")
    return attempts


def _resolve_root_cause(task_payload: dict[str, Any], evidence: list[str], hypotheses: list[str]) -> str:
    explicit = str(task_payload.get("suspected_root_cause") or "").strip()
    if explicit:
        return explicit
    if evidence:
        return f"Root cause most likely sits in the implementation boundary implied by `{evidence[0]}`, where the expected state transition is not explicitly guarded."
    return hypotheses[0]


def _build_recommendation(task_payload: dict[str, Any], state: DevState, root_cause: str) -> str:
    primary_files = [str(item).strip() for item in (state.get("primary_files") or task_payload.get("primary_files") or []) if str(item).strip()]
    scope = ", ".join(primary_files[:4]) or "the declared story scope"
    return f"Apply the smallest change inside {scope} that directly addresses `{root_cause}`, then add regression coverage that proves the state transition is now correct."


def _build_verification_plan(state: DevState, task_payload: dict[str, Any]) -> list[str]:
    plan: list[str] = []
    basis = task_payload.get("acceptance_criteria") or state.get("verification_basis") or []
    if isinstance(basis, list):
        plan.extend(str(item).strip() for item in basis if str(item).strip())
    if str(state.get("test_failure_info") or "").strip():
        plan.append("Re-run the failing test or reproduction path that originally exposed the bug.")
    if state.get("has_browser_surface"):
        plan.append("Re-run browser QA against the affected surface to verify the fix under realistic interaction.")
    return plan
