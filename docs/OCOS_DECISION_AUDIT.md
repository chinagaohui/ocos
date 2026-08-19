# OCOS DECISION AUDIT v1.0

**状态**: Draft
**日期**: 2026-07-22
**审计范围**: Decision ABI、Trace、Event、PolicyEngine、Scheduler、Goal、Process 边界
**前置审计**: Memory Audit ✅, Process Audit (原 Reasoning Audit) ✅

---

## 1. 当前架构扫描

### 1.1 Decision ABI (ocos/kernel/abi.py)

```python
@dataclasses.dataclass(frozen=True)
class Decision:
    decision_id: str
    goal_id: str
    reasoning: str         # 决策理由（供 Audit 使用）
    confidence: float       # 0.0~1.0
    status: str             # formed | validated | executing | completed | failed
    timestamp: str
    schema_version: str
```

消费者:
- `ocos/runtime/policy_engine.py` — `decision_id` 字段在 Action 参数中检查
- `ocos/platform/trace_engine.py` — `DecisionTrace` 记录
- `ocos/runtime/scheduler.py` — 订阅 `ACTION_SCHEDULED` (下游)

### 1.2 Effect Trace (ocos/platform/trace_engine.py)

```python
@dataclass(frozen=True)
class DecisionTrace:
    trace_id, trace_type, source, timestamp, schema_version, metadata
    decision_id: str
    goal_id: str
    reasoning_chain: list[str]
    confidence: float
    outcome: str            # accepted | rejected | deferred
    alternatives: list[str]
```

此外 `_record_decision_from_process()` 将 TransformProcess 映射为 DecisionTrace。

### 1.3 Decision 事件

| EventType | 位置 |
|-----------|------|
| `DECISION_FORMED = "decision.formed"` | abi.py pre-Process block |
| `DECISION_VALIDATED = "decision.validated"` | abi.py pre-Process block |
| `INFORMATION_TRANSFORMATION_*` | abi.py Phase 15 block（通用事件） |

### 1.4 Decision 在 ProcessType 中

```python
class ProcessType(str, Enum):
    DECISION = "decision"
```

TransformProcess 通过 `record_process_trace()` 可分发到 `_record_decision_from_process`。

### 1.5 Relation 图

```
Decision ──goal_id──→ Goal
Decision ──trace──→ DecisionTrace (through record_decision_trace)
TransformProcess(process_type=DECISION) ──record_process_trace──→ DecisionTrace

PolicyEngine ──evaluate──→ Action params (check decision_id exists)
Scheduler ──subscribes──→ ACTION_SCHEDULED (Decision 不直接参与调度)
```

---

## 2. 核心发现

### 🔴 2.1 宪法冲突：Rule 10 禁止 Kernel 包含 Decision

**问题**: 宪法 Rule 10 `KERNEL_NEVER_KNOWS_BUSINESS` 明确规定：
> "Kernel must NOT contain Memory, Knowledge, Identity, Policy, Decision. Kernel does not understand business logic."

但 `Decision` 类定义在 `ocos/kernel/abi.py`（同文件还有 `Goal`、`Knowledge`、`Memory` 类）。

**严重等级**: **高**
**影响**: 宪法与代码矛盾。未来如新增 Rule 10 的自动化测试拒绝 `Decision in kernel`，当前代码会测试失败。

**可能解释**: abi.py 是最早期（Phase 0-1）产物，当时 Decision/Goal/Memory/Knowledge 被放在 Kernel 中作为"ABI 契约"。Rule 10 是 Phase 8+ 引入的，未回扫 Kernel 内容。

**建议**: 
- v1.x：在宪法描述中加注豁免 — "abi.py 作为 ABI 契约包含 Decision 定义（核心业务模型的场所），不视为 Rule 10 违反"
- v2.0：将 Decision 从 abi.py 迁移到 `ocos/models/decision.py`（或通过 `models/information.py` 重构）

### 🟡 2.2 Decision 的身份不明：Information vs Process

**问题**: Decision 目前是独立 frozen dataclass，同时 `ProcessType.DECISION` 已存在。但两者无关联。

当前状态：
```
Decision 类：独立 dataclass，不走 TransformProcess
ProcessType.DECISION：存在于枚举，可通过 record_process_trace 分发
```

双轨设计的后果：
1. 创建 Decision 的代码直接 `Decision(...)` + `record_decision_trace(...)`，不经过 TransformProcess
2. Process 统一入口 `record_process_trace()` 无法覆盖通过 `Decision()` 构造函数创建的传统路径
3. ProcessType.DECISION 的 Trace 映射和 Decision 类的 Trace 映射是两套独立逻辑

**严重等级**: **中**
**影响**: Process 统一抽象在 Decision 环节有裂缝。

**建议**:
- Phase 16 冻结 Decision Model 时二选一：
  - **方案 A**: Decision = Process 的输出 Information（即 Reasoning/Planning Process 产出的 `Role=DECISION` 的 Information）。`Decision` 类合并到 Information 模型中，`decision_id` = Information Address。
  - **方案 B**: Decision 本身就是一种 Process（TransformProcess+process_type=DECISION），`Decision` 类是 TransformProcess 的运行时视图。两者通过 `process_id` 关联。

### 🟡 2.3 Decision 生命周期状态

**问题**: `Decision.status` 使用字符串 `"formed" | "validated" | "executing" | "completed" | "failed"`，由外部代码手动设置。没有统一的状态机。

与 ProcessState 对比：
| Decision 状态 | ProcessState 等价 | 说明 |
|--------------|------------------|------|
| formed | CREATED | ✅ 一致 |
| (无) | RUNNING | ⚠️ Decision 缺少"运行中"状态 |
| validated | (无) | Decision 特有（Governance 验证） |
| executing | (无) | Decision 特有（Action 执行中） |
| completed | COMPLETED | ✅ 一致 |
| failed | FAILED | ✅ 一致 |

**严重等级**: **低**
**建议**: 如果 Decision 是 Process（方案 B），状态可直接复用 ProcessState。如果 Decision 是 Information（方案 A），状态由 Information Lifecycle 管理。

### 🟡 2.4 Decision Trace 与 Process Trace 双轨

**问题**: 两种创建 DecisionTrace 的路径：

1. 传统路径：`engine → record_decision_trace(...)` 
2. Process 路径：`TransformProcess(process_type=DECISION) → record_process_trace(process)`

两路径最终都生成 `DecisionTrace`，但 input 格式不同：
- 传统路径：直接传 `decision_id`, `reasoning_chain`, `confidence` 等参数
- Process 路径：从 TransformProcess 解构 `steps` → `reasoning_chain`, `input_addresses` → 忽略, `confidence` → 复用

Phase 15 已明示长期方向为统一入口。Decision Audit 应确认此方向。

### 🟢 2.5 Event 检查

**问题**: 
- `DECISION_FORMED` 和 `DECISION_VALIDATED` 是 Legacy 事件
- Phase 15 引入了 `INFORMATION_TRANSFORMATION_STARTED / COMPLETED / FAILED`

**建议**:
- 如果 Decision 是 Process（方案 B）：Decision 应触发 TRANSFORMATION 事件（`process_type=DECISION`），v1.x 保留 DECISION_FORMED 兼容，v2.0 移除
- 如果 Decision 是 Information（方案 A）：保留 DECISION_FORMED/DECISION_VALIDATED

### 🟢 2.6 Decision 与 PolicyEngine 关系

PolicyEngine 的 `decision-required` 规则已验证：`execute_engine` 动作必须携带 `decision_id`。此设计正确：
- Decision 是 Action 的授权源
- PolicyEngine 不直接操作 Decision 类，只检查 `decision_id` 存在性
- Governance 事件驱动策略更新，不影响 Decision 生命周期

**结论**: ✅ 正确。不需要改动。

### 🟢 2.7 Decision 与 Scheduler 关系

Scheduler 不直接订阅 Decision 事件。它订阅 `ACTION_SCHEDULED`，在 Action 级别工作。

**结论**: ✅ 正确。Scheduler 不关心 Decision 如何形成，只关心 Action 何时执行。

### 🟢 2.8 Decision 与 Goal 关系

`Decision.goal_id: str` 引用 Goal。方向正确：Goal → Decision → Action。

但 Goal 类本身也需要审计（属于 Goal Audit 范围，此处仅标记交叉点）。

---

## 3. 决策方案评估

### 方案 A: Decision = Information (Role=DECISION)

```
Information {
    address: UniversalAddress
    role: DECISION
    content: { decision_id, goal_id, confidence, alternatives }
}
Process → TransformProcess(process_type=REASONING) → output_addresses=[addr_decision]
```

**优点**:
- ❄️ Process 抽象统一：Decision 不是 Process，是 Process 的输出
- Information 模型完整：Decision 继承 Information 的全部能力（Lifecycle、Address、Query）
- TransformProcess 契约纯净：不需要为 DECISION 做特殊处理
- 🟢 ADR-004 "Reasoning as Non-Decision" 一致

**缺点**:
- 现有 `Decision` 类废弃，迁移成本高
- Constitution Rule 1 "Decision is only Action source" 需要重新术语化
- PolicyEngine 的 `decision_id` 检查需要兼容 Information Address 格式

### 方案 B: Decision = Process (process_type=DECISION)

```
TransformProcess(process_type=DECISION) {
    process_id = decision_id
    input_addresses = [addr_conclusion, addr_goal, addr_policy]
    output_addresses = [addr_decision]
}
Decision 类 = TransformProcess 的运行时视图
```

**优点**:
- ProcessType 枚举的一致性：所有认知过程都是 Process
- Process → Decision → Action 链路自然
- 与 Phase 15 设计一致（process_type 已包含 DECISION）
- Trace 统一：一个 `record_process_trace()` 覆盖所有 Process

**缺点**:
- Decision 的"生命周期"（formed → validated → executing → completed）与 ProcessState（CREATED → RUNNING → COMPLETED/FAILED）不完全对齐
- "Decision 是唯一的 Action Source" 在 Process 模型下需要重新表达（Process 不执行 Action）
- 需要定义"Decision 何时完成"的明确语义

### 对比

| 维度 | 方案 A (Information) | 方案 B (Process) |
|------|---------------------|------------------|
| 与 Phase 15 一致性 | ❌ 冲突（已注册 DECISION ProcessType） | ✅ 一致 |
| 迁移成本 | 高（新数据模型，废弃 Decision 类） | 低（复用 TransformProcess） |
| 实现复杂度 | 低（无运行时状态） | 中（需建立运行时视图） |
| 与宪法 Rule 1 一致性 | 🟡 需重新术语化 | ✅ 保持 |
| Trace 统一 | ✅ 一个 record_process_trace | ✅ 一个 record_process_trace |
| 信息模型完整性 | ✅ 完整 | 🟡 需额外建设 |

---

## 4. 发现总结

| # | 项目 | 严重度 | 状态 | 建议 |
|---|------|--------|------|------|
| F1 | Decision 在 Kernel 违反宪法 Rule 10 | 🔴 高 | 未解决 | v1.x 加注豁免，v2.0 迁移 |
| F2 | Decision 身份不明（Information vs Process） | 🟡 中 | 待定决 | 在方案 A/B 中选择 |
| F3 | Decision 生命周期与 ProcessState 不匹配 | 🟡 中 | 待定决 | 决策后统一 |
| F4 | Decision Trace 有传统/Process 双路径 | 🟡 中 | 部分解决 | Phase 15 已设立统一入口，传统路径逐步迁移 |
| F5 | DECISION_LEGACY 事件与 TRANSFORMATION 事件并存 | 🟢 低 | 待定决 | 决策后决定保留/废弃 |
| F6 | Decision ↔ PolicyEngine 关系 | 🟢 正常 | ✅ 正确 | 无改动 |
| F7 | Decision ↔ Scheduler 关系 | 🟢 正常 | ✅ 正确 | 无改动 |
| F8 | Decision ↔ Goal 关系 | 🟢 正常 | ✅ 正确 | 架构正确，Goal Audit 覆盖 |

---

## 5. 推荐结论

### 关于身份 (F2+F3)

**推荐方案 B（Decision = Process）**。理由：

1. **与 Phase 15 一致** — ProcessType.DECISION 已注册，`record_process_trace` 已支持 DECISION 分发
2. **迁移成本最低** — 复用 TransformProcess 数据模型，不需要新建 Information Role
3. **闭环完整**— Information → Process → Decision → Action → Observation → Information
4. **Trace 统一** — 一个入口覆盖所有 ProcessType

需要在 DECISION_MODEL.md 冻结时解决的问题：
- Decision 作为 Process 的"完成"语义（ProcessState.COMPLETED 对应 Decision 可执行）
- Decision 的 governance validation 作为 Process 的一个 Step，而非独立状态
- Decision 的 Executing 状态下放到 Action 层（Decision Process 本身在 COMPLETED 状态）

### 关于宪法 (F1)

在宪法 `KERNEL_NEVER_KNOWS_BUSINESS` 描述中加注豁免：

> "abi.py 作为 ABI 契约层包含 Decision、Goal、Knowledge 的定义（核心业务模型的场所）。这些是 OCOS 的最基本业务概念，定义在 Kernel 中层是架构冻结期的权宜计策。v2.0 将转移到 models/ 目录。"

### 关于 Trace (F4)

- 淘汰传统 `record_decision_trace()` 的直接调用
- 所有 Decision 统一通过 `TransformProcess(process_type=DECISION) → record_process_trace()` 记录
- 传统 API 标记为 deprecated（但保留 ABI 兼容直到 v2.0）

### 关于 Event (F5)

- 如果 Decision = Process：废弃 `DECISION_FORMED` 和 `DECISION_VALIDATED`，统一使用 INFORMATION_TRANSFORMATION 事件
- v1.x 保留两个 legacy 事件（使用 `event_schema.mark_deprecated`）
- v2.0 移除

---

## 6. 后续工作

| 步骤 | 交付物 | 预估 |
|------|--------|------|
| 冻结 DECISION_MODEL.md | Decision 数据模型文档 | 审计后 |
| Decision ABI 迁移或适配 | 选择方案 A/B 并实现 | 冻结后 |
| Decision Trace 统一 | 淘汰传统 API | Phase 16 |
| Decision 宪法豁免 | 更新 constitution.py 注释 | 立即 |
| Goal Audit | 审计 Goal 系统 | Decision Audit 后 |
