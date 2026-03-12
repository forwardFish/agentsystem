from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agentsystem.runtime.agent_prefs import AgentPrefs
from agentsystem.runtime.agent_state import AgentState


@dataclass
class AgentRuntime:
    agent_type: str
    repo_root: Path
    state: AgentState = AgentState.IDLE
    last_reason: str = ""
    prefs: AgentPrefs = field(init=False)

    def __post_init__(self) -> None:
        self.repo_root = Path(self.repo_root).resolve()
        self.prefs = AgentPrefs(self.repo_root)

    def start(self, reason: str = "") -> None:
        self.state = AgentState.RUNNING
        self.last_reason = reason
        self.write_heartbeat("start", reason or "manual_start")

    def pause(self, reason: str = "") -> None:
        self.state = AgentState.PAUSED
        self.last_reason = reason
        self.write_heartbeat("pause", reason or "manual_pause")

    def fail(self, reason: str) -> None:
        self.state = AgentState.FAILED
        self.last_reason = reason
        self.write_heartbeat("failed", reason)

    def gate(self, reason: str) -> None:
        self.state = AgentState.GATED
        self.last_reason = reason
        self.write_heartbeat("gated", reason)

    def idle(self, reason: str = "") -> None:
        self.state = AgentState.IDLE
        self.last_reason = reason
        self.write_heartbeat("idle", reason or "no_pending_tasks")

    def write_heartbeat(self, event: str, detail: str, *, status: str | None = None) -> None:
        heartbeat_file = self.prefs.get_heartbeat_file(self.agent_type)
        timestamp = datetime.now().isoformat(timespec="seconds")
        line = f"- {timestamp}: {event} | {detail} | status: {(status or self.state.value).lower()}\n"
        if heartbeat_file.exists():
            content = heartbeat_file.read_text(encoding="utf-8")
        else:
            content = f"# {self.agent_type.title()} Agent Heartbeat\n\n"
        heartbeat_file.write_text(content + line, encoding="utf-8")
