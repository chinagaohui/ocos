# Phase14.3 — PatternCandidate ABI

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)

## 1. Purpose

PatternCandidate 是 Pattern Discovery 的原始输出。
它代表一个"尚未经过跨样本验证的候选结构"。
比 Pattern 更弱——只有统计观察,没有稳定性验证。

## 2. ABI 定义

```
PatternCandidate:
  candidate_id: str                       # 候选模式唯一标识 (e.g. "PC-00042")
  scope:
    domain: str                           # 适用域 (e.g. "action_scene", "narrative_boundary")
    boundary: str                         # 范围边界 (e.g. "chapter", "scene")
  structure:
    feature_set: list[str]                # 特征集合
    relation_structure: list[dict]        # 关系结构描述 (与 Pattern 格式一致)
  occurrence_stats:
    occurrence_count: int                 # 出现次数 (>= 0)
    frequency: float                      # 频率 [0.0, 1.0]
    sample_size: int                      # 样本总量 (>= occurrence_count)
  provenance:
    source_relation_ids: list[str]        # 来源 EvidenceRelation ID 集合
    mining_algorithm_version: str         # Mining 算法版本
    mined_at: str                         # ISO 8601 时间戳
  lifecycle:
    status: CandidateStatus               # 当前状态
```

## 3. CandidateStatus 枚举

| 值 | 含义 | 可转换至 |
|----|------|----------|
| `candidate` | 原始候选,未经验证 | validated, rejected, archived |
| `validated` | 满足统计验证条件,晋升为 Pattern | archived |
| `rejected` | 未达到统计验证条件 | archived |
| `archived` | 历史保存 | — |

## 4. 与 Pattern 的关系

```
PatternCandidate (未验证)       Pattern (已验证)
─────────────────────────      ────────────────
candidate_id                   pattern_id
仅有 occurrence_stats          有 validation 块 (stability, counter_evidence)
无稳定性指标                    有稳定性指标
source_relation_ids            source_evidence_ids (更宽)
生命周期状态不同                 生命周期状态不同
```

候选→验证 的转换条件由 Validation 标准定义(不在本合约范围内)。

## 5. 禁止字段

```
good              better            best
effective         recommended       preferred
quality_score     reader_rating     commercial_score
importance        priority          principle
capability        style_label       change_proposal
```

## 6. 约束规则

| 规则 | 描述 |
|------|------|
| PC1 | candidate_id 全局唯一 |
| PC2 | frequency ∈ [0.0, 1.0] |
| PC3 | occurrence_count >= 0 |
| PC4 | sample_size >= occurrence_count |
| PC5 | status ∈ {candidate, validated, rejected, archived} |
| PC6 | 禁止字段不得出现在任何层级 |
