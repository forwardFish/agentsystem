from __future__ import annotations
from pathlib import Path

from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.state import DevState, SubTask


def sync_merge_node(state: DevState) -> DevState:
    print("[Sync Agent] Merging parallel results")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    git = GitAdapter(repo_b_path)
    dev_results = state.get("dev_results", {})

    changed_files: list[str] = []
    completed_types: set[str] = set()
    for agent_name, payload in dev_results.items():
        if isinstance(payload, dict):
            changed_files.extend(str(path) for path in payload.get("updated_files", []))
            completed_types.add(agent_name)

    state["generated_code_diff"] = "\n".join(dict.fromkeys(changed_files))
    state["subtasks"] = _mark_completed(state.get("subtasks", []), completed_types)
    state["staged_files"] = list(dict.fromkeys(changed_files))

    try:
        if git.is_dirty():
            git.add_all()
        staged_files = git.get_staged_files()
        task_payload = state.get("task_payload") or {}
        pr_prep_dir = _build_pr_prep_dir(repo_b_path)
        pr_prep_dir.mkdir(parents=True, exist_ok=True)
        pr_desc = _build_pr_description(state, staged_files)
        commit_msg = _build_commit_message(task_payload, state)

        (pr_prep_dir / "pr_description.md").write_text(pr_desc, encoding="utf-8")
        (pr_prep_dir / "commit_message.txt").write_text(commit_msg, encoding="utf-8")

        state["staged_files"] = staged_files or state["staged_files"]
        state["pr_desc"] = pr_desc
        state["commit_msg"] = commit_msg
        state["pr_prep_dir"] = str(pr_prep_dir)
        state["pr_prep_success"] = True

        if state.get("auto_commit", True) and staged_files:
            git.commit(commit_msg)
            print("[Sync Agent] Local commit created")
        state["sync_merge_success"] = True
        state["message"] = "Synchronized local changes and prepared PR materials."
    except Exception as exc:  # pragma: no cover - defensive
        state["sync_merge_success"] = False
        state["pr_prep_success"] = False
        state["error_message"] = f"Sync merge failed: {exc}"
        state["message"] = state["error_message"]
        print(f"[Sync Agent] Merge failed: {exc}")

    state["current_step"] = "sync_done"
    return state


def _mark_completed(subtasks: list[SubTask], completed_types: set[str]) -> list[SubTask]:
    updated_subtasks: list[SubTask] = []
    for subtask in subtasks:
        if subtask.type in completed_types:
            updated_subtasks.append(subtask.model_copy(update={"status": "completed"}))
        else:
            updated_subtasks.append(subtask)
    return updated_subtasks


def _build_pr_prep_dir(repo_b_path: Path) -> Path:
    # Keep PR prep artifacts outside tracked repo content and alongside workspace metadata.
    return repo_b_path.parent / ".meta" / repo_b_path.name / "pr_prep"


def _build_commit_message(task_payload: dict[str, object], state: DevState) -> str:
    goal = str(task_payload.get("goal", "")).strip() or str(state.get("user_requirement", "")).strip()
    if not goal:
        goal = "prepare local agent change"
    return f"feat(auto-dev): {goal[:60]}"


def _build_pr_description(state: DevState, staged_files: list[str]) -> str:
    task_payload = state.get("task_payload") or {}
    task_goal = str(task_payload.get("goal", "")).strip() or str(state.get("user_requirement", "")).strip()
    acceptance = task_payload.get("acceptance_criteria", []) or []
    changed_files = staged_files or [file for file in (state.get("staged_files") or []) if file]
    review_status = "- [x] Local workflow completed\n- [ ] Human review pending"
    validation_status = str(state.get("test_results") or "Validation pending").strip()

    file_lines = "\n".join(f"- {path}" for path in changed_files) if changed_files else "- No staged files recorded"
    acceptance_lines = (
        "\n".join(f"- {item}" for item in acceptance)
        if isinstance(acceptance, list) and acceptance
        else "- Acceptance criteria not provided"
    )

    return "\n".join(
        [
            "## Change Summary",
            task_goal or "Local agent-generated change.",
            "",
            "## Changed Files",
            file_lines,
            "",
            "## Acceptance Criteria",
            acceptance_lines,
            "",
            "## Validation",
            validation_status,
            "",
            "## Review Status",
            review_status,
        ]
    ).strip() + "\n"
