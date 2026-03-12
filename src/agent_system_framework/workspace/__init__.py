"""Workspace bootstrap helpers for dual-repository collaboration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "BootstrapResult",
    "BranchManager",
    "CommandExecutor",
    "DeliveryResult",
    "GitHubPullRequestManager",
    "ProjectConfig",
    "bootstrap_target_repo",
    "deliver_change",
    "load_project_config",
]

if TYPE_CHECKING:
    from agent_system_framework.workspace.bootstrap import BootstrapResult
    from agent_system_framework.workspace.branching import BranchManager
    from agent_system_framework.workspace.commands import CommandExecutor
    from agent_system_framework.workspace.contracts import ProjectConfig
    from agent_system_framework.workspace.delivery import DeliveryResult
    from agent_system_framework.workspace.github import GitHubPullRequestManager


_EXPORT_MAP = {
    "BootstrapResult": ("agent_system_framework.workspace.bootstrap", "BootstrapResult"),
    "BranchManager": ("agent_system_framework.workspace.branching", "BranchManager"),
    "CommandExecutor": ("agent_system_framework.workspace.commands", "CommandExecutor"),
    "DeliveryResult": ("agent_system_framework.workspace.delivery", "DeliveryResult"),
    "GitHubPullRequestManager": ("agent_system_framework.workspace.github", "GitHubPullRequestManager"),
    "ProjectConfig": ("agent_system_framework.workspace.contracts", "ProjectConfig"),
    "bootstrap_target_repo": ("agent_system_framework.workspace.bootstrap", "bootstrap_target_repo"),
    "deliver_change": ("agent_system_framework.workspace.delivery", "deliver_change"),
    "load_project_config": ("agent_system_framework.workspace.contracts", "load_project_config"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attr_name = _EXPORT_MAP[name]
    module = __import__(module_name, fromlist=[attr_name])
    return getattr(module, attr_name)
