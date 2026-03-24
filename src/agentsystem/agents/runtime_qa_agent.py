from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from agentsystem.adapters.config_reader import RepoBConfigReader
from agentsystem.agents.qa_contract import (
    build_qa_input_sources,
    build_qa_finding,
    build_regression_recommendations,
    build_verification_rerun_plan,
    compute_health_score,
    infer_ship_readiness,
    load_qa_test_context,
    sort_qa_findings,
    write_shared_qa_artifacts,
)
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
    test_context = load_qa_test_context(state, repo_b_path)
    commands = _runtime_qa_commands(repo_b_path)
    command_results: list[str] = []
    blocking_findings: list[str] = []
    warnings: list[str] = []
    structured_findings: list[dict[str, Any]] = []
    command_log_lines: list[str] = []

    if not commands:
        warnings.append("No dedicated runtime QA commands were configured; using verification basis and repository heuristics only.")
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=repo_b_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                shell=True,
                check=False,
            )
            summary = f"{command} -> {'PASS' if completed.returncode == 0 else 'FAIL'}"
            command_results.append(summary)
            command_log_lines.extend(
                [
                    f"$ {command}",
                    f"exit={completed.returncode}",
                    (completed.stdout or "").strip(),
                    (completed.stderr or "").strip(),
                    "",
                ]
            )
            if completed.returncode != 0:
                excerpt = (completed.stdout or completed.stderr or "").strip()[:280]
                finding_text = f"{command} failed. {excerpt}".strip()
                blocking_findings.append(finding_text)
                structured_findings.append(
                    build_qa_finding(
                        finding_id=f"RQA-{len(structured_findings) + 1:03d}",
                        severity="critical",
                        category="runtime_command",
                        summary=f"{command} failed during runtime QA",
                        detail=finding_text,
                        source_mode="runtime_qa",
                        evidence_refs=[],
                        recommended_action="Fix the failing runtime QA command, then rerun runtime QA.",
                        regression_hint=f"Add or update a regression check around `{command}` so this failure is caught earlier.",
                    )
                )
        except Exception as exc:  # pragma: no cover - defensive
            finding_text = f"{command} could not be executed: {exc}"
            command_log_lines.extend([f"$ {command}", f"exception={exc}", ""])
            blocking_findings.append(finding_text)
            structured_findings.append(
                build_qa_finding(
                    finding_id=f"RQA-{len(structured_findings) + 1:03d}",
                    severity="high",
                    category="runtime_command",
                    summary=f"{command} could not be executed",
                    detail=finding_text,
                    source_mode="runtime_qa",
                    evidence_refs=[],
                    recommended_action="Repair the QA command or environment, then rerun runtime QA.",
                    regression_hint=f"Stabilize the runtime QA command `{command}` and keep a regression check for it.",
                )
            )

    if not verification_basis:
        warnings.append("No verification_basis was declared; runtime QA relied on command results only.")
    if not (test_context.get("qa_handoff") or []):
        warnings.append("No QA handoff was recorded from plan-eng-review; runtime QA had to infer validation scope.")
    if not commands and (test_context.get("critical_paths") or test_context.get("failure_modes")):
        warnings.append("Runtime QA did not receive explicit runtime commands even though plan-eng-review declared critical paths or failure modes.")
    for warning in warnings:
        structured_findings.append(
            build_qa_finding(
                finding_id=f"RQA-{len(structured_findings) + 1:03d}",
                severity="medium",
                category="verification_gap",
                summary=warning,
                detail=warning,
                source_mode="runtime_qa",
                evidence_refs=[],
                recommended_action="Preserve stronger verification input from plan-eng-review before acceptance.",
            )
        )

    structured_findings = sort_qa_findings(structured_findings)
    health_score = compute_health_score(structured_findings)
    ship_readiness = infer_ship_readiness(structured_findings, report_only=report_only)
    input_sources = build_qa_input_sources(state, test_context, source_mode="runtime_qa", report_only=report_only)
    regression_recommendations = build_regression_recommendations(structured_findings, test_context)
    verification_rerun_plan = build_verification_rerun_plan(structured_findings, test_context, report_only=report_only)
    shared_artifacts = write_shared_qa_artifacts(
        repo_b_path,
        mode_id=str(state.get("effective_qa_mode") or "qa-only"),
        report_only=report_only,
        findings=structured_findings,
        health_score=health_score,
        ship_readiness=ship_readiness,
        test_context=test_context,
        regression_recommendations=regression_recommendations,
        verification_rerun_plan=verification_rerun_plan,
        input_sources=input_sources,
    )
    command_log_path = qa_dir / "runtime_qa_commands.log"
    command_log_path.write_text("\n".join(item for item in command_log_lines if item is not None), encoding="utf-8")

    report_lines = [
        "# Runtime QA Report",
        "",
        f"- Report only: {'yes' if report_only else 'no'}",
        f"- QA strategy: {state.get('qa_strategy') or 'runtime'}",
        f"- Effective QA mode: {state.get('effective_qa_mode') or 'qa-only'}",
        f"- Health score: {health_score}",
        f"- Ship readiness: {ship_readiness}",
        "",
        "## QA Input",
        f"- Test plan source: {test_context.get('plan_path') or 'none'}",
        *[f"- Input source: {item}" for item in input_sources],
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
    report_lines.extend(["", "## Structured Findings"])
    report_lines.extend(
        [
            f"- [{item['severity']}] {item['summary']} | next={item['recommended_action']}"
            for item in structured_findings
        ]
        or ["- None."]
    )
    report_lines.extend(["", "## Regression Recommendations"])
    report_lines.extend([f"- {item}" for item in regression_recommendations] or ["- None."])
    report_lines.extend(["", "## Verification Rerun Plan"])
    report_lines.extend([f"- {item}" for item in verification_rerun_plan] or ["- None."])
    report = "\n".join(report_lines)
    report_path = qa_dir / "runtime_qa_report.md"
    report_path.write_text(report, encoding="utf-8")

    state["runtime_qa_success"] = True
    state["runtime_qa_passed"] = not blocking_findings
    state["runtime_qa_report"] = report
    state["runtime_qa_dir"] = str(qa_dir)
    state["runtime_qa_findings"] = blocking_findings
    state["runtime_qa_warnings"] = warnings
    state["qa_findings"] = structured_findings
    state["qa_regression_recommendations"] = regression_recommendations
    state["qa_verification_rerun"] = verification_rerun_plan
    state["qa_input_sources"] = input_sources
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

    # Build risk list with context
    risks: list[str] = []
    if blocking_findings:
        risks.extend(blocking_findings[:3])  # Top 3 blocking issues
    if warnings:
        risks.extend(warnings[:2])  # Top 2 warnings

    # Add contextual risks
    if health_score < 80 and not report_only:
        risks.append(f"Health score {health_score}/100 is below the 80 threshold for confident release.")
    if not commands:
        risks.append("No runtime QA commands were configured; validation relies on heuristics only.")
    if not verification_basis:
        risks.append("No verification basis was declared; runtime QA cannot validate against explicit success criteria.")
    if not test_context.get("qa_handoff"):
        risks.append("No QA handoff from plan-eng-review; runtime QA had to infer validation scope without architectural guidance.")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.RUNTIME_QA,
            to_agent=AgentRole.FIXER if issues else AgentRole.SECURITY_SCANNER,
            status=HandoffStatus.BLOCKED if issues else HandoffStatus.COMPLETED,
            what_i_did=f"Executed {len(commands)} runtime QA command(s) against {len(verification_basis)} verification criteria, computed health score {health_score}/100, and validated non-UI story scope.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Runtime QA Report",
                    type="report",
                    path=f".meta/{repo_b_path.name}/runtime_qa/runtime_qa_report.md",
                    description=f"Non-UI QA report with {len(structured_findings)} structured findings, health score {health_score}/100, and ship readiness assessment.",
                    created_by=AgentRole.RUNTIME_QA,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Runtime QA Command Log",
                    type="report",
                    path=f".meta/{repo_b_path.name}/runtime_qa/runtime_qa_commands.log",
                    description="Execution log for all runtime QA commands with stdout, stderr, and exit codes.",
                    created_by=AgentRole.RUNTIME_QA,
                ),
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="QA Summary",
                    type="report",
                    path=f".meta/{repo_b_path.name}/qa/qa_summary.json",
                    description="Shared QA contract with structured findings, regression recommendations, and verification rerun plan for downstream agents.",
                    created_by=AgentRole.RUNTIME_QA,
                ),
            ],
            what_risks_i_found=risks[:5],  # Limit to top 5 risks
            what_i_require_next=(
                f"Fix {len(blocking_findings)} blocking runtime issue(s), then rerun Runtime QA to confirm resolution."
                if issues
                else "Continue to security scanner with runtime QA evidence and health score."
            ),
            issues=issues,
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    state["runtime_qa_health_score"] = health_score
    state["runtime_qa_ship_readiness"] = ship_readiness
    state["mode_artifact_paths"] = {
        **dict(state.get("mode_artifact_paths") or {}),
        "qa_summary": shared_artifacts["qa_summary_path"],
        "qa_findings": shared_artifacts["qa_findings_path"],
        "qa_context": shared_artifacts["qa_context_path"],
        "qa_rerun_plan": shared_artifacts["qa_rerun_plan_path"],
    }
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
