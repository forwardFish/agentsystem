from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


RuntimeRunsLoader = Callable[[int], list[dict[str, Any]]]
RuntimeShowcaseLoader = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RuntimeSurface:
    dashboard_asset: str | None = None
    showcase_loader: RuntimeShowcaseLoader | None = None
    runs_loader: RuntimeRunsLoader | None = None


@dataclass(frozen=True, slots=True)
class ProjectRegistration:
    id: str
    name: str
    description: str
    tasks_dir: Path
    story_status_registry: Path
    story_acceptance_review_registry: Path
    runtime_surface: RuntimeSurface | None = None

    @property
    def has_runtime(self) -> bool:
        return self.runtime_surface is not None and self.runtime_surface.showcase_loader is not None
