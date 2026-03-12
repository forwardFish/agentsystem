from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentsystem.skills_runtime.risk_classify import classify_risk
from agentsystem.skills_runtime.test_report import check_test_result


PROFILE_MAP = {
    "dev": "dev-rw",
    "review": "review-ro",
    "test": "test-rw",
    "requirement": "requirement-ro",
    "release": "release-guarded",
}


class PermissionManager:
    def __init__(self, profile_path: str | Path):
        payload = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8"))
        self.profiles: dict[str, dict[str, Any]] = payload["profiles"]

    def check_permission(self, agent_type: str, action: str, *, context: dict[str, Any] | None = None) -> bool:
        profile_name = PROFILE_MAP.get(agent_type)
        if not profile_name:
            return False
        profile = self.profiles.get(profile_name)
        if not profile:
            return False
        if action in profile.get("deny", []):
            return False
        if action not in profile.get("allow", []):
            return False
        if agent_type == "release":
            return all(self._check_guard(guard, context=context or {}) for guard in profile.get("guards", []))
        return True

    def _check_guard(self, guard: str, *, context: dict[str, Any]) -> bool:
        repo_root = context.get("repo_root")
        if guard == "low_risk_only":
            return classify_risk(repo_root=repo_root) == "low"
        if guard == "test_passed":
            return check_test_result(repo_root=repo_root) == "passed"
        return False
