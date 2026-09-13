# OCOS P1-1 G3 — Worldview Recognition/Evidence/Delta Implementation Scope + Plan + Safety Audit

> 状态：**G3 GATE ACCEPTED → PLAN AMENDED（本版为修订稿）。G3 Implementation = 仍 NOT AUTHORIZED**。
> 承接：`OCOS_P1-1_G3_GATE_ASSESSMENT.md`（GATE ACCEPTED）；`G1_WORLDVIEW_SHAPE_DESIGN.md` §9；`WORLDVIEW_SEMANTIC_CONTRACT.md` §5/§6/§9（FROZEN）。
> 修订点（本版相对前一版）：① Evidence 输入**只给事实/结构化经历信号**，judgment/frame/stance 一律由 G3 Recognition 规则推导，调用方不得预制；② `recognition_type` 与 `trigger_experience_id` 走 `SelfUpdateContract` 进入 `update_history`，形成**可审计持久链**；③ 新增**反伪造测试**。
> 本文件回答：G3 实施改哪几处、Recognition 如何从真实经历真实产生、因果链如何持久可审计。交 Human Gate 单独裁决 **G3 IMPLEMENTATION GO**。**不实现。**

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| 本 Plan（修订稿） | ✅ 授权产出 |
| G3 Implementation | ❌ NOT AUTHORIZED（须本 Plan → Human Gate → 另行 GO） |
| 改 render / brief / thinking / decision / DecisionBridge / schema / migration | ❌ 禁止 |
| 第二套 Evidence / Memory / Governance | ❌ 禁止 |
| 做 Y≠Z / 进入 G4 / P1-1D | ❌ 禁止 |

---

## 1. Scope — 最小改动表面

| 文件 | 变更 | 性质 |
| --- | --- | --- |
| `ocos/self/self_types.py` | +`RecognitionType`（Enum）；`SelfUpdateContract` 增 2 个可选字段 `recognition_type: str = ""`、`trigger_experience_id: str = ""` | 增量，向后兼容（default 兜底，见 §3.7 / §4） |
| `ocos/self/self_evidence.py` | 新 `WorldViewRecognitionRule`；recognize / delta_from_claim / apply_delta 增 worldview 分支；`capital` 侧证据抽取守护 | 增量分支，缺省走既有逻辑 |
| `ocos/tests/test_p1_1_g3_worldview_pipeline.py`（新） | V0–V8 用例载体 | 测试 |

**明确不触碰**：`worldview.py`（`declare/get` 已够）、`self_state.py`（`RecognitionType` 不入 SelfModel；`SelfUpdateContract` 已在注册表，零改动）、schema/migrations、render/brief/context_builder/decision_pipeline/agent_runtime/converse/bridge、G1 已 FROZEN 的 5 文件不再动。

---

## 2. 设计总则

**复用既有五段链路，只喂 worldview 分支**，不建第二套管线。修正后的原则链（对齐裁决 §"必须修订成这个原则"）：

```text
真实 Experience / Episode          ← 调用方只给真实经历的事实观测
        ↓
Evidence extraction               ← 只提取事实信号；拒收预制判断（守护）
        ↓
Recognition rules                 ← G3 内：由信号 + 当前 worldview 推导一切
        ↓                             - recognition_type（信号 vs 现有判断对比）
        ↓                             - stance_type / frame / judgment（规则参数化推导）
        ↓
结构化 WorldViewJudgment
        ↓
W0 → W1 Delta（old/new 结构化）
        ↓
SelfUpdateContract（recognition_type + trigger_experience_id）
        ↓
Govern
        ↓
持久化（update_history → S2 JSON，可审计恢复）
```

**两条信条（本次修订强化）**：
1. **判断必须由 Recognition 从真实经历产生，不允许调用方直接提供最终 Judgment**（裁决 + 契约 P2/N7/N8）。调用方只能提供事实。
2. **因果链必须持久可审计**：`recognition_type` + `trigger_experience_id` 必须能在 committed 状态中恢复，而非仅存在于运行期 `claim.meta`（契约 §5 / §9）。

---

## 3. 设计决策

### 3.1 `RecognitionType`（`self_types.py`）

```text
RecognitionType(Enum):
  CONFLICT      = "conflict"        # 经历与既有理解冲突 → REVISED
  CONFIRM       = "confirm"         # 经历强化既有理解 → 置信↑ / DERIVED
  NOVEL_PATTERN = "novel_pattern"   # 新领域/新范式 → FIRST
  REFRAME       = "reframe"         # 重构既有框架 → REPLACED/DERIVED
```

**Registered？否**：`RecognitionType` 只出现在 pipeline 的类型化逻辑中；持久化时以 `str`（`.value`）写入
`SelfUpdateContract.recognition_type`（见 §3.7）。**不入 `_TYPE_REGISTRY`，`self_state.py` 零改动。**

### 3.2 Evidence 输入契约 —— 只提供事实（修订核心）

**第一红线（修订核心）：输入里禁止出现 judgment/frame/stance_type/recognition_type。**

`capture/wv` 侧抽取守护：若输入的 `wv.experience` meta 含 `judgment / frame / stance_type / recognition_type`
任一预置判断字段 ⇒ **抛 `SelfEvidenceError`**（"recognition must derive from experience, not pre-fabricated"）。

合法输入只含**事实信号**（观测事实，非判断）：

```text
wv.experience
  value      = episode 签名（如 "tool-exit-not-as-expected"）        # 事实事件
  meta (facts only)：
      domain            # 领域（dict key，同 judgment.domain）      【事实】
      expected          # 经历中观察到的预期（如 "exit 0"）          【事实】
      actual            # 经历中观察到的实际（如 "exit 127"）        【事实】
      divergence        # expected≠actual 的差异（布尔，由观测判定）  【事实】
      occurrences       # 该模式出现次数（≥阈值才可凝结）             【事实】
      trigger_episode   # 真实经历锚（X 的身份标识）                  【事实】
```

**为什么这样定**：`Recognition` 从"预期 vs 实际"的差异信号推导 `recognition_type` 与 stance，再从
"domain + divergence + occurrences" 参数化生成 frame/judgment——判断内容永远是**真实经历过的事实的函数**，
调用方无法直接注入最终判断（裁决 gap-1）。真实经历 X 的取值由调用方基于真实 S1 观测填充，G3 不编造经历。

### 3.3 `WorldViewRecognitionRule` —— Judgment/Frame/RecognitionType 的推导（修订核心，`self_evidence.py` 新增）

```text
输入：current.worldview（W0）+ 事实信号（domain, expected, actual, divergence, occurrences, trigger_episode）
步骤：
1. 准入：occurrences 低于 _MIN_WV_OCCURRENCES（如 3）→ 不凝结（守 P2/小样本自信）。
        divergence / trigger_episode 缺失 → 不凝结。
2. recognition_type（规则对比，非调用方提供）：
     no prior domain judgment          → NOVEL_PATTERN
     prior 存在且 new_divergence 与 old 一致 → CONFIRM
     prior 存在且 new_divergence 与 old 相悖 → CONFLICT
     新模式暴露不同组织框架(divergence 类别改变) → REFRAME
3. stance_type（按信号类别规则映射）：
     divergence=true（环境偏离预期）   → normative（"先验证而非信任"）或 epistemic（由规则选定）
     稳定可归纳模式                   → interpretive
     （规则给确定映射，非调用方输入）
4. frame/judgment（由规则从 domain + divergence + occurrences 参数化生成，非通用常量）：
     frame = "在这类 {domain} 场景，观测可能偏离预期（模式={divergence}）"
     judgment = 基于 {domain} 与所述 divergence 的组织化立场（引用具体领域，锚定证据）
5. confidence：由 occurrences 折算；confirm 上调，conflict/reframe 保守。
```

**真实性保障（抗 N8/N4）**：frame/judgment 是 **领域 + divergence 参数的确定性函数**，且必须锚定
`trigger_episode` + occurrences≥阈值。识别法则本身是 G3 组件的能力，不是调用方塞入的字符串；
规则输入的每一份信号均溯到真实经历事实。若某输入**没有可区分的事实模式**（divergence 中性、occurrences=0），
则 `fail-closed`：不凝结、不产 delta（守 F2）。

### 3.4 `recognize()` 分支（增量）

在既有 kind 循环**并列**追加，不改既有 3 类逻辑：

```python
elif obs.key == "wv.experience":
    wv_claim = WorldViewRecognitionRule(current).claim_from(obs)   # 内部完成 3.3 全部推导
    if wv_claim is None:  # 未过准入/fail-closed
        continue
    kind, component = ClaimKind.WORLDVIEW_JUDGMENT, "worldview"
```

`SelfClaim`：`statement=wv_claim.judgment`，`key=wv_claim.domain`，`source` 按形成路径映射（§3.7 表），
`confidence=wv_claim.confidence`。`ClaimKind` 仅 +`WORLDVIEW_JUDGMENT = "worldview_judgment"`（只加 1 个成员；
识别种类由 `RecognitionType` 承载）。`RecognitionType` 与 `trigger_episode` 暂存于 `claim.meta`（**供 pipeline 传入 contract，非持久终点**）。

### 3.5 `delta_from_claim()` 分支

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = current.worldview
    old = wv.get(domain) if wv else None
    new = WorldViewJudgment(
        domain, judgment, stance_type, frame,
        confidence=...,
        evidence_ids=(old.evidence_ids if old else ()) + (evidence_id,),   # 累计归因
        source=...,
        claim_id=claim.claim_id,
        created_tick=old.created_tick if old else tick,
        last_updated_tick=tick,
        continuity=_continuity_for(old, recognition_type),                 # §3.3/step2 映射
        note=f"{reason} [recognition:{recognition_type.value}]",
    )
    impact = _impact(old, new, recognition_type)
```

**连续性映射（V4）**：

| old 存在 | recognition_type | continuity |
| --- | --- | --- |
| 无 | NOVEL_PATTERN / 任意 | FIRST |
| 有 | CONFIRM | DERIVED（或保持连续性 + 置信↑） |
| 有 | CONFLICT | REVISED |
| 有 | REFRAME | REPLACED |

**W1≠W0 判据**：`old is None` 或 `new != old`（dataclass 结构化相等）；`new == old ⇒ 不产 delta`（守 F3）。

### 3.6 `apply_delta()` 分支

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = candidate.worldview
    if wv is None:
        wv = WorldView(); candidate.worldview = wv
    wv.declare(delta.new_value)
```

复用 `declare`（Revision 语义由 new 的 continuity 表达，与 KnowledgeBoundary 一致）。

### 3.7 因果链持久化（本次修订核心，契约 §5/§9）

**结论：`recognition_type` 与 `trigger_experience_id` 通过 `SelfUpdateContract` 进入 `update_history`，随 S2 JSON 持久；`continuity` 通过 `WorldViewJudgment` 叶子持久。**

`SelfUpdateContract` 增 2 个可选字段：

```text
trigger_experience_id: str = ""   # X 的真实经历锚（= S1Evidence 的 trigger_episode）
recognition_type:       str = ""  # RecognitionType.value（"conflict"/"confirm"/"novel_pattern"/"reframe"）
```

管线生成 contract 时（对齐 Shape Design §9 / self_evidence.py 现有 ingest 逻辑）：

```python
contract = SelfUpdateContract(
    source=..., reason=claim.statement, tick_id=tick,
    fields_changed=("worldview",),
    evidence_ids=(evidence_id,),
    claim_id=claim.claim_id,
    trigger_experience_id=claim.meta["trigger_episode"],   # 新增：X 锚
    recognition_type=claim.meta["recognition_type"].value, # 新增：R
    confidence_impact=...,
)
```

**持久可审计链（committed 状态可恢复）**：

```text
update_history 中该 contract：
   trigger_experience_id  → X（真实经历锚）
   recognition_type       → R（conflict/confirm/novel/reframe）
   evidence_ids           → Evidence
   claim_id               → Claim
   reason                 → 判断理由
judgments[domain]（worldview 叶子）：
   continuity             → FIRST/DERIVED/REVISED/REPLACED
   evidence_ids / created_tick / last_updated_tick → 时间线
```

⇒ 审计者可从持久态**恢复 "X → Recognition(R) → W1（continuity）" 完整因果**，不再仅见 `W0→W1`。
`RecognitionType` 枚举本身仍为 pipeline 内部类型（不进入 SelfModel 序列化），持久化的是其 `.value` 字符串。

### 3.8 Source 映射（复用，不新增枚举，契约 §12）

| 形成路径 | source | 对齐 |
| --- | --- | --- |
| 实时经历冲突/观测 | `RUNTIME_OBSERVATION` | 与 failure/capability 同源 |
| 事后反思重构 | `REFLECTION` | 自归洞察 |
| 记忆整合模式 | `MEMORY_CONSOLIDATION` | 跨经历归纳 |

均在 `allowed_update_sources` 白名单（自验证确认），Govern 门零改动。

---

## 4. Safety Audit

| 红线 / 风险 | 守卫 | 证据 |
| --- | --- | --- |
| **gap-1：调用方预制 Judgment** | 证据抽取守护拒收 `judgment/frame/stance_type/recognition_type`；judgment 必为 Recognition 规则对事实信号的函数 | §3.2 / §3.3 / V0 |
| **gap-2：因果链不可审计** | `recognition_type`+`trigger_experience_id` 走 contract → update_history → S2 JSON | §3.7 / V7 |
| N7 无归因自省 | occurrences≥阈值 + trigger_episode 非空 + fail-closed | §3.3 |
| N8 静态模板 | frame/judgment 为 domain+divergence 参数化函数，锚定 trigger_episode，fail-closed | §3.3 |
| N6/F3 version+1 冒充 | Delta old/new 结构化相等；new==old 拒绝 | §3.5 / V3 |
| N3 WorldStore 直写 | 输入须真实经历事实，非外部地图计数 | §3.2 |
| 增量不改既有 | worldview 缺省 → 既有 3 kind 逻辑完全不变 | §3.4 并列分支 |
| 序列化 | 不含新序列化类型入 SelfModel ⇒ Registry 不变；contract 新字段 default 兜底向后兼容 | §3.1 / §3.7 / V8 |

**新增面**：`RecognitionType` 枚举 + `ClaimKind.WORLDVIEW_JUDGMENT` + `WorldViewRecognitionRule` + `SelfUpdateContract` 2 个可选字段 + 3 个分支。无新 authority、无新 runtime。

---

## 5. Verification（V0–V8，实现授权后执行）

> **V0 = 反伪造测试（本次修订新增，对应裁决要点 5）。**
> 载体：`ocos/tests/test_p1_1_g3_worldview_pipeline.py`。

| # | 用例 | 断言 |
| --- | --- | --- |
| **V0** | **反伪造**：仅试图注入预制 judgment/frame/stance/recognition_type 而无对应真实 Evidence（divergence 中性 / 无 trigger_episode / occurrences=0） | 证据抽取守护 throw（预置字段被拒）；或 Recognition fail-closed → **不产任何 WorldView Delta**；committed.worldview 不变 |
| V1 | recognition 凝结 | 给真实经历事实（domain/expected/actual/divergence/occurrences/trigger）→ `recognize()` 产出 claim，kind=WORLDVIEW_JUDGMENT，evidence_ids 非空 |
| V2 | judgment 由规则推导 | claim 的 judgment/frame/stance_type/recognition_type **来自 Recognition 规则**（对给定事实信号输出确定），而非输入 meta |
| V3 | Delta A→B 结构化 | old/new 为 WorldViewJudgment；new≠old 才产 delta；new==old → 拒绝 |
| V4 | continuity 映射 | 表驱动：novel→FIRST、confirm→DERIVED、conflict→REVISED、reframe→REPLACED |
| V5 | Govern | EXTERNAL_AGENT 拒写；合法 RUNTIME_OBSERVATION/REFLECTION 可 commit；update_history 带 claim_id/evidence_ids |
| V6 | W1 落地 | apply 后 `candidate.worldview.get(domain)`==new_value；ingest 提交后 `current.worldview` 反映 new；round-trip 一致 |
| **V7** | **因果链持久恢复** | commit 后：deserialize 的 `update_history` 末条 contract 含 `recognition_type` + `trigger_experience_id`（=真经历锚）；judgment 叶子含 `continuity` + `evidence_ids`；可恢复 "X→R→W1" |
| V8 | 零影响回归 | 不含 `wv.*` 观测的旧场景：render/brief 逐字节不变；既有 recognize 3 kind 行为不变；含历史 test update_history 反序列化向后兼容（新字段缺省兜底） |

**G3 PASS 门槛**：V0–V8 全过，且存在一条"经历归因的 claim + delta（带 evidence，recognition/trigger 可持久恢复）" + "W1≠W0 结构性证明"。行为级 Y≠Z 不在 G3。

---

## 6. Non-Goals / 递延

G4（Thinking 消费：render/brief 文本投影 + 实际读取点）— 不接。P1-1D（X→D→Y）— 不跑。
生产接线（converse/decision/DecisionBridge）— 不碰。schema/migration — 不碰。

---

## 7. Human Gate

- 本文件 = **G3 Implementation Scope / Plan（修订稿）+ Safety Audit**。**Implementation 仍 NOT AUTHORIZED。**
- Gate 裁决选项：
  - **G3 IMPLEMENTATION GO** → 授权落地（2 生产文件 + 1 测试文件 + V0–V8）；
  - **G3 PLAN AMENDED** → 返回修订设计；
  - **G3 NO-GO** → P1-1 停在 G1 PASS。
- 冻结纪律不变：实现授权前不修改任何生产文件。

---

*本文件为实施规格（修订稿），非代码。等待 Human Gate 裁决。*