# Story Completion Standard

## 目的
把单个 Story 定义为系统中的最小执行与验收单元。任何 Story 只有同时满足开发、测试、审查、验收、报告五个环节，才算真正完成。

## Definition of Done
- 任务卡字段完整，能通过 `TaskCard` schema 校验。
- 变更范围清晰，且只覆盖当前 Story 允许的文件。
- 目标产物已经写入目标仓库，且可被后续 Story 直接复用。
- 项目检查与 Story 专项校验通过。
- Reviewer 无 Blocking 问题。
- Code Acceptance Agent 无风格一致性或文件卫生问题。
- Acceptance Gate 所有验收项通过，且无越界改动。
- Delivery report 已生成并归档。

## Acceptance OK
- 每条 `acceptance_criteria` 都有明确的“已满足”证据。
- 测试报告中没有失败项。
- Review / Code Acceptance / Acceptance Gate 三道关都为通过。
- 交付物、报告、日志均为 UTF-8 可读内容。

## 标准流程
1. Requirement Agent：解析任务卡，收敛目标、范围、约束。
2. Builder Agent：只修改 Story 允许范围内的文件。
3. Test Agent：执行项目检查 + Story 专项校验。
4. Review Agent：审查需求命中、结构、风险。
5. Code Acceptance Agent：审查代码风格一致性与文件质量。
6. Acceptance Gate：对照验收标准和范围做最终硬拦截。
7. Doc Agent：输出标准化交付报告。

## Story 交付报告最少包含
- Story 基本信息
- 验收标准清单
- 测试结果
- 审查结果
- 代码验收结果
- 最终结论
