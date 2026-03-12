from __future__ import annotations


class PermissionError(ValueError):
    """Raised when a tool or event is not permitted."""


class PermissionPolicy:
    def validate_tools(self, allowed_tools: list[str], requested_tools: list[str]) -> None:
        denied = sorted(set(requested_tools) - set(allowed_tools))
        if denied:
            raise PermissionError(f"Tools not allowed: {', '.join(denied)}")

    def validate_event(self, allowed_events: list[str], event_name: str) -> None:
        if event_name not in allowed_events:
            raise PermissionError(f"Event not allowed: {event_name}")
