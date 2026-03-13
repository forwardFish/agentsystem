from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentsystem.dashboard import hooks


class DashboardHooksTestCase(unittest.TestCase):
    def test_send_log_writes_jsonl_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            events_dir = Path(tmp) / "events"
            with patch.object(hooks, "EVENTS_DIR", events_dir):
                hooks.send_log("task-demo", "info", "demo message", {"step": "tester"})
                logs = hooks.get_local_logs("task-demo")

            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["task_id"], "task-demo")
            self.assertEqual(logs[0]["type"], "log")
            self.assertEqual(logs[0]["payload"]["message"], "demo message")


if __name__ == "__main__":
    unittest.main()
