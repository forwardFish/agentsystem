from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.graph.dev_workflow import create_dev_graph
from agentsystem.orchestration.agent_manifest_registry import get_agent_manifest
from agentsystem.orchestration.workflow_registry import get_workflow_plugin


class WorkflowRegistryTestCase(unittest.TestCase):
    def test_default_software_engineering_plugin_is_registered(self) -> None:
        plugin = get_workflow_plugin()

        self.assertEqual(plugin.plugin_id, "software_engineering")
        self.assertEqual(plugin.entry_point, "requirement_analysis")
        self.assertIn("architecture_review", {node.node_id for node in plugin.nodes})
        self.assertIn("backend_dev", {node.node_id for node in plugin.nodes})
        self.assertIn("browser_qa", {node.node_id for node in plugin.nodes})
        self.assertIn("reviewer", {node.node_id for node in plugin.nodes})
        self.assertIn("architecture_review", plugin.verification_pipeline)
        self.assertIn("browser_qa", plugin.verification_pipeline)
        self.assertIn("code_acceptance", plugin.verification_pipeline)
        self.assertIn("acceptance_gate", plugin.human_approval_points)
        self.assertTrue(plugin.manifest_path.endswith("software_engineering.yaml"))
        self.assertIn("WorkflowPolicy.default", plugin.policy_refs)
        reviewer = next(node for node in plugin.nodes if node.node_id == "reviewer")
        self.assertEqual(reviewer.agent_id, "software_engineering.reviewer")
        self.assertEqual(reviewer.agent_role, "verification.review")
        self.assertEqual(reviewer.plane, "verification")
        self.assertIn("code_review", reviewer.capabilities)
        self.assertTrue(reviewer.manifest_path.endswith("reviewer.yaml"))

    def test_dev_graph_accepts_registered_plugin_id(self) -> None:
        graph = create_dev_graph("software_engineering")
        self.assertIsNotNone(graph)

    def test_manifest_loader_supports_custom_manifest_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest_dir = base / "workflows"
            agent_dir = base / "agents"
            manifest_dir.mkdir(parents=True)
            agent_dir.mkdir(parents=True)
            (agent_dir / "requirement.yaml").write_text(
                "\n".join(
                    [
                        "agent_id: custom.requirement",
                        "name: Requirement Agent",
                        "handler: requirement_analysis_node",
                        "agent_role: requirement.analysis",
                        "plane: build",
                    ]
                ),
                encoding="utf-8",
            )
            (agent_dir / "doc.yaml").write_text(
                "\n".join(
                    [
                        "agent_id: custom.doc",
                        "name: Doc Agent",
                        "handler: doc_node",
                        "agent_role: documentation.sync",
                        "plane: build",
                    ]
                ),
                encoding="utf-8",
            )
            (manifest_dir / "software_engineering.yaml").write_text(
                "\n".join(
                    [
                        "plugin_id: software_engineering",
                        "name: Custom Workflow",
                        "description: custom manifest",
                        "entry_point: requirement_analysis",
                        "verification_pipeline:",
                        "  - review",
                        "human_approval_points:",
                        "  - acceptance_gate",
                        "nodes:",
                        "  - node_id: requirement_analysis",
                        "    display_name: Requirement",
                        "    agent_manifest: custom.requirement",
                        "  - node_id: doc_writer",
                        "    display_name: Doc Writer",
                        "    agent_manifest: custom.doc",
                        "edges:",
                        "  - source: requirement_analysis",
                        "    target: doc_writer",
                        "  - source: doc_writer",
                        "    target: __end__",
                    ]
                ),
                encoding="utf-8",
            )
            with (
                patch("agentsystem.orchestration.workflow_registry.WORKFLOW_MANIFEST_DIR", manifest_dir),
                patch("agentsystem.orchestration.agent_manifest_registry.AGENT_MANIFEST_DIR", agent_dir),
            ):
                plugin = get_workflow_plugin("software_engineering")

            self.assertEqual(plugin.name, "Custom Workflow")
            self.assertEqual(plugin.edges[0], ("requirement_analysis", "doc_writer"))
            self.assertEqual(plugin.manifest_path, str(manifest_dir / "software_engineering.yaml"))
            self.assertEqual(plugin.nodes[0].agent_id, "custom.requirement")

    def test_agent_manifest_loader_returns_default_agent(self) -> None:
        manifest = get_agent_manifest("software_engineering.reviewer")

        self.assertEqual(manifest.agent_role, "verification.review")
        self.assertIn("code_review", manifest.capabilities)
        self.assertTrue(manifest.manifest_path.endswith("reviewer.yaml"))

    def test_agent_manifest_loader_returns_browser_qa_agent(self) -> None:
        manifest = get_agent_manifest("software_engineering.browser_qa")

        self.assertEqual(manifest.agent_role, "verification.browser_qa")
        self.assertIn("browser_probe", manifest.capabilities)
        self.assertTrue(manifest.manifest_path.endswith("browser_qa.yaml"))


if __name__ == "__main__":
    unittest.main()
