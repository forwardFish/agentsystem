from __future__ import annotations

from pathlib import Path

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

    updated_files = _apply_frontend_changes(repo_b_path)
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


def _apply_frontend_changes(repo_b_path: Path) -> list[str]:
    updated_files: list[str] = []
    frontend_file = repo_b_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
    if not frontend_file.exists():
        return updated_files

    content = frontend_file.read_text(encoding="utf-8")
    if FRONTEND_MARKER not in content:
        frontend_file.write_text(f"{content.rstrip()}\n{FRONTEND_MARKER}\n", encoding="utf-8")
        updated_files.append(str(frontend_file))

    return updated_files
