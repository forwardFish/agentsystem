from __future__ import annotations

from itertools import count

from agent_system_framework.execution_system.sandbox import InMemorySandbox


class SandboxManager:
    def __init__(self) -> None:
        self._sequence = count(1)

    def allocate(self, agent_id: str, resource_limits: dict[str, int]) -> InMemorySandbox:
        return InMemorySandbox(
            sandbox_id=f"sandbox-{next(self._sequence)}",
            agent_id=agent_id,
            resource_limits=resource_limits,
        )
