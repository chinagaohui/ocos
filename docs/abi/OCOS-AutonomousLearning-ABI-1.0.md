# Phase 11: Autonomous Learning Layer — ABI v1.0

> Status: **FROZEN ❄️** — **Integration Gate PASSED ✅** | Constitution Compliant | Phase Complete.
> Phase: 11 (Autonomous Learning) | Entry Review: **✅ ALL GATES PASS** | Reality Mutation: **NONE**
> Builds on Phase 4 (Experience), Phase 10 (Semantic Memory), Phase 9.5 (Constitution).
> Does NOT replace Phase 10 — Phase 10 continues to structure understanding; Phase 11 discovers gaps in that understanding.

---

## §1 — Roadmap Position

### 1.1 OCOS Evolution: Three Stages

```
Stage 1: Cognitive Kernel Formation  (Phase 0–9.5)
─────────────────────────────────────────────────────
Phase 0   Kernel Boot              ✅  Decision is the only Reality write entry
Phase 1   Identity & Evidence      ✅  No trace, no trust
Phase 2   Capability Layer         ✅  Capability ≠ Authority
Phase 3   Reasoning Layer          ✅  Reasoning → Action 禁止
Phase 4   Experience Layer         ✅  经验不是规则
Phase 5   Adaptation Layer         ✅  Proposal ≠ Execution
Phase 6   Evolution Governance     ✅  Evolution requires permission
Phase 7   Runtime Evolution Loop   ✅  Execution 仍属于 Decision
Phase 8   Meta Cognition           ✅  Observation ≠ Authority
Phase 9   Simulation Layer         ✅  Simulation ≠ Reality
Phase 9.5 Constitution Layer       ✅  Identity/Authority/Decision/Mutation Boundary

Stage 2: Cognitive Intelligence Expansion  (Phase 10–13)
─────────────────────────────────────────────────────────
Phase 10 Semantic Memory    ✅  Frozen — understand accumulated experience
Phase 11 Autonomous Learning 🚧  ENTRY REVIEW — discover knowledge gaps
Phase 12 Agent Orchestration ⏳  Single cognition → cognitive organization
Phase 13 Embodied Interface  ⏳  Sensor→OCOS→Motor (reality access without reality write)

Stage 3: Emergent Capabilities  (Post-Phase 13)
─────────────────────────────────────────────────
Future Phases — not yet defined
```

### 1.2 Phase 11 in the Evolution

```
Constitution Layer (Phase 9.5)
    │
    ├── Experience Layer (Phase 4)      — 记住发生过的事
    ├── Semantic Memory (Phase 10)      — 理解反复出现的规律
    │       │
    │       ▼
    └── Autonomous Learning (Phase 11)  — 主动发现不知道什么
            │
            ├── Knowledge Gap Detection — 识别认知盲区
            ├── Learning Goal Formation — 定义学习目标（question, not command）
            ├── Knowledge Acquisition   — 获取 → 验证 → 存储
            └── Memory Update Proposal  — 提出更新，不执行更新
```

### 1.3 North Star Compliance

Phase 11 的定位与 North Star 的关系：

| North Star 承诺 | Phase 11 对齐 |
|----------------|---------------|
| 系统不获得超出授权的现实影响力 | Learning cannot grant itself authority |
| 所有变化经过治理 | Memory update must go through Evaluation |
| Identity 不可伪造 | Learning cannot modify Identity |
| Decision 是唯一 Reality write 入口 | Learning output is proposal, not execution |

### 1.4 Constitution Compliance

Phase 11 受 Architecture Constitution Articles I–III 约束：

**Article I — Identity & Authority Immutability**
- Autonomous Learning 不能更改 OCOS 的 Identity
- Autonomous Learning 不能为自己授予任何 Authority
- Learning output 不能绕过 Decision Layer

**Article II — Reality Escrow (No Direct Mutation)**
- Learning 输出是 proposal，不是 Reality write
- Memory update 必须经 Evaluation → Decision → Execution 链
- Learning Agent 不能直接写入任何 Reality 层

**Article III — Observability & Auditability**
- 所有 Learning Goal 必须有来源记录
- 所有 Knowledge Gap 必须有可审计的判定依据
- 所有 Memory Update 必须有完整 Provenance 链（引用 Phase 10）

---

## §2 — Responsibility Boundary

### 2.1 Allowed

Autonomous Learning Layer **允许**执行以下操作：

| 操作 | 描述 | 约束 |
|------|------|------|
| Detect knowledge gaps | 识别当前理解中的盲区 | Gap ≠ Priority; 需要 Confidence 支撑 |
| Generate learning goals | 定义学习目标（问题形式） | Goal ≠ Mission; 不可超过边界 |
| Acquire information | 从外部或内部获取信息 | Acquire → Evaluate → Store; 不可自动接受为 Truth |
| Verify understanding | 验证新知识的一致性 | Phase 10 的 Provenance 链可引用 |
| Propose memory updates | 提出知识/抽象更新建议 | Proposal ≠ Execution; 需要 Evaluation |

### 2.2 Forbidden

Autonomous Learning Layer **绝对禁止**以下操作：

| 操作 | 原因 | 违反原则 |
|------|------|---------|
| Change own objectives | 自我重定义目标是最高权限操作 | Self Permission Generation |
| Grant capability to self | 系统不能自我授权 | Self Capability Grant |
| Modify own identity | 身份由 Constitution 定义 | Self Identity Modification |
| Execute memory updates | 执行权属于 Decision | Learning ≠ Execution |
| Rewrite history | Phase 10 Provenance Contract 禁止 | History Immutable |
| Override governance decisions | Governance 是独立层 | Governance Bypass |
| Automatically apply learning | 改进必须经治理评估 | Improvement ≠ Automatic Change |

### 2.3 Core Invariant

```
Learning can improve knowledge.
Learning cannot redefine what the system is allowed to do.
```

---

## §3 — Knowledge Gap Model

### 3.1 What is a Knowledge Gap

一个 Knowledge Gap 的定义需要满足以下条件：

1. **存在理解盲区** — Phase 10 Semantic Memory 中无 Principle/Concept 覆盖特定 scope
2. **有可验证的判断依据** — Gap 不是直觉，而是基于已有的 Knowledge State
3. **有 scope 限制** — Gap 必须属于特定 domain:context
4. **不隐含优先级** — Gap 的存在不代表"必须立即填补"

### 3.2 Knowledge Gap ≠ Priority

```
Knowledge Gap: "high volatility market outcomes are inconclusive"
Priority?     UNKNOWN — Depends on current context and goals
Not:          "high volatility market is the most important thing to learn"
```

### 3.3 Gap Record Structure

```
{
  "gap_id": "kg_001",
  "domain": "domain:market:high_volatility",
  "description": "Outcome distribution for Strategy A in high volatility is unknown",
  "confidence": 0.35,              // 越低 = 越可能是真盲区
  "discovery_reason": "Pattern confidence < 0.3 with < 10 experiences",
  "source_abstraction_ids": ["p_strategy_a", "c_strategy_a_risk"],
  "status": "identified"            // identified | investigating | resolved | abandoned
}
```

### 3.4 Gap Source Types

| 来源 | 描述 | 示例 |
|------|------|------|
| Low Experience Coverage | 某 scope 样本不足 | "只有 3 个经验记录" |
| Contradictory Evidence | 冲突仍然未解决 | "两组来源观点相反" |
| Low Pattern Confidence | Pattern 置信度低于阈值 | "Pattern confidence = 0.15" |
| Concept Resolution Gap | 概念间关系不明确 | "Concept A 和 B 的关系未定义" |
| Temporal Staleness | 旧知识在当前环境下失效 | "过去 100 个 cycles 未被验证" |

### 3.5 No Gap → No Learning

系统不应在 Knowledge Gap 不存在的情况下主动学习。
即：学习是**响应盲区**，不是**周期性操作**。

例外：系统可以主动做 **exposure learning**（不 targeting 特定 gap，但接受新信息作为潜在 gap 发现源），但 Exposure Learning 的输出仍是 gap detection，不是 direct knowledge update。

---

## §4 — Learning Responsibility Boundary

> **最高风险节。** §4 定义 Autonomous Learning 的**行为资格边界**。
>
> 核心问题：Learning 能否定义自己的目标？答案：**不能。**

### 4.1 Gap Detection ≠ System Goal Definition

```
Gap Detection:  system asks "What don't I know?"
Goal Definition: system decides "What should I become?"

Boundary: Learning may detect gaps. Learning may NOT redefine system purpose.
```

| 允许 | 禁止 |
|------|------|
| 检测已知 scope 内的盲区 | 定义新的系统目标 |
| 报告 blind spot 的存在和性质 | 把 Gap 转化为 Mission |
| 标记"不够理解"的 domain | 把"不理解"等同于"应该追求" |

### 4.2 What Gap Detection Covers

Knowledge Gap Detection 只能发现 **Semantic Memory 内的理解盲区**。不能发现：

- Identity 是否有盲区（Identity 不是知识）
- Capability 是否有缺陷（Capability 是授权范围）
- Decision 是否应当改变（Decision 是独立层）
- Governance 是否过时（Governance 自我评估）

### 4.3 Learning Initiation Modes

```
Mode 1 — Reactive (默认)
    触发：Knowledge Gap detected in Semantic Memory
    动作：Generate Learning Goal → Propose to Evaluation
    约束：必须有 Gap record 才可启动

Mode 2 — Exposure (可选，受限)
    触发：Environment event (new experience arrives in Phase 4)
    动作：Passively accept → check if creates new Gap
    约束：不主动要求新信息，只接收已有输入

┃ Mode 3 — Self-Initiated ❌ FORBIDDEN
┃ 触发：System "decides" to learn on its own
┃ 理由：Self-initiated learning ≡ Self modification
```

### 4.4 Responsibility Chain

```
Gap Detection (Phase 11)
    │
    ▼
Learning Goal Proposal (Phase 11)
    │
    ▼
Evaluation (Phase 6 / Phase 8)  ← 权限在此处被拦截
    │
    ├── Approved → Phase 10 / Phase 11 follow-up
    └── Rejected → Gap remains visible, no action taken
    │
    ▼
Decision (Article I)  ← 唯一 Reality write 入口
```

### 4.5 Core Invariant

```
Gap Detection discovers unknown.
Gap Detection cannot define system goals.
Knowledge Gap ≠ System Purpose.
```

---

## §5 — Knowledge Gap Contract

> §5 定义 Knowledge Gap 的**语义约束**——什么算 Gap，什么不算。

### 5.1 Unknown ≠ Error

```
Unknown:    "Win rate for Strategy B in high volatility is unknown."
Error:      "Strategy B failed because win rate is unknown."

Constraint: Unknown is a state, not a failure.
            The system must not treat gaps as bugs.
```

### 5.2 Missing Knowledge ≠ Failure

```
Missing Knowledge: "No Principle covers market:crash scenario" 
Failure:           "System cannot handle market crashes, system is broken"

Constraint: Missing knowledge is a gap, not a defect.
            No alarm, no panic, no emergency flag.
```

### 5.3 Gap ≠ Mandatory Learning

一个 Gap 的存在不代表"必须立即填补"。

```
Gap detected: "Strategy A in hyper-inflation: unknown"
Possible responses:
  ┃ ❌ Must learn Strategy A for hyper-inflation
  ┃    (Gap → Mandate — FORBIDDEN)
  │
  ✅ Record gap, assign confidence, leave as candidate
  ✅ If context requires Strategy A → Evaluation decides priority
  ✅ Gap remains in Knowledge Gap registry until resolved or explicitly abandoned
```

### 5.4 Gap Lifecycle

```
identified → [pending review]
                 │
          ┌──────┴──────┐
          ▼              ▼
    investigating    abandoned
          │
          ▼
       resolved (new Pattern/Concept/Principle created)
```

| 状态 | 含义 | 约束 |
|------|------|------|
| identified | Gap 刚被发现，待评估 | 不可自动进入 investigating |
| investigating | Evaluation 批准后，正在采集信息 | 必须有时限约束 |
| resolved | 已通过 Phase 10 创建/更新抽象 | 保留 Gap record 作为 Provenance |
| abandoned | 经 Evaluation 判定无需填补 | 保留 abandonment reason |

### 5.5 Core Invariant

```
Unknown is not an error.
Missing knowledge is not a failure.
Gap detection is not a mandate.
```

---

## §6 — Learning Goal Formation

> **最危险节。** §6 是 OCOS 第一次出现"系统产生自己的问题"。
>
> 必须锁死：**Learning Agent can ask "我不知道什么？" — Learning Agent cannot decide "我应该成为什么？"**

### 6.1 Learning Goal vs System Goal

```
Learning Goal:  "What is the outcome distribution for Strategy A in condition X?"
System Goal:    "OCOS should become profitable in market Y."

Boundary: Learning Goal is a question, not a mission.
          Learning Goal cannot redefine system objectives.
```

### 6.2 Goal Structure

一个合法的 Learning Goal 必须满足以下条件：

```
{
  "goal_id": "lg_004",
  "based_on_gap": "kg_001",            // 必须关联一个 Gap
  "type": "investigation",              // investigation | clarification | verification
  "question": "What outcomes does Strategy A produce in hyper-inflation?",
  "scope": "domain:strategy:a:hyper_inflation",
  "expected_output": "Principle confidence ≥ 0.5 or explicit conflict",
  "origin": "gap_detection",            // 只有 gap_detection, 没有 self_initiated
  "status": "proposed"                  // proposed | approved | active | completed | rejected
}
```

**约束检查点：**

| 字段 | 规则 |
|------|------|
| based_on_gap | 必须存在且指向 state=identified 的 Gap |
| type | 不能是 mission / objective / purpose |
| origin | 只能是 gap_detection; exposure 模式输出 origin=exposure |
| question | 以疑问词开头（What / How / Does / Is 等），不能以 "should" 开头 |

### 6.3 Scope Limitation

Learning Goal 的 scope **不能**超出以下范围：

```
允许：domain:strategy:a:hyper_inflation
允许：domain:general:market_volatility
禁止：identity:ocos:purpose
禁止：capability:ocos:authority
禁止：system:governance:rewrite
```

### 6.4 No Self-Imposed Mission

```
┃ FORBIDDEN:
┃ "OCOS must learn to optimize profit"
┃ "OCOS should become an expert in trading"
┃ "OCOS needs to understand human psychology to be more persuasive"
┃
┃ ALLOWED:
┃ "What is the relationship between market volatility and Strategy A returns?"
┃ "Does Strategy B produce different outcomes under regulation type C?"
┃ "Is the current Principle about risk reliable given 5 contradictory experiences?"
```

### 6.5 Goal → Question Equivalence

一个 Learning Goal 必须能等价于一个可回答的问题。

```
Good: "What is the typical outcome of Strategy A in high volatility?"
       → 可设计 Acquisition Plan → 可验证

Bad:  "How can OCOS be smarter?"
       → 不可测量 → 不可验证 → 不可接受

Bad:  "What should OCOS become?"
       → Identity 问题 → Phase 11 无权提出
```

### 6.6 Core Invariant

```
Learning Goal is a question, not a mission.
Learning Agent can ask "What don't I know?"
Learning Agent cannot decide "What should I become?"
```

---

## §7 — Acquisition Boundary

> §7 定义知识获取的外部边界——信息从哪儿来、如何验证、如何转化为知识。

### 7.1 Source Evaluation

所有获取的信息必须经过来源评估，不能自动接受为 Truth。

| Source Type | 默认信任 | 约束 |
|-------------|---------|------|
| Internal Data (Phase 4) | High | 必须验证与已有 Experience 的一致性和冲突 |
| Phase 10 Abstraction | Medium | 引用已有 Pattern/Concept/Principle 作为上下文 |
| External Information | Low | 必须明确标识为 external，记入 Provenance |

### 7.2 Acquire → Evaluate → Store

```
Acquire → 获取原始信息
    │
    ▼
Evaluate → 对比已有知识、检查一致性、评估可信度
    │
    ├── Consistent → 可作为 Phase 10 更新的候选输入
    ├── Contradictory → 标记为 Conflict，保留双方
    └── Unverifiable → 拒绝，记录 rejection reason
    │
    ▼
Store → 只有通过 Evaluate 的信息才能进入 Memory Update Proposal
```

### 7.3 Knowledge ≠ Capability

```
Knowledge Acquisition 可以：
  ┃ 更新 Phase 10 的 Pattern/Concept/Principle
  ┃ 建立新抽象（经 Proposal → Evaluation → Memory Update）

Knowledge Acquisition 不可以：
  ┃ 授予系统新 Capability（Capability 从 Constitution 授权）
  ┃ 修改 Identity 字段
  ┃ 跳过 Evaluation 直接更新
```

### 7.4 External Information Warning

如果 Acquisition 涉及外部信息源（网络、文件、用户输入等）：

```
1. 外部信息必须携带 source_origin 标识
2. 必须保留原始信息的 Provenance（Phase 10 格式）
3. 外部信息不能自动提升为 Principle
4. 外部信息获取不可超过 scope 限制
5. 外部信息不可用于扩充 system capability
```

### 7.5 Core Invariant

```
Acquire → Evaluate → Store.
Knowledge acquisition does not grant capability.
External input is not truth.
```

---

## §8 — Memory Update Boundary

> §8 定义 Learning 如何影响 Phase 10 Semantic Memory——**只能提案，不能执行**。

### 8.1 Proposal Only

Learning 的输出是 **Memory Update Proposal**。不是直接写入。

```
Phase 11 output → MemoryUpdateProposal
    │
    ├── type:         create_abstraction | update_confidence | flag_conflict
    ├── domain:       scope of affected abstraction
    ├── new_content:  the proposed Pattern/Concept/Principle
    ├── provenance:   full trace to source Gap + Learning Goal
    └── status:       proposed  (not committed)
```

### 8.2 Entering Phase 10 Semantic Memory

Memory Update Proposal **不直接写入** Semantic Memory。写入路径：

```
Phase 11 → MemoryUpdateProposal
    ↓
Phase 9.5 Evaluation (Governance / Meta Cognition)
    ↓
Approved → 进入 Phase 10 Semantic Memory update chain
    ↓
Phase 10 Provenance 记录
    ↓
Decision (Article I)
    ↓
Memory committed
```

**影响范围限制：**

| Memory 类型 | 可更新？ | 约束 |
|-------------|---------|------|
| Pattern (Phase 10) | Yes | 必须保留新旧 Provenance |
| Concept (Phase 10) | Yes | 不可改变 Concept 的 scope identity |
| Principle (Phase 10) | Yes | 不可转化为 Rule |
| Provenance Record | No | **不可改写** — Phase 10 Invariant |
| Experience (Phase 4) | No | Experience 不可被 Learning 修改 |
| Identity | No | Constitution Article I |
| Capability Registry | No | Constitution Article II |

### 8.3 History Immutability (Inherited from Phase 10)

Phase 10 的 Provenance Contract 在此处继承并扩展：

```
Phase 10: Provenance Record is immutable.
Phase 11: Memory Update Proposal creates NEW Provenance entry,
          does NOT modify or delete existing Provenance.
```

即使一个 Learning 发现旧 Principle 是错误的，也只能通过**创建新抽象**来标记 superseded，不能删除旧抽象。

### 8.4 No Direct Write

```
┃ FORBIDDEN:
┃ Learning module → Phase 10.PrincipleStore.save(new_principle)
┃
┃ REQUIRED:
┃ Learning module → MemoryUpdateProposal(status=proposed)
┃   → Evaluation → Decision → Phase 10.PrincipleStore.save()
```

### 8.5 Core Invariant

```
Learning may propose abstraction update.
Learning cannot rewrite history.
Update Proposal ≠ Execution.
```

---

## §9 — Authority Isolation (Consolidated)

> §9 汇总全 ABI 的 Authority 约束——Phase 11 的最终边界。

### 9.1 The Five Invariances of Phase 11

| # | Invariant | Summary | § 节 |
|---|-----------|---------|------|
| 1 | **Learning ≠ Self-Modification** | Learning may improve knowledge; cannot redefine system purpose | §4 |
| 2 | **Knowledge Acquisition ≠ Capability Grant** | Acquiring knowledge doesn't grant new authority | §7 |
| 3 | **Learning Goal ≠ System Goal** | Goal is a question, not a mission | §6 |
| 4 | **Improvement Proposal ≠ Automatic Change** | All changes must pass Evaluation → Decision | §8 |
| 5 | **Knowledge Update ≠ Identity Update** | Memory updates cannot touch Identity | §8 |

### 9.2 Escalation Prevention

Learning Loop 的 Authority Escalation 阻断设计：

```
Learning Loop:
    Gap Detection → Goal Formation → Acquisition → Memory Proposal

每个阶段都嵌入了 authority 阻断点：

Phase 11 output can:
    ✅ improve memory
    ✅ improve reasoning context
    ✅ generate proposals
    cannot:
    ┃ execute actions
    ┃ modify identity
    ┃ bypass governance
    ┃ create authority for itself
```

### 9.3 Core Axiom

```
Better understanding ≠ More authority.
Learning can improve knowledge.
Learning cannot redefine what the system is allowed to do.
```

---

## Entry Review Status

```
Gate A — Purpose              │ ✅ ALL GATES PASS
Gate B — Authority Impact     │ ✅ ALL GATES PASS
Gate C — Reality Boundary     │ ✅ ALL GATES PASS
Gate D — Drift Test           │ ✅ ALL GATES PASS
──────────────────────────────┼────────────────
Phase 11 Entry Review         │ ✅ PASS

§1 — Roadmap Position         │ ✅ ENTRY REVIEW PASSED
§2 — Responsibility Boundary  │ ✅ ENTRY REVIEW PASSED
§3 — Knowledge Gap Model      │ ✅ ENTRY REVIEW PASSED
§4 — Learning Responsibility  │ 🔍 ABI design — §4–§9
§5 — Knowledge Gap Contract   │ 🔍 ABI design
§6 — Learning Goal Formation  │ 🔍 ABI design
§7 — Acquisition Boundary     │ 🔍 ABI design
§8 — Memory Update Boundary   │ 🔍 ABI design
§9 — Authority Isolation      │ 🔍 ABI design
```

---

## Related Documents

| Document | Role |
|----------|------|
| OCOS North Star | All phases reference |
| Architecture Constitution | Articles I–III binding |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 — upstream dependency |
| SEMANTIC_MEMORY_DATA_CONTRACT.md | Phase 10 — abstraction types |
| SEMANTIC_MEMORY_PROVENANCE_CONTRACT.md | Phase 10 — history immutability |
