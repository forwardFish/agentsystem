from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AuditRecord:
    actor_id: str
    action: str
    trace_id: str
    payload: dict[str, Any]


class AuditLogger:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def write(self, actor_id: str, action: str, trace_id: str, payload: dict[str, Any]) -> None:
        self.records.append(AuditRecord(actor_id=actor_id, action=action, trace_id=trace_id, payload=payload))
