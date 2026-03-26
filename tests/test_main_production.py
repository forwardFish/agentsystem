from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import main_production as main_production_module
from main_production import _collect_changed_files_from_state, _resolve_frontend_install_command, _should_prepare_local_dependencies
from agentsystem.orchestration.workspace_manager import SnapshotSyncConflictError


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
            (base / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
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
                output = main_production_module.run_prod_task(
                    story_file,
                    env="test",
                    project="agentHire",
                    task_overrides={
                        "auto_run": False,
                        "formal_entry": False,
                    },
                )

            self.assertFalse(output["success"])
            self.assertIn("INVALID_CONCURRENT_GRAPH_UPDATE", output["error"])
            self.assertTrue((repo_root / "tasks" / "runtime" / "story_failures" / "S1-001.json").exists())
            self.assertTrue((repo_root / "tasks" / "runtime" / "story_handoffs" / "S1-001.md").exists())
            self.assertTrue((repo_root / "tasks" / "runtime" / "story_admissions" / "S1-001.json").exists())
            resume_state = json.loads((repo_root / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_state["status"], "interrupted")
            self.assertEqual(resume_state["story_id"], "S1-001")
            self.assertIn("execution_policy", resume_state)
            self.assertIn("interaction_policy", resume_state)
            self.assertIn("pause_policy", resume_state)
            self.assertIn("blocker_class", resume_state)
            status_registry = json.loads((repo_root / "tasks" / "story_status_registry.json").read_text(encoding="utf-8"))
            self.assertEqual(status_registry["stories"][0]["status"], "failed")
            reviews = json.loads((repo_root / "tasks" / "story_acceptance_reviews.json").read_text(encoding="utf-8"))
            self.assertEqual(reviews["reviews"][0]["verdict"], "rejected")
            self.assertTrue((system_root / "runs" / "prod_audit_task-demo.json").exists())

    def test_run_prod_task_injects_continuity_bundle_into_workflow_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            system_root = base / "agentsystem_root"
            repo_root = base / "versefina"
            sprint_dir = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            (base / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            story_file = epic_dir / "S1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "S1-001",
                        "story_id": "S1-001",
                        "blast_radius": "L1",
                        "goal": "Inject continuity before workflow",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            captured_task: dict[str, object] = {}

            class FakeGitAdapter:
                def __init__(self, _path: Path | str) -> None:
                    self.path = Path(_path)

                def checkout_main_and_pull(self, _branch: str) -> None:
                    return None

                def get_current_commit(self) -> str:
                    return "abc123"

                def is_dirty(self) -> bool:
                    return False

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

                def cleanup_task_resources(self, _task_id: str) -> None:
                    return None

            class FakeLogger:
                def info(self, *_args, **_kwargs) -> None:
                    return None

                def error(self, *_args, **_kwargs) -> None:
                    return None

                def warning(self, *_args, **_kwargs) -> None:
                    return None

            class CapturingWorkflow:
                def __init__(self, _config: dict, _worktree_path: str, task: dict, task_id: str | None = None) -> None:
                    captured_task.update(task)
                    self.task_id = task_id or "task-demo"

                def run(self) -> dict:
                    return {"success": True, "error": None, "state": {"current_step": "doc_done", "last_node": "doc_writer", "acceptance_passed": True}}

            with (
                patch.object(main_production_module, "ROOT_DIR", system_root),
                patch("main_production.SystemConfigReader.load", return_value={"repo": {"versefina": str(repo_root)}, "agent": {"cleanup_on_success": "false"}}),
                patch("main_production.GitAdapter", FakeGitAdapter),
                patch("main_production.WorkspaceManager", FakeWorkspaceManager),
                patch("main_production.DevWorkflow", CapturingWorkflow),
                patch("main_production._prepare_local_dependencies", return_value=None),
                patch("main_production.get_logger", return_value=FakeLogger()),
                patch("main_production.RepoBConfigReader.load_all_config", return_value=type("Cfg", (), {"commands": {"format": []}})()),
            ):
                output = main_production_module.run_prod_task(
                    story_file,
                    env="test",
                    project="versefina",
                    task_overrides={"auto_run": False, "formal_entry": False},
                )

            self.assertTrue(output["success"])
            self.assertEqual(captured_task["continuity_trigger"], "fresh_start")
            self.assertIn("continuity_summary", captured_task)
            self.assertIn("continuity_now", captured_task)

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

    def test_run_prod_task_materializes_snapshot_changes_back_to_target_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            system_root = base / "agentsystem_root"
            repo_root = base / "versefina"
            sprint_dir = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            (base / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            story_file = epic_dir / "S1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "S1-001",
                        "story_id": "S1-001",
                        "blast_radius": "L1",
                        "goal": "Materialize snapshot changes",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}

            class FakeGitAdapter:
                def __init__(self, _path: Path | str) -> None:
                    self.path = Path(_path)
                    self.snapshot_mode = True
                    self.committed = False

                def checkout_main_and_pull(self, _branch: str) -> None:
                    return None

                def get_current_commit(self) -> str:
                    return "after-commit" if self.committed else "before-commit"

                def is_dirty(self) -> bool:
                    return True

                def get_working_tree_files(self) -> list[str]:
                    return ["apps/api/src/demo.py"]

                def add_all(self) -> None:
                    return None

                def commit(self, _message: str) -> None:
                    self.committed = True

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

                def cleanup_task_resources(self, _task_id: str) -> None:
                    return None

                def materialize_snapshot_changes(
                    self,
                    task_id: str,
                    *,
                    target_repo_path: Path,
                    changed_files: list[str] | None = None,
                ) -> dict[str, object]:
                    captured["task_id"] = task_id
                    captured["target_repo_path"] = str(target_repo_path)
                    captured["changed_files"] = list(changed_files or [])
                    return {
                        "status": "applied",
                        "report_path": str(self.worktree_root / ".meta" / task_id / "snapshot_sync_report.json"),
                        "applied_files": ["apps/api/src/demo.py"],
                        "deleted_files": [],
                    }

            class FakeLogger:
                def info(self, *_args, **_kwargs) -> None:
                    return None

                def error(self, *_args, **_kwargs) -> None:
                    return None

                def warning(self, *_args, **_kwargs) -> None:
                    return None

            class SuccessWorkflow:
                def __init__(self, _config: dict, _worktree_path: str, _task: dict, task_id: str | None = None) -> None:
                    self.task_id = task_id or "task-demo"

                def run(self) -> dict:
                    return {
                        "success": True,
                        "error": None,
                        "state": {
                            "current_step": "doc_done",
                            "last_node": "doc_writer",
                            "acceptance_passed": True,
                        },
                    }

            with (
                patch.object(main_production_module, "ROOT_DIR", system_root),
                patch("main_production.SystemConfigReader.load", return_value={"repo": {"versefina": str(repo_root)}, "agent": {"cleanup_on_success": "false"}}),
                patch("main_production.GitAdapter", FakeGitAdapter),
                patch("main_production.WorkspaceManager", FakeWorkspaceManager),
                patch("main_production.DevWorkflow", SuccessWorkflow),
                patch("main_production._prepare_local_dependencies", return_value=None),
                patch("main_production.get_logger", return_value=FakeLogger()),
                patch("main_production.RepoBConfigReader.load_all_config", return_value=type("Cfg", (), {"commands": {"format": []}})()),
            ):
                output = main_production_module.run_prod_task(
                    story_file,
                    env="test",
                    project="versefina",
                    task_overrides={"auto_run": False, "formal_entry": False},
                )

            self.assertTrue(output["success"])
            self.assertEqual(captured["task_id"], "task-demo")
            self.assertEqual(Path(str(captured["target_repo_path"])).resolve(), repo_root.resolve())
            self.assertEqual(captured["changed_files"], ["apps/api/src/demo.py"])
            self.assertEqual(output["state"]["snapshot_sync_report"]["status"], "applied")

    def test_run_prod_task_persists_recoverable_failure_when_snapshot_materialization_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            system_root = base / "agentsystem_root"
            repo_root = base / "versefina"
            sprint_dir = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            (base / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            story_file = epic_dir / "S1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "S1-001",
                        "story_id": "S1-001",
                        "blast_radius": "L1",
                        "goal": "Conflict during snapshot materialization",
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
                    self.snapshot_mode = True

                def checkout_main_and_pull(self, _branch: str) -> None:
                    return None

                def get_current_commit(self) -> str:
                    return "before-commit"

                def is_dirty(self) -> bool:
                    return True

                def get_working_tree_files(self) -> list[str]:
                    return ["apps/api/src/demo.py"]

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

                def materialize_snapshot_changes(
                    self,
                    task_id: str,
                    *,
                    target_repo_path: Path,
                    changed_files: list[str] | None = None,
                ) -> dict[str, object]:
                    raise SnapshotSyncConflictError([{"path": "apps/api/src/demo.py", "reason": "target_modified_since_snapshot"}])

            class FakeLogger:
                def info(self, *_args, **_kwargs) -> None:
                    return None

                def error(self, *_args, **_kwargs) -> None:
                    return None

                def warning(self, *_args, **_kwargs) -> None:
                    return None

            class SuccessWorkflow:
                def __init__(self, _config: dict, _worktree_path: str, _task: dict, task_id: str | None = None) -> None:
                    self.task_id = task_id or "task-demo"

                def run(self) -> dict:
                    return {
                        "success": True,
                        "error": None,
                        "state": {
                            "current_step": "doc_done",
                            "last_node": "doc_writer",
                            "acceptance_passed": True,
                        },
                    }

            with (
                patch.object(main_production_module, "ROOT_DIR", system_root),
                patch("main_production.SystemConfigReader.load", return_value={"repo": {"versefina": str(repo_root)}, "agent": {"cleanup_on_success": "false"}}),
                patch("main_production.GitAdapter", FakeGitAdapter),
                patch("main_production.WorkspaceManager", FakeWorkspaceManager),
                patch("main_production.DevWorkflow", SuccessWorkflow),
                patch("main_production._prepare_local_dependencies", return_value=None),
                patch("main_production.get_logger", return_value=FakeLogger()),
                patch("main_production.RepoBConfigReader.load_all_config", return_value=type("Cfg", (), {"commands": {"format": []}})()),
            ):
                output = main_production_module.run_prod_task(
                    story_file,
                    env="test",
                    project="versefina",
                    task_overrides={"auto_run": False, "formal_entry": False},
                )

            self.assertFalse(output["success"])
            self.assertIn("Snapshot changes conflict", output["error"])
            failure_snapshot = repo_root / "tasks" / "runtime" / "story_failures" / "S1-001.json"
            self.assertTrue(failure_snapshot.exists())
            payload = json.loads(failure_snapshot.read_text(encoding="utf-8"))
            self.assertEqual(payload["story_id"], "S1-001")

    def test_run_prod_task_materializes_non_snapshot_worktree_changes_back_to_target_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            system_root = base / "agentsystem_root"
            repo_root = base / "versefina"
            sprint_dir = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            (base / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            story_file = epic_dir / "S1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "S1-001",
                        "story_id": "S1-001",
                        "blast_radius": "L1",
                        "goal": "Materialize worktree changes",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}

            class FakeGitAdapter:
                def __init__(self, _path: Path | str) -> None:
                    self.path = Path(_path)
                    self.snapshot_mode = False
                    self.committed = False

                def checkout_main_and_pull(self, _branch: str) -> None:
                    return None

                def get_current_commit(self) -> str:
                    return "after-commit" if self.committed else "before-commit"

                def is_dirty(self) -> bool:
                    return True

                def get_working_tree_files(self) -> list[str]:
                    return ["apps/api/src/demo.py"]

                def add_all(self) -> None:
                    return None

                def commit(self, _message: str) -> None:
                    self.committed = True

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

                def cleanup_task_resources(self, _task_id: str) -> None:
                    return None

                def materialize_worktree_changes(
                    self,
                    task_id: str,
                    *,
                    target_repo_path: Path,
                    changed_files: list[str] | None = None,
                ) -> dict[str, object]:
                    captured["task_id"] = task_id
                    captured["target_repo_path"] = str(target_repo_path)
                    captured["changed_files"] = list(changed_files or [])
                    return {
                        "status": "applied",
                        "report_path": str(self.worktree_root / ".meta" / task_id / "snapshot_sync_report.json"),
                        "applied_files": ["apps/api/src/demo.py"],
                        "deleted_files": [],
                    }

            class FakeLogger:
                def info(self, *_args, **_kwargs) -> None:
                    return None

                def error(self, *_args, **_kwargs) -> None:
                    return None

                def warning(self, *_args, **_kwargs) -> None:
                    return None

            class SuccessWorkflow:
                def __init__(self, _config: dict, _worktree_path: str, _task: dict, task_id: str | None = None) -> None:
                    self.task_id = task_id or "task-demo"

                def run(self) -> dict:
                    return {
                        "success": True,
                        "error": None,
                        "state": {
                            "current_step": "doc_done",
                            "last_node": "doc_writer",
                            "acceptance_passed": True,
                        },
                    }

            with (
                patch.object(main_production_module, "ROOT_DIR", system_root),
                patch("main_production.SystemConfigReader.load", return_value={"repo": {"versefina": str(repo_root)}, "agent": {"cleanup_on_success": "false"}}),
                patch("main_production.GitAdapter", FakeGitAdapter),
                patch("main_production.WorkspaceManager", FakeWorkspaceManager),
                patch("main_production.DevWorkflow", SuccessWorkflow),
                patch("main_production._prepare_local_dependencies", return_value=None),
                patch("main_production.get_logger", return_value=FakeLogger()),
                patch("main_production.RepoBConfigReader.load_all_config", return_value=type("Cfg", (), {"commands": {"format": []}})()),
            ):
                output = main_production_module.run_prod_task(
                    story_file,
                    env="test",
                    project="versefina",
                    task_overrides={"auto_run": False, "formal_entry": False},
                )

            self.assertTrue(output["success"])
            self.assertEqual(captured["task_id"], "task-demo")
            self.assertEqual(Path(str(captured["target_repo_path"])).resolve(), repo_root.resolve())
            self.assertEqual(captured["changed_files"], ["apps/api/src/demo.py"])
            self.assertEqual(output["state"]["snapshot_sync_report"]["status"], "applied")


if __name__ == "__main__":
    unittest.main()
