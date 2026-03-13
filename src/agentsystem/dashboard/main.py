from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parents[3]
RUNS_DIR = BASE_DIR / "runs"
EVENTS_DIR = RUNS_DIR / "events"
ARTIFACTS_DIR = RUNS_DIR / "artifacts"
REPO_META_DIR = BASE_DIR / "repo-worktree" / ".meta"


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()
app = FastAPI(title="Agent System Execution Dashboard")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
async def get_dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/tasks")
async def get_tasks() -> JSONResponse:
    return JSONResponse({"tasks": load_tasks()})


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: str) -> JSONResponse:
    return JSONResponse(load_task_detail(task_id))


@app.get("/api/metrics")
async def get_metrics() -> JSONResponse:
    return JSONResponse(compute_metrics())


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str) -> None:
    await manager.connect(websocket)
    event_file = EVENTS_DIR / f"{task_id}.jsonl"
    offset = 0
    try:
        for event in load_task_events(task_id):
            await websocket.send_json(event)
        if event_file.exists():
            offset = event_file.stat().st_size
        while True:
            await asyncio.sleep(0.25)
            if not event_file.exists():
                continue
            current_size = event_file.stat().st_size
            if current_size < offset:
                offset = 0
            if current_size == offset:
                continue
            with event_file.open("r", encoding="utf-8") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    await websocket.send_json(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def load_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if not RUNS_DIR.exists():
        return tasks
    for run_file in sorted(RUNS_DIR.glob("prod_audit_*.json"), reverse=True):
        try:
            payload = json.loads(run_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
        task_payload = result.get("task_payload", {}) if isinstance(result.get("task_payload"), dict) else {}
        tasks.append(
            {
                "task_id": payload.get("task_id") or run_file.stem.replace("prod_audit_", ""),
                "task_name": payload.get("task_name") or task_payload.get("goal") or payload.get("branch"),
                "status": "success" if payload.get("success") else "failed",
                "blast_radius": task_payload.get("blast_radius"),
                "execution_mode": task_payload.get("mode"),
                "branch": payload.get("branch"),
                "commit": payload.get("commit"),
                "created_at": run_file.stat().st_mtime,
            }
        )
    return tasks


def load_task_detail(task_id: str) -> dict[str, Any]:
    run_file = RUNS_DIR / f"prod_audit_{task_id}.json"
    payload: dict[str, Any] = {}
    if run_file.exists():
        payload = json.loads(run_file.read_text(encoding="utf-8"))

    meta_dir = REPO_META_DIR / task_id
    archive_dir = ARTIFACTS_DIR / task_id
    artifacts = {
        "pr_description": _read_first_available_text(
            archive_dir / "pr_prep" / "pr_description.md",
            meta_dir / "pr_prep" / "pr_description.md",
        ),
        "review_report": _read_first_available_text(
            archive_dir / "review" / "review_report.md",
            meta_dir / "review" / "review_report.md",
        ),
        "commit_message": _read_first_available_text(
            archive_dir / "pr_prep" / "commit_message.txt",
            meta_dir / "pr_prep" / "commit_message.txt",
        ),
    }
    return {
        "task_id": task_id,
        "audit_log": payload,
        "artifacts": artifacts,
        "events": load_task_events(task_id),
    }


def compute_metrics() -> dict[str, Any]:
    tasks = load_tasks()
    total_tasks = len(tasks)
    success_tasks = sum(1 for task in tasks if task["status"] == "success")
    first_pass_successes = 0
    retry_rounds = 0
    blocking_issue_count = 0
    acceptance_total = 0
    acceptance_met = 0
    daily: dict[str, dict[str, float]] = {}
    for task in tasks:
        detail = load_task_detail(task["task_id"])
        audit_log = detail.get("audit_log", {})
        result = audit_log.get("result", {}) if isinstance(audit_log, dict) else {}
        fix_attempts = int(result.get("fix_attempts") or 0)
        retry_rounds += fix_attempts
        if audit_log.get("success") and fix_attempts == 0:
            first_pass_successes += 1
        blocking_issue_count += len(result.get("blocking_issues") or [])
        task_payload = result.get("task_payload", {}) if isinstance(result, dict) else {}
        acceptance_items = task_payload.get("acceptance_criteria", []) if isinstance(task_payload, dict) else []
        acceptance_total += len(acceptance_items)
        acceptance_met += _count_met_acceptance_items(result.get("acceptance_report"), acceptance_items)
        created_at = _normalize_created_at(task.get("created_at"))
        if created_at:
            day_key = created_at[:10]
            bucket = daily.setdefault(day_key, {"total": 0, "success": 0, "retries": 0, "acceptance_total": 0, "acceptance_met": 0})
            bucket["total"] += 1
            bucket["success"] += 1 if audit_log.get("success") else 0
            bucket["retries"] += fix_attempts
            bucket["acceptance_total"] += len(acceptance_items)
            bucket["acceptance_met"] += _count_met_acceptance_items(result.get("acceptance_report"), acceptance_items)

    trend_labels = sorted(daily.keys())[-7:]
    success_rate_trend = []
    retry_trend = []
    acceptance_trend = []
    for label in trend_labels:
        bucket = daily[label]
        total = bucket["total"] or 1
        success_rate_trend.append(round(bucket["success"] / total * 100, 1))
        retry_trend.append(round(bucket["retries"] / total, 1))
        acceptance_trend.append(
            round(bucket["acceptance_met"] / bucket["acceptance_total"] * 100, 1) if bucket["acceptance_total"] else 0.0
        )
    return {
        "total_tasks": total_tasks,
        "success_tasks": success_tasks,
        "failed_tasks": total_tasks - success_tasks,
        "first_pass_rate": round(first_pass_successes / total_tasks * 100, 1) if total_tasks else 0.0,
        "avg_blocking_issues": round(blocking_issue_count / total_tasks, 1) if total_tasks else 0.0,
        "avg_retry_rounds": round(retry_rounds / total_tasks, 1) if total_tasks else 0.0,
        "acceptance_hit_rate": round(acceptance_met / acceptance_total * 100, 1) if acceptance_total else 0.0,
        "trend": {
            "labels": trend_labels,
            "success_rate": success_rate_trend,
            "avg_retry_rounds": retry_trend,
            "acceptance_hit_rate": acceptance_trend,
        },
    }


def load_task_events(task_id: str) -> list[dict[str, Any]]:
    event_file = EVENTS_DIR / f"{task_id}.jsonl"
    events: list[dict[str, Any]] = []
    if not event_file.exists():
        return events
    for line in event_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_first_available_text(*paths: Path) -> str:
    for path in paths:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _count_met_acceptance_items(report: Any, acceptance_items: list[Any]) -> int:
    if not isinstance(report, str):
        return len(acceptance_items) if acceptance_items else 0
    return sum(1 for line in report.splitlines() if ": 已满足" in line or ": satisfied" in line.lower())


def _normalize_created_at(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            from datetime import datetime

            return datetime.fromtimestamp(value).isoformat()
        return str(value)
    except Exception:
        return None
