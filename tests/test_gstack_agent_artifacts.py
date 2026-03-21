from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git import Repo

from agentsystem.agents.architecture_review_agent import architecture_review_node
from agentsystem.agents.document_release_agent import document_release_node
from agentsystem.agents.investigate_agent import investigate_node
from agentsystem.agents.office_hours_agent import office_hours_node
from agentsystem.agents.plan_ceo_review_agent import plan_ceo_review_node
from agentsystem.agents.plan_design_review_agent import plan_design_review_node
from agentsystem.agents.qa_contract import build_qa_input_sources, load_qa_test_context, write_shared_qa_artifacts
from agentsystem.agents.retro_agent import retro_node
from agentsystem.agents.review_agent import review_node
from agentsystem.agents.ship_agent import ship_node


class GstackAgentArtifactTestCase(unittest.TestCase):
    def test_architecture_review_emits_qa_handoff_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "parsed_goal": "Ship the ranked theme linkage workflow.",
                "acceptance_checklist": ["Users can review ranked theme linkages in one pass."],
                "parsed_constraints": ["Keep the result schema stable."],
                "parsed_not_do": ["Do not rewrite the ranking engine."],
                "verification_basis": ["Run the ranking artifact pipeline end-to-end."],
                "primary_files": ["apps/web/src/app/page.tsx", "graphs/linkage.py"],
                "secondary_files": ["docs/architecture.md"],
                "story_inputs": ["theme snapshots", "watchlist links"],
                "story_outputs": ["ranked linkage report"],
                "subtasks": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-architecture",
            }

            updated = architecture_review_node(state)

            self.assertTrue(updated["architecture_review_success"])
            self.assertIn("## Architecture Diagram", updated["architecture_review_report"])
            self.assertIn("## Boundaries", updated["architecture_review_report"])
            self.assertIn("## QA Handoff", updated["architecture_review_report"])
            self.assertTrue(Path(updated["architecture_review_dir"]).joinpath("test_plan.json").exists())
            self.assertTrue(Path(updated["architecture_review_dir"]).joinpath("failure_modes.json").exists())
            self.assertTrue(Path(updated["qa_test_plan_path"]).exists())

    def test_architecture_review_can_pause_for_missing_planning_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "parsed_goal": "Ship the ranked theme linkage workflow.",
                "acceptance_checklist": [],
                "parsed_constraints": ["Keep the result schema stable."],
                "parsed_not_do": ["Do not rewrite the ranking engine."],
                "verification_basis": [],
                "primary_files": [],
                "secondary_files": ["docs/architecture.md"],
                "story_inputs": [],
                "story_outputs": [],
                "subtasks": [],
                "shared_blackboard": {},
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-architecture-pause",
            }

            updated = architecture_review_node(state)

            self.assertTrue(updated["architecture_review_success"])
            self.assertTrue(updated["awaiting_user_input"])
            self.assertEqual(updated["resume_from_mode"], "plan-eng-review")
            self.assertIsNotNone(updated["next_question"])
            self.assertTrue(
                Path(updated["architecture_review_dir"]).joinpath("planning_decision_state.json").exists()
            )

    def test_office_hours_outputs_six_forcing_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Ship a better authenticated dashboard flow.",
                "task_payload": {
                    "goal": "Ship a better authenticated dashboard flow.",
                    "audience": "Operations lead reviewing daily portfolio changes.",
                    "success_signal": ["Operators can verify positions in one pass."],
                },
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-office-hours",
            }
            updated = office_hours_node(state)

            self.assertTrue(updated["office_hours_success"])
            self.assertEqual(len(updated["office_hours_questions"]), 6)
            self.assertEqual(updated["office_hours_mode"], "startup")
            self.assertFalse(updated["office_hours_needs_context"])
            self.assertFalse(updated["awaiting_user_input"])
            self.assertIsNotNone(updated["dialogue_state"])
            self.assertIn("Build Next", updated["office_hours_report"])
            self.assertTrue(Path(updated["office_hours_dir"]).joinpath("forcing_questions.json").exists())
            self.assertTrue(Path(updated["office_hours_dir"]).joinpath("dialogue_state.json").exists())
            self.assertTrue(Path(updated["office_hours_design_doc"]).exists())

    def test_office_hours_strict_interaction_pauses_on_first_required_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Ship a better authenticated dashboard flow.",
                "task_payload": {
                    "goal": "Ship a better authenticated dashboard flow.",
                    "audience": "Operations lead reviewing daily portfolio changes.",
                    "success_signal": ["Operators can verify positions in one pass."],
                    "office_hours_require_answers": True,
                },
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-office-hours-pause",
            }

            updated = office_hours_node(state)

            self.assertTrue(updated["office_hours_success"])
            self.assertTrue(updated["awaiting_user_input"])
            self.assertEqual(updated["resume_from_mode"], "office-hours")
            self.assertIsNotNone(updated["next_question"])
            self.assertIn(str(updated["next_question"]["id"]), {"user", "pain", "workaround", "wedge", "proof"})
            self.assertEqual(
                int(updated["interaction_round"] or 0),
                int((updated.get("dialogue_state") or {}).get("answered_count") or 0),
            )

    def test_plan_ceo_review_outputs_mode_and_decision_ceremony(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            (repo_path / "docs").mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Ship a new analyst dashboard with stronger QA evidence.",
                "task_payload": {
                    "goal": "Ship a new analyst dashboard with stronger QA evidence.",
                    "project": "repo",
                    "delivery_mode": "interactive",
                    "constraints": ["Keep the runtime schema stable."],
                    "acceptance_criteria": ["Analysts can verify the dashboard in one pass."],
                    "related_files": ["apps/web/src/app/dashboard/page.tsx"],
                    "accepted_expansions": ["design_intent"],
                },
                "office_hours_summary": "Target analysts first and prove the new dashboard reduces review time.",
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-plan-ceo",
            }

            updated = plan_ceo_review_node(state)

            self.assertTrue(updated["plan_ceo_review_success"])
            self.assertIn("## CEO Review Mode", updated["plan_ceo_review_report"])
            self.assertIn("## Failure Modes Registry", updated["plan_ceo_review_report"])
            self.assertIn(updated["plan_ceo_selected_mode"], {"hold_scope", "selective_expansion", "scope_expansion"})
            self.assertTrue(Path(updated["plan_ceo_requirement_doc"]).exists())
            self.assertTrue(Path(updated["plan_ceo_review_dir"]).joinpath("decision_ceremony.json").exists())
            self.assertIn("accepted_expansions", updated["plan_ceo_decision_ceremony"])
            self.assertEqual(updated["dialogue_state"], updated["plan_ceo_decision_ceremony"])

    def test_plan_ceo_review_auto_run_selective_expansion_defers_instead_of_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            (repo_path / "docs").mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Expand proof only where it directly improves dashboard acceptance evidence.",
                "auto_run": True,
                "interaction_policy": "non_interactive_auto_run",
                "task_payload": {
                    "goal": "Expand proof only where it directly improves dashboard acceptance evidence.",
                    "project": "repo",
                    "delivery_mode": "auto",
                    "ceo_review_mode": "selective_expansion",
                    "constraints": ["Keep the runtime schema stable."],
                    "acceptance_criteria": ["Analysts can verify the dashboard in one pass."],
                    "related_files": ["apps/web/src/app/dashboard/page.tsx"],
                },
                "office_hours_summary": "Stay narrow and auto-defer speculative scope.",
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-plan-ceo-auto",
            }

            updated = plan_ceo_review_node(state)

            self.assertTrue(updated["plan_ceo_review_success"])
            self.assertEqual(updated["plan_ceo_selected_mode"], "selective_expansion")
            self.assertFalse(updated["awaiting_user_input"])
            self.assertFalse(updated["approval_required"])
            self.assertIsNone(updated["resume_from_mode"])
            self.assertEqual(updated["plan_ceo_unresolved_decisions"], [])
            self.assertGreaterEqual(len(updated["plan_ceo_decision_ceremony"].get("auto_deferred_expansions") or []), 1)

    def test_plan_ceo_review_strict_decisions_pause_for_unresolved_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            (repo_path / "docs").mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Expand proof only where it directly improves dashboard acceptance evidence.",
                "task_payload": {
                    "goal": "Expand proof only where it directly improves dashboard acceptance evidence.",
                    "project": "repo",
                    "delivery_mode": "interactive",
                    "ceo_review_mode": "selective_expansion",
                    "plan_ceo_require_decisions": True,
                    "constraints": ["Keep the runtime schema stable."],
                    "acceptance_criteria": ["Analysts can verify the dashboard in one pass."],
                    "related_files": ["apps/web/src/app/dashboard/page.tsx"],
                },
                "office_hours_summary": "Stay narrow, but surface high-value scope decisions explicitly.",
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-plan-ceo-pause",
            }

            updated = plan_ceo_review_node(state)

            self.assertTrue(updated["plan_ceo_review_success"])
            self.assertEqual(updated["plan_ceo_selected_mode"], "selective_expansion")
            self.assertTrue(updated["awaiting_user_input"])
            self.assertTrue(updated["approval_required"])
            self.assertEqual(updated["resume_from_mode"], "plan-ceo-review")
            self.assertGreaterEqual(len(updated["plan_ceo_unresolved_decisions"]), 1)
            self.assertIsNotNone(updated["next_question"])

    def test_investigate_outputs_root_cause_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "user_requirement": "Bugfix the delayed refresh state.",
                "bug_scope": "regression",
                "task_payload": {
                    "goal": "Bugfix the delayed refresh state.",
                    "investigation_context": ["Refresh indicator never exits loading state."],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                },
                "story_inputs": ["browser refresh click"],
                "story_process": ["refresh action", "state transition"],
                "story_outputs": ["idle state visible"],
                "fix_attempts": 1,
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-investigate",
            }
            updated = investigate_node(state)

            self.assertTrue(updated["investigate_success"])
            self.assertIn("## Data Flow", updated["investigation_report"])
            self.assertIn("## Temporary Instrumentation", updated["investigation_report"])
            self.assertIn("## Instrumentation Execution", updated["investigation_report"])
            self.assertIn("## Failed Attempts", updated["investigation_report"])
            self.assertTrue(Path(updated["investigate_dir"]).joinpath("investigation_report.json").exists())
            self.assertTrue(Path(updated["investigate_dir"]).joinpath("reproduction_checklist.json").exists())
            self.assertTrue(Path(updated["investigate_dir"]).joinpath("instrumentation_plan.json").exists())
            self.assertTrue(Path(updated["investigate_dir"]).joinpath("instrumentation_execution.json").exists())

    def test_review_emits_structured_findings_without_staging_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            (repo_path / ".agents").mkdir(parents=True)
            (repo_path / ".agents" / "project.yaml").write_text(
                "name: demo\ngit:\n  default_branch: main\n  working_branch_prefix: agent/\n",
                encoding="utf-8",
            )
            (repo_path / ".agents" / "rules.yaml").write_text("protected_paths: []\n", encoding="utf-8")
            (repo_path / ".agents" / "commands.yaml").write_text("commands: {}\n", encoding="utf-8")
            (repo_path / ".agents" / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "contracts.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / "app.py").write_text("print('before')\n", encoding="utf-8")

            repo = Repo.init(repo_path, initial_branch="main")
            repo.index.add(["."])
            with repo.config_writer() as config:
                config.set_value("user", "name", "Codex")
                config.set_value("user", "email", "codex@example.com")
            repo.index.commit("chore: seed fixture")
            (repo_path / "app.py").write_text("print('after')\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Tighten the ranked theme output.",
                    "acceptance_criteria": ["The main flow still works."],
                    "related_files": ["app.py"],
                },
                "primary_files": ["app.py"],
                "test_results": "Lint: PASS\nTypecheck: PASS\nTest: PASS\nStoryValidation: PASS",
                "handoff_packets": [],
                "issues_to_fix": [],
                "resolved_issues": [{"description": "Previously failing validation was fixed in the fixer loop."}],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-review",
            }

            updated = review_node(state)

            self.assertTrue(updated["review_success"])
            self.assertTrue(updated["review_passed"])
            self.assertIn("## Scope Check", updated["review_report"])
            self.assertTrue(Path(updated["review_dir"]).joinpath("review_findings.json").exists())
            self.assertTrue(Path(updated["review_dir"]).joinpath("review_checklist.json").exists())
            self.assertEqual(repo.git.diff("--cached", "--name-only").strip(), "")
            self.assertIn("app.py", repo.git.diff("--name-only"))
            repo.close()

    def test_review_records_staged_decision_state_for_agentsystem_workflow_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "agentsystem"
            repo_path.mkdir(parents=True)
            (repo_path / ".agents").mkdir(parents=True)
            (repo_path / ".agents" / "project.yaml").write_text(
                "name: agentsystem\ngit:\n  default_branch: main\n  working_branch_prefix: agent/\n",
                encoding="utf-8",
            )
            (repo_path / ".agents" / "rules.yaml").write_text("protected_paths: []\n", encoding="utf-8")
            (repo_path / ".agents" / "commands.yaml").write_text("commands: {}\n", encoding="utf-8")
            (repo_path / ".agents" / "review_policy.yaml").write_text("{}\n", encoding="utf-8")
            (repo_path / ".agents" / "contracts.yaml").write_text("{}\n", encoding="utf-8")
            changed_path = repo_path / "config" / "workflows" / "software_engineering.yaml"
            changed_path.parent.mkdir(parents=True, exist_ok=True)
            changed_path.write_text("plugin_id: software_engineering\n", encoding="utf-8")

            repo = Repo.init(repo_path, initial_branch="main")
            repo.index.add(["."])
            with repo.config_writer() as config:
                config.set_value("user", "name", "Codex")
                config.set_value("user", "email", "codex@example.com")
            repo.index.commit("chore: seed fixture")
            changed_path.write_text("plugin_id: software_engineering\nname: changed\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "story_kind": "runtime_data",
                "task_payload": {
                    "goal": "Tighten the workflow parity gate.",
                    "acceptance_criteria": ["Workflow manifest still resolves correctly."],
                    "related_files": ["config/workflows/software_engineering.yaml"],
                },
                "primary_files": ["config/workflows/software_engineering.yaml"],
                "test_results": "Lint: PASS\nTypecheck: PASS\nTest: PASS\nStoryValidation: PASS",
                "handoff_packets": [],
                "issues_to_fix": [],
                "resolved_issues": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-review-decision",
            }

            updated = review_node(state)

            self.assertTrue(updated["review_success"])
            self.assertTrue(updated["awaiting_user_input"])
            self.assertEqual(updated["resume_from_mode"], "review")
            self.assertEqual(updated["handoff_target"], "review_decision")
            self.assertIn("## Decision Ceremony", updated["review_report"])
            self.assertTrue(Path(updated["review_dir"]).joinpath("review_decision_state.json").exists())
            self.assertTrue(Path(updated["review_dir"]).joinpath("risk_register.json").exists())
            repo.close()

    def test_ship_document_release_and_retro_emit_closeout_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            (repo_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
            (repo_path / "docs").mkdir(parents=True)
            (repo_path / "docs" / "handoff").mkdir(parents=True)
            (repo_path / "docs" / "handoff" / "current_handoff.md").write_text("# Handoff\n", encoding="utf-8")

            repo = Repo.init(repo_path, initial_branch="main")
            repo.index.add(["."])
            with repo.config_writer() as config:
                config.set_value("user", "name", "Codex")
                config.set_value("user", "email", "codex@example.com")
            repo.index.commit("chore: seed fixture")

            base_state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "release_scope": ["S3-001"],
                    "doc_targets": ["README.md", "docs/handoff/current_handoff.md"],
                    "retro_window": "sprint-3",
                },
                "release_scope": ["S3-001"],
                "doc_targets": ["README.md", "docs/handoff/current_handoff.md"],
                "retro_window": "sprint-3",
                "test_passed": True,
                "review_passed": True,
                "code_acceptance_passed": True,
                "acceptance_passed": True,
                "browser_qa_health_score": 92,
                "mode_execution_order": ["plan-eng-review", "build", "review", "qa"],
                "handoff_packets": [],
                "all_deliverables": [],
                "issues_to_fix": [],
                "resolved_issues": [],
                "collaboration_trace_id": "trace-closeout",
            }

            shipped = ship_node(dict(base_state))
            docs = document_release_node(dict(shipped))
            retro = retro_node(dict(docs))

            self.assertTrue(shipped["ship_success"])
            self.assertIn("## Pre-Landing Review", shipped["ship_report"])
            self.assertIn("## Closeout Checklist", shipped["ship_report"])
            self.assertIn("## Coverage Audit", shipped["ship_report"])
            self.assertIn("## Release Version", shipped["ship_report"])
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("release_package.json").exists())
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("closeout_checklist.json").exists())
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("coverage_audit.json").exists())
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("release_version.json").exists())
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("changelog_draft.md").exists())
            self.assertTrue(Path(shipped["ship_dir"]).joinpath("pr_draft.md").exists())
            self.assertTrue(docs["document_release_success"])
            self.assertIn("## Documentation Checklist", docs["document_release_report"])
            self.assertIn("## Sync Actions", docs["document_release_report"])
            self.assertIn("## Applied Changes", docs["document_release_report"])
            self.assertTrue(Path(docs["document_release_dir"]).joinpath("doc_sync_plan.json").exists())
            self.assertTrue(Path(docs["document_release_dir"]).joinpath("stale_sections.json").exists())
            self.assertTrue(Path(docs["document_release_dir"]).joinpath("applied_doc_changes.json").exists())
            self.assertTrue(Path(docs["document_release_dir"]).joinpath("doc_diff_summary.json").exists())
            self.assertTrue(Path(docs["document_release_dir"]).joinpath("skipped_doc_targets.json").exists())
            self.assertTrue(retro["retro_success"])
            self.assertIn("## Metrics", retro["retro_report"])
            self.assertIn("## Closeout Linkage", retro["retro_report"])
            self.assertIn("## Trend Analysis", retro["retro_report"])
            self.assertIn("## Git Activity", retro["retro_report"])
            self.assertTrue(Path(retro["retro_dir"]).joinpath("retro_snapshot.json").exists())
            self.assertTrue(Path(retro["retro_dir"]).joinpath("closeout_linkage.json").exists())
            self.assertTrue(Path(retro["retro_dir"]).joinpath("previous_snapshot.json").exists())
            self.assertTrue(Path(retro["retro_dir"]).joinpath("trend_analysis.json").exists())
            self.assertTrue(Path(retro["retro_dir"]).joinpath("git_activity_summary.json").exists())
            repo.close()

    def test_plan_design_review_emits_route_contract_and_risks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "review_mode": "auto",
                    "acceptance_criteria": ["The first screen explains the route purpose."],
                    "browse_observations": [{"route": "/dashboard", "route_kind": "page", "intent": "summary", "screenshot_path": "after.png"}],
                },
                "browse_observations": [{"route": "/dashboard", "route_kind": "page", "intent": "summary", "screenshot_path": "after.png"}],
                "reference_observations": [],
                "handoff_packets": [],
                "all_deliverables": [],
                "collaboration_trace_id": "trace-plan-design",
            }

            updated = plan_design_review_node(state)

            self.assertTrue(updated["plan_design_review_success"])
            review_dir = Path(updated["plan_design_review_dir"])
            self.assertTrue(review_dir.joinpath("route_design_contract.json").exists())
            self.assertTrue(review_dir.joinpath("design_risks.json").exists())
            self.assertTrue((repo_path / "DESIGN.md").exists())

    def test_shared_qa_artifacts_record_input_sources_and_rerun_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo_path.mkdir(parents=True)
            qa_plan_path = repo_path.parent / ".meta" / repo_path.name / "architecture_review" / "qa_test_plan.md"
            qa_plan_path.parent.mkdir(parents=True, exist_ok=True)
            qa_plan_path.write_text(
                "\n".join(
                    [
                        "# QA Test Plan",
                        "",
                        "## Affected Pages/Routes",
                        "- /rankings",
                        "",
                        "## Key Interactions to Verify",
                        "- trigger ranked linkage refresh",
                        "",
                        "## Edge Cases",
                        "- no linkages available",
                        "",
                        "## Critical Paths",
                        "- ranked linkage render",
                    ]
                ),
                encoding="utf-8",
            )
            context = load_qa_test_context(
                {
                    "story_kind": "runtime_data",
                    "qa_test_plan_path": str(qa_plan_path),
                    "verification_basis": ["validate ranking artifact output"],
                    "architecture_test_plan": {
                        "qa_handoff": ["Validate ranking output ordering."],
                        "failure_modes": [
                            {
                                "failure": "Ranking sort can silently drift.",
                                "verification": "Compare output ordering against expected ranking fixtures.",
                            }
                        ],
                    },
                },
                repo_path,
            )
            input_sources = build_qa_input_sources(
                {"story_kind": "runtime_data", "test_results": "StoryValidation: PASS"},
                context,
                source_mode="runtime_qa",
                report_only=True,
            )
            artifacts = write_shared_qa_artifacts(
                repo_path,
                mode_id="qa-only",
                report_only=True,
                findings=[],
                health_score=100,
                ship_readiness="ready",
                test_context=context,
                regression_recommendations=["Re-run critical path from plan-eng-review: ranked linkage render"],
                verification_rerun_plan=["Re-confirm QA handoff expectation: Validate ranking output ordering."],
                input_sources=input_sources,
            )

            summary = Path(artifacts["qa_summary_path"]).read_text(encoding="utf-8")
            rerun = Path(artifacts["qa_rerun_plan_path"]).read_text(encoding="utf-8")
            self.assertIn("input_sources", summary)
            self.assertIn("rerun_required", summary)
            self.assertIn("verification_rerun_plan", rerun)


if __name__ == "__main__":
    unittest.main()
