from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agentsystem.core.state import (
    AgentRole,
    Deliverable,
    DevState,
    HandoffPacket,
    HandoffStatus,
    add_executed_mode,
    add_handoff_packet,
)
from agentsystem.runtime.browser_session_manager import BrowserSessionManager
from agentsystem.runtime.playwright_browser_runtime import execute_browser_commands


def setup_browser_cookies_node(state: DevState) -> DevState:
    repo_b_path = Path(str(state["repo_b_path"])).resolve()
    task_payload = state.get("task_payload") or {}
    manager = BrowserSessionManager(repo_b_path, str(state.get("task_id") or repo_b_path.name))
    snapshot = manager.ensure_session()

    cookie_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "setup_browser_cookies"
    cookie_dir.mkdir(parents=True, exist_ok=True)

    raw_source = str(
        state.get("cookie_source")
        or task_payload.get("cookie_source")
        or task_payload.get("browser_profile_source")
        or ""
    ).strip()
    source_path = Path(raw_source).expanduser() if raw_source else None
    seeded = _seed_storage_state(manager.storage_state_file, source_path)

    command_result: dict[str, Any] | None = None
    import_count = 0
    try:
        command_result = execute_browser_commands(
            manager,
            [
                {
                    "command": "cookie-import-browser",
                    **({"source": str(source_path)} if source_path else {}),
                }
            ],
            target_name="setup-browser-cookies",
            kind="session",
            viewport_name="desktop",
            viewport={"width": 1280, "height": 720},
        )
        if command_result:
            try:
                import_count = int(((command_result.get("results") or [{}])[0].get("count") or 0))
            except (TypeError, ValueError):
                import_count = 0
        manager.update_session(cookies_imported=bool(import_count))
    except Exception:
        manager.update_session(cookies_imported=False)

    expectations = state.get("auth_expectations") or task_payload.get("auth_expectations") or []
    plan_lines = [
        "# Browser Cookie Import Plan",
        "",
        f"- Session ID: {snapshot.session_id}",
        f"- Source: {str(source_path) if source_path else 'auto-discover local browser profile'}",
        f"- Seeded storage state: {'yes' if seeded else 'no'}",
        f"- Imported into shared runtime: {'yes' if command_result else 'no'}",
        f"- Browser source used: {((command_result or {}).get('results') or [{}])[0].get('browser') if command_result else 'n/a'}",
        f"- Browser profile used: {((command_result or {}).get('results') or [{}])[0].get('browser_profile') if command_result else 'n/a'}",
        "",
        "## Expectations",
        *([f"- {item}" for item in expectations] or ["- Reuse this authenticated session for browse, design review, and QA."]),
        "",
        "## Notes",
        "- Secrets are normalized into local storage state and runtime artifacts; raw secrets are not echoed into reports.",
        "- If the source is a cookie list, it is wrapped into Playwright storage state before import.",
        "- Downstream browse and QA steps should validate that the authenticated state still holds.",
        "",
    ]
    plan_path = cookie_dir / "cookie_import_plan.md"
    plan_path.write_text("\n".join(plan_lines), encoding="utf-8")

    seed_path = cookie_dir / "session_seed.json"
    if manager.storage_state_file.exists():
        seed_path.write_text(manager.storage_state_file.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        seed_path.write_text(json.dumps({"cookies": [], "origins": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    if command_result is not None:
        command_path = cookie_dir / "command_result.json"
        command_path.write_text(json.dumps(command_result, ensure_ascii=False, indent=2), encoding="utf-8")

    state["setup_browser_cookies_success"] = True
    state["setup_browser_cookies_dir"] = str(cookie_dir)
    state["cookie_import_plan_path"] = str(plan_path)
    state["browser_storage_state_path"] = str(manager.storage_state_file)
    state["browser_runtime_dir"] = str(manager.runtime_dir)
    state["browser_session_id"] = snapshot.session_id
    state["current_step"] = "setup_browser_cookies_done"
    state["error_message"] = None
    add_executed_mode(state, "setup-browser-cookies")

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.SESSION_MANAGER,
            to_agent=AgentRole.BROWSE,
            status=HandoffStatus.COMPLETED,
            what_i_did="Prepared the shared browser session, normalized cookie input, and imported auth state into the runtime.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Cookie Import Plan",
                    type="report",
                    path=str(plan_path),
                    description="Authenticated browser session import plan and normalized storage state seed.",
                    created_by=AgentRole.SESSION_MANAGER,
                )
            ],
            what_risks_i_found=(
                ["Imported auth state may expire; validate the logged-in surface in the next browse or QA pass."]
                if seeded
                else ["No importable cookie source was provided."]
            ),
            what_i_require_next="Continue into browse or browser QA with the shared authenticated session.",
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )
    return state


def route_after_setup_browser_cookies(state: DevState) -> str:
    if str(state.get("stop_after") or "").strip() == "setup_browser_cookies":
        return "__end__"
    return "browse"


def _seed_storage_state(storage_state_path: Path, source_path: Path | None) -> bool:
    if source_path is None or not source_path.exists():
        return False
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    normalized: dict[str, Any]
    if isinstance(payload, dict) and "cookies" in payload:
        normalized = {
            "cookies": payload.get("cookies") or [],
            "origins": payload.get("origins") or [],
        }
    elif isinstance(payload, list):
        normalized = {"cookies": payload, "origins": []}
    else:
        return False
    storage_state_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return True
