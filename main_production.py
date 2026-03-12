from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.orchestration.task_state_machine import TaskStateMachine
from agentsystem.orchestration.workspace_manager import WorkspaceManager
from agentsystem.utils.logger import get_logger


def run_prod_task(task_file: str | Path, env: str = "production") -> dict:
    config_name = "test.yaml" if env == "test" else "production.yaml"
    config_path = ROOT_DIR / "config" / config_name
    config = SystemConfigReader().load(config_path)

    logger = get_logger("main_production", ROOT_DIR / config["logging"]["path"])
    logger.info("Initializing production task runner", extra={"task_id": "bootstrap", "agent_type": "system"})

    workspace_root = ROOT_DIR / config["agent"]["workspace_root"]
    workspace_manager = WorkspaceManager(repo_root=ROOT_DIR, worktree_root=ROOT_DIR / "repo-worktree")
    workspace_root.mkdir(parents=True, exist_ok=True)

    task_service = TaskStateMachine(config, workspace_manager)
    result = task_service.run(task_file)
    checkpoint = task_service.save_checkpoint()
    audit_path = task_service.write_audit_log(ROOT_DIR / "runs" / "prod_audit.json")

    logger.info(
        "Production task finished",
        extra={
            "task_id": result["task_id"],
            "agent_type": "system",
        },
    )

    return {
        "result": result,
        "checkpoint": checkpoint,
        "audit_path": str(audit_path),
    }


def main() -> None:
    output = run_prod_task(ROOT_DIR / "tasks" / "current.yaml")
    print(output["result"])


if __name__ == "__main__":
    main()
