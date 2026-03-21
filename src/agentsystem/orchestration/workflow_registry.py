from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from agentsystem.agents.acceptance_gate_agent import route_after_acceptance
from agentsystem.agents.architecture_review_agent import route_after_architecture_review
from agentsystem.agents.browse_agent import route_after_browse
from agentsystem.agents.browser_qa_agent import route_after_browser_qa
from agentsystem.agents.code_acceptance_agent import route_after_code_acceptance
from agentsystem.agents.code_style_reviewer_agent import route_after_code_style_review
from agentsystem.agents.design_consultation_agent import route_after_design_consultation
from agentsystem.agents.document_release_agent import route_after_document_release
from agentsystem.agents.fix_agent import route_after_fix
from agentsystem.agents.investigate_agent import route_after_investigate
from agentsystem.agents.office_hours_agent import route_after_office_hours
from agentsystem.agents.plan_ceo_review_agent import route_after_plan_ceo_review
from agentsystem.agents.plan_design_review_agent import route_after_plan_design_review
from agentsystem.agents.qa_design_review_agent import route_after_qa_design_review
from agentsystem.agents.retro_agent import route_after_retro
from agentsystem.agents.review_agent import route_after_review
from agentsystem.agents.router_agent import route_after_test, task_router
from agentsystem.agents.runtime_qa_agent import route_after_runtime_qa
from agentsystem.agents.setup_browser_cookies_agent import route_after_setup_browser_cookies
from agentsystem.agents.ship_agent import route_after_ship
from agentsystem.orchestration.agent_manifest_registry import AgentManifest, get_agent_manifest


BASE_DIR = Path(__file__).resolve().parents[3]
WORKFLOW_MANIFEST_DIR = BASE_DIR / "config" / "workflows"

RouterHandler = Callable[..., str | list[str]]


ROUTER_CATALOG: dict[str, RouterHandler] = {
    "task_router": task_router,
    "route_after_office_hours": route_after_office_hours,
    "route_after_plan_ceo_review": route_after_plan_ceo_review,
    "route_after_architecture_review": route_after_architecture_review,
    "route_after_investigate": route_after_investigate,
    "route_after_browse": route_after_browse,
    "route_after_plan_design_review": route_after_plan_design_review,
    "route_after_design_consultation": route_after_design_consultation,
    "route_after_setup_browser_cookies": route_after_setup_browser_cookies,
    "route_after_code_style_review": route_after_code_style_review,
    "route_after_test": route_after_test,
    "route_after_browser_qa": route_after_browser_qa,
    "route_after_runtime_qa": route_after_runtime_qa,
    "route_after_qa_design_review": route_after_qa_design_review,
    "route_after_fix": route_after_fix,
    "route_after_review": route_after_review,
    "route_after_code_acceptance": route_after_code_acceptance,
    "route_after_acceptance": route_after_acceptance,
    "route_after_ship": route_after_ship,
    "route_after_document_release": route_after_document_release,
    "route_after_retro": route_after_retro,
}


@dataclass(frozen=True, slots=True)
class WorkflowNodeSpec:
    node_id: str
    display_name: str
    manifest: AgentManifest

    @property
    def handler(self):
        return self.manifest.handler

    @property
    def agent_id(self) -> str:
        return self.manifest.agent_id

    @property
    def agent_role(self) -> str:
        return self.manifest.agent_role

    @property
    def plane(self) -> str:
        return self.manifest.plane

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.manifest.capabilities

    @property
    def policy_refs(self) -> tuple[str, ...]:
        return self.manifest.policy_refs

    @property
    def trigger_events(self) -> tuple[str, ...]:
        return self.manifest.trigger_events

    @property
    def tool_scope(self) -> tuple[str, ...]:
        return self.manifest.tool_scope

    @property
    def verification_tags(self) -> tuple[str, ...]:
        return self.manifest.verification_tags

    @property
    def manifest_path(self) -> str:
        return self.manifest.manifest_path


@dataclass(frozen=True, slots=True)
class WorkflowConditionalEdge:
    source: str
    router: RouterHandler
    router_id: str
    routes: dict[str, str]


@dataclass(frozen=True, slots=True)
class WorkflowPlugin:
    plugin_id: str
    name: str
    description: str
    entry_point: str
    nodes: tuple[WorkflowNodeSpec, ...]
    edges: tuple[tuple[str, str], ...]
    conditional_edges: tuple[WorkflowConditionalEdge, ...]
    policy_refs: tuple[str, ...] = ()
    trigger_events: tuple[str, ...] = ()
    verification_pipeline: tuple[str, ...] = ()
    human_approval_points: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    manifest_path: str = ""

    def node_specs(self) -> Iterable[WorkflowNodeSpec]:
        return self.nodes


def get_workflow_plugin(plugin_id: str = "software_engineering") -> WorkflowPlugin:
    registry = _load_manifest_registry()
    return registry.get(plugin_id) or registry["software_engineering"]


def _load_manifest_registry() -> dict[str, WorkflowPlugin]:
    plugins: dict[str, WorkflowPlugin] = {}
    if WORKFLOW_MANIFEST_DIR.exists():
        for manifest_path in sorted(WORKFLOW_MANIFEST_DIR.glob("*.yaml")):
            plugin = _load_workflow_manifest(manifest_path)
            plugins[plugin.plugin_id] = plugin
    if "software_engineering" not in plugins:
        raise FileNotFoundError(f"Default workflow manifest not found under {WORKFLOW_MANIFEST_DIR}")
    return plugins


def _load_workflow_manifest(manifest_path: Path) -> WorkflowPlugin:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} must contain a mapping")

    plugin_id = str(payload.get("plugin_id") or "").strip()
    if not plugin_id:
        raise ValueError(f"{manifest_path} must define plugin_id")

    nodes_payload = payload.get("nodes") or []
    if not isinstance(nodes_payload, list) or not nodes_payload:
        raise ValueError(f"{manifest_path} must define at least one node")

    node_specs = tuple(_build_node_spec(item, manifest_path) for item in nodes_payload)
    node_ids = {node.node_id for node in node_specs}
    entry_point = str(payload.get("entry_point") or "").strip()
    if entry_point not in node_ids:
        raise ValueError(f"{manifest_path} entry_point must reference an existing node")

    edges = tuple(_build_edge(item, manifest_path, node_ids) for item in payload.get("edges") or [])
    conditional_edges = tuple(
        _build_conditional_edge(item, manifest_path, node_ids) for item in payload.get("conditional_edges") or []
    )

    return WorkflowPlugin(
        plugin_id=plugin_id,
        name=str(payload.get("name") or plugin_id),
        description=str(payload.get("description") or ""),
        entry_point=entry_point,
        nodes=node_specs,
        edges=edges,
        conditional_edges=conditional_edges,
        policy_refs=_as_tuple(payload.get("policy_refs")),
        trigger_events=_as_tuple(payload.get("trigger_events")),
        verification_pipeline=_as_tuple(payload.get("verification_pipeline")),
        human_approval_points=_as_tuple(payload.get("human_approval_points")),
        metadata=_mapping(payload.get("metadata")),
        manifest_path=str(manifest_path),
    )


def _build_node_spec(payload: Any, manifest_path: Path) -> WorkflowNodeSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} node entries must be mappings")
    node_id = str(payload.get("node_id") or "").strip()
    agent_manifest_id = str(payload.get("agent_manifest") or "").strip()
    if not node_id or not agent_manifest_id:
        raise ValueError(f"{manifest_path} nodes must define node_id and agent_manifest")
    return WorkflowNodeSpec(
        node_id=node_id,
        display_name=str(payload.get("display_name") or node_id),
        manifest=get_agent_manifest(agent_manifest_id),
    )


def _build_edge(payload: Any, manifest_path: Path, node_ids: set[str]) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} edge entries must be mappings")
    source = str(payload.get("source") or "").strip()
    target = str(payload.get("target") or "").strip()
    if source not in node_ids:
        raise ValueError(f"{manifest_path} edge source {source!r} is not a registered node")
    if target != "__end__" and target not in node_ids:
        raise ValueError(f"{manifest_path} edge target {target!r} is not a registered node")
    return source, target


def _build_conditional_edge(payload: Any, manifest_path: Path, node_ids: set[str]) -> WorkflowConditionalEdge:
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} conditional edge entries must be mappings")
    source = str(payload.get("source") or "").strip()
    router_id = str(payload.get("router") or "").strip()
    routes_payload = payload.get("routes") or {}
    if source not in node_ids:
        raise ValueError(f"{manifest_path} conditional edge source {source!r} is not a registered node")
    router = ROUTER_CATALOG.get(router_id)
    if router is None:
        raise ValueError(f"{manifest_path} references unknown router {router_id!r}")
    if not isinstance(routes_payload, dict) or not routes_payload:
        raise ValueError(f"{manifest_path} conditional edge {source!r} must declare routes")

    routes: dict[str, str] = {}
    for route_name, target in routes_payload.items():
        target_name = str(target).strip()
        if target_name != "__end__" and target_name not in node_ids:
            raise ValueError(f"{manifest_path} route target {target_name!r} is not a registered node")
        routes[str(route_name).strip()] = target_name
    return WorkflowConditionalEdge(source=source, router=router, router_id=router_id, routes=routes)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("workflow manifest list fields must be arrays")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
