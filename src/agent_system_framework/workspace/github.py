from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import request

from agent_system_framework.workspace.git_tools import GitHubRepository, get_remote_url, parse_github_repository


@dataclass(frozen=True, slots=True)
class PullRequestResult:
    repository: str
    number: int | None
    url: str
    head_branch: str
    base_branch: str


class GitHubPullRequestManager:
    def __init__(self, target_repo: Path) -> None:
        self._target_repo = target_repo.resolve()

    def resolve_repository(self, remote: str = "origin") -> GitHubRepository:
        return parse_github_repository(get_remote_url(self._target_repo, remote))

    def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        remote: str = "origin",
        draft: bool = False,
        token: str | None = None,
    ) -> PullRequestResult:
        repository = self.resolve_repository(remote)
        resolved_token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if resolved_token:
            return self._create_via_api(
                repository=repository,
                title=title,
                body=body,
                head_branch=head_branch,
                base_branch=base_branch,
                draft=draft,
                token=resolved_token,
            )
        return self._create_via_gh(
            repository=repository,
            title=title,
            body=body,
            head_branch=head_branch,
            base_branch=base_branch,
            draft=draft,
        )

    def _create_via_api(
        self,
        *,
        repository: GitHubRepository,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool,
        token: str,
    ) -> PullRequestResult:
        url = f"https://api.github.com/repos/{repository.slug}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
        }
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "agent-system-framework",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        with request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
        return PullRequestResult(
            repository=repository.slug,
            number=data.get("number"),
            url=data["html_url"],
            head_branch=head_branch,
            base_branch=base_branch,
        )

    def _create_via_gh(
        self,
        *,
        repository: GitHubRepository,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool,
    ) -> PullRequestResult:
        if shutil.which("gh") is None:
            raise RuntimeError("GitHub CLI is not available and no GITHUB_TOKEN/GH_TOKEN was provided")
        command = [
            "gh",
            "pr",
            "create",
            "--repo",
            repository.slug,
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body",
            body,
        ]
        if draft:
            command.append("--draft")
        completed = subprocess.run(command, cwd=self._target_repo, check=True, capture_output=True, text=True)
        url_match = re.search(r"https://github\.com/\S+", completed.stdout)
        if url_match is None:
            raise RuntimeError("gh pr create did not return a pull request url")
        return PullRequestResult(
            repository=repository.slug,
            number=None,
            url=url_match.group(0),
            head_branch=head_branch,
            base_branch=base_branch,
        )
