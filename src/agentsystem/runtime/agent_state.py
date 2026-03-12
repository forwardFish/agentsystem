from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    GATED = "GATED"
    FAILED = "FAILED"
