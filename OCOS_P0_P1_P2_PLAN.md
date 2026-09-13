# OCOS P0 / P1 / P2 计划 — 主体生命链建设（⑧）

> **性质：阶段切换宣言 —— 从"代码考古"切到"主体生命链建设"。** 只定契约方向，不进入 Implementation（⑨）。实现需本计划批准后逐项推进。
> **状态：DRAFT（待裁决）。** 输入 = `OCOS_913_SEMANTIC_MAP.md` v0.5（⑥⑦完成）+ `OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`（v1 冻结 + §14.2/14.3 升级）。
> **日期：2026-09-13（Asia/Shanghai）**
> **文档链**：FREEZE（契约）→ 913_MAP（反查）→ **本文件（⑧ P0/P1/P2）** → ⑨ Implementation（未进入）。

---

## 0. 阶段切换的唯一总问题

> 不再问"哪些模块还没完成"，只问：
>
> **"能不能让 OCOS 因为真实发生过的 X，形成可审计的 Self/Cognition Delta，并在下一次同类 Thinking 中产生可归因的 Y ≠ Z？"**

- **PASS** → OCOS 第一次从"带记忆的 Agent / 带记忆的反射系统"跨到"有经验连续性与认知连续性的持续主体"。
- **FAIL** → 即使 S2/Worldview/SelfState 都有数据库、有 version、有 Prompt 注入，也只能判为**结构完成，不是生命链完成**。

**红线**：不要做成"让整个代码库证明自己会成长"的荒谬工程 —— 只有主体候选模块进入 Causal Attribution 验收（分层口径见 FREEZE §14.2）。

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

### P0-2 · Self Delta 主链

建立**唯一合法成长路径**，并禁止伪成长。

```text
Experience → Recognition → Self Claim → Self Delta → Cognition Implication → SelfState → Thinking
```

**强制禁止**被认定为成长：

```text
Episode +1 · Knowledge +1 · Belief +1 · SelfVersion +1 · Prompt +1
```

（与 FREEZE §1.4 一致。）

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

### P0-4 · 第一次真正的 X→D→Y 实验（P0 最终裁决）

不做大规模 benchmark。只做**一个极小、确定性、可重复、可归因的自主任务**：

```text
同一 Goal
  → Attempt 1
  → Failure X
  → Recognition
  → Self/Cognition Delta D
  → Attempt 2
```

**验收（缺一不可）**：

```text
Action₂ ≠ Action₁
Decision₂ 确实消费 D
Y ≠ Z（且能解释为什么是 D 导致了 Y，而非原有策略本来就会产生 Y）
```

而后可回答：

> "因为第一次失败，所以第二次的 OCOS 不再是第一次失败前的那个 OCOS。"

这是 OCOS"活起来"的第一条真正证据。

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

> 判断标准：**都不应阻塞 P0 的"我能不能因为经历而改变"。** P2 在 P0/P1 之后做，或并行但不得抢 P0 资源。

---

## 5. 验收对齐（本计划与 SelfState v1 Freeze 的红线）

- 分层口径：只有主体候选模块进 Causal Attribution（FREEZE §14.2）。
- Causal Attribution = 验收证据对象，非布尔（FREEZE §14.3），禁止用"日志看到 Lesson 被注入"代替"成长发生"。
- P0-4 的 `CausalAttribution` 对象字段即 FREEZE §14.3 的证据对象；P0-4 是**第一次能产出全套该对象**的原型验证。

---

## 6. 推进开关

- 本文件为 **DRAFT**，需要你批准后才能进入 ⑨ 的逐项实现。
- 批准后建议执行顺序：**先 P0-1 → P0-2 → P0-3（三者共同支撑 P0-4）→ 跑 P0-4 实验 → 用 P0-4 结果裁决是否进入 P1**。
- P0-4 为唯一"生命链完成"闸门。