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


if __name__ == "__main__":
    unittest.main()
