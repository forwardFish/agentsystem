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
    if story_id == "S0-001":
        return _validate_profile_schema_story(repo_b_path)
    if story_id == "S0-002":
        return _validate_world_state_schema_story(repo_b_path, task_payload)
    if story_id == "S0-003":
        return _validate_agent_contract_story(repo_b_path, task_payload)
    if story_id == "S0-004":
        return _validate_error_state_spec_story(repo_b_path, task_payload)
    if story_id == "S0-005":
        return _validate_core_db_schema_story(repo_b_path, task_payload)
    if story_id == "S0-006":
        return _validate_statement_storage_story(repo_b_path, task_payload)
    return True, "No story-specific validation required."


def _validate_profile_schema_story(repo_b_path: Path) -> tuple[bool, str]:
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


def _validate_world_state_schema_story(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    if not related_files:
        related_files = [
            "docs/contracts/marketworldstate_schema.schema.json",
            "docs/contracts/examples/marketworldstate_schema.example.json",
            "docs/contracts/examples/marketworldstate_schema.invalid.json",
        ]

    schema_path = repo_b_path / next((path for path in related_files if "example" not in path.lower() and "invalid" not in path.lower()), related_files[0])
    example_path = repo_b_path / next((path for path in related_files if "example" in path.lower()), related_files[1])
    invalid_path = repo_b_path / next((path for path in related_files if "invalid" in path.lower()), related_files[-1])

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
        return True, "World state schema validates example and rejects invalid example."
    return False, "Invalid world state example unexpectedly passed schema validation."


def _validate_agent_contract_story(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    if not related_files:
        related_files = [
            "docs/contracts/agent_register.schema.json",
            "docs/contracts/agent_heartbeat.schema.json",
            "docs/contracts/agent_submit_actions.schema.json",
            "docs/contracts/examples/agent_register.example.json",
            "docs/contracts/examples/agent_heartbeat.example.json",
            "docs/contracts/examples/agent_submit_actions.example.json",
            "docs/contracts/examples/agent_submit_actions.invalid.json",
        ]

    for raw_path in related_files:
        path = repo_b_path / raw_path
        if not path.exists():
            return False, f"Missing required contract artifact: {path}"

    register_schema = json.loads((repo_b_path / "docs/contracts/agent_register.schema.json").read_text(encoding="utf-8"))
    heartbeat_schema = json.loads((repo_b_path / "docs/contracts/agent_heartbeat.schema.json").read_text(encoding="utf-8"))
    submit_schema = json.loads((repo_b_path / "docs/contracts/agent_submit_actions.schema.json").read_text(encoding="utf-8"))
    register_example = json.loads((repo_b_path / "docs/contracts/examples/agent_register.example.json").read_text(encoding="utf-8"))
    heartbeat_example = json.loads((repo_b_path / "docs/contracts/examples/agent_heartbeat.example.json").read_text(encoding="utf-8"))
    submit_example = json.loads((repo_b_path / "docs/contracts/examples/agent_submit_actions.example.json").read_text(encoding="utf-8"))
    invalid_submit_example = json.loads((repo_b_path / "docs/contracts/examples/agent_submit_actions.invalid.json").read_text(encoding="utf-8"))

    validate(instance=register_example, schema=register_schema)
    validate(instance=heartbeat_example, schema=heartbeat_schema)
    validate(instance=submit_example, schema=submit_schema)

    action_required = set(submit_schema["properties"]["actions"]["items"]["required"])
    expected = {"symbol", "side", "qty", "reason", "idempotency_key"}
    if action_required != expected:
        return False, "Submit-actions schema does not require the expected action fields."

    try:
        validate(instance=invalid_submit_example, schema=submit_schema)
    except Exception:
        return True, "Agent contract schemas validate valid examples and reject the invalid submit-actions example."
    return False, "Invalid submit-actions example unexpectedly passed schema validation."


def _validate_error_state_spec_story(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    if not related_files:
        related_files = [
            "docs/contracts/error_codes.md",
            "docs/contracts/state_machine.md",
        ]

    required_paths = [repo_b_path / raw_path for raw_path in related_files]
    for path in required_paths:
        if not path.exists():
            return False, f"Missing required contract artifact: {path}"

    error_codes = (repo_b_path / "docs/contracts/error_codes.md").read_text(encoding="utf-8")
    state_machine = (repo_b_path / "docs/contracts/state_machine.md").read_text(encoding="utf-8")

    error_sections = ["## Upload", "## Parsing", "## Risk", "## Matching", "## Permission"]
    missing_sections = [section for section in error_sections if section not in error_codes]
    if missing_sections:
        return False, f"Missing error code sections: {', '.join(missing_sections)}"

    required_states = [
        "uploaded",
        "parsing",
        "parsed",
        "failed",
        "active",
        "paused",
        "stale",
        "banned",
        "submitted",
        "rejected",
        "filled",
        "pending",
        "revoked",
        "expired",
    ]
    missing_states = [status for status in required_states if f"`{status}`" not in state_machine]
    if missing_states:
        return False, f"Missing state-machine statuses: {', '.join(missing_states)}"

    return True, "Error code and state machine documents include the required sections and transitions."


def _validate_core_db_schema_story(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    sql_path = repo_b_path / next((path for path in related_files if path.endswith(".sql")), "scripts/init_schema.sql")
    if not sql_path.exists():
        return False, f"Missing required SQL artifact: {sql_path}"

    sql = sql_path.read_text(encoding="utf-8")
    required_tables = [
        "agents",
        "statements",
        "trade_records",
        "agent_profiles",
        "world_snapshots",
        "orders",
        "fills",
        "portfolios",
        "positions",
        "equity_points",
        "audit_logs",
        "idempotency_keys",
    ]
    missing_tables = [table for table in required_tables if f"CREATE TABLE IF NOT EXISTS {table}" not in sql]
    if missing_tables:
        return False, f"Missing core tables: {', '.join(missing_tables)}"

    expected_constraints = [
        "PRIMARY KEY",
        "REFERENCES statements(statement_id)",
        "REFERENCES agents(agent_id)",
        "UNIQUE",
    ]
    missing_constraints = [token for token in expected_constraints if token not in sql]
    if missing_constraints:
        return False, f"Missing key SQL constraints: {', '.join(missing_constraints)}"

    if "CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id" not in sql:
        return False, "Missing audit log trace index."

    return True, "Core DB schema SQL defines the required tables, keys, references, and supporting indexes."


def _validate_statement_storage_story(repo_b_path: Path, task_payload: dict[str, object]) -> tuple[bool, str]:
    related_files = [str(item) for item in task_payload.get("related_files", [])]
    storage_path = repo_b_path / next((path for path in related_files if path.endswith("storage.py")), "apps/api/src/modules/statements/storage.py")
    repository_path = repo_b_path / next((path for path in related_files if path.endswith("repository.py")), "apps/api/src/modules/statements/repository.py")

    for path in (storage_path, repository_path):
        if not path.exists():
            return False, f"Missing required statement storage artifact: {path}"

    storage_code = storage_path.read_text(encoding="utf-8")
    repository_code = repository_path.read_text(encoding="utf-8")

    storage_tokens = ["build_statement_object_key", "save_statement_object", "delete_statement_object", "statements/{owner_id}/{statement_id}"]
    missing_storage = [token for token in storage_tokens if token not in storage_code]
    if missing_storage:
        return False, f"Missing storage helper behavior: {', '.join(missing_storage)}"

    repository_tokens = [
        "StatementMetadata",
        "create_statement_metadata_payload",
        "get_statement_metadata_query",
        "rollback_statement_metadata_query",
        "object_key",
        "market",
        "owner_id",
        "parsed_status",
    ]
    missing_repository = [token for token in repository_tokens if token not in repository_code]
    if missing_repository:
        return False, f"Missing repository metadata behavior: {', '.join(missing_repository)}"

    return True, "Statement storage artifacts support object-key generation, metadata persistence, lookup, and rollback."
