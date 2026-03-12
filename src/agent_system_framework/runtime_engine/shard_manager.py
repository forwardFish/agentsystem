from __future__ import annotations


class ShardManager:
    def __init__(self, shard_count: int = 4) -> None:
        self.shard_count = shard_count

    def assign(self, key: str) -> str:
        return f"shard-{hash(key) % self.shard_count}"
