from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from agent_system_framework.core.agent_meta_model import Plane


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAIL = "fail"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"


@dataclass(slots=True)
class TaskMetadata:
    start_time: str | None = None
    end_time: str | None = None
    agent_id: str = ""
    agent_version: str = ""
    trace_id: str = ""
    upstream_event: str = ""


@dataclass(slots=True)
class TaskState:
    task_id: str
    run_id: str
    shard_id: str
    graph_type: Plane
    stage: str
    status: TaskStatus
    input_ref: str
    output_ref: str = ""
    error: dict[str, Any] | None = None
    retry_count: int = 0
    rule_version: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    approval_required: bool = False
    metadata: TaskMetadata = field(default_factory=TaskMetadata)
