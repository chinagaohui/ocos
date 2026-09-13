# OCOS SelfState Schema / Semantics Audit

> **目的：把 SelfState 的语义和边界彻底定下来 —— 不是查代码有没有这些字段，而是逐字段回答"它到底是什么、凭什么这么判断、怎么变化"。**
> **范围：纯语义定义，不写代码、不查 bug。**
> **状态：v0.1 草案，供评审。**
> **日期：2026-09-13（Asia/Shanghai）**
> **前置：`OCOS_COGNITIVE_IDENTITY_AUDIT.md` v0.2（已冻结 §8 决策）。**

---

## 0. 一句话立场

SelfState 不是"一堆域的数据"，而是一个**能回答三个横向问题**的自我：

> 为什么(? Evidence) · 多确定(? Confidence) · 什么从 A 变到 B(? Continuity)

当这五横、七纵（5 横向维度 × 7 子域）都各自有答案时，它才真正像一个"自我"。

---

## 1. 七个纵轴子域的语义（逐字段）

每个子域都必须同时回答三件事：**本域要回答的问题 · 什么能进入本域 · 什么东西永远不属于本域（边界）**。

### 1.1 Identity
- **回答**：我是谁？什么东西永远不能被经验改变？
- **进入**：identity_ref、born_at、type、constitution 引用、与主人的关系锚点。
- **边界（不可变）**：id / 诞生时间 / 宪法哈希。**身份可以稳定。**
- **证据**：无 —— 它是锚，不是判断。

### 1.2 Situation
- **回答**：我现在在哪里？当前处于什么运行环境/生命周期/关系状态？
- **进入**：当前机器与运行环境、生命周期阶段、与主人/助手的关系状态。**当前状态。**
- **边界**：不是"历史经历"，只是"此刻的状态快照"。
- **证据**：运行时观测（daemon / vitals / 环境探针）。

### 1.3 Memory（memory_self）
- **回答**：哪些记忆属于"我的过去"？
- **进入**：与自我相关、可被"我"引用的长期记忆索引。
- **边界**：它是"我的过去"的**索引视图**，不是原始存储本体；不入库不入脑。
- **证据**：指向底层 Memory 条目的引用。

### 1.4 Experience（experience_self）
- **回答**：哪些事情**真正改变过**我？
- **进入**：带因果解释的 episode 链——**做了 X → 结果如何 → 我因此认识/改变了什么**。
- **边界**：只收"产生过自我/认知 delta 的事件"；没改变我的、纯流水账不入此域。
- **证据**：episode 级证据 + 因果链接（+ 反事实 Z 的留痕）。

### 1.5 Capability（capability_self）
- **回答**：我认为自己能做什么 / 不能做什么？证据是什么？
- **进入**：能力声名 + 能力局限 + 失败模式，每条都带"为什么"。
- **边界（关键）**：这是 S2 的**认识**；S1（实测成功率）只是它的一类**证据来源**。不得把 S1 当作"我"。
- **证据**：S1 实测 / Experience / Registry / Reflection。

### 1.6 Worldview
- **回答**：我认为世界是什么样？证据是什么？
- **进入**：对世界的判断库（世界模型），可被证据推翻。
- **边界**：与自我域分域（S40-03）；"我"只引用不复制整个世界。
- **证据**：World / Knowledge / 经历互证。

### 1.7 Cognition（cognition_self）
- **回答**：我现在相信什么、正在想什么？为什么？以及**下一次该怎么想**。
- **进入**：当前认知状态、当前专注、策略意图。
- **边界**：持续变化，是"下一时刻"的输入，不是归档。
- **证据**：运行时认知观测。

---

## 2. 五个横向维度的语义（贯穿所有纵轴）

| 横向维度 | 回答的问题 | 说明 |
|---|---|---|
| **Evidence** | 我为什么这么认为？ | 每条自我认识必须挂证据引用；无证据 → 标记为"猜测"而非"确定"。 |
| **Confidence** | 我有多确定？ | 全局 self_confidence + 每条判断的置信度；诚实标注未知。 |
| **Provenance** | 这个认识是从哪来的？ | 来源分类（Experience / Registry / Reflection / RuntimeObserv / External…），排外部直接注入。 |
| **Temporal** | 它是什么时候成立的？ | 每个认识带时间锚，支持跨期对比。 |
| **Continuity** | 我什么时候从 A 变到 B？为什么？ | **SelfState 最核心属性**。必须能回答"v371 为何 ≠ v370"。 |

**Continuity 的唯一判定标准（冻结自审计 §8.2）**：
> **Version 371 的"我"，为什么和 Version 370 的"我"不一样？**
> 若只有 `version +1 / count +1`、没有可解释的认知 delta，则此 version 无认知意义。

---

## 3. 子域 × 横向 = SelfState 的最终形态

```text
SelfState
├── Identity     { 锚，无 E/C/P/T/C }
├── Situation    { Evidence, Confidence, Provenance, Temporal }
├── Memory       { 引用视图, Provenance, Temporal }
├── Experience   { Evidence, Confidence, Provenance, Temporal, Continuity }
├── Capability   { Evidence, Confidence, Provenance, Temporal, Continuity }   ← S1 是它的证据，不是它
├── Worldview    { Evidence, Confidence, Provenance, Temporal, Continuity }   ← 可被证据推翻
└── Cognition    { Evidence, Confidence, Provenance, Temporal, Continuity }   ← 持续变化
```

> Identity 是唯二没有 E/C/P/T/C 的本体（其余纵轴宣讲 Evidence+Continuity 两条最重的横轴）。这是它与"认识"的根本区别。

---

## 4. 四个层的变更权限（修正 v0.1 层级错误）

```text
Identity Anchor   不可随经验改变         ← 稳定（冻结）
Core Self Boundary 稳定                  ← 稳定（冻结）
SelfModel          可以成长               ← 经受控来源更新
Beliefs/Worldview  可以被证据推翻          ← 证据驱动更新（认识必须可改变）
Cognitive State    持续变化               ← 实时
```

**核心原则**：身份可以稳定，认识必须可以改变。两条必须同时成立，否则"不能改变认识却要通过经历成长"的悖论成立。

---

## 5. 一条必须连通的链（冻结自审计 §8.1）

```text
我能用 shell          ← S1 证据
我为什么常在 shell 失败  ← Experience / Failure
我现在对自己 shell 能力的认识 ← SelfModel
因此下一次遇到 shell 问题 采取什么策略 ← Cognition
```

这四层必须从下到上被打通，且认知在**下一次思考**中被携带。断一环，"我"就只是堆字段。

---

## 6. 语义待决问题（下一轮评审要回答）

1. **Continuity** 的数据载体：用 `delta log`（每次变化记录 A→B 因）还是 `version snapshot`（每版本全量）？两者可并存，但必须至少一种能回答"为什么变"。
2. **反事实 Z** 在哪记：Z 是历史假设，存于 Experience 的因果链留痕，还是重建生成？需定载体。
3. **Worldview 与现 WorldStore / Knowledge 的关系**：合并、投影，还是仅索引？"我"不复制世界是铁律，但读取口径未定。
4. **Situation 的"关系"**：是否纳入与主人/助手的关系状态，还是只留运行环境？语义边界未定。

---

## 7. 落地顺序（本期到此为止，不写码）

1. ✅ 本文件（SelfState 语义定义）→ 交评审。
2. ⬜ 你与侧评审定 §6 待决问题后，冻结 SelfState Schema v1。
3. ⬜ 拿完整源码做 913 文件反查（属于"我 / 工具 / 遗留"→ 目标映射 → 保留/重构/合并/删除）。
4. ⬜ 据此形成真正的 P0/P1/P2（不是从"现有代码有什么"出发，而是从"OCOS 该成为谁"反推代码去留）。

---

## 附：本阶段判断

**从做更强认知 Runtime，切换到做持续存在的"我"。** Fast视图：
Runtime=身体 · Memory=过去 · Perception=接触世界的方式 · Brain=当前思考 · SelfModel=对自己的认识 · WorldModel=对世界的认识 · Learning=改变自己的机制。

**现在不修代码。** 语义定清，再反查代码。