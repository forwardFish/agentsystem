from __future__ import annotations

import os
import subprocess
from pathlib import Path


class ShellExecutor:
    def __init__(self, work_dir: str | Path):
        self.work_dir = Path(work_dir).resolve()

    def run_command(self, command: str) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "PYTHONUTF8": "1",
                },
                timeout=300,
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            return success, output
        except Exception as exc:  # pragma: no cover - defensive path
            return False, f"命令执行异常: {exc}"

    def run_commands(self, commands: list[str]) -> tuple[bool, str]:
        for command in commands:
            success, output = self.run_command(command)
            if not success:
                return False, f"命令执行失败: {command}\n错误信息: {output}"
        return True, "所有命令执行成功"
