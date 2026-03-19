from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from git import GitCommandError
from git import Repo


class _SnapshotGitFacade:
    def __init__(self, adapter: "GitAdapter"):
        self._adapter = adapter

    def show(self, *_args) -> str:
        return self._adapter._snapshot_stat()


class _SnapshotRepoFacade:
    def __init__(self, adapter: "GitAdapter"):
        self.git = _SnapshotGitFacade(adapter)
        self.remotes: list[object] = []


class GitAdapter:
    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.snapshot_meta_dir = self.repo_path.parent / ".meta" / self.repo_path.name
        self.snapshot_state_path = self.snapshot_meta_dir / "snapshot_state.json"
        self.snapshot_base_dir = self.snapshot_meta_dir / "snapshot_base"
        self.snapshot_mode = False

        try:
            self.repo = Repo(self.repo_path)
        except Exception:
            if self.snapshot_state_path.exists() and self.snapshot_base_dir.exists():
                self.snapshot_mode = True
                self.repo = _SnapshotRepoFacade(self)
            else:
                raise

    def checkout_main_and_pull(self, branch_name: str = "main") -> None:
        if getattr(self, "snapshot_mode", False):
            self._update_snapshot_state(branch=branch_name)
            return

        current_branch = self._get_current_branch_name()
        if current_branch != branch_name:
            self.repo.git.checkout(branch_name)

        # Story execution often starts from a locally dirty repository because runtime
        # evidence is persisted in-place. In that case, avoid unnecessary index writes
        # against the base repo and build the worktree from the current branch tip.
        if self.repo.is_dirty(untracked_files=True):
            return

        if "origin" not in {remote.name for remote in self.repo.remotes}:
            return

        try:
            self.repo.git.rev_parse("--verify", f"origin/{branch_name}")
        except GitCommandError:
            return

        self.repo.git.pull("--ff-only", "origin", branch_name)

    def create_new_branch(self, branch_name: str) -> None:
        if getattr(self, "snapshot_mode", False):
            self._update_snapshot_state(branch=branch_name)
            return
        self.repo.git.checkout("HEAD", b=branch_name)

    def add_all(self) -> None:
        if getattr(self, "snapshot_mode", False):
            return
        self.repo.git.add(A=True)

    def commit(self, commit_message: str) -> None:
        if getattr(self, "snapshot_mode", False):
            current_commit = hashlib.sha1(
                f"{datetime.now().isoformat(timespec='seconds')}::{commit_message}::{self.get_diff()}".encode("utf-8")
            ).hexdigest()
            self._refresh_snapshot_base()
            self._update_snapshot_state(current_commit=current_commit, last_commit_message=commit_message)
            return
        self.repo.git.commit("-m", commit_message)

    def add_and_commit(self, commit_message: str) -> None:
        self.add_all()
        self.commit(commit_message)

    def push_branch(self, branch_name: str) -> None:
        if getattr(self, "snapshot_mode", False):
            return
        self.repo.git.push("--set-upstream", "origin", branch_name)

    def get_current_branch(self) -> str:
        if getattr(self, "snapshot_mode", False):
            return str(self._load_snapshot_state().get("branch") or "snapshot")
        return self.repo.active_branch.name

    def get_current_commit(self) -> str:
        if getattr(self, "snapshot_mode", False):
            state = self._load_snapshot_state()
            return str(state.get("current_commit") or state.get("base_commit") or "")
        return self.repo.head.commit.hexsha

    def get_branches(self) -> list[str]:
        if getattr(self, "snapshot_mode", False):
            return [self.get_current_branch()]
        return [head.name for head in self.repo.branches]

    def delete_branch(self, branch_name: str, *, force: bool = False) -> None:
        if getattr(self, "snapshot_mode", False):
            return
        args = ["-D" if force else "-d", branch_name]
        self.repo.git.branch(*args)

    def get_staged_files(self) -> list[str]:
        if getattr(self, "snapshot_mode", False):
            return self._snapshot_changed_files()
        output = self.repo.git.diff("--cached", "--name-only")
        return [line.strip() for line in output.splitlines() if line.strip()]

    def get_diff(self) -> str:
        if getattr(self, "snapshot_mode", False):
            return self._snapshot_diff()
        return self.repo.git.diff("--cached")

    def is_dirty(self) -> bool:
        if getattr(self, "snapshot_mode", False):
            return bool(self._snapshot_changed_files())
        return self.repo.is_dirty(untracked_files=True)

    def _get_current_branch_name(self) -> str | None:
        try:
            return self.repo.active_branch.name
        except Exception:
            return None

    def _load_snapshot_state(self) -> dict[str, object]:
        return json.loads(self.snapshot_state_path.read_text(encoding="utf-8"))

    def _update_snapshot_state(self, **updates: object) -> None:
        state = self._load_snapshot_state()
        state.update(updates)
        self.snapshot_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_snapshot_base(self) -> None:
        self.snapshot_base_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.repo_path,
            self.snapshot_base_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "pytest-cache-files-*"),
        )

    def _snapshot_changed_files(self) -> list[str]:
        baseline = self._snapshot_file_hashes(self.snapshot_base_dir)
        current = self._snapshot_file_hashes(self.repo_path)
        changed: list[str] = []
        for path in sorted(set(baseline) | set(current)):
            if baseline.get(path) != current.get(path):
                changed.append(path)
        return changed

    def _snapshot_file_hashes(self, root: Path) -> dict[str, str]:
        index: dict[str, str] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if self._is_ignored_snapshot_path(rel):
                continue
            index[rel] = hashlib.sha1(path.read_bytes()).hexdigest()
        return index

    def _snapshot_diff(self) -> str:
        chunks: list[str] = []
        for rel in self._snapshot_changed_files():
            before = self.snapshot_base_dir / rel
            after = self.repo_path / rel
            before_lines = self._read_text_lines(before) if before.exists() else []
            after_lines = self._read_text_lines(after) if after.exists() else []
            if before.exists() or after.exists():
                if before_lines is None or after_lines is None:
                    chunks.append(f"Binary or non-text change: {rel}")
                    continue
                diff = difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                    lineterm="",
                )
                chunks.extend(diff)
        return "\n".join(chunks).strip()

    def _snapshot_stat(self) -> str:
        changed = self._snapshot_changed_files()
        if not changed:
            return ""
        return "\n".join(f"- {path}" for path in changed)

    def _read_text_lines(self, path: Path) -> list[str] | None:
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return None

    def _is_ignored_snapshot_path(self, rel: str) -> bool:
        normalized = rel.replace("\\", "/")
        return (
            normalized.startswith(".git/")
            or normalized.startswith("__pycache__/")
            or "/__pycache__/" in normalized
            or normalized.endswith(".pyc")
            or normalized.startswith(".pytest_cache/")
            or "/.pytest_cache/" in normalized
            or "/pytest-cache-files-" in normalized
            or normalized.startswith("pytest-cache-files-")
        )
