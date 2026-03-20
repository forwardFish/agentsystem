from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agentsystem.agents.acceptance_gate_agent import _normalize_changed_path
from agentsystem.agents.backend_dev_agent import _apply_backend_changes
from agentsystem.agents.fix_agent import _generate_fix, route_after_fix
from agentsystem.agents.review_agent import _matches_protected_path
from agentsystem.orchestration.agent_activation_resolver import build_agent_activation_plan
from agentsystem.agents.test_agent import _run_story_specific_validation


class ProjectStoryScopingTestCase(unittest.TestCase):
    def test_agenthire_bootstrap_backend_story_preserves_existing_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            commands_path = repo_root / ".agents" / "commands.yaml"
            project_path = repo_root / ".agents" / "project.yaml"
            commands_path.parent.mkdir(parents=True, exist_ok=True)
            commands_path.write_text("commands:\n  lint:\n    - python scripts/check_scaffold.py\n", encoding="utf-8")
            project_path.write_text("name: agentHire\n", encoding="utf-8")

            backend_tasks = [SimpleNamespace(files_to_modify=[".agents/project.yaml", ".agents/commands.yaml"])]
            payload = {
                "project": "agentHire",
                "story_id": "S0-001",
                "related_files": [".agents/project.yaml", ".agents/commands.yaml"],
            }

            updated_files = _apply_backend_changes(repo_root, payload, backend_tasks)

            self.assertEqual(
                updated_files,
                [
                    str(repo_root / ".agents" / "project.yaml"),
                    str(repo_root / ".agents" / "commands.yaml"),
                ],
            )
            self.assertEqual(commands_path.read_text(encoding="utf-8"), "commands:\n  lint:\n    - python scripts/check_scaffold.py\n")

    def test_agenthire_story_ids_skip_versefina_specific_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            ok, message = _run_story_specific_validation(
                repo_root,
                {
                    "project": "agentHire",
                    "story_id": "S0-001",
                },
            )

            self.assertTrue(ok)
            self.assertIn("No story-specific validation required", message)

    def test_acceptance_gate_normalizes_absolute_repo_paths_for_agenthire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            changed = repo_root / ".agents" / "project.yaml"
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_text("name: agentHire\n", encoding="utf-8")

            normalized = _normalize_changed_path(str(changed), repo_root)

            self.assertEqual(normalized, ".agents/project.yaml")

    def test_fix_agent_does_not_llm_rewrite_yaml_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            target = repo_root / ".agents" / "project.yaml"
            target.parent.mkdir(parents=True, exist_ok=True)
            original = "name: agentHire\n"
            target.write_text(original, encoding="utf-8")

            fixed = _generate_fix(original, "Acceptance failed on scope validation", target)

            self.assertEqual(fixed, original)

    def test_review_protected_path_does_not_block_env_example(self) -> None:
        self.assertFalse(_matches_protected_path(".env.example", [".env", ".env.local"]))
        self.assertTrue(_matches_protected_path(".env", [".env", ".env.local"]))

    def test_fix_agent_does_not_rewrite_env_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            target = repo_root / ".env.example"
            original = "AGENTHIRE_ADMIN_USERNAME=admin\n"
            target.write_text(original, encoding="utf-8")

            fixed = _generate_fix(original, "Review blocked the env file", target)

            self.assertEqual(fixed, original)

    def test_high_risk_story_requires_qa_not_qa_only(self) -> None:
        plan = build_agent_activation_plan(
            {
                "blast_radius": "L2",
                "primary_files": ["apps/api/src/catalog/schema.py", "docs/contracts/api/catalog-api.md"],
                "related_files": ["apps/api/src/catalog/schema.py", "docs/contracts/api/catalog-api.md"],
            }
        )

        self.assertIn("qa", plan.required_modes)
        self.assertNotIn("qa-only", plan.required_modes)

    def test_route_after_fix_can_exit_on_loop_detection(self) -> None:
        next_step = route_after_fix({"error_message": "loop detected", "fix_return_to": "__end__"})
        self.assertEqual(next_step, "__end__")


if __name__ == "__main__":
    unittest.main()
