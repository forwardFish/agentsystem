from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SkillMetadata:
    name: str
    version: str
    entry_point: str
    description: str


class SkillRegistry:
    def __init__(self, registry_path: str | Path):
        self.registry_path = Path(registry_path).resolve()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry: dict[str, list[SkillMetadata]] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            self._save_registry()
            return
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.registry = {
            name: [SkillMetadata(**item) for item in versions]
            for name, versions in payload.items()
        }

    def _save_registry(self) -> None:
        payload = {name: [asdict(item) for item in versions] for name, versions in self.registry.items()}
        self.registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def register_skill(self, metadata: SkillMetadata) -> None:
        versions = self.registry.setdefault(metadata.name, [])
        if any(item.version == metadata.version for item in versions):
            raise ValueError(f"Skill {metadata.name} version {metadata.version} already exists")
        versions.append(metadata)
        self._save_registry()

    def resolve_skill(self, name: str, version: str | None = None) -> SkillMetadata:
        versions = self.registry.get(name)
        if not versions:
            raise ValueError(f"Skill not registered: {name}")
        if version:
            for item in versions:
                if item.version == version:
                    return item
            raise ValueError(f"Skill version not found: {name}@{version}")
        return sorted(versions, key=lambda item: item.version, reverse=True)[0]

    def list_available_skills(self) -> list[str]:
        return sorted(self.registry.keys())

    def load_skill_function(self, name: str, version: str | None = None):
        metadata = self.resolve_skill(name, version)
        module_name, func_name = metadata.entry_point.split(":")
        module = importlib.import_module(module_name)
        return getattr(module, func_name)
