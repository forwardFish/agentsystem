from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


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
) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    docs_root = _resolve_requirement_docs_root(repo_path)
    meta_dir = repo_path.parent / ".meta" / repo_path.name / "plan_ceo_review"
    docs_root.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    normalized_requirement = str(requirement_text or "").strip()
    if not normalized_requirement:
        raise ValueError("requirement_text must not be empty")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    resolved_title = str(title or "").strip() or _derive_title(normalized_requirement, project)
    slug = _slugify(resolved_title)
    requirement_doc_path = docs_root / f"{timestamp}_{slug}.md"
    review_report_path = meta_dir / "product_review_report.md"
    opportunity_map_path = meta_dir / "opportunity_map.json"

    constraint_items = _normalize_list(constraints)
    success_items = _normalize_list(success_signal)
    resolved_problem = str(user_problem or "").strip() or _derive_problem(normalized_requirement)
    resolved_audience = str(audience or "").strip() or "Primary end users described in the requirement"

    requirement_doc = _build_requirement_doc(
        title=resolved_title,
        project=project,
        requirement_text=normalized_requirement,
        user_problem=resolved_problem,
        constraints=constraint_items,
        success_signals=success_items,
        audience=resolved_audience,
        delivery_mode=delivery_mode,
        source_requirement_path=source_requirement_path,
    )
    review_report = _build_review_report(
        title=resolved_title,
        project=project,
        requirement_text=normalized_requirement,
        user_problem=resolved_problem,
        constraints=constraint_items,
        success_signals=success_items,
        audience=resolved_audience,
        delivery_mode=delivery_mode,
    )
    opportunity_map = {
        "title": resolved_title,
        "project": project,
        "delivery_mode": delivery_mode,
        "user_problem": resolved_problem,
        "target_audience": resolved_audience,
        "constraints": constraint_items,
        "success_signals": success_items,
        "source_requirement_path": str(Path(source_requirement_path).resolve()) if source_requirement_path else None,
        "requirement_doc_path": str(requirement_doc_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "next_recommended_actions": _build_next_actions(project, requirement_doc_path, delivery_mode),
    }

    requirement_doc_path.write_text(requirement_doc, encoding="utf-8")
    review_report_path.write_text(review_report, encoding="utf-8")
    opportunity_map_path.write_text(json.dumps(opportunity_map, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "title": resolved_title,
        "delivery_mode": delivery_mode,
        "requirement_doc_path": str(requirement_doc_path),
        "review_report_path": str(review_report_path),
        "opportunity_map_path": str(opportunity_map_path),
        "next_recommended_actions": opportunity_map["next_recommended_actions"],
    }


def _resolve_requirement_docs_root(repo_path: Path) -> Path:
    docs_dir = repo_path / "docs"
    if docs_dir.exists() or repo_path.name in {"versefina", "finahunt"}:
        return docs_dir / "requirements"
    return repo_path / "requirements"


def _build_requirement_doc(
    *,
    title: str,
    project: str,
    requirement_text: str,
    user_problem: str,
    constraints: list[str],
    success_signals: list[str],
    audience: str,
    delivery_mode: str,
    source_requirement_path: str | Path | None,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Context",
        f"- Project: {project}",
        f"- Delivery mode: {delivery_mode}",
        f"- Source requirement file: {Path(source_requirement_path).resolve() if source_requirement_path else 'inline input'}",
        "",
        "## User Problem",
        user_problem,
        "",
        "## Target Audience",
        audience,
        "",
        "## Requirement Summary",
        requirement_text,
        "",
        "## Product Constraints",
    ]
    if constraints:
        lines.extend(f"- {item}" for item in constraints)
    else:
        lines.append("- Follow the repo contract, existing architecture, and blast-radius limits during delivery.")
    lines.extend(["", "## Success Signals"])
    if success_signals:
        lines.extend(f"- {item}" for item in success_signals)
    else:
        lines.append("- The delivered stories complete the requested user outcome with acceptance evidence.")
    lines.extend(
        [
            "",
            "## Delivery Decision",
            f"- Current mode: {delivery_mode}",
            "- `interactive`: stop after backlog generation and continue with human confirmation.",
            "- `auto`: continue into sprint/story execution automatically after this document is accepted.",
            "",
            "## Execution Notes",
            "- This document is the canonical requirement input for downstream backlog generation.",
            "- If scope changes, regenerate this file or create a new requirement revision before rerunning delivery.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_review_report(
    *,
    title: str,
    project: str,
    requirement_text: str,
    user_problem: str,
    constraints: list[str],
    success_signals: list[str],
    audience: str,
    delivery_mode: str,
) -> str:
    lines = [
        f"# Plan CEO Review Report: {title}",
        "",
        "## Product Outcome",
        f"Deliver a clear, testable product increment for `{project}` that solves: {user_problem}",
        "",
        "## Audience",
        audience,
        "",
        "## Why This Matters",
        requirement_text,
        "",
        "## Guardrails",
    ]
    if constraints:
        lines.extend(f"- {item}" for item in constraints)
    else:
        lines.append("- Keep the implementation inside the declared repo and avoid unnecessary scope expansion.")
    lines.extend(["", "## Success Signals"])
    if success_signals:
        lines.extend(f"- {item}" for item in success_signals)
    else:
        lines.append("- The requirement can be decomposed into sprint/story assets and executed end to end.")
    lines.extend(
        [
            "",
            "## Delivery Recommendation",
            f"- Recommended next mode: {delivery_mode}",
            "- Use this requirement document as the source of truth for backlog generation.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_next_actions(project: str, requirement_doc_path: Path, delivery_mode: str) -> list[str]:
    quoted_path = str(requirement_doc_path)
    if delivery_mode == "auto":
        return [
            f"Run auto-deliver against {quoted_path} for project {project}.",
            "Continue sprint/story execution until all generated stories are complete.",
        ]
    return [
        f"Review and refine the generated requirement doc at {quoted_path}.",
        f"Run auto-deliver with --requirement-file {quoted_path} when you want to execute the backlog.",
    ]


def _derive_title(requirement_text: str, project: str) -> str:
    first_line = next((line.strip(" #-\t") for line in requirement_text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:80]
    return f"{project} requirement"


def _derive_problem(requirement_text: str) -> str:
    sentence = next((line.strip() for line in requirement_text.splitlines() if line.strip()), "")
    if sentence:
        return sentence[:200]
    return "Clarify the desired user-facing outcome before implementation starts."


def _normalize_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = re.split(r"[\r\n;；]+", str(value))
    return [item.strip(" -\t") for item in normalized if item.strip(" -\t")]


def _slugify(value: str) -> str:
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return ascii_only[:80] or "requirement"
