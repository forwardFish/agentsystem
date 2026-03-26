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
                    "formal_entry": True,
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
                    "formal_acceptance_reviewer": "acceptance_gate",
                    "implemented": True,
                    "verified": True,
                    "agentized": True,
                    "accepted": True,
                    "evidence": ["runs/prod_audit_task-demo.json"],
                },
            )
            review_path = update_story_acceptance_review(
                repo_root,
                {
                    "project": "agentHire",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_0_project_bootstrap",
                    "story_id": "S0-001",
                    "reviewer": "acceptance_gate",
                    "verdict": "approved",
                    "acceptance_status": "approved",
                    "formal_entry": True,
                    "agent_mode_coverage": {
                        "required": ["plan-eng-review", "review", "qa"],
                        "executed": ["plan-eng-review", "review", "qa"],
                        "advisory": [],
                        "missing_required": [],
                        "all_required_executed": True,
                    },
                    "implemented": True,
                    "verified": True,
                    "agentized": True,
                    "accepted": True,
                    "evidence_paths": ["runs/prod_audit_task-demo.json"],
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

    def test_runtime_memory_downgrades_non_formal_success_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "finahunt"
            (repo_root / "tasks").mkdir(parents=True)
            (repo_root / "docs").mkdir(parents=True)

            status_path = update_story_status(
                repo_root,
                {
                    "project": "finahunt",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_demo",
                    "story_id": "S5-001",
                    "status": "done",
                },
            )
            review_path = update_story_acceptance_review(
                repo_root,
                {
                    "project": "finahunt",
                    "backlog_id": "backlog_v1",
                    "sprint_id": "sprint_demo",
                    "story_id": "S5-001",
                    "reviewer": "agentsystem",
                    "verdict": "approved",
                    "acceptance_status": "approved",
                },
            )

            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual(status_payload["stories"][0]["status"], "implemented_without_formal_flow")
            self.assertEqual(review_payload["reviews"][0]["acceptance_status"], "needs_followup")

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

    def test_invalid_delivery_batch_is_not_treated_as_formal_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "versefina"
            (repo_root / "tasks").mkdir(parents=True)
            status_path = update_story_status(
                repo_root,
                {
                    "project": "versefina",
                    "backlog_id": "roadmap_1_6",
                    "sprint_id": "roadmap_1_6_sprint_1",
                    "story_id": "E1-003",
                    "status": "done",
                    "attempt_status": "invalid_delivery_batch",
                    "implementation_contract": {"required_artifact_types": ["service"]},
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "required_artifact_types": ["service"],
                },
            )
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            entry = payload["stories"][0]
            self.assertEqual(entry["status"], "invalid_delivery_batch")
            self.assertFalse(entry["formal_flow_complete"])
            self.assertIn("invalid_delivery_batch", entry["formal_flow_gap_reasons"])

    def test_authoritative_rerun_clears_prior_invalidation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "versefina"
            (repo_root / "tasks").mkdir(parents=True)
            update_story_status(
                repo_root,
                {
                    "project": "versefina",
                    "backlog_id": "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                    "sprint_id": "E4-001_simulation_prepare_from_graph.yaml",
                    "story_id": "E4-001",
                    "status": "invalid_delivery_batch",
                    "attempt_status": "invalid_delivery_batch",
                    "invalidated_at": "2026-03-25T13:56:11",
                    "invalidated_reason": "invalid_delivery_batch",
                    "implementation_contract": {"required_artifact_types": ["service"]},
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "required_artifact_types": ["service"],
                },
            )
            update_story_acceptance_review(
                repo_root,
                {
                    "project": "versefina",
                    "backlog_id": "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                    "sprint_id": "E4-001_simulation_prepare_from_graph.yaml",
                    "story_id": "E4-001",
                    "reviewer": "acceptance_gate",
                    "acceptance_status": "invalid_delivery_batch",
                    "attempt_status": "invalid_delivery_batch",
                    "invalidated_at": "2026-03-25T13:56:11",
                    "invalidated_reason": "invalid_delivery_batch",
                    "formal_entry": True,
                    "implemented": True,
                    "verified": True,
                    "agentized": True,
                    "accepted": True,
                    "evidence_paths": ["runs/prod_audit_task-demo.json"],
                },
            )

            status_path = update_story_status(
                repo_root,
                {
                    "project": "versefina",
                    "backlog_id": "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                    "sprint_id": "E4-001_simulation_prepare_from_graph.yaml",
                    "story_id": "E4-001",
                    "status": "done",
                    "formal_entry": True,
                    "attempt_status": "authoritative",
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
                    "formal_acceptance_reviewer": "acceptance_gate",
                    "implementation_contract": {"required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"]},
                    "agent_execution_contract": [{"agent": "backend_dev"}, {"agent": "tester"}, {"agent": "acceptance_gate"}],
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "implemented": True,
                    "verified": True,
                    "agentized": True,
                    "accepted": True,
                    "evidence_paths": ["runs/prod_audit_task-demo.json"],
                },
            )
            review_path = update_story_acceptance_review(
                repo_root,
                {
                    "project": "versefina",
                    "backlog_id": "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                    "sprint_id": "E4-001_simulation_prepare_from_graph.yaml",
                    "story_id": "E4-001",
                    "reviewer": "acceptance_gate",
                    "verdict": "approved",
                    "acceptance_status": "approved",
                    "formal_entry": True,
                    "attempt_status": "authoritative",
                    "agent_mode_coverage": {
                        "required": ["plan-eng-review", "review", "qa"],
                        "executed": ["plan-eng-review", "review", "qa"],
                        "advisory": [],
                        "missing_required": [],
                        "all_required_executed": True,
                    },
                    "implementation_contract": {"required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"]},
                    "agent_execution_contract": [{"agent": "backend_dev"}, {"agent": "tester"}, {"agent": "acceptance_gate"}],
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "implemented": True,
                    "verified": True,
                    "agentized": True,
                    "accepted": True,
                    "evidence_paths": ["runs/prod_audit_task-demo.json"],
                },
            )

            status_payload = json.loads(status_path.read_text(encoding="utf-8"))
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            status_entry = status_payload["stories"][0]
            review_entry = review_payload["reviews"][0]
            self.assertEqual(status_entry["status"], "done")
            self.assertEqual(status_entry["attempt_status"], "authoritative")
            self.assertNotIn("invalidated_at", status_entry)
            self.assertNotIn("invalidated_reason", status_entry)
            self.assertEqual(review_entry["acceptance_status"], "approved")
            self.assertEqual(review_entry["attempt_status"], "authoritative")
            self.assertNotIn("invalidated_at", review_entry)
            self.assertNotIn("invalidated_reason", review_entry)


if __name__ == "__main__":
    unittest.main()
