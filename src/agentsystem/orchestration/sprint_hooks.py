from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agentsystem.orchestration.agent_activation_resolver import summarize_sprint_advice


BASE_DIR = Path(__file__).resolve().parents[3]
SPRINT_RUNS_DIR = BASE_DIR / "runs" / "sprints"


def run_sprint_pre_hooks(sprint_dir: str | Path, *, project: str, release: bool = False) -> dict[str, str]:
    sprint_path = Path(sprint_dir).resolve()
    stories = _load_story_payloads(sprint_path)
    advice = summarize_sprint_advice(stories, release=release)
    advice_payload = {
        "project": project,
        "sprint_id": sprint_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **advice,
    }
    output_dir = _ensure_output_dir(project, sprint_path.name)
    advice_path = output_dir / "sprint_agent_advice.json"
    advice_path.write_text(json.dumps(advice_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"advice_path": str(advice_path)}


def run_sprint_post_hooks(sprint_dir: str | Path, *, project: str, release: bool = False) -> dict[str, str | None]:
    sprint_path = Path(sprint_dir).resolve()
    stories = _load_story_payloads(sprint_path)
    output_dir = _ensure_output_dir(project, sprint_path.name)

    document_release_path = output_dir / "document_release_report.md"
    document_release_path.write_text(_build_document_release_report(project, sprint_path.name, stories), encoding="utf-8")

    retro_path = output_dir / "retro_report.md"
    retro_path.write_text(_build_retro_report(project, sprint_path.name, stories), encoding="utf-8")

    ship_advice_path: Path | None = None
    if release:
        ship_advice_path = output_dir / "ship_advice.json"
        ship_advice_path.write_text(
            json.dumps(
                {
                    "project": project,
                    "sprint_id": sprint_path.name,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "advisory_modes": ["ship"],
                    "next_recommended_actions": ["Run ship after confirming sprint-level acceptance and release approval."],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return {
        "document_release_path": str(document_release_path),
        "retro_path": str(retro_path),
        "ship_advice_path": str(ship_advice_path) if ship_advice_path else None,
    }


def _load_story_payloads(sprint_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for story_file in sorted(sprint_dir.rglob("S*.yaml")):
        payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _ensure_output_dir(project: str, sprint_id: str) -> Path:
    path = SPRINT_RUNS_DIR / project / sprint_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_document_release_report(project: str, sprint_id: str, stories: list[dict[str, Any]]) -> str:
    lines = [
        "# Document Release Report",
        "",
        f"- Project: {project}",
        f"- Sprint: {sprint_id}",
        f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Story Coverage",
    ]
    lines.extend(
        [f"- {story.get('story_id') or story.get('task_id')}: {story.get('task_name') or story.get('goal')}" for story in stories]
        or ["- No stories loaded."]
    )
    lines.extend(
        [
            "",
            "## Documentation Sync Guidance",
            "- Update repository-facing docs when behavior, validation, or operating notes changed during this sprint.",
            "- Preserve backlog assets and manual evidence registries.",
            "- Use this report as the sprint-level document-release artifact until a dedicated document-release workflow is wired.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_retro_report(project: str, sprint_id: str, stories: list[dict[str, Any]]) -> str:
    lines = [
        "# Retro Report",
        "",
        f"- Project: {project}",
        f"- Sprint: {sprint_id}",
        f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Completed Story Set",
    ]
    lines.extend(
        [f"- {story.get('story_id') or story.get('task_id')}: {story.get('goal') or story.get('task_name')}" for story in stories]
        or ["- No stories loaded."]
    )
    lines.extend(
        [
            "",
            "## Retro Prompts",
            "- What execution patterns worked repeatedly across the sprint?",
            "- Which stories needed extra review or QA escalation?",
            "- What should be codified into the next iteration of the workflow?",
            "",
        ]
    )
    return "\n".join(lines)
