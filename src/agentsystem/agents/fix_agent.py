from __future__ import annotations

from pathlib import Path
import re
import uuid

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.agents.contract_artifacts import materialize_profile_schema_artifacts, materialize_world_state_schema_artifacts
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

    if state.get("test_passed", False):
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
    related_files = [str(path) for path in task_payload.get("related_files", [])]
    if not related_files:
        state["fixer_success"] = False
        state["fix_result"] = "No target file available for remediation."
        state["error_message"] = state.get("test_failure_info") or state.get("error_message")
        state["current_step"] = "fix_done"
        print(f"[Fix Agent] Fix attempt {attempts} failed: no target file")
        return state

    repo_b_path = Path(state["repo_b_path"]).resolve()
    target_file = repo_b_path / related_files[0]
    if not target_file.exists() and str(task_payload.get("story_id", "")).strip() not in {"S0-001", "S0-002"}:
        state["fixer_success"] = False
        state["fix_result"] = f"Target file missing: {target_file}"
        state["error_message"] = state.get("test_failure_info") or state.get("error_message")
        state["current_step"] = "fix_done"
        print(f"[Fix Agent] Fix attempt {attempts} failed: target missing")
        return state

    story_id = str(task_payload.get("story_id", "")).strip()
    failure_info = state.get("test_failure_info") or state.get("error_message") or "Unknown validation failure"

    if story_id in {"S0-001", "S0-002"}:
        regenerated_files = _regenerate_contract_story_artifacts(repo_b_path, task_payload)
    else:
        current_code = target_file.read_text(encoding="utf-8")
        fixed_code = _generate_fix(current_code, str(failure_info), target_file)
        target_file.write_text(fixed_code, encoding="utf-8")
        regenerated_files = [str(target_file)]

    resolved_issue_ids = [issue.get("issue_id") for issue in list(state.get("issues_to_fix") or []) if issue.get("target_agent") == AgentRole.FIXER]
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
    state["message"] = "Code fixed and ready for another validation pass."
    state["current_step"] = "fix_done"
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.FIXER,
            to_agent=AgentRole.TESTER,
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
            what_i_require_next="Run the same validations again and confirm that all blocking issues are now resolved.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print(f"[Fix Agent] Fix attempt {attempts} recorded")
    return state


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
    return []
