from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from agentsystem.orchestration.story_contracts import (
    build_artifact_inventory,
    build_implementation_contract,
    collect_file_scope,
)


PLACEHOLDER_MARKERS = (
    "/* fixed by fix agent",
    "<h1 classname=",
    "agent 实时观测面板",
    "agent 瀹炴椂瑙傛祴闈㈡澘",
)

CROSS_LANGUAGE_MARKERS = (
    "<h1",
    "className=",
    "export default function",
    "</div>",
)


def evaluate_quality_sentry(
    repo_root: str | Path,
    task_payload: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_root).resolve()
    scoped_files = _merge_paths(changed_files or [], collect_file_scope(task_payload))
    implementation_contract = dict(task_payload.get("implementation_contract") or build_implementation_contract(task_payload))
    inventory = build_artifact_inventory(scoped_files)
    issues: list[dict[str, str]] = []
    syntax_checked_files: list[str] = []
    placeholder_rejections: list[str] = []

    for relative_path in scoped_files:
        absolute_path = repo_path / relative_path
        if not absolute_path.exists() or not absolute_path.is_file():
            continue
        file_issues = inspect_file_quality(absolute_path, relative_path)
        if absolute_path.suffix.lower() == ".py":
            syntax_checked_files.append(relative_path)
        for issue in file_issues:
            issues.append(issue)
            if issue["issue_type"] == "placeholder_artifact":
                placeholder_rejections.append(relative_path)

    issues.extend(_integration_issues(repo_path, task_payload, implementation_contract, inventory, state))
    issues.extend(_agent_contract_issues(task_payload, state))

    blocking_issue_types = sorted({item["issue_type"] for item in issues})
    integration_contract_passed = "integration_missing" not in blocking_issue_types
    agent_contract_satisfaction = "agent_contract_missing" not in blocking_issue_types
    gstack_parity_satisfaction = _gstack_parity_satisfaction(task_payload, state)
    return {
        "issues": issues,
        "blocking_issue_types": blocking_issue_types,
        "syntax_checked_files": syntax_checked_files,
        "placeholder_rejections": placeholder_rejections,
        "artifact_inventory": inventory,
        "integration_contract_passed": integration_contract_passed,
        "agent_contract_satisfaction": agent_contract_satisfaction,
        "gstack_parity_satisfaction": gstack_parity_satisfaction,
        "required_artifact_types": list(implementation_contract.get("required_artifact_types") or []),
    }


def evaluate_quality_sentry_for_state(
    state: dict[str, Any],
    repo_root: str | Path,
    *,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    quality = evaluate_quality_sentry(
        repo_root,
        dict(state.get("task_payload") or {}),
        state=state,
        changed_files=changed_files,
    )
    state["quality_sentry"] = quality
    state["blocking_issue_types"] = quality["blocking_issue_types"]
    state["delivery_evidence"] = quality["artifact_inventory"]
    state["required_artifact_types"] = quality["required_artifact_types"]
    state["agent_contract_satisfaction"] = quality["agent_contract_satisfaction"]
    state["gstack_parity_satisfaction"] = quality["gstack_parity_satisfaction"]
    return quality


def inspect_file_quality(path: Path, relative_path: str) -> list[dict[str, str]]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [
            {
                "issue_type": "syntax_invalid",
                "file": relative_path,
                "detail": f"File is not readable as UTF-8: {exc}",
            }
        ]

    issues: list[dict[str, str]] = []
    if _should_check_placeholder(path) and _is_placeholder_artifact(content):
        issues.append(
            {
                "issue_type": "placeholder_artifact",
                "file": relative_path,
                "detail": "File contains only placeholder markers, comments, or future-import shell content.",
            }
        )
    if path.suffix.lower() == ".py":
        if _has_cross_language_contamination(content):
            issues.append(
                {
                    "issue_type": "cross_language_contamination",
                    "file": relative_path,
                    "detail": "Python source contains JSX/TSX or browser UI markup.",
                }
            )
        try:
            ast.parse(content)
        except SyntaxError as exc:
            issues.append(
                {
                    "issue_type": "syntax_invalid",
                    "file": relative_path,
                    "detail": f"Python AST parse failed: {exc.msg}",
                }
            )
    return issues


def _integration_issues(
    repo_root: Path,
    task_payload: dict[str, Any],
    implementation_contract: dict[str, Any],
    inventory: dict[str, list[str]],
    state: dict[str, Any] | None,
) -> list[dict[str, str]]:
    required_artifacts = [str(item) for item in (implementation_contract.get("required_artifact_types") or []) if str(item).strip()]
    present_types = {key for key, files in inventory.items() if files}
    issues: list[dict[str, str]] = []

    for artifact_type in required_artifacts:
        if artifact_type in {"browser_evidence", "design_evidence"}:
            if not _evidence_present(task_payload, state, artifact_type):
                issues.append(
                    {
                        "issue_type": "integration_missing",
                        "file": "",
                        "detail": f"Missing required {artifact_type} for the current story contract.",
                    }
                )
            continue
        if artifact_type not in present_types:
            issues.append(
                {
                    "issue_type": "integration_missing",
                    "file": "",
                    "detail": f"Missing required artifact type: {artifact_type}",
                }
            )

    if implementation_contract.get("story_track") == "api_domain":
        for artifact_type in ("route", "service", "container_wiring", "tests"):
            if artifact_type not in present_types:
                issues.append(
                    {
                        "issue_type": "integration_missing",
                        "file": "",
                        "detail": f"API story is missing {artifact_type}.",
                    }
                )
        if _should_enforce_qa_evidence(state) and not _evidence_present(task_payload, state, "qa_evidence"):
            issues.append(
                {
                    "issue_type": "integration_missing",
                    "file": "",
                    "detail": "API story is missing QA evidence.",
                }
            )
    return issues


def _agent_contract_issues(task_payload: dict[str, Any], state: dict[str, Any] | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    expanded_agents = [str(item).strip() for item in (task_payload.get("expanded_required_agents") or []) if str(item).strip()]
    execution_contract = task_payload.get("agent_execution_contract")
    if not expanded_agents or not isinstance(execution_contract, list) or not execution_contract:
        issues.append(
            {
                "issue_type": "agent_contract_missing",
                "file": "",
                "detail": "Task payload is missing expanded_required_agents or agent_execution_contract.",
            }
        )
        return issues

    coverage = {}
    if isinstance(state, dict):
        coverage = state.get("agent_mode_coverage") if isinstance(state.get("agent_mode_coverage"), dict) else {}
    missing_required = list((coverage or {}).get("missing_required") or [])
    if missing_required:
        issues.append(
            {
                "issue_type": "agent_contract_missing",
                "file": "",
                "detail": "Required workflow modes are missing: " + ", ".join(missing_required),
            }
        )
    return issues


def _gstack_parity_satisfaction(task_payload: dict[str, Any], state: dict[str, Any] | None) -> bool:
    coverage = {}
    if isinstance(state, dict):
        coverage = state.get("agent_mode_coverage") if isinstance(state.get("agent_mode_coverage"), dict) else {}
    if coverage:
        return bool(coverage.get("all_required_executed"))
    return bool(task_payload.get("required_modes"))


def _evidence_present(task_payload: dict[str, Any], state: dict[str, Any] | None, artifact_type: str) -> bool:
    if artifact_type == "browser_evidence":
        candidates = [
            task_payload.get("browse_report"),
            task_payload.get("design_contract_path"),
            (state or {}).get("browse_report"),
            (state or {}).get("browser_qa_report"),
        ]
        return any(str(item or "").strip() for item in candidates)
    if artifact_type == "design_evidence":
        candidates = [
            task_payload.get("design_contract_path"),
            (state or {}).get("design_contract_path"),
            (state or {}).get("qa_design_review_report"),
        ]
        return any(str(item or "").strip() for item in candidates)
    if artifact_type == "qa_evidence":
        candidates = [
            (state or {}).get("runtime_qa_report"),
            (state or {}).get("browser_qa_report"),
            (state or {}).get("test_results"),
        ]
        return any(str(item or "").strip() for item in candidates)
    return False


def _should_enforce_qa_evidence(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    current_step = str(state.get("current_step") or "").strip().lower()
    if current_step in {"runtime_qa_done", "review_done", "acceptance_done", "code_acceptance_done"}:
        return True
    return any(
        bool(state.get(key))
        for key in ("runtime_qa_report", "browser_qa_report", "review_passed", "code_acceptance_passed", "acceptance_passed")
    )


def _has_cross_language_contamination(content: str) -> bool:
    stripped = content.lstrip()
    if stripped.startswith("/*") or stripped.startswith("<"):
        return True
    lowered = content.lower()
    if "return (" in lowered and any(marker in lowered for marker in ("classname=", "<div", "<section", "<main", "<h1", "</div>")):
        return True
    return any(marker.lower() in lowered for marker in CROSS_LANGUAGE_MARKERS)


def _is_placeholder_artifact(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return True
    lowered_lines = [line.lower() for line in lines]
    if len(lines) == 1 and lowered_lines[0] == "from __future__ import annotations":
        return True
    if all(_is_comment_or_marker(line) for line in lowered_lines):
        return True
    non_comment = [line for line in lowered_lines if not _is_comment_or_marker(line)]
    return bool(non_comment) and all(line == "from __future__ import annotations" for line in non_comment) and any(
        _is_comment_or_marker(line) for line in lowered_lines
    )


def _should_check_placeholder(path: Path) -> bool:
    return path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml"}


def _is_comment_or_marker(line: str) -> bool:
    if any(marker in line for marker in PLACEHOLDER_MARKERS):
        return True
    return line.startswith(("#", "//", "/*", "*", "*/", "<h1"))


def _merge_paths(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for value in group:
            marker = str(value).strip().replace("\\", "/")
            if not marker or marker in seen:
                continue
            seen.add(marker)
            merged.append(marker)
    return merged
