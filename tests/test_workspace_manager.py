from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.orchestration.workspace_manager import WorkspaceManager


class WorkspaceManagerTestCase(unittest.TestCase):
    def test_create_worktree_resets_existing_agent_branch_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_root = base / "repo"
            repo_root.mkdir()
            worktree_root = base / "worktrees"

            self._git(repo_root, "init", "-b", "main")
            self._git(repo_root, "config", "user.email", "codex@example.com")
            self._git(repo_root, "config", "user.name", "Codex")

            (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
            self._git(repo_root, "add", "README.md")
            self._git(repo_root, "commit", "-m", "initial")
            self._git(repo_root, "branch", "agent/l1-task-demo")

            (repo_root / ".env.example").write_text("ADMIN_EMAIL=owner@example.com\n", encoding="utf-8")
            self._git(repo_root, "add", ".env.example")
            self._git(repo_root, "commit", "-m", "add env example")

            manager = WorkspaceManager(repo_root, worktree_root)
            worktree_path = manager.create_worktree("task-demo", "agent/l1-task-demo")

            self.assertTrue((worktree_path / ".env.example").exists())
            self.assertEqual(
                (worktree_path / ".env.example").read_text(encoding="utf-8"),
                "ADMIN_EMAIL=owner@example.com\n",
            )

    def test_create_worktree_uses_snapshot_mode_when_repo_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_root = base / "repo"
            repo_root.mkdir()
            worktree_root = base / "worktrees"

            self._git(repo_root, "init", "-b", "main")
            self._git(repo_root, "config", "user.email", "codex@example.com")
            self._git(repo_root, "config", "user.name", "Codex")

            (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
            self._git(repo_root, "add", "README.md")
            self._git(repo_root, "commit", "-m", "initial")
            (repo_root / "README.md").write_text("dirty\n", encoding="utf-8")

            manager = WorkspaceManager(repo_root, worktree_root)
            worktree_path = manager.create_worktree("task-dirty", "agent/l1-task-dirty")
            snapshot_state = json.loads((worktree_root / ".meta" / "task-dirty" / "snapshot_state.json").read_text(encoding="utf-8"))

            self.assertTrue((worktree_path / "README.md").exists())
            self.assertEqual(snapshot_state["mode"], "snapshot")
            self.assertEqual(snapshot_state["snapshot_reason"], "dirty_worktree")

    def test_release_lock_ignores_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_root = base / "repo"
            repo_root.mkdir()
            manager = WorkspaceManager(repo_root, base / "worktrees")
            lock_path = manager.lock_dir / "demo.lock"
            lock_path.write_text("", encoding="utf-8")

            with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
                manager._release_lock(lock_path)

            self.assertTrue(lock_path.exists())

    def _git(self, repo_root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
