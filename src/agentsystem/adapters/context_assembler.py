from __future__ import annotations

from pathlib import Path


class ContextAssembler:
    """
    Assemble Repo B guidance files so every agent can consume the same project constitution.
    """

    def __init__(self, repo_b_path: str | Path):
        self.repo_b_root = Path(repo_b_path).resolve()
        self.agents_dir = self.repo_b_root / ".agents"

    def build_constitution(self) -> str:
        constitution_parts: list[str] = []

        agents_file = self.repo_b_root / "AGENTS.md"
        if agents_file.exists():
            constitution_parts.append("=" * 40)
            constitution_parts.append("Execution Rules (AGENTS.md)")
            constitution_parts.append("=" * 40)
            constitution_parts.append(agents_file.read_text(encoding="utf-8"))
            constitution_parts.append("\n" + "=" * 40 + "\n")

        claude_file = self.repo_b_root / "CLAUDE.md"
        if claude_file.exists():
            constitution_parts.append("=" * 40)
            constitution_parts.append("Project Constitution (CLAUDE.md)")
            constitution_parts.append("=" * 40)
            constitution_parts.append(claude_file.read_text(encoding="utf-8"))
            constitution_parts.append("\n" + "=" * 40 + "\n")

        style_file = self.agents_dir / "style_guide.md"
        if style_file.exists():
            constitution_parts.append("Code Style Guide")
            constitution_parts.append("-" * 30)
            constitution_parts.append(style_file.read_text(encoding="utf-8"))
            constitution_parts.append("\n" + "-" * 30 + "\n")

        project_file = self.agents_dir / "project.yaml"
        if project_file.exists():
            constitution_parts.append("Project Configuration")
            constitution_parts.append(project_file.read_text(encoding="utf-8"))

        return "\n".join(constitution_parts)
