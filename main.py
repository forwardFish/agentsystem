from __future__ import annotations

import os

from dotenv import load_dotenv

from agentsystem.graph.dev_workflow import create_dev_graph


def main() -> None:
    load_dotenv()

    print("=== Repo A: Agent engineering system start ===")

    user_requirement = """
    Improve the Agent observation page:
    1. The backend should define a complete AgentSnapshot schema.
    2. The frontend should render a positions list.
    """.strip()

    initial_state = {
        "user_requirement": user_requirement,
        "repo_b_path": os.getenv("REPO_B_LOCAL_PATH", ""),
        "branch_name": None,
        "current_step": "init",
        "subtasks": [],
        "requirement_spec": None,
        "dev_results": {},
        "backend_result": None,
        "frontend_result": None,
        "database_result": None,
        "devops_result": None,
        "generated_code_diff": None,
        "test_results": None,
        "security_report": None,
        "review_report": None,
        "doc_result": None,
        "fix_result": None,
        "fix_attempts": 0,
        "error_message": None,
    }

    graph = create_dev_graph()
    print("[Workflow] Running development graph")

    final_output = None
    for output in graph.stream(initial_state):
        final_output = output
        print("\n--- Node completed ---")
        print(output)

    print("\n=== Workflow finished ===")
    print("Final state:", final_output)


if __name__ == "__main__":
    main()
