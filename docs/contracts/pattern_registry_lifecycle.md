# Phase14.3 — Pattern Registry Lifecycle Management

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §5.2 Pattern Registry Lifecycle Management

## 1. Purpose

定义 Pattern 在 Registry 中的生命周期——如何存在、变化、归档、失效。只记录状态变化的事实，不决定"应该保留哪个 Pattern"。

## 2. State Machine

### 2.1 完整状态图

```
          ┌───────────┐
          │ validated │  ← 来自 §4 Validation 输出（已通过验证，待 Gate 审批）
          └─────┬─────┘
                │
          ╔═════╧══════╗
          ║  registered ║  ← Gate 审批通过，存入观察档案
          ╚═════╤══════╝
                │
       ┌────────┴────────┐
       │                 │
  ┌────▼────┐      ┌────▼──────┐
  │ archived │      │ invalidated│
  └──────────┘      └───────────┘
```

### 2.2 状态语义（已冻结）

| 状态 | 含义 | 不是 |
|------|------|------|
| validated | 验证已通过——结构在统计意义上存在 | 不是"优秀"，不是"推荐使用" |
| registered | 已存入 Registry 观察档案 | 不是"知识"，不是"写作方法" |
| archived | 历史保存——不再活跃观察 | 不是"淘汰"，不是"无用" |
| invalidated | 当前观察证据不足或反例超过约束 | 不是"错误"，不是"有害" |

### 2.3 转移规则

| 从 | 到 | 触发器 | 说明 |
|---|----|--------|------|
| validated | registered | Governance Gate 审批通过 | 核心转入事件 |
| validated | invalidated | Governance Gate 直接否决 | Gate 判定不通过 |
| registered | archived | Governance Gate 标记归档 | 不再活跃 |
| registered | invalidated | Governance Gate 判定撤回 | 反例超限/样本偏差等 |
| archived | — | terminal | 不回到活跃状态 |
| invalidated | — | terminal | 不回到任何其他状态 |

禁止的转移：

| 禁止转移 | 禁止原因 |
|----------|----------|
| validated → archived | 未经过 registered 直接归档，跳过 Gate |
| archived → registered | 恢复已归档模式到活跃状态，属于 Governance 决策（Phase14.6） |
| invalidated → registered | 恢复已否决模式，属于 Governance 决策 |
| archived → invalidated | archived 已经是 terminal，不再改变语义含义 |
| 跨版本自动恢复 | 版本号上升不代表状态自动恢复 |

## 3. 状态访问权限

### 3.1 按状态的访问权限矩阵

| 操作 | validated | registered | archived | invalidated |
|------|-----------|------------|----------|-------------|
| read (结构描述) | ✅ | ✅ | ✅ | ✅ |
| read (验证证据) | ✅ | ✅ | ✅ | ✅ |
| read (审计历史) | ✅ | ✅ | ✅ | ✅ |
| read (生命周期事件) | ✅ | ✅ | ✅ | ✅ |
| version (升版) | ❌ | ✅ | ❌ | ❌ |
| write (状态变更) | ✅ 仅 Gate | ✅ 仅 Gate | ❌ | ❌ |
| audit (追溯) | ✅ | ✅ | ✅ | ✅ |
| delete (删除记录) | ❌ | ❌ | ❌ | ❌ |

### 3.2 权限设计纪律

- **只读操作**对所有状态开放——即使 invalidated 的记录也必须可读（追溯需要）
- **写操作**仅限于 Governance Gate 触发的状态变更
- **删除操作**绝对禁止——即使 archived/invalidated 的记录也必须保留完整追溯链
- **版本操作**仅对 registered 状态开放——只有活跃档案可以更新版本

## 4. Lifecycle Event Record

每次生命周期事件必须记录以下字段：

### 4.1 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | str (UUID) | 事件唯一标识 |
| pattern_id | str | 所属 Pattern |
| previous_state | str | 变更前的状态 |
| new_state | str | 变更后的状态 |
| timestamp | datetime | 事件发生时间 |
| trigger | str | 触发器标识（如 governance_action_id） |
| governance_reference | str | 关联的 Governance Gate 动作 ID |
| version | str | 变更后的版本号 |

### 4.2 禁止字段

| 字段 | 禁止原因 |
|------|----------|
| "not useful" | 价值评判属于 Cognitive Domain |
| "low quality" | 质量判断不属于 Observation |
| "reason=redundant" | "冗余"是分析结论，不是状态变更事实 |
| "not popular" | 流行度不属于 Observation |
| "improvement_suggestion" | 改进建议超出 Registry 职责 |
| "better_alternative" | 替代推荐超出存储层 |

Lifecycle Event Record 只记录"发生了什么变化"，不记录"为什么这是一个好的/坏的变化"。

原因（Reason）字段是可选的且只允许：

| 允许的理由 | 类型 | 说明 |
|------------|------|------|
| counter_evidence_exceeded | 事实引用 | 反例超过约束 |
| sample_bias_detected | 事实引用 | 样本偏差 |
| data_pollution | 事实引用 | 数据污染 |
| time_drift | 事实引用 | 时间漂移 |
| governance_review | 结构引用 | 审查决策 |
| manual_review | 结构引用 | 人工审查 |

不允许自由文本的"无用"/"不好"类理由。

## 5. Rollback 策略

### 5.1 Rollback 语义

Rollback = 恢复 Registry 状态到历史版本。

不是：

- ❌ 重新验证 Pattern
- ❌ 重新学习结构
- ❌ 优化 Pattern 定义
- ❌ 纠正"错误的" Pattern

### 5.2 允许的 Rollback

| 场景 | 说明 |
|------|------|
| 恢复状态 | 将 pattern 从 archived 恢复到之前的历史状态（在 Governance Gate 批准下） |
| 恢复版本 | 将 feature_structure 等定义恢复到历史版本 |
| 反撤销 | 撤销一次错误的 invalidated |

### 5.3 Rollback 纪律

- Rollback 本身也产生 Lifecycle Event Record
- Rollback 不删除已有的历史记录——只追加新记录
- Rollback 后的版本号 = 被恢复的历史版本号
- 不可对已 rollback 的记录再进行 rollback（防止循环）
- Rollback 必须经过 Governance Gate 审批（不自动进行）

### 5.4 Rollback Event Record

Rollback 事件记录额外包含：

| 字段 | 说明 |
|------|------|
| restored_from_version | 从哪个版本恢复 |
| restored_to_version | 恢复到哪个版本 |
| rollback_governance_id | 批准该回滚的 Governance Gate 动作 ID |

## 6. 与 Phase14.6 Evolution Governance 的边界

### 6.1 §5.2 负责

- 记录状态变化事实
- 维护生命周期的版本历史
- 执行 Rollback 的存储层面操作
- 维护访问权限矩阵

### 6.2 §5.2 不负责

- 决定"应该保留哪个 Pattern"
- 判断"这个 Pattern 是否有用"
- 自动清理 archived/invalidated 的 Pattern
- 提议"将多个相似 Pattern 合并"
- 评估"Pattern 的健康度"

### 6.3 边界图示

```
§5.2 ──记录──→ Lifecycle Event Record
                    ↑
                    │ 状态变更事实
                    │
§5.2 不决策 ←── Phase14.6 Governance
                         ↓
                    Gate 决策：
                    - 是否注册
                    - 是否归档
                    - 是否撤回
                    - 是否回滚
                    - 是否清理
```

## 7. 生命周期数据不可变性

- 已创建的 Lifecycle Event Record **不可修改**
- 已归档/已无效化的 Pattern Record 的 core fields **保持完整**
- 状态只能通过合法转移路径变更
- 所有状态变更必须追溯到一个 Governance Gate 动作

## 8. 与 Query Contract 的关系

§5.2 为 §5.3 Query Contract 提供生命周期语义基础。

查询接口需要知道：
- 当前状态的 Pattern 有哪些
- 某个历史时间点的 Pattern 状态
- 某次状态变更的来龙去脉

但 §5.2 本身不定义查询接口——§5.3 再定义。
