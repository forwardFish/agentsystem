from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from git import Repo

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.agents.design_consultation_agent import design_consultation_node
from agentsystem.agents.document_release_agent import document_release_node
from agentsystem.agents.plan_design_review_agent import plan_design_review_node
from agentsystem.agents.qa_design_review_agent import qa_design_review_node
from agentsystem.agents.retro_agent import retro_node
from agentsystem.agents.ship_agent import ship_node
from agentsystem.orchestration.full_parity_evidence import record_full_parity_evidence
from agentsystem.orchestration.gstack_parity_audit import write_gstack_parity_audit


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _init_repo(repo_path: Path) -> None:
    repo = Repo.init(repo_path, initial_branch="main")
    with repo.config_writer() as config:
        config.set_value("user", "name", "Codex")
        config.set_value("user", "email", "codex@example.com")
    repo.index.add(["."])
    repo.index.commit("chore: seed full parity evidence fixture")
    repo.close()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _generate_design_chain(evidence_root: Path) -> list[dict[str, object]]:
    repo_path = evidence_root / "design_chain_repo"
    _reset_dir(repo_path)
    _write_text(repo_path / "apps" / "web" / "src" / "app" / "page.tsx", "export default function Page(){ return <main>fixture</main>; }\n")
    _init_repo(repo_path)

    before_path = _write_text(evidence_root / "design_before.png", "before")
    after_path = _write_text(evidence_root / "design_after.png", "after")
    reference_path = _write_text(evidence_root / "design_reference.png", "reference")

    state = {
        "repo_b_path": str(repo_path),
        "task_payload": {
            "goal": "Turn the ranked research surface into a product-grade operating page.",
            "acceptance_criteria": [
                "The first screen explains what the page is for.",
                "The route feels product-grade instead of like a demo board.",
            ],
            "related_files": ["apps/web/src/app/page.tsx"],
            "primary_files": ["apps/web/src/app/page.tsx"],
            "route_scope": ["/dashboard"],
            "browse_observations": [
                {
                    "route": "/dashboard",
                    "selector": "main",
                    "screenshot_path": str(after_path),
                }
            ],
            "reference_observations": [
                {
                    "route": "/dashboard",
                    "selector": "main",
                    "screenshot_path": str(reference_path),
                }
            ],
        },
        "primary_files": ["apps/web/src/app/page.tsx"],
        "risk_level": "high",
        "browser_qa_health_score": 93,
        "browser_qa_warnings": ["Keep summary hierarchy strong under dense evidence."],
        "before_screenshot_paths": [str(before_path)],
        "after_screenshot_paths": [str(after_path)],
        "handoff_packets": [],
        "all_deliverables": [],
        "issues_to_fix": [],
        "resolved_issues": [],
        "executed_modes": [],
        "collaboration_trace_id": "trace-design-chain-parity",
    }

    design_consultation_node(state)
    plan_design_review_node(state)
    qa_design_review_node(state)

    meta_root = repo_path.parent / ".meta" / repo_path.name
    consultation_dir = meta_root / "design_consultation"
    plan_dir = meta_root / "plan_design_review"
    review_dir = meta_root / "qa_design_review"

    return [
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="design-consultation",
            evidence_type="design_consultation_multi_turn",
            project="agentsystem",
            detail="Design consultation produced multi-round convergence artifacts and auto-run assumptions.",
            source="runtime",
            evidence_refs=[
                str(consultation_dir / "design_consultation_report.md"),
                str(consultation_dir / "consultation_rounds.json"),
                str(consultation_dir / "design_decisions.json"),
                str(repo_path / "DESIGN.md"),
            ],
        ),
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="plan-design-review",
            evidence_type="plan_design_route_contract",
            project="agentsystem",
            detail="Plan-design-review produced route-level contract and design-risk artifacts.",
            source="runtime",
            evidence_refs=[
                str(plan_dir / "design_review_report.md"),
                str(plan_dir / "route_design_contract.json"),
                str(plan_dir / "design_risks.json"),
                str(repo_path / "DESIGN.md"),
            ],
        ),
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="design-review",
            evidence_type="design_review_visual_audit",
            project="agentsystem",
            detail="Design-review produced visual checklist, verdict, and route before/after evidence.",
            source="runtime",
            evidence_refs=[
                str(review_dir / "qa_design_review_report.md"),
                str(review_dir / "visual_checklist.json"),
                str(review_dir / "visual_verdict.json"),
                str(review_dir / "route_before_after.json"),
            ],
        ),
    ]


def _generate_closeout_chain(evidence_root: Path) -> list[dict[str, object]]:
    repo_path = evidence_root / "closeout_repo"
    _reset_dir(repo_path)
    _write_text(repo_path / "README.md", "# Closeout Repo\n\nInitial release notes.\n")
    _write_text(repo_path / "docs" / "handoff" / "current_handoff.md", "# Handoff\n")
    _write_text(repo_path / "docs" / "runbook.md", "# Runbook\n")
    _write_text(repo_path / "VERSION", "0.2.0\n")
    _init_repo(repo_path)

    retro_dir = repo_path.parent / ".meta" / repo_path.name / "retro"
    retro_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        retro_dir / "retro_snapshot.json",
        {
            "generated_at": "2026-03-20T23:30:00",
            "window": "previous cycle",
            "metrics": {
                "deliverable_count": 2,
                "open_issue_count": 1,
                "resolved_issue_count": 0,
                "browser_qa_health_score": 88,
                "mode_execution_order": ["ship", "document-release"],
            },
        },
    )

    state = {
        "repo_b_path": str(repo_path),
        "task_payload": {
            "release_scope": ["design parity closeout", "documentation sync"],
            "doc_targets": ["README.md", "docs/handoff/current_handoff.md", "docs/runbook.md"],
            "retro_window": "sprint close",
            "next_recommended_actions": ["Roll the closeout learnings into the next workflow audit."],
        },
        "required_modes": ["ship", "document-release", "retro"],
        "executed_modes": ["plan-eng-review", "review", "qa"],
        "mode_execution_order": ["ship", "document-release", "retro"],
        "agent_mode_coverage": {"all_required_executed": True},
        "all_deliverables": [{"name": "release package"}, {"name": "retro snapshot"}],
        "issues_to_fix": [],
        "resolved_issues": [{"description": "Closeout evidence was stitched into the parity ledger."}],
        "test_passed": True,
        "review_passed": True,
        "code_acceptance_passed": True,
        "acceptance_passed": True,
        "browser_qa_health_score": 95,
        "document_release_success": False,
        "handoff_packets": [],
        "collaboration_trace_id": "trace-closeout-chain-parity",
    }

    ship_node(state)
    document_release_node(state)
    retro_node(state)

    meta_root = repo_path.parent / ".meta" / repo_path.name
    ship_dir = meta_root / "ship"
    document_release_dir = meta_root / "document_release"
    retro_dir = meta_root / "retro"

    return [
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="ship",
            evidence_type="ship_closeout_automation",
            project="agentsystem",
            detail="Ship mode emitted release version, coverage audit, changelog draft, and PR draft artifacts.",
            source="runtime",
            evidence_refs=[
                str(ship_dir / "ship_readiness_report.md"),
                str(ship_dir / "coverage_audit.json"),
                str(ship_dir / "release_version.json"),
                str(ship_dir / "changelog_draft.md"),
                str(ship_dir / "pr_draft.md"),
            ],
        ),
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="document-release",
            evidence_type="document_release_applied_sync",
            project="agentsystem",
            detail="Document-release applied safe doc sync updates and wrote a diff summary.",
            source="runtime",
            evidence_refs=[
                str(document_release_dir / "document_release_report.md"),
                str(document_release_dir / "applied_doc_changes.json"),
                str(document_release_dir / "doc_diff_summary.json"),
                str(document_release_dir / "skipped_doc_targets.json"),
            ],
        ),
        record_full_parity_evidence(
            ROOT_DIR,
            mode_id="retro",
            evidence_type="retro_trend_snapshot",
            project="agentsystem",
            detail="Retro emitted previous snapshot, trend analysis, and git activity summary artifacts.",
            source="runtime",
            evidence_refs=[
                str(retro_dir / "retro_report.md"),
                str(retro_dir / "previous_snapshot.json"),
                str(retro_dir / "trend_analysis.json"),
                str(retro_dir / "git_activity_summary.json"),
            ],
        ),
    ]


def main() -> int:
    evidence_root = ROOT_DIR / "runs" / "parity" / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)

    entries = []
    entries.extend(_generate_design_chain(evidence_root))
    entries.extend(_generate_closeout_chain(evidence_root))

    sprint_dir = ROOT_DIR.parent / "finahunt" / "tasks" / "backlog_v1" / "sprint_3_linkage_and_ranking"
    result = write_gstack_parity_audit(ROOT_DIR / "runs" / "parity", sprint_dir=sprint_dir, project="finahunt")
    print(json.dumps({"recorded_entries": entries, "audit": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
