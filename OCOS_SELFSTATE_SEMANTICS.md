# OCOS SelfState Schema / Semantics Audit

> **目的：把 SelfState 的语义和边界彻底定下来 —— 不是查代码有没有这些字段，而是逐字段回答"它到底是什么、凭什么这么判断、怎么变化"。**
> **范围：纯语义定义，不写代码、不查 bug。**
> **状态：v0.2 —— 方向 GO；Schema v1 已冻结，见 `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`。**
> **日期：2026-09-13（Asia/Shanghai）**
> **前置：`OCOS_COGNITIVE_IDENTITY_AUDIT.md` v0.2（已冻结 §8 决策，裁决：GO/可冻结）。**

---

## 0. 一句话立场

SelfState 不是"一堆域的数据"，而是一个**能回答三个横向问题的自我**：

> 为什么(? Evidence) · 多确定(? Confidence) · 什么从 A 变到 B(? Continuity)

当 5 横向语义 × 7 纵轴都各自有答案时，它才真正像一个"自我"。
**现在不写代码。** 顺序是：语义（本文件）→ Freeze Gate（G1–G5）→ 913 文件反查 → 反推去留 → P0/P1/P2。

---

## 1. Growth Invariant（X/Y/Z —— 项目级最高验收，冻结）

```text
X = 过去真实发生的经历
Y = 现在实际产生的认知 / 行为
Z = 如果没有 X，原本会产生的认知 / 行为

X → Self Delta → Cognition Delta → Y       且  Y ≠ Z
```

**最重要的不是 `Y ≠ Z`，而是必须能解释为什么 `Y ≠ Z`。**

不能解释原因的，以下全部不算成长：

```text
Episode +1 · Knowledge +1 · Self version +1 · Belief +1 · Prompt context +1
```

既有原则被本架构正式吸收：**Recall 进入 Prompt ≠ 行为改变**（A11/A12 行为验证结论）。

---

## 2. 七纵轴语义定义（冻结为 Schema 的语义定义表）

| 域 | 一句话定义 | 回答的问题 |
|---|---|---|
| **Situation** | `= NOW` | 我现在处在哪里 / 当前处于什么状态 |
| **Experience** | `= WHAT HAPPENED` | 我经历过什么（真正改变过我的） |
| **Memory** | `= WHAT I RETAIN` | 我记得什么（索引视图） |
| **Cognition** | `= WHAT I AM THINKING` | 我正在想什么 |
| **Worldview** | `= WHAT I THINK THE WORLD IS` | 我认为世界是什么样 |
| **Capability** | `= WHAT I THINK I CAN DO` | 我认为自己能做什么 |
| **Identity** | `= WHO I AM` | 我是谁（不可变锚） |

---

## 3. 五横向语义：约束，不是数据域（v0.2 修正）

**Evidence / Confidence / Provenance / Temporal / Continuity 不是 SelfState 的五个"数据域"，而是所有可演化子域的横向语义约束。**

```text
SelfState
│
├── Vertical Domains
│   ├── Identity · Situation · Memory · Experience · Capability · Worldview · Cognition
│
└── Cross-Cutting Semantics   ← 约束，不建独立表
    ├── Evidence      我为什么这么认为
    ├── Confidence    我有多确定
    ├── Provenance    这个认识从哪来（排除外部直接注入）
    ├── Temporal      它是什么时候成立的
    └── Continuity    我什么时候从 A 变到 B，为什么
```

**数据库设计红线**：禁止出现 `self_evidence` / `self_confidence` / `self_provenance` 之类的独立表。它们必须**附着在具体的 Self Claim / Self Delta / Self Judgment 上**。

---

## 4. G1 · 最小原子 = Self Claim（不是 Domain）

真正的最小原子不是 Domain，而是 **Claim**：

```text
Capability
    └── Claim
          ├── subject      主题（如 "我在复杂 shell 操作上的可靠性"）
          ├── predicate    谓词（如 "较低"）
          ├── value        值
          ├── evidence[]   证据引用列表
          ├── confidence   置信度
          ├── provenance   来源
          ├── temporal     成立时间
          └── continuity   变化链
```

例（不是 `shell_success_rate = 30.9%`，而是）：

```text
Self Claim: "我在复杂 shell 操作上的可靠性较低"

Evidence:    E2894 · E2716 · E2472
Confidence:  0.82
Provenance:  empirical_episode

Previous:    "我可以稳定完成 shell 操作"
Delta:       reliability_assessment ↓
Reason:      repeated execution failures
```

**S1 的正确进入路径**（不是 S1 → 直接改 SelfModel）：

```text
S1 (agent_self_model)
  ↓ 只作为
Evidence
  ↓
Self Claim
  ↓
Self Delta
  ↓
SelfModel
```

> S1 **不删除**：它不能因为"我觉得自己很厉害"就证明自己厉害 —— 它是客观能力统计证据。降级不是削弱，是放回正确位置。

---

## 5. G2 · Self Delta 标准结构

```text
SelfDelta
├── delta_id           稳定对象标识
├── claim_ref          受影响的 Claim
├── from_value         旧认识（Self 认知变化之起点；即 Z 或上一个状态）
├── to_value           新认识（Self 认知变化之终点）
├── type               strengthen / weaken / reverse / uncertain
├── reason             ★为什么变（必填，否则不算 delta）
├── evidence[]         触发证据
├── counterfactual_Z   反事实基线（见 G4）
├── created_at         时间锚
├── affects            self_claim | worldview_claim
└── cognition_implication  这个 Self Delta 如何改变下一次思考
```

> 正式规范以 `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md` §3.1 为唯一标准。

**G1 + G2 一旦确定，持久化自然成形，而不是先设计一堆表**：

```text
Identity → Self Claim → Evidence → Confidence → Delta → Version → Continuity
```

---

## 6. G3 · Continuity 拆分为两个概念

```text
Continuity
├── State Continuity       "我还是同一个我"    ← identity_ref 不变
└── Cognitive Continuity   "现在的我为什么不同于过去的我" ← v371 = v370 + D，D 必须有原因
```

**红线**：`identity_ref = same, version = 371` 只代表 State Continuity（同一个 ID ≠ 认知连续）。真正需要证明的是：

```text
v370
  │ Experience X
  ↓
Delta D（有原因）
  ↓
v371 = v370 + D
```

---

## 7. Memory ≠ Experience（冻结）

> **我记得发生过什么，不等于那件事改变了我。**

```text
Memory
    ├── 普通记忆         （如 "Episode #100：今天执行 ls 成功"）
    └── Self-relevant memory
              ↓ 只有当它产生 Self/Cognitive Delta
         Experience（真正改变过我的）
              ↓
         Self Delta
```

- 进 Memory：发生过且我记住。
- 进 Experience（Self-relevant）：**产生了 Self/Cognitive Delta**。

---

## 8. G5 · Worldview = 投影认识，不是世界复制（冻结原则）

```text
WorldModel           世界的模型（客观本体，如 shell command X → environment behavior Y）
      ↓ 引用投影（不复制）
SelfState.worldview  "我对世界的认识"（带主体视角 + 证据 + 置信度）
```

```text
WorldModel:   shell command X → environment behavior Y
Worldview:    "我目前认为在环境 E 中，X 通常会导致 Y"
              confidence = 0.73
              evidence   = E123, E127
```

**红线**：Worldview 是带主体视角、证据和置信度的认识，不是 WorldModel 的副本。

**G5 已冻结：Worldview 是 Self 对 WorldModel / Knowledge / Experience 综合形成的主体性认识，不复制 WorldModel。**（正式规范见 `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md` §6）

---

## 9. Cognition Self 严格定义（防退化）

`cognition_self` 极易退化成"把当前 Prompt 存下来"→ 重新变成 Prompt Engineering。**禁止。**

严格定义为：

> 当前认知状态中，已经形成、正在形成、或影响下一次思考的主体性认知状态。

必须能携带：

```text
Current Belief                我现在相信什么
Current Hypothesis            我正在假设什么
Current Uncertainty           我现在不确定什么
Current Focus                 我当前专注什么
Current Strategy Intention    我下一步打算采取什么策略
Overturned Previous Understanding  被现实推翻的旧认识
Open Question                 我留着的开放问题
```

其中最关键的一条：

```text
Previous Understanding
        ↓ Reality contradicted
Current Understanding
```

**这一部分是 SelfState 与普通 Context 的真正区别** —— 上下文是信息，这里是被经历改造过的"我"。

---

## 10. 三层总结构（冻结）

```text
                 ┌─────────────────────┐
                 │     IDENTITY        │   我是不是同一个我
                 └──────────┬──────────┘
                            │
                     SelfState
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
      STATE              HISTORY             CHANGE
        │                   │                   │
  Situation             Memory              Delta
  Capability             Experience          Continuity
  Worldview                                  Why
  Cognition
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ↓
                        THINKING
                            ↓
                         ACTION
                            ↓
                         REALITY
                            ↓
                      OBSERVATION
                            ↓
                       EXPERIENCE
                            ↓
                        LEARNING
                            ↓
                       SELF UPDATE
                            ↺
```

OCOS 的核心不再是一个"有很多认知模块的 Agent"，而是：
**一个具有身份连续性、经历连续性和认知连续性的持续存在主体。**

---

## 11. Freeze Gate 结果（G1–G5 全部冻结）

| 门 | 内容 | 判定 |
|---|---|---|
| **G1** | Self Claim 最小语义原子 | 🟢 GO / Freeze（新增 claim_id） |
| **G2** | Self Delta 标准结构 | 🟢 GO / Freeze（新增 delta_id + cognition_implication） |
| **G3** | Continuity = State + Cognitive | 🟢 GO / Freeze |
| **G4** | Counterfactual Z 持久化 / 重建 | 🟢 Freeze：持久化优先 + 可验证重建兼容 |
| **G5** | Worldview 与 WorldModel / Knowledge 投影关系 | 🟢 Freeze：主体性认识投影，不复制 WorldModel |

**全部冻结内容见 `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`。**

---

## 12. 路线（冻结）

```text
① Self Identity Audit v0.2          ✅ FREEZE
② SelfState Semantics v0.2          ✅ FREEZE
③ SelfState v1 Freeze               ✅ FREEZE
④ Claim / Delta / Continuity Freeze ✅ FREEZE
⑤ 913-file reverse mapping          ⬜ NEXT
⑥ 模块语义映射（8 类：
   Self / Evidence / World / Memory / Cognition / Governance / Tool / Legacy）
⑦ Retain / Rewrite / Merge / Archive
⑧ P0 / P1 / P2
⑨ Implementation
```

**为什么不跳过 ③④ 直接接 S2**：避免把一个还没有完全定义清楚的"我"接进生产系统。

**⑤ 反查应采用的审计问题（冻结）**：

> 这个模块服务于哪个部分的我？
> 如果它不存在，那个"我"的哪一种连续性会断掉？

而不是"这个模块有没有用"。