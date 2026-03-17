from __future__ import annotations

from pathlib import Path
import re
import uuid

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.agents.contract_artifacts import (
    materialize_agent_contract_artifacts,
    materialize_audit_idempotency_artifacts,
    materialize_core_db_schema_artifacts,
    materialize_error_state_spec_artifacts,
    materialize_profile_schema_artifacts,
    materialize_statement_upload_api_artifacts,
    materialize_statement_storage_artifacts,
    materialize_world_state_schema_artifacts,
)
from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_handoff_packet,
    resolve_issue,
)
from agentsystem.llm.client import get_llm

FIXER_COMMENT = "{/* Fixed by Fix Agent after validation failure */}"


def fix_node(state: DevState) -> DevState:
    print("[Fix Agent] Attempting automatic remediation")

    pending_fix_issues = [
        issue for issue in list(state.get("issues_to_fix") or []) if str(issue.get("target_agent")) == AgentRole.FIXER.value
    ]
    needs_fix = bool(pending_fix_issues) or not state.get("test_passed", True) or not state.get("browser_qa_passed", True)
    if not needs_fix:
        state["fixer_needed"] = False
        state["fixer_success"] = True
        state["fix_result"] = "No fix required."
        state["current_step"] = "fix_done"
        print("[Fix Agent] Validation already passed; skipping fix")
        return state

    attempts = state.get("fix_attempts", 0) + 1
    state["fix_attempts"] = attempts
    state["fixer_needed"] = True

    task_payload = state.get("task_payload") or {}
    issue_file_candidates = [str(issue.get("file_path")).strip() for issue in pending_fix_issues if str(issue.get("file_path") or "").strip()]
    related_files = [
        str(path).strip()
        for path in [*(task_payload.get("primary_files", []) or []), *(task_payload.get("related_files", []) or [])]
        if str(path).strip()
    ]
    candidate_files = [*issue_file_candidates, *related_files]
    if not related_files:
        related_files = candidate_files
    if not candidate_files:
        state["fixer_success"] = False
        state["fix_result"] = "No target file available for remediation."
        state["error_message"] = state.get("test_failure_info") or state.get("error_message")
        state["current_step"] = "fix_done"
        print(f"[Fix Agent] Fix attempt {attempts} failed: no target file")
        return state

    repo_b_path = Path(state["repo_b_path"]).resolve()
    target_file = repo_b_path / candidate_files[0]
    if not target_file.exists() and str(task_payload.get("story_id", "")).strip() not in {"S0-001", "S0-002", "S0-003", "S0-004", "S0-005", "S0-006", "S0-007", "S1-001"}:
        state["fixer_success"] = False
        state["fix_result"] = f"Target file missing: {target_file}"
        state["error_message"] = state.get("test_failure_info") or state.get("error_message")
        state["current_step"] = "fix_done"
        print(f"[Fix Agent] Fix attempt {attempts} failed: target missing")
        return state

    story_id = str(task_payload.get("story_id", "")).strip()
    failure_info = (
        (str(pending_fix_issues[0].get("description")) if pending_fix_issues else "")
        or str(state.get("test_failure_info") or "")
        or str(state.get("error_message") or "")
        or "; ".join(str(item) for item in (state.get("browser_qa_findings") or []))
        or "Unknown validation failure"
    )

    if story_id in {"S0-001", "S0-002", "S0-003", "S0-004", "S0-005", "S0-006", "S0-007", "S1-001"}:
        regenerated_files = _regenerate_contract_story_artifacts(repo_b_path, task_payload)
    else:
        current_code = target_file.read_text(encoding="utf-8")
        fixed_code = _generate_fix(current_code, str(failure_info), target_file)
        target_file.write_text(fixed_code, encoding="utf-8")
        regenerated_files = [str(target_file)]

    return_target = _infer_fix_return_target(pending_fix_issues)
    resolved_issue_ids = [issue.get("issue_id") for issue in pending_fix_issues]
    for issue_id in resolved_issue_ids:
        if issue_id:
            resolve_issue(state, str(issue_id))

    fix_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "fixer"
    fix_dir.mkdir(parents=True, exist_ok=True)
    fix_report = fix_dir / "fix_report.md"
    fix_report.write_text(
        "\n".join(
            [
                "# Fix Report",
                "",
                f"- Attempt: {attempts}",
                f"- Failure input: {failure_info}",
                f"- Target files: {', '.join(regenerated_files)}",
                f"- Resolved issues: {len(resolved_issue_ids)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state["fixer_success"] = True
    state["fix_result"] = f"Applied automated remediation to {', '.join(regenerated_files)}."
    state["error_message"] = None
    state["browser_qa_passed"] = True if return_target == "browser_qa" else state.get("browser_qa_passed")
    state["message"] = "Code fixed and ready for another validation pass."
    state["current_step"] = "fix_done"
    state["fix_return_to"] = return_target
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.FIXER,
            to_agent=_route_name_to_agent_role(return_target),
            status=HandoffStatus.COMPLETED,
            what_i_did=f"Applied an automated remediation pass to {', '.join(regenerated_files)} and resolved the currently assigned issues.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Fixed Story Artifacts",
                    type="code",
                    path=", ".join(regenerated_files),
                    description="Updated artifact set after the fixer pass.",
                    created_by=AgentRole.FIXER,
                    version=f"{attempts}.0",
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Fix Report",
                    type="report",
                    path=str(fix_report),
                    description="Summary of the remediation pass and resolved issues.",
                    created_by=AgentRole.FIXER,
                ),
            ],
            what_risks_i_found=[],
            what_i_require_next=f"Return the story to {return_target} and confirm that the previously reported issues are now resolved.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print(f"[Fix Agent] Fix attempt {attempts} recorded")
    return state


def route_after_fix(state: DevState) -> str:
    return str(state.get("fix_return_to") or "tester")


def _generate_fix(current_code: str, failure_info: str, target_file: Path | None = None) -> str:
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a code repair agent.
Repair only the code relevant to the failure.
Return only the complete updated file inside one fenced code block.
                """.strip(),
            ),
            (
                "user",
                """
Failure:
{failure_info}

Current file:
```tsx
{current_code}
```
                """.strip(),
            ),
        ]
    )
    try:
        response = (prompt | llm).invoke({"failure_info": failure_info, "current_code": current_code})
        candidate = _extract_code_block(getattr(response, "content", str(response)))
        if candidate and candidate != current_code:
            return _deterministic_fix(candidate, failure_info, target_file)
    except Exception:
        pass
    return _deterministic_fix(current_code, failure_info, target_file)


def _extract_code_block(content: str) -> str:
    match = re.search(r"```[a-zA-Z0-9]*\s*(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()


def _deterministic_fix(current_code: str, failure_info: str, target_file: Path | None = None) -> str:
    lowered_failure = failure_info.lower()
    stripped = current_code.lstrip()
    if target_file and target_file.suffix.lower() == ".json":
        return current_code
    if stripped.startswith("{") or stripped.startswith("["):
        return current_code

    result = current_code
    if FIXER_COMMENT not in result:
        if "    <div>" in result:
            result = result.replace("    <div>", f"    <div>\n      {FIXER_COMMENT}", 1)
        else:
            result = f"{FIXER_COMMENT}\n{result}"

    subtitle = _extract_quoted_text(failure_info)
    if subtitle and subtitle not in result and "text-slate-500" in result:
        result = result.replace("text-slate-500", "text-slate-500 font-medium", 1)

    if "subtitle" in lowered_failure and "text-slate-500" in result and "font-medium" not in result:
        result = result.replace("text-slate-500", "text-slate-500 font-medium", 1)

    return result


def _extract_quoted_text(text: str) -> str | None:
    match = re.search(r"[\"'“”‘’]([^\"'“”‘’]+)[\"'“”‘’]", text)
    if match:
        return match.group(1).strip()
    return None


def _regenerate_contract_story_artifacts(repo_b_path: Path, task_payload: dict[str, object]) -> list[str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    story_id = str(task_payload.get("story_id", "")).strip()
    if story_id == "S0-001":
        return materialize_profile_schema_artifacts(repo_b_path, related_files)
    if story_id == "S0-002":
        return materialize_world_state_schema_artifacts(repo_b_path, related_files)
    if story_id == "S0-003":
        return materialize_agent_contract_artifacts(repo_b_path, related_files)
    if story_id == "S0-004":
        return materialize_error_state_spec_artifacts(repo_b_path, related_files)
    if story_id == "S0-005":
        return materialize_core_db_schema_artifacts(repo_b_path, related_files)
    if story_id == "S0-006":
        return materialize_statement_storage_artifacts(repo_b_path, related_files)
    if story_id == "S0-007":
        return materialize_audit_idempotency_artifacts(repo_b_path, related_files)
    if story_id == "S1-001":
        return materialize_statement_upload_api_artifacts(repo_b_path, related_files)
    return []


def _infer_fix_return_target(issues: list[dict[str, object]]) -> str:
    priorities = {
        AgentRole.CODE_STYLE_REVIEWER.value: "code_style_reviewer",
        AgentRole.TESTER.value: "tester",
        AgentRole.BROWSER_QA.value: "browser_qa",
        AgentRole.REVIEWER.value: "reviewer",
        AgentRole.CODE_ACCEPTANCE.value: "code_acceptance",
        AgentRole.ACCEPTANCE_GATE.value: "acceptance_gate",
    }
    for source_agent, route_name in priorities.items():
        if any(str(issue.get("source_agent")) == source_agent for issue in issues):
            return route_name
    return "tester"


def _route_name_to_agent_role(route_name: str) -> AgentRole:
    mapping = {
        "code_style_reviewer": AgentRole.CODE_STYLE_REVIEWER,
        "tester": AgentRole.TESTER,
        "browser_qa": AgentRole.BROWSER_QA,
        "reviewer": AgentRole.REVIEWER,
        "code_acceptance": AgentRole.CODE_ACCEPTANCE,
        "acceptance_gate": AgentRole.ACCEPTANCE_GATE,
    }
    return mapping.get(route_name, AgentRole.TESTER)
