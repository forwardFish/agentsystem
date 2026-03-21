from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agentsystem.agents.office_hours_agent import office_hours_node
from agentsystem.agents.document_release_agent import generate_document_release_artifacts
from agentsystem.agents.plan_ceo_review_agent import generate_plan_ceo_review_package
from agentsystem.agents.retro_agent import generate_retro_artifacts
from agentsystem.agents.ship_agent import generate_ship_artifacts
from agentsystem.orchestration.agent_activation_resolver import summarize_sprint_advice
from agentsystem.orchestration.gstack_parity_audit import write_gstack_parity_audit


BASE_DIR = Path(__file__).resolve().parents[3]
SPRINT_RUNS_DIR = BASE_DIR / "runs" / "sprints"


def run_sprint_pre_hooks(sprint_dir: str | Path, *, project: str, release: bool = False) -> dict[str, str]:
    sprint_path = Path(sprint_dir).resolve()
    stories = _load_story_payloads(sprint_path)
    advice = summarize_sprint_advice(stories, release=release)
    repo_b_path = sprint_path.parents[2] if len(sprint_path.parents) >= 3 else sprint_path.parent
    advice_payload = {
        "project": project,
        "sprint_id": sprint_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **advice,
    }
    output_dir = _ensure_output_dir(project, sprint_path.name)
    advice_path = output_dir / "sprint_agent_advice.json"
    advice_path.write_text(json.dumps(advice_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    framing_outputs = _generate_sprint_framing_artifacts(repo_b_path, sprint_path, project, stories, output_dir)
    parity_outputs = write_gstack_parity_audit(output_dir, sprint_dir=sprint_path, project=project)
    return {
        "advice_path": str(advice_path),
        "sprint_framing_path": framing_outputs["sprint_framing_path"],
        "office_hours_path": framing_outputs["office_hours_path"],
        "plan_ceo_review_path": framing_outputs["plan_ceo_review_path"],
        "parity_manifest_path": parity_outputs["parity_manifest_path"],
        "acceptance_checklist_path": parity_outputs["acceptance_checklist_path"],
    }


def run_sprint_post_hooks(sprint_dir: str | Path, *, project: str, release: bool = False) -> dict[str, str | None]:
    sprint_path = Path(sprint_dir).resolve()
    stories = _load_story_payloads(sprint_path)
    output_dir = _ensure_output_dir(project, sprint_path.name)
    repo_b_path = sprint_path.parents[2] if len(sprint_path.parents) >= 3 else sprint_path.parent
    synthetic_state = {
        "retro_window": sprint_path.name,
        "mode_execution_order": ["ship", "document-release", "retro"],
        "test_passed": True,
        "review_passed": True,
        "code_acceptance_passed": True,
        "acceptance_passed": True,
        "doc_targets": ["docs", "tasks/runtime"],
    }
    synthetic_task = {
        "release_scope": [story.get("story_id") or story.get("task_id") for story in stories if isinstance(story, dict)],
        "doc_targets": ["docs", "tasks/runtime"],
        "retro_window": sprint_path.name,
        "next_recommended_actions": ["Use the retro output to tighten the next sprint workflow."],
    }

    document_release_bundle = generate_document_release_artifacts(repo_b_path, synthetic_state, synthetic_task)
    document_release_path = output_dir / "document_release_report.md"
    document_release_path.write_text(document_release_bundle["report"], encoding="utf-8")

    retro_bundle = generate_retro_artifacts(repo_b_path, synthetic_state, synthetic_task)
    retro_path = output_dir / "retro_report.md"
    retro_path.write_text(retro_bundle["report"], encoding="utf-8")

    ship_bundle = generate_ship_artifacts(repo_b_path, synthetic_state, synthetic_task)
    ship_advice_path = output_dir / "ship_advice.json"
    ship_advice_path.write_text(
        json.dumps(
            {
                "project": project,
                "sprint_id": sprint_path.name,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "advisory_modes": ["ship", "document-release", "retro"],
                "next_recommended_actions": ["Clear any ship blockers, then treat this sprint close bundle as the formal closeout source."],
                "ship_ready": ship_bundle["package"].get("ship_ready"),
                "blockers": ship_bundle["package"].get("blockers"),
                "ship_report_path": ship_bundle["report_path"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    sprint_close_bundle = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": project,
        "sprint_id": sprint_path.name,
        "document_release_path": str(document_release_path),
        "retro_path": str(retro_path),
        "ship_advice_path": str(ship_advice_path) if ship_advice_path else None,
    }
    runtime_validation_path: Path | None = None
    if project == "finahunt" and "low_position_one_shot_workbench" in sprint_path.name:
        runtime_validation = _run_finahunt_low_position_runtime_validation(repo_b_path, output_dir)
        runtime_validation_path = output_dir / "sprint_runtime_validation.json"
        runtime_validation_path.write_text(json.dumps(runtime_validation, ensure_ascii=False, indent=2), encoding="utf-8")
        sprint_close_bundle["runtime_validation_path"] = str(runtime_validation_path)

    sprint_close_bundle_path = output_dir / "sprint_close_bundle.json"
    sprint_close_bundle_path.write_text(json.dumps(sprint_close_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "document_release_path": str(document_release_path),
        "retro_path": str(retro_path),
        "ship_advice_path": str(ship_advice_path) if ship_advice_path else None,
        "ship_report_path": str(ship_bundle["report_path"]),
        "sprint_close_bundle_path": str(sprint_close_bundle_path),
        "runtime_validation_path": str(runtime_validation_path) if runtime_validation_path else None,
    }


def _load_story_payloads(sprint_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for story_file in sorted(sprint_dir.rglob("S*.yaml")):
        payload = yaml.safe_load(story_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _generate_sprint_framing_artifacts(
    repo_b_path: Path,
    sprint_path: Path,
    project: str,
    stories: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, str]:
    sprint_summary = _build_sprint_summary(sprint_path, stories)
    related_files = _aggregate_related_files(stories) or [str(sprint_path.relative_to(repo_b_path))]
    office_state = office_hours_node(
        {
            "repo_b_path": str(repo_b_path),
            "parsed_goal": sprint_summary["requirement_text"],
            "task_payload": {
                "project": project,
                "goal": sprint_summary["requirement_text"],
                "task_name": sprint_summary["title"],
                "workflow_enforcement_policy": "new_sprint",
                "auto_run": True,
                "interaction_policy": "non_interactive_auto_run",
                "office_hours_mode": "startup",
                "product_stage": "has-users",
                "audience": sprint_summary["audience"],
                "success_signal": sprint_summary["success_signals"],
                "acceptance_criteria": sprint_summary["success_signals"],
                "related_files": related_files,
            },
        }
    )
    plan_package = generate_plan_ceo_review_package(
        repo_b_path,
        project=project,
        requirement_text=sprint_summary["requirement_text"],
        title=sprint_summary["title"],
        constraints=sprint_summary["constraints"],
        success_signal=sprint_summary["success_signals"],
        audience=sprint_summary["audience"],
        delivery_mode="auto",
        review_mode="hold_scope",
        related_files=related_files,
        office_hours_summary=str(office_state.get("office_hours_summary") or "").strip() or None,
        strict_decisions=False,
    )
    framing_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": project,
        "sprint_id": sprint_path.name,
        "title": sprint_summary["title"],
        "audience": sprint_summary["audience"],
        "requirement_text": sprint_summary["requirement_text"],
        "related_files": related_files,
        "office_hours_dir": office_state.get("office_hours_dir"),
        "office_hours_summary": office_state.get("office_hours_summary"),
        "plan_ceo_review_report_path": plan_package["review_report_path"],
        "plan_ceo_requirement_doc_path": plan_package["requirement_doc_path"],
        "plan_ceo_decision_ceremony_path": plan_package["decision_ceremony_path"],
        "sprint_story_ids": [str(story.get("story_id") or story.get("task_id") or "").strip() for story in stories if str(story.get("story_id") or story.get("task_id") or "").strip()],
    }
    sprint_framing_path = output_dir / "sprint_framing_artifact.json"
    sprint_framing_path.write_text(json.dumps(framing_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sprint_framing_path": str(sprint_framing_path),
        "office_hours_path": str(Path(str(office_state.get("office_hours_dir") or "")).resolve() / "office_hours_report.md"),
        "plan_ceo_review_path": str(plan_package["review_report_path"]),
    }


def _build_sprint_summary(sprint_path: Path, stories: list[dict[str, Any]]) -> dict[str, Any]:
    sprint_plan_path = sprint_path / "sprint_plan.md"
    sprint_plan_text = sprint_plan_path.read_text(encoding="utf-8") if sprint_plan_path.exists() else ""
    title = sprint_path.name
    story_goals = [str(story.get("goal") or "").strip() for story in stories if str(story.get("goal") or "").strip()]
    requirement_text = (
        f"Sprint {sprint_path.name} should deliver the following story goals in one coordinated cycle:\n"
        + "\n".join(f"- {goal}" for goal in story_goals)
    )
    if sprint_plan_text.strip():
        requirement_text = sprint_plan_text.strip() + "\n\n" + requirement_text
    return {
        "title": title,
        "requirement_text": requirement_text,
        "audience": "The primary product operators and analysts who depend on this sprint outcome.",
        "constraints": [
            "Follow the formal story execution matrix.",
            "Do not skip review, QA, or sprint close evidence.",
        ],
        "success_signals": [
            "Every story in the sprint completes with formal evidence.",
            "Sprint-level framing, closeout, and acceptance artifacts are recorded.",
        ],
    }


def _aggregate_related_files(stories: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for story in stories:
        for key in ("primary_files", "related_files", "secondary_files"):
            raw = story.get(key)
            if isinstance(raw, list):
                values.extend(str(item).strip() for item in raw if str(item).strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _run_finahunt_low_position_runtime_validation(repo_b_path: Path, output_dir: Path) -> dict[str, Any]:
    command = [sys.executable, "tools\\run_low_position_workbench.py"]
    result = subprocess.run(
        command,
        cwd=str(repo_b_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload: dict[str, Any] = {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "validation_status": "failed" if result.returncode else "passed",
    }
    if result.returncode != 0:
        return payload

    try:
        runtime_output = json.loads(result.stdout)
    except Exception:
        payload["validation_status"] = "failed"
        payload["parse_error"] = "runtime validation output was not valid JSON"
        return payload

    artifact_batch_raw = str(runtime_output.get("artifact_batch_dir") or "").strip()
    artifact_batch_dir = Path(artifact_batch_raw).resolve() if artifact_batch_raw else None
    required_files = [
        "valuable_messages.json",
        "message_impact_analysis.json",
        "message_company_candidates.json",
        "message_reasoning.json",
        "message_scores.json",
        "daily_message_workbench.json",
        "daily_theme_workbench.json",
    ]
    existing_files = {path.name for path in artifact_batch_dir.glob("*.json")} if artifact_batch_dir and artifact_batch_dir.exists() else set()
    missing_files = [name for name in required_files if name not in existing_files]
    payload.update(
        {
            "runtime_output": runtime_output,
            "artifact_batch_dir": str(artifact_batch_dir) if artifact_batch_dir else "",
            "required_files": required_files,
            "missing_files": missing_files,
            "validation_status": "passed" if not missing_files else "failed",
        }
    )
    return payload


def _ensure_output_dir(project: str, sprint_id: str) -> Path:
    path = SPRINT_RUNS_DIR / project / sprint_id
    path.mkdir(parents=True, exist_ok=True)
    return path
