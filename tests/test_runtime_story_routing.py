from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.agents.backend_dev_agent import RUNTIME_TOUCH_MARKER, _apply_backend_changes
from agentsystem.agents.requirement_agent import requirement_analysis_node


class RuntimeStoryRoutingTestCase(unittest.TestCase):
    def test_requirement_agent_maps_runtime_scope_to_backend_only(self) -> None:
        state = {
            "user_requirement": "unify multi-source events",
            "task_payload": {
                "goal": "Unify events",
                "primary_files": ["packages/schema/models.py", "packages/schema/state.py"],
                "related_files": ["packages/schema/models.py", "packages/schema/state.py", "config/spec/traceability.yaml"],
                "secondary_files": ["config/spec/traceability.yaml"],
                "acceptance_criteria": ["keep source refs"],
                "story_inputs": [],
                "story_process": [],
                "story_outputs": [],
                "verification_basis": [],
                "constraints": [],
                "not_do": [],
            },
            "repo_b_path": None,
            "collaboration_trace_id": "trace-test",
        }

        result = requirement_analysis_node(state)

        self.assertTrue(result["subtasks"])
        self.assertTrue(all(task.type == "backend" for task in result["subtasks"]))
        self.assertFalse(any("apps/web" in file for task in result["subtasks"] for file in task.files_to_modify))
        self.assertFalse(any("apps/api" in file for task in result["subtasks"] for file in task.files_to_modify))

    def test_backend_dev_applies_scoped_runtime_touch_when_llm_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            target_file = repo_root / "packages" / "schema" / "models.py"
            target_file.parent.mkdir(parents=True)
            target_file.write_text("from pydantic import BaseModel\n", encoding="utf-8")
            backend_task = type("Task", (), {"files_to_modify": ["packages/schema/models.py"]})()

            with patch("agentsystem.agents.backend_dev_agent.llm_rewrite_file", return_value=""):
                updated_files = _apply_backend_changes(
                    repo_root,
                    {"story_kind": "runtime_data", "story_id": "S1-004", "related_files": ["packages/schema/models.py"]},
                    [backend_task],
                )

            self.assertEqual(updated_files, [str(target_file)])
            self.assertIn(RUNTIME_TOUCH_MARKER, target_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
