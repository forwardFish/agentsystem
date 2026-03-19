from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git import Repo

from agentsystem.agents.design_consultation_agent import design_consultation_node
from agentsystem.agents.frontend_dev_agent import frontend_dev_node
from agentsystem.agents.qa_design_review_agent import qa_design_review_node
from agentsystem.core.state import SubTask
from agentsystem.graph.dev_workflow import DevWorkflow

PROJECT_YAML = """name: ui-fixture
stack:
  frontend:
    path: apps/web
git:
  default_branch: main
"""
RULES_YAML = "{}\n"
COMMANDS_YAML = """lint:
  - python -c "print('lint ok')"
"""
REVIEW_POLICY_YAML = "{}\n"
CONTRACTS_YAML = "{}\n"
STYLE_GUIDE_MD = "# Style Guide\n"


class DesignClosureTestCase(unittest.TestCase):
    def test_design_consultation_skill_mode_generates_contract_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)

            workflow = DevWorkflow(
                {},
                str(repo_path),
                {
                    "goal": "Turn the page into a product-grade research cockpit.",
                    "acceptance_criteria": ["The first screen explains what the page is for."],
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "skill_mode": "design-consultation",
                },
                task_id="task-design",
            )
            result = workflow.run()

            self.assertTrue(result["success"])
            self.assertEqual(result["state"]["current_step"], "design_consultation_done")
            self.assertIn("design-consultation", result["state"]["executed_modes"])
            self.assertTrue((repo_path / "DESIGN.md").exists())
            self.assertTrue((repo_path.parent / ".meta" / repo_path.name / "design_consultation" / "design_preview.html").exists())

    def test_frontend_builder_uses_design_contract_on_minimal_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            page_path = repo_path / "apps" / "web" / "src" / "app" / "page.tsx"
            page_path.write_text("export default function Page(){ return <main>demo</main>; }\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Turn this into a product page.",
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "acceptance_criteria": ["The page should no longer feel like a demo."],
                    "constraints": [],
                },
                "subtasks": [
                    SubTask(id="1", type="frontend", description="Upgrade page", files_to_modify=["apps/web/src/app/page.tsx"])
                ],
                "collaboration_trace_id": "trace-design",
                "handoff_packets": [],
                "all_deliverables": [],
            }
            design_consultation_node(state)
            result = frontend_dev_node(state)

            updated = page_path.read_text(encoding="utf-8")
            self.assertIn("Product Surface", updated)
            self.assertIn("DESIGN.md", updated)
            self.assertTrue(result["dev_results"]["frontend"]["design_contract_used"])

    def test_frontend_builder_productizes_dashboard_surface_without_live_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            page_path = repo_path / "apps" / "web" / "src" / "app" / "page.tsx"
            page_path.write_text(
                """export default function Page() {
  return (
    <main className="page-shell">
      <section className="hero">
        <span className="eyebrow">Daily Snapshot</span>
        <h1>Demo Board</h1>
        <p>Plain dashboard copy.</p>
        <form className="toolbar"></form>
        <div className="metric-grid"></div>
      </section>
    </main>
  );
}
""",
                encoding="utf-8",
            )

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Turn this dashboard into a product-grade operating surface.",
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "acceptance_criteria": ["The page should no longer feel like a demo."],
                    "constraints": [],
                },
                "subtasks": [
                    SubTask(id="1", type="frontend", description="Upgrade page", files_to_modify=["apps/web/src/app/page.tsx"])
                ],
                "collaboration_trace_id": "trace-dashboard-design",
                "handoff_packets": [],
                "all_deliverables": [],
            }
            design_consultation_node(state)
            result = frontend_dev_node(state)

            updated = page_path.read_text(encoding="utf-8")
            self.assertIn("Decision Lead", updated)
            self.assertIn("Product Intelligence Surface", updated)
            self.assertTrue(
                any(path.replace("\\", "/").endswith("apps/web/src/app/page.tsx") for path in result["dev_results"]["frontend"]["updated_files"])
            )

    def test_qa_design_review_reads_design_contract_expectations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            _create_repo_fixture(repo_path)
            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "Refresh the page into a product surface.",
                    "related_files": ["apps/web/src/app/page.tsx"],
                    "primary_files": ["apps/web/src/app/page.tsx"],
                    "acceptance_criteria": ["The first screen explains what the page is for."],
                    "constraints": [],
                },
                "primary_files": ["apps/web/src/app/page.tsx"],
                "risk_level": "high",
                "browser_qa_health_score": 91,
                "browser_qa_findings": [],
                "browser_qa_warnings": ["Visual density should stay legible under real data."],
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(repo_path / "apps" / "web" / "src" / "app" / "page.tsx")],
                    }
                },
                "collaboration_trace_id": "trace-qa-design",
                "handoff_packets": [],
                "all_deliverables": [],
            }
            design_consultation_node(state)
            updated = qa_design_review_node(state)

            self.assertTrue(updated["qa_design_review_success"])
            self.assertIn("The first screen explains what the page is for.", updated["qa_design_review_report"])
            self.assertIn("Visual density should stay legible under real data.", updated["qa_design_review_report"])


def _create_repo_fixture(repo_path: Path) -> None:
    (repo_path / ".agents").mkdir(parents=True)
    (repo_path / "apps" / "web" / "src" / "app").mkdir(parents=True, exist_ok=True)
    (repo_path / "apps" / "web" / "src" / "app" / "page.tsx").write_text(
        "export default function Page(){ return <main>fixture</main>; }\n",
        encoding="utf-8",
    )
    (repo_path / ".agents" / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
    (repo_path / ".agents" / "rules.yaml").write_text(RULES_YAML, encoding="utf-8")
    (repo_path / ".agents" / "commands.yaml").write_text(COMMANDS_YAML, encoding="utf-8")
    (repo_path / ".agents" / "review_policy.yaml").write_text(REVIEW_POLICY_YAML, encoding="utf-8")
    (repo_path / ".agents" / "contracts.yaml").write_text(CONTRACTS_YAML, encoding="utf-8")
    (repo_path / ".agents" / "style_guide.md").write_text(STYLE_GUIDE_MD, encoding="utf-8")

    repo = Repo.init(repo_path, initial_branch="main")
    repo.index.add(["."])
    with repo.config_writer() as config:
        config.set_value("user", "name", "Codex")
        config.set_value("user", "email", "codex@example.com")
    repo.index.commit("chore: seed fixture")
    repo.close()


if __name__ == "__main__":
    unittest.main()
