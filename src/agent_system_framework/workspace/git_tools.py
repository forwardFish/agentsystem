from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitHubRepository:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


def run_git(repo_root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
    )


def get_current_branch(repo_root: Path) -> str:
    return run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def get_remote_url(repo_root: Path, remote: str = "origin") -> str:
    return run_git(repo_root, ["remote", "get-url", remote]).stdout.strip()


def branch_exists(repo_root: Path, branch_name: str) -> bool:
    result = run_git(repo_root, ["show-ref", "--verify", f"refs/heads/{branch_name}"], check=False)
    return result.returncode == 0


def working_tree_dirty(repo_root: Path) -> bool:
    return bool(run_git(repo_root, ["status", "--short"]).stdout.strip())


def parse_github_repository(remote_url: str) -> GitHubRepository:
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<name>[^/.]+?)(?:\.git)?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<name>[^/.]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<name>[^/.]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            return GitHubRepository(owner=match.group("owner"), name=match.group("name"))
    raise ValueError(f"unsupported GitHub remote url: {remote_url}")
