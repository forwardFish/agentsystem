from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from agentsystem.adapters.git_adapter import GitAdapter


class GitAdapterTestCase(unittest.TestCase):
    def test_checkout_main_and_pull_skips_repo_mutation_when_already_on_main_and_dirty(self) -> None:
        adapter = object.__new__(GitAdapter)
        adapter.repo_path = Path("D:/workspace/repo")
        adapter.repo = MagicMock()
        adapter.repo.active_branch.name = "main"
        adapter.repo.is_dirty.return_value = True
        adapter.repo.remotes = [MagicMock(name="origin")]
        adapter.repo.git = MagicMock()

        adapter.checkout_main_and_pull("main")

        adapter.repo.git.checkout.assert_not_called()
        adapter.repo.git.rev_parse.assert_not_called()
        adapter.repo.git.pull.assert_not_called()

    def test_checkout_main_and_pull_updates_clean_repo_when_branch_switch_is_needed(self) -> None:
        adapter = object.__new__(GitAdapter)
        adapter.repo_path = Path("D:/workspace/repo")
        adapter.repo = MagicMock()
        adapter.repo.active_branch.name = "feature/demo"
        adapter.repo.is_dirty.return_value = False
        origin = MagicMock()
        origin.name = "origin"
        adapter.repo.remotes = [origin]
        adapter.repo.git = MagicMock()

        adapter.checkout_main_and_pull("main")

        adapter.repo.git.checkout.assert_called_once_with("main")
        adapter.repo.git.rev_parse.assert_called_once_with("--verify", "origin/main")
        adapter.repo.git.pull.assert_called_once_with("--ff-only", "origin", "main")


if __name__ == "__main__":
    unittest.main()
