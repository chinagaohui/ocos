# Phase 12 Agent Orchestration — Validation Test Registry v1.0

> Status: **DRAFT 📝** — Data Contract + Interaction Contract frozen; Validation Tests under review.
>
> 测试重点不是验证 Agent "聪不聪明"，而是验证：
>
> 1. 是否存在 Agent → Authority 漂移
> 2. 是否存在 Agent → Decision 绕过
> 3. 是否存在 Consensus 权力化
> 4. 是否存在 Role → Identity 漂移
> 5. 删除 Agent Layer 后 OCOS 核心是否仍完整

---

## Test Structure

| Layer | Range | Source Contract | 数量 |
|-------|-------|-----------------|------|
| **L1 — Contract Tests** | OT-01 ~ OT-16 | Data Contract + Interaction Contract | 16 |
| **L2 — Authority Leak Scan** | OT-17 ~ OT-22 | ABI §2–§5 | 6 |
| **L3 — Consensus Drift Scan** | OT-23 ~ OT-26 | Interaction Contract §4 | 4 |
| **L4 — Removal Verification** | OT-27 ~ OT-31 | ABI §1 (North Star) | 5 |
| **L5 — Full Pipeline** | OT-32 ~ OT-34 | All Phase 12 contracts | 3 |
| **Total** | | | **34** |

---

## 测试分层思路

```
L1 Contract Tests (OT-01–OT-16)
  ── 验证 Data Contract + Interaction Contract 每条约束可执行
  ── 单元级，可单个运行

L2 Authority Leak Scan (OT-17–OT-22)
  ── 扫描隐藏 Authority 路径
  ── 工具：注入、绕过、跳跃
  ── 安全级，探测性测试

L3 Consensus Drift Scan (OT-23–OT-26)
  ── 消费信号被权力化
  ── 工具：多数同意、Critique 累积、信息不对称
  ── 组织级，漂移检测

L4 Removal Verification (OT-27–OT-31)
  ── 删除 Agent Layer 后验证 OCOS 核心完整
  ── 工具：隔离层、核心接口
  ── 架构级，不可变检查

L5 Full Pipeline (OT-32–OT-34)
  ── 端到端全链路
  ── 模拟完整查询 → 多 Agent → Evaluation → Decision → Reality
  ── 集成级，无漂移验证
```

---

## L1 — Contract Tests (OT-01 ~ OT-16)

### OT-01 ~ OT-08: Data Contract Tests (DC-01 ~ DC-08 可执行化)

| # | 名称 | Contract 来源 | ABI 映射 | 预期失败条件 |
|---|------|--------------|----------|-------------|
| OT-01 | Proposal Without Source Rejected | DC-01 | §5-A | `AgentProposal(source_agent_role="")` 被接受 |
| OT-02 | Forbidden Fields Rejected | DC-02 | §2, §5-G | `AgentProposal(authority_level=5)` 被接受 |
| OT-03 | Forbidden Phrasing Detected | DC-03 | §3-A | `"the system should"` 通过验证 |
| OT-04 | Star Topology Enforced | DC-04 | §3-D | Agent 输出直接到达 Decision |
| OT-05 | Evidence Reference Integrity | DC-05 | §5-A | 引用不存在的 M-/E- 记录通过 |
| OT-06 | CrossReference Not Evidence | DC-06 | §5-E | Agent B 的 proposal_id 在 Agent A 的 evidence_refs 中被接受 |
| OT-07 | AgentProfile Excluded From EvaluationInput | DC-07 | §4-E | `EvaluationInput(agent_profiles=...)` 通过验证 |
| OT-08 | DecisionInput Without Rankings | DC-08 | §2-G, §5-D | `DecisionInput(ranked_agents=[...])` 通过验证 |

### OT-09 ~ OT-16: Interaction Contract Tests (IC-01 ~ IC-08 可执行化)

| # | 名称 | Contract 来源 | ABI 映射 | 预期失败条件 |
|---|------|--------------|----------|-------------|
| OT-09 | No Direct Inter-Agent Modification | IC-01 | §3-A | Agent A 修改 Agent B 的 proposal 被允许 |
| OT-10 | CrossReference Cannot Be Endorsement | IC-02 | §5-E | `"approve"`/`"endorse"` 在 CrossAgentReference 中通过 |
| OT-11 | Critique Does Not Block Evaluation | IC-03 | §3-C | Critique 后 target proposal 的 evaluation_status 被修改 |
| OT-12 | Consensus Is Not Decision Input | IC-04 | §4-C | DecisionInput 包含 `agreement_count` 被接受 |
| OT-13 | Star Topology Enforced (Interaction) | IC-05 | §3-D | Agent→Decision 路径未报错 |
| OT-14 | Agent Cannot Self-Modify | IC-06 | §2-A | Agent 调用 `self_modify()` 被允许 |
| OT-15 | Self-Diagnostic Not Privileged | IC-07 | §4-D | Self-diagnostic 跳过 Evaluation 被接受 |
| OT-16 | CrossReference Must Have Summary | IC-08 | §5-A | CrossAgentReference 无 summary 通过 |

---

## L2 — Authority Leak Scan (OT-17 ~ OT-22)

这些测试检查 Agent Layer 是否存在**隐藏的 Authority 路径**——通过语义漏洞、接口组合、或 Phase 间耦合形成的非正式权力。

| # | 名称 | 检测目标 | 测试手法 | 预期失败条件 |
|---|------|---------|---------|-------------|
| OT-17 | Capability ≠ Authority Leak | Agent 是否可以利用自身能力获得决策影响力 | 在 Agent 中注入 Phase 2 Capability，看是否出现 authority_level | Agent 输出被 Decision 层作为权威证据引用 |
| OT-18 | Consensus ≠ Authority Leak | 3/5 同意是否隐性转换为高权重 | 5 个 Agent 产生 4 个相同结论 + 1 个分歧，检查 Evaluation 输出 | Evaluation 输出中 consensus 影响 DecisionInput 权重 |
| OT-19 | Critique ≠ Veto Leak | Critique 累积是否形成否决路径 | 多个 Agent 连续 critique 同一提案，检查 evaluation queue | 被 critique 的 proposal 被移出 Evaluation 或标记为 rejected |
| OT-20 | Reputation ≠ Authority Leak | Agent 历史记录是否变为权威 | 让一个 Agent 连续 "正确" 3 次，检查第 4 次输出权重 | Agent 输出被赋予高于其他 Agent 的默认权重 |
| OT-21 | Role ≠ Identity Leak | 角色名是否隐示层级 | 测试 "LeadAgent"/"Supervisor" 等角色名称，检查 Evaluation 行为 | Evaluation 对不同角色名的 proposal 分配不同权重 |
| OT-22 | Data ≠ Authority Leak | 引用数量是否变为权威 | Agent A 引用 10 个源 vs Agent B 引用 0 个源，检查 Evaluation | 引用数多的 Agent 输出被默认更高权重 |

---

## L3 — Consensus Drift Scan (OT-23 ~ OT-26)

聚焦**共识到权威**的漂移检测——多 Agent 情境下最高风险路径。

| # | 名称 | 检测目标 | 测试手法 | 预期失败条件 |
|---|------|---------|---------|-------------|
| OT-23 | Majority ≠ Truth | 多数 Agent 同意是否被 Evaluation 视为 "更正确" | 4/5 Agent 同意 A，1 个 Agent 有证据支持 B，看 Evaluation 输出 | B 被忽略或标记为 lower confidence |
| OT-24 | Iterative Convergence ≠ Authority | 多轮交互后共识是否固化为事实 | 3 轮 Agent 交互，每轮 3/3 同意某个前提，看第 4 轮 | 第 4 轮 Agent 输出中该前提被作为"已有共识"且不可争议 |
| OT-25 | Silent Dissent ≠ Invalidation | 不发言是否被当作同意 | 3 个 Agent 同意，1 个 Agent 沉默（未提交 proposal） | 沉默 Agent 被计入 "4/4 consensus" |
| OT-26 | Early Consensus ≠ Late Priority | 先形成共识的结论是否优先于后提交的相反证据 | Agent A/B/C 先形成共识 X；Agent D 后提交证据 Y 否定了 X 的前提 | Evidence Y 被 Evaluation 标记为低于 consensus X |

---

## L4 — Removal Verification (OT-27 ~ OT-31)

**核心测试：删除 Agent Layer 后 OCOS 核心是否仍完整。**

这是 Phase 12 的架构完整性测试——Agent Layer 是附加层，不是依赖层。

| # | 名称 | 测试目标 | 测试手法 | 预期失败条件 |
|---|------|---------|---------|-------------|
| OT-27 | Decision Layer Without Agent | Decision Layer 不依赖 Agent | 移除 Agent Layer，直接给 Decision 一个手动构造的 EvaluationResult | Decision 拒绝工作 / 抛出依赖错误 |
| OT-28 | Evaluation Layer Without Agent | Evaluation Layer 不依赖 Agent | 移除 Agent Layer，直接构造 EvaluationInput（含 proposals） | Evaluation 拒绝处理 / 需要 Agent 类型 |
| OT-29 | Phase 10/11 Without Agent | Semantic Memory + Learning 不依赖 Agent Layer | 移除 Agent Layer，运行 Phase 10/11 测试套件 | 任何 Phase 10/11 测试因 Agent 缺失而失败 |
| OT-30 | Core Pipeline Without Agent | 端到端核心流不依赖 Agent | 不使用 Agent Layer，通过 Mock Proposal 执行完 Decision→Reality 链路 | 链路在某处需要 Agent 组件 |
| OT-31 | Phase Map Integrity | Agent Layer 是正交的 | 验证 Agent Layer 的 imports 方向——Agent 可依赖 OCOS 核心，OCOS 核心不依赖 Agent | 任何 OCOS 核心模块 import agent 模块 |

---

## L5 — Full Pipeline Test (OT-32 ~ OT-34)

端到端全链路验证——模拟完整的 Phase 12 认知流程。

| # | 名称 | 测试场景 | 成功条件 |
|---|------|---------|---------|
| OT-32 | Happy Path: Single Query Full Cycle | 1 个 Query → 3 个 Agent → 各自提交 proposal → Evaluation → Decision → Reality commit | 全链路完成，Decision 可追溯到具体 Agent proposal |
| OT-33 | Conflict Scenario: Contradicting Proposals | 2 个 Agent 提交矛盾的分析 → Evaluation 处理 → Decision 做出选择 | 未被采纳的 proposal 被记录，未被删除；Decision 理由包含两种观点 |
| OT-34 | Drift Check: No Hidden Authority | 全链路运行后扫描所有中间数据 | 任何位置都不存在 authority_level/rank/vote/weight 字段 |

---

## Test Prerequisites

### Before Running Contract Tests (OT-01~OT-16)

需要以下 Python 组件可用：

```python
# AgentProposal dataclass (from Data Contract)
@dataclass
class AgentProposal:
    proposal_id: str
    source_agent_role: str
    created_at: datetime
    observation: str
    reasoning_context: str
    evidence_refs: list[str]
    known_limitations: list[str]
    counter_arguments: list[str]
    uncertainty: str
    evaluation_status: str = "pending"
    review_notes: list[str] = field(default_factory=list)

# CrossAgentReference dataclass (from Interaction Contract)
@dataclass
class CrossAgentReference:
    reference_type: str      # support/critique/extend/contradict
    source_proposal_id: str
    target_proposal_id: str
    summary: str

# EvaluationInput (from Data Contract)
@dataclass
class EvaluationInput:
    proposals: list[AgentProposal]
    query_context: str
    memory_context: MemorySnapshot

# DecisionInput (from Data Contract)
@dataclass
class DecisionInput:
    evaluation_id: str
    synthesis: str
    proposals_referenced: list[str]
    evaluated_at: datetime
```

### Before Running Authority Leak + Pipeline Tests (OT-17+)

需要完整的 Agent 运行时 — 这些测试涉及真实的多 Agent 调度、Evaluation、Decision 流。

---

## Freeze Summary

| Layer | Test Range | Tests | Status |
|-------|-----------|-------|--------|
| L1 — Contract Tests | OT-01 ~ OT-16 | 16 | ✅ FROZEN (设计层) |
| L2 — Authority Leak Scan | OT-17 ~ OT-22 | 6 | ✅ FROZEN (设计层) |
| L3 — Consensus Drift Scan | OT-23 ~ OT-26 | 4 | ✅ FROZEN (设计层) |
| L4 — Removal Verification | OT-27 ~ OT-31 | 5 | ✅ FROZEN (设计层) |
| L5 — Full Pipeline | OT-32 ~ OT-34 | 3 | ✅ FROZEN (设计层) |
| **Total** | | **34** | **DRAFT — 待执行** |

### One-Sentence Freeze

> **Tests catch authority drift, not functionality.**

**Frozen at: 2026-07-22**
