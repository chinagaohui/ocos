# OCOS P1-1 G4 — Worldview → Thinking Consumption Implementation Plan（×2 修订稿）

> 状态：**G4 SCOPE ACCEPTED ✅ → 本文件 = G4 Implementation Plan ×2（设计稿）。G4 Implementation = 仍 NOT AUTHORIZED**。
> 授权依据：`docs/OCOS_P1-1_G4_SCOPE_ASSESSMENT.md`（Human Gate：**G4 SCOPE ACCEPTED**）。
> 承接：G3 已 **PASS / FROZEN**；G3 frozen 链（Experience→…→Govern→W1）为唯一 worldview 上游事实链。
> Human Gate ×2 核心裁决（本修订吸收）：
> 1. **G4 是读取，不是认知增强**。2. **G4 是 Thinking input，不是 Decision behavior**。
> 3. **G4 消费 W1，不重新生成 W1**。四线：不碰 context_builder / decision_pipeline / agent_runtime / bridge。
> 本文件交 Human Gate 裁决 **G4 IMPLEMENTATION GO**。**不实现。**

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| 本 Plan（G4 Implementation Plan ×2） | ✅ 授权产出 |
| G4 Implementation | ❌ NOT AUTHORIZED（须本 Plan → Human Gate → 另行 GO） |
| 改 context_builder.py / decision_pipeline.py / agent_runtime.py / bridge.py | ❌ 禁止（行为链，触碰即污染 P1-1D） |
| 改 G3 frozen 链：self_evidence.py / WorldViewRecognitionRule / RecognitionType / Contract anchors | ❌ 禁止 |
| 改 worldview.py / self_types.py 定义 | ❌ 禁止 |
| 改 DecisionBridge / Execution | ❌ 禁止 |
| 做行为实验（Y≠Z）/ 进入 P1-1D | ❌ 禁止 |
| schema / migration | ❌ 禁止 |

---

## 1. G4 目标冻结

**一句话目标**：建立 **W1 → Thinking Input** 的**合法读取通道**，并证明该读取会**改变 reasoning context**；**不证明智能提升、不改变行为**。

```text
Committed WorldView W1
        ↓
WorldViewReadAdapter（只读）
        ↓
Thinking Input Context（WorldViewContextBlock，结构化）
        ↓
Reasoning Output Diff（结构化，测试内确定性 consumer）
```

验证链：

```text
W0 ≠ W1（G3 语义结构变化）
      ↓
input diff（G4-D）
      ↓
reasoning diff（G4-E）
```

**G4 明确不做**：不进入 Decision/AgentRuntime/Bridge/Execution；不生成任何自然语言"我的世界观认为…"；不重新解释或重新生成 W1。

---

## 2. 消费链（只读，新增读路径）

```text
S2 committed worldview（G3 frozen 链产出，经 Govern）
        ↓
SelfProjectionAccessor.get_committed_worldview()     ← read API（唯一读出口，committed only）
        ↓
WorldViewReadAdapter.consume()                      ← 只读，结构化 WorldViewContextBlock
        ↓
ThinkingContextProvider.build()                      ← 追加结构化 worldview 块（不改 base Self）
        ↓
Thinking Input Context（含 worldview block）
        ↓
Reasoning（读取该 context → 结构化 output）           ← G4-E 判据，非生产决策逻辑
```

**终止边界**：链条**止于 Thinking Input Context**。G4 **不做生产决策接线**（不注入 context_builder / decision_pipeline / agent_runtime）。真实决策影响留给 P1-1D。

---

## 3. 文件范围（最小改动表面）

| # | 文件 | 变更 | 性质 |
| --- | --- | --- | --- |
| 1 | `ocos/self/self_state.py` | `SelfProjectionAccessor` 增 **只读** `get_committed_worldview()`：从 committed S2 worldview 出结构化块；无 W1 → `[]`；既有方法（brief/render/project/committed_claims/component_consumption）**零改动** | 增量，读侧，向后兼容 |
| 2 | `ocos/self/worldview_read_adapter.py`（新） | +`WorldViewContextBlock`（结构化数据块）+`WorldViewReadAdapter`（只读封装）+`ThinkingContextProvider`（组装 Thinking Input Context） | 增量，新增，只读 |
| 3 | `ocos/tests/test_p1_1_g4_worldview_consumption.py`（新） | G4-A~H 用例矩阵 | 测试 |

**只允许修改/新增以上 3 项**。以下**绝对冻结不触碰**：

```text
self_evidence.py   ❌   worldview.py  ❌   self_types.py  ❌
context_builder.py ❌   decision_pipeline.py ❌   agent_runtime.py  ❌
bridge.py          ❌   DecisionBridge  ❌     Execution          ❌
schema/migration   ❌
```

---

## 4. 设计决策

### 4.1 `SelfProjectionAccessor.get_committed_worldview()`（read API，只读）

```python
# self_state.py — self_state.SelfProjectionAccessor 新增只读方法
def get_committed_worldview(self) -> list[dict]:
    """从 committed S2 worldview 导出结构化块（只读，无副作用）。

    数据源唯一 = self._manager.current.worldview（已 Govern 的 W1，唯一合法来源）。
    无 worldview / 无 judgment → []（Thinking input 不变化 → G4-B/F 保持）。
    仅暴露读：校验存在后原样结构化返回；不推理、不判断、不修改、不 fallback 生成。
    不改 render/brief/project 等既有方法（G1 T6b 基线不变）。
    """
    s = self._manager.current
    wv = getattr(s, "worldview", None)
    if wv is None:
        return []
    out = []
    for dom in wv.iter_domains():
        j = wv.get(dom)
        if j is None:
            continue
        out.append({
            "type": "worldview",
            "domain": dom,
            "judgment": j.judgment,
            "frame": j.frame,
            "stance_type": j.stance_type.value,
            "confidence": j.confidence,
            "continuity": j.continuity.value,
            "claim_id": j.claim_id,
            "evidence_ids": list(j.evidence_ids),
            "source": "committed_self_projection",
        })
    return out
```

- **只读**：唯一读出口，复用 `SelfProjectionAccessor` "Thinking 只能消费此 accessor 输出"纪律；无写路径。
- **不重新解释**：仅把已入库 W1 结构化搬移，无推导/判断/fallback。

### 4.2 `WorldViewContextBlock`（结构化，非自然语言）

```json
{
  "type": "worldview",
  "version": 1,
  "domain": "external_systems",
  "judgment": "external systems tooling is unreliable",
  "frame": "external_systems_are_uncertain",
  "stance": "cautious",
  "confidence": 0.82,
  "continuity": "first",
  "claim_id": "ev-…-WV",
  "evidence_ids": ["ev-…"],
  "source": "committed_self_projection"
}
```

- **结构化、可审计**；后续 diff 采集友好；不给自然语言"我的世界观认为…"留位（防 prompt 假消费）。

### 4.3 `WorldViewReadAdapter`（只读，禁止推理/判断/修改/fallback）

```python
# ocos/self/worldview_read_adapter.py —— 新增
class WorldViewReadAdapter:
    """只读封装：把 committed S2 worldview 投影为 Thinking 可消费的 WorldViewContextBlock 列表。

    只读：无写路径、不推理不判断、不做 fallback 生成。
    数据源唯一 = SelfProjectionAccessor.get_committed_worldview()（committed，经 Govern）。
    禁止访问：WorldViewRecognitionRule / WorldViewExperienceGate / Claim 生成层。
    """
    def __init__(self, accessor) -> None:
        self._acc = accessor

    def consume(self) -> list[dict]:
        """返回结构化 worldview 块（无 W1 → []）。"""
        return self._acc.get_committed_worldview()

    def has_worldview(self) -> bool:
        return bool(self.consume())
```

### 4.4 `ThinkingContextProvider`（唯一消费入口，只追加结构字段）

```python
# ocos/self/worldview_read_adapter.py —— 新增
class ThinkingContextProvider:
    """把 base Self 上下文 + worldview 块组装成 Thinking Input Context（唯一消费入口）。

    原则：S2 committed worldview → Read Adapter → Thinking input。只追加结构化字段，
    不改 base Self 自然语言段（G4-B 逐字节保 true）；CONFIRM 不改变 input（G4-F）。
    本组件只产出 Thinking Input Context，不接入任何生产决策执行。
    """
    def __init__(self, accessor) -> None:
        self._adapter = WorldViewReadAdapter(accessor)

    def build(self, base_self_context: str = "") -> dict:
        return {
            "self": base_self_context,                     # 逐字节转发，不改
            "worldview": self._adapter.consume(),          # 结构化块；无 W1 → []
        }

    def worldview_for(self, domain: str) -> dict | None:
        for b in self._adapter.consume():
            if b["domain"] == domain:
                return b
        return None
```

### 4.5 G4-E 结构化推理 diff（不引入行为实验，不要求任务成功率）

**不接 LLM 作 G4 判据**（随机性）。G4-E 用**确定性结构化 reasoning consumer**（测试内，非生产决策逻辑）证明：
对同一推理输入，W1 存在/不存在 → 结构化输出可区分（只改"结构化字段值 + 归因 reason"）。

```text
baseline（无 worldview）:
    risk_assessment = unknown
    rationale       = <base self only>
    worldview_used  = null

with worldview（W1: domain=external_systems frame=caution）:
    risk_assessment = high
    rationale       = worldview.frame(external_systems_are_uncertain) for external_systems
    worldview_used  = {"domain": "external_systems", "claim_id": "ev-…-WV",
                       "evidence_ids": ["ev-…"]}
```

即：G4-E 只证明 **worldview 块真的进入推理输入并被结构化输出引用（可归因 claim_id/evidence_ids）**。
**不要求**任务成功率提升 / 行为改善 / 长期策略变化。

### 4.6 防假消费 / 权限边界

- **G4-F**：仅 confidence / evidence_ids 变化（无结构 W1）→ `get_committed_worldview()` 稳定 → provider.build() 的 worldview 块不变 → **Thinking input 不变化**（与 G3 `_worldview_semantic_change` 同构）。
- **G4-H 权限边界（反向影响守卫）**：Thinking 读取**不得**反向改变 Self —— 修改 `ThinkingInputContext` / 消费产物，不能改 `WorldView / Claim / Delta / Govern`，否则成 `Thinking → Self` 自我污染。测试断言：消费路径（adapter/provider 只读）`_manager.current` 及其 worldview/update_history/hash **逐字段不变**；G3 frozen 链文件 import hash 不变、版本不变。

### 4.7 数据权限设计（谁可读 / 谁不可读）

| 层 | 权限 | 依据 |
| --- | --- | --- |
| **读** `SelfProjectionAccessor.get_committed_worldview()` | ✅ 允许 | 唯一读出口 |
| **读** `SelfModel.worldview`（经 accessor） | ✅ 允许（只读） | source=committed |
| **读** `WorldViewRecognitionRule` / `WorldViewExperienceGate` / Claim 生成层 | ❌ 禁止 | G4 不能重新解释世界观，只消费 Govern 后 W1 |

---

## 5. Verification（G4 GO 后执行）

载体：`ocos/tests/test_p1_1_g4_worldview_consumption.py`（G4-A~H）。

| # | 用例 | 判据 |
| --- | --- | --- |
| G4-A | 读取存在 | W1 存在 → `get_committed_worldview()` / provider.build() 含 worldview 块（judgment/frame/stance/confidence/continuity/claim_id/evidence_ids/source） |
| G4-B | 零影响基线 | 无 W1 → `[]`；provider.build() 的 self 段与 base **逐字节一致**（G1 T6b 语义保持） |
| G4-C | 只读消费 | 消费后 `_manager.current`（worldview/update_history/hash/version）不变；G3 frozen 链 import hash 不变 |
| G4-D | **input changed** | W1 形成（结构变化，如 frame: unknown→high_risk_external）前后，provider.build() worldview 块 diff ≠ ∅ 且归因到 judgment/frame/stance |
| G4-E | **output changed** | 确定性结构化 consumer：W1 存在/不存在 → 结构化输出（risk_assessment + worldview_used 归因）可区分 |
| G4-F | 防假消费 | CONFIRM（仅置信/证据）→ worldview 块不变 → input 不变（同 G3 V-sg） |
| G4-G | 回归 | 受影响集合（self_state / G1 / G3 / step1-3 / phase40）全绿 |
| G4-H | **Authority Boundary** | 修改 ThinkingContext/消费产物不反向改变 WorldView/Claim/Delta/Govern（version、content_hash、update_history、worldview 全等） |

**diff 采集方式**：worldview 块 canonical 逐项比较（domain/judgment/frame/stance tuple + claim_id/evidence_ids + confidence + continuity）；G4-E consumer 输出做字段级 tuple diff。

**G4 PASS 门槛**：G4-A~H 全过，且出现**至少一条"结构 W1 → input diff → output 可区分"完整链**（G4-D+E 联合）。仅 A/B/C 不构成 PASS。

---

## 6. Safety Audit

| 风险 | 守卫 | 证据 |
| --- | --- | --- |
| 假消费（prompt 加字段即声称使用） | G4-D/E 双 diff；G4-F CONFIRM 不变 | §4.5/4.6 / G4-D/E/F |
| 破坏 G1 T6b 零影响基线 | 不改 brief/render；新方法增量；无 W1 → []；self 段逐字节转发 | §4.1-4.4 / G4-B |
| 绕过 G3 frozen 链 / 重新生成 W1 | 消费端唯一来源 = committed accessor；禁止访问 Recognition/Claim 层 | §4.7 / G4-C |
| **反向污染 Self**（Thinking→Self） | G4-H 权限边界；adapter/provider 纯只读 | §4.6 / G4-H |
| 触碰行为链（Decision/AgentRuntime/Bridge） | 消费终止于 Thinking Input Context；禁止注入四线文件 | §2/§3 / G4-G |
| G4-E 越界（任务成功率/行为改善） | 限定结构化 output diff，不要求行为 Delta | §4.5 / §7 |
| 改动面失控 | 仅 2 生产文件增量/新增 + 1 测试文件 | §3 |

**新增面核对**：`SelfProjectionAccessor.get_committed_worldview`（只读）、`WorldViewReadAdapter`（只读）、`ThinkingContextProvider`（只读组装）、`WorldViewContextBlock`（数据结构）。**无新 authority、无新存储、无写路径、无生产决策接线、不改既有方法**。

---

## 7. Non-Goals / 递延

- G4 不做生产决策接线（context_builder / decision_pipeline / agent_runtime / bridge 四线冻结）—— 真实行为影响留给 P1-1D。
- G4 不接 LLM 作验证判据（用确定性结构化 consumer）。
- G4 不改 G3 frozen 链 / worldview / self_types / schema。
- G4 之后仍须独立 Human Gate 才能进入 P1-1D。

---

## 8. Human Gate

- 本文件 = **G4 Implementation Scope / Plan ×2 + Safety Audit（设计稿）**。**Implementation 仍 NOT AUTHORIZED。**
- Gate 裁决选项：**G4 IMPLEMENTATION GO** / **G4 PLAN AMENDED** / **G4 NO-GO**。
- 冻结纪律不变：实现授权前不修改任何生产文件；G3 frozen 链不受本 Plan 影响。

---

*本文件为 G4 实施规格（设计稿 ×2），非代码。等待 Human Gate 裁决。*