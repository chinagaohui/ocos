# PROCESS THEORY — OCOS 认知过程层

**版本**: v1.0（冻结中）
**状态**: Frozen（Phase 15 — Process Foundation）
**所属层级**: L4 Process Theory
**前置依赖**: L0 Information Theory ✅, L2 Information Lifecycle ✅

---

## 0. 术语三要素

本文档中的三个核心术语有严格区分，不得混用：

| 术语 | 含义 | 示例 |
|------|------|------|
| **Process** | 认知过程的抽象概念 | "Reasoning 是一种 Process" |
| **Transformation** | Process 执行的行为：Information → Information | "Observation 到 Hypothesis 的 Transformation" |
| **TransformProcess** | Process 的统一数据模型（frozen dataclass） | `TransformProcess(process_type=REASONING)` |

**命名规则**：
- 讨论架构理论时用 **Process**
- 讨论转换行为时用 **Transformation**
- 讨论数据结构时用 **TransformProcess**

---

## 1. 为什么需要 Process

OCOS 在完成 Information Foundation 后，回答了"系统知道什么"（Knowledge）和"系统记住什么"（Memory）。但缺少一个核心抽象：

**Information 从一种状态变化为另一种状态时，中间发生了什么？**

```
观察（Observation）    → 假设（Hypothesis）
知识（Knowledge）      → 新知识（New Knowledge）
直觉（Preference）     → 决策（Decision）
场景（Scenario）       → 预测（Prediction）
```

这些变化不是 Information 自身完成的。它们是由 **Process** 完成的。

Process 是 OCOS 中"认知过程"的统一抽象。它不是某一种能力（如推理），而是所有认知过程的共同描述框架。

---

## 2. Process 的定义

**Process** 是 Information 之间的一类转换过程。它以 Information 为输入，经过一系列步骤，产生新的 Information 作为输出。

```
形式化定义：
  Process: (Input: Information[]) → Step[] → (Output: Information[])
  
  约束：
  - Process 不拥有 Information（使用地址引用）
  - Process 不改变 Information 生命周期
  - Process 不直接执行 Action
  - Process 的执行历史由 Trace 记录
```

Process 不是"活动中的信息"。Process 是描述"信息如何被转换"的不可变记录。

### 2.1 ProcessType 不表示复杂度

**ProcessType 只表示一种 Transformation 类型，不表示实现复杂度。**

```
ProcessType 对比示例：
  REASONING:    Observation + Knowledge → Conclusion    （多步推理）
  DECISION:     Conclusion + Goal + Policy → Decision   （信息汇聚仲裁）
  PLANNING:     Goal + WorldState → Plan                （步骤编排）
  SIMULATION:   Decision + Context → Outcome            （假设推演）
```

例如 Decision 虽然看起来只是"将多个 Information 汇聚生成新的 Decision Information"，但它确实完成了一次 Information → Information 的转换，因此符合 Process 定义。

但即使未来 Decision 变得复杂（Goal Arbitration + Utility Evaluation + Policy Validation），它仍然是 Decision Process，无需升级为独立的 Engine 或 Theory。

**原则**: 复杂度不是区分 ProcessType 的理由。只有 Transformation 的语义不同才需要新增 ProcessType。

---

## 3. Process 在 OCOS 架构中的位置

### 3.1 OCOS 四层模型

```
┌──────────────────────────────────────────────────────────┐
│                      OCOS Architecture                     │
├──────────────────────────────────────────────────────────┤
│  Information（L0） —— 静态对象（What）                     │
│  Lifecycle（L2）   —— 状态变化（How it changes state）     │
│  Process（L4）     —— 认知转换（How information transforms）│
│  Trace（C1）       —— 历史证明（What happened）            │
│  Governance（C3）  —— 约束规则（What is allowed）          │
└──────────────────────────────────────────────────────────┘
```

### 3.2 与 Information 的关系

| 维度 | Information | Process |
|------|------------|---------|
| 本质 | 静态数据 | 转换描述 |
| 生命周期 | 有状态变化 | 有运行状态 |
| 引用方式 | UniversalAddress | 引用 Information 的 Address |
| 持久性 | 持久化存储 | 完成后记录在 Trace 中 |

**Process 引用 Information，但不嵌入 Information。** Process 的 input/output 字段全部使用 `UniversalAddress`，不包含实际数据。这保证了：

- Process 不引入数据耦合
- Process 可序列化、可审计
- Information 始终保持统一访问入口

### 3.3 与 Lifecycle 的关系

Process 是 Lifecycle 中 **Transform** 阶段的具体实现。

```
Information Lifecycle:
  Acquire → Validate → Transform → Decay/Archive/Promote
                            │
                    Process 在此阶段
```

但 Process 不控制 Lifecycle。如果 Process 成功产生了新的 Information，由 Lifecycle Engine 更新 Information 状态。Process 只记录"我用了哪些 Information"和"我产生了哪些 Information"。

### 3.4 与 Trace 的关系

Process 完成后，转为 Trace 记录。

```
Process（正在发生的认知过程）→ 完成 → Trace（不可变历史证明）

对应关系：
  TransformProcess  →  TraceRecord
  process_type      →  TraceType
  process_id        →  trace_id (部分)
  steps             →  步骤描述
  input_addresses   →  输入引用
  output_addresses  →  输出引用
```

Trace 是 Process 的历史持久化形态。Process 是 Trace 的实时生成源。

### 3.5 与 Governance 的关系

Governance 不直接作用于 Process 数据类型，但作用于 Process 允许使用的 Information 范围和结果。

- Governance 可以审计 Process 的合法性
- Governance 可以拒绝 Process 产生的输出
- Process 自身仅记录，不判断

---

## 4. ProcessType 扩展原则

### 4.1 准入条件

新增 ProcessType 必须满足以下全部条件：

| 条件 | 说明 | 验证方式 |
|------|------|----------|
| 1 | 该能力是否是 Information 之间的转换过程？ | 必须有 input → output 的转换语义 |
| 2 | 输入输出是否可以用 Address[] 描述？ | 不能嵌入实际数据 |
| 3 | 是否可以通过 Trace 记录其执行历史？ | Trace 层必须有对应的 TraceType 实现 |

### 4.2 最高优先级：复用现有 ProcessType

**在新增 ProcessType 之前，必须优先确认是否能通过现有 ProcessType 表达。**

| 新能力 | 是否可复用？ | 建议 |
|--------|-------------|------|
| Reflection | 可复用 Reasoning | Reflection = 对自身推理过程的 Reasoning |
| Verification | 可复用 Reasoning | Verification = 比较预期与实际结果的 Reasoning |
| Checking | 可复用 Reasoning | Checking = Verification 的同义变体 |
| Inspection | 可复用 Reasoning | Inspection = 结构化观察 |
| Evaluation | 可复用 Decision | Evaluation = 对选项的 Decision |
| Optimization | 可复用 Planning | Optimization = Planning + 搜索策略 |
| Negotiation | 可复用 Decision | Negotiation = 多参与方 Decision |
| Self-Repair | 多种 Process 组合 | 不属于单一 ProcessType，属于编排层 |

**原则**: 只有当新能力无法表达为现有 ProcessType，且其生命周期、输入输出契约、治理规则均与现有 ProcessType 不同时，才允许新增 ProcessType。

**验证方法**: 在新增 ProcessType 之前，先尝试用 `ProcessType.REASONING` 或 `ProcessType.DECISION` 描述该能力。如果语义完全匹配，则不新增。

### 4.3 禁止操作

**不满足上述条件的情况：**

- 无法用 Information 转换描述的能力 → 不是 Process
- 需要嵌入复杂执行逻辑的能力 → 属于能力实现层（Phase 18+）
- 仅读取不产生输出的能力 → 属于 Information 查询

### 扩展操作步骤

```python
# 1. 在 ProcessType 枚举中添加新成员
class ProcessType(str, Enum):
    REASONING = "reasoning"
    # NEW_CAPABILITY = "new_capability"

# 2. 在 TraceEngine 中添加对应的记录路由方法
# 3. 通过 record_process_trace() 统一入口调用
```

禁止：
- 为新增 ProcessType 创建新的 Engine 文件
- 为新增 ProcessType 创建新的 Theory 文档
- 为新增 ProcessType 创建新的数据模型文件
- 为新增 ProcessType 创建独立事件类型

---

## 5. TransformProcess 统一契约

所有 TransformProcess 实例必须遵守以下契约：

### 5.1 不可变

```python
@dataclasses.dataclass(frozen=True)
class TransformProcess:
    process_id: str
    process_type: ProcessType
    process_state: ProcessState
    input_addresses: tuple[UniversalAddress, ...]
    output_addresses: tuple[UniversalAddress, ...]
    steps: tuple[ProcessStep, ...]
    confidence: float
    metadata: dict[str, Any]
    schema_version: str
```

Process 实例一旦创建，不可修改。这是为了：

- 支持审计（历史记录不可篡改）
- 支持引用（其他组件可以安全引用 Process）

### 5.2 输入输出统一契约

所有 TransformProcess 实例的输入输出字段**只能使用 UniversalAddress[]**，不允许为特定 ProcessType 创建特殊字段。

```python
# ✅ 正确：统一使用 UniversalAddress[]
process = TransformProcess(
    input_addresses=(addr_observation, addr_knowledge),
    output_addresses=(addr_conclusion,),
)

# ❌ 禁止：为特定 ProcessType 创建特殊字段
# class PlanningProcess:
#     goal: str              # 禁止
#     memory: str            # 禁止
#     simulation_results: ... # 禁止

# ❌ 禁止：在 TransformProcess 中增加特殊字段
# TransformProcess(
#     goal=...,              # 禁止
#     observation=...,       # 禁止
# )
```

理由：
- 统一 Address 访问：所有 Information 通过 UniversalAddress 引用，不引入数据耦合
- 防止模型分叉：如果允许特殊字段，PlanningProcess 会有 `goal`，SimulationProcess 会有 `scenario`，最终回到多 dataclass 状态
- 序列化一致性：所有 ProcessType 共享同一序列化/反序列化路径

非 Addressable 的数据（如算法参数、临时状态）放入 `metadata: dict`。

### 5.3 不变量

| 不变量 | 违反示例 | 后果 |
|--------|----------|------|
| 1. 不拥有 Information | 在 TransformProcess 中加入 `content` 字段 | 引入耦合，破坏统一访问 |
| 2. 不控制生命周期 | Process 调用 `state.transition_to()` | 职责蔓延，越权 |
| 3. 不执行 Action | Process 包含 `execute()` 方法 | 违反 Separation of Concerns |
| 4. 引用 Evidence | Process 不记录 input/output | 无法审计 |

### 5.3 生命周期

```
CREATED → RUNNING → COMPLETED
                 ↘ FAILED
```

ProcessState 仅描述 Process 自身的运行状态，不描述 Information 的状态。

---

## 6. Process → Trace 映射规则

### 6.1 通用映射

| TransformProcess 字段 | TraceRecord 字段 |
|----------------------|-----------------|
| `process_id` | 映射到对应 Trace 的 `*_id` 字段 |
| `steps[].description` | 映射到对应 Trace 的步骤/chain 字段 |
| `input_addresses` | 映射到对应 Trace 的输入引用字段 |
| `metadata` | 映射到 metadata |
| `process_type` | 决定目标 TraceType |

### 6.2 具体映射

| ProcessType | Target TraceType | 关键映射 |
|------------|-----------------|----------|
| REASONING | ReasoningTrace | `output_addresses` → `conclusion` |
| DECISION | DecisionTrace | `steps` → `reasoning_chain`, `confidence` → `confidence` |
| SIMULATION | SimulationTrace | `metadata.scenario` → `scenario` |
| LEARNING | LearningTrace | `metadata.new_knowledge` → `new_knowledge` |

### 6.3 统一入口

所有 Process 通过 `TraceEngine.record_process_trace()` 完成映射，外部组件不需要知道内部路由逻辑。

### 6.4 长期演进方向

当前 `record_process_trace()` 内部通过 `process_type` 映射到 4 个专用路由方法。长期方向为：

```
当前（Phase 15）:
  record_process_trace(process) → dispatch by process_type → _record_reasoning_from_process()
                                                          → _record_decision_from_process()
                                                          → _record_simulation_from_process()
                                                          → _record_learning_from_process()

长期愿景（ProcessTrace 统一后）:
  record_process_trace(process) → record_generic_trace(process)
```

目标是消除按 ProcessType 拆分的路由方法，使 `record_process_trace()` 成为唯一的 Trace 记录入口。当新增 ProcessType 时，只需扩展 Trace 数据模型，无需新增 API。

---

## 7. Process 与能力实现层的关系

### 7.1 职责分离

```
Phase 15 — Process Foundation（当前）
  定义 Process 是什么（抽象层）
  定义 ProcessType 有哪些（注册层）
  定义 Process → Trace 映射（接入层）

Phase 18+ — 能力实现层（未来）
  实现 Reasoning 算法
  实现 Planning 引擎
  实现 Learning 机制
```

### 7.2 边界规则

| 属于 Process 层 | 不属于 Process 层 |
|----------------|-----------------|
| Process 数据模型 | 算法实现 |
| ProcessType 注册 | LLM 调用 |
| Process → Trace 映射 | 执行引擎 |
| 事件发射 | 资源管理 |

---

## 8. 版本说明

### v1.0（当前）

- `ProcessType` 包含 5 个成员：REASONING, DECISION, PLANNING, SIMULATION, LEARNING
- `SemanticRole.REASONING` 保持兼容（v2.0 拆除）
- `Decision.reasoning: str` 保持兼容（v2.0 替换为 `reasoning_reference`）
- `TraceEngine.record_process_trace()` 支持 4 种 ProcessType
- PLANNING 类型已注册但尚未完成 Trace 接入

### v2.0 计划

- `SemanticRole.REASONING` 拆分为 ProcessType.REASONING + 新的 Information Role
- `Decision.reasoning` 迁移为 `reasoning_reference: UniversalAddress`
- 统一 ProcessTrace 替代现有的 4 个独立 TraceRecord 类
