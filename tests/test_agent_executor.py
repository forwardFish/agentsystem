from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.agent_executor import AgentExecutor
from agentsystem.adapters.skill_manager import SkillManager


class AgentExecutorTestCase(unittest.TestCase):
    def test_verifier_executes_configured_format_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_a = root / "repo_a"
            repo_b = root / "repo_b"
            (repo_a / "skills").mkdir(parents=True)
            repo_b.mkdir(parents=True)

            for name in ("builder", "reviewer", "verifier", "planner"):
                (repo_a / "skills" / f"{name}.skill.md").write_text(
                    """
## 技能描述
test

## 输入参数
- one

## 执行规则
- only configured commands

## 输出要求
- structured output

## 绝对禁止事项
- none
""".strip(),
                    encoding="utf-8",
                )

            target = repo_b / "demo.tsx"
            target.write_text("export default function Demo() {}\n", encoding="utf-8")

            executor = AgentExecutor(SkillManager(repo_a, repo_b))
            result = executor.execute_verifier(
                task_yaml={"goal": "format file", "related_files": ["demo.tsx"]},
                commands={"format": ['python -c "print(\'ok\')"']},
                target_file=target,
            )

            self.assertEqual(result["final_status"], "passed")
            self.assertEqual(len(result["commands"]), 1)
            self.assertTrue(result["commands"][0]["success"])


if __name__ == "__main__":
    unittest.main()
