from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_PENALTY = {"critical": 28, "high": 16, "medium": 8, "low": 3}


def load_qa_test_context(state: dict[str, Any], repo_b_path: Path) -> dict[str, Any]:
    shared_blackboard = state.get("shared_blackboard") if isinstance(state.get("shared_blackboard"), dict) else {}
    architecture_context = (
        shared_blackboard.get("architecture_review") if isinstance(shared_blackboard.get("architecture_review"), dict) else {}
    )
    plan_path = (
        str(state.get("qa_test_plan_path") or "").strip()
        or str(architecture_context.get("qa_test_plan_ref") or "").strip()
    )
    plan_text = ""
    plan_sections: dict[str, list[str]] = {}
    if plan_path:
        path = Path(plan_path)
        if path.exists():
            plan_text = path.read_text(encoding="utf-8")
            plan_sections = _parse_markdown_sections(plan_text)

    architecture_test_plan = state.get("architecture_test_plan") if isinstance(state.get("architecture_test_plan"), dict) else {}
    qa_handoff = architecture_test_plan.get("qa_handoff") if isinstance(architecture_test_plan.get("qa_handoff"), list) else []
    failure_modes = architecture_test_plan.get("failure_modes") if isinstance(architecture_test_plan.get("failure_modes"), list) else []
    return {
        "plan_path": plan_path or None,
        "plan_text": plan_text,
        "plan_sections": plan_sections,
        "architecture_test_plan": architecture_test_plan,
        "critical_paths": plan_sections.get("Critical Paths") or [],
        "edge_cases": plan_sections.get("Edge Cases") or [],
        "interactions": plan_sections.get("Key Interactions to Verify") or [],
        "affected_routes": plan_sections.get("Affected Pages/Routes") or [],
        "qa_handoff": [str(item).strip() for item in qa_handoff if str(item).strip()],
        "failure_modes": [
            item for item in failure_modes if isinstance(item, dict) and str(item.get("failure") or "").strip()
        ],
        "unit_checks": list(architecture_test_plan.get("unit_checks") or []) if isinstance(architecture_test_plan, dict) else [],
        "integration_checks": list(architecture_test_plan.get("integration_checks") or []) if isinstance(architecture_test_plan, dict) else [],
        "manual_checks": list(architecture_test_plan.get("manual_checks") or []) if isinstance(architecture_test_plan, dict) else [],
        "risk_checks": list(architecture_test_plan.get("risk_checks") or []) if isinstance(architecture_test_plan, dict) else [],
        "verification_basis": [str(item).strip() for item in (state.get("verification_basis") or []) if str(item).strip()],
        "story_kind": str(state.get("story_kind") or "").strip() or None,
        "repo_b_path": str(repo_b_path),
    }


def build_qa_finding(
    *,
    finding_id: str,
    severity: str,
    category: str,
    summary: str,
    detail: str,
    source_mode: str,
    evidence_refs: list[str] | None = None,
    route: str | None = None,
    recommended_action: str | None = None,
    regression_hint: str | None = None,
    disposition: str | None = None,
) -> dict[str, Any]:
    normalized_severity = severity if severity in _SEVERITY_RANK else "medium"
    normalized_disposition = disposition or ("fixer" if normalized_severity in {"critical", "high"} else "report")
    return {
        "finding_id": finding_id,
        "severity": normalized_severity,
        "category": category,
        "summary": summary.strip(),
        "detail": detail.strip(),
        "source_mode": source_mode,
        "route": (route or "").strip() or None,
        "evidence_refs": [item for item in (evidence_refs or []) if str(item).strip()],
        "recommended_action": (recommended_action or "").strip()
        or _default_recommended_action(normalized_severity, category),
        "regression_hint": (regression_hint or "").strip() or None,
        "disposition": normalized_disposition,
    }


def sort_qa_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            _SEVERITY_RANK.get(str(item.get("severity") or ""), 9),
            str(item.get("category") or ""),
            str(item.get("summary") or ""),
        ),
    )


def compute_health_score(findings: list[dict[str, Any]]) -> int:
    penalty = sum(_SEVERITY_PENALTY.get(str(item.get("severity") or ""), 0) for item in findings)
    return max(0, min(100, 100 - penalty))


def infer_ship_readiness(findings: list[dict[str, Any]], *, report_only: bool) -> str:
    severities = {str(item.get("severity") or "") for item in findings}
    if "critical" in severities or "high" in severities:
        return "report_only_attention" if report_only else "needs_fix"
    if "medium" in severities:
        return "caution"
    return "ready"


def build_regression_recommendations(findings: list[dict[str, Any]], context: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    for item in findings:
        severity = str(item.get("severity") or "")
        if severity not in {"critical", "high", "medium"}:
            continue
        route = str(item.get("route") or "").strip()
        summary = str(item.get("summary") or "").strip()
        hint = str(item.get("regression_hint") or "").strip()
        if hint:
            recommendations.append(hint)
            continue
        if route:
            recommendations.append(f"Add a regression verification for {route}: {summary}")
        else:
            recommendations.append(f"Add a regression verification for {summary}")

    for item in context.get("critical_paths") or []:
        if item not in recommendations:
            recommendations.append(f"Re-run critical path from plan-eng-review: {item}")
    for item in context.get("qa_handoff") or []:
        recommendation = f"Preserve QA handoff evidence for: {item}"
        if recommendation not in recommendations:
            recommendations.append(recommendation)
    return recommendations[:8]


def build_verification_rerun_plan(
    findings: list[dict[str, Any]],
    context: dict[str, Any],
    *,
    report_only: bool,
) -> list[str]:
    plan: list[str] = []
    for item in context.get("qa_handoff") or []:
        plan.append(f"Re-confirm QA handoff expectation: {item}")
    for item in context.get("interactions") or []:
        plan.append(f"Verify interaction again: {item}")
    for item in context.get("edge_cases") or []:
        plan.append(f"Re-check edge case: {item}")
    for item in context.get("failure_modes") or []:
        if isinstance(item, dict):
            failure = str(item.get("failure") or "").strip()
            verification = str(item.get("verification") or "").strip()
            if failure:
                plan.append(
                    f"Re-check failure mode: {failure}"
                    + (f" | verify via {verification}" if verification else "")
                )
    for finding in findings[:4]:
        plan.append(f"Re-run evidence capture for {finding.get('summary')}")
    if report_only:
        plan.append("Keep QA in report-only mode; do not enter fixer until a human approves remediation.")
    else:
        plan.append("After each fix, re-run the failing QA step and capture before/after evidence.")
    deduped: list[str] = []
    for item in plan:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped[:10]


def build_qa_input_sources(
    state: dict[str, Any],
    context: dict[str, Any],
    *,
    source_mode: str,
    report_only: bool,
) -> list[str]:
    sources: list[str] = []
    if context.get("plan_path"):
        sources.append(f"plan-eng-review test plan: {context['plan_path']}")
    for item in context.get("qa_handoff") or []:
        sources.append(f"QA handoff: {item}")
    for item in context.get("verification_basis") or []:
        sources.append(f"verification basis: {item}")
    story_kind = str(context.get("story_kind") or state.get("story_kind") or "").strip()
    if story_kind:
        sources.append(f"story kind: {story_kind}")
    if source_mode == "browser_qa":
        session_id = str(state.get("browser_session_id") or "").strip()
        if session_id:
            sources.append(f"browse session: {session_id}")
        if state.get("browser_runtime_dir"):
            sources.append(f"browse runtime dir: {state['browser_runtime_dir']}")
    if source_mode == "runtime_qa":
        commands = state.get("test_results")
        if isinstance(commands, str) and commands.strip():
            sources.append("tester output present")
    sources.append("mode: report-only" if report_only else "mode: fixer-enabled")
    deduped: list[str] = []
    for item in sources:
        text = str(item).strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped[:12]


def write_shared_qa_artifacts(
    repo_b_path: Path,
    *,
    mode_id: str,
    report_only: bool,
    findings: list[dict[str, Any]],
    health_score: int,
    ship_readiness: str,
    test_context: dict[str, Any],
    regression_recommendations: list[str],
    verification_rerun_plan: list[str],
    input_sources: list[str] | None = None,
) -> dict[str, str]:
    qa_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    findings_path = qa_dir / "qa_findings.json"
    summary_path = qa_dir / "qa_summary.json"
    context_path = qa_dir / "qa_context.md"
    rerun_plan_path = qa_dir / "qa_rerun_plan.json"

    findings_path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    category_counts = _category_counts(findings)
    disposition_counts = _disposition_counts(findings)
    rerun_required = any(str(item.get("severity") or "") in {"critical", "high"} for item in findings)
    top_blockers = [str(item.get("summary") or "").strip() for item in findings if str(item.get("severity") or "") == "critical"][:5]
    summary_path.write_text(
        json.dumps(
            {
                "finding_schema_version": "qa.v2",
                "summary_schema_version": "qa_summary.v2",
                "mode_id": mode_id,
                "report_only": report_only,
                "report_mode": "report-only" if report_only else "fixer-enabled",
                "health_score": health_score,
                "ship_readiness": ship_readiness,
                "finding_count": len(findings),
                "severity_counts": _severity_counts(findings),
                "category_counts": category_counts,
                "disposition_counts": disposition_counts,
                "input_sources": list(input_sources or []),
                "rerun_required": rerun_required,
                "top_blockers": top_blockers,
                "test_plan_path": test_context.get("plan_path"),
                "regression_recommendations": regression_recommendations,
                "verification_rerun_plan": verification_rerun_plan,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    rerun_plan_path.write_text(
        json.dumps(
            {
                "mode_id": mode_id,
                "report_only": report_only,
                "rerun_required": rerun_required,
                "verification_rerun_plan": verification_rerun_plan,
                "regression_recommendations": regression_recommendations,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    context_lines = [
        "# QA Context",
        "",
        f"- Mode: {mode_id}",
        f"- Report only: {'yes' if report_only else 'no'}",
        f"- Health score: {health_score}",
        f"- Ship readiness: {ship_readiness}",
        f"- Test plan source: {test_context.get('plan_path') or 'none'}",
        "",
        "## QA Input Sources",
        *([f"- {item}" for item in input_sources or []] or ["- No explicit QA input sources were recorded."]),
        "",
        "## QA Handoff",
        *([f"- {item}" for item in test_context.get("qa_handoff") or []] or ["- None recorded."]),
        "",
        "## Affected Pages/Routes",
        *([f"- {item}" for item in test_context.get("affected_routes") or []] or ["- None recorded."]),
        "",
        "## Key Interactions To Verify",
        *([f"- {item}" for item in test_context.get("interactions") or []] or ["- None recorded."]),
        "",
        "## Edge Cases",
        *([f"- {item}" for item in test_context.get("edge_cases") or []] or ["- None recorded."]),
        "",
        "## Critical Paths",
        *([f"- {item}" for item in test_context.get("critical_paths") or []] or ["- None recorded."]),
        "",
        "## Failure Modes",
        *(
            [
                f"- {item.get('failure')} | verify={item.get('verification') or 'n/a'}"
                for item in test_context.get("failure_modes") or []
                if isinstance(item, dict)
            ]
            or ["- None recorded."]
        ),
        "",
        "## Regression Recommendations",
        *([f"- {item}" for item in regression_recommendations] or ["- No regression recommendations were generated."]),
        "",
        "## Verification Rerun Plan",
        *([f"- {item}" for item in verification_rerun_plan] or ["- No rerun plan was generated."]),
        "",
    ]
    context_path.write_text("\n".join(context_lines), encoding="utf-8")

    return {
        "qa_dir": str(qa_dir),
        "qa_findings_path": str(findings_path),
        "qa_summary_path": str(summary_path),
        "qa_context_path": str(context_path),
        "qa_rerun_plan_path": str(rerun_plan_path),
    }


def _default_recommended_action(severity: str, category: str) -> str:
    if severity in {"critical", "high"}:
        return f"Fix the {category} regression, then rerun QA."
    if severity == "medium":
        return f"Address the {category} issue before acceptance if time permits, then rerun QA evidence."
    return f"Record the {category} issue for follow-up and keep it visible in the QA report."


def _parse_markdown_sections(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_heading = line[3:].strip()
            sections.setdefault(current_heading, [])
            continue
        if current_heading and line.startswith("- "):
            sections[current_heading].append(line[2:].strip())
    return sections


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in findings:
        severity = str(item.get("severity") or "")
        if severity in counts:
            counts[severity] += 1
    return counts


def _category_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        category = str(item.get("category") or "").strip() or "unknown"
        counts[category] = counts.get(category, 0) + 1
    return counts


def _disposition_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        disposition = str(item.get("disposition") or "").strip() or "unknown"
        counts[disposition] = counts.get(disposition, 0) + 1
    return counts
