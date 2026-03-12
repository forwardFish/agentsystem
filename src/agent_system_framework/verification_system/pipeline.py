from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent_system_framework.core.agent_meta_model import AgentMetaModel
from agent_system_framework.core.state_schema import TaskState
from agent_system_framework.runtime_engine.event_bus import Event, EventBus
from agent_system_framework.runtime_engine.read_write_sep import WriteStore
from agent_system_framework.spec_system.schema import ContractSpec, SpecBundle


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


class VerificationSystem:
    def __init__(self, *, event_bus: EventBus, write_store: WriteStore) -> None:
        self._event_bus = event_bus
        self._write_store = write_store

    def verify(self, *, task: TaskState, meta: AgentMetaModel, spec: SpecBundle) -> VerificationResult:
        reasons = self._validate_contract(asdict(task), spec.get_contract(meta.input_contract))
        output_payload = self._write_store.artifacts.get(task.output_ref, {})
        reasons.extend(self._validate_contract(output_payload, spec.get_contract(meta.output_contract)))
        reasons.extend(self._evaluate_compliance(task=task, output_payload=output_payload, spec=spec))
        result = VerificationResult(passed=not reasons, reasons=reasons)
        self._event_bus.publish(
            Event(
                name="verification.passed" if result.passed else "verification.failed",
                payload={"task_id": task.task_id, "rule_version": spec.repo_policy.rule_version},
                trace_id=task.metadata.trace_id,
            )
        )
        return result

    def _validate_contract(self, payload: dict[str, Any], contract: ContractSpec) -> list[str]:
        reasons: list[str] = []
        for path in contract.required_fields:
            if self._lookup(payload, path) is None:
                reasons.append(f"contract:{contract.contract_id}:missing:{path}")
        return reasons

    def _evaluate_compliance(self, *, task: TaskState, output_payload: dict[str, Any], spec: SpecBundle) -> list[str]:
        reasons: list[str] = []
        for rule in spec.repo_policy.compliance_base_rules:
            if rule == "output_ref.required" and not task.output_ref:
                reasons.append("missing output_ref")
            elif rule == "artifact_refs.min_1" and not task.artifact_refs:
                reasons.append("missing artifact_refs")
            elif rule == "trace_id.required" and not task.metadata.trace_id:
                reasons.append("missing trace_id")
            elif rule == "output.result.required" and "result" not in output_payload:
                reasons.append("missing output.result")
            elif rule == "output.result.non_empty" and not output_payload.get("result"):
                reasons.append("empty output.result")
        return reasons

    def _lookup(self, payload: dict[str, Any], path: str) -> Any | None:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current
