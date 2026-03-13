from __future__ import annotations

from pathlib import Path

from agentsystem.agents.llm_editing import llm_rewrite_file
from agentsystem.core.state import DevState


def devops_dev_node(state: DevState) -> dict[str, object]:
    print("[DevOps Agent] Starting infrastructure work")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    updated_files: list[str] = []
    devops_tasks = [task for task in state.get("subtasks", []) if task.type == "devops"]
    candidate_files: list[Path] = []
    for task in devops_tasks:
        for file_path in getattr(task, "files_to_modify", []):
            candidate = repo_b_path / str(file_path)
            if candidate not in candidate_files:
                candidate_files.append(candidate)
    if not candidate_files:
        candidate_files.append(repo_b_path / ".github" / "workflows" / "preview-ci.yml")

    for ci_file in candidate_files:
        ci_file.parent.mkdir(parents=True, exist_ok=True)
        if not ci_file.exists():
            ci_file.write_text(
                "name: preview-ci\n"
                "on:\n"
                "  workflow_dispatch:\n"
                "jobs:\n"
                "  verify:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: echo preview ci scaffold\n",
                encoding="utf-8",
            )
            updated_files.append(str(ci_file))
            continue
        content = ci_file.read_text(encoding="utf-8")
        rewritten = llm_rewrite_file(repo_b_path, state.get("task_payload"), ci_file, system_role="DevOps Builder Agent")
        if rewritten and rewritten != content:
            ci_file.write_text(rewritten, encoding="utf-8")
            updated_files.append(str(ci_file))

    return {
        "devops_result": "DevOps scaffold prepared.",
        "dev_results": {
            "devops": {
                "updated_files": updated_files,
                "summary": "Prepared preview CI scaffold.",
            }
        },
    }
