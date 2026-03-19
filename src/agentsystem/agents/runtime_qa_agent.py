from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    Issue,
    IssueSeverity,
    add_executed_mode,
    add_handoff_packet,
    add_issue,
)


def runtime_qa_node(state: DevState) -> DevState:
    print("[Runtime QA Agent] Running non-UI verification")

    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    qa_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "runtime_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    report_only = bool(state.get("runtime_qa_report_only", state.get("browser_qa_report_only", True)))
    verification_basis = [str(item).strip() for item in (state.get("verification_basis") or []) if str(item).strip()]
    commands = _runtime_qa_commands(repo_b_path)
    command_results: list[str] = []
    blocking_findings: list[str] = []
    warnings: list[str] = []

    if not commands:
        warnings.append("No dedicated runtime QA commands were configured; using verification basis and repository heuristics only.")
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=repo_b_path,
                capture_output=True,
                text=True,
                timeout=120,
                shell=True,
                check=False,
            )
            summary = f"{command} -> {'PASS' if completed.returncode == 0 else 'FAIL'}"
            command_results.append(summary)
            if completed.returncode != 0:
                excerpt = (completed.stdout or completed.stderr or "").strip()[:280]
                blocking_findings.append(f"{command} failed. {excerpt}".strip())
        except Exception as exc:  # pragma: no cover - defensive
            blocking_findings.append(f"{command} could not be executed: {exc}")

    if not verification_basis:
        warnings.append("No verification_basis was declared; runtime QA relied on command results only.")

    report_lines = [
        "# Runtime QA Report",
        "",
        f"- Report only: {'yes' if report_only else 'no'}",
        f"- QA strategy: {state.get('qa_strategy') or 'runtime'}",
        f"- Effective QA mode: {state.get('effective_qa_mode') or 'qa-only'}",
        "",
        "## Verification Basis",
    ]
    report_lines.extend([f"- {item}" for item in verification_basis] or ["- No verification basis recorded."])
    report_lines.extend(["", "## Runtime QA Commands"])
    report_lines.extend([f"- {item}" for item in command_results] or ["- No runtime QA commands executed."])
    report_lines.extend(["", "## Blocking Findings"])
    report_lines.extend([f"- {item}" for item in blocking_findings] or ["- None."])
    report_lines.extend(["", "## Warnings"])
    report_lines.extend([f"- {item}" for item in warnings] or ["- None."])
    report = "\n".join(report_lines)
    report_path = qa_dir / "runtime_qa_report.md"
    report_path.write_text(report, encoding="utf-8")

    state["runtime_qa_success"] = True
    state["runtime_qa_passed"] = not blocking_findings
    state["runtime_qa_report"] = report
    state["runtime_qa_dir"] = str(qa_dir)
    state["runtime_qa_findings"] = blocking_findings
    state["runtime_qa_warnings"] = warnings
    state["runtime_qa_report_only"] = report_only
    state["current_step"] = "runtime_qa_done"
    state["error_message"] = None if not blocking_findings or report_only else "; ".join(blocking_findings)
    mode_id = str((state.get("task_payload") or {}).get("skill_mode") or "").strip()
    if mode_id in {"qa", "qa-only"}:
        add_executed_mode(state, mode_id)
    else:
        add_executed_mode(state, str(state.get("effective_qa_mode") or "qa-only"))

    issues: list[Issue] = []
    if blocking_findings and not report_only:
        target_file = _primary_target_file(state.get("task_payload") or {})
        for finding in blocking_findings:
            issue = Issue(
                issue_id=str(uuid.uuid4()),
                severity=IssueSeverity.BLOCKING,
                source_agent=AgentRole.RUNTIME_QA,
                target_agent=AgentRole.FIXER,
                title="Runtime QA blocking issue",
                description=finding,
                file_path=target_file,
                suggestion="Fix the runtime/data validation regression and re-run Runtime QA.",
            )
            add_issue(state, issue)
            issues.append(issue)

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.RUNTIME_QA,
            to_agent=AgentRole.FIXER if issues else AgentRole.SECURITY_SCANNER,
            status=HandoffStatus.BLOCKED if issues else HandoffStatus.COMPLETED,
            what_i_did="Ran runtime-oriented verification for non-UI story scope using repository QA commands and verification basis.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Runtime QA Report",
                    type="report",
                    path=f".meta/{repo_b_path.name}/runtime_qa/runtime_qa_report.md",
                    description="Non-UI QA report with runtime and artifact validation findings.",
                    created_by=AgentRole.RUNTIME_QA,
                )
            ],
            what_risks_i_found=blocking_findings or warnings,
            what_i_require_next=(
                "Resolve every blocking runtime QA issue, then run Runtime QA again."
                if issues
                else "Continue into security and review checks."
            ),
            issues=issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    print("[Runtime QA Agent] Verification completed")
    return state


def route_after_runtime_qa(state: DevState) -> str:
    if not state.get("runtime_qa_success"):
        return "security_scanner"
    if (
        not state.get("runtime_qa_passed")
        and (
            state.get("fixer_allowed", True)
            or state.get("auto_upgrade_to_qa")
        )
        and state.get("fix_attempts", 0) < 2
    ):
        state["runtime_qa_report_only"] = False
        state["fixer_allowed"] = True
        state["effective_qa_mode"] = "qa"
        add_executed_mode(state, "qa")
        return "fixer"
    if str(state.get("stop_after") or "").strip() in {"runtime_qa", "browser_qa"}:
        return "__end__"
    return "security_scanner"


def _runtime_qa_commands(repo_b_path: Path) -> list[str]:
    config = RepoBConfigReader(repo_b_path).load_all_config()
    commands = config.commands
    runtime_commands: list[str] = []
    for key in ("runtime_qa", "validation", "gate_check"):
        value = commands.get(key)
        if isinstance(value, list):
            runtime_commands.extend(str(item).strip() for item in value if str(item).strip())
    if runtime_commands:
        return runtime_commands

    known_paths = [
        repo_b_path / "tools" / "gate_check" / "validate_norms.py",
        repo_b_path / "tools" / "run_live_event_cognition.py",
    ]
    if known_paths[0].exists():
        runtime_commands.append("python tools/gate_check/validate_norms.py")
    if not runtime_commands and commands.get("test"):
        runtime_commands.extend(str(item).strip() for item in commands["test"] if str(item).strip())
    return runtime_commands


def _primary_target_file(task_payload: dict[str, Any]) -> str | None:
    for key in ("primary_files", "related_files"):
        value = task_payload.get(key)
        if isinstance(value, list):
            for item in value:
                candidate = str(item).strip()
                if candidate:
                    return candidate
    return None
