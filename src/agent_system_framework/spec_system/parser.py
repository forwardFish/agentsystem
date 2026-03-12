from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_system_framework.spec_system.schema import (
    ContractSpec,
    RepoPolicy,
    SpecBundle,
    SpecError,
    StyleGuide,
    TestTargets,
    ToolPolicy,
)


class RuleParserAgent:
    """Parses repository-level rule files into executable structures."""

    def parse_repo_policy(self, path: Path) -> RepoPolicy:
        return RepoPolicy(**self._parse_json_yaml(path))

    def parse_tool_policy(self, path: Path) -> ToolPolicy:
        return ToolPolicy(**self._parse_json_yaml(path))

    def parse_contracts(self, path: Path) -> dict[str, ContractSpec]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        contracts = payload.get("contracts", {})
        return {name: ContractSpec(contract_id=name, **value) for name, value in contracts.items()}

    def parse_style_guide(self, path: Path) -> StyleGuide:
        text = path.read_text(encoding="utf-8")
        start = text.find("```json")
        if start == -1:
            raise SpecError(f"Style guide must contain a json fenced block: {path}")
        start += len("```json")
        end = text.find("```", start)
        if end == -1:
            raise SpecError(f"Style guide json block is not closed: {path}")
        return StyleGuide(**json.loads(text[start:end].strip()))

    def parse_test_targets(self, path: Path) -> TestTargets:
        return TestTargets(**self._parse_json_yaml(path))

    def _parse_json_yaml(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecError(
                f"{path.name} must use JSON-compatible YAML so it can be parsed without extra dependencies"
            ) from exc


class FileSpecLoader:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.parser = RuleParserAgent()

    def load(self) -> SpecBundle:
        files = {
            "repo_policy": self.directory / "RepoPolicy.yaml",
            "tool_policy": self.directory / "ToolPolicy.yaml",
            "contracts": self.directory / "ContractSpec.json",
            "style_guide": self.directory / "StyleGuide.md",
            "test_targets": self.directory / "TestTargets.yaml",
        }
        for path in files.values():
            if not path.exists():
                raise SpecError(f"Missing rule file: {path}")
        bundle = SpecBundle(
            repo_policy=self.parser.parse_repo_policy(files["repo_policy"]),
            tool_policy=self.parser.parse_tool_policy(files["tool_policy"]),
            contracts=self.parser.parse_contracts(files["contracts"]),
            style_guide=self.parser.parse_style_guide(files["style_guide"]),
            test_targets=self.parser.parse_test_targets(files["test_targets"]),
            sources={name: str(path) for name, path in files.items()},
        )
        self._validate(bundle)
        return bundle

    def _validate(self, bundle: SpecBundle) -> None:
        if not bundle.repo_policy.rule_version:
            raise SpecError("RepoPolicy.rule_version is required")
        if bundle.tool_policy.permission_scope not in {"task", "agent", "shard"}:
            raise SpecError("ToolPolicy.permission_scope must be one of task/agent/shard")
        if not bundle.contracts:
            raise SpecError("At least one contract must be defined")
        for contract_id, contract in bundle.contracts.items():
            if contract.contract_id != contract_id:
                raise SpecError(f"Contract id mismatch for {contract_id}")
            if not contract.required_fields:
                raise SpecError(f"Contract {contract_id} must define required_fields")
        if not bundle.style_guide.review_checkpoints:
            raise SpecError("StyleGuide must define review checkpoints")
        checks = {
            "unit_test": bundle.test_targets.unit_test,
            "integration_test": bundle.test_targets.integration_test,
            "contract_test": bundle.test_targets.contract_test,
        }
        for name, config in checks.items():
            if "command" not in config:
                raise SpecError(f"{name} must define a command")
