# OCOS P1-1 G3 — WorldView Recognition/Evidence/Delta Implementation Scope + Plan + Safety Audit

> 状态：**G3 GATE ACCEPTED（设计授权）；G3 Implementation = 仍 NOT AUTHORIZED**。
> 承接：`OCOS_P1-1_G3_GATE_ASSESSMENT.md`（GATE ACCEPTED）；`OCOS_P1-1_G1_WORLDVIEW_SHAPE_DESIGN.md` §9（扩展点注记）；`OCOS_P1-1_WORLDVIEW_SEMANTIC_CONTRACT.md` §5/§6/§9（FROZEN）。
> 本文件回答：**G3 实施到底改哪几个文件、每个函数怎么改、怎么保证安全最小**，交 Human Gate 单独裁决 **G3 IMPLEMENTATION GO**。**不实现。**

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| 本 Plan（G3 Implementation Scope/Plan） | ✅ 授权产出（本文件） |
| G3 Implementation | ❌ NOT AUTHORIZED（须本 Plan → Human Gate → 另行 GO） |
| 改 render / brief / thinking / decision / DecisionBridge / schema / migration | ❌ 禁止 |
| 第二套 Evidence / Memory / Governance | ❌ 禁止 |
| 做 Y≠Z / 进入 G4 / P1-1D | ❌ 禁止 |

---

## 1. Scope — 最小改动表面（仅 1 生产文件 + 1 测试文件）

| 文件 | 变更 | 性质 |
| --- | --- | --- |
| `ocos/self/self_types.py` | +`RecognitionType`（Enum） | 增量，无行为影响 |
| `ocos/self/self_evidence.py` | recognize / delta_from_claim / apply_delta 新增 worldview 分支 | 增量分支，缺省走既有逻辑 |
| `ocos/tests/test_p1_1_g3_worldview_pipeline.py`（新） | V1–V8 用例载体 | 测试 |

**明确不触碰**：`worldview.py`（容器已够用，`declare/get` 已建模 revision）、`self_state.py`（注册表已含 4 类型；`RecognitionType` 是否注册见 §3.1）、schema/migrations、render/brief/context_builder/decision_pipeline/agent_runtime/converse/bridge、G1 已 FROZEN 的 5 文件不再动。

---

## 2. 设计总则

**复用既有五段链路，只喂 worldview 分支**，不建第二套管线。贯彻原则（对齐 Shape Design §2 组件模式 + §9）：

```text
Evidence(S1Evidence) → recognize() → SelfClaim(kind=WORLDVIEW_*) 
  → delta_from_claim() → SelfDelta(old/new = WorldViewJudgment)
  → apply_delta() → candidate.worldview.declare(new)
  → SelfEvidencePipeline.ingest() → governed commit（复用，零改动）
```

**两条信条**：
1. **形成靠真实经历归因**（契约 P2/N7）：judgment/frame 的**内容信号来自 Evidence 的结构化观测**，
   识别法则只裁决"何时/how 凝结 + 差分 + 连续性 + 置信"，**不凭空生成判断内容**（守 N8 模板 / N4 prompt）。
2. **W1≠W0 必须结构化**（契约 §5/§11 F3）：Delta old/new 为 `WorldViewJudgment` 对象差分，拒绝仅 version+1。

---

## 3. 设计决策

### 3.1 `RecognitionType`（`self_types.py`，契约 §5 recognition_type）

```text
@dataclass ? 否 —— 用 Enum：
RecognitionType(Enum):
  CONFLICT     = "conflict"        # 经历与既有理解冲突 → 触发修订/替换
  CONFIRM      = "confirm"         # 经历强化既有理解 → 置信上调（continuity 不变或 DERIVED）
  NOVEL_PATTERN= "novel_pattern"   # 新范式/新领域 → 首次形成（FIRST）
  REFRAME      = "reframe"         # 重构既有框架 → REPLACED/DERIVED
```

**登记与否**：`RecognitionType` 只出现在 **S1Evidence → claim 的内存映射**，不进入 SelfModel/序列化
（judgment 里的语义是 `continuity`，而 continuity 已有注册）。故 **不注册进 `_TYPE_REGISTRY`**，
`self_state.py` 零改动。→ 用 `self_types.py` 放枚举仅为集中枚举定义（与 StanceType/ContinuityKind 同文件物聚）。

### 3.2 Evidence 观测扩展（识别喂料，`self_evidence.py`）

`capture_s1_snapshot` 现状只抽 `s1.capability` / `s1.failure_mode`。**G3 增加一条观测 key**：

```text
wv.experience
  value       = episode 签名（如 "env-mismatch:tool_exit_not_expected"）
  meta        = {
      domain,              # 所属领域（dict key，同 WorldViewJudgment.domain）
      judgment,            # 结构化判断内容（经历归因，非 prompt）→ judgment
      frame,               # 框架描述 → frame
      stance_type,         # interpretive / normative / epistemic
      recognition_type,    # conflict/confirm/novel_pattern/reframe
      strength,            # 经历强度（驱动置信）
      trigger_episode,     # 真实经历锚 → evidence_ids
  }
```

**守卫**：`evidence_ids` / `trigger_episode` 为空 ⇒ 不 emit（守 N7）；`strength` 低 ⇒ 不凝结。
真实经历 X 的值由**调用方（未来 P1-1D harness）基于真实 S1 观测填充**，G3 不编造经历。

### 3.3 `recognize()` 分支（增量）

在既有 kind 循环**并列**追加，不改既有 3 类逻辑：

```python
elif obs.key == "wv.experience":
    kind, component = ClaimKind.WORLDVIEW_JUDGMENT, "worldview"
    # 准入门槛：有 trigger_episode + strength 达标
```

`SelfClaim` 复用：`statement=meta["judgment"]`，`key=meta["domain"]`，`source` 按形成路径映射（见 §3.5），
`confidence` 由 `strength` 折算。`ClaimKind` 仅 +`WORLDVIEW_JUDGMENT = "worldview_judgment"`（**只加 1 个成员**，
识别"种类"由 `RecognitionType` 承载，不拆 4 个 kind，避免枚举膨胀）。

`RecognitionType` 暂存于 claim：为不改 `SelfClaim` 结构，将 `recognition_type` 放进 `claim.meta`。

### 3.4 `delta_from_claim()` 分支

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = current.worldview
    old = wv.get(domain) if wv else None                 # A：现有 judgment（或无）
    old_ct = old.continuity if old else CONTINUITY 无      # 推导 continuity
    new = WorldViewJudgment(
        domain, judgment, stance_type, frame,
        confidence=...,                      # old 存在则融合；否则由 strength
        evidence_ids=old.evidence_ids + (evidence_id,),  # 累计归因（契约 §3.3）
        source=...,
        claim_id=claim.claim_id,
        created_tick=(old.created_tick if old else tick),
        last_updated_tick=tick,
        continuity=_continuity_for(old, recognition_type),  # FIRST/DERIVED/REVISED/REPLACED
        note=reason,
    )
    impact = _impact(old, new, recognition_type)  # confirm≤0 / conflict/reframe 保守小量
```

**连续性推导（V4 焦点）**：

| old 存在 | recognition_type | continuity |
| --- | --- | --- |
| 无 | NOVEL_PATTERN / 任意 | FIRST |
| 有 | CONFIRM | DERIVED（或保持原 continuity + 置信↑） |
| 有 | CONFLICT | REVISED |
| 有 | REFRAME | REPLACED |

**W1≠W0 判据**：`old is None` 或 `new != old`（dataclass 结构化相等，非文本 diff）；`new == old ⇒ 不产 delta`（守 F3）。

### 3.5 `apply_delta()` 分支

```python
elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
    wv = candidate.worldview
    if wv is None:
        wv = WorldView()
        candidate.worldview = wv
    wv.declare(delta.new_value)
```

复用 `declare`（容器哑操作，revision 语义由 new 的 continuity 表达，保持与 KnowledgeBoundary 一致）。

### 3.6 Source 映射（复用，不新增枚举，契约 §12）

| 形成路径 | source | 对齐 |
| --- | --- | --- |
| 实时经历冲突/观测 | `RUNTIME_OBSERVATION` | 与 failure/capability 同源 |
| 事后反思重构 | `REFLECTION` | 自归洞察 |
| 记忆整合模式 | `MEMORY_CONSOLIDATION` | 跨经历归纳 |

均在 `allowed_update_sources` 白名单内（自验证已确认），Govern 门零改动。

### 3.7 治理与 commit（零改动）

复用 `SelfEvidencePipeline.ingest()`：`SelfUpdateContract(fields_changed=("worldview",), evidence_ids=(...), claim_id=...)` →
`commit_change` → update_history 入账。`component_consumption("worldview")` 自动可归因（G1 已建）。EXTERNAL_AGENT 拒写（G1 T5 已证，G3 沿用）。

---

## 4. Safety Audit（对比契约红线与 V 矩阵）

| 红线 / 风险 | 守卫 | 证据 |
| --- | --- | --- |
| N8 模板 / N4 prompt | judgment/frame 来自 Evidence 结构化信号，识别只裁决凝结；不含凭空文本生成 | §3.2 守卫 |
| N7 无归因自省 | evidence_ids/trigger_episode 非空才 emit | §3.2/§3.3 |
| N3 WorldStore 直写 | 喂料须为真实经历观测，非外部地图计数 | §3.2 |
| N6 version+1 冒充 | Delta old/new 结构化相等等差；new==old 拒绝 | §3.4 |
| F3 | 同上 + 结构性差分断言 | V3 |
| 回归环境影响 | 增量分支：worldview 缺省 → 既有 3 kind 逻辑完全不变 | §3.3 并列分支 |
| 序列化 | 不含新序列化类型入 SelfModel ⇒ Registry 不变 | §3.1 |
| 零行为影响 | 不触 render/brief/thinking/decision | Scope |

**新增结构面**：仅 `RecognitionType` 枚举 + 1 个 `ClaimKind` 成员 + 3 个分支；无新 authority、无新 runtime。

---

## 5. Verification（V1–V8 用例，实现授权后执行）

载体：`ocos/tests/test_p1_1_g3_worldview_pipeline.py`。

| # | 用例 | 断言 |
| --- | --- | --- |
| V1 | recognition 凝结 | 给真实经历 `wv.experience` Evidence → `recognize()` 产出 claim，kind=WORLDVIEW_JUDGMENT，evidence_ids 非空、可归因 |
| V2 | 无归因拒绝 | 无 trigger_episode / 低 strength → 不产 worldview 凝结（守 N7） |
| V3 | Delta A→B 结构化 | old/new 为 WorldViewJudgment；new≠old 才产 delta；new==old → 拒绝（守 F3） |
| V4 | continuity 映射 | 表驱动：novel→FIRST、confirm→DERIVED、conflict→REVISED、reframe→REPLACED |
| V5 | Govern | EXTERNAL_AGENT 拒写；合法 RUNTIME_OBSERVATION/REFLECTION 可 commit；update_history 带 claim_id/evidence_ids |
| V6 | W1 落地 | apply 后 `candidate.worldview.get(domain)` == new_value；ingest 提交后 `current.worldview` 反映 new；round-trip 一致 |
| V7 | 零影响回归 | 不含 `wv.*` 观测的旧场景：render/brief 逐字节不变（延续 T6b）；既有 recognize 3 kind 行为不变 |
| V8 | 全量回归 | 受影响集合全绿；pre-existing failures 以 git-stash 反事实验证排除 |

**G3 PASS 门槛**：V1–V8 全过，且存在一条"经历归因的 claim + delta（带 evidence）" + "W1≠W0 结构性证明"。行为级 Y≠Z 不在 G3。

---

## 6. Non-Goals / 递延（复述冻结）

G4（Thinking 消费：render/brief 文本投影 + 实际读取点）— 不接。P1-1D（X→D→Y）— 不跑。
生产接线（converse/decision/DecisionBridge）— 不碰。schema/migration — 不碰。

---

## 7. Human Gate

- 本文件 = **G3 Implementation Scope / Plan + Safety Audit**。**Implementation 仍 NOT AUTHORIZED。**
- Gate 裁决选项：
  - **G3 IMPLEMENTATION GO** → 授权落地（1 生产文件 + 1 测试文件 + V1–V8）；
  - **G3 PLAN AMENDED** → 返回修订设计；
  - **G3 NO-GO** → P1-1 停在 G1 PASS。
- 冻结纪律不变：实现授权前不修改任何生产文件。

---

*本文件为实施规格，非代码。等待 Human Gate 裁决。*