from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.orchestration.gstack_parity_audit import build_gstack_parity_audit, write_gstack_parity_audit
from agentsystem.orchestration.full_parity_evidence import full_parity_evidence_path, record_full_parity_evidence


ROOT_DIR = Path(__file__).resolve().parents[1]


class GstackParityAuditTestCase(unittest.TestCase):
    def test_audit_reports_browse_and_sprint3_blockers(self) -> None:
        sprint_dir = ROOT_DIR.parent / "finahunt" / "tasks" / "backlog_v1" / "sprint_3_linkage_and_ranking"
        audit = build_gstack_parity_audit(sprint_dir=sprint_dir, project="finahunt")

        browse = next(item for item in audit["agents"] if item["mode_id"] == "browse")
        plan_eng_review = next(item for item in audit["agents"] if item["mode_id"] == "plan-eng-review")
        review = next(item for item in audit["agents"] if item["mode_id"] == "review")
        qa = next(item for item in audit["agents"] if item["mode_id"] == "qa")
        self.assertEqual(browse["declared_parity_status"], "partial_runtime")
        self.assertIn(browse["parity_status"], {"partial_runtime", "full_parity"})
        self.assertEqual(browse["formal_evidence_complete"], not bool(browse["full_parity_upgrade_blockers"]))
        self.assertTrue(any(item["name"] == "upstream_skill" and item["status"] == "passed" for item in browse["checks"]))
        self.assertTrue(all(item["status"] == "passed" for item in plan_eng_review["acceptance_checklist"]))
        self.assertTrue(all(item["status"] == "passed" for item in review["acceptance_checklist"]))
        self.assertTrue(all(item["status"] == "passed" for item in qa["acceptance_checklist"]))
        self.assertTrue(plan_eng_review["dogfood_eligible"])
        self.assertTrue(review["dogfood_eligible"])
        self.assertTrue(qa["dogfood_eligible"])
        self.assertEqual(plan_eng_review["parity_status"], "full_parity")
        self.assertEqual(review["parity_status"], "full_parity")
        self.assertEqual(qa["parity_status"], "full_parity")
        self.assertTrue(audit["dogfood_target"]["required_modes"])
        self.assertTrue(audit["dogfood_target"]["formal_dogfood_ready"])
        self.assertTrue(audit["dogfood_target"]["dogfood_completed"])
        self.assertFalse(audit["dogfood_target"]["formal_dogfood_blockers"])

    def test_audit_promotes_nonrequired_modes_when_formal_evidence_exists(self) -> None:
        sprint_dir = ROOT_DIR.parent / "finahunt" / "tasks" / "backlog_v1" / "sprint_3_linkage_and_ranking"
        evidence_path = full_parity_evidence_path(ROOT_DIR)
        original = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else None
        try:
            record_full_parity_evidence(
                ROOT_DIR,
                mode_id="qa-only",
                evidence_type="report_only_runtime_story",
                project="finahunt",
                detail="Report-only QA evidence recorded for a runtime/data story.",
                evidence_refs=[str(ROOT_DIR / "tests" / "test_gstack_agent_artifacts.py")],
            )
            audit = build_gstack_parity_audit(sprint_dir=sprint_dir, project="finahunt")
            qa_only = next(item for item in audit["agents"] if item["mode_id"] == "qa-only")
            self.assertTrue(qa_only["formal_evidence_complete"])
            self.assertEqual(qa_only["parity_status"], "full_parity")
            self.assertFalse(qa_only["full_parity_upgrade_blockers"])
        finally:
            if original is None:
                try:
                    evidence_path.unlink()
                except FileNotFoundError:
                    pass
            else:
                evidence_path.write_text(original, encoding="utf-8")

    def test_audit_writer_emits_manifest_and_checklist(self) -> None:
        sprint_dir = ROOT_DIR.parent / "finahunt" / "tasks" / "backlog_v1" / "sprint_3_linkage_and_ranking"
        with tempfile.TemporaryDirectory() as tmp:
            result = write_gstack_parity_audit(tmp, sprint_dir=sprint_dir, project="finahunt")

            manifest_path = Path(result["parity_manifest_path"])
            checklist_path = Path(result["acceptance_checklist_path"])
            self.assertTrue(manifest_path.exists())
            self.assertTrue(checklist_path.exists())
            self.assertIn("Formal dogfood ready", checklist_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
