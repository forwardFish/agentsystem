from __future__ import annotations

from pathlib import Path

from agentsystem.skills_runtime.change_scope import load_current_task


def classify_risk(repo_root: str | Path | None = None) -> str:
    if repo_root is None:
        return "unknown"
    task = load_current_task(repo_root)
    blast_radius = task.get("blast_radius")
    return {
        "L1": "low",
        "L2": "medium",
        "L3": "high",
    }.get(blast_radius, "unknown")
