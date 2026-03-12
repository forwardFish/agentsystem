from __future__ import annotations

from enum import Enum
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

import yaml

from agentsystem.integrations.checkpoint_saver import get_checkpoint_saver
from agentsystem.orchestration.workspace_manager import WorkspaceLockError


class TaskStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    GATED = "gated"
    APPROVED = "approved"
    MERGED = "merged"
    FAILED = "failed"
    RETRYING = "retrying"
    REJECTED = "rejected"
    REOPENED = "reopened"


class TaskState(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: str
    status: str = TaskStatus.DRAFT.value
    worktree_path: str
    test_result: dict[str, Any] | None = None
    review_result: dict[str, Any] | None = None
    approval_result: dict[str, Any] | None = None
    error_msg: str | None = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1)


def planning_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.PLANNING.value
    return state


def implementing_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.IMPLEMENTING.value
    return state


def verifying_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.VERIFYING.value
    if state.test_result is None:
        state.test_result = {"passed": True, "details": "default verification passed"}
    return state


def reviewing_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.REVIEWING.value
    if state.review_result is None:
        state.review_result = {"passed": True, "details": "default review passed"}
    return state


def gate_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.GATED.value
    return state


def approval_node(state: TaskState) -> TaskState:
    state.status = TaskStatus.GATED.value
    if state.approval_result is None:
        state.approval_result = {"approved": False, "rejected": False}
    return state


def retry_node(state: TaskState) -> TaskState:
    state.retry_count += 1
    state.status = TaskStatus.RETRYING.value if state.retry_count < state.max_retries else TaskStatus.FAILED.value
    return state


def verify_router(state: TaskState) -> str:
    return "reviewing" if (state.test_result or {}).get("passed", False) else "retrying"


def review_router(state: TaskState) -> str:
    return "gated" if (state.review_result or {}).get("passed", False) else "retrying"


def approval_router(state: TaskState) -> str:
    result = state.approval_result or {}
    if result.get("approved", False):
        state.status = TaskStatus.MERGED.value
        return "merged"
    if result.get("rejected", False):
        state.status = TaskStatus.FAILED.value
        return "failed"
    return "waiting"


def retry_router(state: TaskState) -> str:
    return "implementing" if state.retry_count < state.max_retries else "failed"


def build_task_state_machine(*, checkpointer=None):
    graph = StateGraph(TaskState)
    graph.add_node("planning", planning_node)
    graph.add_node("implementing", implementing_node)
    graph.add_node("verifying", verifying_node)
    graph.add_node("reviewing", reviewing_node)
    graph.add_node("gated", gate_node)
    graph.add_node("approval", approval_node)
    graph.add_node("retrying", retry_node)
    graph.set_entry_point("planning")
    graph.add_edge("planning", "implementing")
    graph.add_edge("implementing", "verifying")
    graph.add_conditional_edges("verifying", verify_router, {"reviewing": "reviewing", "retrying": "retrying"})
    graph.add_conditional_edges("reviewing", review_router, {"gated": "gated", "retrying": "retrying"})
    graph.add_edge("gated", "approval")
    graph.add_conditional_edges("approval", approval_router, {"merged": END, "failed": END, "waiting": END})
    graph.add_conditional_edges("retrying", retry_router, {"implementing": "implementing", "failed": END})
    return graph.compile(checkpointer=checkpointer or MemorySaver())


class TaskStateMachine:
    def __init__(self, config: dict[str, Any], workspace_manager):
        self.config = config
        self.workspace_manager = workspace_manager
        self.graph = build_task_state_machine(checkpointer=get_checkpoint_saver())
        self.last_result: dict[str, Any] | None = None
        self.last_task_id: str | None = None
        self.last_worktree_path: str | None = None

    def run(self, task_file: str | Path) -> dict[str, Any]:
        task_path = Path(task_file).resolve()
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{task_path} must contain a mapping")

        task_name = str(payload.get("task_name", "task"))
        task_id = self._slugify(task_name)
        branch = f"feature/{task_id}"
        try:
            worktree_path = self.workspace_manager.create_worktree(task_id, branch)
        except WorkspaceLockError:
            worktree_path = self.workspace_manager.worktree_root / task_id
        self.last_task_id = task_id
        self.last_worktree_path = str(worktree_path)

        state = TaskState(task_id=task_id, worktree_path=str(worktree_path))
        result = self.graph.invoke(state, config={"configurable": {"thread_id": task_id}})
        if isinstance(result, TaskState):
            values = result.model_dump(mode="json")
        else:
            values = self._normalize(result)
        self.workspace_manager.update_task_state(task_id, {"status": values["status"], "retry_count": values["retry_count"]})
        self.last_result = values
        return values

    def save_checkpoint(self) -> dict[str, Any] | None:
        if not self.last_task_id:
            return None
        values = self.graph.get_state({"configurable": {"thread_id": self.last_task_id}}).values
        return self._normalize(values)

    def write_audit_log(self, output_path: str | Path) -> Path:
        if self.last_result is None:
            raise ValueError("No task execution result available")
        audit_path = Path(output_path).resolve()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(json.dumps(self.last_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return audit_path

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9-]+", "-", value.strip().lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        if slug:
            return slug
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        return f"task-{digest}"

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: self._normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._normalize(item) for item in value]
        return value
