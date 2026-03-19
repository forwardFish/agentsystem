from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DIMENSIONS: tuple[str, ...] = (
    "information_architecture",
    "interaction_state_coverage",
    "user_journey_emotional_arc",
    "ai_slop_risk",
    "design_system_alignment",
    "responsive_accessibility",
    "unresolved_design_decisions",
)

STATE_KEYWORDS: tuple[str, ...] = ("loading", "empty", "partial", "error", "success")

AGENTHIRE_ROUTE_SCOPE: tuple[str, ...] = (
    "/",
    "/agents",
    "/agents/[slug]",
    "/request",
    "/content/[slug]",
)

FINAHUNT_ROUTE_SCOPE: tuple[str, ...] = (
    "/",
    "/sprint-2",
)

BENCHMARK_PROFILES: dict[str, dict[str, Any]] = {
    "toolify_directory": {
        "label": "Toolify-style directory",
        "fonts": {"heading": "Sora", "body": "Manrope"},
        "requires_reference": True,
        "colors": {
            "background": "#f6f8fc",
            "surface": "#ffffff",
            "accent_primary": "#3478ff",
            "accent_secondary": "#6f68ff",
            "accent_support": "#1abf91",
            "ink": "#162238",
        },
        "density": "high",
        "direction": [
            "Prefer directory rhythm over landing-page storytelling.",
            "Front-load search, ranking, categories, and next actions.",
            "Use compact cards, visible filters, and dense browse surfaces.",
        ],
        "modules": {
            "home": [
                "sticky marketplace navigation",
                "search-first hero",
                "trust stats or proof strip",
                "featured ranking list",
                "sidebar recommendation rail",
                "dense tool grid",
                "category entry grid",
                "guide and article strip",
                "request bridge CTA",
            ],
            "listing": [
                "filters and categories rail",
                "results toolbar",
                "dense result stream",
                "featured rows or pinned picks",
                "sort and next-action affordances",
            ],
            "detail": [
                "hero summary with pricing or fit tags",
                "proof or preview block",
                "fit and evaluation grid",
                "use cases and decision notes",
                "related items or next-step rail",
            ],
            "request": [
                "request hero",
                "trust and process rail",
                "required-input explanation",
                "examples and expectations",
                "submission CTA",
            ],
            "article": [
                "article hero",
                "summary or picks rail",
                "comparison framework",
                "body sections",
                "browse or request CTA bridge",
            ],
            "dashboard": [
                "workspace header",
                "command or search surface",
                "status strip",
                "primary decision panels",
                "activity or alerts rail",
            ],
            "generic": [
                "clear page header",
                "primary content module",
                "supporting proof or summary",
                "next-step CTA",
            ],
        },
        "signals": {
            "home": {"search": True, "categories": True, "stats": True, "cards": True, "cta": True},
            "listing": {"search": True, "filters": True, "categories": True, "cards": True, "cta": True},
            "detail": {"cards": True, "cta": True},
            "request": {"cards": True, "cta": True},
            "article": {"cards": True, "cta": True},
            "dashboard": {"stats": True, "cards": True, "cta": True, "views": True},
            "generic": {"cards": True, "cta": True},
        },
    },
    "product_directory": {
        "label": "Generic product directory",
        "fonts": {"heading": "Sora", "body": "Manrope"},
        "requires_reference": True,
        "colors": {
            "background": "#f7fafc",
            "surface": "#ffffff",
            "accent_primary": "#2563eb",
            "accent_secondary": "#0ea5e9",
            "accent_support": "#10b981",
            "ink": "#0f172a",
        },
        "density": "medium-high",
        "direction": [
            "Make comparison fast and obvious.",
            "Keep browse, evaluate, and act within one visual system.",
        ],
        "modules": {},
        "signals": {
            "home": {"stats": True, "cards": True, "cta": True},
            "listing": {"search": True, "filters": True, "cards": True, "cta": True},
            "detail": {"cards": True, "cta": True},
            "request": {"cards": True, "cta": True},
            "article": {"cards": True, "cta": True},
            "generic": {"cards": True, "cta": True},
        },
    },
    "dashboard_surface": {
        "label": "Product dashboard surface",
        "fonts": {"heading": "Sora", "body": "Manrope"},
        "requires_reference": False,
        "colors": {
            "background": "#f8fafc",
            "surface": "#ffffff",
            "accent_primary": "#2563eb",
            "accent_secondary": "#0891b2",
            "accent_support": "#16a34a",
            "ink": "#111827",
        },
        "density": "medium",
        "direction": [
            "Expose command context quickly.",
            "Balance summary density with operational clarity.",
        ],
        "modules": {
            "dashboard": [
                "workspace header",
                "query or command bar",
                "decision metrics",
                "main panels",
                "alerts or recent activity rail",
            ],
        },
        "signals": {
            "dashboard": {"stats": True, "cards": True, "cta": True, "views": True, "matrix": True},
            "home": {"stats": True, "cards": True, "cta": True},
        },
    },
    "finahunt_research_cockpit": {
        "label": "Finahunt research cockpit",
        "fonts": {"heading": "Space Grotesk", "body": "IBM Plex Sans"},
        "requires_reference": False,
        "colors": {
            "background": "#07111f",
            "surface": "#0c1b2f",
            "accent_primary": "#58d5ff",
            "accent_secondary": "#99ffbe",
            "accent_support": "#ffd36a",
            "ink": "#e9f4ff",
        },
        "density": "medium-high",
        "direction": [
            "Lead with the daily decision, then the research evidence.",
            "Keep the home route product-facing and the sprint route operator-facing within one system.",
            "Use strong hierarchy between hero, decision strip, workbench sections, evidence, and risk boundary.",
        ],
        "modules": {
            "home": [
                "product thesis hero",
                "date and refresh control rail",
                "today focus summary",
                "runtime and source overview",
                "theme and event entry cards",
                "workbench bridge CTA",
            ],
            "dashboard": [
                "research cockpit hero",
                "view mode controls",
                "decision strip",
                "fermentation board",
                "low-position research board",
                "matrix and evidence views",
                "risk and methodology boundary",
            ],
        },
        "signals": {
            "home": {"stats": True, "cards": True, "cta": True, "risk": True, "refresh": True, "evidence": True},
            "dashboard": {
                "stats": True,
                "cards": True,
                "cta": True,
                "views": True,
                "matrix": True,
                "risk": True,
                "evidence": True,
                "refresh": True,
            },
            "generic": {"cards": True, "cta": True},
        },
    },
}


def select_benchmark_profile(name: str | None, route_scope: list[str] | None = None) -> dict[str, Any]:
    normalized = str(name or "").strip().lower()
    if normalized in BENCHMARK_PROFILES:
        profile = dict(BENCHMARK_PROFILES[normalized])
        profile["id"] = normalized
        return profile

    scope = route_scope or []
    if any(route.startswith("/sprint-") for route in scope):
        profile = dict(BENCHMARK_PROFILES["finahunt_research_cockpit"])
        profile["id"] = "finahunt_research_cockpit"
        return profile
    if any("dashboard" in route or "admin" in route for route in scope):
        profile = dict(BENCHMARK_PROFILES["dashboard_surface"])
        profile["id"] = "dashboard_surface"
        return profile

    profile = dict(BENCHMARK_PROFILES["product_directory"])
    profile["id"] = "product_directory"
    return profile


def resolve_route_scope(
    task_payload: dict[str, Any],
    repo_b_path: Path,
    observations: list[dict[str, Any]] | None = None,
) -> list[str]:
    raw_scope = task_payload.get("route_scope")
    if isinstance(raw_scope, list):
        cleaned = _unique_preserve_order(str(item).strip() for item in raw_scope if str(item).strip())
        if cleaned:
            return cleaned

    candidate_urls: list[str] = []
    for key in ("browser_urls", "qa_urls", "preview_urls", "runtime_urls", "reference_urls"):
        value = task_payload.get(key)
        if isinstance(value, str) and value.strip():
            candidate_urls.append(value.strip())
        elif isinstance(value, list):
            candidate_urls.extend(str(item).strip() for item in value if str(item).strip())

    if candidate_urls:
        inferred = _unique_preserve_order(infer_route_pattern(url) for url in candidate_urls if url)
        current_only = [route for route in inferred if route != "/_external"]
        if current_only:
            return current_only

    observation_urls = [
        str(item.get("final_url") or item.get("url") or "").strip()
        for item in (observations or [])
        if str(item.get("final_url") or item.get("url") or "").strip()
    ]
    if observation_urls:
        inferred = _unique_preserve_order(infer_route_pattern(url) for url in observation_urls)
        current_only = [route for route in inferred if route != "/_external"]
        if current_only:
            return current_only

    if str(task_payload.get("project") or repo_b_path.name).strip().lower() == "agenthire":
        return list(AGENTHIRE_ROUTE_SCOPE)
    if str(task_payload.get("project") or repo_b_path.name).strip().lower() == "finahunt":
        return list(FINAHUNT_ROUTE_SCOPE)
    return ["/"]


def infer_route_pattern(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.netloc.startswith("127.0.0.1"):
        if "localhost" not in parsed.netloc:
            return "/_external"

    return _infer_path_pattern(parsed.path)


def infer_reference_route_pattern(url: str) -> str:
    parsed = urlparse(url)
    return _infer_path_pattern(parsed.path)


def _infer_path_pattern(path_value: str) -> str:
    path = path_value.strip("/")
    if not path:
        return "/"

    segments = [segment for segment in path.split("/") if segment]
    first = segments[0].lower()

    if first in {"content", "blog", "article", "articles", "guides"} and len(segments) > 1:
        return f"/{first}/[slug]"
    if first in {"agents", "tools", "apps", "products", "catalog", "directory"} and len(segments) > 1:
        return f"/{first}/[slug]"
    if first in {"request", "submit", "contact", "signup"}:
        return f"/{first}"
    if first in {"dashboard", "admin"}:
        return f"/{first}"
    if len(segments) == 1:
        return f"/{first}"
    return f"/{first}/[slug]"


def classify_route_kind(route: str) -> str:
    normalized = route.strip() or "/"
    if normalized == "/":
        return "home"
    if normalized.endswith("/[slug]") and any(token in normalized for token in ("/content", "/blog", "/article", "/guides")):
        return "article"
    if normalized.endswith("/[slug]"):
        return "detail"
    if any(token in normalized for token in ("/request", "/submit", "/contact", "/signup")):
        return "request"
    if normalized.startswith("/sprint-") or any(token in normalized for token in ("/dashboard", "/admin", "/workbench", "/research")):
        return "dashboard"
    if any(token in normalized for token in ("/agents", "/tools", "/apps", "/products", "/catalog", "/directory", "/browse")):
        return "listing"
    return "generic"


def build_route_blueprint(route: str, benchmark: dict[str, Any]) -> dict[str, Any]:
    route_kind = classify_route_kind(route)
    modules = benchmark.get("modules", {}).get(route_kind) or BENCHMARK_PROFILES["product_directory"]["modules"].get(route_kind) or BENCHMARK_PROFILES["product_directory"]["modules"].get("generic") or [
        "clear page header",
        "primary content module",
        "supporting proof or summary",
        "next-step CTA",
    ]
    return {
        "route": route,
        "route_kind": route_kind,
        "intent": route_intent(route_kind),
        "modules": modules,
        "expected_signals": expected_signals(route_kind, benchmark),
    }


def route_intent(route_kind: str) -> str:
    intents = {
        "home": "Help a first-time visitor understand the product, search quickly, and enter a discovery flow.",
        "listing": "Help the user compare options fast with visible filters, ranking cues, and a clear next click.",
        "detail": "Let the user decide whether this item fits them without needing to scan the full page.",
        "request": "Turn unmet browse intent into a clear structured submission path.",
        "article": "Make editorial content support discovery instead of feeling disconnected from the product.",
        "dashboard": "Expose the operational picture quickly and make the next decision obvious.",
        "generic": "Explain the page clearly, support the core action, and leave a visible next step.",
    }
    return intents.get(route_kind, intents["generic"])


def expected_signals(route_kind: str, benchmark: dict[str, Any] | None = None) -> dict[str, bool]:
    defaults = {
        "search": route_kind in {"home", "listing"},
        "filters": route_kind == "listing",
        "categories": route_kind in {"home", "listing"},
        "stats": route_kind in {"home", "dashboard"},
        "cards": route_kind in {"home", "listing", "detail", "article", "dashboard"},
        "cta": True,
        "views": route_kind == "dashboard",
        "matrix": route_kind == "dashboard",
        "risk": route_kind in {"home", "dashboard"},
        "evidence": route_kind in {"home", "dashboard", "article"},
        "refresh": route_kind == "dashboard",
    }
    signal_overrides = (benchmark or {}).get("signals", {}).get(route_kind)
    if signal_overrides:
        defaults.update(signal_overrides)
    return defaults


def summarize_route_observations(
    route: str,
    current_observations: list[dict[str, Any]],
    reference_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    current = match_route_observations(current_observations, route)
    reference = match_route_observations(reference_observations, route, allow_kind_match=True)
    card_counts = [int(item.get("card_count") or 0) for item in current]
    return {
        "current_count": len(current),
        "reference_count": len(reference),
        "reference_bundle_present": bool(reference_observations),
        "has_mobile": any(str(item.get("viewport_name") or "") == "mobile" for item in current),
        "search_present": any(bool(item.get("search_present")) for item in current),
        "filters_present": any(len(item.get("filter_labels") or []) > 0 for item in current),
        "categories_present": any(len(item.get("category_labels") or []) > 0 for item in current),
        "stats_present": any(len(item.get("stat_blocks") or []) > 0 for item in current),
        "sponsor_present": any(len(item.get("sponsor_labels") or []) > 0 for item in current),
        "view_controls_present": any(len(item.get("view_controls") or []) > 0 for item in current),
        "matrix_present": any(bool(item.get("matrix_present")) for item in current),
        "risk_present": any(bool(item.get("risk_present")) for item in current),
        "evidence_present": any(bool(item.get("evidence_present")) for item in current),
        "refresh_present": any(bool(item.get("refresh_present")) for item in current),
        "avg_cards": int(sum(card_counts) / len(card_counts)) if card_counts else 0,
        "max_cards": max(card_counts) if card_counts else 0,
        "max_heading_count": max((len(item.get("headings") or []) for item in current), default=0),
        "max_cta_count": max((len(item.get("cta_labels") or []) for item in current), default=0),
        "max_nav_count": max((len(item.get("nav_items") or []) for item in current), default=0),
        "title_present": any(bool(str(item.get("title") or "").strip()) for item in current),
        "current_observations": current,
        "reference_observations": reference,
    }


def match_route_observations(
    observations: list[dict[str, Any]],
    route: str,
    *,
    allow_kind_match: bool = False,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    target_kind = classify_route_kind(route)
    for item in observations:
        raw_url = str(item.get("final_url") or item.get("url") or "")
        candidate = infer_route_pattern(raw_url)
        if candidate == route:
            matches.append(item)
            continue
        if not allow_kind_match:
            continue
        reference_candidate = infer_reference_route_pattern(raw_url)
        if classify_route_kind(reference_candidate) == target_kind:
            matches.append(item)
    return matches


def score_route(
    route: str,
    benchmark: dict[str, Any],
    current_observations: list[dict[str, Any]],
    reference_observations: list[dict[str, Any]],
    design_contract: str = "",
    review_mode: str = "auto",
) -> dict[str, Any]:
    blueprint = build_route_blueprint(route, benchmark)
    metrics = summarize_route_observations(route, current_observations, reference_observations)
    route_kind = blueprint["route_kind"]
    expected = blueprint["expected_signals"]
    design_contract_lower = design_contract.lower()
    route_present_in_contract = route.lower() in design_contract_lower or route_kind in design_contract_lower
    state_hits = sum(1 for keyword in STATE_KEYWORDS if keyword in design_contract_lower)

    signal_checks = {
        "search": (not expected["search"]) or metrics["search_present"],
        "filters": (not expected["filters"]) or metrics["filters_present"],
        "categories": (not expected["categories"]) or metrics["categories_present"],
        "stats": (not expected["stats"]) or metrics["stats_present"],
        "cards": (not expected["cards"]) or metrics["avg_cards"] >= 3,
        "cta": (not expected["cta"]) or metrics["max_cta_count"] >= 2,
        "views": (not expected["views"]) or metrics["view_controls_present"],
        "matrix": (not expected["matrix"]) or metrics["matrix_present"],
        "risk": (not expected["risk"]) or metrics["risk_present"],
        "evidence": (not expected["evidence"]) or metrics["evidence_present"],
        "refresh": (not expected["refresh"]) or metrics["refresh_present"],
    }
    missing_signals = [name for name, passed in signal_checks.items() if not passed]
    matched_count = sum(1 for passed in signal_checks.values() if passed)
    signal_score = int(round((matched_count / max(len(signal_checks), 1)) * 4))
    reference_bonus = 1 if metrics["reference_count"] > 0 or metrics["reference_bundle_present"] or not benchmark.get("requires_reference", True) else 0
    mobile_bonus = 1 if metrics["has_mobile"] else 0
    contract_bonus = 1 if route_present_in_contract else 0
    heading_bonus = 1 if metrics["max_heading_count"] >= 3 else 0

    dimensions = {
        "information_architecture": _dimension(
            4 + signal_score + heading_bonus + (1 if metrics["max_nav_count"] >= 4 else 0),
            _gap_for_information_architecture(route, missing_signals, metrics),
            f"{route} opens with a clear hierarchy: purpose, browse affordance, proof, and next action all land above the fold.",
            f"Clarify the module order for {route}: {' -> '.join(blueprint['modules'])}.",
        ),
        "interaction_state_coverage": _dimension(
            4 + min(state_hits, 4) + contract_bonus,
            _gap_for_state_coverage(route_present_in_contract, state_hits),
            f"{route} explicitly covers loading, empty, partial, error, and success states in both contract and UI.",
            f"Expand DESIGN.md with route-specific state rules for {route}.",
        ),
        "user_journey_emotional_arc": _dimension(
            4 + (1 if metrics["max_nav_count"] >= 4 else 0) + (1 if metrics["max_cta_count"] >= 3 else 0) + contract_bonus + reference_bonus,
            _gap_for_journey(metrics),
            f"{route} feels like part of one continuous discovery-to-action journey.",
            f"Strengthen cross-page next actions and recovery paths around {route}.",
        ),
        "ai_slop_risk": _dimension(
            3 + min(metrics["avg_cards"] // 3, 3) + heading_bonus + reference_bonus + (1 if len(missing_signals) <= 1 else 0),
            _gap_for_ai_slop(metrics, missing_signals),
            f"{route} reads like a real product surface with intentional hierarchy and non-generic density.",
            f"Increase module contrast, density discipline, and ranking or recommendation emphasis on {route}.",
        ),
        "design_system_alignment": _dimension(
            5 + contract_bonus + reference_bonus + (1 if metrics["title_present"] else 0) + (1 if metrics["max_nav_count"] >= 4 else 0),
            _gap_for_design_system(route_present_in_contract, metrics["title_present"]),
            f"{route} clearly follows the same visual language as the rest of the product.",
            f"Lock typography, CTA rules, and card grammar for {route} into DESIGN.md and the implementation.",
        ),
        "responsive_accessibility": _dimension(
            5 + mobile_bonus + (1 if metrics["title_present"] else 0) + (1 if metrics["max_heading_count"] >= 2 else 0) + contract_bonus,
            _gap_for_responsive(metrics["has_mobile"], metrics["title_present"]),
            f"{route} keeps its hierarchy intact on desktop and mobile and preserves accessible structure.",
            f"Capture mobile evidence and retain strong heading/focus hierarchy on {route}.",
        ),
        "unresolved_design_decisions": _dimension(
            4 + contract_bonus + reference_bonus + (1 if review_mode == "auto" else 0) + min(state_hits, 3),
            _gap_for_decisions(route_present_in_contract, review_mode),
            f"{route} has locked module order, states, CTA rules, and review assumptions.",
            f"Write the remaining route assumptions and open design choices for {route} into DESIGN.md.",
        ),
    }

    return {
        "route": route,
        "route_kind": route_kind,
        "intent": blueprint["intent"],
        "modules": blueprint["modules"],
        "metrics": {
            key: value
            for key, value in metrics.items()
            if key not in {"current_observations", "reference_observations"}
        },
        "dimensions": dimensions,
        "missing_signals": missing_signals,
    }


def aggregate_dimension_scores(route_scores: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    overall: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        if not route_scores:
            overall[dimension] = _dimension(
                0,
                "No route evidence was available.",
                "Every reviewed route has evidence and a passing score.",
                "Add route coverage before trusting the design review.",
            )
            continue
        ordered = sorted(
            (
                {
                    "route": route_score["route"],
                    **route_score["dimensions"][dimension],
                }
                for route_score in route_scores
            ),
            key=lambda item: int(item["score"]),
        )
        lowest = ordered[0]
        affected_routes = [item["route"] for item in ordered if int(item["score"]) == int(lowest["score"])]
        overall[dimension] = {
            "score": int(lowest["score"]),
            "gap": f"Lowest-scoring route(s): {', '.join(affected_routes)}. {lowest['gap']}",
            "ten_outcome": lowest["ten_outcome"],
            "spec_fix": lowest["spec_fix"],
        }
    return overall


def build_findings_from_route_scores(
    route_scores: list[dict[str, Any]],
    primary_files: list[str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for route_score in route_scores:
        route = route_score["route"]
        for dimension, detail in route_score["dimensions"].items():
            score = int(detail["score"])
            if score >= 8:
                continue
            findings.append(
                {
                    "severity": "blocking" if score <= 6 else "important",
                    "route": route,
                    "title": f"{route} / {dimension} below threshold",
                    "description": detail["gap"],
                    "spec_fix": detail["spec_fix"],
                    "ten_outcome": detail["ten_outcome"],
                    "file_path": match_primary_file_for_route(route, primary_files),
                }
            )
    return findings


def match_primary_file_for_route(route: str, primary_files: list[str]) -> str:
    mapping = {
        "/": "page.tsx",
        "/agents": "agents/page.tsx",
        "/agents/[slug]": "agents/[slug]/page.tsx",
        "/request": "request/page.tsx",
        "/content/[slug]": "content/[slug]/page.tsx",
        "/sprint-2": "sprint-2/page.tsx",
        "/admin": "admin/page.tsx",
        "/dashboard": "dashboard",
    }
    target = mapping.get(route, "")
    for file_path in primary_files:
        normalized = file_path.replace("\\", "/")
        if target and target in normalized:
            return file_path
    return primary_files[0] if primary_files else ""


def build_design_contract(
    benchmark: dict[str, Any],
    route_scores: list[dict[str, Any]],
    assumptions: list[str],
) -> str:
    lines = [
        "# DESIGN",
        "",
        "## Benchmark",
        f"- Profile: {benchmark['label']}",
        f"- Heading font: {benchmark['fonts']['heading']}",
        f"- Body font: {benchmark['fonts']['body']}",
        f"- Background: {benchmark['colors']['background']}",
        f"- Surface: {benchmark['colors']['surface']}",
        f"- Accent primary: {benchmark['colors']['accent_primary']}",
        f"- Accent secondary: {benchmark['colors']['accent_secondary']}",
        "",
        "## Global Direction",
        *[f"- {item}" for item in benchmark.get("direction", [])],
        "",
        "## Required State Model",
        "- Every reviewed route should define loading, empty, partial, error, and success behavior.",
        "- The first viewport should explain the page purpose and expose a primary next action.",
        "- Desktop and mobile should preserve the same information hierarchy.",
        "",
        "## Assumptions",
        "## Route Contracts",
    ]

    if assumptions:
        lines.extend(f"- {item}" for item in assumptions)
    else:
        lines.append("- None.")
    lines.extend(["", "## Route Contracts"])

    for route_score in route_scores:
        lines.extend(
            [
                "",
                f"### {route_score['route']}",
                f"- Intent: {route_score['intent']}",
                f"- Route kind: {route_score['route_kind']}",
                "- Module order:",
                *[f"  - {module}" for module in route_score["modules"]],
                "- Required states: loading / empty / partial / error / success",
                "- Notes:",
                f"  - Keep {route_score['dimensions']['information_architecture']['ten_outcome']}",
                f"  - Keep {route_score['dimensions']['user_journey_emotional_arc']['ten_outcome']}",
                f"  - Keep {route_score['dimensions']['responsive_accessibility']['ten_outcome']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Accessibility Rules",
            "- Preserve a meaningful heading order on every route.",
            "- Do not rely on color alone for status or category meaning.",
            "- Keep clear keyboard focus states for interactive elements.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _gap_for_information_architecture(route: str, missing_signals: list[str], metrics: dict[str, Any]) -> str:
    if not metrics["current_count"]:
        return f"{route} has no current-surface evidence yet."
    if missing_signals:
        return f"{route} is missing key browse signals: {', '.join(missing_signals)}."
    return f"{route} still needs clearer above-the-fold hierarchy."


def _gap_for_state_coverage(route_present_in_contract: bool, state_hits: int) -> str:
    if not route_present_in_contract:
        return "The route is not explicitly covered in DESIGN.md yet."
    if state_hits < 5:
        return "The design contract still under-specifies loading, empty, partial, error, and success states."
    return "State handling is present but could still be more explicit in the implementation."


def _gap_for_journey(metrics: dict[str, Any]) -> str:
    if metrics["max_cta_count"] < 2:
        return "The page does not present enough clear next actions."
    if metrics["max_nav_count"] < 4:
        return "The page still feels too isolated from the rest of the product journey."
    return "The route needs stronger cross-page continuity."


def _gap_for_ai_slop(metrics: dict[str, Any], missing_signals: list[str]) -> str:
    if metrics["avg_cards"] < 3:
        return "The page still reads like a sparse template instead of a real product surface."
    if missing_signals:
        return f"The page still misses structural signals that prevent generic template feel: {', '.join(missing_signals)}."
    return "The hierarchy is better, but visual intent can still feel too generic."


def _gap_for_design_system(route_present_in_contract: bool, title_present: bool) -> str:
    if not route_present_in_contract:
        return "The shared design system is not fully locked into the contract yet."
    if not title_present:
        return "The route is missing basic metadata polish such as a stable title."
    return "Shared visual rules exist, but they can still be enforced more consistently."


def _gap_for_responsive(has_mobile: bool, title_present: bool) -> str:
    if not has_mobile:
        return "There is no mobile evidence for this route yet."
    if not title_present:
        return "The route needs stronger structural semantics and metadata discipline."
    return "Responsive behavior is present, but can still be tightened."


def _gap_for_decisions(route_present_in_contract: bool, review_mode: str) -> str:
    if not route_present_in_contract:
        return "The route contract is still incomplete."
    if review_mode != "auto":
        return "Some design choices are still waiting for review-mode decisions."
    return "Most decisions are locked, but remaining assumptions should be written down more explicitly."


def _dimension(score: int, gap: str, ten_outcome: str, spec_fix: str) -> dict[str, Any]:
    return {
        "score": max(0, min(10, int(score))),
        "gap": gap,
        "ten_outcome": ten_outcome,
        "spec_fix": spec_fix,
    }


def _unique_preserve_order(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
