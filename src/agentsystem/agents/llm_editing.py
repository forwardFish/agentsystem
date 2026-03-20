from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.llm.client import get_llm


def llm_rewrite_file(
    repo_b_path: str | Path,
    task_payload: dict[str, Any] | None,
    target_file: str | Path,
    *,
    system_role: str,
) -> str | None:
    repo_root = Path(repo_b_path).resolve()
    target_path = Path(target_file)
    if not target_path.is_absolute():
        target_path = repo_root / target_path

    current_code = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    assembler = ContextAssembler(repo_root)
    constitution = assembler.build_constitution()
    task_context = assembler.build_task_context(task_payload)
    suffix = target_path.suffix.lower().lstrip(".") or "text"
    fenced_type = "tsx" if suffix in {"tsx", "jsx"} else ("python" if suffix == "py" else suffix)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a {system_role}.
Follow the repository constitution and the task context strictly.
Only rewrite the single target file.
Return only the complete updated file inside one fenced code block.

## Constitution
{constitution}

## Task Context
{task_context}
                """.strip(),
            ),
            (
                "user",
                """
Target file: {target_file}
Task goal: {task_goal}
Acceptance criteria:
{acceptance_criteria}

Current file:
```{fenced_type}
{current_code}
```
                """.strip(),
            ),
        ]
    )

    response = (prompt | get_llm()).invoke(
        {
            "system_role": system_role,
            "constitution": constitution,
            "task_context": task_context,
            "target_file": str(target_path.relative_to(repo_root)).replace("\\", "/"),
            "task_goal": str((task_payload or {}).get("goal", "")).strip(),
            "acceptance_criteria": "\n".join(
                f"- {item}" for item in (task_payload or {}).get("acceptance_criteria", []) if isinstance(item, str)
            ),
            "fenced_type": fenced_type,
            "current_code": current_code,
        }
    )
    content = str(getattr(response, "content", response)).strip()
    return _extract_code_block(content) or current_code or None


def _extract_code_block(content: str) -> str:
    match = re.search(r"```[a-zA-Z0-9_-]*\s*(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    stripped = content.strip()
    return stripped or ""
