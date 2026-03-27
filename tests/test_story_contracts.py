from __future__ import annotations

import unittest

from agentsystem.orchestration.story_contracts import classify_artifact_type, infer_contract_scope_paths


class StoryContractsTestCase(unittest.TestCase):
    def test_classify_artifact_type_treats_frontend_test_suffixes_as_tests(self) -> None:
        self.assertEqual(
            classify_artifact_type("apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx"),
            "tests",
        )
        self.assertEqual(
            classify_artifact_type("apps/web/src/features/event-sandbox/OverviewScreen.spec.tsx"),
            "tests",
        )

    def test_acceptance_pack_story_infers_domain_service_scope(self) -> None:
        task = {
            "story_id": "E7-005",
            "task_name": "MVP acceptance pack and migration handoff",
            "goal": "Form the roadmap 1.6 MVP acceptance pack and migration handoff.",
            "story_file": "tasks/roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration/E7-005_mvp_acceptance_pack_and_migration_handoff.yaml",
            "story_kind": "api",
            "related_files": [
                "docs/requirements/e7_005_delivery.md",
                "tasks/sprint_overview_1_6_event_participant_first.md",
            ],
        }

        scope_paths = infer_contract_scope_paths(task, story_track="api_domain")

        self.assertIn("apps/api/src/domain/acceptance_pack/service.py", scope_paths)
        self.assertIn("apps/api/src/services/container.py", scope_paths)
        self.assertIn("apps/api/src/api/command/routes.py", scope_paths)


if __name__ == "__main__":
    unittest.main()
