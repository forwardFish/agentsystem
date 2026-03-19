from __future__ import annotations

import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agentsystem.agents.browser_qa_agent import browser_qa_node, route_after_browser_qa
from agentsystem.runtime.browser_session_manager import BrowserSessionManager
from agentsystem.runtime.playwright_browser_runtime import _is_ignorable_request_failure


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
            self.assertTrue(any(str(item.get("screenshot_path") or "").endswith(".png") for item in updated["browse_observations"]))
            self.assertTrue(all("card_count" in item for item in updated["browse_observations"]))
            self.assertTrue(all("search_present" in item for item in updated["browse_observations"]))
            self.assertTrue(all("heading_count" in item for item in updated["browse_observations"]))
            self.assertTrue(all("cta_count" in item for item in updated["browse_observations"]))
            self.assertTrue(all("matrix_present" in item for item in updated["browse_observations"]))
            self.assertTrue(all("risk_present" in item for item in updated["browse_observations"]))
            self.assertTrue(all("evidence_present" in item for item in updated["browse_observations"]))
            self.assertTrue(all("refresh_present" in item for item in updated["browse_observations"]))
            self.assertTrue(
                Path(updated["browser_runtime_dir"]).joinpath("observations").exists(),
            )

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
        body = (
            "<html><head><title>Demo App</title></head>"
            "<body>"
            "<header><nav><a href='/'>Home</a><a href='/sprint-2'>Workbench</a></nav></header>"
            "<main>"
            "<h1>Demo App</h1>"
            "<input type='search' value='demo'>"
            "<section data-view-controls><a href='?view=all'>All</a><button type='button'>Focus</button></section>"
            "<article data-card><h2>Signal lead</h2><p>Important detail</p></article>"
            "<section data-evidence-block><strong>Evidence block</strong></section>"
            "<section data-risk-section><h2>Risk frame</h2><ul><li>Watch concentration</li></ul></section>"
            "<section data-matrix-section><table><thead><tr><th>Theme</th></tr></thead><tbody><tr><td>AI</td></tr></tbody></table></section>"
            "<div data-refresh-state='idle'><button type='button'>立即抓最新</button><span class='refresh-text'>当前最新 run: demo</span></div>"
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
