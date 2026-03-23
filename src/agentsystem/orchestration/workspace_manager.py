from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timedelta
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
            try:
                path.unlink()
            except PermissionError:
                # On Windows, a just-written lock file can briefly remain undeletable
                # even after the owning task has already unwound. Leave stale cleanup
                # as best-effort so the original worktree failure is not masked.
                return

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

    def _repo_is_dirty(self) -> bool:
        if not self._is_git_repo():
            return False
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _clear_stale_git_locks(self) -> None:
        git_dir = self.repo_root / ".git"
        if not git_dir.is_dir():
            return
        candidates: list[Path] = []
        index_lock = git_dir / "index.lock"
        if index_lock.exists():
            candidates.append(index_lock)
        refs_dir = git_dir / "refs"
        if refs_dir.exists():
            candidates.extend(sorted(refs_dir.rglob("*.lock")))
        for candidate in candidates:
            try:
                candidate.unlink()
            except OSError:
                continue

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
                if self._repo_is_dirty():
                    self._create_snapshot_workspace(worktree_path, branch, task_id, reason="dirty_worktree")
                else:
                    try:
                        self._create_git_worktree(worktree_path, branch)
                    except Exception:
                        self._create_snapshot_workspace(worktree_path, branch, task_id, reason="git_worktree_fallback")
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
        base_branch = "main"
        self._clear_stale_git_locks()
        branch_exists = subprocess.run(
            ["git", "-C", str(self.repo_root), "rev-parse", "--verify", branch],
            capture_output=True,
            text=True,
        ).returncode == 0
        if branch_exists:
            # Reusing deterministic task ids is fine, but the branch must be rebased to the
            # current main tip or the worktree can silently resurrect stale repository state.
            subprocess.run(
                ["git", "-C", str(self.repo_root), "branch", "-f", branch, base_branch],
                check=True,
                capture_output=True,
                text=True,
            )
        command = ["git", "-C", str(self.repo_root), "worktree", "add"]
        if not branch_exists:
            command.extend(["-b", branch])
        command.extend([str(worktree_path), branch if branch_exists else base_branch])
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    def _create_snapshot_workspace(self, worktree_path: Path, branch: str, task_id: str, reason: str = "snapshot_mode") -> None:
        snapshot_ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "pytest-cache-files-*", "node_modules", ".next", "dist", "build")
        shutil.rmtree(worktree_path, ignore_errors=True)
        shutil.copytree(self.repo_root, worktree_path, ignore=snapshot_ignore)

        snapshot_meta_dir = self._task_meta_dir(task_id)
        snapshot_base_dir = snapshot_meta_dir / "snapshot_base"
        shutil.rmtree(snapshot_base_dir, ignore_errors=True)
        shutil.copytree(self.repo_root, snapshot_base_dir, ignore=snapshot_ignore)

        base_commit = ""
        if self._is_git_repo():
            result = subprocess.run(
                ["git", "-C", str(self.repo_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                base_commit = result.stdout.strip()

        (snapshot_meta_dir / "snapshot_state.json").write_text(
            json.dumps(
                {
                    "mode": "snapshot",
                    "snapshot_reason": reason,
                    "branch": branch,
                    "base_branch": "main",
                    "base_commit": base_commit,
                    "current_commit": base_commit,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
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
            self._remove_git_worktree(worktree_path)
        else:
            shutil.rmtree(worktree_path, ignore_errors=True)
        shutil.rmtree(self._task_meta_dir(task_id), ignore_errors=True)
        self._release_lock(self._branch_lock_path(branch))
        self._release_lock(self._task_lock_path(task_id))

    def _remove_git_worktree(self, worktree_path: Path) -> None:
        try:
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "remove", str(worktree_path), "--force"],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "prune"],
                check=False,
                capture_output=True,
                text=True,
            )
            shutil.rmtree(worktree_path, ignore_errors=True)

    def cleanup_task_worktree(self, task_id: str) -> None:
        self.clean_worktree(task_id, archive=False)

    def cleanup_task_meta(self, task_id: str) -> None:
        shutil.rmtree(self._task_meta_dir(task_id), ignore_errors=True)
        self._release_lock(self._task_lock_path(task_id))

    def cleanup_task_temp_files(self, task_id: str) -> None:
        temp_dir = self._task_meta_dir(task_id) / "temp"
        shutil.rmtree(temp_dir, ignore_errors=True)

    def cleanup_task_resources(self, task_id: str) -> None:
        worktree_path = self.worktree_root / task_id
        if worktree_path.exists():
            self.cleanup_task_worktree(task_id)
        else:
            self.cleanup_task_meta(task_id)
        self.cleanup_task_temp_files(task_id)

    def cleanup_orphaned_state(self) -> None:
        for meta_dir in self.meta_dir.iterdir():
            if not meta_dir.is_dir():
                continue
            task_id = meta_dir.name
            worktree_path = self.worktree_root / task_id
            if worktree_path.exists():
                continue
            shutil.rmtree(meta_dir, ignore_errors=True)
            self._release_lock(self._task_lock_path(task_id))

    def list_expired_tasks(self, older_than_days: int = 7) -> list[str]:
        cutoff = datetime.now() - timedelta(days=older_than_days)
        expired: list[str] = []
        for meta_dir in self.meta_dir.iterdir():
            if not meta_dir.is_dir():
                continue
            task_yaml = meta_dir / "task.yaml"
            if not task_yaml.exists():
                continue
            try:
                payload = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
                created_at = datetime.fromisoformat(str(payload.get("created_at")))
            except Exception:
                continue
            if created_at <= cutoff:
                expired.append(meta_dir.name)
        return sorted(expired)

    def get_task_state(self, task_id: str) -> dict[str, object]:
        return json.loads(self._state_json_path(task_id).read_text(encoding="utf-8"))

    def update_task_state(self, task_id: str, new_state: dict[str, object]) -> None:
        current = self.get_task_state(task_id)
        current.update(new_state)
        self._state_json_path(task_id).write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
