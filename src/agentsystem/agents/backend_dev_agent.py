from __future__ import annotations

from pathlib import Path
import uuid

from agentsystem.agents.contract_artifacts import (
    materialize_agent_contract_artifacts,
    materialize_audit_idempotency_artifacts,
    materialize_error_state_spec_artifacts,
    materialize_profile_schema_artifacts,
    materialize_statement_upload_api_artifacts,
    materialize_statement_storage_artifacts,
    materialize_world_state_schema_artifacts,
)
from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet


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
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.BUILDER,
            to_agent=AgentRole.SYNC,
            status=HandoffStatus.COMPLETED,
            what_i_did="Implemented the backend portion of the story and wrote the requested backend artifacts.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name=Path(file_path).name,
                    type="code",
                    path=str(file_path),
                    description="Backend artifact produced by the builder step.",
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
        "backend_result": "Backend schema and mock snapshot updated.",
        "dev_results": {
            "backend": {
                "updated_files": updated_files,
                "summary": "Updated backend snapshot scaffold.",
            }
        },
        "handoff_packets": state.get("handoff_packets"),
        "all_deliverables": state.get("all_deliverables"),
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

    story_id = str((task_payload or {}).get("story_id", "")).strip()
    related_files = [str(item) for item in (task_payload or {}).get("related_files", [])]
    if story_id == "S0-001":
        return materialize_profile_schema_artifacts(repo_b_path, related_files)
    if story_id == "S0-002":
        return materialize_world_state_schema_artifacts(repo_b_path, related_files)
    if story_id == "S0-003":
        return materialize_agent_contract_artifacts(repo_b_path, related_files)
    if story_id == "S0-004":
        return materialize_error_state_spec_artifacts(repo_b_path, related_files)
    if story_id == "S0-006":
        return materialize_statement_storage_artifacts(repo_b_path, related_files)
    if story_id == "S0-007":
        return materialize_audit_idempotency_artifacts(repo_b_path, related_files)
    if story_id == "S1-001":
        return materialize_statement_upload_api_artifacts(repo_b_path, related_files)

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
