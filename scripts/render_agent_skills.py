from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

import sys

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.orchestration.agent_manifest_registry import get_agent_manifest
from agentsystem.orchestration.skill_mode_registry import SkillModeSpec, get_skill_mode, list_skill_modes
from agentsystem.orchestration.workflow_registry import get_workflow_plugin


PLACEHOLDER_PATTERN = re.compile(r"\[\[([a-zA-Z0-9_]+)\]\]")


def render_all_agent_skills(root_dir: str | Path = ROOT_DIR) -> list[dict[str, str]]:
    root_path = Path(root_dir).resolve()
    rendered: list[dict[str, str]] = []
    for mode in list_skill_modes("software_engineering"):
        rendered.append(render_agent_skill(mode.mode_id, root_path))
    return rendered


def render_agent_skill(mode_id: str, root_dir: str | Path = ROOT_DIR) -> dict[str, str]:
    root_path = Path(root_dir).resolve()
    mode = get_skill_mode(mode_id, "software_engineering")
    plugin = get_workflow_plugin(mode.workflow_plugin_id)
    template_dir = (root_path / mode.template_dir).resolve()
    template_path = template_dir / "AGENT.md.tmpl"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    skill_path = template_dir / "SKILL.md"
    manifest_path = template_dir / "agent.manifest.json"
    context = _build_context(mode, plugin, root_path)
    rendered_skill = _render_template(template_path.read_text(encoding="utf-8"), context)
    _validate_rendered_text(rendered_skill, template_path)
    compiled_manifest = _build_compiled_manifest(mode, plugin, context, template_path, skill_path)

    skill_path.write_text(rendered_skill, encoding="utf-8")
    manifest_path.write_text(json.dumps(compiled_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    validate_rendered_agent_package(template_dir)

    return {
        "mode_id": mode.mode_id,
        "template_path": str(template_path),
        "skill_path": str(skill_path),
        "manifest_path": str(manifest_path),
    }


def validate_rendered_agent_package(package_dir: str | Path) -> bool:
    package_path = Path(package_dir).resolve()
    template_path = package_path / "AGENT.md.tmpl"
    skill_path = package_path / "SKILL.md"
    manifest_path = package_path / "agent.manifest.json"
    if not template_path.exists() or not skill_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Incomplete agent package: {package_path}")

    skill_text = skill_path.read_text(encoding="utf-8")
    _validate_rendered_text(skill_text, skill_path)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflow_plugin_id = str(payload.get("workflow_plugin_id") or "").strip()
    if not workflow_plugin_id:
        raise ValueError(f"{manifest_path} missing workflow_plugin_id")
    plugin = get_workflow_plugin(workflow_plugin_id)
    if str(payload.get("workflow_manifest_path") or "") != plugin.manifest_path:
        raise ValueError(f"{manifest_path} workflow_manifest_path drift detected")

    agent_manifest_ids = payload.get("agent_manifest_ids") or []
    if not isinstance(agent_manifest_ids, list) or not agent_manifest_ids:
        raise ValueError(f"{manifest_path} must contain agent_manifest_ids")
    for agent_manifest_id in agent_manifest_ids:
        get_agent_manifest(str(agent_manifest_id))

    required_markers = [
        f"workflow_plugin_id: {workflow_plugin_id}",
        f"entry_mode: {payload.get('entry_mode')}",
        f"stop_after: {payload.get('stop_after')}",
    ]
    missing_markers = [item for item in required_markers if item not in skill_text]
    if missing_markers:
        raise ValueError(f"{skill_path} missing rendered markers: {missing_markers}")
    return True


def _build_context(mode: SkillModeSpec, plugin, root_path: Path) -> dict[str, str]:
    agent_manifests = [get_agent_manifest(agent_id) for agent_id in mode.agent_manifest_ids]
    return {
        "name": mode.name,
        "mode_id": mode.mode_id,
        "version": mode.version,
        "description": mode.description,
        "workflow_plugin_id": mode.workflow_plugin_id,
        "workflow_manifest_path": plugin.manifest_path,
        "entry_mode": mode.entry_mode,
        "stop_after": mode.stop_after,
        "report_only": str(mode.report_only).lower(),
        "fixer_allowed": str(mode.fixer_allowed).lower(),
        "default_browser_qa_mode": mode.default_browser_qa_mode or "none",
        "allowed_tools_yaml": _yaml_list(mode.allowed_tools, indent=0),
        "allowed_tools_bullets": _bullet_list(mode.allowed_tools),
        "required_inputs_yaml": _yaml_list(mode.required_inputs, indent=0),
        "required_inputs_bullets": _bullet_list(mode.required_inputs),
        "expected_artifacts_yaml": _yaml_list(mode.expected_artifacts, indent=0),
        "expected_artifacts_bullets": _bullet_list(mode.expected_artifacts),
        "agent_manifest_ids_bullets": _bullet_list(mode.agent_manifest_ids),
        "agent_manifest_paths_bullets": _bullet_list([item.manifest_path for item in agent_manifests]),
        "template_source": str((root_path / mode.template_dir / "AGENT.md.tmpl").resolve()),
        "skill_output": str((root_path / mode.template_dir / "SKILL.md").resolve()),
    }


def _build_compiled_manifest(
    mode: SkillModeSpec,
    plugin,
    context: dict[str, str],
    template_path: Path,
    skill_path: Path,
) -> dict[str, Any]:
    agent_manifests = [get_agent_manifest(agent_id) for agent_id in mode.agent_manifest_ids]
    return {
        "mode_id": mode.mode_id,
        "name": mode.name,
        "version": mode.version,
        "description": mode.description,
        "workflow_plugin_id": mode.workflow_plugin_id,
        "workflow_manifest_path": plugin.manifest_path,
        "entry_mode": mode.entry_mode,
        "stop_after": mode.stop_after,
        "report_only": mode.report_only,
        "fixer_allowed": mode.fixer_allowed,
        "default_browser_qa_mode": mode.default_browser_qa_mode,
        "allowed_tools": list(mode.allowed_tools),
        "required_inputs": list(mode.required_inputs),
        "expected_artifacts": list(mode.expected_artifacts),
        "agent_manifest_ids": list(mode.agent_manifest_ids),
        "agent_manifest_paths": [item.manifest_path for item in agent_manifests],
        "template_path": str(template_path),
        "skill_path": str(skill_path),
        "skill_mode_manifest_path": mode.manifest_path,
        "metadata": {
            **mode.metadata,
            "template_source": context["template_source"],
            "skill_output": context["skill_output"],
        },
    }


def _render_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"Missing template variable: {key}")
        return context[key]

    return PLACEHOLDER_PATTERN.sub(replace, template)


def _validate_rendered_text(content: str, source: Path) -> None:
    unresolved = PLACEHOLDER_PATTERN.findall(content)
    if unresolved:
        raise ValueError(f"{source} contains unresolved placeholders: {sorted(set(unresolved))}")


def _yaml_list(items: tuple[str, ...], indent: int = 0) -> str:
    prefix = " " * indent
    if not items:
        return f"{prefix}[]"
    return "\n".join(f"{prefix}- {item}" for item in items)


def _bullet_list(items: list[str] | tuple[str, ...]) -> str:
    if not items:
        return "- None."
    return "\n".join(f"- {item}" for item in items)


if __name__ == "__main__":
    for result in render_all_agent_skills(ROOT_DIR):
        print(json.dumps(result, ensure_ascii=False))
