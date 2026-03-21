from __future__ import annotations

import atexit
import difflib
import hashlib
import http.client
import json
import os
import queue
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from agentsystem.runtime.browser_session_manager import BrowserSessionManager


DEFAULT_VIEWPORTS: tuple[tuple[str, dict[str, int]], ...] = (
    ("desktop", {"width": 1440, "height": 900}),
    ("mobile", {"width": 390, "height": 844}),
)

_RUNTIME_LOCK = threading.RLock()
_RUNTIMES: dict[str, "_BrowserRuntimeService"] = {}
_REAPER_STARTED = False
SERVICE_POLL_SECONDS = 5.0
HOST_START_TIMEOUT_SECONDS = 20.0
HOST_REQUEST_TIMEOUT_SECONDS = 12.0
ROOT_DIR = Path(__file__).resolve().parents[3]
SERVER_ENTRYPOINT = ROOT_DIR / "src" / "agentsystem" / "runtime" / "browser_host_server.py"
_SPAWNED_HOST_PIDS: set[int] = set()
_SPAWNED_HOST_PROCESSES: dict[int, subprocess.Popen[Any]] = {}


@dataclass(slots=True)
class BrowserTarget:
    url: str
    name: str
    kind: str = "current"
    actions: list[dict[str, Any]] = field(default_factory=list)
    viewports: list[dict[str, Any]] = field(default_factory=list)


class _BrowserRuntimeService:
    def __init__(
        self,
        session_id: str,
        storage_state_path: Path,
        *,
        idle_timeout_minutes: int = 30,
        headless: bool = True,
    ) -> None:
        self.session_id = session_id
        self.storage_state_path = Path(storage_state_path)
        self.idle_timeout_minutes = max(int(idle_timeout_minutes or 30), 1)
        self._default_headless = headless
        self.headless = headless
        self._lock = threading.RLock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: dict[int, Page] = {}
        self._page_events: dict[int, dict[str, list[Any]]] = {}
        self._last_snapshot_payloads: dict[int, dict[str, Any]] = {}
        self._snapshot_ref_maps: dict[int, dict[str, dict[str, Any]]] = {}
        self._tab_cache: list[dict[str, Any]] = []
        self._active_tab_id = 0
        self._next_tab_id = 1
        self._command_count = 0
        self._last_activity_at = datetime.now().isoformat(timespec="seconds")
        self._started = False
        self._started_at: str | None = None
        self._auth_token: str | None = None
        self._handoff_active = False
        self._handoff_reason: str | None = None
        self._dialog_policy = "accept"
        self._dialog_prompt_text: str | None = None
        self._manager: BrowserSessionManager | None = None
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._startup_event = threading.Event()
        self._startup_error: Exception | None = None
        self._command_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._stop_requested = False

    def ensure_started(self, manager: BrowserSessionManager) -> None:
        snapshot = manager.ensure_session()
        self._manager = manager
        if self._started and self.is_healthy():
            self._touch()
            self._write_service_state(manager, status="ready")
            return
        self.close(manager=manager, reason="restarting", remove_runtime=False)
        self._command_count = int(snapshot.command_count or 0)
        self._started_at = snapshot.service_started_at or datetime.now().isoformat(timespec="seconds")
        self._auth_token = snapshot.service_auth_token or f"browse-{self.session_id.replace('browser-', '')[:12]}"
        self._handoff_active = bool(snapshot.handoff_active)
        self._handoff_reason = snapshot.handoff_reason
        self._startup_event = threading.Event()
        self._startup_error = None
        self._stop_requested = False
        self._thread = threading.Thread(target=self._service_loop, args=(manager,), daemon=True, name=f"browse-{self.session_id}")
        self._thread.start()
        if not self._startup_event.wait(timeout=30):
            raise TimeoutError(f"Browser runtime {self.session_id} did not start within 30 seconds.")
        if self._startup_error is not None:
            raise self._startup_error

    def is_healthy(self) -> bool:
        return bool(self._started and self._browser is not None and self._context is not None and self._thread and self._thread.is_alive())

    def close(
        self,
        manager: BrowserSessionManager | None = None,
        *,
        reason: str = "stopped",
        remove_runtime: bool = True,
    ) -> None:
        with self._lock:
            target_manager = manager or self._manager
            current_thread_id = threading.get_ident()
            if self._thread_id is not None and self._thread_id == current_thread_id:
                self._close_resources(target_manager, reason=reason)
            elif self._thread is not None and self._thread.is_alive():
                self._stop_requested = True
                self._command_queue.put(None)
                self._thread.join(timeout=10)
                if self._thread and self._thread.is_alive():
                    self._close_resources(target_manager, reason=reason)
            else:
                self._close_resources(target_manager, reason=reason)
            self._thread = None
            self._thread_id = None
            target_manager = manager or self._manager
            if target_manager is not None:
                target_manager.update_session(
                    status="ready" if reason == "restarting" else reason,
                    service_status=reason,
                    service_started_at=self._started_at,
                    service_auth_token=self._auth_token,
                    handoff_active=False,
                    handoff_reason=None,
                )
                target_manager.write_service_state(
                    {
                        "session_id": self.session_id,
                        "auth_token": self._auth_token,
                        "service_kind": "playwright_persistent_runtime",
                        "status": reason,
                        "started_at": self._started_at,
                        "last_activity_at": self._last_activity_at,
                        "idle_timeout_minutes": self.idle_timeout_minutes,
                        "active_tab_id": None,
                        "tabs": [],
                        "handoff_active": False,
                        "handoff_reason": None,
                    }
                )
            if remove_runtime:
                with _RUNTIME_LOCK:
                    _RUNTIMES.pop(self.session_id, None)

    def execute_commands(
        self,
        manager: BrowserSessionManager,
        commands: list[dict[str, Any]],
        *,
        target_name: str,
        kind: str,
        viewport_name: str,
        viewport: dict[str, int],
    ) -> dict[str, Any]:
        _ensure_reaper_started()
        self.ensure_started(manager)
        done_event = threading.Event()
        result_box: dict[str, Any] = {}
        error_box: dict[str, Exception] = {}
        self._command_queue.put(
            {
                "manager": manager,
                "commands": commands,
                "target_name": target_name,
                "kind": kind,
                "viewport_name": viewport_name,
                "viewport": viewport,
                "result_box": result_box,
                "error_box": error_box,
                "done_event": done_event,
            }
        )
        done_event.wait()
        if "error" in error_box:
            raise error_box["error"]
        return result_box["value"]

    def _service_loop(self, manager: BrowserSessionManager) -> None:
        self._thread_id = threading.get_ident()
        try:
            storage_state = str(self.storage_state_path) if self.storage_state_path.exists() else None
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(ignore_https_errors=True, storage_state=storage_state)
            self._pages = {}
            self._page_events = {}
            self._last_snapshot_payloads = {}
            self._snapshot_ref_maps = {}
            self._active_tab_id = 0
            self._next_tab_id = 1
            self._new_tab()
            self._started = True
            self._touch()
            self._write_service_state(manager, status="ready")
        except Exception as exc:  # pragma: no cover - startup failures are environment-specific
            self._startup_error = exc
            self._startup_event.set()
            return
        self._startup_event.set()

        while not self._stop_requested:
            item = self._command_queue.get()
            if item is None:
                break
            result_box = item["result_box"]
            error_box = item["error_box"]
            done_event = item["done_event"]
            try:
                result_box["value"] = self._execute_commands_sync(
                    item["manager"],
                    item["commands"],
                    target_name=item["target_name"],
                    kind=item["kind"],
                    viewport_name=item["viewport_name"],
                    viewport=item["viewport"],
                )
            except Exception as exc:  # pragma: no cover - forwarded to caller
                error_box["error"] = exc
            finally:
                done_event.set()
            if self._stop_requested:
                break

        self._close_resources(manager, reason="stopped" if self._stop_requested else "shutdown")

    def _close_resources(self, manager: BrowserSessionManager | None, *, reason: str) -> None:
        for page in list(self._pages.values()):
            try:
                page.close()
            except Exception:
                continue
        self._pages = {}
        self._page_events = {}
        self._last_snapshot_payloads = {}
        self._snapshot_ref_maps = {}
        self._tab_cache = []
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._started = False
        self._handoff_active = False
        self._handoff_reason = None
        if manager is not None:
            manager.write_service_state(
                {
                    "session_id": self.session_id,
                    "auth_token": self._auth_token,
                    "service_kind": "playwright_persistent_runtime",
                    "status": reason,
                    "started_at": self._started_at,
                    "last_activity_at": self._last_activity_at,
                    "idle_timeout_minutes": self.idle_timeout_minutes,
                    "active_tab_id": None,
                    "tabs": [],
                    "handoff_active": False,
                    "handoff_reason": None,
                }
            )

    def _execute_commands_sync(
        self,
        manager: BrowserSessionManager,
        commands: list[dict[str, Any]],
        *,
        target_name: str,
        kind: str,
        viewport_name: str,
        viewport: dict[str, int],
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        terminated = False
        for index, raw_command in enumerate(commands, start=1):
            normalized = _normalize_command(raw_command)
            command_name = normalized["command"]
            timestamp = datetime.now().isoformat(timespec="seconds")
            manager.record_step(
                {
                    "timestamp": timestamp,
                    "session_id": self.session_id,
                    "target": target_name,
                    "kind": kind,
                    "viewport": viewport_name,
                    "active_tab_id": self._active_tab_id,
                    "command": command_name,
                    "payload": normalized,
                }
            )
            try:
                if self._handoff_active and command_name not in {"resume", "status", "stop"}:
                    raise RuntimeError("Browser runtime is waiting for user handoff completion. Call resume first.")
                result = self._execute_one(
                    normalized,
                    manager=manager,
                    target_name=target_name,
                    kind=kind,
                    viewport_name=viewport_name,
                    viewport=viewport,
                    index=index,
                )
                result["ok"] = True
            except Exception as exc:
                result = {
                    "command": command_name,
                    "ok": False,
                    "error": str(exc),
                    "target_name": target_name,
                    "kind": kind,
                    "viewport_name": viewport_name,
                    "active_tab_id": self._active_tab_id,
                }
            result["timestamp"] = timestamp
            results.append(result)
            manager.record_command_result(
                f"{target_name}-{viewport_name}-step-{index:02d}-{command_name}",
                result,
            )
            self._command_count += 1
            self._touch()
            if command_name == "stop" and result.get("ok"):
                terminated = True
                break
        if not terminated:
            self._persist_storage_state()
            manager.update_session(
                status="ready",
                active_tab_id=self._active_tab_id,
                tabs=self._tab_summaries(),
                command_count=self._command_count,
                last_command_at=self._last_activity_at,
                service_status="handoff" if self._handoff_active else "ready",
                service_started_at=self._started_at,
                service_auth_token=self._auth_token,
                handoff_active=self._handoff_active,
                handoff_reason=self._handoff_reason,
            )
            self._write_service_state(manager, status="handoff" if self._handoff_active else "ready")
        return {**self._status_payload(), "results": results}

    def _execute_one(
        self,
        command: dict[str, Any],
        *,
        manager: BrowserSessionManager,
        target_name: str,
        kind: str,
        viewport_name: str,
        viewport: dict[str, int],
        index: int,
    ) -> dict[str, Any]:
        name = command["command"]
        if name == "tab":
            return self._handle_tab_command(command)
        if name == "status":
            self._write_service_state(manager, status="handoff" if self._handoff_active else "ready")
            return {"command": "status", **self._status_payload()}
        if name == "stop":
            status = self._status_payload()
            self._stop_requested = True
            return {**status, "command": "stop", "status": "stopped"}
        if name == "resume":
            visibility_adapter: dict[str, Any] | None = None
            if self._default_headless and not self.headless:
                visibility_adapter = self._switch_browser_visibility(headless=True)
            self._handoff_active = False
            self._handoff_reason = None
            manager.write_handoff_state(
                {
                    "session_id": self.session_id,
                "status": "resumed",
                "message": "Browser control returned to the agent runtime.",
                "active_tab_id": self._active_tab_id,
                "url": self._get_page().url if self._pages else "",
                "visibility_adapter": visibility_adapter,
            }
            )
            self._write_service_state(manager, status="ready")
            return {
                "command": "resume",
                "status": "ready",
                "active_tab_id": self._active_tab_id,
                "url": self._get_page().url if self._pages else "",
                "visibility_adapter": visibility_adapter,
            }
        if name == "handoff":
            page = self._get_page()
            visible_requested = bool(command.get("visible")) or str(command.get("mode") or "").strip().lower() in {"visible", "headed"}
            visibility_adapter: dict[str, Any] | None = None
            visible_handoff_path: str | None = None
            if visible_requested:
                visibility_adapter = self._switch_browser_visibility(headless=False)
                page = self._get_page()
                visible_handoff_path = manager.write_json_artifact(
                    manager.session_state_dir,
                    "visible-handoff",
                    {
                        "session_id": self.session_id,
                        "status": "waiting_for_user",
                        "requested_visible": True,
                        "visibility_adapter": visibility_adapter,
                        "active_tab_id": self._active_tab_id,
                        "tabs": self._tab_summaries(),
                        "storage_state_path": str(self.storage_state_path),
                    },
                )
            self._handoff_active = True
            self._handoff_reason = str(command.get("message") or command.get("reason") or "Awaiting user takeover.").strip()
            self._persist_storage_state()
            handoff_path = manager.write_handoff_state(
                {
                    "session_id": self.session_id,
                    "status": "waiting_for_user",
                    "message": self._handoff_reason,
                    "active_tab_id": self._active_tab_id,
                    "url": page.url,
                    "tabs": self._tab_summaries(),
                    "visible_handoff_path": visible_handoff_path,
                    "visibility_adapter": visibility_adapter,
                }
            )
            self._write_service_state(manager, status="handoff")
            return {
                "command": "handoff",
                "status": "waiting_for_user",
                "handoff_path": handoff_path,
                "visible_handoff_path": visible_handoff_path,
                "message": self._handoff_reason,
                "url": page.url,
                "active_tab_id": self._active_tab_id,
                "visibility_adapter": visibility_adapter,
            }
        page = self._get_page()
        if name == "viewport":
            width = int(command.get("width") or viewport.get("width") or 1440)
            height = int(command.get("height") or viewport.get("height") or 900)
            page.set_viewport_size({"width": width, "height": height})
            return {"command": name, "width": width, "height": height, "active_tab_id": self._active_tab_id}
        if name == "goto":
            target_url = str(command.get("url") or "").strip()
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            _wait_for_settle(page)
            return {
                "command": name,
                "url": page.url,
                "requested_url": target_url,
                "status_code": response.status if response is not None else 0,
                "active_tab_id": self._active_tab_id,
            }
        if name == "back":
            response = page.go_back(wait_until="domcontentloaded", timeout=30000)
            _wait_for_settle(page)
            return {
                "command": name,
                "url": page.url,
                "status_code": response.status if response is not None else 0,
                "active_tab_id": self._active_tab_id,
            }
        if name == "forward":
            response = page.go_forward(wait_until="domcontentloaded", timeout=30000)
            _wait_for_settle(page)
            return {
                "command": name,
                "url": page.url,
                "status_code": response.status if response is not None else 0,
                "active_tab_id": self._active_tab_id,
            }
        if name == "reload":
            response = page.reload(wait_until="domcontentloaded", timeout=30000)
            _wait_for_settle(page)
            return {
                "command": name,
                "url": page.url,
                "status_code": response.status if response is not None else 0,
                "active_tab_id": self._active_tab_id,
            }
        if name == "url":
            return {"command": name, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "click":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            page.locator(selector).first.click(timeout=10000)
            _wait_for_settle(page)
            return {"command": name, "selector": selector, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "type":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip(), allow_empty=True)
            value = str(command.get("value") or command.get("text") or "")
            if selector:
                page.locator(selector).first.fill(value, timeout=10000)
            else:
                page.keyboard.type(value)
            return {"command": name, "selector": selector, "value": value, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "hover":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            page.locator(selector).first.hover(timeout=10000)
            return {"command": name, "selector": selector, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "press":
            keys = str(command.get("keys") or command.get("value") or command.get("text") or "").strip()
            page.keyboard.press(keys)
            _wait_for_settle(page)
            return {"command": name, "keys": keys, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "scroll":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip(), allow_empty=True)
            if selector:
                page.locator(selector).first.scroll_into_view_if_needed(timeout=10000)
            else:
                page.mouse.wheel(0, int(command.get("amount") or 1200))
            return {"command": name, "selector": selector, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "select":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            value = str(command.get("value") or command.get("label") or command.get("text") or "").strip()
            page.locator(selector).first.select_option(value=value)
            return {"command": name, "selector": selector, "value": value, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "wait":
            if str(command.get("selector") or "").strip():
                page.wait_for_selector(str(command.get("selector")).strip(), timeout=int(command.get("timeout_ms") or 15000))
            elif str(command.get("until") or "").strip().lower() in {"networkidle", "network_idle"}:
                page.wait_for_load_state("networkidle", timeout=int(command.get("timeout_ms") or 15000))
            elif str(command.get("until") or "").strip().lower() in {"load", "domcontentloaded"}:
                page.wait_for_load_state(str(command.get("until")).strip().lower(), timeout=int(command.get("timeout_ms") or 15000))
            else:
                page.wait_for_timeout(int(command.get("ms") or 1000))
            return {"command": name, "selector": str(command.get("selector") or "").strip(), "until": str(command.get("until") or "").strip(), "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "screenshot":
            label = str(command.get("label") or f"step-{index}").strip() or f"step-{index}"
            screenshot_path = manager.allocate_screenshot_path(f"{target_name}-{viewport_name}-{label}")
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip(), allow_empty=True)
            clip = command.get("clip")
            if selector:
                page.locator(selector).first.screenshot(path=str(screenshot_path))
            elif isinstance(clip, dict):
                page.screenshot(path=str(screenshot_path), clip={key: int(value) for key, value in clip.items()}, full_page=False)
            else:
                page.screenshot(path=str(screenshot_path), full_page=not bool(command.get("viewport_only")))
            manager.update_session(evidence_ref=str(screenshot_path))
            return {"command": name, "label": label, "path": str(screenshot_path), "selector": selector, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "snapshot":
            return self._snapshot_page(
                page,
                manager=manager,
                target_name=target_name,
                kind=kind,
                viewport_name=viewport_name,
                viewport=viewport,
                label=str(command.get("label") or f"step-{index}").strip() or f"step-{index}",
                annotate=bool(command.get("annotate")),
                include_diff=bool(command.get("diff")),
            )
        if name == "evaluate":
            expression = str(command.get("expression") or command.get("script") or "").strip()
            value = page.evaluate(expression)
            return {"command": name, "expression": expression, "value": value, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "attrs":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            attrs = page.locator(selector).first.evaluate(
                """node => Object.fromEntries(Array.from(node.attributes).map(attr => [attr.name, attr.value]))"""
            )
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-attrs", {"selector": selector, "attrs": attrs})
            return {"command": name, "selector": selector, "attrs": attrs, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "accessibility":
            payload = page.evaluate(
                """() => Array.from(document.querySelectorAll('a, button, input, select, textarea, [role]')).slice(0, 120).map((node) => ({
                    tag: node.tagName.toLowerCase(),
                    role: node.getAttribute('role') || '',
                    text: (node.textContent || node.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim(),
                    ariaLabel: node.getAttribute('aria-label') || '',
                    disabled: !!node.getAttribute('disabled')
                }))"""
            )
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-accessibility", {"nodes": payload})
            return {"command": name, "nodes": payload, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "storage_state":
            return self._handle_storage_state(command)
        if name == "import_cookies":
            return self._handle_cookie_import(command, manager)
        if name == "cookie-import-browser":
            return self._handle_cookie_import(command, manager)
        if name == "browser-sources":
            sources = _discover_browser_cookie_sources(command)
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-browser-sources", {"sources": sources})
            return {
                "command": name,
                "sources": sources,
                "path": path,
                "active_tab_id": self._active_tab_id,
            }
        if name == "cookie":
            return self._handle_single_cookie(command)
        if name == "cookies":
            cookies = self._context.cookies() if self._context is not None else []
            path = manager.write_json_artifact(
                manager.command_dir,
                f"{target_name}-{viewport_name}-cookies",
                {"cookies": cookies},
            )
            return {"command": name, "cookies": cookies, "path": path, "active_tab_id": self._active_tab_id}
        if name == "storage":
            return self._handle_storage(command, manager, target_name=target_name, viewport_name=viewport_name)
        if name == "console":
            return self._handle_buffer_dump(
                manager,
                target_name=target_name,
                viewport_name=viewport_name,
                buffer_name="console",
                page=page,
                clear=bool(command.get("clear")),
                errors_only=bool(command.get("errors")),
            )
        if name == "network":
            return self._handle_buffer_dump(
                manager,
                target_name=target_name,
                viewport_name=viewport_name,
                buffer_name="network",
                page=page,
                clear=bool(command.get("clear")),
            )
        if name == "dialog":
            return self._handle_buffer_dump(
                manager,
                target_name=target_name,
                viewport_name=viewport_name,
                buffer_name="dialogs",
                page=page,
                clear=bool(command.get("clear")),
            )
        if name == "text":
            text = _safe_page_text(page)
            path = manager.write_text_artifact(f"{target_name}-{viewport_name}-text", text)
            return {"command": name, "text": text, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "links":
            links = page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]')).map((node) => ({
                    text: (node.textContent || '').replace(/\\s+/g, ' ').trim(),
                    href: node.href
                }))"""
            )
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-links", {"links": links})
            return {"command": name, "links": links, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "forms":
            fields = page.evaluate(
                """() => Array.from(document.querySelectorAll('input, select, textarea')).map((node) => ({
                    tag: node.tagName.toLowerCase(),
                    type: node.getAttribute('type') || '',
                    name: node.getAttribute('name') || '',
                    id: node.id || '',
                    value: node.value || '',
                    placeholder: node.getAttribute('placeholder') || ''
                }))"""
            )
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-forms", {"fields": fields})
            return {"command": name, "fields": fields, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "html":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip(), allow_empty=True)
            html = page.locator(selector).first.inner_html(timeout=10000) if selector else page.content()
            path = manager.write_text_artifact(f"{target_name}-{viewport_name}-html", html, suffix=".html")
            return {"command": name, "selector": selector, "html": html, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "is":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            prop = str(command.get("property") or command.get("state") or "").strip().lower()
            locator = page.locator(selector).first
            checks = {
                "visible": locator.is_visible(),
                "hidden": locator.is_hidden(),
                "enabled": locator.is_enabled(),
                "disabled": locator.is_disabled(),
                "checked": locator.is_checked(),
                "editable": locator.is_editable(),
                "focused": locator.evaluate("node => node === document.activeElement"),
            }
            if prop not in checks:
                raise ValueError(f"Unsupported state check: {prop}")
            return {"command": name, "selector": selector, "property": prop, "value": checks[prop], "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "responsive":
            return self._capture_responsive(
                page,
                manager=manager,
                target_name=target_name,
                viewport_name=viewport_name,
                prefix=str(command.get("prefix") or f"{target_name}-{viewport_name}").strip(),
            )
        if name == "pdf":
            pdf_path = manager.allocate_artifact_path(manager.screenshot_dir, f"{target_name}-{viewport_name}-page", ".pdf")
            page.pdf(path=str(pdf_path))
            manager.update_session(evidence_ref=str(pdf_path))
            return {"command": name, "path": str(pdf_path), "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "upload":
            selector = self._resolve_selector(page, str(command.get("selector") or "").strip())
            files = command.get("files") or command.get("paths") or command.get("path") or []
            normalized_files = [str(item).strip() for item in (files if isinstance(files, list) else [files]) if str(item).strip()]
            page.locator(selector).first.set_input_files(normalized_files, timeout=10000)
            return {"command": name, "selector": selector, "files": normalized_files, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "perf":
            metrics = page.evaluate(
                """() => {
                    const nav = performance.getEntriesByType('navigation')[0];
                    return nav ? {
                        domContentLoaded: nav.domContentLoadedEventEnd,
                        loadEventEnd: nav.loadEventEnd,
                        transferSize: nav.transferSize,
                        encodedBodySize: nav.encodedBodySize
                    } : {};
                }"""
            )
            path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-perf", {"metrics": metrics})
            return {"command": name, "metrics": metrics, "path": path, "url": page.url, "active_tab_id": self._active_tab_id}
        if name == "dialog-accept":
            self._dialog_policy = "accept"
            self._dialog_prompt_text = str(command.get("text") or command.get("value") or "").strip() or None
            return {"command": name, "policy": self._dialog_policy, "prompt_text": self._dialog_prompt_text, "active_tab_id": self._active_tab_id}
        if name == "dialog-dismiss":
            self._dialog_policy = "dismiss"
            self._dialog_prompt_text = None
            return {"command": name, "policy": self._dialog_policy, "active_tab_id": self._active_tab_id}
        if name == "chain":
            nested_results: list[dict[str, Any]] = []
            for offset, nested in enumerate(list(command.get("commands") or []), start=1):
                nested_results.append(
                    self._execute_one(
                        _normalize_command(dict(nested)),
                        manager=manager,
                        target_name=target_name,
                        kind=kind,
                        viewport_name=viewport_name,
                        viewport=viewport,
                        index=index + offset,
                    )
                )
            return {"command": name, "results": nested_results, "active_tab_id": self._active_tab_id, "url": page.url}
        if name == "diff":
            return self._diff_pages(command, manager=manager, target_name=target_name, viewport_name=viewport_name)
        raise ValueError(f"Unsupported browser command: {name}")

    def _handle_tab_command(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action") or command.get("tab_action") or "list").strip().lower()
        if action == "new":
            tab_id = self._new_tab(url=str(command.get("url") or "").strip() or None, viewport=_coerce_viewport(command))
            return {"command": "tab", "action": action, "tab_id": tab_id, "tabs": self._tab_summaries()}
        if action == "switch":
            tab_id = int(command.get("tab_id") or command.get("id") or 0)
            self._switch_tab(tab_id)
            return {"command": "tab", "action": action, "tab_id": tab_id, "tabs": self._tab_summaries()}
        if action == "close":
            tab_id = int(command.get("tab_id") or command.get("id") or self._active_tab_id)
            self._close_tab(tab_id)
            return {"command": "tab", "action": action, "tab_id": tab_id, "tabs": self._tab_summaries()}
        return {"command": "tab", "action": "list", "tab_id": self._active_tab_id, "tabs": self._tab_summaries()}

    def _resolve_selector(self, page: Page, raw_selector: str, *, allow_empty: bool = False) -> str:
        selector = str(raw_selector or "").strip()
        if not selector:
            if allow_empty:
                return ""
            raise ValueError("Browser command requires a selector or @ref.")
        if selector.startswith("@"):
            ref_entry = (self._snapshot_ref_maps.get(self._active_tab_id) or {}).get(selector)
            if not ref_entry:
                raise ValueError(f"Unknown browser ref {selector}. Run snapshot first.")
            selector = str(ref_entry.get("selector") or "").strip()
            if not selector:
                raise ValueError(f"Snapshot ref {raw_selector} does not carry a selector.")
        locator = page.locator(selector).first
        if locator.count() == 0:
            raise ValueError(f"Selector {raw_selector} is stale or no longer present. Run snapshot again.")
        return selector

    def _capture_snapshot_refs(self, page: Page) -> list[dict[str, Any]]:
        return page.evaluate(
            """() => {
                const escapeIdent = (value) => {
                  if (window.CSS && typeof window.CSS.escape === 'function') {
                    return window.CSS.escape(value);
                  }
                  return String(value).replace(/([ #;?%&,.+*~\\':"!^$\\[\\]()=>|/@])/g, '\\\\$1');
                };
                const cssPath = (node) => {
                  if (!(node instanceof Element)) return '';
                  const segments = [];
                  let current = node;
                  while (current && current.nodeType === Node.ELEMENT_NODE && segments.length < 8) {
                    let segment = current.tagName.toLowerCase();
                    if (current.id) {
                      segment += '#' + escapeIdent(current.id);
                      segments.unshift(segment);
                      break;
                    }
                    const siblings = Array.from(current.parentElement ? current.parentElement.children : []).filter((sib) => sib.tagName === current.tagName);
                    const index = siblings.indexOf(current);
                    if (index >= 0 && siblings.length > 1) {
                      segment += `:nth-of-type(${index + 1})`;
                    }
                    segments.unshift(segment);
                    current = current.parentElement;
                  }
                  return segments.join(' > ');
                };
                const primaryNodes = Array.from(document.querySelectorAll('a, button, input, select, textarea, [role]')).slice(0, 60);
                const cursorNodes = Array.from(document.querySelectorAll('[onclick], [tabindex], [style*="cursor"], [class*="cursor"]'))
                  .filter((node) => !primaryNodes.includes(node))
                  .slice(0, 40);
                const summarize = (node, ref) => ({
                  ref,
                  selector: cssPath(node),
                  tag: node.tagName.toLowerCase(),
                  role: node.getAttribute('role') || '',
                  text: (node.textContent || node.getAttribute('aria-label') || node.getAttribute('title') || '').replace(/\\s+/g, ' ').trim().slice(0, 120)
                });
                return [
                  ...primaryNodes.map((node, index) => summarize(node, `@e${index + 1}`)),
                  ...cursorNodes.map((node, index) => summarize(node, `@c${index + 1}`))
                ].filter((item) => item.selector);
            }"""
        )

    def _snapshot_page(
        self,
        page: Page,
        *,
        manager: BrowserSessionManager,
        target_name: str,
        kind: str,
        viewport_name: str,
        viewport: dict[str, int],
        label: str,
        annotate: bool,
        include_diff: bool,
    ) -> dict[str, Any]:
        html = page.content()
        page_text = _safe_page_text(page)
        dom_path = manager.write_dom_snapshot(f"{target_name}-{viewport_name}-{label}", html)
        tab_events = self._page_events.get(self._active_tab_id, {})
        console_messages = list(tab_events.get("console", []))
        network_events = list(tab_events.get("network", []))
        dialog_events = list(tab_events.get("dialogs", []))
        console_path = manager.write_console_log(f"{target_name}-{viewport_name}-{label}", console_messages)
        network_path = manager.write_network_log(f"{target_name}-{viewport_name}-{label}", network_events)
        dialog_path = manager.write_dialog_log(f"{target_name}-{viewport_name}-{label}", dialog_events)
        for entry in console_messages:
            manager.append_gstack_log("console", entry)
        for entry in network_events:
            manager.append_gstack_log("network", entry)
        for entry in dialog_events:
            manager.append_gstack_log("dialog", entry)
        annotated_path = None
        if annotate:
            annotated_path = manager.allocate_screenshot_path(f"{target_name}-{viewport_name}-{label}-annotated")
            page.screenshot(path=str(annotated_path), full_page=True)
            manager.update_session(evidence_ref=str(annotated_path))
        observation = _build_observation(
            page,
            target_name=target_name,
            kind=kind,
            source_url=page.url,
            viewport_name=viewport_name,
            viewport=viewport,
        )
        refs = self._capture_snapshot_refs(page)
        self._snapshot_ref_maps[self._active_tab_id] = {str(item.get("ref") or ""): dict(item) for item in refs if str(item.get("ref") or "").strip()}
        observation.update(
            {
                "label": label,
                "title": page.title(),
                "final_url": page.url,
                "dom_path": dom_path,
                "console_log_path": console_path,
                "network_log_path": network_path,
                "dialog_log_path": dialog_path,
                "request_failures": list(tab_events.get("request_failures", [])),
                "page_errors": list(tab_events.get("page_errors", [])),
                "dialogs": dialog_events,
                "console_messages": console_messages,
                "network_events": network_events,
                "page_text": page_text,
                "annotated_screenshot_path": str(annotated_path) if annotated_path else "",
                "refs": refs,
                "active_tab_id": self._active_tab_id,
            }
        )
        observation_path = manager.record_observation(f"{target_name}-{viewport_name}-{label}", observation)
        snapshot_path = manager.write_snapshot_artifact(f"{target_name}-{viewport_name}-{label}", observation)
        previous_snapshot = self._last_snapshot_payloads.get(self._active_tab_id) or {}
        diff_path = ""
        if include_diff or previous_snapshot:
            diff_text = _build_snapshot_diff(str(previous_snapshot.get("page_text") or ""), page_text)
            if diff_text.strip():
                diff_path = manager.write_diff_artifact(f"{target_name}-{viewport_name}-{label}", diff_text)
        self._last_snapshot_payloads[self._active_tab_id] = observation
        manager.update_session(last_snapshot_ref=snapshot_path, last_snapshot_diff_path=diff_path or None)
        return {
            "command": "snapshot",
            "label": label,
            "snapshot_path": snapshot_path,
            "diff_path": diff_path,
            "observation_path": observation_path,
            "console_log_path": console_path,
            "network_log_path": network_path,
            "dialog_log_path": dialog_path,
            "dom_path": dom_path,
            **observation,
        }

    def _handle_storage_state(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action") or "save").strip().lower()
        if action == "read":
            payload = json.loads(self.storage_state_path.read_text(encoding="utf-8")) if self.storage_state_path.exists() else {"cookies": [], "origins": []}
            return {
                "command": "storage_state",
                "action": action,
                "storage_state_path": str(self.storage_state_path),
                "value": payload,
                "active_tab_id": self._active_tab_id,
            }
        self._persist_storage_state()
        return {
            "command": "storage_state",
            "action": "save",
            "storage_state_path": str(self.storage_state_path),
            "active_tab_id": self._active_tab_id,
        }

    def _handle_cookie_import(self, command: dict[str, Any], manager: BrowserSessionManager) -> dict[str, Any]:
        import_kind = str(command.get("command") or "import_cookies").strip().lower() or "import_cookies"
        payload, import_meta = _load_cookie_payload(command, browser_safe_copy=import_kind == "cookie-import-browser")
        cookies = payload.get("cookies") or []
        if cookies:
            self._context.add_cookies(cookies)
            self._persist_storage_state()
        manager.update_session(cookies_imported=bool(cookies))
        return {
            "command": import_kind,
            "import_kind": import_kind,
            "count": len(cookies),
            "source_path": import_meta.get("source_path"),
            "source_copy_path": import_meta.get("source_copy_path"),
            "browser": import_meta.get("browser"),
            "browser_profile": import_meta.get("browser_profile"),
            "storage_state_path": str(self.storage_state_path),
            "active_tab_id": self._active_tab_id,
        }

    def _handle_single_cookie(self, command: dict[str, Any]) -> dict[str, Any]:
        raw_pair = str(command.get("value") or "").strip()
        name = str(command.get("name") or "").strip()
        value = str(command.get("cookie_value") or "").strip()
        if raw_pair and "=" in raw_pair and not name:
            name, value = raw_pair.split("=", 1)
        current_url = self._get_page().url
        parsed = urlparse(current_url)
        if not name or not parsed.hostname:
            raise ValueError("Cookie command requires a name/value and an active page URL.")
        cookie = {
            "name": name,
            "value": value,
            "domain": parsed.hostname,
            "path": str(command.get("path") or "/"),
            "httpOnly": bool(command.get("httpOnly", False)),
            "secure": parsed.scheme == "https",
            "sameSite": str(command.get("sameSite") or "Lax"),
        }
        self._context.add_cookies([cookie])
        self._persist_storage_state()
        return {
            "command": "cookie",
            "cookie": cookie,
            "storage_state_path": str(self.storage_state_path),
            "active_tab_id": self._active_tab_id,
        }

    def _handle_storage(
        self,
        command: dict[str, Any],
        manager: BrowserSessionManager,
        *,
        target_name: str,
        viewport_name: str,
    ) -> dict[str, Any]:
        page = self._get_page()
        action = str(command.get("action") or "read").strip().lower()
        if action == "set":
            key = str(command.get("key") or "").strip()
            value = str(command.get("value") or "").strip()
            page.evaluate("(payload) => localStorage.setItem(payload.key, payload.value)", {"key": key, "value": value})
            return {"command": "storage", "action": action, "key": key, "value": value, "active_tab_id": self._active_tab_id}
        payload = page.evaluate(
            """() => ({
                localStorage: Object.fromEntries(Object.keys(localStorage).map((key) => [key, localStorage.getItem(key)])),
                sessionStorage: Object.fromEntries(Object.keys(sessionStorage).map((key) => [key, sessionStorage.getItem(key)]))
            })"""
        )
        path = manager.write_json_artifact(manager.command_dir, f"{target_name}-{viewport_name}-storage", payload)
        return {"command": "storage", "action": "read", "value": payload, "path": path, "active_tab_id": self._active_tab_id}

    def _handle_buffer_dump(
        self,
        manager: BrowserSessionManager,
        *,
        target_name: str,
        viewport_name: str,
        buffer_name: str,
        page: Page,
        clear: bool = False,
        errors_only: bool = False,
    ) -> dict[str, Any]:
        tab_events = self._page_events.get(self._active_tab_id, {})
        items = list(tab_events.get(buffer_name, []))
        if buffer_name == "console" and errors_only:
            items = [item for item in items if str(item.get("type") or "").lower() in {"error", "warning"}]
        writer_map = {
            "console": manager.write_console_log,
            "network": manager.write_network_log,
            "dialogs": manager.write_dialog_log,
        }
        path = writer_map[buffer_name](f"{target_name}-{viewport_name}-{buffer_name}", items)
        for entry in items:
            manager.append_gstack_log(buffer_name if buffer_name != "dialogs" else "dialog", entry)
        if clear:
            tab_events[buffer_name] = []
        command_name = "dialog" if buffer_name == "dialogs" else buffer_name
        return {
            "command": command_name,
            "items": items,
            "count": len(items),
            "path": path,
            "url": page.url,
            "active_tab_id": self._active_tab_id,
        }

    def _capture_responsive(
        self,
        page: Page,
        *,
        manager: BrowserSessionManager,
        target_name: str,
        viewport_name: str,
        prefix: str,
    ) -> dict[str, Any]:
        original = page.viewport_size or {"width": 1280, "height": 720}
        captures: list[dict[str, Any]] = []
        try:
            for label, vp in (
                ("mobile", {"width": 375, "height": 812}),
                ("tablet", {"width": 768, "height": 1024}),
                ("desktop", {"width": 1280, "height": 720}),
            ):
                page.set_viewport_size(vp)
                _wait_for_settle(page)
                screenshot_path = manager.allocate_screenshot_path(f"{prefix}-{label}")
                page.screenshot(path=str(screenshot_path), full_page=True)
                manager.update_session(evidence_ref=str(screenshot_path))
                captures.append({"label": label, "viewport": vp, "path": str(screenshot_path)})
        finally:
            page.set_viewport_size({"width": int(original.get("width") or 1280), "height": int(original.get("height") or 720)})
        return {"command": "responsive", "captures": captures, "active_tab_id": self._active_tab_id, "url": page.url, "requested_from": viewport_name}

    def _diff_pages(
        self,
        command: dict[str, Any],
        *,
        manager: BrowserSessionManager,
        target_name: str,
        viewport_name: str,
    ) -> dict[str, Any]:
        url_a = str(command.get("url_a") or command.get("url1") or command.get("from") or "").strip()
        url_b = str(command.get("url_b") or command.get("url2") or command.get("to") or "").strip()
        if not url_a or not url_b:
            raise ValueError("Diff command requires url_a/url_b.")
        original_tab = self._active_tab_id
        first = self._new_tab(url=url_a)
        second = self._new_tab(url=url_b)
        text_a = _safe_page_text(self._pages[first])
        text_b = _safe_page_text(self._pages[second])
        diff_text = _build_snapshot_diff(text_a, text_b, from_label=url_a, to_label=url_b)
        diff_path = manager.write_diff_artifact(f"{target_name}-{viewport_name}-page-diff", diff_text)
        self._close_tab(second)
        self._close_tab(first)
        if original_tab in self._pages:
            self._switch_tab(original_tab)
        return {"command": "diff", "url_a": url_a, "url_b": url_b, "diff_path": diff_path, "active_tab_id": self._active_tab_id}

    def _new_tab(self, url: str | None = None, viewport: dict[str, int] | None = None) -> int:
        if self._context is None:
            raise RuntimeError("Browser context not started")
        page = self._context.new_page()
        tab_id = self._next_tab_id
        self._next_tab_id += 1
        self._pages[tab_id] = page
        self._page_events[tab_id] = {"console": [], "request_failures": [], "page_errors": [], "dialogs": [], "network": []}
        self._wire_page_events(tab_id, page)
        self._active_tab_id = tab_id
        if viewport:
            page.set_viewport_size(viewport)
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _wait_for_settle(page)
        self._refresh_tab_cache()
        return tab_id

    def _switch_tab(self, tab_id: int) -> None:
        if tab_id not in self._pages:
            raise ValueError(f"Tab {tab_id} not found")
        self._active_tab_id = tab_id
        self._refresh_tab_cache()

    def _close_tab(self, tab_id: int) -> None:
        page = self._pages.get(tab_id)
        if page is None:
            raise ValueError(f"Tab {tab_id} not found")
        page.close()
        self._pages.pop(tab_id, None)
        self._page_events.pop(tab_id, None)
        self._last_snapshot_payloads.pop(tab_id, None)
        remaining = sorted(self._pages.keys())
        if remaining:
            self._active_tab_id = remaining[-1]
        else:
            self._new_tab()
            return
        self._refresh_tab_cache()

    def _get_page(self) -> Page:
        page = self._pages.get(self._active_tab_id)
        if page is None:
            raise RuntimeError("No active browser page. Open a tab first.")
        return page

    def _wire_page_events(self, tab_id: int, page: Page) -> None:
        page.on(
            "console",
            lambda message, current_tab_id=tab_id: _append_buffer(
                self._page_events[current_tab_id]["console"],
                {"type": message.type, "text": message.text, "location": str(message.location or {})},
            ),
        )
        page.on(
            "pageerror",
            lambda error, current_tab_id=tab_id: _append_buffer(self._page_events[current_tab_id]["page_errors"], str(error)),
        )
        page.on(
            "requestfailed",
            lambda request, current_tab_id=tab_id: _append_buffer(
                self._page_events[current_tab_id]["request_failures"],
                f"{request.method} {request.url} -> {_request_failure_text(request)}",
            ),
        )
        page.on(
            "response",
            lambda response, current_tab_id=tab_id: _append_buffer(
                self._page_events[current_tab_id]["network"],
                {
                    "url": response.url,
                    "status": response.status,
                    "ok": response.ok,
                    "method": response.request.method,
                },
            ),
        )
        page.on("dialog", lambda dialog, current_tab_id=tab_id: self._handle_dialog(dialog, current_tab_id))

    def _handle_dialog(self, dialog, tab_id: int) -> None:
        _append_buffer(
            self._page_events[tab_id]["dialogs"],
            {"type": dialog.type, "message": dialog.message, "default_value": dialog.default_value},
        )
        try:
            if self._dialog_policy == "dismiss":
                dialog.dismiss()
            elif dialog.type == "prompt" and self._dialog_prompt_text is not None:
                dialog.accept(self._dialog_prompt_text)
            else:
                dialog.accept()
        except Exception:
            try:
                dialog.dismiss()
            except Exception:
                return
        finally:
            self._dialog_prompt_text = None

    def _persist_storage_state(self) -> None:
        if self._context is None:
            return
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(self.storage_state_path))

    def _switch_browser_visibility(self, *, headless: bool) -> dict[str, Any]:
        requested_headless = bool(headless)
        original_headless = bool(self.headless)
        if requested_headless == original_headless:
            return {
                "status": "unchanged",
                "requested_headless": requested_headless,
                "applied_headless": self.headless,
                "applied_headed": not self.headless,
            }
        saved_tabs = self._tab_summaries() or [
            {
                "tab_id": 1,
                "url": "about:blank",
                "active": True,
                "viewport_name": "desktop",
                "viewport": {"width": 1440, "height": 900},
            }
        ]
        active_tab_id = int(self._active_tab_id or 1)
        self._persist_storage_state()
        try:
            self._replace_browser(headless=requested_headless, tab_summaries=saved_tabs, active_tab_id=active_tab_id)
            return {
                "status": "applied",
                "requested_headless": requested_headless,
                "applied_headless": self.headless,
                "applied_headed": not self.headless,
                "tab_count": len(self._tab_summaries()),
            }
        except Exception as exc:
            self._replace_browser(headless=original_headless, tab_summaries=saved_tabs, active_tab_id=active_tab_id)
            return {
                "status": "fallback",
                "requested_headless": requested_headless,
                "applied_headless": self.headless,
                "applied_headed": not self.headless,
                "error": str(exc),
                "tab_count": len(self._tab_summaries()),
            }

    def _replace_browser(self, *, headless: bool, tab_summaries: list[dict[str, Any]], active_tab_id: int) -> None:
        if self._playwright is None:
            raise RuntimeError("Playwright runtime is not started.")
        for page in list(self._pages.values()):
            try:
                page.close()
            except Exception:
                continue
        self._pages = {}
        self._page_events = {}
        self._last_snapshot_payloads = {}
        self._snapshot_ref_maps = {}
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        storage_state = str(self.storage_state_path) if self.storage_state_path.exists() else None
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._context = self._browser.new_context(ignore_https_errors=True, storage_state=storage_state)
        self.headless = headless
        tab_id_map: dict[int, int] = {}
        for summary in tab_summaries:
            viewport = dict(summary.get("viewport") or {}) or {"width": 1440, "height": 900}
            url = str(summary.get("url") or "").strip()
            new_tab_id = self._new_tab(url=url if url and url != "about:blank" else None, viewport=viewport)
            tab_id_map[int(summary.get("tab_id") or new_tab_id)] = new_tab_id
        restored_active = tab_id_map.get(active_tab_id)
        if restored_active in self._pages:
            self._switch_tab(int(restored_active))
        self._refresh_tab_cache()

    def _tab_summaries(self) -> list[dict[str, Any]]:
        if self._thread_id is not None and threading.get_ident() != self._thread_id:
            return [dict(item) for item in self._tab_cache]
        self._refresh_tab_cache()
        return [dict(item) for item in self._tab_cache]

    def _refresh_tab_cache(self) -> None:
        summaries: list[dict[str, Any]] = []
        for tab_id in sorted(self._pages.keys()):
            page = self._pages[tab_id]
            viewport = page.viewport_size or {}
            summaries.append(
                {
                    "tab_id": tab_id,
                    "url": page.url,
                    "title": page.title() if page.url else "",
                    "active": tab_id == self._active_tab_id,
                    "viewport_name": _viewport_name_for_size(viewport),
                    "viewport": viewport,
                    "last_command_at": self._last_activity_at,
                }
            )
        self._tab_cache = summaries

    def _status_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "service_kind": "playwright_persistent_runtime",
            "service_status": "handoff" if self._handoff_active else ("ready" if self._started else "stopped"),
            "service_started_at": self._started_at,
            "service_auth_token": self._auth_token,
            "idle_timeout_minutes": self.idle_timeout_minutes,
            "last_activity_at": self._last_activity_at,
            "headless": self.headless,
            "headed": not self.headless,
            "handoff_active": self._handoff_active,
            "handoff_reason": self._handoff_reason,
            "active_tab_id": self._active_tab_id,
            "command_count": self._command_count,
            "tabs": self._tab_summaries(),
            "storage_state_path": str(self.storage_state_path),
        }

    def _write_service_state(self, manager: BrowserSessionManager, *, status: str) -> None:
        manager.update_session(
            service_status=status,
            service_started_at=self._started_at,
            service_auth_token=self._auth_token,
            handoff_active=self._handoff_active,
            handoff_reason=self._handoff_reason,
        )
        manager.write_service_state(
            {
                "session_id": self.session_id,
                "auth_token": self._auth_token,
                "service_kind": "playwright_persistent_runtime",
                "status": status,
                "started_at": self._started_at,
                "last_activity_at": self._last_activity_at,
                "idle_timeout_minutes": self.idle_timeout_minutes,
                "headless": self.headless,
                "headed": not self.headless,
                "active_tab_id": self._active_tab_id,
                "tabs": self._tab_summaries(),
                "handoff_active": self._handoff_active,
                "handoff_reason": self._handoff_reason,
            }
        )

    def _idle_expired(self) -> bool:
        try:
            last_activity = datetime.fromisoformat(self._last_activity_at)
        except ValueError:
            return False
        return datetime.now() - last_activity > timedelta(minutes=self.idle_timeout_minutes)

    def _touch(self) -> None:
        self._last_activity_at = datetime.now().isoformat(timespec="seconds")


def execute_browser_commands(
    manager: BrowserSessionManager,
    commands: list[dict[str, Any]],
    *,
    target_name: str,
    kind: str = "current",
    viewport_name: str = "desktop",
    viewport: dict[str, int] | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    snapshot = manager.ensure_session()
    response = _send_browser_host_command(
        manager,
        {
            "task_id": manager.task_id,
            "commands": commands,
            "target_name": target_name,
            "kind": kind,
            "viewport_name": viewport_name,
            "viewport": viewport or DEFAULT_VIEWPORTS[0][1],
        },
        headless=headless,
    )
    manager.update_session(
        status="ready" if str(response.get("service_status") or "") != "stopped" else "stopped",
        active_tab_id=_coerce_int(response.get("active_tab_id")),
        tabs=response.get("tabs") if isinstance(response.get("tabs"), list) else snapshot.tabs,
        command_count=int(response.get("command_count") or snapshot.command_count or 0),
        last_command_at=str(response.get("last_activity_at") or snapshot.last_command_at or ""),
        service_status=str(response.get("service_status") or snapshot.service_status or "ready"),
        service_started_at=str(response.get("service_started_at") or snapshot.service_started_at or ""),
        service_auth_token=str(response.get("service_auth_token") or snapshot.service_auth_token or ""),
        handoff_active=bool(response.get("handoff_active")),
        handoff_reason=str(response.get("handoff_reason") or ""),
    )
    return response


def run_browser_capture(
    manager: BrowserSessionManager,
    targets: list[BrowserTarget],
    *,
    headless: bool = True,
) -> dict[str, Any]:
    snapshot = manager.ensure_session(target_url=targets[0].url if targets else None)
    results: list[dict[str, Any]] = []
    if not targets:
        return {"snapshot": snapshot, "results": results}

    for target in targets:
        for viewport_name, viewport in _resolve_viewports(target.viewports):
            execution = execute_browser_commands(
                manager,
                _build_capture_command_plan(target, viewport),
                target_name=target.name,
                kind=target.kind,
                viewport_name=viewport_name,
                viewport=viewport,
                headless=headless,
            )
            results.append(
                _compose_capture_result(
                    target,
                    viewport_name=viewport_name,
                    viewport=viewport,
                    command_results=execution.get("results") or [],
                )
            )

    refreshed_snapshot = manager.load_session() or snapshot
    return {"snapshot": refreshed_snapshot, "results": results}


def supported_browser_commands() -> tuple[str, ...]:
    return (
        "goto",
        "back",
        "forward",
        "reload",
        "url",
        "click",
        "fill",
        "type",
        "hover",
        "press",
        "scroll",
        "select",
        "wait",
        "screenshot",
        "snapshot",
        "chain",
        "js",
        "evaluate",
        "tab",
        "tabs",
        "newtab",
        "closetab",
        "storage_state",
        "import_cookies",
        "cookie-import",
        "cookie-import-browser",
        "browser-sources",
        "cookie",
        "cookies",
        "storage",
        "console",
        "network",
        "dialog",
        "dialog-accept",
        "dialog-dismiss",
        "text",
        "links",
        "forms",
        "html",
        "attrs",
        "accessibility",
        "is",
        "upload",
        "pdf",
        "perf",
        "responsive",
        "diff",
        "status",
        "handoff",
        "resume",
        "stop",
        "viewport",
    )


def get_browser_service_status(manager: BrowserSessionManager) -> dict[str, Any]:
    snapshot = manager.ensure_session()
    browse_state = manager.load_browse_state()
    if browse_state and _browse_state_compatible(manager, browse_state, _current_binary_version()) and _host_is_healthy(browse_state):
        try:
            health = _post_host_request(browse_state, "/health", None, include_auth=False)
            return _merge_status_payload(snapshot, browse_state, health)
        except Exception:
            manager.clear_browse_state()
    service_state = manager.load_service_state()
    return _merge_status_payload(snapshot, browse_state or service_state, {})


def _ensure_runtime(
    session_id: str,
    storage_state_path: Path,
    *,
    idle_timeout_minutes: int,
    headless: bool,
) -> _BrowserRuntimeService:
    with _RUNTIME_LOCK:
        runtime = _RUNTIMES.get(session_id)
        if runtime is None or not runtime.is_healthy():
            runtime = _BrowserRuntimeService(
                session_id,
                storage_state_path,
                idle_timeout_minutes=idle_timeout_minutes,
                headless=headless,
            )
            _RUNTIMES[session_id] = runtime
        return runtime


def _send_browser_host_command(
    manager: BrowserSessionManager,
    payload: dict[str, Any],
    *,
    headless: bool,
    allow_restart: bool = True,
) -> dict[str, Any]:
    browse_state = _ensure_browser_host(manager, headless=headless)
    try:
        return _post_host_request(browse_state, "/command", payload)
    except Exception:
        if not allow_restart:
            raise
        _terminate_browser_host(browse_state)
        manager.clear_browse_state()
        restarted_state = _ensure_browser_host(manager, headless=headless, force_restart=True)
        return _post_host_request(restarted_state, "/command", payload)


def _ensure_browser_host(
    manager: BrowserSessionManager,
    *,
    headless: bool,
    force_restart: bool = False,
) -> dict[str, Any]:
    snapshot = manager.ensure_session()
    expected_version = _current_binary_version()
    existing = manager.load_browse_state()
    if not force_restart and existing and _browse_state_compatible(manager, existing, expected_version) and _host_is_healthy(existing):
        return existing
    if existing:
        _terminate_browser_host(existing)
        manager.clear_browse_state()
    process = _spawn_browser_host(manager, snapshot.session_id, expected_version, headless=headless)
    _SPAWNED_HOST_PIDS.add(process.pid)
    deadline = time.time() + HOST_START_TIMEOUT_SECONDS
    last_error: str | None = None
    while time.time() < deadline:
        time.sleep(0.25)
        browse_state = manager.load_browse_state()
        if browse_state and _browse_state_compatible(manager, browse_state, expected_version):
            try:
                _post_host_request(browse_state, "/health", None, include_auth=False)
                return browse_state
            except Exception as exc:  # pragma: no cover - defensive against racey startup
                last_error = str(exc)
        if process.poll() is not None:
            break
    raise RuntimeError(f"Browse host did not become healthy for {manager.repo_path}. {last_error or 'startup failed'}")


def _spawn_browser_host(
    manager: BrowserSessionManager,
    session_id: str,
    expected_version: str,
    *,
    headless: bool,
) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    src_path = str(ROOT_DIR / "src")
    existing_pythonpath = str(env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    command = [
        sys.executable,
        str(SERVER_ENTRYPOINT),
        "--repo-path",
        str(manager.repo_path),
        "--task-id",
        str(manager.task_id),
        "--session-id",
        session_id,
        "--idle-timeout-minutes",
        str(manager.idle_timeout_minutes),
        "--binary-version",
        expected_version,
    ]
    if not headless:
        command.append("--headed")
    kwargs: dict[str, Any] = {
        "cwd": str(ROOT_DIR),
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, **kwargs)
    _SPAWNED_HOST_PROCESSES[process.pid] = process
    return process


def _browse_state_compatible(
    manager: BrowserSessionManager,
    browse_state: dict[str, Any],
    expected_version: str,
) -> bool:
    return bool(
        str(browse_state.get("workspaceRoot") or "").strip() == str(manager.repo_path)
        and str(browse_state.get("binaryVersion") or "").strip() == expected_version
        and int(browse_state.get("pid") or 0) > 0
        and int(browse_state.get("port") or 0) > 0
        and str(browse_state.get("token") or "").strip()
    )


def _host_is_healthy(browse_state: dict[str, Any]) -> bool:
    try:
        _post_host_request(browse_state, "/health", None, include_auth=False)
        return True
    except Exception:
        return False


def _post_host_request(
    browse_state: dict[str, Any],
    path: str,
    payload: dict[str, Any] | None,
    *,
    include_auth: bool = True,
) -> dict[str, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", int(browse_state["port"]), timeout=HOST_REQUEST_TIMEOUT_SECONDS)
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    token = str(browse_state.get("token") or "").strip()
    if include_auth and token:
        headers["Authorization"] = f"Bearer {token}"
    connection.request("POST", path, body=body, headers=headers)
    response = connection.getresponse()
    text = response.read().decode("utf-8")
    if response.status >= 400:
        raise RuntimeError(f"Browse host request failed: {response.status} {text}")
    payload = json.loads(text) if text.strip() else {}
    return payload if isinstance(payload, dict) else {}


def _merge_status_payload(
    snapshot: Any,
    state_payload: dict[str, Any],
    live_payload: dict[str, Any],
) -> dict[str, Any]:
    live = dict(live_payload or {})
    state = dict(state_payload or {})
    return {
        "session_id": live.get("session_id") or state.get("session_id") or snapshot.session_id,
        "service_kind": live.get("service_kind") or state.get("serviceKind") or state.get("service_kind") or snapshot.service_kind,
        "service_status": live.get("service_status") or state.get("status") or snapshot.service_status,
        "service_started_at": live.get("service_started_at") or state.get("startedAt") or state.get("started_at") or snapshot.service_started_at,
        "service_auth_token": live.get("service_auth_token") or state.get("token") or state.get("auth_token") or snapshot.service_auth_token,
        "idle_timeout_minutes": live.get("idle_timeout_minutes") or state.get("idleTimeoutMinutes") or snapshot.idle_timeout_minutes,
        "last_activity_at": live.get("last_activity_at") or state.get("lastActivityAt") or state.get("last_activity_at") or snapshot.last_seen_at,
        "headless": bool(live.get("headless") if "headless" in live else state.get("headless", True)),
        "headed": bool(live.get("headed") if "headed" in live else state.get("headed", False)),
        "handoff_active": bool(live.get("handoff_active") or state.get("handoffActive") or state.get("handoff_active") or snapshot.handoff_active),
        "handoff_reason": live.get("handoff_reason") or state.get("handoffReason") or state.get("handoff_reason") or snapshot.handoff_reason,
        "active_tab_id": live.get("active_tab_id") or state.get("activeTabId") or state.get("active_tab_id") or snapshot.active_tab_id,
        "command_count": live.get("command_count") or state.get("commandCount") or snapshot.command_count,
        "tabs": live.get("tabs") or state.get("tabs") or snapshot.tabs,
        "storage_state_path": live.get("storage_state_path") or snapshot.storage_state_path,
        "pid": state.get("pid"),
        "port": state.get("port"),
        "binary_version": state.get("binaryVersion") or state.get("binary_version"),
        "workspace_root": state.get("workspaceRoot") or state.get("workspace_root") or str(snapshot.workspace_key),
    }


def _terminate_browser_host(browse_state: dict[str, Any]) -> None:
    pid = int(browse_state.get("pid") or 0)
    if pid <= 0:
        return
    process = _SPAWNED_HOST_PROCESSES.pop(pid, None)
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    if process is not None:
        try:
            process.wait(timeout=3)
        except Exception:
            pass


def _current_binary_version() -> str:
    digest = hashlib.sha1()
    for path in (
        ROOT_DIR / "src" / "agentsystem" / "runtime" / "playwright_browser_runtime.py",
        ROOT_DIR / "src" / "agentsystem" / "runtime" / "browser_session_manager.py",
        ROOT_DIR / "src" / "agentsystem" / "runtime" / "browser_host_server.py",
    ):
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _build_capture_command_plan(target: BrowserTarget, viewport: dict[str, int]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = [
        {"command": "tab", "action": "new"},
        {"command": "viewport", "width": viewport["width"], "height": viewport["height"]},
        {"command": "goto", "url": target.url},
        {"command": "screenshot", "label": "before"},
        {"command": "snapshot", "label": "before", "annotate": True},
    ]
    commands.extend(_normalize_action_commands(target.actions))
    commands.extend(
        [
            {"command": "screenshot", "label": "after"},
            {"command": "snapshot", "label": "after", "annotate": True, "diff": True},
            {"command": "storage_state", "action": "save"},
        ]
    )
    return commands


def _normalize_action_commands(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    allowed = set(supported_browser_commands())
    for action in actions:
        command = _normalize_command(action)
        if command["command"] in allowed:
            normalized.append(command)
    return normalized


def _compose_capture_result(
    target: BrowserTarget,
    *,
    viewport_name: str,
    viewport: dict[str, int],
    command_results: list[dict[str, Any]],
) -> dict[str, Any]:
    before_snapshot = _last_command_result(command_results, "snapshot", label="before")
    after_snapshot = _last_command_result(command_results, "snapshot", label="after") or before_snapshot or {}
    before_screenshot = _last_command_result(command_results, "screenshot", label="before")
    after_screenshot = _last_command_result(command_results, "screenshot", label="after")
    failed_commands = [result for result in command_results if result.get("ok") is False]
    status_code = int(_last_non_empty(command_results, "status_code") or after_snapshot.get("status_code") or 0)
    final_url = str(after_snapshot.get("final_url") or after_snapshot.get("url") or target.url)
    title = str(after_snapshot.get("title") or "").strip()
    request_failures = [str(item) for item in after_snapshot.get("request_failures") or [] if str(item).strip()]
    page_errors = [str(item) for item in after_snapshot.get("page_errors") or [] if str(item).strip()]
    blocking_findings = _find_blocking_issues(status_code, final_url, page_errors, request_failures)
    blocking_findings.extend(
        f"Command {result['command']} failed: {result['error']}"
        for result in failed_commands
        if str(result.get("error") or "").strip()
    )
    important_findings = _find_important_issues(
        title,
        after_snapshot,
        list(after_snapshot.get("console_messages") or after_snapshot.get("console") or []),
    )
    return {
        "name": target.name,
        "url": target.url,
        "kind": target.kind,
        "viewport": viewport,
        "viewport_name": viewport_name,
        "tab_id": after_snapshot.get("active_tab_id"),
        "status_code": status_code,
        "title": title,
        "excerpt": str(after_snapshot.get("excerpt") or ""),
        "final_url": final_url,
        "screenshot_path": str((after_screenshot or {}).get("path") or ""),
        "dom_path": str(after_snapshot.get("dom_path") or ""),
        "console_log_path": str(after_snapshot.get("console_log_path") or ""),
        "network_log_path": str(after_snapshot.get("network_log_path") or ""),
        "dialog_log_path": str(after_snapshot.get("dialog_log_path") or ""),
        "snapshot_path": str(after_snapshot.get("snapshot_path") or ""),
        "snapshot_diff_path": str(after_snapshot.get("diff_path") or ""),
        "observation_path": str(after_snapshot.get("observation_path") or ""),
        "before_screenshot_path": str((before_screenshot or {}).get("path") or ""),
        "before_observation_path": str((before_snapshot or {}).get("observation_path") or ""),
        "before_dom_path": str((before_snapshot or {}).get("dom_path") or ""),
        "command_results": command_results,
        "console_messages": list(after_snapshot.get("console_messages") or after_snapshot.get("console") or []),
        "request_failures": request_failures,
        "page_errors": page_errors,
        "blocking_findings": blocking_findings,
        "important_findings": important_findings,
        **{key: value for key, value in after_snapshot.items() if key not in {"command", "label", "value"}},
    }


def _normalize_command(raw_command: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw_command)
    command = str(payload.get("command") or payload.get("type") or "").strip().lower()
    if not command:
        action_value = str(payload.get("action") or "").strip().lower()
        if action_value in supported_browser_commands() or action_value in {"capture", "fill", "js"}:
            command = action_value
    alias_map = {
        "capture": "screenshot",
        "fill": "type",
        "js": "evaluate",
        "newtab": "tab",
        "closetab": "tab",
        "tabs": "tab",
        "cookie-import": "import_cookies",
    }
    command = alias_map.get(command, command)
    if command == "tab":
        original = str(payload.get("command") or payload.get("type") or "").strip().lower()
        if original == "newtab":
            payload["action"] = "new"
        elif original == "closetab":
            payload["action"] = "close"
        elif original == "tabs":
            payload["action"] = "list"
    if command == "type" and payload.get("value") is None and payload.get("text") is not None:
        payload["value"] = payload.get("text")
    if command == "evaluate" and payload.get("expression") is None and payload.get("script") is not None:
        payload["expression"] = payload.get("script")
    if not command:
        raise ValueError("Missing browser command")
    payload["command"] = command
    return payload


def _coerce_viewport(command: dict[str, Any]) -> dict[str, int] | None:
    if command.get("width") and command.get("height"):
        return {"width": int(command["width"]), "height": int(command["height"])}
    viewport = command.get("viewport")
    if isinstance(viewport, dict):
        width = int(viewport.get("width") or 0)
        height = int(viewport.get("height") or 0)
        if width and height:
            return {"width": width, "height": height}
    return None


def _last_command_result(results: list[dict[str, Any]], command: str, *, label: str | None = None) -> dict[str, Any] | None:
    for result in reversed(results):
        if str(result.get("command") or "").strip() != command:
            continue
        if label is not None and str(result.get("label") or "").strip() != label:
            continue
        return result
    return None


def _last_non_empty(results: list[dict[str, Any]], key: str) -> Any:
    for result in reversed(results):
        value = result.get(key)
        if value not in (None, "", []):
            return value
    return None


def _resolve_viewports(raw_viewports: list[dict[str, Any]]) -> list[tuple[str, dict[str, int]]]:
    if not raw_viewports:
        return list(DEFAULT_VIEWPORTS)
    result: list[tuple[str, dict[str, int]]] = []
    for item in raw_viewports:
        label = str(item.get("name") or item.get("label") or "custom").strip() or "custom"
        width = int(item.get("width") or 1440)
        height = int(item.get("height") or 900)
        result.append((label, {"width": width, "height": height}))
    return result or list(DEFAULT_VIEWPORTS)


def _wait_for_settle(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightError:
        try:
            page.wait_for_timeout(1200)
        except PlaywrightError:
            return


def _build_observation(
    page: Page,
    *,
    target_name: str,
    kind: str,
    source_url: str,
    viewport_name: str,
    viewport: dict[str, int],
) -> dict[str, Any]:
    payload = page.evaluate(
        """() => {
            const textList = (selectors, limit = 12) =>
              Array.from(document.querySelectorAll(selectors))
                .map((node) => (node.textContent || "").replace(/\\s+/g, " ").trim())
                .filter(Boolean)
                .slice(0, limit);
            const bodyText = (document.body?.innerText || "").replace(/\\s+/g, " ").trim();
            const hasSearch = !!document.querySelector('input[type="search"], input[placeholder*="search" i], form input[name*="search" i]');
            const statBlocks = textList('[class*="stat" i], [class*="metric" i], [data-stat]', 10);
            const filterLabels = textList('aside label, form label, [aria-label*="filter" i], [class*="filter" i] label', 12);
            const sponsorLabels = textList('[class*="sponsor" i], [data-sponsored], [class*="featured" i]', 10);
            const viewControls = textList('[data-view-controls] a, [data-view-controls] button, [role="tab"], [class*="tab" i] a, [class*="tab" i] button', 16);
            const matrixHeaders = textList('[data-matrix-section] th, table th, [class*="matrix" i] th', 16);
            const riskLabels = textList('[data-risk-section] h2, [data-risk-section] h3, [data-risk-section] li, [class*="risk" i] h2, [class*="risk" i] h3', 16);
            const evidenceLabels = textList('[data-evidence-block] strong, [data-evidence-block] h3, [class*="evidence" i] strong, [class*="evidence" i] h3', 16);
            const refreshStateEl = document.querySelector('[data-refresh-state]');
            const refreshMessage = ((refreshStateEl?.querySelector('.refresh-text')?.textContent || '')).replace(/\\s+/g, ' ').trim();
            const refreshPresent = !!refreshStateEl || Array.from(document.querySelectorAll('button')).some((node) => /刷新|抓取|refresh/i.test(node.textContent || ''));
            const cards = document.querySelectorAll('article, [class*="card" i], [data-card]').length;
            return {
              nav_items: textList('nav a, header a, [role="navigation"] a', 16),
              headings: textList('h1, h2, h3', 16),
              cta_labels: textList('main a, main button', 16),
              tabs: textList('[role="tab"], [aria-selected="true"], main button, main a', 16),
              category_labels: textList('[class*="category" i] a, [class*="category" i] button, [data-category]', 16),
              content_sections: textList('main section h2, main section h3', 16),
              filter_labels: filterLabels,
              sponsor_labels: sponsorLabels,
              stat_blocks: statBlocks,
              view_controls: viewControls,
              matrix_headers: matrixHeaders,
              risk_labels: riskLabels,
              evidence_labels: evidenceLabels,
              refresh_state: refreshStateEl?.getAttribute('data-refresh-state') || '',
              refresh_message: refreshMessage,
              search_present: hasSearch,
              matrix_present: matrixHeaders.length > 0,
              risk_present: riskLabels.length > 0,
              evidence_present: evidenceLabels.length > 0,
              refresh_present: refreshPresent,
              nav_count: textList('nav a, header a, [role="navigation"] a', 32).length,
              heading_count: textList('h1, h2, h3', 32).length,
              cta_count: textList('main a, main button', 32).length,
              tab_count: textList('[role="tab"], [aria-selected="true"], main button, main a', 32).length,
              category_count: textList('[class*="category" i] a, [class*="category" i] button, [data-category]', 32).length,
              filter_count: filterLabels.length,
              sponsor_count: sponsorLabels.length,
              stat_count: statBlocks.length,
              view_count: viewControls.length,
              matrix_count: matrixHeaders.length,
              risk_count: riskLabels.length,
              evidence_count: evidenceLabels.length,
              card_count: cards,
              excerpt: bodyText.slice(0, 1200),
            };
        }"""
    )
    return {
        "target_name": target_name,
        "kind": kind,
        "url": source_url,
        "viewport_name": viewport_name,
        "viewport": viewport,
        "title": page.title(),
        "status_code": 0,
        "final_url": page.url,
        **payload,
    }


def _find_blocking_issues(
    status_code: int,
    final_url: str,
    page_errors: list[str],
    request_failures: list[str],
) -> list[str]:
    findings: list[str] = []
    if status_code >= 400:
        findings.append(f"{final_url} returned HTTP {status_code}.")
    for error in page_errors[:5]:
        findings.append(f"Page runtime error: {error}")
    for failure in request_failures[:5]:
        if _is_ignorable_request_failure(failure):
            continue
        findings.append(f"Critical request failed: {failure}")
    return findings


def _find_important_issues(
    title: str,
    observation: dict[str, Any],
    console_messages: list[dict[str, str]],
) -> list[str]:
    findings: list[str] = []
    if not title:
        findings.append("Page is missing a clear title.")
    error_logs = [str(item.get("text") or "").strip() for item in console_messages if item.get("type") == "error"]
    for log in error_logs[:3]:
        findings.append(f"Console error: {log}")
    if not observation.get("headings"):
        findings.append("No visible heading hierarchy was detected.")
    return findings


def _request_failure_text(request) -> str:
    failure = request.failure
    if failure is None:
        return "request failed"
    if isinstance(failure, str):
        return failure
    error_text = getattr(failure, "error_text", None)
    if isinstance(error_text, str) and error_text.strip():
        return error_text
    if isinstance(failure, dict):
        text = str(failure.get("errorText") or failure.get("error_text") or "").strip()
        if text:
            return text
    return str(failure)


def _load_cookie_payload(
    command: dict[str, Any],
    *,
    browser_safe_copy: bool = False,
) -> tuple[dict[str, Any], dict[str, str | None]]:
    if isinstance(command.get("cookies"), list):
        return {"cookies": command.get("cookies") or [], "origins": []}, {"source_path": None, "source_copy_path": None}
    source = str(command.get("source") or command.get("path") or "").strip()
    discovered_sources: list[dict[str, Any]] = []
    if browser_safe_copy and not source:
        discovered_sources = _discover_browser_cookie_sources(command)
        if not discovered_sources:
            raise FileNotFoundError("No local browser cookie source could be discovered.")
        source = str(discovered_sources[0].get("source_path") or "").strip()
    if not source:
        return {"cookies": [], "origins": []}, {"source_path": None, "source_copy_path": None, "browser": None, "browser_profile": None}
    source_path = Path(source).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Cookie source not found: {source_path}")
    read_path = source_path
    source_copy_path: str | None = None
    if browser_safe_copy:
        temp_dir = Path(tempfile.mkdtemp(prefix="agentsystem-browser-cookie-copy-"))
        copied_path = temp_dir / source_path.name
        shutil.copy2(source_path, copied_path)
        read_path = copied_path
        source_copy_path = str(copied_path)
    payload = _read_cookie_source_payload(read_path)
    selected_source = discovered_sources[0] if discovered_sources else {}
    if isinstance(payload, dict) and "cookies" in payload:
        return (
            {"cookies": payload.get("cookies") or [], "origins": payload.get("origins") or []},
            {
                "source_path": str(source_path),
                "source_copy_path": source_copy_path,
                "browser": str(selected_source.get("browser") or command.get("browser") or ""),
                "browser_profile": str(selected_source.get("profile") or command.get("profile") or ""),
            },
        )
    if isinstance(payload, list):
        return (
            {"cookies": payload, "origins": []},
            {
                "source_path": str(source_path),
                "source_copy_path": source_copy_path,
                "browser": str(selected_source.get("browser") or command.get("browser") or ""),
                "browser_profile": str(selected_source.get("profile") or command.get("profile") or ""),
            },
        )
    raise ValueError(f"Unsupported cookie payload: {source_path}")


def _read_cookie_source_payload(source_path: Path) -> Any:
    if source_path.suffix.lower() in {".sqlite", ".db"} or source_path.name.lower() in {"cookies", "cookies.sqlite"}:
        return _load_cookie_payload_from_sqlite(source_path)
    return json.loads(source_path.read_text(encoding="utf-8"))


def _load_cookie_payload_from_sqlite(source_path: Path) -> dict[str, Any]:
    query_candidates = (
        (
            "SELECT host_key, path, is_secure, is_httponly, expires_utc, name, value, samesite FROM cookies",
            "chromium",
        ),
        (
            "SELECT host, path, isSecure, isHttpOnly, expiry, name, value, sameSite FROM moz_cookies",
            "firefox",
        ),
    )
    cookies: list[dict[str, Any]] = []
    connection = sqlite3.connect(str(source_path))
    try:
        for query, flavor in query_candidates:
            try:
                rows = list(connection.execute(query))
            except sqlite3.Error:
                continue
            if flavor == "chromium":
                for host, path, is_secure, is_http_only, expires_utc, name, value, same_site in rows:
                    if not str(name or "").strip() or not str(host or "").strip():
                        continue
                    if value in (None, ""):
                        continue
                    cookie = {
                        "name": str(name),
                        "value": str(value),
                        "domain": str(host),
                        "path": str(path or "/"),
                        "secure": bool(is_secure),
                        "httpOnly": bool(is_http_only),
                        "sameSite": _normalize_same_site(same_site),
                    }
                    expires = _convert_chromium_cookie_expiry(expires_utc)
                    if expires is not None:
                        cookie["expires"] = expires
                    cookies.append(cookie)
            else:
                for host, path, is_secure, is_http_only, expiry, name, value, same_site in rows:
                    if not str(name or "").strip() or not str(host or "").strip():
                        continue
                    cookie = {
                        "name": str(name),
                        "value": str(value or ""),
                        "domain": str(host),
                        "path": str(path or "/"),
                        "secure": bool(is_secure),
                        "httpOnly": bool(is_http_only),
                        "sameSite": _normalize_same_site(same_site),
                    }
                    expires = int(expiry or 0) or None
                    if expires is not None:
                        cookie["expires"] = expires
                    cookies.append(cookie)
            if cookies:
                break
    finally:
        connection.close()
    return {"cookies": cookies, "origins": []}


def _normalize_same_site(value: Any) -> str:
    mapping = {
        0: "Lax",
        1: "Lax",
        2: "Strict",
        3: "None",
        "0": "Lax",
        "1": "Lax",
        "2": "Strict",
        "3": "None",
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }
    normalized = mapping.get(value)
    if normalized:
        return normalized
    text = str(value or "").strip().lower()
    return mapping.get(text, "Lax")


def _convert_chromium_cookie_expiry(value: Any) -> int | None:
    try:
        raw = int(value or 0)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    unix_seconds = int((raw / 1_000_000) - 11_644_473_600)
    return unix_seconds if unix_seconds > 0 else None


def _discover_browser_cookie_sources(command: dict[str, Any]) -> list[dict[str, Any]]:
    local_appdata = str(command.get("local_appdata") or os.environ.get("LOCALAPPDATA") or "").strip()
    appdata = str(command.get("appdata") or os.environ.get("APPDATA") or "").strip()
    explicit_sources = [str(item).strip() for item in (command.get("browser_source_candidates") or []) if str(item).strip()]
    candidates: list[dict[str, Any]] = []

    def _append(browser: str, profile: str, path_text: str) -> None:
        path = Path(path_text).expanduser()
        if path.exists():
            candidates.append(
                {
                    "browser": browser,
                    "profile": profile,
                    "label": f"{browser.title()} {profile}",
                    "source_path": str(path),
                }
            )

    for path_text in explicit_sources:
        _append("custom", "provided", path_text)
    if local_appdata:
        _append("chrome", "Default", str(Path(local_appdata) / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"))
        _append("chrome", "Default", str(Path(local_appdata) / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies"))
        _append("edge", "Default", str(Path(local_appdata) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cookies"))
        _append("edge", "Default", str(Path(local_appdata) / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies"))
    if appdata:
        firefox_profiles = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
        if firefox_profiles.exists():
            for profile_dir in sorted(firefox_profiles.glob("*")):
                _append("firefox", profile_dir.name, str(profile_dir / "cookies.sqlite"))
    browser_filter = str(command.get("browser") or "").strip().lower()
    if browser_filter:
        candidates = [item for item in candidates if str(item.get("browser") or "").strip().lower() == browser_filter]
    order = {"chrome": 0, "edge": 1, "firefox": 2, "custom": 3}
    return sorted(candidates, key=lambda item: (order.get(str(item.get("browser") or ""), 99), str(item.get("profile") or "")))


def _viewport_name_for_size(viewport: dict[str, Any]) -> str:
    width = int(viewport.get("width") or 0)
    if width and width <= 430:
        return "mobile"
    if width and width <= 900:
        return "tablet"
    return "desktop"


def _is_ignorable_request_failure(failure: str) -> bool:
    text = str(failure or "").strip()
    if not text:
        return True
    if "_rsc=" in text and "ERR_ABORTED" in text:
        return True
    if "ERR_BLOCKED_BY_ORB" in text:
        return True
    return False


def _ensure_reaper_started() -> None:
    global _REAPER_STARTED
    with _RUNTIME_LOCK:
        if _REAPER_STARTED:
            return
        thread = threading.Thread(target=_runtime_reaper_loop, daemon=True)
        thread.start()
        _REAPER_STARTED = True


def _runtime_reaper_loop() -> None:
    while True:
        time.sleep(SERVICE_POLL_SECONDS)
        stale: list[_BrowserRuntimeService] = []
        with _RUNTIME_LOCK:
            for runtime in list(_RUNTIMES.values()):
                if runtime.is_healthy() and runtime._idle_expired():
                    stale.append(runtime)
        for runtime in stale:
            runtime.close(reason="idle_timeout")


def _append_buffer(buffer: list[Any], item: Any, *, limit: int = 200) -> None:
    buffer.append(item)
    if len(buffer) > limit:
        del buffer[:-limit]


def _safe_page_text(page: Page) -> str:
    try:
        return str(page.locator("body").inner_text(timeout=5000) or "").strip()
    except Exception:
        return ""


def _build_snapshot_diff(
    before_text: str,
    after_text: str,
    *,
    from_label: str = "before",
    to_label: str = "after",
) -> str:
    before_lines = [line for line in before_text.splitlines() if line.strip()]
    after_lines = [line for line in after_text.splitlines() if line.strip()]
    diff = difflib.unified_diff(before_lines, after_lines, fromfile=from_label, tofile=to_label, lineterm="")
    return "\n".join(diff).strip() + "\n"


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _shutdown_runtimes() -> None:
    with _RUNTIME_LOCK:
        for runtime in list(_RUNTIMES.values()):
            runtime.close(remove_runtime=False)
        _RUNTIMES.clear()
    for pid in list(_SPAWNED_HOST_PIDS):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            continue
        finally:
            _SPAWNED_HOST_PIDS.discard(pid)
            process = _SPAWNED_HOST_PROCESSES.pop(pid, None)
            if process is not None:
                try:
                    process.wait(timeout=3)
                except Exception:
                    pass


atexit.register(_shutdown_runtimes)
