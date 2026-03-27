from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


class WorkspaceLockError(RuntimeError):
    pass


class SnapshotSyncConflictError(RuntimeError):
    def __init__(self, conflicts: list[dict[str, Any]]):
        self.conflicts = conflicts
        details = ", ".join(str(item.get("path") or "") for item in conflicts[:5])
        if len(conflicts) > 5:
            details += ", ..."
        message = "Snapshot changes conflict with the target repository"
        if details:
            message = f"{message}: {details}"
        super().__init__(message)


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

    def _snapshot_state_path(self, task_id: str) -> Path:
        return self._task_meta_dir(task_id) / "snapshot_state.json"

    def _snapshot_base_dir(self, task_id: str) -> Path:
        return self._task_meta_dir(task_id) / "snapshot_base"

    def _snapshot_sync_report_path(self, task_id: str) -> Path:
        return self._task_meta_dir(task_id) / "snapshot_sync_report.json"

    def _workspace_mode(self, task_id: str) -> str:
        snapshot_state_path = self._snapshot_state_path(task_id)
        if not snapshot_state_path.exists():
            return "git"
        try:
            payload = json.loads(snapshot_state_path.read_text(encoding="utf-8"))
        except Exception:
            return "snapshot"
        return str(payload.get("mode") or "snapshot")

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
            encoding="utf-8",
            errors="replace",
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
            encoding="utf-8",
            errors="replace",
        ).returncode == 0
        if branch_exists:
            # Reusing deterministic task ids is fine, but the branch must be rebased to the
            # current main tip or the worktree can silently resurrect stale repository state.
            subprocess.run(
                ["git", "-C", str(self.repo_root), "branch", "-f", branch, base_branch],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
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
            encoding="utf-8",
            errors="replace",
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
                encoding="utf-8",
                errors="replace",
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

    def materialize_snapshot_changes(
        self,
        task_id: str,
        *,
        target_repo_path: str | Path | None = None,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        worktree_path = self.worktree_root / task_id
        snapshot_base_dir = self._snapshot_base_dir(task_id)
        if not worktree_path.exists():
            raise FileNotFoundError(f"Snapshot worktree does not exist for {task_id}: {worktree_path}")
        if not snapshot_base_dir.exists():
            raise FileNotFoundError(f"Snapshot baseline does not exist for {task_id}: {snapshot_base_dir}")

        target_root = Path(target_repo_path).resolve() if target_repo_path else self.repo_root
        report_path = self._snapshot_sync_report_path(task_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        plan = self._plan_snapshot_materialization(
            worktree_path=worktree_path,
            snapshot_base_dir=snapshot_base_dir,
            target_root=target_root,
            changed_files=changed_files,
        )
        plan["task_id"] = task_id
        plan["target_repo_path"] = str(target_root)
        plan["report_path"] = str(report_path)

        if plan["conflicts"]:
            plan["status"] = "conflicted"
            report_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SnapshotSyncConflictError(plan["conflicts"])

        applied_files: list[str] = []
        deleted_files: list[str] = []
        for operation in plan["operations"]:
            rel = str(operation["path"])
            action = str(operation["action"])
            source_path = worktree_path / Path(*rel.split("/"))
            target_path = target_root / Path(*rel.split("/"))
            if action in {"add", "update"}:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                applied_files.append(rel)
                continue
            if action == "delete":
                if target_path.exists():
                    target_path.unlink()
                    self._prune_empty_dirs(target_path.parent, target_root)
                deleted_files.append(rel)

        plan["status"] = "applied" if applied_files or deleted_files else "noop"
        plan["applied_files"] = applied_files
        plan["deleted_files"] = deleted_files
        plan["applied_at"] = datetime.now().isoformat(timespec="seconds")
        report_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        snapshot_state_path = self._snapshot_state_path(task_id)
        if snapshot_state_path.exists():
            try:
                snapshot_state = json.loads(snapshot_state_path.read_text(encoding="utf-8"))
            except Exception:
                snapshot_state = {}
            snapshot_state["materialized_to_repo"] = True
            snapshot_state["materialized_at"] = plan["applied_at"]
            snapshot_state["materialized_report_path"] = str(report_path)
            snapshot_state["materialized_target_repo_path"] = str(target_root)
            snapshot_state_path.write_text(json.dumps(snapshot_state, ensure_ascii=False, indent=2), encoding="utf-8")

        return plan

    def materialize_worktree_changes(
        self,
        task_id: str,
        *,
        target_repo_path: str | Path | None = None,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        worktree_path = self.worktree_root / task_id
        if not worktree_path.exists():
            raise FileNotFoundError(f"Worktree does not exist for {task_id}: {worktree_path}")
        target_root = Path(target_repo_path).resolve() if target_repo_path else self.repo_root
        report_path = self._snapshot_sync_report_path(task_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = self._plan_worktree_materialization(
            worktree_path=worktree_path,
            target_root=target_root,
            changed_files=changed_files,
        )
        report["task_id"] = task_id
        report["target_repo_path"] = str(target_root)
        report["report_path"] = str(report_path)

        if report["conflicts"]:
            report["status"] = "conflicted"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise SnapshotSyncConflictError(report["conflicts"])

        applied_files: list[str] = []
        deleted_files: list[str] = []
        for operation in report["operations"]:
            rel = str(operation["path"])
            action = str(operation["action"])
            source_path = worktree_path / Path(*rel.split("/"))
            target_path = target_root / Path(*rel.split("/"))
            if action in {"add", "update"}:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                applied_files.append(rel)
                continue
            if action == "delete":
                if target_path.exists():
                    target_path.unlink()
                    self._prune_empty_dirs(target_path.parent, target_root)
                deleted_files.append(rel)

        report["status"] = "applied" if applied_files or deleted_files else "noop"
        report["applied_files"] = applied_files
        report["deleted_files"] = deleted_files
        report["applied_at"] = datetime.now().isoformat(timespec="seconds")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _plan_snapshot_materialization(
        self,
        *,
        worktree_path: Path,
        snapshot_base_dir: Path,
        target_root: Path,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        baseline = self._snapshot_file_hashes(snapshot_base_dir)
        source = self._snapshot_file_hashes(worktree_path)
        target = self._snapshot_file_hashes(target_root)

        if changed_files:
            candidate_paths = [
                self._normalize_snapshot_relpath(item)
                for item in changed_files
                if self._normalize_snapshot_relpath(item)
            ]
        else:
            candidate_paths = sorted(
                path
                for path in (set(baseline) | set(source))
                if baseline.get(path) != source.get(path)
            )

        operations: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        conflicts: list[dict[str, str]] = []
        seen: set[str] = set()
        for rel in candidate_paths:
            if rel in seen:
                continue
            seen.add(rel)
            base_hash = baseline.get(rel)
            source_hash = source.get(rel)
            target_hash = target.get(rel)
            base_exists = base_hash is not None
            source_exists = source_hash is not None
            target_exists = target_hash is not None

            if base_hash == source_hash:
                skipped.append({"path": rel, "reason": "source_matches_baseline"})
                continue

            if source_hash == target_hash and source_hash is not None:
                skipped.append({"path": rel, "reason": "already_materialized"})
                continue

            if not base_exists and source_exists:
                if not target_exists:
                    operations.append({"path": rel, "action": "add"})
                else:
                    conflicts.append({"path": rel, "reason": "target_added_different_content"})
                continue

            if base_exists and not source_exists:
                if not target_exists:
                    skipped.append({"path": rel, "reason": "already_deleted"})
                elif target_hash == base_hash:
                    operations.append({"path": rel, "action": "delete"})
                else:
                    conflicts.append({"path": rel, "reason": "target_modified_since_snapshot"})
                continue

            if base_exists and source_exists:
                if target_hash == base_hash:
                    operations.append({"path": rel, "action": "update"})
                elif target_hash == source_hash:
                    skipped.append({"path": rel, "reason": "already_materialized"})
                else:
                    conflicts.append({"path": rel, "reason": "target_modified_since_snapshot"})
                continue

            skipped.append({"path": rel, "reason": "no_effect"})

        return {
            "status": "planned",
            "changed_files": sorted(seen),
            "operations": operations,
            "skipped": skipped,
            "conflicts": conflicts,
        }

    def _plan_worktree_materialization(
        self,
        *,
        worktree_path: Path,
        target_root: Path,
        changed_files: list[str] | None = None,
    ) -> dict[str, Any]:
        source = self._snapshot_file_hashes(worktree_path)
        if changed_files:
            candidate_paths = []
            for item in changed_files:
                normalized = self._normalize_snapshot_relpath(item)
                if normalized:
                    candidate_paths.append(normalized)
        else:
            candidate_paths = sorted(source)

        operations: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        conflicts: list[dict[str, str]] = []
        seen: set[str] = set()
        for rel in candidate_paths:
            if rel in seen:
                continue
            seen.add(rel)
            source_hash = source.get(rel)
            target_path = target_root / Path(*rel.split("/"))
            target_hash = hashlib.sha1(target_path.read_bytes()).hexdigest() if target_path.exists() and target_path.is_file() else None
            target_dirty = self._path_has_local_changes(target_root, rel)

            if source_hash is None:
                if not target_path.exists():
                    skipped.append({"path": rel, "reason": "already_deleted"})
                elif target_dirty:
                    conflicts.append({"path": rel, "reason": "target_modified_before_delete"})
                else:
                    operations.append({"path": rel, "action": "delete"})
                continue

            if target_hash == source_hash:
                skipped.append({"path": rel, "reason": "already_materialized"})
                continue

            if target_dirty:
                conflicts.append({"path": rel, "reason": "target_modified_before_materialization"})
                continue

            operations.append({"path": rel, "action": "add" if target_hash is None else "update"})

        return {
            "status": "planned",
            "changed_files": sorted(seen),
            "operations": operations,
            "skipped": skipped,
            "conflicts": conflicts,
        }

    def _snapshot_file_hashes(self, root: Path) -> dict[str, str]:
        index: dict[str, str] = {}
        if not root.exists():
            return index
        for current_root, dirs, files in os.walk(root, topdown=True):
            current_path = Path(current_root)
            rel_root = current_path.relative_to(root)
            normalized_root = "" if rel_root == Path(".") else rel_root.as_posix()
            dirs[:] = [
                name
                for name in dirs
                if not self._is_ignored_snapshot_path(
                    f"{normalized_root}/{name}" if normalized_root else name
                )
            ]
            for filename in files:
                rel = self._normalize_snapshot_relpath(
                    f"{normalized_root}/{filename}" if normalized_root else filename
                )
                if not rel:
                    continue
                index[rel] = hashlib.sha1((current_path / filename).read_bytes()).hexdigest()
        return index

    def _normalize_snapshot_relpath(self, rel: str | Path) -> str:
        raw = str(rel).replace("\\", "/").strip().lstrip("/")
        if not raw or raw in {".", ".."}:
            return ""
        parts = [part for part in raw.split("/") if part and part != "."]
        if not parts or any(part == ".." for part in parts):
            return ""
        normalized = "/".join(parts)
        if self._is_ignored_snapshot_path(normalized):
            return ""
        return normalized

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
            or normalized.startswith(".meta/")
            or "/.meta/" in normalized
            or normalized.startswith("node_modules/")
            or "/node_modules/" in normalized
            or normalized.startswith(".next/")
            or "/.next/" in normalized
            or normalized.startswith("dist/")
            or "/dist/" in normalized
            or normalized.startswith("build/")
            or "/build/" in normalized
        )

    def _path_has_local_changes(self, repo_root: Path, rel: str) -> bool:
        if not (repo_root / ".git").exists():
            return False
        target_path = Path(*rel.split("/"))
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--", str(target_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _prune_empty_dirs(self, path: Path, stop_at: Path) -> None:
        current = path
        stop_path = stop_at.resolve()
        while True:
            try:
                current_resolved = current.resolve()
            except Exception:
                return
            if current_resolved == stop_path:
                return
            if not current.exists() or any(current.iterdir()):
                return
            current.rmdir()
            current = current.parent

    def clean_worktree(self, task_id: str, *, archive: bool = True) -> None:
        worktree_path = self.worktree_root / task_id
        if not worktree_path.exists():
            return
        task_config = yaml.safe_load(self._task_yaml_path(task_id).read_text(encoding="utf-8"))
        branch = task_config["branch"]
        workspace_mode = self._workspace_mode(task_id)
        if archive:
            archive_path = self.repo_root / "archive" / task_id
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self._task_meta_dir(task_id), archive_path / "meta", dirs_exist_ok=True)
        if self._is_git_repo() and workspace_mode != "snapshot":
            self._remove_git_worktree(worktree_path)
        else:
            self._fast_remove_tree(worktree_path)
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
                encoding="utf-8",
                errors="replace",
            )
            return
        except subprocess.CalledProcessError:
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "prune"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._fast_remove_tree(worktree_path)

    def _fast_remove_tree(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            subprocess.run(
                ["cmd", "/c", "rd", "/s", "/q", str(path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            pass
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def _stop_task_browser_hosts(self, task_id: str) -> None:
        script = (
            "$ErrorActionPreference='SilentlyContinue'; "
            f"$taskId='{task_id}'; "
            "$pids = @(Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*browser_host_server.py*' "
            "and $_.CommandLine -like ('*--task-id ' + $taskId + '*') } | "
            "Select-Object -ExpandProperty ProcessId); "
            "foreach ($pid in $pids) { "
            "Start-Process -FilePath 'taskkill.exe' -ArgumentList @('/PID', [string]$pid, '/T', '/F') "
            "-NoNewWindow -Wait | Out-Null }"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return

    def cleanup_task_worktree(self, task_id: str) -> None:
        self.clean_worktree(task_id, archive=False)

    def cleanup_task_meta(self, task_id: str) -> None:
        shutil.rmtree(self._task_meta_dir(task_id), ignore_errors=True)
        self._release_lock(self._task_lock_path(task_id))

    def cleanup_task_temp_files(self, task_id: str) -> None:
        temp_dir = self._task_meta_dir(task_id) / "temp"
        shutil.rmtree(temp_dir, ignore_errors=True)

    def cleanup_task_resources(self, task_id: str) -> None:
        self._stop_task_browser_hosts(task_id)
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
