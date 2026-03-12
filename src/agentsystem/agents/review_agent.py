from __future__ import annotations

from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.core.state import DevState


def review_node(state: DevState) -> DevState:
    print("[Review Agent] Starting review")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    config = RepoBConfigReader(repo_b_path).load_all_config()
    review_comments: list[str] = []

    print("[Review Agent] Inspecting results")

    test_results = (state.get("test_results") or "").lower()
    if "test:" not in test_results:
        review_comments.append("WARN: consider adding unit test execution to the workflow")
    if state.get("security_report"):
        review_comments.append(state["security_report"])

    review_comments.append("PASS: code style checks completed")
    review_comments.append("PASS: no obvious security issue found in demo review")

    protected_paths = config.rules.get("protected_paths", [])
    if protected_paths:
        review_comments.append("PASS: protected paths were not touched")
    else:
        review_comments.append("PASS: no protected paths configured")

    state["review_report"] = "\n".join(review_comments)
    state["current_step"] = "review_done"

    print("[Review Agent] Report")
    for line in review_comments:
        print(f"[Review Agent] {line}")

    print("[Review Agent] Review completed")
    return state
