from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


PRE_HOOK_AGENTS = ["office_hours", "plan_ceo_review", "sprint_framing", "gstack_parity_audit"]
POST_HOOK_AGENTS = ["ship", "document_release", "retro"]

MODE_TO_AGENT_CANDIDATES: dict[str, list[str]] = {
    "office-hours": ["office_hours"],
    "plan-ceo-review": ["plan_ceo_review"],
    "plan-eng-review": ["requirement_analysis", "architecture_review"],
    "investigate": ["investigate"],
    "browse": ["browse"],
    "plan-design-review": ["plan_design_review"],
    "design-consultation": ["design_consultation"],
    "review": ["reviewer"],
    "qa": ["tester", "runtime_qa", "browser_qa", "fixer"],
    "qa-only": ["tester", "runtime_qa", "browser_qa"],
    "design-review": ["browser_qa", "qa_design_review"],
    "setup-browser-cookies": ["setup_browser_cookies"],
    "ship": ["ship"],
    "document-release": ["document_release"],
    "retro": ["retro"],
}

AGENT_OUTPUTS: dict[str, list[str]] = {
    "office_hours": ["office_hours_artifact"],
    "requirement_analysis": ["requirement_breakdown", "task_payload_refresh"],
    "plan_ceo_review": ["plan_ceo_review_package"],
    "architecture_review": ["architecture_review_report", "qa_test_plan"],
    "investigate": ["investigation_report"],
    "browse": ["browser_evidence"],
    "setup_browser_cookies": ["browser_storage_state"],
    "plan_design_review": ["design_route_contract", "design_review_report"],
    "design_consultation": ["design_consultation_report", "DESIGN.md"],
    "workspace_prep": ["workspace_ready"],
    "backend_dev": ["service_or_route_changes"],
    "frontend_dev": ["ui_changes"],
    "database_dev": ["schema_or_storage_changes"],
    "devops_dev": ["runtime_config_changes"],
    "sync_merge": ["merged_story_workspace"],
    "code_style_reviewer": ["code_style_review_report"],
    "tester": ["test_report"],
    "browser_qa": ["browser_qa_report"],
    "runtime_qa": ["runtime_qa_report"],
    "security_scanner": ["security_report"],
    "qa_design_review": ["qa_design_review_report"],
    "reviewer": ["review_report"],
    "code_acceptance": ["code_acceptance_report"],
    "acceptance_gate": ["acceptance_report", "agent_contract_satisfaction"],
    "fixer": ["fix_report"],
    "doc_writer": ["delivery_docs"],
    "ship": ["ship_report"],
    "document_release": ["document_release_report"],
    "retro": ["retro_report"],
}

AGENT_FAILURE_RETURNS: dict[str, str | None] = {
    "tester": "fixer",
    "browser_qa": "fixer",
    "runtime_qa": "fixer",
    "qa_design_review": "fixer",
    "reviewer": "fixer",
    "code_style_reviewer": "fixer",
    "code_acceptance": "fixer",
    "acceptance_gate": "fixer",
    "fixer": "tester",
}

PARITY_EVIDENCE_DEFAULTS: dict[str, list[str]] = {
    "office-hours": ["office_hours_path"],
    "plan-ceo-review": ["plan_ceo_review_path"],
    "plan-eng-review": ["architecture_review_report", "qa_test_plan_path"],
    "investigate": ["investigation_report"],
    "browse": ["browse_report"],
    "plan-design-review": ["plan_design_review_report"],
    "design-consultation": ["design_consultation_report", "design_contract_path"],
    "review": ["review_report"],
    "qa": ["test_report", "runtime_or_browser_qa_report"],
    "qa-only": ["test_report", "runtime_or_browser_qa_report"],
    "design-review": ["browser_qa_report", "qa_design_review_report"],
    "setup-browser-cookies": ["browser_storage_state_path"],
    "ship": ["ship_report"],
    "document-release": ["document_release_report"],
    "retro": ["retro_report"],
}


@dataclass(frozen=True, slots=True)
class StoryContractBundle:
    implementation_contract: dict[str, Any]
    required_artifact_types: list[str]
    contract_scope_paths: list[str]
    agent_execution_contract: list[dict[str, Any]]
    expanded_required_agents: list[str]
    mode_to_agent_map: dict[str, list[str]]
    parity_evidence_contract: dict[str, list[str]]
    blocking_issue_types: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "implementation_contract": self.implementation_contract,
            "required_artifact_types": list(self.required_artifact_types),
            "contract_scope_paths": list(self.contract_scope_paths),
            "agent_execution_contract": list(self.agent_execution_contract),
            "expanded_required_agents": list(self.expanded_required_agents),
            "mode_to_agent_map": dict(self.mode_to_agent_map),
            "parity_evidence_contract": dict(self.parity_evidence_contract),
            "blocking_issue_types": list(self.blocking_issue_types),
        }


def enrich_task_with_story_contracts(task: dict[str, Any]) -> dict[str, Any]:
    runtime_task = dict(task)
    implementation_contract = build_implementation_contract(runtime_task)
    contract_scope_paths = infer_contract_scope_paths(runtime_task, implementation_contract=implementation_contract)
    if implementation_contract.get("story_track") == "contract_schema":
        runtime_task["story_kind"] = "contract_schema"
    required_modes = [str(item).strip() for item in (runtime_task.get("required_modes") or []) if str(item).strip()]
    mode_to_agent_map = build_mode_to_agent_map(runtime_task, required_modes)
    expanded_required_agents = expand_required_agents(runtime_task, mode_to_agent_map=mode_to_agent_map)
    agent_execution_contract = build_agent_execution_contract(runtime_task, expanded_required_agents)
    parity_evidence_contract = build_parity_evidence_contract(required_modes)
    blocking_issue_types = [
        "syntax_invalid",
        "cross_language_contamination",
        "placeholder_artifact",
        "integration_missing",
        "agent_contract_missing",
    ]
    runtime_task.update(
        StoryContractBundle(
            implementation_contract=implementation_contract,
            required_artifact_types=list(implementation_contract.get("required_artifact_types") or []),
            contract_scope_paths=contract_scope_paths,
            agent_execution_contract=agent_execution_contract,
            expanded_required_agents=expanded_required_agents,
            mode_to_agent_map=mode_to_agent_map,
            parity_evidence_contract=parity_evidence_contract,
            blocking_issue_types=blocking_issue_types,
        ).as_dict()
    )
    return runtime_task


def build_implementation_contract(task: dict[str, Any]) -> dict[str, Any]:
    story_track = infer_story_track(task)
    file_scope = collect_file_scope(task)
    artifact_inventory = build_artifact_inventory(file_scope)
    required_artifact_types = _required_artifact_types_for_story(task, story_track, artifact_inventory)
    storage_change = _requires_database_dev(file_scope)
    contract_scope_paths = infer_contract_scope_paths(task, story_track=story_track)
    return {
        "story_id": str(task.get("story_id") or task.get("task_id") or "").strip(),
        "story_kind": story_track if story_track == "contract_schema" else str(task.get("story_kind") or "").strip() or story_track,
        "story_track": story_track,
        "required_artifact_types": required_artifact_types,
        "artifact_inventory": artifact_inventory,
        "contract_scope_paths": contract_scope_paths,
        "requires_browser_evidence": story_track in {"ui", "ui_mixed"},
        "requires_design_evidence": story_track in {"ui", "ui_mixed"},
        "requires_database_dev": storage_change,
        "requires_persistence_changes": storage_change,
        "completion_rule": "implementation_contract + agent_execution_contract + agent_coverage_report + acceptance_gate",
    }


def build_mode_to_agent_map(task: dict[str, Any], required_modes: list[str] | None = None) -> dict[str, list[str]]:
    runtime_task = dict(task)
    story_track = infer_story_track(runtime_task)
    requires_auth = bool(runtime_task.get("requires_auth"))
    qa_strategy = str(runtime_task.get("qa_strategy") or "runtime").strip() or "runtime"
    resolved_modes = required_modes or [str(item).strip() for item in (runtime_task.get("required_modes") or []) if str(item).strip()]

    mapping: dict[str, list[str]] = {}
    for mode in resolved_modes:
        candidates = list(MODE_TO_AGENT_CANDIDATES.get(mode, []))
        if mode == "qa":
            candidates = ["tester", "browser_qa" if qa_strategy == "browser" else "runtime_qa", "fixer"]
        elif mode == "qa-only":
            candidates = ["tester", "browser_qa" if qa_strategy == "browser" else "runtime_qa"]
        elif mode == "design-review":
            candidates = ["browser_qa", "qa_design_review"]
        elif mode == "setup-browser-cookies" and not requires_auth:
            candidates = []
        elif mode == "browse" and story_track not in {"ui", "ui_mixed"}:
            candidates = []
        mapping[mode] = [candidate for candidate in candidates if candidate]
    return mapping


def expand_required_agents(task: dict[str, Any], *, mode_to_agent_map: dict[str, list[str]] | None = None) -> list[str]:
    runtime_task = dict(task)
    story_track = infer_story_track(runtime_task)
    file_scope = collect_file_scope(runtime_task)
    chain: list[str] = []
    if _is_bugfix_task(runtime_task):
        chain.append("investigate")

    if story_track in {"ui", "ui_mixed"}:
        if bool(runtime_task.get("requires_auth")):
            chain.append("setup_browser_cookies")
        chain.extend(["browse", "plan_design_review", "design_consultation"])

    chain.extend(["requirement_analysis", "architecture_review", "workspace_prep"])

    if story_track in {"ui", "ui_mixed"}:
        chain.append("frontend_dev")
    if story_track in {"api_domain", "contract_schema", "ui_mixed"}:
        chain.append("backend_dev")
    if _requires_database_dev(file_scope):
        chain.append("database_dev")
    if _requires_devops_dev(file_scope):
        chain.append("devops_dev")

    chain.extend(["sync_merge", "code_style_reviewer", "tester"])
    if story_track in {"ui", "ui_mixed"}:
        chain.extend(["browser_qa", "qa_design_review"])
    else:
        chain.append("runtime_qa")
    chain.extend(["security_scanner", "reviewer", "code_acceptance", "acceptance_gate", "doc_writer"])

    if mode_to_agent_map:
        for agents in mode_to_agent_map.values():
            for agent in agents:
                if agent == "fixer":
                    continue
                if agent not in chain:
                    insertion_point = chain.index("sync_merge") if "sync_merge" in chain else len(chain)
                    chain.insert(insertion_point, agent)
        if any("fixer" in agents for agents in mode_to_agent_map.values()):
            chain.append("fixer")
    return _dedupe_preserve_order(chain)


def build_agent_execution_contract(task: dict[str, Any], expanded_required_agents: list[str]) -> list[dict[str, Any]]:
    contract: list[dict[str, Any]] = []
    implementation_contract = build_implementation_contract(task)
    required_artifacts = list(implementation_contract.get("required_artifact_types") or [])
    for index, agent in enumerate(expanded_required_agents):
        downstream = expanded_required_agents[index + 1] if index + 1 < len(expanded_required_agents) else None
        outputs = AGENT_OUTPUTS.get(agent, [f"{agent}_artifact"])
        contract.append(
            {
                "agent": agent,
                "entry_condition": _entry_condition_for_agent(agent, task, required_artifacts),
                "required_inputs": _required_inputs_for_agent(agent, task),
                "expected_outputs": outputs,
                "downstream": downstream,
                "failure_return_target": AGENT_FAILURE_RETURNS.get(agent),
                "fixer_allowed": agent == "fixer" or False,
                "primary_implementation_owner": agent in {"backend_dev", "frontend_dev", "database_dev", "devops_dev"},
            }
        )
    return contract


def build_parity_evidence_contract(required_modes: list[str]) -> dict[str, list[str]]:
    return {
        mode: list(PARITY_EVIDENCE_DEFAULTS.get(mode, [f"{mode}_artifact"]))
        for mode in required_modes
    }


def collect_file_scope(task: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("primary_files", "secondary_files", "related_files", "contract_scope_paths"):
        raw = task.get(key)
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        marker = PurePosixPath(value.replace("\\", "/")).as_posix()
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(marker)
    return normalized


def build_artifact_inventory(paths: list[str]) -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = {}
    for path in paths:
        artifact_type = classify_artifact_type(path)
        inventory.setdefault(artifact_type, []).append(path)
    return inventory


def classify_artifact_type(path: str) -> str:
    marker = PurePosixPath(str(path).replace("\\", "/")).as_posix().lower()
    if (
        "/tests/" in marker
        or marker.startswith("tests/")
        or marker.startswith("apps/api/tests/")
        or marker.endswith("_test.py")
        or marker.endswith(".test.py")
        or marker.endswith(".test.ts")
        or marker.endswith(".test.tsx")
        or marker.endswith(".spec.ts")
        or marker.endswith(".spec.tsx")
        or marker.endswith(".spec.js")
        or marker.endswith(".spec.jsx")
    ):
        return "tests"
    if marker.startswith("docs/") or marker.endswith(".md"):
        return "docs"
    if (
        "/schema" in marker
        or "/schemas/" in marker
        or marker.endswith(".schema.json")
        or "/alembic/" in marker
        or marker.endswith("/tables.py")
        or marker.endswith("/models.py")
    ):
        return "schema"
    if "container.py" in marker or "containers/" in marker or "wiring" in marker:
        return "container_wiring"
    if marker.endswith(".sql") or "/migrations/" in marker or "repository.py" in marker or "storage.py" in marker:
        return "schema"
    if "/projection/" in marker:
        return "service"
    if "/domain/" in marker or "/modules/" in marker or marker.endswith("service.py"):
        return "service"
    if "/src/api/" in marker or "/routes/" in marker or marker.endswith("routes.py"):
        return "route"
    return "supporting_code"


def infer_story_track(task: dict[str, Any]) -> str:
    story_kind = str(task.get("story_kind") or "").strip().lower()
    file_scope = collect_file_scope(task)
    if _is_contract_schema_story(file_scope):
        return "contract_schema"
    has_ui = any(_is_ui_path(path) for path in file_scope) or story_kind == "ui"
    has_api = any(_is_api_path(path) for path in file_scope) or story_kind in {"api", "runtime_data"}
    if has_ui and has_api:
        return "ui_mixed"
    if has_ui:
        return "ui"
    return "api_domain"


def _required_artifact_types_for_story(
    task: dict[str, Any],
    story_track: str,
    artifact_inventory: dict[str, list[str]] | None = None,
) -> list[str]:
    inventory = artifact_inventory or build_artifact_inventory(collect_file_scope(task))
    if story_track == "contract_schema":
        required = _required_contract_artifacts_from_inventory(inventory)
    elif story_track in {"ui", "ui_mixed"}:
        required = ["tests", "docs", "browser_evidence", "design_evidence"]
        if story_track == "ui_mixed":
            required = ["schema", "service", "route", "container_wiring", *required]
    else:
        required = ["schema", "service", "route", "container_wiring", "tests", "docs"]
    return _dedupe_preserve_order(required)


def infer_contract_scope_paths(
    task: dict[str, Any],
    *,
    implementation_contract: dict[str, Any] | None = None,
    story_track: str | None = None,
) -> list[str]:
    contract = implementation_contract or {}
    resolved_track = story_track or str(contract.get("story_track") or "").strip() or infer_story_track(task)
    file_scope = collect_file_scope(task)
    if resolved_track == "contract_schema":
        return []
    if resolved_track not in {"api_domain", "ui_mixed"}:
        return []

    story_id = str(task.get("story_id") or task.get("task_id") or "").strip().lower().replace("-", "_")
    module_slug = _infer_module_slug(file_scope, fallback=story_id or "story")
    schema_slug = "event" if "event" in module_slug else module_slug
    route_path = _infer_route_path(file_scope, task=task)
    service_path = _infer_service_path(file_scope, task=task, module_slug=module_slug)
    docs_path = f"docs/requirements/{story_id or module_slug}_delivery.md"
    tests_path = f"apps/api/tests/test_{module_slug}.py"
    scope_paths = [
        f"apps/api/src/schemas/{schema_slug}.py",
        service_path,
        route_path,
        "apps/api/src/services/container.py",
        tests_path,
        docs_path,
    ]
    normalized_scope = {path.replace("\\", "/").lower() for path in file_scope}
    if route_path.endswith("/command/routes.py"):
        scope_paths.extend(
            [
                "apps/api/src/schemas/command.py",
                "apps/api/src/settings/base.py",
            ]
        )
    if "apps/api/src/domain/event_ingestion/service.py" in normalized_scope:
        scope_paths.extend(
            [
                "apps/api/src/domain/theme_mapping/service.py",
                "apps/api/src/domain/event_casebook/service.py",
            ]
        )
    if "apps/api/src/domain/event_casebook/service.py" in normalized_scope:
        scope_paths.extend(
            [
                "apps/api/src/domain/event_ingestion/service.py",
                "apps/api/src/domain/event_structuring/service.py",
                "apps/api/src/domain/theme_mapping/service.py",
                "apps/api/src/schemas/command.py",
                "apps/api/src/settings/base.py",
            ]
        )
    return [path for path in _dedupe_preserve_order([*file_scope, *scope_paths]) if path not in file_scope]


def _entry_condition_for_agent(agent: str, task: dict[str, Any], required_artifacts: list[str]) -> str:
    story_track = infer_story_track(task)
    if agent == "fixer":
        return "Only after a validation agent fails and emits a blocking issue."
    if agent == "acceptance_gate":
        return "Runs only after style review, reviewer, and code acceptance report green or waived."
    if agent in {"browser_qa", "qa_design_review"}:
        return "Requires browser surface evidence or UI story classification."
    if agent == "database_dev":
        return "Requires schema/storage/persistence impact."
    if agent == "backend_dev":
        if story_track == "contract_schema":
            return "Requires contract/schema/docs delivery for the declared story scope."
        return "Requires implementation contract with service/route/container delivery."
    if agent == "frontend_dev":
        return "Requires UI story classification."
    if agent == "doc_writer":
        return "Runs only after acceptance_gate passes."
    if agent == "investigate":
        return "Required bugfix precondition before any builder starts."
    if agent == "workspace_prep":
        return "Runs after requirement and architecture framing are available."
    return "Runs when upstream required inputs are present."


def _required_inputs_for_agent(agent: str, task: dict[str, Any]) -> list[str]:
    shared_inputs = ["task_payload", "implementation_contract", "agent_execution_contract"]
    extras = {
        "acceptance_gate": ["agent_coverage_report", "delivery_evidence"],
        "tester": ["required_artifact_types"],
        "browser_qa": ["browse_report"],
        "qa_design_review": ["browser_qa_report", "design_contract_path"],
        "doc_writer": ["acceptance_report", "delivery_evidence"],
        "investigate": ["blocking_issue_types"],
    }
    return _dedupe_preserve_order([*shared_inputs, *(extras.get(agent) or [])])


def _is_ui_path(path: str) -> bool:
    marker = str(path).replace("\\", "/").lower()
    return marker.startswith("apps/web/") or marker.endswith((".tsx", ".jsx", ".css", ".scss", ".html"))


def _is_api_path(path: str) -> bool:
    marker = str(path).replace("\\", "/").lower()
    return marker.startswith("apps/api/") or marker.endswith((".py", ".sql"))


def _is_contract_schema_story(file_scope: list[str]) -> bool:
    if not file_scope:
        return False
    blockers = ("routes.py", "container.py", "/domain/", "/projection/", "service.py", "apps/web/")
    if any(any(token in path.lower() for token in blockers) for path in file_scope):
        return False
    return all(
        "/schemas/" in path.lower()
        or "/contracts/" in path.lower()
        or path.lower().startswith("docs/")
        or path.lower().startswith("packages/schema/")
        for path in file_scope
    )


def _requires_database_dev(file_scope: list[str]) -> bool:
    tokens = ("/infra/db/", "/alembic/", "/migrations/", ".sql", "repository.py", "storage.py", "tables.py", "models.py", "persistence")
    return any(any(token in path.lower() for token in tokens) for path in file_scope)


def _requires_devops_dev(file_scope: list[str]) -> bool:
    tokens = ("docker", "compose", "infra/", "deployment", "config/runtime")
    return any(any(token in path.lower() for token in tokens) for path in file_scope)


def _is_bugfix_task(task: dict[str, Any]) -> bool:
    values = (
        str(task.get("bug_scope") or "").strip().lower(),
        str(task.get("story_type") or "").strip().lower(),
        str(task.get("issue_type") or "").strip().lower(),
        str(task.get("workflow_enforcement_policy") or "").strip().lower(),
        str(task.get("goal") or "").strip().lower(),
    )
    return any(item in {"bugfix", "bug", "incident", "regression"} for item in values[:-1]) or any(
        token in values[-1] for token in ("bugfix", "bug", "incident", "regression")
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        marker = str(value).strip()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(marker)
    return result


def _required_contract_artifacts_from_inventory(inventory: dict[str, list[str]]) -> list[str]:
    allowed = ["schema", "tests", "docs"]
    required = [artifact_type for artifact_type in allowed if inventory.get(artifact_type)]
    if required:
        return required
    return ["docs"]


def _infer_module_slug(file_scope: list[str], *, fallback: str) -> str:
    for path in file_scope:
        normalized = path.replace("\\", "/")
        if normalized.endswith("service.py"):
            return PurePosixPath(normalized).parent.name.replace("-", "_")
        if "/schemas/" in normalized and normalized.endswith(".py"):
            return PurePosixPath(normalized).stem.replace("-", "_")
    return fallback.replace("-", "_")


def _infer_route_path(file_scope: list[str], *, task: dict[str, Any] | None = None) -> str:
    goal = str((task or {}).get("goal") or "").strip().lower()
    for path in file_scope:
        normalized = path.replace("\\", "/")
        if "/api/query/" in normalized or "/projection/" in normalized or "casebook" in normalized:
            return "apps/api/src/api/query/routes.py"
    if any(token in goal for token in ("read model", "casebook", "review report", "outcome", "retrieval", "why")):
        return "apps/api/src/api/query/routes.py"
    return "apps/api/src/api/command/routes.py"


def _infer_service_path(file_scope: list[str], *, task: dict[str, Any] | None = None, module_slug: str) -> str:
    for path in file_scope:
        normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
        if normalized.endswith("service.py") and ("/domain/" in normalized or "/modules/" in normalized or "/projection/" in normalized):
            return normalized

    haystack = " ".join(
        str((task or {}).get(key) or "").strip().lower()
        for key in ("task_name", "goal", "story_file", "sprint_id", "story_id")
    )
    keyword_overrides = (
        (("acceptance pack", "acceptance_pack", "migration handoff", "migration_handoff", "handoff"), "apps/api/src/domain/acceptance_pack/service.py"),
        (("mirror agent", "mirror_agent"), "apps/api/src/domain/mirror_agent/service.py"),
        (("calibration", "weight feedback", "weight_feedback"), "apps/api/src/domain/calibration/service.py"),
        (("belief graph", "belief_graph"), "apps/api/src/domain/belief_graph/service.py"),
        (("scenario", "watchpoint"), "apps/api/src/domain/scenario_engine/service.py"),
        (("simulation", "timeline", "action log", "action_log"), "apps/api/src/domain/event_simulation/service.py"),
        (("review report", "outcome", "reliability", "retrieval", "why"), "apps/api/src/domain/reporting/service.py"),
        (("participant", "prepare orchestrator", "prepare_orchestrator"), "apps/api/src/domain/participant_preparation/service.py"),
        (("theme", "mapping"), "apps/api/src/domain/theme_mapping/service.py"),
    )
    for keywords, path in keyword_overrides:
        if any(keyword in haystack for keyword in keywords):
            return path
    return f"apps/api/src/domain/{module_slug}/service.py"
