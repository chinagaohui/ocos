# Phase 9: Counterfactual Simulation ABI — v1.0 冻结

## North Star Compliance

**Q1 — Direction**: Enhances the user's cognition (what-if analysis tool).
**Q2 — Nature**: Adds **Information** and **Understanding** (impact reports, evidence). Adds zero Authority.
**Q3 — Removability**: Yes — `rm -rf simulation/` and Phase 0-8 runs unchanged (verified by Gate 7).

See: [North Star](../OCOS_NORTH_STAR.md), [Constitution](../ARCHITECTURE_CONSTITUTION.md)

## Phase 9.5 — Governance Documents

Concurrent with Phase 9, the following governance documents were created:

| Document | Purpose |
|----------|---------|
| `OCOS_NORTH_STAR.md` | Highest-level purpose and constraints |
| `ARCHITECTURE_CONSTITUTION.md` | Five immutable safety rules |
| `PHASE_MAP.md` | Complete capability map with completion estimates |
| `DRIFT_PREVENTION_CHECKLIST.md` | Phase entry review template |

These documents are **Phase-independent** — they govern all future Phases.

## 核心定位

Phase 9 是 OCOS 第一次从「**观察自身**」进入「**验证未来**」。

Phase 0-8 解决的是：

- 系统执行叙事（Phase 0-6）
- 系统运行运行时（Phase 7）
- 系统观察自身（Phase 8）

Phase 9 解决的是：

- 系统在沙盒中验证假设，不触碰现实

**核心定义：**

> Simulation explores possible futures, never creates actual futures.
> 模拟探索可能现实，但不产生真实现实。

> Sandbox is a place where possible states are explored, not a place where reality is changed.
> 沙盒是探索可能状态的容器，不是改变现实的地方。

## 架构定位

```
Phase 0–6: 系统执行叙事
Phase 7:    系统运行运行时
Phase 8:    系统观察自身
Phase 9:    系统模拟未来
       ↓
Gate 1:     ABI + Iron Rules 57-62 冻结 (done)
Gate 2:     Snapshot Provider (Reality → Snapshot 单向) (done)
Gate 3:     Sandbox Engine (假设注入) (done)
Gate 4:     Simulation Runner + Impact Projector (done)
Gate 5:     Governance Bridge (ImpactReport → EvolutionProposal) (done)
Gate 6:     Governance Integration + Decision Binding (done)
Gate 7:     Deletion Proof + Kernel Independence (done)
```

## 当前架构层级

```
Reality
  │ observation (ObservationView)
  ▼
SnapshotProvider
  │ project (RealityProjection)
  ▼
StateSnapshot
  │ hypothetical
  ▼
SandboxState
  │ simulate
  ▼
SimulationRunner
  │ measure diff
  ▼
SimulationResult
  │ project evidence
  ▼
ImpactProjector
  │ structure
  ▼
ImpactReport
  │ bridge (GovernanceBridge)
  ▼
EvolutionProposal (pending)
  │ review
  ▼
Governance
  │ event
  ▼
Decision
  │ commit (唯一 Reality 写入口)
  ▼
Reality
```

## 数据流

Phase 9 涉及两次 Governance 事件，语义不同：

- `approved_for_simulation` — 第一次审批：允许进行模拟
- `approved` / `rejected` — 第二次审批：基于模拟证据的最终决策

```
MetaEvolutionProposal
     │
     ▼
Governance Review (初审)
     │
     ├── rejected
     │     └── GovernanceReviewEvent(decision="rejected")
     │
     └── approved_for_simulation
           └── GovernanceReviewEvent(decision="approved_for_simulation")
                     │
                     ├──→ StateSnapshot (来自 Reality 的只读投影)
                     │         │
                     │         ▼
                     │    SandboxState (可丢弃计算空间)
                     │         │ add hypothesis
                     │         ▼
                     │    SimulationResult (observed diffs)
                     │         │
                     │         ▼
                     │    ImpactReport (结构化 diff 证据)
                     │         │
                     │         ▼
                     │    GovernanceBridge (边界转换)
                     │         │
                     │         ▼
                     │    EvolutionProposal (pending 提案)
                     │         │
                     │         ▼
                     │    Governance Final Review
                     │         │
                     │         ├── rejected
                     │         │     └── GovernanceReviewEvent(decision="rejected")
                     │         │
                     │         └── approved
                     │               └── GovernanceReviewEvent(decision="approved")
                     │
                     ▼
                Decision → Commit → Reality
```

**关键约束：**

- `approved_for_simulation` **不是** `approved`。前者批准的是**模拟请求**，后者批准的是**状态变更**。
- Simulation 是 Governance 可调用的证据工具，不是 Governance 的一部分。
- 两次 Governance 事件共用一个 `GovernanceReviewEvent` 类型，通过 `decision` 值区分语义。
- GovernanceBridge 是纯转换器，不做价值判断。`EvolutionProposal.proposed_change` 仅陈述事实差异，不含倾向性语言。

## 铁律 57-62

### 铁律 57 — Simulation observes possibilities, never reality.
Simulation 只能运行假设状态，不能对真实状态进行写操作。
禁止：写 Event Store、修改 Reality、修改 Decision State。

### 铁律 58 — Simulation State is isolated, never promoted.
模拟状态永远是沙盒状态，不可转移到 Reality。
禁止：`SimulationState → RealityState` 直接转换。
必须经过：`Simulation Result → Governance Event → Decision → Commit`。

### 铁律 59 — Simulation Result is evidence, never recommendation.
模拟结果只能作为证据，不能输出决策建议。
禁止：`recommended_action`、`best_solution`、`optimal_change`。
允许：`impact_projection`、`risk_observation`、`state_difference`。

### 铁律 60 — Snapshot observes state, never owns state.
快照描述状态的只读投影，不拥有状态。
禁止：`write`、`update`、`commit`、`execute`、`mutate`。

### 铁律 61 — Sandbox changes are hypothetical, never transferable.
沙盒变化是假设变化，不可转移到 Reality。
禁止：`promote`、`merge`、`sync`、`commit`。
允许：`add hypothesis`、`calculate diff`、`discard`。

### 铁律 62 — Simulation measures differences, never predicts truth.
模拟测量差异，不预测真相。
禁止：`prediction`、`confidence`、`recommendation`、`optimal`。

### 铁律 63 — Snapshot creation observes reality, never copies authority.
快照创建观察现实，不复制现实权限。
SnapshotProvider 只读观察 Reality，不得获得 Reality 的任何写权限。
禁止：`update()`、`restore()`、`rollback()`、`commit()`、`sync()`。

### 铁律 64 — Snapshot is a projection boundary, never a state boundary.
快照是投影边界，不是状态边界。
`StateSnapshot.state_projection` 是 `Mapping[str, object]` 只读投影，
不是 Reality 状态的副本。修改投影不影响 Reality。
禁止：`RealityState.copy()`、StateSnapshot 拥有可写状态引用。

### 铁律 65 — SnapshotProvider reads through observation interfaces, never internal state access.
SnapshotProvider 只能通过观察接口读取，不得访问 Reality 内部状态。
输入必须是 `ObservationView`（Simulation 层定义的观察接口），
不是 `EventStore`、`RealityStore`、`Database` 等内部接口。
禁止：`SnapshotProvider` 导入 `reality/`、`event_store/`、`database/` 模块。

### 铁律 66 — Sandbox contains hypotheses, never reality.
沙盒包含假设，不包含现实。
`SandboxState.state_projection` 中的值都是假设值，不是真实值。
禁止：`current_state`、`real_state`、`future_state` 字段名。
强制：字段命名统一为 `state_projection`（与 Snapshot 一致）。

### 铁律 67 — Sandbox mutations are isolated, never propagated.
沙盒变化只能存在于沙盒，不向外传播。
修改 SandboxState 不影响 StateSnapshot；销毁 SandboxState 不影响 Reality。
禁止：`promote()`、`merge()`、`sync()`、`commit()`、`restore()` 方法。

### 铁律 68 — Sandbox lifecycle ends with disposal, never promotion.
沙盒生命周期以销毁结束，不存在升级。
Sandbox 的唯一合法结束方式是 `dispose()`。
禁止：SandboxState → Reality 的任何直接路径。
必须经过：`Sandbox → SimulationResult → ImpactReport → Governance → Decision → Commit`。

### 铁律 69 — SandboxState is derived state, never authoritative state.
SandboxState 是派生状态，不是真实状态来源。
`SandboxState.state_projection` 中的值是对 `StateSnapshot.state_projection` 施加假设后的派生值。
修改 SandboxState 不影响 StateSnapshot，修改 StateSnapshot 不反向影响 SandboxState。
禁止：将 SandboxState.state_projection 视为权威状态。
强制：任何决策流程只能以 `StateSnapshot.state_projection`（来自 Reality 的只读投影）作为参考基准。

### 铁律 70 — Runner measures differences, never predicts outcomes.
SimulationRunner 测量假设投影与基态状态的差异，不预测未来。
禁止：`prediction`、`forecast`、`expected_result`、`recommendation`、`optimal`、`confidence`。
允许：`simulate`、`calculate`、`measure`、`compare`。

### 铁律 71 — Projector structures evidence, never recommends action.
ImpactProjector 将 SimulationResult 中的 diff 结构化输出为 ImpactReport，不推荐行动。
禁止：`recommend`、`assess`、`decide`、`approve`、`apply`、`risk_assessment`。
输出限制：`ImpactReport.observed_differences` 只含结构化证据（如 `observed_impacts`），不含 recommendation/risk/action。

### 铁律 72 — Simulation decomposition separates measurement from projection, never expands authority.
模拟分解将测量（Runner）与投影（Projector）分离，不扩大任何一侧的权限。
Runner 无权限预测；Projector 无权限推荐。
Runner 不可跳过 Projector 直接产生 ImpactReport；Projector 不可跳过 Runner 模拟输入。
禁止：Runner 输出 ImpactReport；Projector 接收 SandboxState。

### 铁律 73 — ImpactReport describes observed differences, never evaluates desirability.
ImpactReport 只描述观察到的差异，不评估其合意性。
禁止：`good` / `bad` / `acceptable` / `unacceptable` / `critical` 等价值判断字段。
允许：`resource_delta` / `state_change` / `observed_impacts` 等事实字段。
差异描述示例：`resource_loss=-20` -> 允许；`resource_loss=-20, severity=high` -> 禁止。

### 铁律 74 — Evidence cannot become instruction.
证据不能变成指令。
禁止 ImpactReport 包含 `recommendation` / `suggestion` / `proposed_action` / `next_step`。
禁止 ImpactProjector 输出 Decision 或任何具有执行语义的结构。
强制：Simulation 的输出流向 Governance，由 Governance 产生决策。

### 铁律 75 — Simulation evidence requires governance interpretation before decision.
模拟证据必须经过 Governance 解释后才能进入决策。
禁止 SimulationResult / ImpactReport 绕过 Governance 直接触发 Reality 变更。
禁止：`SimulationResult -> Decision`、`ImpactReport -> Decision` 的直接路径。
强制路由：`ImpactReport -> Governance -> Decision -> Reality`。

### 铁律 76 — Governance consumes proposals, never simulation state.
Governance 只读 EvolutionProposal，不读 SandboxState / SimulationResult / ImpactReport。
禁止 governance/ 导入 simulation/sandbox/、simulation/runner/、simulation/impact/。
禁止：Governance 直接访问 Simulation 内部状态。

### 铁律 77 — Approval exists as an event, never as proposal mutation.
批准语义由 GovernanceEvent.decision 承载，不在 EvolutionProposal.status 上堆叠。
禁止：proposal.status = "approved"；proposal.approved = True。
强制：Approval 始终以 GovernanceEvent(proposal_id=..., decision="approved") 形式存在。

### 铁律 78 — Governance produces decisions, never reality changes.
Governance 输出 GovernanceEvent，不直接修改 Reality。
禁止：approve_and_apply()、execute_proposal()、commit_change()。
强制路由：GovernanceEvent → Decision → Commit → Reality。

### 铁律 79 — Simulation is removable infrastructure, never a kernel dependency.
Simulation 是可删除的基础设施，不是 kernel 的依赖。
Phase 0-8 任何模块（contracts, cognition, reality, narrative 等）不得 import simulation、不得 type hint simulation 类型、不得字符串引用 simulation 模块路径。
禁止：`from opentale.app.simulation import ...`、类型注解含 `"SimulationResult"`、字符串常量含 `"opentale.app.simulation"`。
强制：删除 simulation/ 目录后，kernel 不需要任何改动就能启动。

### 铁律 80 — Reality mutation has one authorized path: Decision Commit.
Reality 写操作只有一个授权路径：Decision Commit。
禁止非 contracts/decision.py 之外的任何模块出现 Reality 写语义词汇（update/commit/write/apply/mutate/patch/replace/restore/merge/sync/persist/save）作为函数定义名、self.属性调用、或裸函数调用。
强制：Only Decision Commit Path may mutate Reality.

### 铁律 81 — Higher-level cognition must not create lower-level authority.
高层认知不产生低层权限。
Simulation 不能直接产生 Decision。正确路径：Simulation → Proposal → Governance → Decision → Reality。
禁止：simulation → decision 的直接依赖。simulation 输出经过 Governance 解释后才能进入决策路径。

---

## Gate 7 — 验证检查

以下验证由 `test_simulation_deletion_proof.py` 覆盖：

| 验证块 | 检查内容 | 测试数 |
|--------|----------|--------|
| A — Kernel Independence Rule | Phase 0-8 不得 import/引用 simulation 模块 | 4 tests |
| B — Reality Mutation Vocabulary | 禁止 zone 内不得出现写语义词汇 | 15 tests |
| C — Reverse Dependency | 单向依赖无逆流 | 9 tests |
| Combined | 可删除性 + 无 import simulation 契约 | 2 tests |

---

## Contract 定义

### StateSnapshot

```python
@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: UUID
    source_event_id: UUID            # 来源 Event ID（可追溯）
    captured_at: datetime            # 采集时间
    state_projection: Mapping[str, object]  # 状态投影（只读快照）
    included_domains: tuple[str, ...]       # 包含的领域列表
    metadata: Mapping[str, object] = {}     # 扩展元数据

    # 禁止字段: write / update / commit / execute / mutate
    # 禁止方法: save() / commit() / apply_changes()
```

### ObservationView（Gate 2 新增）

Simulation 层的观察接口，与 Phase 0-8 的 `Observation` 解耦。
SnapshotProvider 的输入必须是 ObservationView，不是 Reality 内部接口。

```python
@dataclass(frozen=True)
class ObservationView:
    event_id: UUID                   # 观察事件 ID
    timestamp: datetime              # 观察时间
    domains: Mapping[str, object]    # 领域状态映射
    schema_version: int = 1          # 观察 schema 版本
    metadata: Mapping[str, object] = field(default_factory=dict)

    # 禁止字段: store / database / repository / connection / session
    # 禁止: write / update / commit / save
```

### RealityProjection（Gate 2 新增）

Projector 的输出类型。Projection 是 `StateSnapshot.state_projection` 的直接来源。

```python
@dataclass(frozen=True)
class RealityProjection:
    domains: Mapping[str, object]            # 投影后的领域状态
    included_domains: tuple[str, ...]        # 包含的领域列表
    projection_timestamp: datetime           # 投影时间
    metadata: Mapping[str, object] = field(default_factory=dict)

    # 禁止字段: write / update / commit / save / restore
    # 禁止方法: write() / commit() / restore() / rollback()
```

### SnapshotProvider（Gate 2 新增）

```python
class SnapshotProvider:
    """只做一件事：ObservationView → StateSnapshot。"""

    def __init__(self, projector: Projector) -> None: ...
    def create(self, view: ObservationView) -> StateSnapshot: ...

    # 禁止方法: update() / restore() / rollback() / commit() / sync()
    # 禁止方法: write() / save() / execute() / merge() / promote() / apply()
```

### Projector（Gate 2 新增）

Projector 是纯变换函数接口：`ObservationView → RealityProjection`。
SnapshotProvider 内部调用 Projector 生成投影。

```python
class Projector(ABC):
    @abstractmethod
    def project(self, view: ObservationView) -> RealityProjection: ...

    # 禁止方法: update() / restore() / rollback() / commit() / sync()
    # 禁止方法: write() / save()
```

### DefaultProjector（Gate 2 内置实现）

```python
class DefaultProjector(Projector):
    """默认投影：ObservationView.domains 的直接映射。"""
    def project(self, view: ObservationView) -> RealityProjection:
        return RealityProjection(
            domains=dict(view.domains),           # 复制，非引用
            included_domains=tuple(sorted(view.domains.keys())),
            projection_timestamp=view.timestamp,
        )
```

### SandboxState（Gate 3 冻结）

```python
@dataclass(frozen=True)
class SandboxState:
    sandbox_id: UUID
    snapshot_id: UUID                  # 来源快照 ID（追踪基态）
    state_projection: Mapping[str, object]  # 假设状态投影（与 Snapshot 一致命名）
    hypothesis_id: UUID | None = None  # 关联的 Hypothesis ID
    created_at: datetime | None = None # 创建时间

    # 禁止字段: current_state / real_state / future_state
    # 禁止字段: promoted / merged / committed
    # 禁止方法: promote() / merge() / sync() / commit() / restore()
    # 允许方法: dispose()

    def dispose(self) -> None:
        """销毁沙盒状态（铁律 68）。"""
        pass
```

**关键命名规则：**
- 统一用 `state_projection`，不用 `current_state`、`real_state`、`future_state`
- `snapshot_id` 追踪源快照，确保可追溯

### SandboxEngine（Gate 3 新增）

```python
class SandboxEngine:
    """输入 StateSnapshot + Hypothesis → 输出 SandboxState。
    
    SandboxEngine 不读取 Reality，不写 Decision，不修改 Governance。
    """

    def create(self, snapshot: StateSnapshot, hypothesis: Mapping[str, object]) -> SandboxState: ...

    # 禁止方法: promote() / merge() / sync() / commit() / restore()
    # 禁止方法: write() / save() / execute() / apply()
    # 输入禁止: Reality / EventStore / Decision / Governance
    # 输出禁止: SimulationResult / ImpactReport / Decision
```

### SimulationRunner（Gate 4 新增）

```python
class SimulationRunner:
    """输入 SandboxState → 输出 SimulationResult。
    
    Runner 只测量 diff，不预测结果。
    铁律 70: Runner measures differences, never predicts outcomes.
    """

    def run(self, sandbox: SandboxState) -> SimulationResult: ...

    # 禁止方法: apply() / execute() / commit() / promote() / merge() / restore()
    # 禁止方法: predict() / recommend() / approve() / forecast()
    # 输入禁止: Reality / Decision / Governance / EventStore
    # 输出禁止: ImpactReport / Decision / Recommendation
```

### SimulationExecutionContext（Gate 4 内部隔离协议）

```python
@dataclass(frozen=True)
class SimulationExecutionContext:
    """Runner 内部隔离协议，不是跨层 ABI。
    
    确保 Runner 只有一个状态来源（SandboxState），
    不允许 Runner 访问 Reality/Decision/Governance。
    """
    sandbox_id: UUID
    hypothesis_id: UUID
    state_projection: Mapping[str, object]
    environment: Mapping[str, object] = {}
    metadata: Mapping[str, object] = {}

    # 禁止字段: reality_id / commit_id / decision_id / governance_id
    # 与 SimulationResult 的 sandbox_id / hypothesis_id 一致命名
```

### ImpactProjector（Gate 4 新增）

```python
class ImpactProjector:
    """输入 SimulationResult → 输出 ImpactReport。
    
    Projector 结构化 evidence，不推荐 action。
    铁律 71: Projector structures evidence, never recommends action.
    """

    def project(self, context: ImpactProjectionContext, result: SimulationResult) -> ImpactReport: ...

    # 禁止方法: assess() / recommend() / decide() / approve() / apply()
    # 禁止方法: assess_risk() / propose_action()
    # 输入禁止: SandboxState（只能通过 Context 间接访问 diff）
    # 输出禁止: Decision / Recommendation / RiskAssessment
```

### ImpactProjectionContext（Gate 4 内部隔离协议）

```python
@dataclass(frozen=True)
class ImpactProjectionContext:
    """Projector 内部隔离协议，限制解释范围。
    
    只允许访问 observed_diffs，不允许访问 result 内部状态。
    铁律 71: Projector structures evidence, never recommends action.
    """
    simulation_result_id: UUID
    observed_diffs: tuple[Diff, ...]
    metadata: Mapping[str, object] = {}

    # 禁止字段: approval / decision / action / recommendation / risk
```

**数据流：**

```
StateSnapshot + Hypothesis
         │
         ▼
  SandboxEngine.create()
         │
         ▼
  SandboxState.state_projection  ← 假设视角的状态
```

**禁止数据流：**

```
SandboxEngine → Reality              ✗
SandboxEngine → Decision             ✗
SandboxEngine → Governance           ✗
SandboxEngine → SimulationResult     ✗ (那是 Gate 4 的事)
```

### SimulationRequest

```python
@dataclass(frozen=True)
class SimulationRequest:
    request_id: UUID
    hypothesis_id: UUID              # 关联的 Proposal ID
    base_snapshot_id: UUID           # 基态快照 ID
    simulation_parameters: Mapping[str, object]  # 模拟参数
    created_at: datetime

    # 禁止字段: approved / rejected / execute / apply
```

### SimulationResult

```python
@dataclass(frozen=True)
class SimulationResult:
    result_id: UUID
    request_id: UUID                 # 关联的 SimulationRequest
    sandbox_id: UUID                 # 来源 Sandbox ID（溯源）
    hypothesis_id: UUID              # 关联的 Hypothesis ID（溯源）
    snapshot_id: UUID                # 使用的快照
    observed_diffs: tuple[Diff, ...]  # 观察到的状态差异列表
    uncertainty: str                 # 不确定性描述
    created_at: datetime

    # 禁止字段: prediction / confidence / recommendation / optimal / approved
    # 禁止字段: forecast / expected_result / best

@dataclass(frozen=True)
class Diff:
    path: tuple[str, ...]            # 差异路径
    before: object | None            # 变化前的值
    after: object | None             # 变化后的值
    metadata: Mapping[str, object] = {}
```

### ImpactReport

```python
@dataclass(frozen=True)
class ImpactReport:
    report_id: UUID
    simulation_result_id: UUID       # 关联的 SimulationResult
    before_state_reference: UUID     # 变化前状态引用
    after_state_reference: UUID      # 变化后状态引用
    observed_differences: Mapping[str, object]  # 结构化差异
    impact_signals: tuple[uuid.UUID, ...] = ()  # 影响信号列表
    created_at: datetime | None = None

    # 禁止字段: approved / rejected / recommended_action / apply
    # 禁止字段: decision / risk / recommendation / action
```

### EvolutionProposal（Gate 5 新增）

```python
@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: UUID
    evaluation_id: UUID               # 关联的 ImpactReport.report_id
    target_component: str             # 提案影响的目标组件
    proposed_change: str              # 仅描述事实差异，不含评价/建议
    expected_impact: str              # 仅描述预期的中性结果
    evidence_summary: str             # 证据摘要
    status: str = "pending"           # 仅限 "pending"（由 Governance 事件赋予）
    timestamp: datetime | None = None

    # 禁止字段: priority / severity / urgency / recommendation / approved
    # 禁止字段: execute / apply / commit / decision / action
    # proposed_change 禁止包含: "应该"/"应当"/"必须"/"建议"/"优化" 等价值判断
```

### GovernanceSimulationRequest（Gate 6 新增）

向 Governance 提交来自 Simulation 的提案，不包含执行语义。

```python
@dataclass(frozen=True)
class GovernanceSimulationRequest:
    """Simulation → Governance 的提案提交请求。"""
    proposal_id: UUID
    evidence_ids: tuple[UUID, ...]        # 关联的 ImpactReport.report_id
    created_at: datetime

    # 禁止字段: action / execute / apply / commit / mutation / force
    # 禁止字段: priority / severity / urgency / recommendation
```

### GovernanceDecisionRecord（Gate 6 新增）

Governance 决策记录，不是 Proposal 的状态变更。

```python
@dataclass(frozen=True)
class GovernanceDecisionRecord:
    """治理决策的记录，可溯源至特定的 GovernanceEvent。"""
    proposal_id: UUID
    decision: Literal["approved", "rejected"]
    event_id: UUID                        # 关联的 GovernanceReviewEvent.event_id
    source_event_id: UUID                 # 触发该决策的 GovernanceEvent ID（可追溯）
    created_at: datetime

    # 禁止字段: execute / apply / commit / mutate / force / action
```

### GovernanceReviewEvent（Phase 9 扩展）

Phase 8 的 `GovernanceReviewEvent.decision` 扩展为：

```python
# Phase 8: decision: Literal["approved", "rejected"]
# Phase 9: 增加 "approved_for_simulation" 以区分模拟审批与执行审批

GovernanceReviewEvent.decision: Literal[
    "approved",                    # 最终批准执行（Phase 8 原值）
    "rejected",                    # 拒绝（Phase 8 原值）
    "approved_for_simulation",     # 批准模拟（Phase 9 新增）
]
```

`"approved_for_simulation"` 的含义：**允许进行模拟，不等于批准执行。**
这是 Phase 9 新增的事件值，向后兼容 Phase 8（`"approved"` 和 `"rejected"` 语义不变）。

## Authority Separation Model

### Four-Level Separation Principle

Phase 9 的全链路具有四级隔离，缺一不可：

| 层级 | 对象 | 权限 | 铁律 |
|------|------|------|------|
| 0 — Evidence | ImpactReport | 描述差异事实 | 73 |
| 1 — Hypothesis | EvolutionProposal | 提出可能变化，状态为 pending | 74 |
| 2 — Approval | GovernanceEvent | 授权或拒绝，语义为事件而非属性 | 75 |
| 3 — Mutation | Decision + Commit | 唯一 Reality 写入口 | Invariant-001 |

**核心约束：**
- ImpactReport ≠ EvolutionProposal（证据不等同于提案）
- EvolutionProposal ≠ GovernanceDecision（提案不等同于批准）
- GovernanceDecision ≠ Approval State（批准是事件，不是对象属性）
- Approval Event ≠ Reality Mutation（批准不自动等于执行）

### Invariant-001 — No component except Decision layer may mutate Reality state.

这是 OCOS 从 Phase 0 到 Phase 9 的最高级不变量。

> 任何组件——无论是 Simulation、Governance、Meta、Observer、Reasoning——都无权直接修改 Reality。
> 所有修改必须通过以下路径：
> `Decision Resolution → Commit Event → Reality Mutation`
> 只有 `cognition/decision.py` 层拥有 Reality 写入口。

**违反示例：**
- `ImpactProjector → Reality` (禁止)
- `Governance → Reality` (禁止)
- `SimulationRunner → Reality` (禁止)
- `MetaProposalGenerator → Reality` (禁止)
- `Approval Event → 自动触发 Reality 变更` (禁止)

### Gate 6 边界约束（预冻结）

Gate 6（Governance Integration + Decision Binding）的语义边界：

**约束 1：Governance 不读取 Sandbox**

Governance 只通过 `EvolutionProposal` 接收经边界转换的证据。
禁止 Governance 直接访问 SandboxState、SimulationResult、ImpactReport 等模拟内部状态。

```
错误： GovernanceManager.evaluate(sandbox=SandboxState)
正确： GovernanceManager.review(proposal=EvolutionProposal)
```

禁止的 import 方向：`governance/` 不得导入 `simulation/sandbox/`、`simulation/runner/`、`simulation/impact/`。

**约束 2：Approval 是事件，不是状态**

Approval 的语义必须通过 `GovernanceEvent.decision` 承载，不得通过修改 `EvolutionProposal.status` 实现。

```
错误： proposal.status = "approved"
      if proposal.status == "approved": execute()

正确： GovernanceEvent(proposal_id=..., decision="approved")
```

`EvolutionProposal` 始终保持 frozen。批准是外部事件，不是内部状态转换。

**约束 3：Decision 是唯一 Reality 写入口**

Gate 6 完成后，Decision 仍然且始终是 Reality 的唯一变更入口。
禁止 Governance 绕过 Decision 直接写 Reality。
禁止 EvolutionProposal 包含 `execute` / `apply` / `commit` 等执行字段。

## Authority Boundary

### 权限矩阵

| 对象 | 拥有权力 | 无权力 |
|------|----------|--------|
| ObservationView | 描述观察到的状态 | 访问 Reality 内部 / 写操作 |
| RealityProjection | 描述 Reality 的投影 | 写/更新/提交/恢复 |
| Projector | 纯变换：ObservationView → RealityProjection | 修改输入/写状态/提交 |
| SnapshotProvider | 从 ObservationView 创建 StateSnapshot | 修改 Reality / 写 Event Store |
| StateSnapshot | 描述 Reality 的只读投影 | 拥有/修改/提交状态 |
| SandboxState | 承载假设投影 + 追踪假设来源 | 升级到 Reality / 持久化 |
| SandboxEngine | 从 StateSnapshot + Hypothesis 创建 SandboxState | 读 Reality / 写 Decision / 输出 SimulationResult |
| SimulationRequest | 请求模拟执行 | 自带批准/执行语义 |
| SimulationResult | 描述观察到的状态差异 | 预测/推荐/置信度/最优解 |
| ImpactReport | 结构化 diff 证据 | 建议/决策/执行/风险评价 |
| SimulationRunner | 测量 SandboxState 的假设 diff | 预测/推荐/审批/访问 Governance |
| SimulationExecutionContext | 封装 Runner 执行上下文 | 访问 Reality/Decision/Governance |
| ImpactProjector | 结构化 SimulationResult 为 ImpactReport | 推荐/决策/审批/访问 SandboxState |
| ImpactProjectionContext | 限制解释范围为 observed_diffs | 访问 result 内部状态/决策字段 |
| GovernanceBridge | 将 ImpactReport 转化为 EvolutionProposal | 添加倾向性/评价/指令/决策字段 |
| EvolutionProposal | 描述差异事实的 pending 提案 | 推荐/建议/审批/执行语义 |
| EvolutionProposal.proposed_change | 只描述事实差异值 | 包含价值判断/评价性语言/should 指令 |

### 两次 Governance 的权限区分

| 事件 | 含义 | 允许的后续操作 |
|------|------|----------------|
| `decision="approved_for_simulation"` | 批准模拟 | 创建 SimulationRequest → 运行沙盒 |
| `decision="approved"` | 批准执行 | 进入 Decision → Commit 流程 |
| `decision="rejected"` | 拒绝提案 | 关闭提案，无后续操作 |

### 关键约束

- Simulation 的所有输出都是 **evidence**，不是 **decision**。
- 状态提升路径唯一：`SimulationResult → Governance → GovernanceReviewEvent → Decision → Commit → Reality`。
- Sandbox 是 **disposable computational space**，不是 **temporary reality**。

## 测试契约（Test Contract）

Phase 9 是 OCOS 第一次引入状态投影（State Projection），这是所有 Phase 中**最容易出现隐式权限漂移**的地方。
测试契约的优先级高于业务测试。Gate 1 就必须冻结五类测试。

### 第一类：Identity 测试

验证每个对象**是什么**，而不是**做什么**。

每个 Contract 必须测试：

- **frozen 保证**：`dataclasses.frozen` 确认 `StateSnapshot`、`SimulationRequest`、`SimulationResult`、`ImpactReport` 为 frozen
- **禁止字段不存在**：`not hasattr(obj, "write")`、`not hasattr(obj, "commit")`、`not hasattr(obj, "execute")`、`not hasattr(obj, "mutate")`
- **只读投影确认**：`StateSnapshot.state_projection` 是 `Mapping[str, object]`，非可变 `dict`
- **可追溯性**：`StateSnapshot.source_event_id` 是 `UUID`，非 `str` 或 `None`
- **快照不是可写副本**：`StateSnapshot` 不包含 `save()`、`commit()`、`apply_changes()` 方法

### 第二类：Authority 测试

测试对象**无权力**的方法和字段。每个 Contract 一组独立测试类。

**TestSnapshotAuthority**
- `StateSnapshot` 无权：`mutate()`、`commit()`、`save()`、`execute()`
- `StateSnapshot` 字段不得包含：`write`、`update`、`commit`、`execute`、`mutate`
- 创建后不可修改

**TestSandboxAuthority**
- `SandboxState` 无权：`merge()`、`promote()`、`sync()`、`commit()`、`restore()`
- `SandboxState` 字段不得包含：`current_state`、`real_state`、`future_state`、`promoted`、`merged`、`committed`
- `SandboxState` 销毁后 `snapshot_id` 引用的 `StateSnapshot` 不受影响

**TestSandboxIsolation（Gate 3 新增）**
- 输入 Snapshot 的 projection 与 Sandbox 的 projection 独立
- 修改 Sandbox.projection 不影响 Snapshot
- Snapshot.projection 与 Sandbox.projection 指向不同对象（`is not`）
- Sandbox 无法访问 Reality

**TestSandboxEngineAuthority（Gate 3 新增）**
- `SandboxEngine` 无权：`promote()`、`merge()`、`sync()`、`commit()`、`restore()`、`write()`、`save()`、`execute()`、`apply()`
- `SandboxEngine.create()` 输入必须是 `StateSnapshot` + `Mapping[str, object]`
- `SandboxEngine.create()` 输出必须是 `SandboxState`（不是 Reality/Decision/Gov）
- AST 检查 SandboxEngine 不 import `reality/`、`decision/`、`governance/`、`event_store`

**TestSimulationResultAuthority**
- `SimulationResult` 无权：`predict()`、`recommend()`、`approve()`
- `SimulationResult` 字段不得包含：`prediction`、`confidence`、`recommendation`、`optimal`、`approved`
- `observed_diffs` 不可变（`tuple`）

**TestImpactReportAuthority**
- `ImpactReport` 无权：`apply()`、`execute()`、`commit()`
- `ImpactReport` 字段不得包含：`approved`、`rejected`、`recommended_action`、`apply`

### 第三类：Semantic 测试

延续 Phase 8 的模式——测试禁止词汇在 Contract 中不存在。

**禁止字段词汇：**
- `prediction` / `truth` / `best` / `optimal` / `correct` / `must`
- `apply` / `execute` / `rewrite` / `commit`
- `selected` / `approved` / `winner`

**禁止枚举值：**
- `decision` 字段值不能有新的权力语义（`approved_for_simulation` 不算权力语义——它只批准模拟，不批准执行）

**验证方式：**
- 所有 Contract 的 `fields()` 和 `dataclass_fields()` 遍历 + 词汇黑名单
- AST 检查 Contract 源码中禁止词汇的位置（排除 docstring 和注释）

### 第四类：Lifecycle 测试

验证 Simulation 对象的生命周期隔离。

- **Snapshot 可长期存在**：创建后经过任意操作，Snapshot 数据不变
- **Sandbox 必须可销毁**：SandboxState 的 `discard()` 不影响 Snapshot
- **Snapshot 不依赖 Sandbox**：Sandbox 销毁后，Snapshot 依旧可读
- **Snapshot ≠ Sandbox**：Snapshot 的 `state_projection` 不随 Sandbox 变化
- **生命周期路径**：`Reality → Snapshot → Sandbox → Discard` 每一步的状态隔离

### 第五类：Deletion Proof（Gate 1 前置）

不等 Gate 6。Gate 1 就写删除保证测试。

**test_simulation_not_required_by_kernel():**
- AST 扫描 `opentale/app/` 中除 `simulation/` 外的所有模块
- 验证没有模块 `import simulation` 或 `from simulation` 或 `from app.simulation`
- 验证 `LAYER_RULES` 中 simulation 规则不会在 simulation/ 不存在时导致测试失败

**Phase 9 Gate 1 原则：**
> Simulation 是最外层。从第一天起它就是 Optional Layer。

## 删除保证

删除 `opentale/app/simulation/`（Gate 2+ 实现）后，系统回退到 Phase 8 行为：

- `contracts/simulation.py`（StateSnapshot / SandboxState / SimulationRequest / SimulationResult / ImpactReport）→ 作为普通 Contract 保留
- 测试中 AST 边界检查跳过不存在的 `simulation/` 目录
- 无任何 Phase 0–8 模块依赖 Simulation 层
- 全量回归测试保持 905+ passed（Gate 1 测试中 simulation 相关测试自然跳过）

**核心保证：** Simulation 是验证增强层，不是内核依赖。

## ABX 演进规则

1. **冻结前可调**：v1.0 冻结过程中，允许为收紧边界重命名字段（如 `diff` → `observed_diffs`）。公开冻结后只增不删。
2. **只买不借**：Simulation Contract 不得 import 任何 Phase 0–8 业务模块。
3. **向下兼容**：冻结后新增字段必须有 `= None` 默认值。
4. **测试即文档**：每个禁止字段必须有对应的 `not hasattr()` 断言。
5. **沙盒隔离优先**：任何允许模拟域访问现实域的 API，必须有明确的只读标志。

## Gate 结构

| Gate | 模块 | 覆盖范围 | 预计测试数 | 状态 |
|------|------|----------|-----------|------|
| 1 | ABI + 铁律 57-62 | Contract frozen、权限边界、AST 检查、测试契约 | ~66 | done |
| 2 | Snapshot Provider | ObservationView、RealityProjection、Projector、SnapshotProvider 冻结 | ~63 | done |
| 3 | Sandbox Engine | SandboxState、SandboxEngine、假设注入、隔离保证 | ~90 | done |
| 4 | Simulation Runner + Impact Projector | Runner diff 生成、Projector 证据结构化、铁律 70-72 | ~96 | done |
| 5 | Governance Bridge | ImpactReport → EvolutionProposal、铁律 73-75、四级隔离 | ~11 | done |
| 6 | Governance Integration + Decision Binding | 三条预冻结约束验证、Invariant-001 | pending |

## 完整认知循环

Phase 9 完成后，OCOS 形成完整的认知循环：

```
过去:   Experience 记录发生事实
现在:   Reality    当前状态
规律:   Pattern / Principle 提炼规律
推理:   Reasoning  生成可能路径
假设:   MetaEvolutionProposal 提出演化假设
模拟:   Simulation 验证假设影响    ← Phase 9
治理:   Governance 审批决策
行动:   Decision → Commit → Reality
再感知: Observer → ...           ← Phase 8
```

所有路径最终汇聚到 **Decision**。

`Decision` 是唯一改变点。Phase 9 验证的是：连 "模拟的未来" 也不能绕过 Decision。

## 权限闭环验证

Phase 9 的权限链形成完整单向管道：

```
Reality
  │ snapshot (只读)
  ▼
StateSnapshot
  │ hypothetical (沙盒)
  ▼
SandboxState
  │ observe diff (只读)
  ▼
SimulationResult
  │ evidence (证据)
  ▼
ImpactReport
  │ bridge (边界转换)
  ▼
EvolutionProposal (pending)
  │ submit (提交)
  ▼
Governance
  │ event (事件)
  ▼
Decision
  │ commit (唯一改变点)
  ▼
Reality
```

每一步的输出类型决定了下一步的权限范围：

| 步骤 | 输出类型 | 下游能做什么 |
|------|----------|-------------|
| Snapshot | 只读投影 | 复制到沙盒，不可写回 |
| Sandbox | 假设状态 | 计算 diff 后丢弃 |
| Simulation | diff 证据 | 提交为 ImpactReport |
| ImpactReport | 结构化报告 | 转换为 EvolutionProposal |
| EvolutionProposal | pending 提案 | 提交给 Governance 参考 |
| Governance | 事件 | 触发 Decision 或拒绝 |
| Decision | 决议 | Commit 到 Reality |

**铁律 57-62 的实际效果：** Simulation 链路上没有一个对象能写 Reality。

## 合规基线

Gate 1-4 冻结后测试基线：
| - Phase 0-8 回归：905 passed, 2 skipped, 1 xpassed
| - Phase 9 Gate 1 ABI 测试：66 passed
| - Phase 9 Gate 2 Snapshot Provider 测试：63 passed
| - Phase 9 Gate 3 Sandbox Engine 测试：90 passed
| - Phase 9 Gate 4 Runner + Projector 测试：96 passed（runner 42 + impact 45 + layer 9）
| - Phase 9 Gate 5 Governance Bridge 测试：11 passed（bridge 9 + layer 2）
| - 全量 kernel 测试：1167 passed, 1 xpassed
| - 删除保证：Phase 0-8 不变
| - 架构规则：LAYER_RULES 覆盖 simulation/ 全部子模块（sandbox/、runner/、impact/、governance_bridge/）

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-20 | 初版冻结 — Gate 1 ABI + 铁律 57-62 + 测试契约 |
| v1.0 | 2026-07-20 | Gate 2 冻结 — SnapshotProvider + Projector + ObservationView + RealityProjection + 铁律 63-65 |
| v1.0 | 2026-07-20 | Gate 3 design freeze — SandboxState + SandboxEngine + 铁律 66-68 + 7-Gate 扩展 |
| v1.0 | 2026-07-20 | Gate 3 implementation done — SandboxState 迁移到 sandbox/state.py、SandboxEngine、铁律 69、90 测试 |
| v1.0 | 2026-07-21 | Gate 4 implementation done — SimulationRunner + ImpactProjector、铁律 70-72、96 测试、全量 1156 passed |
| v1.0 | 2026-07-21 | Gate 5 implementation done — GovernanceBridge + EvolutionProposal、铁律 73-75、四级隔离公理、Invariant-001、Gate 6 三约束预冻结、全量 1167 passed |
