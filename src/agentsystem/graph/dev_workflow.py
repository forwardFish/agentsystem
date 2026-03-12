from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, StateGraph

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.agents.backend_dev_agent import backend_dev_node
from agentsystem.agents.database_agent import database_dev_node
from agentsystem.agents.devops_agent import devops_dev_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node
from agentsystem.agents.frontend_dev_agent import frontend_dev_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.router_agent import route_after_test, task_router
from agentsystem.agents.review_agent import review_node
from agentsystem.agents.security_agent import security_node
from agentsystem.agents.sync_agent import sync_merge_node
from agentsystem.agents.test_agent import test_node
from agentsystem.agents.workspace_prep_agent import workspace_prep_node
from agentsystem.core.state import DevState


class DevWorkflow:
    def __init__(self, config: dict, worktree_path: str, task: dict):
        self.config = config
        self.worktree_path = worktree_path
        self.task = task
        self.graph = create_dev_graph()

    def run(self) -> dict:
        initial_state: DevState = {
            "user_requirement": str(self.task.get("goal", "")),
            "repo_b_path": str(self.worktree_path),
            "task_payload": self.task,
            "branch_name": GitAdapter(self.worktree_path).get_current_branch(),
            "auto_commit": False,
            "current_step": "init",
            "subtasks": [],
            "dev_results": {},
            "backend_result": None,
            "frontend_result": None,
            "database_result": None,
            "devops_result": None,
            "generated_code_diff": None,
            "test_results": None,
            "security_report": None,
            "review_report": None,
            "doc_result": None,
            "fix_result": None,
            "fix_attempts": 0,
            "error_message": None,
        }
        final_state = self.graph.invoke(initial_state)
        normalized_state = self._normalize(final_state)
        success = final_state.get("current_step") == "doc_done" and not final_state.get("error_message")
        return {
            "success": success,
            "error": normalized_state.get("error_message"),
            "state": normalized_state,
        }

    def _normalize(self, value):
        if hasattr(value, "model_dump"):
            return self._normalize(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {key: self._normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._normalize(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        return value


def create_dev_graph():
    workflow = StateGraph(DevState)
    workflow.add_node("requirement_analysis", requirement_analysis_node)
    workflow.add_node("workspace_prep", workspace_prep_node)
    workflow.add_node("backend_dev", backend_dev_node)
    workflow.add_node("frontend_dev", frontend_dev_node)
    workflow.add_node("database_dev", database_dev_node)
    workflow.add_node("devops_dev", devops_dev_node)
    workflow.add_node("sync_merge", sync_merge_node)
    workflow.add_node("tester", test_node)
    workflow.add_node("fixer", fix_node)
    workflow.add_node("security_scanner", security_node)
    workflow.add_node("reviewer", review_node)
    workflow.add_node("doc_writer", doc_node)
    workflow.set_entry_point("requirement_analysis")
    workflow.add_edge("requirement_analysis", "workspace_prep")
    workflow.add_conditional_edges(
        "workspace_prep",
        task_router,
        {
            "backend_dev": "backend_dev",
            "frontend_dev": "frontend_dev",
            "database_dev": "database_dev",
            "devops_dev": "devops_dev",
            "sync_merge": "sync_merge",
        },
    )
    workflow.add_edge("backend_dev", "sync_merge")
    workflow.add_edge("frontend_dev", "sync_merge")
    workflow.add_edge("database_dev", "sync_merge")
    workflow.add_edge("devops_dev", "sync_merge")
    workflow.add_edge("sync_merge", "tester")
    workflow.add_conditional_edges(
        "tester",
        route_after_test,
        {
            "fixer": "fixer",
            "security_scanner": "security_scanner",
        },
    )
    workflow.add_edge("fixer", "tester")
    workflow.add_edge("security_scanner", "reviewer")
    workflow.add_edge("reviewer", "doc_writer")
    workflow.add_edge("doc_writer", END)
    return workflow.compile()
