from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentsystem.orchestration.runtime_memory import (
    update_agent_coverage_report,
    update_story_acceptance_review,
    update_story_status,
    write_current_handoff,
    write_resume_state,
    write_story_failure,
)


class RuntimeMemoryTestCase(unittest.TestCase):
    def test_runtime_memory_writes_resume_status_and_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "agentHire"
            (repo_root / "tasks").mkdir(parents=True)
            (repo_root / "docs").mkdir(parents=True)

            resume_path = write_resume_state(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-003",
                    "status": "interrupted",
                    "resume_from_story": "S0-003",
                },
            )
            handoff_paths = write_current_handoff(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-003",
                    "status": "interrupted",
                    "resume_from_story": "S0-003",
                    "root_cause": "stream disconnected",
                    "next_action": "resume",
                    "resume_command": "python cli.py auto-deliver --auto-run",
                    "evidence_paths": [],
                },
            )

            payload = json.loads(resume_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["story_id"], "S0-003")
            self.assertTrue(handoff_paths["workspace_handoff"].exists())
            self.assertTrue(handoff_paths["workspace_task"].exists())
            self.assertTrue(handoff_paths["project_handoff"].exists())

    def test_runtime_memory_updates_registries_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "agentHire"
            (repo_root / "tasks").mkdir(parents=True)
            (repo_root / "docs").mkdir(parents=True)

            status_path = update_story_status(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-001",
                    "status": "done",
                },
            )
            review_path = update_story_acceptance_review(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-001",
                    "reviewer": "agentsystem",
                    "verdict": "approved",
                },
            )
            json_report, md_report = update_agent_coverage_report(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-001",
                    "required_modes": ["plan-eng-review", "review", "qa"],
                    "executed_modes": ["plan-eng-review", "review", "qa"],
                    "advisory_modes": [],
                    "agent_mode_coverage": {
                        "required": ["plan-eng-review", "review", "qa"],
                        "executed": ["plan-eng-review", "review", "qa"],
                        "advisory": [],
                        "missing_required": [],
                        "all_required_executed": True,
                    },
                },
            )
            failure_path = write_story_failure(
                repo_root,
                "S0-003",
                {
                    "task_id": "task-demo",
                    "failure_type": "loop_detected",
                },
            )

            self.assertTrue(status_path.exists())
            self.assertTrue(review_path.exists())
            self.assertTrue(json_report.exists())
            self.assertTrue(md_report.exists())
            self.assertTrue(failure_path.exists())
            coverage_payload = json.loads(json_report.read_text(encoding="utf-8"))
            self.assertEqual(coverage_payload["coverage_status"], "complete")

    def test_write_resume_state_can_clear_stale_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "agentHire"
            (repo_root / "tasks").mkdir(parents=True)
            write_resume_state(
                repo_root,
                {
                    "project": "agentHire",
                    "story_id": "S1-001",
                    "status": "interrupted",
                    "resume_from_story": "S1-001",
                    "interruption_reason": "workflow_failed",
                },
            )
            resume_path = write_resume_state(
                repo_root,
                {
                    "project": "agentHire",
                    "status": "completed",
                },
                clear_keys=["story_id", "resume_from_story", "interruption_reason"],
            )
            payload = json.loads(resume_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertNotIn("story_id", payload)
            self.assertNotIn("resume_from_story", payload)
            self.assertNotIn("interruption_reason", payload)


if __name__ == "__main__":
    unittest.main()
