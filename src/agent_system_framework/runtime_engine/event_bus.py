from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class Event:
    name: str
    payload: dict[str, Any]
    trace_id: str


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._events: list[Event] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)

    def publish(self, event: Event) -> None:
        self._events.append(event)
        for handler in self._subscribers.get(event.name, []):
            handler(event)

    @property
    def events(self) -> list[Event]:
        return list(self._events)
