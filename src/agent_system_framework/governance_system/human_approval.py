from __future__ import annotations


class NoopHumanApproval:
    def request(self, *, task_id: str, reasons: list[str]) -> bool:
        return False
