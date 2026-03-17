from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.core.task_card import TaskCard
from agentsystem.dashboard import main as dashboard_main


class StoryContractReportingTestCase(unittest.TestCase):
    def test_task_card_derives_story_contract_defaults(self) -> None:
        card = TaskCard.model_validate(
            {
                "task_id": "S9-001",
                "task_name": "Demo Story",
                "story_id": "S9-001",
                "blast_radius": "L1",
                "mode": "Safe",
                "goal": "Add a contract-aware demo story",
                "entry_criteria": ["Demo dependency is ready"],
                "acceptance_criteria": ["Demo output exists"],
                "related_files": ["apps/api/src/demo.py"],
                "primary_files": ["apps/api/src/demo.py"],
            }
        )

        self.assertTrue(card.story_inputs)
        self.assertTrue(card.story_process)
        self.assertTrue(card.story_outputs)
        self.assertEqual(card.verification_basis, ["Demo output exists"])

    def test_requirement_agent_persists_story_contract_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "task-demo"
            repo_path.mkdir(parents=True)
            state = {
                "task_id": "task-demo",
                "repo_b_path": str(repo_path),
                "user_requirement": "Implement a story with explicit input output contract.",
                "task_payload": {
                    "goal": "Implement a story with explicit input output contract.",
                    "acceptance_criteria": ["Demo output exists"],
                    "story_inputs": ["Demo request payload", "Demo repository state"],
                    "story_process": ["Inspect the target module", "Implement the requested behavior"],
                    "story_outputs": ["Updated demo module", "Acceptance evidence"],
                    "verification_basis": ["Acceptance checklist", "Manual review"],
                    "primary_files": ["apps/api/src/demo.py"],
                    "related_files": ["apps/api/src/demo.py"],
                },
                "collaboration_trace_id": "trace-demo",
            }

            updated = requirement_analysis_node(state)
            requirement_dir = repo_path.parent / ".meta" / repo_path.name / "requirement"
            parsed_requirement = json.loads(requirement_dir.joinpath("parsed_requirement.json").read_text(encoding="utf-8"))
            intent_confirmation = requirement_dir.joinpath("intent_confirmation.md").read_text(encoding="utf-8")

            self.assertEqual(updated["story_inputs"], ["Demo request payload", "Demo repository state"])
            self.assertEqual(parsed_requirement["story_process"], ["Inspect the target module", "Implement the requested behavior"])
            self.assertEqual(updated["shared_blackboard"]["story_outputs"], ["Updated demo module", "Acceptance evidence"])
            self.assertIn("## Planned Input", intent_confirmation)
            self.assertIn("## Verification Basis", intent_confirmation)

    def test_doc_agent_writes_story_result_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-001",
                    "task_name": "Demo Story",
                    "sprint": "Sprint 0",
                    "epic": "Epic 0.1 Demo",
                    "acceptance_criteria": ["demo output exists"],
                    "story_inputs": ["demo input"],
                    "story_process": ["inspect demo", "update demo"],
                    "story_outputs": ["demo output"],
                    "verification_basis": ["acceptance checklist"],
                    "primary_files": ["apps/api/src/demo.py"],
                    "secondary_files": ["docs/demo.md"],
                },
                "dev_results": {"backend": {"updated_files": ["apps/api/src/demo.py"]}},
                "shared_blackboard": {"current_goal": "Demo Story", "story_inputs": ["demo input"]},
                "handoff_packets": [{"packet_id": "p1"}],
                "issues_to_fix": [],
                "fix_attempts": 0,
                "code_style_review_passed": True,
                "test_passed": True,
                "review_passed": True,
                "code_acceptance_passed": True,
                "acceptance_passed": True,
                "test_results": "StoryValidation: PASS",
                "code_style_review_dir": str(repo_path / ".meta" / "code_style_review"),
                "review_dir": str(repo_path / ".meta" / "review"),
                "code_acceptance_dir": str(repo_path / ".meta" / "code_acceptance"),
                "acceptance_dir": str(repo_path / ".meta" / "acceptance"),
            }

            updated = doc_node(state)
            delivery_dir = Path(updated["delivery_dir"])
            result_report = delivery_dir / "story_result_report.md"
            delivery_report = delivery_dir / "story_delivery_report.md"

            self.assertTrue(result_report.exists())
            self.assertIn("## Actual Input Used", result_report.read_text(encoding="utf-8"))
            self.assertIn("## Planned Story Contract", delivery_report.read_text(encoding="utf-8"))
            self.assertIn("Result report", delivery_report.read_text(encoding="utf-8"))

    def test_load_task_detail_reads_requirement_and_result_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runs_dir = base / "runs"
            meta_dir = base / "repo-worktree" / ".meta" / "task-demo"
            (meta_dir / "requirement").mkdir(parents=True)
            (meta_dir / "delivery").mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (runs_dir / "prod_audit_task-demo.json").write_text(
                json.dumps({"task_id": "task-demo", "success": True, "result": {"task_payload": {}}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (meta_dir / "requirement" / "parsed_requirement.json").write_text('{"story_inputs":["demo input"]}', encoding="utf-8")
            (meta_dir / "requirement" / "intent_confirmation.md").write_text("# Intent", encoding="utf-8")
            (meta_dir / "delivery" / "story_result_report.md").write_text("# Result", encoding="utf-8")

            with (
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "REPO_META_DIR", base / "repo-worktree" / ".meta"),
                patch.object(dashboard_main, "ARTIFACTS_DIR", base / "runs" / "artifacts"),
            ):
                detail = dashboard_main.load_task_detail("task-demo")

            self.assertEqual(detail["artifacts"]["parsed_requirement"], '{"story_inputs":["demo input"]}')
            self.assertEqual(detail["artifacts"]["intent_confirmation"], "# Intent")
            self.assertEqual(detail["artifacts"]["result_report"], "# Result")

    def test_load_story_detail_merges_runtime_story_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runs_dir = base / "runs"
            meta_root = base / "repo-worktree" / ".meta"
            sprint_dir = tasks_dir / "backlog_v1" / "sprint_0_contract_foundation" / "epic_0_1_platform_contract"
            sprint_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            story_file = sprint_dir / "S0-001_demo_story.yaml"
            story_file.write_text(
                "\n".join(
                    [
                        'task_id: "S0-001"',
                        'task_name: "Demo Story"',
                        'story_id: "S0-001"',
                        'sprint: "Sprint 0"',
                        'epic: "Epic 0.1 Demo"',
                        'blast_radius: "L1"',
                        'execution_mode: "Safe"',
                        'mode: "Safe"',
                        'goal: "Demo goal"',
                        'acceptance_criteria:',
                        '  - "demo output exists"',
                        'related_files:',
                        '  - "apps/api/src/demo.py"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (runs_dir / "prod_audit_task-demo.json").write_text(
                json.dumps(
                    {
                        "task_id": "task-demo",
                        "success": True,
                        "result": {
                            "task_payload": {
                                "story_id": "S0-001",
                                "task_id": "S0-001",
                                "story_inputs": ["runtime input"],
                                "story_process": ["runtime process"],
                                "story_outputs": ["runtime output"],
                                "verification_basis": ["runtime verification"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", tasks_dir / "story_status_registry.json"),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
                patch.object(dashboard_main, "REPO_META_DIR", meta_root),
                patch.object(dashboard_main, "ARTIFACTS_DIR", runs_dir / "artifacts"),
            ):
                detail = dashboard_main.load_story_detail("backlog_v1", "sprint_0_contract_foundation", "S0-001", "versefina")

            self.assertEqual(detail["story"]["story_inputs"], ["runtime input"])
            self.assertEqual(detail["story"]["story_process"], ["runtime process"])
            self.assertEqual(detail["story"]["story_outputs"], ["runtime output"])
            self.assertEqual(detail["story"]["verification_basis"], ["runtime verification"])

    def test_finahunt_sprint2_story_specs_define_contract_fields(self) -> None:
        specs = dashboard_main._load_finahunt_sprint2_story_specs()

        self.assertGreaterEqual(len(specs), 15)
        self.assertIn("S2A-006", specs)
        for story_id, payload in specs.items():
            self.assertTrue(payload.get("story_inputs"), story_id)
            self.assertTrue(payload.get("story_process"), story_id)
            self.assertTrue(payload.get("story_outputs"), story_id)
            self.assertTrue(payload.get("verification_basis"), story_id)

    def test_finahunt_dashboard_uses_chinese_labels_for_acceptance(self) -> None:
        template = dashboard_main._build_acceptance_template(
            {
                "story_inputs": ["输入"],
                "story_process": ["过程"],
                "story_outputs": ["输出"],
                "verification_basis": ["依据"],
                "acceptance_criteria": ["标准"],
            },
            {"acceptance_passed": True},
            {"verdict": "approved"},
        )

        self.assertEqual(template["cards"][0]["title"], "1. 输入检查")
        self.assertIn("自动化验收状态", template["cards"][-1]["items"][0])
        self.assertEqual(dashboard_main._label_for_finahunt_dataset("raw_documents"), "原始资讯")
        self.assertEqual(dashboard_main._build_finahunt_inspection({})["first_input_label"], "原始资讯输入")

    def test_versefina_backlog_story_cards_define_contract_fields(self) -> None:
        backlog_root = dashboard_main.TASKS_DIR / "backlog_v1"
        sprint_dirs = [
            backlog_root / "sprint_0_contract_foundation",
            backlog_root / "sprint_1_statement_to_agent",
            backlog_root / "sprint_2_world_ledger_loop",
        ]

        story_files: list[Path] = []
        for sprint_dir in sprint_dirs:
            story_files.extend(sorted(sprint_dir.rglob("S*.yaml")))

        self.assertTrue(story_files)
        for story_file in story_files:
            payload = dashboard_main.yaml_safe_load(story_file)
            story_id = payload.get("story_id") or payload.get("task_id") or story_file.stem
            self.assertTrue(payload.get("story_inputs"), story_id)
            self.assertTrue(payload.get("story_process"), story_id)
            self.assertTrue(payload.get("story_outputs"), story_id)
            self.assertTrue(payload.get("verification_basis"), story_id)

    def test_save_story_acceptance_review_persists_latest_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            registry = base / "story_acceptance_reviews.json"
            with patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", registry):
                review = dashboard_main.save_story_acceptance_review(
                    "versefina",
                    "backlog_v1",
                    "sprint_0_contract_foundation",
                    "S0-001",
                    {
                        "reviewer": "Lin",
                        "verdict": "approved",
                        "summary": "Story is acceptable.",
                        "notes": "Checked inputs and outputs.",
                        "run_id": "task-demo",
                    },
                )
                loaded = dashboard_main.load_story_acceptance_review(
                    "versefina",
                    "backlog_v1",
                    "sprint_0_contract_foundation",
                    "S0-001",
                )

            self.assertEqual(review["verdict"], "approved")
            self.assertEqual(loaded["reviewer"], "Lin")
            self.assertEqual(loaded["run_id"], "task-demo")

    def test_load_story_detail_includes_human_review_and_acceptance_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            runs_dir = base / "runs"
            sprint_dir = tasks_dir / "backlog_v1" / "sprint_0_contract_foundation" / "epic_0_1_platform_contract"
            sprint_dir.mkdir(parents=True)
            runs_dir.mkdir(parents=True)

            (sprint_dir / "S0-001_demo_story.yaml").write_text(
                "\n".join(
                    [
                        'task_id: "S0-001"',
                        'task_name: "Demo Story"',
                        'story_id: "S0-001"',
                        'sprint: "Sprint 0"',
                        'epic: "Epic 0.1 Demo"',
                        'blast_radius: "L1"',
                        'execution_mode: "Safe"',
                        'mode: "Safe"',
                        'goal: "Demo goal"',
                        'acceptance_criteria:',
                        '  - "demo output exists"',
                        'story_inputs:',
                        '  - "demo input"',
                        'story_process:',
                        '  - "inspect demo"',
                        'story_outputs:',
                        '  - "demo output"',
                        'verification_basis:',
                        '  - "acceptance checklist"',
                        'related_files:',
                        '  - "apps/api/src/demo.py"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            review_registry = tasks_dir / "story_acceptance_reviews.json"
            review_registry.write_text(
                json.dumps(
                    {
                        "reviews": [
                            {
                                "project": "versefina",
                                "backlog_id": "backlog_v1",
                                "sprint_id": "sprint_0_contract_foundation",
                                "story_id": "S0-001",
                                "reviewer": "Lin",
                                "verdict": "approved",
                                "summary": "All good.",
                                "notes": "Checked manually.",
                                "checked_at": "2026-03-16T10:00:00+08:00",
                                "updated_at": "2026-03-16T10:00:00+08:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "TASKS_DIR", tasks_dir),
                patch.object(dashboard_main, "STORY_STATUS_REGISTRY", tasks_dir / "story_status_registry.json"),
                patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", review_registry),
                patch.object(dashboard_main, "RUNS_DIR", runs_dir),
            ):
                detail = dashboard_main.load_story_detail("backlog_v1", "sprint_0_contract_foundation", "S0-001", "versefina")

            self.assertEqual(detail["human_review"]["verdict"], "approved")
            self.assertEqual(detail["acceptance_template"]["template_version"], "v1")
            self.assertEqual(detail["acceptance_template"]["cards"][-1]["status"], "approved")

    def test_acceptance_review_api_writes_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            review_registry = base / "story_acceptance_reviews.json"
            client = TestClient(dashboard_main.app)

            with patch.object(dashboard_main, "STORY_ACCEPTANCE_REVIEW_REGISTRY", review_registry):
                response = client.post(
                    "/api/backlogs/backlog_v1/sprints/sprint_0_contract_foundation/stories/S0-001/acceptance-review?project=versefina",
                    json={
                        "reviewer": "Lin",
                        "verdict": "needs_followup",
                        "summary": "Need one more manual check.",
                        "notes": "Output looks right but I want a second pass.",
                        "run_id": "task-demo",
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["verdict"], "needs_followup")
            saved = json.loads(review_registry.read_text(encoding="utf-8"))
            self.assertEqual(saved["reviews"][0]["story_id"], "S0-001")

    def test_finahunt_showcase_story_includes_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runtime_dir = base / "runtime"
            run_dir = runtime_dir / "run-demo"
            run_dir.mkdir(parents=True)
            (run_dir / "manifest.json").write_text(json.dumps({"run_id": "run-demo"}, ensure_ascii=False), encoding="utf-8")
            (run_dir / "result_warehouse_summary.json").write_text(
                json.dumps({"saved_artifacts": [], "manifest_ref": "artifact://manifest"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (run_dir / "raw_documents.json").write_text("[]", encoding="utf-8")
            (run_dir / "normalized_documents.json").write_text("[]", encoding="utf-8")
            (run_dir / "canonical_events.json").write_text("[]", encoding="utf-8")
            (run_dir / "theme_candidates.json").write_text("[]", encoding="utf-8")
            (run_dir / "structured_result_cards.json").write_text("[]", encoding="utf-8")
            (run_dir / "theme_heat_snapshots.json").write_text("[]", encoding="utf-8")
            (run_dir / "fermenting_theme_feed.json").write_text("[]", encoding="utf-8")
            (run_dir / "daily_review.json").write_text("{}", encoding="utf-8")

            review_registry = base / "finahunt_story_acceptance_reviews.json"
            review_registry.write_text(
                json.dumps(
                    {
                        "reviews": [
                            {
                                "project": "finahunt",
                                "backlog_id": "backlog_v1",
                                "sprint_id": "sprint_2_catalyst_mining_core",
                                "story_id": "S2-001",
                                "reviewer": "Lin",
                                "verdict": "approved",
                                "summary": "Sprint 2 story reviewed.",
                                "checked_at": "2026-03-16T10:00:00+08:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(dashboard_main, "FINAHUNT_RUNTIME_DIR", runtime_dir),
                patch.object(dashboard_main, "FINAHUNT_STORY_ACCEPTANCE_REVIEW_REGISTRY", review_registry),
            ):
                showcase = dashboard_main.load_finahunt_runtime_showcase()

            self.assertEqual(showcase["stories"][0]["human_review"]["verdict"], "approved")
            self.assertEqual(showcase["stories"][0]["acceptance_template"]["human_signoff_status"], "approved")


if __name__ == "__main__":
    unittest.main()
