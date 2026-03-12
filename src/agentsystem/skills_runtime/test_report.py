from __future__ import annotations

import json
from pathlib import Path


def latest_run_log(repo_root: str | Path) -> Path | None:
    run_dir = Path(repo_root).resolve() / "runs"
    if not run_dir.exists():
        return None
    logs = sorted(run_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def check_test_result(repo_root: str | Path | None = None) -> str:
    if repo_root is None:
        return "unknown"
    latest = latest_run_log(repo_root)
    if latest is None:
        return "unknown"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    if payload.get("status") != "success":
        return "failed"
    format_results = payload.get("format_results", [])
    if any(not item.get("success") for item in format_results):
        return "failed"
    return "passed"
