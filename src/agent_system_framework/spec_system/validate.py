from __future__ import annotations

import json
from pathlib import Path

from agent_system_framework.spec_system.parser import FileSpecLoader
from agent_system_framework.spec_system.version_manager import RuleVersionManager


def main() -> int:
    spec_dir = Path(__file__).resolve().parents[3] / "docs" / "examples" / "minimal-specs"
    bundle = FileSpecLoader(spec_dir).load()
    summary = {
        "spec_dir": str(spec_dir),
        "rule_version": bundle.repo_policy.rule_version,
        "contracts": sorted(bundle.contracts.keys()),
        "tool_allowlist": bundle.tool_policy.allowlist,
        "rule_snapshot": RuleVersionManager().snapshot(bundle.sources),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
