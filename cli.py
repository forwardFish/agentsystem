from __future__ import annotations

import sys
from pathlib import Path

import click

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main_production import run_prod_task
from agentsystem.adapters.config_reader import SystemConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
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
        click.echo(f"❌ 任务卡文件不存在: {task_file}", err=True)
        raise SystemExit(1)

    click.echo(f"开始执行任务: {task_file}")
    click.echo(f"环境: {env}")
    if resume:
        click.echo("resume 参数已保留，当前主流程默认按本地闭环执行")

    try:
        output = run_prod_task(task_path, env)
    except Exception as exc:
        click.echo(f"❌ 任务执行失败: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("任务执行完成")
    click.echo(f"   分支: {output['branch']}")
    click.echo(f"   Commit: {output['commit']}")
    click.echo(f"   审计日志: {output['audit_path']}")


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
    click.echo("验证Skill文件...")
    if skill_file:
        if validate_skill_file(skill_file):
            click.echo("Skill文件验证通过")
            return
        click.echo("❌ Skill文件验证失败", err=True)
        raise SystemExit(1)

    results = validate_all_skills(ROOT_DIR / "skills")
    if results and all(results.values()):
        click.echo("所有Skill文件验证通过")
        return
    if not results:
        click.echo("当前没有可验证的 .skill.md 文件")
        return
    click.echo("❌ 部分Skill文件验证失败", err=True)
    raise SystemExit(1)


@cli.command("fix-encoding")
@click.option("--root", default=str(ROOT_DIR), show_default=True, help="Root directory to normalize")
def fix_encoding(root: str) -> None:
    click.echo("修复中文编码...")
    fix_tree_encoding(root)
    click.echo("编码修复完成")


if __name__ == "__main__":
    cli()
