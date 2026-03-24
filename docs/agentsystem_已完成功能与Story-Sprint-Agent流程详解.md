# agentsystem 已完成功能与 Story / Sprint / Agent 流程详解

最后更新：2026-03-23

## 1. 这份文档是干什么的

这份文档专门解释 `D:\lyh\agent\agent-frame\agentsystem` 目前已经做完、已经能跑、已经在代码里落地的能力。

重点不是抽象概念，而是回答下面这些实际问题：

1. `agentsystem` 现在到底已经完成了哪些功能。
2. 这个系统里“几十个 agent”分别是什么角色，什么时候被调用。
3. 一个 Story 从进入系统到完成交付，完整会经过哪些环节。
4. 一个 Sprint 是怎么从需求拆解、到 Story 排序、到跑完前后钩子、再到收口的。
5. 代码、报告、状态、交接文档分别写到哪里，为什么 fresh session 可以接着干。

如果你把 `agentsystem` 看成“Agent 驱动的软件工厂控制台”，这份文档就是它的操作系统说明书。

## 2. 先给结论：这个仓库现在已经实现了什么

按照当前代码实现，`agentsystem` 已经不只是一个 dashboard，也不只是一个 CLI。它已经具备下面 9 类完整能力：

### 2.1 需求拆解与 backlog 生成

- 能把长需求拆成 `Sprint -> Epic -> Story`。
- 能在 `tasks/backlog_v1/` 下落出正式 backlog 目录结构。
- 能生成：
  - `sprint_overview.md`
  - `sprint_plan.md`
  - `execution_order.txt`
  - 每个 epic 的说明文档
  - 每个 story 的 yaml task card
- 对金融世界类需求、Agent Marketplace 类需求，代码里已经有内置 blueprint。
- 如果环境里有 LLM，也支持直接让 LLM 产出 backlog 结构。

对应实现：

- `src/agentsystem/agents/requirements_analyst_agent.py`
- CLI 命令：`analyze`、`split_requirement`、`auto-deliver`

### 2.2 Story 任务卡规范化与准入

- 每个 Story 都会走 `TaskCard` 结构校验。
- Story 会被补齐：
  - `story_inputs`
  - `story_process`
  - `story_outputs`
  - `verification_basis`
- 正式执行前会做 Story admission：
  - 是否有 acceptance criteria
  - 是否有 file scope
  - UI Story 是否有 `browser_urls` / `preview_base_url`
  - Sprint 级自动运行是否拿到了 pre-hook 产物

对应实现：

- `src/agentsystem/core/task_card.py`
- `src/agentsystem/orchestration/workflow_admission.py`

### 2.3 Agent 自动激活策略

- 系统会根据 Story 类型自动判断：
  - 是不是 UI Story
  - 是不是 bugfix
  - 是不是 planning request
  - 是不是 sprint closeout
  - 风险等级高不高
  - 是否需要浏览器、设计审查、认证态 QA
- 然后自动推导：
  - `required_modes`
  - `advisory_modes`
  - `qa_strategy`
  - `effective_qa_mode`

也就是说，很多时候你不用手工指定所有 agent，只要 task card 足够完整，系统会自动把该走的链路补出来。

对应实现：

- `src/agentsystem/orchestration/agent_activation_resolver.py`

### 2.4 LangGraph 工作流编排

- 系统已经把软件工程流程抽成 `software_engineering` 工作流插件。
- 这个插件不是几条脚本，而是一张正式图：
  - 有节点
  - 有普通边
  - 有条件边
  - 有 router
  - 有 manifest
- 当前工作流里已经注册了 29 个节点。
- 每个节点都有：
  - agent manifest
  - handler
  - capabilities
  - plane
  - tool scope

对应实现：

- `config/workflows/software_engineering.yaml`
- `src/agentsystem/orchestration/workflow_registry.py`
- `src/agentsystem/graph/dev_workflow.py`

### 2.5 Story 级完整交付链

当前代码已经实现并测试覆盖了完整 Story 交付链，核心顺序是：

1. Requirement
2. Architecture Review
3. Workspace Prep
4. Builder 分流
5. Sync Merge
6. Code Style Review
7. Test
8. Browser QA / Runtime QA
9. Review
10. Code Acceptance
11. Acceptance Gate
12. Doc Writer

如果中间失败，还会进入 `Fixer -> 回到失败节点` 的回路。

而且不仅“跑完了”，每个阶段还会写正式产物到 `.meta/<repo>/...`。

### 2.6 UI / Browser / 设计链

对于 UI Story，系统已经落地了完整的浏览器和设计链，不再只是“写完代码再看一眼页面”：

- `browse`
- `setup-browser-cookies`
- `plan-design-review`
- `design-consultation`
- `browser_qa`
- `qa_design_review`
- `design-review`

它们会产出：

- 浏览器 session
- observation
- screenshot
- 设计评分卡
- `DESIGN.md`
- before / after evidence

### 2.7 Sprint 前后钩子

系统已经实现 Sprint 级别的 pre-hooks 和 post-hooks：

- pre-hooks：
  - sprint agent advice
  - office hours framing
  - plan-ceo-review package
  - sprint framing artifact
  - gstack parity audit
- post-hooks：
  - ship advice
  - document release report
  - retro report
  - sprint close bundle
  - 特定 Sprint 的运行时验证

对应实现：

- `src/agentsystem/orchestration/sprint_hooks.py`

### 2.8 Dashboard 可视化

dashboard 已经不是单纯任务列表，而是一个多项目执行控制台：

- 可看 tasks
- 可看 task detail
- 可看协作链路
- 可看 backlog / sprint / story 层级
- 可看 acceptance review
- 可看运行时 showcase
- 可看 metrics
- 可 websocket 追踪任务执行事件
- 支持项目切换：
  - `agentsystem`
  - `versefina`
  - `finahunt`
  - `agentHire`（无 runtime surface）

对应实现：

- `src/agentsystem/dashboard/main.py`
- `src/agentsystem/dashboard/static/index.html`
- `src/agentsystem/dashboard/static/story.html`

### 2.9 运行时记忆、恢复、交接

这是整个系统非常关键的一层，已经做出来了：

- checkpoint
- resume state
- story status registry
- story acceptance review registry
- runtime coverage report
- handoff markdown
- failure snapshot

所以一个 fresh Codex session 不依赖聊天历史，也能从文件继续往下干。

对应实现：

- `src/agentsystem/orchestration/runtime_memory.py`

## 3. 这个系统的核心架构

`agentsystem` 可以分成 7 层。

### 3.1 输入层

输入分两种：

1. 大需求输入
   - 来自 `analyze` / `split_requirement`
   - 输出 backlog、sprint、story
2. 单 Story 输入
   - 来自 `run-task`
   - 输入是一个 task yaml

### 3.2 任务协议层

这一层负责把 Story 变成机器能执行的标准协议：

- `TaskCard`
- scope
- acceptance
- input / process / output / verification
- story_kind
- risk_level

### 3.3 编排策略层

这一层决定“该激活哪些 agent / mode”：

- `workflow_admission`
- `agent_activation_resolver`
- `skill_mode_registry`

### 3.4 工作流定义层

这一层不是业务逻辑，而是流程真相来源：

- workflow manifest
- agent manifest
- conditional edges
- router catalog

核心思想：

- 不是直接靠 prompt 把流程“说出来”
- 而是先把流程定义成 manifest，再由 LangGraph 执行

### 3.5 执行层

执行层是真正跑 agent handler 的地方：

- requirement
- architecture review
- builders
- QA
- review
- acceptance
- docs
- release

### 3.6 证据沉淀层

所有关键节点都要落产物：

- `.meta/<repo>/<mode>/...`
- `tasks/runtime/...`
- `runs/prod_audit_*.json`
- `runs/artifacts/<task-id>/...`

### 3.7 可视化与运营层

dashboard 从这些产物读取状态，形成：

- execution timeline
- story completion
- mode coverage
- sprint quality
- runtime showcase

## 4. 目录如何理解

### 4.1 最重要的目录

```text
agentsystem/
  cli.py
  config/
  src/agentsystem/
  docs/
  tasks/
  runs/
  repo-worktree/
  .claude/agents/
  vendors/gstack/
```

### 4.2 每个目录的职责

#### `cli.py`

统一入口。你平时操作系统，基本都从这里进：

- `run-task`
- `run-sprint`
- `auto-deliver`
- `analyze`
- `split_requirement`
- `render-agent-skills`
- `audit-gstack-parity`
- `dashboard`

#### `config/workflows/`

定义工作流图。

当前主工作流：

- `software_engineering.yaml`

#### `config/agents/software_engineering/`

定义每个 agent 的 manifest。

这里回答的是：

- 这个 agent 叫什么
- 属于哪个 plane
- 有什么能力
- 对应哪个 handler

#### `config/skill_modes/`

定义用户入口模式，也就是“从哪一段开始跑，到哪一段结束”。

比如：

- `plan-eng-review`
- `qa`
- `browse`
- `ship`

#### `src/agentsystem/agents/`

真正的 agent 实现都在这里。

#### `src/agentsystem/graph/`

把 workflow manifest 组装成 LangGraph 图。

#### `src/agentsystem/orchestration/`

这里是整个系统的大脑中枢，负责：

- agent 激活
- skill mode 解析
- workflow registry
- runtime memory
- sprint hooks
- workspace management

#### `tasks/`

计划资产与运行时注册表：

- backlog
- sprint
- story yaml
- story status registry
- story acceptance reviews
- tasks/runtime

#### `runs/`

正式运行审计与归档：

- `prod_audit_<task-id>.json`
- `artifacts/<task-id>/...`
- `events/<task-id>.jsonl`
- `sprints/<project>/<sprint>/...`

#### `repo-worktree/`

执行时的工作树与中间元数据区。

## 5. 三种“agent”要分清

很多人第一次看这个仓库会混淆，其实这里至少有 3 种不同概念的“agent”。

### 5.1 工作流节点 Agent

这是最重要的一种。

它们是 LangGraph 里的节点，比如：

- `requirement_analysis`
- `tester`
- `reviewer`
- `acceptance_gate`

这是“真正执行流程”的 agent。

### 5.2 Skill Mode

Skill mode 不是一个单节点 agent，而是一个“入口包装”。

比如：

- `plan-eng-review`
  - 从 `requirement_analysis` 进入
  - 在 `architecture_review` 停下
- `qa`
  - 从 `tester` 进入
  - 在 `browser_qa` 或 `runtime_qa` 一段停止
- `browse`
  - 走 report-only 浏览器观察路径

它是“用户怎么切入流程”的定义，不等于底层只有一个 agent。

### 5.3 `.claude/agents/` 模式包

这个目录里的内容是渲染后的 host-facing 包：

- `AGENT.md.tmpl`
- `SKILL.md`
- `agent.manifest.json`

它更多是“给宿主和技能系统看的包装层”，不是真正的编排真相源。

真正的真相顺序是：

1. workflow manifest
2. agent manifest
3. skill mode manifest
4. AGENT template
5. rendered SKILL

## 6. 当前工作流里的 29 个节点 Agent

下面这张表，是当前 `software_engineering` 工作流里真正注册的节点。

| 节点 | 角色 | 什么时候进入 | 核心作用 | 主要产物 |
| :--- | :--- | :--- | :--- | :--- |
| `office_hours` | 需求框定 | 新需求 / 新 Sprint / planning | 通过 6 个高杠杆问题重新框定问题 | `office_hours_report.md`、`forcing_questions.json` |
| `requirement_analysis` | Story 解析 | 几乎所有 Story 起点 | 把 task card 变成 subtasks、范围、验收清单 | `parsed_requirement.json`、`intent_confirmation.md` |
| `plan_ceo_review` | 产品级规划 | planning 场景或显式调用 | 把需求升级成 requirement doc、opportunity map | `product_review_report.md`、`docs/requirements/*.md` |
| `architecture_review` | 工程规划 | build 前 | 输出实现结构、边界、失败模式、测试计划 | `architecture_review_report.md`、`test_plan.json` |
| `investigate` | 根因调查 | bugfix / 回归 | 先定位根因，再允许修复 | `investigation_report.md/json` |
| `browse` | 浏览器观察 | UI Story 规划前 | 采集页面证据，不改代码 | 借用 `browser_qa` 产物，report-only |
| `plan_design_review` | 设计规划审查 | 高风险 UI Story | 形成 route score、设计约束和 `DESIGN.md` | `design_review_report.md`、`design_scorecard.json`、`DESIGN.md` |
| `design_consultation` | 设计咨询 | UI Story build 前 | 给出视觉方向、模块结构、preview | `design_consultation_report.md`、`DESIGN.md`、`design_preview.html` |
| `setup_browser_cookies` | 会话准备 | 认证态 UI 验证前 | 导入 cookie / storage state | `cookie_import_plan.md`、`storage_state.json` |
| `workspace_prep` | 工作区准备 | 正式 build 前 | 检查前置门槛、切分支、准备工作树 | branch、workspace state |
| `backend_dev` | 后端开发 | subtasks 中有 backend | 修改 API / service / runtime 代码 | 代码变更 |
| `frontend_dev` | 前端开发 | subtasks 中有 frontend | 修改页面、组件、交互 | 代码变更 |
| `database_dev` | 数据库开发 | subtasks 中有 database | 修改 schema / SQL / storage | 代码变更 |
| `devops_dev` | DevOps 开发 | subtasks 中有 devops | 修改 CI / infra / env 相关 | 代码变更 |
| `sync_merge` | 归并同步 | builder 结束后 | 汇总并行开发结果进入统一验证链 | dev result 聚合 |
| `code_style_reviewer` | 风格预审 | build 后第一道门 | 检查 UTF-8、tab、trailing space、行长 | `code_style_review_report.md` |
| `tester` | 测试执行 | style review 后 | 跑 install / lint / typecheck / test + Story 专项验证 | `test_report.md` |
| `browser_qa` | 浏览器 QA | UI / browser 场景 | 真实页面抓取、截图、控制台、健康分 | `browser_qa_report.md`、`session.json` |
| `runtime_qa` | 运行时 QA | 非 UI Story | 跑 runtime/gate check，验证数据和运行时产物 | `runtime_qa_report.md`、`runtime_qa_commands.log` |
| `qa_design_review` | 设计感知 QA | UI Story 浏览器 QA 后 | 把 DESIGN.md、截图和 route score 结合做设计验收 | `qa_design_review_report.md`、`before_after_report.md` |
| `fixer` | 自动修复 | 任意验证失败后 | 根据 issue source 回到对应节点前修复 | `fix_report.md` |
| `security_scanner` | 安全扫描 | QA 后、review 前 | 扫敏感字符串和配置风险 | security scan 结果 |
| `reviewer` | 工程审查 | 安全后 | 以生产风险为中心做 review，不只是样式检查 | `review_report.md`、`risk_register.json` |
| `code_acceptance` | 代码验收 | review 后 | 检查文件可读性、JSON、卫生规范 | `code_acceptance_report.md` |
| `acceptance_gate` | 最终验收门 | code acceptance 后 | 一条条核对 acceptance criteria + scope drift | `acceptance_report.md` |
| `doc_writer` | Story 文档收口 | acceptance 通过后 | 生成交付报告、结果报告、完成标准 | `story_delivery_report.md`、`story_result_report.md` |
| `ship` | 发版就绪 | Sprint closeout | 汇总 release scope、验证状态、变更信息 | `ship_readiness_report.md`、`release_package.json` |
| `document_release` | 文档发布同步 | ship 后 | 检查 release-facing docs 漂移并补 sync note | `document_release_report.md`、`doc_sync_plan.json` |
| `retro` | 回顾复盘 | document release 后 | 形成 retro、趋势、下一步动作 | `retro_report.md`、`retro_snapshot.json` |

## 7. 这些 Agent 如何分组理解

如果用“一个完整研发流程”来理解，这 29 个节点可以拆成 6 组。

### 7.1 规划组

- `office_hours`
- `requirement_analysis`
- `plan_ceo_review`
- `architecture_review`
- `investigate`

职责：

- 把“想做什么”变成“可以执行什么”
- 把模糊问题收敛成 Story contract
- 把 bugfix 先变成根因调查，而不是直接乱修

### 7.2 UI 观察与设计组

- `setup_browser_cookies`
- `browse`
- `plan_design_review`
- `design_consultation`
- `qa_design_review`

职责：

- 让 UI Story 有“真实页面证据”
- 让设计要求变成 `DESIGN.md`
- 让设计验收进入正式交付链，而不是靠主观感觉

### 7.3 构建组

- `workspace_prep`
- `backend_dev`
- `frontend_dev`
- `database_dev`
- `devops_dev`
- `sync_merge`
- `fixer`

职责：

- 准备分支和工作区
- 按 subtask 类型路由到不同 builder
- 合并结果
- 出问题时自动回修

### 7.4 验证组

- `code_style_reviewer`
- `tester`
- `browser_qa`
- `runtime_qa`
- `security_scanner`

职责：

- 在 review 之前，先把明显的 style / test / browser / runtime 问题挡住

### 7.5 审查与验收组

- `reviewer`
- `code_acceptance`
- `acceptance_gate`

职责：

- `reviewer` 看生产风险与架构/流程问题
- `code_acceptance` 看文件卫生与落地质量
- `acceptance_gate` 看 story contract 是否真正被满足

### 7.6 交付收口组

- `doc_writer`
- `ship`
- `document_release`
- `retro`

职责：

- Story 结束时沉淀交付材料
- Sprint 结束时沉淀发版材料和复盘材料

## 8. Skill Mode 是怎么工作的

Skill mode 是操作入口，不是底层节点本身。

当前已经落地的主要 mode：

| mode | 从哪开始 | 到哪停止 | 用途 |
| :--- | :--- | :--- | :--- |
| `office-hours` | `office_hours` | `office_hours` | 需求 framing |
| `plan-ceo-review` | `plan_ceo_review` | `plan_ceo_review` | 产品级重构需求 |
| `plan-eng-review` | `requirement_analysis` | `architecture_review` | 工程规划，不进 build |
| `investigate` | `investigate` | `investigate` | 根因分析 |
| `browse` | `browse` | `browse` | 浏览器观察，report-only |
| `plan-design-review` | `plan_design_review` | `plan_design_review` | UI 设计规划 |
| `design-consultation` | `design_consultation` | `design_consultation` | 生成设计合同 |
| `review` | `reviewer` | `reviewer` | 单独 review |
| `qa` | `tester` | `browser_qa` | 测试 + QA + 允许 fixer |
| `qa-only` | `tester` | `browser_qa` | 只做 QA 报告，不修 |
| `qa-design-review` | `browser_qa` | `qa_design_review` | 设计感知 QA |
| `design-review` | `browser_qa` | `qa_design_review` | 后置设计审查 |
| `setup-browser-cookies` | `setup_browser_cookies` | `setup_browser_cookies` | 导入认证态会话 |
| `ship` | `ship` | `ship` | 出发版包 |
| `document-release` | `document_release` | `document_release` | 文档同步 |
| `retro` | `retro` | `retro` | Sprint 回顾 |

### 8.1 为什么 mode 很重要

因为 mode 决定：

- 入口节点
- 停止节点
- 是否 report-only
- 是否允许 fixer
- 默认 browser QA mode

也就是说，同一个底层工作流，可以被切成很多“实用入口”。

## 9. 一个普通 Story 是怎么跑完的

这是最核心的问题。

下面用“普通非 UI Story”举例。

### 第 1 步：准备 Story task card

Story yaml 至少要包含：

- `goal`
- `acceptance_criteria`
- `related_files`
- 最好有：
  - `primary_files`
  - `constraints`
  - `story_inputs`
  - `story_process`
  - `story_outputs`
  - `verification_basis`

### 第 2 步：TaskCard 规范化

系统先用 `TaskCard` 校验 Story。

如果有缺失，会自动补默认值，例如：

- 默认 input/process/output
- 默认 verification basis
- 默认 `agent_policy=auto`

### 第 3 步：Story admission

系统会先判断这张 Story 卡能不能正式进流程。

会检查：

- 文件范围是不是为空
- acceptance criteria 是不是为空
- required modes 能不能推导出来
- 如果是 UI Story，有没有浏览器入口
- 如果是 Sprint 自动执行，有没有拿到 pre-hook 产物

这一步会落：

- `tasks/runtime/story_admissions/<story_id>.json`

### 第 4 步：自动激活 agent 链

系统根据：

- file scope
- story kind
- bug scope
- risk
- requires_auth
- workflow_enforcement_policy

自动算出：

- `required_modes`
- `advisory_modes`
- `qa_strategy`
- `effective_qa_mode`

例如普通 Story 一般会要求：

- `plan-eng-review`
- `review`
- `qa`

如果是 UI Story，还会自动追加：

- `browse`
- `plan-design-review`
- `design-consultation`
- `design-review`

### 第 5 步：Requirement Analysis

`requirement_analysis` 会把 Story 真正拆成 subtasks。

它会根据文件路径推断是：

- frontend
- backend
- database
- devops

同时写出：

- acceptance checklist
- story contract
- 共享黑板 `shared_blackboard`

产物：

- `.meta/<repo>/requirement/parsed_requirement.json`
- `.meta/<repo>/requirement/intent_confirmation.md`

### 第 6 步：Architecture Review

这是 Story 真正进入 build 之前最关键的一步。

它会输出：

- execution shape
- data flow
- architecture diagram
- boundaries
- edge cases
- failure modes
- QA handoff
- test plan

如果信息还不够，它甚至会暂停流程，要求补规划问题。

产物：

- `.meta/<repo>/architecture_review/architecture_review_report.md`
- `.meta/<repo>/architecture_review/test_plan.json`
- `.meta/<repo>/architecture_review/failure_modes.json`
- `.meta/<repo>/architecture_review/qa_test_plan.md`

### 第 7 步：Workspace Prep

在真正 build 前，会先检查：

- `plan-eng-review` 是否完成
- bugfix 是否先 investigate
- 当前是不是默认分支

如果在默认分支，会自动切到工作分支。

### 第 8 步：Builder 分流

`task_router` 根据 subtasks 决定接下来执行：

- `backend_dev`
- `frontend_dev`
- `database_dev`
- `devops_dev`

这些 builder 是可以并行概念化的，最后统一汇总到 `sync_merge`。

### 第 9 步：Code Style Review

build 之后，先不过 test，而是先过一层风格/卫生门：

- UTF-8 可读性
- tab
- trailing spaces
- line length

这一步的意义是：

- 把低成本、确定性的脏问题先挡住
- 避免 test/review 被样式噪音污染

### 第 10 步：Tester

`tester` 会跑：

- install
- lint
- typecheck
- test
- Story-specific validation

Story-specific validation 是这个系统很实用的一层。

比如某些 Story 不是简单“pytest 过了就行”，而是要验证：

- schema 文件是否齐全
- contract example 是否有效
- SQL 是否包含关键表
- statement upload API 的 token 是否齐全

也就是说，系统已经内建了“按 Story ID 定制验收逻辑”的能力。

### 第 11 步：QA

普通 Story 根据 `qa_strategy` 二选一：

- 有浏览器表面：
  - 走 `browser_qa`
- 没有浏览器表面：
  - 走 `runtime_qa`

`browser_qa` 会做：

- 浏览器 session
- 页面 observation
- screenshot
- console log
- health score
- ship readiness

`runtime_qa` 会做：

- runtime command 执行
- gate check
- structured findings
- health score

### 第 12 步：Fixer 回路

只要下面任何一步产生 blocking issue：

- code_style_review
- test
- browser_qa
- runtime_qa
- review
- code_acceptance
- acceptance_gate

都可以把 issue 派给 `fixer`。

`fixer` 会：

- 识别 issue 来源
- 找目标文件
- 修复
- 决定返回哪个节点

返回目标可能是：

- `code_style_reviewer`
- `tester`
- `browser_qa`
- `runtime_qa`
- `reviewer`
- `code_acceptance`
- `acceptance_gate`

所以 `fixer` 不是固定回到 test，而是“回到出问题的那个门之前”。

### 第 13 步：Reviewer

`reviewer` 不是 style checker，也不是 acceptance gate。

它关注的是：

- 生产风险
- scope drift
- protected path
- validation 是否足够
- 文档是否陈旧
- runtime / contract / infra 变更是否风险偏高

输出分级：

- blocking
- important
- nice_to_have

### 第 14 步：Code Acceptance

这一层更偏“落地质量验收”：

- 文件是不是 UTF-8
- 行有没有 tab / trailing space
- JSON 能不能 parse
- 改动文件是否能读

### 第 15 步：Acceptance Gate

这是 Story 的最终硬门。

它会：

1. 一条条跑 acceptance criteria
2. 检查 scope drift
3. 检查：
   - review 是否通过
   - code style review 是否通过
   - code acceptance 是否通过

只有它通过，Story 才算正式 accepted。

### 第 16 步：Doc Writer

最后不是直接结束，而是必须落文档：

- `story_completion_standard.md`
- `story_delivery_report.md`
- `story_result_report.md`

这一步非常关键，因为它把：

- 计划中的 story contract
- 实际输入
- 实际过程证据
- 实际输出
- 验证结果

统一沉淀成可交接材料。

## 10. 一个 UI Story 会多走哪些 Agent

UI Story 比普通 Story 多一整条 UI / Design 证据链。

完整链条大致是：

1. `requirement_analysis`
2. `architecture_review`
3. 如果要认证态：
   - `setup_browser_cookies`
4. `browse`
5. `plan_design_review`
6. `design_consultation`
7. `workspace_prep`
8. `frontend_dev` / 相关 builder
9. `code_style_review`
10. `tester`
11. `browser_qa`
12. `qa_design_review`
13. `security_scanner`
14. `reviewer`
15. `code_acceptance`
16. `acceptance_gate`
17. `doc_writer`

### UI Story 为什么要这么长

因为系统的设计原则是：

- 不能只凭代码 diff 说 UI 做完了
- 不能只凭 screenshot 说 UI 合格了
- UI 要有：
  - 真实页面证据
  - 设计规划证据
  - 设计合同
  - 设计验收证据

## 11. 一个 bugfix Story 会多走哪些 Agent

bugfix 最大的区别是：不能直接修。

完整思路：

1. `investigate`
2. `workspace_prep`
3. build / fix
4. `tester`
5. `browser_qa` 或 `runtime_qa`
6. `reviewer`
7. `code_acceptance`
8. `acceptance_gate`
9. `doc_writer`

### investigate 在 bugfix 中的作用

它会先写：

- evidence
- reproduction checklist
- instrumentation plan
- hypotheses
- root cause
- fix recommendation
- verification plan

也就是说，这个系统强制把“修 bug”改成：

- 先调查
- 再修
- 再证明回归关闭

## 12. 一个 Sprint 是怎么做的

Sprint 不是“把多个 Story 顺序跑完”这么简单。

在这个系统里，一个 Sprint 有正式前置、正式执行、正式收口。

### 12.1 Sprint 准备

Sprint 一般先来自 requirement split：

- `analyze`
- `split_requirement`
- 或 `auto-deliver`

产物目录长这样：

```text
tasks/backlog_v1/
  sprint_overview.md
  sprint_xxx/
    sprint_plan.md
    execution_order.txt
    epic_x_x_xxx.md
    epic_x_x_xxx/
      Sx-001_xxx.yaml
      Sx-002_xxx.yaml
```

### 12.2 Sprint pre-hooks

运行 `run-sprint` 时，先跑 pre-hooks。

pre-hooks 会生成：

- `sprint_agent_advice.json`
- `sprint_framing_artifact.json`
- `office_hours_path`
- `plan_ceo_review_path`
- `parity_manifest_path`
- `acceptance_checklist_path`

换句话说，一个 Sprint 在正式跑 Story 之前，会先有：

- Sprint 级 framing
- Sprint 级产品 review
- Sprint 级建议 agent 链
- parity audit

### 12.3 Sprint 内部 Story 执行

然后系统会按 `execution_order.txt` 的顺序执行 Story。

每个 Story 都会：

1. 读取 yaml
2. 规范化 task card
3. 定位 backlog / sprint / story context
4. 做 admission
5. 进入 DevWorkflow
6. 产出 audit 和 artifacts
7. 更新 status / acceptance / coverage / handoff

### 12.4 Story 执行后的正式落账

每个 Story 执行完，不只是一个 `success=true` 就结束，还会更新：

- `tasks/story_status_registry.json`
- `tasks/story_acceptance_reviews.json`
- `tasks/runtime/agent_coverage_report.json`
- `tasks/runtime/story_handoffs/<story_id>.md`
- 如果失败：
  - `tasks/runtime/story_failures/<story_id>.json`

### 12.5 Sprint post-hooks

当 Sprint 里的 Story 跑完后，post-hooks 会继续收口：

- `ship`
- `document_release`
- `retro`

并生成：

- `ship_advice.json`
- `document_release_report.md`
- `retro_report.md`
- `sprint_close_bundle.json`

如果是特定 Sprint，还会加运行时专项验证。

### 12.6 Sprint special acceptance

系统还支持把某个 Sprint 做成“正式流程完整度审计”。

会检查：

- status 是否落账
- acceptance review 是否落账
- handoff 是否存在
- failure / evidence 是否完整
- sprint level artifacts 是否齐

这一步输出的是“这个 Sprint 是否真的按标准流程跑过”，不是“看起来差不多完成了”。

## 13. Story / Sprint 完成，哪些文件是最重要的

### 13.1 Story 级

优先看：

- `runs/prod_audit_<task-id>.json`
- `.meta/<repo>/delivery/story_delivery_report.md`
- `.meta/<repo>/delivery/story_result_report.md`
- `tasks/story_status_registry.json`
- `tasks/story_acceptance_reviews.json`
- `tasks/runtime/story_handoffs/<story_id>.md`

### 13.2 Sprint 级

优先看：

- `runs/sprints/<project>/<sprint>/sprint_agent_advice.json`
- `runs/sprints/<project>/<sprint>/sprint_framing_artifact.json`
- `runs/sprints/<project>/<sprint>/ship_advice.json`
- `runs/sprints/<project>/<sprint>/document_release_report.md`
- `runs/sprints/<project>/<sprint>/retro_report.md`
- `runs/sprints/<project>/<sprint>/sprint_close_bundle.json`

## 14. Dashboard 现在能看什么

当前 dashboard 已完成的能力，按使用视角可以分成 5 类。

### 14.1 任务视角

- `/api/tasks`
- `/api/tasks/{task_id}`
- `/api/tasks/{task_id}/collaboration`

可以看到：

- audit log
- artifacts
- events
- collaboration trace
- workflow metadata

### 14.2 backlog / sprint / story 视角

- `/api/backlogs`
- `/api/backlogs/{backlog_id}`
- `/api/backlogs/{backlog_id}/sprints/{sprint_id}`
- `/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}`

可以看到：

- backlog 层级
- sprint plan
- epic 下的 story
- execution order
- story latest task
- workflow coverage

### 14.3 acceptance review 视角

- Story 支持人工 acceptance review 的读取和写入。

接口：

- `GET /api/backlogs/{...}/acceptance-review`
- `POST /api/backlogs/{...}/acceptance-review`

### 14.4 runtime showcase 视角

多项目 runtime 页面：

- `/projects/versefina/runtime`
- `/projects/finahunt/runtime`

支持把产品 repo 的运行时证据映射成 story 视角卡片。

### 14.5 实时执行视角

- `/ws/{task_id}`

通过 websocket 看：

- node_start
- node_end
- log
- workflow_state

## 15. 一个“完整开发流程”在这个系统里到底经过哪几个 Agent

如果你问的是“标准软件交付闭环”的最完整版，那么按照当前系统标准，答案是：

### 15.1 新需求 / 新 Sprint 级

1. `office_hours`
2. `plan_ceo_review`
3. `plan_eng_review`

这里的目标不是改代码，而是把需求框准。

### 15.2 单个普通 Story 级

1. `requirement_analysis`
2. `architecture_review`
3. `workspace_prep`
4. `builder`
5. `sync_merge`
6. `code_style_reviewer`
7. `tester`
8. `runtime_qa` 或 `browser_qa`
9. `security_scanner`
10. `reviewer`
11. `code_acceptance`
12. `acceptance_gate`
13. `doc_writer`

### 15.3 UI Story 级

1. `requirement_analysis`
2. `architecture_review`
3. `setup_browser_cookies`（如果需要认证）
4. `browse`
5. `plan_design_review`
6. `design_consultation`
7. `workspace_prep`
8. `frontend_dev` / 其他 builder
9. `code_style_reviewer`
10. `tester`
11. `browser_qa`
12. `qa_design_review`
13. `security_scanner`
14. `reviewer`
15. `code_acceptance`
16. `acceptance_gate`
17. `doc_writer`

### 15.4 Bugfix Story 级

1. `investigate`
2. `workspace_prep`
3. `builder` / `fixer`
4. `tester`
5. `runtime_qa` / `browser_qa`
6. `reviewer`
7. `code_acceptance`
8. `acceptance_gate`
9. `doc_writer`

### 15.5 Sprint 收口级

1. `ship`
2. `document_release`
3. `retro`

## 16. 这套流程为什么能“实现功能”，而不是只生成报告

这是个很关键的问题。

因为这套系统不是纯 planning 工具，它真正把“实现功能”拆成了 4 个闭环：

### 16.1 规划闭环

需求先被变成：

- goal
- file scope
- acceptance
- input/process/output
- verification basis

所以 builder 不是盲改。

### 16.2 实现闭环

builder 不是全局乱写，而是：

- 先路由到 backend/frontend/database/devops
- 再回 sync_merge

所以改动边界是可控的。

### 16.3 质量闭环

不是写完就完，而是必须过：

- code style
- test
- QA
- review
- code acceptance
- acceptance gate

而且任何一步失败都能被 fixer 拉回去。

### 16.4 记忆闭环

不是运行结束就丢失，而是每一步都在沉淀：

- checkpoint
- audit
- handoff
- delivery report
- status registry

所以系统可以持续接力。

## 17. 你如果现在要用这套系统做一个新功能，推荐怎么走

### 17.1 如果是“大需求”

推荐流程：

1. 写 requirement 文本或 markdown
2. 跑 `analyze` 或 `split_requirement`
3. 检查 `tasks/backlog_v1`
4. 跑 `run-sprint` 或 `auto-deliver`
5. 用 dashboard 看 Story 执行和收口状态

### 17.2 如果是“单个 Story”

推荐流程：

1. 写一个 task yaml
2. 明确：
   - goal
   - acceptance criteria
   - related_files
   - primary_files
   - verification_basis
3. 如果是特殊入口，指定 `skill_mode`
4. 跑 `run-task`
5. 看 `.meta/<repo>/...` 和 dashboard

### 17.3 如果是“UI Story”

额外要准备：

- `browser_urls` 或 `preview_base_url`
- 如果要登录态：
  - `requires_auth: true`
  - `cookie_source`
  - `auth_expectations`

### 17.4 如果是“bugfix”

额外要准备：

- `bug_scope`
- `investigation_context`
- 可复现证据

## 18. 常用命令清单

```powershell
cd D:\lyh\agent\agent-frame\agentsystem

# 1. 需求拆解为 backlog
python cli.py analyze -r "你的需求" --project versefina --prefix backlog_v1

# 2. 从 requirement 文件拆解 backlog
python cli.py split_requirement --requirement-file D:\path\to\requirement.md --project finahunt --prefix backlog_v1

# 3. 跑单个 Story
python cli.py run-task --task-file D:\path\to\story.yaml --env test --project versefina

# 4. 跑整个 Sprint
python cli.py run-sprint --sprint-dir D:\path\to\sprint_dir --env test --project versefina

# 5. backlog 生成后自动执行
python cli.py auto-deliver --requirement-file D:\path\to\requirement.md --env test --project finahunt --prefix backlog_v1 --auto-run

# 6. 渲染 skill mode 包
python cli.py render-agent-skills

# 7. 启动 dashboard
python cli.py dashboard --host 127.0.0.1 --port 8010
```

## 19. 当前这套系统最值得记住的 10 个事实

1. `agentsystem` 已经实现的是“控制面 + 编排层 + 审计层 + dashboard”，不是单纯 demo。
2. 真正的流程真相来源是 manifest，不是 prompt 文本。
3. Story 不是改完代码就算完成，而是必须 `implemented + verified + agentized + accepted`。
4. UI Story 在这里是重流程对象，不能跳过 browse / design / QA 链。
5. bugfix 不能跳过 investigate。
6. Sprint 关闭不能跳过 ship / document-release / retro。
7. mode 是入口，不是底层节点本体。
8. `.meta/<repo>/...` 是 fresh session 延续能力的核心。
9. dashboard 读取的是运行证据，不是凭记忆拼装的状态。
10. 这套系统已经能把 Story 和 Sprint 的“过程完整性”本身当成一个被验证对象。

## 20. 最后一句话总结

`agentsystem` 现在已经完成的，不只是“让多个 agent 参与开发”，而是把软件交付过程正式拆成了：

- 需求框定
- Story 契约化
- agent 自动激活
- 工作流编排
- 构建与修复
- 多层验证
- 最终验收
- 文档沉淀
- Sprint 收口
- dashboard 可追踪

所以你可以把它理解成：

一个已经具备正式 Story / Sprint 执行语义的软件工厂控制台，而不是一个临时性的 Agent 调度脚本集合。
