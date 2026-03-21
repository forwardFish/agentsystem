from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agentsystem.agents.design_contracts import design_contract_path, read_if_exists
from agentsystem.agents.design_review_framework import (
    DIMENSIONS,
    aggregate_dimension_scores,
    build_findings_from_route_scores,
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
    Issue,
    IssueSeverity,
    add_executed_mode,
    add_handoff_packet,
    add_issue,
)


def qa_design_review_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    review_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "qa_design_review"
    review_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    browse_observations = [
        item
        for item in ((state.get("browse_observations") or task_payload.get("browse_observations") or []))
        if isinstance(item, dict)
    ]
    reference_observations = [
        item
        for item in ((state.get("reference_observations") or task_payload.get("reference_observations") or []))
        if isinstance(item, dict)
    ]
    design_contract = read_if_exists(design_contract_path(repo_b_path))
    primary_files = [str(item).strip() for item in (state.get("primary_files") or []) if str(item).strip()]
    review_mode = str(task_payload.get("review_mode") or "auto").strip() or "auto"
    route_scope = resolve_route_scope(task_payload, repo_b_path, browse_observations)
    benchmark = select_benchmark_profile(task_payload.get("design_benchmark"), route_scope)
    route_scores = [
        score_route(
            route,
            benchmark,
            current_observations=browse_observations,
            reference_observations=reference_observations,
            design_contract=design_contract,
            review_mode=review_mode,
        )
        for route in route_scope
    ]
    overall_scores = aggregate_dimension_scores(route_scores)
    findings = build_findings_from_route_scores(route_scores, primary_files)
    route_findings = _build_route_findings(route_scores, findings)
    visual_checklist = _build_visual_checklist(route_scores, findings)
    visual_verdict = _build_visual_verdict(overall_scores, findings, before_paths=[], after_paths=[])

    before_paths = [str(item).strip() for item in (state.get("before_screenshot_paths") or []) if str(item).strip()]
    after_paths = [str(item).strip() for item in (state.get("after_screenshot_paths") or []) if str(item).strip()]
    if not after_paths:
        after_paths = [
            str(item.get("screenshot_path") or "").strip()
            for item in browse_observations
            if str(item.get("screenshot_path") or "").strip()
        ]
    visual_verdict = _build_visual_verdict(overall_scores, findings, before_paths=before_paths, after_paths=after_paths)

    report_path = review_dir / "qa_design_review_report.md"
    report_path.write_text(
        _build_report(
            overall_scores,
            route_scores,
            findings,
            browser_health_score=state.get("browser_qa_health_score"),
            browser_warnings=_normalize_strings(state.get("browser_qa_warnings")),
            acceptance_criteria=_normalize_strings(task_payload.get("acceptance_criteria")),
            before_paths=before_paths,
            after_paths=after_paths,
            design_contract_present=bool(design_contract),
            route_findings=route_findings,
        ),
        encoding="utf-8",
    )

    before_after_path = review_dir / "before_after_report.md"
    before_after_path.write_text(
        "\n".join(
            [
                "# Before / After Evidence",
                "",
                "## Before",
                *([f"- {item}" for item in before_paths] or ["- None."]),
                "",
                "## After",
                *([f"- {item}" for item in after_paths] or ["- None."]),
            ]
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    score_bundle = {
        "benchmark": benchmark["id"],
        "route_scope": route_scope,
        "overall_scores": overall_scores,
        "route_scores": route_scores,
        "route_findings": route_findings,
    }
    score_path = review_dir / "design_scorecard.json"
    score_path.write_text(json.dumps(score_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    route_findings_path = review_dir / "route_findings.json"
    route_findings_path.write_text(json.dumps(route_findings, ensure_ascii=False, indent=2), encoding="utf-8")
    visual_checklist_path = review_dir / "visual_checklist.json"
    visual_checklist_path.write_text(json.dumps(visual_checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    visual_verdict_path = review_dir / "visual_verdict.json"
    visual_verdict_path.write_text(json.dumps(visual_verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    route_before_after_path = review_dir / "route_before_after.json"
    route_before_after_path.write_text(
        json.dumps(
            {
                "route_scope": route_scope,
                "before_paths": before_paths,
                "after_paths": after_paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    evidence_bundle_path = review_dir / "design_evidence_bundle.json"
    evidence_bundle_path.write_text(
        json.dumps(
            {
                "route_scope": route_scope,
                "before_paths": before_paths,
                "after_paths": after_paths,
                "browser_health_score": state.get("browser_qa_health_score"),
                "browser_warnings": _normalize_strings(state.get("browser_qa_warnings")),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    passed = all(int(item["score"]) >= 8 for item in overall_scores.values())
    state["qa_design_review_success"] = True
    state["qa_design_review_passed"] = passed
    state["qa_design_review_report"] = report_path.read_text(encoding="utf-8")
    state["qa_design_review_dir"] = str(review_dir)
    state["design_review_scores"] = overall_scores
    state["design_review_route_scores"] = route_scores
    state["design_review_findings"] = findings
    state["design_review_route_findings"] = route_findings
    state["design_review_visual_checklist"] = visual_checklist
    state["design_review_visual_verdict"] = visual_verdict
    state["design_review_passed"] = passed
    state["design_review_report"] = state["qa_design_review_report"]
    state["after_screenshot_paths"] = after_paths
    state["current_step"] = "qa_design_review_done"
    state["error_message"] = None if passed else "; ".join(item["description"] for item in findings if item["severity"] == "blocking")
    add_executed_mode(state, "qa-design-review")
    add_executed_mode(state, "design-review")

    issues: list[Issue] = []
    if not passed:
        for finding in findings:
            if finding["severity"] != "blocking":
                continue
            issue = Issue(
                issue_id=str(uuid.uuid4()),
                severity=IssueSeverity.BLOCKING,
                source_agent=AgentRole.QA_DESIGN_REVIEW,
                target_agent=AgentRole.FIXER,
                title=finding["title"],
                description=finding["description"],
                file_path=finding["file_path"] or None,
                suggestion=finding["spec_fix"],
            )
            add_issue(state, issue)
            issues.append(issue)

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.QA_DESIGN_REVIEW,
            to_agent=AgentRole.FIXER if issues else AgentRole.SECURITY_SCANNER,
            status=HandoffStatus.BLOCKED if issues else HandoffStatus.COMPLETED,
            what_i_did=(
                "Compared current route evidence, reference observations, and DESIGN.md requirements, then produced "
                "route-aware design review scores and fixable findings."
            ),
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Design Review Report",
                    type="report",
                    path=f".meta/{repo_b_path.name}/qa_design_review/qa_design_review_report.md",
                    description="Design review report with overall scores, route-level notes, evidence, and actionable findings.",
                    created_by=AgentRole.QA_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Before After Report",
                    type="report",
                    path=f".meta/{repo_b_path.name}/qa_design_review/before_after_report.md",
                    description="Before/after screenshot evidence used during the design review stage.",
                    created_by=AgentRole.QA_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Design Route Findings",
                    type="report",
                    path=f".meta/{repo_b_path.name}/qa_design_review/route_findings.json",
                    description="Route-level visual findings, grouped fixes, and score deltas from design review.",
                    created_by=AgentRole.QA_DESIGN_REVIEW,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Visual Checklist",
                    type="report",
                    path=f".meta/{repo_b_path.name}/qa_design_review/visual_checklist.json",
                    description="Dimension-by-dimension visual checklist and verdict for design review.",
                    created_by=AgentRole.QA_DESIGN_REVIEW,
                ),
            ],
            what_risks_i_found=[finding["description"] for finding in findings],
            what_i_require_next=(
                "Fix the blocking route-level design issues, then rerun browse and design-review."
                if issues
                else "Design review passed; continue into the remaining QA and acceptance chain."
            ),
            issues=issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_qa_design_review(state: DevState) -> str:
    if not state.get("qa_design_review_passed") and state.get("fixer_allowed", True) and state.get("fix_attempts", 0) < 3:
        state["fixer_allowed"] = True
        return "fixer"
    if str(state.get("stop_after") or "").strip() == "qa_design_review":
        return "__end__"
    return "security_scanner"


def _score_design_review(
    browse_observations: list[dict[str, Any]],
    reference_observations: list[dict[str, Any]],
    design_contract: str,
) -> dict[str, Any]:
    benchmark = select_benchmark_profile("product_directory")
    route_scope = resolve_route_scope({}, Path("."), browse_observations)
    route_scores = [
        score_route(
            route,
            benchmark,
            current_observations=browse_observations,
            reference_observations=reference_observations,
            design_contract=design_contract,
        )
        for route in route_scope
    ]
    return {"scores": aggregate_dimension_scores(route_scores), "route_scores": route_scores}


def _build_report(
    overall_scores: dict[str, dict[str, Any]],
    route_scores: list[dict[str, Any]],
    findings: list[dict[str, str]],
    *,
    browser_health_score: Any,
    browser_warnings: list[str],
    acceptance_criteria: list[str],
    before_paths: list[str],
    after_paths: list[str],
    design_contract_present: bool,
    route_findings: list[dict[str, Any]],
) -> str:
    lines = [
        "# Design Review",
        "",
        f"- Browser health score: {browser_health_score if browser_health_score is not None else '-'}",
        f"- Design contract: {'present' if design_contract_present else 'missing'}",
        "",
        "## Overall Scores",
    ]
    for dimension in DIMENSIONS:
        score = overall_scores[dimension]
        lines.extend(
            [
                f"- {dimension}: {score['score']}/10",
                f"  gap: {score['gap']}",
                f"  target: {score['ten_outcome']}",
                f"  fix: {score['spec_fix']}",
            ]
        )

    if acceptance_criteria:
        lines.extend(["", "## Acceptance Criteria", *[f"- {item}" for item in acceptance_criteria]])

    if browser_warnings:
        lines.extend(["", "## Browser QA Warnings", *[f"- {item}" for item in browser_warnings]])

    for route_score in route_scores:
        lines.extend(
            [
                "",
                f"## Route {route_score['route']}",
                f"- Route kind: {route_score['route_kind']}",
                f"- Intent: {route_score['intent']}",
                f"- Missing signals: {', '.join(route_score['missing_signals']) if route_score['missing_signals'] else 'None'}",
                "",
            ]
        )
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

    lines.extend(["", "## Before Screenshots", *([f"- {item}" for item in before_paths] or ["- None."])])
    lines.extend(["", "## After Screenshots", *([f"- {item}" for item in after_paths] or ["- None."])])
    lines.extend(["", "## Route-Level Findings"])
    if route_findings:
        for item in route_findings:
            lines.append(f"- {item['route']}: {item['summary']}")
            for fix in item["recommended_fixes"]:
                lines.append(f"  fix: {fix}")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Findings",
            *([f"- [{item['severity']}] {item['title']}: {item['description']}" for item in findings] or ["- None."]),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _normalize_strings(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _build_route_findings(
    route_scores: list[dict[str, Any]],
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    findings_by_route: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        route = str(finding.get("route") or "unknown").strip() or "unknown"
        findings_by_route.setdefault(route, []).append(finding)

    route_findings: list[dict[str, Any]] = []
    for route_score in route_scores:
        route = route_score["route"]
        route_specific = findings_by_route.get(route, [])
        low_dimensions = [
            dimension
            for dimension, detail in route_score["dimensions"].items()
            if int(detail["score"]) < 8
        ]
        if not route_specific and not low_dimensions:
            continue
        recommended_fixes = [
            str(item.get("spec_fix") or "").strip()
            for item in route_specific
            if str(item.get("spec_fix") or "").strip()
        ]
        if not recommended_fixes:
            recommended_fixes = [
                str(route_score["dimensions"][dimension]["spec_fix"]).strip()
                for dimension in low_dimensions
                if str(route_score["dimensions"][dimension]["spec_fix"]).strip()
            ]
        route_findings.append(
            {
                "route": route,
                "summary": f"Route has {len(route_specific)} finding(s) and low scores in {', '.join(low_dimensions) or 'no scored dimensions below threshold'}.",
                "finding_count": len(route_specific),
                "low_dimensions": low_dimensions,
                "recommended_fixes": recommended_fixes or ["Re-check the route against DESIGN.md and re-run browse evidence."],
            }
        )
    return route_findings


def _build_visual_checklist(
    route_scores: list[dict[str, Any]],
    findings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    dimensions = (
        "hierarchy",
        "navigation_clarity",
        "state_clarity",
        "copy_quality",
        "responsiveness",
        "density_control",
        "evidence_readability",
        "product_feel",
    )
    route_lookup = {str(item.get("route") or ""): item for item in route_scores}
    checklist: list[dict[str, Any]] = []
    for dimension in dimensions:
        related_routes = []
        related_findings = []
        for finding in findings:
            route = str(finding.get("route") or "unknown")
            route_score = route_lookup.get(route)
            low_dimensions = [
                key for key, detail in (route_score or {}).get("dimensions", {}).items() if int(detail["score"]) < 8
            ]
            dimension_markers = {
                "hierarchy": {"hierarchy", "information_density"},
                "navigation_clarity": {"navigation", "interaction"},
                "state_clarity": {"clarity", "interaction"},
                "copy_quality": {"clarity"},
                "responsiveness": {"responsiveness"},
                "density_control": {"information_density"},
                "evidence_readability": {"clarity", "information_density"},
                "product_feel": {"visual_maturity", "hierarchy"},
            }
            if any(marker in low_dimensions for marker in dimension_markers[dimension]):
                related_routes.append(route)
                related_findings.append(finding["description"])
        verdict = "pass" if not related_routes else "fix"
        checklist.append(
            {
                "dimension": dimension,
                "verdict": verdict,
                "routes": sorted(set(related_routes)),
                "notes": related_findings[:3],
            }
        )
    return checklist


def _build_visual_verdict(
    overall_scores: dict[str, dict[str, Any]],
    findings: list[dict[str, str]],
    *,
    before_paths: list[str],
    after_paths: list[str],
) -> dict[str, Any]:
    failing_dimensions = [
        dimension
        for dimension, detail in overall_scores.items()
        if int(detail.get("score") or 0) < 8
    ]
    return {
        "passed": not failing_dimensions and not any(item.get("severity") == "blocking" for item in findings),
        "failing_dimensions": failing_dimensions,
        "before_count": len(before_paths),
        "after_count": len(after_paths),
        "summary": "Design review passed." if not failing_dimensions else f"Design review needs fixes in {', '.join(failing_dimensions)}.",
    }
