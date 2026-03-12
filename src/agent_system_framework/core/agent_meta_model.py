from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AgentType(StrEnum):
    TRANSACTIONAL = "transactional"
    BUSINESS = "business"


class Plane(StrEnum):
    BUILD = "build"
    RUNTIME = "runtime"
    GOVERNANCE = "governance"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass(slots=True)
class AgentMetaModel:
    agent_id: str
    agent_type: AgentType
    plane: Plane
    capabilities: list[str] = field(default_factory=list)
    input_contract: str = "runtime-task-input"
    output_contract: str = "runtime-task-output"
    allowed_tools: list[str] = field(default_factory=list)
    allowed_events: list[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.DRAFT
    version: str = "0.1.0"
    owner: str = "system"
    approval_policy: str = "default"
    idempotency_scope: str = "task"
    shard_affinity: str = "agent_id"
