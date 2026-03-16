from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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

    def build_task_context(self, task_payload: dict[str, Any] | None) -> str:
        if not task_payload:
            return ""

        context_parts: list[str] = []
        goal = str(task_payload.get("goal", "")).strip()
        acceptance = task_payload.get("acceptance_criteria", [])
        story_inputs = task_payload.get("story_inputs", [])
        story_process = task_payload.get("story_process", [])
        story_outputs = task_payload.get("story_outputs", [])
        verification_basis = task_payload.get("verification_basis", [])
        constraints = task_payload.get("constraints", [])
        related_files = [str(path) for path in task_payload.get("related_files", [])]

        context_parts.append("# Task Card")
        context_parts.append(f"Goal: {goal or 'n/a'}")
        context_parts.append(f"Acceptance Criteria: {json.dumps(acceptance, ensure_ascii=False)}")
        context_parts.append(f"Story Inputs: {json.dumps(story_inputs, ensure_ascii=False)}")
        context_parts.append(f"Story Process: {json.dumps(story_process, ensure_ascii=False)}")
        context_parts.append(f"Story Outputs: {json.dumps(story_outputs, ensure_ascii=False)}")
        context_parts.append(f"Verification Basis: {json.dumps(verification_basis, ensure_ascii=False)}")
        context_parts.append(f"Constraints: {json.dumps(constraints, ensure_ascii=False)}")
        context_parts.append("")

        if related_files:
            context_parts.append("# Related Files")
            for raw_path in related_files:
                candidate = self.repo_b_root / raw_path
                context_parts.append(f"## {raw_path}")
                if candidate.exists():
                    context_parts.append("```")
                    context_parts.append(candidate.read_text(encoding="utf-8"))
                    context_parts.append("```")
                else:
                    context_parts.append("(missing)")
            context_parts.append("")

        focused_tree = self._build_focused_tree(related_files)
        if focused_tree:
            context_parts.append("# Focused Project Tree")
            context_parts.extend(focused_tree)

        return "\n".join(context_parts).strip()

    def _build_focused_tree(self, related_files: list[str]) -> list[str]:
        roots: set[Path] = set()
        for raw_path in related_files:
            normalized = Path(raw_path)
            if normalized.parts[:2] == ("apps", "web"):
                roots.add(self.repo_b_root / "apps" / "web" / "src")
            elif normalized.parts[:2] == ("apps", "api"):
                roots.add(self.repo_b_root / "apps" / "api" / "src")

        lines: list[str] = []
        for root in sorted(roots):
            if not root.exists():
                continue
            lines.append(str(root.relative_to(self.repo_b_root)))
            for child in sorted(root.iterdir()):
                lines.append(f"- {child.relative_to(self.repo_b_root)}")
        return lines
