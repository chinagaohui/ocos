# Phase14.2-B2 Relation Extraction — 设计文档 v1.1

**状态**: ✅ DESIGN APPROVED 2026-07-22
**日期**: 2026-07-22
**上游**: Phase14.2-B1 (Evidence Layer ❄️)
**下游**: Phase14.3 Style Knowledge Graph (○)

---

## §0 架构定位

```
Raw Text → Phase14.2-A (Text Observation ❄️)
           ↓
          Phase14.2-B1 (Evidence Generation ❄️)
           ↓
          Phase14.2-B2 (Relation Layer) ← 当前
           ↓
          Phase14.3 (Style Knowledge Graph)
           ↓
          Phase14.4 (Meta Principle)
           ↓
          Phase14.5 (Capability Package)
           ↓
          Phase14.8 (Edit Agent)
           ↓
          OpenTale
```

**核心原则**:
> Relation describes observable *structural* relationships between Evidence.
> Relation does **not** explain *why* they exist.

**B2 不是**:
- ❌ Evidence 理解
- ❌ 知识发现
- ❌ 模式总结
- ❌ 因果推理

**B2 只是**:
- ✅ Evidence 之间的可追溯结构连接层

---

## §1 RelationType 冻结（4 类，不扩展）

```python
class RelationType(Enum):
    RELATED = "related"
    CO_OCCURRENCE = "co_occurrence"
    TEMPORAL_PROXIMITY = "temporal_proximity"
    SAME_SCOPE = "same_scope"
```

### 1.1 RELATED — 一般关联
- 两个 Evidence 出现在同一分析范围内（sentence/paragraph/scene/chapter）
- **禁止 work/corpus 范围 all-pairs**（见 §4 Detector 限制）
- 不表示任何语义关联

### 1.2 CO_OCCURRENCE — 共同出现
- 两个不同 EvidenceType 在同一 location 内共同出现
- 需要 `SourceLocation` 重叠，不依赖章节标签
- 记录 `observation_count` + `sample_size`，不评分

### 1.3 TEMPORAL_PROXIMITY — 时间接近
- 基于 `SourceLocation` 的章节/段落位置关系
- 只记录 `distance` + `unit`，不评估距离产生的影响
- **禁止：** `proximity_strength`, `near_connected`, `distance_significance`

### 1.4 SAME_SCOPE — 共享范围
- EvidenceNode 共享 `SourceLocation.scope` 值
- 纯元数据关系，不涉及内容分析

### 1.5 未来禁止扩展（Phase14.3+ 保留）
```
CAUSE, INFLUENCE, IMPACT, FUNCTION, PURPOSE, ROLE, MEANING
```
以上必须属于 Phase14.3+ 推导层。

---

## §2 EvidenceRelation ABI

```python
@dataclass(frozen=True)
class EvidenceRelation:
    relation_id: UUID
    source_evidence_id: UUID
    target_evidence_id: UUID
    relation_type: RelationType
    scope: SourceLocation
    observation_count: int = 0
    sample_size: int = 0
    extraction_method: str = ""
    extraction_version: str = ""
    created_at: datetime
```

### 2.1 字段说明

| 字段 | 类型 | 约束 |
|------|------|------|
| `relation_id` | UUID | 全局唯一，不可变 |
| `source_evidence_id` | UUID | 必须 ∈ EvidenceStore |
| `target_evidence_id` | UUID | 必须 ∈ EvidenceStore |
| `relation_type` | RelationType | 仅 4 类冻结值 |
| `scope` | SourceLocation | 复用 Phase14.1 合约 |
| `observation_count` | int | 检测到该关系实例数量，**不代表有效性** |
| `sample_size` | int | 参与检测的数据规模，**不代表重要性** |
| `extraction_method` | str | 检测器方法描述 |
| `extraction_version` | str | 版本号，用于追溯 |
| `created_at` | datetime | 关系发现时间戳 |

### 2.2 明确禁止的字段

```python
FORBIDDEN_RELATION_FIELDS = frozenset({
    # 权威/重要性
    "confidence_score", "relation_strength", "importance",
    "weight", "priority", "significance",
    # 因果/解释
    "cause", "impact", "meaning", "function", "purpose", "intent",
    # 质量评价
    "effective", "good_relation", "correct", "reliable",
    # 下游引用
    "capability_reference", "style_change", "pipeline_update",
})
```

---

## §3 FORBIDDEN_RELATION_TYPES（RB2-01 基础）

### 3.1 禁止关系类型名

```python
FORBIDDEN_RELATION_TYPES = frozenset({
    # 因果
    "causes", "caused_by", "results_in", "leads_to", "explains",
    # 评价
    "improves", "reduces", "better_than", "worse_than", "effective_for",
    # 读者/创作
    "reader_response", "style_rule", "recommendation",
    # 解释/原则
    "principle", "meaning", "intent",
    # 伪中性（已进入解释层）
    "correlates_with", "predicts", "depends_on",
    "requires", "enables", "supports",
})
```

### 3.2 禁止词汇扫描（RB2-06 Relation Vocabulary Isolation）

```python
FORBIDDEN_RELATION_VOCABULARY = frozenset({
    # 因果/解释
    "cause", "impact", "meaning", "function", "purpose", "intent",
    "explain", "result", "lead_to", "influence",
    # Phase14.3+ 层引用
    "pattern", "principle", "style", "capability", "rule", "strategy",
    "recommendation", "decision", "suggestion", "advice",
})
```

以上词汇在任何 Relation 字段中均禁止出现（字段名 + 字符串值递归检查）。

---

## §4 Detector 设计

### 4.1 通用限制

- **`maximum_relation_scope`**: 仅允许 `sentence` / `paragraph` / `scene` / `chapter`
- **禁止 work/corpus 级别 all-pairs**: 防止 O(n²) 爆炸
- 每个检测器继承 `RelationExtractor(ABC)`

### 4.2 RelatedDetector

- 输入: `list[EvidenceNode]`
- 输出: `list[EvidenceRelation]`
- 规则: 同一 scope 内（sentence/paragraph/scene/chapter）的 EvidenceNode pairs
- 限制: 排除 **work** 和 **corpus** 范围

### 4.3 CoOccurrenceDetector

- 输入: `list[EvidenceNode]`
- 输出: `list[EvidenceRelation]`
- 规则: 两个不同 `EvidenceType` 在 `SourceLocation` 有重叠
- 限制: 必须验证 `scope_overlap`，不依赖章节标签
- 字段: `observation_count`, `sample_size`（不含评分）

### 4.4 TemporalProximityDetector

- 输入: `list[EvidenceNode]`
- 输出: `list[EvidenceRelation]`
- 规则: 基于 `SourceLocation.chapter` / `paragraph_range` 的差值
- 字段: `distance`（int）, `unit`（"chapter"|"paragraph"|"sentence"）
- **禁止**: `proximity_strength`, `near_connected`, `distance_significance`

### 4.5 SameScopeDetector

- 输入: `list[EvidenceNode]`
- 输出: `list[EvidenceRelation]`
- 规则: 共享 `SourceLocation.scope` 值
- 纯元数据匹配，零语义

---

## §5 RB2 验证规则（7 条）

| ID | 名称 | 检查内容 |
|----|------|----------|
| RB2-01 | Relation Purity | `relation_type` ∈ {4 类冻结值}，字段不含 forbidden 类型名 |
| RB2-02 | Evidence Existence | `source_evidence_id` + `target_evidence_id` 均存在于 EvidenceStore |
| RB2-03 | Symmetry Check | RELATED + CO_OCCURRENCE 必须双向对称已验证 |
| RB2-04 | Deterministic | 同输入+版本+配置→同 hash（外部断言） |
| RB2-05 | Cross Layer Isolation | 禁止引用 CapabilityPackage / EditAction / StyleProfile / ParameterChange |
| RB2-06 | Relation Vocabulary Isolation | 递归扫描禁止词汇（cause/impact/meaning/pattern/principle/style等） |
| RB2-07 | Append Only | 只允许 ADD / LINK / ARCHIVE / INVALIDATE；禁止 DELETE / OVERWRITE / MERGE |

---

## §6 文件清单

| 文件 | 类型 |
|------|------|
| `contracts/evidence_relation.py` | 新增 — ABI + RelationType + FORBIDDEN 集合 |
| `reality/extractors/relation/__init__.py` | 新增 — 包入口 |
| `reality/extractors/relation/relation_extractor.py` | 新增 — ABC |
| `reality/extractors/relation/related_detector.py` | 新增 — RELATED 检测器 |
| `reality/extractors/relation/cooccurrence_detector.py` | 新增 — CO_OCCURRENCE 检测器 |
| `reality/extractors/relation/temporal_proximity_detector.py` | 新增 — TEMPORAL_PROXIMITY 检测器 |
| `reality/extractors/relation/same_scope_detector.py` | 新增 — SAME_SCOPE 检测器 |
| `reality/evidence_validator.py` | 追加 — RB2-01~07 验证逻辑 |
| `tests/relation/test_evidence_relation.py` | 新增 — 合约+ABI（~10） |
| `tests/relation/test_detectors.py` | 新增 — 4 检测器各 4 测试（~16） |
| `tests/relation/test_rbx_validation.py` | 新增 — RB2 验证（~10） |
| `tests/relation/test_determinism.py` | 新增 — 确定性（~2） |
| `tests/relation/test_integration.py` | 新增 — B1→B2 集成（~5） |

**预估测试数**: ~43

---

## §7 开发顺序

```
① contracts/evidence_relation.py       — ABI 冻结
② reality/extractors/relation/          — 包结构 + ABC
③ RelatedDetector
④ CoOccurrenceDetector
⑤ TemporalProximityDetector
⑥ SameScopeDetector
⑦ reality/evidence_validator.py         — RB2-01~07 追加
⑧ 单元测试
⑨ 集成测试
⑩ 回归验证（B1 不受影响）
⑪ 门禁报告 + 正式冻结
```

---

## §8 设计审查签名

| 审查项 | 结论 |
|--------|------|
| B2 架构定位与 Phase14 链一致 | ✅ PASS |
| RelationType 4 类冻结，不扩展 | ✅ PASS |
| EvidenceRelation 无 confidence/importance/weight | ✅ PASS |
| ABI 含 created_at 时间戳 | ✅ PASS |
| Detector 范围限制（max = chapter, no work/corpus all-pairs） | ✅ PASS |
| RB2-01~07 覆盖完整 | ✅ PASS |
| FORBIDDEN_RELATION_TYPES + FORBIDDEN_RELATION_VOCABULARY 对齐 | ✅ PASS |
| 测试策略覆盖合约/检测器/RB2/确定性/集成 | ✅ PASS |

**Design Owner**: laogao **日期**: 2026-07-22
**Reviewer**: laogao **日期**: 2026-07-22

---

✅ **DESIGN APPROVED — 进入 Step 1 实现阶段**

---

*文档版本: v1.1 (修正版)*
*修正内容: 增加 created_at / Detector 范围限制 / RB2-06~07 / 扩展禁止词汇*
