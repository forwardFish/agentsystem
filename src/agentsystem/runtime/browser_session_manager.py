from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class BrowserSessionSnapshot:
    session_id: str
    task_id: str
    workspace_key: str
    started_at: str
    last_seen_at: str
    idle_timeout_minutes: int = 30
    status: str = "ready"
    recent_targets: list[str] = field(default_factory=list)
    recent_probe_refs: list[str] = field(default_factory=list)
    cookies_imported: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrowserSessionManager:
    def __init__(self, repo_path: str | Path, task_id: str, idle_timeout_minutes: int = 30):
        self.repo_path = Path(repo_path).resolve()
        self.task_id = task_id
        self.idle_timeout_minutes = idle_timeout_minutes
        self.runtime_dir = self.repo_path.parent / ".meta" / self.repo_path.name / "browser_runtime"
        self.session_file = self.runtime_dir / "session.json"
        self.probe_dir = self.runtime_dir / "probes"
        self.screenshot_dir = self.runtime_dir / "screenshots"
        self.observation_dir = self.runtime_dir / "observations"
        self.dom_dir = self.runtime_dir / "dom"
        self.console_dir = self.runtime_dir / "console"
        self.steps_file = self.runtime_dir / "steps.jsonl"
        self.storage_state_file = self.runtime_dir / "storage_state.json"

    def ensure_session(self, target_url: str | None = None) -> BrowserSessionSnapshot:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.probe_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.observation_dir.mkdir(parents=True, exist_ok=True)
        self.dom_dir.mkdir(parents=True, exist_ok=True)
        self.console_dir.mkdir(parents=True, exist_ok=True)

        snapshot = self._load_session()
        now = _now()
        if snapshot is None:
            snapshot = BrowserSessionSnapshot(
                session_id=f"browser-{uuid.uuid4()}",
                task_id=self.task_id,
                workspace_key=str(self.repo_path),
                started_at=now,
                last_seen_at=now,
                idle_timeout_minutes=self.idle_timeout_minutes,
                status="created",
            )
        elif self._is_idle_expired(snapshot):
            snapshot = BrowserSessionSnapshot(
                session_id=f"browser-{uuid.uuid4()}",
                task_id=self.task_id,
                workspace_key=str(self.repo_path),
                started_at=now,
                last_seen_at=now,
                idle_timeout_minutes=self.idle_timeout_minutes,
                status="restarted",
                recent_targets=list(snapshot.recent_targets[-5:]),
                recent_probe_refs=list(snapshot.recent_probe_refs[-5:]),
                cookies_imported=bool(snapshot.cookies_imported),
            )
        else:
            snapshot.last_seen_at = now
            snapshot.status = "reused"

        if target_url:
            target = target_url.strip()
            if target:
                snapshot.recent_targets = _trim_tail([*snapshot.recent_targets, target], limit=10)

        self.session_file.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return snapshot

    def record_probe(self, name: str, payload: dict[str, Any]) -> str:
        self.probe_dir.mkdir(parents=True, exist_ok=True)
        probe_name = _slugify(name) or f"probe-{uuid.uuid4()}"
        probe_path = self.probe_dir / f"{probe_name}.json"
        probe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        snapshot = self.ensure_session()
        snapshot.recent_probe_refs = _trim_tail([*snapshot.recent_probe_refs, str(probe_path)], limit=10)
        self.session_file.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(probe_path)

    def write_placeholder_screenshot(self, name: str, summary: str) -> str:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_name = _slugify(name) or f"screenshot-{uuid.uuid4()}"
        screenshot_path = self.screenshot_dir / f"{screenshot_name}.txt"
        screenshot_path.write_text(summary.strip() + "\n", encoding="utf-8")
        return str(screenshot_path)

    def allocate_screenshot_path(self, name: str, suffix: str = ".png") -> Path:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_name = _slugify(name) or f"screenshot-{uuid.uuid4()}"
        return self.screenshot_dir / f"{screenshot_name}{suffix}"

    def write_dom_snapshot(self, name: str, html: str) -> str:
        self.dom_dir.mkdir(parents=True, exist_ok=True)
        dom_name = _slugify(name) or f"dom-{uuid.uuid4()}"
        dom_path = self.dom_dir / f"{dom_name}.html"
        dom_path.write_text(html, encoding="utf-8")
        return str(dom_path)

    def write_console_log(self, name: str, payload: list[dict[str, Any]]) -> str:
        self.console_dir.mkdir(parents=True, exist_ok=True)
        console_name = _slugify(name) or f"console-{uuid.uuid4()}"
        console_path = self.console_dir / f"{console_name}.json"
        console_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(console_path)

    def record_observation(self, name: str, payload: dict[str, Any]) -> str:
        self.observation_dir.mkdir(parents=True, exist_ok=True)
        observation_name = _slugify(name) or f"observation-{uuid.uuid4()}"
        observation_path = self.observation_dir / f"{observation_name}.json"
        observation_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        snapshot = self.ensure_session()
        snapshot.recent_probe_refs = _trim_tail([*snapshot.recent_probe_refs, str(observation_path)], limit=20)
        self.session_file.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(observation_path)

    def record_step(self, payload: dict[str, Any]) -> str:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False)
        with self.steps_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return str(self.steps_file)

    def _load_session(self) -> BrowserSessionSnapshot | None:
        if not self.session_file.exists():
            return None
        try:
            payload = json.loads(self.session_file.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return BrowserSessionSnapshot(
            session_id=str(payload.get("session_id") or f"browser-{uuid.uuid4()}"),
            task_id=str(payload.get("task_id") or self.task_id),
            workspace_key=str(payload.get("workspace_key") or self.repo_path),
            started_at=str(payload.get("started_at") or _now()),
            last_seen_at=str(payload.get("last_seen_at") or _now()),
            idle_timeout_minutes=int(payload.get("idle_timeout_minutes") or self.idle_timeout_minutes),
            status=str(payload.get("status") or "ready"),
            recent_targets=[str(item) for item in payload.get("recent_targets") or [] if str(item).strip()],
            recent_probe_refs=[str(item) for item in payload.get("recent_probe_refs") or [] if str(item).strip()],
            cookies_imported=bool(payload.get("cookies_imported")),
        )

    def _is_idle_expired(self, snapshot: BrowserSessionSnapshot) -> bool:
        try:
            last_seen = datetime.fromisoformat(snapshot.last_seen_at)
        except ValueError:
            return False
        return datetime.now() - last_seen > timedelta(minutes=max(snapshot.idle_timeout_minutes, 1))


def _trim_tail(items: list[str], limit: int) -> list[str]:
    return items[-limit:] if len(items) > limit else items


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
