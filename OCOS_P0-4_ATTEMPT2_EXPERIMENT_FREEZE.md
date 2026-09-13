# OCOS P0-4 ATTEMPT 2 — EXPERIMENT DESIGN FREEZE

> 状态：**DESIGN-FREEZE**（已冻结，尚未执行，零生产代码改动）。
> 前置裁决：P0-4 Preconditions A(Z Freeze) + B(Decision₂ Trace) 验收 **PASS** → **Gate OPEN**。
> Gate OPEN ≠ P0-4 PASS。本文件只定义一次**受控 Attempt 2** 的可信执行协议。
>
> 纪律：**协议冻结后，才允许执行一次受控 Attempt 2。** 执行前本协议任何字段修改均视为破坏冻结。

---

## 0. 本文件目的

把"OCOS 第一次完整生命链"的受控实验钉死成一个可复核、可伪造检测的协议。目标是生产级证据：

```
过去发生了 X → 我理解发生了变化 D → 所以现在我想得不一样 → 所以我的行为 Y 不一样
```

不是看"A2 成功没有"，而是证明因果：
**因为 X → D，且 Decision₂ 消费了 D，所以产出与 Z 结构不同的 Y。**

---

## 1. Goal（同一 Goal，A1/A2 不许偷换任务）

> A1 与 A2 必须使用**同一个 Goal G**。任何 A1/A2 任务描述不一致 ⇒ **INVALID**。

```text
Goal = G
Attempt 1 = G
Attempt 2 = G
```

**G（冻结任务描述）**：确定性 shell/文件操作任务（沿用 forensic §2 已验证的候选，环境最易固定）。

```text
G = "在 初始目录 INIT_DIR 下，按 规格(SPEC) 完成对 目标文件集 FILES 的确定性重排，
     并把结果写入 输出清单 OUT。"
```

冻结项均在 §5 控制变量表锁定（INIT_DIR / SPEC / FILES / OUT / 环境 / 工具集）。

---

## 2. X —— A1 的真实执行失败

> 不允许用"纯 S1 手工注入"作为最终生命链证据。**X 必须对应当前 Attempt-1 的一次真实执行结果。**

```text
Action₁ → Reality → Failure X → Observation → Recognition
```

- **harness 只能控制失败条件**（如：预先扣除某 capability、制造文件缺失/权限/格式不兼容），
  从而让 A1 在真实执行中失败；失败事件 X 由 harness 从**真实执行结果**捕获，转成 S1 Evidence。
- 证据装箱走生产入口：
  - `capture_s1_snapshot(snapshot)` → `S1Evidence`，其中：
    - `failure_modes: [{cause, count≥阈值}]` → `key="s1.failure_mode"`
    - capability 降级 → `key="s1.capability"`（`attempts ≥ 3` 才产 Claim，防小样本）
  - 产出 `evidence_id` + `data_hash`（可哈希可追溯）。

**X 冻结记录（A1 完成后回填）**：

```text
action_1:      <实际 Action₁ 的 action_id>
reality:       <真实执行结果（退出码/输出/副作用）>
failure_x:     <X 的 failure cause / 观测>
observation:   snapshot 字段（failure_modes / capabilities）
evidence_id:   S1E-...
data_hash:     <capture_s1_snapshot 计算>
```

强检查：`X.confirmed` 仅在上述字段全部回填且源自真实执行时打勾。

---

## 3. A / D —— A1 完成后冻结

A1 完成后（X 已确认），把 Recognition → D → governed S2 commit 的产物立即冻结：

```text
Self Claim A → Recognition → SelfDelta D → Governed S2 commit
```

走生产管道 `SelfEvidencePipeline(manager).ingest(evidence)`（内部：`recognize`
→ `delta_from_claim` → `apply_delta` → 逐 claim `commit_change`）。

**D 冻结记录（A1 后立即回填，禁止在 A2 后回头补填）**：

```text
claim_id:              SelfClaim.claim_id（kind=FAILURE_PATTERN）
delta_id:              SelfDelta（claim_id 派生，记录即可）
evidence_ids:          [evidence_id]
self_version_before:   ingest 前 manager.version
self_version_after:    ingest 后 manager.version（= before+1，逐 claim 单调）
content_hash_before:   ingest 前 accessor.content_hash
content_hash_after:    ingest 后 accessor.content_hash
fields_changed:        Contract.fields_changed（目标组件）
```

**S2 的 D 是实验自变量，不是"环境变化"。** A1/A2 之间除 D 之外的所有环境本构必须不变（§5）。

---

## 4. Z —— 严格先于 A2 冻结（序不变量，违反即 INVALID）

```text
A1 → X → Recognition → D → Z generation → Z FREEZE → A2
```

禁止（直接 INVALID）：

```text
A1 → D → A2 → 观察 Y → 构造 Z
```

- 用 `CounterfactualBaselineStore.freeze(baseline_id, frozen_by="experiment")` 冻结；
  `frozen_at` 必须严格早于 A2 首次执行时间（`frozen_at < A2_start`）。
- Z 的判定字段 `source / evidence[] / confidence / frozen_at / baseline_hash` 全部非空。
- 冻结后任何改写 / 重冻结 / 覆盖在同 `(goal, initial_state)` 上被实体层 + DB 唯一索引双拒。
- 归因只允许对照 `baseline_for(goal, initial_state)` 返回的**已冻结** Z；若不返回 ⇒ 该 Goal 归因 **BLOCKED**。

---

## 5. 控制变量冻结（锁死，不改动）

以下每一项在 A1 开始前冻结为常量，A1/A2 之间**不变**；任何一项漂移 ⇒ 记录并重新评估归因可信度：

```text
Goal                     = §1 G（A1=A2 同一）
Task specification       = §1 SPEC（文本字面量锁定）
Initial state            = INIT_DIR 快照（哈希锁定；A2 回到与 A1 同一初始态）
Environment              = sandbox / OS / 依赖锁定
Relevant files/data      = FILES + OUT + 只读/禁止区
Capability availability  = 除被 harness 用于制造 X 的扣减外，其余不变
Model/provider           = 冻结
Model version            = 冻结
System prompt            = 冻结
Self projection baseline = §3 self_version/content_hash before/after 留档
Temperature              = 0.6
Sampling configuration   = 冻结（temperature 固定；记录是否 seed/多抽样基线——见 §12）
Tool definitions         = 冻结
Execution timeout        = 冻结
```

> 特别区分：**D 是自变量**。capability 不可用若同时影响行为，会与 D 交织成混杂变量 ——
> 因此 harness 扣减的 failure 条件在 Z 的"无 D"假设中必须被显式模型化或消除（§7）。

---

## 6. Decision₂ —— 完整 Trace（B 已补齐基础设施，禁再用弱证据）

本实验唯一可接受的 D 消费证据是**结构化同链 trace**，不是"Prompt 看起来变了"。

```text
X ── evidence_id
 ↓
Recognition ── claim_id
 ↓
D ── delta_id
 ↓
S2 vN+1 ── content_hash
 ↓
Thinking Trace
 │  ├─ thinking_trace_id
 │  ├─ self_version        = N+1（必须 = §3 self_version_after）
 │  ├─ consumed_delta_ids  = 含 D 的 claim_id
 │  └─ consumed_evidence_ids = 含 X 的 evidence_id
 ↓
Decision₂ ── decision_id
 ↓
Action₂ ── action_id
 ↓
Y ── y_ref
```

实现钩子（已存在，冻结其用法，不改实现）：
- `record_thinking_trace(db)`：S2 投影装入处生成 `ThinkingTrace`（self_version + committed_claims 过滤出的 consumed ids）。
- `record_decision_trace(db, thinking_trace_id, decision, strategy, action, action_ids, y_ref)`：同链 `DecisionRecord`。

**必须同时满足（B-T2 级校验）**：
`ThinkingTrace.self_version == §3 self_version_after` 且
`D.claim_id ∈ ThinkingTrace.consumed_delta_ids` 且
`X.evidence_id ∈ ThinkingTrace.consumed_evidence_ids`。
任一缺失 ⇒ **F5 未闭合 ⇒ FAIL**。

---

## 7. Z 反事实基准纯净性审计（最强一条）

Z 必须是"**实验前可获得**的反事实基准"。Z 的依据**不得依赖**以下任何一项：

- ❌ A2 的输出
- ❌ A2 的成功/失败
- ❌ A2 的 observation
- ❌ A2 的 action
- ❌ A2 的 result

即使 DB 层面 `frozen_at < A2`，若 Z 的 `source / evidence[] / decision / strategy / action / predicted_result` 内容借用了 A2 的任何信息，**语义上仍判 post-hoc contamination ⇒ INVALID**。

审核清单（freeze 时逐项核）：

```text
source            = experiment harness / projection 在 A2 前可得 ?
evidence[]        = 仅来自 A1 前已存在证据 / §3 D 的 evidence（不引用 A2）?
confidence        = A2 前无观察时按先验设定，不得随 A2 结果改写 ?
predicted_result  = 只预测"若无 D，会怎么办"，与 A2 无关 ?
```

产出一个 Z 是否合格的布尔结论 `Z_clean`（必须 True 才算归因可用）。

---

## 8. 执行过程（顺序冻结 + 任一步停）

```text
Step 0  冻结 §1–§5 控制变量 + 打 INIT_DIR 快照哈希。
Step 1  执行 A1（真实执行）→ 捕获 Failure X → 回填 §2。
Step 2  SelfEvidencePipeline.ingest → 回填 §3（claim/delta/evidence/version/hash）。
Step 3  生成 Z（来源=harness"无 D"先验预测）→ 通过 §7 审计 → CounterfactualBaselineStore.freeze。
         校验 frozen_at < A2_start。Z 不可冻结 ⇒ STOP（该 Goal 归因 BLOCKED）。
Step 4  回到 §5 同一 INIT_DIR 初始态，执行 A2。
Step 5  record_thinking_trace → 校验 §6 三条（self_version / consumed delta / consumed evidence）。
        校验失败 ⇒ STOP（F5 未闭合，不进入归因）。
Step 6  record_decision_trace（含 decision/strategy/action/action_ids/y_ref=Y）。
Step 7  结构化比较 Decision₂/Strategy₂/Action₂ vs Z（§9）→ 归因（§10）。
```

任一步不满足即停；**不停下以"让测试看起来过"为借口**。

---

## 9. 结构化差异判定（Decision₂ vs Z）

对 `DecisionRecord` 的字段与冻结 Z 对应字段做**结构化 diff**（非文本相似度）：

```text
decision   : DecisionRecord.decision   vs Z.decision
strategy   : DecisionRecord.strategy   vs Z.strategy
action     : DecisionRecord.action     vs Z.action
action_ids : DecisionRecord.action_ids vs Z.action
```

判定为"结构性不同"需显式列出字段级差异；仅精确相等 ⇒ 无差异（不算通过）。

---

## 10. 最终 P0-4 PASS 标准（Attempt 2 后逐项打勾）

```text
[1] X confirmed（真实执行失败，§2 完整回填）
[2] Recognition confirmed（FAILURE_PATTERN claim 产出）
[3] D committed（version N+1 + content_hash 变化，§3 完整回填）
[4] Z frozen BEFORE A2（frozen_at < A2_start，且 Z_clean=True）
[5] Decision₂ consumed D（§6 三条全满足）
[6] Decision₂ structurally differs from Z（§9 字段级差异）
[7] Action₂/Strategy₂ structurally differs from Z（§9 字段级差异）
[8] Y observed（行为结果捕获，y_ref 回填）
[9] Y ≠ Z（Y 与 Z.predicted_result 结构化不同）
[10] alternative explanations rejected（§11）
[11] causal attribution complete（X→D→consumed→different→Y≠Z 全链闭合）
```

**A2 成功 ≠ PASS；A2 与 A1 不同 ≠ PASS。** 必须第 1–11 全绿。

---

## 11. 外部解释消除（causal attribution 必要）

排除与 D 竞争的替代假设：

```text
E1 环境漂移      : INIT_DIR 哈希在 A1/A2 间一致，env/依赖/Model/version/prompt 全不变。
E2 sampling 噪声 : 见 §12 —— 若未 pin seed，需多抽样基线证明差异可重复，或把结论降级为
                   仅"存在差异"而非"单样本因果"。
E3 capability 混杂: harness 扣减的 failure 条件在 Z"无 D"假设中的效应被显式模型化/消除。
E4 其他 prompt 变体: A1/A2 system prompt 字面量一致。
```

E1–E4 全部可回答为"已消除/已记录" 才可过 `[10]`。任何一项不能排除 ⇒ 因果归因降级或 FAIL。

---

## 12. 采样说明（诚实声明）

- `temperature=0.6` 冻结。是否 `seed` / 多次抽样基线在冻结时明确记录：
  - **Option A**：项目支持固定 seed ⇒ 单次输出即可做严格结构对比，归因最强。
  - **Option B**：无 seed ⇒ 需对 (Z 假设 vs D-消费) 各做 ≥3 抽样，
    用结构差异的可重复性代替单样本因果（E2 以多抽样消除）。
- 冻结时必须记录走 A 还是 B；执行照所选分支，不临时切换（切换会破坏不变式）。

---

## 13. 明确不变量 / 不碰（维持 forensic 纪律）

```xml
- ❌ 不修改生产代码去"涨通过率"：Z 逻辑、DecisionRuntime、Prompt、采样、S2 语义均不改。
- ❌ 不为让测试绿去放宽 §6/§7/§10 判据。
- ❌ 不跑 P0-3 Worldview（后置）。
- ❌ 不进入 P1。
- ✅ 只跑一次受控 Attempt 2 + 记录 + 归因，产出一份 Attempt 2 执行记录。
```

---

## 14. 产物

- `OCOS_P0-4_ATTEMPT2_EXPERIMENT_FREEZE.md`（本文件，冻结协议）
- Attempt 2 执行记录（Step 0–11 逐项回填 + 结论）

---

*文档结尾不变式：本文件仅冻结一次 Attempt-2 的执行协议，未执行，未改任何生产代码。*