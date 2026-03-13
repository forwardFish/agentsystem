from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from click.testing import CliRunner

from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.requirements_analyst_agent import RequirementsAnalystAgent
from agentsystem.core.task_card import TaskCard
from cli import cli


FINANCE_REQUIREMENT = """
给 versefina 做一个 Agent-native 金融世界 MVP：
1. 先完成契约、状态机和基础存储
2. 支持交割单上传、解析、生成 Agent profile
3. 支持世界状态、撮合、账本、daily loop
4. 支持 dashboard 只读观察台和 OpenClaw-first 接入
""".strip()


class RequirementsAnalystAgentTestCase(unittest.TestCase):
    def test_analyze_generates_backlog_v1_structure(self) -> None:
        repo_b_path = Path("D:/lyh/agent/agent-frame/versefina").resolve()

        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp) / "tasks"
            agent = RequirementsAnalystAgent(repo_b_path, tasks_root)
            result = agent.analyze(FINANCE_REQUIREMENT, prefix="backlog_v1")

            backlog_root = tasks_root / "backlog_v1"
            self.assertTrue(backlog_root.exists())
            self.assertTrue((backlog_root / "sprint_overview.md").exists())
            self.assertTrue((backlog_root / "backlog_v2.md").exists())

            sprint_dir = backlog_root / "sprint_0_contract_foundation"
            self.assertTrue((sprint_dir / "sprint_plan.md").exists())
            self.assertTrue((sprint_dir / "execution_order.txt").exists())
            self.assertTrue((sprint_dir / "epic_0_1_platform_contract.md").exists())
            self.assertTrue((sprint_dir / "epic_0_1_platform_contract").exists())
            self.assertTrue((backlog_root / "sprint_4_agent_gallery_population").exists())

            story_files = list(backlog_root.rglob("S0-001_*.yaml"))
            self.assertEqual(len(story_files), 1)
            payload = yaml.safe_load(story_files[0].read_text(encoding="utf-8"))
            validated = TaskCard.model_validate(payload)

            self.assertEqual(validated.story_id, "S0-001")
            self.assertEqual(validated.epic, "Epic 0.1 平台契约")
            self.assertTrue(validated.business_value)
            self.assertTrue(validated.entry_criteria)
            self.assertTrue(validated.out_of_scope)
            self.assertTrue(validated.dependencies)
            self.assertIn("normal", validated.test_cases)
            self.assertIn("exception", validated.test_cases)
            self.assertGreaterEqual(len(result["story_cards"]), 50)

    def test_requirement_node_parses_story_card_fields(self) -> None:
        state = {
            "user_requirement": "给个人中心页面加标题",
            "task_payload": {
                "goal": "给个人中心页面加标题和基础骨架",
                "acceptance_criteria": ["页面顶部显示个人中心标题", "页面通过 prettier 格式化"],
                "constraints": ["必须复用现有布局组件"],
                "primary_files": ["apps/web/src/app/(dashboard)/onboarding/page.tsx"],
                "secondary_files": ["apps/web/src/app/(dashboard)/layout.tsx"],
                "not_do": ["不新增后端 API"],
            },
        }

        updated = requirement_analysis_node(state)

        self.assertEqual(updated["parsed_goal"], "给个人中心页面加标题和基础骨架")
        self.assertEqual(updated["primary_files"], ["apps/web/src/app/(dashboard)/onboarding/page.tsx"])
        self.assertEqual(updated["secondary_files"], ["apps/web/src/app/(dashboard)/layout.tsx"])
        self.assertEqual(updated["parsed_not_do"], ["不新增后端 API"])
        self.assertTrue(updated["subtasks"])

    def test_split_requirement_cli_creates_backlog_v1(self) -> None:
        runner = CliRunner()
        backlog_root = Path("D:/lyh/agent/agent-frame/agentsystem/tasks") / "backlog_test"
        shutil.rmtree(backlog_root, ignore_errors=True)
        with tempfile.TemporaryDirectory() as tmp:
            requirement_file = Path(tmp) / "requirement.md"
            requirement_file.write_text(FINANCE_REQUIREMENT, encoding="utf-8")
            result = runner.invoke(
                cli,
                ["split_requirement", "--requirement-file", str(requirement_file), "--env", "test", "--prefix", "backlog_test"],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Requirement split completed", result.output)
            self.assertTrue(backlog_root.exists())
            self.assertTrue((backlog_root / "sprint_4_agent_gallery_population").exists())
        shutil.rmtree(backlog_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
