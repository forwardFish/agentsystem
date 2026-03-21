from __future__ import annotations

from datetime import datetime
from pathlib import Path

from langgraph.graph import END, StateGraph

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import DevState, build_mode_coverage
from agentsystem.dashboard.hooks import send_log, send_node_end, send_node_start, send_workflow_state
from agentsystem.orchestration.runtime_memory import collect_mode_artifact_paths, write_node_checkpoint
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
        manual_mode = str(self.task.get("skill_mode") or "").strip() or None
        initial_state: DevState = {
            "task_id": self.task_id,
            "user_requirement": str(self.task.get("goal", "")),
            "repo_b_path": str(self.worktree_path),
            "task_payload": self.task,
            "auto_run": self.task.get("auto_run"),
            "run_policy": self.task.get("run_policy"),
            "execution_policy": self.task.get("execution_policy"),
            "interaction_policy": self.task.get("interaction_policy"),
            "pause_policy": self.task.get("pause_policy"),
            "acceptance_policy": self.task.get("acceptance_policy"),
            "retry_policy": self.task.get("retry_policy"),
            "acceptance_attempt": self.task.get("acceptance_attempt") or 0,
            "acceptance_failure_class": self.task.get("acceptance_failure_class"),
            "repair_iteration": self.task.get("repair_iteration") or 0,
            "final_green_required": self.task.get("final_green_required"),
            "blocker_class": self.task.get("blocker_class"),
            "story_kind": self.task.get("story_kind"),
            "risk_level": self.task.get("risk_level"),
            "has_browser_surface": self.task.get("has_browser_surface"),
            "requires_auth": self.task.get("requires_auth"),
            "qa_strategy": self.task.get("qa_strategy"),
            "session_policy": self.task.get("session_policy"),
            "cookie_source": self.task.get("cookie_source"),
            "auth_expectations": list(self.task.get("auth_expectations") or []),
            "investigation_context": list(self.task.get("investigation_context") or []),
            "bug_scope": self.task.get("bug_scope"),
            "release_scope": list(self.task.get("release_scope") or []),
            "doc_targets": list(self.task.get("doc_targets") or []),
            "retro_window": self.task.get("retro_window"),
            "workflow_enforcement_policy": self.task.get("workflow_enforcement_policy"),
            "upstream_agent_parity": self.task.get("upstream_agent_parity"),
            "required_modes": list(self.task.get("required_modes") or []),
            "advisory_modes": list(self.task.get("advisory_modes") or []),
            "next_recommended_actions": list(self.task.get("next_recommended_actions") or []),
            "executed_modes": [manual_mode] if manual_mode else [],
            "effective_qa_mode": self.task.get("effective_qa_mode"),
            "auto_upgrade_to_qa": self.task.get("auto_upgrade_to_qa"),
            "needs_design_review": self.task.get("needs_design_review"),
            "needs_qa_design_review": self.task.get("needs_qa_design_review"),
            "needs_design_consultation": self.task.get("needs_design_consultation"),
            "needs_ceo_review_advice": self.task.get("needs_ceo_review_advice"),
            "agent_activation_plan": self.task.get("agent_activation_plan"),
            "agent_mode_coverage": None,
            "skill_mode": self.task.get("skill_mode"),
            "skill_mode_name": self.task.get("skill_mode_name"),
            "skill_mode_description": self.task.get("skill_mode_description"),
            "skill_mode_manifest_path": self.task.get("skill_mode_manifest_path"),
            "skill_entry_mode": self.task.get("skill_entry_mode"),
            "stop_after": self.task.get("stop_after"),
            "fixer_allowed": self.task.get("fixer_allowed", True),
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
            "office_hours_success": None,
            "office_hours_dir": None,
            "office_hours_report": None,
            "office_hours_summary": None,
            "office_hours_questions": None,
            "requirement_spec": None,
            "parsed_goal": None,
            "plan_ceo_review_success": None,
            "plan_ceo_review_dir": None,
            "plan_ceo_review_report": None,
            "plan_ceo_requirement_doc": None,
            "plan_ceo_opportunity_map": None,
            "architecture_review_success": None,
            "architecture_review_dir": None,
            "architecture_review_report": None,
            "architecture_review_summary": None,
            "architecture_test_plan": None,
            "investigate_success": None,
            "investigate_dir": None,
            "investigation_report": None,
            "investigation_summary": None,
            "investigation_root_cause": None,
            "investigation_recommendation": None,
            "plan_design_review_success": None,
            "plan_design_review_dir": None,
            "plan_design_review_report": None,
            "plan_design_route_contract": None,
            "plan_design_risks": None,
            "design_consultation_success": None,
            "design_consultation_dir": None,
            "design_consultation_report": None,
            "design_consultation_rounds": None,
            "design_decisions": None,
            "design_contract_path": None,
            "design_preview_path": None,
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
            "browse_success": None,
            "browse_dir": None,
            "browse_report": None,
            "setup_browser_cookies_success": None,
            "setup_browser_cookies_dir": None,
            "cookie_import_plan_path": None,
            "browser_storage_state_path": None,
            "browse_observations": None,
            "reference_observations": None,
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
            "runtime_qa_success": None,
            "runtime_qa_passed": None,
            "runtime_qa_report": None,
            "runtime_qa_dir": None,
            "runtime_qa_findings": None,
            "runtime_qa_warnings": None,
            "runtime_qa_report_only": bool(self.task.get("runtime_qa_report_only")),
            "qa_input_sources": None,
            "qa_design_review_success": None,
            "qa_design_review_passed": None,
            "qa_design_review_report": None,
            "qa_design_review_dir": None,
            "plan_design_scorecard": None,
            "plan_design_assumptions": None,
            "design_review_scores": None,
            "design_review_route_scores": None,
            "design_review_findings": None,
            "design_review_visual_checklist": None,
            "design_review_visual_verdict": None,
            "design_review_passed": None,
            "design_review_report": None,
            "before_screenshot_paths": None,
            "after_screenshot_paths": None,
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
            "ship_success": None,
            "ship_dir": None,
            "ship_report": None,
            "ship_release_package": None,
            "ship_coverage_audit_path": None,
            "ship_release_version_path": None,
            "ship_changelog_draft_path": None,
            "ship_pr_draft_path": None,
            "document_release_success": None,
            "document_release_dir": None,
            "document_release_report": None,
            "document_release_targets": None,
            "document_release_applied_changes": None,
            "document_release_skipped_targets": None,
            "retro_success": None,
            "retro_dir": None,
            "retro_report": None,
            "retro_previous_snapshot_path": None,
            "retro_trend_analysis_path": None,
            "retro_git_activity_summary_path": None,
            "fix_result": None,
            "fix_attempts": 0,
            "fix_fingerprint_history": [],
            "fix_return_to": None,
            "failure_type": None,
            "interruption_reason": None,
            "last_node": None,
            "review_issue_signature": None,
            "review_issue_history": [],
            "mode_execution_order": [],
            "mode_artifact_paths": {},
            "failure_snapshot_path": None,
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
        _dedupe_state_lists(final_state)
        final_state["mode_artifact_paths"] = collect_mode_artifact_paths(final_state)
        final_state["agent_mode_coverage"] = build_mode_coverage(
            final_state.get("required_modes"),
            final_state.get("advisory_modes"),
            final_state.get("executed_modes"),
        )
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
            if stop_after == "browser_qa" and current_step == "runtime_qa_done":
                return True
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
        send_log(task_id, "INFO", f"Starting {node_name} node")
        send_workflow_state(task_id, node_name, node_input)

        checkpoint_repo_path = Path(
            str((state.get("task_payload") or {}).get("project_repo_root") or state.get("repo_b_path") or "")
        ).resolve()
        if checkpoint_repo_path.exists():
            write_node_checkpoint(
                checkpoint_repo_path,
                project=str((state.get("task_payload") or {}).get("project") or checkpoint_repo_path.name),
                task_payload=state.get("task_payload"),
                task_id=task_id,
                node_name=node_name,
                phase="start",
                current_step=str(state.get("current_step") or ""),
                branch_name=str(state.get("branch_name") or ""),
                fix_attempts=int(state.get("fix_attempts") or 0),
                error_message=str(state.get("error_message") or "") or None,
                extra={"last_node": node_name},
            )

        try:
            result = node_func(state)
            result["last_node"] = node_name
            node_output = _compact_payload(result)
            status = "failed" if result.get("error_message") else "success"
            send_node_end(task_id, node_name, node_output, status)
            send_log(task_id, "INFO" if status == "success" else "ERROR", f"{node_name} node completed")
            send_workflow_state(task_id, node_name, node_output)
            if checkpoint_repo_path.exists():
                write_node_checkpoint(
                    checkpoint_repo_path,
                    project=str((result.get("task_payload") or {}).get("project") or (state.get("task_payload") or {}).get("project") or checkpoint_repo_path.name),
                    task_payload=result.get("task_payload") or state.get("task_payload"),
                    task_id=task_id,
                    node_name=node_name,
                    phase="end",
                    current_step=str(result.get("current_step") or ""),
                    branch_name=str(result.get("branch_name") or state.get("branch_name") or ""),
                    fix_attempts=int(result.get("fix_attempts") or 0),
                    error_message=str(result.get("error_message") or "") or None,
                    extra={"last_node": node_name},
                )
            return result
        except Exception as exc:
            send_log(task_id, "ERROR", f"{node_name} node failed: {exc}")
            send_node_end(task_id, node_name, {"error": str(exc)}, "failed")
            if checkpoint_repo_path.exists():
                write_node_checkpoint(
                    checkpoint_repo_path,
                    project=str((state.get("task_payload") or {}).get("project") or checkpoint_repo_path.name),
                    task_payload=state.get("task_payload"),
                    task_id=task_id,
                    node_name=node_name,
                    phase="exception",
                    current_step=str(state.get("current_step") or ""),
                    branch_name=str(state.get("branch_name") or ""),
                    fix_attempts=int(state.get("fix_attempts") or 0),
                    error_message=str(exc),
                    extra={
                        "status": "interrupted",
                        "interruption_reason": "workflow_node_exception",
                        "last_node": node_name,
                    },
                )
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


def _dedupe_state_lists(state: DevState) -> None:
    for key in ("required_modes", "executed_modes", "advisory_modes", "next_recommended_actions"):
        values = state.get(key)
        if not isinstance(values, list):
            continue
        deduped: list[object] = []
        seen: set[str] = set()
        for item in values:
            marker = str(item)
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        state[key] = deduped
