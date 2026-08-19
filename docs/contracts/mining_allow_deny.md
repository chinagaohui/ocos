# Phase14.3 — Mining Allow/Deny Boundary

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §2 Mining Input Contract

## 1. Purpose

定义 Mining Engine 能读取什么、不能读取什么。

采用**白名单优先 + 黑名单二次拦截**的双层隔离设计。

## 2. 安全哲学

```
白名单 (Allow List)     — "默认拒绝,明确开放"
  第一层：只可读取明确列出的字段
  第二层：新增字段默认拒绝

黑名单 (Deny List)      — "确认拦截"
  第一层：强制禁止价值信号类别
  第二层：防止白名单遗漏
```

## 3. Allow List — 可读字段

### 3.1 EvidenceNode 可读字段

| 字段 | 用途 | 约束 |
|------|------|------|
| `node_id` | 节点标识 | 只读 |
| `evidence_type` | 证据类型 | 已在 Phase14.1 冻结 |
| `features` | 特征向量 / 观察值 | 数值或可比较类型 |
| `scope` | 范围信息 (域/边界) | 用于分组统计 |
| `timestamp` | 时间位置 | 用于时序分析 |
| `scene_index` | 场景索引 | 用于分组 |
| `source_ref` | 源引用 | 只读、不用于特征计算 |

### 3.2 EvidenceRelation 可读字段

| 字段 | 用途 | 约束 |
|------|------|------|
| `relation_id` | 关系标识 | 只读 |
| `relation_type` | 关系类型 | 仅限已冻结的四类 |
| `source_node_id` | 源节点 | 用于关联分析 |
| `target_node_id` | 目标节点 | 用于关联分析 |
| `scope` | 范围信息 | 用于分组 |
| `observation_count` | 出现次数 | 整数 |
| `sample_size` | 样本量 | 整数 |

### 3.3 Metadata 可读字段

| 字段 | 用途 |
|------|------|
| `evidence_schema_version` | Schema 版本 (用于兼容性判断) |
| `relation_schema_version` | Schema 版本 |
| `extractor_version` | 提取器版本 |
| `corpus_size` | 语料规模 (用于统计基准) |
| `work_count` | 作品数 |
| `chapter_count` | 章节数 |
| `scene_count` | 场景数 |

### 3.4 MiningConfig 可读字段

| 字段 | 用途 | 约束 |
|------|------|------|
| `scope_filter` | 范围过滤 | 字符串或正则 |
| `relation_type_filter` | 关系类型过滤 | 枚举集合过滤 |
| `frequency_threshold` | 频率阈值 | ∈ [0.0, 1.0] |
| `window_definition` | 窗口定义 | 用于序列/转换模式 |
| `sampling_policy` | 采样策略 | 枚举 |

## 4. Deny List — 禁止字段

### 4.1 绝对禁止类别

| 类别 | 禁止字段示例 | 原因 |
|------|-------------|------|
| **Value Signals** | `quality_score`, `quality_label`, `effectiveness`, `impact` | 价值判断属于 Cognitive Domain |
| **Evaluation Signals** | `reader_rating`, `reader_score`, `review_score`, `rating` | 读者评价属于 Phase14.4+ |
| **Recommendation Signals** | `recommended`, `preferred`, `suggested_usage`, `apply_now` | 推荐行为属于 Phase14.5+ |
| **Commercial Signals** | `sales_count`, `revenue`, `conversion_rate`, `subscription_boost` | 商业数据属于外部层 |
| **Human Judgment Signals** | `editor_score`, `expert_rating`, `human_label`, `author_tier` | 人工评价属于外部层 |
| **Popularity Signals** | `bestseller`, `trending`, `viral`, `popular_tag`, `hot_rank` | 热度标签可能携带价值偏向 |
| **Capability Signals** | `capability_id`, `capability_score`, `skill_tag` | 属于 Phase14.5+ |
| **Principle Signals** | `principle_id`, `principle_name`, `rule_text` | 属于 Phase14.4+ |

### 4.2 禁止字段完整列表

```
quality_score           quality_label           effectiveness
impact                  reader_rating           reader_score
review_score            rating                  recommended
preferred               suggested_usage         apply_now
sales_count             revenue                 conversion_rate
subscription_boost      editor_score            expert_rating
human_label             author_tier             bestseller
trending                viral                   popular_tag
hot_rank                capability_id           capability_score
skill_tag               principle_id            principle_name
rule_text               reader_attention_score  retention_rate
style_name              genre_label             emotional_valence
```

> **注意**: style_name 和 genre_label 虽与内容相关,但它们携带"这是什么风格的"隐含判断,属于理解层。Phase14.3 只回答"哪些特征组合出现",不回答"这是什么风格"。

## 5. 污染检测规则

| 规则 | 描述 |
|------|------|
| AD1 | 任何允许字段必须显式列在 Allow List 中 |
| AD2 | 隐式拒绝: 未在 Allow List 中的字段默认不可读 |
| AD3 | Deny List 中的字段即使出现在 Allow List 也必须拒绝 (Deny 优先) |
| AD4 | 禁止字段**不得出现在** EvidenceGraphSnapshot 的 nodes/relations 中 |
| AD5 | 新增字段 = 默认禁止,直到通过审查加入 Allow List |

## 6. 隔离验证

```
Input Payload
  ├── EvidenceNode (Allow List fields only)
  │     └── 若含有 Deny List 字段 → REJECT
  ├── EvidenceRelation (Allow List fields only)
  │     └── 若含有 Deny List 字段 → REJECT
  └── Metadata (Allow List fields only)
        └── 若含有 Deny List 字段 → REJECT
```
