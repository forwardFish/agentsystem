from __future__ import annotations

from pathlib import Path

from agentsystem.core.state import DevState

SECRET_PATTERNS = ("ghp_", "api_key", "secret_key", "password=")


def security_node(state: DevState) -> DevState:
    print("[Security Agent] Scanning changed files")

    findings: list[str] = []
    changed_files = [line for line in (state.get("generated_code_diff") or "").splitlines() if line.strip()]
    for file_path in changed_files:
        path = Path(file_path)
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if any(pattern in content.lower() for pattern in SECRET_PATTERNS):
            findings.append(f"WARN: potential secret pattern found in {path.name}")

    if not findings:
        findings.append("PASS: no obvious secret or credential pattern found")

    state["security_report"] = "\n".join(findings)
    state["current_step"] = "security_done"

    for line in findings:
        print(f"[Security Agent] {line}")

    return state
