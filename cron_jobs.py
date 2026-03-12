from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentsystem.runtime.agent_daemon import AgentDaemon


def main() -> None:
    daemon = AgentDaemon(ROOT_DIR)
    while True:
        daemon.run_cycle()
        time.sleep(300)


if __name__ == "__main__":
    main()
