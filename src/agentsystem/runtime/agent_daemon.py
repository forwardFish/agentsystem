from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from agentsystem.runtime.agent_runtime import AgentRuntime
from agentsystem.skills_runtime.change_scope import get_low_risk_tasks
from agentsystem.skills_runtime.pr_desc_gen import get_pending_prs


Notifier = Callable[[str], None]


@dataclass
class AgentDaemon:
    repo_root: Path
    notifier: Notifier = print
    requirement_agent: AgentRuntime = field(init=False)
    dev_agent: AgentRuntime = field(init=False)
    test_agent: AgentRuntime = field(init=False)
    review_agent: AgentRuntime = field(init=False)

    def __post_init__(self) -> None:
        self.repo_root = Path(self.repo_root).resolve()
        self.requirement_agent = AgentRuntime("requirement", self.repo_root)
        self.dev_agent = AgentRuntime("dev", self.repo_root)
        self.test_agent = AgentRuntime("test", self.repo_root)
        self.review_agent = AgentRuntime("review", self.repo_root)

    def run_cycle(self) -> dict[str, str]:
        summary: dict[str, str] = {}

        low_risk_tasks = get_low_risk_tasks(repo_root=self.repo_root)
        if low_risk_tasks:
            if self.dev_agent.state.value != "RUNNING":
                self.dev_agent.start("low_risk_tasks_detected")
            summary["dev"] = f"started:{len(low_risk_tasks)}"
        else:
            self.dev_agent.idle("no_low_risk_tasks")
            summary["dev"] = "idle"

        self.test_agent.start("scheduled_test_run")
        self.test_agent.idle("test_cycle_complete")
        summary["test"] = "scheduled"

        self.review_agent.start("scheduled_review_run")
        pending_prs = get_pending_prs(repo_root=self.repo_root)
        if pending_prs:
            self.review_agent.gate("pending_pr_approval")
            self.dev_agent.gate("pending_pr_approval")
            self.notifier(f"Pending PRs require approval: {pending_prs}")
            summary["review"] = f"gated:{len(pending_prs)}"
        else:
            self.review_agent.idle("no_pending_prs")
            summary["review"] = "idle"

        return summary
