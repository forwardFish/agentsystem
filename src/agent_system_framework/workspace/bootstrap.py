from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from agent_system_framework.workspace.contracts import ProjectConfig, load_project_config as load_project_contract
from agent_system_framework.workspace.git_tools import run_git


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    target_repo: Path
    project: ProjectConfig
    marker_path: Path
    commit_sha: str | None = None


def load_project_config(target_repo: Path) -> ProjectConfig:
    return load_project_contract(target_repo)


def bootstrap_target_repo(target_repo: Path, *, commit: bool = False, message: str | None = None) -> BootstrapResult:
    repo_root = target_repo.resolve()
    project = load_project_config(repo_root)
    marker_path = repo_root / "docs" / "bootstrap" / "phase-1-bootstrap.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(
            {
                "project": project.name,
                "description": project.description,
                "default_branch": project.git["default_branch"],
                "working_branch_prefix": project.git["working_branch_prefix"],
                "stack_paths": {name: section["path"] for name, section in project.stack.items()},
                "status": "bootstrap-ready",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commit_sha = _commit_changes(repo_root, [marker_path], message or "chore: bootstrap target repo") if commit else None
    return BootstrapResult(target_repo=repo_root, project=project, marker_path=marker_path, commit_sha=commit_sha)
def _commit_changes(repo_root: Path, paths: list[Path], message: str) -> str:
    rel_paths = [str(path.relative_to(repo_root)) for path in paths]
    run_git(repo_root, ["add", "--", *rel_paths])
    run_git(
        repo_root,
        [
            "-c",
            "user.name=Agent System",
            "-c",
            "user.email=agent-system@example.invalid",
            "commit",
            "-m",
            message,
            "--",
            *rel_paths,
        ],
    )
    return run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a target repository from its .agents contract")
    parser.add_argument("--target-repo", required=True, type=Path, help="Path to the target repository root")
    parser.add_argument("--commit", action="store_true", help="Commit the generated marker file inside the target repo")
    parser.add_argument("--message", default="chore: bootstrap target repo", help="Commit message to use with --commit")
    args = parser.parse_args()

    result = bootstrap_target_repo(args.target_repo, commit=args.commit, message=args.message)
    print(
        json.dumps(
            {
                "project": result.project.name,
                "marker_path": str(result.marker_path),
                "commit_sha": result.commit_sha,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
