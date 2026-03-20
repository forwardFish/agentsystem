from __future__ import annotations

from agentsystem.core.state import DevState, add_executed_mode


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
    qa_target = "browser_qa" if str(state.get("qa_strategy") or "browser") == "browser" else "runtime_qa"
    report_only = bool(state.get("browser_qa_report_only")) if qa_target == "browser_qa" else bool(state.get("runtime_qa_report_only"))
    if state.get("error_message") or state.get("test_passed") is False:
        if (
            (state.get("fixer_allowed", True) or state.get("auto_upgrade_to_qa"))
            and state.get("fix_attempts", 0) < 2
        ):
            state["fixer_allowed"] = True
            state["effective_qa_mode"] = "qa"
            if qa_target == "browser_qa":
                state["browser_qa_report_only"] = False
                state["browser_qa_mode"] = "quick"
            else:
                state["runtime_qa_report_only"] = False
            add_executed_mode(state, "qa")
            return "fixer"
        if report_only:
            return qa_target
        if str(state.get("stop_after") or "").strip() == "tester":
            return "__end__"
    if str(state.get("stop_after") or "").strip() == "tester":
        return "__end__"
    return qa_target
