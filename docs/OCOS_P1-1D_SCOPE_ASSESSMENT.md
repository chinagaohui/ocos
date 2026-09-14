# OCOS P1-1D — Scope Assessment（生产现实审计，Human Gate 五问）

> 状态：**P1-1D SCOPE ASSESSMENT = PASS / FROZEN**（Human Gate 终裁，2026-09-14）。
> 裁决：**P1-1D 实施授权 = NO-GO（NOT AUTHORIZED）**；B（Trace 增强）暂不实施；
> A（接 DecisionBridge）否决；C（继续冻结）当前有效。
> 下一步（唯一开放）：**Decision Host / Semantic Boundary 只读审计**。
> 承接：G4 PASS / FROZEN（Worldview → Thinking Consumption，2026-09-14）。
> P1-1D = **NOT AUTHORIZED**（Human Gate 终裁）；本文件 = 进入 P1-1D 前的生产现实审计。
>
> 审计问题（Human Gate 指定，非"怎么接 Decision"）：
>
> > **G4 已证明的 Worldview → Thinking 输入差异，是否存在一条最小、可治理、可追踪、
> > 可验证的路径，使这种认知差异进一步影响 Decision，而不破坏现有 Authority Boundary？**

---

## 0. 审计纪律

- **纯只读审计**：未修改任何生产代码、未新增任何文件（除本文档）。
- 审计方法：源码追踪（Grep/Read）+ 生产宿主定位，结论附 `文件:行号` 证据（I2）。
- 冻结线（上游基准设施，本阶段**不触碰**）：`self_state.py`、`worldview_read_adapter.py`、
  `converse.py`（G4 接线）、G4-D/E、P-E1~P-E6、I1/I2/I3。
- 除非审计明确证明"生产架构不存在合法接线点"，否则不修改
  `context_builder.py` / `decision_pipeline.py` / `agent_runtime.py` / `bridge.py`。

---

## Q1. Decision 消费入口：生产 Thinking 输出究竟到哪里

### 1.1 生产 Thinking 宿主 = `ChatResponder.respond()`

```text
converse.py::ChatResponder.respond()（L1791）
  ├─ build_context()（L1802）→ 生产 Thinking Context/Prompt
  │    └─ L977-1003：G4 唯一生产接线（committed W1 → worldview 块 → Thinking input）
  ├─ TextGenerator / LLM provider → 生产回复（L1836-1966）
  └─ 回复生成后（L1968-1990）：
       ├─ _remember_conversation()（L1969）      → 记忆沉淀（Episode）
       ├─ session_manager.append_turn()（L1973-74）→ 会话追加
       └─ record_decision_trace()（L1981-1987）   → P0-4 B4：只读 trace 记录
```

### 1.2 回复产出的唯一"决策侧"动作 = `record_decision_trace`（只读记录）

[converse.py L1979-1990](file:///workspace/ocos/interaction/converse.py#L1979-L1990)：

```python
# P0-4 B4: Decision₂ 身份串联（thinking_trace_id → decision_id → action_ids → Y）。
# 只读记录 + 在 reply 信封附加 trace identity，供 P0-4 实验 Join；不改决策语义。
if thinking_trace_id:
    record_decision_trace(
        self._db_path, thinking_trace_id,
        decision=str(out.get("reply", ""))[:1000],
        strategy="", action="", action_ids=())
```

**结论（Q1）**：生产 Thinking 输出的唯一去向 = 对话展示 + 记忆（Episode）+ 只读 trace。
**不存在**任何"Thinking result → Decision input"的结构化接口或生产调用路径。
回复文本被当作 `decision` 字段落 trace，但 `action_ids=()` / `strategy=""` / `action=""` —— 无行为。

---

## Q2. Decision 是否真的读取 Thinking 输出

### 2.1 三级证据区分（本审计的判定标准）

| 证据等级 | 含义 | 当前状态 |
| --- | --- | --- |
| E1: Thinking output 存在 | 生产回复确实产生 | ✅ 存在 |
| E2: Decision 实际消费 Thinking output | 某 Decision 组件以 reply/context 为输入 | ❌ 无任何消费者 |
| E3: Decision 因 Thinking output 不同而不同 | ΔThinking → ΔDecision 因果 | ❌ 无宿主，无法验证 |

### 2.2 生产 Decision 链逐条核对

**决策智能链（`decision/` 包）= 备用引擎，无生产消费者**

[decision/__init__.py L5-8](file:///workspace/ocos/decision/__init__.py#L5-L8)：
组件链由 GAP-P1-1 接入 `cognitive_loop/decision_pipeline`（真实调用），
但该循环**无生产消费者**（备用引擎，见 [cognitive_loop/__init__.py L5-10](file:///workspace/ocos/cognitive_loop/__init__.py#L5-L10)）。
`DecisionPipeline` 消费 `LoopContext`（perception_input / active_wisdom），
**不消费 ChatResponder 回复**，亦无 worldview 字段（[context_builder.py](file:///workspace/ocos/decision/context_builder.py)：goal/self/wisdom/world/constraints 五槽，无 worldview）。

**生产 tick 决策 = AgentRuntime + DecisionBridge**

- `DecisionBridge.execute_dag_task(task)`（[agent_runtime.py L2213-2218](file:///workspace/ocos/agent/agent_runtime.py#L2213-L2218)）：
  输入 = TaskDAG task（来自 `_tick_step_planning_trigger` 规划，L1400 `self._active_dag = dag`），
  **与 Thinking 输出无交集**。
- `DecisionBridge.process(core_loop_result)`（[agent_runtime.py L2452-2461](file:///workspace/ocos/agent/agent_runtime.py#L2452-L2461)，
  [bridge.py L334-341](file:///workspace/ocos/execution/bridge.py#L334-L341)）：
  输入 = `_last_core_loop_result`，其唯一赋值点（L2421）位于 legacy cognitive loop fallback 内，
  而该 fallback **已永久停用**（L2416 `_enable_cognitive_loop = False`）→ **生产基本不会触发**。

**结论（Q2）**：三处候选 Decision 消费点（decision/ 包、AgentRuntime core_loop、DecisionBridge）
输入源均与生产 Thinking 输出（ChatResponder 回复）**无交集**。E2/E3 均为 ❌。

---

## Q3. Authority Boundary：Thinking → Self 写路径全枚举

核心风险：`Worldview → Thinking → Decision` 过程中是否出现
`Thinking → 修改 Worldview / Self / Claim / Goal / Governance`。

### 3.1 生产代码中所有"Thinking 侧 → Self 侧"写路径（穷举）

| 写路径 | 位置 | 写入对象 | 是否涉及 worldview 链 | 状态 |
| --- | --- | --- | --- | --- |
| `_remember_conversation` | converse.py L1969 | Episode（记忆） | ❌ | 既有机制，非 Self 组件 |
| `record_thinking_trace` / `record_decision_trace` | decision_trace.py L283-332 | trace 表（append-only） | ❌ | 只记录，零行为偏移 |
| `self_improve` | converse.py L1499-1576 | self_knowledge.md（经治理链） | ❌ | 既有机制；人工批准/审批关闭才应用 |
| `apply_self_upgrade` | converse.py L1578-1582 | self_knowledge.md | ❌ | 同上 |
| S2 boot 注册 | agent_runtime.py L574-582 | SelfStateManager 激活 + register_self_projection | ❌ | boot 时一次性，注册读出口 |

### 3.2 关键事实

1. **S2/Worldview 的唯一写入口 = `update_worldview`**（[self_model.py L178-197](file:///workspace/ocos/self/self_model.py#L178-L197)），
   仅经 `SelfEvidencePipeline.ingest()`（[self_evidence.py L673](file:///workspace/ocos/self/self_evidence.py#L673)）可达。
2. **`SelfEvidencePipeline` 无任何生产调用者**（全库 Grep：仅测试与 counterfactual_baseline 提及，
   而 [counterfactual_baseline.py L16](file:///workspace/ocos/self/counterfactual_baseline.py#L16) 明确声明"不写 S2、不碰 SelfEvidencePipeline"）。
   → **生产 tick/Thinking/Decision 没有任何代码能修改 Worldview / Claim / Governance。**
3. G4-H（既有测试）已证：修改 ThinkingContext 或消费产物**不反向改变** WorldView/Claim/Delta/Govern。
4. 既有 `self_improve` 通道：对话 → 提案 → 治理链（`propose_upgrade` → 影响分析/沙箱/快照）
   → 待批/自动应用至 `~/.ocos/self_knowledge.md`。这是**前 G1 时代既有**的"对话影响提示词层"
   机制，**与 worldview 链正交**（不写 S2、不写 Worldview），且需人工批准（`approval_disabled()` 例外）。

**结论（Q3）**：**Authority Boundary 未被破坏**。`W1 → Thinking → Decision` 链路上
不存在 Thinking → 修改 Worldview/Self/Claim/Goal/Governance 的任何生产写路径。
唯一现存"Thinking 影响自身"通道（self_improve → self_knowledge.md）是既有、人工门控、
且不属于 worldview 因果链。

---

## Q4. Decision Delta 可归因性：证据基础设施盘点

沿用 G4 证据哲学（Input changed + Output changed + Attributable），审计 P1-1D 需要的
`ΔW → ΔThinking → ΔDecision` 归因设施现状。

### 4.1 现有可复用设施

| 设施 | 内容 | 位置 |
| --- | --- | --- |
| ThinkingTrace | `thinking_trace_id + self_version + consumed_delta_ids + consumed_evidence_ids` | [decision_trace.py L35-43](file:///workspace/ocos/self/decision_trace.py#L35-L43) |
| DecisionRecord | `decision_id + thinking_trace_id + decision + strategy + action + action_ids + y_ref` | [decision_trace.py L46-57](file:///workspace/ocos/self/decision_trace.py#L46-L57) |
| 同链 Join | `decisions_for_trace(thinking_trace_id)` 按身份 join 回 ThinkingTrace | [decision_trace.py L220-227](file:///workspace/ocos/self/decision_trace.py#L220-L227) |
| Counterfactual Baseline Z | P0-4A 冻结的不可变反事实基准 | counterfactual_baseline.py |
| S2 版本号 | W1 commit 使 S2 v1→v2，可作 W0/W1 决策分组的代理键 | self_state.py |

### 4.2 归因缺口（关键）

| 缺口 | 说明 | 影响 |
| --- | --- | --- |
| **trace 无 worldview 快照** | ThinkingTrace 只记 `self_version + claim ids`，**不记 worldview 块内容**（domain/judgment/frame/claim_id） | ΔW 无法在单条 trace 上直接归因；只能靠 S2 版本号代理分组 |
| **decision=reply 文本** | DecisionRecord.decision 存的是回复文本，非"决策" | ΔDecision 的"决策语义"与"回复文本"混同 |
| **action_ids 恒空** | 生产上 `action_ids=()` / `strategy=""` / `action=""` | ΔBehavior（Y≠Z）无动作身份，无法归因 |
| **无 W0/W1 对照宿主** | P0-4 的 Z 是反事实基线，但 P1-1D 需要"同一宿主在 W0 与 W1 下分别决策"的配对 | ΔDecision≠0 无法与随机性/prompt 其它变量/provider 差异分离 |

**结论（Q4）**：归因基础设施**部分存在**（同链 identity + S2 版本代理 + Z 基线），
但**缺少 worldview 级快照与动作级身份**，不足以支撑 `ΔWorldview → ΔDecision` 的严格归因。
任何 P1-1D 实施必须先补 trace 的 worldview 快照字段（只读、append-only）。

---

## Q5. Behavior Delta 阶段切分（P1-1D-A/B/C）

`Thinking → Decision` 与 `Decision → Behavior` 是两个不同的证据问题，单独切分：

```text
P1-1D-A  Worldview → Thinking       = G4（PASS/FROZEN，上游基准）
P1-1D-B  Thinking → Decision        = 本阶段的真正目标（当前 ❌）
P1-1D-C  Decision → Behavior        = 独立证据问题（P0-4 Y/action_ids 的宿主域）
```

### 5.1 现有 Behavior Delta 宿主盘点（只读）

| 候选宿主 | 现状 | 可验证性 |
| --- | --- | --- |
| `DecisionBridge.execute_dag_task` | 生产生效，输入 = DAG task | 可产生真实行为，但输入不来自 Thinking 输出 |
| `DecisionBridge.process` | 生产基本不触发（legacy fallback 停用） | 输入 = core_loop_result |
| `converse.py respond()` | 生产生效，输入 = 用户消息 | 输出 = 回复文本（可作 Y，但无 action_ids） |
| `record_decision_trace` | 生产生效，只读 | 已记录 decision=reply，缺 action_ids 与行为差分 |

**结论（Q5）**：当前**不存在**"生产 Thinking 输出 → 决策 → 行为"的完整宿主。
P0-4 的 Y 目前是 reply 文本，不是行为；action_ids 为空。
**P1-1D-C（Behavior Delta）应排除在本阶段之外** —— 最小授权只需跨越
P1-1D-B 边界（Thinking → Decision 的可审计消费），且该边界当前也不存在生产宿主。

---

## 6. 核心结论

> 1. **生产 Thinking 输出（ChatResponder 回复）当前不存在任何合法 Decision 消费点**
>    （Q1/Q2：E2/E3 均为 ❌，断开点 = 回复只走记忆 + 会话 + 只读 trace）。
> 2. **Authority Boundary 未被破坏**（Q3：W1→Thinking→Decision 链上无任何
>    Thinking→Self/Worldview/Claim/Goal/Governance 写路径；SelfEvidencePipeline 无生产调用者）。
> 3. **归因基础设施有缺口**（Q4：trace 无 worldview 快照、action_ids 恒空、无 W0/W1 配对宿主）。
> 4. **Behavior Delta（P1-1D-C）应切出本阶段**（Q5：无完整宿主，Y 目前是文本不是行为）。
> 5. **W1 形成的生产可达性存疑**：`SelfEvidencePipeline` 无生产调用者 —— 即使接入 Decision，
>   生产上 W1 也仅在测试/手工凝结后存在。这是 P1-1D 授权前必须向 Human Gate 澄清的事实。

---

## 7. 最小授权范围建议（Scope 候选，待 Human Gate 裁决）

### 7.1 Scope 选项

| 选项 | 内容 | 风险 | 建议 |
| --- | --- | --- | --- |
| **A. 只接真实链** | 把 worldview 块接入 DecisionBridge 决策 prompt（DAG 任务执行时消费） | 需证明"世界观看进决策输入"且不改变 DAG 任务语义；跨 G4 冻结边界；且 DAG 输入与 Thinking 输出本就无交集 | 不推荐直接做 |
| **B. 最小 Scope Amendment** | 在 trace 中补 worldview 快照字段 + 解析 reply 的 USE| 动作行为 action_ids | 只补证据链（append-only），不改决策语义；与 P0-4 兼容；是 ΔW→ΔDecision 归因的前提 | **候选**（若目标 = 可审计的 Decision Delta） |
| **C. 保持 NOT AUTHORIZED** | 维持 P1-1D 冻结，不实施 | 无风险 | **默认**（证据不足时） |

### 7.2 本审计的推荐结论

- **当前证据强度不足以授权任何 P1-1D 实施**。生产 Thinking 输出→Decision 的接线不存在，
  且现有宿主（AgentRuntime/DecisionBridge）的输入语义与"Thinking 输出消费"不匹配。
- **不修改** `context_builder.py` / `decision_pipeline.py` / `agent_runtime.py` / `bridge.py`：
  审计未发现这些文件存在满足目标的合法接线点。
- 若 Human Gate 认为 P1-1D 阶段性目标 = **"可审计的 Thinking → Decision 消费证据"**，
  选项 B（补 trace 证据字段）是最小、只读、与 P0-4 兼容的候选 —— 但它**只建证据链，
  不产生 Decision Delta**。
- 若目标 = **"真实 Decision Delta / Behavior Delta"**，则生产链不存在，需新的 Scope Amendment
  （且必须先解决 Q4 归因缺口与 W1 生产形成可达性）。

---

## 8. 提交 Human Gate

- 本文件 = **P1-1D Scope Assessment（生产现实审计，五问结构）**。
- 请 Human Gate 裁决：
  1. Q1-Q5 审计结论是否认可？
  2. Scope 选项 A / B / C 是否选择其一，或要求补充审计？
  3. 若选 B：是否同时要求先澄清 W1 生产形成可达性（SelfEvidencePipeline 无生产调用者）？

---

## 9. Human Gate 终裁（FROZEN，2026-09-14）

```text
P1-1D SCOPE ASSESSMENT
======================

Q1 生产 Thinking 输出宿主
→ ChatResponder.respond()
→ PASS

Q2 Decision 是否消费生产 Thinking
→ E1 PASS
→ E2 FAIL
→ E3 FAIL
→ PASS（审计结论：不存在生产消费路径）

Q3 Authority Boundary
→ 未发现 Thinking → Self/Worldview/Claim/Goal/Governance
   生产写路径
→ PASS

Q4 Decision Attribution Infrastructure
→ 部分存在
→ 缺少 worldview snapshot / action identity /
   W0-W1 paired Decision host
→ PASS（缺口确认）

Q5 Behavior Delta Separation
→ Decision→Behavior 与 Thinking→Decision 必须分离
→ 当前 P1-1D-C 不纳入
→ PASS

SCOPE VERDICT
=============

P1-1D 当前仍 NOT AUTHORIZED。

不授权：
- ChatResponder → DecisionBridge 直接接线
- Worldview → DecisionBridge prompt 直接注入
- 修改 decision_pipeline.py
- 修改 agent_runtime.py
- 修改 bridge.py
- 修改 context_builder.py
- 任何 Decision→Behavior 实施

允许下一步：
- Decision Host / Semantic Boundary 只读审计
- 明确现有生产 Decision 语义宿主
- 明确 Thinking→Decision 是否存在合法最小接口
- 明确所需最小 Attribution Infrastructure

B 仅可作为后续证据基础设施 Scope Amendment 候选，
不得解释为已经建立 Thinking→Decision。
```

**冻结状态**：P1-1D Scope Assessment = **PASS / FROZEN**；
P1-1D 实施授权 = **NO-GO**；唯一开放下一步 = Decision Host / Semantic Boundary 只读审计
（见 `OCOS_P1-1D_DECISION_HOST_SEMANTIC_BOUNDARY_AUDIT.md`）。

---

*本文件为 P1-1D 只读审计材料（PASS / FROZEN）。未修改任何生产代码。下一步仅限 Decision Host 只读审计，需 Human Gate 明确授权方可进入实施。*
