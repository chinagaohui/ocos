# OCOS P1-1D — Decision Host / Semantic Boundary Audit（只读）

> 状态：**只读审计完成，提交 Human Gate 裁决**。
> 承接：P1-1D Scope Assessment = PASS / FROZEN（2026-09-14）；P1-1D 实施 = NO-GO。
> 本审计 = Human Gate 唯一开放的下一步，目的（非接线）：
>
> > **确定 OCOS 当前哪个生产组件"理论上有资格成为 Thinking → Decision 的宿主"。**
>
> 审计问题（Human Gate 指定 7 项）：
> 1. `DecisionRecord` 真正由谁创建
> 2. 有没有除 `converse.py` 之外的生产 DecisionRecord producer
> 3. `thinking_trace_id → decision_id` 在生产环境是否真实存在
> 4. `DecisionBridge` 接收的对象语义到底是什么
> 5. `TaskDAG` 是"已经做出的决策"，还是"决策结果的执行载体"
> 6. 有没有现存的结构化 `DecisionCandidate / DecisionContext / DecisionInput` 可以承接 Thinking
> 7. 如果不存在，是否意味着需要新增一个真正的 **Thinking→Decision boundary**

---

## 0. 审计纪律

- **纯只读审计**：未修改任何生产代码、未新增任何文件（除本文档）。
- 冻结线不触碰：`self_state.py` / `worldview_read_adapter.py` / `converse.py`（G4 接线）、
  `decision_pipeline.py` / `agent_runtime.py` / `bridge.py` / `context_builder.py`。
- 结论附 `文件:行号` 证据（I2）。同名不同义的方法做了**语义区分**，不混淆。

---

## 1. `DecisionRecord` 真正由谁创建

### 1.1 唯一 P0-4 identity 链生产者

`DecisionRecord`（`thinking_trace_id` 同链）定义于 [decision_trace.py L46-57](file:///workspace/ocos/self/decision_trace.py#L46-L57)。
生产代码中创建它的**唯一调用点**：

- [converse.py L1982](file:///workspace/ocos/interaction/converse.py#L1982)：`record_decision_trace(...)`（P0-4 B4 钩子），
  字段 = `decision=reply[:1000], strategy="", action="", action_ids=()`。
- `DecisionTraceStore.record_decision_contemporaneous`（[decision_trace.py L131-192](file:///workspace/ocos/self/decision_trace.py#L131-L192)，P0-4A 原子记录）
  **无任何生产调用者**（仅测试使用）。

### 1.2 同名不同义（必须区分，防误判）

| 模块 | 方法 | 语义 | 与 DecisionRecord 关系 |
| --- | --- | --- | --- |
| `platform/trace_engine.py` L323 | `record_decision_trace` | 平台审计 TraceEngine（InMemoryTraceStore），参数 = decision_id/goal_id/status/outcome | **不同的表/模块**，注入接口，非 P0-4 链 |
| `goal/store.py` L367 | `record_decision` | 把 decision_id 挂到 goals 行的 `decision_refs` | goal 侧引用，不产生 DecisionRecord |
| `cognitive_loop/decision_pipeline.py` L116 | `record_decision` | 备用链内记录 | 无生产消费者 |
| `opentale_bridge` / `cognitive_timeline` | `record_decision` | 其他子系统记忆/时间线 | 无关 |

**结论（Q1）**：P0-4 identity 链的 `DecisionRecord` 生产上**仅由 `converse.py::respond()` 创建**，
且内容是"回复记录"而非"决策语义"。

---

## 2. 除 converse.py 之外的生产 DecisionRecord producer

全库 Grep（排除 tests）：`record_decision_trace` 的生产调用者 = **converse.py L1982 唯一一处**；
`record_decision` 的生产调用者（goal/store、cognitive_loop 等）均属上文 1.2 的不同语义模块。

**结论（Q2）**：**不存在**第二个生产 DecisionRecord producer。
ThinkingTrace / DecisionRecord 同链 identity 目前是对话回复路径的独有产物。

---

## 3. `thinking_trace_id → decision_id` 在生产环境是否真实存在

生产唯一路径（converse.py::respond）确实形成该链：

```text
L1808-1812  record_thinking_trace()   → thinking_trace_id（S2 存在时）
L1979-1990  record_decision_trace()   → decision_id（同 thinking_trace_id）
```

- 存在条件：respond() 被调用 **且** committed S2 存在。
- 数据库约束：[schema.py L334/344/353](file:///workspace/ocos/storage/schema.py#L334-L353)
  （thinking_trace_id 主键 / decision 外键索引）。
- **但语义上**：这是"一次对话回复"的 identity，不是"一次决策"的 identity——
  `decision=reply[:1000]`、`strategy/action/action_ids` 恒空（[converse.py L1982-1985](file:///workspace/ocos/interaction/converse.py#L1982-L1985)）。

**结论（Q3）**：`thinking_trace_id → decision_id` 生产链**存在但仅具记录语义**，
未承载任何决策/动作身份。AgentRuntime / DecisionBridge 路径**不产生**该链。

---

## 4. `DecisionBridge` 接收的对象语义

[bridge.py L334-341](file:///workspace/ocos/execution/bridge.py#L334-L341)：

```python
def process(self, core_loop_result: dict, attention_focus: str = "") -> BridgeReport:
    """处理一次 core_loop 决策输出 (step 7 → step 8 调用)。"""
    text = self._extract_decision_text(core_loop_result)   # 递归取 action_result.based_on 文本
```

- **`process()` 的输入语义** = legacy core_loop 决策输出 dict（决策文本）。
  该路径输入源 `_last_core_loop_result` 唯一赋值点（[agent_runtime.py L2421](file:///workspace/ocos/agent/agent_runtime.py#L2421)）
  在已永久停用的 fallback 内（L2416）→ **生产不触发**。
- **`execute_dag_task(task)` 的输入语义**（[bridge.py L405-406](file:///workspace/ocos/execution/bridge.py#L405-L406)）
  = PlanTask（TaskDAG 节点），按任务类型/描述解释为动作并执行（只读类 AUTO / 写类 ASK）。

**结论（Q4）**：DecisionBridge 的两个入口语义分别是"core_loop 决策文本"与"规划任务"，
**均不是 Thinking 输出**。它接收的是"决策结果"，不是"待决策的认知产物"。

---

## 5. `TaskDAG` 的语义：决策，还是执行载体

来源 = `_tick_step_planning_trigger`（[agent_runtime.py L1311-1405](file:///workspace/ocos/agent/agent_runtime.py#L1311-L1405)）：

```text
Goal(PENDING, HUMAN 优先) 触发
  ├─ caller=chat → 单任务直执行（L1370-1381，goal 描述即任务）
  └─ 其他       → TaskDecomposer.decompose(ug)（L1383，模板分解）
self._active_dag = dag（L1400）→ 逐任务 DecisionBridge.execute_dag_task（L2218）
```

**结论（Q5）**：`TaskDAG` = **规划阶段已经做出的"做什么"决策产物（执行计划）→ 执行载体**。
"决策"发生在 Goal 受理/编译/分解时刻；DAG 不是待决策候选。生产上真正的决策语义位于
**goal→plan 层**，与 ChatResponder 的 Thinking 输出**完全分离**。

---

## 6. 现存结构化承接载体盘点

| 载体 | 位置 | 字段 | 能否承接 Thinking 输出 |
| --- | --- | --- | --- |
| `DecisionContext` | [decision_types.py L30-54](file:///workspace/ocos/decision/decision_types.py#L30-L54) | goal_summary / self_summary / wisdom_hints / world_snapshot / constraints | ❌ 无 thinking / worldview 槽位 |
| `DecisionOption` | [decision_types.py L71-82](file:///workspace/ocos/decision/decision_types.py#L71-L82) | 选项描述/置信/风险/价值 | ❌ 是决策输出候选，非输入载体 |
| `DecisionProposal` | decision_types.py | 最终提案 | ❌ |
| `WorldViewContextBlock` | worldview_read_adapter.py | G4 结构化块 | ❌ 只进 ChatResponder Thinking context，不进任何 decision 链结构 |
| `DecisionCandidate / DecisionInput` | — | **不存在此类** | — |

且 `decision/` 包整体**无生产消费者**（[decision/__init__.py L5-8](file:///workspace/ocos/decision/__init__.py#L5-L8)）。

**结论（Q6）**：**不存在**任何现存结构化载体能承接"Thinking 输出 → Decision 输入"。
最接近的 `DecisionContext` 由 ContextBuilder 从 goal/self/wisdom/world 四层组装，
其 `self_summary` 与 G4 worldview 块**不是同一物**（且 ContextBuilder 无生产消费者）。

---

## 7. 结论：是否需要新增 Thinking→Decision boundary

**需要（若未来授权）**。现有生产架构不存在合法接口：

1. 三条候选消费链（decision/ 包、AgentRuntime core_loop、DecisionBridge）输入语义
   均与 Thinking 输出无交集（Q4/Q5）。
2. 无结构化输入载体（Q6），且该包无生产消费者。
3. 唯一 Thinking 侧产物（回复 + 只读 trace）不构成决策语义（Q1/Q3）。

因此 P1-1D-B（Thinking → Decision）若实施，**不是"补现有接口的线"，而是新增一条
认知→决策架构接线**（新的 Thinking→Decision boundary），属于**新架构 Scope Amendment**，
超出"最小接线"。

且必须配套 Q4 归因基础设施（Scope Assessment 确认的缺口）：
- trace 增加 worldview 快照（domain/judgment/frame/claim_id，append-only）；
- 动作级身份（action_ids 非空）；
- W0/W1 配对决策宿主（ΔDecision 归因）。

---

## 8. 提交 Human Gate

- 本文件 = **Decision Host / Semantic Boundary 只读审计（7 项）**。
- 请裁决：
  1. 七项结论是否认可？
  2. "生产 Decision 语义宿主 = goal→plan 层（AgentRuntime + TaskDAG + DecisionBridge），
     与 ChatResponder Thinking 完全分离"这一判定是否成立？
  3. 若成立 → P1-1D-B 需新增 Thinking→Decision boundary（新架构 Scope Amendment）；
     是否要求在授权前先冻结"最小 Attribution Infrastructure"需求清单？

---

*本文件为 P1-1D 只读审计材料。未修改任何生产代码。任何实施需 Human Gate 明确授权。*
