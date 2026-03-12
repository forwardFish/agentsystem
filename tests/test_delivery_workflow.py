from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from agent_system_framework.workspace.branching import BranchManager
from agent_system_framework.workspace.commands import CommandExecutionError, CommandExecutor
from agent_system_framework.workspace.github import GitHubPullRequestManager


class DeliveryWorkflowTestCase(unittest.TestCase):
    def test_branch_manager_creates_prefixed_working_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            init_git_repo(repo_root)
            write_agents_contracts(repo_root)

            manager = BranchManager(repo_root)
            result = manager.create_working_branch(
                "Feature PR",
                timestamp=datetime(2026, 3, 11, 14, 30, 0, tzinfo=UTC),
            )

            self.assertEqual(result.base_branch, "main")
            self.assertEqual(result.working_branch, "agent/feature-pr-20260311-143000")

    def test_command_executor_runs_phase_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            write_agents_contracts(repo_root)
            executor = CommandExecutor(repo_root)

            results = executor.run_phase("lint")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].returncode, 0)
            self.assertIn("lint ok", results[0].stdout)

    def test_command_executor_raises_for_failed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            write_agents_contracts(repo_root, failing_test=True)
            executor = CommandExecutor(repo_root)

            with self.assertRaises(CommandExecutionError):
                executor.run_phase("test")

    def test_github_pr_manager_uses_api_when_token_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            init_git_repo(repo_root)
            add_origin(repo_root, "https://github.com/example/versefina.git")
            manager = GitHubPullRequestManager(repo_root)

            payload = json.dumps({"number": 12, "html_url": "https://github.com/example/versefina/pull/12"}).encode(
                "utf-8"
            )
            response = mock.Mock()
            response.read.return_value = payload
            response.__enter__ = mock.Mock(return_value=response)
            response.__exit__ = mock.Mock(return_value=False)

            with mock.patch("agent_system_framework.workspace.github.request.urlopen", return_value=response) as urlopen:
                result = manager.create_pull_request(
                    title="Agent change: scaffold",
                    body="body",
                    head_branch="agent/scaffold-20260311-143000",
                    base_branch="main",
                    token="token",
                )

            req = urlopen.call_args.args[0]
            self.assertEqual(req.full_url, "https://api.github.com/repos/example/versefina/pulls")
            self.assertEqual(result.number, 12)
            self.assertEqual(result.url, "https://github.com/example/versefina/pull/12")


def write_agents_contracts(repo_root: Path, *, failing_test: bool = False) -> None:
    agents_dir = repo_root / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "project.yaml").write_text(
        json.dumps(
            {
                "name": "versefina",
                "description": "Agent-native finance backtesting platform",
                "stack": {
                    "frontend": {"framework": "nextjs", "package_manager": "pnpm", "path": "apps/web"},
                    "backend": {"framework": "fastapi", "runtime": "python:3.11", "path": "apps/api"},
                },
                "git": {"default_branch": "main", "working_branch_prefix": "agent/"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (agents_dir / "commands.yaml").write_text(
        json.dumps(
            {
                "lint": ["python -c \"print('lint ok')\""],
                "test": ["python -c \"import sys; sys.exit(1)\""] if failing_test else ["python -c \"print('test ok')\""],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def init_git_repo(repo_root: Path) -> None:
    from agent_system_framework.workspace.git_tools import run_git

    run_git(repo_root, ["init", "-b", "main"])
    (repo_root / "README.md").write_text("workspace\n", encoding="utf-8")
    run_git(repo_root, ["add", "README.md"])
    run_git(
        repo_root,
        [
            "-c",
            "user.name=Agent System",
            "-c",
            "user.email=agent-system@example.invalid",
            "commit",
            "-m",
            "chore: initial commit",
        ],
    )


def add_origin(repo_root: Path, remote_url: str) -> None:
    from agent_system_framework.workspace.git_tools import run_git

    run_git(repo_root, ["remote", "add", "origin", remote_url])


if __name__ == "__main__":
    unittest.main()
