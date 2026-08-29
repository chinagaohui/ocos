# OCOS 代码级实现报告

> 依据：`docs/CODE_LEVEL_IMPLEMENTATION_REPORT.md`（OpenTale 代码级实现报告标准）的结构与口径，对 OCOS 项目重新执行代码级审计。
> 审计时间：2026-08-28（晚间复核）。全部结论基于直接读码与全量测试，未修改任何文件。
> 与 `OCOS_COMPREHENSIVE_AUDIT.md`（2026-08-28 07:30）的关系：本文按标准文档的 27 节结构重写，并复核/修正了其中已过时的结论（详见 §23）。

## 1. 报告范围

- 只读静态审计：`search_files` / `read_file` / 全量 `pytest` 运行，零代码改动。
- 审计对象：`ocos/` 源码树 + `tests/` + `ocos/tests/`，排除 venv、__pycache__、.git。
- 判断口径：不依据理想设计，只依据"当前代码实际是什么、被谁引用、能否跑通"。所有结论附文件:行号证据。
- 三个并行子代理（认知循环/记忆持久化/能力治理）+ 主代理逐文件核验，交叉验证。

## 2. 当前总体判断

OCOS 的**认知循环零件全部真实存在且实现完整**，但**未被组装成一条可运行的生产链路**。

- 真实实现的：AgentRuntime 10 步 tick（EventBus→Attention→WM→Goal→Exec→Planning→CoreLoop→Dispatch→ResultIngest→Learning）、MasterAgent act/learn/dream、Attention 决策管道（Phase 35/36）、Homeostasis、Identity/Goal/Episode 持久化、18 个认知引擎、能力编排 8 类、三入口（CLI/API/REPL）、治理三件套（PermissionGuard/BehavioralConstitution/StatementValidator）。
- 未激活的：没有任何生产入口能启动认知循环——CLI/API/REPL 均不实例化任何运行时；ResidentRuntime daemon 外壳存在但零生产引用；RuntimeKernel/TickPipeline 与 AgentRuntime 被治理规则刻意隔离、互不感知；LoopOrchestrator/AutonomousLoop/TaskScheduler 是孤岛。
- 结论一句话：**"已有什么但未激活"是本项目当前最准确的状态描述，不是"缺什么"。** 与 OpenTale 报告（§2"外壳与内核都在推进，但未收口"）同构：OCOS 是"内核零件齐备、主链未点亮"。

## 3. 当前代码规模与结构

### 3.1 核心文件规模（直接命令统计，非近似）

| 范围 | 文件数 | 行数 |
|---|---|---|
| 源码 `ocos/`（不含 ocos/tests） | 580 | 91,178 |
| 顶层文件（`ocos/*.py`） | 6 | 929 |
| `ocos/tests/` | 113 | 39,856 |
| `tests/` | 136 | 31,312 |
| **总计** | **844** | **166,039** |

源码:测试 ≈ 55% : 45%，测试面充足（对照 OpenTale 报告 §17.1 测试 46K/源码 39K，本项目测试规模更大）。

### 3.2 现有主要模块族（按行数排序）

| 模块 | 文件 | 行数 | 定位 |
|---|---|---|---|
| ocos/agent | 37 | 7,426 | AgentRuntime / MasterAgent / 生命周期 |
| ocos/capability | 35 | 7,335 | 能力神经系统（Phase 45）+ PermissionGateway |
| ocos/runtime | 22 | 5,375 | RuntimeKernel / TickPipeline（心跳型） |
| ocos/engines | 18 | 4,912 | 18 个认知引擎 |
| ocos/opentale_bridge | 16 | 4,384 | OpenTale 写作器官桥（Phase 59） |
| ocos/platform | 14 | 4,029 | 平台/日志 |
| ocos/self | 14 | 3,120 | Self 模型 + PreferenceModel |
| ocos/interaction | 10 | 1,497 | CLI / API / REPL 三入口 |
| ocos/goal | 12 | 1,477 | 目标模型 + SQLite 持久化 |
| ocos/memory | — | ~1,400 | MemoryHub + 四通道 store |
| ocos/kernel | 6 | 1,323 | ABI / Constitution 枚举 / GoalTypes |

## 4. 入口层实现状态

### 4.1 CLI（ocos/interaction/cli/）

- `main.py`（argparse，main() 完整）：10 命令 goal / plan / memory / belief / self / trace / organ / decide / regulate / feedback。
- organ/decide/regulate/feedback 四命令直连 OpenTale 桥组件（`opentale_bridge/master_agent.py` 的 `MasterAgent, WritingIntent`、`organ_client.py` 的 `OrganClient`），即"OCOS 作为大脑驱动 OpenTale 写作器官"的入口已可用。
- **关键缺陷**：CLI 只做读/写查询，**不实例化任何认知运行时**（无 AgentRuntime/ResidentRuntime/RuntimeKernel/AutonomousLoop 引用）。`ocos goal create` 不驱动认知循环。

### 4.2 API（ocos/interaction/api/）

- `server.py`（FastAPI，main() → uvicorn :8900）：7 路由 goal/plan/memory/belief/trace/chat/quality + `/ocos/health`。
- `routes/chat.py`（S6：OCOS 主对话入口）——意图解析→写作决策（MasterAgent）→可选经 Organ API 驱动 OpenTale。
- `routes/quality.py`（2026-08-23 老高裁决）——QualityAnalyzer/TrendAnalyzer 暴露为 HTTP，OpenTale 每批章节后调用。
- **同 CLI 缺陷**：API 也是查询壳，不驱动认知循环。

### 4.3 REPL（ocos/interaction/repl/）

- `shell.py`（cmd.Cmd，main() 完整）：认知观察壳，仅观察/查询，不驱动运行时。

### 4.4 入口结论

三入口**完整可运行但定位均为"查询壳"**；pyproject.toml 无 `[project.scripts]`，但 `ocos.egg-info/entry_points.txt` 定义了 ocos / ocos-server / ocos-shell 三个命令（editable 安装残留）。"安装后可用 ocos 命令"在当前 pyproject 下不成立——需在 pyproject 补 `[project.scripts]`。

## 5. 核心认知链路实现状态（对应 OpenTale 报告 §5"核心生成链路"）

### 5.1 AgentRuntime.tick()：10 步全部真实实现（非 stub）

`ocos/agent/agent_runtime.py:309`，步骤映射（每步有真实方法体，L332-1078）：

| Step | 名称 | 方法 | 状态 |
|---|---|---|---|
| 1 | Event Ingestion | `_tick_step_event_ingestion` (L385) | ✅ EventBus→Normalizer→Attention 评估（Phase 34A/35） |
| 2 | Attention Update | `_tick_step_attention_update` | ✅ CognitiveAttentionController 决策（Phase 35/36） |
| 3 | WM Sync | `_tick_step_wm_sync` (L531) | ✅ 工作记忆持久化 + wm_allocation 指令路由 |
| 4 | Goal Maintenance | `_tick_step_goal_maintenance` (L588) | ✅ Attention-aware 目标维护 v2（Phase 36） |
| 5 | Execution Check | `_tick_step_execution_check` | ✅ 执行状态扫描 |
| 6 | Planning Trigger | `_tick_step_planning_trigger` | ✅ 计划触发 |
| 7 | Core Loop | `_tick_step_core_loop` (L769) | ✅ TaskDAG 优先，无 DAG 回退认知循环 |
| 8 | Dispatch | — | ⚠️ 记录执行状态，未真正派发（见 §5.2） |
| 9 | Result Ingest | `_record_episode_from_result` (L984) | ✅ 验证→结构化→Episode 持久化（Phase 26） |
| 10 | Learning Trigger | — | ✅ 记忆固化触发 |

### 5.2 双运行时并存（核心架构事实）

存在 4 套平行且互不接线的"认知/心跳循环"：

- **A. AgentRuntime.tick() 10 步**（ocos/agent/agent_runtime.py）——认知型，被 daemon 包装、被测试驱动，**无 CLI/API 入口**。
- **B. RuntimeKernel + TickPipeline 8 阶段**（ocos/runtime/）——心跳型（tick/checkpoint/recovery），`python -m ocos.runtime` 可自启（60 ticks 演示），**零生产消费者**。
- **C. LoopOrchestrator 7 阶段**（ocos/cognitive_loop/，Phase 46）——被 AutonomousLoop（Phase 60）包装，整体成为**孤岛**（仅 tests/test_phase60.py 引用）。
- **D. TaskScheduler**（ocos/runtime_scheduler/）——纯孤岛（仅 tests/test_phase51_2.py 引用）。

A 与 B 功能同构（同为 event→attention→wm→goal→execution→learning），但治理规则刻意隔离：`tests/phase_e4/release_gate_audit.py:240,437` 把 `ocos.runtime` 列入 forbidden_modules，`test_phase39_1.py:262-263` 断言 import ocos.runtime 不触发 Goal/Agent 初始化。**结果是：心跳引擎永远不会感知认知状态，反之亦然。**

### 5.3 ResidentRuntime（daemon）

- `ocos/daemon/__init__.py:46`——真实 daemon 外壳：包 AgentRuntime + tick 线程（tick_interval=5s）+ 目标队列消费 + 降速。
- **零生产引用**：仅 `tests/test_capability/test_phase33.py` 引用（`grep -rn "ResidentRuntime" ocos/ --include="*.py" | grep -v tests` 为空）。
- 结论：**"常驻个人智脑"的运行时存在，但没有一个入口把它拉起来。**

### 5.4 MasterAgent act / learn / dream：全部真实化（非 stub）

- `act()`（master_agent.py:478）——Phase 22-A 替换 stub：通过 ExecutionManager → EngineBridge.dispatch 到真实引擎，不可用时降级 simulated。
- `learn()`（:616）——CognitiveBridge 调 LearningEngine，结果经 ExperienceBuilder → EpisodeStore 持久化。
- `dream()`（:803）——Memory Consolidation + Lessons Synthesis，合成 Lessons 存 Episode，LifecycleManager 管理宏观阶段。

## 6. Pipeline 实现状态（对应 OpenTale §6）

### 6.1 已存在模块

- **TickPipeline**（ocos/runtime/pipeline.py:39）——8 阶段不可变流水线，每 Stage TickContext→TickContext，失败→SAFE MODE，记录 stage trace。8 个 stage 与 AgentRuntime 的 10 步认知环节一一对应（perception↔Step1、attention↔Step2、memory_sync↔Step3、goal_maintenance↔Step4、execution_check↔Step5、learning_trigger↔Step10、result_collection↔Step9）。
- **runtime/stages/**——goal_maintenance / attention / execution_check / checkpoint_decision 等独立 stage 文件齐全。

### 6.2 成熟度判断

两套 pipeline 语义重复但互不知晓。TickPipeline 由 RuntimeKernel 驱动（仅测试与 `python -m ocos.runtime`），AgentRuntime 内嵌自己的 10 步实现。**这是本项目最大的结构性债务：治理冻结制造了隔离，隔离制造了重复。**

## 7. Domain 模型实现状态（对应 OpenTale §7）

### 7.1 kernel/ 冻结层（6 文件 1,323 行）

- `abi.py`、`constitution.py`（ConstitutionalRule 枚举，24 条不可变规则，L14）、`event_schema.py`、`goal_types.py`（GoalStatus 等）、`time_manager.py`。
- `docs/abi/02-agent-adapter-abi.md` 冻结的 ABI #9（2026-07-25 签署）要求 `AgentLifecycleManager` 等 —— **见 §23.4 发布阻塞**。

### 7.2 现有 domain 模块

- `ocos/goal/`——GoalDomain / GoalStatus / GoalSQLiteStore（goal/store.py:20 建表，save/load/update/delete 齐全）+ factory + tree。
- `ocos/agent/identity_anchor.py` + `identity_store.py`——IdentityAnchor 含 born_at/owner_id（L21-22 建表，L72 save，L98 load）。
- `ocos/interaction/base.py`——GoalRequest / InteractionSession / PermissionGuard 基础抽象。
- `ocos/agent/state.py` / `lifecycle.py`——AgentState + LifecycleManager（BOOTING→ACTIVE→SLEEPING→DREAMING→SHUTDOWN 宏循环 + 微循环状态机，线程安全 RLock）。

## 8. 运行时模式与 fast-path 实现状态（对应 OpenTale §8）

- **无 ExecutionMode 概念**；OCOS 对应物是"运行模式"：AgentRuntime（认知型，被 daemon 包装）/ RuntimeKernel（心跳型，可自启）/ AutonomousLoop（自主型，孤岛）。
- fast-path 对应物：AgentRuntime tick Step 7 的 **TaskDAG 优先执行**（L775-797，每 tick 取 1 task → echo_agent.execute，DAG cursor 推进）——这是唯一真正"干活"的路径，但只存在于测试驱动的运行时里。

## 9. Checkpoint 实现状态（对应 OpenTale §9）

### 9.1 已存在 checkpoint 模块

- `ocos/runtime/checkpoint/`——CheckpointEngine（持久化快照）、recovery/execution_recovery.py。
- `ocos/snapshot/`——manager.py（DB_PATH="ocos.db"，独立连接池复用 storage/connection）、recovery.py（CrashRecovery.load_latest → RecoveryResult）、models.py（AgentSnapshot）。

### 9.2 成熟度判断

- RuntimeKernel 每 10 ticks checkpoint（`python -m ocos.runtime` 演示路径可用）。
- CrashRecovery 已实现（snapshot/recovery.py，加载最新→标记恢复→返回结果）。
- **但**：snapshot 体系（入口 B）与 memory store 自建表（入口 A）是**两套独立持久化命名空间**，互不统辖（详见 §13）。

## 10. Governance 实现状态（对应 OpenTale §10）

### 10.1 已存在模块

- **PermissionGateway**（ocos/capability/permission_gateway.py:186，Phase 24-A 完整版）——caller_id 校验 + issuer 追溯（L1）、反向控制指令检测（L4）、路径穿越/命令注入/SSRF 检测（L4.4）、结构化 JSON 审计日志（L24a4）、集成 AgentRuntime（L24a5）。
- **PermissionGuard**（ocos/interaction/base.py:26）——入口权限强制执行器。**三入口全部强制调用**（CLI 命令 belief/goal/memory/plan/quality/trace、API 路由 belief/goal/memory/plan/quality/trace 全部 `_guard.check()`）。
  - ⚠️ **修正今早审计结论**：OCOS_COMPREHENSIVE_AUDIT.md 声称"PermissionGuard 未强制调用"——**已不成立**。
  - 例外：CLI 的 decide/feedback/organ 命令（写作器官路径）无 guard 调用，属于 OpenTale 桥专用通道（直连 Organ API，非认知写路径）。
- **BehavioralConstitution**（ocos/constitution/behavioral.py，Phase 21.03）——check_decision / check_action / check_promotion 三检查齐全；master_agent.decide() 运行时接线（Decision 检查），check_action 在 autonomous_runtime/loop_supervisor.py:136，check_promotion 在 engines/promotion_engine.py:211。**运行时检查覆盖 Decision+Action+Promotion 三层**（修正今早审计"仅 Decision"的过时结论）。
- **StatementValidator**（ocos/constitution/statement_validator.py）——L5 禁止词汇 + L6 Belief 声明拦截，已注入 ocos/memory/belief/__init__.py:12-13,46-47。
- **auth/**（identity_store / user / role）——仅 scripts/phase23_gate.py 引用，无生产调用者。

### 10.2 能力编排 Governance 事实

- **Capability 8 引擎类齐全**（capability/__init__.py:30-37：CapabilityRegistry/Graph/Selector/Router/AdapterManager/LifecycleManager/ExecutionBridge/ResultInterpreter），**测试齐全**（ocos/tests/test_phase45.py 全覆盖），**但无生产调用者**——ExecutionBridge/ResultInterpreter 仅测试引用；CapabilityOrchestrator 仅被 agent_runtime.py:163-165 延迟初始化（echo_agent 演示用）。
- `agent_runtime.py:832-842` 的 gateway 调用是**死代码**（`if hasattr(self.controller, "pending_contracts")`——MetaController 无该属性）。

## 11. 认知引擎实现状态（对应 OpenTale §11"Compiler"）

- `ocos/engines/` 18 个引擎真实存在：planning / decision / learning / forgetting / goal_arbitration / reflection / retrieval / simulation / prediction / narrative / promotion 等。
- EngineBridge（agent/cognitive_bridge.py）注册表 ENGINE_REGISTRY 齐全（planner/planning_engine 等）。
- **但**：engines 只被 tests 与 agent_runtime 的延迟初始化引用；独立引擎（如 consolidation_engine/forgetting_engine）无生产循环调用（grep 仅命中 cognitive_bridge 的参数位）。
- 判断：引擎 = 器官齐备，主循环 = 未点亮。与 OpenTale §11"合同引擎已存在但能力未接入主链"同构。

## 12. 记忆与状态层实现状态（对应 OpenTale §12/§13 合并）

### 12.1 MemoryHub 四通道（ocos/memory/hub.py:20）

- `episode()` / `belief()` / `semantic()` / `pattern()` 四 store 齐全；initialize/shutdown/is_initialized 完整。
- AgentRuntime `_init_persistence()`（agent_runtime.py:231-295）：Identity 优先恢复 → MemoryHub 初始化 → WorkingMemory 条件创建。**接线真实**。

### 12.2 持久化逐项事实（修正今早审计）

| 记忆 | 实现 | 持久化 | 证据 |
|---|---|---|---|
| Identity | identity_anchor + identity_store | ✅ SQLite（born_at/owner_id 已写入） | identity_store.py:19-22,72,98 |
| GoalStack | goal/store.py GoalSQLiteStore | ✅ SQLite + set_store/restore_from_store | goal/store.py:20 |
| Episode | MemoryHub.episode + MemoryConsolidator 双写 | ✅ hub SQLite | agent_runtime.py:1022,1153 |
| Belief | BeliefSystem（agent/belief_system.py）内存实现 | ⚠️ store 类存在（memory/belief/store.py）但**无 SQLite 写路径** | 无 save 调用者 |
| Pattern | memory/pattern/store.py | ⚠️ 同 Belief：有仓库无写入者 | — |
| WorkingMemory | SQLiteWorkingMemory | ⚠️ **条件持久化**：仅 `db_path != ":memory:"` 时创建（agent_runtime.py:291） | 默认配置下不存在 |
| PersonalMemory | WisdomStore（personal_memory/wisdom_store.py:31-33 内存 dict） | ❌ 未持久化，无生产调用者 | 无 sqlite import |
| EventMemory | EventStore（event_memory/event_store.py:32-37 内存 dict） | ❌ 未持久化；跨 session 靠手动 export | EM54-05 |

### 12.3 新增重大发现：默认 `:memory:` 库

`MemoryHub(db_path=':memory:')`（hub.py:35 默认值）——**即使 store 是 SQLite 实现，默认配置下全部落进程内内存，进程退出即失**。AgentRuntime 的 db_path 由调用方传入，无任何生产调用方传真实路径（CLI/API 不实例化运行时），所以"SQLite 持久化"目前只在测试里为真。

### 12.4 持久化入口分叉（4 套）

- A：各 store 自带 `CREATE TABLE IF NOT EXISTS` 自建表（identity_store.py:19、goal_store.py:20、belief/store.py:24），不走 storage/connection.py 连接池。
- B：master_agent 的 SnapshotManager（ocos/snapshot/manager.py）——独立 DB_PATH="ocos.db"。
- C：ocos/persistence/（Phase 51.1）——独立 SnapshotManager/RecoveryManager/LifecycleManager，**无生产调用者**。
- D：storage/schema.py + migrations.ensure_schema——只覆盖 storage/ 六张表，与 A 的 DDL 无统一迁移编排。

## 13. Repository / 外部器官桥（对应 OpenTale §14）

- **opentale_bridge**（16 文件 4,384 行，Phase 59）——OCOS-OpenTale 桥：organ_client.py（OrganClient，生成任务/状态）、master_agent.py（WritingIntent）、ocos_activation.py、ocos_memory.py、belief_gate.py、bridge_session.py（493 行）。
- 老高裁决已落实：OpenTale 不 import ocos，仅纯 HTTP 转发（quality.py 路由头注释）。
- 判断：桥接层是**生产唯一有真实调用方的路径**（CLI organ/decide/regulate/feedback + API chat/quality）——写作器官集成是当前唯一"点亮"的生产链路。

## 14. Evaluation 实现状态（对应 OpenTale §15）

- 健康/自检族齐全：health_examination/（10 文件）、living_verification/（8 文件）、living_test/（12 文件）、diagnosis/（11 文件）、audit/（8 文件）。
- 但同上模式：主要被 ocos/tests/ 与 living_test 协议驱动，无生产循环挂载。

## 15. 测试实现状态（对应 OpenTale §17）

### 15.1 全量测试（2026-08-28 晚间实测）

```
3134 passed, 4 failed, 1 error   (--continue-on-collection-errors)
```

### 15.2 失败明细（全部有断言证据）

| # | 测试 | 根因 | 定性 |
|---|---|---|---|
| 1 (error) | tests/test_capability/test_phase24.py 收集失败 | `from ocos.capability.lifecycle_manager import AgentLifecycleManager` 失败——**生产代码只有 LifecycleManager** | 🔴 发布阻塞（ABI #9 违约） |
| 2 | tests/test_e2e/test_v1_e2e.py TestEchoAgentEndToEnd | 同 AgentLifecycleManager 缺失 | 🔴 同源 |
| 3 | tests/test_e2e/test_v1_e2e.py TestFullIntegration | 同源 | 🔴 同源 |
| 4 | tests/interaction/test_repl_api.py::test_shared_permission_rules | `assert 8 == 6`：生产 2026-08-23 合法新增 analyze_quality/analyze_trend，测试仍断言 6 条 | 🟡 测试过时 |
| 5 | tests/self/test_no_personality_leak.py | Phase 40（07-26）新增 PreferenceModel 到 ocos/self/，静态扫描（07-24）禁止 self/ 出现"偏好/prefer"字样 | 🟡 测试与功能演进冲突（需裁决：PreferenceModel 归 self 还是 belief） |
| 6 | tests/platform/test_logging_coverage.py | 日志覆盖率 15.4%（107/693 文件）< 20% 门槛 | 🟡 覆盖率缺口 |

### 15.3 判断

3134 绿 = 核心零件验证充分；4 failed + 1 error 中 **3 个同源（AgentLifecycleManager）**，2 个是测试过期，1 个是真实覆盖率缺口。测试面与 OpenTale 报告 §17 同构：**面已扩张，但缺口清单里只有 1 个是"生产资产缺失"，其余是测试与演进失同步**。

## 16. 当前所处阶段映射（对应 OpenTale §18）

- Phase 62（ocos/tests/test_phase62c_pool_integration.py、test_phase62d_loop_coupling.py 存在）——Agent Orchestration + 循环耦合测试已就位。
- Phase 61（agent_orchestration_autonomous.py）——AutonomousOrchestrator 实现但仅测试引用。
- 按 OCOS 阶段推进表：**代码已推进到 Phase 62（自主编排 + 循环耦合），但"点亮运行时"（Phase 33 daemon 激活 / Phase 60 autonomous 激活）从未在阶段中被完成**——阶段推进靠测试绿，不靠生产链路接通。

## 17. 当前系统的主要优点

- **优点 1**：认知循环零件全部真实实现——10 步 tick 无 stub，act/learn/dream 全真实化，Attention/Homeostasis 已接入 tick。
- **优点 2**：治理三件套落地——PermissionGuard 三入口强制、BehavioralConstitution 三检查运行时接线、StatementValidator 注入 Belief 创建。
- **优点 3**：持久化骨架已铺——Identity/Goal/Episode 三通道 SQLite 真实接线（修正今早审计后确认）。
- **优点 4**：测试面远超同类项目——249 个测试文件 71K 行，3134 绿。
- **优点 5**：OpenTale 桥是生产唯一点亮链路——老高裁决落实，器官化边界干净（HTTP 转发、零 import）。
- **优点 6**：治理冻结产生隔离是有意为之（forbidden_modules）——防线存在，只是隔离过度导致未收口。

## 18. 当前系统的主要问题

- **问题 1**：4 套循环互不接线——认知型（AgentRuntime）/ 心跳型（RuntimeKernel）/ 自主型（AutonomousLoop）/ 调度型（TaskScheduler）并存且互不知晓。
- **问题 2**：无任何生产入口点亮运行时——CLI/API/REPL 全是查询壳，ResidentRuntime 零引用，"常驻个人智脑"不存在于任何可启动路径。
- **问题 3**：持久化四入口分叉 + 默认 :memory:——SQLite"持久化"在默认配置下是进程内内存。
- **问题 4**：pyproject 无 [project.scripts]——ocos 命令入口只在 egg-info 残留。
- **问题 5**：AgentLifecycleManager 缺失（ABI #9 冻结违约，Phase 24-C 测试定义完整 API 但生产为零）。
- **问题 6**：Belief/Pattern 有仓库无写入者——信念系统的持久化半途而废。
- **问题 7**：日志覆盖率 15.4%——平台成熟度门槛未过。

## 19. 当前发布阻塞项

- **阻塞项 1（P0）**：AgentLifecycleManager 缺失 → 1 error + 2 failed（test_phase24 / test_v1_e2e×2），ABI #9 冻结违约。缺口面：AgentHandle / AgentState / ConnectMethod / register/connect/authenticate/execute/sleep/wake/release/reclaim_idle/get_stats/health_check。实现位置按冻结：`ocos/capability/lifecycle_manager.py`。注意 `ocos/agent/lifecycle.py` 已有线程安全生命周期状态机（LifecycleManager/LifecyclePhase/MicroState）可复用/包装，不要重复造。
- **阻塞项 2（P1）**：无生产运行时入口——需要决定并实现"点亮"路径：CLI `ocos run` / API 常驻 / daemon 激活三者取一（推荐 daemon ResidentRuntime 作为 `ocos-server --daemon`，或新增 `ocos run` 命令实例化 AgentRuntime + tick 线程）。
- **阻塞项 3（P1）**：持久化默认 :memory:——需要生产默认 db_path（~/.ocos/ocos.db）与统一迁移编排（A/B/C/D 四入口收口）。
- **阻塞项 4（P2）**：pyproject 缺 [project.scripts]——补 ocos / ocos-server / ocos-shell。
- **阻塞项 5（P2）**：PreferenceModel 归属裁决——Phase 40 把它放 self/，Phase 22 静态约束禁 self/ 出现偏好。要么移 belief/，要么修订约束（需用户裁决，勿静默改测试）。
- **阻塞项 6（P2）**：日志覆盖率 15.4% < 20%——按 logging-instrumentation 方法论补 42 个文件（693×5%）。

## 20. 结论

OCOS 的真实状态是：**"个人智脑"的每一个器官（认知循环、注意力、内稳态、目标、记忆、信念、能力编排、治理、写作桥）都已真实编码并有测试证明其正确，但没有任何东西把它们装进一个"始终运行"的进程里。** 这与 OpenTale 报告 §22 的结论同构：零件齐备、主链未亮。下一步不是造新零件，而是**收口**：① 补 AgentLifecycleManager（解锁 3 个红）；② 点亮一个运行时入口（daemon 或 ocos run）；③ 收口持久化（默认库路径 + 四入口统一）；④ 裁决 PreferenceModel 归属 + 修 2 个过期测试 + 补日志覆盖。四条做完，3134+6 全绿 + 常驻可启动，"个人智脑"从测试态进入可运行态。

## 21. 当前代码缺口清单

### 21.1 已完成（本次复核确认）

- ✅ Identity 持久化（born_at/owner_id）——**修正今早审计"缺失"结论**（identity_store.py:19-22）。
- ✅ GoalStack 持久化——**修正今早审计"TODO"结论**（goal/store.py + set_store/restore）。
- ✅ PermissionGuard 三入口强制——**修正今早审计"未强制"结论**（CLI/API 各 5+ 命令路由）。
- ✅ BehavioralConstitution 三检查运行时覆盖——**修正今早审计"仅 Decision"结论**（decision/action/promotion）。
- ✅ act/learn/dream 真实化——**修正今早审计"stub"结论**（master_agent.py:478/616/803）。
- ✅ Attention/Homeostasis 接入 tick——Step 2/3 完整。
- ✅ Episode 双写 SQLite。

### 21.2 半完成

- ⚠️ Belief/Pattern：store 类齐全但无写路径。
- ⚠️ WorkingMemory：条件持久化（默认 :memory: 下不存在）。
- ⚠️ Capability 编排：8 类齐全但无生产调用者；gateway 调用为死代码。
- ⚠️ RuntimeKernel/TickPipeline：完整但被治理隔离为孤岛。
- ⚠️ opentale_bridge：点亮但仅在 CLI/API 查询层。

### 21.3 未完成

- ❌ AgentLifecycleManager / AgentHandle / AgentState / ConnectMethod（ABI #9）。
- ❌ 生产运行时入口（无 CLI/API 实例化任何运行时）。
- ❌ pyproject [project.scripts]。
- ❌ 持久化四入口统一迁移。
- ❌ PersonalMemory / EventMemory 持久化。

### 21.4 发布阻塞（复述 §19 前 3 项）

AgentLifecycleManager 缺失 → 3 红；无运行时入口 → 产品不成立；:memory: 默认 → 持久化不成立。

## 22. 面向"健康可运行态"的剩余工作摘要

- **主线 1（内核收口）**：AgentLifecycleManager 落地（复用 agent/lifecycle.py 状态机）+ Belief/Pattern 写路径接线。
- **主线 2（运行时点亮）**：daemon ResidentRuntime 或 `ocos run` 成为唯一生产启动路径；4 套循环收敛为 1 套被驱动（建议：AgentRuntime 为主，RuntimeKernel 作为其心跳壳，LoopOrchestrator/TaskScheduler 挂载为阶段）。
- **主线 3（持久化收口）**：默认 db_path 落地 + 四入口统一 schema/migration；PersonalMemory/EventMemory 补持久化。
- **主线 4（测试收口）**：修 2 个过期测试（shared_permission_rules、personality_leak 裁决）、补日志覆盖到 20%。
- **主线 5（发布收口）**：pyproject [project.scripts] + README 启动文档。

## 23. 具体施工任务清单

### P0：必须先做

1. 在 `ocos/capability/lifecycle_manager.py` 实现 `AgentLifecycleManager`（冻结 ABI #9 要求的完整 API 面：register/connect/authenticate/execute/sleep/wake/release/reclaim_idle/get_stats/health_check + AgentHandle/AgentState/ConnectMethod）。可包装 `ocos/agent/lifecycle.py` 的线程安全状态机，避免重复实现。验收：test_phase24.py TestLifecycleManager 全绿 + test_v1_e2e 两个 E2E 全绿。
2. 补 pyproject `[project.scripts]`（ocos / ocos-server / ocos-shell 对齐 egg-info 残留）。

### P1：运行时点亮

3. 决策并实现生产启动入口：推荐 `ocos run`（实例化 AgentRuntime + ResidentRuntime daemon 线程，tick_interval 可配）或 `ocos-server --daemon`。验收：`ocos run --ticks 3` 真实驱动 10 步 tick 并落库。
4. 持久化默认路径：AgentRuntime/MemoryHub 默认 db_path 改为 `~/.ocos/ocos.db`（环境变量可覆盖），`:memory:` 仅保留给测试。验收：两次 `ocos run` 之间 Identity/Episode 可恢复。
5. 持久化四入口收口：以 storage/connection.py 连接池 + migrations.ensure_schema 为唯一 DDL 编排，各 store 自建表收敛为 schema 注册（保留兼容 DDL 但标记 deprecated）。验收：storage/migrations 单入口建全表。

### P2：数据与产物收口

6. Belief/Pattern 写路径：BeliefSystem 增补 hub.belief().save() 调用（含 StatementValidator L6 门控）；Pattern 由 learning_trigger 写入。
7. PersonalMemory/EventMemory 持久化：WisdomStore/EventStore 增 SQLite 后端。
8. 裁决 PreferenceModel 归属（self/ vs belief/），同步修订 test_no_personality_leak 或迁移模块（**需用户裁决，禁止静默改测试**）。

### P3：质量门与运行收口

9. 日志覆盖率：按 logging-instrumentation 方法补至 ≥20%（约 42 个文件）。
10. 修 test_shared_permission_rules：断言更新为 8（analyze_quality/analyze_trend 为 2026-08-23 老高裁决合法新增）。
11. 4 套循环收敛路线图：以 AgentRuntime 为唯一认知主循环，RuntimeKernel 心跳作为其 watchdog，LoopOrchestrator 7 阶段映射到 AgentRuntime 步骤（或标注 deprecated 由 governance 裁决）。

### P4：外壳与发布

12. README 补启动文档（ocos / ocos-server / ocos-shell / ocos run）。
13. API 增 /ocos/metrics（对齐 /ocos/health 已有实现）。
14. docs/OCOS_COMPREHENSIVE_AUDIT.md 更新（本次审计已修正 4 条过时结论）。

## 24. 推荐执行顺序

P0(1-2) → P1(3-5) → P2(6-8) → P3(9-11) → P4(12-14)。

- P0 先解锁 3 红（AgentLifecycleManager 一个类解 3 个失败），成本最低收益最高。
- P1 点亮运行时后，P2 的持久化才有真实载体（否则写库无进程）。
- P3 的质量门在运行时点亮后再补（覆盖率统计对象才稳定）。
- 每阶段完成需跑全量 pytest 确认无回归（当前基线 3134+4+1）。

## 25. 最终执行标准

### 内核标准
- 认知循环唯一化：任何新循环必须挂载到 AgentRuntime 或显式标注 deprecated，禁止新增第 5 套平行循环。
- ABI 冻结不可违约：新类必须先在 docs/abi/ 冻结再实现（AgentLifecycleManager 属已冻结未实现，立即补）。

### 数据标准
- 持久化唯一事实源：所有 SQLite 走 storage/connection 连接池 + migrations 编排；:memory: 仅测试用。
- 记忆写路径闭环：任何 store 必须有写入者（Belief/Pattern 补写路径，禁止"有仓库无写入者"）。

### 质量标准
- 全量 pytest 基线：3134 passed / 0 failed / 0 error（修复后基线，禁止新增红）。
- 日志覆盖率 ≥20%，禁止回退。
- 静态约束与功能演进冲突时先裁决后动代码（PreferenceModel 先问老高，不静默改测试）。

### 交付标准
- pyproject [project.scripts] 三命令可用 + `ocos run` 可启动常驻认知。
- 两次启动间 Identity/Episode/Goal 可恢复（持久化验收）。
- 本报告 §23 任务逐项勾销，OCOS_COMPREHENSIVE_AUDIT.md 同步更新。
