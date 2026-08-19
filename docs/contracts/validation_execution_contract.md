# Phase14.3 — Validation Execution Contract

**Domain**: Observation (Pattern Discovery Layer)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.3 §4.2 Validation Execution Contract

## 1. Purpose

定义 Validation Engine 的执行契约——验证过程如何运行、不能做什么、如何保证确定性、如何记录审计轨迹。

§4.1 定义了验证的**数据结构**（ABI / 维度 / 阈值 / 状态）。§4.2 定义验证的**运行规则**。

## 2. Execution Pipeline

### 2.1 Pipeline Stages

```
initialize → resolve_candidates → evaluate_dimensions → aggregate_status → emit_result
```

| Stage | 职责 | 输入 | 输出 |
|-------|------|------|------|
| initialize | 加载阈值配置、验证器版本、时间戳 | ThresholdConfig, validator_version | ExecutionContext |
| resolve_candidates | 逐个解析 PatternCandidate 的统计字段 | PatternCandidate[] | ResolvedCandidate[] |
| evaluate_dimensions | 对每个维度执行阈值比较 | ResolvedCandidate, ThresholdConfig, DimensionMap | DimensionResult[] |
| aggregate_status | 聚合所有维度结果并确定状态 | DimensionResult[] | PatternStatus |
| emit_result | 输出 ValidationEvidence + status | PatternStatus, DimensionResult[] | ValidationRecord |

### 2.2 不允许的 Pipeline

以下 pipeline 设计被禁止：

```text
# ❌ 禁止：引入 Cognitive Domain 判断
initialize → evaluate → interpret("这个模式好在哪里") → emit

# ❌ 禁止：修改 Evidence Graph
initialize → evaluate → modify_evidence_graph → emit

# ❌ 禁止：跨候选优化排序
initialize → evaluate_all → rank_candidates → emit_best
```

### 2.3 允许的 Pipeline 变体

```text
# ✅ 允许：批量执行（无交叉比较）
for each candidate:
    initialize → evaluate → emit

# ✅ 允许：带上下文的单次执行
initialize(resolve_context=True) → evaluate → emit
```

## 3. Execution Isolation

Validation Engine 执行期间**不得**：

| 禁止项 | 原因 |
|--------|------|
| 修改 Evidence Graph | 违背 Phase14.3 定位——观察者不改变观察对象 |
| 写入 Pattern Registry | 必须经过 Governance Gate（见 §4.0 §9） |
| 修改 PatternCandidate | 候选是 Mining 阶段的产物，Validation 无权变更 |
| 访问 Cognitive Domain 服务 | 原则性隔离——Phase14.4 尚未进入 |
| 触发 OpenTale 调控 | Control Domain 未进入 |
| 访问读者评分、质量评估、商业指标 | 被 §4.0 Forbid List 禁止 |
| 持久化任何副作用 | Validation 是纯计算过程 |
| 调用外部 AI 模型解释结果 | 解释属于 Cognitive Domain |

**允许的操作**：

| 允许项 | 说明 |
|--------|------|
| 读取 Evidence Graph（只读） | 用于 cross-context 和 counter-evidence 检查 |
| 读取 ThresholdConfig | 来源自 Pattern Registry 的配置 |
| 写入 Execution Audit | 审计日志（见 §6） |
| 写入临时中间结果 | 仅限于 Engine 内存生命周期内 |

## 4. Determinism Contract

### 4.1 确定性规则

相同输入必定产生相同输出。

```text
∀ input, full_validator, threshold_config:
    run(input, threshold_config) == run(input, threshold_config)
```

### 4.2 确定性约束

- 维度评估顺序不影响结果
- 阈值比较函数必须是纯函数（无状态、无随机数）
- 反例检查必须使用相同的统计范围定义
- 不允许使用随机采样或 shuffle
- 不允许使用时间戳作为比较因子（时间戳仅记录在审计中）

### 4.3 非确定性来源（禁止）

| 来源 | 禁止原因 |
|------|----------|
| 随机数生成 | 每次运行结果可能不同 |
| 外部 API 调用 | 结果不可控且可能失败 |
| 内存地址依赖 | 不同环境地址不同 |
| 哈希种子不一致 | Python 3 默认 seed 随机化 |
| 浮点精度依赖 | 跨平台舍入不一致 |

## 5. Candidate Resolution Contract

Validation 必须从 PatternCandidate 中提取以下字段：

### 5.1 必需解算字段

| 字段 | 来源（PatternCandidate） | 用途 |
|------|--------------------------|------|
| pattern_id | pattern_id | 标识验证目标 |
| observed_frequency | frequency | 与 minimum_observation_count 比较 |
| observed_stability | stability | 与 maximum_variance 比较 |
| observed_recurrence | recurrence | 与 minimum_context_count 比较 |
| observed_cross_context | cross_context_count | 与 minimum_context_type_count 比较 |
| observed_counter_ratio | counter_evidence.ratio | 与 maximum_counter_ratio 比较 |

### 5.2 禁止解算的字段

| 字段 | 禁止原因 |
|------|----------|
| quality_score | §4.0 禁止 |
| effectiveness | §4.0 禁止 |
| recommendation | §4.0 禁止 |
| 外部评分 | 任何非统计信号 |
| 候选生成时的中间状态 | 已超出 Validation 的职责范围 |

## 6. Audit Contract

Validation 的每次执行必须记录审计轨迹，以便追溯验证决策。

### 6.1 Audit Record Fields

| 字段 | 类型 | 说明 |
|------|------|------|
| execution_id | str (UUID) | 单次执行唯一标识 |
| start_timestamp | datetime | 执行开始时间 |
| end_timestamp | datetime | 执行结束时间 |
| validator_version | str | 验证器版本标识 |
| candidate_count | int | 本轮处理候选数 |
| dimension_results | List[DimensionResult] | 每个维度的比较结果（含 observed/threshold/met） |
| status_counts | Dict[str, int] | validated/archived/invalidated 数量 |
| peak_memory_mb | float | 执行峰值内存（可选） |
| errors | List[str] | 执行过程中的异常记录（无异常则为空） |

### 6.2 Audit 禁止项

| 字段 | 禁止原因 |
|------|----------|
| quality_score | 价值判断 |
| ranking | 排序输出 |
| recommendation | 推荐行为 |
| cognitive_notes | 超出观察层 |

### 6.3 Audit 纯度要求

Audit Record 是**追加写入**的——已完成的 audit record 不可修改。

## 7. Error Handling

| 场景 | 行为 | 候选状态 |
|------|------|----------|
| Candidate 缺少必需字段 | 跳过该候选，记录 error | 不变（不进入 validated/archived/invalidated） |
| 阈值配置缺失某个维度 | 使用该维度的默认值（禁止值语义），记录 warning | 正常评估 |
| CounterEvidence 数据不完整 | 以 counter_evidence = 0 处理，记录 warning | 正常评估 |
| 全局执行超时 | 终止执行，已完成的候选正常输出 | 按实际结果 |
| 内存超限 | 终止执行，已输出结果保持有效 | 按实际结果 |

## 8. Execution Lifecycle

```
IDLE → RUNNING → COMPLETED
           ↓
         FAILED
```

| 状态 | 含义 |
|------|------|
| IDLE | Engine 已初始化，等待执行 |
| RUNNING | 正在执行 validate 流程 |
| COMPLETED | 所有候选已处理，审计记录已写入 |
| FAILED | 执行异常终止，部分候选可能已处理 |

失败状态下已完成的 ValidationRecord 仍然有效——Engine 不负责回滚。

## 9. Versioning

- Validator 必须携带版本号（semver）
- 版本号记录在每个 ValidationEvidence 中
- 相同版本号的相同输入必须产生相同输出
- 版本升级需要重新验证已注册的 Pattern（交由 Governance Gate 决策）