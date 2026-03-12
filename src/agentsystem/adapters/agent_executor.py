from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.adapters.skill_manager import SkillManager
from agentsystem.llm.client import get_llm


class AgentExecutor:
    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager
        self.llm = get_llm()

    def execute_builder(self, task_yaml: dict[str, Any], current_code: str, constitution: str) -> str:
        builder_skill = self.skill_manager.get_final_skill("builder", task_yaml)
        target_files = task_yaml.get("related_files") or task_yaml.get("target_files") or []

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
你是 Builder Agent，必须严格遵守以下全部规则。

## 执行规则
{execution_rules}

## 输出要求
{output_requirements}

## 绝对禁止事项
{forbidden_items}

## 项目专属规则
{custom_rules}

## 项目宪法
{constitution}
""".strip(),
                ),
                (
                    "user",
                    """
任务目标：
{task_goal}

约束条件：
{task_constraints}

目标文件：
{target_file}

当前文件内容：
```tsx
{current_code}
```

请只输出修改后的完整文件内容，并放在单个 ```tsx 代码块中。
""".strip(),
                ),
            ]
        )

        response = (prompt | self.llm).invoke(
            {
                "execution_rules": builder_skill.execution_rules,
                "output_requirements": builder_skill.output_requirements,
                "forbidden_items": builder_skill.forbidden_items,
                "custom_rules": builder_skill.custom_rules,
                "constitution": constitution,
                "task_goal": task_yaml["goal"],
                "task_constraints": "\n".join(f"- {item}" for item in task_yaml.get("constraints", [])),
                "target_file": target_files[0] if target_files else "",
                "current_code": current_code,
            }
        )
        return response.content if hasattr(response, "content") else str(response)

    def execute_reviewer(self, task_yaml: dict[str, Any], old_code: str, new_code: str) -> str:
        reviewer_skill = self.skill_manager.get_final_skill("reviewer", task_yaml)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
你是 Reviewer Agent，只做审查，不做代码修改。

## 执行规则
{execution_rules}

## 输出要求
{output_requirements}

## 绝对禁止事项
{forbidden_items}
""".strip(),
                ),
                (
                    "user",
                    """
任务目标：
{task_goal}

原始代码：
```tsx
{old_code}
```

修改后代码：
```tsx
{new_code}
```
""".strip(),
                ),
            ]
        )
        response = (prompt | self.llm).invoke(
            {
                "execution_rules": reviewer_skill.execution_rules,
                "output_requirements": reviewer_skill.output_requirements,
                "forbidden_items": reviewer_skill.forbidden_items,
                "task_goal": task_yaml["goal"],
                "old_code": old_code,
                "new_code": new_code,
            }
        )
        return response.content if hasattr(response, "content") else str(response)

    def execute_verifier(self, task_yaml: dict[str, Any], commands: dict[str, list[str]], target_file: Path) -> dict[str, Any]:
        verifier_skill = self.skill_manager.get_final_skill("verifier", task_yaml)
        del verifier_skill

        suffix = target_file.suffix.lower()
        format_commands = list(commands.get("format", []))
        if suffix in {".ts", ".tsx", ".js", ".jsx"}:
            selected_commands = [
                command
                for command in format_commands
                if any(token in command.lower() for token in ("prettier", "eslint", "pnpm", "python"))
            ]
        elif suffix == ".py":
            selected_commands = [
                command
                for command in format_commands
                if any(token in command.lower() for token in ("black", "ruff", "python"))
            ]
        else:
            selected_commands = format_commands
        selected_commands = selected_commands or format_commands

        shell = ShellExecutor(self.skill_manager.repo_b)
        results: list[dict[str, Any]] = []
        final_status = "passed"
        for command in selected_commands:
            success, output = shell.run_command(command)
            results.append(
                {
                    "command": command,
                    "success": success,
                    "output_preview": output[:300],
                }
            )
            if not success:
                final_status = "failed"

        return {
            "commands": results,
            "final_status": final_status,
        }
