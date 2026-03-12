from __future__ import annotations

from agent_system_framework.core.agent_meta_model import AgentStatus


class LifecycleError(ValueError):
    """Raised when an invalid lifecycle transition is requested."""


class LifecycleManager:
    _transitions: dict[AgentStatus, set[AgentStatus]] = {
        AgentStatus.DRAFT: {AgentStatus.REGISTERED},
        AgentStatus.REGISTERED: {AgentStatus.READY},
        AgentStatus.READY: {AgentStatus.RUNNING, AgentStatus.PAUSED},
        AgentStatus.RUNNING: {
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.BLOCKED,
            AgentStatus.PAUSED,
            AgentStatus.AWAITING_APPROVAL,
        },
        AgentStatus.PAUSED: {AgentStatus.RUNNING, AgentStatus.ARCHIVED},
        AgentStatus.BLOCKED: {AgentStatus.READY, AgentStatus.ARCHIVED},
        AgentStatus.FAILED: {AgentStatus.READY, AgentStatus.ARCHIVED},
        AgentStatus.AWAITING_APPROVAL: {AgentStatus.RUNNING, AgentStatus.BLOCKED},
        AgentStatus.COMPLETED: {AgentStatus.ARCHIVED},
        AgentStatus.ARCHIVED: set(),
    }

    def transition(self, current: AgentStatus, target: AgentStatus) -> AgentStatus:
        if target not in self._transitions[current]:
            raise LifecycleError(f"Invalid lifecycle transition: {current} -> {target}")
        return target
