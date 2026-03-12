from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.integrations.checkpoint_saver import get_checkpoint_saver
from agentsystem.integrations.pr_approval_integration import approval_node_with_pr
from agentsystem.orchestration.identity_runtime import AgentIdentity
from agentsystem.orchestration.skill_registry import SkillMetadata, SkillRegistry
from agentsystem.orchestration.task_state_machine import TaskState, TaskStateMachine, TaskStatus, build_task_state_machine
from agentsystem.orchestration.workspace_manager import WorkspaceLockError, WorkspaceManager


class EngineeringCloseoutTestCase(unittest.TestCase):
    def test_task_state_machine_routes_failed_verification_to_retry(self) -> None:
        graph = build_task_state_machine()
        initial = TaskState(
            task_id="task-001",
            worktree_path="D:/tmp/task-001",
            test_result={"passed": False, "details": "failing test"},
        )

        result = graph.invoke(initial, config={"configurable": {"thread_id": "task-001"}})

        self.assertEqual(result["status"], TaskStatus.FAILED)
        self.assertEqual(result["retry_count"], 3)

    def test_workspace_manager_creates_updates_and_cleans_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = WorkspaceManager(repo_root=root)

            worktree = manager.create_worktree("task-001", "feature/task-001")
            self.assertTrue((worktree / "task.yaml").exists())
            manager.update_task_state("task-001", {"status": "implementing"})
            self.assertEqual(manager.get_task_state("task-001")["status"], "implementing")

            with self.assertRaises(WorkspaceLockError):
                manager.create_worktree("task-002", "feature/task-001")

            manager.clean_worktree("task-001", archive=True)
            self.assertFalse(worktree.exists())
            self.assertTrue((root / "archive" / "task-001" / "task.yaml").exists())

    def test_identity_runtime_reads_writes_memory_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            identity = AgentIdentity("dev-agent-001", tmp)
            loaded = identity.load_identity()
            identity.append_memory("完成任务 task-001")
            identity.write_heartbeat("running", "executing task-002")
            policy = identity.resolve_policy()

            self.assertEqual(loaded["agent_id"], "dev-agent-001")
            self.assertIn("完成任务", identity.read_memory())
            self.assertIn("run_tests", policy["permissions"])

    def test_skill_registry_registers_and_loads_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            registry = SkillRegistry(registry_path)
            registry.register_skill(
                SkillMetadata(
                    name="classify_risk",
                    version="1.0.0",
                    entry_point="agentsystem.skills_runtime.risk_classify:classify_risk",
                    description="classify risk level",
                )
            )

            func = registry.load_skill_function("classify_risk")

            self.assertIn("classify_risk", registry.list_available_skills())
            self.assertTrue(callable(func))

    def test_approval_node_without_github_env_stays_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "task-001"
            worktree.mkdir(parents=True)
            (worktree / "task.yaml").write_text("task_id: task-001\nbranch: feature/task-001\n", encoding="utf-8")

            state = TaskState(task_id="task-001", worktree_path=str(worktree))
            result = approval_node_with_pr(state)

            self.assertEqual(result.status, TaskStatus.GATED)
            self.assertFalse(result.approval_result["approved"])

    def test_checkpoint_saver_defaults_to_memory(self) -> None:
        saver = get_checkpoint_saver()
        self.assertIsNotNone(saver)

    def test_task_state_machine_generates_stable_id_for_non_ascii_task_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_file = root / "current.yaml"
            task_file.write_text("task_name: 给前端页面加个标题\n", encoding="utf-8")

            manager = WorkspaceManager(repo_root=root)
            service = TaskStateMachine({}, manager)
            result = service.run(task_file)

            self.assertRegex(result["task_id"], r"^task-[0-9a-f]{8}$")
            self.assertEqual(result["status"], "gated")

    def test_task_state_machine_checkpoint_is_json_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_file = root / "current.yaml"
            task_file.write_text("task_name: task checkpoint\n", encoding="utf-8")

            manager = WorkspaceManager(repo_root=root)
            service = TaskStateMachine({}, manager)
            service.run(task_file)
            checkpoint = service.save_checkpoint()

            self.assertIsInstance(checkpoint["status"], str)
            self.assertEqual(checkpoint["status"], "gated")


if __name__ == "__main__":
    unittest.main()
