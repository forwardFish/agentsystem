from __future__ import annotations

import os
import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

TITLE_TEXT = "Agent \u5b9e\u65f6\u89c2\u6d4b\u9762\u677f"


def _extract_code(prompt_text: str) -> tuple[str, str]:
    matches = re.findall(r"```([a-zA-Z0-9_+-]*)\s*(.*?)```", prompt_text, re.DOTALL)
    if matches:
        fence, code = matches[-1]
        return fence or "text", code.strip()
    return "text", prompt_text.strip()


def _fallback_invoke(prompt_value) -> AIMessage:
    if hasattr(prompt_value, "messages") and prompt_value.messages:
        prompt_text = prompt_value.messages[-1].content
    else:
        prompt_text = prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
    fence, current_code = _extract_code(prompt_text)
    return AIMessage(content=f"```{fence}\n{current_code}\n```")


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if api_key:
        return ChatOpenAI(model=model, api_key=api_key, temperature=0)
    return RunnableLambda(_fallback_invoke)
