# OCOS Phase 36 — Executive Attention Binding Freeze（执行-注意力绑定协议）

> **v0.2 — 2026-07-25 — Phase 36 Architecture Freeze (APPROVED WITH MINOR AMENDMENTS)**
> **层级：Layer 2 — 编排层（Orchestration）**
> **前置：Phase 35 Attention & Cognitive Control Freeze**
> **地位：定义 Attention 决策如何约束 Goal Maintenance / Planning / Execution 的资源分配。**
>
> 本协议不新增模块。它在 Phase 34-35 已有的器官之间建立信息通路。

---

## §1 核心定义

Phase 36 解决一个问题：

> OCOS 已经有了注意力（Phase 35）和目标系统（Phase 22+），
> 但二者是独立运行的。一个高优先级 Goal 到达后，
> Planning Trigger 会立即分解，**不管 OCOS 当前注意力在哪**。

这导致：
- 多个 Goal 同时触发 Planning → 认知过载
- Attention 疲劳时 Execution 仍在推进 → 低质量输出
- Attention 中断后旧 Goal 继续占用 Planning 资源

**Phase 36 目标**：让 Attention 决策真正约束下游 Goal/Planning/Execution 的资源分配。

```
Phase 35:  Attention → 认知选择
Phase 36:  Attention → 认知选择 → Goal 维护 → Planning 门控 → Execution 调度
```

---

## §2 AttentionReport ABI（注意力报告）

### §2.1 定义

`AttentionReport` 是 Attention 系统对外发布的标准化快照，
下游步骤（Goal Maintenance / Planning / Execution）只读此报告，不直接访问 Attention 内部状态。

```python
@dataclass
class AttentionReport:
    """Phase 36: 注意力系统对外报告。

    由 CognitiveAttentionController.emit_report() 在每个 tick 的 step 2 末尾生成。
    所有下游步骤只读此报告，不访问 Attention 内部状态。
    """

    tick_id: str                          # 关联的 tick id
    focus_state: str                      # IDLE | FOCUSED | INTERRUPTED | SUSPENDED | RE_EVALUATION
    current_focus_id: str | None          # 当前焦点目标 ID
    current_focus_type: str | None        # EVENT | GOAL | TASK | NONE
    current_focus_priority: float         # 当前焦点复合优先级
    fatigue: float                        # 注意力疲劳度 [0, 1]
    interrupt_count_1m: int               # 过去 1 分钟中断次数

    # 最近决策摘要
    last_decisions: list[DecisionDigest]  # 最近 N 个 AttentionDecision 的摘要

    # 推荐指令（Attention 不强制，只建议）
    recommendation: AttentionRecommendation

@dataclass
class DecisionDigest:
    event_id: str
    decision: str                         # ACCEPTED | QUEUED | DEFERRED | DISMISSED
    composite: float

@dataclass
class AttentionRecommendation:
    """Attention 对下游的推荐（纯建议，不绑定）。"""
    suppress_planning: bool               # 建议暂停 Planning
    prioritize_goals: list[str]           # 建议优先维护的 Goal ID 列表
    deprioritize_goals: list[str]         # 建议延迟维护的 Goal ID 列表
    ready_for_new_goal: bool              # 是否有余力接受新 Goal
    suggested_maintenance_depth: int      # 建议 Goal Maintenance 检查深度
```

### §2.2 生成时机

每个 tick，step 2 (Attention Update) 末尾调用 `controller.emit_report()` 生成报告。
报告缓存在 `self._attention_report`，供 step 4/5/6 读取。

### §2.3 推荐逻辑（Recommendation Engine）

```
IF focus_state == FATIGUE:
    suppress_planning = True
    suggested_maintenance_depth = 1

IF interrupt_count_1m >= 3:
    suppress_planning = True
    # 频繁中断 → 不稳定期，不启动新计划

IF focus_state == FOCUSED AND current_focus_type == "GOAL":
    prioritize_goals = [current_focus_id]
    deprioritize_goals = [all other active goals]
    ready_for_new_goal = False

IF focus_state in (INTERRUPTED, SUSPENDED, RE_EVALUATION):
    suppress_planning = True
    # 过渡态不启动新计划

IF focus_state == IDLE:
    ready_for_new_goal = True
    suggested_maintenance_depth = max_active_goals
```

---

## §3 Attention → Goal Interaction ABI

### §3.1 权限边界

| 操作 | Attention 可做 | Goal System 可做 |
|------|:-:|:-:|
| 提醒 Goal 需要维护 | ✅ | — |
| 建议提升 Goal 上下文可用性 | ✅ | — |
| 建议延迟 Goal 检查 | ✅ | — |
| 建议抑制 Planning | ✅ | — |
| **创建 Goal** | ❌ | ✅ |
| **删除 Goal** | ❌ | ✅ |
| **修改 Goal priority** | ❌ | ✅ |
| **修改 Goal status** | ❌ | ✅ |
| **发起 Goal 执行** | ❌ | ✅ |

### §3.2 交互协议

```
Attention.emit_report()
    ↓
AttentionReport.recommendation
    ↓
Step 4: GoalMaintenance.read(report)
    ↓
    - 按 recommendation.prioritize_goals 排序维护顺序
    - recommendation.suggested_maintenance_depth 限制检查深度
    - 被 deprioritize 的 goals 跳过本次 tick
    ↓
Step 6: PlanningTrigger.check_gate(report)  ← 新增门控
    ↓
    - suppress_planning=True → 跳过所有 Planning
    - ready_for_new_goal=False → 只对当前焦点 Goal 分解
    - 否则正常流程
```

### §3.3 Attention-Planning Boundary（注意力-规划边界）

**Attention 对 Planning 的权限：**

| 操作 | Attention 可做 | Planning System 可做 |
|------|:-:|:-:|
| 建议 ALLOW_PLANNING | ✅ | — |
| 建议 DEFER_PLANNING | ✅ | — |
| 传递焦点 Goal ID | ✅ | — |
| **创建 Plan** | ❌ | ✅ |
| **修改 Plan** | ❌ | ✅ |
| **取消 Plan** | ❌ | ✅ |
| **修改 TaskDAG** | ❌ | ✅ |

最终链：

```
Attention
   │
   │ ALLOW_PLANNING / DEFER_PLANNING (signal)
   ↓
Planning Trigger
   │
   │ decision
   ↓
Planner → TaskDAG
```

Attention 不拥有 Planning 权。它只产生信号，Planning 层做出决策。

---

## §4 Goal Maintenance Tick v2

### §4.1 当前（Phase 34）

```python
def _tick_step_goal_maintenance(self):
    agent = self.agent
    if hasattr(agent, "goal_stack"):
        active = agent.goal_stack.get_active_count()
        return {"active_goals": active}
    return {"status": "no_goal_stack"}
```

**问题**：只统计数量，不做任何维护。

### §4.2 Phase 36 改造

```python
def _tick_step_goal_maintenance(self):
    report = self._attention_report
    if report is None:
        return {"step": 4, "status": "no_attention_report"}

    # 1. 读取活跃 Goal
    goals = self._goal_store.load_active() if self._goal_store else []

    # 2. 按 Attention 推荐排序
    prioritize = set(report.recommendation.prioritize_goals)
    deprioritize = set(report.recommendation.deprioritize_goals)

    ordered = []
    skipped = []
    for g in goals:
        if g.goal_id in deprioritize:
            skipped.append(g.goal_id)
            continue
        ordered.append(g)
    ordered.sort(key=lambda g: (g.goal_id in prioritize, g.priority), reverse=True)

    # 3. 限制深度
    depth = report.recommendation.suggested_maintenance_depth
    ordered = ordered[:max(depth, 1)]

    # 4. 逐条维护（check deadline / progress staleness / consistency）
    maintained = []
    for g in ordered:
        if self._goal_maintenance_check(g):
            maintained.append(g.goal_id)

    return {
        "step": 4,
        "name": "goal_maintenance",
        "active_total": len(goals),
        "maintained": len(maintained),
        "skipped_by_attention": len(skipped),
        "attention_depth": depth,
    }
```

---

## §5 Planning Trigger Gate（规划门控）

### §5.1 当前（Phase 34）

```python
def _tick_step_planning_trigger(self):
    for g in active:           # ← 遍历所有 PENDING goals
        if g.status == PENDING: # ← 没有任何门控条件
            decompose(g)        # ← 立即分解
```

### §5.2 Phase 36 改造：三条件门控

```
Plan = Goal.ready AND Attention.available AND Resource.available
```

| 条件 | 检查 | 来源 |
|------|------|------|
| Goal.ready | status == PENDING | GoalStore |
| Attention.available | NOT suppress_planning | AttentionReport.recommendation |
| Resource.available | 当前 active DAG count < MAX_CONCURRENT | Runtime state |

### §5.3 实现

```python
def _tick_step_planning_trigger(self):
    report = self._attention_report

    # Gate 1: Attention available
    if report and report.recommendation.suppress_planning:
        return {"step": 6, "name": "planning_trigger",
                "gated": True, "reason": "attention_suppress"}

    # Gate 2: Resource available (MAX_CONCURRENT_DAGS = 3)
    if self._active_dag_count >= 3:
        return {"step": 6, "name": "planning_trigger",
                "gated": True, "reason": "resource_saturated"}

    # Gate 3: Goal ready + attention-aware filtering
    goals = self._goal_store.load_active()
    pending = [g for g in goals if g.status.name == "PENDING"]

    # If focused on a goal, only decompose that one
    if report and report.current_focus_type == "GOAL" and not report.recommendation.ready_for_new_goal:
        pending = [g for g in pending if g.goal_id == report.current_focus_id]

    # Decompose at most 1 goal per tick
    for g in pending[:1]:
        decompose(g)

    return {
        "step": 6, "name": "planning_trigger",
        "pending_total": len(pending),
        "decomposed": 1 if pending else 0,
        "gated_by_attention": report.recommendation.suppress_planning if report else False,
    }
```

---

## §6 Execution Check v2

### §6.1 当前

只检查 controller 状态（blocked/stats）。

### §6.2 Phase 36 改造

增加 Attention-aware 执行检查。

**关键冻结**：`attention_block` 是 `ExecutionDecision`（allowed=false），不是任务状态变更。

禁止：
```
RUNNING → BLOCKED  ❌  Attention 不拥有执行状态权
```

正确：
```
ExecutionDecision: allowed=false, reason=ATTENTION_RESOURCE_UNAVAILABLE
```

**触发条件**：
- FATIGUE → ExecutionDecision(allowed=false)
- INTERRUPTED → ExecutionDecision(allowed=false)
- SUSPENDED → ExecutionDecision(allowed=false)

**不触发**：
- 不修改 Task 生命周期字段
- 不改变 Task.status
- 不改变 RUNNING→BLOCKED 状态

```python
def _tick_step_execution_check(self):
    report = self._attention_report
    attention_allowed = True
    attention_block_reason = ""

    if report:
        if report.fatigue > 0.9:
            attention_allowed = False
            attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"
        elif report.focus_state in ("INTERRUPTED", "SUSPENDED"):
            attention_allowed = False
            attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"

    # 原有检查
    controller = self.controller
    stats = controller.get_stats() if hasattr(controller, "get_stats") else {}
    blocked = controller.is_blocked() if hasattr(controller, "is_blocked") else False

    return {
        "step": 5,
        "name": "execution_check",
        "controller_blocked": blocked,
        "attention_allowed": attention_allowed,
        "attention_block_reason": attention_block_reason,
        "stats": stats,
    }
```

---

## §7 完整 Tick 流程图（Phase 36 后）

```
Tick
 │
 ├─ Step 1: Event Ingestion           → Events[]
 │
 ├─ Step 2: Attention Update          → AttentionReport [NEW]
 │    Event → Score → Decide          → AttentionDecision[]
 │    emit_report()                   → cached for steps 4/5/6
 │
 ├─ Step 3: WM Sync                   → WM allocations from decisions
 │
 ├─ Step 4: Goal Maintenance v2       [READS AttentionReport]
 │    prioritize / deprioritize / depth limit
 │
 ├─ Step 5: Execution Check v2        [READS AttentionReport]
 │    fatigue → block / suspended → block
 │
 ├─ Step 6: Planning Trigger v2       [READS AttentionReport]
 │    Gate: suppress | filter | resource
 │
 ├─ Step 7: Core Loop / Dispatch
 │
 ├─ Step 8: Result
 ├─ Step 9: Memory
 └─ Step 10: Learning
```

---

## §8 测试矩阵（10 场景）

| ID | 场景 | 预期 |
|----|------|------|
| EB-01 | Attention FATIGUED → suppress_planning=True | Planning Trigger 跳过 |
| EB-02 | Attention FOCUSED on Goal A → only Goal A gets maintenance | 其他 Goal deprioritized |
| EB-03 | Attention INTERRUPTED → suppress_planning=True | Execution 不推进 |
| EB-04 | 3+ interrupts in 1 min → suppress_planning=True | 不稳定期保护 |
| EB-05 | IDLE + multiple PENDING goals → ready_for_new_goal=True | 正常 Planning |
| EB-06 | AttentionReport None（无 Attention） → 降级到旧行为 | 不阻断 |
| EB-07 | Attention 不能修改 Goal priority | ABI 边界验证 |
| EB-08 | Attention 不能创建 Goal | 主权检查 |
| EB-09 | Planning Trigger 只对最多 1 个 Goal 分解 | 防止认知过载 |
| EB-10 | Execution Check 读取 fatigue > 0.9 → block | 执行保护 |

---

## §9 不变式

1. **Attention 只建议，不强制**：所有 recommendation 字段是纯建议，Goal/Planning/Execution 各自有权忽略。
2. **降级兼容**：如果 AttentionReport 为 None（Phase 35 未启用），所有步骤回退到 Phase 34 行为。
3. **单 Goal 分解 / Tick（Cognitive Serialization Constraint）**：
   不是硬性资源限制，而是当前 OCOS 单焦点认知模型的自然推导。
   未来 Phase 45 多焦点模型升级时，此约束可由焦点数动态推导。
4. **不新增模块**：Phase 36 只修改 Step 4/5/6 的现有方法，不创建新文件（除 ABI 定义）。

---

## §10 实施步骤

| 步骤 | 内容 | 改动范围 |
|------|------|---------|
| 36.1 | `AttentionReport` ABI → `ocos/contracts/` | 1 个新 dataclass |
| 36.2 | `CognitiveAttentionController.emit_report()` | attention.py +20 行 |
| 36.3 | Step 4 Goal Maintenance v2 | agent_runtime.py ~30 行 |
| 36.4 | Step 5 Execution Check v2 | agent_runtime.py ~15 行 |
| 36.5 | Step 6 Planning Trigger Gate | agent_runtime.py ~25 行 |
| 36.6 | Test Suite (10 scenarios) + import rules | 新测试文件 |
| 36.7 | Full Regression | 基线 1864+ |

---

## §11 完成标准

- [ ] `AttentionReport` 在每个 tick step 2 末尾生成
- [ ] Step 4 读取 report，按推荐排序 Goal 维护顺序
- [ ] Step 5 在 fatigue/suspended 时阻止执行推进
- [ ] Step 6 在 suppress_planning 时跳过 Planning
- [ ] Step 6 在 FOCUSED+GOAL 时只分解当前焦点 Goal
- [ ] 全量回归 1864+ 保持零失败
- [ ] import rules 新增 Phase 36 gate
- [ ] Attention 永不修改 Goal priority/status（ABI 边界测试通过）

---

*Phase 36 Freeze v0.2 — 2026-07-25 — APPROVED*
*下一步：用户确认后进入 Phase 36.1 实施*
