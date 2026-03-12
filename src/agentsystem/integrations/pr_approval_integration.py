from __future__ import annotations

import os
from pathlib import Path

import requests
import yaml

from agentsystem.orchestration.task_state_machine import TaskState, TaskStatus


class PRApprovalClient:
    def __init__(self, token: str, owner: str, repo: str):
        self.base_url = "https://api.github.com"
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def create_pr(self, task_id: str, head_branch: str, base_branch: str = "main") -> int:
        response = requests.post(
            f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls",
            headers=self.headers,
            json={
                "title": f"Task {task_id}: 自动开发变更",
                "head": head_branch,
                "base": base_branch,
                "body": f"任务ID：{task_id}\n由 Agent 自动提交，等待审批",
            },
            timeout=30,
        )
        response.raise_for_status()
        return int(response.json()["number"])

    def get_pr_approval_status(self, pr_number: int) -> dict[str, bool]:
        reviews = requests.get(
            f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews",
            headers=self.headers,
            timeout=30,
        )
        reviews.raise_for_status()
        review_items = reviews.json()
        approved = any(item["state"] == "APPROVED" for item in review_items)
        rejected = any(item["state"] == "CHANGES_REQUESTED" for item in review_items)

        pull = requests.get(
            f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_number}",
            headers=self.headers,
            timeout=30,
        )
        pull.raise_for_status()
        mergeable = bool(pull.json().get("mergeable", False))
        return {"approved": approved, "rejected": rejected, "mergeable": mergeable}

    def merge_pr(self, pr_number: int) -> bool:
        response = requests.put(
            f"{self.base_url}/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge",
            headers=self.headers,
            timeout=30,
        )
        return response.status_code == 200


def approval_node_with_pr(state: TaskState) -> TaskState:
    token = os.getenv("GITHUB_TOKEN")
    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO_B_NAME")
    if not token or not owner or not repo:
        state.status = TaskStatus.GATED
        state.approval_result = {"approved": False, "rejected": False, "mergeable": False}
        return state

    client = PRApprovalClient(token=token, owner=owner, repo=repo)
    worktree_path = Path(state.worktree_path).resolve()
    task_yaml_path = worktree_path.parent / ".meta" / worktree_path.name / "task.yaml"
    task_yaml = yaml.safe_load(task_yaml_path.read_text(encoding="utf-8"))
    pr_number = task_yaml.get("pr_number")
    if not pr_number:
        pr_number = client.create_pr(task_id=state.task_id, head_branch=task_yaml["branch"])
        task_yaml["pr_number"] = pr_number
        task_yaml_path.write_text(
            yaml.safe_dump(task_yaml, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    approval_status = client.get_pr_approval_status(int(pr_number))
    state.approval_result = approval_status
    if approval_status["approved"] and approval_status["mergeable"]:
        if client.merge_pr(int(pr_number)):
            state.status = TaskStatus.MERGED
            return state
    if approval_status["rejected"]:
        state.status = TaskStatus.FAILED
        return state
    state.status = TaskStatus.GATED
    return state
