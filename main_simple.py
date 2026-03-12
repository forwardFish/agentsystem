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

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.context_assembler import ContextAssembler
from agentsystem.adapters.git_adapter import GitAdapter
from agentsystem.adapters.agent_executor import AgentExecutor
from agentsystem.adapters.skill_manager import SkillManager


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

        skill_manager = SkillManager(ROOT_DIR, repo_b_path)
        executor = AgentExecutor(skill_manager)

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
        print(f"[Builder] Mode: {'openai' if os.getenv('OPENAI_API_KEY') else 'fallback'}")
        llm_output = executor.execute_builder(task_yaml=task, current_code=current_code, constitution=constitution)
        new_code = _extract_code_block(llm_output)
        if not new_code or len(new_code) < len(current_code) * 0.5:
            raise ValueError("Generated code looks invalid. Aborting before write.")

        target_file.write_text(new_code + "\n", encoding="utf-8")
        print("[Builder] File updated")

        print("\n[Reviewer] Generating review report")
        review_report = executor.execute_reviewer(task_yaml=task, old_code=current_code, new_code=new_code)
        run_log["review_report_preview"] = review_report[:500]
        print("[Reviewer] Report generated")

        print("\n[Verifier] Running format commands")
        commands = RepoBConfigReader(repo_b_path).load_commands()
        verify_result = executor.execute_verifier(task_yaml=task, commands=commands, target_file=target_file)
        run_log["format_commands"] = [item["command"] for item in verify_result["commands"]]
        run_log["format_results"] = verify_result["commands"]
        if not verify_result["commands"]:
            print("[Verifier] No format commands configured")
        else:
            for item in verify_result["commands"]:
                status = "PASS" if item["success"] else "FAIL"
                print(f"[Verifier] {status}: {item['command']}")

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
