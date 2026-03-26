from __future__ import annotations

import unittest
from pathlib import Path

import yaml

import cli as cli_module
from agentsystem.orchestration.workflow_admission import build_story_admission


class Roadmap17AssetsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agentsystem_root = Path(__file__).resolve().parents[1]
        cls.workspace_root = cls.agentsystem_root.parent
        cls.versefina_root = cls.workspace_root / "versefina"
        cls.tasks_root = cls.versefina_root / "tasks"

    def test_roadmap_1_7_discovery_finds_six_sprints_and_thirty_stories(self) -> None:
        result = cli_module._discover_roadmap_result(self.tasks_root, "roadmap_1_7")

        sprint_dirs = [Path(item) for item in (result.get("sprint_dirs") or [])]
        story_cards = list(result.get("story_cards") or [])

        self.assertEqual(result.get("roadmap_prefix"), "roadmap_1_7")
        self.assertEqual(len(sprint_dirs), 6)
        self.assertEqual(len(story_cards), 30)
        self.assertEqual(
            [path.name for path in sprint_dirs],
            [
                "roadmap_1_7_sprint_1_event_input_and_activation",
                "roadmap_1_7_sprint_2_round_interaction_and_timeline",
                "roadmap_1_7_sprint_3_influence_belief_market_dynamics",
                "roadmap_1_7_sprint_4_replay_report_and_validation",
                "roadmap_1_7_sprint_5_event_sandbox_pages",
                "roadmap_1_7_sprint_6_authoritative_closeout",
            ],
        )

    def test_roadmap_1_7_preflight_passes(self) -> None:
        roadmap_result = cli_module._discover_roadmap_result(self.tasks_root, "roadmap_1_7")

        preflight = cli_module._preflight_roadmap(
            repo_b_path=self.versefina_root,
            project="versefina",
            tasks_root=self.tasks_root,
            roadmap_result=roadmap_result,
        )

        self.assertTrue(preflight.get("passed"), preflight.get("errors"))
        self.assertEqual(preflight.get("story_count"), 30)
        self.assertEqual(len(preflight.get("sprints") or []), 6)
        self.assertFalse(preflight.get("errors"))

    def test_sprint_5_ui_story_is_admitted_with_browser_surface(self) -> None:
        story_file = (
            self.tasks_root
            / "roadmap_1_7_sprint_5_event_sandbox_pages"
            / "V17-021_event_sandbox_input_page.yaml"
        )
        payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
        payload.update(
            {
                "project": "versefina",
                "backlog_id": "roadmap_1_7",
                "backlog_root": str(self.tasks_root),
                "sprint_id": "roadmap_1_7_sprint_5_event_sandbox_pages",
                "auto_run": True,
                "formal_entry": True,
                "execution_policy": "continuous_full_sprint",
                "interaction_policy": "non_interactive_auto_run",
                "office_hours_path": "preflight://office-hours",
                "plan_ceo_review_path": "preflight://plan-ceo-review",
                "sprint_framing_path": "preflight://sprint-framing",
                "gstack_parity_manifest_path": "preflight://gstack-parity",
                "gstack_acceptance_checklist_path": "preflight://gstack-checklist",
            }
        )

        admission = build_story_admission(payload, self.versefina_root, story_file=story_file)

        self.assertTrue(admission.get("admitted"), admission.get("errors"))
        self.assertTrue(admission.get("has_browser_urls"))
        self.assertIn("browse", admission.get("required_modes") or [])
        self.assertIn("design-review", admission.get("required_modes") or [])
        self.assertIn("browser_qa", admission.get("expanded_required_agents") or [])


if __name__ == "__main__":
    unittest.main()
