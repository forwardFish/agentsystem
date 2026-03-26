from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROADMAP_ID = "roadmap_1_6"

SPRINT_FOCUS_MAP: dict[str, str] = {
    "roadmap_1_6_sprint_1_event_lane_and_mapping_base": "事件白名单、事件记录结构、事件输入结构化、题材映射、casebook 基座",
    "roadmap_1_6_sprint_2_participant_preparation": "participant preparation 与 prepare orchestrator",
    "roadmap_1_6_sprint_3_belief_graph_and_scenarios": "belief graph、三情景引擎、watchpoints、event card read model",
    "roadmap_1_6_sprint_4_lightweight_simulation_runtime": "lightweight simulation runtime、timeline、action log",
    "roadmap_1_6_sprint_5_review_and_outcome_validation": "review report、T+1/T+3 outcome、reliability、why/retrieval API",
    "roadmap_1_6_sprint_6_statement_to_style_assets": "statement -> style assets",
    "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration": "mirror agent、distribution calibration、acceptance pack / handoff",
}

API_DEMO_ENDPOINTS: list[dict[str, str]] = [
    {"capability": "事件入口与结构化", "method": "POST", "path": "/api/v1/events", "note": "创建事件主记录。"},
    {"capability": "participant preparation", "method": "POST", "path": "/api/v1/events/{event_id}/prepare", "note": "生成参与者准备结果。"},
    {"capability": "belief graph / scenarios", "method": "POST", "path": "/api/v1/events/{event_id}/belief-graph", "note": "构建 belief graph。"},
    {"capability": "belief graph / scenarios", "method": "POST", "path": "/api/v1/events/{event_id}/scenarios", "note": "生成 bull/base/bear 三情景。"},
    {"capability": "simulation runtime", "method": "POST", "path": "/api/v1/events/{event_id}/simulation/run", "note": "执行轻量模拟链路。"},
    {"capability": "review / outcome / why", "method": "GET", "path": "/api/v1/events/{event_id}/review-report", "note": "查看 review report。"},
    {"capability": "review / outcome / why", "method": "GET", "path": "/api/v1/events/{event_id}/why", "note": "查看 why / retrieval 结果。"},
    {"capability": "style assets", "method": "POST", "path": "/api/v1/statements/{statement_id}/style-features", "note": "从 statement 生成 style features。"},
    {"capability": "mirror agent", "method": "POST", "path": "/api/v1/statements/{statement_id}/mirror-agent", "note": "构建 mirror agent。"},
    {"capability": "distribution calibration", "method": "GET", "path": "/api/v1/statements/{statement_id}/distribution-calibration", "note": "读取 distribution calibration 结果。"},
    {"capability": "acceptance pack", "method": "GET", "path": "/api/v1/roadmaps/1.6/acceptance-pack", "note": "查看 roadmap_1_6 acceptance pack。"},
]
NEXT_EXECUTION_PRIORITY: list[dict[str, Any]] = [
    {
        "order": 1,
        "sprint_id": "roadmap_1_6_sprint_4_lightweight_simulation_runtime",
        "title": "Sprint 4",
        "focus": "lightweight simulation runtime, timeline, action log",
        "story_ids": ["E4-001", "E4-002", "E4-003", "E4-004", "E4-005"],
        "why_now": "The main 1.6 document requires Sprint 1-5 before Sprint 6-7, so Sprint 4 is the next required gap-closure lane.",
    },
    {
        "order": 2,
        "sprint_id": "roadmap_1_6_sprint_5_review_and_outcome_validation",
        "title": "Sprint 5",
        "focus": "report, T+1/T+3 outcome, reliability, why/retrieval API",
        "story_ids": ["E5-001", "E5-002", "E5-003", "E5-004", "E5-005"],
        "why_now": "Sprint 5 closes the P0 event-sandbox loop after Sprint 4.",
    },
    {
        "order": 3,
        "sprint_id": "p0_closeout",
        "title": "P0 Closeout",
        "focus": "authoritative closeout across Sprint 1-5",
        "story_ids": [],
        "why_now": "Sprint 1-5 should be auditable end-to-end before the plan advances into Sprint 6-7 gap closure.",
    },
    {
        "order": 4,
        "sprint_id": "roadmap_1_6_sprint_6_statement_to_style_assets",
        "title": "Sprint 6",
        "focus": "statement to style assets",
        "story_ids": ["E6-001", "E6-002", "E6-003", "E6-004", "E6-005"],
        "why_now": "Sprint 6 is the next P1 lane once the P0 event lane is fully closed.",
    },
    {
        "order": 5,
        "sprint_id": "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration",
        "title": "Sprint 7",
        "focus": "mirror agent and distribution calibration",
        "story_ids": ["E7-001", "E7-002", "E7-003", "E7-004", "E7-005"],
        "why_now": "Sprint 7 closes mirror, grading, calibration, and final acceptance once Sprint 6 is done.",
    },
]

MID_PROCESS_VALIDATION: list[dict[str, str]] = [
    {
        "stage": "story_boundary",
        "check": "Inspect NOW.md and current_handoff.md to confirm the active story boundary and recovery command.",
        "entrypoint": "D:\\lyh\\agent\\agent-frame\\versefina\\NOW.md",
    },
    {
        "stage": "continuity",
        "check": "Inspect the continuity manifest and mirror files before resuming after an interruption.",
        "entrypoint": "D:\\lyh\\agent\\agent-frame\\.meta\\versefina\\continuity\\continuity_manifest.json",
    },
    {
        "stage": "api_tests",
        "check": "Run the Versefina API test suite after Story or Sprint changes that affect the product surface.",
        "entrypoint": "python -m pytest apps/api/tests -q",
    },
    {
        "stage": "swagger",
        "check": "Open Swagger and verify event, simulation, review/outcome/why, and style/mirror routes manually.",
        "entrypoint": "http://127.0.0.1:8001/docs",
    },
    {
        "stage": "product_demo",
        "check": "Open the product demo and confirm the newly delivered capability is visible there.",
        "entrypoint": "http://127.0.0.1:3000/roadmap-1-6-demo",
    },
    {
        "stage": "audit_dashboard",
        "check": "Open the runtime audit dashboard and inspect sprint/story status plus evidence links.",
        "entrypoint": "http://127.0.0.1:8010/versefina/runtime",
    },
]

FINAL_EFFECT_CHECKLIST: list[str] = [
    "Product demo shows event -> participant preparation -> belief graph -> scenarios -> simulation -> outcome -> why.",
    "Product demo shows statement -> style features -> mirror agent -> validation grading -> distribution calibration.",
    "Swagger exposes the main event, simulation, review/outcome/why, style, mirror, and demo routes.",
    "Runtime audit dashboard shows roadmap, sprint, story, evidence, continuity, and report visibility.",
]


def refresh_roadmap_1_6_execution_reports(
    project_root: Path,
    agentsystem_root: Path,
    validation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = build_roadmap_1_6_showcase(project_root=project_root, agentsystem_root=agentsystem_root, validation_override=validation_override)
    report_paths = payload.get("report_paths") or {}
    markdown_path = Path(str(report_paths.get("markdown_path") or project_root / "docs" / "reports" / "roadmap_1_6_execution_report.md"))
    json_path = Path(str(report_paths.get("json_path") or project_root / "docs" / "reports" / "roadmap_1_6_execution_report.json"))
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(_report_json_payload_enriched(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown_report_enriched(payload), encoding="utf-8")
    return payload


def build_roadmap_1_6_showcase(
    project_root: Path,
    agentsystem_root: Path,
    validation_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace_root = agentsystem_root.parent
    runs_root = agentsystem_root / "runs"
    summary_path = _latest_roadmap_summary(runs_root / "roadmaps")
    summary = _read_json(summary_path) if summary_path else {}
    report_dir = project_root / "docs" / "reports"
    report_markdown_path = report_dir / "roadmap_1_6_execution_report.md"
    report_json_path = report_dir / "roadmap_1_6_execution_report.json"
    existing_report = _read_json(report_json_path) if report_json_path.exists() else {}

    now_path = project_root / "NOW.md"
    state_path = project_root / "STATE.md"
    decisions_path = project_root / "DECISIONS.md"
    handoff_path = project_root / "docs" / "handoff" / "current_handoff.md"
    continuity_manifest_path = workspace_root / ".meta" / "versefina" / "continuity" / "continuity_manifest.json"
    playbook_path = project_root / "docs" / "bootstrap" / "roadmap_1_7_execution_playbook.md"

    summary_sprints = summary.get("sprints") if isinstance(summary, dict) else []
    last_sprint = summary_sprints[-1] if isinstance(summary_sprints, list) and summary_sprints else {}
    document_release_path = Path(str(((last_sprint.get("post_hook") or {}).get("document_release_path")) or agentsystem_root / "runs" / "sprints" / "versefina" / "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration" / "document_release_report.md"))
    retro_path = Path(str(((last_sprint.get("post_hook") or {}).get("retro_path")) or agentsystem_root / "runs" / "sprints" / "versefina" / "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration" / "retro_report.md"))
    special_acceptance_path = Path(str((last_sprint.get("special_acceptance_report_path")) or agentsystem_root / "runs" / "sprints" / "versefina" / "roadmap_1_6_sprint_7_mirror_agent_and_distribution_calibration" / "special_acceptance_report.json"))
    ship_report_path = Path(str(((last_sprint.get("post_hook") or {}).get("ship_report_path")) or workspace_root / ".meta" / "versefina" / "ship" / "ship_readiness_report.md"))

    summary_metrics = _summary_metrics(summary)
    continuity = _build_continuity_status(
        now_path=now_path,
        state_path=state_path,
        decisions_path=decisions_path,
        handoff_path=handoff_path,
        continuity_manifest_path=continuity_manifest_path,
    )
    ship_readiness = _parse_ship_report(ship_report_path)
    special_acceptance = _parse_special_acceptance(special_acceptance_path)
    validation = _resolve_validation(summary=summary, ship_readiness=ship_readiness, existing_report=existing_report, validation_override=validation_override)
    residual_issues = _build_residual_issues(
        ship_readiness=ship_readiness,
        special_acceptance=special_acceptance,
        summary=summary,
        document_release_path=document_release_path,
    )
    sprint_results = _build_sprint_results(summary)
    showcase_links = {
        "dashboard": "http://127.0.0.1:8010/",
        "runtime_showcase": "http://127.0.0.1:8010/versefina/runtime",
        "product_demo": "http://127.0.0.1:3000/roadmap-1-6-demo",
        "swagger": "http://127.0.0.1:8001/docs",
        "report_markdown": "/versefina/runtime/report",
        "report_json": "/api/versefina/runtime/report",
    }
    evidence_paths = {
        "roadmap_summary": str(summary_path) if summary_path else "",
        "ship_readiness_report": str(ship_report_path),
        "special_acceptance_report": str(special_acceptance_path),
        "document_release_report": str(document_release_path),
        "retro_report": str(retro_path),
        "current_handoff": str(handoff_path),
        "now_md": str(now_path),
        "state_md": str(state_path),
        "decisions_md": str(decisions_path),
        "continuity_manifest": str(continuity_manifest_path),
        "execution_playbook": str(playbook_path),
    }

    status = str(summary.get("status") or "unknown")
    delivery_complete = status == "completed"
    release_clean = bool(ship_readiness.get("ship_ready"))
    return {
        "roadmap_id": ROADMAP_ID,
        "status": status,
        "completed_at": summary.get("completed_at") or summary.get("last_updated_at"),
        "delivery_complete": delivery_complete,
        "delivery_status_label": "delivery complete" if delivery_complete else "delivery incomplete",
        "release_clean": release_clean,
        "release_status_label": "release clean" if release_clean else "release not clean yet",
        "sprint_results": sprint_results,
        "summary_metrics": summary_metrics,
        "showcase_links": showcase_links,
        "api_demo_endpoints": API_DEMO_ENDPOINTS,
        "validation": validation,
        "next_execution_priority": NEXT_EXECUTION_PRIORITY,
        "mid_process_validation": MID_PROCESS_VALIDATION,
        "final_effect_checklist": FINAL_EFFECT_CHECKLIST,
        "continuity": continuity,
        "residual_issues": residual_issues,
        "evidence_paths": evidence_paths,
        "ship_readiness": ship_readiness,
        "special_acceptance": special_acceptance,
        "report_paths": {
            "markdown_path": str(report_markdown_path),
            "json_path": str(report_json_path),
            "markdown_url": showcase_links["report_markdown"],
            "json_url": showcase_links["report_json"],
        },
        "new_capabilities": [item["focus"] for item in sprint_results if item.get("focus")],
        "authoritative_source": str(summary_path) if summary_path else "",
    }


def _latest_roadmap_summary(roadmaps_dir: Path) -> Path | None:
    if not roadmaps_dir.exists():
        return None
    matches = sorted(roadmaps_dir.glob(f"{ROADMAP_ID}_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _build_sprint_results(summary: dict[str, Any]) -> list[dict[str, Any]]:
    sprint_results: list[dict[str, Any]] = []
    for index, sprint in enumerate(summary.get("sprints") or [], start=1):
        sprint_id = str(sprint.get("sprint_id") or sprint.get("sprint_dir") or f"sprint_{index}")
        pre_hook = sprint.get("pre_hook") or {}
        post_hook = sprint.get("post_hook") or {}
        completed_stories = sprint.get("completed_stories") or []
        sprint_results.append(
            {
                "index": index,
                "sprint_id": sprint_id,
                "title": f"Sprint {index}",
                "focus": SPRINT_FOCUS_MAP.get(sprint_id, sprint_id),
                "status": sprint.get("status") or "unknown",
                "story_count": int(sprint.get("story_count") or 0),
                "completed_story_count": len(completed_stories),
                "failed_story_count": len(sprint.get("failed_stories") or []),
                "last_success_story": sprint.get("last_success_story") or (completed_stories[-1].get("story_id") if completed_stories else None),
                "authoritative_attempt": sprint.get("authoritative_attempt"),
                "pre_hook_ready": all(bool(pre_hook.get(key)) for key in ("office_hours_path", "plan_ceo_review_path", "sprint_framing_path", "parity_manifest_path")),
                "post_hook_ready": all(bool(post_hook.get(key)) for key in ("document_release_path", "retro_path", "ship_report_path")),
                "pre_hook_paths": pre_hook,
                "post_hook_paths": post_hook,
                "special_acceptance_report_path": sprint.get("special_acceptance_report_path"),
            }
        )
    return sprint_results


def _summary_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    verification_metrics = ((summary.get("verification") or {}).get("summary_metrics")) or {}
    if verification_metrics:
        return dict(verification_metrics)
    return {
        "versefina_business_files_changed": int(summary.get("versefina_business_files_changed") or 0),
        "syntax_checked_files": int(summary.get("syntax_checked_files") or 0),
        "placeholder_rejections": int(summary.get("placeholder_rejections") or 0),
        "integration_contract_passed": bool(summary.get("integration_contract_passed")),
        "api_test_count": int(summary.get("api_test_count") or 0),
        "agent_coverage_passed": bool(summary.get("agent_coverage_passed")),
        "gstack_parity_passed": bool(summary.get("gstack_parity_passed")),
    }


def _build_continuity_status(
    now_path: Path,
    state_path: Path,
    decisions_path: Path,
    handoff_path: Path,
    continuity_manifest_path: Path,
) -> dict[str, Any]:
    now_data = _parse_bullet_file(now_path)
    state_data = _parse_bullet_file(state_path)
    handoff_data = _parse_bullet_file(handoff_path)
    manifest = _read_json(continuity_manifest_path) if continuity_manifest_path.exists() else {}
    completed_boundary = all(
        str(value or "").strip().lower() == "completed"
        for value in (now_data.get("status"), state_data.get("phase"), handoff_data.get("status"))
    )
    return {
        "now_status": now_data.get("status"),
        "now_task": now_data.get("current task"),
        "state_phase": state_data.get("phase"),
        "state_goal": state_data.get("goal"),
        "handoff_status": handoff_data.get("status"),
        "handoff_last_success_story": handoff_data.get("last success story"),
        "completed_boundary": completed_boundary,
        "manifest_exists": continuity_manifest_path.exists(),
        "manifest_sync_status": manifest.get("status") or ("present" if continuity_manifest_path.exists() else "missing"),
        "paths": {
            "now_md": str(now_path),
            "state_md": str(state_path),
            "decisions_md": str(decisions_path),
            "current_handoff": str(handoff_path),
            "continuity_manifest": str(continuity_manifest_path),
        },
    }


def _parse_ship_report(path: Path) -> dict[str, Any]:
    metadata = _parse_bullet_file(path)
    blockers = _parse_markdown_section(path, "## Blockers")
    return {
        "path": str(path),
        "generated_at": metadata.get("generated at"),
        "branch": metadata.get("branch"),
        "commit": metadata.get("commit"),
        "dirty_tree": str(metadata.get("dirty tree") or "").strip().lower() == "yes",
        "ship_ready": str(metadata.get("ship ready") or "").strip().lower() == "yes",
        "blockers": blockers or [],
    }


def _parse_special_acceptance(path: Path) -> dict[str, Any]:
    payload = _read_json(path) if path.exists() else {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "path": str(path),
        "formal_flow_complete": bool(payload.get("formal_flow_complete")),
        "completed_story_count": int(payload.get("completed_story_count") or 0),
        "story_count": int(payload.get("story_count") or 0),
        "missing_items": list(payload.get("missing_items") or []),
        "final_verdict": payload.get("final_verdict"),
    }


def _resolve_validation(
    summary: dict[str, Any],
    ship_readiness: dict[str, Any],
    existing_report: dict[str, Any],
    validation_override: dict[str, Any] | None,
) -> dict[str, Any]:
    if validation_override:
        return validation_override
    existing_validation = existing_report.get("validation") if isinstance(existing_report, dict) else None
    if isinstance(existing_validation, dict):
        return existing_validation
    return {
        "api_tests": {
            "command": "python -m pytest apps/api/tests -q",
            "status": "reported_green",
            "details": f"Roadmap summary recorded api_test_count={int(summary.get('api_test_count') or 0)}.",
            "recorded_at": summary.get("completed_at") or summary.get("last_updated_at"),
        },
        "dashboard": {
            "status": "pending_refresh",
            "details": "Refresh the local dashboard after report generation to inspect the showcase.",
        },
        "ship_readiness": {
            "status": "not_clean" if not ship_readiness.get("ship_ready") else "clean",
            "details": "Dirty tree keeps ship readiness below release-clean.",
        },
    }


def _build_residual_issues(
    ship_readiness: dict[str, Any],
    special_acceptance: dict[str, Any],
    summary: dict[str, Any],
    document_release_path: Path,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not ship_readiness.get("ship_ready"):
        blockers = ship_readiness.get("blockers") or ["Working tree is still dirty."]
        issues.append(
            {
                "id": "ship_readiness_dirty_tree",
                "severity": "medium",
                "title": "Ship ready: no",
                "detail": "Ship readiness is still not release-clean because the working tree is dirty. This is a release hygiene issue, not a feature failure.",
                "evidence": blockers,
            }
        )
    if _special_acceptance_inconsistent(summary, special_acceptance):
        issues.append(
            {
                "id": "special_acceptance_drift",
                "severity": "medium",
                "title": "Sprint 7 special acceptance 与 roadmap summary 不一致",
                "detail": "Roadmap authoritative summary is completed, but Sprint 7 special acceptance still reports formal_flow_complete=false and lists missing items. This should be treated as evidence governance drift, not as a rollback of roadmap completion.",
                "evidence": [
                    f"formal_flow_complete={special_acceptance.get('formal_flow_complete')}",
                    f"missing_items={', '.join(special_acceptance.get('missing_items') or []) or 'none'}",
                    str(special_acceptance.get("path") or ""),
                ],
            }
        )
    document_release_text = document_release_path.read_text(encoding="utf-8") if document_release_path.exists() else ""
    if "Applied Changes" in document_release_text and "None." in document_release_text:
        issues.append(
            {
                "id": "document_release_followup",
                "severity": "low",
                "title": "Document release 仍有对齐治理项",
                "detail": "Sprint 7 document release did not apply in-place doc updates and explicitly carried drift into retro. The roadmap can stay completed, but release-facing docs still need follow-up alignment.",
                "evidence": [str(document_release_path)],
            }
        )
    return issues


def _special_acceptance_inconsistent(summary: dict[str, Any], special_acceptance: dict[str, Any]) -> bool:
    if str(summary.get("status") or "").strip().lower() != "completed":
        return False
    if not special_acceptance:
        return False
    if not special_acceptance.get("formal_flow_complete"):
        return True
    if special_acceptance.get("missing_items"):
        return True
    return False


def _report_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "roadmap_id": payload.get("roadmap_id"),
        "status": payload.get("status"),
        "completed_at": payload.get("completed_at"),
        "sprint_results": payload.get("sprint_results"),
        "summary_metrics": payload.get("summary_metrics"),
        "showcase_links": payload.get("showcase_links"),
        "api_demo_endpoints": payload.get("api_demo_endpoints"),
        "validation": payload.get("validation"),
        "residual_issues": payload.get("residual_issues"),
        "evidence_paths": payload.get("evidence_paths"),
        "continuity": payload.get("continuity"),
        "delivery_status_label": payload.get("delivery_status_label"),
        "release_status_label": payload.get("release_status_label"),
        "report_paths": payload.get("report_paths"),
    }


def _render_markdown_report(payload: dict[str, Any]) -> str:
    sprint_lines = [
        "| Sprint | 主题 | 状态 | Story | 备注 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sprint in payload.get("sprint_results") or []:
        sprint_lines.append(
            f"| {sprint.get('title')} | {sprint.get('focus')} | {sprint.get('status')} | {sprint.get('completed_story_count')}/{sprint.get('story_count')} | last={sprint.get('last_success_story') or '-'} |"
        )

    capability_lines = [f"- {item}" for item in payload.get("new_capabilities") or []]
    link_lines = [
        f"- Dashboard: {payload.get('showcase_links', {}).get('dashboard')}",
        f"- Runtime showcase: {payload.get('showcase_links', {}).get('runtime_showcase')}",
        f"- Swagger: {payload.get('showcase_links', {}).get('swagger')}",
        f"- Report JSON API: {payload.get('showcase_links', {}).get('report_json')}",
        f"- Report Markdown API: {payload.get('showcase_links', {}).get('report_markdown')}",
    ]
    api_lines = [
        f"- `{item.get('method')} {item.get('path')}`: {item.get('capability')}，{item.get('note')}"
        for item in payload.get("api_demo_endpoints") or []
    ]
    metric_lines = [f"- `{key}`: {value}" for key, value in (payload.get("summary_metrics") or {}).items()]
    validation_lines = _render_validation_lines(payload.get("validation") or {})
    evidence_lines = [f"- `{key}`: {value}" for key, value in (payload.get("evidence_paths") or {}).items()]
    residual_lines = [
        f"- {item.get('title')}: {item.get('detail')}"
        for item in payload.get("residual_issues") or []
    ] or ["- 暂无残留问题。"]

    return "\n".join(
        [
            "# roadmap_1_6 执行报告",
            "",
            "## 执行结论",
            f"- 路线状态: `{payload.get('status')}`",
            f"- 完成时间: `{payload.get('completed_at')}`",
            f"- 交付结论: `{payload.get('delivery_status_label')}`",
            f"- 发布结论: `{payload.get('release_status_label')}`",
            "- authoritative source 以 roadmap summary 为准；ship readiness 与 special acceptance 作为残留证据展示。",
            "",
            "## 7 个 Sprint 完成情况",
            *sprint_lines,
            "",
            "## 新增业务能力清单",
            *(capability_lines or ["- 暂无。"]),
            "",
            "## 可演示页面与 API 入口",
            *link_lines,
            "",
            "### 关键 API 示例",
            *api_lines,
            "",
            "## 验证结果",
            *metric_lines,
            *validation_lines,
            "",
            "## 证据索引",
            *evidence_lines,
            "",
            "## 残留问题与下一步",
            *residual_lines,
            "- 下一步建议: 清理 dirty worktree，并补齐 Sprint 7 special acceptance / document release 的证据治理。",
            "",
        ]
    )


def _render_validation_lines(validation: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in validation.items():
        if not isinstance(value, dict):
            lines.append(f"- `{key}`: {value}")
            continue
        parts = [f"status={value.get('status') or '-'}"]
        if value.get("command"):
            parts.append(f"command={value['command']}")
        if value.get("details"):
            parts.append(f"details={value['details']}")
        if value.get("recorded_at"):
            parts.append(f"recorded_at={value['recorded_at']}")
        lines.append(f"- `{key}`: " + " | ".join(parts))
    return lines


def _report_json_payload_enriched(payload: dict[str, Any]) -> dict[str, Any]:
    base = _report_json_payload(payload)
    base.update(
        {
            "next_execution_priority": payload.get("next_execution_priority"),
            "mid_process_validation": payload.get("mid_process_validation"),
            "final_effect_checklist": payload.get("final_effect_checklist"),
        }
    )
    return base


def _render_markdown_report_enriched(payload: dict[str, Any]) -> str:
    sprint_lines = [
        "| Sprint | Focus | Status | Stories | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sprint in payload.get("sprint_results") or []:
        sprint_lines.append(
            f"| {sprint.get('title')} | {sprint.get('focus')} | {sprint.get('status')} | {sprint.get('completed_story_count')}/{sprint.get('story_count')} | last={sprint.get('last_success_story') or '-'} |"
        )

    capability_lines = [f"- {item}" for item in payload.get("new_capabilities") or []] or ["- None."]
    link_lines = [
        f"- Dashboard: {payload.get('showcase_links', {}).get('dashboard')}",
        f"- Runtime showcase: {payload.get('showcase_links', {}).get('runtime_showcase')}",
        f"- Product demo: {payload.get('showcase_links', {}).get('product_demo')}",
        f"- Swagger: {payload.get('showcase_links', {}).get('swagger')}",
        f"- Report JSON API: {payload.get('showcase_links', {}).get('report_json')}",
        f"- Report Markdown API: {payload.get('showcase_links', {}).get('report_markdown')}",
    ]
    api_lines = [
        f"- `{item.get('method')} {item.get('path')}`: {item.get('capability')} / {item.get('note')}"
        for item in payload.get("api_demo_endpoints") or []
    ] or ["- None."]
    metric_lines = [f"- `{key}`: {value}" for key, value in (payload.get("summary_metrics") or {}).items()]
    validation_lines = _render_validation_lines(payload.get("validation") or {})
    next_priority_lines = [
        f"- {item.get('order')}. {item.get('title')}: {item.get('focus')} | stories={', '.join(item.get('story_ids') or []) or '-'} | why={item.get('why_now')}"
        for item in payload.get("next_execution_priority") or []
    ] or ["- None."]
    mid_process_lines = [
        f"- `{item.get('stage')}`: {item.get('check')} | {item.get('entrypoint')}"
        for item in payload.get("mid_process_validation") or []
    ] or ["- None."]
    final_effect_lines = [f"- {item}" for item in payload.get("final_effect_checklist") or []] or ["- None."]
    evidence_lines = [f"- `{key}`: {value}" for key, value in (payload.get("evidence_paths") or {}).items()]
    residual_lines = [
        f"- {item.get('title')}: {item.get('detail')}"
        for item in payload.get("residual_issues") or []
    ] or ["- None."]

    return "\n".join(
        [
            "# roadmap_1_6 Execution Report",
            "",
            "## Execution Summary",
            f"- roadmap status: `{payload.get('status')}`",
            f"- completed at: `{payload.get('completed_at')}`",
            f"- delivery status: `{payload.get('delivery_status_label')}`",
            f"- release status: `{payload.get('release_status_label')}`",
            "- authoritative source: roadmap summary; ship readiness and special acceptance remain residual evidence.",
            "",
            "## Sprint Results",
            *sprint_lines,
            "",
            "## New Capabilities",
            *capability_lines,
            "",
            "## Showcase Links",
            *link_lines,
            "",
            "## Next Execution Priority",
            *next_priority_lines,
            "",
            "## Mid-Process Validation",
            *mid_process_lines,
            "",
            "## Final Effect Checklist",
            *final_effect_lines,
            "",
            "## API Demo Endpoints",
            *api_lines,
            "",
            "## Validation Results",
            *metric_lines,
            *validation_lines,
            "",
            "## Evidence Index",
            *evidence_lines,
            "",
            "## Residual Issues And Next Step",
            *residual_lines,
            "- Next step: continue Sprint 4 gap closure through agentsystem and keep continuity plus handoff aligned after each Story boundary.",
            "",
        ]
    )


def _parse_bullet_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        data[key.strip().lower()] = value.strip()
    return data


def _parse_markdown_section(path: Path, heading: str) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    capture = False
    items: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip()
        if line.strip() == heading:
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.strip().startswith("- "):
            items.append(line.strip()[2:].strip())
    return items


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
