from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_system_framework.core.state_schema import TaskState
from agent_system_framework.runtime_engine.event_bus import Event


@dataclass(slots=True)
class WriteStore:
    tasks: dict[str, TaskState] = field(default_factory=dict)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class ReadStore:
    dashboard: dict[str, dict[str, Any]] = field(default_factory=dict)


class ReadModelProjector:
    def __init__(self, read_store: ReadStore) -> None:
        self._read_store = read_store

    def project(self, event: Event) -> None:
        task_id = event.payload.get("task_id", "unknown")
        current = self._read_store.dashboard.setdefault(task_id, {"events": []})
        current["events"].append(event.name)
        current["last_payload"] = event.payload
