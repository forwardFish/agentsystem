from __future__ import annotations

from pathlib import PurePosixPath

from agentsystem.core.state import DevState, SubTask


def requirement_analysis_node(state: DevState) -> DevState:
    print("[Requirement Agent] Analyzing requirement")

    requirement = state.get("user_requirement", "").lower()
    task_payload = state.get("task_payload") or {}
    related_files = [str(path) for path in task_payload.get("related_files", [])]
    subtasks: list[SubTask] = []

    if related_files:
        for index, file_path in enumerate(related_files, start=1):
            normalized = PurePosixPath(file_path.replace("\\", "/")).as_posix()
            if normalized.startswith("apps/web/"):
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="frontend",
                        description="Update the requested frontend page",
                        files_to_modify=[normalized],
                    )
                )
            elif normalized.startswith("apps/api/"):
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="backend",
                        description="Update the requested backend module",
                        files_to_modify=[normalized],
                    )
                )
            elif "/infra/db/" in normalized or "migration" in normalized:
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="database",
                        description="Update the requested database asset",
                        files_to_modify=[normalized],
                    )
                )
            elif normalized.startswith(".github/") or normalized.startswith("infra/"):
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="devops",
                        description="Update the requested DevOps asset",
                        files_to_modify=[normalized],
                    )
                )

    if not subtasks:
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
                id=str(len(subtasks) + 1),
                type="database",
                description="Prepare database table scaffold",
                files_to_modify=["apps/api/src/infra/db/tables.py"],
            )
        )
    if "devops" in requirement or "docker" in requirement or "ci" in requirement:
        subtasks.append(
            SubTask(
                id=str(len(subtasks) + 1),
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
