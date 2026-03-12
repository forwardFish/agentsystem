from __future__ import annotations

from pathlib import Path

from agentsystem.adapters.shell_executor import ShellExecutor


def execute_command(repo_root: str | Path, command: str) -> tuple[bool, str]:
    return ShellExecutor(Path(repo_root).resolve()).run_command(command)
