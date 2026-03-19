from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parents[3]
POLICY_PATH = BASE_DIR / "config" / "automation" / "agent_activation_policy.yaml"

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True, slots=True)
class AgentActivationPlan:
    story_kind: str
    risk_level: str
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "story_kind": self.story_kind,
            "risk_level": self.risk_level,
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
        }


def apply_agent_activation_policy(task: dict[str, Any], repo_b_path: str | Path | None = None) -> dict[str, Any]:
    runtime_task = dict(task)
    plan = build_agent_activation_plan(task)
    runtime_task["agent_activation_plan"] = plan.as_dict()
    runtime_task["story_kind"] = plan.story_kind
    runtime_task["risk_level"] = plan.risk_level
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

    agent_policy = str(runtime_task.get("agent_policy") or "auto").strip().lower() or "auto"
    if agent_policy == "manual":
        return runtime_task
    if str(runtime_task.get("skill_mode") or "").strip():
        return runtime_task

    runtime_task["fixer_allowed"] = plan.effective_qa_mode == "qa"
    runtime_task["browser_qa_report_only"] = plan.qa_strategy == "browser" and plan.effective_qa_mode != "qa"
    runtime_task["runtime_qa_report_only"] = plan.qa_strategy == "runtime" and plan.effective_qa_mode != "qa"
    if plan.qa_strategy == "browser" and not runtime_task.get("browser_qa_mode"):
        runtime_task["browser_qa_mode"] = "quick" if plan.effective_qa_mode == "qa" else "qa_only"
    return runtime_task


def build_agent_activation_plan(task: dict[str, Any]) -> AgentActivationPlan:
    policy = _load_policy()
    file_scope = _collect_file_scope(task)

    story_kind = _classify_story_kind(file_scope, policy)
    risk_level = _classify_risk_level(task, file_scope, story_kind, policy)
    has_browser_surface = _has_browser_surface(task, file_scope, story_kind)
    requires_auth = bool(task.get("requires_auth"))
    needs_design_review = story_kind in {"ui", "mixed"} and risk_level == "high"
    needs_qa_design_review = story_kind in {"ui", "mixed"} and risk_level == "high"
    needs_design_consultation = story_kind in {"ui", "mixed"} and risk_level == "high"
    needs_ceo_review_advice = _is_advisory_enabled("plan-ceo-review", story_kind, risk_level, requires_auth, policy)

    qa_strategy = "browser" if has_browser_surface else "runtime"
    effective_qa_mode = "qa" if risk_level == "high" else str(policy["qa"].get("default_mode") or "qa-only")
    auto_upgrade_to_qa = effective_qa_mode != "qa"

    default_required_modes = [str(item).strip() for item in (policy["defaults"].get("required_modes") or []) if str(item).strip()]
    required_modes = [mode for mode in default_required_modes if mode != "qa-only"]
    qa_required_mode = "qa" if effective_qa_mode == "qa" else "qa-only"
    if qa_required_mode not in required_modes:
        required_modes.append(qa_required_mode)
    if needs_design_review and "plan-design-review" not in required_modes:
        required_modes.append("plan-design-review")
    if needs_qa_design_review and "qa-design-review" not in required_modes:
        required_modes.append("qa-design-review")

    advisory_modes: list[str] = []
    if needs_ceo_review_advice:
        advisory_modes.append("plan-ceo-review")
    if needs_design_consultation and _is_advisory_enabled("design-consultation", story_kind, risk_level, requires_auth, policy):
        advisory_modes.append("design-consultation")
    if _is_advisory_enabled("setup-browser-cookies", story_kind, risk_level, requires_auth, policy):
        advisory_modes.append("setup-browser-cookies")

    next_actions = [_next_action_for_mode(mode) for mode in advisory_modes]
    return AgentActivationPlan(
        story_kind=story_kind,
        risk_level=risk_level,
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
    )


def summarize_sprint_advice(stories: list[dict[str, Any]], *, release: bool = False) -> dict[str, Any]:
    plans = [build_agent_activation_plan(story) for story in stories]
    advisory_modes: list[str] = []
    if any(plan.needs_ceo_review_advice for plan in plans):
        advisory_modes.append("plan-ceo-review")
    if any(plan.needs_design_consultation for plan in plans):
        advisory_modes.append("design-consultation")
    if release:
        advisory_modes.append("ship")
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
    return story_kind in {"ui", "mixed"} and any(path.startswith("apps/web/") for path in file_scope)


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
        "plan-ceo-review": "Run plan-ceo-review before locking the sprint scope.",
        "design-consultation": "Run design-consultation before large UI implementation starts.",
        "setup-browser-cookies": "Prepare browser session import before authenticated QA.",
        "ship": "Run ship only after sprint acceptance is complete and release is approved.",
    }
    return messages.get(mode_id, f"Review advisory mode {mode_id}.")
