from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(slots=True)
class BrowserTabSnapshot:
    tab_id: int
    url: str = "about:blank"
    title: str = ""
    active: bool = False
    viewport_name: str = "desktop"
    viewport: dict[str, int] = field(default_factory=dict)
    last_command_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    evidence_refs: list[str] = field(default_factory=list)
    cookies_imported: bool = False
    active_tab_id: int | None = None
    tabs: list[dict[str, Any]] = field(default_factory=list)
    command_count: int = 0
    last_command_at: str | None = None
    storage_state_path: str | None = None
    service_kind: str = "playwright_persistent_runtime"
    service_status: str = "stopped"
    service_started_at: str | None = None
    service_auth_token: str | None = None
    service_state_path: str | None = None
    handoff_active: bool = False
    handoff_reason: str | None = None
    last_snapshot_ref: str | None = None
    last_snapshot_diff_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrowserSessionManager:
    def __init__(self, repo_path: str | Path, task_id: str, idle_timeout_minutes: int = 30):
        self.repo_path = Path(repo_path).resolve()
        self.task_id = task_id
        self.idle_timeout_minutes = idle_timeout_minutes
        self.gstack_dir = self.repo_path / ".gstack"
        self.browse_state_file = self.gstack_dir / "browse.json"
        self.gstack_console_log = self.gstack_dir / "browse-console.log"
        self.gstack_network_log = self.gstack_dir / "browse-network.log"
        self.gstack_dialog_log = self.gstack_dir / "browse-dialog.log"
        self.runtime_dir = self.repo_path.parent / ".meta" / self.repo_path.name / "browser_runtime"
        self.session_file = self.runtime_dir / "session.json"
        self.service_file = self.runtime_dir / "service.json"
        self.handoff_file = self.runtime_dir / "handoff.json"
        self.probe_dir = self.runtime_dir / "probes"
        self.screenshot_dir = self.runtime_dir / "screenshots"
        self.observation_dir = self.runtime_dir / "observations"
        self.dom_dir = self.runtime_dir / "dom"
        self.console_dir = self.runtime_dir / "console"
        self.network_dir = self.runtime_dir / "network"
        self.dialog_dir = self.runtime_dir / "dialogs"
        self.command_dir = self.runtime_dir / "commands"
        self.snapshot_dir = self.runtime_dir / "snapshots"
        self.diff_dir = self.runtime_dir / "diffs"
        self.text_dir = self.runtime_dir / "text"
        self.session_state_dir = self.runtime_dir / "state"
        self.steps_file = self.runtime_dir / "steps.jsonl"
        self.storage_state_file = self.runtime_dir / "storage_state.json"
        self.tabs_file = self.session_state_dir / "tabs.json"

    def ensure_session(self, target_url: str | None = None) -> BrowserSessionSnapshot:
        self._ensure_dirs()
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
                storage_state_path=str(self.storage_state_file),
                service_state_path=str(self.service_file),
                service_auth_token=self._load_service_auth_token() or secrets.token_hex(16),
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
                recent_probe_refs=list(snapshot.recent_probe_refs[-10:]),
                evidence_refs=list(snapshot.evidence_refs[-10:]),
                cookies_imported=bool(snapshot.cookies_imported),
                storage_state_path=str(self.storage_state_file),
                service_state_path=str(self.service_file),
                service_auth_token=self._load_service_auth_token() or secrets.token_hex(16),
            )
        else:
            snapshot.last_seen_at = now
            snapshot.status = "reused"
            snapshot.storage_state_path = str(self.storage_state_file)
            snapshot.service_state_path = str(self.service_file)
            snapshot.service_auth_token = snapshot.service_auth_token or self._load_service_auth_token() or secrets.token_hex(16)

        if target_url:
            target = target_url.strip()
            if target:
                snapshot.recent_targets = _trim_tail([*snapshot.recent_targets, target], limit=12)

        self.save_session(snapshot)
        return snapshot

    def load_session(self) -> BrowserSessionSnapshot | None:
        return self._load_session()

    def save_session(self, snapshot: BrowserSessionSnapshot) -> None:
        self._ensure_dirs()
        self.session_file.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def update_session(
        self,
        *,
        status: str | None = None,
        active_tab_id: int | None = None,
        tabs: list[dict[str, Any]] | None = None,
        cookies_imported: bool | None = None,
        command_count: int | None = None,
        last_command_at: str | None = None,
        recent_target: str | None = None,
        probe_ref: str | None = None,
        evidence_ref: str | None = None,
        service_status: str | None = None,
        service_started_at: str | None = None,
        service_auth_token: str | None = None,
        handoff_active: bool | None = None,
        handoff_reason: str | None = None,
        last_snapshot_ref: str | None = None,
        last_snapshot_diff_path: str | None = None,
    ) -> BrowserSessionSnapshot:
        snapshot = self.ensure_session()
        snapshot.last_seen_at = _now()
        if status:
            snapshot.status = status
        if active_tab_id is not None:
            snapshot.active_tab_id = int(active_tab_id)
        if tabs is not None:
            snapshot.tabs = [dict(item) for item in tabs]
            self.write_tab_state(
                {
                    "updated_at": snapshot.last_seen_at,
                    "active_tab_id": snapshot.active_tab_id,
                    "tabs": snapshot.tabs,
                }
            )
        if cookies_imported is not None:
            snapshot.cookies_imported = bool(cookies_imported)
        if command_count is not None:
            snapshot.command_count = int(command_count)
        if last_command_at:
            snapshot.last_command_at = str(last_command_at)
        if recent_target and recent_target.strip():
            snapshot.recent_targets = _trim_tail([*snapshot.recent_targets, recent_target.strip()], limit=12)
        if probe_ref and probe_ref.strip():
            snapshot.recent_probe_refs = _trim_tail([*snapshot.recent_probe_refs, probe_ref.strip()], limit=20)
        if evidence_ref and evidence_ref.strip():
            snapshot.evidence_refs = _trim_tail([*snapshot.evidence_refs, evidence_ref.strip()], limit=20)
        if service_status:
            snapshot.service_status = service_status
        if service_started_at:
            snapshot.service_started_at = str(service_started_at)
        if service_auth_token:
            snapshot.service_auth_token = str(service_auth_token)
        if handoff_active is not None:
            snapshot.handoff_active = bool(handoff_active)
        if handoff_reason is not None:
            snapshot.handoff_reason = str(handoff_reason).strip() or None
        if last_snapshot_ref:
            snapshot.last_snapshot_ref = str(last_snapshot_ref)
        if last_snapshot_diff_path:
            snapshot.last_snapshot_diff_path = str(last_snapshot_diff_path)
        snapshot.storage_state_path = str(self.storage_state_file)
        snapshot.service_state_path = str(self.service_file)
        self.save_session(snapshot)
        return snapshot

    def load_service_state(self) -> dict[str, Any]:
        for candidate in (self.service_file, self.browse_state_file):
            if not candidate.exists():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    def write_service_state(self, payload: dict[str, Any]) -> str:
        self._ensure_dirs()
        normalized = dict(payload)
        normalized.setdefault("updated_at", _now())
        self._atomic_write_json(self.service_file, normalized)
        return str(self.service_file)

    def load_browse_state(self) -> dict[str, Any]:
        if not self.browse_state_file.exists():
            return {}
        try:
            payload = json.loads(self.browse_state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def write_browse_state(self, payload: dict[str, Any]) -> str:
        self._ensure_dirs()
        normalized = dict(payload)
        normalized.setdefault("workspaceRoot", str(self.repo_path))
        normalized.setdefault("updatedAt", _now())
        self._atomic_write_json(self.browse_state_file, normalized, owner_only=True)
        mirror_payload = {
            "session_id": normalized.get("session_id"),
            "auth_token": normalized.get("token"),
            "service_kind": normalized.get("serviceKind") or "browse_host_daemon",
            "status": normalized.get("status") or "ready",
            "started_at": normalized.get("startedAt"),
            "last_activity_at": normalized.get("lastActivityAt"),
            "idle_timeout_minutes": normalized.get("idleTimeoutMinutes") or self.idle_timeout_minutes,
            "active_tab_id": normalized.get("activeTabId"),
            "tabs": normalized.get("tabs") or [],
            "handoff_active": bool(normalized.get("handoffActive")),
            "handoff_reason": normalized.get("handoffReason"),
            "host_pid": normalized.get("pid"),
            "host_port": normalized.get("port"),
            "binary_version": normalized.get("binaryVersion"),
            "workspace_root": normalized.get("workspaceRoot") or str(self.repo_path),
        }
        self.write_service_state(mirror_payload)
        return str(self.browse_state_file)

    def clear_browse_state(self) -> None:
        for candidate in (self.browse_state_file, self.service_file):
            try:
                candidate.unlink()
            except FileNotFoundError:
                continue

    def append_gstack_log(self, kind: str, payload: Any) -> str:
        self._ensure_dirs()
        if kind == "console":
            target = self.gstack_console_log
        elif kind == "network":
            target = self.gstack_network_log
        else:
            target = self.gstack_dialog_log
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
        return str(target)

    def write_handoff_state(self, payload: dict[str, Any]) -> str:
        self._ensure_dirs()
        normalized = dict(payload)
        normalized.setdefault("updated_at", _now())
        self.handoff_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.handoff_file)

    def record_probe(self, name: str, payload: dict[str, Any]) -> str:
        probe_path = self.write_json_artifact(self.probe_dir, name, payload)
        self.update_session(probe_ref=probe_path)
        return probe_path

    def write_placeholder_screenshot(self, name: str, summary: str) -> str:
        screenshot_path = self.allocate_artifact_path(self.screenshot_dir, name, ".txt")
        screenshot_path.write_text(summary.strip() + "\n", encoding="utf-8")
        self.update_session(evidence_ref=str(screenshot_path))
        return str(screenshot_path)

    def allocate_screenshot_path(self, name: str, suffix: str = ".png") -> Path:
        return self.allocate_artifact_path(self.screenshot_dir, name, suffix)

    def allocate_artifact_path(self, directory: Path, name: str, suffix: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        artifact_name = _slugify(name) or f"artifact-{uuid.uuid4()}"
        return directory / f"{artifact_name}{suffix}"

    def write_dom_snapshot(self, name: str, html: str) -> str:
        dom_path = self.allocate_artifact_path(self.dom_dir, name, ".html")
        dom_path.write_text(html, encoding="utf-8")
        self.update_session(evidence_ref=str(dom_path))
        return str(dom_path)

    def write_console_log(self, name: str, payload: list[dict[str, Any]]) -> str:
        console_path = self.allocate_artifact_path(self.console_dir, name, ".json")
        console_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.update_session(evidence_ref=str(console_path))
        return str(console_path)

    def write_network_log(self, name: str, payload: list[dict[str, Any]]) -> str:
        network_path = self.allocate_artifact_path(self.network_dir, name, ".json")
        network_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.update_session(evidence_ref=str(network_path))
        return str(network_path)

    def write_dialog_log(self, name: str, payload: list[dict[str, Any]]) -> str:
        dialog_path = self.allocate_artifact_path(self.dialog_dir, name, ".json")
        dialog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.update_session(evidence_ref=str(dialog_path))
        return str(dialog_path)

    def write_snapshot_artifact(self, name: str, payload: dict[str, Any]) -> str:
        snapshot_path = self.allocate_artifact_path(self.snapshot_dir, name, ".json")
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.update_session(evidence_ref=str(snapshot_path), probe_ref=str(snapshot_path), last_snapshot_ref=str(snapshot_path))
        return str(snapshot_path)

    def write_diff_artifact(self, name: str, diff_text: str) -> str:
        diff_path = self.allocate_artifact_path(self.diff_dir, name, ".diff")
        diff_path.write_text(diff_text, encoding="utf-8")
        self.update_session(evidence_ref=str(diff_path), last_snapshot_diff_path=str(diff_path))
        return str(diff_path)

    def write_text_artifact(self, name: str, text: str, *, suffix: str = ".txt") -> str:
        text_path = self.allocate_artifact_path(self.text_dir, name, suffix)
        text_path.write_text(text, encoding="utf-8")
        self.update_session(evidence_ref=str(text_path))
        return str(text_path)

    def record_observation(self, name: str, payload: dict[str, Any]) -> str:
        observation_path = self.write_json_artifact(self.observation_dir, name, payload)
        self.update_session(probe_ref=observation_path, evidence_ref=observation_path)
        return observation_path

    def record_command_result(self, name: str, payload: dict[str, Any]) -> str:
        command_path = self.write_json_artifact(self.command_dir, name, payload)
        self.update_session(evidence_ref=command_path)
        return command_path

    def write_tab_state(self, payload: dict[str, Any]) -> str:
        self.session_state_dir.mkdir(parents=True, exist_ok=True)
        self.tabs_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.tabs_file)

    def write_json_artifact(self, directory: Path, name: str, payload: dict[str, Any]) -> str:
        artifact_path = self.allocate_artifact_path(directory, name, ".json")
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(artifact_path)

    def record_step(self, payload: dict[str, Any]) -> str:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False)
        with self.steps_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return str(self.steps_file)

    def _ensure_dirs(self) -> None:
        self.gstack_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.probe_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.observation_dir.mkdir(parents=True, exist_ok=True)
        self.dom_dir.mkdir(parents=True, exist_ok=True)
        self.console_dir.mkdir(parents=True, exist_ok=True)
        self.network_dir.mkdir(parents=True, exist_ok=True)
        self.dialog_dir.mkdir(parents=True, exist_ok=True)
        self.command_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.session_state_dir.mkdir(parents=True, exist_ok=True)

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
            evidence_refs=[str(item) for item in payload.get("evidence_refs") or [] if str(item).strip()],
            cookies_imported=bool(payload.get("cookies_imported")),
            active_tab_id=_coerce_int(payload.get("active_tab_id")),
            tabs=[dict(item) for item in payload.get("tabs") or [] if isinstance(item, dict)],
            command_count=int(payload.get("command_count") or 0),
            last_command_at=str(payload.get("last_command_at") or "") or None,
            storage_state_path=str(payload.get("storage_state_path") or self.storage_state_file),
            service_kind=str(payload.get("service_kind") or "playwright_persistent_runtime"),
            service_status=str(payload.get("service_status") or "stopped"),
            service_started_at=str(payload.get("service_started_at") or "") or None,
            service_auth_token=str(payload.get("service_auth_token") or "") or None,
            service_state_path=str(payload.get("service_state_path") or self.service_file),
            handoff_active=bool(payload.get("handoff_active")),
            handoff_reason=str(payload.get("handoff_reason") or "") or None,
            last_snapshot_ref=str(payload.get("last_snapshot_ref") or "") or None,
            last_snapshot_diff_path=str(payload.get("last_snapshot_diff_path") or "") or None,
        )

    def _load_service_auth_token(self) -> str | None:
        payload = self.load_service_state()
        token = str(payload.get("auth_token") or payload.get("token") or "").strip()
        return token or None

    def _atomic_write_json(self, path: Path, payload: dict[str, Any], *, owner_only: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, path)
        if owner_only:
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass

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


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
