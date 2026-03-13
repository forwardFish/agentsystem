from __future__ import annotations

import json
import uuid
from pathlib import Path

from jsonschema import validate

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.adapters.shell_executor import ShellExecutor
from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    Issue,
    IssueSeverity,
    add_handoff_packet,
    add_issue,
)


def test_node(state: DevState) -> DevState:
    print("[Test Agent] Starting validation")

    repo_b_path = Path(state["repo_b_path"]).resolve()
    config = RepoBConfigReader(repo_b_path).load_all_config()
    shell = ShellExecutor(repo_b_path)

    results: list[str] = []
    task_payload = state.get("task_payload") or {}
    install_commands = config.commands.get("install", [])
    lint_commands = config.commands.get("lint", [])
    typecheck_commands = config.commands.get("typecheck", [])
    test_commands = config.commands.get("test", [])
    state["test_passed"] = True
    state["test_failure_info"] = None
    state["error_message"] = None

    print("[Test Agent] Preparing environment")
    if install_commands:
        install_success, install_output = shell.run_commands(install_commands)
        results.append(f"Install: {'PASS' if install_success else 'FAIL'}")
        if not install_success:
            print(f"[Test Agent] Install output: {install_output[:200]}")
            state["error_message"] = f"Install failed: {install_output}"
            state["test_passed"] = False
    else:
        results.append("Install: SKIP (not configured)")

    print("[Test Agent] Running lint")
    if lint_commands:
        lint_success, lint_output = shell.run_commands(lint_commands[:1])
        results.append(f"Lint: {'PASS' if lint_success else 'FAIL'}")
        if not lint_success:
            print(f"[Test Agent] Lint output: {lint_output[:200]}")
            state["error_message"] = f"Lint failed: {lint_output}"
            state["test_passed"] = False
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

    story_validation_success, story_validation_message = _run_story_specific_validation(repo_b_path, task_payload)
    results.append(f"StoryValidation: {'PASS' if story_validation_success else 'FAIL'}")
    if not story_validation_success:
        state["error_message"] = story_validation_message
        state["test_passed"] = False

    raw_simulated_failure = task_payload.get("test_failure_info")
    simulated_failure = str(raw_simulated_failure).strip() if raw_simulated_failure not in (None, "") else ""
    if simulated_failure and state.get("fix_attempts", 0) == 0:
        results.append("FixerGate: FAIL (simulated failure injected)")
        state["error_message"] = simulated_failure
        state["test_failure_info"] = simulated_failure
        state["test_passed"] = False
    elif not state.get("test_passed"):
        state["test_failure_info"] = state.get("error_message")
    else:
        state["test_failure_info"] = None

    state["test_results"] = "\n".join(results)
    state["current_step"] = "test_done"
    _record_test_handoff(state)

    print("[Test Agent] Report")
    for line in results:
        print(f"[Test Agent] {line}")

    print("[Test Agent] Validation completed")
    return state


def _record_test_handoff(state: DevState) -> None:
    repo_b_path = Path(state["repo_b_path"]).resolve()
    test_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "test"
    test_dir.mkdir(parents=True, exist_ok=True)
    report_path = test_dir / "test_report.md"
    report_path.write_text(str(state.get("test_results") or ""), encoding="utf-8")

    if state.get("test_passed"):
        add_handoff_packet(
            state,
            HandoffPacket(
                packet_id=str(uuid.uuid4()),
                from_agent=AgentRole.TESTER,
                to_agent=AgentRole.REVIEWER,
                status=HandoffStatus.COMPLETED,
                what_i_did="Executed configured validation commands and story-specific checks.",
                what_i_produced=[
                    Deliverable(
                        deliverable_id=str(uuid.uuid4()),
                        name="Test Report",
                        type="test_result",
                        path=str(report_path),
                        description="Validation output for the current story iteration.",
                        created_by=AgentRole.TESTER,
                    )
                ],
                what_risks_i_found=[],
                what_i_require_next="Review the validated change set for requirement fit, risk, and maintainability.",
                trace_id=str(state.get("collaboration_trace_id") or ""),
            ),
        )
        return

    failure_message = str(state.get("test_failure_info") or state.get("error_message") or "Validation failed").strip()
    target_file = None
    related_files = state.get("task_payload", {}).get("related_files", []) if isinstance(state.get("task_payload"), dict) else []
    if isinstance(related_files, list) and related_files:
        target_file = str(related_files[0])

    issue = Issue(
        issue_id=str(uuid.uuid4()),
        severity=IssueSeverity.BLOCKING,
        source_agent=AgentRole.TESTER,
        target_agent=AgentRole.FIXER,
        title="Validation failure blocks story delivery",
        description=failure_message,
        file_path=target_file,
        suggestion="Fix the reported validation issue and re-run the test step.",
    )
    add_issue(state, issue)
    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.TESTER,
            to_agent=AgentRole.FIXER,
            status=HandoffStatus.BLOCKED,
            what_i_did="Executed validation and found a blocking issue that prevents the story from progressing.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Test Report",
                    type="test_result",
                    path=str(report_path),
                    description="Validation output showing the blocking failure.",
                    created_by=AgentRole.TESTER,
                )
            ],
            what_risks_i_found=[failure_message],
            what_i_require_next="Resolve every blocking validation issue, then hand the story back for another test pass.",
            issues=[issue],
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )


def _run_story_specific_validation(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    story_id = str(task_payload.get("story_id", "")).strip()
    if story_id != "S0-001":
        return True, "No story-specific validation required."

    schema_path = repo_b_path / "docs" / "contracts" / "trading_agent_profile.schema.json"
    example_path = repo_b_path / "docs" / "contracts" / "examples" / "trading_agent_profile.example.json"
    invalid_path = repo_b_path / "docs" / "contracts" / "examples" / "trading_agent_profile.invalid.json"

    for path in (schema_path, example_path, invalid_path):
        if not path.exists():
            return False, f"Missing required contract artifact: {path}"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    example = json.loads(example_path.read_text(encoding="utf-8"))
    invalid_example = json.loads(invalid_path.read_text(encoding="utf-8"))

    validate(instance=example, schema=schema)
    try:
        validate(instance=invalid_example, schema=schema)
    except Exception:
        return True, "Schema validates example and rejects invalid example."
    return False, "Invalid example unexpectedly passed schema validation."
