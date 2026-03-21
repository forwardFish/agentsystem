from __future__ import annotations

import argparse
import atexit
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agentsystem.runtime.browser_session_manager import BrowserSessionManager
from agentsystem.runtime.playwright_browser_runtime import _BrowserRuntimeService


class BrowseHostServer:
    def __init__(
        self,
        *,
        repo_path: Path,
        task_id: str,
        session_id: str,
        idle_timeout_minutes: int,
        binary_version: str,
        headless: bool,
        port: int = 0,
    ) -> None:
        self.repo_path = repo_path.resolve()
        self.task_id = task_id
        self.session_id = session_id
        self.idle_timeout_minutes = max(int(idle_timeout_minutes or 30), 1)
        self.binary_version = binary_version
        self.headless = headless
        self.port = int(port or 0)
        self.manager = BrowserSessionManager(self.repo_path, self.task_id, idle_timeout_minutes=self.idle_timeout_minutes)
        self.runtime = _BrowserRuntimeService(
            self.session_id,
            self.manager.storage_state_file,
            idle_timeout_minutes=self.idle_timeout_minutes,
            headless=headless,
        )
        self.runtime.ensure_started(self.manager)
        handler = self._build_handler()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.httpd.timeout = 1
        self.port = int(self.httpd.server_address[1])
        self._shutdown_requested = False
        atexit.register(self.shutdown)
        self._write_browse_state("ready")

    def _build_handler(self):
        host = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path not in {"/command", "/health"}:
                    self._send_json(404, {"error": "unknown_path"})
                    return
                if self.path != "/health" and not self._authorized():
                    self._send_json(401, {"error": "unauthorized"})
                    return
                payload = self._read_payload()
                try:
                    if self.path == "/health":
                        result = host.health_payload()
                    else:
                        result = host.execute(payload)
                except Exception as exc:  # pragma: no cover - defensive
                    self._send_json(500, {"error": str(exc)})
                    return
                self._send_json(200, result)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _authorized(self) -> bool:
                header = str(self.headers.get("Authorization") or "").strip()
                token = str(host.runtime._auth_token or "").strip()
                return bool(token and header == f"Bearer {token}")

            def _read_payload(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw) if raw.strip() else {}
                return payload if isinstance(payload, dict) else {}

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def health_payload(self) -> dict[str, Any]:
        self._write_browse_state("handoff" if self.runtime._handoff_active else "ready")
        return {
            **self.runtime._status_payload(),
            "pid": os.getpid(),
            "port": self.port,
            "binary_version": self.binary_version,
            "workspace_root": str(self.repo_path),
        }

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        manager = BrowserSessionManager(
            self.repo_path,
            str(payload.get("task_id") or self.task_id),
            idle_timeout_minutes=self.idle_timeout_minutes,
        )
        result = self.runtime.execute_commands(
            manager,
            list(payload.get("commands") or []),
            target_name=str(payload.get("target_name") or "browse"),
            kind=str(payload.get("kind") or "current"),
            viewport_name=str(payload.get("viewport_name") or "desktop"),
            viewport=dict(payload.get("viewport") or {"width": 1440, "height": 900}),
        )
        self._write_browse_state(str(result.get("service_status") or "ready"))
        if any(str(item.get("command") or "") == "stop" for item in result.get("results") or []):
            self._shutdown_requested = True
        return result

    def _write_browse_state(self, status: str) -> None:
        payload = self.runtime._status_payload()
        self.manager.write_browse_state(
            {
                "pid": os.getpid(),
                "port": self.port,
                "token": payload.get("service_auth_token"),
                "startedAt": payload.get("service_started_at"),
                "binaryVersion": self.binary_version,
                "workspaceRoot": str(self.repo_path),
                "session_id": payload.get("session_id"),
                "status": status,
                "serviceKind": "browse_host_daemon",
                "lastActivityAt": payload.get("last_activity_at"),
                "idleTimeoutMinutes": payload.get("idle_timeout_minutes"),
                "headless": payload.get("headless"),
                "headed": payload.get("headed"),
                "activeTabId": payload.get("active_tab_id"),
                "commandCount": payload.get("command_count"),
                "tabs": payload.get("tabs") or [],
                "handoffActive": payload.get("handoff_active"),
                "handoffReason": payload.get("handoff_reason"),
            }
        )

    def serve(self) -> None:
        try:
            while not self._shutdown_requested:
                self.httpd.handle_request()
                if self.runtime._idle_expired():
                    break
                if not self.runtime.is_healthy():
                    break
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._shutdown_requested and getattr(self, "_already_shutdown", False):
            return
        self._already_shutdown = True
        try:
            self.httpd.server_close()
        except Exception:
            pass
        try:
            self.runtime.close(manager=self.manager, reason="stopped", remove_runtime=False)
        finally:
            self.manager.clear_browse_state()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local browse host daemon for agentsystem.")
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--idle-timeout-minutes", type=int, default=30)
    parser.add_argument("--binary-version", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    server = BrowseHostServer(
        repo_path=Path(args.repo_path),
        task_id=str(args.task_id),
        session_id=str(args.session_id),
        idle_timeout_minutes=int(args.idle_timeout_minutes),
        binary_version=str(args.binary_version),
        headless=not bool(args.headed),
        port=int(args.port),
    )
    server.serve()


if __name__ == "__main__":
    main()
