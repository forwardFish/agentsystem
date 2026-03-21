from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def full_parity_evidence_path(root_dir: str | Path) -> Path:
    return Path(root_dir).resolve() / "runs" / "parity" / "full_parity_evidence.json"


def load_full_parity_evidence(root_dir: str | Path) -> dict[str, Any]:
    path = full_parity_evidence_path(root_dir)
    if not path.exists():
        return {"generated_at": None, "entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "entries": []}
    if not isinstance(payload, dict):
        return {"generated_at": None, "entries": []}
    entries = payload.get("entries")
    return {
        "generated_at": payload.get("generated_at"),
        "entries": list(entries) if isinstance(entries, list) else [],
    }


def write_full_parity_evidence(root_dir: str | Path, payload: dict[str, Any]) -> Path:
    path = full_parity_evidence_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "generated_at": str(payload.get("generated_at") or datetime.now().isoformat(timespec="seconds")),
        "entries": list(payload.get("entries") or []),
    }
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def record_full_parity_evidence(
    root_dir: str | Path,
    *,
    mode_id: str,
    evidence_type: str,
    project: str | None = None,
    status: str = "passed",
    detail: str | None = None,
    story_id: str | None = None,
    sprint_id: str | None = None,
    source: str | None = None,
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_full_parity_evidence(root_dir)
    entry = {
        "mode_id": str(mode_id).strip(),
        "evidence_type": str(evidence_type).strip(),
        "project": str(project).strip() or None if project is not None else None,
        "status": str(status).strip() or "passed",
        "detail": str(detail).strip() or None if detail is not None else None,
        "story_id": str(story_id).strip() or None if story_id is not None else None,
        "sprint_id": str(sprint_id).strip() or None if sprint_id is not None else None,
        "source": str(source).strip() or "runtime" if source is not None else "runtime",
        "evidence_refs": [str(item).strip() for item in (evidence_refs or []) if str(item).strip()],
        "metadata": dict(metadata or {}),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    entries = [item for item in payload.get("entries") or [] if isinstance(item, dict)]
    entries.append(entry)
    payload["generated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["entries"] = entries
    write_full_parity_evidence(root_dir, payload)
    return entry


def latest_passing_evidence_by_mode(root_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    evidence = load_full_parity_evidence(root_dir)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in evidence.get("entries") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").strip().lower() != "passed":
            continue
        mode_id = str(item.get("mode_id") or "").strip()
        if not mode_id:
            continue
        grouped.setdefault(mode_id, []).append(item)
    return grouped
