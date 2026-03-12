from __future__ import annotations

from dataclasses import dataclass

from agent_system_framework.governance_system.audit import AuditLogger
from agent_system_framework.governance_system.human_approval import NoopHumanApproval
from agent_system_framework.governance_system.observability import ObservabilityModule
from agent_system_framework.runtime_engine.event_bus import Event, EventBus
from agent_system_framework.verification_system.pipeline import VerificationResult


@dataclass(slots=True)
class GovernanceReport:
    approved: bool
    reasons: list[str]


class GovernanceSystem:
    def __init__(
        self,
        *,
        audit_logger: AuditLogger,
        event_bus: EventBus,
        human_approval: NoopHumanApproval,
        observability: ObservabilityModule,
    ) -> None:
        self._audit_logger = audit_logger
        self._event_bus = event_bus
        self._human_approval = human_approval
        self._observability = observability

    def govern(
        self,
        *,
        agent_id: str,
        task_id: str,
        trace_id: str,
        verification: VerificationResult,
        rule_snapshot: dict[str, str],
    ) -> GovernanceReport:
        approved = verification.passed
        reasons = list(verification.reasons)
        if not approved:
            self._human_approval.request(task_id=task_id, reasons=reasons)
        self._audit_logger.write(
            actor_id=agent_id,
            action="final_gate",
            trace_id=trace_id,
            payload={"task_id": task_id, "approved": approved, "reasons": reasons, "rule_snapshot": rule_snapshot},
        )
        self._event_bus.publish(
            Event(name="governance.final_gate", payload={"task_id": task_id, "approved": approved}, trace_id=trace_id)
        )
        self._observability.record_run(approved)
        return GovernanceReport(approved=approved, reasons=reasons)
