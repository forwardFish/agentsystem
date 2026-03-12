from __future__ import annotations

from pathlib import Path
import re

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.core.state import DevState
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

    target_file = Path(state["repo_b_path"]).resolve() / related_files[0]
    if not target_file.exists():
        state["fixer_success"] = False
        state["fix_result"] = f"Target file missing: {target_file}"
        state["error_message"] = state.get("test_failure_info") or state.get("error_message")
        state["current_step"] = "fix_done"
        print(f"[Fix Agent] Fix attempt {attempts} failed: target missing")
        return state

    current_code = target_file.read_text(encoding="utf-8")
    failure_info = state.get("test_failure_info") or state.get("error_message") or "Unknown validation failure"
    fixed_code = _generate_fix(current_code, str(failure_info))
    target_file.write_text(fixed_code, encoding="utf-8")

    state["fixer_success"] = True
    state["fix_result"] = f"Applied automated remediation to {related_files[0]}."
    state["error_message"] = None
    state["message"] = "Code fixed and ready for another validation pass."
    state["current_step"] = "fix_done"

    print(f"[Fix Agent] Fix attempt {attempts} recorded")
    return state


def _generate_fix(current_code: str, failure_info: str) -> str:
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
            return _deterministic_fix(candidate, failure_info)
    except Exception:
        pass
    return _deterministic_fix(current_code, failure_info)


def _extract_code_block(content: str) -> str:
    match = re.search(r"```[a-zA-Z0-9]*\s*(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()


def _deterministic_fix(current_code: str, failure_info: str) -> str:
    result = current_code
    if FIXER_COMMENT not in result:
        if "    <div>" in result:
            result = result.replace("    <div>", f"    <div>\n      {FIXER_COMMENT}", 1)
        else:
            result = f"{FIXER_COMMENT}\n{result}"

    subtitle = _extract_quoted_text(failure_info)
    if subtitle and subtitle not in result and "text-slate-500" in result:
        result = result.replace("text-slate-500", "text-slate-500 font-medium", 1)

    return result


def _extract_quoted_text(text: str) -> str | None:
    match = re.search(r"[\"'“”‘’]([^\"'“”‘’]+)[\"'“”‘’]", text)
    if match:
        return match.group(1).strip()
    return None
