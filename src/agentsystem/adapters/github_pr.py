from __future__ import annotations

import requests


class GitHubPullRequestAdapter:
    def __init__(self, *, token: str, owner: str, repo_name: str):
        self._token = token
        self._owner = owner
        self._repo_name = repo_name

    def create_pull_request(self, *, title: str, body: str, head_branch: str, base_branch: str) -> str:
        url = f"https://api.github.com/repos/{self._owner}/{self._repo_name}/pulls"
        headers = {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 201:
            raise RuntimeError(f"GitHub API 错误: {response.status_code} {response.text}")
        return response.json()["html_url"]
