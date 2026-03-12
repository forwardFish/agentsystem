from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import yaml


class WorkspaceLockError(RuntimeError):
    pass


class WorkspaceManager:
    def __init__(self, repo_root: str | Path, worktree_root: str | Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.worktree_root = Path(worktree_root).resolve() if worktree_root else self.repo_root / "repo-worktree"
        self.lock_dir = self.worktree_root / ".locks"
        self.meta_dir = self.worktree_root / ".meta"
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def _branch_lock_path(self, branch: str) -> Path:
        safe_branch = branch.replace("/", "__")
        return self.lock_dir / f"branch-{safe_branch}.lock"

    def _task_lock_path(self, task_id: str) -> Path:
        return self.lock_dir / f"{task_id}.lock"

    def _acquire_lock(self, path: Path) -> None:
        try:
            path.touch(exist_ok=False)
        except FileExistsError as exc:
            raise WorkspaceLockError(f"Lock already exists: {path.name}") from exc

    def _release_lock(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def _task_meta_dir(self, task_id: str) -> Path:
        return self.meta_dir / task_id

    def _task_yaml_path(self, task_id: str) -> Path:
        return self._task_meta_dir(task_id) / "task.yaml"

    def _state_json_path(self, task_id: str) -> Path:
        return self._task_meta_dir(task_id) / "state.json"

    def generate_task_id(self, task_seed: str) -> str:
        digest = hashlib.sha1(task_seed.encode("utf-8")).hexdigest()[:8]
        base = f"task-{digest}"
        candidate = base
        counter = 2
        while (
            (self.worktree_root / candidate).exists()
            or self._task_lock_path(candidate).exists()
            or self._branch_lock_path(f"agent/l1-{candidate}").exists()
        ):
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def _is_git_repo(self) -> bool:
        return (self.repo_root / ".git").exists()

    def create_worktree(self, task_id: str, branch: str) -> Path:
        task_lock = self._task_lock_path(task_id)
        branch_lock = self._branch_lock_path(branch)
        self._acquire_lock(task_lock)
        try:
            self._acquire_lock(branch_lock)
        except Exception:
            self._release_lock(task_lock)
            raise

        worktree_path = self.worktree_root / task_id
        try:
            if self._is_git_repo():
                self._create_git_worktree(worktree_path, branch)
            else:
                worktree_path.mkdir(parents=True, exist_ok=False)
        except Exception:
            self._release_lock(branch_lock)
            self._release_lock(task_lock)
            raise
        meta_dir = self._task_meta_dir(task_id)
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "logs").mkdir(exist_ok=True)
        self._task_yaml_path(task_id).write_text(
            yaml.safe_dump(
                {
                    "task_id": task_id,
                    "branch": branch,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "max_retries": 3,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self._state_json_path(task_id).write_text(
            json.dumps({"status": "draft", "retry_count": 0}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return worktree_path

    def _create_git_worktree(self, worktree_path: Path, branch: str) -> None:
        branch_exists = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", "--verify", branch],
            capture_output=True,
            text=True,
        ).returncode == 0
        command = ["git", "-C", str(self.repo_root), "worktree", "add"]
        if not branch_exists:
            command.extend(["-b", branch])
        command.extend([str(worktree_path), branch if branch_exists else "main"])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    def clean_worktree(self, task_id: str, *, archive: bool = True) -> None:
        worktree_path = self.worktree_root / task_id
        if not worktree_path.exists():
            return
        task_config = yaml.safe_load(self._task_yaml_path(task_id).read_text(encoding="utf-8"))
        branch = task_config["branch"]
        if archive:
            archive_path = self.repo_root / "archive" / task_id
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self._task_meta_dir(task_id), archive_path / "meta", dirs_exist_ok=True)
        if self._is_git_repo():
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "remove", str(worktree_path), "--force"],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            shutil.rmtree(worktree_path, ignore_errors=True)
        shutil.rmtree(self._task_meta_dir(task_id), ignore_errors=True)
        self._release_lock(self._branch_lock_path(branch))
        self._release_lock(self._task_lock_path(task_id))

    def get_task_state(self, task_id: str) -> dict[str, object]:
        return json.loads(self._state_json_path(task_id).read_text(encoding="utf-8"))

    def update_task_state(self, task_id: str, new_state: dict[str, object]) -> None:
        current = self.get_task_state(task_id)
        current.update(new_state)
        self._state_json_path(task_id).write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
