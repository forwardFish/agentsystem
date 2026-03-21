from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]


class GstackParityManifestTestCase(unittest.TestCase):
    def test_manifest_pins_upstream_commit_and_modes(self) -> None:
        manifest_path = ROOT_DIR / "config" / "platform" / "gstack_parity_manifest.yaml"
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["upstream"]["commit"], "8ddfab233d3999edb172bed54aaf06fc5ff92646")
        mode_ids = {item["mode_id"] for item in payload["agents"]}
        self.assertIn("browse", mode_ids)
        self.assertIn("office-hours", mode_ids)
        self.assertIn("investigate", mode_ids)
        self.assertIn("ship", mode_ids)
        browse = next(item for item in payload["agents"] if item["mode_id"] == "browse")
        self.assertEqual(browse["parity_status"], "partial_runtime")
        self.assertTrue(browse["acceptance_gates"])
        self.assertEqual(browse["missing_capabilities"], [])
        qa_only = next(item for item in payload["agents"] if item["mode_id"] == "qa-only")
        self.assertEqual(qa_only["missing_capabilities"], [])
        setup_browser_cookies = next(item for item in payload["agents"] if item["mode_id"] == "setup-browser-cookies")
        self.assertEqual(setup_browser_cookies["missing_capabilities"], [])


if __name__ == "__main__":
    unittest.main()
