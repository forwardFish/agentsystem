from __future__ import annotations

from pathlib import Path

from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.agents.contract_artifacts import materialize_core_db_schema_artifacts
from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet
import uuid

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

    task_payload = state.get("task_payload") or {}
    story_id = str(task_payload.get("story_id", "")).strip()
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    if story_id == "S0-005":
        updated_files = materialize_core_db_schema_artifacts(repo_b_path, related_files)
        add_handoff_packet(
            state,
            HandoffPacket(
                packet_id=str(uuid.uuid4()),
                from_agent=AgentRole.BUILDER,
                to_agent=AgentRole.SYNC,
                status=HandoffStatus.COMPLETED,
                what_i_did="Implemented the database portion of the story and generated the requested core schema SQL artifact.",
                what_i_produced=[
                    Deliverable(
                        deliverable_id=str(uuid.uuid4()),
                        name=Path(file_path).name,
                        type="code",
                        path=str(file_path),
                        description="Database artifact produced by the builder step.",
                        created_by=AgentRole.BUILDER,
                    )
                    for file_path in updated_files
                ],
                what_risks_i_found=[],
                what_i_require_next="Consolidate the changed files, prepare PR materials, and move the story into validation.",
                trace_id=str(state.get("collaboration_trace_id") or ""),
            ),
        )
        return {
            "database_result": "Core database schema artifacts prepared.",
            "dev_results": {
                "database": {
                    "updated_files": updated_files,
                    "summary": "Prepared Sprint 0 core database schema SQL.",
                }
            },
            "handoff_packets": state.get("handoff_packets"),
            "all_deliverables": state.get("all_deliverables"),
        }

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
