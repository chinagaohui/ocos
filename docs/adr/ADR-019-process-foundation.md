# ADR-019: Process Foundation — 认知过程层冻结证书

| 属性 | 值 |
|------|-----|
| **ADR 编号** | 019 |
| **状态** | Accepted |
| **日期** | 2026-07-22 |
| **发起人** | OCOS 架构评审（Reasoning Audit v1.0 → v1.3） |
| **影响范围** | `ocos/models/process.py`, `ocos/kernel/abi.py`, `ocos/kernel/event_schema.py`, `ocos/platform/trace_engine.py`, `docs/PROCESS_THEORY.md` |
| **前置依赖** | ADR-018 (Architecture Theory Calibration), Phase 14 Information Foundation |

---

## 背景

OCOS 在完成 Information Foundation（Phase 14）后，需要建立"认知过程"的统一抽象层。Reasoning Audit v1.3 经过三轮校准，确定了以下关键发现：

### 架构问题

1. **Reasoning 没有理论定位** — Reasoning 相关接口存在（`Decision.reasoning`、`ReasoningTrace`），但缺少"推理是什么"的本体模型。
2. **独立 Engine 陷阱** — 初期方案错误地倾向创建 `reasoning_engine.py`，违反了 OCOS 的"Information 不嵌入行为"原则。
3. **独立 Model 陷阱** — 后续方案又倾向创建 `models/reasoning.py`，违反了"Model 不堆叠"原则。
4. **层命名陷阱** — 初始 L4 定位为"Reasoning Theory"，会将一种能力提升为架构层，重复 Memory 的错误。
5. **Capability 扩散风险** — 缺少统一的认知能力注册机制，未来每新增一种能力（Reflection、Negotiation等）都可能产生新的 Engine、Theory 或 Data Model。

### 根本原因

OCOS 缺少一个统一的"认知过程"抽象层。Reasoning、Decision、Planning、Simulation、Learning 都是同一种抽象（Process）的不同实例，但此前架构层没有定义这个抽象。

---

## 决策

### 1. L4 = Process Theory，非 Reasoning Theory

```
过去（错误）：        L0 Information → L1 Graph → L2 Lifecycle → L3 Knowledge → L4 Reasoning
现在（正确）：        L0 Information → L1 Graph → L2 Lifecycle → L3 Knowledge → L4 Process
```

Reasoning 降级为 ProcessType 的一个成员，不再作为独立的架构层。

### 2. 统一 Process 数据模型

创建 `ocos/models/process.py`，包含：

- `ProcessType` — 所有认知过程的统一枚举（Reasoning、Decision、Planning、Simulation、Learning）
- `ProcessState` — 过程运行状态（CREATED、RUNNING、COMPLETED、FAILED）
- `ProcessStep` — 过程中的单个步骤
- `TransformProcess` — 认知过程的统一表示

TransformProcess 的四条不变量：
1. **不拥有 Information** — 使用地址引用，不嵌入内容
2. **不改变生命周期** — 由 Lifecycle Engine 管理
3. **不执行 Action** — 由 Execution 层处理
4. **必须引用 Evidence** — 可追溯审计

### 3. 统一 Process 事件

使用 INFORMATION_TRANSFORMATION_STARTED / COMPLETED / FAILED 三个统一事件，通过 `process_type` 字段区分具体能力。不按 ProcessType 拆分独立事件。

### 4. Process → Trace 统一入口

`TraceEngine.record_process_trace()` 作为 Process 到 Trace 的唯一入口，内部按 ProcessType 自动分发。

---

## 被否决的方案

| 方案 | 否决原因 | 对应原则 |
|------|----------|---------|
| 创建 `reasoning_engine.py` | 认知能力不是独立 Engine；Information 不嵌入行为 | Engine 不堆叠 |
| 创建 `models/reasoning.py` | 认知能力应使用统一 TransformProcess + process_type | Model 不堆叠 |
| 创建 `REASONING_THEORY.md` | L4 描述的是抽象范畴（Process），不是某一种能力 | 层命名不堆叠 |
| 按能力驱动扩展（新增 Reflection → 新增 Theory + Engine + Model） | 新增能力只增加 ProcessType 成员，不新增架构边界 | Capability 不堆叠 |

---

## 影响

### 新增文件

| 文件 | 说明 |
|------|------|
| `ocos/models/process.py` | Process 数据模型（~150 行） |
| `ocos/tests/test_process_model.py` | Process 模型测试 |
| `ocos/tests/test_transformation_events.py` | Transform 事件测试 |
| `ocos/tests/test_process_trace_integration.py` | Process→Trace 集成测试 |
| `ocos/tests/test_architecture_principles.py` | 四条不堆叠原则架构约束测试 |
| `docs/PROCESS_THEORY.md` | L4 Process 理论文档（待创建） |

### 修改文件

| 文件 | 说明 |
|------|------|
| `ocos/models/__init__.py` | 导出 Process 模块 |
| `ocos/kernel/abi.py` | EventType 添加 3 个 Transform 事件 |
| `ocos/kernel/event_schema.py` | 注册 3 个事件 schema |
| `ocos/platform/trace_engine.py` | 添加 record_process_trace() 统一入口 |
| `ocos/tests/test_import_rules.py` | 开通 platform → models 依赖路径 |

### 不修改的文件

- `ocos/kernel/abi.py` 中的 `Decision.reasoning` 字段 — v1.x 保持兼容
- `ocos/models/information.py` 中的 `SemanticRole.REASONING` — v1.x 保持兼容，v2.0 拆除
- `ocos/kernel/abi.py` 中的 `SCHEMA_VERSION` — 不变
- `ocos/runtime/` 下的所有文件 — 不涉及

### 兼容性

- 所有现有 Engine：0 改动
- 所有现有测试：1187 全部通过
- ABI：`Decision.reasoning: str` 不变，`SemanticRole.REASONING` 保留

---

## 架构原则固化

四条"不堆叠"原则通过 `test_architecture_principles.py` 固化为可执行约束：

1. 不存在 `reasoning_engine.py` / `planning_engine.py` 等认知 Engine
2. 不存在 `models/reasoning.py` 等独立认知 Model
3. 不存在 `REASONING_THEORY.md` / `DECISION_THEORY.md` 等独立 Theory
4. ProcessType 枚举是认知能力注册的唯一入口

---

## 后续路线

| Phase | 内容 | 依赖 |
|-------|------|------|
| Phase 16 | Decision Foundation | Phase 15 Process Foundation |
| Phase 17 | Planning/Goal Intelligence | Phase 16 |
| Phase 18 | Agent Evolution | Phase 17 |

v2.0 路线：
- `SemanticRole.REASONING` 拆分为 ProcessType.REASONING + 新的 Information Role（BELIEF / HYPOTHESIS / CONCLUSION）
- `Decision.reasoning: str` 替换为 `reasoning_reference: UniversalAddress`

---

## 参考资料

- `docs/design/Phase15-Process-Foundation.md` — Phase 15 设计提案
- `docs/OCOS_REASONING_AUDIT.md` v1.3 — 三轮校准完整记录
- `docs/OCOS_CORE_CONSTITUTION.md` — 宪法依赖方向规则
- `docs/adr/ADR-018-architecture-theory-calibration.md` — 前置 ADR
