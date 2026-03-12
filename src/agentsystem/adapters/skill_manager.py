from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    name: str
    type: str
    description: str
    input_params: list[str]
    execution_rules: str
    output_requirements: str
    forbidden_items: str
    priority: int
    custom_rules: str = ""


class SkillParser:
    def __init__(self) -> None:
        self.patterns = {
            "description": re.compile(r"## 技能描述\s*([\s\S]*?)(?=\n## |\Z)"),
            "input_params": re.compile(r"## 输入参数\s*([\s\S]*?)(?=\n## |\Z)"),
            "execution_rules": re.compile(r"## 执行规则\s*([\s\S]*?)(?=\n## |\Z)"),
            "output_requirements": re.compile(r"## 输出要求\s*([\s\S]*?)(?=\n## |\Z)"),
            "forbidden_items": re.compile(r"## 绝对禁止事项\s*([\s\S]*?)(?=\n## |\Z)"),
            "custom_rules": re.compile(r"## 专属编码规则\s*([\s\S]*?)(?=\n## |\Z)"),
        }

    def parse(self, md_content: str, skill_name: str, skill_type: str) -> Skill:
        return Skill(
            name=skill_name,
            type=skill_type,
            description=self._extract_field(md_content, "description"),
            input_params=self._extract_params(md_content),
            execution_rules=self._extract_field(md_content, "execution_rules"),
            output_requirements=self._extract_field(md_content, "output_requirements"),
            forbidden_items=self._extract_field(md_content, "forbidden_items"),
            custom_rules=self._extract_field(md_content, "custom_rules"),
            priority={"global": 1, "project": 2, "task": 3}[skill_type],
        )

    def _extract_field(self, content: str, field_name: str) -> str:
        match = self.patterns[field_name].search(content)
        return match.group(1).strip() if match else ""

    def _extract_params(self, content: str) -> list[str]:
        raw = self._extract_field(content, "input_params")
        params: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("-"):
                value = stripped[1:].strip()
                if value:
                    params.append(value)
        return params


class SkillRegistry:
    def __init__(self) -> None:
        self.skill_pool: dict[str, dict[str, Skill]] = {}

    def register_skill(self, skill: Skill) -> None:
        self.skill_pool.setdefault(skill.name, {})[skill.type] = skill

    def get_merged_skill(self, skill_name: str) -> Skill:
        if skill_name not in self.skill_pool:
            raise ValueError(f"Skill not found: {skill_name}")

        ordered = sorted(self.skill_pool[skill_name].values(), key=lambda item: item.priority)
        merged = Skill(
            name=skill_name,
            type="merged",
            description="",
            input_params=[],
            execution_rules="",
            output_requirements="",
            forbidden_items="",
            priority=3,
            custom_rules="",
        )

        for skill in ordered:
            merged.description = self._append_block(merged.description, skill.description)
            merged.input_params = self._merge_params(merged.input_params, skill.input_params)
            merged.execution_rules = self._append_block(merged.execution_rules, skill.execution_rules)
            merged.output_requirements = self._append_block(merged.output_requirements, skill.output_requirements)
            merged.forbidden_items = self._append_block(merged.forbidden_items, skill.forbidden_items)
            merged.custom_rules = self._append_block(merged.custom_rules, skill.custom_rules)

        return merged

    def _append_block(self, base: str, extra: str) -> str:
        if not extra:
            return base
        if not base:
            return extra.strip()
        return f"{base.strip()}\n---\n{extra.strip()}"

    def _merge_params(self, base: list[str], extra: list[str]) -> list[str]:
        merged = list(base)
        for param in extra:
            if param not in merged:
                merged.append(param)
        return merged


class SkillManager:
    def __init__(self, repo_a_path: str | Path, repo_b_path: str | Path):
        self.repo_a = Path(repo_a_path).resolve()
        self.repo_b = Path(repo_b_path).resolve()
        self.parser = SkillParser()

    def get_final_skill(self, skill_name: str, task_yaml: dict[str, Any] | None = None) -> Skill:
        registry = SkillRegistry()
        self._load_global_skill(skill_name, registry)
        self._load_project_skill(skill_name, registry)
        if task_yaml:
            registry.register_skill(self._build_task_skill(skill_name, task_yaml))
        return registry.get_merged_skill(skill_name)

    def _load_global_skill(self, skill_name: str, registry: SkillRegistry) -> None:
        skill_file = self.repo_a / "skills" / f"{skill_name}.skill.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Global skill file is missing: {skill_file}")
        content = skill_file.read_text(encoding="utf-8")
        registry.register_skill(self.parser.parse(content, skill_name, "global"))

    def _load_project_skill(self, skill_name: str, registry: SkillRegistry) -> None:
        skill_file = self.repo_b / ".agents" / "skills" / f"{skill_name}.skill.md"
        if not skill_file.exists():
            return
        content = skill_file.read_text(encoding="utf-8")
        registry.register_skill(self.parser.parse(content, skill_name, "project"))

    def _build_task_skill(self, skill_name: str, task_yaml: dict[str, Any]) -> Skill:
        target_files = task_yaml.get("related_files") or task_yaml.get("target_files") or []
        task_lines = [
            "## 技能描述",
            str(task_yaml.get("goal", "")).strip(),
            "",
            "## 输入参数",
            "- task_goal",
            "- task_constraints",
            "- target_file",
            "",
            "## 执行规则",
            f"仅处理以下文件：{', '.join(target_files)}",
        ]
        for item in task_yaml.get("constraints", []):
            task_lines.append(f"- {item}")
        task_lines.extend(
            [
                "",
                "## 输出要求",
                "- 输出内容必须满足本次任务验收标准",
                "- 不允许擅自扩大改动范围",
                "",
                "## 绝对禁止事项",
            ]
        )
        for item in task_yaml.get("explicitly_not_doing", []):
            task_lines.append(f"- {item}")
        return self.parser.parse("\n".join(task_lines), skill_name, "task")
