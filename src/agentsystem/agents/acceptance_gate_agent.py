from __future__ import annotations

import re
import uuid
from pathlib import Path

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


def acceptance_gate_node(state: DevState) -> DevState:
    _safe_print("[Acceptance Gate] Evaluating acceptance criteria")

    task_payload = state.get("task_payload") or {}
    acceptance_items = [str(item).strip() for item in task_payload.get("acceptance_criteria", []) if str(item).strip()]
    related_files = [str(item).strip() for item in task_payload.get("related_files", []) if str(item).strip()]
    repo_b_path = Path(state["repo_b_path"]).resolve()
    report_dir = repo_b_path.parent / ".meta" / repo_b_path.name / "acceptance"
    report_dir.mkdir(parents=True, exist_ok=True)

    changed_files = _collect_changed_files(state, repo_b_path)
    checklist_lines: list[str] = []
    blocking_issues: list[str] = []

    for criterion in acceptance_items:
        satisfied, detail = _evaluate_criterion(criterion, task_payload, related_files, changed_files, repo_b_path, state)
        checklist_lines.append(f"- {'[x]' if satisfied else '[ ]'} {criterion} - {detail}")
        if not satisfied:
            blocking_issues.append(f"Acceptance unmet: {criterion}")

    allowed_scope = _build_scope_allowlist(task_payload, repo_b_path)
    if allowed_scope and changed_files:
        allowed = {path.replace("\\", "/") for path in allowed_scope}
        unexpected = [path for path in changed_files if path.replace("\\", "/") not in allowed]
        if unexpected:
            blocking_issues.append(f"Changes exceed task scope: {', '.join(unexpected)}")

    if not state.get("review_passed"):
        blocking_issues.append("Reviewer did not pass the change set.")
    if not state.get("code_style_review_passed"):
        blocking_issues.append("Code style review did not pass the change set.")
    if not state.get("code_acceptance_passed"):
        blocking_issues.append("Code acceptance did not pass the change set.")

    report_lines = [
        "# Acceptance Gate Report",
        "",
        "## Checklist",
        *(checklist_lines or ["- No acceptance criteria defined."]),
        "",
        "## Scope Check",
        f"- Changed files: {', '.join(changed_files) if changed_files else 'None recorded'}",
        f"- Related files: {', '.join(related_files) if related_files else 'None recorded'}",
        "",
        "## Review Gates",
        f"- Code style review passed: {'yes' if state.get('code_style_review_passed') else 'no'}",
        f"- Reviewer passed: {'yes' if state.get('review_passed') else 'no'}",
        f"- Code acceptance passed: {'yes' if state.get('code_acceptance_passed') else 'no'}",
        "",
        "## Verdict",
        "- [x] Acceptance passed" if not blocking_issues else "- [ ] Acceptance failed",
    ]

    report = "\n".join(report_lines).strip() + "\n"
    (report_dir / "acceptance_report.md").write_text(report, encoding="utf-8")

    state["acceptance_report"] = report
    state["acceptance_passed"] = not blocking_issues
    state["acceptance_success"] = True
    state["acceptance_dir"] = str(report_dir)
    state["blocking_issues"] = blocking_issues
    state["current_step"] = "acceptance_done"

    issues: list[Issue] = []
    for item in blocking_issues:
        issue = Issue(
            issue_id=str(uuid.uuid4()),
            severity=IssueSeverity.BLOCKING,
            source_agent=AgentRole.ACCEPTANCE_GATE,
            target_agent=AgentRole.FIXER,
            title="Acceptance gate blocking issue",
            description=str(item),
            suggestion="Resolve the failed acceptance item or scope violation and return the story for validation.",
        )
        if not state.get("acceptance_passed"):
            add_issue(state, issue)
        issues.append(issue)

    add_handoff_packet(
        state,
        HandoffPacket(
            packet_id=str(uuid.uuid4()),
            from_agent=AgentRole.ACCEPTANCE_GATE,
            to_agent=AgentRole.DOC_WRITER if state.get("acceptance_passed") else AgentRole.FIXER,
            status=HandoffStatus.COMPLETED if state.get("acceptance_passed") else HandoffStatus.BLOCKED,
            what_i_did="Cross-checked acceptance criteria, task scope, code style review, reviewer status, and code acceptance status for the story.",
            what_i_produced=[
                Deliverable(
                    deliverable_id=str(uuid.uuid4()),
                    name="Acceptance Gate Report",
                    type="report",
                    path=str(report_dir / "acceptance_report.md"),
                    description="Final acceptance checklist and scope-verification report.",
                    created_by=AgentRole.ACCEPTANCE_GATE,
                )
            ],
            what_risks_i_found=[str(item) for item in blocking_issues],
            what_i_require_next="If accepted, generate the delivery report. If blocked, fix the outstanding acceptance issues before trying again.",
            issues=issues if not state.get("acceptance_passed") else [],
            trace_id=str(state.get("collaboration_trace_id") or ""),
        ),
    )

    for line in report.splitlines():
        if line.strip():
            _safe_print(f"[Acceptance Gate] {line}")

    return state


def route_after_acceptance(state: DevState) -> str:
    return "doc_writer" if state.get("acceptance_passed") else "fixer"


def _collect_changed_files(state: DevState, repo_b_path: Path | None = None) -> list[str]:
    changed: list[str] = []
    dev_results = state.get("dev_results") or {}
    for payload in dev_results.values():
        if not isinstance(payload, dict):
            continue
        for item in payload.get("updated_files", []):
            changed.append(_normalize_changed_path(str(item), repo_b_path))
    changed.extend(_normalize_changed_path(str(item), repo_b_path) for item in (state.get("staged_files") or []))
    unique: list[str] = []
    seen: set[str] = set()
    for item in changed:
        normalized = item.replace("\\", "/")
        if _is_ignored_changed_path(normalized):
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _normalize_changed_path(path: str, repo_b_path: Path | None = None) -> str:
    normalized = str(path).replace("\\", "/")
    if repo_b_path is not None:
        try:
            return Path(normalized).resolve().relative_to(repo_b_path.resolve()).as_posix()
        except Exception:
            pass
    scope_roots = (".agents/", "apps/", "docs/", "scripts/", "tasks/", "packages/", "config/", "agents/", "graphs/", "workflows/", "skills/", "tools/")
    for root in scope_roots:
        marker = f"/{root}"
        if marker in normalized:
            return root + normalized.split(marker, 1)[1]
        if normalized.startswith(root):
            return normalized
    if normalized.endswith("/README.md"):
        return "README.md"
    if "/.env" in normalized:
        return normalized.rsplit("/", 1)[-1]
    return normalized


def _is_ignored_changed_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("tasks/runtime/")
        or normalized.startswith("docs/handoff/")
        or "__pycache__/" in normalized
        or normalized.endswith(".pyc")
        or ".pytest_cache/" in normalized
    )


def _build_scope_allowlist(task_payload: dict[str, object], repo_b_path: Path) -> list[str]:
    allowed: list[str] = []
    for key in ("primary_files", "secondary_files", "related_files"):
        for raw_path in task_payload.get(key, []) or []:
            normalized = _normalize_changed_path(str(raw_path), repo_b_path)
            if normalized not in allowed:
                allowed.append(normalized)

    design_contract_path = str(task_payload.get("design_contract_path") or "").strip()
    if design_contract_path:
        normalized = _normalize_changed_path(design_contract_path, repo_b_path)
        if normalized not in allowed:
            allowed.append(normalized)

    if bool(task_payload.get("needs_design_consultation")) or str(task_payload.get("skill_mode") or "").strip() == "design-consultation":
        if "DESIGN.md" not in allowed:
            allowed.append("DESIGN.md")

    project_key = str(task_payload.get("project") or repo_b_path.name).strip().lower()
    story_id = str(task_payload.get("story_id") or "").strip()
    if project_key == "agenthire" and story_id == "S1-001" and "apps/api/src/db/models.py" in allowed:
        allowed.append("apps/api/src/infra/db/tables.py")
    return allowed


def _evaluate_criterion(
    criterion: str,
    task_payload: dict[str, object],
    related_files: list[str],
    changed_files: list[str],
    repo_b_path: Path,
    state: DevState,
) -> tuple[bool, str]:
    lowered = criterion.lower()
    story_id = str(task_payload.get("story_id", "")).strip()
    project_key = str(task_payload.get("project") or repo_b_path.name).strip().lower()

    if project_key == "versefina" and story_id == "S0-003":
        evidence = _evaluate_s0_003_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "versefina" and story_id == "S0-004":
        evidence = _evaluate_s0_004_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "versefina" and story_id == "S0-005":
        evidence = _evaluate_s0_005_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "versefina" and story_id == "S0-006":
        evidence = _evaluate_s0_006_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "versefina" and story_id == "S0-007":
        evidence = _evaluate_s0_007_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "versefina" and story_id == "S1-001":
        evidence = _evaluate_s1_001_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence
    if project_key == "agenthire" and story_id == "S1-001":
        evidence = _evaluate_agenthire_s1_001_criterion(criterion, repo_b_path)
        if evidence is not None:
            return evidence

    if "subtitle" in lowered or "副标题" in criterion:
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=True)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text and target_text in content:
                    return True, f"Found subtitle '{target_text}' in {raw_path}"
                if not target_text and ("text-slate-500" in content or "<p" in content):
                    return True, f"Subtitle markup found in {raw_path}"
        return False, "Subtitle content not found"
    if "title" in lowered or "标题" in criterion:
        target_text = _infer_target_text(str(task_payload.get("goal", "")), subtitle=False)
        for raw_path in related_files:
            candidate = repo_b_path / raw_path
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if target_text and target_text in content:
                    return True, f"Found title '{target_text}' in {raw_path}"
                if not target_text and "<h1" in content:
                    return True, f"Heading found in {raw_path}"
        return False, "Heading content not found"
    if "schema" in lowered:
        for raw_path in related_files:
            if not raw_path.endswith(".json"):
                continue
            candidate = repo_b_path / raw_path
            if candidate.exists():
                return True, f"Schema artifact exists: {raw_path}"
        return False, "Schema artifact not found"
    if "prettier" in lowered or "格式化" in criterion:
        report = str(state.get("test_results") or "")
        if "FAIL" in report.upper():
            return False, "Validation report still contains failing checks"
        return True, "Validation report has no failing formatting checks"
    if "只修改" in criterion or "only modify" in lowered:
        allowed = {path.replace("\\", "/") for path in related_files}
        unexpected = [path for path in changed_files if path.replace("\\", "/") not in allowed]
        if unexpected:
            return False, f"Unexpected files changed: {', '.join(unexpected)}"
        return True, "Changed files stayed within declared scope"
    return True, "No deterministic rule required for this criterion"


def _evaluate_s0_003_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    if "agent_register.schema.json" in lowered:
        path = repo_b_path / "docs/contracts/agent_register.schema.json"
        if not path.exists():
            return False, "Register schema file is missing"
        content = path.read_text(encoding="utf-8")
        required_tokens = ['"agentId"', '"runtime"', '"runtimeAgentId"', '"capabilities"']
        missing = [token for token in required_tokens if token not in content]
        return (not missing, "Register schema contains required fields" if not missing else f"Missing fields: {', '.join(missing)}")
    if "agent_heartbeat.schema.json" in lowered:
        path = repo_b_path / "docs/contracts/agent_heartbeat.schema.json"
        if not path.exists():
            return False, "Heartbeat schema file is missing"
        content = path.read_text(encoding="utf-8")
        required_tokens = ['"lastSeenAt"', '"health"', '"status"', '"latencyMs"']
        missing = [token for token in required_tokens if token not in content]
        return (not missing, "Heartbeat schema contains required health fields" if not missing else f"Missing fields: {', '.join(missing)}")
    if "agent_submit_actions.schema.json" in lowered:
        path = repo_b_path / "docs/contracts/agent_submit_actions.schema.json"
        if not path.exists():
            return False, "Submit-actions schema file is missing"
        content = path.read_text(encoding="utf-8")
        required_tokens = ['"symbol"', '"side"', '"qty"', '"reason"', '"idempotency_key"']
        missing = [token for token in required_tokens if token not in content]
        return (not missing, "Submit-actions schema defines the required action fields" if not missing else f"Missing fields: {', '.join(missing)}")
    if "valid example payloads exist" in lowered:
        paths = [
            repo_b_path / "docs/contracts/examples/agent_register.example.json",
            repo_b_path / "docs/contracts/examples/agent_heartbeat.example.json",
            repo_b_path / "docs/contracts/examples/agent_submit_actions.example.json",
        ]
        missing = [path.name for path in paths if not path.exists()]
        return (not missing, "All valid examples exist" if not missing else f"Missing examples: {', '.join(missing)}")
    if "invalid submit-actions example" in lowered:
        path = repo_b_path / "docs/contracts/examples/agent_submit_actions.invalid.json"
        return (path.exists(), "Invalid submit-actions example exists" if path.exists() else "Invalid submit-actions example is missing")
    return None


def _evaluate_s0_004_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    error_codes_path = repo_b_path / "docs/contracts/error_codes.md"
    state_machine_path = repo_b_path / "docs/contracts/state_machine.md"
    error_codes = error_codes_path.read_text(encoding="utf-8") if error_codes_path.exists() else ""
    state_machine = state_machine_path.read_text(encoding="utf-8") if state_machine_path.exists() else ""

    if "error_codes.md" in lowered and "upload" in lowered and "permission" in lowered:
        required_sections = ["## Upload", "## Parsing", "## Risk", "## Matching", "## Permission"]
        missing = [section for section in required_sections if section not in error_codes]
        return (not missing, "error_codes.md covers all required categories" if not missing else f"Missing sections: {', '.join(missing)}")
    if "statement" in lowered and "uploaded" in lowered and "failed" in lowered:
        required_states = ["`uploaded`", "`parsing`", "`parsed`", "`failed`"]
        missing = [state for state in required_states if state not in state_machine]
        return (not missing, "Statement states are documented" if not missing else f"Missing statement states: {', '.join(missing)}")
    if "agent" in lowered and "stale" in lowered and "banned" in lowered:
        required_states = ["`active`", "`paused`", "`stale`", "`banned`"]
        missing = [state for state in required_states if state not in state_machine]
        return (not missing, "Agent states are documented" if not missing else f"Missing agent states: {', '.join(missing)}")
    if "order" in lowered and "submitted" in lowered and "filled" in lowered:
        required_states = ["`submitted`", "`rejected`", "`filled`"]
        missing = [state for state in required_states if state not in state_machine]
        return (not missing, "Order states are documented" if not missing else f"Missing order states: {', '.join(missing)}")
    if "binding" in lowered:
        required_states = ["`pending`", "`active`", "`revoked`", "`expired`"]
        missing = [state for state in required_states if state not in state_machine]
        return (not missing, "Binding states are documented" if not missing else f"Missing binding states: {', '.join(missing)}")
    return None


def _evaluate_s0_005_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    sql_path = repo_b_path / "scripts/init_schema.sql"
    sql = sql_path.read_text(encoding="utf-8") if sql_path.exists() else ""

    if ("primary key" in lowered and "foreign key" in lowered) or ("主键" in criterion and "外键" in criterion):
        required_tokens = ["PRIMARY KEY", "REFERENCES statements(statement_id)", "REFERENCES agents(agent_id)", "UNIQUE"]
        missing = [token for token in required_tokens if token not in sql]
        return (not missing, "Primary, unique, and foreign key constraints are present" if not missing else f"Missing constraints: {', '.join(missing)}")
    if "local initialization" in lowered or "init_schema.sql can be executed" in lowered or "本地初始化" in criterion or "begin/commit" in lowered:
        required_tokens = ["BEGIN;", "COMMIT;", "CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id"]
        missing = [token for token in required_tokens if token not in sql]
        return (not missing, "SQL script has transaction wrapper and supporting indexes" if not missing else f"Missing execution markers: {', '.join(missing)}")
    if "agents" in lowered and "idempotency_keys" in lowered:
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
        missing = [table for table in required_tables if f"CREATE TABLE IF NOT EXISTS {table}" not in sql]
        return (not missing, "init_schema.sql defines all required core tables" if not missing else f"Missing tables: {', '.join(missing)}")
    return None


def _evaluate_s0_006_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    storage_path = repo_b_path / "apps/api/src/modules/statements/storage.py"
    repository_path = repo_b_path / "apps/api/src/modules/statements/repository.py"
    storage_code = storage_path.read_text(encoding="utf-8") if storage_path.exists() else ""
    repository_code = repository_path.read_text(encoding="utf-8") if repository_path.exists() else ""

    if "storage.py" in lowered and "repository.py" in lowered:
        missing = [path.name for path in (storage_path, repository_path) if not path.exists()]
        return (not missing, "Statement storage and repository artifacts exist" if not missing else f"Missing files: {', '.join(missing)}")
    if "object_key" in lowered and "parsed_status" in lowered:
        required_tokens = ["StatementMetadata", "object_key", "market", "owner_id", "parsed_status"]
        missing = [token for token in required_tokens if token not in repository_code]
        return (not missing, "Repository metadata contract covers object_key, market, owner_id, and parsed_status" if not missing else f"Missing repository fields: {', '.join(missing)}")
    if ("statement_id" in lowered and "rollback" in lowered) or ("statement_id" in criterion and "回滚" in criterion):
        required_tokens = ["get_statement_metadata_query", "rollback_statement_metadata_query", "build_statement_object_key", "delete_statement_object"]
        combined = storage_code + "\n" + repository_code
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Lookup by statement_id and rollback helpers are defined" if not missing else f"Missing lookup/rollback helpers: {', '.join(missing)}")
    return None


def _evaluate_s0_007_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    audit_path = repo_b_path / "apps/api/src/modules/audit/service.py"
    idempotency_path = repo_b_path / "apps/api/src/modules/idempotency/service.py"
    audit_code = audit_path.read_text(encoding="utf-8") if audit_path.exists() else ""
    idempotency_code = idempotency_path.read_text(encoding="utf-8") if idempotency_path.exists() else ""

    if "audit" in lowered and "idempotency" in lowered and ("helper" in lowered or "基础设施" in criterion or "复用" in criterion):
        missing = [path.name for path in (audit_path, idempotency_path) if not path.exists()]
        return (not missing, "Audit and idempotency helper modules exist" if not missing else f"Missing helper modules: {', '.join(missing)}")
    if (
        ("single business boundary" in lowered)
        or ("一个业务边界" in criterion)
        or ("only covers" in lowered and "audit" in lowered and "idempotency" in lowered)
        or ("does not expand" in lowered and "module" in lowered)
        or ("audit" in lowered and "idempotency" in lowered and "module" in lowered)
        or ("本 story 只覆盖" in criterion)
        or ("不扩展到相邻业务模块" in criterion)
    ):
        expected = {
            "apps/api/src/modules/audit/service.py",
            "apps/api/src/modules/idempotency/service.py",
        }
        existing = {
            "apps/api/src/modules/audit/service.py" if audit_path.exists() else "",
            "apps/api/src/modules/idempotency/service.py" if idempotency_path.exists() else "",
        }
        existing.discard("")
        return (existing == expected, "Changes stay within the audit/idempotency module boundary" if existing == expected else "Artifacts drifted outside the expected module boundary")
    if ("downstream" in lowered and "reused" in lowered) or ("后续" in criterion and "复用" in criterion):
        required_tokens = [
            "build_audit_write_query",
            "build_audit_log_payload",
            "build_idempotency_lookup_query",
            "build_idempotency_insert_query",
            "evaluate_idempotency",
        ]
        combined = audit_code + "\n" + idempotency_code
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Reusable downstream helper functions are present" if not missing else f"Missing reusable helpers: {', '.join(missing)}")
    if ("failure" in lowered and "result" in lowered) or ("失败路径" in criterion) or ("正常路径" in criterion):
        required_tokens = [
            "INSERT INTO audit_logs",
            "trace_id",
            "seen_before",
            "result_ref",
            "status",
        ]
        combined = audit_code + "\n" + idempotency_code
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Helpers cover both write-path and duplicate/failure-path evaluation" if not missing else f"Missing normal/failure-path coverage tokens: {', '.join(missing)}")
    return None


def _evaluate_s1_001_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    route_path = repo_b_path / "apps/api/src/api/command/routes.py"
    schema_path = repo_b_path / "apps/api/src/schemas/command.py"
    service_path = repo_b_path / "apps/api/src/domain/dna_engine/service.py"
    storage_path = repo_b_path / "apps/api/src/infra/storage/object_store.py"
    route_code = route_path.read_text(encoding="utf-8") if route_path.exists() else ""
    schema_code = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
    service_code = service_path.read_text(encoding="utf-8") if service_path.exists() else ""
    storage_code = storage_path.read_text(encoding="utf-8") if storage_path.exists() else ""
    combined = "\n".join([route_code, schema_code, service_code, storage_code])

    if ("upload" in lowered and "object_key" in lowered) or ("statement_id" in lowered and "upload_status" in lowered):
        required_tokens = [
            '@router.post("/api/v1/statements/upload")',
            "statement_id",
            "upload_status",
            "object_key",
        ]
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Upload route and response contract expose statement_id, upload_status, and object_key" if not missing else f"Missing upload contract tokens: {', '.join(missing)}")
    if ("scope" in lowered and "parsing" in lowered) or ("不扩展到解析" in criterion) or ("只覆盖交割单上传" in criterion):
        unexpected_tokens = ["parse_report", "normalize_statement", "profile_generation"]
        hit = [token for token in unexpected_tokens if token in combined]
        return (not hit, "Artifacts stay focused on upload validation and object-key preparation" if not hit else f"Unexpected downstream tokens found: {', '.join(hit)}")
    if ("csv" in lowered and "xlsx" in lowered) or ("10mb" in lowered) or ("非法格式" in criterion) or ("超限" in criterion):
        required_tokens = [".csv", ".xlsx", ".xls", "10 * 1024 * 1024", "Unsupported statement file type", "Statement file exceeds the 10MB upload limit."]
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Upload validation covers allowed file types, size limit, and explainable failures" if not missing else f"Missing upload validation tokens: {', '.join(missing)}")
    if ("reused" in lowered and "story" in lowered) or ("后续 Story" in criterion) or ("object_key" in lowered and "bucket" in lowered):
        required_tokens = ["build_statement_object_key", "object_store_bucket", "bucket"]
        missing = [token for token in required_tokens if token not in combined]
        return (not missing, "Object-key and bucket helpers are reusable by downstream statement-processing stories" if not missing else f"Missing reusable upload helpers: {', '.join(missing)}")
    if ("failure" in lowered and "result" in lowered) or ("正常路径" in criterion) or ("失败路径" in criterion):
        required_tokens = ['upload_status="uploaded"', 'upload_status="rejected"', "error_message", "Statement file is empty."]
        missing = [token for token in required_tokens if token not in service_code]
        return (not missing, "Service covers both success and key failure-path outcomes" if not missing else f"Missing success/failure-path tokens: {', '.join(missing)}")
    return None


def _evaluate_agenthire_s1_001_criterion(criterion: str, repo_b_path: Path) -> tuple[bool, str] | None:
    lowered = criterion.lower()
    migration_path = repo_b_path / "apps/api/alembic/versions/0001_agent_marketplace_baseline.py"
    tables_path = repo_b_path / "apps/api/src/infra/db/tables.py"
    data_model_path = repo_b_path / "docs/contracts/data-model.md"

    if "schema" in lowered or "migration" in lowered or "marketplace schema" in lowered:
        artifacts_exist = migration_path.exists() and (tables_path.exists() or data_model_path.exists())
        if artifacts_exist:
            return True, "Migration baseline artifacts exist for the marketplace schema story"
        return False, "Migration baseline artifacts are missing"
    return None


def _infer_target_text(goal: str, *, subtitle: bool) -> str | None:
    quote_match = re.search(r"[\"'“”‘’「」『』](.*?)[\"'“”‘’「」『』]", goal)
    if quote_match:
        return quote_match.group(1).strip()

    patterns = [r"subtitle[:：]?\s*(.+)$"] if subtitle else [r"title[:：]?\s*(.+)$"]
    cleaned = goal.strip(" ，。：:!?\"'“”‘’「」『』")
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(" ，。：:!?\"'“”‘’「」『』")
    return None


def _safe_print(message: str) -> None:
    try:
        print(message)
    except OSError:
        pass
