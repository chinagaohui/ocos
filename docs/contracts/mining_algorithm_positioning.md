# Phase14.3 — Mining Algorithm Positioning

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §3.0 Algorithm Positioning Review

## 1. Purpose

定义 §3 Mining Algorithm Design 在整个 Phase14.3 中的精确定位。

这不是算法设计文档——**这是算法域进入前的认知边界冻结**。
当算法代码可以未来替换，但认知边界一旦污染就无法清洗。

## 2. Pipeline 位置

```
Evidence Graph
    ↓  §2 Snapshot Contract
EvidenceGraphSnapshot
    ↓  §3 Mining Algorithm  ← 当前位置
PatternCandidate[]
    ↓  §4 Validation
Pattern[]
    ↓  §5+ Classification & Registry
```

### 2.1 §3 的身份声明

```
Domain:     Observation
Role:       Statistical Structure Discovery
Input:      EvidenceGraphSnapshot (受 §2 契约约束)
Output:     PatternCandidate[] (受 §1 ABI 约束)
```

### 2.2 §3 不是

```
不是:  Cognitive Domain — Value Understanding
不是:  Quality Evaluator — 不判断好坏
不是:  Pattern Recommender — 不推荐应用
不是:  Style Learner — 不学习写作风格
不是:  Success Predictor — 不预测市场表现
```

## 3. Allow Domain — §3 可以做什么

### 3.1 Candidate Generation

发现 Evidence Graph 中的统计结构。允许的搜索类型：

| 类型 | 含义 | 示例 |
|------|------|------|
| **Co-occurrence** | 特征组频繁同时出现 | `sentence_length↓ + dialogue_ratio↑` 同现于 action_scene |
| **Sequential** | 特征按稳定顺序出现 | `narrative_speed↑ → dialogue_ratio↑` 跨段落序列 |
| **Transition** | 特征在边界处规律转换 | scene_transition 前后 `sentence_length` 变化模式 |
| **Cluster** | 节点基于特征自然聚集 | 以 `sentence_length/dialogue_ratio/tag_density` 为轴的空间聚集 |

**允许**：发现 `A + B + C 频繁共同出现`
**允许**：发现 `A → B → C 稳定顺序出现`
**禁止**：断言 `A → B → C 所以效果更好`

### 3.2 Search Space

| 允许定义 | 禁止定义 |
|----------|----------|
| 节点范围 (scope) | **根据价值标签缩小范围** (只搜爆款章节) |
| 关系类型范围 (relation_type_filter) | 基于质量评分的过滤 |
| 时间窗口 (window_definition) | 基于商业表现的加权 |
| 采样策略 (sampling_policy) | 个性化偏好选择 |

### 3.3 Statistical Metrics

描述**出现情况**的度量，不描述**质量**：

| 指标 | 含义 | 值域 |
|------|------|------|
| `frequency` | 出现频率 | [0.0, 1.0] |
| `support` | 支持度 (覆盖样本比例) | [0.0, 1.0] |
| `stability` | 跨样本稳定性 | [0.0, 1.0] |
| `distribution` | 范围分布 | 范围频率表 |
| `occurrence_count` | 绝对出现次数 | ≥ 0 |

**允许**：`rank patterns by frequency`
**禁止**：`rank patterns by quality`

### 3.4 Dedup Strategy

结构去重——管理候选集膨胀，不是评估价值。

允许：
- 避免 `P1: A+B` → `P2: A+B+C` → `P3: A+B+C+D` 无限制增长
- 合并等价结构
- 按粒度分层存储

禁止：
- 基于"价值"的过滤
- 基于"读者偏好"的排序
- 基于"商业效果"的剪枝

## 4. Forbidden Domain — §3 禁止做什么

### 4.1 绝对禁止清单

| 类别 | 举例 | 原因 |
|------|------|------|
| **Effectiveness 优化** | `maximize_effectiveness` | 隐含价值目标 |
| **Quality 评价** | `rank by quality`, `quality_score` | 不属于 Observation |
| **Better/Success 比较** | `better_pattern`, `success_rate` | 不属于 Observation |
| **Reader 偏好** | `reader_like`, `reader_preference`, `audience_fit` | 属于 Phase14.4+ |
| **Commercial 价值** | `commercial_value`, `bestseller_correlation` | 不属于 Phase14.3 |
| **推荐过滤** | `recommended`, `apply_priority` | 属于 Phase15 |
| **最大化目标函数** | `maximize retention`, `optimize conversion` | 引入价值域目标 |

### 4.2 禁止举例

```
❌ maximize_effectiveness(snapshot, config)
    → 算法已经知道"有效"是什么

❌ rank_patterns_by_quality(candidates)
    → quality 不属于 Observation Domain

❌ filter_by_reader_preference(candidates, reader_profile)
    → Reader 反馈在 Phase14.4+

❌ optimize_for_commercial(candidates, sales_data)
    → 商业数据是外部信号

❌ recommend_top_patterns(candidates, k=5)
    → 推荐行为在 Phase15
```

## 5. §3 与上下游的隔离

### 5.1 与 §2 Snapshot 的关系

```
§2 提供:  EvidenceGraphSnapshot (受 Allow/Deny 约束)
§3 接收:  同一份数据
§3 不得:  主动请求价值信号
```

### 5.2 与 §4 Validation 的关系

```
§3 职责:  发现"有没有稳定结构"
           输出 PatternCandidate

§4 职责:  验证"这个候选是否满足统计标准"
           例如: 是否稳定,是否跨范围复现,证据是否充分

§3 不得:  自行验证/自行过滤 (避免突破 Candidate→Pattern 层级)
§4 不得:  重新发现 (避免重复劳动)
```

### 5.3 与 §5+ Classification 的关系

```
§3 不得:  标记"这个模式属于 Style / Structure / Reader / Scene"
          归属分类在 §5+ Pattern Registry
```

## 6. 设计纪律

1. **算法可替换**: 算法代码可以未来优化/替换。但认知边界必须现在冻结。
2. **拒绝隐性价值**: 即使算法内部没有显式的价值目标，也不能通过"搜索策略偏好"或"采样偏置"引入隐性价值。
3. **确定性保持**: 同 snapshot_id + config_id + algorithm_version → 同输出候选集 (§2 确定性契约)。
4. **边界优先于性能**: 先保证边界正确，再谈算法效率。

## 7. §3.0 → §3.1 入口规则

§3.0 通过后进入 §3.1 Candidate Generation Model。
§3.1 仍不写算法代码，而是冻结：
- 候选生成空间定义
- Pattern 搜索类型枚举
- Mining Strategy 框架
- 复杂度边界
- 去重协议

§3.0 未通过 → 修正定位 → 重新审查。

## 8. 冻结声明

```
Phase14.3 §3.0 Algorithm Positioning ❄️ (2026-07-22)
Domain:  Observation — Statistical Structure Discovery
Input:   EvidenceGraphSnapshot (§2)
Output:  PatternCandidate[] (§1)
Frozen:  Allow Domain, Forbidden Domain, Isolation Boundaries
Unfrozen: Algorithm Implementation, Search Strategy, Parameter Values
```
