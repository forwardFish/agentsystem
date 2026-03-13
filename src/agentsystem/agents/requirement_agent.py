from __future__ import annotations

from pathlib import PurePosixPath

from agentsystem.core.state import DevState, SubTask


def requirement_analysis_node(state: DevState) -> DevState:
    print("[Requirement Agent] Analyzing requirement")

    requirement = state.get("user_requirement", "").lower()
    task_payload = state.get("task_payload") or {}
    primary_files = [str(path) for path in task_payload.get("primary_files", [])]
    related_files = [str(path) for path in task_payload.get("related_files", [])]
    if not related_files:
        related_files = list(primary_files)
    secondary_files = [str(path) for path in task_payload.get("secondary_files", [])]
    acceptance_checklist = [str(item).strip() for item in task_payload.get("acceptance_criteria", []) if str(item).strip()]
    constraints = [str(item).strip() for item in task_payload.get("constraints", []) if str(item).strip()]
    not_do = [
        str(item).strip()
        for item in (task_payload.get("explicitly_not_doing") or task_payload.get("not_do") or [])
        if str(item).strip()
    ]
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
            elif normalized.startswith("docs/") or normalized.startswith(".agents/"):
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="backend",
                        description="Update the requested contract or documentation asset",
                        files_to_modify=[normalized],
                    )
                )
            elif normalized.startswith("scripts/") or normalized.endswith(".sql"):
                subtasks.append(
                    SubTask(
                        id=str(index),
                        type="database",
                        description="Update the requested database or script asset",
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
    state["parsed_goal"] = str(task_payload.get("goal", "")).strip() or str(state.get("user_requirement", "")).strip()
    state["acceptance_checklist"] = acceptance_checklist
    state["primary_files"] = primary_files or related_files
    state["secondary_files"] = secondary_files
    state["parsed_constraints"] = constraints
    state["parsed_not_do"] = not_do
    state["error_message"] = None

    print(f"[Requirement Agent] Produced {len(subtasks)} subtasks")
    return state
