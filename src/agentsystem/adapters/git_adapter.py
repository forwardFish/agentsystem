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

    def get_branches(self) -> list[str]:
        return [head.name for head in self.repo.branches]

    def delete_branch(self, branch_name: str, *, force: bool = False) -> None:
        args = ["-D" if force else "-d", branch_name]
        self.repo.git.branch(*args)

    def get_staged_files(self) -> list[str]:
        output = self.repo.git.diff("--cached", "--name-only")
        return [line.strip() for line in output.splitlines() if line.strip()]

    def get_diff(self) -> str:
        return self.repo.git.diff("--cached")

    def is_dirty(self) -> bool:
        return self.repo.is_dirty(untracked_files=True)
