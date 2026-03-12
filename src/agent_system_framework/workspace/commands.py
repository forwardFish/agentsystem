from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_system_framework.workspace.contracts import load_commands_config


@dataclass(frozen=True, slots=True)
class CommandResult:
    phase: str
    command: str
    returncode: int
    stdout: str
    stderr: str


class CommandExecutionError(RuntimeError):
    def __init__(self, result: CommandResult) -> None:
        super().__init__(f"phase {result.phase!r} failed with exit code {result.returncode}: {result.command}")
        self.result = result


class CommandExecutor:
    def __init__(self, target_repo: Path) -> None:
        self._target_repo = target_repo.resolve()

    def run_phase(self, phase: str, *, check: bool = True) -> list[CommandResult]:
        commands = load_commands_config(self._target_repo)
        if phase not in commands:
            raise KeyError(f"phase {phase!r} not found in .agents/commands.yaml")
        results: list[CommandResult] = []
        for command in commands[phase]:
            completed = subprocess.run(
                self._shell_command(command),
                cwd=self._target_repo,
                check=False,
                capture_output=True,
                text=True,
            )
            result = CommandResult(
                phase=phase,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            results.append(result)
            if check and result.returncode != 0:
                raise CommandExecutionError(result)
        return results

    def run_phases(self, phases: list[str], *, check: bool = True) -> dict[str, list[CommandResult]]:
        return {phase: self.run_phase(phase, check=check) for phase in phases}

    def _shell_command(self, command: str) -> list[str]:
        if os.name == "nt":
            return ["powershell", "-NoProfile", "-Command", command]
        return ["/bin/sh", "-lc", command]
