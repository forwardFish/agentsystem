from __future__ import annotations

from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.core.state import DevState


def test_node(state: DevState) -> DevState:
    print("[Test Agent] Starting validation")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    config = RepoBConfigReader(repo_b_path).load_all_config()
    shell = ShellExecutor(repo_b_path)

    results: list[str] = []
    install_commands = config.commands.get("install", [])
    lint_commands = config.commands.get("lint", [])
    typecheck_commands = config.commands.get("typecheck", [])
    test_commands = config.commands.get("test", [])

    print("[Test Agent] Preparing environment")
    if install_commands:
        install_success, install_output = shell.run_commands(install_commands)
        results.append(f"Install: {'PASS' if install_success else 'FAIL'}")
        if not install_success:
            print(f"[Test Agent] Install output: {install_output[:200]}")
            state["error_message"] = f"Install failed: {install_output}"
    else:
        results.append("Install: SKIP (not configured)")

    print("[Test Agent] Running lint")
    if lint_commands:
        lint_success, lint_output = shell.run_commands(lint_commands[:1])
        results.append(f"Lint: {'PASS' if lint_success else 'FAIL'}")
        if not lint_success:
            print(f"[Test Agent] Lint output: {lint_output[:200]}")
            state["error_message"] = f"Lint failed: {lint_output}"
    else:
        results.append("Lint: SKIP (not configured)")

    print("[Test Agent] Evaluating typecheck")
    if typecheck_commands:
        results.append("Typecheck: SKIP (demo mode)")
    else:
        results.append("Typecheck: SKIP (not configured)")

    print("[Test Agent] Evaluating tests")
    if test_commands:
        results.append("Test: SKIP (demo mode)")
    else:
        results.append("Test: SKIP (not configured)")

    state["test_results"] = "\n".join(results)
    state["current_step"] = "test_done"
    if not state.get("error_message"):
        state["error_message"] = None

    print("[Test Agent] Report")
    for line in results:
        print(f"[Test Agent] {line}")

    print("[Test Agent] Validation completed")
    return state
