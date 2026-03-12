from __future__ import annotations

import re
from pathlib import Path


REQUIRED_HEADERS = [
    r"## 技能描述",
    r"## 输入参数",
    r"## 执行规则",
    r"## 输出要求",
    r"## 绝对禁止事项",
]


def validate_skill_file(file_path: str | Path) -> bool:
    skill_file = Path(file_path).resolve()
    content = skill_file.read_text(encoding="utf-8")
    return all(re.search(pattern, content) for pattern in REQUIRED_HEADERS)


def validate_all_skills(root: str | Path) -> bool:
    skill_root = Path(root).resolve()
    results = [validate_skill_file(skill_file) for skill_file in skill_root.glob("*.skill.md")]
    return all(results) if results else True
