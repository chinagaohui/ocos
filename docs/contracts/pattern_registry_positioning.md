# Phase14.3 — Pattern Registry Positioning

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §5.0 Pattern Registry Positioning Review

## 1. Purpose

确认 Pattern Registry 在 Observation Domain 中的定位——Registry 是观察事实的长期存储，不是知识库，不是能力库，不提供推荐。

### Registry 是

**观察事实的持久化层**。

### Registry 不是

- ❌ 知识库（那是 Phase14.4 Principle Layer 的输出）
- ❌ 能力库（那是 Phase14.5 Capability Package 的输出）
- ❌ 推荐系统（那是 Control Domain 的行为）
- ❌ 写作技巧大全（不提供"好写法"的定义）

## 2. Pipeline Position

```text
[Phase14.3 Observation Domain]

Evidence Graph
     ↓
PatternCandidate  →  Validation  →  Pattern[]
     ↓  §3.x            ↓  §4.x         ↓  §5
                                 Governance Gate
                                      ↓
                               Pattern Registry
                                      ↓
                              [查询/审计/版本管理]

[Phase14.4 入口]
Pattern Registry → Meta Principle Formation → Principle
```

Registry 是 Observation Domain 的最后一层。所有从 Observation Domain 输出的 Pattern 都要经过 Registry 的承载才能被 Cognitive Domain 读取。

但注意：

**Registry 不提供"解读"**。Cognitive Domain 读取 Registry 中的 Pattern 时，仍然需要自己的理解过程。

## 3. Registry 能力边界

### Allow List

Registry 允许：

| 能力 | 说明 |
|------|------|
| 存储 Validated Pattern | 持久化观察事实 |
| 版本管理 | 记录每次 Pattern 定义的变更 |
| 生命周期状态管理 | validated → active → archived → invalidated |
| 查询 | 按 context / feature / scope 检索 |
| 审计追溯 | 回放验证过程，追溯数据来源 |
| 回滚 | 恢复到历史版本的 Pattern |

### Forbid List

Registry 禁止：

| 能力 | 禁止原因 |
|------|----------|
| 推荐最佳 Pattern | 属于 Control Domain |
| 计算 Pattern 质量评分 | 评分是 Cognitive 行为 |
| 解释 Pattern 意义 | 解释属于 Phase14.4 Principle Formation |
| 合并 Pattern | 合并是认知分析，不是存储行为 |
| 自动清理 Pattern | 清理属于 Governance（Phase14.6） |
| 输出"最有用的"Pattern | 排序推荐超出 Observation 职责 |
| 修改输入的 Pattern 定义 | Registry 是存储，不是数据加工 |
| 跨 Pattern 推理 | "因为 Pattern A 所以 Pattern B" 是认知 |
| 生成写作建议 | 建议属于 Capability/Control Domain |

## 4. Registry 不改变 Pattern 语义

一个 Pattern 进入 Registry 时怎样，从 Registry 读出时也怎样。

Registry 不附加：

- ❌ readability_score
- ❌ usage_count_feedback
- ❌ author_preference
- ❌ quality_rank

Registry 只保持：

- ✅ pattern_id
- ✅ feature_structure
- ✅ relation_structure
- ✅ source_candidates (原始 PatternCandidate 引用)
- ✅ validation_records (验证证据链)
- ✅ context_boundary (该 Pattern 被验证的上下文范围)
- ✅ version
- ✅ status

## 5. Registry 与 Governance Gate 的关系

```
Validation Result
     ↓
Governance Gate          ← Phase14.6 范畴（自动或人工审查）
     ↓  (approve/reject)
Pattern Registry         ← §5.0 范畴（存储已通过的）
```

Governance Gate 决定**是否入库**，Registry 负责**存入后的事**。

Registry 不替代 Gate，也不绕过 Gate。

即使 Gate 审批通过后进入 Registry，Registry 仍保留完整的来源记录，以便 Gate 在需要时撤回。

## 6. Registry 与 Phase14.4 的关系

```
Pattern Registry          ← Observation Domain 输出
     ↓
Phase14.4 Meta Principle   ← Cognitive Domain 入口
     ↓
Principle[]
```

- Phase14.4 从 Registry 读取 Pattern
- Phase14.4 输出的是 Principle，不是 Pattern
- Registry 不负责解释 Pattern
- Phase14.4 不修改 Registry 中的 Pattern（只读引用）

## 7. 谁写 Registry

| 操作 | 允许者 | 说明 |
|------|--------|------|
| write | Governance Gate (Phase14.6) | 审批通过后写入 |
| read | 任何查询者 | 按查询契约读取 |
| update status | Governance Gate | 生命周期状态变更 |
| create version | Governance Gate | 记录每次变更 |
| archive | Governance Gate | 标记为不再活跃 |
| rollback | Governance Gate | 恢复到有效历史版本 |

注意：Validation Engine 不写 Registry（§4.2 已冻结此隔离）。只有 Governance Gate 有权触发写操作。

## 8. 设计纪律

1. **Registry 是存储层，不是分析层**——不加工、不排序、不推荐
2. **Pattern 不可变**——一旦写入，字段不可修改（只可版本化）
3. **版本可回滚**——回滚是 Registry 的责任，不是 Governance 的责任
4. **来源不可丢失**——每个注册的 Pattern 必须追溯到原始 Validation Record
5. **不自动清理**——即使状态为 archived/invalidated，记录不能被删除
6. **只读不解释**——读端获得的是 Pattern 原始数据，不是解读结果