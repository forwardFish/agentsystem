from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass
class TaskEvent:
    event_id: str
    task_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class RedisEventBus:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis package is required for RedisEventBus") from exc
        self.client = redis.Redis(host=host, port=port, db=db)
        self.stream_key = "task_events"
        self.consumer_group = "task_state_machine"

    def init_consumer_group(self) -> None:
        try:
            self.client.xgroup_create(name=self.stream_key, groupname=self.consumer_group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish_event(self, event: TaskEvent) -> str:
        payload = asdict(event)
        payload["payload"] = json.dumps(payload["payload"], ensure_ascii=False)
        event_id = self.client.xadd(self.stream_key, payload)
        return event_id.decode() if isinstance(event_id, bytes) else str(event_id)

    def subscribe_events(self, callback: Callable[[TaskEvent], None]) -> None:
        self.init_consumer_group()
        while True:
            responses = self.client.xreadgroup(
                groupname=self.consumer_group,
                consumername="task_worker",
                streams={self.stream_key: ">"},
                block=1000,
            )
            for _stream, events in responses:
                for event_id, raw in events:
                    event = TaskEvent(
                        event_id=event_id.decode() if isinstance(event_id, bytes) else str(event_id),
                        task_id=raw[b"task_id"].decode(),
                        event_type=raw[b"event_type"].decode(),
                        payload=json.loads(raw[b"payload"]),
                        timestamp=float(raw[b"timestamp"]),
                    )
                    callback(event)
                    self.client.xack(self.stream_key, self.consumer_group, event_id)
