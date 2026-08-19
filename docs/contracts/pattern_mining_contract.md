# Phase14.3 — Pattern Mining Input Contract

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)

## 1. Purpose

定义 Mining Engine 的输入输出契约——它在什么数据上操作、能读取什么、不能读取什么。

## 2. 输入定义

Mining Engine 接受唯一输入:

```
EvidenceGraphSnapshot:
  version: str                           # 快照版本标识
  created_at: str                        # ISO 8601 时间戳
  scope: str                             # 快照范围 (e.g. "corpus_v2.1", "work_0142")
  nodes: list[EvidenceNode]              # EvidenceNode 列表
  relations: list[EvidenceRelation]      # EvidenceRelation 列表
  metadata: EvidenceGraphMetadata        # 元数据
```

### 2.1 EvidenceNode (可用字段)

Mining Engine 可以读取:

| 字段 | 用途 |
|------|------|
| evidence_id | 节点标识 |
| evidence_type | 证据类型 |
| text_span | 文本范围 (位置/长度) |
| observation | 具体的观察数值 |
| feature_vector | 特征向量 |
| scope | 范围信息 |
| scene_index | 场景索引 |
| source_ref | 源引用 |

### 2.2 EvidenceRelation (可用字段)

Mining Engine 可以读取:

| 字段 | 用途 |
|------|------|
| relation_id | 关系标识 |
| relation_type | 关系类型 |
| source_evidence_id | 源节点 |
| target_evidence_id | 目标节点 |
| scope | 关系范围 |
| observation_count | 出现次数 |
| sample_size | 样本量 |

### 2.3 Metadata (可用字段)

| 字段 | 用途 |
|------|------|
| extraction_version | 提取版本 |
| corpus_size | 语料规模 |
| work_count | 作品数量 |
| chapter_count | 章节数量 |
| scene_count | 场景数量 |

## 3. 输出定义

Mining Engine 输出:

```
list[PatternCandidate]    # 候选模式列表
```

输出必须满足:
- **Deterministic**: 相同输入 + 相同参数 → 相同 PatternCandidate 集
- **No Value Judgments**: 所有 PatternCandidate 不含禁止字段
- **Scope Bounded**: 每个 PatternCandidate 的 scope 必须在允许范围内

## 4. 禁止输入信号

Mining Engine **不得读取**以下数据源:

| 类别 | 禁止内容 | 原因 |
|------|----------|------|
| Reader Signals | ReaderOS 评分、读者情绪标签、阅读时长、留存率 | 属于 Phase14.4+ 认知层 |
| Quality Signals | Quality Gate 评分、质量标签、评审意见 | 属于 Phase14.4+ 评估层 |
| Commercial Metrics | 销售额、订阅量、转化率、商业标签 | 属于外部商业层 |
| Human Evaluation | 人工评分、专家评价、编辑标签、作者等级 | 属于外部评估层 |
| Capability | Capability 标识、能力评分、技能标签 | 属于 Phase14.5+ |
| Principle | Principle 标识、原则名称、规则描述 | 属于 Phase14.4+ |
| Popularity | 爆款标签、热门标识、推荐次数 | 属于外部市场层 |

## 5. 输出确定性测试契约

```
def test_deterministic_discovery():
    """
    相同 EvidenceGraphSnapshot + 相同 Mining 参数
    → 两次输出必须包含相同的 PatternCandidate 集
    (以 candidate_id + feature_set + frequency 三元组判定)
    """
    snapshot = load_test_snapshot("corpus_v2.1")
    params = MiningParams(min_frequency=0.1, scope_limit="chapter")

    engine = PatternMiningEngine(params)
    result_a = engine.mine(snapshot)
    result_b = engine.mine(snapshot)

    assert sorted(result_a, key=key_fn) == sorted(result_b, key=key_fn)
```

## 6. 合约规则

| 规则 | 描述 |
|------|------|
| MC1 | Mining Engine 输入必须为 EvidenceGraphSnapshot |
| MC2 | Mining Engine 不得访问禁止输入信号 |
| MC3 | 输出必须为 list[PatternCandidate] |
| MC4 | 输出结果必须确定性可重复 |
| MC5 | 输出 scope 不得超过 EvidenceGraphSnapshot 的 scope 范围 |
| MC6 | 输出必须满足 PatternCandidate ABI 约束 |
