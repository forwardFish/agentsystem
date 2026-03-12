# Python SDK

Python 侧接入点：

- `agent_system_framework.framework.AgentSystemFramework`
- `agent_system_framework.sdk.python.KernelAgent`
- `agent_system_framework.sdk.python.KernelArtifact`

业务仓库应自行实现 `KernelAgent`，并在自己的仓库中准备规则目录，再通过 `register_agent(..., spec_root=...)` 接入。
