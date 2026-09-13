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

## 2. P0-1 目标架构（S2 = 唯一主 Self）

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

## 3. P0-1 实现步骤（DRAFT，待批准）

> 顺序设计为避免"先建壳再接线"的假 PASS。**先持久化，再聚合，再替换接线，最后 T-S1 验收。**

**Step 0 · 基线**：跑现有 self 相关测试（`test_phase40` / `test_phase43` / S1 相关），记录当前行为快照，保证重构可回滚。

**Step 1 · S2 持久化落地**
- 为 S2（Phase 40 `SelfModel`）建立首个持久化宿主：`self_state` 表（identity_ref / version / update_history / 7 域 JSON / content_hash / updated_at），复用现有 storage 连接模式（不新建第二套 DB）。
- 目的：让 S2 首次具备跨 restart 连续性 §14.2。
- **注意**：这**不是** P1 的"World continuity"，而是 P0-1 的"**State 连续性（Persistence）**"——分层口径允许。

**Step 2 · 7 域归并 + S1 降级为 Evidence**
- 定义 S2 7 域映射：现有 Phase 40 5 组件（Capability/Knowledge/Experience/Preference/Cognitive）+ 补齐 Situation / Worldview（占位，无数据则诚实缺省）。
- S1（AgentSelfModel 的 capabilities/personality/focus/failure_modes）作为 **Capability/Situation 域的 empirical evidence 源**注入 S2，S1 本体退出 Thinking 直连。

**Step 3 · 生产接线（替代硬编码占位符 + S1 直连）**
- `decision_pipeline.py L74`：`set_self_context("agent current state")` → 传入真实 S2 render。
- 三处 S1 直连（bridge/recall/converse）→ 改为消费 S2 的 Evidence/Claim projection（由 S2 聚合 S1 实测）。此处是 T-S1 红线落点。
- **明确禁止**：`context += S1.render() + S2.render()` 双注入（换壳）。

**Step 4 · T-S1 强制验收（P0-1 PASS/FAIL）**
```text
T-S1:
Decision/LLM 所消费的 Self representation，其 authoritative source 必须是 S2 SelfState。
任何 S1 信息出现在 Thinking，必须能追溯为 S2 当前状态内的
Evidence/Claim/Capability projection，而非 S1 独立 Self representation。
```
验收手段：静态 → 全库 lint 禁止生产路径 `AgentSelfModel.render()/render_brief()` 直连 Prompt；运行时 → decision_pipeline self 槽位输出 ≠ "agent current state"，且来自 S2。

**Step 5 · 记录决策日志**：S2 首次通电后，持久化首个 SelfState 快照供 P0-4 实验作为 baseline。

---

## 4. 明确非目标（P0-1 不做）

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