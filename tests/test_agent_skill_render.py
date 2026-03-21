from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.render_agent_skills import ROOT_DIR, render_all_agent_skills, validate_rendered_agent_package
from scripts.render_codex_skill_adapters import render_codex_skill_adapters


class AgentSkillRenderTestCase(unittest.TestCase):
    def test_render_all_agent_skills_generates_expected_packages(self) -> None:
        rendered = render_all_agent_skills(ROOT_DIR)

        self.assertEqual(
            {item["mode_id"] for item in rendered},
            {
                "office-hours",
                "plan-ceo-review",
                "plan-eng-review",
                "investigate",
                "plan-design-review",
                "design-consultation",
                "review",
                "ship",
                "browse",
                "qa",
                "qa-only",
                "design-review",
                "qa-design-review",
                "setup-browser-cookies",
                "retro",
                "document-release",
            },
        )
        for item in rendered:
            package_dir = Path(item["skill_path"]).resolve().parent
            self.assertTrue((package_dir / "AGENT.md.tmpl").exists())
            self.assertTrue((package_dir / "SKILL.md").exists())
            self.assertTrue((package_dir / "agent.manifest.json").exists())
            self.assertTrue(validate_rendered_agent_package(package_dir))

    def test_rendered_manifest_matches_expected_mode_contract(self) -> None:
        render_all_agent_skills(ROOT_DIR)
        manifest_path = ROOT_DIR / ".claude" / "agents" / "qa" / "agent.manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode_id"], "qa")
        self.assertEqual(payload["workflow_plugin_id"], "software_engineering")
        self.assertEqual(payload["entry_mode"], "tester")
        self.assertEqual(payload["stop_after"], "browser_qa")
        self.assertTrue(payload["fixer_allowed"])
        self.assertIn("software_engineering.browser_qa", payload["agent_manifest_ids"])

    def test_ship_skill_manifest_is_runtime_ready(self) -> None:
        render_all_agent_skills(ROOT_DIR)
        manifest_path = ROOT_DIR / ".claude" / "agents" / "ship" / "agent.manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode_id"], "ship")
        self.assertTrue(payload["runtime_ready"])
        self.assertEqual(payload["entry_mode"], "ship")
        self.assertEqual(payload["stop_after"], "ship")

    def test_codex_skill_adapters_include_upstream_mirror(self) -> None:
        rendered = render_codex_skill_adapters(ROOT_DIR)
        self.assertIn("browse", {item["mode_id"] for item in rendered})
        browse_dir = ROOT_DIR / "codex_skills" / "browse"
        self.assertTrue((browse_dir / "SKILL.md").exists())
        self.assertTrue((browse_dir / "UPSTREAM_SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
