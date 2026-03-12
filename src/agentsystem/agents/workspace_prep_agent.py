from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import DevState


def workspace_prep_node(state: DevState) -> DevState:
    print("[Workspace Prep] Preparing workspace")

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
    return state
