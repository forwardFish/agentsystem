from __future__ import annotations

from pathlib import Path
import re

from agentsystem.adapters.context_assembler import ContextAssembler
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
                "summary": "Updated frontend observation page scaffold.",
                "constitution_length": len(constitution),
            }
        },
    }


def _apply_frontend_changes(repo_b_path: Path, task_payload: dict[str, object] | None = None) -> list[str]:
    updated_files: list[str] = []
    frontend_file = _resolve_frontend_target(repo_b_path, task_payload)
    if not frontend_file.exists():
        return updated_files

    content = frontend_file.read_text(encoding="utf-8")
    updated_content = _apply_task_specific_change(content, task_payload)
    if updated_content != content:
        frontend_file.write_text(updated_content, encoding="utf-8")
        updated_files.append(str(frontend_file))

    return updated_files


def _resolve_frontend_target(repo_b_path: Path, task_payload: dict[str, object] | None) -> Path:
    if task_payload:
        for raw_path in task_payload.get("related_files", []):
            candidate = repo_b_path / str(raw_path)
            if candidate.suffix in {".tsx", ".ts", ".jsx", ".js"}:
                return candidate
    return repo_b_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"


def _apply_task_specific_change(content: str, task_payload: dict[str, object] | None) -> str:
    if not task_payload:
        if FRONTEND_MARKER in content:
            return content
        return f"{content.rstrip()}\n{FRONTEND_MARKER}\n"

    goal = str(task_payload.get("goal", ""))
    subtitle = _extract_quoted_text(goal)
    if not subtitle:
        if FRONTEND_MARKER in content:
            return content
        return f"{content.rstrip()}\n{FRONTEND_MARKER}\n"

    subtitle_line = f'      <p className="mb-2 text-sm text-slate-500">{subtitle}</p>'
    if subtitle in content:
        return content
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


def _extract_quoted_text(goal: str) -> str | None:
    match = re.search(r"[\"'“”‘’]([^\"'“”‘’]+)[\"'“”‘’]", goal)
    if match:
        return match.group(1).strip()
    return None
