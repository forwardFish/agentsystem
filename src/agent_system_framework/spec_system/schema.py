from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RepoPolicy:
    rule_version: str
    shard_affinity: str = "agent_id"
    resource_limits: dict[str, int] = field(default_factory=dict)
    compliance_base_rules: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolPolicy:
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    permission_scope: str = "task"


@dataclass(slots=True)
class ContractSpec:
    contract_id: str
    description: str = ""
    required_fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class StyleGuide:
    language_rules: dict[str, Any] = field(default_factory=dict)
    format_rules: dict[str, Any] = field(default_factory=dict)
    review_checkpoints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TestTargets:
    unit_test: dict[str, Any] = field(default_factory=dict)
    integration_test: dict[str, Any] = field(default_factory=dict)
    contract_test: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SpecBundle:
    repo_policy: RepoPolicy
    tool_policy: ToolPolicy
    contracts: dict[str, ContractSpec]
    style_guide: StyleGuide
    test_targets: TestTargets
    sources: dict[str, str]

    def get_contract(self, contract_id: str) -> ContractSpec:
        if contract_id not in self.contracts:
            raise SpecError(f"Unknown contract: {contract_id}")
        return self.contracts[contract_id]


class SpecError(ValueError):
    """Raised when rules are invalid or incomplete."""
