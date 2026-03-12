from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GateDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
