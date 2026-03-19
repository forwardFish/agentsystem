from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


def merge_lists(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return [*(left or []), *(right or [])]


def merge_last_non_empty(left: Any, right: Any) -> Any:
    if right not in (None, ""):
        return right
    return left


class SubTask(BaseModel):
    id: str
    type: str
    description: str
    files_to_modify: list[str] = Field(default_factory=list)
    status: str = "pending"


class AgentRole(str, Enum):
    REQUIREMENT = "Requirement"
    ARCHITECTURE_REVIEW = "ArchitectureReview"
    PLAN_DESIGN_REVIEW = "PlanDesignReview"
    DESIGN_CONSULTATION = "DesignConsultation"
    BUILDER = "Builder"
    SYNC = "Sync"
    TESTER = "Tester"
    BROWSER_QA = "BrowserQA"
    RUNTIME_QA = "RuntimeQA"
    QA_DESIGN_REVIEW = "QADesignReview"
    SECURITY_SCANNER = "SecurityScanner"
    FIXER = "Fixer"
    REVIEWER = "Reviewer"
    CODE_STYLE_REVIEWER = "CodeStyleReviewer"
    CODE_ACCEPTANCE = "CodeAcceptance"
    ACCEPTANCE_GATE = "AcceptanceGate"
    DOC_WRITER = "DocWriter"


class HandoffStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class IssueSeverity(str, Enum):
    BLOCKING = "blocking"
    IMPORTANT = "important"
    NICE_TO_HAVE = "nice_to_have"


class Issue(BaseModel):
    issue_id: str
    severity: IssueSeverity
    source_agent: AgentRole
    target_agent: AgentRole
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    suggestion: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    resolved_at: str | None = None
    resolved: bool = False


class Deliverable(BaseModel):
    deliverable_id: str
    name: str
    type: str
    path: str
    description: str
    created_by: AgentRole
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    version: str = "1.0"


class HandoffPacket(BaseModel):
    packet_id: str
    from_agent: AgentRole
    to_agent: AgentRole
    status: HandoffStatus = HandoffStatus.PENDING
    what_i_did: str
    what_i_produced: list[Deliverable] = Field(default_factory=list)
    what_risks_i_found: list[str] = Field(default_factory=list)
    what_i_require_next: str
    issues: list[Issue] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    trace_id: str


class AgentMessage(BaseModel):
    message_id: str
    from_agent: AgentRole
    to_agent: AgentRole | None = None
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def add_handoff_packet(state: "DevState", packet: HandoffPacket) -> None:
    handoff_packets = list(state.get("handoff_packets") or [])
    handoff_packets.append(packet.model_dump(mode="json"))
    state["handoff_packets"] = handoff_packets

    all_deliverables = list(state.get("all_deliverables") or [])
    all_deliverables.extend(deliverable.model_dump(mode="json") for deliverable in packet.what_i_produced)
    state["all_deliverables"] = all_deliverables


def add_issue(state: "DevState", issue: Issue) -> None:
    issues = list(state.get("issues_to_fix") or [])
    issues.append(issue.model_dump(mode="json"))
    state["issues_to_fix"] = issues


def add_executed_mode(state: "DevState", mode_id: str) -> None:
    mode = str(mode_id).strip()
    if not mode:
        return
    executed = list(state.get("executed_modes") or [])
    if mode not in executed:
        executed.append(mode)
    state["executed_modes"] = executed
    execution_order = list(state.get("mode_execution_order") or [])
    execution_order.append(mode)
    state["mode_execution_order"] = execution_order


def build_mode_coverage(
    required_modes: list[str] | None,
    advisory_modes: list[str] | None,
    executed_modes: list[str] | None,
) -> dict[str, Any]:
    required = [str(item).strip() for item in (required_modes or []) if str(item).strip()]
    advisory = [str(item).strip() for item in (advisory_modes or []) if str(item).strip()]
    executed = [str(item).strip() for item in (executed_modes or []) if str(item).strip()]
    executed_set = set(executed)
    missing_required = [mode for mode in required if mode not in executed_set]
    advisory_executed = [mode for mode in advisory if mode in executed_set]
    return {
        "required": required,
        "executed": executed,
        "advisory": advisory,
        "missing_required": missing_required,
        "executed_required_count": sum(1 for mode in required if mode in executed_set),
        "required_count": len(required),
        "advisory_executed": advisory_executed,
        "advisory_executed_count": len(advisory_executed),
        "all_required_executed": not missing_required,
    }


def resolve_issue(state: "DevState", issue_id: str) -> None:
    remaining: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = list(state.get("resolved_issues") or [])
    for issue in list(state.get("issues_to_fix") or []):
        if issue.get("issue_id") == issue_id:
            issue["resolved"] = True
            issue["resolved_at"] = datetime.now().isoformat(timespec="seconds")
            resolved.append(issue)
        else:
            remaining.append(issue)
    state["issues_to_fix"] = remaining
    state["resolved_issues"] = resolved


class DevState(TypedDict, total=False):
    task_id: str
    user_requirement: str
    repo_b_path: str
    task_payload: dict[str, Any] | None
    story_kind: str | None
    risk_level: str | None
    has_browser_surface: bool | None
    requires_auth: bool | None
    qa_strategy: str | None
    required_modes: list[str] | None
    advisory_modes: list[str] | None
    next_recommended_actions: list[str] | None
    executed_modes: Annotated[list[str] | None, merge_lists]
    effective_qa_mode: str | None
    auto_upgrade_to_qa: bool | None
    needs_design_review: bool | None
    needs_qa_design_review: bool | None
    needs_design_consultation: bool | None
    needs_ceo_review_advice: bool | None
    agent_activation_plan: dict[str, Any] | None
    agent_mode_coverage: dict[str, Any] | None
    skill_mode: str | None
    skill_mode_name: str | None
    skill_mode_description: str | None
    skill_mode_manifest_path: str | None
    skill_entry_mode: str | None
    stop_after: str | None
    fixer_allowed: bool | None
    workflow_plugin_id: str | None
    workflow_manifest_path: str | None
    workflow_policy_refs: list[str] | None
    workflow_agent_manifest_ids: list[str] | None
    workflow_agent_manifest_paths: list[str] | None
    branch_name: str | None
    auto_commit: bool | None
    sync_merge_success: bool | None
    staged_files: list[str] | None
    message: str | None
    pr_prep_success: bool | None
    pr_prep_dir: str | None
    pr_desc: str | None
    commit_msg: str | None
    requirement_spec: str | None
    parsed_goal: str | None
    architecture_review_success: bool | None
    architecture_review_dir: str | None
    architecture_review_report: str | None
    architecture_review_summary: str | None
    architecture_test_plan: dict[str, Any] | None
    plan_design_review_success: bool | None
    plan_design_review_dir: str | None
    plan_design_review_report: str | None
    design_consultation_success: bool | None
    design_consultation_dir: str | None
    design_consultation_report: str | None
    design_contract_path: str | None
    design_preview_path: str | None
    runtime_qa_success: bool | None
    runtime_qa_passed: bool | None
    runtime_qa_report: str | None
    runtime_qa_dir: str | None
    runtime_qa_findings: list[str] | None
    runtime_qa_warnings: list[str] | None
    runtime_qa_report_only: bool | None
    acceptance_checklist: list[str] | None
    story_inputs: list[str] | None
    story_process: list[str] | None
    story_outputs: list[str] | None
    verification_basis: list[str] | None
    primary_files: list[str] | None
    secondary_files: list[str] | None
    parsed_constraints: list[str] | None
    parsed_not_do: list[str] | None
    subtasks: list[SubTask]
    dev_results: Annotated[dict[str, Any], merge_dicts]
    backend_result: str | None
    frontend_result: str | None
    database_result: str | None
    devops_result: str | None
    generated_code_diff: str | None
    test_results: str | None
    test_passed: bool | None
    test_failure_info: str | None
    browser_runtime_dir: str | None
    browser_session_id: str | None
    browse_observations: list[dict[str, Any]] | None
    reference_observations: list[dict[str, Any]] | None
    browser_qa_success: bool | None
    browser_qa_passed: bool | None
    browser_qa_report: str | None
    browser_qa_dir: str | None
    browser_qa_findings: list[str] | None
    browser_qa_warnings: list[str] | None
    browser_qa_health_score: int | None
    browser_qa_ship_readiness: str | None
    browser_qa_mode: str | None
    browser_qa_report_only: bool | None
    qa_design_review_success: bool | None
    qa_design_review_passed: bool | None
    qa_design_review_report: str | None
    qa_design_review_dir: str | None
    plan_design_scorecard: dict[str, Any] | None
    plan_design_assumptions: list[str] | None
    design_review_scores: dict[str, Any] | None
    design_review_route_scores: list[dict[str, Any]] | None
    design_review_findings: list[dict[str, Any]] | None
    design_review_passed: bool | None
    design_review_report: str | None
    before_screenshot_paths: list[str] | None
    after_screenshot_paths: list[str] | None
    security_report: str | None
    review_success: bool | None
    review_passed: bool | None
    review_dir: str | None
    blocking_issues: list[str] | None
    important_issues: list[str] | None
    nice_to_haves: list[str] | None
    review_report: str | None
    code_style_review_success: bool | None
    code_style_review_passed: bool | None
    code_style_review_report: str | None
    code_style_review_dir: str | None
    code_style_review_issues: list[str] | None
    code_acceptance_success: bool | None
    code_acceptance_passed: bool | None
    code_acceptance_report: str | None
    code_acceptance_dir: str | None
    code_acceptance_issues: list[str] | None
    acceptance_success: bool | None
    acceptance_passed: bool | None
    acceptance_report: str | None
    acceptance_dir: str | None
    doc_result: str | None
    delivery_dir: str | None
    fix_result: str | None
    fixer_needed: bool | None
    fixer_success: bool | None
    fix_attempts: int
    fix_fingerprint_history: Annotated[list[str] | None, merge_lists]
    fix_return_to: str | None
    failure_type: str | None
    interruption_reason: str | None
    last_node: Annotated[str | None, merge_last_non_empty]
    review_issue_signature: str | None
    review_issue_history: Annotated[list[str] | None, merge_lists]
    mode_execution_order: Annotated[list[str] | None, merge_lists]
    mode_artifact_paths: dict[str, str] | None
    failure_snapshot_path: str | None
    current_step: str
    error_message: str | None
    shared_blackboard: dict[str, Any] | None
    handoff_packets: Annotated[list[dict[str, Any]] | None, merge_lists]
    issues_to_fix: Annotated[list[dict[str, Any]] | None, merge_lists]
    resolved_issues: Annotated[list[dict[str, Any]] | None, merge_lists]
    agent_messages: Annotated[list[dict[str, Any]] | None, merge_lists]
    all_deliverables: Annotated[list[dict[str, Any]] | None, merge_lists]
    collaboration_trace_id: str | None
    collaboration_started_at: str | None
    collaboration_ended_at: str | None
