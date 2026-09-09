# OCOS 全模块功能与接线审计报告（2026-08-30）

> 📜 **HISTORICAL（2026-08-30 时点基线）**：测试基线当时为 5245 passed，当前为 7034 passed；
> 接线/激活状态以白皮书 v1.3.1 与 CONVERGENCE_DECISION_v1.0 为准。

> **方法**: ① AST 生产导入图 + 入口可达性扫描（CLI/API/REPL/daemon 四入口 BFS）；
> ② 三个并行代理逐模块代码核实（对照扫描分类，file:line 证据）；
> ③ 每模块测试覆盖统计（import 该包的测试文件中的 test 函数数）；
> ④ 合并全量测试基线 5245 passed / 24 skipped / 0 failed（commit 0de4c62 后）。
> **定位**: GAP 修复计划 + R4-A 之后的第一次全仓接线审计。
> **⚠️ 时效声明（2026-08-31 更新）**: 本报告的部分结论已被后续 48 个 commit 推进——
> 沉睡器官 14/24 已上电（见 POWER_ON_PLAN 执行记录）、F1-F10 全部闭环、
> 测试基线 5245 → 5287。**当前状态以文末「九、2026-08-31 全量状态更新」为准**，
> 第二/四节的表格保留为 08-30 快照供历史对照。

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

---

## 七、修复执行记录（AUDIT_FIX_PLAN v1.0，2026-08-30 执行）

| 编号 | 内容 | commit | 验证 |
|---|---|---|---|
| AUD-F1 | run.py 半接线补齐: SemanticStore 镜像 on + 感知管线挂载（0 sensors 零噪音）; factory.build_knowledge_abi; ResidentRuntime.memory_hub/attach_perception_pipeline | (见 git log) | 冒烟 2 ticks + 定向测试 |
| AUD-F3 | stages/__init__ docstring 更新为 P2-2 后事实 | 6d9542c | 单测 |
| AUD-F4 | living_test day1-7 协议 fail-closed（钩子缺失不再假通过）; drill 仍 10/10 | 7f85048 | test_phase58_1 + drill |
| AUD-F2 | 双调度器分工裁决 docstring | (见 git log) | test_phase51_2 |
| AUD-F5/F6 | operations vs digital_world、storage vs events 四件套裁决 | (见 git log) | storage/recovery/event 测试 |
| AUD-F7/F10a | TaskDAG 规划期 vs 执行期裁决; 候选裁撤清单（auth/belief.py/SelfGovernor） | (见 git log) | 全量 |
| AUD-F11 | supervisor 回退执行器改诚实失败（无 AgentExecutor 注入 → NOT executed） | (见 git log) | orch/validation 测试注入 stub |
| AUD-F8 | CLI goal/plan 落库（goals + plan_dag 表, schema v4）; TBD 文案清零; 自愈 DDL 补 agent_id/metadata 列; 测试 DB 隔离 | (见 git log) | E2E: create/plan/list 全通 |
| AUD-F12 | R4-B 最小可用: pending_actions 表 + PendingStore + ocos approvals list/approve/deny; approve 后无 executor 诚实 blocked | (见 git log) | E2E 审批流 + 7 项单测 |
| AUD-F9 | build_master_agent 注册 5 个认知引擎 — 生产 tick 不再走 status:"stub" 降级 | (见 git log) | 冒烟 + agent 测试 |
| AUD-F13 | 选项 A: cognitive_loop/decision 备用引擎定位裁决 docstring | (见 git log) | phase43/46 测试 |
| AUD-F14 | 四模块 E2E 补强 7 项（proactive/alerts/decision/execution DENY） | (见 git log) | 新测试全过 |
| **最终基线** | | | **5258 passed / 24 skipped / 0 failed** |

### F15 占位复查残留（全部为已登记的诚实降级/文档性标注，非假通过）

- runtime/attention_engine.py:64 — SemanticContentAnalyzer 未实现的显式声明（GAP 已标注）
- engines/text_generator.py:59 — Mock Provider 无 key 时降级（设计）
- runtime/runtime_state.py:4 — SAFE MODE 状态存在性说明
- self/builder.py:273 — 无数据时低置信度占位（诚实标注）
- capability/skill_registry.py:208 — 缺失 skill 占位填充（小项，可后续改进）
- proactive/templates.py:34 — 模板 {topic} 槽位回退（非代码占位）

---

## 九、2026-08-31 全量状态更新（48 commits，本节为当前权威状态）

> 覆盖: POWER_ON_PLAN（上电）+ LLM 接入 + 交互闭环（UX 系列）+ 审计响应（P1/P2/P3）。
> 基线: **5287 passed / 24 skipped / 0 failed**。

### 9.1 沉睡器官上电结果（对照第四节，14/24 已上电）

| 器官 | 上电方式 | 实测产出 |
|---|---|---|
| personal_memory (WisdomStore) | dream 巩固周期触发智慧提炼 | wisdom_items 0→2 |
| personal_intelligence | 对话统计→风格画像→回复适配 | 运行中 |
| cognitive_continuity | dream 连续性检查点落盘 ~/.ocos/continuity.json | 运行中 |
| event_memory | bridge 执行留痕（execute_approved 统一入口） | 运行中 |
| evolution | self_upgrade 提案走完整治理链（影响分析→沙箱→迁移→可回滚） | 运行中 |
| extension | cmd: 候选经 SandboxOps 真隔离试运行 | 运行中 |
| diagnosis | 诊断循环→白名单修复→checkpoint/rollback | 运行中（含探针假阳性修复） |
| living_verification/recovery_resilience | scripts/resilience_drill.py 评分 10/10 | 可定期跑 |
| operations | RUN_COMMAND/HTTP_FETCH 沙盒执行层（白名单+敏感路径+分段校验） | 实测宿主机分析 |
| digital_world | file_op 审批执行器（approval_id 强制+受保护路径拒绝） | 实测 |
| task | AgentRuntime 任务镜像 → Stage ⑤ resolve_ready | 运行中 |
| runtime_scheduler | PriorityQueue 上电（目标优先级+背压 50 上限） | 运行中 |
| perception | --watch-dir 传感器 + 文件语义解析器 → 世界模型接受落库 | 实测 |
| agent_orchestration | 维持沉睡（裁决: 并行执行触碰 step7 冻结语义，延后） | — |

维持沉睡/裁决项: auth、belief.py、agent_orchestration_autonomous、os_v1 路由层、persistence（Deprecated 登记或分工裁决，见 AUDIT_KERNEL 清单）。

### 9.2 本节 F1-F10 全部闭环

F1 半接线 ✓（run.py 装配+镜像 on）· F2 双调度器裁决 ✓ · F3 docstring ✓ · F4 day7 fail-closed ✓ · F5/F6/F7 裁决 ✓ · F8 goal/plan 落库+schema v4 ✓ · F9 引擎注册（stub 降级消灭）✓ · F10 候选裁撤登记 ✓。

### 9.3 新能力（审计之后长出来的）

| 能力 | 说明 |
|---|---|
| 对话即执行 | 说任务自动受理为目标（LLM 编译器分类+改写），无按钮；question/continue 拦截 |
| 真实任务执行 | chat 目标单任务直执行（不走模板分解）；LLM→RUN/FILE_WRITE→沙盒白名单+敏感路径+分段校验；被拦截带反馈重试 |
| 结果自动回推 | 目标完成 → outbox 出站通道 → Web 对话流自动弹 📋 结果气泡（无需询问） |
| LLM 语言核心 | DeepSeek (deepseek-v4-flash) 经 OpenAI 兼容端点接入；日预算 500 次封顶 |
| 内视 | 人型 UI 器官点击 + /ocos/introspect 全模块报告（身份/引擎/记忆/目标/连续性/风格/执行史） |
| 自我迭代 | 自省→治理链提案→审批→self_knowledge 回注提示词，可回滚 |
| 免疫 | 体检→故障检测→白名单修复→checkpoint/rollback；resilience_drill 10/10 |
| 记忆闭环 | 对话自动沉淀 episode；dream 每 200 tick 巩固→belief/wisdom（实测 belief 0→4, wisdom 0→2） |

### 9.4 期间修复的关键静默失效（模式备忘）

| 模式 | 案例 |
|---|---|
| 缺顶层 import | agent_runtime 缺 datetime → F4 去重静默失效（一夜 4000+ 堆积）|
| 属性遮蔽方法 | bridge._textgen=None 遮蔽 _textgen() → 'NoneType' not callable |
| 枚举校验 | Task agent_type='executor' 不在枚举 → 分解永远失败 |
| DB 往返丢字段 | goal 表不存 caller → chat 单任务路径永不触发 |
| 探针调不存在 API | event_memory.count() 不存在 → 假阳性修复循环 148 条 |
| 进程旧代码 | ocos run/server 重启前不加载新代码（多次"修了没生效"的元凶）|

### 9.5 待办余量

- PW-4.3 并行执行（延后裁决）、PW-5.2 营养指标内视化（低优）
- 模板任务描述质量：development 模板仍产出"设计架构"类空壳描述（chat 目标已走单任务路径绕开；SELF/CLI 目标仍受影响）
- consciousness 打通后 belief/wisdom 的消费端（对话上下文已接，决策引用未接）
