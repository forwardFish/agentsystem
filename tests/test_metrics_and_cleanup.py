from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from agentsystem.dashboard import main as dashboard_main
from agentsystem.orchestration.workspace_manager import WorkspaceManager


class MetricsAndCleanupTestCase(unittest.TestCase):
    def test_metrics_derive_first_pass_retry_and_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runs_dir = base / "runs"
            artifacts_dir = runs_dir / "artifacts"
            meta_dir = base / "repo-worktree" / ".meta"
            runs_dir.mkdir(parents=True)
            artifacts_dir.mkdir(parents=True)
            meta_dir.mkdir(parents=True)

            first_pass = {
                "task_id": "task-pass",
                "task_name": "任务一",
                "success": True,
                "status": "success",
                "result": {
                    "fix_attempts": 0,
                    "blocking_issues": [],
                    "task_payload": {
                        "acceptance_criteria": ["页面有副标题", "代码通过 prettier 格式化"],
                    },
                    "acceptance_report": "\n".join(
                        [
                            "# Acceptance Gate Report",
                            "- 页面有副标题: 已满足 (ok)",
                            "- 代码通过 prettier 格式化: 已满足 (ok)",
                        ]
                    ),
                },
            }
            retried = {
                "task_id": "task-retry",
                "task_name": "任务二",
                "success": True,
                "status": "success",
                "result": {
                    "fix_attempts": 2,
                    "blocking_issues": ["Acceptance unmet: 页面有副标题"],
                    "task_payload": {
                        "acceptance_criteria": ["页面有副标题", "代码通过 prettier 格式化"],
                    },
                    "acceptance_report": "\n".join(
                        [
                            "# Acceptance Gate Report",
                            "- 页面有副标题: 未满足 (missing)",
                            "- 代码通过 prettier 格式化: 已满足 (ok)",
                        ]
                    ),
                },
            }

            (runs_dir / "prod_audit_task-pass.json").write_text(
                json.dumps(first_pass, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (runs_dir / "prod_audit_task-retry.json").write_text(
                json.dumps(retried, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "ARTIFACTS_DIR", artifacts_dir),
                patch.object(dashboard_main, "REPO_META_DIR", meta_dir),
            ):
                metrics = dashboard_main.compute_metrics()

            self.assertEqual(metrics["total_tasks"], 2)
            self.assertEqual(metrics["success_tasks"], 2)
            self.assertEqual(metrics["first_pass_rate"], 50.0)
            self.assertEqual(metrics["avg_retry_rounds"], 1.0)
            self.assertEqual(metrics["avg_blocking_issues"], 0.5)
            self.assertEqual(metrics["acceptance_hit_rate"], 75.0)

    def test_workspace_manager_lists_expired_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "versefina"
            worktree_root = Path(tmp) / "repo-worktree"
            repo_root.mkdir(parents=True)
            manager = WorkspaceManager(repo_root, worktree_root)

            old_meta = manager.meta_dir / "task-old"
            new_meta = manager.meta_dir / "task-new"
            old_meta.mkdir(parents=True)
            new_meta.mkdir(parents=True)

            (old_meta / "task.yaml").write_text(
                yaml.safe_dump({"task_id": "task-old", "created_at": "2026-01-01T00:00:00", "branch": "agent/l1-task-old"}),
                encoding="utf-8",
            )
            (new_meta / "task.yaml").write_text(
                yaml.safe_dump({"task_id": "task-new", "created_at": "2030-01-01T00:00:00", "branch": "agent/l1-task-new"}),
                encoding="utf-8",
            )

            expired = manager.list_expired_tasks(older_than_days=7)

            self.assertIn("task-old", expired)
            self.assertNotIn("task-new", expired)


if __name__ == "__main__":
    unittest.main()
