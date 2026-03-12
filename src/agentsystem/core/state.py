from __future__ import annotations

from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


class SubTask(BaseModel):
    id: str
    type: str
    description: str
    files_to_modify: list[str] = Field(default_factory=list)
    status: str = "pending"


class DevState(TypedDict, total=False):
    user_requirement: str
    repo_b_path: str
    task_payload: dict[str, Any] | None
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
    security_report: str | None
    review_success: bool | None
    review_passed: bool | None
    review_dir: str | None
    blocking_issues: list[str] | None
    important_issues: list[str] | None
    nice_to_haves: list[str] | None
    review_report: str | None
    doc_result: str | None
    fix_result: str | None
    fixer_needed: bool | None
    fixer_success: bool | None
    fix_attempts: int
    current_step: str
    error_message: str | None
