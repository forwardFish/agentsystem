from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from git import Repo

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.github_pr import GitHubPullRequestAdapter
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.core.constants import (
    DEMO_BRANCH_SLUG,
    DEMO_COMMIT_MESSAGE,
    DEMO_PR_BODY,
    DEMO_PR_TITLE,
    REPLACEMENT_SENTENCE,
    TARGET_SENTENCE,
)
from agentsystem.core.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    source_repo_b_path = Path(settings.repo_b_local_path).resolve()

    print("=== Repo A demo start ===")
    print("1. Load Repo B .agents config")
    config_reader = RepoBConfigReader(source_repo_b_path)
    repo_config = config_reader.load_all_config()
    print(f"[OK] Project: {repo_config.project['name']}")
    print(f"[OK] Frontend path: {repo_config.project['stack']['frontend']['path']}")

    print("\n2. Prepare clean checkout")
    default_branch = repo_config.project["git"]["default_branch"]
    branch_prefix = repo_config.project["git"]["working_branch_prefix"]
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    new_branch = f"{branch_prefix}{DEMO_BRANCH_SLUG}-{timestamp}"

    with TemporaryDirectory(prefix="agentsystem-demo-", ignore_cleanup_errors=True) as tmp:
        repo_b_path = _prepare_clean_checkout(source_repo_b_path, Path(tmp), default_branch)
        git = GitAdapter(repo_b_path)
        git.checkout_main_and_pull(default_branch)
        git.create_new_branch(new_branch)
        print(f"[OK] Working branch: {new_branch}")

        print("\n3. Update Repo B source")
        home_page_path = repo_b_path / "apps" / "web" / "src" / "app" / "page.tsx"
        content = home_page_path.read_text(encoding="utf-8")
        if TARGET_SENTENCE not in content:
            raise RuntimeError(f"Target sentence not found in {home_page_path}")
        updated_content = content.replace(TARGET_SENTENCE, REPLACEMENT_SENTENCE, 1)
        home_page_path.write_text(updated_content, encoding="utf-8")
        print(f"[OK] Updated {home_page_path.relative_to(repo_b_path)}")

        shell = ShellExecutor(repo_b_path)

        print("\n4. Install project dependencies")
        install_commands = repo_config.commands.get("install", [])
        install_success, install_output = shell.run_commands(install_commands)
        if not install_success:
            raise RuntimeError(f"Install failed:\n{install_output}")
        print("[OK] Install completed")

        print("\n5. Run lint")
        lint_commands = repo_config.commands["lint"]
        lint_success, lint_output = shell.run_commands(lint_commands)
        if not lint_success:
            raise RuntimeError(f"Lint failed:\n{lint_output}")
        print("[OK] Lint passed")

        print("\n6. Commit and push branch")
        git.add_and_commit(DEMO_COMMIT_MESSAGE)
        git.push_branch(new_branch)
        print("[OK] Branch pushed to origin")

        print("\n7. Open GitHub PR")
        if not settings.github_token or not settings.github_owner or not settings.github_repo_b_name:
            raise RuntimeError("Missing GitHub config in .env")
        pr = GitHubPullRequestAdapter(
            token=settings.github_token,
            owner=settings.github_owner,
            repo_name=settings.github_repo_b_name,
        )
        pr_url = pr.create_pull_request(
            title=DEMO_PR_TITLE,
            body=DEMO_PR_BODY,
            head_branch=new_branch,
            base_branch=default_branch,
        )
        print(f"[OK] PR created: {pr_url}")

    print("\n=== Repo A demo completed ===")


def _prepare_clean_checkout(source_repo_b_path: Path, working_root: Path, default_branch: str) -> Path:
    source_repo = Repo(source_repo_b_path)
    clone_target = working_root / "repo_b"
    remote_url = source_repo.remotes.origin.url if source_repo.remotes else None

    if source_repo.remotes:
        source_repo.git.fetch("origin", default_branch)
        active_branch = source_repo.active_branch.name if not source_repo.head.is_detached else None
        if active_branch != default_branch:
            source_repo.git.branch("-f", default_branch, f"origin/{default_branch}")

    Repo.clone_from(str(source_repo_b_path), clone_target, branch=default_branch)
    clone_repo = Repo(clone_target)
    if remote_url:
        clone_repo.remotes.origin.set_url(remote_url)
    return clone_target


if __name__ == "__main__":
    main()
