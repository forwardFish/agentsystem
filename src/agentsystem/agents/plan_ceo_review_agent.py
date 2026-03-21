from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_executed_mode, add_handoff_packet


CEO_REVIEW_MODES = {"scope_expansion", "selective_expansion", "hold_scope", "scope_reduction"}


def generate_plan_ceo_review_package(
    repo_b_path: str | Path,
    *,
    project: str,
    requirement_text: str,
    title: str | None = None,
    user_problem: str | None = None,
    constraints: str | list[str] | None = None,
    success_signal: str | list[str] | None = None,
    audience: str | None = None,
    delivery_mode: str = "interactive",
    source_requirement_path: str | Path | None = None,
    review_mode: str | None = None,
    related_files: list[str] | None = None,
    office_hours_summary: str | None = None,
    strict_decisions: bool = False,
    accepted_expansions: list[str] | None = None,
    rejected_expansions: list[str] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    docs_root = _resolve_requirement_docs_root(repo_path)
    meta_dir = repo_path.parent / ".meta" / repo_path.name / "plan_ceo_review"
    docs_root.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    normalized_requirement = str(requirement_text or "").strip()
    if not normalized_requirement:
        raise ValueError("requirement_text must not be empty")

    constraint_items = _normalize_list(constraints)
    success_items = _normalize_list(success_signal)
    related_items = [str(item).strip() for item in (related_files or []) if str(item).strip()]
    resolved_problem = str(user_problem or "").strip() or _derive_problem(normalized_requirement)
    resolved_audience = str(audience or "").strip() or "Primary end users described in the requirement"
    selected_mode = _select_mode(review_mode, normalized_requirement, constraint_items, delivery_mode)
    ui_scope = _detect_ui_scope(normalized_requirement, related_items)

    proposals = [
        {"id": "observability", "title": "Add explicit observability and proof hooks", "why": resolved_problem},
        {"id": "regression", "title": "Add regression coverage tied to the primary success signal", "why": success_items[0] if success_items else "Tighten verification."},
    ]
    if ui_scope:
        proposals.append({"id": "design_intent", "title": "Add plan-design-review and design-review evidence", "why": "UI scope should not skip design intent."})

    accepted_ids = {str(item).strip() for item in (accepted_expansions or []) if str(item).strip()}
    rejected_ids = {str(item).strip() for item in (rejected_expansions or []) if str(item).strip()}
    unresolved = [
        {
            "proposal_id": item["id"],
            "question": f"Should `{item['title']}` become part of the committed scope?",
            "recommendation": "yes" if selected_mode in {"scope_expansion", "selective_expansion"} else "no",
        }
        for item in proposals
        if item["id"] not in accepted_ids and item["id"] not in rejected_ids
    ]
    if selected_mode == "scope_expansion" and not strict_decisions and not accepted_ids:
        accepted_ids = {item["id"] for item in proposals}
        unresolved = []
    if selected_mode in {"hold_scope", "scope_reduction"} and not strict_decisions:
        rejected_ids = {item["id"] for item in proposals if item["id"] not in accepted_ids}
        unresolved = []
    auto_deferred = []
    if selected_mode == "selective_expansion" and not strict_decisions:
        auto_deferred = [
            item
            for item in proposals
            if item["id"] not in accepted_ids and item["id"] not in rejected_ids
        ]
        rejected_ids = rejected_ids | {item["id"] for item in auto_deferred}
        unresolved = []

    accepted = [item for item in proposals if item["id"] in accepted_ids]
    deferred = [item for item in proposals if item["id"] in rejected_ids]
    ceremony = {
        "selected_mode": selected_mode,
        "ui_scope_detected": ui_scope,
        "accepted_expansions": accepted,
        "deferred_expansions": deferred,
        "unresolved_decisions": unresolved if strict_decisions or selected_mode == "selective_expansion" else [],
        "auto_deferred_expansions": auto_deferred,
        "approval_options": [
            "Approve the selected mode and continue into plan-eng-review.",
            "Revise the mode or scope proposals before engineering planning starts.",
            "Keep the requirement package as hold-scope only.",
        ],
    }
    if selected_mode == "selective_expansion" and not strict_decisions:
        ceremony["unresolved_decisions"] = []

    system_audit = {
        "repo": repo_path.name,
        "docs_present": [name for name in ("README.md", "CLAUDE.md", "TODOS.md") if repo_path.joinpath(name).exists()],
        "related_files": related_items,
        "office_hours_summary": office_hours_summary,
        "ui_scope_detected": ui_scope,
        "system_findings": [
            "Design scope detected; keep plan-design-review in the downstream chain." if ui_scope else "No major UI scope detected from this requirement.",
            "Office-hours framing is available and should be treated as upstream context." if office_hours_summary else "No office-hours framing was provided; premise challenge stays conservative.",
            f"Constraint count: {len(constraint_items)} | Success signals: {len(success_items)}.",
        ],
    }
    premise_challenge = [
        f"Premise 1: The real problem to solve is `{resolved_problem}`.",
        f"Premise 2: Success should be measured by `{success_items[0]}`." if success_items else "Premise 2: The success signal is still weak and needs tightening.",
        "Premise 3: The plan must make silent failure modes visible before build starts.",
    ]
    alternatives = [
        {"name": "baseline", "summary": f"Ship the narrowest version that directly addresses `{resolved_problem}`.", "effort": "medium"},
        {"name": "expanded", "summary": "Increase ambition with better observability, polish, and leverage." + (" Include UI intentionality." if ui_scope else ""), "effort": "high"},
        {"name": "reduced", "summary": "Strip the plan down to the smallest viable slice.", "effort": "low"},
    ]
    if selected_mode == "scope_expansion":
        alternatives = [alternatives[1], alternatives[0], alternatives[2]]
    elif selected_mode == "scope_reduction":
        alternatives = [alternatives[2], alternatives[0], alternatives[1]]

    failure_modes = [
        {"codepath": ", ".join(related_items[:3]) or "implied surfaces", "failure_mode": "Proof is too weak to show the user problem was solved.", "rescued": False, "tested": False, "user_sees": "Ambiguous outcome", "logged": True},
        {"codepath": "workflow routing", "failure_mode": "A required planning or QA step is skipped because story metadata is incomplete.", "rescued": True, "tested": True, "user_sees": "Missing review evidence", "logged": True},
    ]
    if ui_scope:
        failure_modes.append({"codepath": "browser-facing surface", "failure_mode": "The UI looks fine in code review but breaks real interaction or auth-state flows.", "rescued": True, "tested": selected_mode != "scope_reduction", "user_sees": "Broken interaction", "logged": True})

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    resolved_title = str(title or "").strip() or _derive_title(normalized_requirement, project)
    slug = _slugify(resolved_title)
    requirement_doc_path = docs_root / f"{timestamp}_{slug}.md"
    review_report_path = meta_dir / "product_review_report.md"
    opportunity_map_path = meta_dir / "opportunity_map.json"
    decision_ceremony_path = meta_dir / "decision_ceremony.json"

    requirement_doc_path.write_text(
        _build_requirement_doc(
            title=resolved_title,
            project=project,
            requirement_text=normalized_requirement,
            source_requirement_path=source_requirement_path,
            delivery_mode=delivery_mode,
            selected_mode=selected_mode,
            user_problem=resolved_problem,
            audience=resolved_audience,
            constraints=constraint_items,
            success_signals=success_items,
            accepted=accepted,
            system_audit=system_audit,
        ),
        encoding="utf-8",
    )
    review_report_path.write_text(
        _build_review_report(
            title=resolved_title,
            project=project,
            requirement_text=normalized_requirement,
            user_problem=resolved_problem,
            audience=resolved_audience,
            delivery_mode=delivery_mode,
            selected_mode=selected_mode,
            constraints=constraint_items,
            success_signals=success_items,
            system_audit=system_audit,
            premise_challenge=premise_challenge,
            alternatives=alternatives,
            ceremony=ceremony,
            failure_modes=failure_modes,
            next_actions=_build_next_actions(project, requirement_doc_path, delivery_mode, ui_scope),
        ),
        encoding="utf-8",
    )

    opportunity_map = {
        "title": resolved_title,
        "project": project,
        "delivery_mode": delivery_mode,
        "selected_mode": selected_mode,
        "user_problem": resolved_problem,
        "target_audience": resolved_audience,
        "constraints": constraint_items,
        "success_signals": success_items,
        "source_requirement_path": str(Path(source_requirement_path).resolve()) if source_requirement_path else None,
        "requirement_doc_path": str(requirement_doc_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ui_scope_detected": ui_scope,
        "system_audit": system_audit,
        "premise_challenge": premise_challenge,
        "alternatives": alternatives,
        "accepted_expansions": accepted,
        "deferred_expansions": deferred,
        "unresolved_decisions": ceremony["unresolved_decisions"],
        "auto_deferred_expansions": ceremony["auto_deferred_expansions"],
        "next_recommended_actions": _build_next_actions(project, requirement_doc_path, delivery_mode, ui_scope),
    }
    opportunity_map_path.write_text(json.dumps(opportunity_map, ensure_ascii=False, indent=2), encoding="utf-8")
    decision_ceremony_path.write_text(json.dumps(ceremony, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "title": resolved_title,
        "delivery_mode": delivery_mode,
        "selected_mode": selected_mode,
        "requirement_doc_path": str(requirement_doc_path),
        "review_report_path": str(review_report_path),
        "opportunity_map_path": str(opportunity_map_path),
        "decision_ceremony_path": str(decision_ceremony_path),
        "unresolved_decisions": ceremony["unresolved_decisions"],
        "next_recommended_actions": opportunity_map["next_recommended_actions"],
    }


def plan_ceo_review_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    task_payload = state.get("task_payload") or {}
    non_interactive_auto_run = _is_non_interactive_auto_run(state, task_payload)
    package = generate_plan_ceo_review_package(
        repo_b_path,
        project=str(task_payload.get("project") or repo_b_path.name),
        requirement_text=str(state.get("parsed_goal") or state.get("user_requirement") or "").strip(),
        title=str(task_payload.get("task_name") or task_payload.get("title") or "").strip() or None,
        user_problem=task_payload.get("user_problem"),
        constraints=task_payload.get("constraints") or state.get("parsed_constraints"),
        success_signal=task_payload.get("success_signal") or task_payload.get("acceptance_criteria"),
        audience=task_payload.get("audience"),
        delivery_mode=str(task_payload.get("delivery_mode") or task_payload.get("review_mode") or "auto"),
        source_requirement_path=task_payload.get("source_requirement_path"),
        review_mode=task_payload.get("ceo_review_mode") or task_payload.get("scope_mode"),
        related_files=[
            *(str(item).strip() for item in (task_payload.get("related_files") or []) if str(item).strip()),
            *(str(item).strip() for item in (state.get("primary_files") or []) if str(item).strip()),
        ],
        office_hours_summary=str(state.get("office_hours_summary") or "").strip() or None,
        strict_decisions=bool(task_payload.get("plan_ceo_require_decisions")) and not non_interactive_auto_run,
        accepted_expansions=task_payload.get("accepted_expansions"),
        rejected_expansions=task_payload.get("rejected_expansions"),
    )

    review_path = Path(package["review_report_path"]).resolve()
    opportunity_map_path = Path(package["opportunity_map_path"]).resolve()
    requirement_doc_path = Path(package["requirement_doc_path"]).resolve()
    decision_ceremony_path = Path(package["decision_ceremony_path"]).resolve()
    state["plan_ceo_review_success"] = True
    state["plan_ceo_review_dir"] = str(review_path.parent)
    state["plan_ceo_review_report"] = review_path.read_text(encoding="utf-8")
    state["plan_ceo_requirement_doc"] = str(requirement_doc_path)
    state["plan_ceo_opportunity_map"] = json.loads(opportunity_map_path.read_text(encoding="utf-8"))
    state["plan_ceo_selected_mode"] = str(package["selected_mode"])
    state["plan_ceo_decision_ceremony"] = json.loads(decision_ceremony_path.read_text(encoding="utf-8"))
    state["plan_ceo_unresolved_decisions"] = list(package.get("unresolved_decisions") or [])
    state["awaiting_user_input"] = bool(package.get("unresolved_decisions"))
    state["dialogue_state"] = state["plan_ceo_decision_ceremony"]
    state["next_question"] = (
        dict(package["unresolved_decisions"][0])
        if package.get("unresolved_decisions")
        else None
    )
    state["approval_required"] = bool(package.get("unresolved_decisions"))
    state["handoff_target"] = "plan-eng-review"
    state["resume_from_mode"] = "plan-ceo-review" if package.get("unresolved_decisions") else None
    state["decision_state"] = state["plan_ceo_decision_ceremony"]
    state["interaction_round"] = len(state["plan_ceo_decision_ceremony"].get("accepted_expansions") or []) + len(
        state["plan_ceo_decision_ceremony"].get("deferred_expansions") or []
    )
    state["current_step"] = "plan_ceo_review_done"
    state["error_message"] = None
    add_executed_mode(state, "plan-ceo-review")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.PLAN_CEO_REVIEW,
            to_agent=AgentRole.ARCHITECTURE_REVIEW,
            status=HandoffStatus.BLOCKED if package.get("unresolved_decisions") else HandoffStatus.COMPLETED,
            what_i_did="Reframed the request into a higher-leverage product outcome, selected a CEO review mode, and wrote a requirement package with a decision ceremony record.",
            what_i_produced=[
                Deliverable(deliverable_id=str(uuid.uuid4()), name="Plan CEO Review Report", type="report", path=str(review_path), description="CEO review report with mode selection, alternatives, and failure-mode registry.", created_by=AgentRole.PLAN_CEO_REVIEW),
                Deliverable(deliverable_id=str(uuid.uuid4()), name="Requirement Document", type="report", path=str(requirement_doc_path), description="Canonical requirement document generated from the CEO review step.", created_by=AgentRole.PLAN_CEO_REVIEW),
                Deliverable(deliverable_id=str(uuid.uuid4()), name="CEO Decision Ceremony", type="report", path=str(decision_ceremony_path), description="Mode selection and scope proposal record for the CEO review step.", created_by=AgentRole.PLAN_CEO_REVIEW),
            ],
            what_risks_i_found=[*(str(item) for item in (state["plan_ceo_opportunity_map"].get("constraints") or [])), *(str(item.get("question") or "") for item in (package.get("unresolved_decisions") or []))],
            what_i_require_next="Resolve the pending CEO review decisions, then run architecture review." if package.get("unresolved_decisions") else "Use the generated requirement document as the planning source of truth for architecture review.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_plan_ceo_review(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "plan_ceo_review":
        return "__end__"
    if state.get("awaiting_user_input") and str(state.get("resume_from_mode") or "").strip() == "plan-ceo-review":
        return "__end__"
    return "architecture_review"


def _is_non_interactive_auto_run(state: DevState, task_payload: dict[str, Any]) -> bool:
    interaction_policy = str(state.get("interaction_policy") or task_payload.get("interaction_policy") or "").strip().lower()
    return bool(state.get("auto_run") or task_payload.get("auto_run")) or interaction_policy == "non_interactive_auto_run"


def _resolve_requirement_docs_root(repo_path: Path) -> Path:
    return repo_path.joinpath("docs", "requirements") if repo_path.joinpath("docs").exists() or repo_path.name in {"versefina", "finahunt"} else repo_path / "requirements"


def _select_mode(requested_mode: str | None, requirement_text: str, constraints: list[str], delivery_mode: str) -> str:
    explicit = str(requested_mode or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"expansion": "scope_expansion", "scope_expansion": "scope_expansion", "selective": "selective_expansion", "selective_expansion": "selective_expansion", "hold": "hold_scope", "hold_scope": "hold_scope", "reduction": "scope_reduction", "scope_reduction": "scope_reduction"}
    if explicit in aliases:
        return aliases[explicit]
    lowered = requirement_text.lower()
    if any(token in lowered for token in ("think bigger", "10x", "ambitious", "expand scope")):
        return "scope_expansion"
    if any(token in lowered for token in ("strip down", "minimum", "reduce scope")):
        return "scope_reduction"
    return "hold_scope" if constraints or delivery_mode == "auto" else "selective_expansion"


def _detect_ui_scope(requirement_text: str, related_files: list[str]) -> bool:
    lowered = requirement_text.lower()
    if any(token in lowered for token in ("ui", "page", "screen", "dashboard", "frontend", "layout", "interaction")):
        return True
    return any(path.endswith((".tsx", ".jsx", ".css", ".scss")) or "/web/" in path.replace("\\", "/") for path in related_files)


def _build_requirement_doc(**kwargs: Any) -> str:
    lines = [
        f"# {kwargs['title']}",
        "",
        "## Context",
        f"- Project: {kwargs['project']}",
        f"- Delivery mode: {kwargs['delivery_mode']}",
        f"- CEO review mode: {kwargs['selected_mode']}",
        f"- Source requirement file: {Path(kwargs['source_requirement_path']).resolve() if kwargs['source_requirement_path'] else 'inline input'}",
        "",
        "## User Problem",
        kwargs["user_problem"],
        "",
        "## Target Audience",
        kwargs["audience"],
        "",
        "## Requirement Summary",
        kwargs["requirement_text"],
        "",
        "## Product Constraints",
        *([f"- {item}" for item in kwargs["constraints"]] or ["- Follow the repo contract and declared blast radius."]),
        "",
        "## Success Signals",
        *([f"- {item}" for item in kwargs["success_signals"]] or ["- The delivered stories complete the requested user outcome with acceptance evidence."]),
        "",
        "## CEO Mode Decision",
        f"- Selected mode: {kwargs['selected_mode']}",
        *([f"- Accepted expansion: {item['title']}" for item in kwargs["accepted"]] or ["- No scope expansion was auto-accepted."]),
        "",
        "## System Audit Snapshot",
        *[f"- {item}" for item in kwargs["system_audit"]["system_findings"]],
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _build_review_report(**kwargs: Any) -> str:
    failure_lines = [f"| {item['codepath']} | {item['failure_mode']} | {'Y' if item['rescued'] else 'N'} | {'Y' if item['tested'] else 'N'} | {item['user_sees']} | {'Y' if item['logged'] else 'N'} |" for item in kwargs["failure_modes"]]
    lines = [
        f"# Plan CEO Review Report: {kwargs['title']}",
        "",
        "## Product Outcome",
        f"Deliver a clear, testable product increment for `{kwargs['project']}` that solves: {kwargs['user_problem']}",
        "",
        "## Audience",
        kwargs["audience"],
        "",
        "## Why This Matters",
        kwargs["requirement_text"],
        "",
        "## CEO Review Mode",
        f"- Selected mode: {kwargs['selected_mode']}",
        f"- Delivery mode: {kwargs['delivery_mode']}",
        *([f"- Accepted expansion: {item['title']}" for item in kwargs["ceremony"]["accepted_expansions"]] or ["- No scope expansion was accepted automatically."]),
        *([f"- Deferred expansion: {item['title']}" for item in kwargs["ceremony"]["deferred_expansions"]] or []),
        "",
        "## System Audit",
        *[f"- {item}" for item in kwargs["system_audit"]["system_findings"]],
        "",
        "## Premise Challenge",
        *[f"- {item}" for item in kwargs["premise_challenge"]],
        "",
        "## Alternatives Considered",
        *[f"- {item['name']}: {item['summary']} | effort={item['effort']}" for item in kwargs["alternatives"]],
        "",
        "## Guardrails",
        *([f"- {item}" for item in kwargs["constraints"]] or ["- Keep the implementation inside the declared repo and avoid unnecessary scope expansion."]),
        "",
        "## Success Signals",
        *([f"- {item}" for item in kwargs["success_signals"]] or ["- Tighten the success signal before build starts."]),
        "",
        "## Failure Modes Registry",
        "| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |",
        "| --- | --- | --- | --- | --- | --- |",
        *failure_lines,
        "",
        "## Review Readiness Summary",
        f"- Critical gaps: {sum(1 for item in kwargs['failure_modes'] if not item['rescued'] and not item['tested'])}",
        f"- Unresolved decisions: {len(kwargs['ceremony']['unresolved_decisions'])}",
        f"- Recommended next reviews: {', '.join(kwargs['next_actions'][:2])}",
        "",
        "## Next Actions",
        *[f"- {item}" for item in kwargs["next_actions"]],
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _build_next_actions(project: str, requirement_doc_path: Path, delivery_mode: str, ui_scope: bool) -> list[str]:
    actions = [f"Run plan-eng-review against {requirement_doc_path} for project {project}.", "Keep the CEO decision ceremony attached to the downstream planning packet."]
    if ui_scope:
        actions.append("Run plan-design-review before implementation because UI scope was detected.")
    actions.append(f"{'Continue auto delivery from' if delivery_mode == 'auto' else 'Review and refine'} {requirement_doc_path}.")
    return actions


def _derive_title(requirement_text: str, project: str) -> str:
    first_line = next((line.strip(' #-\t') for line in requirement_text.splitlines() if line.strip()), "")
    return first_line[:80] if first_line else f"{project} requirement"


def _derive_problem(requirement_text: str) -> str:
    sentence = next((line.strip() for line in requirement_text.splitlines() if line.strip()), "")
    return sentence[:200] if sentence else "Clarify the desired user-facing outcome before implementation starts."


def _normalize_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip(" -\t") for item in re.split(r"[\r\n;；]+", str(value)) if item.strip(" -\t")]


def _slugify(value: str) -> str:
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return ascii_only[:80] or "requirement"
