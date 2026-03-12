from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_system_framework.workspace.contracts import load_project_config
from agent_system_framework.workspace.git_tools import branch_exists, get_current_branch, run_git, working_tree_dirty


@dataclass(frozen=True, slots=True)
class BranchResult:
    previous_branch: str
    base_branch: str
    working_branch: str


class BranchManager:
    def __init__(self, target_repo: Path) -> None:
        self._target_repo = target_repo.resolve()

    def create_working_branch(
        self,
        change_slug: str,
        *,
        base_branch: str | None = None,
        prefix: str | None = None,
        timestamp: datetime | None = None,
    ) -> BranchResult:
        project = load_project_config(self._target_repo)
        resolved_base = base_branch or project.git["default_branch"]
        resolved_prefix = prefix or project.git["working_branch_prefix"]
        previous_branch = get_current_branch(self._target_repo)

        if previous_branch != resolved_base:
            if working_tree_dirty(self._target_repo):
                raise ValueError(
                    f"target repo is dirty on branch {previous_branch}; cannot safely switch to {resolved_base}"
                )
            run_git(self._target_repo, ["switch", resolved_base])

        branch_name = self._build_branch_name(resolved_prefix, change_slug, timestamp=timestamp)
        while branch_exists(self._target_repo, branch_name):
            branch_name = f"{branch_name}-1"

        run_git(self._target_repo, ["switch", "-c", branch_name])
        return BranchResult(previous_branch=previous_branch, base_branch=resolved_base, working_branch=branch_name)

    def push(self, branch_name: str, *, remote: str = "origin") -> None:
        run_git(self._target_repo, ["push", "--set-upstream", remote, branch_name])

    def _build_branch_name(self, prefix: str, change_slug: str, *, timestamp: datetime | None) -> str:
        normalized_slug = re.sub(r"[^a-z0-9]+", "-", change_slug.lower()).strip("-") or "change"
        stamp = (timestamp or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
        return f"{prefix}{normalized_slug}-{stamp}"
