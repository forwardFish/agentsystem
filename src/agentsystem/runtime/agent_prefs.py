from __future__ import annotations

from pathlib import Path


WORKSPACE_MAP = {
    "requirement": "requirement-agent-workspace",
    "dev": "dev-agent-workspace",
    "test": "test-agent-workspace",
    "review": "review-agent-workspace",
}


class AgentPrefs:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self.workspace_root = self.repo_root / "agent-workspaces"

    def get_workspace_dir(self, agent_type: str) -> Path:
        try:
            workspace_name = WORKSPACE_MAP[agent_type]
        except KeyError as exc:
            raise ValueError(f"Unknown agent type: {agent_type}") from exc
        path = self.workspace_root / workspace_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_memory_file(self, agent_type: str) -> Path:
        return self.get_workspace_dir(agent_type) / "MEMORY.md"

    def get_heartbeat_file(self, agent_type: str) -> Path:
        return self.get_workspace_dir(agent_type) / "HEARTBEAT.md"

    def get_agents_file(self, agent_type: str) -> Path:
        return self.get_workspace_dir(agent_type) / "AGENTS.md"
