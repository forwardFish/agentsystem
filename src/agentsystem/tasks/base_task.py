from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TaskResult:
    name: str
    success: bool
    detail: str


class BaseTask:
    name = "base-task"

    def run(self) -> TaskResult:  # pragma: no cover - interface method
        raise NotImplementedError
