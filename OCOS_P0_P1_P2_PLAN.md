# OCOS P0 / P1 / P2 计划 — 主体生命链建设（⑧）

> **性质：阶段切换宣言 —— 从"代码考古"切到"主体生命链建设"。** 只定契约方向，不进入 Implementation（⑨）。实现需本计划批准后逐项推进。
> **状态：FREEZE（⑧ 方向契约正式冻结，2026-09-13）。** 已吸收裁决修订：P0-4-Z Counterfactual Baseline Freeze（Attempt 2 前冻结 Z）、T-S1 authoritative source 精确化、P2 Protected Semantic Path 红线。
> **输入** = `OCOS_913_SEMANTIC_MAP.md` v0.5（⑥⑦完成）+ `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`（v1 冻结 + §14.2/14.3 升级 + §15）。
> **日期：2026-09-13（Asia/Shanghai）**
> **文档链**：FREEZE（契约）→ 913_MAP（反查）→ **本文件（⑧ P0/P1/P2，FREEZE）** → ⑨ Implementation（待 P0-1→P0-2→P0-4 推进）。

---

## 0. 阶段切换的唯一总问题

> 不再问"哪些模块还没完成"，只问：
>
> **"能不能让 OCOS 因为真实发生过的 X，形成可审计的 Self/Cognition Delta，并在下一次同类 Thinking 中产生可归因的 Y ≠ Z？"**

**⑧ 的唯一交付物**（Gate，冻结）：

> **不是"完成多少模块"，而是建立并验证一条不可伪造的主体生命链：真实 Experience X 经 Recognition 形成 Self/Cognition Delta D，D 被下一次 Thinking/Decision 实际消费，并在受控反事实基线 Z 下产生可归因的 Y ≠ Z。**

- **PASS** → Life-chain established → 可进 P1。
- **FAIL** → Architecture evidence（当前 OCOS 不具备被证明的 X→D→Y 因果成长能力），**不得以调 Prompt/规则补丁绕过，不进入 P1**。
- **红线**：不要做成"让整个代码库证明自己会成长"的荒谬工程 —— 只有主体候选模块进入 Causal Attribution 验收（分层口径见 FREEZE §14.2）。

---

## 1. 架构地图（反查收口后的目标形状）

```text
OCOS / 我
├── Identity · Situation · Experience · Memory · Cognition · Worldview · Capability
│        └────────────────────────────────────────────────
│                         SelfState
│                              ↓
│                          Thinking → Decision → Action → Reality → Observation → Experience
│                              ↓
│                    Recognition → Self Claim → Self Delta → Cognition Delta → (回到 SelfState) ↺
└──────────────────────────────────────────────
外围（维持/使用边界）
├── Governance / Authority / Runtime / Persistence / Security / Recovery  → 保护"我"，不属于"我"
└── LLM / WorldModel / Shell / Browser / Tools / Interaction             → "我"使用的外部能力
Legacy：os_v1 / _archive / examples  → Archive
```

---

## 2. P0 · 主体生命链（只有 4 条主链，不做几十项）

### P0-1 · SelfState 真身通电

**目标**：S1 与 S2 各归其位。

```text
S1 agent_self_model   = "我过去实际表现出来的能力证据"     → 只作 Evidence，不是"我"
S2 SelfModel          = 真正的 SelfState（参与 Thinking 的唯一真身）
```

7 域（Identity · Situation · Experience · Memory · Capability · Worldview · Cognition）共同挂到：

```text
identity_ref + timeline + version + update chain
```

**关键（修正）**：S2"通电" ≠ 新建一个对象并塞进 Prompt。正确含义 = **把 SelfState 变成真实的认知状态源** —— 以后真正参与 Thinking 的 Self 必须是 S2，S1 降级为证据底座。

**硬红线（修正 2）：S1 不得继续作为独立 SelfState 直接进入 Thinking。**

S1 允许的路径：
```text
S1 ─→ Evidence ─→ Self Claim ─→ Self Delta ─→ S2
或
S1 empirical capability evidence ─→ S2.capability_self
```

禁止路径：
```text
S1.render() ─→ DecisionBridge ─→ LLM     ← 继续冒充"我的自我描述"
context += S1.render() + S2.render()      ← 只换壳：S2(形式) + S1(真身)
```

**强制验收（T-S1，P0-1 未过则不算 PASS）**：
```text
T-S1:
Decision/LLM 所消费的 Self representation，其 authoritative source 必须是 S2 SelfState。
任何 S1 信息若出现于 Thinking，必须能够追溯为 S2 当前状态中的
Evidence / Claim / Capability projection，而不能以 S1 独立 Self representation 存在。
```

**T-S1 精确化（修正）**：验收对象不是"代码里有没有调用 `AgentSelfModel.render()`"，而是——

```text
S1 ─→ Empirical Evidence ─→ Claim / Delta ─→ S2 ─→ Thinking     ✅
S1 ─────────────────────────────────────────────→ Thinking      ✗
```

即：**不得错误理解成"所有关于自己的信息只能来自 SelfState"**（那会切断 S1 的 Evidence 路径）；而是 Self representation 的 **authoritative source** 必须是 S2 —— S1 信息出现在 Thinking 中必须是以 S2 状态内的 Evidence/Claim/Capability projection 形态。

### P0-2 · Self Growth 主链

**建立唯一合法的 Self Growth / Cognitive Growth 路径**，并禁止伪成长。

**名称修正（修正 1）**：不是"唯一合法成长路径"——而是"唯一合法 **Self Growth / Cognitive Growth** 路径"。以下状态变化是**真实的系统内部状态变化**，本身合法：

```text
Episode +1 · Knowledge +1 · Belief +1 · Skill +1 · SelfVersion +1 · Prompt +1
```

但它们**单独存在时不得宣称 Self Growth / Cognitive Growth**。禁止的就是"把这类状态变化直接冒充为成长"。唯一合法成长链：

```text
Experience → Recognition → Self Claim → Self Delta → Cognition Implication → SelfState → Thinking
```

**强制禁止**被认定为 Self Growth：

```text
Episode +1 · Knowledge +1 · Belief +1 · Skill +1 · SelfVersion +1 · Prompt +1
```

（与 FREEZE §1.4 一致 —— 否则"Skill 学会一个东西 / Knowledge 增加一条 → OCOS 又成长了"会重新污染审计。）

### P0-3 · Worldview

建立投影链：

```text
WorldModel → Evidence → Worldview Judgment → SelfState.worldview
```

Worldview 保存主体判断，而非复制 WorldModel：

```text
"我认为 X 是 Y" with confidence · provenance · temporal validity · history · overturn
```

**三分（修正，彼此不可混）**：

| 概念 | 回答 |
|---|---|
| **WorldModel** | 世界发生了什么？（entity/relation/state/event/causal） |
| **Worldview** | 我现在认为世界是什么样？（带 confidence/evidence/temporal/provenance/history） |
| **Self Delta** | 为什么我现在这样认为，而以前不是？（A→B 的 D + 依据） |

**P0 不重建 WorldModel** —— WorldModel 已有 `WorldStore update_from_observation` 唯一写路径；Worldview 只做**主体性判断投影**，引用不复制。

**依赖关系（修正，P0-3 不是 P0-4 的必要前置）**：

```text
P0-1 SelfState ─→ P0-2 Self Growth ─→ P0-4 X→D→Y（生命链最小闭环）
                        │
                        └── P0-3 Worldview（主体世界理解层补齐，不是 P0-4 的前置）
```

P0-4 最小生命链不依赖持久 Worldview；Worldview 是主体完整性核心，但**不阻塞第一次成长实验**。避免为了跑实验先被 WorldModel/Worldview 工程拖住。

### P0-4 · 第一次真正的 X→D→Y 实验（唯一 Life-chain Gate）

不做大规模 benchmark。只做**一个极小、确定性、可重复、可归因的自主任务**：

```text
同一 Goal
  → Attempt 1
  → Failure X
  → Recognition
  → Self/Cognition Delta D
  → Attempt 2
```

**Behavioral Delta 定义（修正 3，≠ 机械的 Action₂ != Action₁）**：

```text
Action₁ = shell("ls")            → 机械变化
Action₂ = shell("ls", timeout=20)
```
与
```text
Action₁ = search("A")            → Action 相同但 Cognition 变
Action₂ = search("A")（内部 Decision reasoning 已完全不同）
```

都不能仅凭 `Action₂ != Action₁` 或 `Action₂ == Action₁` 判定。准确定义：

```text
Behavioral Delta
=
Decision₂ / Action₂ / Strategy₂ 至少一个具有可验证的结构性差异
AND
Decision₂ consumes D（确实消费 Delta）
AND
该变化的 decision/action/strategy 可归因于 D（attributable to D）
```

**验收（缺一不可）**：

```text
D 被 Decision₂ 消费
  ↓
Decision₂ 与 baseline Decision₂^Z 有结构性差异
  ↓
Action₂ / Strategy₂ 与 baseline 有结构性差异
  ↓
产生 Y
  ↓
Y ≠ Z
```

**Z 的定义（反事实基线）**：Z 不只是"另一个结果"，而是——

> 如果没有 X→D，这一次在相同条件下，**最有证据支持会发生什么**。

`Y ≠ Z` 必须可解释为"为什么是 D 导致了 Y，而非原有策略本来就会产生 Y"。这样 Y≠Z 才有真正的反事实意义。

### P0-4-Z · Counterfactual Baseline Freeze（前置门，冻结）

> **Z 必须由谁产生、何时冻结、依据什么证据确定 —— 在 Attempt 2 执行之前冻结，禁止事后定义 Z。** 否则会重新引入 post-hoc attribution："结果变了 → 研究者事后解释'如果没有 D，应该还是原来的策略'"。

**冻结规则**：Attempt 2 执行**之前**，必须先冻结：

```text
Z =
在 X → D 不发生的条件下，
基于已有证据所预测的
Decision / Strategy / Action / Result
```

并记录：

```text
Z
Z.source
Z.evidence[]
Z.confidence
Z.frozen_at
```

**Z 的来源标记**：

```text
counterfactual_source = reconstructed         历史重建（基于先前认知/策略/同任务 baseline/历史 policy）
counterfactual_source = controlled_baseline    真实受控 baseline（同条件对照跑）
```

**红线**：**Attempt 2 完成以后不得重新定义 Z。** Z 一旦冻结即为一等审计对象（与 FREEZE §5 G4 一致）。

**完整实验流（P0-4 更新）**：

```text
                ┌───────────────┐
                │ Freeze Z      │
                │ before A2     │
                └───────┬───────┘
                        ↓
Goal
 ↓
Attempt 1
 ↓
Failure X
 ↓
Recognition
 ↓
Self/Cognition Delta D
 ↓
Decision₂ consumes D
 ↓
Attempt 2
 ↓
Actual Y
 ↓
Compare(Y, Z)
 ↓
Causal Attribution
```

**实验控制条件（修正 4，冻结）**——确保 attribution experiment 而非普通 retry：

```text
固定（不可变）：
  Goal · Task specification · Environment · Relevant initial state
  Available capabilities · model/provider · temperature/sampling · Prompt baseline
唯一允许变化的关键变量：
  X → Recognition → D
比较：
  Actual Attempt 2   vs   Counterfactual Z
```

若第一次是"网络失败"，第二次"网络刚好恢复"后成功，**不被视为学习**——因为变化的不是 D 而是环境变量（被固定项）。

**允许 FAIL（修正 5，硬纪律）**：

```text
P0-4 不是"一定要证明 OCOS 会学习"，而是"第一次尝试验证是否具备可归因的经验改变行为能力"。

P0-4 PASS = X → Recognition → D → Decision₂ consumes D → behavioral delta → Y ≠ Z → causal attribution complete
否则 = P0-4 FAIL
```

**禁止**：为通过实验而反复调 Prompt / 打规则补丁：

```text
没有成功 → 加几个 Prompt → 再跑 → 终于成功 → PASS   ← 禁止
```

> 明确：**实验失败首先是架构证据，而不是立即进入功能补丁。**（与 ER2/A11/A12 纪律一致。）

**P0 排除项**（不做）：世界持久化（P1）、地基债务清理（P2）、任何大规模 benchmark。

---

## 3. P1 · 稳定主体边界的支撑项（不抢 P0 的生命链）

| ID | 内容 | 目标 |
|---|---|---|
| **P1-1** | WorldModel 持久化 | 修 `WorldStore → memory only → restart → empty`；`Observation → WorldModel → Persistent → World continuity` |
| **P1-2** | Experience / Memory / Wisdom 三层收敛 | `event_memory`（经历）· `memory/hub`（记忆）· `personal_memory`（智慧）分工成立，**不因目录名字像就强行合并** |
| **P1-3** | Knowledge → Self / Worldview 边界 | 明确 `Knowledge ≠ Self Claim ≠ Worldview`；建立合法转换 `Knowledge/Evidence → 是否改变我的理解？→ Self Claim / Worldview` |
| **P1-4** | Skill 真正进入成长链 | 从能力治理（Candidate→Verified→Committed）升级为：`Experience → 稳定模式 → Skill → Capability Self → 未来 Thinking 使用 → Behavioral Delta` |

---

## 4. P2 · 架构债务清理（重要但不阻塞 P0）

```text
- capability_registry / registry / skill_registry  → 统一（含项目内 MVP 后 add）
- events/event_store vs event_memory/event_store vs storage/event_store  → 最终 ownership / source-of-truth 裁决
- working_memory 归属
- dead paths / duplicate attention / legacy cognitive packages / oversized modules
```

**P2 总红线（Protected Semantic Path，冻结）**：

> **P0 通过的主体生命链属于 Protected Semantic Path。P2 任何重构不得改变其输入、输出、证据身份、因果关系及可审计性。**

```text
event_store · attention · registry · bridge · runtime · memory
```
即使以后发现结构很丑，也不能因为"架构不优雅"而改出 `Cognitive Runtime B`，或把 `Experience → Recognition → Delta → Thinking` 拆散成另一套。

**P0 的生命链是 P2 重构之后的验收基准，而不是 P2 的重构对象。** P2 可以改 **implementation**，不得改 **semantics/evidence**。

```text
P0 semantic path
     ↓
  PROTECTED
     ↓
P2 may refactor implementation
but may not alter semantics / evidence
```

**禁止**：
```text
发现 event_store 三个     → 先重构
发现 attention 两个       → 先统一
发现 bridge 3500 行       → 先拆
发现 registry 重复        → 先重写
→ 半年后回到代码考古        ← 禁止
```
尤其：**不要为追求"优雅架构"重新制造第二条 Cognitive Runtime**（继续作为红线）。

> 判断标准：**都不应阻塞 P0 的"我能不能因为经历而改变"。** P2 在 P0/P1 之后做，或并行但不得抢 P0 资源。

---

## 5. 验收对齐（本计划与 SelfState v1 Freeze 的红线）

- 分层口径：只有主体候选模块进 Causal Attribution（FREEZE §14.2）。
- Causal Attribution = 验收证据对象，非布尔（FREEZE §14.3），禁止用"日志看到 Lesson 被注入"代替"成长发生"。
- P0-4 的 `CausalAttribution` 对象字段即 FREEZE §14.3 的证据对象；P0-4 是**第一次能产出全套该对象**的原型验证。

---

## 6. 推进开关

- **状态**：已 FREEZE。⑨ **只允许按 P0-1 → P0-2 → P0-4 推进；P0-3 可并行，不作为 P0-4 前置。**
- 依赖序：**P0-1（S2=Self，T-S1）→ P0-2（Self/Cognitive Growth 链）→ P0-4（X→D→Y Attribution，含 P0-4-Z 前置冻结）；P0-3 Worldview 并行补齐。**
- P0-4 为唯一 Life-chain Gate：PASS → Life-chain established → 可进 P1；FAIL → Architecture evidence，不进入 P1。
- **禁止**在 P0-4 PASS/FAIL 判明前：扩 P0 项目 · 扩大 913 审计 · 清 P2 · WorldModel 持久化 · 追求架构漂亮。