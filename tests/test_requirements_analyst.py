from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.requirements_analyst_agent import RequirementsAnalystAgent
from agentsystem.agents.requirement_agent import requirement_analysis_node


class RequirementsAnalystAgentTestCase(unittest.TestCase):
    def test_analyze_generates_sprint_plan_and_story_cards(self) -> None:
        repo_b_path = Path("D:/lyh/agent/agent-frame/versefina").resolve()
        requirement = (
            "给versefina的web前端做一个用户个人中心，包括页面标题和骨架、"
            "用户头像昵称展示、我的订单入口卡片、设置入口按钮。"
            "只做前端，不动后端API，必须复用现有组件。"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tasks_root = Path(tmp) / "tasks"
            agent = RequirementsAnalystAgent(repo_b_path, tasks_root)
            result = agent.analyze(requirement, "1")

            sprint_dir = tasks_root / "sprint_1"
            self.assertTrue(sprint_dir.exists())
            self.assertTrue((sprint_dir / "sprint_plan.md").exists())
            self.assertTrue((sprint_dir / "execution_order.txt").exists())
            self.assertEqual(len(result["story_cards"]), 4)

            for card in result["story_cards"]:
                self.assertIn(card["blast_radius"], {"L1", "L2"})
                self.assertTrue(card["primary_files"])
                self.assertTrue(card["related_files"])
                self.assertNotIn("不动后端API", card["goal"])
                self.assertNotIn("必须复用现有组件", card["goal"])

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


if __name__ == "__main__":
    unittest.main()
