from __future__ import annotations

from pathlib import Path

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import DevState, SubTask


def sync_merge_node(state: DevState) -> DevState:
    print("[Sync Agent] Merging parallel results")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    git = GitAdapter(repo_b_path)
    dev_results = state.get("dev_results", {})

    changed_files: list[str] = []
    completed_types: set[str] = set()
    for agent_name, payload in dev_results.items():
        if isinstance(payload, dict):
            changed_files.extend(str(path) for path in payload.get("updated_files", []))
            completed_types.add(agent_name)

    state["generated_code_diff"] = "\n".join(dict.fromkeys(changed_files))
    state["subtasks"] = _mark_completed(state.get("subtasks", []), completed_types)

    if git.is_dirty():
        try:
            git.add_and_commit("feat: synchronize multi-agent development changes")
            print("[Sync Agent] Local commit created")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[Sync Agent] Commit skipped: {exc}")

    state["current_step"] = "sync_done"
    return state


def _mark_completed(subtasks: list[SubTask], completed_types: set[str]) -> list[SubTask]:
    updated_subtasks: list[SubTask] = []
    for subtask in subtasks:
        if subtask.type in completed_types:
            updated_subtasks.append(subtask.model_copy(update={"status": "completed"}))
        else:
            updated_subtasks.append(subtask)
    return updated_subtasks
