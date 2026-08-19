# Phase14.3 — Pattern Schema

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Supersedes**: N/A — Phase14.3 §1 Pattern Model Definition

## 1. Purpose

Pattern 是 Evidence Graph 上经过统计验证的结构观察对象。
它描述"什么结构稳定重复出现"，不描述"这个结构有什么意义"。

## 2. Pattern 完整数据模型

```
Pattern:
  pattern_id: str                          # 唯一标识 (e.g. "P-00001")
  scope:
    domain: str                            # 适用域 (e.g. "action_scene", "dialogue_scene")
    boundary: str                          # 范围边界 (e.g. "chapter", "scene", "paragraph")
  structure:
    feature_set: list[str]                 # 特征集合 (e.g. ["sentence_length_decrease", "dialogue_ratio_increase"])
    relation_structure: list[dict]         # 关系结构描述 (e.g. [{type: "CO_OCCURRENCE", between: ["A","B"]}])
  observation:
    occurrence_count: int                  # 出现次数 (>= 0)
    frequency: float                       # 频率 [0.0, 1.0]
    distribution: list[dict]               # 分布详情 (可选, 按 scope 维度)
  validation:
    stability: dict[str, float] | None     # 稳定性指标 (e.g. {"cross_work": 0.68, "cross_chapter": 0.72})
    counter_evidence: float | None         # 反例出现率 [0.0, 1.0]
  provenance:
    source_evidence_ids: list[str]         # 来源 Evidence ID 集合
    extraction_version: str                # Mining 算法版本
  lifecycle:
    status: PatternStatus                  # 当前状态 (见 §3)
```

## 3. PatternStatus 枚举

| 值 | 含义 | 可转换至 |
|----|------|----------|
| `observed` | 经统计验证的稳定结构 | validated, archived, invalidated |
| `validated` | 跨样本/跨作品复现确认 | archived, invalidated |
| `archived` | 历史保存,不再参与当前发现 | invalidated |
| `invalidated` | 新 Evidence 不再支持该模式 | archived |

## 4. 禁止字段

以下字段**不得**出现在 Pattern 模型中：

```
good              better            best
effective         recommended       preferred
style_name        quality_score     reader_rating
commercial_score  importance        priority
principle_id      capability_id     change_proposal
```

## 5. 约束规则

| 规则 | 描述 |
|------|------|
| P1 | pattern_id 全局唯一 |
| P2 | frequency ∈ [0.0, 1.0] |
| P3 | occurrence_count >= 0 |
| P4 | counter_evidence ∈ [0.0, 1.0] (if present) |
| P5 | stability.* ∈ [0.0, 1.0] (if present) |
| P6 | status ∈ {observed, validated, archived, invalidated} |
| P7 | 禁止字段不得出现在任何层级 |

## 6. 与后续阶段的关系

| 阶段 | 如何使用 Pattern |
|------|-----------------|
| Phase14.3 (本层) | 发现、存储、验证 Pattern |
| Phase14.4 | 结合 ReaderOS + 注意力模型 → 解释"可能意味着什么" |
| Phase14.5 | 将解释后的 Principle → Capability |
| Phase15 | Control Plane 使用 Capability 安全影响系统 |

## 7. 设计原则

> Pattern 是被发现的,不是被创造的;是被统计确认的,不是被评价出来的。
