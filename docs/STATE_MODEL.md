# State Model — 概念定义文档

> **版本**: v0.1 (概念草案)
> **状态**: Pre-Freeze 概念文档
> **范围**: 只定义概念和使用契约，不涉及代码实现
> **目标**: 在 v1.0 冻结前明确 State 的位置，为 v1.x 实现预留接口空间

---

## 1. 为什么需要 State

### 1.1 当前缺失

OCOS 当前有三个核心概念：

| 概念 | 性质 | 例子 |
|------|------|------|
| **Information** | 历史记录 — "发生过什么" | "太阳昨天升起了" |
| **Knowledge** | 泛化规律 — "世界如何运作" | "太阳会升起" |
| **State** | **缺失** — "现在是什么情况" | **"现在在下雨"** |

当前系统中，State 散落在：

- `ContextManager.WorkingMemory` — 部分扮演 State，但没有类型化
- `AttentionEngine` — 隐式记录"当前注意什么"
- 各 Engine 内部自己维护状态（无统一契约）

### 1.2 缺失的后果

1. **没有"当前世界快照"的原子单元** — Decision 无法知道"此刻系统相信什么"
2. **没有 State 生命周期** — 无法追踪 state 的产生、活跃、被替代
3. **没有 State → Information 的转换契约** — 当前 State 过期后应当成为 Information
4. **World Intelligence 无法构建** — 世界智能 = State 快照 × Knowledge 规律

---

## 2. State 的定义

### 2.1 核心命题

> **State = 系统此刻相信世界是什么样。**

它与 Information 和 Knowledge 的关系：

```
Information (过去) ──过期──→ State (现在) ──过时──→ Information (历史记录)
                                    ↑
                              Knowledge (规律) 用于预测未来 State
```

### 2.2 形式定义

```
State {
    state_id: UUID
    type: StateType          // 状态的类型分类
    domain: str              // 所属领域（world / task / agent / conversation ...）
    content: dict            // 状态数据体
    timestamp: datetime      // 状态被观测或断言的时间
    confidence: float        // 系统对该状态的置信度
    source: StateSource      // 产生源（Observation / Inference / Decision / External）
    superseded_by: UUID|null // 被哪个后续 State 替代
    metadata: StateMetadata  // 扩展元数据
}
```

### 2.3 与 Information 的精确区别

| 维度 | Information | State |
|------|-------------|-------|
| 时间指向 | 过去 | 现在 |
| 生命周期 | 永久（draft→active→archived/deprecated） | 临时（created→active→superseded） |
| 过期行为 | 归档或遗忘 | 变成 Information |
| 更新方式 | 追加（immutable） | 替换（supersede） |
| 消费者 | 分析、学习、审计 | Decision、Planning、Realtime |

---

## 3. State 类型分类

### 3.1 已知 State 类型

| StateType | 描述 | 例子 |
|-----------|------|------|
| `WorldState` | 外部世界的当前事实 | "现在下雨"、"用户在线" |
| `TaskState` | 当前任务的执行状态 | "写作中"、"推理中" |
| `GoalState` | 目标系统的当前状态 | "目标 A 活跃"、"目标 B 已暂停" |
| `SystemState` | 系统内部运行状态 | "CPU 70%"、"沙箱激活中" |
| `AgentState` | Agent 内部状态 | "疲惫度、注意力焦点" |
| `IdentityState` | 身份/角色状态 | "当前身份：Writer" |
| `ConversationState` | 对话会话状态 | "第 3 轮对话、用户情绪" |
| `SimulationState` | 模拟平行世界状态 | "假设分支 A 的当前结果" |
| `ExecutionState` | 动作执行状态 | "Action X 执行中，进度 45%" |

### 3.2 创建规则

State 可以通过以下方式产生：

1. **Observation → State**: 外部感知直接建立当前事实（"我感知到下雨"）
2. **Inference → State**: 从 Knowledge + 其他 State 推理出当前事实（"根据气压下降 + 湿度，推断即将下雨"）
3. **Decision → State**: 决策导致状态变化（"Decision：开始写作 → TaskState：写作中"）
4. **External → State**: 外部系统注入状态

---

## 4. State 生命周期

### 4.1 状态机

```
Created ──→ Active ──→ Superseded
               │
               └──→ Expired
```

| 状态 | 含义 |
|------|------|
| `Created` | State 被创建，尚未生效 |
| `Active` | 系统当前相信这个 State |
| `Superseded` | 被新 State 替代（记录了 superseded_by 引用） |
| `Expired` | 超时/过期（无后继者） |

### 4.2 过期处理

当 State 变为 Superseded 或 Expired 时，它应当自动转换为一条 Information：

```
State "现在下雨" ──(被替代)──→ Information "2026-07-22T12:00:00 系统认为在下雨"
```

这种设计保证了：
- State 是不稳定的（随时可能被替代）
- Information 是稳定的历史记录
- 没有信息丢失 — 所有 State 最终成为 Information

---

## 5. State 与现有架构的关系

### 5.1 定位

State 位于 Information 和 Knowledge 之间，是独立的概念层：

```
┌──────────────────────────────────────────────┐
│                  Knowledge                    │  ─── 规律
├──────────────────────────────────────────────┤
│                  State Model                  │  ─── 当前事实  ★ NEW
├──────────────────────────────────────────────┤
│               Information                     │  ─── 历史记录
├──────────────────────────────────────────────┤
│                  Runtime                      │  ─── 现在运行什么
├──────────────────────────────────────────────┤
│                  Kernel (ABI)                 │  ─── 不可变契约
└──────────────────────────────────────────────┘
```

### 5.2 接口契约

所有 Engine 对 State 的访问应通过统一 ABI：

```
StateABI {
    get_state(state_id: UUID) → State
    get_active_states(type: StateType, domain: str) → list[State]
    set_state(state: State) → State  // 返回新 State，自动 supersede 旧 State
    supersede_state(state_id: UUID, new_state: State) → State
    subscribe(type: StateType, callback) → Subscription
}
```

### 5.3 与现有概念的互操作

| 操作 | 涉及模块 | 说明 |
|------|----------|------|
| Observation → State | Perception → StateABI | 外部感知产生 State |
| Decision → State | Decision → StateABI | 决策改变状态 |
| State → Information | StateABI → EventBus | State superseded 时发布 Information |
| State → Decision | StateABI → Decision | Decision 需要当前 State 做选择 |
| Knowledge × State → Prediction | PredictionEngine | 规律 × 当前状态 → 预测下一步 |
| State → Attention | StateABI → Attention | Attention 需要知道"当前什么状态" |

---

## 6. 冻结前的预留

### 6.1 当前可做（不影响现有架构）

1. **在 INFORMATION_THEORY.md 中标注 State 为未来概念** — ✅ 已完成
2. **确认 State 不依赖现有模块** — State 只需要 Kernel 的 EventType + UniversalAddress
3. **预留 EventType** — 新增 `STATE_CHANGED`, `STATE_SUPERSEDED`, `STATE_EXPIRED`

### 6.2 冻结后不可做的（v1.0 不动）

1. 不创建 `ocos/state/` 包
2. 不修改 Constitution 添加 State 规则
3. 不修改 ABI 添加 State 类型
4. 不修改 Information 的状态机

State Model 是 v1.x 的第一个大特性，不在 v1.0 冻结范围内。

---

## 7. State 使用场景（未来展望）

### 7.1 World Intelligence Pipeline

```
State(当前世界) + Knowledge(世界规律)
    → PredictionEngine → State(预测的未来)
    → Decision → Action
    → Perception → State(新的当前事实)
    → Learning → Knowledge(新的规律)
```

### 7.2 Simulation

```
State(当前) → Fork → State_Sim_A_(假设分支)
    → 快速推演 → State_Sim_A_(推演结果)
    → 与 State_Sim_B 比较
    → Decision(选择最佳路径)
```

### 7.3 Conflict Detection

```
State_A("用户在线")  // 从 Observation 产生
State_B("用户离线")  // 从另一个 Observation 产生
    → ConflictResolutionEngine
    → State_C("用户在线，最后活跃 2 分钟前")
```

---

## 8. 与其他层的关系总结

```
                  ┌──────────┐
                  │ Knowledge │  State 的规律解释器
                  └────┬─────┘
                       │ 指导 State 的预测
                       ▼
┌──────┐     ┌──────────────┐     ┌───────────┐
│ Info │ ←── │ State Model  │ ──→ │  Decision  │
│(历史)│     │  (当前事实)   │     │  (选择)    │
└──────┘     └──────┬───────┘     └───────────┘
                    │
                    ▼
              ┌──────────┐
              │  Runtime  │  State 的调控者
              └──────────┘
```

State Model 使得 Information（历史）、State（当前）、Knowledge（规律）、Decision（选择）四者形成完整闭环。这是目前 OCOS 架构中最后一块尚未定义的概念拼图。

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-22 | 初版概念草案 — v0.1 Pre-Freeze Concept |
