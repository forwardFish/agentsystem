from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from git import Repo

from agentsystem.runtime.agent_daemon import AgentDaemon
from agentsystem.runtime.agent_prefs import AgentPrefs
from agentsystem.runtime.agent_runtime import AgentRuntime
from agentsystem.runtime.agent_state import AgentState
from agentsystem.runtime.permission_manager import PermissionManager
from agentsystem.skills_runtime.change_scope import get_low_risk_tasks
from agentsystem.skills_runtime.diff_summary import summarize_diff
from agentsystem.skills_runtime.test_report import check_test_result


class AutonomousRuntimeTestCase(unittest.TestCase):
    def _create_repo_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "tasks").mkdir(parents=True)
        (root / "runs").mkdir(parents=True)
        (root / "agent-workspaces").mkdir(parents=True)
        return root

    def _write_task(self, root: Path, blast_radius: str = "L1") -> None:
        (root / "tasks" / "current.yaml").write_text(
            f"""
task_name: demo
blast_radius: "{blast_radius}"
goal: demo goal
constraints:
  - only one file
explicitly_not_doing:
  - do not touch backend
related_files:
  - apps/web/src/app/page.tsx
""".strip(),
            encoding="utf-8",
        )

    def _write_run_log(self, root: Path, *, status: str = "success", format_success: bool = True) -> None:
        payload = {
            "status": status,
            "format_results": [{"success": format_success}],
        }
        (root / "runs" / "demo.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_permission_manager_honors_release_guards(self) -> None:
        root = self._create_repo_root()
        self._write_task(root, "L1")
        self._write_run_log(root, status="success", format_success=True)
        manager = PermissionManager(Path(__file__).resolve().parents[1] / "config" / "permission_profiles.yaml")

        self.assertTrue(manager.check_permission("release", "release_approve", context={"repo_root": root}))

        self._write_task(root, "L3")
        self.assertFalse(manager.check_permission("release", "release_approve", context={"repo_root": root}))

    def test_agent_runtime_writes_heartbeat(self) -> None:
        root = self._create_repo_root()
        runtime = AgentRuntime("dev", root)

        runtime.start("unit_test")
        runtime.gate("pending_pr")

        heartbeat = AgentPrefs(root).get_heartbeat_file("dev").read_text(encoding="utf-8")
        self.assertIn("unit_test", heartbeat)
        self.assertIn("pending_pr", heartbeat)
        self.assertEqual(runtime.state, AgentState.GATED)

    def test_daemon_starts_dev_and_gates_on_non_main_branch(self) -> None:
        root = self._create_repo_root()
        self._write_task(root, "L1")
        self._write_run_log(root, status="success", format_success=True)

        repo = Repo.init(root)
        repo.git.checkout("-b", "main")
        (root / "README.md").write_text("demo\n", encoding="utf-8")
        repo.git.add(A=True)
        repo.git.commit("-m", "init")
        repo.git.checkout("-b", "agent/demo-branch")

        notifications: list[str] = []
        daemon = AgentDaemon(root, notifier=notifications.append)
        result = daemon.run_cycle()

        self.assertEqual(result["dev"], "started:1")
        self.assertEqual(result["review"], "gated:1")
        self.assertEqual(daemon.dev_agent.state, AgentState.GATED)
        self.assertTrue(notifications)

    def test_runtime_skills_report_expected_values(self) -> None:
        root = self._create_repo_root()
        self._write_task(root, "L1")
        self._write_run_log(root, status="success", format_success=True)

        repo = Repo.init(root)
        repo.git.checkout("-b", "main")
        (root / "README.md").write_text("demo\n", encoding="utf-8")
        repo.git.add(A=True)
        repo.git.commit("-m", "init")
        (root / "README.md").write_text("demo updated\n", encoding="utf-8")
        repo.git.add(A=True)
        repo.git.commit("-m", "update")

        self.assertEqual(len(get_low_risk_tasks(root)), 1)
        self.assertEqual(check_test_result(root), "passed")
        self.assertIn("README.md", summarize_diff(root))


if __name__ == "__main__":
    unittest.main()
