from __future__ import annotations

from pathlib import Path

from agentsystem.core.state import DevState

DATABASE_MARKER = "# Database Agent scaffold"


def database_dev_node(state: DevState) -> dict[str, object]:
    print("[Database Agent] Starting database work")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    updated_files: list[str] = []
    tables_file = repo_b_path / "apps" / "api" / "src" / "infra" / "db" / "tables.py"
    tables_file.parent.mkdir(parents=True, exist_ok=True)

    if not tables_file.exists():
        tables_file.write_text(
            "from __future__ import annotations\n\n"
            f"{DATABASE_MARKER}\n"
            "AGENT_TABLES = ['agents', 'trade_logs']\n",
            encoding="utf-8",
        )
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
