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
from agentsystem.agents.requirements_analyst_agent import analyze_requirement
from scripts.fix_encoding import fix_tree_encoding
from scripts.validate_skill import validate_all_skills, validate_skill_file


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
        click.echo(f"任务卡文件不存在: {task_file}", err=True)
        raise SystemExit(1)

    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        TaskCard.model_validate(payload)
    except Exception as exc:
        click.echo(f"任务卡校验失败: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"开始执行任务: {task_file}")
    click.echo(f"环境: {env}")
    if resume:
        click.echo("resume 参数已保留，当前主流程默认按本地闭环执行")

    try:
        output = run_prod_task(task_path, env)
    except Exception as exc:
        click.echo(f"任务执行失败: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("任务执行完成")
    click.echo(f"   分支: {output['branch']}")
    click.echo(f"   Commit: {output['commit']}")
    click.echo(f"   审计日志: {output['audit_path']}")


@cli.command("analyze")
@click.option("--requirement", "-r", required=True, help="Large natural-language requirement")
@click.option("--sprint", "-s", default="1", show_default=True, help="Sprint number")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def analyze(requirement: str, sprint: str, env: str) -> None:
    """Analyze a large requirement and generate sprint planning artifacts."""
    config_name = "test.yaml" if env == "test" else "production.yaml"
    config = SystemConfigReader().load(ROOT_DIR / "config" / config_name)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()

    result = analyze_requirement(repo_b_path, ROOT_DIR / "tasks", requirement, sprint)
    click.echo(f"需求分析完成，Sprint {sprint} 已生成")
    click.echo(f"   Sprint 目录: {result['sprint_dir']}")
    click.echo(f"   规划文档: {result['sprint_plan_path']}")
    click.echo(f"   执行顺序: {result['execution_order_path']}")
    click.echo(f"   Story 数量: {len(result['story_cards'])}")


@cli.command("run-sprint")
@click.option("--sprint", "-s", required=True, help="Sprint number")
@click.option("--start-from", default=0, show_default=True, help="Story index to start from")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def run_sprint(sprint: str, start_from: int, env: str) -> None:
    """Run all story cards in a generated sprint directory."""
    sprint_dir = ROOT_DIR / "tasks" / f"sprint_{sprint}"
    execution_file = sprint_dir / "execution_order.txt"
    if not sprint_dir.exists() or not execution_file.exists():
        click.echo(f"Sprint 目录不存在或缺少 execution_order.txt: {sprint_dir}", err=True)
        raise SystemExit(1)

    order = [line.strip() for line in execution_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if start_from < 0 or start_from >= len(order):
        click.echo(f"start-from 超出范围: {start_from}", err=True)
        raise SystemExit(1)

    for index, story_id in enumerate(order[start_from:], start=start_from + 1):
        candidates = sorted(sprint_dir.glob(f"{story_id}_*.yaml"))
        if not candidates:
            click.echo(f"未找到 Story 任务卡: {story_id}", err=True)
            raise SystemExit(1)
        story_file = candidates[0]
        click.echo(f"[{index}/{len(order)}] 执行 Story: {story_id}")
        output = run_prod_task(story_file, env)
        click.echo(f"   完成，分支: {output['branch']}")
        click.echo(f"   Commit: {output['commit']}")

    click.echo(f"Sprint {sprint} 执行完成")


@cli.command("list-tasks")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
def list_tasks(env: str) -> None:
    config_name = "test.yaml" if env == "test" else "production.yaml"
    config = SystemConfigReader().load(ROOT_DIR / "config" / config_name)
    repo_b_path = config["repo"]["versefina"]
    git = GitAdapter(repo_b_path)

    click.echo("本地 Agent 任务分支:")
    agent_branches = [branch for branch in git.get_branches() if branch.startswith("agent/")]
    if not agent_branches:
        click.echo("   暂无 Agent 任务分支")
        return
    for branch in agent_branches:
        click.echo(f"   - {branch}")


@cli.command("validate-skill")
@click.option("--file", "skill_file", help="Validate a single skill file")
def validate_skill(skill_file: str | None) -> None:
    click.echo("验证 Skill 文件...")
    if skill_file:
        if validate_skill_file(skill_file):
            click.echo("Skill 文件验证通过")
            return
        click.echo("Skill 文件验证失败", err=True)
        raise SystemExit(1)

    results = validate_all_skills(ROOT_DIR / "skills")
    if results and all(results.values()):
        click.echo("所有 Skill 文件验证通过")
        return
    if not results:
        click.echo("当前没有可验证的 .skill.md 文件")
        return
    click.echo("部分 Skill 文件验证失败", err=True)
    raise SystemExit(1)


@cli.command("fix-encoding")
@click.option("--root", default=str(ROOT_DIR), show_default=True, help="Root directory to normalize")
def fix_encoding(root: str) -> None:
    click.echo("修复中文编码...")
    fix_tree_encoding(root)
    click.echo("编码修复完成")


@cli.command("cleanup")
@click.option("--env", default="test", show_default=True, help="Runtime environment")
@click.option("--task-id", help="Specific task id to clean")
@click.option("--branches", is_flag=True, help="Remove local agent task branches")
@click.option("--full", "full_cleanup", is_flag=True, help="Remove task worktrees, meta, and branches")
def cleanup(env: str, task_id: str | None, branches: bool, full_cleanup: bool) -> None:
    config_name = "test.yaml" if env == "test" else "production.yaml"
    config = SystemConfigReader().load(ROOT_DIR / "config" / config_name)
    repo_b_path = Path(config["repo"]["versefina"]).resolve()
    worktree_root = ROOT_DIR / "repo-worktree"
    workspace_manager = WorkspaceManager(repo_b_path, worktree_root)
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
        click.echo("已清理以下分支/任务资源:")
        for item in cleaned:
            click.echo(f"   - {item}")
    else:
        click.echo("没有需要清理的任务资源")


@cli.command("dashboard")
@click.option("--host", default="127.0.0.1", show_default=True, help="Dashboard host")
@click.option("--port", default=8000, show_default=True, help="Dashboard port")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True, help="Open browser automatically")
def dashboard(host: str, port: int, open_browser: bool) -> None:
    url = f"http://{host}:{port}"
    if open_browser:
        webbrowser.open(url)
    click.echo(f"Dashboard 已启动: {url}")
    uvicorn.run(dashboard_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
