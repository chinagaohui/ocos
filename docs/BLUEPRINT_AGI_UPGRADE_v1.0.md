# OCOS AGI Upgrade Gap & Architecture Blueprint v1.0

**版本**: v1.0  
**日期**: 2026-09-03  
**性质**: 架构蓝图（非冻结文档）— 基于 v2.0 Reality Audit 的升级差距分析与目标架构设计  
**上游证据**: `docs/AUDIT_REPORT_AGI_REALITY_v2.0.md`（783 行, E-RUN/E-DB 双证据）  
**范围**: 只覆盖"Experience → Learning → Memory/Skill → Future Cognition"闭环的 8 个核心缺口

---

## 0. 蓝图原则（本蓝图自身遵守的约束）

1. **不新增"第 N 套基础设施"**：复用现有类型判别器（ProcessType / CapabilityType / 存储接口），拒绝为每个缺口新建平行引擎（Four 不堆叠）
2. **不破坏既有不变量**：Decision 唯一 Mutation Authority / Governance fail-closed / Trace 连续 / Persistence 不静默丢失——每项设计都附不变量影响表
3. **语义先行**：每个闭环先定义"这是什么/输出什么/谁拥有"，再谈实现
4. **确定性规则优先于 LLM 修补**（用户铁律）：先做规则型闭环，LLM 只在规则无法覆盖处注入
5. **每条设计必须指出现有接线点**（文件/类/方法），不允许悬空架构

---

## 1. Executive Summary

### 1.1 起点判断（v2 审计确认）

OCOS 已是**真实运行的 Cognitive Runtime**：

```
持续 Runtime ✅ (RuntimeKernel + ResidentRuntime + AgentRuntime.tick 10步)
Event ✅ → Attention ✅ → WM ✅ → Goal Maintenance ✅
内生 Goal ✅ (隔离运行: boot 即生成"主动联结/探索盲区")
Planning ✅ (TaskDecomposer 模板DAG) → Decision ✅ (Constitution fail-closed)
Action ✅ (DecisionBridge 分级) → Execution ✅ (LLM转换 + 白名单真实执行)
Observation ✅ (E-RUN: uname 结果) → Episode ✅ (E-DB: 717 条)
Persistence ✅ (21表 SQLite) → Governance ✅ (R4-B审批 + 审计)
```

**骨架是真的。** 目标不是"把骨架做出来"，而是：

> **让这个已经会"做事"的系统，开始从自己的经历中"变强"。**

### 1.2 核心差距（一句话）

> OCOS 能积累**经历**（717 Episodes），但经历不转化为**能力增长**——因为它缺一条闭合的 Experience → Evaluation → Learning → Memory/Skill → Future Cognition 回路。

### 1.3 能力跃迁路径

```
现在:  Cognitive Runtime（执行型自治）
        ↓  本蓝图第一跃迁（L1-L3 优先）
目标:  Adaptive Cognitive Runtime（经验型自治）
        ↓  第二跃迁（L4-L8）
远景:  General Intelligence Runtime
```

### 1.4 8 个核心缺口分级

| 编号 | 缺口 | v2 等级 | 优先级 | 跃迁 |
|------|------|---------|--------|------|
| L1 | Experience Learning（快通路） | R5管道/R1信号 | ★★★ | 第一跃迁 |
| L2 | Memory Recall 进入主认知链 | R3 | ★★★ | 第一跃迁 |
| L3 | World Model 消费 | R5写/R0读 | ★★ | 第一跃迁 |
| L4 | Failure → Replan | R0 | ★★★ | 第二跃迁 |
| L5 | Skill Acquisition | R0 | ★★ | 第二跃迁 |
| L6 | Skill Reuse | R4执行/R0习得 | ★★ | 第二跃迁 |
| L7 | Generalization | R2 | ★ | 第二跃迁 |
| L8 | Metacognition 影响决策 | R2 | ★ | 第二跃迁 |

---

## 2. 关键修正：v2 报告的 Learning 判断需分层

蓝图动工前必须先修正一处审计盲区（本蓝图与 v2 报告的唯一分歧点）：

### v2 报告结论（部分正确但不完整）

> "Learning 空转 — learn() 管道完整但零样本"

### 蓝图修正

v2 只追踪了**快通路**（MasterAgent.learn → CognitiveBridge.learn → LearningEngine），未覆盖**慢通路**。本次审计补充证据：

| 通路 | 路径 | 状态 | 证据 |
|------|------|------|------|
| 快通路 | learn() → LearningEngine(examples=None) | ❌ 空转 (R1) | master_agent.py:949 |
| **慢通路** | daemon 每200tick → _run_dream_cycle → sleep()→dream() → **_consolidate_episodes()** | ✅ **真实实施+生产可达** | daemon/__init__.py `_run_dream_cycle`; master_agent.py `_consolidate_episodes` (完整实现: 重放→Belief聚类巩固→Pattern提取去重→弱模式修剪→幂等置CONSOLIDATED) |

**慢通路细节（本次审计新证据）：**
- 触发：ResidentRuntime `dream_interval_ticks=200`，daemon `_tick_loop` 每 200 tick 调 `_run_dream_cycle()`
- 实现：`_consolidate_episodes()` 完整——按 goal/tags 聚类 Episode → 新建 Belief(conf 0.6)/追加证据+强化 → PatternExtractor 提取+去重 → conf<0.35 weaken/archive → Episode 置 CONSOLIDATED
- 存储：`belief_store/pattern_store` 构造注入或惰性 `:memory:`；`attach_memory_hub` 时切 `hub.belief`
- 生命周期修复：`_run_dream_cycle` 处理 BOOTING→ACTIVE 迁移（此前 dream 永不运转的 bug 已修）

### 修正后的 Learning 真实等级

```
慢通路（Episode→Belief/Pattern 巩固）: R6 PRODUCING ✅ 确定性规则闭环存在
快通路（LearningEngine 统计学习）:     R1 DECLARED ❌ 空样本
行为改进（失败→策略调整→变强）:        R0 ABSENT    ❌ 不存在
```

**结论修正**：OCOS 有"**经验归纳**"（慢通路，规则型），无"**经验学习**"（行为改变）。Blueprint 的 L1 因此不是"从零造巩固"，而是"打通巩固→行为影响"与"为快通路注入真实信号"。

---

## 3. L1 — Experience Learning: 从"归纳"到"学习"

### 3.1 语义定义（六问）

| 问题 | 答案 |
|------|------|
| 这是什么 | 把执行结果(成功/失败)转化为可检索、可影响未来决策的学习产物 |
| 输出什么 | LearningModel（rules + accuracy）+ 持久化学习轨迹 |
| 输入什么 | LearningExample（input/output/feedback/metadata）— 从 Episode 结构化派生 |
| 谁拥有 | LearningEngine（已存在）+ ExperienceBuilder（已存在） |
| 可否撤销 | 是 — LearningModel 可版本化/回滚（evolution 模式） |
| 谁管理生命周期 | LearningEngine.learn/update + daemon dream 周期 |

### 3.2 现状 Gap

1. 快通路 `learn()` 收到 `examples=None`（master_agent.py:949）
2. LearningEngine 与 Episode 存储**无接线**：Episode→LearningExample 转换不存在
3. 慢通路产出 Belief/Pattern 但**不反馈**到 planning/decision（PatternStore 无消费方）

### 3.3 目标架构

```
EpisodeStore (已存 717 条)
    ↓ (新增: ExperienceBuilder 已部分存在, 补 Episode→LearningExample 转换)
LearningExample(input=task描述, output=结果摘要, reward=success?1:0,
                feedback=LLM诚实失败原因, metadata={task_id,agent,goal})
    ↓ (新增: daemon dream 周期内调用, 复用 _run_dream_cycle)
LearningEngine.learn(examples, learn_fn=规则型, strategy=SUPERVISED/REINFORCEMENT)
    ↓
LearningModel (rules: 任务模式→成功率统计, accuracy 表)
    ↓ (新增: 写 PatternStore/Belief 的"行为建议"字段, 或独立 lessons 表)
未来 Decision/Planning 可查询: "此类任务历史成功率 X%, 失败原因 Y"
```

### 3.4 接线点（现有代码）

| 动作 | 文件:方法 |
|------|----------|
| 派生样本 | `agent/master_agent.py:_persist_learning`（已有 TraceBundle 结构，补 examples 构造） |
| 学习触发 | `daemon/__init__.py:_run_dream_cycle`（每200tick, 已存在） |
| 存储 | `ocos/models/learning.py:LearningExample/Model`（已存在） |
| 消费 | `ocos/capability/skill_registry.py` 或 PatternStore 新查询接口 |

### 3.5 不变量影响

| 不变量 | 影响 | 防护 |
|--------|------|------|
| Decision 唯一 Mutation Authority | 无 — 学习产物只写 Memory/Model 层，不直接产生 Action | LearningModel 无 execute 路径 |
| Trace | 学习轨迹已有 LearningTrace | 样本携带 task_id/goal_id |
| Persistence | LearningModel 需落库（当前内存 dict） | 复用 memory 表或新增 learning_models 表 |

---

## 4. L2 — Memory Recall 进入主认知链

### 4.1 语义定义

把"经验仓库"变成"认知记忆"：**think/decide 的输入必须包含历史相关记忆**。

### 4.2 现状 Gap

- MemoryRecall 已初始化（agent_runtime.py:367），recall 生产调用仅 2 处（initiative/opentale_bridge）
- **主认知链 DecisionLoop.execute_single 的 think() 不注入 recall 结果**
- `MasterAgent._recall_and_record` 是 pass 空壳（master_agent.py）

### 4.3 目标架构

```
DecisionLoop.execute_single (decision_loop.py)
    ↓ observe() 后新增: agent.recall_context()（新方法或改造 _recall_and_record）
MemoryRecall.recall(context=观察/意图) → RecallResult
    ↓ 结构化: 相关 Episode(近例) + Belief(相关主题) + Pattern(历史成功率)
    ↓ 注入 think() premises["memory_context"]
MasterAgent.think(observation) 消费 → LLM/引擎推理带记忆上下文
```

### 4.4 接线点

| 动作 | 文件:方法 |
|------|----------|
| 新增 recall_context | `agent/master_agent.py`（改造 `_recall_and_record` pass 空壳 → 真实现） |
| think 注入 | `agent/master_agent.py:think`（premises 增 memory_context 键） |
| 调用位 | `agent/decision_loop.py:execute_single`（observe 与 reason 之间） |
| 检索实现 | `ocos/memory/recall.py:MemoryRecall`（已存在） |

### 4.5 不变量影响

| 不变量 | 影响 | 防护 |
|--------|------|------|
| I-2 Context 唯一入口 | 记忆注入须经 context 构建，不直连引擎 | 经 MemoryRecall 统一出口 |
| I-5 Observation 不升级 Action | 记忆只影响推理输入，不触发动作 | recall 结果只进 premises |

---

## 5. L3 — World Model Consumption

### 5.1 现状 Gap

- 写入链完整：PerceptionPipeline → WorldStore → CausalityLink（v2 REJECTED 第一轮"无 WM"）
- **读取方唯一是 pipeline 自身**（get_entity_state 用于因果推断）
- WorldStore 查询接口（get_neighbors/search_entities/summary）无生产消费者
- 默认零传感器（build_perception_pipeline sensors=[]）→ 生产环境 WorldStore 通常为空

### 5.2 目标架构（最小闭环）

```
WorldStore (已存在)
    ↓ 新增: 认知侧查询接口封装 WorldABI (world_query(entity/relation/summary))
DecisionLoop observe 或 planning_trigger 前:
    context["world_state"] = WorldABI.summary(相关域)  → 注入 think/plan
Action 执行后 (已有 Step 9):
    传感器观察 → pipeline.tick → WorldStore 更新（已有）
```

### 5.3 关键判断

L3 优先级设为 ★★（非 ★★★）——因为当前**默认零传感器**，即使消费接口就位，WorldStore 也常空。真正的先决是传感器激活策略（FileSensor 注入或 LLM 观察回填），但这属于"感知供给"，蓝图只保证"消费就绪"。

### 5.4 接线点

| 动作 | 文件 |
|------|------|
| WorldABI 查询封装 | `world_model/world_store.py`（新增 summary/query 面向认知的封装） |
| 注入 think | `agent/agent_runtime.py:_tick_step_wm_sync`（Step 3 已存在, 补读回） |
| 消费 | `agent/decision_loop.py` context 构建 |

---

## 6. L4 — Failure → Replan（认知级恢复）

### 6.1 现状 Gap

- 失败 → 诚实归档 ✅（E-RUN: "分析数据"→failed 落 Episode）
- 失败 → `_dag_cursor += 1` 直接下一任务（agent_runtime.py core_loop）
- **无 诊断→假设→替代计划→继续 链**

### 6.2 目标架构

```
TaskDAG 任务失败 (Step 7)
    ↓ 新增: FailureDiagnoser（规则优先）
      失败原因分类: LLM判不可执行 / 执行错误 / 权限拒绝 / 超时
    ↓ 可重试? (原因=执行错误/超时 且 retry_count<max)
      → DecisionBridge 重试(带修正: 补充上下文/换参数)  [AUTO 只读 / ASK 写类]
    ↓ 不可重试? (原因=LLM判不可执行 或 retry 耗尽)
      → 记录失败原因到 Episode (已有)
      → 触发 Replanner: 该 goal 剩余任务是否可替代路径?
         → TaskDecomposer 以"排除失败任务"重新分解 或 标记 goal 阻塞
```

### 6.3 关键判断

区分两种恢复：
- **Retry same command**（已有 retry_policy）→ 不算认知恢复
- **Cognitive replan**（本蓝图）→ 改变后续任务路径

### 6.4 不变量影响

| 不变量 | 影响 | 防护 |
|--------|------|------|
| I-6 Decision 唯一 Mutation Authority | **重试/重规划必须经 DecisionBridge 或 ASK**，禁止绕过 | Replanner 产出新 DAG 仍走 bridge.execute_dag_task |
| Governance | 重试次数上限 + 写类仍 ASK | 复用 R4-B |

---

## 7. L5/L6 — Skill Acquisition & Reuse

### 7.1 现状 Gap

- SkillRegistry/SkillGraph/SkillGraphExecutor ✅（执行+组合 R4）
- **无 SkillLearner / SkillGenerator**（习得 R0）
- MasterAgent.think 有 capability_selector 路径但生产未启用（_capability_selector 默认 None）

### 7.2 目标架构（确定性先行）

```
Episode 聚类 (复用慢通路已有聚类键: goal/tags)
    ↓ 新增: SkillProposer（规则型）
      同 goal 成功 ≥ N 次 (N=3) → 提议新 Skill
      Skill = {trigger: goal/task 描述模式, procedure: 成功任务的
               agent_type+task_type 序列, success_rate, version}
    ↓ Skill 验证 (R4-A 审批)
      写类 skill 或执行代价高 → ASK 待批 (approvals)
      只读类 skill → 自动注册
    ↓ SkillRegistry.register → 持久化
    ↓ 未来: think → capability_selector.select(intent) 命中 → SkillGraphExecutor 执行
```

### 7.3 接线点

| 动作 | 文件 |
|------|------|
| Skill 数据模型 | `capability/skill_registry.py`（已存在, 补 generator 调用） |
| 提议器 | `capability/agents/` 新 agent 或 planning/decomposer 旁路 |
| 验证/审批 | `daemon` R4-B approvals 复用 |
| 选择/执行 | `agent/master_agent.py:_think_with_selector`（已存在, 生产激活 _capability_selector） |

---

## 8. L7 — Generalization

### 8.1 现状 Gap

- LLM 任务转换层提供浅层泛化（E-RUN: "收集数据"→真实只读命令）
- 无跨任务结构迁移：模板分解是 domain 固定模板

### 8.2 目标架构（不新建泛化引擎，靠 Skill 层实现）

```
Skill 积累 (L5/L6) 后:
    Task A 成功 → Skill A (trigger 模式)
    新任务 B 与 A 共享 trigger 特征 (domain/动词/结构)
    → capability_selector 命中 Skill A 的 procedure 变体 → 迁移执行
```

**判断**：Generalization 不是独立模块，是 L5/L6 + L2(记忆近例) 的涌现结果。本蓝图不为其单独建层（Four 不堆叠）。

---

## 9. L8 — Metacognition 影响决策

### 9.1 现状 Gap

- confidence 字段存在于引擎层但**不影响决策**
- ReflectionEngine 有 reflect 但输出不回流 planning
- Self Model: Identity ✅ / capability 自知 ⚠️ / 失败史 ⚠️

### 9.2 目标架构（最小闭环）

```
决策前 (agent.decide):
    新增: CapabilityConfidence 查询 — "此任务类型历史成功率?"
    context["capability_confidence"] = SkillRegistry.query_success_rate(意图)
    → Constitution 之后、Bridge 之前注入
    → 低成功率 (<阈值) + 写类动作 → 自动升级 ASK (治理增强而非削弱)
失败后 (已有诚实失败):
    → 失败原因回写 Skill/Pattern 统计 (accuracy 降)
    → 未来同类任务 confidence 降 → 决策更保守
```

### 9.3 不变量影响

| 不变量 | 影响 | 防护 |
|--------|------|------|
| I-6 Decision 唯一 Mutation Authority | Metacognition 只调 confidence/升级 ASK，不直接授权 | 低置信→更严审批，不放开 |

---

## 10. 实施序（依赖排序）

```
Phase A (L1+L4 基础) — 让失败产生学习信号
    A1: Episode→LearningExample 转换 (L1 输入)
    A2: Failure Diagnoser (L4 前置) — 失败原因结构化
    A3: daemon dream 周期调 LearningEngine.learn (L1 快通路激活)

Phase B (L2+L3) — 让认知有记忆与世界
    B1: recall_context() 真实现 + think 注入 (L2)
    B2: WorldABI 消费接口 + WM sync 读回 (L3)

Phase C (L4 完整 + L5/L6) — 失败重规划 + 技能生长
    C1: Replanner (失败→替代 DAG)
    C2: SkillProposer (成功 N 次→Skill) + 审批
    C3: capability_selector 生产激活

Phase D (L7+L8) — 泛化与元认知涌现
    D1: Skill 命中迁移 (L7)
    D2: CapabilityConfidence 注入决策 (L8)
```

依赖理由：Learning 信号(Phase A)是 Skill(Phase C)与泛化(Phase D)的输入；Recall(Phase B)增强 think 但独立可先行。

---

## 11. 边界表（Scope Freeze）

| 包含 | 不包含 |
|------|--------|
| 快通路样本注入（learn 收真实 examples） | 模型训练（torch/transformers 微调） |
| 慢通路→行为反馈（Belief/Pattern 影响决策） | 新 LLM provider |
| Recall 注入 think 输入 | 新的认知阶段（不新增 ProcessType） |
| Failure 分类 + 重试/替代路径 | 自主写类动作放开（仍 ASK） |
| Skill 自动提议 + 审批注册 | 无审批的 Skill 自执行 |
| Metacognition 置信度调决策保守度 | 新存储系统（复用 SQLite 表/模式） |

---

## 12. 架构成熟度对比（升级前后）

| 维度 | 现在 (v2 实测) | Phase A-D 后（目标） |
|------|---------------|---------------------|
| Experience→Belief/Pattern | R6 慢通路 ✅ | R8（+快通路样本） |
| Experience→行为改变 | R0 | R4 (失败→重试/重规划) |
| Memory→Reasoning | R3 | R6 (recall 进 think) |
| World→Cognition | R0 读 | R4 (WorldABI 消费) |
| Skill 习得 | R0 | R5 (提议+审批+注册) |
| Metacognition | R2 | R4 (置信调决策) |
| 不变量 (I-1~I-8) | 全部保持 | 全部保持（防护表见各节） |

---

## 13. 符合本蓝图原则声明

1. ✅ 零新建基础设施层：全部复用 ProcessType/LearningEngine/WorldStore/SkillRegistry/approvals 现有边界
2. ✅ 不变量表逐项给出（每节 3.5/4.5/5.4/6.4/9.3）
3. ✅ 确定性规则优先（SkillProposer 阈值、Failure 分类、Belief 巩固已规则化）
4. ✅ 每条设计带现有接线点（文件:方法）
5. ✅ 不触碰 Decision 唯一 Mutation Authority（学习/记忆/世界/元认知均无直接 Action 路径）

---

## 14. Next Phase 提案

建议下一步按 Phase A 开始（L1 快通路激活 + L4 失败诊断），因：
1. A1/A2 改动面最小（agent_runtime + master_agent 内聚方法）
2. 立即激活已存在但空转的 LearningEngine（快通路）
3. 失败原因结构化是 Replan(Skill 生长) 的前置依赖

**蓝图到此为止。不进入实现。等批准。**
