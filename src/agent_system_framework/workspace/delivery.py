from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from agent_system_framework.workspace.branching import BranchManager, BranchResult
from agent_system_framework.workspace.commands import CommandExecutor, CommandResult
from agent_system_framework.workspace.github import GitHubPullRequestManager, PullRequestResult


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    branch: BranchResult
    phases: dict[str, list[CommandResult]]
    pull_request: PullRequestResult | None


def deliver_change(
    target_repo: Path,
    *,
    change_slug: str,
    phases: list[str],
    push: bool = False,
    open_pr: bool = False,
    pr_title: str | None = None,
    pr_body: str = "",
    draft: bool = False,
) -> DeliveryResult:
    target_repo = target_repo.resolve()
    branch_manager = BranchManager(target_repo)
    branch = branch_manager.create_working_branch(change_slug)

    executor = CommandExecutor(target_repo)
    phase_results = executor.run_phases(phases)

    pull_request: PullRequestResult | None = None
    if push or open_pr:
        branch_manager.push(branch.working_branch)
    if open_pr:
        github = GitHubPullRequestManager(target_repo)
        pull_request = github.create_pull_request(
            title=pr_title or f"Agent change: {change_slug}",
            body=pr_body,
            head_branch=branch.working_branch,
            base_branch=branch.base_branch,
            draft=draft,
        )
    return DeliveryResult(branch=branch, phases=phase_results, pull_request=pull_request)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a working branch, run repo commands, and optionally open a PR")
    parser.add_argument("--target-repo", required=True, type=Path, help="Path to the target repository root")
    parser.add_argument("--change-slug", required=True, help="Short identifier for the working branch name")
    parser.add_argument(
        "--phase",
        dest="phases",
        action="append",
        required=True,
        help="Command phase from .agents/commands.yaml. Repeat for multiple phases.",
    )
    parser.add_argument("--push", action="store_true", help="Push the generated working branch to origin")
    parser.add_argument("--open-pr", action="store_true", help="Create a pull request after pushing the branch")
    parser.add_argument("--pr-title", help="Pull request title. Defaults to Agent change: <change-slug>")
    parser.add_argument("--pr-body", default="", help="Pull request body text")
    parser.add_argument("--draft", action="store_true", help="Create the pull request as a draft")
    args = parser.parse_args()

    result = deliver_change(
        args.target_repo,
        change_slug=args.change_slug,
        phases=args.phases,
        push=args.push,
        open_pr=args.open_pr,
        pr_title=args.pr_title,
        pr_body=args.pr_body,
        draft=args.draft,
    )
    print(
        json.dumps(
            {
                "working_branch": result.branch.working_branch,
                "base_branch": result.branch.base_branch,
                "phases": {phase: [item.returncode for item in items] for phase, items in result.phases.items()},
                "pull_request_url": None if result.pull_request is None else result.pull_request.url,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
