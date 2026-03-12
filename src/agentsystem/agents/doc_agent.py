from __future__ import annotations

from agentsystem.core.state import DevState


def doc_node(state: DevState) -> DevState:
    print("[Doc Agent] Preparing delivery notes")

    lines = [
        "Documented workflow outcome.",
        f"Requirement: {state.get('requirement_spec') or 'n/a'}",
        f"Tests: {state.get('test_results') or 'n/a'}",
        f"Review: {state.get('review_report') or 'n/a'}",
    ]
    state["doc_result"] = "\n".join(lines)
    state["current_step"] = "doc_done"
    print("[Doc Agent] Delivery notes prepared")
    return state
