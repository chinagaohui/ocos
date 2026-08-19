# Phase14.3 — Mining Input Snapshot ABI

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §2 Mining Input Contract

## 1. Purpose

Evidence Graph Snapshot 是 Mining Engine 唯一接受的输入格式。

它代表**某一时刻、某一组 Evidence Graph 状态的不可变快照**。
Snapshot 用 UUID 标识身份，用内部 version 字段描述数据来源。

## 2. Snapshot 结构

```
EvidenceGraphSnapshot:
  snapshot_id: str                       # UUID — 唯一身份标识,不可变
  name: str | None                       # 可读名称 (可选,用于调试/日志)
  created_at: str                        # ISO 8601 — Snapshot 创建时间
  scope: str                             # 数据范围 (e.g. "corpus_v2.1", "work_0142")

  # ── 数据体 ──
  nodes: list[EvidenceNode]              # EvidenceNode 集合
  relations: list[EvidenceRelation]      # EvidenceRelation 集合

  # ── 版本追溯 ──
  versions: EvidenceGraphVersions        # 数据来源版本

  # ── 元信息 ──
  metadata: SnapshotMetadata              # 快照元信息
```

## 3. EvidenceGraphVersions

描述 Snapshot 中各层数据的来源版本。
回答：**"这份数据来自哪个生成版本？"**

```
EvidenceGraphVersions:
  evidence_schema_version: str           # Evidence Schema 版本 (e.g. "1.0")
  relation_schema_version: str           # Relation Schema 版本 (e.g. "1.0")
  extractor_version: str                 # Extractor 算法版本 (e.g. "0.3.1")
  relation_version: str                  # Relation Detector 版本 (e.g. "1.2.0")
  snapshot_schema_version: str           # 本 Snapshot 格式版本 (e.g. "1.0")
```

## 4. SnapshotMetadata

```
SnapshotMetadata:
  corpus_size: int                       # 语料总规模 (节点数)
  work_count: int                        # 涉及作品数
  chapter_count: int                     # 涉及章节数
  scene_count: int                       # 涉及场景数
  extraction_date: str                   # ISO 8601 — 数据提取日期
  notes: str | None                      # 附注 (可选)
```

## 5. 约束规则

| 规则 | 描述 |
|------|------|
| SS1 | snapshot_id 必须为合法 UUID 格式 |
| SS2 | snapshot_id 创建后不可变 |
| SS3 | versions 中所有版本字段必须非空 |
| SS4 | scope 必须与内部数据范围一致 |
| SS5 | created_at 必须为 ISO 8601 格式 |
| SS6 | nodes 和 relations 不得同时为空 |
| SS7 | 同一 snapshot_id 永远指向同一份数据 |

## 6. 版本 vs 身份

| 概念 | 用途 | 示例 |
|------|------|------|
| snapshot_id (UUID) | 回答"我分析哪一次数据状态？" | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| evidence_schema_version | 回答"Evidence 数据格式版本" | `"1.0"` |
| relation_schema_version | 回答"Relation 数据格式版本" | `"1.0"` |
| extractor_version | 回答"使用哪个提取器版本" | `"0.3.1"` |

**不要** 用版本号作为 Snapshot 标识——版本计数不唯一，UUID 才是不可变的身份标记。

## 7. 与后续阶段的关系

```
EvidenceGraphSnapshot
  ↓
Mining Engine (§2 → §3)
  ↓
PatternCandidate[]  (以 snapshot_id + config_id 追溯)
  ↓
Validation (§4)
  ↓
Pattern[]
```
