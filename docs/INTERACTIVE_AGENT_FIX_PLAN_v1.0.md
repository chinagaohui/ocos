# OCOS Interactive Agent 可落地修复计划 v1.0

> 依据《OCOS Interactive Agent Reality Audit v1.0》的全部结论制定。
> 本文件只描述**改什么、在哪改、如何验收**，不写实现细节级代码。
> 原则：**先接通已存在的能力，不新增认知模块**。大部分修复是"找对调用点"，
> 而不是"发明新器官"。

---

## 0. 审计基线（本计划的事实依据）

| 项 | 审计结论 |
|---|---|
| 交互生产链 | 对话回复 = `ChatResponder.respond` 单次 LLM 文本生成；任务执行 = `DecisionBridge` 单次 LLM 命令转换。两条管线互不咬合 |
| 认知循环 | MasterAgent 兜底循环每 idle tick 空转（reasoning/decision/act 全 stub），不产生用户可见输出 |
| 真实有效的注入 | 仅 3 项：最近对话转录、goal_result、compile_goal 意图路由（+ wisdom / self_knowledge） |
| 断链总数 | Critical Disconnected = 5；Decorative/Dormant = 14 |
| 审计读数 | 25 capabilities · 12 used · 7 effective · 14 dormant · 5 disconnected |

**修复目标读数**：effective 7 → **≥12**；dormant 14 → **≤6**；disconnected 5 → **≤2**。

---

## 1. 修复总原则

1. **只读审计 → 改动最小化**：每个 FIX 优先找"已有能力的缺失调用点"，而非新建模块。
2. **行为可观测优先**：任何修复必须能在 TUI 对话流中直接看到行为变化（记忆注入 → 对话文本；执行回流 → 面板/追问回答）。
3. **不破坏既有闭环**：goal 状态机、执行-反馈-重试链、goal_result 回推是已验证有效的资产，只扩展不推翻。
4. **可回滚**：每个 FIX 尽量以独立开关/独立函数落地，方便逐项回退。
5. **验收 = 真机场景**：测试通过 ≠ 生产链有效；每个 FIX 给真机验证脚本（§6）。

---

## 2. 修复清单总览

| FIX-ID | 优先级 | 问题（审计编号） | 一句话方案 | 涉及文件 |
|---|---|---|---|---|
| FIX-01 | P0 | 认知循环空转装饰（P0-4） | 生产默认停用 idle 兜底循环 | agent_runtime.py |
| FIX-02 | P0 | 元认知置信链构造器死（P0-3） | 重写 `_load_rules` 为确定性 DB 统计 | daemon/factory.py, learning/metacognition.py |
| FIX-03 | P0 | say 入口绕过 respond_auto（P1-5） | daemon 收件箱改用 `respond_auto` | daemon/__init__.py |
| FIX-04 | P0 | goal 状态/结果不回流对话（P0-2） | build_context 注入 session 关联目标的真实状态与多条结果 | converse.py |
| FIX-05 | P0 | "继续/追问"无 Goal grounding（P1-4） | continue/question 分支实际查询 GoalStore 并锚定 goal_id | converse.py |
| FIX-06 | P1 | Learning 产物不注入决策（P1-1） | recall 传 learning_rules；技能 registry 落库 | converse.py, recall.py, factory.py |
| FIX-07 | P1 | Reflection 不改变下一次决策（P1-2） | 失败/反思结果注入下一次规划与对话 prompt | bridge.py, converse.py |
| FIX-08 | P1 | Learning 不落库（进程即失） | 生产 learning 持久化（rules/skills 入库） | factory.py, learning/ |
| FIX-09 | P1 | Recall 检索质量差（P1-3） | 语义/模式/经验召回加相关性过滤（中文 bi-gram） | memory/recall.py |
| FIX-10 | P1 | World/Self 模型不参与推理（P1-6） | 世界状态可用时注入 build_context；自我演化摘要入对话 | converse.py, factory.py |
| FIX-11 | P1 | 对话无工具反馈闭环 | 受理确认 + 追问引用真实结果（依赖 FIX-04/05） | converse.py |
| FIX-12 | P2 | 记忆窗口过窄 | 最近对话 6→10 轮（按 token 预算动态） | converse.py |
| FIX-13 | P2 | InteractionContext 未接入 | ChatResponder 统一走 InteractionContext 访问 stores | context.py, converse.py |
| FIX-14 | P2 | goal 无结构化 progress | GoalStore 增加 progress 字段并注入对话 | goal/store.py, converse.py |
| FIX-15 | P3 | continuity 仅内视可见 | 非空时并入 build_context | converse.py |
| FIX-16 | P3 | bi-gram 检索为启发式 | 有 embedding 则语义召回，否则调阈值 | converse.py, recall.py |
| FIX-17 | P2 | 主动输出断在回调（P1-6b） | 生产注入 proactive 回调到 outbox | factory.py, master_agent.py |

---

## 3. 分阶段实施路线

```
Phase 0  止血（低风险，1 个批次）
  FIX-01 · FIX-03 · FIX-02(Option A)
  → 立即消除空转浪费与入口漂移，修复死链路
  ↓
Phase 1  对话↔执行咬合（核心行为改变，优先）
  FIX-04 · FIX-05 · FIX-11
  → "继续/结果呢/让 你分析…"从猜变查；执行结果回流对话
  ↓
Phase 2  认知注入（让已有器官真正起作用）
  FIX-08(前置) → FIX-06 · FIX-07
  → 学习/反思结果进入下一次决策与回复
  ↓
Phase 3  感知与主动性
  FIX-09 · FIX-10 · FIX-17
  → 召回质量、世界/自我模型、主动输出可达用户
  ↓
Phase 4  优化（不阻塞前 3 阶段）
  FIX-12 · FIX-13 · FIX-14 · FIX-15 · FIX-16
```

依赖关系：`FIX-08` → `FIX-06`、`FIX-02(Option B)`；`FIX-04/05` → `FIX-11`；`FIX-09` 独立。

---

## 4. 逐项修复详细方案

### FIX-01 [P0] 停用空转认知循环兜底

- **现象**：daemon 每个无任务 tick 都跑一轮 MasterAgent 认知循环，输出全是 stub（"Reasoning unavailable"），白耗 CPU 且掩盖"认知在跑"的假象。
- **证据**：`ocos/agent/agent_runtime.py:1304-1313`（`self.loop.execute_single()` fallback）；`master_agent.py` think/decide/act 均 stub；DecisionBridge.process 将其降为 NOOP 仅审计（`bridge.py:442-447`）。
- **根因**：fallback 路径设计为"无 DAG 时跑认知循环"，但该循环从未接 LLM、从未接工具、输出从不回显——它是历史遗留装饰。
- **方案**：
  1. 在 `agent_runtime.py:1305` 处加环境开关 `OCOS_ENABLE_COGNITIVE_LOOP`（默认 `0`）。
  2. 默认关闭时，step 7 fallback 直接返回 `{"step": 7, "name": "core_loop", "status": "idle"}`，不执行 `execute_single()`。
  3. 保留 DecisionLoop 代码与开关（供未来真正接 LLM 的认知循环使用），不删除。
- **风险**：低。该路径当前不产生任何用户可见行为；`_last_core_loop_result` 清空后 step 8 的 bridge.process 跳过即可（已有 `if decision_bridge is not None and last_result` 判空）。
- **验收**：
  - 日志不再出现 "Reasoning unavailable" stub 记录；
  - `get_stability_report()` 的 cycles 正常增长，belief 提取不受影响（belief 提取在 step 10，独立于 step 7）；
  - 真机：TUI 对话、目标执行、结果回推全部正常。

---

### FIX-02 [P0] 修复元认知置信链（构造器死链路）

- **现象**：`attach_confidence_source` 已装配，但置信门永远不会触发——写类任务从不因低置信升级 ASK。
- **证据**：`ocos/daemon/factory.py:24-35` `_load_rules` 调 `LearningEngine(db_path=db_path)`；而 `ocos/engines/learning_engine.py:61-65` 构造签名为 `__init__(self, event_bus, working_memory)` —— **无 db_path 参数**，必然 TypeError → 返回 `[]`。且 `engine.list_models()`（factory.py:29）**方法不存在**。双重死。
- **根因**：`_make_confidence_source` 是"想从持久化学习规则读置信"的意图，但生产 learning 引擎是内存实例（factory.py:100），且没有读取接口。
- **方案**：
  - **Option A（本期推荐，确定性）**：`_load_rules` 改为直接查 SQLite：统计 `episodes` 表 `action='goal_result'` 中与当前任务 bi-gram 重叠的近期条目的 success/fail 数，构造 `[{task_pattern, success_rate, success_count, fail_count}]`。复用 `bridge._prior_task_results` 的同款检索手法，零依赖 LearningEngine。
  - **Option B（Phase 2 后）**：FIX-08 落库后，从 learning_models/rules 表读取。
- **风险**：低。规则为空时 `CapabilityConfidence.evaluate` 返回 "no learning history" 不干预（现状即安全兜底）。
- **验收**：单测：构造含失败历史的 task_pattern，`evaluate` 返回 `should_escalate=True`；真机：写类任务在历史低成功率下进入待批而非 AUTO。

---

### FIX-03 [P0] 统一 say 入口为 respond_auto

- **现象**：`ocos say`（收件箱路径）与 web/TUI 行为不一致——任务类消息在 say 下只回文本、不建目标、不执行。
- **证据**：`ocos/daemon/__init__.py:531` `self._responder.respond(msg["content"])`；对比 web 路由 `ocos/interaction/api/routes/converse.py:44-47` 用 `respond_auto`。
- **根因**：daemon 收件箱路径未升级到 UX-H 的"对话即路由"。
- **方案**：
  1. `daemon/__init__.py:531` 改为 `out = self._responder.respond_auto(msg["content"], session_id=msg.get("session_id", "say"))`。
  2. `UserInbox.reply` 回写时把 `out["goal_id"]` / `out["kind"]` 追加进回复正文或 reply 记录字段（TUI 面板依赖 reply 文本即可）。
- **风险**：低。respond_auto 内部对 question/continue/task 均有兜底。
- **验收**：`ocos say "分析宿主机"` → 回复含"已受理为目标 GOAL-xxx"，随后 daemon 认领并执行，`/ocos/outbox` 出现 goal_result 回推（与 TUI 行为一致）。

---

### FIX-04 [P0] Goal 状态/结果结构化回流对话

- **现象**：对话层只看到"活跃目标: 前 30 字"和"第一条 goal_result"，无目标 id/状态/阶段/最近结果——用户问"结果呢"时 LLM 只能碰运气。
- **证据**：`converse.py:140-143`（`description[:30]` 单字符串）；`converse.py:155-161`（只注入第一条 goal_result，截断 1000 字）。
- **根因**：`build_context` 以"读一眼状态"替代"结构化上下文对象"，且无 session→goal 关联。
- **方案**：
  1. `build_context` 新增 `_session_goal_context(session_id)`：
     - 按 session_id（FIX-8 已贯穿记忆，`converse.py:437`）查最近活跃/最近完成目标；
     - 每个目标注入 `id / status / 描述[:60] / 最近一条 goal_result[:400]`；
     - 与当前消息的"最近对话"并行拼接，替换现有"活跃目标+第一条结果"的弱注入。
  2. 保留全局活跃目标行（兜底），但增加"本会话目标"节。
  3. goal_result 注入改多条（最近 2-3 条，各截断）。
- **风险**：低-中。prompt 变长 → 控制在 800 字内；注意 `_session_goal_context` 查询失败时降级为现状（已有 try/except 模式）。
- **验收**：Scenario B：连续对话中"分析宿主机"后追问"结果呢"，回复引用具体 goal_id 与真实 stdout 摘要（不再泛泛）。

---

### FIX-05 [P0] "继续/追问"的 Goal grounding

- **现象**：`compile_goal` 把"继续/结果呢"分类为 continue/question 后，只给一句文本提示（"依据最近对话作答"），没有真实目标可锚定。
- **证据**：`converse.py:700-702`（goal_note 仅文本）；`converse.py:561-629` compile_goal 不产出 goal_id 引用。
- **根因**：continue 语义停留在 prompt 暗示层，未落到结构化 Goal 查询。
- **方案**：
  1. `respond_auto` 的 question/continue 分支：实际调用 `GoalStore.load_active()` + 最近完成目标，取最近 1 个与本 session 关联（或描述与最近对话重叠）的目标。
  2. 构造结构化注记注入 `respond()`：
     ```
     【当前任务上下文】
     goal_id=GOAL-xxx  status=ACTIVE  描述=...
     最近结果: <goal_result 前 400 字>
     ```
  3. `goal_note` 同时携带该 goal_id，供 LLM 直接引用。
- **风险**：低。查不到目标时退化为现状提示。
- **验收**：输入"继续刚才那个任务"，回复中出现具体 goal_id、状态与最近结果；且不再新建重复目标（`_find_duplicate_goal` 已有，保持）。

---

### FIX-06 [P1] Learning 产物注入决策（learning → behavior）

- **现象**：dream 产出的 `LearningModel.rules` 与技能提案无人消费；对话 recall 调用 `format_for_prompt` 时未传 learning_rules。
- **证据**：`master_agent.py:1579-1612`（`_fast_path_learning`/`grow_skills_from_episodes`）；`converse.py:376-377`（`MemoryRecall.format_for_prompt(context, limit=6)`，无 rules）；`recall.py:238-301`（`recall_cognitive` 已支持 `learning_rules` 参数，但无人使用）。
- **根因**：学习端与消费端都是"各自实现好了但中间没有接线"。
- **方案**：
  1. 新增 `load_learning_rules(db_path)`（读 FIX-08 落库的 rules；Phase 2 前先读 pattern 表兜底）。
  2. `converse.py:_recall_context` 改调 `MemoryRecall.recall_cognitive(context, limit=6, learning_rules=load_learning_rules(...))`，把 `conflict_set`（成功/失败冲突组）格式化注入 prompt。
  3. `factory.py:build_master_agent` 为 MasterAgent 注入 `set_skill_registry(持久化实现)`，使 `grow_skills_from_episodes` 从"仅 proposal"变为"真实提交"（`master_agent.py:866-912`）。
- **风险**：中。rules 质量依赖学习器；注入前加"仅成功经验"过滤（沿用 FIX-4v2 的负反馈教训，`bridge.py:892+`）。
- **验收**：第二次同类任务时，对话/规划 prompt 出现"相关经验/规则"节；Skill Reuse 矩阵从 D 升为 A。

---

### FIX-07 [P1] Reflection 改变下一次决策

- **现象**：反思只写审计 JSON，从不影响下一次规划/回复。
- **证据**：`bridge.py:442-447`（`_handler_reflect` 写文件）；`master_agent.py:1060-1101`（reflect 返回 stub）。
- **根因**：反思结果没有"下一次 prompt 消费点"。
- **方案**：
  1. 执行链：`_replan_failed_task`（`agent_runtime.py:1072-1142`）已回注【执行反馈】到任务描述——扩展为同时注入 `FailureDiagnoser.cause` 与上一次规划的原始输出，使重试 LLM 看到"做了什么、为什么失败"。
  2. 对话层：`self_improve` 提案被批准后（`converse.py:330-333` `apply_self_upgrade`），把最近一次批准的自省摘要作为"反思节"注入下轮 `build_context`（复用 self_knowledge 通道，标注来源=reflection）。
- **风险**：中。注意控制注入量，避免 prompt 污染。
- **验收**：Scenario D：构造失败任务，第二次重试的规划输出不再原样重放（对比第一次的动作序列）。

---

### FIX-08 [P1] Learning 持久化（rules/skills 落库）

- **现象**：生产装配的 learning 引擎是内存实例，进程退出即丢；metacognition 与 recall 无库可读。
- **证据**：`factory.py:100` `"learning_engine": LearningEngine(eb, wm)`（内存）；dream 结果仅在本进程。
- **根因**：learning 没有持久化存储。
- **方案**：
  1. 新增 `learning_models` 表（model_id, strategy, created_at, rules_json, skills_json）。
  2. dream 巩固后（`daemon/__init__.py:318-322` 触发点）把 `LearningModel.rules` 序列化写库；boot 时读回注入内存引擎（或按需加载）。
  3. FIX-02(Option B) / FIX-06 从该表读取。
- **风险**：中。schema 变更需迁移；写库失败降级为内存（不阻塞 daemon）。
- **验收**：重启 daemon 后 `load_learning_rules(db_path)` 仍返回上次 dream 的 rules；metacognition 门开始真实生效。

---

### FIX-09 [P1] Recall 检索质量（相关性过滤）

- **现象**：语义召回按英文关键词切词（中文无效）；模式召回忽略 query（`query_highest_confidence` 与上下文无关）；经验召回只看最近。
- **证据**：`recall.py:110-146`（`_extract_keywords` 英文 stopwords）；`:148-167`；`:169-189`。
- **根因**：召回层没有"与当前上下文的相关性过滤"，只是按置信/时间取 top-k。
- **方案**（复用 `converse.py:384-415` 已验证的中文 bi-gram 手法）：
  1. `_recall_semantic`：对 entry.content 与 context 做字符 bi-gram 重叠度过滤（阈值 0.25），按重叠度重排序，替换英文关键词路径；英文关键词作为兜底保留。
  2. `_recall_patterns`：仅保留 description 与 query 有重叠的模式。
  3. `_recall_experience`：`get_recent` 后按 lesson 文本与 query 重叠过滤。
  4. `recall()` 统一在排序后加 relevance 下限（如 < 0.2 丢弃）。
- **风险**：低-中。召回可能变少 → 需在真机确认"相关召回不消失"（用例见 §6 Scenario A）。
- **验收**：中文多轮场景召回命中率提升；`/ocos/introspect` 与对话中"相关记忆"节不再全是噪音。

---

### FIX-10 [P1] World / Self 模型进对话上下文

- **现象**：世界状态只在空转循环被消费（默认空）；自我模型只打日志。
- **证据**：`master_agent.py:927-943`（`world_context` 默认 available=False）；`daemon/__init__.py:356-364`（SelfMonitor 仅 log）。
- **根因**：感知/自我演化与对话层无接口。
- **方案**：
  1. `build_context` 增加世界状态节：`load_world_summary(db)` 有数据才注入（零传感器时为空串，保持零噪音）。
  2. SelfMonitor 演化有动作时，把 `result.message` 摘要写入最近一次 goal_result 或 self_knowledge 通道，使对话能引用"自我演化"。
- **风险**：低。无传感器环境 prompt 不膨胀（关键约束）。
- **验收**：注入文件传感器后，对话能引用文件系统观察；无传感器时上下文与现状一致。

---

### FIX-11 [P1] 对话层工具确认 + 工具反馈闭环

- **现象**：对话回复从不涉及工具；执行结果不回流对话推理（只有面板回推）。
- **证据**：`converse.py:497-545` respond 无工具调用；执行结果经 `_record_goal_result` 落 episode（`agent_runtime.py:1020-1062`）后不再进入对话推理。
- **根因**：对话与执行是两条独立 LLM 管线，中间只有"episode 落库"这个被动通道。
- **方案**（依赖 FIX-04/05 的存储支撑）：
  1. `respond_auto` task 分支：回复确认受理时带上计划（已有雏形，`converse.py:694-699`）——增强为引用"该目标将执行的动作类型"。
  2. 用户下轮追问"结果呢/好了吗"→ 命中 FIX-05 的 goal grounding → 注入该目标真实 goal_result（stdout 摘要），使"工具结果 → 对话推理"成立。
- **风险**：中。这是行为改变最大的项，需防注入过长（结果截断 400-800 字）。
- **验收**：完整闭环真机：`分析宿主机` → 受理确认 → 面板出现结果 → 追问"结果呢" → 对话引用真实 uname/df 输出。

---

### FIX-12 [P2] 记忆上下文窗口扩展

- **现象**：`_recent_dialogue` 仅 6 轮（`converse.py:337-357`），长会话前文丢失。
- **方案**：turns 6→10，按 token 预算动态收缩（`_SYSTEM_PROMPT` 200 字回复约束下总 prompt 可控）；多主题会话用 session_id 分段（FIX-04 的 session→goal 关联复用）。
- **验收**：10 轮内指代"第三轮提过的事"命中率提升。

---

### FIX-13 [P2] InteractionContext 统一接入

- **现象**：`InteractionContext`（`interaction/context.py`）声明为统一 Store 注入点，但 ChatResponder 直连 MemoryHub/GoalStore，未使用。
- **方案**：ChatResponder 的 stores 访问收敛到 InteractionContext（只读查询路径）；消除第三处实现漂移。
- **验收**：行为不变；`interaction/context.py` 出现在生产路径。

---

### FIX-14 [P2] Goal 结构化 progress

- **方案**：`GoalStore` 增加 `progress` 字段维护（0.0-1.0），DAG 推进时更新（`agent_runtime.py:1232` cursor 递增处）；`build_context` 注入 `id/status/progress`。
- **验收**：对话能报告"目标完成度 40%"。

---

### FIX-15 [P3] continuity 并入对话上下文

- **方案**：`load_continuity()`（`continuity_trigger.py`）非空时注入 `build_context`（当前仅 `/ocos/introspect` 可读，`converse.py:216-221`）。
- **验收**：跨 session 恢复信息出现在对话。

---

### FIX-16 [P3] 语义检索增强

- **方案**：有 embedding 能力时用语义相似度替换 bi-gram 重叠；无则调高重叠阈值并补充同义词表（中文）。
- **验收**：召回 F1 提升（对比 FIX-09 基线）。

---

### FIX-17 [P2] 主动输出接通 outbox

- **现象**：`maybe_proactive_output` 每 60 tick 触发，但回调为 None → 只写本地日志，用户永远看不到。
- **证据**：`master_agent.py:1643-1655`（`_build_proactive_callback` 在 `_external_interaction=None` 时返回 `_proactive_output_callback`，生产恒 None）。
- **方案**：`build_master_agent` 注入 `proactive_output_callback` → `UserInbox.post_outbound(消息)`（复用 daemon 已建的 outbox 回推通道，`daemon/__init__.py:447-472`），使主动输出以面板形式进入对话流（符合"结果在对话流展示"硬约束）。
- **风险**：中。需防打扰：沿用 ProactiveEngine 的 daily_limit + SELF goal 门控。
- **验收**：构造 SELF 目标后等待触发，`/ocos/outbox` 出现主动消息并被 TUI 面板渲染。

---

## 5. 行为回归验证矩阵（真机）

| 场景 | 操作 | 预期（修复后） | 关联 FIX |
|---|---|---|---|
| A 上下文 | 聊项目→聊记忆→"数据库怎么设计？" | 第三轮引用前两轮决策，不再反问"指哪个" | 09, 12 |
| B 任务连续 | "分析宿主机"→等待→"继续" | 锚定 GOAL-id，引用状态与最近结果，不新建重复目标 | 04, 05, 11 |
| C 历史经验 | 先分析 Python 项目，再分析 Rust 项目 | 第二次复用第一次的方法（planning prompt 出现同类成功经验） | 06, 08 |
| D 失败恢复 | 触发失败任务 | 重试输出携带【执行反馈】，动作序列不再原样重放 | 07, 02 |
| E 工具闭环 | "分析宿主机"→追问"结果呢" | 对话引用真实 uname/df stdout 摘要 | 11, 04 |
| F 入口一致 | `ocos say "分析宿主机"` 与 TUI 同输入 | 两者都建目标并执行 | 03 |
| G 主动性 | 构造 SELF 目标，等待触发 | outbox 出现主动面板消息 | 17 |
| H 元认知 | 写类任务 + 历史低成功率 | 升级 ASK 待批而非 AUTO | 02, 08 |

---

## 6. 量化验收指标（对齐审计读数）

| 指标 | 审计基线 | 修复目标 |
|---|---|---|
| Behaviorally Effective | 7 | ≥ 12 |
| Decorative/Dormant | 14 | ≤ 6 |
| Critical Disconnected | 5 | ≤ 2 |
| 对话中"猜"的回复占比（真机抽查 20 轮） | 高（无统计） | ≤ 20% |
| "继续/结果呢"锚定到具体 goal_id 的比例 | 0 | ≥ 80% |
| 第二次同类任务注入学习经验的比例 | 0 | ≥ 60% |

---

## 7. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| prompt 膨胀（FIX-04/05/06/10） | 每节限 400-800 字；无数据不注入 | 各注入点独立函数 + 环境开关 |
| learning 落库 schema 变更（FIX-08） | 建表幂等；写库失败降级内存 | 删除表回退 |
| 主动输出打扰（FIX-17） | 沿用 daily_limit + SELF 门控 | 环境开关 `OCOS_ENABLE_PROACTIVE=0` |
| 认知循环停用副作用（FIX-01） | 保留代码与开关 | `OCOS_ENABLE_COGNITIVE_LOOP=1` 恢复 |
| 召回变少（FIX-09） | 阈值 0.25 起，真机校准 | 调回旧路径 |

每个 FIX 落版时均需：单元测试（构造路径） + 真机场景（§5 矩阵）双验收；本文件不承诺一次性全部落地，建议按 Phase 顺序分批合入。

---

## 8. 一句话结论

这份计划不新增任何认知模块——它只是把 OCOS 已经写好的 Memory、Goal、Learning、Reflection、World/Self Model 的能力，**真正接到那两次决定用户感受的 LLM 调用点（converse.py 与 bridge.py）上**，让"器官"从 DECORATIVE 变为 ACTIVE。
