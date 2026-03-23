# HandoffPacket 质量标准

## 概述

HandoffPacket 是 agentsystem 中 agent 之间协作的核心机制。每个 agent 完成工作后，必须生成高质量的 HandoffPacket 来传递上下文、成果和风险给下游 agent。

## HandoffPacket 结构

```python
class HandoffPacket(BaseModel):
    packet_id: str                          # UUID
    from_agent: AgentRole                   # 发送方角色
    to_agent: AgentRole                     # 接收方角色
    status: HandoffStatus                   # 状态（pending/completed/blocked）
    what_i_did: str                         # 我做了什么
    what_i_produced: list[Deliverable]      # 我产出了什么
    what_risks_i_found: list[str]           # 我发现了什么风险
    what_i_require_next: str                # 下一步需要什么
    issues: list[Issue]                     # 发现的问题
    trace_id: str                           # 追踪ID
```

## 标准 1: what_i_did 描述格式

### 原则
- **动作导向**：使用过去时动词开头（Executed, Reviewed, Converted, Collected, Traced）
- **具体明确**：说明具体做了什么，不要泛泛而谈
- **范围清晰**：明确工作边界和覆盖范围
- **一句话总结**：控制在 1-2 句话内

### 格式模板

**规划类 Agent**：
```
"Converted [输入] into [输出] with [关键特征]."
```

**执行类 Agent**：
```
"Implemented [范围] and generated [产出]."
```

**验证类 Agent**：
```
"Executed [验证内容] and [验证结果]."
```

**审查类 Agent**：
```
"Reviewed [审查对象] for [审查维度]."
```

**调查类 Agent**：
```
"Traced [问题] through [分析路径] before [下一步行动]."
```

### 优秀示例

✅ **GOOD**:
```python
what_i_did="Converted the UI story into a concrete design contract with a reusable DESIGN.md and preview artifact."
```
- 清晰说明输入（UI story）
- 明确输出（design contract, DESIGN.md, preview artifact）
- 突出价值（concrete, reusable）

✅ **GOOD**:
```python
what_i_did="Traced the bug through evidence, data flow, failed attempts, and root-cause framing before allowing any fix."
```
- 明确调查路径（evidence → data flow → failed attempts → root cause）
- 强调守护原则（before allowing any fix）

✅ **GOOD**:
```python
what_i_did="Collected release scope, validation state, diff discipline, and blockers into a closeout package."
```
- 列举收集内容（4个维度）
- 明确产出形式（closeout package）

### 需要改进的示例

❌ **BAD**:
```python
what_i_did="Did some work on the code."
```
- 太模糊，没有说明具体做了什么

❌ **BAD**:
```python
what_i_did="Fixed bugs and improved quality."
```
- 太泛泛，没有具体范围和方法

## 标准 2: what_risks_i_found 风险识别

### 原则
- **具体可操作**：每个风险都应该是具体的、可验证的
- **优先级排序**：最严重的风险放在前面（最多列出 3-5 个）
- **上下文完整**：说明风险的触发条件和影响范围
- **前瞻性**：不仅指出当前问题，还要预警潜在风险

### 风险分类

**1. 架构风险**：
```python
what_risks_i_found=[
    "The current data flow bypasses the validation layer, allowing invalid state to propagate downstream.",
    "The proposed architecture introduces a circular dependency between modules A and B.",
]
```

**2. 实现风险**：
```python
what_risks_i_found=[
    "The implementation modifies protected paths without explicit approval.",
    "The change introduces breaking API changes that affect 3 downstream consumers.",
]
```

**3. 质量风险**：
```python
what_risks_i_found=[
    "Browser QA health score is 65/100, below the 80 threshold for confident release.",
    "Test coverage dropped from 85% to 72% after the recent changes.",
]
```

**4. 流程风险**：
```python
what_risks_i_found=[
    "Without a design contract, high-risk UI work tends to fall back to generic dashboard patterns.",
    "The first screen should explain the page's product value before dense data blocks begin.",
]
```

**5. 依赖风险**：
```python
what_risks_i_found=[
    "The feature depends on an external API that has no SLA guarantee.",
    "The database migration requires manual intervention in production.",
]
```

### 优秀示例

✅ **GOOD**:
```python
what_risks_i_found=[
    "The working tree is still dirty, so the release evidence is not stable yet.",
    "Browser QA health score is too low for confident release.",
    "Acceptance gate has not passed yet.",
]
```
- 每个风险都具体可验证
- 说明了风险的影响（release evidence not stable, not confident for release）

✅ **GOOD**:
```python
what_risks_i_found=evidence[:4]  # 从调查证据中提取前4个最重要的风险
```
- 基于实际证据
- 限制数量（前4个）

### 需要改进的示例

❌ **BAD**:
```python
what_risks_i_found=["There might be some issues."]
```
- 太模糊，没有具体说明是什么问题

❌ **BAD**:
```python
what_risks_i_found=[]  # 空列表
```
- 没有进行风险识别（除非确实没有风险）

## 标准 3: what_i_require_next 下一步行动

### 原则
- **动作明确**：使用祈使句，明确下一步要做什么
- **条件清晰**：如果有前置条件，明确说明
- **责任明确**：说明谁应该做什么
- **可验证**：下一步行动应该是可验证完成的

### 格式模板

**无条件行动**：
```
"[动词] [对象] [方式/标准]."
```

**条件行动**：
```
"[动词] [对象] [方式/标准], then [后续动作] if [条件]."
```

**守护行动**：
```
"[动词] only [限制条件], then [验证动作]."
```

### 优秀示例

✅ **GOOD**:
```python
what_i_require_next="Implement the target surface against DESIGN.md, then run design-aware QA against the same contract."
```
- 明确实现标准（against DESIGN.md）
- 明确验证方式（design-aware QA against the same contract）

✅ **GOOD**:
```python
what_i_require_next="Fix only inside the root-cause boundary above, then prove the regression is closed with the verification plan."
```
- 明确限制条件（only inside the root-cause boundary）
- 明确验证要求（prove the regression is closed）

✅ **GOOD**:
```python
what_i_require_next="Sync release-facing documentation, then only treat the work as shippable if the blocker list stays empty."
```
- 明确先后顺序（Sync → treat as shippable）
- 明确条件（if the blocker list stays empty）

### 需要改进的示例

❌ **BAD**:
```python
what_i_require_next="Continue working on the task."
```
- 太模糊，没有说明具体要做什么

❌ **BAD**:
```python
what_i_require_next="Fix the issues."
```
- 没有说明如何修复、修复标准是什么

## 标准 4: what_i_produced 产出物

### 原则
- **完整性**：列出所有重要产出物
- **可追溯**：每个产出物都有明确的路径
- **描述清晰**：说明产出物的用途和价值
- **类型明确**：使用标准类型（report, document, html, json, code）

### Deliverable 结构

```python
Deliverable(
    deliverable_id=str(uuid.uuid4()),
    name="产出物名称",                    # 简短名称
    type="report",                        # 类型
    path="相对路径",                      # 文件路径
    description="产出物的用途和价值",      # 详细描述
    created_by=AgentRole.XXX,            # 创建者
)
```

### 优秀示例

✅ **GOOD**:
```python
what_i_produced=[
    Deliverable(
        deliverable_id=str(uuid.uuid4()),
        name="Design Consultation Report",
        type="report",
        path=f".meta/{task_scope_name}/design_consultation/design_consultation_report.md",
        description="Design framing, audience, modules, and visual direction for the target surface.",
        created_by=AgentRole.DESIGN_CONSULTATION,
    ),
    Deliverable(
        deliverable_id=str(uuid.uuid4()),
        name="DESIGN.md",
        type="document",
        path="DESIGN.md",
        description="Executable design contract for downstream frontend implementation and review.",
        created_by=AgentRole.DESIGN_CONSULTATION,
    ),
]
```
- 每个产出物都有清晰的名称、类型、路径、描述
- 描述说明了产出物的用途（for downstream frontend implementation and review）

## 实施检查清单

在生成 HandoffPacket 之前，检查以下项目：

- [ ] `what_i_did` 使用过去时动词开头
- [ ] `what_i_did` 控制在 1-2 句话内
- [ ] `what_i_did` 明确说明输入、输出、关键特征
- [ ] `what_risks_i_found` 列出 3-5 个具体风险
- [ ] `what_risks_i_found` 每个风险都具体可验证
- [ ] `what_risks_i_found` 风险按优先级排序
- [ ] `what_i_require_next` 使用祈使句
- [ ] `what_i_require_next` 明确下一步行动和验证标准
- [ ] `what_i_require_next` 说明条件和限制
- [ ] `what_i_produced` 列出所有重要产出物
- [ ] `what_i_produced` 每个产出物都有完整的 Deliverable 信息
- [ ] `status` 设置为 HandoffStatus.COMPLETED
- [ ] `trace_id` 从 state 中获取

## 参考实现

参考以下高质量 agent 的 HandoffPacket 实现：

1. **design_consultation_agent.py** - 设计评审交接
2. **ship_agent.py** - 发布准备交接
3. **investigate_agent.py** - 调查分析交接
4. **architecture_review_agent.py** - 架构评审交接
5. **office_hours_agent.py** - 产品思维交接
