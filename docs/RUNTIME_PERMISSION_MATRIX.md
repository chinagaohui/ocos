# OCOS Runtime Permission Matrix（运行时权限矩阵）

> **v1.0 — 2026-07-26 — Phase 38 Gate 修补**  
> **层级：Layer 1 — Constitution 级别**  
> **地位：本矩阵定义 Runtime 各组件的读写权限边界。违反此矩阵视为 Constitution Violation。**

---

## 核心理念

**Runtime 是调度者，不是主体。**

```
Scheduler（调度 Tick）
    ↓
Runtime Components（组件）
    ↓
Identity / Goal / Memory / Self / Agent
```

每个组件对被管理对象有不同的读写权限。权限矩阵消除隐式越权。

---

## Runtime 组件权限矩阵

| Runtime 组件 | Goal 创建 | Goal 状态 | Memory | Self Model | Identity | Agent 调用 |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tick Engine** | READ | READ | READ | READ | READ | NO |
| **Perception** | NO | NO | WRITE WM | NO | NO | NO |
| **Attention** | NO | READ | WRITE WM | NO | READ | NO |
| **Goal Maintenance** | CREATE MAINTENANCE | UPDATE STATE | READ | NO | NO | NO |
| **Evaluator** | NO | READ | READ | NO | NO | NO |
| **Planner** | NO | READ | READ | NO | NO | NO |
| **Executive Controller** | NO | READ | WRITE Result | NO | NO | CALL (经 Decision) |
| **Feedback Loop** (P37) | NO | NO | WRITE Evidence | NO (见注) | NO | NO |
| **External Agent** | NO | NO | NO | NO | NO | SELF |

**注**：Feedback Loop 不直接写 Self Model。它通过 Evidence Pool → Belief Update 间接影响认知，但 Belief 不直接写入 Identity.self_view。

---

## 权限语义

### Goal

| 操作 | 语义 | 允许的组件 |
|------|------|-----------|
| READ | 读取 Goal 状态、内容、依赖 | Tick Engine, Attention, Evaluator, Planner, Executive Controller |
| CREATE MAINTENANCE | 创建 MAINTENANCE 级别的 Goal | Goal Maintenance |
| CREATE HUMAN/SYSTEM | 创建 HUMAN/SYSTEM Goal | 用户（CLI/API/REPL）/ Orchestrator |
| UPDATE STATE | 改变 Goal 状态（PENDING→ACTIVE→COMPLETED） | Goal Maintenance, Executive Controller |
| MODIFY CONTENT | 修改 Goal 内容、目标、优先级 | 用户（CLI/API/REPL） |
| DELETE | 删除 Goal | 用户（需确认） |

### Memory

| 操作 | 语义 | 允许的组件 |
|------|------|-----------|
| READ | 读取记忆内容 | 所有组件 |
| WRITE WM | 写入 Working Memory | Perception, Attention |
| WRITE Result | 写入执行结果到 Episode | Executive Controller, Feedback Loop |
| MODIFY LT | 修改长期记忆 | LEARN 阶段（经 Consolidation） |
| DELETE | 删除记忆 | Forgetting 机制（不直接） |

### Self Model

| 操作 | 语义 | 允许的组件 |
|------|------|-----------|
| READ | 读取自我认知 | Tick Engine, Attention, Evaluator, Planner |
| UPDATE CAPABILITIES | 更新能力列表 | 用户 / REFLECT（Phase 39+，经用户确认） |
| UPDATE LIMITATIONS | 更新限制认知 | 用户 / REFLECT（Phase 39+） |
| UPDATE PREFERENCES | 更新偏好 | 用户 / 缓慢演化 |

### Identity

| 操作 | 语义 | 允许的操作者 |
|------|------|-----------|
| READ | 读取身份 | Runtime 全部组件 |
| READ HASH | 验证完整性 | Tick Engine（每个 Tick） |
| MODIFY ANCHOR | 修改核心身份 | 用户（需显式确认） |
| MODIFY STATE | 修改运行时状态 | Runtime Loop |
| MODIFY SELF_VIEW | 修改自我模型 | 用户 / REFLECT（Phase 39+） |

### Agent

| 操作 | 语义 | 允许的组件 |
|------|------|-----------|
| CALL | 调用 Agent 执行任务 | Executive Controller（需经 Decision） |
| REGISTER | 注册新 Agent | 用户 / Phase 40 Capability Nervous System |
| UNREGISTER | 注销 Agent | 用户 / Phase 40 Capability Nervous System |
| MONITOR | 监控 Agent 执行状态 | Executive Controller |

---

## 禁止的越权行为

### 禁止：Tick Engine 调用 Agent

```
禁止:
  Tick Engine → 直接调用 Agent → "帮我查一下..."

正确:
  Tick → PERCEIVE → EVALUATE → DECIDE (Planner) → Executive Controller → Agent
  Agent 调用必须经过 Decision → Executive Controller 链路
```

**理由**：Tick Engine 是调度者，不能绕过决策层直接执行。否则 Tick 本身就变成了 Agent。

### 禁止：Goal Maintenance 修改用户 Goal

```
禁止:
  MAINTENANCE Goal → UPDATE STATE of HUMAN Goal → "把用户 Goal 标记为完成"

允许:
  MAINTENANCE Goal → UPDATE STATE of MAINTENANCE Goal → "标记维护完成"
  Evaluator → READ HUMAN Goal → "检测到过期" → 通知用户
```

**理由**：用户 Goal 的状态变更只能由用户或 Executive Controller（执行后标记完成）决定。维护系统不能替用户关闭目标。

### Attention Authority Boundary（注意力权限边界 — v2.0）

> **Phase 38 Gate 修补补充，2026-07-26**
> **地位：本约束防止 Attention 成为隐形决策中心。**

Attention Engine 目前仅作为评分层输出 attention_snapshot。但 Runtime 一旦持续运行，Attention 会在每个 Tick 重新计算焦点，存在累积越权风险。

**允许**：

```
Attention → 调整焦点排序     (在现有 Goal 中选"看哪个")
Attention → 更新焦点权重     (relevance_weight 微调)
Attention → 标记过期焦点     (上次关注的 Goal 已不相关)
Attention → 写入 WM          (将当前焦点写入 Working Memory)
Attention → 发出 Attention Shift 事件 (通知 Planner 兴趣变化)
```

**禁止**：

```
Attention → 创建 Goal         (即使"发现重要事件"也不能直接创建 Goal)
Attention → 修改 User Goal    (不能改变用户 Goal 的优先级/状态/内容)
Attention → 修改 Identity     (不能影响 self_view 或 anchor)
Attention → 跳过 Evaluator    (Attention 不能绕过评估直接触发 DECIDE)
Attention → 提升 MAINTENANCE  (不能把内部维护焦点升级为用户级 Goal)
```

**边界检查**：

```
每个 Tick:
  Attention 输出 attention_snapshot 后:
    1. 检查焦点是否指向已存在的 Goal               → 如是新 Goal → 违规
    2. 检查是否有 Goal 被 Attention 修改了优先级    → 如有 → 违规
    3. 检查 attention_snapshot 是否包含 Identity 字段 → 如有 → 违规

违规处理:
  - 拒绝 attention_snapshot，使用上一个有效快照
  - 记录 AuditableViolation
  - 通知用户
```

**与 Phase 36 Attention-Planning Boundary 的关系**：

Phase 36 冻结了 Attention ↔ Planning 边界。本约束扩展为 Runtime 级别的 Attention 边界：

```
Phase 36:  Attention 选"看哪里" ≠ Planning 决定"做什么"
Phase 38:  Attention 选"看哪里" ≠ Runtime 创建 Goal

两个边界互为补充:
  Phase 36 → 防止 Attention 绕过 Planning 决策
  Phase 38 → 防止 Attention 绕过 Goal Authority 创建 Goal
```

### 禁止：Attention 修改 Goal（Phase 36 保留）

```
禁止:
  Attention → 发现 Goal 不重要 → 降低 Goal 优先级
  Attention → 发现新事件重要 → 创建新 Goal

允许:
  Attention → 更新 attention_snapshot → 影响 DECIDE 阶段的决策输入
```

**理由**：Attention 选"看哪里"，Goal 决定"做什么"。Attention 的评分是决策输入，不是决策本身。

### 禁止：Feedback Loop 直接写入 Self Model

```
禁止:
  Feedback → "Agent A 连续成功 5 次" → 直接修改 self_view.capabilities

允许:
  Feedback → Evidence Pool → Belief Update → 间接影响认知
  REFLECT Phase 39+ → 综合 Evidence + Belief → 生成 self_view 更新建议
```

**理由**：Feedback 是 observation 不是 self-knowledge。即使观察到 5 次成功，也不意味着"我有这个能力"——那需要更长时间的经验积累和用户确认。

---

## 权限验证机制

```
每个 Runtime 组件在执行操作前:
  1. 查询 Permission Matrix
  2. 如果操作被允许 → 执行
  3. 如果操作被拒绝 → PermissionError → 记录 AuditableViolation → 通知用户

AuditableViolation:
  - violation_id: UUID7
  - component: 违规组件名
  - operation: 尝试的操作
  - target: 操作目标
  - tick_id: 发生的 Tick
  - timestamp: UTC
  - severity: WARNING | CRITICAL
```

---

## 与 Goal Authority Model 的关系

| Goal Authority | Goal 创建 | Goal 修改 | Agent 调用 | Identity 修改 |
|---------------|:---:|:---:|:---:|:---:|
| USER_AUTHORITY | ✅ 任意层级 | ✅ 任意 | ✅ | ✅ (经确认) |
| SYSTEM_AUTHORITY | ✅ Task 级 | ✅ 自己创建的 | 间接 | ❌ |
| MAINTENANCE_AUTHORITY | ✅ MAINTENANCE 级 | ✅ 自己创建的 | ❌ | ❌ |
| PROPOSAL_AUTHORITY | 建议 | ❌ | ❌ | ❌ |

---

## 矩阵的不变性

本权限矩阵是 Constitution 级别。修改要求：

1. 发起 Amendment Proposal
2. 审计受影响的所有组件
3. 更新所有相关 Gate 测试
4. 用户批准
5. 更新 Constitution Hash

任何单个 Phase 不能单方面修改此矩阵。
