from __future__ import annotations

from typing import Protocol


class IdempotencyStore(Protocol):
    def seen(self, key: str) -> bool: ...

    def record(self, key: str, result: object) -> None: ...

    def get(self, key: str) -> object | None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, object] = {}

    def seen(self, key: str) -> bool:
        return key in self._results

    def record(self, key: str, result: object) -> None:
        self._results[key] = result

    def get(self, key: str) -> object | None:
        return self._results.get(key)
