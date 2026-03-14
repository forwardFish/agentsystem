from __future__ import annotations

from pathlib import Path
from datetime import datetime

from langgraph.graph import END, StateGraph

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.dashboard.hooks import send_log, send_node_end, send_node_start, send_workflow_state
from agentsystem.agents.backend_dev_agent import backend_dev_node
from agentsystem.agents.acceptance_gate_agent import acceptance_gate_node, route_after_acceptance
from agentsystem.agents.code_acceptance_agent import code_acceptance_node, route_after_code_acceptance
from agentsystem.agents.code_style_reviewer_agent import code_style_review_node, route_after_code_style_review
from agentsystem.agents.database_agent import database_dev_node
from agentsystem.agents.devops_agent import devops_dev_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node, route_after_fix
from agentsystem.agents.frontend_dev_agent import frontend_dev_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.router_agent import route_after_test, task_router
from agentsystem.agents.review_agent import review_node, route_after_review
from agentsystem.agents.security_agent import security_node
from agentsystem.agents.sync_agent import sync_merge_node
from agentsystem.agents.test_agent import test_node
from agentsystem.agents.workspace_prep_agent import workspace_prep_node
from agentsystem.core.state import DevState


class DevWorkflow:
    def __init__(self, config: dict, worktree_path: str, task: dict, task_id: str | None = None):
        self.config = config
        self.worktree_path = worktree_path
        self.task = task
        self.task_id = task_id or Path(worktree_path).name
        self.graph = create_dev_graph()

    def run(self) -> dict:
        initial_state: DevState = {
            "task_id": self.task_id,
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
            "review_success": None,
            "review_passed": None,
            "review_dir": None,
            "blocking_issues": None,
            "important_issues": None,
            "nice_to_haves": None,
            "review_report": None,
            "code_style_review_success": None,
            "code_style_review_passed": None,
            "code_style_review_report": None,
            "code_style_review_dir": None,
            "code_style_review_issues": None,
            "code_acceptance_success": None,
            "code_acceptance_passed": None,
            "code_acceptance_report": None,
            "code_acceptance_dir": None,
            "code_acceptance_issues": None,
            "acceptance_success": None,
            "acceptance_passed": None,
            "acceptance_report": None,
            "acceptance_dir": None,
            "doc_result": None,
            "delivery_dir": None,
            "fix_result": None,
            "fix_attempts": 0,
            "fix_return_to": None,
            "error_message": None,
            "shared_blackboard": {},
            "handoff_packets": [],
            "issues_to_fix": [],
            "resolved_issues": [],
            "agent_messages": [],
            "all_deliverables": [],
            "collaboration_trace_id": f"trace_{self.task_id}",
            "collaboration_started_at": datetime.now().isoformat(timespec="seconds"),
            "collaboration_ended_at": None,
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
    workflow.add_node("requirement_analysis", _instrument_node("Requirement", requirement_analysis_node))
    workflow.add_node("workspace_prep", _instrument_node("Workspace Prep", workspace_prep_node))
    workflow.add_node("backend_dev", _instrument_node("Backend Dev", backend_dev_node))
    workflow.add_node("frontend_dev", _instrument_node("Frontend Dev", frontend_dev_node))
    workflow.add_node("database_dev", _instrument_node("Database Dev", database_dev_node))
    workflow.add_node("devops_dev", _instrument_node("DevOps Dev", devops_dev_node))
    workflow.add_node("sync_merge", _instrument_node("Sync Merge", sync_merge_node))
    workflow.add_node("code_style_reviewer", _instrument_node("Code Style Reviewer", code_style_review_node))
    workflow.add_node("tester", _instrument_node("Tester", test_node))
    workflow.add_node("fixer", _instrument_node("Fixer", fix_node))
    workflow.add_node("security_scanner", _instrument_node("Security Scanner", security_node))
    workflow.add_node("reviewer", _instrument_node("Reviewer", review_node))
    workflow.add_node("code_acceptance", _instrument_node("Code Acceptance", code_acceptance_node))
    workflow.add_node("acceptance_gate", _instrument_node("Acceptance Gate", acceptance_gate_node))
    workflow.add_node("doc_writer", _instrument_node("Doc Writer", doc_node))
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
    workflow.add_edge("sync_merge", "code_style_reviewer")
    workflow.add_conditional_edges(
        "code_style_reviewer",
        route_after_code_style_review,
        {
            "tester": "tester",
            "fixer": "fixer",
        },
    )
    workflow.add_conditional_edges(
        "tester",
        route_after_test,
        {
            "fixer": "fixer",
            "security_scanner": "security_scanner",
        },
    )
    workflow.add_conditional_edges(
        "fixer",
        route_after_fix,
        {
            "code_style_reviewer": "code_style_reviewer",
            "tester": "tester",
            "reviewer": "reviewer",
            "code_acceptance": "code_acceptance",
            "acceptance_gate": "acceptance_gate",
        },
    )
    workflow.add_edge("security_scanner", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "code_acceptance": "code_acceptance",
            "fixer": "fixer",
        },
    )
    workflow.add_conditional_edges(
        "code_acceptance",
        route_after_code_acceptance,
        {
            "acceptance_gate": "acceptance_gate",
            "fixer": "fixer",
        },
    )
    workflow.add_conditional_edges(
        "acceptance_gate",
        route_after_acceptance,
        {
            "doc_writer": "doc_writer",
            "fixer": "fixer",
        },
    )
    workflow.add_edge("doc_writer", END)
    return workflow.compile()


def _instrument_node(node_name: str, node_func):
    def wrapped(state: DevState):
        task_id = str(state.get("task_id") or Path(str(state.get("repo_b_path", "workspace"))).name)
        node_input = _compact_payload(state)
        send_node_start(task_id, node_name, node_input)
        send_log(task_id, "INFO", f"开始执行 {node_name} 节点")
        send_workflow_state(task_id, node_name, node_input)
        try:
            result = node_func(state)
            node_output = _compact_payload(result)
            status = "failed" if result.get("error_message") else "success"
            send_node_end(task_id, node_name, node_output, status)
            send_log(task_id, "INFO" if status == "success" else "ERROR", f"{node_name} 节点执行完成")
            send_workflow_state(task_id, node_name, node_output)
            return result
        except Exception as exc:
            send_log(task_id, "ERROR", f"{node_name} 节点执行失败: {exc}")
            send_node_end(task_id, node_name, {"error": str(exc)}, "failed")
            raise

    return wrapped


def _compact_payload(state: DevState) -> dict[str, object]:
    subtasks = state.get("subtasks") or []
    payload = {
        "task_id": state.get("task_id"),
        "current_step": state.get("current_step"),
        "branch_name": state.get("branch_name"),
        "repo_b_path": state.get("repo_b_path"),
        "subtask_count": len(subtasks),
        "fix_attempts": state.get("fix_attempts"),
        "test_passed": state.get("test_passed"),
        "review_passed": state.get("review_passed"),
        "acceptance_passed": state.get("acceptance_passed"),
        "error_message": state.get("error_message"),
    }
    return {key: value for key, value in payload.items() if value is not None}
