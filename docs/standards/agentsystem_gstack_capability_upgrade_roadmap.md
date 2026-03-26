# agentsystem gstack Capability Upgrade Roadmap

最后更新：2026-03-25

## 1. 目标定义

这份文档定义的是：

`agentsystem` 如何先让关键 Agent 能力至少达到 `gstack` 当前公开水平，然后再逐步做成自己的系统优势。

这里的“超过 gstack”不是指：

- 命令更多
- 文档更长
- 说法更激进

而是指：

1. 关键 Agent 能力先达到 `gstack` 的当前公开水平。
2. 在 parity 达成后，把 `agentsystem` 已有的 Story/Sprint/acceptance/control-plane 优势做成上游没有的系统壁垒。

### 1.1 两个必须区分的基线

#### 基线 A：formal parity 基线

本地 migration / audit 当前绑定的 upstream pin：

- `8ddfab233d3999edb172bed54aaf06fc5ff92646`

这个基线用于：

- parity manifest
- formal audit
- dogfood truth

#### 基线 B：市场对标基线

本路线图对标的是 `gstack main` 在 `2026-03-25` 的公开仓库状态。

扫描时的公开事实：

- upstream latest commit：`9870a4ec49078ad3fc150c3d93605401a747af6d`
- upstream pushed at：`2026-03-25T04:01:22Z`
- upstream 当前公开 skill 目录：27 个

这个基线用于回答：

- “今天的 gstack 已经做到哪里了？”
- “我们现在还差什么？”
- “什么叫至少达到它的水平？”

### 1.2 本路线图的非目标

第一阶段不把下面这些当作阻塞项：

- 遥测社区增长
- 市场传播文案
- “看起来像 gstack” 的包装一致性

第一阶段只盯住：

- Agent 能力
- host/runtime 习惯
- workflow reachability
- artifact / test / dogfood 证据

## 2. 当前差距总表

当前能力矩阵用四档来标：

- `已领先`
- `已接近`
- `明显落后`
- `尚未接入`

| 能力维度 | 当前本地状态 | 对比 gstack main（2026-03-25） | 判断 |
| :--- | :--- | :--- | :--- |
| Story / Sprint / Roadmap 语义 | 已有正式 backlog、Sprint、Roadmap、closeout、invalid batch 吊销 | `gstack` 更偏 skill / host workflow | 已领先 |
| Acceptance / Coverage / Registry | 已有 status、acceptance review、coverage、authoritative vs evidence-only | 上游更偏 skill 习惯和 PR/workflow | 已领先 |
| Dashboard / Control Plane | 已有多项目 runtime showcase 与 execution timeline | 上游不以控制台为主 | 已领先 |
| Continuity / Handoff | 已有 `NOW.md` / `STATE.md` / `DECISIONS.md` / resume guard | 上游更强在 host habit，但系统化 continuity 文档没有本地这么重 | 已领先 |
| Browse runtime | 已有 Playwright 适配、storage state、browser QA | 上游有 persistent daemon、`.gstack/browse.json`、50+ commands、handoff / resume | 明显落后 |
| Office-hours / CEO / Design 互动节奏 | 已有 workflow 节点和 artifact | 上游是 AskUserQuestion 驱动、单问题决策节奏、repo mode / host preamble 更强 | 明显落后 |
| Review / QA / Ship 深度 | 已有正式 workflow、security、acceptance、fixer | 上游在 checklist 深度、回归测试生成、ship-to-PR 自动化上更成熟 | 已接近 |
| Specialist Agents | 缺少 `cso`、`benchmark`、`land-and-deploy`、`canary`、`setup-deploy`、`codex`、`autoplan`、`careful`、`unfreeze` | 上游当前 main 已公开这些 skill | 尚未接入 |
| Safety hooks / repo host habit | 本地有部分 policy 和 parity guard | 上游 `freeze` / `guard` / `gstack-upgrade` / repo mode 形成更完整 host habit | 明显落后 |

### 2.1 当前已领先项

`agentsystem` 现在真正已经比 `gstack` 更强的，是系统层能力：

- Story/Sprint/Roadmap 原生语义
- acceptance registry
- agent coverage registry
- multi-repo dashboard
- continuity 文档链
- invalid batch 吊销与重跑

### 2.2 当前已接近项

这些项不是没有，而是深度和使用习惯还没有完全追平：

- `review`
- `qa`
- `qa-only`
- `ship`
- `document-release`
- `retro`

### 2.3 当前明显落后项

当前真正的硬差距主要是：

- persistent browse host
- interactive planning rhythm
- ship-to-PR automation
- safety hook / repo mode / upgrade habit

### 2.4 当前尚未接入项

对比 `gstack main` 当前公开 skill 目录，本地还缺少或未正式接入：

- `cso`
- `benchmark`
- `land-and-deploy`
- `canary`
- `setup-deploy`
- `codex`
- `autoplan`
- `careful`
- `unfreeze`

此外，虽然本地已 vendored：

- `freeze`
- `guard`
- `gstack-upgrade`

但还没有全部变成本地正式 runtime mode。

## 3. Phase 1：达到 gstack 水平

这一阶段的目标非常直接：

不要先追求“超越”，先让关键 Agent 能力至少达到 `gstack main` 的当前公开水平。

## 3.1 P0 浏览器能力补齐

这是第一优先级，不能后置。

### 目标

把本地浏览器能力从“可用的 Playwright 适配”升级成“接近 gstack browse host 的正式平台能力”。

### 必做项

- 实现持久化 browse host，而不是每次临时跑一段适配逻辑。
- 正式维护 `.gstack/browse.json` 兼容状态：
  - `pid`
  - `port`
  - `token`
  - `startedAt`
  - `binaryVersion`
  - `workspaceRoot`
- 支持共享 session / storage state / tabs 复用。
- 支持 `browse -> qa -> design-review -> setup-browser-cookies` 复用同一 browser service contract。
- 扩大命令面，至少补齐上游公开关键能力：
  - navigation
  - read
  - snapshot refs
  - interact
  - inspect
  - screenshot/pdf
  - tab management
  - `chain`
  - `handoff`
  - `resume`

### 退出条件

- `.gstack/browse.json` 成为浏览器 host 真相源，而不是文档中的兼容口号。
- 同一 Story 中多次浏览器调用可稳定复用同一 session。
- `qa`、`design-review`、`setup-browser-cookies` 默认复用同一 browse host。
- 至少有一组测试和一组 dogfood 证明该 host 可长期运行与恢复。

## 3.2 P0 互动式规划补齐

### 目标

把 `office-hours`、`plan-ceo-review`、`plan-design-review` 从“会产报告”提升到“保留上游节奏的互动式 Agent”。

### 必做项

- 让 planning mode 正式支持：
  - `awaiting_user_input`
  - `dialogue_state`
  - `next_question`
  - `approval_required`
- `office-hours` 改成 one-question-at-a-time 节奏，不再一次性沉淀完整报告再补问。
- `plan-ceo-review` 支持明确的决策暂停，而不是默认 workflow artifact 一次性落地。
- `plan-design-review` 保留 route-level 决策与设计选择暂停。
- 所有互动暂停都必须可 resume，不允许因为中断而重新生成整份 package。

### 退出条件

- 至少一个 office-hours 场景必须经历真实暂停与恢复。
- 至少一个 CEO review 场景必须把“用户确认的决策”写入 state，而不是只写最终报告。
- planning mode 的 pause/resume 被 workflow admission 和 dashboard 正确认知。

## 3.3 P0 review / qa / ship 深度补齐

### `review`

- 接入更接近上游的 checklist 深度。
- 引入 adversarial / second-opinion review 机制，避免单 reviewer 风格锁定。
- 让 review 更明确地区分：
  - correctness
  - production risk
  - UX / scope drift
  - release risk

### `qa`

- 强化回归测试建议或生成能力。
- 让 QA 报告包含更可执行的 rerun plan，不只是 findings 列表。
- 在 fixer 回路里引入更强的“验证后再放行”策略。

### `ship`

- 从 readiness artifact 升级到正式 landing choreography：
  - base branch diff discipline
  - 必要测试
  - VERSION / CHANGELOG 规范
  - PR draft 产物
  - branch / push / create PR 的可选自动化

### 退出条件

- `review`、`qa`、`ship` 各自至少有一条 dogfood 证据，证明它们不是“写报告版适配”。
- `ship` 至少能稳定产出 PR-ready package，而不仅是 readiness report。

## 3.4 P1 专项 Agent 补齐

### 目标

把当前缺失的上游公开 skill 补齐为本地正式 runtime mode，或明确写进“暂不接入”清单。

### 优先补齐顺序

1. `codex`
2. `autoplan`
3. `cso`
4. `benchmark`
5. `land-and-deploy`
6. `canary`
7. `setup-deploy`
8. `careful`
9. `unfreeze`

并对以下 vendored skill 做明确决策：

- `freeze`
- `guard`
- `gstack-upgrade`

### 原则

- 不允许目录 vendored 了，就算“能力已接入”。
- 必须具备：
  - local adapter
  - workflow reachability
  - artifact contract
  - tests
  - dogfood

### 退出条件

- 每个模式都有 parity status 和测试，不再停留在模板层。
- parity manifest 里每个模式的状态都可追溯。

## 3.5 P1 Host 行为补齐

### 目标

把上游 skill 依赖的 host habit 补齐到不再“静默丢失”。

### 必做项

- repo ownership / repo mode 语义
- upgrade/check lifecycle
- freeze / guard enforcement
- field-report 级别的 host interaction affordance
- session-level behavior consistency

### 非阻塞项

遥测可以存在，但不是 Phase 1 parity 的阻塞项；除非某个上游能力明确依赖 telemetry 行为。

### 退出条件

- 任何依赖 host habit 的上游 skill，在本地都不再是“prompt 里提到，但系统没实现”。

## 4. Phase 2：超过 gstack

只有在 Phase 1 达标后，才进入这阶段。

这里的“超过”不是更多 slash command，而是把 `agentsystem` 已经具备的系统能力做成正式平台优势。

## 4.1 Story / Sprint 原生 autoplan

目标：

把 `office-hours -> CEO -> design -> eng review` 从分散 skill 串联，升级成 Story/Sprint 级自动前置链。

要点：

- 支持 demand-to-backlog 自动规划
- 支持 sprint framing 自动注入
- 支持规划链的状态机与验收闭环

为什么这会超过 gstack：

- `gstack` 强在 skill 与个人 host 习惯
- `agentsystem` 可以把规划链升格成 backlog / sprint 级系统语义

## 4.2 Contract-aware self-healing

目标：

让 fixer / qa / review 不只是“失败后回跳”，而是根据 implementation contract 与 artifact inventory 自适应修复。

要点：

- 结合 `story_contracts.py`
- 结合 `quality_sentry.py`
- 让系统理解“缺哪类 artifact、缺哪类 integration、哪个 contract 没满足”

为什么这会超过 gstack：

- 这会把“修 bug”从节点回路升级成契约驱动的恢复系统

## 4.3 Multi-repo release control plane

目标：

让 `agentsystem`、`versefina`、`finahunt` 的运行证据、交付状态、retro、release readiness 在一个控制面统一治理。

要点：

- project registry 做成正式发布控制台
- 统一 acceptance / ship / retro 视图
- 统一 dogfood 与 parity 视图

为什么这会超过 gstack：

- `gstack` 不是以多 repo 控制台为主
- 这是 `agentsystem` 天然更适合做的平台能力

## 4.4 Product-native specialist agents

目标：

把金融世界、runtime validation、artifact warehouse、数据审计等 repo 专有能力抽成平台级 specialist。

要点：

- specialist 不是通用 prompt，而是带产品域验证器的 mode
- specialist 必须进入 Story/Sprint workflow，而不是孤立脚本

为什么这会超过 gstack：

- 这会把“通用工程 Agent”提升成“平台 + 领域 specialist”

## 4.5 Authoritative acceptance

目标：

把 `implemented / verified / agentized / accepted` 做成强于上游的完成定义和仪表盘。

要点：

- authoritative vs evidence-only 尝试清晰可见
- acceptance follow-up 和 parity follow-up 可见
- dashboard 可直接展示真实完成状态

为什么这会超过 gstack：

- 这是系统级交付真相，不是单 skill 的好坏

## 5. 分期落地顺序

建议顺序必须固定，不能随意跳：

1. 浏览器能力补齐
2. 互动式规划补齐
3. review / qa / ship 深度补齐
4. 专项 Agent 补齐
5. host 行为补齐
6. 超越层优化

### 5.1 为什么先补 browse

因为 browse 是上游一大核心平台能力，也是 `qa`、`design-review`、`setup-browser-cookies` 的基础设施。

### 5.2 为什么再补互动式规划

因为 planning rhythm 是 `office-hours` / `CEO review` 的能力核心；不补这个，planning 只能算“生成报告”。

### 5.3 为什么 ship 在第三层

因为 ship 自动化很重要，但它建立在 review / qa / host habit 已经成熟的前提上。

### 5.4 为什么超越层最后做

因为如果 parity 还没到位，就直接讲“超越”，最后通常会变成：

- 命名上很强
- 实际上两头不到岸

## 6. Definition Of Done

以后只要文档里要把某个能力写成“达到 gstack 水平”或“已超过 gstack”，必须同时满足下面 6 条。

## 6.1 Reachable

- mode 可直达
- CLI 可调用
- workflow 可强制

## 6.2 Behavioral

- 角色相同
- 节奏相同
- hard stop 条件相同
- 必要输入相同

## 6.3 Artifacted

- artifact family 完整
- 产物足够让 fresh session 和 reviewer 接手

## 6.4 Tested

- registry test
- route test
- artifact test
- scenario test

## 6.5 Dogfooded

- 至少有一条真实 dogfood 证据
- 不只是 synthetic test

## 6.6 Truthfully Labeled

- 达不到就继续标：
  - `template_only`
  - `partial_runtime`
  - `workflow_wired`
- 只有真正完成，才允许标：
  - `达到 gstack 水平`
  - 或 `超过 gstack`

最后一句话：

`agentsystem` 的下一阶段不是“发明更多 Agent 名字”，而是先把核心 Agent 能力追平 `gstack main`，再利用自己已经更强的 Story/Sprint/acceptance/control-plane 体系，把这些能力做成更硬的平台优势。
