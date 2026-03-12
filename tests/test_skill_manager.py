from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.skill_manager import SkillManager, SkillParser


class SkillManagerTestCase(unittest.TestCase):
    def test_parser_extracts_structured_fields(self) -> None:
        content = """
## 技能描述
用于修改单个文件

## 输入参数
- task_goal
- target_file

## 执行规则
- 只改一个文件

## 输出要求
- 输出完整代码

## 绝对禁止事项
- 不改其他文件
""".strip()

        skill = SkillParser().parse(content, "builder", "global")

        self.assertEqual(skill.name, "builder")
        self.assertEqual(skill.input_params, ["task_goal", "target_file"])
        self.assertIn("只改一个文件", skill.execution_rules)

    def test_manager_merges_global_project_and_task_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_a = root / "repo_a"
            repo_b = root / "repo_b"
            (repo_a / "skills").mkdir(parents=True)
            (repo_b / ".agents" / "skills").mkdir(parents=True)

            (repo_a / "skills" / "builder.skill.md").write_text(
                """
## 技能描述
全局规则

## 输入参数
- task_goal

## 执行规则
- 全局最小改动

## 输出要求
- 输出完整文件

## 绝对禁止事项
- 不得修改无关文件
""".strip(),
                encoding="utf-8",
            )
            (repo_b / ".agents" / "skills" / "builder.skill.md").write_text(
                """
## 技能描述
项目规则

## 输入参数
- current_code

## 执行规则
- 保持 Next.js 页面风格

## 输出要求
- 保留现有导入顺序

## 绝对禁止事项
- 不得新增依赖
""".strip(),
                encoding="utf-8",
            )

            task = {
                "goal": "给页面加标题",
                "constraints": ["只改一个文件"],
                "explicitly_not_doing": ["不改后端"],
                "related_files": ["apps/web/src/app/page.tsx"],
            }

            merged = SkillManager(repo_a, repo_b).get_final_skill("builder", task)

            self.assertIn("全局最小改动", merged.execution_rules)
            self.assertIn("保持 Next.js 页面风格", merged.execution_rules)
            self.assertIn("只改一个文件", merged.execution_rules)
            self.assertIn("不改后端", merged.forbidden_items)


if __name__ == "__main__":
    unittest.main()
