from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.acceptance_gate_agent import acceptance_gate_node


class AcceptanceGateAgentTestCase(unittest.TestCase):
    def test_runtime_scope_acceptance_uses_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "acceptance_criteria": ["keep source refs"],
                    "related_files": ["packages/schema/models.py", "packages/schema/state.py", "config/spec/traceability.yaml"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [
                            str(repo_root / "packages" / "schema" / "models.py"),
                            str(repo_root / "packages" / "schema" / "state.py"),
                        ]
                    }
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": [],
                "collaboration_trace_id": "trace-test",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertIn("packages/schema/models.py", result["acceptance_report"])
            self.assertIn("packages/schema/state.py", result["acceptance_report"])

    def test_design_contract_is_allowed_when_design_consultation_is_part_of_story_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "DESIGN.md").write_text("# DESIGN\n", encoding="utf-8")
            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "finahunt",
                    "story_id": "S1-009-ui-validate",
                    "acceptance_criteria": ["The page no longer reads like a demo table or placeholder board."],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "needs_design_consultation": True,
                    "design_contract_path": "DESIGN.md",
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(repo_root / "DESIGN.md")],
                    }
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": [],
                "collaboration_trace_id": "trace-design-scope",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertIn("DESIGN.md", result["acceptance_report"])

    def test_agenthire_s1_001_acceptance_merges_staged_files_and_ignores_cache_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            migration_path = repo_root / "apps" / "api" / "alembic" / "versions" / "0001_agent_marketplace_baseline.py"
            tables_path = repo_root / "apps" / "api" / "src" / "infra" / "db" / "tables.py"
            pyc_path = repo_root / "apps" / "api" / "src" / "__pycache__" / "main.cpython-313.pyc"
            migration_path.parent.mkdir(parents=True, exist_ok=True)
            tables_path.parent.mkdir(parents=True, exist_ok=True)
            pyc_path.parent.mkdir(parents=True, exist_ok=True)
            migration_path.write_text("# migration baseline\n", encoding="utf-8")
            tables_path.write_text("from __future__ import annotations\n", encoding="utf-8")
            pyc_path.write_bytes(b"cache")

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "agentHire",
                    "story_id": "S1-001",
                    "acceptance_criteria": ["Marketplace schema baseline exists"],
                    "primary_files": ["apps/api/alembic/versions/0001_agent_marketplace_baseline.py"],
                    "secondary_files": ["apps/api/src/db/models.py", "docs/contracts/data-model.md"],
                    "related_files": [
                        "apps/api/alembic/versions/0001_agent_marketplace_baseline.py",
                        "apps/api/src/db/models.py",
                        "docs/contracts/data-model.md",
                    ],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [str(tables_path)],
                    }
                },
                "staged_files": [str(migration_path), str(pyc_path)],
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": ["stale blocker"],
                "collaboration_trace_id": "trace-test",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertEqual(result["blocking_issues"], [])
            self.assertIn("apps/api/alembic/versions/0001_agent_marketplace_baseline.py", result["acceptance_report"])
            self.assertIn("apps/api/src/infra/db/tables.py", result["acceptance_report"])
            self.assertNotIn("__pycache__", result["acceptance_report"])


if __name__ == "__main__":
    unittest.main()
