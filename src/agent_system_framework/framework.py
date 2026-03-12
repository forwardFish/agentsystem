from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from agent_system_framework.core.agent_meta_model import AgentMetaModel, AgentStatus, Plane
from agent_system_framework.core.idempotency import InMemoryIdempotencyStore
from agent_system_framework.core.lifecycle import LifecycleManager
from agent_system_framework.core.permission import PermissionPolicy
from agent_system_framework.core.state_schema import TaskMetadata, TaskState, TaskStatus
from agent_system_framework.execution_system.agent_pool import KernelAgent
from agent_system_framework.execution_system.engine import ExecutionSystem
from agent_system_framework.governance_system.audit import AuditLogger
from agent_system_framework.governance_system.human_approval import NoopHumanApproval
from agent_system_framework.governance_system.observability import ObservabilityModule
from agent_system_framework.governance_system.runtime import GovernanceSystem
from agent_system_framework.governance_system.sandbox_manager import SandboxManager
from agent_system_framework.runtime_engine.checkpoint import CheckpointStore
from agent_system_framework.runtime_engine.event_bus import EventBus
from agent_system_framework.runtime_engine.read_write_sep import ReadModelProjector, ReadStore, WriteStore
from agent_system_framework.runtime_engine.shard_manager import ShardManager
from agent_system_framework.spec_system.parser import FileSpecLoader
from agent_system_framework.spec_system.schema import SpecBundle, SpecError
from agent_system_framework.spec_system.version_manager import RuleVersionManager
from agent_system_framework.verification_system.pipeline import VerificationSystem


@dataclass(slots=True)
class RunResult:
    task: TaskState
    approved: bool
    reasons: list[str]


class AgentSystemFramework:
    def __init__(self) -> None:
        self.lifecycle = LifecycleManager()
        self.permissions = PermissionPolicy()
        self.idempotency = InMemoryIdempotencyStore()
        self.event_bus = EventBus()
        self.shard_manager = ShardManager()
        self.checkpoints = CheckpointStore()
        self.write_store = WriteStore()
        self.read_store = ReadStore()
        self.projector = ReadModelProjector(self.read_store)
        self.audit_logger = AuditLogger()
        self.observability = ObservabilityModule()
        self.sandbox_manager = SandboxManager()
        self.rule_versions = RuleVersionManager()
        self.execution_system = ExecutionSystem(
            event_bus=self.event_bus,
            write_store=self.write_store,
            checkpoint_store=self.checkpoints,
            idempotency_store=self.idempotency,
            lifecycle=self.lifecycle,
            permissions=self.permissions,
            sandbox_manager=self.sandbox_manager,
        )
        self.verification_system = VerificationSystem(event_bus=self.event_bus, write_store=self.write_store)
        self.governance_system = GovernanceSystem(
            audit_logger=self.audit_logger,
            event_bus=self.event_bus,
            human_approval=NoopHumanApproval(),
            observability=self.observability,
        )
        self.agents: dict[str, KernelAgent] = {}
        self.agent_specs: dict[str, SpecBundle] = {}
        for event_name in ("artifact.ready", "agent.completed", "verification.passed", "verification.failed", "governance.final_gate"):
            self.event_bus.subscribe(event_name, self.projector.project)

    def register_agent(self, agent: KernelAgent, spec_root: Path) -> AgentMetaModel:
        spec = FileSpecLoader(spec_root).load()
        meta = agent.meta
        self._validate_meta(meta, spec)
        meta.status = self.lifecycle.transition(meta.status, AgentStatus.REGISTERED)
        meta.status = self.lifecycle.transition(meta.status, AgentStatus.READY)
        self.agents[meta.agent_id] = agent
        self.agent_specs[meta.agent_id] = spec
        return meta

    def run_agent(self, agent_id: str, input_ref: str, *, plane: Plane = Plane.RUNTIME) -> RunResult:
        agent = self.agents[agent_id]
        spec = self.agent_specs[agent_id]
        task = self._new_task(agent_id=agent_id, input_ref=input_ref, plane=plane, spec=spec)
        task = self.execution_system.run(task=task, agent=agent, meta=agent.meta, spec=spec)
        verification = self.verification_system.verify(task=task, meta=agent.meta, spec=spec)
        governance = self.governance_system.govern(
            agent_id=agent_id,
            task_id=task.task_id,
            trace_id=task.metadata.trace_id,
            verification=verification,
            rule_snapshot=self.rule_versions.snapshot(spec.sources),
        )
        return RunResult(task=task, approved=governance.approved, reasons=governance.reasons)

    def _new_task(self, *, agent_id: str, input_ref: str, plane: Plane, spec: SpecBundle) -> TaskState:
        task_id = str(uuid4())
        shard_key = agent_id if spec.repo_policy.shard_affinity == "agent_id" else task_id
        return TaskState(
            task_id=task_id,
            run_id=str(uuid4()),
            shard_id=self.shard_manager.assign(shard_key),
            graph_type=plane,
            stage="created",
            status=TaskStatus.PENDING,
            input_ref=input_ref,
            rule_version=spec.repo_policy.rule_version,
            metadata=TaskMetadata(
                agent_id=agent_id,
                agent_version=self.agents[agent_id].meta.version,
                trace_id=str(uuid4()),
                upstream_event="task.created",
            ),
        )

    def _validate_meta(self, meta: AgentMetaModel, spec: SpecBundle) -> None:
        disallowed_tools = set(meta.allowed_tools) - set(spec.tool_policy.allowlist)
        denied_tools = set(meta.allowed_tools) & set(spec.tool_policy.denylist)
        if disallowed_tools or denied_tools:
            raise SpecError(
                f"Agent tools violate ToolPolicy: disallowed={sorted(disallowed_tools)}, denied={sorted(denied_tools)}"
            )
        spec.get_contract(meta.input_contract)
        spec.get_contract(meta.output_contract)
