from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.orchestration.checkpoint_saver import MemoryTaskCheckpointSaver, PostgresCheckpointSaver, build_task_checkpoint_saver
from agentsystem.orchestration.task_state_machine import TaskStateMachine
from agentsystem.orchestration.workspace_manager import WorkspaceManager


class CheckpointRecoveryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.config = SystemConfigReader().load(root / "config" / "test.yaml")

    def setUp(self) -> None:
        self.saver = build_task_checkpoint_saver(self.config)
        if not isinstance(self.saver, PostgresCheckpointSaver):
            self.skipTest("Postgres checkpoint store is not available")

    def tearDown(self) -> None:
        if isinstance(self.saver, PostgresCheckpointSaver):
            self.saver.delete("test-task-001")
            self.saver.delete("checkpoint-task")
            self.saver.close()

    def test_save_and_load(self) -> None:
        self.saver.save(
            task_id="test-task-001",
            state="implementing",
            workspace_path="agent-workspaces/test-agent-workspace",
            metadata={"test_pending": True, "files_changed": 2},
        )

        checkpoint = self.saver.load("test-task-001")

        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint["state"], "implementing")
        self.assertTrue(checkpoint["metadata"]["test_pending"])

    def test_list_all(self) -> None:
        self.saver.save(
            task_id="test-task-001",
            state="verifying",
            workspace_path="agent-workspaces/test-agent-workspace",
            metadata={"test_pending": False},
        )
        checkpoints = self.saver.list_all()
        self.assertTrue(any(item["task_id"] == "test-task-001" for item in checkpoints))

    def test_task_state_machine_resume_reads_saved_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_file = root / "current.yaml"
            task_file.write_text("task_name: checkpoint task\n", encoding="utf-8")

            workspace_manager = WorkspaceManager(repo_root=root)
            task_id = "checkpoint-task"
            worktree_path = workspace_manager.create_worktree(task_id, f"feature/{task_id}")
            self.saver.save(
                task_id=task_id,
                state="implementing",
                workspace_path=str(worktree_path),
                metadata={"retry_count": 1, "max_retries": 3},
            )

            service = TaskStateMachine(self.config, workspace_manager)
            restored = service.run(task_file, resume=True)

            self.assertEqual(restored["status"], "implementing")
            self.assertEqual(restored["retry_count"], 1)


class MemoryCheckpointFallbackTestCase(unittest.TestCase):
    def test_memory_checkpoint_store_round_trip(self) -> None:
        saver = MemoryTaskCheckpointSaver()
        saver.save("memory-task", "planning", "repo-worktree/memory-task", {"step": 1})

        checkpoint = saver.load("memory-task")

        self.assertEqual(checkpoint["state"], "planning")
        self.assertEqual(checkpoint["metadata"]["step"], 1)


if __name__ == "__main__":
    unittest.main()
