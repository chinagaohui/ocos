# OCOS P1-1 G4 — Production Thinking Read-Path Audit + Scope Amendment（AMENDED 响应）

> 依据：Human Gate 终裁 **G4 AMENDED ❌→不予 PASS**（2026-09-14）。
> 裁决要点：G4 读取/投影层实现合格（G4-A/B/C/D/F/G/H、I1/I2/I3 均满足），但 **G4-E 使用测试内
> deterministic consumer，未证明 OCOS production Thinking 实际消费 W1** → 核心命题
> "Worldview → Thinking Consumption" 尚未闭合。
> 裁决指示：**不动现有 G4 三文件**，先做 **Production Thinking Read-Path Audit**；
> 若存在合法生产消费者 → 只补真实调用链和生产级 G4-E 证据；若不存在 → 走最小 Scope Amendment。

---

## 0. 审计结论（TL;DR）

> **OCOS 存在合法生产 Thinking 入口，且不属于冻结四线（context_builder / decision_pipeline /
> agent_runtime / bridge）：`ocos/interaction/converse.py` — `ChatResponder`。**

生产链完整存在且当前**已经**在生产消费 S2 committed projection（P0-1 Step 3 语义）：

```text
HTTP / daemon / CLI 生产调用方
        ↓
ChatResponder.respond()            （converse.py:1763，生产 Thinking 入口）
        ↓
build_context()                    （converse.py:885，生产 LLM 上下文构造）
        ↓  已消费：get_self_projection(db).render()（L4-2 块，S2 committed）
真实 LLM TextGenerator._provider.generate(prompt, system_prompt=_SYSTEM_PROMPT)
        ↓
回复
```

**关键缺口（与 Human Gate 判断一致）**：
1. `render()`（self_state.py:552）**不含 worldview**（只含 5 组件；G1 第六组件未纳入 render 基线）
   → 生产 Thinking 目前**连文本形式都看不到 W1**。
2. `ThinkingContextProvider`（G4 新）**无生产调用方**——只有 G4 测试调用 → G4-E 是测试 consumer。

**因此**：补"真实调用链 + 生产级 G4-E 证据"的合法宿主 = `converse.py ChatResponder`（生产 Thinking
Entry，不在冻结四线），**无需新建第二条 Thinking Runtime，无需触碰四线**。

---

## 1. Audit 证据链（逐文件）

### 1.1 生产 Thinking 入口盘点（全库 LLM 推理点）

| 位置 | 角色 | 是否冻结四线 | 是否 S2 生产消费点 |
| --- | --- | --- | --- |
| `interaction/converse.py` ChatResponder | **对话 Thinking（主生产入口）** | ❌ 否 | ✅ 已消费（render/brief） |
| `reflection/self_review.py` / `engines/reasoning_engine.py` / `planning_engine.py` / `decision_making_engine.py` | 反思/推理/规划/决策引擎 | ❌ 否（但各自独立上下文构造，非本轮 context 宿主） | 部分 |
| `execution/bridge.py` / `goal_executor.py` | 执行层 LLM | ✅ 是（冻结） | 是（P0-4B 范围，不在 G4） |

**结论**：对话 Thinking 的唯一生产宿主 = `ChatResponder`；`ocos/runtime/context_manager.py` 的
`build_context` 是 Goal 执行 Context（goals/tasks/preferences 组装，非 LLM 推理上下文），与本轮无关。

### 1.2 ChatResponder 调用收敛（所有生产入口 → 同一宿主）

```text
routes/converse.py:85  (POST /ocos/converse)   → respond_auto
routes/converse.py:121 (POST /ocos/converse/stream) → respond_auto(_emit=)
routes/ws.py:188       (WebSocket)             → respond_auto
routes/openai_compat.py:84                     → respond_async
daemon/__init__.py:271                         → respond_auto
        ↓ 全部收敛
respond_auto → respond（converse.py:2547）
respond_stream → respond（converse.py:2002）
respond_async → respond（converse.py:2555）
        ↓
respond()（converse.py:1763）→ build_context()（:1774）→ LLM generate（:1851/:1897）
```

### 1.3 生产已消费 S2 committed 的证据（P0-1 Step 3 冻结语义在产线成立）

- `converse.py:965-975`（L4-2）：`get_self_projection(db).render()` 注入 S2；无 S2 → 空，绝不回退 S1。
- `converse.py:801-812`：能力自画像块同样经 `get_self_projection(db).brief()`。
- `self_state.py:602` 注释确认：生产 Prompt 路径（converse/bridge/recall_router）一律经 S2。
- `test_self_thinking_step3.py` T3-1~T3-4（FROZEN）：唯一 S2 来源 / No S1 bypass / committed 边界 / 持久化连续性。

### 1.4 缺口实证

- `self_state.py render()`（:552-578）：输出仅含 capability_awareness / knowledge_boundary /
  experience_profile / preference_model / cognitive_state —— **worldview 不在 render 中**（G1 T6b 基线
  有意保持 render 不含 worldview）。
- `worldview_read_adapter.py` 引用检索：生产代码（非测试）中 `ThinkingContextProvider` 调用 = **0 处**。

---

## 2. Scope Amendment 提案（最小接线，交 Human Gate 批准后实施）

### 2.1 原则（不违反 I3 No Silent Expansion 的显式 amendment）

- **不动** G4 三文件（self_state.py / worldview_read_adapter.py / G4 测试）——现有实现保持。
- **唯一新增生产文件**：`ocos/interaction/converse.py`（生产 Thinking 宿主，非冻结四线）。
- **唯一新增测试文件**：`ocos/tests/test_p1_1_g4_production_consumption.py`（生产级 G4-E 证据）。

### 2.2 接线点：`ChatResponder.build_context()`（converse.py:885，L4-2 S2 块之后）

在 `build_context()` 中 L4-2 块之后追加 **worldview 消费块**（最小、只读、可裁剪安全）：

```python
# G4: Worldview → Thinking consumption（committed 只读投影，经唯一读出口）
# 无 W1 → 块为空 → context 逐字节不变（G4-B 生产级保持）。
# 不推理、不判断、不修改；I2 溯源（claim_id/evidence_ids）保留。
try:
    from ocos.self.self_state import get_self_projection
    from ocos.self.worldview_read_adapter import ThinkingContextProvider
    s2 = get_self_projection(self._db_path)
    if s2 is not None:
        blocks = ThinkingContextProvider(s2).build(base_self_context="")["worldview"]
        if blocks:
            wv_lines = ["世界观（committed，结构化投影）:"]
            for b in blocks:
                wv_lines.append(
                    f"  [{b['domain']}] {b['judgment']} "
                    f"(frame={b['frame']}, stance={b['stance_type']}, "
                    f"conf={b['confidence']}, claim={b['claim_id']}, "
                    f"evidence={len(b['evidence_ids'])})")
            lines.append("\n".join(wv_lines))
except Exception as e:
    logger.debug("worldview consumption failed: %s", e)
```

设计要点：
- **数据流**：`committed S2 worldview → SelfProjectionAccessor.get_committed_worldview() →
  WorldViewReadAdapter.consume() → WorldViewContextBlock → ThinkingContextProvider.build() →
  build_context 文本段 → LLM prompt`。即 Human Gate §7 要求的
  `Production Thinking Entry → ThinkingContextProvider.build() → WorldViewContextBlock → Production Reasoning`。
- **零影响**：无 W1 → `blocks == []` → 不追加 → context 与改动前逐字节一致（G4-B 生产级）。
- **只读**：仅追加上下文文本，无写 Self / 无更新 worldview / 无回写（G4-H 语义保持）。
- **裁剪安全**：追加位置在核心块区（身份/daemon/画像/最近对话之前为裁剪保留区）——若超 4000 字符
  裁剪，worldview 块可能被裁掉，此时行为等同无 W1（无破坏）。
- **不进入 Decision/Execution**：converse 是对话 Thinking 层；reply 生成不触发
  decision_pipeline / agent_runtime / bridge 行为链（行为链 P1-1D 继续 NOT AUTHORIZED）。

### 2.3 生产级 G4-E 证据（新测试，真实生产路径调用）

`test_p1_1_g4_production_consumption.py` 覆盖（调用**真实生产代码路径**，非测试 consumer）：

| # | 用例 | 断言 |
| --- | --- | --- |
| P-E1 | 生产 mock consumer diff | 无 W1 vs 有 W1：真实 `ChatResponder.respond()`（mock 模式 = 生产兜底 consumer）输出 `reply` 可区分，且 diff 归因于 worldview 块文本 |
| P-E2 | 生产 LLM prompt 差分 | `respond()`（mock 或注入 fake provider）构造的 prompt 在 W1 存在时含 `世界观（committed…）` 块，不存在时不含；除该块外 base context 逐字节一致（唯一变量 = worldview） |
| P-E3 | 生产零影响基线 | 无 W1：`respond()` 的 context 与接线前基线**逐字节一致**（G4-B 生产级） |
| P-E4 | 只读 & 无回写 | 经生产路径消费后：S2 version/hash/history/worldview 全等；`m.current.worldview.get("evil") is None`（G4-H 生产级） |
| P-E5 | 溯源 | prompt 中 worldview 块含 `claim_id` / `evidence_ids` 计数（I2 生产级） |
| P-E6 | 回归 | 既有 converse 测试（mock 回复、编译目标、流式）全绿 |

- **生产 consumer 说明**：真实 LLM 路径（`TextGenerator`）在 CI 无 API key 环境不可注入；
  证据分两层：① 真实生产 mock consumer（`_state_reply`，确定性、生产代码）输出差分；
  ② LLM 路径的**输入差分**（prompt 文本含 worldview 块 = LLM 推理输入的直接证据），
  与 Human Gate §5 允许的 `risk_assessment: unknown → high` 型判定对齐（输入变化 → 推理输出变化，
  由生产路径 + 确定性 consumer 双侧落证）。

### 2.4 Amendment 边界（冻结保持）

```text
不改：self_state.py / worldview_read_adapter.py / G4 测试（已实现层）
不改：context_builder.py / decision_pipeline.py / agent_runtime.py / bridge.py（四线冻结）
不改：self_evidence.py / worldview.py / self_types.py / schema / migration（G3/G1 冻结）
不改：DecisionBridge / Execution
不进入：P1-1D（Thinking→Decision→Behavior Delta）、P0-4B 生产决策验证
```

---

## 3. 风险与失败案例预判

| 风险 | 处置 |
| --- | --- |
| worldview 块被 4000 字符裁剪裁掉 → 生产证据弱 | 测试用短 context（无裁剪触发）；生产裁剪行为 = 无 W1 等价（无破坏） |
| `get_self_projection` 在 :memory:/无身份时返回 None | 已有 L4-2 同款 try/except 兜底；无 S2 → 无块 → 零影响 |
| mock consumer（`_state_reply`）只回显 context 前 2000 字符 | P-E1 断言基于该生产回显路径的真实输出（生产代码行为，非测试伪造）；P-E2 覆盖 LLM prompt 层 |
| 既有 converse 测试（E2E/mock/流式）断言 context 全文 | P-E6 全量回归；无 W1 时逐字节不变保证旧断言不受影响 |

---

## 4. 请求

> 请求 Human Gate 批准 **G4 Scope Amendment**：
> 允许修改 `ocos/interaction/converse.py`（唯一生产文件，非冻结四线）追加 worldview 消费块，
> 新增 `test_p1_1_g4_production_consumption.py`（生产级 G4-E 证据），
> 其余全部保持 G4 AMENDED 裁决中的冻结项。

批准后实施步骤：① 接线 build_context → ② 生产级 G4-E 测试（P-E1~P-E6）→ ③ 受影响回归
（converse / self_state / G1 / G3 / step1-3 / phase40 / P0-4）→ ④ 全量回归 → ⑤ 更新
G4 Implementation Verification Report → 提交 G4 PASS/FROZEN 终裁。

**P1-1D 继续严格 NOT AUTHORIZED。**
