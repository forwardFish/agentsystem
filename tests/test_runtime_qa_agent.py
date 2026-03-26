from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.runtime_qa_agent import runtime_qa_node


class RuntimeQaAgentTestCase(unittest.TestCase):
    def test_runtime_qa_skips_frontend_test_command_for_backend_story(self) -> None:
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
                    "story_id": "E1-005",
                    "primary_files": ["apps/api/src/domain/event_casebook/service.py"],
                    "related_files": ["apps/api/src/domain/event_casebook/service.py"],
                    "implementation_contract": {
                        "contract_scope_paths": [
                            "apps/api/src/domain/event_casebook/service.py",
                            "apps/api/tests/test_event_casebook.py",
                        ]
                    },
                },
                "verification_basis": ["event casebook replay works"],
                "handoff_packets": [],
                "issues_to_fix": [],
                "all_deliverables": [],
                "mode_artifact_paths": {},
                "qa_strategy": "runtime",
                "effective_qa_mode": "qa",
                "collaboration_trace_id": "trace-runtime-qa",
            }

            updated = runtime_qa_node(state)

            self.assertTrue(updated["runtime_qa_passed"])
            self.assertEqual(updated["runtime_qa_findings"], [])
            self.assertIn("No runtime QA commands executed.", updated["runtime_qa_report"])
            self.assertIn("out of scope for this story", updated["runtime_qa_report"])


if __name__ == "__main__":
    unittest.main()
