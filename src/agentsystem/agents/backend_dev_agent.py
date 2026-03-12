from __future__ import annotations

from pathlib import Path

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

    updated_files = _apply_backend_changes(repo_b_path)
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


def _apply_backend_changes(repo_b_path: Path) -> list[str]:
    updated_files: list[str] = []
    backend_file = repo_b_path / "apps" / "api" / "src" / "domain" / "agent_registry" / "service.py"
    if not backend_file.exists():
        return updated_files

    content = backend_file.read_text(encoding="utf-8")
    marker = 'Position(symbol="000001.SZ", qty=300, avg_cost=12.45),'
    if marker not in content:
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
