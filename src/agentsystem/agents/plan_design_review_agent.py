from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agentsystem.agents.design_review_framework import (
    DIMENSIONS,
    aggregate_dimension_scores,
    build_design_contract,
    resolve_route_scope,
    score_route,
    select_benchmark_profile,
)
from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_executed_mode,
    add_handoff_packet,
)


def plan_design_review_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    review_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "plan_design_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    review_mode = str(task_payload.get("review_mode") or "auto").strip() or "auto"
    current_observations = [
        item
        for item in ((state.get("browse_observations") or task_payload.get("browse_observations") or []))
        if isinstance(item, dict)
    ]
    reference_observations = [
        item
        for item in ((state.get("reference_observations") or task_payload.get("reference_observations") or []))
        if isinstance(item, dict)
    ]
    route_scope = resolve_route_scope(task_payload, repo_b_path, current_observations)
    benchmark = select_benchmark_profile(task_payload.get("design_benchmark"), route_scope)
    route_scores = [
        score_route(
            route,
            benchmark,
            current_observations=current_observations,
            reference_observations=reference_observations,
            review_mode=review_mode,
        )
        for route in route_scope
    ]
    overall_scores = aggregate_dimension_scores(route_scores)
    assumptions = _build_assumptions(task_payload, route_scope, benchmark["id"], review_mode)
    route_findings = _build_route_findings(route_scores)
    route_design_contract = _build_route_design_contract(route_scores, route_findings, benchmark["id"])
    design_risks = _build_design_risks(route_scores, route_findings)
    scorecard = {
        "review_mode": review_mode,
        "design_benchmark": benchmark["id"],
        "benchmark_label": benchmark["label"],
        "route_scope": route_scope,
        "assumptions": assumptions,
        "routes": route_scores,
        "overall_scores": overall_scores,
        "route_findings": route_findings,
        "route_design_contract": route_design_contract,
        "design_risks": design_risks,
    }

    report_path = review_dir / "design_review_report.md"
    report_path.write_text(
        _build_report(
            benchmark,
            route_scores,
            overall_scores,
            current_observations=current_observations,
            reference_observations=reference_observations,
            assumptions=assumptions,
            acceptance_criteria=_normalize_strings(task_payload.get("acceptance_criteria")),
            route_findings=route_findings,
        ),
        encoding="utf-8",
    )

    scorecard_path = review_dir / "design_scorecard.json"
    scorecard_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
    route_findings_path = review_dir / "route_findings.json"
    route_findings_path.write_text(json.dumps(route_findings, ensure_ascii=False, indent=2), encoding="utf-8")
    route_design_contract_path = review_dir / "route_design_contract.json"
    route_design_contract_path.write_text(json.dumps(route_design_contract, ensure_ascii=False, indent=2), encoding="utf-8")
    design_risks_path = review_dir / "design_risks.json"
    design_risks_path.write_text(json.dumps(design_risks, ensure_ascii=False, indent=2), encoding="utf-8")

    design_contract = build_design_contract(benchmark, route_scores, assumptions)
    design_contract_path = repo_b_path / "DESIGN.md"
    design_contract_path.write_text(design_contract, encoding="utf-8")

    state["plan_design_review_success"] = True
    state["plan_design_review_dir"] = str(review_dir)
    state["plan_design_review_report"] = report_path.read_text(encoding="utf-8")
    state["plan_design_scorecard"] = scorecard
    state["plan_design_assumptions"] = assumptions
    state["plan_design_route_findings"] = route_findings
    state["plan_design_route_contract"] = route_design_contract
    state["plan_design_risks"] = design_risks
    state["design_contract_path"] = str(design_contract_path)
    state["current_step"] = "plan_design_review_done"
    add_executed_mode(state, "plan-design-review")
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.PLAN_DESIGN_REVIEW,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did=(
                "Reviewed browse evidence, benchmark expectations, and route scope, then produced a route-aware design "
                "contract for downstream implementation."
            ),
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Plan Design Review Report",
                    type="report",
                    path=f".meta/{repo_b_path.name}/plan_design_review/design_review_report.md",
                    description="Route-aware plan design review report with benchmark fit, assumptions, and per-route scores.",
                    created_by=AgentRole.PLAN_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Design Scorecard",
                    type="report",
                    path=f".meta/{repo_b_path.name}/plan_design_review/design_scorecard.json",
                    description="Structured scorecard containing assumptions, route scope, and per-route dimension scores.",
                    created_by=AgentRole.PLAN_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Route Findings",
                    type="report",
                    path=f".meta/{repo_b_path.name}/plan_design_review/route_findings.json",
                    description="Route-level design risks and recommended fixes derived from the plan-design-review stage.",
                    created_by=AgentRole.PLAN_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Route Design Contract",
                    type="report",
                    path=f".meta/{repo_b_path.name}/plan_design_review/route_design_contract.json",
                    description="Route-level design contract with module, responsive, and regression expectations.",
                    created_by=AgentRole.PLAN_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="DESIGN.md",
                    type="document",
                    path="DESIGN.md",
                    description="Route-level design contract for builder and design-review stages.",
                    created_by=AgentRole.PLAN_DESIGN_REVIEW,
                ),
            ],
            what_risks_i_found=_collect_plan_risks(route_scores, overall_scores),
            what_i_require_next="Build against DESIGN.md, then rerun browse and design-review to verify each route.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_plan_design_review(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "plan_design_review":
        return "__end__"
    if state.get("needs_design_consultation") and not state.get("design_consultation_success"):
        return "design_consultation"
    return "workspace_prep"


def _build_report(
    benchmark: dict[str, Any],
    route_scores: list[dict[str, Any]],
    overall_scores: dict[str, dict[str, Any]],
    *,
    current_observations: list[dict[str, Any]],
    reference_observations: list[dict[str, Any]],
    assumptions: list[str],
    acceptance_criteria: list[str],
    route_findings: list[dict[str, Any]],
) -> str:
    lines = [
        "# Plan Design Review",
        "",
        f"- Benchmark: {benchmark['label']} (`{benchmark['id']}`)",
        f"- Current observations: {len(current_observations)}",
        f"- Reference observations: {len(reference_observations)}",
        "",
        "## Global Direction",
        *[f"- {item}" for item in benchmark.get("direction", [])],
        "",
        "## Assumptions",
        *([f"- {item}" for item in assumptions] if assumptions else ["- None."]),
        "",
    ]

    if acceptance_criteria:
        lines.extend(["## Acceptance Criteria", *[f"- {item}" for item in acceptance_criteria], ""])
    lines.extend(["## Route-Level Findings"])
    if route_findings:
        for item in route_findings:
            lines.append(f"- {item['route']}: {item['summary']}")
            for fix in item["recommended_fixes"]:
                lines.append(f"  fix: {fix}")
    else:
        lines.append("- No blocking route-level findings were identified in planning.")
    lines.append("")

    lines.extend(["## Overall Scores"])
    for dimension in DIMENSIONS:
        detail = overall_scores[dimension]
        lines.extend(
            [
                f"- {dimension}: {detail['score']}/10",
                f"  gap: {detail['gap']}",
                f"  target: {detail['ten_outcome']}",
                f"  fix: {detail['spec_fix']}",
            ]
        )

    for route_score in route_scores:
        lines.extend(
            [
                "",
                f"## Route {route_score['route']}",
                f"- Route kind: {route_score['route_kind']}",
                f"- Intent: {route_score['intent']}",
                f"- Modules: {', '.join(route_score['modules'])}",
                f"- Missing signals: {', '.join(route_score['missing_signals']) if route_score['missing_signals'] else 'None'}",
                "",
                "### Metrics",
            ]
        )
        for key, value in route_score["metrics"].items():
            lines.append(f"- {key}: {value}")

        lines.extend(["", "### Scores"])
        for dimension in DIMENSIONS:
            detail = route_score["dimensions"][dimension]
            lines.extend(
                [
                    f"- {dimension}: {detail['score']}/10",
                    f"  gap: {detail['gap']}",
                    f"  target: {detail['ten_outcome']}",
                    f"  fix: {detail['spec_fix']}",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def _build_assumptions(
    task_payload: dict[str, Any],
    route_scope: list[str],
    benchmark_id: str,
    review_mode: str,
) -> list[str]:
    assumptions = [
        f"Route scope: {', '.join(route_scope)}",
        f"Benchmark profile: {benchmark_id}",
        f"Review mode: {review_mode}",
    ]
    browser_urls = _normalize_strings(task_payload.get("browser_urls"))
    if browser_urls:
        assumptions.append("Route scope was inferred or confirmed from browser_urls.")
    if not task_payload.get("route_scope"):
        assumptions.append("No explicit route_scope was provided; the review used inferred routes.")
    return assumptions


def _collect_plan_risks(
    route_scores: list[dict[str, Any]],
    overall_scores: dict[str, dict[str, Any]],
) -> list[str]:
    risks: list[str] = []
    for dimension in DIMENSIONS:
        detail = overall_scores[dimension]
        if int(detail["score"]) < 8:
            risks.append(f"{dimension}: {detail['gap']}")
    if not risks:
        risks.append("No blocking plan-level design risks remain in the current scorecard.")
    return risks


def _build_route_findings(route_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for route_score in route_scores:
        low_dimensions = []
        recommended_fixes: list[str] = []
        for dimension in DIMENSIONS:
            detail = route_score["dimensions"][dimension]
            if int(detail["score"]) < 8:
                low_dimensions.append(dimension)
                fix = str(detail["spec_fix"]).strip()
                if fix and fix not in recommended_fixes:
                    recommended_fixes.append(fix)
        if not low_dimensions:
            continue
        findings.append(
            {
                "route": route_score["route"],
                "route_kind": route_score["route_kind"],
                "summary": f"Route needs improvement in {', '.join(low_dimensions)}.",
                "dimensions": low_dimensions,
                "recommended_fixes": recommended_fixes or ["Tighten the route against DESIGN.md and benchmark expectations."],
            }
        )
    return findings


def _build_route_design_contract(
    route_scores: list[dict[str, Any]],
    route_findings: list[dict[str, Any]],
    benchmark_id: str,
) -> dict[str, Any]:
    findings_by_route = {str(item.get("route") or ""): item for item in route_findings}
    routes: list[dict[str, Any]] = []
    for route_score in route_scores:
        route = str(route_score["route"])
        route_finding = findings_by_route.get(route) or {}
        routes.append(
            {
                "route": route,
                "route_kind": route_score["route_kind"],
                "benchmark": benchmark_id,
                "required_modules": list(route_score.get("modules") or []),
                "responsive_expectations": [
                    "Primary summary remains visible on narrow screens.",
                    "Dense evidence sections collapse into stacked blocks without losing labels.",
                ],
                "state_expectations": [
                    "Loading, empty, partial, and failure states remain explicit.",
                    "Main route thesis stays visible before detailed evidence blocks.",
                ],
                "forbidden_regressions": list(route_finding.get("dimensions") or []),
                "recommended_fixes": list(route_finding.get("recommended_fixes") or []),
            }
        )
    return {"benchmark": benchmark_id, "routes": routes}


def _build_design_risks(
    route_scores: list[dict[str, Any]],
    route_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_by_route = {str(item.get("route") or ""): item for item in route_findings}
    risks: list[dict[str, Any]] = []
    for route_score in route_scores:
        route = str(route_score["route"])
        route_finding = findings_by_route.get(route) or {}
        low_dimensions = [
            dimension
            for dimension, detail in route_score["dimensions"].items()
            if int(detail["score"]) < 8
        ]
        if not low_dimensions:
            continue
        risks.append(
            {
                "route": route,
                "severity": "important" if len(low_dimensions) == 1 else "blocking",
                "dimensions": low_dimensions,
                "summary": route_finding.get("summary")
                or f"{route} needs design fixes in {', '.join(low_dimensions)}.",
            }
        )
    return risks


def _normalize_strings(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
