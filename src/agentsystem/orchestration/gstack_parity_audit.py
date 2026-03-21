from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy
from agentsystem.orchestration.full_parity_evidence import latest_passing_evidence_by_mode
from agentsystem.runtime.playwright_browser_runtime import supported_browser_commands


BASE_DIR = Path(__file__).resolve().parents[3]
PARITY_MANIFEST_PATH = BASE_DIR / "config" / "platform" / "gstack_parity_manifest.yaml"
SKILL_MODE_PATH = BASE_DIR / "config" / "skill_modes" / "software_engineering.yaml"
WORKFLOW_PATH = BASE_DIR / "config" / "workflows" / "software_engineering.yaml"
ALLOWED_PARITY_STATUSES = {"template_only", "partial_runtime", "workflow_wired", "full_parity"}


def build_gstack_parity_audit(
    *,
    root_dir: Path | None = None,
    sprint_dir: str | Path | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    resolved_root = Path(root_dir or BASE_DIR).resolve()
    manifest = _load_yaml(resolved_root / "config" / "platform" / "gstack_parity_manifest.yaml")
    skill_modes = _mode_index(_load_yaml(resolved_root / "config" / "skill_modes" / "software_engineering.yaml").get("modes") or [])
    workflow_nodes = {
        str(item.get("node_id") or "").strip()
        for item in (_load_yaml(resolved_root / "config" / "workflows" / "software_engineering.yaml").get("nodes") or [])
        if isinstance(item, dict)
    }
    evidence_by_mode = latest_passing_evidence_by_mode(resolved_root)

    agents: list[dict[str, Any]] = []
    for agent in manifest.get("agents") or []:
        if not isinstance(agent, dict):
            continue
        mode_id = str(agent.get("mode_id") or "").strip()
        if not mode_id:
            continue
        checks = _build_structural_checks(agent, resolved_root, skill_modes, workflow_nodes)
        acceptance = _build_acceptance_checklist(mode_id, agent, resolved_root)
        parity_status = str(agent.get("parity_status") or "").strip()
        dogfood_eligible = _is_dogfood_eligible(parity_status, checks, acceptance)
        if parity_status not in ALLOWED_PARITY_STATUSES:
            checks.append({"name": "parity_status_valid", "status": "failed", "detail": f"Unexpected parity status: {parity_status}"})
        else:
            checks.append({"name": "parity_status_valid", "status": "passed", "detail": parity_status})
        agents.append(
            {
                "mode_id": mode_id,
                "entry_mode": agent.get("entry_mode"),
                "stop_after": agent.get("stop_after"),
                "declared_parity_status": parity_status,
                "parity_status": parity_status,
                "dogfood_eligible": dogfood_eligible,
                "missing_capabilities": list(agent.get("missing_capabilities") or []),
                "intentional_deviations": list(agent.get("intentional_deviations") or []),
                "checks": checks,
                "acceptance_checklist": acceptance,
                "formal_evidence_entries": list(evidence_by_mode.get(mode_id) or []),
                "formal_evidence_complete": False,
                "full_parity_upgrade_blockers": [],
                "full_parity_claimable": False,
            }
        )

    dogfood_target = None
    if sprint_dir:
        dogfood_target = _build_sprint_dogfood_target(Path(sprint_dir).resolve(), agents, root_dir=resolved_root, project=project)

    required_modes = set((dogfood_target or {}).get("required_modes") or [])
    dogfood_completed = bool((dogfood_target or {}).get("dogfood_completed"))
    for agent in agents:
        declared_parity_status = str(agent.get("declared_parity_status") or "").strip()
        mode_id = str(agent.get("mode_id") or "").strip()
        formal_evidence_complete = bool(dogfood_completed) if mode_id in required_modes else bool(agent.get("formal_evidence_entries"))
        full_parity_upgrade_blockers = _build_full_parity_upgrade_blockers(
            parity_status=declared_parity_status,
            checks=list(agent.get("checks") or []),
            acceptance=list(agent.get("acceptance_checklist") or []),
            missing_capabilities=list(agent.get("missing_capabilities") or []),
            dogfood_eligible=bool(agent.get("dogfood_eligible")),
            requires_dogfood=mode_id in required_modes,
            dogfood_completed=dogfood_completed,
            formal_evidence_complete=formal_evidence_complete,
        )
        resolved_status = (
            "full_parity"
            if declared_parity_status in {"workflow_wired", "partial_runtime", "full_parity"} and not full_parity_upgrade_blockers
            else declared_parity_status
        )
        agent["parity_status"] = resolved_status
        agent["formal_evidence_complete"] = formal_evidence_complete
        agent["full_parity_upgrade_blockers"] = full_parity_upgrade_blockers
        agent["full_parity_claimable"] = bool(resolved_status == "full_parity")

    audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "upstream": dict(manifest.get("upstream") or {}),
        "agents": agents,
        "summary": _build_summary(agents),
    }
    if dogfood_target is not None:
        audit["dogfood_target"] = dogfood_target
    return audit


def write_gstack_parity_audit(
    output_dir: str | Path,
    *,
    root_dir: Path | None = None,
    sprint_dir: str | Path | None = None,
    project: str | None = None,
) -> dict[str, str]:
    audit = build_gstack_parity_audit(root_dir=root_dir, sprint_dir=sprint_dir, project=project)
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "parity_manifest.json"
    checklist_path = target_dir / "acceptance_checklist.md"
    manifest_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_path.write_text(_render_acceptance_checklist(audit), encoding="utf-8")
    return {
        "parity_manifest_path": str(manifest_path),
        "acceptance_checklist_path": str(checklist_path),
    }


def _build_structural_checks(
    agent: dict[str, Any],
    root_dir: Path,
    skill_modes: dict[str, dict[str, Any]],
    workflow_nodes: set[str],
) -> list[dict[str, str]]:
    mode_id = str(agent.get("mode_id") or "").strip()
    checks: list[dict[str, str]] = []
    for field_name in ("upstream_skill", "local_template_dir", "local_codex_adapter_dir"):
        relative = str(agent.get(field_name) or "").strip()
        path = root_dir / relative if relative else None
        checks.append(
            {
                "name": field_name,
                "status": "passed" if path and path.exists() else "failed",
                "detail": str(path) if path else "(missing)",
            }
        )
    mode_spec = skill_modes.get(mode_id)
    checks.append(
        {
            "name": "skill_mode_registered",
            "status": "passed" if mode_spec else "failed",
            "detail": SKILL_MODE_PATH.as_posix(),
        }
    )
    checks.append(
        {
            "name": "entry_mode_matches",
            "status": "passed" if mode_spec and str(mode_spec.get("entry_mode") or "") == str(agent.get("entry_mode") or "") else "failed",
            "detail": f"mode={mode_spec.get('entry_mode') if mode_spec else None} manifest={agent.get('entry_mode')}",
        }
    )
    checks.append(
        {
            "name": "stop_after_matches",
            "status": "passed" if mode_spec and str(mode_spec.get("stop_after") or "") == str(agent.get("stop_after") or "") else "failed",
            "detail": f"mode={mode_spec.get('stop_after') if mode_spec else None} manifest={agent.get('stop_after')}",
        }
    )
    stop_after = str(agent.get("stop_after") or "").strip()
    checks.append(
        {
            "name": "workflow_node_registered",
            "status": "passed" if stop_after in workflow_nodes else "failed",
            "detail": stop_after,
        }
    )
    return checks


def _build_acceptance_checklist(mode_id: str, agent: dict[str, Any], root_dir: Path) -> list[dict[str, Any]]:
    gate_statuses = _gate_statuses_for_mode(mode_id, root_dir)
    checklist: list[dict[str, Any]] = []
    for gate in agent.get("acceptance_gates") or []:
        gate_text = str(gate).strip()
        payload = gate_statuses.get(gate_text) or {"status": "pending", "evidence": [], "detail": "No automated gate mapped yet."}
        checklist.append(
            {
                "gate": gate_text,
                "status": payload["status"],
                "detail": payload["detail"],
                "evidence_refs": payload["evidence"],
            }
        )
    return checklist


def _gate_statuses_for_mode(mode_id: str, root_dir: Path) -> dict[str, dict[str, Any]]:
    runtime_commands = set(supported_browser_commands())
    architecture_review_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "architecture_review_agent.py")
    office_hours_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "office_hours_agent.py")
    investigate_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "investigate_agent.py")
    design_consultation_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "design_consultation_agent.py")
    plan_design_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "plan_design_review_agent.py")
    qa_design_review_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "qa_design_review_agent.py")
    workspace_prep_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "workspace_prep_agent.py")
    review_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "review_agent.py")
    test_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "test_agent.py")
    runtime_qa_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "runtime_qa_agent.py")
    ship_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "ship_agent.py")
    document_release_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "document_release_agent.py")
    retro_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "retro_agent.py")
    browse_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py")
    cookie_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "setup_browser_cookies_agent.py")
    qa_contract_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "qa_contract.py")
    browser_runtime_source = _read_text(root_dir / "src" / "agentsystem" / "runtime" / "playwright_browser_runtime.py")
    browser_session_source = _read_text(root_dir / "src" / "agentsystem" / "runtime" / "browser_session_manager.py")
    browser_host_source = _read_text(root_dir / "src" / "agentsystem" / "runtime" / "browser_host_server.py")
    if mode_id == "plan-eng-review":
        return {
            "Architecture review report exists": {
                "status": "passed" if all(token in architecture_review_source for token in ("architecture_review_report.md", "## Architecture Diagram", "## QA Handoff", "## Open Planning Questions")) else "failed",
                "detail": "architecture_review_agent.py renders the architecture review report with diagram, QA handoff, and staged planning-question sections.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "architecture_review_agent.py")],
            },
            "Test plan exists": {
                "status": "passed" if all(token in architecture_review_source + workspace_prep_source for token in ("test_plan.json", "qa_test_plan.md", "failure_modes.json", "planning_decision_state.json", "plan_eng_review_required")) else "failed",
                "detail": "architecture_review_agent.py writes structured plan/test artifacts and workspace_prep_agent.py blocks build when plan-eng-review is missing.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "architecture_review_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "workspace_prep_agent.py"),
                ],
            },
        }
    if mode_id == "office-hours":
        return {
            "Six forcing questions artifact exists": {
                "status": "passed" if office_hours_source.count('("') >= 6 and "FORCING_QUESTIONS" in office_hours_source else "failed",
                "detail": "office_hours_agent.py defines six forcing questions.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "office_hours_agent.py")],
            },
            "Dialogue state and design doc artifacts exist": {
                "status": "passed" if all(token in office_hours_source for token in ("dialogue_state.json", "design_doc.md", "office_hours_next_question")) else "failed",
                "detail": "office_hours_agent.py persists dialogue state and a design-doc style artifact for the office-hours session.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "office_hours_agent.py")],
            },
            "Handoff summary points to plan-ceo-review and plan-eng-review": {
                "status": "passed" if "plan-ceo-review" in office_hours_source and "plan-eng-review" in office_hours_source else "failed",
                "detail": "office_hours_agent.py handoff text references downstream planning agents.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "office_hours_agent.py")],
            },
        }
    if mode_id == "plan-ceo-review":
        plan_ceo_source = _read_text(root_dir / "src" / "agentsystem" / "agents" / "plan_ceo_review_agent.py")
        return {
            "Requirement document exists": {
                "status": "passed" if "requirement_doc_path.write_text" in plan_ceo_source else "failed",
                "detail": "plan_ceo_review_agent.py writes a requirement document artifact.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "plan_ceo_review_agent.py")],
            },
            "Opportunity map exists": {
                "status": "passed" if "opportunity_map_path.write_text" in plan_ceo_source else "failed",
                "detail": "plan_ceo_review_agent.py writes an opportunity-map artifact.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "plan_ceo_review_agent.py")],
            },
            "Decision ceremony exists with selected mode and scope proposals": {
                "status": "passed" if all(token in plan_ceo_source for token in ("decision_ceremony_path", "selected_mode", "accepted_expansions", "unresolved_decisions")) else "failed",
                "detail": "plan_ceo_review_agent.py persists CEO review mode selection and scope proposal decisions.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "plan_ceo_review_agent.py")],
            },
        }
    if mode_id == "investigate":
        return {
            "Investigation report includes evidence, data flow, hypotheses, failed attempts, root cause, and verification plan": {
                "status": "passed" if all(token in investigate_source for token in ("## Data Flow", "## Reproduction Checklist", "## Temporary Instrumentation", "## Failed Attempts", "## Root Cause", "## Verification Plan", "reproduction_checklist.json", "instrumentation_plan.json")) else "failed",
                "detail": "investigate_agent.py renders reproduction, instrumentation, evidence, and verification artifacts before any fix is allowed.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "investigate_agent.py")],
            },
            "Bugfix build path is blocked if investigation report is missing": {
                "status": "passed" if "investigation_report" in workspace_prep_source and "bug_scope" in workspace_prep_source else "failed",
                "detail": "workspace_prep_agent.py blocks build/fix when investigation is missing.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "workspace_prep_agent.py")],
            },
        }
    if mode_id == "browse":
        return {
            ".gstack browse state file exposes pid, port, token, binaryVersion, and workspaceRoot": {
                "status": "passed" if all(token in browser_session_source for token in ("browse_state_file", "binaryVersion", "workspaceRoot", "token", "port", "pid")) else "failed",
                "detail": "browser_session_manager.py defines the .gstack browse state compatibility layer.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "runtime" / "browser_session_manager.py")],
            },
            "Shared browser host reuses session across independent invocations and downstream QA/design-review/setup-browser-cookies": {
                "status": "passed" if all(token in browser_runtime_source for token in ("_ensure_browser_host", "_send_browser_host_command", "SERVER_ENTRYPOINT")) and all(token in browse_source + cookie_source for token in ("BrowserSessionManager", "run_browser_capture", "execute_browser_commands")) else "failed",
                "detail": "browse host is started out-of-process and reused by browse, QA, and cookie setup entrypoints.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "runtime" / "playwright_browser_runtime.py"),
                    str(root_dir / "src" / "agentsystem" / "runtime" / "browser_host_server.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "setup_browser_cookies_agent.py"),
                ],
            },
            "Shared browser command runtime supports goto, click, type, wait, screenshot, snapshot refs, chain, tabs, storage_state, import_cookies, and cookie-import-browser": {
                "status": "passed" if {"goto", "click", "type", "wait", "screenshot", "snapshot", "chain", "tabs", "tab", "storage_state", "import_cookies", "cookie-import-browser"}.issubset(runtime_commands) and all(token in browser_runtime_source for token in ("_capture_snapshot_refs", "_resolve_selector", "\"chain\"")) else "failed",
                "detail": "playwright_browser_runtime.py exposes the gstack-style browser command surface with ref and chain support.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "runtime" / "playwright_browser_runtime.py")],
            },
        }
    if mode_id == "plan-design-review":
        return {
            "Design review report exists": {
                "status": "passed" if all(token in plan_design_source for token in ("design_review_report.md", "## Route-Level Findings", "design_scorecard.json")) else "failed",
                "detail": "plan_design_review_agent.py renders a route-aware review report with route-level findings.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "plan_design_review_agent.py")],
            },
            "DESIGN.md handoff exists": {
                "status": "passed" if all(token in plan_design_source for token in ("DESIGN.md", "route_findings.json", "design_contract_path")) else "failed",
                "detail": "plan_design_review_agent.py writes DESIGN.md plus route findings for downstream builder and design review.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "plan_design_review_agent.py")],
            },
        }
    if mode_id == "design-consultation":
        return {
            "Design consultation report exists": {
                "status": "passed" if all(token in design_consultation_source for token in ("# Design Consultation", "design_consultation_report.md", "Design Consultation Report")) else "failed",
                "detail": "design_consultation_agent.py writes a consultation report with audience, modules, and direction.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "design_consultation_agent.py")],
            },
            "DESIGN.md or preview artifact exists": {
                "status": "passed" if all(token in design_consultation_source for token in ("DESIGN.md", "design_preview_path", "design_preview_notes_path")) else "failed",
                "detail": "design_consultation_agent.py emits DESIGN.md plus preview artifacts for downstream implementation.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "design_consultation_agent.py")],
            },
        }
    if mode_id == "review":
        return {
            "Review report exists": {
                "status": "passed" if all(token in review_source for token in ("review_report.md", "## Scope Check", "## Checklist Findings", "## Decision Ceremony")) else "failed",
                "detail": "review_agent.py renders a structured diff review report with scope, checklist, and staged decision sections.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "review_agent.py")],
            },
            "Structured blocking, important, and nice-to-have findings exist with dispositions when review fails": {
                "status": "passed" if all(token in review_source for token in ('"blocking"', '"important"', '"nice_to_have"', '"disposition"', "review_findings.json", "risk_register.json", "review_decision_state.json", '"ASK"', '"AUTO-FIX"')) else "failed",
                "detail": "review_agent.py persists structured findings, risk-register output, and staged review-decision metadata.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "review_agent.py")],
            },
        }
    if mode_id == "design-review":
        return {
            "Browser evidence includes before and after captures": {
                "status": "passed" if all(token in qa_design_review_source for token in ("before_after_report.md", "## Before Screenshots", "## After Screenshots", "design_evidence_bundle.json")) else "failed",
                "detail": "qa_design_review_agent.py persists before/after capture evidence and a design evidence bundle.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "qa_design_review_agent.py")],
            },
            "Design review route is mandatory for UI stories that request it": {
                "status": "passed" if all(token in qa_design_review_source for token in ("route_findings.json", "## Route-Level Findings", "add_executed_mode(state, \"design-review\")")) else "failed",
                "detail": "qa_design_review_agent.py emits route-level findings and records design-review execution.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "qa_design_review_agent.py")],
            },
        }
    if mode_id == "qa":
        return {
            "Can run in fixer-enabled mode": {
                "status": "passed" if all(token in browse_source + runtime_qa_source for token in ("return \"fixer\"", "auto_upgrade_to_qa", "effective_qa_mode")) and all(token in test_source for token in ("run_commands(typecheck_commands)", "run_commands(test_commands)", "Typecheck:", "Test:")) else "failed",
                "detail": "tester plus browser/runtime QA can escalate from report-only findings into a fixer-enabled loop.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "test_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "runtime_qa_agent.py"),
                ],
            },
            "Shares browser runtime evidence with browse and design-review": {
                "status": "passed" if all(token in browse_source for token in ("BrowserSessionManager", "run_browser_capture", "write_shared_qa_artifacts")) and "write_shared_qa_artifacts" in qa_contract_source else "failed",
                "detail": "QA persists shared evidence and structured findings through the common browser runtime and QA contract.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "qa_contract.py"),
                ],
            },
            "QA summary includes severity counts, regression recommendations, and verification rerun plan": {
                "status": "passed" if all(token in qa_contract_source for token in ("severity_counts", "regression_recommendations", "verification_rerun_plan", "input_sources", "qa_rerun_plan.json", "disposition_counts")) else "failed",
                "detail": "qa_contract.py writes severity/category/disposition counts, input sources, regression recommendations, and rerun guidance into shared QA artifacts.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "qa_contract.py")],
            },
        }
    if mode_id == "qa-only":
        return {
            "Runs in report-only mode without fixer": {
                "status": "passed" if all(token in browse_source + runtime_qa_source for token in ("report_only", "if blocking_findings and not report_only")) else "failed",
                "detail": "QA agents respect report-only mode and avoid creating fixer issues when the mode is qa-only.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "runtime_qa_agent.py"),
                ],
            },
            "Shares browser runtime evidence with browse and design-review": {
                "status": "passed" if all(token in browse_source for token in ("BrowserSessionManager", "run_browser_capture", "write_shared_qa_artifacts")) and "write_shared_qa_artifacts" in qa_contract_source else "failed",
                "detail": "qa-only keeps the same shared QA evidence contract while staying report-only.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "browser_qa_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "qa_contract.py"),
                ],
            },
            "QA summary includes severity counts, regression recommendations, and verification rerun plan": {
                "status": "passed" if all(token in qa_contract_source for token in ("severity_counts", "regression_recommendations", "verification_rerun_plan", "input_sources", "qa_rerun_plan.json", "disposition_counts")) else "failed",
                "detail": "qa_contract.py writes severity/category/disposition counts, input sources, regression recommendations, and rerun guidance into shared QA artifacts.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "qa_contract.py")],
            },
        }
    if mode_id == "setup-browser-cookies":
        return {
            "Cookie source is normalized into storage state": {
                "status": "passed" if all(token in cookie_source for token in ("_seed_storage_state", "session_seed.json", "browser_storage_state_path")) else "failed",
                "detail": "setup_browser_cookies_agent.py normalizes cookie input into storage state and saves the seed artifact.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "setup_browser_cookies_agent.py")],
            },
            "Shared browser runtime reuses imported cookies in downstream browse and QA passes": {
                "status": "passed" if all(token in cookie_source for token in ("execute_browser_commands", "cookie-import-browser", "Continue into browse or browser QA")) else "failed",
                "detail": "setup_browser_cookies_agent.py imports cookies into the shared browser runtime and hands off to browse/QA.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "setup_browser_cookies_agent.py")],
            },
        }
    if mode_id == "ship":
        return {
            "Ship report includes release scope, validation, diff discipline, and blockers": {
                "status": "passed" if all(token in ship_source for token in ("## Pre-Landing Review", "## Validation", "## Blockers", "## Closeout Checklist", "closeout_checklist.json")) else "failed",
                "detail": "ship_agent.py renders closeout sections and writes a structured closeout checklist.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "ship_agent.py")],
            },
            "Sprint closeout routes into document-release": {
                "status": "passed" if "document_release" in _read_text(root_dir / "config" / "workflows" / "software_engineering.yaml") else "failed",
                "detail": "workflow manifest routes ship into document-release.",
                "evidence": [str(root_dir / "config" / "workflows" / "software_engineering.yaml")],
            },
        }
    if mode_id == "document-release":
        return {
            "Document release report includes checklist and stale sections": {
                "status": "passed" if all(token in document_release_source for token in ("## Documentation Checklist", "## Stale Sections Or Required Updates", "## Sync Actions", "stale_sections.json")) else "failed",
                "detail": "document_release_agent.py renders checklist, stale sections, and sync actions with separate artifacts.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "document_release_agent.py")],
            },
            "Doc targets are carried into retro": {
                "status": "passed" if all(token in document_release_source + retro_source for token in ("doc_targets", "document_release_targets", "document_release_stale_sections", "closeout_linkage")) else "failed",
                "detail": "document-release and retro both carry doc target context.",
                "evidence": [
                    str(root_dir / "src" / "agentsystem" / "agents" / "document_release_agent.py"),
                    str(root_dir / "src" / "agentsystem" / "agents" / "retro_agent.py"),
                ],
            },
        }
    if mode_id == "retro":
        return {
            "Retro report includes metrics, wins, pain points, and next actions": {
                "status": "passed" if all(token in retro_source for token in ("## Metrics", "## Wins", "## Pain Points", "## Closeout Linkage", "## Next Actions")) else "failed",
                "detail": "retro_agent.py renders the expected closeout sections.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "retro_agent.py")],
            },
            "Retro snapshot artifact exists": {
                "status": "passed" if all(token in retro_source for token in ("retro_snapshot.json", "closeout_linkage.json")) else "failed",
                "detail": "retro_agent.py writes a retro snapshot artifact and a closeout-linkage artifact.",
                "evidence": [str(root_dir / "src" / "agentsystem" / "agents" / "retro_agent.py")],
            },
        }
    return {}


def _build_summary(agents: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    dogfood_eligible_count = 0
    for agent in agents:
        status = str(agent.get("parity_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if agent.get("dogfood_eligible"):
            dogfood_eligible_count += 1
    return {
        "agent_count": len(agents),
        "status_counts": status_counts,
        "full_parity_count": status_counts.get("full_parity", 0),
        "dogfood_eligible_count": dogfood_eligible_count,
        "formal_evidence_count": sum(1 for agent in agents if agent.get("formal_evidence_complete")),
    }


def _build_sprint_dogfood_target(
    sprint_dir: Path,
    agents: list[dict[str, Any]],
    *,
    root_dir: Path,
    project: str | None,
) -> dict[str, Any]:
    parity_by_mode = {str(item.get("mode_id") or ""): item for item in agents}
    project_root = (root_dir.parent / str(project).strip()).resolve() if project else None
    story_status_index = _load_story_status_index(project_root)
    acceptance_review_index = _load_acceptance_review_index(project_root)
    story_summaries: list[dict[str, Any]] = []
    required_union: list[str] = []
    for story_file in sorted(sprint_dir.rglob("S*.yaml")):
        payload = _load_yaml(story_file)
        if not isinstance(payload, dict):
            continue
        task = apply_agent_activation_policy(payload)
        required_modes = [str(item).strip() for item in task.get("required_modes") or [] if str(item).strip()]
        for mode in required_modes:
            if mode not in required_union:
                required_union.append(mode)
        story_id = str(payload.get("story_id") or payload.get("task_id") or "").strip()
        story_status = story_status_index.get(story_id) or {}
        acceptance_review = acceptance_review_index.get(story_id) or {}
        implemented = str(story_status.get("status") or "").strip().lower() == "done"
        verified = bool(story_status.get("verified_at"))
        accepted = str(acceptance_review.get("verdict") or "").strip().lower() == "approved"
        agentized = bool(required_modes)
        story_summaries.append(
            {
                "story_id": story_id,
                "required_modes": required_modes,
                "effective_qa_mode": task.get("effective_qa_mode"),
                "implemented": implemented,
                "verified": verified,
                "agentized": agentized,
                "accepted": accepted,
                "delivery_report": story_status.get("delivery_report"),
                "acceptance_run_id": acceptance_review.get("run_id"),
            }
        )
    blockers = [
        {
            "mode_id": mode,
            "parity_status": parity_by_mode.get(mode, {}).get("parity_status"),
            "dogfood_eligible": bool(parity_by_mode.get(mode, {}).get("dogfood_eligible")),
            "reason": "Required mode is not dogfood_eligible yet."
            if not parity_by_mode.get(mode, {}).get("dogfood_eligible")
            else "",
        }
        for mode in required_union
        if not parity_by_mode.get(mode, {}).get("dogfood_eligible")
    ]
    completed_story_count = sum(1 for item in story_summaries if item.get("implemented"))
    accepted_story_count = sum(1 for item in story_summaries if item.get("accepted"))
    dogfood_completed = bool(
        story_summaries
        and not blockers
        and all(item.get("implemented") and item.get("verified") and item.get("accepted") for item in story_summaries)
    )
    return {
        "project": project,
        "sprint_dir": str(sprint_dir),
        "story_count": len(story_summaries),
        "completed_story_count": completed_story_count,
        "accepted_story_count": accepted_story_count,
        "stories": story_summaries,
        "required_modes": required_union,
        "dogfood_eligible_modes": [mode for mode in required_union if parity_by_mode.get(mode, {}).get("dogfood_eligible")],
        "formal_dogfood_ready": not blockers,
        "dogfood_completed": dogfood_completed,
        "formal_dogfood_blockers": blockers,
    }


def _render_acceptance_checklist(audit: dict[str, Any]) -> str:
    lines = [
        "# gstack Parity Acceptance Checklist",
        "",
        f"- Generated at: {audit.get('generated_at')}",
        f"- Upstream commit: {(audit.get('upstream') or {}).get('commit')}",
        "",
    ]
    for agent in audit.get("agents") or []:
        lines.extend(
            [
                f"## {agent['mode_id']}",
                f"- Parity status: {agent['parity_status']}",
                f"- Declared parity status: {agent.get('declared_parity_status')}",
                f"- Dogfood eligible: {'yes' if agent.get('dogfood_eligible') else 'no'}",
                f"- Formal evidence complete: {'yes' if agent.get('formal_evidence_complete') else 'no'}",
                f"- Full parity claimable: {'yes' if agent['full_parity_claimable'] else 'no'}",
                "",
                "### Structural Checks",
            ]
        )
        lines.extend(f"- [{check['status']}] {check['name']}: {check['detail']}" for check in agent.get("checks") or [])
        lines.extend(["", "### Acceptance Gates"])
        lines.extend(
            f"- [{item['status']}] {item['gate']}: {item['detail']}"
            for item in agent.get("acceptance_checklist") or []
        )
        lines.extend(["", "### Full Parity Upgrade Blockers"])
        blockers = agent.get("full_parity_upgrade_blockers") or []
        lines.extend(f"- {item}" for item in blockers)
        if not blockers:
            lines.append("- None.")
        lines.extend(["", "### Formal Evidence"])
        evidence_entries = agent.get("formal_evidence_entries") or []
        lines.extend(
            f"- [{item.get('status')}] {item.get('evidence_type')}: {item.get('detail') or 'No detail.'}"
            for item in evidence_entries
        )
        if not evidence_entries:
            lines.append("- None.")
        lines.append("")
    dogfood = audit.get("dogfood_target") or {}
    if dogfood:
        lines.extend(
            [
                "## Dogfood Target",
                f"- Sprint dir: {dogfood.get('sprint_dir')}",
                f"- Story count: {dogfood.get('story_count')}",
                f"- Completed stories: {dogfood.get('completed_story_count')}",
                f"- Accepted stories: {dogfood.get('accepted_story_count')}",
                f"- Formal dogfood ready: {'yes' if dogfood.get('formal_dogfood_ready') else 'no'}",
                f"- Dogfood completed: {'yes' if dogfood.get('dogfood_completed') else 'no'}",
                "",
                "### Blockers",
            ]
        )
        blockers = dogfood.get("formal_dogfood_blockers") or []
        lines.extend(
            f"- {item['mode_id']}: {item['parity_status']} | {item['reason']}"
            for item in blockers
        )
        if not blockers:
            lines.append("- None.")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _is_dogfood_eligible(
    parity_status: str,
    checks: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> bool:
    if parity_status not in {"workflow_wired", "partial_runtime", "full_parity"}:
        return False
    if any(str(item.get("status") or "") != "passed" for item in checks):
        return False
    if any(str(item.get("status") or "") != "passed" for item in acceptance):
        return False
    return True


def _build_full_parity_upgrade_blockers(
    *,
    parity_status: str,
    checks: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    missing_capabilities: list[str],
    dogfood_eligible: bool,
    requires_dogfood: bool,
    dogfood_completed: bool,
    formal_evidence_complete: bool,
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(
        f"Structural check failed: {item.get('name')}."
        for item in checks
        if str(item.get("status") or "") != "passed"
    )
    blockers.extend(
        f"Acceptance gate not passed: {item.get('gate')}."
        for item in acceptance
        if str(item.get("status") or "") != "passed"
    )
    blockers.extend(str(item).strip() for item in missing_capabilities if str(item).strip())
    if parity_status == "template_only":
        blockers.append("Mode is still template_only.")
    if not dogfood_eligible:
        blockers.append("Mode is not dogfood_eligible yet.")
    elif requires_dogfood and not dogfood_completed:
        blockers.append("Required dogfood evidence is not complete yet.")
    if not formal_evidence_complete:
        blockers.append("Formal E2E evidence has not promoted this mode to full_parity yet.")
    return blockers


def _load_story_status_index(project_root: Path | None) -> dict[str, dict[str, Any]]:
    if project_root is None:
        return {}
    path = project_root / "tasks" / "story_status_registry.json"
    payload = _load_json(path)
    items = payload.get("stories") if isinstance(payload, dict) else None
    index: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if isinstance(item, dict):
            story_id = str(item.get("story_id") or "").strip()
            if story_id:
                index[story_id] = item
    return index


def _load_acceptance_review_index(project_root: Path | None) -> dict[str, dict[str, Any]]:
    if project_root is None:
        return {}
    path = project_root / "tasks" / "story_acceptance_reviews.json"
    payload = _load_json(path)
    items = payload.get("reviews") if isinstance(payload, dict) else None
    index: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        story_id = str(item.get("story_id") or "").strip()
        if not story_id:
            continue
        existing = index.get(story_id)
        if existing is None or str(item.get("checked_at") or item.get("updated_at") or "") >= str(existing.get("checked_at") or existing.get("updated_at") or ""):
            index[story_id] = item
    return index


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _mode_index(items: list[Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict):
            mode_id = str(item.get("mode_id") or "").strip()
            if mode_id:
                index[mode_id] = item
    return index


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""
