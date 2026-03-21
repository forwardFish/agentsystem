from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from agentsystem.agents.acceptance_gate_agent import acceptance_gate_node
from agentsystem.agents.architecture_review_agent import architecture_review_node
from agentsystem.agents.browse_agent import browse_node
from agentsystem.agents.backend_dev_agent import backend_dev_node
from agentsystem.agents.browser_qa_agent import browser_qa_node
from agentsystem.agents.code_acceptance_agent import code_acceptance_node
from agentsystem.agents.code_style_reviewer_agent import code_style_review_node
from agentsystem.agents.database_agent import database_dev_node
from agentsystem.agents.design_consultation_agent import design_consultation_node
from agentsystem.agents.document_release_agent import document_release_node
from agentsystem.agents.devops_agent import devops_dev_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node
from agentsystem.agents.frontend_dev_agent import frontend_dev_node
from agentsystem.agents.investigate_agent import investigate_node
from agentsystem.agents.office_hours_agent import office_hours_node
from agentsystem.agents.plan_ceo_review_agent import plan_ceo_review_node
from agentsystem.agents.plan_design_review_agent import plan_design_review_node
from agentsystem.agents.qa_design_review_agent import qa_design_review_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.retro_agent import retro_node
from agentsystem.agents.review_agent import review_node
from agentsystem.agents.runtime_qa_agent import runtime_qa_node
from agentsystem.agents.security_agent import security_node
from agentsystem.agents.setup_browser_cookies_agent import setup_browser_cookies_node
from agentsystem.agents.ship_agent import ship_node
from agentsystem.agents.sync_agent import sync_merge_node
from agentsystem.agents.test_agent import test_node
from agentsystem.agents.workspace_prep_agent import workspace_prep_node


BASE_DIR = Path(__file__).resolve().parents[3]
AGENT_MANIFEST_DIR = BASE_DIR / "config" / "agents"

NodeHandler = Callable[..., dict]


HANDLER_CATALOG: dict[str, NodeHandler] = {
    "office_hours_node": office_hours_node,
    "requirement_analysis_node": requirement_analysis_node,
    "plan_ceo_review_node": plan_ceo_review_node,
    "architecture_review_node": architecture_review_node,
    "investigate_node": investigate_node,
    "browse_node": browse_node,
    "plan_design_review_node": plan_design_review_node,
    "design_consultation_node": design_consultation_node,
    "setup_browser_cookies_node": setup_browser_cookies_node,
    "workspace_prep_node": workspace_prep_node,
    "backend_dev_node": backend_dev_node,
    "frontend_dev_node": frontend_dev_node,
    "database_dev_node": database_dev_node,
    "devops_dev_node": devops_dev_node,
    "sync_merge_node": sync_merge_node,
    "code_style_review_node": code_style_review_node,
    "test_node": test_node,
    "browser_qa_node": browser_qa_node,
    "runtime_qa_node": runtime_qa_node,
    "qa_design_review_node": qa_design_review_node,
    "fix_node": fix_node,
    "security_node": security_node,
    "review_node": review_node,
    "code_acceptance_node": code_acceptance_node,
    "acceptance_gate_node": acceptance_gate_node,
    "doc_node": doc_node,
    "ship_node": ship_node,
    "document_release_node": document_release_node,
    "retro_node": retro_node,
}


@dataclass(frozen=True, slots=True)
class AgentManifest:
    agent_id: str
    name: str
    description: str
    handler_id: str
    handler: NodeHandler
    agent_role: str
    plane: str
    capabilities: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()
    trigger_events: tuple[str, ...] = ()
    tool_scope: tuple[str, ...] = ()
    verification_tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    manifest_path: str = ""


def get_agent_manifest(agent_id: str) -> AgentManifest:
    registry = _load_agent_manifest_registry()
    if agent_id not in registry:
        raise KeyError(f"Unknown agent manifest: {agent_id}")
    return registry[agent_id]


def _load_agent_manifest_registry() -> dict[str, AgentManifest]:
    registry: dict[str, AgentManifest] = {}
    if not AGENT_MANIFEST_DIR.exists():
        raise FileNotFoundError(f"Agent manifest directory not found: {AGENT_MANIFEST_DIR}")
    for manifest_path in sorted(AGENT_MANIFEST_DIR.rglob("*.yaml")):
        manifest = _load_agent_manifest(manifest_path)
        registry[manifest.agent_id] = manifest
    return registry


def _load_agent_manifest(manifest_path: Path) -> AgentManifest:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path} must contain a mapping")

    agent_id = str(payload.get("agent_id") or "").strip()
    handler_id = str(payload.get("handler") or "").strip()
    if not agent_id or not handler_id:
        raise ValueError(f"{manifest_path} must define agent_id and handler")
    handler = HANDLER_CATALOG.get(handler_id)
    if handler is None:
        raise ValueError(f"{manifest_path} references unknown handler {handler_id!r}")

    return AgentManifest(
        agent_id=agent_id,
        name=str(payload.get("name") or agent_id),
        description=str(payload.get("description") or ""),
        handler_id=handler_id,
        handler=handler,
        agent_role=str(payload.get("agent_role") or agent_id),
        plane=str(payload.get("plane") or "build"),
        capabilities=_as_tuple(payload.get("capabilities")),
        policy_refs=_as_tuple(payload.get("policy_refs")),
        trigger_events=_as_tuple(payload.get("trigger_events")),
        tool_scope=_as_tuple(payload.get("tool_scope")),
        verification_tags=_as_tuple(payload.get("verification_tags")),
        metadata=_mapping(payload.get("metadata")),
        manifest_path=str(manifest_path),
    )


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("agent manifest list fields must be arrays")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
