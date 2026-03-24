from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from agentsystem.orchestration.sprint_hooks import run_sprint_pre_hooks


class SprintHooksTestCase(unittest.TestCase):
    def test_run_sprint_pre_hooks_supports_roadmap_execution_order_story_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo_path = base / "versefina"
            sprint_dir = repo_path / "tasks" / "roadmap_1_6_sprint_1_alpha"
            epic_dir = sprint_dir / "epic_demo"
            epic_dir.mkdir(parents=True)
            (sprint_dir / "execution_order.txt").write_text("E1-001\n", encoding="utf-8")
            (sprint_dir / "sprint_plan.md").write_text("# sprint\n", encoding="utf-8")
            (epic_dir / "E1-001_demo.yaml").write_text(
                yaml.safe_dump(
                    {
                        "task_id": "E1-001",
                        "story_id": "E1-001",
                        "goal": "Freeze the first roadmap event whitelist.",
                        "acceptance_criteria": ["done"],
                        "related_files": ["apps/api/src/demo.py"],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            with (
                patch("agentsystem.orchestration.sprint_hooks.summarize_sprint_advice", return_value={"advisory_modes": [], "notes": []}),
                patch(
                    "agentsystem.orchestration.sprint_hooks.office_hours_node",
                    return_value={"office_hours_dir": str(base / "office_hours"), "office_hours_summary": "summary"},
                ),
                patch(
                    "agentsystem.orchestration.sprint_hooks.generate_plan_ceo_review_package",
                    return_value={
                        "review_report_path": str(base / "plan_ceo_review.md"),
                        "requirement_doc_path": str(base / "requirement.md"),
                        "decision_ceremony_path": str(base / "decision.json"),
                    },
                ) as plan_ceo_mock,
                patch(
                    "agentsystem.orchestration.sprint_hooks.write_gstack_parity_audit",
                    return_value={
                        "parity_manifest_path": str(base / "gstack_parity_manifest.json"),
                        "acceptance_checklist_path": str(base / "gstack_acceptance_checklist.md"),
                    },
                ),
            ):
                result = run_sprint_pre_hooks(sprint_dir, project="versefina", release=False)

            self.assertEqual(result["parity_manifest_path"], str(base / "gstack_parity_manifest.json"))
            self.assertEqual(result["acceptance_checklist_path"], str(base / "gstack_acceptance_checklist.md"))
            plan_repo_path = plan_ceo_mock.call_args.args[0]
            self.assertEqual(Path(plan_repo_path).resolve(), repo_path.resolve())
            self.assertIn("Freeze the first roadmap event whitelist.", plan_ceo_mock.call_args.kwargs["requirement_text"])


if __name__ == "__main__":
    unittest.main()
