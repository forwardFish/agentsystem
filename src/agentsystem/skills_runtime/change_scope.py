from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_current_task(repo_root: str | Path) -> dict[str, Any]:
    task_file = Path(repo_root).resolve() / "tasks" / "current.yaml"
    payload = yaml.safe_load(task_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def get_low_risk_tasks(repo_root: str | Path) -> list[dict[str, Any]]:
    task = load_current_task(repo_root)
    if task.get("blast_radius") == "L1":
        return [task]
    return []
