from __future__ import annotations

import unittest
from pathlib import Path

from agentsystem.agents.design_review_framework import (
    aggregate_dimension_scores,
    build_findings_from_route_scores,
    infer_route_pattern,
    resolve_route_scope,
    score_route,
    select_benchmark_profile,
)


class DesignReviewFrameworkTestCase(unittest.TestCase):
    def test_infer_route_pattern_collapses_dynamic_paths(self) -> None:
        self.assertEqual(infer_route_pattern("http://127.0.0.1:3002/"), "/")
        self.assertEqual(infer_route_pattern("http://127.0.0.1:3002/agents"), "/agents")
        self.assertEqual(infer_route_pattern("http://127.0.0.1:3002/agents/agent-01"), "/agents/[slug]")
        self.assertEqual(infer_route_pattern("http://127.0.0.1:3002/sprint-2"), "/sprint-2")
        self.assertEqual(infer_route_pattern("https://www.toolify.ai/"), "/_external")

    def test_resolve_route_scope_prefers_browser_urls_when_no_explicit_scope(self) -> None:
        scope = resolve_route_scope(
            {
                "browser_urls": [
                    "http://127.0.0.1:3002/",
                    "http://127.0.0.1:3002/agents",
                    "http://127.0.0.1:3002/agents/agent-01",
                ]
            },
            Path("D:/tmp/repo"),
        )
        self.assertEqual(scope, ["/", "/agents", "/agents/[slug]"])

    def test_score_route_returns_strong_score_for_dense_listing_surface(self) -> None:
        benchmark = select_benchmark_profile("toolify_directory", ["/agents"])
        listing_observations = [
            {
                "final_url": "http://127.0.0.1:3002/agents",
                "viewport_name": "desktop",
                "search_present": True,
                "filter_labels": ["Industry", "Pricing"],
                "category_labels": ["Finance", "Ops"],
                "stat_blocks": ["128 agents"],
                "sponsor_labels": ["Featured"],
                "card_count": 18,
                "headings": ["Browse by fit", "Find agents by task"],
                "cta_labels": ["Open profile", "Submit request", "Sort"],
                "nav_items": ["Products", "Categories", "Ranking", "Submit"],
                "title": "Agent Directory",
            },
            {
                "final_url": "http://127.0.0.1:3002/agents",
                "viewport_name": "mobile",
                "search_present": True,
                "filter_labels": ["Industry"],
                "category_labels": ["Finance"],
                "stat_blocks": ["128 agents"],
                "sponsor_labels": [],
                "card_count": 16,
                "headings": ["Find agents", "Most practical right now", "Featured rows"],
                "cta_labels": ["Open profile", "Submit request", "Sort"],
                "nav_items": ["Products", "Categories", "Ranking", "Submit"],
                "title": "Agent Directory",
            },
        ]
        route_score = score_route(
            "/agents",
            benchmark,
            current_observations=listing_observations,
            reference_observations=[],
            design_contract="# DESIGN\n## Route /agents\nloading empty partial error success\n",
        )

        self.assertGreaterEqual(route_score["dimensions"]["information_architecture"]["score"], 8)
        self.assertGreaterEqual(route_score["dimensions"]["responsive_accessibility"]["score"], 8)

    def test_score_route_uses_reference_bundle_for_journey_scoring(self) -> None:
        benchmark = select_benchmark_profile("toolify_directory", ["/request"])
        request_observations = [
            {
                "final_url": "http://127.0.0.1:3002/request",
                "viewport_name": "desktop",
                "search_present": False,
                "filter_labels": [],
                "category_labels": [],
                "stat_blocks": ["48h turnaround"],
                "sponsor_labels": [],
                "card_count": 10,
                "headings": ["Submit the workflow", "What happens next", "What we need"],
                "cta_labels": ["Compare catalog first", "View a ranked example", "Read the selection guide"],
                "nav_items": ["Products", "Categories", "Rankings", "Guides", "Submit"],
                "title": "Request shortlist",
            }
        ]
        reference_observations = [
            {
                "final_url": "https://www.toolify.ai/",
                "viewport_name": "desktop",
                "search_present": True,
                "filter_labels": [],
                "category_labels": ["Category"],
                "stat_blocks": ["100K"],
                "sponsor_labels": ["Featured"],
                "card_count": 20,
                "headings": ["Find AI tools", "Top tools"],
                "cta_labels": ["Browse", "Submit", "Read more"],
                "nav_items": ["Products", "Categories", "Rankings", "Submit"],
                "title": "Toolify",
            }
        ]

        route_score = score_route(
            "/request",
            benchmark,
            current_observations=request_observations,
            reference_observations=reference_observations,
            design_contract="# DESIGN\n## Route /request\nloading empty partial error success\n",
        )

        self.assertGreaterEqual(route_score["dimensions"]["user_journey_emotional_arc"]["score"], 8)

    def test_selects_finahunt_research_cockpit_for_sprint_routes(self) -> None:
        benchmark = select_benchmark_profile(None, ["/", "/sprint-2"])
        self.assertEqual(benchmark["id"], "finahunt_research_cockpit")

    def test_score_route_returns_strong_score_for_finahunt_workbench(self) -> None:
        benchmark = select_benchmark_profile("finahunt_research_cockpit", ["/sprint-2"])
        workbench_observations = [
            {
                "final_url": "http://127.0.0.1:3004/sprint-2",
                "viewport_name": "desktop",
                "search_present": False,
                "filter_labels": [],
                "category_labels": [],
                "stat_blocks": ["8 themes", "4 runs"],
                "sponsor_labels": [],
                "view_controls": ["全景视图", "发酵主题", "对照视图"],
                "matrix_headers": ["主题", "阶段", "发酵"],
                "risk_labels": ["统一风险提示", "研究边界"],
                "evidence_labels": ["关键证据", "证据带"],
                "refresh_state": "idle",
                "refresh_present": True,
                "matrix_present": True,
                "risk_present": True,
                "evidence_present": True,
                "card_count": 18,
                "headings": ["研究工作台", "主线发酵主题", "低位研究机会"],
                "cta_labels": ["返回首页", "切换日期", "立即抓最新", "全景视图"],
                "nav_items": ["首页", "Sprint 2 工作台", "今日入口", "研究方法"],
                "title": "Finahunt Sprint 2",
            },
            {
                "final_url": "http://127.0.0.1:3004/sprint-2",
                "viewport_name": "mobile",
                "search_present": False,
                "filter_labels": [],
                "category_labels": [],
                "stat_blocks": ["8 themes"],
                "sponsor_labels": [],
                "view_controls": ["全景视图", "发酵主题"],
                "matrix_headers": ["主题", "阶段"],
                "risk_labels": ["统一风险提示"],
                "evidence_labels": ["关键证据"],
                "refresh_state": "idle",
                "refresh_present": True,
                "matrix_present": True,
                "risk_present": True,
                "evidence_present": True,
                "card_count": 14,
                "headings": ["研究工作台", "主线发酵主题"],
                "cta_labels": ["返回首页", "立即抓最新", "发酵主题"],
                "nav_items": ["首页", "Sprint 2 工作台", "今日入口", "研究方法"],
                "title": "Finahunt Sprint 2",
            },
        ]

        route_score = score_route(
            "/sprint-2",
            benchmark,
            current_observations=workbench_observations,
            reference_observations=[],
            design_contract="# DESIGN\n## Route /sprint-2\nloading empty partial error success\n",
        )

        self.assertGreaterEqual(route_score["dimensions"]["information_architecture"]["score"], 9)
        self.assertGreaterEqual(route_score["dimensions"]["design_system_alignment"]["score"], 9)
        self.assertGreaterEqual(route_score["dimensions"]["responsive_accessibility"]["score"], 9)

    def test_build_findings_uses_route_specific_primary_file_mapping(self) -> None:
        route_scores = [
            {
                "route": "/agents",
                "dimensions": {
                    "information_architecture": {
                        "score": 6,
                        "gap": "Needs stronger results hierarchy.",
                        "ten_outcome": "Listing is easy to scan.",
                        "spec_fix": "Tighten the results toolbar and filters.",
                    }
                },
            }
        ]
        for dimension in (
            "interaction_state_coverage",
            "user_journey_emotional_arc",
            "ai_slop_risk",
            "design_system_alignment",
            "responsive_accessibility",
            "unresolved_design_decisions",
        ):
            route_scores[0]["dimensions"][dimension] = {
                "score": 8,
                "gap": "ok",
                "ten_outcome": "ok",
                "spec_fix": "ok",
            }

        findings = build_findings_from_route_scores(
            route_scores,
            ["apps/web/src/app/page.tsx", "apps/web/src/app/agents/page.tsx"],
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["file_path"], "apps/web/src/app/agents/page.tsx")

    def test_aggregate_dimension_scores_uses_lowest_route_score(self) -> None:
        route_scores = [
            {
                "route": "/",
                "dimensions": {
                    "information_architecture": {"score": 9, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "interaction_state_coverage": {"score": 8, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "user_journey_emotional_arc": {"score": 8, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "ai_slop_risk": {"score": 9, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "design_system_alignment": {"score": 9, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "responsive_accessibility": {"score": 8, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "unresolved_design_decisions": {"score": 8, "gap": "home ok", "ten_outcome": "ok", "spec_fix": "ok"},
                },
            },
            {
                "route": "/agents",
                "dimensions": {
                    "information_architecture": {"score": 7, "gap": "listing weak", "ten_outcome": "ok", "spec_fix": "fix listing"},
                    "interaction_state_coverage": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "user_journey_emotional_arc": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "ai_slop_risk": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "design_system_alignment": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "responsive_accessibility": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                    "unresolved_design_decisions": {"score": 8, "gap": "listing ok", "ten_outcome": "ok", "spec_fix": "ok"},
                },
            },
        ]

        overall = aggregate_dimension_scores(route_scores)
        self.assertEqual(overall["information_architecture"]["score"], 7)
        self.assertIn("/agents", overall["information_architecture"]["gap"])


if __name__ == "__main__":
    unittest.main()
