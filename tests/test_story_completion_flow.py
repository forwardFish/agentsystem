from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git import Repo

from agentsystem.agents.code_acceptance_agent import code_acceptance_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.review_agent import review_node, route_after_review


class StoryCompletionFlowTestCase(unittest.TestCase):
    def test_code_acceptance_passes_for_clean_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            schema_path = repo_path / "docs" / "contracts" / "trading_agent_profile.schema.json"
            schema_path.parent.mkdir(parents=True)
            schema_path.write_text('{\n  "title": "TradingAgentProfile"\n}\n', encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "dev_results": {
                    "backend": {
                        "updated_files": [str(schema_path)],
                    }
                },
            }
            updated = code_acceptance_node(state)
            self.assertTrue(updated["code_acceptance_success"])
            self.assertTrue(updated["code_acceptance_passed"])
            self.assertTrue(Path(updated["code_acceptance_dir"]).joinpath("code_acceptance_report.md").exists())

    def test_doc_agent_writes_delivery_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-001",
                    "task_name": "TradingAgentProfile Schema",
                    "sprint": "Sprint 0",
                    "epic": "Epic 0.1 Platform Contract",
                    "acceptance_criteria": ["schema file exists", "example passes validation"],
                },
                "test_passed": True,
                "review_passed": True,
                "code_acceptance_passed": True,
                "acceptance_passed": True,
                "test_results": "StoryValidation: PASS",
                "review_dir": str(repo_path / ".meta" / "review"),
                "code_acceptance_dir": str(repo_path / ".meta" / "code_acceptance"),
                "acceptance_dir": str(repo_path / ".meta" / "acceptance"),
            }
            updated = doc_node(state)
            delivery_dir = Path(updated["delivery_dir"])
            self.assertTrue((delivery_dir / "story_completion_standard.md").exists())
            self.assertTrue((delivery_dir / "story_delivery_report.md").exists())
            self.assertIn("Story Delivery Report", updated["doc_result"])

    def test_review_block_routes_back_to_fixer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            changed_file = repo_path / "README.md"
            changed_file.write_text("demo change\n", encoding="utf-8")
            repo = Repo.init(repo_path)
            repo.git.add("README.md")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Create an intentionally failing review path",
                    "acceptance_criteria": ["README updated"],
                },
                "staged_files": ["README.md"],
                "test_results": "Lint: FAIL",
                "collaboration_trace_id": "trace-demo",
                "handoff_packets": [],
                "issues_to_fix": [],
                "resolved_issues": [],
                "all_deliverables": [],
            }
            with patch(
                "agentsystem.agents.review_agent.ReviewerAgent.run",
                return_value={
                    "review_success": True,
                    "review_passed": False,
                    "review_dir": str(repo_path / ".meta" / "review"),
                    "review_report": "# Review Report",
                    "blocking_issues": ["Validation report still contains failing checks."],
                    "important_issues": ["Typecheck is still in demo mode."],
                    "nice_to_haves": [],
                    "error_message": None,
                },
            ):
                updated = review_node(state)
            self.assertFalse(updated["review_passed"])
            self.assertEqual(route_after_review(updated), "fixer")
            self.assertGreater(len(updated["issues_to_fix"]), 0)


if __name__ == "__main__":
    unittest.main()
