from __future__ import annotations

import unittest
from pathlib import Path

from agentsystem.orchestration.agent_activation_resolver import apply_agent_activation_policy, build_agent_activation_plan
from agentsystem.orchestration.workflow_admission import build_story_admission


class AgentActivationResolverTestCase(unittest.TestCase):
    def test_high_risk_ui_story_enables_design_and_qa_upgrade(self) -> None:
        plan = build_agent_activation_plan(
            {
                "blast_radius": "L3",
                "primary_files": ["apps/web/src/app/dashboard/page.tsx"],
                "related_files": ["apps/web/src/app/dashboard/page.tsx", "apps/web/src/app/dashboard/styles.css"],
            }
        )

        self.assertEqual(plan.story_kind, "ui")
        self.assertEqual(plan.risk_level, "high")
        self.assertEqual(plan.qa_strategy, "browser")
        self.assertEqual(plan.effective_qa_mode, "qa")
        self.assertEqual(plan.workflow_enforcement_policy, "gstack_strict")
        self.assertIn("plan-eng-review", plan.required_modes)
        self.assertIn("review", plan.required_modes)
        self.assertIn("qa", plan.required_modes)
        self.assertIn("browse", plan.required_modes)
        self.assertIn("plan-design-review", plan.required_modes)
        self.assertIn("design-review", plan.required_modes)
        self.assertIn("design-consultation", plan.required_modes)
        self.assertIn("browse", plan.mode_to_agent_map)
        self.assertIn("browser_qa", plan.expanded_required_agents)
        self.assertEqual(plan.mode_to_agent_map["plan-eng-review"], ["requirement_analysis", "architecture_review"])

    def test_runtime_story_defaults_to_runtime_qa_baseline(self) -> None:
        plan = build_agent_activation_plan(
            {
                "blast_radius": "L1",
                "primary_files": ["agents/source_registry.py"],
                "related_files": ["skills/event/fermentation.py", "tools/gate_check/validate_norms.py"],
            }
        )

        self.assertEqual(plan.story_kind, "runtime_data")
        self.assertEqual(plan.risk_level, "low")
        self.assertEqual(plan.qa_strategy, "runtime")
        self.assertEqual(plan.effective_qa_mode, "qa")
        self.assertFalse(plan.auto_upgrade_to_qa)
        self.assertIn("qa", plan.required_modes)
        self.assertNotIn("plan-design-review", plan.required_modes)

    def test_explicit_skill_mode_is_not_overridden(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L1",
                "skill_mode": "browse",
                "primary_files": ["apps/web/src/app/page.tsx"],
                "related_files": ["apps/web/src/app/page.tsx"],
            }
        )

        self.assertEqual(runtime_task["skill_mode"], "browse")
        self.assertEqual(runtime_task["story_kind"], "ui")
        self.assertEqual(runtime_task["qa_strategy"], "browser")
        self.assertNotIn("fixer_allowed", runtime_task)
        self.assertIn("implementation_contract", runtime_task)
        self.assertIn("agent_execution_contract", runtime_task)

    def test_authenticated_bugfix_injects_cookie_setup_and_parity_context(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L2",
                "goal": "Fix the authenticated dashboard regression before release.",
                "requires_auth": True,
                "primary_files": ["dashboard/static/index.html"],
                "related_files": ["dashboard/static/index.html", "src/agentsystem/dashboard/main.py"],
            }
        )

        self.assertEqual(runtime_task["workflow_enforcement_policy"], "bugfix_strict")
        self.assertEqual(runtime_task["bug_scope"], "bugfix")
        self.assertEqual(runtime_task["session_policy"], "authenticated_browser_session")
        self.assertIn("setup-browser-cookies", runtime_task["required_modes"])
        self.assertIn("investigate", runtime_task["required_modes"])
        self.assertIn("setup_browser_cookies", runtime_task["expanded_required_agents"])
        self.assertEqual(
            runtime_task["upstream_agent_parity"]["tracked_modes"]["setup-browser-cookies"]["parity_status"],
            "workflow_wired",
        )

    def test_docs_only_contract_story_only_requires_docs_artifact(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L1",
                "story_id": "E1-001",
                "primary_files": ["docs/需求文档/事件分类白名单_v0.1.md"],
                "related_files": ["docs/需求文档/事件分类白名单_v0.1.md"],
            }
        )

        self.assertEqual(runtime_task["story_kind"], "contract_schema")
        self.assertEqual(runtime_task["implementation_contract"]["story_track"], "contract_schema")
        self.assertEqual(runtime_task["required_artifact_types"], ["docs"])
        self.assertEqual(runtime_task["contract_scope_paths"], [])

    def test_api_story_infers_contract_supporting_scope_paths(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L2",
                "story_id": "E1-003",
                "primary_files": ["apps/api/src/domain/event_ingestion/service.py"],
                "related_files": [
                    "apps/api/src/domain/event_ingestion/service.py",
                    "apps/api/src/domain/event_structuring/service.py",
                    "apps/api/src/api/command/routes.py",
                ],
            }
        )

        self.assertEqual(runtime_task["implementation_contract"]["story_track"], "api_domain")
        self.assertIn("apps/api/src/schemas/event.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/src/schemas/command.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/src/settings/base.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/src/services/container.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/src/domain/theme_mapping/service.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/src/domain/event_casebook/service.py", runtime_task["contract_scope_paths"])
        self.assertIn("apps/api/tests/test_event_ingestion.py", runtime_task["contract_scope_paths"])
        self.assertIn("docs/requirements/e1_003_delivery.md", runtime_task["contract_scope_paths"])

    def test_schema_contract_story_does_not_force_database_dev_for_python_schema_module(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "blast_radius": "L2",
                "story_id": "E1-002",
                "primary_files": [
                    "docs/需求文档/Event_Structuring_字段字典.md",
                    "apps/api/src/schemas/event.py",
                ],
                "related_files": [
                    "docs/需求文档/Event_Structuring_字段字典.md",
                    "apps/api/src/schemas/event.py",
                ],
            }
        )

        self.assertEqual(runtime_task["implementation_contract"]["story_track"], "contract_schema")
        self.assertFalse(runtime_task["implementation_contract"]["requires_database_dev"])
        self.assertNotIn("database_dev", runtime_task["expanded_required_agents"])

    def test_story_admission_is_idempotent_for_pre_enriched_api_story_scope(self) -> None:
        runtime_task = apply_agent_activation_policy(
            {
                "project": "versefina",
                "blast_radius": "L2",
                "story_id": "E1-003",
                "goal": "Implement event ingestion and structuring",
                "acceptance_criteria": ["POST /api/v1/events exists"],
                "primary_files": ["apps/api/src/domain/event_ingestion/service.py"],
                "related_files": [
                    "apps/api/src/domain/event_ingestion/service.py",
                    "apps/api/src/domain/event_structuring/service.py",
                    "apps/api/src/api/command/routes.py",
                ],
            }
        )

        admission = build_story_admission(runtime_task, Path("d:/lyh/agent/agent-frame/versefina"))
        contract_scope_paths = admission["task_payload"].get("contract_scope_paths") or []

        self.assertIn("apps/api/src/schemas/command.py", contract_scope_paths)
        self.assertIn("apps/api/src/settings/base.py", contract_scope_paths)
        self.assertNotIn("apps/api/src/api/query/routes.py", contract_scope_paths)


if __name__ == "__main__":
    unittest.main()
