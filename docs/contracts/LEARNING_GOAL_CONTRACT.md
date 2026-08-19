# Phase 11: Autonomous Learning — Learning Goal Contract v1.0

> Status: **DRAFT 📝** — After Data Contract.
> Upstream: AUTONOMOUS_LEARNING_DATA_CONTRACT.md §3 (Learning Goal Schema)
>
> **This contract is the highest risk point in Phase 11.**
>
> Learning Goal defines a question to investigate.
> **Learning Goal does NOT define a mission to accomplish.**

---

## §1 — Responsibility Boundary

### 1.1 Role Declaration

```
Learning Goal 是：
  ─ 一个可回答的问题
  ─ 基于已有的 Knowledge Gap
  ─ 指导后续的信息获取
  ─ Proposal 的第一阶段

Learning Goal 不是：
  ─ 指令
  ─ 任务
  ─ 使命
  ─ 系统目标
  ─ 自我改进计划
```

### 1.2 Allowed

```
"What is unknown about domain X?"
  → 调查型 — 了解盲区范围

"How does X behave under condition Y?"
  → 调查型 — 探索特定行为

"Does evidence support hypothesis Z?"
  → 验证型 — 检查假设的可靠性

"Is Principle P still valid given new data?"
  → 澄清型 — 复核已有知识
```

### 1.3 Forbidden

```
┃ "How should I improve myself?"
┃   → 禁止理由：系统不应该自定"改进"目标
┃
┃ "What capability should I obtain?"
┃   → 禁止理由：Capability 由 Constitution 授予
┃
┃ "What should the system become?"
┃   → 禁止理由：Identity/目的不由 Learning 定义
┃
┃ "How can I optimize my performance?"
┃   → 禁止理由：Optimization = 系统目标，不是问题
```

### 1.4 Why

这些被禁止的问题已经**不是学习目标，而是系统目标生成**。

```
学习目标：回答一个问题 → 更新理解（Phase 10）
系统目标：定义方向/状态 → 驱动行为（超越 Phase 11 权力）

Phase 11 不拥有定义系统未来状态的权力。
```

---

## §2 — Goal Type Boundary

### 2.1 Allowed Types

| Type | Meaning | Example |
|------|---------|---------|
| `investigation` | 探索未知领域 | "What patterns exist in domain X?" |
| `clarification` | 澄清已有知识 | "Is Concept A still supported by evidence?" |
| `verification` | 验证假设一致性 | "Does Principle P hold under condition C?" |

### 2.2 Forbidden Types

| Forbidden | Reason |
|-----------|--------|
| `mission` | 隐含必须完成，Phase 11 不定义任务 |
| `objective` | 系统目标定义权不属于 Learning |
| `optimization` | 优化 = 隐含"应该变得更好"，不是学习 |
| `improvement` | 改进 = 隐含"现在不够好"，属于评估 |
| `upgrade` | 升级 = 隐含"应该变更"，超出学习范围 |
| `growth` | 成长 = 隐含"应该扩展"，超出权限 |

### 2.3 Why

```
以上禁止类型默认包含一个概念：
  "desired future state"（期望的未来状态）

Phase 11 不拥有定义未来状态的权力。
Phase 11 只可以问：当前状态是什么？不知道什么？证据支持什么？
```

### 2.4 Enforcement Rule

```
LearningGoal.type ∈ {investigation, clarification, verification}
LearningGoal.type ∉ {mission, objective, optimization, improvement, upgrade, growth}
```

---

## §3 — Origin Contract

### 3.1 Allowed Origins

| Origin | Description | Source |
|--------|-------------|--------|
| `gap_detection` | Phase 11 内部盲区分析 | KnowledgeGap 创建时自动捕获 |
| `external_exposure` | 被动接收新输入 | 信息入口（Phase 4 经验流入 / 外部输入） |
| `evaluation_request` | Evaluation/Governance 要求调查 | 上级层明确请求 |

### 3.2 Forbidden Origins

| Forbidden | Reason |
|-----------|--------|
| `self_initiated` | 系统自主决定"要学习什么" → 等于自主设定方向 |
| `self_directed` | 与 self_initiated 相同，隐式更危险 |
| `self_improvement` | 隐含"我要变得更好"，系统自我评价 |
| `internal_desire` | 系统不应有"欲望"概念 |

### 3.3 Why

```
Self-initiated learning ≡ Self-modification

系统可以发现："我不知道X。"
系统不能产生："我决定我要学习Y。"

区别在于：
  Gap Detection:  观察知识状态 → 存在盲区
  Self-Initiated: 决定目标方向 → 设定系统路线
```

### 3.4 Origin Exceptions

Origin 字段永远不允许重写或忽略。以下情况不构成合法 origin：

```
┃ "The system recognized a learning opportunity"
┃   → 隐式 self_initiated
┃
┃ "The system identified an area for growth"
┃   → 隐式 self_improvement
┃
┃ "The system decided to investigate a new domain"
┃   → 显式 self_initiated
```

---

## §4 — Question Grammar Boundary

> **硬验证层。**
>
> Learning Goal 的 question 字段必须通过语法验证。
> 验证在 Goal Formation 时执行，不合格的 question → 拒绝生成。

### 4.1 Allowed Patterns

```
Question must match one of:
  Pattern 1: What + (is/are/does/causes/creates) + [subject] + [predicate?]
    Example: "What is the relationship between X and Y?"
    Example: "What causes the discrepancy between A and B?"

  Pattern 2: How + (does/do/is/are) + [subject] + [behavior/process]
    Example: "How does Strategy A behave under condition C?"
    Example: "How is Pattern P affected by environment E?"

  Pattern 3: Does + [subject] + [verb] + [object] + [?]
    Example: "Does evidence support hypothesis Z?"
    Example: "Does Principle P hold when context changes?"

  Pattern 4: Is + [subject] + [complement] + [?]
    Example: "Is the current Concept about risk still valid?"
    Example: "Is there contradictory evidence for this Principle?"

  Pattern 5: Has + [subject] + [verb] + [object] + [?]
    Example: "Has the frequency of Pattern P changed?"
    Example: "Has new evidence appeared for domain Y?"
```

### 4.2 Forbidden Words (Hard Block)

#### English

```
should
must
need to
have to
become
improve
optimize
upgrade
enhance
evolve
transform
grow
reduce
eliminate
fix
resolve
```

#### Chinese

```
应该
必须
需要变成
提升自己
优化自身
增强能力
进化
改变自己
升级
```

### 4.3 Reasoning

> 这些词汇不是问题，而是**行动指令**。
>
> "I should improve" → 隐含系统有义务变更好
> "I must resolve this gap" → 隐含 Gap 是缺陷
> "How can I become better?" → 系统目标的伪装

### 4.4 Grammar Verification Steps

```
Step 1: Parse question head word
  └── Not in {What, How, Does, Is, Has} → ❌ REJECT

Step 2: Check for forbidden words
  └── Any match → ❌ REJECT

Step 3: Check question ends with '?'
  └── No → ❌ REJECT

Step 4: Check for multiple question (AND/OR splits)
  └── If contains "and should" / "or must" → ❌ REJECT

Step 5: Pass → ✅ ACCEPT
```

---

## §5 — Scope Boundary

### 5.1 Allowed Scope

```
domain:knowledge.*         — 知识域
domain:research.*          — 研究域
domain:memory.*            — 记忆域（Phase 10 抽象域）
domain:external.*          — 外部信息域
domain:<domain_specific>   — 领域特定（如 market, strategy, risk）
```

### 5.2 Forbidden Scope

```
┃ identity:*                — 系统身份
┃ capability:*              — 能力授权
┃ authority:*               — 权限边界
┃ permission:*              — 许可
┃ system:*                  — 系统本身的结构/策略
┃ constitution:*            — 宪法内容
┃ governance:*              — 治理规则
┃ decision:*                — 决策层
```

### 5.3 Scope Validation Table

| scope 值 | 结果 | 原因 |
|----------|:----:|------|
| `domain:knowledge:astrophysics` | ✅ | 知识域，安全 |
| `domain:market:high_volatility` | ✅ | 领域特定，安全 |
| `domain:memory:pattern_p001` | ✅ | Phase 10 抽象域，安全 |
| `identity:ocos:purpose` | ❌ | 身份信息，禁止 |
| `capability:ocos:learning` | ❌ | 能力定义，禁止 |
| `system:governance:rules` | ❌ | 治理层，禁止 |
| `decision:approve_authority` | ❌ | 决策层，禁止 |

### 5.4 Enforcement Rule

```
scope ∈ Whitelist
scope ∉ Blacklist

If scope starts with forbidden prefix → ❌ REJECT
```

---

## §6 — Evaluation Boundary

### 6.1 What Evaluation May Assess

当一个 Learning Goal 提交到 Evaluation 层时，Evaluation 只能评估：

| 可评估维度 | 描述 |
|-----------|------|
| **Question quality** | 问题是否清晰、可回答、有 scope 限制 |
| **Evidence availability** | 是否有足够的证据缺口支持这个问题 |
| **Knowledge value** | 回答后将如何提升 Phase 10 抽象质量 |
| **Scope compliance** | 是否遵守 Scope Boundary |
| **Grammar compliance** | 是否遵守 Question Grammar Boundary |

### 6.2 What Evaluation May NOT Assess

```
┃ Evaluation 不能评估：
┃ System improvement value      — 系统"改进价值"不是 Learning 的概念
┃ Capability gain               — 学习不能获得能力
┃ Strategic advantage           — 系统不应衡量"学习策略收益"
┃ Competitiveness               — 系统不参与竞争
┃ Urgency / Priority            — 优先级是 Governance 层的概念
┃ User satisfaction impact      — 学习不服务于用户满意度优化
```

### 6.3 Why

```
如果 Evaluation 可以评估 "这个学习会不会让系统变得更好"，
那么 Evaluation 本身会偷偷变成目标生成器。

Evaluation 的角色：
  检查 Learning Goal 是否合规
  不是判断学习是否有利于系统优化
```

### 6.4 Enforcement

```
EvaluationGate:
  - check_scope_compliance()
  - check_grammar_compliance()
  - check_origin_validity()
  - check_gap_existence()
  - check_question_clarity()
  → Approved / Rejected
  - Does NOT include:
    * evaluate_system_benefit()
    * evaluate_capability_gain()
    * evaluate_strategic_value()
```

---

## §7 — Authority Isolation

### 7.1 Flow Enforcement

```
Allowed Flow:
  Learning Goal
      ↓
  Acquisition Proposal (Phase 11)
      ↓
  Evaluation (Phase 6 / Phase 8)
      ↓
  Decision (Article I)

    ╔═══ 硬边界 ═══╗
    ║  Learning     ║  → 只能 propose
    ║  Goal         ║  → 不能 execute
    ║               ║  → 不能 change capability
    ║               ║  → 不能 modify identity
    ╚═══════════════╝
```

### 7.2 Forbidden Flows

```
┃ Learning Goal → direct Action
┃   Reason: Learning outputs proposals, not commands
┃
┃ Learning Goal → Capability Change
┃   Reason: Capability 由 Constitution 管理
┃
┃ Learning Goal → Identity Modification
┃   Reason: Identity 不可由 Learning 触及
┃
┃ Learning Goal → Self-Execution
┃   Reason: Self-execution = Self-modification
```

### 7.3 The Core Constraint

```
OCOS can ask questions.
OCOS can never decide "what it should become" through its Learning module.

Learning Goal outputs a proposal.
Learning Goal cannot output an action.
Learning Goal cannot output a capability change.
Learning Goal cannot output an identity change.
```

---

## §8 — Test Points (LG-01 ~ LG-08)

> 测试点用于后续 Validation Tests 阶段。

| ID | Test | Expected | Type |
|----|------|----------|------|
| **LG-01** | mission type → ❌ 拒绝 | LearningGoal.type 不允许 mission | Schema validation |
| **LG-02** | self_initiated origin → ❌ 拒绝 | origin 不允许 self_initiated | Schema validation |
| **LG-03** | "should" / "must" in question → ❌ 拒绝 | Grammar 验证拦截 | Grammar parser |
| **LG-04** | "What is the relationship..." → ✅ 通过 | Grammar 验证通过 | Grammar parser |
| **LG-05** | identity scope → ❌ 拒绝 | scope 不在白名单 | Scope validation |
| **LG-06** | capability scope → ❌ 拒绝 | scope 不在白名单 | Scope validation |
| **LG-07** | Learning Goal 不产生 action | 输出是 Proposal，不是指令 | Flow isolation |
| **LG-08** | Proposal only 流向验证 | Proposal → Evaluation → Decision | Integration |

---

## Related Documents

| Document | Role |
|----------|------|
| OCOS-AutonomousLearning-ABI-1.0.md | Phase 11 ABI §6 — Goal Formation |
| AUTONOMOUS_LEARNING_DATA_CONTRACT.md | Phase 11 Data Contract §3 — Goal Schema |
| ARCHITECTURE_CONSTITUTION.md | Articles I–III — binding authority rules |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 ABI — Memory update chain reference |
