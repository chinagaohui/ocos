# OCOS 全模块功能与接线审计报告（2026-08-30）

> **方法**: ① AST 生产导入图 + 入口可达性扫描（CLI/API/REPL/daemon 四入口 BFS）；
> ② 三个并行代理逐模块代码核实（对照扫描分类，file:line 证据）；
> ③ 每模块测试覆盖统计（import 该包的测试文件中的 test 函数数）；
> ④ 合并全量测试基线 5245 passed / 24 skipped / 0 failed（commit 0de4c62 后）。
> **定位**: GAP 修复计划 + R4-A 之后的第一次全仓接线审计。

---

## 一、总体结论

**主链路（点亮部分）是健康的**：`ocos run` → ResidentRuntime → RuntimeKernel 心跳 → AgentRuntime 10 步 tick → DecisionBridge（AUTO/ASK/DENY 风险分级真实执行）→ capability_reality 沙盒执行 + ExecutionAudit 审计，外加周期健康体检 → alerts 落盘。这条链上的 33 个包全部入口可达、有真实生产调用者、有测试覆盖。

**主要缺口换了两类形态**：
1. **"造好未上电"的半接线**——P1/P2 若干接线只做到 factory 层，默认入口 `run.py` 没有调用对应 builder（知识库镜像、感知管线）；
2. **约 20 个"完整实现、仅测试引用"的沉睡器官**——与上次审计基本一致，另纠正了脚本对 cognitive_loop/decision/task 的三处高估。

---

## 二、主链路（入口可达，33 包）

| 模块 | 中文功能 | 生产调用证据 | 测试 |
|---|---|---|---|
| ocos.agent | Agent 主体运行时：`AgentRuntime` 10 步持久化 tick + `MasterAgent` 门面 + 身份/目标 SQLite 存储 | daemon/factory.py:17 装配；daemon/__init__.py:124 驱动 tick | 32 文件/571 函数 |
| ocos.runtime | 运行时内核：`RuntimeKernel` 心跳 + `TickPipeline` 8 阶段 + 权限网关（fail-closed）+ 恢复 | daemon 经 driver 注入驱动；P2-2 后 4 个 stage 已接线 | 29/744 |
| ocos.execution | **R4-A 执行铰链** `DecisionBridge`：决策→AUTO/ASK/DENY 分级→沙盒真实执行→审计 | factory.py:99 装配；agent_runtime step 7/8 每 tick 调用 | 1/27 |
| ocos.capability | 能力神经系统：注册/选择/路由 + `HomeostasisManager` 稳态 + `PermissionGateway` | health_loop 装配 Homeostasis；DecisionBridge 内 fail-closed 权限 | 26/568 |
| ocos.capability_reality | 真实能力层：Filesystem/Shell 适配器 + 自动发现（沙盒 safe_roots） | DecisionBridge `_exec_fs` 真实执行 | 1/36 |
| ocos.autonomous_runtime | 决策解释与分发：`ActionDispatcher`（决策文本→DispatchedAction）⚠️ 仅 dispatcher 可达，AutonomousLoop 未上电 | execution/bridge.py:30 | 2/77 |
| ocos.daemon | 常驻运行时 `ResidentRuntime` + `HealthLoop` 周期体检 + factory 生产装配层（零 Mock） | cli/commands/run.py:49-67 | 5/51 |
| ocos.interaction | 交互门面：CLI 子命令 / REPL / FastAPI / `CognitiveInterface` + PermissionGuard 入口宪法 | pyproject 三个 console_scripts | 7/148 |
| ocos.opentale_bridge | OpenTale 写作器官桥：`MasterAgent` 写作决策 + `OrganClient` 真实 HTTP + 反馈回流/自调节 | cli decide/regulate/feedback + api quality | 5/150 |
| ocos.health_examination | 认知健康体检 `CognitiveExaminer`（记忆膨胀/决策漂移等疾病检测） | daemon/health_loop.py:20 每 100 tick | 2/50 |
| ocos.alerts | 告警中枢：`AlertManager` + Log/File 双通道（JSON 落盘 ~/.ocos/alerts/） | health_loop.py:132-148 真实发送 | 2/18 |
| ocos.memory | 记忆中枢 `MemoryHub`：Episode/Belief/Semantic/Pattern 四库共享 SQLite，写入者齐全 | belief_system/_persist、dream 巩固、agent_runtime | 17/264 |
| ocos.storage | SQLite 基础设施：连接池(WAL)/schema/迁移/事件存储/死信队列/工作记忆 | run.py ensure_schema + 各 Store | 9/95 |
| ocos.snapshot | agent 专用 SQLite 快照 + `CrashRecovery`（默认路径 ~/.ocos/ocos.db） | master_agent 复活链 | 2/16 |
| ocos.knowledge | 知识平面：ABI/本体/`KnowledgeRegistry`（P2-1 起可镜像落 SemanticStore） | engines consolidation/promotion 消费 | 9/183 |
| ocos.engines | 18 个认知引擎（`__manifest__` 声明 + EngineDiscoverer/Loader），循环导入已治愈 | EngineBridge 注册 planner/reasoner/writer | 18/328 |
| ocos.planning | 任务规划：`TaskDecomposer`（agent_runtime step 6）+ PlanValidator（P3-6 已合并）+ 模拟器 | agent_runtime.py:813 + interaction plan | 17/143 |
| ocos.goal | 目标系统：`GoalOriginEnforcer` 来源守门 + MaintenanceEngine + 宪法工厂 | agent_runtime.py:616 + goal_maintenance stage | 22/434 |
| ocos.proactive | 主动行为引擎：频率闸门→SELF 目标→疲劳闸门→模板轮换→权限双检 fail-closed | master_agent.py:1022 空闲期触发 | 1/12 |
| ocos.decision | 决策组件链：Context→Option→Risk→Value→Validator/Tracer ⚠️ 接进了 cognitive_loop，但该循环本身未上电（见三-1） | decision_pipeline.py:73-114（挂空） | 1/20 |
| ocos.cognitive_loop | Phase 46 认知循环编排（LoopOrchestrator 7 阶段 + DecisionPipeline）⚠️ 生产 tick 不经过它（见三-1） | 仅 autonomous_loop（本身未上电） | 2/36 |
| ocos.attention | B 层注意力评分引擎（评分+惯性+切换阈值）；三套注意力已按 P3-8 分层裁决 | runtime/stages/attention.py 每 tick | 2/54 |
| ocos.perception | 感知层：传感器+校验+`PerceptionPipeline`（→world_model）⚠️ factory 可达、入口未接线（见三-2） | 仅测试直测 | 2/45 |
| ocos.world_model | 世界模型：WorldStore/Validator/CausalityEngine 因果与状态追踪 | perception/pipeline.py 桥接写入 | 2/36 |
| ocos.events | 宪法事件总线（kernel.abi.Event topic pub/sub）+ 内存 EventStore（裁决保留） | runtime/agent/engines 约 20 处 | 25/556 |
| ocos.event | 感知神经系统：外部事件归一化→注意力候选分 | agent_runtime.py:150 | （并入上行） |
| ocos.kernel | 不可变内核：宪法规则/冻结 ABI/事件 schema/TimeManager | 全仓最广泛依赖 | 37/1154 |
| ocos.models | 引擎数据模型（TransformProcess 等） | engines/agent 消费 | 34/693 |
| ocos.contracts | 冻结 ABI 契约：AttentionReport/Decision、CognitiveFeedback/DriftAlert | agent/capability/attention | 4/86 |
| ocos.task | 线程安全 TaskDAG ⚠️ 实际零生产 import（execution_check 是 duck-type 可选注入且默认不传）；与 planning/models 的同名 TaskDAG 撞名 | 仅测试 | 0 |
| ocos.self | 自我模型：`IdentityBoundary`/`StatementValidator` 生产在用；SelfGovernor/SelfMonitor 零引用 | factory.py:27、belief_system.py:17 | 11/214 |
| ocos.constitution | 宪法层：BehavioralConstitution（请求入口强制）+ StatementValidator | interaction/base.py:25 等 | 6/104 |
| ocos.platform | 引擎清单发现/加载 + 插件沙箱（P0-4 后诚实失败）+ 治理/追踪引擎 | engines manifest、capability/discovery | 15/587 |
| ocos.logging | 结构化 JSON 日志：get_logger/formatter/rotator/search | 全仓数十处 | 4/30 |

## 三、脚本扫描的三处误判（代理已纠正）

1. **cognitive_loop 与 decision 并非入口可达**——GAP-P1-1 的接线（DecisionPipeline→decision 组件链）代码真实存在，但它挂在 `AutonomousLoop` 上，而生产 tick 走 RuntimeKernel+AgentRuntime，不经过 LoopOrchestrator。**这条决策链是"接好电线的备用引擎"，主机没点火。**
2. **agent_orchestration 仅 audit 进生产**——Supervisor/Selector/Pool 无生产实例化，supervisor.py:32-38 模拟回退仍在（沉睡不害人）。
3. **task/ 零生产 import**——execution_check.py 自称"ocos/task 首个生产消费者"，实为 duck-type 可选注入且 pipeline 默认不传。

## 四、沉睡器官（实现完整、仅测试引用，20 个）

| 模块 | 中文功能 | 测试 | 备注 |
|---|---|---|---|
| ocos.persistence | 通用多域 JSON 快照框架（vs snapshot/ SQLite 版，裁决并存） | 2 文件/87 | P3-2 裁决 docstring 已落地 |
| ocos.event_memory | 事件记忆 + HOT/WARM/COLD 归档（SQLite 化已实现，无生产注入方） | 2/57 | P2-3 能力落地、未接线 |
| ocos.runtime_scheduler | 心跳调度器（Clock/优先级队列/背压/Worker） | 1/43 | ⚠️ 与 runtime/scheduler.py 是 P3 唯一没写裁决 docstring 的一组 |
| ocos.personal_memory | 智慧层 WisdomStore（SQLite 落盘已实现，零生产写入者） | 2/38 | P2-4 能力落地、未接线 |
| ocos.personal_intelligence | 个人智能：个性化(FORMAL/BOLD 已补实现)/一致性/成熟度 | 2/34 | 仅审计元数据引用 |
| ocos.diagnosis | 免疫系统：故障检测→修复提案→沙盒→执行→记忆（诚实失败设计） | 1/38 | 待接 health 链 |
| ocos.living_verification | 活体验证：故障注入/长寿测试/轨迹审计 | 2/84 | 系统级证明组件 |
| ocos.living_test | 7 天活体测试协议 ⚠️ day7 协议本体在钩子缺失时仍假通过（drill 脚本兜底） | 1/56 | P2-5 已真实化 scripts/resurrection_drill.py |
| ocos.recovery_resilience | 韧性测试协议（DamageInjector + Mock 状态，Mock 属设计） | 1/86 | |
| ocos.evolution | 认知进化治理闭环：提案→影响分析→沙箱→审批→迁移→回滚 | 1/25 | 审批链与 self/governor 并存未打通 |
| ocos.extension | 认知扩展治理（P0-4 后 sandbox_runner 诚实探测，仍非真隔离） | 1/21 | P2-6 真隔离未做 |
| ocos.audit | Phase 51 集成审计：TaskSimulator/边界检查/差距分析 | 1/53 | 验证工具 |
| ocos.os_v1 | PersonalCognitiveOS v1.0 验证 + 认知主权冻结清单 | 1/31 | 契约冻结性质 |
| ocos.cognitive_continuity | 认知连续性：身份连续/生命记忆图/知识老化 | 1/27 | 纯内存，os_v1/freeze 仅声明性列举 |
| ocos.cognitive_nutrition | 认知营养：7 天数据喂养消化验证协议 | 1/68 | 消化增量为估算值 |
| ocos.agent_orchestration_autonomous | AutonomousLoop×AgentOrchestration 连接门面 | 2/23 | 依赖链未上电 |
| ocos.recovery | 进程级 CrashRecovery（P3-3 裁决与 agent 轻量恢复分工） | — | 被 resurrection_drill 真实使用 |
| ocos.auth | 传统 User/Role/身份存储 ⚠️ 与 self.IdentityBoundary 语义重叠，候选裁撤 | 4 文件/31 | FastAPI 无鉴权仍未接 |
| ocos.operations | **Phase 22-E 安全操作层**：SandboxOps（30+ 危险命令黑名单+白名单+真实 subprocess）、SearchOps（URL 白名单+真实 HTTP）——生产级实现但从未接线 | 2/37 | 与 digital_world 平行，P3 未裁决 |
| ocos.digital_world | 数字环境操作：file/git/api/db/search/sandbox（真实执行，默认 dry_run） | 13/58 | 与 operations/ 平行的另一套操作面 |

顶层转发壳（无逻辑，正常）：`ocos/orchestrator.py`、`ocos/homeostasis.py`、`ocos/cognitive_interface.py`（均指向真实实现）；`ocos/belief.py`（BeliefManager 第三套信念系统，无生产引用，持久化 TBD）。

## 五、新发现问题（本次审计产出）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| F1 | **P2-1/P1-3 半接线**：`run.py` 未调 `build_knowledge_registry` 与 `build_perception_pipeline`——语义镜像与世界模型感知链在默认入口不生效 | run.py:49-58 | run.py 装配两行 + 传参 |
| F2 | **runtime_scheduler ↔ runtime/scheduler 无裁决**：P3 四组裁决唯一缺失的一对 | 两包互无提及 | 补分工 docstring 或合并 |
| F3 | **stages/__init__.py docstring 过期**：仍写 4 个 stage 是"占位"，实际 P2-2 已全部接线 | stages/__init__.py:4-9 | 更新文档 |
| F4 | **living_test day7 协议本体假通过**：钩子为 None 时 restored/memory_intact/goals_intact 仍置 True | day7_resurrection.py:80-95 | 改 fail-closed（drill 已兜底，风险低） |
| F5 | **operations/ 与 digital_world/ 平行未裁决**：两套真实执行的操作面（沙盒/黑名单）并存 | 见二/四表 | P3-9 补裁决 |
| F6 | **storage/event_store、dead_letter_queue 与 events/ 同名第三套实现**，P3 未覆盖 | 三-表备注 | 并入裁决清单 |
| F7 | **task/ 与 planning/models 的 TaskDAG 同名撞车**，且 task/ 零生产消费 | 三-3 | 撞名去重或明确废弃 |
| F8 | **CLI goal/plan 仍未落库**（GAP 计划 P1-4 顺手项未执行），API goal 路由只读 | cli/commands/goal.py:64,74 | 按原 GAP-P1-4 补 |
| F9 | **master_agent 引擎未注册时 think/decide/reflect/learn 返回 status:"stub"**：build_master_agent 未注入任何决策引擎 | master_agent.py:312,413,484,624,667 | factory 注册引擎或在启动输出明示降级状态 |
| F10 | auth 与 self.IdentityBoundary 语义重叠、belief.py 第三套信念系统、SelfGovernor/SelfMonitor 零引用——三个"候选裁撤"项 | 见四表 | 下个版本裁决 |

## 六、测试覆盖说明

- 合并基线 5245 passed / 24 skipped / 0 failed（testpaths 已含 ocos/tests）。
- 覆盖最强的包：kernel（1154 test 函数）、runtime（744）、models（693）、agent（571）、capability（568）。
- 覆盖最弱的主链路包：proactive（12）、execution（27）、alerts（18）、decision（20）——新接线模块测试偏薄，建议下阶段补 E2E。
- 测试覆盖 ≠ 生产接线：如 digital_world 有 58 个测试函数但零生产调用者；反之 runtime/stages 接线后测试在 test_single_main_loop 内。
