from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class AgentIdentity:
    def __init__(self, agent_id: str, identity_root: str | Path):
        self.agent_id = agent_id
        self.root = Path(identity_root).resolve() / agent_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.agent_file = self.root / "AGENTS.md"
        self.memory_file = self.root / "MEMORY.md"
        self.policy_file = self.root / "policy.yaml"
        self.heartbeat_file = self.root / "HEARTBEAT.md"
        self._init_default_files()

    def _init_default_files(self) -> None:
        if not self.agent_file.exists():
            self.agent_file.write_text(
                f"# Agent {self.agent_id}\n\n## 基本信息\n- 角色：工程代理\n- 技能：代码、测试、审查\n",
                encoding="utf-8",
            )
        if not self.memory_file.exists():
            self.memory_file.write_text(f"# Agent {self.agent_id} 记忆\n\n## 长期记忆\n- 无\n", encoding="utf-8")
        if not self.policy_file.exists():
            self.policy_file.write_text(
                yaml.safe_dump(
                    {
                        "permissions": ["read_repo", "write_code", "run_tests"],
                        "limits": {"max_retry": 3, "max_task_concurrency": 1},
                    },
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
        if not self.heartbeat_file.exists():
            self.write_heartbeat("idle", "initialized")

    def load_identity(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "content": self.agent_file.read_text(encoding="utf-8"),
            "last_modified": self.agent_file.stat().st_mtime,
        }

    def read_memory(self) -> str:
        return self.memory_file.read_text(encoding="utf-8")

    def append_memory(self, content: str) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        with self.memory_file.open("a", encoding="utf-8") as handle:
            handle.write(f"\n### {timestamp}\n{content}\n")

    def write_heartbeat(self, status: str, message: str = "") -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        self.heartbeat_file.write_text(
            f"# Agent {self.agent_id} 心跳\n\n## 最后活跃时间\n- {timestamp}\n\n## 当前状态\n- {status}\n\n## 最新消息\n- {message}\n",
            encoding="utf-8",
        )

    def resolve_policy(self) -> dict[str, Any]:
        return yaml.safe_load(self.policy_file.read_text(encoding="utf-8"))
