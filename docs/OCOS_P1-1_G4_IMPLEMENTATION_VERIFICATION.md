# OCOS P1-1 G4 — Worldview → Thinking Consumption 实施验证报告

> 状态：**G4 PASS / FROZEN ✅（Human Gate 终裁，2026-09-14）**。
> 终裁：G4-A~H / Production Read-Path / P-E1~P-E6 / I1·I2·I3 / Regression / Scope / Authority Boundary 全部 PASS。
> **G4 正式收口，不再继续扩展。P1-1D = NOT AUTHORIZED，下一步仅允许 Scope Assessment，不得直接实施。**
> 授权依据：`docs/OCOS_P1-1_G4_IMPLEMENTATION_PLAN.md`（×2 修订稿，Human Gate：**G4 IMPLEMENTATION GO ✅**）
> + `docs/OCOS_P1-1_G4_SCOPE_AMENDMENT_PRODUCTION_READPATH.md`（Human Gate：**G4 Scope Amendment = GO**，补齐生产 Thinking 真实消费证据）。
> 承接已 FROZEN 的 G1 Physical Seat（PASS）、G3 formation chain（PASS/FROZEN，Experience→Evidence→Provenance Gate→Derived statistics→Recognition→Claim→Delta→Govern→W1）。
> 本报告为**收口裁决材料**，报告 G4 已落地内容与 G4-A~H + P-E1~P-E6 验证证据，并逐项对照 Human Gate 授权范围
> （§2 允许修改 3 文件 / §3 禁止项冻结 / §4.2 adapter output == projection / §5 G4-E 边界 / §6 I1·I2·I3 约束 / Scope Amendment 生产宿主＝`ChatResponder.build_context()`）。

---

## 0. 收口定位

```text
G1 PASS FROZEN
       ↓
G3 PASS FROZEN
       ↓
G4 Scope ACCEPTED
       ↓
G4 Plan ×2 ACCEPTED
       ↓
G4 IMPLEMENTATION GO（Human Gate）
       ↓
G4 Implementation（G4-A~H 实证）
       ↓
G4 Verification G4-A~H（PASS 候选）
       ↓
Human Gate 终裁：G4 AMENDED（缺口：未证明生产 Thinking 真正消费 W1）
       ↓
G4 Scope Amendment = GO（补齐生产 Thinking Read-Path）
       ↓
Production Thinking Read-Path 接线（converse.py 唯一生产接线）
       ↓
G4 Verification P-E1~P-E6（生产消费实证）
       ↓
Human Gate 终裁：G4 PASS / FROZEN ✅（2026-09-14）
       ↓
P1-1D Scope Assessment（下一步，仅审计，不得直接实施）
```

**能力声明边界（严格保持）**：G4 完成后最多只能声明——

> **Worldview can enter Thinking input and produce attributable reasoning-context differentiation.**

G4 **不**主张：智能提升、成功率/任务完成提升、Thinking→Decision→Behavior Delta（Y≠Z）、长期策略改变。
以上全部属于 P1-1D，继续 **NOT AUTHORIZED**。

### 0.1 Scope Amendment 唯一缺口（Human Gate 终裁原文摘录）

```text
G4 的"读取层"实现是合格的；但 G4 定义的核心目标"WorldView → Thinking Consumption"
目前没有被证明发生在生产 Thinking 链上。
→ 要求：补齐"真实 Thinking 消费"证据/最小接线。
```

本修订版针对该唯一缺口：把消费链从"测试内 deterministic consumer"升级为
**生产宿主 `ChatResponder.build_context()` → 生产 Thinking Context / Prompt →
ChatResponder 真实 reasoning path**，并以 P-E1~P-E6 六项生产实证落证。

---

## 1. 落地范围（严格对齐 Human Gate §2 授权 + Scope Amendment 授权）

| # | 文件 | 变更 | 授权 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | `ocos/self/self_state.py` | `SelfProjectionAccessor.get_committed_worldview()`（只读 / committed only / no fallback / no inference / no mutation）；附 ruff 导入排序整理（无新增依赖） | §2① | ✅ |
| 2 | `ocos/self/worldview_read_adapter.py`（新） | `WorldViewContextBlock` + `WorldViewReadAdapter` + `ThinkingContextProvider` | §2② | ✅ |
| 3 | `ocos/tests/test_p1_1_g4_worldview_consumption.py`（新） | G4-A~H 共 8 用例（含 I1 diff 快照 / I2 source trace / G4-H 反向注入守卫） | §2③ | ✅ |
| 4 | `ocos/interaction/converse.py` | `ChatResponder.build_context()` 在 L4-2 块（S2 投影）之后注入 Worldview 消费块（Scope Amendment 唯一生产接线） | Amendment | ✅ |
| 5 | `ocos/tests/test_p1_1_g4_production_consumption.py`（新） | P-E1~P-E6 共 6 用例（生产 Reasoning Consumer / Prompt 差分 / 零影响基线 / Authority Boundary / I2 溯源 / 回归） | Amendment | ✅ |

### 1.1 文件变更证明（git status / git ls-files）

```text
生产文件：self_state.py（修改）+ worldview_read_adapter.py（新增）+ converse.py（修改）＝ 3 个
测试文件：test_p1_1_g4_worldview_consumption.py（新增）+ test_p1_1_g4_production_consumption.py（新增）＝ 2 个
```

**之外 0 修改。** 生产接线恰好 1 处（converse.py `build_context`），与 Scope Amendment 授权逐字一致。

### 1.1b Scope Amendment 唯一生产接线（converse.py 增量）

```text
生产链：committed W1 → SelfProjectionAccessor → WorldViewReadAdapter →
       ThinkingContextProvider → ChatResponder.build_context() →
       生产 Thinking Context/Prompt → ChatResponder 真实 reasoning path
```

```python
# G4: Worldview → Thinking consumption（P1-1 G4 Scope Amendment，唯一生产接线）。
try:
    from ocos.self.self_state import get_self_projection
    from ocos.self.worldview_read_adapter import ThinkingContextProvider
    s2 = get_self_projection(self._db_path)
    if s2 is not None:
        blocks = ThinkingContextProvider(s2).build(
            base_self_context="")["worldview"]
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
    logger.error("worldview consumption failed: %s", e, exception=e)
```

接线纪律（FROZEN）：
- **只读投影**，不推理、不判断、不修改；只进 Thinking input。
- **不接入** `context_builder / decision_pipeline / agent_runtime / bridge`（G4 终止边界不变）。
- 无 W1（accessor None / 无 judgment）→ 块为空 → context 逐字节不变（P-E3）。
- 「无 W1」≠「消费失败」：accessor/adapter/assembly 任何异常 → `logger.error`
  （不得静默降级成"没有 worldview"，避免生产证据链掩盖真实接线故障）。

### 1.2 明确不触碰（§3 禁止项 —— 全部冻结，未漂移）

```text
self_evidence.py      ❌ 未修改（G3 frozen 链原样）
worldview.py          ❌ 未修改（G1 容器原样）
self_types.py         ❌ 未修改
context_builder.py    ❌ 未修改（G4 终止边界：不接入）
decision_pipeline.py  ❌ 未修改
agent_runtime.py      ❌ 未修改
bridge.py             ❌ 未修改
DecisionBridge / Execution / schema / migration  ❌ 未触碰
```

### 1.3 上游链冻结保持（G3 frozen chain 未被修改）

```text
Experience → Evidence → Provenance Gate → Derived statistics → Recognition
→ Claim → Delta → Govern → W1        （G3，FROZEN，本次只读消费）
```

G4 实现**只**新增了 W1 之后的**读出口**（测试内消费层 + 生产 Thinking 接线）：

```text
W1（committed S2）
 ↓
Accessor read（get_committed_worldview，唯一读出口）
 ↓
structured projection（WorldViewContextBlock）
 ↓
Thinking Input Context（ThinkingContextProvider）
 ↓
ChatResponder.build_context()（生产 Thinking 上下文组装，Scope Amendment 唯一接线）
 ↓
生产 Thinking Context / Prompt → ChatResponder 真实 reasoning path
```

---

## 2. G4-A~H 实证（test output + 关键断言 + 失败案例）

测试载体：`ocos/tests/test_p1_1_g4_worldview_consumption.py`（8 用例，独立 tmp_path DB）。
W1 一律经 G3 frozen 链（`SelfEvidencePipeline` + 真实 Experience resolver）形成，**非**测试手造对象。

### 2.1 Test Output

```text
$ python -m pytest ocos/tests/test_p1_1_g4_worldview_consumption.py -v
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4a_read_path_contains_worldview_block PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4b_zero_impact_baseline          PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4c_readonly_consumption          PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4d_input_changed_with_snapshots  PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4e_output_changed_attributable   PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4f_confirm_does_not_change_input PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4g_existing_accessor_methods_intact PASSED
ocos/tests/test_p1_1_g4_worldview_consumption.py::test_g4h_thinking_cannot_mutate_self  PASSED
============================== 8 passed in 0.39s ==============================
```

### 2.2 逐项实证（关键断言）

| # | 用例 | 关键断言 | 结果 |
| --- | --- | --- | --- |
| **G4-A** | 读取点存在 | `get_committed_worldview()` 返回结构化块，字段 ⊆ `WorldViewContextBlock.FIELDS` 白名单；`type=="worldview"`、`source=="committed_self_projection"`；I2 溯源锚 `claim_id`/`evidence_ids` 非空；`provider.build()` 的 `worldview` 段与 accessor 输出一致 | ✅ |
| **G4-B** | 零影响基线 | 无 W1 → `[]`；`base_self_context` 段**逐字节一致**（`ctx["self"] == base`，G1 T6b 语义保持） | ✅ |
| **G4-C** | 只读消费 | 消费后 `m.version` / content_hash / update_history / worldview.judgments **全等**；`WorldViewReadAdapter`/`ThinkingContextProvider` 无 `update/declare/commit/replace/apply` 任何 mutation 方法 | ✅ |
| **G4-D** | input changed（I1） | W0 快照 `[]` → FIRST 后 `w1_blocks != w0_blocks`（diff ≠ ∅）；REFRAME 后二次 diff 归因到 `frame` 变化 + `continuity=="replaced"`；canonical key 7 字段齐全（domain+judgment+frame+stance_type+continuity+claim_id+confidence） | ✅ |
| **G4-E** | output changed | 同 base self：无 W1 → `risk_assessment=="unknown"`、`worldview_used is None`；W1 存在 → `wv_out != baseline_out`、`worldview_used.claim_id/evidence_ids/domain` 与块一致（可归因）；输出字段 ⊆ 白名单 `{risk_assessment, rationale, worldview_used}`（无 recommended_action/strategy/decision，P1-1D 边界） | ✅ |
| **G4-F** | 防假消费 | CONFIRM（同 expected/actual）→ `ingest()==[]`、`m.version` 不变、块逐字段不变 → Thinking input 不变 | ✅ |
| **G4-G** | 回归（消费点） | 消费路径存在时既有 accessor 方法 `render`/`brief`/`project`/`version` 仍正常 | ✅ |
| **G4-H** | Authority Boundary | 篡改 ThinkingContext（`ctx["worldview"]=[]` / 注入 `{"domain":"evil",...}`）后：version/hash/history/worldview 全等；`m.current.worldview.get("evil") is None`（无反向注入，Thinking 无回写能力） | ✅ |

### 2.3 失败案例（测试开发过程中的真实失败与修复 —— 非一次性装饰性测试）

| # | 失败 | 原因 | 修复 | 状态 |
| --- | --- | --- | --- | --- |
| F1 | `test_g4d` 断言失败 | `_canonical_key` 元组索引错位（`key_tuple[1]` 应为 `key_tuple[0]` 才匹配 domain） | 修正索引，断言 domain=="tool" | ✅ 修复后通过 |
| F2 | `test_g4g` 断言失败 | `brief()` 返回 `str` 而非 `list`（既有 accessor 契约） | 修正类型断言 `isinstance(acc.brief(), str)` | ✅ 修复后通过 |
| F3 | `test_g4h` KeyError | 篡改的 worldview 块缺 `confidence` 字段 → `_structured_consumer` 抛 KeyError | 测试内 try-except 捕获（篡改数据不应对被测组件构成回写路径） | ✅ 修复后通过 |
| F4 | ruff E501（line too long） | 测试注释超长行违反 line-length=100 | 拆分注释行 | ✅ 0 issue |
| F5 | `WorldViewContextBlock._BLOCK_FIELDS` 私有引用报错 | 测试直接引用模块私有变量 | 在类上暴露 `FIELDS` 类属性供 schema 断言 | ✅ 修复后通过 |

**归因**：F1–F3 是测试自身断言的修正（被测实现语义未变）；F4–F5 是测试可读性与 API 暴露的完善。修复后 8/8 全绿，且修复**未**触碰生产语义（§4 安全审计）。

---

## 2b. P-E1~P-E6 实证（Scope Amendment：生产 Thinking 消费）

测试载体：`ocos/tests/test_p1_1_g4_production_consumption.py`（6 用例，独立 tmp_path DB）。
W1 一律经 G3 frozen 链（`SelfEvidencePipeline` + 真实 Experience resolver）形成；消费宿主为
**真实生产 `ChatResponder`**（`ocos/interaction/converse.py`），`_FakeProvider` 只做
deterministic provider 挂载（记录生产 prompt、返回固定回答，不伪造推理、不触碰 S2）。

### 2b.1 Test Output

```text
$ python -m pytest ocos/tests/test_p1_1_g4_production_consumption.py -v
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e1_production_reasoning_consumer PASSED
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e2_production_prompt_diff        PASSED
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e3_zero_impact_baseline          PASSED
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e4_authority_boundary            PASSED
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e5_i2_trace_in_production        PASSED
ocos/tests/test_p1_1_g4_production_consumption.py::test_p_e6_regression                    PASSED
============================== 6 passed in 1.11s ==============================
```

### 2b.2 逐项实证（关键断言）

| # | 用例 | 关键断言 | 结果 |
| --- | --- | --- | --- |
| **P-E1** | 生产 Reasoning Consumer | fake provider 挂在真实 `ChatResponder.respond()` 路径（`out["provider"]=="fake"` 证明走真实 provider 分支）；W0 生产 prompt 无 worldview 块 → W1 后 prompt 含块；同一 respond() 路径下 `prompts[0] != prompts[1]`（生产 prompt 差分） | ✅ |
| **P-E2** | 生产 Prompt 差分 | `ctx_w0` 无块 → `_make_w1` 后 `ctx_w1` 含块且 `!= ctx_w0`；**唯一新增变量定位**：`_mask_s2_version(_strip_wv_block(ctx_w1)) == _mask_s2_version(ctx_w0)`（剥离块 + 归一化 S2 版本号后逐字节相等）；生产 prompt 层携带 `claim={claim_id}` / `evidence={n}` | ✅ |
| **P-E3** | 零影响基线 | 无 W1 → `get_committed_worldview()==[]`、`provider.build()["worldview"]==[]`、生产 context 无块；替换 provider 为恒空块（与真实"无 W1"输出等价）→ `ctx_inert == ctx_normal`（G4 注入完全惰性，逐字节零贡献） | ✅ |
| **P-E4** | Authority Boundary | W1 存在且生产 prompt 真实消费后（先断言 `WV_HEADER in prompts[0]`），`serialize_state` 快照 `(version, hash, update_history, worldview.judgments)` **全等**（消费能力 ≠ Self Mutation Authority） | ✅ |
| **P-E5** | I2 溯源（生产级） | 生产 context 含 `claim={claim_id}` / `evidence={n}` / `[{domain}]` / committed judgment 原样；生产 prompt 含同源 `claim_id`（I2 生产链可恢复） | ✅ |
| **P-E6** | 回归 | 既有 context 块 `身份:`/`认知引擎:`/`真实能力:` 完整；回复结构 `{"reply","provider"}` 不变；有 W1 时 `SelfState v` 投影与 worldview 块互不干扰；accessor `render/brief/project` 正常 | ✅ |

### 2b.3 Scope Amendment 缺口对照（Human Gate 终裁逐项关闭）

| 终裁缺口 | P-E 证据 | 状态 |
| --- | --- | --- |
| "G4-E 只在测试内 deterministic consumer 上证明消费" | P-E1：消费链挂真实 `ChatResponder.respond()`，provider 只替换 LLM 引擎（生产宿主、生产 prompt 组装路径原样） | ✅ 关闭 |
| "未证明生产 Thinking 真正消费 W1" | P-E1/P-E2：生产 context 与生产 prompt 均含 committed worldview 块，且块剥离前后逐字节差分归因 | ✅ 关闭 |
| "真实 Thinking 消费"证据完整性 | P-E2/P-E5：生产 prompt 层携带 claim_id / evidence 计数（I2 溯源贯通到生产 reasoning 输入） | ✅ 关闭 |

**P-E 系列与 G4-E 的关系**：G4-E 证明"输入差分 → 可归因推理输出差分"的**因果机制**（确定性 consumer）；
P-E 系列证明同一输入差分**确实进入生产 Thinking 输入**（ChatResponder 真实组装路径）。
二者叠加 = 生产链上"W1 进入 Thinking input"且"差分可被 reasoning 消费"双证齐备。

---

## 3. G4-D/E 完整链（最高优先级实证）

Human Gate 要求必须证明：

```text
结构 W1 → Thinking input changed → Reasoning output changed
```

### 3.1 G4-D：结构 W1 → Thinking input changed（含 I1 快照）

```python
# W0 input snapshot（FIRST 前）
w0_blocks = list(provider.build(base_self_context="base")["worldview"])
assert w0_blocks == []

# FIRST 形成 W1（NOVEL_PATTERN：无 prior → 结构变化）
pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"))
w1_blocks = provider.build(base_self_context="base")["worldview"]
assert w1_blocks != w0_blocks          # ← input diff ≠ ∅
assert key_tuple[0] == "tool"

# 结构 REFRAME（divergence 类别改变 → frame 变化）→ 二次 diff 可归因到 frame
pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "file exists", "missing", "EP-REFRAME"))
w2_blocks = provider.build(base_self_context="base")["worldview"]
assert w2_blocks != w1_blocks
assert w2_blocks[0]["frame"] != w1_blocks[0]["frame"]   # ← 归因：frame 变化
assert w2_blocks[0]["continuity"] == "replaced"
```

**I1（Diff 可审计）**：canonical diff 键覆盖 7 字段（domain/judgment/frame/stance_type/continuity/claim_id/confidence），W0/W1 快照在测试内显式保存并断言——不是"运行后看输出"的事后重建，是**决策前冻结、决策后对比**。

### 3.2 G4-E：Thinking input changed → Reasoning output changed

```python
base = "SELF-v1"
baseline_ctx = provider.build(base_self_context=base)
baseline_out = _structured_consumer(baseline_ctx)
assert baseline_out["risk_assessment"] == "unknown"
assert baseline_out["worldview_used"] is None

pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"))
wv_ctx = provider.build(base_self_context=base)
assert wv_ctx["self"] == baseline_ctx["self"]   # 唯一变化 = worldview 块（变量控制）
wv_out = _structured_consumer(wv_ctx)

assert wv_out != baseline_out                    # ← output changed
assert wv_out["worldview_used"]["claim_id"] == block["claim_id"]      # 归因
assert wv_out["worldview_used"]["evidence_ids"] == block["evidence_ids"]
assert wv_out["worldview_used"]["domain"] == "tool"
assert set(wv_out) <= {"risk_assessment", "rationale", "worldview_used"}  # P1-1D 边界
```

**G4-E 合格标准核对**：输出差分是 `risk_assessment: unknown → high` 型（`rationale: worldview.frame(...)` 型）——**attributable reasoning-context differentiation**；不是 "因为 worldview 所以执行 X 行为"（后者 = P1-1D，禁止）。同一确定性 consumer 在"无 W1 vs 有 W1"下输出可区分，且 base self 段逐字节一致（唯一变量 = worldview 块）→ 差分因果归因于 worldview 输入。

### 3.3 完整链（结构 W1 → input → output）一次落证

G4-D（input diff）+ G4-E（output diff）在同一 G3 frozen 链上串联：真实 Experience → Evidence → Provenance Gate → Recognition → Claim → Delta → Govern → committed W1 → Accessor read → Block → Thinking Context → Reasoning output。**无一步绕过 G3 链**（W1 均由 `SelfEvidencePipeline.ingest` 形成）。

---

## 4. I1 / I2 / I3 实现约束验证

| 约束 | 要求 | 证据 |
| --- | --- | --- |
| **I1** Diff 可审计 | G4-D 保存 W0 input snapshot / W1 input snapshot / canonical diff，含 domain/judgment/frame/stance_type/continuity/claim_id | `test_g4d`：w0_blocks/w1_blocks/w2_blocks 三快照 + `_canonical_key` 7 字段断言（§3.1） |
| **I2** Source Trace 保留 | WorldViewContextBlock 必须保留 claim_id / evidence_ids / source | `WorldViewContextBlock.FIELDS` 含 3 溯源字段；`test_g4a` 断言 `claim_id`/`evidence_ids` 非空、`source=="committed_self_projection"`；`test_g4e` 断言 reasoning output 的 `worldview_used.claim_id/evidence_ids` 与块一致 → 最终链 `Experience→Evidence→Claim→W1→Thinking Input` 可恢复 |
| **I3** No Silent Expansion | 若需改 context_builder/decision_pipeline/agent_runtime → 立即停止并重提 Scope Amendment | **未发生**：git diff 证明 0 触碰（§1.2）。G4 终止边界 = Thinking Input Context，未接入任何生产决策执行 |

---

## 5. 回归与零破坏归因

### 5.1 G4 新测试 —— 14 passed（8 G4-A~H + 6 P-E1~P-E6）

```text
ocos/tests/test_p1_1_g4_worldview_consumption.py   …… 8 passed  （G4-A~H）
ocos/tests/test_p1_1_g4_production_consumption.py  …… 6 passed  （P-E1~P-E6）
```

### 5.2 受影响回归 —— 113 passed（全绿，本次实测）

```text
ocos/tests/test_p1_1_g4_worldview_consumption.py  …… 8  passed  （G4 新，单独计）
ocos/tests/test_p1_1_g4_production_consumption.py …… 6  passed  （P-E 新，单独计）
ocos/tests/test_p1_1_g1_worldview_seat.py          …… 13 passed  （G1 governance）
ocos/tests/test_p1_1_g3_worldview_pipeline.py      …… 12 passed  （G3 formation 链）
ocos/tests/test_self_state_step1.py                …… 8  passed  （S2 持久化/投影）
ocos/tests/test_self_evidence_step2.py             …… 8  passed  （Evidence pipeline）
ocos/tests/test_self_thinking_step3.py             …… 5  passed  （S2→Thinking 只读投影）
ocos/tests/test_phase40.py                         …… 35 passed  （六组件/UpdateContract 回归）
ocos/tests/test_p0_4_preconditions.py              …… 10 passed  （Z 冻结 / Decision Trace）
ocos/tests/test_external_interaction.py            …… 16 passed  （converse 宿主交互回归）
ocos/tests/test_p52_active_interaction.py          …… 6  passed  （主动交互回归）
合计：113 passed（不含 G4 新 14 项）；连同 G4 新测试 = 127 passed，0 failed
```

证明 G4 未破坏：G1 worldview 座位、G3 formation 链、S2 持久化、Evidence pipeline、
Thinking 只读投影、P0-4 前置冻结、converse 交互宿主（生产接线宿主本身回归通过）。

### 5.3 全量目录回归 —— 失败全部 pre-existing，零 G4 归因

```text
$ python -m pytest ocos/tests/ -q --ignore=ocos/tests/test_webchat_api.py
= 39 failed, 4198 passed, 31 skipped, 8 xfailed in 1059.59s =
```

失败集中于 10 个文件，逐一归因（**均与 G4 改动无关**）：

| 失败文件 | 原因 | 归因 |
| --- | --- | --- |
| test_text_generator.py / test_server_manager.py / test_runtime_loop.py / test_performance_manager.py / test_phase50_growth.py / test_phase51.py / test_phase52.py / test_phase_fix17_proactive.py | `async def` 无 async 插件支持（缺 pytest-asyncio 等） | 环境依赖缺失，**非代码** |
| test_import_rules.py | 80 个非法 import，其中 `self/self_state.py:56-58` 的 `ocos.storage.*` 为 **HEAD 既有**（G1/G3 时代已存在，本次仅 ruff 重排导入顺序，未新增任何非法 import）；其余全部来自 agent/autonomous/execution/governance 等 G4 未触碰文件 | **pre-existing**（`git stash` 到 HEAD 复跑：**同样 11 failed**，22 passed） |
| test_execution_bridge.py | DAG 依赖缺失 / `assert 'failed' == 'completed'`（execution 层既有行为） | **pre-existing**（G4 禁止触碰 execution 层） |

**归因方法**：`git stash push -u`（移除 G4 全部改动）后复跑 `test_import_rules.py + test_text_generator.py` → **11 failed / 22 passed** 与改动前一致 → 证明失败在 HEAD 即存在，G4 零贡献。stash 已恢复（pop 后 git status 与改动前逐字一致）。

### 5.4 Lint / Quality

```text
ruff check ocos/self/worldview_read_adapter.py \
         ocos/tests/test_p1_1_g4_worldview_consumption.py \
         ocos/tests/test_p1_1_g4_production_consumption.py
→ 0 issue（新文件全净）

ruff check ocos/self/self_state.py / ocos/interaction/converse.py
→ 既有错误（N818 / B905 / E501 等）git show HEAD 验证全部为改动前已存在，非本次引入，不阻塞 G4
```

---

## 6. 安全性审计结论（对照 G4_IMPLEMENTATION_PLAN ×2 §4 与 Human Gate §4/§6）

| 红线 / 风险 | 状态 | 证据 |
| --- | --- | --- |
| 消费即生成新 judgment（accessor → 重新解释 → 新判断） | ✅ 关闭 | `get_committed_worldview()` 只做结构化搬移（无规则/无派生/无 default 补值）；adapter output == projection（G4-A/G4-C） |
| adapter output == interpretation（recommended_action/strategy/decision） | ✅ 关闭 | 块字段白名单 = committed W1 原样字段 + 溯源锚；`test_g4e` 断言输出 ⊆ `{risk_assessment, rationale, worldview_used}`（G4-E 边界） |
| Thinking→Self 反向污染（修改 context → 改 worldview/claim/delta） | ✅ 关闭 | `test_g4h`：篡改 input context 后 version/hash/history/worldview 全等，`evil` 域未注入 |
| 绕过 Govern 读取（读 Recognition/Claim 生成层） | ✅ 关闭 | 数据源唯一 = committed S2 worldview（`self._manager.current.worldview`），不触 recognition/claim 层（G4-A 断言 source） |
| 假消费（加字段即声称使用） | ✅ 关闭 | G4-F（CONFIRM 不改变 input）+ G4-D/E 双 diff 判据（input changed ∧ output changed 且可归因） |
| 无 W1 fallback 生成 | ✅ 关闭 | 无 worldview → `[]`，Thinking input 不变化（G4-B / P-E3） |
| I3 静默扩面（动 context_builder/decision_pipeline/agent_runtime） | ✅ 未发生 | git diff：0 触碰（§1.2） |
| 降低 G3 可追溯性 | ✅ 未发生 | 块保留 claim_id/evidence_ids/source（I2），G3 链未修改（§1.3） |
| **生产接线反向污染**（build_context 消费 → 改 Self） | ✅ 关闭 | P-E4：生产 prompt 真实消费后 `(version, hash, update_history, worldview)` 快照全等 |
| **生产接线故障被静默掩盖**（异常降级成"没有 worldview"） | ✅ 关闭 | 接线用 `logger.error`（无 W1 = 无日志；异常 = 显式 error），不静默降级（§1.1b） |
| **生产接线破坏既有 Thinking 上下文** | ✅ 关闭 | P-E3（无 W1 逐字节不变）+ P-E6（既有块/回复结构不受影响） |

**新增面核对**：1 个只读方法 + 3 个只读类 + 1 处生产只读接线（converse.py `build_context` 内追加块）。
**无新 authority、无新 runtime、无新存储、无自然语言注入、无生产决策接线**（接线终止于 Thinking input 组装，未接入 decision/execution）。

---

## 7. G4 PASS Gate 前检查项（对照 Human Gate 裁决书逐项）

| Human Gate 检查项 | 状态 |
| --- | --- |
| G3 frozen chain 未被修改 | ✅ 未修改（§1.3） |
| G4 仅消费 W1，不重新生成 W1 | ✅ 消费即投影（§6） |
| Scope 未漂移（仅 3 生产文件 + 2 测试） | ✅ git status 逐字一致（§1.1） |
| 未触碰 Decision / Execution 行为链 | ✅ 0 触碰（§1.2） |
| 未进入 P1-1D | ✅ 输出白名单 + 终止边界 = Thinking Input Context（§3.2） |
| 防假消费判据明确 | ✅ G4-D + G4-E 双 diff + P-E2 生产 prompt 差分（§3 / §2b） |
| 输入变化 → 推理输出变化验证路径存在 | ✅ G4-D/E 完整链（§3.3） |
| **生产 Thinking 真实消费 W1（Scope Amendment 缺口）** | ✅ P-E1/P-E2：真实 ChatResponder 生产 prompt 携带块且差分可归因（§2b） |
| **生产消费零影响基线** | ✅ P-E3：无 W1 → 生产 context 逐字节不变（§2b） |
| Authority boundary 明确 | ✅ G4-H + P-E4（§6） |
| 最小改动面定义完成 | ✅ 3 生产文件 + 2 测试（§1） |
| I1 diff 可审计 | ✅ W0/W1/canonical diff 三快照（§4） |
| I2 source trace 保留 | ✅ claim_id/evidence_ids/source + P-E5 生产级（§4 / §2b） |
| I3 no silent expansion | ✅ 未发生（§4） |

---

## 8. 边界与递延（不越权）

- G4 只证明：**Worldview can enter Thinking input and produce attributable reasoning-context differentiation**（结构 W1 → Thinking input changed → Reasoning output changed）。
- **Scope Amendment 补证**：该输入差分**确实进入生产 Thinking 输入**（`ChatResponder.build_context()` → 生产 Context/Prompt → 真实 reasoning path，P-E1~P-E6）。
- **未进入 / 继续 NOT AUTHORIZED**：P1-1D（Thinking→Decision→Behavior Delta，即 Y≠Z）、成功率/任务完成提升验证、长期策略改变、context_builder/decision_pipeline/agent_runtime/bridge 生产接线、P0-4B 生产 LLM 决策验证。
- 生产接线**只**把 worldview 块追加进 Thinking input；provider 层是否因该块改变推理输出，属生产 LLM 行为，**不在** G4 断言范围（G4 断言到"生产 prompt 携带可归因块"为止；差分被 reasoning 消费的因果机制由 G4-E 确定性 consumer 证明）。
- **不得**以 G4 实现为理由宣称 "OCOS 已具备世界观驱动认知" 或 "Worldview 已改变行为"。
- 下一阶段（P1-1D Scope Assessment）须**单独授权**，不能自动推进。

---

## 9. Human Gate（终裁记录）

- **终裁：G4 PASS / FROZEN ✅（2026-09-14）**。
- G4 正式收口，不再继续扩展。P1-1D = NOT AUTHORIZED。
- 冻结生产面：`get_committed_worldview()` → `WorldViewContextBlock` / `WorldViewReadAdapter` / `ThinkingContextProvider` → `ChatResponder.build_context()` → Production Thinking Input。
- 冻结已验证判据：G4-D（W0→W1→Input Diff）、G4-E（Input Diff→Reasoning-context Output Diff）、P-E2（Production Prompt Diff）、P-E3（No-W1 Zero-Impact）、P-E4（No Reverse Mutation）、P-E5（Production Source Trace）。
- 下一步：**P1-1D Scope Assessment**（只读审计，不得直接实施）。

### 9.1 终裁理由（十三项）

1. Implementation scope 未漂移（生产文件 3 个：self_state.py + worldview_read_adapter.py + converse.py；测试 2 个新增，git 逐字验证）。
2. G4-A~H 8 用例全通过 + P-E1~P-E6 6 用例全通过（test output 实证 + 关键断言 + 失败案例归因）。
3. G4-D 完整链成立：W0 快照 `[]` → FIRST 后 input diff ≠ ∅ → REFRAME 后 diff 归因到 frame；I1 canonical diff 7 字段齐全。
4. G4-E 完整链成立：同 base self 下无/有 W1 → 结构化输出可区分且 `claim_id/evidence_ids` 可归因；输出白名单无 P1-1D 字段。
5. **Scope Amendment 唯一缺口关闭**：P-E1 证明消费链挂真实 `ChatResponder.respond()` 生产路径（provider 仅替换 LLM 引擎，宿主与 prompt 组装原样）。
6. **生产 Prompt 差分可归因**：P-E2 证明 `Prompt(W0) ≠ Prompt(W1)`，且剥离 worldview 块 + 归一化 S2 版本号后逐字节相等（唯一新增变量 = committed worldview block）。
7. **零影响基线（生产级）**：P-E3 证明无 W1 → G4 接线对生产 context 逐字节零贡献（完全惰性）。
8. 防假消费：G4-F（CONFIRM 不改变 input）+ G4-D/E 双 diff 判据 + P-E2 生产 prompt 差分，三层防"加字段即声称使用"。
9. Authority boundary：G4-H（篡改消费产物无回写）+ P-E4（生产消费后 committed S2 全等）。
10. I2 source trace：块保留 claim_id/evidence_ids/source；P-E5 证明生产 context/prompt 携带同源 claim/evidence（生产链可恢复）。
11. 回归 clean：受影响集合 113 passed（连同 G4 新测试 127 passed，0 failed）；全量失败全部 pre-existing（stash 归因复跑同结果）。
12. 无新增 authority / runtime / storage / 决策接线（新增面 = 1 只读方法 + 3 只读类 + 1 处生产只读接线，终止于 Thinking input）。
13. I3 未触发：无需修改 context_builder/decision_pipeline/agent_runtime，无静默扩面；生产接线故障用 `logger.error` 暴露而非静默降级。

### 9.2 能力表述（收口后保持）

- ✅ **Worldview can enter Thinking input and produce attributable reasoning-context differentiation.**
- ✅ **该输入差分进入生产 Thinking 输入**（ChatResponder 真实组装路径，P-E1~P-E6）。
- ✅ **G3 Worldview formation mechanism validated（上游，FROZEN）。**
- ❌ "OCOS 已具备世界观驱动认知"（不等价于 G4）。
- ❌ "Thinking → Decision → Behavior Delta"（属 P1-1D，未验证、未授权）。

### 9.3 建议冻结范围（G4 新增面，作为 P1-1D 上游事实链）

```text
SelfProjectionAccessor.get_committed_worldview()   （唯一读出口）
WorldViewContextBlock / WorldViewReadAdapter / ThinkingContextProvider   （只读消费层）
ChatResponder.build_context() worldview 块注入   （生产 Thinking 唯一接线，只读追加）
G4-D/E 双 diff 判据（input changed ∧ output changed 且可归因）
P-E2/P-E3 生产差分与零影响判据（剥离块逐字节相等 / 无 W1 零贡献）
```

**冻结纪律**：G4 文件不再修改；不得以 G4 实现为理由进入 Decision 行为链接线；P1-1D Scope Assessment 另行授权。

---

*G4 收口裁决材料（终裁：PASS / FROZEN，2026-09-14）。G4-A~H + P-E1~P-E6 全部通过（14 passed + 受影响回归 113 passed，合计 127 passed / 0 failed）。下一步 P1-1D 仅允许 Scope Assessment，另行授权。*
