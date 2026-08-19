# OCOS Runtime ABI（运行时抽象接口）

> **v1.0 — 2026-07-26 — Phase 38 Gate 修补**  
> **层级：Layer 2.5 — 介于理论与实现之间**  
> **地位：Runtime ABI 定义 OCOS 持续运行所需的数据结构、事件格式、检查点和恢复协议。Phase 38A 实现前必须冻结。**

---

## 核心概念

Runtime 是 OCOS 的"心跳"。它不是功能模块，而是**调度框架**。

```
           ┌─────────────────────────┐
           │     Runtime Loop        │
           │   (while alive: tick)   │
           └───────────┬─────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    Tick N-1      Tick N        Tick N+1
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │Perceive │   │Perceive │   │Perceive │
    │Evaluate │   │Evaluate │   │Evaluate │
    │Maintain │   │Maintain │   │Maintain │
    │Decide   │   │Decide   │   │Decide   │
    │Act      │   │Act      │   │Act      │
    │Learn    │   │Learn    │   │Learn    │
    └─────────┘   └─────────┘   └─────────┘
```

**Runtime 的职责**：调度 Tick、维护检查点、检测异常、恢复状态。
**Runtime 不负责**：创建 Goal、执行 Action、修改 Identity。

---

## Tick ABI

### RuntimeTick

```python
@dataclass(frozen=True)
class RuntimeTick:
    """一次运行时心跳。"""

    tick_id: str                    # UUID7，单调递增
    tick_number: int                # 自 BOOT 以来的序号
    timestamp: datetime             # Tick 开始时间（UTC）

    # 状态快照
    runtime_state: RuntimeState     # BOOTING | RUNNING | SLEEPING | SAFE_MODE | SHUTTING_DOWN

    # 感知输入
    events: list[EventRef]          # 本 Tick 新到达的事件引用
    attention_snapshot: AttentionSnapshot  # 当前注意力状态
    goal_snapshot: GoalSnapshot     # 当前 Goal 栈状态

    # 决策输出
    decisions: list[DecisionRef]    # 本 Tick 做出的决策
    actions: list[ExecutionIntent]  # 本 Tick 产生的执行意图

    # 追踪
    checkpoint_id: str              # 指向本 Tick 对应的 Checkpoint
    previous_tick_id: str           # 上一个 Tick
    elapsed_ms: float               # 距上一个 Tick 的间隔（毫秒）
```

### Tick 生命周期

```
BOOT → Tick 0 (初始状态检查)
     → Tick 1..N (持续运行)
     → SLEEP (低活跃)
     → Tick N+1..M (唤醒)
     → SHUTDOWN
```

### Tick 内部阶段

```
每个 Tick 内:
  1. PERCEIVE  — 收集事件、更新 Attention Snapshot
  2. EVALUATE  — 检查 Goal 状态、Homeostasis 指标
  3. MAINTAIN  — 执行 MAINTENANCE Goal（如果有）
  4. DECIDE    — 评估是否需要新决策
  5. ACT       — 执行已批准的 Decision
  6. LEARN     — 处理 ExecutionResult → Feedback (Phase 37)
  7. CHECKPOINT — 保存状态快照
```

**约束**：
- 每个阶段必须完成才能进入下一阶段
- 阶段不能跳过（即使无操作也要执行空阶段）
- 阶段超时 → 进入降级 Tick

---

## RuntimeState 枚举

```python
class RuntimeState(Enum):
    BOOTING       = "booting"        # 启动中（加载 Identity + Memory）
    RUNNING       = "running"        # 正常运行
    SLEEPING      = "sleeping"       # 低功耗模式（无用户交互）
    DREAMING      = "dreaming"       # 记忆巩固模式（SLEEP 期间）
    SAFE_MODE     = "safe_mode"      # 异常保护模式（暂停决策/执行）
    SHUTTING_DOWN = "shutting_down"  # 关闭中
    CRASHED       = "crashed"        # 非正常终止（仅用于恢复日志）
```

### 状态转换

```
BOOTING → RUNNING                   (启动成功)
RUNNING → SLEEPING                  (无交互超时)
SLEEPING → DREAMING                 (周期性巩固触发)
DREAMING → SLEEPING                 (巩固完成)
SLEEPING → RUNNING                  (用户唤醒 / 事件触发)
RUNNING → SAFE_MODE                 (Identity Boundary Violation / 系统异常)
SAFE_MODE → RUNNING                 (用户确认恢复)
RUNNING → SHUTTING_DOWN             (用户命令 / 系统信号)
SHUTTING_DOWN → (进程终止)
任意状态 → CRASHED                  (未捕获异常，仅记录)

禁止:
  SAFE_MODE → (SHUTTING_DOWN 以外的任何状态，除用户显式确认)
  CRASHED → (直接从 CRASHED 恢复，必须经过 BOOTING)
```

---

## Checkpoint ABI

### Checkpoint

检查点不保存所有状态。只保存**认知连续性所需的最小集合**。

```python
@dataclass(frozen=True)
class Checkpoint:
    """认知连续性检查点。"""

    checkpoint_id: str              # UUID7
    tick_id: str                    # 指向对应的 RuntimeTick
    timestamp: datetime

    # 身份连续性
    identity_hash: str              # Identity.anchor 的 SHA256
    constitution_hash: str          # 宪法的 SHA256

    # Goal 连续性
    active_goals: list[GoalRef]     # 当前活跃 Goal 的引用（非完整内容）
    goal_stack_depth: int           # Goal 栈深度

    # 注意连续性
    attention_focus: FocusRef       # 当前注意力焦点

    # 记忆连续性
    working_memory_refs: list[str]  # Working Memory 中的关键条目 ID
    episode_cursor: str             # 最新的 Episode ID
    memory_version: int             # Memory 层版本号

    # 信念连续性
    belief_version: int             # Belief 层版本号
    active_belief_count: int

    # Runtime 元数据
    runtime_version: str            # OCOS 版本
    tick_count: int                 # BOOT 以来的总 Tick 数
    uptime_seconds: float           # 运行时间

    # 健康状态
    health_summary: dict[str, Any]  # Homeostasis 摘要
```

### 保存策略

```
微检查点（每 N 个 Tick）：    仅内存，不持久化（N=10~100）
轻检查点（每 M 分钟）：       持久化到磁盘（M=5~30）
完整检查点（每次 SLEEP 前）：  完整快照 + 验证
```

### 恢复优先级

```
恢复时加载顺序:
  1. identity_hash      → 验证"还是同一个我"
  2. constitution_hash  → 验证宪法未变
  3. active_goals       → 知道"我在做什么"
  4. working_memory_refs → 恢复上下文
  5. attention_focus    → 恢复注意焦点
  6. belief_version     → 验证信念一致性

加载失败的处理:
  identity_hash 验证失败 → 身份危机 → 进入 SAFE MODE
  constitution_hash 失败 → 宪法被篡改 → 进入 SAFE MODE
  active_goals 加载失败 → Goal 栈损坏 → 重建 Goal 栈（从 Mission 向下恢复）
  working_memory 加载失败 → 丢失上下文 → 标记为"失忆状态"，继续运行
  attention_focus 失败 → 重新扫描环境 → 重建注意力状态
```

---

## Recovery ABI

### 启动流程

```
进程启动
    ↓
BOOTING
    ↓
1. Load Identity
    ├── 成功 → 2
    └── 失败 → IDENTITY_CRISIS → SAFE MODE
    ↓
2. Verify Constitution
    ├── 成功 → 3
    └── 失败 → CONSTITUTION_TAMPERED → SAFE MODE
    ↓
3. Load Last Checkpoint
    ├── 成功 → 4
    ├── 损坏 → RESTORE_PREVIOUS_CHECKPOINT → 3
    └── 不存在 → COLD_START → 4
    ↓
4. Restore Working Memory
    ├── 成功 → 5
    └── 部分失败 → AMNESIA_MODE (标记，继续)
    ↓
5. Verify Goal Stack
    ├── 完整 → 6
    └── 损坏 → REBUILD_GOAL_STACK → 6
    ↓
6. Resume Runtime Loop
    ├── → RUNNING
    └── RuntimeState = RUNNING
```

### 崩溃恢复

```
崩溃检测:
  - 进程退出时最后写入 CRASHED 标记
  - 下次 BOOT 检测到 CRASHED 标记

崩溃恢复:
  1. 加载最近的完整检查点
  2. 如果检查点距今 < 阈值（如 5 分钟）→ 从检查点恢复
  3. 如果检查点距今 > 阈值 → 进入 SAFE MODE（可能丢失重要状态）
  4. 记录崩溃事件到 EventBus
  5. 通知用户："OCOS 从崩溃中恢复，请检查状态"
```

### 冷启动

```
条件: 没有历史检查点存在

冷启动流程:
  1. BOOT → 加载 Identity
  2. Identity 来自 Manifesto（或交互式创建）
  3. Goal 栈从 Mission → 逐级分解
  4. Working Memory 为空
  5. Attention 初始化为环境扫描
  6. 进入 RUNNING
```

---

## 降级 Tick

当 Tick 内部阶段超时或失败时：

```
正常 Tick:          PERCEIVE → EVALUATE → MAINTAIN → DECIDE → ACT → LEARN → CHECKPOINT
降级 Tick (轻量):   PERCEIVE → EVALUATE → CHECKPOINT  (跳过 DECIDE/ACT/LEARN)
降级 Tick (最轻):   PERCEIVE → CHECKPOINT               (仅感知+保存)
```

**触发条件**：
- 连续 3 个 Tick 的某阶段超时 → 降级到轻量
- 降级后连续 5 个 Tick 正常 → 恢复完整 Tick
- SAFE MODE 期间 → 最轻 Tick（仅感知）

---

## 与现有组件的关系

| 现有组件 | 在 Runtime 中的钩子 |
|----------|-------------------|
| EventBus | PERCEIVE 阶段读取新事件 |
| Attention (Phase 36) | PERCEIVE 阶段更新 attention_snapshot |
| Goal Stack | EVALUATE 阶段检查 Goal 状态 |
| Homeostasis (Phase 31) | EVALUATE 阶段检查健康指标 |
| MAINTENANCE Goal | MAINTAIN 阶段执行 |
| Planner (Phase 32) | DECIDE 阶段产出 Decision |
| Executive Controller | ACT 阶段执行 ExecutionIntent |
| Feedback Loop (Phase 37) | LEARN 阶段处理 ExecutionResult |
| Checkpoint Store | CHECKPOINT 阶段持久化 |
| Identity Boundary (Gate-3) | 每个 Tick 验证 Identity.anchor hash |

---

## 禁止的行为

```
Runtime SHALL NOT:
  - 创建 HUMAN 级别的 Goal（只能创建 MAINTENANCE）
  - 修改 Identity.anchor
  - 修改 Identity.self_view
  - 跳过 MAINTAIN 阶段执行 DECIDE
  - 在 SAFE MODE 下执行 ACT
  - 在 SLEEPING 下执行外部 Action
  - 自动从 SAFE MODE 恢复到 RUNNING（必须用户确认）
```
