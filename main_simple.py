from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.llm.client import get_llm


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "task"


def write_run_log(data: dict[str, Any]) -> None:
    log_dir = ROOT_DIR / "runs"
    log_dir.mkdir(exist_ok=True)
    safe_task_name = _slugify(data["task_name"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{safe_task_name}_{timestamp}.json"
    log_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Audit] Log written to {log_file}")


def _format_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _extract_code_block(llm_output: str) -> str:
    if "```tsx" in llm_output:
        code_start = llm_output.find("```tsx") + len("```tsx")
        code_end = llm_output.rfind("```")
        return llm_output[code_start:code_end].strip()
    if "```" in llm_output:
        code_start = llm_output.find("```") + len("```")
        code_end = llm_output.rfind("```")
        return llm_output[code_start:code_end].strip()
    return llm_output.strip()


def _select_format_commands(commands: list[str], target_file: Path) -> list[str]:
    suffix = target_file.suffix.lower()
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        selected = [
            command
            for command in commands
            if any(token in command.lower() for token in ("pnpm", "prettier", "eslint"))
        ]
        return selected or commands
    if suffix == ".py":
        selected = [
            command
            for command in commands
            if any(token in command.lower() for token in ("black", "ruff", "python"))
        ]
        return selected or commands
    return commands


def main() -> None:
    load_dotenv()

    start_time = datetime.now()
    run_log: dict[str, Any] = {
        "start_time": start_time.isoformat(),
        "status": "running",
        "error_message": None,
    }

    print("=" * 60)
    print("Repo A minimal unattended loop")
    print("=" * 60)

    try:
        repo_b_path = os.getenv("REPO_B_LOCAL_PATH", "../versefina")
        task_file = ROOT_DIR / "tasks" / "current.yaml"
        if not task_file.exists():
            raise FileNotFoundError(f"Task card is missing: {task_file}")

        task = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        if not isinstance(task, dict):
            raise ValueError("tasks/current.yaml must contain a mapping")

        task_name = str(task["task_name"])
        run_log.update(
            {
                "task_name": task_name,
                "repo_b_path": str(Path(repo_b_path).resolve()),
                "related_files": task["related_files"],
            }
        )

        print(f"[Task] {task_name}")
        print(f"[Goal] {task['goal']}")

        print("\n[Context] Loading project constitution")
        assembler = ContextAssembler(repo_b_path)
        constitution = assembler.build_constitution()
        if len(constitution) < 100:
            raise ValueError("Project constitution is too short. Check Repo B AGENTS.md and CLAUDE.md.")
        print(f"[Context] Constitution loaded ({len(constitution)} chars)")

        print("\n[Git] Preparing repository")
        git = GitAdapter(repo_b_path)
        git.checkout_main_and_pull()
        branch_name = f"agent/{str(task.get('blast_radius', 'L1')).lower()}-{_slugify(task_name)}-{os.urandom(4).hex()}"
        git.create_new_branch(branch_name)
        run_log["branch_name"] = branch_name
        print(f"[Git] Switched to {branch_name}")

        target_file_rel = task["related_files"][0]
        target_file = Path(repo_b_path).resolve() / target_file_rel
        run_log["target_file"] = str(target_file)
        print(f"\n[File] Reading {target_file_rel}")
        if not target_file.exists():
            raise FileNotFoundError(f"Target file does not exist: {target_file}")

        current_code = target_file.read_text(encoding="utf-8")
        print(f"[File] Loaded {len(current_code)} chars")

        print("\n[Builder] Generating updated code")
        llm = get_llm()
        print(f"[Builder] Mode: {'openai' if os.getenv('OPENAI_API_KEY') else 'fallback'}")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a Builder Agent.
You must follow the project constitution below.

{constitution}

Rules:
1. Only modify the single target file.
2. Keep the code style aligned with the existing file.
3. Return only the complete updated file inside one ```tsx code block.
4. Do not include explanation outside the code block.
""".strip(),
                ),
                (
                    "user",
                    """
Task goal:
{task_goal}

Constraints:
{constraints}

Explicitly not doing:
{not_doing}

Current file:
```tsx
{current_code}
```

Return the full updated file.
""".strip(),
                ),
            ]
        )

        response = (prompt | llm).invoke(
            {
                "constitution": constitution,
                "task_goal": task["goal"],
                "constraints": _format_list(task.get("constraints", [])),
                "not_doing": _format_list(task.get("explicitly_not_doing", [])),
                "current_code": current_code,
            }
        )

        llm_output = response.content if hasattr(response, "content") else str(response)
        new_code = _extract_code_block(llm_output)
        if not new_code or len(new_code) < len(current_code) * 0.5:
            raise ValueError("Generated code looks invalid. Aborting before write.")

        target_file.write_text(new_code + "\n", encoding="utf-8")
        print("[Builder] File updated")

        print("\n[Verifier] Running format commands")
        commands = RepoBConfigReader(repo_b_path).load_commands()
        shell = ShellExecutor(repo_b_path)
        format_commands = _select_format_commands(commands.get("format", []), target_file)
        run_log["format_commands"] = list(format_commands)
        if not format_commands:
            print("[Verifier] No format commands configured")
        else:
            format_results: list[dict[str, Any]] = []
            for command in format_commands:
                success, output = shell.run_command(command)
                format_results.append(
                    {
                        "command": command,
                        "success": success,
                        "output_preview": output[:300],
                    }
                )
                status = "PASS" if success else "FAIL"
                print(f"[Verifier] {status}: {command}")
            run_log["format_results"] = format_results

        print("\n[Git] Creating commit")
        git.add_all()
        git.commit(f"feat(auto-dev): {task_name}\n\nGoal: {task['goal']}")
        commit_hash = git.get_current_commit()
        run_log["commit_hash"] = commit_hash
        print(f"[Git] Commit created: {commit_hash[:7]}")

        run_log["status"] = "success"
        end_time = datetime.now()
        run_log["end_time"] = end_time.isoformat()
        run_log["duration_seconds"] = (end_time - start_time).total_seconds()

        print("\n" + "=" * 60)
        print("Minimal unattended loop completed successfully")
        print("=" * 60)
        print(f"1. Review: cd {repo_b_path} && git diff HEAD^ HEAD")
        print(f"2. Merge if approved: cd {repo_b_path} && git checkout main && git merge {branch_name}")
    except Exception as exc:
        run_log["status"] = "failed"
        run_log["error_message"] = str(exc)
        print(f"\n[Error] {exc}")
        raise
    finally:
        write_run_log(run_log)


if __name__ == "__main__":
    main()
