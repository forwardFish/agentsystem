from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


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
            raise FileNotFoundError(f"Repo B 的 .agents 目录不存在: {self.agents_dir}")
        return RepoBConfig(
            project=self._load_yaml("project.yaml"),
            rules=self._load_yaml("rules.yaml"),
            commands=self._load_yaml("commands.yaml"),
            review_policy=self._load_yaml("review_policy.yaml"),
            contracts=self._load_yaml("contracts.yaml"),
        )

    def _load_yaml(self, filename: str) -> dict[str, Any]:
        file_path = self.agents_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        return yaml.safe_load(file_path.read_text(encoding="utf-8"))
