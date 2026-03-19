from __future__ import annotations

import unittest

from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy, build_agent_activation_plan


class AgentActivationResolverTestCase(unittest.TestCase):
    def test_high_risk_ui_story_enables_design_and_qa_upgrade(self) -> None:
        plan = build_agent_activation_plan(
            {
                "blast_radius": "L3",
                "primary_files": ["apps/web/src/app/dashboard/page.tsx"],
                "related_files": ["apps/web/src/app/dashboard/page.tsx", "apps/web/src/app/dashboard/styles.css"],
            }
        )

        self.assertEqual(plan.story_kind, "ui")
        self.assertEqual(plan.risk_level, "high")
        self.assertEqual(plan.qa_strategy, "browser")
        self.assertEqual(plan.effective_qa_mode, "qa")
        self.assertIn("plan-eng-review", plan.required_modes)
        self.assertIn("review", plan.required_modes)
        self.assertIn("qa-only", plan.required_modes)
        self.assertIn("qa", plan.required_modes)
        self.assertIn("plan-design-review", plan.required_modes)
        self.assertIn("qa-design-review", plan.required_modes)
        self.assertIn("design-consultation", plan.advisory_modes)

    def test_runtime_story_defaults_to_runtime_qa_baseline(self) -> None:
        plan = build_agent_activation_plan(
            {
                "blast_radius": "L1",
                "primary_files": ["agents/source_registry.py"],
                "related_files": ["skills/event/fermentation.py", "tools/gate_check/validate_norms.py"],
            }
        )

        self.assertEqual(plan.story_kind, "runtime_data")
        self.assertEqual(plan.risk_level, "low")
        self.assertEqual(plan.qa_strategy, "runtime")
        self.assertEqual(plan.effective_qa_mode, "qa-only")
        self.assertTrue(plan.auto_upgrade_to_qa)
        self.assertNotIn("plan-design-review", plan.required_modes)

    def test_explicit_skill_mode_is_not_overridden(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L1",
                "skill_mode": "browse",
                "primary_files": ["apps/web/src/app/page.tsx"],
                "related_files": ["apps/web/src/app/page.tsx"],
            }
        )

        self.assertEqual(runtime_task["skill_mode"], "browse")
        self.assertEqual(runtime_task["story_kind"], "ui")
        self.assertEqual(runtime_task["qa_strategy"], "browser")
        self.assertNotIn("fixer_allowed", runtime_task)


if __name__ == "__main__":
    unittest.main()
