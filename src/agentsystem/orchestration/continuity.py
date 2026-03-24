from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


CONTINUITY_TRIGGERS = {
    "fresh_start",
    "resume_interrupt",
    "story_boundary",
    "sprint_boundary",
    "node_boundary",
}

DEFAULT_TRIGGER = "fresh_start"
DEFAULT_PREVIEW_CHARS = 2000


class ContinuityGuardError(RuntimeError):
    pass


def resolve_continuity_paths(repo_root: str | Path, project: str | None = None) -> dict[str, Path]:
    repo_path = Path(repo_root).resolve()
    project_id = str(project or repo_path.name).strip() or repo_path.name
    workspace_root = repo_path.parent
    continuity_root = workspace_root / ".meta" / project_id / "continuity"
    continuity_root.mkdir(parents=True, exist_ok=True)
    return {
        "repo_root": repo_path,
        "workspace_root": workspace_root,
        "continuity_root": continuity_root,
        "agents_md": workspace_root / "AGENTS.md",
        "now_md": continuity_root / "NOW.md",
        "state_md": continuity_root / "STATE.md",
        "decisions_md": continuity_root / "DECISIONS.md",
        "manifest_json": continuity_root / "continuity_manifest.json",
        "resume_json": repo_path / "tasks" / "runtime" / "auto_resume_state.json",
        "status_registry": repo_path / "tasks" / "story_status_registry.json",
        "acceptance_registry": repo_path / "tasks" / "story_acceptance_reviews.json",
    }


def sync_continuity(
    trigger: str,
    project: str,
    repo_root: str | Path,
    *,
    task_payload: dict[str, Any] | None = None,
    current_story_path: str | Path | None = None,
    sprint_artifact_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    decision_refs: list[str] | None = None,
) -> dict[str, Any]:
    trigger_name = _normalize_trigger(trigger)
    paths = resolve_continuity_paths(repo_root, project)
    old_manifest = _read_json(paths["manifest_json"], {})
    resume_state = _read_json(paths["resume_json"], {})
    status_payload = _read_json(paths["status_registry"], {"stories": []})
    acceptance_payload = _read_json(paths["acceptance_registry"], {"reviews": []})
    task = dict(task_payload or {})

    story_path = Path(current_story_path).resolve() if current_story_path else None
    explicit_artifacts = _normalize_paths(artifact_refs)
    sprint_refs = _normalize_paths(sprint_artifact_refs)
    explicit_decisions = _normalize_paths(decision_refs)
    inferred_decisions = _infer_decision_refs(task)
    merged_decisions = _merge_unique_paths(
        list(((old_manifest.get("docs") or {}).get("decisions") or {}).get("decision_refs") or []),
        inferred_decisions,
        explicit_decisions,
    )

    now_doc = _build_now_doc(
        trigger=trigger_name,
        repo_root=paths["repo_root"],
        task_payload=task,
        resume_state=resume_state,
        current_story_path=story_path,
        sprint_artifact_refs=sprint_refs,
        artifact_refs=explicit_artifacts,
        decision_refs=merged_decisions,
    )
    state_doc = _build_state_doc(
        trigger=trigger_name,
        repo_root=paths["repo_root"],
        task_payload=task,
        resume_state=resume_state,
        status_payload=status_payload,
        acceptance_payload=acceptance_payload,
        current_story_path=story_path,
        sprint_artifact_refs=sprint_refs,
        next_action=str(now_doc.get("next_action") or "").strip() or None,
    )
    decisions_doc = _build_decisions_doc(
        decision_refs=merged_decisions,
        previous=((old_manifest.get("docs") or {}).get("decisions") or {}),
    )

    paths["now_md"].write_text(_render_now_markdown(now_doc), encoding="utf-8")
    paths["state_md"].write_text(_render_state_markdown(state_doc), encoding="utf-8")
    paths["decisions_md"].write_text(_render_decisions_markdown(decisions_doc), encoding="utf-8")

    manifest = {
        "project": project,
        "trigger": trigger_name,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "paths": {key: str(value) for key, value in paths.items() if key in {"agents_md", "now_md", "state_md", "decisions_md"}},
        "docs": {
            "now": _finalize_doc_manifest(now_doc),
            "state": _finalize_doc_manifest(state_doc),
            "decisions": _finalize_doc_manifest(decisions_doc),
        },
    }
    paths["manifest_json"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def plan_read_set(
    *,
    trigger: str,
    current_story: str | None = None,
    current_sprint: str | None = None,
    now_doc: dict[str, Any] | None = None,
    state_doc: dict[str, Any] | None = None,
    resume_state: dict[str, Any] | None = None,
    agents_path: str | Path | None = None,
    now_path: str | Path | None = None,
    state_path: str | Path | None = None,
    decisions_path: str | Path | None = None,
    current_story_path: str | Path | None = None,
) -> dict[str, Any]:
    del current_story
    del current_sprint
    del resume_state
    trigger_name = _normalize_trigger(trigger)
    now_payload = now_doc or {}
    state_payload = state_doc or {}

    required = []
    optional = []

    if trigger_name == "fresh_start":
        required.extend([agents_path, state_path, now_path])
        optional.append(decisions_path)
    elif trigger_name == "resume_interrupt":
        required.append(now_path)
        required.extend((now_payload.get("artifact_refs") or []))
        if bool(now_payload.get("decision_deps")):
            optional.append(decisions_path)
    elif trigger_name == "story_boundary":
        required.extend([state_path, current_story_path])
        optional.extend((state_payload.get("artifact_refs") or []))
    elif trigger_name == "sprint_boundary":
        required.append(state_path)
        optional.extend((state_payload.get("artifact_refs") or []))
    elif trigger_name == "node_boundary":
        required.append(now_path)

    required_paths = _normalize_paths(required)
    optional_paths = _normalize_paths(optional)
    missing_required = [item for item in required_paths if not Path(item).exists()]
    return {
        "trigger": trigger_name,
        "required_paths": required_paths,
        "optional_paths": optional_paths,
        "missing_required": missing_required,
    }


def load_continuity_bundle(
    trigger: str,
    project: str,
    repo_root: str | Path,
    *,
    current_story_path: str | Path | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    trigger_name = _normalize_trigger(trigger)
    paths = resolve_continuity_paths(repo_root, project)
    manifest = _read_json(paths["manifest_json"], {})
    docs = manifest.get("docs") if isinstance(manifest.get("docs"), dict) else {}
    now_doc = docs.get("now") if isinstance(docs.get("now"), dict) else {}
    state_doc = docs.get("state") if isinstance(docs.get("state"), dict) else {}
    decisions_doc = docs.get("decisions") if isinstance(docs.get("decisions"), dict) else {}
    resume_state = _read_json(paths["resume_json"], {})

    read_set = plan_read_set(
        trigger=trigger_name,
        current_story=str(now_doc.get("story_id") or ""),
        current_sprint=str(state_doc.get("current_sprint") or ""),
        now_doc=now_doc,
        state_doc=state_doc,
        resume_state=resume_state,
        agents_path=paths["agents_md"],
        now_path=paths["now_md"],
        state_path=paths["state_md"],
        decisions_path=paths["decisions_md"],
        current_story_path=current_story_path,
    )

    required_sources = _read_text_sources(read_set["required_paths"], required=True)
    optional_sources = _read_text_sources(read_set["optional_paths"], required=False)
    staleness = _compute_staleness(paths, manifest, resume_state, now_doc, state_doc, decisions_doc)
    bundle = {
        "project": project,
        "trigger": trigger_name,
        "strict": strict,
        "manifest": manifest,
        "required_paths": read_set["required_paths"],
        "optional_paths": read_set["optional_paths"],
        "missing_required": read_set["missing_required"],
        "required_sources": required_sources,
        "optional_sources": optional_sources,
        "continuity_now": {
            "text": _read_text(paths["now_md"]),
            "data": now_doc,
        },
        "continuity_state": {
            "text": _read_text(paths["state_md"]),
            "data": state_doc,
        },
        "continuity_decisions": {
            "text": _read_text(paths["decisions_md"]),
            "data": decisions_doc,
        },
        "continuity_agents": {
            "text": _read_text(paths["agents_md"]),
        },
        "continuity_refs": {
            "required": read_set["required_paths"],
            "optional": read_set["optional_paths"],
        },
        "continuity_summary": _build_bundle_summary(trigger_name, now_doc, state_doc),
        "continuity_last_synced_at": str(manifest.get("updated_at") or ""),
        "staleness": staleness,
    }
    if strict:
        assert_continuity_ready(bundle, strict=True)
    return bundle


def assert_continuity_ready(bundle: dict[str, Any], strict: bool = True) -> None:
    if not strict:
        return
    missing_required = list(bundle.get("missing_required") or [])
    if missing_required:
        raise ContinuityGuardError("Missing required continuity inputs: " + ", ".join(missing_required))

    staleness = bundle.get("staleness") if isinstance(bundle.get("staleness"), dict) else {}
    now_doc = ((bundle.get("continuity_now") or {}).get("data") or {}) if isinstance(bundle.get("continuity_now"), dict) else {}
    decision_deps = bool(now_doc.get("decision_deps"))
    stale_labels = []
    for key, value in staleness.items():
        if not value:
            continue
        if key == "decisions" and not decision_deps:
            continue
        stale_labels.append(key)
    if stale_labels:
        raise ContinuityGuardError("Continuity snapshot is stale: " + ", ".join(stale_labels))

    trigger_name = str(bundle.get("trigger") or DEFAULT_TRIGGER)
    if trigger_name == "resume_interrupt":
        artifact_refs = _normalize_paths(now_doc.get("artifact_refs") or [])
        missing_refs = [item for item in artifact_refs if not Path(item).exists()]
        if missing_refs:
            raise ContinuityGuardError("Resume continuity is missing required artifacts: " + ", ".join(missing_refs))


def inject_continuity_into_task(task_payload: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    task = dict(task_payload)
    task.update(
        {
            "continuity_trigger": bundle.get("trigger"),
            "continuity_summary": bundle.get("continuity_summary"),
            "continuity_now": ((bundle.get("continuity_now") or {}).get("data") or {}),
            "continuity_state": ((bundle.get("continuity_state") or {}).get("data") or {}),
            "continuity_decisions": ((bundle.get("continuity_decisions") or {}).get("data") or {}),
            "continuity_refs": bundle.get("continuity_refs") or {},
            "continuity_last_synced_at": bundle.get("continuity_last_synced_at"),
        }
    )
    return task


def _normalize_trigger(trigger: str | None) -> str:
    candidate = str(trigger or "").strip() or DEFAULT_TRIGGER
    return candidate if candidate in CONTINUITY_TRIGGERS else DEFAULT_TRIGGER


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return payload if isinstance(payload, dict) else dict(default)


def _read_text(path: Path, *, max_chars: int | None = None) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    if max_chars is not None and len(content) > max_chars:
        return content[:max_chars].rstrip() + "\n...[truncated]"
    return content


def _read_text_sources(paths: list[str], *, required: bool) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for marker in paths:
        path = Path(marker)
        if not path.exists():
            if required:
                sources.append({"path": str(path), "required": True, "missing": True, "preview": ""})
            continue
        sources.append(
            {
                "path": str(path),
                "required": required,
                "missing": False,
                "preview": _read_text(path, max_chars=DEFAULT_PREVIEW_CHARS),
            }
        )
    return sources


def _build_now_doc(
    *,
    trigger: str,
    repo_root: Path,
    task_payload: dict[str, Any],
    resume_state: dict[str, Any],
    current_story_path: Path | None,
    sprint_artifact_refs: list[str],
    artifact_refs: list[str],
    decision_refs: list[str],
) -> dict[str, Any]:
    story_id = str(task_payload.get("story_id") or task_payload.get("task_id") or resume_state.get("story_id") or "").strip()
    sprint_id = str(task_payload.get("sprint_id") or resume_state.get("sprint_id") or "").strip()
    current_node = str(task_payload.get("current_node") or resume_state.get("current_node") or "").strip()
    status = str(task_payload.get("status") or resume_state.get("status") or "ready").strip() or "ready"
    blocker = str(task_payload.get("blocker_class") or resume_state.get("blocker_class") or "").strip()
    next_action = _derive_next_action(trigger, story_id=story_id, sprint_id=sprint_id, current_node=current_node, status=status)
    refs = _merge_unique_paths(
        artifact_refs,
        sprint_artifact_refs,
        _story_runtime_refs(repo_root, story_id),
        [str(current_story_path)] if current_story_path else [],
    )
    validate = _default_validate_command(str(task_payload.get("project") or repo_root.name))
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "trigger": trigger,
        "current_task": str(task_payload.get("task_name") or task_payload.get("goal") or resume_state.get("task_name") or "Continue current work").strip(),
        "story_id": story_id,
        "sprint_id": sprint_id,
        "current_node": current_node,
        "current_step": str(task_payload.get("current_step") or resume_state.get("current_step") or "").strip(),
        "status": status,
        "blocker": blocker,
        "next_action": next_action,
        "validate_command": validate,
        "artifact_refs": refs,
        "decision_deps": bool(decision_refs),
        "decision_refs": decision_refs,
        "source_paths": _normalize_paths([repo_root / "tasks" / "runtime" / "auto_resume_state.json"]),
    }


def _build_state_doc(
    *,
    trigger: str,
    repo_root: Path,
    task_payload: dict[str, Any],
    resume_state: dict[str, Any],
    status_payload: dict[str, Any],
    acceptance_payload: dict[str, Any],
    current_story_path: Path | None,
    sprint_artifact_refs: list[str],
    next_action: str | None,
) -> dict[str, Any]:
    stories = [item for item in (status_payload.get("stories") or []) if isinstance(item, dict)]
    reviews = [item for item in (acceptance_payload.get("reviews") or []) if isinstance(item, dict)]
    done_stories = [item for item in stories if str(item.get("status") or "").strip().lower() in {"done", "accepted"}]
    problem_stories = [
        item
        for item in stories
        if str(item.get("status") or "").strip().lower() in {"failed", "rejected", "needs_followup", "implemented_without_formal_flow"}
    ]
    current_story = str(task_payload.get("story_id") or task_payload.get("task_id") or resume_state.get("story_id") or "").strip()
    current_sprint = str(task_payload.get("sprint_id") or resume_state.get("sprint_id") or "").strip()
    current_status = str(task_payload.get("status") or resume_state.get("status") or "ready").strip() or "ready"
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "trigger": trigger,
        "goal": str(task_payload.get("goal") or task_payload.get("task_name") or resume_state.get("task_name") or "Continue project delivery").strip(),
        "phase": _derive_phase(trigger, current_status, current_sprint),
        "current_sprint": current_sprint,
        "current_story": current_story,
        "current_status": current_status,
        "done_items": [
            _summarize_story_entry(item)
            for item in sorted(done_stories, key=_story_sort_key, reverse=True)[:5]
        ],
        "working_items": [line for line in [_working_line(current_story, current_sprint, current_status)] if line],
        "problem_items": [
            _summarize_story_entry(item)
            for item in sorted(problem_stories, key=_story_sort_key, reverse=True)[:3]
        ],
        "next_steps": [item for item in [next_action or "", _next_step_from_reviews(reviews)] if item],
        "artifact_refs": _merge_unique_paths(
            sprint_artifact_refs,
            [str(current_story_path)] if current_story_path else [],
        ),
        "source_paths": _normalize_paths(
            [
                repo_root / "tasks" / "story_status_registry.json",
                repo_root / "tasks" / "story_acceptance_reviews.json",
                repo_root / "tasks" / "runtime" / "auto_resume_state.json",
            ]
        ),
    }


def _build_decisions_doc(decision_refs: list[str], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    previous_payload = previous or {}
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "decision_refs": _merge_unique_paths(list(previous_payload.get("decision_refs") or []), decision_refs),
        "source_paths": _normalize_paths(decision_refs),
    }


def _render_now_markdown(doc: dict[str, Any]) -> str:
    artifact_refs = list(doc.get("artifact_refs") or [])
    lines = [
        "# NOW.md",
        "",
        f"- Updated: {doc.get('updated_at') or '-'}",
        f"- Trigger: {doc.get('trigger') or '-'}",
        f"- Current task: {doc.get('current_task') or '-'}",
        f"- Sprint: {doc.get('sprint_id') or '-'}",
        f"- Story: {doc.get('story_id') or '-'}",
        f"- Node: {doc.get('current_node') or '-'}",
        f"- Status: {doc.get('status') or '-'}",
        f"- Blocker: {doc.get('blocker') or 'None'}",
        "",
        "## Next Action",
        str(doc.get("next_action") or "Continue from the latest safe point."),
        "",
        "## Validate",
        str(doc.get("validate_command") or "n/a"),
        "",
        "## Artifact Refs",
    ]
    if artifact_refs:
        lines.extend(f"- {item}" for item in artifact_refs)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Decision Deps",
            "- required" if doc.get("decision_deps") else "- none",
            "",
        ]
    )
    return "\n".join(lines)


def _render_state_markdown(doc: dict[str, Any]) -> str:
    lines = [
        "# STATE.md",
        "",
        f"- Updated: {doc.get('updated_at') or '-'}",
        f"- Trigger: {doc.get('trigger') or '-'}",
        f"- Goal: {doc.get('goal') or '-'}",
        f"- Phase: {doc.get('phase') or '-'}",
        f"- Current sprint: {doc.get('current_sprint') or '-'}",
        f"- Current story: {doc.get('current_story') or '-'}",
        f"- Status: {doc.get('current_status') or '-'}",
        "",
        "## Done",
    ]
    done_items = list(doc.get("done_items") or [])
    lines.extend(done_items or ["- None"])
    lines.extend(["", "## Working"])
    working_items = list(doc.get("working_items") or [])
    lines.extend(working_items or ["- None"])
    lines.extend(["", "## Problems"])
    problem_items = list(doc.get("problem_items") or [])
    lines.extend(problem_items or ["- None"])
    lines.extend(["", "## Next"])
    next_steps = list(doc.get("next_steps") or [])
    lines.extend(f"- {item}" for item in next_steps) if next_steps else lines.append("- None")
    lines.extend(["", "## Artifact Refs"])
    artifact_refs = list(doc.get("artifact_refs") or [])
    lines.extend(f"- {item}" for item in artifact_refs) if artifact_refs else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _render_decisions_markdown(doc: dict[str, Any]) -> str:
    refs = list(doc.get("decision_refs") or [])
    lines = [
        "# DECISIONS.md",
        "",
        f"- Updated: {doc.get('updated_at') or '-'}",
        "",
        "## Active Decision Inputs",
    ]
    if refs:
        lines.extend(f"- {item}" for item in refs)
    else:
        lines.append("- No recorded decision inputs yet.")
    lines.append("")
    return "\n".join(lines)


def _finalize_doc_manifest(doc: dict[str, Any]) -> dict[str, Any]:
    source_paths = _normalize_paths(doc.get("source_paths") or [])
    source_mtimes = {
        path: _file_mtime(Path(path))
        for path in source_paths
        if Path(path).exists()
    }
    payload = dict(doc)
    payload["source_paths"] = source_paths
    payload["source_mtimes"] = source_mtimes
    return payload


def _compute_staleness(
    paths: dict[str, Path],
    manifest: dict[str, Any],
    resume_state: dict[str, Any],
    now_doc: dict[str, Any],
    state_doc: dict[str, Any],
    decisions_doc: dict[str, Any],
) -> dict[str, bool]:
    docs = manifest.get("docs") if isinstance(manifest.get("docs"), dict) else {}
    now_manifest = docs.get("now") if isinstance(docs.get("now"), dict) else {}
    state_manifest = docs.get("state") if isinstance(docs.get("state"), dict) else {}
    decisions_manifest = docs.get("decisions") if isinstance(docs.get("decisions"), dict) else {}
    trigger = str(now_doc.get("trigger") or manifest.get("trigger") or DEFAULT_TRIGGER)
    return {
        "now": _doc_sources_changed(now_manifest) or (trigger == "resume_interrupt" and _resume_state_mismatch(resume_state, now_doc)),
        "state": _doc_sources_changed(state_manifest),
        "decisions": _doc_sources_changed(decisions_manifest) or _decision_refs_missing(decisions_doc),
        "manifest": not paths["manifest_json"].exists(),
    }


def _doc_sources_changed(doc_manifest: dict[str, Any]) -> bool:
    source_mtimes = doc_manifest.get("source_mtimes") if isinstance(doc_manifest.get("source_mtimes"), dict) else {}
    for path, previous in source_mtimes.items():
        current = _file_mtime(Path(path))
        if current != previous:
            return True
    return False


def _resume_state_mismatch(resume_state: dict[str, Any], now_doc: dict[str, Any]) -> bool:
    if not resume_state:
        return False
    mapping = {
        "story_id": "story_id",
        "current_node": "current_node",
        "status": "status",
    }
    for resume_key, now_key in mapping.items():
        resume_value = str(resume_state.get(resume_key) or "").strip()
        now_value = str(now_doc.get(now_key) or "").strip()
        if resume_value and now_value and resume_value != now_value:
            return True
    checkpoint_at = str(resume_state.get("last_checkpoint_at") or "").strip()
    updated_at = str(now_doc.get("updated_at") or "").strip()
    return bool(checkpoint_at and updated_at and checkpoint_at > updated_at)


def _decision_refs_missing(decisions_doc: dict[str, Any]) -> bool:
    refs = _normalize_paths(decisions_doc.get("decision_refs") or [])
    return any(not Path(item).exists() for item in refs)


def _build_bundle_summary(trigger: str, now_doc: dict[str, Any], state_doc: dict[str, Any]) -> dict[str, Any]:
    story_id = str(now_doc.get("story_id") or state_doc.get("current_story") or "").strip()
    current_node = str(now_doc.get("current_node") or "").strip()
    status = str(now_doc.get("status") or state_doc.get("current_status") or "").strip()
    return {
        "safe_point": f"{story_id or 'unknown'} @ {current_node or 'boundary'}",
        "status": status or "unknown",
        "why_resumed_here": str(now_doc.get("next_action") or state_doc.get("next_steps", ["Continue from the latest boundary."])[0]),
        "allowed_next_action": str(now_doc.get("next_action") or "Continue from the current safe point."),
        "relevant_artifacts": _merge_unique_paths(
            list(now_doc.get("artifact_refs") or []),
            list(state_doc.get("artifact_refs") or []),
        )[:8],
    }


def _infer_decision_refs(task_payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "plan_ceo_review_path",
        "plan_ceo_requirement_doc_path",
        "plan_ceo_decision_ceremony_path",
        "architecture_review_report",
        "architecture_review_path",
        "design_contract_path",
        "plan_design_review_report",
        "plan_design_review_path",
    ):
        refs.extend(_normalize_paths(task_payload.get(key)))
    for key in ("continuity_decision_refs", "decision_refs"):
        refs.extend(_normalize_paths(task_payload.get(key)))
    return refs


def _story_runtime_refs(repo_root: Path, story_id: str) -> list[str]:
    if not story_id:
        return []
    runtime_dir = repo_root / "tasks" / "runtime"
    return _normalize_paths(
        [
            runtime_dir / "story_handoffs" / f"{story_id}.md",
            runtime_dir / "story_failures" / f"{story_id}.json",
            runtime_dir / "story_admissions" / f"{story_id}.json",
        ]
    )


def _normalize_paths(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple, set)) else [value]
    results: list[str] = []
    for item in items:
        marker = str(item or "").strip()
        if marker:
            results.append(marker)
    return results


def _merge_unique_paths(*groups: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in _normalize_paths(group):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _derive_next_action(trigger: str, *, story_id: str, sprint_id: str, current_node: str, status: str) -> str:
    if trigger == "resume_interrupt":
        return f"Resume story {story_id or 'unknown'} from node {current_node or 'latest safe point'} after re-reading the recorded artifacts."
    if trigger == "story_boundary":
        return f"Start story {story_id or 'unknown'} inside sprint {sprint_id or 'unknown'} using the refreshed state snapshot."
    if trigger == "sprint_boundary":
        return f"Continue sprint {sprint_id or 'unknown'} from the next story boundary."
    if trigger == "node_boundary":
        return f"Continue story {story_id or 'unknown'} from node {current_node or 'current'}."
    if status == "running":
        return f"Continue story {story_id or 'unknown'} from the latest safe point."
    return "Continue from the latest safe point."


def _derive_phase(trigger: str, status: str, current_sprint: str) -> str:
    if trigger == "sprint_boundary":
        return f"sprint::{current_sprint or 'unknown'}"
    if trigger == "story_boundary":
        return "story_execution"
    if trigger == "resume_interrupt":
        return "resume_recovery"
    if status == "running":
        return "active_delivery"
    return "ready"


def _working_line(story_id: str, sprint_id: str, status: str) -> str:
    if not story_id and not sprint_id and not status:
        return ""
    return f"- Sprint `{sprint_id or '-'}` / Story `{story_id or '-'}` / Status `{status or '-'}`"


def _summarize_story_entry(entry: dict[str, Any]) -> str:
    story_id = str(entry.get("story_id") or entry.get("task_id") or "unknown").strip()
    status = str(entry.get("status") or "unknown").strip()
    summary = str(entry.get("summary") or entry.get("validation_summary") or "").strip()
    if summary:
        return f"- {story_id}: {status} - {summary}"
    return f"- {story_id}: {status}"


def _story_sort_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("finished_at") or entry.get("verified_at") or entry.get("started_at") or ""),
        str(entry.get("sprint_id") or ""),
        str(entry.get("story_id") or ""),
    )


def _next_step_from_reviews(reviews: list[dict[str, Any]]) -> str:
    for review in sorted(reviews, key=lambda item: str(item.get("checked_at") or ""), reverse=True):
        status = str(review.get("acceptance_status") or review.get("verdict") or "").strip().lower()
        if status in {"needs_followup", "rejected"}:
            return f"Follow up review findings for {review.get('story_id') or 'unknown'}."
    return ""


def _default_validate_command(project: str) -> str:
    key = str(project or "").strip().lower()
    if key == "agentsystem":
        return "python -m unittest tests.test_dashboard_api -v"
    if key == "versefina":
        return "python -m pytest apps/api/tests -q"
    if key == "finahunt":
        return "python -m pytest -q"
    return "python -m pytest -q"


def _file_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except Exception:
        return None
