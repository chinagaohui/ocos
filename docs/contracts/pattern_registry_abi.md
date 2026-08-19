# Phase14.3 — Pattern Registry ABI

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §5.1 Pattern Registry ABI

## 1. Purpose

定义 Pattern Registry 的存储数据结构——PatternRecord 承载的字段、生命周期状态、版本策略、审计字段，以及绝对禁止的字段类型。

PatternRecord = 观察事实的持久化容器。描述"这个结构是什么"，不回答"这个结构好不好"。

## 2. PatternRecord 核心字段

### 2.1 身份字段

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| pattern_id | str (UUID) | 是 | 全局唯一标识 |
| source_candidate_ids | List[str] | 是 | 产生该 Pattern 的 PatternCandidate ID 列表（≥1） |
| validation_record_ids | List[str] | 是 | 通过该 Pattern 的 ValidationRecord ID 列表（≥1） |
| version | str (semver) | 是 | 当前版本号（初始 1.0.0） |
| status | str (enum) | 是 | 当前生命周期状态（§3） |

### 2.2 结构描述字段

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| feature_structure | Dict | 是 | 观察到的特征结构（与 PatternCandidate.feature_set 同义） |
| relation_structure | List[Tuple] | 是 | 观察到的关系结构（与 PatternCandidate.relation_structure 同义） |
| context_boundary | str | 否 | 该 Pattern 被验证的上下文范围描述（如 "zh_novel_fiction_2015_2025"） |
| observation_scope | str | 否 | 观察覆盖范围（如 "cross_project", "single_project", "limited"） |

### 2.3 审计字段

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| created_at | datetime | 是 | 首次存入 Registry 的时间 |
| updated_at | datetime | 是 | 最近一次状态变更的时间 |
| history | List[RegistryHistory] | 是 | 完整版本历史（至少 1 条） |
| governance_action_id | str (UUID) | 是 | 批准该 Pattern 进入 Registry 的 Governance Gate 动作 ID |

### 2.4 RegistryHistory 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| version | str | 该历史版本的版本号 |
| status | str | 该版本时的生命周期状态 |
| changed_at | datetime | 变更时间戳 |
| change_type | str | 变更类型：create / update_status / rollback / archive |
| governance_action_id | str | 触发该变更的 Governance Gate 动作 ID |
| comment | str (可选) | 变更说明 |

## 3. 生命周期状态

```
validated → registered → archived
                ↓
           invalidated
```

| 状态 | 含义 | 可迁入 |
|------|------|--------|
| validated | 候选已通过验证，待 Gate 审批 | 来自 §4 输出 |
| registered | 已通过 Gate 审批，存入观察档案 | validated |
| archived | 不再活跃，但记录保留 | registered |
| invalidated | Gate 撤回/否决，但记录保留 | validated, registered |

### 状态语义纪律

- **registered** ≠ "推荐使用"。含义：该结构已被观察到并录入观察档案。
- **archived** ≠ "无用"。含义：该结构在当前上下文中不再活跃观察。
- **invalidated** ≠ "错误"。含义：Gate 判定该结构不适合继续留在活跃观察集中（可能因数据污染、单作品偏差等）。

所有状态的 PatternRecord 都不可删除——archived 和 invalidated 状态的记录同样保留完整追溯链。

## 4. 版本策略

| 场景 | 版本行为 |
|------|----------|
| 首次写入 | version = 1.0.0 |
| 状态变更 | version 不变 |
| 纠正结构描述 | version 升 minor (1.0.0 → 1.1.0) |
| 回滚 | version 记录恢复到历史版本号 |
| 结构重新定义 | version 升 major (1.0.0 → 2.0.0) |

版本号递增表示 Pattern 定义的变更。状态变更不构成定义变更。

## 5. 字段 Allow List

PatternRecord 允许包含的字段类别：

| 类别 | 字段 |
|------|------|
| 标识 | pattern_id, version, status |
| 来源 | source_candidate_ids, validation_record_ids, governance_action_id |
| 结构 | feature_structure, relation_structure |
| 范围 | context_boundary, observation_scope |
| 时间 | created_at, updated_at |
| 历史 | history |
| 扩展 | tags (仅用于结构化检索，无语义含义) |

## 6. 字段 Forbid List

PatternRecord 绝对禁止包含的字段：

| 字段 | 禁止原因 |
|------|----------|
| quality_score | 质量判断属于 Cognitive Domain |
| effectiveness | 效果判断属于 Cognitive Domain |
| success_rate | 成功评估属于 Control Domain |
| recommendation | 推荐行为属于 Phase14.5 Capability |
| usage_frequency_as_advice | "常用=好"是价值判断 |
| best_for | 模式匹配推荐属于 Control Domain |
| should_apply | 建议施加属于 Phase15 |
| genre_quality_rating | 类型质量评分超出 Observation |
| author_preference | 作者偏好是认知分析 |
| reader_rating | 读者评分是 Control Domain 输入 |
| usefulness | 有用性判断属于 Cognitive Domain |
| difficulty_level | 难度评估属于 Cognitive Domain |
| creativity_score | 创造性评分超出 Observation |
| novelty_score | 新颖性评分超出 Observation |
| confidence | 置信度（非统计置信区间，指"相信这个模式好"） |
| popularity | 流行度评估超出 Observation |
| aesthetic_value | 审美判断超出 Observation |
| commercial_value | 商业价值超出整个 Pattern 系统 |

## 7. PatternRecord 不变性

一个 PatternRecord 被写入 Registry 后：

- 核心字段（feature_structure, relation_structure, source_candidate_ids, validation_record_ids）不可修改
- 状态只能通过生命周期状态转移变更
- 版本只能通过版本策略递增
- 历史只增不删

不可执行的操作：

| 操作 | 禁止原因 |
|------|----------|
| MERGE | 合并两个 Pattern 是认知行为 |
| IMPROVE | 改进 Pattern 定义超出存储职责 |
| OPTIMIZE | 优化 Pattern 结构超出存储职责 |
| ENHANCE | 增强 Pattern 信息超出 Observation |
| SPLIT | 拆分 Pattern 是认知分析 |
| SUPPLEMENT | 补充额外分析信息超出存储层 |

## 8. Query 设计原则

§5.1 不定义完整查询接口，只定义查询原则（§5.3 定义完整查询契约）。

查询必须是**被动的**：

```
允许的查询形式：
  获取 pattern_id 为 X 的 PatternRecord
  获取 feature_structure 包含 Y 的 PatternRecord 列表
  获取 status = registered 的 PatternRecord 列表
  获取版本历史

禁止的查询形式：
  获取"最好"的 Pattern
  推荐某个上下文适用的 Pattern
  排序 Pattern 列表
  获取"最相关的" Pattern (相关性由查询者判断)
```

## 9. 与 ValidationRecord 的关系

```
PatternCandidate (1..N)
     ↓  (mining + validation)
ValidationRecord (1..N)
     ↓  (Governance Gate 审批通过)
PatternRecord (1)
     ↓
Registry
```

- 一个 PatternRecord 可能对应多个 ValidationRecord（多次验证）
- 一个 ValidationRecord 可能对应同一个 PatternRecord 的多次验证
- PatternRecord.source_candidate_ids 追溯到候选源头
- PatternRecord.validation_record_ids 追溯到验证记录
- ValidationRecord 不修改已注册的 PatternRecord

## 10. 与 Phase14.4 的关系

```
PatternRegistry (只读引用)
     ↓
Phase14.4 Meta Principle Formation
     ↓
Principle[]
```

- Phase14.4 使用 Pattern 作为输入来形成 Principle
- Phase14.4 不修改 Registry 中的 PatternRecord
- Registry 不为 Phase14.4 提供预计算的解读
