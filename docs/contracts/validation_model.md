# Phase14.3 — Validation Model

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §4.1 Validation Model

## 1. Purpose

定义 PatternCandidate 经过统计证据验证后成为 Pattern 的数据契约。

**注意**：

这是数据契约设计。

不是评价模型设计。

不是评分机制。

## 2. Pipeline Position

```
PatternCandidate[]
     │
     ▼
┌─────────────────────────────┐
│    Validation Engine         │
│                              │
│  1. For each Candidate:      │
│  2. Collect ValidationEvidence│
│  3. Check Thresholds         │
│  4. Determine PatternStatus  │
└─────────────────────────────┘
     │
     ▼
Pattern[] (status ∈ {validated, archived, invalidated})
```

## 3. Validation Evidence ABI

ValidationEvidence 记录单次验证操作的完整信息。

```python
@dataclass
class ValidationEvidence:
    """一次验证记录的完整数据契约。"""
    candidate_id: str
    validation_type: ValidationDimension
    observed_count: float
    sample_scope: str
    sample_size: int
    counter_evidence: Optional[CounterEvidence]
    timestamp: str
    validator_version: str

    # ❌ 禁止字段:
    # quality_score: float         — 质量评价, 属于价值判断
    # usefulness: float            — 有用程度, 超出观察层
    # recommendation: str          — 推荐方向, 属于控制层
```

### 字段语义

| 字段 | 类型 | 含义 | 约束 |
|------|------|------|------|
| candidate_id | str | 待验证候选的唯一标识 | 必填, 对应 §1 ABI 的 candidate_id |
| validation_type | ValidationDimension | 本次验证的维度 | 必须是枚举定义值 |
| observed_count | float | 该维度的实际观测值 | 非负, 可以是小数（如稳定性系数）|
| sample_scope | str | 验证覆盖的样本范围描述 | 如 "project:test_project" 或 "all_projects" |
| sample_size | int | 样本数量 | 正整数 |
| counter_evidence | Optional[CounterEvidence] | 反例证据 | 可为 None 表示无反例 |
| timestamp | str | 验证时间 | ISO 8601 格式 |
| validator_version | str | 验证器版本 | 支持审计追溯 |

## 4. Validation Dimension Enumeration

```python
class ValidationDimension(Enum):
    """验证维度的统计语义枚举。

    所有维度必须是纯粹的统计/结构判断。
    禁止包含价值语义。
    """
    FREQUENCY = "frequency"
    STABILITY = "stability"
    RECURRENCE = "recurrence"
    CROSS_CONTEXT = "cross_context_presence"
    COUNTER_EVIDENCE = "counter_evidence"
```

### 维度语义

| 枚举值 | 统计含义 | 典型阈值 | 示例问题 |
|--------|----------|----------|----------|
| FREQUENCY | 结构出现的绝对次数 | minimum_observation_count: 30 | "这个结构在数据集中出现了足够多次吗？" |
| STABILITY | 结构在时间/窗口间的波动幅度 | max_variance: 1.5 | "这个结构每次出现的规模稳定吗？" |
| RECURRENCE | 结构是否在多个独立上下文中重复 | minimum_context_count: 2 | "这个结构在多个故事中都出现了吗？" |
| CROSS_CONTEXT | 结构是否跨越不同类型的上下文 | minimum_context_type_count: 1 | "这个结构在对话和叙述中都存在吗？" |
| COUNTER_EVIDENCE | 反例证据严重程度 | max_counter_ratio: 0.3 | "有多少样本中这个结构不成立？" |

### 非统计维度（禁止出现在枚举中）

以下概念不属于 ValidationDimension：

```
effectiveness       — 有效性（属于原则层）
usefulness          — 实用性（属于能力层）
quality             — 质量评价（需要人类标准）
recommendation      — 推荐方向（属于控制层）
genre_suitability   — 类型适配（属于风格分析）
commercial_value    — 商业价值（不在 OCOS 范围内）
```

## 5. Counter Evidence Data Contract

```python
@dataclass
class CounterEvidence:
    """反例证据数据契约。"""
    evidence_description: str
    count: int
    ratio: float
    sample_scope: str
```

| 字段 | 类型 | 含义 | 约束 |
|------|------|------|------|
| evidence_description | str | 反例的人类可读描述 | 必填, 不可为通用占位符 |
| count | int | 反例出现次数 | 非负整数 |
| ratio | float | 反例在总样本中的占比 | [0.0, 1.0] |
| sample_scope | str | 反例来源范围 | 必填 |

## 6. Threshold Contract

### 设计原则

1. 阈值表示**数据充分程度**, 不是价值程度
2. 阈值是统计含义, 不是质量含义
3. 阈值不做归一化处理, 保留原始单位
4. 阈值不参与加权组合

### 阈值命名规范

正确命名（统计含义）：

```
minimum_observation_count      ✅
minimum_stability_coefficient  ✅
minimum_context_count          ✅
maximum_counter_ratio          ✅
```

错误命名（价值含义）：

```
high_quality_line              ❌
effectiveness_threshold        ❌
reader_appeal_minimum          ❌
good_pattern_cutoff            ❌
```

### 阈值示例

```python
VALIDATION_THRESHOLDS = {
    "frequency": {"minimum_observation_count": 30},
    "stability": {"maximum_variance": 1.5},
    "recurrence": {"minimum_context_count": 2},
    "cross_context": {"minimum_context_type_count": 1},
    "counter_evidence": {"maximum_counter_ratio": 0.3},
}
```

**注意**：具体数值是占位符（placeholder），实际数值由系统部署者根据数据规模设定。冻结的是阈值的设计模式（只能是统计含义的键值对），不是具体数字。

## 7. Status Transition Contract

```
PatternCandidate (status=observed)
     │
     ├── ALL dimensions meet thresholds ────→ Pattern (status=validated)
     │
     ├── Any dimension fails ───────────────→ Pattern (status=archived)
     │
     └── counter_evidence.ratio > threshold ─→ Pattern (status=invalidated)
```

### 转换规则

1. **全部满足 → validated**: 所有允许维度（含 counter_evidence）均满足阈值
2. **任何失败 → archived**: 至少一个维度不满足阈值
3. **反例超标 → invalidated**: counter_evidence.ratio 超过阈值（可以视为 archived 的特例, 但单独标记以便追溯）

## 8. 完整验证流程数据流

```
PatternCandidate
  │ pattern_id, feature_set, relation_structure, frequency,
  │ distribution, stability, counter_evidence, status=observed
  ▼
ValidationEngine
  │
  ├─→ For each dimension in ValidationDimension:
  │     │
  │     ├─→ Read Candidate's evidence for that dimension
  │     ├─→ Look up threshold for that dimension
  │     ├─→ Compare: observed >= threshold? (or <= for counter)
  │     ├─→ Create ValidationEvidence record
  │     └─→ Record met/not_met
  │
  ├─→ Determine overall status
  │     ALL met?     → validated
  │     ANY not_met? → archived
  │     counter fail → invalidated
  │
  └─→ Return Pattern with updated status + validation_evidence
```

## 9. 隔离约束

1. Validation Engine 不读取任何 §4.0 Forbid List 中的信号
2. Validation Evidence 不包含 quality_score / usefulness / recommendation
3. Pattern 输出不属于 Cognitive Domain, 不含写作建议或类型标签
4. Validation 结果不可触发 Phase14.4+ 的任何自动决策

## 10. 确定性契约

相同输入保证相同验证结果：

```python
# 给定:
input_candidate = PatternCandidate(...)
threshold_config = {...}

# 第一次验证:
result_1 = validate(input_candidate, threshold_config)

# 第二次验证（相同输入）:
result_2 = validate(input_candidate, threshold_config)

# 保证:
assert result_1.status == result_2.status
assert result_1.validation_evidence == result_2.validation_evidence
```

验证过程不依赖随机采样、随机种子或外部状态。
