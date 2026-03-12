from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.graph.dev_workflow import DevWorkflow
from agentsystem.orchestration.workspace_manager import WorkspaceLockError, WorkspaceManager
from agentsystem.utils.logger import get_logger


def run_prod_task(task_file: str | Path, env: str = "test") -> dict:
    logger = get_logger("main_production", ROOT_DIR / "logs" / "agent_system.log")
    logger.info("Starting production task", extra={"task_id": "bootstrap", "agent_type": "system"})

    config_name = "test.yaml" if env == "test" else "production.yaml"
    config = SystemConfigReader().load(ROOT_DIR / "config" / config_name)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()

    git = GitAdapter(repo_b_path)
    git.checkout_main_and_pull("main")

    workspace_manager = WorkspaceManager(repo_b_path, ROOT_DIR / "repo-worktree")
    task_path = Path(task_file).resolve()
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    if not isinstance(task, dict):
        raise ValueError(f"{task_path} must contain a mapping")

    task_id = workspace_manager.generate_task_id(task_path.read_text(encoding="utf-8"))
    branch_name = f"agent/l1-{task_id}"
    try:
        worktree_path = workspace_manager.create_worktree(task_id, branch_name)
    except WorkspaceLockError:
        worktree_path = workspace_manager.worktree_root / task_id
    logger.info(
        "Workspace created",
        extra={"task_id": task_id, "agent_type": "system"},
    )
    _prepare_local_dependencies(repo_b_path, worktree_path)

    workflow = DevWorkflow(config, str(worktree_path), task)
    result = workflow.run()
    if not result["success"]:
        logger.error(
            "Workflow execution failed",
            extra={"task_id": task_id, "agent_type": "system"},
        )
        return {
            "task_id": task_id,
            "branch": branch_name,
            "worktree_path": str(worktree_path),
            "success": False,
            "error": result.get("error"),
            "state": result["state"],
        }

    repo_b_config = RepoBConfigReader(worktree_path).load_all_config()
    format_commands = repo_b_config.commands.get("format", [])
    if format_commands:
        shell = ShellExecutor(worktree_path)
        format_success, format_output = shell.run_commands(format_commands)
        if not format_success:
            raise RuntimeError(f"Format failed: {format_output}")

    git_worktree = GitAdapter(worktree_path)
    commit_hash = git_worktree.get_current_commit()
    if git_worktree.is_dirty():
        git_worktree.add_all()
        commit_message = str(result["state"].get("commit_msg") or f"feat(auto-dev): {str(task.get('goal', 'task'))[:50]}")
        git_worktree.commit(commit_message)
        commit_hash = git_worktree.get_current_commit()

    audit_log = {
        "task_id": task_id,
        "branch": branch_name,
        "commit": commit_hash,
        "success": True,
        "pr_prep_dir": result["state"].get("pr_prep_dir"),
        "pr_desc": result["state"].get("pr_desc"),
        "commit_msg": result["state"].get("commit_msg"),
        "result": result["state"],
    }
    audit_path = ROOT_DIR / "runs" / f"prod_audit_{task_id}.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit_log, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Production task finished",
        extra={"task_id": task_id, "agent_type": "system"},
    )
    return {
        "task_id": task_id,
        "branch": branch_name,
        "worktree_path": str(worktree_path),
        "commit": commit_hash,
        "audit_path": str(audit_path),
        "pr_prep_dir": result["state"].get("pr_prep_dir"),
        "success": True,
        "state": result["state"],
    }


def _prepare_local_dependencies(repo_b_path: Path, worktree_path: Path) -> None:
    source_web = repo_b_path / "apps" / "web"
    target_web = worktree_path / "apps" / "web"
    if not (source_web / "node_modules").exists():
        return
    if (target_web / "node_modules").exists():
        return
    shell = ShellExecutor(worktree_path)
    success, output = shell.run_command("pnpm --dir apps/web install --frozen-lockfile")
    if not success:
        raise RuntimeError(f"Failed to prepare local frontend dependencies: {output}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main_production.py <task_file> [env]")
        raise SystemExit(1)
    task_file = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) > 2 else "test"
    output = run_prod_task(task_file, env)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
