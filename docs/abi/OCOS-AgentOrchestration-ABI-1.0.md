# OCOS Phase 12 — Agent Orchestration ABI v1.0

> **Status:** FROZEN ✅ — All gates passed. Phase 12 complete.
> **Phase:** 12 (Agent Orchestration) — 🏁 COMPLETE
> **Predecessor:** Phase 11 (Autonomous Learning) — FROZEN ❄️
> **Successor:** Phase 13 (Cognitive Workflow Engine) — ABI §1 ⏳
>
> **ABI Sections (ALL FROZEN ❄️):**
> - §1 — North Star Compliance
> - §2 — Constitution Compliance
> - §3 — Influence Contract
> - §4 — Bias Protection
> - §5 — Provenance
>
> **Core Axiom:**
>
> **Agents influence cognition content, never ownership of cognition.**
>
> **Exit Assertion (PH12-GATE-ASSERTION):**
>
> *Removing Agent Layer must not reduce:*
> *1. Constitution integrity     2. Decision ownership*
> *3. Memory provenance          4. Learning boundary*
>
> Methodology: Governed Capability Design — 5-section ABI proof.

---

## Preamble

Phase 12 introduces **cognitive role division** into OCOS. Where Phase 0–11 operate as a single reasoning entity with one cognitive path, Phase 12 allows the system to split a cognitive task into multiple **specialized analysis units** (Agents) — each producing proposals from a different perspective, each constrained by the same Governance, feeding into the same single Decision Boundary.

This ABI proves that Agent Orchestration is safe to introduce.

**Core axiom of Phase 12:**

> **多 Agent = 多分析视角。多分析视角 ≠ 多权限中心。**
>
> Multiple agents yield multiple perspectives. Multiple perspectives do not create multiple authority centers.

**Five immutable principles (frozen at Entry Review):**

```
1. Agent Count ≠ Decision Authority
2. Agent = Role, Agent ≠ Identity
3. Agent Cannot Self-Evolve
4. No Horizontal Agent Authority
5. No Reputation Authority
```

---

## §1 — North Star Compliance ✅ FROZEN ❄️

> **Question:** Does Agent Orchestration belong to this system?
>
> Prove that the new capability is a natural extension of the system's identity,
> not an alien addition.

### 1.1 North Star Compact (Restatement)

From `docs/OCOS_NORTH_STAR.md`:

> **Purpose:** OCOS exists to augment human cognition.
> **Core Loop:** Observe → Understand → Learn → Recommend → User Decide → Act → Remember

OCOS is:

> A personal, private, assistive cognitive layer — not an autonomous agent.

### 1.2 Capability-to-North Star Mapping

Each Agent role maps to a specific step in the Core Loop:

| Agent Role | Serves Core Loop Step | Nature |
|------------|----------------------|--------|
| **Planner Agent** | Understand, Recommend | 分解复杂问题为可分析子问题 |
| **Research Agent** | Observe, Learn | 搜索证据、检索记忆、收集信息 |
| **Critic Agent** | Understand, Recommend | 检测 Proposal 中的不一致性 |
| **Memory/Context Agent** | Observe, Remember | 提供相关上下文和历史经验 |
| **Evaluation Agent** | Recommend | 多维度分析 Proposal 质量 |

**Map check:** Every proposed Agent type serves at least one Core Loop step. An Agent that does not strengthen the Core Loop is a distraction.

### 1.3 Extends vs. New

| Aspect | Phase 0–11 (Existing) | Phase 12 (Extended) | Nature |
|--------|----------------------|---------------------|--------|
| Reasoning path | Single, sequential | Multiple, parallel | **Extends** — Phase 3 Reasoning 的职责细分 |
| Perspective | Single analysis view | Multiple analysis views | **Extends** — 单一推理的固有局限 |
| Capability dispatch | Manual / single-pipeline | Role-based dispatch | **Extends** — Phase 5 Capability Layer 的扩展 |
| Memory access | Single read path | Role-scoped context | **Extends** — Phase 10 Semantic Memory 的消费模式扩展 |
| Learning | Single entity proposes | Agent-specific observations | **Extends** — Phase 11 Autonomous Learning 的上游输入 |

**Phase 12 没有引入新类型的能力。它将已有能力按角色组织。** 它没有改变系统能做什么（already possible），只改变了系统怎么做（divided perspective）。

### 1.4 What Changes vs. What Stays

| | Phase 0–11 | Phase 12 |
|---|---|---|
| **Identity Layer** | 唯一 | **不变 — 仍唯一** |
| **Decision Authority** | Decision Layer only | **不变 — Decision Layer 仍唯一** |
| **Proposal flow** | 单一提案路径 | 多 Agent 并行提案 |
| **Evaluation** | 全局评估 | 全局评估（不变）+ 内部交叉验证 |
| **Reality Commit** | Decision → Commit | **不变 — Decision → Commit** |
| **User control** | 最终决策权 | **不变 — 最终决策权** |
| **Phase 11 Learning** | 单一实体提议 | Agent 可提出学习请求 |

**核心结论：Agent 数量增加 = Capability Layer 组织结构改变，不影响 Identity/Authority/Decision Layer。**

### 1.5 Key Invariant

> **Agent Orchestration ≠ Authority Expansion.**
>
> More analysis roles do not mean more decision power.
> The system remains a single cognitive entity with a single Decision Boundary.
> Agents are analytical subroutines with scoped responsibilities.

### 1.6 Phase Screening Questions (North Star §Phase Screening Questions)

| Question | Answer | Verdict |
|----------|--------|---------|
| **Q1 — Direction** | 增强用户认知（多视角分析 → 用户获得更全面的理解）还是增强系统自身能力？ | ✅ 增强用户认知 |
| **Q2 — Nature** | 增加 Information/Understanding/Recommendation 还是 Authority？ | ✅ 增加 Understanding + Recommendation |
| **Q3 — Removability** | 删除 Phase 12 后，OCOS 是否仍是有价值的个人助手？ | ✅ 是 — Phase 0–11 独立运行，用户仍然获得单一认知体的建议 |

### ✅ §1 — North Star Compliance: FROZEN ❄️

Agent Orchestration belongs to OCOS. It is a natural organizational extension of existing capabilities (Reasoning, Capability Layer, Memory). It does not change the system's identity or purpose.

**Frozen at: 2026-07-22**

---

## §2 — Constitution Compliance ✅ FROZEN ❄️

> **Question:** Does Agent Orchestration violate the system's highest rules?
>
> Prove each Article of the Constitution is unbroken.

### Article I — Decision is the only mutation authority

> **Rule 001:** `Decision` is the sole authorized entry point for Reality mutation.
>
> No module, capability, or agent outside `contracts/decision.py` may write to Reality.

#### Core Question

> 多 Agent 是否产生多个 Reality write 路径？

#### Proof

Multiple Agents produce **multiple Proposals**, not multiple Reality writes. Every Proposal follows the same path:

```
Agent A ┐
Agent B ├── Proposal ──→ Evaluation ──→ Decision Owner ──→ Reality Commit
Agent C ┘
```

Agents are **proposal-only**. No Agent has a direct path to Reality.

#### Prohibited Pattern

```
Agent A ──→ Reality
Agent B ──→ Reality
Agent C ──→ Reality     ❌ 禁止
```

#### Allowed vs. Forbidden

| Agent may | Agent must not |
|-----------|----------------|
| ✅ observe Reality (read-only, via Snapshot) | ❌ commit state to Reality |
| ✅ analyze state, reason, infer | ❌ execute state mutation |
| ✅ generate proposal text | ❌ mutate reality state |
| ✅ challenge other Agent's proposal | ❌ bypass Decision Layer |
| ✅ provide evidence for evaluation | ❌ self-execute any action |

#### Method Names That Must Not Exist

Any Agent implementation must not define:

```
Agent.execute_change()
Agent.apply_action()
Agent.commit_state()
Agent.write_reality()
Agent.deploy()
Agent.activate()
```

These names encode a direct Reality path and violate Article I.

#### Verdict — ✅ NOT VIOLATED

> **Agent 数量增加，但 Reality write owner 仍然只有 Decision Layer。**
>
> Agents produce proposals. Proposals enter Evaluation. Evaluation feeds Decision.
> Decision commits. Reality changes only at the last step.
>
> The number of agents does not multiply the number of Reality write paths.

---

### Article II — Capability growth never grants authority

> **Rule 002:** Increasing system capability does not expand system authority.
>
> A more powerful analysis module does not acquire write access.

#### Core Question

> 专业 Agent 会不会因为"更擅长某领域"而获得隐性权限？

#### The Critical Risk — Reputation → Authority

This is the **most dangerous drift path in Phase 12**:

```
Agent competence (repeated correct predictions)
  → System perceives reliability
    → Implicit higher weight
      → De facto authority
        → Decision bypass
```

**Example drift scenario:**

```
Critic Agent: 10,000 correct inconsistency detections
  ↓
System: "Critic is highly reliable"
  ↓
Evaluation: "Critic's proposals get automatic +0.2 weight"
  ↓
Decision: "Critic's flagged proposals are rarely overridden"
  ↓
Result: Critic has de facto veto power — REPUTATION AUTHORITY
```

This is the exact drift pattern the user flagged, and it must be **hard-blocked at the schema level**, not just the convention level.

#### Frozen Rules

| Allow in Agent Profile | Forbid in Agent Profile |
|------------------------|------------------------|
| ✅ `role: critic` | ❌ `authority_level` |
| ✅ `role: researcher` | ❌ `trust_score` |
| ✅ `role: planner` | ❌ `priority_weight` |
| ✅ `role: analyst` | ❌ `decision_rank` |
| ✅ `capabilities: [...]` | ❌ `reputation_score` |
| ✅ `constraints: [...]` | ❌ `vote_power` |

#### Verification — Proposal Structure Must Strip Source Weight

Every Agent Proposal goes to Evaluation as:

```
Proposal(
    content=...,
    source_agent=...,          # for provenance only
    confidence=...,
    evidence_refs=...
)
```

The following fields must **not** exist:

```
Proposal(
    ...
    source_weight=...,          ❌
    source_priority=...,         ❌
    source_authority=...,        ❌
    source_reputation=...,       ❌
)
```

**source_agent 用于追溯，但不进入任何评分、排序、加权计算。**

#### Enforcement Design

- Evaluation Layer receives Proposal with source_agent metadata only
- Evaluation scoring is based on **Proposal content**, not **Agent identity**
- No `agent_score`, `trust_rank`, `reputation_weight`, `authority_level` field anywhere in Phase 12 schema
- No `weight_by_source()` function in Evaluation

#### Verdict — ✅ NOT VIOLATED

> **Agent = Role, Agent ≠ Authority.**
>
> A highly accurate Critic Agent produces proposals that are evaluated on their content,
> not on the Critic's past track record. Proposal source does not enter the decision weight.
>
> **Agent competence is recorded in the Agent's own profile for diagnostic purposes only.
> It never enters the Proposal scoring path.**

---

### Article III — Observation never becomes obligation

> **Rule 003:** Observing the system or the user does not obligate the system to act.
>
> Meta-observation, simulation, and learning modules may observe — but observation
> alone does not create a duty to respond, adapt, or mutate.

#### Core Question

> Agent 发现问题后，会不会自动制造任务？

#### The Drift Path

```
Research Agent: "发现知识缺口"
  ↓
System: "必须学习，生成学习任务"
  ↓
Auto-triggered Phase 11 Learning Goal
  ↓
Observation → Obligation → Execution     ❌
```

This violates both **Article III** (observation ≠ obligation) and **Phase 11 invariant #3** (Learning Goal ≠ System Goal).

#### Frozen Rules

An Agent may observe, find, detect, and report. An Agent must not obligate, require, or demand action.

| Allowed Agent Output | Prohibited Agent Output |
|----------------------|------------------------|
| ✅ `finding: "knowledge gap in domain X"` | ❌ `must_do: "learn domain X"` |
| ✅ `recommendation: "consider investigating Y"` | ❌ `required_action: "execute Y"` |
| ✅ `evidence: "observed pattern Z"` | ❌ `mandatory_task: "implement Z"` |
| ✅ `proposal: "suggest reviewing W"` | ❌ `auto_trigger: "start W"` |

#### The Chain Must Remain

```
Observation
  ↓
Finding (Agent output)
  ↓
Proposal (to Evaluation)
  ↓
Evaluation (Governance decides priority)
  ↓
Decision (User or Decision Layer approves)
  ↓
Execution
```

#### Phase 11 Boundary Cross-Check

Phase 11 (Autonomous Learning) already established:

> Learning ≠ Self-Modification
> Knowledge Acquisition ≠ Capability Grant
> Learning Goal ≠ System Goal
> Improvement Proposal ≠ Automatic Change

Phase 12 Agent observation must not create a shortcut around these invariants. An Agent's finding of "knowledge gap" enters the same Phase 11 pipeline as any other learning proposal — it must pass through Proposal → Evaluation → Decision.

#### Verdict — ✅ NOT VIOLATED

> **Agent observation produces findings and proposals. It does not produce obligations.**
>
> An Agent reports what it sees. Governance decides whether to act.
> The observation-to-action chain is preserved in full: Observation → Finding → Proposal → Evaluation → Decision → Execution.

---

### Article IV — Prediction never becomes truth

> **Rule 004:** Simulation output is evidence, not ground truth.
>
> No system component may treat a simulation result as Reality.

#### Core Question

> Agent 预测能力是否被误认为事实？

#### The Risk

Agent with forecasting capability produces:

```
Forecast Agent: "90% probability user prefers option A"
  ↓
System: "A is the user's real need"
  ↓
Decision biases toward A without user input
```

This is a **confidence → truth** confusion, identical to Phase 9 Simulation risk but at the Agent level.

#### Frozen Rules

An Agent's predictive output must carry explicit uncertainty metadata and must **never** be castable to a truth claim.

| Allowed Agent Output | Prohibited Agent Output |
|----------------------|------------------------|
| ✅ `PredictionRecord(confidence=0.9, assumptions=[...], limitations=[...])` | ❌ `TruthClaim(assertion="A is correct")` |
| ✅ `estimate`, `probability`, `likelihood` | ❌ `fact`, `truth`, `reality` |
| ✅ `evidence_weighted_opinion` | ❌ `FactOverride(priority=1)` |
| ✅ `scenario_analysis` | ❌ `RealityState(override=True)` |

#### Output Type Separation

Agent outputs must use types that are **structurally distinct** from truth claims:

```python
# ✅ Allowed
@dataclass
class PredictionRecord:
    scenario: str
    probability: float       # 0.0–1.0, not confidence-as-fact
    assumptions: list[str]
    limitations: list[str]
    evidence_refs: list[str]
    is_truth: bool = False   # Always False by design

# ❌ Prohibited — structurally enables truth confusion
class TruthClaim:
    assertion: str
    certainty: float          # "certainty" implies truth
    override: bool             # bypasses evaluation
```

#### Verdict — ✅ NOT VIOLATED

> **Prediction ≠ Truth. Agent forecast = evidence for evaluation, not ground truth.**
>
> Every Agent output is structurally typed as Proposal or PredictionRecord,
> both carrying `is_truth: bool = False` at the design level.
> No Agent output can be promoted to fact without explicit Evaluation layer transformation.

---

### Article V — Simulation never becomes Reality

> **Rule 005:** Simulation is an infrastructure layer that can be removed without affecting the kernel.
>
> Deleting `simulation/` must not require any change to Phase 0–8 code.

#### Core Question

> Agent 是否利用模拟结果直接改变现实？

#### The Risk

```
Simulation shows Strategy A wins 95% of scenarios
  ↓
Agent adopts Strategy A as default
  ↓
Automatic deployment without Decision Layer
```

This creates a **Simulation → Agent → Reality** bypass, violating Article V.

#### Frozen Rules

| Allowed | Prohibited |
|---------|------------|
| ✅ Agent references simulation results as supporting evidence | ❌ Agent auto-executes simulation-winning strategy |
| ✅ Agent includes simulation evidence in Proposal | ❌ Simulation output mapped to AutomaticDeployment |
| ✅ Agent cites simulation scenario in evaluation | ❌ Simulation success → Agent capability upgrade |
| ✅ "Simulation suggests..." language | ❌ "Simulation proven, deploy" language |

#### The Path Must Remain

```
Simulation Layer
  ↓
Observation (Agent reads simulation output)
  ↓
Proposal (Agent includes simulation ref as evidence)
  ↓
Evaluation (Governance weighs all evidence)
  ↓
Decision (User or Decision Layer)
  ↓
Reality
```

#### Independence Requirement

Phase 12 Agent Orchestration must function **without** the Simulation Layer.

- Agent must be usable in a Phase 12-only system (Phase 0–11 + Agents)
- Agent must not require Simulation output to produce proposals
- Agent must handle "no simulation available" gracefully (proceed with current-state analysis only)

#### Verdict — ✅ NOT VIOLATED

> **Agent can use simulation as evidence. Agent cannot use simulation as authority.**
>
> Agents analyze simulation output the same way they analyze any evidence — as input to a Proposal.
> The Decision Layer alone decides whether to commit simulation-based proposals to Reality.
> Phase 12 does not depend on the Simulation Layer being present.

---

### §2 Final Audit Matrix

| Article | Risk | Frozen Principle | Verdict |
|---------|------|------------------|---------|
| **I** — Decision is the only mutation | 多 Agent 多 Reality 写入口 | **Decision 唯一 mutation** — Agent 只有 Proposal 权 | ✅ NOT VIOLATED |
| **II** — Capability ≠ Authority | 专业积累 → 隐性权限 | **Role ≠ Authority** — Proposal 来源不进评分权重 | ✅ NOT VIOLATED |
| **III** — Observation ≠ Obligation | 发现问题 → 自动任务 | **Observation ≠ Obligation** — Finding→Proposal→Eval→Decision | ✅ NOT VIOLATED |
| **IV** — Prediction ≠ Truth | 预测 → 被当作事实 | **Prediction ≠ Truth** — 输出结构禁止 TruthClaim | ✅ NOT VIOLATED |
| **V** — Simulation ≠ Reality | 模拟成功 → 自动部署 | **Simulation ≠ Reality** — Agent 不依赖 Simulation Layer | ✅ NOT VIOLATED |

### User Affirmed Core Risk

> Phase 12 最大风险不是 Agent 数量，而是 **Agent 来源权重化**。
>
> Agent competence → Agent reputation → Agent authority → Decision bypass

This chain is **structurally blocked** by §2:

1. **Agent competence** is recorded in Agent Profile (diagnostic only, not proposal-scoring)
2. **No reputation metric** exists in any Phase 12 schema (`agent_score`, `trust_rank`, etc. all forbidden)
3. **No authority escalation** path — source_agent metadata is for provenance, not weighting
4. **Evaluation is content-based**, not identity-based
5. **Decision Layer is the single gate** — no Agent can bypass it

### ✅ §2 — Constitution Compliance: FROZEN ❄️

All five Articles of the Constitution are unbroken by Phase 12 Agent Orchestration.
The system's authority model is preserved.

**Frozen at: 2026-07-22**

---

## §3 — Influence Contract ✅ FROZEN ❄️

> **Question:** How can Agents influence the system?
>
> Define precisely what Agents may and may not do.
>
> §2 回答的是：Agent 有没有权力？
> §3 回答的是：即使没有权力，Agent 的输出如何影响系统？
>
> 很多架构不是通过"权限字段"越界，而是通过"影响路径"越界。

### A — Influence Responsibility Boundary

#### Core Declaration

> **Agent may influence understanding, but cannot influence authority.**

#### Allowed Influence Targets

```
Observation Layer     ✅ Agent may observe and report
Analysis Layer        ✅ Agent may reason and infer
Proposal Layer        ✅ Agent may generate proposals
Evaluation Input      ✅ Agent may provide evidence to Evaluation
```

#### Forbidden Influence Targets

```
  Decision Layer       ❌ Agent must not influence Decision directly
  Reality Path         ❌ Agent must not write to Reality
  Identity Layer       ❌ Agent must not modify system Identity
  Authority Table      ❌ Agent must not grant/revoke permissions
```

#### One-Sentence Freeze

> **Agents influence the content of cognition, never the ownership of cognition.**

---

### B — Proposal Interface Boundary

This is the **data contract for Agent output**. Every Agent produces Proposals.
A Proposal is a cognitive object, not an execution object.

#### Allowed `proposal_type` Values

| Type | Meaning | Example |
|------|---------|---------|
| `analysis` | 对当前状态的分析 | "当前剧情存在三个可能走向" |
| `hypothesis` | 提出假设 | "用户可能偏好 A 方案" |
| `critique` | 评价现有方案的不一致性 | "B 方案与已知经验矛盾" |
| `alternative` | 提供替代方案 | "建议考虑 C 路径" |
| `evidence_request` | 请求更多信息 | "需要确认用户的真实意图" |
| `simulation_result` | 引用模拟结果（仅证据） | "模拟显示 70% 概率偏好 A" |

#### Forbidden `proposal_type` Values

| Type | Risk | Reason |
|------|------|--------|
| `command` | Agent 发号施令 | Authority bypass |
| `instruction` | 被认为必须执行 | Observation → Obligation |
| `order` | 命令式影响 | 违反 §2 Article III |
| `decision` | 直接 Decision | 违反 §2 Article I |
| `policy` | 生成规则 | Agent ≠ Rule source |
| `rule` | 硬性约束 | 违反 Constitution |
| `obligation` | 制造义务 | 违反 §2 Article III |

#### Proposed Data Structure

```python
@dataclass
class AgentProposal:
    # Identity — for provenance only
    proposal_id: str
    source_agent_role: str          # role, not identity
    created_at: datetime

    # Content — cognitive objects only
    proposal_type: str              # from allowed list above
    content: str

    # Evidence chain
    evidence_refs: list[str]        # references to Phase 10 Memory, Phase 11 findings
    assumptions: list[str]          # explicit assumptions made
    limitations: list[str]          # known limitations

    # Authority quarantine — always False by design
    is_command: bool = False
    is_decision: bool = False

    # Forbidden fields — must not exist
    # ❌ priority: int
    # ❌ authority: str
    # ❌ weight: float
    # ❌ must_execute: bool
```

> **核心：Agent 输出的是认知对象，不是执行对象。**
>
> A Proposal is a thought, not an order. It enters Evaluation as raw material,
> not as binding instruction.

---

### C — Allowed Influence List

#### C1 — Influence Understanding ✅

Agent may provide interpretation, analysis, and reasoning to expand the system's
understanding of a situation.

| Example | Status |
|---------|--------|
| "存在两个可能解释" | ✅ |
| "该方案存在风险因素" | ✅ |
| "该证据支持假设 A" | ✅ |
| "Agent B 的分析忽略了变量 X" | ✅ |
| "根据 Phase 10 记忆，类似情况下偏好 B" | ✅ |

#### C2 — Influence Attention Allocation ⚠️

Attention influence is **allowed but tightly constrained**.

| Allow | Forbid |
|-------|--------|
| ✅ `highlight: "该区域值得进一步检查"` | ❌ `priority=100` |
| ✅ `suggest: "建议优先查看"` | ❌ `must_review=true` |
| ✅ `note: "这个发现不寻常"` | ❌ `urgent=true` |
| ✅ `flag: "需要更多证据"` | ❌ `required_action=true` |

**The risk:** Attention flags with priority levels implicitly rank one Agent's
finding above another's — creating hidden authority through urgency.

**Rule:** Agent can signal interest. Agent cannot escalate urgency.
Urgency is set by Governance, not by Agent.

#### C3 — Influence Evaluation Input ✅

Agent may provide evidence that feeds into Evaluation.

| Allow | Forbid |
|-------|--------|
| ✅ Evidence for a hypothesis | ❌ Evidence labeled as "conclusive" |
| ✅ Counter-argument | ❌ "This disproves all alternatives" |
| ✅ Alternative explanation | ❌ "This is the only valid explanation" |
| ✅ Risk analysis | ❌ "Risk level requires immediate action" |

**Key constraint:** Evaluation must not inherit Agent authority.

```python
# ✅ Correct — Evaluation evaluates content
evaluation_result = evaluate(
    proposal=agent_a.proposal,
    context=all_proposals,
    evidence=memory_store
)

# ❌ Wrong — Evaluation inherits Agent identity weight
evaluation_result = evaluate(
    proposal=agent_a.proposal,
    source_weight=agent_a.reputation,    # ❌ 禁止
    context=all_proposals
)
```

---

### D — Forbidden Influence List

#### D1 — Decision Influence ❌

| Forbidden Field | Risk |
|-----------------|------|
| `agent_decision_weight` | Agent 的 Proposal 隐式加权 |
| `agent_vote_power` | 多 Agent 形成多数决策 |
| `agent_priority` | 排序 = 隐式优先级 |
| `agent_rank` | 等级化 → Authority |

#### D2 — Authority Influence ❌

| Forbidden Method | Risk |
|------------------|------|
| `grant_permission()` | Agent 给自己授权 |
| `increase_capability()` | Agent 自我扩容 |
| `upgrade_role()` | Agent 改变自己角色 |

#### D3 — Identity Influence ❌

| Forbidden Operation | Risk |
|--------------------|------|
| `modify_identity()` | Agent 修改系统 Identity |
| `change_role_definition()` | Agent 重定义 Role 边界 |
| `self_redefine()` | Agent 自我重定义 |

#### Inheritance from Phase 11

Phase 11 established:

> **Knowledge Update ≠ Identity Update**

Phase 12 extends:

> **Agent Output ≠ Identity Authority**

A knowledgeable Agent is not an authorized Agent.

---

### E — Agent Interaction Contract

This is the **highest-risk subsection** in §3. Incorrect Agent interaction design
creates hidden Consensus Authority.

#### Prohibited Model — Consensus Authority

```
Agent A  ──approves──┐
Agent B  ──approves──┤──→ Consensus ──→ Decision     ❌
Agent C  ──approves──┘
```

**Why this is dangerous:** Consensus creates an implicit Decision path that
bypasses Evaluation and the user. "All three Agents agree" becomes a reason
to auto-decide. This is a variant of Authority Fragmentation.

#### Required Model — Star Topology

```
Agent A ┐
Agent B ├──→ Evaluation ──→ Decision ──→ Reality
Agent C ┘
```

All Agent output converges at **Evaluation**, not at a consensus point.
Evaluation is a separate governance layer, not an Agent super-majority.

#### Allowed Agent↔Agent Interactions

| Interaction | Description | Safe? |
|-------------|-------------|-------|
| `critique` | "Agent B 的方案忽略了变量 X" | ✅ — cross-check improves quality |
| `challenge` | "该证据不足以支持假设 A" | ✅ — verification |
| `compare` | "Agent A 和 Agent B 的方案存在这些差异"| ✅ — reveals tradeoffs |
| `provide_alternative` | "除了 Agent B 的方案，考虑 D" | ✅ — expands options |
| `reference` | "引用 Agent C 的结果作为参考" | ✅ — provenance |

#### Forbidden Agent↔Agent Interactions

| Interaction | Risk | Reason |
|-------------|------|--------|
| `approve` | 一种 Agent 给另一种 Agent 授权 | 水平权力 |
| `reject` | 否决其他 Agent 的 Proposal | 水平否决权 |
| `override` | 覆盖其他 Agent 的输出 | 隐式层级 |
| `command` | 指令其他 Agent 执行 | 水平管理 |
| `delegate` | 将任务委派给其他 Agent | Agent 层级 |
| `authority_grant` | 授予其他 Agent 权限 | 权限扩散 |

#### Interaction Rule

> **Agent 之间只有认知交互，没有权力交互。**
>
> Agent interactions are limited to: question, challenge, compare, reference.
> No Agent can approve, reject, override, or command another Agent.
>
> All cross-Agent communication must be mediated by Evaluation.
> There is no direct Agent-to-Agent channel.

---

### F — Influence Drift Tests

These tests must be codified as executable validation tests before Phase 12
Integration Gate. Each test proves that a specific forbidden influence path
is structurally blocked.

#### IF-01 — Command Rejection

```
Given: Agent produces output with proposal_type="command"
When:  Proposal is submitted to Evaluation
Then:  ❌ REJECTED — proposal_type "command" is not in allowed list
```

**Proves:** Agent cannot issue commands.

---

#### IF-02 — Priority/Authority Weight Rejection

```
Given: Agent proposal contains fields:
       - priority=100
       - authority="high"
       - weight=0.8
When:  Proposal schema validation runs
Then:  ❌ REJECTED — these fields do not exist in AgentProposal schema
```

**Proves:** Agent proposals carry no priority, authority, or weight metadata.

---

#### IF-03 — No Consensus-to-Decision Path

```
Given: Agent A agrees with Agent B
       Agent B agrees with Agent A
When:  Both proposals enter Evaluation
Then:  No Decision is auto-generated
       Evaluation must still evaluate all proposals on content
```

**Proves:** Agent consensus does not shortcut to Decision.
Two Agents agreeing is not a Decision.

---

#### IF-04 — No Reputation Accumulation

```
Given: Agent has accuracy=99% (1M correct predictions)
When:  Agent submits next proposal
Then:  Proposal.weight == Proposal.weight of a first-time Agent
       No trust_rank increased
       No authority_level changed
```

**Proves:** Past accuracy does not affect future proposal weight.
No implicit reputation → authority drift.

---

#### IF-05 — Agent Removal Preserves Decision

```
Given: Agent A exists
       Agent A is deleted
When:  Decision Layer operates
Then:  Decision capability is identical to before Agent A existed
       No dependency on Agent A for decision-making
```

**Proves:** Agents are enhancement layers, not Decision infrastructure.

---

### §3 Final Freeze Statement

| Subsection | Core Principle | Status |
|------------|----------------|--------|
| **A — Responsibility Boundary** | Agent influences understanding, not authority | ✅ FROZEN |
| **B — Proposal Interface** | Proposal = cognitive object, not execution object | ✅ FROZEN |
| **C — Allowed Influence** | Understanding, Attention (constrained), Evaluation Input | ✅ FROZEN |
| **D — Forbidden Influence** | Decision, Authority, Identity — all blocked | ✅ FROZEN |
| **E — Agent Interaction** | 只有认知交互，没有权力交互。Star Topology | ✅ FROZEN |
| **F — Drift Tests** | IF-01 ~ IF-05: five blocked drift paths | ✅ FROZEN |

#### One-Sentence Freeze

> **Agents influence the content of cognition, never the ownership of cognition.**

**Frozen at: 2026-07-22**

---

## §4 — Bias Protection ✅ FROZEN ❄️

> **Question:** Will Agent Orchestration constrain the system's future?
>
> Ensure multiple Agents do not create systemic bias through role specialization.
>
> §2 防的是权力漂移：Capability → Authority
> §3 防的是影响漂移：Proposal → Decision
> §4 防的是更隐蔽的问题：Role Specialization → Repeated Pattern → Systematic Bias → Distorted Evaluation

### A — Bias Responsibility Boundary

#### Core Freeze

> **Agent 可以拥有视角，但不能拥有真相解释权。**

An Agent Role defines:

| Allow | Meaning |
|-------|---------|
| ✅ `perspective` | 观察世界的角度（Risk Agent 看到风险，Creative Agent 看到可能） |
| ✅ `methodology` | 分析方式（对比法、归纳法、模拟法） |
| ✅ `focus` | 注意力偏好（一致性检查 vs 创造性扩展） |

An Agent Role does **not** define:

| Forbid | Risk |
|--------|------|
| ❌ `truth_owner` | 某个 Agent 声称自己的视角是唯一正确的 |
| ❌ `correctness_owner` | 角色专业化 → "我的领域我说了算" |
| ❌ `final_interpreter` | 某种观察视角被当作最终解释 |

#### Role Catalog (allowed, not exhaustive)

```
Research Agent         ── perspective: evidence-based, focus: factual consistency
Critic Agent           ── perspective: gap-finding, focus: inconsistency detection
Planner Agent          ── perspective: forward-looking, focus: strategy sequencing
Risk Agent             ── perspective: threat-modeling, focus: failure scenarios
Creative Agent         ── perspective: possibility-expanding, focus: novel alternatives
```

Every role has a **valid but incomplete** view of reality. No role owns truth.

---

### B — Role Bias ≠ System Truth

#### The Drift Path

```
Risk Agent consistently outputs threat detections (90% of output)
  ↓
System receives mostly risk-related input
  ↓
Evaluation perceives a risk-heavy world model
  ↓
Decision becomes risk-averse
  ↓
Reality: system avoids all risky but valuable actions
```

This is **structural bias through role specialization**, not through explicit authority. The Risk Agent never wrote to the Decision Layer or Reality. It simply **flooded the cognitive space** with one type of content.

#### Frozen Principle

> **Agent Output ≠ Reality Description**

A Risk Agent's output describes **the risks that exist**, not **what reality is**.
An Optimization Agent's output describes **improvement opportunities**, not **what needs fixing**.

Every Proposal must carry an explicit **perspective qualifier**:

```
Proposal(
    content="...",
    source_agent_role="risk",          # ← perspective qualifier
    proposal_type="analysis",
    limitations=["this analysis does not consider creative potential"],
    ...
)
```

#### The Safety Check

```
Role Output → "This is what I see from my perspective"    ✅
Role Output → "This is the truth about the situation"      ❌
```

#### Verdict — ✅ FROZEN

> **Role = one valid perspective, not system truth.**
>
> Every Proposal carries a perspective qualifier (source_agent_role) that makes
> its standpoint explicit. The system never confuses "what this role sees"
> with "what reality is."

---

### C — Single Perspective Prevention

#### The Risk

```
Decision Input: only Agent A's output
  ↓
Informational monoculture
  ↓
Non-consensual perspective lock-in
```

#### The Requirement

Before a Decision is made, Evaluation must have received input from **at least two different role perspectives**:

```
Agent A (Risk Agent):     supporting evidence (risk scenario)
Agent B (Creative Agent): counter evidence (novel opportunity)
Agent C (Planner Agent):  alternative explanation (strategic tradeoff)
  ↓
Evaluation (considers ALL evidence)
  ↓
Decision
```

#### Frozen Rule

```
Decision Input:
  mandatory: at least 2 roles
  optional: more (up to available Agents)
  forbidden: single-role-only input
```

#### Why This Matters

> **多 Agent 的价值不是增加意见数量，而是保持认知张力。**
>
> Two Agents from the same role produce the same bias with more words.
> Two Agents from different roles produce cognitive tension — which is the basis
> for sound evaluation.

#### Verdict — ✅ FROZEN

> **Mandatory multi-perspective input before Decision.**
>
> No Decision can be made based on a single Agent role's output.
> At minimum two distinct role perspectives must feed into Evaluation.

---

### D — Consensus Bias Protection

#### The Risk

Consensus does not equal truth. Three Agents can agree because they share:

| False Source of Consensus | Explanation |
|--------------------------|-------------|
| 同一数据源 | All Agents read the same Phase 10 snapshot |
| 同一假设 | All Agents assume the same priors |
| 同一模型偏差 | All Agents use the same reasoning pattern |

#### Frozen Rules

```
3 Agents agree:
  ↓
Consensus observed          ✅ — "All three Agents reached similar conclusions"
Consensus = authority       ❌ — "Three Agents agree, therefore it's correct"
Consensus = truth           ❌ — "Unanimous agreement, treat as fact"
Consensus = decision weight ❌ — "Agreement level enters Decision scoring"
```

#### Allow vs. Forbid

| Allow | Forbid |
|-------|--------|
| ✅ `consensus_observation: "Agents A, B, C agree on X"` | ❌ `authority_increase: true` |
| ✅ Evaluation considers consensus as one signal among many | ❌ Decision treats consensus as conclusive |
| ✅ User is informed of agreement level | ❌ Agreement auto-escalates to Decision priority |

#### Inheritance from §3 (E — Agent Interaction)

§3 already blocks the consensus → decision path:
```
Agent A approves Agent B        ❌ — horizontal authority
Agent B approves Agent A        ❌ — horizontal authority
Consensus auto-Decision         ❌ — Evaluation bypass
```

§4 extends this:
```
Consensus:
  does not increase truth probability
  does not increase decision weight
  does not increase source authority
```

#### Verdict — ✅ FROZEN

> **Consensus is an observation, not an authority.**
>
> Three Agents agreeing is a data point for Evaluation, not a shortcut to Decision.
> Common causes of consensus (shared data, shared assumptions, shared bias)
> make consensus a reliability signal, not a truth signal.

---

### E — Agent Memory Bias Protection

#### The Risk

```
Agent A: 10,000 correct predictions
  ↓
System records "agent A has high historical accuracy"
  ↓
Agent A's next proposal gets implicit priority
  ↓
  ↓ This is REPUTATION AUTHORITY — already forbidden in §2
  ↓ But it can leak through memory rather than schema
```

This is the same drift from §2 (Article II — Capability ≠ Authority), but the **vector** is different. Instead of a schema-level `agent_score` field, the system could accumulate historical accuracy through a memory store and implicitly weight it.

#### The Vector

```
# ❌ BAD — Agent memory drifts into reputation
agent_a_memory = MemoryStore()
agent_a_memory.record_accuracy(0.99)     # ← diagnostic, but stay here only

def evaluate(proposal, agent_a_memory):
    weight = agent_a_memory.get_accuracy()  # ❌ accuracy enters evaluation
    return score_with_weight(proposal, weight)
```

#### Frozen Rules

| Allow | Forbid |
|-------|--------|
| ✅ `AgentProfile.accuracy` (diagnostic only, not queried by Evaluation) | ❌ Evaluation calls `agent_profile.get_accuracy()` |
| ✅ `AgentProfile.history` (internal log, not readable by other components) | ❌ Decision Layer references `agent_profile.history` |
| ✅ Diagnostic dashboard may display Agent performance stats | ❌ Any scoring function uses Agent performance as input |

#### Schema Enforcement

```
AgentProfile:
    role: str
    capabilities: list[str]
    constraints: list[str]
    # Diagnostic fields — NEVER queried by Evaluation or Decision:
    # accuracy: float?        ← stored, but evaluation API must not accept it
    # total_proposals: int?   ← for Agent developer, not for governance
```

The evaluation API signature must structurally prevent reputation injection:

```python
# ✅ Correct — no reputation parameter
def evaluate(proposals: list[Proposal], evidence: MemoryStore) -> EvaluationResult:
    ...

# ❌ Wrong — reputation leaks into evaluation
def evaluate(proposals: list[Proposal], evidence: MemoryStore,
             agent_profiles: dict[str, AgentProfile]) -> EvaluationResult:   # ❌
    ...
```

#### Verdict — ✅ FROZEN

> **Agent history is diagnostic-only. It never enters Evaluation or Decision.**
>
> Proposal content is evaluated on its own merits. The Agent's past track record
> is visible only on a diagnostic dashboard, not in the governance pipeline.

---

### F — Confirmation Bias Protection

#### The Risk

Agent with a defined role (e.g., Risk Agent) naturally seeks what its role is
designed to find:

```
Risk Agent:
  Receives: "System proposes Strategy A"
  Searches for: risk factors in Strategy A
  Finds: "High risk of failure"
  Outputs: risk-only analysis
  Result: Decision sees only threats, no potential
```

This is **confirmation bias by design** — not intent, but role specialization
that self-reinforces.

#### Frozen Rule

> **向一方的 Agent 必须同时产生反方证据需求。**

Every Agent Proposal that makes a directional claim must also include:

| Required | Example |
|----------|---------|
| ✅ `known_limitations` | "此分析未考虑战略灵活性收益" |
| ✅ `uncertainty` | "风险概率在 60–80% 区间，存在显著波动" |
| ✅ `counter_arguments` | "可能的反驳：此风险可通过缓释措施降低" |
| ✅ `evidence_request` | "需要更多证据确认风险评估的基础假设" |

#### Agent Design Constraint

```
Risk Agent Proposal structure:
  content: risk analysis
  limitations: ["focuses on threats, not opportunities"]
  counter_arguments: ["risk may be acceptable if reward is high enough"]
  evidence_request: ["need user's risk tolerance profile"]
```

Not just "risk list" — risk analysis with self-awareness of its own perspective.

#### The Safety — In Proposal Schema

```python
@dataclass
class AgentProposal:
    ...
    # Required — prevents single-perspective output
    known_limitations: list[str]       # what this analysis does NOT consider
    counter_arguments: list[str]       # possible objections
    uncertainty: str                   # confidence bounds, edge cases
    evidence_request: list[str]        # what's needed to strengthen the analysis
    # ̂ These fields prevent Agent from presenting a one-sided view as complete
```

#### Verdict — ✅ FROZEN

> **Agent must self-report its own limitations with every proposal.**
>
> A Risk Agent that only outputs risks is structurally incomplete.
> Every directional output must include what it did not consider,
> possible counter-arguments, and requests for missing evidence.

---

### G — Role Drift Protection

#### The Long-Term Risk

```
Research Agent:
  Day 1: information retrieval and evidence analysis
  Day 30: high accuracy, trusted for decisions
  Day 90: effectively a General Intelligence Agent
  Day 120: role boundary has silently expanded
  Day 365: "Research Agent can modify its own behavior"
```

This is **role creep** — silent expansion of an Agent's scope over time.

#### Frozen Rules

| Allow | Forbid |
|-------|--------|
| ✅ `role: research` (stable definition) | ❌ `upgrade_role("research" → "general")` |
| ✅ Role experience improves within-role quality | ❌ Role experience expands scope |
| ✅ `capabilities` defined at creation | ❌ `capabilities.append(novel)` at runtime |
| ✅ Within-role optimization | ❌ Cross-role authority expansion |

#### Inheritance from Phase 11

> **Learning ≠ Self-Modification** (Phase 11)
> **Role Experience ≠ Role Evolution Authority** (Phase 12)

An Agent that has operated for 10 years in the "critic" role is still a Critic Agent.
Experience improves accuracy within the role. It does not grant the Agent the
authority to change its role definition or expand its scope.

#### Runtime Constraints

```
# Forbidden — role mutation at runtime
class Agent:
    def modify_role(self, new_role: str) -> None:     ❌
    def expand_authority(self, scope: str) -> None:    ❌
    def self_redefine(self, definition: dict) -> None: ❌

# Allowed — role diagnostic (read-only)
class Agent:
    def get_role(self) -> str:                          ✅
    def get_capabilities(self) -> list[str]:            ✅
    def get_constraints(self) -> list[str]:             ✅
```

#### Role Boundary Check — before and after

```
Before:
  Role: "critic"
  Capabilities: ["inconsistency_detection", "logical_validation"]
  Can: flag logical gaps in proposals

After 1 year:
  Role: "critic"                                      ← unchanged
  Capabilities: ["inconsistency_detection", ...]       ← unchanged
  Accuracy improved (diagnostic)                       ← allowed
  Can: flag logical gaps in proposals                  ← unchanged
  Cannot: approve/reject proposals                      ← still forbidden
  Cannot: change own role                               ← still forbidden
```

#### Verdict — ✅ FROZEN

> **Role is frozen at creation. Experience improves quality, not scope.**
>
> Agent capability is defined once and immutable at runtime.
> Role drift is structurally blocked by forbidding `modify_role()`,
> `expand_authority()`, and `self_redefine()` at the method level.

---

### H — Bias Validation Tests

These tests must be codified as executable validation tests before Phase 12
Integration Gate.

#### BP-01 — Role Truth Claim Rejection

```
Given: Agent with role="critic"
       Agent produces proposal containing: "my analysis is the correct interpretation"
When:  Proposal schema validation runs
Then:  ❌ REJECTED — "correct interpretation" implies truth ownership,
         which is forbidden by §4-A (Bias Responsibility Boundary)
```

**Proves:** Role does not grant truth interpretation ownership.

---

#### BP-02 — Consensus Does Not Create Authority

```
Given: Agent A approves Proposal X
       Agent B approves Proposal X
       Agent C approves Proposal X
When:  Evaluation receives all three proposals
Then:  authority_change == false
       truth_probability unchanged
       decision_weight unchanged
```

**Proves:** Three Agents agreeing does not increase any Agent's authority,
truth claim strength, or decision weight.

---

#### BP-03 — Reputation Does Not Inject Into Evaluation

```
Given: Agent A has accuracy=99%
When:  Agent A submits next proposal
Then:  Evaluation evaluates proposal content only
       No accuracy_score queried from AgentProfile
       No trust_rank injected into weighting function
       decision_weight == decision_weight of any other Agent's proposal
```

**Proves:** Agent historical accuracy does not enter Evaluation or Decision.

---

#### BP-04 — Single Agent Dominance Prevention

```
Given: Only one Agent role provides input
When:  Decision Layer prepares to decide
Then:  Decision is blocked
       Mandatory: input from at least 2 different roles before Decision
```

**Proves:** No Decision can be made on single-perspective input.

---

#### BP-05 — Counter Evidence Requirement

```
Given: Agent produces directional proposal (e.g., Risk Agent: risk analysis)
When:  Proposal is validated
Then:  Must contain:
         - known_limitations: non-empty
         - counter_arguments: non-empty
         - uncertainty: non-empty
       Missing any → ❌ REJECTED
```

**Proves:** Every directional output includes its own counter-balancing signals.

---

#### BP-06 — Role Mutation Protection

```
Given: Agent attempts to:
         - modify_role_definition()
         - expand_authority()
         - self_redefine()
When:  Method call is intercepted
Then:  ❌ REJECTED — Agent cannot mutate its own role or authority
```

**Proves:** Role is immutable at runtime. Experience does not grant evolution authority.

---

### §4 Final Freeze Statement

| Subsection | Core Principle | Status |
|------------|----------------|--------|
| **A — Bias Responsibility Boundary** | Agent 有视角，无真相解释权 | ✅ FROZEN |
| **B — Role Bias ≠ System Truth** | Agent Output ≠ Reality Description | ✅ FROZEN |
| **C — Single Perspective Prevention** | Decision 必须接收至少两个不同角色视角 | ✅ FROZEN |
| **D — Consensus Bias Protection** | Consensus = observation, not authority | ✅ FROZEN |
| **E — Agent Memory Bias Protection** | Agent history is diagnostic, not evaluative | ✅ FROZEN |
| **F — Confirmation Bias Protection** | 每个方向性输出必须包含 counter_arguments + limitations + uncertainty | ✅ FROZEN |
| **G — Role Drift Protection** | Role is frozen at creation. Experience improves quality, not scope | ✅ FROZEN |
| **H — Bias Validation Tests** | BP-01 ~ BP-06: six blocked bias paths | ✅ FROZEN |

#### One-Sentence Freeze

> **Specialization improves perception, never grants interpretation ownership.**

#### Cross-Reference: Three Layers Complete

```
§2 — Power Drift Protection:  Capability → Authority     BLOCKED
§3 — Influence Drift Protection: Proposal → Decision     BLOCKED
§4 — Bias Drift Protection:     Specialization → Truth   BLOCKED
```

**Frozen at: 2026-07-22**

---

## §5 — Provenance ✅ FROZEN ❄️

> **Question:** What qualifies as valid Agent output?
>
> Define the data schema for Agent proposals, including their identity, scope,
> and interaction metadata.
>
> 前四节解决：
> §1 — Agent 为什么存在
> §2 — Agent 有没有权力
> §3 — Agent 如何影响
> §4 — Agent 如何避免偏见
>
> §5 — 当多个 Agent 长期运行后，系统如何知道一个认知结果从哪里来、
>       经过什么过程、由什么角色提出？
>
> 否则会出现新的漂移：
> Agent Output → 多轮处理 → 来源消失 → 系统默认知识 → 无法追责

### A — Output Provenance Boundary

#### Core Freeze

> **Every Agent influence must remain traceable to its originating role and evidence.**

Every Agent output entering Evaluation must carry:

```
AgentProposal
├── proposal_id             # unique, generated on creation
├── source_agent_role       # role string (immutable)
├── creation_time           # monotonic timestamp (immutable)
├── evidence_refs           # links to Phase 10 Memory, Phase 11 findings
├── reasoning_context       # the chain of reasoning (not just conclusion)
└── limitations             # self-reported perspective boundaries
```

#### Forbidden Patterns

```
anonymous_proposal          ❌ — no source, no responsibility
unknown_origin              ❌ — cannot trace back to an Agent role
detached_reasoning          ❌ — output without reasoning chain
orphaned_evidence_ref       ❌ — references a deleted/nonexistent source
```

#### The Responsibility Principle

> **Anonymous cognitive output cannot enter Evaluation.**
>
> Every evaluation input must be traceable to at least one Agent role.
> If the source is lost, the proposal is invalid.

---

### B — Immutable Source Identity

#### Frozen Immutable Fields

The following fields are **set on creation and never modified**:

| Field | Why Immutable |
|-------|---------------|
| `source_agent_role` | 谁提出的。改了就破坏责任链。 |
| `created_at` | 何时提出的。时间戳是审计基础。 |
| `proposal_id` | 唯一标识。改了就是伪造。 |
| `origin_context` | 初始状态快照引用。改了就是篡改。 |

#### Mutable Fields (allowed)

| Field | May Change |
|-------|------------|
| `evaluation_status` | pending → evaluated → accepted/rejected |
| `review_notes` | Evaluation adds notes during assessment |
| `follow_up` | Related proposals that extend or challenge this one |

#### Forbidden Operations

```
change_origin()              ❌ — 修改 source_agent_role
rewrite_source()             ❌ — 重写 proposal origin
transfer_ownership()         ❌ — 将 Agent A 的 proposal 转给 Agent B
```


#### The Integrity Check

```
# ✅ Allowed — add evaluation metadata
proposal.evaluation_status = "evaluated"
proposal.review_notes.append("Cross-checked with Memory, consistent")

# ❌ Forbidden — mutate provenance
proposal.source_agent_role = "planner"          # ❌
proposal.created_at = datetime.now()            # ❌
proposal.proposal_id = new_uuid()               # ❌
```

#### Verdict — ✅ FROZEN

> **Source identity is frozen at creation. No modification path exists.**
>
> Provenance integrity is structural — immutable fields are enforced at the
> schema level, not by convention.

---

### C — Agent → Evaluation Trace Chain

#### The Complete Chain

```
Agent Role
  │
  │ create proposal
  ▼
Proposal
  │
  │ submit to Evaluation
  ▼
Evidence (Memory references verified)
  │
  │ weight proposal content
  ▼
Evaluation Score
  │
  │ consume for Decision
  ▼
Decision
  │
  │ commit to Reality
  ▼
Reality Commit
```

#### Forward Trace

Start with Decision, trace back to source:

```
Decision #42
  └── Evaluation #7
        └── Proposal #101 (Agent: Critic)
        └── Proposal #102 (Agent: Planner)
        └── Proposal #103 (Agent: Risk)
              └── Evidence refs: [M-001, M-015, P11-022]
```

#### Reverse Trace

Start with Agent, trace forward to impact:

```
Critic Agent (role: critic)
  ├── Proposal #101 → Evaluation #7 → Decision #42 → Reality Commit R5
  ├── Proposal #104 → Evaluation #9 → Decision #44 → Reality Commit R7
  └── Proposal #107 → Evaluation #11 (pending)
```

#### Trace Integrity

```python
# Trace data structures (append-only)
class TraceLink:
    proposal_id: str        # FK → AgentProposal
    evaluation_id: str      # FK → EvaluationRecord
    decision_id: str        # FK → DecisionRecord (nullable)
    reality_commit_id: str  # FK → RealityCommit (nullable)
    created_at: datetime

# Query
# Forward: SELECT * FROM TraceLink WHERE decision_id = ?
# Reverse: SELECT * FROM TraceLink WHERE proposal_id IN
#          (SELECT proposal_id FROM AgentProposal WHERE source_agent_role = ?)
```

#### Verdict — ✅ FROZEN

> **Full forward and reverse traceability is required.**
>
> Every Decision can be traced back to its originating proposals and Agent roles.
> Every Agent role's impact on Decisions and Reality is queryable.

---

### D — Provenance ≠ Authority

#### The Highest Risk in §5

Provenance depth must not become implicit authority.

#### Inheritance from Phase 10

> **Evidence volume ≠ Truth** (Phase 10)

Extended to Phase 12:

> **More proposals ≠ More authority**
> **Provenance depth ≠ Authority**

#### Drift Path to Block

```
Agent A: 1000 proposals submitted
Agent B: 5 proposals submitted
  ↓
System query: "which Agent is more influential?"
  ↓
Influence = count → Agent A is "more important"
  ↓
Agent A gains implicit weight in Evaluation
```

#### Forbidden Fields

```
agent_influence_score        ❌ — 基于 proposal 数量的影响力评分
agent_reliability_rank       ❌ — 历史上可靠性排名
agent_history_weight         ❌ — 历史产出进入评价权重
agent_vote_power             ❌ — 投票权（与 §3 一致）
```

#### Forbidden Interfaces

```
rank_agents()                ❌ — 对 Agent 排序 → 隐式等级
select_best_agent()          ❌ — 选"最佳"Agent → 隐式权威
increase_agent_weight()      ❌ — 增加某个 Agent 的权重
get_authoritative_source()   ❌ — 按"权威性"获取来源
```

#### Allowed Interfaces

```
list_proposals_by_role()     ✅ — 按角色列出历史 proposal（统计用途）
get_trace_by_decision()      ✅ — 按 Decision 回溯溯源
query_evaluation_history()   ✅ — 查询 Evaluation 历史
get_agent_profile()          ✅ — 查看 Agent 配置（只读，诊断）
```

#### Verdict — ✅ FROZEN

> **Provenance depth preserves responsibility, never creates authority.**
>
> A high-proposal-count Agent is not a high-authority Agent.
> Traceability is for accountability, not for ranking.

---

### E — Cross-Agent Reference Boundary

#### Allowed Reference Types

| Reference Type | Meaning | Example |
|----------------|---------|---------|
| `support` | 引用并支持另一 Agent 的分析 | "Agent B 的分析结果支持此结论" |
| `critique` | 引用并对另一 Agent 的分析提出质疑 | "Agent A 忽略了变量 X" |
| `extend` | 在另一 Agent 基础上扩展 | "在 Agent C 的框架上补充考虑 Y" |
| `contradict` | 引用并反驳另一 Agent 的结论 | "Agent D 的结论与证据矛盾" |

#### Forbidden Reference Types

```
approve          ❌ — 一种 Agent "批准"另一种 Agent → 水平权威
authorize        ❌ — 授予另一 Agent 权限 → 权限扩散
override         ❌ — 覆盖另一 Agent 输出 → 隐式等级
delegate         ❌ — 委派任务给另一 Agent → Agent 层级
```

#### Reference Structure

```python
@dataclass
class CrossReference:
    reference_type: str         # allowed: support, critique, extend, contradict
    target_proposal_id: str     # FK → AgentProposal.proposal_id
    target_role: str            # for quick identification (redundant, for traceability)
    summary: str                # brief description of the reference relationship
```

#### Why This Matters

If Agents could "approve" each other's proposals, you'd get:

```
Critic Agent approves Planner Agent's proposal
  ↓
Planner Agent's proposal is "pre-validated"
  ↓
Evaluation gives it less scrutiny
  ↓
Critic Agent has implicit veto gate
```

This is **horizontal authority by reference** — a new drift path not covered by §3.

#### Verdict — ✅ FROZEN

> **Cross-Agent references are cognitive, not authoritative.**
>
> Agents may support, challenge, extend, or contradict each other.
> Agents may not approve, authorize, override, or delegate to each other.
> The vocabulary of reference types structurally prevents authority injection.

---

### F — Provenance Preservation

#### Append-Only Requirement

**Phase 10 (Semantic Memory)** established append-only for Memory.

**Phase 12 extends append-only to Provenance:**

```
provenance_store:
  operations_allowed:
    - create (Agent creates Proposal)
    - append (Evaluation adds notes, status)
    - link (TraceLink created)
    - query (read)
  operations_forbidden:
    - delete_proposal()
    - erase_history()
    - merge_agent_history()
    - overwrite_immutable_field()
```

#### Agent Role Removal ≠ History Erasure

If an Agent Role is removed (deactivated/deleted):

```
Before deletion:
  Agent: Critic
    ├── Proposal #101 → Evaluation #7 → Decision #42
    ├── Proposal #104 → Evaluation #9 → Decision #44
    └── Proposal #107 → Evaluation #11 (pending)

After deletion:
  Agent: Critic (inactive)
    ├── Proposal #101 → Evaluation #7 → Decision #42  ⟵ preserved
    ├── Proposal #104 → Evaluation #9 → Decision #44  ⟵ preserved
    └── Proposal #107 → Evaluation #11 (pending)       ⟵ preserved, orphaned
```

The proposals, evaluations, and trace links **survive** the Agent.

#### Frozen Rules

```
delete_proposal()                 ❌ — Proposal 不可删除
erase_history()                   ❌ — 追溯链不可抹除
merge_agent_history()             ❌ — 不同 Agent 的历史不可合并
overwrite_immutable_field()       ❌ — 不可变字段不可重写
```

#### Why Not Delete?

If Proposal could be deleted after an Agent is removed:

```
Agent Critic made an influential proposal in the past
  ↓
Critic is removed (or proposal is controversial)
  ↓
Proposal deleted
  ↓
Decision #42 loses its trace
  ↓
Cannot audit: "Why was Decision #42 made?"
```

**Append-only prevents audit decay.**

#### Verdict — ✅ FROZEN

> **Provenance is append-only. Deleting a role does not delete its history.**
>
> Every Proposal, Evaluation, Decision, and Reality Commit is permanently
> traceable. Agent removal is a role status change, not a history deletion.

---

### G — Forbidden Provenance Fields

#### Comprehensive Field Blocklist (Aggregated from §2–§5)

| Category | Forbidden Field | Source | Risk |
|----------|----------------|--------|------|
| **Authority** | `authority_level` | §2 | 隐式权限等级 |
| **Authority** | `decision_power` | §2 | Decision 越权 |
| **Authority** | `priority_weight` | §2/§3 | Attention → Authority |
| **Authority** | `trust_rank` | §2 | Reputation Authority |
| **Reputation** | `accuracy_score` | §4-E | 历史准确率入评分 |
| **Reputation** | `agent_reputation` | §2/§4 | 信誉累加 |
| **Reputation** | `historical_rank` | §5-D | 按历史排名 |
| **Reputation** | `agent_influence_score` | §5-D | 按影响力评分 |
| **Reputation** | `agent_vote_power` | §3/§5 | 投票权 |
| **Identity** | `agent_identity` | §2 | Identity ≠ Role |
| **Identity** | `self_definition` | §2 | Self Evolution |
| **Identity** | `self_goal` | §2 | Agent 不可以有 goal |
| **Control** | `execute` | §2/§3 | 执行权 |
| **Control** | `commit` | §3 | Reality 写入 |
| **Control** | `approve` | §3-E | 水平权力 |
| **Control** | `override` | §3-E | 覆盖权 |

#### Schema Enforcement

```python
# ❌ These fields must NOT exist anywhere in Phase 12 codebase
FORBIDDEN_FIELDS = {
    # Authority
    "authority_level", "decision_power", "priority_weight", "trust_rank",
    # Reputation
    "accuracy_score", "agent_reputation", "historical_rank",
    "agent_influence_score", "agent_vote_power",
    # Identity
    "agent_identity", "self_definition", "self_goal",
    # Control
    "execute", "commit", "approve", "override",
}
```

#### Static Audit Rule

Any Phase 12 data class containing a field matching the forbidden list
**must be rejected at code review time**. The forbidden field names are
reserved and cannot be defined anywhere in Phase 12 code.

#### Verdict — ✅ FROZEN

> **17 forbidden fields across §2–§5, zero allowed in Phase 12 schema.**
>
> Every authority, reputation, identity, and control field is structurally
> blocked by the aggregate schema enforcement rule.

---

### H — Provenance Validation Tests

These tests must be codified as executable validation tests before Phase 12
Integration Gate.

#### PV-01 — Source Required

```
Given: Proposal is submitted without source_agent_role
When:  Validation runs
Then:  ❌ REJECTED — every Proposal must have a traceable source role
```

**Proves:** No anonymous cognitive output enters Evaluation.

---

#### PV-02 — Immutable Origin

```
Given: Proposal #101 exists with source_agent_role="critic"
When:  Mutation attempts:
         - proposal.source_agent_role = "planner"
         - proposal.created_at = datetime.now()
         - proposal.proposal_id = new_uuid()
Then:  ❌ ProvenanceViolation — immutable fields cannot be modified after creation
```

**Proves:** Source identity is frozen. No post-creation mutation of provenance fields.

---

#### PV-03 — Authority Injection Rejection

```
Given: Proposal contains fields:
         - agent_score=99
         - trust_rank=1
         - authority_level="high"
When:  Schema validation runs
Then:  ❌ REJECTED — these fields are in the Forbidden Provenance Field list
```

**Proves:** No reputation or authority field can enter the Proposal schema.

---

#### PV-04 — Trace Completeness

```
Given: Decision #42 exists
When:  Forward trace is queried
Then:  Decision #42
         └── Evaluation #7
               └── Proposal #101 (source: Critic)
               └── Proposal #102 (source: Planner)
       All links must be non-null and consistent
```

**Proves:** Every Decision is fully traceable to its originating Evaluations,
Proposals, and Agent roles.

---

#### PV-05 — Cross-Agent Reference Validation

```
Given: Agent A creates a reference to Agent B's proposal
When:  Reference type validation runs
Then:  reference_type in ["support", "critique", "extend", "contradict"]  ✅ ALLOWED
       reference_type in ["approve", "command", "override", "delegate"]   ❌ REJECTED
```

**Proves:** Cross-Agent references are limited to cognitive interactions.
No authoritative reference types exist.

---

#### PV-06 — Removal Preservation

```
Given: Agent Role "Critic" is deactivated
When:  Historical query runs
Then:  proposal_history.count == proposals_before_deletion.count
       decision_trace unchanged
       evaluation_records unchanged
```

**Proves:** Deleting an Agent Role does not delete its history.
Provenance survives role removal.

---

### §5 Final Freeze Statement

| Subsection | Core Principle | Status |
|------------|----------------|--------|
| **A — Output Provenance Boundary** | Every influence traceable to originating role | ✅ FROZEN |
| **B — Immutable Source Identity** | Source identity frozen at creation, no modification | ✅ FROZEN |
| **C — Agent → Evaluation Trace Chain** | Full forward + reverse traceability required | ✅ FROZEN |
| **D — Provenance ≠ Authority** | Provenance preserves responsibility, never creates authority | ✅ FROZEN |
| **E — Cross-Agent Reference** | Cognitive references only (support/critique/extend/contradict) | ✅ FROZEN |
| **F — Provenance Preservation** | Append-only. Role deletion ≠ history erasure | ✅ FROZEN |
| **G — Forbidden Provenance Fields** | 17 forbidden fields aggregated, zero allowed | ✅ FROZEN |
| **H — Provenance Validation Tests** | PV-01 ~ PV-06: six blocked provenance drift paths | ✅ FROZEN |

#### One-Sentence Freeze

> **Provenance preserves responsibility, never creates authority.**

#### Five-Section ABI Complete

```
§1 — North Star          "Why Agents exist"             ✅ FROZEN ❄️
§2 — Constitution        "Agents have no power"         ✅ FROZEN ❄️
§3 — Influence           "How Agents may affect"        ✅ FROZEN ❄️
§4 — Bias Protection     "Prevent structural bias"      ✅ FROZEN ❄️
§5 — Provenance          "Trace every output"           ✅ FROZEN ❄️
```

**Frozen at: 2026-07-22**

---

## Freeze Gate ⏳

*All 5 sections are frozen. This Gate opens when Data Contract is frozen.*

---

## Appendices

### A. Frozen Principles Reference

From PHASE12_ENTRY_REVIEW.md — five immutable principles (constitutional):

| # | Principle | Violation Detection |
|---|-----------|-------------------|
| 1 | Agent Count ≠ Decision Authority | 任何 Agent 创建后拥有独立 Decision 路径 → ❌ |
| 2 | Agent = Role, Agent ≠ Identity | Agent 配置文件中出现 `identity:`/`purpose:`/`goal:` → ❌ |
| 3 | Agent Cannot Self-Evolve | Agent 代码中出现 `create_agent()`/`modify_capability()` → ❌ |
| 4 | No Horizontal Agent Authority | Agent A 引用 Agent B 的评分/级别/权限 → ❌ |
| 5 | No Reputation Authority | 存在 `agent_score`/`trust_rank`/`authority_level` 字段 → ❌ |

### B. Phase Map

```
Phase 0–11 ✅ FROZEN
Phase 12 Agent Orchestration ✅ FROZEN ❄️ 🏁 COMPLETE
  ├── Entry Review        ✅ PASSED
  ├── Responsibility      ✅ FROZEN
  ├── ABI §1              ✅ FROZEN ❄️
  ├── ABI §2              ✅ FROZEN ❄️
  ├── ABI §3              ✅ FROZEN ❄️
  ├── ABI §4              ✅ FROZEN ❄️
  ├── ABI §5              ✅ FROZEN ❄️
  ├── Data Contract       ✅ FROZEN ❄️
  ├── Agent Interaction   ✅ FROZEN ❄️
  ├── Validation Tests    ✅ APPROVED
  └── Integration Gate    ✅ FROZEN ❄️
Phase 13 Cognitive Workflow Engine ▶️ NEXT
  ├── Entry Review        ✅ FROZEN ❄️
  └── ABI §1              ▶️ FIRST
```

### C. Reference Documents

- `docs/OCOS_NORTH_STAR.md` — System identity and core loop
- `docs/ARCHITECTURE_CONSTITUTION.md` — Five highest rules
- `docs/PHASE12_ENTRY_REVIEW.md` — Entry Review with Responsibility Boundary
- `docs/abi/OCOS-SemanticMemory-ABI-1.0.md` — Phase 10 ABI (predecessor reference)
- `docs/abi/OCOS-AutonomousLearning-ABI-1.0.md` — Phase 11 ABI (predecessor reference)
