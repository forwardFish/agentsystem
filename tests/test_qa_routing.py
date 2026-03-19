from __future__ import annotations

import unittest

from agentsystem.agents.browser_qa_agent import route_after_browser_qa
from agentsystem.agents.router_agent import route_after_test


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


if __name__ == "__main__":
    unittest.main()
