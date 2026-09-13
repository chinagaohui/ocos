# OCOS P1-1 G4 Scope — Worldview → Thinking Consumption 评估（只读审计/设计）

> 状态：**G4 SCOPE = ACCEPTED ✅**（授权进入 G4 Implementation Plan 编写阶段；**G4 Implementation = 仍 NOT AUTHORIZED**）。
> Human Gate 终裁（2026-09-13）：G4 Scope Assessment 达到裁决条件，ACCEPTED candidate。
> 授权边界：仅允许产出 **G4 Implementation Plan（设计）**；**不授权 G4 Implementation GO**，须再次提交 Plan → Human Gate → GO。
> 承接：G3 已 **PASS / FROZEN**（`docs/OCOS_P1-1_G3_IMPLEMENTATION_VERIFICATION.md`，2026-09-13 收口）。
> 依据：`WORLDVIEW_SEMANTIC_CONTRACT.md`（§5/§6/§9，FROZEN）；G1 Shape Design；G3 冻结语义链。
> 本文件是 **G4 Gate 的前置论证材料**，回答 "W1 形成后，OCOS 的 Thinking 是否真的读取它、怎么读才算真实消费"，
> 产出后交 Human Gate 裁决（G4 SCOPE ACCEPTED → 仅授权进入实现方案；NOT AUTHORIZED 维持 → 冻结）。

---

## 0. G4 定位（与 G3 的边界）

```text
G3（已收口 PASS）             G4（本评估，未授权）
Experience → Evidence →       WorldView W1
Provenance → Recognition      ↓
→ Claim → Delta → Govern      Thinking input changed（read path）
→ ⭐ W1 形成（可审计）          ↓
                              Reasoning output changed（consumption）
```

**G3 一句话**：OCOS 能因真实经历形成自己的 Worldview Delta（X→R→W1 可审计）。
**G4 一句话**：让 W1 首次进入 Thinking 消费链——但**必须证明是真实消费**（input 因 W1 变化，且 reasoning 输出可区分），
而不是"worldview 存在 + prompt 加字段 = 使用了"。

**G4 不回答**：行为是否改变（Y≠Z）——那是 P1-1D。G4 只到 **Thinking 读取并因 W1 改变推理输入** 为止。

---

## 1. G4-1 Read Path Audit（只读实证，2026-09-13）

### 1.1 审计方法

全仓库 grep `worldview` / `has_worldview` / `.worldview` 引用 + render/brief 实现逐行核对。

### 1.2 审计事实

| 路径 | 是否读取 worldview | 证据 |
| --- | --- | --- |
| `SelfProjectionAccessor.render()`（[self_state.py](file:///workspace/ocos/self/self_state.py#L523-L549)） | **否** | 逐组件列出 capability_awareness / knowledge_boundary / experience_profile / preference_model / cognitive_state —— **无 worldview 段** |
| `SelfProjectionAccessor.brief()`（[self_state.py](file:///workspace/ocos/self/self_state.py#L551-L568)） | **否** | 仅 capabilities / needs_verification / focus 三段，**无 worldview** |
| `agent_self_model.py::render()`（S1 legacy，[L302](file:///workspace/ocos/self/agent_self_model.py#L302)） | **否** | S1 路径，非 S2 消费点；G1 T6b 已证 worldview 文本零泄漏 |
| `context_builder.py` / `decision_pipeline.py` / `agent_runtime.py` / `converse.py` / `bridge.py` | **否** | 生产非 self 层 `worldview` 引用 = **0 处** |
| `ocos/self/` 生产代码 | 仅"写入/存储/识别"侧 | self_state.py（注册表）/ self_model.py（update_worldview）/ self_evidence.py（G3 管线）/ self_types.py（类型）—— **全部是 G1/G3 形成的写入端，无消费端** |

### 1.3 审计结论

> **W1 当前处于"已形成、可持久、可审计，但零读取"状态。**
> Thinking / Decision / Prompt 路径对 worldview 的消费接线 **完全空白** —— 这正是 G4 要填补的范围。

这也从反面对应 G1 T6b 的既有硬证据（render/brief 逐字节不变 + worldview 不泄漏）：
G1/G3 没有把 worldview 偷偷塞进任何生产 prompt 槽位，**消费边界现在仍是干净的**。

---

## 2. G4 范围定义（只读提案，未授权）

### 2.1 G4 要做（消费接线，严格对齐 G3 冻结语义链）

```text
仅允许消费：
WorldView W1（judgment / frame / stance_type / confidence / evidence_ids / continuity）
        ↑ 必须来自 G3 frozen 链：Experience → Evidence → Provenance Gate → Derived stats
        → Recognition → Claim → Delta → Govern → W1
禁止任何其他注入源（不走此链的 worldview 内容 = 非法）
```

候选消费接入点（**待 Human Gate 选定**，本文件只列评估，不实现）：

| 接入点 | 作用 | 风险 |
| --- | --- | --- |
| `render()` 追加 worldview 段 | Self 文本投影含世界观（只读） | 低：render 非 prompt 源；但需保 G1 T6b 零影响基线 |
| `brief()` 追加 worldview 摘要 | 决策自注入槽位含世界观 | **中：brief 是决策空间自注入源** → 直接进 Thinking；必须走防假消费判据（§3） |
| `context_builder` 注入 | Thinking prompt 含世界观段 | **中高：触及生产 prompt 槽位** → 必须证明 W1 变化 → input 变化 → output 变化 |

### 2.2 G4 不做（边界）

- ❌ 不改 G3 frozen 链（RecognitionType / Gate / Rule / Contract anchors 冻结不动）。
- ❌ 不做行为实验（Y≠Z）—— P1-1D 范畴。
- ❌ 不改 Decision Pipeline 逻辑 / DecisionBridge / AgentRuntime 行为。
- ❌ 不新建第二套 worldview 数据（消费端只读 committed S2 projection）。
- ❌ schema / migration 不改。

---

## 3. G4-2 防假消费判据（G4 核心验收红线）

### 3.1 假消费（禁止的形态）

```text
worldview 存在
        +
prompt 加字段
        =
Thinking "使用了" worldview      ← 这是数据库字段消费，不是认知消费
```

任何 G4 验收**不得**以此类断言通过。

### 3.2 真实消费（G4 必须证明的链）

```text
W0（无/旧 worldview 的 Thinking input）
 ↓
Experience X
 ↓
Recognition R
 ↓
W1（结构变化：judgment/frame/stance 至少一者变）
 ↓
Thinking input changed（render/brief/context 因 W1 实际变化 —— 逐字节 diff 证据）
 ↓
Reasoning output changed（对同一问题/同一输入，因 W1 存在推理可区分 —— 与 baseline 对照）
```

**判据清单**（G4 测试必须逐条断言）：

| # | 判据 | 证据要求 |
| --- | --- | --- |
| G4-A | 读取点存在 | render/brief/context 指定接入点**含** worldview 段（仅当 W1 存在时） |
| G4-B | 零影响基线 | 无 W1 时，接入点输出与 G1 T6b 基线**逐字节一致**（worldview 不泄漏到旧路径） |
| G4-C | 只读消费 | 消费端只读 committed S2 projection，**不写**、不 bypass govern、不改 G3 frozen 链 |
| G4-D | **input changed** | W1 形成前后，同一接入点的输出 diff ≠ ∅，且 diff 内容**可归因**到 W1 的 judgment/frame/stance |
| G4-E | **output changed** | 对同一推理输入，W1 存在 vs 不存在 → reasoning 输出（结构化/判定）**可区分** |
| G4-F | 防假消费终审 | 仅 confidence/evidence_ids 变化（无结构 W1）→ Thinking input **不变化**（与 G3 V-sg 对齐） |

### 3.3 判据成立性前提

- G4-D/E 必须以 **G3 冻结的 W1 语义**为因变量：只有 `_worldview_semantic_change` 认可的
  结构变化（judgment/frame/stance 任一）才允许改变 Thinking input；CONFIRM（仅置信/证据）**不得**改变 input。
- 这意味着 G4 与 G3 的 A 项判据同构：**世界观的认知影响力也只认结构变化，不认 tick/confidence 跳动**。

---

## 4. Safety Audit（G4 实施安全评估）

| 风险 | 守卫 | 证据/设计 |
| --- | --- | --- |
| 假消费（prompt 加字段即声称使用） | §3.2 G4-D/E 双 diff 判据 | 设计即验证 |
| 破坏 G1 零影响基线 | G4-B 逐字节对照 + 接入点条件渲染（无 W1 不输出） | G1 T6b 既有基线复用 |
| 绕过 G3 frozen 链注入 worldview | 消费端唯一来源 = committed S2 projection；识别/写入端不动 | §2.1 |
| 破坏 render/brief 既有消费者 | 接入点新段追加、旧段逐字节不变；受影响回归全绿 | 待 G4 GO 后执行 |
| 推理输出被世界观污染（超范围） | G4-E 只要求"可区分"，不要求"自动改变决策"；行为改变留给 P1-1D | §0 边界 |
| 改动面失控 | 仅限 Human Gate 选定接入点；Decision Pipeline 逻辑零改动 | §2.2 |

**当前零破坏事实（已审计）**：G1/G3 至今未触碰任何生产 prompt 槽位，消费边界干净（§1.3）——G4 是第一次在此边界上开孔，因此 Safety Audit 是 G4 的强制前置。

---

## 5. Verification 设计（G4 GO 后执行，本文件仅提案）

载体：`ocos/tests/test_p1_1_g4_worldview_consumption.py`（G4-A~F 矩阵）。

| # | 用例 | 判据 |
| --- | --- | --- |
| G4-A | 读取点含 worldview 段 | W1 存在 → render/brief/context 接入点输出含 judgment/stance/frame |
| G4-B | 零影响基线 | 无 W1 → 与 G1 T6b 基线逐字节一致 |
| G4-C | 只读消费 | 消费端不写 S2、不 bypass govern、G3 frozen 链文件 hash 不变 |
| G4-D | input changed | W1 结构变化前后，接入点输出 diff ≠ ∅ 且可归因 |
| G4-E | output changed | 同一输入下 W1 存在/不存在 → 推理输出可区分 |
| G4-F | 防假消费 | CONFIRM（仅置信/证据）→ input 不变 |
| G4-G | 回归 | 受影响集合（render/brief/decision 消费点 + G1/G3 全量）全绿 |

**G4 PASS 门槛**：G4-A~G 全过，且必须出现**至少一条"结构 W1 → input diff → output 可区分"完整链**（G4-D+E 联合）。
仅 A/B/C（字段存在 + 零影响）不构成 G4 PASS。

---

## 6. Non-Goals / 递延

- G4 不证明行为改变（Y≠Z）→ P1-1D，另行授权。
- G4 不接 DecisionBridge / AgentRuntime 行为修改。
- G4 不改 G3 frozen 链 / schema / migration。
- G4 之后仍须独立 Human Gate 才能进入 P1-1D。

---

## 7. Human Gate（终裁收口）

- 本文件 = **G4 Scope Assessment / Read Path Audit / 防假消费判据设计（只读，未实现）**。
- **Human Gate 终裁（2026-09-13）：G4 SCOPE ACCEPTED ✅** — 授权进入 G4 Implementation Plan 编写阶段；**G4 Implementation 仍 NOT AUTHORIZED**。

### 7.1 授权范围

**允许进入**：G4 Implementation Plan（设计）。**不授权**：G4 Implementation GO。
须再次提交：`G4 Implementation Plan → Human Gate → G4 IMPLEMENTATION GO`。

### 7.2 接受原因（六项）

1. G3 frozen semantic chain intact（G4 未改链，仅在其上新增读路径）。
2. W1 read path audit complete（render/brief/context/decision 零读取现状已实证）。
3. Consumption boundary identified（唯一 S2 读入口 = `SelfProjectionAccessor`；生产 prompt 经 `accessor.brief()`）。
4. Anti-fake-consumption criteria established（G4-D/E 双 diff 链，拒绝 context augmentation 冒充认知消费）。
5. G4 does not overlap P1-1D behavior delta（G4-E 限定为结构化 reasoning output diff，不要求任务成功率/行为改善）。
6. No production mutation proposed（本评估零生产改动）。

### 7.3 实施边界冻结（进入 Plan 阶段的硬约束）

**G4 允许（新增，仅读）**：
- `WorldViewReadAdapter` 或 `ThinkingContextProvider`（读取 committed S2 worldview → 结构化 worldview 块）。
- 消费原则：`S2 committed worldview → Read Adapter → Thinking input`。

**G4 禁止（绝对不触碰）**：
```text
worldview.py 修改 ❌
self_evidence.py 修改 ❌（G3 frozen 链）
WorldViewRecognitionRule 修改 ❌
DecisionBridge 修改 ❌
AgentRuntime 行为修改 ❌
Execution 修改 ❌
```

### 7.4 G4-E 克制定义（防提前侵入 P1-1D）

- **允许**：结构化 reasoning output diff（如 `risk_assessment: unknown → high` + `reason=worldview.frame mismatch`；candidate ranking 变化）。
- **不要求**：最终任务成功率提升、行为改善、长期策略变化 —— 这些属 P1-1D。

---

*本文件为 G4 Scope 前置评估材料，非代码。G4 SCOPE ACCEPTED ✅，下一步编写 G4 Implementation Plan（设计，另行 GO）。*
