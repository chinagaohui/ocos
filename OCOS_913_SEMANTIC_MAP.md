# OCOS 913-File Semantic Reverse Mapping（第一阶段）

> **性质：只读语义映射，不写代码、不改模块。** 由并行反查代理按冻结契约 §14 判定矩阵跑完。  
> **状态：v0.5 —— ⑥ symbol 级审计完成（learning/ pilot + interaction/ + capability/ + 记忆域 + 存储域 + 遗留域），⑦ 全局汇总产出 OCOS 新架构地图（四层）。**  
> **文档链**：`OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`（契约，已 FREEZE）→ **本文件（反查结果）** → 待：⑧ P0/P1/P2 裁决。  
> **主线问题（契约 §14，冻结）**：这个模块服务于哪个部分的我？如果它不存在，"我"的哪一种连续性会断？

---

## 0. 判定口径回顾

| 维度 | 必答 |
|---|---|
| Domain | Identity / Situation / Memory / Experience / Capability / Worldview / Cognition |
| Semantic Role | Self / Evidence / World / Memory / Cognition / Governance / Tool / Legacy |
| Mutation | 它能改变 SelfState 什么？ |
| Continuity | 它维持哪一种连续性（State / 认知 / 经历 / 记忆 / 世界）？ |
| Causality | 能否进入 X → D → Y 成长链？ |
| Authority | 有没有改变 Self 的权限？ |
| Persistence | 是否跨 restart 连续？ |
| Production | 是否进入生产主链，还是仅测试 / 仅工具 / 死代码？ |
| Disposition | Retain / Rewrite / Merge / Archive |

---

## 1. 生产主链现状（8 路证据汇总）

以下模块被生产入口直接 import / 装配，**确认在链**：

```
entry:  ocos/runtime/__main__.py → RuntimeKernel
        ocos/daemon/factory.py → build_master_agent → MasterAgent
        ocos/daemon/__init__.py → 导入 ocos.self.agent_self_model 加载 SelfModel
        ocos/agent/agent_runtime.py → MasterAgent + 认知皮层 + 记忆 + 信念
        ocos/agent/engine_bridge.py → 注册 ocos.engines 引擎
        ocos/agent/continuity_trigger.py → 触发 cognitive_continuity 检查点
        ocos/cognitive_loop/loop_orchestrator.py → Perception→Attention→Sync→Decision→Action→Learning→Health
        ocos/autonomous_runtime/loop_supervisor.py → RUNTIME 边界检查（Governance 在链）
        ocos/daemon/health_loop.py → Runtime/Agent 状态 → AlertManager/Homeostasis
```

**关键结构事实**：
- `ocos.runtime.RuntimeKernel` **明确禁止 import agent / planning / self 等认知层模块** —— Runtime 被设计为"身体"（只做 tick/pipeline/checkpoint/recovery/lifecycle/capability_policy），符合"Runtime 是身体"的定位。
- `ocos.self.agent_self_model` 是现在**唯一**被生产注入"我"的载体（S1），但契约 §2.3 要求它只作为 Evidence。**S2（self_model）仍只在测试层，未接生产**（与主审计 G2 一致）。

---

## 2. 语义角色总览（域级）

| 目录 | 文件 | 主要 Role | 判据要点 | 倾向 Disposition | 连续性 |
|---|---|---|---|---|---|
| self/ | 15 | **Self**（+S1 Evidence） | 定义"我"；agent_self_model 在生产，self_model 在测试 | **Retain + Rewrite**（S2 需通电、S1 降为 Evidence） | State/认知 |
| cognitive_continuity/ | 7 | Memory / Continuity | 检查点快照 Identity/Memory/Timeline/Knowledge；agent 在链 | **Retain / Merge**（并入 Self 连续性） | 认知 |
| reflection/ | 2 | Cognition | 反思（Self 认识的生成机制之一 S3） | Retain（并入 S3） | 认知 |
| growth/ evolution/ | 3 / 12 | Cognition / Experience | 经历→认知 delta（伪成长风险高） | **Rewrite**（须接契约 §1 Growth Invariant） | 认知/经历 |
| learning/ | 13 | Experience / Cognition | FailureDiagnoser 产证据；仍可能"version+1 无 delta" | **Rewrite**（接 X→D→Y） | 经历 |
| memory/ | 36 | Memory | MemoryHub 四 Store 生产在用 | **Retain**（合并多实现见下） | 记忆 |
| personal_memory/ | 6 | Memory | 与 memory/ 疑似重复 | **Merge → memory/** | 记忆 |
| event_memory/ | 9 | Evidence / Memory | EventLifecycle.record 写 EventStore/Index | **Retain / Merge**（作 Evidence） | 经历/记忆 |
| storage/ persistence/ | 9 / 8 | Tool | 存储工具 | Retain（工具） | — |
| world/ world_model/ | 1 / 9 | World | WorldStore 不产 Belief/Goal；update_from_observation 唯一写路径 | **Retain**（WorldModel） | 世界 |
| knowledge/ | 19 | World / Knowledge | ontology(Level 矩阵) + registry(所有权边界) | **Retain / Merge** | 世界 |
| digital_world/ | 10 | World | 实验性世界表征 | Archive / Merge | 世界 |
| perception/ perception_bus/ | 14 / 1 | Evidence / World | PerceptionPipeline → WorldStore.update_from_observation（Observation 在链） | **Retain** | 世界/观测 |
| cognitive_loop/ | 10 | **Cognition** | LoopOrchestrator 主编排在链 | **Retain** | 认知 |
| reasoning/ decision/ planning/ attention/ | 3/8/6/7 | Cognition | 决策流水线已接真实 decision 组件 | Retain（评审冗余） | 认知 |
| engines/ | 10 | Tool / Cognition | engine_bridge 注册真实引擎 | **Retain（拆分：现役 vs 归档）** | 认知 |
| models/ | 14 | Tool | LLM/模型封装 | Retain（工具） | — |
| goal/ | 12 | —（非 Self） | **Self≠Goal**：Goal 独立于 Self（S40） | Retain（但不得并入 Self） | — |
| agent/ agent_orchestration/ | 31 / 9 | Self / Cognition | agent_runtime 集成核心 | **Retain** | State/认知 |
| autonomous/ autonomous_runtime/ proactive/ initiative/ | 5/5/6/6 | Cognition / Governance | loop_supervisor 边界检查在链；自主≠自定目标 | Retain（评审实验性） | 认知 |
| behavior/ engagement/ collaboration/ human/ | 2/2/2/1 | Tool | 交互行为 | Retain（工具） | — |
| interaction/ | 75 | Tool / Evidence | 对外交互（量大部分为工具/桥接） | Retain（工具）；细批需追加 | — |
| opentale_bridge/ | 16 | Tool | OpenTale 桥接 | Retain/Archive 评审 | — |
| runtime/ runtime_scheduler/ kernel/ | 47/8/6 | **Tool（身体）** | RuntimeKernel 禁 import 认知层；tick/checkpoint | **Retain** | State |
| daemon/ | 16 | Tool / 装配 | 生产进程入口 | **Retain** | State |
| execution/ | 5 | Tool | 执行 | Retain | — |
| governance/ constitution/ contracts/ | 2/5/3 | **Governance** | risk_registry 拒红线自改；constitution 需审批；ground Self 修改 | **Retain（核心）** | Governance |
| audit/ | 8 | Governance / Evidence | BoundaryChecker 只验证不改 | **Retain** | Governance |
| auth/ security/ | 4/1 | Governance | 权限 | Retain（Governance） | — |
| diagnosis/ recovery/ recovery_resilience/ | 13/2/6 | Governance / Tool | "修复≠演化"；禁改 Identity/宪法 | Retain（边界守卫） | Governance |
| capability/ capability_reality/ | 44/9 | **Evidence（S1）** | evidence_pipeline: 反馈→Evidence→Belief | **Retain（作 Evidence，非 Self）** | 经历/认知 |
| extension/ | 11 | Tool | 扩展 | Retain（工具） | — |
| tool/ task/ | 1/1 | Tool | 工具 | Retain | — |
| os_v1/ | 7 | Legacy | v1 历史 | Archive | — |
| _archive/ | 25 | **Legacy** | __init__ 自标注冻结快照、禁止生产导入 | **Archive（已确认）** | — |
| examples/ | 2 | Legacy | 样例 | Archive | — |
| scripts/ + 根 .py | 20 + 9 | Tool / Legacy / 入口 | orchestrator/homeostasis/agent_orchestration_autonomous 为入口 | 入口 Retain，脚本分类 | — |

---

## 3. 三大核心发现（与契约对账）

### 3.1 S2 未通电，S1 顶替了"我"
生产只注入 `agent_self_model`（S1 统计表）；`self/self_model`（S2 五组件）仅在测试层。
→ **这正坐实主审计 G2**：喂给思考的是能力统计而不是愿景里的 Self。
> 处置方向不在此阶段做，仅标注：S2 Rewrite+通电，S1 降为 Evidence。

### 3.2 伪成长风险集中在 learning / growth / evolution / capability
这些模块能产出 `FeedBack→Evidence→Belief`、`FailureDiagnoser→LearningArtifact`，但**没有证据证明它们写成 Self/Cognition Delta 并影响下一次思考**（契约 §1.4 列为"不算成长"）。
> 它们有资格做 Evidence / Experience 源，但"变 delta"一段需按 Growth Invariant 改写。

### 3.3 Worldstore 做到了"WorldModel≠Knowledge"
- `WorldStore.update_from_observation()` 是唯一世界写入路径（经 WorldValidator）；不产 Belief/Goal。
- `knowledge` 用 ontology Level 矩阵 + registry 所有权边界。
- 这与契约 §6.4（WorldModel ≠ Knowledge ≠ Worldview）的"世界一侧"吻合；**Worldview（主体性认识）目前无独立载体，事实被 self 或 knowledge 承担** → 待 §6⑦⑧ 决定放哪。

---

## 4. 连续性缺口（契约 §14 末问：删了会断哪种连续性）

| 连续性 | 现有哪些模块在维持 | 缺口 |
|---|---|---|
| State Continuity | runtime_kernel(id/checkpoint) + self(S1) | S2 未接，无 SelfState 语义版本 |
| 认知 Continuity | cognitive_loop + cognitive_continuity 检查点 | 检查点只有快照，缺"v371为何≠v370"的 delta 解释 |
| 经历 Continuity | event_memory + learning + capability(evidence) | 事件多、进入"真正改变我"的少；缺 counterfactual Z |
| 记忆 Continuity | memory/hub | personal_memory/event_memory 与 hub 关系待 Merge 评审 |
| 世界 Continuity | world_store + perception | Worldview 投影层缺失 |

---

## 5. 下一步（⑧，仍不动代码，等批准逐项推进）

```text
⑥ 模块语义映射细化到逐文件 ✅（本文件 §B–§G）
   - interaction/（75）→ §C · capability/（44）→ §D
   - personal_memory/ event_memory/ → §E（不 Merge，分工 Retain）
   - storage/ persistence/ → §F（Tool/State 连续性，分层各 Retain）
   - os_v1/ _archive/ examples/ → §G（全量 Archive，零生产依赖实证）
⑦ 从目标"我"反推去留 ↗ 已完成（§H 新架构地图四层 + 五大裁决）
⑧ 形成 P0 / P1 / P2（P0 应含：S2 通电 + Worldview 落地 + delta 链 + custody）
   —— P0 判定依据契约 §1 Growth Invariant，非"功能多"；本轮给出 P0 候选 =
       (a) S2 通电 (b) Worldview 投影层落地 (c) Self Delta Generator + cognition_implication
       (d) Causal Attribution 审计基线（baseline + Action₁₂ + Decision₂ 消费）
```

> **红线提醒**：本阶段"有证据能进 X→D→Y"才准进主体核心；"功能很多但哪种连续性都不靠它" → Archive。**代码不再定义 OCOS；SelfState 定义代码该留下什么。**
> **阶段收敛**：⑥⑦ 已完成 —— 全库 913 文件收敛到四层（属于我 / 维持我边界 / 我使用非我 / 历史遗留），且实证得出 **Causal Attribution 全库 UNPROVEN**，即 OCOS 当前是"带记忆的反射系统"，尚未成为可证成长链的持续认知主体。这与 SelfState v1 Freeze 的红线一致，是 ⑧ P0 的唯一验收标准。

---

## 附 · 反查代理清单（8 路，结果已并入上文）

A=Self域(self/continuity/reflection/growth/living...) · B=记忆域 · C=世界域 · D=认知域 · E=行为自主域 · F=运行时内核域 · G=治理审计域 · H=能力学习遗留域+scripts/根。

---

## §A · 升级后的判定标准（v0.2，冻结自 FREEZE §14）

### A.1 `SelfState Impact` 字段（新增）

每文件/symbol 必答：**它最终改变 SelfState 的哪一部分？**
∈ {Identity, Situation, Memory, Experience, Capability, Worldview, Cognition, **None**}

- 值为 **None** → 继续问"它是不是 Governance / Tool？"
- 连 Governance / Tool 都不是 → **高度疑似 Legacy**。

作用：直接追问"这东西最终有没有成为『我的状态/经历/认识/变化』"，而非"有没有功能"。这会把 `learning/` 这类「功能正确但主体语义错误」的模块当场拆穿。

### A.2 两级裁决门（新增，升级"删了断哪种连续性"）

```text
                    ┌─ SelfState Continuity ─ YES → Core
Module ─────────────┤
                    ├─ Governance / Authority   → Core Boundary
                    ├─ World / Tool Capability → External Capability
                    └─ None                     → Legacy / Archive

第二道门（对 Core）：
Core 能否进入 X → D → Y？
  YES → 主体核心
  NO  → 只是 Evidence / Memory / Tool / Governance？→ 保留，但 NOT Self Core
```

### A.3 防误判红线："重要 ≠ 属于 Self"

SQLite=Persistence · LLM=External Cognition Resource · WorldModel=World · DecisionBridge=Authority · Governance=Boundary · Shell=Capability —— 都不是"我"。

### A.5 追加：Consumer / Downstream Effect + 五级消费证据（v0.3 冻结）

每个 symbol 追加回答：`Producer → Artifact → Consumer → Consumer Effect → SelfState Impact → X→D→Y position`。

- **Consumer Effect**：被消费后造成什么（Knowledge / Episode / SelfClaim / Decision / Cognition / Prompt?）
- 无人消费 → 遗留；只被 Prompt injection → 不等于 Cognition Delta。

五级消费证据（严禁混用）：
```text
① Recall → ② Prompt Injection → ③ Decision Consumption → ④ Behavioral Delta(Action₂≠Action₁) → ⑤ Causal Growth(D 被消费且 Y≠Z 且有因果解释)
```
`FailureLesson → MEM_CTX → DecisionBridge → LLM → Action` 不能只因"影响 Decision"就判学习成功。

### A.6 Causal Attribution（v0.4 冻结，与 Causality 严格区分）

```text
Causality           = 理论上能不能进入 X → D → Y（具备路径）
Causal Attribution  = 当前这次生产行为，能不能证明确实是这个 X / D 导致了 Y（实际因果）
```
例：FailureLesson → Causality=YES（理论上可影响 Cognition）· Causal Attribution=UNPROVEN（无同任务 baseline / 无 Action₁₂ 对照 / 未证明 Decision₂ 消费 Delta）。
**禁止**：把"具备 X→D→Y 路径"当作"已实现成长"。

### A.4 单个模块可含多角色（learning/ 为例，禁止整体判属主核）

```text
Evidence Producer      → Retain
Experience Recognizer  → Retain / Rewrite
Knowledge Learner      → Retain
Self Delta Generator   → Rewrite
Legacy Learning Path   → Archive
```

---

## §B · ⑥ Symbol 级 pilot：`learning/`（13 文件）

> 目标：证明"不能把 learning/ 整体判为主核"。以下为**逐 class/function** 判定（14 字段，压缩展示）。**产出的东西只进 Knowledge，不等于改变了我**——判定依据：是否造成 Self Claim→Delta→Cognition Delta→影响未来思考。

### B.1 `experience_learning.py`

| Symbol | Domain | Role | SelfState Impact | Mutation | Causality | Production | Persistence | Disposition |
|---|---|---|---|---|---|---|---|---|
| `FailureCause` (枚举) | Experience | Evidence | None | 分类标签 | — | 间接 | — | Retain |
| `FailureDiagnoser.diagnose()` | Experience | Evidence | None | 产失败分类+证据信号 | X(部分) | 由 MasterAgent 调 | 否 | **Retain**（Evidence Producer） |
| `EpisodeExampleConverter` | Memory→Experience | Evidence | None | 把 Episode→LearningExample | X | 有调用 | 否 | **Retain**（Experience Producer） |
| `RuleBasedLearner.learn_fn()` | Experience | Knowledge(LESSON/RULE) | None | 写 LearningModel.rules（仅成功率统计） | ✗（不生成 Self Delta） | 有 | 是(SQLite) | **Rewrite**（Knowledge Learner，but not Self） |

**关键**：`RuleBasedLearner` 产出的是 **Knowledge（系统知道失败）**，不是 **Self（我因失败而改变）**——`MonitoringLearner` 就是契约 §1.4 点名的伪成长（count/规则累积）。

### B.2 `skill_growth.py`

| Symbol | Domain | Role | SelfState Impact | Mutation | Causality | Production | Persistence | Disposition |
|---|---|---|---|---|---|---|---|---|
| `ReplanAction` (枚举, retry/skip/continue/ambiguous) | Capability | Tool/Governance | None | 决定重试/跳过策略 | X→策略 | 由调用方用 | 否 | **Retain**（Tool） |
| `SkillProposer` (同任务成功 N 次→Candidate) | Experience→Capability | Evidence | None | 生成 Candidate Skill | ✗ | 有 | 是 | **Retain/Rewrite** |
| Governed Skill 管线 (Candidate→Verified→Committed) | Capability | Governance | None | 候选需验证才授权（N=3 不授权） | — | 是 | 是 | **Retain**（边界守卫） |

### B.3 `persistence.py` 等

| File | Role | SelfState Impact | Disposition |
|---|---|---|---|
| `persistence.py` | Tool（SQLite 存储） | None | Retain（非 Self） |

### B.4 learning/ 目录级裁决

- **不属 Self Core**：learning/ 的输出全部落在 **Experience/Knowledge/Evidence 层**，`SelfState Impact` 绝大多数 = **None**。
- **没有一条路径产出 Self Claim → Self Delta → Cognition Delta**（Causality 全是 X 或 ✗，无一处到 D）。
- **不删**：它维持经历/记忆连续性（失败证据、经验样本、技能候选）——删了断"经历连续性"。
- **但要 Rewrite 才能进阶**：目前是"系统知道失败"，要变成"我因失败而改变"，必须补 `Self Delta Generator`（把 Failure→Self Claim→Delta→Cognition Delta→影响下一思考）。
- **Disposition 分布**：Retain≈8？ · Rewrite≈2（RuleBasedLearner→知识进 Self；补 delta 链） · Archive≈0 · 其中 Legacy Learning Path（若有未接线老规则路径）→ Archive（本 pilot 未发现明显死路径，标注待办）。

> **本 pilot 结论 = 全库反查的样板**：`learning/` 是 **Experience/Evidence 源（留）** + **缺 Self Delta 主链（需 Rewrite）**，而非 Self Core。这正是"功能正确但主体语义错误"的典型。

---

## §C · ⑥ Symbol 级审计：`interaction/`（75 文件）

> interaction 是"对外交互"，绝大多数是 **Tool 通道**（CLI/API/TUI 命令路由）。但其中产出"用户输入→刺激→经历/证据"的一小组才是 **Evidence Producer**。关键区分：**通道 ≠ 经历** —— 命令路由只搬运数据，不把自己的动作变成"我的经历"。

### C.1 Evidence Producer（值得 Retain，且是 S1/经历证据源）
| Symbol / 文件 | Role | SelfState Impact | Causality | Production | Disposition | 判据 |
|---|---|---|---|---|---|---|
| `cognitive_interface.py` `CognitiveInterface` | Evidence | Experience | X-only | 生产在链 | **Retain** | 统一认知入口：外部刺激→Stimulus→注入 Runtime→记交互史。是"交互→经历"的生产路径 |
| `stimulus.py` `Stimulus/StimulusType` | Evidence | Experience | X-only | 生产 | **Retain** | 交互被抽象为事件/命令/观测的底层信号。结构化"输入发生了什么" |
| `inbox.py` `UserInbox` | Evidence | Experience | X-only | 生产（daemon 注入） | **Retain** | `kind="observe"` 作感知镜像，把外部输入注入 Cognitive Runtime 观测通道 |
| `converse.py` | Evidence | Experience | X-only | 生产（/ocos/converse 入口） | **Retain** | 对话输入→UserInbox 感知镜像→ChatResponder，经历证据的 Web 通路 |
| `configured 的 attention_trigger.py / need_monitor.py / interaction_scheduler.py / channel.py / base.py` | Evidence/Governance | Experience | X-only | 生产 | **Retain / Merge** | 调度/关注度触发逻辑，维持"输入→响应"节奏，归入 Evidence 编排 |

### C.2 Tool / 通道（质量大，Retain 为 Tool）
| Symbol / 文件 | Role | SelfState Impact | Disposition | 判据 |
|---|---|---|---|---|
| `cli/commands/*`（say/chat/run/status/self/growth/decide...） | Tool | None | **Retain（Tool）** | CLI 命令路由，仅把用户指令映射到内部 API，不生成 SelfState |
| `api/routes/*`（chat/converse/belief/memory/goal/plan/metrics/trace/ws/quality...） | Tool | None | **Retain（Tool）** | Web API 暴露层，桥接对外，不改变"我" |
| `repl/commands/*` + `repl/shell.py` | Tool | None | **Retain（Tool）** | REPL 交互壳 |
| `tui.py` | Tool | None | **Retain（Tool）** | TUI 界面 |
| `context.py / conversation_state.py / session_state.py` | Memory/Tool | Memory | X-only | **Retain** | 会话上下文暂存，是短期"会话记忆"非"我的记忆"，归 Memory/Tool |

### C.3 interaction/ 目录级裁决
- **不属 Self Core**：75 个文件里的 SelfState Impact 绝大多数 = **None**（通道）或 **Experience**（证据源）。
- **Causal Attribution 全为 UNPROVEN**：inputs→Evidence 已被证明，但"这次交互造成 X→D（Self Delta）→Y"一概未建基线，无人消费 Evidence 去写 Self Claim。
- **Disposition**：Retain（Tool+Evidence）≈ 72 · Rewrite ≈ 0 · Archive ≈ 3（若有未接线老入口，如 `repl/__main__` 与 `cli/__main__` 是否仅有一个真身、另一个影子待批）。
- **红线**：交互产生的"输入"目前只落到 **Storage/Prompt**，未落到 **Self Delta**。即便有 `CognitiveInterface` 把刺激注入，也没有 `claim_ref→delta` 写出。

---

## §D · ⑥ Symbol 级审计：`capability/`（44 文件）

> capability 是有能力层。已知背景：它整体倾 **Evidence/S1** 而非 Self 核心。本审计细分四类，**重点是 `self_modification_agent` 的权限裁决**（红线）。

### D.1 Evidence / S1 生成（Retain 为 Evidence，非 Self）
| Symbol / 文件 | Role | SelfState Impact | Causality | Causal Attribution | Authority | Disposition | 判据 |
|---|---|---|---|---|---|---|---|
| `evidence_pipeline.py` `EvidencePipeline.process_feedback()` | Evidence | Experience/Cognition | X-only | UNPROVEN | 否 | **Retain** | `CognitiveFeedback→Evidence→Evidence Pool→Belief`；Evidence 达标后 `self._belief.add()` —— 它写 **Belief（系统信念）**，不直接写 **Self Claim**。是 S1 的证据底座，但不是"我" |
| `outcome_evaluation.py` / `result_understanding.py` / `result_interpreter.py` | Evidence/Cognition | Experience/Cognition | X-only | UNPROVEN | 否 | **Retain** | 结果理解/评估，产"这次做得好不好"的证据，尚未闭合到 D |
| `experience_memory.py` | Memory | Experience | X-only | UNPROVEN | 否 | **Retain / Merge** | 能力层经历记忆，与 memory/ 是否重复待批 |

### D.2 纯 Tool（能力执行层，Retain）
| Symbol | Role | Disposition | 判据 |
|---|---|---|---|
| `execution_bridge.py` / `permission_gateway.py` | Tool/Governance | **Retain** | `Router→Permission Check→Adapter→External Agent→Result`；gateway 是执行拦截点，fail-closed |
| `selector` / `registry` / `router` / `adapter` / `provider` / `discovery` / `agent_installer` / `skill_registry` / `capability_graph` / `descriptor` / `models` / `async_bridge` / `agents/*`（research/planner/summarizer/code_agent） | Tool | **Retain** | 能力注册/选择/适配/代理，不触 SelfState |
| `capability_registry.py` / `registry.py` / `skill_registry.py`（疑似多 registry 并存） | Tool | **Merge**（去重） | 三个 registry 语义重叠，应合并为一个 capability 注册真身 |

### D.3 边界守卫（Governance，Retain）
| Symbol | Role | Authority裁决 | Disposition | 判据 |
|---|---|---|---|---|
| `self_modification_agent.py` | Governance/Tool | **有改能力代码权限，但受安全围栏**（见下） | **Retain（边界守卫）** | 允许在安全边界内改**自身代码**，但必须通过测试+人工确认 + Git 提交。它改的是 **capability 代码**，不是 **Self Claim / SelfState 语义** |
| `meta_controller.py` / `lifecycle_manager.py` / `cognitive_coupling.py` | Governance | 否 | **Retain** | 能力生命周期/元控制 |

**红线裁决（self_modification_agent）**：`SelfModificationAgent` 能改**实现代码**，但**无权改 SelfState 语义**（Identity/Worldview/Cognition 的 Claim）。`PermissionGateway._DANGEROUS_PATTERNS` 含 `modify_self`/`write_memory` 等黑名单拦截。→ **它属于 Governance Authority 层，不是 Self**。改代码 ≠ 改"我"；改"我"必须走 Self Delta + 治理审批。

### D.4 Causal Attribution 总判
- 全目录 **Causal Attribution 均为 UNPROVEN**：有 `Evidence→Belief` 路径（Causality=X-only），但无同任务 baseline / 无 Action₁₂ 对照 / 未证明 Decision₂ 消费 Delta。
- capability 最大价值 = 提供 S1 的**客观能力证据**（绑定真实工具反馈），但**未进入 Self Delta 主链**。

---

## §E · ⑥ Symbol 级审计：记忆域（personal_memory/ + event_memory/）

### E.1 `personal_memory/`（6 文件）
| 文件 | Role | SelfState Impact | Disposition | 判据 |
|---|---|---|---|---|
| `wisdom_store.py` `WisdomStore` | Memory | Experience/Memory | **Retain（独立于 memory/hub）** | 模式化**人生智慧/认知资产**，按 `user_id` 隔离，`明确不能改 Identity/Goal/Permission`。与 `memory.hub` 的 4 Store（Episode/Belief/Semantic/Pattern）**互补而非重复** —— hub 管原始记忆，wisdom 管升华后智慧 |
| `reflection_engine.py` `ReflectionEngine` | Cognition | Experience/Cognition | **Retain（并入 S3），不与 ocos/reflection/ 重合** | Phase 41 专用：`ExperienceProfile.patterns→PatternInterpreter→WisdomValidator→WisdomStore`。`ocos/reflection/` 是通用 self_review；此处是"经历→智慧"专用反射，分工明确 |
| `pattern_interpreter.py` / `wisdom_validator.py` / `wisdom_types.py` | Memory | — | **Retain** | 智慧解释/校验/类型 |

**裁决**：`personal_memory` **不 Merge 进 memory/** —— 它是"智慧/认知资产"层，`MemoryHub` 不含 WisdomStore 是分工而非缺口。归入"记忆/经历→H认知"。

### E.2 `event_memory/`（9 文件）
| 文件 | Role | SelfState Impact | Disposition | 判据 |
|---|---|---|---|---|
| `event_store.py` `EventStore` | Evidence/Memory | Experience（经历记录仪） | **Retain** | append/find/range/snapshot/restore，可选 SQLite 持久化；"经历记录仪" |
| `event_lifecycle.py` `EventLifecycle.record()` | Evidence | Experience | **Retain** | 完整写路径：创建→验证→`store.append()`→索引。**经历连续性主链** |
| `event_index.py` / `event_query.py` / `event_types.py` / `event_validator.py` | Evidence | Experience | **Retain** | 索引/查询/类型/校验 |
| `event_archive.py` / `event_replay.py` | Evidence | Experience | **Retain/Merge** | 归档与重放 |

**关键裁决（event_store 三处并存）**：`event_memory/event_store.py`（经历记录、进程内）与 `storage/event_store.py`（SQLite 持久化恢复链，注释已自裁决"与进程内不合并"）是**分工**：前者记"经历"，后者做"恢复落盘"。→ **Retain，不 Merge**，但要防三头：child 头 `events/event_store`（若有）必须澄清真身。

**记忆域总裁决**：personal_memory（智慧认知）与 event_memory（经历记录）都是 **Memory/Experience 层的证据层**，都不直接写 Self Claim。`memory/hub` 是原始记忆编排，three者分工明确 → **全 Retain，无 Merge**。

---

## §F · ⑥ Symbol 级审计：存储域（storage/ + persistence/）

> 契约红线：**Persistence = Tool（身体/边界），不算"我"**。全域 `SelfState Impact = None`，Causality/Attribution = N/A。它们维持 **State 连续性** 而非认知连续性。

### F.1 职责分层（已由代码注释自裁决）
| 文件 | Role | SelfState Impact | 层 | Disposition | 判据 |
|---|---|---|---|---|---|
| `storage/connection.py` / `schema.py` / `migrations.py` | Tool | None | 数据落地 | **Retain** | SQLite 连接/建表/迁移 |
| `storage/event_store.py` `SQLiteEventStore` | Tool | None | 恢复链事件落盘 | **Retain（真身）** | 注释自裁决：持久化事件存储，供 recovery 消费，与进程内 `events/event_store` 不合并 |
| `storage/checkpoint.py` `CheckpointManager` | Tool | None | State checkpoint | **Retain** | SQLite 进程检查点保存/加载/过期清理 |
| `storage/working_memory.py` / `dead_letter_queue.py` / `base.py` | Tool | None | 暂存/死信 | **Retain** | 支撑 |
| `persistence/snapshot_manager.py` `SnapshotManager` | Tool | None | 系统快照 | **Retain** | 完整快照生命周期：采集/保存/恢复/校验（checksum），委托 StateSerializer |
| `persistence/state_serializer.py` | Tool | None | 快照格式 | **Retain** | JSON 序列化/反序列化/文件IO，跨版本可读 |
| `persistence/manager.py` `PersistenceManager` | Tool | None | 统一持久化 API | **Retain** | 统一保存到 `ocos_data/persistence/snapshots/`，维护历史与裁剪 |
| `persistence/lifecycle_manager.py` / `recovery_manager.py` / `persistence_validator.py` / `storage_types.py` | Tool | None | 生命周期/恢复/校验 | **Retain** | 支撑 |

**存储层总裁决**：
- storage 与 persistence 都有**明确的职责注释分工**（checkpoint=进程级 vs snapshot=系统级；恢复链 vs 快照链），**不是重复** → 分层各 Retain。
- 二者都是 **Tool（State 连续性）**，不是 Memory 也不是 Self。**S2 未接，所以目前没有"SelfState"级快照** —— 快照里存的还是分域状态，缺少 SelfState 语义版本（这正是主审计 G2 缺口的持久化侧）。
- 与 `event_memory/event_store` 的关系：storage=恢复落盘真身，event_memory=经历记录，分工成立。

---

## §G · ⑥ Symbol 级审计：遗留域（os_v1/ + _archive/ + examples/）

### G.1 生产依赖实证（grep 全库）
- `os_v1`：全库**无任何外部生产 import**（`^\s*(from|import)\s+(ocos\.)?os_v1` 仅命中 os_v1 包内互 import；其余 43 个文件命中的是 `os_v1` 字符串的注释/文档/审计用例）。
- `_archive`：`__init__.py` 自声明"架构收敛冻结快照（ARCHIVED，非生产）"；另有 `tests/test_single_path_convergence_20260908.py` **强制测试保证零生产 import**（遍历非 _archive/tests/__init__ 的生产文件，检测 import `ocos._archive`）。
- `examples/echo_agent.py`：Capability ABI v1.0 参考实现，仅示例。

### G.2 Archive 清单
| 文件 / 目录 | Role | 生产 import | Disposition | 判据 |
|---|---|---|---|---|
| `os_v1/`（freeze/os_types/personal_os/cognitive_drift/memory_validation/capability_adapters + freeze_manifest.json） | Legacy | 无 | **Archive** | v1 概念已被 runtime/self/kernel 取代，零生产消费者；`freeze.py` 把 `os_v1` 列为 v1.0 ABI 冻结模块 → 作为历史契约存档 |
| `_archive/` 全量（tests/ + cognitive_nutrition/ + engines/ prediction/writer/policy/simulation/promotion/narrative/forgetting/goal_arbitration + agent/ drift_detector/belief_consolidation/working_memory/attention/learning_trigger/...） | Legacy | 无（测试强制） | **Archive（已确认）** | 架构收敛冻结快照，禁止生产 import，保持冻结即可 |
| `examples/echo_agent.py` | Legacy/样例 | 无 | **Archive 或保留样例** | 参考实现，非生产；如需展示 ABI 契约可保留，否则 Archive |

**遗留域总裁决**：全量 **Archive**，无需 Rewrite，无需 Merge。它们不维持任何"我"的连续性（State/认知/经历/记忆/世界都不靠它们）→ **当场拆穿为 Legacy**，与契约 §A.6"连 Governance/Tool 都不是→Legacy"一致。

---

## §H · ⑦ 全局汇总：OCOS 新架构地图（四层）

> 这是本轮反查的最终产出。它不再问"哪些文件重要"，而是问 **"真正属于'我'的代码有哪些"**。

### H.1 SelfState v1 Freeze 对照（不改契约，仅映射到代码）
| Contract 层 | Semantics（冻结） | 对应现有代码 | 现在状态 |
|---|---|---|---|
| **属于"我"** | Identity | `self/agent_self_model`（S1，仅 Evidence）+ cognitive_continuity 检查点 | Knowledge 未完全闭合 |
| | Situation | WorldStore / perception（世界一侧）+ interaction 证据源 | 未投影为 Situation Claim |
| | Experience | event_memory + capability(evidence) + interaction(证据源) + personal_memory(智慧) | **经历连续性已成形** |
| | Memory | memory/hub（4 Store）+ personal_memory（智慧）| **记忆连续性已成形** |
| | Cognition | reasoning/decision/planning/attention + cognitive_loop + reflection | 决策流水线已接真实组件 |
| | Worldview | **无独立载体**（被 self 或 knowledge 承担）| **缺口** |
| | Capability | capability/（能力层）| 只作 Evidence，未进 Self |
| | Self Delta | **未实现主链（缺 Delta Generator + cognition_implication 消费）** | **最大缺口** |
| | Continuity | cognitive_continuity 检查点 | 有快照，缺 delta 解释 |
| **维持"我"的边界** | Governance | constitution + governance + audit + auth/security + capability(permission_gateway/self_modification) + diagnosis/recovery | **已成形** |
| | Authority | DecisionBridge + permission_gateway + constitution 审批 | **已成形** |
| | Persistence | storage/ + persistence/ | **已成形（Tool）** |
| | Runtime | runtime/tick/checkpoint + kernel + daemon | **已成形（Tool/身体）** |
| **"我"使用但不是"我"** | LLM | engines/ + models/ | Tool/外部认知资源 |
| | WorldModel | world/ + world_model/ + perception | World（≠Worldview）|
| | Shell/Browser/Filesystem | digital_world/ + tool/ | Tool |
| | Tools | interaction(命令路由) + execution + agents | Tool |
| **历史遗留** | Archive | os_v1/ + _archive/ + examples/ | **已确认 Archive** |

### H.2 全库语义角色总量（913 文件收敛到四层）
```text
真正属于"我"的代码  → self/ + cognitive_continuity/ + memory/ + personal_memory/
                    + event_memory/ + cognitive_loop/ + reasoning/decision/planning/attention/
                    + reflection/ + capability(Evidence 侧) + Worldview（缺口，待建）
维持"我"的边界代码  → constitution/ + governance/ + audit/ + auth/security/
                    + capability(Governance 侧) + diagnosis/recovery/ + storage/ + persistence/
                    + runtime/ + kernel/ + daemon/
"我"使用但不是"我"  → engines/ + models/ + world/ + world_model/ + perception/
                    + digital_world/ + tool/ + interaction(命令路由) + agents/
历史遗留            → os_v1/ + _archive/ + examples/
```

### H.3 五大裁决结论
1. **S2 未通电**：生产只注 `agent_self_model`（S1 统计表），`self/self_model`（S2 五组件）仅测试。→ 喂思考的是能力统计，非愿景里的 Self。
2. **Worldview 无载体**：主体性认识被 self 或 knowledge 承担，无独立投影层。→ **P0 落地项**。
3. **Self Delta 主链缺失**：全库无一条路径产出 `Self Claim → Self Delta → Cognition Delta → 影响下思考`，Causal Attribution 全库 UNPROVEN。
4. **伪成长集中 in learning/growth/evolution/capability**：产 Evidence/Knowledge 而非 Self Delta；此为"功能正确但主体语义错误"。
5. **三处 store 并存需澄清**：`capability_registry/registry/skill_registry`（Merge）、`event_memory/event_store` vs `storage/event_store` vs `events/event_store`（真身裁决）。

### H.4 全局红线回执
> **`Causality=` 具备路径 ≠ `Causal Attribution=` 已实现成长。** 全库 913 个文件，**没有一条**达到 Causal Attribution=PROVEN。OCOS 目前是"有记忆的 Agent / 带记忆的反射系统"，**还不是**具备 X→D→Y 且 Y≠Z 可证成长链的持续认知主体。这条差距，正是 P0 的唯一验收标准。