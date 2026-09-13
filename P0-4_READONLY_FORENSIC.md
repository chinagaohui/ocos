# P0-4 Read-Only Forensic — Life-Chain Causality Audit

> 状态：**READ-ONLY / 不写代码 / 不跑 A2 / 不改 Prompt / 不改规则**。
> 本文件只做证据审计，回答用户的 7 个 forensic 问题（F1–F7），
> 并对实验计划的可行性给出 **PASS / FAIL / BLOCKED** 裁决建议。
> 依据：T3 已证明 S2 committed state 是 Thinking 的唯一 authoritative Self source。

---

## 0. 审计目标（用户锁定的强命题）

要证明的，不是"Evidence/Claim/Delta 类已存在"，而是**第一次完整闭环**：

```
X → Recognition → D → governed S2 commit
  → Decision₂ consumes D
  → Decision₂/Strategy₂/Action₂ structural delta
  → Y
  → Y ≠ Z
  → competing explanations eliminated → causal attribution
```

其中 P0-4 最容易造假的是 **F5**（D 是否被 Decision₂ 实际消费）。
P0-4 的成败关键前置是 **F6**（Z 必须在 A2 之前可信冻结，冻结后禁止修改）。

---

## 1. 逐节点证据审计

### F1 — X 从哪里来？一个真实、可重复、可注入的 Attempt-1 Failure

| 项 | 证据 | 判定 |
| -- | -- | -- |
| Evidence 结构 | `ocos.self.self_evidence.py` `S1Evidence`（frozen）：含 `evidence_id / source / observed_at / s1_version / s1_content_hash / data_hash / observations` | ✅ 存在 |
| Failure 观测 | `observations` 支持 `key="s1.failure_mode"`，`meta={count}`，`value=cause` | ✅ 存在可注入的 Failure 原子 |
| 提取入口 | `capture_s1_snapshot(snapshot) -> S1Evidence`：从一次 S1 画像快照规范化装箱，计算 `data_hash` | ✅ 存在且确定 |
| 不足 | 当前**只能从 S1 快照**取 X（capabilities 降级 + failure_modes）；没有一个"一次真实 Attempt-1 执行失败事件 → 自动进 Evidence"的运行时接线（实验需包 harness） | ⚠️ 部分满足 |

**结论 F1**：X 的**数据结构与可注入性成立**（evidence_id + data_hash 可哈希可追溯）。但"Attempt-1 File/Search 失败"需要一个**确定性实验 harness** 把失败做成可重复注入，而非依赖活体 S1 漂移。

---

### F2 — Recognition 是否真的识别 X？

| 项 | 证据 | 判定 |
| -- | -- | -- |
| 识别器 | `recognize(evidence) -> list[SelfClaim]`（规则化，无 LLM，确定性） | ✅ 存在 |
| Failure 识别 | `key=="s1.failure_mode"` → `ClaimKind.FAILURE_PATTERN` → 目标组件 `knowledge_boundary`，`key=cause` | ✅ 真识别 |
| 门槛 | 能力类：`attempts < _MIN_CAPABILITY_ATTEMPTS(=3)` 不产 Claim（防小样本） | ✅ 有准入 |
| 产出 | `SelfClaim`：claim_id / kind / statement / key / meta / evidence(锚) / confidence | ✅ 结构化，非 prompt |

**结论 F2**：Recognition **成立**。`recognize()` 是确定性规则工序，能把 Failure×計数 → 明确的 `SelfClaim`，且保留 evidence 锚。

---

### F3 — D 到底是什么？

| 项 | 证据 | 判定 |
| -- | -- | -- |
| Delta 对象 | `SelfDelta`：`claim_id / evidence_id / kind / target_component / key / old_value(A) / new_value(B) / source / confidence_impact` | ✅ 显式 A→B |
| Failure→D | Failure 类 claim → `delta_from_claim` 构造 `DomainStatement(domain=cause, NEEDS_VERIFICATION)`，`new` = 需验证的知识域 | ✅ 非 Lesson/日志/Prompt 文本 |
| 治理契约 | `SelfUpdateContract`：carries `evidence_ids / claim_id / confidence_impact / fields_changed` | ✅ provenance 完整 |
| S2 commit | `SelfEvidencePipeline.ingest` → 每 claim 一次 `commit_change(candidate, contract)` → version N+1 → hash → 原子落库（T2/T3 已验） | ✅ 成立 |

**结论 F3**：D 是**真正的结构化 Self/Cognition Delta**（A→B 对象），且经治理门进入 S2。✓

---

### F4 — D 是否以可追溯 identity 进入 Decision₂？

| 项 | 证据 | 判定 |
| -- | -- | -- |
| 生产决策路径 | `converse.py respond()` → `TextGenerator.generate(prompt, temperature=0.6, max_tokens=2000)` **自由文本生成** | 已核实 |
| S2→决策输入 | S2 投影文本注入 prompt："SelfState v{N}" + known capabilities + brief（T3 已验） | ✅ 文本层面 |
| delta 级可追溯 | **无** `delta_id / evidence_id / self_version / thinking_trace_id / decision_id` 必填注入或结构化决策输出 | ❌ 缺失 |
| 结构化决策运行时 | `decision_runtime.DecisionRuntimeEngine.form_decision()` 有 `decision_id` 状态机，但**只在 tests/planning/reasoning runtime 使用，未接生产对话 Thinking 路径，也未消费 S2 delta** | ❌ 未接线 |

**结论 F4**：D 的**效果**以文本（capability/域）进入 Decision₂ 输入，但**没有可追溯的 `delta_id/evidence_id/self_version` 钩子**把 D → Decision₂ input → Decision₂ output → Action₂ 串成同一条 identity 链。**不满足** "Decision₂ 输入中存在可追溯 trace" 的强要求。

---

### F5 — D 是否实际改变 Decision₂？（最容易造假）

| 项 | 现状 |
| -- | -- |
| 能证明的 | 仅 T3-3 级别的 **Prompt 文本随 S2 commit 变化** |
| 证明不了的 | "Decision₂(D) ≠ Decision₂(Z)" —— 因为：无结构化决策输出、无 delta 消费记录、无冻结的 Z、sampling 未 pin（temperature=0.6 固定但无 seed/多抽样基线） |

**结论 F5**：当前**最多只能证明** "S2 变化后 LLM 看到不同 Prompt"，**不能证明** "Thinking 消费了这个主体 Delta 并因此产生行为改变"。F5 在现有接线下 **不可证**。

---

### F6 — Z 能否在 A2 前可信冻结？（P0-4 最重要前置）

| 项 | 证据 | 判定 |
| -- | -- | -- |
| 反事实基线机制 | **代码库中不存在**任何 `Z / counterfactual / frozen_at / decision_baseline` 机制 | ❌ 缺失 |
| 冒名项 1 | `os_v1/freeze.py` 是 **OS ABI 冻结**（manifest/signatures），与决策反事实基线无关 | 排除 |
| 冒名项 2 | `optimization/manager.py _baseline` 是 **性能指标浮点基线**（metric_name→value），非"无 D 时 Agent 会做何决策/策略/动作/结果的预测基准" | 排除 |

**结论 F6**：**Z 无法在 A2 前可信冻结**。没有任何生成 `Z.source / Z.evidence[] / Z.confidence / Z.frozen_at` 的机制，也没有"冻结后禁止修改 Z"的强制与审计。

---

### F7 — Y 能否与 Z 做因果归因、排除其他变量？

| 项 | 现状 |
| -- | -- |
| 环境固定 | 无环境 checkout / 同 Initial State 快照设施 |
| model/prompt | prompt 基线只有隐式 context，无冻结快照 |
| sampling | temperature 固定，但**无 seed、无多抽样统计基线**（单样本 LLM 输出不可归因为 D） |
| capability | 能力可用性本身是 S2 的一部分；若"不可用"同时影响行为，会成为与 D 交织的混杂变量，当前无法分离 |

**结论 F7**：现有设施**无法**排除 environment/model/prompt/sampling/capability 等其他变量 → 因果归因**不可信**。

---

## 2. P0-4 最小实验（候选）— 节点证据表

沿用已验证的确定性文件/搜索类任务作为候选（环境最易固定）。实验链与期望证据：

```
Goal（固定）→ A1(确定性失败 X) → Recognition → D → governed S2 commit
  → Decision₂ → A2 → Y
```

| 节点 | 候选证据 | 可行性 |
| -- | -- | -- |
| X | 同一 Goal，A1 制造可解释失败（如按 S1 快照注入 failure_mode:cause）→ `S1Evidence` | ✅ 结构可注入 |
| Recognition | `recognize()` 产出 `FAILURE_PATTERN` SelfClaim | ✅ 已存在 |
| D | `SelfDelta`（knowledge_boundary 加 NEEDS_VERIFICATION）+ contract | ✅ 已存在 |
| S2 commit | version N+1，hash 更新，T3 已验投影可见 | ✅ 已存在 |
| Decision₂ consumes D | **需结构化 trace 钩子（delta_id/self_version/decision_id）——当前缺失** | ❌ 阻塞 |
| Z 冻结 | **无机制**（无反事实基线、无 frozen_at、无 max 修改保护） | ❌ 阻塞 |
| Y ≠ Z 归因 | **无** sampling pin、无多抽样基线、无 env 快照 | ❌ 阻塞 |

反证检查（用户强调）：只证明"S2 变化后 LLM 看到不同 Prompt"**不够**。要证明"Thinking 消费主体 Delta 并改行为"，必须 `delta_id/evidence_ids/self_version/thinking_trace_id/decision_id/action_id` 同一 identity 串起——当前**不存在**。

---

## 3. 裁决建议

### 结论：**P0-4 BLOCKED**

不是"再优化 Prompt"，而是**两个必要前置机制缺证/缺失**，导致因果链在 F4/F5/F6/F7 断裂：

1. **F6 缺失（硬阻塞）**：不存在 Z 反事实基线的生成与冻结机制。按用户纪律——"Z 在 A2 前无法可信冻结 → 直接判 BLOCKED，不开始实验"。
2. **F4 缺失 / F5 不可证**：生产 Decision₂ 是自由文本生成，无结构化决策 schema，无 `delta_id/self_version/thinking_trace_id` 钩子；无法把 D→Decision₂→Action₂ 串成同一可追溯 identity。

### 已满足 / 已证（不应重复开发）

- F1（X 结构与可注入）：✅ `S1Evidence` + failure_mode 原子
- F2（Recognition 真识别）：✅ `recognize()` 
- F3（D 结构化 + S2 commit）：✅ `SelfDelta` + `SelfUpdateContract` + governed commit

### BLOCKED 后的下一步（本轮不做，属后续 scoped implementation）

P0-4 若放行，需要**先补齐两件只读-designable 的前置**（本 forensic 仅为 audit，不实施）：

```
A. Z 冻结机制（解锁 F6/F7）
   Z.source / Z.evidence[] / Z.confidence / Z.frozen_at
   反事实基线在 A2 前冻结；冻结后只读、禁止修改；审计不可篡改。
B. Decision₂ 结构化 trace（解锁 F4/F5）
   生产决策输出/记录带 decision_id，并由 S2 accessor 携带
   self_version + consumed delta_ids/evidence_ids → 同链 identity。
```

在 A、B 落地前，任何 Attempt-2 运行都**不能**被归因为 D，运行即白跑。

---

*本文件由 READ-ONLY forensic 生成。未修改任何生产代码、未运行 Attempt 2、未改 Prompt/规则。*