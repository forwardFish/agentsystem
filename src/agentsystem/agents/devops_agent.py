from __future__ import annotations

from pathlib import Path

from agentsystem.core.state import DevState


def devops_dev_node(state: DevState) -> dict[str, object]:
    print("[DevOps Agent] Starting infrastructure work")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    updated_files: list[str] = []
    ci_file = repo_b_path / ".github" / "workflows" / "preview-ci.yml"
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

    return {
        "devops_result": "DevOps scaffold prepared.",
        "dev_results": {
            "devops": {
                "updated_files": updated_files,
                "summary": "Prepared preview CI scaffold.",
            }
        },
    }
