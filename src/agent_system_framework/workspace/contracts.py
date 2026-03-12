from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    name: str
    description: str
    stack: dict[str, dict[str, str]]
    git: dict[str, str]


def load_contract_mapping(target_repo: Path, contract_name: str) -> dict[str, Any]:
    return _load_mapping(target_repo / ".agents" / contract_name)


def load_project_config(target_repo: Path) -> ProjectConfig:
    payload = load_contract_mapping(target_repo, "project.yaml")
    return ProjectConfig(
        name=str(payload["name"]),
        description=str(payload["description"]),
        stack=_normalize_mapping(payload["stack"], "stack"),
        git=_normalize_mapping(payload["git"], "git"),
    )


def load_commands_config(target_repo: Path) -> dict[str, list[str]]:
    payload = load_contract_mapping(target_repo, "commands.yaml")
    commands_payload = payload.get("commands", payload)
    if not isinstance(commands_payload, dict):
        raise ValueError("commands.yaml must contain a mapping or a top-level 'commands' mapping")
    commands: dict[str, list[str]] = {}
    for phase, values in commands_payload.items():
        if not isinstance(phase, str):
            raise ValueError("command phase names must be strings")
        if phase == "start":
            continue
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"commands for phase {phase!r} must be a list of strings")
        commands[phase] = list(values)
    return commands


def _load_mapping(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - exercised only when YAML fallback is needed
            raise ValueError(
                f"{path} must be JSON-compatible YAML when PyYAML is unavailable"
            ) from exc
        payload = yaml.safe_load(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a mapping object")
    return payload


def _normalize_mapping(payload: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return payload
