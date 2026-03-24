from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.test_agent import test_node


class TestAgentExecutionTestCase(unittest.TestCase):
    def test_test_node_runs_typecheck_and_test_commands_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            agents_dir = repo_path / ".agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "project.yaml").write_text(
                "name: demo\ngit:\n  default_branch: main\n  working_branch_prefix: agent/\n",
                encoding="utf-8",
            )
            (agents_dir / "rules.yaml").write_text("protected_paths: []\n", encoding="utf-8")
            (agents_dir / "commands.yaml").write_text(
                "\n".join(
                    [
                        "commands:",
                        '  lint:',
                        '    - python -c "print(\'lint ok\')"',
                        '  typecheck:',
                        '    - python -c "print(\'typecheck ok\')"',
                        '  test:',
                        '    - python -c "print(\'test ok\')"',
                    ]
                ),
                encoding="utf-8",
            )
            (agents_dir / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (agents_dir / "contracts.yaml").write_text("{}\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {},
                "handoff_packets": [],
                "issues_to_fix": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-test-agent",
            }

            updated = test_node(state)

            self.assertTrue(updated["test_passed"])
            self.assertIn("Lint: PASS", updated["test_results"])
            self.assertIn("Typecheck: PASS", updated["test_results"])
            self.assertIn("Test: PASS", updated["test_results"])

    def test_test_node_skips_frontend_commands_when_story_scope_is_docs_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            agents_dir = repo_path / ".agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "project.yaml").write_text(
                "name: demo\ngit:\n  default_branch: main\n  working_branch_prefix: agent/\n",
                encoding="utf-8",
            )
            (agents_dir / "rules.yaml").write_text("protected_paths: []\n", encoding="utf-8")
            (agents_dir / "commands.yaml").write_text(
                "\n".join(
                    [
                        "commands:",
                        "  lint:",
                        '    - pnpm --dir apps/web lint',
                        "  test:",
                        '    - pnpm --dir apps/web test --run',
                    ]
                ),
                encoding="utf-8",
            )
            (agents_dir / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (agents_dir / "contracts.yaml").write_text("{}\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "E1-001",
                    "related_files": ["docs/requirements/event_whitelist.md"],
                    "primary_files": ["docs/requirements/event_whitelist.md"],
                },
                "handoff_packets": [],
                "issues_to_fix": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-test-agent-docs",
            }

            updated = test_node(state)

            self.assertTrue(updated["test_passed"])
            self.assertIn("Lint: SKIP (out of scope)", updated["test_results"])
            self.assertIn("Test: SKIP (out of scope)", updated["test_results"])
            self.assertIn("StoryValidation: PASS", updated["test_results"])


if __name__ == "__main__":
    unittest.main()
