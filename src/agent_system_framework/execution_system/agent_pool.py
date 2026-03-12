from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agent_system_framework.core.agent_meta_model import AgentMetaModel
from agent_system_framework.core.state_schema import TaskState


@dataclass(slots=True)
class KernelArtifact:
    output_ref: str
    output_payload: dict[str, Any]
    artifacts: dict[str, dict[str, Any]]
    emitted_events: list[tuple[str, dict[str, Any]]]


class KernelAgent(Protocol):
    @property
    def meta(self) -> AgentMetaModel: ...

    def can_handle(self, task: TaskState) -> bool: ...

    def execute(self, task: TaskState) -> KernelArtifact: ...
