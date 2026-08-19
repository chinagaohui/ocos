# OCOS 认知过程层审计报告 v1.3

**日期**: 2026-07-22
**原审计范围**: ocos 代码库中与"推理/思考/Reasoning"相关的所有概念
**修正范围追溯**:
  - v1.0: "思考模块审计" → 隐式假设 Reasoning 是独立模块
  - v1.1: Reasoning = Transform Process → 剥离 Engine 假设
  - v1.2: models/process.py → 剥离 Model 特殊化
  - **v1.3: L4 = Process Theory，不是 Reasoning Theory → 剥离命名范畴假设**
**审计方法**: 逐文件扫描 + 三轮架构评审校准

---

## 总体评分: 5.0~5.5 / 10

当前 OCOS 缺失的不是"推理能力"，而是**认知过程层（Process Layer）的理论冻结**。

### 三轮校准演进

| 轮次 | 校准内容 | 发现的错误假设 |
|------|---------|-------------|
| 第一轮 | Engine 不堆叠 | "缺 reasoning_engine.py" → Reasoning 不是 Engine |
| 第二轮 | Model 不堆叠 | "创建 models/reasoning.py" → Reasoning 不是特殊 Model |
| **第三轮** | **层命名不堆叠** | **"L4 = Reasoning Theory" → L4 是 Process Theory，不是 Reasoning Theory** |

第三轮是范畴修正：如果把一个 ProcessType（Reasoning）的提升为层命名（Reasoning Theory），早晚会有人提议 DECISION_THEORY.md、PLANNING_THEORY.md——Memory 的错误以另一种形式复现。

---

## 一、存在什么（不变）

### 1.1 SemanticRole.REASONING ✅

`ocos/models/information.py:60`。v1.x 保留，v2.0 删除（REASONING 应归 ProcessType 而非 SemanticRole）。

### 1.2 ReasoningTrace ✅

`ocos/platform/trace_engine.py:72-89`

### 1.3 TraceEngine.record_reasoning_trace() ✅

### 1.4 Decision.reasoning: str ✅

待改为 `reasoning_reference: UniversalAddress`。

### 1.5 DECISION_FORMED 事件 ✅

### 1.6 引擎级映射 ✅

consolidation_engine / promotion_engine 中有 `"reasoning" → KnowledgeLevel.EVIDENCE`。

---

## 二、真正缺失什么（v1.3 最终版）

### 2.1 ❌ L4 = Process Theory 未冻结

这是唯一的核心问题。其余都是它的投影。

```
当前 OCOS 架构栈：

L0 Information Theory     ✅  被操作的对象
L1 Information Graph      🟡  关系网络
L2 Information Lifecycle  ✅  生命周期契约
L3 Knowledge Theory       ✅  稳定知识的定义
L4 Process Theory         ❌  改变信息关系的过程  ← 当前空缺
L5 Execution Theory       ❌  如何作用于世界

L4 如果命名为 "Reasoning Theory"，会将一个 ProcessType（Reasoning）
提升为层名，隐含"这个 Process 比其他 Process 更基础"的错误假设。
```

### 2.2 ❌ 无统一 Process 模型

缺少 `models/process.py`：

```python
class ProcessType(Enum):
    REASONING = "reasoning"
    DECISION = "decision"
    PLANNING = "planning"
    SIMULATION = "simulation"
    LEARNING = "learning"
    # REFLECTION, EVALUATION 等可扩展

class ProcessState(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessStep:
    step_id: str
    description: str
    input_addresses: list[UniversalAddress]
    output_addresses: list[UniversalAddress]
    operation: str
    confidence: float

class TransformProcess:
    process_id: str
    process_type: ProcessType   # 统一的 Process 类型
    input_addresses: list[UniversalAddress]
    output_addresses: list[UniversalAddress]
    steps: list[ProcessStep]
    state: ProcessState
    confidence: float
    metadata: dict
```

**不创建独立的 ReasoningProcess/DecisionProcess/PlanningProcess dataclass。** 一个 TransformProcess + process_type 即可覆盖所有。

### 2.3 ❌ 无 INFORMATION_TRANSFORMATION 事件

缺少：

```python
INFORMATION_TRANSFORMATION_STARTED
    payload: { process_id, process_type, input_addresses }
INFORMATION_TRANSFORMATION_COMPLETED
    payload: { process_id, process_type, output_addresses }
INFORMATION_TRANSFORMATION_FAILED
    payload: { process_id, process_type, error }
```

这样 Reasoning / Planning / Simulation / Learning 全部共享同一组事件。事件不爆炸。

### 2.4 ❌ Process → Trace 链路中断

### 2.5 ❌ 无 PROCESS_THEORY.md

---

## 三、Process 在 OCOS 中的正确定位

### 3.1 OCOS 认知系统的核心对象只有两个

```
Information — 被操作的东西（数据）
Process     — 改变信息关系的过程（操作）
```

这两个对象构成了 OCOS 认知架构的全部基础。Memory、Knowledge、Reasoning、Decision、Planning、Learning 都是它们的投影或组合。

```
传统 Agent 架构：
  Memory Engine → Reasoning Engine → Decision Engine → Action Engine
  每个能力是独立黑盒，互相耦合

OCOS 架构：
  Information ← Process → 新的 Information
    │                         │
    └── Lifecycle              └── Trace
         │                         │
         └── Governance ────────────┘
```

### 3.2 Process 不拥有任何东西

四个不变量（v1.2 → v1.3 保持）：

1. Process 不拥有 Information（使用地址引用）
2. Process 不改变 Information 生命周期（由 Lifecycle Engine 管理）
3. Process 不执行 Action（由 Execution 层处理）
4. Process 必须引用 Evidence（可追溯）

### 3.3 Process 与 Trace 的对称关系

```mermaid
ProcessLayer            TraceLayer
─────────────           ───────────
REASONING  Process  ══> ReasoningTrace   ✅
DECISION   Process  ══> DecisionTrace    ✅
SIMULATION Process  ══> SimulationTrace  ✅
LEARNING   Process  ══> LearningTrace    ✅
MEMORY     Process  ══> MemoryTrace      ✅
```

Trace 层早已正确映射了 Process 层——五个 TraceType 正好对应五个 ProcessType。工程直觉再次领先理论。

### 3.4 SemanticRole.REASONING 的处理

v1.2 正确识别了问题：REASONING 是 ProcessType 而非 SemanticRole。

v1.3 最终判断：

```
v1.x: 保留 SemanticRole.REASONING（向后兼容）
v2.0: 
  删除 SemanticRole.REASONING
  新增 ProcessType.REASONING
  新增 SemanticRole: BELIEF, HYPOTHESIS, CONCLUSION, ASSESSMENT
```

产生的信息：
```
Reasoning Process:
  ProcessType.REASONING
    │
    ├── 输入: Observation("天空异常红光"), Knowledge("红光频率对照表")
    ├── 输出: Information(role=CONCLUSION, content="太阳风暴概率78%")
    └── Trace: ReasoningTrace(...)
```

---

## 四、问题分级（v1.3 最终）

### P1（冻结阻塞）

| # | 问题 | 影响 |
|---|------|------|
| P-01 | **Process Theory 未冻结** — L4 理论层空缺 | 六层架构唯一理论空洞 |
| P-02 | **无 Process 模型** — models/process.py 不存在 | TransformProcess 无数据载体 |
| P-03 | **层命名错误风险** — 若将 L4 命名为 "Reasoning Theory" | 会诱导后续"每个能力写一篇 Theory"的错误路径 |

### P2（链路断裂）

| # | 问题 | 影响 |
|---|------|------|
| P-04 | **无 INFORMATION_TRANSFORMATION 事件** | Transform 作为 Lifecycle 阶段无事件标记 |
| P-05 | **Process → Trace 链路断裂** | record_reasoning_trace() 从未被调用 |
| P-06 | **SemanticRole.REASONING 零实例** | 角色存在但无 Information 使用 |

### P3（扩展性）

| # | 问题 | 影响 |
|---|------|------|
| P-07 | 无 DECISION_MODEL.md | 下游文档链断裂 |
| P-08 | Decision.reasoning 是 str 而非地址引用 | 链式追溯断裂 |

---

## 五、修复建议（v1.3 最终版）

### 建议 1：冻结 PROCESS_THEORY.md（核心）

创建 `docs/PROCESS_THEORY.md`，而非 `REASONING_THEORY.md`。

冻结内容：

1. **Process 定义**
   - Process = Information Transformation Process
   - 输入：`Information Address[]`
   - 输出：`Information Address[]`
   - 不变量（见 §3.2）

2. **Process 在 Information Lifecycle 中的定位**
   - 作为 Transform 阶段调用 Lifecycle
   - Process 不拥有自己的生命周期

3. **ProcessType 枚举**
   - REASONING, DECISION, PLANNING, SIMULATION, LEARNING, ...

4. **Process 与 Trace 的对称关系**
   - 每个 ProcessType 对应一个 TraceType
   - Process 完成时自动 record Trace

5. **Confidence 模型**
   - 基于 Evidence 引用数量和质量

### 建议 2：创建统一 Process 模型

创建 `ocos/models/process.py`：

```python
class ProcessType(str, Enum):
    REASONING = "reasoning"
    DECISION = "decision"
    PLANNING = "planning"
    SIMULATION = "simulation"
    LEARNING = "learning"

class ProcessState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessStep:
    step_id: str
    description: str
    input_addresses: list[UniversalAddress]
    output_addresses: list[UniversalAddress]
    operation: str
    confidence: float

class TransformProcess:
    process_id: str
    process_type: ProcessType
    process_state: ProcessState = ProcessState.CREATED
    input_addresses: list[UniversalAddress]
    output_addresses: list[UniversalAddress]
    steps: list[ProcessStep]
    confidence: float
    metadata: dict
    schema_version: str = SCHEMA_VERSION
```

### 建议 3：Transform 事件

```python
INFORMATION_TRANSFORMATION_STARTED
    payload: { process_id, process_type, input_addresses }
INFORMATION_TRANSFORMATION_COMPLETED
    payload: { process_id, process_type, output_addresses, result }
INFORMATION_TRANSFORMATION_FAILED
    payload: { process_id, process_type, error }
```

统一事件，覆盖所有 ProcessType。

### 建议 4：Process → Trace 接入

TransformProcess 状态变更时（COMPLETED）自动调用 TraceEngine 对应方法：

```python
TRACE_METHOD_MAP = {
    ProcessType.REASONING: TraceEngine.record_reasoning_trace,
    ProcessType.DECISION:  TraceEngine.record_decision_trace,
    ProcessType.SIMULATION: TraceEngine.record_simulation_trace,
    ProcessType.LEARNING:   TraceEngine.record_learning_trace,
}
```

### 建议 5：文档结构

```
docs/
├── INFORMATION_THEORY.md       L0 ✅
├── INFORMATION_LIFECYCLE.md     L2 ✅
├── PROCESS_THEORY.md           L4 ← Phase 15 核心
├── REASONING_MODEL.md          ProcessType 子文档
├── DECISION_MODEL.md           ProcessType 子文档
├── PLANNING_MODEL.md           ProcessType 子文档
### 四"不堆叠"原则

| 原则 | v1.0 错误 | 现状态 |
|------|-----------|--------|
| Engine 不堆叠 | "写 reasoning_engine.py" — 认知能力不是 Engine | ✅ |
| Model 不堆叠 | "写 models/reasoning.py" — 认知能力不是特殊 dataclass | ✅ |
| 层命名不堆叠 | "写 REASONING_THEORY.md" — 架构层描述抽象范畴（Process），不是某一种 Process | ✅ |
| **Capability 不堆叠** | 新增能力时新增架构层/Engine/独立文档 — 新增能力优先表示为 **ProcessType** | ✅ 新增 |

**第四条的内涵**：任何新增认知能力（Reflection、Negotiation、Verification、Optimization、Self-Repair），优先回答一个问题——"它是不是一种 Process？"如果是，只需要成为 ProcessType 的一个新成员，不再需要新的架构层、独立理论文档、Engine 或专用数据模型。

---

## Phase 15 — Process Foundation（最终定义）

### 一句话目标

> **建立 OCOS 中所有认知过程的统一表示，而不是实现任何具体认知能力。**

### 范围清单

| 模块 | 交付物 | 复杂度 |
|------|--------|--------|
| **A. 理论** | `docs/PROCESS_THEORY.md` v1.0 | 中 |
| **B. 模型** | `ocos/models/process.py` — ProcessType, ProcessState, ProcessStep, TransformProcess | 低 |
| **C. 事件** | `INFORMATION_TRANSFORMATION_STARTED/COMPLETED/FAILED` + EventSchema 注册 | 低 |
| **D. 接入** | TransformProcess completion → TraceEngine 自动 record | 低 |
| **E. 测试** | `test_process_model.py`, `test_transformation_events.py`, `test_process_trace_integration.py` | 低 |
| **F. ADR** | `ADR-019-process-foundation.md` | 低 |

### PROCESS_THEORY.md 必须覆盖的内容

1. Process 的定义（为什么存在）
2. Process 与 Information、Lifecycle、Trace 的关系
3. ProcessType 的扩展原则（新增类型必须满足什么条件）
4. TransformProcess 的统一契约
5. Process → Trace 的映射规则
6. 为什么 Process 不拥有 Information、不拥有生命周期、不直接执行 Action

### 不包含（Phase 15 明确排除）

任何具体认知能力的实现（Reasoning Engine、Deduction Engine、Planning Engine、LLM 集成等）→ Phase 18+。

---

## 最终判断

v1.3/v1.4 的核心价值不在于把 Reasoning 设计好了，而在于**把"认知能力"从架构层剥离出来，归入统一的 Process 抽象**。

```
Information —— 静态对象（What）
Process     —— 转换过程（How）
Trace       —— 历史记录（What happened）
Governance  —— 约束规则（What is allowed）

ProcessType（所有认知能力在此平级）：
  REASONING | DECISION | PLANNING | SIMULATION | LEARNING
  REFLECTION | NEGOTIATION | VERIFICATION | OPTIMIZATION | SELF_REPAIR（未来）
```

这意味着未来新增任何认知能力，都不再需要新的架构层、理论文档、Engine 或专用数据模型——只需要成为 ProcessType 的一个新成员。

| ❌ 排除项 | 原因 | 归属 |
|-----------|------|------|
| reasoning_engine.py | Engine 不代表认知过程 | Phase 18+ |
| reasoning_algorithm.py | 具体推理算法 | Phase 18+ |
| deduction_engine.py | 规则引擎 | Phase 18+ |
| SemanticRole.REASONING 删除 | 向后兼容约束 | v2.0 |
| DECISION_MODEL.md | 文档链：先冻结 Theory 再写子文档 | Phase 16 |
| PLANNING_MODEL.md | 同上 | Phase 17 |

---

## 七、OCOS 认知架构成熟度（Phase 15 入口）

```
                      当前     Phase 15 后
Information Theory    ██████████ 100% → 100%
Memory Architecture   ████████░░  80% →  80%   (理论已完成，v2.0 代码迁移)
Knowledge Architecture █████████░  90% →  90%   (刚冻结)
Process Architecture   ██░░░░░░░░  20% →  60%   ⬅️ Phase 15
Decision Architecture  ███░░░░░░░  30% →  30%
Execution Architecture █░░░░░░░░░  10% →  10%
Learning Architecture  ████░░░░░░  40% →  40%
```

### Phase 路线图

```
Phase 14 — Information Foundation         ✅
Phase 15 — Process Foundation             ⬅️ 当前
Phase 16 — Decision Foundation            待开始
Phase 17 — Planning / Goal Intelligence   待开始
Phase 18 — Agent Evolution                待开始
```

---

## 八、代码行统计

| 组件 | 行数 | 状态 |
|------|------|------|
| `ocos/models/process.py` | **0** | ❌ 待创建 |
| `docs/PROCESS_THEORY.md` | **0** | ❌ 待创建 |
| `ocos/platform/trace_engine.py` — ReasoningTrace | ~33 | ✅ 待接入 |
| `ocos/models/information.py` — SemanticRole | 1 | 🟡 保留至 v2.0 |

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | 初始审计（核心错误：缺 reasoning_engine.py） |
| v1.1 | 2026-07-22 | 第一轮校准：Engine 不堆叠，Reasoning = Transform Process |
| v1.2 | 2026-07-22 | 第二轮校准：Model 不堆叠，models/process.py 而非 reasoning.py |
| **v1.3** | 2026-07-22 | **第三轮校准：层命名不堆叠。L4 = Process Theory，非 Reasoning Theory。Phase 15 从 Reasoning Foundation 更名为 Process Foundation。统一 TransformProcess + process_type，不创建独立 Process dataclass。SemanticRole.REASONING 最终判断：v2.0 删除，替换为 BELIEF/HYPOTHESIS/CONCLUSION。** |
