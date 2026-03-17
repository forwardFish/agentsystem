from __future__ import annotations

import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agentsystem.agents.browser_qa_agent import browser_qa_node, route_after_browser_qa
from agentsystem.runtime.browser_session_manager import BrowserSessionManager


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


class _DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = "<html><head><title>Demo App</title></head><body><main>ok</main></body></html>".encode("utf-8")
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
