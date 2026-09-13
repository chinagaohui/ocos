# OCOS P1-1 G3 Gate — Worldview Recognition/Evidence/Delta 评估（只读设计/审计）

> 状态：**G3 = NOT AUTHORIZED**（仅 Gate 设计/审计评估，不写生产代码）。
> 承接：G1 已 **PASS / FROZEN**（`docs/OCOS_P1-1_G1_IMPLEMENTATION_VERIFICATION.md`）。
> 依据：`docs/OCOS_P1-1_WORLDVIEW_SEMANTIC_CONTRACT.md`（§1–§14，语义冻结）与 G1 Shape Design。
> 本文件是 **G3 Gate 的前置论证材料**，回答"G3 到底要做什么、做到什么程度、为什么安全"，
> 产出后交 Human Gate 裁决（ACCEPTED → 仅授权进入实现方案；NOT AUTHORIZED 维持 → 冻结）。

---

## 0. G3 定位（与 G1 的边界）

```text
G1（已完成）             G3（本评估，未授权）
WorldView = 一个可写、    Evidence → Recognition → Judgment
            可持久化、       → Delta → Govern →  ⭐ WorldView Judgment 真正"形成"
            可投影的物理座位  ├─ 真实经历归因（P2 experience-attributed）
                            ├─ 框架性判断（P3 framework, not proposition）
                            └─ 变更连续性（P4 mutable via delta）
```

**G1 一句话**：WorldView 已存在于 SelfState 的物理模型中，但**尚未进入生产认知消费链**。
**G3 一句话**：让 WorldView 首次拥有**"形成能力"**——真实经历 X 能被规则化地识别为结构化 judgment 并提供 A→B 差分。

**重要：G3 产出的是"形成机制"，不是"已经形成"**。G3 完成到 Evidence→Judgment→Delta→Govern→W1
即满足 Recognition/Evidence/Delta 管线成立；"W1 确实改变了后续 Thinking/Decision 且 Y≠Z"
属于 **G4（Thinking Consumption）/ P1-1D（X→D→Y）**。

---

## 1. 现有管线只读审计（G3 的复用基座）

G1 已通过 `SelfEvidencePipeline` 验证：**任意写 S2 的动作都必经 goyvern commit（治理门）**。
以下是对 `ocos/self/self_evidence.py` 的现状盘点，用于判断 G3 能复用多少、在哪里扩展。

| 阶段 | 现有实现 | 对 worldview 的复用度 | G3 需扩展 |
| --- | --- | --- | --- |
| Evidence 装箱 | `capture_s1_snapshot` → `S1Evidence`（provenance 锚点：evidence_id/source/s1_version/data_hash） | ✅ 直接复用（真实经历锚） | 需补充 **worldview 领域观测 key**（s1.mismatch / episode pattern 等）的抽取规则 |
| Recognition | `recognize()`：rules → `SelfClaim`（CAPABILITY_KNOWN / UNCERTAIN / FAILURE_PATTERN） | ⚠️ 机制复用 | **新增 Worldview 领域识别**：`RecognitionType.conflict/confirm/novel-pattern/reframe` → `WorldViewJudgment` claim |
| Claim | `SelfClaim`（kind/statement/target_component/key/evidence/source/confidence） | ⚠️ 结构复用 | target_component=`worldview`；key=`domain`；statement=judgment 表达式 |
| Delta | `delta_from_claim()`：由 claim 相对 current 算 A→B | ✅ **必须扩展** | 计算 `old_value/new_value = WorldViewJudgment`，设定 `confidence_impact` |
| apply | `apply_delta()`：写入 candidate 组件 | ✅ 必须扩展 | 写入 `candidate.worldview.declare(new_judgment)` |
| 治理门 | `SelfBoundaryRules`（source 白名单；EXTERNAL_AGENT 拒写） | ✅ 直接复用（G1 T5 已验证） | 继续复用；确认 worldview 在来源白名单内可写 |
| commit | `SelfEvidencePipeline.ingest()`：per-claim governed commit，provenance 并入 update_history | ✅ 直接复用 | 无改动 |

**审计结论**：G3 不需要新链路，只需在既有 `Evidence→Claim→Delta→apply→commit` 五段中
**为 worldview 增加"识别规则 + 结构映射"**。边界最小、语义与既有 S1→S2 通道一致。

---

## 2. G3 范围定义（只读提案，未授权）

**G3 要做（形成机制）**，严格对齐 Semantic Contract §5/§6/§9：

```text
1. RecognitionType（新增）      conflict/confirm/novel-pattern/reframe
                               → 直接驱动 ContinuityKind（FIRST/DERIVED/REVISED/REPLACED）
2. Worldview Judgement 识别      从真实经历 Evidence 提取 domain + judgment + stance_type + frame
                               （interpretive/normative/epistemic；带 evidence_ids 归因）
3. Worldview Delta              结构化 old/new = WorldViewJudgment 快照（非字符串），
                               W-DELTA 含 trigger_experience_id / recognition_type / reason /
                               confidence_after / continuity
4. apply 写入                   经 WorldView.declare()（G1 已建）写回 candidate.worldview
5. Govern commit                复用既有 SelfBoundaryRules；source 用 REFLECTION / RUNTIME_OBSERVATION 归类
```

**G3 明确不做（后续 Gate）**：不接入 Thinking/Decision 消费（G4）；
不做生产控制流接线（P1-1D，受 P0-4B B1–B5 冻结）；不改 schema/migrations；
不新增第二套 self/runtime/authority；不碰 render/brief（延续 G1 T6b 零影响纪律）。

**Source 归类**（契约 §12.5）：优先复用 `REFLECTION` / `RUNTIME_OBSERVATION`；
**只有**当 judgment 无法归入二者时才需新增枚举成员——那属于 decision-semantics 变更，须单独立项、
单独 Human Gate，**不并入本 G3**。（当前审计判断：conflict/reframe 走 REFLECTION，
live 观测残差走 RUNTIME_OBSERVATION，**预期无需新增枚举**。）

---

## 3. 防冒充审计（G3 不越红线）

对契约 §2 N1–N8 / §5 不等性判据 / §11 Failure F1–F5，逐一检查 G3 提案：

| 红线 | G3 设计是否守住 | 守卫机制 |
| --- | --- | --- |
| N1 知识别名 | ✅ | judgment 是"如何理解/如何判断"的 stance，不是"世界是什么"的事实；recognition 只从经历归因，不直接从 knowledge_boundary 复制 |
| N2 belief 改名 | ✅ | Delta 是结构化的 WorldViewJudgment（frame/stance_type），不是 belief 表改名 |
| N3 WorldStore 数据直写 | ✅ | evidence 锚必须是真实经历（S1Evidence / episode），非外部地图计数；recognition 有准入门槛 |
| N4/N5 prompt 文本 / LLM 一句话 | ✅ | 产物是结构化 claim+delta+provenance+commit 链，非文本 |
| N6 version+1 / text diff 冒充 delta | ✅ | Delta old/new 为结构化对象，旧→新可差分；拒绝无证据的 new_value |
| N7 无归因的自省 | ✅ | recognition 门：judgment 无 evidence_ids 不可 emit |
| N8 静态宪法/模板 | ✅ | 模板不产生 delta，不满足 P4 |
| F1–F5 | ✅ | 均由 Recognition 门 + Govern 门 + 不接生产控制流 兜底 |
| T6b（render/brief 零影响） | ✅ | G3 只写 worldview 分量，延续 G1 证明的零影响（实现时用同款测试固化） |

**审计结论**：G3 提案在语义层面与既有 FROZEN 契约一致，无越线。

---

## 4. 最小性 / 安全性审计

- **最小改动表面**：仅 `self_evidence.py`（新增 recognition/claim/delta 分支）±
  `self_types.py`（新增 RecognitionType 枚举）。不改 schema/migrations、不改 render/brief、不改任何消费端。
- **治理通道不变**：所有写 S2 仍走 `SelfEvidencePipeline` → `commit_change`（Govern 门），无旁路。
- **向后兼容**：G3 为增量分支（worldview 缺省时走既有逻辑），旧状态加载不受影响（G1 T2 已证）。
- **幂等 / 触发纪律**：五条件（C1–C5）全满足才触发，避免"为写而写"。
- **风险**：识别规则若过松会把 Knowledge 污染进 worldview ⇒ 用 Recognition 准入门槛 +
  evidence_ids 非空强制 + Govern 门三重兜底。

---

## 5. Verification 方案（G3 PASS 的证据定义，未执行）

| # | 验证点 | 判据 |
| --- | --- | --- |
| V1 | Recognition 形成 | 给定真实经历 Evidence，`recognize()` 产出带 evidence_ids 的 WorldViewJudgment claim（非空、可归因） |
| V2 | 无归因拒绝 | 无 experience 的输入不产 worldview judgment（守 N7） |
| V3 | Delta A→B | `old_value(new_value = WorldViewJudgment` 结构化差分成立；new≠old 才 claim |
| V4 | continuity | conflict→REVISED/REPLACED、novel-pattern→FIRST/DERIVED 映射正确 |
| V5 | Govern | EXTERNAL_AGENT 拒写 worldview；合法 REFLECTION/RUNTIME_OBSERVATION 可 commit；update_history 带 claim_id/evidence_ids |
| V6 | commit 后 W1 | committed.worldview 反映 new_value；round-trip 一致 |
| V7 | 零影响回归 | 不含 worldview 输入的旧场景消息 render/brief 保持逐字节不变（延续 T6b） |
| V8 | 全量回归 | 受影响测试集合全绿；pre-existing failures 以 git-stash 反事实验证排除 |

**G3 PASS 门槛（与契约 §11 Acceptance A2/A3 对齐）**：V1–V8 全过，且至少存在一条
"经历归因的 claim + delta（带 evidence）"与"W1≠W0 的结构性证明"。行为级 Y≠Z 不在 G3，属 G4/P1-1D。

---

## 6. G3 Human Gate 选项

- **GATE ACCEPTED** → 授权产出 G3 实现方案（Scope/Plan/Safety）+ 单文件新增；实现仍须单独 Gate。
- **GATE AMENDED** → 返回修订识别规则/领域边界，不进入实现。
- **NOT AUTHORIZED（维持）** → 本评估冻结，P1-1 停在 G1 PASS 状态。

**G3 仍 NOT AUTHORIZED。** 本文件为 Gate 评估材料，不构成实现放行。

---

*本文件为设计/审计产物，非代码。等待 Human Gate 裁决。*