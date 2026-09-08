# Cognitive Runtime Single-Path Convergence Decision v1.0

| 项 | 值 |
|---|---|
| 状态 | **FROZEN DECISION**（架构冻结令，随 AFP 体系生效） |
| 审计来源 | agent/ 二级联通审计（A-J 十层 × 五档定级，2026-09-08）+ Cognitive Runtime Convergence Audit（三验证点 V1-V3 + R1-R4 裁决） |
| 证据基线 | journalctl 7 天 logger 分布、~/.ocos/ocos.db episodes 分布、daemon/factory.py 装配精读、agent_runtime tick 十步源码核实 |
| 裁决人 | 用户（2026-09-08 终审收口） |
| 上位文档 | ARCHITECTURE_FREEZE_PROTOCOL.md、DECISION_OWNERSHIP_MAP.md |

---

## 一、六条冻结令（Convergence Decision Freeze）

1. **AgentRuntime 是唯一 Cognitive Runtime Host。** 生产认知主链唯一形态：`daemon → RuntimeKernel → pipeline(8 stage) → AgentRuntime.tick(10步) → TaskDAG → DecisionBridge → Permission/Execution → Event/Observation/Persistence`。
2. **DecisionBridge 是生产 Decision/Mutation Authority。** 经 PermissionGuard → ASK/PendingStore → 审批 → 沙盒执行链行使。
3. **`OCOS_ENABLE_COGNITIVE_LOOP=1` 在本裁决的 Migration 完成并通过 Single-Path Production Verification 之前持续禁止。** 打开即构成双认知循环并行生产事故风险。
4. **Legacy 器官严禁直接删除。** 全部走六档 disposition：KEEP / MERGE / RE-HOST / DEGRADE / ARCHIVE / DELETE（DELETE 仅限末阶段）。
5. **LearningEngine 是唯一明确的 Legacy→New RE-HOST 候选。**
6. **ResultUnderstandingLayer 暂不因"理论完整性"而强制激活**（R1 裁决，ARCHIVE）。

## 二、三态架构模型（现状精确定义）

```
Legacy Cognition                    Production Runtime（唯一主链）
MasterAgent                selective      RuntimeKernel
  ↓ DecisionLoop           borrowing        ↓ AgentRuntime (10-step tick)
  ↓ CognitiveBridge      ┌──────────→      ↓ TaskDAG / DecisionBridge
  ↓ 5 Engines            │ borrowed:        ↓ Permission / Execution
                         │ MasterAgent.dream ↓ Event / Observation / Persistence
                         │ LearningEngine   ↓ Learning / Consolidation (dream)
                         └─ goal_stack.restore
```

架构收敛债务的准确表述：**New Runtime 已成为唯一生产认知主链，但部分 Legacy Cognitive Organs 被选择性借用，尚未完成 Re-host。**

## 三、10 能力位终版裁决矩阵

| # | 能力位 | 当前生产实现 | Legacy/重复实现 | 重叠 | Authority | 生产证据 | 独特语义资产 | 终版 Disposition |
|---|---|---|---|---|---|---|---|---|
| 1 | Attention | CognitiveAttentionController（Step2 每 tick decide/tick/emit_report；零 agent 包依赖，仅 logging+contracts.attention_abi） | agent/attention.py（零引用）；ocos/attention 包（stages⑦ 在用） | 低 | 新链 | Step2 源码 + tick result attention_update | 无（旧实现零语义产出） | agent/attention=ARCHIVE；CognitiveAttentionController=KEEP |
| 2 | Working Memory | runtime WorkingMemory + SQLiteWorkingMemory + MemoryConsolidator（Step3） | agent/working_memory.py（零引用） | 零 | 新链 | Step3 每 tick | 无 | ARCHIVE |
| 3 | Episode | memory/episode 家族（MemoryHub） | agent/episode_memory.py（零引用） | 零 | 新链 | episodes 表 963+ 条 | 无 | ARCHIVE |
| 4 | Reasoning | bridge 规划 LLM（12 注入点）+ TaskDecomposer | ReasoningEngine（注册零执行） | 高 | DecisionBridge | bridge 288 日志、goal_result 378 | 无 | ARCHIVE→DELETE（末阶段） |
| 5 | Planning | TaskDAG/TaskDecomposer/TaskReplanner | PlanningEngine（零执行） | 高 | TaskDAG | DAG 执行链 | 无 | ARCHIVE→DELETE（末阶段） |
| 6 | Decision | DecisionBridge（execute_dag_task+confidence gate） | DecisionEngine+DecisionLoop.decide | 高 | DecisionBridge | writer.execute 340 / researcher.execute 583 | 无 | ARCHIVE→DELETE（末阶段） |
| 7 | Reflection | 分布式：_record_failure_lesson（cause→lesson episode）+ _replan_failed_task（retry/replan）+ dream replay_important + FIX-9 失败回注 | ReflectionEngine+MasterAgent.reflect（零执行）；ResultUnderstandingLayer（声明+lazy init，零调用） | 中 | 新链 | 22 条 failure_lesson episodes | 失败→cause→lesson 归因语义（现役已承载） | ReflectionEngine=ARCHIVE；ResultUnderstandingLayer=ARCHIVE（R1）；现役分布式实现=KEEP |
| 8 | Learning | dream 链（daemon._run_dream_cycle→agent.sleep/dream→LearningEngine.learn→persist_latest_rules→wisdom_trigger）+ Step10 + memory.hub | LearningEngine（**被新宿主借用**） | 杂交 | 混合（待 RE-HOST） | 73 条 learn 日志、「Persisted 2 learning rules」持续至今 | learn 语义 + persist_latest_rules | **RE-HOST**（R2，唯一候选） |
| 9 | Lifecycle | RuntimeKernel + agent/lifecycle.py（dream 相位迁移依赖） | LifeCycleOrchestrator（tick 零调用；fatigue/proactive/shutdown 三职能在被用） | 中 | 新链 | dream 相位迁移日志 | fatigue/proactive/shutdown | 三职能 MERGE 入 daemon 后 Orchestrator=ARCHIVE（R3）；lifecycle.py=KEEP |
| 10 | Agent Cognition | AgentRuntime 10 步 | MasterAgent 五步循环+DecisionLoop+CognitiveBridge | 高 | 新链 | 8167 runtime 日志 vs master_agent 650 条全装配日志 | CognitiveBridge 显式路由（R4 判定：职能已被 prompt 路径覆盖） | MasterAgent=DEGRADE 为 Identity/Lifeform Facade/Dream Host；认知循环路径=ARCHIVE；CognitiveBridge=ARCHIVE（R4） |

> **P1 执行修正（2026-09-08）**：identity_anchor 从 ARCHIVE 批次剔除，重定级 🟢——P1 影响面精查发现 `agent_runtime` boot 身份恢复路径真实实例化 `IdentityAnchor`，且 `identity_store` 以其为存取类型（save/load/from_dict）。原静态审计漏判，已随 P1 甄别纠正。

## 四、R1-R4 终审裁决

- **R1 ResultUnderstandingLayer → ARCHIVE，不接线。** failure→cause→lesson→replan→dream 巩固已有生产证据；接线属增强非补缺。不为了"模块存在"而激活模块。
- **R2 LearningEngine → RE-HOST。** 不删除、不永久维持跨架构借用。目标形态：`Runtime → Learning/Consolidation Service → LearningEngine semantic implementation`——保留学习语义，迁移宿主。
- **R3 LifeCycleOrchestrator → MERGE（功能抽取后归档）。** 迁移 fatigue/proactive/shutdown 三职能入 daemon/Runtime；完整认知循环职责已属旧链。
- **R4 CognitiveBridge → ARCHIVE，暂不 RE-HOST。** 无证据表明显式 engine-routing 是不可替代能力；现役 TaskDecomposer/TaskReplanner/DecisionBridge LLM role/prompt routing 已承担语义路由。

## 五、MasterAgent 最终定位（分解裁决）

MasterAgent 不删除，按职能拆解：

| 职能组 | 内容 | 处置 |
|---|---|---|
| Identity / Lifeform Facade | identity、agent_id、get_status_report、world_context | KEEP（暂态宿主） |
| Dream Host | sleep/dream 巩固（LearningEngine 语义经此行使） | 暂态 KEEP → 随 R2 RE-HOST 后移交新宿主 |
| 认知循环 | observe→think→decide→act→reflect→learn（经 DecisionLoop） | ARCHIVE（随冻结令 #1） |

## 六、分期执行清单（Migration Plan）

| Phase | 内容 | 风险 | 验收门 |
|---|---|---|---|
| **P0 冻结生效**（立即，零代码） | 本文档生效；六条冻结令入项目记忆；审计结论入 ARCHITECTURE_FREEZE_PROTOCOL 体系 | 零 | 文档+记忆落盘确认 |
| **P1 低风险 ARCHIVE 批次** | 归档零引用/被替代模块：agent/{attention,working_memory,episode_memory,memory_consolidation,belief_consolidation,learning_trigger,identity_anchor,adaptive_params,drift_detector,context_compressor,retry_policy}.py + engines/writer_engine.py + ResultUnderstandingLayer 接线点标记。形式按 AFP 归档惯例（标记 deprecated + 移入归档命名空间，不物理删除） | 低 | 全量回归绿（2787+4424）；生产服务无新增 WARNING/ERROR |
| **P2 MERGE** | LifeCycleOrchestrator fatigue/proactive/shutdown 三职能迁入 daemon；原模块归档 | 中 | 行为级：疲劳触发 dream、主动输出、优雅关闭三项 E2E 不回归 |
| **P3 RE-HOST** | daemon 侧 Learning/Consolidation Service 建立；LearningEngine 语义迁入；dream 宿主从 MasterAgent 移交 | 高（触碰 dream 生产闭环） | dream 全链 E2E：learn→persist→wisdom 落库证据不中断；learning rules 持久化行为等价 |
| **P4 Single-Path Production Verification** | 单主链验证：断言生产无任何 MasterAgent 认知五步调用路径；tests/test_behavioral_acceptance_20260908.py 全绿；与既有 T1-T10 行为验收合并 | 中 | 验收通过后 DELETE 批次（ReasoningEngine 等四引擎+CognitiveBridge+DecisionLoop）方可启动 |

## 七、违冻条款（禁止事项）

- 禁止在 P3 完成前设置 `OCOS_ENABLE_COGNITIVE_LOOP=1`（冻结令 #3）。
- 禁止对任何 ARCHIVE 对象做物理 `rm`（冻结令 #4；DELETE 须 P4 验收后单独立项）。
- 禁止为"让五步循环跑起来"而激活 B 链任何组件。
- 禁止在 RE-HOST 前改动 dream 调用链（daemon._run_dream_cycle 现为生产闭环，触碰需走 P3 验收门）。
