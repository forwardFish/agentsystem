from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.llm.client import get_llm


class LlmClientTestCase(unittest.TestCase):
    def test_fallback_client_preserves_requested_fence_without_injecting_heading(self) -> None:
        original_api_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "Return updated Python only."),
                    (
                        "user",
                        """
Current file:
```python
{current_code}
```
""".strip(),
                    ),
                ]
            )

            response = (prompt | llm).invoke(
                {
                    "current_code": """
def demo() -> str:
    return "ok"
""".strip()
                }
            )

            self.assertIn("```python", response.content)
            self.assertIn('return "ok"', response.content)
            self.assertNotIn("Agent 实时观测面板", response.content)
        finally:
            if original_api_key is not None:
                os.environ["OPENAI_API_KEY"] = original_api_key

    def test_llm_rewrite_file_returns_none_without_api_key(self) -> None:
        original_api_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo_path = Path(tmp)
                target_path = repo_path / "sample.py"
                target_path.write_text("print('hello')\n", encoding="utf-8")

                rewritten = llm_rewrite_file(
                    repo_path,
                    {"goal": "Add a helper function."},
                    target_path,
                    system_role="Backend Builder Agent",
                )

                self.assertIsNone(rewritten)
        finally:
            if original_api_key is not None:
                os.environ["OPENAI_API_KEY"] = original_api_key


if __name__ == "__main__":
    unittest.main()
