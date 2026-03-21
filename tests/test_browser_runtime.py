from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agentsystem.agents.browser_qa_agent import browser_qa_node, route_after_browser_qa
from agentsystem.agents.setup_browser_cookies_agent import setup_browser_cookies_node
from agentsystem.runtime.browser_session_manager import BrowserSessionManager
from agentsystem.runtime.playwright_browser_runtime import (
    _is_ignorable_request_failure,
    execute_browser_commands,
    get_browser_service_status,
)


class BrowserRuntimeTestCase(unittest.TestCase):
    def test_browser_session_manager_reuses_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            manager = BrowserSessionManager(repo_path, "task-demo")
            first = manager.ensure_session("http://127.0.0.1/demo")
            second = manager.ensure_session("http://127.0.0.1/demo")

            self.assertEqual(first.session_id, second.session_id)
            self.assertEqual(second.status, "reused")
            self.assertIn("http://127.0.0.1/demo", second.recent_targets)
            self.assertTrue(manager.session_file.exists())

    def test_browser_qa_node_records_passing_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                state = {
                    "task_id": "task-demo",
                    "repo_b_path": str(repo_path),
                    "task_payload": {
                        "browser_urls": [url],
                        "primary_files": ["apps/web/src/app/page.tsx"],
                    },
                    "fix_attempts": 0,
                    "handoff_packets": [],
                    "issues_to_fix": [],
                    "resolved_issues": [],
                    "all_deliverables": [],
                    "collaboration_trace_id": "trace-demo",
                }

                updated = browser_qa_node(state)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertTrue(updated["browser_qa_success"])
            self.assertTrue(updated["browser_qa_passed"])
            self.assertEqual(route_after_browser_qa(updated), "security_scanner")
            self.assertGreaterEqual(int(updated["browser_qa_health_score"] or 0), 90)
            self.assertTrue(Path(updated["browser_qa_dir"]).joinpath("browser_qa_report.md").exists())
            self.assertTrue(Path(updated["browser_runtime_dir"]).joinpath("session.json").exists())
            self.assertTrue(repo_path.parent.joinpath(".meta", repo_path.name, "qa", "qa_summary.json").exists())
            self.assertTrue(repo_path.parent.joinpath(".meta", repo_path.name, "qa", "qa_findings.json").exists())
            self.assertTrue(any(str(item.get("screenshot_path") or "").endswith(".png") for item in updated["browse_observations"]))
            self.assertTrue(all("before_screenshot_path" in item for item in updated["browse_observations"]))
            self.assertTrue(all("card_count" in item for item in updated["browse_observations"]))
            self.assertTrue(Path(updated["browser_runtime_dir"]).joinpath("observations").exists())

    def test_execute_browser_commands_supports_tabs_snapshot_and_storage_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-demo")
                result = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "viewport", "width": 960, "height": 640},
                        {"command": "goto", "url": url},
                        {"command": "type", "selector": "#name", "value": "Alice"},
                        {"command": "click", "selector": "#apply"},
                        {"command": "evaluate", "expression": "() => document.querySelector('#result').textContent"},
                        {"command": "snapshot", "label": "after"},
                        {"command": "storage_state", "action": "save"},
                        {"command": "tab", "action": "list"},
                    ],
                    target_name="current-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertGreaterEqual(len(result["tabs"]), 1)
            self.assertTrue(Path(manager.storage_state_file).exists())
            browse_state = json.loads(manager.browse_state_file.read_text(encoding="utf-8"))
            self.assertEqual(os.path.normcase(os.path.realpath(str(browse_state["workspaceRoot"]))), os.path.normcase(os.path.realpath(str(repo_path))))
            self.assertGreater(int(browse_state["pid"]), 0)
            self.assertGreater(int(browse_state["port"]), 0)
            self.assertTrue(str(browse_state["token"]))
            eval_result = next(item for item in result["results"] if item["command"] == "evaluate")
            self.assertEqual(eval_result["value"], "Alice")
            snapshot_result = next(item for item in result["results"] if item["command"] == "snapshot")
            self.assertTrue(Path(snapshot_result["observation_path"]).exists())
            self.assertTrue(Path(snapshot_result["dom_path"]).exists())
            self.assertTrue(snapshot_result["refs"])
            session = manager.load_session()
            self.assertIsNotNone(session)
            self.assertGreaterEqual(int(session.command_count), 1)
            self.assertGreaterEqual(len(session.tabs), 1)
            self.assertTrue(Path(manager.tabs_file).exists())

    def test_persistent_runtime_reuses_page_state_across_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-persist")
                first = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "goto", "url": url},
                        {"command": "type", "selector": "#name", "value": "Alice"},
                        {"command": "status"},
                    ],
                    target_name="persist-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
                second = execute_browser_commands(
                    manager,
                    [
                        {"command": "evaluate", "expression": "() => document.querySelector('#name').value"},
                        {"command": "status"},
                    ],
                    target_name="persist-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            eval_result = next(item for item in second["results"] if item["command"] == "evaluate")
            status_result = next(item for item in second["results"] if item["command"] == "status")
            self.assertEqual(eval_result["value"], "Alice")
            self.assertEqual(first["session_id"], second["session_id"])
            self.assertEqual(status_result["service_status"], "ready")
            self.assertTrue(status_result["service_auth_token"])
            self.assertTrue(Path(manager.service_file).exists())
            self.assertTrue(Path(manager.browse_state_file).exists())
            runtime_status = get_browser_service_status(manager)
            self.assertEqual(runtime_status["service_status"], "ready")
            self.assertEqual(int(runtime_status["pid"]), int(json.loads(manager.browse_state_file.read_text(encoding="utf-8"))["pid"]))

    def test_handoff_requires_resume_before_more_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-handoff")
                handoff = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "goto", "url": url},
                        {"command": "handoff", "message": "Simulate user takeover."},
                    ],
                    target_name="handoff-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
                blocked = execute_browser_commands(
                    manager,
                    [{"command": "evaluate", "expression": "() => document.title"}],
                    target_name="handoff-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
                resumed = execute_browser_commands(
                    manager,
                    [
                        {"command": "resume"},
                        {"command": "evaluate", "expression": "() => document.title"},
                    ],
                    target_name="handoff-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            handoff_result = next(item for item in handoff["results"] if item["command"] == "handoff")
            blocked_result = blocked["results"][0]
            resumed_eval = next(item for item in resumed["results"] if item["command"] == "evaluate")
            self.assertEqual(handoff_result["status"], "waiting_for_user")
            self.assertFalse(blocked_result["ok"])
            self.assertIn("resume", blocked_result["error"].lower())
            self.assertEqual(resumed_eval["value"], "Demo App")
            self.assertTrue(Path(manager.handoff_file).exists())

    def test_visible_handoff_writes_adapter_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-visible-handoff")
                handoff = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "goto", "url": url},
                        {"command": "handoff", "message": "Visible takeover requested.", "visible": True},
                    ],
                    target_name="visible-handoff-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
                resumed = execute_browser_commands(
                    manager,
                    [{"command": "resume"}],
                    target_name="visible-handoff-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            handoff_result = next(item for item in handoff["results"] if item["command"] == "handoff")
            self.assertTrue(Path(str(handoff_result["visible_handoff_path"])).exists())
            self.assertIn(
                str((handoff_result.get("visibility_adapter") or {}).get("status") or ""),
                {"applied", "fallback", "unchanged"},
            )
            resume_result = next(item for item in resumed["results"] if item["command"] == "resume")
            self.assertIn(
                str((resume_result.get("visibility_adapter") or {}).get("status") or "unchanged"),
                {"applied", "fallback", "unchanged"},
            )

    def test_cookie_import_browser_auto_discovers_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            local_appdata = Path(tmp) / "localappdata"
            cookie_db = local_appdata / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
            cookie_db.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(cookie_db))
            try:
                connection.execute(
                    "CREATE TABLE cookies (host_key TEXT, path TEXT, is_secure INTEGER, is_httponly INTEGER, expires_utc INTEGER, name TEXT, value TEXT, samesite INTEGER)"
                )
                connection.execute(
                    "INSERT INTO cookies (host_key, path, is_secure, is_httponly, expires_utc, name, value, samesite) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (".example.test", "/", 0, 1, 0, "demo_cookie", "demo-value", 1),
                )
                connection.commit()
            finally:
                connection.close()

            manager = BrowserSessionManager(repo_path, "task-cookie-discovery")
            discovered = execute_browser_commands(
                manager,
                [
                    {"command": "browser-sources", "local_appdata": str(local_appdata)},
                    {"command": "cookie-import-browser", "local_appdata": str(local_appdata)},
                    {"command": "storage_state", "action": "read"},
                ],
                target_name="cookie-home",
                kind="session",
                viewport_name="desktop",
                viewport={"width": 960, "height": 640},
            )

            sources_result = next(item for item in discovered["results"] if item["command"] == "browser-sources")
            import_result = next(item for item in discovered["results"] if item["command"] == "cookie-import-browser")
            state_result = next(item for item in discovered["results"] if item["command"] == "storage_state")
            self.assertGreaterEqual(len(sources_result["sources"]), 1)
            self.assertEqual(import_result["browser"], "chrome")
            self.assertEqual(import_result["browser_profile"], "Default")
            self.assertTrue(Path(str(import_result["source_copy_path"])).exists())
            self.assertEqual(import_result["count"], 1)
            self.assertEqual(state_result["value"]["cookies"][0]["name"], "demo_cookie")

    def test_chain_and_ref_commands_work_against_snapshot_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-chain")
                first = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "goto", "url": url},
                        {"command": "type", "selector": "#name", "value": "Chain"},
                        {"command": "snapshot", "label": "refs"},
                    ],
                    target_name="chain-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
                snapshot_result = next(item for item in first["results"] if item["command"] == "snapshot")
                apply_ref = next(item["ref"] for item in snapshot_result["refs"] if "Apply" in str(item.get("text") or ""))
                second = execute_browser_commands(
                    manager,
                    [
                        {
                            "command": "chain",
                            "commands": [
                                {"command": "click", "selector": apply_ref},
                                {"command": "evaluate", "expression": "() => document.querySelector('#result').textContent"},
                            ],
                        }
                    ],
                    target_name="chain-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            chain_result = second["results"][0]
            nested_eval = next(item for item in chain_result["results"] if item["command"] == "evaluate")
            self.assertEqual(nested_eval["value"], "Chain")

    def test_setup_browser_cookies_imports_into_shared_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            server, thread = _start_test_server()
            port = server.server_address[1]
            cookie_path = Path(tmp) / "cookies.json"
            cookie_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "session",
                            "value": "abc123",
                            "domain": "127.0.0.1",
                            "path": "/",
                            "httpOnly": False,
                            "secure": False,
                            "sameSite": "Lax",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            try:
                state = {
                    "task_id": "task-cookie",
                    "repo_b_path": str(repo_path),
                    "task_payload": {
                        "cookie_source": str(cookie_path),
                        "auth_expectations": ["Session cookie should be available during browser QA."],
                    },
                    "cookie_source": str(cookie_path),
                    "auth_expectations": ["Session cookie should be available during browser QA."],
                    "handoff_packets": [],
                    "all_deliverables": [],
                    "collaboration_trace_id": "trace-cookie",
                }
                updated = setup_browser_cookies_node(state)
                manager = BrowserSessionManager(repo_path, "task-cookie")
                result = execute_browser_commands(
                    manager,
                    [
                        {"command": "tab", "action": "new"},
                        {"command": "goto", "url": f"http://127.0.0.1:{port}/"},
                        {"command": "evaluate", "expression": "() => document.cookie"},
                    ],
                    target_name="auth-check",
                    kind="session",
                    viewport_name="desktop",
                    viewport={"width": 1280, "height": 720},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertTrue(updated["setup_browser_cookies_success"])
            self.assertTrue(Path(updated["browser_storage_state_path"]).exists())
            eval_result = next(item for item in result["results"] if item["command"] == "evaluate")
            self.assertIn("session=abc123", str(eval_result["value"]))
            session = manager.load_session()
            self.assertIsNotNone(session)
            self.assertTrue(session.cookies_imported)

    def test_browser_runtime_supports_extended_command_surface_and_safe_browser_cookie_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            upload_path = Path(tmp) / "demo-upload.txt"
            upload_path.write_text("demo upload", encoding="utf-8")
            cookie_path = Path(tmp) / "browser-cookies.json"
            cookie_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "session",
                            "value": "browser-copy",
                            "domain": "127.0.0.1",
                            "path": "/",
                            "httpOnly": False,
                            "secure": False,
                            "sameSite": "Lax",
                        }
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                manager = BrowserSessionManager(repo_path, "task-extended")
                result = execute_browser_commands(
                    manager,
                    [
                        {"command": "newtab"},
                        {"command": "goto", "url": url},
                        {"command": "fill", "selector": "#name", "value": "Extended"},
                        {"command": "upload", "selector": "#upload", "path": str(upload_path)},
                        {"command": "evaluate", "expression": "() => document.querySelector('#upload').files[0].name"},
                        {"command": "cookie-import-browser", "source": str(cookie_path)},
                        {"command": "pdf"},
                        {"command": "perf"},
                        {"command": "dialog-accept", "text": "approved"},
                        {"command": "evaluate", "expression": "() => { setTimeout(() => prompt('enter value', 'demo'), 0); return 'scheduled'; }"},
                        {"command": "wait", "ms": 200},
                        {"command": "dialog"},
                        {"command": "tabs"},
                    ],
                    target_name="extended-home",
                    kind="current",
                    viewport_name="desktop",
                    viewport={"width": 960, "height": 640},
                )
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            upload_eval = next(item for item in result["results"] if item["command"] == "evaluate" and item.get("value") == upload_path.name)
            cookie_import = next(item for item in result["results"] if item["command"] == "cookie-import-browser")
            pdf_result = next(item for item in result["results"] if item["command"] == "pdf")
            perf_result = next(item for item in result["results"] if item["command"] == "perf")
            dialog_result = next(item for item in result["results"] if item["command"] == "dialog")
            tabs_result = next(item for item in result["results"] if item["command"] == "tab" and item.get("action") == "list")

            self.assertEqual(upload_eval["value"], upload_path.name)
            self.assertEqual(cookie_import["import_kind"], "cookie-import-browser")
            self.assertEqual(cookie_import["count"], 1)
            self.assertTrue(Path(str(cookie_import["source_copy_path"])).exists())
            self.assertNotEqual(Path(str(cookie_import["source_copy_path"])).resolve(), cookie_path.resolve())
            self.assertTrue(Path(str(pdf_result["path"])).exists())
            self.assertTrue(Path(str(perf_result["path"])).exists())
            self.assertGreaterEqual(int(dialog_result["count"]), 1)
            self.assertGreaterEqual(len(tabs_result["tabs"]), 1)

    def test_ignores_prefetch_and_orb_request_failures(self) -> None:
        self.assertTrue(
            _is_ignorable_request_failure(
                "GET http://127.0.0.1:3002/agents/agent-01?_rsc=abc -> net::ERR_ABORTED"
            )
        )
        self.assertTrue(
            _is_ignorable_request_failure(
                "GET https://cdn-images.toolify.ai/example.webp -> net::ERR_BLOCKED_BY_ORB"
            )
        )
        self.assertFalse(
            _is_ignorable_request_failure(
                "GET http://127.0.0.1:3002/_next/static/css/app.css -> net::ERR_CONNECTION_REFUSED"
            )
        )


class _DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/next"):
            body = "<html><head><title>Next Tab</title></head><body><main>next</main></body></html>".encode("utf-8")
        else:
            body = (
                "<html><head><title>Demo App</title></head>"
                "<body>"
                "<header><nav><a href='/'>Home</a><a href='/next'>Workbench</a></nav></header>"
                "<main>"
                "<h1>Demo App</h1>"
                "<input id='name' type='text' value='demo'>"
                "<input id='upload' type='file'>"
                "<button id='apply' type='button' onclick=\"document.querySelector('#result').textContent = document.querySelector('#name').value\">Apply</button>"
                "<p id='result'>demo</p>"
                "<input type='search' value='demo'>"
                "<section data-view-controls><a href='?view=all'>All</a><button type='button'>Focus</button></section>"
                "<article data-card><h2>Signal lead</h2><p>Important detail</p></article>"
                "<section data-evidence-block><strong>Evidence block</strong></section>"
                "<section data-risk-section><h2>Risk frame</h2><ul><li>Watch concentration</li></ul></section>"
                "<section data-matrix-section><table><thead><tr><th>Theme</th></tr></thead><tbody><tr><td>AI</td></tr></tbody></table></section>"
                "<div data-refresh-state='idle'><button type='button'>Refresh</button><span class='refresh-text'>Current run: demo</span></div>"
                "<script>console.log('demo ready')</script>"
                "</main>"
                "</body></html>"
            ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _start_test_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    return server, thread


if __name__ == "__main__":
    unittest.main()
