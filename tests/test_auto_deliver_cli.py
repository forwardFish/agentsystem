from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cli as cli_module
import click
import yaml
from click.testing import CliRunner

from cli import cli


class AutoDeliverCliTestCase(unittest.TestCase):
    def _write_story_card(self, sprint_dir: Path, story_id: str) -> Path:
        epic_dir = sprint_dir / "epic_demo"
        epic_dir.mkdir(parents=True, exist_ok=True)
        story_path = epic_dir / f"{story_id}_demo.yaml"
        story_path.write_text(
            yaml.safe_dump(
                {
                    "task_id": story_id,
                    "story_id": story_id,
                    "blast_radius": "L1",
                    "goal": f"Implement {story_id}",
                    "acceptance_criteria": ["done"],
                    "related_files": ["apps/api/src/demo.py"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return story_path

    def _write_story_card_with_dependencies(self, sprint_dir: Path, story_id: str, dependencies: list[str]) -> Path:
        epic_dir = sprint_dir / "epic_demo"
        epic_dir.mkdir(parents=True, exist_ok=True)
        story_path = epic_dir / f"{story_id}_demo.yaml"
        story_path.write_text(
            yaml.safe_dump(
                {
                    "task_id": story_id,
                    "story_id": story_id,
                    "blast_radius": "L1",
                    "goal": f"Implement {story_id}",
                    "acceptance_criteria": ["done"],
                    "related_files": ["apps/api/src/demo.py"],
                    "dependencies": dependencies,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return story_path

    def _write_success_audit(self, runs_dir: Path, *, project: str, backlog_id: str, sprint_id: str, story_id: str, task_id: str) -> None:
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / f"prod_audit_{task_id}.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "project": project,
                    "branch": f"agent/l1-{task_id}",
                    "commit": f"commit-{story_id.lower()}",
                    "success": True,
                    "created_at": "2026-03-19T09:00:00",
                    "result": {
                        "task_payload": {
                            "project": project,
                            "task_id": story_id,
                            "story_id": story_id,
                            "backlog_id": backlog_id,
                            "sprint_id": sprint_id,
                            "blast_radius": "L1",
                            "goal": f"Implement {story_id}",
                            "acceptance_criteria": ["done"],
                            "related_files": ["apps/api/src/demo.py"],
                        },
                        "required_modes": ["review", "qa-only", "qa"],
                        "executed_modes": ["review", "qa"],
                        "advisory_modes": [],
                        "mode_execution_order": ["review", "qa"],
                        "last_node": "doc_writer",
                        "current_step": "doc_done",
                        "test_results": "PASS",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _pre_hook_payload(self, base: Path) -> dict[str, str]:
        paths = {
            "advice_path": str(base / "advice.json"),
            "office_hours_path": str(base / "office_hours.md"),
            "plan_ceo_review_path": str(base / "plan_ceo_review.md"),
            "sprint_framing_path": str(base / "sprint_framing.json"),
            "parity_manifest_path": str(base / "gstack_parity_manifest.json"),
            "acceptance_checklist_path": str(base / "gstack_acceptance_checklist.md"),
        }
        for path in paths.values():
            Path(path).write_text("artifact\n", encoding="utf-8")
        return paths

    def _post_hook_payload(self, base: Path) -> dict[str, str | None]:
        paths = {
            "document_release_path": str(base / "document_release.md"),
            "retro_path": str(base / "retro.md"),
            "ship_advice_path": None,
            "ship_report_path": str(base / "ship_report.md"),
            "sprint_close_bundle_path": str(base / "sprint_close_bundle.json"),
            "runtime_validation_path": None,
        }
        for key, path in paths.items():
            if path and key != "sprint_close_bundle_path":
                Path(path).write_text("artifact\n", encoding="utf-8")
        Path(str(paths["sprint_close_bundle_path"])).write_text("{}", encoding="utf-8")
        return paths

    def _write_gap_closure_story(self, sprint_dir: Path, story_id: str) -> Path:
        epic_dir = sprint_dir / "epic_demo"
        epic_dir.mkdir(parents=True, exist_ok=True)
        (sprint_dir / "sprint_plan.md").write_text("# sprint\n", encoding="utf-8")
        (sprint_dir / "execution_order.txt").write_text(f"{story_id}\n", encoding="utf-8")
        story_path = epic_dir / f"{story_id}_demo.yaml"
        story_path.write_text(
            yaml.safe_dump(
                {
                    "task_id": story_id,
                    "story_id": story_id,
                    "blast_radius": "L1",
                    "goal": f"Implement {story_id}",
                    "acceptance_criteria": ["done"],
                    "related_files": ["apps/api/src/demo.py"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return story_path

    def _write_gap_closure_docs(self, repo_path: Path, *, sprint_id: str, story_id: str) -> None:
        (repo_path / "docs" / "handoff").mkdir(parents=True, exist_ok=True)
        (repo_path / "docs" / "bootstrap").mkdir(parents=True, exist_ok=True)
        requirement_dir = repo_path / "docs" / "需求文档" / "需求分析_1.6_最终版_事件参与者优先"
        requirement_dir.mkdir(parents=True, exist_ok=True)
        (requirement_dir / "需求分析_1.6_最终版_事件参与者优先.md").write_text("# requirement\n", encoding="utf-8")
        (repo_path / "docs" / "bootstrap" / "roadmap_1_7_execution_playbook.md").write_text("# playbook\n", encoding="utf-8")
        (repo_path / "NOW.md").write_text("# NOW\n", encoding="utf-8")
        (repo_path / "STATE.md").write_text("# STATE\n", encoding="utf-8")
        (repo_path / "DECISIONS.md").write_text("# DECISIONS\n", encoding="utf-8")
        (repo_path / "docs" / "handoff" / "current_handoff.md").write_text(
            "\n".join(
                [
                    "# Current Handoff",
                    "",
                    "- Project: versefina",
                    "- Backlog: roadmap_1_6",
                    f"- Sprint: {sprint_id}",
                    f"- Story: {story_id}",
                    f"- Resume from story: {story_id}",
                    "- Status: interrupted",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_gap_closure_manifest(self, workspace_root: Path, *, sprint_id: str, story_id: str) -> None:
        continuity_root = workspace_root / ".meta" / "versefina" / "continuity"
        continuity_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "project": "versefina",
            "trigger": "fresh_start",
            "docs": {
                "now": {
                    "sprint_id": sprint_id,
                    "story_id": story_id,
                    "status": "ready",
                }
            },
        }
        (continuity_root / "continuity_manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_auto_deliver_without_auto_run_only_generates_backlog(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            repo_path.mkdir()
            requirement_file = base / "requirement.md"
            requirement_file.write_text("# demo requirement\n", encoding="utf-8")

            with (
                patch("cli._load_env_config", return_value={"repo": {"demo": str(repo_path)}}),
                patch(
                    "cli.split_requirement_file",
                    return_value={
                        "backlog_root": str(repo_path / "tasks" / "backlog_demo"),
                        "overview_path": str(repo_path / "tasks" / "backlog_demo" / "sprint_overview.md"),
                        "sprint_dirs": [],
                        "story_cards": [{}, {}],
                    },
                ) as split_mock,
                patch("cli.run_prod_task") as run_prod_task_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "auto-deliver",
                        "--requirement-file",
                        str(requirement_file),
                        "--project",
                        "demo",
                        "--env",
                        "test",
                        "--prefix",
                        "backlog_demo",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Auto-run is off", result.output)
            split_mock.assert_called_once()
            run_prod_task_mock.assert_not_called()

    def test_auto_deliver_with_auto_run_executes_all_sprints(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            repo_path.mkdir()
            tasks_root = repo_path / "tasks"
            sprint_1 = tasks_root / "backlog_demo" / "sprint_1_alpha"
            sprint_2 = tasks_root / "backlog_demo" / "sprint_2_beta"
            for sprint_dir, story_id in ((sprint_1, "S1-001"), (sprint_2, "S2-001")):
                epic_dir = sprint_dir / "epic_demo"
                epic_dir.mkdir(parents=True)
                (sprint_dir / "execution_order.txt").write_text(f"{story_id}\n", encoding="utf-8")
                (epic_dir / f"{story_id}_demo.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "task_id": story_id,
                            "story_id": story_id,
                            "blast_radius": "L1",
                            "goal": "demo",
                            "acceptance_criteria": ["done"],
                            "related_files": ["apps/api/src/demo.py"],
                        },
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )

            with (
                patch("cli._load_env_config", return_value={"repo": {"demo": str(repo_path)}}),
                patch(
                    "cli.analyze_requirement",
                    return_value={
                        "backlog_root": str(tasks_root / "backlog_demo"),
                        "overview_path": str(tasks_root / "backlog_demo" / "sprint_overview.md"),
                        "sprint_dirs": [str(sprint_1), str(sprint_2)],
                        "story_cards": [{}, {}],
                    },
                ) as analyze_mock,
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch(
                    "cli.run_sprint_post_hooks",
                    return_value=self._post_hook_payload(base),
                ),
                patch(
                    "cli.run_prod_task",
                    side_effect=[
                        {"success": True, "task_id": "task-1", "branch": "agent/l1-task-1", "commit": "abc"},
                        {"success": True, "task_id": "task-2", "branch": "agent/l1-task-2", "commit": "def"},
                    ],
                ) as run_prod_task_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "auto-deliver",
                        "--requirement",
                        "demo requirement",
                        "--project",
                        "demo",
                        "--env",
                        "test",
                        "--prefix",
                        "backlog_demo",
                        "--auto-run",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Completed stories: 2", result.output)
            analyze_mock.assert_called_once()
            self.assertEqual(run_prod_task_mock.call_count, 2)

    def test_plan_ceo_review_interactive_only_generates_requirement_package(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            (repo_path / "docs").mkdir(parents=True)

            with patch("cli._load_env_config", return_value={"repo": {"demo": str(repo_path)}}):
                result = runner.invoke(
                    cli,
                    [
                        "plan-ceo-review",
                        "--requirement",
                        "Build a new runtime intelligence dashboard for analysts.",
                        "--project",
                        "demo",
                        "--delivery-mode",
                        "interactive",
                        "--env",
                        "test",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Delivery mode is interactive", result.output)
            requirements_dir = repo_path / "docs" / "requirements"
            generated_files = list(requirements_dir.glob("*.md"))
            self.assertEqual(len(generated_files), 1)
            generated_text = generated_files[0].read_text(encoding="utf-8")
            self.assertIn("Build a new runtime intelligence dashboard for analysts.", generated_text)

    def test_plan_ceo_review_auto_mode_hands_off_to_auto_delivery(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            (repo_path / "docs").mkdir(parents=True)

            with (
                patch("cli._load_env_config", return_value={"repo": {"demo": str(repo_path)}}),
                patch(
                    "cli._build_backlog_from_requirement",
                    return_value=(
                        {
                            "backlog_root": str(repo_path / "tasks" / "backlog_demo"),
                            "overview_path": str(repo_path / "tasks" / "backlog_demo" / "sprint_overview.md"),
                            "sprint_dirs": [],
                            "story_cards": [{}],
                        },
                        repo_path,
                        repo_path / "tasks",
                    ),
                ) as build_backlog_mock,
                patch("cli._execute_auto_delivery") as execute_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "plan-ceo-review",
                        "--requirement",
                        "Ship the new project bootstrap flow.",
                        "--project",
                        "demo",
                        "--delivery-mode",
                        "auto",
                        "--env",
                        "test",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("starting auto delivery", result.output.lower())
            build_backlog_mock.assert_called_once()
            execute_mock.assert_called_once()
            _, kwargs = build_backlog_mock.call_args
            self.assertIsNone(kwargs["requirement"])
            self.assertTrue(str(kwargs["requirement_file"]).endswith(".md"))

    def test_auto_deliver_uses_agenthire_default_requirement_file_when_missing(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "agentHire"
            requirement_dir = repo_path / "docs" / "requirements"
            requirement_dir.mkdir(parents=True)
            requirement_file = requirement_dir / "20260318_agent_marketplace_mvp_v0_1_phase_1_execution_requirement_v0_3.md"
            requirement_file.write_text("# agentHire requirement\n", encoding="utf-8")

            with (
                patch("cli._load_env_config", return_value={"repo": {"agentHire": str(repo_path)}}),
                patch(
                    "cli.split_requirement_file",
                    return_value={
                        "backlog_root": str(repo_path / "tasks" / "backlog_demo"),
                        "overview_path": str(repo_path / "tasks" / "backlog_demo" / "sprint_overview.md"),
                        "sprint_dirs": [],
                        "story_cards": [{}],
                    },
                ) as split_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "auto-deliver",
                        "--project",
                        "agentHire",
                        "--env",
                        "test",
                        "--prefix",
                        "backlog_demo",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            split_mock.assert_called_once()
            args = split_mock.call_args.args
            self.assertTrue(str(args[2]).endswith("20260318_agent_marketplace_mvp_v0_1_phase_1_execution_requirement_v0_3.md"))

    def test_execute_auto_delivery_reconciles_success_audits_and_resumes_from_earliest_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            tasks_root = repo_path / "tasks"
            backlog_root = tasks_root / "backlog_demo"
            sprint_0 = backlog_root / "sprint_0_alpha"
            sprint_1 = backlog_root / "sprint_1_beta"
            sprint_0.mkdir(parents=True)
            sprint_1.mkdir(parents=True)
            (backlog_root / "sprint_overview.md").write_text("# Demo Backlog", encoding="utf-8")
            (sprint_0 / "execution_order.txt").write_text("S0-001\n", encoding="utf-8")
            (sprint_1 / "execution_order.txt").write_text("S1-001\nS1-002\n", encoding="utf-8")
            self._write_story_card(sprint_0, "S0-001")
            story_s1_001 = self._write_story_card(sprint_1, "S1-001")
            self._write_story_card(sprint_1, "S1-002")

            runs_dir = base / "runs"
            self._write_success_audit(runs_dir, project="demo", backlog_id="backlog_demo", sprint_id="sprint_0_alpha", story_id="S0-001", task_id="task-s0-001")
            self._write_success_audit(runs_dir, project="demo", backlog_id="backlog_demo", sprint_id="sprint_1_beta", story_id="S1-002", task_id="task-s1-002")
            (repo_path / "tasks" / "runtime").mkdir(parents=True, exist_ok=True)
            (repo_path / "tasks" / "runtime" / "auto_resume_state.json").write_text(
                json.dumps(
                    {
                        "status": "interrupted",
                        "backlog_root": str(backlog_root),
                        "sprint_id": "sprint_1_beta",
                        "story_id": "S1-002",
                        "resume_from_story": "S1-002",
                        "interruption_reason": "stale_resume_pointer",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            backlog_result = {
                "backlog_root": str(backlog_root),
                "overview_path": str(backlog_root / "sprint_overview.md"),
                "sprint_dirs": [str(sprint_0), str(sprint_1)],
                "story_cards": ["S0-001", "S1-001", "S1-002"],
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch(
                    "cli.run_sprint_post_hooks",
                    return_value=self._post_hook_payload(base),
                ),
                patch(
                    "cli.run_prod_task",
                    return_value={"success": True, "task_id": "task-s1-001", "branch": "agent/l1-task-s1-001", "commit": "commit-s1-001"},
                ) as run_prod_task_mock,
            ):
                summary_path = cli_module._execute_auto_delivery(
                    backlog_result=backlog_result,
                    repo_b_path=repo_path,
                    tasks_root=tasks_root,
                    env="test",
                    project="demo",
                    release=False,
                    echo=lambda _message: None,
                )

            self.assertTrue(summary_path.exists())
            self.assertEqual(run_prod_task_mock.call_count, 1)
            self.assertEqual(Path(run_prod_task_mock.call_args.args[0]).resolve(), story_s1_001.resolve())
            status_registry = json.loads((repo_path / "tasks" / "story_status_registry.json").read_text(encoding="utf-8"))
            story_ids = {entry["story_id"] for entry in status_registry["stories"]}
            self.assertIn("S0-001", story_ids)
            self.assertIn("S1-002", story_ids)
            review_registry = json.loads((repo_path / "tasks" / "story_acceptance_reviews.json").read_text(encoding="utf-8"))
            review_story_ids = {entry["story_id"] for entry in review_registry["reviews"]}
            self.assertIn("S0-001", review_story_ids)
            self.assertIn("S1-002", review_story_ids)
            self.assertTrue((repo_path / "tasks" / "runtime" / "story_handoffs" / "S0-001.md").exists())
            self.assertTrue((repo_path / "tasks" / "runtime" / "story_handoffs" / "S1-002.md").exists())

    def test_execute_auto_delivery_continues_after_story_local_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            tasks_root = repo_path / "tasks"
            backlog_root = tasks_root / "backlog_demo"
            sprint_1 = backlog_root / "sprint_1_beta"
            sprint_1.mkdir(parents=True)
            (backlog_root / "sprint_overview.md").write_text("# Demo Backlog", encoding="utf-8")
            (sprint_1 / "execution_order.txt").write_text("S1-001\nS1-002\n", encoding="utf-8")
            self._write_story_card(sprint_1, "S1-001")
            self._write_story_card(sprint_1, "S1-002")

            backlog_result = {
                "backlog_root": str(backlog_root),
                "overview_path": str(backlog_root / "sprint_overview.md"),
                "sprint_dirs": [str(sprint_1)],
                "story_cards": ["S1-001", "S1-002"],
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch(
                    "cli.run_sprint_post_hooks",
                    return_value=self._post_hook_payload(base),
                ),
                patch(
                    "cli.run_prod_task",
                    side_effect=[
                        {
                            "success": False,
                            "task_id": "task-s1-001",
                            "error": "workflow_failed",
                            "state": {"last_node": "reviewer", "interruption_reason": "workflow_failed", "blocker_class": "story_local_blocker"},
                        },
                        {"success": True, "task_id": "task-s1-002", "branch": "agent/l1-task-s1-002", "commit": "def"},
                    ],
                ) as run_prod_task_mock,
            ):
                summary_path = cli_module._execute_auto_delivery(
                    backlog_result=backlog_result,
                    repo_b_path=repo_path,
                    tasks_root=tasks_root,
                    env="test",
                    project="demo",
                    release=False,
                    echo=lambda _message: None,
                )

            self.assertTrue(summary_path.exists())
            self.assertEqual(run_prod_task_mock.call_count, 2)
            resume_state = json.loads((repo_path / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_state["status"], "completed")
            self.assertEqual(resume_state["run_policy"], "single_pass_to_completion")
            self.assertEqual(resume_state["acceptance_policy"], "must_pass_all_required_runs")
            self.assertEqual(resume_state["retry_policy"], "auto_repair_until_green")
            self.assertTrue(resume_state["final_green_required"])
            failure_snapshot = json.loads((repo_path / "tasks" / "runtime" / "story_failures" / "S1-001.json").read_text(encoding="utf-8"))
            self.assertEqual(failure_snapshot["blocker_class"], "story_local_blocker")

    def test_execute_auto_delivery_stops_after_shared_dependency_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            tasks_root = repo_path / "tasks"
            backlog_root = tasks_root / "backlog_demo"
            sprint_1 = backlog_root / "sprint_1_beta"
            sprint_1.mkdir(parents=True)
            (backlog_root / "sprint_overview.md").write_text("# Demo Backlog", encoding="utf-8")
            (sprint_1 / "execution_order.txt").write_text("S1-001\nS1-002\n", encoding="utf-8")
            self._write_story_card(sprint_1, "S1-001")
            self._write_story_card(sprint_1, "S1-002")

            backlog_result = {
                "backlog_root": str(backlog_root),
                "overview_path": str(backlog_root / "sprint_overview.md"),
                "sprint_dirs": [str(sprint_1)],
                "story_cards": ["S1-001", "S1-002"],
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch(
                    "cli.run_sprint_post_hooks",
                    return_value=self._post_hook_payload(base),
                ),
                patch(
                    "cli.run_prod_task",
                    return_value={
                        "success": False,
                        "task_id": "task-s1-001",
                        "error": "workflow_failed",
                        "state": {"last_node": "reviewer", "interruption_reason": "workflow_failed", "blocker_class": "shared_dependency_blocker"},
                    },
                ) as run_prod_task_mock,
            ):
                with self.assertRaises(click.ClickException):
                    cli_module._execute_auto_delivery(
                        backlog_result=backlog_result,
                        repo_b_path=repo_path,
                        tasks_root=tasks_root,
                        env="test",
                        project="demo",
                        release=False,
                        echo=lambda _message: None,
                    )

            self.assertEqual(run_prod_task_mock.call_count, 1)
            resume_state = json.loads((repo_path / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_state["status"], "interrupted")
            self.assertEqual(resume_state["story_id"], "S1-001")
            self.assertEqual(resume_state["blocker_class"], "shared_dependency_blocker")
            self.assertEqual(resume_state["acceptance_failure_class"], "shared_dependency_blocker")

    def test_execute_auto_delivery_escalates_failed_story_when_downstream_depends_on_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "demo_repo"
            tasks_root = repo_path / "tasks"
            backlog_root = tasks_root / "backlog_demo"
            sprint_1 = backlog_root / "sprint_1_beta"
            sprint_1.mkdir(parents=True)
            (backlog_root / "sprint_overview.md").write_text("# Demo Backlog", encoding="utf-8")
            (sprint_1 / "execution_order.txt").write_text("S1-001\nS1-002\n", encoding="utf-8")
            self._write_story_card(sprint_1, "S1-001")
            self._write_story_card_with_dependencies(sprint_1, "S1-002", ["S1-001"])

            backlog_result = {
                "backlog_root": str(backlog_root),
                "overview_path": str(backlog_root / "sprint_overview.md"),
                "sprint_dirs": [str(sprint_1)],
                "story_cards": ["S1-001", "S1-002"],
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch(
                    "cli.run_sprint_post_hooks",
                    return_value=self._post_hook_payload(base),
                ),
                patch(
                    "cli.run_prod_task",
                    return_value={
                        "success": False,
                        "task_id": "task-s1-001",
                        "error": "workflow_failed",
                        "state": {"last_node": "reviewer", "interruption_reason": "workflow_failed", "blocker_class": "story_local_blocker"},
                    },
                ) as run_prod_task_mock,
            ):
                with self.assertRaises(click.ClickException):
                    cli_module._execute_auto_delivery(
                        backlog_result=backlog_result,
                        repo_b_path=repo_path,
                        tasks_root=tasks_root,
                        env="test",
                        project="demo",
                        release=False,
                        echo=lambda _message: None,
                    )

            self.assertEqual(run_prod_task_mock.call_count, 1)
            resume_state = json.loads((repo_path / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            self.assertEqual(resume_state["status"], "interrupted")
            self.assertEqual(resume_state["blocker_class"], "shared_dependency_blocker")
            self.assertEqual(resume_state["run_policy"], "single_pass_to_completion")

    def test_run_roadmap_executes_existing_roadmap_sprints_in_order(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_1 = tasks_root / "roadmap_1_6_sprint_1_alpha"
            sprint_2 = tasks_root / "roadmap_1_6_sprint_2_beta"
            for sprint_dir, story_id in ((sprint_1, "E1-001"), (sprint_2, "E2-001")):
                epic_dir = sprint_dir / "epic_demo"
                epic_dir.mkdir(parents=True)
                (sprint_dir / "sprint_plan.md").write_text("# sprint\n", encoding="utf-8")
                (sprint_dir / "execution_order.txt").write_text(f"{story_id}\n", encoding="utf-8")
                (epic_dir / f"{story_id}_demo.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "task_id": story_id,
                            "story_id": story_id,
                            "blast_radius": "L1",
                            "goal": f"Implement {story_id}",
                            "acceptance_criteria": ["done"],
                            "related_files": ["apps/api/src/demo.py"],
                        },
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )

            with (
                patch("cli._load_env_config", return_value={"repo": {"versefina": str(repo_path)}}),
                patch("cli.run_sprint_pre_hooks", return_value=self._pre_hook_payload(base)),
                patch("cli.run_sprint_post_hooks", return_value=self._post_hook_payload(base)),
                patch(
                    "cli.run_prod_task",
                    side_effect=[
                        {"success": True, "task_id": "task-e1", "branch": "agent/l1-task-e1", "commit": "commit-e1"},
                        {"success": True, "task_id": "task-e2", "branch": "agent/l1-task-e2", "commit": "commit-e2"},
                    ],
                ) as run_prod_task_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "run-roadmap",
                        "--project",
                        "versefina",
                        "--env",
                        "test",
                        "--tasks-root",
                        str(tasks_root),
                        "--roadmap-prefix",
                        "roadmap_1_6",
                    ],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Roadmap preflight report:", result.output)
            self.assertIn("Roadmap summary:", result.output)
            self.assertEqual(run_prod_task_mock.call_count, 2)
            first_task = run_prod_task_mock.call_args_list[0].args[0]
            second_task = run_prod_task_mock.call_args_list[1].args[0]
            self.assertIn("roadmap_1_6_sprint_1_alpha", str(first_task))
            self.assertIn("roadmap_1_6_sprint_2_beta", str(second_task))

    def test_execute_roadmap_resume_reuses_existing_phase_1_summary_without_reinvalidating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_1 = tasks_root / "roadmap_1_6_sprint_1_alpha"
            sprint_2 = tasks_root / "roadmap_1_6_sprint_2_beta"
            for sprint_dir, story_id in ((sprint_1, "E1-001"), (sprint_2, "E2-001")):
                epic_dir = sprint_dir / "epic_demo"
                epic_dir.mkdir(parents=True)
                (sprint_dir / "sprint_plan.md").write_text("# sprint\n", encoding="utf-8")
                (sprint_dir / "execution_order.txt").write_text(f"{story_id}\n", encoding="utf-8")
                (epic_dir / f"{story_id}_demo.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "task_id": story_id,
                            "story_id": story_id,
                            "blast_radius": "L1",
                            "goal": f"Implement {story_id}",
                            "acceptance_criteria": ["done"],
                            "related_files": ["apps/api/src/demo.py"],
                        },
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )

            (repo_path / "tasks" / "runtime").mkdir(parents=True, exist_ok=True)
            (repo_path / "docs" / "handoff").mkdir(parents=True, exist_ok=True)
            (repo_path / "NOW.md").write_text("# now\n", encoding="utf-8")
            (repo_path / "STATE.md").write_text("# state\n", encoding="utf-8")
            (repo_path / "DECISIONS.md").write_text("# decisions\n", encoding="utf-8")
            existing_summary_path = base / "runs" / "roadmaps" / "roadmap_1_6_20260325_140840.json"
            existing_summary_path.parent.mkdir(parents=True, exist_ok=True)
            existing_summary_path.write_text(
                json.dumps(
                    {
                        "project": "versefina",
                        "env": "test",
                        "repo_path": str(repo_path),
                        "tasks_root": str(tasks_root),
                        "roadmap_prefix": "roadmap_1_6",
                        "force_rerun": False,
                        "story_count": 2,
                        "release": False,
                        "status": "interrupted",
                        "started_at": "2026-03-25T14:08:40",
                        "execution_policy": "continuous_full_sprint",
                        "interaction_policy": "non_interactive_auto_run",
                        "pause_policy": "story_boundary_or_shared_blocker_only",
                        "run_policy": "single_pass_to_completion",
                        "acceptance_policy": "must_pass_all_required_runs",
                        "retry_policy": "auto_repair_until_green",
                        "acceptance_attempt": 0,
                        "acceptance_failure_class": None,
                        "repair_iteration": 0,
                        "final_green_required": True,
                        "sprint_count": 2,
                        "sprint_dirs": [str(sprint_1), str(sprint_2)],
                        "sprints": [
                            {
                                "sprint_dir": str(sprint_1),
                                "story_count": 1,
                                "completed_stories": [{"story_id": "E1-001", "task_id": "task-e1", "commit": "commit-e1"}],
                                "failed_stories": [],
                                "status": "completed",
                                "sprint_id": sprint_1.name,
                            }
                        ],
                        "current_sprint": sprint_2.name,
                        "current_story": "E2-001",
                        "current_node": "tester",
                        "last_success_story": "E1-001",
                        "resume_from_story": "E2-001",
                        "interruption_reason": "shared_dependency_blocker",
                        "error_message": "blocked",
                        "phase_1_cleanup": {
                            "backlog_id": "roadmap_1_6",
                            "cleaned_at": "2026-03-25T14:08:40",
                            "candidate_count": 41,
                            "deleted_files": ["apps/api/src/domain/event_ingestion/service.py"],
                            "repaired_files": [],
                            "blocked_files": [],
                            "syntax_checked_files": ["apps/api/src/domain/event_ingestion/service.py"],
                            "placeholder_rejections": [],
                            "invalidation": {
                                "backlog_id": "roadmap_1_6",
                                "invalidated_at": "2026-03-25T14:08:38",
                                "story_count": 70,
                                "review_count": 47,
                                "resume_sprint_id": sprint_1.name,
                                "resume_story_id": "E1-001",
                            },
                        },
                        "phase_2_gate_hardening": {"status": "implemented_in_repo", "completed_at": "2026-03-25T14:08:40"},
                        "phase_3_rerun": {"status": "running"},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (repo_path / "tasks" / "runtime" / "auto_resume_state.json").write_text(
                json.dumps(
                    {
                        "project": "versefina",
                        "backlog_id": "roadmap_1_6",
                        "roadmap_prefix": "roadmap_1_6",
                        "roadmap_summary_path": str(existing_summary_path),
                        "status": "interrupted",
                        "sprint_id": sprint_2.name,
                        "story_id": "E2-001",
                        "resume_from_story": "E2-001",
                        "last_success_story": "E1-001",
                        "interruption_reason": "shared_dependency_blocker",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            roadmap_result = {
                "roadmap_prefix": "roadmap_1_6",
                "tasks_root": str(tasks_root),
                "sprint_dirs": [str(sprint_1), str(sprint_2)],
                "story_cards": ["E1-001", "E2-001"],
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli.invalidate_roadmap_batch") as invalidate_mock,
                patch("cli.cleanup_invalid_batch") as cleanup_mock,
                patch(
                    "cli._run_sprint_directory",
                    return_value={
                        "sprint_dir": str(sprint_2),
                        "story_count": 1,
                        "completed_stories": [{"story_id": "E2-001", "task_id": "task-e2", "commit": "commit-e2"}],
                        "failed_stories": [],
                        "status": "completed",
                        "current_story": None,
                        "current_node": "doc_writer",
                        "last_success_story": "E2-001",
                        "resume_from_story": None,
                        "interruption_reason": None,
                        "error_message": None,
                        "sprint_id": sprint_2.name,
                    },
                ) as run_sprint_mock,
            ):
                summary_path = cli_module._execute_roadmap(
                    roadmap_result=roadmap_result,
                    repo_b_path=repo_path,
                    tasks_root=tasks_root,
                    env="test",
                    project="versefina",
                    release=False,
                    echo=lambda _message: None,
                )

            self.assertEqual(summary_path.resolve(), existing_summary_path.resolve())
            invalidate_mock.assert_not_called()
            cleanup_mock.assert_not_called()
            self.assertEqual(run_sprint_mock.call_count, 1)
            self.assertEqual(run_sprint_mock.call_args.args[0].resolve(), sprint_2.resolve())

            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["phase_1_cleanup"]["cleaned_at"], "2026-03-25T14:08:40")
            self.assertEqual(summary_payload["status"], "completed")
            sprint_ids = [item["sprint_id"] for item in summary_payload["sprints"]]
            self.assertEqual(sprint_ids, [sprint_1.name, sprint_2.name])

    def test_resolve_roadmap_resume_cursor_can_recover_from_story_level_running_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            sprint_1 = repo_path / "tasks" / "roadmap_1_6_sprint_1_alpha"
            sprint_2 = repo_path / "tasks" / "roadmap_1_6_sprint_2_beta"
            for sprint_dir, story_ids in ((sprint_1, ["E1-001", "E1-002"]), (sprint_2, ["E2-001", "E2-002"])):
                sprint_dir.mkdir(parents=True, exist_ok=True)
                (sprint_dir / "execution_order.txt").write_text("\n".join(story_ids) + "\n", encoding="utf-8")

            (repo_path / "tasks" / "runtime").mkdir(parents=True, exist_ok=True)
            (repo_path / "tasks" / "runtime" / "auto_resume_state.json").write_text(
                json.dumps(
                    {
                        "project": "versefina",
                        "backlog_id": "roadmap_1_6_sprint_2_beta",
                        "roadmap_prefix": "roadmap_1_6",
                        "roadmap_summary_path": str(base / "runs" / "roadmaps" / "roadmap_1_6_20260325_140840.json"),
                        "status": "running",
                        "sprint_id": "E2-001_story_level.yaml",
                        "story_id": "E2-001",
                        "resume_from_story": "E2-001",
                        "last_success_story": "E1-002",
                        "interruption_reason": "run_prod_task_exception",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            sprint_id, story_id, last_success_story, interruption_reason = cli_module._resolve_roadmap_resume_cursor(
                repo_path,
                roadmap_prefix="roadmap_1_6",
                sprint_dirs=[sprint_1.resolve(), sprint_2.resolve()],
                successful_story_index={},
            )

            self.assertEqual(sprint_id, sprint_2.name)
            self.assertEqual(story_id, "E2-001")
            self.assertEqual(last_success_story, "E1-002")
            self.assertEqual(interruption_reason, "run_prod_task_exception")

    def test_run_roadmap_preflight_fails_before_execution_when_story_card_is_missing(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_1 = tasks_root / "roadmap_1_6_sprint_1_alpha"
            sprint_1.mkdir(parents=True)
            (sprint_1 / "sprint_plan.md").write_text("# sprint\n", encoding="utf-8")
            (sprint_1 / "execution_order.txt").write_text("E1-001\n", encoding="utf-8")

            with (
                patch("cli._load_env_config", return_value={"repo": {"versefina": str(repo_path)}}),
                patch("cli.run_prod_task") as run_prod_task_mock,
            ):
                result = runner.invoke(
                    cli,
                    [
                        "run-roadmap",
                        "--project",
                        "versefina",
                        "--env",
                        "test",
                        "--tasks-root",
                        str(tasks_root),
                        "--roadmap-prefix",
                        "roadmap_1_6",
                        "--preflight-only",
                    ],
                )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Roadmap preflight failed", result.output)
            run_prod_task_mock.assert_not_called()

    def test_story_boundary_overrides_include_gstack_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "repo"
            story_dir = repo_path / "tasks" / "roadmap_1_6_sprint_1_alpha" / "epic_demo"
            story_dir.mkdir(parents=True)
            story_file = story_dir / "E1-001_demo.yaml"
            story_file.write_text(
                yaml.safe_dump(
                    {
                        "task_id": "E1-001",
                        "story_id": "E1-001",
                        "blast_radius": "L1",
                        "goal": "Implement roadmap story",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            with patch("cli._sync_and_assert_continuity", return_value={"trigger": "story_boundary"}) as continuity_mock:
                overrides = cli_module._story_boundary_overrides(
                    project="demo",
                    repo_b_path=repo_path,
                    story_file=story_file,
                    pre_hook=self._pre_hook_payload(base),
                    backlog_id="roadmap_1_6",
                    backlog_root=str(repo_path / "tasks"),
                    sprint_id="roadmap_1_6_sprint_1_alpha",
                )

            self.assertEqual(overrides["gstack_parity_manifest_path"], str(base / "gstack_parity_manifest.json"))
            self.assertEqual(overrides["gstack_acceptance_checklist_path"], str(base / "gstack_acceptance_checklist.md"))
            self.assertIn(str(base / "gstack_parity_manifest.json"), overrides["continuity_sprint_artifact_refs"])
            self.assertIn(str(base / "gstack_acceptance_checklist.md"), overrides["continuity_sprint_artifact_refs"])
            kwargs = continuity_mock.call_args.kwargs
            self.assertEqual(kwargs["task_payload"]["backlog_id"], "roadmap_1_6")
            self.assertEqual(kwargs["task_payload"]["sprint_id"], "roadmap_1_6_sprint_1_alpha")

    def test_run_roadmap_gap_closure_preflight_requires_aligned_handoff_boundary(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_ids = [
                ("roadmap_1_6_sprint_4_lightweight_simulation_runtime", "E4-001"),
                ("roadmap_1_6_sprint_5_review_and_outcome_validation", "E5-001"),
                ("roadmap_1_6_sprint_6_statement_to_style_assets", "E6-001"),
                ("roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration", "E7-001"),
            ]
            for sprint_name, story_id in sprint_ids:
                self._write_gap_closure_story(tasks_root / sprint_name, story_id)
            self._write_gap_closure_docs(
                repo_path,
                sprint_id="roadmap_1_6_sprint_5_review_and_outcome_validation",
                story_id="E5-001",
            )
            self._write_gap_closure_manifest(
                base,
                sprint_id="roadmap_1_6_sprint_5_review_and_outcome_validation",
                story_id="E5-001",
            )

            with patch("cli._load_env_config", return_value={"repo": {"versefina": str(repo_path)}}):
                result = runner.invoke(
                    cli,
                    [
                        "run-roadmap-gap-closure",
                        "--project",
                        "versefina",
                        "--env",
                        "test",
                        "--tasks-root",
                        str(tasks_root),
                        "--roadmap-prefix",
                        "roadmap_1_6",
                        "--from-sprint",
                        "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                        "--preflight-only",
                    ],
                )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Gap-closure preflight failed", result.output)

    def test_execute_roadmap_gap_closure_stops_at_p0_closeout_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_specs = [
                ("roadmap_1_6_sprint_1_event_lane_and_mapping_base", "E1-001"),
                ("roadmap_1_6_sprint_2_participant_preparation", "E2-001"),
                ("roadmap_1_6_sprint_3_belief_graph_and_scenarios", "E3-001"),
                ("roadmap_1_6_sprint_4_lightweight_simulation_runtime", "E4-001"),
                ("roadmap_1_6_sprint_5_review_and_outcome_validation", "E5-001"),
                ("roadmap_1_6_sprint_6_statement_to_style_assets", "E6-001"),
                ("roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration", "E7-001"),
            ]
            for sprint_name, story_id in sprint_specs:
                self._write_gap_closure_story(tasks_root / sprint_name, story_id)
            self._write_gap_closure_docs(
                repo_path,
                sprint_id="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                story_id="E4-001",
            )
            self._write_gap_closure_manifest(
                base,
                sprint_id="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                story_id="E4-001",
            )
            (repo_path / "tasks" / "runtime").mkdir(parents=True, exist_ok=True)

            gap_result = cli_module._discover_gap_closure_result(
                tasks_root,
                "roadmap_1_6",
                "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
            )
            preflight = cli_module._preflight_gap_closure(
                repo_b_path=repo_path,
                project="versefina",
                tasks_root=tasks_root,
                roadmap_result=gap_result,
                from_sprint="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                from_story="E4-001",
            )
            self.assertTrue(preflight["passed"])

            sprint_4 = tasks_root / "roadmap_1_6_sprint_4_lightweight_simulation_runtime"
            sprint_5 = tasks_root / "roadmap_1_6_sprint_5_review_and_outcome_validation"
            interrupted_receipt = {
                "status": "interrupted",
                "formal_flow_complete": False,
                "missing_items": ["roadmap_1_6_sprint_1_event_lane_and_mapping_base: formal_flow_incomplete"],
                "root_cause": "Sprint 1-5 are not yet authoritatively closed.",
            }

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch(
                    "cli._run_sprint_directory",
                    side_effect=[
                        {
                            "sprint_dir": str(sprint_4),
                            "story_count": 1,
                            "completed_stories": [{"story_id": "E4-001", "task_id": "task-e4", "commit": "commit-e4"}],
                            "failed_stories": [],
                            "status": "completed",
                            "current_story": None,
                            "current_node": "doc_writer",
                            "last_success_story": "E4-001",
                            "resume_from_story": None,
                            "interruption_reason": None,
                            "error_message": None,
                            "sprint_id": sprint_4.name,
                            "special_acceptance_report_path": str(base / "e4_acceptance.json"),
                        },
                        {
                            "sprint_dir": str(sprint_5),
                            "story_count": 1,
                            "completed_stories": [{"story_id": "E5-001", "task_id": "task-e5", "commit": "commit-e5"}],
                            "failed_stories": [],
                            "status": "completed",
                            "current_story": None,
                            "current_node": "doc_writer",
                            "last_success_story": "E5-001",
                            "resume_from_story": None,
                            "interruption_reason": None,
                            "error_message": None,
                            "sprint_id": sprint_5.name,
                            "special_acceptance_report_path": str(base / "e5_acceptance.json"),
                        },
                    ],
                ) as run_sprint_mock,
                patch("cli._run_gap_closure_validation_suite", return_value={"status": "passed", "command": "pytest"}),
                patch("cli._refresh_gap_closure_outputs", return_value={"report_paths": {}}),
                patch("cli._sync_and_assert_continuity", return_value={"trigger": "resume_interrupt"}),
                patch(
                    "cli._run_p0_closeout_checkpoint",
                    return_value=(interrupted_receipt, base / "p0_closeout.json"),
                ),
            ):
                with self.assertRaises(click.ClickException):
                    cli_module._execute_roadmap_gap_closure(
                        roadmap_result=gap_result,
                        preflight=preflight,
                        repo_b_path=repo_path,
                        tasks_root=tasks_root,
                        env="test",
                        project="versefina",
                        release=False,
                        from_sprint="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                        from_story="E4-001",
                        echo=lambda _message: None,
                    )

            self.assertEqual(run_sprint_mock.call_count, 2)
            resume_payload = json.loads((repo_path / "tasks" / "runtime" / "auto_resume_state.json").read_text(encoding="utf-8"))
            summary_payload = json.loads(Path(str(resume_payload["gap_closure_summary_path"])).read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["status"], "interrupted")
            self.assertEqual(summary_payload["phase_1_sprint_4"]["status"], "completed")
            self.assertEqual(summary_payload["phase_2_sprint_5"]["status"], "completed")
            self.assertEqual(summary_payload["phase_3_p0_closeout"]["status"], "interrupted")
            self.assertEqual(summary_payload["current_sprint"], "p0_closeout")

    def test_execute_roadmap_gap_closure_completes_and_refreshes_showcase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            tasks_root = repo_path / "tasks"
            sprint_specs = [
                ("roadmap_1_6_sprint_1_event_lane_and_mapping_base", "E1-001"),
                ("roadmap_1_6_sprint_2_participant_preparation", "E2-001"),
                ("roadmap_1_6_sprint_3_belief_graph_and_scenarios", "E3-001"),
                ("roadmap_1_6_sprint_4_lightweight_simulation_runtime", "E4-001"),
                ("roadmap_1_6_sprint_5_review_and_outcome_validation", "E5-001"),
                ("roadmap_1_6_sprint_6_statement_to_style_assets", "E6-001"),
                ("roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration", "E7-001"),
            ]
            for sprint_name, story_id in sprint_specs:
                self._write_gap_closure_story(tasks_root / sprint_name, story_id)
            self._write_gap_closure_docs(
                repo_path,
                sprint_id="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                story_id="E4-001",
            )
            self._write_gap_closure_manifest(
                base,
                sprint_id="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                story_id="E4-001",
            )
            (repo_path / "tasks" / "runtime").mkdir(parents=True, exist_ok=True)

            gap_result = cli_module._discover_gap_closure_result(
                tasks_root,
                "roadmap_1_6",
                "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
            )
            preflight = cli_module._preflight_gap_closure(
                repo_b_path=repo_path,
                project="versefina",
                tasks_root=tasks_root,
                roadmap_result=gap_result,
                from_sprint="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                from_story="E4-001",
            )
            self.assertTrue(preflight["passed"])

            sprint_dirs = {
                name: tasks_root / name
                for name, _story_id in sprint_specs
            }
            run_results = []
            for sprint_name in [
                "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                "roadmap_1_6_sprint_5_review_and_outcome_validation",
                "roadmap_1_6_sprint_6_statement_to_style_assets",
                "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration",
            ]:
                story_id = {
                    "roadmap_1_6_sprint_4_lightweight_simulation_runtime": "E4-001",
                    "roadmap_1_6_sprint_5_review_and_outcome_validation": "E5-001",
                    "roadmap_1_6_sprint_6_statement_to_style_assets": "E6-001",
                    "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration": "E7-001",
                }[sprint_name]
                run_results.append(
                    {
                        "sprint_dir": str(sprint_dirs[sprint_name]),
                        "story_count": 1,
                        "completed_stories": [{"story_id": story_id, "task_id": f"task-{story_id.lower()}", "commit": f"commit-{story_id.lower()}"}],
                        "failed_stories": [],
                        "status": "completed",
                        "current_story": None,
                        "current_node": "doc_writer",
                        "last_success_story": story_id,
                        "resume_from_story": None,
                        "interruption_reason": None,
                        "error_message": None,
                        "sprint_id": sprint_name,
                        "special_acceptance_report_path": str(base / f"{sprint_name}_acceptance.json"),
                    }
                )

            with (
                patch.object(cli_module, "ROOT_DIR", base),
                patch("cli._run_sprint_directory", side_effect=run_results) as run_sprint_mock,
                patch("cli._run_gap_closure_validation_suite", return_value={"status": "passed", "command": "pytest"}),
                patch(
                    "cli._refresh_gap_closure_outputs",
                    return_value={
                        "report_paths": {
                            "markdown_path": str(repo_path / "docs" / "reports" / "roadmap_1_6_execution_report.md"),
                            "json_path": str(repo_path / "docs" / "reports" / "roadmap_1_6_execution_report.json"),
                        },
                        "showcase_links": {
                            "product_demo": "http://127.0.0.1:3000/roadmap-1-6-demo",
                            "runtime_showcase": "http://127.0.0.1:8010/versefina/runtime",
                        },
                    },
                ) as refresh_mock,
                patch("cli._sync_and_assert_continuity", return_value={"trigger": "fresh_start"}),
                patch(
                    "cli._run_p0_closeout_checkpoint",
                    return_value=(
                        {
                            "status": "completed",
                            "formal_flow_complete": True,
                            "missing_items": [],
                            "root_cause": "P0 closeout passed.",
                        },
                        base / "p0_closeout.json",
                    ),
                ),
                patch(
                    "cli._probe_local_url",
                    side_effect=lambda url: {"url": url, "reachable": True, "status_code": 200},
                ),
            ):
                summary_path = cli_module._execute_roadmap_gap_closure(
                    roadmap_result=gap_result,
                    preflight=preflight,
                    repo_b_path=repo_path,
                    tasks_root=tasks_root,
                    env="test",
                    project="versefina",
                    release=False,
                    from_sprint="roadmap_1_6_sprint_4_lightweight_simulation_runtime",
                    from_story="E4-001",
                    echo=lambda _message: None,
                )

            self.assertEqual(run_sprint_mock.call_count, 4)
            self.assertTrue(refresh_mock.called)
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["status"], "completed")
            self.assertEqual(summary_payload["phase_3_p0_closeout"]["status"], "completed")
            self.assertEqual(summary_payload["phase_6_final_closeout"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
