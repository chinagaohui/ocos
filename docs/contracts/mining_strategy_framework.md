# Phase14.3 — Mining Strategy Implementation Framework

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §3.2 Mining Strategy Implementation Framework

## 1. Purpose

定义矿挖策略的实现框架——"如何组织搜索过程"，而不是"哪个算法最好"。

§3.1 回答了"搜索什么"（Search Space），§3.2 回答了"搜索过程如何组织"（Strategy Implementation Framework）。

## 2. Strategy Interface

每条策略对外暴露统一的接口契约：

```
MiningStrategy
  input:   EvidenceGraphSnapshot  (引自 §2)
  output:  PatternCandidate[]     (引自 §1 ABI)
```

策略实例在输入/输出层面是完全可替换的——调用方不感知具体策略类型。

## 3. Strategy Lifecycle

每条策略的实现必须遵循以下生命周期阶段（每个阶段有严格输入/输出契约）：

```
Initialize
  │  接收 EvidenceGraphSnapshot
  │  创建策略本地上下文（不影响图数据本身）
  ▼
Prepare
  │  基于策略类型确定搜索参数
  │  如：window_scan 计算窗口边界
  │     global_scan 确定全局范围
  │     hierarchical_scan 构建层级树
  │     seed_based_scan 选择种子节点
  ▼
Search Space
  │  转化 §3.1 Search Space 定义
  │  为具体可遍历的搜索空间实例
  |  在此阶段执行 Scope Filter（仅允许的维度）
  ▼
Generate Candidate
  │  遍历搜索空间
  │  检测统计结构
  │  生成 PatternCandidate
  ▼
Normalize
  │  标准化输出到统一的 Candidate ABI
  │  映射字段名、格式化特征集、对齐关系结构
  ▼
Deduplicate
  │  引用 §3.1 Dedup Protocol
  │  去除等价/子集/重复 Candidatenode_attribution, with_counts
  ▼
Emit
  │  输出 PatternCandidate[]
  │  截断超过 max_candidate_count 的部分
```

### 生命周期纪律

1. **Prepare 不可修改 EvidenceGraphSnapshot**——策略只能读取，不能写入
2. **Search Space 阶段必须进行 Scope Filter**——过滤不允许的维度，而非过滤"低质量"数据
3. **Normalize 确保输出格式一致**——无论采用哪种策略，调用方看到的是同一 ABI
4. **Deduplicate 只判断结构相似性**——不比较价值

## 4. Strategy Isolation

所有策略共享同一个输入/输出契约，保证以下隔离：

| 策略类型 | 定位 |
|----------|------|
| global_scan | 遍历全部证据图节点对 |
| window_scan | 在时间/章节窗口内遍历 |
| hierarchical_scan | 按层级关系遍历 |
| seed_based_scan | 从选定种子节点扩展 |

### 隔离规则

1. **所有策略输出必须通过同一个 Candidate ABI**——不存在"special output for global_scan"
2. **策略之间不共享中间状态**——每条策略独立运行
3. **不同策略的输出可以合并**（在 §5 Pattern Registry 层面），但合并策略不在此阶段定义

## 5. Resource Boundary

为每条策略定义可执行资源约束：

| 约束 | 含义 | 示例值（上下文决定，不在此冻结） |
|------|------|----------------------------------|
| memory_limit | 策略运行最大内存 | 依赖部署环境 |
| max_node_visits | 最多访问的节点数 | 依赖数据规模 |
| max_candidate_limit | 输出候选上限 | 依赖下游容量 |
| time_budget_seconds | 执行时间上限 | 依赖调度策略 |

这些约束在实现时由上下文注入，不在框架层硬编码。

## 6. Strategy Comparison

策略间比较限于以下维度：

| 允许比较 | 禁止比较 |
|----------|----------|
| 覆盖范围（覆盖了多少节点/关系） | 哪个策略发现的结构"更好" |
| 执行成本（时间/内存/节点访问量） | 哪个策略更适合某类叙事 |
| 候选数量（生成了多少候选） | 哪个策略更受读者喜爱 |
| 结构类型分布 | 哪个策略推荐的写法更成功 |

## 7. Explicit Forbidden

§3.2 禁止：

- ❌ 实际 Mining Algorithm（留给后续子阶段）
- ❌ 小说类型特化搜索（如"只搜索言情小说的情感结构"）
- ❌ 作者风格学习或适应
- ❌ 写法推荐或评价
- ❌ 自动优化策略选择（策略选择权在调用方）

## 8. Appendix: Lifecycle State Audit

每条策略执行完成后，必须返回执行审计记录：

```
{
  "strategy_type": "global_scan",
  "pipeline_id": "uuid-xxx",
  "phases": {
    "prepare_ms": 12,
    "search_space_ms": 45,
    "generate_ms": 2340,
    "normalize_ms": 8,
    "deduplicate_ms": 23
  },
  "nodes_visited": 50000,
  "candidates_before_dedup": 1200,
  "candidates_after_dedup": 342,
  "candidates_emitted": 200,
  "memory_peak_mb": 128
}
```

审计记录用于策略比较和资源监控，不用于价值判断。
