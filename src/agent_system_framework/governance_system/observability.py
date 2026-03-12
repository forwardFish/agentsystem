from __future__ import annotations


class ObservabilityModule:
    def __init__(self) -> None:
        self.metrics: dict[str, int] = {"runs": 0, "approved": 0, "blocked": 0}

    def record_run(self, approved: bool) -> None:
        self.metrics["runs"] += 1
        self.metrics["approved" if approved else "blocked"] += 1
