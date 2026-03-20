# agentsystem

## Skill Mode Status

Runtime-ready modes:
- `plan-eng-review`
- `browse`
- `qa`
- `qa-only`

Template-only preserved modes:
- `plan-ceo-review`
- `plan-design-review`
- `design-consultation`
- `review`
- `ship`
- `qa-design-review`
- `setup-browser-cookies`
- `retro`
- `document-release`

Template-only modes are rendered into `.claude/agents/<mode>/SKILL.md` and `agent.manifest.json`,
but they are intentionally not wired into `DevWorkflow` execution yet.

## Auto Orchestration Update

当前默认执行口径已经升级为“自动编排优先，`skill_mode` 只做显式 override”。

- 所有 Story 默认具备 `plan-eng-review`、`review`、`qa-only`
- `qa` 不再需要手动点名；高风险 Story 或 baseline QA 出现 blocking findings 时会自动升级
- UI Story 默认走 `browser_qa`
- 非 UI Story 默认走 `runtime_qa`
- `plan-ceo-review`、`design-consultation`、`setup-browser-cookies`、`ship` 默认只作为 advisory 提示，不自动执行
- `document-release` 和 `retro` 在 Sprint 收口时由 sprint hooks 生成产物

### Task Card

```yaml
project: versefina | finahunt
agent_policy: auto | manual
requires_auth: true | false
skill_mode: optional-explicit-override
```

- `agent_policy: auto`：走自动编排
- `agent_policy: manual`：只跑显式 `skill_mode`
- 显式 `skill_mode` 优先级高于自动策略
- `requires_auth` 只接受显式声明，不做隐式猜测

### CLI

```powershell
python cli.py run-task --task-file D:\path\to\task.yaml --env test --project versefina
python cli.py run-task --task-file D:\path\to\task.yaml --env test --project finahunt
python cli.py run-sprint --sprint-dir D:\path\to\sprint_dir --env test --project versefina
python cli.py run-sprint --sprint-dir D:\path\to\sprint_dir --env test --project finahunt
```

如果下面的旧章节还在强调“必须手动写 `skill_mode` 才能跑”，请以本节为准。

`agentsystem` 是一个面向本地 Git 仓库的 Agent 控制平面。  
它把“像 gstack 那样的工作模式”落成了三层：

1. `workflow manifest`
   负责真实执行链路。
2. `agent manifest`
   负责每个节点的身份、能力、工具和规则绑定。
3. `AGENT.md.tmpl -> SKILL.md`
   负责宿主入口层，让模式可以像 `plan-eng-review`、`browse`、`qa` 一样被人和宿主工具理解。

当前仓库已经内置了 4 个模式：

- `plan-eng-review`
- `browse`
- `qa`
- `qa-only`

这份 README 不是讲概念，而是讲一个“新的项目”如何接进来并真正跑起来。

## 1. 当前能力

如果你熟悉 `gstack`，可以把 `agentsystem` 现在理解成：

- `plan-eng-review`
  等价于“先出架构、边界条件和测试计划，再决定怎么改代码”。
- `browse`
  等价于“给系统一个轻量的浏览能力，做页面/预览探测，但不修代码”。
- `qa`
  等价于“测试 + Browser QA + Fixer 回路”。
- `qa-only`
  等价于“只出 QA 报告，不修代码”。

和 `gstack` 的关键区别：

- 这里的真实执行源头是 `workflow/agent manifests`，不是 `SKILL.md`
- 这里的模式入口目前是 `task card + skill_mode`，不是 CLI slash command
- 这里的 Browser QA 是“轻量 runtime probe + session scaffold”，不是完整的 Chromium daemon

## 2. 目录说明

接入新项目时，最重要的是这几个目录：

```text
agentsystem/
  .claude/agents/                 # 编译后的模式包
    plan-eng-review/
      AGENT.md.tmpl
      SKILL.md
      agent.manifest.json
    browse/
    qa/
    qa-only/
  config/
    workflows/
      software_engineering.yaml   # 默认研发工作流
    agents/software_engineering/  # 各执行节点 manifest
    skill_modes/
      software_engineering.yaml   # 模式 -> 工作流桥接层
  scripts/
    render_agent_skills.py        # 模板编译脚本
  src/agentsystem/
    graph/dev_workflow.py         # 运行时入口
    orchestration/skill_mode_registry.py
  repo-worktree/                  # 临时工作树
  runs/                           # 审计日志和归档产物
```

## 3. 新项目接入总流程

一个新的项目要接进 `agentsystem`，按下面 6 步做。

### 第一步：准备目标项目仓库

目标项目必须是一个本地 Git 仓库，并且至少提供 `.agents/` 目录。

最小结构：

```text
your-project/
  .agents/
    project.yaml
    rules.yaml
    commands.yaml
    review_policy.yaml
    contracts.yaml
    style_guide.md
```

建议同时提供：

```text
your-project/
  CLAUDE.md
```

`CLAUDE.md` 目前不是强依赖，但对前端/后端 builder 的上下文质量有帮助。

### 第二步：填写目标项目的 `.agents` 配置

最小可用示例：

`project.yaml`

```yaml
name: my-app
stack:
  frontend:
    path: apps/web
  backend:
    path: apps/api
git:
  default_branch: main
```

`rules.yaml`

```yaml
protected_paths: []
```

`commands.yaml`

```yaml
lint:
  - python -c "print('lint ok')"
test:
  - python -c "print('test ok')"
format: []
```

`review_policy.yaml`

```yaml
{}
```

`contracts.yaml`

```yaml
{}
```

`style_guide.md`

```md
# Style Guide

Prefer existing project structure and naming conventions.
```

说明：

- `commands.yaml` 里的 `lint/test/format` 会被 tester 和 main production 流程读取
- Browser QA 目前不会自动启动你的 dev server，所以如果你想跑 `browse/qa`，目标 URL 必须已经可访问

### 第三步：把 agentsystem 指向你的项目

当前 `agentsystem` 的运行配置还沿用了旧字段名 `repo.versefina`。  
接入新项目时，直接把它改成你的项目路径即可。

修改：

- [test.yaml](/d:/lyh/agent/agent-frame/agentsystem/config/test.yaml)
- [production.yaml](/d:/lyh/agent/agent-frame/agentsystem/config/production.yaml)

把：

```yaml
repo:
  versefina: "D:\\lyh\\agent\\agent-frame\\versefina"
```

改成：

```yaml
repo:
  versefina: "D:\\path\\to\\your-project"
```

现在代码读取的就是这个路径。

如果你后面要把 `agentsystem` 做成真正的多项目 CLI，再把这个字段改名成更泛化的 `target_repo`。

## 4. 先编译模式包

接入完项目后，先生成 `.claude/agents` 下的最终产物。

```powershell
cd D:\lyh\agent\agent-frame\agentsystem
python cli.py render-agent-skills
```

如果只想生成一个模式：

```powershell
python cli.py render-agent-skills --mode-id qa
```

生成结果：

```text
.claude/agents/<mode>/
  AGENT.md.tmpl
  SKILL.md
  agent.manifest.json
```

这里三者的关系是：

- `AGENT.md.tmpl`
  源文件，负责行为模板
- `SKILL.md`
  编译后的宿主说明书
- `agent.manifest.json`
  编译后的机器可读模式配置

真源头顺序固定为：

`workflow manifest -> agent manifest -> skill mode manifest -> AGENT.md.tmpl -> SKILL.md`

## 5. 模式说明

### `plan-eng-review`

用途：

- 先跑需求解析
- 再跑架构评审
- 产出实现结构、边界条件、测试计划
- 不进入 builder、不改代码

运行行为：

- `entry_mode = requirement_analysis`
- `stop_after = architecture_review`
- `report_only = true`
- `fixer_allowed = false`

主要产物：

- `.meta/<repo>/architecture_review/architecture_review_report.md`
- `.meta/<repo>/architecture_review/test_plan.json`

适合场景：

- 一个 Story 还没开始写
- 你想先像 `gstack /plan-eng-review` 那样把结构想清楚

### `browse`

用途：

- 只跑 Browser QA
- 只出报告
- 不修代码

运行行为：

- `entry_mode = browser_qa`
- `stop_after = browser_qa`
- `report_only = true`
- `fixer_allowed = false`

主要产物：

- `.meta/<repo>/browser_qa/browser_qa_report.md`
- `.meta/<repo>/browser_runtime/session.json`
- `.meta/<repo>/browser_runtime/probes/*.json`

适合场景：

- 你已经有一个预览地址
- 只想做一次轻量可视/页面健康检查

### `qa`

用途：

- 跑 tester
- 跑 browser_qa
- 有 blocking finding 时允许进入 fixer

运行行为：

- `entry_mode = tester`
- `stop_after = browser_qa`
- `report_only = false`
- `fixer_allowed = true`

主要产物：

- `.meta/<repo>/test/test_report.md`
- `.meta/<repo>/browser_qa/browser_qa_report.md`
- `.meta/<repo>/browser_runtime/session.json`
- `.meta/<repo>/fixer/fix_report.md`

适合场景：

- 你想做“能修”的 QA 闭环
- 需要 health score、ship readiness 和修复证据

### `qa-only`

用途：

- 走 QA 路径
- 但永远不进入 fixer
- 只保留错误报告和证据

运行行为：

- `entry_mode = tester`
- `stop_after = browser_qa`
- `report_only = true`
- `fixer_allowed = false`

适合场景：

- 只要 bug report，不要系统改代码

## 6. 如何写 task card

当前不是 slash command 模式。  
你要通过一个 task yaml 指定 `skill_mode`。

注意：

- `mode` 仍然保留给 `Fast/Safe`
- 新模式字段是 `skill_mode`

### 示例 1：`plan-eng-review`

```yaml
task_id: PLAN-001
task_name: Plan dashboard rebuild
story_id: PLAN-001
sprint: Sprint X
epic: Epic X.Y
blast_radius: L1
execution_mode: Safe
mode: Safe
goal: Plan how to rebuild the account dashboard page and its summary API.
acceptance_criteria:
  - architecture review report exists
  - test plan exists
constraints:
  - stay inside the declared scope
related_files:
  - apps/web/src/app/dashboard/page.tsx
  - apps/api/src/routes/dashboard.py
primary_files:
  - apps/web/src/app/dashboard/page.tsx
  - apps/api/src/routes/dashboard.py
skill_mode: plan-eng-review
```

### 示例 2：`browse`

```yaml
task_id: BROWSE-001
task_name: Browse preview home page
story_id: BROWSE-001
blast_radius: L1
execution_mode: Safe
mode: Safe
goal: Inspect the preview home page and produce a browser QA report.
acceptance_criteria:
  - browser report exists
related_files:
  - apps/web/src/app/page.tsx
primary_files:
  - apps/web/src/app/page.tsx
skill_mode: browse
browser_urls:
  - http://127.0.0.1:3000/
```

### 示例 3：`qa`

```yaml
task_id: QA-001
task_name: QA dashboard story
story_id: QA-001
blast_radius: L1
execution_mode: Safe
mode: Safe
goal: Run QA for the dashboard page and fix blocking findings if they appear.
acceptance_criteria:
  - test report exists
  - browser QA report exists
related_files:
  - apps/web/src/app/dashboard/page.tsx
primary_files:
  - apps/web/src/app/dashboard/page.tsx
skill_mode: qa
browser_urls:
  - http://127.0.0.1:3000/dashboard
browser_qa_mode: quick
```

### 示例 4：`qa-only`

```yaml
task_id: QAONLY-001
task_name: QA-only dashboard story
story_id: QAONLY-001
blast_radius: L1
execution_mode: Safe
mode: Safe
goal: Run report-only QA for the dashboard page.
acceptance_criteria:
  - browser QA report exists
related_files:
  - apps/web/src/app/dashboard/page.tsx
primary_files:
  - apps/web/src/app/dashboard/page.tsx
skill_mode: qa-only
browser_urls:
  - http://127.0.0.1:3000/dashboard
```

## 7. 如何运行

### 运行单个任务

```powershell
cd D:\lyh\agent\agent-frame\agentsystem
python cli.py run-task --task-file D:\path\to\task.yaml --env test
```

### 打开 Dashboard

```powershell
python cli.py dashboard --host 127.0.0.1 --port 8010
```

### 验证旧 `.skill.md`

这是 legacy 入口，只用于旧技能文件：

```powershell
python cli.py validate-skill
```

它不校验新的 `.claude/agents` 模式包。

## 8. 运行后会产生什么

### 工作树

执行时会创建：

```text
agentsystem/repo-worktree/<task-id>/
```

用于隔离本次改动。

### 审计日志

执行成功后会写：

```text
agentsystem/runs/prod_audit_<task-id>.json
```

这里能看到：

- `task_payload`
- `skill_mode`
- `workflow_plugin_id`
- `workflow_manifest_path`
- `workflow_agent_manifest_ids`
- 各节点结果

### 归档产物

执行成功后会归档到：

```text
agentsystem/runs/artifacts/<task-id>/
```

现在已经会归档：

- `architecture_review/`
- `browser_qa/`
- `browser_runtime/`
- `pr_prep/`
- `review/`
- `code_acceptance/`
- `acceptance/`
- `delivery/`

## 9. 推荐的新项目接入顺序

如果你接的是一个新项目，我建议按这个顺序用：

1. 先用 `plan-eng-review`
   先把文件范围、边界条件、测试计划跑出来。
2. 再用正常开发 Story
   如果需要代码修改，就走默认 `software_engineering` 主链。
3. 再用 `browse`
   对预览地址做第一轮轻量探测。
4. 最后用 `qa` 或 `qa-only`
   做 ship-readiness 或纯报告式 QA。

## 10. 当前限制

这部分很重要，避免你把它想成已经完全等同于 `gstack`：

- 还没有 CLI slash command，例如 `/qa`
- 还没有完整的浏览器常驻 daemon
- `browse/qa` 目前依赖可访问 URL，不会自动起你的前端 dev server
- `config/test.yaml` 和 `production.yaml` 还沿用旧字段 `repo.versefina`
- `skills/*.skill.md` 是 legacy，不是新的主体系

## 11. 你真正要改哪些地方

接一个新项目时，通常只需要改这几处：

1. 目标项目的 `.agents/*`
2. `agentsystem/config/test.yaml`
3. `agentsystem/config/production.yaml`
4. 新建 task card
5. 如有必要，补你的 `commands.yaml`

只有当你要扩展新的模式时，才需要再改：

1. `config/skill_modes/software_engineering.yaml`
2. `.claude/agents/<new-mode>/AGENT.md.tmpl`
3. `scripts/render_agent_skills.py`

## 12. 推荐命令清单

```powershell
cd D:\lyh\agent\agent-frame\agentsystem

# 1) 编译 4 个模式包
python cli.py render-agent-skills

# 2) 执行 plan-eng-review
python cli.py run-task --task-file D:\path\to\plan_task.yaml --env test

# 3) 执行 browse
python cli.py run-task --task-file D:\path\to\browse_task.yaml --env test

# 4) 执行 qa
python cli.py run-task --task-file D:\path\to\qa_task.yaml --env test

# 5) 打开 dashboard
python cli.py dashboard --host 127.0.0.1 --port 8010
```

## 13. 参考文件

- [software_engineering skill modes](/d:/lyh/agent/agent-frame/agentsystem/config/skill_modes/software_engineering.yaml)
- [default workflow](/d:/lyh/agent/agent-frame/agentsystem/config/workflows/software_engineering.yaml)
- [QA skill](/d:/lyh/agent/agent-frame/agentsystem/.claude/agents/qa/SKILL.md)
- [Plan Eng Review skill](/d:/lyh/agent/agent-frame/agentsystem/.claude/agents/plan-eng-review/SKILL.md)
- [render_agent_skills.py](/d:/lyh/agent/agent-frame/agentsystem/scripts/render_agent_skills.py)
