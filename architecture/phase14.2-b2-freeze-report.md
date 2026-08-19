# Phase14.2-B2 — Evidence Relation 冻结报告

**日期**: 2026-07-22
**状态**: ❄️ **FROZEN**

**设计文档**: `architecture/phase14.2-b2-design.md` (✅ APPROVED 2026-07-22)
**冻结链**: Phase14.1 ❄️ → Phase14.2‑A ❄️ → B1‑A ❄️ → B1‑B ❄️ → B1‑C ❄️ (2026‑07‑21) → **B2 ❄️ (2026‑07‑22)**

## 门禁逐项审计

| 门禁 | 状态 | 验证方法 |
|------|------|----------|
| **A. Purpose** — B2 职责边界清晰 | ✅ | 合约 header 明确"Evidence Relation"——仅允许 4 类结构关系（RELATED/CO_OCCURRENCE/TEMPORAL_PROXIMITY/SAME_SCOPE），禁止 22 个因果/评估/伪中性类型 |
| **B. Authority Impact** — 不影响 Phase13 身份模型/P10 语义记忆 | ✅ | Relation 不主动创造 Evidence、不参与排序、不含 confidence/importance/weight 等权威字段 |
| **C. Reality Boundary** — 观测指标冻结 | ✅ | ABI: EvidenceRelation (relation_id, source/target, relation_type, scope, observation_count, sample_size, extraction_method, extraction_version, created_at) ——仅 observation_count + sample_size 纯计数，无推导字段 |
| **D. Drift Test** — 禁止词汇/字段无泄漏 | ✅ | RB2-01~07 + FORBIDDEN_RELATION_TYPE_NAMES(22)+ FORBIDDEN_RELATION_FIELDS(16)+ FORBIDDEN_RELATION_VOCABULARY(16) + FUTURE_RESERVED_RELATION_TYPES(7) |

## 测试矩阵

| 套件 | 通过 | 总数 | 状态 |
|------|------|------|------|
| RelationType 冻结枚举 | 5 | 5 | ✅ |
| FORBIDDEN_RELATION_TYPE_NAMES | 4 | 4 | ✅ |
| FORBIDDEN_RELATION_FIELDS | 3 | 3 | ✅ |
| FORBIDDEN_RELATION_VOCABULARY | 2 | 2 | ✅ |
| MAXIMUM_RELATION_SCOPE | 2 | 2 | ✅ |
| EvidenceRelation 构造 | 8 | 8 | ✅ |
| **合约小计** | **24** | **24** | ✅ |
| RelatedDetector | 7 | 7 | ✅ |
| CoOccurrenceDetector | 7 | 7 | ✅ |
| TemporalProximityDetector | 7 | 7 | ✅ |
| SameScopeDetector | 7 | 7 | ✅ |
| 检测器集成 | 6 | 6 | ✅ |
| **检测器小计** | **34** | **34** | ✅ |
| RB2-01 Relation Purity | 2 | 2 | ✅ |
| RB2-02 Evidence Existence | 5 | 5 | ✅ |
| RB2-03 Symmetry Check | 2 | 2 | ✅ |
| RB2-05 Cross Layer Isolation | 1 | 1 | ✅ |
| RB2-06 Vocabulary Isolation | 1 | 1 | ✅ |
| validate_relations_and_filter | 1 | 1 | ✅ |
| RB2-07 Append Only (checkpoint) | 1 | 1 | ✅ |
| **验证器小计** | **13** | **13** | ✅ |
| **合计** | **71** | **71** | **✅ 100%** |

## ABI 合规验证

- **ABI-T10 (Determinism)**: 同一输入多次提取 → 完全相同输出（检测器需通过 extractor-level determinism，每个检测器均有 `test_deterministic` 测试）
- **RB2-01**: FORBIDDEN_RELATION_TYPE_NAMES (22 个关键词) → 全部被拒绝 ✅
- **RB2-02**: source/target EvidenceNode 不存在 → 被拒绝 ✅；不提供 evidence_nodes → 跳过检查 ✅
- **RB2-03**: 成对关系双向一致（默认关闭，需显式启用 `check_symmetry=True`） ✅
- **RB2-05**: FORBIDDEN_RELATION_FIELDS (16 个) + mutable fields (5 个: confidence_score/relation_strength/importance/weight/priority) → 全部被拒绝 ✅
- **RB2-06**: FORBIDDEN_RELATION_VOCABULARY (16 个: cause/impact/meaning/pattern/style/rule/strategy...) → 全部被拒绝 ✅
- **RB2-07**: Append-Only 约束由 store 层保证，验证器提供检查点标记 ✅
- **Relation 不创造 Evidence**: 设计文档 §2 明确约束，合约中无 create_from_relation 方法 ✅
- **Relation 不参与排序**: EvidenceRelation 不含 order/rank/priority 字段 ✅
- **Scope 限制**: MAXIMUM_RELATION_SCOPE = {sentence, paragraph, scene, chapter}，禁止 work/corpus ✅
- **FUTURE_RESERVED_RELATION_TYPES** (7 个: cause/influence/impact/function/purpose/role/meaning) → 明确声明归 Phase14.3+ 推导层 ✅

## 关键设计决策

1. **对称性检查（RB2-03）默认关闭**：因为在验证器层面无法确定关系集合是否完整。对称性将在 RelationStore 层作为追加约束强制执行。`validate_relations(check_symmetry=True)` 在需要时启用。
2. **RB2-02 跳过条件**：当不提供 `evidence_nodes` 列表时跳过 Existence 检查，允许对关系集合进行独立验证。
3. **FORBIDDEN_RELATION_TYPE_NAMES 扩展**：22 个禁止关系类型名称，分为因果(6)、评价(4)、读者/创作(3)、解释/原则(3)、伪中性(6)五类。
4. **无 observation_count/sample_size 阈值**：计数器仅为纯计数，不暗示有效性或重要性。

## 文件快照

| 文件 | 行数 | 类型 |
|------|------|------|
| `contracts/evidence_relation.py` | 134 | 合约 |
| `reality/extractors/relation/relation_extractor.py` | 55 | ABC |
| `reality/extractors/relation/related_detector.py` | 79 | 检测器 |
| `reality/extractors/relation/cooccurrence_detector.py` | 103 | 检测器 |
| `reality/extractors/relation/temporal_proximity_detector.py` | 99 | 检测器 |
| `reality/extractors/relation/same_scope_detector.py` | 78 | 检测器 |
| `reality/evidence_validator.py` (RB2 块) | ~780 行 delta | 验证器 |
| `tests/relation/test_evidence_relation.py` | 189 | 合约测试 |
| `tests/relation/test_detectors.py` | 322 | 检测器测试 |
| `tests/relation/test_relation_validator.py` | 195 | 验证器测试 |

## 冻结结论

**Phase14.2-B2 Evidence Relation** 所有门禁通过，正式冻结。

- 71/71 测试全部通过
- 4 类冻结关系类型不可扩展（禁止未来直接增加 causal/semantic 类型）
- 22 个禁止关系类型名称、16 个禁止字段、16 个禁止词汇——三重复合隔离
- 7 个未来保留类型声明归 Phase14.3+
- 三原则：Relation 不创造 Evidence、不参与排序、Store 不可变（仅 ADD/LINK/ARCHIVE/INVALIDATE）
- 核心公理成立：**depth of understanding ≠ scope of power**

**下一步入口**: Phase14.3 Style Knowledge Graph — 在 Evidence + Relation 基础上构建知识图谱层。
