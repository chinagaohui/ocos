# Phase14.3 — Pattern Registry Query Contract

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §5.3 Pattern Registry Query Contract

## 1. Purpose

定义 Pattern Registry 的受控读取接口——提供对 Pattern 观察记录的查询能力，但不是搜索系统、推荐引擎或认知分析接口。

§5.3 建立的基础：
- §5.1 ABI：定义了存储什么（PatternRecord 结构）
- §5.2 Lifecycle：定义了如何存在（生命周期状态语义）
- §5.3 Query：定义如何读取

## 2. Query Interface

### 2.1 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| query_context | Dict | 否 | 查询上下文（如 feature 过滤器、relation 过滤器） |
| scope_filter | str | 否 | 按 context_boundary / observation_scope 筛选 |
| version_constraint | str | 否 | 版本约束（如 ">=1.0.0"、"latest"） |
| status_filter | List[str] | 否 | 按生命周期状态筛选（如 ["registered", "archived"]） |
| pattern_ids | List[str] | 否 | 精确 ID 查询 |

参数为按需组合，不要求全部提供。

### 2.2 输出

```
PatternReference {
    pattern_id: str
    feature_structure: Dict
    relation_structure: List
    status: str
    version: str
    context_boundary: Optional[str]
    observation_scope: Optional[str]
    source_candidate_ids: List[str]
    validation_record_ids: List[str]
    history_summary: Optional[List]  # 精简版本历史摘要
}
```

输出字段来自 PatternRecord（§5.1），不新增字段。

### 2.3 查询语义

- 未提供任何过滤器时：返回所有状态的 Pattern 列表
- 多过滤器组合：AND 语义（同时满足所有筛选条件）
- 空结果集：返回空列表（不是错误）
- 不存在的 pattern_id：返回空列表（不是错误）

## 3. Query Allow Boundary

### 3.1 允许的查询方式

| 查询维度 | 说明 |
|----------|------|
| 按 pattern_id 查询 | 精确 ID 匹配 |
| 按 feature_structure 查询 | 匹配 feature_structure 中指定的键值对 |
| 按 relation_structure 查询 | 匹配 relation_structure 中的关系 |
| 按 context_boundary 查询 | 按观察上下文范围筛选 |
| 按 version 查询 | 按版本号约束（精确/范围/最近） |
| 按 lifecycle 状态查询 | 按 validated/registered/archived/invalidated 筛选 |
| 按 source_candidate_ids 查询 | 追溯到原始候选 |
| 按 validation_record_ids 查询 | 追溯到验证记录 |
| tags 过滤 | 按扩展标签筛选（tags 是结构化检索用，无语义含义） |

### 3.2 组合查询

多条件查询使用 AND 组合。

示例：
- 查询所有 registered 状态的 Pattern，feature_structure 包含 "sentence_shortening"
- 查询所有 archived 状态的 Pattern，version >= 2.0.0
- 查询所有 validated 状态的 Pattern，observation_scope == "cross_project"

### 3.3 分页

查询支持分页（offset / limit）以支持大数据量。分页参数：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| offset | int | 0 | 跳过的记录数 |
| limit | int | 50 | 返回的最大记录数（上限 100） |
| total | bool | false | 是否返回总匹配数 |

分页不影响确定性——在相同 Registry Snapshot 下，相同的 offset/limit 返回相同结果。

## 4. Query Forbidden Boundary

### 4.1 禁止的输出字段

| 字段 | 禁止原因 |
|------|----------|
| quality_score | 品质判断属于 Cognitive Domain |
| effectiveness | 效果评估超出 Observation |
| success_rate | 成功率属于 Control Domain |
| recommendation | 推荐行为属于 Capability |
| priority | 优先级排序超出 Registry |
| ranking | 排名超出存储层职责 |
| confidence | 置信度（非统计置信区间） |
| usefulness | 有用性判断属于 Cognitive Domain |
| best_for | 适用性推荐属于 Phase14.5 |
| should_apply | 是否应用属于 Phase15 |

### 4.2 禁用的查询操作

| 操作 | 禁止原因 |
|------|----------|
| sort_by_best | "最好"涉及价值判断 |
| rank_patterns | 排名超出 Observation |
| select_optimal | "最优"选择属于 Control Domain |
| recommend_top | 推荐属于 Capability |
| find_similar | 相似度匹配涉及认知判断 |
| cluster_patterns | 聚类是认知分析（Phase14.4） |
| summarize_patterns | 摘要生成超出存储层 |
| explain_pattern | 解释属于 Cognitive Domain |
| predict_applicability | 适用性预测属于 Phase15 |

### 4.3 禁止的查询模式

| 模式 | 禁止原因 |
|------|----------|
| "给我最好的写作模式" | 推荐/排名 |
| "推荐适合 X 题材的模式" | Phase14.5 |
| "找出最有效的模式" | 效果判断 |
| "有什么区别" | 对比分析属于 Cognitive Domain |
| "为什么这个模式存在" | 因果解释超出 Observation |

## 5. 确定性要求

### 5.1 核心原则

```
∀ query, registry_snapshot:
    run(query, registry_snapshot, tc1) = run(query, registry_snapshot, tc2)
```

相同的 Registry Snapshot + 相同的查询参数 = 相同的结果。

### 5.2 确定性保障

| 因素 | 确定性处理 |
|------|------------|
| Registry 内容 | 固定快照，查询期间不变 |
| 版本约束 | 精确比较，不含 AI 推断 |
| 状态筛选 | 精确字符串匹配 |
| 特征匹配 | 精确键值对匹配 |
| 分页 | 固定 offset/limit，无随机采样 |
| 排序 | 按 pattern_id 自然序（UUID 字符串序） |
| 空结果 | 返回 []，不是 None 或错误 |

### 5.3 排序规则

查询结果默认按 pattern_id 升序排序。无活跃/推荐序。

## 6. 与 Phase14.4 的隔离

### 6.1 隔离原则

Query 输出 = Pattern Reference

不是：

- Principle
- Interpretation
- Meaning
- Recommendation
- Capability

### 6.2 禁止输出

| 输出类型 | 禁止原因 |
|----------|----------|
| CandidatePrinciple | Phase14.4 专属，Registry 不涉及 |
| InterpretationScore | 解读评分超出 Observation |
| CognitiveLabel | 认知标注属于 Phase14.4 |
| GenreSuggestion | 类型建议超出存储层 |
| UsageAdvice | 使用建议属于 Phase15 |

### 6.3 Phase14.4 如何使用

```
Phase14.3 Registry ← 只读查询 ── Phase14.4 Meta Principle Formation
                                         ↓
                                    Pattern Reference[]
                                         ↓
                                    分析、归纳、形成 Principle
```

Phase14.4 从 Registry 读取 Pattern，自己分析形成 Principle。
Registry 不提供预分析的结果。

## 7. 查询结果不可变契约

- 查询本身**不修改** Registry 状态
- 查询结果**不缓存**到 Registry 中
- 查询不产生审计事件（读操作不记录）
- 查询不触发任何副作用（不写日志之外的任何输出）

## 8. 错误处理

| 场景 | 行为 |
|------|------|
| 无效 pattern_id | 返回空结果，非错误 |
| 无效 status_filter | 忽略该过滤器，继续执行 |
| 无效 version_constraint | 忽略该约束，继续执行 |
| 超出分页限制 | 限制到最大值（100） |
| 空 Registry | 返回空列表 |
| 查询超时 | 返回当前已收集的结果 + 截断标记 |

错误定义：查询接口没有"失败"——最多返回空结果。
查询不抛出异常（抛异常属于实现问题，不是契约问题）。

## 9. 与 §5.2 Lifecycle 的关系

Query 利用 §5.2 定义的 lifecycle status 进行筛选。
状态语义由 §5.2 定义，Query 只读取不解释。

```
§5.2 定义：registered = "观察档案中的活跃记录"
§5.3 执行：status_filter=["registered"] → 返回所有 registered Pattern
```

Query 不添加关于状态的额外语义。
