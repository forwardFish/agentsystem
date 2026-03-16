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
            (sprint_dir / "sprint_quality_report.md").write_text("# Sprint Quality", encoding="utf-8")
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
            self.assertEqual(sprint_detail["quality_report_markdown"], "# Sprint Quality")
            self.assertEqual(sprint_detail["epics"][0]["stories"][0]["story_id"], "S0-001")
            self.assertEqual(story_detail["story"]["task_name"], "TradingAgentProfile Schema")
            self.assertEqual(story_detail["latest_task_id"], "task-story")
            self.assertEqual(story_detail["status"], "done")
            self.assertTrue(story_detail["task_detail"]["completion"]["acceptance_passed"])

    def test_story_status_registry_marks_story_done_without_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runs_dir = base / "runs"
            backlog_dir = tasks_dir / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_1_statement_to_agent"
            epic_dir = sprint_dir / "epic_1_1_statement_ingestion"
            epic_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (backlog_dir / "sprint_overview.md").write_text("# Backlog Overview", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint Plan", encoding="utf-8")
            (sprint_dir / "epic_1_1_statement_ingestion.md").write_text("# Epic", encoding="utf-8")
            (epic_dir / "S1-003_file_detection.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S1-003",
                        "task_name: File Type Detection",
                        "story_id: S1-003",
                        "sprint: Sprint 1",
                        "epic: Epic 1.1 Statement Ingestion",
                        "blast_radius: L1",
                    ]
                ),
                encoding="utf-8",
            )
            (tasks_dir / "story_status_registry.json").write_text(
                json.dumps(
                    {
                        "stories": [
                            {
                                "story_id": "S1-003",
                                "task_id": "business-validation-s1-003",
                                "status": "done",
                                "commit": "abc123",
                                "verified_at": "2026-03-16T11:00:00+08:00",
                                "source": "versefina_business_validation",
                                "repository": "versefina",
                                "summary": "Validated real file type detection flow.",
                                "evidence": [
                                    "Validated csv detection",
                                    "Validated mime mismatch rejection",
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", tasks_dir / "story_status_registry.json"),
            ):
                backlog_detail = dashboard_main.load_backlog_detail("backlog_v1")
                sprint_detail = dashboard_main.load_sprint_detail("backlog_v1", "sprint_1_statement_to_agent")
                story_detail = dashboard_main.load_story_detail("backlog_v1", "sprint_1_statement_to_agent", "S1-003")

            self.assertEqual(backlog_detail["sprints"][0]["status"], "done")
            self.assertEqual(sprint_detail["epics"][0]["stories"][0]["status"], "done")
            self.assertEqual(story_detail["status"], "done")
            self.assertEqual(story_detail["latest_run"]["commit"], "abc123")
            self.assertEqual(story_detail["latest_run"]["repository"], "versefina")
            self.assertEqual(story_detail["latest_run"]["summary"], "Validated real file type detection flow.")
            self.assertEqual(len(story_detail["latest_run"]["evidence"]), 2)

    def test_registry_only_story_detail_exposes_business_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            finahunt_tasks = base / "finahunt_tasks"
            backlog_dir = finahunt_tasks / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_0_info_foundation"
            epic_dir = sprint_dir / "epic_0_2_runtime_governance"
            epic_dir.mkdir(parents=True)
            (backlog_dir / "sprint_overview.md").write_text("# Finahunt", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint 0", encoding="utf-8")
            (sprint_dir / "epic_0_2_runtime_governance.md").write_text("# Epic", encoding="utf-8")
            (epic_dir / "S0-005_runtime_graph_input_output_baseline.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S0-005",
                        "task_name: Runtime Graph 输入输出基线",
                        "story_id: S0-005",
                    ]
                ),
                encoding="utf-8",
            )
            (finahunt_tasks / "story_status_registry.json").write_text(
                json.dumps(
                    {
                        "stories": [
                            {
                                "story_id": "S0-005",
                                "status": "done",
                                "project": "finahunt",
                                "source": "finahunt_foundation_validation",
                                "validation_summary": "runtime graph foundation validated",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", finahunt_tasks),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_tasks / "story_status_registry.json"),
            ):
                detail = dashboard_main.load_story_detail("backlog_v1", "sprint_0_info_foundation", "S0-005", "finahunt")

            self.assertEqual(detail["status"], "done")
            self.assertEqual(detail["task_detail"]["business_validation"]["source"], "finahunt_foundation_validation")

    def test_metrics_follow_project_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            versefina_tasks = base / "versefina_tasks"
            finahunt_tasks = base / "finahunt_tasks"
            runs_dir = base / "runs"
            runs_dir.mkdir(parents=True)
            for tasks_root, sprint_name, story_id in [
                (versefina_tasks, "sprint_1_statement_to_agent", "S1-001"),
                (finahunt_tasks, "sprint_0_info_foundation", "S0-001"),
            ]:
                epic_dir = tasks_root / "backlog_v1" / sprint_name / "epic_demo"
                epic_dir.mkdir(parents=True)
                (tasks_root / "backlog_v1" / "sprint_overview.md").write_text("# Backlog", encoding="utf-8")
                (tasks_root / "backlog_v1" / sprint_name / "sprint_plan.md").write_text("# Sprint", encoding="utf-8")
                (tasks_root / "backlog_v1" / sprint_name / "epic_demo.md").write_text("# Epic", encoding="utf-8")
                (epic_dir / f"{story_id}_demo.yaml").write_text(
                    f"task_id: {story_id}\nstory_id: {story_id}\ntask_name: demo\nacceptance_criteria:\n  - one\n",
                    encoding="utf-8",
                )
            (versefina_tasks / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
            (finahunt_tasks / "story_status_registry.json").write_text(
                json.dumps(
                    {
                        "stories": [
                            {
                                "story_id": "S0-001",
                                "status": "done",
                                "project": "finahunt",
                                "verified_at": "2026-03-16T10:00:00+08:00",
                                "validation_summary": "foundation done",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (runs_dir / "prod_audit_task-versefina.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-versefina",
                        "success": True,
                        "result": {
                            "task_payload": {"story_id": "S1-001", "task_id": "S1-001", "acceptance_criteria": ["one"]},
                            "fix_attempts": 2,
                            "blocking_issues": ["x"],
                            "acceptance_report": "- one: satisfied",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", versefina_tasks),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", versefina_tasks / "story_status_registry.json"),
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", finahunt_tasks),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_tasks / "story_status_registry.json"),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
            ):
                versefina_metrics = dashboard_main.compute_metrics("versefina")
                finahunt_metrics = dashboard_main.compute_metrics("finahunt")

            self.assertEqual(versefina_metrics["total_tasks"], 1)
            self.assertEqual(versefina_metrics["avg_retry_rounds"], 2.0)
            self.assertEqual(finahunt_metrics["total_tasks"], 1)
            self.assertEqual(finahunt_metrics["avg_retry_rounds"], 0.0)
            self.assertEqual(finahunt_metrics["first_pass_rate"], 100.0)

    def test_load_projects_and_finahunt_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            versefina_tasks = base / "versefina_tasks"
            finahunt_tasks = base / "finahunt_tasks"
            versefina_tasks.mkdir(parents=True)
            finahunt_tasks.mkdir(parents=True)

            (versefina_tasks / "backlog_v1").mkdir()
            (versefina_tasks / "backlog_v1" / "sprint_overview.md").write_text("# Versefina", encoding="utf-8")

            finahunt_backlog = finahunt_tasks / "backlog_v1"
            finahunt_backlog.mkdir()
            (finahunt_backlog / "sprint_overview.md").write_text("# Finahunt", encoding="utf-8")
            sprint_dir = finahunt_backlog / "sprint_0_info_foundation"
            epic_dir = sprint_dir / "epic_0_1_source_contract"
            epic_dir.mkdir(parents=True)
            (sprint_dir / "sprint_plan.md").write_text("# Sprint 0", encoding="utf-8")
            (sprint_dir / "epic_0_1_source_contract.md").write_text("# Epic", encoding="utf-8")
            (epic_dir / "S0-001_source_registry_baseline.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S0-001",
                        "task_name: Source Registry Baseline",
                        "story_id: S0-001",
                        "sprint: Sprint 0",
                        "epic: Epic 0.1 Source Contract",
                        "blast_radius: L1",
                    ]
                ),
                encoding="utf-8",
            )
            (finahunt_tasks / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")

            with (
                patch.object(dashboard_main, "TASKS_DIR", versefina_tasks),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", versefina_tasks / "story_status_registry.json"),
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", finahunt_tasks),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_tasks / "story_status_registry.json"),
            ):
                projects = dashboard_main.load_projects()
                finahunt_backlogs = dashboard_main.load_backlogs("finahunt")
                finahunt_detail = dashboard_main.load_backlog_detail("backlog_v1", "finahunt")

            self.assertEqual({project["id"] for project in projects}, {"versefina", "finahunt"})
            self.assertEqual(finahunt_backlogs[0]["project"], "finahunt")
            self.assertEqual(finahunt_detail["project"], "finahunt")
            self.assertEqual(finahunt_detail["sprints"][0]["name"], "sprint_0_info_foundation")

    def test_finahunt_story_ids_do_not_reuse_versefina_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            versefina_tasks = base / "versefina_tasks"
            finahunt_tasks = base / "finahunt_tasks"
            runs_dir = base / "runs"
            runs_dir.mkdir(parents=True)
            versefina_tasks.mkdir(parents=True)
            finahunt_tasks.mkdir(parents=True)

            backlog_dir = finahunt_tasks / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_0_info_foundation"
            epic_dir = sprint_dir / "epic_0_1_source_contract"
            epic_dir.mkdir(parents=True)
            (backlog_dir / "sprint_overview.md").write_text("# Finahunt", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint", encoding="utf-8")
            (sprint_dir / "epic_0_1_source_contract.md").write_text("# Epic", encoding="utf-8")
            (epic_dir / "S0-001_source_registry_baseline.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S0-001",
                        "task_name: Source Registry Baseline",
                        "story_id: S0-001",
                        "sprint: Sprint 0",
                        "epic: Epic 0.1 Source Contract",
                        "blast_radius: L1",
                    ]
                ),
                encoding="utf-8",
            )
            (finahunt_tasks / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")

            (runs_dir / "prod_audit_task-versefina.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-versefina",
                        "success": True,
                        "result": {
                            "task_payload": {
                                "story_id": "S0-001",
                                "task_id": "S0-001",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "TASKS_DIR", versefina_tasks),
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", finahunt_tasks),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_tasks / "story_status_registry.json"),
            ):
                sprint_detail = dashboard_main.load_sprint_detail("backlog_v1", "sprint_0_info_foundation", "finahunt")

            self.assertEqual(sprint_detail["epics"][0]["stories"][0]["status"], "not_started")


if __name__ == "__main__":
    unittest.main()
