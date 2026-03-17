from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import click
import uvicorn
import yaml

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main_production import run_prod_task
from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.core.task_card import TaskCard
from agentsystem.dashboard.main import app as dashboard_app
from agentsystem.orchestration.workspace_manager import WorkspaceManager
from agentsystem.agents.requirements_analyst_agent import analyze_requirement, split_requirement_file
from scripts.fix_encoding import fix_tree_encoding
from scripts.render_agent_skills import render_agent_skill, render_all_agent_skills, validate_rendered_agent_package
from scripts.validate_skill import validate_all_skills, validate_skill_file


def _load_env_config(env: str) -> dict:
    config_name = "test.yaml" if env == "test" else "production.yaml"
    return SystemConfigReader().load(ROOT_DIR / "config" / config_name)


@click.group()
def cli() -> None:
    """AgentSystem command line tool."""


@cli.command("run-task")
@click.option("--task-file", required=True, help="Task card file path")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--resume", is_flag=True, help="Resume from checkpoint (reserved)")
def run_task(task_file: str, env: str, resume: bool) -> None:
    task_path = Path(task_file)
    if not task_path.exists():
        click.echo(f"Task card file does not exist: {task_file}", err=True)
        raise SystemExit(1)

    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        TaskCard.model_validate(payload)
    except Exception as exc:
        click.echo(f"Task card validation failed: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"Running task: {task_file}")
    click.echo(f"Environment: {env}")
    if resume:
        click.echo("resume is reserved; the current local workflow always starts from the task card.")

    try:
        output = run_prod_task(task_path, env)
    except Exception as exc:
        click.echo(f"Task execution failed: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("Task completed")
    click.echo(f"  Branch: {output['branch']}")
    click.echo(f"  Commit: {output['commit']}")
    click.echo(f"  Audit log: {output['audit_path']}")


@cli.command("analyze")
@click.option("--requirement", "-r", required=True, help="Large natural-language requirement")
@click.option("--sprint", "-s", default="1", show_default=True, help="Fallback sprint number for generic requirements")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
def analyze(requirement: str, sprint: str, env: str, prefix: str) -> None:
    """Analyze a large requirement and generate backlog artifacts."""
    config = _load_env_config(env)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()
    result = analyze_requirement(repo_b_path, ROOT_DIR / "tasks", requirement, sprint=sprint, prefix=prefix)
    click.echo("Requirement analysis completed")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Overview: {result['overview_path']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")


@cli.command("split_requirement")
@click.option(
    "--requirement-file",
    "-f",
    default=r"D:\lyh\agent\agent-frame\versefina\docs\需求文档\需求分析.md",
    show_default=True,
    help="Requirement markdown file path",
)
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--prefix", "-p", default="backlog_v1", show_default=True, help="Output backlog directory name")
def split_requirement(requirement_file: str, env: str, prefix: str) -> None:
    """Split a requirement markdown file into formal backlog_v1 sprint artifacts."""
    config = _load_env_config(env)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()
    result = split_requirement_file(repo_b_path, ROOT_DIR / "tasks", requirement_file, prefix=prefix)
    click.echo("Requirement split completed")
    click.echo(f"  Backlog root: {result['backlog_root']}")
    click.echo(f"  Overview: {result['overview_path']}")
    click.echo(f"  Story count: {len(result['story_cards'])}")


@cli.command("run-sprint")
@click.option("--sprint-dir", help="Sprint directory path, for example tasks/backlog_v1/sprint_0_contract_foundation")
@click.option("--sprint", help="Legacy sprint number, for example 1")
@click.option("--start-from", default=0, show_default=True, help="Story index to start from")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def run_sprint(sprint_dir: str | None, sprint: str | None, start_from: int, env: str) -> None:
    """Run all story cards in a generated sprint directory."""
    if not sprint_dir and not sprint:
        click.echo("Either --sprint-dir or --sprint is required.", err=True)
        raise SystemExit(1)

    if sprint_dir:
        target_dir = Path(sprint_dir).resolve()
    else:
        target_dir = ROOT_DIR / "tasks" / f"sprint_{sprint}"

    execution_file = target_dir / "execution_order.txt"
    if not target_dir.exists() or not execution_file.exists():
        click.echo(f"Sprint directory or execution_order.txt is missing: {target_dir}", err=True)
        raise SystemExit(1)

    story_ids = [line.strip() for line in execution_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if start_from < 0 or start_from >= len(story_ids):
        click.echo(f"start-from is out of range: {start_from}", err=True)
        raise SystemExit(1)

    for index, story_id in enumerate(story_ids[start_from:], start=start_from + 1):
        story_file = next(target_dir.rglob(f"{story_id}_*.yaml"), None)
        if story_file is None:
            click.echo(f"Story card not found for {story_id}", err=True)
            raise SystemExit(1)
        click.echo(f"[{index}/{len(story_ids)}] Running {story_id}")
        output = run_prod_task(story_file, env)
        click.echo(f"  Branch: {output['branch']}")
        click.echo(f"  Commit: {output['commit']}")

    click.echo(f"Sprint completed: {target_dir}")


@cli.command("list-tasks")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def list_tasks(env: str) -> None:
    config = _load_env_config(env)
    repo_b_path = config["repo"]["versefina"]
    git = GitAdapter(repo_b_path)
    branches = [branch for branch in git.get_branches() if branch.startswith("agent/")]
    click.echo("Local agent branches:")
    if not branches:
        click.echo("  (none)")
        return
    for branch in branches:
        click.echo(f"  - {branch}")


@cli.command("validate-skill")
@click.option("--file", "skill_file", help="Validate a single skill file")
def validate_skill(skill_file: str | None) -> None:
    click.echo("Validating skill files...")
    if skill_file:
        if validate_skill_file(skill_file):
            click.echo("Skill file is valid.")
            return
        click.echo("Skill file validation failed.", err=True)
        raise SystemExit(1)

    results = validate_all_skills(ROOT_DIR / "skills")
    if results and all(results.values()):
        click.echo("All skill files are valid.")
        return
    if not results:
        click.echo("No .skill.md files found.")
        return
    click.echo("Some skill files failed validation.", err=True)
    raise SystemExit(1)


@cli.command("render-agent-skills")
@click.option("--mode-id", help="Render only one skill mode package")
@click.option("--validate/--no-validate", default=True, show_default=True, help="Validate rendered packages after writing")
def render_agent_skills(mode_id: str | None, validate: bool) -> None:
    click.echo("Rendering agent skill packages...")
    if mode_id:
        rendered = [render_agent_skill(mode_id, ROOT_DIR)]
    else:
        rendered = render_all_agent_skills(ROOT_DIR)
    if validate:
        for item in rendered:
            validate_rendered_agent_package(Path(item["skill_path"]).resolve().parent)
    for item in rendered:
        click.echo(f"  - {item['mode_id']}: {item['skill_path']}")
    click.echo("Agent skill packages rendered.")


@cli.command("fix-encoding")
@click.option("--root", default=str(ROOT_DIR), show_default=True, help="Root directory to normalize")
def fix_encoding(root: str) -> None:
    click.echo("Fixing text encoding...")
    fix_tree_encoding(root)
    click.echo("Encoding normalization completed.")


@cli.command("cleanup")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--task-id", help="Specific task id to clean")
@click.option("--branches", is_flag=True, help="Remove local agent task branches")
@click.option("--full", "full_cleanup", is_flag=True, help="Remove task worktrees, meta, and branches")
def cleanup(env: str, task_id: str | None, branches: bool, full_cleanup: bool) -> None:
    config = _load_env_config(env)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()
    workspace_manager = WorkspaceManager(repo_b_path, ROOT_DIR / "repo-worktree")
    git = GitAdapter(repo_b_path)
    cleaned: list[str] = []

    if task_id:
        workspace_manager.cleanup_task_resources(task_id)
        branch_name = f"agent/l1-{task_id}"
        if branch_name in git.get_branches():
            git.delete_branch(branch_name, force=True)
            cleaned.append(branch_name)

    if branches or full_cleanup:
        for branch_name in list(git.get_branches()):
            if not branch_name.startswith("agent/l1-task-"):
                continue
            task_key = branch_name.removeprefix("agent/l1-")
            workspace_manager.cleanup_task_resources(task_key)
            git.delete_branch(branch_name, force=True)
            cleaned.append(branch_name)

    if full_cleanup:
        workspace_manager.cleanup_orphaned_state()

    if cleaned:
        click.echo("Removed resources:")
        for item in cleaned:
            click.echo(f"  - {item}")
    else:
        click.echo("No matching resources to clean.")


@cli.command("dashboard")
@click.option("--host", default="127.0.0.1", show_default=True, help="Dashboard host")
@click.option("--port", default=8000, show_default=True, help="Dashboard port")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True, help="Open browser automatically")
def dashboard(host: str, port: int, open_browser: bool) -> None:
    url = f"http://{host}:{port}"
    if open_browser:
        webbrowser.open(url)
    click.echo(f"Dashboard started at {url}")
    uvicorn.run(dashboard_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
