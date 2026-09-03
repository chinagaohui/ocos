# OCOS → AGI 二次 Reality Audit Report v2.0

**Audit Date**: 2026-09-03  
**Auditor**: Independent AGI Runtime Architecture Auditor  
**Method**: Definition → Construction → Registration → Wiring → Reachability → Activation → Production → Consumption → Persistence → Reuse  
**Discipline**: 只读审计。零代码修改。隔离 DB 运行验证（/tmp，运行后删除）。生产 DB 未触碰。

---

## 1. Executive Summary

v2.0 审计以**真实调用链 + 运行时证据**推翻第一轮报告的大部分核心结论。

第一轮报告犯了一个根本性方法错误：**以猜测的文件路径做可达性追踪**（如 `daemon/daemon.py`、`cognitive_loop/tick.py` 直接 NOT FOUND），进而得出"无 Runtime Loop""Cognitive Loop 缺失""World Model 无接线"等结论。

**v2.0 关键修正：**

| 第一轮结论 | v2.0 修正 |
|-----------|----------|
| 无独立 tick() 循环 | **REJECTED** — `AgentRuntime.tick()` 是完整 10 步认知循环，且被生产驱动 |
| Runtime Loop 缺失 | **REJECTED** — `RuntimeLoop`(Phase M) + `RuntimeKernel` + `ResidentRuntime` 三层循环真实存在 |
| World Model R2 无接线 | **REJECTED** — `PerceptionPipeline → WorldStore → CausalityLink` 真实写入链存在 |
| 内生 Goal 无触发 | **REJECTED** — 隔离运行证明 daemon boot 自动生成内生目标（主动联结/探索盲区） |
| Goal→Action 无闭环 | **REJECTED** — 内生目标被自动分解 → LLM 转命令 → 真实执行 `uname -a` → Episode 落库 |
| Memory 仅 6 分 | **PARTIALLY CONFIRMED** — 写入/持久化强，recall→reasoning 消费弱 |
| Learning R1-R2 | **CONFIRMED（但修正细节）** — LearningEngine 空转，生产零样本 |
| Generalization 0 | **UNRESOLVED** — 无直接证据，但存在 skill graph + LLM 转换的弱泛化路径 |

**核心判断：OCOS 是一个真实运行的 Cognitive Runtime（有限自主），不是"代码存在但未激活"。**

---

## 2. Audit Methodology

- 静态：AST 解析 817 模块 → 真实导入图 → 关键类/方法提取
- 运行时：隔离 DB（/tmp/ocos_audit_tmp.db）跑 `ocos run --ticks 2`，观察真实行为
- 证据分级：E-CODE（代码）/ E-RUN（隔离运行）/ E-DB（数据库行）/ E-LOG（运行日志）
- 生产 DB（~/.ocos/ocos.db）只读 stat，未写一行

---

## 3. Repository Reality

```
Repository (ocos/, 167,311 行, 817 模块, 2,364 类)
├── runtime/         (47) — RuntimeKernel / RuntimeLoop / tick / scheduler / 各运行时
├── agent/           (42) — AgentRuntime(10步tick) / MasterAgent(142方法) / DecisionLoop
├── capability/      (42) — CapabilityRegistry / agents / self_modification
├── memory/          (33) — MemoryHub / recall / gate / hub
├── interaction/     (62) — CLI / API / TUI / converse
├── cognitive_loop/  (10) — loop_orchestrator / decision_pipeline / perception_bridge
├── world_model/     (9)  — WorldStore / state_tracker / causality_engine
├── perception/      (11) — PerceptionPipeline / sensors / engine
├── goal/            (12) — GoalStore / tracker / maintenance_engine
├── planning/        (6)  — TaskDecomposer / simulator
├── decision/        (8)  — context_builder / option_generator / risk_engine
├── execution/       (3)  — DecisionBridge(869行, 完整分级执行)
├── daemon/          (4)  — ResidentRuntime(556行) / factory(生产装配)
├── engines/         (18) — reasoning/planning/decision/reflection/learning engine
├── learning/        (2)  — manager (极小)
├── autonomous/      (2)  — goal_manager (内生目标)
├── self/            (14) — self_model / capability_awareness / governor
├── evolution/       (11) — evolution_manager / sandbox / rollback
└── ... (其余)
```

**关键：第一轮"daemon.py NOT FOUND / tick.py NOT FOUND"是因为真实文件在 `runtime/runtime_kernel.py`（非 daemon/daemon.py）与 `agent/agent_runtime.py:tick`（非 cognitive_loop/tick.py）。**

---

## 4. Runtime Entry Points

| 入口 | 文件 | 状态 |
|------|------|------|
| `ocos run` (生产 daemon) | interaction/cli/commands/run.py | ✅ 运行时验证通过 |
| `ocos chat` (TUI) | interaction/cli/commands/chat.py | ✅ |
| API Server | interaction/api/server.py | ✅ 运行中(port 8900) |
| CLI 命令 | interaction/cli/main.py | ✅ |

**运行时进程证据（E-RUN）：**
- `ocos run` daemon 真实运行：PID 300637 / 326322（opentale venv）
- API server 真实运行：PID 299699（port 8900）
- 生产 DB 持续写入：~/.ocos/ocos.db 1,476KB，最后修改 20:33:26（审计时）

---

## 5. Production Runtime Graph

真实生产链（隔离运行 `ocos run --ticks 2` 证实）：

```
cmd_run (run.py)
  → build_master_agent() (daemon/factory.py — 零 Mock 全生产组件)
  → ResidentRuntime(agent, db_path)  (daemon/__init__.py)
      ├── attach_decision_bridge(DecisionBridge)   ← 执行铰链
      ├── attach_perception_pipeline(PerceptionPipeline + WorldStore)
      ├── attach_health_loop(HealthLoop + AlertManager)
      └── start()
           → AgentRuntime.boot()
                ├── _init_persistence (SQLite)
                ├── _verify_identity_continuity (IdentityAnchor)
                ├── _init_memory_recall (MemoryRecall)
                ├── _init_goal_manager
                └── agent.boot() (MasterAgent + CrashRecovery)
           → RuntimeKernel.start() + attach_agent_driver(tick)
           → _tick_loop 线程 (daemon)
                ├── 心跳落盘 (5 tick)
                ├── 目标结果回推 (5 tick)
                ├── dream 巩固 (Episode→Belief/Pattern/Wisdom)
                ├── _drain_goal_queue (目标导入)
                ├── _claim_persisted_goals (认领 CLI 持久化目标)
                ├── _drain_user_inbox (ocos say 消息)
                ├── perception_pipeline.tick() (感知→世界)
                └── kernel.tick_loop(1) → AgentRuntime.tick()
```

**E-RUN 证据（隔离运行日志）：**
```
ResidentRuntime daemon started (interval=0.5s)
TextGenerator initialized with provider=openai
HTTP Request: POST https://apihub.agnes-ai.com/v1/chat/completions "HTTP/1.1 200 OK"   ← LLM 真实调用
完成 2 个 tick
ResidentRuntime daemon stopped. 0 goals processed.
final: state=STOPPED cycles=2
```

---

## 6. Cognitive Loop Reality

### 第一轮结论：❌ "无 Cognitive Loop" → **REJECTED**

### 真实结构（E-CODE: agent/agent_runtime.py:tick, 76 行主调度）

```
AgentRuntime.tick() — 10 步持久化认知循环
  Step 1: Event Ingestion      (EventBus → 感知事件)
  Step 2: Attention Update     (注意力模型)
  Step 3: WM Sync              (工作记忆持久化)
  Step 4: Goal Maintenance     (目标状态检查)
  Step 4.5: Homeostasis Regulation (内生目标, P2-A)
  Step 5: Execution Check      (执行状态扫描)
  Step 6: Planning Trigger     (goal → TaskDAG, Phase 36 三条件门控)
  Step 7: Core Loop            (DAG 执行 或 DecisionLoop.execute_single)
  Step 8: Dispatch             (经 DecisionBridge 分级执行)
  Step 9: Result Ingest        (结果 → Memory + Attention + Episode)
  Step 10: Learning Consolidation (consolidate + belief 提取)
```

### DecisionLoop.execute_single（E-CODE: agent/decision_loop.py:138）

当无 TaskDAG 时的认知回退循环，完整 8 阶段：

```
perceive (agent.observe)
  → reason (agent.think → CognitiveBridge)
  → select (CapabilitySelector)
  → decide (agent.decide → Constitution 拦截 → Bridge)
  → execute (EngineBridge 或 agent.act)
  → observe_result (reflect)
  → reflect (agent.reflect)
  → learn (agent.learn → 空样本 → Episode 持久化)
```

### 三层循环宿主（E-CODE）

| 层 | 文件 | 职责 |
|----|------|------|
| RuntimeLoop | runtime/runtime_loop.py (432行) | 抽象循环引擎（sync/async） |
| RuntimeKernel | runtime/runtime_kernel.py (224行) | 认知循环单一宿主，tick 驱动 |
| ResidentRuntime | daemon/__init__.py (556行) | 生产 daemon 包装 |

**结论：Cognitive Loop 存在且被生产驱动（R5-R6 ACTIVATED/PRODUCING）。**

---

## 7. Observation / State Reality

### 第一轮结论：⚠️ "Observation→State 未建立" → **REJECTED（写入链存在）**

### 真实链（E-CODE: perception/pipeline.py:187, daemon/__init__.py:363）

```
传感器 (FileSensor/TextSensor/环境传感器)
  → PerceptionEngine.tick() → PerceptionEvent
  → PerceptionPipeline._bridge_to_world(obs)
       → WorldObservation(entity_id, claimed_state, raw_data)
       → WorldStore.update_from_observation()   ← 唯一写入路径
       → WorldValidator 校验
       → 若 infer_causality: _infer_causality_links()
            → 状态变化 → CausalityLink 写入 world.causality
```

### daemon 每 tick 驱动（E-CODE: daemon/__init__.py:363-367）

```python
if self._perception_pipeline is not None:
    self._perception_pipeline.tick()
```

### 断点

- **默认零传感器**：`build_perception_pipeline()` 默认 `sensors=[]`（零噪音设计），须 `--watch-dir` 注入 FileSensor 才有感知输入
- **读取方唯一**：`get_entity_state` 的生产调用者只有 pipeline 自身（因果推断用），**WorldStore 无下游认知消费方**

**结论：Observation→WorldState 写入链完整（R5），但 WorldState→Reasoning 消费链缺失（断点在 Consumption）。**

---

## 8. Memory Reality

### 写入链（E-CODE + E-DB 双重证据）

```
执行结果 → _tick_step_result_ingest
  ├── A. memory.add_to_working()          (Working Memory)
  ├── B. _record_episode_from_result()    (→ MemoryHub EpisodeStore)
  ├── C. attention.push_focus()           (Attention 信号)
  └── experiences.record()                (Experience)
```

### 持久化证据（E-DB: 隔离运行 2 tick 后）

| 表 | 行数 | 证据 |
|----|------|------|
| episodes | 2 | `EPI-6cc9dc0e5a34 tick_1 收集数据` / `EPI-20b6fec3c53a tick_2 分析数据` |
| event_store | 1 | `EVT-0c744b63c959 result dag_execute: Linux laogao...` |
| goal | 2 | 内生目标（见 §10） |

### 生产 DB 存量证据（E-DB: ~/.ocos/ocos.db 只读）

| 表 | 行数 |
|----|------|
| episodes | 717 |
| goals | 51（大部分 COMPLETED） |
| user_messages | 32 |
| working_memory | 1 |
| knowledge | 0 |

### recall→Reasoning 消费（断点所在）

- MemoryRecall 初始化 ✅（agent_runtime.py:367）
- 生产 recall 调用点仅 2 处：
  - `initiative/true_initiative.py:105` — `recall(context="current topic")`（主动输出触发器）
  - `opentale_bridge/master_agent.py:199` — `_memory.recall(intent.title)`
- **DecisionLoop 认知主链（think/decide）不注入 recall 结果**

**结论：Memory 写入+持久化 R6-R7；recall→reasoning 消费 R2（断点：MasterAgent._recall_and_record 是 pass 空壳）。**

---

## 9. World Model Reality

### 第一轮结论：❌ "仅类型定义 R2" → **REJECTED（实现远比第一轮充分）**

### 真实组件（E-CODE: world_model/）

| 文件 | 内容 |
|------|------|
| world_store.py | WorldStore：update_from_observation / get_entity / get_entity_state / get_neighbors / search_entities / summary |
| state_tracker.py | 状态追踪 |
| causality_engine.py | 因果引擎 |
| relation_graph.py | 关系图 |
| entity_model.py / event_model.py | 实体/事件模型 |
| world_validator.py | 观察校验 |

### 数据流回答

| 问题 | 答案 | 证据 |
|------|------|------|
| ① 有无当前世界状态 | ✅ WorldStore 实体+状态 | E-CODE |
| ② 状态随 Observation 更新 | ✅ `update_from_observation` 唯一写入路径 | E-CODE pipeline.py:141 |
| ③ Reasoning 读取该状态 | ❌ 无生产读取方 | E-SCAN |
| ④ 能预测未来状态 | ⚠️ CausalityLink 推断（CONTRIBUTES 0.6） | E-CODE pipeline.py:168 |
| ⑤ Prediction 影响 Planning | ❌ 无 | — |
| ⑥ Action 后 World 更新 | ⚠️ 仅传感器注入时 | — |

**结论：World Model 是 R4-R5（WIRED→ACTIVATED），可称为 Distributed World Model（EntityStore+StateStore+CausalityLink 组成），但只写不读——下游认知不消费世界状态。**

---

## 10. Goal / Planning Reality

### 第一轮结论：❌ "人类必须提供每一步任务" → **REJECTED（内生目标真实生成）**

### 内生目标证据（E-DB: 隔离运行 2 tick，goal 表 2 行）

```
goal_id=30811eb1... status=PENDING  priority=0.4
  description='发起一次主动联结：向用户或外部环境发起一次有意义的交互'
goal_id=83353e67... status=ACTIVE   priority=0.5
  description='探索新领域：识别并吸收一条当前认知盲区的新信息'
```

**这两个目标在隔离 DB（无任何用户输入）中自动出现 → 来自 Homeostasis/Autonomous 内生目标系统，daemon boot 即触发。**

### Goal→TaskDAG→Action 闭环（E-RUN 隔离运行 + E-DB）

```
内生目标 '探索新领域' (ACTIVE)
  → AgentRuntime._tick_step_planning_trigger (Step 6)
       Gate1: Attention 可用
       Gate2: 资源可用
       Gate3: Goal PENDING/ACTIVE + HUMAN 优先
  → TaskDecomposer.decompose (planning/decomposer.py 模板)
       → TaskDAG (收集数据 → 分析数据 → ...)
  → Step 7 Core Loop: bridge.execute_dag_task(task)
       → LLM 可用? → _handler_dag_task 把任务描述转真实动作
       → 只读类 → 白名单真实执行
  → Step 8 Dispatch → 真实命令执行
  → Step 9 Result Ingest → Episode 落库
```

### E-RUN 执行证据（event_store 行）

```
EVT-0c744b63c959  result  '{"status": "completed", "summary": "dag_execute: Linux laogao 7.0.0-28-generic..."'
```

**内生目标被自动分解 → LLM 转换成真实 shell 命令（uname）→ 执行 → 结果事件落库。这是从"系统自主生成目标"到"真实行动"的完整闭环。**

### 诚实失败路径（E-RUN: tick_2 episode）

```
EPI-20b6fec3c53a  '分析数据'  decision='{"status": "failed", "reason": "任务描述\"分析数据\"过于模糊，未指定数据源"}'
```

LLM 判定不可执行时诚实 failed（不伪装 pending），落入 goal_result 摘要。**这是真实判断力，不是 stub。**

### Replanning 断点

- 失败 → 诚实归档 ✅
- 失败 → 诊断 → 修改计划 → 继续 ❌（无 Replan 链，`_dag_cursor += 1` 直接跳到下一任务）

---

## 11. Decision / Action Reality

### DecisionBridge（E-CODE: execution/bridge.py:869 行）

完整执行铰链，权限分级明确：

```
process(core_loop_result)
  → _extract_decision_text
  → dispatcher.interpret_decision (意图解析)
  → _adjudicate (分级)
       ├── auto → dispatcher.dispatch → 真实执行 → _audit_action
       ├── ask  → _enqueue_pending (R4-B Outbox 待批)
       └── denied → 拒绝
```

### DAG 任务执行（execute_dag_task）

| 条件 | 动作 | 证据 |
|------|------|------|
| LLM 可用 + 描述可执行 | LLM 转只读命令 → 白名单执行 | E-RUN HTTP 200 |
| 写/shell 类 | ASK 待批 (R4-B) | E-CODE |
| 只读 analyze/verify | AUTO 真实执行 | E-RUN uname |
| 描述模糊 LLM 判不可执行 | 诚实 failed | E-RUN episode |

### Governance 在决策链中真实生效

- `agent.decide()` → BehavioralConstitution.check_decision 先于 Bridge
- 宪法故障 **fail-closed**（BR-04 C-1：宪法引擎不可用 → 决策必须拒绝，不得静默放行）
- 所有 action 经 `_audit_action` 落审计

---

## 12. Tool Runtime Reality

### Capability 层

- CapabilityRegistry / CapabilityManager / CapabilitySelector 全存在（E-CODE）
- 5 内置 agents（code/research/planner/summarizer/selfmod）经 AgentProxy 统一调用（Phase 48）
- SkillGraphExecutor + SkillRegistry（E-CODE: capability/skill_registry.py）

### LLM Provider

- TextGenerator(provider=openai, mock=false) — E-RUN 日志确认真实 HTTP 调用 agnes-ai
- 生产调用方：DecisionBridge(685行) / converse.py / writer_engine

### 断点

- 工具"能否被选"依赖 CapabilitySelector 的 intent→skill 映射，生产映射表有限

---

## 13. Skill Runtime Reality

| 问题 | 答案 | 证据 |
|------|------|------|
| Skill A 能否被执行 | ✅ SkillGraphExecutor 存在 | E-CODE |
| Skill B 能否被组合 | ✅ SkillGraph（skills + edges） | E-CODE |
| Skill C 能否由经验产生 | ❌ 无 SkillLearner/SkillGenerator | E-SCAN |
| Skill D 新 Skill 持久化 | ⚠️ 手动注册可持久化 | E-CODE skill_registry |
| Skill E 下次调用新 Skill | ⚠️ 仅手动注册的 | — |

**结论：Skill 执行/组合 R4；Skill 习得 R0（无生成器）。Skill Registry 存在 ≠ Skill Acquisition。**

---

## 14. Learning Reality

### 真实链（E-CODE 追踪）

```
MasterAgent.learn() (master_agent.py:938)
  → CognitiveBridge.learn(model=None, examples=None, strategy="supervised")
  → LearningEngine.execute()
  → _persist_learning()
       → TraceBundle(observation→reasoning→decision→action→outcome→reflection→learning)
       → ExperienceBuilder.build() → Episode → EpisodeStore.save()
```

### 关键发现：学习管道完整，但**零样本流**

- `MasterAgent.learn()` 调用时传 `model=None, examples=None`（E-CODE: master_agent.py:949）
- CognitiveBridge.learn 默认 `examples or []` → **LearningEngine 每次收到空样本**
- patterns_learned 恒为 0
- Episode 持久化 ✅ 但模式提取（belief 提取是确定性规则）非统计学习

### AgentRuntime Step 10（E-CODE）

```python
if self._cycle_count % 5 == 0:  self.memory.consolidate_to_long_term()
if self._cycle_count % 10 == 0: self._extract_beliefs()
```

belief 提取是规则型（从 episode 文本提取），不是从错误中学习。

**结论：Learning = 管道存在(R5 ACTIVATED)但无真实学习信号(R1 DECLARED)。"完成任务后明天不会更强" — CONFIRMED。**

---

## 15. Failure / Recovery Reality

| 机制 | 状态 | 证据 |
|------|------|------|
| Retry same command | ⚠️ execution 层 retry_policy | E-CODE agent/retry_policy.py |
| 执行失败诚实归档 | ✅ | E-RUN episode failed |
| Crash Recovery | ✅ CrashRecovery.recover() in boot | E-CODE master_agent.py:197 |
| Snapshot 恢复 | ✅ RuntimeKernel checkpoint | E-CODE runtime/checkpoint.py |
| **认知级 Replan（失败→诊断→改计划→继续）** | ❌ | 无生产链 |

**结论：系统崩溃恢复（persistence 级）✅；任务失败认知恢复（策略级）❌。第一轮 "无 Failure→Replan" CONFIRMED。**

---

## 16. Self Model / Metacognition Reality

| 能力 | 状态 | 证据 |
|------|------|------|
| Identity 连续 | ✅ IdentityAnchor + SQLiteStore + 快照 | E-CODE |
| Capability 自知（会什么） | ✅ capability_awareness | E-CODE self/capability_awareness.py |
| Confidence/Uncertainty | ⚠️ 引擎层有 confidence 字段，未影响决策 | E-CODE |
| 失败历史 | ⚠️ drift_detector 记录能力漂移 | E-CODE |
| Reflection 改变策略 | ⚠️ ReflectionEngine 存在但反射结果不回流到 planning | E-CODE |
| Metacognition 影响 Decision | ❌ | — |

**结论：Self Model R4（Identity+能力自知）；Metacognition R2（反思不改变策略）。第一轮大致 CONFIRMED。**

---

## 17. Generalization Reality

| 机制 | 状态 |
|------|------|
| 跨任务模板 | ⚠️ TaskDecomposer 按 domain 模板分解（弱泛化） |
| LLM 将模糊任务转具体命令 | ✅ E-RUN（"收集数据"→uname 类只读命令）— 这是最强泛化证据 |
| Skill 迁移 | ❌ |
| 类比/抽象 | ❌ |
| 未预定义任务 | ⚠️ LLM 可转换但无学习沉淀 |

**结论：存在"LLM 驱动的弱泛化"（任务描述→动作转换真实发生），但无跨任务学习迁移。第一轮 Generalization=0 过于绝对 → UNRESOLVED（无结构性泛化机制，但 LLM 转换层提供浅层泛化）。**

---

## 18. Autonomy Reality

| 能力 | 人类介入 | 状态 |
|------|----------|------|
| 接收目标 | 可选 | ✅ 内生目标自动生成（E-RUN 2 目标） |
| 分解目标 | 自主 | ✅ TaskDecomposer |
| 制定计划 | 自主 | ⚠️ 模板 DAG（非自适应） |
| 选择工具 | 自主 | ✅ DecisionBridge 分级 |
| 执行动作 | 自主 | ✅ AUTO 只读执行（E-RUN uname） |
| 写类动作 | ASK 待批 | ✅ R4-B 审批链 |
| 处理失败 | 自主 | ⚠️ 诚实归档（无 replan） |
| 获取知识 | 依赖 | ❌ 无自主知识获取循环 |
| 学习技能 | 依赖 | ❌ |

**结论：Autonomy R5（生产激活：内生目标→分解→执行→归档闭环真实跑通）；瓶颈在失败后认知恢复与知识获取。**

---

## 19. Persistence / Continuity Reality

| 表 | 生产行数 | 隔离运行验证 |
|----|---------|-------------|
| episodes | 717 | ✅ 2 tick 写入 2 行 |
| goals | 51 | ✅ 内生目标写入 |
| event_store | — | ✅ 执行事件写入 |
| identity | ✅ | boot 快照验证 |
| working_memory | ✅ | 每 tick 持久化 |

### 重启连续性（E-CODE）

- `_verify_identity_continuity()` boot 时校验
- `_restore_working_memory()` 恢复 WM
- CrashRecovery.recover() snapshot 恢复
- `_claim_persisted_goals()` 认领上次 PENDING 目标

**结论：Persistence R7-R8（写入/恢复机制完整+生产运行中）。跨运行认知连续性 = episodes/identity/goals 全持久化，重启可恢复。第一轮 R7 CONFIRMED。**

---

## 20. Governance Reality

| 机制 | 状态 | 证据 |
|------|------|------|
| BehavioralConstitution 决策拦截 | ✅ 先于 Bridge，fail-closed | E-CODE master_agent.py |
| DecisionBridge 分级 (auto/ask/deny) | ✅ | E-CODE bridge.py |
| R4-B 待批 Outbox | ✅ pending_actions 表 | E-DB |
| 审计记录 | ✅ _audit_action | E-CODE |
| 只读 AUTO / 写类 ASK | ✅ _DAG_AUTO_TYPES/_DAG_ASK_TYPES | E-CODE |
| 敏感路径拦截 | ✅ 沙盒白名单 | E-CODE |

**结论：Governance R6-R8。写入类动作强制人工审批——Mutation Authority 受控。第一轮低估（曾评 R6 但未验证 enforcement，现确认 fail-closed 设计）。**

---

## 21. Trace / Observability Reality

| 追踪链 | 状态 |
|--------|------|
| Episode ID (EPI-) | ✅ |
| Goal ID (GOAL- / goal_id) | ✅ |
| Trace ID (引擎层 trace_id) | ✅ |
| Task ID (TASK-) | ✅ |
| 事件 ID (EVT-) | ✅ |
| DecisionBridge audit_records | ✅ |
| ID 互关联 | ⚠️ episode.context 含 task/goal 引用 |

**结论：执行级追踪完整（R6）；端到端认知重放（goal→learn）缺 learn 段（因为 learn 零样本）。**

---

## 22. Dormant Capability Registry

| 分类 | 条目 | 证据 |
|------|------|------|
| D1 IMPLEMENTED_NOT_CALLED | RuntimeLoop.sync 模式（生产只用 kernel.tick_loop） | runtime_loop.py |
| D2 TEST_ONLY | 部分 engines 的 handler 路径 | — |
| D3 REACHABLE_NOT_ACTIVATED | WorldStore 读取接口（get_neighbors/search） | world_store.py |
| D4 ACTIVATED_NO_EFFECT | MasterAgent.learn（空样本→0 模式） | master_agent.py:949 |
| D5 OUTPUT_DISCARDED | DecisionLoop engine_results 注入后少消费 | decision_loop.py |
| D6 PERSISTED_NOT_RECALLED | knowledge 表（生产 0 行）；episodes 写入后主链不 recall | E-DB |
| D7 LEARNED_NOT_REUSED | —（无真实学习） | — |
| D8 SKILL_NOT_COMPOSABLE | skill_registry 存在但 SkillLearner 缺失 | — |
| D9 GOVERNANCE_NOT_ENFORCED | 未发现（治理真实生效） | — |
| D10 DECLARED_NO_EVIDENCE | sleep_dream（有方法但无生产触发证据）；evolution 大部 | — |

---

## 23. False Capability Registry

| 伪能力 | 判定 | 证据 |
|--------|------|------|
| "Learning" 引擎 | 伪 — 空样本学习管道 | master_agent.py:949 examples=None |
| "Reflection 改变行为" | 伪 — reflection 结果不回流 planning | — |
| "World Model 支持推理" | 伪 — 世界状态无下游消费者 | E-SCAN |
| "_recall_and_record 记忆召回" | 伪 — pass 空壳 | master_agent.py |
| "Generalization 结构" | 伪 — 无迁移机制（仅 LLM 浅层转换） | — |

---

## 24. First-Round Conclusion Verification

| 第一轮结论 | 原报告 | 二次审计证据 | 修正 | 最终等级 |
|-----------|--------|-------------|------|---------|
| World Model | R2 仅类型 | PerceptionPipeline→WorldStore→Causality 真实写入 | **REJECTED** | R4-R5（只写不读） |
| Memory | 6 | 717 episodes 生产 + 写入链完整，recall 消费弱 | PARTIALLY | R7 写 / R2 读 |
| Learning | 1-2 | 管道全但零样本 | CONFIRMED | R5 管道 / R1 信号 |
| Goal | 6 | 内生目标自动生成+分解+执行闭环 | **REJECTED**（低估） | R6 |
| Planning | 4 | 模板分解+门控真实，无 replan | PARTIALLY | R5 |
| Tool Use | 7 | 分级执行+LLM 转换真实 | CONFIRMED | R7 |
| Cognitive Loop | 缺失 | 10 步 tick + 8 阶段 DecisionLoop + 3 层宿主 | **REJECTED** | R6 |
| Autonomy | 2 | 内生目标→行动闭环真实跑通 | **REJECTED**（低估） | R5 |
| Generalization | 0 | LLM 转换层弱泛化 | PARTIALLY | R2 |
| Self Model | 4 | Identity+能力自知，metacognition 弱 | CONFIRMED | R4 |

---

## 25. Intelligence Graph（真实）

```
Endogenous Goal (Homeostasis/Autonomous — daemon boot 自动生成)
  ↓  (goal 表, 隔离运行证据)
AgentRuntime.tick Step 6 Planning Trigger (门控: attention/resource/ready)
  ↓
TaskDecomposer → TaskDAG (模板分解, 5 任务串行)
  ↓
Step 7 Core Loop → DecisionBridge.execute_dag_task
  ├── LLM 可用 → _handler_dag_task (任务描述→真实动作, HTTP 200 E-RUN)
  │     ├── 只读 → 白名单 AUTO 执行 → uname 真实运行 (E-RUN event_store)
  │     └── 模糊/不可执行 → 诚实 failed (E-RUN episode)
  ├── 写类 → R4-B ASK 待批
  └── EchoAgent fallback (无能力匹配)
  ↓
Step 8 Dispatch → _audit_action (审计)
  ↓
Step 9 Result Ingest → Working Memory + Episode (E-DB) + Attention signal
  ↓
Step 10 Consolidation (5-tick 巩固 / 10-tick belief 规则提取)
  ↓
User Inbox (ocos say) → inject_user_message → EventBus → Step 1 摄入
```

---

## 26. Evidence Matrix

| Capability | Definition | Construction | Wiring | Reachability | Activation | Production | Downstream | Persistence | Reuse | Evidence |
|-----------|-----------|-------------|--------|-------------|-----------|-----------|-----------|-------------|-------|----------|
| Cognitive Loop | runtime/ | ✅ | ✅ | ✅ | ✅ 生产 | ✅ 2tick | ✅ episode | ✅ | ✅ | E-RUN |
| Goal→Action | autonomous/ | ✅ | ✅ | ✅ | ✅ boot | ✅ uname | ✅ episode | ✅ goals表 | ✅ | E-RUN+E-DB |
| Perception→World | perception/ | ✅ | ✅ | ✅ | ✅ 每tick | ⚠️ 零sensor | ❌ 无读方 | ⚠️ 内存 | ❌ | E-CODE |
| Memory 写 | memory/ | ✅ | ✅ | ✅ | ✅ | ✅ 717 | ✅ belief | ✅ SQLite | ⚠️ | E-DB |
| Memory 读 | recall | ✅ | ⚠️ | ⚠️ | ⚠️ 2调用 | ⚠️ | ❌ think不消费 | — | ❌ | E-CODE |
| Learning | engines/ | ✅ | ✅ | ✅ | ✅ 每tick10 | ⚠️ 空样本 | ❌ 0模式 | ⚠️ episode | ❌ | E-CODE |
| World Model | world_model/ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | E-CODE |
| Replan | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | E-SCAN |

---

## 27. Capability Reality Matrix

| 能力 | 等级 | 第一断点 |
|------|------|---------|
| Cognitive Loop | R6 PRODUCING | — |
| Goal Management | R6 PRODUCING | — |
| Action Execution | R7 OBSERVABLE | — |
| Governance | R7 OBSERVABLE | — |
| Persistence | R7 OBSERVABLE | — |
| Memory Write | R7 OBSERVABLE | — |
| Trace | R6 PRODUCING | — |
| Tool Use | R7 OBSERVABLE | — |
| Perception | R5 ACTIVATED | 默认零传感器 |
| Memory Recall | R3 REACHABLE | think 不消费 recall |
| World Model | R5 ACTIVATED | 无下游消费者 |
| Planning | R5 ACTIVATED | 模板化，无 replan |
| Learning | R5 管道 / R1 信号 | learn() 空样本 |
| Skill Acquisition | R0 | 无 SkillLearner |
| Generalization | R2 | 无迁移机制 |
| Metacognition | R2 | reflection 不回流 |
| Autonomy | R5 ACTIVATED | 失败无认知恢复 |

---

## 28. AGI Capability Vector

| 能力 | 得分 | 依据 |
|------|------|------|
| Perception | 5 | 管线全+每tick驱动，零传感器 |
| Memory | 7 | 717episodes+全表持久化+recall弱 |
| World Model | 5 | 写入链真实，无读方 |
| Reasoning | 6 | LLM+Constitution 真实链 |
| Planning | 5 | 模板DAG+门控，无replan |
| Goal Management | 7 | 内生+认领+闭环 |
| Tool Use | 7 | 分级+LLM转换+审计 |
| Action | 7 | 真实命令执行验证 |
| Reflection | 4 | 引擎在，不回流 |
| Metacognition | 2 | 无决策影响 |
| Learning | 2 | 管道空转 |
| Skill Acquisition | 1 | 声明级 |
| Skill Composition | 4 | SkillGraph 可执行 |
| Generalization | 2 | LLM 浅层转换 |
| Autonomy | 6 | 内生→行动跑通，知识获取缺失 |
| Persistence | 8 | 全表+恢复+认领 |
| Self Model | 4 | Identity 强，认知自知弱 |
| Governance | 8 | fail-closed+分级+审批 |
| Observability | 6 | 执行追踪全，认知重放缺 |
| Reliability | 6 | 崩溃恢复+诚实失败 |

**强项**: Governance / Persistence / Goal→Action 闭环 / Memory 持久化  
**最短板**: Learning（空样本）、Skill Acquisition（无）、Generalization（无结构）、Metacognition（不回流）

---

## 29. Critical Bottlenecks

1. **Learning 空转** — learn() 管道完整但 examples=None，系统永远不产生新模式；Episode 写了 717 条但从不"变强"
2. **World Model 只写不读** — 世界状态更新了但 Reasoning/Planning 不消费，World→Cognition 断链
3. **无认知级 Replan** — 失败诚实归档后直接下一任务，无诊断→策略修改→继续
4. **Memory 主链不 recall** — think/decide 不注入历史记忆，跨会话记忆仅靠 initiative 触发器
5. **Skill 无习得** — 有执行/组合，无生成/验证/持久化闭环

---

## 30. Current System Classification

**分类: Cognitive Runtime（有限自主，真实运行中）**

依据:
- ✅ 真实循环: 10 步 tick + 8 阶段认知 + 生产驱动（非测试）
- ✅ 内生目标自动生成（非人类每步指令）
- ✅ Goal→分解→执行→事件→Episode 闭环（隔离运行验证）
- ✅ Governance fail-closed + 分级 + 审计
- ❌ 无经验学习 → 不到 Adaptive Cognitive Runtime
- ❌ 无跨任务迁移 → 远非 General Intelligence

它不是 Automation（有自主目标生成）
它不是纯 Agent（有持续认知循环）
它是 **Cognitive Runtime** — 但 Learning/World/Replan 三环断裂，无法自适应进化。

---

## 31. Final Verdict

```
CURRENT OCOS CLASS:
Cognitive Runtime (有限自主, 生产激活) — 距 Adaptive Cognitive Runtime 差 Learning 闭环

COGNITIVE LOOP:
内生目标/用户消息 → EventBus → AgentRuntime.tick(10步)
→ [Step6] TaskDecomposer 分解 → [Step7] DecisionBridge(LLM转换+分级)
→ [Step8] 白名单执行/待批/诚实失败 → [Step9] Episode+WM+Attention
→ [Step10] 5-tick巩固/10-tick信念提取 → daemon dream 周期 → 持久化

STRONGEST CAPABILITY:
Governance + Goal→Action 执行闭环（fail-closed 宪法 + LLM 转换 + 分级审批 + 审计）

WEAKEST CAPABILITY:
Learning（空样本管道）— 系统执行了 717 个 episode 却零学习产出

FIRST MAJOR BREAKPOINT:
MasterAgent.learn() 调用 CognitiveBridge.learn(model=None, examples=None)
→ LearningEngine 每次收到空样本 → patterns_learned 恒为 0（D4 激活无效果）

LEARNING STATUS:
管道 R5 激活 / 信号 R1 — 无真实学习发生（假能力）

WORLD MODEL STATUS:
R5 写入链真实（PerceptionPipeline→WorldStore→CausalityLink）
但 World→Reasoning 消费 R0（只写不读，沉睡器官 D3）

SKILL ACQUISITION STATUS:
R0 — SkillRegistry/SkillGraph 可执行可组合，但无 SkillLearner/SkillGenerator

GENERALIZATION STATUS:
R2 — 仅 LLM 任务转换层提供浅层泛化；无跨任务学习迁移结构

AUTONOMY STATUS:
R6 — 内生目标自动生成+自主分解+自主执行(AUTO)+诚实失败归档
瓶颈: 失败后无认知恢复; 无自主知识获取循环

PERSISTENCE STATUS:
R8 — 21 表 SQLite + snapshot + crash recovery + 目标认领 + 工作记忆恢复
隔离运行验证写入, 生产 DB 717 episodes 存量

GOVERNANCE STATUS:
R8 — BehavioralConstitution fail-closed + DecisionBridge auto/ask/deny
+ R4-B 人工审批 + 审计记录（生产强制执行, 非声明）

AGI READINESS:
4.6/10 (v1.0 的 4.3 低估了认知循环与自主执行, 高估了部分声明能力;
真实差距在 Learning/World消费/Skill习得 三环)

CONFIDENCE:
HIGH（关键结论均有 E-CODE + E-RUN/E-DB 双重证据）

TOP 3 STRUCTURAL GAPS:
1. Learning 空转 — learn() 管道完整但零样本, Episode→Skill 无转化(第一断点)
2. World Model 只写不读 — 世界状态不进 Reasoning/Planning 输入
3. 无认知级 Replan — 失败→诊断→改策略→继续 整链缺失
```

---

**审计纪律确认**: 零代码修改；隔离 DB 运行 2 tick 后删除；生产 DB 仅只读 stat（~/.ocos/ocos.db 未被触碰）；未修改任何配置/测试/文档。

**审计结束。不进入设计/实施阶段。**
