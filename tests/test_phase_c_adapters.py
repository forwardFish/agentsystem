from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.shell_executor import ShellExecutor


class PhaseCAdaptersTestCase(unittest.TestCase):
    def test_config_reader_loads_agents_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            agents_dir = repo_root / ".agents"
            agents_dir.mkdir(parents=True)
            for name in ("project.yaml", "rules.yaml", "commands.yaml", "review_policy.yaml", "contracts.yaml"):
                agents_dir.joinpath(name).write_text("key: value\n", encoding="utf-8")

            config = RepoBConfigReader(repo_root).load_all_config()

            self.assertEqual(config.project["key"], "value")
            self.assertEqual(config.contracts["key"], "value")

    def test_shell_executor_runs_simple_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            success, output = ShellExecutor(tmp).run_command("python -c \"print('ok')\"")
            self.assertTrue(success)
            self.assertIn("ok", output)

    def test_git_adapter_reports_current_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            from git import Repo

            repo = Repo.init(repo_root)
            repo.git.checkout("-b", "main")
            repo_root.joinpath("README.md").write_text("demo\n", encoding="utf-8")
            repo.git.add(A=True)
            repo.git.commit("-m", "init")

            adapter = GitAdapter(repo_root)
            self.assertEqual(adapter.get_current_branch(), "main")


if __name__ == "__main__":
    unittest.main()
