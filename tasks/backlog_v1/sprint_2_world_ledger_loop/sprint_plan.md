# Sprint 2 世界、撮合、账本、日循环

## Sprint目标
完成世界日历、行情、动作校验、撮合、账本和 Daily Loop。

## 不做什么
- [ ] 不实现 Dashboard 前端
- [ ] 不实现 OpenClaw 对外接入

## Epic 总览
| Epic | Story数 | 核心职责 |
| :--- | :--- | :--- |
| 市场日历与行情 | 4 | 构建交易日历、行情拉取、缓存和版本号。 |
| 动作校验与风控 | 3 | 完成 schema 校验、风控、现金 / 仓位 / lot size 校验。 |
| 撮合与账本 | 6 | 实现收盘价撮合、手续费滑点、fill、portfolio/positions、幂等和对账。 |
| Daily Loop | 4 | 构建 context pack、规则版决策引擎、编排和当日摘要。 |
