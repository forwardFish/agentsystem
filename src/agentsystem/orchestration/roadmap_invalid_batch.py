from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.orchestration.quality_sentry import inspect_file_quality
from agentsystem.orchestration.runtime_memory import write_current_handoff, write_resume_state


def collect_invalid_batch_candidate_files(repo_root: str | Path, backlog_id: str) -> list[str]:
    repo_path = Path(repo_root).resolve()
    runtime_dir = repo_path / "tasks" / "runtime" / "story_admissions"
    if not runtime_dir.exists():
        return []
    candidates: list[str] = []
    for path in runtime_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        task_payload = payload.get("task_payload") if isinstance(payload.get("task_payload"), dict) else {}
        markers = [
            str(task_payload.get("backlog_id") or ""),
            str(task_payload.get("backlog_root") or ""),
            str(task_payload.get("story_file") or payload.get("story_file") or ""),
            str(payload.get("story_file") or ""),
        ]
        if not any(backlog_id in marker for marker in markers):
            continue
        for key in ("primary_files", "secondary_files", "related_files"):
            raw = task_payload.get(key)
            if isinstance(raw, list):
                candidates.extend(str(item).strip().replace("\\", "/") for item in raw if str(item).strip())
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def cleanup_invalid_batch(repo_root: str | Path, backlog_id: str) -> dict[str, Any]:
    repo_path = Path(repo_root).resolve()
    candidates = collect_invalid_batch_candidate_files(repo_path, backlog_id)
    deleted: list[str] = []
    repaired: list[str] = []
    blocked: list[str] = []
    syntax_checked_files: list[str] = []
    placeholder_rejections: list[str] = []

    for relative_path in candidates:
        absolute_path = repo_path / relative_path
        if not absolute_path.exists() or not absolute_path.is_file():
            continue
        quality_issues = inspect_file_quality(absolute_path, relative_path)
        if absolute_path.suffix.lower() == ".py":
            syntax_checked_files.append(relative_path)
        if any(issue["issue_type"] == "placeholder_artifact" for issue in quality_issues):
            placeholder_rejections.append(relative_path)

        if _is_tracked(repo_path, relative_path):
            updated = _surgical_cleanup_text(absolute_path.read_text(encoding="utf-8"))
            if updated is None:
                if quality_issues:
                    blocked.append(relative_path)
                continue
            absolute_path.write_text(updated, encoding="utf-8")
            repaired.append(relative_path)
            continue

        if quality_issues or relative_path.startswith(("apps/api/src/domain/", "apps/api/src/projection/", "apps/api/src/workflows/")):
            absolute_path.unlink(missing_ok=True)
            deleted.append(relative_path)
            _remove_empty_parents(absolute_path.parent, repo_path)

    return {
        "backlog_id": backlog_id,
        "cleaned_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_count": len(candidates),
        "deleted_files": deleted,
        "repaired_files": repaired,
        "blocked_files": blocked,
        "syntax_checked_files": syntax_checked_files,
        "placeholder_rejections": placeholder_rejections,
    }


def invalidate_roadmap_batch(
    repo_root: str | Path,
    backlog_id: str,
    *,
    project: str,
    env: str = "test",
    reset_sprint_id: str | None = None,
    reset_story_id: str | None = None,
    reason: str = "invalid_delivery_batch",
) -> dict[str, Any]:
    repo_path = Path(repo_root).resolve()
    invalidated_at = datetime.now().isoformat(timespec="seconds")
    story_registry = repo_path / "tasks" / "story_status_registry.json"
    acceptance_registry = repo_path / "tasks" / "story_acceptance_reviews.json"

    story_payload = _read_json(story_registry, {"stories": []})
    story_count = 0
    for entry in story_payload.get("stories", []):
        if not isinstance(entry, dict) or not _entry_matches_backlog(entry, backlog_id):
            continue
        entry["status"] = "invalid_delivery_batch"
        entry["attempt_status"] = "invalid_delivery_batch"
        entry["invalidated_at"] = invalidated_at
        entry["invalidated_reason"] = reason
        entry["formal_flow_complete"] = False
        story_count += 1
    story_registry.write_text(json.dumps(story_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    acceptance_payload = _read_json(acceptance_registry, {"reviews": []})
    review_count = 0
    for entry in acceptance_payload.get("reviews", []):
        if not isinstance(entry, dict) or not _entry_matches_backlog(entry, backlog_id):
            continue
        entry["verdict"] = "needs_followup"
        entry["acceptance_status"] = "invalid_delivery_batch"
        entry["attempt_status"] = "invalid_delivery_batch"
        entry["invalidated_at"] = invalidated_at
        entry["invalidated_reason"] = reason
        entry["formal_flow_complete"] = False
        review_count += 1
    acceptance_registry.write_text(json.dumps(acceptance_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    write_resume_state(
        repo_path,
        {
            "project": project,
            "backlog_id": backlog_id,
            "roadmap_prefix": backlog_id,
            "sprint_id": reset_sprint_id,
            "story_id": reset_story_id,
            "resume_from_story": reset_story_id,
            "status": "interrupted",
            "interruption_reason": reason,
            "error_message": "Previous roadmap batch was invalidated and must rerun from Sprint 1.",
        },
    )
    write_current_handoff(
        repo_path,
        {
            "project": project,
            "backlog_id": backlog_id,
            "sprint_id": reset_sprint_id or "sprint_1",
            "story_id": reset_story_id or "roadmap_restart_boundary",
            "current_node": "roadmap_reset",
            "status": "invalid_delivery_batch",
            "resume_from_story": reset_story_id or "roadmap_restart_boundary",
            "interruption_reason": reason,
            "root_cause": "The previous roadmap batch produced invalid delivery artifacts and cannot be treated as authoritative.",
            "next_action": "Restart roadmap execution from Sprint 1 after cleanup and gate hardening.",
            "resume_command": f'python cli.py run-roadmap --project {project} --env {env} --tasks-root "{repo_path / "tasks"}" --roadmap-prefix {backlog_id} --resume',
            "evidence_paths": [str(story_registry), str(acceptance_registry)],
            "cleanup_note": "Historical evidence is preserved but authoritative success has been revoked.",
            "execution_policy": "continuous_full_sprint",
            "interaction_policy": "non_interactive_auto_run",
            "pause_policy": "story_boundary_or_shared_blocker_only",
        },
    )
    return {
        "backlog_id": backlog_id,
        "invalidated_at": invalidated_at,
        "story_count": story_count,
        "review_count": review_count,
        "resume_sprint_id": reset_sprint_id,
        "resume_story_id": reset_story_id,
    }


def _surgical_cleanup_text(content: str) -> str | None:
    lines = content.splitlines()
    changed = False
    while lines and _is_leading_pollution(lines[0]):
        lines.pop(0)
        changed = True
    while lines and not lines[0].strip():
        lines.pop(0)
        changed = True
    if not changed:
        return None
    return "\n".join(lines).rstrip() + "\n"


def _is_leading_pollution(line: str) -> bool:
    lowered = line.strip().lower()
    return (
        lowered.startswith("/* fixed by fix agent")
        or lowered.startswith("{/* fixed by fix agent")
        or lowered.startswith("<h1 classname=")
        or "agent 实时观测面板" in lowered
        or "agent 瀹炴椂瑙傛祴闈㈡澘" in lowered
    )


def _is_tracked(repo_root: Path, relative_path: str) -> bool:
    process = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", relative_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    return process.returncode == 0


def _remove_empty_parents(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.exists():
        if any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _entry_matches_backlog(entry: dict[str, Any], backlog_id: str) -> bool:
    markers = [
        str(entry.get("backlog_id") or ""),
        str(entry.get("backlog_root") or ""),
        str(entry.get("story_file") or ""),
        str(entry.get("authoritative_attempt") or ""),
    ]
    return any(backlog_id in marker for marker in markers)
