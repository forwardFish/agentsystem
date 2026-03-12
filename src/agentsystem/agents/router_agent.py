from __future__ import annotations

from agentsystem.core.state import DevState


def task_router(state: DevState) -> list[str]:
    print("[Router] Dispatching subtasks")

    next_nodes: list[str] = []
    subtasks = state.get("subtasks", [])

    if any(task.type == "backend" for task in subtasks):
        next_nodes.append("backend_dev")
    if any(task.type == "frontend" for task in subtasks):
        next_nodes.append("frontend_dev")
    if any(task.type == "database" for task in subtasks):
        next_nodes.append("database_dev")
    if any(task.type == "devops" for task in subtasks):
        next_nodes.append("devops_dev")

    if not next_nodes:
        next_nodes.append("sync_merge")

    print(f"[Router] Next nodes: {next_nodes}")
    return next_nodes


def route_after_test(state: DevState) -> str:
    if state.get("error_message") and state.get("fix_attempts", 0) < 1:
        return "fixer"
    return "security_scanner"
