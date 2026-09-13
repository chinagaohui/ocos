# OCOS P1-1 G3 — Worldview Recognition/Evidence/Delta Implementation Scope + Plan + Safety Audit

> 状态：**G3 GATE ACCEPTED → PLAN AMENDED（×2 修订稿）。G3 Implementation = 仍 NOT AUTHORIZED**。
> 承接：`OCOS_P1-1_G3_GATE_ASSESSMENT.md`（GATE ACCEPTED）；`G1_WORLDVIEW_SHAPE_DESIGN.md` §9；`WORLDVIEW_SEMANTIC_CONTRACT.md` §5/§6/§9（FROZEN）。
> §2 修订（上上版）→ 关闭：①核心阻断"调用方预制 Judgment"；②核心阻断"因果链不可持久审计"。
> 本次修订（相对前版）→ 关闭 4 个**间接伪造/假 Delta**阻断项：
> **A** W1≠W0 必须是 worldview 语义**结构变化**（judgment/frame/stance 至少一者变）；confidence/evidence/tick/version/continuity 单独不能构成 W1。
> **B** `occurrences` 必须 **derived/verified**，不得由 caller 作为可信计数。
> **C** `trigger_experience_id` 必须经 **真实 Experience provenance 验证**（存在/归属/证据关联），失败 fail-closed。
> **D** `divergence` 不再用 bool；由 `expected+actual` 经**确定性分类器**得到结构化 `divergence_kind`，REFRAME 依赖类别变化。
> 本文件回答：G3 实施改哪几处、Recognition 如何从真实经历真实产生、因果链如何持久可审计、如何防间接伪造与假 Delta。交 Human Gate 单独裁决 **G3 IMPLEMENTATION GO**。**不实现。**

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| 本 Plan（×2 修订稿） | ✅ 授权产出 |
| G3 Implementation | ❌ NOT AUTHORIZED（须本 Plan → Human Gate → 另行 GO） |
| 改 render / brief / thinking / decision / DecisionBridge / schema / migration | ❌ 禁止 |
| 第二套 Evidence / Memory / Governance | ❌ 禁止 |
| 做 Y≠Z / 进入 G4 / P1-1D | ❌ 禁止 |

---

## 1. Scope — 最小改动表面

| 文件 | 变更 | 性质 |
| --- | --- | --- |
| `ocos/self/self_types.py` | +`RecognitionType`（Enum）；`SelfUpdateContract` 增 2 个可选字段 `recognition_type: str=""`、`trigger_experience_id: str=""` | 增量，向后兼容（default 兜底，§3.4/§4） |
| `ocos/self/self_evidence.py` | +`WorldViewExperienceGate`；+`_classify_divergence`；+`WorldViewRecognitionRule`；recognize / delta_from_claim / apply_delta 增 worldview 分支；证据抽取守护 | 增量分支，缺省走既有逻辑 |
| `ocos/tests/test_p1_1_g3_worldview_pipeline.py`（新） | V 用例载体（含反伪造） | 测试 |

**明确不触碰（不因此新增生产模块）**：`worldview.py`、`self_state.py`（`RecognitionType` 不入 SelfModel；`SelfUpdateContract` 已在注册表）、schema/migrations、render/brief/context_builder/decision_pipeline/agent_runtime/converse/bridge、G1 已 FROZEN 的 5 文件。
**Experience 解析**：通过 **注入的 resolver 回调**访问既有 Experience/Memory 层（如 `S1Evidence` 快照与真实经历记录），**不新建 Experience 存储**。

---

## 2. 设计总则（含本次 4 项收口）

**复用既有五段链路，只喂 worldview 分支**，不建第二套管线。修正后的原则链：

```text
真实 Experience / Episode          ← 调用方只给候选事实观测
        ↓
Evidence extraction               ← 只提取事实；拒收预制判断（守护）
        ↓
Experience provenance gate        ← 解析 trigger_experience_id → 存在/归属/证据关联（C）
        ↓
occurrences derived/verified      ← 由真实经历事实计数，非 caller 可信计数（B）
        ↓
Recognition rules                 ← 由信号+当前 worldview 推导一切（含 R）
        ↓
_structural standpoint delta      ← expected+actual → divergence_kind（D）；识别类
        ↓
结构化 WorldViewJudgment（semantic structural change）  ← W1≠W0 结构门（A）
        ↓
SelfUpdateContract（recognition_type + trigger_experience_id）→ Govern → update_history（S2）
```

**四条硬性收口**：
1. **W1≠W0 = worldview 语义结构变化**：`judgment / frame / stance_type` 至少一者变化才算；`confidence↑、evidence_ids+、timestamp、version、continuity` **单独不构成 W1**（A）。
2. **occurrences 不可信 caller**：只作候选事实，必须由真实经历解析后 derived/verified，无法验证则 fail-closed（B）。
3. **trigger_experience_id 必过 provenance 门**：解析真实 Experience → 存在/归属/证据关联；任一失败则 NO Recognition / NO Delta / NO Commit（C）。
4. **divergence 结构化**：`expected+actual` → 确定性分类器 → `divergence_kind`（类别），REFRAME 依赖**类别改变**，不依赖 bool（D）。

---

## 3. 设计决策

### 3.1 `RecognitionType`（`self_types.py`）

```text
RecognitionType(Enum):
  CONFLICT      = "conflict"
  CONFIRM       = "confirm"
  NOVEL_PATTERN = "novel_pattern"
  REFRAME       = "reframe"
```

**不注册进 `_TYPE_REGISTRY`**：仅 pipeline 内部类型；持久化用其 `.value` 字符串（§3.4）。`self_state.py` 零改动。

### 3.2 Evidence 输入契约 —— 只提供候选事实（召回 C/B/D）

**第一红线**：输入**禁止**携带 `judgment / frame / stance_type / recognition_type`；**也禁止直接携带 `divergence` 布尔**（D）。
`capture/wv` 抽取守护：含任一预置判断/布尔 divergence ⇒ 抛 `SelfEvidenceError`。

合法输入只含**候选事实**（观测事实 + 一个不定长度的"可验证引用"，非可信结论）：

```text
wv.experience
  value      = episode 签名（事实事件，如 "tool-exit-not-as-expected"）
  meta (facts/candidates only)：
      domain            # 领域（dict key）                          【事实】
      expected          # 观测预期（如 "exit 0"）                   【事实】
      actual            # 观测实际（如 "exit 127"）                 【事实】
      trigger_episode   # X 的身份标识（候选 → 须 §3.3 解析验证）      【候选】
      occurrences_candidate  # 候选写法次数（不可信 → §3.3 推导）      【候选】非可信
```

**不进入输入**：`divergence`（由 classifier 派生，§3.6）、`occurrences`（由 gate 推导，§3.3）、`recognition_type`（规则推导）、`judgment/frame/stance`（规则生成）。

### 3.3 `WorldViewExperienceGate` —— trigger_experience_id 的 provenance 门（新增，C）

> 目的：把 "Experience 字符串关联" 提升为 "真实 Experience 验证"，杜绝 `trigger_episode="FAKE-001"` 直接进入 update_history。

```text
resolve(trigger_episode, current_identity) -> resolved_experience|null
  1. existence      — 在注入的 Experience resolver 中找到该 Episode
  2. ownership      — resolved.identity_ref == current.identity_ref（属于本 OCOS）
  3. evidence_link  — resolved 关联的 Evidence 与当前观测的 provenance（data_hash）匹配
任一步失败 → return None  → 调用方 fail-closed（无 Claim / 无 Delta / 无 commit）
```

- **职责**：`WorldViewExperienceGate(experience_resolver)`，resolver 由调用方注入（复用既有 Memory/Experience 层，不新建存储）。
- **occurrences derived（B）**：`occurrences = gate.count(resolved_experience)` —— 由该真实经历关联的观测计数得到，**非 caller 传入**。无法解析 → derived=0 → fail-closed。
- **测试注入**：已知真实 Experience 记录（pass）与 `FAKE-001`（fail-closed）对照。

### 3.4 `SelfUpdateContract` 持久字段（C 落库）

`SelfUpdateContract` 增 2 个可选字段（已核实：该类型已在 `_TYPE_REGISTRY`，`update_history` 直接存实例并经 `_to_canonical` 入 S2 JSON；缺省 default 兜底向后兼容）：

```text
trigger_experience_id: str = ""     # 仅当 §3.3 解析通过后写入（否则空 → 拒 delta）
recognition_type:       str = ""    # RecognitionType.value（"conflict"/"confirm"/... )
```

**持久可审计链**（committed 态可恢复）：
```text
update_history 该 contract：trigger_experience_id(=真经历锚) / recognition_type / evidence_ids / claim_id / reason
worldview 叶子：    continuity / evidence_ids / created_tick / last_updated_tick
```

### 3.5 `WorldViewRecognitionRule` —— 推导（D + B + R 来源）

```text
输入：W0(=current.worldview) + gate.resolved_experience + 事实(domain, expected, actual, derived_occurrences)
步骤：
1. 准入：先走 §3.3 gate；resolved 无 / derived_occurrences < _MIN_WV_OCCURRENCES(3) → fail-closed 不凝结。
2. divergence_kind = _classify_divergence(expected, actual)     # 确定性，§3.6
3. recognition_type（规则，非调用方）：
   - 无 prior domain 判断            → NOVEL_PATTERN
   - prior 且 divergence_kind 类别一致 → CONFIRM
   - prior 且 divergence_kind 与 old 框架方向相悖 → CONFLICT
   - prior 且 divergence_kind 类别改变（暴露不同组织框架）→ REFRAME      # 依赖类别，非 bool
4. stance_type：信号类别规则映射（divergence_kind 偏离 → normative/epistemic；稳定可归纳 → interpretive）
5. frame/judgment：规则从 domain + divergence_kind 参数化生成（锚定 trigger_experience_id）
6. confidence：由 derived_occurrences 折算；confirm 上调，conflict/reframe 保守
```

### 3.6 `_classify_divergence(expected, actual) -> divergence_kind`（D）

确定性分类器（同输入同输出，非 bool）：

```text
divergence_kind ∈ { none, type_mismatch, missing, unexpected_value, exceeds_bound, timing, ... }
例：
  expected="exit 0", actual="exit 127"     → unexpected_value（退出状态值不符）
  expected="file exists", actual="missing" → missing
  expected=actual                          → none（无差异 → 不触发 conflict/reframe 类）
```

- 决定语义：`REFRAME` 仅在 `divergence_kind`（类别）相对 prior 判断的框架发生**类别改变**时触发；`CONFIRM` 需类别一致。`none` 且有 prior 时视为 confirm；无 prior 且 `none` → 不凝结（无 distinguishable pattern，fail-closed F2）。
- 到 `stance_type` 的映射由分类器输出类别 + 规则表共同决定，非调用方注入。

### 3.7 `recognize()` 分支（增量）

```python
elif obs.key == "wv.experience":
    wv_claim = WorldViewRecognitionRule(gate, current).claim_from(obs)  # gate + rule = §3.3/3.5 全部推导
    if wv_claim is None:
        continue                        # 未过 gate/准入 → fail-closed
    kind, component = ClaimKind.WORLDVIEW_JUDGMENT, "worldview"
```

`SelfClaim`：`statement=judgment`、`key=domain`、`source` 按路径映射（§3.9 表）、`confidence=derived`。
`ClaimKind` 仅 +`WORLDVIEW_JUDGMENT`。`RecognitionType` 与 `trigger_episode`（已过门）暂存 `claim.meta`（供 contract，非持久终点）。

### 3.8 `delta_from_claim()` 分支 —— W1≠W0 语义结构门（A）

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = current.worldview; old = wv.get(domain) if wv else None
    # 结构门：W1≠W0 必须 judgment/frame/stance_type 至少一者变
    if old is not None and not _worldview_semantic_change(old, new):
        reject_delta()                              # 仅 confidence/evidence/tick 变 → 不产 W1 delta
    new = WorldViewJudgment(domain, judgment, ...,
          evidence_ids=(old.evidence_ids if old else ())+(evidence_id,),
          claim_id=..., created_tick=..., last_updated_tick=tick,
          continuity=_continuity_for(old, recognition_type),
          note=f"{reason} [recognition:{recognition_type.value}]")
    impact = _impact(...)

def _worldview_semantic_change(old, new) -> bool:
    if old is None: return True                     # FIRST 形成
    return not (new.judgment==old.judgment and new.frame==old.frame and new.stance_type==old.stance_type)
```

**判据升级**：`W1≠W0` = `_worldview_semantic_change()`，即 judgment/frame/stance **任一结构变化**。`confidence↑ / evidence_ids+ / timestamp / version / continuity` **不单独构成 W1**；因此 **CONFIRM 若仅置信/证据累积而无结构变化 → 不产 W1 Delta、不产生新 worldview mutation**（A / V 断言）。`new==old` 亦拒绝（无任何差异）。

### 3.9 `apply_delta()` 分支（增量）

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = candidate.worldview
    if wv is None: wv = WorldView(); candidate.worldview = wv
    wv.declare(delta.new_value)
```

#### Source 映射（复用，不新增枚举，契约 §12）

| 形成路径 | source |
| --- | --- |
| 实时经历冲突/观测 | `RUNTIME_OBSERVATION` |
| 事后反思重构 | `REFLECTION` |
| 记忆整合模式 | `MEMORY_CONSOLIDATION` |

均在 `allowed_update_sources` 白名单（自验证确认），Govern 门零改动。

#### 管线接 contract（§3.4 落库）

```python
contract = SelfUpdateContract(
    source=..., reason=claim.statement, tick_id=tick,
    fields_changed=("worldview",), evidence_ids=(evidence_id,), claim_id=claim.claim_id,
    trigger_experience_id=gate.resolved.id,           # 仅 gate 通过后（C）
    recognition_type=claim.meta["recognition_type"].value,
    confidence_impact=...)
```

---

## 4. Safety Audit

| 红线 / 风险 | 守卫 | 证据 |
| --- | --- | --- |
| 调用方预制 Judgment | 守护拒 `judgment/frame/stance/recognition_type`；judgment 必为规则对解析经历的函数 | §3.2 / §3.5 / V0 |
| **C 伪造 trigger**（`FAKE-001`→可审计链陷阱） | `WorldViewExperienceGate` 解析存在/归属/证据关联；失败 fail-closed | §3.3 / V-pg |
| **B 伪造 occurrences**（caller 改 3→100） | occurrences 由解析后真实经历 derived，非可信输入；无法验证 → 0 → fail-closed | §3.3 / V-oc |
| **A 假 Delta**（仅 confidence↑ 声称 W1≠W0） | `_worldview_semantic_change` 结构门；仅置信/证据/时间/版本/continuity 变 → 拒绝 | §3.8 / V-sg |
| **D REFRAME 无输入**（bool divergence→REFRAME） | `expected+actual`→`divergence_kind` 类别；REFRAME 仅类别改变触发 | §3.6 / V-dk |
| N7 无归因自省 | provenance 解析 + derived_occurrences≥阈值 + fail-closed | §3.3/§3.5 |
| N8 静态模板 | frame/judgment 为 domain+divergence_kind 参数化函数，锚定真经历 | §3.5/§3.6 |
| N6/F3 | Delta old/new 结构化 + 结构门；new==old 拒绝 | §3.8 / V-sg |
| 增量不改既有 | worldview 缺省 → 既有 3 kind 逻辑完全不变 | §3.7 并列分支 |
| 序列化 | `RecognitionType` 不入 SelfModel；`SelfUpdateContract` 新字段 default 兜底 | §3.1/§3.4 / V-reg |

**新增面**：`RecognitionType` 枚举、`ClaimKind.WORLDVIEW_JUDGMENT`、`WorldViewExperienceGate`、`_classify_divergence`、`WorldViewRecognitionRule`、`SelfUpdateContract` 2 可选字段、3 分支。无新 authority、无新 runtime、无新存储。

---

## 5. Verification（实现授权后执行）

> 载体：`ocos/tests/test_p1_1_g3_worldview_pipeline.py`。gate 用注入 resolver + 已知/伪造 Experience 记录对照。

| # | 用例 | 判据 |
| --- | --- | --- |
| V0 | 反预制 Judgment | 输入带 `judgment/frame/stance/recognition_type/divergence(bool)` → 守护 throw；或 fail-closed 不产 Delta |
| **V-pg** | **trigger provenance 门（C）** | `trigger_episode="FAKE-001"`（无法解析/归属不符/证据不匹配）→ 不产 Claim/Delta/commit；已知真实记录 → 通过 |
| **V-oc** | **occurrences derived（B）** | 输入 occurrences_candidate 不参与决策；真实经历串联观测计数 <3 → 不凝结；≥3 才凝结 |
| **V-sg** | **语义结构门（A）** | CONFIRM 仅 `confidence 0.70→0.82`/evidence+1/tick+1，judgment/frame/stance 未变 → **不产 W1 Delta**、worldview 无变化；结构变化（judgment/frame/stance 任一）→ 产 W1 |
| **V-dk** | **divergence 结构化（D）** | `expected+actual`→`divergence_kind` 确定性；REFRAME 仅在类别改变时触发；bool divergence 不被接受 |
| V1 | recognition 凝结 | 真实解析经历(≥3) → `recognize()` 产 claim，kind=WORLDVIEW_JUDGMENT，evidence_ids 非空 |
| V2 | judgment 由规则推导 | judgment/frame/stance_type/recognition_type 来自规则（对给定信号输出确定），非输入 meta |
| V3 | Delta A→B | old/new 为 WorldViewJudgment；结构未变 → 拒绝；new==old 拒绝 |
| V4 | continuity 映射 | novel→FIRST、confirm→DERIVED/保持、conflict→REVISED、reframe→REPLACED |
| V5 | Govern | EXTERNAL_AGENT 拒写；合法源可 commit；update_history 带 claim_id/evidence_ids |
| V6 | W1 落地 | apply 后 `candidate.worldview.get(domain)`==new；提交后 current 反映 new；round-trip 一致 |
| V7 | 因果链持久恢复 | commit 后 deserialize：末条 contract 含 `recognition_type`+`trigger_experience_id`(=真经历锚)；叶子含 continuity/evidence_ids；恢复 "X→R→W1" |
| V8 | 零影响回归 | 无 `wv.*` 旧场景 render/brief 逐字节不变；既有 3 kind 行为不变；`SelfUpdateContract` 新字段缺省向后兼容反序列化 |

**G3 PASS 门槛**：V0–V8 且含 V-pg/V-oc/V-sg/V-dk 全过；存在一条"真实解析经历归因的 claim+delta（recognition/trigger 可持久恢复）" + "W1≠W0 语义结构证明"。行为级 Y≠Z 不在 G3。

---

## 6. Non-Goals / 递延

G4（Thinking 消费）— 不接。P1-1D（X→D→Y）— 不跑。生产接线（converse/decision/DecisionBridge）— 不碰。schema/migration — 不碰。不新建 Experience 存储（复用 resolver）。

---

## 7. Human Gate

- 本文件 = **G3 Implementation Scope / Plan（×2 修订稿）+ Safety Audit**。**Implementation 仍 NOT AUTHORIZED。**
- Gate 裁决选项：**G3 IMPLEMENTATION GO** / **G3 PLAN AMENDED** / **G3 NO-GO**。
- 冻结纪律不变：实现授权前不修改任何生产文件。

---

*本文件为实施规格（×2 修订稿），非代码。等待 Human Gate 裁决。*