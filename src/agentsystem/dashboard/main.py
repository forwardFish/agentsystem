from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .project_registry import ProjectRegistration, RuntimeSurface
from .versefina_runtime_showcase import load_versefina_runtime_showcase_data

BASE_DIR = Path(__file__).resolve().parents[3]
RUNS_DIR = BASE_DIR / "runs"
EVENTS_DIR = RUNS_DIR / "events"
ARTIFACTS_DIR = RUNS_DIR / "artifacts"
REPO_META_DIR = BASE_DIR / "repo-worktree" / ".meta"
TASKS_DIR = BASE_DIR / "tasks"
STORY_STATUS_REGISTRY = TASKS_DIR / "story_status_registry.json"
STORY_ACCEPTANCE_REVIEW_REGISTRY = TASKS_DIR / "story_acceptance_reviews.json"
FINAHUNT_TASKS_DIR = BASE_DIR.parent / "finahunt" / "tasks"
FINAHUNT_STORY_STATUS_REGISTRY = FINAHUNT_TASKS_DIR / "story_status_registry.json"
FINAHUNT_STORY_ACCEPTANCE_REVIEW_REGISTRY = FINAHUNT_TASKS_DIR / "story_acceptance_reviews.json"
FINAHUNT_RUNTIME_DIR = BASE_DIR.parent / "finahunt" / "workspace" / "artifacts" / "runtime"
VERSEFINA_RUNTIME_DIR = BASE_DIR.parent / "versefina" / ".runtime"


class StoryAcceptanceReviewPayload(BaseModel):
    reviewer: str = Field(min_length=1)
    verdict: Literal["approved", "needs_followup", "rejected"]
    summary: str = Field(min_length=1)
    notes: str = ""
    checked_at: str | None = None
    run_id: str | None = None


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


@app.get("/projects/{project_id}/runtime")
async def get_project_runtime_dashboard(project_id: str):
    return _runtime_dashboard_response(project_id)


@app.get("/finahunt/runtime")
async def get_finahunt_runtime_dashboard() -> FileResponse:
    return _runtime_dashboard_response("finahunt")


@app.get("/versefina/runtime")
async def get_versefina_runtime_dashboard() -> FileResponse:
    return _runtime_dashboard_response("versefina")


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
async def get_metrics(project: str = "versefina") -> JSONResponse:
    return JSONResponse(compute_metrics(project))


@app.get("/api/projects")
async def get_projects() -> JSONResponse:
    return JSONResponse({"projects": load_projects()})


@app.get("/api/projects/{project_id}/runtime/showcase")
async def get_project_runtime_showcase(project_id: str, run_id: str | None = None) -> JSONResponse:
    return JSONResponse(load_runtime_showcase(project_id, run_id=run_id))


@app.get("/api/projects/{project_id}/runtime/runs")
async def get_project_runtime_runs(project_id: str, limit: int = 12) -> JSONResponse:
    return JSONResponse({"project": project_id, "runs": load_runtime_runs(project_id, limit=limit)})


@app.get("/api/backlogs")
async def get_backlogs(project: str = "versefina") -> JSONResponse:
    return JSONResponse({"project": project, "backlogs": load_backlogs(project)})


@app.get("/api/backlogs/{backlog_id}")
async def get_backlog_detail(backlog_id: str, project: str = "versefina") -> JSONResponse:
    return JSONResponse(load_backlog_detail(backlog_id, project))


@app.get("/api/backlogs/{backlog_id}/sprints/{sprint_id}")
async def get_sprint_detail(backlog_id: str, sprint_id: str, project: str = "versefina") -> JSONResponse:
    return JSONResponse(load_sprint_detail(backlog_id, sprint_id, project))


@app.get("/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}")
async def get_story_detail(backlog_id: str, sprint_id: str, story_id: str, project: str = "versefina") -> JSONResponse:
    return JSONResponse(load_story_detail(backlog_id, sprint_id, story_id, project))


@app.get("/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}/acceptance-review")
async def get_story_acceptance_review(backlog_id: str, sprint_id: str, story_id: str, project: str = "versefina") -> JSONResponse:
    return JSONResponse(
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": sprint_id,
            "story_id": story_id,
            "human_review": load_story_acceptance_review(project, backlog_id, sprint_id, story_id),
        }
    )


@app.post("/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}/acceptance-review")
async def post_story_acceptance_review(
    backlog_id: str,
    sprint_id: str,
    story_id: str,
    payload: StoryAcceptanceReviewPayload,
    project: str = "versefina",
) -> JSONResponse:
    return JSONResponse(save_story_acceptance_review(project, backlog_id, sprint_id, story_id, payload.model_dump()))


@app.get("/api/finahunt/runtime/runs")
async def get_finahunt_runtime_runs(limit: int = 12) -> JSONResponse:
    return JSONResponse({"runs": load_finahunt_runtime_runs(limit=limit)})


@app.get("/api/finahunt/runtime/showcase")
async def get_finahunt_runtime_showcase(run_id: str | None = None) -> JSONResponse:
    return JSONResponse(load_finahunt_runtime_showcase(run_id))


@app.get("/api/versefina/runtime/showcase")
async def get_versefina_runtime_showcase() -> JSONResponse:
    return JSONResponse(load_versefina_runtime_showcase())


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


def _runtime_dashboard_response(project_id: str):
    project = _get_project_registration(project_id)
    runtime_surface = project.runtime_surface
    if runtime_surface is None or not runtime_surface.dashboard_asset:
        return JSONResponse(status_code=404, content={"project": project_id, "error": "runtime_dashboard_not_configured"})
    return FileResponse(Path(__file__).parent / "static" / runtime_surface.dashboard_asset)


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
        "code_style_review_report": _read_first_available_text(
            archive_dir / "code_style_review" / "code_style_review_report.md",
            meta_dir / "code_style_review" / "code_style_review_report.md",
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
        "parsed_requirement": _read_first_available_text(
            archive_dir / "requirement" / "parsed_requirement.json",
            meta_dir / "requirement" / "parsed_requirement.json",
        ),
        "architecture_review_report": _read_first_available_text(
            archive_dir / "architecture_review" / "architecture_review_report.md",
            meta_dir / "architecture_review" / "architecture_review_report.md",
        ),
        "browser_qa_report": _read_first_available_text(
            archive_dir / "browser_qa" / "browser_qa_report.md",
            meta_dir / "browser_qa" / "browser_qa_report.md",
        ),
        "browser_session_manifest": _read_first_available_text(
            archive_dir / "browser_runtime" / "session.json",
            meta_dir / "browser_runtime" / "session.json",
        ),
        "intent_confirmation": _read_first_available_text(
            archive_dir / "requirement" / "intent_confirmation.md",
            meta_dir / "requirement" / "intent_confirmation.md",
        ),
        "delivery_report": _read_first_available_text(
            archive_dir / "delivery" / "story_delivery_report.md",
            meta_dir / "delivery" / "story_delivery_report.md",
        ),
        "result_report": _read_first_available_text(
            archive_dir / "delivery" / "story_result_report.md",
            meta_dir / "delivery" / "story_result_report.md",
        ),
        "completion_standard": _read_first_available_text(
            archive_dir / "delivery" / "story_completion_standard.md",
            meta_dir / "delivery" / "story_completion_standard.md",
        ),
    }
    completion = _extract_completion(payload)
    workflow = _extract_workflow(payload)
    return {
        "task_id": task_id,
        "audit_log": payload,
        "artifacts": artifacts,
        "events": load_task_events(task_id),
        "collaboration": _extract_collaboration(payload),
        "completion": completion,
        "workflow": workflow,
    }


def load_task_collaboration(task_id: str) -> dict[str, Any]:
    run_file = RUNS_DIR / f"prod_audit_{task_id}.json"
    payload: dict[str, Any] = {}
    if run_file.exists():
        payload = json.loads(run_file.read_text(encoding="utf-8"))
    collaboration = _extract_collaboration(payload)
    return {"task_id": task_id, **collaboration}


def compute_metrics(project_id: str = "versefina") -> dict[str, Any]:
    records = _collect_story_metrics_records(project_id)
    total_tasks = len(records)
    completed_records = [record for record in records if record["status"] in {"done", "failed"}]
    success_tasks = sum(1 for record in completed_records if record["status"] == "done")
    failed_tasks = sum(1 for record in completed_records if record["status"] == "failed")
    first_pass_successes = 0
    retry_rounds_total = 0
    blocking_issue_count = 0
    acceptance_total = 0
    acceptance_met = 0
    daily: dict[str, dict[str, float]] = {}
    for record in completed_records:
        fix_attempts = int(record.get("fix_attempts") or 0)
        retry_rounds_total += fix_attempts
        if record["status"] == "done" and fix_attempts == 0:
            first_pass_successes += 1
        blocking_issue_count += int(record.get("blocking_issue_count") or 0)
        acceptance_items = int(record.get("acceptance_total") or 0)
        acceptance_hits = int(record.get("acceptance_met") or 0)
        acceptance_total += acceptance_items
        acceptance_met += acceptance_hits
        created_at = _normalize_created_at(record.get("created_at"))
        if created_at:
            day_key = created_at[:10]
            bucket = daily.setdefault(day_key, {"total": 0, "success": 0, "retries": 0, "acceptance_total": 0, "acceptance_met": 0})
            bucket["total"] += 1
            bucket["success"] += 1 if record["status"] == "done" else 0
            bucket["retries"] += fix_attempts
            bucket["acceptance_total"] += acceptance_items
            bucket["acceptance_met"] += acceptance_hits

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
        "failed_tasks": failed_tasks,
        "first_pass_rate": round(first_pass_successes / len(completed_records) * 100, 1) if completed_records else 0.0,
        "avg_blocking_issues": round(blocking_issue_count / len(completed_records), 1) if completed_records else 0.0,
        "avg_retry_rounds": round(retry_rounds_total / len(completed_records), 1) if completed_records else 0.0,
        "acceptance_hit_rate": round(acceptance_met / acceptance_total * 100, 1) if acceptance_total else 0.0,
        "trend": {
            "labels": trend_labels,
            "success_rate": success_rate_trend,
            "avg_retry_rounds": retry_trend,
            "acceptance_hit_rate": acceptance_trend,
        },
    }


def _collect_story_metrics_records(project_id: str) -> list[dict[str, Any]]:
    story_index = _load_story_run_index(project_id)
    records: list[dict[str, Any]] = []
    tasks_dir = _get_tasks_dir(project_id)
    if not tasks_dir.exists():
        return records

    for backlog_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        overview_file = backlog_dir / "sprint_overview.md"
        if not overview_file.exists():
            continue
        for story_file in backlog_dir.rglob("S*.yaml"):
            payload = yaml_safe_load(story_file)
            story_id = str(payload.get("story_id") or payload.get("task_id") or story_file.stem.split("_", 1)[0])
            run_info = story_index.get(story_id) or {}
            record = {
                "story_id": story_id,
                "status": _story_status_from_run(run_info if run_info else None),
                "created_at": run_info.get("created_at"),
                "fix_attempts": 0,
                "blocking_issue_count": 0,
                "acceptance_total": len(payload.get("acceptance_criteria") or []),
                "acceptance_met": 0,
            }
            if run_info.get("source") == "agentsystem_audit" and run_info.get("task_id"):
                detail = load_task_detail(str(run_info["task_id"]))
                audit_log = detail.get("audit_log", {})
                result = audit_log.get("result", {}) if isinstance(audit_log, dict) else {}
                task_payload = result.get("task_payload", {}) if isinstance(result, dict) else {}
                acceptance_items = task_payload.get("acceptance_criteria", []) if isinstance(task_payload, dict) else []
                record.update(
                    {
                        "fix_attempts": int(result.get("fix_attempts") or 0),
                        "blocking_issue_count": len(result.get("blocking_issues") or []),
                        "acceptance_total": len(acceptance_items),
                        "acceptance_met": _count_met_acceptance_items(result.get("acceptance_report"), acceptance_items),
                    }
                )
            elif record["status"] == "done":
                record["acceptance_met"] = record["acceptance_total"]
            records.append(record)
    return records


def load_projects() -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for project in _build_project_registry().values():
        tasks_dir = project.tasks_dir
        backlogs = load_backlogs(project.id)
        projects.append(
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "available": tasks_dir.exists(),
                "backlog_count": len(backlogs),
                "has_runtime": project.has_runtime,
                "runtime_dashboard_path": f"/projects/{project.id}/runtime" if project.has_runtime else None,
            }
        )
    return projects


def load_backlogs(project_id: str = "versefina") -> list[dict[str, Any]]:
    backlogs: list[dict[str, Any]] = []
    tasks_dir = _get_tasks_dir(project_id)
    if not tasks_dir.exists():
        return backlogs
    for backlog_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        overview_file = backlog_dir / "sprint_overview.md"
        if not overview_file.exists():
            continue
        sprint_dirs = sorted(path for path in backlog_dir.iterdir() if path.is_dir() and path.name.startswith("sprint_"))
        story_count = sum(len(list(sprint_dir.rglob("S*.yaml"))) for sprint_dir in sprint_dirs)
        backlogs.append(
            {
                "project": project_id,
                "id": backlog_dir.name,
                "name": backlog_dir.name,
                "overview_path": str(overview_file),
                "sprint_count": len(sprint_dirs),
                "story_count": story_count,
            }
        )
    return backlogs


def load_backlog_detail(backlog_id: str, project_id: str = "versefina") -> dict[str, Any]:
    backlog_dir = _get_tasks_dir(project_id) / backlog_id
    sprint_dirs = sorted(path for path in backlog_dir.iterdir() if path.is_dir() and path.name.startswith("sprint_")) if backlog_dir.exists() else []
    return {
        "project": project_id,
        "id": backlog_id,
        "overview_markdown": _read_optional_text(backlog_dir / "sprint_overview.md"),
        "sprints": [_build_sprint_summary(backlog_id, sprint_dir, project_id) for sprint_dir in sprint_dirs],
    }


def load_sprint_detail(backlog_id: str, sprint_id: str, project_id: str = "versefina") -> dict[str, Any]:
    sprint_dir = _get_tasks_dir(project_id) / backlog_id / sprint_id
    story_index = _load_story_run_index(project_id)
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
        "project": project_id,
        "id": sprint_id,
        "sprint_plan_markdown": _read_optional_text(sprint_dir / "sprint_plan.md"),
        "quality_report_markdown": _read_optional_text(sprint_dir / "sprint_quality_report.md"),
        "execution_order": execution_order,
        "epics": epics,
    }


def load_story_detail(backlog_id: str, sprint_id: str, story_id: str, project_id: str = "versefina") -> dict[str, Any]:
    sprint_dir = _get_tasks_dir(project_id) / backlog_id / sprint_id
    story_file = next(sprint_dir.rglob(f"{story_id}_*.yaml"), None)
    payload = yaml_safe_load(story_file) if story_file else {}
    story_index = _load_story_run_index(project_id)
    run_info = story_index.get(story_id)
    if run_info and run_info.get("task_id"):
        task_detail = load_task_detail(str(run_info["task_id"]))
    else:
        task_detail = {
            "audit_log": {},
            "artifacts": {},
            "events": [],
            "business_validation": {
                "source": run_info.get("source") if run_info else None,
                "summary": run_info.get("summary") if run_info else None,
                "repository": run_info.get("repository") if run_info else None,
                "evidence": run_info.get("evidence") if run_info else [],
                "commit": run_info.get("commit") if run_info else None,
            },
        }
    payload = _merge_story_contract(payload, task_detail.get("audit_log") if isinstance(task_detail, dict) else {})
    human_review = load_story_acceptance_review(project_id, backlog_id, sprint_id, story_id)
    acceptance_template = _build_acceptance_template(payload, task_detail.get("completion") or {}, human_review)
    return {
        "project": project_id,
        "story_id": story_id,
        "story": payload,
        "story_file": str(story_file) if story_file else "",
        "status": _story_status_from_run(run_info),
        "latest_task_id": run_info.get("task_id") if run_info else None,
        "latest_run": run_info,
        "task_detail": task_detail,
        "workflow": task_detail.get("workflow") if isinstance(task_detail, dict) else {},
        "human_review": human_review,
        "acceptance_template": acceptance_template,
    }


def load_finahunt_runtime_runs(limit: int = 12) -> list[dict[str, Any]]:
    if not FINAHUNT_RUNTIME_DIR.exists():
        return []

    runs: list[dict[str, Any]] = []
    for run_dir in sorted(
        (path for path in FINAHUNT_RUNTIME_DIR.iterdir() if path.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        manifest = _read_json_file(run_dir / "manifest.json")
        if not isinstance(manifest, dict):
            manifest = {}
        summary = _read_json_file(run_dir / "result_warehouse_summary.json")
        if not isinstance(summary, dict):
            summary = {}
        run_id = str(manifest.get("run_id") or run_dir.name)
        runs.append(
            {
                "run_id": run_id,
                "artifact_dir": str(run_dir),
                "created_at": manifest.get("created_at"),
                "updated_at": manifest.get("updated_at"),
                "trace_id": manifest.get("trace_id"),
                "saved_artifact_count": len(summary.get("saved_artifacts") or []),
                "structured_result_card_count": _json_list_count(run_dir / "structured_result_cards.json"),
                "theme_heat_snapshot_count": _json_list_count(run_dir / "theme_heat_snapshots.json"),
                "low_position_count": _json_list_count(run_dir / "low_position_opportunities.json"),
                "fermenting_theme_count": _json_list_count(run_dir / "fermenting_theme_feed.json"),
                "today_focus_count": len((_read_json_file(run_dir / "daily_review.json") or {}).get("today_focus_page") or []),
            }
        )
    return runs[: max(limit, 1)]


def load_finahunt_runtime_showcase(run_id: str | None = None) -> dict[str, Any]:
    runs = load_finahunt_runtime_runs(limit=24)
    empty_stories = _build_finahunt_story_validation_cards({}, {})
    if not runs:
        return {
            "run_id": None,
            "runs": [],
            "stories": empty_stories,
            "manifest": {},
            "result_warehouse_summary": {},
            "inspection": _build_finahunt_inspection({}),
            "source_scout_candidates": [],
            "theme_clusters": [],
            "theme_candidate_mappings": [],
            "theme_purity_candidates": [],
            "fermentation_monitor": [],
            "theme_candidates": [],
            "structured_result_cards": [],
            "theme_heat_snapshots": [],
            "low_position_opportunities": [],
            "fermenting_theme_feed": [],
            "daily_review": {},
            "stats": {
                "story_count": len(empty_stories),
                "structured_result_card_count": 0,
                "theme_heat_snapshot_count": 0,
                "low_position_count": 0,
                "fermenting_theme_count": 0,
                "today_focus_count": 0,
                "watchlist_count": 0,
            },
        }

    selected_run = next((item for item in runs if item["run_id"] == run_id), None) if run_id else None
    if selected_run is None:
        selected_run = runs[0]

    run_dir = FINAHUNT_RUNTIME_DIR / str(selected_run["run_id"])
    manifest = _read_json_file(run_dir / "manifest.json")
    if not isinstance(manifest, dict):
        manifest = {}
    result_warehouse_summary = _read_json_file(run_dir / "result_warehouse_summary.json")
    if not isinstance(result_warehouse_summary, dict):
        result_warehouse_summary = {}
    raw_documents = _read_json_list(run_dir / "raw_documents.json")
    source_scout_candidates = _read_json_list(run_dir / "source_scout_candidates.json")
    normalized_documents = _read_json_list(run_dir / "normalized_documents.json")
    canonical_events = _read_json_list(run_dir / "canonical_events.json")
    theme_clusters = _read_json_list(run_dir / "theme_clusters.json")
    theme_candidate_mappings = _read_json_list(run_dir / "theme_candidate_mappings.json")
    theme_purity_candidates = _read_json_list(run_dir / "theme_purity_candidates.json")
    theme_candidates = _read_json_list(run_dir / "theme_candidates.json")
    fermentation_monitor = _read_json_list(run_dir / "fermentation_monitor.json")
    structured_result_cards = _read_json_list(run_dir / "structured_result_cards.json")
    theme_heat_snapshots = _read_json_list(run_dir / "theme_heat_snapshots.json")
    low_position_opportunities = _read_json_list(run_dir / "low_position_opportunities.json")
    fermenting_theme_feed = _read_json_list(run_dir / "fermenting_theme_feed.json")
    daily_review = _read_json_file(run_dir / "daily_review.json")
    if not isinstance(daily_review, dict):
        daily_review = {}

    artifact_counts = {
        "raw_documents": len(raw_documents),
        "source_scout_candidates": len(source_scout_candidates),
        "normalized_documents": len(normalized_documents),
        "canonical_events": len(canonical_events),
        "theme_clusters": len(theme_clusters),
        "theme_candidate_mappings": len(theme_candidate_mappings),
        "theme_purity_candidates": len(theme_purity_candidates),
        "theme_candidates": len(theme_candidates),
        "fermentation_monitor": len(fermentation_monitor),
        "structured_result_cards": len(structured_result_cards),
        "theme_heat_snapshots": len(theme_heat_snapshots),
        "low_position_opportunities": len(low_position_opportunities),
        "fermenting_theme_feed": len(fermenting_theme_feed),
        "result_warehouse": len(result_warehouse_summary.get("saved_artifacts") or []),
    }
    datasets = {
        "raw_documents": raw_documents,
        "source_scout_candidates": source_scout_candidates,
        "normalized_documents": normalized_documents,
        "canonical_events": canonical_events,
        "theme_clusters": theme_clusters,
        "theme_candidate_mappings": theme_candidate_mappings,
        "theme_purity_candidates": theme_purity_candidates,
        "theme_candidates": theme_candidates,
        "fermentation_monitor": fermentation_monitor,
        "structured_result_cards": structured_result_cards,
        "theme_heat_snapshots": theme_heat_snapshots,
        "low_position_opportunities": low_position_opportunities,
        "fermenting_theme_feed": fermenting_theme_feed,
        "daily_review": daily_review,
        "result_warehouse_summary": result_warehouse_summary,
    }
    stories = _build_finahunt_story_validation_cards(artifact_counts, datasets)

    return {
        "run_id": selected_run["run_id"],
        "runs": runs,
        "artifact_dir": selected_run["artifact_dir"],
        "manifest": manifest,
        "result_warehouse_summary": result_warehouse_summary,
        "raw_documents": raw_documents,
        "source_scout_candidates": source_scout_candidates,
        "normalized_documents": normalized_documents,
        "canonical_events": canonical_events,
        "theme_clusters": theme_clusters,
        "theme_candidate_mappings": theme_candidate_mappings,
        "theme_purity_candidates": theme_purity_candidates,
        "theme_candidates": theme_candidates,
        "fermentation_monitor": fermentation_monitor,
        "structured_result_cards": structured_result_cards,
        "theme_heat_snapshots": theme_heat_snapshots,
        "low_position_opportunities": low_position_opportunities,
        "fermenting_theme_feed": fermenting_theme_feed,
        "daily_review": daily_review,
        "inspection": _build_finahunt_inspection(datasets),
        "pipeline": _build_finahunt_pipeline(artifact_counts, daily_review),
        "stories": stories,
        "stats": {
            "story_count": len(stories),
            "raw_document_count": len(raw_documents),
            "normalized_document_count": len(normalized_documents),
            "canonical_event_count": len(canonical_events),
            "structured_result_card_count": len(structured_result_cards),
            "theme_heat_snapshot_count": len(theme_heat_snapshots),
            "low_position_count": len(low_position_opportunities),
            "fermenting_theme_count": len(fermenting_theme_feed),
            "today_focus_count": len(daily_review.get("today_focus_page") or []),
            "watchlist_count": len(daily_review.get("watchlist_event_page") or []),
        },
    }


def load_runtime_runs(project_id: str, limit: int = 12) -> list[dict[str, Any]]:
    project = _get_project_registration(project_id)
    runtime_surface = project.runtime_surface
    if runtime_surface is None or runtime_surface.runs_loader is None:
        return []
    return runtime_surface.runs_loader(limit)


def load_versefina_runtime_showcase() -> dict[str, Any]:
    return load_versefina_runtime_showcase_data(
        runtime_root=VERSEFINA_RUNTIME_DIR,
        tasks_dir=TASKS_DIR,
        story_status_registry=STORY_STATUS_REGISTRY,
        story_acceptance_review_registry=STORY_ACCEPTANCE_REVIEW_REGISTRY,
    )


def load_runtime_showcase(project_id: str, run_id: str | None = None) -> dict[str, Any]:
    project = _get_project_registration(project_id)
    runtime_surface = project.runtime_surface
    if runtime_surface is None or runtime_surface.showcase_loader is None:
        return {"project": project_id, "error": "runtime_showcase_not_configured"}
    if runtime_surface.runs_loader is None:
        return runtime_surface.showcase_loader()
    return runtime_surface.showcase_loader(run_id=run_id)


def _merge_story_contract(story_payload: dict[str, Any], audit_log: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(story_payload or {})
    runtime_task_payload: dict[str, Any] = {}
    if isinstance(audit_log, dict):
        result = audit_log.get("result", {})
        if isinstance(result, dict) and isinstance(result.get("task_payload"), dict):
            runtime_task_payload = dict(result["task_payload"])

    for key in ("story_inputs", "story_process", "story_outputs", "verification_basis"):
        current = payload.get(key)
        if isinstance(current, list) and any(str(item).strip() for item in current):
            payload[key] = [str(item).strip() for item in current if str(item).strip()]
            continue
        runtime_value = runtime_task_payload.get(key)
        if isinstance(runtime_value, list) and any(str(item).strip() for item in runtime_value):
            payload[key] = [str(item).strip() for item in runtime_value if str(item).strip()]
        else:
            payload[key] = []
    return payload


def _build_acceptance_template(
    story_payload: dict[str, Any],
    completion: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
) -> dict[str, Any]:
    completion = completion or {}
    automation_status = (
        "passed"
        if completion.get("acceptance_passed")
        else "needs_attention" if any(completion.get(key) is False for key in ("tests_passed", "review_passed", "code_acceptance_passed")) else "pending"
    )
    verdict = str((human_review or {}).get("verdict") or "pending_signoff")
    cards = [
        {
            "key": "input_review",
            "title": "1. 输入检查",
            "prompt": "确认这条 story 的输入是否写清楚，且与实际进入执行的内容一致。",
            "items": list(story_payload.get("story_inputs") or []),
            "status": "ready" if story_payload.get("story_inputs") else "missing",
        },
        {
            "key": "process_review",
            "title": "2. 过程检查",
            "prompt": "确认这条 story 是否写清楚了中间处理过程，并给出了足够的检查节点。",
            "items": list(story_payload.get("story_process") or []),
            "status": "ready" if story_payload.get("story_process") else "missing",
        },
        {
            "key": "output_review",
            "title": "3. 输出检查",
            "prompt": "确认预期输出是否明确，并且能与实际结果一一对照。",
            "items": list(story_payload.get("story_outputs") or []),
            "status": "ready" if story_payload.get("story_outputs") else "missing",
        },
        {
            "key": "verification_review",
            "title": "4. 验收依据检查",
            "prompt": "确认验收依据和 acceptance criteria 足以判断这条 story 是否真正完成。",
            "items": list(story_payload.get("verification_basis") or []) + list(story_payload.get("acceptance_criteria") or []),
            "status": "ready" if story_payload.get("verification_basis") else "missing",
        },
        {
            "key": "human_signoff",
            "title": "5. 人工签收",
            "prompt": "在检查输入、过程、输出和验收证据之后，记录最终检验结论。",
            "items": [
                f"自动化验收状态：{_review_status_label(automation_status)}",
                f"当前人工结论：{_review_status_label(verdict)}",
            ],
            "status": verdict if verdict != "pending_signoff" else "pending_signoff",
        },
    ]
    return {
        "template_version": "v1",
        "automation_status": automation_status,
        "cards": cards,
        "human_signoff_status": verdict,
    }


def _extract_completion(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    task_payload = result.get("task_payload", {}) if isinstance(result, dict) else {}
    return {
        "tests_passed": bool(result.get("test_passed")),
        "browser_qa_passed": result.get("browser_qa_passed"),
        "browser_qa_health_score": result.get("browser_qa_health_score"),
        "code_style_review_passed": bool(result.get("code_style_review_passed")),
        "review_passed": bool(result.get("review_passed")),
        "code_acceptance_passed": bool(result.get("code_acceptance_passed")),
        "acceptance_passed": bool(result.get("acceptance_passed")),
        "fix_attempts": int(result.get("fix_attempts") or 0),
        "blocking_issues": list(result.get("blocking_issues") or []),
        "acceptance_criteria": list(task_payload.get("acceptance_criteria") or []),
        "story_id": task_payload.get("story_id") or task_payload.get("task_id"),
        "task_name": task_payload.get("task_name") or task_payload.get("goal"),
    }


def _extract_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    task_payload = result.get("task_payload", {}) if isinstance(result.get("task_payload"), dict) else {}
    agent_manifest_ids = [str(item) for item in (result.get("workflow_agent_manifest_ids") or []) if item]
    return {
        "workflow_plugin_id": result.get("workflow_plugin_id") or task_payload.get("workflow_plugin") or task_payload.get("workflow_plugin_id"),
        "workflow_manifest_path": result.get("workflow_manifest_path"),
        "agent_manifest_ids": agent_manifest_ids,
        "agent_manifest_count": len(agent_manifest_ids),
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


def _build_sprint_summary(backlog_id: str, sprint_dir: Path, project_id: str = "versefina") -> dict[str, Any]:
    story_index = _load_story_run_index(project_id)
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
        "project": project_id,
        "id": sprint_dir.name,
        "name": sprint_dir.name,
        "backlog_id": backlog_id,
        "story_count": len(story_ids),
        "done_count": done,
        "failed_count": failed,
        "status": overall,
    }


def _load_story_run_index(project_id: str = "versefina") -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if RUNS_DIR.exists():
        for run_file in sorted(RUNS_DIR.glob("prod_audit_*.json"), key=lambda item: item.stat().st_mtime):
            try:
                payload = json.loads(run_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
            task_payload = result.get("task_payload", {}) if isinstance(result.get("task_payload"), dict) else {}
            task_project = task_payload.get("project") or task_payload.get("repository")
            if project_id == "versefina":
                if task_project and str(task_project) not in {"versefina", "agentsystem"}:
                    continue
            else:
                if str(task_project or "") != project_id:
                    continue
            story_id = task_payload.get("story_id") or task_payload.get("task_id")
            if not story_id:
                continue
            index[str(story_id)] = {
                "task_id": payload.get("task_id"),
                "success": bool(payload.get("success")),
                "status": "done" if payload.get("success") else "failed",
                "branch": payload.get("branch"),
                "commit": payload.get("commit"),
                "created_at": payload.get("created_at") or run_file.stat().st_mtime,
                "source": "agentsystem_audit",
            }
    for entry in _load_story_status_registry(project_id):
        story_id = entry.get("story_id")
        if not story_id:
            continue
        current = index.get(str(story_id))
        current_ts = _normalize_created_at(current.get("created_at")) if current else None
        entry_ts = _normalize_created_at(entry.get("verified_at"))
        if current_ts and entry_ts and current_ts > entry_ts:
            continue
        index[str(story_id)] = {
            "task_id": entry.get("task_id"),
            "success": entry.get("status") == "done",
            "status": entry.get("status") or "done",
            "branch": entry.get("branch"),
            "commit": entry.get("commit"),
            "created_at": entry.get("verified_at"),
            "source": entry.get("source") or "business_validation",
            "summary": entry.get("summary") or entry.get("validation_summary"),
            "repository": entry.get("repository"),
            "evidence": entry.get("evidence") or [],
        }
    return index


def _story_status_from_run(run_info: dict[str, Any] | None) -> str:
    if not run_info:
        return "not_started"
    if run_info.get("status"):
        return str(run_info.get("status"))
    return "done" if run_info.get("success") else "failed"


def _load_story_status_registry(project_id: str = "versefina") -> list[dict[str, Any]]:
    registry_path = _get_story_status_registry(project_id)
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = payload.get("stories") if isinstance(payload, dict) else []
    return entries if isinstance(entries, list) else []


def load_story_acceptance_review(project_id: str, backlog_id: str, sprint_id: str, story_id: str) -> dict[str, Any] | None:
    for review in _load_story_acceptance_reviews(project_id):
        if (
            str(review.get("backlog_id")) == backlog_id
            and str(review.get("sprint_id")) == sprint_id
            and str(review.get("story_id")) == story_id
        ):
            return review
    return None


def save_story_acceptance_review(
    project_id: str,
    backlog_id: str,
    sprint_id: str,
    story_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    review = {
        "project": project_id,
        "backlog_id": backlog_id,
        "sprint_id": sprint_id,
        "story_id": story_id,
        "reviewer": str(payload.get("reviewer") or "").strip(),
        "verdict": str(payload.get("verdict") or "needs_followup").strip(),
        "summary": str(payload.get("summary") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "run_id": str(payload.get("run_id") or "").strip() or None,
        "checked_at": str(payload.get("checked_at") or datetime.now().isoformat(timespec="seconds")),
        "template_version": "v1",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    registry_path = _get_story_acceptance_review_registry(project_id)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_story_acceptance_reviews(project_id)
    filtered = [
        item
        for item in existing
        if not (
            str(item.get("backlog_id")) == backlog_id
            and str(item.get("sprint_id")) == sprint_id
            and str(item.get("story_id")) == story_id
        )
    ]
    filtered.append(review)
    registry_path.write_text(json.dumps({"reviews": filtered}, ensure_ascii=False, indent=2), encoding="utf-8")
    return review


def _load_story_acceptance_reviews(project_id: str = "versefina") -> list[dict[str, Any]]:
    registry_path = _get_story_acceptance_review_registry(project_id)
    if not registry_path.exists():
        return []
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = payload.get("reviews") if isinstance(payload, dict) else []
    return entries if isinstance(entries, list) else []


def _get_tasks_dir(project_id: str) -> Path:
    return _get_project_registration(project_id).tasks_dir


def _get_story_status_registry(project_id: str) -> Path:
    return _get_project_registration(project_id).story_status_registry


def _get_story_acceptance_review_registry(project_id: str) -> Path:
    return _get_project_registration(project_id).story_acceptance_review_registry


def _get_project_registration(project_id: str) -> ProjectRegistration:
    registry = _build_project_registry()
    return registry.get(project_id) or registry["versefina"]


def _build_project_registry() -> dict[str, ProjectRegistration]:
    return {
        "versefina": ProjectRegistration(
            id="versefina",
            name="Versefina",
            description="Agent-native financial world delivery backlog",
            tasks_dir=TASKS_DIR,
            story_status_registry=STORY_STATUS_REGISTRY,
            story_acceptance_review_registry=STORY_ACCEPTANCE_REVIEW_REGISTRY,
            runtime_surface=RuntimeSurface(
                dashboard_asset="versefina_runtime.html",
                showcase_loader=load_versefina_runtime_showcase,
            ),
        ),
        "finahunt": ProjectRegistration(
            id="finahunt",
            name="Finahunt",
            description="Financial news cognition system MVP backlog",
            tasks_dir=FINAHUNT_TASKS_DIR,
            story_status_registry=FINAHUNT_STORY_STATUS_REGISTRY,
            story_acceptance_review_registry=FINAHUNT_STORY_ACCEPTANCE_REVIEW_REGISTRY,
            runtime_surface=RuntimeSurface(
                dashboard_asset="finahunt_runtime.html",
                showcase_loader=load_finahunt_runtime_showcase,
                runs_loader=load_finahunt_runtime_runs,
            ),
        ),
    }


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


def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    payload = _read_json_file(path)
    return payload if isinstance(payload, list) else []


def _json_list_count(path: Path) -> int:
    payload = _read_json_file(path)
    return len(payload) if isinstance(payload, list) else 0


def _load_finahunt_sprint2_story_cards(artifact_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    artifact_counts = artifact_counts or {}
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith("S2-")
    }
    story_output_map = {
        "S2-001": ("theme_candidates", "Theme candidate inputs"),
        "S2-002": ("structured_result_cards", "Catalyst typing in cards"),
        "S2-003": ("theme_heat_snapshots", "Strength and timeliness scoring"),
        "S2-004": ("theme_candidates", "Theme candidate aggregation"),
        "S2-005": ("structured_result_cards", "Theme to asset linkage"),
        "S2-006": ("structured_result_cards", "Structured result cards"),
        "S2-007": ("result_warehouse", "Result warehouse"),
        "S2-008": ("theme_heat_snapshots", "Theme heat snapshots"),
        "S2-009": ("fermenting_theme_feed", "Fermenting theme feed"),
    }
    cards: list[dict[str, Any]] = []
    for story_id in [f"S2-00{index}" for index in range(1, 10)]:
        entry = registry_by_story.get(story_id, {})
        output_key, output_label = story_output_map.get(story_id, ("unknown", "Unknown output"))
        cards.append(
            {
                "story_id": story_id,
                "status": entry.get("status") or "not_started",
                "summary": entry.get("summary") or entry.get("validation_summary") or "",
                "delivery_report": entry.get("delivery_report"),
                "evidence": entry.get("evidence") or [],
                "output_key": output_key,
                "output_label": output_label,
                "output_ready": bool(artifact_counts.get(output_key)),
                "output_count": int(artifact_counts.get(output_key) or 0),
            }
        )
    return cards


def _build_finahunt_story_validation_cards(
    artifact_counts: dict[str, int],
    datasets: dict[str, Any],
) -> list[dict[str, Any]]:
    spec_by_story = _load_finahunt_sprint2_story_specs()
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith("S2-")
    }
    io_map = {
        "S2-001": ("canonical_events", "theme_candidates", "确认候选题材能回溯到具体事件与证据链。"),
        "S2-002": ("canonical_events", "structured_result_cards", "确认结构化结果里已经体现催化解释，而不是只有题材名。"),
        "S2-003": ("theme_candidates", "theme_heat_snapshots", "确认热度快照已经吸收强度与时效性信息。"),
        "S2-004": ("canonical_events", "theme_candidates", "确认多个事件信号被组织成同一个候选题材。"),
        "S2-005": ("theme_candidates", "structured_result_cards", "确认输出里能看见题材到资产的客观映射。"),
        "S2-006": ("theme_candidates", "structured_result_cards", "确认结果卡包含摘要、证据和风险提示。"),
        "S2-007": ("structured_result_cards", "result_warehouse_summary", "确认产物已写入结果仓库，不只是内存数据。"),
        "S2-008": ("theme_candidates", "theme_heat_snapshots", "确认快照里有 score_breakdown 与 fermentation stage。"),
        "S2-009": ("theme_heat_snapshots", "fermenting_theme_feed", "确认最终 feed 可以直接用于观察与验收。"),
    }

    cards: list[dict[str, Any]] = []
    for story_id in [f"S2-00{index}" for index in range(1, 10)]:
        spec = spec_by_story.get(story_id, {})
        registry_entry = registry_by_story.get(story_id, {})
        human_review = load_story_acceptance_review("finahunt", "backlog_v1", "sprint_2_catalyst_mining_core", story_id)
        input_key, output_key, validation_hint = io_map.get(story_id, ("", "", ""))
        input_value = datasets.get(input_key)
        output_value = datasets.get(output_key)
        completion = {
            "acceptance_passed": registry_entry.get("status") == "done",
            "tests_passed": registry_entry.get("status") == "done",
            "review_passed": registry_entry.get("status") == "done",
            "code_acceptance_passed": registry_entry.get("status") == "done",
        }
        cards.append(
            {
                "story_id": story_id,
                "task_name": spec.get("task_name") or story_id,
                "status": registry_entry.get("status") or "not_started",
                "summary": registry_entry.get("summary") or registry_entry.get("validation_summary") or "",
                "delivery_report": registry_entry.get("delivery_report"),
                "evidence": registry_entry.get("evidence") or [],
                "acceptance_criteria": spec.get("acceptance_criteria") or [],
                "story_inputs": spec.get("story_inputs") or [],
                "story_process": spec.get("story_process") or [],
                "story_outputs": spec.get("story_outputs") or [],
                "verification_basis": spec.get("verification_basis") or [],
                "input_label": _label_for_finahunt_dataset(input_key),
                "input_count": _count_dataset_items(input_value),
                "input_sample": _sample_dataset_item(input_value),
                "output_label": _label_for_finahunt_dataset(output_key),
                "output_count": _count_dataset_items(output_value),
                "output_sample": _sample_dataset_item(output_value),
                "output_ready": bool(artifact_counts.get(output_key)),
                "validation_hint": validation_hint,
                "human_review": human_review,
                "acceptance_template": _build_acceptance_template(spec, completion, human_review),
            }
        )
    return cards


def _load_finahunt_sprint2_story_specs() -> dict[str, dict[str, Any]]:
    sprint_dir = _get_tasks_dir("finahunt") / "backlog_v1" / "sprint_2_catalyst_mining_core"
    if not sprint_dir.exists():
        return {}
    specs: dict[str, dict[str, Any]] = {}
    for story_file in sprint_dir.rglob("S2-*.yaml"):
        payload = yaml_safe_load(story_file)
        story_id = str(payload.get("story_id") or payload.get("task_id") or "")
        if story_id:
            specs[story_id] = payload
    return specs


def _label_for_finahunt_dataset(key: str) -> str:
    labels = {
        "raw_documents": "原始资讯",
        "normalized_documents": "标准化资讯",
        "canonical_events": "归一事件",
        "theme_candidates": "题材候选",
        "structured_result_cards": "结构化结果卡",
        "theme_heat_snapshots": "题材热度快照",
        "low_position_opportunities": "低位挖掘结果",
        "fermenting_theme_feed": "发酵题材结果流",
        "result_warehouse_summary": "结果仓库摘要",
    }
    return labels.get(key, key or "-")


def _count_dataset_items(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        if isinstance(value.get("saved_artifacts"), list):
            return len(value["saved_artifacts"])
        return len(value)
    return 0


def _sample_dataset_item(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, dict) and isinstance(value.get("saved_artifacts"), list):
        return value["saved_artifacts"][0] if value["saved_artifacts"] else None
    return value


def _build_finahunt_inspection(datasets: dict[str, Any]) -> dict[str, Any]:
    low_position = datasets.get("low_position_opportunities")
    return {
        "first_input_label": "原始资讯输入",
        "first_input_sample": _sample_dataset_item(datasets.get("raw_documents")),
        "last_output_label": "低位挖掘结果" if _count_dataset_items(low_position) else "最终发酵题材结果流",
        "last_output_sample": _sample_dataset_item(low_position) if _count_dataset_items(low_position) else _sample_dataset_item(datasets.get("fermenting_theme_feed")),
    }


def _build_finahunt_pipeline(artifact_counts: dict[str, int], daily_review: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"stage": "raw_documents", "label": "资讯源运行时", "count": int(artifact_counts.get("raw_documents") or 0)},
        {"stage": "normalized_documents", "label": "资讯标准化", "count": int(artifact_counts.get("normalized_documents") or 0)},
        {"stage": "canonical_events", "label": "事件归一", "count": int(artifact_counts.get("canonical_events") or 0)},
        {"stage": "theme_candidates", "label": "题材候选聚合", "count": int(artifact_counts.get("theme_candidates") or 0)},
        {"stage": "structured_result_cards", "label": "结构化结果卡", "count": int(artifact_counts.get("structured_result_cards") or 0)},
        {"stage": "theme_heat_snapshots", "label": "题材热度快照", "count": int(artifact_counts.get("theme_heat_snapshots") or 0)},
        {"stage": "low_position_opportunities", "label": "低位挖掘", "count": int(artifact_counts.get("low_position_opportunities") or 0)},
        {"stage": "fermenting_theme_feed", "label": "发酵题材结果流", "count": int(artifact_counts.get("fermenting_theme_feed") or 0)},
        {"stage": "daily_review", "label": "日终复盘", "count": len(daily_review.get("today_focus_page") or [])},
    ]


FINAHUNT_SHOWCASE_STORY_ORDER: list[dict[str, str]] = [
    {"story_id": "S2-001", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "theme_candidates", "validation_hint": "Confirm theme candidates can be traced back to specific events and evidence chains."},
    {"story_id": "S2-002", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "structured_result_cards", "validation_hint": "Confirm structured cards preserve catalyst typing rather than only theme names."},
    {"story_id": "S2-003", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "theme_heat_snapshots", "validation_hint": "Confirm heat snapshots absorb strength and timeliness scoring."},
    {"story_id": "S2-004", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "theme_candidates", "validation_hint": "Confirm multiple events are aggregated into reusable theme candidates."},
    {"story_id": "S2-005", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "structured_result_cards", "validation_hint": "Confirm outputs expose objective theme-to-asset mapping evidence."},
    {"story_id": "S2-006", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "structured_result_cards", "validation_hint": "Confirm cards contain summary, evidence, and risk notice."},
    {"story_id": "S2-007", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "structured_result_cards", "output_key": "result_warehouse_summary", "validation_hint": "Confirm results are persisted into the warehouse rather than staying in memory only."},
    {"story_id": "S2-008", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "theme_heat_snapshots", "validation_hint": "Confirm snapshots include scoring breakdowns and fermentation stage fields."},
    {"story_id": "S2-009", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_heat_snapshots", "output_key": "fermenting_theme_feed", "validation_hint": "Confirm the final feed is directly usable for observation and acceptance."},
    {"story_id": "S2-010", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "low_position_opportunities", "validation_hint": "Confirm low-consensus theme clustering produces core narratives and timing anchors."},
    {"story_id": "S2-011", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "low_position_opportunities", "validation_hint": "Confirm candidate mappings include purity scoring, breakdowns, and risk flags."},
    {"story_id": "S2-012", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_heat_snapshots", "output_key": "low_position_opportunities", "validation_hint": "Confirm research priority scores combine catalyst, continuity, purity, and fermentation signals."},
    {"story_id": "S2-013", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "low_position_opportunities", "output_key": "daily_review", "validation_hint": "Confirm low-position research cards surface narrative, candidates, evidence, and risk notes for review."},
    {"story_id": "S2A-001", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "raw_documents", "output_key": "source_scout_candidates", "validation_hint": "Confirm early-catalyst clues are prioritized and remain traceable to public sources."},
    {"story_id": "S2A-002", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "source_scout_candidates", "output_key": "canonical_events", "validation_hint": "Confirm event extraction preserves catalyst boundary, continuity hints, and source priority."},
    {"story_id": "S2A-003", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "canonical_events", "output_key": "theme_clusters", "validation_hint": "Confirm scattered events merge into unified theme clusters with anchor terms and noise labels."},
    {"story_id": "S2A-004", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_clusters", "output_key": "theme_candidate_mappings", "validation_hint": "Confirm theme clusters produce ranked candidate mappings with reasons and evidence references."},
    {"story_id": "S2A-005", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_candidate_mappings", "output_key": "theme_purity_candidates", "validation_hint": "Confirm candidate pools receive accepted/watch/filter purity decisions with explanations."},
    {"story_id": "S2A-006", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_candidates", "output_key": "fermentation_monitor", "validation_hint": "Confirm fermentation monitoring outputs phase, platform spread, and reignition strength."},
]


def _load_finahunt_sprint2_story_cards(artifact_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    artifact_counts = artifact_counts or {}
    story_index = _load_story_run_index("finahunt")
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith(("S2-", "S2A-"))
    }
    cards: list[dict[str, Any]] = []
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        story_id = config["story_id"]
        entry = registry_by_story.get(story_id, {})
        run_info = story_index.get(story_id, {})
        output_key = config["output_key"]
        cards.append(
            {
                "story_id": story_id,
                "sprint_id": config["sprint_id"],
                "status": run_info.get("status") or entry.get("status") or "not_started",
                "summary": run_info.get("summary") or entry.get("summary") or entry.get("validation_summary") or "",
                "delivery_report": entry.get("delivery_report"),
                "evidence": entry.get("evidence") or [],
                "output_key": output_key,
                "output_label": _label_for_finahunt_dataset(output_key),
                "output_ready": bool(artifact_counts.get(output_key)),
                "output_count": int(artifact_counts.get(output_key) or 0),
            }
        )
    return cards


def _build_finahunt_story_validation_cards(
    artifact_counts: dict[str, int],
    datasets: dict[str, Any],
) -> list[dict[str, Any]]:
    spec_by_story = _load_finahunt_sprint2_story_specs()
    story_index = _load_story_run_index("finahunt")
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith(("S2-", "S2A-"))
    }

    cards: list[dict[str, Any]] = []
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        story_id = config["story_id"]
        spec = spec_by_story.get(story_id, {})
        registry_entry = registry_by_story.get(story_id, {})
        run_info = story_index.get(story_id, {})
        human_review = load_story_acceptance_review("finahunt", "backlog_v1", config["sprint_id"], story_id)
        input_key = config["input_key"]
        output_key = config["output_key"]
        input_value = datasets.get(input_key)
        output_value = datasets.get(output_key)
        completion = {
            "acceptance_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "tests_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "review_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "code_acceptance_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
        }
        cards.append(
            {
                "story_id": story_id,
                "sprint_id": config["sprint_id"],
                "sprint_label": spec.get("sprint") or config["sprint_id"],
                "task_name": spec.get("task_name") or story_id,
                "status": run_info.get("status") or registry_entry.get("status") or "not_started",
                "summary": run_info.get("summary") or registry_entry.get("summary") or registry_entry.get("validation_summary") or "",
                "delivery_report": registry_entry.get("delivery_report"),
                "evidence": registry_entry.get("evidence") or [],
                "acceptance_criteria": spec.get("acceptance_criteria") or [],
                "story_inputs": spec.get("story_inputs") or [],
                "story_process": spec.get("story_process") or [],
                "story_outputs": spec.get("story_outputs") or [],
                "verification_basis": spec.get("verification_basis") or [],
                "input_label": _label_for_finahunt_dataset(input_key),
                "input_count": _count_dataset_items(input_value),
                "input_sample": _sample_dataset_item(input_value),
                "output_label": _label_for_finahunt_dataset(output_key),
                "output_count": _count_dataset_items(output_value),
                "output_sample": _sample_dataset_item(output_value),
                "output_ready": bool(artifact_counts.get(output_key)),
                "validation_hint": config["validation_hint"],
                "human_review": human_review,
                "acceptance_template": _build_acceptance_template(spec, completion, human_review),
            }
        )
    return cards


def _load_finahunt_sprint2_story_specs() -> dict[str, dict[str, Any]]:
    backlog_dir = _get_tasks_dir("finahunt") / "backlog_v1"
    specs: dict[str, dict[str, Any]] = {}
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        sprint_dir = backlog_dir / config["sprint_id"]
        if not sprint_dir.exists():
            continue
        story_file = next(sprint_dir.rglob(f"{config['story_id']}_*.yaml"), None)
        payload = yaml_safe_load(story_file)
        story_id = str(payload.get("story_id") or payload.get("task_id") or "")
        if story_id:
            specs[story_id] = payload
    return specs


def _label_for_finahunt_dataset(key: str) -> str:
    labels = {
        "raw_documents": "原始资讯",
        "source_scout_candidates": "早期催化候选集",
        "normalized_documents": "标准化资讯",
        "canonical_events": "归一事件",
        "theme_clusters": "题材事件簇",
        "theme_candidate_mappings": "候选标的映射",
        "theme_purity_candidates": "正宗度评判池",
        "theme_candidates": "题材候选",
        "fermentation_monitor": "发酵监控结果",
        "structured_result_cards": "结构化结果卡",
        "theme_heat_snapshots": "题材热度快照",
        "low_position_opportunities": "低位挖掘结果",
        "fermenting_theme_feed": "发酵题材结果流",
        "result_warehouse_summary": "结果仓库摘要",
    }
    return labels.get(key, key or "-")


def _build_finahunt_pipeline(artifact_counts: dict[str, int], daily_review: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"stage": "raw_documents", "label": "资讯源运行时", "count": int(artifact_counts.get("raw_documents") or 0)},
        {"stage": "source_scout_candidates", "label": "早期催化候选集", "count": int(artifact_counts.get("source_scout_candidates") or 0)},
        {"stage": "normalized_documents", "label": "资讯标准化", "count": int(artifact_counts.get("normalized_documents") or 0)},
        {"stage": "canonical_events", "label": "事件归一", "count": int(artifact_counts.get("canonical_events") or 0)},
        {"stage": "theme_clusters", "label": "题材簇归一", "count": int(artifact_counts.get("theme_clusters") or 0)},
        {"stage": "theme_candidate_mappings", "label": "候选标的映射", "count": int(artifact_counts.get("theme_candidate_mappings") or 0)},
        {"stage": "theme_purity_candidates", "label": "正宗度评判", "count": int(artifact_counts.get("theme_purity_candidates") or 0)},
        {"stage": "theme_candidates", "label": "题材候选聚合", "count": int(artifact_counts.get("theme_candidates") or 0)},
        {"stage": "fermentation_monitor", "label": "发酵监控", "count": int(artifact_counts.get("fermentation_monitor") or 0)},
        {"stage": "structured_result_cards", "label": "结构化结果卡", "count": int(artifact_counts.get("structured_result_cards") or 0)},
        {"stage": "theme_heat_snapshots", "label": "题材热度快照", "count": int(artifact_counts.get("theme_heat_snapshots") or 0)},
        {"stage": "low_position_opportunities", "label": "低位挖掘", "count": int(artifact_counts.get("low_position_opportunities") or 0)},
        {"stage": "fermenting_theme_feed", "label": "发酵题材结果流", "count": int(artifact_counts.get("fermenting_theme_feed") or 0)},
        {"stage": "daily_review", "label": "日终复盘", "count": len(daily_review.get("today_focus_page") or [])},
    ]


FINAHUNT_SHOWCASE_STORY_ORDER: list[dict[str, str]] = [
    {"story_id": "S2-001", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "theme_candidates", "validation_hint": "Confirm theme candidates can be traced back to specific events and evidence chains."},
    {"story_id": "S2-002", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "structured_result_cards", "validation_hint": "Confirm structured cards preserve catalyst typing rather than only theme names."},
    {"story_id": "S2-003", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "theme_heat_snapshots", "validation_hint": "Confirm heat snapshots absorb strength and timeliness scoring."},
    {"story_id": "S2-004", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "canonical_events", "output_key": "theme_candidates", "validation_hint": "Confirm multiple events are aggregated into reusable theme candidates."},
    {"story_id": "S2-005", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "structured_result_cards", "validation_hint": "Confirm outputs expose objective theme-to-asset mapping evidence."},
    {"story_id": "S2-006", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "structured_result_cards", "validation_hint": "Confirm cards contain summary, evidence, and risk notice."},
    {"story_id": "S2-007", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "structured_result_cards", "output_key": "result_warehouse_summary", "validation_hint": "Confirm results are persisted into the warehouse rather than staying in memory only."},
    {"story_id": "S2-008", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "theme_heat_snapshots", "validation_hint": "Confirm snapshots include scoring breakdowns and fermentation stage fields."},
    {"story_id": "S2-009", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_heat_snapshots", "output_key": "fermenting_theme_feed", "validation_hint": "Confirm the final feed is directly usable for observation and acceptance."},
    {"story_id": "S2-010", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "low_position_opportunities", "validation_hint": "Confirm low-consensus theme clustering produces core narratives and timing anchors."},
    {"story_id": "S2-011", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_candidates", "output_key": "low_position_opportunities", "validation_hint": "Confirm candidate mappings include purity scoring, breakdowns, and risk flags."},
    {"story_id": "S2-012", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "theme_heat_snapshots", "output_key": "low_position_opportunities", "validation_hint": "Confirm research priority scores combine catalyst, continuity, purity, and fermentation signals."},
    {"story_id": "S2-013", "sprint_id": "sprint_2_catalyst_mining_core", "input_key": "low_position_opportunities", "output_key": "daily_review", "validation_hint": "Confirm low-position research cards surface narrative, candidates, evidence, and risk notes for review."},
    {"story_id": "S2A-001", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "raw_documents", "output_key": "source_scout_candidates", "validation_hint": "Confirm early-catalyst clues are prioritized and remain traceable to public sources."},
    {"story_id": "S2A-002", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "source_scout_candidates", "output_key": "canonical_events", "validation_hint": "Confirm event extraction preserves catalyst boundary, continuity hints, and source priority."},
    {"story_id": "S2A-003", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "canonical_events", "output_key": "theme_clusters", "validation_hint": "Confirm scattered events merge into unified theme clusters with anchor terms and noise labels."},
    {"story_id": "S2A-004", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_clusters", "output_key": "theme_candidate_mappings", "validation_hint": "Confirm theme clusters produce ranked candidate mappings with reasons and evidence references."},
    {"story_id": "S2A-005", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_candidate_mappings", "output_key": "theme_purity_candidates", "validation_hint": "Confirm candidate pools receive accepted/watch/filter purity decisions with explanations."},
    {"story_id": "S2A-006", "sprint_id": "sprint_2a_early_theme_discovery_engine", "input_key": "theme_candidates", "output_key": "fermentation_monitor", "validation_hint": "Confirm fermentation monitoring outputs phase, platform spread, and reignition strength."},
]


def _load_finahunt_sprint2_story_cards(artifact_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    artifact_counts = artifact_counts or {}
    story_index = _load_story_run_index("finahunt")
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith(("S2-", "S2A-"))
    }
    cards: list[dict[str, Any]] = []
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        story_id = config["story_id"]
        entry = registry_by_story.get(story_id, {})
        run_info = story_index.get(story_id, {})
        output_key = config["output_key"]
        cards.append(
            {
                "story_id": story_id,
                "sprint_id": config["sprint_id"],
                "status": run_info.get("status") or entry.get("status") or "not_started",
                "summary": run_info.get("summary") or entry.get("summary") or entry.get("validation_summary") or "",
                "delivery_report": entry.get("delivery_report"),
                "evidence": entry.get("evidence") or [],
                "output_key": output_key,
                "output_label": _label_for_finahunt_dataset(output_key),
                "output_ready": bool(artifact_counts.get(output_key)),
                "output_count": int(artifact_counts.get(output_key) or 0),
            }
        )
    return cards


def _build_finahunt_story_validation_cards(
    artifact_counts: dict[str, int],
    datasets: dict[str, Any],
) -> list[dict[str, Any]]:
    spec_by_story = _load_finahunt_sprint2_story_specs()
    story_index = _load_story_run_index("finahunt")
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry("finahunt")
        if str(entry.get("story_id") or "").startswith(("S2-", "S2A-"))
    }

    cards: list[dict[str, Any]] = []
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        story_id = config["story_id"]
        spec = spec_by_story.get(story_id, {})
        registry_entry = registry_by_story.get(story_id, {})
        run_info = story_index.get(story_id, {})
        human_review = load_story_acceptance_review("finahunt", "backlog_v1", config["sprint_id"], story_id)
        input_key = config["input_key"]
        output_key = config["output_key"]
        input_value = datasets.get(input_key)
        output_value = datasets.get(output_key)
        completion = {
            "acceptance_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "tests_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "review_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
            "code_acceptance_passed": run_info.get("status") == "done" or registry_entry.get("status") == "done",
        }
        cards.append(
            {
                "story_id": story_id,
                "sprint_id": config["sprint_id"],
                "sprint_label": spec.get("sprint") or config["sprint_id"],
                "task_name": spec.get("task_name") or story_id,
                "status": run_info.get("status") or registry_entry.get("status") or "not_started",
                "summary": run_info.get("summary") or registry_entry.get("summary") or registry_entry.get("validation_summary") or "",
                "delivery_report": registry_entry.get("delivery_report"),
                "evidence": registry_entry.get("evidence") or [],
                "acceptance_criteria": spec.get("acceptance_criteria") or [],
                "story_inputs": spec.get("story_inputs") or [],
                "story_process": spec.get("story_process") or [],
                "story_outputs": spec.get("story_outputs") or [],
                "verification_basis": spec.get("verification_basis") or [],
                "input_label": _label_for_finahunt_dataset(input_key),
                "input_count": _count_dataset_items(input_value),
                "input_sample": _sample_dataset_item(input_value),
                "output_label": _label_for_finahunt_dataset(output_key),
                "output_count": _count_dataset_items(output_value),
                "output_sample": _sample_dataset_item(output_value),
                "output_ready": bool(artifact_counts.get(output_key)),
                "validation_hint": config["validation_hint"],
                "human_review": human_review,
                "acceptance_template": _build_acceptance_template(spec, completion, human_review),
            }
        )
    return cards


def _load_finahunt_sprint2_story_specs() -> dict[str, dict[str, Any]]:
    backlog_dir = _get_tasks_dir("finahunt") / "backlog_v1"
    specs: dict[str, dict[str, Any]] = {}
    for config in FINAHUNT_SHOWCASE_STORY_ORDER:
        sprint_dir = backlog_dir / config["sprint_id"]
        if not sprint_dir.exists():
            continue
        story_file = next(sprint_dir.rglob(f"{config['story_id']}_*.yaml"), None)
        payload = yaml_safe_load(story_file)
        story_id = str(payload.get("story_id") or payload.get("task_id") or "")
        if story_id:
            specs[story_id] = payload
    return specs


def _label_for_finahunt_dataset(key: str) -> str:
    labels = {
        "raw_documents": "原始资讯",
        "source_scout_candidates": "早期催化候选集",
        "normalized_documents": "标准化资讯",
        "canonical_events": "归一事件",
        "theme_clusters": "题材事件簇",
        "theme_candidate_mappings": "候选标的映射",
        "theme_purity_candidates": "正宗度评判池",
        "theme_candidates": "题材候选",
        "fermentation_monitor": "发酵监控结果",
        "structured_result_cards": "结构化结果卡",
        "theme_heat_snapshots": "题材热度快照",
        "low_position_opportunities": "低位挖掘结果",
        "fermenting_theme_feed": "发酵题材结果流",
        "result_warehouse_summary": "结果仓库摘要",
    }
    return labels.get(key, key or "-")


def _build_finahunt_pipeline(artifact_counts: dict[str, int], daily_review: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"stage": "raw_documents", "label": "资讯源运行时", "count": int(artifact_counts.get("raw_documents") or 0)},
        {"stage": "source_scout_candidates", "label": "早期催化候选集", "count": int(artifact_counts.get("source_scout_candidates") or 0)},
        {"stage": "normalized_documents", "label": "资讯标准化", "count": int(artifact_counts.get("normalized_documents") or 0)},
        {"stage": "canonical_events", "label": "事件归一", "count": int(artifact_counts.get("canonical_events") or 0)},
        {"stage": "theme_clusters", "label": "题材簇归一", "count": int(artifact_counts.get("theme_clusters") or 0)},
        {"stage": "theme_candidate_mappings", "label": "候选标的映射", "count": int(artifact_counts.get("theme_candidate_mappings") or 0)},
        {"stage": "theme_purity_candidates", "label": "正宗度评判", "count": int(artifact_counts.get("theme_purity_candidates") or 0)},
        {"stage": "theme_candidates", "label": "题材候选聚合", "count": int(artifact_counts.get("theme_candidates") or 0)},
        {"stage": "fermentation_monitor", "label": "发酵监控", "count": int(artifact_counts.get("fermentation_monitor") or 0)},
        {"stage": "structured_result_cards", "label": "结构化结果卡", "count": int(artifact_counts.get("structured_result_cards") or 0)},
        {"stage": "theme_heat_snapshots", "label": "题材热度快照", "count": int(artifact_counts.get("theme_heat_snapshots") or 0)},
        {"stage": "low_position_opportunities", "label": "低位挖掘", "count": int(artifact_counts.get("low_position_opportunities") or 0)},
        {"stage": "fermenting_theme_feed", "label": "发酵题材结果流", "count": int(artifact_counts.get("fermenting_theme_feed") or 0)},
        {"stage": "daily_review", "label": "日终复盘", "count": len(daily_review.get("today_focus_page") or [])},
    ]


def _review_status_label(status: str | None) -> str:
    labels = {
        "done": "已完成",
        "success": "已通过",
        "approved": "已签收",
        "passed": "已通过",
        "failed": "失败",
        "rejected": "已拒绝",
        "not_started": "未开始",
        "pending": "待执行",
        "pending_signoff": "待人工签收",
        "partial": "部分完成",
        "running": "进行中",
        "needs_followup": "待跟进",
        "needs_attention": "需关注",
        "ready": "已就绪",
        "missing": "缺失",
    }
    return labels.get(str(status or "").strip(), str(status or "-"))
