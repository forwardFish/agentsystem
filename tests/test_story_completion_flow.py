from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git import Repo

from agentsystem.agents.architecture_review_agent import architecture_review_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.code_acceptance_agent import code_acceptance_node
from agentsystem.agents.code_style_reviewer_agent import (
    _collect_changed_files,
    _collect_style_review_files,
    code_style_review_node,
    route_after_code_style_review,
)
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import FIXER_COMMENT, fix_node, route_after_fix
from agentsystem.agents.review_agent import ReviewerAgent, review_node, route_after_review
from agentsystem.agents.router_agent import route_after_test
from agentsystem.agents.test_agent import _run_story_specific_validation


class StoryCompletionFlowTestCase(unittest.TestCase):
    def test_review_node_synthesizes_blocker_when_reviewer_rejects_without_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            Repo.init(repo_path)

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {"story_id": "V17-021"},
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-review",
            }

            with patch.object(
                ReviewerAgent,
                "run",
                return_value={
                    "review_success": False,
                    "review_passed": False,
                    "review_dir": str(repo_path / ".meta" / "review"),
                    "review_report": "",
                    "review_findings": [],
                    "review_checklist": [],
                    "blocking_issues": [],
                    "important_issues": [],
                    "nice_to_haves": [],
                    "awaiting_user_input": False,
                    "dialogue_state": None,
                    "next_question": None,
                    "approval_required": False,
                    "handoff_target": None,
                    "resume_from_mode": None,
                    "decision_state": None,
                    "interaction_round": 0,
                    "error_message": "Review failed: ",
                },
            ):
                updated = review_node(state)

            self.assertEqual(updated["failure_type"], "workflow_bug")
            self.assertIn("Review failed:", updated["blocking_issues"][0])
            self.assertEqual(route_after_review(updated), "fixer")

    def test_architecture_review_writes_plan_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "task_id": "task-demo",
                "repo_b_path": str(repo_path),
                "user_requirement": "Implement a dashboard page and its API endpoint.",
                "parsed_goal": "Implement a dashboard page and its API endpoint.",
                "acceptance_checklist": ["page renders", "API returns summary"],
                "verification_basis": ["check API response", "open dashboard page"],
                "primary_files": ["apps/web/src/app/dashboard/page.tsx", "apps/api/src/routes/dashboard.py"],
                "secondary_files": ["docs/architecture.md"],
                "parsed_constraints": ["do not change the persistence schema"],
                "parsed_not_do": ["no unrelated layout rewrite"],
                "story_inputs": ["task payload"],
                "story_outputs": ["dashboard page", "summary API"],
                "subtasks": [
                    {"id": "1", "type": "frontend", "files_to_modify": ["apps/web/src/app/dashboard/page.tsx"]},
                    {"id": "2", "type": "backend", "files_to_modify": ["apps/api/src/routes/dashboard.py"]},
                ],
                "shared_blackboard": {},
                "handoff_packets": [],
                "all_deliverables": [],
                "issues_to_fix": [],
                "resolved_issues": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = architecture_review_node(state)

            self.assertTrue(updated["architecture_review_success"])
            self.assertEqual(updated["current_step"], "architecture_review_done")
            review_dir = Path(updated["architecture_review_dir"])
            self.assertTrue((review_dir / "architecture_review_report.md").exists())
            self.assertTrue((review_dir / "test_plan.json").exists())
            self.assertIn("architecture_review", updated["shared_blackboard"])

    def test_requirement_agent_does_not_infer_devops_from_specification(self) -> None:
        state = {
            "task_id": "task-demo",
            "user_requirement": "Define the platform-wide error code catalog and the state-machine specification for statement, agent, order, and binding flows.",
            "task_payload": {
                "goal": "Define the platform-wide error code catalog and the state-machine specification for statement, agent, order, and binding flows.",
                "related_files": [
                    "docs/contracts/error_codes.md",
                    "docs/contracts/state_machine.md",
                ],
                "acceptance_criteria": ["docs/contracts/error_codes.md documents upload, parsing, risk, matching, and permission error categories."],
            },
            "collaboration_trace_id": "trace-demo",
        }

        updated = requirement_analysis_node(state)
        self.assertTrue(all(subtask.type != "devops" for subtask in updated["subtasks"]))

    def test_requirement_agent_routes_only_primary_files_into_execution_subtasks(self) -> None:
        state = {
            "task_id": "task-demo",
            "user_requirement": "Initialize the core DB schema for the platform.",
            "task_payload": {
                "goal": "Initialize the core DB schema for the platform.",
                "primary_files": ["scripts/init_schema.sql"],
                "secondary_files": [
                    "docs/contracts/trading_agent_profile.schema.json",
                    "docs/contracts/marketworldstate_schema.schema.json",
                ],
                "related_files": [
                    "scripts/init_schema.sql",
                    "docs/contracts/trading_agent_profile.schema.json",
                    "docs/contracts/marketworldstate_schema.schema.json",
                ],
                "acceptance_criteria": ["scripts/init_schema.sql defines the required core tables."],
            },
            "collaboration_trace_id": "trace-demo",
        }

        updated = requirement_analysis_node(state)
        subtasks = updated["subtasks"]
        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].type, "database")
        self.assertEqual(subtasks[0].files_to_modify, ["scripts/init_schema.sql"])

    def test_code_acceptance_passes_for_clean_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            schema_path = repo_path / "docs" / "contracts" / "trading_agent_profile.schema.json"
            schema_path.parent.mkdir(parents=True)
            schema_path.write_text('{\n  "title": "TradingAgentProfile"\n}\n', encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-001",
                    "required_artifact_types": [],
                    "implementation_contract": {
                        "story_id": "S0-001",
                        "story_kind": "contract",
                        "story_track": "contract",
                        "required_artifact_types": [],
                    },
                    "expanded_required_agents": ["code_style_reviewer"],
                    "agent_execution_contract": [
                        {
                            "agent": "code_style_reviewer",
                            "expected_outputs": ["code_style_review_report"],
                        }
                    ],
                },
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

    def test_code_style_review_passes_for_clean_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            schema_path = repo_path / "docs" / "contracts" / "trading_agent_profile.schema.json"
            schema_path.parent.mkdir(parents=True)
            schema_path.write_text('{\n  "title": "TradingAgentProfile"\n}\n', encoding="utf-8")
            (repo_path / ".agents").mkdir(parents=True, exist_ok=True)
            (repo_path / ".agents" / "project.yaml").write_text("code_style:\n  line_length: 120\n", encoding="utf-8")
            (repo_path / ".agents" / "rules.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "commands.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "contracts.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "style_guide.md").write_text("# Style Guide\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-001",
                    "required_artifact_types": [],
                    "implementation_contract": {
                        "story_id": "S0-001",
                        "story_kind": "contract",
                        "story_track": "contract",
                        "required_artifact_types": [],
                    },
                    "expanded_required_agents": ["code_style_reviewer"],
                    "agent_execution_contract": [
                        {
                            "agent": "code_style_reviewer",
                            "expected_outputs": ["code_style_review_report"],
                        }
                    ],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [str(schema_path)],
                    }
                },
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }
            updated = code_style_review_node(state)
            self.assertTrue(updated["code_style_review_success"])
            self.assertTrue(updated["code_style_review_passed"])
            self.assertEqual(route_after_code_style_review(updated), "tester")
            self.assertTrue(Path(updated["code_style_review_dir"]).joinpath("code_style_review_report.md").exists())

    def test_code_style_review_ignores_generated_and_dependency_paths(self) -> None:
        state = {
            "dev_results": {
                "frontend": {
                    "updated_files": [
                        "apps/web/src/app/event-sandbox/page.tsx",
                        "apps/web/node_modules/.bin/next",
                        ".gstack/browse.json",
                        ".meta/task-123/state.json",
                        "apps/web/.next/server/app.js",
                    ],
                }
            },
            "staged_files": [
                "apps/web/src/features/event-sandbox/api.ts",
                "node_modules/react/index.js",
            ],
        }

        changed_files = _collect_changed_files(state)

        self.assertEqual(
            changed_files,
            [
                "apps/web/src/app/event-sandbox/page.tsx",
                "apps/web/src/features/event-sandbox/api.ts",
            ],
        )

    def test_code_style_review_limits_scope_to_declared_story_files(self) -> None:
        state = {
            "task_payload": {
                "primary_files": ["apps/web/src/app/event-sandbox/page.tsx"],
                "secondary_files": [
                    "apps/web/src/features/event-sandbox/EventSandboxInputPage.tsx",
                    "apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx",
                ],
                "related_files": [
                    "apps/web/src/app/event-sandbox/page.tsx",
                    "apps/web/src/features/event-sandbox/EventSandboxInputPage.tsx",
                    "apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx",
                    "docs/requirements/v17_021_delivery.md",
                ],
                "implementation_contract": {
                    "artifact_inventory": {
                        "supporting_code": [
                            "apps/web/src/app/event-sandbox/page.tsx",
                            "apps/web/src/features/event-sandbox/EventSandboxInputPage.tsx",
                            "apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx",
                        ],
                        "docs": ["docs/requirements/v17_021_delivery.md"],
                    }
                },
            },
            "dev_results": {
                "frontend": {
                    "updated_files": [
                        "docs/demo/basic.md",
                        "scripts/build.js",
                        "apps/web/src/app/event-sandbox/page.tsx",
                    ],
                }
            },
        }

        changed_files = _collect_style_review_files(state)

        self.assertEqual(
            changed_files,
            [
                "apps/web/src/app/event-sandbox/page.tsx",
                "apps/web/src/features/event-sandbox/EventSandboxInputPage.tsx",
                "apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx",
                "docs/requirements/v17_021_delivery.md",
            ],
        )

    def test_code_style_review_treats_integration_gaps_as_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            page_path = repo_path / "apps" / "web" / "src" / "app" / "event-sandbox" / "page.tsx"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text("export default function Page() {\n  return <main>demo</main>;\n}\n", encoding="utf-8")
            (repo_path / ".agents").mkdir(parents=True, exist_ok=True)
            (repo_path / ".agents" / "project.yaml").write_text("code_style:\n  line_length: 120\n", encoding="utf-8")
            (repo_path / ".agents" / "rules.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "commands.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "contracts.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "style_guide.md").write_text("# Style Guide\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "V17-021",
                    "required_artifact_types": ["page", "tests", "docs"],
                    "primary_files": ["apps/web/src/app/event-sandbox/page.tsx"],
                    "secondary_files": [
                        "apps/web/src/features/event-sandbox/EventSandboxInputPage.test.tsx",
                        "docs/requirements/v17_021_delivery.md",
                    ],
                    "implementation_contract": {
                        "story_id": "V17-021",
                        "story_kind": "ui",
                        "story_track": "ui",
                        "required_artifact_types": ["page", "tests", "docs"],
                    },
                    "expanded_required_agents": ["code_style_reviewer"],
                    "agent_execution_contract": [
                        {"agent": "code_style_reviewer", "expected_outputs": ["code_style_review_report"]}
                    ],
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(page_path)],
                    }
                },
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = code_style_review_node(state)

            self.assertTrue(updated["code_style_review_success"])
            self.assertTrue(updated["code_style_review_passed"])
            self.assertEqual(route_after_code_style_review(updated), "tester")
            self.assertTrue(
                any("integration_missing" in issue for issue in (updated["code_style_review_issues"] or []))
            )

    def test_code_style_review_missing_declared_file_is_non_blocking_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            page_path = repo_path / "apps" / "web" / "src" / "app" / "event-sandbox" / "page.tsx"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text("export default function Page() {\n  return <main>demo</main>;\n}\n", encoding="utf-8")
            (repo_path / ".agents").mkdir(parents=True, exist_ok=True)
            (repo_path / ".agents" / "project.yaml").write_text("code_style:\n  line_length: 120\n", encoding="utf-8")
            (repo_path / ".agents" / "rules.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "commands.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "contracts.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "style_guide.md").write_text("# Style Guide\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "V17-021",
                    "required_artifact_types": [],
                    "primary_files": ["apps/web/src/app/event-sandbox/page.tsx"],
                    "secondary_files": ["apps/web/src/features/event-sandbox/EventSandboxInputPage.tsx"],
                    "implementation_contract": {
                        "story_id": "V17-021",
                        "story_kind": "ui",
                        "story_track": "ui",
                        "required_artifact_types": [],
                    },
                    "expanded_required_agents": ["code_style_reviewer"],
                    "agent_execution_contract": [
                        {"agent": "code_style_reviewer", "expected_outputs": ["code_style_review_report"]}
                    ],
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(page_path)],
                    }
                },
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = code_style_review_node(state)

            self.assertTrue(updated["code_style_review_success"])
            self.assertTrue(updated["code_style_review_passed"])
            self.assertTrue(
                any("missing from worktree" in issue for issue in (updated["code_style_review_issues"] or []))
            )

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
                "code_style_review_passed": True,
                "test_passed": True,
                "review_passed": True,
                "code_acceptance_passed": True,
                "acceptance_passed": True,
                "test_results": "StoryValidation: PASS",
                "code_style_review_dir": str(repo_path / ".meta" / "code_style_review"),
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

    def test_review_without_structured_findings_becomes_workflow_bug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            Repo.init(repo_path)
            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Exercise reviewer guard path",
                    "acceptance_criteria": ["README updated"],
                },
                "staged_files": [],
                "test_results": "Lint: PASS",
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
                    "blocking_issues": [],
                    "important_issues": [],
                    "nice_to_haves": [],
                    "error_message": None,
                },
            ):
                updated = review_node(state)

            self.assertEqual(updated["failure_type"], "workflow_bug")
            self.assertEqual(updated["interruption_reason"], "reviewer_missing_findings")
            self.assertEqual(route_after_review(updated), "__end__")

    def test_review_pass_with_important_findings_keeps_fixer_queue_empty(self) -> None:
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
                    "goal": "Exercise review advisory findings",
                    "acceptance_criteria": ["README updated"],
                },
                "staged_files": ["README.md"],
                "test_results": "Lint: PASS",
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
                    "review_passed": True,
                    "review_dir": str(repo_path / ".meta" / "review"),
                    "review_report": "# Review Report",
                    "blocking_issues": [],
                    "important_issues": ["Typecheck or automated tests are still running in demo mode."],
                    "nice_to_haves": [],
                    "error_message": None,
                },
            ):
                updated = review_node(state)

            self.assertTrue(updated["review_passed"])
            self.assertEqual(route_after_review(updated), "code_acceptance")
            self.assertEqual(updated["issues_to_fix"], [])

    def test_reviewer_uses_implementation_contract_scope_and_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            route_path = repo_path / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            service_path = repo_path / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            schema_path = repo_path / "apps" / "api" / "src" / "schemas" / "command.py"
            settings_path = repo_path / "apps" / "api" / "src" / "settings" / "base.py"
            test_path = repo_path / "apps" / "api" / "tests" / "test_event_ingestion.py"
            docs_path = repo_path / "docs" / "requirements" / "e1_003_delivery.md"
            for path, content in (
                (route_path, '@router.post("/api/v1/events")\n'),
                (service_path, "from __future__ import annotations\n\nclass Service:\n    pass\n"),
                (schema_path, "from __future__ import annotations\n\nclass EventCommand:\n    pass\n"),
                (settings_path, "from __future__ import annotations\n\nclass Settings:\n    pass\n"),
                (test_path, "def test_ok():\n    assert True\n"),
                (docs_path, "# delivery\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            Repo.init(repo_path)
            task_payload = {
                "project": "versefina",
                "project_repo_root": str(repo_path),
                "goal": "Implement event ingestion and structure extraction",
                "acceptance_criteria": ["POST /api/v1/events exists"],
                "related_files": [
                    "apps/api/src/api/command/routes.py",
                    "apps/api/src/domain/event_ingestion/service.py",
                ],
                "implementation_contract": {
                    "story_track": "api_domain",
                    "contract_scope_paths": [
                        "apps/api/src/schemas/command.py",
                        "apps/api/src/settings/base.py",
                        "apps/api/tests/test_event_ingestion.py",
                        "docs/requirements/e1_003_delivery.md",
                    ],
                },
            }
            state = {
                "repo_b_path": str(repo_path),
                "task_payload": task_payload,
                "story_kind": "api",
                "test_results": "StoryValidation: PASS",
                "runtime_qa_report": "runtime ok",
                "resolved_issues": [],
            }
            changed_files = [
                "apps/api/src/api/command/routes.py",
                "apps/api/src/domain/event_ingestion/service.py",
                "apps/api/src/schemas/command.py",
                "apps/api/src/settings/base.py",
                "apps/api/tests/test_event_ingestion.py",
                "docs/requirements/e1_003_delivery.md",
            ]

            analysis = ReviewerAgent(repo_path, task_payload)._build_review_analysis("", changed_files, state)

            finding_summaries = [str(item.get("summary") or "") for item in analysis["findings"]]
            self.assertEqual(analysis["repo_profile"], "versefina")
            self.assertNotIn("The diff expands beyond the declared story scope.", finding_summaries)
            self.assertNotIn("The change touches production-sensitive runtime or contract surfaces.", finding_summaries)

    def test_route_after_test_sends_successful_run_to_browser_qa(self) -> None:
        state = {
            "test_passed": True,
            "error_message": None,
            "fix_attempts": 0,
        }

        self.assertEqual(route_after_test(state), "browser_qa")

    def test_fixer_routes_back_to_browser_qa_for_browser_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            file_path = repo_path / "apps" / "web" / "src" / "app" / "page.tsx"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("export default function Page(){ return <main>demo</main>; }\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S9-998",
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "related_files": ["apps/web/src/app/page.tsx"],
                },
                "test_passed": True,
                "browser_qa_passed": False,
                "browser_qa_findings": ["Homepage returned HTTP 500."],
                "issues_to_fix": [
                    {
                        "issue_id": "issue-browser",
                        "severity": "blocking",
                        "source_agent": "BrowserQA",
                        "target_agent": "Fixer",
                        "title": "Browser regression",
                        "description": "Homepage returned HTTP 500.",
                        "file_path": "apps/web/src/app/page.tsx",
                    }
                ],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            self.assertEqual(route_after_fix(updated), "browser_qa")

    def test_story_specific_validation_for_s0_002_world_state_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            schema_path = repo_path / "docs" / "contracts" / "marketworldstate_schema.schema.json"
            example_path = repo_path / "docs" / "contracts" / "examples" / "marketworldstate_schema.example.json"
            invalid_path = repo_path / "docs" / "contracts" / "examples" / "marketworldstate_schema.invalid.json"
            invalid_path.parent.mkdir(parents=True, exist_ok=True)

            schema_path.write_text(
                """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MarketWorldState",
  "type": "object",
  "required": ["worldId", "market", "tradingDay", "nextTradingDay", "sessionRules", "costModelDefault", "universe", "prices", "dataVersion"],
  "properties": {
    "worldId": {"type": "string"},
    "market": {"type": "string"},
    "tradingDay": {"type": "string"},
    "nextTradingDay": {"type": "string"},
    "sessionRules": {"type": "object", "required": ["fillPrice", "allowShort", "lotSize"]},
    "costModelDefault": {"type": "object", "required": ["feePct", "slipPct"]},
    "universe": {"type": "array"},
    "prices": {"type": "object"},
    "dataVersion": {"type": "string"}
  },
  "additionalProperties": false
}
""",
                encoding="utf-8",
            )
            example_path.write_text(
                """{
  "worldId": "world_cn_a_v2",
  "market": "CN_A",
  "tradingDay": "2026-03-11",
  "nextTradingDay": "2026-03-12",
  "sessionRules": {"fillPrice": "close", "allowShort": false, "lotSize": 100},
  "costModelDefault": {"feePct": 0.0005, "slipPct": 0.001},
  "universe": ["600519.SH"],
  "prices": {"600519.SH": {"open": 1, "high": 2, "low": 1, "close": 2, "vol": 100}},
  "dataVersion": "v1"
}
""",
                encoding="utf-8",
            )
            invalid_path.write_text(
                """{
  "worldId": "world_cn_a_v2",
  "market": "CN_A",
  "tradingDay": "2026-03-11"
}
""",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-002",
                    "related_files": [
                        "docs/contracts/marketworldstate_schema.schema.json",
                        "docs/contracts/examples/marketworldstate_schema.example.json",
                        "docs/contracts/examples/marketworldstate_schema.invalid.json",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("rejects invalid example", message)

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_002(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            schema_path = repo_path / "docs" / "contracts" / "marketworldstate_schema.schema.json"
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text("{ invalid json", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-002",
                    "related_files": [
                        "docs/contracts/marketworldstate_schema.schema.json",
                        "docs/contracts/examples/marketworldstate_schema.example.json",
                        "docs/contracts/examples/marketworldstate_schema.invalid.json",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Schema JSON parse failed",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-002",
                    "related_files": [
                        "docs/contracts/marketworldstate_schema.schema.json",
                        "docs/contracts/examples/marketworldstate_schema.example.json",
                        "docs/contracts/examples/marketworldstate_schema.invalid.json",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("rejects invalid example", message)

    def test_story_specific_validation_for_s0_003_agent_contract_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            contract_dir = repo_path / "docs" / "contracts"
            example_dir = contract_dir / "examples"
            example_dir.mkdir(parents=True, exist_ok=True)

            contract_dir.joinpath("agent_register.schema.json").write_text(
                """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["agentId", "runtime", "runtimeAgentId", "capabilities"],
  "properties": {
    "agentId": {"type": "string"},
    "runtime": {"type": "string"},
    "runtimeAgentId": {"type": "string"},
    "capabilities": {"type": "array"}
  },
  "additionalProperties": false
}
""",
                encoding="utf-8",
            )
            contract_dir.joinpath("agent_heartbeat.schema.json").write_text(
                """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["agentId", "runtime", "runtimeAgentId", "capabilities", "lastSeenAt", "health"],
  "properties": {
    "agentId": {"type": "string"},
    "runtime": {"type": "string"},
    "runtimeAgentId": {"type": "string"},
    "capabilities": {"type": "array"},
    "lastSeenAt": {"type": "string"},
    "health": {
      "type": "object",
      "required": ["status", "latencyMs"],
      "properties": {
        "status": {"type": "string"},
        "latencyMs": {"type": "integer"}
      }
    }
  },
  "additionalProperties": false
}
""",
                encoding="utf-8",
            )
            contract_dir.joinpath("agent_submit_actions.schema.json").write_text(
                """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["agentId", "tradingDay", "actions"],
  "properties": {
    "agentId": {"type": "string"},
    "tradingDay": {"type": "string"},
    "actions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["symbol", "side", "qty", "reason", "idempotency_key"],
        "properties": {
          "symbol": {"type": "string"},
          "side": {"type": "string", "enum": ["buy", "sell"]},
          "qty": {"type": "integer", "minimum": 1},
          "reason": {"type": "string"},
          "idempotency_key": {"type": "string"}
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
""",
                encoding="utf-8",
            )
            example_dir.joinpath("agent_register.example.json").write_text(
                '{"agentId":"agt_123","runtime":"openclaw","runtimeAgentId":"main","capabilities":["plan","act"]}\n',
                encoding="utf-8",
            )
            example_dir.joinpath("agent_heartbeat.example.json").write_text(
                '{"agentId":"agt_123","runtime":"openclaw","runtimeAgentId":"main","capabilities":["plan","act"],"lastSeenAt":"2026-03-13T09:30:00+08:00","health":{"status":"ok","latencyMs":120}}\n',
                encoding="utf-8",
            )
            example_dir.joinpath("agent_submit_actions.example.json").write_text(
                '{"agentId":"agt_123","tradingDay":"2026-03-13","actions":[{"symbol":"600519.SH","side":"buy","qty":100,"reason":"breakout","idempotency_key":"agt_123-001"}]}\n',
                encoding="utf-8",
            )
            example_dir.joinpath("agent_submit_actions.invalid.json").write_text(
                '{"agentId":"agt_123","tradingDay":"2026-03-13","actions":[{"symbol":"600519.SH","side":"hold","qty":0,"reason":""}]}\n',
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-003",
                    "related_files": [
                        "docs/contracts/agent_register.schema.json",
                        "docs/contracts/agent_heartbeat.schema.json",
                        "docs/contracts/agent_submit_actions.schema.json",
                        "docs/contracts/examples/agent_register.example.json",
                        "docs/contracts/examples/agent_heartbeat.example.json",
                        "docs/contracts/examples/agent_submit_actions.example.json",
                        "docs/contracts/examples/agent_submit_actions.invalid.json",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("reject", message.lower())

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_003(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "docs" / "contracts" / "agent_submit_actions.schema.json"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("{ invalid json", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-003",
                    "related_files": [
                        "docs/contracts/agent_register.schema.json",
                        "docs/contracts/agent_heartbeat.schema.json",
                        "docs/contracts/agent_submit_actions.schema.json",
                        "docs/contracts/examples/agent_register.example.json",
                        "docs/contracts/examples/agent_heartbeat.example.json",
                        "docs/contracts/examples/agent_submit_actions.example.json",
                        "docs/contracts/examples/agent_submit_actions.invalid.json",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Submit-actions schema JSON parse failed",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-003",
                    "related_files": [
                        "docs/contracts/agent_register.schema.json",
                        "docs/contracts/agent_heartbeat.schema.json",
                        "docs/contracts/agent_submit_actions.schema.json",
                        "docs/contracts/examples/agent_register.example.json",
                        "docs/contracts/examples/agent_heartbeat.example.json",
                        "docs/contracts/examples/agent_submit_actions.example.json",
                        "docs/contracts/examples/agent_submit_actions.invalid.json",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("reject", message.lower())

    def test_story_specific_validation_for_s0_004_error_state_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            docs_dir = repo_path / "docs" / "contracts"
            docs_dir.mkdir(parents=True, exist_ok=True)
            docs_dir.joinpath("error_codes.md").write_text(
                "# Error Codes\n\n## Upload\n- a\n\n## Parsing\n- a\n\n## Risk\n- a\n\n## Matching\n- a\n\n## Permission\n- a\n",
                encoding="utf-8",
            )
            docs_dir.joinpath("state_machine.md").write_text(
                "# State Machine\n\n## Statement\n- `uploaded`\n- `parsing`\n- `parsed`\n- `failed`\n\n## Agent\n- `active`\n- `paused`\n- `stale`\n- `banned`\n\n## Order\n- `submitted`\n- `rejected`\n- `filled`\n\n## Binding\n- `pending`\n- `active`\n- `revoked`\n- `expired`\n",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-004",
                    "related_files": [
                        "docs/contracts/error_codes.md",
                        "docs/contracts/state_machine.md",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("required sections and transitions", message)

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_004(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "docs" / "contracts" / "error_codes.md"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("broken", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-004",
                    "related_files": [
                        "docs/contracts/error_codes.md",
                        "docs/contracts/state_machine.md",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Missing required error code sections",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-004",
                    "related_files": [
                        "docs/contracts/error_codes.md",
                        "docs/contracts/state_machine.md",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("required sections and transitions", message)

    def test_story_specific_validation_for_s0_005_core_db_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            sql_path = repo_path / "scripts" / "init_schema.sql"
            sql_path.parent.mkdir(parents=True, exist_ok=True)
            sql_path.write_text(
                """BEGIN;
CREATE TABLE IF NOT EXISTS agents (agent_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS statements (statement_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS trade_records (record_id TEXT PRIMARY KEY, statement_id TEXT REFERENCES statements(statement_id));
CREATE TABLE IF NOT EXISTS agent_profiles (agent_id TEXT PRIMARY KEY REFERENCES agents(agent_id));
CREATE TABLE IF NOT EXISTS world_snapshots (world_id TEXT, trading_day DATE, PRIMARY KEY (world_id, trading_day));
CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, agent_id TEXT REFERENCES agents(agent_id), idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS fills (fill_id TEXT PRIMARY KEY, order_id TEXT REFERENCES orders(order_id));
CREATE TABLE IF NOT EXISTS portfolios (agent_id TEXT REFERENCES agents(agent_id), trading_day DATE, PRIMARY KEY (agent_id, trading_day));
CREATE TABLE IF NOT EXISTS positions (agent_id TEXT REFERENCES agents(agent_id), symbol TEXT, PRIMARY KEY (agent_id, symbol));
CREATE TABLE IF NOT EXISTS equity_points (agent_id TEXT REFERENCES agents(agent_id), trading_day DATE, PRIMARY KEY (agent_id, trading_day));
CREATE TABLE IF NOT EXISTS audit_logs (audit_id TEXT PRIMARY KEY, trace_id TEXT);
CREATE TABLE IF NOT EXISTS idempotency_keys (idempotency_key TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id ON audit_logs(trace_id);
COMMIT;
""",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-005",
                    "related_files": ["scripts/init_schema.sql"],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Core DB schema SQL", message)

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_005(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "scripts" / "init_schema.sql"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("BEGIN;\nCREATE TABLE demo(id INT);\nCOMMIT;\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-005",
                    "related_files": ["scripts/init_schema.sql"],
                },
                "test_passed": False,
                "test_failure_info": "Missing core tables in init_schema.sql",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-005",
                    "related_files": ["scripts/init_schema.sql"],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Core DB schema SQL", message)

    def test_story_specific_validation_for_s0_006_statement_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            storage_path = repo_path / "apps" / "api" / "src" / "modules" / "statements" / "storage.py"
            repository_path = repo_path / "apps" / "api" / "src" / "modules" / "statements" / "repository.py"
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            repository_path.parent.mkdir(parents=True, exist_ok=True)

            storage_path.write_text(
                "def build_statement_object_key(owner_id, statement_id, original_filename):\n"
                "    return f\"statements/{owner_id}/{statement_id}/{original_filename}\"\n\n"
                "def save_statement_object(*args, **kwargs):\n"
                "    return None\n\n"
                "def delete_statement_object(*args, **kwargs):\n"
                "    return None\n",
                encoding="utf-8",
            )
            repository_path.write_text(
                "class StatementMetadata:\n"
                "    statement_id = None\n"
                "    object_key = None\n"
                "    market = None\n"
                "    owner_id = None\n"
                "    parsed_status = None\n\n"
                "def create_statement_metadata_payload(metadata):\n"
                "    return metadata\n\n"
                "def get_statement_metadata_query(statement_id):\n"
                "    return statement_id\n\n"
                "def rollback_statement_metadata_query(statement_id):\n"
                "    return statement_id\n",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-006",
                    "related_files": [
                        "apps/api/src/modules/statements/storage.py",
                        "apps/api/src/modules/statements/repository.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Statement storage artifacts", message)

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_006(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "apps" / "api" / "src" / "modules" / "statements" / "storage.py"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("pass\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-006",
                    "related_files": [
                        "apps/api/src/modules/statements/storage.py",
                        "apps/api/src/modules/statements/repository.py",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Missing statement storage helper behavior",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-006",
                    "related_files": [
                        "apps/api/src/modules/statements/storage.py",
                        "apps/api/src/modules/statements/repository.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Statement storage artifacts", message)

    def test_story_specific_validation_for_s0_007_audit_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            audit_path = repo_path / "apps" / "api" / "src" / "modules" / "audit" / "service.py"
            idempotency_path = repo_path / "apps" / "api" / "src" / "modules" / "idempotency" / "service.py"
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            idempotency_path.parent.mkdir(parents=True, exist_ok=True)

            audit_path.write_text(
                "from dataclasses import dataclass, asdict\n\n"
                "INSERT_AUDIT_LOG_SQL = 'INSERT INTO audit_logs'\n\n"
                "@dataclass(frozen=True)\n"
                "class AuditLogEntry:\n"
                "    audit_id: str\n"
                "    actor_type: str\n"
                "    actor_id: str\n"
                "    action: str\n"
                "    payload_ref: str | None\n"
                "    trace_id: str\n\n"
                "def build_audit_log_payload(entry):\n"
                "    return asdict(entry)\n\n"
                "def build_audit_write_query(entry):\n"
                "    return INSERT_AUDIT_LOG_SQL, build_audit_log_payload(entry)\n",
                encoding="utf-8",
            )
            idempotency_path.write_text(
                "from dataclasses import dataclass\n\n"
                "SELECT_IDEMPOTENCY_KEY_SQL = 'SELECT idempotency_key'\n"
                "INSERT_IDEMPOTENCY_KEY_SQL = 'INSERT INTO idempotency_keys'\n\n"
                "@dataclass(frozen=True)\n"
                "class IdempotencyCheckResult:\n"
                "    idempotency_key: str\n"
                "    seen_before: bool\n"
                "    result_ref: str | None = None\n"
                "    status: str | None = None\n\n"
                "def build_idempotency_lookup_query(idempotency_key):\n"
                "    return SELECT_IDEMPOTENCY_KEY_SQL, {'idempotency_key': idempotency_key}\n\n"
                "def build_idempotency_insert_query(idempotency_key, result_ref, status):\n"
                "    return INSERT_IDEMPOTENCY_KEY_SQL, {'idempotency_key': idempotency_key, 'result_ref': result_ref, 'status': status}\n\n"
                "def evaluate_idempotency(existing_row, idempotency_key):\n"
                "    if not existing_row:\n"
                "        return IdempotencyCheckResult(idempotency_key=idempotency_key, seen_before=False)\n"
                "    return IdempotencyCheckResult(idempotency_key=idempotency_key, seen_before=True, result_ref=existing_row.get('result_ref'), status=existing_row.get('status'))\n",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-007",
                    "related_files": [
                        "apps/api/src/modules/audit/service.py",
                        "apps/api/src/modules/idempotency/service.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Audit and idempotency artifacts", message)

    def test_fixer_rebuilds_contract_story_artifacts_for_s0_007(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "apps" / "api" / "src" / "modules" / "audit" / "service.py"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("pass\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S0-007",
                    "related_files": [
                        "apps/api/src/modules/audit/service.py",
                        "apps/api/src/modules/idempotency/service.py",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Missing audit helper behavior",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S0-007",
                    "related_files": [
                        "apps/api/src/modules/audit/service.py",
                        "apps/api/src/modules/idempotency/service.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Audit and idempotency artifacts", message)

    def test_story_specific_validation_for_s1_001_statement_upload_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            route_path = repo_path / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            schema_path = repo_path / "apps" / "api" / "src" / "schemas" / "command.py"
            service_path = repo_path / "apps" / "api" / "src" / "domain" / "dna_engine" / "service.py"
            storage_path = repo_path / "apps" / "api" / "src" / "infra" / "storage" / "object_store.py"
            route_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            service_path.parent.mkdir(parents=True, exist_ok=True)
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            route_path.write_text(
                '@router.post("/api/v1/statements/upload")\n'
                "def upload_statement(payload: StatementUploadRequest):\n"
                "    return container.dna_engine.ingest_statement(payload)\n",
                encoding="utf-8",
            )
            schema_path.write_text(
                "class StatementUploadRequest:\n"
                "    file_name: str\n"
                "    content_type: str\n"
                "    byte_size: int\n"
                "    statement_id: str\n"
                "\n"
                "class StatementUploadResponse:\n"
                "    upload_status: str\n"
                "    object_key: str\n"
                "    bucket: str\n",
                encoding="utf-8",
            )
            service_path.write_text(
                'upload_status="uploaded"\n'
                'upload_status="rejected"\n'
                "error_message = 'Statement file is empty.'\n"
                "error_message = 'Unsupported statement file type'\n"
                "error_message = 'Statement file exceeds the 10MB upload limit.'\n"
                "build_statement_object_key\n"
                "object_store_bucket()\n",
                encoding="utf-8",
            )
            storage_path.write_text(
                '".csv"\n".xlsx"\n".xls"\n10 * 1024 * 1024\n'
                "def supported_statement_suffixes(): ...\n"
                "def max_statement_upload_bytes(): ...\n"
                "def build_statement_object_key(): ...\n",
                encoding="utf-8",
            )

            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S1-001",
                    "related_files": [
                        "apps/api/src/api/command/routes.py",
                        "apps/api/src/schemas/command.py",
                        "apps/api/src/domain/dna_engine/service.py",
                        "apps/api/src/infra/storage/object_store.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Statement upload API artifacts", message)

    def test_fixer_rebuilds_story_artifacts_for_s1_001(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            broken = repo_path / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text("pass\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S1-001",
                    "related_files": [
                        "apps/api/src/api/command/routes.py",
                        "apps/api/src/schemas/command.py",
                        "apps/api/src/domain/dna_engine/service.py",
                        "apps/api/src/infra/storage/object_store.py",
                    ],
                },
                "test_passed": False,
                "test_failure_info": "Statement upload API contract is incomplete",
                "issues_to_fix": [],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            ok, message = _run_story_specific_validation(
                repo_path,
                {
                    "story_id": "S1-001",
                    "related_files": [
                        "apps/api/src/api/command/routes.py",
                        "apps/api/src/schemas/command.py",
                        "apps/api/src/domain/dna_engine/service.py",
                        "apps/api/src/infra/storage/object_store.py",
                    ],
                },
            )
            self.assertTrue(ok)
            self.assertIn("Statement upload API artifacts", message)

    def test_fixer_routes_back_to_code_style_review_for_style_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            file_path = repo_path / "apps" / "api" / "src" / "demo.py"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("print('demo')\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S9-999",
                    "related_files": ["apps/api/src/demo.py"],
                },
                "test_passed": False,
                "test_failure_info": "tabs are not allowed",
                "issues_to_fix": [
                    {
                        "issue_id": "issue-style",
                        "severity": "blocking",
                        "source_agent": "CodeStyleReviewer",
                        "target_agent": "Fixer",
                        "title": "Code style review issue",
                        "description": "tabs are not allowed",
                    }
                ],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-demo",
            }

            updated = fix_node(state)
            self.assertTrue(updated["fixer_success"])
            self.assertEqual(route_after_fix(updated), "code_style_reviewer")

    def test_fixer_trims_trailing_spaces_for_code_style_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            file_path = repo_path / "apps" / "web" / "src" / "app" / "page.tsx"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("export default function Page() {  \n  return <main>demo</main>;  \n}\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "story_id": "S9-999",
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "related_files": ["apps/web/src/app/page.tsx"],
                },
                "test_passed": True,
                "issues_to_fix": [
                    {
                        "issue_id": "issue-style-trailing",
                        "severity": "blocking",
                        "source_agent": "CodeStyleReviewer",
                        "target_agent": "Fixer",
                        "title": "Code style review issue",
                        "description": "apps/web/src/app/page.tsx:1: trailing spaces are not allowed",
                        "file_path": "apps/web/src/app/page.tsx",
                    }
                ],
                "resolved_issues": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-style-fix",
            }

            updated = fix_node(state)

            self.assertTrue(updated["fixer_success"])
            self.assertEqual(route_after_fix(updated), "code_style_reviewer")
            self.assertNotIn(FIXER_COMMENT, file_path.read_text(encoding="utf-8"))
            self.assertEqual(
                file_path.read_text(encoding="utf-8"),
                "export default function Page() {\n  return <main>demo</main>;\n}\n",
            )


if __name__ == "__main__":
    unittest.main()
