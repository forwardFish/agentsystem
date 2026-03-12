from __future__ import annotations

from dataclasses import replace

from agent_system_framework.core.agent_meta_model import AgentMetaModel, AgentStatus
from agent_system_framework.core.idempotency import IdempotencyStore
from agent_system_framework.core.lifecycle import LifecycleManager
from agent_system_framework.core.permission import PermissionPolicy
from agent_system_framework.core.state_schema import TaskState, TaskStatus
from agent_system_framework.execution_system.agent_pool import KernelAgent
from agent_system_framework.governance_system.sandbox_manager import SandboxManager
from agent_system_framework.runtime_engine.checkpoint import CheckpointStore
from agent_system_framework.runtime_engine.event_bus import Event, EventBus
from agent_system_framework.runtime_engine.read_write_sep import WriteStore
from agent_system_framework.spec_system.schema import SpecBundle


class ExecutionSystem:
    def __init__(
        self,
        *,
        event_bus: EventBus,
        write_store: WriteStore,
        checkpoint_store: CheckpointStore,
        idempotency_store: IdempotencyStore,
        lifecycle: LifecycleManager,
        permissions: PermissionPolicy,
        sandbox_manager: SandboxManager,
    ) -> None:
        self._event_bus = event_bus
        self._write_store = write_store
        self._checkpoint_store = checkpoint_store
        self._idempotency_store = idempotency_store
        self._lifecycle = lifecycle
        self._permissions = permissions
        self._sandbox_manager = sandbox_manager

    def run(self, *, task: TaskState, agent: KernelAgent, meta: AgentMetaModel, spec: SpecBundle) -> TaskState:
        cached = self._idempotency_store.get(task.task_id)
        if isinstance(cached, TaskState):
            return cached

        if not agent.can_handle(task):
            raise ValueError(f"Agent {meta.agent_id} cannot handle task {task.task_id}")
        self._permissions.validate_tools(meta.allowed_tools, ["emit_event", "write_artifact"])
        meta.status = self._lifecycle.transition(meta.status, AgentStatus.RUNNING)

        sandbox = self._sandbox_manager.allocate(meta.agent_id, spec.repo_policy.resource_limits)
        running_task = replace(task, status=TaskStatus.RUNNING, stage="execution")
        self._write_store.tasks[running_task.task_id] = running_task
        self._checkpoint_store.save(running_task.task_id, {"stage": running_task.stage, "sandbox_id": sandbox.session.sandbox_id})

        result = agent.execute(running_task)
        if len(result.artifacts) > spec.repo_policy.resource_limits.get("max_artifacts", 8):
            raise ValueError("artifact count exceeds repo policy")
        if len(result.emitted_events) > spec.repo_policy.resource_limits.get("max_events", 8):
            raise ValueError("event count exceeds repo policy")

        for artifact_id, payload in result.artifacts.items():
            self._write_store.artifacts[artifact_id] = payload
        self._write_store.artifacts[result.output_ref] = {
            "task_id": running_task.task_id,
            "kind": "output",
            **result.output_payload,
        }

        completed = replace(
            running_task,
            status=TaskStatus.SUCCESS,
            stage="completed",
            output_ref=result.output_ref,
            artifact_refs=list(result.artifacts.keys()),
        )
        self._write_store.tasks[completed.task_id] = completed
        self._checkpoint_store.save(completed.task_id, {"stage": completed.stage, "status": completed.status})
        for event_name, payload in result.emitted_events:
            self._permissions.validate_event(meta.allowed_events, event_name)
            self._event_bus.publish(Event(name=event_name, payload=payload, trace_id=completed.metadata.trace_id))
        self._event_bus.publish(
            Event(
                name="agent.completed",
                payload={"task_id": completed.task_id, "output_ref": completed.output_ref},
                trace_id=completed.metadata.trace_id,
            )
        )
        self._idempotency_store.record(completed.task_id, completed)
        meta.status = self._lifecycle.transition(meta.status, AgentStatus.COMPLETED)
        return completed
