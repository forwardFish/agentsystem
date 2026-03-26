from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from agentsystem.orchestration.story_contracts import enrich_task_with_story_contracts


BASE_DIR = Path(__file__).resolve().parents[3]
POLICY_PATH = BASE_DIR / "config" / "automation" / "agent_activation_policy.yaml"
PARITY_MANIFEST_PATH = BASE_DIR / "config" / "platform" / "gstack_parity_manifest.yaml"

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}
PLANNING_POLICIES = {"planning", "new_demand", "new_epic", "new_sprint"}
RELEASE_POLICIES = {"release", "sprint_closeout", "closeout"}
DEFAULT_WORKFLOW_ENFORCEMENT_POLICY = "gstack_strict"


@dataclass(frozen=True, slots=True)
class AgentActivationPlan:
    story_kind: str
    risk_level: str
    workflow_enforcement_policy: str
    is_bugfix: bool
    is_planning_request: bool
    is_release_closeout: bool
    has_browser_surface: bool
    requires_auth: bool
    needs_design_review: bool
    needs_qa_design_review: bool
    needs_design_consultation: bool
    needs_ceo_review_advice: bool
    qa_strategy: str
    required_modes: list[str]
    advisory_modes: list[str]
    next_recommended_actions: list[str]
    effective_qa_mode: str
    auto_upgrade_to_qa: bool
    expanded_required_agents: list[str]
    mode_to_agent_map: dict[str, list[str]]
    parity_evidence_contract: dict[str, list[str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "story_kind": self.story_kind,
            "risk_level": self.risk_level,
            "workflow_enforcement_policy": self.workflow_enforcement_policy,
            "is_bugfix": self.is_bugfix,
            "is_planning_request": self.is_planning_request,
            "is_release_closeout": self.is_release_closeout,
            "has_browser_surface": self.has_browser_surface,
            "requires_auth": self.requires_auth,
            "needs_design_review": self.needs_design_review,
            "needs_qa_design_review": self.needs_qa_design_review,
            "needs_design_consultation": self.needs_design_consultation,
            "needs_ceo_review_advice": self.needs_ceo_review_advice,
            "qa_strategy": self.qa_strategy,
            "required_modes": list(self.required_modes),
            "advisory_modes": list(self.advisory_modes),
            "next_recommended_actions": list(self.next_recommended_actions),
            "effective_qa_mode": self.effective_qa_mode,
            "auto_upgrade_to_qa": self.auto_upgrade_to_qa,
            "expanded_required_agents": list(self.expanded_required_agents),
            "mode_to_agent_map": dict(self.mode_to_agent_map),
            "parity_evidence_contract": dict(self.parity_evidence_contract),
        }


def apply_agent_activation_policy(task: dict[str, Any], repo_b_path: str | Path | None = None) -> dict[str, Any]:
    runtime_task = dict(task)
    plan = build_agent_activation_plan(task)
    runtime_task["agent_activation_plan"] = plan.as_dict()
    runtime_task["story_kind"] = plan.story_kind
    runtime_task["risk_level"] = plan.risk_level
    runtime_task["workflow_enforcement_policy"] = plan.workflow_enforcement_policy
    runtime_task["has_browser_surface"] = plan.has_browser_surface
    runtime_task["requires_auth"] = plan.requires_auth
    runtime_task["needs_design_review"] = plan.needs_design_review
    runtime_task["needs_qa_design_review"] = plan.needs_qa_design_review
    runtime_task["needs_design_consultation"] = plan.needs_design_consultation
    runtime_task["needs_ceo_review_advice"] = plan.needs_ceo_review_advice
    runtime_task["qa_strategy"] = plan.qa_strategy
    runtime_task["required_modes"] = list(plan.required_modes)
    runtime_task["advisory_modes"] = list(plan.advisory_modes)
    runtime_task["next_recommended_actions"] = list(plan.next_recommended_actions)
    runtime_task["effective_qa_mode"] = plan.effective_qa_mode
    runtime_task["auto_upgrade_to_qa"] = plan.auto_upgrade_to_qa
    runtime_task["expanded_required_agents"] = list(plan.expanded_required_agents)
    runtime_task["mode_to_agent_map"] = dict(plan.mode_to_agent_map)
    runtime_task["parity_evidence_contract"] = dict(plan.parity_evidence_contract)
    runtime_task["upstream_agent_parity"] = _build_upstream_agent_parity(plan.required_modes, plan.advisory_modes)

    if plan.is_bugfix and not str(runtime_task.get("bug_scope") or "").strip():
        runtime_task["bug_scope"] = "bugfix"
    if plan.has_browser_surface and not str(runtime_task.get("session_policy") or "").strip():
        runtime_task["session_policy"] = "authenticated_browser_session" if plan.requires_auth else "browser_evidence"

    agent_policy = str(runtime_task.get("agent_policy") or "auto").strip().lower() or "auto"
    if agent_policy == "manual":
        return enrich_task_with_story_contracts(runtime_task)
    if str(runtime_task.get("skill_mode") or "").strip():
        return enrich_task_with_story_contracts(runtime_task)

    runtime_task["fixer_allowed"] = plan.effective_qa_mode == "qa"
    runtime_task["browser_qa_report_only"] = plan.qa_strategy == "browser" and plan.effective_qa_mode != "qa"
    runtime_task["runtime_qa_report_only"] = plan.qa_strategy == "runtime" and plan.effective_qa_mode != "qa"
    if plan.qa_strategy == "browser" and not runtime_task.get("browser_qa_mode"):
        runtime_task["browser_qa_mode"] = "quick" if plan.effective_qa_mode == "qa" else "qa_only"
    return enrich_task_with_story_contracts(runtime_task)


def build_agent_activation_plan(task: dict[str, Any]) -> AgentActivationPlan:
    policy = _load_policy()
    file_scope = _collect_file_scope(task)

    story_kind = _classify_story_kind(file_scope, policy)
    workflow_enforcement_policy = _resolve_workflow_enforcement_policy(task)
    risk_level = _classify_risk_level(task, file_scope, story_kind, policy)
    has_browser_surface = _has_browser_surface(task, file_scope, story_kind)
    requires_auth = bool(task.get("requires_auth"))
    is_bugfix = _is_bugfix_task(task)
    is_planning_request = workflow_enforcement_policy in PLANNING_POLICIES
    is_release_closeout = workflow_enforcement_policy in RELEASE_POLICIES
    needs_design_review = has_browser_surface and story_kind in {"ui", "mixed"}
    needs_qa_design_review = needs_design_review
    needs_design_consultation = needs_design_review
    needs_ceo_review_advice = (
        not is_planning_request
        and _is_advisory_enabled("plan-ceo-review", story_kind, risk_level, requires_auth, policy)
    )

    qa_strategy = "browser" if has_browser_surface else "runtime"
    effective_qa_mode = "qa" if not is_planning_request and not is_release_closeout else str(policy["qa"].get("high_risk_mode") or "qa")
    auto_upgrade_to_qa = False

    default_required_modes = [
        str(item).strip()
        for item in (policy["defaults"].get("required_modes") or [])
        if str(item).strip()
    ]
    required_modes: list[str]
    if is_planning_request:
        required_modes = ["office-hours", "plan-ceo-review", "plan-eng-review"]
    elif is_release_closeout:
        required_modes = ["ship", "document-release", "retro"]
    else:
        if is_bugfix:
            required_modes = ["investigate", "review", "qa"]
        else:
            required_modes = [mode for mode in default_required_modes if mode not in {"qa-only", "qa"}]
            required_modes.append("qa")
        if requires_auth and has_browser_surface:
            required_modes.append("setup-browser-cookies")
        if has_browser_surface and story_kind in {"ui", "mixed"}:
            required_modes.extend(["browse", "plan-design-review", "design-consultation", "design-review"])

    advisory_modes: list[str] = []

    required_modes = _dedupe_preserve_order(required_modes)
    advisory_modes = [mode for mode in _dedupe_preserve_order(advisory_modes) if mode not in required_modes]
    next_actions = [_next_action_for_mode(mode) for mode in advisory_modes]
    contracted_task = enrich_task_with_story_contracts(
        {
            **task,
            "story_kind": story_kind,
            "required_modes": required_modes,
            "advisory_modes": advisory_modes,
            "qa_strategy": qa_strategy,
            "requires_auth": requires_auth,
        }
    )
    resolved_story_kind = str(contracted_task.get("story_kind") or story_kind).strip() or story_kind
    return AgentActivationPlan(
        story_kind=resolved_story_kind,
        risk_level=risk_level,
        workflow_enforcement_policy=workflow_enforcement_policy,
        is_bugfix=is_bugfix,
        is_planning_request=is_planning_request,
        is_release_closeout=is_release_closeout,
        has_browser_surface=has_browser_surface,
        requires_auth=requires_auth,
        needs_design_review=needs_design_review,
        needs_qa_design_review=needs_qa_design_review,
        needs_design_consultation=needs_design_consultation,
        needs_ceo_review_advice=needs_ceo_review_advice,
        qa_strategy=qa_strategy,
        required_modes=required_modes,
        advisory_modes=advisory_modes,
        next_recommended_actions=next_actions,
        effective_qa_mode=effective_qa_mode,
        auto_upgrade_to_qa=auto_upgrade_to_qa,
        expanded_required_agents=list(contracted_task.get("expanded_required_agents") or []),
        mode_to_agent_map=dict(contracted_task.get("mode_to_agent_map") or {}),
        parity_evidence_contract=dict(contracted_task.get("parity_evidence_contract") or {}),
    )


def summarize_sprint_advice(stories: list[dict[str, Any]], *, release: bool = False) -> dict[str, Any]:
    plans = [build_agent_activation_plan(story) for story in stories]
    advisory_modes: list[str] = []
    if stories:
        advisory_modes.append("office-hours")
    if any(plan.needs_ceo_review_advice for plan in plans):
        advisory_modes.append("plan-ceo-review")
    if stories:
        advisory_modes.append("plan-eng-review")
    if any(plan.needs_design_consultation for plan in plans):
        advisory_modes.append("design-consultation")
    if release:
        advisory_modes.extend(["ship", "document-release", "retro"])
    advisory_modes = list(dict.fromkeys(advisory_modes))
    recommended_actions = [_next_action_for_mode(mode) for mode in advisory_modes]
    story_kinds = sorted({plan.story_kind for plan in plans})
    risk_level = _highest_risk([plan.risk_level for plan in plans])
    return {
        "story_count": len(stories),
        "story_kinds": story_kinds,
        "risk_level": risk_level,
        "advisory_modes": advisory_modes,
        "next_recommended_actions": recommended_actions,
    }


def _load_policy() -> dict[str, Any]:
    payload = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{POLICY_PATH} must contain a mapping")
    return payload


@lru_cache(maxsize=1)
def _load_parity_manifest() -> dict[str, Any]:
    payload = yaml.safe_load(PARITY_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{PARITY_MANIFEST_PATH} must contain a mapping")
    return payload


def _collect_file_scope(task: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("primary_files", "related_files", "secondary_files"):
        raw = task.get(key)
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _classify_story_kind(file_scope: list[str], policy: dict[str, Any]) -> str:
    classification = policy.get("classification", {}) if isinstance(policy.get("classification"), dict) else {}
    ui_hits = [_is_ui_path(path, classification) for path in file_scope]
    api_hits = [_matches_prefix(path, classification.get("api_prefixes") or []) for path in file_scope]
    runtime_hits = [_matches_prefix(path, classification.get("runtime_prefixes") or []) for path in file_scope]
    active_categories = sum(
        [
            any(ui_hits),
            any(api_hits),
            any(runtime_hits),
        ]
    )
    if active_categories >= 2:
        return "mixed"
    if any(ui_hits):
        return "ui"
    if any(runtime_hits):
        return "runtime_data"
    if any(api_hits):
        return "api"
    return "api"


def _classify_risk_level(task: dict[str, Any], file_scope: list[str], story_kind: str, policy: dict[str, Any]) -> str:
    blast_radius = str(task.get("blast_radius") or "").strip().upper()
    if blast_radius == "L3" or story_kind == "mixed":
        return "high"
    classification = policy.get("classification", {}) if isinstance(policy.get("classification"), dict) else {}
    high_tokens = [str(item).lower() for item in (classification.get("high_risk_tokens") or [])]
    lowered_scope = " ".join(file_scope).lower()
    if any(token in lowered_scope for token in high_tokens):
        return "high"
    if blast_radius == "L2":
        return "medium"
    if len(file_scope) >= 4:
        return "medium"
    return "low"


def _has_browser_surface(task: dict[str, Any], file_scope: list[str], story_kind: str) -> bool:
    for key in ("browser_urls", "qa_urls", "preview_urls", "runtime_urls"):
        value = task.get(key)
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
        if isinstance(value, str) and value.strip():
            return True
    if str(task.get("preview_base_url") or "").strip():
        return True
    return story_kind in {"ui", "mixed"}


def _has_design_signal(file_scope: list[str], policy: dict[str, Any]) -> bool:
    classification = policy.get("classification", {}) if isinstance(policy.get("classification"), dict) else {}
    tokens = [str(item).lower() for item in (classification.get("design_tokens") or [])]
    lowered_scope = " ".join(file_scope).lower()
    return any(token in lowered_scope for token in tokens)


def _is_advisory_enabled(
    mode_id: str,
    story_kind: str,
    risk_level: str,
    requires_auth: bool,
    policy: dict[str, Any],
) -> bool:
    advisory = policy.get("advisory", {}) if isinstance(policy.get("advisory"), dict) else {}
    mode = advisory.get(mode_id, {}) if isinstance(advisory.get(mode_id), dict) else {}
    if mode.get("requires_auth") and not requires_auth:
        return False
    allowed_kinds = [str(item) for item in (mode.get("story_kinds") or []) if str(item).strip()]
    if allowed_kinds and story_kind not in allowed_kinds:
        return False
    min_risk = str(mode.get("min_risk") or "").strip().lower()
    if min_risk and RISK_ORDER.get(risk_level, 0) < RISK_ORDER.get(min_risk, 0):
        return False
    return bool(mode)


def _highest_risk(risk_levels: list[str]) -> str:
    highest = "low"
    for item in risk_levels:
        if RISK_ORDER.get(item, 0) > RISK_ORDER.get(highest, 0):
            highest = item
    return highest


def _matches_prefix(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(str(prefix)) for prefix in prefixes)


def _is_ui_path(path: str, classification: dict[str, Any]) -> bool:
    prefixes = [str(item) for item in (classification.get("ui_prefixes") or []) if str(item).strip()]
    extensions = [str(item) for item in (classification.get("ui_extensions") or []) if str(item).strip()]
    return _matches_prefix(path, prefixes) or any(path.endswith(ext) for ext in extensions)


def _next_action_for_mode(mode_id: str) -> str:
    messages = {
        "office-hours": "Run office-hours first to sharpen demand, wedge, and proof before planning.",
        "plan-ceo-review": "Run plan-ceo-review before locking the sprint scope.",
        "plan-eng-review": "Run plan-eng-review before implementation starts so architecture and tests are explicit.",
        "investigate": "Run investigate before any bugfix or rollback-style change.",
        "browse": "Run browse first to collect real page evidence before design or QA decisions.",
        "design-consultation": "Run design-consultation before large UI implementation starts.",
        "setup-browser-cookies": "Prepare browser session import before authenticated QA.",
        "ship": "Run ship only after sprint acceptance is complete and release is approved.",
        "document-release": "Run document-release after acceptance so docs match shipped behavior.",
        "retro": "Run retro after the release package is assembled so improvements are captured immediately.",
    }
    return messages.get(mode_id, f"Review advisory mode {mode_id}.")


def _is_bugfix_task(task: dict[str, Any]) -> bool:
    tokens = (
        str(task.get("bug_scope") or "").strip().lower(),
        str(task.get("story_type") or "").strip().lower(),
        str(task.get("issue_type") or "").strip().lower(),
        str(task.get("workflow_enforcement_policy") or "").strip().lower(),
        str(task.get("goal") or "").strip().lower(),
    )
    if any(token in {"bugfix", "bug", "incident", "regression"} for token in tokens[:-1]):
        return True
    goal = tokens[-1]
    return any(keyword in goal for keyword in ("bugfix", "bug", "incident", "regression"))


def _resolve_workflow_enforcement_policy(task: dict[str, Any]) -> str:
    explicit = str(task.get("workflow_enforcement_policy") or "").strip().lower()
    if explicit:
        return explicit
    if task.get("release_scope") or task.get("retro_window") or str(task.get("skill_mode") or "").strip() in {
        "ship",
        "document-release",
        "retro",
    }:
        return "sprint_closeout"
    if _is_bugfix_task(task):
        return "bugfix_strict"
    return DEFAULT_WORKFLOW_ENFORCEMENT_POLICY


def _build_upstream_agent_parity(required_modes: list[str], advisory_modes: list[str]) -> dict[str, Any]:
    manifest = _load_parity_manifest()
    upstream = dict(manifest.get("upstream") or {})
    agents = manifest.get("agents") or []
    if not isinstance(agents, list):
        agents = []
    indexed = {
        str(item.get("mode_id") or "").strip(): item
        for item in agents
        if isinstance(item, dict) and str(item.get("mode_id") or "").strip()
    }
    tracked_modes = _dedupe_preserve_order([*required_modes, *advisory_modes])
    tracked_payload = {
        mode: {
            "entry_mode": indexed.get(mode, {}).get("entry_mode"),
            "stop_after": indexed.get(mode, {}).get("stop_after"),
            "parity_status": indexed.get(mode, {}).get("parity_status"),
            "upstream_skill": indexed.get(mode, {}).get("upstream_skill"),
        }
        for mode in tracked_modes
        if mode in indexed
    }
    return {
        "repo": upstream.get("repo"),
        "commit": upstream.get("commit"),
        "license": upstream.get("license"),
        "tracked_modes": tracked_payload,
        "intentional_deviations": list(manifest.get("intentional_deviations") or []),
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        mode = str(value).strip()
        if not mode or mode in seen:
            continue
        seen.add(mode)
        result.append(mode)
    return result
