from __future__ import annotations

from copy import deepcopy
from typing import Any


class CheckpointStore:
    def __init__(self) -> None:
        self._checkpoints: dict[str, dict[str, Any]] = {}

    def save(self, key: str, payload: dict[str, Any]) -> None:
        self._checkpoints[key] = deepcopy(payload)

    def load(self, key: str) -> dict[str, Any] | None:
        payload = self._checkpoints.get(key)
        return deepcopy(payload) if payload is not None else None
