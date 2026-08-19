# Phase14.3 — Candidate Generation Model

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §3.1 Candidate Generation Model

## 1. Purpose

定义 Mining Engine 生成 PatternCandidate 的搜索空间、挖掘策略框架、复杂度边界和去重协议。

**这不是算法设计文档**——只冻结候选生成的边界和约束，不绑定具体算法实现（Apriori / FP-Growth / GNN / Embedding Search 等留 §3.2+）。

## 2. Pipeline 位置

```
§2 EvidenceGraphSnapshot
   ↓
§3.1 Candidate Generation Model  ← 当前位置
   ↓
Mining Operations (§3.2+，实现层)
   ↓
PatternCandidate[]
   ↓
§4 Validation
```

## 3. Search Space — Mining Engine 在哪些维度寻找结构

### 3.1 搜索维度

| 维度 | 含义 | 允许搜索 | 禁止范围 |
|------|------|----------|----------|
| **Node Space** | 哪些 EvidenceNode 参与搜索 | 所有符合 scope_filter 的节点 | 按作品质量/作者等级过滤 |
| **Relation Space** | 哪些 EvidenceRelation 参与连接 | 所有 relation_type_filter 允许的类型 | 按商业表现/读者评分筛选关系 |
| **Temporal Scope** | 时间窗口内的结构搜索 | 窗口内出现/顺序/转换 | 根据价值标签裁剪窗口 |
| **Context Boundary** | 上下文边界定义 | 段落/场景/章节/作品层级 | 根据"是否精彩"选择边界 |
| **Hierarchy Scope** | 分层聚合粒度的选择 | 从节点级到跨作品级 | 按商业成就有偏向地选择层级 |

### 3.2 搜索空间定义

```
SearchSpace:
  node_filters:     dict   # 节点筛选条件 (scope_filter, type_filter)
  relation_filters: dict   # 关系筛选条件 (relation_type_filter)
  temporal_window:  dict   # 时间窗口定义 (可选)
  hierarchy_levels: list   # 聚合层级列表 (e.g. ["scene", "chapter", "work"])
  max_nodes:        int    # 最大参与节点数 (上限)
```

### 3.3 禁止的搜索偏置

```
❌ SearchSpace(hierarchy_levels=["scene_bestseller"])
    → 按商业成就选择层级

❌ SearchSpace(node_filters={quality_score > 0.8})
    → 按质量评分过滤节点

❌ SearchSpace(temporal_window={"high_rating_chapters_only": True})
    → 按读者评分选择时间窗口
```

## 4. Pattern Search Types — 允许发现的模式类型

### 4.1 枚举

| 类型 | 数学含义 | 命名纪律 |
|------|----------|----------|
| `CO_OCCURRENCE` | 特征/实体在同一范围内同时出现 | 描述"怎么出现"，不解释"有什么意义" |
| `SEQUENCE` | 特征/实体按稳定顺序出现 | 同上 |
| `TRANSITION` | 特征在边界处发生规律性变化 | 同上 |
| `CLUSTER` | 特征/实体基于某种相似性自然聚集 | 同上 |

### 4.2 禁止的模式类型命名

```
❌ EMOTION_PATTERN     — 名称已带入解释
❌ SUCCESS_PATTERN     — 隐含价值判断
❌ VIRAL_PATTERN       — 隐含商业判断
❌ HIGH_QUALITY_PATTERN— 隐含质量判断
❌ READER_FAVORITE     — 隐含读者偏好
❌ RECOMMENDED_STRUCTURE— 隐含推荐意图
```

### 4.3 搜索类型定义

```
PatternSearchType:
  type_id:   str      # 枚举值: CO_OCCURRENCE / SEQUENCE / TRANSITION / CLUSTER
  name:      str      # 可读名称（仅统计描述）
  definition: str     # 数学/逻辑定义

  # 允许的附加属性
  feature_count:  int  # 参与特征的数目
  support_count:  int  # 支持样本数
  frequency:      float  # 频率

  # 禁止的附加属性
  # quality_score: float       — 禁止
  # effectiveness: float       — 禁止
  # reader_appeal: float       — 禁止
```

## 5. Mining Strategy Framework — 策略类别

### 5.1 允许的策略类别

| 策略 | 含义 | 适用场景 |
|------|------|----------|
| **Global Scan** | 在整个搜索空间内扫描所有结构 | 小型/中型数据集，全貌发现 |
| **Window Scan** | 在滑动窗口内局部扫描 | 时序/顺序模式发现 |
| **Hierarchical Scan** | 按层级逐层聚合发现 | 多粒度结构发现 |
| **Seed-based Scan** | 从种子节点/关系出发扩展 | 具热点中心的结构发现 |

**不绑定**：Apriori / FP-Growth / GNN / Embedding Search — 这些是算法的具体实现，属于 §3.2+。

### 5.2 禁止的策略

```
❌ Value-guided Scan     — 根据价值信号引导搜索方向
❌ Reader-bias Scan      — 根据读者偏好调整搜索权重
❌ Success-directed Scan — 根据商业成功定向搜索
```

## 6. Complexity Boundaries — 搜索复杂度约束

### 6.1 允许定义的上限

| 约束 | 含义 | 类型 |
|------|------|------|
| `max_feature_depth` | 组合特征的最大深度（A+B+...） | int，≥ 1 |
| `max_expansion_width` | 每个节点的最大扩展宽度 | int，≥ 1 |
| `max_candidate_count` | 单次挖掘最大候选数 | int，≥ 1 |
| `min_support` | 最小支持度（过滤稀疏模式） | float，[0.0, 1.0] |
| `max_scope_depth` | 层级搜索最大深度 | int，≥ 1 |

**不冻结具体数字**——不同数据规模需要动态调整。

### 6.2 禁止的约束

```
❌ min_quality           — 基于质量的过滤
❌ max_commercial_only   — 商业优先的剪枝
❌ reader_relevance_threshold — 基于读者偏好的阈值
```

## 7. Dedup Protocol — 候选去重协议

### 7.1 去重规则

所有去重基于**结构相似性**，不是价值相似性。

| 规则 | 含义 | 示例 |
|------|------|------|
| DP1 | 完全相同特征集 + 完全相同关系结构 = 重复 | `{f1,f2}` + `co_occurrence` = 重复 |
| DP2 | 子集关系：P1 特征集 ⊆ P2 特征集 + 同结构 = 同链，保留最简 | `{f1,f2}` 和 `{f1,f2,f3}` 同结构 → 保留最简 |
| DP3 | 合并等价结构：不同关系类型但统计不可分 = 合并 | 不同关系类型但同频率分布 |
| DP4 | 粒度分层：相同模式在不同范围的实例 = 分层不重复 | 同一模式在 scene/chapter/work 都有实例 |

### 7.2 禁止的去重

```
❌ "这篇写得更好 → 保留这个"     — 价值判断
❌ "读者更喜欢这个 → 合并那个"  — 读者偏好
❌ "这个模式更有可能 → 只保留"  — 预测偏向
```

## 8. Candidate Output Shape — 候选输出形状

### 8.1 输出定义

每个 Candidate 必须包含 §1 PatternCandidate ABI 定义的最低字段：

```
PatternCandidate:
  candidate_id:       str      # UUID
  scope:              dict     # domain, boundary
  feature_set:        list     # 特征列表
  relation_structure: list     # 关系结构
  occurrence_stats:   dict     # occurrence_count, frequency, sample_size
  source_relation_ids: list    # 可追溯的源关系 ID 列表
  mining_algorithm_version: str # 挖掘算法版本
  mined_at:           str      # ISO 8601
  status:             str      # "candidate"
```

### 8.2 禁止的输出

```
❌ Pattern[]               — 必须经过 §4 Validation
❌ Principle[]             — Phase14.4
❌ Recommendation[]        — Phase15
❌ 包含 quality_score      — 价值信号
❌ 包含 effectiveness      — 价值信号
```

## 9. Search Neutrality Contract — 搜索中立性契约

### 9.1 原则声明

**搜索空间本身不能隐藏偏向。**

Mining Engine 的搜索行为必须对所有结构保持中立——不以优先级、权重、价值信号或推荐方向偏袒某种模式。

### 9.2 中立性规则

| 规则 | 描述 |
|------|------|
| SN1 | Search Space 不能包含"只搜索 XX 型结构"的隐式偏置 |
| SN2 | 搜索方向不能根据价值标签调整 |
| SN3 | 权重分配必须基于统计出现，不能基于预测质量 |
| SN4 | 随机/采样策略不能偏向高价值样本 |
| SN5 | 搜索策略类别（Global/Window/Hierarchical/Seed）对所有结构一视同仁 |

### 9.3 违反示例

```
❌ Default search only "conflict scenes"
    → 搜索空间已偏向某种叙事类型

❌ Weight by reader_rating before searching
    → 引入读者评价偏置

❌ Skip search on non-bestseller works
    → 引入商业偏置

❌ Higher priority for "action scene structures"
    → 引入类型偏置
```

### 9.4 违反后果

搜索中立性违背将导致：

- 发现的 Pattern 集携带系统性偏置
- Phase14.4 基于偏置数据形成有偏 Principle
- Phase14.5 Capability 基于偏置 Principle 产生有害控制
- 整条 Observation → Cognitive → Control 链不可信

## 10. 冻结声明

```
Phase14.3 §3.1 Candidate Generation Model ❄️ (2026-07-22)
Domain:  Observation — Search Space & Candidate Discovery Constraints
Frozen:  Search Space, Pattern Types, Strategy Framework,
         Complexity Boundaries, Dedup Protocol, Output Shape,
         Search Neutrality Contract
Unfrozen: Algorithm Implementation, Parameter Values,
          Performance Optimization, Specific Mining Methods
```
