# Phase 15 — Process Foundation 设计提案

**版本**: v0.1（审查前草稿）
**日期**: 2026-07-22
**状态**: Draft（待架构审查）
**前置依赖**: Phase 14 Information Foundation ✅, ADR-018 Architecture Theory Calibration ✅

---

## 1. 设计目标

### 一句话目标

> **建立 OCOS 中所有认知过程的统一表示，而不是实现任何具体认知能力。**

### 为什么需要 Process Foundation

当前 OCOS 已有完整的 Information Theory、Lifecycle、Knowledge Theory，但缺少对"认知过程"的统一抽象：

```
信息可以被存储、查询、提升、遗忘。         ✅
信息可以被追踪生命周期。                    ✅
信息之间的关系可以被管理。                   ✅
信息如何被推理、决策、规划、模拟？           ❌ 无统一表示
```

没有 Process 层，每个新的认知能力都会在代码库中寻找自己的落脚点——最终趋向于 Engine、Theory、Model 三者各一个的膨胀模式。Process Foundation 提供**一个统一的抽象槽位**，所有认知能力只需要填充 ProcessType 枚举的一个新成员。

### 解决的问题

| 问题 | 无 Process 层 | 有 Process 层 |
|------|-------------|-------------|
| 新增 Reasoning | 写 reasoning_engine.py + REASONING_THEORY.md + ReasoningModel | 写 ProcessType.REASONING 实现 |
| 新增 Planning | 写 planning_engine.py + PLANNING_THEORY.md + PlanningModel | 写 ProcessType.PLANNING 实现 |
| 新增 Reflection | 找"这是不是该有个 reflection_engine.py" | 自然归入 ProcessType.REFLECTION |
| 认知过程如何关联 Trace | 每个能力自己实现记录逻辑 | Process → Trace 自动映射 |

---

## 2. 架构原则（四条"不堆叠"原则）

### 2.1 Engine 不堆叠

> 认知能力不是独立 Engine。

违反：`ocos/engines/reasoning_engine.py` 中有一个 `reason()` 方法。

正确：Reasoning 表现为 ProcessType.REASONING，可以被任何组件消费——包括 Engine（如 AttentionEngine 可以触发 Reasoning Process）。

### 2.2 Model 不堆叠

> 认知能力不是特殊 dataclass。

违反：`ocos/models/reasoning.py` 中定义了 `ReasoningChain`。

正确：所有认知过程共享 `ocos/models/process.py` 中的 `TransformProcess`，以 `process_type` 区分。

### 2.3 层命名不堆叠

> 架构层描述抽象范畴（Process），不是某一种 Process。

违反：将 L4 命名为 `Reasoning Theory`。

正确：L4 = `Process Theory`。Reasoning、Decision、Planning…都是 ProcessType 成员。

### 2.4 Capability 不堆叠

> 新增能力优先用 ProcessType，不新增架构边界。

| 新增能力 | ❌ 错误路径 | ✅ 正确路径 |
|----------|-----------|-----------|
| Reflection | reflection_engine.py + REFLECTION_THEORY.md | ProcessType.REFLECTION |
| Negotiation | negotiation_model.py | ProcessType.NEGOTIATION |
| Verification | verification_engine.py | ProcessType.VERIFICATION |
| Self-Repair | self_repair_theory.md | ProcessType.SELF_REPAIR |

---

## 3. 影响范围

### 3.1 新增文件

| 文件 | 类型 | 内容 |
|------|------|------|
| `ocos/models/process.py` | **新增** | ProcessType, ProcessState, ProcessStep, TransformProcess |
| `docs/PROCESS_THEORY.md` | **新增** | Process 层理论文档 |
| `ocos/tests/test_process_model.py` | **新增** | Process 数据模型测试 |
| `ocos/tests/test_transformation_events.py` | **新增** | Transform 事件测试 |
| `ocos/tests/test_process_trace_integration.py` | **新增** | Process → Trace 闭环测试 |
| `docs/adr/ADR-019-process-foundation.md` | **新增** | 冻结证书 |

### 3.2 修改文件

| 文件 | 修改内容 | 影响级别 |
|------|---------|---------|
| `ocos/kernel/event_schema.py` | 注册 INFORMATION_TRANSFORMATION_STARTED/COMPLETED/FAILED 事件 | **低** — 纯新增，不修改已有 schema |
| `ocos/kernel/abi.py` | 在 EventType 枚举中增加 3 个新事件 | **低** — 纯新增枚举值 |
| `ocos/platform/trace_engine.py` | 新增 `record_process_trace()` 或接入方法 | **低** — 扩展，不修改已有 trace 逻辑 |
| `docs/adr/INDEX.md` | 增加 ADR-019 索引 | 纯文档 |

### 3.3 不修改的文件（ABI 稳定边界）

```python
# 以下文件在任何情况下都不修改：

ocos/kernel/constitution.py       # 宪法不变
ocos/models/information.py        # Information 模型不变（SemanticRole.REASONING 保留至 v2.0）
ocos/models/address.py            # 地址模型不变
ocos/kernel/abi.py (现有 ABI)     # 已有 dataclass 字段不变
ocos/kernel/event_schema.py (已有 schema)  # 已有事件 schema 不修改
ocos/engines/*.py                 # 已有 Engine 逻辑不变
```

### 3.4 不创建的文件（阻止架构倒退）

```python
# 以下文件不允许创建（如果 PR 中出现了，审查应当拒绝）：

ocos/engines/reasoning_engine.py   # ❌ Engine 不堆叠
ocos/models/reasoning.py           # ❌ Model 不堆叠
docs/REASONING_THEORY.md           # ❌ 层命名不堆叠
```

---

## 4. Process 数据模型

### 4.1 ProcessType

```python
class ProcessType(str, Enum):
    """OCOS 认知过程类型。

    所有认知能力在此平级。新增能力只在此增加一个成员，
    不需要创建新的 Engine、Theory 或专用数据模型。

    扩展条件：
    1. 该能力是否是 Information 之间的转换过程？
    2. 输入输出是否可以用 Address[] 描述？
    3. 是否可以通过 Trace 记录其执行历史？
    如果三个都是"是"，就适合成为 ProcessType。
    """
    REASONING = "reasoning"
    DECISION = "decision"
    PLANNING = "planning"
    SIMULATION = "simulation"
    LEARNING = "learning"
    # 未来扩展：
    # REFLECTION = "reflection"
    # NEGOTIATION = "negotiation"
    # VERIFICATION = "verification"
    # OPTIMIZATION = "optimization"
    # SELF_REPAIR = "self_repair"
```

### 4.2 ProcessState

```python
class ProcessState(str, Enum):
    """Process 的状态生命周期。"""
    CREATED = "created"       # 已创建，尚未执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 执行完成
    FAILED = "failed"         # 执行失败
```

### 4.3 ProcessStep

```python
@dataclass(frozen=True)
class ProcessStep:
    """Process 中的单个步骤。

    设计原则：
    - 不拥有 Information（使用地址引用）
    - 不包含执行逻辑（纯数据）
    - 可序列化、可追踪
    """
    step_id: str
    description: str
    input_addresses: list[UniversalAddress]
    output_addresses: list[UniversalAddress]
    operation: str
    confidence: float
```

### 4.4 TransformProcess

```python
@dataclass(frozen=True)
class TransformProcess:
    """OCOS 认知过程的统一表示。

    设计原则（对应审计报告四条不变量）：
    1. Process 不拥有 Information（使用地址引用）
    2. Process 不改变 Information 生命周期（由 Lifecycle Engine 管理）
    3. Process 不执行 Action（由 Execution 层处理）
    4. Process 必须引用 Evidence（可追溯）
    """
    process_id: str
    process_type: ProcessType
    process_state: ProcessState = ProcessState.CREATED
    input_addresses: list[UniversalAddress] = field(default_factory=list)
    output_addresses: list[UniversalAddress] = field(default_factory=list)
    steps: list[ProcessStep] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
```

### 4.5 为什么是一个 dataclass 而非多个

设计 Decision：

```python
# ❌ 不要（独立 dataclass）
class ReasoningProcess:
    reasoning_id: str
    premises: list[UniversalAddress]
    conclusion: InformationData  # 嵌入结果对象——违反"Process 不拥有 Information"

class DecisionProcess:
    decision_id: str
    options: list[DecisionOption]
    chosen: str

# ✅ 正确（统一 TransformProcess + process_type）
process = TransformProcess(
    process_id="proc-001",
    process_type=ProcessType.REASONING,
    input_addresses=[obs_addr, know_addr],
    output_addresses=[conclusion_addr],  # 引用，非嵌入
    steps=[ProcessStep(...)],
    confidence=0.78,
)
```

理由：如果为每个 ProcessType 创建独立 dataclass，当 ProcessType 增长到 10 个时，会再次出现 Model 堆叠——正好是第一条原则禁止的。

---

## 5. 事件设计

### 5.1 事件枚举

```python
class EventType(str, Enum):
    # ... 已有事件 ...
    INFORMATION_TRANSFORMATION_STARTED = "information_transformation_started"
    INFORMATION_TRANSFORMATION_COMPLETED = "information_transformation_completed"
    INFORMATION_TRANSFORMATION_FAILED = "information_transformation_failed"
```

**命名理由**：`Transformation`（名词）与已有 `INFORMATION_STATUS_CHANGED` 风格一致。

### 5.2 事件 Payload

```python
# INFORMATION_TRANSFORMATION_STARTED
{
    "process_id": "proc-001",
    "process_type": "reasoning",
    "input_addresses": ["addr:obs-001", "addr:know-042"],
    "timestamp": "2026-07-22T12:00:00Z",
}

# INFORMATION_TRANSFORMATION_COMPLETED
{
    "process_id": "proc-001",
    "process_type": "reasoning",
    "output_addresses": ["addr:con-007"],
    "result": {"conclusion": "太阳风暴概率78%", "confidence": 0.78},
    "timestamp": "2026-07-22T12:00:05Z",
}

# INFORMATION_TRANSFORMATION_FAILED
{
    "process_id": "proc-001",
    "process_type": "reasoning",
    "error": "输入信息不足：缺少历史频率数据",
    "timestamp": "2026-07-22T12:00:03Z",
}
```

### 5.3 不创建独立事件

```python
# ❌ 不要
REASONING_STARTED        # 每个 ProcessType 一个 => 事件爆炸
REASONING_COMPLETED
PLANNING_STARTED
SIMULATION_STARTED

# ✅ 正确：统一事件 + process_type 区分
INFORMATION_TRANSFORMATION_STARTED  # payload 中的 process_type 区分类型
```

---

## 6. Trace 接入方式

### 6.1 问题

当前 `trace_engine.py` 中已存在：

```python
record_reasoning_trace()    # 定义了但从未被调用
record_decision_trace()     # 定义了但从未被调用
record_simulation_trace()   # 定义了但从未被调用
record_learning_trace()     # 定义了但从未被调用
```

### 6.2 解决方案

在 `trace_engine.py` 中增加一个统一入口：

```python
# 新增统一方法
def record_process_trace(self, process: TransformProcess) -> str:
    """根据 process_type 自动分发到对应的 trace 记录方法。"""
    method = self._trace_dispatch.get(process.process_type)
    if method:
        return method(process)
    raise ValueError(f"Unknown process type: {process.process_type}")
```

内部路由表：

```python
_TRACE_DISPATCH = {
    ProcessType.REASONING: TraceEngine.record_reasoning_trace,
    ProcessType.DECISION: TraceEngine.record_decision_trace,
    ProcessType.SIMULATION: TraceEngine.record_simulation_trace,
    ProcessType.LEARNING: TraceEngine.record_learning_trace,
}
```

### 6.3 触发时机

TransformProcess 状态变更时自动触发：

```
TransformProcess.state → COMPLETED
    → 内部调用 TraceEngine.record_process_trace(self)
    → TraceEngine 根据 process_type 分发到对应记录方法
    → 发射 INFORMATION_TRANSFORMATION_COMPLETED 事件
```

这个触发逻辑目前由消费方实现（Phase 15 只定义契约和接入方法，不实现 Engine 调度器）。Phase 18+ 的 Process Engine 会在调度层自动处理状态变更与 Trace 的联动。

---

## 7. 兼容性分析

### 7.1 ABI 兼容

| 组件 | 是否受影响 | 原因 |
|------|-----------|------|
| `InformationData` | ❌ 不变 | 无字段修改 |
| `SemanticRole` | ❌ 不变 | REASONING 保留至 v2.0 |
| `UniversalAddress` | ❌ 不变 | 无字段修改 |
| `Decision` | ❌ 不变 | reasoning 字段暂不改（Phase 16 处理） |
| `EventType` | **新增** | 纯新增枚举值，不影响已有消费者 |
| `EventSchema` | **新增** | 纯新增 schema，不影响已有验证 |

### 7.2 Engine 兼容

| Engine | 是否受影响 | 原因 |
|--------|-----------|------|
| AttentionEngine | ❌ 不变 | 不引用 Process 模型 |
| PolicyEngine | ❌ 不变 | 只验证 Decision 内容 |
| ConsolidationEngine | ❌ 不变 | 只处理 Information role 映射 |
| PromotionEngine | ❌ 不变 | 同上 |
| ForgettingEngine | ❌ 不变 | 只处理 decay lifecycle |
| RetrievalEngine | ❌ 不变 | 只处理 Information 查询 |

### 7.3 测试兼容

| 测试套件 | 行数 | 是否受影响 |
|---------|------|-----------|
| 现有 1187 测试 | 1187 | ❌ 不变 |

所有新增测试为纯新增文件，不修改已有测试。

---

## 8. 迁移策略

### 8.1 v1.x 阶段（Phase 15 完成时）

| 项目 | 状态 |
|------|------|
| PROCESS_THEORY.md | ✅ 已冻结 |
| models/process.py | ✅ 可用 |
| INFORMATION_TRANSFORMATION 事件 | ✅ 已注册 |
| Process → Trace 接入 | ✅ 已接通 |
| SemanticRole.REASONING | 🟡 保留（兼容） |
| Decision.reasoning: str | 🟡 保留（Phase 16 改为引用） |
| trace_engine.py 中独立方法 | 🟡 保留（record_reasoning_trace 等仍可用） |

### 8.2 v2.0 清理计划

| 项目 | 处理方式 |
|------|---------|
| 删除 SemanticRole.REASONING | 替换为 ProcessType.REASONING + 新增 CONCLUSION/BELIEF/HYPOTHESIS role |
| 删除独立 trace 方法 | 统一到 record_process_trace()，原有独立方法标记 deprecated |
| Decision.reasoning: str | 改为 reasoning_reference: UniversalAddress |

---

## 9. 架构审查清单（供 Step 2 使用）

### 9.1 Process 是否保持抽象？

| 检查项 | 预期回答 |
|--------|---------|
| Process 是否不暗示任何具体推理算法？ | ✅（无 reason()/evaluate() 等方法） |
| Process 是否不暗示 LLM？ | ✅（无 model_name/prompt 等字段） |
| Process 是否不嵌入任何 Information？ | ✅（全部使用 Address 引用） |
| 新增 ProcessType 是否不需要修改模型结构？ | ✅（只需加一个枚举成员） |

### 9.2 是否没有引入新的耦合？

| 检查项 | 预期回答 |
|--------|---------|
| Process 是否不依赖任何 Engine？ | ✅（纯 dataclass） |
| Process 是否不依赖 EventBus？ | ✅（只是被消费的对象） |
| Process 是否可以被任何组件创建？ | ✅（无创建限制） |

### 9.3 是否符合四条"不堆叠"原则？

| 原则 | 检验 |
|------|------|
| Engine 不堆叠 | ❌ 无 reasoning_engine.py |
| Model 不堆叠 | ✅ 统一 TransformProcess |
| 层命名不堆叠 | ✅ L4 = Process Theory |
| Capability 不堆叠 | ✅ 新增能力 = ProcessType 成员 |

### 9.4 是否与现有架构职责边界一致？

| 边界 | Process 的定位 |
|------|-------------|
| Information | 被操作的对象 — Process 引用但不拥有 |
| Lifecycle | 生命周期契约 — Process 作为 Transform 阶段调用 |
| Trace | 历史记录 — Process 完成时自动记录 |
| Governance | 约束规则 — Process 必须在规则范围内运行 |

---

## 10. 架构约束测试（Step 4 新增）

除三个功能测试外，建议新增一组架构约束测试（architecture enforcement tests）：

```python
# test_architecture_principles.py

def test_no_reasoning_engine():
    """验证不存在独立的 reasoning_engine.py（Engine 不堆叠）"""
    import os
    path = os.path.join(ROOT, "ocos/engines/reasoning_engine.py")
    assert not os.path.exists(path), "Reasoning Engine would violate Engine 不堆叠"

def test_no_reasoning_model():
    """验证不存在独立的 models/reasoning.py（Model 不堆叠）"""
    import os
    path = os.path.join(ROOT, "ocos/models/reasoning.py")
    assert not os.path.exists(path), "Reasoning Model would violate Model 不堆叠"

def test_no_reasoning_theory():
    """验证不存在独立的 REASONING_THEORY.md（层命名不堆叠）"""
    import os
    path = os.path.join(ROOT, "docs/REASONING_THEORY.md")
    assert not os.path.exists(path), "Reasoning Theory would violate 层命名不堆叠"

def test_process_type_extensible():
    """验证 ProcessType 可以扩展但不会要求新增 Theory 文档或 Engine"""
    # ProcessType 的枚举值应当可以在不修改任何其他文件的情况下新增
    from ocos.models.process import ProcessType
    original_count = len(ProcessType)
    # 新枚举值应当只需 1 行修改
    # 不应当触发新增 Engine/Theory
```

---

## 11. ADR-019 框架

ADR-019 应记录以下内容。

### 11.1 新增了什么

- PROCESS_THEORY.md — Process 层理论
- models/process.py — 统一 Process 数据模型
- INFORMATION_TRANSFORMATION 事件
- Process → Trace 自动映射

### 11.2 被否决的方案

| 被否决的方案 | 否决理由 |
|-------------|---------|
| 独立 Reasoning Engine | Engine 不堆叠 — 认知能力不是独立 Engine |
| 独立 Reasoning Model（models/reasoning.py） | Model 不堆叠 — 认知能力不是特殊 dataclass |
| 独立 Reasoning Theory（REASONING_THEORY.md） | 层命名不堆叠 — L4 是 Process Theory，非 Reasoning Theory |
| Capability 驱动扩展（每个能力独立 Engine + Theory） | Capability 不堆叠 — 新增能力归入 ProcessType，不新增架构边界 |

### 11.3 保留的兼容债务

- SemanticRole.REASONING → v2.0 删除
- Decision.reasoning: str → Phase 16 改为引用
- 独立 trace 方法 → v2.0 统一

---

## 12. 执行计划

| 步骤 | 内容 | 交付物 |
|------|------|--------|
| Step 1 | ✅ 设计提案（本文档） | `docs/design/Phase15-Process-Foundation.md` |
| Step 2 | 架构审查 | 审查意见记录 |
| Step 3 | 实现 | `models/process.py`, event registry, trace bridge |
| Step 4 | 测试 | 3 个功能测试 + 1 个架构约束测试 |
| Step 5 | ADR 冻结 | `ADR-019-process-foundation.md` |
