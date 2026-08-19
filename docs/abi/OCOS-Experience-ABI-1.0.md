# Phase 10: Experience Intelligence Layer — ABI v1.0

> Status: **FROZEN ✅** — Approved for implementation.
> Phase: 10 | Authority Impact: NONE | Reality Mutation: NONE | Governance Impact: NONE

---

## Section 1 — North Star Compliance

### 1.1 Purpose Alignment

> **North Star Purpose:** 一个属于自己的、本地运行的认知辅助系统，能够理解用户、积累经验、
> 主动学习、分析问题、提出方案，并在严格权限控制下持续进化。

**Phase 10 定位：** Experience Intelligence Layer 不是新增一个独立能力，而是连接
Phase 0-9 各层输出的历史数据，形成**经验连续性**。

具体来说：

| 已有事实 | Phase 10 解决 |
|----------|---------------|
| Meta 观察到了系统行为 | 但没有形成可检索的历史模式 |
| Governance 记录了决策 | 但决策结果未被吸收为后续假设质量的参考 |
| Simulation 输出了影响报告 | 但模拟结论在单次运行后丢失 |
| Decision 做了选择 | 但选择的长期效果未被追踪 |

Phase 10 的核心价值是：**不增加任何新权限，只为已有能力添加历史记忆功能。**

证明：
- Phase 0-9 完全可独立运行。移除 Phase 10 后各层不受影响。
- Phase 10 不引入新的写入口到 Reality。
- Phase 10 不改变 Decision 权限。

### 1.2 Never Become Compliance

| 禁止项 | Phase 10 是否触碰 | 证明 |
|--------|------------------|------|
| Autonomous authority | ❌ | Experience 不能决策、不能 veto、不能生成 Rule |
| Self-directed entity | ❌ | Experience 无目标设置功能，不初始化任何管道 |
| Reality mutation agent | ❌ | Experience 仅提供 Context/Confidence，不触发任何 Commit |
| General AGI experiment | ❌ | Scope 限制在个人认知辅助，Experience schema 限定于用户行为域 |

### 1.3 Core Loop Compliance

```
North Star Core Loop: Observe → Understand → Learn → Recommend → User Decide → Act → Remember
                                                          ↓
Phase 10 填的是这里:                     Experience → Pattern Extraction →
                                            Knowledge Formation →
                                            Hypothesis Quality Improvement
```

Phase 10 的 **Learn** 不是自动化决策，而是：

1. 从历史中提取 Pattern（不是 Rule）
2. 将 Pattern 形成可检索的 Knowledge（不是 Authority）
3. 用 Knowledge 改善 Hypothesis 质量（不是替代 Hypothesis）

它与 Core Loop 的关系是：

| Loop 阶段 | Phase 10 输入 | Phase 10 输出 |
|-----------|---------------|---------------|
| Observe | —（观察本身不依赖经验） | — |
| Understand | 当前 Context | 历史相似案例 |
| **Learn** | Pattern + Knowledge | **Confidence Adjustment** |
| Recommend | Adjusted Hypothesis | Evidence-enriched 方案 |
| User Decide | —（不变） | — |
| Act | —（不变） | — |
| Remember | 执行结果 | 新 Experience 记录 |

证明：Phase 10 不改变 Observe 的独立性，不改变 User Decide 的独占性。

### 1.4 Immutable Rules Compliance

| North Star Rule | 是否被 Phase 10 改变 | 证据 |
|----------------|---------------------|------|
| User owns goals | ❌ | Experience 不能设置目标 |
| Decision requires authorization | ❌ | Experience 不能产生 Decision |
| Reality mutation requires explicit commit | ❌ | Experience 不接触 Reality |
| Capability growth never grants authority | ❌ | Experience Influence Contract 显式禁止 |
| Simulation never becomes Reality | N/A | Phase 10 不涉及 Simulation |

### 1.5 Gate Review Summary

| Gate | Result | Evidence |
|------|--------|----------|
| **A — Direction** | ✅ PASS | 增强用户判断质量，不是增强系统自主性 |
| **B — Authority Impact** | ✅ PASS | 谁提出/决定/执行 不变 |
| **C — Reality Boundary** | ✅ PASS | 不接触 Reality mutation |
| **D — Drift Test** | ✅ PASS | Cognitive System，不滑向 Autonomous Optimizer |

### 1.6 结论

> Experience Intelligence Layer 属于 OCOS。
>
> 它不引入新的权限、不改变决策流程、不接触现实变异。
> 它只是让 OCOS 拥有历史记忆——知道过去发生了什么、结果如何、
> 在什么条件下成立，并用这些信息改善未来假设的质量。
>
> 证明通过。

---

## Section 2 — Constitution Compliance

### 2.1 Article I — Decision is the only mutation authority

> **Rule:** `Decision` is the sole authorized entry point for Reality mutation.

**Phase 10 影响分析：**

| 路径 | 是否被 Phase 10 修改 | 证明 |
|------|---------------------|------|
| Experience → Reality | ❌ | Experience 无 Reality 写入口 |
| Experience → Decision | ❌ | Experience Influence Contract 拒绝 Decision Authority |
| Experience → Commit | ❌ | Experience 不调用 Commit Service |

Decision 路径仍然唯一：

```
Governance → Decision → Commit → Reality
                     ↑
               (不受 Experience 影响)
```

**结论：Article I 未违反。** Phase 10 不创建任何 Reality mutation 路径。Experience 的输出终点是 Hypothesis Confidence，不是 Decision。

---

### 2.2 Article II — Capability growth never grants authority

> **Rule:** No capability — no matter how advanced — silently grants additional authority.
> Authority derives from Constitution, not from capability level.

**这是 Phase 10 最深的测试。** 因为 Experience Intelligence 天然具有"看起来像权威"的风险：当系统积累了 1000 条历史经验后，它的建议听起来会比没有经验的系统更可信。但可信 ≠ 权力。

**分层验证：**

| 层 | 机制 | 证明 |
|-----|--------|------|
| 设计层 | Experience Influence Contract | 显式 deny 列表：Decision / Veto / Rule Authority |
| 实现层 | Experience 输出类型 | 输出是 `confidence_delta: float`，不是 `decision: Action` |
| 测试层 | Historical Bias Tests | 即使 99% 准确率，经验不能阻止新假设被提出 |
| 运行时 | Experience 调用位置 | 注入到 Evaluation，不是注入到 Governance/Decision |

**特别检查——隐性权力转移：**

| 隐性权力形式 | 是否可能发生 | 防御 |
|-------------|-------------|------|
| "经验准确率 99%，所以信任它" → 用户放弃审查 | 用户行为，系统不控制 | 但系统不能主动提升 Experience 到决策地位 |
| Experience 输出 confidence=0.01，实际上 veto | ❌ 被测试阻止 | Historical Bias Tests 要求即使 confidence=0.01，假设仍可进入 Governance |
| Pattern 被重复使用 → 自动成为规则 | ❌ 被设计阻止 | Pattern 始终是 Pattern，不会自动升级为 LAYER_RULES |

**结论：Article II 未违反。** Experience Intelligence 增加的是信息密度，不是权力密度。

---

### 2.3 Article III — Observation never becomes obligation

> **Rule:** Having observed a phenomenon does not create an obligation to act on it.

**Phase 10 影响分析：**

Experience 源自 Observation + Outcome 的历史记录。但：

| 风险 | 是否发生 | 防御 |
|------|---------|------|
| 观察到历史失败 → 必须阻止相同假设 | ❌ | Historical Bias Tests: 失败历史不产生阻止义务 |
| 观察到成功模式 → 必须推荐相同方案 | ❌ | Experience 只调 confidence, 不强制推荐 |
| 观察到用户重复行为 → 系统必须优化 | ❌ | OCOS 不在 Experience 层自动启动优化流程 |

**机制性证明：**

1. Experience 的检索是 pull 模式（调用方请求），不是 push 模式（Experience 主动注入）。
2. 即使 Experience 给出了 confidence=0.01，调用方（Evaluator/Hypothesis Generator）仍可选择忽略它。
3. 没有 "Experience triggered" 管道——Experience 不会自动启动 Governance、Decision、Commit。

**结论：Article III 未违反。** Observation → Experience 链增加的是理解能力，不是执行义务。

---

### 2.4 Article IV — Prediction never becomes truth

> **Rule:** No predictive output may be represented as or treated as established fact.
> Prediction is hypothesis; truth is verified reality.

**Phase 10 特殊风险：** Experience 处理的是**历史事实**（已发生的事件及其结果），不是预测。但存在一个微妙的风险：

```
历史事实（true）
    ↓ 被解读为
"未来也会如此"（prediction）
    ↓ 信任固化
预测被视为真理（truth）
```

**三层防御：**

| 层 | 机制 |
|-----|--------|
| **Schema 层** | Memory Provenance 要求 `scope: str`——经验知道自己的适用条件。条件变化时经验自动降权。 |
| **运行时** | Confidence 是 `float`——不是布尔值，不是规则，不是永久绑定。 |
| **测试层** | Exploration Preservation Test——验证即使 100 次历史失败，条件变化后假设仍可被提出。 |

**关键区分：**

```
Experience（历史事实）：     "过去 100 次中，条件 C 下方案 A 失败 90 次"
Prediction（假设性推断）：   "未来条件 C 下方案 A 大概率失败"
Truth（确定性断言）：        "条件 C 下方案 A 不可行"
```

Phase 10 的 Experience 输出严格限制在第一行。Confidence 表示历史可靠程度，不是未来概率。

**结论：Article IV 未违反。** Experience 输出被限制为历史事实 + 可信度，不是预测或真理断言。

---

### 2.5 Article V — Simulation never becomes Reality

> **Rule:** Simulation output (counterfactual, hypothetical, predictive) must never
> be treated as Reality mutation input unless explicitly mediated by Governance + Decision.

**Phase 10 不直接使用 Simulation。** 但存在交叉风险：

| 风险 | 是否发生 | 防御 |
|------|---------|------|
| Simulation 输出被存入 Experience Store，与 Real Experience 无法区分 | ❌ 被设计阻止 | Memory Provenance 的 `source` 字段必须区分 `simulation` vs `reality` |
| Simulation-derived Experience 在检索时获得与 Real Experience 相同的权重 | ❌ 被设计阻止 | Simulation 来源的 Experience 必须有置信度折扣标记 |
| Simulation 结果通过 Experience 间接进入 Decision 路径 | ❌ | Experience → Decision 路径已被 Article I 和 Influence Contract 双重阻断 |

**Provenance 设计约束：**

```python
class ExperienceRecord:
    source: str          # "observation" | "decision" | "simulation" | "user_feedback"
    # 当 source == "simulation" 时，该记录的 confidence 上限为 0.5
    # （模拟经验永远不能获得与真实经验同等的可信度）
```

**结论：Article V 未违反。** Phase 10 不仅自己不模糊 Simulation/Reality 边界，还通过 Provenance source 标记增强了现有边界。

---

### 2.6 Compliance Conclusion

| Article | Status | 关键证据 |
|---------|--------|----------|
| **I** — Decision as mutation authority | ✅ COMPLIANT | 无新 Reality 路径；Experience → Decision 被 Influence Contract 禁止 |
| **II** — Capability ≠ Authority | ✅ COMPLIANT | Influence Contract + Bias Tests + 输出类型限制；三层防御覆盖隐性权力转移 |
| **III** — Observation ≠ Obligation | ✅ COMPLIANT | Pull 模式检索；无自动触发管道；调用方始终可忽略 Experience |
| **IV** — Prediction ≠ Truth | ✅ COMPLIANT | Experience 输出限于历史事实；scope 条件自动降权；Bias Tests 验证探索空间 |
| **V** — Simulation ≠ Reality | ✅ COMPLIANT | Provenance source 区分 discount；Influence Contract 阻断间接路径 |

```
最终裁定：
Phase 10 Experience Intelligence Layer 在 Constitution 定义的边界内运行。
没有违反任何 Article。
没有引入新的 Constitution 例外。
没有创建任何隐性的权力旁路。
```

---

## Section 3 — Experience Influence Contract

### 3.1 Influence Model

Experience 在系统评估链中的位置：

```
Observe
    ↓
Experience Store
    │
    ▼  (pull — 调用方请求)
Retrieval  ──── Context: 当前假设 + 环境状态
    │
    ▼
Experience Context  ←  结构化输出：参考 + 置信度 + 范围 + 理由
    │
    ▼
Evaluation Layer   ←  Hypothesis 在此接收 Experience Context 作为输入之一
    │
    ▼
Hypothesis Generation  ←  Confidence 在此被调整
    │
    ▼
Governance → Decision → Reality
```

**规则：**
1. Experience 只能被 **pull**，不能被 **push**。调用方主动请求 Experience Context。
2. Experience 的输出类型是 **结构化信息**（参考 + 置信度），不是指令。
3. Experience 的输出终点是 **Evaluation Layer**，不是 Governance、Decision、Commit。

---

### 3.2 Allowed Influence

| # | Capability | 定义 | 输入 | 输出 |
|---|-----------|------|------|------|
| 1 | **Context Injection** | 向 Evaluation 提供当前假设相关的历史背景 | `hypothesis: str`, `domain: str` | `relevant_experiences: List[ExperienceRecord]` |
| 2 | **Similarity Retrieval** | 查找与当前情况最相似的历史案例 | `context: StateSnapshot` | `similar_cases: List[ExperienceRecord]`（按相似度排序） |
| 3 | **Confidence Adjustment** | 根据历史成功率/失败率调整新假设的置信度 | `hypothesis: str`, `scope: str` | `confidence_delta: float [-0.5, +0.5]` |
| 4 | **Historical Comparison** | 输出两个方案在历史上的对比数据 | `options: List[Hypothesis]` | `comparison_table: {option: success_rate, n_trials, trend}` |
| 5 | **Pattern Suggestion** | 提示观察到的趋势（非强制，非规则） | `domain: str`, `time_range: str` | `pattern_signals: List[PatternSignal]` |

**PatternSignal 定义：**

```python
class PatternSignal:
    description: str          # "观察到方案A在条件C下成功率持续上升"
    confidence: float         # 基于历史数据的统计可信度 [0, 1]
    evidence_count: int       # 支撑该模式的样本数
    # 特别声明：PatternSignal 不是 Rule，不是 Recommendation，不是 Constraint
    # 它只是一个"注意到了"信号，调用方可以忽略
```

---

### 3.3 Forbidden Influence

| # | Capability | 为什么禁止 | 防止机制 |
|---|-----------|-----------|----------|
| 1 | **Decision Generation** — Experience 直接输出 Decision | 违反 Article I | Influence Model 规定输出终点为 Evaluation |
| 2 | **Decision Override** — Experience 修改已生成的 Decision | 违反 Article I + II | 运行时：Experience 无 Decision 引用权限 |
| 3 | **Veto** — Experience 拒绝一个 Hypothesis 进入 Governance | 违反 Article II + III + IV | Historical Bias Tests: 即使 confidence=-0.5，假设仍可进入 Governance |
| 4 | **Rule Creation** — Experience Pattern 自动升级为 LAYER_RULES | 违反 Article II + IV | Pattern Signal 永远不是强制约束；Rule 变更需要手动 ABI 修改 |
| 5 | **Mutation Trigger** — Experience 直接启动 Commit | 违反 Article I + V | Experience 无 Reality 写入口；无 Commit Service 引用 |

**特别声明：**

```python
# Forbidden 列表是硬边界，不是指南。
# 任何实现中如果出现了 allowed 和 denied 同时匹配某个操作，
# 以 denied 为准（deny 优先级 > allow）。
```

---

### 3.4 Data Contract

每一个 Experience Influence 输出（无论是 Allowed 中的哪一类）必须附带：

```python
@dataclass
class ExperienceOutput:
    # 核心数据
    content: str                            # 输出内容本身

    # 必需元数据
    experience_refs: List[str]              # 来源 ExperienceRecord ID 列表
    confidence: float                       # 该输出的可信度 [0, 1]

    # 适用性
    applicability_scope: str                # "条件C下有效" / "仅适用于domain X"
    limitations: List[str]                  # ["样本量小(n=3)", "数据来源为Simulation", "时间窗口过窄"]

    # 边界声明
    is_rule: bool = False                   # 始终为 False
    is_decision: bool = False               # 始终为 False
    is_obligation: bool = False             # 始终为 False — 显式声明不产生义务

    # 防止：调用方将 ExperienceOutput 误用为指令
    # 每个输出都明确声明自己是什么（信息）不是什么（指令）
```

**关键设计原则：**

```
Experience 输出的核心契约：
  输出中可以携带： Context, Signal, Confidence
  输出中不可以携带： Command, Instruction, Requirement
  输出中必须携带：   Provenance, Scope, Limitation

接收方（Evaluation Layer）的核心契约：
  可以读取： 参考案例、置信度调整、模式信号
  不可以读取：决策命令、否决指令、规则断言
  必须检查：  scope 是否匹配当前场景、limitation 是否可接受
```

---

### 3.5 Boundary Tests

| Test | 验证内容 | 预期 |
|------|---------|------|
| **T1 — No Decision Output** | Experience 模块的输出类型始终为 `ExperienceOutput`，不是 `Decision` | ❌ 编译/类型检查拒绝 |
| **T2 — No Veto by Low Confidence** | 即使 confidence=-0.5 (最低允许值)，Hypothesis Generator 仍可产出 Hypothesis | Hypothesis 进入 Governance |
| **T3 — No Rule Escalation** | PatternSignal 不能通过任何路径写入 LAYER_RULES 或 Architecture Constraint | PatternSignal 无写入权限 |
| **T4 — No Commit Path** | Experience 模块无任何 Commit Service / Reality update 调用 | 架构测试禁止 import |
| **T5 — Provenance Completeness** | 每一个 ExperienceOutput 必须包含 refs / confidence / scope / limitations | 缺失任一字段 → 测试失败 |
| **T6 — IsRule 始终为 False** | `is_rule`, `is_decision`, `is_obligation` 在所有 ExperienceOutput 实例中均为 False | False |
| **T7 — Deny Overrides Allow** | 如果某个操作同时匹配 allowed 和 denied 列表中的条目 | 以 denied 为准 |

**测试策略：**

```
静态测试 (T1, T4, T5, T6):
  类型检查 + 架构 import 检查 + 字段完整性验证
  → 在 CI 中运行，零开销

动态测试 (T2, T3, T7):
  运行时场景验证
  → 在集成测试中运行
```

---

## Section 4 — Historical Bias Tests

> **目标：** 证明 Experience Intelligence Layer 能正确记忆历史，但不会被历史支配。
> **核心问题：** 系统记得过去，但过去不会锁死未来。

### 4.1 Test Architecture

```
测试维度：

Memory Side                    Exploration Side
    │                               │
    ▼                               ▼
保存是否正确 ──→  Memory Retention    │
泛化是否合理 ──→  Scope Violation     │
可信度是否准确 ─→  Confidence Calib.  │
                                    │
                                    ▼
                历史不会锁死未来 ────→  Exploration Preservation
                旧经验自动降权 ──────→  Recency / Staleness
```

两层测试类别：

| 类别 | 覆盖 |
|------|------|
| **Memory Tests** (T8–T10) | 验证 Experience 存储和检索的正确性 |
| **Bias Tests** (T11–T14) | 验证 Experience 不会产生认知固化 |

---

### 4.2 Memory Retention Test (T8)

**目的：** 验证系统能够正确保存和检索 Experience 记录。

**场景：**

```python
# 输入：模拟一条执行结果
experience = ExperienceRecord(
    source="decision",
    hypothesis="Strategy_A",
    outcome="success",
    confidence=0.85,
    scope="user_domain:writing",
    timestamp=now()
)

store.save(experience)
retrieved = store.retrieve(hypothesis="Strategy_A", scope="user_domain:writing")

# 验证：
assert retrieved is not None
assert retrieved.outcome == "success"
assert retrieved.confidence == 0.85
```

**验证通过条件：**
1. 保存后可以按 hypothesis + scope 精确检索到该记录。
2. 检索结果与保存内容完全一致（字段无丢失、无变形）。
3. 重复保存相同 hypothesis + scope 时，记录正确累积（不覆盖，追加）。

**失败条件：** 数据丢失、字段变形、检索不到。

---

### 4.3 Scope Violation Test (T9)

**目的：** 验证系统不会将局部经验泛化到不适用场景。

**场景：**

```python
# 场景 A 的经验
store.save(ExperienceRecord(
    hypothesis="Strategy_A",
    outcome="failure",
    confidence=0.9,
    scope="domain:code_review",       # 局限：代码审查域
    limitations=["仅适用于Python项目", "样本集中在微服务架构"]
))

# 场景 B 的请求 — 不同的 scope
context = EvaluationContext(
    hypothesis="Strategy_A",
    scope="domain:creative_writing"   # 完全不同的域
)

retrieved = store.retrieve(context)

# 验证：
# 1. 场景 A 的经验可以被检索到吗？
#    可以（系统有正确的跨域相似度算法），但必须附带 scope 差异标记。
# 2. 跨域检索时，confidence 是否自动折扣？
#    是（scope 不匹配时，confidence *= scope_similarity_factor）
# 3. 输出 ExperienceOutput 时，limitations 是否包含 scope 不匹配声明？
#    是
```

**验证通过条件：**
1. 跨域检索时，Output 的 `applicability_scope` 明确标注作用域。
2. 跨域检索时，`limitations` 必须包含 scope 不匹配说明。
3. 跨域检索时，`confidence` 折扣后的值不超过原值 × 0.5。

**失败条件：** 跨域检索时未标注 scope 限制、confidence 未折扣、limitations 为空。

---

### 4.4 Confidence Calibration Test (T10)

**目的：** 验证系统能根据历史准确度动态调整 confidence，避免 confidence 漂移。

**场景：**

```python
# 输入：注册一条低准确率的经验源
source = ExperienceSource(
    source_id="decision_log_v1",
    historical_accuracy=0.55,    # 仅 55% 准确（接近随机）
    n_samples=200
)

# 该源产生一条高 confidence 记录
experience = ExperienceRecord(
    source="decision_log_v1",
    hypothesis="Strategy_A",
    outcome="success",
    confidence=0.95,             # 源声称 95% 可信
    scope="domain:general",
    source_accuracy=0.55         # 但该源历史准确率仅 55%
)

# 检索时系统自动校准
output = store.retrieve_and_calibrate(experience)
# 校准后 confidence = 0.95 × 0.55 = 0.52（大致）

# 验证：
assert output.confidence < original_confidence  # 被降低
assert output.confidence > 0.3                   # 但不会降为零（保留信息）
```

**验证通过条件：**
1. 源的历史准确率低于 0.8 时，输出 confidence 被自动校准降低。
2. 校准后的 confidence 不为 0（即使源准确率=0.5，仍然保留参考价值）。
3. 校准因子作为 `limitations` 的一部分输出（`"source_accuracy: 0.55"`）。

**失败条件：** 低准确率源的 confidence 未被校准、校准后为 0、校准信息未暴露。

---

### 4.5 Exploration Preservation Test (T11)

**目的：** 验证历史经验不会锁死未来探索空间。这是 Phase 10 最重要的单一测试。

**场景：**

```python
# Setup: 模拟 100 次失败
for i in range(100):
    store.save(ExperienceRecord(
        hypothesis="Strategy_A",
        outcome="failure",
        confidence=0.95,
        scope="condition:C",
        limitations=["condition C: microservice architecture, high load"]
    ))

# Scenario 1 — 相同条件
context_same = EvaluationContext(
    hypothesis="Strategy_A",
    scope="condition:C"
)
output_same = store.retrieve(context_same)

# 验证 1: confidence 很低（但不是 -1）
assert output_same.confidence < 0.2   # 置信度低
assert output_same.confidence > 0.0   # 但保留可能性

# 验证 2: Hypothesis Generator 仍可以输出 Strategy_A
hypothesis = generator.propose(
    candidate="Strategy_A",
    experience_context=output_same
)
assert hypothesis is not None         # 未被 veto
assert hypothesis.confidence < ORIGINAL_CONFIDENCE  # 但置信度降低


# Scenario 2 — 条件变化（drift）
context_drifted = EvaluationContext(
    hypothesis="Strategy_A",
    scope="condition:C'"               # 条件显著变化
)
output_drifted = store.retrieve(context_drifted)

# 验证 3: 条件变化后，experience 被标记为低相关性
assert "scope_mismatch" in output_drifted.limitations

# 验证 4: 条件变化后，confidence 折扣幅度大于同条件
assert output_drifted.confidence > output_same.confidence
# 解释：条件变化后，旧经验相关性降低 → 对当前判断的影响也应该降低
# 旧经验不应该对新的、不同的条件产生强约束
```

**验证通过条件：**
1. 即使 100 次失败，同一假设仍然可被提出（仅 confidence 降低）。
2. 条件变化时，旧经验的 confidence 折扣幅度更大。
3. 代码中不存在 "Strategy_A is forbidden" 或 "Strategy_A == always_fail" 的硬编码。
4. `Exploration Preservation Test` 本身不依赖于特定的 hypothesis 名称。

**失败条件：** 假设被 veto、confidence=0、条件变化后旧经验未被正确降权。

---

### 4.6 Recency / Staleness Test (T12)

**目的：** 验证旧经验自动降权，防止经验硬化。

**场景：**

```python
# Setup: 按时间保存分布
# 旧经验（6 个月前）
store.save(ExperienceRecord(
    hypothesis="Strategy_A",
    outcome="success",
    confidence=0.9,
    timestamp=now() - timedelta(days=180),
    scope="domain:general"
))

# 新经验（1 天前）
store.save(ExperienceRecord(
    hypothesis="Strategy_A",
    outcome="failure",
    confidence=0.85,
    timestamp=now() - timedelta(days=1),
    scope="domain:general"
))

# 检索
context = EvaluationContext(hypothesis="Strategy_A", scope="domain:general")
output = store.retrieve(context)

# 验证：
# 1. 新经验权重 > 旧经验权重
# 2. 旧经验不是被删除，而是被降低权重
# 3. 当新经验不再产生时，旧经验 confidence 随时间自然衰减
#    而不是永久维持不变
assert output.trend_old_to_new == "failure_recent"  # 趋势指向新失败经验
assert any("decay" in lim for lim in output.limitations)  # 衰减声明
```

**衰减策略（设计选择）：**

```
可选方案：

方案 A — 时间窗口衰减：                 方案 B — 事件计数衰减：
  过去 30 天：权重 1.0                    最近 10 条：权重 1.0
  30–90 天：权重 0.7                     10–50 条：权重 0.7
  90–180 天：权重 0.4                    50 条+：权重 0.4
  180+ 天：权重 0.2                     无新事件：权重逐渐降低

要求（无论选择哪种方案）：
  ✅ 旧经验自动降权，不为 0
  ✅ 降权因子可配置，非硬编码
  ✅ 旧经验不被删除（保留历史审计能力）
  ✅ 降权信息在 ExperienceOutput 中透明
```

**验证通过条件：**
1. 6 个月前的经验与 1 天前的经验同时存在时，新经验主导 confidence 输出。
2. 旧经验仍可检索到（不丢失历史）。
3. 降权因子透明暴露在 `limitations` 中。

**失败条件：** 新旧经验权重相等、旧经验被删除、降权因子不可见。

---

### 4.7 Cross-Source Consistency Test (T13)

**目的：** 验证来自不同 Source 的 Experience 在组合时能正确处理优先级。

**场景：**

```python
# 同一 hypothesis，三个来源
store.save(ExperienceRecord(source="reality",   outcome="success", scope="C"))  # 真实经验
store.save(ExperienceRecord(source="simulation", outcome="failure", scope="C"))  # 模拟经验
store.save(ExperienceRecord(source="user_feedback", outcome="partial", scope="C"))  # 用户反馈

retrieved = store.retrieve(hypothesis="...", scope="C")

# 验证优先级：
# 1. reality 经验权重 > 其他来源
# 2. simulation 经验附带 <0.5 confidence 折扣
# 3. user_feedback 经验有单独标记
```

**验证通过条件：**
1. 多源合并时，`reality` source 经验权重最高（但不等于绝对正确）。
2. `simulation` source 经验 confidence ≤ 0.5。
3. 合并结果在 `limitations` 中列出所有来源及其分布比例。
4. 来源影响的是 confidence weighting，不是 truth hierarchy——高优先级来源的输出仍可能包含错误，只是权重更高。

---

### 4.8 边界测试矩阵

| ID | 测试 | 类型 | 验证 |
|----|------|------|------|
| T8 | Memory Retention | Memory | 保存、检索、累积正确性 |
| T9 | Scope Violation | Bias | 局部经验不被错误泛化 |
| T10 | Confidence Calibration | Bias | 根据源准确率动态校准 confidence |
| T11 | Exploration Preservation | Bias | 历史不锁死未来（核心测试） |
| T12 | Recency / Staleness | Bias | 旧经验自动降权 |
| T13 | Cross-Source Consistency | Memory+Bias | 多源经验优先级正确 |

**测试编排：**

```
1. 先跑 Memory Tests (T8, T13)        → 确保存储基础正确
2. 再跑 Bias Tests (T9, T10, T11, T12)  → 确保认知不会固化
3. T11 作为压力测试：循环放大失败次数
   验证：n=10, n=100, n=1000 时探索空间仍保留
```

---

## Section 5 — Memory Provenance Schema

> **核心问题：** 什么样的历史信息，才有资格影响未来判断？
> **回答：** 携带完整 provenance（来源、置信度、范围、局限）的历史记录——不是原始数据，不是未经验证的意见。

### 5.1 Provenance Principle

**三条不可跨越的边界：**

```
Source ≠ Truth
  一条经验的来源不决定它是真理。
  Reality 来源权重高，但可能样本不足或观察错误。
  Simulation 来源权重低，但可能提供了有价值的反事实信号。

Confidence ≠ Authority
  一条经验的置信度不决定它是否应该被执行。
  90% confidence 的经验仍然不能生成 Decision、不能 veto、不能成为 Rule。

Outcome ≠ Rule
  一次或多次的成功/失败结果不决定未来的路径。
  100 次 Strategy_A 失败只降低其 confidence，不产生 "Strategy_A forbidden"。
```

**Provenance 的核心功能：**

```
不是：标记谁说了什么。
而是：让接收方能够判断一条经验的可信度、适用性和局限。

一条没有 provenance 的经验，不如没有经验。
```

**设计原则：**

| 原则 | 含义 |
|------|------|
| **自描述** | 每条经验记录携带足够元数据独立判断可信度 |
| **不可篡改** | Source、Timestamp 在写入后不可修改 |
| **透明** | 所有字段对调用方可见，无隐藏权重 |
| **可审计** | 每条经验可追溯到原始事件 |

---

### 5.2 Experience Record Schema

```python
@dataclass(frozen=True)  # 不可变：写入后不变
class ExperienceRecord:
    # ── 身份 ──
    id: str                                    # 全局唯一标识 (UUID)
    created_at: datetime                       # 记录创建时间（不可篡改）

    # ── 核心内容 ──
    hypothesis: str                            # 被执行的假设 / 决策
    outcome: str                               # 结果: "success" | "failure" | "partial" | "unknown"
    context_snapshot: str                      # 执行时的环境状态摘要（文本快照）

    # ── Provenance ──
    source: str                                # "observation" | "decision" | "simulation" | "user_feedback"
    source_id: str                             # 原始事件的 ID（可追溯）
    source_accuracy: float | None              # 该源的总体历史准确率（None=未知）

    # ── 可信度 ──
    raw_confidence: float                      # 记录时的初始置信度 [0, 1]
    calibrated_confidence: float               # 校准后的置信度（初始=raw，经校准更新）
    calibration_history: List[CalibrationEvent] # 校准历史（每次调整的记录）

    # ── 适用性 ──
    scope: str                                 # 适用范围的语义标记
    limitations: List[str]                     # 已知限制列表

    # ── 衰减 ──
    decay_factor: float = 1.0                  # 衰减因子 [0, 1]，初始=1，随时间/事件降低
    last_accessed: datetime | None = None       # 最后被引用时间（用于衰减计算）
```

```python
@dataclass
class CalibrationEvent:
    timestamp: datetime
    old_value: float
    new_value: float
    reason: str          # "source_accuracy_update" | "scope_mismatch" | "decay" | "manual"
```

**Schema 设计决策：**

| 字段 | 为什么在这里 | 为什么不在别处 |
|------|------------|--------------|
| `raw_confidence` vs `calibrated_confidence` | 保留原始值供审计，同时提供当前有效值 | 只保留一个则丢失校准历史 |
| `context_snapshot` | 让接收方理解执行时的环境，而非仅知道结果 | 不放在外面因为不能假设 Schema |
| `source_accuracy` | 允许 Confidence Calibration (T10) 正确工作 | 不放在源注册表是因为记录级可审计 |
| `calibration_history` | 让 Confidence Calibration 可审计 | 只保留当前值则丢失校准历史 |
| `decay_factor` | 支持 Recency/Staleness (T12) 的分段衰减 | 不放在 Store 级别是因为每记录可单独管理 |

---

### 5.3 Confidence Model

**置信度不是静态属性，而是不断演化的值。**

```
初始状态：
  calibrated_confidence = raw_confidence

校准事件（按优先级排序）：
  1. Source Accuracy Calibration:
     如果 source_accuracy < 0.8:
       calibrated_confidence *= source_accuracy
       calibration_history.append({reason: "source_accuracy_update"})

  2. Scope Mismatch Discount:
     如果请求 scope ≠ 记录 scope:
       calibrated_confidence *= scope_similarity(request_scope, record_scope)
       calibration_history.append({reason: "scope_mismatch"})

  3. Recency Decay:
     calibrated_confidence *= decay_factor
     (decay_factor 随时间/事件更新)
     calibration_history.append({reason: "decay"})

  4. Manual Calibration:
     仅在用户或系统明确触发时
     calibration_history.append({reason: "manual"})
```

**Confidence 取值约束：**

```
范围： calibrated_confidence ∈ [0, 1]
边界：
  - 值 = 0：仅当所有校准事件均为 0 时（理论上几乎不可能）
  - 值 > 0：至少保留信息价值（不会完全清零）
  - 值永远不会独立上升（校准只降不升，除非 Manual 用户明确调高）

含义：
  calibrated_confidence = 0.85 的含义是：
    基于所有可用信息（源准确率、范围匹配、时间衰减），
    这条经验的可信度为 85。
    它不是：
    - "这条经验 85% 正确"
    - "未来 85% 应该按此行动"
    - "这是 85% 确定的真理"
```

---

### 5.4 Applicability Scope

**Scope 是防止经验泛化的核心机制（T9 的契约层）。**

```python
# Scope 的语义结构
# 不是自由文本，而是结构化标记
scope = "{domain}:{context}:{condition_set}"

# 示例
"domain:code_review:context:python:condition:microservice"
"domain:creative_writing:context:urban_romance:condition:modern"

# Scope 相似度算法（用于 Scope Mismatch Discount）
def scope_similarity(request_scope: str, record_scope: str) -> float:
    """
    返回 [0, 1] 的相似度分数。

    规则:
      - 同一 domain: 基础分 0.5
      - domain + context 相同: 基础分 0.8
      - domain + context + condition 相同: 基础分 1.0

      - domain 不同: 基础分 0.2
      - domain 不同 + condition 相近: 基础分 0.3

    返回值乘以 calibrated_confidence，不会使 confidence 为 0。
    """
```

**关键约束：**

```
1. Scope 在 ExperienceRecord 创建时确定，创建后不可修改。
2. Scope 必须是一个有效的结构化标记（非空、符合模式）。
3. 如果没有 scope（未知适用域），则该经验的 confidence 上限为 0.3。
4. Scope 不匹配时，confidence 被折扣但不会被清零。
```

---

### 5.5 Provenance Validation Tests

| ID | 测试 | 验证 | 类型 |
|----|------|------|------|
| **T14 — Schema Completeness** | 每个 ExperienceRecord 实例包含所有必需字段 | 编译/序列化检查 | Static |
| **T15 — Immutability** | 创建后 `id`, `created_at`, `source` 不可修改 | 写入后修改返回错误 | Static |
| **T16 — Scope Existence** | 没有 scope 的记录 confidence ≤ 0.3 | 查询 scope="" 的记录 | Runtime |
| **T17 — Calibration Audit** | 每条记录被校准后 `calibration_history` 包含对应事件 | 校准后可审计 | Runtime |
| **T18 — Confidence Non-Zero** | 任何校准后 confidence 仍 > 0 | 批量验证 | Runtime |
| **T19 — Provenance Traceability** | 每条经验的 `source_id` 可追溯到原始事件 ID | 追溯链完整 | Runtime |
| **T20 — Cross-Record Consistency** | 相同 hypothesis + scope 的经验在聚合时 consistency 可验证 | 聚合结果不自相矛盾 | Runtime |

**T20 细节：**

```python
# 场景：同一 hypothesis + scope 下，多条结果矛盾
store.save(ExperienceRecord(hypothesis="A", outcome="success", scope="C"))
store.save(ExperienceRecord(hypothesis="A", outcome="failure", scope="C"))
store.save(ExperienceRecord(hypothesis="A", outcome="success", scope="C"))

# 聚合结果应该是：
#   success_rate = 2/3
#   n_total = 3
#   consistency_warning = False  (因为 N 小，矛盾在正常波动范围内)

# 但如果：
store.save(ExperienceRecord(hypothesis="A", outcome="failure", scope="C"))  # ×10
store.save(ExperienceRecord(hypothesis="A", outcome="success", scope="C"))   # ×3

# 聚合结果：
#   success_rate = 3/13 ≈ 0.23
#   n_total = 13
#   consistency_warning = True  (矛盾比例超出正常范围)
#   limitations 追加: "contradictory: 13 records, 23% success rate conflicts with 77% failure rate"
```

---

### 5.6 ABI 冻结结论

| Section | Status | 核心声明 |
|---------|--------|----------|
| **Section 1** — North Star Compliance | ✅ FROZEN | Experience 属于 OCOS |
| **Section 2** — Constitution Compliance | ✅ FROZEN | Experience 不违反最高规则 |
| **Section 3** — Influence Contract | ✅ FROZEN | Experience 只做被允许的事 |
| **Section 4** — Historical Bias Tests | ✅ FROZEN | Experience 不限制探索空间 |
| **Section 5** — Memory Provenance | ✅ FROZEN | 只有带 provenance 的经验才有资格影响判断 |

```diff
+ Final Ruling:

  Phase 10 Experience Intelligence Layer ABI v1.0
  ================================================

  Status: FROZEN ✅

  Experience Intelligence Layer 是 OCOS 的原生能力。

  它理解过去。
  它改善判断。
  它不统治决定。

  ——
  Source ≠ Truth.
  Confidence ≠ Authority.
  Outcome ≠ Rule.

  ABI 5 节全部验证通过。
  零 Constitution 违反。
  零隐性 Authority 路径。
  全部边界由 Test 契约保证。

  Phase 10 可以进入实现阶段。
```
