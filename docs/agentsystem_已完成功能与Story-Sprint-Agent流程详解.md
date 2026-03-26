# agentsystem 已完成功能与 Story / Sprint / Agent 流程详解

最后更新：2026-03-25

## 1. 这份文档是干什么的

这份文档只回答一个问题：

`D:\lyh\agent\agent-frame\agentsystem` 现在按代码真相，已经真正做成了什么？

它不是愿景稿，也不是抽象框架稿，而是当前可执行能力说明书。这里的表述以代码、manifest、CLI 入口、runtime artifact 和测试覆盖为准；如果和旧文档或聊天记忆冲突，以代码为准。

这份文档重点解释：

1. `agentsystem` 现在已经做完哪些正式能力。
2. Story / Sprint / Roadmap 在系统里是怎么被契约化、编排、执行、验证、收口的。
3. `gstack` 迁移到哪一步了，本地适配和上游公开仓库还有哪些差异。
4. fresh session 为什么可以不依赖聊天历史继续往下干。

一句话总结：

`agentsystem` 现在已经不是一个“多 Agent demo”，而是一个带 Story/Sprint 语义、质量闸门、续跑记忆、交付审计和多项目 dashboard 的 Agent 软件工厂控制面。

## 2. 当前已经完成的 12 类核心能力

## 2.1 需求拆解与 backlog 生成

- 能把长需求拆成 `Sprint -> Epic -> Story`。
- 能在 `tasks/backlog_v1/` 或 roadmap 目录下落出正式 backlog 结构。
- 能生成：
  - `sprint_overview.md`
  - `sprint_plan.md`
  - `execution_order.txt`
  - epic 说明文档
  - story yaml task card
- 支持内置 blueprint，也支持从 requirement 文档直接生成。

对应实现：

- `src/agentsystem/agents/requirements_analyst_agent.py`
- CLI：`analyze`、`split_requirement`、`auto-deliver`

## 2.2 TaskCard、Story Contract 与正式准入

- 每个 Story 先经过 `TaskCard` 规范化。
- 系统会补齐：
  - `story_inputs`
  - `story_process`
  - `story_outputs`
  - `verification_basis`
- 在正式执行前，系统还会补全 Story contract：
  - `implementation_contract`
  - `contract_scope_paths`
  - `agent_execution_contract`
  - `parity_evidence_contract`
  - `mode_to_agent_map`
  - `expanded_required_agents`
- admission 不只是检查 acceptance 和 file scope，还会检查：
  - required modes 是否已解析
  - UI/browser Story 是否声明浏览器表面
  - Sprint/roadmap 自动运行是否拿到 pre-hook 产物
  - story contract 是否完整

对应实现：

- `src/agentsystem/core/task_card.py`
- `src/agentsystem/orchestration/story_contracts.py`
- `src/agentsystem/orchestration/workflow_admission.py`

## 2.3 Agent 自动激活与模式推导

- 系统会根据 file scope、story kind、risk、bugfix、UI/browser 表面、release closeout 等条件自动推导：
  - `required_modes`
  - `advisory_modes`
  - `qa_strategy`
  - `effective_qa_mode`
  - `upstream_agent_parity`
  - `fixer_allowed`
- planning、bugfix、UI、release closeout 走的是不同链路，不需要手工写一大串 mode。

对应实现：

- `src/agentsystem/orchestration/agent_activation_resolver.py`

## 2.4 LangGraph 工作流编排

- 主工作流已经 manifest 化，不是 prompt 口头约定。
- 当前 `software_engineering` 工作流有 29 个节点。
- 支持：
  - node manifest
  - conditional edges
  - routers
  - fixer 回路
  - stop-after mode entry

对应实现：

- `config/workflows/software_engineering.yaml`
- `src/agentsystem/orchestration/workflow_registry.py`
- `src/agentsystem/graph/dev_workflow.py`

## 2.5 gstack 适配模式与宿主包装层

- 已经把一批 `gstack` 核心能力适配成可执行本地 mode。
- 当前本地 `codex_skills/` 下有 16 个 Codex 适配 mode：
  - `office-hours`
  - `plan-ceo-review`
  - `plan-eng-review`
  - `investigate`
  - `browse`
  - `plan-design-review`
  - `design-consultation`
  - `review`
  - `qa`
  - `qa-only`
  - `qa-design-review`
  - `design-review`
  - `setup-browser-cookies`
  - `ship`
  - `document-release`
  - `retro`
- `.claude/agents/` 是 Claude host 包装层。
- `vendors/gstack/` 是 pinned upstream mirror。
- `config/platform/gstack_parity_manifest.yaml` 是本地 parity 真相源。

这意味着系统现在不只是“流程里有这些节点”，而是已经有：

- upstream mirror
- local adapter
- workflow wiring
- parity audit

对应实现：

- `codex_skills/`
- `.claude/agents/`
- `vendors/gstack/`
- `config/platform/gstack_parity_manifest.yaml`

## 2.6 Story 级正式交付链

普通 Story 的正式主链现在是：

1. `requirement_analysis`
2. `architecture_review`
3. `workspace_prep`
4. builder 分流
5. `sync_merge`
6. `code_style_reviewer`
7. `tester`
8. `browser_qa` 或 `runtime_qa`
9. `security_scanner`
10. `reviewer`
11. `code_acceptance`
12. `acceptance_gate`
13. `doc_writer`

如果中间任何关键门失败，还会进入：

- `fixer -> 回到出问题的门之前`

对应实现：

- `config/workflows/software_engineering.yaml`
- `src/agentsystem/graph/dev_workflow.py`

## 2.7 UI / Browser / Design 证据链

UI Story 已经不是“改完代码后看一眼”。

当前系统已落地：

- `setup-browser-cookies`
- `browse`
- `plan-design-review`
- `design-consultation`
- `browser_qa`
- `qa_design_review`
- `design-review`

并且会沉淀：

- 浏览器 session / storage state
- observation
- screenshot
- `DESIGN.md`
- before / after evidence
- design scorecard

对应实现：

- `src/agentsystem/agents/browser_qa_agent.py`
- `src/agentsystem/agents/design_*`
- `src/agentsystem/agents/setup_browser_cookies_agent.py`

## 2.8 Sprint 前后钩子与 closeout

Sprint 不只是顺序跑 Story。

当前 pre-hooks 已生成：

- `sprint_agent_advice.json`
- `office_hours_report.md`
- `product_review_report.md`
- `sprint_framing_artifact.json`
- `parity_manifest.json`
- `acceptance_checklist.md`

当前 post-hooks 已生成：

- `ship_readiness_report.md`
- `ship_advice.json`
- `document_release_report.md`
- `retro_report.md`
- `sprint_close_bundle.json`
- 特定 Sprint 的运行时专项验证

对应实现：

- `src/agentsystem/orchestration/sprint_hooks.py`

## 2.9 Roadmap 级批量交付与无效批次回滚

除单 Sprint 外，系统已经支持 roadmap 级执行。

当前已具备：

- `run-roadmap`
- roadmap preflight
- `--resume`
- `--force-rerun`
- invalid batch 标记
- invalid batch cleanup
- 从 roadmap 级 safe point 重新开始

这层能力的意义是：

- 系统已经能处理“多 Sprint 连续交付”
- 也能处理“上一批产物不可信，需要正式吊销并重跑”

对应实现：

- CLI：`run-roadmap`、`invalidate-roadmap-batch`、`cleanup-invalid-batch`
- `src/agentsystem/orchestration/roadmap_invalid_batch.py`

## 2.10 Dashboard 多项目控制台

dashboard 现在已经不是简单 task list。

当前已支持：

- tasks / task detail / collaboration trace
- backlog / sprint / story 层级视图
- acceptance review 读写
- metrics
- websocket 事件流
- project registry
- 多项目 runtime showcase

当前项目面板已覆盖：

- `agentsystem`
- `versefina`
- `finahunt`
- `agentHire`

对应实现：

- `src/agentsystem/dashboard/main.py`
- `src/agentsystem/dashboard/static/index.html`
- `src/agentsystem/dashboard/static/story.html`

## 2.11 Runtime Memory、Continuity 与 Handoff

系统现在不只是记结果，还记“为什么可以从这里继续”。

当前已落地：

- `tasks/runtime/auto_resume_state.json`
- `tasks/runtime/story_admissions/`
- `tasks/runtime/story_failures/`
- `tasks/runtime/story_handoffs/`
- `tasks/runtime/agent_coverage_report.json`
- `tasks/runtime/agent_coverage_report.md`
- `tasks/story_status_registry.json`
- `tasks/story_acceptance_reviews.json`
- `docs/handoff/current_handoff.md`
- workspace `.meta/<repo>/continuity/`
- root `NOW.md`
- root `STATE.md`
- root `DECISIONS.md`

并且 continuity 不是静态文档，而是带 guard 的：

- 会检查 staleness
- 会生成 read set
- 会把 continuity bundle 注入 task payload
- 会在 resume interrupt 场景下阻止“带着过期上下文继续干”

对应实现：

- `src/agentsystem/orchestration/runtime_memory.py`
- `src/agentsystem/orchestration/continuity.py`

## 2.12 gstack Parity Audit 与 Full Parity Evidence

系统已经不是“口头说接近 gstack”。

当前有正式 parity 机制：

- `audit-gstack-parity` CLI
- `parity_manifest.json`
- `acceptance_checklist.md`
- `runs/parity/full_parity_evidence.json`
- per-mode structural checks
- dogfood target evaluation

也就是说，本地已经有能力区分：

- `template_only`
- `partial_runtime`
- `workflow_wired`
- `full_parity`

对应实现：

- `src/agentsystem/orchestration/gstack_parity_audit.py`
- `src/agentsystem/orchestration/full_parity_evidence.py`

## 3. 核心架构怎么理解

当前 `agentsystem` 可以按 8 层理解。

## 3.1 输入层

- requirement 文本 / markdown
- story yaml
- sprint dir
- roadmap prefix

## 3.2 协议层

- `TaskCard`
- implementation contract
- agent execution contract
- parity evidence contract
- story admission

## 3.3 激活策略层

- story kind / risk / browser surface 推断
- required/advisory mode 推断
- QA 策略推断

## 3.4 工作流定义层

- workflow manifest
- agent manifest
- skill mode manifest
- parity manifest

## 3.5 执行层

- planning
- build
- QA
- review
- acceptance
- closeout

## 3.6 质量与证据层

- quality sentry
- artifact inventory
- scope drift
- parity evidence
- acceptance evidence

说明：

`quality_sentry` 是编排和证据层能力，不是单独 workflow node。

## 3.7 记忆与续跑层

- runtime memory
- checkpoint / resume
- continuity docs
- handoff

## 3.8 可视化与运营层

- dashboard
- runtime showcase
- project metrics
- websocket timeline

## 4. 目录如何理解

最关键的目录现在是：

```text
agentsystem/
  cli.py
  config/
  src/agentsystem/
  codex_skills/
  .claude/agents/
  vendors/gstack/
  docs/
  tasks/
  runs/
  repo-worktree/
```

### `cli.py`

统一入口。

当前关键命令包括：

- `run-task`
- `analyze`
- `split_requirement`
- `run-sprint`
- `auto-deliver`
- `run-roadmap`
- `invalidate-roadmap-batch`
- `cleanup-invalid-batch`
- `plan-ceo-review`
- `render-agent-skills`
- `audit-gstack-parity`
- `dashboard`

### `config/workflows/`

workflow 真相源。

### `config/agents/software_engineering/`

workflow node 对应的 agent manifest。

### `config/skill_modes/`

mode 入口定义。

### `config/platform/`

和上游平台对齐相关的 parity 规则与 manifest。

### `src/agentsystem/orchestration/`

整个控制层的大脑，当前重点模块包括：

- `agent_activation_resolver.py`
- `workflow_admission.py`
- `story_contracts.py`
- `quality_sentry.py`
- `runtime_memory.py`
- `continuity.py`
- `sprint_hooks.py`
- `gstack_parity_audit.py`
- `roadmap_invalid_batch.py`

### `codex_skills/`

Codex host 适配包。这里是本地 mode 如何以 Codex 可消费形式暴露出去的关键目录。

### `.claude/agents/`

Claude host 包装层。

### `vendors/gstack/`

本地 pinned upstream mirror，不代表本地已经 full parity。

### `tasks/`

规划资产、注册表和 runtime 状态。

### `runs/`

正式审计、artifact、event、sprint closeout、parity audit。

## 5. 现在至少有 5 种“Agent/Mode/Package”概念

## 5.1 工作流节点 Agent

真正执行流程的 LangGraph 节点。

例如：

- `requirement_analysis`
- `tester`
- `reviewer`
- `acceptance_gate`

## 5.2 Skill Mode

对外的入口模式。

例如：

- `plan-eng-review`
- `qa`
- `browse`
- `ship`

## 5.3 Host Package

给宿主消费的包装层：

- `.claude/agents/`
- `codex_skills/`

## 5.4 Upstream Mirror

`vendors/gstack/` 里的 upstream mirror，回答的是：

- 上游怎么定义
- 本地是按哪个 commit 对齐的

## 5.5 Contract / Evidence Evaluator

这不是 slash skill，也不是 workflow node，而是控制层评估器：

- `story_contracts.py`
- `quality_sentry.py`
- `gstack_parity_audit.py`

## 6. 当前工作流里的 29 个节点

| 节点 | 角色 | 核心作用 |
| :--- | :--- | :--- |
| `office_hours` | 需求框定 | 六个高杠杆问题或 framing 产物 |
| `requirement_analysis` | Story 解析 | 把 task 变成 subtasks / contract |
| `plan_ceo_review` | 产品级规划 | requirement doc / opportunity map |
| `architecture_review` | 工程规划 | execution shape / edge cases / test plan |
| `investigate` | 根因调查 | bugfix 前先做证据和 root cause |
| `browse` | 浏览器观察 | report-only 页面证据采集 |
| `plan_design_review` | 设计规划审查 | route score / DESIGN.md |
| `design_consultation` | 设计咨询 | 视觉方向 / preview / handoff |
| `setup_browser_cookies` | 会话准备 | storage state / cookie import |
| `workspace_prep` | 工作区准备 | 检查门槛、分支、工作树 |
| `backend_dev` | 后端开发 | API / service / runtime 代码 |
| `frontend_dev` | 前端开发 | 页面 / 组件 / 交互 |
| `database_dev` | 数据开发 | schema / SQL / storage |
| `devops_dev` | DevOps 开发 | CI / infra / env |
| `sync_merge` | 结果归并 | builder 结果进入统一验证链 |
| `code_style_reviewer` | 风格预审 | UTF-8 / tab / trailing space / hygiene |
| `tester` | 测试执行 | install / lint / typecheck / test |
| `browser_qa` | 浏览器 QA | 页面、截图、控制台、健康分 |
| `runtime_qa` | 运行时 QA | command / gate check / 结构化 findings |
| `qa_design_review` | 设计感知 QA | browser evidence + design contract 验收 |
| `fixer` | 自动修复 | 回修失败节点 |
| `security_scanner` | 安全扫描 | 敏感配置和安全风险检查 |
| `reviewer` | 工程审查 | 生产风险、scope drift、验证充分性 |
| `code_acceptance` | 代码验收 | 文件卫生与可读性 |
| `acceptance_gate` | 最终验收门 | acceptance criteria / scope drift |
| `doc_writer` | Story 文档收口 | delivery / result / completion 文档 |
| `ship` | 发版就绪 | release package / readiness |
| `document_release` | 文档发布同步 | docs 漂移同步 |
| `retro` | 回顾复盘 | 指标、问题、下一步 |

## 7. 当前 mode 入口一览

当前主 skill mode 如下：

| mode | 从哪开始 | 到哪停止 | 用途 |
| :--- | :--- | :--- | :--- |
| `office-hours` | `office_hours` | `office_hours` | 需求 framing |
| `plan-ceo-review` | `plan_ceo_review` | `plan_ceo_review` | 产品级规划 |
| `plan-eng-review` | `requirement_analysis` | `architecture_review` | 工程规划 |
| `investigate` | `investigate` | `investigate` | 根因分析 |
| `browse` | `browse` | `browse` | 浏览器观察 |
| `plan-design-review` | `plan_design_review` | `plan_design_review` | UI 设计规划 |
| `design-consultation` | `design_consultation` | `design_consultation` | 设计合同 |
| `review` | `reviewer` | `reviewer` | 风险 review |
| `qa` | `tester` | `browser_qa` / `runtime_qa` | QA + fixer |
| `qa-only` | `tester` | `browser_qa` / `runtime_qa` | report-only QA |
| `qa-design-review` | `browser_qa` | `qa_design_review` | 设计感知 QA |
| `design-review` | `browser_qa` | `qa_design_review` | 后置设计审查 |
| `setup-browser-cookies` | `setup_browser_cookies` | `setup_browser_cookies` | 导入认证态会话 |
| `ship` | `ship` | `ship` | 发布就绪 |
| `document-release` | `document_release` | `document_release` | 文档同步 |
| `retro` | `retro` | `retro` | Sprint 回顾 |

## 8. 普通 Story 是怎么跑完的

## 8.1 先有 TaskCard 和 Story Contract

Story 至少要有：

- `goal`
- `acceptance_criteria`
- `related_files`

系统会自动补：

- input / process / output / verification
- implementation contract
- agent execution contract
- parity evidence contract

## 8.2 admission 不通过，Story 不会正式开始

当前 admission 会挡住这些问题：

- 没 acceptance criteria
- 没 file scope
- required modes 解析失败
- UI/browser Story 没浏览器表面
- sprint 自动运行缺 pre-hook
- story contract 不完整

产物：

- `tasks/runtime/story_admissions/<story_id>.json`

## 8.3 进入 planning/build/verify/acceptance 正式链

普通 Story 一般会走：

1. `requirement_analysis`
2. `architecture_review`
3. `workspace_prep`
4. builder 分流
5. `sync_merge`
6. `code_style_reviewer`
7. `tester`
8. `runtime_qa` 或 `browser_qa`
9. `security_scanner`
10. `reviewer`
11. `code_acceptance`
12. `acceptance_gate`
13. `doc_writer`

## 8.4 fixer 不是固定回到 test

`fixer` 会识别失败来源，然后回到正确节点前：

- `code_style_reviewer`
- `tester`
- `browser_qa`
- `runtime_qa`
- `reviewer`
- `code_acceptance`
- `acceptance_gate`

## 8.5 现在的完成定义不是“代码改完”

系统区分：

- `implemented`
- `verified`
- `agentized`
- `accepted`

如果 required Agent 没跑，即使代码存在，也不算 fully done。

## 9. UI Story 会多走哪些链路

UI Story 当前正式链大致是：

1. `requirement_analysis`
2. `architecture_review`
3. `setup_browser_cookies`（如果需要认证）
4. `browse`
5. `plan_design_review`
6. `design_consultation`
7. `workspace_prep`
8. builder
9. `code_style_reviewer`
10. `tester`
11. `browser_qa`
12. `qa_design_review`
13. `security_scanner`
14. `reviewer`
15. `code_acceptance`
16. `acceptance_gate`
17. `doc_writer`

这套链路已经把：

- 页面证据
- 设计合同
- before/after 证据
- route-level findings

正式变成 Story 完成的一部分。

## 10. bugfix Story 会多走哪些链路

bugfix 当前硬规则是：

- 没 `investigate`，就不能假装正式修完

标准链：

1. `investigate`
2. `workspace_prep`
3. build / fix
4. `tester`
5. `browser_qa` 或 `runtime_qa`
6. `security_scanner`
7. `reviewer`
8. `code_acceptance`
9. `acceptance_gate`
10. `doc_writer`

## 11. Sprint 和 Roadmap 现在怎么跑

## 11.1 Sprint

当前 Sprint 不是“多个 Story 顺序执行”这么简单。

正式流程是：

1. pre-hooks
2. 按 `execution_order.txt` 跑 Story
3. 更新 status / acceptance / coverage / handoff
4. post-hooks

关键 Sprint 产物：

- `runs/sprints/<project>/<sprint>/sprint_agent_advice.json`
- `runs/sprints/<project>/<sprint>/sprint_framing_artifact.json`
- `runs/sprints/<project>/<sprint>/parity_manifest.json`
- `runs/sprints/<project>/<sprint>/acceptance_checklist.md`
- `runs/sprints/<project>/<sprint>/ship_advice.json`
- `runs/sprints/<project>/<sprint>/document_release_report.md`
- `runs/sprints/<project>/<sprint>/retro_report.md`
- `runs/sprints/<project>/<sprint>/sprint_close_bundle.json`

## 11.2 Roadmap

Roadmap 是当前代码里已经存在、但旧文档没讲清的一层能力。

当前支持：

- roadmap preflight
- roadmap summary
- safe point resume
- invalid batch 吊销
- invalid batch cleanup

这意味着系统现在已经能处理：

- 多 Sprint 长链交付
- 历史成功被吊销重跑
- authoritative run 与 evidence-only run 的区分

## 12. 运行时记忆、续跑与交接

当前最重要的不是“有没有报告”，而是“fresh session 能不能正确续上”。

当前关键文件：

- `tasks/runtime/auto_resume_state.json`
- `tasks/runtime/story_admissions/<story_id>.json`
- `tasks/runtime/story_handoffs/<story_id>.md`
- `tasks/runtime/story_failures/<story_id>.json`
- `tasks/runtime/agent_coverage_report.json`
- `tasks/runtime/agent_coverage_report.md`
- `tasks/story_status_registry.json`
- `tasks/story_acceptance_reviews.json`
- `.meta/<repo>/continuity/continuity_manifest.json`
- `NOW.md`
- `STATE.md`
- `DECISIONS.md`
- `docs/handoff/current_handoff.md`

当前还区分：

- authoritative attempt
- evidence-only attempt
- accepted but mode coverage follow-up

所以现在的 handoff 已经不是“写一段总结”，而是正式 runtime state。

## 13. Dashboard 现在能看什么

当前 dashboard 已完成的视图包括：

### 13.1 Task 视角

- `/api/tasks`
- `/api/tasks/{task_id}`
- `/api/tasks/{task_id}/collaboration`

### 13.2 Backlog / Sprint / Story 视角

- `/api/backlogs`
- `/api/backlogs/{backlog_id}`
- `/api/backlogs/{backlog_id}/sprints/{sprint_id}`
- `/api/backlogs/{backlog_id}/sprints/{sprint_id}/stories/{story_id}`

### 13.3 Acceptance Review 视角

- `GET /api/backlogs/{...}/acceptance-review`
- `POST /api/backlogs/{...}/acceptance-review`

### 13.4 Project / Runtime 视角

- `/api/projects`
- `/projects/{project_id}/runtime`
- `/api/projects/{project_id}/runtime/showcase`
- `/api/projects/{project_id}/runtime/runs`

### 13.5 实时执行视角

- `/ws/{task_id}`

## 14. 常用命令清单（按当前代码）

```powershell
cd D:\lyh\agent\agent-frame\agentsystem

# 1. 跑单个 Story
python cli.py run-task --task-file D:\path\to\story.yaml --env test --project versefina

# 2. 需求拆解
python cli.py analyze -r "你的需求" --project versefina --prefix backlog_v1
python cli.py split_requirement --requirement-file D:\path\to\requirement.md --project finahunt --prefix backlog_v1

# 3. 跑单个 Sprint
python cli.py run-sprint --sprint-dir D:\path\to\sprint_dir --env test --project versefina

# 4. 自动交付
python cli.py auto-deliver --requirement-file D:\path\to\requirement.md --env test --project finahunt --prefix backlog_v1 --auto-run

# 5. 跑 Roadmap
python cli.py run-roadmap --tasks-root D:\lyh\agent\agent-frame\versefina\tasks --roadmap-prefix roadmap_1_6 --project versefina --env test

# 6. 吊销并清理无效批次
python cli.py invalidate-roadmap-batch --project versefina --env test --roadmap-prefix roadmap_1_6
python cli.py cleanup-invalid-batch --project versefina --env test --roadmap-prefix roadmap_1_6

# 7. 单独做 Plan CEO Review
python cli.py plan-ceo-review --requirement-file D:\path\to\requirement.md --project versefina --delivery-mode interactive

# 8. 渲染 host skill 包
python cli.py render-agent-skills

# 9. 做 gstack parity audit
python cli.py audit-gstack-parity --project finahunt

# 10. 启动 dashboard
python cli.py dashboard --host 127.0.0.1 --port 8010
```

## 15. 当前与 gstack 的差异（按 2026-03-25 公开仓库状态）

这一节说的是：

- 本地 `agentsystem` 当前代码
- 对比 `gstack main` 在 2026-03-25 的公开仓库状态

不是对比本地 pinned commit，也不是对比想象中的上游。

### 15.1 对比基线

- 本地 formal parity pinned commit：
  - `8ddfab233d3999edb172bed54aaf06fc5ff92646`
- 上游公开仓库最新提交（扫描时）：
  - `9870a4ec49078ad3fc150c3d93605401a747af6d`
- 上游 `main` pushed at：
  - `2026-03-25T04:01:22Z`

### 15.2 数量层面的当前事实

- 本地 `codex_skills/` 适配 mode：16 个
- 本地 vendored `gstack` skill 目录：18 个
- 上游 `gstack main` 当前公开 skill 目录：27 个

上游当前公开 skill 目录包括：

- `autoplan`
- `benchmark`
- `browse`
- `canary`
- `careful`
- `codex`
- `cso`
- `design-consultation`
- `design-review`
- `document-release`
- `freeze`
- `gstack-upgrade`
- `guard`
- `investigate`
- `land-and-deploy`
- `office-hours`
- `plan-ceo-review`
- `plan-design-review`
- `plan-eng-review`
- `qa`
- `qa-only`
- `retro`
- `review`
- `setup-browser-cookies`
- `setup-deploy`
- `ship`
- `unfreeze`

### 15.3 你已经明显更强的地方

相对 `gstack`，`agentsystem` 当前已经更强的地方主要在“系统工程控制面”：

- Story / Sprint / Roadmap 原生语义
- `implemented / verified / agentized / accepted` 完成定义
- story status / acceptance review / agent coverage 正式注册表
- multi-repo dashboard 与 runtime showcase
- continuity docs 与 guard
- invalid batch 吊销与重跑

换句话说：

`gstack` 更像强大的 Agent 工作习惯集合，`agentsystem` 已经更接近“带审计语义的软件工厂控制台”。

### 15.4 仍明显落后的地方

当前最重要的差距仍然在 Agent 能力和 host 行为层：

#### `browse`

- 本地仍是 Playwright 适配型 browser runtime
- 上游已经是持久化本地 daemon + `.gstack/browse.json` + 丰富命令面 + tab / chain / handoff / resume 体系

#### 互动式规划

- 上游 `office-hours` 明确依赖 `AskUserQuestion`
- 上游更强调 one-question-at-a-time 决策节奏、repo mode、upgrade/check、telemetry prompt、session habit
- 本地当前更偏 workflow artifact 产出，互动节奏明显更轻

#### `ship`

- 上游目标是：merge base、跑测试、review diff、bump version、更新 changelog、commit、push、create PR
- 本地当前 `ship` 仍主要是 readiness/report/package，离正式 landing choreography 还有差距

#### 专项 Agent 覆盖

本地现在还没有完整接入：

- `cso`
- `benchmark`
- `land-and-deploy`
- `canary`
- `setup-deploy`
- `codex`
- `autoplan`
- `careful`
- `unfreeze`

另外虽然 vendored 了：

- `freeze`
- `guard`
- `gstack-upgrade`

但本地还没有把它们都做成正式 runtime mode。

### 15.5 当前最诚实的结论

截至 2026-03-25，本地 `agentsystem` 的真实状态不是“已经超过 gstack 全部能力”，而是：

- 在 Story/Sprint/控制面/审计/continuity 上已经形成明显系统优势
- 在 browse、互动规划、release automation、专项 Agent 覆盖上仍未达到 `gstack main` 当前公开水平

所以更准确的表述应该是：

`agentsystem` 已经具备比 gstack 更强的流程控制和交付审计能力，但关键 Agent 能力本身还在 parity 途中。

## 16. 下一阶段看哪份文档

如果你想看：

- “现在已经做到了什么”
  - 继续看本文
- “怎么先达到 gstack 水平，再逐步超过它”
  - 看：
    - [agentsystem_gstack_capability_upgrade_roadmap.md](D:/lyh/agent/agent-frame/agentsystem/docs/standards/agentsystem_gstack_capability_upgrade_roadmap.md)

一句话收尾：

`agentsystem` 当前已经完成的是一个可执行、可审计、可恢复、可多项目运营的 Agent 软件工厂控制面；但如果目标是“Agent 能力本身先达到 gstack 水平，再逐步超过”，下一阶段仍然要优先补浏览器 host、互动式规划、release automation 和专项 Agent 覆盖。
