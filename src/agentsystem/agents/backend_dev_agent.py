from __future__ import annotations

from pathlib import Path

from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.core.state import DevState


def backend_dev_node(state: DevState) -> dict[str, object]:
    print("[Backend Dev Agent] Starting backend work")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    backend_tasks = [task for task in state.get("subtasks", []) if task.type == "backend"]

    if not backend_tasks:
        print("[Backend Dev Agent] No backend tasks to process")
        return {
            "backend_result": "No backend work required.",
            "dev_results": {
                "backend": {
                    "updated_files": [],
                    "summary": "No backend changes were needed.",
                }
            },
        }

    updated_files = _apply_backend_changes(repo_b_path, state.get("task_payload"), backend_tasks)
    for file_path in updated_files:
        print(f"[Backend Dev Agent] Updated: {file_path}")

    print("[Backend Dev Agent] Backend work completed")
    return {
        "backend_result": "Backend schema and mock snapshot updated.",
        "dev_results": {
            "backend": {
                "updated_files": updated_files,
                "summary": "Updated backend snapshot scaffold.",
            }
        },
    }


def _apply_backend_changes(repo_b_path: Path, task_payload: dict[str, object] | None, backend_tasks) -> list[str]:
    updated_files: list[str] = []
    candidate_files: list[Path] = []
    for task in backend_tasks:
        for file_path in getattr(task, "files_to_modify", []):
            candidate = repo_b_path / str(file_path)
            if candidate not in candidate_files:
                candidate_files.append(candidate)
    if not candidate_files:
        candidate_files.append(repo_b_path / "apps" / "api" / "src" / "domain" / "agent_registry" / "service.py")

    for backend_file in candidate_files:
        if not backend_file.exists():
            backend_file.parent.mkdir(parents=True, exist_ok=True)
            backend_file.write_text("from __future__ import annotations\n", encoding="utf-8")
        content = backend_file.read_text(encoding="utf-8")
        rewritten = llm_rewrite_file(repo_b_path, task_payload, backend_file, system_role="Backend Builder Agent")
        if rewritten and rewritten != content:
            backend_file.write_text(rewritten, encoding="utf-8")
            updated_files.append(str(backend_file))
            continue
        marker = 'Position(symbol="000001.SZ", qty=300, avg_cost=12.45),'
        if backend_file.name == "service.py" and marker not in content:
            content = content.replace(
                '            positions=[Position(symbol="600519.SH", qty=100, avg_cost=1680.0)],',
                '            positions=[\n'
                '                Position(symbol="600519.SH", qty=100, avg_cost=1680.0),\n'
                '                Position(symbol="000001.SZ", qty=300, avg_cost=12.45),\n'
                "            ],",
            )
            backend_file.write_text(content, encoding="utf-8")
            updated_files.append(str(backend_file))
    return updated_files
