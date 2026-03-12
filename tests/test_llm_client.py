from __future__ import annotations

import os
import unittest

from langchain_core.prompts import ChatPromptTemplate

from agentsystem.llm.client import TITLE_TEXT, get_llm


class LlmClientTestCase(unittest.TestCase):
    def test_fallback_client_adds_requested_heading(self) -> None:
        original_api_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "Return updated TSX only."),
                    (
                        "user",
                        """
Current file:
```tsx
{current_code}
```
""".strip(),
                    ),
                ]
            )

            response = (prompt | llm).invoke(
                {
                    "current_code": """
export default function Page() {{
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Agent: demo</h1>
    </div>
  );
}}
""".strip()
                }
            )

            self.assertIn(TITLE_TEXT, response.content)
        finally:
            if original_api_key is not None:
                os.environ["OPENAI_API_KEY"] = original_api_key


if __name__ == "__main__":
    unittest.main()
