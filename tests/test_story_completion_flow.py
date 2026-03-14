from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git import Repo

from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.code_acceptance_agent import code_acceptance_node
from agentsystem.agents.code_style_reviewer_agent import code_style_review_node, route_after_code_style_review
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node, route_after_fix
from agentsystem.agents.review_agent import review_node, route_after_review
from agentsystem.agents.test_agent import _run_story_specific_validation


class StoryCompletionFlowTestCase(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
