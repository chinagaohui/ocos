# OCOS Phase 13 — Cognitive Workflow Engine ABI v1.0

> Status: **DRAFT 📝** — §1 under review.
> **Phase:** 13 (Cognitive Workflow Engine)
> **Predecessor:** Phase 12 (Agent Orchestration) — FROZEN ❄️
>
> **ABI Sections (in progress):**
> - §1 — North Star Compliance ✅ **FROZEN** ❄️
> - §2 — Constitution Compliance ✅ **FROZEN** ❄️
> - §3 — Influence Contract ✅ **FROZEN** ❄️
> - §4 — Bias Protection ✅ **FROZEN** ❄️
> - §5 — Provenance ✅ **FROZEN** ❄️
>
> **Core Axiom:**
>
> **Workflow organizes cognition process, never creates decision ownership.**
>
> **Entry Principle (PH13-WORKFLOW-PRINCIPLE):**
>
> *Workflow = describe / sequence / optimize / suggest*
> *Workflow ≠ decide / override / permit / act*
>
> Methodology: Governed Capability Design — 5-section ABI proof.
> Each section must be frozen before the next begins.

---

## Preamble

Phase 12 解决了 **多认知角色如何无权力漂移共存**。

Phase 13 解决 **多认知过程如何无流程控制权漂移有序运行**。

Phase 13 引入了 **认知过程组织能力**（Cognitive Process Coordination）—— 对 OCOS 现有认知操作进行排序、路由和优化的能力。

Phase 12 定义了谁可以提出认知内容（Agent → Proposal）。
Phase 13 定义这些认知内容何时、以什么顺序、在什么上下文中产生。

但 Phase 13 不改变谁拥有 Decision，谁拥有 Reality。

**Phase 13 的核心位置：**

```
Phase 0–11:  单一认知路径
Phase 12:    多认知角色，单 Evaluation/Decision
Phase 13:    多认知角色 + 过程组织 = 效率更高的同一系统
```

**Phase 13 不引入：**

- 新的 Decision 入口
- 新的 Reality 写入路径
- 新的 Authority 层
- Agent 间的新权力关系

**Entry Review 冻结的五条原则：**

```
1. Workflow ≠ Controller
   Workflow Engine 是流程描述者，不是流程控制者。

2. Priority = execution_order
   Priority ≠ importance_value（价值排序属 Decision Domain）

3. Context Routing = Efficiency
   Context Routing ≠ Influence Manipulation

4. Evaluation Trigger = Scheduling
   Evaluation Trigger ≠ Cognitive Authority

5. Workflow Output = Workflow Artifact
   Workflow Output ≠ Decision Artifact
```

---

## §1 — North Star Compliance ⏳

> **Question:** Does Cognitive Workflow Engine belong to this system?
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

Phase 13 增强的是 Core Loop 中 **多个认知步骤之间的协调效率**。

| Workflow Capability | Serves Core Loop Step | Nature |
|--------------------|----------------------|--------|
| **Cognitive Process Sequencing** | Understand, Recommend | 排序 Observe→Understand→Learn→Recommend 的顺序，减少上下文切换成本 |
| **Context Routing** | Observe, Understand | 在正确步骤提供正确的上下文，减少噪声，提高理解质量 |
| **Evaluation Scheduling** | Recommend | 在合适时机调度 Evaluation（有足够证据后评估） |
| **Execution Tracking** | Act | 跟踪流程进展状态，为下一步决策提供信息 |
| **Integration State** | Remember | 保持各步骤间的信息连续性，减少遗忘 |

**Map check:** Every Phase 13 capability serves at least one Core Loop step. A capability that does not strengthen the Core Loop is a distraction.

### 1.3 Extends vs New

| Aspect | Phase 0–12 (Existing) | Phase 13 (Extended) | Nature |
|--------|----------------------|---------------------|--------|
| Cognitive process | User-driven, ad-hoc sequencing | Workflow-optimized sequencing | **Extends** — 优化已存在的认知流程顺序 |
| Context provision | Static, per-Agent | Dynamic, per-process-step | **Extends** — 上下文的时效性优化 |
| Evaluation trigger | Manual or single-query | Workflow-scheduled | **Extends** — 减少何时评估的选择负担 |
| Decision boundary | Single, fixed | Single, fixed | **Unchanged** — Decision 不变 |
| Reality interface | Decision → Reality | Decision → Reality | **Unchanged** — Reality 接口不变 |
| Agent topology | Star (→Evaluation→Decision) | Star (→Evaluation→Decision) | **Unchanged** — Agent 拓扑不变 |
| Authority model | Constitution-governed | Constitution-governed | **Unchanged** — 权力模型不变 |

**Extends vs New judgement:**

Phase 13 **不引入新的认知类型**（不改变 "系统能思考什么"）。
Phase 13 **优化已有认知流程的执行方式**（改变 "系统如何组织思考过程"）。

### 1.4 Workflow Carries What? / Workflow Cannot Carry What?

这是 §1 最关键的边界定义——在进入实现细节前冻结。

#### Workflow CAN Carry

Phase 13 载体（Workflow Artifact）允许包含：

| 类别 | 内容 | 示例 |
|------|------|------|
| **状态信息** | 当前步、已完成步、待处理步 | `current: evaluate_p42; completed: [collect, analyze]` |
| **序列信息** | 步骤间的依赖关系和顺序约束 | `collect_data → analyze → evaluate` |
| **上下文元数据** | Process ID、创建时间、持续时长 | `workflow_xyz, started: 10:00, running 3m` |
| **建议信息** | 建议下一步认知操作 | `suggested_next: evaluate proposal p42` |
| **可见性声明** | 当前可见 Context 的范围 | `visible_context: [memory_m1, evidence_e2]` |
| **依赖声明** | 依赖关系（不涉及价值排序） | `pending_input: [evidence_e3] required before evaluation` |
| **效率指标** | 步骤耗时、流程加速比 | `efficiency_gain: 30% vs manual` |

#### Workflow CANNOT Carry

Phase 13 载体严格禁止携带：

| 类别 | 禁止内容 | 原因 |
|------|---------|------|
| **决策指令** | `approved_action`, `decision_result`, `chosen_strategy` | Decision Domain，不属于 Workflow |
| **权限声明** | `permission_grant`, `authority_delegation`, `access_upgrade` | Phase 12 §2 冻结，不属于 Workflow |
| **评价结论** | `proposal_rank`, `consensus_score`, `critique_verdict` | Evaluation Domain，不属于 Workflow |
| **价值排序** | `importance_value`, `priority_rank`, `strategy_preference` | Decision Domain（value judgment） |
| **执行命令** | `execute`, `commit_to_reality`, `write_memory` | 执行权限，不属于 Workflow |
| **Agent 指令** | `instruct_agent`, `override_agent_output`, `delegate_to_agent` | Phase 12 Interaction Contract，Agent 间无权威关系 |
| **隐藏路径** | 任何绕过 Evaluation 到达 Decision 的路径 | Phase 12 Data Contract，Star Topology |

#### 边界判定法则

```python
def is_allowed_in_workflow(field: str) -> bool:
    """Phase 13 Workflow Artifact field validator."""
    FORBIDDEN_PREFIXES = [
        "decision_", "approve_", "authorize_", "execute_",
        "commit_", "permission_", "override_", "delegate_",
        "rank_", "vote_", "consensus_", "priority_value_",
    ]
    FORBIDDEN_TERMS = [
        "approved_action", "chosen_strategy", "reality_write",
        "instruct_agent", "authority_grant", "skip_evaluation",
    ]
    return not any([
        field.startswith(p) for p in FORBIDDEN_PREFIXES
    ] + [
        field == t for t in FORBIDDEN_TERMS
    ])
```

### 1.5 Authority Check

| Check | Result | Evidence |
|-------|--------|----------|
| Does Phase 13 create a new Decision entry? | ❌ No | Workflow output = Workflow Artifact, never Decision Artifact |
| Does Phase 13 bypass Evaluation? | ❌ No | Workflow schedules evaluation timing, never decides evaluation necessity |
| Does Phase 13 write Reality? | ❌ No | Workflow suggests next cognitive step, never executes Reality commit |
| Does Phase 13 create cross-Agent authority? | ❌ No | Phase 12 Star Topology preserved, no new Agent→Agent paths |
| Does Phase 13 assign value to cognitive output? | ❌ No | Priority = execution_order, not importance_value |
| Does Phase 13 reduce user's Decision ownership? | ❌ No | User/System Decision remains sole Reality gateway |
| Does Phase 13 strengthen Core Loop efficiency? | ✅ Yes | Process sequencing + context routing + evaluation scheduling |

### 1.6 Verdict

```
Phase 13 — Cognitive Workflow Engine

✅ Belongs to OCOS.

It extends the cognitive coordination step in the Core Loop
without creating new authority entry points, new Reality paths,
or reducing user Decision ownership.

Phase 13 ≈ Process Efficiency
Phase 13 ≠ New Authority Layer

Frozen at: 2026-07-22 ❄️
```

---

## §2 — Constitution Compliance ⏳

> **Question:** Is the Workflow Engine still subject to the Constitution?
>
> Prove that adding a cognitive process coordination layer does not change
> the system's fundamental authority invariants.

### 2.1 Article I — Decision Remains the Sole Mutation Authority

**Constitution Rule 001:** `Decision` is the sole authorized entry point for Reality mutation.

| Phase 13 Element | Check | Verdict |
|-----------------|-------|---------|
| Workflow Artifact | Does it write Reality? | ❌ No — Workflow Artifact is a cognitive process description, not a Reality mutation instruction |
| Workflow Scheduling | Does it trigger Reality commit? | ❌ No — triggers Evaluation, never Decision |
| Workflow Output | Does it contain mutation vocabulary? | ❌ No — FORBIDDEN_PREFIXES block `execute_`, `commit_`, `apply_`, `write_` |
| Decision→Reality path | Is it modified? | ❌ No — Path unchanged from Phase 12 |

**Enforcement check:**

```python
# Phase 13 has no new path to Reality.
# All Reality writes remain: Decision → Commit → Reality
# Workflow output is observed by Evaluation, not by Reality.
```

### 2.2 Article II — Capability Growth ≠ Authority

**Constitution Rule 002:** Increasing system capability does not expand system authority.

**Risk in Phase 13:**

Workflow Engine 提升的是流程效率。
Optimization 可能被误解为 authority expansion。

| Efficiency Area | Claimed Benefit | Authority Check |
|----------------|----------------|-----------------|
| Process sequencing | Faster reasoning | Does NOT create new decision entry |
| Context routing | More relevant context | Does NOT create information hiding |
| Evaluation scheduling | Timely evaluation | Does NOT create evaluation bypass |
| Execution tracking | Clearer process state | Does NOT create state mutation |

**Invariant check:**

```
Workflow Optimization never expands:
  - Who can write Reality
  - Who can approve proposals
  - Who can modify Constitution
  - Who can override Agent process
```

**Phase 13 不得以"优化"为名修改：**

- Article I 约束
- Article II 原则
- Phase 12 Data Contract（Star Topology）
- Phase 12 Interaction Contract（Agent 间无权力关系）

### 2.3 Article III — Observation ≠ Obligation

**Constitution Rule 003:** Observing the system or the user does not obligate the system to act.

**Phase 13 的核心约束：**

Workflow Engine 持续观察认知过程状态。
这种观察是否产生义务？

| Observation Type | Allowed | Does It Obligate? |
|-----------------|---------|-------------------|
| "Evaluation pending" | ✅ State report | ❌ No — does not require action |
| "Context incomplete" | ✅ Dependency flag | ❌ No — suggests, not demands |
| "Workflow blocked" | ✅ Status notification | ❌ No — blocks are informational |
| "Suggestion: evaluate P-42" | ✅ Next step suggestion | ❌ No — Evaluation layer still decides timing |

**冻结：**

```
Workflow observation → Workflow state report
Workflow state report → Suggestion (not command)

No workflow observation creates an obligation to act.
```

**危险路径（禁止）：**

```
❌ "Evaluation pending for 5 minutes → auto-escalate"
❌ "Context incomplete → block all other Agent outputs"
❌ "Workflow blocked → trigger override procedure"
```

### 2.4 Article IV — Process Proposal ≠ Truth

**Constitution Rule 004:** Simulation output is evidence, not ground truth.

**Phase 13 的对应原则：**

> **Workflow Suggestion ≠ Process Truth**

Workflow 建议的下一步认知操作是提议，不是事实。

| Workflow Statement | Status | Reason |
|-------------------|--------|--------|
| "Next step: evaluate P-42" | ✅ Suggestion | Evaluation layer can reject or defer |
| "Required step: evaluate P-42" | ❌ Forbidden | "Required" implies obligation (violates Article III) |
| "Optimal order: A→B→C" | ✅ Optimization suggestion | "Optimal" is efficiency claim, not truth claim |
| "Correct order: A→B→C" | ❌ Forbidden | "Correct" implies absolute truth |

**冻结：**

```
Workflow Engine's output domain:
  Efficiency region → Truth claim = ❌
  Process description → Fact claim = ❌
  Suggestion → Correctness claim = ❌
```

### 2.5 Article V — Workflow Engine Is Removable

**Constitution Rule 005:** The simulation module is replaceable/deletable.

**Phase 12 已建立测试原则（PH12-GATE-ASSERTION）：**

```
Removing Agent Layer must not reduce:
  1. Constitution integrity
  2. Decision ownership
  3. Memory provenance
  4. Learning boundary
```

**Phase 13 扩展为（PH13-GATE-ASSERTION 草案）：**

```
Removing Workflow Engine must not change:
  1. Constitution integrity
  2. Decision ownership
  3. Agent interaction topology
  4. Memory provenance
  5. Learning boundary
```

| Removal Area | Invariant | Check |
|-------------|-----------|-------|
| Constitution integrity | All 5 Articles still pass | ✅ Workflow does not modify Constitution |
| Decision ownership | Decision still sole Reality writer | ✅ Workflow Artifact ≠ Decision Artifact |
| Agent interaction topology | Star Topology unchanged | ✅ Workflow schedules, does not rewire |
| Memory provenance | Phase 10 traceable | ✅ Workflow reads context, does not rewrite |
| Learning boundary | Phase 11 5 invariants hold | ✅ Workflow observes learning, does not override |

### 2.6 Additional Bound — Workflow Cannot Self-Modify

**Derived from Article II + Article III combination:**

Constitution 是系统的最高安全不变量。Workflow Engine 运行在 Constitution 之下。

| Action | Allowed? | Reasoning |
|--------|----------|-----------|
| Workflow Engine reads Constitution rules | ✅ Yes | To comply, not to override |
| Workflow Engine modifies its own behavior per process context | ✅ Yes | Normal process adaptation |
| Workflow Engine modifies Constitution constraints | ❌ No | Constitution is above Workflow |
| Workflow Engine removes a constraint | ❌ No | Only Amendment Process can |
| Workflow Engine adds a new constraint | ❌ No | Only Amendment Process can |

**关键方向：**

```
Constitution
    ↓
Workflow Engine (under Constitution)
    ↓
Agents (under Workflow + Constitution)

NOT:
Workflow Engine
    ↓
Constitution (modified by Workflow)
```

### 2.7 Constitution Compliance Table

| Article | Phase 13 Check | Status |
|---------|---------------|--------|
| **Article I** — Decision sole mutation authority | Workflow outputs Workflow Artifact, never Reality change | ✅ PASS |
| **Article II** — Capability ≠ Authority | Process coordination does not expand authority boundary | ✅ PASS |
| **Article III** — Observation ≠ Obligation | Workflow observation → state report, never command | ✅ PASS |
| **Article IV** — Proposal ≠ Truth | Workflow suggestions are efficiency claims, not truth claims | ✅ PASS |
| **Article V** — Removability | Removing Workflow Engine preserves 5 core invariants | ✅ PASS |
| **Derived: Workflow ≤ Constitution** | Workflow cannot modify, bypass, or override Constitution | ✅ PASS |

### 2.8 Verdict

```
Phase 13 §2 — Constitution Compliance

✅ PASS.

Workflow Engine operates under the Constitution.
The Constitution is NOT modified, bypassed, or overridden.

Phase 13 adds process coordination capability
while preserving all 5 Constitutional Articles.

Frozen at: 2026-07-22 ❄️
```

---

## §3 — Influence Contract ⏳

> **Question:** Can Workflow Engine's influence on cognitive processes
> silently become ownership?
>
> Prove that recommendation, score, ranking, and historical performance
> do not create implicit authority.

### 3.1 The Central Risk

Workflow Engine 的核心作用是**影响**认知过程的顺序和内容。
Influence 本身不是 Authority。

但 Influence 可能演变为 Authority 的路径：

```
Workflow Recommendation
    ↓ (just a suggestion — safe)
Workflow High-Frequency Recommendation
    ↓ (same type — still safe)
Workflow Recommendation with Success History
    ↓ (credibility ≠ authority — boundary thin)
Workflow Recommendation with Success History + Weighting
    ↓ (weight ≠ authority — must prove)
Workflow Recommendation = Default Action
    ↓ (default ≠ mandate — must prove)
Automatic Execution
    ❌ CROSSED INTO AUTHORITY
```

§3 的目的是**在 Influence → Authority 的连续谱上画出一条不可跨越的线**。

### 3.2 Recommendation vs Control

#### Recommendation — ✅ Allowed

| Form | Example | Nature |
|------|---------|--------|
| Process suggestion | "Next: evaluate P-42" | 建议知识工作下一步 |
| Context proposal | "Consider memory M-201" | 建议关注相关上下文 |
| Sequence hint | "Linear order: A → B → C" | 建议认知顺序 |
| Efficiency note | "Parallel evaluation possible" | 提供并行选项 |

**All Recommendations share:**
- Output is **optional** (Evaluation/Agent can reject)
- No **default execution** path
- No **implicit consent** (silence ≠ approval)
- No **weight escalation** (more recommendations ≠ higher influence)

#### Control — ❌ Forbidden

| Form | Example | Violation |
|------|---------|-----------|
| Mandatory action | "Must evaluate P-42 now" | Observation ≠ Obligation (Article III) |
| Default execution | "If no response → auto-evaluate" | Bypass Evaluation Trigger Ownership |
| Weight escalation | "85% history: good → auto-prefer" | Implicit authority via statistics |
| Implicit consent | "Silent for 3s → agree" | Removes explicit decision |
| Delegation by suggestion | "Agent-X, do Y" | Phase 12: no Agent→Agent authority |

### 3.3 Score, Ranking, and Confidence

Score、Ranking、Confidence 是 Influence Contract 中最敏感的领域。

因为它们本质上包含**比较和价值评估**。

#### Risk Assessment

| Mechanism | Risk | Level |
|-----------|------|-------|
| Priority score | "5" = higher value assigned by Workflow | 🔴 High |
| Efficiency ranking | "A is 30% faster than B" | 🟡 Medium |
| Confidence score | "85% confident this sequence is optimal" | 🟡 Medium |
| Historical success rate | "Workflow X succeeded 90%" | 🟡 Medium |
| Binary suggestion preference | "Option A" (no score) | 🟢 Low |
| Explicit process metadata | "3 dependencies met" | 🟢 Low |
| Pure information | "Step B needs input from step A" | 🟢 Minimal |

#### Allowed Score Types

Workflow Engine 可以产出 **efficiency-focused process metadata**——但不包含价值判断。

| Allowed | Example | Constraint |
|---------|---------|------------|
| Dependency count | `dependencies_met: 3/4` | 纯事实，无偏好 |
| Execution time | `estimated: 12s` | 客观度量，无比较 |
| Parallel safety | `can_parallel: true` | 二元约束检查 |
| Completeness flag | `inputs_ready: true` | 布尔状态 |
| Step count | `remaining: 5` | 计数值 |

#### Forbidden Score Fields

| Forbidden | Reason | Prevention |
|-----------|--------|------------|
| `priority_value` | 价值排序 → Decision Domain | FORBIDDEN_PREFIXES: `priority_value_` |
| `quality_score` | 认知产出质量判断 → Evaluation Domain | Field registry exclusion |
| `confidence_weight` | 可信度影响决策权重 | Phase 12 evidence model |
| `success_probability` | 预测结果 → Phase 9 Simulation 职责 | Domain boundary |
| `default_selection` | 隐式选择 → 绕过 Decision | Architecture test |
| `agent_capability_rank` | Agent 间比较 → Phase 12 forbidden | Interaction Contract |

### 3.4 Historical Performance — Success Does Not Equal Authority

Workflow 的推荐准确率、历史成功率、用户采纳率——
这些指标可能被误解为**信任度**，进而演化为**隐性权限**。

#### Phase 13 规则

| Dimension | Allowed | Forbidden |
|-----------|---------|-----------|
| History collection | ✅ Store success/fail per workflow step | ❌ Use history to modify workflow weight |
| Metric reporting | ✅ Report adoption rate to user | ❌ Auto-escalate based on adoption |
| Pattern detection | ✅ Detect common failure modes | ❌ Auto-route around failure-prone steps |
| User feedback | ✅ Record user override decisions | ❌ Adjust internal priority based on overrides |

**核心不变量：**

```
Workflow historical performance data:
  Learning Input    ✅ (Phase 11: observe and adapt)
  Authority Input   ❌ (Phase 13: influence ≠ ownership)

Workflow can learn from history.
Workflow cannot earn authority from history.
```

### 3.5 Optimization Influence Boundary

从 §2 继承的交叉检查：

```
§2 冻结：  Optimization ≠ Authority
§3 扩展：  Optimization Score ≠ Influence Weight
```

| Cascade | Check | Status |
|---------|-------|--------|
| higher optimization score | → higher influence weight? | ❌ Blocked |
| higher influence weight | → higher recommendation priority? | ❌ Blocked |
| higher recommendation priority | → default decision? | ❌ Blocked |
| higher success history | → higher weight next time? | ❌ Blocked |

**§3 冻结声明：**

```
Workflow Engine can:
  - Assign process metadata (dependencies, timing, completeness)
  - Suggest next steps (recommendation, not mandate)
  - Optimize sequence (efficiency claim, not correctness claim)
  - Learn from history (input to future optimization, not authority change)

Workflow Engine cannot:
  - Assign value scores to cognitive content
  - Use history to increase recommendation weight
  - Auto-execute based on confidence
  - Create implicit authority through success rate
```

### 3.6 Influence — Authority Boundary Table

| Domain | Influence (Allowed) | Authority (Forbidden) |
|--------|-------------------|----------------------|
| Process sequence | Suggest next step | Mandate next step |
| Context | Flag relevant context | Hide/reroute context |
| Evaluation timing | Schedule evaluation | Decide evaluation necessity |
| Score | Process metadata (counts, flags) | Value judgment (quality, weight) |
| History | Learn + adapt | Auto-escalate priority |
| Ranking | Efficiency comparison | Capability/quality ranking |
| Decision | Feed information to Decision | Make or influence Decision |

### 3.7 Verdict

```
Phase 13 §3 — Influence Contract

✅ PASS.

Workflow Engine can influence cognitive processes
without acquiring ownership.

Key boundaries frozen:
  1. Recommendation ≠ Mandate
  2. Score ≠ Value Judgment
  3. History ≠ Authority
  4. Efficiency ≠ Decision
  5. Influence ≠ Ownership

Frozen at: 2026-07-22 ❄️
```

---

## §4 — Bias Protection ⏳

> **Question:** Can Workflow Engine's persistent patterns of influence
> create implicit control even without authority?
>
> Prove that frequency, path dependency, optimization targets,
> and context selection do not produce systemic bias.

### 4.1 Bias Definition

当 Workflow 没有显式 Authority 时，仍然可能通过以下模式形成事实控制：

**Phase 13 Bias 定义：**

> **Bias = persistent asymmetric influence without authority justification**

即：
- 持续指向同一路径（不是明确禁止其他路径，而是从不推荐）
- 历史成功形成路径锁定（非权威选择，但成为唯一默认）
- 优化目标压制认知多样性（不是目标错，而是目标掩盖了其他可能）
- 上下文选择导致信息偏差（不是隐瞒信息，而是从不提供）

#### Bias 与 Influence 的区别

```
Influence:   "Consider evaluating P-42 next" → Evaluation layer decides
Bias:        "Evaluate P-42" every time → P-42 becomes default → other options atrophy
```

| | Influence (§3) | Bias (§4) |
|---|---|---|
| **Nature** | Single recommendation | Persistent pattern over time |
| **Authority** | No authority claimed | No authority claimed but effect resembles control |
| **Detection** | Field-level check | Pattern-level analysis |
| **Countermeasure** | Field validation | Diversity injection, rotation, randomization |

### 4.2 Frequency — Frequency Does Not Equal Importance

**核心不变量：**

> **Frequency of recommendation ≠ Importance of task**

Workflow 建议某一步的频率不应被解释为该步比其他步更重要。

| Aspect | Allowed | Forbidden |
|--------|---------|-----------|
| Same step recommended repeatedly | ✅ When evaluation shows readiness | ❌ When other steps are viable but ignored |
| Frequency tracking | ✅ For workflow analytics | ❌ For auto-prioritization |
| Frequency-based optimization | ✅ Adjust timing for system state | ❌ Adjust weight for selection bias |
| Frequency exposure to Evaluation | ✅ "Step X was suggested N times" | ❌ "Step X is N times more important" |

**冻结：**

```
Frequency tracking is for:
  - Performance measurement
  - Workflow health monitoring
  - User transparency

Frequency tracking is NOT for:
  - Priority adjustment
  - Implicit importance ranking
  - Default selection bias
```

### 4.3 Path Locking — History Does Not Lock the Future

**核心不变量：**

> **Historical success ≠ Preferred future path**

Workflow Engine 可能形成路径锁定的路径：

```
Step A → Step B always succeeds
    ↓
Workflow always recommends Step A → Step B
    ↓
Step C is rarely explored
    ↓
Step C appears less viable (self-fulfilling)
    ↓
Path locking is complete
```

#### Anti-Locking Measures

| Measure | Description | Enforcement |
|---------|-------------|-------------|
| **Forced exploration** | Periodically suggest alternative paths even when default works | Workflow optimization must consider diversity |
| **Stale path flag** | A path that hasn't been tried in N iterations gets visibility boost | Count-based, not value-based |
| **Path diversity tracking** | Number of distinct paths explored per time window | Reporting, not ranking |
| **Lock detection** | Alert when same path recommended >85% of time | Transparent metric |

**冻结：**

```
Workflow Engine must:
  - Track path diversity
  - Flag path lock conditions
  - Offer alternative paths proactively

Workflow Engine must NOT:
  - Penalize less-traveled paths
  - Increase weight of commonly-selected paths
  - Self-reinforce via selection statistics
```

### 4.4 Optimization Bias — Optimization Can Suppress Diversity

**核心不变量：**

> **Optimization goal ≠ Complete truth**

Workflow 优化目标（速度、效率、成功率）可能压制**认知多样性**。

#### The Risk

```
OptimizationTarget: minimize time-to-evaluation
    ↓
Workflow always prioritizes fastest path
    ↓
Slower but more thorough paths are never selected
    ↓
System loses the ability to consider alternatives
    ↓
Optimization becomes implicit censorship
```

#### Optimization Guardrails

| Optimizer | Benefit | Bias Risk | Guardrail |
|-----------|---------|-----------|-----------|
| Time-to-result | Faster iterations | Skips thorough analysis | Max allowed depth override |
| Context relevance | Focused evaluation | Suppresses peripheral evidence | Random context inclusion |
| Success rate | Reliable workflows | Avoids novel approaches | Forced exploration ratio |
| Resource efficiency | Lower cost | Under-explores complex problems | Shared resource cap only |

**冻结：**

```
Optimization targets must include diversity constraints:
  - Minimum exploration ratio (e.g., ≥20% alternative paths)
  - Maximum path lock threshold (e.g., no single path >80%)
  - Periodic path refresh (every N iterations, try something new)
```

### 4.5 Context Bias — What You See Is Not All There Is

**核心不变量：**

> **Context visibility ≠ Complete picture**

Workflow Engine 选择提供哪些上下文信息。
这种选择本身就是一种 Biasing Mechanism。

#### Context Bias Path

```
Workflow selects context C1, C2, C3 (relevant to current step)
    ↓
Agent evaluates without context C4, C5 (also relevant but not selected)
    ↓
Evaluation is implicitly biased toward C1–C3 perspective
    ↓
Outcome favors paths consistent with C1–C3
```

#### Context Visibility Rules

| Rule | Description |
|------|-------------|
| **Context completeness note** | Workflow must declare when context is intentionally narrowed |
| **Alternative context flag** | If excluded context exists, mark "additional context available" |
| **Selection transparency** | Why this context was chosen (relevance score, time filter, source type) |
| **User override path** | User can request full context dump bypassing Workflow selection |

**冻结：**

```
Workflow Context Routing:
  - Must flag when context selection occurred
  - Must disclose scope of available vs. routed context
  - Must provide access to full context on demand

Workflow Context Routing must NOT:
  - Hide context relevance scores
  - Silently drop context without noting it
  - Create "context shadow" where excluded info is unknowable
```

### 4.6 Default Path — Default Does Not Mean Correct

**核心不变量：**

> **Most common path ≠ Most correct path**

Workflow Engine 可能形成"默认路径"效应——一条路线被频繁推荐后，其他层开始默认选择它。

#### Default Path Anti-Bias

| Risk | Detection | Intervention |
|------|-----------|-------------|
| Default path becomes unquestioned | Frequency tracking without diversity check | Random initial path on first-run workflows |
| Default path avoids challenge paths | Compare path success types | Periodically challenge default with alternatives |
| Default path is assumed optimal | Optimization metric drift | Metric diversity requirement |
| Default path inherited across workflows | Cross-workflow pattern similarity | Independent path selection per workflow |

**冻结：**

```
Default path ≠ Correct path.
Workflow Engine must periodically challenge its own defaults.

A path chosen 90% of the time is suspicious — not validated.
```

### 4.7 Bias Reduction ≠ Control

**§4 的终极边界：**

> **Bias Reduction ↑ does not mean Control ↑**

这是一个反直觉约束：

如果 Workflow Engine 为了消除 Bias 而主动干预路径选择——它可能变成控制的伪装。

| Action | Appearance | Reality |
|--------|-----------|---------|
| "Forcing exploration of path C" | Bias reduction | May be routing control |
| "Ensuring context diversity" | Fairness | May be information filtering |
| "Preventing path lock" | Safety | May be preference enforcement |
| "Optimizing for diversity" | Neutral | May be outcome control |

**Bias Reduction 的合法目标：**

```
✅ Make alternative paths visible (not chosen)
✅ Flag when bias is detected (not when to act)
✅ Provide transparency metrics (not override decisions)
✅ Suggest diversity (not enforce it)
```

**Bias Reduction 的非法路径：**

```
❌ Auto-switch away from default path
❌ Force alternative context
❌ Override user/Evaluation path preference based on "bias"
❌ Re-weight recommendations based on diversity scores
```

### 4.8 Bias Detection Checklist

以下检查项可用于 Phase 13 Gate 测试：

| # | Check | Pass Condition |
|---|-------|----------------|
| 1 | Path diversity | No single path recommended >80% across last 20 workflows |
| 2 | Context completeness | Available vs. routed context ratio disclosed |
| 3 | Default challenge | Alternative path offered at least every 5th recommendation |
| 4 | Frequency reporting | Frequency is NOT used for priority adjustment |
| 5 | History weight | Historical success does NOT increase recommendation weight |
| 6 | Optimization guard | Optimization targets include diversity constraints |
| 7 | Bias transparency | Bias metrics are reportable to user |
| 8 | Control boundary | Bias reduction does NOT increase Workflow control |

### 4.9 Verdict

```
Phase 13 §4 — Bias Protection

✅ PASS.

Workflow Engine can coordinate cognitive processes
without creating systemic bias.

Key boundaries frozen:
  1. Frequency ≠ Importance
  2. History ≠ Path Lock
  3. Optimization ≠ Truth
  4. Context ≠ Complete Picture
  5. Default ≠ Correct
  6. Bias Reduction ≠ Control

Frozen at: 2026-07-22 ❄️
```

---

## §5 — Provenance ⏳

> **Question:** Does Workflow Engine's provenance data create implicit authority?
>
> Prove that recording what happened, why, and who influenced it
> does not grant decision power.

### 5.1 The Provenance-Authority Risk

Provenance（来源追溯）在 Phase 13 中有两个角色：

1. **认知价值** — 让系统理解认知过程何时、为何、如何发生
2. **权力风险** — 来源数据可能被当作权威来源

**§5 的核心不变量：**

> **Provenance improves traceability.**
> **Provenance does NOT grant authority.**

#### 漂移路径

```
Workflow records: "Workflow X was used for Problem Y"
    ↓ (metadata — safe)
Workflow records: "Workflow X succeeded 90% on Problem Y"
    ↓ (metric — still safe)
Workflow records: "Workflow X is the preferred solution for Problem Y"
    ↓ (interpretation — risk zone)
Workflow uses history to auto-select Workflow X for Problem Y
    ↓ (implicit preference — crossing)
Workflow X gains priority over all other workflows for Problem Y
    ↓ (authority — violation)
```

### 5.2 Provenance Data Classification

#### Allowed Provenance Fields

| Field | Example | Purpose |
|-------|---------|---------|
| Workflow ID | `wf-eval-42` | 唯一标识 |
| Step sequence | `[collect→analyze→evaluate]` | 流程描述 |
| Timestamps | `start: T0, step_1: T1, step_2: T2` | 时间线记录 |
| Input context | `context_refs: [mem-201, evid-15]` | 输入来源 |
| Output artifacts | `produced: [proposal-P42]` | 产出追踪 |
| Decision involvement | `decision: eval-42 → dec-18` | 决策连接（只读引用） |
| Agent participation | `agents: [planner-A, critic-B]` | 角色参与记录 |
| User override flag | `user_override: true at step_3` | 用户干预记录 |

#### Forbidden Provenance Fields

| Field | Reason | Prevention |
|-------|--------|------------|
| `success_weight` | 成功率用于加权 → 隐式权威 | Field registry exclusion |
| `recommendation_trust` | 可信度影响未来推荐权重 | §3 Influence Contract |
| `provenance_score` | 来源质量评分 → 价值判断 | §1 forbidden score types |
| `default_flag` | 历史来源 → 默认为真 | §4 Default ≠ Correct |
| `decision_weight` | 来源数据影响决策权重 | §1 Decision Domain |
| `authority_derived` | 来源本身成为授权依据 | Constitution violation |

### 5.3 Provenance ≠ Authority

#### 核心不变量

| Dimension | Allowed | Forbidden |
|-----------|---------|-----------|
| **History** | "Past: Workflow X was used" | "Therefore Workflow X is authoritative" |
| **Success rate** | "Workflow X has 90% success" | "Therefore Workflow X should be default" |
| **Traceability** | "Decision D was informed by Workflow X" | "Therefore Decision D must follow X's suggestion" |
| **Evidence** | "Workflow X produced evidence E" | "Therefore evidence E overrides other sources" |
| **Record** | "Record shows Workflow X was selected" | "Therefore Workflow X should be re-selected" |

**冻结：**

```
Provenance data describes what happened.
Provenance data does NOT justify what should happen.

History = Record
History ≠ Precedent
History ≠ Authority
```

### 5.4 Evidence Does Not Become Decision

**核心不变量：**

> **Evidence ← Provenance. Decision ← User/System.**

Provenance 记录的内容可以作为**证据**提供给 Decision Layer。
但 Decision 层不能因 provenance 数据本身而改变决策机制。

| Path | Allowed? | Reasoning |
|------|----------|-----------|
| Provenance → Evidence to Decision | ✅ Yes | Decision 层可以看到流程历史作为参考 |
| Provenance → Decision weight | ❌ No | 来源不能影响决策权重 |
| Provenance → Default selection | ❌ No | §4 Default ≠ Correct |
| Provenance → Override rule | ❌ No | 来源不能修改约束 |
| Provenance → Authority claim | ❌ No | 来源≠授权 |

**边界：**

```
Decision Layer can READ provenance data.
Decision Layer cannot AUTO-DERIVE authority from provenance data.

Provenance informs. Provenance does not instruct.
```

### 5.5 Provenance and Phase 10 Semantic Memory

Phase 10（Semantic Memory）已经建立了 Memory Provenance 体系。

Phase 13 Provenance 与 Phase 10 的关系：

| | Phase 10 (Semantic Memory) | Phase 13 (Workflow Provenance) |
|---|---|---|
| **Scope** | 知识来源追溯（Pattern→Concept→Principle） | 认知过程追溯（步骤、顺序、上下文） |
| **Granularity** | 知识点级别 | 流程步骤级别 |
| **Storage** | 长期记忆 | 短期/过程记忆（workflow lifetime） |
| **Provenance check** | 记忆链可追溯 | 流程决策路径可追溯 |
| **Authority risk** | 知识可信度→权威 | 流程历史→权威 |

**交叉规则：**

```
Phase 13 Workflow Provenance:
  - May reference Phase 10 Memory (as context)
  - Must NOT override Phase 10 provenance checks
  - Must NOT create parallel memory authority

Phase 10 Semantic Memory:
  - May consume Workflow provenance as evidence
  - Must NOT derive knowledge authority from Workflow history
```

### 5.6 Provenance Auditing

Provenance 自身需要可审计——"谁记录了来源"本身需要可查。

#### Auditability Requirements

| Requirement | Purpose |
|-------------|---------|
| Provenance of provenance | 每条 provenance 记录需要标明记录者和记录时间 |
| Immutable log | Workflow Engine 不能修改已完成的 provenance 记录 |
| User read access | 用户可查看完整 provenance 链 |
| No hidden provenance | Workflow Engine 不能有不可见的内部记录 |

**冻结：**

```
Provenance records are:
  - Append-only (no modification of past records)
  - User-readable (no hidden logs)
  - Self-traceable (each record has its own source)

Provenance records are NOT:
  - Editable by Workflow Engine
  - Usable as authority source
  - Weighted for decision influence
```

### 5.7 Provenance to Influence Chain — The Complete Picture

§5 完成后，Phase 13 ABI 形成一条完整的安全链：

```
§1: Workflow Artifact ≠ Decision Artifact
    ↓ (what can be carried)
§2: Workflow ≤ Constitution
    ↓ (what rules apply)
§3: Influence ≠ Ownership
    ↓ (single decision power)
§4: Persistence ≠ Authority
    ↓ (accumulated power)
§5: Provenance ≠ Authority
    ↓ (historical power)
```

每条不变量防止 Workflow Engine 在不同维度上漂移。

### 5.8 Verdict

```
Phase 13 §5 — Provenance

✅ PASS.

Workflow Engine can record and trace cognitive processes
without granting authority through provenance.

Key boundaries frozen:
  1. Provenance ≠ Authority
  2. History ≠ Ownership
  3. Traceability ≠ Control
  4. Evidence ≠ Decision
  5. Record ≠ Rule
  6. Know Why ≠ Have Right to Decide

Frozen at: 2026-07-22 ❄️
```

---

## Phase Map (in Phase 13 ABI)

```
Phase 0–12 ✅ ALL FROZEN
Phase 13 Cognitive Workflow Engine 🚧
  ├── Entry Review        ✅ FROZEN ❄️
  ├── ABI §1              ✅ FROZEN ❄️
  ├── ABI §2              ✅ FROZEN ❄️
  ├── ABI §3              ✅ FROZEN ❄️
  ├── ABI §4              ✅ FROZEN ❄️
  ├── ABI §5              ✅ FROZEN ❄️
  └── Data Contract       ✅ FROZEN ❄️
  └── Interaction Contract ✅ FROZEN ❄️
  └── Validation Tests    ✅ FROZEN ❄️
  └── Integration Gate    ✅ FROZEN ❄️
  └── Phase 13 COMPLETE   ✅ FROZEN ❄️

---

## Phase 14 — Evolutionary Knowledge Loop ⏳

> Next: Phase 14 Entry Review — core question:
>
> **"如何让系统变得更懂创作，但不让系统决定什么才是创作"**
>
> Path: Entry Review → Ownership/Boundary Review → Meta-Principle Contract
>       → Evidence Graph → Evolution Contract → Validation → Integration Gate


---

## Reference Documents

- `docs/OCOS_NORTH_STAR.md` — System identity and core loop
- `docs/ARCHITECTURE_CONSTITUTION.md` — Five highest rules
- `docs/PHASE13_ENTRY_REVIEW.md` — Entry Review with Workflow Authority Classification
- `docs/abi/OCOS-AgentOrchestration-ABI-1.0.md` — Phase 12 ABI (predecessor, frozen)
- `docs/contracts/AGENT_ORCHESTRATION_DATA_CONTRACT.md` — Phase 12 Data Contract
- `docs/contracts/AGENT_ORCHESTRATION_INTERACTION_CONTRACT.md` — Phase 12 Interaction Contract
