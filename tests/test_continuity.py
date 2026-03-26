from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.orchestration.continuity import (
    ContinuityGuardError,
    assert_continuity_ready,
    inject_continuity_into_task,
    load_continuity_bundle,
    sync_continuity,
)


class ContinuityTestCase(unittest.TestCase):
    def test_sync_and_load_fresh_start_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "versefina"
            (repo_root / "tasks" / "runtime").mkdir(parents=True)
            (repo_root / "tasks").mkdir(parents=True, exist_ok=True)
            (workspace / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            (repo_root / "tasks" / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
            (repo_root / "tasks" / "story_acceptance_reviews.json").write_text(json.dumps({"reviews": []}), encoding="utf-8")
            (repo_root / "tasks" / "runtime" / "auto_resume_state.json").write_text(
                json.dumps({"status": "running", "story_id": "S1-001", "current_node": "tester"}, ensure_ascii=False),
                encoding="utf-8",
            )
            story_file = repo_root / "tasks" / "backlog_v1" / "sprint_1_demo" / "epic_demo" / "S1-001_demo.yaml"
            story_file.parent.mkdir(parents=True)
            story_file.write_text("story_id: S1-001\n", encoding="utf-8")

            sync_continuity(
                "fresh_start",
                "versefina",
                repo_root,
                task_payload={"project": "versefina", "story_id": "S1-001", "goal": "demo"},
                current_story_path=story_file,
            )
            self.assertTrue((repo_root / "STATE.md").exists())
            self.assertTrue((repo_root / "NOW.md").exists())
            self.assertTrue((workspace / ".meta" / "versefina" / "continuity" / "STATE.md").exists())
            self.assertTrue((workspace / ".meta" / "versefina" / "continuity" / "NOW.md").exists())
            bundle = load_continuity_bundle(
                "fresh_start",
                "versefina",
                repo_root,
                current_story_path=story_file,
                strict=False,
            )

            self.assertEqual(bundle["trigger"], "fresh_start")
            self.assertEqual(bundle["continuity_now"]["data"]["story_id"], "S1-001")
            self.assertIn("safe_point", bundle["continuity_summary"])
            self.assertEqual(Path(bundle["required_paths"][1]).resolve(), (repo_root / "STATE.md").resolve())
            self.assertEqual(Path(bundle["required_paths"][2]).resolve(), (repo_root / "NOW.md").resolve())
            assert_continuity_ready(bundle, strict=True)

    def test_resume_interrupt_requires_existing_artifact_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "finahunt"
            (repo_root / "tasks" / "runtime").mkdir(parents=True)
            (workspace / "AGENTS.md").write_text("Workspace rules\n", encoding="utf-8")
            (repo_root / "tasks" / "story_status_registry.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
            (repo_root / "tasks" / "story_acceptance_reviews.json").write_text(json.dumps({"reviews": []}), encoding="utf-8")
            (repo_root / "tasks" / "runtime" / "auto_resume_state.json").write_text(
                json.dumps(
                    {"status": "interrupted", "story_id": "S2-001", "current_node": "reviewer", "last_checkpoint_at": "2026-03-23T12:00:00"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            sync_continuity(
                "resume_interrupt",
                "finahunt",
                repo_root,
                task_payload={"project": "finahunt", "story_id": "S2-001"},
                artifact_refs=[repo_root / "missing-artifact.md"],
            )
            bundle = load_continuity_bundle("resume_interrupt", "finahunt", repo_root, strict=False)
            with self.assertRaises(ContinuityGuardError):
                assert_continuity_ready(bundle, strict=True)

    def test_context_assembler_includes_continuity_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            repo_root.mkdir(parents=True)
            payload = inject_continuity_into_task(
                {
                    "goal": "Implement dashboard",
                    "acceptance_criteria": ["done"],
                    "related_files": [],
                },
                {
                    "trigger": "story_boundary",
                    "continuity_summary": {
                        "safe_point": "S1-001 @ reviewer",
                        "status": "running",
                        "why_resumed_here": "Story boundary refresh completed.",
                        "allowed_next_action": "Start the story with refreshed context.",
                        "relevant_artifacts": ["D:/demo/story.yaml"],
                    },
                    "continuity_now": {"status": "running", "next_action": "Start the story."},
                    "continuity_state": {},
                    "continuity_decisions": {},
                    "continuity_refs": {"required": ["D:/demo/story.yaml"], "optional": []},
                    "continuity_last_synced_at": "2026-03-23T12:00:00",
                },
            )

            context = ContextAssembler(repo_root).build_task_context(payload)

            self.assertIn("# Continuity Summary", context)
            self.assertIn("Current safe point: S1-001 @ reviewer", context)


if __name__ == "__main__":
    unittest.main()
