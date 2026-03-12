from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from dotenv import load_dotenv


class RepoBConfig(BaseModel):
    project: dict[str, Any]
    rules: dict[str, Any]
    commands: dict[str, Any]
    review_policy: dict[str, Any]
    contracts: dict[str, Any]


class RepoBConfigReader:
    def __init__(self, repo_b_path: str | Path):
        self.repo_b_root = Path(repo_b_path).resolve()
        self.agents_dir = self.repo_b_root / ".agents"

    def load_all_config(self) -> RepoBConfig:
        if not self.agents_dir.exists():
            raise FileNotFoundError(f"Repo B .agents directory does not exist: {self.agents_dir}")

        commands_payload = self._load_yaml("commands.yaml")
        return RepoBConfig(
            project=self._load_yaml("project.yaml"),
            rules=self._load_yaml("rules.yaml"),
            commands=self._normalize_commands(commands_payload),
            review_policy=self._load_yaml("review_policy.yaml"),
            contracts=self._load_yaml("contracts.yaml"),
        )

    def load_commands(self) -> dict[str, Any]:
        return self._normalize_commands(self._load_yaml("commands.yaml"))

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        file_path = self.agents_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {file_path}")

        payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{file_path} must contain a mapping")
        return payload

    def _normalize_commands(self, payload: dict[str, Any]) -> dict[str, Any]:
        commands_payload = payload.get("commands", payload)
        if not isinstance(commands_payload, dict):
            raise ValueError("commands.yaml must contain a mapping or a top-level 'commands' mapping")

        normalized: dict[str, Any] = {}
        for phase, values in commands_payload.items():
            if not isinstance(phase, str):
                raise ValueError("command phase names must be strings")
            if phase == "start":
                normalized[phase] = values
                continue
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"commands for phase {phase!r} must be a list of strings")
            normalized[phase] = list(values)
        return normalized


class SystemConfigReader:
    def __init__(self) -> None:
        load_dotenv()

    def load(self, config_path: str | Path) -> dict[str, Any]:
        config_file = Path(config_path).resolve()
        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{config_file} must contain a mapping")
        return self._replace_env_vars(payload)

    def _replace_env_vars(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: self._replace_env_vars(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._replace_env_vars(item) for item in data]
        if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            import os

            return os.getenv(data[2:-1], "")
        return data
