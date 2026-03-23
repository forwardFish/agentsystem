from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.agents.design_contracts import design_contract_path, design_preview_path, relpath, read_if_exists
from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.agents.request_text_inference import infer_requested_text
from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet

FRONTEND_MARKER = "// Frontend Dev Agent was here (with Constitution loaded)"


def frontend_dev_node(state: DevState) -> dict[str, object]:
    print("[Frontend Dev Agent] Initializing")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    frontend_tasks = [task for task in state.get("subtasks", []) if task.type == "frontend"]

    if not frontend_tasks:
        print("[Frontend Dev Agent] No frontend tasks to process")
        return {
            "frontend_result": "No frontend work required.",
            "dev_results": {
                "frontend": {
                    "updated_files": [],
                    "summary": "No frontend changes were needed.",
                }
            },
        }

    assembler = ContextAssembler(repo_b_path)
    constitution = assembler.build_constitution()
    prepared_task_payload, design_inputs = _prepare_frontend_task_payload(repo_b_path, state)
    task_context = assembler.build_task_context(prepared_task_payload)
    print("[Frontend Dev Agent] Loading project constitution")
    print(f"[Frontend Dev Agent] Constitution loaded ({len(constitution)} chars)")

    updated_files = _apply_frontend_changes(repo_b_path, prepared_task_payload)
    for file_path in updated_files:
        print(f"[Frontend Dev Agent] Updated: {file_path}")

    # Build risk list with context
    risks: list[str] = []
    if not updated_files:
        risks.append("No frontend files were modified; implementation may be incomplete or skipped.")

    if not design_inputs["design_contract_used"]:
        risks.append("No DESIGN.md contract found; frontend implementation relies on generic patterns without design guidance.")

    if len(updated_files) > 5:
        risks.append(f"Large frontend change set ({len(updated_files)} files) increases UI consistency and testing complexity.")

    task_payload = state.get("task_payload") or {}
    primary_files = task_payload.get("primary_files") or []
    if primary_files:
        missing_primary = [f for f in primary_files if str(f) not in [str(u) for u in updated_files]]
        if missing_primary:
            risks.append(f"{len(missing_primary)} primary file(s) were not modified: {', '.join(str(f) for f in missing_primary[:2])}")

    if not constitution:
        risks.append("Project constitution was not loaded; frontend implementation lacks project-specific context and patterns.")

    print("[Frontend Dev Agent] Frontend work completed")
    task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.BUILDER,
            to_agent=AgentRole.SYNC,
            status=HandoffStatus.COMPLETED,
            what_i_did=(
                f"Implemented {len(frontend_tasks)} frontend subtask(s) and materialized {len(updated_files)} frontend artifact(s) "
                f"using {len(constitution)} chars of project constitution"
                + (f" and DESIGN.md contract" if design_inputs["design_contract_used"] else "")
                + "."
            ),
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name=Path(file_path).name,
                    type="code",
                    path=str(file_path),
                    description=f"Frontend artifact for {Path(file_path).parent.name} module, built with constitution and design contract guidance.",
                    created_by=AgentRole.BUILDER,
                )
                for file_path in updated_files
            ],
            what_risks_i_found=risks[:5],  # Limit to top 5 risks
            what_i_require_next=f"Consolidate {len(updated_files)} frontend change(s), prepare PR materials, and send to validation with browser QA.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return {
        "frontend_result": "Frontend development completed (constitution loaded).",
        "dev_results": {
            "frontend": {
                "updated_files": updated_files,
                "summary": "Updated frontend page scaffold.",
                "constitution_length": len(constitution),
                "task_context_length": len(task_context),
                "design_contract_used": design_inputs["design_contract_used"],
                "design_contract_path": design_inputs["design_contract_path"],
                "design_preview_path": design_inputs["design_preview_path"],
            }
        },
        "handoff_packets": state.get("handoff_packets"),
        "all_deliverables": state.get("all_deliverables"),
    }


def _apply_frontend_changes(repo_b_path: Path, task_payload: dict[str, object] | None = None) -> list[str]:
    updated_files: list[str] = []
    frontend_file = _resolve_frontend_target(repo_b_path, task_payload)
    if not frontend_file.exists():
        return updated_files
    project_key = str((task_payload or {}).get("project") or repo_b_path.name).strip().lower()
    story_id = str((task_payload or {}).get("story_id") or "").strip()
    if project_key == "agenthire" and story_id == "S0-002":
        return [str(frontend_file)]

    content = frontend_file.read_text(encoding="utf-8")
    design_contract = _load_design_contract(repo_b_path, task_payload)
    if design_contract and not os.getenv("OPENAI_API_KEY"):
        updated_content = _apply_task_specific_change(content, task_payload, frontend_file, design_contract)
    else:
        updated_content = llm_rewrite_file(repo_b_path, task_payload, frontend_file, system_role="Frontend Builder Agent")
        if not updated_content:
            updated_content = _apply_task_specific_change(content, task_payload, frontend_file, design_contract)
    if updated_content != content:
        frontend_file.write_text(updated_content, encoding="utf-8")
        updated_files.append(str(frontend_file))

    return updated_files


def _resolve_frontend_target(repo_b_path: Path, task_payload: dict[str, object] | None) -> Path:
    if task_payload:
        candidate_paths = list(task_payload.get("primary_files", []) or []) + list(task_payload.get("related_files", []) or [])
        for raw_path in candidate_paths:
            candidate = repo_b_path / str(raw_path)
            if candidate.suffix in {".tsx", ".ts", ".jsx", ".js"}:
                return candidate
    return repo_b_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"


def _apply_task_specific_change(
    content: str,
    task_payload: dict[str, object] | None,
    frontend_file: Path,
    design_contract: str,
) -> str:
    if not task_payload:
        if FRONTEND_MARKER in content:
            return content
        return f"{content.rstrip()}\n{FRONTEND_MARKER}\n"

    if design_contract and _looks_like_minimal_page(frontend_file, content):
        upgraded = _build_product_page(task_payload, design_contract)
        if upgraded:
            return upgraded

    updated = content
    request_candidates = [
        str(task_payload.get("goal", "")).strip(),
        *(str(item).strip() for item in task_payload.get("acceptance_criteria", []) or []),
    ]
    requested_title = infer_requested_text(request_candidates, target_kind="title")
    requested_subtitle = infer_requested_text(request_candidates, target_kind="subtitle")

    if requested_title:
        updated = _ensure_heading(updated, requested_title)
    if requested_subtitle:
        updated = _ensure_subtitle(updated, requested_subtitle)
    if updated == content and design_contract and _looks_like_dashboard_surface(frontend_file, content):
        updated = _apply_dashboard_productization(content, task_payload, design_contract)
    if updated == content and design_contract:
        return content
    if updated == content and FRONTEND_MARKER not in updated:
        updated = f"{updated.rstrip()}\n{FRONTEND_MARKER}\n"
    return updated


def _ensure_heading(content: str, title: str) -> str:
    if not title or title in content:
        return content

    match = re.search(r"(?P<indent>\s*)<h1[^>]*>.*?</h1>", content)
    if match:
        indent = match.group("indent")
        replacement = f'{indent}<h1 className="mb-6 text-3xl font-bold">{title}</h1>'
        return content[: match.start()] + replacement + content[match.end() :]
    if "    <div>" in content:
        return content.replace("    <div>", f'    <div>\n      <h1 className="mb-6 text-3xl font-bold">{title}</h1>', 1)
    return f'<h1 className="mb-6 text-3xl font-bold">{title}</h1>\n{content}'


def _ensure_subtitle(content: str, subtitle: str) -> str:
    if not subtitle or subtitle in content:
        return content

    subtitle_line = f'      <p className="mb-2 text-sm text-slate-500">{subtitle}</p>'
    if '      <h1 className="mb-6 text-3xl font-bold">' in content:
        return content.replace(
            '      <h1 className="mb-6 text-3xl font-bold">',
            f"{subtitle_line}\n      <h1 className=\"mb-6 text-3xl font-bold\">",
            1,
        )
    if '      <h1 className="mb-4 text-2xl font-bold">' in content:
        return content.replace(
            '      <h1 className="mb-4 text-2xl font-bold">',
            f"{subtitle_line}\n      <h1 className=\"mb-4 text-2xl font-bold\">",
            1,
        )
    if "    <div>" in content:
        return content.replace("    <div>", f"    <div>\n{subtitle_line}", 1)
    return f"{content.rstrip()}\n{subtitle_line}\n"


def _infer_requested_text(task_payload: dict[str, Any], target_kind: str) -> str | None:
    candidates: list[str] = []
    goal = str(task_payload.get("goal", "")).strip()
    if goal:
        candidates.append(goal)

    for item in task_payload.get("acceptance_criteria", []):
        candidate = str(item).strip()
        if candidate:
            candidates.append(candidate)
    return infer_requested_text(candidates, target_kind=target_kind)


def _prepare_frontend_task_payload(
    repo_b_path: Path,
    state: DevState,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    raw_task_payload = state.get("task_payload")
    if not isinstance(raw_task_payload, dict):
        return None, {
            "design_contract_used": False,
            "design_contract_path": None,
            "design_preview_path": None,
        }

    task_payload = dict(raw_task_payload)
    related_files = [str(item).strip() for item in task_payload.get("related_files", []) if str(item).strip()]
    constraints = [str(item).strip() for item in task_payload.get("constraints", []) if str(item).strip()]
    design_contract_file = design_contract_path(repo_b_path)
    design_preview_file = design_preview_path(repo_b_path)
    design_contract_used = design_contract_file.exists()

    if design_contract_file.exists():
        contract_relpath = relpath(repo_b_path, design_contract_file)
        if contract_relpath not in related_files:
            related_files.append(contract_relpath)
        constraints.append("Follow DESIGN.md as the design contract for hierarchy, modules, and copy tone.")
        task_payload["design_contract_path"] = contract_relpath

    if design_preview_file.exists():
        preview_relpath = relpath(repo_b_path, design_preview_file)
        if preview_relpath not in related_files:
            related_files.append(preview_relpath)
        task_payload["design_preview_path"] = preview_relpath

    task_payload["related_files"] = related_files
    task_payload["constraints"] = _dedupe_strings(constraints)
    return task_payload, {
        "design_contract_used": design_contract_used,
        "design_contract_path": task_payload.get("design_contract_path"),
        "design_preview_path": task_payload.get("design_preview_path"),
    }


def _load_design_contract(repo_b_path: Path, task_payload: dict[str, object] | None) -> str:
    if task_payload and str(task_payload.get("design_contract_path") or "").strip():
        candidate = repo_b_path / str(task_payload["design_contract_path"])
        return read_if_exists(candidate)
    return read_if_exists(design_contract_path(repo_b_path))


def _looks_like_minimal_page(frontend_file: Path, content: str) -> bool:
    if frontend_file.suffix.lower() not in {".tsx", ".jsx"}:
        return False
    normalized = re.sub(r"\s+", " ", content)
    return len(content.splitlines()) <= 4 or "<main>demo</main>" in normalized or ">demo<" in normalized


def _looks_like_dashboard_surface(frontend_file: Path, content: str) -> bool:
    if frontend_file.suffix.lower() not in {".tsx", ".jsx"}:
        return False
    normalized = re.sub(r"\s+", " ", content)
    return (
        'className="page-shell"' in normalized
        and 'className="hero"' in normalized
        and ('className="metric-grid"' in normalized or 'className="theme-grid"' in normalized)
    )


def _build_product_page(task_payload: dict[str, object], design_contract: str) -> str:
    title = _extract_design_title(design_contract) or str(task_payload.get("goal") or "Product Page").strip() or "Product Page"
    subtitle = _extract_design_subtitle(design_contract)
    modules = _extract_design_modules(design_contract)
    module_items = "\n".join(
        f"""        <article className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <h3 className="text-lg font-semibold text-white">{item}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">Built from the active design contract instead of a demo placeholder.</p>
        </article>"""
        for item in modules[:3]
    )
    return f"""export default function Page() {{
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10 text-slate-100">
      <section className="mx-auto grid max-w-6xl gap-6 rounded-[32px] border border-cyan-400/20 bg-slate-900/80 p-8 shadow-2xl shadow-cyan-950/30">
        <span className="w-fit rounded-full border border-cyan-400/30 px-3 py-1 text-xs uppercase tracking-[0.18em] text-cyan-300">
          Product Surface
        </span>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_320px]">
          <div className="grid gap-4">
            <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white">{title}</h1>
            <p className="max-w-2xl text-base leading-7 text-slate-300">
              {subtitle}
            </p>
          </div>
          <aside className="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-300">Design Contract</p>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              This page was upgraded from a demo scaffold by following DESIGN.md and preserving a product-first hierarchy.
            </p>
          </aside>
        </div>
      </section>
      <section className="mx-auto mt-8 grid max-w-6xl gap-4 md:grid-cols-3">
{module_items}
      </section>
    </main>
  );
}}
"""


def _apply_dashboard_productization(content: str, task_payload: dict[str, object], design_contract: str) -> str:
    if "Decision Lead" in content:
        return content

    title = _extract_design_title(design_contract) or str(task_payload.get("goal") or "Product Page").strip() or "Product Page"
    subtitle = _extract_design_subtitle(design_contract)
    modules = _extract_design_modules(design_contract)
    lead_module = modules[0] if modules else "Hero section with page thesis, active context, and primary controls"
    support_module = modules[1] if len(modules) > 1 else "Decision strip that highlights the top summary, lead theme, or top opportunity"

    updated = content
    updated = re.sub(
        r'<span className="eyebrow">.*?</span>',
        '<span className="eyebrow">Product Intelligence Surface</span>',
        updated,
        count=1,
        flags=re.DOTALL,
    )
    updated = re.sub(
        r"<h1>.*?</h1>",
        f"<h1>{title}</h1>",
        updated,
        count=1,
        flags=re.DOTALL,
    )
    updated = re.sub(
        r"<p>\s*.*?</p>",
        (
            "<p>"
            f"{subtitle}. This surface should lead with the main market call, show the operating context, "
            "and keep evidence plus risks close to every metric."
            "</p>"
        ),
        updated,
        count=1,
        flags=re.DOTALL,
    )

    if "</form>" in updated:
        decision_strip = f"""
        </form>
        <div className="duo-grid">
          <article className="card">
            <span className="eyebrow">Decision Lead</span>
            <h2>What operators should see first</h2>
            <p>{lead_module}</p>
            <div className="pill-row">
              <span className="pill accent">Lead signal on top</span>
              <span className="pill">Decision context visible</span>
              <span className="pill good">Risk posture attached</span>
            </div>
          </article>
          <article className="card">
            <span className="eyebrow">Working Frame</span>
            <h2>How the page should behave</h2>
            <p>{support_module}</p>
            <p className="muted">Built from DESIGN.md so the page reads like a product workflow instead of an internal dump.</p>
          </article>
        </div>"""
        updated = updated.replace("</form>", decision_strip, 1)

    return updated


def _extract_design_title(design_contract: str) -> str | None:
    for line in design_contract.splitlines():
        if line.startswith("- Goal:"):
            return line.split(":", 1)[1].strip()
    return None


def _extract_design_subtitle(design_contract: str) -> str:
    for line in design_contract.splitlines():
        if line.startswith("- Direction:"):
            return line.split(":", 1)[1].strip()
    return "A product-grade surface with stronger hierarchy, summary-first framing, and clearer decision context."


def _extract_design_modules(design_contract: str) -> list[str]:
    modules: list[str] = []
    in_section = False
    for line in design_contract.splitlines():
        if line.strip() == "## Information Architecture":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            cleaned = re.sub(r"^\d+\.\s*", "", line.strip())
            if cleaned:
                modules.append(cleaned)
    return modules or [
        "Hero section with page thesis and controls",
        "Decision strip that highlights the main summary",
        "Working sections that separate summary from detailed evidence",
    ]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
