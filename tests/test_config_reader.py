from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.adapters.config_reader import RepoBConfigReader


class RepoBConfigReaderTestCase(unittest.TestCase):
    def test_missing_agents_dir_falls_back_to_repo_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "tools" / "gate_check").mkdir(parents=True)
            (repo_root / "tools" / "gate_check" / "validate_norms.py").write_text("print('ok')\n", encoding="utf-8")
            (repo_root / "tests").mkdir()

            config = RepoBConfigReader(repo_root).load_all_config()

            self.assertEqual(config.project["git"]["default_branch"], "main")
            self.assertEqual(config.project["git"]["working_branch_prefix"], "agent/")
            self.assertEqual(config.commands["lint"], ["python tools/gate_check/validate_norms.py"])
            self.assertEqual(config.commands["gate_check"], ["python tools/gate_check/validate_norms.py"])
            self.assertEqual(config.commands["test"], ["python -m pytest -q"])


if __name__ == "__main__":
    unittest.main()
