from __future__ import annotations

import os
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

TITLE_TEXT = "Agent \u5b9e\u65f6\u89c2\u6d4b\u9762\u677f"


def _extract_code(prompt_text: str) -> str:
    matches = re.findall(r"```tsx\s*(.*?)```", prompt_text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return prompt_text.strip()


def _apply_fallback_edit(code: str) -> str:
    marker = f'      <h1 className="mb-6 text-3xl font-bold">{TITLE_TEXT}</h1>'
    if TITLE_TEXT in code:
        return code

    if "    <div>" in code:
        return code.replace("    <div>", f"    <div>\n{marker}", 1)
    return f"{marker}\n{code}"


def _fallback_invoke(prompt_value) -> AIMessage:
    if hasattr(prompt_value, "messages") and prompt_value.messages:
        prompt_text = prompt_value.messages[-1].content
    else:
        prompt_text = prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
    current_code = _extract_code(prompt_text)
    updated_code = _apply_fallback_edit(current_code)
    return AIMessage(content=f"```tsx\n{updated_code}\n```")


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if api_key:
        return ChatOpenAI(model=model, api_key=api_key, temperature=0)
    return RunnableLambda(_fallback_invoke)
