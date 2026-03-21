from __future__ import annotations

import unittest

from agentsystem.agents.architecture_review_agent import route_after_architecture_review
from agentsystem.agents.browser_qa_agent import route_after_browser_qa
from agentsystem.agents.investigate_agent import route_after_investigate
from agentsystem.agents.office_hours_agent import route_after_office_hours
from agentsystem.agents.plan_ceo_review_agent import route_after_plan_ceo_review
from agentsystem.agents.plan_design_review_agent import route_after_plan_design_review
from agentsystem.agents.router_agent import route_after_test
from agentsystem.agents.workspace_prep_agent import workspace_prep_node


class QaRoutingTestCase(unittest.TestCase):
    def test_route_after_test_uses_runtime_qa_for_non_ui_story(self) -> None:
        state = {
            "qa_strategy": "runtime",
            "test_passed": True,
            "error_message": None,
        }

        self.assertEqual(route_after_test(state), "runtime_qa")

    def test_route_after_test_upgrades_blocking_baseline_failure_to_fixer(self) -> None:
        state = {
            "qa_strategy": "browser",
            "test_passed": False,
            "error_message": "lint failed",
            "fixer_allowed": False,
            "auto_upgrade_to_qa": True,
            "fix_attempts": 0,
            "browser_qa_report_only": True,
            "executed_modes": [],
        }

        self.assertEqual(route_after_test(state), "fixer")
        self.assertTrue(state["fixer_allowed"])
        self.assertFalse(state["browser_qa_report_only"])
        self.assertEqual(state["effective_qa_mode"], "qa")
        self.assertIn("qa", state["executed_modes"])

    def test_browser_qa_routes_into_qa_design_review_for_high_risk_ui(self) -> None:
        state = {
            "browser_qa_success": True,
            "browser_qa_passed": True,
            "needs_qa_design_review": True,
            "fix_attempts": 0,
        }

        self.assertEqual(route_after_browser_qa(state), "qa_design_review")

    def test_browser_qa_routes_into_qa_design_review_for_design_review_mode(self) -> None:
        state = {
            "browser_qa_success": True,
            "browser_qa_passed": True,
            "skill_mode": "design-review",
            "fix_attempts": 0,
        }

        self.assertEqual(route_after_browser_qa(state), "qa_design_review")

    def test_architecture_review_routes_authenticated_ui_story_to_cookie_setup_first(self) -> None:
        state = {
            "requires_auth": True,
            "has_browser_surface": True,
            "story_kind": "ui",
            "setup_browser_cookies_success": False,
        }

        self.assertEqual(route_after_architecture_review(state), "setup_browser_cookies")

    def test_architecture_review_stops_when_plan_eng_review_needs_user_input(self) -> None:
        state = {
            "awaiting_user_input": True,
            "resume_from_mode": "plan-eng-review",
        }

        self.assertEqual(route_after_architecture_review(state), "__end__")

    def test_office_hours_stops_when_waiting_for_answer(self) -> None:
        state = {
            "awaiting_user_input": True,
            "resume_from_mode": "office-hours",
        }

        self.assertEqual(route_after_office_hours(state), "__end__")

    def test_plan_ceo_review_stops_when_decision_is_unresolved(self) -> None:
        state = {
            "awaiting_user_input": True,
            "resume_from_mode": "plan-ceo-review",
        }

        self.assertEqual(route_after_plan_ceo_review(state), "__end__")

    def test_investigate_routes_authenticated_ui_story_to_cookie_setup_first(self) -> None:
        state = {
            "requires_auth": True,
            "has_browser_surface": True,
            "story_kind": "ui",
            "setup_browser_cookies_success": False,
        }

        self.assertEqual(route_after_investigate(state), "setup_browser_cookies")

    def test_plan_design_review_routes_into_design_consultation_when_required(self) -> None:
        state = {
            "needs_design_consultation": True,
            "design_consultation_success": False,
        }

        self.assertEqual(route_after_plan_design_review(state), "design_consultation")

    def test_workspace_prep_blocks_when_plan_eng_review_is_missing(self) -> None:
        state = {
            "repo_b_path": ".",
            "required_modes": ["plan-eng-review", "review", "qa"],
            "architecture_review_success": False,
        }

        updated = workspace_prep_node(state)

        self.assertEqual(updated["current_step"], "workspace_blocked")
        self.assertEqual(updated["interruption_reason"], "plan_eng_review_required")


if __name__ == "__main__":
    unittest.main()
