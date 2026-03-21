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


FORCING_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("user", "Who is the single most important user for this cycle?"),
    ("pain", "What is the concrete pain or blockage they feel today?"),
    ("workaround", "What low-quality workaround do they use if we do nothing?"),
    ("wedge", "What is the smallest wedge we should land first?"),
    ("differentiator", "What would make this meaningfully better than a generic feature?"),
    ("proof", "What evidence would prove this solved something real, not just shipped code?"),
)

BUILDER_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("coolest_version", "What is the coolest version of this idea?"),
    ("wow_moment", "Who would you show this to, and what would make them say whoa?"),
    ("leverage", "What existing code, data, or workflows can we reuse instead of starting from zero?"),
    ("hard_part", "What is the hardest or riskiest part to prototype early?"),
    ("delight", "What small touch would make this feel intentional rather than generic?"),
    ("build_next", "What should we build first, second, and third if we start today?"),
)

_WHY_STARTUP = {
    "user": "Without a precise user, the wedge drifts and every later review gets weaker.",
    "pain": "If the pain is vague, the team will optimize for shipping activity rather than user relief.",
    "workaround": "The workaround reveals the real competitor and the switching cost we need to beat.",
    "wedge": "A sharp wedge keeps the first version focused and preserves room to expand later.",
    "differentiator": "This protects the product from collapsing into a generic feature request.",
    "proof": "Proof keeps implementation and impact separate so acceptance means something real.",
}

_WHY_BUILDER = {
    "coolest_version": "Builder-mode office hours should generate energy and direction, not only constraints.",
    "wow_moment": "A vivid demo target keeps the idea from becoming abstract or forgettable.",
    "leverage": "Reuse is the fastest path to a convincing prototype and reduces accidental complexity.",
    "hard_part": "Surfacing the riskiest unknown early prevents false confidence.",
    "delight": "A small delight detail is often what separates a useful prototype from a memorable one.",
    "build_next": "Concrete next steps turn brainstorming into build momentum.",
}

_STARTUP_STAGE_REQUIRED: dict[str, tuple[str, ...]] = {
    "pre-product": ("user", "pain", "workaround"),
    "has-users": ("user", "pain", "workaround", "wedge", "proof"),
    "paying-customers": ("user", "pain", "workaround", "wedge", "differentiator", "proof"),
}


def office_hours_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    office_hours_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "office_hours"
    office_hours_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    goal = str(state.get("parsed_goal") or state.get("user_requirement") or task_payload.get("goal") or "").strip()
    mode = _select_mode(goal, task_payload, state)
    product_stage = _select_product_stage(task_payload)
    strict_interaction = bool(task_payload.get("office_hours_require_answers")) and not _is_non_interactive_auto_run(state, task_payload)

    answers = _build_answers(goal, task_payload, state, mode=mode, strict_interaction=strict_interaction)
    question_ids = [item["id"] for item in answers]
    required_ids = list(_required_question_ids(mode, product_stage))
    next_question = next(
        (
            {"id": item["id"], "question": item["question"]}
            for item in answers
            if item["id"] in required_ids and not str(item["answer"]).strip()
        ),
        None,
    )
    needs_context = next_question is not None
    open_questions = [item["question"] for item in answers if not str(item["answer"]).strip()]
    framing_summary = _build_framing_summary(answers, mode=mode)
    next_build_steps = _build_next_steps(answers, mode=mode)
    premises = _build_premises(answers, mode=mode)
    alternatives = _build_alternatives(answers, mode=mode)
    approval_options = _build_approval_options(mode)

    dialogue_state = {
        "mode": mode,
        "product_stage": product_stage if mode == "startup" else None,
        "question_order": question_ids,
        "required_question_ids": required_ids,
        "answered_count": sum(1 for item in answers if str(item["answer"]).strip()),
        "next_question": next_question,
        "needs_context": needs_context,
        "approval_options": approval_options,
        "handoff_targets": ["plan-ceo-review", "plan-eng-review"],
    }

    report_lines = [
        "# Office Hours",
        "",
        f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
        f"- Goal: {goal or 'n/a'}",
        f"- Mode: {mode}",
        f"- Product stage: {product_stage if mode == 'startup' else 'builder-context'}",
        f"- Strict interaction: {'yes' if strict_interaction else 'no'}",
        "",
        "## Question Flow",
        f"- Required questions: {', '.join(required_ids) if required_ids else 'all'}",
        f"- Next question: {next_question['question'] if next_question else 'None'}",
        "",
        "## Questions",
    ]
    for item in answers:
        report_lines.extend(
            [
                f"### {item['id']}. {item['question']}",
                f"- Answer: {item['answer'] or '(pending user answer)'}",
                f"- Source: {item['source']}",
                f"- Why it matters: {item['why_it_matters']}",
                "",
            ]
        )
    report_lines.extend(
        [
            "## Premises To Confirm",
            *[f"- {item}" for item in premises],
            "",
            "## Alternatives",
            *[f"- {item}" for item in alternatives],
            "",
            "## Framing Summary",
            framing_summary,
            "",
            "## Build Next",
            *[f"- {item}" for item in next_build_steps],
            "",
            "## Open Questions",
            *([f"- {item}" for item in open_questions] or ["- None."]),
            "",
            "## Approval Handoff",
            *[f"- {item}" for item in approval_options],
            "",
            "## Handoff",
            "- Carry this framing into `plan-ceo-review` before finalizing product scope.",
            "- Carry the chosen wedge, constraints, and proof signal into `plan-eng-review` before implementation.",
            "",
        ]
    )
    report = "\n".join(report_lines).strip() + "\n"

    design_doc = _build_design_doc(
        goal=goal,
        mode=mode,
        product_stage=product_stage,
        framing_summary=framing_summary,
        answers=answers,
        premises=premises,
        alternatives=alternatives,
        next_build_steps=next_build_steps,
        approval_options=approval_options,
        needs_context=needs_context,
    )

    report_path = office_hours_dir / "office_hours_report.md"
    report_path.write_text(report, encoding="utf-8")
    questions_path = office_hours_dir / "forcing_questions.json"
    questions_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "goal": goal,
                "mode": mode,
                "product_stage": product_stage,
                "questions": answers,
                "dialogue_state": dialogue_state,
                "framing_summary": framing_summary,
                "premises": premises,
                "alternatives": alternatives,
                "next_build_steps": next_build_steps,
                "open_questions": open_questions,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    design_doc_path = office_hours_dir / "design_doc.md"
    design_doc_path.write_text(design_doc, encoding="utf-8")
    dialogue_state_path = office_hours_dir / "dialogue_state.json"
    dialogue_state_path.write_text(json.dumps(dialogue_state, ensure_ascii=False, indent=2), encoding="utf-8")

    state["office_hours_success"] = True
    state["office_hours_dir"] = str(office_hours_dir)
    state["office_hours_report"] = report
    state["office_hours_summary"] = framing_summary
    state["office_hours_questions"] = answers
    state["office_hours_mode"] = mode
    state["office_hours_product_stage"] = product_stage if mode == "startup" else "builder-context"
    state["office_hours_dialog_state"] = dialogue_state
    state["office_hours_next_question"] = next_question
    state["office_hours_needs_context"] = needs_context
    state["office_hours_design_doc"] = str(design_doc_path)
    state["awaiting_user_input"] = needs_context
    state["dialogue_state"] = dialogue_state
    state["next_question"] = next_question
    state["approval_required"] = needs_context
    state["handoff_target"] = "plan-ceo-review"
    state["resume_from_mode"] = "office-hours" if needs_context else None
    state["decision_state"] = {
        "mode": mode,
        "product_stage": product_stage if mode == "startup" else None,
        "approval_options": approval_options,
    }
    state["interaction_round"] = int(dialogue_state.get("answered_count") or 0)
    state["current_step"] = "office_hours_done"
    state["error_message"] = None
    add_executed_mode(state, "office-hours")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.OFFICE_HOURS,
            to_agent=AgentRole.PLAN_CEO_REVIEW,
            status=HandoffStatus.BLOCKED if needs_context else HandoffStatus.COMPLETED,
            what_i_did="Reframed the request through office-hours diagnostics and packaged the next decision ceremony for downstream planning.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Office Hours Report",
                    type="report",
                    path=str(report_path),
                    description="Mode-aware office-hours report with question flow, premises, and handoff guidance.",
                    created_by=AgentRole.OFFICE_HOURS,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Office Hours Design Doc",
                    type="report",
                    path=str(design_doc_path),
                    description="Design-style artifact capturing the office-hours framing and next build direction.",
                    created_by=AgentRole.OFFICE_HOURS,
                ),
            ],
            what_risks_i_found=[item["why_it_matters"] for item in answers if not str(item["answer"]).strip() or item["id"] in {"pain", "proof", "hard_part"}],
            what_i_require_next=(
                "Collect the pending office-hours answer, then continue into plan-ceo-review."
                if needs_context
                else "Run plan-ceo-review on top of this framing, then lock engineering scope in plan-eng-review."
            ),
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_office_hours(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "office_hours":
        return "__end__"
    if state.get("awaiting_user_input") and str(state.get("resume_from_mode") or "").strip() == "office-hours":
        return "__end__"
    return "plan_ceo_review"


def _is_non_interactive_auto_run(state: DevState, task_payload: dict[str, Any]) -> bool:
    interaction_policy = str(state.get("interaction_policy") or task_payload.get("interaction_policy") or "").strip().lower()
    return bool(state.get("auto_run") or task_payload.get("auto_run")) or interaction_policy == "non_interactive_auto_run"


def _select_mode(goal: str, task_payload: dict[str, Any], state: DevState) -> str:
    explicit = str(task_payload.get("office_hours_mode") or task_payload.get("idea_goal") or "").strip().lower()
    if explicit in {"startup", "builder"}:
        return explicit
    story_kind = str(state.get("story_kind") or "").strip().lower()
    if story_kind in {"epic", "sprint", "initiative"}:
        return "startup"
    text = " ".join(
        [
            goal,
            str(task_payload.get("audience") or ""),
            str(task_payload.get("success_signal") or ""),
            str(task_payload.get("workflow_enforcement_policy") or ""),
        ]
    ).lower()
    startup_markers = ("startup", "customer", "revenue", "market", "analyst", "operator", "paying", "growth")
    return "startup" if any(marker in text for marker in startup_markers) else "builder"


def _select_product_stage(task_payload: dict[str, Any]) -> str:
    explicit = str(task_payload.get("product_stage") or "").strip().lower()
    aliases = {
        "pre_product": "pre-product",
        "pre-product": "pre-product",
        "idea": "pre-product",
        "has_users": "has-users",
        "has-users": "has-users",
        "users": "has-users",
        "paying": "paying-customers",
        "paying_customers": "paying-customers",
        "paying-customers": "paying-customers",
    }
    return aliases.get(explicit, "has-users")


def _required_question_ids(mode: str, product_stage: str) -> tuple[str, ...]:
    if mode != "startup":
        return tuple(item[0] for item in BUILDER_QUESTIONS)
    return _STARTUP_STAGE_REQUIRED.get(product_stage, tuple(item[0] for item in FORCING_QUESTIONS))


def _build_answers(
    goal: str,
    task_payload: dict[str, Any],
    state: DevState,
    *,
    mode: str,
    strict_interaction: bool,
) -> list[dict[str, str]]:
    provided_answers = task_payload.get("office_hours_answers")
    answer_map = provided_answers if isinstance(provided_answers, dict) else {}
    question_set = BUILDER_QUESTIONS if mode == "builder" else FORCING_QUESTIONS
    required_ids = set(_required_question_ids(mode, _select_product_stage(task_payload)))
    defaults = _default_answers(goal, task_payload, state, mode=mode)
    why_map = _WHY_BUILDER if mode == "builder" else _WHY_STARTUP

    items: list[dict[str, str]] = []
    for key, question in question_set:
        provided = str(answer_map.get(key) or "").strip()
        if provided:
            answer = provided
            source = "provided"
        elif strict_interaction and key in required_ids:
            answer = ""
            source = "pending"
        else:
            answer = defaults.get(key, "")
            source = "inferred"
        items.append(
            {
                "id": key,
                "question": question,
                "answer": answer,
                "why_it_matters": why_map[key],
                "source": source,
            }
        )
    return items


def _default_answers(goal: str, task_payload: dict[str, Any], state: DevState, *, mode: str) -> dict[str, str]:
    if mode == "builder":
        return {
            "coolest_version": _first_non_empty(
                task_payload.get("wow_outcome"),
                task_payload.get("goal"),
                goal,
                "A version that feels focused, surprising, and demo-ready.",
            ),
            "wow_moment": _first_non_empty(
                task_payload.get("audience"),
                "A teammate or early adopter who would immediately understand the value.",
            ),
            "leverage": _first_non_empty(
                task_payload.get("related_files"),
                task_payload.get("dependencies"),
                "Reuse the strongest existing paths, components, and artifacts before inventing new ones.",
            ),
            "hard_part": _first_non_empty(
                task_payload.get("constraints"),
                state.get("parsed_not_do"),
                "The risky edge is still unclear and should be prototyped first.",
            ),
            "delight": _first_non_empty(
                task_payload.get("success_signal"),
                "The result should feel intentional rather than like generic scaffolding.",
            ),
            "build_next": _first_non_empty(
                state.get("story_outputs"),
                task_payload.get("acceptance_criteria"),
                "Ship the narrowest impressive slice, then expand from proven usage.",
            ),
        }
    return {
        "user": _first_non_empty(
            task_payload.get("audience"),
            task_payload.get("user_problem"),
            "The primary user affected by this story.",
        ),
        "pain": _first_non_empty(
            state.get("acceptance_checklist"),
            task_payload.get("constraints"),
            goal,
            "The current problem is still too vague.",
        ),
        "workaround": _first_non_empty(
            task_payload.get("dependencies"),
            task_payload.get("related_files"),
            "Manual coordination, scattered pages, or fragile scripts.",
        ),
        "wedge": _first_non_empty(
            state.get("story_outputs"),
            task_payload.get("story_outputs"),
            "A smallest viable wedge that changes the user path immediately.",
        ),
        "differentiator": _first_non_empty(
            state.get("parsed_not_do"),
            task_payload.get("not_do"),
            "Avoid turning this into a generic CRUD or AI-slop feature.",
        ),
        "proof": _first_non_empty(
            task_payload.get("success_signal"),
            task_payload.get("acceptance_criteria"),
            state.get("verification_basis"),
            "Evidence that the user problem is actually reduced after delivery.",
        ),
    }


def _build_framing_summary(answers: list[dict[str, str]], *, mode: str) -> str:
    answer_map = {item["id"]: item["answer"] for item in answers}
    if mode == "builder":
        return (
            f"Build toward `{answer_map['coolest_version']}`, optimize for the wow moment with "
            f"`{answer_map['wow_moment']}`, and prototype the risky edge `{answer_map['hard_part']}` first."
        )
    return (
        f"Target `{answer_map['user']}` first, solve `{answer_map['pain']}` via the wedge "
        f"`{answer_map['wedge']}`, and judge success using `{answer_map['proof']}`."
    )


def _build_next_steps(answers: list[dict[str, str]], *, mode: str) -> list[str]:
    answer_map = {item["id"]: item["answer"] for item in answers}
    if mode == "builder":
        return [
            f"Prototype the coolest version as a narrow slice: {answer_map['coolest_version']}.",
            f"Use existing leverage before inventing new infrastructure: {answer_map['leverage']}.",
            f"Design one memorable detail around: {answer_map['delight']}.",
            f"Sequence the first implementation steps around: {answer_map['build_next']}.",
        ]
    return [
        f"Plan the product scope around the wedge: {answer_map['wedge']}.",
        f"Make sure the final implementation displaces the current workaround: {answer_map['workaround']}.",
        f"Preserve the differentiator in later design and build reviews: {answer_map['differentiator']}.",
        f"Wire acceptance and QA to the proof signal: {answer_map['proof']}.",
    ]


def _build_premises(answers: list[dict[str, str]], *, mode: str) -> list[str]:
    answer_map = {item["id"]: item["answer"] for item in answers}
    if mode == "builder":
        return [
            f"This idea should feel distinct because of `{answer_map['delight']}`.",
            f"The first prototype should prove the wow moment for `{answer_map['wow_moment']}`.",
            f"The riskiest unknown to collapse early is `{answer_map['hard_part']}`.",
        ]
    return [
        f"The most important user really is `{answer_map['user']}` for this cycle.",
        f"The first wedge should be `{answer_map['wedge']}` instead of a broader rollout.",
        f"Success must be measured by `{answer_map['proof']}`, not just by merged code.",
    ]


def _build_alternatives(answers: list[dict[str, str]], *, mode: str) -> list[str]:
    answer_map = {item["id"]: item["answer"] for item in answers}
    if mode == "builder":
        return [
            f"Lean demo: reuse everything possible and prove `{answer_map['wow_moment']}` quickly.",
            f"Delight-first slice: over-invest in `{answer_map['delight']}` and keep the surface narrow.",
            f"Risk-first prototype: isolate `{answer_map['hard_part']}` before polishing the rest.",
        ]
    return [
        f"Narrow wedge first: solve `{answer_map['pain']}` only for `{answer_map['user']}`.",
        f"Platform-first variant: overbuild the differentiator `{answer_map['differentiator']}` before adoption proof.",
        f"Proof-first variant: make `{answer_map['proof']}` measurable before expanding scope.",
    ]


def _build_approval_options(mode: str) -> list[str]:
    if mode == "builder":
        return [
            "Approve and carry this build sketch into plan-eng-review.",
            "Revise the framing and regenerate the design doc before planning.",
            "Start over in startup mode if this is becoming a company-shaped problem.",
        ]
    return [
        "Approve and carry this framing into plan-ceo-review.",
        "Revise the diagnostics before product scope is locked.",
        "Switch to builder mode if the goal is a prototype or learning exercise, not a company bet.",
    ]


def _build_design_doc(
    *,
    goal: str,
    mode: str,
    product_stage: str,
    framing_summary: str,
    answers: list[dict[str, str]],
    premises: list[str],
    alternatives: list[str],
    next_build_steps: list[str],
    approval_options: list[str],
    needs_context: bool,
) -> str:
    title = goal or "Office Hours Design"
    question_lines = [f"- **{item['question']}** {item['answer'] or '(pending user answer)'}" for item in answers]
    lines = [
        f"# Design: {title}",
        "",
        f"Status: {'NEEDS_CONTEXT' if needs_context else 'DRAFT_READY_FOR_REVIEW'}",
        f"Mode: {mode}",
        f"Product Stage: {product_stage if mode == 'startup' else 'builder-context'}",
        "",
        "## Framing Summary",
        framing_summary,
        "",
        "## Question Log",
        *question_lines,
        "",
        "## Premises To Confirm",
        *[f"- {item}" for item in premises],
        "",
        "## Alternatives Considered",
        *[f"- {item}" for item in alternatives],
        "",
        "## Next Steps",
        *[f"- {item}" for item in next_build_steps],
        "",
        "## Approval Options",
        *[f"- {item}" for item in approval_options],
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for item in value:
                if str(item).strip():
                    return str(item).strip()
    return ""
