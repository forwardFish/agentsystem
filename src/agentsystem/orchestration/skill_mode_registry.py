from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentsystem.orchestration.agent_manifest_registry import get_agent_manifest
from agentsystem.orchestration.workflow_registry import get_workflow_plugin


BASE_DIR = Path(__file__).resolve().parents[3]
SKILL_MODE_DIR = BASE_DIR / "config" / "skill_modes"


@dataclass(frozen=True, slots=True)
class SkillModeSpec:
    mode_id: str
    name: str
    version: str
    description: str
    workflow_plugin_id: str
    entry_mode: str
    stop_after: str
    report_only: bool
    fixer_allowed: bool
    default_browser_qa_mode: str | None = None
    allowed_tools: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    agent_manifest_ids: tuple[str, ...] = ()
    template_dir: str = ""
    manifest_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def apply_to_task(self, task: dict[str, Any]) -> dict[str, Any]:
        runtime_task = dict(task)
        runtime_task["workflow_plugin"] = self.workflow_plugin_id
        runtime_task["skill_mode"] = self.mode_id
        runtime_task["skill_mode_name"] = self.name
        runtime_task["skill_mode_description"] = self.description
        runtime_task["skill_mode_manifest_path"] = self.manifest_path
        runtime_task["skill_entry_mode"] = self.entry_mode
        runtime_task["stop_after"] = self.stop_after
        runtime_task["fixer_allowed"] = self.fixer_allowed
        runtime_task["browser_qa_report_only"] = self.report_only
        if self.default_browser_qa_mode and not runtime_task.get("browser_qa_mode"):
            runtime_task["browser_qa_mode"] = self.default_browser_qa_mode
        return runtime_task


def get_skill_mode(mode_id: str, workflow_plugin_id: str = "software_engineering") -> SkillModeSpec:
    registry = _load_skill_mode_registry()
    key = (workflow_plugin_id, mode_id)
    if key not in registry:
        raise KeyError(f"Unknown skill mode: {workflow_plugin_id}:{mode_id}")
    return registry[key]


def resolve_runtime_task(task: dict[str, Any]) -> tuple[dict[str, Any], SkillModeSpec | None]:
    mode_id = str(task.get("skill_mode") or "").strip()
    if not mode_id:
        return dict(task), None
    workflow_plugin_id = str(task.get("workflow_plugin") or "software_engineering").strip() or "software_engineering"
    spec = get_skill_mode(mode_id, workflow_plugin_id)
    return spec.apply_to_task(task), spec


def list_skill_modes(workflow_plugin_id: str = "software_engineering") -> list[SkillModeSpec]:
    registry = _load_skill_mode_registry()
    return [value for (plugin_id, _), value in registry.items() if plugin_id == workflow_plugin_id]


def _load_skill_mode_registry() -> dict[tuple[str, str], SkillModeSpec]:
    registry: dict[tuple[str, str], SkillModeSpec] = {}
    if not SKILL_MODE_DIR.exists():
        raise FileNotFoundError(f"Skill mode directory not found: {SKILL_MODE_DIR}")
    for manifest_path in sorted(SKILL_MODE_DIR.glob("*.yaml")):
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{manifest_path} must contain a mapping")
        workflow_plugin_id = str(payload.get("workflow_plugin_id") or "").strip()
        if not workflow_plugin_id:
            raise ValueError(f"{manifest_path} must define workflow_plugin_id")
        plugin = get_workflow_plugin(workflow_plugin_id)
        plugin_node_ids = {node.node_id for node in plugin.nodes}
        modes = payload.get("modes") or []
        if not isinstance(modes, list) or not modes:
            raise ValueError(f"{manifest_path} must define at least one mode")
        for item in modes:
            spec = _build_skill_mode(item, manifest_path, workflow_plugin_id, plugin_node_ids)
            registry[(workflow_plugin_id, spec.mode_id)] = spec
    return registry


def _build_skill_mode(
    payload: Any,
    manifest_path: Path,
    workflow_plugin_id: str,
    plugin_node_ids: set[str],
) -> SkillModeSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} mode entries must be mappings")
    mode_id = str(payload.get("mode_id") or "").strip()
    entry_mode = str(payload.get("entry_mode") or "").strip()
    stop_after = str(payload.get("stop_after") or "").strip()
    if not mode_id or not entry_mode or not stop_after:
        raise ValueError(f"{manifest_path} mode entries must define mode_id, entry_mode, and stop_after")
    if entry_mode not in plugin_node_ids:
        raise ValueError(f"{manifest_path} mode {mode_id!r} references unknown entry_mode {entry_mode!r}")
    if stop_after not in plugin_node_ids:
        raise ValueError(f"{manifest_path} mode {mode_id!r} references unknown stop_after {stop_after!r}")

    agent_manifest_ids = _as_tuple(payload.get("agent_manifest_ids"))
    for agent_manifest_id in agent_manifest_ids:
        get_agent_manifest(agent_manifest_id)

    template_dir = str(payload.get("template_dir") or "").strip()
    if template_dir:
        resolved_template_dir = (BASE_DIR / template_dir).resolve()
        if not resolved_template_dir.exists():
            raise ValueError(f"{manifest_path} references missing template_dir {template_dir!r}")

    return SkillModeSpec(
        mode_id=mode_id,
        name=str(payload.get("name") or mode_id),
        version=str(payload.get("version") or "v1"),
        description=str(payload.get("description") or ""),
        workflow_plugin_id=workflow_plugin_id,
        entry_mode=entry_mode,
        stop_after=stop_after,
        report_only=bool(payload.get("report_only")),
        fixer_allowed=bool(payload.get("fixer_allowed", True)),
        default_browser_qa_mode=_optional_str(payload.get("default_browser_qa_mode")),
        allowed_tools=_as_tuple(payload.get("allowed_tools")),
        required_inputs=_as_tuple(payload.get("required_inputs")),
        expected_artifacts=_as_tuple(payload.get("expected_artifacts")),
        agent_manifest_ids=agent_manifest_ids,
        template_dir=template_dir,
        manifest_path=str(manifest_path),
        metadata=_mapping(payload.get("metadata")),
    )


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("skill mode list fields must be arrays")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
