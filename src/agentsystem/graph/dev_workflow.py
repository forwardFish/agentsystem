from __future__ import annotations

from pathlib import Path
from datetime import datetime

from langgraph.graph import END, StateGraph

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.dashboard.hooks import send_log, send_node_end, send_node_start, send_workflow_state
from agentsystem.core.state import DevState
from agentsystem.orchestration.skill_mode_registry import resolve_runtime_task
from agentsystem.orchestration.workflow_registry import get_workflow_plugin


class DevWorkflow:
    def __init__(self, config: dict, worktree_path: str, task: dict, task_id: str | None = None):
        self.config = config
        self.worktree_path = worktree_path
        self.task, self.skill_mode_spec = resolve_runtime_task(task)
        self.task_id = task_id or Path(worktree_path).name
        self.workflow_plugin_id = str(self.task.get("workflow_plugin") or "software_engineering")
        self.workflow_plugin = get_workflow_plugin(self.workflow_plugin_id)
        self.entry_point_override = str(self.task.get("skill_entry_mode") or "").strip() or None
        self.graph = create_dev_graph(self.workflow_plugin_id, entry_point_override=self.entry_point_override)

    def run(self) -> dict:
        initial_state: DevState = {
            "task_id": self.task_id,
            "user_requirement": str(self.task.get("goal", "")),
            "repo_b_path": str(self.worktree_path),
            "task_payload": self.task,
            "skill_mode": self.task.get("skill_mode"),
            "skill_mode_name": self.task.get("skill_mode_name"),
            "skill_mode_description": self.task.get("skill_mode_description"),
            "skill_mode_manifest_path": self.task.get("skill_mode_manifest_path"),
            "skill_entry_mode": self.task.get("skill_entry_mode"),
            "stop_after": self.task.get("stop_after"),
            "fixer_allowed": self.task.get("fixer_allowed"),
            "workflow_plugin_id": self.workflow_plugin.plugin_id,
            "workflow_manifest_path": self.workflow_plugin.manifest_path,
            "workflow_policy_refs": list(self.workflow_plugin.policy_refs),
            "workflow_agent_manifest_ids": [node.agent_id for node in self.workflow_plugin.nodes],
            "workflow_agent_manifest_paths": [node.manifest_path for node in self.workflow_plugin.nodes],
            "branch_name": GitAdapter(self.worktree_path).get_current_branch(),
            "auto_commit": False,
            "current_step": "init",
            "subtasks": [],
            "dev_results": {},
            "backend_result": None,
            "frontend_result": None,
            "database_result": None,
            "devops_result": None,
            "requirement_spec": None,
            "parsed_goal": None,
            "architecture_review_success": None,
            "architecture_review_dir": None,
            "architecture_review_report": None,
            "architecture_review_summary": None,
            "architecture_test_plan": None,
            "acceptance_checklist": None,
            "story_inputs": None,
            "story_process": None,
            "story_outputs": None,
            "verification_basis": None,
            "primary_files": None,
            "secondary_files": None,
            "parsed_constraints": None,
            "parsed_not_do": None,
            "generated_code_diff": None,
            "test_results": None,
            "test_passed": None,
            "test_failure_info": None,
            "browser_runtime_dir": None,
            "browser_session_id": None,
            "browser_qa_success": None,
            "browser_qa_passed": None,
            "browser_qa_report": None,
            "browser_qa_dir": None,
            "browser_qa_findings": None,
            "browser_qa_warnings": None,
            "browser_qa_health_score": None,
            "browser_qa_ship_readiness": None,
            "browser_qa_mode": None,
            "browser_qa_report_only": bool(self.task.get("browser_qa_report_only")),
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
        success = self._is_successful_completion(final_state)
        return {
            "success": success,
            "error": normalized_state.get("error_message"),
            "state": normalized_state,
        }

    def _is_successful_completion(self, final_state: DevState) -> bool:
        if final_state.get("error_message"):
            return False
        current_step = str(final_state.get("current_step") or "").strip()
        stop_after = str(final_state.get("stop_after") or "").strip()
        if stop_after:
            return current_step == f"{stop_after}_done"
        return current_step == "doc_done"

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


def create_dev_graph(workflow_plugin_id: str = "software_engineering", entry_point_override: str | None = None):
    plugin = get_workflow_plugin(workflow_plugin_id)
    workflow = StateGraph(DevState)
    for node in plugin.node_specs():
        workflow.add_node(node.node_id, _instrument_node(node.display_name, node.handler))
    workflow.set_entry_point(entry_point_override or plugin.entry_point)
    for start, end in plugin.edges:
        workflow.add_edge(start, END if end == "__end__" else end)
    for conditional_edge in plugin.conditional_edges:
        workflow.add_conditional_edges(
            conditional_edge.source,
            conditional_edge.router,
            {key: END if value == "__end__" else value for key, value in conditional_edge.routes.items()},
        )
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
        "workflow_plugin_id": state.get("workflow_plugin_id"),
        "workflow_agent_count": len(state.get("workflow_agent_manifest_ids") or []),
        "subtask_count": len(subtasks),
        "fix_attempts": state.get("fix_attempts"),
        "test_passed": state.get("test_passed"),
        "browser_qa_passed": state.get("browser_qa_passed"),
        "browser_qa_health_score": state.get("browser_qa_health_score"),
        "review_passed": state.get("review_passed"),
        "acceptance_passed": state.get("acceptance_passed"),
        "error_message": state.get("error_message"),
    }
    return {key: value for key, value in payload.items() if value is not None}
