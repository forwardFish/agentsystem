from __future__ import annotations

from pathlib import Path

from agentsystem.agents.browser_qa_agent import browser_qa_node
from agentsystem.core.state import DevState, add_executed_mode


def browse_node(state: DevState) -> DevState:
    task_payload = dict(state.get("task_payload") or {})
    original_mode = task_payload.get("skill_mode")

    task_payload["skill_mode"] = "browse"
    state["task_payload"] = task_payload
    state["browser_qa_report_only"] = True
    state["browser_qa_mode"] = "report_only"
    state["fixer_allowed"] = False

    updated = browser_qa_node(state)
    if original_mode:
        task_payload["skill_mode"] = original_mode
    else:
        task_payload.pop("skill_mode", None)
    updated["task_payload"] = task_payload
    updated["browse_success"] = True
    updated["browse_dir"] = updated.get("browser_qa_dir")
    updated["browse_report"] = updated.get("browser_qa_report")
    updated["current_step"] = "browse_done"
    updated["error_message"] = None
    add_executed_mode(updated, "browse")
    return updated


def route_after_browse(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "browse":
        return "__end__"
    if state.get("needs_design_review") or state.get("needs_design_consultation"):
        return "plan_design_review"
    return "workspace_prep"
