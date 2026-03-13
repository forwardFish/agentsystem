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
TASKS_DIR = BASE_DIR / "tasks"


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


@app.get("/story")
async def get_story_dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "story.html")


@app.get("/api/tasks")
async def get_tasks() -> JSONResponse:
    return JSONResponse({"tasks": load_tasks()})


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: str) -> JSONResponse:
    return JSONResponse(load_task_detail(task_id))


@app.get("/api/tasks/{task_id}/collaboration")
async def get_task_collaboration(task_id: str) -> JSONResponse:
    return JSONResponse(load_task_collaboration(task_id))


@app.get("/api/metrics")
async def get_metrics() -> JSONResponse:
    return JSONResponse(compute_metrics())


@app.get("/api/backlogs")
async def get_backlogs() -> JSONResponse:
    return JSONResponse({"backlogs": load_backlogs()})


@app.get("/api/backlogs/{backlog_id}")
async def get_backlog_detail(backlog_id: str) -> JSONResponse:
    return JSONResponse(load_backlog_detail(backlog_id))


@app.get("/api/backlogs/{backlog_id}/sprints/{sprint_id}")
async def get_sprint_detail(backlog_id: str, sprint_id: str) -> JSONResponse:
    return JSONResponse(load_sprint_detail(backlog_id, sprint_id))


@app.get("/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}")
async def get_story_detail(backlog_id: str, sprint_id: str, story_id: str) -> JSONResponse:
    return JSONResponse(load_story_detail(backlog_id, sprint_id, story_id))


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
        "code_acceptance_report": _read_first_available_text(
            archive_dir / "code_acceptance" / "code_acceptance_report.md",
            meta_dir / "code_acceptance" / "code_acceptance_report.md",
        ),
        "acceptance_report": _read_first_available_text(
            archive_dir / "acceptance" / "acceptance_report.md",
            meta_dir / "acceptance" / "acceptance_report.md",
        ),
        "delivery_report": _read_first_available_text(
            archive_dir / "delivery" / "story_delivery_report.md",
            meta_dir / "delivery" / "story_delivery_report.md",
        ),
        "completion_standard": _read_first_available_text(
            archive_dir / "delivery" / "story_completion_standard.md",
            meta_dir / "delivery" / "story_completion_standard.md",
        ),
    }
    completion = _extract_completion(payload)
    return {
        "task_id": task_id,
        "audit_log": payload,
        "artifacts": artifacts,
        "events": load_task_events(task_id),
        "collaboration": _extract_collaboration(payload),
        "completion": completion,
    }


def load_task_collaboration(task_id: str) -> dict[str, Any]:
    run_file = RUNS_DIR / f"prod_audit_{task_id}.json"
    payload: dict[str, Any] = {}
    if run_file.exists():
        payload = json.loads(run_file.read_text(encoding="utf-8"))
    collaboration = _extract_collaboration(payload)
    return {"task_id": task_id, **collaboration}


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


def load_backlogs() -> list[dict[str, Any]]:
    backlogs: list[dict[str, Any]] = []
    if not TASKS_DIR.exists():
        return backlogs
    for backlog_dir in sorted(path for path in TASKS_DIR.iterdir() if path.is_dir()):
        overview_file = backlog_dir / "sprint_overview.md"
        if not overview_file.exists():
            continue
        sprint_dirs = sorted(path for path in backlog_dir.iterdir() if path.is_dir() and path.name.startswith("sprint_"))
        story_count = sum(len(list(sprint_dir.rglob("S*.yaml"))) for sprint_dir in sprint_dirs)
        backlogs.append(
            {
                "id": backlog_dir.name,
                "name": backlog_dir.name,
                "overview_path": str(overview_file),
                "sprint_count": len(sprint_dirs),
                "story_count": story_count,
            }
        )
    return backlogs


def load_backlog_detail(backlog_id: str) -> dict[str, Any]:
    backlog_dir = TASKS_DIR / backlog_id
    sprint_dirs = sorted(path for path in backlog_dir.iterdir() if path.is_dir() and path.name.startswith("sprint_")) if backlog_dir.exists() else []
    return {
        "id": backlog_id,
        "overview_markdown": _read_optional_text(backlog_dir / "sprint_overview.md"),
        "sprints": [_build_sprint_summary(backlog_id, sprint_dir) for sprint_dir in sprint_dirs],
    }


def load_sprint_detail(backlog_id: str, sprint_id: str) -> dict[str, Any]:
    sprint_dir = TASKS_DIR / backlog_id / sprint_id
    story_index = _load_story_run_index()
    execution_order = [line.strip() for line in _read_optional_text(sprint_dir / "execution_order.txt").splitlines() if line.strip()]
    epics: list[dict[str, Any]] = []
    for epic_doc in sorted(sprint_dir.glob("epic_*.md")):
        epic_dir = sprint_dir / epic_doc.stem
        stories: list[dict[str, Any]] = []
        if epic_dir.exists():
            for story_file in sorted(epic_dir.glob("S*.yaml")):
                payload = yaml_safe_load(story_file)
                story_id = str(payload.get("story_id") or payload.get("task_id") or story_file.stem.split("_", 1)[0])
                run_info = story_index.get(story_id)
                stories.append(
                    {
                        "story_id": story_id,
                        "task_name": payload.get("task_name") or story_id,
                        "epic": payload.get("epic"),
                        "blast_radius": payload.get("blast_radius"),
                        "status": _story_status_from_run(run_info),
                        "latest_task_id": run_info.get("task_id") if run_info else None,
                    }
                )
        epics.append(
            {
                "id": epic_doc.stem,
                "title": epic_doc.stem,
                "markdown": _read_optional_text(epic_doc),
                "stories": stories,
            }
        )
    return {
        "id": sprint_id,
        "sprint_plan_markdown": _read_optional_text(sprint_dir / "sprint_plan.md"),
        "execution_order": execution_order,
        "epics": epics,
    }


def load_story_detail(backlog_id: str, sprint_id: str, story_id: str) -> dict[str, Any]:
    sprint_dir = TASKS_DIR / backlog_id / sprint_id
    story_file = next(sprint_dir.rglob(f"{story_id}_*.yaml"), None)
    payload = yaml_safe_load(story_file) if story_file else {}
    story_index = _load_story_run_index()
    run_info = story_index.get(story_id)
    task_detail = load_task_detail(run_info["task_id"]) if run_info else {"audit_log": {}, "artifacts": {}, "events": []}
    return {
        "story_id": story_id,
        "story": payload,
        "story_file": str(story_file) if story_file else "",
        "status": _story_status_from_run(run_info),
        "latest_task_id": run_info.get("task_id") if run_info else None,
        "latest_run": run_info,
        "task_detail": task_detail,
    }


def _extract_completion(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    task_payload = result.get("task_payload", {}) if isinstance(result, dict) else {}
    return {
        "tests_passed": bool(result.get("test_passed")),
        "review_passed": bool(result.get("review_passed")),
        "code_acceptance_passed": bool(result.get("code_acceptance_passed")),
        "acceptance_passed": bool(result.get("acceptance_passed")),
        "fix_attempts": int(result.get("fix_attempts") or 0),
        "blocking_issues": list(result.get("blocking_issues") or []),
        "acceptance_criteria": list(task_payload.get("acceptance_criteria") or []),
        "story_id": task_payload.get("story_id") or task_payload.get("task_id"),
        "task_name": task_payload.get("task_name") or task_payload.get("goal"),
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


def _build_sprint_summary(backlog_id: str, sprint_dir: Path) -> dict[str, Any]:
    story_index = _load_story_run_index()
    story_ids: list[str] = []
    done = failed = 0
    for story_file in sprint_dir.rglob("S*.yaml"):
        payload = yaml_safe_load(story_file)
        story_id = str(payload.get("story_id") or payload.get("task_id") or story_file.stem.split("_", 1)[0])
        story_ids.append(story_id)
        status = _story_status_from_run(story_index.get(story_id))
        if status == "done":
            done += 1
        elif status == "failed":
            failed += 1
    if failed:
        overall = "failed"
    elif done == len(story_ids) and story_ids:
        overall = "done"
    elif done:
        overall = "partial"
    else:
        overall = "not_started"
    return {
        "id": sprint_dir.name,
        "name": sprint_dir.name,
        "backlog_id": backlog_id,
        "story_count": len(story_ids),
        "done_count": done,
        "failed_count": failed,
        "status": overall,
    }


def _load_story_run_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not RUNS_DIR.exists():
        return index
    for run_file in sorted(RUNS_DIR.glob("prod_audit_*.json"), key=lambda item: item.stat().st_mtime):
        try:
            payload = json.loads(run_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
        task_payload = result.get("task_payload", {}) if isinstance(result.get("task_payload"), dict) else {}
        story_id = task_payload.get("story_id") or task_payload.get("task_id")
        if not story_id:
            continue
        index[str(story_id)] = {
            "task_id": payload.get("task_id"),
            "success": bool(payload.get("success")),
            "branch": payload.get("branch"),
            "commit": payload.get("commit"),
            "created_at": payload.get("created_at") or run_file.stat().st_mtime,
        }
    return index


def _story_status_from_run(run_info: dict[str, Any] | None) -> str:
    if not run_info:
        return "not_started"
    return "done" if run_info.get("success") else "failed"


def yaml_safe_load(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _extract_collaboration(audit_log: dict[str, Any]) -> dict[str, Any]:
    result = audit_log.get("result", {}) if isinstance(audit_log, dict) else {}
    if not isinstance(result, dict):
        result = {}
    return {
        "trace_id": result.get("collaboration_trace_id"),
        "started_at": result.get("collaboration_started_at"),
        "ended_at": result.get("collaboration_ended_at"),
        "shared_blackboard": result.get("shared_blackboard") or {},
        "handoff_packets": result.get("handoff_packets") or [],
        "issues_to_fix": result.get("issues_to_fix") or [],
        "resolved_issues": result.get("resolved_issues") or [],
        "all_deliverables": result.get("all_deliverables") or [],
    }
