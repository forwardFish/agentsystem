from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.dashboard import main as dashboard_main


class DashboardApiTestCase(unittest.TestCase):
    def test_load_tasks_reads_audit_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            runs_dir.mkdir(parents=True)
            audit_file = runs_dir / "prod_audit_task-demo.json"
            audit_file.write_text(
                json.dumps(
                    {
                        "task_id": "task-demo",
                        "task_name": "给前端页面加副标题",
                        "success": True,
                        "branch": "agent/l1-task-demo",
                        "commit": "abc123",
                        "blast_radius": "L1",
                        "execution_mode": "Fast",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(dashboard_main, "RUNS_DIR", runs_dir):
                tasks = dashboard_main.load_tasks()

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["task_id"], "task-demo")
            self.assertEqual(tasks[0]["task_name"], "给前端页面加副标题")
            self.assertEqual(tasks[0]["status"], "success")

    def test_load_task_detail_reads_meta_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runs_dir = base / "runs"
            meta_dir = base / "repo-worktree" / ".meta" / "task-demo"
            (meta_dir / "pr_prep").mkdir(parents=True)
            (meta_dir / "review").mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (runs_dir / "prod_audit_task-demo.json").write_text(
                json.dumps({"task_id": "task-demo", "success": True}, ensure_ascii=False),
                encoding="utf-8",
            )
            (meta_dir / "pr_prep" / "pr_description.md").write_text("PR body", encoding="utf-8")
            (meta_dir / "pr_prep" / "commit_message.txt").write_text("feat: demo", encoding="utf-8")
            (meta_dir / "review" / "review_report.md").write_text("review body", encoding="utf-8")

            with (
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "REPO_META_DIR", base / "repo-worktree" / ".meta"),
            ):
                detail = dashboard_main.load_task_detail("task-demo")

            self.assertEqual(detail["task_id"], "task-demo")
            self.assertEqual(detail["artifacts"]["pr_description"], "PR body")
            self.assertEqual(detail["artifacts"]["commit_message"], "feat: demo")
            self.assertEqual(detail["artifacts"]["review_report"], "review body")


if __name__ == "__main__":
    unittest.main()
