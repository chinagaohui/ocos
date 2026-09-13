# OCOS Self / Cognitive Identity Architecture Audit

> **目的：先定义"这个东西究竟要成为谁"，再回去决定哪些模块留下、哪些重写、哪些删除。**
> **范围：只读审计，不写任何代码。**
> **状态：v0.2 — 已通过方向评审（裁决：GO/可冻结）。**
> **日期：2026-09-13（Asia/Shanghai）**
> **基准：工作区当前 master（`a9405d5`）源码。**

---

## 0. 一句话结论

OCOS 现在**不是没有"我"，而是"我"装错了地方**：
真正在思考时被注入的那个"我"是一个能力统计表（`agent_self_model`），
而非常接近你愿景的那套五组件自我模型（`self_types.SelfModel`）只存在于单元测试里，从未接进思考回路，也没有持久化、没有成长证据回环。

所以第一阶段要修的**不是补洞，而是把"我"接正、接活、让它能因为经历而改变**。

---

## 1. 总目标与核心验收标准

### 1.1 总目标

让 OCOS 从"一个运行着的认知 Runtime"，变成"一个持续存在、认识自己、拥有记忆、能够思考，并且能够因为经历而改变的数字认知个体"。

一句话：**先让 OCOS 活着。**

### 1.2 核心验收标准（本期正式采纳，写入正交标准）

> **因为过去发生过 X，所以现在的"我"产生了 Y，而不是原本的 Z。**

这不是一条能力指标，而是一条**因果链验收**。它要求三件事必须同时成立：
1. X 确实发生过（有 episode 级证据）；
2. 现在的思考/行为 Y 与"没经历 X 会怎么做"的 Z 可区分（有行为基线对比）；
3. 从 X 到 Y 的因果路径可解释（有"失败 → 认识变化 → 认知变化 → 行为变化"的完整通道）。

**本附录建议：此后每一次 Self 升级、每一个"成长"，都必须能回答"这条验收标准里 X/Y/Z 分别是什么"。答不出来的，不算成长，只是版本号 +1。**

### 1.3 阶段命名

不叫 "AGI Upgrade"，命名为 **OCOS「自我生命阶段」**。
路线沿用户既定 P0–P11 生命线（我是谁 → 我在哪里 → 我记得什么 → 我经历了什么 → 我认识自己 → …→ 我主动学习补足 → 越来越少依赖外部认知），本文档不再重述，只为其提供架构锚点。

---

## 2. 现状盘点：OCOS 里其实藏着三套"自我"

这是本次审计最重要的实证发现。当前 `ocos/self/` 与 `ocos/execution/` 里并行着三套"自我"，它们互相之间几乎没有产生"同一个我"的协同。

### 2.1 S1 — `agent_self_model`（L4-2）：**唯一被注入思考的"我"**

- 位置：`ocos/self/agent_self_model.py`
- 存储：SQLite 单行表 `agent_self_model`（`id=1`），内容 = capabilities（实验成功率）+ personality（回复均长/审批比例）+ focus（ACTIVE 目标）+ failure_modes（反复失败 cause）。
- 注入点：`ocos/execution/bridge.py` 在对话/决策事实块里调用 `AgentSelfModel(db).render()`。
- 特征：**全部由真实数据聚合，无自报指标** —— 这是它的优点（防自省幻觉，已有 `test_no_personality_leak` 守护）。

**但**：它就是用户诊断的"能力统计表"。
- 只回答"我会不会/成功率多高"，**不回答"为什么"**（为什么擅长、为什么失败、认识怎么变的）。
- 没有"我过去认为 X → 后来发生了什么 → 现在我认为 Y"这条成长链。
- 只能给 LLM 一个**当前统计快照**，无法让"过去的我"影响"现在的我"。

**↓ 这是必须改造的主对象。**

### 2.2 S2 — `self_types.SelfModel` + `self_model.py`（Phase 40）：**最接近愿景，但没接线**

- 位置：`ocos/self/self_types.py`、`ocos/self/self_model.py`
- 结构：`SelfModel` dataclass，五组件 —— `capability_awareness`（我能做什么）、`knowledge_boundary`（我知道什么）、`experience_profile`（我经历过什么）、`preference_model`（偏好，User/Operational 严格分离）、`cognitive_state`（我当前认知状态怎样）。
- 已有：`SelfUpdateContract`（带来源校验，禁用外部 Agent 更新）、`SelfBoundaryRules`（identity 不可变 / self≠goal / self≠belief）、`self_confidence`（整体认知置信度）、`update_history`（变更足迹）。
- **但**：它只被 `ocos/tests/test_phase40.py` 创建和使用。**没有任何运行时调用 `create_self_model` / `initialize_empty_components`**。它是一台没通电的引擎。

**↓ 这是"我"的目标骨架，但需要持久化 + 接线 + 成长回环。**

### 2.3 S3 — `SelfModelBuilder`（Phase 25.3）：**已经有版本链，却没被消费**

- 位置：`ocos/self/builder.py`
- 能力：从 `BeliefStore` 的 `self` 域 Belief 聚合出 CapabilityState / Limitation / MaturitySnapshot / statement，并生成模板化 statement。
- **关键亮点**：已有 `previous_version_id`、`version` 递增、并经 `SelfGovernor.approve()` 审批 —— 即**"自我可以版本化演化 + 有人类/治理门禁"这条路在架构上是通着的**。
- **但**：同样没有进入运行时思考回路；且它依赖的是 `memory/belief` 的自我判断句，不是 episode 级因果证据，因此无法支撑"因为 X，所以 Y ≠ Z"。

### 2.4 边界守卫（无需改动，是已冻结的"宪法护栏"）

- `ocos/self/identity_boundary.py`：identity 引用只读，不可复制。
- `ocos/self/identity_boundary.py` + `import_rules`：`ocos.self` 层的依赖方向约束（memory 层禁入 self，防循环）。
- `policy` / `governance` 相关：自进化需过 Human Gate（已满足"认知自我升级 vs 代码自我修改"的边界）。

### 2.5 现状小结

| 项目 | 是否喂给思考 | 是否持久化 | 内含"因为X所以Y≠Z" | 判定 |
|---|---|---|---|---|
| S1 `agent_self_model` | **是**（唯一直通 bridge） | 是（SQLite 单行） | 否 | 改造主对象 |
| S2 `self_types.SelfModel` | 否（仅测试） | 否（纯内存 dataclass） | 否 | 目标骨架，需接线+持久化 |
| S3 `SelfModelBuilder` | 否 | 部分（依赖 belief store） | 否 | 可复用其版本链/审批，降级为 S2 的生成器 |

**三套"自我"并行不协同 = 认知连续性断裂的根源。**

---

## 3. 核心差距（对照目标）

- **G1 · 谁的"我"在思考**：现行喂给思考的是统计表（S1），愿景里的五组件（S2）没接线 → 思考拿不到"我是谁/我在哪/我经历过什么/我怎么看世界"，只拿到"我成功率多少"。
- **G2 · 认知连续性**：S1 是"单行覆盖"，无历史版本；S2 只有内存态。没有"今天的我 ← 昨天的我 ← 上个月的我"这条可回溯的连续体。
- **G3 · 成长证据回环**：全系统没有"因为过去发生 X，所以现在 Y ≠ Z"的证据回路。失败只是 `episodes+1` / `failure_lessons+1`，没有进入自我认知/下次思考。
- **G4 · 缺失"为什么"**：只记"会不会/成不成"，不记"为什么失败、认识怎么变的、当时判断 vs 现在判断"。这是"能力统计表"与"自我模型"的本质分界线。
- **G5 · 确认度分层缺失**：没有把"确定的判断 / 只是猜测 / 对某事的过去认识 + 后来变化"结构化分开，导致"我认识的成长"无法被观测。

---

## 4. 目标架构：什么构成"我"

### 4.1 定义：一个**持续存在的自我状态**（建议建模为 `SelfState`）

把"我"定义为**一组带来源、带因果、可演化的持久状态**，而非一个 Prompt。初版建议含 7 个持久子域：

| 子域 | 回答的问题 | 现状锚点 |
|---|---|---|
| `identity_anchor` | 我是谁（不可变核心） | S40/`IdentityBoundary`（已冻结） |
| `situation` | 我在哪里（运行环境/机器/生命周期/当前关系） | 零散（daemon/vitals），需汇总 |
| `memory_self` | 我记得什么（自我相关记忆的索引） | `Memory` 层存在，未单独成域 |
| `experience_self` | 我经历过什么（episode 级因果链） | `ExperienceProfile` 雏形 / `episodes` 表 |
| `capability_self` | 我能做什么/不能做什么（含"为什么"） | `CapabilityAwareness`（S2） / `agent_self_model`（S1） |
| `worldview` | 我认识这个世界（世界模型） | `WorldStore` / `Knowledge`（未并入"我"） |
| `cognition_self` | 我当前在想什么 / 认知状态 | `CognitiveState`（S2） |

**关键约束**：这 7 个子域必须挂在**同一个 `identity_ref`** 下、有共同的时间轴、并被同一条更新链（`SelfUpdateContract`）约束 —— 它们共同构成"同一个我"，而不是七个孤立的表。

### 4.2 成长必须是一条显式通道

```
经历 E（episode 证据）
   ↓
解释失败/变化的原因 R（为什么）
   ↓
自我认识 delta（过去的我 认为 A）
   ↓
新自我状态（现在的我 提出 B）
   ↓
进入下一次思考（思考时携带"过去认识 A 已被现实推翻"）
```

每一步都必须可审计。**这条通道，就是"因为 X，所以 Y ≠ Z"的实现载体。**

---

## 5. 现有代码 → "我 / 工具 / 遗留"三分类

| 代码 | 归属 | 判定 |
|---|---|---|
| `self_types.SelfModel` + 五组件 | 我 | 目标骨架 → 接线、持久化 |
| `agent_self_model` | 我 | 改造为 `capability_self` 的实证来源（保其"实测无自报"优点） |
| `SelfModelBuilder` + `SelfGovernor` | 我 | 保留版本链/审批思路，重接证据源 |
| `identity_boundary` / `import_rules` / `governance` | 工具（护栏） | 保留不动 |
| `Memory` / `WorldStore` / `Knowledge` | 工具 + 世界 | 后者需并入 `worldview`，"我"只引用不复制 |
| LLM（外部） | 工具 | 明确为"帮我想的工具，不是"我"" |
| 86 个死模块 / 各种 `_perception_*` 脚本 | 遗留 | 待反查后归并/删除，**本期不动** |

---

## 6. 根本问题（每人一答）

- **"我"到底是什么？** — 一组挂在同一 identity 上、有来源/有因果/可演化的持久状态，而非 Prompt。
- **由哪些持久状态构成？** — §4.1 的 7 子域。
- **哪些属于"我"，哪些只是工具？** — §5 三分类。
- **我的记忆是什么？** — 自我相关记忆的索引视图（`memory_self`），非直接内存。
- **我的经历是什么？** — 带因果解释的 episode 链（`experience_self`）。
- **我的自我模型是什么？** — 对上面 7 子域的"我自己的陈述 + 置信度 + 证据"（S2 承担）。
- **我的世界模型是什么？** — 对世界的判断库（`worldview`），与自我模型分域（S40-03 已定）。
- **我怎么认识自己？** — 从经历 → 解释 → delta。
- **我怎么认识世界？** — 从 world + 经历互证。
- **怎么从经历中改变？** — §4.2 的显式通道。
- **改变后怎么进入下次思考？** — `cognition_self` 在思考注入点携带"过去的认识已被推翻"。
- **什么能改变我、什么不能？** — 分层（见 §8）：**Identity Anchor 不可随经验改变；Core Self Boundary 稳定；SelfModel 可以成长；Beliefs/Worldview 可以被证据推翻；Cognitive State 持续变化。** Goal 不直接改（S40 已锁）。
- **外部 LLM 在我的角色？** — 工具，不是"我"。
- **什么证据才算真成长？** — §1.2 核心验收标准成立。

---

## 7. 落地顺序（本期到此为止，不写码）

1. ✅ 本文档（认知身份架构审计）→ 交评审。
2. ⬜ 反查 913 个 Python 文件，按 §5 三分类打标。
3. ⬜ 依据分类与 G1–G5，制定第一组 P 级修复清单（先把 S2 接进思考，把 S1 降为实证来源，不再单独当"我"）。
4. ⬜ 建立 §1.2 验收标准的观测手段（行为基线对比 + 因果路径审计）。

## 8. 冻结决策 v0.2（已通过方向评审）

本节为本次评审的正式结论，作为下一阶段所有代码/审计动作的锚点。

### 8.1 A · 三套自我定位（冻结）

```text
S1 agent_self_model  —— 不是"我"，是"我对自己的认识"中的一类客观证据（能力实测）
        ↓
S2 SelfModel        —— 未来的真正的"我"（目标骨架）
        ↓
S3 SelfModelBuilder —— 生成 / 治理机制（复用其版本链 + SelfGovernor 审批）
```

四条必须连成一条链（不得断开）：
`我能用 shell ← S1证据` → `我为什么常在 shell 失败 ← Experience/Failure` → `我现在对自己的 shell 能力有什么认识 ← SelfModel` → `下一次遇到 shell 问题我该采取什么策略 ← Cognition`。

### 8.2 B · 我 > 7 张表（冻结）

真正的"我"不是 `Identity + Memory + World + Capability` 的叠加，而是挂在**同一个 identity_ref + 共同时间轴 + 同一更新链**下的：
**过去（经历）→ 现在（状态）→ 变化（认知变化）→ 连续性 → 下一次思考**。

因此 `SelfState` 最核心的属性之一 = **Continuity（连续性）**。判定标准：**Version 371 的"我"为什么和 Version 370 不一样？答不出，这个 version 就没有认知意义。**

### 8.3 C · 成长判定的最高级验收（冻结）

所有"学习 / 成长 / 自我升级"统一归到同一判定，且**必须存在反事实 Z**：

```text
过去发生 X → 我认识到 → Self/Cognitive Delta → 当前 Y ≠ 原本 Z → 成长成立
```

若中间缺 "我没有反事实 Z" 或 "Y == Z"，则 **Memory+1 / version+1 / Knowledge+1 均不构成成长**。

### 8.4 D · 不可变性与可成长性分区（修正 v0.1 层级错误，冻结）

**不能把 Belief 与 Identity 放在同一个不可变等级**，否则陷入"不能改变认识，却要凭经历成长"的悖论。

```text
Identity Anchor       不可随经验改变
Core Self Boundary    稳定
Self Model            可以成长
Beliefs / Worldview   可以被证据推翻
Cognitive State       持续变化
```

身份可以稳定，认识必须可以改变。

### 8.5 项目定位转换（冻结）

之前：建设一个越来越强的认知 Runtime。
现在：**建设一个持续存在的"我"** —— Runtime 是它的身体，Memory 是它的过去，Perception 是它接触世界的方式，Brain 是它当前思考的能力，SelfModel 是它对自己的认识，WorldModel 是它对世界的认识，Learning 是它改变自己的机制。

决策：**现在不修代码。** 下一轮做 **SelfState Schema / Semantics Audit**（见 `OCOS_SELFSTATE_SEMANTICS.md`），定义清楚后再拿完整源码做 913 文件反查。

---

## 附：一句话推荐

**不要删 S2，不要只补 S1。** 把 S2 通电（持久化 + 接入思考回路），把 S1 降级为 S2 的"实测证据源"，用 §1.2 的标准给每次变化发"是不是成长"的判决书。这就是"让 OCOS 真正活着"的第一段足够小的路。