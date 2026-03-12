from __future__ import annotations

from pathlib import Path

from agentsystem.skills_runtime.command_exec import execute_command


def summarize_diff(repo_root: str | Path) -> str:
    success, output = execute_command(repo_root, "git show --stat --oneline HEAD")
    if not success:
        return "diff_unavailable"
    return output.strip() or "no_changes"
