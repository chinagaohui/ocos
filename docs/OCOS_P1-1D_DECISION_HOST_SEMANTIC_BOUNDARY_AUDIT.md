# OCOS P1-1D — Decision Host / Semantic Boundary Audit（D1-D5，只读）

> 状态：**只读审计完成，提交 Human Gate 裁决**。
> 承接：P1-1D Scope Assessment = PASS / FROZEN（2026-09-14）；P1-1D 实施 = NO-GO；
> A（接 DecisionBridge）REJECTED；B（Trace 增强）NOT AUTHORIZED；C（继续冻结）SELECTED。
> 本审计 = Human Gate 唯一开放的下一步，**只回答一个基础问题（不研究"怎么接线"）**：
>
> > **OCOS 生产系统中，到底有没有一个已经存在、具有真实 Decision 语义和 Authority 边界的 Decision Host？**
>
> 审计结构（Human Gate 固定五问）：
> **D1** Decision Host Identity · **D2** Semantic Boundary · **D3** Authority Entry ·
> **D4** Existing vs Legacy/Dead Host · **D5** 最小合法边界是否已存在。
>
> 注：本文件取代 7 点中间版审计（`OCOS_P1-1D_DECISION_HOST_SEMANTIC_BOUNDARY_AUDIT.md` 旧版），
> 事实核验口径不变，证据与行号重新整理为 D1-D5 结构。

---

## 0. 审计纪律

- **纯只读审计**：未修改任何生产代码、未新增任何文件（除本文档）。
- 冻结线不触碰：`self_state.py` / `worldview_read_adapter.py` / `converse.py`（G4 接线）、
  `decision_pipeline.py` / `agent_runtime.py` / `bridge.py` / `context_builder.py`。
- 判定原则（防"类名陷阱"）：**模块名称像 Decision ≠ Decision Host**。
  每个组件按「输入 → 输出 → 调用者 → 生产可达性 → 是否影响执行」五元组判定。
- 结论附 `文件:行号` 证据（I2）。

---

## D1 — Decision Host Identity：谁真正拥有"Decision"语义

### 1.1 生产可达的"决策"候选逐一核验

| 候选 | 输入 | 输出 | 生产调用者 | 生产可达 | 影响执行 |
| --- | --- | --- | --- | --- | --- |
| `ChatResponder.respond()` | 用户消息 | reply 文本 + 只读 trace | daemon / API | ✅ | ❌（不产生行为） |
| `AgentRuntime._tick_step_planning_trigger` | Goal(PENDING) | `_active_dag = dag` | AgentRuntime tick step 6 | ✅ | ✅（决定做什么） |
| `DecisionBridge.execute_dag_task(task)` | DAG task | 执行结果 / 待批 / 拒绝 | AgentRuntime L2218 | ✅ | ✅（产生真实行为） |
| `DecisionBridge.process(core_loop_result)` | core_loop 输出 dict | BridgeReport | `_last_core_loop_result`（恒空） | ❌ | ❌ |
| `DecisionLoop.execute_single()` | MasterAgent 感知/思考 | cycle 结果 | AgentRuntime L2419（停用 fallback 内） | ❌ | ❌ |
| `MasterAgent.decide()`（CognitiveBridge） | thought | BridgeResult | 仅 DecisionLoop | ❌ | ❌ |
| `DecisionMakingEngine.execute()`（Phase 19） | options_data/context | selected option | 仅 CognitiveBridge.decide | ❌ | ❌ |
| `DecisionRuntimeEngine.form_decision()`（Phase 18） | goal_id | Decision 对象（WorkingMemory） | **无**（policy 白名单仅字符串） | ❌ | ❌ |
| `decision/` 包（ContextBuilder→Proposal） | LoopContext | DecisionProposal | cognitive_loop（备用链） | ❌ | ❌ |

### 1.2 D1 结论

> **生产上真正拥有"Decision"语义的位置 = `AgentRuntime` step6 规划层（goal→DAG）
> + `DecisionBridge.execute_dag_task()`（DAG 任务 → 动作执行）。**
>
> 输入语义 = **Goal（HUMAN/chat 目标描述 / 模板分解）**；
> 输出 = **DAG / 执行动作**；影响执行 = ✅。
>
> **它的输入不是 Thinking 输出。** 所有以"认知产物"为输入的决策组件
> （DecisionLoop / MasterAgent.decide / DecisionMakingEngine / DecisionRuntimeEngine / decision/ 包）
> 均**生产不可达**（停用 fallback 或无调用者）。

---

## D2 — Semantic Boundary：Thinking ≠ Decision ≠ Mutation ≠ Execution

### 2.1 四层语义在代码中的实际落点

```text
Thinking      ChatResponder.build_context → LLM → reply（认知结果）
Decision      AgentRuntime step6（Goal 受理/规划分解 → DAG = 已决定的"做什么"）
Mutation Auth DecisionBridge.execute_dag_task → _adjudicate（auto/ask/deny）+ 权限网关
Execution     dispatcher.dispatch → 动作执行（sandbox 白名单 / pending outbox / audit）
```

### 2.2 关键追问：什么从"认知结果"被正式解释为"决策"？

全库追踪结果：**没有任何代码把 Thinking 输出（reply / build_context 产物）解释为决策**。

- [converse.py L1968-1990](file:///workspace/ocos/interaction/converse.py#L1968-L1990)：reply 只走记忆 + 会话 + 只读 trace。
- DAG 任务的来源 = Goal 描述（[agent_runtime.py L1370-1400](file:///workspace/ocos/agent/agent_runtime.py#L1370-L1400)），
  由 chat 目标编译 / 模板分解产生，**不经 Thinking 输出**。
- `decision/` 包唯一消费方 `cognitive_loop/decision_pipeline` 输入 = LoopContext（感知/智慧），
  非 Thinking 输出，且无生产消费者。

### 2.3 D2 结论

> **Thinking ≠ Decision ≠ Mutation Authorization ≠ Execution 四个语义层在生产代码中
> 明确分离。** "认知结果 → 决策"的正式解释点**不存在**。
> `DecisionRecord` 存在 ≠ `Decision` 发生 —— 它只是 **Thinking/Reply 的审计记录**
> 被暂存在名为 DecisionRecord 的数据结构中（[decision_trace.py L46-57](file:///workspace/ocos/self/decision_trace.py#L46-L57)，
> 生产值 `decision=reply`、`action_ids=()`，[converse.py L1982-1985](file:///workspace/ocos/interaction/converse.py#L1982-L1985)）。

---

## D3 — Authority Entry：真正的 Decision → Mutation Authority 入口

### 3.1 唯一生产入口

```text
DecisionBridge.execute_dag_task(task)（bridge.py L405）
  ├─ _gateway_scan(description)           → 反向控制/注入直接拒绝（L414-431）
  ├─ 元认知置信门（写类低置信 → ASK 待批）（L434-463）
  ├─ LLM 优先转动作（只读类 AUTO / 写类 ASK）（L470+）
  ├─ _adjudicate(action)                   → auto / ask / deny（L627）
  │     ├─ auto  → dispatcher.dispatch → 真实执行（sandbox 白名单）
  │     ├─ ask   → pending outbox（待人工批准）
  │     └─ deny  → 拒绝 + 审计
  └─ _audit_record / _audit_action         → 全量审计
```

### 3.2 关键澄清（防误判）

- **`USE|` 动作行不是 Decision，不产生 Mutation Authority**：
  `_USE_ALLOWED = ("shell", "fs_read")`（[converse.py L104](file:///workspace/ocos/interaction/converse.py#L104)），
  仅只读能力 + 预算护栏（`_USE_LINE_LIMIT=2`、`_MAX_TOOL_ROUNDS=2`，L101-102）。
  它是 **Thinking 内部的受限只读工具调用**，不经过 `_adjudicate` / 权限网关 / 审计链，
  **不是 Decision → Mutation Authority 入口**。
- 生产上唯一合法的 **Decision → Mutation Authority** 入口 = `DecisionBridge.execute_dag_task`
  内的裁决链（上表）。**只有经裁决的 DAG 任务能产生 mutation。**

### 3.3 D3 结论

> **冻结原则成立：只有 Decision 才能产生 Mutation Authority。**
> 生产上唯一的授权入口在 **DAG 执行裁决链**，其输入 = Goal 派生的任务，
> **与 Thinking 输出无关**。任何 LLM 输出（含 `USE|`）不因此获得 mutation authority。

---

## D4 — Existing Host vs Legacy / Dead Host 分类

| 组件 | 分类 | 依据 |
| --- | --- | --- |
| `ChatResponder`（converse.py） | **Production Thinking Host** | daemon/API 生产调用；产出 reply + 只读 trace |
| `DecisionTraceStore`（decision_trace.py） | **Record facility** | append-only；生产唯一 producer = converse |
| `AgentRuntime` | **Production Runtime（tick orchestrator）** | 生产 tick 主链：event→attention→planning→DAG→dispatch |
| `TaskDAG` / `TaskDecomposer`（planning/） | **Production Planning Output / Execution Carrier** | goal→plan 产物（已决定的"做什么"），经 execute_dag_task 执行 |
| `DecisionBridge.execute_dag_task` | **Production Execution Gate** | 网关前检 + 置信门 + 裁决 + 审计；唯一 mutation 入口 |
| `DecisionBridge.process` | **Dead**（legacy 路径） | 输入源 `_last_core_loop_result` 恒空（fallback 停用） |
| `cognitive_loop/`（DecisionPipeline 等） | **Legacy / Dead**（已接好线备用引擎） | [cognitive_loop/__init__.py L5-10](file:///workspace/ocos/cognitive_loop/__init__.py#L5-L10) 无生产消费者 |
| `decision/` 包（ContextBuilder→Proposal） | **Legacy / Dead** | 仅被 cognitive_loop 调用（备用链） |
| `DecisionLoop` / `MasterAgent.decide` / `CognitiveBridge` | **Legacy / Dead** | 唯一调用点 = agent_runtime L2419（停用 fallback） |
| `DecisionMakingEngine`（Phase 19） | **Legacy / Dead** | 仅 CognitiveBridge.decide 可达 |
| `DecisionRuntimeEngine`（Phase 18） | **Dead** | 无生产调用者；WorkingMemory 生命周期管理 |
| `_adjudicate` / `dispatcher` / `_gateway_scan`（bridge.py） | **Production Execution Gate 组件** | 构成唯一 mutation 授权链 |

**D4 结论**：
- 生产 Decision 语义 = **AgentRuntime(goal→plan) + DecisionBridge.execute_dag_task 裁决链**。
- 所有"认知型决策"组件（名称含 Decision 的 Phase 18/19 引擎、DecisionLoop、decision/ 包）
  一律 **Legacy / Dead** —— **"模块名称像 Decision"全部被排除出生产 Host 资格**。

---

## D5 — 最小合法边界是否已经存在

按 Human Gate 三情况判定：

### 情况 A：现成 Production Decision Host 消费 Thinking
> **不存在。** 生产 Decision Host（AgentRuntime + DecisionBridge）输入 = Goal/DAG，
> 无任何 Thinking 输出消费点（D1/D2）。

### 情况 B：Decision Host 存在，但输入语义完全不是 Thinking
> **成立（主判定）。**
> `TaskDAG → DecisionBridge → Execution` 是真实生产链，但 Thinking 输出与之**无接口**。
> **架构缺的不是"接线"，而是 Semantic Boundary。**
> 禁止用 adapter 把两个语义硬接（`ChatResponder → DecisionBridge` 会人为创造新认知→决策主链）。

### 情况 C：根本没有生产 Decision Host
> **不成立（就"goal→DAG"语义而言）。** 生产存在决策层，只是语义域不同。
> 但若把"Decision Host"严格限定为"消费认知结果产生决策"——则**不存在**，
> 即：**P1-1D 不是 wiring task，而是新架构能力建设问题**。

### D5 结论

> **Situation B 为主判定，叠加 C 的部分成立**：
> 生产存在 Decision Host（goal→DAG 语义域），但**不存在 Thinking→Decision 的合法最小接口**，
> 更不存在"认知决策"宿主。强行接线 = 创造新认知→决策主链（超出最小接线，禁止）。
>
> 若未来进入 P1-1D-B，必须：
> 1. 先设计 **Semantic Boundary**（Thinking 输出何时、以何种载体被正式解释为 Decision）；
> 2. 配套最小 Attribution Infrastructure（Scope Assessment Q4 缺口：
>    worldview 快照 / action_ids / W0-W1 配对宿主）；
> 3. 以 **新 Scope Amendment** 授权，而非沿 P1-1D 实施。

---

## 6. 提交 Human Gate

- 本文件 = **Decision Host / Semantic Boundary 只读审计（D1-D5）**。
- 请裁决：
  1. D1-D5 结论是否认可？
  2. 主判定 **Situation B**（生产 Decision Host 存在但语义域 = goal→DAG，与 Thinking 无接口；
     缺 Semantic Boundary，非缺接线）是否成立？
  3. 是否确认：P1-1D-B 若实施 = 新架构能力建设（新 Scope Amendment），
     且必须先冻结最小 Attribution Infrastructure 需求清单？

---

*本文件为 P1-1D 只读审计材料。未修改任何生产代码。任何实施需 Human Gate 明确授权。*
