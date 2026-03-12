from __future__ import annotations

from pathlib import Path

from git import Repo


class GitAdapter:
    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.repo = Repo(self.repo_path)

    def checkout_main_and_pull(self, branch_name: str = "main") -> None:
        self.repo.git.checkout(branch_name)
        self.repo.git.pull("origin", branch_name)

    def create_new_branch(self, branch_name: str) -> None:
        self.repo.git.checkout("HEAD", b=branch_name)

    def add_all(self) -> None:
        self.repo.git.add(A=True)

    def commit(self, commit_message: str) -> None:
        self.repo.git.commit("-m", commit_message)

    def add_and_commit(self, commit_message: str) -> None:
        self.add_all()
        self.commit(commit_message)

    def push_branch(self, branch_name: str) -> None:
        self.repo.git.push("--set-upstream", "origin", branch_name)

    def get_current_branch(self) -> str:
        return self.repo.active_branch.name

    def get_current_commit(self) -> str:
        return self.repo.head.commit.hexsha

    def is_dirty(self) -> bool:
        return self.repo.is_dirty(untracked_files=True)
