# Phase14.3 — Pattern Validation Positioning

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §4.0 Pattern Validation Positioning Review

## 1. Purpose

确认 Pattern Validation 的定位边界——验证一个 PatternCandidate 在什么条件下可以升级为 Pattern。

验证判断的是：

**统计可靠性**。

不是：

**价值高低**。

## 2. Pipeline Position

```
Evidence Graph
     ↓  §3.2
PatternCandidate[]
     ↓  §4.0
PatternCandidate[] → Validation Evidence → Pattern Status
     ↓  §4.1 (Validation Model)
Pattern[]
     ↓  §5 (Pattern Registry)
```

§4 处于 Observation Domain 的最后一个子阶段。输出仍然是 Observation Domain 的数据（Pattern），不是 Cognitive Domain 的建议或决策。

## 3. Validate / Forbid

### Validation Allow List

Validation 判断的内容：

| 维度 | 含义 | 示例 |
|------|------|------|
| frequency | 结构在数据集中出现的绝对次数 | "出现 47 次" |
| stability | 结构在时间/窗口间的波动幅度 | "每章出现 3-5 次, 标准差 < 0.8" |
| recurrence | 结构是否在多个独立上下文中重复出现 | "同时出现在三个不同故事中" |
| cross-context presence | 结构是否跨越不同类型的上下文 | "出现在对话/叙述两种模式中" |
| counter evidence | 是否存在反例削弱该结构的可靠性 | "在 20% 的样本中未出现" |

### Validation Forbid List

Validation 不判断：

| 维度 | 禁止原因 |
|------|----------|
| effectiveness | 属于 Cognitive Domain（Phase14.4+) |
| usefulness | 依赖于具体使用场景，超出观察层 |
| quality | 需要人类评价标准，超出统计层 |
| recommendation | 属于 Control Domain（Phase15+） |
| commercial_value | 完全不在 Pattern Discovery 职责内 |
| reader_appeal | 需要读者反馈信号（Phase14.4+） |
| author_skill | 属于认知评价，不是结构观察 |
| success_probability | 预测行为不在观察域内 |
| genre_suitability | 类型适配是风格分析层职责 |
| better_than_others | 比较式判断超出统计可靠性范围 |

## 4. 不是评分系统

这是一个关键设计约束：

**Pattern Validation 不是评分系统**。

以下设计被禁止：

```python
# ❌ 禁止：评分式设计
pattern_score = 0.85  # "此模式优秀程度 85%"
if pattern_score > 0.7:
    promote_to_pattern()
```

以下设计被允许：

```python
# ✅ 允许：证据满足/不满足条件
validation_results = {
    "frequency":  {"threshold": 30, "observed": 47, "met": True},
    "stability":  {"threshold": 1.5, "observed": 0.8, "met": True},
    "counter_evidence": {"threshold": 0.3, "observed": 0.2, "met": True},
}
all_met = all(r["met"] for r in validation_results.values())
if all_met:
    promote_to_pattern()
```

### 为什么不是评分系统

1. 评分隐含"更好/更差"的比较——Validation 不做价值比较
2. 评分需要归一化和阈值——这些是 Cognitive Domain 的决策工具
3. 评分系统会诱导上层依赖"模式的分数"而不是"模式的证据链"

## 5. 状态转换契约

Validation 的结果是触发 PatternCandidate 的状态转换：

```
observed → (if validation PASS) → validated
observed → (if validation FAIL) → archived
observed → (if counter_evidence > threshold) → invalidated
```

完整状态转换定义见 §1 Pattern State Machine。

## 6. 与 §3 的边界

| | §3 Mining | §4 Validation |
|--|-----------|---------------|
| 输入 | EvidenceGraphSnapshot | PatternCandidate[] + Evidence Graph |
| 输出 | PatternCandidate[] | Pattern[] |
| 判断内容 | 是否存在统计结构 | 统计结构是否可靠 |
| 是否可以拒绝 | 否（发现所有结构） | 是（确认可靠才升级） |
| 是否使用价值 | 禁止 | 禁止 |
| 确定性 | 相同输入→相同候选 | 相同输入→相同验证结果 |

## 7. Validation 结果不进入 Cognitive Domain

重要隔离：

Validation 的输出（Pattern[]）仍然属于 Observation Domain。

Pattern 本身不包含：

- ❌ 写作建议
- ❌ 质量评级
- ❌ 风格标签
- ❌ 推荐优先级

Pattern 只包含：

- ✅ 结构定义（feature_set + relation_structure）
- ✅ 统计证据（occurrence_stats + validation_evidence）
- ✅ 生命周期状态（status）

Cognitive Domain 对 Pattern 的解读（"这个模式可能意味着什么"）属于 Phase14.4。

## 8. 设计纪律

1. **Validation 不是筛选**——不是挑出一个"最好的"模式
2. **Threshold 是统计阈值**——如 "min_frequency=30"，不是质量阈值
3. **所有维度必须独立判断**——不用加权公式合并不同维度
4. **Counter Evidence 是必检项**——没有反例检查的 Validation 不完整
5. **Validation 结果可审计**——每个验证决策必须追溯到原始统计证据

## 9. 不自动注册原则

Validation 不自动注册 Pattern 到 Pattern Registry。

正确链路：

```text
Validation Engine
     ↓
Validation Evidence + Validation Result
     ↓
Governance / Human Gate
     ↓
Pattern Registry
```

Validation 只回答：

**"这个结构是否满足统计存在条件"**

不回答：

**"这个结构是否值得进入长期知识体系"**

### 为什么需要 Gate

因为后续 Phase14.6 Evolution Governance 需要处理：

-   数据污染（作品级系统误差）
-   单作品偏差（一位作者的独特习惯被误判为通用模式）
-   样本偏差（数据来源不全面）
-   时间漂移（过去成立的模式现在不再成立）
-   错误强化（被验证过的模式自我强化，掩盖反例）

### Validated Pattern ≠ 永久知识

"Validated" 状态的含义是：

**"已通过观察层验证，可以提交到 Pattern Registry 等待审查"**

不是：

**"模式已进入知识库"**

Gate 的责任——自动化的 Governance Gate 或人类审查——属于 Phase14.6 Evolution Governance。
