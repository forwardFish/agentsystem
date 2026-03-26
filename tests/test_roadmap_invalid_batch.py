from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agentsystem.orchestration.quality_sentry import evaluate_quality_sentry
from agentsystem.orchestration.roadmap_invalid_batch import cleanup_invalid_batch, invalidate_roadmap_batch


class RoadmapInvalidBatchTestCase(unittest.TestCase):
    def test_quality_sentry_rejects_future_import_only_and_cross_language_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            target = repo_root / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("from __future__ import annotations\n", encoding="utf-8")

            quality = evaluate_quality_sentry(
                repo_root,
                {
                    "related_files": ["apps/api/src/domain/event_ingestion/service.py"],
                    "implementation_contract": {"story_track": "api_domain", "required_artifact_types": ["service"]},
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "expanded_required_agents": ["backend_dev"],
                    "required_modes": ["plan-eng-review"],
                },
            )

            self.assertIn("placeholder_artifact", quality["blocking_issue_types"])

    def test_quality_sentry_uses_contract_scope_paths_for_api_story_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            files = {
                "apps/api/src/domain/event_ingestion/service.py": "from __future__ import annotations\n\nclass EventIngestionService:\n    pass\n",
                "apps/api/src/domain/event_structuring/service.py": (
                    "from __future__ import annotations\n\n"
                    "class EventStructuringService:\n"
                    "    def fallback(self) -> tuple[str, str]:\n"
                    "        return ('ok', 'still-python')\n"
                ),
                "apps/api/src/api/command/routes.py": "from __future__ import annotations\n\nROUTE = '/api/v1/events'\n",
                "apps/api/src/schemas/event.py": "from __future__ import annotations\n\nclass EventRecord:\n    event_id: str\n",
                "apps/api/src/services/container.py": "from __future__ import annotations\n\nCONTAINER = 'ready'\n",
                "apps/api/tests/test_event_ingestion.py": "def test_ok():\n    assert True\n",
                "docs/requirements/e1_003_delivery.md": "# delivery\n",
            }
            for relative_path, content in files.items():
                target = repo_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            quality = evaluate_quality_sentry(
                repo_root,
                {
                    "project": "versefina",
                    "story_id": "E1-003",
                    "related_files": [
                        "apps/api/src/domain/event_ingestion/service.py",
                        "apps/api/src/domain/event_structuring/service.py",
                        "apps/api/src/api/command/routes.py",
                    ],
                    "contract_scope_paths": [
                        "apps/api/src/schemas/event.py",
                        "apps/api/src/services/container.py",
                        "apps/api/tests/test_event_ingestion.py",
                        "docs/requirements/e1_003_delivery.md",
                    ],
                    "implementation_contract": {
                        "story_track": "api_domain",
                        "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    },
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "agent_execution_contract": [{"agent": "backend_dev"}, {"agent": "tester"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["backend_dev", "tester", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                state={
                    "runtime_qa_report": "runtime ok",
                    "agent_mode_coverage": {
                        "required": ["plan-eng-review", "review", "qa"],
                        "executed": ["plan-eng-review", "review", "qa"],
                        "advisory": [],
                        "missing_required": [],
                        "all_required_executed": True,
                    },
                },
            )

            self.assertNotIn("integration_missing", quality["blocking_issue_types"])
            self.assertNotIn("cross_language_contamination", quality["blocking_issue_types"])

    def test_quality_sentry_defers_api_qa_evidence_until_later_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            files = {
                "apps/api/src/domain/event_ingestion/service.py": "from __future__ import annotations\n\nclass EventIngestionService:\n    pass\n",
                "apps/api/src/api/command/routes.py": "from __future__ import annotations\n\nROUTE = '/api/v1/events'\n",
                "apps/api/src/schemas/event.py": "from __future__ import annotations\n\nclass EventRecord:\n    event_id: str\n",
                "apps/api/src/services/container.py": "from __future__ import annotations\n\nCONTAINER = 'ready'\n",
                "apps/api/tests/test_event_ingestion.py": "def test_ok():\n    assert True\n",
                "docs/requirements/e1_003_delivery.md": "# delivery\n",
            }
            for relative_path, content in files.items():
                target = repo_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            task_payload = {
                "project": "versefina",
                "story_id": "E1-003",
                "related_files": [
                    "apps/api/src/domain/event_ingestion/service.py",
                    "apps/api/src/api/command/routes.py",
                ],
                "contract_scope_paths": [
                    "apps/api/src/schemas/event.py",
                    "apps/api/src/services/container.py",
                    "apps/api/tests/test_event_ingestion.py",
                    "docs/requirements/e1_003_delivery.md",
                ],
                "implementation_contract": {
                    "story_track": "api_domain",
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                },
                "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                "agent_execution_contract": [{"agent": "backend_dev"}, {"agent": "tester"}, {"agent": "acceptance_gate"}],
                "expanded_required_agents": ["backend_dev", "tester", "acceptance_gate"],
                "required_modes": ["plan-eng-review", "review", "qa"],
            }

            early_quality = evaluate_quality_sentry(repo_root, task_payload, state={})
            late_quality = evaluate_quality_sentry(repo_root, task_payload, state={"review_passed": True})

            self.assertNotIn("integration_missing", early_quality["blocking_issue_types"])
            self.assertIn("integration_missing", late_quality["blocking_issue_types"])

    def test_cleanup_and_invalidation_handle_roadmap_1_6_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "versefina"
            tracked = repo_root / "apps" / "api" / "src" / "modules" / "statements" / "parser_service.py"
            polluted = repo_root / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            admission_dir = repo_root / "tasks" / "runtime" / "story_admissions"
            tracked.parent.mkdir(parents=True, exist_ok=True)
            polluted.parent.mkdir(parents=True, exist_ok=True)
            admission_dir.mkdir(parents=True, exist_ok=True)
            (repo_root / "tasks").mkdir(parents=True, exist_ok=True)
            (repo_root / "docs" / "handoff").mkdir(parents=True, exist_ok=True)

            tracked.write_text(
                "/* Fixed by Fix Agent after validation failure */\n<h1 className=\"mb-6 text-3xl font-bold\">Agent 实时观测面板</h1>\nfrom __future__ import annotations\n\nprint('ok')\n",
                encoding="utf-8",
            )
            polluted.write_text(
                "/* Fixed by Fix Agent after validation failure */\n<h1 className=\"mb-6 text-3xl font-bold\">Agent 实时观测面板</h1>\nfrom __future__ import annotations\n",
                encoding="utf-8",
            )
            (repo_root / "tasks" / "story_status_registry.json").write_text(
                json.dumps({"stories": [{"backlog_id": "roadmap_1_6", "sprint_id": "roadmap_1_6_sprint_1", "story_id": "E1-003", "status": "done"}]}),
                encoding="utf-8",
            )
            (repo_root / "tasks" / "story_acceptance_reviews.json").write_text(
                json.dumps({"reviews": [{"backlog_id": "roadmap_1_6", "sprint_id": "roadmap_1_6_sprint_1", "story_id": "E1-003", "acceptance_status": "approved", "verdict": "approved"}]}),
                encoding="utf-8",
            )
            (admission_dir / "E1-003.json").write_text(
                json.dumps(
                    {
                        "task_payload": {
                            "backlog_id": "roadmap_1_6",
                            "related_files": [
                                "apps/api/src/modules/statements/parser_service.py",
                                "apps/api/src/domain/event_ingestion/service.py",
                            ],
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            subprocess.run(["git", "add", "apps/api/src/modules/statements/parser_service.py"], cwd=repo_root, check=True, capture_output=True)

            cleanup = cleanup_invalid_batch(repo_root, "roadmap_1_6")
            invalidation = invalidate_roadmap_batch(
                repo_root,
                "roadmap_1_6",
                project="versefina",
                reset_sprint_id="roadmap_1_6_sprint_1",
                reset_story_id="E1-001",
            )

            self.assertIn("apps/api/src/modules/statements/parser_service.py", cleanup["repaired_files"])
            self.assertIn("apps/api/src/domain/event_ingestion/service.py", cleanup["deleted_files"])
            self.assertNotIn("Fixed by Fix Agent", tracked.read_text(encoding="utf-8"))
            self.assertFalse(polluted.exists())
            self.assertEqual(invalidation["story_count"], 1)
            status_payload = json.loads((repo_root / "tasks" / "story_status_registry.json").read_text(encoding="utf-8"))
            self.assertEqual(status_payload["stories"][0]["status"], "invalid_delivery_batch")


if __name__ == "__main__":
    unittest.main()
