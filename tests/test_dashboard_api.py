from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.dashboard import main as dashboard_main


class DashboardApiTestCase(unittest.TestCase):
    def test_load_tasks_reads_audit_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            runs_dir.mkdir(parents=True)
            audit_file = runs_dir / "prod_audit_task-demo.json"
            audit_file.write_text(
                json.dumps(
                    {
                        "task_id": "task-demo",
                        "task_name": "Add subtitle to dashboard page",
                        "success": True,
                        "branch": "agent/l1-task-demo",
                        "commit": "abc123",
                        "result": {"task_payload": {"blast_radius": "L1", "mode": "Fast"}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(dashboard_main, "RUNS_DIR", runs_dir):
                tasks = dashboard_main.load_tasks()

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["task_id"], "task-demo")
            self.assertEqual(tasks[0]["task_name"], "Add subtitle to dashboard page")
            self.assertEqual(tasks[0]["status"], "success")

    def test_load_task_detail_reads_meta_artifacts_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runs_dir = base / "runs"
            meta_dir = base / "repo-worktree" / ".meta" / "task-demo"
            (meta_dir / "pr_prep").mkdir(parents=True)
            (meta_dir / "review").mkdir(parents=True)
            (meta_dir / "code_style_review").mkdir(parents=True)
            (meta_dir / "code_acceptance").mkdir(parents=True)
            (meta_dir / "acceptance").mkdir(parents=True)
            (meta_dir / "delivery").mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (runs_dir / "prod_audit_task-demo.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-demo",
                        "success": True,
                        "result": {
                            "test_passed": True,
                            "review_passed": True,
                            "code_acceptance_passed": True,
                            "acceptance_passed": True,
                            "fix_attempts": 1,
                            "blocking_issues": ["Issue A"],
                            "task_payload": {"acceptance_criteria": ["schema file exists"]},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (meta_dir / "pr_prep" / "pr_description.md").write_text("PR body", encoding="utf-8")
            (meta_dir / "pr_prep" / "commit_message.txt").write_text("feat: demo", encoding="utf-8")
            (meta_dir / "review" / "review_report.md").write_text("review body", encoding="utf-8")
            (meta_dir / "code_style_review" / "code_style_review_report.md").write_text("code style body", encoding="utf-8")
            (meta_dir / "code_acceptance" / "code_acceptance_report.md").write_text("code acceptance body", encoding="utf-8")
            (meta_dir / "acceptance" / "acceptance_report.md").write_text("acceptance body", encoding="utf-8")
            (meta_dir / "delivery" / "story_delivery_report.md").write_text("delivery body", encoding="utf-8")
            (meta_dir / "delivery" / "story_completion_standard.md").write_text("completion standard", encoding="utf-8")

            with (
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "REPO_META_DIR", base / "repo-worktree" / ".meta"),
            ):
                detail = dashboard_main.load_task_detail("task-demo")

            self.assertEqual(detail["task_id"], "task-demo")
            self.assertEqual(detail["artifacts"]["pr_description"], "PR body")
            self.assertEqual(detail["artifacts"]["commit_message"], "feat: demo")
            self.assertEqual(detail["artifacts"]["review_report"], "review body")
            self.assertEqual(detail["artifacts"]["code_style_review_report"], "code style body")
            self.assertEqual(detail["artifacts"]["code_acceptance_report"], "code acceptance body")
            self.assertEqual(detail["artifacts"]["acceptance_report"], "acceptance body")
            self.assertEqual(detail["artifacts"]["delivery_report"], "delivery body")
            self.assertEqual(detail["artifacts"]["completion_standard"], "completion standard")
            self.assertTrue(detail["completion"]["acceptance_passed"])
            self.assertEqual(detail["completion"]["fix_attempts"], 1)
            self.assertIn("collaboration", detail)

    def test_load_task_collaboration_reads_state_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runs_dir = base / "runs"
            runs_dir.mkdir(parents=True)
            (runs_dir / "prod_audit_task-demo.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-demo",
                        "success": True,
                        "result": {
                            "collaboration_trace_id": "trace_task-demo",
                            "collaboration_started_at": "2026-03-13T10:00:00",
                            "collaboration_ended_at": "2026-03-13T10:05:00",
                            "shared_blackboard": {"current_goal": "Finish story"},
                            "handoff_packets": [{"packet_id": "p1", "from_agent": "Requirement", "to_agent": "Builder"}],
                            "issues_to_fix": [{"issue_id": "i1", "title": "Blocking issue"}],
                            "resolved_issues": [{"issue_id": "i2", "title": "Resolved issue"}],
                            "all_deliverables": [{"deliverable_id": "d1", "name": "Report"}],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(dashboard_main, "RUNS_DIR", runs_dir):
                collaboration = dashboard_main.load_task_collaboration("task-demo")

            self.assertEqual(collaboration["task_id"], "task-demo")
            self.assertEqual(collaboration["trace_id"], "trace_task-demo")
            self.assertEqual(collaboration["shared_blackboard"]["current_goal"], "Finish story")
            self.assertEqual(collaboration["handoff_packets"][0]["packet_id"], "p1")

    def test_load_backlog_hierarchy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runs_dir = base / "runs"
            backlog_dir = tasks_dir / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_0_contract_foundation"
            epic_dir = sprint_dir / "epic_0_1_platform_contract"
            epic_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (backlog_dir / "sprint_overview.md").write_text("# Backlog Overview", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint Plan", encoding="utf-8")
            (sprint_dir / "execution_order.txt").write_text("S0-001\n", encoding="utf-8")
            (sprint_dir / "epic_0_1_platform_contract.md").write_text("# Epic Contract", encoding="utf-8")
            (epic_dir / "S0-001_profile_schema.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S0-001",
                        "task_name: TradingAgentProfile Schema",
                        "story_id: S0-001",
                        "sprint: Sprint 0",
                        "epic: Epic 0.1 Platform Contract",
                        "blast_radius: L1",
                        "execution_mode: Safe",
                        "goal: Define trading profile schema",
                        "acceptance_criteria:",
                        "  - schema file exists",
                        "related_files:",
                        "  - docs/contracts/trading_agent_profile.schema.json",
                        "primary_files:",
                        "  - docs/contracts/trading_agent_profile.schema.json",
                    ]
                ),
                encoding="utf-8",
            )
            (runs_dir / "prod_audit_task-story.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-story",
                        "success": True,
                        "branch": "agent/l1-task-story",
                        "commit": "abc999",
                        "result": {
                            "task_payload": {
                                "story_id": "S0-001",
                                "task_id": "S0-001",
                                "goal": "Define trading profile schema",
                                "acceptance_criteria": ["schema file exists"],
                            },
                            "test_passed": True,
                            "review_passed": True,
                            "code_acceptance_passed": True,
                            "acceptance_passed": True,
                            "fix_attempts": 0,
                            "blocking_issues": [],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
            ):
                backlogs = dashboard_main.load_backlogs()
                backlog_detail = dashboard_main.load_backlog_detail("backlog_v1")
                sprint_detail = dashboard_main.load_sprint_detail("backlog_v1", "sprint_0_contract_foundation")
                story_detail = dashboard_main.load_story_detail("backlog_v1", "sprint_0_contract_foundation", "S0-001")

            self.assertEqual(backlogs[0]["id"], "backlog_v1")
            self.assertEqual(backlog_detail["sprints"][0]["status"], "done")
            self.assertEqual(sprint_detail["execution_order"], ["S0-001"])
            self.assertEqual(sprint_detail["epics"][0]["stories"][0]["story_id"], "S0-001")
            self.assertEqual(story_detail["story"]["task_name"], "TradingAgentProfile Schema")
            self.assertEqual(story_detail["latest_task_id"], "task-story")
            self.assertEqual(story_detail["status"], "done")
            self.assertTrue(story_detail["task_detail"]["completion"]["acceptance_passed"])


if __name__ == "__main__":
    unittest.main()
