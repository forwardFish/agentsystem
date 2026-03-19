from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agentsystem.agents.design_contracts import (
    design_contract_path,
    design_meta_dir,
    design_preview_notes_path,
    design_preview_path,
    design_report_path,
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


def design_consultation_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    meta_dir = design_meta_dir(repo_b_path)
    meta_dir.mkdir(parents=True, exist_ok=True)

    task_payload = state.get("task_payload") or {}
    goal = str(state.get("parsed_goal") or state.get("user_requirement") or task_payload.get("goal") or "").strip()
    story_kind = str(state.get("story_kind") or task_payload.get("story_kind") or "ui").strip() or "ui"
    risk_level = str(state.get("risk_level") or task_payload.get("risk_level") or "medium").strip() or "medium"
    primary_files = _clean_lines(state.get("primary_files") or task_payload.get("primary_files"))
    related_files = _clean_lines(task_payload.get("related_files"))
    acceptance = _clean_lines(state.get("acceptance_checklist") or task_payload.get("acceptance_criteria"))
    constraints = _clean_lines(state.get("parsed_constraints") or task_payload.get("constraints"))
    surface_scope = primary_files or related_files

    audience = _infer_audience(surface_scope, goal)
    visual_direction = _infer_visual_direction(surface_scope, goal)
    safe_choice = _safe_choice(surface_scope)
    creative_risk = _creative_risk(surface_scope)
    modules = _suggest_modules(surface_scope, acceptance)
    visual_tokens = _visual_tokens(surface_scope)
    interaction_rules = _interaction_rules(risk_level)
    scope_lines = [f"- {item}" for item in surface_scope] or ["- No explicit UI file scope declared."]
    constraint_lines = [f"- {item}" for item in constraints] or [
        "- Preserve current navigation, working states, and repository patterns."
    ]

    report_lines = [
        "# Design Consultation",
        "",
        f"- Goal: {goal or 'n/a'}",
        f"- Story kind: {story_kind}",
        f"- Risk level: {risk_level}",
        f"- Audience: {audience}",
        f"- Visual direction: {visual_direction}",
        "",
        "## Surface Scope",
        *scope_lines,
        "",
        "## Safe Choice",
        f"- {safe_choice}",
        "",
        "## Creative Risk",
        f"- {creative_risk}",
        "",
        "## Recommended Modules",
        *[f"- {item}" for item in modules],
        "",
        "## Interaction Rules",
        *[f"- {item}" for item in interaction_rules],
        "",
        "## Constraints To Preserve",
        *constraint_lines,
    ]

    design_md_lines = [
        "# DESIGN",
        "",
        "## Product Intent",
        f"- Goal: {goal or 'n/a'}",
        f"- Audience: {audience}",
        f"- Surface scope: {', '.join(surface_scope) if surface_scope else 'n/a'}",
        "",
        "## Visual System",
        f"- Direction: {visual_direction}",
        *[f"- {item}" for item in visual_tokens],
        "",
        "## Information Architecture",
        *[f"1. {item}" if index == 0 else f"{index + 1}. {item}" for index, item in enumerate(modules)],
        "",
        "## Interaction Rules",
        *[f"- {item}" for item in interaction_rules],
        "",
        "## Copy Direction",
        "- Write like a product surface, not an internal demo board.",
        "- Lead with the main decision, then evidence, then risks.",
        "- Prefer concise labels over engineering jargon in the page chrome.",
        "",
        "## Implementation Notes",
        "- Preserve current data contracts and route shape.",
        "- Use layered panels, strong hierarchy, and explicit summary sections above dense detail blocks.",
        "- Keep empty, loading, partial-data, and failure states visible.",
        "",
        "## Review Checklist",
        "- The first screen explains what the page is for.",
        "- The main theme or decision lead is visible without scanning the full list.",
        "- The page no longer reads like a demo table or placeholder board.",
    ]

    preview_notes = {
        "surface_scope": surface_scope,
        "audience": audience,
        "visual_direction": visual_direction,
        "safe_choice": safe_choice,
        "creative_risk": creative_risk,
        "recommended_modules": modules,
        "interaction_rules": interaction_rules,
        "visual_tokens": visual_tokens,
    }

    preview_html = _build_preview_html(goal, audience, visual_direction, modules, safe_choice, creative_risk)

    report_file = design_report_path(repo_b_path)
    contract_file = design_contract_path(repo_b_path)
    preview_notes_file = design_preview_notes_path(repo_b_path)
    preview_file = design_preview_path(repo_b_path)

    report_file.write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")
    contract_file.write_text("\n".join(design_md_lines).strip() + "\n", encoding="utf-8")
    preview_notes_file.write_text(json.dumps(preview_notes, ensure_ascii=False, indent=2), encoding="utf-8")
    preview_file.write_text(preview_html, encoding="utf-8")

    shared_blackboard = dict(state.get("shared_blackboard") or {})
    shared_blackboard["design_consultation"] = {
        "goal": goal,
        "audience": audience,
        "visual_direction": visual_direction,
        "modules": modules,
        "contract_path": str(contract_file),
        "preview_path": str(preview_file),
    }

    state["design_consultation_success"] = True
    state["design_consultation_dir"] = str(meta_dir)
    state["design_consultation_report"] = report_file.read_text(encoding="utf-8")
    state["design_contract_path"] = str(contract_file)
    state["design_preview_path"] = str(preview_file)
    state["shared_blackboard"] = shared_blackboard
    state["current_step"] = "design_consultation_done"
    add_executed_mode(state, "design-consultation")

    task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.DESIGN_CONSULTATION,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did="Converted the UI story into a concrete design contract with a reusable DESIGN.md and preview artifact.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Design Consultation Report",
                    type="report",
                    path=f".meta/{task_scope_name}/design_consultation/design_consultation_report.md",
                    description="Design framing, audience, modules, and visual direction for the target surface.",
                    created_by=AgentRole.DESIGN_CONSULTATION,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="DESIGN.md",
                    type="document",
                    path="DESIGN.md",
                    description="Executable design contract for downstream frontend implementation and review.",
                    created_by=AgentRole.DESIGN_CONSULTATION,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Design Preview",
                    type="html",
                    path=f".meta/{task_scope_name}/design_consultation/design_preview.html",
                    description="Preview artifact describing the intended product direction before implementation.",
                    created_by=AgentRole.DESIGN_CONSULTATION,
                ),
            ],
            what_risks_i_found=[
                "Without a design contract, high-risk UI work tends to fall back to generic dashboard patterns.",
                "The first screen should explain the page's product value before dense data blocks begin.",
            ],
            what_i_require_next="Implement the target surface against DESIGN.md, then run design-aware QA against the same contract.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        )
    )
    return state


def route_after_design_consultation(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "design_consultation":
        return "__end__"
    return "workspace_prep"


def _clean_lines(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _infer_audience(surface_scope: list[str], goal: str) -> str:
    scope = " ".join(surface_scope).lower()
    lowered_goal = goal.lower()
    if "sprint" in scope or "dashboard" in scope or "analytics" in scope:
        return "operators and researchers who need a decision-oriented working surface"
    if "landing" in scope or "marketing" in scope or "homepage" in lowered_goal:
        return "end users evaluating the product for the first time"
    return "product users who need a clear, high-signal interface"


def _infer_visual_direction(surface_scope: list[str], goal: str) -> str:
    scope = " ".join(surface_scope).lower()
    lowered_goal = goal.lower()
    if "sprint" in scope or "dashboard" in scope or "theme" in lowered_goal:
        return "editorial market-intelligence dashboard with layered panels and clear decision hierarchy"
    if "form" in scope or "wizard" in lowered_goal:
        return "guided product workflow with strong step framing and calm validation states"
    return "product-grade application surface with bold hierarchy and restrained detail density"


def _safe_choice(surface_scope: list[str]) -> str:
    scope = " ".join(surface_scope).lower()
    if "page.tsx" in scope:
        return "Use a strong hero plus summary rail before dense cards or tables."
    return "Start with a clear page thesis, then break the work surface into named sections."


def _creative_risk(surface_scope: list[str]) -> str:
    scope = " ".join(surface_scope).lower()
    if "dashboard" in scope or "sprint" in scope:
        return "Introduce an opinionated summary strip so the page feels like a research cockpit instead of a report dump."
    return "Use one memorable visual motif rather than a neutral internal-tool layout."


def _suggest_modules(surface_scope: list[str], acceptance: list[str]) -> list[str]:
    modules = [
        "Hero section with page thesis, active context, and primary controls",
        "Decision strip that highlights the top summary, lead theme, or top opportunity",
        "Working sections that separate summary from detailed evidence",
        "Shared risk and method boundary section near the end of the page",
    ]
    if acceptance:
        modules.append("Explicit handling for empty, partial, failure, and refresh states")
    if any("table" in str(item).lower() for item in acceptance):
        modules.append("Matrix view that supports quick horizontal comparison without becoming the first thing users see")
    return modules


def _visual_tokens(surface_scope: list[str]) -> list[str]:
    scope = " ".join(surface_scope).lower()
    if "sprint" in scope or "dashboard" in scope:
        return [
            "Deep navy or carbon base with restrained cyan / mint accents",
            "Layered glass-like panels with clear contrast between summary and detail",
            "Large editorial headline paired with compact analytical labels",
        ]
    return [
        "Clear background atmosphere rather than a flat single-color page",
        "Expressive headline hierarchy and compact supporting labels",
        "One accent color family for primary emphasis and one for caution/risk",
    ]


def _interaction_rules(risk_level: str) -> list[str]:
    rules = [
        "Active filters and view modes should be visually obvious.",
        "Primary metrics must sit next to interpretation, not alone.",
        "Dense detail blocks should be chunked into evidence, signals, and risks.",
    ]
    if risk_level == "high":
        rules.append("High-risk UI work should preserve navigation continuity and state clarity across refresh and partial data.")
    return rules


def _build_preview_html(
    goal: str,
    audience: str,
    visual_direction: str,
    modules: list[str],
    safe_choice: str,
    creative_risk: str,
) -> str:
    module_cards = "\n".join(f"<li>{item}</li>" for item in modules)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Design Preview</title>
    <style>
      body {{
        margin: 0;
        font-family: "Segoe UI", sans-serif;
        background: linear-gradient(180deg, #08111f, #0c1827 55%, #07101a);
        color: #eaf4ff;
      }}
      main {{
        max-width: 1080px;
        margin: 0 auto;
        padding: 40px 24px 64px;
      }}
      .hero, .card {{
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 24px;
        background: rgba(11,24,40,0.86);
        padding: 24px;
        box-shadow: 0 24px 60px rgba(0,0,0,0.22);
      }}
      .hero {{
        margin-bottom: 18px;
      }}
      .grid {{
        display: grid;
        gap: 18px;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      }}
      .eyebrow {{
        display: inline-block;
        margin-bottom: 12px;
        color: #55d4ff;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 12px;
      }}
      h1, h2 {{
        margin: 0 0 12px;
      }}
      p, li {{
        color: #9cb1cd;
        line-height: 1.7;
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <span class="eyebrow">Design Consultation Preview</span>
        <h1>{goal or "Product page direction"}</h1>
        <p><strong>Audience:</strong> {audience}</p>
        <p><strong>Direction:</strong> {visual_direction}</p>
      </section>
      <section class="grid">
        <article class="card">
          <span class="eyebrow">Safe Choice</span>
          <h2>Reliable Upgrade</h2>
          <p>{safe_choice}</p>
        </article>
        <article class="card">
          <span class="eyebrow">Creative Risk</span>
          <h2>Distinctive Move</h2>
          <p>{creative_risk}</p>
        </article>
        <article class="card">
          <span class="eyebrow">Modules</span>
          <h2>Recommended Structure</h2>
          <ul>
            {module_cards}
          </ul>
        </article>
      </section>
    </main>
  </body>
</html>
"""
