from __future__ import annotations

import json
import re
import uuid
from pathlib import PurePosixPath
from pathlib import Path

from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, SubTask, add_handoff_packet


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
    story_inputs = [str(item).strip() for item in task_payload.get("story_inputs", []) if str(item).strip()]
    story_process = [str(item).strip() for item in task_payload.get("story_process", []) if str(item).strip()]
    story_outputs = [str(item).strip() for item in task_payload.get("story_outputs", []) if str(item).strip()]
    verification_basis = [str(item).strip() for item in task_payload.get("verification_basis", []) if str(item).strip()]
    constraints = [str(item).strip() for item in task_payload.get("constraints", []) if str(item).strip()]
    not_do = [
        str(item).strip()
        for item in (task_payload.get("explicitly_not_doing") or task_payload.get("not_do") or [])
        if str(item).strip()
    ]
    subtasks: list[SubTask] = []

    execution_files = primary_files or related_files
    if execution_files:
        for index, file_path in enumerate(execution_files, start=1):
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
                description="Refine backend registry snapshot service",
                files_to_modify=["apps/api/src/domain/agent_registry/service.py"],
            ),
            SubTask(
                id="2",
                type="frontend",
                description="Render positions on the agent observation page",
                files_to_modify=["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
            ),
        ]

    if _contains_signal_word(requirement, "database", "migration"):
        subtasks.append(
            SubTask(
                id=str(len(subtasks) + 1),
                type="database",
                description="Prepare database table scaffold",
                files_to_modify=["apps/api/src/infra/db/tables.py"],
            )
        )
    if _contains_signal_word(requirement, "devops", "docker", "ci"):
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
    state["story_inputs"] = story_inputs
    state["story_process"] = story_process
    state["story_outputs"] = story_outputs
    state["verification_basis"] = verification_basis
    state["primary_files"] = primary_files or related_files
    state["secondary_files"] = secondary_files
    state["parsed_constraints"] = constraints
    state["parsed_not_do"] = not_do
    state["error_message"] = None
    state["shared_blackboard"] = {
        "current_goal": state["parsed_goal"],
        "acceptance_checklist": acceptance_checklist,
        "story_inputs": story_inputs,
        "story_process": story_process,
        "story_outputs": story_outputs,
        "verification_basis": verification_basis,
        "primary_files": state["primary_files"],
        "secondary_files": secondary_files,
        "constraints": constraints,
        "not_do": not_do,
    }
    state.setdefault("handoff_packets", [])
    state.setdefault("issues_to_fix", [])
    state.setdefault("resolved_issues", [])
    state.setdefault("agent_messages", [])
    state.setdefault("all_deliverables", [])

    task_scope_name = str(state.get("task_id") or "task")
    if state.get("repo_b_path"):
        repo_b_path = Path(str(state["repo_b_path"])).resolve()
        _write_requirement_artifacts(repo_b_path, state)
        task_scope_name = repo_b_path.name
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.REQUIREMENT,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did="Parsed the story card into executable scope, checklist, constraints, and file targets.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Parsed Requirement JSON",
                    type="report",
                    path=f".meta/{task_scope_name}/requirement/parsed_requirement.json",
                    description="Structured requirement payload for downstream agents.",
                    created_by=AgentRole.REQUIREMENT,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Intent Confirmation Markdown",
                    type="report",
                    path=f".meta/{task_scope_name}/requirement/intent_confirmation.md",
                    description="Human-readable requirement interpretation and boundaries.",
                    created_by=AgentRole.REQUIREMENT,
                ),
            ],
            what_risks_i_found=["Some target files may need to be created from scratch."] if related_files else [],
            what_i_require_next="Modify only the declared primary files, satisfy every checklist item, and keep edits within the task boundary.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    print(f"[Requirement Agent] Produced {len(subtasks)} subtasks")
    return state


def _write_requirement_artifacts(repo_b_path: Path, state: DevState) -> None:
    requirement_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "requirement"
    requirement_dir.mkdir(parents=True, exist_ok=True)
    parsed_payload = {
        "parsed_goal": state.get("parsed_goal"),
        "acceptance_checklist": state.get("acceptance_checklist") or [],
        "story_inputs": state.get("story_inputs") or [],
        "story_process": state.get("story_process") or [],
        "story_outputs": state.get("story_outputs") or [],
        "verification_basis": state.get("verification_basis") or [],
        "primary_files": state.get("primary_files") or [],
        "secondary_files": state.get("secondary_files") or [],
        "constraints": state.get("parsed_constraints") or [],
        "not_do": state.get("parsed_not_do") or [],
    }
    (requirement_dir / "parsed_requirement.json").write_text(
        json.dumps(parsed_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    acceptance_lines = [f"- {item}" for item in (state.get("acceptance_checklist") or [])] or ["- None"]
    story_input_lines = [f"- {item}" for item in (state.get("story_inputs") or [])] or ["- None"]
    story_process_lines = [f"- {item}" for item in (state.get("story_process") or [])] or ["- None"]
    story_output_lines = [f"- {item}" for item in (state.get("story_outputs") or [])] or ["- None"]
    verification_lines = [f"- {item}" for item in (state.get("verification_basis") or [])] or ["- None"]
    file_scope_lines = [f"- {item}" for item in (state.get("primary_files") or [])] or ["- None"]
    lines = [
        "# Requirement Intent Confirmation",
        "",
        f"- Goal: {state.get('parsed_goal') or 'n/a'}",
        "",
        "## Acceptance Checklist",
        *acceptance_lines,
        "",
        "## Planned Input",
        *story_input_lines,
        "",
        "## Planned Process",
        *story_process_lines,
        "",
        "## Planned Output",
        *story_output_lines,
        "",
        "## Verification Basis",
        *verification_lines,
        "",
        "## File Scope",
        *file_scope_lines,
    ]
    (requirement_dir / "intent_confirmation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _contains_signal_word(text: str, *signals: str) -> bool:
    for signal in signals:
        if re.search(rf"\b{re.escape(signal)}\b", text):
            return True
    return False
