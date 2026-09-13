# OCOS_IMPLEMENTATION_P0-4_PRECONDITIONS_PLAN.md

> 前置裁决：P0-4 Read-Only Forensic ⇒ **BLOCKED**（F4/F5/F6/F7 阻塞）。
> 本 plan 只允许两个解锁项，其余一律不做：
>   - **A：Counterfactual Baseline Freeze（Z）** —— 解锁 F6/F7
>   - **B：Decision₂ Trace（D→Thinking→Decision₂→Action₂ 身份连续性）** —— 解锁 F4/F5
> **明确不碰**：Attempt 2 运行、P1、重构 converse/DecisionRuntime/Planning/DecisionBridge/TaskDAG。

---

## 0. 背景收口

- P0-1/P0-2/P0-3 已铺好结构链：`X(Evidence) → recognize → SelfClaim → SelfDelta(D) → SelfUpdateContract → governed commit → S2`，且 T3 已证 **S2 committed 是 Thinking 的唯一 Self source**。
- P0-4 剩下的是**因果验证**：证明 D 真正改变了后续认知/决策，而不是"S2 变了 Prompt 变了"。
- 两个前置机制当前**缺失**（forensic 判定）：
  1. Z 反事实基线（生成 + A2 前冻结 + 冻结后只读）。
  2. 生产 Decision₂ 无可追溯 identity（`thinking_trace_id → self_version / delta_ids[] / evidence_ids[] → decision_id → decision/strategy/action → action_id → Y`）。

---

# A. Counterfactual Baseline Freeze（Z）

## A.1 目标

形成**一等、独立、只写一次**的证据对象 Z，并在 A2 之前冻结；冻结后任何改写被拒。
消灭 post-hoc attribution：

```
A2 成功 → 再回头构造"若无 D 会怎样"的 Z → 宣布 Y≠Z   （❌ 禁止）
```

## A.2 对象契约（一等证据）

```text
CounterfactualBaseline
  baseline_id        str          # 唯一
  goal               str          # 固定 Goal（task 描述）
  initial_state      object       # 初始环境/状态快照（可哈希）
  decision           str          # 若无 D，最有证据的决策
  strategy           str          # 策略
  action             str          # 动作
  predicted_result   object       # 预测结果
  source             str          # 基线来源（experiment harness / projection）
  evidence[]         list[str]    # 支撑 evidence_ids（可为 S1Evidence.id）
  confidence         float        # 该基线的置信度
  frozen_at          datetime|None # 冻结时刻；None 表示未冻结（不可用于归因）
  frozen_by          str          # 冻结属主
  baseline_hash      str          # 冻结态的 canonical hash（防篡改）
```

**不变式（强）**：

```
Freeze(Z) ─→ Attempt 2 ─→ Z 不得改变
```

- 未冻结的 Baseline 只是"草稿"，**不可**用作归因基准。
- `frozen_at` 写入后：`update`/`rewrite`/`unfreeze` 一律 `reject`（抛不可变性异常）。
- 每个 `(goal, initial_state)` 只允许**一份**已冻结 Z；重复冻结同 key → reject。

## A.3 修改边界

- **新增**：`ocos/self/counterfactual_baseline.py`（数据对象 + `CounterfactualBaselineStore` SQLite 存储 + `freeze/unfreeze_check/baseline_for`）。
- **新增表**：`counterfactual_baseline`（append-only；`frozen_at IS NULL` 的草稿可被同 key 新草稿替换，**`frozen_at` 非空记录不可改**）。
- **不碰**：S2、SelfEvidencePipeline、S3 Thinking 接线、任何决策运行时。
- 存储复用 `ocos.storage.connection.get_connection` 与 `ensure_schema`（与 S2 一致）。

## A.4 Invariant 强制实现

- `freeze()`：填充 `frozen_at/frozen_by`，`baseline_hash = sha256(canonical(Z 除 freeze 元数据外))`，事务内写库。
- 写库前 SQL 级校验：目标 key 已有非空 `frozen_at` → 事务回滚 + `CounterfactualBaselineError`。
- `baseline_for(goal, initial_state)` → 返回冻结 Z 或 `None`。**`None` ⇒ 该 Goal 的 A2 归因直接 BLOCKED**。

# B. Decision₂ Trace（D→Thinking→Decision₂→Action₂ 身份连续性）

## B.1 目标

让 P0-4 能在同一条 identity 上回答问题：
> "这次 Decision₂ 到底有没有消费那个 D？"
而不是只能证明"S2 更新后 Prompt 变了"。

## B.2 最小 trace 结构（不强改决策流）

```text
ThinkingTrace
  thinking_trace_id     str       # 每次决策生成一个
  self_version          int       # 决策时刻 S2 version
  consumed_delta_ids[]  list[str] # 该决策所见投影中含的 claim/delta ids
  consumed_evidence_ids[] list[str]

DecisionRecord(同 thinking_trace_id)
  decision_id           str
  decision              str
  strategy              str
  action_ids[]          str list   # 实际引发的动作（USE| action 或 DAG action）
  y_ref                 str|None   # 指向结果记录（experiment 期填充）

Action₂ ─→ Y
```

**同一身份链**：`thinking_trace_id → decision_id → action_ids → Y`。P0-4 归因据此 join。

## B.3 数据来源（复用已有，不新建语义）

- `consumed_delta_ids / consumed_evidence_ids`：源自 S2 `current.update_history` 中 **已提交 contract**（每项含 `claim_id` + `evidence_ids` + `fields_changed`）。决策所见投影正是由这些 committed 内容渲染。
- 实现：在 `SelfProjectionAccessor` 增加只读 `committed_claims()`（返回 `update_history` 的 `(version, claim_id, evidence_ids, target_component)` 列表，无副作用）。**不写 S2、不改变 render/brief 语义**。

## B.4 修改边界（最小 instrumentation，in-place hook）

- **新增**：`ocos/self/decision_trace.py`（`ThinkingTrace + DecisionRecord` 对象 + append-only `DecisionTraceStore` SQLite）。
- **接入点（仅两个、不改变控制流）**：
  1. `converse.py::respond()` 的 `L4-2` S2 投影注入处：存在 s2 projection 时生成 `thinking_trace_id`，记录 `self_version` + `committed_claims()` 过滤出的 `consumed_delta_ids/evidence_ids`；写入 trace 并随 reply 信封返回 `thinking_trace_id`。
  2. 决策结果落点：解析最终 reply 的决策文本 + 实际执行的动作 `action_ids`，以同一 `thinking_trace_id` 写 `DecisionRecord`。
- **不碰**：`TextGenerator`、`DecisionRuntime`、`Planning`、`DecisionBridge`、`TaskDAG`、`build_context` 的 prompt 内容与顺序。

## B.5 Invariant

- 同一 `thinking_trace_id` 的 `ThinkingTrace` 与 `DecisionRecord` **版本级一致**：`DecisionRecord.self_version == ThinkingTrace.self_version`，且 `consumed_*` 非空时其 id 必须出现在 S2 该 version 的 `current.update_history` 中（可校验）。
- trace 只记录、**不影响决策结果**（zero behavioral delta：prompt 与采样不改）。

# C. P0-4 Controlled Experiment Gate（本轮不跑，只定义 gate）

A、B 均完成且 forensic 通过后，才允许跑 Attempt-2。附门禁：

```
P0-4-Experiment  可执行 ⟺ Pre(A,Z) ∧ Pre(B,D)
Pre(A,Z) = 存在冻结 Z：(goal, initial_state) → Z.frozen_at 非空
Pre(B,D) = Decision₂ 的 ThinkingTrace 满足：
             self_version ≥ v(D) 且 consumed_delta_ids 含 D 的 claim_id
缺失任一 ⇒ 该 Goal 归因 BLOCKED；不得虚假归因。
```

# D. 验收测试（forensic gate）

## A 验收（Z Freeze）

- **A-T1 Freeze 基础**：可 `freeze()`，`frozen_at`/`baseline_hash` 非空，`baseline_for` 返回该 Z。
- **A-T2 不可变性（防 post-hoc）**：冻结后调 `update/rewrite/unfreeze` 抛 `CounterfactualBaselineError`；不得覆盖已冻结 Z。
- **A-T3 单份冻结**：同 `(goal, initial_state)` 二次 freeze → reject。
- **A-T4 未冻结不可归因**：草稿 `baseline_for` 返回 None 或显式标记未冻结；不可用于归因。
- **A-T5 持久化续存**：`baseline_for` 跨 store 重开仍返回同一 `baseline_hash`（仿真 S2 T8/T34 风格）。

## B 验收（Decision₂ Trace）

- **B-T1 身份链完整**：一次决策产出 `thinking_trace_id → decision_id → action_ids`，自洽唯一。
- **B-T2 D 消费可证**：注入一 Failure→D→commit(version N+1) 后，决策的 `ThinkingTrace.self_version` = N+1 且 `consumed_delta_ids` 含 D 的 claim_id。
- **B-T3 无 D 则无消费钩**：无新 commit 时，消费列表不引入不存在证据；`consumed_*` 全部可在 `update_history` 校验。
- **B-T4 零行为偏移**：加 trace 前后，对同一确定性输入，prompt 内容与决策结果不变（仅附 trace 元数据）。
- **B-T5 同链 join**：`DecisionRecord` 能按 `thinking_trace_id` join 回 `ThinkingTrace` 且版本一致。

## 批次门禁

```
A、B 全部测试绿 + 修改边界清单逐项勾选 ✅ → P0-4 Preconditions PASS
   → 才允许排期 P0-4 Controlled Experiment（Attempt 2）
任何一项红 → 维持 BLOCKED，不进入实验。
```

# E. 明确不做（范围压缩）

- ❌ 不跑 Attempt 2 / 不生成实验 Y。
- ❌ 不进入 P1。
- ❌ 不重构 converse / DecisionRuntime / Planning / DecisionBridge / TaskDAG。
- ❌ 不改 S2 semantic、不改 prompt 内容、不改采样（temperature=0.6）。
- ❌ 不做 P0-3 Worldview（可后置）。

# F. 文件清单（增量）

| 类型 | 文件 | 说明 |
| -- | -- | -- |
| A 新增 | `ocos/self/counterfactual_baseline.py` | Z 对象 + Store + freeze/invariant |
| B 新增 | `ocos/self/decision_trace.py` | ThinkingTrace + DecisionRecord + Store |
| B 加量 | `ocos/self/self_state.py` | `SelfProjectionAccessor.committed_claims()`（只读） |
| B 接入 | `ocos/interaction/converse.py` | `L4-2` 处 in-place trace hook（不改 prompt/流控） |
| A/B 新增 | `ocos/tests/test_p0_4_preconditions.py` | A-T1..5 + B-T1..5 |
| 表 | `ensure_schema` 增量 | `counterfactual_baseline` / `decision_trace` 两表 |

*文档结尾不变式：本 plan 只定义 A/B 的 implementation contract、边界、验收与 gate；不实施、不触发 Attempt2。*