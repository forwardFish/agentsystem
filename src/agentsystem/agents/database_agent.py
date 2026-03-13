from __future__ import annotations

from pathlib import Path

from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.core.state import DevState

DATABASE_MARKER = "# Database Agent scaffold"


def database_dev_node(state: DevState) -> dict[str, object]:
    print("[Database Agent] Starting database work")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    updated_files: list[str] = []
    database_tasks = [task for task in state.get("subtasks", []) if task.type == "database"]
    candidate_files: list[Path] = []
    for task in database_tasks:
        for file_path in getattr(task, "files_to_modify", []):
            candidate = repo_b_path / str(file_path)
            if candidate not in candidate_files:
                candidate_files.append(candidate)
    if not candidate_files:
        candidate_files.append(repo_b_path / "apps" / "api" / "src" / "infra" / "db" / "tables.py")

    for tables_file in candidate_files:
        tables_file.parent.mkdir(parents=True, exist_ok=True)
        if not tables_file.exists():
            tables_file.write_text(
                "from __future__ import annotations\n\n"
                f"{DATABASE_MARKER}\n"
                "AGENT_TABLES = ['agents', 'trade_logs']\n",
                encoding="utf-8",
            )
            updated_files.append(str(tables_file))
            continue
        content = tables_file.read_text(encoding="utf-8")
        rewritten = llm_rewrite_file(repo_b_path, state.get("task_payload"), tables_file, system_role="Database Builder Agent")
        if rewritten and rewritten != content:
            tables_file.write_text(rewritten, encoding="utf-8")
            updated_files.append(str(tables_file))

    return {
        "database_result": "Database schema scaffold prepared.",
        "dev_results": {
            "database": {
                "updated_files": updated_files,
                "summary": "Prepared database scaffold files.",
            }
        },
    }
