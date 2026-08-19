# Phase14.4.1 — Principle Model Definition

**Status**: ❄️ FROZEN (2026-07-22)
**Phase**: Phase14.4 Meta Principle Formation
**Previous**: §14.4.0 Positioning Review ✅
**Next**: §14.4.2 Pattern→Principle Inference Contract

---

## 1. PrincipleRecord ABI

### 1.1 Core Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `principle_id` | `str` | ✅ | 唯一标识, 格式: `p-{uuid_short}` |
| `mechanism_name` | `str` | ✅ | 机制名称, 中性描述性, e.g. "Constraint Escalation" |
| `mechanism_description` | `str` | ✅ | 机制描述, 说明结构关系和因果逻辑 |
| `abstraction_level` | `Level` | ✅ | 抽象层级 (L1/L2/L3) |
| `status` | `Status` | ✅ | 生命周期状态 |
| `version` | `int` | ✅ | 版本号, 从 1 递增 |

### 1.2 Tracing

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_pattern_ids` | `List[str]` | ✅ | 支撑此 Principle 的 Pattern ID 列表, ≥1 |
| `evidence_chain_ids` | `List[str]` | ✅ | 可追溯的证据链 ID 列表 |
| `relation_source_ids` | `List[str]` | ❌ | 关联的 Relation ID (Phase14.2-B2) |

### 1.3 Scope

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `context_boundary` | `str` | ✅ | 上下文边界, e.g. "zh_novel_fiction_2015_2025" |
| `scope` | `str` | ✅ | 作用域描述, 说明什么条件下此机制成立 |

### 1.4 Lifecycle

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `Status` | ✅ | 当前状态 |
| `created_at` | `datetime` | ✅ | 创建时间 |
| `updated_at` | `datetime` | ✅ | 最后更新时间 |
| `history` | `List[HistoryEntry]` | ❌ | 状态变更历史 |

### 1.5 Evolution

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `derived_from` | `Optional[str]` | ❌ | 派生的上级 Principle ID |
| `version` | `int` | ✅ | 当前版本 |
| `superseded_by` | `Optional[str]` | ❌ | 被哪个 Principle 取代 |

---

## 2. Abstraction Levels

| Level | Name | Description | Source Count | Example |
|-------|------|-------------|-------------|---------|
| L0 | Pattern | 具体结构观察 (Phase14.3) | 1 | Pattern: 主角目标受阻+信息隐藏+时间压力 |
| L1 | Mechanism Candidate | 局部机制假说 | 1-3 个同作品 Pattern | 候选: 该作品内部的约束递进模式 |
| L2 | Principle | 跨作品可迁移机制 | ≥3 个不同作品 Pattern | 原理: Cross-work Constraint Escalation Mechanism |
| L3 | General Principle | 跨类型可迁移机制 | 跨多个类型 Pattern | 通用: Uncertainty-driven Decision Pressure Architecture |

**禁止跳跃**:
- L0 → L2 (单 Pattern 直接声称 Principle)
- L0 → L3 (单 Pattern 直接声称 General Principle)

---

## 3. Principle ↔ Pattern Relationship

### 3.1 Allowed Relations

```
Pattern --supports--> Principle
Pattern --contrasts--> Principle  (反例贡献)
Principle --generalizes--> Principle (抽象层级提升)
Principle --refines--> Principle (细化/修正)
```

### 3.2 Forbidden Relations

```
Pattern --equals--> Principle          ❌ 一个模式不是原则
Pattern --proves--> Principle          ❌ 模式不证明原则
Pattern --recommends--> Principle      ❌ 模式不推荐原则
Principle --validates--> Pattern       ❌ 原则不验证模式
```

**核心原则**: `supports` 是概率性的, 不是确定性的。一个 Principle 是跨样本抽象, 不是单个 Pattern 的等价物。

---

## 4. Principle Status Lifecycle

```
                  ┌──────────────┐
                  │  Candidate   │
                  └──────┬───────┘
                         │
                    ┌────▼───────┐
                    │  Reviewing │
                    └────┬───────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌───▼──────┐
         │Validated│ │Archived│ │Invalidated│
         └────┬───┘ └────────┘ └───────────┘
              │
         ┌────▼───────┐
         │Superseded  │
         └────────────┘
```

- **Candidate**: 初始状态, 从 Pattern 提出假说
- **Reviewing**: 正在验证
- **Validated**: 通过验证
- **Archived**: 不再活跃但保留
- **Invalidated**: 被反例推翻
- **Superseded**: 被更高版本/更精确的 Principle 取代

---

## 5. Forbidden Properties

以下属性**永久禁止**出现在 PrincipleRecord 中:

### 5.1 Value Judgments

| Property | Reason |
|----------|--------|
| `quality_score` | 质量评估属于 Validation/Governance |
| `effectiveness` | 有效性属于 Capability 层 |
| `success_rate` | 成功率是商业指标 |
| `usage_priority` | 使用优先级属于 Recommendation |

### 5.2 Commercial / Popularity

| Property | Reason |
|----------|--------|
| `reader_score` | ReaderOS 边界隔离 |
| `market_data` | 市场数据不属于认知域 |
| `popularity` | 流行度不是机制属性 |
| `revenue_impact` | 收入影响属于商业层 |

### 5.3 Recommendation / Normative

| Property | Reason |
|----------|--------|
| `recommended` | 推荐属于 Governance |
| `best_for` | "最佳"属于 Capability 路由 |
| `should_use` | "应该使用"是规范决策 |
| `optimal_context` | 最优上下文属于 Capability |

### 5.4 Keyword Forbidden List (Naming & Description)

| Chinese | English | Reason |
|---------|---------|--------|
| 最好 | best | 价值判断 |
| 更有效 | more effective | 效果评价 |
| 强大 | powerful | 非结构性 |
| 推荐 | recommended | 规范判断 |
| 最优 | optimal | 能力层属性 |
| 读者喜欢 | reader favorite | 读者评价 |
| 爆款必用 | viral essential | 商业趋势 |

---

## 6. Phase14.4 ↔ Phase14.5 Interface

### 6.1 Phase14.4 Output

```
Validated Principle
  ↓
Phase14.5 Input
```

### 6.2 Interface Contract

```python
@dataclass
class Phase14Dot4Output:
    """Phase14.4 提交给 Phase14.5 的输出."""
    principles: List[PrincipleRecord]  # 只包含 validated 状态的
    # 不包含:
    # - capabilities
    # - usage instructions
    # - generation strategies
    # - quality rankings
```

### 6.3 What Phase14.4 Does NOT Produce

```
❌ Writing Agent
❌ Prompt / Instruction
❌ Writing Template
❌ Generation Strategy
❌ Modification Suggestion
❌ Style Transfer Config
❌ Text Generation Parameters
```

这些全部保留给 Phase14.5。

---

## 7. Validation Rules (Forbidden Attributes in PrincipleRecord)

```python
FORBIDDEN_ATTRIBUTES = {
    "quality_score", "effectiveness", "success_rate",
    "reader_score", "market_data", "popularity",
    "revenue_impact", "usage_priority",
    "recommended", "best_for", "should_use",
    "optimal_context", "author_preference",
}
```

任何 PrincipleRecord 实例**不得**包含上述属性。

---

## 8. Conftest Guard

```python
# conftest.py — 全局守卫
def pytest_configure(config):
    """Phase14.4.1 保护: 禁止 PrincipleRecord 包含 forbidden attributes."""
    from principle.models import PrincipleRecord

    for attr in FORBIDDEN_ATTRIBUTES:
        assert not hasattr(PrincipleRecord, attr), (
            f"FORBIDDEN ATTRIBUTE: PrincipleRecord must not have '{attr}'"
        )
```

---

**Document Author**: Hermes Agent (Phase14.4.0 → Phase14.4.1 transition)
**Freeze Date**: 2026-07-22
**Next Document Phase**: §14.4.2 Pattern→Principle Inference Contract
