from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


def merge_lists(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return [*(left or []), *(right or [])]


class SubTask(BaseModel):
    id: str
    type: str
    description: str
    files_to_modify: list[str] = Field(default_factory=list)
    status: str = "pending"


class AgentRole(str, Enum):
    REQUIREMENT = "Requirement"
    ARCHITECTURE_REVIEW = "ArchitectureReview"
    BUILDER = "Builder"
    SYNC = "Sync"
    TESTER = "Tester"
    BROWSER_QA = "BrowserQA"
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
    fix_return_to: str | None
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
