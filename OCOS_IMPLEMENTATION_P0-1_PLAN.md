# OCOS ⑨ Implementation P0-1 执行方案 — SelfState 真身通电（Read-Only Preflight + 计划）

> **性质：⑨ 第一阶段执行方案。** 只覆盖 P0-1：S2 真身通电、T-S1、持久化、生产 Thinking 接线。
> **状态：DRAFT（待你裁决后再动代码）。** 本文件先是 **Read-Only Preflight** 实证结果，再是 P0-1 实现步骤。
> **日期：2026-09-13（Asia/Shanghai）**
> **输入契约**：`OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md` §15 + `OCOS_P0_P1_P2_PLAN.md`（已冻结）。
> **范围边界（严守）**：不碰 P0-2 / P0-3 / P1 / P2；不扩大 913 审计；不写大代码；本次仅完成"真实生产路径测绘 + S2 通电设计 + T-S1 验收定义"。

---

## 0. 总目标（冻结自 ⑧）

> **让"以后真正参与 Thinking 的 Self 必须是 S2（SelfState）"。S1（AgentSelfModel）降级为能力证据，不得以独立 SelfState 进入 Thinking。** 以 **T-S1**（authoritative source 必须为 S2）为 P0-1 唯一验收。

---

## 1. Read-Only Preflight 实证（本次新测绘）

### 1.1 当前"Self 信息从哪里进入 Thinking"——实测生产路径

**生产里真正写进 Prompt 的 Self 内容 = S1 `AgentSelfModel`（SQLite 持久化，`agent_self_model` 表）**，存在 4 个注入/消费点：

| # | 位置 | 注入内容 | 语义 |
|---|---|---|---|
| 1 | [execution/bridge.py L2426-2429](file:///workspace/ocos/execution/bridge.py#L2426-L2429) | `AgentSelfModel().render()` → `facts`（自我能力事实块） | 自省/差距/总结类任务注入"我是谁" |
| 2 | [memory/recall_router.py L395-403](file:///workspace/ocos/memory/recall_router.py#L395-L403) | `AgentSelfModel().render_brief()`（≤120 字自我画像） | 持久召回 self 条目 |
| 3 | [interaction/converse.py L985-986](file:///workspace/ocos/interaction/converse.py#L985-L986) | `AgentSelfModel().render()` | 对话 self 块 |
| 4 | [daemon/__init__.py L385-392](file:///workspace/ocos/daemon/__init__.py#L385-L392) + [daemon/continuity.py L137-138](file:///workspace/ocos/daemon/continuity.py#L137-L138) + [daemon/motivation.py L489](file:///workspace/ocos/daemon/motivation.py#L489) | boot 加载 / 跨重启 hash / 动机源 | 生命周期支撑（非直接 Thinking 注入） |

**结论（T-S1 违规实证）**：生产里 LLM 所见到的"我"**全部来自 S1 的 render/render_brief**——正是 T-S1 要消灭的"S1 独立 Self representation 进入 DecisionBridge/LLM"。S1 目前是 de-facto 主 Self。

### 1.2 S2（SelfState）现状——存在双形体，均未接生产 Thinking

| 形体 | 位置 | 持久化 | 生产消费者 |
|---|---|---|---|
| Phase 40 `SelfModel` | [self/self_types.py L282](file:///workspace/ocos/self/self_types.py#L282) + [self_model.py L32](file:///workspace/ocos/self/self_model.py#L32) | ❌ **无持久化**（纯内存 dataclass） | ❌ 唯一"消费点"是硬编码占位符 |
| Phase 25.3 `SelfModelBuilder` | [self/models.py](file:///workspace/ocos/self/models.py) + [builder.py L116](file:///workspace/ocos/self/builder.py#L116) | ⚠️ 依赖 BeliefStore / SelfGovernor 记录 | ⚠️ `SelfMonitor`（自演化治理检查，非 Thinking 输入） |

**决策管线占位符（最刺眼证据）**：[cognitive_loop/decision_pipeline.py L73-74](file:///workspace/ocos/cognitive_loop/decision_pipeline.py#L73-L74)

```python
builder = ContextBuilder()
builder.set_self_context("agent current state")   # ← 硬编码字符串，不是 S2 SelfState
```

即：**决策/意图 Thinking 本来预留了 Self 槽位，却填入字面量 `"agent current state"`**。S2 完全没进去。

### 1.3 身份锚点（identity_ref 来源）——已具备持久化

- `IdentityAnchor.get_identity_id()` → `agent_id`（[agent/identity_anchor.py L85](file:///workspace/ocos/agent/identity_anchor.py#L85)）。
- `IdentitySQLiteStore` 持久化（[agent/identity_store.py L48](file:///workspace/ocos/agent/identity_store.py#L48)）；在 [agent_runtime.py L472](file:///workspace/ocos/agent/agent_runtime.py#L472) 装配。

**⇒ `identity_ref` 已有可信持久化来源，S2 可安全引用它（FREEZE S40-01 只引用不复制）。**

### 1.4 Preflight 问题清单回执

| 问题 | 实证 |
|---|---|
| S2 当前实例在哪里？ | Phase 40：仅 `daemon._self_monitor`（governance）持有 builder 输出的 `models.SelfModel`；Phase 40 `self_types.SelfModel` 无实例 |
| 生命周期在哪里？ | 无 S2 Thinking 生命周期；S1 生命周期在 daemon boot/tick |
| 是否有 persistence？ | SelfState v1 语义层 **无持久化**；S1 才有 `agent_self_model` 表 |
| identity_ref 从哪来？ | `IdentityAnchor(IdentitySQLiteStore)` 可提供 |
| version / update_history 从哪来？ | Phase 40 `SelfModel.update` 有 version+update_history（[self_types.py](file:///workspace/ocos/self/self_types.py)）；但无可持续化宿主 |
| 7 domains 谁负责？ | Phase 40 5 组件（Capability/Knowledge/Experience/Preference/Cognitive）；**缺 Situation/Worldview/Memory 域**；S1 也非 7 域 |
| 是否存在真实 runtime consumer？ | ❌ 无。决策槽位是硬编码占位符 |

---

## 2. STEP 0 · SelfState Ownership & Authority Freeze（只读冻结契约）

> **前置硬门：先冻结 S2 的所有权 / 权威 / 持久化 / 投影契约，再接线。** 本步不写业务逻辑，只锁死 6 件事。Step 0 产出后，才进入 Step 1-5。

### 2.1 六个契约裁决（冻结）

| # | 事项 | 裁决（冻结） |
|---|---|---|
| **1** | **S2 唯一实例** | 谁创建：`AgentRuntime` 在 boot（配好 `IdentityAnchor` 之后）创建唯一 S2。谁持有：**由 `AgentRuntime` 独占持有**，对外仅经只读 accessor 暴露。生命周期：boot 创建 → 仅经权威更新 → 每次更新持久化 → shutdown/按需 snapshot。**禁止**第二处创建 S2 真身；`SelfMonitor` 里 `SelfModelBuilder` 产出的 `models.SelfModel` 是**演化治理候选**，不得作为 Thinking 的 S2（否则出现"第二个我"）。 |
| **2** | **Persistence** | 每次权威更新**原子持久化当前 SelfState**：`identity_ref · version · 7 域投影 · 有限 update_history · content_hash · updated_at`。持久化的是**权威当前状态**（State continuity），**不是 Prompt**。跨 restart 可恢复该状态（§14.2）。 |
| **3** | **identity_ref** | 只读引用 `IdentityAnchor.get_identity_id()`（S40-01 只引不复制）。S2 只存 `agent_id` 字符串引用，不持有 anchor 对象；identity 唯一事实来源 = `IdentitySQLiteStore`。 |
| **4** | **Version vN→vN+1 谁产生** | 仅 S2 属主（`AgentRuntime`）经**权威更新路径**（`SelfGovernor`/`SelfUpdateContract`）递增 version。任何其它代码**不得**直接 bump。每次授权变更原子地产出 vN+1 并落库。 |
| **5** | **Update Authority** | 仅经冻结的权威通道（Phase 40 `SelfUpdateContract` + `SelfGovernor`）可改 S2 组件。来源受限（Experience/Registry/MemoryConsolidation/RuntimeObservation）。**S1 证据只能经 Claim/Delta 通道进入 S2**，禁止任意模块 raw 写 S2。 |
| **6** | **Thinking Projection** | S2 仅暴露**一个**投影接口，内部把 S1 证据处理成 Claim/Capability projection 输出给 Thinking。**生产 Thinking 只消费这个 S2 projection**。S1 的 `render()/render_brief()` **不得再出现在生产 Prompt 边**（S1→Thinking、S1+S2→Prompt 均禁止）。投影**从已提交的 S2 状态生成，不复读 S1 实时 render** —— S2 当前状态可独立存在/持久化/版本化。 |

### 2.2 强制投影链（冻结）

```text
S1 AgentSelfModel
      ↓ evidence
Self Claim / Capability evidence
      ↓
S2 SelfModel（权威状态，7 域，独立存在）
      ↓
S2 authoritative projection（单一路径）
      ↓
Thinking → Decision
```

**禁止边（生产）**：
```text
S1.render() ──→ Thinking        ✗
S2.render() ──→ Thinking(独立)  ✗（若无 S1 evidence 归并，算二次渲染）
S1.render() + S2.render() → Prompt  ✗
```

### 2.3 "S2 不是 S1 重新包装" 的冻结定义（关键）

替换 `S1.render()→Prompt` 为 `S2.render()→Prompt` **如果 S2 内容只是 S1 数据重打包，则形式 T-S1 PASS、语义未迁移**。

**必须证明**：S2 是 authoritative state，S1 只是其 evidence source；**S2 当前状态可独立存在、持久化、版本化**，Thinking 消费的是**该已提交状态**，而非 S1 的实时 render。

**反证测试（Step 4 forensic）**：在 S1 表内容变化后、但 S2 未重新聚合时，S2 投影应仍输出**上次已提交的权威状态**（证明 Thinking 消费提交态，而非 S1 实时值）。

### 2.4 Step 0 完成后的代码审计预期形状

```text
IdentityAnchor(IdentitySQLiteStore)
        ↓ identity_ref
S2 SelfModel(唯一, AgentRuntime 持有)
  Identity · Situation · Experience · Memory · Capability · Worldview · Cognition
        ↓ authoritative Self projection（单一路径）
   Thinking → Decision

S1 AgentSelfModel ──(empirical evidence)──→ S2.capability/claim/evidence
（不再存在 S1 → Thinking 的生产边）
```

---

## 3. P0-1 目标架构（S2 = 唯一主 Self）

```text
S1 AgentSelfModel（能力证据，SQLite）
        │ 只作 empirical capability evidence
        ▼
Self Claim / Self Delta
        ▼
S2 SelfState（唯一 authoritative representation，7 域）
        │
        ▼  production wiring（替代占位符 + S1 降级投影）
   Thinking / Decision / 对话
```

**接线替换原则（T-S1）**：
- 生产 Thinking 消费 Self **必须**来自 S2 的 render（authoritative source = S2）。
- S1 的信息若需出现在 Thinking，**必须以 S2 内 Evidence/Claim/Capability projection 形态**（即 S2 聚合 S1 实测后输出），**不得**以 `AgentSelfModel().render()` 直连 Prompt。
- 三处 S1 直连注入点（bridge facts / recall brief / converse block）改由 S2 交集提供。

---

## 4. P0-1 实现步骤（DRAFT，待批准）

> 顺序设计为避免"先建壳再接线"的假 PASS。**先锁 Ownership/Authority，再持久化，再聚合，再替换接线，最后 T-S1 forensic 验收。**
> **Step 0 是前置硬门，未冻结前不得进入后续步骤；后续步骤均为"接线"实现，需在 Step 0 契约上落地。**

**Step 0（前置 · 已完成冻结）**：SelfState Ownership & Authority Freeze —— 见 §2。产出后只读审计代码，确认无 `S1→Thinking` 生产边、无第二处 S2 真身。

**Step 1 · S2 持久化落地**
- 由 `AgentRuntime` 为其独占的 S2 建首个持久化宿主：`self_state` 表（identity_ref / version / 7 域 / 有限 update_history / content_hash / updated_at），复用现有 storage 连接模式（不新建第二套 DB）。
- 目的：S2 首次具备跨 restart 连续性。
- **注意**：这是 P0-1 的 **State continuity（Persistence）**，**不是** P1 的 World continuity（分层口径允许）。

**Step 2 · 7 域归并 + S1 evidence migration**
- S2 7 域 = Phase 40 5 组件（Capability/Knowledge/Experience/Preference/Cognitive）+ 补 Situation / Worldview（无数据则诚实缺省）。
- S1（capabilities/personality/focus/failure_modes）作为 **Capability/Situation 域 empirical evidence** 注入 S2；S1 本体退出 Thinking 直连。
- **S2 = 权威状态，独立可持久化/版本化；非 S1 数据重打包。**

**Step 3 · production Thinking replacement**
- `decision_pipeline.py L74`：`"agent current state"` → 真实 S2 authoritative projection。
- 三处 S1 直连（bridge/recall/converse）→ 消费 S1 证据经 S2 归并后的 projection。
- **禁止双注入**（`S1.render()+S2.render()`），**禁止 S1 作为生产投影**。

**Step 4 · T-S1 forensic acceptance（含反证测试）**
```text
T-S1（静态）：全库 lint 禁止生产路径出现 AgentSelfModel.render()/render_brief() 直连 Prompt；
             S2 projection 为 Thinking/Decision 的唯一 Self 输入。
T-S1（运行时）：decision_pipeline self 槽位输出 ≠ "agent current state"，且来自 S2 提交态。
反证（§2.3）：S1 表内容变化而未重新聚合时，S2 投影仍输出上次已提交权威状态。
```

**Step 5 · P0-4 baseline snapshot（主体状态基线，非 Prompt）**
- **不是保存当前 Prompt**，而是保存 P0-4 所需的主体状态基线：S2 的 7 域权威状态 + `identity_ref` + `version` + `update_history` + 关键证据锚 + `content_hash` + `updated_at`。
- 目的：为后续 Z（反事实）与 D（Self Delta）提供可靠因果锚点，避免 Z/D 审计无锚、落入事后解释。

---

## 5. 明确非目标（P0-1 不做）

- ❌ P0-2 Self Growth 链 / Self Delta 生成（下次）。
- ❌ P0-3 Worldview 重建（P0-1 只占位）。
- ❌ P1 World/Persistence/Skill 全量。
- ❌ P2 债务清理 / registry 统一。
- ❌ 新建"第二条 Cognitive Runtime"或第二套 SelfState 语义。

---

## 5. P0-1 自身闸门

- **PASS**：T-S1 通过（authoritative source = S2；S1 退出 Thinking 直连；占位符被真实 S2 替代；S2 有持久化）。
- **FAIL**：未达 T-S1（S1 仍直连 / S2 仍是壳 / 占位符未替换）→ 返回 Step 1-3 修正，**不得用调 Prompt 绕过**。

---

## 6. 待你裁决

本方案为 DRAFT。两条路：
1. **批准进入 Step 0** → 我开始实际接线（动代码）。
2. **先审阅本方案** → 调整后我再动。

你希望现在开始写代码，还是先核对该 Preflight 结论与步骤？