from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_executed_mode,
    add_handoff_packet,
)


def generate_ship_artifacts(repo_b_path: str | Path, state: dict[str, Any], task_payload: dict[str, Any]) -> dict[str, Any]:
    repo_path = Path(repo_b_path).resolve()
    ship_dir = repo_path.parent / ".meta" / repo_path.name / "ship"
    ship_dir.mkdir(parents=True, exist_ok=True)

    git = GitAdapter(repo_path)
    release_scope = [str(item).strip() for item in (task_payload.get("release_scope") or state.get("release_scope") or []) if str(item).strip()]
    staged_files = git.get_staged_files()
    diff_text = git.get_diff()
    diff_stat = _safe_git_stat(git)
    commit_log = _safe_git_log(git)

    validation = {
        "test_passed": bool(state.get("test_passed")),
        "review_passed": bool(state.get("review_passed")),
        "code_acceptance_passed": bool(state.get("code_acceptance_passed")),
        "acceptance_passed": bool(state.get("acceptance_passed")),
        "browser_qa_health_score": state.get("browser_qa_health_score"),
        "document_release_pending": not bool(state.get("document_release_success")),
    }
    pre_landing_review = {
        "staged_files": staged_files,
        "diff_line_count": len(diff_text.splitlines()) if diff_text else 0,
        "diff_stat": diff_stat,
        "commit_log": commit_log,
    }
    package = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "branch": git.get_current_branch(),
        "commit": git.get_current_commit(),
        "dirty": git.is_dirty(),
        "release_scope": release_scope,
        "validation": validation,
        "pre_landing_review": pre_landing_review,
    }
    blockers = _ship_blockers(package)
    closeout_checklist = _build_closeout_checklist(package)
    coverage_audit = _build_coverage_audit(state, release_scope, staged_files)
    release_version = _build_release_version(repo_path, diff_text)
    changelog_draft = _build_changelog_draft(release_scope, staged_files, blockers, validation)
    pr_draft = _build_pr_draft(repo_path, release_scope, blockers, changelog_draft)
    package["blockers"] = blockers
    package["closeout_checklist"] = closeout_checklist
    package["ship_ready"] = not blockers
    package["coverage_audit"] = coverage_audit
    package["release_version"] = release_version

    report_lines = [
        "# Ship Readiness Report",
        "",
        f"- Generated At: {package['generated_at']}",
        f"- Branch: {package['branch'] or 'n/a'}",
        f"- Commit: {package['commit'] or 'n/a'}",
        f"- Dirty tree: {'yes' if package['dirty'] else 'no'}",
        f"- Ship ready: {'yes' if package['ship_ready'] else 'no'}",
        "",
        "## Release Scope",
        *([f"- {item}" for item in release_scope] or ["- No explicit release scope declared."]),
        "",
        "## Validation",
        f"- Tests: {'PASS' if validation['test_passed'] else 'FAIL'}",
        f"- Review: {'PASS' if validation['review_passed'] else 'FAIL'}",
        f"- Code Acceptance: {'PASS' if validation['code_acceptance_passed'] else 'FAIL'}",
        f"- Acceptance Gate: {'PASS' if validation['acceptance_passed'] else 'FAIL'}",
        f"- Browser QA health score: {validation['browser_qa_health_score'] if validation['browser_qa_health_score'] is not None else '-'}",
        "",
        "## Pre-Landing Review",
        f"- Staged files: {len(staged_files)}",
        f"- Diff lines: {pre_landing_review['diff_line_count']}",
        *([f"- Diff stat: {item}" for item in diff_stat] or ["- Diff stat unavailable."]),
        *([f"- Commit log: {item}" for item in commit_log] or ["- Commit log unavailable."]),
        "",
        "## Blockers",
        *([f"- {item}" for item in blockers] or ["- None."]),
        "",
        "## Coverage Audit",
        f"- Required modes: {', '.join(coverage_audit['required_modes']) if coverage_audit['required_modes'] else 'none'}",
        f"- Executed modes: {', '.join(coverage_audit['executed_modes']) if coverage_audit['executed_modes'] else 'none'}",
        f"- Accepted: {'yes' if coverage_audit['accepted'] else 'no'}",
        "",
        "## Release Version",
        f"- Current: {release_version['current_version'] or 'n/a'}",
        f"- Next: {release_version['next_version']}",
        "",
        "## Closeout Checklist",
        *[f"- {item['name']}: {item['status']} - {item['detail']}" for item in closeout_checklist],
        "",
        "## Next Step",
        "- Continue into document-release if ship_ready is true, otherwise clear blockers before treating the story or sprint as releasable.",
        "",
    ]
    report = "\n".join(report_lines)

    report_path = ship_dir / "ship_readiness_report.md"
    report_path.write_text(report, encoding="utf-8")
    package_path = ship_dir / "release_package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_path = ship_dir / "closeout_checklist.json"
    checklist_path.write_text(json.dumps(closeout_checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    coverage_audit_path = ship_dir / "coverage_audit.json"
    coverage_audit_path.write_text(json.dumps(coverage_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    release_version_path = ship_dir / "release_version.json"
    release_version_path.write_text(json.dumps(release_version, ensure_ascii=False, indent=2), encoding="utf-8")
    changelog_draft_path = ship_dir / "changelog_draft.md"
    changelog_draft_path.write_text(changelog_draft, encoding="utf-8")
    pr_draft_path = ship_dir / "pr_draft.md"
    pr_draft_path.write_text(pr_draft, encoding="utf-8")
    return {
        "dir": str(ship_dir),
        "report": report,
        "report_path": str(report_path),
        "package": package,
        "package_path": str(package_path),
        "checklist_path": str(checklist_path),
        "coverage_audit_path": str(coverage_audit_path),
        "release_version_path": str(release_version_path),
        "changelog_draft_path": str(changelog_draft_path),
        "pr_draft_path": str(pr_draft_path),
    }


def ship_node(state: DevState) -> DevState:
    task_payload = state.get("task_payload") or {}
    artifacts = generate_ship_artifacts(state["repo_b_path"], state, task_payload)
    state["ship_success"] = True
    state["ship_dir"] = artifacts["dir"]
    state["ship_report"] = artifacts["report"]
    state["ship_release_package"] = artifacts["package"]
    state["ship_closeout_checklist"] = artifacts["package"].get("closeout_checklist") or []
    state["ship_coverage_audit_path"] = artifacts["coverage_audit_path"]
    state["ship_release_version_path"] = artifacts["release_version_path"]
    state["ship_changelog_draft_path"] = artifacts["changelog_draft_path"]
    state["ship_pr_draft_path"] = artifacts["pr_draft_path"]
    state["current_step"] = "ship_done"
    state["error_message"] = None
    add_executed_mode(state, "ship")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.SHIP,
            to_agent=AgentRole.DOCUMENT_RELEASE,
            status=HandoffStatus.COMPLETED,
            what_i_did="Collected release scope, validation state, diff discipline, and blockers into a closeout package.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Ship Readiness Report",
                    type="report",
                    path=str(artifacts["report_path"]),
                    description="Release-readiness report with diff scope, validation, and blockers.",
                    created_by=AgentRole.SHIP,
                )
            ],
            what_risks_i_found=[str(item) for item in artifacts["package"].get("blockers") or []],
            what_i_require_next="Sync release-facing documentation, then only treat the work as shippable if the blocker list stays empty.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_ship(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "ship":
        return "__end__"
    return "document_release"


def _ship_blockers(package: dict[str, Any]) -> list[str]:
    validation = package.get("validation") or {}
    blockers: list[str] = []
    if package.get("dirty"):
        blockers.append("The working tree is still dirty, so the release evidence is not stable yet.")
    if not validation.get("test_passed"):
        blockers.append("Automated tests are not passing yet.")
    if not validation.get("review_passed"):
        blockers.append("Review has not passed yet.")
    if not validation.get("code_acceptance_passed"):
        blockers.append("Code acceptance has not passed yet.")
    if not validation.get("acceptance_passed"):
        blockers.append("Acceptance gate has not passed yet.")
    browser_score = validation.get("browser_qa_health_score")
    if browser_score is not None and int(browser_score) < 80:
        blockers.append("Browser QA health score is too low for confident release.")
    return blockers


def _build_closeout_checklist(package: dict[str, Any]) -> list[dict[str, str]]:
    validation = package.get("validation") or {}
    pre_landing = package.get("pre_landing_review") or {}
    release_scope = package.get("release_scope") or []
    checklist = [
        {
            "name": "release_scope",
            "status": "ready" if release_scope else "needs_review",
            "detail": "Release scope was declared." if release_scope else "Declare release scope before formal ship sign-off.",
        },
        {
            "name": "validation",
            "status": "ready" if all(bool(validation.get(key)) for key in ("test_passed", "review_passed", "code_acceptance_passed", "acceptance_passed")) else "blocked",
            "detail": "Core validation gates are green." if all(bool(validation.get(key)) for key in ("test_passed", "review_passed", "code_acceptance_passed", "acceptance_passed")) else "At least one validation gate is still failing.",
        },
        {
            "name": "diff_discipline",
            "status": "ready" if int(pre_landing.get("diff_line_count") or 0) >= 0 else "needs_review",
            "detail": "Diff stat and staged-file review were collected for pre-landing review.",
        },
        {
            "name": "document_release",
            "status": "pending" if validation.get("document_release_pending") else "ready",
            "detail": "Document-release still needs to run." if validation.get("document_release_pending") else "Document-release already completed for this cycle.",
        },
    ]
    return checklist


def _safe_git_stat(git: GitAdapter) -> list[str]:
    try:
        output = git.repo.git.show("--stat", "--format=", "HEAD")
    except Exception:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _safe_git_log(git: GitAdapter) -> list[str]:
    try:
        output = git.repo.git.log("--oneline", "-5")
    except Exception:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _build_coverage_audit(
    state: dict[str, Any],
    release_scope: list[str],
    staged_files: list[str],
) -> dict[str, Any]:
    return {
        "release_scope": list(release_scope),
        "staged_file_count": len(staged_files),
        "executed_modes": list(state.get("executed_modes") or []),
        "required_modes": list(state.get("required_modes") or []),
        "agent_mode_coverage": dict(state.get("agent_mode_coverage") or {}),
        "implemented": bool(state.get("test_passed") is not None),
        "verified": bool(state.get("test_passed")),
        "agentized": bool((state.get("agent_mode_coverage") or {}).get("all_required_executed")),
        "accepted": bool(state.get("acceptance_passed")),
    }


def _build_release_version(repo_path: Path, diff_text: str) -> dict[str, Any]:
    current = _discover_current_version(repo_path)
    next_version = _suggest_next_version(current, diff_text)
    return {
        "current_version": current,
        "next_version": next_version,
        "strategy": "local_patch_candidate" if current else "local_bootstrap_candidate",
    }


def _discover_current_version(repo_path: Path) -> str | None:
    candidates = [
        repo_path / "pyproject.toml",
        repo_path / "package.json",
        repo_path / "VERSION",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        if candidate.name == "VERSION":
            value = text.strip()
            return value or None
        for line in text.splitlines():
            normalized = line.strip()
            if normalized.startswith("version"):
                parts = normalized.replace('"', "'").split("'")
                if len(parts) >= 2 and parts[1].strip():
                    return parts[1].strip()
    return None


def _suggest_next_version(current: str | None, diff_text: str) -> str:
    if not current:
        return "0.0.1-local"
    pieces = current.split(".")
    if len(pieces) < 3 or not all(part.isdigit() for part in pieces[:3]):
        return f"{current}-local"
    major, minor, patch = (int(pieces[0]), int(pieces[1]), int(pieces[2]))
    if "BREAKING CHANGE" in diff_text or "migration" in diff_text.lower():
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _build_changelog_draft(
    release_scope: list[str],
    staged_files: list[str],
    blockers: list[str],
    validation: dict[str, Any],
) -> str:
    lines = [
        "# Changelog Draft",
        "",
        "## Scope",
        *([f"- {item}" for item in release_scope] or ["- No explicit release scope declared."]),
        "",
        "## Files Touched",
        *([f"- {item}" for item in staged_files] or ["- No staged files detected."]),
        "",
        "## Validation",
        f"- Tests: {'PASS' if validation.get('test_passed') else 'FAIL'}",
        f"- Review: {'PASS' if validation.get('review_passed') else 'FAIL'}",
        f"- Acceptance: {'PASS' if validation.get('acceptance_passed') else 'FAIL'}",
        "",
        "## Remaining Blockers",
        *([f"- {item}" for item in blockers] or ["- None."]),
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def _build_pr_draft(
    repo_path: Path,
    release_scope: list[str],
    blockers: list[str],
    changelog_draft: str,
) -> str:
    scope_summary = ", ".join(release_scope) if release_scope else "current release scope"
    return (
        f"# PR Draft for {repo_path.name}\n\n"
        f"## Summary\n- Ship {scope_summary}.\n\n"
        "## Checklist\n"
        f"{''.join(f'- [ ] {item}\\n' for item in (blockers or ['No remaining blockers.']))}\n"
        "## Changelog\n"
        f"{changelog_draft}"
    )
