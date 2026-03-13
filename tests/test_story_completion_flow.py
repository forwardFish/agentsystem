from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git import Repo

from agentsystem.agents.code_acceptance_agent import code_acceptance_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node
from agentsystem.agents.review_agent import review_node, route_after_review
from agentsystem.agents.test_agent import _run_story_specific_validation


class StoryCompletionFlowTestCase(unittest.TestCase):
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
                "test_passed": True,
                "review_passed": True,
                "code_acceptance_passed": True,
                "acceptance_passed": True,
                "test_results": "StoryValidation: PASS",
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


if __name__ == "__main__":
    unittest.main()
