# Sprint 1 交割单到 Agent 建模

## Sprint目标
完成交割单上传、解析、标准化、profile 生成和 Agent 创建。

## 不做什么
- [ ] 不实现世界状态与撮合逻辑
- [ ] 不实现前端观察台

## Epic 总览
| Epic | Story数 | 核心职责 |
| :--- | :--- | :--- |
| 交割单摄入 | 4 | 实现上传 API、状态机、文件识别和上传失败路径。 |
| 交割单解析与标准化 | 3 | 把原始交割单映射为标准化 TradeRecord 并输出解析报告。 |
| Agent DNA / Profile | 3 | 从标准化交易记录中提取 profile 并创建 Agent。 |
