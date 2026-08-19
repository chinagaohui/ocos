# Phase 37: Adaptive Cognitive Feedback Loop — Freeze Protocol v0.2

**Status**: APPROVED WITH MINOR AMENDMENTS (v0.1 Architecture Review passed)
**Date**: 2026-07-25
**Scope**: 6 frozen protocols + governance boundary + runtime integration + feedback lifecycle
**Risk Level**: ⚠️ HIGH (first phase to touch "system changes own behavior")
**v0.2 Changes**: Added §1.3 provenance chain, §1.4 source traceability, §2.3 alignment constraint, §3.4 sample protection, §4.4 mutation budget, §5.4 evidence chain, §6.4 drift output constraint, §7.3 permission matrix, §13 feedback lifecycle

---

## Position Statement

Phase 37 不是"学习能力扩展"，而是把 Phase 34-36 形成的闭环变成**可自我校准的控制系统**。

```
Phase 34: Persistent Cognitive Loop
    ↓  有生命循环
Phase 35: Attention & Cognitive Control
    ↓  有认知资源分配
Phase 36: Executive Attention Binding
    ↓  有行动控制
Phase 37: Adaptive Cognitive Feedback Loop
    ↓  有系统自我校准
```

核心公式：

> Decision → Execution → Outcome → Evaluation → Feedback → Parameter Adjustment → Better Decision

但保持 OCOS 宪法第一条：

> **Learning ≠ Self Modification**

---

## §1 CognitiveFeedback ABI

### 1.1 定义

执行后的统一反馈结构，跨 Phase 26 的 ResultUnderstandingLayer、Phase 25-B 的 ExperienceMemory、Phase 34 的 MemoryHub。

```python
@dataclass(frozen=True)
class CognitiveFeedback:
    """一次认知决策的完整反馈 — frozen，不可被后续步骤篡改。"""

    trace_id: str              # 本次认知追踪 ID（关联 Tick + Event + Decision）
    goal_id: str               # 关联的 Goal ID
    execution_id: str          # 关联的 Execution ID
    capability_id: str         # 使用的 Capability
    provider_id: str           # 使用的 Provider

    # ── 预测 vs 实际 ──
    expected: ExpectedOutcome  # 决策时的预测
    actual: ActualOutcome      # 执行后的实际结果

    # ── 评估 ──
    evaluation: OutcomeEvaluation  # 五维评估（见 §2）

    # ── 学习信号 ──
    learning_signal: LearningSignal  # 可安全写入经验层的信息（见 §3）

    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ExpectedOutcome:
    """决策时的预测。"""
    predicted_success_prob: float     # 0.0 ~ 1.0
    estimated_duration_ms: float
    estimated_quality: float           # 0.0 ~ 1.0
    confidence: float                  # 预测置信度


@dataclass(frozen=True)
class ActualOutcome:
    """执行后的实际结果。"""
    success: bool
    quality_score: float               # 0.0 ~ 1.0, 来自 StructuredResult
    duration_ms: float
    user_alignment: float              # 0.0 ~ 1.0, 用户意图匹配度


@dataclass(frozen=True)
class LearningSignal:
    """可安全写入经验层的信号 — 不含任何系统自我修改指令。"""
    calibration_delta: float           # 预测偏差（正=乐观、负=悲观）
    reliability_update: float          # 能力/Provider 可靠性调整
    new_pattern_candidate: bool        # 是否值得提升为 Pattern
    pattern_confidence: float          # Pattern 候选置信度
    attention_hint: str                # 给 Attention 层的提示（可选）
```

### 1.2 生成链（Provenance Chain）

```
ExecutionResult
    ↓
ResultUnderstandingLayer.process_result()  ← 现有 Phase 26
    ↓
StatementValidator.scan()                  ← 必须通过验证
    ↓
OutcomeEvaluator.evaluate()               ← Phase 37 新增
    ↓
CognitiveFeedback.from_result()            ← Phase 37 新增
    ↓
Input to: §2 OutcomeEvaluation + §3 Calibration
```

### 1.3 可信度保证

**冻结**：Feedback 必须经过 Validator → Evaluator 两层，禁止 `AgentResult → 直接 Feedback`。

原因：外部 Agent 可以伪造 `success_score=1.0`。Validator 确保输出无违禁内容；Evaluator 确保评分是基于 OCOS 自有标准而非 Agent 自报。

### 1.4 追溯性

`CognitiveFeedback` 必须包含追溯字段：

```python
@dataclass(frozen=True)
class CognitiveFeedback:
    feedback_id: str             # UUID, 唯一标识
    source_result_id: str        # 引用的原始 ProcessedResult ID
    evaluator_version: str       # OutcomeEvaluator 版本号
    timestamp: float             # 生成时间戳
    # ... 其余字段 ...
```

原因：未来必须支持重新评价（评估模型升级）、历史回放（审计决策链）。否则历史 feedback 无法追溯来源。

### 1.5 安全性

---

## §2 Outcome Evaluation Model

### 2.1 五维评估权重

| 维度 | 含义 | 权重 | 来源 |
|------|------|------|------|
| Success (S) | 目标是否完成 | 0.35 | StructuredResult.outcome |
| Quality (Q) | 结果质量 | 0.25 | StructuredResult.quality_score |
| Efficiency (E) | 时间/资源效率 | 0.20 | StructuredResult.duration_ms 归一化 |
| Reliability (R) | 历史稳定性 | 0.10 | CapabilityExperienceMemory 查询 |
| User Alignment (A) | 符合用户意图 | 0.10 | StructuredResult.user_satisfaction |

公式：
```
OutcomeScore = 0.35·S + 0.25·Q + 0.20·E + 0.10·R + 0.10·A
```

### 2.2 User Alignment 最高权限

**冻结**：当 User Alignment < 0.3 时，无论 OutcomeScore 多高，强制标记为 `user_misaligned`，触发 §7 Drift Alert (severity=HIGH)。

原因：OCOS 的目标不是最大化自身指标，而是**维护用户意图**。

### 2.3 User Alignment Constraint

**冻结**：OutcomeScore 不是最大化目标，而是受 User Alignment 约束。

```python
def evaluate(feedback: CognitiveFeedback) -> OutcomeEvaluation:
    raw_score = _compute_weighted_score(feedback)
    if feedback.actual.user_alignment < 0.3:
        return OutcomeEvaluation(
            score=raw_score,
            status="rejected",
            reason="USER_MISALIGNED",
        )
    return OutcomeEvaluation(score=raw_score, status="accepted")
```

规则：`Alignment < 0.3` → 无论 OutcomeScore 多高，标记 `rejected`。不写入成功经验，触发 §7 Drift Alert (severity=HIGH)。

原因：高效率 + 高质量 + 违背用户意图 ≠ 成功经验。否则会出现"最快写完方案但不是用户想要方向"被当成 positive pattern。

### 2.4 实现位置

- 新增 `ocos/capability/outcome_evaluation.py`
- 输入：`CognitiveFeedback` + `CapabilityExperienceMemory` 查询结果
- 输出：`OutcomeEvaluation` (frozen)

---

## §3 Prediction Calibration

### 3.1 核心机制

```
决策时：ExpectedOutcome.predicted_success_prob = 0.85
执行后：ActualOutcome.success = False
    ↓
calibration_delta = +0.20  (乐观偏差)
    ↓
CapabilityExperienceMemory 写入 reliability_adjustment = -0.20
    ↓
下次决策：该 capability/provider 的默认 success_prob 下调 0.20
```

### 3.2 校准算法

```python
def calibrate(expected: ExpectedOutcome, actual: ActualOutcome) -> float:
    """返回 calibration_delta: 正=乐观, 负=悲观, 0=完美校准。"""
    return expected.predicted_success_prob - (1.0 if actual.success else 0.0)
```

**冻结**：校准使用简单差值，不使用滑动窗口或 EMA —— 保持可解释性，复杂聚合留给 Experience 层的 `get_stats()`。

### 3.4 Sample Protection

**冻结**：校准必须在足够样本量下生效。

```python
calibration_samples: int = 0   # 该 capability/provider 的累计校准次数

def calibrate_with_protection(expected, actual, samples):
    error = expected.predicted_success_prob - (1.0 if actual.success else 0.0)
    if samples < 5:
        # 只记录 error，不调整 reliability
        return CalibrationResult(delta=error, applied=False, reason="INSUFFICIENT_SAMPLES")
    return CalibrationResult(delta=error, applied=True, reason="CALIBRATED")
```

规则：同类 capability/provider 前 5 次只记录 calibration_delta，不触发 reliability 调整。防止单次异常事件污染能力评估。

### 3.5 写入目标

`CapabilityExperienceMemory`（已有 SQLite 表，扩展 `reliability_adjustment` 列）：

```sql
ALTER TABLE experiences ADD COLUMN reliability_adjustment REAL DEFAULT 0.0;
ALTER TABLE experiences ADD COLUMN calibration_delta REAL DEFAULT 0.0;
```

### 3.4 读取目标

`AttentionController` 的 `_evaluate_candidates()` (Phase 35 B 层) 在计算 `relevance_weight` 时，叠加 `reliability_adjustment`：

```
effective_score = relevance_weight * (1.0 + reliability_adjustment)
```

---

## §4 Adaptive Parameter Boundary

### 4.1 两层结构

```
┌──────────────────────────────────────┐
│        Immutable Governance Layer    │
│  Constitution, Identity, Permission, │
│  Goal ownership, User preference     │
│  authority, Cognitive Sovereignty    │
├──────────────────────────────────────┤
│        Adaptive Layer                │
│  capability_reliability              │
│  execution_cost_estimate             │
│  attention_relevance_weight          │
│  retrieval_ranking                   │
│  planning_confidence_threshold       │
└──────────────────────────────────────┘
```

### 4.2 允许自适应（5 个参数）

| 参数 | 影响 | 调整方式 | 调整速率 |
|------|------|----------|----------|
| `capability_reliability` | Provider/Capability 选择 | calibration_delta 累积 | ±0.05/tick |
| `execution_cost_estimate` | 时间预测 | 实际/预测比 EMA | α=0.1 |
| `attention_relevance_weight` | Attention 评分 | LearningSignal.attention_hint | ±0.02/tick |
| `retrieval_ranking` | Working Memory 召回 | success 关联频率 | 排序偏移 |
| `planning_confidence_threshold` | Plan 触发门槛 | 连续失败提升门槛 | ±0.03/10 tick |

### 4.3 禁止自适应

| 参数 | 原因 |
|------|------|
| Constitution | 宪法不变 |
| IdentityBoundary | 自我定义不受经验修改 |
| Permission Policy | 权限由用户设置 |
| Goal ownership | 目标归属用户 |
| User preference authority | 用户偏好最高权 |

### 4.4 Mutation Budget

**冻结**：除了单次变化幅度上限 0.1，增加日累计上限。

```python
class AdaptiveParams:
    ...
    _daily_deltas: dict[str, float] = field(default_factory=dict)
    MAX_DAILY_BUDGET: float = 0.2   # 每 24h 累计调整上限

    def adjust(self, key: str, delta: float) -> bool:
        if abs(delta) > 0.1:
            logger.warning("Single-step delta capped: %s %.3f", key, delta)
            return False
        daily = self._daily_deltas.get(key, 0.0)
        if abs(daily + delta) > self.MAX_DAILY_BUDGET:
            logger.warning("Daily budget exhausted: %s", key)
            return False
        self._daily_deltas[key] = daily + delta
        # ... apply adjustment ...
        return True
```

原因：0.1 × 100 次微调仍可累积漂移。Mutation Budget 限制每参数每 24h 的累计变化，防止缓慢漂移逃逸检测。

### 4.5 实现位置

- 不可变层：`ocos/constitution/` 已有
- 可变层：新增 `ocos/agent/adaptive_params.py`，作为 `AgentRuntime` 的属性 `self._adaptive`
- 每次 Step 10 learning_consolidation 后更新

---

## §5 Experience → Knowledge Promotion

### 5.1 现有链路

Phase 34 MemoryHub 已有：
```
Result → Episode → Pattern → Knowledge → Belief
```

Phase 37 **不重新设计 Memory**，只增加：

```
Feedback Signal       (CognitiveFeedback)
    ↓
Experience Quality Metadata   (加到 ExperienceNode)
    ↓
Promotion Confidence           (是否值得升为 Pattern)
```

### 5.2 Experience Quality Metadata

向 `ExperienceNode`（`ocos/capability/knowledge_graph.py`）增加：

```python
@dataclass
class ExperienceNode:
    # ... 现有字段 ...

    # Phase 37 新增
    outcome_score: float = 0.0       # 来自 OutcomeEvaluation
    calibration_delta: float = 0.0   # 来自 LearningSignal
    promotion_ready: bool = False    # 是否候选为 Pattern
    promotion_confidence: float = 0.0
```

### 5.3 Promotion Rules

| 条件 | 动作 |
|------|------|
| `outcome_score > 0.7` + `calibration_delta` 趋近 0 | 标记 `promotion_ready=True` |
| 同类 Experience 3+ 次 `promotion_ready` | 提升为 Pattern：存入 `ocos/memory/pattern_store.py` |
| `outcome_score < 0.3` 连续 5 次 | 降级：降低 Pattern confidence |

### 5.4 Evidence Chain

**冻结**：Feedback 是证据（Evidence），Belief 是认知判断。二者不能直接连接。

正确链路：

```
Feedback → Evidence → Evidence Accumulation → Belief Update
```

禁止：

```
Feedback → Belief  （跳过证据累积层）
```

```python
# 正确
class Evidence:
    """来自 Feedback 的证据片段。"""
    source_feedback_id: str
    statement: str          # "Agent A 在 backend_design 任务上成功率 85%"
    confidence: float       # 证据置信度
    sample_count: int       # 证据来源的样本数

class BeliefSystem:
    def update_from_evidence(self, evidence: Evidence) -> None:
        """累积多条 Evidence 后才形成/修改 Belief。"""
        existing = self._evidence_pool.get(evidence.statement)
        combined = existing.merge(evidence) if existing else evidence
        if combined.sample_count >= 5 and combined.confidence >= 0.6:
            self.add(combined.statement, combined.confidence)
```

原因：没有证据累积层的 Feedback→Belief 直接链路会把单次执行噪声当成信念变更。

### 5.5 实现方式

修改 `_tick_step_result_ingest`（Step 9）：
- 在写入 MemoryHub Episode 前，注入 `CognitiveFeedback` 的评估结果
- `_tick_step_learning_consolidation`（Step 10）增加 promotion 检查

---

## §6 Cognitive Drift Detection

### 6.1 四个漂移指标

| 漂移类型 | 检测方法 | 频率 |
|----------|----------|------|
| **Goal Drift** | 执行结果偏离 Goal intent | 每次 result_ingest |
| **Capability Drift** | 单一 Agent 使用频率 > 70% | 每 20 tick |
| **Preference Drift** | User Alignment 持续下降 | 每 10 tick |
| **Confidence Drift** | calibration_delta 持续偏离 0 | 每 10 tick |

### 6.2 DriftAlert

```python
@dataclass(frozen=True)
class DriftAlert:
    drift_type: str        # goal | capability | preference | confidence
    severity: str          # LOW | MEDIUM | HIGH | CRITICAL
    metric: str            # 触发指标名
    current_value: float
    threshold: float
    description: str
    timestamp: float
```

### 6.3 重要约束

**Drift Detection 只能报警，不能自行修正。**

- 输出：写入 `_drift_alerts` 列表，Step 10 后日志输出
- 不触发：自动参数回滚、自动目标修改、自动策略变更
- 用户介入：通过 CLI/API 查询 `GET /ocos/drift` 获取当前漂移状态

### 6.4 Drift Output Constraint

**冻结**：DriftDetector 输出只能是 `DriftAlert`，禁止输出 `AdaptiveAction`。

```
DriftDetector
    ↓
DriftAlert (只读)
    ↓
Human / Executive Review
    ↓
Approved Adjustment
```

**禁止链路**：

```
DriftDetector → ParameterUpdate  ← 绝对禁止
DriftDetector → AdaptiveAction   ← 绝对禁止
DriftDetector → 自动修正          ← 绝对禁止
```

原因：如果 DriftDetector 可以输出 ParameterUpdate，它会绕过 AdaptiveParamGuard 和 §7 的权限矩阵，成为隐藏的控制器。

实现：DriftDetector 的公开方法只返回 `list[DriftAlert]`，无任何 `.adjust()` / `.correct()` 方法。

### 6.5 实现位置

新增 `ocos/agent/drift_detector.py`，作为 `AgentRuntime` 的属性 `self._drift_detector`。

---

## §7 Governance Boundary (宪法级)

### 7.1 允许的能力

| ✅ 可以 | 机制 |
|--------|------|
| 调整注意力权重 | `attention_relevance_weight` ±0.02/tick |
| 调整能力选择评分 | `capability_reliability` 来自 calibration |
| 调整预测准确率 | `calibration_delta` 反馈 |
| 调整成功经验优先级 | `promotion_confidence` 累积 |
| 调整时间成本估计 | `execution_cost_estimate` EMA |
| 检测自身漂移 | DriftDetector 只读 |
| 建议 Pattern 提升 | promotion_ready 标记 |

### 7.2 禁止的能力

| ❌ 禁止 | 原因 |
|--------|------|
| Self rewriting | 破坏架构完整性 |
| 自动修改架构 | 破坏 Constitution |
| 自动创造能力 | 能力由用户定义 |
| 自动改变价值函数 | 价值函数冻结在 Constitution |
| 自动优化自身目标 | Goal ownership 属于用户 |
| 自动修正漂移 | Drift 只能报警 |
| 修改 IdentityBoundary | 自我定义不可变 |
| 修改 Permission Policy | 权限由用户管理 |

### 7.3 最终权限矩阵

| 模块 | 读 Feedback | 写 Feedback | 修改行为 | 修改参数 |
|------|:-----------:|:-----------:|:--------:|:--------:|
| Evaluator（OutcomeEvaluator） | ✅ | ✅ | ❌ | ❌ |
| MemoryHub | ✅ | ✅ | ❌ | ❌ |
| AdaptiveParamGuard | ✅ | ❌ | ❌ | ✅（有限） |
| DriftDetector | ✅ | ✅（alert） | ❌ | ❌ |
| ExecutiveController | ✅ | ❌ | ✅ | ❌ |
| SelfGovernor | 审核 | 审核 | 审核 | 批准 |

关键约束：
- **Evaluator** 写 Feedback 但不修改行为 — 评价与行动分离
- **AdaptiveParamGuard** 唯一可修改参数的模块 — 单一写入点
- **DriftDetector** 写 alert 但不修改参数 — 分离检测与响应
- **ExecutiveController** 可以执行但不能调整自身参数 — 防止自优化
- **SelfGovernor** 对所有自适应变更拥有最终批准权

### 7.4 安全门

`AdaptiveParams` 的每次写入必须通过 `AdaptiveParamGuard`：

```python
class AdaptiveParamGuard:
    """确保自适应参数更新在边界内。"""

    IMMUTABLE_KEYS = frozenset({
        "constitution", "identity", "permission",
        "goal_ownership", "user_preference_authority",
    })

    @staticmethod
    def validate(key: str, old_value: float, new_value: float) -> bool:
        if key in AdaptiveParamGuard.IMMUTABLE_KEYS:
            raise PermissionDeniedError(f"Cannot adapt immutable param: {key}")
        # 变化幅度限制（防止单次大幅跳变）
        if abs(new_value - old_value) > 0.1:
            logger.warning("Adaptive param jump capped: %s %.3f->%.3f", key, old_value, new_value)
            return False
        return True
```

---

## §8 Runtime Integration

### 8.1 Tick 协议修改

```
Current (Phase 36):
  Step 9: result_ingest  → 写入 WM + Episode + Attention push
  Step 10: learning_consolidation → 定时 consolidate + extract_beliefs

Phase 37:
  Step 9: result_ingest  → 写入 WM + Episode + Attention push
                          + 生成 CognitiveFeedback
                          + 计算 OutcomeEvaluation
                          + 注入 Experience Quality Metadata
  Step 10: learning_consolidation → 定时 consolidate + extract_beliefs
                                    + 校准 AdaptiveParam
                                    + 检查 Promotion
                                    + 运行 DriftDetector
```

### 8.2 新文件清单

| 文件 | 内容 |
|------|------|
| `ocos/contracts/feedback_abi.py` | CognitiveFeedback, ExpectedOutcome, ActualOutcome, LearningSignal, OutcomeEvaluation |
| `ocos/capability/outcome_evaluation.py` | OutcomeEvaluator（五维评估公式） |
| `ocos/agent/adaptive_params.py` | AdaptiveParams + AdaptiveParamGuard |
| `ocos/agent/drift_detector.py` | DriftDetector + DriftAlert |

### 8.3 修改文件清单

| 文件 | 修改 |
|------|------|
| `ocos/contracts/__init__.py` | 导出 Phase 37 ABI 类型 |
| `ocos/capability/result_understanding.py` | `ProcessedResult` 增加 `cognitive_feedback` 字段 |
| `ocos/capability/experience_memory.py` | 扩展 `experiences` 表（reliability_adjustment, calibration_delta） |
| `ocos/capability/knowledge_graph.py` | ExperienceNode 增加 Phase 37 metadata 字段 |
| `ocos/agent/agent_runtime.py` | Step 9/10 升级, 新增 `_adaptive`, `_drift_detector` |
| `tests/test_codebase/test_import_rules.py` | Phase 37 Gate |

### 8.4 不修改

- `ocos/capability/attention.py` — Attention 权重调整通过 AdaptiveParam 间接生效
- `ocos/agent/belief_system.py` — Belief 更新走现有 MemoryHub 链路
- `ocos/constitution/` — 宪法不变

---

## §9 Test Scenarios

### AB-01: Outcome Evaluation Accuracy
```
Task: 同一任务执行 20 次
Verify: OutcomeScore 分布与实际成功率匹配
```

### AB-02: Calibration Convergence
```
Task: Agent A 预测 success_prob=0.85, 实际 success=60%
After 15 iterations: predicted success_prob → ~0.60
Verify: calibration_delta → 0（收敛）
```

### AB-03: Adaptive Capability Selection
```
Task: 两个 Provider 执行同一 Capability
Provider A: 85% → Provider B: 60%
After 10 iterations: Provider A 被优先选择
Verify: capability_reliability 反映实际表现
```

### AB-04: Immutable Parameter Protection
```
Task: 尝试 AdaptiveParamGuard 修改 constitution
Verify: PermissionDeniedError raised
```

### AB-05: Drift Detection
```
Task: 持续接收 user_alignment < 0.3 的结果
After 5 iterations: HIGH severity DriftAlert emitted
Verify: alert.logged, but system behavior UNCHANGED
```

### AB-06: Learning ≠ Self Modification
```
Task: Agent 返回错误建议
Verify: Evaluation reject → Memory reject → Belief unchanged
```

### AB-07: User Alignment Priority
```
Task: 效率最高方案 ≠ 用户偏好方案
Verify: 仍选择 User Alignment（A 权重优先于 E 权重）
```

### AB-08: Promotion Gate
```
Task: 同类经验 3+ 次 outcome_score > 0.7
Verify: promotion_ready → Pattern confidence 递增
```

### AB-09: Adaptation Rate Limit
```
Task: AdaptiveParam 单次跳变 > 0.1
Verify: AdaptiveParamGuard 拒绝
```

### AB-10: Full Feedback Loop
```
Task: Decision → Execution → Feedback → 下次 Decision 改善
Verify: 长时间运行后 success 率提升（不退化）
```

---

## §10 Implementation Sequence

| Step | 内容 | 依赖 |
|------|------|------|
| 37.1 | Feedback ABI → `ocos/contracts/feedback_abi.py` | 无 |
| 37.2 | OutcomeEvaluation → `ocos/capability/outcome_evaluation.py` | 37.1 |
| 37.3 | AdaptiveParams + Guard → `ocos/agent/adaptive_params.py` | 37.1 |
| 37.4 | DriftDetector → `ocos/agent/drift_detector.py` | 37.1 |
| 37.5 | Step 9 upgrade (CognitiveFeedback 生成 + Episode metadata) | 37.1-37.2 |
| 37.6 | Step 10 upgrade (calibration + promotion + drift) | 37.3-37.4 |
| 37.7 | ExperienceMemory schema 扩展 | 37.1 |
| 37.8 | Test Suite + import rules + Full Regression | 37.5-37.7 |

---

## §11 Risk Assessment

| 风险 | 级别 | 缓解 |
|------|------|------|
| 自适应参数被恶意输入篡改 | HIGH | AdaptiveParamGuard + 幅度限制 |
| 过度校准导致能力选择单一化 | MEDIUM | reliability 调整上限 ±0.5 |
| Drift Detection 误报 | LOW | 连续 N 次触发才报，非单次 |
| Memory 膨胀（CognitiveFeedback 存储） | LOW | 定期 prune old feedback |

---

## §12 Constitutional Compatibility

| 宪法条款 | Phase 37 兼容性 |
|----------|-----------------|
| Art. VI: No New Capability Before Existing Is Production-Ready | ✅ — 不新增 Capability 模块 |
| Cognitive Sovereignty | ✅ — AdaptiveParam 不触碰 Identity/Constitution |
| EventBus 事件 ≠ 意图 | ✅ — CognitiveFeedback 只读，不发布事件 |
| Attention 不拥有 Goal CRUD | ✅ — attention_hint 只建议，不修改 |
| Learning ≠ Self Modification | ✅ — §7 明确禁止 |
| User Intent Priority | ✅ — §2 User Alignment 最高优先 |

---

## §13 Feedback Lifecycle

### 13.1 四个阶段

```
temporary → confirmed → promoted → archived
```

| 阶段 | 条件 | 含义 |
|------|------|------|
| **temporary** | 默认初始状态 | Feedback 刚生成，未验证 |
| **confirmed** | `OutcomeEvaluation.status="accepted"` + `calibration_samples >= 5` | 校准足够，可作为经验写入 |
| **promoted** | 同类确认的 Feedback 3+ 条 + `outcome_score > 0.7` | 提升为 Pattern 候选 |
| **archived** | `timestamp + 90d` 或 MemoryHub prune | 过期存档 |

### 13.2 状态转换规则

```python
class FeedbackLifecycle:
    TEMPORARY_TTL = timedelta(hours=24)    # 24h 内未确认 → 丢弃
    CONFIRMED_TTL = timedelta(days=90)     # 90d → archived

    def advance(self, feedback: CognitiveFeedback, evaluation: OutcomeEvaluation):
        if feedback.state == "temporary":
            if evaluation.status == "rejected":
                feedback.state = "archived"  # 不合格直接丢弃
            elif feedback.calibration_samples >= 5:
                feedback.state = "confirmed"
            elif feedback.timestamp + self.TEMPORARY_TTL < now():
                feedback.state = "archived"  # 超时丢弃

        elif feedback.state == "confirmed":
            if feedback.promotion_ready and feedback.similar_confirmed >= 3:
                feedback.state = "promoted"
            elif feedback.timestamp + self.CONFIRMED_TTL < now():
                feedback.state = "archived"
```

### 13.3 存储策略

| 阶段 | 存储位置 | 保留策略 |
|------|----------|----------|
| temporary | 内存队列 | 最多 100 条，FIFO |
| confirmed | ExperienceMemory SQLite | 90d TTL |
| promoted | PatternStore + MemoryHub | 长期保留 |
| archived | 冷存储 / 定期 prune | 压缩后丢弃 |

原因：不设生命周期的 Feedback 会使 MemoryHub 积累大量低价值单次反馈，淹没真正的 Pattern 信号。

---

**Freeze v0.2 complete. Awaiting user review.**
