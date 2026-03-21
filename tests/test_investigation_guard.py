from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.workspace_prep_agent import workspace_prep_node


class InvestigationGuardTestCase(unittest.TestCase):
    def test_bugfix_workspace_prep_requires_investigation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "bug_scope": "regression",
                "investigation_report": None,
            }
            updated = workspace_prep_node(state)

            self.assertEqual(updated["current_step"], "workspace_blocked")
            self.assertEqual(updated["failure_type"], "workflow_bug")
            self.assertEqual(updated["interruption_reason"], "investigation_required")
            self.assertIn("investigate", updated["error_message"])


if __name__ == "__main__":
    unittest.main()
