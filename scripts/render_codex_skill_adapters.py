from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

import sys

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.orchestration.skill_mode_registry import list_skill_modes


OUTPUT_DIR = ROOT_DIR / "codex_skills"


def render_codex_skill_adapters(root_dir: str | Path = ROOT_DIR) -> list[dict[str, str]]:
    root_path = Path(root_dir).resolve()
    output_root = root_path / "codex_skills"
    output_root.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, str]] = []
    for mode in list_skill_modes("software_engineering"):
        upstream_ref = str(mode.metadata.get("upstream_skill") or "").strip()
        upstream_path = (root_path / upstream_ref).resolve() if upstream_ref else None
        package_dir = output_root / mode.mode_id
        package_dir.mkdir(parents=True, exist_ok=True)

        skill_text = _build_codex_skill(mode, upstream_ref, upstream_path)
        skill_path = package_dir / "SKILL.md"
        skill_path.write_text(skill_text, encoding="utf-8")

        manifest_path = package_dir / "adapter.manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "mode_id": mode.mode_id,
                    "workflow_plugin_id": mode.workflow_plugin_id,
                    "entry_mode": mode.entry_mode,
                    "stop_after": mode.stop_after,
                    "runtime_ready": mode.runtime_ready,
                    "report_only": mode.report_only,
                    "fixer_allowed": mode.fixer_allowed,
                    "upstream_skill": upstream_ref,
                    "expected_artifacts": list(mode.expected_artifacts),
                    "required_inputs": list(mode.required_inputs),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        if upstream_path and upstream_path.exists():
            (package_dir / "UPSTREAM_SKILL.md").write_text(upstream_path.read_text(encoding="utf-8"), encoding="utf-8")

        rendered.append(
            {
                "mode_id": mode.mode_id,
                "skill_path": str(skill_path),
                "manifest_path": str(manifest_path),
            }
        )
    return rendered


def _build_codex_skill(mode, upstream_ref: str, upstream_path: Path | None) -> str:
    upstream_hint = upstream_ref or "not vendored"
    upstream_status = "present" if upstream_path and upstream_path.exists() else "missing"
    lines = [
        f"# {mode.name}",
        "",
        "## Purpose",
        mode.description,
        "",
        "## Upstream Mirror",
        f"- Source: {upstream_hint}",
        f"- Snapshot available: {upstream_status}",
        "",
        "## Codex Adaptation",
        "- This package is adapted for Codex-hosted execution rather than Claude Code host hooks.",
        "- Claude-only preambles, AskUserQuestion formatting, and telemetry hooks stay in the vendored upstream copy for reference.",
        "- Local execution should follow the runtime contract below.",
        "",
        "## Runtime Contract",
        f"- workflow_plugin_id: {mode.workflow_plugin_id}",
        f"- entry_mode: {mode.entry_mode or 'n/a'}",
        f"- stop_after: {mode.stop_after or 'n/a'}",
        f"- runtime_ready: {str(mode.runtime_ready).lower()}",
        f"- report_only: {str(mode.report_only).lower()}",
        f"- fixer_allowed: {str(mode.fixer_allowed).lower()}",
        "",
        "## Required Inputs",
        *([f"- {item}" for item in mode.required_inputs] or ["- None."]),
        "",
        "## Expected Artifacts",
        *([f"- {item}" for item in mode.expected_artifacts] or ["- None."]),
        "",
        "## Notes",
        "- The vendored upstream skill remains the reference source of behavior and wording.",
        "- The agentsystem workflow/runtime is the execution host of record.",
        "",
    ]
    return "\n".join(lines).strip() + "\n"


if __name__ == "__main__":
    for item in render_codex_skill_adapters(ROOT_DIR):
        print(json.dumps(item, ensure_ascii=False))
