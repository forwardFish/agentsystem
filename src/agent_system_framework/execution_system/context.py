from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextBundle:
    mounted_specs: list[str] = field(default_factory=list)
    mounted_memory: list[str] = field(default_factory=list)


class ContextManager:
    def mount(self, *, spec_paths: list[str], memory_refs: list[str] | None = None) -> ContextBundle:
        return ContextBundle(mounted_specs=spec_paths, mounted_memory=memory_refs or [])
