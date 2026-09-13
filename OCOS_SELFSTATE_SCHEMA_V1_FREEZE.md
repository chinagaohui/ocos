# OCOS SelfState Schema v1 — Freeze

> **性质：这不是"数据库 Schema"，而是一套可审计的主体语义系统。**  
> **状态：v1 FREEZE —— 语义内核冻结，冻结后不可语义漂移；任何改动必须走修订流程。**  
> **日期：2026-09-13（Asia/Shanghai）**  
> **文档链：**  
> `OCOS_COGNITIVE_IDENTITY_AUDIT.md` v0.2（GO/可冻结）→ `OCOS_SELFSTATE_SEMANTICS.md` v0.2（GO）→ **本文件（FREEZE）**

---

## 0. 冻结判定总表

| Gate | 判定 |
|---|---|
| G1 Self Claim | 🟢 GO / Freeze |
| G2 Self Delta | 🟢 GO / Freeze（增加 `delta_id` + `cognition_implication`） |
| G3 Continuity | 🟢 GO / Freeze |
| G4 Counterfactual Z | 🟢 Freeze：持久化优先、可验证重建兼容 |
| G5 Worldview | 🟢 Freeze：主体性认识投影，不复制 WorldModel |

---

## 1. 语义验收公理（Growth Invariant 完整链）

### 1.1 成长主链（冻结）

```text
Reality
  ↓
Observation
  ↓
Experience X
  ↓
Recognition
  ↓
Self Claim
  ↓
Self Delta
  ↓
Cognition Delta
  ↓
Current SelfState
  ↓
Thinking
  ↓
Y
```

### 1.2 成长必须能回答（冻结）

```text
X：过去到底发生了什么？
A：过去的我怎么理解？
为什么 A 被现实推翻？
D：发生了什么认知变化？
B：现在的我怎么理解？
Y：因此现在实际产生了什么不同？
Z：如果没有 X，本来会怎样？
Y ≠ Z
```

### 1.3 变量定义与判定（冻结）

```text
X = Experience（过去真实发生的经历）
A = Previous Self/Cognitive State
D = Self Delta
B = Current Self/Cognitive State
Z = Counterfactual baseline
Y = Actual current cognition/behavior

X → A → Reality contradicts A → D → B → Cognition changes → Y

AND  Y ≠ Z
AND  causal explanation exists（必须能解释为什么 Y ≠ Z）
```

### 1.4 不算成长（冻结）

```text
Episode +1 · Knowledge +1 · Self version +1 · Belief +1 · Prompt context +1
Learning → version +1 → Prompt 多了一句话
```

以上全部不算成长。已有原则吸收：**Recall 进入 Prompt ≠ 行为改变**（A11/A12）。

---

## 2. G1 · Self Claim — FREEZE

最小语义原子 = **Claim**（不是 Domain）。

### 2.1 结构（冻结）

```text
SelfClaim
├── claim_id            ← 新增：稳定对象标识，供 Delta/历史/Cognition 引用
├── subject             主题（如 "我在复杂 shell 操作上的可靠性"）
├── predicate           谓词（如 "较低"）
├── value               值
├── evidence[]          证据引用列表
├── confidence          置信度
├── provenance          来源
├── temporal            成立时间
└── continuity          变化链
```

> 无 `claim_id`，`claim_ref` 会退化成"某一段 JSON 的路径"。Claim 必须是可被 Delta 引用、被历史版本引用、被 Cognition 引用的**稳定对象**。

### 2.2 例（冻结）

```text
Self Claim: "我在复杂 shell 操作上的可靠性较低"

Evidence:    E2894 · E2716 · E2472
Confidence:  0.82
Provenance:  empirical_episode
```

### 2.3 S1 进入路径（冻结）

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

S1 不删除：它不能因为"我觉得自己很厉害"就证明自己厉害 —— 客观能力统计证据，降级不是削弱。

---

## 3. G2 · Self Delta — FREEZE

### 3.1 结构（冻结）

```text
SelfDelta
├── delta_id              ← 新增：稳定对象标识
├── claim_ref            受影响的 Claim
├── from_value           旧认识（Self 认知变化之起点）
├── to_value             新认识（Self 认知变化之终点）
├── type                 strengthen / weaken / reverse / uncertain
├── reason                ★为什么变（必填，否则不算 delta）
├── evidence[]           触发证据
├── counterfactual_Z     反事实基线（见 G4）
├── created_at           时间锚
├── affects              self_claim | worldview_claim
└── cognition_implication  ← 新增：这个 Self Delta 如何改变下一次思考
```

### 3.2 关键语义（冻结）

**`from_value → to_value` 是"我对自己的认识"的变化；`cognition_implication` 说明它如何改变下一次思考。二者不是同一个东西，Y 也不等于 SelfState 的新认识。**

```text
X:                      连续 3 次 shell 操作失败

旧 Self Claim A:        "我可以稳定完成复杂 shell 操作"
Self Delta D:           "我的复杂 shell 操作可靠性低于原先判断"
新 Self Claim B:        "我在复杂 shell 操作上可靠性较低"
Cognition Delta:        "下一次复杂 shell 任务，我应该先验证命令环境，而不是直接执行"
Y:                      下一次实际行为采用验证策略
```

### 3.3 伪成长堵漏（冻结）

```text
Learning → Self version +1 → Prompt 多了一句话        ← 伪成长，禁止
Experience → Recognition → Self/Cognitive Delta → Future Thinking → Y ≠ Z   ← 真成长
```

---

## 4. G3 · Continuity — FREEZE

### 4.1 拆分（冻结）

```text
Continuity
├── State Continuity       "我还是不是同一个我？"    ← identity_ref 不变
└── Cognitive Continuity   "为什么现在的我和过去不同？" ← v371 = v370 + D
```

### 4.2 红线（冻结）

```text
identity_ref == same
```
只能证明**还是这个 OCOS**，不能证明**它还是沿着认知历史连续成长过来的**。

```text
v370
  ↓ Experience X
  ↓ Delta D
v371
```

必须能回答：`v371 = v370 + 什么？为什么？依据什么？` 否则 `version=371` 没有认知意义。

---

## 5. G4 · Counterfactual Z — FREEZE（持久化优先 + 可验证重建兼容）

### 5.1 冻结原则

> **Z 是成长因果链的一等语义对象。新产生的成长事件必须持久化 Z；历史事件允许基于可验证历史证据重建，但必须标记 `reconstructed`，并携带置信度与证据来源。**

不可伪造历史 + 可以兼容旧数据。

### 5.2 Experience X 结构（冻结）

```text
Experience X
├── actual_outcome        实际结果
├── recognized_delta      被识别的认识变化
├── counterfactual_Z      反事实基线（一等语义对象）
└── causal_explanation    因果解释
```

### 5.3 重建规则（冻结）

```text
优先：persisted Z（历史留痕，事后不可篡改）

否则（早期 Experience 未显式保存 Z）：
reconstruct Z from
    previous cognition    先前认知
    previous strategy     先前策略
    previous decision     先前决策
    same-task baseline    同任务基线
    historical policy     历史策略

重建产物必须标记：
    counterfactual_source = reconstructed
    confidence = ...
不能与原始记录等价
```

### 5.4 为什么不能只重建（冻结）

> 如果 Z 没保存，几年后再问"当时如果没有这次经历，OCOS 本来会怎么做？"只能让今天的 LLM 重猜 → `历史事实 + 今天的 LLM → 重新编造过去的 Z`。这不是审计意义上的成长证据。

---

## 6. G5 · Worldview — FREEZE（主体性认识投影，不复制 WorldModel）

### 6.1 冻结定义

> **Worldview 不是 WorldModel 的复制品，也不是简单 projection cache，而是 Self 对 WorldModel / Knowledge / Experience 综合形成的主体性判断。**

```text
                 World
                   ↓
             Observation
                   ↓
          ┌────────┴────────┐
          ↓                 ↓
     WorldModel         Experience
          ↓                 ↓
          └────────┬────────┘
                   ↓
              Knowledge
                   ↓
              Self cognition
                   ↓
               Worldview
```

### 6.2 可引用，不复制（冻结）

Worldview 可以引用：

```text
world_entity_id · world_relation_id · knowledge_id · episode_id · observation_id
```

但不复制整个 WorldModel。

### 6.3 必须允许被推翻（冻结）

```text
WorldModel:   X → Y

Worldview:    "我认为在环境 E 中，X 通常导致 Y"   confidence = 0.73

Experience:   X → Z   → Reality contradicts worldview

Worldview Delta:
  A:          X usually → Y
  B:          X may → Z under condition C
  Reason:     E123 / E127 / E198
  Confidence: 0.73 → 0.61
```

这才是"我对世界的理解发生了变化"，而不是 WorldModel 表里多了一行。

### 6.4 三区分（冻结）

| 概念 | 回答 | 内容 |
|---|---|---|
| **WorldModel** | 世界实际上是什么结构？ | entity · relation · state · event · causal relation |
| **Knowledge** | OCOS 保留下来的可复用知识是什么？ | "X 在条件 C 下通常导致 Y" |
| **Worldview** | 我现在认为世界是什么样？ | 天生带 subject · confidence · evidence · temporal validity · history |

```text
Knowledge:  X → Y
Worldview:  "我相信 X → Y，置信度 0.73，因为 E123/E127"
```

---

## 7. 七纵轴语义（7 Domains）— FREEZE

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

## 8. 五横向语义 — FREEZE（约束，不是数据域）

```text
SelfState
│
├── Vertical Domains
│   └── Identity · Situation · Memory · Experience · Capability · Worldview · Cognition
│
└── Cross-Cutting Semantics   ← 约束，附着于 Claim / Delta / Judgment
    ├── Evidence      我为什么这么认为
    ├── Confidence    我有多确定
    ├── Provenance    这个认识从哪来（排除外部直接注入）
    ├── Temporal      它是什么时候成立的
    └── Continuity    我什么时候从 A 变到 B，为什么
```

**红线**：禁止出现 `self_evidence` / `self_confidence` / `self_provenance` 独立表。

---

## 9. Boundary Redlines（七条）— FREEZE

```text
① Memory ≠ Experience         我记得 ≠ 改变了我
② WorldModel ≠ Worldview      世界本身 ≠ 我对世界的认识
③ WorldModel ≠ Knowledge      客观结构 ≠ 可复用知识
④ SelfState ≠ Context         Cognition Self 最易被破坏处
⑤ Identity ≠ Self（SelfModel） 不可变锚 ≠ 可演化投影
⑥ Self ≠ Goal                 自我不产生目标（S40）
⑦ Self ≠ Belief               自身状态判断 ≠ 世界判断（S40-03）
```

### 9.1 SelfState ≠ Context 的精确边界（冻结）

```text
Context:     "我现在看到了什么信息？"
Cognition:   "我现在因此形成了什么判断、假设、不确定性、策略意图？"
SelfState:   "这些判断如何成为'我的当前认知状态'，并且它们为什么不同于过去的我？"
```

```text
Prompt context +1  ≠  Cognition Delta  ≠  Self Growth
```

---

## 10. Cognition Self 严格定义 — FREEZE（防退化）

禁止退化为"把当前 Prompt 存下来"。必须能携带：

```text
Current Belief                我现在相信什么
Current Hypothesis            我正在假设什么
Current Uncertainty           我现在不确定什么
Current Focus                 我当前专注什么
Current Strategy Intention    我下一步打算采取什么策略
Overturned Previous Understanding  被现实推翻的旧认识
Open Question                 我留着的开放问题
```

关键链：

```text
Previous Understanding → Reality contradicted → Current Understanding
```

这是 SelfState 与普通 Context 的真正区别。

---

## 11. 三层总结构 + 生命环 — FREEZE

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

OCOS = **一个具有身份连续性、经历连续性和认知连续性的持续存在主体**，而不是"有很多认知模块的 Agent"。

---

## 12. 语义闭环（G1–G5 一句话）— FREEZE

```text
G1 Self Claim            → "我现在相信什么"
G2 Self Delta            → "我为什么从 A 变成 B"
G3 Continuity            → "为什么这个 B 仍然属于同一个持续存在的我"
G4 Counterfactual Z      → "如果没有 X，我原本会怎样"
G5 Worldview Projection  → "我对世界的认识是什么，而不是世界本身是什么"
```

---

## 13. 冻结后的唯一动作

本文件冻结后，才允许进入 **913 文件反查**。顺序：

```text
① Self Identity Audit v0.2          ✅ FREEZE
② SelfState Semantics v0.2          ✅ FREEZE
③ SelfState v1 Freeze               ✅ FREEZE
④ Claim / Delta / Continuity Freeze ✅ FREEZE
⑤ 913-file reverse mapping          ⬜ NEXT
⑥ 模块语义映射（8 类：Self / Evidence / World / Memory / Cognition / Governance / Tool / Legacy）
⑦ Retain / Rewrite / Merge / Archive
⑧ P0 / P1 / P2
⑨ Implementation
```

**⑤ 反查审计问题（冻结）**：

> 这个模块服务于哪个部分的我？
> 如果它不存在，那个"我"的哪一种连续性会断掉？

而不是"这个模块有没有用"。**先定义"我是谁"，再检查代码里哪些东西真正服务于这个"我"** —— 不能被现有代码结构绑架。

---

## 14. 913 文件反查判定矩阵（冻结）

**SelfState v1 已最小闭环，不再扩展字段。** 反查阶段从"这个模块有没有价值"改为以下判定矩阵：

| 维度 | 必答问题 |
|---|---|
| Subject | 它服务"我"的哪个部分？ |
| Domain | Identity / Situation / Memory / Experience / Capability / Worldview / Cognition？ |
| Semantic Role | Self / Evidence / World / Memory / Cognition / Governance / Tool / Legacy？ |
| Evidence | 它产生什么可验证证据？ |
| Mutation | 它能改变 SelfState 什么？ |
| Continuity | 它维持哪一种连续性？ |
| Causality | 能否进入 X → D → Y？ |
| Authority | 它有没有改变 Self 的权限？ |
| Persistence | 它的状态是否跨 restart 连续？ |
| Production | 是否真正进入生产主链？ |
| **SelfState Impact** | **它最终改变 SelfState 的哪一部分？** ∈ {Identity, Situation, Memory, Experience, Capability, Worldview, Cognition, **None**} |
| Disposition | Retain / Rewrite / Merge / Archive |

**SelfState Impact 判定规则（冻结）**：
- 值为 **None** 时：继续问"它是不是 Governance / Tool？"
- 若连 Governance / Tool 都不是 → **高度疑似 Legacy**。

**Disposition 两级裁决门（冻结，升级末问）**：

```text
                    ┌─ SelfState Continuity ─ YES → Core
Module ─────────────┤
                    ├─ Governance / Authority   → Core Boundary
                    ├─ World / Tool Capability → External Capability
                    └─ None                     → Legacy / Archive

第二道门（对 Core）：
Core 能否进入 X → D → Y？
  YES → 主体核心
  NO  → 只是 Evidence / Memory / Tool / Governance？→ 保留，但 NOT Self Core
```

**防误判红线（冻结）："重要 ≠ 属于 Self"**
SQLite=Persistence · LLM=External Cognition Resource · WorldModel=World · DecisionBridge=Authority · Governance=Boundary · Shell capability=Capability —— 它们都不是"我"。

**追加字段 —— Consumer / Downstream Effect（冻结，⑥ 必查）**：

对每个 symbol 额外回答：`Producer → Artifact → Consumer → Consumer Effect → SelfState Impact → X→D→Y position`。

- **Producer**：它产生什么对象。
- **Consumer**：这个对象最终被谁消费？
- **Consumer Effect**：被消费后造成什么（Knowledge? Episode? SelfClaim? Decision? Cognition? Prompt?）

这是为了把"生产了什么"和"真正改变了什么"彻底分开：
```text
A 产生了一个看起来重要的对象
   但没人消费 → 遗留
   或只被 Prompt injection → Prompt injection ≠ Cognition Delta
```

**五级消费证据分级（冻结，严禁混用）**：

```text
① Recall Evidence              对象被召回
② Prompt Injection Evidence    对象进入了 Prompt
③ Decision Consumption Evidence 对象被 Decision 消费
④ Behavioral Delta Evidence    Action₂ ≠ Action₁
⑤ Causal Growth Evidence       消费了 D 且 Y ≠ Z 且因果解释存在
```

```text
FailureLesson → MEM_CTX → DecisionBridge → LLM → Action
```
不能只因为"Lesson 影响了 Decision"就判学习成功；必须证明 `Action₂ ≠ Action₁` 且 `Decision₂/Action₂ 确实消费了 D`，最后落到 ⑤ Y ≠ Z。

**追加字段 —— Causal Attribution（冻结，⑥ 必查，与 Causality 严格区分）**：

```text
Causality           = 理论上能不能进入 X → D → Y（机制具备路径）
Causal Attribution  = 当前这次生产行为，能不能证明确实是这个 X / D 导致了 Y（实际因果）
```

例：
```text
FailureLesson
  Causality          = YES（理论上可影响 Cognition）
  Causal Attribution = UNPROVEN
      原因：无同任务 baseline；无 Action₁/Action₂ 对照；未证明 Decision₂ 消费了 Delta
```

**禁止**：把"具备 X→D→Y 路径"当作"已实现成长"。

**最后一个问题（冻结）**：

> 如果这个模块删除，"我"的哪一种连续性会断？

若答案是"没有任何 Self / Memory / Experience / Cognition / World / Governance 连续性会断"，那么即使它"功能很多"，**也没有资格因为"有用"留在主体核心里**。

### 14.1 第一阶段只做语义映射，不做整改

```text
913 files
   ↓
Semantic Reverse Mapping
   ↓
每个模块属于什么
   ↓
服务 Self 的哪一部分
   ↓
依赖什么
   ↓
产生什么证据
   ↓
是否维持连续性
   ↓
生产是否真实使用
```

然后得到三分：

```text
Core Self          Cognitive/World       External
Retain / Rewrite   Retain / Merge        Tool / Capability
New                Archive
        ↓
P0 / P1 / P2 → Implementation
```

**代码不再定义 OCOS；SelfState 开始定义代码应该留下什么。**