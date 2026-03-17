from __future__ import annotations

import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from git import Repo

from agentsystem.graph.dev_workflow import DevWorkflow
from agentsystem.orchestration.skill_mode_registry import get_skill_mode, list_skill_modes


PROJECT_YAML = """name: agentsystem-fixture
stack:
  frontend:
    path: apps/web
git:
  default_branch: main
"""
RULES_YAML = "{}\n"
COMMANDS_YAML = """lint:
  - python -c "print('lint ok')"
"""
REVIEW_POLICY_YAML = "{}\n"
CONTRACTS_YAML = "{}\n"
STYLE_GUIDE_MD = "# Style Guide\n"


class SkillModeRegistryTestCase(unittest.TestCase):
    def test_default_skill_modes_are_registered(self) -> None:
        modes = list_skill_modes("software_engineering")
        mode_index = {mode.mode_id: mode for mode in modes}

        self.assertEqual(set(mode_index.keys()), {"plan-eng-review", "browse", "qa", "qa-only"})
        self.assertFalse(mode_index["plan-eng-review"].fixer_allowed)
        self.assertTrue(mode_index["qa"].fixer_allowed)
        self.assertTrue(mode_index["qa-only"].report_only)

    def test_plan_eng_review_stops_after_architecture_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)

            workflow = DevWorkflow(
                {},
                str(repo_path),
                {
                    "goal": "Plan a dashboard story before implementation.",
                    "acceptance_criteria": ["plan exists"],
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "skill_mode": "plan-eng-review",
                },
                task_id="task-plan",
            )
            result = workflow.run()

            self.assertTrue(result["success"])
            self.assertEqual(result["state"]["current_step"], "architecture_review_done")
            self.assertTrue(result["state"]["architecture_review_success"])
            self.assertIsNone(result["state"]["backend_result"])

    def test_browse_mode_stops_after_browser_qa_without_fixer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                workflow = DevWorkflow(
                    {},
                    str(repo_path),
                    {
                        "goal": "Browse the preview surface.",
                        "acceptance_criteria": ["browser report exists"],
                        "related_files": ["apps/web/src/app/page.tsx"],
                        "primary_files": ["apps/web/src/app/page.tsx"],
                        "browser_urls": [url],
                        "skill_mode": "browse",
                    },
                    task_id="task-browse",
                )
                result = workflow.run()
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertTrue(result["success"])
            self.assertEqual(result["state"]["current_step"], "browser_qa_done")
            self.assertEqual(result["state"]["fix_attempts"], 0)
            self.assertTrue(result["state"]["browser_qa_report_only"])

    def test_qa_only_does_not_enter_fixer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                workflow = DevWorkflow(
                    {},
                    str(repo_path),
                    {
                        "goal": "Run qa-only report for the page.",
                        "acceptance_criteria": ["report exists"],
                        "related_files": ["apps/web/src/app/page.tsx"],
                        "primary_files": ["apps/web/src/app/page.tsx"],
                        "browser_urls": [url],
                        "test_failure_info": "Simulated lint failure",
                        "skill_mode": "qa-only",
                    },
                    task_id="task-qa-only",
                )
                result = workflow.run()
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertTrue(result["success"])
            self.assertEqual(result["state"]["current_step"], "browser_qa_done")
            self.assertEqual(result["state"]["fix_attempts"], 0)
            self.assertTrue(result["state"]["browser_qa_report_only"])

    def test_qa_mode_can_enter_fixer_and_return_to_browser_qa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            server, thread = _start_test_server()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            try:
                workflow = DevWorkflow(
                    {},
                    str(repo_path),
                    {
                        "goal": "Run fix-capable QA for the page.",
                        "acceptance_criteria": ["report exists"],
                        "related_files": ["apps/web/src/app/page.tsx"],
                        "primary_files": ["apps/web/src/app/page.tsx"],
                        "browser_urls": [url],
                        "test_failure_info": "Simulated test failure for fixer coverage",
                        "skill_mode": "qa",
                    },
                    task_id="task-qa",
                )
                result = workflow.run()
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertTrue(result["success"])
            self.assertEqual(result["state"]["current_step"], "browser_qa_done")
            self.assertGreaterEqual(int(result["state"]["fix_attempts"] or 0), 1)
            self.assertFalse(result["state"]["browser_qa_report_only"])


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


def _create_repo_fixture(repo_path: Path) -> None:
    (repo_path / ".agents").mkdir(parents=True)
    (repo_path / "apps" / "web" / "src" / "app").mkdir(parents=True, exist_ok=True)
    (repo_path / "apps" / "web" / "src" / "app" / "page.tsx").write_text(
        "export default function Page(){ return <main>demo</main>; }\n",
        encoding="utf-8",
    )
    (repo_path / ".agents" / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
    (repo_path / ".agents" / "rules.yaml").write_text(RULES_YAML, encoding="utf-8")
    (repo_path / ".agents" / "commands.yaml").write_text(COMMANDS_YAML, encoding="utf-8")
    (repo_path / ".agents" / "review_policy.yaml").write_text(REVIEW_POLICY_YAML, encoding="utf-8")
    (repo_path / ".agents" / "contracts.yaml").write_text(CONTRACTS_YAML, encoding="utf-8")
    (repo_path / ".agents" / "style_guide.md").write_text(STYLE_GUIDE_MD, encoding="utf-8")

    repo = Repo.init(repo_path, initial_branch="main")
    repo.index.add(["."])
    with repo.config_writer() as config:
        config.set_value("user", "name", "Codex")
        config.set_value("user", "email", "codex@example.com")
    repo.index.commit("chore: seed fixture")


if __name__ == "__main__":
    unittest.main()
