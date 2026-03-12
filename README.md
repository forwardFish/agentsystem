# agent-system-framework

纯 L0 Agent 系统内核库。

## 定位

- 本仓库只包含与业务完全解耦的 Agent 系统工程内核。
- 不包含任何业务示例代码、业务插件、业务前端、业务后端。
- 业务仓库应独立存在，并通过 SDK/API 依赖本仓库接入。

## 当前目录

- `src/agent_system_framework`
- `src/agent_system_framework/core`
- `src/agent_system_framework/spec_system`
- `src/agent_system_framework/execution_system`
- `src/agent_system_framework/verification_system`
- `src/agent_system_framework/governance_system`
- `src/agent_system_framework/runtime_engine`
- `src/agent_system_framework/sdk`
- `docs/architecture`
- `docs/api`
- `docs/examples`
- `tests`

## 验证

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
python -m compileall src tests
python -m agent_system_framework.spec_system.validate
```
