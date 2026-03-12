from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SandboxSession:
    sandbox_id: str
    agent_id: str
    resource_limits: dict[str, int] = field(default_factory=dict)


class InMemorySandbox:
    def __init__(self, sandbox_id: str, agent_id: str, resource_limits: dict[str, int]) -> None:
        self.session = SandboxSession(
            sandbox_id=sandbox_id,
            agent_id=agent_id,
            resource_limits=resource_limits,
        )
