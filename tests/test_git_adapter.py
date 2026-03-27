from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.git_adapter import GitAdapter


class GitAdapterTestCase(unittest.TestCase):
    def test_snapshot_workspace_under_parent_git_repo_uses_snapshot_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parent_repo = base / "parent"
            parent_repo.mkdir()
            self._git(parent_repo, "init", "-b", "main")
            self._git(parent_repo, "config", "user.email", "codex@example.com")
            self._git(parent_repo, "config", "user.name", "Codex")
            (parent_repo / "README.md").write_text("parent\n", encoding="utf-8")
            self._git(parent_repo, "add", "README.md")
            self._git(parent_repo, "commit", "-m", "init")

            snapshot_repo = parent_repo / "repo-worktree" / "task-demo"
            snapshot_repo.mkdir(parents=True)
            (snapshot_repo / "app.txt").write_text("hello\n", encoding="utf-8")

            snapshot_meta = parent_repo / "repo-worktree" / ".meta" / "task-demo"
            snapshot_meta.mkdir(parents=True)
            (snapshot_meta / "snapshot_base").mkdir()
            (snapshot_meta / "snapshot_base" / "app.txt").write_text("hello\n", encoding="utf-8")
            (snapshot_meta / "snapshot_state.json").write_text(
                json.dumps(
                    {
                        "mode": "snapshot",
                        "branch": "agent/l1-task-demo",
                        "base_branch": "main",
                        "base_commit": "abc123",
                        "current_commit": "abc123",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            adapter = GitAdapter(snapshot_repo)

            self.assertTrue(adapter.snapshot_mode)
            self.assertEqual(adapter.get_current_branch(), "agent/l1-task-demo")
            self.assertEqual(adapter.get_current_commit(), "abc123")
            self.assertFalse(adapter.is_dirty())

    def test_snapshot_mode_ignores_generated_runtime_and_dependency_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parent_repo = base / "parent"
            parent_repo.mkdir()
            self._git(parent_repo, "init", "-b", "main")
            self._git(parent_repo, "config", "user.email", "codex@example.com")
            self._git(parent_repo, "config", "user.name", "Codex")
            (parent_repo / "README.md").write_text("parent\n", encoding="utf-8")
            self._git(parent_repo, "add", "README.md")
            self._git(parent_repo, "commit", "-m", "init")

            snapshot_repo = parent_repo / "repo-worktree" / "task-demo"
            snapshot_repo.mkdir(parents=True)
            (snapshot_repo / "app.txt").write_text("hello\n", encoding="utf-8")
            (snapshot_repo / "node_modules").mkdir()
            (snapshot_repo / "node_modules" / "noise.js").write_text("console.log('x')\n", encoding="utf-8")
            (snapshot_repo / ".next").mkdir()
            (snapshot_repo / ".next" / "chunk.js").write_text("compiled\n", encoding="utf-8")
            (snapshot_repo / ".gstack").mkdir()
            (snapshot_repo / ".gstack" / "browse.json").write_text("{}", encoding="utf-8")

            snapshot_meta = parent_repo / "repo-worktree" / ".meta" / "task-demo"
            snapshot_meta.mkdir(parents=True)
            (snapshot_meta / "snapshot_base").mkdir()
            (snapshot_meta / "snapshot_base" / "app.txt").write_text("hello\n", encoding="utf-8")
            (snapshot_meta / "snapshot_state.json").write_text(
                json.dumps(
                    {
                        "mode": "snapshot",
                        "branch": "agent/l1-task-demo",
                        "base_branch": "main",
                        "base_commit": "abc123",
                        "current_commit": "abc123",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            adapter = GitAdapter(snapshot_repo)

            self.assertTrue(adapter.snapshot_mode)
            self.assertFalse(adapter.is_dirty())
            self.assertEqual(adapter.get_working_tree_files(), [])
            self.assertEqual(adapter.get_working_tree_diff(), "")

    def test_snapshot_commit_refresh_does_not_copy_dependency_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parent_repo = base / "parent"
            parent_repo.mkdir()
            self._git(parent_repo, "init", "-b", "main")
            self._git(parent_repo, "config", "user.email", "codex@example.com")
            self._git(parent_repo, "config", "user.name", "Codex")
            (parent_repo / "README.md").write_text("parent\n", encoding="utf-8")
            self._git(parent_repo, "add", "README.md")
            self._git(parent_repo, "commit", "-m", "init")

            snapshot_repo = parent_repo / "repo-worktree" / "task-demo"
            snapshot_repo.mkdir(parents=True)
            (snapshot_repo / "app.txt").write_text("hello\n", encoding="utf-8")
            (snapshot_repo / "apps" / "web" / "node_modules" / "pkg").mkdir(parents=True)
            (
                snapshot_repo
                / "apps"
                / "web"
                / "node_modules"
                / "pkg"
                / "index.js"
            ).write_text("console.log('x')\n", encoding="utf-8")

            snapshot_meta = parent_repo / "repo-worktree" / ".meta" / "task-demo"
            snapshot_meta.mkdir(parents=True)
            (snapshot_meta / "snapshot_base").mkdir()
            (snapshot_meta / "snapshot_base" / "app.txt").write_text("hello\n", encoding="utf-8")
            (snapshot_meta / "snapshot_state.json").write_text(
                json.dumps(
                    {
                        "mode": "snapshot",
                        "branch": "agent/l1-task-demo",
                        "base_branch": "main",
                        "base_commit": "abc123",
                        "current_commit": "abc123",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            adapter = GitAdapter(snapshot_repo)
            adapter.commit("refresh baseline")

            self.assertFalse(
                (snapshot_meta / "snapshot_base" / "apps" / "web" / "node_modules").exists()
            )

    def _git(self, repo_root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
