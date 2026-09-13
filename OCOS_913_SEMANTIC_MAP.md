# OCOS 913-File Semantic Reverse Mapping（第一阶段）

> **性质：只读语义映射，不写代码、不改模块。** 由 8 个并行反查代理按冻结契约 §14 判定矩阵跑完。  
> **状态：v0.1 草案（domain 级 + 代表文件级）；完整到"逐文件行级"的颗粒度留作追加遍历。**  
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