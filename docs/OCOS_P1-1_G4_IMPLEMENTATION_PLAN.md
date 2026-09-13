# OCOS P1-1 G4 — Worldview → Thinking Consumption Implementation Plan

> 状态：**G4 SCOPE ACCEPTED ✅ → 本文件 = G4 Implementation Plan（设计稿）。G4 Implementation = 仍 NOT AUTHORIZED**。
> 授权依据：`docs/OCOS_P1-1_G4_SCOPE_ASSESSMENT.md`（Human Gate：**G4 SCOPE ACCEPTED**）。
> 承接：G3 已 **PASS / FROZEN**；G3 frozen 链（Experience→…→Govern→W1）为唯一 worldview 上游事实链。
> 本文件回答：G4 改哪几处、WorldViewReadAdapter / ThinkingContextProvider 边界、消费入口选择、
> G4-A~F diff 采集方式、防假消费判据落地、与 P1-1D 的边界。交 Human Gate 裁决 **G4 IMPLEMENTATION GO**。**不实现。**

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| 本 Plan（G4 Implementation Plan） | ✅ 授权产出 |
| G4 Implementation | ❌ NOT AUTHORIZED（须本 Plan → Human Gate → 另行 GO） |
| 改 G3 frozen 链：self_evidence.py / WorldViewRecognitionRule / RecognitionType / Contract anchors | ❌ 禁止 |
| 改 worldview.py 定义 | ❌ 禁止 |
| 改 DecisionBridge / AgentRuntime 行为 / Execution | ❌ 禁止 |
| 做行为实验（Y≠Z）/ 进入 P1-1D | ❌ 禁止 |
| schema / migration | ❌ 禁止 |

---

## 1. Scope — 最小改动表面

| 文件 | 变更 | 性质 |
| --- | --- | --- |
| `ocos/self/self_state.py` | `SelfProjectionAccessor` 增 **只读** `worldview_context()` 方法：从 committed S2 worldview 生成结构化消费块；无 W1 → 返回空；同名旧方法（brief/render/project/committed_claims/component_consumption）零改动 | 增量，读侧，向后兼容 |
| `ocos/self/worldview_consumption.py`（新） | +`WorldViewReadAdapter`（只读封装 committed worldview 读取）+`ThinkingContextProvider`（将 base Self 上下文 + worldview 块组装成 Thinking input context；**唯一消费入口**） | 增量，新增，只读 |
| `ocos/tests/test_p1_1_g4_worldview_consumption.py`（新） | G4-A~G 用例矩阵 | 测试 |

**明确不触碰**：`worldview.py`、`self_evidence.py`、G3 frozen 链、`DecisionBridge`、`AgentRuntime`、`Execution`、schema/migrations。

---

## 2. 设计总则

### 2.1 消费链（G4 只新增读路径，不触碰 G3 写链）

```text
S2 committed worldview（G3 frozen 链产出，只读）
        ↓
SelfProjectionAccessor.worldview_context()      ← 只读投影（唯一 S2 读入口）
        ↓
WorldViewReadAdapter                            ← 只读封装，结构化 worldview 块
        ↓
ThinkingContextProvider                          ← 组装 base Self + worldview → Thinking input context
        ↓
Thinking input changed（G4-D）
        ↓
Reasoning 读取该 input → 结构化 output diff（G4-E）
```

**与 G3 的对称性**：
- G3：`Experience 改变 → Recognition 改变 → W0→W1`（H3 结构门）。
- G4：`W1 改变 → Thinking input 改变 → Reasoning output 改变`（G4-D/E）。
- 两者共用同一边界哲学：**只认结构变化（judgment/frame/stance），不认 tick/confidence 跳动**。

### 2.2 唯一消费入口选择（分阶段，三选一 → 推荐 context_builder 承接注入）

审计事实（G4-Scope §1）：唯一 S2 读入口 = `SelfProjectionAccessor`；生产 prompt 经 `accessor.brief()`（recall_router:403 / converse:808）；`ContextBuilder` 是被动聚合袋（set_self_context → build → DecisionContext.self_summary），**非决策逻辑**。

| 候选接入点 | 风险 | 结论 |
| --- | --- | --- |
| 直接改 `brief()` 内嵌 worldview | **高**：brief 是生产 prompt 自注入槽位，改写会动 G1 T6b 零影响基线 | 不采用 |
| 新 `ThinkingContextProvider` 组装（推荐） | 低：新增只读组件，不改既有方法 | **采用为唯一消费入口** |
| 注入到 `ContextBuilder.set_self_context` | 低-中：唯一真正进入决策上下文聚合的接线点，需受控 | **作为 Wiring 阶段承接（§3.6）** |

**推荐**：消费的核心载体是新增的 `ThinkingContextProvider`；真正的生产注入点选择 **`ContextBuilder.set_self_context()`**（决策上下文 `self_summary` 槽位会带上 worldview 结构化块 —— 不触碰 DecisionBridge/AgentRuntime/Execution 逻辑本身，只是喂给既有聚合袋的 self 文本来源）。

---

## 3. 设计决策

### 3.1 `SelfProjectionAccessor.worldview_context()`（只读，增量）

```python
# self_state.py — SelfProjectionAccessor 新增只读方法
def worldview_context(self) -> list[dict]:
    """从 committed S2 worldview 生成结构化消费块（只读，无副作用）。

    无 worldview / 无 judgment → []（Thinking input 不变化 → G4-B/F 保持）。
    每条 judgment 输出结构化字段：domain / judgment / stance_type / frame /
    confidence / continuity / claim_id / evidence_ids。
    不改 render/brief/project 等既有方法（G1 T6b 基线不变）。
    """
    wv = getattr(self._manager.current, "worldview", None)
    if wv is None:
        return []
    return wv.summaries()          # WorldView.summary() 结构化视图（只读）
```

- **只读**：不提供任何写路径，复用 `SelfProjectionAccessor` "Thinking 只能消费此 accessor 输出"的既有纪律。
- **零影响**：新增方法不动既有方法；无 W1 → `[]`，消费端自然不变化。

### 3.2 `WorldViewReadAdapter`（新，只读）

```python
# ocos/self/worldview_consumption.py —— 新增
class WorldViewReadAdapter:
    """只读封装：把 committed S2 worldview 投影为可被 Thinking 消费的规范块。

    数据源唯一 = SelfProjectionAccessor.worldview_context()（committed，经 govern）。
    只读：无写路径、不 bypass govern、不 touch G3 frozen 链。
    """
    def __init__(self, accessor):
        self._acc = accessor

    def consume(self) -> list[dict]:
        """返回结构化 worldview 块（无 W1 → []）。"""
        return self._acc.worldview_context()

    def has_worldview(self) -> bool:
        return bool(self.consume())
```

### 3.3 `ThinkingContextProvider`（新，唯一消费入口）

```python
# ocos/self/worldview_consumption.py —— 新增
class ThinkingContextProvider:
    """把 base Self 上下文 + worldview 块组装成 Thinking input context（唯一消费入口）。

    原则：S2 committed worldview → Read Adapter → Thinking input。
    input context 的 worldview 部分由 W1 结构变化驱动；CONFIRM（仅置信/证据）不产生变化（G4-F）。
    """
    def __init__(self, accessor):
        self._adapter = WorldViewReadAdapter(accessor)

    def build(self, base_self_context: str = "") -> dict:
        return {
            "self": base_self_context,        # 既有 Self 上下文（逐字节转发，不改）
            "worldview": self._adapter.consume(),  # 结构化块；无 W1 → []
        }

    def worldview_for(self, domain: str) -> dict | None:
        for j in self._adapter.consume():
            if j["domain"] == domain:
                return j
        return None
```

### 3.4 G4-E 结构化推理 diff（不引入行为实验，不要求任务成功率）

**不接 LLM 作 G4 判据**（LLM 有随机性）。G4-E 用**确定性结构化推理消费者**证明：
对同一推理输入，W1 存在/不存在 → 结构化输出可区分（只改"结构化字段值 + 归因 reason"）。
示例（测试内确定性 consumer，非生产决策逻辑）：

```text
baseline（无 worldview）:
    risk_assessment = unknown
    rationale       = <base self only>

with worldview（W1: tool 域 frame=caution）:
    risk_assessment = high
    rationale       = worldview.frame(caution) for tool
    worldview_used  = {"domain": "tool", "claim_id": "...", "evidence_ids": [...]}
```

即：G4-E 只证明 **worldview 块真的进入了推理输入并被结构化输出引用**（可归因到 claim_id/evidence_ids），
**不要求**任务成功率提升 / 行为改善 / 长期策略变化。

### 3.5 防假消费终审（G4-F）

- 仅 confidence / evidence_ids 变化（无结构 W1）→ `worldview_context()` 输出稳定 → `ThinkingContextProvider.build()` 的 worldview 块不变 → **Thinking input 不变化**。
- 与 G3 `_worldview_semantic_change` 同构对齐；G4 测试复用 G3 的 CONFIRM 路径构造。

### 3.6 Wiring 阶段（唯一生产注入：`ContextBuilder.set_self_context`）

- 唯一生产接线点 = `ContextBuilder.set_self_context(provider_built.self 文本 + worldview 块)`。
- `ContextBuilder` 是被动聚合袋，`build()` 产出 `DecisionContext.self_summary`；**不改 `build()` / 决策逻辑 / DecisionBridge / AgentRuntime / Execution**。
- reverse 性：该注入可回退，不影响既有 self_summary 语义；无 W1 时 worldview 块为空，self_summary 与旧行为等价。

---

## 4. Safety Audit

| 风险 | 守卫 | 证据 |
| --- | --- | --- |
| 假消费（prompt 加字段即声称使用） | G4-D/E 双 diff；G4-F CONFIRM 不变 | §3.4/§3.5 / G4-D/E/F |
| 破坏 G1 T6b 零影响基线 | 不改 brief/render；新方法增量；无 W1 → [] | §3.1 / G4-B |
| 绕过 G3 frozen 链 | 消费端唯一来源 = committed S2 accessor；写端/G3 frozen 链零改动 | §3.1-3.3 / G4-C |
| 触碰 Decision 逻辑 | 只喂 `ContextBuilder.set_self_context` 文本；build()/DecisionBridge/AgentRuntime/Execution 零改动 | §3.6 / G4-G |
| G4-E 越界（任务成功率/行为改善） | G4-E 限定为结构化 output diff，不要求行为 Delta | §3.4 / §6 |
| 改动面失控 | 仅 2 生产文件（1 改增量 + 1 新）+ 1 测试文件 | §1 |

**新增面核对**：`SelfProjectionAccessor.worldview_context`（只读）、`WorldViewReadAdapter`（只读）、`ThinkingContextProvider`（只读组装）。**无新 authority、无新存储、无写路径、不改既有方法**。

---

## 5. Verification（G4 GO 后执行）

载体：`ocos/tests/test_p1_1_g4_worldview_consumption.py`（G4-A~G）。

| # | 用例 | 判据 |
| --- | --- | --- |
| G4-A | 读取点存在 | W1 存在 → `worldview_context()` / provider.build() 含 worldview 结构化块（domain/judgment/stance/frame/claim_id/evidence_ids） |
| G4-B | 零影响基线 | 无 W1 → `[]`；provider.build() 的 self 段与 base 逐字节一致（G1 T6b 语义保持） |
| G4-C | 只读消费 | 消费端只读 committed S2；不写 S2、不改 G3 frozen 链（import hash 不变） |
| G4-D | **input changed** | W1 形成（结构变化）前后，provider.build() 的 worldview 块 diff ≠ ∅ 且可归因到 judgment/frame/stance |
| G4-E | **output changed** | 确定性结构化 consumer：W1 存在 vs 不存在 → 结构化输出（risk_assessment + worldview_used 归因）可区分 |
| G4-F | 防假消费 | CONFIRM（仅置信/证据）→ worldview 块不变 → input 不变（同 G3 V-sg） |
| G4-G | 回归 | 受影响集合（self_state / context_builder / G1 / G3 / step1-3）全绿 |

**diff 采集方式**：对 `provider.build()["worldview"]`（list[dict]）做 canonical 逐项比较（domain/judgment/frame/stance tuple + claim_id/evidence_ids）；对 G4-E 结构化 consumer 输出做字段级 tuple diff。

**G4 PASS 门槛**：G4-A~G 全过，且出现**至少一条"结构 W1 → input diff → output 可区分"完整链**（G4-D+E 联合）。仅 A/B/C 不构成 PASS。

---

## 6. Non-Goals / 递延

- G4 不证明**生产用户可得性**：`ContextBuilder` 注入真实 runtime 场景的端到端验证与真实 LLM prompt 效果，属 Wiring 后续 + P1-1D 前置，另行处理。
- G4 不做行为改变（Y≠Z）→ P1-1D，另行授权。
- G4 不改 G3 frozen 链 / schema / DecisionBridge / AgentRuntime / Execution。
- G4 之后仍须独立 Human Gate 才能进入 P1-1D。

---

## 7. Human Gate

- 本文件 = **G4 Implementation Scope / Plan + Safety Audit（设计稿）**。**Implementation 仍 NOT AUTHORIZED。**
- Gate 裁决选项：**G4 IMPLEMENTATION GO** / **G4 PLAN AMENDED** / **G4 NO-GO**。
- 冻结纪律不变：实现授权前不修改任何生产文件；G3 frozen 链不受本 Plan 影响。

---

*本文件为 G4 实施规格（设计稿），非代码。等待 Human Gate 裁决。*