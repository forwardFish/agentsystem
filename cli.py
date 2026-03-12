from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from main_production import run_prod_task
from scripts.fix_encoding import fix_tree_encoding
from scripts.validate_skill import validate_all_skills, validate_skill_file


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentSystem CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_task = subparsers.add_parser("run-task", help="Run a production task")
    run_task.add_argument("--task-file", required=True)
    run_task.add_argument("--env", default="production")

    validate_skill = subparsers.add_parser("validate-skill", help="Validate skill files")
    validate_skill.add_argument("--file")

    fix_encoding = subparsers.add_parser("fix-encoding", help="Normalize file encodings")
    fix_encoding.add_argument("--root", default=str(ROOT_DIR))

    args = parser.parse_args()

    if args.command == "run-task":
        output = run_prod_task(args.task_file, args.env)
        print(output["result"])
        return
    if args.command == "validate-skill":
        if args.file:
            ok = validate_skill_file(args.file)
            raise SystemExit(0 if ok else 1)
        raise SystemExit(0 if validate_all_skills(ROOT_DIR / "skills") else 1)
    if args.command == "fix-encoding":
        fix_tree_encoding(args.root)
        return


if __name__ == "__main__":
    main()
