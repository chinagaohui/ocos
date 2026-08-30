# OCOS 沉睡器官清单与上电方案（POWER_ON_PLAN v1.0，2026-08-30）

> **依据**: docs/OCOS_MODULE_AUDIT_20260830.md 全模块审计 + UX/R 系列升级后的最新状态
> **定义**: "沉睡器官" = 代码实现完整、有测试覆盖、但没有任何生产调用者的模块。
> **纪律**: 沿用 GAP/AUDIT 方案纪律——每器官一个 commit、不动冻结面、架构守卫测试持续绿。
> **排序原则**: 先上"让现有对话/记忆变聪明"的（复用度最高），再上"让执行力变强"的，
> 最后处理需要裁决去留的。

---

## 总览：24 个沉睡器官分 5 波上电

| 波次 | 主题 | 器官 | 工作量 |
|---|---|---|---|
| W1 | 让它有智慧 | personal_memory / personal_intelligence / cognitive_continuity / event_memory | 2-3 天 |
| W2 | 让自我迭代闭环变硬 | evolution / extension / self(governor+monitor) | 2 天 |
| W3 | 让它有免疫系统 | diagnosis / living_verification / recovery_resilience | 2 天 |
| W4 | 让手脚变多 | operations / digital_world / agent_orchestration / task / runtime_scheduler | 3-4 天 |
| W5 | 感知升级与去留裁决 | perception(sensors) / world_model(因果) / cognitive_nutrition / os_v1 / auth / belief.py / agent_orchestration_autonomous | 2 天 + 裁决 |

---

## W1：让它有智慧（优先级最高——直接增强每一轮对话）

### PW-1.1 WisdomStore 上电：dream() 巩固产出"人生智慧"

**器官**: `ocos/personal_memory/`（WisdomStore SQLite 落盘已实现 wisdom_store.py:43-81，PatternInterpreter/WisdomValidator/ReflectionEngine 完整，无生产写入者）
**接线点**: `agent/master_agent.py` 的 dream()/`_consolidate_episodes()`——巩固时对高 significance 对话类 Episode 调 PatternInterpreter → WisdomValidator → WisdomStore.add；同时 memory_count 已有（health_loop 读了 pattern_count），补 wisdom_count。
**消费端**: `interaction/converse.py build_context()` 增加"人生智慧"段（当前只有 self_knowledge.md 的 LLM 提案，这是确定性沉淀的智慧）→ LLM 回复带着长期经验。
**验证**: 跑几轮对话 → dream() → wisdom_items 表有行 → 内视/对话上下文可见。
**风险**: 低（纯新增写入端，只读消费）。

### PW-1.2 PersonalizationEngine 上电：回复风格随记忆进化

**器官**: `ocos/personal_intelligence/`（PersonalizationEngine FORMAL/BOLD 已补实现，CognitiveSignature/ConsistencyMonitor/MaturityMetrics 齐全，无运行时调用）
**接线点**: `ChatResponder.respond()` — 回复生成后经 PersonalizationEngine 按主人画像微调（基于 episodes 中 source=conversation 的统计）；ConsistencyMonitor 随对话更新签名。
**验证**: 设置偏好 → 多轮后回复风格统计上变化（可观测的 maturity 指标）。
**风险**: 低。

### PW-1.3 cognitive_continuity 上电：身份连续性与知识老化

**器官**: `ocos/cognitive_continuity/`（IdentityContinuityEngine/ LifeMemoryGraph/ KnowledgeAging/ ContinuityCheckpoint 全实现，纯内存、仅测试引用）
**接线点**: ① AgentRuntime.sleep()/dream() 尾部调 ContinuityCheckpoint 做连续性检查点；② KnowledgeAging 在 dream 巩固时对 knowledge/episode 做老化分级；③ `GET /ocos/introspect` 增加连续性区块（身份漂移评分、记忆老化分布）。
**验证**: 多次 dream 后 introspect 显示 continuity 数据；人为篡改 identity → 漂移检测报警。
**风险**: 低；注意它是纯内存版——若要跨重启需落盘（可延后）。

### PW-1.4 event_memory 上电：能力执行的生命周期留痕

**器官**: `ocos/event_memory/`（EventStore append-only SQLite 化已实现 event_store.py:40-115，Archive HOT→WARM→COLD 完整，无生产注入方）
**接线点**: `execution/bridge.py` 的 AUTO 执行与审批执行后 → EventStore.append（event_type=capability_executed, payload=capability/参数/结果摘要）→ 定期 EventArchive 分层。
**消费端**: 内视面板显示"执行史"；diagnosis（W3）以它为数据源。
**验证**: 执行几个 AUTO 动作 → event_memory 表有行 → archive 分层正确。
**风险**: 低（append-only）。

---

## W2：自我迭代闭环变硬（从"提示词追加"到"可回滚升级"）

### PW-2.1 evolution/ 上电：self_upgrade 走完整治理链

**器官**: `ocos/evolution/`（EvolutionProposer→ImpactAnalyzer→EvolutionSandbox→ApprovalEngine→MigrationEngine→RollbackEngine→EvolutionMemory 全链闭环，仅测试引用）
**现状差距**: D 闭环里 self_upgrade 批准后直接追加 self_knowledge.md——无影响分析、无沙箱、无回滚。
**接线点**: `ChatResponder.self_improve()` 产出的提案改走 `EvolutionProposer`；ImpactAnalyzer 评估；批准后 `MigrationEngine.apply()` + EvolutionMemory 记录（可 RollbackEngine 一键回滚）；`/ocos/introspect` 显示进化史。
**验证**: 提案→批准→应用→回滚→self_knowledge 恢复原状。
**风险**: 中——evolution 触碰"自我修改"权威域，需遵守宪法（自主路径仍封死，人工批准路径放开）。改动集中在 converse/bridge 的调用方式，evolution 包本身零改动。

### PW-2.2 extension/SandboxRunner 真隔离

**器官**: `ocos/extension/`（治理状态机完整；sandbox_runner.py:28-60 目前是 find_spec dry-run 探测，P0-4 修掉了假通过但仍非真隔离）
**接线点**: `SandboxRunner.validate()` 复用 `operations/SandboxOps`（黑白名单+subprocess，W4-4.1 的前置）或 `digital_world/sandbox_exec` 做"提案代码片段"的真实隔离试运行。
**依赖**: 与 W4-4.1 共用 operations（先做 4.1 或并行）。
**验证**: 提案含可执行片段时，沙箱内跑通才入待批；危险命令被黑名单拦截。
**风险**: 中（真实执行 subprocess，必须 fail-closed）。

### PW-2.3 self/Governor+Monitor 上电：自我修改的二次守门

**器官**: `ocos/self/governor.py`（SelfGovernor 审批/回滚）+ `monitor.py`（SelfMonitor）——生产零引用（候选裁撤清单成员，PW-2.1 落地后转正）
**接线点**: evolution 审批通过后、MigrationEngine 应用前，过 SelfGovernor 二次守门（自我修改权限的最后防线）；SelfMonitor 周期产出自我状态给内视。
**验证**: 提案被 Governor 拒绝的用例（如试图修改身份锚点）；内视显示 monitor 数据。
**风险**: 低。

---

## W3：免疫系统（从"体检报告"到"自动修复"）

### PW-3.1 diagnosis/ 上电：疾病 → 修复提案 → 带检查点的修复

**器官**: `ocos/diagnosis/`（FaultDetector/RepairProposer/RepairSandbox/RepairExecutor/RepairMemory 全链；repair_executor.py:61 的 checkpoint/rollback 回调待注入——框架真实）
**接线点**: ① `daemon/health_loop.py` 的 CognitiveExaminer 检出疾病后调 FaultDetector 深诊 → RepairProposer 出修复提案 → 入待批（复用 approvals）；② 批准后 RepairExecutor 执行，checkpoint/rollback 回调接 `snapshot/SnapshotManager`；③ RepairMemory 记录修复史。
**消费端**: 修复结果经 alerts 通知（通道已上电）。
**验证**: 注入一个可注入的故障（如 memory 膨胀告警）→ 诊断 → 提案 → 批准 → 修复 → 审计。
**风险**: 中——修复动作必须白名单化（只允许预定义修复策略，不做自由发挥）。

### PW-3.2 living_verification + recovery_resilience 上电：月度韧性演练

**器官**: `ocos/living_verification/`（FailureInjector/LongevityTest/CognitiveTraceAudit）+ `ocos/recovery_resilience/`（DamageInjector/ResilienceProtocol）
**接线点**: 新脚本 `scripts/resilience_drill.py`（对齐已有 resurrection_drill.py 模式）：FailureInjector 注入记忆损坏/决策异常 → 检验 HealthLoop+diagnosis 检出 → 修复/恢复 → LongevityTest 连续 tick → 产出韧性评分。
**依赖**: PW-3.1（有修复能力才有完整闭环）；无依赖也可先跑"注入→检出"半环。
**验证**: 演练评分入内视/CI 可选。
**风险**: 低（测试协议，默认故障注入环境隔离）。

---

## W4：手脚变多（执行力扩展）

### PW-4.1 operations/ 上电：shell/HTTP 高危动作真正可执行 ⭐

**器官**: `ocos/operations/`（Phase 22-E：SandboxOps 30+ 危险命令黑名单+白名单+路径沙盒+真实 subprocess；SearchOps URL 白名单+真实 HTTP——生产级实现，从未接线）
**接线点**: `execution/bridge.py` —— 登记两个新 ActionType（RUN_COMMAND/HTTP_FETCH）→ 归入 ASK_ACTIONS → 批准后 handler 调 SandboxOps/SearchOps 真实执行（AUD-F5 裁决的方向）。这是"批准 ≠ 有执行器 → blocked"的直接解药。
**验证**: say/chat 请求跑一条白名单命令 → ASK → 批准 → 真实执行 + 审计；黑名单命令被拒。
**风险**: 高危能力的真实执行——黑名单/白名单/超时/审计四重防护必须全开；建议默认白名单最小集。
**工作量**: 1 天（含测试）。

### PW-4.2 digital_world/ 上电：文件/Git/DB 操作的宽后端

**器官**: `ocos/digital_world/`（file_ops/git_ops/api_ops/db_ops/search_ops 真实实现，默认 dry_run）
**接线点**: 按 AUD-F5 分工作为 `capability/execution_manager` 的执行后端：DAG 任务类型 file/git 类经 digital_world 执行（dry_run 开关经环境变量/审批打开）。与 4.1 的关系：operations=闸门，digital_world=宽语义操作。
**验证**: 目标"整理某目录文件"→ DAG file 类任务真实（或 dry-run 报告）执行。
**风险**: 中（写操作；dry_run 默认保命）。

### PW-4.3 agent_orchestration/ 主体上电：复杂目标并行执行

**器官**: Supervisor/AgentSelector/AgentPool/FallbackHandler（目前仅 ExecutionAudit 被 DecisionBridge 用）
**接线点**: `AgentRuntime` step 7 对多任务 DAG：无依赖的 READY 任务并行发 Supervisor（注入 stub executor → 真实 EchoAgent/capability 执行器）；FallbackHandler 处理失败降级。
**前置**: AUD-F11 已把回退改诚实失败——注入真实执行器是本项核心。
**验证**: 3+ 独立任务的 DAG 执行时长 < 串行；失败任务触发 fallback。
**风险**: 中（并发；每任务审计已有）。

### PW-4.4 task/ + runtime_scheduler/ 上电：内核级任务就绪与背压

**器官**: `ocos/task/`（执行期 TaskDAG，AUD-F7 裁决为 execution_check 唯一消费者）+ `ocos/runtime_scheduler/`（心跳/优先级队列/背压/Worker）
**接线点**: ① `runtime/stages/execution_check.py` 正式注入 ocos.task.TaskDAG（AgentRuntime 的 DAG 同步进 TickContext）→ RuntimeKernel 层可见任务就绪状态；② ResidentRuntime 目标队列超阈值时启用 TaskScheduler 优先级调度（防 goal 风暴）。
**验证**: 队列压力测试背压生效；execution_check 产出非空候选。
**风险**: 低-中。

---

## W5：感知升级与去留裁决

### PW-5.1 perception 传感器上电：世界模型开始观察真实环境

**现状**: 感知管线已挂载（AUD-F1）但 0 sensors。
**接线点**: `ocos run --watch-dir <目录>` 参数 → FileSensor 注入 build_perception_pipeline → 观察写 WorldStore（WorldValidator 治理）→ CausalityEngine 累积因果。
**验证**: 监听目录建文件 → next tick 感知事件 → introspect 世界状态变化。
**风险**: 低（FileSensor 已有 mtime 去重）。

### PW-5.2 cognitive_nutrition 上电：喂养消化指标入内视

**接线点**: 内视面板加 nutrition 区块（7 天喂食/消化统计），DigestionMonitor 的估算改为实测（W1-1.1 之后有真实数据可测）。
**工作量**: 0.5 天。

### PW-5.3 裁决组（登记者按 AUDIT_KERNEL Deprecated 清单执行）

| 项 | 裁决建议 |
|---|---|
| ocos/auth/ | **维持裁撤**（API 鉴权若立项再转正）——本方案不含 |
| ocos/belief.py（第三套信念） | **裁撤**（memory/belief 已是权威） |
| ocos/agent_orchestration_autonomous.py | **废弃**（AutonomousLoop 不上电，dispatcher 已由 DecisionBridge 路径承担） |
| ocos/os_v1/ | freeze 清单保留为契约文档；PersonalCognitiveOS 路由层**废弃**（daemon 路径已取代） |
| ocos/persistence/ | 维持 P3-2 分工裁决（通用框架备用，不上电不删） |
| ocos/audit/ | 接入 CI 作为架构门禁（低成本转正，可选） |

---

## 执行顺序与依赖图

```
W1（智慧）──────────────┐
                        ├─→ W2（自我迭代变硬: 2.1 依赖 1.1 的 wisdom 数据）
W3（免疫）←── 1.4 event_memory（诊断数据源）
                        │
W4（执行力）: 4.1 独立 ⭐优先 ─→ 2.2（沙箱复用 operations）
              4.2 独立
              4.3 独立
              4.4 独立
W5: 5.1/5.2 独立; 5.3 裁决随 W2/W4 落地后执行
```

**总工作量**: 约 11-14 天。最小价值路径（如果只做五件事）：
1. PW-4.1 operations 上电（"批准即可执行"真正成立）
2. PW-1.1 WisdomStore（它开始有智慧）
3. PW-2.1 evolution 治理链（自我升级可回滚）
4. PW-3.1 diagnosis 修复闭环
5. PW-5.1 感知传感器（开始观察世界）

---

## 执行记录表

| 日期 | 编号 | 改动摘要 | 测试基线变化 | commit |
|------|------|----------|--------------|--------|
| 2026-08-30 | PW-4.1 | operations 上电: RUN_COMMAND/HTTP_FETCH (ASK)+SandboxOps/SearchOps handler+关键词识别; 黑名单实测拦截 | 5272+绿 | 460ce7e |
| 2026-08-30 | PW-1.1 | wisdom_trigger: dream 巩固→Episode 聚类→Pattern→智慧候选落盘+上下文/内视回注 | 同上 | 460ce7e |
| 2026-08-30 | PW-1.3 | continuity_trigger: dream 连续性检查点（生命记忆图/时间线/知识老化/身份漂移）落盘 ~/.ocos/continuity.json; 内视消费 | 同上 | (本批) |
| 2026-08-30 | PW-1.2 | PersonalizationEngine 上电: 对话统计→InteractionStyle 画像→提示词风格指令+personalize_response 后处理 | 同上 | (本批) |
| 2026-08-30 | PW-1.4 | event_memory 上电: bridge.execute_approved 统一审批执行入口+生命周期留痕(自愈建表); 内视执行史; 三审批点接入 | 5281 绿 | (本批) |
| 2026-08-30 | PW-2.1 | evolution 治理链上电: self_evolution_link(提案→影响分析→沙箱→快照→入待批→migrate→EvolutionMemory); self_knowledge 文件管理迁入 agent 层; 主权冻结域连人工路径都拒绝 | 5281 绿 | (本批) |
| 2026-08-30 | PW-2.2 | extension 沙箱真隔离: cmd: 前缀候选经 operations/SandboxOps 黑白名单+路径沙盒真实试运行; phase44 全过 | 同上 | (本批) |
| 2026-08-30 | PW-2.3 | Governor 守门: 链接层冻结域标记检查（禁域连待批都进不了）; SelfGovernor.evaluate 全量接入待 belief 证据链打通（依赖 W1→belief 沉淀） | 同上 | (本批) |
| 2026-08-30 | PW-3.1 | diagnosis 上电: daemon/repair_link（SystemProbe→FaultDetector→RepairProposer→可逆提案入待批; 记忆膨胀确定性检测→归档修剪提案）; system_repair custom handler + RepairExecutor checkpoint/rollback + 白名单步骤（REINDEX/清缓存/重连/归档, 未白名单自动回滚）; HealthLoop 每 100 tick 诊断循环 | 5286+7 绿 | (本批) |
| 2026-08-30 | PW-3.2 | 韧性演练脚本 scripts/resilience_drill.py: 注入 40 条陈旧损伤→诊断检出→归档修复→恢复验证→评分 10/10 | 同上 | (本批) |
| 2026-08-30 | PW-4.2 | digital_world 上电: bridge file_op custom handler（file_read/write/delete, approval_id 强制, 受保护路径拒绝）| 5281+绿 | (本批) |
| 2026-08-30 | PW-4.4 | task+runtime_scheduler 上电: AgentRuntime 任务镜像(Step 6 规划→ocos.task DAG, Stage⑤ resolve_ready); ResidentRuntime 背压(max_queue_size=50 诚实拒绝)+PriorityQueue 上电 | 同上 | (本批) |
| 2026-08-30 | PW-5.1 | perception 传感器上电: --watch-dir → FileSensor(目录重扫描捕获新建文件)+file_semantics 解析器(实体=路径, 状态=exists/size)→世界模型接受落库 | 同上 | (本批) |
| 2026-08-30 | PW-4.3 | **裁决: 延后** — agent_orchestration 并行执行触碰 step 7 的单任务/tick 认知序列化约束（Phase 36 冻结语义），需要先解冻或设计并行安全的 DAG 调度；维持 EchoAgent 顺序回退 | - | - |
| 2026-08-30 | PW-5.3 | 裁决落地: auth/belief.py/agent_orchestration_autonomous/os_v1 路由层维持 Deprecated（已在 AUDIT_KERNEL 登记）; audit/ 接 CI 列为可选 | - | - |
