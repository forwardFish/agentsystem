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
                    "implementation_contract": {
                        "story_track": "contract_schema",
                        "required_artifact_types": ["schema"],
                    },
                    "required_artifact_types": ["schema"],
                    "agent_execution_contract": [{"agent": "requirement_analysis"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["requirement_analysis", "acceptance_gate"],
                    "required_modes": ["plan-eng-review"],
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
                "agent_mode_coverage": {
                    "required": ["plan-eng-review"],
                    "executed": ["plan-eng-review"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
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
            (repo_root / "apps" / "web" / "tests").mkdir(parents=True, exist_ok=True)
            (repo_root / "apps" / "web" / "tests" / "page.test.tsx").write_text("test('ok', () => {})\n", encoding="utf-8")
            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "finahunt",
                    "story_id": "S1-009-ui-validate",
                    "acceptance_criteria": ["The page no longer reads like a demo table or placeholder board."],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "related_files": ["apps/web/src/app/page.tsx", "apps/web/tests/page.test.tsx"],
                    "needs_design_consultation": True,
                    "design_contract_path": "DESIGN.md",
                    "implementation_contract": {
                        "story_track": "ui",
                        "required_artifact_types": ["tests", "docs", "browser_evidence", "design_evidence"],
                    },
                    "required_artifact_types": ["tests", "docs", "browser_evidence", "design_evidence"],
                    "agent_execution_contract": [{"agent": "browse"}, {"agent": "qa_design_review"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["browse", "qa_design_review", "acceptance_gate"],
                    "required_modes": ["browse", "design-review"],
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(repo_root / "DESIGN.md")],
                    }
                },
                "browse_report": "browse evidence",
                "qa_design_review_report": "design qa",
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": [],
                "agent_mode_coverage": {
                    "required": ["browse", "design-review"],
                    "executed": ["browse", "design-review"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
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
            migration_path.write_text(
                "revision = '0001'\n\ndef upgrade() -> None:\n    return None\n",
                encoding="utf-8",
            )
            tables_path.write_text(
                "from __future__ import annotations\n\nTABLES = ['agents']\n",
                encoding="utf-8",
            )
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
                    "implementation_contract": {
                        "story_track": "contract_schema",
                        "required_artifact_types": ["schema"],
                    },
                    "required_artifact_types": ["schema"],
                    "agent_execution_contract": [{"agent": "requirement_analysis"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["requirement_analysis", "acceptance_gate"],
                    "required_modes": ["plan-eng-review"],
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
                "agent_mode_coverage": {
                    "required": ["plan-eng-review"],
                    "executed": ["plan-eng-review"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "collaboration_trace_id": "trace-test",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertEqual(result["blocking_issues"], [])
            self.assertIn("apps/api/alembic/versions/0001_agent_marketplace_baseline.py", result["acceptance_report"])
            self.assertIn("apps/api/src/infra/db/tables.py", result["acceptance_report"])
            self.assertNotIn("__pycache__", result["acceptance_report"])

    def test_api_story_without_route_container_and_tests_fails_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            docs_path = repo_root / "docs" / "requirements" / "story.md"
            service_path.parent.mkdir(parents=True, exist_ok=True)
            docs_path.parent.mkdir(parents=True, exist_ok=True)
            service_path.write_text("from __future__ import annotations\n\nclass Service:\n    pass\n", encoding="utf-8")
            docs_path.write_text("# story\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "E1-003",
                    "acceptance_criteria": ["Service exists"],
                    "related_files": [
                        "apps/api/src/domain/event_ingestion/service.py",
                        "docs/requirements/story.md",
                    ],
                    "implementation_contract": {
                        "story_track": "api_domain",
                        "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    },
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "expanded_required_agents": ["backend_dev", "tester", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [str(service_path), str(docs_path)],
                    }
                },
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review"],
                    "advisory": [],
                    "missing_required": ["qa"],
                    "all_required_executed": False,
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": [],
                "collaboration_trace_id": "trace-api-gap",
            }

            result = acceptance_gate_node(state)

            self.assertFalse(result["acceptance_passed"])
            self.assertTrue(any("integration_missing" in item for item in result["blocking_issues"]))
            self.assertIn("gstack parity", result["acceptance_report"].lower())

    def test_contract_scope_paths_are_allowed_during_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "event.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_event_ingestion.py"
            docs_path = repo_root / "docs" / "requirements" / "e1_003_delivery.md"
            route_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            for path, content in (
                (container_path, "from __future__ import annotations\n"),
                (schema_path, "from __future__ import annotations\n"),
                (test_path, "def test_ok():\n    assert True\n"),
                (docs_path, "# delivery\n"),
                (route_path, "from __future__ import annotations\n"),
                (service_path, "from __future__ import annotations\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "E1-003",
                    "acceptance_criteria": ["Service exists"],
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
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "expanded_required_agents": ["backend_dev", "tester", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [
                            str(service_path),
                            str(route_path),
                            str(schema_path),
                            str(container_path),
                            str(test_path),
                            str(docs_path),
                        ]
                    }
                },
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review", "qa"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "runtime_qa_report": "runtime ok",
                "blocking_issues": [],
                "collaboration_trace_id": "trace-contract-scope",
            }

            result = acceptance_gate_node(state)

            self.assertFalse(result["acceptance_passed"])
            self.assertFalse(any("Changes exceed task scope" in item for item in result["blocking_issues"]))

    def test_acceptance_uses_contract_scope_paths_from_implementation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "event.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_event_ingestion.py"
            docs_path = repo_root / "docs" / "requirements" / "e1_003_delivery.md"
            route_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "event_ingestion" / "service.py"
            runtime_qa_path = repo_root / ".meta" / "repo" / "runtime_qa" / "runtime_qa_report.md"
            for path, content in (
                (container_path, "from __future__ import annotations\n\nCONTAINER = object()\n"),
                (
                    schema_path,
                    "from __future__ import annotations\n\nclass EventRecord:\n    event_id: str\n    title: str\n",
                ),
                (test_path, "def test_ok():\n    assert True\n"),
                (docs_path, "# delivery\n"),
                (
                    route_path,
                    "from __future__ import annotations\n\n"
                    "def register_routes() -> list[str]:\n"
                    "    return ['/api/v1/events']\n",
                ),
                (
                    service_path,
                    "from __future__ import annotations\n\n"
                    "class Service:\n"
                    "    def ingest(self) -> str:\n"
                    "        return 'ok'\n",
                ),
                (runtime_qa_path, "# runtime qa\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "E1-003",
                    "acceptance_criteria": ["Service exists"],
                    "related_files": [
                        "apps/api/src/domain/event_ingestion/service.py",
                        "apps/api/src/api/command/routes.py",
                    ],
                    "implementation_contract": {
                        "story_track": "api_domain",
                        "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                        "contract_scope_paths": [
                            "apps/api/src/schemas/event.py",
                            "apps/api/src/services/container.py",
                            "apps/api/tests/test_event_ingestion.py",
                            "docs/requirements/e1_003_delivery.md",
                        ],
                    },
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "expanded_required_agents": ["backend_dev", "tester", "runtime_qa", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [
                            str(service_path),
                            str(route_path),
                            str(schema_path),
                            str(container_path),
                            str(test_path),
                            str(docs_path),
                        ]
                    }
                },
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review", "qa"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "runtime_qa_report": str(runtime_qa_path),
                "blocking_issues": [],
                "collaboration_trace_id": "trace-impl-scope",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertFalse(any("Changes exceed task scope" in item for item in result["blocking_issues"]))

    def test_acceptance_ignores_snapshot_unchanged_files_when_enforcing_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            snapshot_root = root / ".meta" / "repo" / "snapshot_base"

            current_paths = {
                "service": repo_root / "apps" / "api" / "src" / "domain" / "event_casebook" / "service.py",
                "schema": repo_root / "apps" / "api" / "src" / "schemas" / "event.py",
                "route": repo_root / "apps" / "api" / "src" / "api" / "query" / "routes.py",
                "command_route": repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py",
                "container": repo_root / "apps" / "api" / "src" / "services" / "container.py",
                "test": repo_root / "apps" / "api" / "tests" / "test_event_casebook.py",
                "docs": repo_root / "docs" / "requirements" / "e1_005_delivery.md",
            }
            baseline_paths = {name: snapshot_root / path.relative_to(repo_root) for name, path in current_paths.items()}

            for path in list(current_paths.values()) + list(baseline_paths.values()):
                path.parent.mkdir(parents=True, exist_ok=True)

            current_paths["service"].write_text(
                "from __future__ import annotations\n\nclass EventCasebookService:\n    pass\n",
                encoding="utf-8",
            )
            current_paths["schema"].write_text(
                "from __future__ import annotations\n\nclass EventRecord:\n    event_id: str\n",
                encoding="utf-8",
            )
            current_paths["route"].write_text(
                "from __future__ import annotations\n\n"
                "def event_casebook() -> dict[str, str]:\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            current_paths["command_route"].write_text(
                "from __future__ import annotations\n\n"
                "def register_routes() -> list[str]:\n"
                "    return ['/api/v1/events']\n",
                encoding="utf-8",
            )
            current_paths["container"].write_text(
                "from __future__ import annotations\n\nCONTAINER = object()\n",
                encoding="utf-8",
            )
            current_paths["test"].write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            current_paths["docs"].write_text("# delivery\n", encoding="utf-8")

            baseline_paths["service"].write_text(
                "from __future__ import annotations\n\nclass LegacyCasebookService:\n    pass\n",
                encoding="utf-8",
            )
            baseline_paths["schema"].write_text("from __future__ import annotations\n", encoding="utf-8")
            baseline_paths["route"].write_text("from __future__ import annotations\n", encoding="utf-8")
            baseline_paths["command_route"].write_text(
                current_paths["command_route"].read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            baseline_paths["container"].write_text("from __future__ import annotations\n", encoding="utf-8")
            baseline_paths["test"].write_text("def test_old():\n    assert True\n", encoding="utf-8")
            baseline_paths["docs"].write_text("# old delivery\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "E1-005",
                    "acceptance_criteria": ["Support replay by event_id"],
                    "related_files": [
                        "apps/api/src/domain/event_casebook/service.py",
                        "workspace/event_casebook/",
                    ],
                    "contract_scope_paths": [
                        "apps/api/src/schemas/event.py",
                        "apps/api/src/api/query/routes.py",
                        "apps/api/src/services/container.py",
                        "apps/api/tests/test_event_casebook.py",
                        "docs/requirements/e1_005_delivery.md",
                    ],
                    "implementation_contract": {
                        "story_track": "api_domain",
                        "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                        "contract_scope_paths": [
                            "apps/api/src/schemas/event.py",
                            "apps/api/src/api/query/routes.py",
                            "apps/api/src/services/container.py",
                            "apps/api/tests/test_event_casebook.py",
                            "docs/requirements/e1_005_delivery.md",
                        ],
                    },
                    "required_artifact_types": ["schema", "service", "route", "container_wiring", "tests", "docs"],
                    "agent_execution_contract": [{"agent": "backend_dev"}],
                    "expanded_required_agents": ["backend_dev", "tester", "runtime_qa", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [
                            str(current_paths["service"]),
                            str(current_paths["schema"]),
                            str(current_paths["route"]),
                            str(current_paths["command_route"]),
                            str(current_paths["container"]),
                            str(current_paths["test"]),
                            str(current_paths["docs"]),
                        ]
                    }
                },
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review", "qa"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "runtime_qa_report": "runtime ok",
                "blocking_issues": [],
                "collaboration_trace_id": "trace-snapshot-scope",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertFalse(any("apps/api/src/api/command/routes.py" in item for item in result["blocking_issues"]))

    def test_contract_schema_story_uses_python_schema_for_field_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            docs_path = repo_root / "docs" / "需求文档" / "Event_Structuring_字段字典.md"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "event.py"
            docs_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            docs_path.write_text("# Event Structuring 字段字典\n", encoding="utf-8")
            schema_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "EVENT_LIFECYCLE_STATUSES = ('raw', 'structured', 'prepared', 'simulated', 'reviewed')",
                        "",
                        "class EventRecord:",
                        "    event_id: str",
                        "    title: str",
                        "    body: str",
                        "    source: str",
                        "    event_time: str",
                        "    status: str",
                        "",
                        "class EventStructure:",
                        "    event_type: str",
                        "    entities: list[str]",
                        "    commodities: list[str]",
                        "    chain_links: list[dict[str, str]]",
                        "    sectors: list[str]",
                        "    affected_symbols: list[str]",
                        "    causal_chain: list[str]",
                        "    monitor_signals: list[str]",
                        "    invalidation_conditions: list[str]",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "E1-002",
                    "acceptance_criteria": [
                        "EventRecord 至少包含 event_id、title、body、source、event_time、status。",
                        "EventStructure 至少包含 event_type、entities、commodities、chain_links、sectors、affected_symbols、causal_chain、monitor_signals、invalidation_conditions。",
                        "状态机至少覆盖 raw、structured、prepared、simulated、reviewed。",
                    ],
                    "related_files": [
                        "docs/需求文档/Event_Structuring_字段字典.md",
                        "apps/api/src/schemas/event.py",
                    ],
                    "implementation_contract": {
                        "story_track": "contract_schema",
                        "required_artifact_types": ["schema"],
                    },
                    "required_artifact_types": ["schema"],
                    "agent_execution_contract": [{"agent": "requirement_analysis"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["requirement_analysis", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [str(docs_path), str(schema_path)],
                    }
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "blocking_issues": [],
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review", "qa"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "collaboration_trace_id": "trace-contract-schema",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertIn("EventRecord contract fields are present", result["acceptance_report"])
            self.assertIn("EventStructure contract fields are present", result["acceptance_report"])

    def test_acceptance_treats_python_schema_tokens_as_schema_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "simulation.py"
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "SIMULATION_ACTION_PROTOCOL = (",
                        "    'IGNORE',",
                        "    'WATCH',",
                        "    'VALIDATE',",
                        "    'BROADCAST_BULL',",
                        "    'BROADCAST_BEAR',",
                        "    'LEAD',",
                        "    'FOLLOW',",
                        "    'EXIT',",
                        ")",
                    ]
                ),
                encoding="utf-8",
            )

            state = {
                "repo_b_path": str(repo_root),
                "task_payload": {
                    "project": "versefina",
                    "story_id": "V17-004",
                    "acceptance_criteria": ["Schemas define IGNORE, WATCH, VALIDATE, BROADCAST_BULL, BROADCAST_BEAR, LEAD, FOLLOW, and EXIT."],
                    "related_files": ["apps/api/src/schemas/simulation.py"],
                    "implementation_contract": {
                        "story_track": "contract_schema",
                        "required_artifact_types": ["schema"],
                    },
                    "required_artifact_types": ["schema"],
                    "agent_execution_contract": [{"agent": "backend_dev"}, {"agent": "acceptance_gate"}],
                    "expanded_required_agents": ["backend_dev", "acceptance_gate"],
                    "required_modes": ["plan-eng-review", "review", "qa"],
                },
                "dev_results": {
                    "backend": {
                        "updated_files": [str(schema_path)],
                    }
                },
                "review_passed": True,
                "code_style_review_passed": True,
                "code_acceptance_passed": True,
                "runtime_qa_report": "runtime ok",
                "blocking_issues": [],
                "agent_mode_coverage": {
                    "required": ["plan-eng-review", "review", "qa"],
                    "executed": ["plan-eng-review", "review", "qa"],
                    "advisory": [],
                    "missing_required": [],
                    "all_required_executed": True,
                },
                "collaboration_trace_id": "trace-python-schema-criterion",
            }

            result = acceptance_gate_node(state)

            self.assertTrue(result["acceptance_passed"])
            self.assertIn("Python schema artifact", result["acceptance_report"])


if __name__ == "__main__":
    unittest.main()
