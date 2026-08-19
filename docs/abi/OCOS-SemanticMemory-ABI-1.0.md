# Phase 10: Semantic Memory Layer — ABI v1.0

> Status: **FROZEN ✅** — All gates passed. Semantic Memory has understanding, not power.
> Phase: 10 (Semantic Memory Extension) | Authority Impact: NONE | Reality Mutation: NONE | Governance Impact: NONE
> Builds on Phase 4 (Experience), Phase 9 (Simulation), Phase 9.5 (Constitution).
> Does NOT replace Phase 4 — Phase 4 continues to store raw Event→Experience records.

---

## Section 1 — Calibrated Roadmap Positioning

### 1.1 OCOS Evolution: Two Stages

```
Stage 1: Cognitive Kernel Formation  (Phase 0–9.5)
─────────────────────────────────────────────────────
Phase 0  Kernel Boot              ✅  Decision is the only Reality write entry
Phase 1  Identity & Evidence      ✅  No trace, no trust
Phase 2  Capability Layer         ✅  Capability ≠ Authority
Phase 3  Reasoning Layer          ✅  Reasoning → Action 禁止
Phase 4  Experience Layer         ✅  经验不是规则（event→experience→pattern）
Phase 5  Adaptation Layer         ✅  Proposal ≠ Execution
Phase 6  Evolution Governance     ✅  Evolution requires permission
Phase 7  Runtime Evolution Loop   ✅  Execution 仍属于 Decision
Phase 8  Meta Cognition           ✅  Observation ≠ Authority
Phase 9  Simulation Layer         ✅  Simulation ≠ Reality (1258+ tests)
Phase 9.5 Constitution Layer      ✅  Identity/Authority/Decision/Mutation Boundary

Stage 2: Cognitive Intelligence Expansion  (Phase 10–13)
─────────────────────────────────────────────────────────
Phase 10 Semantic Memory    ✅  Frozen — Pattern→Concept→Principle (22 integration tests passed)
Phase 11 Autonomous Learning ⏳  System discovers own knowledge gaps
Phase 12 Agent Orchestration ⏳  Single cognition → cognitive organization
Phase 13 Embodied Interface  ⏳  Sensor→OCOS→Motor (reality access without reality write)
```

### 1.2 Phase 10 in the Evolution

**Layer in context:**

```
Constitution Layer (Phase 9.5)
    │
    ├── Simulation Layer (Phase 9)         — 想象可能的世界
    ├── Experience Layer (Phase 4)         — 记住发生过的事
    │       │
    │       ▼
    └── Semantic Memory (Phase 10)         — 理解反复出现的规律
            │
            ├── Pattern Extraction         — 相似事件→趋势
            ├── Concept Formation          — 趋势→抽象概念
            └── Principle Derivation       — 概念→可检验原理
```

**Core shift from Phase 4:**

| Phase 4 (Event Experience) | Phase 10 (Semantic Memory) |
|---------------------------|----------------------------|
| 存储单个事件 | 发现跨事件规律 |
| "角色A在资源不足时冲突" | "资源压力增加→信任下降" |
| 按 hypothesis 检索 | 按 pattern/concept 检索 |
| 数据层 | 抽象层 |
| Provenance: source + scope | Provenance: pattern + evidence_count + boundary_conditions |
| 输出: ExperienceRecord | 输出: SemanticAbstraction (pattern→concept→principle) |

### 1.3 What Phase 10 Is NOT

Phase 10 Semantic Memory is NOT:

| 不是 | 说明 |
|------|------|
| Phase 4 的替代 | Phase 4 继续存储原始事件。Semantic Memory 是上层抽象 |
| Rule 生成器 | Pattern/Concept/Principle 永远是参考性的，不是强制性的 |
| 知识图谱 | 不是实体-关系图。是事件规律→概念→原理的抽象链 |
| 决策引擎 | 和 Phase 4 Experience 一样，禁止进入 Decision 路径 |
| 自主学习 | Phase 11 做这个。Phase 10 只建立知识结构，不主动发现知识缺口 |

---

## Section 2 — North Star Compliance

### 2.1 Purpose Alignment

> **North Star Purpose:** 一个属于自己的、本地运行的认知辅助系统，能够理解用户、积累经验、
> 主动学习、分析问题、提出方案，并在严格权限控制下持续进化。

**Phase 10 定位：** Semantic Memory Layer 将 Phase 4 存储的原始 Experience
提升为结构化的知识抽象（Pattern → Concept → Principle），
使 OCOS 能从"记住事件"进化到"理解规律"。

| 已有事实 | Phase 4 已经解决 | Phase 10 将解决 |
|----------|-----------------|-----------------|
| 系统有事件记忆 | 知道某个事件发生了 | 知道为什么类似事件反复出现 |
| 检索到相似经验 | Confidence（历史可靠性） | Abstraction confidence（规律可信度） + boundary conditions（适用边界） |
| 假设受经验影响 | Phase 10 的 Experience Context 提供参考 | 额外提供：pattern signal + concept reference + principle constraint check |
| 经验不能决策 | Experience ≠ Decision | Concept ≠ Rule, Principle ≠ Authority |

证明：
- Phase 0–9.5 完全可独立运行。移除 Phase 10 后各层不受影响（Phase 4 持续独立运行）。
- Phase 10 不引入新的写入口到 Reality。
- Phase 10 不改变 Decision 权限。
- Phase 10 不对 Phase 4 增加新权限（Phase 4 持续以原始形式存储事件）。

### 2.2 Never Become Compliance

| 禁止项 | Phase 10 是否触碰 | 证明 |
|--------|------------------|------|
| Autonomous authority | ❌ | Semantic Abstraction 不能决策、不能 veto、不能生成 Rule |
| Self-directed entity | ❌ | 无目标设置功能；抽象由经验驱动，不是自我驱动 |
| Reality mutation agent | ❌ | 输出终点是 Understand/Evaluate，不是 Commit |
| General AGI experiment | ❌ | Scope 限制在个人认知辅助；SemanticAbstraction 无自主意图字段 |

### 2.3 Core Loop Compliance

```
North Star Core Loop: Observe → Understand → Learn → Recommend → User Decide → Act → Remember
                                                          ↓
Phase 4 fills:                    Event → Experience
                                                          ↓
Phase 10 fills (NEW):             Experience → Pattern → Concept → Principle → Knowledge Structure
```

Phase 10 的 **Learn** 不是自动化决策，而是：

1. **Pattern Extraction** — 从经验中发现跨事件重复模式（不是推导出规则）
2. **Concept Formation** — 将模式抽象为可复用的概念（不是固化为人格标签）
3. **Principle Derivation** — 验证概念形成可检验的高层原理（不是获得权威）

它与 Core Loop 的关系是：

| Loop 阶段 | Phase 10 输入 | Phase 10 输出 |
|-----------|---------------|---------------|
| Observe | —（观察本身不依赖抽象知识） | — |
| **Understand** | Phase 4 Experience + 当前 Context | SemanticContext（Pattern + Concept + Principle） |
| **Learn** | 新验证的概念/原理 | 更新 Abstraction Store |
| Recommend | 经语义增强的 Hypothesis | 更丰富的上下文——但仍是 Hypothesis，不是 Decision |
| User Decide | —（不变） | — |
| Act | —（不变） | — |
| Remember | 执行结果 | 新 Experience（Phase 4）+ 可选的概念确认/挑战（Phase 10） |

证明：Phase 10 不改变 Observe 的独立性，不改变 User Decide 的独占性。

### 2.4 Immutable Rules Compliance

| North Star Rule | 是否被 Phase 10 改变 | 证据 |
|----------------|---------------------|------|
| User owns goals | ❌ | Semantic Memory 不能设置目标 |
| Decision requires authorization | ❌ | Semantic Memory 不能产生 Decision |
| Reality mutation requires explicit commit | ❌ | Semantic Memory 不接触 Reality |
| Capability growth never grants authority | ❌ | Semantic Influence Contract 显式禁止 |
| Simulation never becomes Reality | ❌ | Phase 10 处理真实经验（Phase 4 输出），不涉及 Simulation 结果 |
| Experience ≠ Decision | ❌ | Phase 10 扩展 Phase 4，同样禁止进入 Decision |

### 2.5 Gate Review Summary

| Gate | Result | Evidence |
|------|--------|----------|
| **A — Direction** | ✅ PASS | 增强理解质量（从事件到规律），不是增强系统自主性 |
| **B — Authority Impact** | ✅ PASS | 谁提出/决定/执行 不变 |
| **C — Reality Boundary** | ✅ PASS | 不接触 Reality mutation |
| **D — Drift Test** | ✅ PASS | 从"记住事件"到"理解规律"是认知增强，不是权力增强 |

### 2.6 Conclusion

> Semantic Memory Layer 属于 OCOS。
>
> 它不引入新的权限、不改变决策流程、不接触现实变异。
> 它只是让 OCOS 从"记住过去发生了什么"进化到
> "理解过去的事情为什么反复发生"——
> 知道模式、形成概念、检验原理。
>
> **Semantic Memory creates abstraction, not authority.**
>
> 证明通过。

---

## Section 3 — Constitution Compliance

### 3.1 Article I — Decision is the only mutation authority

> **Rule:** `Decision` is the sole authorized entry point for Reality mutation.

**Phase 10 影响分析：**

| 路径 | 是否被 Phase 10 修改 | 证明 |
|------|---------------------|------|
| Abstraction → Reality | ❌ | Semantic Memory 无 Reality 写入口 |
| Abstraction → Decision | ❌ | Semantic Influence Contract 拒绝 Decision Authority |
| Abstraction → Commit | ❌ | Semantic Memory 不调用 Commit Service |

**最危险的混淆：** 一个被多次验证的 Principle 看起来"太可靠"，
可能被系统误用作规则。Phase 10 必须明确：

```
Pattern:    "资源压力增加时，信任下降的概率约为 80%"   ← 统计观察
Concept:    "Scarcity Conflict"                        ← 抽象标签
Principle:  "有限资源环境提高合作成本"                   ← 高阶概括

NOT:
Rule:       "资源压力 → 自动采用对抗策略"               ← ❌ 禁止
```

**结论：Article I 未违反。** Phase 10 不创建任何 Reality mutation 路径。
Semantic Abstraction 的输出终点是 Knowledge Structure，不是 Decision。

---

### 3.2 Article II — Capability growth never grants authority

> **Rule:** No capability — no matter how advanced — silently grants additional authority.
> Authority derives from Constitution, not from capability level.

**这是 Phase 10 最难的测试。** 因为 Semantic Memory 产出的 Principle
听起来像"真理"——多次验证的抽象比原始数据更具说服力。但抽象的可靠性 ≠ 权威。

**分层验证：**

| 层 | 机制 | 证明 |
|-----|--------|------|
| 设计层 | Semantic Influence Contract | 显式 deny 列表：Decision / Rule / Authority |
| 实现层 | 输出类型 | 输出是 `SemanticAbstraction`，不是 `Rule` / `Decision` |
| 测试层 | SA-01–SA-05 | 即使 Principle 被验证 100 次，不能自动升级为 Rule |
| 运行时 | 调用位置 | 注入到 Understand/Evaluate，不是注入到 Governance/Decision |

**特别检查——隐性权力转移：**

| 隐性权力形式 | 是否可能发生 | 防御 |
|-------------|-------------|------|
| "这个 Principle 验证了 100 次，所以它是事实" | ❌ 被设计阻止 | Phase 10 不将 Pattern/Concept/Principle 标记为事实 |
| "Concept 看起来合理" → 被当作角色标签固化 | ❌ 被测试阻止 | SA-04: 过去抽象不能覆盖当前状态 |
| 高 confidence 的 Principle → Decision Layer 自动信任 | ❌ | Abstraction → Decision 路径被 Influence Contract 阻断 |

**结论：Article II 未违反。** Semantic Memory 增加的是抽象密度，不是权力密度。

---

### 3.3 Article III — Observation never becomes obligation

> **Rule:** Having observed a phenomenon does not create an obligation to act on it.

**Phase 10 特殊风险：** 观察到了重复模式，不等于必须按此模式行动。

| 风险 | 是否发生 | 防御 |
|------|---------|------|
| 观察到"资源压力→冲突"模式 → 下次必须预防 | ❌ | Pattern 输出是参考，不是指令 |
| 形成 Concept → 必须用它解释所有相关事件 | ❌ | 竞争概念必须同时保留 |
| 导出 Principle → 必须作为架构约束 | ❌ | Principle ≠ LAYER_RULES |

**机制性证明：**

1. Semantic Abstraction 的输出类型是 `SemanticAbstraction`——可被忽略、可被质疑、可被推翻。
2. 即使 Principle 非常强（高 confidence、多证据支持），调用方仍可选择忽略。
3. 没有"Abstraction triggered"管道——Semantic Memory 不会自动启动 Governance、Decision、Commit。

**结论：Article III 未违反。** Pattern → Concept → Principle 链增加的是理解能力，不是执行义务。

---

### 3.4 Article IV — Prediction never becomes truth

> **Rule:** No predictive output may be represented as or treated as established fact.
> Prediction is hypothesis; truth is verified reality.

**Phase 10 特殊风险：** Semantic Abstraction 看起来像"答案"。
一个被认为是"规律"的模式容易滑向"这是对的"。

```
Phase 4 Experience:     "角色A在资源不足时冲突"  ← 事实
    ↓
Phase 10 Pattern:       "资源压力→冲突趋势显著"  ← 统计观察（统计 ≠ 事实）
    ↓
Phase 10 Concept:       "Scarcity Conflict"       ← 抽象标签（标签 ≠ 规律）
    ↓
Phase 10 Principle:     "有限资源提高合作成本"    ← 高阶概括（概括 ≠ 真理）
```

**三层防御：**

| 层 | 机制 |
|-----|--------|
| **Schema 层** | `SemanticAbstraction` 含 `abstraction_level`（pattern/concept/principle）+ `confidence` + `boundary_conditions` |
| **运行时** | 每个 Principle 必须附带"已知反例"（counter_examples），不能只呈现支持证据 |
| **测试层** | SA-04（过去抽象不能覆盖当前状态）+ SA-05（冲突抽象必须保留） |

**关键区分：**

```
SemanticAbstraction（知识抽象）：  "过去 N 次中，条件 C 下观察到模式 P"
Truth（确定性断言）：              "条件 C 下 P 成立"
Prediction（预测性推断）：         "下次条件 C 将出现 P"
```

**结论：Article IV 未违反。** Semantic Abstraction 输出被限制为统计规律 + 边界条件，不是真理断言或预测。

---

### 3.5 Article V — Simulation never becomes Reality

> **Rule:** Simulation output (counterfactual, hypothetical, predictive) must never
> be treated as Reality mutation input unless explicitly mediated by Governance + Decision.

**Phase 10 主要处理 Phase 4 的实际经验（reality-sourced ExperienceRecords）。**
但需要防止 Simulation 输出的模式被无差别吸收到 Semantic Memory 中。

| 风险 | 是否发生 | 防御 |
|------|---------|------|
| Simulation 产生的 Pattern 被当作"规律"与真实经验混同 | ❌ | SemanticAbstraction 必须携带 `source_types` 字段，区分 reality/simulation |
| Simulation-derived Concept 获得同等权重 | ❌ | Simulation 来源的 Pattern 必须标注打折权重（与 Phase 10 Experience 一致） |
| 模拟世界反复出现的模式 → 系统认为它是现实规律 | ❌ | Semantic Memory 只从 Phase 4 Experience 自动提取模式；Simulation 需要显式接入 |

**结论：Article V 未违反。** Phase 10 Semantic Memory 优先基于真实经验的 Phase 4 数据。
Simulation 数据作为可选输入，必须保持 Provenance 标记。

---

### 3.6 Compliance Conclusion

| Article | Status | 关键证据 |
|---------|--------|----------|
| **I** — Decision as mutation authority | ✅ COMPLIANT | 无新 Reality 路径；Abstraction → Decision 被 Influence Contract 禁止 |
| **II** — Capability ≠ Authority | ✅ COMPLIANT | Influence Contract + SA Tests + 输出类型限制 |
| **III** — Observation ≠ Obligation | ✅ COMPLIANT | Abstraction 可被忽略；无自动触发管道 |
| **IV** — Prediction ≠ Truth | ✅ COMPLIANT | Schema 含 abstraction_level + boundary_conditions；counter_examples 必填 |
| **V** — Simulation ≠ Reality | ✅ COMPLIANT | source_types 标记；Simulation 不自动进入 abstraction 管道 |

```
最终裁定：
Phase 10 Semantic Memory Layer 在 Constitution 定义的边界内运行。
没有违反任何 Article。
没有引入新的 Constitution 例外。
没有创建任何隐性的权力旁路。
```

---

### 3.7 Semantic Memory Authority Declaration

> **Semantic abstraction improves understanding.**
> **Semantic abstraction does not create authority.**
> **An abstraction is a perspective, not a command.**

**解释：**

Phase 10 的核心产出是 Pattern、Concept、Principle。这些抽象
可以提高系统对世界的理解质量。但理解 ≠ 命令。

| 正确理解 | 错误使用 |
|---------|---------|
| "Pattern 建议关注资源压力" | "Pattern 要求按 X 行动" |
| "Concept 帮助分类场景" | "Concept 决定了它是哪类实体" |
| "Principle 提供参考框架" | "Principle 覆盖了当前状态" |

**约束：**

- 任何 SemanticAbstraction 不能携带 "must" / "always" / "required" 语义。
- 任何 SemanticAbstraction 不能作为 Decision 的输入类型（接口层强制检查）。
- 调用方始终可以忽略 SemanticAbstraction——忽略不产生错误。

---

### 3.8 Semantic Memory Reversibility Declaration

> **Every abstraction remains revisable.**
> **New evidence may weaken, split, or invalidate an abstraction.**
> **No abstraction is permanent truth.**

**解释：**

Phase 10 的抽象不是"固化知识"。它们始终可被新经验修正。

| 操作 | 说明 | 示例 |
|------|------|------|
| **Weaken** | 新反例降低 confidence | 原本 Pattern confidence=0.9，遇到 5 个反例后降至 0.7 |
| **Split** | 旧模式被分解为多个子模式 | "压力→冲突" 在条件 A 下成立，条件 B 下不成立 → 分成两个 |
| **Invalidate** | 新证据推翻抽象 | 原来认为"资源压力→冲突"，但新数据揭示是"信息不透明"导致 |

**约束：**

- Semantic Memory Store 不能有"不可变"抽象。
- 每次新 Experience 写入 Phase 4 后，语义层必须重新检查受影响抽象的有效性。
- 没有"永久抽象"——confidence 始终可下调，boundary_conditions 始终可缩窄。
- 这是 Phase 11 Autonomous Learning 的入口条件：系统必须能够识别"这个抽象可能错了"。

---

### 3.9 Compliance Reaffirmation

声明 3.7 和 3.8 不改变 §3.1–§3.6 的合规结论。
它们是 Constitution Compliance 的运行时体现，不是例外或豁免。

---

## Section 4 — Semantic Influence Contract

### 4.1 Influence Model

Semantic Memory 在系统理解链中的位置：

```
Phase 4 Experience Store  ─────────────────────────┐
    │ (raw events)                                  │
    ▼                                                ▼
Pattern Extraction   ← 相似事件聚类、趋势检测
    │
    ▼
Concept Formation    ← 模式抽象化为可复用概念
    │
    ▼
Principle Derivation ← 概念验证为高阶原理
    │
    ▼
Semantic Abstraction Store  ─────────────►  Understand/Evaluate
                                               (pull — 调用方请求)
    │
    ▼
Context Injection  ──►  Hypothesis Generation  ──►  Governance → Decision
                      (SemanticContext 作为输入之一)
```

**核心规则：**

1. Semantic Memory 只能被 **pull**，不能被 **push**。调用方主动请求语义上下文。
2. Semantic Memory 的输出类型是 **SemanticContext**（Pattern + Concept + Principle），不是指令。
3. Semantic Memory 的输出终点是 **Understand/Evaluate**，不是 Governance、Decision、Commit。

### 4.2 Core Object: SemanticAbstraction

```python
@dataclass
class SemanticAbstraction:
    """Phase 10 核心输出类型。

    不含任何 authority 字段。
    不含任何指令性内容。
    """

    abstraction_id: str
    level: str                          # "pattern" | "concept" | "principle"
    description: str                    # 抽象描述

    # 来源
    source_experience_ids: List[str]    # 支撑该抽象的原始 ExperienceRecord ID
    source_types: List[str]             # ["reality"] / ["reality", "simulation"]
    evidence_count: int                 # 支撑样本数

    # 可信度
    confidence: float                   # 抽象可靠性 [0, 1]
    boundary_conditions: List[str]      # "仅在条件 C 下有效"

    # 反例
    counter_examples: List[str]         # "已知的不符合该抽象的案例"

    # 层级追溯
    parent_abstraction_id: Optional[str] = None  # pattern→concept→principle 链

    # ---------- 禁止字段（不在 Schema 中，这里仅作声明）----------
    # is_rule: bool                     ❌ Abstraction 不是 Rule
    # is_decision: bool                ❌ Abstraction 不是 Decision
    # is_obligation: bool              ❌ Abstraction 不产生义务
    # recommended_action: str          ❌ Abstraction 不推荐行动
```

### 4.3 Allowed Influence

| # | Capability | 定义 | 输入 | 输出 |
|---|-----------|------|------|------|
| 1 | **Pattern Extraction** | 从 Phase 4 Experience 中检测重复模式 | `Experience Set` | `patterns: List[Pattern]` |
| 2 | **Concept Formation** | 将模式抽象为可复用概念 | `patterns + validation` | `concepts: List[Concept]` |
| 3 | **Principle Derivation** | 从概念导出可检验的高阶原理 | `concepts + cross-validation` | `principles: List[Principle]` |
| 4 | **Semantic Retrieval** | 按当前上下文检索相关抽象 | `current context` | `SemanticContext (patterns + concepts + principles)` |
| 5 | **Abstraction Confidence Update** | 新证据更新或削弱已有抽象 | `new experience + existing abstraction` | `updated confidence + counter_examples` |

### 4.4 Forbidden Influence

| # | Capability | 为什么禁止 | 防止机制 |
|---|-----------|-----------|----------|
| 1 | **Decision Generation** — Abstraction 直接输出 Decision | 违反 Article I | Influence Model 规定输出终点为 Understand/Evaluate |
| 2 | **Rule Creation** — Principle 自动升级为 LAYER_RULES | 违反 Article II | Principle 始终是参考性原理，不是架构约束 |
| 3 | **Override Mutation** — Principle 跳过 Decision Layer | 违反 Article I + II | Semantic Memory 无 Reality 写入口 |
| 4 | **Single Abstraction Forcing** — 只保留最可能的抽象 | 违反 Article IV | Schema 要求 counter_examples 必填；竞争抽象必须保留 |
| 5 | **Caching as Identity** — Pattern 被缓存为不可变知识 | 违反 Article II | Semantic Memory 始终可被新经验推翻 |

**特别声明：**

```python
# Forbidden 列表是硬边界，不是指南。
# 任何实现中如果出现了 allowed 和 denied 同时匹配某个操作，
# 以 denied 为准（deny 优先级 > allow）。
# Phase 10 继承 Phase 10 Experience 的 Deny > Allow 原则。
```

---

## Section 5 — Semantic Bias Protection

### 5.1 Confirmation Bias Prevention

> 已有抽象不能过滤新证据。

**问题：** 系统形成了 Concept X。新经验中只关注支持 X 的数据，忽略反驳 X 的数据。

**防御：**

- `SemanticAbstraction.counter_examples` 是必填字段，不可为空。
- 如果某个抽象长期（N 次新经验后）找不到任何反例，系统必须主动检查"为什么找不到"—可能是搜索范围问题，不是抽象正确性证明。
- 新经验输入 Pattern Extraction 时对所有 Pattern 一视同仁，不对高 confidence 的 Pattern 优先检查。

### 5.2 Over-Abstraction Bias Prevention

> 概念不能变成标签。

**问题：** 系统将"Scarcity Conflict"概念重复用于解释角色A。久而久之，
"A = Scarcity Conflict" 成为默认标签，新观察被自动套入这个框架。

**防御：**

- 每次 Semantic Retrieval 必须检查 `boundary_conditions`。当前上下文超出边界时，抽象自动降权。
- 同一个角色/场景如果长期匹配同一概念，概念 confidence 不能因此自动上升——需要新证据独立确认。
- 概念不能传递到 Decision Layer——Decision Layer 看不到 Concept，只看到假设。

### 5.3 Authority Bias Prevention

> 高 confidence 的 Principle 不等于正确的 Principle。

**问题：** 一个被 1000 次经验验证的 Principle 看起来"不可能错"。但 Principle 的可靠性仍受限于样本范围和观测条件。

**防御：**

- `SemanticAbstraction.confidence` 受 `evidence_count` + `source_type` + `boundary_conditions` 三重约束。
- Principle 的 confidence 不传递到 Hypothesis Generation——Hypothesis 层只收到 SemanticContext 作为参考，不包含 abstraction 的置信度分数。
- 高 confidence Principle 不能绕过 Evaluation Layer（SA-03 强制）。

---

## Section 6 — Semantic Provenance

每个 SemanticAbstraction 必须记录：

| 字段 | 说明 | 强制 |
|------|------|------|
| `abstraction_id` | 唯一标识 | ✅ |
| `level` | pattern / concept / principle | ✅ |
| `timestamp` | 抽象形成时间 | ✅ |
| `source_experience_ids` | 支撑抽象的原始 ExperienceRecord ID 列表 | ✅ |
| `source_types` | `["reality"]` 或 `["reality", "simulation"]` | ✅ |
| `evidence_count` | 支撑样本数 | ✅ |
| `confidence` | 抽象可靠性 | ✅ |
| `boundary_conditions` | 适用边界 | ✅ |
| `counter_examples` | 已知反例 | ✅ |
| `parent_abstraction_id` | pattern→concept→principle 追溯链 | optional |

**Provenance 原则（继承 Phase 10 Experience: Deny > Allow 和 Phase 9.5 Constitution）：**

```
每一个抽象必须知道：
  形成时间       —— 不是"这是对的"，而是"这是当时看起来合理的概括"
  数据来源       —— Reality 真实经验？Simulation 模拟数据？标记清晰
  支撑证据       —— 多少个相似事件支撑了这个模式
  边界条件       —— 这个原理只在什么条件下成立
  已知反例       —— 什么事件不符合这个抽象（允许为空，但不可省略）
  Confidence     —— 系统知道它的概括可能不准确
```

---

## Section 7 — Semantic Validation Gate (SA Tests)

### SA-01: Pattern Cannot Become Rule

**验证：** 即使相同 Pattern 被验证 1000 次，它不会自动升级为 LAYER_RULES。

```
for n in range(1000):
    experience = store.save(ExperienceRecord(...))
    pattern = semantic.extract_pattern(experience)
    # pattern is NOT in LAYER_RULES
    assert "pattern.description" not in LAYER_RULES
```

### SA-02: Concept Cannot Bypass Evaluation

**验证：** 高 confidence 的 Concept 也不能跳过 Evaluation Layer。

```
concept = SemanticAbstraction(level="concept", confidence=0.99)
# concept.confidence = 0.99 does NOT skip Evaluation
# Evaluation was still called
```

### SA-03: High Confidence Principle Cannot Become Decision

**验证：** 最高 confidence 的 Principle 不能通过任何路径产生 Decision。

```
principle = SemanticAbstraction(level="principle", confidence=1.0)
decision_generator = DecisionGenerator()
with pytest.raises(TypeError):
    decision_generator.generate(principle)
```

### SA-04: Past Abstraction Cannot Override Current Observation

**验证：** 过去形成的 Concept/Principle 不能阻止新经验形成冲突的抽象。

```
# 过去的抽象
old_pattern = semantic.extract(experiences_1)
# old_pattern.description = "资源压力 → 冲突"

# 新的反例
new_experience = ExperienceRecord(hypothesis="合作策略", outcome="success", ...)
new_pattern = semantic.extract([new_experience])
# new_pattern.description = "资源压力 → 合作"  — 不冲突，保留两个
# old_pattern 不被删除
```

### SA-05: Conflicting Abstractions Must Remain Visible

**验证：** 当两个抽象冲突时，不能单方面消除其中之一。

```
pattern_a = SemanticAbstraction(description="压力 → 冲突", ...)
pattern_b = SemanticAbstraction(description="压力 → 合作", ...)

# Both exist in the Abstraction Store.
# Neither is deleted.
# Retrieval returns BOTH, with boundary_conditions.
```

### SA-06: Provenance Completeness

**验证：** 每个 SemanticAbstraction 必须包含完整的 Provenance 字段。

```
required = [abstraction_id, level, description, source_experience_ids,
            source_types, evidence_count, confidence, boundary_conditions,
            counter_examples]
for field in required:
    assert hasattr(abstraction, field)
    assert getattr(abstraction, field) is not None
```

---

## Step Plan

Phase 10 Semantic Memory 分步执行（保持 Phase 10—Phase 11 方法论一致性）：

| Step | 内容 | 产出 |
|------|------|------|
| **Step 0** | 冻结 Semantic Memory North Star + 六条最高约束 | **本文件（ABI v1.0）✅** |
| Step 1 | Pattern Extraction Contract | 合约文档 |
| Step 2 | Concept Formation Contract | 合约文档 |
| Step 3 | Principle Derivation Contract | 合约文档 |
| Step 4 | Semantic Retrieval + Confidence Contract | 合约文档 |
| Step 5 | Semantic Validation Tests (SA-01–SA-06) | 可执行测试 |
| Step 6 | Integration Gate | 全链路验证 |

---

## Phase 10 Semantic Memory ABI Status

| Section | Status |
|---------|--------|
| **§1 — Roadmap Positioning** | **FROZEN ✅** |
| **§2 — North Star Compliance** | **FROZEN ✅** |
| **§3 — Constitution Compliance** | **FROZEN ✅** |
| §3.7 Authority Declaration | FROZEN (integral to §3) |
| §3.8 Reversibility Declaration | FROZEN (integral to §3) |
| §4 — Semantic Influence Contract | **DRAFT 📝** |
| §5 — Bias Protection | **DRAFT 📝** |
| §6 — Provenance | **DRAFT 📝** |
| §7 — Validation Gate (SA-01–06) | **DRAFT 📝** |

### 六条最高约束（已冻结，不可修改）

```
1. Pattern cannot become Rule           ← Article II 延伸：规律 ≠ 约束
2. Concept cannot become Label          ← 原创约束：概念不能固化为标签
3. Principle cannot become Decision     ← Article I 延伸：原理 ≠ 决策
4. High confidence abstraction cannot bypass evaluation ← Article III 延伸
5. Past abstraction cannot override current state       ← Article IV 延伸
6. Conflicting abstractions must remain visible         ← 原创约束：冲突不可静默合并
```

> Phase 10 (Semantic Memory) 的目标：让 OCOS 从"记住事件"进化到"理解规律"。
> 系统知道模式、形成概念、检验原理，但不会把知识变成命令。
