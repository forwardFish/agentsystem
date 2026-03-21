from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git import Repo

from agentsystem.graph.dev_workflow import create_dev_graph


PROJECT_YAML = """name: versefina
stack:
  frontend:
    path: apps/web
  backend:
    path: apps/api
git:
  default_branch: main
  working_branch_prefix: "agent/"
"""

RULES_YAML = "{}\n"
COMMANDS_YAML = """lint:
  - python -c "print('lint ok')"
"""
REVIEW_POLICY_YAML = "{}\n"
CONTRACTS_YAML = "{}\n"
CLAUDE_MD = """# VerseFina Constitution

Follow existing code patterns first.
"""
STYLE_GUIDE_MD = """# Style Guide

Use existing structures before creating new ones.
"""

BACKEND_CONTENT = """from __future__ import annotations

from dataclasses import dataclass

from schemas.common import AcceptedResponse
from schemas.command import AgentRegisterRequest, HeartbeatRequest
from schemas.agent import AgentSnapshot, Position


@dataclass(slots=True)
class AgentRegistryService:
    default_world_id: str

    def register(self, payload: AgentRegisterRequest) -> AcceptedResponse:
        return AcceptedResponse(status="accepted", task_id=f"register::{payload.agent_id}")

    def heartbeat(self, agent_id: str, payload: HeartbeatRequest) -> AcceptedResponse:
        return AcceptedResponse(status="accepted", task_id=f"heartbeat::{agent_id}::{payload.heartbeat_at}")

    def snapshot(self, agent_id: str) -> AgentSnapshot:
        return AgentSnapshot(
            agent_id=agent_id,
            status="active",
            equity=105000.00,
            cash=50000.00,
            drawdown=0.05,
            tags=["trend", "swing"],
            positions=[Position(symbol="600519.SH", qty=100, avg_cost=1680.0)],
        )
"""

FRONTEND_CONTENT = """export default function Page() {
  return <div>Agent page</div>;
}
"""


class LangGraphWorkflowTestCase(unittest.TestCase):
    def test_workflow_runs_parallel_pipeline(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo_path = Path(tmp) / "versefina"
            self._create_repo_fixture(repo_path)

            graph = create_dev_graph()
            initial_state = {
                "user_requirement": "Render agent positions on the observation page.",
                "repo_b_path": str(repo_path),
                "branch_name": None,
                "current_step": "init",
                "subtasks": [],
                "dev_results": {},
                "backend_result": None,
                "frontend_result": None,
                "database_result": None,
                "devops_result": None,
                "generated_code_diff": None,
                "test_results": None,
                "security_report": None,
                "review_success": None,
                "review_passed": None,
                "review_dir": None,
                "blocking_issues": None,
                "important_issues": None,
                "nice_to_haves": None,
                "review_report": None,
                "code_acceptance_success": None,
                "code_acceptance_passed": None,
                "code_acceptance_report": None,
                "code_acceptance_dir": None,
                "code_acceptance_issues": None,
                "acceptance_success": None,
                "acceptance_passed": None,
                "acceptance_report": None,
                "acceptance_dir": None,
                "doc_result": None,
                "delivery_dir": None,
                "fix_result": None,
                "fix_attempts": 0,
                "error_message": None,
            }

            final_state = graph.invoke(initial_state)

            self.assertEqual(final_state["current_step"], "doc_done")
            self.assertEqual(len(final_state["subtasks"]), 2)
            self.assertEqual(final_state["subtasks"][0].type, "backend")
            self.assertEqual(final_state["subtasks"][1].type, "frontend")
            self.assertTrue(all(task.status == "completed" for task in final_state["subtasks"]))
            self.assertEqual(final_state["backend_result"], "Backend schema and mock snapshot updated.")
            self.assertEqual(final_state["frontend_result"], "Frontend development completed (constitution loaded).")
            self.assertIn("service.py", final_state["generated_code_diff"])
            self.assertIn("page.tsx", final_state["generated_code_diff"])
            self.assertIn("Lint: PASS", final_state["test_results"])
            self.assertIn("# Review Report", final_state["review_report"])
            self.assertIn("Story Delivery Report", final_state["doc_result"])
            self.assertIn("backend", final_state["dev_results"])
            self.assertIn("frontend", final_state["dev_results"])
            self.assertGreater(final_state["dev_results"]["frontend"]["constitution_length"], 0)
            self.assertEqual(final_state["dev_results"]["frontend"]["task_context_length"], 0)
            self.assertTrue(final_state["branch_name"].startswith("agent/parallel-dev-"))
            self.assertTrue(final_state["sync_merge_success"])
            self.assertTrue(final_state["pr_prep_success"])
            self.assertTrue(final_state["pr_prep_dir"].endswith("pr_prep"))
            self.assertIn("## Change Summary", final_state["pr_desc"])
            self.assertIn("feat(auto-dev):", final_state["commit_msg"])
            self.assertTrue(final_state["code_style_review_passed"])
            self.assertTrue(final_state["review_success"])
            self.assertTrue(final_state["review_passed"])
            self.assertTrue(final_state["review_dir"].endswith("review"))
            self.assertTrue(final_state["code_acceptance_success"])
            self.assertTrue(final_state["code_acceptance_passed"])
            self.assertTrue(final_state["code_acceptance_dir"].endswith("code_acceptance"))
            self.assertTrue(final_state["acceptance_passed"])
            self.assertTrue(final_state["acceptance_dir"].endswith("acceptance"))
            self.assertTrue(final_state["delivery_dir"].endswith("delivery"))

            frontend_content = (
                repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
            ).read_text(encoding="utf-8")
            self.assertIn("// Frontend Dev Agent was here (with Constitution loaded)", frontend_content)

            backend_content = (
                repo_path / "apps" / "api" / "src" / "domain" / "agent_registry" / "service.py"
            ).read_text(encoding="utf-8")
            self.assertIn('Position(symbol="000001.SZ", qty=300, avg_cost=12.45)', backend_content)
            self.assertNotIn("Target file:", backend_content)

            repo = Repo(repo_path)
            self.assertEqual(repo.active_branch.name, final_state["branch_name"])
            self.assertEqual(repo.head.commit.message.strip(), final_state["commit_msg"])

            pr_prep_dir = Path(final_state["pr_prep_dir"])
            self.assertTrue((pr_prep_dir / "pr_description.md").exists())
            self.assertTrue((pr_prep_dir / "commit_message.txt").exists())
            review_dir = Path(final_state["review_dir"])
            self.assertTrue((review_dir / "review_report.md").exists())
            code_acceptance_dir = Path(final_state["code_acceptance_dir"])
            self.assertTrue((code_acceptance_dir / "code_acceptance_report.md").exists())
            acceptance_dir = Path(final_state["acceptance_dir"])
            self.assertTrue((acceptance_dir / "acceptance_report.md").exists())
            delivery_dir = Path(final_state["delivery_dir"])
            self.assertTrue((delivery_dir / "story_delivery_report.md").exists())
            self.assertEqual(final_state["blocking_issues"], [])
            self.assertNotIn(".git/", final_state["review_report"])

    def test_workflow_runs_fixer_cycle_after_simulated_failure(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo_path = Path(tmp) / "versefina"
            self._create_repo_fixture(repo_path)

            graph = create_dev_graph()
            initial_state = {
                "user_requirement": "Fix the failing frontend observation page.",
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "给前端页面加一个有小错误的副标题，验证 Fixer 能自动修复",
                    "related_files": ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                    "test_failure_info": "TypeError: Cannot read property 'text' of undefined at line 42",
                },
                "branch_name": None,
                "auto_commit": False,
                "current_step": "init",
                "subtasks": [],
                "dev_results": {},
                "backend_result": None,
                "frontend_result": None,
                "database_result": None,
                "devops_result": None,
                "generated_code_diff": None,
                "test_results": None,
                "test_passed": None,
                "test_failure_info": None,
                "security_report": None,
                "review_success": None,
                "review_passed": None,
                "review_dir": None,
                "blocking_issues": None,
                "important_issues": None,
                "nice_to_haves": None,
                "review_report": None,
                "code_acceptance_success": None,
                "code_acceptance_passed": None,
                "code_acceptance_report": None,
                "code_acceptance_dir": None,
                "code_acceptance_issues": None,
                "acceptance_success": None,
                "acceptance_passed": None,
                "acceptance_report": None,
                "acceptance_dir": None,
                "doc_result": None,
                "delivery_dir": None,
                "fix_result": None,
                "fixer_needed": None,
                "fixer_success": None,
                "fix_attempts": 0,
                "error_message": None,
            }

            final_state = graph.invoke(initial_state)

            self.assertEqual(final_state["current_step"], "doc_done")
            self.assertEqual(final_state["fix_attempts"], 1)
            self.assertTrue(final_state["fixer_needed"])
            self.assertTrue(final_state["fixer_success"])
            self.assertTrue(final_state["test_passed"])
            self.assertIsNone(final_state["error_message"])
            self.assertIn("Applied automated remediation", final_state["fix_result"])
            self.assertTrue(final_state["sync_merge_success"])
            self.assertTrue(final_state["pr_prep_success"])
            self.assertTrue(final_state["review_success"])
            self.assertTrue(final_state["review_passed"])
            self.assertTrue(final_state["code_acceptance_passed"])

            frontend_content = (
                repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
            ).read_text(encoding="utf-8")
            self.assertIn("Fixed by Fix Agent after validation failure", frontend_content)

    def test_frontend_dev_infers_unquoted_subtitle_from_task_goal(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo_path = Path(tmp) / "versefina"
            self._create_repo_fixture(repo_path)

            graph = create_dev_graph()
            initial_state = {
                "user_requirement": "给前端页面加一个 Reviewer 测试副标题",
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "给前端页面加一个 Reviewer 测试副标题",
                    "acceptance_criteria": ["页面顶部有副标题"],
                    "related_files": ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                },
                "branch_name": None,
                "auto_commit": False,
                "current_step": "init",
                "subtasks": [],
                "dev_results": {},
                "backend_result": None,
                "frontend_result": None,
                "database_result": None,
                "devops_result": None,
                "generated_code_diff": None,
                "test_results": None,
                "test_passed": None,
                "test_failure_info": None,
                "security_report": None,
                "review_success": None,
                "review_passed": None,
                "review_dir": None,
                "blocking_issues": None,
                "important_issues": None,
                "nice_to_haves": None,
                "review_report": None,
                "code_acceptance_success": None,
                "code_acceptance_passed": None,
                "code_acceptance_report": None,
                "code_acceptance_dir": None,
                "code_acceptance_issues": None,
                "acceptance_success": None,
                "acceptance_passed": None,
                "acceptance_report": None,
                "acceptance_dir": None,
                "doc_result": None,
                "delivery_dir": None,
                "fix_result": None,
                "fixer_needed": None,
                "fixer_success": None,
                "fix_attempts": 0,
                "error_message": None,
            }

            final_state = graph.invoke(initial_state)

            self.assertEqual(final_state["current_step"], "doc_done")
            self.assertGreater(final_state["dev_results"]["frontend"]["task_context_length"], 0)
            frontend_content = (
                repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
            ).read_text(encoding="utf-8")
            self.assertIn("Reviewer 测试副标题", frontend_content)

    def _create_repo_fixture(self, repo_path: Path) -> None:
        (repo_path / ".agents").mkdir(parents=True)
        (repo_path / "apps" / "api" / "src" / "domain" / "agent_registry").mkdir(parents=True)
        (repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]").mkdir(parents=True)

        (repo_path / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
        (repo_path / ".agents" / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
        (repo_path / ".agents" / "rules.yaml").write_text(RULES_YAML, encoding="utf-8")
        (repo_path / ".agents" / "commands.yaml").write_text(COMMANDS_YAML, encoding="utf-8")
        (repo_path / ".agents" / "review_policy.yaml").write_text(REVIEW_POLICY_YAML, encoding="utf-8")
        (repo_path / ".agents" / "contracts.yaml").write_text(CONTRACTS_YAML, encoding="utf-8")
        (repo_path / ".agents" / "style_guide.md").write_text(STYLE_GUIDE_MD, encoding="utf-8")
        (repo_path / "apps" / "api" / "src" / "domain" / "agent_registry" / "service.py").write_text(
            BACKEND_CONTENT,
            encoding="utf-8",
        )
        (repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx").write_text(
            FRONTEND_CONTENT,
            encoding="utf-8",
        )

        repo = Repo.init(repo_path, initial_branch="main")
        repo.index.add(["."])
        with repo.config_writer() as config:
            config.set_value("user", "name", "Codex")
            config.set_value("user", "email", "codex@example.com")
        repo.index.commit("chore: seed fixture")


if __name__ == "__main__":
    unittest.main()
