from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet


def workspace_prep_node(state: DevState) -> DevState:
    print("[Workspace Prep] Preparing workspace")

    required_modes = {str(item).strip() for item in (state.get("required_modes") or []) if str(item).strip()}

    if "plan-eng-review" in required_modes and not state.get("architecture_review_success"):
        state["current_step"] = "workspace_blocked"
        state["failure_type"] = "workflow_bug"
        state["interruption_reason"] = "plan_eng_review_required"
        state["error_message"] = "Build cannot start before plan-eng-review completes and records architecture review artifacts."
        return state

    if state.get("awaiting_user_input") and str(state.get("resume_from_mode") or "").strip() == "plan-eng-review":
        state["current_step"] = "workspace_blocked"
        state["failure_type"] = "workflow_bug"
        state["interruption_reason"] = "plan_eng_review_waiting_for_input"
        state["error_message"] = "Build cannot start while plan-eng-review still has unresolved planning questions."
        return state

    if str(state.get("bug_scope") or "").strip() and not str(state.get("investigation_report") or "").strip():
        state["current_step"] = "workspace_blocked"
        state["failure_type"] = "workflow_bug"
        state["interruption_reason"] = "investigation_required"
        state["error_message"] = "Bugfix and regression work must complete investigate before entering build or fix."
        return state

    repo_b_path = Path(state["repo_b_path"]).resolve()
    git = GitAdapter(repo_b_path)
    config = RepoBConfigReader(repo_b_path).load_all_config()
    default_branch = config.project["git"]["default_branch"]
    branch_prefix = config.project["git"]["working_branch_prefix"]
    branch_name = git.get_current_branch()

    try:
        if branch_name == default_branch:
            branch_name = f"{branch_prefix}parallel-dev-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
            if git.repo.remotes:
                git.checkout_main_and_pull(default_branch)
            git.create_new_branch(branch_name)
            print(f"[Workspace Prep] Switched to branch: {branch_name}")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[Workspace Prep] Branch preparation skipped: {exc}")

    state["branch_name"] = branch_name
    state["dev_results"] = {}
    state["current_step"] = "workspace_ready"
    state["workspace_prep_success"] = True

    # Build risk list
    risks: list[str] = []
    if not git.repo.remotes:
        risks.append("No remote repository configured; changes will remain local until remote is added.")
    if git.is_dirty():
        risks.append("Working tree has uncommitted changes from previous work.")
    if "plan-eng-review" in required_modes and not state.get("test_plan_path"):
        risks.append("Architecture review completed but test plan artifact is missing.")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.SESSION_MANAGER,
            to_agent=AgentRole.BUILDER,
            status=HandoffStatus.COMPLETED,
            what_i_did=f"Prepared isolated workspace on branch '{branch_name}', validated prerequisite gates, and initialized development environment.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Workspace Branch",
                    type="git_branch",
                    path=branch_name,
                    description=f"Isolated working branch for parallel development, branched from {default_branch}.",
                    created_by=AgentRole.SESSION_MANAGER,
                )
            ],
            what_risks_i_found=risks,
            what_i_require_next="Implement the story scope against architecture review artifacts, then stage all changes for validation.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    return state
