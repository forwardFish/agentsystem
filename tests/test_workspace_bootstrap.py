from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from agent_system_framework.workspace.bootstrap import bootstrap_target_repo, load_project_config


PROJECT_YAML = {
    "name": "versefina",
    "description": "Agent-native finance backtesting platform",
    "stack": {
        "frontend": {"framework": "nextjs", "package_manager": "pnpm", "path": "apps/web"},
        "backend": {"framework": "fastapi", "runtime": "python:3.11", "path": "apps/api"},
        "worker": {"framework": "celery", "path": "apps/worker"},
    },
    "git": {"default_branch": "main", "working_branch_prefix": "agent/"},
}


class WorkspaceBootstrapTestCase(unittest.TestCase):
    def test_load_project_config_reads_json_compatible_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            write_project_config(repo_root)

            config = load_project_config(repo_root)

            self.assertEqual(config.name, "versefina")
            self.assertEqual(config.stack["frontend"]["path"], "apps/web")
            self.assertEqual(config.git["working_branch_prefix"], "agent/")

    def test_bootstrap_target_repo_writes_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            write_project_config(repo_root)

            result = bootstrap_target_repo(repo_root)

            self.assertEqual(result.project.name, "versefina")
            marker_payload = json.loads(result.marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker_payload["status"], "bootstrap-ready")
            self.assertEqual(marker_payload["stack_paths"]["backend"], "apps/api")

    def test_bootstrap_target_repo_can_commit_marker(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is not available")

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            write_project_config(repo_root)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)

            result = bootstrap_target_repo(repo_root, commit=True, message="chore: bootstrap marker")

            self.assertIsNotNone(result.commit_sha)
            commit_subject = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(commit_subject, "chore: bootstrap marker")


def write_project_config(repo_root: Path) -> None:
    agents_dir = repo_root / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "project.yaml").write_text(
        json.dumps(PROJECT_YAML, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
