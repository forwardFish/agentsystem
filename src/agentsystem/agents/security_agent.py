from __future__ import annotations

import uuid
from pathlib import Path

from agentsystem.core.state import AgentRole, Deliverable, DevState, HandoffPacket, HandoffStatus, add_handoff_packet

SECRET_PATTERNS = ("ghp_", "api_key", "secret_key", "password=")


def security_node(state: DevState) -> DevState:
    print("[Security Agent] Scanning changed files")

    findings: list[str] = []
    changed_files = [line for line in (state.get("generated_code_diff") or "").splitlines() if line.strip()]
    scanned_count = 0

    for file_path in changed_files:
        path = Path(file_path)
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            scanned_count += 1
            if any(pattern in content.lower() for pattern in SECRET_PATTERNS):
                findings.append(f"WARN: potential secret pattern found in {path.name}")
        except Exception:
            continue

    if not findings:
        findings.append("PASS: no obvious secret or credential pattern found")

    report = "\n".join(findings)
    state["security_report"] = report
    state["current_step"] = "security_done"

    # Build risk list with context
    risks: list[str] = []
    warning_findings = [f for f in findings if f.startswith("WARN:")]
    if warning_findings:
        risks.extend(warning_findings[:3])  # Top 3 warnings

    # Add contextual risks
    if scanned_count == 0:
        risks.append("No files were scanned; security check cannot validate credential leakage.")
    if len(changed_files) > 20:
        risks.append(f"Large change set ({len(changed_files)} files) increases risk of accidental credential exposure.")
    env_files = [f for f in changed_files if ".env" in f.lower() or "config" in f.lower()]
    if env_files:
        risks.append(f"{len(env_files)} configuration/environment file(s) modified; manual review recommended for credential safety.")

    repo_b_path = Path(str(state.get("repo_b_path", "."))).resolve()
    task_scope_name = repo_b_path.name

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.SECURITY_SCANNER,
            to_agent=AgentRole.CODE_STYLE_REVIEWER,
            status=HandoffStatus.COMPLETED,
            what_i_did=f"Scanned {scanned_count} changed file(s) for credential patterns (ghp_, api_key, secret_key, password=) before code review.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Security Scan Report",
                    type="report",
                    path=f".meta/{task_scope_name}/security/security_report.txt",
                    description=f"Security scan results for {scanned_count} file(s) with credential pattern detection.",
                    created_by=AgentRole.SECURITY_SCANNER,
                )
            ],
            what_risks_i_found=risks[:5] if risks else ["No security risks detected in scanned files."],
            what_i_require_next="Proceed to code style review, then full code review with the security scan evidence.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    for line in findings:
        print(f"[Security Agent] {line}")

    return state
