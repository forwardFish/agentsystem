from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import main_production as main_production_module
from main_production import _collect_changed_files_from_state, _resolve_frontend_install_command, _should_prepare_local_dependencies


class MainProductionTestCase(unittest.TestCase):
    def test_runtime_story_skips_frontend_dependency_prep(self) -> None:
        self.assertFalse(
            _should_prepare_local_dependencies(
                {
                    "story_kind": "runtime_data",
                    "qa_strategy": "runtime",
                    "has_browser_surface": False,
                }
            )
        )

    def test_ui_story_keeps_frontend_dependency_prep(self) -> None:
        self.assertTrue(
            _should_prepare_local_dependencies(
                {
                    "story_kind": "ui",
                    "qa_strategy": "browser",
                    "has_browser_surface": True,
                }
            )
        )

    def test_resolve_frontend_install_command_prefers_package_lock_for_npm_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            web_root = Path(tmp)
            (web_root / "package-lock.json").write_text("{}", encoding="utf-8")
            self.assertEqual(_resolve_frontend_install_command(web_root), "npm --prefix apps/web ci")

    def test_resolve_frontend_install_command_prefers_pnpm_when_lockfile_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            web_root = Path(tmp)
            (web_root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'", encoding="utf-8")
            (web_root / "package-lock.json").write_text("{}", encoding="utf-8")
            self.assertEqual(_resolve_frontend_install_command(web_root), "pnpm --dir apps/web install --frozen-lockfile")

    def test_run_prod_task_persists_recoverable_failure_when_workflow_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            system_root = base / "agentsystem_root"
            repo_root = base / "agentHire"
            sprint_dir = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            story_file = epic_dir / "S1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "S1-001",
                        "story_id": "S1-001",
                        "blast_radius": "L1",
                        "goal": "Implement recoverable failure persistence",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            class FakeGitAdapter:
                def __init__(self, _path: Path | str) -> None:
                    self.path = Path(_path)

                def checkout_main_and_pull(self, _branch: str) -> None:
                    return None

            class FakeWorkspaceManager:
                def __init__(self, _repo_b_path: Path, worktree_root: Path) -> None:
                    self.worktree_root = Path(worktree_root)
                    self.worktree_root.mkdir(parents=True, exist_ok=True)

                def generate_task_id(self, _seed: str) -> str:
                    return "task-demo"

                def create_worktree(self, task_id: str, _branch_name: str) -> Path:
                    path = self.worktree_root / task_id
                    path.mkdir(parents=True, exist_ok=True)
                    return path

                def update_task_state(self, _task_id: str, _payload: dict[str, object]) -> None:
                    return None

            class RaisingWorkflow:
                def __init__(self, _config: dict, _worktree_path: str, _task: dict, task_id: str | None = None) -> None:
                    self.task_id = task_id or "task-demo"

                def run(self) -> dict:
                    raise RuntimeError("INVALID_CONCURRENT_GRAPH_UPDATE on last_node")

            class FakeLogger:
                def info(self, *_args, **_kwargs) -> None:
                    return None

                def error(self, *_args, **_kwargs) -> None:
                    return None

                def warning(self, *_args, **_kwargs) -> None:
                    return None

            with (
                patch.object(main_production_module, "ROOT_DIR", system_root),
                patch("main_production.SystemConfigReader.load", return_value={"repo": {"agentHire": str(repo_root)}, "agent": {"cleanup_on_success": "false"}}),
                patch("main_production.GitAdapter", FakeGitAdapter),
                patch("main_production.WorkspaceManager", FakeWorkspaceManager),
                patch("main_production.DevWorkflow", RaisingWorkflow),
                patch("main_production._prepare_local_dependencies", return_value=None),
                patch("main_production.get_logger", return_value=FakeLogger()),
            ):
                output = main_production_module.run_prod_task(story_file, env="test", project="agentHire")

            self.assertFalse(output["success"])
            self.assertIn("INVALID_CONCURRENT_GRAPH_UPDATE", output["error"])
            self.assertTrue((repo_root / "tasks" / "runtime" / "story_failures" / "S1-001.json").exists())
            self.assertTrue((repo_root / "tasks" / "runtime" / "story_handoffs" / "S1-001.md").exists())
            resume_state = json.loads((repo_root / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_state["status"], "interrupted")
            self.assertEqual(resume_state["story_id"], "S1-001")
            status_registry = json.loads((repo_root / "tasks" / "story_status_registry.json").read_text(encoding="utf-8"))
            self.assertEqual(status_registry["stories"][0]["status"], "failed")
            reviews = json.loads((repo_root / "tasks" / "story_acceptance_reviews.json").read_text(encoding="utf-8"))
            self.assertEqual(reviews["reviews"][0]["verdict"], "rejected")
            self.assertTrue((system_root / "runs" / "prod_audit_task-demo.json").exists())

    def test_collect_changed_files_from_state_merges_staged_files_and_filters_cache_entries(self) -> None:
        files = _collect_changed_files_from_state(
            {
                "dev_results": {
                    "backend": {
                        "updated_files": [
                            "D:/workspace/repo/apps/api/src/infra/db/tables.py",
                        ]
                    }
                },
                "staged_files": [
                    "apps/api/alembic/versions/0001_agent_marketplace_baseline.py",
                    "apps/api/src/__pycache__/main.cpython-313.pyc",
                ],
            }
        )

        self.assertEqual(
            files,
            [
                "apps/api/src/infra/db/tables.py",
                "apps/api/alembic/versions/0001_agent_marketplace_baseline.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
