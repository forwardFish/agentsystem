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
                            "workflow_plugin_id": "software_engineering",
                            "workflow_manifest_path": "config/workflows/software_engineering.yaml",
                            "workflow_agent_manifest_ids": [
                                "software_engineering.requirement_analysis",
                                "software_engineering.reviewer",
                            ],
                            "story_kind": "runtime_data",
                            "risk_level": "high",
                            "qa_strategy": "runtime",
                            "effective_qa_mode": "qa",
                            "required_modes": ["plan-eng-review", "review", "qa-only", "qa"],
                            "executed_modes": ["plan-eng-review", "qa", "review"],
                            "advisory_modes": ["plan-ceo-review"],
                            "next_recommended_actions": ["Run plan-ceo-review before locking the sprint scope."],
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
            self.assertEqual(detail["workflow"]["workflow_plugin_id"], "software_engineering")
            self.assertEqual(detail["workflow"]["workflow_manifest_path"], "config/workflows/software_engineering.yaml")
            self.assertEqual(detail["workflow"]["story_kind"], "runtime_data")
            self.assertEqual(detail["workflow"]["risk_level"], "high")
            self.assertEqual(detail["workflow"]["qa_strategy"], "runtime")
            self.assertEqual(detail["workflow"]["effective_qa_mode"], "qa")
            self.assertEqual(detail["workflow"]["required_modes"], ["plan-eng-review", "review", "qa-only", "qa"])
            self.assertEqual(detail["workflow"]["executed_modes"], ["plan-eng-review", "qa", "review"])
            self.assertEqual(detail["workflow"]["advisory_modes"], ["plan-ceo-review"])
            self.assertEqual(detail["workflow"]["mode_coverage"]["missing_required"], ["qa-only"])
            self.assertFalse(detail["workflow"]["mode_coverage"]["all_required_executed"])
            self.assertEqual(
                detail["workflow"]["agent_manifest_ids"],
                [
                    "software_engineering.requirement_analysis",
                    "software_engineering.reviewer",
                ],
            )
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
                            "workflow_plugin_id": "software_engineering",
                            "workflow_manifest_path": "config/workflows/software_engineering.yaml",
                            "workflow_agent_manifest_ids": [
                                "software_engineering.requirement_analysis",
                                "software_engineering.tester",
                                "software_engineering.doc_writer",
                            ],
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
            self.assertEqual(story_detail["workflow"]["workflow_plugin_id"], "software_engineering")
            self.assertEqual(
                story_detail["workflow"]["agent_manifest_ids"],
                [
                    "software_engineering.requirement_analysis",
                    "software_engineering.tester",
                    "software_engineering.doc_writer",
                ],
            )

    def test_load_sprint_detail_reads_agent_advice_and_closeout_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            sprint_runs_dir = base / "runs" / "sprints" / "versefina" / "sprint_1_statement_to_agent"
            backlog_dir = tasks_dir / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_1_statement_to_agent"
            sprint_dir.mkdir(parents=True)
            sprint_runs_dir.mkdir(parents=True)

            (backlog_dir / "sprint_overview.md").write_text("# Backlog Overview", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint Plan", encoding="utf-8")
            (sprint_dir / "execution_order.txt").write_text("S1-001\n", encoding="utf-8")
            (sprint_runs_dir / "sprint_agent_advice.json").write_text(
                json.dumps(
                    {
                        "risk_level": "high",
                        "story_kinds": ["ui", "runtime_data"],
                        "advisory_modes": ["design-consultation"],
                        "next_recommended_actions": ["Run design-consultation before large UI implementation starts."],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (sprint_runs_dir / "document_release_report.md").write_text("# Document Release", encoding="utf-8")
            (sprint_runs_dir / "retro_report.md").write_text("# Retro", encoding="utf-8")
            (sprint_runs_dir / "ship_advice.json").write_text(
                json.dumps({"advisory_modes": ["ship"]}, ensure_ascii=False),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "SPRINT_RUNS_DIR", base / "runs" / "sprints"),
            ):
                detail = dashboard_main.load_sprint_detail("backlog_v1", "sprint_1_statement_to_agent")

            self.assertEqual(detail["sprint_agent_advice"]["risk_level"], "high")
            self.assertEqual(detail["sprint_agent_advice"]["advisory_modes"], ["design-consultation"])
            self.assertEqual(detail["document_release_report_markdown"], "# Document Release")
            self.assertEqual(detail["retro_report_markdown"], "# Retro")
            self.assertEqual(detail["ship_advice"]["advisory_modes"], ["ship"])

    def test_story_detail_prefers_runtime_coverage_over_stale_audit_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runs_dir = base / "runs"
            backlog_dir = tasks_dir / "backlog_v1"
            sprint_dir = backlog_dir / "sprint_1_statement_to_agent"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)
            (tasks_dir / "runtime").mkdir(parents=True)

            (backlog_dir / "sprint_overview.md").write_text("# Backlog", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# Sprint", encoding="utf-8")
            (sprint_dir / "execution_order.txt").write_text("S1-001\n", encoding="utf-8")
            (epic_dir / "S1-001_demo.yaml").write_text(
                "\n".join(
                    [
                        "task_id: S1-001",
                        "task_name: Runtime Coverage Demo",
                        "story_id: S1-001",
                        "blast_radius: L1",
                        "goal: Demonstrate runtime coverage overlay",
                        "acceptance_criteria:",
                        "  - done",
                        "related_files:",
                        "  - apps/api/src/demo.py",
                    ]
                ),
                encoding="utf-8",
            )
            (tasks_dir / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
            (tasks_dir / "story_acceptance_reviews.json").write_text(json.dumps({"reviews": []}), encoding="utf-8")
            (tasks_dir / "runtime" / "agent_coverage_report.json").write_text(
                json.dumps(
                    {
                        "coverage_status": "complete",
                        "stories": [
                            {
                                "backlog_id": "backlog_v1",
                                "sprint_id": "sprint_1_statement_to_agent",
                                "story_id": "S1-001",
                                "required_modes": ["review", "qa"],
                                "executed_modes": ["review", "qa"],
                                "advisory_modes": [],
                                "agent_mode_coverage": {
                                    "required": ["review", "qa"],
                                    "executed": ["review", "qa"],
                                    "advisory": [],
                                    "missing_required": [],
                                    "all_required_executed": True,
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (runs_dir / "prod_audit_task-s1-001.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-s1-001",
                        "success": True,
                        "result": {
                            "task_payload": {
                                "project": "versefina",
                                "story_id": "S1-001",
                                "task_id": "S1-001",
                                "goal": "Demonstrate runtime coverage overlay",
                                "acceptance_criteria": ["done"],
                                "related_files": ["apps/api/src/demo.py"],
                            },
                            "required_modes": ["review", "qa-only", "qa"],
                            "executed_modes": ["review", "qa"],
                            "advisory_modes": [],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", tasks_dir / "story_status_registry.json"),
                patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", tasks_dir / "story_acceptance_reviews.json"),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
            ):
                detail = dashboard_main.load_story_detail("backlog_v1", "sprint_1_statement_to_agent", "S1-001")

            self.assertEqual(detail["workflow"]["required_modes"], ["review", "qa"])
            self.assertTrue(detail["workflow"]["mode_coverage"]["all_required_executed"])
            self.assertEqual(detail["task_detail"]["workflow"]["required_modes"], ["review", "qa"])

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
            agenthire_tasks = base / "agenthire_tasks"
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
                patch.object(dashboard_main, "AGENTHIRE_TASKS_DIR", agenthire_tasks),
                patch.object(dashboard_main, "AGENTHIRE_STORY_STATUS_REGISTRY", agenthire_tasks / "story_status_registry.json"),
            ):
                projects = dashboard_main.load_projects()
                finahunt_backlogs = dashboard_main.load_backlogs("finahunt")
                finahunt_detail = dashboard_main.load_backlog_detail("backlog_v1", "finahunt")

            self.assertEqual({project["id"] for project in projects}, {"versefina", "finahunt", "agentHire"})
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

    def test_load_finahunt_runtime_showcase_reads_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runtime_dir = base / "runtime"
            tasks_dir = base / "finahunt_tasks"
            sprint_2_dir = tasks_dir / "backlog_v1" / "sprint_2_catalyst_mining_core" / "epic_demo"
            sprint_2a_dir = tasks_dir / "backlog_v1" / "sprint_2a_early_theme_discovery_engine" / "epic_demo"
            sprint_2_dir.mkdir(parents=True)
            sprint_2a_dir.mkdir(parents=True)
            (tasks_dir / "backlog_v1" / "sprint_overview.md").write_text("# Finahunt", encoding="utf-8")
            (tasks_dir / "backlog_v1" / "sprint_2_catalyst_mining_core" / "sprint_plan.md").write_text("# Sprint 2", encoding="utf-8")
            (tasks_dir / "backlog_v1" / "sprint_2a_early_theme_discovery_engine" / "sprint_plan.md").write_text("# Sprint 2A", encoding="utf-8")
            (tasks_dir / "backlog_v1" / "sprint_2_catalyst_mining_core" / "epic_demo.md").write_text("# Epic", encoding="utf-8")
            (tasks_dir / "backlog_v1" / "sprint_2a_early_theme_discovery_engine" / "epic_demo.md").write_text("# Epic", encoding="utf-8")
            (sprint_2_dir / "S2-006_demo.yaml").write_text(
                "task_id: S2-006\nstory_id: S2-006\ntask_name: Structured Result Cards\nstory_inputs:\n  - cards input\nstory_process:\n  - build cards\nstory_outputs:\n  - cards output\nverification_basis:\n  - verify cards\nacceptance_criteria:\n  - cards exist\n",
                encoding="utf-8",
            )
            (sprint_2_dir / "S2-009_demo.yaml").write_text(
                "task_id: S2-009\nstory_id: S2-009\ntask_name: Fermenting Feed\nstory_inputs:\n  - feed input\nstory_process:\n  - build feed\nstory_outputs:\n  - feed output\nverification_basis:\n  - verify feed\nacceptance_criteria:\n  - feed exists\n",
                encoding="utf-8",
            )
            (sprint_2a_dir / "S2A-001_demo.yaml").write_text(
                "task_id: S2A-001\nstory_id: S2A-001\ntask_name: Source Scout\nsprint: Sprint 2A\nstory_inputs:\n  - raw docs\nstory_process:\n  - scout sources\nstory_outputs:\n  - scout output\nverification_basis:\n  - verify scout\nacceptance_criteria:\n  - scout exists\n",
                encoding="utf-8",
            )
            (sprint_2a_dir / "S2A-006_demo.yaml").write_text(
                "task_id: S2A-006\nstory_id: S2A-006\ntask_name: Fermentation Monitor\nsprint: Sprint 2A\nstory_inputs:\n  - theme candidates\nstory_process:\n  - monitor fermentation\nstory_outputs:\n  - monitor output\nverification_basis:\n  - verify monitor\nacceptance_criteria:\n  - monitor exists\n",
                encoding="utf-8",
            )
            run_dir = runtime_dir / "run-demo"
            run_dir.mkdir(parents=True)
            (run_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-demo",
                        "trace_id": "trace-demo",
                        "created_at": "2026-03-16T10:00:00+00:00",
                        "updated_at": "2026-03-16T10:05:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "result_warehouse_summary.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-demo",
                        "artifact_batch_dir": str(run_dir),
                        "saved_artifacts": [
                            {"filename": "raw_documents.json", "artifact_ref": "artifact://raw", "record_count": 2},
                            {"filename": "structured_result_cards.json", "artifact_ref": "artifact://cards", "record_count": 1},
                        ],
                        "manifest_ref": "artifact://manifest",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "raw_documents.json").write_text(json.dumps([{"id": 1}, {"id": 2}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "source_scout_candidates.json").write_text(json.dumps([{"id": "scout-1"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "normalized_documents.json").write_text(json.dumps([{"id": 1}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "canonical_events.json").write_text(json.dumps([{"event_id": "evt-1"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "theme_clusters.json").write_text(json.dumps([{"cluster_id": "cluster-1"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "theme_candidate_mappings.json").write_text(json.dumps([{"cluster_id": "cluster-1", "candidates": []}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "theme_purity_candidates.json").write_text(json.dumps([{"cluster_id": "cluster-1", "judge_status": "accepted"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "theme_candidates.json").write_text(json.dumps([{"theme_name": "AI"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "fermentation_monitor.json").write_text(json.dumps([{"theme_name": "AI", "fermentation_phase": "spreading"}], ensure_ascii=False), encoding="utf-8")
            (run_dir / "structured_result_cards.json").write_text(
                json.dumps([{"card_id": "card-1", "theme_name": "AI"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (run_dir / "theme_heat_snapshots.json").write_text(
                json.dumps([{"theme_name": "AI", "theme_heat_score": 42}], ensure_ascii=False),
                encoding="utf-8",
            )
            (run_dir / "fermenting_theme_feed.json").write_text(
                json.dumps([{"theme_name": "AI", "fermentation_stage": "emerging"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (run_dir / "daily_review.json").write_text(
                json.dumps(
                    {
                        "today_focus_page": [{"theme_name": "AI"}],
                        "watchlist_event_page": [{"theme_name": "AI"}],
                        "daily_review_report": {"summary": ["AI"]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            finahunt_registry = base / "finahunt_story_status_registry.json"
            finahunt_registry.write_text(
                json.dumps(
                    {
                        "stories": [
                            {
                                "story_id": "S2-006",
                                "status": "done",
                                "project": "finahunt",
                                "validation_summary": "structured cards validated",
                            },
                            {
                                "story_id": "S2-009",
                                "status": "done",
                                "project": "finahunt",
                                "validation_summary": "feed validated",
                            },
                            {
                                "story_id": "S2A-001",
                                "status": "done",
                                "project": "finahunt",
                                "validation_summary": "source scout validated",
                            },
                            {
                                "story_id": "S2A-006",
                                "status": "done",
                                "project": "finahunt",
                                "validation_summary": "fermentation monitor validated",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review_registry = base / "finahunt_story_acceptance_reviews.json"
            review_registry.write_text(
                json.dumps(
                    {
                        "reviews": [
                            {
                                "project": "finahunt",
                                "backlog_id": "backlog_v1",
                                "sprint_id": "sprint_2a_early_theme_discovery_engine",
                                "story_id": "S2A-006",
                                "reviewer": "QA",
                                "verdict": "approved",
                                "summary": "formal acceptance passed",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "FINAHUNT_RUNTIME_DIR", runtime_dir),
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_registry),
                patch.object(dashboard_main, "FINAHUNT_STORY_ACCEPTANCE_REVIEW_REGISTRY", review_registry),
            ):
                showcase = dashboard_main.load_finahunt_runtime_showcase()

            self.assertEqual(showcase["run_id"], "run-demo")
            self.assertEqual(showcase["stats"]["raw_document_count"], 2)
            self.assertEqual(showcase["stats"]["structured_result_card_count"], 1)
            self.assertEqual(showcase["pipeline"][0]["label"], "资讯源运行时")
            self.assertEqual(showcase["pipeline"][0]["count"], 2)
            story_ids = [item["story_id"] for item in showcase["stories"]]
            self.assertIn("S2-006", story_ids)
            self.assertIn("S2A-001", story_ids)
            self.assertIn("S2A-006", story_ids)
            story_by_id = {item["story_id"]: item for item in showcase["stories"]}
            self.assertTrue(story_by_id["S2-006"]["output_ready"])
            self.assertTrue(story_by_id["S2A-001"]["output_ready"])
            self.assertEqual(story_by_id["S2A-006"]["human_review"]["verdict"], "approved")
            self.assertEqual(showcase["fermenting_theme_feed"][0]["theme_name"], "AI")

    def test_load_finahunt_runtime_showcase_handles_empty_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runtime_dir = base / "runtime"
            finahunt_registry = base / "finahunt_story_status_registry.json"
            finahunt_registry.write_text(json.dumps({"stories": []}, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(dashboard_main, "FINAHUNT_RUNTIME_DIR", runtime_dir),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_registry),
            ):
                showcase = dashboard_main.load_finahunt_runtime_showcase()

            self.assertIsNone(showcase["run_id"])
            self.assertEqual(showcase["stats"]["structured_result_card_count"], 0)
            self.assertGreaterEqual(len(showcase["stories"]), 15)

    def test_generic_runtime_showcase_uses_project_registration(self) -> None:
        with patch.object(dashboard_main, "load_finahunt_runtime_showcase", return_value={"run_id": "run-demo"}) as loader:
            showcase = dashboard_main.load_runtime_showcase("finahunt", run_id="run-demo")

        self.assertEqual(showcase["run_id"], "run-demo")
        loader.assert_called_once_with(run_id="run-demo")

    def test_load_projects_exposes_runtime_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            versefina_tasks = base / "versefina_tasks"
            finahunt_tasks = base / "finahunt_tasks"
            agenthire_tasks = base / "agenthire_tasks"
            for tasks_root in [versefina_tasks, finahunt_tasks, agenthire_tasks]:
                backlog_dir = tasks_root / "backlog_v1"
                backlog_dir.mkdir(parents=True)
                (backlog_dir / "sprint_overview.md").write_text("# Backlog", encoding="utf-8")
                (tasks_root / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")

            with (
                patch.object(dashboard_main, "TASKS_DIR", versefina_tasks),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", versefina_tasks / "story_status_registry.json"),
                patch.object(dashboard_main, "FINAHUNT_TASKS_DIR", finahunt_tasks),
                patch.object(dashboard_main, "FINAHUNT_STORY_STATUS_REGISTRY", finahunt_tasks / "story_status_registry.json"),
                patch.object(dashboard_main, "AGENTHIRE_TASKS_DIR", agenthire_tasks),
                patch.object(dashboard_main, "AGENTHIRE_STORY_STATUS_REGISTRY", agenthire_tasks / "story_status_registry.json"),
            ):
                projects = dashboard_main.load_projects()

            project_index = {item["id"]: item for item in projects}
            self.assertTrue(project_index["versefina"]["has_runtime"])
            self.assertEqual(project_index["versefina"]["runtime_dashboard_path"], "/projects/versefina/runtime")
            self.assertTrue(project_index["finahunt"]["has_runtime"])
            self.assertEqual(project_index["finahunt"]["runtime_dashboard_path"], "/projects/finahunt/runtime")
            self.assertFalse(project_index["agentHire"]["has_runtime"])
            self.assertIsNone(project_index["agentHire"]["runtime_dashboard_path"])

    def test_load_versefina_runtime_showcase_reads_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runtime_dir = base / "versefina_runtime"
            registry_path = tasks_dir / "story_status_registry.json"
            review_path = tasks_dir / "story_acceptance_reviews.json"

            sprint_1_dir = tasks_dir / "backlog_v1" / "sprint_1_statement_to_agent" / "epic_demo"
            sprint_2_dir = tasks_dir / "backlog_v1" / "sprint_2_world_ledger_loop" / "epic_demo"
            sprint_1_dir.mkdir(parents=True)
            sprint_2_dir.mkdir(parents=True)

            for path, story_id, task_name in [
                (sprint_1_dir / "S1-001_demo.yaml", "S1-001", "Upload"),
                (sprint_1_dir / "S1-010_demo.yaml", "S1-010", "Create Agent"),
                (sprint_2_dir / "S2-001_demo.yaml", "S2-001", "Calendar Sync"),
                (sprint_2_dir / "S2-005_demo.yaml", "S2-005", "Action Validation"),
            ]:
                path.write_text(
                    "\n".join(
                        [
                            f"task_id: {story_id}",
                            f"story_id: {story_id}",
                            f"task_name: {task_name}",
                            "story_inputs:",
                            "  - input",
                            "story_process:",
                            "  - process",
                            "story_outputs:",
                            "  - output",
                            "verification_basis:",
                            "  - verify",
                            "acceptance_criteria:",
                            "  - criteria",
                        ]
                    ),
                    encoding="utf-8",
                )

            registry_path.write_text(
                json.dumps(
                    {
                        "stories": [
                            {"story_id": "S1-010", "status": "done", "summary": "agent created", "evidence": ["agent persisted"]},
                            {"story_id": "S2-001", "status": "done", "summary": "calendar synced", "evidence": ["calendar cached"]},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            review_path.write_text(
                json.dumps(
                    {
                        "reviews": [
                            {
                                "backlog_id": "backlog_v1",
                                "sprint_id": "sprint_1_statement_to_agent",
                                "story_id": "S1-010",
                                "verdict": "approved",
                                "summary": "人工确认通过",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            for directory in ["statement_meta", "statement_parse_reports", "trade_records", "agent_profiles", "agents", "market_world"]:
                (runtime_dir / directory).mkdir(parents=True)
            (runtime_dir / "statement_meta" / "stmt-demo.json").write_text(
                json.dumps(
                    {
                        "statement_id": "stmt-demo",
                        "owner_id": "demo-user",
                        "market": "CN_A",
                        "file_name": "demo.csv",
                        "content_type": "text/csv",
                        "byte_size": 128,
                        "object_key": "statements/demo/stmt-demo/demo.csv",
                        "upload_status": "parsed",
                        "detected_file_type": "csv",
                        "parser_key": "statement_csv_parser",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (runtime_dir / "statement_parse_reports" / "stmt-demo.json").write_text(
                json.dumps(
                    {"statement_id": "stmt-demo", "broker": "demo_broker", "parsed_records": 2, "failed_records": 0, "parser_key": "statement_csv_parser"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (runtime_dir / "trade_records" / "stmt-demo.json").write_text(
                json.dumps([{"symbol": "600519.SH", "side": "buy", "qty": 100}], ensure_ascii=False),
                encoding="utf-8",
            )
            (runtime_dir / "agent_profiles" / "stmt-demo.json").write_text(
                json.dumps(
                    {"statement_id": "stmt-demo", "styleTags": ["trend"], "riskControls": {"maxPositionPct": 0.3}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (runtime_dir / "agents" / "agt_stmt-demo.json").write_text(
                json.dumps(
                    {"agent_id": "agt_stmt-demo", "statement_id": "stmt-demo", "world_id": "cn-a", "init_cash": 100000, "profile_path": "profile.json"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (runtime_dir / "market_world" / "cn-a.calendar.json").write_text(
                json.dumps(
                    {
                        "world_id": "cn-a",
                        "market": "CN_A",
                        "start_date": "2026-03-13",
                        "end_date": "2026-03-18",
                        "trading_days": ["2026-03-13", "2026-03-16", "2026-03-17"],
                        "closed_days": ["2026-03-14", "2026-03-15"],
                        "source": "fallback_cn_calendar",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", registry_path),
                patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", review_path),
                patch.object(dashboard_main, "VERSEFINA_RUNTIME_DIR", runtime_dir),
            ):
                showcase = dashboard_main.load_versefina_runtime_showcase()

            self.assertEqual(showcase["stats"]["statement_count"], 1)
            self.assertEqual(showcase["stats"]["trade_record_count"], 1)
            self.assertEqual(len(showcase["story_groups"]), 2)
            sprint_1_story = next(item for item in showcase["story_groups"][0]["stories"] if item["story_id"] == "S1-010")
            sprint_2_story = next(item for item in showcase["story_groups"][1]["stories"] if item["story_id"] == "S2-005")
            self.assertEqual(sprint_1_story["evidence_status"], "real")
            self.assertEqual((sprint_1_story["human_review"] or {}).get("verdict"), "approved")
            self.assertEqual(sprint_2_story["evidence_status"], "placeholder")

    def test_load_versefina_runtime_showcase_handles_empty_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runtime_dir = base / "versefina_runtime"
            registry_path = tasks_dir / "story_status_registry.json"
            review_path = tasks_dir / "story_acceptance_reviews.json"
            sprint_dir = tasks_dir / "backlog_v1" / "sprint_1_statement_to_agent" / "epic_demo"
            sprint_dir.mkdir(parents=True)
            (sprint_dir / "S1-001_demo.yaml").write_text(
                "task_id: S1-001\nstory_id: S1-001\ntask_name: Upload\nstory_inputs:\n  - input\n",
                encoding="utf-8",
            )
            registry_path.write_text(json.dumps({"stories": []}, ensure_ascii=False), encoding="utf-8")
            review_path.write_text(json.dumps({"reviews": []}, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", registry_path),
                patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", review_path),
                patch.object(dashboard_main, "VERSEFINA_RUNTIME_DIR", runtime_dir),
            ):
                showcase = dashboard_main.load_versefina_runtime_showcase()

            self.assertEqual(showcase["stats"]["statement_count"], 0)
            self.assertEqual(showcase["stats"]["real_evidence_story_count"], 0)
            self.assertEqual(showcase["story_groups"][0]["stories"][0]["evidence_status"], "missing")


if __name__ == "__main__":
    unittest.main()
