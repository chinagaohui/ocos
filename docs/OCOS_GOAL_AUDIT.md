# OCOS GOAL AUDIT v1.0

**状态**: Draft
**日期**: 2026-07-22
**审计范围**: Goal ABI、事件、生命周期、层级结构、所有权、与 Process/Decision 边界
**前置审计**: Memory ✅, Process ✅, Decision Audit (一阶段) ✅
**前置依赖**: 无（GOAL_THEORY 冻结先于 DECISION_THEORY）

---

## 1. 当前架构扫描

### 1.1 Goal ABI (ocos/kernel/abi.py)

```python
@dataclasses.dataclass(frozen=True)
class Goal:
    """目标：系统行为的驱动方向。"""
    goal_id: str = ...          # default: uuid4
    description: str = ""
    priority: int = 0            # 0=low, 1=normal, 2=high, 3=critical
    status: str = "active"       # active | paused | completed | abandoned
    timestamp: str = ...
    schema_version: str = ...
```

### 1.2 Goal 事件 (ocos/kernel/event_schema.py)

| EventType | 必须字段 |
|-----------|---------|
| `GOAL_SET` | goal_id, description, priority |
| `GOAL_UPDATED` | goal_id, status |
| `GOAL_COMPLETED` | goal_id, outcome |

### 1.3 消费者清单

| 模块 | 用途 |
|------|------|
| `runtime/context_manager.py` | 管理 `dict[str, Goal]`；add/remove/get/update_status |
| `runtime/scheduler.py` | 订阅 GOAL_SET/UPDATED/COMPLETED；优先级 0.8/0.6/0.7 |
| `runtime/attention_engine.py` | `goal_relevance` 评分（与 active Goal 的 description 关键词匹配） |
| `runtime/policy_engine.py` | 白名单中包含 `set_goal`、`complete_goal` action_type |
| `kernel/abi.py` — `Decision.goal_id` | Decision 引用其来源 Goal |
| `platform/trace_engine.py` | `DecisionTrace.goal_id`；`Trace.address = "working:goal:g1"` |
| `platform/audit_engine.py` | Trace 中提取 goal_id |
| `tests/test_context_manager.py` | 120 行 Goal 测试 |
| `tests/test_object_model.py` | Goal 是 CORE_OBJECTS 之一 |

### 1.4 未发现 Goal 的地方

| 位置 | 说明 |
|------|------|
| `ocos/models/information.py` | Goal 不是 Information |
| `constitution.py` | 宪法未提及 Goal |
| `engines/address_resolver.py` | Address 未处理 "goal:" 前缀以外的 Goal 引用 |
| 现有文档 | 无 GOAL_THEORY.md 或 Goal 设计文档 |

---

## 2. 你对 Goal 的六问 → 当前状态映射

### Q1: Goal 的语义边界 (⚡最严重)

**当前状态**: Goal 的 `description` 字段承载了目标描述，但未区分"方向性意图"与"实现方式"。

**核心原则**: Goal 是**规范性对象**（Desired Future），Information 是**描述性对象**（Observed/Derived State）。Goal 回答"世界应该变成什么"，Information 回答"世界现在是什么"。两者属于不同范畴。

**GOAL_THEORY 的边界**: 只冻结到 Goal → Decision。Plan、Task、Action 属于后续理论（Planning / Execution），不在 GOAL_THEORY 中冻结链条。

```
Goal Theory 的边界
────────────────
Goal
    ↓
Decision      # Goal 驱动 Decision，但不规定如何实现
```

Goal 不负责实现方式（那属于 Planning）。Goal 不负责执行（那属于 Execution）。

### Q2: Goal 是状态还是对象？(🔴)

**当前状态**: Goal 是 frozen dataclass（对象），但 `ContextManager` 通过 `dataclasses.replace()` 创建新实例替换旧对象来模拟状态更新。Goal 的 `status` 字段在取代。

**核心判断: Goal ≠ Information**。理由如下：

| 维度 | Information (描述性) | Goal (规范性) |
|------|---------------------|---------------|
| 回答 | 世界现在是什么 | 世界应该变成什么 |
| 范畴 | Observed / Derived State | Desired Future |
| 生命周期 | Acquire→Store→Curate→Recall→Passivate→Decay→Archive | active→paused→completed/failed/superseded/expired |
| 变更动力 | 外部观察 → Information 生成 | 内部意图 → Goal 设定 → Decision 驱动执行 |
| 终止方式 | Decay / Archive | Completed / Failed / Superseded / Cancelled / Expired |

**建议**: Goal 保持独立对象，不合并入 Information。

### Q3: Goal 从哪里来？(🟡)

**当前状态**: 无来源追踪。Goal 的 `description` 和 `priority` 由创建者决定，但来源信息未记录。

**发现**: `policy_engine` 的白名单包含 `set_goal` action_type，说明 Goal 可以被 Agent 内部创建。但 `source` 字段不存在——无法区分"用户显式指定"vs"Agent 自主生成"vs"上级 Goal 分解"。

### Q4: 层级关系 (🔴)

**当前状态**: 无层级支持。Goal 只有平铺的 `goal_id` → `description`。没有 `parent_goal_id`、`sub_goals`、`mission_id`。

**建议**: GOAL_THEORY.md 冻结层级兼容结构：

```python
class Goal:
    goal_id: str
    parent_goal_id: str | None = None   # 上级 Goal（None = root）
    mission_id: str | None = None       # 可选顶层 Mission
    description: str
    priority: int
    source: str              # user | agent_generated | decomposition | external_event | system
    # ... 其他字段
```

### Q5: Goal 如何结束？(🟡)

**当前状态**: 仅 4 个 `status` 值: `active | paused | completed | abandoned`。事件仅 3 个。没有 `failed`、`cancelled`、`superseded`、`expired` 等结束状态。

**缺少的事件**:
- `GOAL_FAILED` — 目标不可达成
- `GOAL_SUPERSEDED` — 被更优目标取代
- `GOAL_CANCELLED` — 被创建者撤销
- `GOAL_DECOMPOSED` — 被分解为子目标

### Q6: Goal 与其他模块的边界 (✅ 基本正确)

**当前状态**:
- Goal **不负责** 如何实现 ✅（决策由 Decision 负责）
- Goal **不负责** 执行 ✅（Action 由 Scheduler/Execution 负责）
- Goal 可以成为多个 Process 的输入 ✅（ContextManager 提供 Goal 作为上下文）
- Goal 不负责存储经验 ✅（Memory 负责）

**但需要明确定义**:
- Goal 是否可以作为 Information（从而拥有 Address）
- Goal 与 Preference 的关系（当前 Context Manager 同时管理 Goal 和 Preference）
- Goal 与 Constitution 的关系（当前宪法无 Goal 相关规则）

---

## 3. 发现总结

| # | 项目 | 严重度 | 当前状态 | 建议 |
|---|------|--------|---------|------|
| G1 | Goal ↔ Task/Plan/Action 边界缺失 | 🔴 高 | 未定义 | GOAL_THEORY 冻结链条映射 |
| G2 | Goal 生命周期属于对象还是 Information？ | 🔴 高 | 未定决 | 冻结时选择 |
| G3 | Goal 无层级支持 | 🟡 中 | 不存在 | 添加 parent_goal_id |
| G4 | Goal 无来源追踪 | 🟡 中 | 不存在 | 添加 source 字段 |
| G5 | Goal 结束类型不完整 | 🟡 中 | 仅 4 种状态 | 扩展状态：superseded/cancelled/expired |
| G6 | Goal 事件不完全 | 🟡 中 | 仅 3 事件 | 新增 GOAL_FAILED/SUPERSEDED/CANCELLED |
| G7 | Goal 未出现在宪法中 | 🟢 低 | 宪法无 Goal | 可选新增宪法规则 |
| G8 | Goal 在 abi.py 使用字符串状态（无类型安全） | 🟢 低 | str 字段 | 可冻结为 GoalStatus 枚举 |
| G11 | **Goal ↔ Decision 是一对多关系** — OCOS 目前未显式禁止一对一的隐含绑定，但后续重规划、自修复、策略切换都需要多 Decision 共享同一 Goal | 🔴 高 | 未定义 | 在 GOAL_THEORY 冻结此约束 |
| G9 | Goal ↔ Process 边界 | ✅ 正常 | 无 ProcessType.GOAL | ✅ 正确 |
| G10 | Goal ↔ Decision 关系（Decision.goal_id） | ✅ 正常 | 引用正确 | ✅ 正确 |

---

## 4. 推荐冻结方向

### 4.1 Goal 不是 Process（已确认 ✅）

`ProcessType` 中不需要 `GOAL`。Goal 作为 Process 的输入，而非 Process 本身。四个"不堆叠"原则已涵盖此约束。

### 4.2 Goal 的三个不变量

**Invariant 1 — Goal 不描述实现方式**。Goal 只描述"世界应该变成什么"，不描述"如何实现"。错误示例：`Goal: 去调用 execute_engine`（这是实现方式）。正确示例：`Goal: 获得完整地图`（实现方式属于 Planning / Decision）。

**Invariant 2 — Goal 生命周期长于 Decision 生命周期**。Goal 可以长期存在，而针对该 Goal 的 Decision 可以反复变化（失败→重规划）。错误示例：每个 Goal 只创建一次 Decision。正确示例：

```
Goal: 逃离星球
    ├── Decision A → failed → retry
    ├── Decision B → failed → retry
    └── Decision C → succeeded
```

Goal 从设定到完成/终止之间的跨度可能经历多次 Decision 迭代。

**Invariant 3 — Goal 可以产生多个 Decision（一对多关系）**。如果 Goal ↔ Decision 是一对一，则系统不支持重规划、自修复、多轮尝试、策略切换。一个 Goal 可以：

```
产生多个 Decision（串行或并行）
    ↓
失败的 Decision 不终止 Goal
    ↓
被新的 Decision 取代（旧的 Decision 标记为 superseded）
```

这是后续 Agent 自主能力的架构基础。

### 4.3 Goal 的生命周期模型

**确认**: Goal = 拥有独立生命周期对象（非 Information）。

理由：
1. Goal 是**规范性对象**（Desired Future），Information 是**描述性对象**（Observed/Derived State）。Goal 和 Information 属于不同范畴。
2. Goal 的生命周期（active→paused→completed/failed/superseded/expired）与 Information Lifecycle（Acquire→Store→...→Archive）不同源
3. Goal 是"意图表达"，不是"事实记录"
4. Information 的终止方式（Decay→Archive）不适用于 Goal——Goal 的终止方式是"完成时产生 Memory/Knowledge"

### 4.3 Goal 状态机（建议冻结）

```
GoalStatus 枚举:
    ACTIVE
    PAUSED        ← 可回退到 ACTIVE
    COMPLETED     ← 达成
    FAILED        ← 不可达成
    SUPERSEDED    ← 被新 Goal 替代
    CANCELLED     ← 被创建者撤销
    EXPIRED       ← 超时或失去时效
```

合法转换:
```
ACTIVE    → PAUSED / COMPLETED / FAILED / SUPERSEDED / EXPIRED
PAUSED    → ACTIVE / CANCELLED / SUPERSEDED
COMPLETED → (终止态)
FAILED    → (终止态)
SUPERSEDED → (终止态)
CANCELLED → (终止态)
EXPIRED   → (终止态)
```

### 4.4 Goal 数据模型（建议冻结）

```python
@dataclasses.dataclass(frozen=True)
class Goal:
    goal_id: str
    parent_goal_id: str | None = None
    mission_id: str | None = None
    description: str
    priority: int          # 0~10
    status: GoalStatus = GoalStatus.ACTIVE
    source: GoalSource = GoalSource.AGENT_GENERATED
    owner_id: str = ""     # 负责该 Goal 的 Agent/Module
    created_at: str = ...
    completed_at: str | None = None
    schema_version: str = ...
```

### 4.5 Goal 事件（建议冻结）

| EventType | Required Payload |
|-----------|-----------------|
| `GOAL_SET` | goal_id, description, priority, source |
| `GOAL_UPDATED` | goal_id, status |
| `GOAL_COMPLETED` | goal_id, outcome |
| `GOAL_FAILED` | goal_id, reason |
| `GOAL_SUPERSEDED` | goal_id, superseded_by |
| `GOAL_CANCELLED` | goal_id, reason |
| `GOAL_DECOMPOSED` | goal_id, sub_goal_ids |

---

## 5. 后续工作

| 步骤 | 交付物 | 前置依赖 |
|------|--------|---------|
| 冻结 GOAL_THEORY.md | 概念定义、六问答案、状态机、与其他层边界 | 本审计 |
| Goal 模型重构 | `GoalStatus` 枚举 + 扩展 Goal 数据模型 | GOAL_THEORY 冻结 |
| Goal 事件扩展 | 新增 4 个 Goal 事件 | 模型冻结 |
| Goal 测试套件 | 模型 + 生命周期 + 事件 + 集成测试 | 实现后 |
| 宪法更新（可选） | 新增或确认 Goal 在宪法中的地位 | GOAL_THEORY 冻结 |
| → Decision Audit 二阶段 | DECISION_THEORY.md 冻结 | Goal 冻结 |

---

## 6. 对 Decision Audit 的影响

Goal 冻结后，以下问题在 Decision Audit 中将更清晰：

| 之前混淆的问题 | 冻结 Goal 后的答案 |
|---------------|-------------------|
| Decision 输入包含什么？ | `{Goal, Reasoning Result, Context, Preference, Policy}`，其中 Goal 是 Address 引用 |
| Decision 属于谁？ | 引用 `Goal.owner_id` |
| Decision 是否可撤销？ | Goal 允许 SUPERSEDED → 旧的 Decision 自动失效（Invariant 3） |
| 一个 Goal 是否只对应一个 Decision？ | **否**。Goal ↔ Decision 是一对多（Invariant 3）。失败的 Decision 不终止 Goal |
| Decision 输出是什么？ | 属于后来的 Planning Theory 定义。GOAL_THEORY 仅明确 Goal → Decision |
| Goal 不负责什么？ | 不负责如何实现（Invariant 1）、不负责执行（Execution） |
