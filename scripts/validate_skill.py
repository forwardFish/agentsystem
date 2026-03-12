from __future__ import annotations

import os
import re
from pathlib import Path


REQUIRED_HEADERS = [
    r"## 技能描述",
    r"## 输入参数",
    r"## 执行规则",
    r"## 输出要求",
]


def validate_skill_file(file_path: str | Path) -> bool:
    skill_file = Path(file_path).resolve()
    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"{skill_file} 读取失败: {exc}")
        return False

    missing = [pattern for pattern in REQUIRED_HEADERS if not re.search(pattern, content)]
    if missing:
        print(f"{skill_file} 验证失败: 缺失 {missing}")
        return False

    print(f"{skill_file} 验证通过")
    return True


def validate_all_skills(skills_dir: str | Path = "skills") -> dict[str, bool]:
    results: dict[str, bool] = {}
    skills_path = Path(skills_dir).resolve()
    if not skills_path.exists():
        print(f"Skill目录不存在: {skills_path}")
        return results

    for root, _, files in os.walk(skills_path):
        for file_name in files:
            if file_name.endswith(".skill.md"):
                file_path = Path(root) / file_name
                results[str(file_path)] = validate_skill_file(file_path)

    return results


if __name__ == "__main__":
    validate_all_skills()
