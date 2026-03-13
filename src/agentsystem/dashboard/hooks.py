from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.dashboard.main import BASE_DIR

EVENTS_DIR = BASE_DIR / "runs" / "events"


def send_node_start(task_id: str, node_name: str, input_data: dict[str, Any] | None = None) -> None:
    emit_event(
        task_id,
        "node_start",
        {
            "node_name": node_name,
            "input": input_data or {},
        },
    )


def send_node_end(
    task_id: str,
    node_name: str,
    output_data: dict[str, Any] | None = None,
    status: str = "success",
) -> None:
    emit_event(
        task_id,
        "node_end",
        {
            "node_name": node_name,
            "output": output_data or {},
            "status": status,
        },
    )


def send_log(task_id: str, level: str, message: str, extra: dict[str, Any] | None = None) -> None:
    emit_event(
        task_id,
        "log",
        {
            "level": level.upper(),
            "message": message,
            "extra": extra or {},
        },
    )


def send_workflow_state(task_id: str, current_node: str, workflow_state: dict[str, Any]) -> None:
    emit_event(
        task_id,
        "workflow_state",
        {
            "current_node": current_node,
            "state": workflow_state,
        },
    )


def get_local_logs(task_id: str | None = None) -> list[dict[str, Any]]:
    if task_id:
        return _read_event_file(EVENTS_DIR / f"{task_id}.jsonl")

    logs: list[dict[str, Any]] = []
    if not EVENTS_DIR.exists():
        return logs
    for event_file in sorted(EVENTS_DIR.glob("*.jsonl")):
        logs.extend(_read_event_file(event_file))
    return logs


def emit_event(task_id: str, event_type: str, payload: dict[str, Any]) -> None:
    event = {
        "task_id": task_id,
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    event_file = EVENTS_DIR / f"{task_id}.jsonl"
    with event_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_event_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
