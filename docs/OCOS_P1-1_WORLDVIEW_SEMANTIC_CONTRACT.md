# OCOS P1-1 Worldview — Semantic Contract（语义冻结）

> 状态：**P1-1 DESIGN = GO；Implementation = 继续 NOT AUTHORIZED。**
> 本文件是 **Worldview 语义冻结契约**，不是代码、不是 schema、不是实现。
> 冻结对象：**"什么才算 OCOS 自己的世界观"**。在契约 + Human Gate 通过前，不得修改
> `SelfModel` / schema / prompt / Converse / DecisionBridge / 任何生产认知语义。
>
> 承接：`docs/OCOS_P1-1_WORLDVIEW_READONLY_AUDIT.md`（NOT-IMPLEMENTED，语义角色缺失）。
> 目的：把 Worldview 定义到足够严格，使 `Belief / Knowledge / WorldModel / Prompt Context` **无法冒充**。

---

## 1. Worldview 定义

**正式定义（W-DEF）**：

> **Worldview 是 OCOS 自己拥有的、由真实经历经 Recognition 形成、可追溯（evidence → claim → delta）的、对"世界/领域如何运作 + 我应如何理解与判断"的高层主体性理解框架（interpretive stance）。**

三要素（缺一不成立）：

```text
owner    = OCOS Self（写入 SelfState，经 SelfProjectionAccessor 读取；不是外部模块直连）
genesis  = 真实经历（每条判断可审计到至少一条 Experience + Evidence）
function = 作为后续认知的解读框架（影响后续 Thinking/Decision，而非仅陈述）
```

**五条必要属性**（每一条都必须满足才构成 Worldview，用于判定"是不是 Worldview"）：

| # | 属性 | 含义 |
| --- | --- | --- |
| P1 | 主体性 self-owned | 属于 OCOS 自己，非外部模型结论、非外部世界数据 |
| P2 | 经历归因 experience-attributed | 可追溯到真实经历 + Evidence，非凭空/模板 |
| P3 | 框架性 framework, not proposition | 是"如何理解这类事情"的组织化立场，不是孤立命题 |
| P4 | 可变更 mutable via delta | W0 → X → W1，W1 ≠ W0，变更带 old/new/evidence |
| P5 | 认知影响 cognitive influence | 进入后续 Thinking/Decision，可产生可归因行为差异（Y ≠ Z） |

**判定规则**：任一属性不成立 ⇒ 该项不是 Worldview，只能是其下位/伪载体。

---

## 2. Worldview 非定义（伪实现黑名单）

以下每一项**都不是** Worldview，禁止以这些名义宣称 Worldview 已形成：

| # | 排除项 | 反例 / 理由 |
| --- | --- | --- |
| N1 | Knowledge 的别名 | "世界是什么"是事实，可外部注入、可验证；Worldview 不可被新事实直接替换，只能被经历修正 |
| N2 | Belief 的聚合改名 | belief 是局部命题置信；给 belief 换名 ≠ 形成理解框架 |
| N3 | WorldStore 数据 | 外部世界实体/关系/因果是地图，不是持图者的理解方式 |
| N4 | Prompt 自述文本 | 让 LLM"声称自己认为世界如何"只是文本，无 Self 载体与经历归因 |
| N5 | LLM 输出的一句话总结 | 无 claim/delta/provenance/commit 链，不算认知状态 |
| N6 | version+1 / text diff | 无结构化 old/new 差分与行为验证，不算 delta |
| N7 | reflection 的任意自省 | 无经历归因的反思输出不算；必须形成 judgment 且可追溯 |
| N8 | 静态宪法/模板文本 | 非经历产生、不可 delta，不是 Worldview |

---

## 3. Knowledge / Belief / WorldModel / Worldview 边界矩阵

| 维度 | Knowledge | Belief | WorldModel | **Worldview** |
| --- | --- | --- | --- | --- |
| 回答的问题 | 世界是什么（事实） | 命题 X 是否成立的置信 | 外部世界如何结构化运作 | **我如何理解世界/领域，并据此如何判断** |
| owner | 可外部注入 | OCOS | OCOS 维护的外部地图 | **OCOS 自己（主体）** |
| 真值性 | 可验证真伪 | 概率化置信 | 可观测校准 | **不可简单验证——是立场/框架** |
| 变更驱动 | 新事实/证据 | 证据更新 | 观测更新 | **经历 X + Recognition** |
| 载体 | knowledge_boundary / knowledge | belief 表 | world_model 独立模块 | **SelfState.worldview（待建）** |
| 对认知的影响 | 提供事实素材 | 命题置信 | 提供情境 | **改变解读框架 → 影响决策** |

**防冒充规则**：
- **R-K**：Knowledge 只进 `knowledge_boundary`/knowledge 表，**不得直接进 worldview**。
- **R-B**：belief 可以是 Worldview 的素材/表达之一；**单个 belief 或 belief 聚合 ≠ Worldview**。
- **R-W**：WorldStore 实体/因果 ≠ Worldview；**必须经 Recognition/Judgment 形成自归判断**后才可入 worldview。

红线重申（延续审计 §16）：WorldModel ≠ Worldview；Belief ≠ Worldview；Prompt Context ≠ Thinking Consumption。

---

## 4. Worldview Claim Schema（语义层）

> 语义结构，**不是实现**。定义"一条世界判断长什么样"，供后续 G1 形状定稿时映射到既有
> `SelfUpdateContract` provenance 设施（[self_types.py:79-90](file:///workspace/ocos/self/self_types.py#L79)）。

```text
wv_claim_id         # 唯一身份（复用 claim 语义）
worldview_domain    # 领域，如 relationship / work / survival / mystery / power / 自定义领域
judgment            # 判断语句：表达立场/理解方式（不是事实陈述）
stance_type         # 立场类型：interpretive(如何理解) / normative(应如何) / epistemic(知道边界)
frame               # 框架描述：对"这类事情"的组织化理解方式
evidence_ids[]      # 真实经历 Evidence 锚点（非空，必须）
source              # SelfUpdateSource 语义（复用 REFLECTION / RUNTIME_OBSERVATION，见 §12）
confidence          # 判断置信 [0,1]
created_at / tick   # 时间锚
```

**示范（区分三态）**：
- Knowledge：`failed command exit=127`（事实）
- Belief：`exit=127 大概率是 command not found`（命题置信）
- Worldview：经历多次"环境与预期不符"后形成——
  `judgment="在不确定环境中，我先验证而非信任"`，`frame="环境不可靠时，以证据为准"`（**主体判断框架**）

---

## 5. Worldview Delta Schema（语义层）

**W-DELTA 必须记录的结构**（复用 `SelfDelta` old/new 语义，[self_evidence.py:118-131](file:///workspace/ocos/self/self_evidence.py#L118)）：

```text
wv_delta_id
old_value             # 结构化 frame/stance 快照（非字符串）
new_value             # 结构化 frame/stance 快照
trigger_experience_id # X（真实经历）
recognition_type      # conflict(冲突) / confirm(强化) / novel-pattern(新范式) / reframe(重构)
evidence_ids[]
reason
confidence_after
tick / timestamp
continuity            # 与旧值关系：衍生 / 修订 / 替换
```

**不等性判据（W1 ≠ W0 的证明要求）**：
1. **结构差分**：新增/删除/修改的 judgment 条目（frame/stance 级，非文本 diff）；
2. **行为验证**：后续 Thinking/Decision 在 W1 下产生 Y，对照 Z 产生差异（§7/§10）；
3. **禁止**：仅 `version+1` / 仅 prompt 文本变化 / 仅文本 diff 冒充 delta。

---

## 6. Experience → Recognition → Worldview Delta 触发条件

**五条件全部满足才允许触发**：

```text
C1  X 是真实经历（episode/observation，有 evidence）      ✓ 必须
C2  X 与当前 worldview 相关领域存在 conflict / confirm / novel-pattern
C3  Recognition 产出明确的 judgment 变化（不是知识新增）
C4  形成 claim + delta（old/new/evidence/reason 全量）
C5  通过 govern commit（复用既有治理门与 update_history）
```

**禁止**：
- 无经历归因的机械写入；
- 为"让字段有东西可写"而把 reflection 或 WorldStore 结果塞进 worldview（§2 N7/N3）。

---

## 7. W0 / X / Recognition / W1 / Y / Z 关系

**符号系统（对齐 P0-4 因果链）**：

```text
W0           X 之前 committed worldview
X           真实经历（evidence）
R           Recognition 结果（conflict/confirm/novel/reframe）
W1          经历 X 后 committed worldview，W1 ≠ W0（结构差分）
Z           反事实基线：若没有 X，OCOS 将基于 W0 怎么想/怎么做
Decision₂   W1 下的决策
Y           Decision₂ 的行为产物
ZDecision   无 X 条件下（W0）的对照决策
```

**目标链**：

```text
W0 --(X, R)--> W1 --Decision₂--> Y        （实验组）
W0 --(无 X)--> ZDecision --> ZY            （对照组）
验证：W1≠W0（§5） 且  Y ≠ Z               （行为级）
```

**关键问题（必须能回答）**："如果没有这次经历 X，OCOS 原本会怎么想？"——由 Z 冻结回答，与 P0-4 同构。

---

## 8. Thinking Consumption Contract

**读取路径（唯一）**：Worldview 必须经 `SelfProjectionAccessor` 读取（与既有 5 组件同路径，
[agent_runtime.py:548-581](file:///workspace/ocos/agent/agent_runtime.py#L548)），**禁止任何模块直读**。

**消费点**：Thinking/Decision 实际读取 worldview 组件时，形成 consumption manifest
（复用 `component_consumption()` 语义，[self_state.py:485](file:///workspace/ocos/self/self_state.py#L485)）。

**证据分级（由低到高，必须达标的层级明确冻结）**：

| 层级 | 证据形态 | 是否算"进入 Thinking" |
| --- | --- | --- |
| CONTEXT-ONLY | worldview 出现在 prompt/context | ❌ 不算 |
| DECISION CONSUMPTION | 决策读取点形成 consumption manifest | ⚠️ 中间证据 |
| BEHAVIORAL | 行为差异 Y ≠ Z | ✅ 才算成立 |
| CAUSAL | P0-4 式 X→D→Y 因果链 + Z 对照 | ✅ 最终目标 |

**冻结**：不得仅凭"prompt 里出现 worldview"宣布 Thinking 已消费（延续审计红线 10/12）。

---

## 9. Evidence / Provenance / Confidence / Temporal / Continuity

| 维度 | 要求 |
| --- | --- |
| Evidence | 每条 judgment 必须带 evidence_ids（真实经历） |
| Provenance | 复用 `SelfUpdateContract`（source/reason/claim_id/evidence_ids，[self_types.py:79-90](file:///workspace/ocos/self/self_types.py#L79)） |
| Confidence | 复用 `self_confidence` / `confidence_impact` 机制 |
| Temporal | `created_at` / `tick`；delta 时间线可回溯 |
| Continuity | delta 链 old→new 可串联；committed 版本复用 S2 version |
| 禁止 | 用 DB 聚合（如 WorldStore counts）冒充 Worldview Provenance（审计红线 11） |

---

## 10. Worldview X→D→Y 实验规范（P1-1D）

对齐 P0-4 的受控 harness（生产接线受 P0-4B B1–B5 冻结，**实验先在受控 harness 做**）：

```text
Step 0  环境披露（provider 状态如实登记）
Step 1  构造真实 X（真实经历 + evidence）
Step 2  Recognition → Worldview Claim C_w → Worldview Delta D_w
Step 3  govern commit → S2.worldview = W1；在 A2 前冻结 Z（无 X 基线）
Step 4  Decision₂(W1) vs ZDecision(W0) → 结构差异（W1≠W0 证明）
Step 5  Action₂ → Y；断言 Y ≠ Z（行为差异）
Step 6  fused trace（thinking/decision 同链记录）
```

**排除混杂（与 P0-4 相同）**：E1 环境、E2 sampling、E3 能力混杂、E4 prompt 变化。
**禁止**：为 P1-1D 修改生产控制流（延续 P0-4B 红线，见 §13）。

---

## 11. Acceptance / Failure Gate

**Acceptance（全部满足才 PASS）**：
- A1 存在自归 worldview 组件（G1 落位）
- A2 至少一条经历归因的 claim + delta（带 evidence）
- A3 W1 ≠ W0 的结构性证明（非文本 diff）
- A4 Thinking 消费至少达到 DECISION CONSUMPTION 级；BEHAVIORAL（Y≠Z）为目标
- A5 Z 对照成立（反事实有效）

**Failure（任一触发即 FAIL）**：
- F1 worldview 被 knowledge/belief/WorldStore 数据机械填充
- F2 无经历归因（N1–N8 任一成立）
- F3 仅 version+1 / 仅 prompt 变化，无结构差分
- F4 仅 CONTEXT-ONLY 即宣布消费成立
- F5 生产接线绕过 P0-4B 冻结（B1–B5 未解即动 Converse）

---

## 12. G1 是否必要、G1 最小形状

**判定：G1 必要，但非充分。** 语义需要一个物理座位才能被 commit/provenance/消费；
但"加字段 ≠ Worldview 完成"（§17.4 审计裁决）。

**G1 最小形状（语义级，不实现）**：

```text
1. SelfModel 第 6 组件 worldview（组件类型按 §4/§5 语义定义）
2. valid_components 白名单加入（[self_types.py:337-340](file:///workspace/ocos/self/self_types.py#L337)）
3. canonical serialization + 类型注册表（[self_state.py](file:///workspace/ocos/self/self_state.py) 既有机制）
4. accessor render/brief 投影（新增 worldview 输出槽）
5. SelfUpdateSource 归类：优先复用 REFLECTION / RUNTIME_OBSERVATION；
   仅当语义无法归类时才需新增枚举成员（属 decision-semantics 变更，单独立项）
6. commit 复用既有 SelfEvidencePipeline → govern commit 全链
```

**硬性前提**：G1 形状必须在本契约 §1–§10 冻结后才定稿；**不得先加字段再编语义**。

---

## 13. 明确禁止的实现路径

1. 只加字段、不建 judgment→claim→delta→commit 链
2. belief 改名 worldview
3. WorldStore 数据直写 worldview
4. prompt 塞一段"世界观"文本即宣布形成
5. LLM 输出总结直接落 worldview
6. 为 P1-1D 修改生产控制流（延续 P0-4B 冻结）
7. 新增第二套 self / 新 runtime / 新 authority
8. 不经本契约 + Human Gate 即实现

---

## 14. Human Gate

- 本文件即 **P1-1 DESIGN 产出 = Semantic Contract**，冻结 Worldview 语义。
- 在 **Semantic Contract + Human Gate 通过** 前：**不得修改** `SelfModel` / schema / prompt /
  Converse / DecisionBridge / 任何生产认知语义。
- Gate 裁决选项：
  - **CONTRACT ACCEPTED** → 授权进入 G1 形状设计与实现方案（仅授权设计，非实现放行）；
  - **CONTRACT AMENDED** → 返回修订语义，不进入任何设计/实现；
  - **REJECTED** → P1-1 停更，语义保持 NOT-IMPLEMENTED。

---

*本文件为语义冻结产物，非代码。等待 Human Gate 裁决。*
