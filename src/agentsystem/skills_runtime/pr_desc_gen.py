from __future__ import annotations

from pathlib import Path

from agentsystem.skills_runtime.command_exec import execute_command


def get_pending_prs(repo_root: str | Path) -> list[str]:
    success, branch = execute_command(repo_root, "git branch --show-current")
    if not success:
        return []
    branch_name = branch.strip()
    if branch_name and branch_name != "main":
        return [branch_name]
    return []
