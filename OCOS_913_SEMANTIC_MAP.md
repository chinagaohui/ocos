# OCOS 913-File Semantic Reverse Mapping（第一阶段）

> **性质：只读语义映射，不写代码、不改模块。** 由 8 个并行反查代理按冻结契约 §14 判定矩阵跑完。  
> **状态：v0.2 —— 裁决标准已升级（新增 SelfState Impact + 两级裁决门）；映射仍为 domain 级，⑥ 已进 symbol 级。**  
> **文档链**：`OCOS_SELFSTATE_SCHEMA_V1_FREEZE.md`（契约）→ **本文件（反查结果）** → 待：⑥⑦⑧。  
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

## 5. 下一步（⑥⑦⑧，仍不动代码，等批准逐项推进）

```text
⑥ 模块语义映射细化到逐文件（本 file 为 domain 级 v0.1）
   - interaction/（75）、capability/（44）两大声量目录做逐文件分组
   - 判定 personal_memory/event_memory/storage/persistence 的 Merge 目标
   - 判定 os_v1/_archive/examples 全量 Archive 清单
⑦ 从目标"我"反推去留：Retain / Rewrite / Merge / Archive 落到目录
⑧ 形成 P0 / P1 / P2（P0 应含：S2 通电 + Worldview 落地 + delta 链 + custody）
   —— P0 判定依据契约 §1 Growth Invariant，非"功能多"
```

> **红线提醒**：本阶段"有证据能进 X→D→Y"才准进主体核心；"功能很多但哪种连续性都不靠它" → Archive。**代码不再定义 OCOS；SelfState 定义代码该留下什么。**

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