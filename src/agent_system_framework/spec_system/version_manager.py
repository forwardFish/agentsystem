from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class RuleVersionManager:
    """Tracks effective rule snapshots without executing any business logic."""

    def snapshot(self, sources: dict[str, str]) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for name, path_str in sources.items():
            snapshot[name] = sha256(Path(path_str).read_bytes()).hexdigest()[:12]
        return snapshot
