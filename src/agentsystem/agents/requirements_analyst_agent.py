from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from langchain_core.prompts import ChatPromptTemplate

from agentsystem.llm.client import get_llm

CONTRACTS_DIR = "docs/contracts"
API_DIR = "apps/api/src"
WEB_DIR = "apps/web/src"

AGENT_MARKETPLACE_V2_BACKLOG: list[dict[str, Any]] = [
    {"name": "Evaluation Layer", "description": "Standardize deeper scorecards, pairwise comparison pages, and recommendation logic after Phase 1 discovery surfaces are stable."},
    {"name": "Matching Broker", "description": "Add qualified request routing and builder matching once request leads show repeatable demand."},
    {"name": "Service Wrapping", "description": "Wrap selected high-quality agents into callable services only after the curated marketplace proves usability."},
    {"name": "Provider Portal", "description": "Delay open builder onboarding, self-serve listings, and monetization controls until curated operations are repeatable."},
]

AGENT_MARKETPLACE_BACKLOG_BLUEPRINT: list[dict[str, Any]] = [
    {
        "number": 0,
        "slug": "project_bootstrap",
        "name": "Project Bootstrap",
        "goal": "Create the agentHire repo skeleton, contracts, and automation-ready project rules so AgentSystem can execute Phase 1 work end-to-end.",
        "out_of_scope": ["Do not implement marketplace business logic yet.", "Do not add external cloud services or deployment automation."],
        "epics": [
            {
                "code": "0_1",
                "slug": "repo_contracts",
                "title": "Repo Contracts",
                "description": "Define repo-local contracts, commands, and project layout expected by the software factory.",
                "stories": [
                    ("S0-001", "AgentHire Repo Contract Pack", "Create .agents contracts, command definitions, and review rules for agentHire."),
                    ("S0-002", "Backend And Frontend Workspace Bootstrap", "Bootstrap FastAPI and Next.js application roots with local startup commands."),
                    ("S0-003", "Project Environment And Seed Scripts", "Add env examples, seed placeholders, and developer scripts needed by automated delivery."),
                    ("S0-004", "Backlog And Registry Foundation", "Create tasks registries, docs/contracts root, and baseline project documentation."),
                ],
            }
        ],
    },
    {
        "number": 1,
        "slug": "foundation_and_contracts",
        "name": "Foundation And Contracts",
        "goal": "Establish the data model, migrations, API contracts, and admin session baseline for the curated Agent Marketplace.",
        "out_of_scope": ["Do not build the public browsing experience yet.", "Do not implement direct marketplace transactions."],
        "epics": [
            {
                "code": "1_1",
                "slug": "data_foundation",
                "title": "Data Foundation",
                "description": "Lay down the schema, settings, and core data contracts for agents, evaluations, content, and request leads.",
                "stories": [
                    ("S1-001", "Marketplace Schema And Migration Baseline", "Define the Phase 1 database schema and migration baseline for catalog, evaluations, content, analytics, and leads."),
                    ("S1-002", "Pydantic Contracts And API Envelope", "Create shared request/response contracts, error envelope, and pagination models."),
                    ("S1-003", "Admin Session And Access Guard", "Implement minimal admin session auth backed by environment-configured credentials."),
                    ("S1-004", "Taxonomy And Seed Import Contract", "Define taxonomy and seed import contracts for curated catalog ingestion."),
                ],
            }
        ],
    },
    {
        "number": 2,
        "slug": "public_discovery_surfaces",
        "name": "Public Discovery Surfaces",
        "goal": "Ship the homepage, search, filters, and list experience that lets users discover curated agents by task, industry, and capability.",
        "out_of_scope": ["Do not build direct in-platform agent execution.", "Do not build complex recommendation or ranking engines."],
        "epics": [
            {
                "code": "2_1",
                "slug": "catalog_discovery",
                "title": "Catalog Discovery",
                "description": "Expose homepage and listing surfaces backed by catalog and taxonomy read APIs.",
                "stories": [
                    ("S2-001", "Catalog List Query API", "Implement searchable, filterable, sortable catalog listing API for public discovery surfaces."),
                    ("S2-002", "Taxonomy Query API", "Serve category buckets for industry, task, capability, integration, and pricing filters."),
                    ("S2-003", "Homepage Discovery Surface", "Build the public homepage with hero search, featured agents, and category entry points."),
                    ("S2-004", "Agent List Surface", "Build the list page with filter state, sorting, pagination, and card rendering."),
                ],
            }
        ],
    },
    {
        "number": 3,
        "slug": "detail_evaluation_and_content",
        "name": "Detail, Evaluation, And Content",
        "goal": "Help users understand and compare curated agents through structured detail pages, evaluations, similar agents, and content entry pages.",
        "out_of_scope": ["Do not build automated recommendation models.", "Do not open a provider upload workflow."],
        "epics": [
            {
                "code": "3_1",
                "slug": "detail_and_evaluation",
                "title": "Detail And Evaluation",
                "description": "Build the agent detail read model, evaluation surface, and CTA analytics hooks.",
                "stories": [
                    ("S3-001", "Agent Detail Read API", "Aggregate agent profile, categories, evaluation, integrations, use cases, and similar agents into one detail response."),
                    ("S3-002", "Evaluation And Use-Case Persistence", "Persist and expose evaluation dimensions, pros/cons, use cases, and integrations."),
                    ("S3-003", "Agent Detail Page", "Build the public detail page with evaluation sections, scenarios, pros/cons, and CTA entry points."),
                    ("S3-004", "Similar Agents And CTA Analytics", "Add rule-based similar agent recommendations and CTA analytics capture."),
                ],
            },
            {
                "code": "3_2",
                "slug": "content_surfaces",
                "title": "Content Surfaces",
                "description": "Support rankings, guides, and comparison articles as SEO and education surfaces.",
                "stories": [
                    ("S3-005", "Content Post API And Markdown Rendering", "Serve guide, ranking, and comparison content with markdown rendering support."),
                    ("S3-006", "Content Pages And SEO Metadata", "Build content pages with metadata, structured headings, and public navigation entry points."),
                ],
            },
        ],
    },
    {
        "number": 4,
        "slug": "leads_and_admin_cms",
        "name": "Leads And Admin CMS",
        "goal": "Give users a lightweight request path and give internal operators the admin tools needed to curate and publish catalog data.",
        "out_of_scope": ["Do not add public user accounts.", "Do not build builder self-serve portals or chat workflows."],
        "epics": [
            {
                "code": "4_1",
                "slug": "request_leads",
                "title": "Request Leads",
                "description": "Capture custom agent demand when users cannot find a good fit in the curated directory.",
                "stories": [
                    ("S4-001", "Request Lead Submit API", "Implement the public request-lead submission endpoint with validation and persistence."),
                    ("S4-002", "Need A Custom Agent Page", "Build the lightweight request form page and success state."),
                    ("S4-003", "Lead Status Management", "Expose lead list and status transitions for internal operations."),
                ],
            },
            {
                "code": "4_2",
                "slug": "admin_cms",
                "title": "Admin CMS",
                "description": "Allow internal operators to create, edit, publish, and unpublish agents, evaluations, taxonomy, and content.",
                "stories": [
                    ("S4-004", "Admin Agent CRUD Surface", "Create the admin CRUD flow for curated agent records."),
                    ("S4-005", "Admin Evaluation Content And Taxonomy CRUD", "Add admin editing flows for evaluations, taxonomy, and content posts."),
                    ("S4-006", "Publish Visibility Rules", "Enforce publish/unpublish visibility rules between admin and public surfaces."),
                ],
            },
        ],
    },
    {
        "number": 5,
        "slug": "hardening_and_delivery_proof",
        "name": "Hardening And Delivery Proof",
        "goal": "Prove the Phase 1 marketplace can be seeded, tested, started locally, and driven by AgentSystem with backlog visibility and delivery evidence.",
        "out_of_scope": ["Do not implement payment, subscriptions, or service wrapping.", "Do not extend into Phase 2-4 business workflows."],
        "epics": [
            {
                "code": "5_1",
                "slug": "quality_and_seed_data",
                "title": "Quality And Seed Data",
                "description": "Finish automated tests, seed data, local startup scripts, and delivery evidence for Phase 1.",
                "stories": [
                    ("S5-001", "Backend Frontend And Smoke Test Coverage", "Add test coverage for public catalog, request leads, admin auth, and key frontend routes."),
                    ("S5-002", "Seed Catalog And Content Pack", "Provide 20 curated sample agents, taxonomy values, evaluations, and baseline content pages."),
                    ("S5-003", "Automation Proof And Runbook", "Document and verify the local run path and AgentSystem auto-delivery proof for agentHire."),
                ],
            }
        ],
    },
]


FINANCE_BACKLOG_BLUEPRINT: list[dict[str, Any]] = [
    {
        "number": 0,
        "slug": "contract_foundation",
        "name": "契约与基础设施钉死",
        "goal": "先把 schema、状态机、基础存储和审计底座钉死，避免后续返工。",
        "out_of_scope": ["不实现交割单解析逻辑", "不实现交易撮合", "不实现前端观察台"],
        "epics": [
            {
                "code": "0_1",
                "slug": "platform_contract",
                "title": "平台契约",
                "description": "先定义核心 schema、payload 契约、错误码和状态机。",
                "stories": [
                    ("S0-001", "TradingAgentProfile Schema", "定义 TradingAgentProfile 的统一 JSON Schema。"),
                    ("S0-002", "MarketWorldState Schema", "定义统一的 MarketWorldState Schema。"),
                    ("S0-003", "Agent Contract Schema", "定义 register、heartbeat、submit-actions 三类 payload schema。"),
                    ("S0-004", "错误码与状态流转规范", "定义 statement、agent、order、binding 的状态机与统一错误码。"),
                ],
            },
            {
                "code": "0_2",
                "slug": "foundation_storage",
                "title": "基础存储与底座",
                "description": "完成数据库表、对象存储、审计日志和幂等底座。",
                "stories": [
                    ("S0-005", "初始化核心 DB Schema", "创建 MVP 所需的核心写模型表结构。"),
                    ("S0-006", "对象存储与 Statement 元数据表", "打通交割单原件存储与 statements 元数据引用关系。"),
                    ("S0-007", "审计日志与幂等基础设施", "提供统一 audit write helper 和 idempotency check helper。"),
                ],
            },
        ],
    },
    {
        "number": 1,
        "slug": "statement_to_agent",
        "name": "交割单到 Agent 建模",
        "goal": "完成交割单上传、解析、标准化、profile 生成和 Agent 创建。",
        "out_of_scope": ["不实现世界状态与撮合逻辑", "不实现前端观察台"],
        "epics": [
            {
                "code": "1_1",
                "slug": "statement_ingestion",
                "title": "交割单摄入",
                "description": "实现上传 API、状态机、文件识别和上传失败路径。",
                "stories": [
                    ("S1-001", "交割单上传 API", "实现 CSV/XLSX 文件上传并落对象存储。"),
                    ("S1-002", "交割单状态机", "实现 statement 状态流转和非法跳转拦截。"),
                    ("S1-003", "文件类型识别", "识别 csv/xlsx 并路由到正确解析器。"),
                    ("S1-004", "上传失败处理", "覆盖上传阶段异常路径。"),
                ],
            },
            {
                "code": "1_2",
                "slug": "statement_parsing",
                "title": "交割单解析与标准化",
                "description": "把原始交割单映射为标准化 TradeRecord 并输出解析报告。",
                "stories": [
                    ("S1-005", "券商字段映射规则", "定义原始列名到统一字段的映射规则。"),
                    ("S1-006", "TradeRecord 标准化", "把原始记录转换为统一 TradeRecord。"),
                    ("S1-007", "解析校验与错误报告", "输出结构化解析结果与错误报告。"),
                ],
            },
            {
                "code": "1_3",
                "slug": "agent_profile",
                "title": "Agent DNA / Profile",
                "description": "从标准化交易记录中提取 profile 并创建 Agent。",
                "stories": [
                    ("S1-008", "规则版 Profile 提取", "从 TradeRecord 提取基础交易画像。"),
                    ("S1-009", "风格标签与风控约束生成", "生成 styleTags、riskControls、cadence。"),
                    ("S1-010", "Agent 创建 API", "基于 statement/profile/init_cash 创建 Agent。"),
                ],
            },
        ],
    },
    {
        "number": 2,
        "slug": "world_ledger_loop",
        "name": "世界、撮合、账本、日循环",
        "goal": "完成世界日历、行情、动作校验、撮合、账本和 Daily Loop。",
        "out_of_scope": ["不实现 Dashboard 前端", "不实现 OpenClaw 对外接入"],
        "epics": [
            {
                "code": "2_1",
                "slug": "market_calendar_data",
                "title": "市场日历与行情",
                "description": "构建交易日历、行情拉取、缓存和版本号。",
                "stories": [
                    ("S2-001", "交易日历同步", "接入 trade_cal。"),
                    ("S2-002", "当前交易日 / 下一交易日推进", "生成 tradingDay 和 nextTradingDay。"),
                    ("S2-003", "日线行情拉取", "接入 daily 行情数据。"),
                    ("S2-004", "行情缓存与版本号", "给 world snapshot 提供缓存和 dataVersion。"),
                ],
            },
            {
                "code": "2_2",
                "slug": "action_validation_risk",
                "title": "动作校验与风控",
                "description": "完成 schema 校验、风控、现金 / 仓位 / lot size 校验。",
                "stories": [
                    ("S2-005", "actions payload 校验", "校验 submit-actions 输入格式。"),
                    ("S2-006", "风控规则校验", "校验 maxPositionPct、maxHoldDays、turnover 等规则。"),
                    ("S2-007", "现金 / 仓位 / lot size 校验", "校验是否可下单。"),
                ],
            },
            {
                "code": "2_3",
                "slug": "matching_and_ledger",
                "title": "撮合与账本",
                "description": "实现收盘价撮合、手续费滑点、fill、portfolio/positions、幂等和对账。",
                "stories": [
                    ("S2-008", "收盘价撮合", "实现 MVP 阶段基于 close price 的撮合逻辑。"),
                    ("S2-009", "手续费与滑点模型", "实现 feePct/slipPct。"),
                    ("S2-010", "fill 生成与结算", "生成 fills 并更新现金。"),
                    ("S2-011", "portfolio / positions 更新", "基于 fills 更新持仓与组合。"),
                    ("S2-012", "幂等提交去重", "同 idempotency_key 不重复入账。"),
                    ("S2-013", "日终对账校验", "确保 equity = cash + 持仓市值。"),
                ],
            },
            {
                "code": "2_4",
                "slug": "daily_loop",
                "title": "Daily Loop",
                "description": "构建 context pack、规则版决策引擎、编排和当日摘要。",
                "stories": [
                    ("S2-014", "Context Pack 构建", "为每日决策生成 context。"),
                    ("S2-015", "规则版决策引擎", "MVP 用 rule-based 产生 actions。"),
                    ("S2-016", "Daily Loop 编排", "串起 context -> decide -> risk -> match -> settle。"),
                    ("S2-017", "Run Log 与当日摘要", "生成 daily summary 和审计日志。"),
                ],
            },
        ],
    },
    {
        "number": 3,
        "slug": "dashboard_openclaw",
        "name": "只读观察台 + OpenClaw-first 接入",
        "goal": "完成人类只读观察台和 OpenClaw-first 接入能力。",
        "out_of_scope": ["不实现 Event Bus、Shard Manager、多 runtime adapter", "不实现公开 Agent 广场"],
        "epics": [
            {
                "code": "3_1",
                "slug": "dashboard_read_api",
                "title": "Dashboard 读接口",
                "description": "完成 dashboard aggregate、positions/equity/logs 和访问控制。",
                "stories": [
                    ("S3-001", "dashboard aggregate API", "提供 Agent 观测台聚合接口。"),
                    ("S3-002", "positions / equity / logs API", "拆分 positions、equity curve、logs 明细接口。"),
                    ("S3-003", "公开页与权限控制", "支持 private/public 只读页。"),
                ],
            },
            {
                "code": "3_2",
                "slug": "readonly_frontend",
                "title": "只读前端",
                "description": "完成持仓面板、收益曲线、日志和只读护栏。",
                "stories": [
                    ("S3-004", "持仓面板", "展示当前持仓。"),
                    ("S3-005", "收益曲线", "展示 equity curve。"),
                    ("S3-006", "日志流与当日摘要", "展示交易日志与 summary。"),
                    ("S3-007", "只读护栏", "确保前端和 API 都无人工交易入口。"),
                ],
            },
            {
                "code": "3_3",
                "slug": "openclaw_adapter",
                "title": "OpenClaw-first 接入",
                "description": "完成 register、heartbeat、submit-actions、revoke 和接入文档。",
                "stories": [
                    ("S3-008", "OpenClaw register API", "绑定 openclaw_agent_id 并生成 agent_api_key。"),
                    ("S3-009", "OpenClaw heartbeat API", "接收运行时心跳。"),
                    ("S3-010", "OpenClaw submit-actions API", "OpenClaw Agent 能提交 actions。"),
                    ("S3-011", "binding / revoke", "支持解绑与失效处理。"),
                    ("S3-012", "OpenClaw Skill 与 Cron 文档", "产出可直接跑通的接入文档。"),
                ],
            },
        ],
    },
    {
        "number": 4,
        "slug": "agent_gallery_population",
        "name": "Agent 广场与群体运营",
        "goal": "让平台从单 Agent 演示升级为多 Agent 持续运行与可比较的展示平台。",
        "out_of_scope": ["不实现社交评论与关注系统", "不实现复杂推荐算法", "不实现多租户商业化治理"],
        "epics": [
            {
                "code": "4_1",
                "slug": "seed_population",
                "title": "种子 Agent 与批量供给",
                "description": "解决平台冷启动，确保一进入平台就能看到一批可运行 Agent。",
                "stories": [
                    ("S4-001", "seed agents bootstrap", "初始化一批官方种子 Agent，覆盖不同风格与市场偏好。"),
                    ("S4-002", "batch agent creation", "支持按模板或 profile 批量创建 Agent。"),
                ],
            },
            {
                "code": "4_2",
                "slug": "gallery_discovery",
                "title": "广场与发现",
                "description": "为大量 Agent 提供列表、筛选、浏览与只读公共展示能力。",
                "stories": [
                    ("S4-003", "agent index read model", "构建 Agent 列表页所需的索引读模型。"),
                    ("S4-004", "agent list API", "提供 Agent 列表、筛选、排序与分页接口。"),
                    ("S4-005", "agent gallery frontend", "实现 Agent 广场首页与卡片式浏览。"),
                    ("S4-008", "public profile and privacy", "完善公开页、私有页与分享策略。"),
                ],
            },
            {
                "code": "4_3",
                "slug": "compare_rankings",
                "title": "比较与榜单",
                "description": "让围观者能在统一世界里横向比较多个 Agent。",
                "stories": [
                    ("S4-006", "agent compare view", "支持多个 Agent 的收益、回撤、风格与活跃度对比。"),
                    ("S4-007", "leaderboard projection", "生成收益、回撤、活跃度等榜单投影。"),
                ],
            },
            {
                "code": "4_4",
                "slug": "lifecycle_operations",
                "title": "运行调度与生命周期",
                "description": "让很多 Agent 能持续运行、可暂停、可恢复、可归档。",
                "stories": [
                    ("S4-009", "batch daily loop scheduler", "支持按世界或批次调度多个 Agent 的 daily loop。"),
                    ("S4-010", "agent lifecycle ops", "支持 pause、resume、archive、stale 检测和批量运维。"),
                ],
            },
        ],
    },
]


V2_BACKLOG = [
    {"name": "Event Bus", "description": "后续用事件总线解耦 world、orders、fills、projection。"},
    {"name": "Read Model Projection", "description": "后续拆出 projection/read model 优化 Dashboard 和 Agent 广场。"},
    {"name": "Shard Manager", "description": "后续支持多 runtime / 多 Agent shard 调度。"},
]


def _looks_like_finance_world(requirement: str) -> bool:
    lowered = requirement.lower()
    markers = ["金融", "交割单", "撮合", "账本", "openclaw", "ledger", "portfolio", "statement", "agent-native"]
    return any(marker in requirement or marker in lowered for marker in markers)


def _looks_like_agent_marketplace(requirement: str, repo_name: str = "") -> bool:
    if str(repo_name or "").strip().lower() == "agenthire":
        return True
    lowered = requirement.lower()
    markers = [
        "agent marketplace",
        "agenthire",
        "curated agent directory",
        "find the right agent",
        "request lead",
        "custom agent",
        "agent evaluation",
        "agent directory",
    ]
    return any(marker in lowered for marker in markers)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value)
    return "_".join(part for part in slug.split("_") if part) or "item"


def _story_filename(story: dict[str, Any]) -> str:
    return f"{story['story_id']}_{_slugify(str(story['task_name']))}.yaml"


def _infer_agent_marketplace_paths(story_id: str, title: str, epic_slug: str) -> tuple[list[str], list[str]]:
    title_slug = _slugify(title)
    if epic_slug == "repo_contracts":
        if story_id == "S0-001":
            return ([".agents/project.yaml", ".agents/commands.yaml"], [".agents/contracts.yaml", ".agents/rules.yaml", ".agents/review_policy.yaml"])
        if story_id == "S0-002":
            return (["apps/api/src/main.py", "apps/web/src/app/page.tsx"], ["apps/api/pyproject.toml", "apps/web/package.json"])
        if story_id == "S0-003":
            return ([".env.example", "scripts/seed_agent_marketplace.py"], ["apps/api/alembic.ini", "apps/web/.env.local.example"])
        if story_id == "S0-004":
            return (["tasks/story_status_registry.json", "docs/contracts/README.md"], ["tasks/story_acceptance_reviews.json", "README.md"])
    if epic_slug == "data_foundation":
        if story_id == "S1-001":
            return (["apps/api/alembic/versions/0001_agent_marketplace_baseline.py"], ["apps/api/src/db/models.py", "docs/contracts/data-model.md"])
        if story_id == "S1-002":
            return (["apps/api/src/schemas/common.py", "apps/api/src/schemas/catalog.py"], ["docs/contracts/api/catalog-api.md", "docs/contracts/api/admin-api.md"])
        if story_id == "S1-003":
            return (["apps/api/src/modules/admin/session.py"], ["apps/api/src/routes/admin.py", "apps/web/src/lib/admin-session.ts"])
        if story_id == "S1-004":
            return (["scripts/seed_agent_marketplace.py", "docs/contracts/taxonomy.md"], ["apps/api/src/modules/catalog/taxonomy.py"])
    if epic_slug == "catalog_discovery":
        if story_id == "S2-001":
            return (["apps/api/src/routes/catalog.py"], ["apps/api/src/modules/catalog/service.py", "apps/api/src/modules/catalog/repository.py"])
        if story_id == "S2-002":
            return (["apps/api/src/modules/catalog/taxonomy.py"], ["apps/api/src/routes/catalog.py", "docs/contracts/api/taxonomy-api.md"])
        if story_id == "S2-003":
            return (["apps/web/src/app/page.tsx"], ["apps/web/src/components/home/hero.tsx", "apps/web/src/components/agent/agent-card.tsx"])
        if story_id == "S2-004":
            return (["apps/web/src/app/agents/page.tsx"], ["apps/web/src/components/agent/filter-sidebar.tsx", "apps/web/src/components/agent/agent-list.tsx"])
    if epic_slug == "detail_and_evaluation":
        if story_id == "S3-001":
            return (["apps/api/src/routes/agents.py"], ["apps/api/src/modules/agents/detail_service.py", "apps/api/src/modules/agents/similar_service.py"])
        if story_id == "S3-002":
            return (["apps/api/src/modules/evaluations/service.py"], ["apps/api/src/db/models.py", "docs/contracts/evaluation-model.md"])
        if story_id == "S3-003":
            return (["apps/web/src/app/agents/[slug]/page.tsx"], ["apps/web/src/components/agent/detail-sections.tsx", "apps/web/src/components/agent/evaluation-panel.tsx"])
        if story_id == "S3-004":
            return (["apps/api/src/routes/analytics.py"], ["apps/web/src/components/agent/similar-agent-strip.tsx", "apps/web/src/lib/analytics.ts"])
    if epic_slug == "content_surfaces":
        if story_id == "S3-005":
            return (["apps/api/src/routes/content.py"], ["apps/api/src/modules/content/service.py", "docs/contracts/content-post.md"])
        if story_id == "S3-006":
            return (["apps/web/src/app/content/[slug]/page.tsx"], ["apps/web/src/lib/seo.ts", "apps/web/src/components/content/content-renderer.tsx"])
    if epic_slug == "request_leads":
        if story_id == "S4-001":
            return (["apps/api/src/routes/request_leads.py"], ["apps/api/src/modules/leads/service.py", "docs/contracts/request-lead.md"])
        if story_id == "S4-002":
            return (["apps/web/src/app/request/page.tsx"], ["apps/web/src/components/request/request-form.tsx"])
        if story_id == "S4-003":
            return (["apps/api/src/modules/leads/admin_service.py"], ["apps/web/src/app/admin/request-leads/page.tsx", "apps/api/src/routes/admin.py"])
    if epic_slug == "admin_cms":
        if story_id == "S4-004":
            return (["apps/web/src/app/admin/agents/page.tsx"], ["apps/api/src/routes/admin.py", "apps/web/src/components/admin/agent-editor.tsx"])
        if story_id == "S4-005":
            return (["apps/web/src/app/admin/content/page.tsx"], ["apps/web/src/app/admin/evaluations/page.tsx", "apps/web/src/app/admin/taxonomy/page.tsx"])
        if story_id == "S4-006":
            return (["apps/api/src/modules/publishing/visibility.py"], ["apps/api/src/routes/admin.py", "apps/web/src/middleware.ts"])
    if epic_slug == "quality_and_seed_data":
        if story_id == "S5-001":
            return (["apps/api/tests/test_catalog_api.py", "apps/web/tests/homepage.test.tsx"], ["apps/web/tests/request-page.test.tsx", "apps/api/tests/test_admin_session.py"])
        if story_id == "S5-002":
            return (["scripts/seed_agent_marketplace.py", "apps/api/src/data/seed_agents.json"], ["apps/api/src/data/seed_content.json", "apps/api/src/data/seed_taxonomy.json"])
        if story_id == "S5-003":
            return (["README.md", "docs/contracts/runbook.md"], ["scripts/start_local.ps1", "tasks/backlog_v1/sprint_overview.md"])
    return ([f"{CONTRACTS_DIR}/{title_slug}.md"], [f"{CONTRACTS_DIR}/examples/{title_slug}.example.json"])


def _infer_paths(story_id: str, title: str, epic_slug: str) -> tuple[list[str], list[str]]:
    lowered = title.lower()
    agent_marketplace_epics = {
        "repo_contracts",
        "data_foundation",
        "catalog_discovery",
        "detail_and_evaluation",
        "content_surfaces",
        "request_leads",
        "admin_cms",
        "quality_and_seed_data",
    }
    if epic_slug in agent_marketplace_epics:
        return _infer_agent_marketplace_paths(story_id, title, epic_slug)
    if story_id.startswith("S0-00"):
        primary = [f"{CONTRACTS_DIR}/{_slugify(title)}.md" if "schema" not in lowered else f"{CONTRACTS_DIR}/{_slugify(title)}.schema.json"]
        secondary = [f"{CONTRACTS_DIR}/examples/{_slugify(title)}.example.json"] if "schema" in lowered else []
        if story_id == "S0-005":
            primary = ["scripts/init_schema.sql"]
            secondary = [f"{CONTRACTS_DIR}/trading_agent_profile.schema.json"]
        elif story_id == "S0-006":
            primary = [f"{API_DIR}/modules/statements/storage.py", f"{API_DIR}/modules/statements/repository.py"]
            secondary = ["scripts/init_schema.sql"]
        elif story_id == "S0-007":
            primary = [f"{API_DIR}/modules/audit/service.py", f"{API_DIR}/modules/idempotency/service.py"]
            secondary = ["scripts/init_schema.sql"]
        return (primary, secondary)
    if epic_slug == "statement_ingestion":
        return ([f"{API_DIR}/routes/statements.py"], [f"{API_DIR}/modules/statements/{_slugify(title)}.py"])
    if epic_slug == "statement_parsing":
        return ([f"{API_DIR}/modules/statements/{_slugify(title)}.py"], [f"{API_DIR}/modules/statements/mappers/__init__.py"])
    if epic_slug == "agent_profile":
        return ([f"{API_DIR}/modules/profile/{_slugify(title)}.py"], [f"{CONTRACTS_DIR}/trading_agent_profile.schema.json"])
    if epic_slug == "market_calendar_data":
        return ([f"{API_DIR}/modules/world/{_slugify(title)}.py"], [f"{API_DIR}/modules/world/service.py"])
    if epic_slug == "action_validation_risk":
        return ([f"{API_DIR}/modules/orders/{_slugify(title)}.py"], [f"{CONTRACTS_DIR}/agent_contract_schema.json"])
    if epic_slug == "matching_and_ledger":
        return ([f"{API_DIR}/modules/matching/{_slugify(title)}.py"], [f"{API_DIR}/modules/orders/service.py"])
    if epic_slug == "daily_loop":
        return ([f"{API_DIR}/modules/loop/{_slugify(title)}.py"], [f"{API_DIR}/modules/world/service.py"])
    if epic_slug == "dashboard_read_api":
        return ([f"{API_DIR}/routes/{_slugify(title)}.py"], [f"{API_DIR}/modules/dashboard/service.py"])
    if epic_slug == "readonly_frontend":
        return ([f"{WEB_DIR}/app/(dashboard)/agents/[agentId]/page.tsx"], [f"{WEB_DIR}/features/agent-observation/AgentObservation.tsx"])
    if epic_slug == "openclaw_adapter":
        return ([f"{API_DIR}/routes/openclaw.py"], [f"{CONTRACTS_DIR}/agent_submit_actions.schema.json"])
    if epic_slug == "seed_population":
        return ([f"{API_DIR}/modules/agents/bootstrap.py"], [f"{CONTRACTS_DIR}/trading_agent_profile.schema.json"])
    if epic_slug == "gallery_discovery":
        return ([f"{API_DIR}/modules/gallery/{_slugify(title)}.py"], [f"{WEB_DIR}/app/gallery/page.tsx"])
    if epic_slug == "compare_rankings":
        return ([f"{API_DIR}/modules/leaderboard/{_slugify(title)}.py"], [f"{WEB_DIR}/app/gallery/compare/page.tsx"])
    if epic_slug == "lifecycle_operations":
        return ([f"{API_DIR}/modules/runtime/{_slugify(title)}.py"], [f"{API_DIR}/modules/loop/service.py"])
    return ([f"{WEB_DIR}/app/(dashboard)/onboarding/page.tsx"], [])


def _infer_blast_radius(story_id: str, title: str) -> tuple[str, str]:
    lowered = title.lower()
    if story_id.startswith("S0-") or "文档" in title or "schema" in lowered or "规范" in title:
        return ("L1", "Safe")
    if any(keyword in lowered for keyword in ["api", "daily", "matching", "portfolio", "profile", "validation", "engine", "scheduler", "gallery", "leaderboard"]):
        return ("L2", "Safe")
    return ("L1", "Fast")


def _default_acceptance(task_name: str) -> list[str]:
    return [
        f"{task_name} 的核心输出可以被独立验收。",
        "只跨一个业务边界，不扩展到相邻模块。",
        "产物能够被后续 Story 直接复用。",
        "正常路径和关键失败路径都有可验证结果。",
    ]


def _default_story_inputs(task_name: str, primary_files: list[str], previous_story_id: str | None) -> list[str]:
    inputs = [f"Upstream context for {task_name} is ready to consume."]
    if previous_story_id:
        inputs.append(f"Outputs from dependency story {previous_story_id} are available.")
    if primary_files:
        inputs.append(f"Current in-scope implementation: {', '.join(primary_files[:3])}")
    return inputs


def _default_story_process(task_name: str, primary_files: list[str]) -> list[str]:
    scoped_files = ", ".join(primary_files[:3]) if primary_files else "the declared primary files"
    return [
        f"Inspect {scoped_files} and understand the current implementation for {task_name}.",
        f"Implement only the logic required to make {task_name} independently executable.",
        "Run story-specific checks and archive acceptance evidence for final review.",
    ]


def _default_story_outputs(task_name: str, primary_files: list[str]) -> list[str]:
    outputs = [f"A reusable output for {task_name} is produced and ready for downstream stories."]
    if primary_files:
        outputs.append(f"Updated scope files: {', '.join(primary_files[:3])}")
    outputs.append("Delivery evidence is archived for acceptance and replay.")
    return outputs


def _default_verification_basis(task_name: str) -> list[str]:
    return [
        f"Review the story acceptance criteria for {task_name}.",
        "Confirm the story-specific validation passes.",
        "Confirm the delivery report contains explicit evidence for the outcome.",
    ]


def _default_constraints(primary_files: list[str]) -> list[str]:
    joined = ", ".join(primary_files[:3])
    return [
        "每个 Story 默认控制在 0.5 天到 1 天完成。",
        "只修改当前 Story 相关文件，不跨多个大模块。",
        f"优先修改这些 primary files: {joined}" if joined else "优先修改 Story 指定的 primary files。",
    ]


def _default_out_of_scope(task_name: str) -> list[str]:
    return [f"不在本 Story 中实现 {task_name} 之外的后续能力。", "不做架构级重构。"]


def _default_tests(task_name: str) -> dict[str, list[str]]:
    return {
        "normal": [f"正常路径：{task_name} 的核心场景可以完成。"],
        "exception": [f"异常路径：{task_name} 失败时返回可解释结果。"],
    }


def _build_story(
    story_id: str,
    task_name: str,
    goal: str,
    sprint_number: int,
    epic_title: str,
    epic_slug: str,
    previous_story_id: str | None,
) -> dict[str, Any]:
    primary_files, secondary_files = _infer_paths(story_id, task_name, epic_slug)
    blast_radius, execution_mode = _infer_blast_radius(story_id, task_name)
    dependencies = ["无"] if previous_story_id is None else [previous_story_id]
    return {
        "task_id": story_id,
        "task_name": task_name,
        "sprint": f"Sprint {sprint_number}",
        "epic": epic_title,
        "story_id": story_id,
        "blast_radius": blast_radius,
        "execution_mode": execution_mode,
        "mode": execution_mode,
        "goal": goal,
        "business_value": f"让 {task_name} 成为可独立验收、可直接进入 Agent 执行闭环的 Story。",
        "entry_criteria": ["前置依赖已完成并可用。"] if previous_story_id else ["无前置依赖。"],
        "acceptance_criteria": _default_acceptance(task_name),
        "constraints": _default_constraints(primary_files),
        "out_of_scope": _default_out_of_scope(task_name),
        "not_do": _default_out_of_scope(task_name),
        "dependencies": dependencies,
        "related_files": list(dict.fromkeys(primary_files + secondary_files)),
        "primary_files": primary_files,
        "secondary_files": secondary_files,
        "story_inputs": _default_story_inputs(task_name, primary_files, previous_story_id),
        "story_process": _default_story_process(task_name, primary_files),
        "story_outputs": _default_story_outputs(task_name, primary_files),
        "verification_basis": _default_verification_basis(task_name),
        "test_cases": _default_tests(task_name),
    }


def _ensure_story_contract(story: dict[str, Any]) -> dict[str, Any]:
    payload = dict(story)
    task_name = str(payload.get("task_name") or payload.get("goal") or "this story")
    primary_files = [str(item) for item in payload.get("primary_files", []) if str(item).strip()]
    dependencies = [str(item) for item in payload.get("dependencies", []) if str(item).strip()]
    previous_story_id = next((item for item in dependencies if item.lower() not in {"none", "n/a", "无"}), None)
    payload.setdefault("story_inputs", _default_story_inputs(task_name, primary_files, previous_story_id))
    payload.setdefault("story_process", _default_story_process(task_name, primary_files))
    payload.setdefault("story_outputs", _default_story_outputs(task_name, primary_files))
    payload.setdefault("verification_basis", _default_verification_basis(task_name))
    return payload


class RequirementsAnalystAgent:
    """Planning-layer agent that turns a large requirement into formal backlog artifacts."""

    def __init__(self, repo_b_path: str | Path, tasks_root: str | Path):
        self.repo_b_path = Path(repo_b_path).resolve()
        self.tasks_root = Path(tasks_root).resolve()

    def analyze(self, requirement: str, sprint: str = "1", prefix: str = "backlog_v1") -> dict[str, Any]:
        requirement = requirement.strip()
        if not requirement:
            raise ValueError("requirement must not be empty")
        llm_backlog = self._maybe_generate_backlog_with_llm(requirement)
        if llm_backlog:
            return self._materialize_llm_backlog(llm_backlog, prefix)
        if _looks_like_agent_marketplace(requirement, self.repo_b_path.name):
            return self._materialize_agent_marketplace_backlog(prefix)
        if _looks_like_finance_world(requirement):
            return self._materialize_finance_backlog(prefix)
        return self._materialize_generic_backlog(requirement, str(sprint).strip() or "1", prefix)

    def analyze_file(self, requirement_file_path: str | Path, prefix: str = "backlog_v1") -> dict[str, Any]:
        requirement_path = Path(requirement_file_path).resolve()
        if not requirement_path.exists():
            raise FileNotFoundError(f"Requirement file not found: {requirement_path}")
        return self.analyze(requirement_path.read_text(encoding="utf-8"), prefix=prefix)

    def _materialize_finance_backlog(self, prefix: str) -> dict[str, Any]:
        return self._materialize_blueprint(
            prefix=prefix,
            blueprint=FINANCE_BACKLOG_BLUEPRINT,
            overview_title="# 金融世界 MVP 正式 Backlog v1.0",
            v2_items=V2_BACKLOG,
        )

    def _materialize_agent_marketplace_backlog(self, prefix: str) -> dict[str, Any]:
        return self._materialize_blueprint(
            prefix=prefix,
            blueprint=AGENT_MARKETPLACE_BACKLOG_BLUEPRINT,
            overview_title="# Agent Marketplace Phase 1 Backlog v1.0",
            v2_items=AGENT_MARKETPLACE_V2_BACKLOG,
        )

    def _materialize_blueprint(
        self,
        *,
        prefix: str,
        blueprint: list[dict[str, Any]],
        overview_title: str,
        v2_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        backlog_root = self.tasks_root / prefix
        backlog_root.mkdir(parents=True, exist_ok=True)
        _write_text(backlog_root / "sprint_overview.md", self._build_generic_overview_md(blueprint, overview_title))
        _write_text(backlog_root / "backlog_v2.md", self._build_generic_v2_md(v2_items))

        story_cards: list[dict[str, Any]] = []
        sprint_dirs: list[str] = []
        for sprint in blueprint:
            sprint_dir = backlog_root / f"sprint_{sprint['number']}_{sprint['slug']}"
            sprint_dir.mkdir(parents=True, exist_ok=True)
            sprint_dirs.append(str(sprint_dir))
            execution_order: list[str] = []
            _write_text(sprint_dir / "sprint_plan.md", self._build_generic_sprint_plan_md(sprint))
            for epic in sprint["epics"]:
                epic_doc_name = f"epic_{epic['code']}_{epic['slug']}.md"
                epic_dir_name = f"epic_{epic['code']}_{epic['slug']}"
                _write_text(sprint_dir / epic_doc_name, self._build_generic_epic_md(epic))
                epic_dir = sprint_dir / epic_dir_name
                epic_dir.mkdir(parents=True, exist_ok=True)
                previous_story_id: str | None = None
                for story_id, task_name, goal in epic["stories"]:
                    epic_label = f"Epic {str(epic['code']).replace('_', '.')} {epic['title']}"
                    story = _build_story(story_id, task_name, goal, sprint["number"], epic_label, epic["slug"], previous_story_id)
                    _write_yaml(epic_dir / _story_filename(story), story)
                    story_cards.append(story)
                    execution_order.append(story_id)
                    previous_story_id = story_id
            _write_text(sprint_dir / "execution_order.txt", "\n".join(execution_order) + "\n")
        return {
            "backlog_root": str(backlog_root),
            "overview_path": str(backlog_root / "sprint_overview.md"),
            "sprint_dirs": sprint_dirs,
            "story_cards": story_cards,
        }

    def _materialize_generic_backlog(self, requirement: str, sprint_number: str, prefix: str) -> dict[str, Any]:
        backlog_root = self.tasks_root / prefix
        sprint_dir = backlog_root / f"sprint_{sprint_number}_general_planning"
        sprint_dir.mkdir(parents=True, exist_ok=True)
        story = _build_story(
            f"S{sprint_number}-001",
            "首个可执行 Story",
            requirement,
            int(sprint_number),
            "Epic 1 通用规划",
            "general_scope",
            None,
        )
        epic_dir = sprint_dir / f"epic_{sprint_number}_1_general_scope"
        epic_dir.mkdir(parents=True, exist_ok=True)
        _write_text(backlog_root / "sprint_overview.md", "# Generic backlog\n")
        _write_text(sprint_dir / "sprint_plan.md", f"# Sprint {sprint_number}\n\n{requirement}\n")
        _write_text(sprint_dir / "execution_order.txt", f"{story['story_id']}\n")
        _write_text(sprint_dir / f"epic_{sprint_number}_1_general_scope.md", "# Epic 通用规划\n")
        _write_yaml(epic_dir / _story_filename(story), story)
        return {
            "backlog_root": str(backlog_root),
            "overview_path": str(backlog_root / "sprint_overview.md"),
            "sprint_dirs": [str(sprint_dir)],
            "story_cards": [story],
        }

    def _materialize_llm_backlog(self, backlog: dict[str, Any], prefix: str) -> dict[str, Any]:
        backlog_root = self.tasks_root / prefix
        backlog_root.mkdir(parents=True, exist_ok=True)
        _write_text(backlog_root / "sprint_overview.md", backlog.get("overview", "# backlog_v1\n"))
        if backlog.get("v2_backlog_markdown"):
            _write_text(backlog_root / "backlog_v2.md", str(backlog["v2_backlog_markdown"]))

        story_cards: list[dict[str, Any]] = []
        sprint_dirs: list[str] = []
        for sprint in backlog.get("sprints", []):
            sprint_dir = backlog_root / f"sprint_{sprint['number']}_{sprint['slug']}"
            sprint_dir.mkdir(parents=True, exist_ok=True)
            sprint_dirs.append(str(sprint_dir))
            _write_text(sprint_dir / "sprint_plan.md", str(sprint["plan_markdown"]))
            _write_text(sprint_dir / "execution_order.txt", "\n".join(sprint["execution_order"]) + "\n")
            for epic in sprint.get("epics", []):
                _write_text(sprint_dir / f"epic_{epic['code']}_{epic['slug']}.md", str(epic["markdown"]))
                epic_dir = sprint_dir / f"epic_{epic['code']}_{epic['slug']}"
                epic_dir.mkdir(parents=True, exist_ok=True)
                for story in epic.get("stories", []):
                    story = _ensure_story_contract(story)
                    _write_yaml(epic_dir / _story_filename(story), story)
                    story_cards.append(story)
        return {
            "backlog_root": str(backlog_root),
            "overview_path": str(backlog_root / "sprint_overview.md"),
            "sprint_dirs": sprint_dirs,
            "story_cards": story_cards,
        }

    def _build_overview_md(self, sprints: list[dict[str, Any]]) -> str:
        lines = [
            "# 金融世界 MVP 正式 Backlog v1.0",
            "",
            "## Sprint 总览",
            "| Sprint | 名称 | Epic数 | Story数 | 核心目标 |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for sprint in sprints:
            story_count = sum(len(epic["stories"]) for epic in sprint["epics"])
            lines.append(f"| Sprint {sprint['number']} | {sprint['name']} | {len(sprint['epics'])} | {story_count} | {sprint['goal']} |")
        return "\n".join(lines) + "\n"

    def _build_sprint_plan_md(self, sprint: dict[str, Any]) -> str:
        lines = [f"# Sprint {sprint['number']} {sprint['name']}", "", "## Sprint目标", sprint["goal"], "", "## 不做什么"]
        lines.extend(f"- [ ] {item}" for item in sprint["out_of_scope"])
        lines.extend(["", "## Epic 总览", "| Epic | Story数 | 核心职责 |", "| :--- | :--- | :--- |"])
        for epic in sprint["epics"]:
            lines.append(f"| {epic['title']} | {len(epic['stories'])} | {epic['description']} |")
        return "\n".join(lines) + "\n"

    def _build_epic_md(self, epic: dict[str, Any]) -> str:
        lines = [f"# Epic {epic['code']} {epic['title']}", "", epic["description"], "", "## Stories", "| Story ID | Story 名称 |", "| :--- | :--- |"]
        for story_id, task_name, _goal in epic["stories"]:
            lines.append(f"| {story_id} | {task_name} |")
        return "\n".join(lines) + "\n"

    def _build_v2_md(self) -> str:
        lines = ["# backlog_v2", "", "> 以下内容不进入当前 MVP 执行范围。", ""]
        for item in V2_BACKLOG:
            lines.extend([f"## {item['name']}", item["description"], ""])
        return "\n".join(lines)

    def _build_generic_overview_md(self, sprints: list[dict[str, Any]], title: str) -> str:
        lines = [
            title,
            "",
            "## Sprint Overview",
            "| Sprint | Name | Epic Count | Story Count | Goal |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for sprint in sprints:
            story_count = sum(len(epic["stories"]) for epic in sprint["epics"])
            lines.append(f"| Sprint {sprint['number']} | {sprint['name']} | {len(sprint['epics'])} | {story_count} | {sprint['goal']} |")
        return "\n".join(lines) + "\n"

    def _build_generic_sprint_plan_md(self, sprint: dict[str, Any]) -> str:
        lines = [f"# Sprint {sprint['number']} {sprint['name']}", "", "## Sprint Goal", sprint["goal"], "", "## Out Of Scope"]
        lines.extend(f"- [ ] {item}" for item in sprint["out_of_scope"])
        lines.extend(["", "## Epic Overview", "| Epic | Story Count | Responsibility |", "| :--- | :--- | :--- |"])
        for epic in sprint["epics"]:
            lines.append(f"| {epic['title']} | {len(epic['stories'])} | {epic['description']} |")
        return "\n".join(lines) + "\n"

    def _build_generic_epic_md(self, epic: dict[str, Any]) -> str:
        lines = [f"# Epic {epic['code']} {epic['title']}", "", epic["description"], "", "## Stories", "| Story ID | Story Name |", "| :--- | :--- |"]
        for story_id, task_name, _goal in epic["stories"]:
            lines.append(f"| {story_id} | {task_name} |")
        return "\n".join(lines) + "\n"

    def _build_generic_v2_md(self, items: list[dict[str, Any]]) -> str:
        lines = ["# backlog_v2", "", "> The items below stay outside the current Phase 1 / MVP execution scope.", ""]
        for item in items:
            lines.extend([f"## {item['name']}", item["description"], ""])
        return "\n".join(lines)

    def _maybe_generate_backlog_with_llm(self, requirement: str) -> dict[str, Any] | None:
        if not os.getenv("OPENAI_API_KEY"):
            return None
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a requirements analyst for an agentic software factory.
Break the requirement into Sprint -> Epic -> Story.
Every story must be 0.5 to 1 day, independently testable, and directly executable by a coding agent.
Return strict JSON with this shape:
{
  "overview": "markdown",
  "v2_backlog_markdown": "markdown",
  "sprints": [
    {
      "number": 0,
      "slug": "contract_foundation",
      "plan_markdown": "...",
      "execution_order": ["S0-001"],
      "epics": [
        {
          "code": "0_1",
          "slug": "platform_contract",
          "markdown": "...",
          "stories": [
            {
              "task_id": "S0-001",
              "task_name": "...",
              "sprint": "Sprint 0",
              "epic": "Epic 0.1 平台契约",
              "story_id": "S0-001",
              "blast_radius": "L1",
              "execution_mode": "Safe",
              "goal": "...",
              "business_value": "...",
              "entry_criteria": ["..."],
              "acceptance_criteria": ["..."],
              "story_inputs": ["..."],
              "story_process": ["..."],
              "story_outputs": ["..."],
              "verification_basis": ["..."],
              "constraints": ["..."],
              "out_of_scope": ["..."],
              "dependencies": ["无"],
              "related_files": ["..."],
              "primary_files": ["..."],
              "secondary_files": ["..."],
              "test_cases": {"normal": ["..."], "exception": ["..."]}
            }
          ]
        }
      ]
    }
  ]
}
Only return JSON.
                    """.strip(),
                ),
                (
                    "user",
                    """
Repository root: {repo_b_path}
Requirement:
{requirement}
                    """.strip(),
                ),
            ]
        )
        try:
            response = (prompt | get_llm()).invoke(
                {
                    "repo_b_path": str(self.repo_b_path),
                    "requirement": requirement,
                }
            )
            text = str(getattr(response, "content", response)).strip()
            return yaml.safe_load(text)
        except Exception:
            return None


def analyze_requirement(
    repo_b_path: str | Path,
    tasks_root: str | Path,
    requirement: str,
    sprint: str = "1",
    prefix: str = "backlog_v1",
) -> dict[str, Any]:
    return RequirementsAnalystAgent(repo_b_path, tasks_root).analyze(requirement, sprint=sprint, prefix=prefix)


def split_requirement_file(
    repo_b_path: str | Path,
    tasks_root: str | Path,
    requirement_file_path: str | Path,
    prefix: str = "backlog_v1",
) -> dict[str, Any]:
    return RequirementsAnalystAgent(repo_b_path, tasks_root).analyze_file(requirement_file_path, prefix=prefix)
