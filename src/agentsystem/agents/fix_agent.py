from __future__ import annotations

from agentsystem.core.state import DevState


def fix_node(state: DevState) -> DevState:
    print("[Fix Agent] Attempting automatic remediation")

    attempts = state.get("fix_attempts", 0) + 1
    state["fix_attempts"] = attempts
    state["fix_result"] = "No automatic fix available in demo mode."
    state["error_message"] = None
    state["current_step"] = "fix_done"

    print(f"[Fix Agent] Fix attempt {attempts} recorded")
    return state
