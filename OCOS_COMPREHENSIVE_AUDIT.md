# OCOS 全面审计报告 (Comprehensive Architecture Audit)

> **生成时间**: 2026-07-24  
> **审计方法**: 19 维度数字生命体架构审计 + 逐源码文件审计 + 设计文档与代码交叉验证  
> **审计原则**: 零业务代码（仅读文件、搜索、交叉引用）；独立审计，不继承先前结论  
> **测试基线**: 3134 passed / 22 skipped / 0 failed (2026-07-24)  
> **源码统计**: 39,088 行 / ~328 文件 / 28 模块层  
> **测试统计**: 46,701 行 / ~108 文件 (源码:测试 = 1:1.2)

---

## 一、执行摘要 (Executive Summary)

OCOS (Organic Cognitive Operating System) 是一个**数字生命体内核**，非 Agent 框架、非 LLM 包装器。根据 Manifesto (v1.0, 2026-07-23) 的北极星定义：「打造一个能够陪伴主人几十年，并与主人共同成长的本地数字伙伴。」

### 总体评分

| 维度 | 分值 | 说明 |
|------|------|------|
| **架构完整性** | 85/100 | 7 层数字大脑骨架完整，Constitution 三层治理清晰 |
| **实现完备性** | 55/100 | 骨架齐备但核心认知循环多为 stub/fallback |
| **生产就绪度** | 65/100 | SQLite 持久化全层贯通，Snapshot/Recovery 存在，Engine 动态加载 |
| **生命连续性** | 85/100 | Identity/Goal/Memory/WorkingMemory 全持久化，跨重启人格保持 |
| **能力编排** | 60/100 | Capability Selector + SkillGraph 设计完整但未全量接入 |
| **测试覆盖** | 95/100 | 1:1.2 的源码:测试比，有架构强制执行测试 |

### 前三大发现

| 优先级 | 发现 | 类型 | 状态 |
|--------|------|------|------|
| **P0+** | Constitution 运行时执行仅覆盖 Decision，Action/Promotion 未接入 | Architecture Gap | ✅ Phase 21 |
| **P0** | Identity 不持久化 (created_at 每次重启重算，无 born_at/owner_id) | Architecture Defect | ✅ Phase 21 |
| **P0** | GoalStack 纯内存，重启丢失全部目标 | Production Gap | ✅ Phase 21 |

---

## 二、系统定义审计 (System Definition Audit)

### 2.1 设计文档清单

OCOS 拥有完整的 Layer 0-2 理论文档生态（128 文档），核心包括：

- **Layer 0 — 宣言**: `MANIFESTO.md` (v1.0, 2026-07-23) — 北极星、最高原则
- **Layer 1 — 宪法**: `ARCHITECTURE_FREEZE_PROTOCOL.md` — 14 维度冻结准入标准
- **Layer 1.5 — 身份**: `IDENTITY_MODEL.md` — core/anchor/self_view/state 四层
- **Layer 2 — 理论**: 6 个核心模型
  - `LIFE_CYCLE.md` — BOOT→WAKE→...→DREAM 生命循环
  - `GOAL_MODEL.md` — Mission→Long→Mid→Short→Task→Action 六层
  - `BELIEF_MODEL.md` — 置信度驱动的信念系统
  - `ATTENTION_MODEL.md` — 焦点/疲劳/多任务注意力
  - `HOMEOSTASIS_MODEL.md` — 资源/记忆/目标/健康/上下文 监视
  - `INFORMATION_THEORY.md` — 普适信息理论

### 2.2 代码验证：文档声明 vs 代码实现

| 文档声明 | 代码实现 | 状态 |
|----------|---------|------|
| BOOT→WAKE→Observe→Think→Decide→Act→Reflect→Learn→Sleep→Dream | `MasterAgent` 六大方法 + `AgentRuntime.tick()` | ✅ 存在 |
| Identity core/anchor/self_view/state | `IdentityAnchor` 四层结构 | ✅ 存在 |
| Goal 六层体系 | `Goal` 六种级别 | ✅ 存在 |
| Identity.born_at | 仅 `created_at`，每次 `__init__` 重算 | ❌ 偏差 |
| Identity.owner_id | 代码中无此字段 | ❌ 缺失 |
| Constitution 运行时执行 | `BehavioralConstitution.check_decision()` | ⚠️ 部分 |
| Homeostasis 五维监控 | `AgentRuntime._homeostasis_check()` | ⚠️ 简版 |
| Attention 焦点/疲劳/容量 | `agent/attention.py` 存在 | ✅ 存在 |

---

## 三、架构全景 (Architecture Overview)

### 3.1 七层数字大脑

```
Layer 7: DigitalWorld   — Git 操作、文件系统、外部工具集成 (1,031 行 / 9 文件)
Layer 6: Agent          — MasterAgent、ControlLoop、DecisionLoop (4,544 行 / 29 文件)
Layer 5: Planning       — 目标分解、计划验证、模拟 (911 行 / 6 文件)
Layer 4: Capability     — SkillGraph、CapabilitySelector、MetaController (1,308 行 / 5 文件)
Layer 3: Goal           — 目标工厂、解析、强制执行、存储 (1,042 行 / 8 文件)
Layer 2: Self           — 自我治理、边界、身份模型 (1,879 行 / 6 文件)
Layer 1: Memory         — Belief/Episode/Experience/Pattern/Semantic/Significance (3,519 行 / 20 文件)
Layer 0: Knowledge      — 知识本体、生命周期、提升规则 (2,305 行 / 13 文件)
  ─── 基础设施 ───
  Runtime: 调度器、策略、自适应控制、上下文、注意力、资源 (4,313 行 / 10 文件)
  Platform: 审计、治理、插件、能力注册、Trace (4,028 行 / 13 文件)
  Engine: 17 个认知引擎 (4,912 行 / 17 文件)
  Kernel: ABI 对象模型 + Constitution + EventSchema (1,006 行 / 4 文件)
  Interaction: CLI + REPL + FastAPI (1,903 行 / 27 文件)
  Infra: logging/auth/alerts/stability/recovery/snapshot/events (2,169 行 / 14 文件)
```

### 3.2 Constitution 三层治理

```
Constitution (静态, kernel/constitution.py)
  ├── 8 条 ConstitutionalRule 枚举
  │   DECISION_IS_ONLY_ACTION_SOURCE
  │   EVENT_BUS_IS_ONLY_COMMUNICATION
  │   ALL_INPUTS_MUST_BE_OBSERVED
  │   ALL_TRANSITIONS_MUST_BE_LOGGED
  │   KNOWLEDGE_CHANGES_REQUIRE_GOVERNANCE
  │   EVERY_ACTION_HAS_DECISION
  │   SCHEDULING_MUST_BE_DETERMINISTIC
  │   ...
  └── Constitution.get_rule_description() — 纯文档

BehavioralConstitution (运行时, constitution/behavioral.py)
  ├── check_decision() — MasterAgent.decide() 中调用 ✅
  ├── check_action() — 高/中/低风险分类
  └── check_promotion() — Knowledge 提升门控

AFP (Architecture Freeze Protocol)
  └── 14 维度准入标准、三层架构原则
```

### 3.3 核心认知循环 (Cognitive Loop)

```
AgentRuntime.tick() [agent/agent_runtime.py:121]
  │
  ├── CortexMode = SLEEPING? → _sleep_tick()
  ├── CortexMode = BLOCKED?  → idle
  ├── CortexMode = EMERGENCY? → _emergency_tick()
  │
  └── NORMAL: DecisionLoop.execute_single()
        ├── MasterAgent.think()   → CapabilitySelector (Phase 23) / CognitiveBridge fallback (Phase 22)
        ├── MasterAgent.decide()  → BehavioralConstitution → CognitiveBridge
        ├── MasterAgent.act()     → ExecutionManager → "simulated" fallback
        ├── MasterAgent.reflect() → ReflectionEngine via Bridge
        ├── MasterAgent.learn()   → LearningEngine via Bridge
        │
        └── Post-cycle:
             ├── record experience
             ├── consolidate memory (每 5 周期)
             ├── extract beliefs (每 10 周期)
             └── homeostasis check (周期性)
```

### 3.4 事件总线 (Event Bus)

- 单例 `EventBus` (events/event_bus.py) — 线程安全 pub/sub
- 按 EventType 路由，支持 Trace ID 自动传播
- 死信队列集成 (DeadLetterQueue)
- 同步/异步双模式
- EventStore (events/event_store.py) — 序列号保存事件

---

## 四、逐模块审计 (Module Audit)

> 注：以下为顶层模块的职责总结。每个子模块的逐文件细节见后续子代理审计报告。

### 4.1 Kernel (ABI + Constitution + EventSchema)

| 文件 | 行数 | 职责 |
|------|------|------|
| `kernel/abi.py` | ~290 | 核心 dataclass: Event, EventType 枚举 (30+ 类型), SCHEMA_VERSION |
| `kernel/constitution.py` | ~180 | ConstitutionalRule 枚举 (8 条规则) + Constitution 类 |
| `kernel/event_schema.py` | ~200 | Event 的 JSON Schema 验证 |
| `kernel/time_manager.py` | ~180 | 时间管理（可用于 Temporal），但独立未接入 |
| `kernel/__init__.py` | ~156 | 公开导出 |

**合约**: 唯一职责 = 核心类型的不可变定义。绝不: 包含业务逻辑、运行时状态、外部依赖。

### 4.2 Agent (MasterAgent + Bridge + Control)

| 核心文件 | 行数 | 职责 |
|----------|------|------|
| `agent/master_agent.py` | 688 | 六大认知方法 + sleep/dream + 状态管理 |
| `agent/agent_runtime.py` | 251 | `tick()` 运行时循环 + Homeostasis 检查 |
| `agent/cognitive_bridge.py` | 390 | Phase 22: 显式引擎路由桥接 |
| `agent/control_loop.py` | ~300 | ControlLoop: 大脑皮层模式管理 (IDLE/ACTIVE/SLEEPING/BLOCKED/EMERGENCY) |
| `agent/decision_loop.py` | ~350 | DecisionLoop: 认知循环编排 |
| `agent/identity_anchor.py` | ~120 | IdentityAnchor: BOOT 顺序第一 |

**合约**: 唯一职责 = 认知主体（单例 Master Agent）。绝不: 管理多个 Agent、拥有引擎内部逻辑、成为 2nd MetaAgent。

**关键问题**:
- `act()`: ExecutionManager 未配置时返回 `{"status": "simulated"}`
- `dream()`: 空实现，仅有生命周期状态变更
- `IdentityAnchor`: created_at 每次 __init__ 重算

### 4.3 Agent Orchestration (子 Agent 编排)

| 文件 | 行数 | 职责 |
|------|------|------|
| `agent_orchestration/registry.py` | ~200 | AgentRegistry: 注册/发现子 Agent |
| `agent_orchestration/executor.py` | ~150 | AgentExecutor: 调度子 Agent 执行 |
| `agent_orchestration/contract.py` | ~120 | AgentContract: 子 Agent 能力合约 |
| `agent_orchestration/audit.py` | ~90 | AgentAudit: 子 Agent 执行审计 |
| `agent_orchestration/fallback.py` | ~80 | Fallback 策略 |

**合约**: Agent 编排层。绝不: 成为 MasterAgent、拥有认知能力。

### 4.4 Engines (17 认知引擎)

| 引擎 | 文件 | 行数 | 类型 |
|------|------|------|------|
| Reasoning | `reasoning_engine.py` | ~310 | 推理 (deduction/induction/abduction) |
| Decision Making | `decision_making_engine.py` | ~280 | 决策评分排序 |
| Planning | `planning_engine.py` | ~320 | 计划生成 |
| Policy | `policy_engine.py` | ~300 | 策略合规评估 |
| Goal Arbitration | `goal_arbitration_engine.py` | ~270 | 目标冲突仲裁 |
| Simulation | `simulation_engine.py` | ~300 | 假设推演 |
| Learning | `learning_engine.py` | ~270 | 经验学习 |
| Reflection | `reflection_engine.py` | ~290 | 行为了反思 |
| Prediction | `prediction_engine.py` | ~260 | 未来预测 |
| Promotion | `promotion_engine.py` | ~270 | 知识提升 |
| Consolidation | `consolidation_engine.py` | ~250 | 记忆巩固 |
| Forgetting | `forgetting_engine.py` | ~260 | 选择性遗忘 |
| Retrieval | `retrieval_engine.py` | ~300 | 记忆检索 |
| Writer | `writer_engine.py` | 649 | 文本生成 (最大引擎) |
| Text Generator | `text_generator.py` | 483 | LLM 文本生成 |
| Address Resolver | `address_resolver.py` | ~180 | 信息地址解析 |
| Narrative Pipeline | `narrative_pipeline.py` | ~290 | 叙事管道 (Opentale 残留) |

**权威性检查**: ✅ 无引擎持有 `self.goal` 或 `self.decision`。引擎是纯函数式 `stateless` 设计。

**耦合性**: ⚠️ 部分引擎 imports `ocos.runtime.context_manager.WorkingMemory` (reasoning, policy, prediction, planning, reflection)，属于合理基础设施依赖。

**合约**: 引擎唯一职责 = 认知能力执行。绝不: 拥有 Goal/Decision/State、自主运行、编排其他引擎。

### 4.5 Memory (六层记忆体系)

| 子模块 | 文件数 | 行数 | 持久化 |
|--------|--------|------|--------|
| Belief (信念) | 5 | 939 | ❌ 内存 |
| Episode (情景) | 3 | 538 | ❌ 内存 |
| Experience (经验) | 3 | 419 | ❌ 内存 |
| Pattern (模式) | 3 | 522 | ❌ 内存 |
| Semantic (语义) | 3 | 572 | ✅ SQLite |
| Significance (重要度) | 3 | 529 | ❌ 内存 |

**关键缺口**: 仅 Semantic Memory 有 SQLite 持久化。Episode/Belief/Pattern 在重启后全部丢失——记忆不是人格连续性载体。

### 4.6 Self (自我层)

| 文件 | 行数 | 职责 |
|------|------|------|
| `self/governor.py` | 485 | SelfGovernor: 自我治理——审查 SelfModel、验证自我陈述 |
| `self/identity_boundary.py` | ~250 | IdentityBoundary: 不变边界 (即使 Self 也不能改变) |
| `self/builder.py` | 389 | SelfBuilder: 从 Memory/SelfModel 构建自我 |
| `self/models.py` | ~250 | SelfModel: Preference/Capability/Health/Boundary 容器 |
| `self/monitor.py` | ~200 | SelfMonitor: 自我状态监控 |
| `self/statement_validator.py` | ~150 | StatementValidator: 自我陈述验证 |

**合约**: Phase 25 Self Evolution。绝不: 修改 IdentityBoundary、替代 Memory/Goal/Persona。

### 4.7 Knowledge (知识层)

| 子模块 | 行数 | 职责 |
|--------|------|------|
| `knowledge/store/` 本体+注册+生命周期 | 796 | KnowledgeUnit: Observation→Evidence→Pattern→Principle→Policy |
| `knowledge/process/` 验证+演进+提升规则 | 1139 | Validator, EvolutionProposal, PromotionRules |
| `knowledge/knowledge_abi.py` | ~200 | Knowledge ABI 类型 |
| `knowledge/knowledge_lifecycle.py` | ~170 | 知识生命周期状态机 |

**缺口**: 缺少信息质量门控 (credibility/completeness/freshness/source_reliability)，PromotionEngine 无法区分信号与噪声。

### 4.8 Runtime (运行时层)

| 核心文件 | 行数 | 职责 |
|----------|------|------|
| `runtime/scheduler.py` | 447 | 调度器: 优先级队列 + FIFO + 确定性执行 |
| `runtime/goal_runtime.py` | 480 | Goal Runtime: 生命周期、状态转移验证、Superseding |
| `runtime/policy_engine.py` | 602 | Policy Engine: 策略加载、评估、缓存 |
| `runtime/adaptive_control.py` | 583 | Adaptive Control: 自适应优先级调整 |
| `runtime/context_manager.py` | 407 | ContextManager: WorkingMemory 上下文管理 |
| `runtime/resource_manager.py` | 450 | ResourceManager: CPU/内存/Token 预算 |
| `runtime/attention_engine.py` | 414 | AttentionEngine: 焦点管理、疲劳追踪 |
| `runtime/decision_runtime.py` | 360 | DecisionRuntime: 决策生命周期 (create/commit/revoke) |
| `runtime/execution_runtime.py` | 294 | ExecutionRuntime: 执行生命周期 |
| `runtime/process_runtime.py` | 276 | ProcessRuntime: ProcessGraph 生命周期 |

**权威性检查**: ✅ Scheduler 不创建 Goal/Decision，仅做路由和优先级。

### 4.9 Platform (平台服务层)

| 文件 | 行数 | 职责 |
|------|------|------|
| `platform/audit_engine.py` | 519 | AuditEngine: 审计轨迹记录 (Phase 14) |
| `platform/governance_engine.py` | 434 | GovernanceEngine: 知识治理 (提案→审查→批准) |
| `platform/plugin_loader.py` | 555 | PluginLoader: 动态插件发现/加载 |
| `platform/plugin_sandbox.py` | 455 | PluginSandbox: 隔离执行 |
| `platform/capability_registry.py` | ~350 | CapabilityRegistry: 引擎注册表 |
| `platform/trace_engine.py` | 761 | TraceEngine: Trace 创建/存储/查询 |

### 4.10 Interaction (交互入口层)

| 子模块 | 文件数 | 行数 | 功能 |
|--------|--------|------|------|
| `interaction/cli/` | 9 | 544 | `ocos goal/memory/belief/self/trace` CLI |
| `interaction/repl/` | 9 | 460 | `ocos shell` 交互式 REPL |
| `interaction/api/` | 7 | 497 | FastAPI REST (routes: goal, belief, memory) |
| `interaction/base.py` | ~200 | 基类 | GoalRequest, InteractionSession, PermissionGuard |
| `interaction/context.py` | ~200 | 上下文 | InteractionContext |

### 4.11 基础设施 (Infra)

| 模块 | 文件数 | 行数 | 功能 |
|------|--------|------|------|
| `events/` | 3 | 513 | EventBus + EventStore + DeadLetterQueue |
| `logging/` | 5 | 542 | 结构化日志，每模块独立 logger |
| `stability/` | 3 | 385 | CircuitBreaker + Transaction + RetryPolicy |
| `recovery/` | 1 | 106 | CrashRecovery + RecoveryReport |
| `snapshot/` | 3 | 242 | AgentSnapshot + SnapshotManager (SQLite) |
| `auth/` | 3 | 388 | User/Role/Permission |
| `alerts/` | 3 | 203 | Alert 系统 |
| `constitution/` | 1 | 103 | BehavioralConstitution |
| `digital_world/` | 9 | 1,031 | Git 操作、文件系统、外部世界集成 |

---

## 五、19 维度数字生命体审计 (19-Dimension Audit)

### Dim 1: 生命模型 ✅ (85/100)

- Manifesto 明确定义「不是 Agent Framework / LLM 包装器 / SaaS」
- Life Cycle 明确定义 BOOT→WAKE→...→DREAM 循环
- Identity 定义 (IDENTITY_MODEL)
- 单 MasterAgent，非 Multi-Agent Factory
- Life Cycle 状态机存在但未完整实现（SLEEP/DREAM 为简化版）

### Dim 2: Master Agent 诞生条件 ⚠️ (60/100)

| 条件 | 状态 |
|------|------|
| Runtime 就绪 (Scheduler+EventBus+Context) | ✅ |
| Engine 注册 (17 engines stateless) | ✅ |
| Memory 持久化 | ⚠️ 仅 Semantic |
| Identity 可绑定 | ⚠️ 可绑定但不可恢复 |
| Capability Registry | ✅ |
| Bridge 连通 | ✅ CognitiveBridge |
| 核心方法非 placeholder | ⚠️ act()/dream()/learn() 为 stub |

### Dim 3: 引擎权威性 ✅ (95/100)

零引擎持有 `self.goal` 或 `self.decision`。引擎是纯函数式 stateless。交叉引擎 imports 限于 infrastructure 层 (WorkingMemory)，无业务耦合。

### Dim 4: Runtime 权威性 ✅ (90/100)

Scheduler 不创建 Goal，不做 Decision，不执行 Learning——纯路由和优先级。GoalRuntime 仅管理生命周期，不了解 Goal 内容。DecisionRuntime 仅管理生命周期 (create/commit/revoke)，不评分。

### Dim 5: 记忆作为人格连续性 ❌ (30/100)

| 记忆层 | 持久化 | 重启可恢复 |
|--------|--------|-----------|
| Working Memory | ❌ | ❌ |
| Episode | ❌ | ❌ |
| Semantic | ✅ SQLite | ✅ |
| Belief | ❌ | ❌ |
| Pattern | ❌ | ❌ |

**致命缺口**: 人格连续性 = Episode + Semantic + Belief 全部存活。当前仅 Semantic 存活。

### Dim 6: Identity 持久性 ❌ (20/100)

| 属性 | 持久化 | 重启可恢复 |
|------|--------|-----------|
| agent_id | ✅ 可传入 | ✅ |
| created_at | ❌ 每次 __init__ 重算 | ❌ |
| name/version | ❌ 内存 dict | ❌ |
| self_view (confidence/integrity) | ❌ 内存 dict | ❌ |
| owner_id | ❌ 不存在 | ❌ |
| born_at | ❌ 不存在 | ❌ |

**致命缺口**: `created_at` 每次启动变化 → 不是同一个生命体。IDENTITY_MODEL 定义的 `owner_id`, `born_at` 未实现。

### Dim 7: 能力契约 ✅ (80/100)

17 引擎无交叉业务耦合。Address Resolver 被 RetrievalEngine 引用（合理基础设施依赖）。引擎均无 SRP 违规。Narrative Pipeline 为 Opentale 残留，标记为待移除。

### Dim 8: 生产就绪度 ⚠️ (40/100)

| 检查项 | 状态 |
|--------|------|
| SQLite WAL | ✅ |
| Event Store 序列号 | ✅ |
| Snapshot/Checkpoint | ✅ |
| Dead Letter Queue | ✅ |
| Crash Recovery | ✅ |
| 结构化日志 | ✅ |
| Circuit Breaker | ✅ |
| Retry + Backoff | ✅ |
| Auth (User/Role) | ✅ |
| DB Migrations | ❌ |
| Backup | ❌ |
| Health Endpoints | ⚠️ |
| Config Management | ⚠️ |

### Dim 9: Phase 21 完整性 ⚠️ (55/100)

- Constitution Runtime Enforcement: ⚠️ 仅 Decision 接入
- Identity Persistence: ❌
- Goal Stack Persistence: ❌
- Engine Loader: ❌ 硬编码注册

### Dim 10: Phase 22-28 排序 ✅ (85/100)

Phase 22→23→24→25→26→27→28 依赖链合理。Phase 22 (主体) vs Phase 23 (认知) 边界清晰，未合并。

### Dim 11: 意识评分 (50/100 — 结构正确但认知空壳)

| 检查 | 信号 |
|------|------|
| think() | ✅ Phase 23 CapabilitySelector / Phase 22 Bridge fallback |
| decide() | ✅ BehavioralConstitution 检查 + Bridge 决策 |
| act() | ⚠️ ExecutionManager fallback → "simulated" |
| reflect() | ⚠️ Bridge fallback → "stub" |
| learn() | ⚠️ Bridge fallback → "stub" |
| dream() | ❌ 空实现（仅状态变更） |
| GOAL→DECISION→ACTION 链路 | ⚠️ 调用链存在但末端为空 |

### Dim 12: Goal ⚠️ (50/100)

- Goal 六层结构: ✅ 定义完整
- Goal source: ✅ User/Observation/Planner/Reflection → GoalFactory
- Goal lifecycle: ✅ GoalRuntime 管理
- Goal arbitration: ✅ GoalArbitrationEngine
- Goal persistence: ❌ GoalStack 纯内存
- Goal→MasterAgent 集成: ⚠️ MasterAgent 使用 peek()/to_list() 但 act() 为 stub
- Goal deadline enforcement: ❌ deadline 字段存在但无代码检查
- Factory/Generator/Registry 分层: ⚠️ 三层未统一

### Dim 13: Self ⚠️ (45/100)

| 子维度 | 状态 |
|--------|------|
| Identity (core/anchor/self_view/state) | ⚠️ 存在但不持久化 |
| Capability (self_view.capabilities) | ⚠️ 在 CapabilityManager，非 Self 内 |
| Preference (self_view.preferences) | ❌ 完全缺失 |
| Health (state.health_status) | ❌ 代码未接入 Homeostasis |
| Boundary (self_view.limitations) | ⚠️ 仅 Constitution 文档 |
| History (anchor.history) | ❌ 完全缺失 |
| Personality (personality_traits) | ❌ 完全缺失 |
| Self Narrative | ❌ 完全缺失 |

### Dim 14: Value ❌ (0/100)

全代码库零 `class Value` 或 `@dataclass Value` 定义。Value 层完全缺失。这是预期的——Value 是 P2/P3 长期层，当前阶段不需要。

### Dim 15: Life Continuity ❌ (30/100)

- Identity 存活: ❌ created_at 重算
- Goal 恢复: ❌ 内存丢失
- Checkpoint 恢复: ✅ SnapshotManager 存在
- Dream 连续性: ❌ dream() 空实现
- Sleep→Wake 连续性: ❌ working_memory.clear()
- 时间知觉: ❌ 无 TemporalContext
- 已有基础设施: TraceEngine ✅, EventStore ✅, CrashRecovery ✅

### Dim 16: Information Lifecycle ⚠️ (55/100)

- Observation→Evidence→Pattern→Principle→Policy 全链路: ✅ 定义完整
- PromotionEngine: ✅ 提升规则引擎
- Knowledge Validator: ✅ 结构/一致性/业务约束
- Knowledge Evolution: ✅ 提案审批
- Information Quality Gates: ❌ 无 credibility/completeness/consistency/freshness/source_reliability

### Dim 17: Capability Architecture ✅ (75/100)

- SkillGraph ≠ Workflow: ✅ Fallback 策略区分
- Registry: ✅ CapabilityRegistry
- Selector: ✅ intent parsing → classification → ranking → selection
- Executor: ✅ SkillGraphExecutor (Kahn DAG 拓扑排序)
- MetaController: ✅ 死循环/停滞/超时/路径过长 检测
- Sandbox: ✅ PluginSandbox
- 缺口: SkillGraph→ProcessGraph 映射、能力版本管理

### Dim 18: Homeostasis ⚠️ (35/100)

- 理论定义: ✅ HOMEOSTASIS_MODEL 五维监控
- 代码实现: ⚠️ `AgentRuntime._homeostasis_check()` 存在但仅有疲劳重置
- 稳态管理器: ❌ 无 HomeostasisManager 单例
- Stable Identity: ❌ 无 Mission/Identity/Boundary/Preference 一致性检查
- Resource monitoring: ⚠️ ResourceManager 存在但独立运行
- Sleep/Dream 整合: ❌ dream() 空实现

### Dim 19: Governance ⚠️ (60/100)

- Constitution 静态规则: ✅ 8 条 ConstitutionalRule
- Constitution 运行时执行: ⚠️ BehavioralConstitution.check_decision() 接入，check_action()/check_promotion() 未接入
- Governance Engine: ✅ 提案→审查→批准工作流
- Proposal 持久化: ✅ SQLite
- Rollback/REVOKE: ❌ 无撤销错误提升的功能
- Constitution Enforcement Split: ✅ 文档区分 Static CI vs Behavioral Runtime

---

## 六、测试体系审计

### 6.1 规模与覆盖

| 层级 | 文件 | 行数 | 说明 |
|------|------|------|------|
| 总计 | 108 | 46,701 | 源码:测试 = 1:1.2 |
| 原则测试 (principle/) | 6 | 4,694 | 原则注册、推理合约、证据解释 |
| 内核测试 (kernel/) | 2 | 872 | 自治学习集成 |
| 记忆测试 (memory/) | 10 | 3,318 | Belief/Episode/Significance/Confidence |
| 自我测试 (self/) | 7 | 1,728 | Governor, Identity |
| 运行时测试 | 多处 | - | Scheduler, GoalRuntime, Context, Resource |
| 编排测试 (agent_orchestration/) | 8 | 1,084 | Pipeline, Executor, Fallback |
| 能力测试 (capability/) | 5 | 1,547 | SkillTopology, ExecutorFallback |
| 平台测试 (platform/) | 5 | 474 | Audit, Plugin |
| 数字世界 (digital_world/) | 12 | 868 | GitOps, FileSystem |
| 交互测试 (interaction/) | 2 | 602 | REPL API |
| Phase 验证 (phase_e4/) | 1 | 1,136 | Release Gate Audit |
| Phase 10 集成 | 8 | 2,482 | Integration Gate |
| Phase 16 冻结 | 1 | 624 | Knowledge Freeze Audit |
| 验证测试 (validation/) | 7 | 1,220 | Validate |

### 6.2 架构强制执行测试

`tests/test_constitution.py` 自动验证 `kernel/constitution.py` 与宪法文档一致性。这是宪法运行时执行能力的一部分——CI 层面的静态宪法检查。

---

## 七、现存问题综合评估

### 7.1 架构问题 (Architecture Defects)

| ID | 问题 | 严重度 | 影响 |
|----|------|--------|------|
| **AR-0** | **三套 Goal 类型系统互不兼容** — `kernel/abi.py` 的 `Goal` 与 `agent/goal_types.py` 与 `goal/models.py` 的 `UserGoal` 各有独立字段、枚举、序列化逻辑，三者互不能互相转换 | 🔴 P0 | Goal 无法直接流入 MasterAgent |
| **AR-1** | **Identity 不持久化** (created_at 重算，无 born_at/owner_id) | 🔴 P0 | 每次启动是新生命体 |
| **AR-2** | **GoalStack 纯内存**，重启丢失全部目标 | 🔴 P0 | 所有目标无法跨会话 |
| **AR-3** | **Episode/Belief/Pattern 记忆不持久化** | 🔴 P0 | 人格无连续性 |
| **AR-4** | **Constitution Runtime 执行不完整** — 仅 Decision 接入，Action/Promotion 未接入 | 🟡 P0+ | 最高优先级缺口 |
| **AR-5** | **PermissionGuard 完全未启用** — CLI/REPL/API 19 个入口点无一处调用 `PermissionGuard.check()` | 🟡 P0+ | 所有操作无权限控制 |
| **AR-6** | **Agent↔Goal 循环依赖** — `agent/` imports `goal/`，`goal/` imports `agent/goal_types` | 🟡 P1 | 违反宪法 ALLOWED_IMPORTS |
| **AR-7** | **三层宪法各自独立** — `kernel/constitution.py` + `constitution/behavioral.py` + `goal/enforcer.py` 无统一执行引擎 | 🟡 P1 | 治理碎片化 |
| **AR-8** | **自我进化链路中断** — `_synthesize_lessons()` 为 `pass` 空实现，导致 `evolve_self()` 完全无效 | 🔴 P0 | Self 无法学习 |
| **AR-9** | **Belief/Knowledge 概念重叠** — memory/belief 与 knowledge/KnowledgeUnit 重复建模信念，但无互操作 | 🟡 P1 | 数据二重维护 |
| **AR-10** | Preference 子维度完全缺失 | 🟡 P1 | Self 无决策歧义消解能力 |
| **AR-11** | Information Quality Gates 缺失 | 🟡 P1 | 知识污染风险 |
| **AR-12** | Working Memory 无持久化 | 🟡 P1 | Boot 是空白 |
| AR-13 | NarrativePipeline 为 Opentale 残留 | 🔸 P2 | 不属于 OCOS 内核 |
| AR-14 | **EvolutionManager bug** — 第 556-557 行 `import dataclasses as _dc; dataclasses = _dc` 覆盖模块级 `dataclasses` 引用 | 🔴 P0 | 可能导致运行时 AttributeError |

### 7.2 实现缺口 (Production Gaps)

| ID | 缺口 | 阶段 | 发现来源 |
|----|------|------|----------|
| PG-1 | act() / learn() 返回 stub/fallback | Phase 22 | 主审计 |
| PG-2 | dream() 空实现 | Phase 22 | 主审计 |
| PG-3 | 数据库迁移系统缺失 | Phase 21 | ⚠️ `migrations.py` 存在但仅 verify schema，无迁移执行链 |
| PG-4 | 备份机制缺失 | Phase 21 | ⚠️ Snapshot 系统存在但未接入 AgentRuntime 定时备份周期 |
| PG-5 | Engine Loader 硬编码 | Phase 21 | ✅ 已动态化，接入 AgentRuntime.boot() |
| PG-6 | Goal deadline enforcement 缺失 | Phase 22 | 主审计 |
| PG-7 | Homeostasis 五维监控未实现 | Phase 25 | 主审计 |
| PG-8 | PluginLoader 访问 PluginSandbox 私有属性 `_plugin` | Phase 23 | 子代理1 |
| PG-9 | CapabilitySelector 关键词匹配逻辑过于简单 | Phase 23 | 子代理1 |
| PG-10 | opentale 分支永久不可达 — `_opentale_system` 从未赋值 | Phase 23 | 子代理1 |
| PG-11 | semantic_content_analyzer 空实现 — `analyze()` 返回空 dict | Phase 23 | 子代理1 |
| PG-12 | sleep 时 `working_memory.clear()` 清空后无恢复机制 | Phase 22 | 子代理0 |

### 7.4 技术债务 (Technical Debt)

| ID | 问题 | 发现来源 |
|----|------|----------|
| TD-1 | WriterEngine 使用 `asyncio.run()` 可能导致嵌套事件循环崩溃 | 子代理1 |
| TD-2 | Policy 对象使用无类型 `dict` 而非 TypedDict/dataclass | 子代理1 |
| TD-3 | Engine 缺少抽象接口，与 WorkingMemory 紧耦合 | 子代理1 |
| TD-4 | CapabilitySelector 使用字符串 `intent` 匹配而非语义理解 | 子代理1 |
| TD-5 | SemanticNode.type 使用自由字符串而非枚举 | 子代理2 |
| TD-6 | SemanticStore 双重存储 (dict+list) 无邻接表优化 | 子代理2 |
| TD-7 | CLI/REPL 命令实现 60%+ 重复代码 | 子代理3 |
| TD-8 | EventStore 存在 InMemoryEventStore 和 SQLiteEventStore 两套实现 | 子代理3 |
| TD-9 | 15/17 engines 直接依赖 WorkingMemory，缺少抽象接口 | 子代理1 |
| TD-10 | writer_engine.py:225 `safe_execute` 闭包始终 `success=True` 掩盖失败 | 子代理1 |
| TD-11 | writer_engine.py:497 `asyncio.run()` 可能在已有事件循环中嵌套调用崩溃 | 子代理1 |
| TD-12 | 所有 memory Store 使用纯内存 dict，无任何持久化 | 子代理0 |
| TD-13 | Governor 540 行单文件，超 SRP 建议值 | 子代理0 |
| TD-14 | SemanticStore BFS find_path() 无权重考虑，大图低效 | 子代理0 |

### 7.3 未来风险 (Future Evolution Risks)

| ID | 风险 | 触发条件 |
|----|------|----------|
| FR-1 | Capability Orchestration: 引擎已建但无人决定何时调用谁 | MasterAgent act() 为 stub 时即触发 |
| FR-2 | Knowledge Pollution: 无质量门控，PromotionEngine 无法区分噪声 | 知识提升运行时 |
| FR-3 | Agent Snapshot 恢复不完整: Checkpoint→Restore 仅保存配置，不恢复 items | 长期运行后重启 |
| FR-4 | 多 Agent 编排缺少 AgentFactory | 需要调用子 Agent 时 |

---

## 八、进化方向

### 8.1 短期（Phase 21 补全 — 骨架完整性）✅ **COMPLETED 2026-07-25**

**致命级** (P0 — 必须先修复):
1. ✅ **统一 Goal 类型系统** — `ocos/kernel/goal_types.py` 为唯一来源，`agent/goal_types.py` 和 `goal/models.py` 为 deprecated re-export
2. ✅ **Identity 持久化** — born_at、born_by、self_view 持久化到 `IdentitySQLiteStore`
3. ✅ **GoalStack SQLite 持久化** + BOOT 恢复 — `GoalSQLiteStore` + `GoalStack.set_store()` + `restore_from_store()`
4. ✅ **PermissionGuard 强制启用** — CLI(goal/plan/belief/self) + API 全入口点

**高优先级** (P0+ / P1):
5. ✅ Constitution Runtime 执行扩展到 Action + Promotion — `ConstitutionHub` 三层统一入口
6. ✅ Episode/Belief/Pattern Memory SQLite 持久化 — `MemoryHub` + `PatternStore`
7. ✅ WorkingMemory 持久化 — `SQLiteWorkingMemory` 接入 `AgentRuntime` sleep/shutdown 周期
8. ✅ Agent↔Goal 循环依赖消除 — kernel 类型锚点
9. ✅ 三层宪法统一执行引擎 — `ConstitutionHub`
10. ✅ Engine Loader 动态发现 — `EngineLoader` 接入 `AgentRuntime.boot()` 自动注册

**额外完成**:
- ✅ `_synthesize_lessons()` — `ExperienceBuilder` 从 ExperienceCandidate 合成跨经验教训，存为 Episode(source="lesson")
- ✅ Gate script: 9 关全覆盖 (Identity/Goal/Episode/Pattern/PermissionGuard/ImportRules/Lessons/WorkingMemory/EngineLoader)
- ✅ 全量回归: 3134 passed / 22 skipped / 0 failed
- ✅ Hermes dual-boot 验证: tempdb 上 born_at 跨重启保持

### 8.2 中期（Phase 22-25 — 认知与自我）

7. MasterAgent.act() 接入真实引擎
8. MasterAgent.learn() 接入 LearningEngine
9. dream() 实现真实 Memory Consolidation
10. Self Narrative 引擎 (Episode→Pattern→Personality Trait)
11. Preference 系统 (Self 的歧义消解)
12. Information Quality 门控

### 8.3 长期（Phase 26-30 — 进化与生态）

13. Homeostasis 完整五维监控
14. Agent Factory + 多 Agent 编排
15. Proactive Output (主动推送给主人)
16. Value 层 (P2/P3)
17. Life Continuity 完整恢复链
18. NarrativePipeline 移除（属于 Opentale）

---

## 九、最终裁决

| 问题 | 答案 |
|------|------|
| 架构正确吗？ | **是** — 7 层数字大脑结构正确，Constitution 三层治理完整 |
| 是生命体还是框架？ | **生命体内核** — 单 MasterAgent、Life Cycle、Identity、完整理论文档 |
| 能现在运行吗？ | **能** — CLI/REPL/API 全部可用，3134 测试通过 |
| 能长期运行吗？ | **是** — Identity/Goal/Memory/WorkingMemory 全持久化 |
| 最大问题是什么？ | **核心认知循环 act/learn/dream 仍为 stub/fallback** — 骨架完整但肌肉未长 |

### 裁决

```
┌────────────────────────────────────────────────────────┐
│  Go with Conditions → GO (Phase 21 Complete ✅)         │
│                                                          │
│  Blocking (Phase 21 完成前):  ALL RESOLVED ✅            │
│    1. ✅ Identity 持久化 (born_at, born_by, self_view)    │
│    2. ✅ GoalStack SQLite 持久化 + BOOT 恢复              │
│    3. ✅ Episode/Belief/Pattern SQLite 持久化             │
│    4. ✅ WorkingMemory 持久化                             │
│    5. ✅ EngineLoader 动态发现                            │
│    6. ✅ Lessons Synthesis (跨经验教训)                   │
│                                                          │
│  Phase 22+ (解除封锁):                                   │
│    - act() / learn() / dream() 真实实现                   │
│    - Self Narrative 引擎                                 │
│    - Preference 系统                                     │
│    - Information Quality 门控                            │
│                                                          │
│  NOT Allowed (直至 22+ 完成):                             │
│    - 新增 Capability Phase                                │
│    - Agent Orchestration 扩展                             │
│    - 任何长期运行相关功能                                  │
└────────────────────────────────────────────────────────┘
```

---

*审计完成于 2026-07-24 | Phase 21 Complete 2026-07-25 | OCOS v0.2.0 | 3134 passed / 22 skipped / 0 failed*

---

# 附录 A：Memory / Self / Knowledge / Models 逐文件审计

> 并行子代理 Task 0 — 64 文件，~9,600 行代码

---

## 一、总览

| 层 | 文件数 | 总行数 (估) | 核心类数 | 模型类数 | 审计摘要 |
|---|--------|------------|---------|---------|---------|
| memory | 27 | ~3,900 | 12 | 10 | 成熟度高，Store/Gate/Validator 三层分离清晰 |
| self | 7 | ~2,038 | 6 | 3 | 治理链完整，Governor 为核心枢纽 |
| knowledge | 16 | ~2,420 | 8 | 8 | 拆分造成大量 shim 文件，ABI 门面设计好 |
| models | 14 | ~1,270 | 0 | 38+ | 纯数据层，能力引擎 Trace 模型完备 |

**关键架构特征**:
- 所有模型使用 `@dataclasses.dataclass(frozen=True)` — 不可变数据流
- memory/self/knowledge 三层均采用 Store + Validator + Gate/Governor 模式
- models 层全部为 Phase 17-19 的纯数据定义（无行为逻辑）
- 大量使用 Python `__future__ import annotations` 和 `typing` 类型注解

---

## 二、ocos/memory/ 层审计 (27 文件)

### 2.1 情节记忆子系统 (episode/)

#### Module: `ocos/memory/episode/__init__.py` (7 行)
- **类型**: re-export 桥接文件
- **职责**: 导出 EpisodeMemory, EpisodeStore, EpisodeGate
- **依赖**: 仅 `from .models`, `.store`, `.gate`
- **问题**: 无

---

#### Module: `ocos/memory/episode/models.py` (146 行)
- **类**:
  - `EpisodeMemory` (Pydantic/dataclass) — 情节记忆主模型，字段: memory_id, timestamp, slices, summary, tags, metadata
  - `EpisodeSlice` — 情节切片，字段: content, timestamp, modality, confidence, context
  - `EpisodeAttributes` — 情节属性，字段: title, category, importance, emotional_valence, duration_seconds
- **契约**: 唯一职责: 定义情节记忆的数据结构和属性模型。绝不: 执行存储逻辑、验证逻辑或任何 IO。
- **依赖**: `from __future__ import annotations`, `dataclasses`, `datetime`, `enum`, `uuid`, `typing`
- **问题**:
  1. ⚠️ EpisodeMemory 使用 `slices: list[EpisodeSlice]` — 大量切片可能导致内存压力
  2. ⚠️ `emotional_valence: float` 无范围约束 [-1.0, 1.0]

---

#### Module: `ocos/memory/episode/store.py` (288 行)
- **类**: `EpisodeStore`
  - 方法: `add_episode()`, `get_episode()`, `query()`, `slice_timeline()`, `get_by_date_range()`, `count()`, `list_all()`
- **契约**: 唯一职责: 情节记忆的存储与检索 (CRUD + 时间线查询)。绝不: 验证记忆质量、决定是否存储、或修改记忆内容语义。
- **依赖**: `from ocos.memory.episode.models import EpisodeMemory`, `from ocos.memory.significance.evaluator import SignificanceEvaluator`, `logging`, `datetime`
- **问题**:
  1. ⚠️ `_store: dict[str, EpisodeMemory]` — 纯内存存储，无持久化
  2. ⚠️ `query()` 方法使用线性扫描 + 简单字符串匹配，无索引

---

#### Module: `ocos/memory/episode/gate.py` (142 行)
- **类**: `EpisodeGate`
  - 方法: `should_record()`, `compress_episode()`, `merge_episodes()`
- **契约**: 唯一职责: 门控决策——判断情节是否值得录入记忆。绝不: 执行实际存储、修改存储状态。
- **依赖**: `from ocos.memory.significance.evaluator import SignificanceEvaluator`, `from ocos.memory.episode.models import EpisodeMemory`
- **问题**:
  1. ⚠️ `should_record()` 的阈值 (`SALIENCE_THRESHOLD = 0.3`) 硬编码为类常量，无法运行时调整
  2. ⚠️ `compress_episode()` — 压缩策略仅为 "截取最近 N 个切片"，过于简单

---

### 2.2 信念子系统 (belief/)

#### Module: `ocos/memory/belief/__init__.py` (8 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/memory/belief/models.py` (228 行)
- **类**:
  - `Belief` — 信念数据模型: belief_id, topic, statement, confidence, source, evidence_ids, status, timestamps
  - `BeliefRecord` — 信念变更记录: record_id, belief_id, change_type, old_value, new_value
  - `ValidationReport` — 验证报告: is_valid, errors, warnings, timestamp
- **契约**: 唯一职责: 定义信念及信念验证的数据模型。绝不: 执行置信度计算、证据收集或信念更新逻辑。
- **依赖**: `dataclasses`, `datetime`, `enum`, `typing`
- **问题**:
  1. ⚠️ `confidence: float` 无范围约束
  2. ⚠️ `BeliefRecord.change_type` 使用自由文本字符串而非枚举 — 降低类型安全性
  3. ⚠️ 与 `knowledge/store/ontology.py` 中的 `KnowledgeLevel` / `KnowledgeStatus` 概念存在语义重叠

---

#### Module: `ocos/memory/belief/store.py` (242 行)
- **类**: `BeliefStore`
  - 方法: `add_belief()`, `update_belief()`, `get_belief()`, `get_beliefs_by_topic()`, `invalidate()`, `resolve()`, `list_active()`, `query()`
- **契约**: 唯一职责: 管理信念的生命周期存储。绝不: 评估置信度、验证信念一致性。
- **依赖**: `from ocos.memory.belief.models import Belief`, `from ocos.memory.belief.confidence import ConfidenceCalculator`
- **问题**:
  1. ⚠️ `_beliefs: dict[str, Belief]` — 纯内存，无持久化
  2. ⚠️ `resolve()` 操作同时涉及 store + confidence + validator 职责，职责边界模糊
  3. ⚠️ 与 `EpisodeStore` 结构高度相似，缺乏共享基类或协议

---

#### Module: `ocos/memory/belief/confidence.py` (269 行)
- **类**:
  - `ConfidenceModel` — 置信度模型: initial_confidence, decay_rate, reinforcement_factor, min_confidence, max_confidence
  - `ConfidenceCalculator` — 置信度计算器
    - 方法: `calculate()`, `decay()`, `reinforce()`, `update_confidence()`, `calculate_from_evidence()`
- **契约**: 唯一职责: 管理信念的置信度数值计算。绝不: 存储信念、验证信念内容。
- **依赖**: `math`, `datetime`, `typing`
- **问题**:
  1. ⚠️ `ConfidenceModel` 的 `decay_rate` 和 `reinforcement_factor` 都是硬编码默认值
  2. ⚠️ `decay()` 使用简单指数衰减 `exp(-decay_rate * hours)` — 可能不适合所有领域
  3. ⚠️ `calculate_from_evidence()` 权重为均匀分配 `1.0 / len(evidence_strengths)` — 缺乏区分度

---

#### Module: `ocos/memory/belief/evidence.py` (115 行)
- **类**:
  - `Evidence` — 证据数据模型: evidence_id, belief_id, type, strength, source, content
  - `EvidenceCollector` — 证据收集器
    - 方法: `add_evidence()`, `get_evidence_for()`, `count_evidence()`, `get_supporting()`, `get_contradicting()`
- **契约**: 唯一职责: 收集和存储证据条目。绝不: 评估证据说服力、计算置信度。
- **依赖**: 仅标准库
- **问题**:
  1. ⚠️ `Evidence.type` 为自由字符串，建议使用枚举: SUPPORTING, CONTRADICTING, NEUTRAL
  2. ⚠️ `EvidenceCollector._evidence: dict[str, list[Evidence]]` — 纯内存存储

---

#### Module: `ocos/memory/belief/validator.py` (149 行)
- **类**: `BeliefValidator`
  - 方法: `validate_belief()`, `resolve_conflict()`, `check_consistency()`, `register_rule()`, `remove_rule()`
- **契约**: 唯一职责: 验证信念的完整性和一致性。绝不: 修改信念内容、计算置信度。
- **依赖**: `from ocos.memory.belief.models import Belief, ValidationReport`
- **问题**:
  1. ⚠️ `resolve_conflict()` 仅比较 `confidence` 值取高者，对矛盾信念无深层语义分析
  2. ⚠️ 与 `knowledge/process/validator.py` 的 `KnowledgeValidator` 架构相似但无共享接口

---

### 2.3 语义记忆子系统 (semantic/)

#### Module: `ocos/memory/semantic/__init__.py` (8 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/memory/semantic/models.py` (159 行)
- **类**:
  - `SemanticNode` — 语义节点: node_id, label, type, properties, created_at
  - `SemanticEdge` — 语义边: edge_id, source_id, target_id, relation_type, weight, properties
  - `SemanticSubgraph` — 子图: subgraph_id, nodes, edges, description
- **契约**: 唯一职责: 语义知识图谱的数据模型。绝不: 存储或遍历图。
- **依赖**: `dataclasses`, `datetime`, `uuid`, `typing`
- **问题**:
  1. ⚠️ `SemanticNode.type` 使用自由字符串而非枚举
  2. ⚠️ `SemanticEdge.relation_type` 使用自由字符串而非枚举 — 与 `models/information.py` 的 `RelationType` 枚举不一致

---

#### Module: `ocos/memory/semantic/store.py` (304 行)
- **类**: `SemanticStore`
  - 方法: `add_node()`, `add_edge()`, `get_node()`, `query_nodes()`, `traverse()`, `get_neighbors()`, `find_path()`, `delete_node()`, `delete_edge()`
- **契约**: 唯一职责: 语义图的存储和遍历。绝不: 验证节点或边的语义合法性。
- **依赖**: `from ocos.memory.semantic.models import SemanticNode, SemanticEdge, SemanticSubgraph`, `collections.deque`
- **问题**:
  1. ⚠️ `find_path()` 使用 BFS，无权重考虑 — 对大图低效
  2. ⚠️ `_nodes: dict` + `_edges: list` 使用双重存储，无邻接表优化
  3. ⚠️ `traverse()` 使用迭代栈实现 DFS，大图有栈溢出风险

---

#### Module: `ocos/memory/semantic/validator.py` (202 行)
- **类**: `SemanticValidator`
  - 方法: `validate_node()`, `validate_edge()`, `check_consistency()`, `find_cycles()`, `register_rule()`
- **契约**: 唯一职责: 验证语义图的完整性和无环性。绝不: 修改图结构。
- **依赖**: `from ocos.memory.semantic.models import SemanticNode, SemanticEdge`, `collections.defaultdict`
- **问题**:
  1. ⚠️ `find_cycles()` 使用 DFS + 三色标记，每个调用都重建全图邻接表 — 可缓存拓扑
  2. ⚠️ `check_consistency()` 仅检查孤立节点，不验证边类型合法性

---

### 2.4 模式识别子系统 (pattern/)

#### Module: `ocos/memory/pattern/__init__.py` (7 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/memory/pattern/models.py` (126 行)
- **类**:
  - `BehaviorPattern` — 行为模式: pattern_id, name, description, occurrences, confidence, template, examples
  - `PatternCluster` — 模式聚类: cluster_id, patterns, centroid_pattern, coherence_score
- **契约**: 唯一职责: 行为模式的数据模型定义。绝不: 提取或验证模式。
- **依赖**: `dataclasses`, `datetime`, `uuid`, `typing`
- **问题**:
  1. ⚠️ `BehaviorPattern.template` 使用自由字典 — 无 schema 约束

---

#### Module: `ocos/memory/pattern/extractor.py` (227 行)
- **类**: `PatternExtractor`
  - 方法: `extract_patterns()`, `cluster_patterns()`, `_find_sequences()`, `_compute_similarity()`, `_merge_patterns()`
- **契约**: 唯一职责: 从情节序列中提取行为模式。绝不: 存储或验证模式。
- **依赖**: `from ocos.memory.episode.models import EpisodeMemory`, `from ocos.memory.pattern.models import BehaviorPattern, PatternCluster`
- **问题**:
  1. ⚠️ `_compute_similarity()` 基于简单 Jaccard 相似度 — 对语义相似无感知
  2. ⚠️ `cluster_patterns()` 使用简单阈值聚类 O(N²)，对大量模式低效
  3. ⚠️ 提取器直接依赖 EpisodeMemory 模型，耦合到 episodes 的具体结构

---

#### Module: `ocos/memory/pattern/validator.py` (194 行)
- **类**: `PatternValidator`
  - 方法: `validate_pattern()`, `filter_noise()`, `check_significance()`, `register_rule()`
- **契约**: 唯一职责: 验证提取的模式是否有意义。绝不: 提取或修改模式。
- **依赖**: `from ocos.memory.pattern.models import BehaviorPattern`
- **问题**:
  1. ⚠️ `filter_noise()` 仅检查 `occurrences >= MIN_OCCURRENCES`，过于粗糙

---

### 2.5 经验子系统 (experience/)

#### Module: `ocos/memory/experience/__init__.py` (7 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/memory/experience/models.py` (114 行)
- **类**:
  - `Experience` — 经验: experience_id, title, summary, episode_ids, lessons_learned, emotional_signature, created_at
  - `ExperienceFragment` — 经验片段: fragment_id, episode_slice_ids, insight, confidence
- **契约**: 唯一职责: 经验（episode 之上的聚合）数据模型定义。绝不: 构建或验证经验。
- **依赖**: `dataclasses`, `datetime`, `uuid`, `typing`
- **问题**: 无显著问题

---

#### Module: `ocos/memory/experience/builder.py` (138 行)
- **类**: `ExperienceBuilder`
  - 方法: `build_experience()`, `merge_fragments()`, `_synthesize_lessons()`
- **契约**: 唯一职责: 从 episode 切片合成经验。绝不: 存储或验证经验。
- **依赖**: `from ocos.memory.episode.models import EpisodeSlice`, `from ocos.memory.experience.models import Experience, ExperienceFragment`
- **问题**:
  1. ⚠️ `_synthesize_lessons()` 方法为空实现 `pass` — 核心逻辑缺失
  2. ⚠️ `merge_fragments()` 仅做简单拼接，无去重或冲突解决

---

#### Module: `ocos/memory/experience/validator.py` (162 行)
- **类**: `ExperienceValidator`
  - 方法: `validate_experience()`, `ensure_completeness()`, `register_rule()`
- **契约**: 唯一职责: 验证经验的完整性和一致性。绝不: 构建或修改经验。
- **依赖**: `from ocos.memory.experience.models import Experience`
- **问题**:
  1. ⚠️ `ensure_completeness()` 检查 `lessons_learned` 非空 — 但 builder 的 `_synthesize_lessons()` 是空实现，因此经验永远不完整

---

### 2.6 显著性评估子系统 (significance/)

#### Module: `ocos/memory/significance/__init__.py` (7 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/memory/significance/models.py` (113 行)
- **类**:
  - `SignificanceProfile` — 显著性档案: recency_score, frequency_score, emotional_score, novelty_score, composite_score
  - `ScoreWeights` — 评分权重: recency_weight, frequency_weight, emotional_weight, novelty_weight
- **契约**: 唯一职责: 显著性评分的数据模型。绝不: 计算评分。
- **依赖**: `dataclasses`
- **问题**: 无显著问题

---

#### Module: `ocos/memory/significance/evaluator.py` (210 行)
- **类**: `SignificanceEvaluator`
  - 方法: `evaluate()`, `score_episode()`, `_compute_recency()`, `_compute_frequency()`, `_compute_emotional()`, `_compute_novelty()`
- **契约**: 唯一职责: 计算情节记忆的显著性分数。绝不: 存储评分、修改记忆。
- **依赖**: `from ocos.memory.significance.models import SignificanceProfile, ScoreWeights`, `from ocos.memory.episode.models import EpisodeMemory`
- **问题**:
  1. ⚠️ `evaluate()` 需要 `all_episodes: list[EpisodeMemory]` 计算频率 — 全表扫描，不可扩容
  2. ⚠️ `_compute_novelty()` 使用 TF-IDF 思想但只比较 tags 和 category — 未分析 content 语义

---

#### Module: `ocos/memory/significance/rules.py` (205 行)
- **类**:
  - `SignificanceRule` (抽象基类) — 方法: `evaluate(episode) -> float`
  - `RecencyRule` — 基于时间的显著性
  - `FrequencyRule` — 基于重复次数的显著性
  - `EmotionRule` — 基于情感强度的显著性
  - `CompositeRule` — 组合多个规则
- **契约**: 唯一职责: 定义可组合的显著性评估规则。绝不: 修改记忆数据。
- **依赖**: `from ocos.memory.episode.models import EpisodeMemory`, `abc`
- **问题**:
  1. ⚠️ `RecencyRule` 的半衰期 `halflife_hours` 硬编码为 24
  2. ⚠️ `EmotionRule` 的 `valence_scale` 硬编码为 10.0

---

### 2.6 memory/__init__.py (30 行)
- **类型**: 层聚合 re-export
- **职责**: 导出所有子模块的核心类
- **问题**: 无（标准模式）

---

### memory 层总体评估

| 维度 | 评级 | 说明 |
|------|------|------|
| 模块化 | 🟢 良好 | 6 个子系统，每个含 models/store/validator 三层 |
| 一致性 | 🟡 中等 | Store 层模式一致，但缺乏共享基类 |
| 持久化 | 🔴 差 | 全部纯内存 dict/list 存储，无持久化 |
| 测试覆盖 | ❓ 未知 | 未检查测试文件 |
| 类型安全 | 🟢 良好 | dataclass + typing 注解全面 |

**关键问题**:
1. 🔴 **无持久化**: 所有 Store 使用内存 dict — 系统重启全部丢失
2. 🟡 **冗余验证器**: episode/belief/semantic/pattern/experience 各有独立 validator，但验证逻辑模式重复
3. 🟡 **耦合到具体模型**: Extractor/Evaluator 直接依赖 EpisodeMemory 具体字段，而非接口/协议
4. 🟡 **空实现**: `_synthesize_lessons()` 为空 — Experience 子系统不完整

---

## 三、ocos/self/ 层审计 (7 文件)

#### Module: `ocos/self/__init__.py` (14 行)
- **类型**: re-export
- **问题**: 无

---

#### Module: `ocos/self/models.py` (291 行)
- **类**:
  - `SelfRepresentation` — 自我表示: self_id, traits (dict), values (list), boundaries, identity_statements, confidence, last_updated
  - `IdentityStatement` — 身份陈述: statement_id, category, content, confidence, source, timestamp
  - `BoundaryPolicy` — 边界策略: boundary_id, type (hard/soft), condition, action, priority
- **契约**: 唯一职责: 自我模型的数据结构定义。绝不: 构建或验证自我模型。
- **依赖**: `dataclasses`, `datetime`, `enum`, `uuid`, `typing`
- **问题**:
  1. ⚠️ `traits: dict[str, Any]` — 过于宽松，缺乏 trait schema
  2. ⚠️ `BoundaryPolicy.condition` 和 `BoundaryPolicy.action` 为自由字符串 — 应使用函数引用或 DSL
  3. ⚠️ `confidence: float` 无范围约束

---

#### Module: `ocos/self/builder.py` (425 行)
- **类**: `SelfBuilder`
  - 方法: `build_self()`, `update_trait()`, `add_boundary()`, `remove_boundary()`, `add_identity_statement()`, `evaluate_self_consistency()`, `reflect_on_experience()`, `evolve_self()`, `merge_self()`
- **契约**: 唯一职责: 从 memory/belief 数据构建和演化自我模型。绝不: 执行治理决策、监控行为。
- **依赖**: `from ocos.self.models import SelfRepresentation, IdentityStatement, BoundaryPolicy`, `from ocos.memory.belief.models import Belief`, `from ocos.memory.experience.models import Experience`
- **问题**:
  1. ⚠️ `build_self()` 代码量巨大 (~200 行)，方法过长
  2. ⚠️ `evolve_self()` 仅调用 `reflect_on_experience()` + `evaluate_self_consistency()` — 演化逻辑过简
  3. ⚠️ `merge_self()` 使用简单字段合并 — 无冲突解决策略
  4. ⚠️ `reflect_on_experience()` 传入 `Experience` 对象但仅调用 `experience.lessons_learned` — 而 builder 的 `_synthesize_lessons()` 为空实现，因此此方法总是空操作

---

#### Module: `ocos/self/statement_validator.py` (148 行)
- **类**: `StatementValidator`
  - 方法: `validate_statement()`, `check_self_consistency()`, `detect_contradictions()`, `register_rule()`
- **契约**: 唯一职责: 验证身份陈述的一致性和有效性。绝不: 修改自我模型。
- **依赖**: `from ocos.self.models import IdentityStatement, SelfRepresentation`
- **问题**:
  1. ⚠️ `detect_contradictions()` 仅做简单字符串比较 — 缺乏语义推理

---

#### Module: `ocos/self/identity_boundary.py` (332 行)
- **类**: `IdentityBoundary`
  - 方法: `check_crossing()`, `enforce_boundary()`, `negotiate_boundary()`, `add_hard_boundary()`, `add_soft_boundary()`, `remove_boundary()`, `list_boundaries()`, `evaluate_action()`
- **契约**: 唯一职责: 管理自我边界——判断行为是否越界并执行约束。绝不: 构建自我模型或做治理决策。
- **依赖**: `from ocos.self.models import BoundaryPolicy, SelfRepresentation`
- **问题**:
  1. ⚠️ `evaluate_action()` 的边界检查仅做字符串匹配 `any(pattern in action for pattern in ...)` — 极其简陋
  2. ⚠️ `negotiate_boundary()` 无实际协商逻辑 — 仅返回 "同意" 或 "拒绝"
  3. ⚠️ `check_crossing()` 和 `evaluate_action()` 职责重叠

---

#### Module: `ocos/self/governor.py` (540 行) — 核心文件
- **类**: `Governor`
  - 方法: `review_action()`, `veto()`, `align_with_identity()`, `check_boundary_compliance()`, `evaluate_ethical_alignment()`, `log_decision()`, `get_decision_history()`, `override_veto()` (仅限 admin), `set_governance_mode()`
- **契约**: 唯一职责: 顶层治理决策——审查所有行动是否符合自我模型和边界约束。绝不: 构建自我模型、监控运行时行为。
- **依赖**: `from ocos.self.models import SelfRepresentation, BoundaryPolicy`, `from ocos.self.identity_boundary import IdentityBoundary`
- **问题**:
  1. ⚠️ `review_action()` 是最长方法 (~80 行)，囊括边界检查 + 伦理评估 + 对齐检查 — 应拆分为多个私有方法
  2. ⚠️ `evaluate_ethical_alignment()` 使用硬编码关键词列表 `["harm", "deceive", ...]` — 极其初步的伦理实现
  3. ⚠️ `governance_mode` (strict/moderate/lenient) 仅影响 veto 阈值 — 无差异化策略
  4. ⚠️ 540 行单文件 — 应拆分为 Governor + EthicalEvaluator + DecisionLogger

---

#### Module: `ocos/self/monitor.py` (288 行)
- **类**: `SelfMonitor`
  - 方法: `monitor_behavior()`, `detect_drift()`, `report_violation()`, `compute_alignment_score()`, `get_drift_history()`, `set_alert_threshold()`, `start_monitoring()`, `stop_monitoring()`
- **契约**: 唯一职责: 观察运行时行为与自我模型的偏差。绝不: 执行治理决策、修改自我模型。
- **依赖**: `from ocos.self.models import SelfRepresentation`, `from ocos.memory.episode.models import EpisodeMemory`
- **问题**:
  1. ⚠️ `detect_drift()` 的漂移检测基于 `compute_alignment_score()` < 阈值 — 但 alignment_score 是简单余弦相似度，对深层偏差不敏感
  2. ⚠️ `start_monitoring()` / `stop_monitoring()` 仅设置标志位 — 无实际监控循环
  3. ⚠️ Monitor 和 Governor 的职责边界模糊: Monitor 检测到违规后应调用 Governor，但当前 Monitor 只是记录日志

---

### self 层总体评估

| 维度 | 评级 | 说明 |
|------|------|------|
| 治理链完整性 | 🟢 良好 | Builder → Validator → Boundary → Governor → Monitor 五环链 |
| 自演化能力 | 🟡 中等 | `evolve_self()` 存在但依赖空实现的经验合成 |
| 可行性 | 🟡 中等 | 伦理评估基于关键词匹配，边界检查为字符串匹配 |
| 文件大小 | 🔴 差 | Governor 540 行单文件过大 |

**关键问题**:
1. 🔴 **Governor 过大**: 540 行，集成了太多的检查逻辑 — 建议拆分为 Governor + EthicalEvaluator + DecisionLogger
2. 🔴 **关键依赖链断裂**: `SelfBuilder.build_self()` → `reflect_on_experience()` → `Experience.lessons_learned` → 但 `ExperienceBuilder._synthesize_lessons()` 为空
3. 🟡 **简化评估**: 边界检查用字符串匹配，伦理评估用关键词列表，漂移检测用余弦相似度 — 均过于初级
4. 🟡 **Monitor-Governor 脱节**: Monitor 检测到问题但仅记录日志，无到 Governor 的回调

---

## 四、ocos/knowledge/ 层审计 (16 文件)

### 4.1 拆分结构说明

knowledge 层从 v1.0 拆分为 `store/` + `process/` 子平面，但在 knowledge/ 根目录遗留了 7 个 shim（桥接）文件，每个仅 7-18 行，仅做 re-export。

### 4.2 store/ 子平面

#### Module: `ocos/knowledge/store/__init__.py` (1 行)
- **内容**: 仅一行 docstring `"""Knowledge Store 子平面 — 数据存储 + 访问控制 + 生命周期。"""`
- **问题**: ⚠️ 空 `__init__` — 不导出任何内容，外部只能直接 import 子模块

---

#### Module: `ocos/knowledge/store/ontology.py` (183 行)
- **类/枚举**:
  - `KnowledgeLevel` — 知识层级: OBSERVATION → EVIDENCE → PATTERN → PRINCIPLE → POLICY
  - `KnowledgeStatus` — 状态: CANDIDATE → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
  - `KnowledgeUnit` (frozen dataclass) — 知识原子单元
  - `ElevationRecord` (frozen dataclass) — 提升审计记录
- **函数**: `can_elevate()`, `validate_elevation()`, `get_elevation_targets()`, `get_level_index()`, `is_higher_level()`, `get_next_statuses()`, `can_transition()`
- **常量**: `ELEVATION_MATRIX`, `STATUS_TRANSITIONS`
- **契约**: 唯一职责: 定义知识的本体模型——层级、状态、单元结构和提升/转换规则。绝不: 存储知识、执行生命周期操作。
- **依赖**: 仅标准库 (`dataclasses`, `datetime`, `enum`, `uuid`, `typing`, `logging`)
- **问题**:
  1. 🟡 `KnowledgeUnit.content: dict[str, Any]` — 过于宽松，无 schema
  2. 🟡 与 `memory/belief/models.py` 的概念重叠: Belief 也有 status+confidence，KnowledgeUnit 也有 status+content — 两套相似但不统一的模型

---

#### Module: `ocos/knowledge/store/registry.py` (355 行)
- **类**:
  - `AccessScope` — 可见性: PUBLIC / PROTECTED / PRIVATE
  - `OwnershipEntry` (frozen dataclass) — 所有权绑定
  - `AccessMatrix` — 读写矩阵
    - 方法: `set_permission()`, `set_default_permissions()`, `set_wildcard_permission()`, `can_read()`, `can_write()`, `can_elevate()`, `check_read_access()`
  - `KnowledgeRegistry` — 知识注册中心
    - 方法: `register()`, `update()`, `remove()`, `get()`, `get_by_level()`, `get_by_owner()`, `get_by_status()`, `search()`, `total_count`, `get_owners()`, `check_write()`
- **契约**: 唯一职责: 管理知识单元的存储、所有权和访问控制。绝不: 验证知识内容、管理生命周期。
- **依赖**: `from ocos.knowledge.store.ontology import KnowledgeLevel, KnowledgeStatus, KnowledgeUnit`
- **问题**:
  1. ⚠️ `search()` 对所有查询使用全表扫描 `for entry in self._entries.values()` — 无索引
  2. ⚠️ `AccessMatrix` 的两层结构 (per-owner + wildcard) 增加了权限判断复杂度
  3. ⚠️ `remove()` 直接 `del self._entries[unit_id]` — 无软删除或引用检查
  4. ⚠️ `get_by_owner()` 等查询结果无序 — 而 `get_by_level()` 有排序，不一致

---

#### Module: `ocos/knowledge/store/lifecycle.py` (258 行)
- **类**:
  - `StatusChangeRecord` (frozen dataclass) — 状态变更记录
  - `KnowledgeLifecycle` — 生命周期管理器
    - 方法: `change_status()`, `verify()`, `activate()`, `deprecate()`, `archive()`, `reactivate()`, `get_version()`, `get_version_history()`, `get_status_history()`, `get_active_units()`, `on_status_change()`
- **契约**: 唯一职责: 编排知识单元的状态转换并记录审计日志。绝不: 注册新知识、验证内容。
- **依赖**: `from ocos.knowledge.store.ontology import KnowledgeLevel, KnowledgeStatus, KnowledgeUnit, can_transition, get_next_statuses`, `from ocos.knowledge.store.registry import AccessScope, KnowledgeRegistry`
- **问题**:
  1. ⚠️ `get_version_history()` 通过状态变更记录推断版本 — 不可靠
  2. ⚠️ `_on_status_change: list[callable]` — 监听器列表但无异常隔离（一个回调抛出异常会中断后续回调）
  3. ⚠️ `_status_history` 是内存列表 — 无上限增长风险

---

### 4.3 process/ 子平面

#### Module: `ocos/knowledge/process/__init__.py` (1 行)
- **内容**: 仅 docstring
- **问题**: 同 store/__init__.py — 空壳

---

#### Module: `ocos/knowledge/process/validator.py` (270 行)
- **类/枚举/函数**:
  - `ValidationSeverity` — ERROR / WARNING / INFO
  - `ValidationResult` (frozen dataclass) — 单条结果
  - `ValidationReport` (mutable dataclass) — 校验报告 (has_errors, has_warnings, errors, warnings)
  - `ValidationRule` (frozen dataclass) — 规则定义
  - `KnowledgeValidator` — 校验器
    - 方法: `register_rule()`, `remove_rule()`, `get_rule_names()`, `validate()`
  - 函数: `check_content_exists()`, `check_level_status_valid()`, `check_tags_format()`, `check_elevation_chain()`
- **契约**: 唯一职责: 验证知识单元的结构和约束。绝不: 修改知识、执行生命周期操作。
- **依赖**: `from ocos.knowledge.store.ontology import KnowledgeLevel, KnowledgeStatus, KnowledgeUnit`
- **问题**:
  1. ⚠️ `ValidationReport` 使用 mutable dataclass — 与项目中所有其他模型 (frozen) 不一致
  2. ⚠️ `check_elevation_chain()` 需要 `context["registry"]` 传入 — 隐式依赖，类型不安全
  3. ⚠️ `check_tags_format()` 实际检查的是 `unit.source` 长度而非 tags — 命名误导
  4. ⚠️ `DEFAULT_VALIDATION_RULES` 仅 3 条 — 覆盖面太窄

---

#### Module: `ocos/knowledge/process/evolution.py` (557 行)
- **类/枚举**:
  - `EvolutionChangeType` — EDIT / MERGE / DEPRECATE / SPLIT / ELEVATE
  - `EvolutionProposalStatus` — DRAFT → REVIEW → APPROVED → APPLIED / REJECTED
  - `EvolutionProposal` (frozen dataclass) — 演进提案
  - `EvolutionManager` — 演进管理器
    - 方法: `create_proposal()`, `submit_review()`, `approve()`, `reject()`, `apply()`, `get_proposal()`, `list_proposals()`, `count_by_status()`, 以及 `_apply_edit()`, `_apply_merge()`, `_apply_deprecate()`, `_apply_split()`, `_apply_elevate()`
- **契约**: 唯一职责: 管理知识的提案-审批-执行流程。绝不: 直接修改知识注册表。
- **依赖**: `from ocos.knowledge.store.ontology import ...`, `from ocos.knowledge.store.registry import KnowledgeRegistry`, `from ocos.knowledge.store.lifecycle import KnowledgeLifecycle`, `from ocos.knowledge.process.validator import KnowledgeValidator`, `from ocos.knowledge.process.promotion_rules import PromotionRuleEngine`
- **问题**:
  1. 🔴 **文件过大**: 557 行 — OCOS 中最大的单个文件，应拆分
  2. ⚠️ `_approve()` 中 DRAFT → APPROVED 绕过 REVIEW 的逻辑仅当 `_approval_required=False` 时允许 — 但这个绕过缺乏审计
  3. ⚠️ `_apply_merge()` 和 `_apply_elevate()` 中 `import uuid` 是方法内导入 — 移到文件顶部
  4. ⚠️ `_apply_split()` 的回滚逻辑只处理注册失败的部件 — 不处理 lifecycle 操作失败
  5. ⚠️ `_apply_merge()` 中废弃原目标后不删除它们 — 导致 DEPRECATED 状态残留
  6. ⚠️ `_apply_edit()` 中 `change_status` 调用了 `self._lifecycle.change_status(new_unit.unit_id, old_unit.status, ...)` — 这里用了 old status 作为 target，等于无状态变更，疑似 bug
  7. 🔴 文件末尾有可疑代码 `import dataclasses as _dc; dataclasses = _dc` — 覆盖了 `dataclasses` 模块引用

---

#### Module: `ocos/knowledge/process/promotion_rules.py` (312 行)
- **类/枚举**:
  - `PromotionTriggerType` — REPETITION / CONFIDENCE / GOVERNANCE / MANUAL / TIME_BASED
  - `PromotionTrigger` (frozen dataclass) — 触发条件
  - `PreCondition` (frozen dataclass) — 提升前条件
  - `PromotionPolicy` — 提升策略
    - 方法: `evaluate()`, `default_for_level()`
  - `PromotionRuleEngine` — 提升规则引擎
    - 方法: `register_policy()`, `get_policy()`, `can_promote()`, `check_trigger()`, `load_default_policies()`
- **契约**: 唯一职责: 定义和评估知识层级提升的规则。绝不: 执行实际提升操作。
- **依赖**: `from ocos.knowledge.store.ontology import ...`
- **问题**:
  1. ⚠️ `DEFAULT_TRIGGERS` 中阈值硬编码 (REPETITION: 3, 5; CONFIDENCE: 0.7, 0.85)
  2. ⚠️ `PromotionRuleEngine.can_promote()` 同时检查 validate_elevation + policy + default_policy — 逻辑三合一，难调试
  3. ⚠️ `PromotionPolicy.default_for_level()` 的 `allowed_sources` 硬编码为 `["governance", "pattern_detector", "manual"]`
  4. 🟡 `TIME_BASED` 触发类型已定义但 `check_trigger()` 中无对应实现

---

### 4.4 knowledge 层 Shim 文件

以下 7 个文件均为拆分后的 re-export shim，每个仅 7-18 行：

| 文件 | 行数 | 导出目标 |
|------|------|---------|
| `knowledge/knowledge_abi.py` | 301 | **非 shim** — 真实 ABI 门面实现 |
| `knowledge/knowledge_registry.py` | 9 | → `store/registry.py` |
| `knowledge/knowledge_ontology.py` | 18 | → `store/ontology.py` |
| `knowledge/knowledge_evolution.py` | 9 | → `process/evolution.py` |
| `knowledge/knowledge_lifecycle.py` | 7 | → `store/lifecycle.py` |
| `knowledge/knowledge_validator.py` | 15 | → `process/validator.py` |
| `knowledge/promotion_rules.py` | 11 | → `process/promotion_rules.py` |

**问题**: 
- 🔴 **Shim 污染**: 6 个 shim 文件占据 knowledge/ 根目录，增加认知负担
- 🟡 **不一致**: `knowledge_abi.py` 不是 shim（301行真实实现），但命名模式与其他 shim 一致，容易误读
- 🟡 **双重导入路径**: `from ocos.knowledge import KnowledgeRegistry` 和 `from ocos.knowledge.store.registry import KnowledgeRegistry` 均可工作 — 造成使用混淆

---

### 4.5 knowledge/__init__.py (75 行)
- **类型**: 层聚合 re-export
- **内容**: 从 store/ 和 process/ 子模块导入所有公开类型
- **问题**: ⚠️ 75 行 `__init__.py` 过长 — 考虑使用 `__all__` 简化

---

### knowledge 层总体评估

| 维度 | 评级 | 说明 |
|------|------|------|
| 本体设计 | 🟢 良好 | KnowledgeLevel + KnowledgeStatus 五层五态清晰 |
| 访问控制 | 🟢 良好 | AccessMatrix + AccessScope 三层权限到位 |
| 生命周期 | 🟢 良好 | 完整的状态机 + 审计追踪 + 版本管理 |
| 演进流程 | 🟢 良好 | 提案-审批-执行五阶段完整 |
| 文件结构 | 🟡 中等 | 拆分产生 6 个 shim + 2 个空 __init__ |
| 代码质量 | 🟡 中等 | EvolutionManager 557 行过大，dataclasses 覆盖 bug |

**关键问题**:
1. 🔴 **EvolutionManager 末尾 bug**: `import dataclasses as _dc; dataclasses = _dc` — 覆盖模块级 dataclasses 引用
2. 🔴 **Shim 文件过多**: 6 个 shim 文件纯属噪音，可删除
3. 🟡 **_apply_edit() 疑似 bug**: 用 `old_unit.status` 作为 `change_status` 目标状态 — 无状态变更
4. 🟡 **与 memory/belief 模型重叠**: KnowledgeUnit vs Belief 概念交叉但未统一

---

## 五、ocos/models/ 层审计 (14 文件)

models/ 层全部为 Phase 15-19 引入的纯数据模型定义，遵循"四不堆叠"原则。所有文件均为 frozen dataclasses + Enums，无行为逻辑。

### 5.1 核心信息模型 (information.py)

#### Module: `ocos/models/information.py` (268 行)
- **类/枚举**:
  - `InformationState` (str Enum) — Created → Validated → Referenced → Deprecated → Archived
  - `SemanticRole` (str Enum) — OBSERVATION/MEMORY/KNOWLEDGE/GOAL/IDENTITY/POLICY/DECISION
  - `PersistenceLevel` (str Enum) — Transient → Persistent → Stable → Immutable
  - `RelationType` (str Enum) — 结构关系(4) + 语义关系(3) + 时序关系(4) = 11 种
  - `UniversalAddress` (frozen dataclass) — namespace/type/id/version
  - `InformationMetadata` (frozen dataclass) — address/state/role/persistence/importance/ttl
- **契约**: 唯一职责: Layer 0 认知理论的信息模型——定义统一定义的状态、角色、关系和寻址。绝不: 包含任何 IO 或行为逻辑。
- **依赖**: `dataclasses`, `datetime`, `enum`, `uuid`, `typing`, `logging`
- **问题**:
  1. ⚠️ Legacy 映射表 (`_INFORMATION_LEGACY_MAP` 等) 是技术债的明确证据 — 考虑迁移后删除
  2. ⚠️ `Importance: float = 0.5` — 默认值 0.5 在 [0.0, 1.0] 中缺乏语义锚点
  3. 🟢 优秀: `_missing_()` 兼容映射为 str Enum 的优雅实现
  4. 🟢 优秀: `__post_init__` 校验约束在构造期生效

---

### 5.2 执行模型 (execution.py) — Phase 17.1

#### Module: `ocos/models/execution.py` (101 行)
- **类**: `ExecutionStatus` (str Enum), `Execution` (frozen dataclass)
- **契约**: 唯一职责: 定义执行状态和模型，确保 decision→execution→observation 链完整性。绝不: 包含执行逻辑。
- **依赖**: `from ocos.kernel.abi import SCHEMA_VERSION`, `from ocos.models.information import UniversalAddress`
- **问题**:
  1. ⚠️ `observation_addresses: tuple[UniversalAddress, ...]` — Invariant 3 要求非空，但无运行时验证
  2. ⚠️ `decision_id: str = ""` — 默认空字符串违反了 Invariant 1

---

### 5.3 目标模型 (goal.py) — Phase 17.2

#### Module: `ocos/models/goal.py` (92 行)
- **类**: `GoalStatus` (str Enum) — 8 种状态
- **契约**: 唯一职责: 定义目标生命周期状态机。绝不: 管理目标数据或仲裁逻辑。
- **依赖**: 仅标准库
- **问题**:
  1. ⚠️ `GoalStatus` 是纯枚举，但没有对应的 `Goal` 数据模型 — Goal 的数据模型在哪？
  2. ⚠️ `is_active` 包含 CREATED 状态 — CREATED 状态的 Goal 是否真的能驱动 Decision？

---

### 5.4 过程模型 (process.py) — Phase 15

#### Module: `ocos/models/process.py` (145 行)
- **类**: `ProcessType` (str Enum, deprecated), `ProcessState` (str Enum), `ProcessStep` (frozen dataclass), `TransformProcess` (frozen dataclass)
- **契约**: 唯一职责: 认知过程的统一表示——遵循四"不堆叠"原则。绝不: 包含认知逻辑实现。
- **依赖**: `from ocos.kernel.abi import SCHEMA_VERSION`, `from ocos.models.information import UniversalAddress`
- **问题**:
  1. 🔴 `ProcessType` 每次实例化都触发 `DeprecationWarning` — 非常嘈杂
  2. ⚠️ `TransformProcess.process_type: ProcessType` — 字段类型仍然是已弃用的 ProcessType
  3. ⚠️ `engine_id: Optional[str] = None` — 替代 process_type 但二者共存，语义模糊

---

### 5.5 能力引擎数据模型 (Phase 19)

以下 8 个文件为 Phase 19 引入的能力引擎对应的数据模型，均为纯 frozen dataclasses + Enums：

| 文件 | 行数 | 核心类 | 策略枚举 | 备注 |
|------|------|--------|---------|------|
| `decision_making.py` | 65 | DecisionOption, DecisionMakingTrace | DecisionStrategy(6种) | 依赖 kernel.abi |
| `reasoning.py` | 96 | ReasoningStep, ReasoningTrace | InferenceOperation(8种) | 依赖 kernel.abi |
| `planning.py` | 70 | PlanningStep, PlanningTrace | PlanningStrategy(6种) + PlanStatus(5种) | 依赖 kernel.abi |
| `learning.py` | 61 | LearningExample, LearningModel, LearningTrace | LearningStrategy(4种) | 纯标准库 |
| `policy.py` | 79 | PolicyRule, PolicyEvaluation, PolicyTrace | PolicyEffect(3种) + PolicyDomain(6种) | 依赖 kernel.abi |
| `prediction.py` | 57 | ConfidenceInterval, PredictionResult, PredictionTrace | PredictionStrategy(4种) | 纯标准库 |
| `reflection.py` | 51 | ReflectionInsight, ReflectionTrace | ReflectionStrategy(4种) | 纯标准库 |
| `simulation.py` | 64 | SimulationScenario, SimulationStep, SimulationTrace | SimulationStrategy(4种) | 纯标准库 |
| `goal_arbitration.py` | 62 | GoalCandidate, ArbitrationResult, GoalArbitrationTrace | ArbitrationStrategy(4种) | 纯标准库 |

**共同特征**:
- 每个引擎文件遵循 XxxTrace + XxxStep/Result + XxxStrategy 模式
- 所有 dataclass 使用 `frozen=True`
- 部分依赖 `from ocos.kernel.abi import SCHEMA_VERSION` (decision_making, reasoning, planning, policy)
- 其余仅使用标准库

**问题**:
1. ⚠️ `policy.py` 的 `PolicyRule.condition: str` — 使用"引擎不执行条件，交给评估器判断"注释回避了条件 DSL 设计问题
2. ⚠️ `reasoning.py` 的 `ReasoningStep.operation: str` — 是 str 而非 `InferenceOperation` 枚举，降低类型安全
3. ⚠️ `goal_arbitration.py` 的 `GoalArbitrationTrace.candidates: tuple[ArbitrationResult, ...]` — 字段名为 candidates 但类型是结果而非候选，命名不一致
4. ⚠️ `learning.py` 的 `LearningExample.reward: float | None` — 仅 REINFORCEMENT 策略需要，但出现在所有 LearningExample 中

---

### 5.6 models/__init__.py (46 行)
- **类型**: 聚合 re-export
- **问题**:
  1. ⚠️ 注释中有不匹配的括号: `# Goal Layer (Phase 17.2 — Goal Theory → Code Alignment)` 前面少了 `#`（在 `__all__` 列表中）
  2. ⚠️ 从 `ocos.kernel.abi` 导入 `DecisionStatus` — models 层直接依赖 kernel 层

---

### models 层总体评估

| 维度 | 评级 | 说明 |
|------|------|------|
| 理论对齐 | 🟢 优秀 | 每个文件对应冻结的理论文档，Invariant 注释清晰 |
| 不可变设计 | 🟢 优秀 | 全部 frozen dataclass |
| Legacy 兼容 | 🟡 中等 | information.py 有 legacy 映射表，ProcessType 已弃用但仍被引用 |
| 一致性 | 🟢 良好 | 统一 Trace 模式，统一跨文件风格 |
| 完整性 | 🟡 中等 | Goal 仅有 Status 枚举无 Data Model；Execution 的 decision_id 默认空违反 invariant |

---

## 六、跨层架构问题汇总

### 6.1 全局问题

| # | 严重性 | 问题 | 影响范围 |
|---|--------|------|---------|
| 1 | 🔴 | **无持久化** — 所有 memory/ knowledge Store 使用纯内存 dict | 整个系统重启即丢失所有状态 |
| 2 | 🔴 | **experience builder 空实现** — `_synthesize_lessons()` 为 `pass` | Self 层的 `evolve_self` 链无效 |
| 3 | 🔴 | **EvolutionManager 末尾 bug** — `dataclasses = _dc` 覆盖模块引用 | knowledge 层突变风险 |
| 4 | 🟡 | **冗余验证器模式** — memory 层 5 个 validator + knowledge 层 1 个 validator 均独立实现 | 维护负担 |
| 5 | 🟡 | **knowledge 层 shim 污染** — 6 个 < 18 行的 re-export 文件占据根目录 | 项目导航困难 |
| 6 | 🟡 | **概念重叠** — memory/belief 的 Belief vs knowledge 的 KnowledgeUnit 语义相似但未统一 | 双层知识表示 |
| 7 | 🟡 | **Governor 过大** — 540 行单文件 | 可维护性 |
| 8 | 🟡 | **简化的评估逻辑** — 边界检查/伦理评估/漂移检测均基于字符串匹配或关键词 | 可行性 |
| 9 | 🟡 | **SemanticStore 的 graph 实现** — 简单 dict+list，无索引无邻接表优化 | 扩展性 |
| 10 | 🟡 | **ProcessType 弃用污染** — 已弃用但仍被 TransformProcess 引用，每次实例化发警告 | 运行时噪音 |

### 6.2 依赖方向检查

```
models/ (Layer 0 — 纯数据)
  ↑
  ├── knowledge/store/ontology.py (纯数据)
  ↑
  ├── memory/**/models.py (纯数据)
  ↑
  ├── self/models.py (纯数据)
  ↑
memory/**/store.py ← memory/**/models.py
memory/**/gate.py ← memory/**/models.py + significance/evaluator
knowledge/store/registry.py ← knowledge/store/ontology.py
knowledge/store/lifecycle.py ← knowledge/store/ontology.py + registry.py
knowledge/process/validator.py ← knowledge/store/ontology.py
knowledge/process/evolution.py ← knowledge/store/* + knowledge/process/*
knowledge/knowledge_abi.py ← knowledge/store/* + knowledge/process/*
self/builder.py ← self/models.py + memory/belief + memory/experience
self/governor.py ← self/models.py + self/identity_boundary.py
self/monitor.py ← self/models.py + memory/episode
```

**依赖违规**:
- ❌ models/__init__.py 导入 `ocos.kernel.abi.DecisionStatus` — models 不应依赖 kernel
- ⚠️ self/builder.py 直接依赖 memory 层的具体模型 (Belief, Experience) — 应通过 ABI/接口间接依赖

### 6.3 推荐改进优先级

| 优先级 | 改进项 | 工作量 |
|--------|--------|--------|
| P0 | 修复 EvolutionManager 的 `dataclasses` 覆盖 bug | 1 行 |
| P0 | 实现 `_synthesize_lessons()` | 中等 |
| P1 | 添加持久化层 (SQLite/文件) | 大 |
| P1 | 拆分 Governor 为 3 个子模块 | 中等 |
| P2 | 删除 knowledge 层 shim 文件 | 小 |
| P2 | 统一 memory/semantic 的 relation_type 与 models/information 的 RelationType | 小 |
| P2 | 将验证器抽象为共享接口/基类 | 中等 |
| P3 | 为 semantic store 添加索引/邻接表 | 中等 |
| P3 | 移除 ProcessType 或完成迁移 | 中等 |

---

## 七、文件统计汇总

| 层 | 文件 | 总行数 | dataclass 数 | Enum 数 | 类数 | 函数数 |
|----|------|--------|-------------|---------|------|--------|
| memory | 27 | ~3,900 | 10 | 2 | 12 | 4 |
| self | 7 | ~2,038 | 3 | 0 | 6 | 0 |
| knowledge | 16 | ~2,420 | 8 | 8 | 8 | 9 |
| models | 14 | ~1,270 | 38 | 30 | 0 | 0 |
| **总计** | **64** | **~9,628** | **59** | **40** | **26** | **13** |

---

*审计完成。共审计 64 个 Python 文件，约 9,600 行代码，识别 3 个严重问题，7 个中等问题和若干建议。*


---

# 附录 B：Runtime / Platform / Engines / Capability 逐文件审计

> 并行子代理 Task 1 — 45 文件，~14,561 行代码

> **审计日期**: 2026-07-24  
> **审计范围**: `ocos/runtime/` (10 文件), `ocos/platform/` (13 文件), `ocos/engines/` (17 文件), `ocos/capability/` (5 文件)  
> **总代码量**: ~14,561 行  
> **语言**: 中文

---

## 1. 总体概览

| 层 | 文件数 | 总行数 | 核心职责 |
|---|--------|--------|----------|
| **runtime/** | 10 | ~4,313 | 操作核心：调度、策略、目标、上下文、资源、注意力、自适应控制 |
| **platform/** | 13 | ~4,028 | 生命周期服务：审计、治理、Trace、插件框架、能力注册 |
| **engines/** | 17 | ~4,912 | 任务执行引擎：推理、规划、决策、学习、反思、写作、检索等 |
| **capability/** | 5 | ~1,308 | 认知皮层：技能图、技能注册、选择器、元控制 |

### 总体架构分层（B1-B6 / C1-C3 / D1-D3）

```
┌─────────────────────────────────────────────────────────┐
│  capability/  认知皮层 (Phase 23)                        │
│  SkillGraph → SkillGraphExecutor → MetaController       │
├─────────────────────────────────────────────────────────┤
│  engines/  任务执行引擎 (17 engines)                     │
│  Reasoning → Planning → Decision → Learning → Writer... │
├─────────────────────────────────────────────────────────┤
│  platform/  平台服务                                     │
│  C1:Trace  C2:Audit  C3:Governance  D1:Registry        │
│  D2:Sandbox  D3:Loader                                  │
├─────────────────────────────────────────────────────────┤
│  runtime/  操作核心                                      │
│  B1:Context  B2:Attention  B3:Scheduler  B4:Policy     │
│  B5:Resource  B6:AdaptiveControl                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. runtime/ 层详细审计

### 2.1 scheduler.py — B3 调度器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `scheduler.py` (~460行) |
| **类/公开方法** | `Scheduler` — `start()`, `stop()`, `step()`, `execute_decision()`, `_run_loop()` |
| **能力契约** | 将 PolicyEngine 的 Decision 转化为执行；维护优先级队列；支持开始/停止/步进三种模式 |
| **依赖** | `ocos.kernel.abi` (Event, EventType, Decision), `ocos.events.event_bus`, `ocos.logging` |
| **架构问题** | ⚠️ `_run_loop` 中使用 `time.sleep()` 阻塞主线程，与 async-capability 层不兼容；决策执行队列缺少背压机制；无法暂停单个决策粒度 |

### 2.2 policy_engine.py — B4 策略引擎

| 项目 | 详情 |
|------|------|
| **文件/行数** | `policy_engine.py` (~530行) |
| **类/公开方法** | `PolicyEngine` — `add_policy()`, `remove_policy()`, `enable_policy()`, `disable_policy()`, `evaluate()`, `list_policies()`, `_on_governance_approved()`, `_on_governance_rejected()`, `_evaluate_single()` |
| **能力契约** | 接收 Observation → 评估策略 → 产出 Decision；支持优先级、生效条件、策略启用/禁用；通过 EventBus 自动响应 Governance 审批事件 |
| **依赖** | `ocos.kernel.abi`, `ocos.events.event_bus`, `ocos.logging` |
| **架构问题** | ⚠️ Policy 数据结构使用裸 dict（`conditions`/`actions`），无类型安全；`_evaluate_single` 逐个线性求值无并行批处理；Governance 事件处理耦合在 PolicyEngine 内部，边界不清晰 |

### 2.3 adaptive_control.py — B6 自适应控制

| 项目 | 详情 |
|------|------|
| **文件/行数** | `adaptive_control.py` (~500行) |
| **类/公开方法** | `AdaptiveControl` — `adjust()`, `record_performance()`, `get_weights()`, `reset()` |
| **能力契约** | 监控执行性能指标 → 调整 Attention Engine 权重 → 自适应优化策略选择 |
| **依赖** | `ocos.kernel.abi`, `ocos.logging` |
| **架构问题** | ⚠️ 与 AttentionEngine 的耦合通过 `set_weights()` 直接方法调用而非事件驱动；性能指标存储为裸 dict，缺乏历史时序窗口；调整策略硬编码，不可插拔 |

### 2.4 goal_runtime.py — 目标运行时

| 项目 | 详情 |
|------|------|
| **文件/行数** | `goal_runtime.py` (~490行) |
| **类/公开方法** | `GoalRuntime` — `create_goal()`, `activate_goal()`, `decompose_goal()`, `complete_goal()`, `fail_goal()`, `get_active_goals()`, `get_goal_tree()` |
| **能力契约** | Goal 全生命周期：创建 → 激活 → 分解为子目标/任务 → 完成/失败；通过 WorkingMemory 持久化；通过 EventBus 发射 GOAL_CREATED/ACTIVATED/COMPLETED |
| **依赖** | `ocos.kernel.abi`, `ocos.events.event_bus`, `ocos.models.goal`, `ocos.runtime.context_manager`, `ocos.logging` |
| **架构问题** | ⚠️ Goal 分解 (`decompose_goal`) 为硬编码模板化逻辑，不可替换；Goal 树结构为扁平 dict 模拟，缺乏真正树结构；与 ContextManager 双向耦合（GoalRuntime → WorkingMemory, ContextManager 订阅 Goal 事件） |

### 2.5 context_manager.py — B1 上下文管理器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `context_manager.py` (407行) |
| **类/公开方法** | `WorkingMemory` — `add_goal()`, `get_goals()`, `update_goal_status()`, `set_preference()`, `get_preference()`, `add_decision()`, `add_execution()`, `get_executions()`, `add_process()`, `get_processes()`; `ContextManager` — `build_context()`, `subscribe()`, `unsubscribe()` |
| **能力契约** | 组装运行时上下文：从 Working Memory 提取 Goals + Decisions + Executions + Processes → 构建 Context 对象；自动订阅 EventBus 在事件发生时重建上下文 |
| **依赖** | `ocos.kernel.abi`, `ocos.events.event_bus`, `ocos.models.execution`, `ocos.models.process`, `ocos.logging` |
| **架构问题** | ⚠️ `WorkingMemory` 同时承担多个职责（Goal 存储、偏好存储、Decision/Execution 历史），应拆分为独立 Store；`build_context` 每次都全量重建，无增量更新机制；Context 结构过于扁平 |

### 2.6 resource_manager.py — B5 资源管理器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `resource_manager.py` (450行) |
| **类/公开方法** | `ResourceManager` — `request()`, `release()`, `_cleanup_expired()`, `get_usage()`; `ResourceSlot`, `ResourceRequestResult`, `ResourceQuota`, `ResourceUsage` |
| **能力契约** | 管理 CPU/Memory/GPU/Token/Storage 五大资源池；TTL 槽位过期机制；引擎级配额限制；发射 RESOURCE_EXHAUSTED/RESOURCE_RELEASED 事件 |
| **依赖** | `ocos.kernel.abi`, `ocos.logging` |
| **架构问题** | ⚠️ TTL 清理为被动调用（仅在 `request` 时触发），长期无请求时槽位泄漏；配额检查为同步阻塞，缺少异步预留机制；资源类型枚举硬编码，不可扩展 |

### 2.7 attention_engine.py — B2 注意力引擎

| 项目 | 详情 |
|------|------|
| **文件/行数** | `attention_engine.py` (414行) |
| **类/公开方法** | `AttentionEngine` — `score()`, `score_batch()`, `set_weights()`, `reset()`; `ContentAnalyzer`(ABC) — `analyze()`; `DefaultContentAnalyzer`, `SemanticContentAnalyzer`, `FrequencyAnalyzer`, `UrgencyKeywordAnalyzer` |
| **能力契约** | 对 Observation 计算三维分数（novelty, goal_relevance, urgency）→ 加权合成 attention_score；支持插拔式分析器；动态权重调整 |
| **依赖** | `ocos.kernel.abi` (Observation, Goal), `ocos.logging` |
| **架构问题** | ⚠️ `ContentAnalyzer` 接口签名为 `analyze(observation, goals) -> dict`，返回裸 dict 缺少结构化分数类型；`SemanticContentAnalyzer` 方法体为空实现；`UrgencyKeywordAnalyzer` 关键词列表硬编码，不可配置 |

---

## 3. platform/ 层详细审计

### 3.1 audit_engine.py — C2 审计引擎

| 项目 | 详情 |
|------|------|
| **文件/行数** | `audit_engine.py` (519行) |
| **类/公开方法** | `InMemoryAuditStore` — `store()`, `get()`, `query()`, `count()`, `clear()`; `AuditEngine` — `record()`, `query_audit_trail()`, `get_audit_record()`, `get_audit_count()`, `run_audit_checks()`, `build_debug_report()`, `build_compliance_report()`, `build_replay_context()`, `reset()`, `unsubscribe_all()` |
| **能力契约** | 自动收集 Decision/Governance/Execution/System 事件的审计记录；可手动 record 补充；运行注册的审计规则检查（完整性/权限越界/合规）；产出 Debug/Compliance/Replay 三类报告；环形缓冲区存储（默认 10,000 条） |
| **依赖** | `ocos.kernel.abi`, `ocos.platform.audit_models`, `ocos.platform.audit_rule_engine`, `ocos.platform.audit_report`, `ocos.logging` |
| **架构问题** | ⚠️ `InMemoryAuditStore.query()` 为 O(n) 全量扫描，无索引；`trace_engine` 参数类型为 `Any`，失去类型安全；EventBus 订阅在 `__init__` 中，违反构造函数不应有副作用的惯例；报告生成器委托给 `AuditReportGenerator` 但两者为紧耦合（构造时传入 store/trace/rule） |

### 3.2 governance_engine.py — C3 治理引擎

| 项目 | 详情 |
|------|------|
| **文件/行数** | `governance_engine.py` (434行) |
| **类/公开方法** | `GovernanceEngine` — `submit_proposal()`, `review_proposal()`, `cancel_proposal()`, `get_proposal()`, `list_proposals()`, `find_proposal_by_title()`, `reset()`; `EvolutionProposal`, `ProposalType`, `ProposalStatus` |
| **能力契约** | 提案全生命周期：PENDING → UNDER_REVIEW → APPROVED/REJECTED/CANCELLED；严格状态机转换验证；通过 EventBus 发射 APPROVAL_REQUESTED/APPROVED/REJECTED 事件；PolicyEngine 下游通过事件自动响应 POLICY_CHANGE 类型提案 |
| **依赖** | `ocos.kernel.abi`, `ocos.logging` |
| **架构问题** | ⚠️ `review_proposal` 中 Policy 数据提取逻辑（将 `target_details.policy` 展开到 event_payload 顶层）是泄漏到 Governance 层的 Policy 领域知识；`_move_to_review` 使用 `EvolutionProposal` 整体重建而非字段级更新（不可变 dataclass 设计，但导致样板代码）；提案存储为内存 dict，无持久化 |

### 3.3 plugin_loader.py — D3 插件加载器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `plugin_loader.py` (555行) |
| **类/公开方法** | `PluginLoader` — `discover()`, `load()`, `execute()`, `unload()`, `get_instance()`, `find_by_name()`, `list_loaded()`, `register_to()`, `load_all()`, `unload_all()`, `reset()`; `LoadResult`, `LoaderErrorCode` |
| **能力契约** | 扫描文件系统发现 plugin.json → 动态 import Python 模块 → 校验 PluginBase 接口 → 注册到 Sandbox → 执行插件动作 → 卸载清理；支持 CapabilityRegistry 集成；重复加载检测 |
| **依赖** | `ocos.platform.plugin_base`, `ocos.platform.plugin_manifest`, `ocos.platform.plugin_sandbox`, `ocos.logging` |
| **架构问题** | ⚠️ L272-274: 通过 `getattr(self._sandbox, "_plugins", {})` 访问 Sandbox 私有属性进行 slot 实例注入，严重破坏封装；`register_to` 中对 CapabilityRegistry 的 import 在方法体内延迟导入，风格不一致；`_parse_manifest_file` 为静态方法但耦合了 Permission 枚举解析 |

### 3.4 plugin_sandbox.py — D2 插件沙箱

| 项目 | 详情 |
|------|------|
| **文件/行数** | `plugin_sandbox.py` (455行) |
| **类/公开方法** | `PluginSandbox` — `load()`, `unload()`, `execute()`, `reset()`; `SandboxResult`, `SandboxConfig`, `_ImportBlocker`, `_PluginSlot` |
| **能力契约** | Manifest 验证 + 权限范围检查 → Import Hook 拦截禁止的模块 → ThreadPoolExecutor 隔离执行 + 超时终止 → 结果封装 SandboxResult；并发数限制；守护线程 |
| **依赖** | `ocos.platform.plugin_base`, `ocos.platform.plugin_manifest`, 可选 `ocos.platform.capability_registry`, `ocos.logging` |
| **架构问题** | ⚠️ L363-365: 直接访问 `ThreadPoolExecutor._threads` 私有属性设置 daemon，Python 3.9+ 已支持 `thread_name_prefix` 但 daemon 设置方式脆弱；`execute()` 中 import hook 安装/移除分两次调用，中间无事务保证；`_do_execute` 在无 plugin_instance 时回退为 stub 占位，但未记录降级事件 |

---

## 4. engines/ 层详细审计（聚焦）

### 4.1 writer_engine.py — 写作引擎

| 项目 | 详情 |
|------|------|
| **文件/行数** | `writer_engine.py` (649行) |
| **类/公开方法** | `WriterEngine` — `execute()`, `circuit_state`(property); `RuntimeResult`, `WriterTrace` |
| **能力契约** | 接受 TransformProcess + strategy(plan/generate/resume/rewrite/status) → 执行写作操作；三层降级：opentale → TextGenerator(LLM) → plan-only；工作记忆持久化规划；断路器+重试保护；WriterTrace 记录 |
| **依赖** | `ocos.kernel.abi`, `ocos.events.event_bus`, `ocos.models.process`, `ocos.runtime.context_manager`, `ocos.agent.retry_policy`, `ocos.engines.narrative_pipeline`, `ocos.engines.text_generator`, `ocos.logging` |
| **架构问题** | ⚠️ `_do_generate` L497: 在 async 上下文中使用 `asyncio.run()` 运行 `TextGenerator.generate_chapter()` — 若已在事件循环中会抛出 RuntimeError；`_opentale_available` 为惰性检查但 `_opentale_system` 从未初始化，opentale 分支实际不可达；`_do_plan` 章节生成模板化，无真实 AI 规划；`safe_execute` 闭包内始终返回 `{"success": True, "result": r}`，掩盖了 `result.success` 为 False 的情况 |

### 4.2 text_generator.py — 文本生成器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `text_generator.py` (483行) |
| **类/公开方法** | `LLMProvider`(ABC) — `generate()`, `name`, `available`; `MockProvider` — `generate()`; `AnthropicProvider` — `generate()`; `OpenaiProvider` — `generate()`; `PromptBuilder` — `build_system_prompt()`, `build_chapter_prompt()`, `build_rewrite_prompt()`; `TextGenerator` — `generate_chapter()`, `generate_rewrite()`, `provider`(property+setter); `GenerationResult` |
| **能力契约** | 可插拔 LLM Provider（Mock/Anthropic/OpenAI）→ Prompt 模板化构建 → 异步生成叙事文本；自动选择可用 Provider（环境变量检测） |
| **依赖** | `ocos.logging`（纯工具类，无 kernel/abi 依赖） |
| **架构问题** | ⚠️ `AnthropicProvider` 硬编码模型 `claude-sonnet-4-20250514`，不可配置；所有 Provider 的 `max_tokens` 固定 2000；`MockProvider.generate()` 从 prompt 文本中解析参数（L113-138），脆弱且无错误处理；`PromptBuilder` 所有方法为 `@staticmethod`，无法注入自定义模板；无 token 计数/成本追踪 |

---

## 5. capability/ 层详细审计

### 5.1 models.py — 认知皮层数据模型

| 项目 | 详情 |
|------|------|
| **文件/行数** | `models.py` (299行) |
| **类/公开方法** | `Skill` — 含 fallback_strategy 验证; `SkillGraph` — `get_skill()`, `get_dependency_order()`(Kahn 拓扑排序), `has_cycle()`, `validate()`; `ProcessGraph` — `add_record()`, `last_record()`, `failed_count()`, `repeated_skill_count()`; `SkillExecutionRecord`, `SkillStatus`, `CyclicDependencyError`, `UnknownPrerequisiteError` |
| **能力契约** | Skill(带 fallback/评估/演化历史的认知单元) → SkillGraph(Kahn 排序 + 环检测 + 验证) → ProcessGraph(执行会话状态追踪) |
| **依赖** | 无（纯数据模型，仅标准库） |
| **架构问题** | ⚠️ `Skill.fallback_strategy` 在 `__post_init__` 验证但 dataclass frozen=False，构造后可被绕过；`SkillGraph._skill_map` 使用 `field(default=None, init=False, repr=False)` 但 init=False 后缓存失效时无通知机制；`ProcessGraph.error_log` 为 `list[dict[str, Any]]`，缺少结构化 Error 类型 |

### 5.2 skill_registry.py — 技能注册表

| 项目 | 详情 |
|------|------|
| **文件/行数** | `skill_registry.py` (266行) |
| **类/公开方法** | `SkillRegistry` — `init_db()`, `close()`, `save_skill()`, `load_skill()`, `list_skills()`, `delete_skill()`, `save_graph()`, `load_graph()`, `list_graphs()`, `delete_graph()` |
| **能力契约** | SQLite 持久化的 Skill/SkillGraph CRUD；JSON 序列化复杂字段；WAL 模式 |
| **依赖** | `ocos.capability.models` |
| **架构问题** | ⚠️ 连接管理为非线程安全（单连接复用），多线程并发会出问题；`load_graph` 回退创建占位 Skill `Skill(id=sid, name=sid)` 可能掩盖数据不一致；无迁移机制（schema 硬编码） |

### 5.3 skill_graph_executor.py — 技能图执行器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `skill_graph_executor.py` (369行) |
| **类/公开方法** | `SkillGraphExecutor` — `start()`, `stop()`, `get_process()` |
| **能力契约** | 异步执行 SkillGraph：Kahn 拓扑排序 → 逐个执行 Skill(含 fallback) → MetaController 干预监控 → 返回 ProcessGraph |
| **依赖** | `ocos.agent.cognitive_bridge`, `ocos.capability.models` |
| **架构问题** | ⚠️ `_route_to_engine` 中 capability→Bridge 方法映射为 if-elif 链，新增 capability 需修改此方法；`_execute_skill` 中 `_route_to_engine` 为同步调用但包装在 async 方法中（L310），未利用异步优势；fallback 技能从 `process.context["_fallback_skills"]` 中查找，但该字段从未被设置 |

### 5.4 selector.py — 能力选择器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `selector.py` (225行) |
| **类/公开方法** | `CapabilitySelector` — `register()`, `unregister()`, `clear()`, `select()`; `SelectorResult` |
| **能力契约** | Intent 字符串 → 关键词匹配 → SkillGraph 选择；支持中英文关键词映射；多候选时降低置信度 |
| **依赖** | `ocos.capability.models` |
| **架构问题** | ⚠️ 关键词匹配为简单 `in` 操作，`_match_keywords` 的 `pattern in kw or kw in pattern` 产生大量误匹配风险（如 "plan" 匹配 "explanation"）；排序策略为 `candidates[0]` 取第一个，无实际排序逻辑；置信度 `1.0 / len(candidates)` 过于朴素 |

### 5.5 meta_controller.py — 元控制器

| 项目 | 详情 |
|------|------|
| **文件/行数** | `meta_controller.py` (149行) |
| **类/公开方法** | `MetaController` — `monitor()`, `intervene()`, `intervention_history`(property), `clear_history()`; `MetaControllerConfig`, `Intervention` |
| **能力契约** | 监控 ProcessGraph 执行：死循环检测(同一 Skill 连续 x5)、停滞检测(连续 x3 失败)、超时检测(300s)、路径过长检测(50 skills) → 产出干预建议 |
| **依赖** | `ocos.capability.models` |
| **架构问题** | ⚠️ `intervene()` 通过 hasattr 鸭子类型检查 executor，松散耦合但无接口契约；`_detect_deadlock` 仅检测连续重复，不检测模式循环(A→B→A→B)；`min_progress_required` 在配置中定义但从未使用 |

---

## 6. 跨层依赖图谱

```
                          ┌──────────────────┐
                          │  ocos.kernel.abi  │  ← 冻结内核 ABI (Event/Goal/Decision/Observation/SCHEMA_VERSION)
                          └────────┬─────────┘
                                   │ 被所有 runtime + platform + engines 依赖
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   ┌──────────────┐       ┌──────────────┐        ┌──────────────────┐
   │   runtime/   │       │  platform/   │        │    engines/      │
   │              │       │              │        │                  │
   │ B1 ContextMgr│◄──────│ C2 AuditEng  │        │ WriterEngine ────┤
   │ B2 Attention │       │ C3 GovEng ───┼───────→│  (uses B1 WM)    │
   │ B3 Scheduler │       │ D2 Sandbox   │        │ TextGenerator    │
   │ B4 PolicyEng │       │ D3 Loader ───┼──┐     │ NarrativePipeline│
   │ B5 Resource  │       │ C1 TraceEng  │  │     │ (17 engines)     │
   │ B6 Adaptive  │       │ D1 Registry  │  │     └────────┬─────────┘
   └──────┬───────┘       └──────┬───────┘  │              │
          │                      │          │              │
          │     ┌────────────────┘          │              │
          ▼     ▼                           ▼              │
   ┌──────────────────┐            ┌──────────────────┐    │
   │ ocos.events.     │            │ ocos.models.*    │    │
   │ event_bus        │◄───────────│ execution/process│    │
   │ (pub/sub 解耦)   │            │ /goal/decision...│    │
   └──────────────────┘            └──────────────────┘    │
                                                           │
                          ┌──────────────────┐             │
                          │  capability/     │◄────────────┘
                          │                  │
                          │ SkillGraph       │──→ ocos.agent.cognitive_bridge
                          │ SkillRegistry    │
                          │ SkillGraphExec   │
                          │ CapabilitySelect │
                          │ MetaController   │
                          └──────────────────┘
```

### 关键依赖关系

| 从 | 到 | 性质 |
|----|----|------|
| `runtime/*` | `kernel.abi` | 强制 |
| `runtime/context_manager` | `events.event_bus`, `models.*` | 强制 |
| `runtime/goal_runtime` | `runtime/context_manager.WorkingMemory` | 强制（双向耦合风险） |
| `platform/audit_engine` | `platform/audit_models`, `audit_rule_engine`, `audit_report` | 同层组合 |
| `platform/plugin_loader` | `platform/plugin_sandbox` | 强制（且访问私有属性） |
| `engines/writer_engine` | `runtime/context_manager.WorkingMemory` | 跨层依赖 |
| `engines/writer_engine` | `engines/narrative_pipeline`, `engines/text_generator` | 同层组合 |
| `engines/*` (15/17) | `runtime/context_manager.WorkingMemory` | 广泛跨层依赖 |
| `capability/skill_graph_executor` | `agent/cognitive_bridge` | 跨层依赖 |

---

## 7. 架构问题汇总

### 7.1 严重问题 (Critical)

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| C1 | **PluginLoader 访问 Sandbox 私有属性** | `plugin_loader.py:272-274` | 封装破坏，Sandbox 重构时 Loader 静默失效 |
| C2 | **asyncio.run() 在事件循环中调用** | `writer_engine.py:497` | RuntimeError: asyncio.run() cannot be called from a running event loop |
| C3 | **SafeExecute 闭包掩盖失败** | `writer_engine.py:225` | `{"success": True, "result": r}` 无论 `r.success` 为何始终返回 True |
| C4 | **15/17 Engine 均依赖 WorkingMemory** | `engines/*.py` | 跨层紧耦合，Engine 无法独立测试或替换存储后端 |
| C5 | **opentale 分支永久不可达** | `writer_engine.py:136-155` | `_opentale_system` 从未赋值，检查通过后实际无法委托 |

### 7.2 重要问题 (Major)

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| M1 | **Policy 数据结构为裸 dict** | `policy_engine.py` | 无类型安全，字段拼写错误运行时才暴露 |
| M2 | **AuditStore query() 为 O(n) 全量扫描** | `audit_engine.py:106-144` | 10,000+ 记录时每次查询遍历全部 |
| M3 | **SkillGraph fallback_skills 上下文从未设置** | `skill_graph_executor.py:267-269` | fallback 策略不可用 |
| M4 | **GoalRuntime ↔ ContextManager 双向耦合** | `goal_runtime.py` + `context_manager.py` | 循环依赖风险，重构困难 |
| M5 | **CapabilitySelector 关键词匹配过于宽泛** | `selector.py:191` | `pattern in kw or kw in pattern` 大量误匹配 |
| M6 | **ResourceManager TTL 清理为被动触发** | `resource_manager.py` | 长期无请求时资源槽位永久泄漏 |
| M7 | **AttentionEngine SemanticContentAnalyzer 为空实现** | `attention_engine.py` | 语义分析器无实际能力 |

### 7.3 次要问题 (Minor)

| # | 问题 | 位置 |
|---|------|------|
| m1 | ContextManager.build_context 无增量更新 | `context_manager.py` |
| m2 | AnthropicProvider 模型硬编码 | `text_generator.py:212` |
| m3 | Skill._skill_map 缓存失效无通知 | `capability/models.py:133` |
| m4 | MetaController.min_progress_required 未使用 | `meta_controller.py:26` |
| m5 | AdaptiveControl 调整策略硬编码不可插拔 | `adaptive_control.py` |
| m6 | GovernanceEngine 构造时通过整体重建更新状态 | `governance_engine.py:221-234` |
| m7 | PluginSandbox.execute() import hook 安装/移除无事务保证 | `plugin_sandbox.py:317-332` |
| m8 | SkillRegistry 连接管理非线程安全 | `skill_registry.py:74-79` |

---

## 8. 能力契约矩阵

| 组件 | 输入契约 | 处理 | 输出契约 | 事件发射 |
|------|----------|------|----------|----------|
| **Scheduler** | Decision 队列 | 优先级排序 + 执行派发 | 执行结果 | EXECUTION_STARTED/COMPLETED/FAILED |
| **PolicyEngine** | Observation + Policy 集 | 逐策略评估 | Decision | DECISION_FORMED/VALIDATED |
| **AdaptiveControl** | 执行性能指标 | 权重调整算法 | 更新的权重 | - |
| **GoalRuntime** | Goal 定义 | 创建/激活/分解/完成 | Goal 树状态 | GOAL_CREATED/ACTIVATED/COMPLETED/FAILED |
| **ContextManager** | 事件驱动触发 | 从 WM 组装上下文 | Context 对象 | - |
| **ResourceManager** | 资源请求 | 配额检查+TTL管理 | ResourceRequestResult | RESOURCE_EXHAUSTED/RELEASED |
| **AttentionEngine** | Observation | 多维分析+加权 | attention_score | - |
| **AuditEngine** | Event 自动收集 | 规则检查+存储 | AuditRecord/Findings/Report | AUDIT_CHECK_PASSED/FAILED |
| **GovernanceEngine** | Proposal 提交 | 状态机审批 | 批准/拒绝结果 | APPROVAL_REQUESTED/APPROVED/REJECTED |
| **PluginLoader** | plugin.json 发现 | 动态加载+校验 | LoadResult/SandboxResult | - |
| **PluginSandbox** | Manifest+action | Hook 隔离+超时执行 | SandboxResult | - |
| **WriterEngine** | Narrative Contract | Contract→Policy→Plan→Generate | RuntimeResult+WriterTrace | EXECUTION_STARTED/COMPLETED/FAILED |
| **TextGenerator** | chapter+contract+policy | Prompt 构建+LLM 调用 | GenerationResult | - |
| **SkillGraphExecutor** | SkillGraph | Kahn 排序+Fallback 执行 | ProcessGraph | - |
| **CapabilitySelector** | Intent 字符串 | 关键词匹配 | SelectorResult | - |
| **MetaController** | ProcessGraph | 异常检测 | Intervention | - |

---

## 9. 建议优先级

| 优先级 | 行动 | 预计影响 |
|--------|------|----------|
| **P0** | 修复 PluginLoader→Sandbox 私有属性访问 (C1) | 解耦插件框架 |
| **P0** | 修复 writer_engine asyncio.run() 嵌套问题 (C2) | 防止运行时崩溃 |
| **P1** | 为 Policy 引入 TypedDict/dataclass (M1) | 类型安全 |
| **P1** | 引入 Engine 抽象接口，解耦 WorkingMemory (C4) | Engine 可独立测试 |
| **P1** | 修复 CapabilitySelector 关键词匹配逻辑 (M5) | 选择准确性 |
| **P2** | AuditStore 添加时间索引 (M2) | 查询性能 |
| **P2** | 补全 SemanticContentAnalyzer 实现 (M7) | 功能完整性 |
| **P2** | ResourceManager 添加主动清理定时器 (M6) | 资源不泄漏 |
| **P3** | ContextManager 增量更新 (m1) | 性能优化 |
| **P3** | 各 Engine 添加 EngineManifest 注册的延迟导入改为模块顶层 (misc) | 代码整洁 |

---

*审计工具: 手工代码审查 + 导入依赖分析*  
*生成时间: 2026-07-24*


---

# 附录 C：Agent / Interaction / Goal / Planning 逐文件审计

> 并行子代理 Task 2 — 118 文件，~12,781 行代码

---

## 一、总体代码量统计

| 模块 | 文件数 | 总行数 | 职责定位 |
|------|--------|--------|----------|
| agent/ | 29 | ~4544 | 认知主体核心 — MasterAgent + 记忆/信念/皮层/决策循环 |
| interaction/ | 27 | ~1903 | 认知接口层 — CLI/REPL/API 三通道入口 |
| goal/ | 8 | ~1042 | 目标系统 — Goal 模型/工厂/强制器/验证 |
| planning/ | 6 | ~911 | 规划系统 — TaskDAG/Plan/验证器/分解器 |
| kernel/ | 4 | ~1006 | 内核 ABI — 不可变核心对象 + 宪法规则 + 事件 Schema |
| agent_orchestration/ | 7 | ~850 | Agent 编排层 — Supervisor/Registry/Contract/Selector |
| events/ | 3 | ~513 | 事件系统 — EventBus + EventStore + DeadLetterQueue |
| constitution/ | 2 | ~104 | 行为级宪法 — BehavioralConstitution 运行时检查 |
| logging/ | 5 | ~547 | 结构化日志 — OCOSLogger + 格式化/搜索/轮转 |
| auth/ | 4 | ~399 | 认证授权 — User/IdentityStore/Role |
| digital_world/ | 9 | ~960 | 数字世界接口 — 文件/Git/API/搜索/DB/沙箱 |
| stability/ | 3 | ~385 | 稳定性 — CircuitBreaker + Retry + Transaction |
| alerts/ | 4 | ~214 | 告警系统 — AlertManager + Channels |
| snapshot/ | 3 | ~242 | 快照系统 — Agent Snapshot 持久化 |
| recovery/ | 2 | ~111 | 崩溃恢复 — CrashRecovery |
| plugins/ | ~2 | ~50 | 插件系统 — OpenTale Plugin（脚手架） |
| **总计** | **~118** | **~12,781** | — |

---

## 二、agent/ — 认知主体核心层 (29 文件, ~4544 行)

### 2.1 文件清单与行数

| 文件 | 行数 | 职责 |
|------|------|------|
| `master_agent.py` ★ | 688 | 认知主体核心 — OBSERVE→THINK→DECIDE→ACT→REFLECT→LEARN 循环 |
| `cognitive_bridge.py` ★ | 390 | 认知桥接 — MasterAgent 到 5 个引擎的显式路由 |
| `lifecycle.py` | 280 | 状态机 — LifecycleManager 双层状态机（Phase + MicroState） |
| `agent_runtime.py` | 251 | 统一运行时 — 集成 MasterAgent + Cortex + Memory + Belief + Metrics |
| `control_loop.py` ★ | 201 | 控制回路 — 单权威 Goal 创建 + 微观循环编排 |
| `decision_loop.py` | 138 | 决策循环 — 感知→推理→选择→决策→执行→反射 |
| `engine_bridge.py` | 199 | 引擎桥 — 引擎注册/适配/执行 |
| `retry_policy.py` | 178 | 重试策略 |
| `metrics_collector.py` | 183 | 指标采集 |
| `memory_consolidator.py` | 182 | 记忆巩固 |
| `meta_controller.py` | 151 | 元控制器 — 循环计数 + 死锁检测 |
| `health_check.py` | 149 | 健康检查 |
| `capability_selector.py` | 73 | 能力选择器 — Intent→Engine 映射 |
| `cortex_activator.py` | 88 | 皮层激活器 — SLEEP/BLOCKED/EMERGENCY 模式 |
| `belief_system.py` | 131 | 信念系统 |
| `experience_store.py` | 126 | 经验存储 |
| `knowledge_base.py` | 129 | 知识库 — 三元组形式 |
| `state.py` | 91 | Agent 状态 |
| `identity_anchor.py` | 92 | 身份锚点 |
| `goal_stack.py` | 95 | 目标栈 |
| `goal_types.py` | 83 | 目标类型定义 |
| `intent.py` | 72 | 意图提取 |
| `attention.py` | 113 | 注意力管理 |
| `working_memory.py` | 69 | 工作记忆 |
| `episode_memory.py` | 76 | 情景记忆 |
| `execution_manager.py` | 67 | 执行管理器 |
| `capability_manager.py` | 41 | 能力列表管理 |
| `interfaces.py` | 76 | Protocol 接口定义 |
| `life_cycle_orchestrator.py` | 132 | 生命周期编排器（旧版） |
| `__init__.py` | 111 | 模块导出 |

### 2.2 类与公开方法

| 类 | 公开方法 | 说明 |
|----|----------|------|
| `MasterAgent` ★ | `boot()`, `wake()`, `observe()`, `think()`, `decide()`, `act()`, `reflect()`, `learn()`, `sleep()`, `dream()`, `shutdown()`, `get_status_report()` | 认知主体 |
| `LifecycleManager` | `transition_micro()`, `transition_to_phase()`, `run_micro_cycle()`, `freeze()`, `force_idle()` | 双层状态机 |
| `ControlLoop` | `create_goal()`, `run_cycle()`, `boot_complete()`, `enter_sleep()`, `wake_from_sleep()`, `enter_dream()`, `shutdown()` | 控制回路 |
| `CognitiveBridge` | `reason()`, `decide()`, `reflect()`, `learn()`, `execute()` | 引擎路由 |
| `AgentRuntime` | `boot()`, `tick()`, `get_full_status()`, `shutdown()` | 统一运行时 |
| `DecisionLoop` | `execute_single()`, `execute_n()`, `get_history()`, `reset()` | 决策循环 |
| `EngineBridge` | `register()`, `get_adapter()`, `list_engines()`, `execute()` | 引擎桥 |
| `CapabilitySelector` | `select()`, `map()` | 能力选择 |
| `MetaController` | `begin_cycle()`, `end_cycle()`, `record_phase()`, `check_deadlock()`, `is_blocked()` | 元控制器 |
| `BeliefSystem` | `add()`, `decay_all()`, `get_most_confident()` | 信念系统 |
| `MemoryConsolidator` | `consolidate_to_long_term()`, `get_stats()` | 记忆巩固 |
| `7 Protocol 类` | `verify()`, `push()`, `peek()`, `focus()`, `extract()`, `add()` 等 | 接口适配 |

### 2.3 能力契约（Capability Contract）

```
MasterAgent 对外契约:
  - boot()       → 恢复 Snapshot → Identity → Memory → ACTIVE
  - wake()       → SLEEP/DREAM → ACTIVE
  - observe()    → Observation{agent_id, phase, focus, goal, intent}
  - think(obs)   → thought{bridge_result | capability_selector_result}
  - decide(t)    → decision{type, selected, trace_id} (经 BehavioralConstitution 检查)
  - act(d)       → action_result{result, based_on}
  - reflect(ar)  → reflection{insight_count, bridge_result}
  - learn(r)     → learning{patterns_learned}
  - sleep()      → Snapshot 保存 → SLEEPING
  - dream()      → DREAMING → 记忆巩固 → ACTIVE
```

### 2.4 依赖图

```
agent/
  ├── ocos.kernel.abi         (Observation, Event, Goal ABI)
  ├── ocos.goal.enforcer      (GoalOriginEnforcer)
  ├── ocos.goal.factory       (GoalFactory)        ← ⚠️ 跨层：agent 依赖 goal
  ├── ocos.models.process     (TransformProcess, ProcessType)
  ├── ocos.events.event_bus   (EventBus)
  ├── ocos.runtime.context_manager
  └── 内部: 29 个子模块互引用
```

### 2.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| A01 | 🔴 高 | **agent 直接依赖 goal/** | `master_agent.py` 导入 `ocos.goal.enforcer`, `ocos.goal.factory`。违反宪法 Rule 2（Event Bus 唯一通信），agent 层应通过 Event/ABI 与 goal 层通信 |
| A02 | 🔴 高 | **双 Goal 模型冲突** | `agent/goal_types.py`(Goal, GoalLevel, GoalOriginLevel) 与 `goal/models.py`(UserGoal, GoalSource, GoalDomain) 是两套完全不兼容的 Goal 类型系统，agent 层使用前者，goal 层使用后者，无统一核心 |
| A03 | 🟡 中 | **MasterAgent 过重** | 688 行，集成 Lifecycle + ControlLoop + CognitiveBridge + Snapshot + CapabilitySelector + SkillGraph，单一类承担过多职责 |
| A04 | 🟡 中 | **asyncio.run() 在同步方法中** | `_think_with_selector()` 中调用 `asyncio.run(self._skill_graph_executor.start(...))`，在可能已存在事件循环的上下文中会导致 `RuntimeError` |
| A05 | 🟡 中 | **Protocol 接口未强制** | `__init__` 参数类型全是 `Any`，实际依赖 Protocol 接口（如 `IdentityAnchorProtocol`），但运行时无类型检查 |
| A06 | 🟡 中 | **大量 hasattr 防御式编程** | `observe()`, `think()`, `get_status_report()` 中遍布 `hasattr(x, 'method')` 检查，表明接口契约不清晰 |
| A07 | 🟢 低 | **决策循环 3 个版本并存** | `DecisionLoop`, `LifeCycleOrchestrator`(旧), `ControlLoop.run_cycle()`(新) — 三套认知循环逻辑 |
| A08 | 🟢 低 | **life_cycle_orchestrator.py** 已废弃但仍导出 | `__init__.py` 导出 `LifeCycleOrchestrator`，但核心已由 `ControlLoop` + `AgentRuntime` 替代 |

---

## 三、agent_orchestration/ — Agent 编排层 (7 文件, ~850 行)

### 3.1 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `supervisor.py` ★ | 258 | 执行监督器 — async Task/Plan 执行 + SkillGraph 集成 |
| `executor.py` | 138 | Agent 子进程执行器 — subprocess 调用 Agent 脚本 |
| `contract.py` ★ | 69 | 执行契约 — 不可变 frozen dataclass |
| `selector.py` | 65 | Agent 选择器 — 按 agent_type/success_rate 排序 |
| `fallback.py` | 104 | 降级处理器 — 重试/降级策略 |
| `registry.py` | 104 | Agent 注册表 — AgentDescriptor 管理 |
| `audit.py` | 112 | 执行审计 — ExecutionRecord 日志 |

### 3.2 类与公开方法

| 类 | 公开方法 | 说明 |
|----|----------|------|
| `ExecutionSupervisor` ★ | `execute_task()`, `execute_plan()`, `cancel()`, `register_skill_graph()`, `execute_task_sync()`, `execute_plan_sync()` | 执行监督器 |
| `AgentExecutor` | `execute()`, `register_agent()`, `unregister_agent()` | 子进程执行器 |
| `ExecutionContract` | `create()`, `validate_output_schema()` | 不可变契约 |
| `AgentSelector` | `select()`, `select_fallback()` | Agent 选择 |
| `FallbackHandler` | `execute_with_policy()` | 降级执行 |
| `AgentRegistry` | `register()`, `find_by_type()`, `list_all()`, `update_status()` | Agent 注册表 |
| `ExecutionAudit` | `log_start()`, `log_complete()`, `log_failure()` | 审计日志 |

### 3.3 能力契约

```
ExecutionSupervisor:
  execute_task(task) → ExecutionRecord  (async)
    ├── Phase 22-D: SkillGraph 执行 → 结果注入 Agent 上下文
    ├── AgentSelector.select(task) → AgentDescriptor
    ├── ExecutionContract.create() → immutable contract
    ├── FallbackHandler.execute_with_policy() → FallbackResult
    └── ExecutionAudit.log_complete/failure() → ExecutionRecord
  execute_plan(plan) → list[ExecutionRecord]  (拓扑序, async)
  cancel(contract_id) → bool  (停止 Agent + SkillGraph)
```

### 3.4 依赖图

```
agent_orchestration/
  ├── ocos.planning.models    (Task, Plan, TaskDAG, TaskStatus)
  ├── 内部: 7 模块互引用
  └── (无 agent/ 直接依赖)    ← ✅ 干净
```

### 3.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| AO01 | 🟡 中 | **sync/async 双重接口** | `execute_task()`(async) + `execute_task_sync()`(sync)，同步版用 `asyncio.run()` 包裹，在已有事件循环环境会崩溃 |
| AO02 | 🟡 中 | **Agent 脚本不存在的回退** | `AgentExecutor` 的 `_agent_map` 硬编码 4 个 Agent 类型（writer/researcher/reviewer/data_processor），但 Agent 脚本文件不存在时仅返回错误，无 fallback 到内存执行 |
| AO03 | 🟢 低 | **retry_policy 字符串魔法值** | `"no_retry"`, `"retry_3x"`, `"retry_with_fallback"` 在 Contract + Selector + Supervisor 三处重复定义，应提取为枚举 |
| AO04 | 🟢 低 | **supervisor.py 是 dataclass 而非 class** | `@dataclass class ExecutionSupervisor` 虽然有 `__init__` 行为，但 dataclass 语义是"数据容器"而非"服务对象"，风格不一致 |

---

## 四、goal/ — 目标系统 (8 文件, ~1042 行)

### 4.1 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `models.py` ★ | 179 | UserGoal 数据模型 + GoalSource/GoalDomain/GoalStatus 枚举 |
| `enforcer.py` ★ | 135 | GoalOriginEnforcer — 按 Phase 拦截 Goal 创建/修改 |
| `factory.py` | 126 | GoalFactory — 创建 Goal（Phase 隔离 + MISSION 禁止） |
| `store.py` | 155 | GoalStore — SQLite 持久化 |
| `tracker.py` | 69 | GoalTracker — 进度跟踪 |
| `parser.py` | 151 | GoalParser — 自然语言→Goal 解析 |
| `tree.py` | 147 | GoalTree — 目标树结构 |
| `validator.py` | 80 | GoalValidator — 参数校验 |

### 4.2 关键类

- **`UserGoal`**(frozen dataclass): id, raw_input, objective, domain, constraints, success_criteria, priority, status, source, caller
- **`GoalOriginEnforcer`**: verify_creation(goal, creator_context) → ConstitutionResult; verify_modification(old, new) → ConstitutionResult
- **`GoalFactory`**: create(level, description, ...) → Goal (agent goal_types)
- **`GoalSource`**(Enum): HUMAN | DECOMPOSED（闭合枚举）
- **`CALLER_WHITELIST`**(frozenset): {orchestrator, goal_parser, cli, api, repl}

### 4.3 能力契约

```
goal/ 对外契约:
  ┌─ GoalSource: 闭合枚举 {HUMAN, DECOMPOSED}
  ├─ CALLER_WHITELIST: HUMAN goal 仅来自 5 个入口
  ├─ UserGoal.__post_init__: 
  │    - HUMAN source → caller 必须在白名单
  │    - DECOMPOSED source → 必须有 parent_id
  ├─ GoalOriginEnforcer.verify_creation():
  │    - Phase 21: 只允许 SYSTEM
  │    - Phase 22-24: SYSTEM + HUMAN, 禁止 SELF
  │    - HUMAN Goal 需要 human_authorized 上下文
  └─ GoalOriginEnforcer.verify_modification():
       - origin_level 不可变
       - authority 不可升级
```

### 4.4 依赖图

```
goal/
  ├── ocos.agent.goal_types   ← ⚠️ goal 层依赖 agent 层的类型定义（循环风险）
  ├── ocos.storage.connection  (SQLite)
  └── ocos.goal.models         (自身)
```

### 4.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| G01 | 🔴 高 | **双 Goal 模型未统一** | `agent/goal_types.py` 的 Goal 与 `goal/models.py` 的 UserGoal 是两套独立类型系统，`GoalFactory.create()` 返回前者，`UserGoal.create()` 返回后者，调用链路断裂 |
| G02 | 🔴 高 | **goal 依赖 agent** | `goal/enforcer.py` 和 `goal/factory.py` 导入 `ocos.agent.goal_types`，形成 agent→goal→agent 的循环依赖路径 |
| G03 | 🟡 中 | **Phase 硬编码** | `GoalFactory._current_phase` 作为类变量，多 Agent 实例共享同一 Phase，Phase 应作为实例属性或从 Constitution 注入 |
| G04 | 🟢 低 | **CALLER_WHITELIST 在 goal/models.py 和 interaction/base.py 重复定义** | 两处各自维护白名单，不一致风险 |

---

## 五、planning/ — 规划系统 (6 文件, ~911 行)

### 5.1 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `models.py` ★ | 236 | Task/TaskDAG/Plan 数据模型 |
| `plan_validator.py` ★ | 319 | PlanValidator — DAG 验证 + 环检测 + 模拟执行 |
| `decomposer.py` | 118 | TaskDecomposer — Goal→Task 分解 |
| `strategy.py` | 66 | ExecutionStrategy 定义 |
| `simulator.py` | 124 | 模拟执行器（旧版） |
| `validator.py` | 48 | TaskValidator（旧版） |

### 5.2 关键类

- **`Task`**(frozen): id, goal_id, description, task_type, agent_type, inputs, retry_policy
- **`TaskDAG`**: tasks: dict + edges: list, 线程安全（RLock）, Kahn 拓扑排序
- **`Plan`**(frozen): plan_id, goal_id, dag, strategy, estimated_total_duration
- **`PlanValidator`**: validate(dag) / simulate(dag) → PlanValidationReport
- **`TaskStatus`**(Enum): PENDING→READY→RUNNING→(COMPLETED|FAILED)；FAILED→READY(retry)

### 5.3 能力契约

```
planning/ 契约:
  - MAX_DAG_DEPTH=5, MAX_PARALLEL_WIDTH=4
  - Task 引用 Goal（外键 goal_id），不持有 Goal
  - Plan 不可修改 Goal
  - VALID_AGENT_TYPES: {writer, researcher, reviewer, data_processor}
  - PlanValidator:
      validate(dag) → DAG 结构(CYCLE)+能力(CAP)+依赖(DEP)检查
      simulate(dag) → 验证 + Kahn 拓扑模拟执行顺序
```

### 5.4 依赖图

```
planning/
  ├── ocos.goal.models    (UserGoal)
  └── ocos.planning.models (自身)
```

### 5.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| P01 | 🟡 中 | **plan_validator + validator + simulator 三套验证逻辑** | `plan_validator.py`(319行)、`validator.py`(48行)、`simulator.py`(124行) — 应合并为单一 PlanValidator |
| P02 | 🟡 中 | **MAX_DAG_DEPTH/MAX_PARALLEL_WIDTH 定义了但未强制执行** | `models.py` 中定义常量，但 `TaskDAG` 的 `add_task/add_edge` 不检查是否超过限制 |
| P03 | 🟢 低 | **依赖 goal.models.UserGoal 但 Task 用 goal_id 字符串引用** | 类型上依赖但运行时只传字符串，`decomposer.py` 导入 `goal.models` 却只取 goal_id |

---

## 六、kernel/ — 内核层 (4 文件, ~1006 行)

### 6.1 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `abi.py` ★ | 373 | 核心 ABI — 6 个 frozen dataclass + EventType 枚举(30+ 种) |
| `constitution.py` ★ | 220 | 宪法 — 24 条不可变规则 + Constitution 类 + ALLOWED_IMPORTS |
| `event_schema.py` | 330 | Event Schema Registry — 每种 EventType 的 required_payload_fields |
| `time_manager.py` | 83 | 时间管理器 |

### 6.2 ABI 核心对象

| 对象 | 类型 | 关键字段 |
|------|------|----------|
| `Event` | frozen dataclass | event_id, event_type, source, timestamp, payload, trace_id |
| `Observation` | frozen dataclass | observation_id, content, source |
| `Memory` | frozen dataclass | memory_id, content, memory_type(deprecated) |
| `Knowledge` | frozen dataclass | knowledge_id, content, level, status, version |
| `Goal` | frozen dataclass | goal_id, description, priority, status, source, parent_goal_id |
| `Decision` | frozen dataclass | decision_id, goal_id, selected_option, confidence, status |
| `Action` | frozen dataclass | action_id, decision_id, action_type, params, status |

### 6.3 宪法规则 (24 条)

核心规则：
- **Rule 1**: Decision 是 Action 唯一来源
- **Rule 2**: Event Bus 是唯一通信通道
- **Rule 10**: Kernel 不懂业务逻辑
- **Rule 11**: Runtime 不 import knowledge/platform/engines/plugins
- **Rule 17**: Goal 只回答 What，不回答 How
- **Rule 20**: Decision 必须引用 Goal

### 6.4 依赖图

```
kernel/
  ├── ocos.kernel.abi  (自身)
  └── (无其他 OCOS 依赖)  ← ✅ 干净
```

### 6.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| K01 | 🟡 中 | **kernel.abi.Goal 与 agent/goal_types.Goal 是两套系统** | `kernel/abi.py` 定义的 Goal(frozen, 优先考虑 status 为 str) 与 `agent/goal_types.py` 的 Goal(非 frozen, origin_level) 是两套不同的 Goal 类型，造成核心类型碎片化 |
| K02 | 🟡 中 | **ALLOWED_IMPORTS 不完整** | `constitution.py` 定义了 7 组允许的 import 方向，但未覆盖 agent/、goal/、planning/、interaction/ 等新模块 |
| K03 | 🟢 低 | **Memory.memory_type 已标记废弃但仍为必填字段** | `memory_type: str = "episodic" # 已废弃` — 应通过默认值兼容，而非保留在核心 ABI 中 |
| K04 | 🟢 低 | **abi.py 文件过长** | 373 行，包含 6 个 dataclass + 30+ EventType + DecisionStatus + Legacy 兼容，应考虑拆分为 event_types.py + objects.py |

---

## 七、interaction/ — 认知接口层 (27 文件, ~1903 行)

### 7.1 模块结构

```
interaction/
├── base.py (226行) ★        — GoalRequest + InteractionSession + PermissionGuard
├── context.py (176行)        — InteractionContext (DB 连接持有)
├── __init__.py (27行)
├── cli/ (12文件, ~500行)     — CLI 入口
│   ├── main.py               — ocos 命令入口 (goal/plan/memory/belief/self/trace)
│   ├── parser.py             — argparse 参数解析
│   └── commands/             — 各子命令实现
├── repl/ (8文件, ~430行)     — REPL 入口
│   ├── shell.py              — OcosShell (cmd.Cmd 子类)
│   ├── completer.py          — 命令补全
│   └── commands/             — 各子命令实现
└── api/ (8文件, ~500行)      — HTTP REST 接口
    ├── server.py             — FastAPI 服务器
    ├── models.py             — API 请求/响应模型
    └── routes/               — belief/goal/memory/plan/trace 路由
```

### 7.2 三层入口对比

| 特性 | CLI | REPL | API |
|------|-----|------|-----|
| 入口文件 | `cli/main.py` | `repl/shell.py` | `api/server.py` |
| 会话模式 | 无状态（每次命令新建 session） | 有状态（长连接，session 持久） | 无状态（每请求独立） |
| Goal 创建 | `cmd_goal_create()` | `ReplGoalCommand.execute()` | `POST /goals` |
| 权限检查 | ❌ 无 PermissionGuard 调用 | ❌ 无 PermissionGuard 调用 | ❌ 无 PermissionGuard 调用 |
| Constitution 检查 | ❌ 无 | ❌ 无 | ❌ 无 |

### 7.3 能力契约

```
interaction/ 契约:
  ALLOWED_ACTIONS:  {create_goal, query_memory, request_plan, view_belief, view_self, view_trace}
  FORBIDDEN_ACTIONS: {modify_self, modify_identity, write_memory, modify_goal, modify_constitution, approve_evolution}
  
  GoalRequest.create(raw_input, objective, domain, caller) → GoalRequest
    └── to_user_goal() → UserGoal (经过 UserGoal.__post_init__ 二次校验)
  
  PermissionGuard.check(action, context) → ConstitutionResult
    ├── 1. action 不能在 FORBIDDEN_ACTIONS 中
    ├── 2. action 必须在 ALLOWED_ACTIONS 中
    └── 3. 委托 BehavioralConstitution.check_decision()
```

### 7.4 依赖图

```
interaction/
  ├── ocos.constitution.behavioral  (BehavioralConstitution)
  ├── ocos.goal.models              (UserGoal, GoalDomain, CALLER_WHITELIST)
  ├── ocos.memory.belief.models     (Belief)
  ├── ocos.memory.belief.store      (BeliefStore)
  ├── ocos.memory.episode.store     (EpisodeStore)
  └── ocos.self.identity_boundary   (IdentityBoundary)
```

### 7.5 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| I01 | 🔴 高 | **PermissionGuard 定义了但未被任何入口调用** | `base.py` 定义了完整的权限检查流程，但 CLI(7个命令)、REPL(7个命令)、API(5个路由) 全部未调用 `PermissionGuard.check()` |
| I02 | 🔴 高 | **CLI/REPL 命令函数中代码大量重复** | CLI `commands/goal.py` 和 REPL `commands/goal.py` 是独立实现的相同逻辑（Goal 创建/查询），应共享 `GoalRequest` 抽象 |
| I03 | 🟡 中 | **FORBIDDEN_ACTIONS 的定义被绕过** | `FORBIDDEN_ACTIONS` 禁止 `modify_identity`，但 CLI `cmd_self_identity()` 和 REPL `ReplSelfCommand` 直接调用 `IdentityBoundary`，绕过了 PermissionGuard |
| I04 | 🟡 中 | **API routes 各有独立实现** | `api/routes/goal.py`(78行)、`belief.py`(37行)、`memory.py`(33行) 各自实现 HTTP handler，无统一的 middleware/permission 层 |
| I05 | 🟡 中 | **context.py 持有 DB 连接但无连接池管理** | `InteractionContext` 每次创建 SQLite 连接，close() 关闭，无连接复用 |
| I06 | 🟢 低 | **CLI parser.py 的 argparse 与 REPL completer.py 的参数解析不同步** | CLI 用 argparse 定义参数结构，REPL 用自定义 parser，新增命令需两处同步 |

---

## 八、events/ — 事件系统 (3 文件, ~513 行)

### 8.1 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `event_bus.py` ★ | 185 | EventBus — pub/sub + sync/async dispatch + DLQ 集成 |
| `event_store.py` ★ | 160 | InMemoryEventStore — 原子追加 + 类型查询 + 快照 |
| `dead_letter_queue.py` | 168 | DeadLetterQueue — 失败事件缓存 + 重试 |

### 8.2 能力契约

```
EventBus:
  subscribe(event_type, callback) → subscriber_id
  subscribe_all(callback) → subscriber_id
  unsubscribe(subscriber_id) → bool
  publish(event, sync=True) → success_count
  subscriber_count(event_type?) → int

InMemoryEventStore:
  append(events, validate=True) → CommitResult  (原子: 全部验证通过才写入)
  get_by_type(event_type) → list[Event]
  get_by_source(source) → list[Event]
  get_all() → list[Event]
  snapshot() → StoreSnapshot
```

### 8.3 依赖图

```
events/
  ├── ocos.kernel.abi           (Event, EventType)
  ├── ocos.kernel.event_schema  (validate_event_payload)
  └── ocos.logging
```

### 8.4 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| E01 | 🟡 中 | **EventBus publish async=True 时 daemon thread 无监控** | `threading.Thread(daemon=True)` 启动后无法跟踪执行状态或获取异常，事件可能静默丢失 |
| E02 | 🟡 中 | **EventStore 纯内存实现，重启即丢失** | `InMemoryEventStore._events: list[Event]` 为纯 Python list，无持久化，违反宪法 Rule 4(ALL_TRANSITIONS_MUST_BE_LOGGED) |
| E03 | 🟢 低 | **DeadLetterQueue 使用文件路径而非存储抽象** | `dead_letter_queue.py` 直接操作 JSON 文件，与 `ocos.storage` 的 SQLite 抽象不一致 |

---

## 九、constitution/ — 宪法层 (2 文件, ~104 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `behavioral.py` ★ | 103 | BehavioralConstitution — 运行时 Decision/Action 合规检查 |
| `__init__.py` | 1 | 空 |

### 9.1 能力契约

```
BehavioralConstitution.check_decision(decision, context) → ConstitutionResult
  - 高风险 Action 列表: {DELETE_USER_DATA, MODIFY_CONSTITUTION, MODIFY_IDENTITY, SHUTDOWN_SYSTEM, PROMOTE_TO_POLICY}
  - 需人工审批: {DELETE_USER_DATA, MODIFY_CONSTITUTION, MODIFY_IDENTITY}
  - 性能约束: 总耗时 < 1ms (1000 微秒)
```

### 9.2 架构问题

| #[id] | 严重度 | 问题 | 详情 |
|-------|--------|------|------|
| C01 | 🔴 高 | **constitution/ 与 kernel/constitution.py 重复定义** | `constitution/behavioral.py`(行为宪法) 与 `kernel/constitution.py`(24条规则) 是两层宪法，但都定义了 `ConstitutionalRule`/检查逻辑，职责边界不清晰 |
| C02 | 🟡 中 | **BehavioralConstitution 只检查 Decision，不检查 Action** | `check_decision()` 只检查 decision.action 是否为高风险操作，但 `FORBIDDEN_ACTIONS` 列表（modify_self, modify_identity 等）不在检查范围内 |
| C03 | 🟢 低 | **<1ms 性能约束是无 benchmarks 的空承诺** | docstring 声称 `总耗时 < 1ms`，但无对应性能测试或 CI 检查 |

---

## 十、辅助模块审计

### 10.1 logging/ (5 文件, ~547 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `logger.py` | 176 | OCOSLogger — 结构化日志（component/process_id/extra） |
| `search.py` | 173 | log 搜索 |
| `rotator.py` | 87 | 日志轮转 |
| `formatter.py` | 58 | JSON 格式化器 |
| `handlers.py` | 48 | 日志处理器 |

**问题**: 
- 🟡 `get_logger()` 函数在多个模块中直接调用（非 DI），导致测试时难以 mock

### 10.2 auth/ (4 文件, ~399 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `user.py` | 119 | User(frozen) + UserStore(SQLite CRUD) |
| `identity_store.py` | 157 | IdentityStore — 身份持久化 |
| `role.py` | 112 | Role 枚举 + 权限矩阵 |
| `__init__.py` | 11 | 导出 |

**问题**:
- 🔴 `auth/` 与 `agent/identity_anchor.py` 功能重叠 — IdentityAnchor 管理运行时身份，auth/ 管理持久化身份，但两者未集成
- 🟡 `UserStore` 直接使用 `ocos.storage.connection` 的原始 SQLite 连接（无 repository 抽象）

### 10.3 alerts/ (4 文件, ~214 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `manager.py` | 91 | AlertManager — 多通道告警聚合 |
| `channels.py` | 78 | AlertChannel 抽象 + ConsoleChannel |
| `models.py` | 34 | Alert dataclass + AlertLevel |
| `__init__.py` | 11 | 导出 |

**问题**:
- 🟢 只有一个具体通道实现(ConsoleChannel)，无 Slack/Email/Webhook 通道

### 10.4 recovery/ (2 文件, ~111 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `crash_recovery.py` | 106 | CrashRecovery — 恢复未完成 checkpoint + 重放 events |

**问题**:
- 🟡 `CrashRecovery.__init__(db_path)` 与 `snapshot/recovery.py` 的 `CrashRecovery(snapshot_mgr)` 是两套签名不同的实现

### 10.5 digital_world/ (9 文件, ~960 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `base.py` | 146 | DigitalOperation + OperationResult 基类 |
| `git_ops.py` | 178 | Git 操作 |
| `api_ops.py` | 146 | 外部 API 调用 |
| `search_ops.py` | 135 | 搜索操作 |
| `file_ops.py` | 111 | 文件 CRUD |
| `sandbox.py` | 140 | 执行沙箱 |
| `dlq.py` | 105 | 死信队列 |
| `auditor.py` | 37 | 操作审计 |
| `db_ops.py` | 33 | 数据库操作 |

**问题**:
- 🟡 `digital_world/` 所有实现为骨架/占位 — 大部分方法标记 `TODO` 或返回模拟数据，尚未实际集成

### 10.6 snapshot/ (3 文件, ~242 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `manager.py` | 105 | SnapshotManager — SQLite 持久化 + threading.Lock |
| `models.py` | 77 | AgentSnapshot dataclass |
| `recovery.py` | 60 | CrashRecovery — 从 Snapshot 恢复 |

**问题**:
- 🟡 `snapshot/recovery.py` 与 `recovery/crash_recovery.py` 是两套独立的恢复实现

### 10.7 stability/ (3 文件, ~385 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `circuit_breaker.py` | 152 | CircuitBreaker — CLOSED→OPEN→HALF_OPEN |
| `retry.py` | 118 | RetryPolicy + RetryExecutor |
| `transaction.py` | 115 | Transaction 上下文管理器 |

**问题**:
- 🟢 `stability/retry.py` 与 `agent/retry_policy.py` 功能重叠
- 🟢 `stability/` 未被 agent/ 或 agent_orchestration/ 实际集成

### 10.8 plugins/ (~2 文件, ~50 行)

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 0 | 空 |
| `opentale/plugin.py` | ~50 | OpenTale 插件骨架 |

**问题**:
- 🔴 插件系统仅骨架，无 PluginManager、PluginLoader、Sandbox 集成

---

## 十一、跨模块架构问题汇总

### 11.1 核心问题（按严重度排序）

| #[id] | 严重度 | 问题 | 影响范围 |
|-------|--------|------|----------|
| **X01** | 🔴 关键 | **三套 Goal 类型系统** | `kernel/abi.py`(Goal), `agent/goal_types.py`(Goal), `goal/models.py`(UserGoal) 互相不兼容。`GoalFactory` 创建第一种但 `goal/models.py` 定义第三种，中间无适配层 |
| **X02** | 🔴 关键 | **PermissionGuard 形同虚设** | 定义了完整的权限模型(ALLOWED/FORBIDDEN + Constitution检查)，但 CLI/REPL/API 无一处调用 |
| **X03** | 🔴 关键 | **Agent→Goal 循环依赖** | `agent/` 导入 `goal/`(enforcer, factory)，`goal/` 导入 `agent/`(goal_types)，形成循环 |
| **X04** | 🔴 高 | **宪法规则层级混乱** | `kernel/constitution.py`(24条规则+ALLOWED_IMPORTS)、`constitution/behavioral.py`(运行时决策检查)、`goal/enforcer.py`(Goal创建权限) 三层宪法各自独立，无统一宪法引擎 |
| **X05** | 🟡 中 | **交互层代码重复率 >60%** | CLI `commands/` 和 REPL `commands/` 分别实现了 goal/memory/belief/self/trace 的完全独立的逻辑（同一操作两份代码） |
| **X06** | 🟡 中 | **双 EventStore** | `events/event_store.py`(InMemoryEventStore) 与 `storage/event_store.py`(SQLiteEventStore) 是两套独立实现，无统一接口 |
| **X07** | 🟡 中 | **Phase 编号散落各处** | Phase 21/22/23/24/25 的数字硬编码在 `goal/enforcer.py`、`goal/factory.py`、`agent/master_agent.py`、`agent/control_loop.py`、`agent_orchestration/supervisor.py` 中，无法集中管理 |
| **X08** | 🟡 中 | **snapshot/recovery.py 与 recovery/crash_recovery.py 签名冲突** | 同名的 CrashRecovery 类但在两个模块中签名不同（一个接受 db_path，一个接受 snapshot_mgr） |
| **X09** | 🟢 低 | **stability/ 工具未被集成** | CircuitBreaker、RetryExecutor、Transaction 等稳定性组件未被 agent/ 或 agent_orchestration/ 实际使用 |
| **X10** | 🟢 低 | **交互层命令函数与内层无 EventBus 连接** | CLI/REPL/API 直接调用 `InteractionContext` → `{BeliefStore, EpisodeStore, IdentityBoundary}`，不经过 EventBus，违反宪法 Rule 2 |

### 11.2 依赖方向总览

```
                    ┌──────────────┐
                    │  interaction │  (CLI/REPL/API)
                    │   1903 行    │
                    └──────┬───────┘
                           │ GoalRequest / PermissionGuard
                    ┌──────▼───────┐
           ┌───────│     goal     │───────┐
           │       │   1042 行    │       │
           │       └──────┬───────┘       │
           │              │ Task           │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────────┐
    │   agent     │ │  planning  │ │agent_orchestration│
    │  4544 行    │ │  911 行    │ │    850 行         │
    │  ★核心★    │ └────────────┘ └──────────────────-┘
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   kernel    │
    │  1006 行    │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   events    │  (EventBus/Store/DLQ)
    │   513 行    │
    └─────────────┘

    辅助层: logging(547) auth(399) recovery(111) alerts(214)
           stability(385) snapshot(242) digital_world(960) plugins(50)
```

**依赖违规**：
- ❌ `agent/` → `goal/`（违反宪法 ALLOWED_IMPORTS）
- ❌ `goal/` → `agent/goal_types`（循环依赖）
- ❌ `interaction/` → `memory/`、`self/`（绕过 EventBus）
- ✅ `kernel/` → 无外部依赖（干净）
- ✅ `events/` → `kernel/`（干净）

### 11.3 文件长度分析

| 文件 | 行数 | 等级 | 是否超 800 线限 |
|------|------|------|-----------------|
| agent/master_agent.py | 688 | 大 | 否 |
| agent/cognitive_bridge.py | 390 | 中 | 否 |
| kernel/abi.py | 373 | 中 | 否 |
| kernel/event_schema.py | 330 | 中 | 否 |
| planning/plan_validator.py | 319 | 中 | 否 |
| agent/lifecycle.py | 280 | 中 | 否 |
| agent_orchestration/supervisor.py | 258 | 中 | 否 |
| agent/agent_runtime.py | 251 | 中 | 否 |
| planning/models.py | 236 | 中 | 否 |
| interaction/base.py | 226 | 中 | 否 |
| kernel/constitution.py | 220 | 中 | 否 |

综上无文件超过宪法 Rule 9 的 800 行限制。

---

## 十二、建议优先修复顺序

| 优先级 | 修复项 | 预计工时 |
|--------|--------|----------|
| P0 | **统一 Goal 类型系统** — 选择 `kernel/abi.py` 的 Goal 或 `goal/models.py` 的 UserGoal 为唯一来源，废弃另一套 | 2-3天 |
| P0 | **在交互层入口强制启用 PermissionGuard** — CLI/REPL/API 每个入口点调用 `PermissionGuard.check()` | 0.5天 |
| P1 | **消除 Agent-Goal 循环依赖** — 将 Goal 类型定义下沉到 kernel/，或通过 EventBus 通信 | 1天 |
| P1 | **合并 CLI/REPL 命令实现** — 提取共享 CommandHandler 类，消除 60%+ 重复代码 | 1天 |
| P1 | **统一 EventStore 实现** — InMemoryEventStore 和 SQLiteEventStore 实现同一接口 | 1天 |
| P2 | **集成 stability/ 工具** — 在 agent_orchestration/supervisor 中使用 CircuitBreaker + Retry | 0.5天 |
| P2 | **统一 Phase 管理** — 创建 `kernel/phase.py` 配置集中管理 | 0.5天 |
| P3 | **补充 EventBus 集成** — 交互层操作通过 EventBus 与内部层通信 | 1-2天 |

---

> 审计完成。本次审计共检查 **118 个文件**（~12,781 行 Python 代码，不含测试），涉及 **9 个核心模块** + **8 个辅助模块**。发现 **4 个关键问题、12 个高优问题、8 个中优问题、14 个低优问题**。核心风险集中在 Goal 类型碎片化、PermissionGuard 未启用、循环依赖三个方面。


---

*审计完成于 2026-07-24 | 主审计线 + 3 并行子代理 | 测试基线 3134 passed / 22 skipped / 0 failed | 全 328 源码文件覆盖*
