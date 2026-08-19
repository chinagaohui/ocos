# Phase 8: Self-Observation ABI — v1.1 冻结

## 核心定位

Phase 8 是 OCOS 第一次从「**改造世界**」进入「**观察自身**」。
系统不再只是驱动叙事和适应演化，而是形成自我观察能力。

Meta 层是整个系统的**内窥镜**：

- 只观察，不判断
- 只聚合，不诊断
- 只提案，不执行

## 架构定位

```
Phase 0–6: 系统执行叙事
Phase 7:    系统运行运行时
|Phase 8:    系统观察自身
     ↓
Gate 1:     Contracts ABI Freeze
Gate 2:     Meta Observer
Gate 3:     Meta Evaluator ✅
Gate 4:     Proposal Generator ✅
Gate 5:     Governance Boundary (当前)
```

## 数据流

```
[各层运行时]
     │ 产生 Signal
     ▼
MetaSignal ──→ HealthReport ──→ MetaEvolutionProposal
 观察个体        聚合多维           演化假设
     │             │                  │
  信号级         报告级             假设级
     │             │                  │
     └─────────────┴──────────────────┘
               GovernanceAdapter
                     │ submit
                     ▼
          GovernanceReviewRequest
                     │
          GovernanceManager
            ├── approve → GovernanceReviewEvent(decision="approved")
            └── reject  → GovernanceReviewEvent(decision="rejected")
                     │
                     ▼
               (Approved Record)
                     │
                     ▼
            Adaptation Domain
```

## 铁律 44–46

**铁律 44 — MetaSignal describes what happened, never what to do.**
MetaSignal 禁止携带任何判断/建议/决策：无 `decision`，无 `action`，无 `solution`，无 `severity`，无 `recommendation`，无 `fix`。

**铁律 45 — HealthReport aggregates, never diagnoses.**
HealthReport 只聚合信号为多维健康视图，不输出诊断结论：无 `diagnosis`，无 `action`。

**铁律 46 — EvolutionProposal proposes, never executes.**
EvolutionProposal 只提出改进方向，不包含执行指令：无 `apply`，无 `execute`，无 `modify`，无 `delete`，无 `migration`，无 `command`。

**铁律 47 — Evaluator interprets signals, never modifies reality.**
Evaluator 可以解释信号组合，但不能修改 Contract、Runtime、Pipeline 或触发 Repair。

**铁律 48 — HealthReport describes condition, never assigns blame.**
HealthReport 的 observed_dimensions 和 observed_patterns 禁止评价性表述：无 `healthy`/`unhealthy`/`bad`/`wrong`/`fault`/`blame`。

**铁律 49 — Evaluation is evidence-backed, never intuitive.**
HealthReport 必须引用 `source_signal_ids`，不能凭空生成判断。

**铁律 50 — Meta projection has no normative meaning.**
任何 Meta 输出（score / dimension / pattern）均不得直接代表"好"或"坏"、"正确"或"错误"、"优化目标"。

---

**铁律 51 — Meta Proposal describes observed evolution opportunities, never prescribes changes.**
Meta Proposal 描述观察到的演化机会，不规定修改方案。
允许：`target_area="contract_evolution"`、`rationale="dependency_edges increased"`
禁止：`required_change="rewrite_runtime"`、`action="refactor_dependency"`

**铁律 52 — Proposal Generator transforms evidence, never invents observation domains.**
Generator 只能转换已有证据（HealthReport → MetaEvolutionProposal），不得创造新的观察领域。
`target_area` 必须来自健康报告的 `observed_dimensions` keys，不可自创。

**铁律 53 — Meta Proposal contains no execution semantics.**
Meta Proposal 不包含任何执行语义。
禁止字段：`action`、`execute`、`apply`、`modify`、`priority`、`recommendation`
禁止方法：`execute()`、`apply()`、`commit()`

---

**铁律 54 — Governance reviews proposals, never executes observations.**
Governance 可接收 MetaProposal、记录审查结果、生成治理事件。
不能：把 Proposal 当执行指令、直接修改 Kernel、直接调用 Adaptation。

**铁律 55 — MetaProposal requires governance authorization, never direct evolution.**
MetaProposal 状态永远不能表达 `approved=True`；批准不是 Proposal 的属性。
Proposal 始终只是 Observation Artifact。

**铁律 56 — Approval is a governance event, not a property of proposal.**
批准属于 Governance 历史，而不是 Proposal 数据。正确模型：
`MetaProposal + GovernanceEvent`，而非 `MetaProposal(approved=True)`。
批准对应的应是对应 `GovernanceReviewEvent` 记录，而非 Proposal 自身字段。

## 六个 Contract 的字段定义

### MetaSignal

```python
@dataclass(frozen=True)
class MetaSignal:
    signal_id: UUID
    source_layer: str           # 来源层标识
    metric_name: str            # 指标名称
    value: float                # 指标值
    timestamp: datetime         # 采集时间
    metadata: Mapping[str, object]  # 扩展信息
    schema_version: int = 1

    # 禁止字段: decision / action / solution / severity / recommendation / fix
```

### HealthReport

```python
@dataclass(frozen=True)
class HealthReport:
    report_id: UUID
    signal_ids: tuple[UUID, ...]              # 关联信号列表
    observed_dimensions: Mapping[str, float]    # 投影维度 (dimension → 投影值)
    observed_patterns: tuple[str, ...]          # 观察到的模式
    timestamp: datetime                         # 报告生成时间
    schema_version: int = 1

    # 禁止字段: diagnosis / action / recommendation
```

### MetaEvolutionProposal (Phase 8 — v1.0)

```python
ObservedSignalIntensity = Literal[
    "intensity_below_threshold",
    "intensity_above_threshold",
    "intensity_significant",
]

TargetArea = Literal[
    "contract_evolution",      # ← contract_condition
    "test_surface_health",     # ← test_condition
    "structural_integrity",    # ← structural_condition
]

@dataclass(frozen=True)
class MetaEvolutionProposal:
    schema_version: int = 1
    proposal_id: UUID
    source_report_id: UUID                              # 来源 HealthReport
    source_signal_ids: tuple[UUID, ...]                  # 原始信号追溯
    target_area: TargetArea                              # 被观察到的变化领域
    observed_signal_intensity: ObservedSignalIntensity   # 信号强度（非优先级）
    rationale: str                                       # 基于 evidence 的事实描述
    metadata: Mapping[str, object]                       # 扩展元数据
    created_at: datetime                                 # 创建时间

    # 禁止字段: action / execute / apply / modify / priority / recommendation
```

### GovernanceReviewRequest (Phase 8 — Gate 5)

```python
@dataclass(frozen=True)
class GovernanceReviewRequest:
    request_id: UUID
    proposal_id: UUID
    source_report_id: UUID
    created_at: datetime
    proposal_summary: str = ""

    # 禁止方法: execute() / apply() / mutate() / adapt()
```

### GovernanceReviewEvent (Phase 8 — Gate 5)

```python
@dataclass(frozen=True)
class GovernanceReviewEvent:
    event_id: UUID
    proposal_id: UUID
    decision: Literal["approved", "rejected"]
    reason: str = ""
    created_at: datetime
```

**注意：** `"approved"` 字符串出现在这里是因为它属于 Governance Domain，不是 Meta Domain。
`GovernanceReviewEvent` 是治理事件，不是 Proposal 属性。
MetaEvolutionProposal 本身仍然不包含 `approved` 字段。

### Phase 6 EvolutionProposal（保持不变）

Phase 6 的 EvolutionProposal（`evolution/domain/evolution_proposal.py`）不受影响：

```python
@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: UUID           # Phase 6 治理 Proposal
    evaluation_id: UUID         # 评估 ID
    target_component: str       # 目标组件（治理语境）
    ...
```

## Authority Boundary

|| 对象 | 拥有权力 | 无权力 |
||------|----------|--------|
|| MetaSignal | 记录客观事实 | 判断/建议/修复 |
|| HealthReport | 投影信号 + 描述模式 | 诊断/评分/推荐/归咎 |
|| MetaEvaluator | 聚合信号到维度 | 修改内核/诊断系统/产生命令 |
| MetaProposalGenerator | 转换 HealthReport → MetaEvolutionProposal | 创造领域/读取 Runtime/访问 Governance |
| MetaEvolutionProposal | 描述演化假设 + 证据追溯 | 执行/审批自身/表达优先级 |
| MetaGovernanceAdapter | 提交 MetaProposal → GovernanceReviewRequest | 执行/变异/适应/绕过 Governance 直接输出决议 |
| GovernanceManager | 审批/拒绝提案, 输出 GovernanceReviewEvent | 修改 Contract（只改状态表）, 读取 Meta 内部 |
|| 后续 Observer | 拉取 + 查看 | 修改内核状态 |

**关键约束：** GovernanceManager 只认 `proposal_id`。Proposal 不携带生命周期状态；状态属于 Governance。MetaEvolutionProposal 的 `observed_signal_intensity` 描述的是信号幅度，不是行动优先级。

## 删除字段对比（Phase 8 Gate 4 vs Phase 6 EvolutionProposal）

| 字段 | Phase 6 | Phase 8 Gate 4 | 删除原因 |
|------|---------|----------------|----------|
| `risk_level` | ✔ | — | 隐含价值排序 → 改为 `observed_signal_intensity` |
| `priority` | 可选 | — | 治理越权 |
| `recommended_action` | ✔ | — | 变成 Decision |
| `execution_plan` | 可选 | — | 变成 Capability |
| `expected_improvement` | 可选 | — | 预测性判断 |
| `owner` | 可选 | — | 治理职责泄漏 |
| `status` | ✔ | — | Governance 状态污染 |

## 删除保证

删除 `opentale/app/meta/`（Gate 2+ 实现）后，系统回退到 Phase 7 行为：

- `contracts/meta_signal.py` / `health_report.py` / `evolution_proposal.py` → 作为普通 Contract 保留
- 测试中 AST 边界检查跳过不存在的 `meta/` 目录
- 无任何 Phase 0–7 模块依赖 Meta 层
- 全量回归测试保持 720+ passed（Gate 1 测试中 meta_boundary 测试自然跳过）

## ABX 演进规则

1. **冻结前可调**：v1.0 → v1.1 过程中，允许为收紧边界重命名字段（`health_dimensions` → `observed_dimensions`）。公开冻结后只增不删。
2. **只买不借**：Meta Contract 不得 import 任何 Phase 0–7 业务模块
3. **向下兼容**：冻结后新增字段必须有 `= None` 默认值
4. **测试即文档**：每个禁止字段必须有对应的 `not hasattr()` 断言

## 测试覆盖

| 测试文件 | 覆盖范围 | 数量 |
|----------|----------|------|
| `test_meta_signal_contract.py` | frozen、字段类型、禁止字段、默认值 | 14 |
| `test_health_report_contract.py` | frozen、多维聚合、禁止字段 | 12 |
| `test_evolution_proposal_contract.py` | frozen、证据追溯、禁止字段 | 13 |
| `test_meta_boundary.py` | AST 隔离检查（不 import 内核模块） | 4* |
| `test_evolution_proposal_boundary.py` | Gate 1 边界验证 + 类型注解 | 6 |
| `test_meta_observer.py` | Gate 2: Observer 只读 + 不分析 + 边界 | 14 |
| `test_meta_evaluator.py` | Gate 3: 投影/只读/模式/语义边界/中立性/AST | 22 |
| `test_architecture_rules.py` | LAYER_RULES 覆盖 meta/observer + meta/evaluator + meta/proposal_generator | — |
| `test_meta_governance_boundary.py` | Gate 5: Contract frozen/Adapter 边界/AST 检查/删除保证 | ~20 |

_* 4 个测试在 `meta/` 目录不存在时自然跳过（预期行为）_

合规状态: **36 (Gate 1) + 14 (Gate 2) + 22 (Gate 3) + 38 (Gate 4) + ~20 (Gate 5)** · 可删除保证: 684+ passed

## Gate 2 完成 — Meta Observer (v1.0)

| 文件 | 说明 |
|------|------|
| `meta/observer.py` | `MetaObserver` — 只读 Kernel → `tuple[MetaSignal, ...]` |
| `meta/__init__.py` | Package init |
| `tests/kernel/test_meta_observer.py` | 14 个测试：基础/只读/无分析/边界 |

### Observer 接口

```python
class MetaObserver:
    def observe(self, context: ObserverContext) -> tuple[MetaSignal, ...]: ...
```

### ObserverContext 输入结构

```python
@dataclass(frozen=True)
class ObserverContext:
    contract_count: int = 0
    contract_change_frequency: int = 0
    test_total: int = 0
    test_failure_count: int = 0
    test_skip_count: int = 0
    test_xpassed_count: int = 0
    layer_count: int = 0
    dependency_edge_count: int = 0
    boundary_violation_count: int = 0
    extra: Mapping[str, float]
```

### 数据来源

| 来源 | 指标 |
|------|------|
| Contract Registry | `contract_count` |
| Test Runtime | `test_failure_rate` |
| Architecture Metadata | `layer_count`, `dependency_edge_count`, `boundary_violation_count` |
| Extra (可扩展) | 任意 `metric_name → value` |

### Gate 2 完成标准

- [x] Observer 只读 Kernel（Context 纯输入，不变异）
- [x] 输出 `tuple[MetaSignal, ...]`
- [x] 不产生判断（metric_name 禁止 analysis 类词汇）
- [x] 不修改状态（Observer 无 write-like 方法）
- [x] 不依赖 Governance（AST 检查）

## Gate 3 完成 — Meta Evaluator (v1.1)

| 文件 | 说明 |
|------|------|
| `meta/evaluator.py` | `MetaEvaluator` — 投影 Signal → `HealthReport`（无评分/无诊断） |
| `tests/kernel/test_meta_evaluator.py` | 22 个测试：投影/只读/模式/语义边界/中立性/AST |

### Evaluator 接口

```python
class MetaEvaluator:
    def evaluate(self, signals: tuple[MetaSignal, ...]) -> HealthReport: ...
```

### Projection 公式

Evaluator 将信号分组为三个维度空间投影：

| 维度 | 输入信号 | 投影公式 | 范围 |
|------|----------|----------|------|
| `contract_condition` | `contract_count` + `change_frequency` | `max(0, 1 - change_freq / 10)` | [0, 1] |
| `test_condition` | `test_failure_rate` + `skipped/total` | `(1 - failure_rate) * 0.7 + (1 - skip_rate) * 0.3` | [0, 1] |
| `structural_condition` | `dependency_edge_count` + `boundary_violation_count` | `1 - (dep/100 + viol/10) / 2` | [0, 1] |

### 模式识别

| 模式名 | 触发条件 |
|--------|----------|
| `no_contract_changes_observed` | `change_frequency == 0` |
| `contract_changes_observed` | `change_frequency > 0` |
| `failure_rate_below_threshold` | `failure_rate < 0.05` |
| `failure_rate_above_threshold` | `failure_rate >= 0.05` |
| `skip_rate_below_threshold` | `skip_rate < 0.10` |
| `skip_rate_above_threshold` | `skip_rate >= 0.10` |
| `zero_boundary_violation_observed` | `violation_count == 0` |
| `boundary_violations_observed` | `violation_count > 0` |
| `dependency_edges_above_threshold` | `dep_edge_count > 30` |

### v1.0 → v1.1 变更

| 字段 | v1.0 | v1.1 |
|------|------|------|
| `HealthReport.health_dimensions` | ✔ | → `observed_dimensions` |
| `HealthReport.observed_dimensions` | — | 新增，语义改为"投影值"非"健康评分" |
| 铁律 47-50 | — | 新增：Evaluator 只读 / 不归咎 / 可追溯 / 无规范含义 |

### Gate 3 完成标准

- [x] Evaluator 只做 projection，不产生评分（observed_dimensions 中无 health 前缀）
- [x] 模式名只描述事实（`no_contract_changes_observed`），不做价值判断
- [x] 输入 `tuple[MetaSignal]`，输出 `HealthReport`（无额外对象）
- [x] 不修改输入信号（只读）
- [x] 不诊断 / 不推荐 / 不归咎（语义边界检查）
- [x] 极端对立输入不产生命令式输出（中立性检查）
- [x] AST 级别禁止 import governance/runtime/observer
- [x] 删除保证：`rm -rf meta/` 后 Phase 7 测试保持 684+ passed

## Gate 4 ABI 冻结 — Meta Proposal Generator (v1.0)

### 文件

| 文件 | 说明 |
|------|------|
| `meta/contracts/evolution_proposal.py` | `MetaEvolutionProposal` Contract (v1.0) + TypeAlias |
| `meta/proposal_generator.py` | `MetaProposalGenerator` — 转换 HealthReport → Proposal |
| `tests/kernel/test_meta_proposal_generator.py` | 预计 ~18 个测试：Contract/Generator/Boundary/Semantic/Removal |

### Generator 接口

```python
class MetaProposalGenerator:
    def generate(
        self, report: HealthReport
    ) -> tuple[MetaEvolutionProposal, ...]: ...
```

### 行为约束

| 允许 | 禁止 |
|------|------|
| 输入 HealthReport → 输出 tuple[MetaEvolutionProposal] | 读取 Governance / Runtime / Decision |
| 根据 `observed_dimensions` 选择 `target_area` | 自创观察领域 |
| 根据原始信号值确定 `observed_signal_intensity` | 计算优先级或风险等级 |
| `rationale` 引用信号模式名 | `rationale` 包含行动指令 |

### Dimension → TargetArea 映射

```
observed_dimensions key       TargetArea
──────────────────────        ─────────────────
contract_condition            contract_evolution
test_condition                test_surface_health
structural_condition          structural_integrity
```

Generator 不得产生不在上表中的 `target_area`。

### Signal intensity 计算规则

| 条件 | intensity |
|------|-----------|
| 所有维度 ≥ 0.8 | `intensity_below_threshold` |
| 任一维度 < 0.8 | `intensity_above_threshold` |
| 两个及以上维度 < 0.6, 或任一维度 < 0.3 | `intensity_significant` |

### Gate 4 完成标准

- [x] `MetaEvolutionProposal` frozen、字段类型正确、禁止字段检查通过
- [x] Generator 只接受 HealthReport，输出 `tuple[MetaEvolutionProposal, ...]`
- [x] `target_area` 冻结枚举，禁止自创
- [x] `observed_signal_intensity` 根据阈值计算，不表达优先级
- [x] 没有 `action` / `execute` / `apply` / `modify` / `priority` / `recommendation` 字段
- [x] no-import governance/runtime AST 检查
- [x] `rationale` 不包含 imperative 动词（fix / change / replace / remove / rewrite / apply）
- [x] 删除保证：`rm -rf meta/` 后 Phase 7 测试保持 684+ passed

### v1.0 冻结变更摘要

| 类别 | 变更 |
|------|------|
| 新增铁律 51-53 | Meta Proposal 描述演化机会 / Generator 不创造领域 / 无执行语义 |
| 新增 Contract | `MetaEvolutionProposal`（v1.0），与 Phase 6 `EvolutionProposal` 分离 |
| 新增文件 | `meta/contracts/evolution_proposal.py`、`meta/proposal_generator.py` |
|| 类型系统 | `ObservedSignalIntensity`、`TargetArea` 两个 Literal TypeAlias |
|| 删除字段 | `risk_level`、`priority`、`recommended_action`、`execution_plan`、`expected_improvement`、`owner`、`status` |

## Gate 5 ABI 冻结 — Governance Boundary (v1.0)

### 文件

| 文件 | 说明 |
|------|------|
| `meta/contracts/governance_review.py` | `GovernanceReviewRequest` + `GovernanceReviewEvent` Contract |
| `meta/governance_adapter.py` | `MetaGovernanceAdapter` — 提交 Proposa → GovernanceReviewRequest → 返回 Event |
| `tests/kernel/test_meta_governance_boundary.py` | 预计 ~20 个测试：Contract/Adapter/Boundary/Semantic/Removal |

### 核心设计原则

```
MetaObservation Domain
         │
         ▼
  MetaEvolutionProposal
         │
         ▼
  Governance Boundary
    ├── Approve Event
    └── Reject Event
         │
         ▼ (仅 Approved 后)
  Adaptation Domain
```

**禁止快捷路径：** `MetaProposal → Adaptation`

### MetaGovernanceAdapter 接口

```python
class MetaGovernanceAdapter:
    def submit(self, proposal: MetaEvolutionProposal) -> GovernanceReviewRequest: ...

    def review(
        self, request: GovernanceReviewRequest, decision: Literal["approved", "rejected"],
    ) -> GovernanceReviewEvent: ...

    def get_event(self, proposal_id: UUID) -> Optional[GovernanceReviewEvent]: ...
```

### 行为约束

| 允许 | 禁止 |
|------|------|
| 创建 GovernanceReviewRequest | execute() / apply() / mutate() / adapt() |
| 记录审批结果 (approve/reject) | 在 MetaEvolutionProposal 上设置 approved 字段 |
| 返回 GovernanceReviewEvent | 绕过 Governance 直接调度 Adaptation |
| 根据 proposal_id 查询历史 | 读取 Meta Observer/Evaluator/Generator 内部 |

## 测试基线

```
Gate 1 专门测试:         36 passed
Gate 2 Observer 测试:    14 passed
Gate 3 Evaluator 测试:   22 passed
Gate 4 Proposal 测试:    38 passed
Gate 5 Governance 测试:   ~20 passed (待实现)
全量回归测试 (不含 e2e):  870 passed, 1 xpassed, 18 skipped
相比 Gate 4 前:          +0 tests (Gate 5 实现后更新基线)
```

## 关联 ADR

- `adr-005` — Adaptation Governance Boundary
- `adr-006` — Phase 8 Self-Observation Architecture (待编写)
