from __future__ import annotations

import json
import shutil
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
        self.worktree_root.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

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
        worktree_path.mkdir(parents=True, exist_ok=False)
        (worktree_path / "logs").mkdir(exist_ok=True)
        (worktree_path / "task.yaml").write_text(
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
        (worktree_path / "state.json").write_text(
            json.dumps({"status": "draft", "retry_count": 0}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return worktree_path


    def clean_worktree(self, task_id: str, *, archive: bool = True) -> None:
        worktree_path = self.worktree_root / task_id
        if not worktree_path.exists():
            return
        task_config = yaml.safe_load((worktree_path / "task.yaml").read_text(encoding="utf-8"))
        branch = task_config["branch"]
        if archive:
            archive_path = self.repo_root / "archive" / task_id
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(worktree_path, archive_path, dirs_exist_ok=True)
        shutil.rmtree(worktree_path, ignore_errors=True)
        self._release_lock(self._branch_lock_path(branch))
        self._release_lock(self._task_lock_path(task_id))

    def get_task_state(self, task_id: str) -> dict[str, object]:
        state_file = self.worktree_root / task_id / "state.json"
        return json.loads(state_file.read_text(encoding="utf-8"))

    def update_task_state(self, task_id: str, new_state: dict[str, object]) -> None:
        state_file = self.worktree_root / task_id / "state.json"
        current = self.get_task_state(task_id)
        current.update(new_state)
        state_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
