# OCOS Cognitive Sovereignty Freeze v0.1

**文档状态**：Architecture Freeze  
**冻结日期**：2026-07-25  
**适用范围**：OCOS v2.0 及后续所有版本  
**冻结范围**：系统身份、宪法条款、架构边界、核心子系统职责、开发阶段顺序  

---

## 1. 系统身份（永久冻结）

> **OCOS 是一个属于个人的认知操作系统。**
> 
> 它不是执行任务的 Agent，而是管理个人意图、记忆、决策和外部能力调用的唯一认知主体。

**更短版本**：

> **OCOS 是脑，Agent 是手。**

### 1.1 身份边界

| OCOS 是 | OCOS 不是 |
|---------|----------|
| 用户的认知主体 | 数字生命 |
| 意图的管理者 | 自主 AI |
| 能力的调度者 | Agent 框架 |
| 持续在场的系统 | 请求-响应服务器 |
| 个人数字大脑 | 企业工具链 |

### 1.2 与外部 Agent 的关系（永久冻结）

```
User
  |
  v
OCOS -- Cognitive Authority（唯一认知主体）
  |
  v
Executive Controller（前额叶）
  |
  v
Capability Nervous System（运动神经）
  |
  |-- Codex（coding）
  |-- OpenClaw（action）
  |-- OpenTale（creation）
  |-- Browser（information）
  |-- Excel（data）
  |-- Photoshop（design）
  `-- ...（任何未来接入）
```

**铁律**：所有外部实体（Agent、软件、工具、API、硬件）必须落在 **Capability Provider** 层，**绝不** 可以成为 **Cognitive Entity**。

---

## 2. 宪法条款（Constitution）

### Article I -- Identity Boundary（已冻结）
Self 层不包含 personality、goal、value、emotion、narrative、preference、authority、oracle。Self 是能力与局限的只读结构化快照。

### Article II -- Goal Source（已冻结）
Goal 的 `source` 字段为闭合枚举（HUMAN / DECOMPOSED）。Agent 不能创建 Goal，系统不能自主产生 Goal。

### Article III -- Memory Flow（已冻结）
Memory -> Belief -> Self 为单向流。Belief 只能引用 evidence_ids，不能反向写入 Memory。Self 层零 `ocos.self` 导入。

### Article IV -- Cognitive Sovereignty（本次冻结）

> **OCOS is the sole cognitive authority.**
>
> External capabilities may execute actions, provide information, and return results.
>
> External capabilities shall never:
> 1. create cognitive goals;
> 2. modify OCOS identity;
> 3. modify beliefs directly;
> 4. alter constitutional rules;
> 5. command OCOS decision processes.

**中文**：

> **外部能力只能执行、反馈、提供能力，不拥有认知权。**

#### 禁令矩阵

| 禁止行为 | 违反后果 | 架构检查点 |
|---------|---------|-----------|
| Agent 创建 Goal | 认知权篡夺 | `GoalTree.add_child` 校验 caller_id；仅 HUMAN / SYSTEM 维护任务可创建 |
| Agent 修改 Memory | 记忆污染 | `ResultUnderstandingLayer` 强制验证；Agent 输出必须经 Experience -> Episode -> Pattern -> Knowledge -> Belief 管道 |
| Agent 修改 Self | 身份篡改 | Self 层零外部导入；`IdentityBoundary` frozen |
| Agent 指挥 OCOS | 主仆颠倒 | `PermissionGateway` 拒绝反向控制指令 |
| Agent 形成价值判断 | 价值观植入 | `StatementValidator` 扫描 Agent 输出；禁止词汇过滤 |
| Agent 直接写入 Belief | 信念污染 | Belief 构造器 `__post_init__` 校验；仅内部认知管道可生成 Belief |

---

## 3. 架构蓝图（v2.0 冻结）

```
+-------------------------------------------------------------+
|                        用户 (User)                           |
+--------------------------+----------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|              Cognitive Interface（唯一意识入口）              |
|    +--------+ +--------+ +--------+ +--------+             |
|    | Voice  | |  CLI   | |  Web   | |  API   |  ...        |
|    +--------+ +--------+ +--------+ +--------+             |
|              统一输出：Stimulus -> Intent + Context           |
+--------------------------+----------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|                    OCOS Cognitive Core                       |
|                                                              |
|  +--------------+  +--------------+  +--------------+      |
|  | Memory Layer |  | Reasoning    |  | Self Layer   |      |
|  | (Experience  |  | Layer        |  | (Boundary    |      |
|  |  Episode     |  | (Planning    |  |  Governor    |      |
|  |  Pattern     |  |  Decomposer) |  |  Limitation) |      |
|  |  Knowledge   |  +--------------+  +--------------+      |
|  |  Belief)     |                                           |
|  +--------------+                                           |
|                                                              |
|  [Attention Engine] <- 意识焦点（单一）                        |
|  [Working Memory]   <- 当前上下文（5+-2 组块）                  |
+--------------------------+----------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|            Persistent Cognitive Loop（心跳层）                |
|                                                              |
|  while alive:                                                |
|    (1) Tick -> (2) Event Ingest -> (3) Attention Update            |
|    -> (4) Working Memory Sync -> (5) Goal Maintenance            |
|    -> (6) Execution Check -> (7) Planning Trigger                |
|    -> (8) Dispatch -> (9) Result Ingest -> (10) Learning             |
|                                                              |
|  冻结原则：Loop != Desire Generator                           |
|  只负责维护用户意图，不产生自主意图                           |
+-------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|              Executive Controller（前额叶）                   |
|                                                              |
|  职责：理解意图 -> 制定策略 -> 选择能力 -> 授权执行 -> 监督结果 -> 学习 |
|                                                              |
|  输入：Goal + Context                                        |
|  输出：ExecutionContract[]                                   |
|  约束：不修改 Goal，只推进；失败降级；审计全记录               |
+--------------------------+----------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|         Capability Nervous System（能力神经系统）             |
|                                                              |
|  +---------------------------------------------------------+|
|  | Capability Discovery          | 扫描并发现可用能力       ||
|  +---------------------------------------------------------+|
|  | Capability Registry           | 平面注册表               ||
|  +---------------------------------------------------------+|
|  | Capability Knowledge Graph    | 能力关系网络             ||
|  +---------------------------------------------------------+|
|  | Capability Experience Memory  | 能力历史表现             ||
|  +---------------------------------------------------------+|
|  | Capability Selection Engine   | 任务->能力组合优化决策     ||
|  +---------------------------------------------------------+|
|  | Capability Adapter            | 协议统一（MCP/Subprocess）||
|  +---------------------------------------------------------+|
|  | Permission Gateway            | 权限隔离（认知主权守卫）   ||
|  +---------------------------------------------------------+|
|  | Agent Lifecycle Manager       | 连接/认证/执行/释放       ||
|  +---------------------------------------------------------+|
|  | Result Understanding Layer    | 验证->结构化->经验->记忆     ||
|  +---------------------------------------------------------+|
|                                                              |
|  宪法约束：Capability != Authority                            |
|  外部 Agent 只能被调用，不能反向影响 OCOS                     |
+--------------------------+----------------------------------+
                           |
                           v
+-------------------------------------------------------------+
|              External Capability Ecosystem                   |
|                                                              |
|  +--------+ +--------+ +--------+ +--------+ +--------+   |
|  | Codex  | |OpenClaw| |Browser | | Excel  | |Photoshop|  |
|  |(coding)| |(action)| |(browse)| |(data)  | |(design) |  |
|  +--------+ +--------+ +--------+ +--------+ +--------+   |
|  +--------+ +--------+ +--------+ +--------+             |
|  |OpenTale| | Git    | | Search | |Custom  |  ...        |
|  |(create)| |(version)| |(info)  | |Agent   |             |
|  +--------+ +--------+ +--------+ +--------+             |
|                                                              |
|  地位：能力提供者 (Capability Provider)                       |
|  权利：被 OCOS 调用，返回结果                                |
|  禁止：拥有认知权、记忆权、目标权                            |
+-------------------------------------------------------------+
```

---

## 4. 核心子系统详细设计（冻结）

### 4.1 Cognitive Interface（唯一入口）

**原则**：所有用户交互必须通过单一入口进入认知核心。CLI、Web、Voice、Camera、Mobile、API 只是 **Input Sensor**，不是独立入口。

**数据流**：

```
Input Sensor（CLI / Voice / Web / API / Camera）
        |
        v
Input Adapter（模态转换）
        |
        v
Cognitive Interface
        |
        |-- Stimulus 识别（类型/紧急度/来源）
        |-- Intent 提取（用户想要什么）
        |-- Context 绑定（Working Memory + 相关历史 Memory）
        |-- 输出：Intent + Context
        |
        v
Cognitive Core
```

**冻结决策**：
- 新增 Input Sensor 时，**只增加 Input Adapter**，不修改 Cognitive Core
- Voice 不是"OCOS 的语音模块"，而是"Input Adapter 增加了一个感官"
- 所有输入统一为 `Stimulus` -> `Intent` 模型

### 4.2 Persistent Cognitive Loop（心跳层）

**冻结原则**：

> **Cognitive Loop != Desire Generator**

**正确职责**：
- 维护用户意图（Goal Maintenance）
- 监控外部事件（Event Ingestion）
- 调度认知资源（Attention Update）
- 恢复系统状态（State Recovery）
- 触发学习过程（Learning & Consolidation）

**禁止职责**：
- 自主产生 Goal（X）
- 自主修改 IdentityBoundary（X）
- 自主决定"我想做什么"（X）

**Tick 周期**：

```python
while alive:
    tick_start = time.monotonic()

    events = event_ingestion.collect()        # (1)
    attention.update(events)                   # (2)
    working_memory.sync(attention.focus)       # (3)
    goal_tree.maintenance()                    # (4)
    executable = goal_tree.check_execution_ready() # (5)

    for goal in executable:
        plan = planner.plan(goal)              # (6)
        contracts = executive.dispatch(plan)   # (7)
        asyncio.create_task(agent_monitor.track(contracts)) # (8)

    result_ingestion.collect_completed()       # (9)
    learning.consolidate()                     # (10)

    # 精确节拍控制
    sleep_for = max(0, TICK_INTERVAL - elapsed)
    await asyncio.sleep(sleep_for)
```

### 4.3 Executive Controller（前额叶）

**定位调整**：不是"任务调度器"，而是 **OCOS 的前额叶皮层**。

**职责链**：
1. **理解意图**：解析 Goal + Context，形成内部表征
2. **制定策略**：决定如何达成目标（是否需要分解、并行、顺序）
3. **选择能力**：查询 Capability Knowledge Graph + Experience Memory，选择最佳能力组合
4. **授权执行**：生成 ExecutionContract，经 Permission Gateway 检查
5. **监督结果**：异步监控 Agent 执行，处理超时/失败/异常
6. **学习**：将执行结果反馈给 Capability Experience Memory

**与 AgentExecutor 的区别**：

| | Executive Controller | AgentExecutor |
|--|---------------------|---------------|
| 类比 | 前额叶 | 手 |
| 职责 | 决定做什么、怎么做 | 实际执行动作 |
| 认知权 | 有 | 无 |
| 状态 | 持续存在 | 临时激活 |

### 4.4 Capability Nervous System（能力神经系统）

#### 4.4.1 子系统清单（8 个）

| # | 子系统 | 职责 | 优先级 |
|---|--------|------|--------|
| 1 | Capability Discovery | 扫描并发现可用能力 | P0 |
| 2 | Capability Registry | 平面注册表（有什么） | P0 |
| 3 | Capability Knowledge Graph | 能力关系网络（什么适合什么） | P0 |
| 4 | Capability Experience Memory | 能力历史表现（谁做得好） | P0 |
| 5 | Capability Selection Engine | 任务->能力组合优化决策 | P0 |
| 6 | Capability Adapter | 协议统一（MCP / Subprocess / HTTP） | P0 |
| 7 | Permission Gateway | 权限隔离（认知主权守卫） | P0 |
| 8 | Agent Lifecycle Manager | 连接 / 认证 / 执行 / 释放 | P0 |
| 9 | Result Understanding Layer | 验证 -> 结构化 -> 经验 -> 记忆 | P1 |

#### 4.4.2 Capability Knowledge Graph（三类节点）

```python
@dataclass(frozen=True)
class CapabilityNode:
    """能力本身"""
    capability_id: str           # "code_generation", "image_edit"
    domain: str                  # "coding", "image", "data", "communication"
    actions: tuple[str, ...]     # "generate", "edit", "analyze", "transform"
    input_types: tuple[str, ...] # "text", "image", "excel"
    output_types: tuple[str, ...]

@dataclass(frozen=True)
class ProviderNode:
    """能力提供者"""
    provider_id: str             # "codex", "photoshop_agent", "local_python"
    capabilities: tuple[str, ...] # 提供的 CapabilityNode IDs
    protocol: str                # "mcp", "subprocess", "http"
    auth_required: bool
    resource_limits: ResourceLimits

@dataclass(frozen=True)
class ExperienceNode:
    """历史经验"""
    experience_id: str
    task_type: str               # 任务分类
    capability_id: str           # 使用了什么能力
    provider_id: str             # 使用了哪个提供者
    outcome: str                 # "success", "failure", "partial"
    quality_score: float         # 输出质量 [0, 1]
    duration_ms: int             # 耗时
    user_satisfaction: float     # 用户满意度 [0, 1]
    timestamp: datetime
```

**关系**：
- `ProviderNode --provides--> CapabilityNode`
- `ExperienceNode --instance_of--> CapabilityNode`
- `ExperienceNode --provided_by--> ProviderNode`
- `CapabilityNode --requires--> CapabilityNode`（依赖关系）

#### 4.4.3 Capability Experience Memory

**作用**：让 OCOS 知道"哪个能力过去表现如何"。

**示例**：

```
Task: 制作商业计划书 PPT

Capability: document_creation
|-- Provider: PowerPoint-Agent-A
|   |-- 成功率: 62%
|   |-- 平均耗时: 35min
|   |-- 用户满意度: 0.6
|
|-- Provider: PowerPoint-Agent-B
|   |-- 成功率: 94%
|   |-- 平均耗时: 8min
|   |-- 用户满意度: 0.9
|
Selection Decision: PowerPoint-Agent-B
```

**存储位置**：`ocos/capability/experience_memory.py`，数据存入 SQLite（与 Memory 层隔离）。

**更新机制**：每次 Agent 执行完成后，Result Understanding Layer 生成 ExperienceNode，更新 Capability Experience Memory。

#### 4.4.4 Permission Gateway（认知主权守卫）

**核心规则**：

```python
class PermissionGateway:
    """
    所有 Capability 调用必须经过此网关。
    确保：Capability 可以影响外部世界，但不能反向影响 OCOS。
    """

    def validate(self, contract: ExecutionContract) -> GatewayDecision:
        # 1. 检查调用者身份（必须是 Executive Controller）
        # 2. 检查参数是否包含危险模式（路径穿越、命令注入、反向控制指令）
        # 3. 检查是否超出该 Capability 的授权范围
        # 4. 生成审计记录
        # 5. 禁止任何试图修改 OCOS 内部状态的调用
        pass
```

**禁止模式清单**（运行时检测）：
- 参数中包含 `ocos.memory`、`ocos.self`、`ocos.goal` 等内部模块引用
- 参数中包含 `create_goal`、`modify_identity`、`write_belief` 等认知操作指令
- 返回结果中包含 `StatementValidator` 的 6 类禁止词汇

---

## 5. 上下文架构（冻结）

**不是简单的"存储"，而是四层管道**：

```
+-----------------------------------------+
|         Long-Term Memory                |
|  (Experience -> Episode -> Pattern      |
|   -> Knowledge -> Belief)               |
|  存储：SQLite + 向量数据库               |
|  特性：持久、压缩、索引、可检索          |
+------------------+----------------------+
                   | Retrieval (RAG)
                   v
+-----------------------------------------+
|         Working Memory                  |
|  (当前相关上下文的缓存视图)               |
|  容量：5+-2 个组块 (Attention Engine 管理) |
|  特性：短期、高带宽、与注意力焦点绑定      |
+------------------+----------------------+
                   | Context Injection
                   v
+-----------------------------------------+
|         Current Cognitive Context       |
|  (进入推理的即时上下文)                   |
|  形式：Prompt / System Message / API 参数 |
|  特性：受 token 限制，必须压缩            |
+-----------------------------------------+
```

**关键机制**：
- **Memory Consolidation**：夜间低峰期自动压缩旧 Experience
- **Attention-Driven Retrieval**：当前注意力需要什么，就检索什么
- **Context Compression**：将 Working Memory 压缩为 LLM 可用的上下文格式

---

## 6. 开发阶段（冻结顺序）

| Phase | 名称 | 目标 | 预计时间 |
|-------|------|------|----------|
| **Phase 25** | Kernel Hardening | 现有 7 层达到生产级（真实 Digital World、并发锁、SQLite 连接池） | 1 个月 |
| **Phase 26** | Cognitive Interface | 建立唯一入口；Input Sensor -> Stimulus -> Intent 管道 | 3-4 周 |
| **Phase 26.5** | **Capability Sovereignty Freeze** | **冻结 ABI、协议、权限模型、知识图谱 Schema；签署 Architecture Freeze** | **4 周** |
| **Phase 27** | Persistent Cognitive Loop | 实现心跳层；Event Ingestion；Tick Budget；Graceful Degradation | 3-4 周 |
| **Phase 28** | Capability Nervous System | 实现 8 个子系统（Discovery -> Registry -> KG -> Experience -> Selection -> Adapter -> Gateway -> Lifecycle） | 3 个月 |
| **Phase 29** | Executive Controller | 实现前额叶；意图理解 -> 策略制定 -> 能力选择 -> 授权执行 -> 监督学习 | 1.5-2 个月 |
| **Phase 30** | Agent Ecosystem | 接入 Codex、OpenClaw、Browser、Excel 等真实 Capability Provider | 持续进行 |
| **Phase 31** | Personal Cognitive OS v1.0 | 产品级发布：本地部署、数据加密、用户配置面板 | 1-2 个月 |

**总计**：约 8-10 个月（从 Phase 25 开始计算）

### Phase 26.5 交付物（冻结前必须完成）

| # | 交付物 | 内容 | 格式 |
|---|--------|------|------|
| 1 | Capability ABI Spec | Capability 描述标准（ID、Schema、Cost、Reliability、Domain、Action、Input/Output Types） | Markdown |
| 2 | Agent Adapter ABI | 外部 Agent 接入必须实现的接口（Discover / Invoke / Health / Shutdown） | Markdown + Python Protocol |
| 3 | Permission Model | Capability 调用权限矩阵；单向控制原则；隔离级别 | Markdown |
| 4 | Discovery Protocol | MCP Server 发现、本地工具扫描、远程服务注册机制 | Markdown |
| 5 | Knowledge Graph Schema | Capability / Provider / Experience 三类节点；边类型；属性定义；查询接口 | Markdown + JSON Schema |
| 6 | Result Validation Pipeline | Agent 输出 -> Experience 的验证规则、危险内容检测、结构化提取规范 | Markdown |
| 7 | Reference Implementation | 极简 Capability Provider（如 `echo_agent`），验证 ABI 可行性 | Python |

**冻结标准**：
- 所有 ABI 变更必须经过 `SelfGovernor` 审批流程
- 参考实现必须通过 `PermissionGateway` 完整安全检查
- 文档必须包含"为什么不能"的边界说明
- 冻结后，Capability Nervous System 的 ABI 在 v2.x 生命周期内不可变更

---

## 7. 边界声明（OCOS 永不做什么）

以下行为 **永远** 不会出现在 OCOS 中：

1. **自主产生 Goal**：系统不会"感到无聊"或"想要进化"
2. **自主修改 Constitution**：IdentityBoundary、GoalSource、Cognitive Sovereignty 只能由用户或治理流程修改
3. **自主修改 Self**：SelfModel 的演化必须经过 `SelfGovernor` 7 步审批
4. **自主获取网络/系统权限**：权限由用户授予，系统不主动寻求扩展
5. **声称拥有情感/人格/意识**：`StatementValidator` 永久阻止此类表达
6. **与 Agent 平级协作**：Agent 永远是能力提供者，不是认知伙伴
7. **多入口并行处理**：所有输入必须经过 Cognitive Interface 统一序列化

---

## 8. 附录

### 8.1 术语表

| 术语 | 定义 |
|------|------|
| **Cognitive Sovereignty** | 认知主权。OCOS 是唯一认知主体，外部能力不拥有认知权。 |
| **Capability Provider** | 能力提供者。提供具体执行能力的外部实体（Agent、软件、工具、API）。 |
| **Cognitive Entity** | 认知实体。拥有目标、记忆、身份、决策能力的智能主体。OCOS 是唯一的 Cognitive Entity。 |
| **Capability Nervous System** | 能力神经系统。连接 OCOS 认知核心与外部能力生态的完整中间层。 |
| **Executive Controller** | 执行控制器。OCOS 的前额叶，负责意图理解、策略制定、能力选择、执行监督。 |
| **Persistent Cognitive Loop** | 持续认知循环。OCOS 的心跳层，维持系统生命体征。 |
| **Cognitive Interface** | 认知接口。用户与 OCOS 的唯一交互入口，统一所有输入模态。 |
| **Input Sensor** | 输入传感器。CLI、Voice、Web、API 等具体输入方式，属于 Cognitive Interface 的下层。 |
| **Capability Knowledge Graph** | 能力知识图谱。描述能力、提供者、历史经验之间关系的图结构。 |
| **Capability Experience Memory** | 能力经验记忆。记录每个能力提供者的历史表现数据。 |

### 8.2 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-07-25 | 初始冻结。确立系统身份、Article IV Cognitive Sovereignty、Capability Nervous System 8 子系统、Phase 26.5 Architecture Freeze。 |
| v0.2 | 2026-07-25 | 增量嵌入路线通过。新增 §9 实施路线，Freeze Phase 25→31 映射为 OCOS Phase 22→28，方案 B 增量嵌入。 |
| v0.3 | 2026-07-25 | §9 合并优化：整合"认知循环真实化"与"生产就绪 + 主权守卫"双线，Phase 22-24 重排。 |

---

**签署**：

> 本文档冻结后，OCOS 的系统身份、宪法条款、架构边界、核心子系统职责、开发阶段顺序在 v2.x 生命周期内不可变更。
> 
> 任何变更必须发起 Architecture Amendment Proposal，经 `SelfGovernor` 审批流程通过后方可实施。

---

## 9. 实施路线 v2（合并优化版 — 方案 B）

> **策略**：双线并行——A 线"认知循环真实化"（act/learn/dream + Tick 循环）打通底层，
> B 线"主权守卫 + 生产就绪"（PermissionGateway 桥接 + SQLite/并发修复）夯实骨架。
> 两线在 Phase 22-23 交替推进，Phase 24 合龙。
> 零推倒重构，零破坏现有 7 层骨架。

### 9.1 概念映射速查

| Freeze 概念 | OCOS 对等物 | 当前状态 |
|-----------|-----------|---------|
| Cognitive Interface | `interaction/api/` + `interaction/cli/` | 有，待统一 |
| Persistent Cognitive Loop | `AgentRuntime.tick()` + `DecisionLoop` | 有单步循环，Phase 22 扩展 10 步 |
| Executive Controller | `MetaController` | Phase 22 改名前额叶 |
| Capability Discovery | `EngineLoader` | ✅ Phase 21 |
| Capability Registry | `ENGINE_REGISTRY` + `_engine_types` | ✅ 已有 |
| Capability Adapter | `EngineAdapter` | ✅ 已有 |
| Capability Knowledge Graph | — | Phase 25 |
| Capability Experience Memory | — | Phase 25 |
| Selection Engine | `CapabilitySelector` | Phase 25 |
| Permission Gateway | `PermissionGuard` | Phase 22 MVP / Phase 24 完整版 |
| Agent Lifecycle Manager | — | Phase 24 |
| Result Understanding Layer | `ExperienceBuilder` | Phase 26 |
| Statement Validator | — | Phase 24 |
| Memory Consolidation | `MemoryConsolidator` | Phase 24 |

### 9.2 总体架构

```
Phase 22 ─┐ A线: act/learn 真实化 → Tick 循环 → ExecutiveController
          │ B线: Bridge + PermissionGateway MVP → search_ops/sandbox_ops 真实化
          └────────────────────────────────────────────────────────────────

Phase 23 ─┐ A线: Capability 3/9 定型 (Discovery + Registry + Adapter)
          │ B线: SQLite 泄漏修复 → 并发锁补全 → 代码质量清理
          └────────────────────────────────────────────────────────────────

Phase 24 ─ 合龙: PermissionGateway 完整版 + StatementValidator
           + AgentLifecycle + MemoryConsolidation + Goal 自主维护
           + Memory→Belief→Self 单向流加固
```

---

### 9.3 Phase 22: 结构就绪与主权守卫 (Structural & Sovereignty Readiness)

> **覆盖 Freeze**: §4.2 Persistent Cognitive Loop, §4.3 Executive Controller, §2 Art.IV (MVP)
> **目标**：解除 L5 硬阻塞——act/learn 不再 stub、Bridge 打通真实 Capability 调用、PermissionGateway 建立安全基线
> **基线**: 3134 passed / 22 skipped / 0 failed

#### 22-A: act/learn/dream 真实化（A 线 · 最高优先级）

> **为什么先做**：act/learn 是认知循环最底层——不先让它们真跑起来，后面 Bridge 桥接到哪里？无上游消费方。

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 22a1 | `act()` 接入真实引擎 | `ocos/agent/master_agent.py` | 替换 stub: Goal → EngineBridge.execute() → 返回结果 |
| 22a2 | `learn()` 接入 LearningEngine | `ocos/agent/master_agent.py` | 替换 stub: 经验 → ExperienceBuilder → 存入 EpisodeStore |
| 22a3 | `dream()` 强化 | `ocos/agent/master_agent.py` | 已有 `_synthesize_lessons`，本次不做行为变更仅加固测试 |
| 22a4 | act/learn 单元测试 | `tests/test_agent/test_master_agent.py` | 覆盖非 stub 路径：真实引擎调用、经验写入 |

#### 22-B: Capability Bridge + PermissionGateway MVP（B 线 · 最高优先级）

> **为什么第二**：act/learn 打通后立即接 Bridge + Gateway。MVP 标准：成功执行一次合法调用 + 成功拦截一次包含 `ocos.memory` 的非法调用 = 完成。
> Gateway 完整版（ABI/协议/文档）推迟到 Phase 27 冻结。

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 22b1 | `AsyncBridge` 后台 Event Loop | `ocos/capability/async_bridge.py` | 异步→同步桥接，接管 Capability 线程生命周期 |
| 22b2 | `PermissionGateway` MVP | `ocos/capability/permission_gateway.py` | `validate(contract) → GatewayDecision`；拦截参数中 `ocos.*` 引用和危险指令 |
| 22b3 | `GatewayDecision` 枚举 | 同上 | ALLOWED / BLOCKED / RESTRICTED |
| 22b4 | Bridge 集成 Gateway | 同上 | `executive.dispatch()` 后第一件事：`validate(contract)`；BLOCKED 时抛 `PermissionDeniedError` |
| 22b5 | 拦截测试 | `tests/test_capability/test_permission_gateway.py` | 合法调用通过 + 含 `ocos.memory` 调用被拦截 + 含 `create_goal` 调用被拦截 |

#### 22-C: Persistent Cognitive Loop 10 步 Tick（A 线）

> **前置依赖**：22-A 完成（act/learn 真实化后才可做完整 Tick）

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 22c1 | Event Ingestion 层 | `ocos/events/event_ingestion.py` | Tick Step 1 |
| 22c2 | Attention Update → WM Sync | `ocos/agent/agent_runtime.py` | Tick Steps 2-3 |
| 22c3 | Goal Maintenance 定时检查 | `ocos/agent/agent_runtime.py` | Tick Step 4 |
| 22c4 | Execution Check + Planning Trigger | `ocos/agent/agent_runtime.py` | Tick Steps 5-7 |
| 22c5 | Dispatch + Result Ingest (经 Bridge+Gateway) | `ocos/agent/agent_runtime.py` | Tick Steps 8-9 |
| 22c6 | Learning Consolidation (复用 Phase 21) | `ocos/agent/agent_runtime.py` | Tick Step 10 |
| 22c7 | Tick Budget 控制 + Graceful Degradation | `ocos/agent/agent_runtime.py` | §4.2 节拍控制 |
| 22c8 | 10 步 Tick 集成测试 | `tests/test_agent/test_runtime_loop.py` | 覆盖完整 Tick 周期 |

#### 22-D: Executive Controller 改造（A 线）

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 22d1 | `MetaController` → `ExecutiveController` 重命名 | `ocos/agent/executive_controller.py` | §4.3 |
| 22d2 | 意图理解 → 策略制定 → 能力选择 三阶段 | `ocos/agent/executive_controller.py` | §4.3 职责链 |
| 22d3 | `ExecutionContract` dataclass | `ocos/agent/executive_contract.py` | §4.3 输出 |
| 22d4 | 所有 `MetaController` 引用更新 | `agent_runtime.py` `decision_loop.py` 等 | 零行为变更 |
| 22d5 | ExecutiveController 单元测试 | `tests/test_agent/test_executive_controller.py` | 覆盖 6 步职责链 |

#### 22-E: search_ops + sandbox_ops 真实化（B 线）

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 22e1 | search_ops 真实化 | `ocos/operations/search_ops.py` | 真实搜索 URL 纳入 `API_WHITELIST` |
| 22e2 | sandbox_ops 真实化 | `ocos/operations/sandbox_ops.py` | `BLOCKED_COMMANDS` 生效 |
| 22e3 | ops 测试 | `tests/test_operations/` | 覆盖真实调用路径 |

#### 22-F: Cognitive Interface 统一入口（低优先级 · A 线尾巴）

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 22f1 | `CognitiveInterface` + `InputAdapter` 基类 | `ocos/interaction/cognitive_interface.py` | §4.1 |
| 22f2 | `Stimulus → Intent + Context` 模型 | `ocos/interaction/stimulus.py` | §4.1 |
| 22f3 | CLI/API 挂接 InputAdapter | `ocos/interaction/` | 不改行为 |

#### 22-ENG: 工程化收尾

| # | 检查项 |
|---|-------|
| 22e1 | 全量 pytest: 3134+ 基线 |
| 22e2 | 新增 Gate: PermissionGateway 拦截覆盖率检查 |
| 22e3 | 更新 `test_import_rules.py`（新增 bridge/gateway/contract 跨包导入） |
| 22e4 | 审计文档补齐 Phase 22 行 |

---

### 9.4 Phase 23: 生产就绪 + Capability 3/9 (Production Readiness & Capability Core)

> **覆盖 Freeze**: §4.4 #1/2/6 + 审计报告 SQLite 泄漏/并发锁
> **目标**：SQLite 零泄漏、并发安全、Capability Discovery/Registry/Adapter 文件定型
> **基线**: 3134 passed / 22 skipped / 0 failed

#### 23-A: Capability 子系统 3/9（A 线）

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 23a1 | `CapabilityDescriptor` ABI | `ocos/capability/descriptor.py` | §4.4.2 CapabilityNode |
| 23a2 | `ProviderDescriptor` ABI | `ocos/capability/provider.py` | §4.4.2 ProviderNode |
| 23a3 | `CapabilityRegistry` 平面注册表 | `ocos/capability/registry.py` | §4.4 #2 |
| 23a4 | `CapabilityDiscovery` 扫描机制 | `ocos/capability/discovery.py` | §4.4 #1，扩展现有 EngineLoader |
| 23a5 | `CapabilityAdapter` 协议统一 | `ocos/capability/adapter.py` | §4.4 #6，扩展现有 EngineAdapter |
| 23a6 | ENGINE_REGISTRY 迁移到 CapabilityRegistry | `ocos/agent/engine_bridge.py` | 零破坏：保留 deprecated alias |
| 23a7 | Capability 集成测试 | `tests/test_capability/` | 覆盖发现、注册、适配全链路 |

#### 23-B: SQLite 连接泄漏修复（B 线）

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 23b1 | storage 层连接泄漏 | `ocos/storage/` | Context Manager 修复；老接口保留 deprecated alias |
| 23b2 | auth 层连接泄漏 | `ocos/auth/` | 同上 |
| 23b3 | 长时间运行 FD 泄漏检测测试 | `tests/test_stability/` | — |

#### 23-C: 并发锁机制补全（B 线）

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 23c1 | GoalTree RLock | `ocos/goal/goal_tree.py` | `threading.RLock` 包裹读写 |
| 23c2 | TaskDAG RLock | `ocos/task/dag.py` | 同上 |
| 23c3 | AgentRegistry RLock | `ocos/capability/registry.py` | 同上 |
| 23c4 | 竞态条件复现与回归测试 | `tests/test_concurrency/` | — |

#### 23-D: 代码质量清理

| # | 任务 | 内容 |
|---|------|------|
| 23d1 | TODO/FIXME 清理 | 逐一审查，修复或转 issue |
| 23d2 | `agent_type` 定义统一 | 消除重复定义，单一来源 |
| 23d3 | PlanValidator/Simulator 接口合并 | 如审计报告指出重叠 >50% 则合并 |

#### 23-ENG: 工程化收尾

| # | 检查项 |
|---|-------|
| 23e1 | 全量 pytest: 3134+ 基线 |
| 23e2 | 新增 Gate: FD 泄漏 + RLock 覆盖检查 |
| 23e3 | 新增 Gate: import rules 无循环依赖 |
| 23e4 | 审计文档补齐 Phase 23 行 |

---

### 9.5 Phase 24: 认知主权 + 基础设施闭环 (Cognitive Sovereignty & Infrastructure)

> **覆盖 Freeze**: §2 Art.IV 完整版, §4.4 #7/8, §5 四层上下文
> **目标**：PermissionGateway 完整版 + StatementValidator + AgentLifecycle + MemoryConsolidation 管道 + Goal 自主维护
> **基线**: 3134 passed / 22 skipped / 0 failed

#### 24-A: PermissionGateway 完整版

> Phase 22 的 Gateway MVP 仅做基础拦截。Phase 24 扩展为完整版。

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 24a1 | caller_id 校验 + issuer 追溯 | `ocos/capability/permission_gateway.py` | §2 禁令矩阵 L1 |
| 24a2 | 反向控制指令检测（"指挥 OCOS" 模式) | 同上 | §2 禁令矩阵 L4 |
| 24a3 | 路径穿越/命令注入/SSRF 检测 | 同上 | §4.4.4 禁止模式清单 |
| 24a4 | 完整审计日志 | 同上 | 每次 validate 调用写入 audit trail |
| 24a5 | Gateway 集成到 AgentRuntime | `ocos/agent/agent_runtime.py` | 所有 dispatch 必过 Gateway |

#### 24-B: StatementValidator + 单向流加固

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 24b1 | `StatementValidator` 类 | `ocos/constitution/statement_validator.py` | §2 禁令矩阵 L5 |
| 24b2 | 6 类禁止词汇/模式检测 | 同上 | 情感/人格/意识声称 + 价值判断 |
| 24b3 | Agent 输出管道接入 | `ocos/capability/result_understanding.py` | Capability 返回结果强制扫描 |
| 24b4 | Belief `__post_init__` 校验 | `ocos/memory/belief/` | §2 禁令矩阵 L6 |
| 24b5 | Self 层零外部导入验证 | `ocos/tests/test_import_rules.py` | §2 Art.III |
| 24b6 | 集成测试 | `tests/test_constitution/` | 禁令矩阵全覆盖 |

#### 24-C: Agent Lifecycle Manager

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 24c1 | `AgentLifecycleManager` 类 | `ocos/capability/lifecycle_manager.py` | §4.4 #8 |
| 24c2 | 连接 → 认证 → 执行 → 释放 四阶段 | 同上 | — |
| 24c3 | Agent 休眠/销毁/超时回收 | 同上 | — |
| 24c4 | 集成到 Bridge | `ocos/capability/async_bridge.py` | Bridge 委托 Lifecycle 管理 Agent 生命周期 |

#### 24-D: Memory Consolidation 四层管道

> **严格遵循 Freeze §5**：Long-Term → Working → Current Cognitive Context

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 24d1 | Memory Consolidation 定时调度 | `ocos/agent/memory_consolidator.py` | 夜间低峰期自动压缩旧 Experience |
| 24d2 | Attention-Driven Retrieval | `ocos/attention/retrieval.py` | 注意力焦点→检索 Long-Term Memory |
| 24d3 | Context Compression | `ocos/agent/context_compressor.py` | Working Memory → LLM token 预算内格式 |
| 24d4 | 四层管道集成测试 | `tests/test_memory/test_consolidation_pipeline.py` | 压缩率检测 + Token 预算不超 |

#### 24-E: Goal lifecycle 初步自主运行

| # | 任务 | 文件 | 内容 |
|---|------|------|------|
| 24e1 | `goal_tree.maintenance()` 自主清理 | `ocos/goal/goal_tree.py` | 自动清理已完成/过期 Goal |
| 24e2 | Goal 状态机完整性 | 同上 | CREATED→ACTIVE→COMPLETED/ABANDONED 全路径 |

#### 24-ENG: 工程化收尾

| # | 检查项 |
|---|-------|
| 24e1 | 全量 pytest: 3134+ 基线 |
| 24e2 | 新增 Gate: 上下文 Token 压缩率检查 |
| 24e3 | 新增 Gate: 禁令矩阵 6 行全覆盖 |
| 24e4 | 审计文档补齐 Phase 24 行 |

---

### 9.6 Phase 25: Capability Knowledge Graph + Experience Memory

> **覆盖 Freeze**: §4.4 #3/4/5
> **基线**: 3134 passed / 22 skipped / 0 failed

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 25a1 | CapabilityNode / ProviderNode / ExperienceNode dataclass | `ocos/capability/knowledge_graph.py` | §4.4.2 |
| 25a2 | 三类边类型 + 查询接口 | 同上 | `query_by_task_type()` / `rank_providers()` |
| 25a3 | CapabilityExperienceMemory (SQLite) | `ocos/capability/experience_memory.py` | §4.4.3 |
| 25a4 | SelectionEngine 接入 KG + Experience | `ocos/capability/selection_engine.py` | §4.4 #5 |
| 25a5 | 集成测试 | `tests/test_capability/test_knowledge_graph.py` | — |

---

### 9.7 Phase 26: Result Understanding Layer

> **覆盖 Freeze**: §4.4 #9
> **基线**: 3134 passed / 22 skipped / 0 failed

| # | 任务 | 文件 | Freeze 对应 |
|---|------|------|------------|
| 26a1 | ResultUnderstandingLayer | `ocos/capability/result_understanding.py` | §4.4 #9 |
| 26a2 | 验证 → 结构化 → Experience → Memory 管道 | 同上 | §4.4.3 更新机制 |
| 26a3 | 接入 Dispatch→Result→Learn 路径 | `ocos/agent/agent_runtime.py` | Tick Steps 8→9→10 |
| 26a4 | 集成测试 | `tests/test_capability/test_result_understanding.py` | — |

---

### 9.8 Phase 27: Capability Sovereignty Freeze

> **覆盖 Freeze**: §6 Phase 26.5 全部 7 份交付物
> **目标**：ABI/协议/安全模型正式冻结文档化
> **基线**: 3134 passed / 22 skipped / 0 failed

| # | 交付物 | Freeze 对应 |
|---|--------|------------|
| 27a1 | Capability ABI Spec (Markdown) | 交付物 #1 |
| 27a2 | Agent Adapter ABI (Markdown + Python Protocol) | 交付物 #2 |
| 27a3 | Permission Model 文档 | 交付物 #3 |
| 27a4 | Discovery Protocol 文档 | 交付物 #4 |
| 27a5 | Knowledge Graph Schema (Markdown + JSON Schema) | 交付物 #5 |
| 27a6 | Result Validation Pipeline 文档 | 交付物 #6 |
| 27a7 | `echo_agent` 参考实现 | 交付物 #7 |
| 27a8 | PermissionGateway 全量安全检查验证 | 冻结标准 |
| 27a9 | Architecture Freeze 正式签署 | — |

---

### 9.9 Phase 28: Agent Ecosystem 接入

> **覆盖 Freeze**: §6 Phase 30
> **基线**: 3134 passed / 22 skipped / 0 failed

| # | Provider | 内容 |
|---|----------|------|
| 28a1 | Codex | 编码能力接入 |
| 28a2 | OpenClaw | 动作能力接入 |
| 28a3 | Browser | 浏览能力接入 |
| 28a4 | Excel | 数据能力接入 |
| 28a5 | Custom Agent 模板 | 用户自定义 Agent 接入规范 |

---

### 9.10 Phase 29: Personal Cognitive OS v1.0

> **覆盖 Freeze**: §6 Phase 31
> **基线**: 3134 passed / 22 skipped / 0 failed

| # | 任务 |
|---|------|
| 29a1 | 产品级本地部署方案 |
| 29a2 | 用户数据加密 |
| 29a3 | 用户配置面板 |
| 29a4 | 端到端集成测试 |
| 29a5 | v1.0 发布 |

---

### 9.11 执行原则（每个 Phase 通用）

1. **DoD (完成定义)**：子任务完成 → 立即跑全量 pytest，3134 基线不退化才算完成
2. **Gate 检查**：每个 Phase 结束至少新增 1 个 Gate script（如 Gateway 拦截覆盖率、FD 泄漏检测、Token 压缩率）
3. **Import rules**：每新增跨包导入 → 同步更新 `test_import_rules.py`
4. **审计文档**：每个 Phase 完成后更新 `OCOS_COMPREHENSIVE_AUDIT.md` 对应行
5. **零推倒重构**：新模块放 `ocos/capability/` 新区；老模块保留为 deprecated alias，旧 import 路径继续可用
6. **Freeze §1-7 为不变约束**：Phase 执行中任何偏离必须先起草 Amendment Proposal 修改本文档
7. **Phase 22-B 的 PermissionGateway MVP** 不追求完整 ABI——Phase 27 才冻结文档。MVP 标准：合法调用通过 + 非法调用拦截 = 完成
8. **按时序依赖执行**：22-A → 22-B/C；22-B 完成后可并行 22-C/D/E；Phase 23 A/B/C 可并行
