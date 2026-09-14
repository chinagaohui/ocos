# OCOS P1-1D — Scope Assessment（生产现实审计）

> 状态：**P1-1D SCOPE ASSESSMENT — 只读审计完成，提交 Human Gate 裁决**。
> 承接：G4 PASS / FROZEN（Worldview → Thinking Consumption，2026-09-14）。
> P1-1D = **NOT AUTHORIZED**（Human Gate 终裁）；本文件 = 进入 P1-1D 前的生产现实审计，
> 回答 Human Gate 指定的第一个问题：
>
> > **"现在 OCOS 的生产 Thinking 输出，究竟在哪里被合法地消费为 Decision 输入？"**

---

## 0. 审计纪律

- 本文件为**纯只读审计**，未修改任何生产代码、未新增任何文件（除本文档）。
- 审计方法：源码追踪（Grep/Read）+ 生产宿主定位，所有结论附 `文件:行号` 证据。
- 审计范围：生产 Thinking 宿主（converse.py）、生产 Decision 链（decision/、cognitive_loop/、AgentRuntime、DecisionBridge）、W1 消费点。

---

## 1. 生产 Thinking 输出现状（ChatResponder）

### 1.1 生产 Thinking 宿主 = `ocos/interaction/converse.py::ChatResponder`

```text
converse.py::ChatResponder.respond()
  ├─ build_context()（L1791-1803 附近）→ 生产 Thinking Context/Prompt
  │    └─ L977-1003：G4 唯一生产接线（committed W1 → worldview 块 → Thinking input）
  ├─ TextGenerator / LLM provider → 生产回复（L1831-1882）
  └─ 回复生成后（L1968-1990）：
       ├─ _remember_conversation()          → 记忆沉淀
       ├─ session_manager.append_turn()      → 会话追加
       └─ record_decision_trace()            → P0-4 B4：只读 trace 记录
```

### 1.2 回复产出的唯一"决策"动作 = `record_decision_trace`（只读记录）

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

**关键事实**：
- `record_decision_trace` 把 reply 文本作为 `decision` 字段落 trace，`strategy/action/action_ids` 为空。
- 这是 **P0-4 实验证据链的记录**，**不产生任何决策执行**，不进入任何 Decision 生产链。
- **生产 Thinking 输出（reply）→ 无任何 Decision 消费点。** 回复只用于对话展示 + 记忆 + trace。

---

## 2. 生产 Decision 链现状

### 2.1 决策智能链（`decision/` 包）= **备用引擎，无生产消费者**

[decision/__init__.py L5-8](file:///workspace/ocos/decision/__init__.py#L5-L8)：

```text
接线状态（AUD-F13 选项 A, 2026-08-30）: 本组件链由 GAP-P1-1 接入
cognitive_loop/decision_pipeline（真实调用, decision_pipeline.py:73-114），
但该循环当前无生产消费者（备用引擎定位，见 cognitive_loop/__init__）。
生产 tick 决策 = AgentRuntime + DecisionBridge。组件本身完整可用。
```

[cognitive_loop/__init__.py L5-10](file:///workspace/ocos/cognitive_loop/__init__.py#L5-L10)：

```text
定位裁决（AUD-F13 选项 A, 2026-08-30）:
    本包 = 自治循环编排视图（AutonomousLoop 激活路径）。生产 tick 的
    决策路径 = AgentRuntime step7/8 + DecisionBridge（RuntimeKernel 驱动），
    不经过 LoopOrchestrator — 本链是"已接好线的备用引擎"，当前无生产
    消费者。
```

**关键事实**：
- `ContextBuilder → OptionGenerator → RiskEngine → ValueModel → DecisionProposal` 链完整存在，
  且由 `cognitive_loop/decision_pipeline.py:73-114` 真实调用。
- 但 cognitive_loop 本身 **无生产消费者**（不经过 LoopOrchestrator）。
- `DecisionPipeline.process()` 消费 `LoopContext`（perception_input / active_wisdom），
  **不消费 ChatResponder 回复**。

### 2.2 生产 tick 决策 = AgentRuntime + DecisionBridge

[agent_runtime.py L2213-2218](file:///workspace/ocos/agent/agent_runtime.py#L2213-L2218)：

```python
# R4-A: 真实任务优先经 DecisionBridge 执行
bridge = getattr(self, "_decision_bridge", None)
if bridge is not None:
    dag_result = bridge.execute_dag_task(task)
```

[agent_runtime.py L2452-2461](file:///workspace/ocos/agent/agent_runtime.py#L2452-L2461)：

```python
# ── R4-A: DecisionBridge — 决策输出 → 真实执行 (AUTO) / 待批 (ASK) ──
decision_bridge = getattr(self, "_decision_bridge", None)
last_result = getattr(self, "_last_core_loop_result", None)
if decision_bridge is not None and last_result:
    report = decision_bridge.process(last_result)
```

[execution/bridge.py L334-404](file:///workspace/ocos/execution/bridge.py#L334-L404)：

```python
def process(self, core_loop_result: dict, attention_focus: str = "") -> BridgeReport:
    """处理一次 core_loop 决策输出 (step 7 → step 8 调用)。"""
    text = self._extract_decision_text(core_loop_result)   # ← 输入来自 core_loop_result
    ...
    actions = self._dispatcher.interpret_decision(text, attention_focus)
```

**关键事实**：
- `DecisionBridge.process()` 的输入 = `core_loop_result`（core_loop 决策输出），
  `_extract_decision_text` 递归取 `action_result.based_on` 文本。
- `DecisionBridge.execute_dag_task()` 输入 = TaskDAG task。
- **DecisionBridge 输入源 = AgentRuntime 的 core_loop / DAG 任务，与 ChatResponder 回复无交集。**

### 2.3 `_last_core_loop_result` 生产赋值点 —— 已永久停用

[agent_runtime.py L2411-2425](file:///workspace/ocos/agent/agent_runtime.py#L2411-L2425)：

```python
# ── Fallback: original cognitive loop (or idle if not booted) ──
# FIX-01 + P0-C (2026-09-11): **永久停用** legacy cognitive loop fallback.
_enable_cognitive_loop = False
if _enable_cognitive_loop and hasattr(self, "loop") and self.loop is not None:
    ...
    self._last_core_loop_result = result if isinstance(result, dict) else {}
```

**关键事实**：
- `_last_core_loop_result` 唯一赋值点在 legacy cognitive loop fallback 内，而该 fallback **已永久停用**
  （`_enable_cognitive_loop = False`，环境变量开关已删除）。
- 因此 `DecisionBridge.process()` 在生产 tick 上**基本不会触发**（last_result 恒为空）。
- 生产上真实生效的 Decision 执行 = `DecisionBridge.execute_dag_task()`（DAG 任务路径）。

---

## 3. W1 → Thinking → Decision 真实路径审计（核心结论）

### 3.1 逐段审计结果

| 链段 | 是否存在 | 证据 | 状态 |
| --- | --- | --- | --- |
| W1 → Thinking Input | ✅ 存在 | converse.py L977-1003（G4 唯一生产接线） | **G4 PASS/FROZEN** |
| Thinking Input → Reasoning | ✅ 存在 | G4-E 机制证据 + P-E1/P-E2 生产 prompt 差分 | **G4 PASS/FROZEN** |
| Thinking 输出 → Decision 消费 | ❌ **不存在** | converse.py L1968-1990：回复仅记忆+会话+只读 trace；无任何 Decision 组件消费 reply | **断开** |
| Thinking → decision/ 包链 | ❌ 不存在 | decision/__init__ L7-8：cognitive_loop 无生产消费者 | **断开** |
| Thinking → AgentRuntime core_loop | ❌ 不存在 | agent_runtime L2411-2416：legacy fallback 永久停用 | **断开** |
| Thinking → DecisionBridge | ❌ 不存在 | bridge.process 输入 = core_loop_result，非 ChatResponder reply | **断开** |

### 3.2 唯一"决策侧读 Self"的旁路（需显式排除）

[execution/bridge.py L2410-2436](file:///workspace/ocos/execution/bridge.py#L2410-L2436)：

```python
def _self_knowledge_hint(self, description: str) -> str:
    # 仅当任务文本含 复盘/总结/自我/能力/数字生命/成长/反思 等关键词才触发
    if not any(k in text for k in ("复盘", "总结", "差距", "自我", ...)):
        return ""
    facts: list[str] = ["【自我能力事实（实测真值，分析自身必须引用）】"]
    from ocos.self.self_state import get_self_projection
    s2 = get_self_projection(self._db_path)
    if s2 is not None:
        facts.append(s2.render())        # ← 整 S2 render，非 worldview 块
```

**关键事实**：
- DecisionBridge 自省类任务会读 `S2.render()`（整 S2 文本）注入决策 prompt。
- 这是 **S2 整体 render**，**不是 G4 的 worldview 结构化块**（`get_committed_worldview()`）。
- 触发条件 = 关键词匹配（复盘/总结/自我等），非 worldview 驱动的决策。
- **结论：这不算 W1→Decision 接线**，但它是 P1-1D 必须注意的既有 S2 决策侧读取通道。

### 3.3 核心结论

> **生产 Thinking 输出（ChatResponder 回复）当前不存在任何合法 Decision 消费点。**
>
> `W1 → Thinking Input`（G4，FROZEN）与 `Thinking → Decision`（P1-1D 目标）之间
> **在真实生产路径上没有接线**。断开点 = ChatResponder 回复产出后，只走
> 记忆 + 会话 + 只读 trace，不进入 decision/ 包、不进入 AgentRuntime core_loop、
> 不进入 DecisionBridge。

---

## 4. Behavior Delta（Y ≠ Z）验证宿主审计

### 4.1 P0-4 现有宿主（可复用的事实链）

- `record_decision_trace`（converse.py L1981-1987）：`thinking_trace_id → decision_id → action_ids → Y`，
  已把 reply 作为 `decision` 落 trace。这是 P0-4 实验 Join 的既有宿主。
- 但 `action_ids=()` / `strategy=""` / `action=""` —— **尚未接任何 Behavior/执行动作**。

### 4.2 合法 Behavior Delta 验证宿主候选（只读盘点，不实施）

| 候选宿主 | 现状 | 可验证性 |
| --- | --- | --- |
| `DecisionBridge.execute_dag_task` | 生产生效，输入 = DAG task | 可产生真实行为，但输入不来自 Thinking 输出 |
| `DecisionBridge.process` | 生产基本不触发（legacy fallback 停用） | 输入 = core_loop_result |
| `converse.py respond()` | 生产生效，输入 = 用户消息 | 输出 = 回复文本（可作 Y，但无 action_ids） |
| `record_decision_trace` | 生产生效，只读 | 已记录 decision=reply，缺 action_ids 与行为差分 |

**审计结论**：当前**不存在**"生产 Thinking 输出 → 决策 → 行为"的完整宿主。
P0-4 的 Y 目前是 reply 文本，不是行为；action_ids 为空。

---

## 5. 最小授权范围建议（Scope 候选，待 Human Gate 裁决）

依据 Human Gate 指示："如果生产链已经存在，就只接真实链；如果不存在，再做最小 Scope Amendment。"

### 5.1 生产现实结论

1. 生产 Thinking 输出（converse reply）→ Decision：**链不存在**。
2. 生产 Decision 宿主存在（AgentRuntime + DecisionBridge），但输入源与 Thinking 输出无交集。
3. decision/ 包链存在但无生产消费者（备用引擎）。

### 5.2 Scope 选项（不实施，仅供裁决）

| 选项 | 内容 | 风险 | 建议 |
| --- | --- | --- | --- |
| **A. 只接真实链** | 把 worldview 块接入 DecisionBridge 的决策 prompt（DAG 任务执行时消费） | 需证明"世界观看进决策输入"且不改变 DAG 任务语义；跨 G4 冻结边界 | 不推荐直接做 |
| **B. 最小 Scope Amendment** | 在 `record_decision_trace` 的 trace 中补充 action_ids（把 reply 的 USE 协议动作行解析为 action_ids） | 只补证据链，不改决策语义；P0-4 已授权只读记录 | **候选**（若目标=Behavior Delta 可审计） |
| **C. 保持 NOT AUTHORIZED** | 维持 P1-1D 冻结，不实施 | 无风险 | **默认**（证据不足时） |

### 5.3 本审计的推荐结论

- **当前证据强度不足以授权任何 P1-1D 实施**。生产 Thinking 输出→Decision 的接线不存在，
  且现有宿主（AgentRuntime/DecisionBridge）的输入语义与"Thinking 输出消费"不匹配。
- 若 Human Gate 认为 P1-1D 的阶段性目标只是"可审计的 Behavior Delta 证据链"，
  选项 B（trace 补 action_ids）是最小、只读、与 P0-4 兼容的候选。
- 任何选项均需**单独授权**，不得自动推进。

---

## 6. 提交 Human Gate

- 本文件 = **P1-1D Scope Assessment（生产现实审计）**。
- 请 Human Gate 裁决：
  1. 审计结论是否认可（生产 Thinking 输出当前无合法 Decision 消费点）？
  2. Scope 选项 A / B / C 是否选择其一，或要求补充审计？

---

*本文件为 P1-1D 只读审计材料。未修改任何生产代码。下一步行动需 Human Gate 明确授权。*
