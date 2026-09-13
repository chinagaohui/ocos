# OCOS P1-1 G3 — Worldview Experience→Recognition→Delta→Govern→W1 实施验证报告

> 状态：**G3 IMPLEMENTATION COMPLETE — 提交 Human Gate 裁决（G3 PASS 候选，待终裁）**。
> 授权依据：`docs/OCOS_P1-1_G3_IMPLEMENTATION_PLAN.md`（×2 修订稿，Human Gate：**G3 IMPLEMENTATION GO**）。
> 承接已 FROZEN 的 `WORLDVIEW_SEMANTIC_CONTRACT.md`（§5/§6/§9）与 G1 Physical Seat（PASS/FROZEN）。
> 本报告为**收口裁决材料**，报告 G3 已落地内容与 V0–V8（含 V-pg/V-oc/V-sg/V-dk）验证证据，并逐项对照
> Human Gate 三条实现红线（H1 resolver 真实性 / H2 occurrences 无权威 / H3 真实结构 W1）。
>
> **EOD Read-only Audit 结论（2026-09-13）**：Scope 未漂移、H1/H2/H3 全部由测试证伪风险关闭、
> 回归全绿、lint 无新增 —— **建议提交 Human Gate：G3 PASS 候选**。剩余最后一步为 Human Gate 终裁。

---

## 0. 收口定位

```text
G3 Gate Assessment(ACCEPTED)
        ↓
G3 Implementation Plan ×2(ACCEPTED)
        ↓
G3 IMPLEMENTATION GO（Human Gate）
        ↓
G3 Implementation（本报告）
        ↓
G3 Verification V0–V8
        ↓
Human Gate: G3 PASS / FAIL        ← 当前所在步骤
```

**不越权声明**：G3 只证明 "OCOS 能因**真实经历**形成自己的 Worldview Delta（X→R→W1 可审计、可恢复）"。
本报告**不主张** "OCOS 已具备 Worldview formation capability（Accepted）"，更**不主张**行为已改变（Y≠Z）。
G4（Thinking 消费）、P1-1D（X→D→Y 行为 Delta）、Converse/DecisionBridge 接线、P0-4B **全部继续 NOT AUTHORIZED / FROZEN**。

---

## 1. 落地范围（严格对齐 G3_IMPLEMENTATION_PLAN §1）

| # | 文件 | 变更 | 状态 |
| --- | --- | --- | --- |
| 1 | `ocos/self/self_types.py` | +`RecognitionType`（Enum，4 值）；`SelfUpdateContract` +2 可选字段 `recognition_type: str=""`、`trigger_experience_id: str=""`（default 兜底向后兼容） | ✅ |
| 2 | `ocos/self/self_evidence.py` | +`WorldViewExperienceGate`（§3.3 H1）；+`_classify_divergence`（§3.6 D）；+`WorldViewRecognitionRule`（§3.5 B+C+R 全推导）；recognize/delta_from_claim/apply_delta 增 worldview 分支；`_worldview_semantic_change` 结构门（§3.8 A）；ingest 接入 resolver（fail-closed） | ✅ |
| 3 | `ocos/tests/test_p1_1_g3_worldview_pipeline.py`（新） | V0–V8 共 12 用例（含 V-pg/V-oc/V-sg/V-dk 四项反伪造） | ✅ |

**明确不触碰（确认未漂移）**：`worldview.py`、`self_state.py`（`RecognitionType` 不入 SelfModel 注册表；`SelfUpdateContract` 本已在注册表）、schema/migrations、render/brief/context_builder/decision_pipeline/agent_runtime/converse/bridge、G1 FROZEN 的 5 文件。
**未新建 Experience 存储**：真实经历经**注入的 resolver 回调**访问既有层（测试以 `_Episode/_Resolver` 模拟既有记录协议）。

**Git 变更集（`git status`）**：恰好 2 个生产文件修改 + 1 个新测试文件，无其他生产改动。

---

## 2. V0–V8 + H1–H3 验证证据

测试载体：`ocos/tests/test_p1_1_g3_worldview_pipeline.py`（12 用例）+ 针对性回归（§3）。

| # | 用例 | 断言基 | 结果 |
| --- | --- | --- | --- |
| V0 | 反预制 Judgment | 输入携带 `judgment/frame/stance_type/recognition_type/divergence(bool)` 任一项 → 守护抛 `SelfEvidenceError` | ✅ |
| **V-pg** | **trigger provenance 门（C/H1）** | FAKE-001 不存在 → 无 claim、ingest fail-closed；归属不符（other-agent）→ fail-closed；证据哈希不符 → fail-closed；真实记录（≥3 观测）→ 凝结 | ✅ |
| **V-oc** | **occurrences derived（B/H2）** | candidate=100/0/3 行为完全一致；真实经历=2（<3）→ 不凝结；derived occurrences=3 进 meta，`occurrences_candidate` 不进 meta | ✅ |
| **V-sg** | **语义结构门（A/H3）** | FIRST 形成 W0；CONFIRM 仅置信/证据/tick 变化 → 无 delta、版本不变、judgment/frame/stance 全等；REFRAME 类别改变 → 产 W1，continuity=REPLACED，三元组变化 | ✅ |
| **V-dk** | **divergence 结构化（D）** | `expected+actual` → 确定性 `divergence_kind`（unexpected_value/missing/exceeds_bound/falls_short/none）；REFRAME 仅类别改变触发；CONFLICT 同维反方向；CONFIRM 同类别同向；无 prior → NOVEL_PATTERN | ✅ |
| V1 | recognition 凝结 | 真实解析经历(≥3) → claim，kind=WORLDVIEW_JUDGMENT，evidence_ids 非空 | ✅ |
| V2 | judgment 由规则推导 | judgment/frame/stance_type/recognition_type 全部来自规则（非输入 meta）；`occurrences`=derived；candidate 不入 meta | ✅ |
| V3 | Delta A→B | old=None / new=WorldViewJudgment 结构化；apply 落 candidate.worldview | ✅ |
| V4 | continuity 映射 | novel→FIRST、confirm→DERIVED、conflict→REVISED、reframe→REPLACED | ✅ |
| V5 | Govern | 合法源（RUNTIME_OBSERVATION）commit 入 update_history；EXTERNAL_AGENT 拒写、版本不变 | ✅ |
| V6 | W1 落地 + round-trip | committed 态 worldview.get("tool") 为 WorldViewJudgment；reload 后 judgment/evidence_ids/continuity 一致 | ✅ |
| V7 | 因果链持久恢复 | reload 后末条 contract 含 `trigger_experience_id`(=EP-NOVEL 真锚) + `recognition_type`(novel_pattern) + evidence_ids/claim_id；叶子含 continuity/evidence_ids/claim_id/note → 恢复 "X→R→W1" | ✅ |
| V8 | 零影响回归 | 非 worldview 路径 contract 锚字段留空；SelfUpdateContract 新字段缺省向后兼容；无 worldview 的 manager 投影/序列化正常 | ✅ |

### 2.1 Human Gate 三条实现红线的测试证明

| 红线 | 测试 | 关键证据 |
| --- | --- | --- |
| **H1** resolver 不能成为"万能信任接口" | `test_vpg_provenance_gate_fails_closed` | `resolve()` 返回真实 Episode（存在/归属/证据哈希三重校验），**不是**按 ID 构造的包装；任一失败 → fail-closed（无 Claim/无 Delta/无 commit） |
| **H2** occurrences_candidate 完全无权威 | `test_voc_occurrences_derived_not_trusted` | candidate=100 / 0 / 3 → 同一行为、同一 derived occurrences=3；candidate 值不进 claim.meta（数据流上无权威字段） |
| **H3** G3 的 PASS 必须出现至少一次真正结构性 W1 | `test_vsg_semantic_structure_gate` | CONFIRM 仅 confidence/evidence/tick 变 → 不产 W1、版本不变；REFRAME → `(judgment, frame, stance_type)` 三元组变化 + continuity=REPLACED |

### 2.2 关键硬证据细节

- **H3 反假 Delta（用户点名最高优先级）**：W1≠W0 = `_worldview_semantic_change()`（[self_evidence.py](file:///workspace/ocos/self/self_evidence.py#L610-L619)），强制 `judgment/frame/stance_type` 至少一者变化；old=None（FIRST）视为结构变化。`confidence↑ / evidence_ids+ / tick / version / continuity` **单独不构成 W1** —— 测试证明 CONFIRM 路径 `m.version` 不变、worldview 叶子全等。
- **H1 三重 provenance 门（用户点名）**：`WorldViewExperienceGate.resolve()`（[self_evidence.py](file:///workspace/ocos/self/self_evidence.py#L220-L258)）校验 existence → ownership（identity_ref==current）→ evidence_link（data_hash 匹配）；`occurrences = gate.count(resolved)` 由真实经历关联观测派生（B）。
- **D 结构化 divergence（用户点名）**：`_classify_divergence()`（[self_evidence.py](file:///workspace/ocos/self/self_evidence.py#L261-L283)）确定性输出 `divergence_kind`，REFRAME 依赖**类别改变**（_DIV_FAMILY），不依赖 bool。
- **V7 因果链持久恢复（用户点名）**：`SelfUpdateContract` 新锚字段（[self_types.py](file:///workspace/ocos/self/self_types.py#L92-L99)）进 update_history；reload 后恢复 `X(trigger_experience_id) → R(recognition_type) → Claim/Evidence(claim_id/evidence_ids) → W1(叶子 continuity/evidence_ids/claim_id)` 完整链。

---

## 3. 回归与零破坏归因

### 3.1 G3 新测试 —— 12 passed

```text
ocos/tests/test_p1_1_g3_worldview_pipeline.py  …… 12 passed
```

### 3.2 受影响回归 —— 98 passed（全绿）

引用 `ocos.self` 全部受 G3 影响的测试集合：

```text
ocos/tests/test_p1_1_g3_worldview_pipeline.py   …… 12 passed  （G3 新）
ocos/tests/test_p1_1_g1_worldview_seat.py       …… 13 passed  （G1 governance）
ocos/tests/test_self_evidence_step2.py          …… 8  passed  （Evidence pipeline）
ocos/tests/test_self_state_step1.py             …… 8  passed  （S2 持久化）
ocos/tests/test_self_thinking_step3.py          …… 5  passed  （S2→Thinking，零消费）
ocos/tests/test_phase40.py                      …… 35 passed  （六组件回归）
ocos/tests/test_phase47_self_modification.py    …… 17 passed
合计：98 passed
```

证明 G3 未破坏：`SelfUpdateContract` / Govern / Evidence pipeline / S2 持久化 / Thinking 只读投影。

### 3.3 零影响与向后兼容（V8）

- **非 worldview 路径**：`capture_s1_snapshot` 既有 3 kind 逻辑走原路径，contract 的 `recognition_type`/`trigger_experience_id` 留空 —— 旧行为逐位不变。
- **旧 contract 反序列化**：新字段带 default 兜底，旧 update_history 可读（V8b 用例）。
- **无 worldview 的 manager**：投影/序列化正常（`worldview is None`）。
- **全量目录回归说明**：环境存在 pre-existing 阻塞测试（immune 周期调度）与 fastapi 缺失（collection error），G1 验证报告 §3.2/§3.3 已逐项 stash 归因为 pre-existing；G3 不触碰这些路径，受影响集合全绿即为零破坏证据。

### 3.4 Lint / Quality

```text
G3 引入：0 个 Ruff issue（E501 超长行 5 处 + self_types 新 docstring 超长均已修复）
剩余：N818（UnrecognizableEvidence）、E501（self_types.py:18）、W293（self_types.py:398）
归因：git stash + HEAD 验证 → 全部为改动前已存在，非本次引入，不阻塞 G3
```

---

## 4. 安全性审计结论（对照 G3_IMPLEMENTATION_PLAN §4）

| 红线 / 风险 | 状态 | 证据 |
| --- | --- | --- |
| 调用方预制 Judgment | ✅ 关闭 | 守护拒 `judgment/frame/stance/recognition_type/divergence(bool)`（V0） |
| **C 伪造 trigger**（FAKE-001→可审计链陷阱） | ✅ 关闭 | `WorldViewExperienceGate` 三重验证，失败 fail-closed（V-pg） |
| **B 伪造 occurrences**（caller 改 3→100） | ✅ 关闭 | occurrences 由真实经历 derived；candidate 数据流无权威（V-oc） |
| **A 假 Delta**（仅 confidence↑ 冒充 W1≠W0） | ✅ 关闭 | `_worldview_semantic_change` 结构门；CONFIRM 不产 W1（V-sg） |
| **D REFRAME 无输入**（bool divergence） | ✅ 关闭 | `_classify_divergence` 确定性类别；REFRAME 仅类别改变（V-dk） |
| N7 无归因自省 | ✅ | provenance 解析 + derived≥3 + fail-closed（V-pg/V-oc） |
| N8 静态模板 | ✅ 缓解 | frame/judgment 为 domain+divergence_kind 参数化规则函数，锚定真经历（V2 断言） |
| N6/F3 | ✅ | Delta old/new 结构化 + 结构门；CONFIRM 拒绝（V-sg/V3） |
| 增量不改既有 | ✅ | worldview 缺省 → 既有 3 kind 逻辑不变（V8a） |
| 序列化 | ✅ | `RecognitionType` 不入 SelfModel；新字段 default 兜底（V8b/V6 round-trip） |

**新增面核对**：`RecognitionType` 枚举、`ClaimKind.WORLDVIEW_JUDGMENT`、`WorldViewExperienceGate`、`_classify_divergence`、`WorldViewRecognitionRule`、`SelfUpdateContract` 2 可选字段、3 分支 —— **无新 authority、无新 runtime、无新存储**。

**权威链正确性**（H2 关闭的隐藏漏洞）：

```text
Experience
    ↓
Evidence（事实观测，拒预制判断）
    ↓
Derived statistics（occurrences，gate 派生）
    ↓
Recognition（规则推导 judgment/frame/stance/recognition_type）
    ↓
WorldView Claim → Delta → Govern → W1
```

---

## 5. G3 PASS Gate 前检查项（EOD Audit 清单复核）

| 项目 | 状态 |
| --- | --- |
| Plan scope 未漂移（仅 §1 授权 3 文件） | ✅ |
| H1 provenance（resolver 非万能信任接口） | ✅ |
| H2 occurrence authority（candidate 完全无权威） | ✅ |
| H3 semantic delta（W1≠W0 必须结构变化，且 PASS 路径出现至少一次真实结构 W1） | ✅ |
| Regression clean（受影响集合 98 passed + V8 向后兼容） | ✅ |

---

## 6. 边界与递延（不越权）

- G3 只证明 **WorldView Recognition/Evidence/Delta formation mechanism validated**（X→R→W1 可审计）。
- **未进入**：G4（WorldView→Thinking consumption，render/brief 接线）、P1-1D（X→D→Y 行为 Delta）、Converse/DecisionBridge、AgentRuntime、Decision Pipeline、P0-4B —— 全部维持 **NOT AUTHORIZED / FROZEN**。
- **不得**以 G3 实现为理由宣称 "OCOS 已获得 Worldview" 或 "Worldview 已改变行为"。
- 下一阶段（G4 Scope Assessment）须**单独授权**，不能自动推进。

---

## 7. Human Gate（收口）

- 本报告 = **G3 Implementation Evidence / Verification Report**。
- 建议裁决：**G3 PASS**（WorldView Recognition/Evidence/Delta formation mechanism validated）。
- 与 G1 一致的能力表述纪律：
  - ❌ "OCOS 已获得 Worldview formation capability"（capability 未被 Gate Accepted）
  - ✅ "G3 Implementation 已完成，并通过 V0–V8 设计约束测试证明具备进入 Worldview formation capability 验收阶段的条件"
- 冻结纪律不变：实现授权范围内文件可继续审计，但 G4/P1-1D/schema/接线**仍禁止**。

---

*本报告为 G3 收口裁决材料。G3 实现 + V0–V8 验证已完成，等待 Human Gate 终裁。*
