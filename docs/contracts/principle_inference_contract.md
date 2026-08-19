# Phase14.4.2 — Pattern→Principle Inference Contract

**Status**: ❄️ FROZEN (2026-07-22)
**Phase**: Phase14.4 Meta Principle Formation
**Previous**: §14.4.1 Principle Model Definition ✅
**Next**: §14.4.3 Evidence Chain / Explanation ABI

---

## 0. Positioning — Inference Phase

Phase14.4.2 回答的核心问题：

> 一个 Pattern Set 如何被允许提升为 Mechanism Candidate / Principle Proposal？

**不是**实现推理算法，而是**冻结推导边界、输入输出接口和约束条件**。

---

## 1. Input Boundary

### 1.1 Allowed Inputs

| Source | Type | Description |
|--------|------|-------------|
| Pattern Registry | `PatternReference[]` | Phase14.3 已注册的 Pattern（含 feature_structure, context_boundary, occurrence） |
| Evidence Chain | `EvidenceRecord[]` | Phase14.1 的证据链（含 source_text, analysis, confidence） |
| Relation Graph | `RelationRecord[]` | Phase14.2-B2 的 Relation（含 type, pattern_a, pattern_b, strength） |

### 1.2 Forbidden Inputs

| Source | Reason |
|--------|--------|
| ReaderOS Score | 读者评分 → 价值判断，不属于 Pattern→Principle 推导 |
| Commercial Data | 市场数据 → 商业层，不进入认知域 |
| Human Preference | 人工偏好 → 不用于机制发现 |
| Genre Success | 类型成功率 → 商业指标 |
| Author Reputation | 作者声誉 → 不相关 |
| Popularity Rank | 热度排名 → 非结构信息 |
| Revenue / Sales | 收入数据 → 商业层 |
| Editor Review | 编辑评审 → 非观察数据 |

**核心纪律**：推导只能基于**观察层面的结构信息**，不能基于**价值层面的判断信息**。

---

## 2. Derivation Relationship

### 2.1 Allowed Derivation Path

```
Pattern Set (≥1 patterns, ≥1 evidence chains)
     │
     ├── supports ──► Mechanism Candidate (L1)
     ├── contrasts ─► Mechanism Candidate (L1)  [反例路径]
     │
     ▼
Principle Proposal (L2 / L3)  [需要更多跨作品 pattern]
```

### 2.2 Derivation Types (Allowed)

| Type | Description | Example |
|------|-------------|---------|
| `similar_structure` | 不同作品中出现结构相似的模式 | Pattern A(甲作品) + Pattern B(乙作品) → 共同结构抽象 |
| `recurring_relation` | Relation 多次出现于同类型结构 | Relation(信息隐藏→认知期待) 在多组 Pattern 中一致 |
| `cross_context_appearance` | 同一结构在不同上下文中出现 | Pattern 在都市/玄幻类型中都出现 |
| `structural_abstraction` | 从具体特征提取抽象关系 | "主角隐藏信息+对手施压" → "信息不对称下的决策压力" |

### 2.3 Forbidden Derivation

```
Single Pattern ──► Principle          ❌ 跳跃禁止
Pattern Set ──► "good principle"      ❌ 价值判定禁止
Pattern Set ──► "effective method"    ❌ 有效性禁止
Pattern Set ──► "readers love this"   ❌ 读者偏好禁止
Single Pattern ──► General Principle  ❌ 双重跳跃
```

---

## 3. Output Contract

### 3.1 Output Type: PrincipleCandidate

`PrincipleCandidate` 是推导阶段的唯一输出。它**不是** Validated Principle。

```python
@dataclass
class PrincipleCandidate:
    """推导阶段的输出 — 尚未验证."""
    candidate_id: str                  # 格式: pc-{uuid_short}
    mechanism_name: str                # 建议的机制名称
    mechanism_description: str         # 建议的机制描述
    abstraction_level: AbstractionLevel  # L1 / L2 / L3
    source_pattern_ids: List[str]      # 支撑的 Pattern IDs
    source_evidence_ids: List[str]     # 支撑的证据链 IDs
    derivation_type: DerivationType    # 推导类型
    derivation_path: str               # 自然语言描述推导路径
    context_boundary: str              # 建议上下文边界
    created_at: datetime
    # 以下字段 NOT YET VALIDATED (属于 Phase14.4.4)
    # status = NOT_YET_VALIDATED (implicit)
```

### 3.2 PrincipleCandidate Forbidden Fields

```python
FORBIDDEN_CANDIDATE_FIELDS = {
    "quality_score",
    "effectiveness",
    "success_probability",
    "reader_approval",
    "market_fit",
    "genre_trend",
    "recommendation_strength",
}
```

### 3.3 What PrincipleCandidate Does NOT Become

```
PrincipleCandidate ──► Direct Registration         ❌ (需先验证)
PrincipleCandidate ──► Phase14.5 Capability Input    ❌ (需先验证)
PrincipleCandidate ──► Writing Template              ❌ (永久禁止)
PrincipleCandidate ──► Author Advice                 ❌ (永久禁止)
```

---

## 4. Audit Chain

### 4.1 Every Candidate must trace to evidence

```
PrincipleCandidate
  ├── source_pattern_ids ──► Pattern Registry (Phase14.3)
  │                            └── evidence_chain_ids ──► Evidence Chain (Phase14.1)
  └── source_evidence_ids ───► Evidence Chain (Phase14.1)
```

**规则**: 每个 PrincipleCandidate 必须同时引用至少 1 个 Pattern 和 1 个 Evidence Chain。

### 4.2 Forbidden audit states

```
PrincipleCandidate with 0 patterns     ❌ 无 Pattern 支撑
PrincipleCandidate with 0 evidence     ❌ 无证据链溯源
PrincipleCandidate with derivation_path = ""  ❌ 无推导路径记录
PrincipleCandidate with fake source IDs      ❌ 不可解析的引用
```

### 4.3 Derivation path must be human-readable

derivation_path 字段必须包含自然语言描述，说明**为什么**这个 Pattern Set 被推导为这个候选机制。

示例：
```
Pattern A(甲作品·信息隐藏结构) + Pattern B(乙作品·时间压力结构):
两者共享"受限信息+硬约束"的底层结构，且 Relation Graph 显示
信息不对称→决策压力 的 Relation 在两组 Pattern 中一致。
→ 推导为: 信息受限环境下的决策压力机制 (L2)
```

---

## 5. Derivation Types Enum

```python
class DerivationType(str, Enum):
    SIMILAR_STRUCTURE = "similar_structure"          # 跨作品结构相似
    RECURRING_RELATION = "recurring_relation"        # 反复出现的 Relation
    CROSS_CONTEXT_APPEARANCE = "cross_context_appearance"  # 跨类型出现
    STRUCTURAL_ABSTRACTION = "structural_abstraction"    # 结构抽象
```

### 5.1 Derivation Type Constraints

| Type | Min Patterns | Min Evidence Chains | Cross-work Required |
|------|-------------|-------------------|-------------------|
| `similar_structure` | 2 | 2 | Yes |
| `recurring_relation` | 2 | 2 | Yes |
| `cross_context_appearance` | 3 | 3 | Yes (cross-genre) |
| `structural_abstraction` | 1 | 1 | No (can be single pattern abstraction) |

**说明**: `structural_abstraction` 允许 L0→L1 (同作品内部抽象)，但仍禁止 L0→L2/L3。

---

## 6. Inference Engine Constraints (Not Implemented)

Phase14.4.2 只冻结**接口和约束**，不实现推理算法。

### 6.1 What we freeze now

- [x] Input types and boundaries
- [x] Output type (PrincipleCandidate)
- [x] Derivation types and constraints
- [x] Audit chain requirements
- [x] Forbidden derivation paths

### 6.2 What we defer to implementation

- [ ] Pattern similarity detection algorithm
- [ ] Relation graph traversal
- [ ] Mechanism name generation
- [ ] Derivation path generation
- [ ] Candidate ranking / scoring

---

## 7. Boundary Guards (conftest level)

```python
# conftest guard — Phase14.4.2
def pytest_configure(config):
    """Guard: forbid value-based fields in PrincipleCandidate."""
    for field in FORBIDDEN_CANDIDATE_FIELDS:
        assert field not in PrincipleCandidate.__dataclass_fields__, (
            f"PrincipleCandidate must NOT have field: {field}"
        )
```

---

## 8. Example Flow

```
Input:
  Pattern A: [feature=information_hiding, context=都市职场, occurrence=5]
  Pattern B: [feature=information_hiding+time_pressure, context=玄幻修炼, occurrence=3]
  Evidence E1: [source=text_chunk_42, analysis="主角隐藏关键信息导致对手判断失误"]
  Evidence E2: [source=text_chunk_97, analysis="时间限制下信息差带来的决策压力变化"]

Derivation:
  type = "similar_structure"
  path = "Pattern A 和 Pattern B 共享'信息受限+时间压力'结构，"
         "跨作品出现，涉及不同类型(都市/玄幻)。"
         "Evidence 显示信息不对称→决策压力的因果链。"

Output:
  PrincipleCandidate {
    candidate_id = "pc-a1b2"
    mechanism_name = "Constrained Information Decision Pressure"
    mechanism_description = "在信息受限+时间压力的双重约束下，"
                           "角色决策压力结构性增加"
    abstraction_level = L2_PRINCIPLE
    source_pattern_ids = ["pat-A", "pat-B"]
    source_evidence_ids = ["ev-42", "ev-97"]
    derivation_type = "similar_structure"
    derivation_path = "..."
    context_boundary = "zh_novel_fiction_cross_work"
  }
```

---

**Document Author**: Hermes Agent (Phase14.4.1 → Phase14.4.2 transition)
**Freeze Date**: 2026-07-22
**Next Document Phase**: §14.4.3 Evidence Chain / Explanation ABI
