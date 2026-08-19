# OCOS Platform Constitution v1.0

**版本**: v1.0
**状态**: Frozen
**冻结日期**: 2026-07-22
**适用范围**: OCOS 认知操作系统平台，所有 Engine、Plugin、Runtime 组件均受本宪法约束。
**不可变原则**: 宪法中标记为「不可变」的条款，任何修改须经架构委员会全票通过，并执行全平台兼容性验证。

---

## 前言

本宪法是 OCOS 平台的最高准则，定义了系统的对象模型、通信协议、治理规则和演化机制。任何模块、插件、外部能力接入，都必须遵守本宪法。宪法不规定具体实现（算法、模型），但规定了所有组件之间的边界和交互方式。

本宪法冻结后，OCOS 从"架构设计阶段"进入"平台实现阶段"。后续新增 Engine、Plugin、行业应用，均在本宪法框架内进行，无需修改核心架构。

---

## 第一部分：核心对象模型 (Object Model)

所有模块共享统一的对象定义。对象分为 **不可变核心对象** 和 **可扩展对象**。

### 1.1 不可变核心对象

这些对象的结构一经冻结，永不可变。所有 Engine 必须使用相同的定义，且不能添加、删除或修改字段语义。

#### Observation（观察）
- `observation_id: UUID`
- `source: str`               // 来源（Perception / Event / User）
- `type: str`                 // 观察类型（TEXT / IMAGE / AUDIO / EVENT）
- `content: dict`             // 结构化观察内容
- `timestamp: datetime`
- `confidence: float`         // 提取/感知的置信度

#### Memory（记忆）——四种子类型共用基类
- `memory_id: UUID`
- `memory_type: enum`        // WORKING / SEMANTIC / EPISODIC / PROCEDURAL
- `content: dict`
- `created_at: datetime`
- `last_accessed: datetime`
- `access_count: int`
- `strength: float`           // 记忆强度，用于遗忘算法
- `source_observation_ids: list[UUID]`

> ⚠️ **本模型已废弃（v1.0 冻结后待修订）**：Memory 的四子类型模型应被 [INFORMATION_THEORY.md](./INFORMATION_THEORY.md) 的二维坐标系（PersistenceLevel × SemanticRole）替代。当前保留以维护 ABI 向后兼容，v2.0 将依据 INFORMATION_THEORY 重构。

#### Knowledge（知识）
- `knowledge_id: UUID`
- `type: str`                 // PRINCIPLE / PATTERN / RULE / MODEL
- `content: dict`
- `evidence_chain: list[UUID]`// 支持该知识的 Evidence ID 列表
- `confidence: float`
- `status: enum`              // CANDIDATE / VERIFIED / ACTIVE / DEPRECATED / ARCHIVED
- `created_at: datetime`
- `updated_at: datetime`
- `version: int`

#### Goal（目标）
- `goal_id: UUID`
- `description: str`
- `priority: int`
- `parent_goal_id: UUID|null`
- `status: enum`              // ACTIVE / SUSPENDED / COMPLETED / FAILED
- `created_at: datetime`

#### Decision（决策）
- `decision_id: UUID`
- `type: str`                 // ACTION / POLICY_CHANGE / EVOLUTION_PROPOSAL
- `content: dict`
- `reasoning_trace_id: UUID`  // 关联的推理追溯
- `simulation_trace_id: UUID|null`
- `status: enum`              // DRAFT / APPROVED / EXECUTING / COMPLETED / REJECTED
- `created_at: datetime`
- `approved_by: str`          // Governance / Human / System
- `approval_reason: str|null`

#### Action（动作）
- `action_id: UUID`
- `decision_id: UUID`
- `type: str`                 // TOOL_CALL / API_CALL / PLUGIN_COMMAND
- `parameters: dict`
- `status: enum`              // PENDING / EXECUTING / SUCCESS / FAILED
- `execution_trace_id: UUID`

所有核心对象均以 `frozen dataclass` 形式实现，并附带 `schema_version` 字段。新增字段只允许追加并提供默认值。

---

## 第二部分：事件模型 (Event Schema)

模块间通信的唯一方式是发布/订阅事件。直接函数调用、导入其他模块的行为被禁止（由架构测试强制执行）。

### 2.1 事件总线 (Event Bus)

- 所有 Engine 必须通过 Event Bus 发布事件。
- Engine 只能订阅其声明关注的事件类型。
- Event Bus 负责事件的持久化、顺序保证和重放（基于 Event Store）。

### 2.2 核心事件类型

| 事件名 | 发布者 | 订阅者 | 说明 |
|--------|--------|--------|------|
| `ObservationCreated` | Perception | Runtime, Attention | 新观察进入系统 |
| `AttentionFocus` | Attention | Working Memory, Reasoning | 注意力选择 |
| `ReasoningStarted` | Runtime | Reasoning, Simulation | 推理请求 |
| `ReasoningCompleted` | Reasoning | Decision, Context Mgr | 推理结果 |
| `SimulationCompleted` | Simulation | Decision, World Model | 模拟结果 |
| `DecisionApproved` | Decision | Execution, Governance | 决策批准 |
| `ExecutionCompleted` | Execution | Runtime, Learning | 执行完成 |
| `KnowledgePromoted` | Governance | Cognitive Platform | 知识提升为正式 |
| `KnowledgeDeprecated` | Governance | Cognitive Platform | 知识弃用 |
| `EvolutionProposalSubmitted` | Evolution | Governance | 进化提案 |
| `PolicyUpdated` | Governance | Policy Engine | 策略更新 |
| `SystemAlert` | Any | Runtime, Governance | 系统警报 |

事件结构为不可变 dataclass，包含 `event_id`, `timestamp`, `source_component`, `payload`。所有事件写入 Event Store，支持重放和审计。

---

## 第三部分：接口契约 (ABI)

### 3.1 Engine 接口

所有认知引擎必须实现：

```python
class CognitiveEngine(Protocol):
    engine_id: str
    version: str
    def handle_event(self, event: Event) -> list[Event]: ...
    def get_capabilities(self) -> list[str]: ...
```

引擎不能直接访问 Event Store，只能通过 Event Bus 接收和发送事件。

### 3.2 Plugin 接口

插件接入必须实现：

```python
class Plugin(Protocol):
    plugin_id: str
    def on_register(self, registry: CapabilityRegistry) -> None: ...
    def execute(self, action: Action) -> ActionResult: ...
    def get_manifest(self) -> PluginManifest: ...
```

### 3.3 Capability Registry 接口

```python
class CapabilityRegistry:
    def register_tool(self, tool: ToolSpec) -> None: ...
    def register_plugin(self, plugin: Plugin) -> None: ...
    def register_model(self, model: ModelSpec) -> None: ...
    def find_capability(self, query: CapabilityQuery) -> list[Capability]: ...
```

### 3.4 Runtime 调度接口

Runtime 通过 Scheduler 调用 Engine，不能硬编码 Engine 列表。Scheduler 根据 Context Manager 提供的上下文和 Attention 的聚焦，决定下一步激活哪个 Engine。

---

## 第四部分：通信协议 (Communication Protocol)

- 所有模块间通信必须经过 Event Bus，禁止直接导入其他模块。
- Event Bus 是唯一的生产者/消费者通道。
- 允许的通信模式：Publish/Subscribe、Request/Response（通过关联事件 ID）。
- 架构测试中强制检查 `import` 语句，违反者 CI 直接失败。

---

## 第五部分：治理规则 (Governance Rules)

### 5.1 决策权限

- 只有 Decision 组件可以产生最终决策（Action / PolicyChange）。
- 任何 Engine 不能直接调用 Execution。
- Capability 只能提供候选方案，不能自激活。

### 5.2 变更审批

- 知识库变更（新增、弃用、修改 Knowledge）必须通过 Governance 审批。
- 自我进化提案（EvolutionProposal）必须经过 Governance 审批，且附带回滚计划。
- Governance 可以修改 Policy Engine 中的策略，但本身不能执行任何动作。

### 5.3 安全边界

- Policy Engine 强制执行运行时约束（如夜间禁止危险操作、本地禁止联网）。
- 紧急 Halt：任何模块可发出 `SystemAlert`，Runtime 立即暂停所有执行，并恢复至上一个安全基态。
- Change Budget：Edit Agent 单次修改参数量受限制（默认 max_pipeline_params=3, max_style_profiles=1）。

---

## 第六部分：生命周期 (Lifecycle)

### 6.1 观察到知识的演化

```
Observation → (Attention) → Working Memory
    → (Learning) → Candidate Knowledge
    → (Verification) → Verified Knowledge
    → (Governance) → Active Knowledge
```

### 6.2 目标到动作的闭环

```
Goal → (Reasoning) → Candidate Decisions
    → (Simulation) → Evaluated Decisions
    → (Decision) → Approved Action
    → (Execution) → ActionResult
    → (Perception) → Observation → ...
```

### 6.3 系统自我演化

```
Performance Signal → Evaluation → Evolution Proposal
    → Governance Approval → Capability Update
    → Monitoring → (repeat)
```

---

## 第七部分：可解释性 (Explainability)

任何 Engine 必须自动生成追踪记录（Trace），包括：

- Decision Trace：为什么选择这个动作？备选方案是什么？
- Reasoning Trace：推理步骤、依赖的知识/证据。
- Simulation Trace：模拟的场景、参数、结果。
- Learning Trace：新知识的来源、验证结果、提升过程。

Trace 以结构化事件形式发布到 Event Bus，可被 Explainability Engine 消费生成人类可读报告。

---

## 落地方案与实施步骤

当前 OCOS 已完成 Phase 0-15 的认知骨架，但基础设施层尚未构建。以下分步实施计划，确保从现有状态平滑过渡到 v1.0 平台。

### Phase A: 宪法冻结与基础设施准备 (2 周)

**目标**：将本宪法正式纳入代码库，搭建基础组件。

#### 步骤 A1: 宪法文档与测试框架
- 将本宪法存入 `docs/constitution/`，作为项目最高文档。
- 编写架构测试（ArchUnit 风格），检查以下规则：
  - 所有 dataclass 核心对象符合宪法定义。
  - 禁止跨层 import（如 Reasoning 导入 Decision）。
  - 所有 Engine 通过 Event Bus 通信。
  - 禁止直接写入 Event Store。

#### 步骤 A2: 内核层实现
- 实现 `kernel/` 包：
  - `constitution.py`：硬编码不可变规则（Decision 唯一性等）。
  - `abi.py`：定义所有核心 dataclass、Event 类型枚举。
  - `event_schema.py`：Event 定义与序列化。
  - `time_manager.py`：统一时间源（逻辑时钟 + 物理时钟）。

#### 步骤 A3: Event Bus 原型
- 实现内存版 Event Bus（支持 publish/subscribe）。
- 集成到现有 Event Store，所有历史事件可重放。
- 测试：发布/订阅、顺序保证、重放。

**交付物**：可运行的 Event Bus + 内核模块，架构测试通过。

---

### Phase B: Runtime 层与横切引擎 (3 周)

**目标**：建立调度、上下文、策略、资源管理、注意力机制。

#### 步骤 B1: Context Manager
- 定义 Context 数据结构（当前目标、活跃任务、用户偏好、可用工具列表）。
- 实现 ContextManager：从 Working Memory 和 Goal 组装上下文。
- 测试：上下文创建、更新、销毁。

#### 步骤 B2: Policy Engine
- 实现 Policy Engine，加载默认策略（如安全规则）。
- 提供接口：`evaluate(action) -> bool`。
- Governance 可通过事件更新策略。

#### 步骤 B3: Attention Engine
- 实现简单的注意力模型：基于新颖性、目标相关性、紧急度评分。
- 过滤 Observation 流，输出聚焦后的子集给 Working Memory。
- 测试：多输入下正确过滤。

#### 步骤 B4: Adaptive Control
- 实现动态参数调节：根据系统负载（CPU/内存）和风险等级，调整 Simulation 深度、Learning 权重等。
- 集成 Resource Manager（初期简单版）。

#### 步骤 B5: Resource Manager
- 监控 CPU、内存、GPU（可选）。
- 提供接口：`request_resource(type, amount) -> bool`。
- 在资源不足时通知 Adaptive Control。

#### 步骤 B6: Scheduler
- 实现基于优先级的调度器，通过 Event Bus 触发 Engine 执行。
- 不硬编码 Engine 列表，从 Capability Registry 动态发现。

**交付物**：Runtime 层可运行，调度器能根据上下文和注意力调度 Reasoning/Simulation 等引擎。

---

### Phase C: 解释性与治理增强 (2 周)

#### 步骤 C1: Explainability Trace 引擎
- 定义 Trace 数据结构。
- 修改 Reasoning、Decision、Simulation 组件，在产生结果时发布 Trace 事件。
- 实现 Trace 查询服务。

#### 步骤 C2: Governance 完善
- 实现审批工作流（EvolutionProposal → Review → Approve/Reject）。
- 集成 Policy Engine，审批后可更新策略。

**交付物**：完整的决策追溯链，Governance 可审批进化提案。

---

### Phase D: Capability Registry 与 Plugin 框架 (2 周)

#### 步骤 D1: Capability Registry
- 实现注册中心，支持 Tool、Plugin、Model 注册。
- 提供查询接口（按类型、标签、能力描述）。

#### 步骤 D2: Plugin 加载器
- 实现 Plugin 动态加载（从指定目录加载 Python 包）。
- Plugin 必须实现标准接口。
- 测试：加载 OpenTale Plugin，验证通信。

#### 步骤 D3: OpenTale Plugin 适配
- 将现有的 Writer Adapter 重构为 OpenTale Plugin。
- 通过 Event Bus 接收 Decision 事件，调用 OpenTale Pipeline。

**交付物**：OpenTale 作为第一个 Plugin 成功接入，通过 Event Bus 与 OCOS 交互。

---

### Phase E: 平台集成与全量测试 (2 周)

#### 步骤 E1: 端到端集成测试
- 模拟完整创作流程：文本输入 → 特征提取 → 推理 → 决策 → 执行 (OpenTale) → 反馈。
- 测试多 Plugin 共存、资源争抢。

#### 步骤 E2: 性能与稳定性测试
- 长时间运行（>24小时），检测内存泄漏、事件积压。
- 测试紧急 Halt 和恢复。

#### 步骤 E3: 文档与冻结
- 更新开发者文档。
- 正式冻结 `OCOS Platform v1.0`。

---

## 附录：不可变规则清单

1. 只有 Decision 可以产生最终动作。
2. 任何 Engine 不得直接调用 Execution。
3. 所有模块间通信必须经由 Event Bus。
4. 知识库变更须经 Governance 审批。
5. 核心对象模型不可变（新增字段可追加）。
6. 内核 Constitution 永不可变。
7. 删除 `capability/`、`adaptation/` 目录；合并至 Platform。
8. Plugin 不可直接修改系统状态。
9. Platform 组件超 800 行须按职责拆分。
10. Kernel 永不包含业务逻辑（Memory、Knowledge、Identity、Policy、Decision）。
11. Runtime 永不 import Knowledge/Plugin/Engine。
12. 所有 Information 必须遵循统一生命周期（Acquire → Validate → Retain → Access → Transform → Decay → Archive → Delete）。
13. Information 不拥有自身生命周期控制权。Archive、Delete、Promote、Forget 由 Governance/Lifecycle/Promotion/Forgetting Engine 决定。

---
*本宪法冻结后，OCOS 进入平台实现阶段。所有开发活动以本文档为最高准则。*

---

## 第七部分：边界原则（Boundary Principles）

> 以下 6 条原则源自 Life Model 的本体论定义和 2026-07-23 架构定调会议决议。它们是宪法第一至第六部分的补充，不是替代。

### 7.1 唯一主体原则

整个 OCOS 运行时只有一个 Master Agent（意识）。Engine/Runtime/Worker/Plugin 全部是器官，没有自主目标，没有自己的"想做什么"。

### 7.2 意识 ≠ 身体原则

Master Agent 与 Tool 分离。更换工具不改变身份。失去身体不影响意识。意识是 Master Agent 的属性，不是 Tool 的属性。

### 7.3 记忆 = 人格连续性原则

Memory 不仅是存储，更是"人格连续性"。无记忆则每次启动都是"另一个人"。Identity 是人格的锚点，Memory 是人格的素材。

### 7.4 人类最终负责原则

任何自我演化（Growth）的 Apply 必须经人类审批。不能默认 Yes（auto-accept 是违规）。审批记录永久保存。EvolutionProposal 必须附带 Simulation 结果 + 风险评估 + 回滚计划。

### 7.5 能力 vs 工具分离原则

Capability = 认知功能（Reasoning / Planning / Decision / Learning 等）。Tool = 身体接口（Browser / Filesystem / Robot / Plugin 等）。神经系统（Runtime）与手脚（Tool）本质不同。Capability 不直接操作外部世界，Capability 产 Decision → Tool 执行。

### 7.6 稳态优先原则

Homeostasis（稳态）的优先级高于所有 Goal，但稳态不直接打断用户交互。用户交互时稳态在后台监控，空闲时执行非紧急调节，SLEEP/DREAM 时执行全面维护。紧急告警时（如即将 OOM）获得最高优先级，可以暂停用户交互并告知主人。

---

## State Model 预留

> 本宪法不包含 State Model。State（当前事实）是 Information（历史记录）和 Knowledge（泛化规律）之间缺失的概念层。
> 概念定义见 `docs/STATE_MODEL.md`。State Model 是 v1.0 冻结后的第一个大特性，不在本冻结范围内。
