from __future__ import annotations

from agentsystem.core.state import DevState, SubTask


def requirement_analysis_node(state: DevState) -> DevState:
    print("[Requirement Agent] Analyzing requirement")

    requirement = state.get("user_requirement", "").lower()
    subtasks = [
        SubTask(
            id="1",
            type="backend",
            description="Refine backend AgentSnapshot contract",
            files_to_modify=["apps/api/src/schemas/agent.py"],
        ),
        SubTask(
            id="2",
            type="frontend",
            description="Render positions on the agent observation page",
            files_to_modify=["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
        ),
    ]
    if "database" in requirement or "migration" in requirement:
        subtasks.append(
            SubTask(
                id="3",
                type="database",
                description="Prepare database table scaffold",
                files_to_modify=["apps/api/src/infra/db/tables.py"],
            )
        )
    if "devops" in requirement or "docker" in requirement or "ci" in requirement:
        subtasks.append(
            SubTask(
                id="4",
                type="devops",
                description="Prepare DevOps scaffold",
                files_to_modify=[".github/workflows/preview-ci.yml"],
            )
        )

    state["subtasks"] = subtasks
    state["current_step"] = "requirement_done"
    state["requirement_spec"] = f"Decomposed the request into {len(subtasks)} implementation subtasks."
    state["error_message"] = None

    print(f"[Requirement Agent] Produced {len(subtasks)} subtasks")
    return state
