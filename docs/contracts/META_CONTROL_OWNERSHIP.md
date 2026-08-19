# Meta Control Ownership (Phase15.6)

> **Frozen**: 2026-07-23
> **Certified By**: Hermes Agent — Phase15.5 Runtime Certification ✅
> **Prerequisite**: Phase15.0–Phase15.5 all frozen (735 tests + 147 audit checks)

---

## Meta Control ── Four Ownership Questions

### Q1: Meta Control 可以决定什么？

Meta Control 是 Control Plane 的顶层协调层，负责以下七类决策：

| # | Decision | Scope |
|---|----------|-------|
| 1 | **Cross-signal conflict resolution** | 当来自不同 Principle 的 ControlSignal 相互矛盾时（如 Principle-A 要求快节奏、Principle-B 要求停顿），Meta Control 裁决优先顺序 |
| 2 | **Budget rebalancing** | 当全局性资源限制（total allocations per tick、timeout pool）被多个 ExecutionPlan 竞争时，Meta Control 调整分配方案 |
| 3 | **Global policy enforcement** | 执行跨 Domain 的架构级规则（如"所有 Domain 都必须在启动前注册"、"不允许未定义的 ControlDomain"） |
| 4 | **Signal priority ordering** | 定义基础优先级映射：哪些 ControlDomain 在冲突时优先（如 `narrative_pacing` vs `character_consistency`） |
| 5 | **Escalation decision** | 当 Director 无法仲裁（冲突不可消解）时，Meta Control 决定是否升级为架构级异常 |
| 6 | **Meta-level event logging** | 记录所有跨域决策和策略变更到 Signal Registry（用于审计和回溯） |
| 7 | **Policy freeze / unfreeze** | 决定哪些全局性策略在特定 Volume 或 Session 中被冻结或解冻 |

**核心原则**：Meta Control 管理的是 **政策层面的冲突和策略**，而非单次 ExecutionPlan 的仲裁。

---

### Q2: Meta Control 绝对不能决定什么？

| # | Forbidden Decision | Rationale |
|---|-------------------|-----------|
| 1 | ❌ **生成任何形式的文本** | 违反 Control Plane 的根本定位——Control Plane 不生产内容 |
| 2 | ❌ **评估叙事质量** | 质量评估是 Quality Gate 的职责，但 Meta Control 不得自设质量评判标准 |
| 3 | ❌ **修改单个 ExecutionPlan** | ExecutionPlan 是 Director 的产出，Meta Control 只调整全局策略，不修改具体计划 |
| 4 | ❌ **创建具体的 ControlSignal** | 信号由 Principle→Signal Mapping 层产生，Meta Control 不介入信号生成 |
| 5 | ❌ **修改 Registry 条目** | Registry（Pattern / Principle / Knowledge）写操作属于 Knowledge Plane 的权限 |
| 6 | ❌ **干预 Runtime 执行细节** | Scheduler、Queue、Ticket 生命周期等属于 Runtime Orchestrator 的权限 |
| 7 | ❌ **逐 Plan 仲裁** | Per-Plan 的仲裁是 Director 的职责（Phase15.3），Meta Control 不接手 |
| 8 | ❌ **调用 LLM / 模型 API** | 任何模型调用都会污染 Control Plane 的确定性契约 |
| 9 | ❌ **生成或修改 Narrative State** | Runtime 拥有 Narrative State Zero 原则（Runtime owns no narrative state） |
| 10 | ❌ **绕过 Quality Gate** | 任何 ExecutionPlan 都必须经过 Quality Gate 验证，Meta Control 不能颁发豁免 |

---

### Q3: Meta Control 的输入来自哪里？

```
┌─────────────────────────────────────────────────┐
│                    Input Sources                 │
├─────────────────────────────────────────────────┤
│                                                   │
│  ①  Director Arbitration Log                     │
│     └─ 不可消解的 ControlSignal 冲突               │
│     └─ 超出 Budget 的 Allocation 请求              │
│                                                   │
│  ②  Quality Gate Violation Report                 │
│     └─ 重复性/系统性违规（非一次性）                 │
│     └─ 架构性违规（跨 Plan 模式）                   │
│                                                   │
│  ③  Signal Registry Query                         │
│     └─ 当前活跃信号集合                             │
│     └─ 历史冲突模式信号                             │
│                                                   │
│  ④  Global Policy Configuration                   │
│     └─ 当前会话级/Volume 级策略参数                 │
│     └─ 冻结/解冻标记                                │
│                                                   │
│  ⑤  Orchestrator Resource Report                  │
│     └─ 资源使用趋势（超时率、重试率、队列深度）        │
│                                                   │
└─────────────────────────────────────────────────┘
```

**输入接口契约**：

```python
@dataclass(frozen=True)
class MetaControlInput:
    conflicts: tuple[SignalConflict, ...]        # From Director
    violations: tuple[QualityGateViolation, ...]  # From Quality Gate (systemic only)
    active_signals: tuple[ControlSignal, ...]     # From Signal Registry
    policy_config: GlobalPolicyConfig             # Session-level policy parameters
    resource_report: ResourceReport | None        # From Orchestrator (optional)
```

---

### Q4: Meta Control 的输出去向哪里？

```
┌─────────────────────────────────────────────────┐
│                   Output Destinations            │
├─────────────────────────────────────────────────┤
│                                                   │
│  ① → Director                                    │
│     └─ PolicyOverride: 覆盖冲突优先级              │
│     └─ BudgetAdjustment: 调整全局分配上限           │
│                                                   │
│  ② → Quality Gate                                 │
│     └─ PolicyRule: 新增/修改策略验证规则            │
│     └─ FreezeDirective: 锁定/解锁某策略            │
│                                                   │
│  ③ → Signal Registry                              │
│     └─ MetaEvent: 策略变更记录（仅追加）            │
│     └─ AuditLog: 跨域裁决日志                      │
│                                                   │
│  ④ → Runtime Orchestrator                         │
│     └─ ResourceConstraint: 全局资源约束更新         │
│                                                   │
└─────────────────────────────────────────────────┘
```

**输出接口契约**：

```python
@dataclass(frozen=True)
class MetaControlOutput:
    policy_overrides: tuple[PolicyOverride, ...]      # → Director
    policy_rules: tuple[PolicyRule, ...]              # → Quality Gate
    meta_events: tuple[MetaEvent, ...]                # → Signal Registry (append-only)
    resource_constraints: ResourceConstraint | None   # → Orchestrator (optional)
```

---

## §0 — Position in Architecture

### Four-Layer Architecture (Emerged)

```
┌──────────────────────────────────┐
│  Knowledge Plane (Phase14)       │  ← 知道什么
│  Pattern Discovery · Principle   │     Patterns、Principles、Registry
│  Registry                         │
├──────────────────────────────────┤
│  Control Plane (Phase15)         │  ← 决定做什么
│  Meta Control · Director         │     Signals、Policy、Coordination
│  Quality Gate · Signal           │
├──────────────────────────────────┤
│  Runtime Plane (Phase15.5)       │  ← 执行决定
│  Scheduler · Adapter · Recovery  │     Scheduling、Invocation、Recovery
│  Validation                      │
├──────────────────────────────────┤
│  Execution Plane (OpenTale)      │  ← 真正生成内容
│  Narrative Generation            │     Text、Characters、Plot
└──────────────────────────────────┘
```

**Decision chain (never bypassable):**

```
Meta Control ──► Director ──► ExecutionPlan ──► Runtime ──► OpenTale
  Policy           Plan              Plan             Execute       Generate
```

Each layer is a pure decision funnel: narrower scope, higher specificity.

### Control Plane Architecture Detail
Cognitive Plane (Phase14)
  Pattern Discovery · Principle Registry
       │
       ▼  Principle Constraints
Mapping Layer (Phase14.5)
  Principle ──► ControlSignal
       │
       ▼  ControlSignal Stream
  ╔══════════════════════════════════════════════╗
  ║          Control Plane (Phase15)             ║
  ║                                              ║
  ║  ┌──────────┐    ┌─────────────┐            ║
  ║  │ Director │◄───│ Quality Gate│            ║
  ║  │ (15.3)   │    │ (15.4)      │            ║
  ║  └────┬─────┘    └──────┬──────┘            ║
  ║       │                 │                   ║
  ║       ▼                 ▼                   ║
  ║  ┌────────────────────────────────────┐     ║
  ║  │      Meta Control (Phase15.6)      │     ║
  ║  │  ┌─────────────────────────────┐   │     ║
  ║  │  │ Policy Conflict Resolver    │   │     ║
  ║  │  │ Budget Rebalancer           │   │     ║
  ║  │  │ Escalation Manager          │   │     ║
  ║  │  │ Meta Event Logger           │   │     ║
  ║  │  └─────────────────────────────┘   │     ║
  ║  └────────────────────────────────────┘     ║
  ║              │                              ║
  ║              ▼ Policy Signals               ║
  ║  ┌────────────────────────────────────┐     ║
  ║  │     Runtime Orchestrator (15.5)    │     ║
  ║  │     Scheduler · Adapter · Recovery │     ║
  ║  └─────────────┬──────────────────────┘     ║
  ╚══════════════════╤═══════════════════════════╝
                     │ AdaptedConstraint
                     ▼
             OpenTale Runtime
```

## §1 — Ownership Matrix

| Operation | Meta Control | Director | Quality Gate | Orchestrator |
|-----------|:-----------:|:--------:|:------------:|:------------:|
| **Cross-signal conflict resolution** | ✅ | ❌ | ❌ | ❌ |
| **Per-plan arbitration** | ❌ | ✅ | ❌ | ❌ |
| **Budget rebalancing** | ✅ | ❌ | ❌ | ✅ (per-ticket) |
| **Policy rule creation** | ✅ | ❌ | ❌ | ❌ |
| **Execution verification** | ❌ | ❌ | ✅ | ❌ |
| **Generate ExecutionPlan** | ❌ | ✅ | ❌ | ❌ |
| **Registry write** | ❌ | ❌ | ❌ | ❌ |
| **Signal creation** | ❌ | ✅ (via Mapping) | ❌ | ❌ |
| **Content generation** | ❌ | ❌ | ❌ | ❌ |
| **Runtime lifecycle** | ❌ | ❌ | ❌ | ✅ |
| **Invoke Runtime/Adapter/Scheduler/Recovery** | ❌ | ❌ | ❌ | ✅ |
| **Invoke Quality Gate / Director** | ❌ | ❌ (self) | ❌ (self) | ❌ |

## §2 — Data Flow Contract

### 2.1 — Input Validation

Meta Control 的所有输入必须经过 **结构性校验**（非 Quality Gate——即前置校验）：

- `conflicts` 列表中的每个 SignalConflict 必须包含两个冲突的 signal_id 和冲突类型
- `violations` 列表拒绝单次性违规——只有系统性/重复性违规可以提交
- `policy_config` 必须包含当前会话的所有已定义策略值

### 2.2 — Output Purity

Meta Control 的输出必须是 **纯函数式的**：

- 相同的输入 → 相同的输出（确定性）
- 输出不可变（所有输出类型为 frozen dataclass）
- 无副作用（不修改自身之外的状态）

### 2.3 — Append-Only Logging

Meta Control 的所有决策必须记录到 Signal Registry：

- 每条 meta_event 包含：event_id, timestamp, decision_type, input_summary, output_summary
- 事件是不可变的（追加写入，不支持删除或修改）
- 审计回溯由此日志保证

## §3 — Boundary Rules (Frozen)

### §3.1 — Meta Control ↔ Director

| Rule | Direction | Enforcement |
|------|-----------|-------------|
| Meta Control 接收 Director 无法消解的冲突 | Director → Meta | Director's conflict has `requires_meta=True` flag |
| Meta Control 返回 PolicyOverride | Meta → Director | Override 包含明确的优先级映射，不修改 ExecutionPlan |
| Director 不得绕过 Meta 直接执行冲突 Plan | Director → Execution | Quality Gate 检查 Plan 中是否有关联的未解决冲突 |

### §3.2 — Meta Control ↔ Quality Gate

| Rule | Direction | Enforcement |
|------|-----------|-------------|
| Quality Gate 上报系统性违规给 Meta Control | QG → Meta | QG 的 violation report 带 `systemic=True` 标记 |
| Meta Control 返回 PolicyRule | Meta → QG | PolicyRule 变更后，QG 在下一次验证中生效 |
| Meta Control 不得干预 QG 的逐 Plan 验证结果 | Meta → ✗ | QG 的验证裁决是最终决定 |

### §3.3 — Meta Control ↔ Runtime Orchestrator

| Rule | Direction | Enforcement |
|------|-----------|-------------|
| Meta Control 仅发送全局资源约束 | Meta → Runtime | 不涉及单个 Ticket 或 Session |
| Orchestrator 不得请求 Meta Control 介入每次调度 | Runtime → Meta | 无接口暴露单向调用 |

### §3.4 — Meta Control ↔ Signal Registry

| Rule | Enforcement |
|------|-------------|
| Meta Control 只读查询活跃信号 | `active_signals` 从 Registry 的只读副本获取 |
| Meta Control 只追加写入事件 | Registry 拒绝任何非追加操作 |
| Meta Control 不得修改已有事件 | 事件不可变性由 Registry 保证 |

### §3.5 — Meta Control Never Executes

Meta Control 是一个纯粹的 **协调器（Coordinator）**，不是执行器（Executor）。

**可以 (Allowed):**
- emit Policy / PolicyOverride
- emit MetaEvent / AuditLog
- emit BudgetAdjustment / ResourceConstraint
- emit PolicyRule / FreezeDirective

**绝对不可以 (Forbidden):**

| # | Forbidden | Why |
|---|-----------|-----|
| 1 | ❌ **invoke Adapter** | Adapter 调用属于 Runtime Plane, 绕过 Runtime Orchestrator 即破坏分层 |
| 2 | ❌ **invoke Runtime** | 直接操作 Runtime 实例等同于绕过 Scheduler 生命周期 |
| 3 | ❌ **invoke Scheduler** | Scheduler 是 Runtime Orchestrator 内部组件, Meta Control 不拥有调度权 |
| 4 | ❌ **invoke Recovery** | Recovery 只在 Runtime 层触发, Meta Control 不介入单次恢复流程 |
| 5 | ❌ **invoke Quality Gate** | Quality Gate 是独立验证器, Meta Control 可以发 PolicyRule 但不能调用它 |
| 6 | ❌ **invoke Director** | Director 接收 PolicyOverride 作为输入, 但不是被 "调用" 的——它是自主仲裁 |
| 7 | ❌ **invoke OpenTale** | 任何直接接触 Execution Plane 的行为都会越过整个 Control+Runtime 栈 |

**执行必须经过的路径（永不绕过）：**

```
Meta Control ──► Director ──► ExecutionPlan ──► Runtime ──► OpenTale
     │
     ├── emit Policy → Director reads on next Plan
     ├── emit MetaEvent → Signal Registry (append)
     ├── emit PolicyRule → Quality Gate reads on next verify
     └── emit ResourceConstraint → Orchestra reads on next schedule
```

**理性：** 防止 Meta Control 演变成"超级 Runtime"。如果 Meta Control 获得了执行能力，它就同时拥有了"决定做什么"和"直接执行"的权力——这正是 Runtime 架构漂移的根源。Meta Control 必须保持纯协调器身份，所有实际操作必须经过 Director → ExecutionPlan → Runtime → OpenTale 这条完整的决策链。

## §4 — Verification Protocol

| Check | Method | Frequency |
|-------|--------|-----------|
| **Input purity** | Meta Control 不调用外部模型/API | Per Freeze Audit |
| **Output determinism** | 相同输入 → 相同输出的测试覆盖率 | Per Phase commit |
| **No content generation** | 源代码 AST 扫描：无文本生成调用 | Per Freeze Audit |
| **No state mutation** | 所有输出类型为 frozen dataclass | Per Freeze Audit |
| **Never executes** | 源代码 AST 扫描：无 Adapter/Runtime/Scheduler/Recovery/QG/OpenTale 调用 | Per Freeze Audit |
| **Append-only logging** | Registry 拒绝 UPDATE/DELETE 的防御性测试 | Per Phase commit |
| **Boundary isolation** | 无反向调用（Director→Meta 的单向依赖） | Per Freeze Audit |

## §5 — Changelog

| Date | Change | Approver |
|------|--------|----------|
| 2026-07-23 | Initial freeze — Phase15.6 Meta Control Ownership | Freeze Audit (Phase15.5 Certification) |
