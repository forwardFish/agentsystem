from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Annotated, TypedDict
from unittest.mock import patch

from langgraph.graph import END, StateGraph

from agentsystem.core.state import merge_last_non_empty
from agentsystem.graph.dev_workflow import _dedupe_state_lists, _instrument_node


class DevWorkflowTestCase(unittest.TestCase):
    def test_dedupe_state_lists_keeps_first_seen_order(self) -> None:
        state = {
            "required_modes": ["plan-eng-review", "review", "plan-eng-review"],
            "executed_modes": ["plan-eng-review", "qa", "plan-eng-review", "review", "qa"],
            "advisory_modes": ["ship", "ship"],
            "next_recommended_actions": ["Run ship later", "Run ship later"],
        }

        _dedupe_state_lists(state)

        self.assertEqual(state["required_modes"], ["plan-eng-review", "review"])
        self.assertEqual(state["executed_modes"], ["plan-eng-review", "qa", "review"])
        self.assertEqual(state["advisory_modes"], ["ship"])
        self.assertEqual(state["next_recommended_actions"], ["Run ship later"])

    def test_parallel_last_node_updates_use_merge_safe_reducer(self) -> None:
        class ParallelState(TypedDict, total=False):
            last_node: Annotated[str | None, merge_last_non_empty]

        workflow = StateGraph(ParallelState)
        workflow.add_node("fanout", lambda _state: {})
        workflow.add_node("backend_dev", lambda _state: {"last_node": "backend_dev"})
        workflow.add_node("database_dev", lambda _state: {"last_node": "database_dev"})
        workflow.set_entry_point("fanout")
        workflow.add_edge("fanout", "backend_dev")
        workflow.add_edge("fanout", "database_dev")
        workflow.add_edge("backend_dev", END)
        workflow.add_edge("database_dev", END)

        result = workflow.compile().invoke({})

        self.assertIn(result["last_node"], {"backend_dev", "database_dev"})

    def test_instrument_node_sets_last_node_in_result_without_mutating_input_state(self) -> None:
        observed_last_nodes: list[object] = []

        def node(state: dict[str, object]) -> dict[str, object]:
            observed_last_nodes.append(state.get("last_node"))
            return {"current_step": "backend_done"}

        wrapped = _instrument_node("backend_dev", node)
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp)
            state = {
                "task_id": "task-demo",
                "repo_b_path": str(repo_path),
                "task_payload": {},
                "current_step": "init",
            }
            with (
                patch("agentsystem.graph.dev_workflow.send_node_start"),
                patch("agentsystem.graph.dev_workflow.send_log"),
                patch("agentsystem.graph.dev_workflow.send_workflow_state"),
                patch("agentsystem.graph.dev_workflow.send_node_end"),
            ):
                result = wrapped(state)

        self.assertEqual(observed_last_nodes, [None])
        self.assertIsNone(state.get("last_node"))
        self.assertEqual(result["last_node"], "backend_dev")


if __name__ == "__main__":
    unittest.main()
