from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.core.state import DevState

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
    task_context = assembler.build_task_context(state.get("task_payload"))
    print("[Frontend Dev Agent] Loading project constitution")
    print(f"[Frontend Dev Agent] Constitution loaded ({len(constitution)} chars)")

    updated_files = _apply_frontend_changes(repo_b_path, state.get("task_payload"))
    for file_path in updated_files:
        print(f"[Frontend Dev Agent] Updated: {file_path}")

    print("[Frontend Dev Agent] Frontend work completed")
    return {
        "frontend_result": "Frontend development completed (constitution loaded).",
        "dev_results": {
            "frontend": {
                "updated_files": updated_files,
                "summary": "Updated frontend page scaffold.",
                "constitution_length": len(constitution),
                "task_context_length": len(task_context),
            }
        },
    }


def _apply_frontend_changes(repo_b_path: Path, task_payload: dict[str, object] | None = None) -> list[str]:
    updated_files: list[str] = []
    frontend_file = _resolve_frontend_target(repo_b_path, task_payload)
    if not frontend_file.exists():
        return updated_files

    content = frontend_file.read_text(encoding="utf-8")
    updated_content = llm_rewrite_file(repo_b_path, task_payload, frontend_file, system_role="Frontend Builder Agent")
    if not updated_content:
        updated_content = _apply_task_specific_change(content, task_payload)
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


def _apply_task_specific_change(content: str, task_payload: dict[str, object] | None) -> str:
    if not task_payload:
        if FRONTEND_MARKER in content:
            return content
        return f"{content.rstrip()}\n{FRONTEND_MARKER}\n"

    updated = content
    requested_title = _infer_requested_text(task_payload, "title")
    requested_subtitle = _infer_requested_text(task_payload, "subtitle")

    if requested_title:
        updated = _ensure_heading(updated, requested_title)
    if requested_subtitle:
        updated = _ensure_subtitle(updated, requested_subtitle)
    if updated == content and FRONTEND_MARKER not in updated:
        updated = f"{updated.rstrip()}\n{FRONTEND_MARKER}\n"
    return updated


def _ensure_heading(content: str, title: str) -> str:
    if not title or title in content:
        return content

    match = re.search(r'(?P<indent>\s*)<h1[^>]*>.*?</h1>', content)
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
            f'{subtitle_line}\n      <h1 className="mb-6 text-3xl font-bold">',
            1,
        )
    if '      <h1 className="mb-4 text-2xl font-bold">' in content:
        return content.replace(
            '      <h1 className="mb-4 text-2xl font-bold">',
            f'{subtitle_line}\n      <h1 className="mb-4 text-2xl font-bold">',
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

    for candidate in candidates:
        quoted = _extract_quoted_text(candidate)
        if quoted:
            return quoted

    if target_kind == "subtitle":
        patterns = [
            r"加(?:一个|个)?副标题[:：]?\s*(.+)$",
            r"添加(?:一个|个)?副标题[:：]?\s*(.+)$",
            r"副标题(?:为|是)?[:：]?\s*(.+)$",
            r"add\s+(?:a\s+)?subtitle[:：]?\s*(.+)$",
        ]
    else:
        patterns = [
            r"加(?:一个|个)?标题[:：]?\s*(.+)$",
            r"添加(?:一个|个)?标题[:：]?\s*(.+)$",
            r"标题(?:为|是)?[:：]?\s*(.+)$",
            r"add\s+(?:a\s+)?title[:：]?\s*(.+)$",
        ]

    for candidate in candidates:
        cleaned = candidate.strip(" ，。：；!?\"'“”‘’「」『』")
        for pattern in patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip(" ，。：；!?\"'“”‘’「」『』")
            if value:
                return value
    return None


def _extract_quoted_text(text: str) -> str | None:
    match = re.search(r"[\"'“”‘’「」『』](.*?)[\"'“”‘’「」『』]", text)
    if match:
        return match.group(1).strip()
    return None
