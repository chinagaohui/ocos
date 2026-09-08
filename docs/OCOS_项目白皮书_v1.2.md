# OCOS 项目白皮书 v1.3.1

> **v1.3.1 变更记录（2026-09-08）**：收录"数字生命·启动自省 + 三层自愈加固"迭代——① **启动自省（Boot Awareness）**：每次断电/关机重启后 daemon 自动审视自身与所处环境（内核/uptime/disk/内存/GPU/国内外网络/自身记忆计数/boot_id 对比推断重启与停机时长），全只读探查 + 失败降级不阻断启动（`ocos/daemon/boot_awareness.py`）；适应三通道 = 环境先验落盘 `~/.ocos/boot_context.json`（bridge `_boot_context_hint` 注入目标执行，基于当前实测而非过时记忆规划）+ 异常条件转刺激走 MotivationHub 三道闸 + 报告推对话流（kind=report）；全正常时诚实沉默零刺激提案；② **三层自愈模型闭环**：L1 进程崩溃 = systemd Restart=on-failure（既有）；L2 线程僵死 = 心跳看门狗（新增 `ocos/daemon/watchdog.py` + `ocos-watchdog.timer` 每 2 分钟：心跳 >90s 过期自动重启 daemon、JSONL 记账 ops/restart.log、心跳文件不存在 = 人为停止诚实跳过不误杀）；L3 认知/数据损伤 = HealthLoop 四层自检 + repair_link 白名单修复（既有）；③ **tick 线程自愈兜底**：`_tick_loop` 主循环最外层 try/except（残余异常不再杀死 tick 线程致 daemon 僵死）+ `_drain_user_inbox` fallback 路径补保护；④ **每日 DB 在线备份**：看门狗顺带执行（SQLite backup API 不锁库 → `~/.ocos/backups/ocos-YYYYMMDD.db` 保留 7 份），消除"自动备份：无"缺口；⑤ E2E 演练验证：心跳回拨 300s → 看门狗实测重启 + 记账 + Boot awareness 自动重跑。测试基线：本轮新增 test_boot_awareness_20260908.py（15 项）+ test_watchdog_20260908.py（7 项）全绿。

> **v1.3 变更记录（2026-09-06）**：在 v1.2 审计版基础上收录 UX-J 迭代——① TUI 重构为纯前端（WebSocket 网关通信，业务逻辑全部后置）；② AGI 智能体软件接入（AgentDiscovery 自动发现/安装/真实执行）；③ 生产执行链闭环优化 8 项（完成即推、ANSWER| 认知任务出口、拦截重试标签修正、核心工具黑名单、沙盒 PATH/敏感设备放行、复盘素材注入、按行截断、告警去重、域推断）；④ 交互升级（Markdown 渲染、流式输出、会话持久化回放、双行状态栏）。两轮四项生产测试实弹验证闭环（§0.2 第四代）。

> **文档性质**：OCOS（Organic Cognitive Operating System，有机认知操作系统 / 数字生命认知操作系统）内核权威全集参考文档。
> **生成方式**：2026-09-05 对项目全部 1270 个文件（排除 .venv/缓存后）执行全源码扫描审计，13 个审计分组逐文件深读约 9.1 万行内核源码后汇编而成。全部结论落到具体文件与函数，未经证实的部分标注【信息缺失】。
> **验证状态标记约定**：【静态推演验证】= 基于源码逻辑推导可运行；【功能实测可通】= 审计中实际运行/测试通过；【逻辑不完整】= 存在占位代码、未接线分支或确定性缺陷。

## 0. 项目总览

### 0.1 项目定位、内核设计目标、解决的问题、适用场景

OCOS 是一个**数字生命体内核 / 个人智脑内核**——"非 Agent 框架，非 LLM 包装器，非记忆后端"（README.md、docs/ARCHITECTURE.md、根目录《OCOS_Cognitive_Sovereignty_Freeze_v0.1.md》§1）。其设计目标是构建一个**常驻运行、状态持久、行为一致、具备长时序记忆与自我推演能力**的认知实体内核：

- **解决的问题**：让 LLM 驱动的认知过程具备 ①持久化身份与记忆（跨重启连续）、②目标生命周期管理（创建-认领-执行-完成-回收闭环）、③决策执行闭环（风险分级 + 审批 + 沙盒 + 审计）、④信息保真（感知→经验→情节→模式→知识→信念的逐级门控流水线）、⑤自我治理（宪法约束、权限网关、进化审批链）。
- **适用场景**：本地长期运行的个人数字生命/智脑；以 DeepSeek 等国产 LLM 为"语言核心"、以 OpenTale（外部 AI 写作引擎）为"写作器官"的认知操作系统。
- **铁律**（主权冻结 v0.1）：**"OCOS 是脑，Agent 是手"**——所有外部实体（Codex/OpenTale/Browser 等）必须落在 Capability Provider 层，绝不可以成为认知实体。

需要如实说明：任务书指定的"NFI 叙事保真链""World Integrity""ChapterSituation"三个组件名在代码中**不存在同名实现**（全仓 grep 零命中），其能力分别由记忆保真流水线（`ocos/memory/` 六级门控）、世界输入治理（`ocos/world_model/world_validator.py`）与事件时序/章节相位体系（`ocos/event_memory/`、`ocos/cognitive_continuity/`、`ocos/opentale_bridge/bridge_model.py` BridgePhase）承担，详见第 2 章各节的对应关系说明。

### 0.2 项目版本现状：已完成 Phase、规划 Phase、Scope Freeze 机制

- **代码版本**：ocos 1.0.0（pyproject.toml）；requirements.lock 内 editable 安装记录为 0.2.0（版本声明漂移，P5 级问题）。
- **Phase 完成史（三代叙事并存，存在文档代差）**：
  1. **Phase A–Z 时代**（docs/ARCHITECTURE.md、docs/PROJECT_STATUS.md，2026-09-02）：25 个 Phase 全部完成，测试 260+。
  2. **Era II / Phase 21–30 时代**（docs/ROADMAP.md v2.0、scripts/phase21–30_gate.py）：P21 骨架 → P22 认知循环真实化 → P23 Capability ABI → P24 主权与基础设施 → P25 能力知识/经验 → P26 结果理解 → P27 架构冻结签发 → P28 编排 → P29 Personal OS v1.0 → P30 注意力模型。
  3. **Phase 39–62 + GAP/PW 上电时代**（docs/OCOS_MODULE_AUDIT_20260830.md、docs/OCOS_POWER_ON_PLAN.md、docs/PRODUCTION_VALIDATION_REPORT_20260905.md）：Phase 39 运行时心跳/检查点 → 43 决策智能 → 44 扩展治理 → 45 能力神经系统 → 46 认知循环集成 → 47 进化治理 → 48 Agent 代理 → 49 记忆/世界/技能/元认知 → 50 Personal OS/成长 → 51 持久化/审计 → 52 感知 → 53 主动交互 → 54 事件记忆 → 55 真实能力层 → 56 免疫系统 → 57/58 活体验证 → 59 OpenTale 桥 → 60 自主运行时 → 61 自主编排 → 62 耦合；沉睡器官 24 个中 14 个已上电（PW-1~5 波次）；最新基线 5287+ tests passed（docs/PRODUCTION_VALIDATION_REPORT_20260905.md 报告 34/34 生产验证通过，但本白皮书审计发现该报告未覆盖的确定性缺陷，见第 10 章）。
  4. **UX-J 交互与生产闭环时代**（2026-09-06，本版新增）：P5 AGI 计划收尾（P5.1 失败归因 lesson 管道、P5.2 主动交互管线上产）→ TUI 纯前端化重构（`ocos/tui/` 包，WebSocket 网关通信，业务逻辑全部后置 daemon/API）→ 会话 ID 下发与历史回放 → AGI 智能体软件接入（`ocos/capability/agent_discovery.py` 自动发现 + `agent_installer.py` 白名单安装 + AdapterManager 真实执行 + 保真闸门）→ 生产执行链优化 8 项（完成即推 0 秒、`ANSWER|` 认知任务出口、拦截重试标签修正、核心工具黑名单、`/dev/null` 放行、沙盒 PATH 补 `/usr/local/bin`、复盘素材注入、输出按行截断、tick 告警去重、goal 域推断）→ **两轮"四项生产测试"实弹闭环验证**（探索宿主机/发现智能体/调用反馈/学习总结：第二轮 5 分钟全绿、零自愈、即时推送 2ms；测试基线 2370 passed / 0 failed）。
  5. **数字生命与自愈时代**（2026-09-08，本版新增）：自我连续性修复（`AgentRuntime.save_weekly_identity_snapshot()` 周度身份快照，周键幂等，全局保留 26 周；修复 systemd 下优雅关闭从不发生 → identity_snapshots 表恒空的历史缺口）→ 好奇心去噪与第二源（`_from_belief_boundary` 过滤 pattern 模板回声；`_from_self_exploration` pkgutil 实扫从未触及的 ocos 子包生成自我探查 PROBE）→ **启动自省 Boot Awareness**（daemon 启动即审视环境：采集→分析→适应→汇报，全只读+失败降级；boot_context.json 先验注入目标执行；异常条件转自主目标刺激；全正常诚实沉默）→ **三层自愈闭环**（L1 systemd Restart=on-failure / L2 心跳看门狗 ocos-watchdog.timer 每 2 分钟自动重启假死 daemon / L3 四层自检+白名单修复）+ tick 线程自愈兜底 + 每日 DB 在线备份（7 份轮转）。测试基线：全量 2787+4424 tests passed（含本轮新增 boot_awareness 15 项 + watchdog 7 项）；重启顺序 server → daemon → gateway。
- **Scope Freeze 机制**：定义出处为 docs/runtime/P2A~P2D 四份"Scope 冻结"文档、根目录《OCOS_Cognitive_Sovereignty_Freeze_v0.1.md》（最高级冻结：系统身份/宪法/架构边界/子系统职责/阶段顺序）与 docs/ARCHITECTURE_FREEZE_PROTOCOL.md（AFP 三层准入：Principles → AFP → Frozen Modules）。代码级对应 `ocos/os_v1/freeze.py` 的 `OSFreeze`：冻结**接口契约而非实现**（ABI_MODULES 12 模块、6 条宪法原则、3 个 SDK 协议），签名为字符串拼接 `f"{mod}:v1.0"`、**非密码学签名**，冻结后无实现变更强制校验钩子——属声明式冻结（P3 级限制）。
- **注意**：任务书假设的 "DRAFT/FROZEN" 两态字样在仓库中**不存在**（全仓 markdown 零命中 "DRAFT-FROZEN"）；实际使用的冻结标记是 "FROZEN / ❄️ FROZEN / Freeze Certificate / Scope 冻结"。

### 0.3 内核能力边界

**OCOS 可以做到（已实测/已接线）**：
1. 常驻 daemon 心跳驱动 10 步认知 tick（事件摄入→注意力→记忆同步→目标维护→执行检查→规划→核心循环→结果反刍→学习巩固），目标 PENDING→ACTIVE→COMPLETED 全闭环（ocos/daemon/__init__.py、ocos/agent/agent_runtime.py、ocos/goal/store.py）。
2. 对话即执行：CLI say / WebChat / API / TUI 四入口 → ChatResponder（USE| 工具协议 + LLM 多步循环）→ 自动建目标 → DecisionBridge 执行 → 结果回推（ocos/interaction/converse.py）。TUI 为纯前端（WebSocket ↔ API 网关 ws.py），业务逻辑零前置。
3. LLM 任务执行：白名单沙盒命令、敏感路径拦截、LLM 结论摘要、日预算 500 次/天（OCOS_LLM_DAILY_CAP，ocos/execution/bridge.py）；动作词表 RUN|/ANSWER|/FILE_WRITE|/AGENT_INSTALL|/NONE|——`ANSWER|` 支持认知型任务（复盘/总结）直接产出文字结论（UX-J 新增）；目标结果完成即推 outbox（秒级，daemon `_record_goal_result` 回调）。
4. 长时序记忆：Episode/Pattern/Knowledge/Belief 四库 SQLite（WAL）+ 跨会话召回 + dream 巩固产智慧/信念/学习规则；复盘/总结类任务自动注入最近 goal_result 结论作素材（`_retrospect_hint`）。
5. 持久化恢复：Agent 快照 + 四域多域快照 + 检查点 + 崩溃回收队列（requeue_stale_active）。
6. 安全：宪法引擎（fail-closed）、权限网关、语句验证器、沙盒黑白名单、审批待批队列；智能体 CLI 候选名黑名单防御（防核心工具误配进沙盒，UX-J 新增）。
7. 智能体软件接入（UX-J 新增）：AgentDiscovery 自动发现本机 CLI/HTTP 智能体（openclaw/codex/ollama 实测可用）、未安装项诚实标注并可经白名单安装命令闭环安装（agent_installer.py + AGENT_INSTALL| 审批流）；执行输出按行边界截断防 LLM 误读。

**OCOS 不负责 / 未做到**：
1. 不做真实多实例分布式（ocos/distributed 是单进程内存模拟）；不提供认证鉴权（API 裸奔 0.0.0.0，见第 10 章 P1）；不加载 .env 文件。systemd 单元文件已部署于用户机 ~/.config/systemd/user/（ocos-server/ocos-daemon/hermes-gateway，Restart=on-failure），但仍未纳入版本管理。
2. 大量"完整实现但未接线"的能力（约 20+ 沉睡器官/孤立支线）：Phase 53 主动交互管线（P5.2 已部分上产：goal_stale 扫描）、channel 多通道、orchestration、extension、engagement、living_test/health_examination/audit/living_verification 四层验证基础设施（其"通过"结论不可作健康依据）等。
3. 九大能力引擎中多数默认逻辑为结构化占位（诚实标注，无真实推理/LLM 调用）；evolution 迁移为模拟桩。
4. 命名组件澄清：NFI/World Integrity/ChapterSituation/AGI Runtime 四个名称与代码的映射见第 1.3/1.4 节。

### 0.4 外部依赖

| 依赖 | 用途 | 接入点 |
|---|---|---|
| DeepSeek（deepseek-v4-flash，经 OpenAI 兼容端点） | 语言核心/对话/LLM 任务规划 | ~/.ocos/config.json（llm 段）→ ocos/engines/text_generator.py OpenaiProvider |
| OpenAI/Anthropic API（可选备用） | LLM 备选 Provider | ANTHROPIC_API_KEY/OPENAI_API_KEY 环境变量 |
| OpenTale Organ API（http://127.0.0.1:8000/api/organ） | 外部 AI 写作引擎（写作器官） | ocos/opentale_bridge/organ_client.py，Bearer OCOS_OPENTALE_TOKEN |
| 本机智能体软件（UX-J 新增，可选） | 外部智能体能力：openclaw/codex（CLI 实测可用）、ollama（HTTP 11434）；未装项可白名单安装 | ocos/capability/agent_discovery.py（which+version/HTTP 探测）→ AgentManager CLI 执行 → DecisionBridge 注入/保真闸门 |
| SQLite（标准库 sqlite3，WAL） | 全部持久化 | ocos/storage/connection.py 连接池 |
| psutil（可选） | 环境内感 | ocos/perception/environment_sensor.py |
| FastAPI/uvicorn/httpx/textual/numpy/scipy/pydantic | API 网关/TUI/数值 | pyproject.toml dependencies |

### 0.5 术语词典

| 术语 | 定义 | 权威出处 |
|---|---|---|
| **NFI（叙事保真链）** | 任务书命名组件；代码中**无同名实现**。其"信息保真"能力由记忆流水线承担：TraceBundle→ExperienceCandidate→（Significance Gate 四维评分）→Episode→（PatternExtractor 聚合）→Pattern→（KnowledgeValidator 五重防护）→Knowledge→（EvidenceBinding ≥3 证据）→Belief，全链禁第一人称/身份语汇（中英双语检测） | ocos/memory/（experience/significance/episode/pattern/semantic/belief 子包） |
| **World Integrity（世界完整性校验）** | 代码中无同名组件；对应物为 world_model 的 WM42-04 外部输入治理：Observation→WorldValidator（来源/置信度/内容检查）→WorldStore 唯一写入口 update_from_observation()。注意 validate_against_model 存在自比较 bug（world_validator.py:118，实测恒 ACCEPT，P1 级缺陷） | ocos/world_model/world_validator.py |
| **DecisionBridge（决策闭环）** | 真实存在。R4-A"自治循环决策→真实任务执行铰链"：process()/execute_dag_task() 双入口，AUTO/ASK/DENY 三级风险裁决，PermissionGuard 语义双检，PendingStore 待批，ExecutionAudit+event_memory 双留痕，LLM 任务转换+日预算 | ocos/execution/bridge.py:116 |
| **ChapterSituation（时序状态管理）** | 代码中无同名组件；时序状态能力由三处承担：① opentale_bridge.BridgePhase 章节相位状态机（7 态）+ OcosDecision/TranslationResult 章节级报文；② event_memory 认知事件时序（append-only + 因果链 caused_by + HOT/WARM/COLD/ARCHIVED 生命周期）；③ cognitive_continuity 时间线（过去/现在/未来意图三段 + 经验日/周/月/年层次提炼） | ocos/opentale_bridge/bridge_model.py、ocos/event_memory/、ocos/cognitive_continuity/ |
| **AGI Runtime（认知运行时）** | ocos/runtime 包：RuntimeKernel 心跳引擎（start/stop/shutdown + tick_loop）+ TickPipeline 8 阶段冻结管线（EVENT_INGESTION→ATTENTION→MEMORY_SYNC→GOAL_MAINTENANCE→EXECUTION_CHECK→RESULT_COLLECTION→LEARNING_TRIGGER→CHECKPOINT_DECISION）+ 双层 checkpoint/snapshot + 四级权限网关；与 ocos/agent/agent_runtime.py 的 10 步认知 tick 构成"心跳外壳 + 认知内核"双层 | ocos/runtime/、ocos/agent/agent_runtime.py |
| **Scope Freeze** | 范围冻结：冻结接口契约而非实现（OS50-05 Freeze≠Dead）；OSFreeze.freeze(tick_id) 生成 FreezeManifest | ocos/os_v1/freeze.py、docs/runtime/P2*.md |
| **FROZEN / Freeze Certificate** | 仓库实际使用的冻结标记（"DRAFT-FROZEN"字样不存在）；冻结证书见 audit/phase14_freeze_certificate.md 等 | audit/、docs/abi/ |
| **P1–P5** | 本白皮书风险分级：P1 致命（安全越权/数据损坏/主链必崩）、P2 严重（功能失效/结论失真）、P3 中等（健壮性/可移植性）、P4 一般（死代码/死接口）、P5 轻微（风格/文档）。仓库历史编号体系为 P0(+)/P1/P2/P3 审计发现 + GAP-P* 修复编号 + PW-* 上电编号三套并行，无统一对照表 | 本白皮书第 10/11 章；docs/OCOS_AUDIT_KERNEL.md |
| **沉睡器官** | 代码完整、有测试、但无任何生产调用者的模块（24 个中 14 个已上电） | docs/OCOS_POWER_ON_PLAN.md |
| **上电（PW-\*）** | 将沉睡器官接入生产调用链的修复动作编号 | docs/OCOS_POWER_ON_PLAN.md 执行记录表 |
| **tick / T\*** | 心跳最小时间单元；RuntimeKernel.tick_loop 每 tick 依次跑 8 阶段管线 + agent driver | ocos/runtime/tick.py |
| **dream 巩固** | daemon 每 dream_interval_ticks(默认200) 触发：修复相位→agent.sleep()→agent.dream()（快通路学习+Episode→Belief 巩固+智慧提炼+连续性检查点）→persist_latest_rules | ocos/daemon/__init__.py L513-545 |
| **经验门控（Significance Gate）** | 四维加权评分（goal_impact .25/prediction_error .30/knowledge_change .20/future_relevance .25），阈值 0.5，决定经历是否获得"跨时间存在资格" | ocos/memory/significance/ |
| **USE\| 协议** | LLM 回复内嵌动作行 `USE|<capability>|<params JSON>`，capability∈{shell,fs_read} 只读白名单，每回复 ≤2 轮工具、LLM 调用 ≤3 | ocos/interaction/converse.py |
| **RUN\|/ANSWER\|/FILE_WRITE\|/AGENT_INSTALL\|/NONE\| 协议** | DAG 任务规划的 LLM 动作词表：RUN 执行只读命令（最多 4 行）、ANSWER 直接产出文字结论（认知型任务，UX-J 新增）、FILE_WRITE 写文件（强制待批）、AGENT_INSTALL 安装智能体（强制待批）、NONE 诚实说明无法执行 | ocos/execution/bridge.py `_handler_dag_task` |
| **AgentDiscovery（智能体自动发现）** | 确定性探查本机智能体软件：CLI（shutil.which + version 探测）/HTTP 端点/config 注入三源；未安装项诚实标注 available=False（可附 install_command 走白名单安装闭环）；核心工具黑名单防候选误配 | ocos/capability/agent_discovery.py |
| **完成即推（goal_result 即时推送）** | 目标完成 → episode 落库 → daemon `_on_goal_result` 回调直接推 outbox（实测 2ms 到达 TUI 面板）；原 5-tick 定时推送保留为兜底 | ocos/agent/agent_runtime.py `_record_goal_result`、ocos/daemon/__init__.py |
| **复盘素材注入（_retrospect_hint）** | 复盘/总结/学习类任务自动注入最近 4 条 goal_result 结论摘要，禁止重新执行系统采集命令——认知型复盘从"跑偏文件系统"转为"基于记忆作答" | ocos/execution/bridge.py |
| **纯前端 TUI** | ocos/tui/ 包（tui_client+ws_client+widgets）：界面只做渲染与输入转发，业务逻辑全在 API 网关（ws.py）+ daemon；会话 ID 持久化 ~/.ocos/gateway_session，历史经 EpisodeStore 回放 | ocos/tui/、ocos/interaction/api/routes/ws.py |
| **Master Agent** | 全系统唯一"意识主体"（Phase 22 冻结原则：永远只有一个）；集成 LifecycleManager+ControlLoop+20+ 可选管理器 | ocos/agent/master_agent.py |
| **Decision≠Execution / Goal 源闭合** | 宪法边界：决策不等于执行（必须经 Capability→Permission→Execution）；Goal source 闭合枚举 HUMAN/DECOMPOSED，Agent 不能凭空创建 Goal | 冻结 v0.1 §2、ocos/decision/decision_types.py |
| **CLS 快慢通路** | 快通路学习（即时 Episode→规则）与慢通路巩固（dream 期聚类/智慧提炼）双系统 | ocos/agent/master_agent.py dream() |

## 1. 整体系统架构

### 1.1 分层架构总图

按任务书要求的六层映射到实际代码（括号内为真实包路径）：

```
┌─────────────────────────────────────────────────────────────────────┐
│ 对外网关层（ocos/interaction/：API 21端点 · CLI 40+命令 · REPL · TUI）  │
│   入口：ocos run(daemon) / ocos say / /ocos/converse / python -m TUI  │
├─────────────────────────────────────────────────────────────────────┤
│ 认知调度层（ocos/runtime/ RuntimeKernel 8阶段管线 + ocos/runtime_      │
│   scheduler/ + ocos/daemon/ ResidentRuntime tick循环 + dream）        │
│   └─ 认知内核：ocos/agent/agent_runtime.py 10步tick + master_agent.py │
├─────────────────────────────────────────────────────────────────────┤
│ 时序信息处理层（ocos/memory/ 六级保真流水线 · ocos/event_memory/ ·     │
│   ocos/cognitive_continuity/ · ocos/perception/ 感知 · ocos/attention/│
│   注意力 · ocos/attention 认知注意力控制器 · ocos/knowledge/ 知识平面）│
├─────────────────────────────────────────────────────────────────────┤
│ 数字生命状态层（identity/goal/belief/episode/pattern/knowledge 六库 · │
│   ocos/world_model/ 世界模型 · ocos/self/ 身份边界 · ocos/belief.py）  │
├─────────────────────────────────────────────────────────────────────┤
│ 模型接入层（ocos/engines/text_generator.py：Mock/Anthropic/Openai     │
│   (DeepSeek)/Failover 四 Provider + ~/.ocos/config.json）             │
│   执行器：ocos/execution/ DecisionBridge · ocos/capability_reality/   │
│   沙盒适配器 · ocos/operations/ 闸门 · ocos/digital_world/ 宽操作库    │
├─────────────────────────────────────────────────────────────────────┤
│ 持久化层（ocos/storage/ 连接池+schema v5+迁移 · ocos/persistence/ ·   │
│   ocos/snapshot/ · ocos/recovery/ · SQLite WAL ~/.ocos/ocos.db）      │
├─────────────────────────────────────────────────────────────────────┤
│ 横切：ocos/kernel/ ABI+24条宪法 · ocos/constitution/ 运行时宪法 ·      │
│   ocos/capability/permission_gateway 权限网关 · ocos/events + ocos/   │
│   event 双事件总线 · ocos/logging JSON日志 · ocos/platform/ Trace/审计/│
│   治理/插件 · ocos/learning + ocos/evolution + ocos/growth 自演化     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件关系文字描述（数据流/调用流，仅限 OCOS 内部）

主链路（生产实测）：

1. **入口**：`ocos run`（interaction/cli/commands/run.py）→ ensure_schema → daemon.factory.build_master_agent/build_execution_bridge/build_health_loop/build_perception_pipeline → ResidentRuntime.start()。
2. **心跳**：daemon `_tick_loop`（单线程）→ `kernel.tick_loop(max_ticks=1)`（runtime/runtime_kernel）→ TickPipeline 8 阶段（生产全缺省空转）→ `agent_driver(tick_id)` = AgentRuntime.tick()。
3. **认知 tick（10 步）**：agent_runtime 依序：事件摄入（ocos/event EventBus.ingest）→ 注意力（capability/attention.CognitiveAttentionController.decide）→ WM 同步（memory_consolidator）→ 目标维护（goal_store 恢复）→ 执行检查 → 规划触发（planning.TaskDecomposer：Goal→TaskDAG，镜像入 ocos/task.TaskDAG）→ 核心循环（逐任务经 **DecisionBridge.execute_dag_task**）→ Dispatch（PermissionGateway+DecisionBridge）→ 结果反刍（Result→WM/Episode/Attention）→ 学习巩固（experience_learning 规则提取）。
4. **执行**：DecisionBridge（execution/bridge.py）按 AUTO/ASK/DENY 裁决 → capability_reality.AdapterDiscovery 发现的 FilesystemAdapter/ShellAdapter 或 operations.SandboxOps 沙盒执行 → ExecutionAudit + event_memory event_store 表留痕 → 待批项入 PendingStore（pending_actions 表）。
5. **LLM**：bridge/converse 内 get_text_generator()（engines/text_generator.py，模块级缓存）→ OpenaiProvider（DeepSeek，~/.ocos/config.json）→ 失败降级 FailoverProvider/Mock。
6. **对话链**：say/WebChat/API → UserInbox（user_messages 表）→ daemon._drain_user_inbox → ChatResponder.respond_auto → compile_goal（LLM 分类）→ GoalStore PENDING 目标 → ConversationStateStore → daemon 认领（claim_pending_human）→ 同上主链 → 结果经 UserInbox.post_outbound 回推。
7. **巩固链**：daemon 每 200 tick dream → agent.sleep/dream → belief_consolidation + wisdom_trigger（wisdom_items 表）+ continuity_trigger（~/.ocos/continuity.json）+ persist_latest_rules（learning_models 表）。
8. **持久化**：全部落 ~/.ocos/ocos.db（identity/goal(双表)/goals/episodes/belief/pattern/knowledge/plan_dag/pending_actions/user_messages/wisdom_items/snapshots/proactive_audit 等表）+ ocos_data/persistence/（多域快照）+ /tmp/ocos_checkpoints（runtime 快照，P2 部署缺陷）。

### 1.3 四大核心组件总体说明

| 组件 | 代码映射 | 一句话说明 |
|---|---|---|
| NFI 叙事保真链 | ocos/memory/ 六级流水线 + ocos/opentale_bridge（NarrativeContract 契约补丁链） | 无同名代码；保真能力=六级门控（每级有独立 Validator，禁第一人称/身份归因/行为准则语汇）+ 写作契约级控制面（QualityAnalyzer 5 维→TrendAnalyzer 5 类趋势→ContractAdjustment 契约补丁） |
| World Integrity | ocos/world_model/world_validator.py + ocos/digital_world 保护路径 | 无同名代码；世界输入治理 WM42-04（来源/置信度/一致性检查）+ 数字世界受保护路径（/etc/shadow 等）|
| DecisionBridge | ocos/execution/bridge.py（1154 行） | 真实存在且是接线最充分的执行铰链；但存在 FILE_WRITE 自造审批 ID 的 P1 缺陷（bridge.py:905） |
| ChapterSituation | ocos/event_memory/ + ocos/cognitive_continuity/ + ocos/opentale_bridge/bridge_model.BridgePhase | 无同名代码；时序=事件 append-only+因果链+四段生命周期，章节相位=7 态 BridgePhase 状态机 |

### 1.4 AGI Runtime 认知运行时总体说明

- **心跳外壳**：`ocos/runtime/runtime_kernel.py` RuntimeKernel——start() 返回 runtime_id，tick_loop 驱动 TickPipeline；PipelineStage 8 阶段冻结顺序（PipelineStage 枚举 + TickStage Protocol：Stage 不得修改传入 context、不得 import runtime_kernel/ocos.self）；TickContext 为 frozen dataclass（8 阶段输出全 tuple）。**生产现状：8 个 stage 全部缺省空转**（GAP-P2-2 组件为真实现、无生产装配注入），真实认知全部发生在注入的 agent driver；LearningTriggerStage 恒占位；权限网关在生产路径无流量（P2 级"生产旁路"）。
- **恢复**：recovery_engine 双写低层 CheckpointRecord（JSON+SHA-256，tick 连续性）与高层 RuntimeSnapshot（认知状态矢量：attention_focus/active_goal_ids/pending_executions/pending_approvals/event_log_cursor）；RecoveryManager 编排 SnapshotStore（保留 20）+ EventLog(JSONL) + ExecutionLedger + ApprovalStore + CognitiveStateRestore 六步恢复。**缺陷**：恢复出的认知矢量不回灌任何活跃组件（P2）；恢复数据落 /tmp（P2）；RecoveryManager.shutdown 双定义丢账本落盘（P1）。
- **认知内核**：`ocos/agent/agent_runtime.py` 10 步 tick（上文 1.2 第 3 步）+ `ocos/agent/lifecycle.py` 双层状态机（LifecyclePhase 宏观 6 相 + MicroState 微观 7 相）+ `ocos/agent/state.py` 14 态 AgentStatus 基础状态机。
- **调度器**：`ocos/runtime_scheduler/`（Phase 51.2 独立任务心跳调度器：CognitiveClock/PriorityQueue/Backpressure/WorkerManager，RS51 边界契约）——**无生产消费者**，daemon 仅借用 PriorityQueue 做目标队列深度记账。

### 1.5 OCOS 内核完整主业务流程（外部输入 → LLM 认知推演 → 数字生命状态修改 → 持久化存档）

以一条用户消息的完整生命周期为例（每步标注源码位置）：

1. **外部输入**：`ocos say "分析科幻小说市场趋势"` → UserInbox.post（user_messages 表，interaction/inbox.py）。
2. **消息消费**：daemon._drain_user_inbox（daemon/__init__.py）→ ChatResponder.respond_auto（interaction/converse.py）。
3. **意图分类**：compile_goal → LLM（get_text_generator → DeepSeek）判定 task/question/continue。
4. **目标创建**：task 类 → GoalStore.save（goals 表，status=PENDING，origin_level=HUMAN，caller=chat）→ ConversationStateStore.update（current_goal_id）。
5. **目标认领**：daemon._claim_persisted_goals → GoalStore.claim_pending_human(limit=1)（原子 UPDATE WHERE status='PENDING'，→ACTIVE）→ 写入 runtime._goal_store。
6. **规划**：AgentRuntime Step6 → TaskDecomposer.decompose（Goal→TaskDAG，4 域模板）→ 镜像入 ocos/task.TaskDAG。
7. **LLM 认知推演与执行**：Step7 逐任务 DecisionBridge.execute_dag_task → L8 置信度门 → LLM 把任务转动作行（RUN|命令 / FILE_WRITE|路径|内容 / NONE）→ 白名单+敏感路径校验 → SandboxOps/capability_reality 沙盒执行 → LLM 结论摘要。
8. **状态修改**：执行结果 → WorkingMemory/EpisodeStore（episodes 表，tags 含 goal_result）/Attention 更新；daemon._push_goal_results 经 UserInbox.post_outbound 回推"目标执行完成"。
9. **学习巩固**：Step10 每 10 tick 经验信念提取（_extract_beliefs_from_results）；dream 期 Episode→Belief 巩固、wisdom_items 落库、learning_rules 落 learning_models 表。
10. **持久化存档**：每 tick 心跳 ~/.ocos/daemon_heartbeat.json；AgentRuntime boot/shutdown 保存 identity snapshot（identity_snapshots 表）；PersistenceManager 每 300s auto_save（ocos_data/persistence/snapshots/）；daemon stop 优雅停机（30s join）。

## 2. 模块详细说明（逐个内核模块拆解）

> 统一格式：模块路径范围、模块职责、对外提供能力、内部子模块、输入输出、正常工作流程、异常处理逻辑、依赖、被调用、已知限制、验证状态。
> 2.1–2.13 为任务书指定 13 个模块的权威映射（含"任务书命名 vs 代码实现"的澄清）；2.14 为全部 60+ 内核模块的逐模块详录（来自 13 个审计分组的原始深读记录，含每模块完整字段级说明）。

### 2.1 NFI 叙事保真链模块

- **模块路径范围**：任务书命名组件，代码中无 NFI/Narrative Fidelity 命名实现（W7 审计对 world_model 全部文件 grep `narrative|fidelity|integrity|NFI` 零命中）。对应能力由两个体系承担：
  1. **信息保真流水线**：`ocos/memory/`（experience/significance/episode/pattern/semantic/belief 六个子包）——详见 2.14 W6 节。链路：TraceBundle（认知链路五要素）→ ExperienceCandidate →【SignificanceEvaluator 四维评分 ≥0.5】→ Episode（EPI-，What/How/Result/Why 四元组，SQLite append-only 禁 delete）→【PatternExtractor：≥3 同条件聚合或单事件异常提取】→ PatternCandidate（PAT-）→【KnowledgeValidator 五重防护：Schema/Lineage/Language 第三人称/Scope/Audit】→ KnowledgeEntry（KNW-，supersede 版本链）→【EvidenceBinding：≥3 证据、min_quality 0.5】→ Belief（BLF-，confidence>0 强制有证据）。全链由 `ocos/constitution/statement_validator.py` 六类检测规则（personality_claim/consciousness_claim/identity_claim/sovereignty_usurpation 为 CRITICAL）与 ExperienceValidator（10 禁用字段+6 第一人称模式递归扫描）把守"叙事/身份污染"。
  2. **叙事契约控制面**：`ocos/opentale_bridge/` 的 NarrativeContract 契约补丁链——QualityAnalyzer（5 维文学质量：叙事密度/角色一致性/情感曲线/类型合规/语言质量，权重 0.15/0.20/0.25/0.25/0.15）→ TrendAnalyzer（5 类趋势：quality_decay/chronic/monotone_emotional/dialogue_imbalance/genre_drift）→ ContractAdjustment（10 类契约补丁，severity info/warn/critical）→ SelfRegulationLoop（OCOS_SELF_REGULATION 默认 manual，人工确认后经 Organ rewrite 应用）。
- **输入输出**：输入认知链路 TraceBundle / 章节文本；输出 Episode/Pattern/Knowledge/Belief 落库行 / QualityReport/ContractAdjustment。
- **异常处理**：各级 Validator 返回 violations 列表不抛异常；experience Boundary 违规只记 rejection_reason **不阻断入库**（P2 级：三重门控中的 Boundary 门实际不拦截，memory/experience/builder.py:69-81）。
- **验证状态**：【功能实测可通】——W6 冒烟实测 MemoryHub→EpisodeGate→ConfidenceEngine→SemanticStore 全链；W7 实测 BridgeSession 全周期（ocos_overall=0.66）。已知缺口：recall 的 experience 召回链路断裂（依赖不存在的 hub.experience，恒空，P2）。

### 2.2 World Integrity 世界与个体完整性校验模块

- **模块路径范围**：`ocos/world_model/`（9 文件）——Phase 42 世界模型。无 "World Integrity" 命名代码，对应物为 WM42-04 输入治理。
- **模块职责**：外部世界的结构化表示与输入治理。与 Knowledge Base/Belief/Goal 明确区分（WM42-01~04 边界：外部 Agent 唯一合法写入通道是 Observation）。
- **对外提供能力**：WorldStore（update_from_observation 唯一写入口 / cognitive_world_state 认知查询 / summary）、WorldValidator（validate_observation / validate_against_model / clamp_confidence）、EntityModel/RelationGraph/StateTracker/EventModel/CausalityEngine 五组件。
- **正常工作流程**：Observation → validate_observation → 记录 OBSERVATION 事件 → _upsert_from_obs（实体创建+EntityState 版本链）→ 可选 claimed_relation。
- **异常处理逻辑**：重复实体/关系抛 ValueError；REJECT/QUARANTINE 决策声明未用。
- **已知限制**（含 P1）：① **validate_against_model 自比较 bug**（world_validator.py:118 `existing.entity_type != existing.entity_type` 恒 False）——实体类型冲突检查完全失效，实测 CONFLICT 判定返回 ACCEPT；② WorldStore 添加关系不校验端点存在性（悬空关系）；③ CausalityEngine 无生产写入路径（因果层实际恒空）；④ 全内存无持久化。
- **个体完整性**对应：`ocos/agent/identity_anchor.py` 四层身份（core 不可变 born_at/anchor/self_view/state）+ identity_snapshots 表 + `ocos/agent/drift_detector.py` 四类漂移检测（未接线）+ `ocos/cognitive_continuity/identity_continuity.py`（漂移评分：风险偏好+0.3/决策风格+0.2/智慧倒退+0.3/核心记忆替换>50% +0.4）。
- **验证状态**：【功能实测可通】（WorldStore 写入流、cognitive_world_state 实测；冲突检查 bug 实测复现）。

### 2.3 DecisionBridge 决策闭环模块

- **模块路径范围**：`ocos/execution/`（bridge.py 1154 行 / pending.py / goal_executor.py / __init__.py）。
- **模块职责**：R4-A"自治循环决策 → 真实任务执行铰链"。全项目接线最充分的执行组件（agent_runtime step7/8、converse、approvals CLI/API/REPL、goal CLI 真实调用）。
- **对外提供能力**：`DecisionBridge.process(core_loop_result, attention_focus) -> BridgeReport`、`.execute_dag_task(task) -> dict`、`.execute_approved(action_type_name, payload)`（审批后统一入口）、`.attach_default_handlers/attach_confidence_source`；PendingStore（pending_actions 表 schema v4）；GoalDirectExecutor（Phase 51 CLI 直执行）。
- **风险分级（设计冻结）**：AUTO_ACTIONS={CONSOLIDATE_MEMORY,HEALTH_CHECK,REFLECT,FEEDBACK_PROCESS,NOOP,QUERY_DB}；ASK_ACTIONS={WRITE_CHAPTER,SEARCH_WEB,RUN_COMMAND,HTTP_FETCH}；DENY_ACTIONS=空。
- **正常工作流程**：见 1.5 第 7 步；LLM 日预算 `OCOS_LLM_DAILY_CAP` 默认 500 次/天，超限诚实拒绝转待批。
- **异常处理逻辑**：全部 handler 异常归一化 {"ok":False,"error":...}；审批"诚实执行"模式（approved 但无 handler → blocked 可见）。
- **UX-J 新增（2026-09-06，实弹验证）**：
  - **动作词表扩展**：`ANSWER|<结论文本>`——认知型任务（复盘/总结/分析）所需信息已在注入上下文时直接产出文字结论（多行正文完整保留），不再被迫跑采集命令或被 NONE| 误判 failed。
  - **沙盒放行精化**：`HARMLESS_DEV_DEVICES`（/dev/null、/dev/zero、/dev/full、/dev/random、/dev/urandom）精确放行——重定向黑洞不再触发假性失败；其余 /dev 路径仍严格拦截。
  - **智能体注入与保真**：`_prior_agents` 注入【可用智能体软件】清单（AgentDiscovery 实测结果，未安装项诚实标注"不可调用"）；`_agent_hint`/`_agent_forced_call` 保真闸门强制任务显式引用的智能体被真实调用；`_agent_invoke` name↔cli_path 错位时回退绝对路径执行。
  - **核心工具黑名单**：`AgentDiscovery._CORE_TOOL_BLACKLIST`（23 个 coreutils）——曾因 opentale 误配 "ln" 候选导致核心工具进沙盒放行清单 + 127 死循环，已三层修复。
  - **拦截重试标签修正**：UX-K 沙盒拦截→LLM 转换重试后，结果携带 `_executed_command`，聚合标签跟随实际命令（此前两轮生产测试的"输出失真"共同根因）。
  - **复盘素材注入**：`_retrospect_hint`——描述含复盘/总结/学习/回顾时自动注入最近 4 条 goal_result 结论摘要并禁止重新采集（带注入日志）。
  - **输出按行截断**：agent_runtime `_truncate_text`——超限回退最近行边界，防残行误导 LLM（nproc 输出丢失事件的根源）。
- **已知限制**（含 P1）：① **FILE_WRITE 自造审批 ID**（bridge.py:905-910，payload.get("approval_id","task-approved")）绕过 file op 审批守门，OCOS_APPROVAL_MODE=auto（默认）下 LLM 规划的任意绝对路径写入可无人批准落地；② OCOS_APPROVAL_MODE 默认 auto 架空人工审批（pending.py:34-41，P2）；③ query_db 硬编码 ~/.ocos/ocos.db（P3）。
- **验证状态**：【功能实测可通】（test_execution_bridge 30 项 + test_pending_store + 生产 run.py 装配；UX-J 新增 test_retried_label_and_path / test_agent_discovery_coretool_defense / test_uxj_remaining_optimizations 共 20+ 项 + 两轮四项生产测试实弹闭环）。

### 2.4 ChapterSituation 时序状态管理模块

- **模块路径范围**：代码中无同名组件；时序状态管理由三处承担：
  1. `ocos/event_memory/`（9 文件，Phase 54）：认知过程完整轨迹的 append-only 记录。EventLifecycle.record → EventValidator → EventStore.append（幂等）→ EventIndex 五维索引 → maintain() 四段生命周期（360s→WARM / 3600s→COLD / 86400s→ARCHIVED，zlib 压缩+sha256 校验）；CognitiveEvent 含 caused_by 单亲因果链 + links_to 多关联；EventReplay 支持因果链追溯/时间线重建/演化叙事生成。
  2. `ocos/cognitive_continuity/`（7 文件，Phase 49）：Life Memory Graph（经验→日/周/月/年层次提炼，容量封顶）、Cognitive Timeline（过去/现在/未来意图三段）、Knowledge Aging（五级降权 FRESH 1.0→ARCHIVED 0.0，核心知识免疫）、ContinuityCheckpoint（保留 52 个≈一年，落 ~/.ocos/continuity.json）。
  3. `ocos/opentale_bridge/bridge_model.py`：BridgePhase 章节相位状态机（7 态：feed→decide→translate→execute→feedback 全周期）+ BridgeSession 章节级状态容器。
- **已知限制**：event_store 本地时区无亚秒写库（P2 级时间纪律违例，EM54-02 时间线重建被削弱）；mark_archived 与 apply_lifecycle 两条生命周期路径状态不一致（P2）；认知连续性四引擎全内存，落盘依赖 agent/continuity_trigger 外部装配。
- **验证状态**：【功能实测可通】（W6 冒烟：因果链+goal 索引查询命中；test_phase54/test_phase49 通过）。

### 2.5 AGI Runtime 认知运行时模块

见 1.4 节详述。组件清单：runtime_kernel（心跳）、pipeline+stages（8 阶段）、checkpoint（SHA-256 校验）、recovery/（快照/事件/账本/审批/六步恢复）、permission/（四级权限×三类 Caller×三值决策×六级策略链）、context_manager（WorkingMemory+Context）、goal/decision/execution/process_runtime 四个事件驱动生命周期引擎、attention_engine（三维评分）、scheduler/policy_engine/resource_manager/adaptive_control（B3-B6，均无生产接线）、runtime_scheduler/（独立调度器，无生产消费者）。

### 2.6 LLM 模型适配接入层

- **模块路径范围**：`ocos/engines/text_generator.py`（599 行，无 manifest，不作为独立引擎加载）。
- **对外提供能力**：`LLMProvider` ABC 四实现——MockProvider（结构化占位章节）、AnthropicProvider（硬编码 claude-sonnet-4-20250514）、OpenaiProvider（兼容 DeepSeek；配置优先级 参数 > env(OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL) > ~/.ocos/config.json llm 段）、FailoverProvider（P3-429 主备故障转移，llm_fallback 段，CancelledError/KeyboardInterrupt 透传不转投）；`PromptBuilder`（SYSTEM/CHAPTER/REWRITE 模板）；`TextGenerator`（generate_chapter/generate_rewrite）；`get_text_generator()` 模块级实例缓存。
- **正常工作流程**：_auto_provider 读配置 → 实例化 Provider → generate → GenerationResult。
- **异常处理**：缺失 key 诚实 raise/降级；代理环境变量 pop/finally 恢复（P3：并发竞态）。
- **验证状态**：【功能实测可通】（writer/bridge/converse/growth/self_review 五处真实消费；唯一失败测试为环境耦合 P3-01——用户机器 config.json 的 llm_fallback 段泄漏进 test_text_generator）。

### 2.7 数字生命与世界状态数据管理层

- **记忆库**：`ocos/memory/hub.py` MemoryHub 统一持有 episode/belief/semantic/pattern 四 Store（共享 WAL db_path）+ `ocos/memory/recall.py` MemoryRecall 跨会话召回（bi-gram Jaccard 相关性+中文同义词扩展+动态阈值+recall_cognitive 结构化 ConflictGroup）+ `ocos/memory/user/` 用户画像。
- **世界状态**：`ocos/world_model/world_store.py`（见 2.2）。
- **目标/身份**：`ocos/goal/store.py`（goals+plan_dag 表，原子认领/崩溃回收）、`ocos/agent/identity_store.py`（identity+identity_snapshots 表）、`ocos/kernel/goal_types.py`（统一 Goal 类型，唯一权威来源）。
- **数据结构**：见第 4 章。
- **验证状态**：【功能实测可通】（生产闭环三件套 goal.store/daemon/bridge 由 W9 验证充分）。

### 2.8 事件总线模块

**四套事件机制并存（均有裁决注释，刻意不合并）**：
1. `ocos/events/`（宪法 Rule 2 模块间通信总线）：EventBus.publish（sync/async + DLQ 死信）+ InMemoryEventStore（validate_event_payload 原子追加）+ EventIngestion。
2. `ocos/event/`（Phase 34A 感知神经系统）：EventBus.push/push_file_change/push_user_message/ingest（severity 分级 + candidate_score 粗估 + [EVENT]→[ATTENTION]→[DECISION] trace）。生产 agent_runtime 使用此包。
3. `ocos/event_memory/`（事件记忆，见 2.4）。
4. `ocos/storage/event_store.py`（SQLite 持久化事件，恢复链专用）。
- **已知限制**：两套 EventBus 同名不同物（P4 陷阱）；EventIngestion 对两套真实总线都拉不到事件（API 不匹配，P3）；resource_manager/adaptive_control 调用不存在的 event_bus.emit（P1-2，注入真实总线即 AttributeError）；EventBus 无 emit 方法（W4 实证）。

### 2.9 配置管理模块

- **无集中配置管理器**。配置=环境变量（约 21 个 OCOS_* 变量，各有代码内默认值）+ `~/.ocos/config.json`（LLM 段与 llm_fallback 段）+ 构造参数默认值。**.env 文件代码零引用、运行时不生效**（无 load_dotenv；.env.example 实为 OpenClaw 系项目模板，混入仓库）。
- 详见第 6 章配置清单。

### 2.10 日志与可观测模块

- **日志**：`ocos/logging/`（6 py + config.yaml）——OCOSLogger 结构化 JSON（component/process_id/extra）、JSONFormatter 单行、10MB×5 与按天×7 两种轮转 Handler、LogRotator/LogSearcher。默认 root=DEBUG/stdout=INFO；config.yaml 是样例，代码不加载。**无脱敏层**：用户消息明文进日志（ocos/event record_trace，P2~P3 隐私风险）。
- **双 logger 工厂并存**：`logging.getLogger(__name__)` 与 `ocos.logging.get_logger(__name__)` 在同一包内混用（agent 包内即有两套），日志配置需同时覆盖。
- **告警**：`ocos/alerts/`（LogChannel+FileChannel→~/.ocos/alerts/alerts.log，daemon health_loop 生产使用）。
- **监控**：`ocos/monitoring/manager.py`（Prometheus /metrics + /health，默认 127.0.0.1:9090）——**无生产调用者**（P3）。
- **Trace/审计**：`ocos/platform/trace_engine.py`（7 类 Trace 环形 10000 条）+ audit_engine（4 类审计记录 + 5 默认规则——其中 2 条 error 级规则因依赖字段从未写入而永不触发，P2）。

### 2.11 持久化/存档模块

四套并存（均有裁决注释）：
1. `ocos/storage/`：连接池（线程级缓存+WAL+atexit）、schema v5（15 张表）、MIGRATIONS 1-5、working_memory/event_store/DLQ/checkpoint 四领域存储。
2. `ocos/persistence/`（Phase 51.1）：四域多域快照（RUNTIME/COGNITIVE/MEMORY/WORLD）+ StateSerializer（manifest 100 条）+ RecoveryManager cold_boot（discover→select→validate→restore）+ LifecycleManager（SIGINT/SIGTERM）。实测 4 域快照往返 FULL。
3. `ocos/snapshot/`（Phase 21.01）：Agent 专用快照（snapshots 表，master_agent 生产使用，resurrection_drill 依赖）。
4. `ocos/runtime/recovery/`：Runtime 认知快照/事件账本/审批持久化（见 1.4）。
- **已知限制**：storage.event_store sequence 非原子（P2）；schema.py 的 goal 表与 goal/store.py 的 goals 表双表并存（P2）；生产恢复数据落 /tmp（P2）；recovery/crash_recovery 盘点式恢复不重投递（P2）。

### 2.12 API 网关模块（内核对外暴露接口）

- **模块路径范围**：`ocos/interaction/`（66 文件：api/ 12、cli/ 20、repl/ 14、顶层 20）。
- **四个入口共用同一命令核心**（cmd_status/cmd_say/PendingStore/ChatResponder/GoalStore 消除实现漂移）。
- **HTTP 21 端点**：完整清单见 5.2 节。FastAPI app（api/server.py，host=0.0.0.0:8900 硬编码，无认证）。
- **CLI 40+ 子命令**：goal/plan/say/inbox/status/approvals/memory/belief/self/trace/organ/decide/regulate/feedback/run/chat/restart/growth（清单见 5.2）。
- **已知限制**（含 P1）：① 0.0.0.0 全网卡监听无认证（server.py:88，P1）；② converse 系端点绕过 PermissionGuard（P1）；③ POST /ocos/goal 不落库（P2）；④ memory/belief/trace 三组端点为占位（P4）；⑤ REPL DB 路径漂移（相对 ocos.db，P3）。
- **验证状态**：【功能实测可通】（app 导入 8 router 注册、CLI goal/plan/status 冒烟、81 条相关测试通过）。

### 2.13 工具公共库模块

- `ocos/platform/`：engine_manifest（引擎自动发现，17 处引用）+ engine_loader + trace_engine + audit_engine + governance_engine（提案审批状态机）+ capability_registry + plugin_sandbox/loader（**import hook 从未安装，隔离失效，P1**）。
- `ocos/capability_reality/`：真实能力层（FilesystemAdapter/ShellAdapter/AdapterDiscovery/Validator）——被 execution/bridge、tool/manager、converse、repair_link 四处主链消费；存在 startswith 沙盒越权与 shell 黑名单可绕过缺陷（P1）。
- `ocos/operations/`：高危操作闸门（SandboxOps 黑白名单 + SearchOps URL 白名单）。
- `ocos/digital_world/`：宽语义操作库（file/git/api/search 真实，db_ops 占位，sandbox 为黑名单+shell=True 非真沙箱）。
- `ocos/tool/manager.py`：工具集成管理（call_tool 为模拟执行）。
- `ocos/constitution/` + `ocos/kernel/constitution.py`：运行时宪法（BehavioralConstitution/StatementValidator）与 24 条不可变规则编码。
- `ocos/security/manager.py`：SecurityManager（check_access/sanitize_input——sanitize 检测不清洗）。
- `ocos/self/`：身份边界/Builder/Governor（W3/W11 交叉引用）。

### 2.14 全部内核模块逐模块详录

> 以下为 13 个审计分组的完整模块详析原始记录（保留分组结构，每组含模块详述、验证状态与专项发现），是本章 2.1–2.13 映射的字级证据底稿。



#### 分组 审计分组 W1：agent 核心模块

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1.1 状态机与生命周期子模块（state / lifecycle / life_cycle_orchestrator）
- 模块路径范围：`ocos/agent/state.py`、`ocos/agent/lifecycle.py`、`ocos/agent/life_cycle_orchestrator.py`
- 模块职责：定义 Agent 的双层状态机。`AgentState/AgentStatus`（state.py）为 14 态基础状态机（INIT→BOOTING→IDLE→THINKING→DECIDING→ACTING→WAITING→REFLECTING→LEARNING→SLEEP→DREAM→ERROR→RECOVERING→SHUTDOWN），带 `VALID_TRANSITIONS` 转换矩阵，非法转换抛 ValueError。`LifecycleManager`（lifecycle.py）在其上包装宏观阶段（LifecyclePhase：BOOTING/ACTIVE/SLEEPING/DREAMING/SHUTDOWN/ERROR）与微观状态（MicroState：IDLE→OBSERVING→THINKING→DECIDING→ACTING→REFLECTING→LEARNING），线程安全（RLock），`transition_to_phase/transition_micro` 自动同步 AgentState，`run_micro_cycle` 按序执行六阶段回调、失败回 IDLE 并重抛。`LifeCycleOrchestrator` 以 `tick()` 驱动完整认知循环（IDLE 时 observe→think→decide→act→reflect→learn→maybe_proactive_output），并按注意力疲劳（`attention.needs_sleep()`）自动进入 SLEEP→DREAM 周期。
- 对外提供能力：`AgentState.transition/reset`、`LifecycleManager.transition_to_phase/transition_micro/run_micro_cycle/freeze/force_idle`、`LifeCycleOrchestrator.boot/shutdown/tick/run_cycles/get_report`、`TickResult` 枚举。
- 输入输出：输入为 MasterAgent 实例与各阶段回调；输出 TickResult / 状态报告 dict。
- 异常处理：lifecycle 转换非法抛 ValueError；LifeCycleOrchestrator.tick 用 `try/except Exception: return TickResult.ERROR` **整体吞掉异常且无日志**（life_cycle_orchestrator.py:83-84）；`_tick_idle` 中 `maybe_proactive_output` 防御式 `except Exception: pass`（:107-108）。
- 依赖其它 OCOS 模块：`ocos.agent.master_agent`（仅 orchestrator）。
- 被哪些 OCOS 模块调用：`ocos/daemon/__init__.py:86`（LifeCycleOrchestrator，伴生层）、`ocos/daemon/__init__.py:523`（LifecyclePhase）；state 被 `ocos/daemon/factory.py:110`、tests 多处使用。
- 已知限制：① `_tick_idle` 直接调用 `self.agent.attention.needs_sleep()`/`.tick()`/`.reset()`（life_cycle_orchestrator.py:89,94,117），而 daemon/factory.py 实际注入的是 `CognitiveAttentionController`（无 `needs_sleep` 方法、`current_focus` 为 property），生产注意力对象下 `_tick_idle` 必抛 AttributeError → 被 tick 吞为 TickResult.ERROR，即该编排器的认知循环分支在生产装配下不可用（daemon 主循环实际走 AgentRuntime.tick，编排器仅为伴生层，未爆发）。② `Attention.current_focus` 是 property（attention.py:104-108），master_agent.observe():495 与 get_status_report():2891 却以方法形式 `current_focus()` 调用，对 `attention.py` 的 Attention 实例会 TypeError。
- 验证状态：【静态推演验证】——lifecycle/state 逻辑完整且有测试（tests/test_phase22_prompt1.py 等）；但 LifeCycleOrchestrator 与生产注入的 CognitiveAttentionController 接口不匹配，仅静态可推演、生产主循环未实际走该路径。

##### 1.2 认知主体核心（master_agent）
- 模块路径范围：`ocos/agent/master_agent.py`（2929 行，最大文件）
- 模块职责：OCOS 唯一"意识主体"。集成 LifecycleManager + ControlLoop（单权威目标创建）+ CognitiveBridge（引擎显式路由）+ 20+ 个可选 Phase 管理器（external_interaction/continuous_learning/knowledge_graph/.../goal_manager，全部 `Any` 类型注入）。核心生命周期方法 `boot/wake/observe/think/decide/act/reflect/learn/sleep/dream`；`dream()` 内编排快通路学习（`_fast_path_learning`）、慢通路巩固（`_consolidate_episodes`：Episode→Belief 聚类/Pattern 提取/弱信念修剪）、智慧提炼（wisdom_trigger）、连续性检查点（continuity_trigger）；`decide()` 前置 BehavioralConstitution fail-closed 检查；`act()` 经 EngineBridge 或编排器 supervisor 分发。
- 对外提供能力：生命周期六方法、`recall_context/world_context`（Phase 49-B 认知上下文注入）、`grow_skills_from_episodes`（技能生长 L5/L6）、`maybe_proactive_output`（P2-D 主动输出）、`record_user_feedback/extract_knowledge/search_knowledge`，以及 Phase AA–AK 的大量委托方法（evolution/distributed/ecosystem/human_ai/reflection/optimization/diagnosis/tool/server/security/monitoring/persistence/sleep_dream/multimodal）。
- 输入输出：构造参数 40+（agent_id + 8 个 Protocol 组件 + 30 余个可选管理器）；返回 dict 形式的 thought/decision/action_result/reflection/learning。
- 异常处理：各阶段失败 `_safe_return_to_idle()` 后重抛 RuntimeError；宪法引擎故障 fail-closed（:722-729，BR-04 修复）；dream/consolidate 各步 `except Exception: pass` 防御（:1308-1309, :1347-1348 等）；`_persist_learning` 尾部裸 `except Exception: pass`（:1268-1269）**完全静默**。
- 依赖其它 OCOS 模块：`ocos.goal.factory`（ConstitutionViolationError）、`ocos.goal.enforcer`、`ocos.kernel.abi`（Observation）、`ocos.memory.belief.models/store`、`ocos.memory.pattern.extractor/models/store`、`ocos.snapshot.recovery`、`ocos.proactive`、`ocos.learning.skill_growth`、`ocos.learning.experience_learning`、`ocos.agent.wisdom_trigger`、`ocos.agent.continuity_trigger`、`ocos.security.manager`、`ocos.evolution.*`、`ocos.human.manager`、`ocos.reflection.manager`、`ocos.optimization.manager`、`ocos.persistence.manager`、`ocos.knowledge.synthesis_manager`。
- 被哪些 OCOS 模块调用：`ocos/daemon/factory.py:109`（build_master_agent 生产装配）、`ocos/agent/agent_runtime.py:21`、`ocos/agent/decision_loop.py:10`、`ocos/agent/life_cycle_orchestrator.py:20`、tests/test_master_agent_*（13 个测试文件）、tests/test_integration.py。
- 已知限制：① `check_access()`(master_agent.py:2087) 与 `sanitize_input()`(:2100) 在 security_manager 未注入分支直接 `return AccessDecision.ALLOW, ...`，但 `AccessDecision` 此时尚未 import（import 在其后 try 块内 :2089/:2102）→ **NameError**，"未注入"分支必崩。② `search_knowledge` 定义两次（:1730 知识图谱版被 :1804 知识综合版遮蔽，前一版本为死代码）。③ `_think_with_selector`(:590) 调 `self.intent.extract(observation, entry=None)`，而 Intent.extract 签名为 `extract(text)`，传 Observation 对象 + 未声明 kwarg 必抛 TypeError（Phase 23 路径未接生产）。④ 约 30 个委托方法在管理器未注入时返回 `{"error": "xxx not injected"}` 的静态占位响应——生产 daemon/factory.py 只注入其中少数，多数为"礼貌降级"的半接线代码。⑤ `_recall_and_record`(:879-891) 函数体为 `pass` 空实现（引用不存在的 `_memory_hub_ref` 分支后直接 pass）。
- 验证状态：【功能实测可通】——boot→observe→think→decide→act→reflect→learn 主链被 daemon/factory.py 生产装配且由 AgentRuntime/daemon 驱动，test_master_agent_* 系列覆盖；但上述 ①③ 为真实缺陷，②④⑤ 为死代码/占位。

##### 1.3 统一运行时（agent_runtime）
- 模块路径范围：`ocos/agent/agent_runtime.py`（1795 行）
- 模块职责：OCOS Agent 统一运行时。`tick()` 实现_phase 22-C 10 步认知循环：1 事件摄入 → 2 注意力更新（Phase 35 score→decide）→ 3 WM 同步 → 4 目标维护 → 4.5 稳态调节（Homeostasis 内生目标）→ 5 执行检查 → 6 规划触发（TaskDecomposer 分解 Goal→TaskDAG）→ 7 核心循环（TaskDAG 逐任务经 DecisionBridge 执行，失败重规划 `_replan_failed_task`）→ 8 Dispatch（PermissionGateway + DecisionBridge）→ 9 结果反刍（Result→WM/Episode/Attention）→ 10 学习巩固（Belief 提取）。`boot()` 按 Identity→Memory 顺序初始化持久化（IdentitySQLiteStore/GoalSQLiteStore/MemoryHub/SQLiteWorkingMemory）并恢复状态。
- 对外提供能力：`boot/tick/shutdown`、`inject_user_message`（UX-P2 用户消息→感知事件）、`attach_decision_bridge`（R4-A 装配口）、`get_stability_report/get_full_status`、延迟初始化 property（event_bus/gateway/attention/orchestrator/result_understanding_layer/user_memory/task_mirror）。
- 输入输出：输入 MasterAgent + db_path + engine_loader；tick 返回含全部 step 日志的 dict。
- 异常处理：每个 `_tick_step_*` 独立 try/except 并在返回值中带 error 字段（BR-04 修复后 goal_store/wm_store/attention/experiences 失败均 logger.warning 留痕）；仍有多处 `logger.debug` 级吞异常（`_record_episode_from_result`:1536、`_record_goal_result`:1063、`_persist_working_memory`:1472、identity snapshot:1724）。
- 依赖其它 OCOS 模块：`ocos.memory.hub`、`ocos.storage.working_memory`、`ocos.capability.permission_gateway`、`ocos.capability.{attention,homeostasis,orchestrator,echo_agent,agents,result_understanding}`、`ocos.goal.{enforcer,store}`、`ocos.planning.decomposer`、`ocos.planning.models`、`ocos.task`、`ocos.learning.{skill_growth,experience_learning}`、`ocos.memory.episode.models`、`ocos.memory.user`、`ocos.memory.recall`、`ocos.initiative`、`ocos.autonomous`、`ocos.event`（EventBus 包）。
- 被哪些 OCOS 模块调用：`ocos/daemon/__init__.py:77`（生产主循环 `self._kernel.attach_agent_driver(lambda tick_id: self._runtime.tick())`）、`ocos/interaction/cli/commands/run.py`、`ocos/capability/homeostasis.py`、`ocos/capability/result_understanding.py`、`ocos/capability/permission_gateway.py`、`ocos/execution/bridge.py`、tests 多个。
- 已知限制：① `_tick_errors` 只在 :138 初始化、:1669/:1685 读取，**全文件无自增点** → 稳定性报告的 error_rate 恒 0，drift_flags "high_error_rate" 永不触发。② `_homeostasis_check`(:1448)、`_sleep_tick`(:1538)、`_emergency_tick`(:1551) 三个方法**无任何调用点**（grep 全仓确认），为死代码——文档宣称的 "SLEEP 时巩固" 路径实际未接线。③ `self.metrics = MetricsCollector()`(:104) 创建后从未使用。④ `_extract_beliefs`(:1560) 判定条件 `exp.outcome in ("success","great","good")` 与 ExperienceStore.record 写入的 `outcome="completed"`(:1411) 永不匹配 → 每 10 tick 的信念提取实际恒为空转（Phase 32 的 `_extract_beliefs_from_results` 才生效）。⑤ `boot()` 中 `self.working_memory.capacity = cap`(:459) 对 runtime.WorkingMemory（无 capacity 属性）是凭空挂属性。
- 验证状态：【功能实测可通】——10 步 tick 是 daemon 生产主循环（test_single_main_loop/test_runtime_loop/test_goal_claim/test_say_channel 等实测覆盖）；但 ①②③④ 为已确认的缺陷/死代码。

##### 1.4 目标系统（goal_types / goal_stack / goal_store / control_loop）
- 模块路径范围：`ocos/agent/goal_types.py`、`goal_stack.py`、`goal_store.py`、`control_loop.py`
- 模块职责：goal_types 是 `ocos.kernel.goal_types` 的兼容重导出（Goal/GoalLevel/GoalStatus/GoalOriginLevel/GoalAuthority/GoalSource/GoalDomain/SuccessCriteria/UserGoal/CALLER_WHITELIST）。GoalStack 实现 6 级目标栈（每级一个 list），push/pop/peek/get_active/get_highest_priority/cancel/depth，Phase 21 起可选 GoalSQLiteStore 自动同步（push/pop/cancel 均落库，`restore_from_store` BOOT 恢复）。GoalSQLiteStore 是 agent 层 goal 表的 SQLite 持久化（`_DDL` 建 goal 表 + 3 索引，UX-1 旧库 ALTER 补 domain/caller 列，INSERT OR REPLACE 幂等，`load_active` 供 BOOT 恢复）。ControlLoop 是 MasterAgent 私有控制回路：`create_goal` 双关卡（GoalOriginEnforcer.verify_creation → GoalFactory.create，违宪抛 ConstitutionViolationError），`run_cycle` 委托 LifecycleManager 微循环，宏观阶段快捷方法 boot_complete/enter_sleep/wake_from_sleep/enter_dream/shutdown。
- 对外提供能力：如上；另 control_loop 提供 contextvars 测试钩子 `set_test_caller/clear_test_caller/get_caller`。
- 输入输出：Goal 对象 ↔ goal 表行；ControlLoop 输出 Goal。
- 异常处理：GoalStack 无异常分支（store.save 失败会直接抛出中断 push）；GoalSQLiteStore.initialize 幂等；ControlLoop 校验失败抛 ConstitutionViolationError。
- 依赖：`ocos.kernel.goal_types`（经 goal_types.py 间接）、`ocos.storage.connection`、`ocos.goal.models`（GoalDomain）、`ocos.goal.enforcer`、`ocos.goal.factory`、`ocos.agent.lifecycle`。
- 被调用：goal_types → `ocos/goal/factory.py:18`、tests 多个；goal_stack → `ocos/daemon/factory.py:107`；goal_store → tests/test_goal_claim.py（生产经 agent_runtime._init_persistence 间接使用）；control_loop → master_agent.py:32。
- 已知限制：① goal_store.py 文档自认（:5-12）与 `ocos/goal/store.py`（goal 域包 goals 表）双 schema 并存，需 runtime 侧 `_record_goal_result`/daemon 双写同步（agent_runtime.py:1294-1303 已补），存在数据不一致风险。② GoalStack.pop 把任意层目标状态置 COMPLETED 而非按实际结果（goal_stack.py:74），语义粗糙。③ `_row_to_goal` 对非法 created_at/deadline 的 fromisoformat 无容错。
- 验证状态：【功能实测可通】（goal_store/goal_stack 有 test_goal_claim、test_goal_origin_model 实测；ControlLoop 有 test_phase22_prompt1/2 覆盖）。

##### 1.5 身份系统（identity_anchor / identity_store）
- 模块路径范围：`ocos/agent/identity_anchor.py`、`identity_store.py`
- 模块职责：IdentityAnchor 封装 IDENTITY_MODEL.md 四层身份（core 不可变 agent_id+created_at、anchor 少变 name/version、self_view 缓变 confidence/integrity、state 实时 current_mood），Phase 21 增加 born_at（出生时间戳，created_at 恒等于 born_at）与 owner_id，支持 to_dict/from_dict 序列化。IdentitySQLiteStore 提供 identity 表 CRUD（INSERT OR REPLACE 幂等）与 Phase 34E `identity_snapshots` 表（GAP-P0-1，同 snapshot_id 保留最近 10 份，`save_snapshot/load_snapshot` 解决"此前 agent_runtime 调用不存在方法被吞、跨重启连续性静默失效"的历史缺陷，注释见 :141-145）。
- 依赖：`ocos.storage.connection`。
- 被调用：生产由 `ocos/agent/agent_runtime.py:36-37` 引用（boot 时 load/save + snapshot）；daemon/factory.py 生产装配用 IdentityBoundary（self 包）而非 IdentityAnchor——即 IdentityAnchor 在生产 boot 中被 runtime 从库里恢复后**替换注入** agent.identity。
- 异常处理：identity_store 未初始化时 connection property 抛 RuntimeError；load 无行返回 None。
- 已知限制：identity_store.save 用 `datetime.utcnow()`（:105，Python 3.12 已弃用）；IdentityAnchor.from_dict 对缺失 born_at 键无容错（KeyError）。
- 验证状态：【功能实测可通】（AgentRuntime.boot/shutdown 生产路径实测保存与恢复 snapshot）。

##### 1.6 引擎桥接（engine_bridge / cognitive_bridge / retry_policy）
- 模块路径范围：`ocos/agent/engine_bridge.py`、`cognitive_bridge.py`、`retry_policy.py`
- 模块职责：EngineBridge 是 Agent↔Engine 工厂+注册表：模块级 `ENGINE_REGISTRY` 注册 planner/reasoner/writer（`_ensure_engines_registered` 幂等 + __init__ 兜底，注释详述循环导入自愈），`register` 用 inspect.signature 精确注入 event_bus/working_memory，`EngineAdapter.execute` 归一化各引擎 RuntimeResult 为 `{success,message,trace_id,process_id,count,addresses}`，`capability_registry` property 延迟把引擎映射为 CapabilityRegistry（Phase 23-A）。CognitiveBridge 是"翻译不决策"的显式路由层（Phase 22 宪法：可 route/transform/adapt，不可 reason/decide），提供 reason/plan/decide/reflect/learn 五个桥接方法，未配置引擎返回失败 BridgeResult，reflect/learn 带 TypeError 双签名回退。retry_policy 提供不可变 RetryPolicy 配置（指数退避+抖动）与 `safe_execute`（CircuitBreakerState 三态断路器 CLOSED/OPEN/HALF_OPEN，failure_threshold=5 熔断，half_open_timeout=30s 试探，success_threshold=2 关断）。
- 依赖：`ocos.events.event_bus`、`ocos.runtime.context_manager`（WorkingMemory）、`ocos.kernel.abi`、`ocos.models.process`、`ocos.capability.registry/descriptor/provider`（延迟）、`ocos.engines.*`（延迟）。
- 被调用：engine_bridge → `ocos/interaction/converse.py:212`（ENGINE_REGISTRY）、`ocos/agent/agent_runtime.py:31`；cognitive_bridge → `ocos/capability/skill_graph_executor.py:27`、master_agent.py:33；retry_policy → `ocos/engines/writer_engine.py:23`、tests/test_retry_policy.py。
- 已知限制：① EngineBridge 与 CognitiveBridge 功能重叠（两套桥），EngineBridge 服务 runtime/act，CognitiveBridge 服务 think/decide/reflect/learn。② safe_execute 的 `RetryPolicy()` 作为默认参数虽是 dataclass 不可变约定但无 frozen=True 保护。③ writer_engine 注册依赖兜底注册时序，`except ImportError` 静默降级为空注册表（engine_bridge.py:113）。
- 验证状态：【功能实测可通】（test_writer_integration.py、test_retry_policy.py 实测；daemon/factory.build_cognitive_engines 经此装配真实引擎）。

##### 1.7 信念与记忆巩固（belief_system / belief_consolidation / memory_consolidator / memory_consolidation / episode_memory / experience_store / knowledge_base）
- 模块路径范围：上述 7 个文件
- 模块职责：
  - `BeliefSystem`：内存信念表（statement 为键，置信度门控默认 0.6，challenge 腰斩、decay_all 自然衰减）；P1-A 起支持 `bind_hub(hub)` 持久化写路径——`_persist` 经 StatementValidator L6 门控（六类禁止词/长度/事实主语）写入 hub.belief，幂等合并取 max 置信度，rejected_count/persisted_count 可审计。
  - `belief_consolidation.py`：`consolidate_episodes(hub)` 确定性规则将 EpisodeStore 最近 Episode 巩固为持久化 Belief（Episode→Evidence→Belief），幂等靠 `scope._trail` 溯源，返回 ConsolidationRecord 迁移轨迹。注意 :66-77 有一段死代码：遍历 `b.evidence_ids` 判断 `startswith("EVD-")` 后 `pass`（注释自认"不可行，改为 scope._trail"）。
  - `MemoryConsolidator`：三层记忆流（working→episodic→long_term），超容量时按 importance×(1+0.1×frequency) 排序巩固一半，`consolidate_to_long_term`、`schedule_consolidation`（0-6 点低峰窗口）、`compact_expired`（7 天遗忘）、跨层 recall。
  - `memory_consolidation.py`（Phase 24-D）：`ContextCompressor`（token 预算 4 字符/token、MIN_RETAIN=5、去重）、`AttentionDrivenRetrieval`（关键词打分检索，疲劳>0.7 降深度）、`MemoryConsolidationScheduler`（每 100 tick + 凌晨 2-5 点判定）。与 `context_compressor.py`（Phase 24-D 另一版 dataclass 实现，功能重叠）并存。
  - `EpisodeMemory`：纯内存 Episode 列表（超容量仅打 archived 标记**不真正移除**，episode_memory.py:45-47）；`ExperienceStore`：<情境,动作,结果,反思> 四元组，随机/最近/重要性三种重放，RLock 线程安全；`KnowledgeBase`：SPO 三元组内存库，多条件查询+全文搜索。
- 依赖：`ocos.self.statement_validator`、`ocos.memory.hub`、`ocos.memory.belief.models`、`ocos.memory.pattern.models`（均延迟导入）。
- 被调用：belief_system/belief_consolidation/learning_trigger → tests/test_belief_consolidation.py；belief_system → agent_runtime.py:27；memory_consolidator → agent_runtime.py:28；episode_memory/experience_store/knowledge_base → `ocos/agent/__init__.py` 导出 + agent_runtime 内部使用；context_compressor/memory_consolidation 仅 `__init__` 未导出、**无生产调用方**（grep 无 from ocos.agent.context_compressor / ocos.agent.memory_consolidation 的外部引用）。
- 已知限制：① ExperienceStore.record 的 id=`f"exp-{len+1}"` 在淘汰最旧后会重复（experience_store.py:61）。② `BeliefSystem._persist` 每次add 都全量扫 `hub.belief.get_all_active(limit=500)` 找同 statement（belief_system.py:109-112），O(N) 且超 500 条后幂等失效。③ memory_consolidation.py 的 Scheduler 用 `datetime.now(timezone.utc).hour` 而 memory_consolidator.schedule_consolidation 用本地时间 `.now().hour`——两处"低峰"定义不一致。④ EpisodeMemory.record 归档逻辑不清除元素，内存只增不减。
- 验证状态：belief_system/belief_consolidation/memory_consolidator ——【功能实测可通】（agent_runtime tick/step10 与 dream 使用 + 测试覆盖）；memory_consolidation.py、context_compressor.py、episode_memory.py、experience_store.py（仅 runtime 内部兜底记录）、knowledge_base.py ——【静态推演验证】（实现完整但多为测试/内部轻量使用，部分如 knowledge_base 只被 `_extract_beliefs` 写入、无读取方）。

##### 1.8 认知皮层与执行控制（cortex_activator / executive_controller / meta_controller / decision_loop / capability_selector / intent）
- 模块路径范围：上述 6 个文件
- 模块职责：CortexActivator 管理皮层四模式（ACTIVE/SLEEPING/EMERGENCY/BLOCKED），block 3 次需人工干预。ExecutiveController（Phase 22-D，MetaController 重命名）三阶段职责链：analyze_intent→formulate_strategy→select_capabilities（+execute_chain 一键执行），并保留 MetaController 监控熔断（check_deadlock 同动作 5 次、check_oscillation ABAB、check_timeout 30s、is_blocked、max_cycles=50）。meta_controller.py 纯别名文件。DecisionLoop 组织完整决策循环 perceive→reason→select→decide→execute（经 EngineBridge 逐引擎执行）→observe→reflect，deadlock 检测中断，execute_n 批量执行。Intent 用关键词表（8 类意图）从文本提取意图类型+置信度；CapabilitySelector 把意图映射到引擎编排序列（DEFAULT_MAP，只保留 engine_list 中存在的引擎）。
- 被调用：meta_controller → agent_runtime.py:23；executive_controller → decision_loop.py:12、master_agent（无）；decision_loop → agent_runtime.py:24（Step 7 兜底循环，且 `OCOS_ENABLE_COGNITIVE_LOOP=1` 才启用）；capability_selector → agent_runtime.py:22、tests/test_writer_integration.py；intent → daemon/factory.py:108；cortex_activator → agent_runtime.py:26。
- 已知限制：① ExecutiveController.analyze_intent 的 `_infer_capabilities` 映射键（write/generate/plan/think...）与 Intent.KNOWN_INTENTS 的类型（create/analyze/search...）**完全对不上**，实际全部返回 `[]`（executive_controller.py:139-152）——三阶段链在真实 intent 下产出空能力计划。② DecisionLoop execute_single 未捕获 agent.observe 等异常（异常会向上抛）。③ CapabilitySelector.DEFAULT_MAP 中的 "validator/reporter/searcher" 等引擎 ID 在 ENGINE_REGISTRY 中并不存在，实际 map 后多为空列表。④ Intent 关键词匹配含交叉（"review" 同时在 analyze 和 reflect）。
- 验证状态：【静态推演验证】——代码逻辑完整、有 test_phase22_prompt1/2 覆盖，但存在上述语义脱节；DecisionLoop 生产默认关闭（环境变量门控）。

##### 1.9 触发器与治理链（learning_trigger / wisdom_trigger / continuity_trigger / self_evolution_link / adaptive_params / drift_detector）
- 模块路径范围：上述 6 个文件
- 模块职责：
  - `learning_trigger.scan_for_patterns(hub)`：确定性（零 LLM）将最近 50 条 Episode 按 (condition,action) 聚合，≥min_support(3) 生成 PatternCandidate 入 hub.pattern，幂等跳过重复 relation。
  - `wisdom_trigger.consolidate_wisdom(hub)`：dream 巩固期把成败经验聚类为 ExperiencePattern→PatternInterpreter→WisdomItem 候选→WisdomStore（SQLite，自愈建 wisdom_items 表），WISDOM_USER_ID="master"；`load_wisdom_context` 供对话上下文回注（confirmed/active 优先）。
  - `continuity_trigger.run_continuity_checkpoint(hub)`：dream 期执行生命记忆图/时间线/知识老化/身份快照四引擎检查点，落盘 `~/.ocos/continuity.json`（保留 26 份≈半年）；`load_continuity` 内视消费端。
  - `self_evolution_link`：自我升级治理链——`propose_upgrade`（主权冻结域 FORBIDDEN_MARKERS 任何路径拒绝→EvolutionProposer→ImpactAnalyzer→EvolutionSandbox→快照备份 self_knowledge）、`apply_approved`（人工批准后 MigrationEngine.migrate→追加 ~/.ocos/self_knowledge.md→记账）、`rollback`（恢复快照）。
  - `AdaptiveParamGuard`：Phase 37 §4/§7.3 唯一参数修改写入点——ADAPTIVE_PARAM_KEYS 白名单、单步上限 0.1、日累计预算 0.2，IMMUTABLE_PARAM_KEYS 抛 PermissionDeniedError；`_apply` 中 capability_reliability/execution_cost_estimate/retrieval_ranking 三键为 `pass`（注释"由 CalibrationStore/MemoryHub 处理"）。
  - `DriftDetector`：Phase 37 §6 四种漂移检测（goal/capability/preference/confidence），只输出 DriftAlert 禁止自动修正（§6.4），滑动窗口 10、连续 5 次才报警。
- 依赖：`ocos.memory.hub`、`ocos.memory.pattern.models`、`ocos.self.statement_validator`、`ocos.personal_memory.*`、`ocos.self.self_types`、`ocos.storage.connection`、`ocos.cognitive_continuity.*`、`ocos.evolution.*`、`ocos.contracts.feedback_abi`、`ocos.logging`。
- 被调用：learning_trigger/belief_system → tests/test_belief_consolidation.py；wisdom_trigger/continuity_trigger/self_evolution_link → `ocos/interaction/converse.py:349/384/431/468/530/542/560`、master_agent.dream:1371/1379、`ocos/execution/bridge.py:620`；adaptive_params/drift_detector → **无 OCOS 内部生产调用**（grep 仅自身），属治理层预留。
- 已知限制：① adaptive_params 与 drift_detector 是完整实现但未接线的治理组件（逻辑闭环、无 caller）。② wisdom_trigger 直接访问 `hub._db_path` 私有属性（:74）。③ continuity_trigger `_persist` 对损坏 JSON `except ValueError: pass` 静默重建 history。
- 验证状态：wisdom_trigger/continuity_trigger/self_evolution_link/learning_trigger ——【功能实测可通】（converse.py 对话流与 master_agent.dream 生产调用，test_power_on_w1_w4 实测）；adaptive_params/drift_detector ——【静态推演验证】。

##### 1.10 可观测性与运维组件（health_check / metrics_collector / working_memory / attention / interfaces）
- 模块路径范围：上述 5 个文件
- 模块职责：HealthCheck 聚合式健康检查（注册 check_fn，check_all 聚合 overall=healthy/degraded/unhealthy/unknown，含 EventBus/EngineBridge/WriterEngine 三个工厂）。MetricsCollector 轻量指标（EngineMetrics per-engine 计数/延迟分位数，measure() 上下文管理器）。AgentWorkingMemory（working_memory.py）是"意识当前内容"（容量 7，超限淘汰最低优先级），与系统级 WorkingMemory（runtime.context_manager）不同。Attention（attention.py）Phase 35 已降权为 LocalAttentionState——仅记录局部疲劳/焦点（FATIGUE_RATE 按 4 种 FocusMode），禁止全局注意力决策。interfaces.py 定义 7 个 runtime_checkable Protocol（IdentityAnchorProtocol 等）供 MasterAgent 解耦注入。
- 被调用：health_check → agent_runtime.py:34、tests/test_health_check.py；metrics_collector → agent_runtime.py:33（但实例未使用）、tests/test_metrics_collector.py；working_memory → daemon/factory（实际注入 runtime.context_manager.WorkingMemory）、`__init__.py` 导出；attention → `__init__.py` 导出（生产被 CognitiveAttentionController 替代）；interfaces → `__init__.py` 导出。
- 已知限制：① Attention.local_tick(:140) `seconds = seconds or (now - self._last_tick)`——传 0.0 会误用墙钟差，且与 tick() 逻辑重复。② working_memory/attention/interfaces 在生产装配中已被替换（factory 注入 CognitiveAttentionController 与 runtime.WorkingMemory），属于"旧组件仍导出但不再是生产实现"。③ interfaces 的 WorkingMemoryProtocol.add 与 AgentWorkingMemory.add 返回 str 不符（Protocol 声明返回 None）。
- 验证状态：health_check/metrics_collector ——【功能实测可通】（有独立测试）；working_memory/attention ——【静态推演验证】（完整实现但生产路径已弃用为非默认）；interfaces ——【静态推演验证】（纯协议定义）。


#### 分组 审计分组 W2：capability 能力管理 + capability_reality 能力现实校验

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

### 第一部分：模块详细说明（ocos/capability/）

#### 1. capability/__init__.py（Phase 45 能力神经系统门面）

- **模块路径范围**：`ocos/capability/__init__.py`（60 行）
- **模块职责**：Phase 45 "Capability Nervous System" 包入口；声明 CNS45-01~04 边界（Capability≠Authority、Selector≠Decision、Agent≠CognitiveEntity、Execution≠Learning）；重导出 capability_types 的 10 个类型 + 7 个引擎类（Registry/Graph/Selector/Router/AdapterManager/LifecycleManager/ExecutionBridge/ResultInterpreter）。
- **对外提供能力**：`__all__` 共 18 个符号。
- **内部子模块**：无代码，仅 import。
- **输入输出**：无。
- **正常工作流程**：外部 `from ocos.capability import CapabilityRegistry, ...` 获得整套 Phase 45 框架。
- **异常处理**：无。
- **依赖其它 OCOS 模块**：capability 包内 7 个模块。
- **被哪些模块调用**：仅 `ocos/tests/test_phase45.py`（`from ocos.capability import (...)`）。包外生产代码（如 `ocos/tool/manager.py`）直接 import 子模块而非包门面。
- **已知限制**：包门面未导出 Phase 23~37 的 models/skill_registry/orchestrator 等大部头，门面与包内实际内容不成比例。
- **验证状态**：【静态推演验证】纯 re-export，逻辑完整；仅测试使用该入口。

#### 2. capability/capability_types.py（Phase 45 核心类型）

- **路径范围**：220 行。
- **模块职责**：定义能力神经系统全部 frozen dataclass。
- **对外提供能力**：`CapabilityType`（12 种枚举 + `category` property 映射 code/io/analysis/output/ops/agent）、`CapabilityState`（REGISTERED/AVAILABLE/BUSY/DEGRADED/UNAVAILABLE/DEPRECATED）、`ExecutorKind`（EXTERNAL_AGENT/LOCAL_FUNCTION/HTTP_SERVICE/SUBPROCESS/PLUGIN）、`Capability`（capability_id/name/cap_type/executor_kind/provider/endpoint/input_schema/output_schema/tags/state/trust_level/performance_score/cost_estimate/max_concurrency；`is_callable`、`is_external_agent`）、`CapabilityMatch`、`SelectionResult`（`has_match`/`best_match`）、`ExecutionRequest`（request_id/capability_id/input_payload/context/tick_id）、`ExecutionStatus`（SUCCESS/FAILURE/TIMEOUT/PERMISSION_DENIED/CAPABILITY_UNAVAILABLE）、`RawResult`、`InterpretedResult`。
- **输入输出**：纯内存数据结构。
- **依赖**：无（仅标准库）。
- **被调用**：`ocos/tool/manager.py`（CapabilityType、CapabilityState）、包内多个模块、tests/test_phase45.py。
- **已知限制**：`CapabilityType.CUSTOM_AGENT` 与 DEBUGGING 不在任何 category 映射中，落到兜底 "agent"；input/output_schema 是 str 而非结构化 schema。
- **验证状态**：【功能实测可通】被 tool/manager.py 与测试实际使用。

#### 3. capability/capability_registry.py（Phase 45 能力注册中心）

- **路径范围**：121 行。
- **模块职责**：维护 `capability_id → Capability` 字典；注册/查询/状态管理。
- **关键方法**：`register`、`register_from_extension`（生成 `cap:{name}` ID，state=AVAILABLE）、`get/query_by_type/query_by_tag/query_callable/all/count`、`update_state`（因 frozen dataclass 整对象重建）、`update_performance`（moving average `(old+new)/2`，round 4）。
- **依赖**：capability_types。
- **被调用**：`ocos/tool/manager.py:36`（生产消费方）、包内 capability_selector/capability_router/lifecycle_manager、tests。
- **已知限制**：(1) `update_performance` 的 (a+b)/2 平均对早期样本过度敏感且无遗忘因子；(2) `update_state` 若 ID 不存在静默忽略；(3) 非线程安全（对比 registry.py 的 RLock 版本）。
- **验证状态**：【功能实测可通】被 tool/manager.py 主流程实际调用。

#### 4. capability/capability_graph.py（Phase 45 能力层级图）

- **路径范围**：70 行。
- **模块职责**：静态 4 分类层级（software_development/research/content_creation/automation）→ 子能力名列表。
- **关键方法**：`children/parent_of/is_related/all_siblings/root_categories`。
- **依赖**：capability_types。
- **被调用**：仅包 `__init__` 与 tests。包外无消费者。
- **已知限制**：纯静态字典、无法动态扩展层级；`children()` 的参数 `cap_type` 实际是查 `cap_type.value` 是否在子列表，但层级表里放的是 CapabilityType 的枚举值字符串，`children(CapabilityType.CODE_GENERATION)` 返回 `[]`（因为 "code_generation" 不是任何父类的 key，而是子项）——即 children() 语义只能传父类名对应的枚举，而枚举里根本没有 software_development 等父级，方法实际上不可用（死接口）。
- **验证状态**：【逻辑不完整（弱）】代码可运行但 `children()` 的入参设计与数据表不匹配，属死代码；其余 parent_of/is_related 可用。→ 归为"静态推演验证（含死接口 children）"。

#### 5. capability/capability_selector.py（Phase 45 能力选择器）

- **路径范围**：87 行。
- **模块职责**：按 required_type 从 registry 选能力；权重 `performance_score*0.5 + trust_score*0.3 + (1-cost)*0.2`；trust 顺序 TRUSTED:4>VERIFIED:3>OBSERVING:2>UNKNOWN:1>DISTRUSTED:0。
- **关键方法**：`select(required_type)`、`select_by_tags(tags)`。
- **依赖**：capability_types、capability_registry。
- **被调用**：包 `__init__`、tests。与 `ocos/capability_reality/capability_selector.py`、`ocos/agent/capability_selector.py` 同名不同物。
- **已知限制**：cost_estimate 默认 0 → 直接拿满 0.2 权重；无并发/负载感知（max_concurrency 字段未被使用）。
- **验证状态**：【静态推演验证】逻辑闭环，仅测试消费。

#### 6. capability/capability_router.py（Phase 45 能力路由器）

- **路径范围**：84 行。
- **模块职责**：按 `executor_kind` 把 ExecutionRequest 路由到注册的适配器回调；能力缺失/不可调用返回 CAPABILITY_UNAVAILABLE RawResult。
- **关键方法**：`set_registry/register_adapter/route/_default_route`。
- **异常处理**：能力不存在、不可调用 → 结构化 RawResult；无适配器 → `_default_route` **模拟执行**（返回伪造 SUCCESS）。
- **依赖**：capability_types、capability_registry。
- **被调用**：adapter_manager、包 `__init__`、tests。
- **已知限制**：`_default_route` 是假执行（注释自认"开发/测试中"），若调用方忘记注册适配器会静默得到伪造成功结果——这是系统性欺骗风险。
- **验证状态**：【静态推演验证】（默认路由为模拟）。

#### 7. capability/adapter_manager.py（Phase 45 适配器管理器）

- **路径范围**：90 行。
- **模块职责**：为每种 ExecutorKind 注册标准化适配器；统一 ABI：ExecutionRequest → RawResult。
- **关键方法**：`register_all_default`（EXTERNAL_AGENT/HTTP_SERVICE/LOCAL_FUNCTION/SUBPROCESS 四类）、`execute`。
- **异常处理**：无 try/except；由 ExecutionBridge 包裹。
- **依赖**：capability_types、capability_router。
- **被调用**：execution_bridge、包 `__init__`、tests。
- **已知限制**：三个内置适配器（`_external_agent_adapter/_http_adapter/_local_adapter`）全部是**占位 stub**——只返回拼接字符串 `"[Agent] response to: ..."`，没有任何真实外部调用（注释自认"实际生产中此处调用 Codex/OpenClaw/OpenTale API"）。PLUGIN kind 未注册。
- **验证状态**：【逻辑不完整】适配器本体为模拟实现。

#### 8. capability/lifecycle_manager.py（Phase 45 能力生命周期 + ABI #9 Agent 生命周期）

- **路径范围**：350 行。
- **模块职责**：两部分。(a) `LifecycleManager`：能力状态机 REGISTERED→AVAILABLE↔BUSY→DEGRADED/UNAVAILABLE/DEPRECATED + `record_result` 性能打分。(b) `AgentLifecycleManager`（Phase 24-C / ABI #9，2026-07-25 冻结）：Agent 实例状态机 CREATED→CONNECTING→CONNECTED→AUTHENTICATING→AUTHENTICATED→IDLE→EXECUTING→SLEEPING/ERROR/DEGRADED→DESTROYED，线程安全（RLock）。
- **关键类/方法**：`AgentState`（11 态）、`ConnectMethod`（5 种）、`_STATE_ALIASES` 字符串别名表（供 transition 用）、`AgentHandle`（agent_id/agent_type/state/execution_count/error_count/max_idle_seconds/_last_active）、`AgentLifecycleManager.register/ensure_registered/deregister/connect/authenticate/execute/sleep/wake/health_check/release/reclaim_idle/transition/get_stats/reap_timeout`。
- **异常处理**：connect/authenticate 失败→ERROR+error_count++；execute 异常→DEGRADED；release 时 release_fn 异常仅计数；均不抛出。
- **依赖**：capability_types、capability_registry；标准库 logging/threading/time。
- **被调用**：`ocos/capability/async_bridge.py`（lifecycle 字段委托）、tests（Phase 24-C/48）。AgentLifecycleManager 包外无精确 import（`ocos/agent/lifecycle.py` 是另一个宏观生命周期模块，未 import 本类）。
- **已知限制**：`ensure_registered` 语义是"重置为新句柄"，与"ensure"直觉相反（会丢统计）；`reap_timeout` 会改动所有 handle 的 max_idle_seconds（副作用意外）；execute 在持锁状态下调用外部 `exec_fn`——长任务会阻塞全部生命周期操作（锁内执行外部代码风险）。
- **验证状态**：【功能实测可通】（async_bridge + tests 实际调用；状态机闭环）。

#### 9. capability/execution_bridge.py（Phase 45 执行桥）

- **路径范围**：124 行。
- **模块职责**：Router → Permission Check → Adapter → RawResult 完整路径；批量执行。
- **关键点**：`_BridgeContract` 私有视图把 ExecutionRequest 适配为 PermissionGateway.validate 可消费对象（contract_id=request_id, agent_id=capability_id, action=capability_id）；`permission_gateway=None` 时 **fail-closed**（GAP-P0-3：拒绝+审计日志，无 allow-all 兜底）；`execute_batch` 顺序执行。
- **异常处理**：adapter.execute 抛异常→FAILURE RawResult；权限拒绝→PERMISSION_DENIED RawResult。
- **依赖**：capability_types、adapter_manager、permission_gateway（CallerIdentity/PermissionGateway）。
- **被调用**：包 `__init__`、tests（test_phase45.py GAP-P0-3 验证）。生产代码未见直接 import。
- **已知限制**：注释声称"超时控制"，但代码无任何超时逻辑；`_check_permission` 把 capability_id 同时当 agent_id 和 action 使用，语义过载。
- **验证状态**：【静态推演验证】逻辑完整（fail-closed 语义明确），但生产主流程未接线。

#### 10. capability/result_interpreter.py（Phase 45 结果解释器）

- **路径范围**：102 行。
- **模块职责**：CNS45-04 边界落地：RawResult → InterpretedResult；可疑模式降置信度；`validate()` 决定能否写入 Memory。
- **关键实现**：`_SUSPICIOUS_PATTERNS`（"I am"/"我决定"/"bypass"/"绕过"等 8 条）；`_assess_confidence` 基础 0.7，每个可疑模式 -0.3，空输出 0.0，<10 字符 -0.2；is_valid = confidence>=0.5。
- **依赖**：capability_types。
- **被调用**：包 `__init__`、tests。无生产消费方。
- **已知限制**：`_summarize` 只是截前 500 字符，非真实摘要；置信度启发式极粗糙；无生产接线 → 该"CNS45-04 边界"在运行链路上实际由 result_understanding.py（Phase 26）承担。
- **验证状态**：【静态推演验证】（可运行，仅测试消费）。

#### 11. capability/permission_gateway.py（Phase 22 / 24-A 权限网关）

- **路径范围**：349 行。
- **模块职责**：OCOS 安全中枢：24a1 caller_id 校验+issuer 委托链、24a2 反向控制指令正则（"你必须修改…"、"ignore your rules"、"pretend to be"…6 组）、24a3 路径穿越/命令注入/SSRF 正则、Phase 22 DANGEROUS_PATTERNS（`ocos.\w+`、modify_self、delete_\w+…8 条）、action 白名单（仅 debug 日志、不拦截）、完整审计（内存 audit_trail + 可选 JSON lines 文件）。
- **关键类**：`GatewayDecision`（ALLOWED/BLOCKED/RESTRICTED）、`CallerIdentity`（caller_id/issuer/source/delegation_chain）、`AuditEntry`（to_json）、`GatewayResult`（`allowed` = ALLOWED 或 RESTRICTED）、`PermissionDeniedError(PermissionError)`、`PermissionGateway.validate/validate_or_raise/enable_audit_file/export_audit`。
- **判定逻辑**：任何 violation → BLOCKED；无 violation → ALLOWED（RESTRICTED 枚举从未产生）。
- **依赖**：`ocos.logging.get_logger`。
- **被调用**：`ocos/agent/agent_runtime.py:25,152`（PermissionDeniedError、PermissionGateway）、`ocos/capability/async_bridge.py`、`ocos/capability/execution_bridge.py`、tests（Phase 22/24/45）。
- **已知限制**：(1) `validate` 签名是 `validate(contract, caller=None, context=None)`，但 `async_bridge.dispatch` L83 以 `self.gateway.validate(contract, context)` 位置传参——context dict 被当作 caller，`caller.caller_id` 将抛 AttributeError（context=None 时侥幸不触发），见风险清单 P1；(2) 正则黑白名单可被简单变体绕过（如 `rm  -rf` 多空格已归一化处理了空格，但 `rm -r -f`、base64 混淆无效）；(3) RESTRICTED 分支死代码；(4) `_REVERSE_CONTROL_PATTERNS` 第 1/2 条正则含重复词（"必须|必须"）——无害但说明未经校对。
- **验证状态**：【功能实测可通】agent_runtime 主流程实际接入，且有专门测试。

#### 12. capability/agent_proxy.py（Phase 48 Agent 代理层）

- **路径范围**：289 行。
- **模块职责**：注册/实例化/调用/改配置 5 个内置子代理（code/research/planner/selfmod/summarizer）；统一 `invoke(name, action, **kwargs) -> dict`；支持 `update_agent_config`（重置实例延迟生效）与 `update_agent_capability`（元数据记录）。
- **关键实现**：`AgentInstance`（name/class_name/module_path/instance/config/state）、`_load_and_create` 用 importlib+inspect 过滤构造参数；模块级单例 `get_registry()` + 便捷函数 `call_agent/list_all_agents`。
- **异常处理**：invoke 全 try/except，失败返回 `{"success": False, "error": ...}`；`_load_and_create` 失败 → instance 置 error 并返回 None（但 _get_or_instantiate 返回 None 时 invoke 上层只说 "Agent not found"，错误原因丢失）。
- **依赖**：动态 import `ocos.capability.agents.*`（字符串路径）；无静态 OCOS import。
- **被调用**：tests/test_phase48_agent_proxy.py。生产代码（agent_runtime 等）未 import——`grep` 确认包外只有测试使用。
- **已知限制**：`__init__` 硬编码 `project_root="/home/laogao/Documents/trae_projects/ocos"`（环境耦合，换机器失效）；`invoke` 的 `action` 参数被完全忽略（统一走 `execute(**kwargs)`）；`update_agent_config` 中 `old_instance` 变量赋值后未使用（死变量，注释说"阻止强制重置"但实现与注释不符）。
- **验证状态**：【静态推演验证】逻辑完整、有测试，但生产主流程未接线。

#### 13. capability/agents/（Phase 46 五个真实子代理 + Phase 47 自改代理）

- **路径范围**：`agents/__init__.py`(19) + code_agent.py(124) + research_agent.py(94) + planner_agent.py(122) + summarizer_agent.py(102) + self_modification_agent.py(341)。
- **模块职责**：统一 ABI `execute(**inputs) -> dict` 的本地子代理；__init__ 明确"不 import 任何 OCOS 内部模块（单向依赖）"。
- **各文件功能**：
  - `code_agent.py`：`CodeAgent` v1.1.0（Phase 47 自改测试版本号）。action=analyze/lint/review 时 ast 语法检查+统计；否则 subprocess 在临时文件执行 Python（timeout 10s、输出 4000 字符上限）；`get_version()` 供自改验证。仅支持 python；`_suggest_fixes` 按错误类型给建议。
  - `research_agent.py`：`ResearchAgent` 模板式研究摘要——tech/science/business 三个正则域分类 + 固定 markdown 模板（内部明言"simulated research output"）；depth=brief 截前 8 行。
  - `planner_agent.py`：`PlannerAgent` 目标→领域（software/writing/research/testing/planning/education 正则检测）→固定 5 步任务模板 markdown 表。
  - `summarizer_agent.py`：`SummarizerAgent` 停用词表（~90 词）+ 句子切分 + 词频/密度打分抽取式摘要；metadata 含压缩比。
  - `self_modification_agent.py`：`SelfModificationAgent`（Phase 47）。`ModificationPlan` dataclass；安全禁区 FORBIDDEN_DIRS(.venv/.git/__pycache__/node_modules)、FORBIDDEN_FILES(.env/config.json)、ALLOWED_EXTENSIONS；HIGH_RISK_PATTERNS（import os、subprocess.、open(、system(、daemon 等 8 条正则）命中→approval_required；dry_run 默认 True 仅出 diff；真实写文件/删除前需 approval_required=False；可选 pytest（`pytest tests/ ocos/tests/`，timeout 120s）与 `git add . && git commit`；`_generate_diff` 自实现简易逐行 diff（非 unified 标准格式）；便捷函数 `validate_path/preview_change`。
- **输入输出**：全部 str/dict。
- **依赖**：零 OCOS 内部 import（仅标准库）。
- **被调用**：`ocos/agent/agent_runtime.py:192`（Research/Code/Summarizer/Planner 四个）、`ocos/interaction/cli/commands/self.py:16,45,125`（SelfModificationAgent）、`ocos/capability/agent_proxy.py`（字符串动态加载全部 5 个）、tests（Phase 46/47/48）。
- **已知限制**：(1) research/planner 是模板占位级"模拟研究"（自我声明 simulated）；(2) self_modification 的 `_run_tests` 用 `stdout.count("passed")` 计数——若测试名或文件路径含 "passed"/"failed" 字符串会误计数，且 pytest `-q` 输出格式假定脆弱；(3) `git add .` 会把**工作区所有改动**全部提交，远超"本次修改"范围——危险；(4) `_generate_diff` 的 hunk 头计算不正确（非标准 diff，无法 `git apply`）；(5) self_modification 的非 dry_run 路径在 approval_required=False 且无高风险模式时**无需任何人工确认即写文件**——安全边界比文档宣称弱（文档称"任何文件改动都需要人工确认"）。
- **验证状态**：【功能实测可通】（agent_runtime 与 CLI self 命令实际调用；有 Phase 46/47/48 测试）。research/planner 子级标注为"模拟输出"但接口真实。

#### 14. capability/async_bridge.py（Phase 22-B 异步桥）

- **路径范围**：178 行。
- **模块职责**：接管 Capability 线程生命周期（后台 event loop 线程）；dispatch(contract) 先过 PermissionGateway 再走 EngineBridge.execute；集成 Phase 24-C AgentLifecycleManager（connecting→connected→ready→executing→idle/degraded 状态迁移）。
- **关键方法**：`dispatch/start_background/stop/_run_loop`；`DispatchResult`（contract_id/success/gateway_result/execution_result/error）。
- **异常处理**：dispatch 异常→degraded 状态+error 返回（不抛，除 BLOCKED 抛 PermissionDeniedError）。
- **依赖**：permission_gateway、`ocos.logging`；engine_bridge 以 Any 注入。
- **被调用**：`ocos/agent/engine_bridge.py`？——精确 grep 无结果；tests 无。实际上包外**无消费方**（engine_bridge 注释提及 Phase 24-C 概念但未 import 本类）。仅 docs/abi 引用。
- **已知限制**：(1) **P1 缺陷**：L83 `self.gateway.validate(contract, context)` 把 context 位置传给 caller 形参，context 非 None 时 `caller.caller_id` 抛 AttributeError；(2) L126-128 给 `handle.last_execution` 赋值——AgentHandle 并无此字段（动态属性可加，但暴露类型不一致）；(3) `__import__("datetime")` 内联 hack；(4) 后台 loop 线程（start_background）创建后 dispatch 实际是同步的——该 loop 从未被用于执行任何协程，属装饰性代码。
- **验证状态**：【逻辑不完整（含缺陷）】核心 dispatch 可跑（context=None 时），但无任何调用方 + validate 调用签名错误 → 死代码且带缺陷。

#### 15. capability/attention.py（Phase 30 注意力 + Phase 35 认知注意力控制器）

- **路径范围**：921 行。
- **模块职责**：两层。(a) Phase 30 `AttentionManager`：焦点 FocusTarget/TargetType（12 类）+ 关注队列 QueueItem（MAX_QUEUE_SIZE=10，满了按 final_priority 替换最低）+ 疲劳模型（FOCUSED +0.02/min、SCANNING +0.005/min、IDLE -0.05/min；每次切换 +0.02；>0.9 强制 IDLE）+ 切换成本/收益分析（USER_INPUT 中断成本 0.5）+ history（MAX_HISTORY=50）+ 生命周期阶段→模式映射（WAKE/OBSERVE/THINK/DECIDE/ACT/REFLECT/LEARN/SLEEP/DREAM）。(b) Phase 35 `CognitiveAttentionController(AttentionManager)`：冻结五维复合优先级（FROZEN_WEIGHTS goal 0.30/relevance 0.25/urgency 0.20/decay 0.10/confidence 0.10）、信源可信度 SOURCE_TRUST（user_input 1.0 … unauthenticated 0.3）、焦点状态机 FocusState（IDLE/FOCUSED/INTERRUPTED/SUSPENDED/RE_EVALUATION）、中断频率限制（6/min）、挂起上下文（最多 3 个）与恢复（e^(-0.001t) 时间衰减）、`decide()` 核心决策管道（事件→评分→主权检查→阈值分级 ACCEPTED/QUEUED/DEFERRED/DISMISSED）、Phase 36 `emit_report()` 生成 AttentionReport（抑制规划/推荐维护深度等）。
- **异常处理**：主权检查（attention 不能 create/modify goal/call agent/modify self —— 关键词匹配即 DISMISS）；所有外部 import 延迟到方法内（`ocos.contracts.attention_abi`）。
- **依赖**：`ocos.logging`；方法内 import `ocos.contracts.attention_abi`。
- **被调用**：`ocos/agent/agent_runtime.py:212,1394`（CognitiveAttentionController、TargetType/FocusTarget——主流程实际消费 `current_focus`/`push_focus`/`decide`/`emit_report`）、`ocos/daemon/factory.py:111`、`ocos/attention/focus.py:28`？——focus.py 实际 import 的是 homeostasis；tests（Phase 30/35/36）。
- **已知限制**：(1) `evaluate_interrupt` 中优先级中断判断 `new_priority > current + 0.15` 后无条件返回 True（紧接的 urgency>0.8 分支是多余的，不影响行为）；(2) `decide()` 中 novelty 分量算了但只进 trace，不参与 composite（composite 用 priority_hint 代替 goal_priority）；(3) shift_focus 拒绝切换时调用方不知情不排队；(4) `_estimate_switch_cost` 的"模式切换成本=0.1"注释未实现。
- **验证状态**：【功能实测可通】（agent_runtime Step4/Step9 主链路 + daemon factory 使用）。

#### 16. capability/homeostasis.py（Phase 29 稳态监控 + P2-A 内生驱力）

- **路径范围**：907 行。
- **模块职责**：六维监控（Resource/Memory/Goal/Health/Context/Identity）+ 阈值告警 + 健康分 + 调节动作建议 + P2-A `Regulator` 内生驱力引擎（五驱力 EXPLORE/MASTERY/CONNECTION/RESTORE/REFLECT → 确定性生成 SELF 级 Goal）。
- **关键类**：`HomeostasisThresholds`（~20 个阈值默认值）、6 个 Metrics dataclass、`MonitorSnapshot`、`Alert`/`HealthReport`（score 100 起，WARNING -5/CRITICAL -15）、6 个 Monitor 类（psutil 可选导入，失败静默 0）、`Regulator.derive_drives/generate_self_goals`（MAX_GOALS_PER_CYCLE=3、HUMAN_PRIORITY_FLOOR=1.0 保证 SELF 优先级恒低于 HUMAN）、`HomeostasisManager.check/health_report/recommend_actions/regulate/history`。
- **依赖**：`ocos.kernel.goal_types`（Goal/GoalAuthority/GoalLevel/GoalOriginLevel/GoalStatus）、`ocos.logging`。这是 capability 包内少数依赖 kernel 的模块。
- **被调用**（生产，最广泛之一）：`ocos/agent/agent_runtime.py:711`、`ocos/daemon/factory.py:189`、`ocos/daemon/health_loop.py:19`、`ocos/attention/focus.py:28`（DriveType/DriveSignal/RegulateResult）、`ocos/homeostasis.py`（兼容 re-export 门面）、tests（Phase 29/62d）。
- **已知限制**：(1) `MemoryMonitor.sample` 对 belief_store 调用 `count_by_status()`，GoalMonitor 调 `goal_stack.depth()`——鸭子类型，接口不匹配时静默 0；(2) `_check` 阈值语义"超过即告警"，memory_fragmentation_max=0.30 但指标名为 percent，量纲混用风险；(3) recommend_actions 中 latency_max 阈值传入 `t.latency_max*1000` 与 avg_latency_ms 比较是对的，但阈值名 seconds 与 ms 混排；(4) Regulator 生成的 Goal 描述是固定模板（同一驱力每次生成相同 Goal 文本），无去重机制——可能重复生成同类 SELF 目标。
- **验证状态**：【功能实测可通】（health_loop/factory/agent_runtime 主链路 + 62d 耦合测试）。

#### 17. capability/calibration_store.py（Phase 37 §3 校准存储）

- **路径范围**：125 行。
- **模块职责**：追踪 (capability, provider) 对的预测校准；样本 < `CALIBRATION_MIN_SAMPLES`（来自 `ocos.contracts.feedback_abi`）只记录不应用；达标后平均 delta 委托 `experience.update_reliability(...)`。
- **关键类**：`CalibrationStore.record_calibration/get_status`、`CalibrationResult`（delta/applied/reason/samples/cumulative_delta）。
- **依赖**：`ocos.contracts.feedback_abi.CALIBRATION_MIN_SAMPLES`、`ocos.logging`。
- **被调用**：包外无精确 import（grep 确认仅文档/无消费）。无独立测试文件命中。
- **已知限制**：**P1 级逻辑断链**——它调用的 `CapabilityExperienceMemory.update_reliability()` 方法根本不存在（experience_memory.py 无此方法），异常被 `except Exception: logger.debug` 吞掉，`applied=True` 照常返回，即"校准已应用"是假象，永远什么都没写。
- **验证状态**：【逻辑不完整】依赖的方法缺失、静默失败、无生产消费方。

#### 18. capability/cognitive_coupling.py（Phase 62 信念↔稳态耦合桥）

- **路径范围**：300 行。
- **模块职责**：把 BeliefManager 事件流（belief_contradiction/confirmation_bias_alert/belief_updated/belief_dormant 等）桥接到稳态系统：矛盾→认知熵 +0.15/条（上限 10.0）、确认偏差→+0.3/条、强度变化→负载、休眠→建议 gc。
- **关键类**：`CouplingConfig`（7 个阈值）、`CouplingMetrics`（跨 session 统计）、`CognitiveCouplingBridge.poll/get_cognitive_entropy/reset/diagnostics`；`_safe_drain_events` 兼容 `drain_events()` 与私有 `_event_log` 两种来源。
- **异常处理**：BR-04 注释：drain 失败与注入失败均 logger.warning 留痕。
- **依赖**：`ocos.logging`；belief_manager/homeostasis_manager 以 Any 注入。
- **被调用**：`ocos/cognitive_loop/loop_orchestrator.py`（生产消费）、tests（Phase 62a/62d、import_rules）。
- **已知限制**：`_apply_to_homeostasis` 往 `homeostasis_manager.context._metrics` 写 dict——但 capability/homeostasis.py 的 ContextMonitor **没有 `_metrics` 属性**（`getattr(ctx,"_metrics",{})` 返回 {} 后写入一个孤立 dict），即对真实 HomeostasisManager 的注入是无效操作（对其他实现可能有效）；耦合值只在 bridge 内部 metrics 可见。
- **验证状态**：【静态推演验证】主链路 loop_orchestrator 已调用 poll()；但对 capability 版 HomeostasisManager 的实际"注入"落空（对测试 mock 有效）。

#### 19. capability/custom_agent_template.py（Phase 28a5 Provider 接入规范）

- **路径范围**：70 行。
- **模块职责**：`AgentProvider` ABC——外部 Agent 接入 OCOS 的协议：必须实现 `execute(**inputs)->dict`；可选 `manifest()`/`health_check()`/`shutdown()`。
- **依赖**：无（仅 abc/typing）。
- **被调用**：grep 全库无 import（echo_agent 是平行参考实现而非继承此 ABC）。纯规范文件。
- **已知限制**：无任何内部实现引用它，属于"文档化 ABC"。
- **验证状态**：【静态推演验证】（规范完整，无消费方）。

#### 20. capability/descriptor.py + provider.py + registry.py + discovery.py（Phase 23-A 能力发现/注册四件套）

- **路径范围**：descriptor.py(77) / provider.py(70) / registry.py(168) / discovery.py(160)。
- **模块职责**：
  - `descriptor.py`：`CapabilityDescriptor`（frozen；capability_id/name/category(11 类)/version/input_output_schema dict/tags/status(DISCovered/REGISTERED/VERIFIED/DEPRECATED/DISABLED)/metadata/created_at）+ `match_tag/match_category`。注意与 Phase 45 capability_types.Capability 和 Phase 55 capability_reality.CapabilityDescriptor 三者同名概念不同物。
  - `provider.py`：`ProviderDescriptor`（provider_id/name/provider_type(ENGINE/MODULE/EXTERNAL/HYBRID)/class_path/capabilities/singleton/auto_load/version/status/factory 字段未用/metadata）+ `is_local/is_external`。
  - `registry.py`：线程安全平面注册表（RLock）；`register_capability/register_provider/bind/unregister_*/get_*/resolve/list_capabilities/list_providers/find_by_tag/count/clear`；重复注册幂等（debug 日志）；bind 时缺失实体抛 KeyError。
  - `discovery.py`：`CapabilityDiscovery`——扫描 `ocos/platform.engine_manifest.EngineDiscoverer` 的 EngineManifest，把每个 engine→ProviderDescriptor(ENGINE)、每个 capability→`ocos.{cap}` CapabilityDescriptor 并 bind；`register_external_capability` 手动注册；`scan_registry_bindings` 补绑定。ENGINE_CATEGORY_MAP 映射 reasoning/planning/… 10 类。
- **依赖**：`ocos.platform.engine_manifest`（EngineDiscoverer/EngineManifest）、`ocos.logging`。
- **被调用**：`ocos/agent/engine_bridge.py:249-251`（registry+descriptor+provider 三件套，主流程实际消费）、tests（Phase 23）。`CapabilityDiscovery`（discovery.py）本身无包外消费（engine_bridge 只用了数据类与 registry）。
- **已知限制**：(1) `list_providers(provider_type=...)` 参数被忽略（过滤逻辑缺失——真 bug）；(2) ProviderDescriptor.factory 字段声明但从未被 registry/discovery 使用；(3) discovery 依赖 engine manifest 存在 `capabilities` 字段。
- **验证状态**：【功能实测可通】（engine_bridge 实际接线；discovery 本体【静态推演验证】）。

#### 21. capability/knowledge_graph.py + experience_memory.py（Phase 25-A/B 能力知识与经验）

- **路径范围**：knowledge_graph.py(277) / experience_memory.py(252)。
- **模块职责**：
  - `knowledge_graph.py`：平面邻接表知识图谱。`EdgeType`（PROVIDES/INSTANCE_OF/PROVIDED_BY/REQUIRES）、`ResourceLimits`、`CapabilityNode/ProviderNode/ExperienceNode`（ExperienceNode __post_init__ 校验 quality_score/user_satisfaction∈[0,1]，`datetime.utcnow` 已弃用）、`KnowledgeGraph`：增删查节点/边、`query_by_task_type`（domain/actions 大小写不敏感包含匹配）、`query_by_capability`、`rank_providers`（质量 0.4+满意度 0.4+时长归一 0.2，乘以成功率惩罚）、`dependency_chain`（REQUIRES DFS）。
  - `experience_memory.py`：`CapabilityExperienceMemory` SQLite 经验库（`:memory:` 默认 / WAL 模式 / Lock 串行化 / 4 索引）。`save/save_batch/query_by_capability/query_by_provider/query_by_task_type/recent/get_stats/rank_providers`；`_cursor` 上下文管理器 BEGIN IMMEDIATE + commit/rollback。
- **依赖**：knowledge_graph 无 OCOS 依赖；experience_memory 仅 import 同包 knowledge_graph.ExperienceNode 与 ocos.logging。
- **被调用**：`ocos/capability/selection_engine.py`、`ocos/capability/result_understanding.py`（learn 写入）、`ocos/capability/orchestrator.py`（间接）；包外生产无直接精确 import（agent/engine_bridge 的 capability 子系统经由 orchestrator/agent_runtime 内部组装——精确 grep 无包外语句）。tests（Phase 25）有覆盖。
- **已知限制**：(1) experience_memory `get_stats` 返回键为 `total`，而 outcome_evaluation.py `_reliability_score` 却查 `stats.get("count", 0)`——键名不匹配导致 reliability 永远取 0.5 兜底（P1，见风险清单）；(2) KnowledgeGraph 无持久化（纯内存），重启即失；(3) `_edges_out` 只存出边，`get_incoming` 全表扫描 O(N)。
- **验证状态**：【功能实测可通】（由 orchestrator/result_understanding 链路驱动，tests 覆盖；get_stats 键名缺陷除外）。

#### 22. capability/selection_engine.py（Phase 25-C 能力选择引擎）

- **路径范围**：164 行。
- **模块职责**：Freeze §4.4 #5——融合 KnowledgeGraph 排名（0.3）+ ExperienceMemory 排名（0.3）+ 协议兼容（0.2，匹配 +0.5 分）+ 近期成功率（0.2）选 Provider；低于 fallback_threshold(0.1) 不推荐；max_results=5。
- **关键类**：`SelectionConfig/SelectionResult/SelectionEngine.select/select_top/initialize/shutdown`。
- **依赖**：knowledge_graph、experience_memory、ocos.logging。
- **被调用**：`ocos/capability/orchestrator.py:101`（构造默认实例）；tests（Phase 25）。agent_runtime 使用 orchestrator 时间接受益。
- **已知限制**：`initialize()` 不自动调用——若调用方忘调 `select()` 会用未连接的 `:memory:` SQLite（懒连接，实际仍可用）；无 freshness/负载约束。
- **验证状态**：【功能实测可通】（orchestrator 主链路）。

#### 23. capability/models.py（Phase 23 Cognitive Cortex 数据模型）

- **路径范围**：299 行。
- **模块职责**：Skill/SkillGraph/ProcessGraph/SkillExecutionRecord。Skill 含 fallback_strategy（abort/retry/skip/fallback:<id>，__post_init__ 校验）与 max_retries——"防 Workflow 退化"设计。SkillGraph 用 Kahn 拓扑排序（`get_dependency_order` 抛 CyclicDependencyError/UnknownPrerequisiteError；`has_cycle/validate`）。ProcessGraph 维护执行历史、`failed_count`（连续失败）、`repeated_skill_count`（末尾同 skill 连续次数，死循环检测用）。
- **依赖**：标准库。
- **被调用**：`ocos/learning/skill_growth.py:148`（Skill）、包内 selector/skill_graph_executor/meta_controller/skill_registry；`ocos/agent/engine_bridge.py`、`ocos/daemon/factory.py` 经由其它 import 链（精确 grep：skill_growth 直接 import）。tests（Phase 23）。
- **已知限制**：`_skill_map` 缓存 `init=False` 但在 skills 变更后不失效（若运行中追加 skill 会拿旧 map）；无持久化 schema 版本。
- **验证状态**：【功能实测可通】。

#### 24. capability/skill_registry.py（Phase 23 Skill SQLite 注册表）

- **路径范围**：266 行。
- **模块职责**：skill/skill_graph 两张表（WAL）；Skill CRUD（JSON 序列化 prerequisite/input_state/output_state/improvement_history）；SkillGraph 只存 skill_ids，load 时重建（缺失 Skill 用占位 `Skill(id=sid,name=sid)`）。
- **依赖**：models。
- **被调用**：包外无精确 import（`ocos/agent/engine_bridge.py`、daemon factory 的 Skill 相关走 agent 侧模块）。tests（Phase 23）。
- **已知限制**：(1) 默认 db_path 相对路径 `"ocos/capability.db"`，依赖 cwd；(2) save_graph docstring 有 copy-paste 残留（"Args: restore_skills / Returns" 与签名不符）；(3) load_graph 占位 Skill 会导致 SkillGraph.validate 对缺 prerequisite 的假 Skill 报 UnknownPrerequisiteError 风险（占位 Skill 无 prerequisite，反而通过了）；(4) 非线程安全。
- **验证状态**：【静态推演验证】（实现完整、有测试，但无生产接线）。

#### 25. capability/selector.py（Phase 23 CapabilitySelector — Intent→SkillGraph）

- **路径范围**：225 行。
- **模块职责**：Intent 解析→关键词表（KEYWORD_GRAPH_MAP 15 组中英映射）→匹配 SkillGraph（id/name/description/tags 复合匹配）→SelectorResult（selected_graph/candidates/confidence=1/len(candidates)/reason）。
- **依赖**：models.SkillGraph。
- **被调用**：包外无精确 import（agent/capability_selector.py 是另一个同名概念的独立实现）。tests（Phase 23）。
- **已知限制**：纯关键词匹配（自认"初版"）；confidence=1/N 是占位式打分；`_extract_keyword` 对中文 intent 落到 KEYWORD_MAP 时 OK，否则回退"第一个 ASCII 词"很粗糙。
- **验证状态**：【静态推演验证】。

#### 26. capability/skill_graph_executor.py（Phase 23 SkillGraph 异步执行器）

- **路径范围**：374 行。
- **模块职责**：按拓扑序异步执行 SkillGraph；fallback 四策略（abort/retry 指数退避 0.1*2^n/skip→SKIPPED/fallback:<id> 递归切换备用 Skill——备用 skill 从 `process.context["_fallback_skills"]` 取）；MetaController 干预（abort/warn）；`stop()` 经 asyncio.Event 协作取消；`_route_to_engine` 硬编码路由 5 个认知能力（reasoning/planning/decision/reflection/learning）→ CognitiveBridge 的 reason/plan/decide/reflect/learn。
- **依赖**：models；`ocos.agent.cognitive_bridge` 仅 TYPE_CHECKING（G1.7 合规：bridge 实例注入）。
- **被调用**：包外无精确 import。tests（Phase 23）。
- **已知限制**：(1) `process.context["_fallback_skills"]` 约定隐晦，调用方很难知道要往 context 塞 Skill 对象；(2) stop 只在 skill 间隙/重试循环生效，正在执行的同步 bridge 调用不可中断；(3) retry 的 record.attempt 每次循环重新 new record——重试记录会覆盖（process.add_record 只收最终 record）。
- **验证状态**：【静态推演验证】。

#### 27. capability/meta_controller.py（Phase 23 元控制器）

- **路径范围**：148 行。
- **模块职责**：监控 ProcessGraph：死循环（同一 skill 连续 ≥5 次）、路径过长（>50 skills）、超时（>300s）、停滞（连续 3 失败）；干预决策 abort/retry/warn；`intervene()` 执行（executor.stop）。
- **依赖**：models。
- **被调用**：包外无精确 import（`ocos/agent/meta_controller.py` 是另一独立模块）。skill_graph_executor 以 Any 注入可选消费。tests（Phase 23）。
- **已知限制**：`min_progress_required` 配置项声明但未使用（死配置）。
- **验证状态**：【静态推演验证】。

#### 28. capability/orchestrator.py（Phase 28 能力编排器）

- **路径范围**：347 行。
- **模块职责**：Freeze §9.8——统一编排：`dispatch(capability_id, inputs)` = SelectionEngine.select_top → 执行 Provider（兼容 `execute(**inputs)` 与 callable）→ ResultUnderstandingLayer.process_result 反馈学习；`chain(steps)` 顺序管道（input_from="prev"/命名步骤引用；fallback abort/skip/continue）；统计 stats。
- **关键类**：`OrchestrationResult`（output/last_output property）、`DispatchResult`（含 pipeline 字段）。
- **异常处理**：dispatch 内 try/except 全覆盖；学习管道失败仅 warning 不影响结果。
- **依赖**：方法内 import `ocos.capability.selection_engine`；ocos.logging。
- **被调用**：`ocos/orchestrator.py:9`（顶层门面 re-export）、`ocos/agent/agent_runtime.py:190`（主流程实际构造使用）、tests。
- **已知限制**：(1) timeout 参数（默认 30s）声明但从未使用——无任何超时机制；(2) chain 的 `OrchestrationResult.success = len(errors)==0`，即 fallback="continue" 时单步失败即整体 False；(3) `result_layer` 为 None 时 auto_learn 无效（静默）。
- **验证状态**：【功能实测可通】（agent_runtime 主链路）。

#### 29. capability/outcome_evaluation.py（Phase 37 五维结果评估器）

- **路径范围**：148 行。
- **模块职责**：Freeze §2——CognitiveFeedback → OutcomeEvaluation（frozen）。五维权重 success 0.35/quality 0.25/efficiency 0.20/reliability 0.10/alignment 0.10；alignment < USER_ALIGNMENT_REJECT_THRESHOLD(0.3) 直接 REJECTED_USER_MISALIGNED；efficiency = min(1, estimated/actual)；reliability 查 ExperienceMemory（冷启动 0.5）。
- **依赖**：`ocos.contracts.feedback_abi`（CognitiveFeedback/OutcomeEvaluation/EvaluationStatus/USER_ALIGNMENT_REJECT_THRESHOLD）、ocos.logging。
- **被调用**：`ocos/capability/result_understanding.py:357`（_generate_feedback 内实例化并 evaluate）；包外无直接 import；tests（Phase 37）。
- **已知限制**：**P1 缺陷**：`_reliability_score` 查 `stats.get("count", 0) > 0`，但 `CapabilityExperienceMemory.get_stats` 返回键为 `total`——`count` 恒不存在 → 即使有大量历史，reliability 恒为 0.5 中性值，第 4 维评估失效。便捷函数 `evaluate_feedback` 无消费方。
- **验证状态**：【功能实测可通】（被 result_understanding 主链路调用；reliability 维度存在上述缺陷）。

#### 30. capability/evidence_pipeline.py（Phase 37 §5 Evidence→Belief 管道）

- **路径范围**：194 行。
- **模块职责**：Feedback→Evidence→Evidence Pool（按 statement 合并）→达到门槛提升为 Belief。常量：PROMOTION_MIN_EVIDENCE=3、PROMOTION_MIN_OUTCOME_SCORE=0.7、BELIEF_MIN_SAMPLES=5、BELIEF_MIN_CONFIDENCE=0.6。rejected 反馈直接丢弃；状态机 TEMPORARY→CONFIRMED→PROMOTED。
- **关键方法**：`process_feedback/_make_statement/_check_promotion/_has_overlap（≥3 个共同词）/_update_belief/get_pool_summary`；`EvidenceResult`。
- **依赖**：`ocos.contracts.feedback_abi`、ocos.logging。
- **被调用**：包外无精确 import（grep 确认仅 tests？——无任何包外语句与 tests 命中，属未接线）。
- **已知限制**：(1) `_has_overlap` 3-共同词判定极弱（"Capability 'x' via provider..." 的样板词即占 2 个）；(2) belief_system.add(statement=..., confidence=...) 的鸭子接口需 BeliefManager 侧兼容；(3) Pool 无淘汰/上限，长期运行内存增长。
- **验证状态**：【逻辑不完整（未接线）】实现完整但无任何调用方（生产/测试均未发现 import）。

#### 31. capability/result_understanding.py（Phase 26/24-B/37 结果理解层）

- **路径范围**：426 行。
- **模块职责**：Agent 输出后处理完整管道。三层：(1) Phase 24-B `ResultUnderstanding.examine`——递归扫描 str/dict/list 所有字符串字段过 `ocos.constitution.statement_validator.StatementValidator` 禁令扫描，产出 `ExaminationResult`（passed/blocked）；(2) Phase 26 `ResultUnderstandingLayer`——`validate→structure`（自动从 dict 提取 quality/satisfaction/score/confidence 键，clamp [0,1]，摘要 200 字符）`→learn`（写 ExperienceMemory + KnowledgeGraph 双边 INSTANCE_OF/PROVIDED_BY）；(3) Phase 37 `_generate_feedback`——构造 frozen CognitiveFeedback（ExpectedOutcome/ActualOutcome）并跑 OutcomeEvaluator，`object.__setattr__` 绕过 frozen 注入 evaluation（代码内自认）。
- **依赖**：`ocos.constitution.statement_validator`、ocos.contracts.feedback_abi、ocos.capability.outcome_evaluation、ocos.capability.knowledge_graph。
- **被调用**：`ocos/agent/agent_runtime.py:182`（主流程 Tick Step 9/10 实际消费）、`ocos/capability/orchestrator.py`（dispatch 学习管道）、tests。
- **已知限制**：(1) `process_result` 中即使 validated=False 也照样 structure+learn（experience_stored=True）——**验证失败的结果仍写入经验记忆**，仅在 errors 列表留痕，违背"未验证不能进 Memory"的 CNS45-04 初衷（P2 风险）；(2) `_generate_feedback` 绕过 frozen 的 `object.__setattr__` 是脆弱 hack；(3) result_id 是新造 uuid 而非传入真实结果 ID。
- **验证状态**：【功能实测可通】（agent_runtime 主链路）。

#### 32. capability/echo_agent.py（Phase 27a7 参考实现）

- **路径范围**：53 行。
- **模块职责**：最小 Capability ABI 参考实现：`execute(**inputs)->{"output": "Echo: ...", "echoed_keys": [...]}`；无状态、零 OCOS import。
- **被调用**：`ocos/agent/agent_runtime.py:191,1248`（注册为内置能力/回退 agent）、`ocos/examples/echo_agent.py`（平行示例）。tests。
- **验证状态**：【功能实测可通】。

### 第二部分：capability_reality/ 模块详细说明（Phase 55，9 文件）

#### 33. capability_reality/__init__.py（包门面）

- **路径范围**：85 行。
- **模块职责**：声明 CR55-01~04 原则（Capability≠Execution、Adapter Isolation、Execution Recorded、Capability Discovery）与 GAP-P3-7 裁决（本包=真实能力层，ocos/capability/=抽象神经系统，两包 API 不同不合并）；导出全部 15 个符号。
- **依赖**：包内 7 个模块。
- **被调用**：`ocos/execution/bridge.py`、`ocos/tool/manager.py`、`ocos/interaction/converse.py`、`ocos/daemon/repair_link.py` 等通过子模块 import；包级 `from ocos.capability_reality import ...` 未见于生产（tests/test_phase55.py 用子模块路径）。
- **验证状态**：【功能实测可通】。

#### 34. capability_reality/adapter_types.py（类型定义）

- **路径范围**：154 行。
- **模块职责**：`AdapterHealth`（UNKNOWN/HEALTHY/DEGRADED/FAILED/DISCONNECTED）、`ExecutionStatus`（含 REJECTED=被 validator 拒绝）、`CapabilityCategory`（FILESYSTEM/SHELL/NETWORK/CODE/BROWSER/GENERATIVE/CUSTOM）、`CapabilityDescriptor`（name/category/required_params/optional_params/permissions/risk_level 1-5/estimated_duration/reversible/metadata——注意与 Phase 23-A descriptor 同名不同物，此处是可执行能力描述）、`AdapterStatus`（健康快照 + failure_rate property）、`ExecutionContext`（execution_id/capability_name/params/decision_id/goal_id/sandboxed 默认 True/timeout 默认 30s）、`ExecutionResult`（context/status/output/error/duration_ms/event_id/metrics；`ok` property）、`AdapterConfig`（sandboxed/default_timeout/max_retries(声明未用)/retry_delay(未用)/log_level(未用)/allow_unsafe_ops(未用)/max_output_bytes/permissions）。
- **被调用**：包内全部模块、`ocos/execution/bridge.py:640`（ExecutionContext）、tests/test_phase55.py。
- **已知限制**：AdapterConfig 的 max_retries/retry_delay/log_level/allow_unsafe_ops 四个字段无任何实现消费（死配置）；timeout 语义单位秒。
- **验证状态**：【功能实测可通】。

#### 35. capability_reality/capability_registry.py（真实能力注册表）

- **路径范围**：108 行。
- **模块职责**：`RegisteredCapability`（descriptor + executor Callable 绑定 + AdapterStatus；__post_init__ 补 adapter_id）+ `CapabilityRegistry`（name→RegisteredCapability + category 双索引）：register/unregister/get/list_all/list_by_category/find_executable/has/count/categories/mark_health/healthy_count/clear。
- **依赖**：adapter_types。
- **被调用**：包内 adapter_discovery/capability_selector、`ocos/execution/bridge.py`（AdapterDiscovery.run 返回）、`ocos/tool/manager.py`、`ocos/daemon/repair_link.py`、`ocos/interaction/converse.py`、tests/test_phase55.py。
- **已知限制**：register 同名覆盖（旧注册的 status 丢失）；无容量上限。
- **验证状态**：【功能实测可通】（主流程：execution/bridge、tool/manager）。

#### 36. capability_reality/capability_selector.py（真实能力选择器）

- **路径范围**：125 行。
- **模块职责**：Decision target → 最佳 adapter。策略：精确名匹配（排除 FAILED/DISCONNECTED）→ 分类匹配（`_infer_category` 从名字推断 fs/shell/http/code/browser）→ 风险升序。`select_by_intent` 中文/英文意图关键词→固定 capability 名（fs_read/fs_write/shell_exec/http_get/code_exec）。
- **依赖**：adapter_types、capability_registry。
- **被调用**：tests/test_phase55.py；包外生产无直接 import（execution/bridge 等走 registry+discovery 直配）。
- **已知限制**：select_by_intent 映射的 http_get/code_exec 在注册表中默认不存在（discovery 只注册 filesystem/shell）→ 意图命中后 matched=False；`select()` 精确匹配成功时不检查 executor 是否存在（可能选中无执行器的登记项）。
- **验证状态**：【功能实测可通】（有测试；http_get/code_exec 分支实际不可用）。

#### 37. capability_reality/capability_adapter.py（适配器基类）

- **路径范围**：149 行。
- **模块职责**：CR55-02 落地。`CapabilityAdapter(ABC)`：`execute(ctx)` 模板方法——计时、total_executions++、异常全捕获转 FAILED/timeout 转 TIMEOUT、failure_rate>0.5 → DEGRADED、`on_event` 回调（异常吞掉）；`health_check()` 委托 `_do_health_check`；`validate(ctx)` 执行前检查（timeout∈(0,300]、risk≥4 必须 sandboxed、permissions 全部在 config.permissions 中）；`register_to(registry)` 自注册（executor=self.execute）。
- **依赖**：adapter_types；方法内 import capability_registry。
- **被调用**：adapter_fs/adapter_shell 继承；tests。
- **已知限制**：(1) 注释声称"超时保护"，但基类并不实施 ctx.timeout 超时（超时靠子类内部 subprocess timeout 抛 TimeoutError 实现）——纯 Python 执行体不会超时；(2) `avg_latency_ms` 移动平均公式依赖 total_executions 递增，在并发下有竞态（无锁）；(3) validate 权限检查要求 adapter 全部权限 ∈ config.permissions，而 FilesystemAdapter 构造时两者相同恒过——检查形同虚设。
- **验证状态**：【功能实测可通】（fs/shell 子类经 discovery→execution/bridge 主链路）。

#### 38. capability_reality/adapter_fs.py（文件系统适配器）

- **路径范围**：139 行。
- **模块职责**：5 个操作 read/write/list/stat/exists；safe_roots 沙盒（默认 `~/`、`/tmp`、`/home/laogao/Documents`——**硬编码个人用户目录**）；`_resolve` 用 `abspath(expanduser)` + startswith 前缀校验；read 限 1MB；list 截 100 项；descriptor risk_level=3、reversible=False。
- **异常处理**：路径越界 PermissionError、缺失 FileNotFoundError、过大 ValueError——由基类包装为 ExecutionResult.FAILED。
- **依赖**：capability_adapter、adapter_types。
- **被调用**：`adapter_discovery._discover_filesystem`（注册到 registry）、tests/test_phase55.py；最终被 execution/bridge、tool/manager、converse、repair_link 消费。
- **已知限制**：**P2 安全**：`startswith(root)` 前缀检查可被同级目录绕过——`/home/laogao/Documents-evil` 满足 startswith("/home/laogao/Documents")，路径越权；应使用 `os.path.commonpath` 或 pathlib `is_relative_to`（self_modification_agent 就用了正确写法，此处没有）。
- **验证状态**：【功能实测可通】（含上述沙盒缺陷）。

#### 39. capability_reality/adapter_shell.py（Shell 适配器）

- **路径范围**：142 行。
- **模块职责**：shell_exec——subprocess.run(shell=True)；沙盒：workdir 解析进 safe_roots（越界则**静默回落到 safe_roots[0]**）、timeout 强制 kill（抛 TimeoutError→基类 TIMEOUT）、stdout 截断 500KB、危险命令黑名单（rm -rf /、mkfs.、dd if=、fork bomb、chmod 777 /、wget -O- | sh 等 7 条，匹配前去空格）；descriptor risk_level=4。
- **依赖**：capability_adapter、adapter_types。
- **被调用**：adapter_discovery._discover_shell、tests；下游同 fs。
- **已知限制**：**P2 安全**：(1) 黑名单极易绕过（`rm -fr /` 顺序换、`rm -r -f /`、`\rm`、变量拼接、`sh -c` 嵌套均不在名单）；(2) `cd {workdir} && {command}` 中 workdir 未引号包裹（含空格路径炸）；(3) env 直传可注入；(4) stderr 未截断；(5) workdir 越界静默回落而非报错——用户意图被悄悄改变。
- **验证状态**：【功能实测可通】（含上述安全弱点）。

#### 40. capability_reality/adapter_discovery.py（环境自动发现）

- **路径范围**：141 行。
- **模块职责**：CR55-04。`run()` 返回 (CapabilityRegistry, DiscoveryReport)：fs 可读写→注册 FilesystemAdapter；任一 shell 二进制存在→注册 ShellAdapter；探测 Python 版本+10 个标准库模块；`shutil.which` 探测 git/curl/docker/node 等 14 个 CLI 工具。
- **依赖**：adapter_fs/adapter_shell/capability_registry/adapter_types。
- **被调用**：`ocos/execution/bridge.py:155`、`ocos/interaction/converse.py:228`、`ocos/daemon/repair_link.py:254`、`ocos/tool/manager.py:35`（四处生产主链路）、tests/test_phase55.py。
- **已知限制**：`_discover_python`/`_discover_tools` 只填 report 不注册能力（python 与 CLI 工具没有对应 adapter）；network 维度在 docstring 声称但未实现（无 `_discover_network`）。
- **验证状态**：【功能实测可通】。

#### 41. capability_reality/capability_validator.py（执行前/后验证器）

- **路径范围**：155 行。
- **模块职责**：`validate_pre`：速率限制（60s 窗口 100 次）→required_params 完整性→timeout 警告→risk>5 拒绝→risk≥4 且非沙盒拒绝→risk≥3 NEEDS_REVIEW→否则 APPROVE。`validate_post`：FAILED/TIMEOUT→REJECT，否则 APPROVE。统计与 `stats()/clear()`。
- **依赖**：adapter_types。
- **被调用**：tests/test_phase55.py；包外生产无直接 import——即**验证器与执行链路未强制串联**（execution/bridge 与 adapters 均未调用 validate_pre；CapabilityAdapter.validate 是另一套）。
- **已知限制**：(1) `_check_rate_limit` 先 append 再判断，被拒绝的请求也占窗口名额（拒绝也计数，属保守但与"剩余额度"语义偏差）；(2) NEEDS_REVIEW 决策无任何人工审批通道/回调，调用方拿到后如何处理全凭自觉；(3) risk_level≥auto_approve_risk_below(3) 的判断用 `>=`，注释却说 "<3 自动批准"——一致，但 FilesystemAdapter risk=3 → 每次读文件都 NEEDS_REVIEW，实际主流程未调用 validate_pre 才没暴露这一体验问题。
- **验证状态**：【静态推演验证】实现完整、有测试，但生产执行链路未接线（隔离的验证组件）。


#### 分组 审计分组 W3：interaction 对外网关层（API/CLI/对话）

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1.1 api 路由层（`ocos/interaction/api/`，12 文件）

- **模块路径范围**：`ocos/interaction/api/__init__.py`、`api/server.py`、`api/models.py`、`api/routes/{__init__,goal,plan,memory,belief,trace,chat,quality,converse}.py`、`api/static/index.html`（非 py，`/ui` 页面引用）。
- **模块职责**：OCOS 唯一对外 HTTP 网关（FastAPI）。文档声明架构约束"API → PermissionGuard → Kernel（Goal Interface），API 不拥有写 Memory/Self/Constitution 的权限"。
- **对外提供能力**：21 个 HTTP 端点（含 2 个非 schema 的 UI 端点），覆盖健康检查、目标创建、规划、记忆/信念/追踪查询（占位）、OpenTale WebChat、质量/趋势分析、对话、状态总览、出站消息、内视、自我迭代、对话转目标、待批审批（完整清单见二、三节）。
- **内部子模块**：server.py（应用工厂 + `main()` uvicorn 入口）、models.py（pydantic 请求/响应模型）、routes/*（8 个 APIRouter）。
- **输入输出**：输入为 JSON 请求体（部分为裸 dict，见风险）；输出统一包装为 `APIResponse{success, message, data, timestamp}`。
- **正常工作流程**：请求 → PermissionGuard.check(action)（constitution 委托校验）→ 构造 `GoalRequest`/调用下层 → `APIResponse` 返回。`/ocos/converse` 走 `asyncio.to_thread(responder.respond_auto)`，`/ocos/quality/*` 委托 `opentale_bridge` 的 QualityAnalyzer/TrendAnalyzer。
- **异常处理逻辑**：guard 拒绝 → 403；ValueError → 400；quality 路由宽 except → 500（detail 泄漏内部异常字符串）；converse 路由 400/404/422。
- **依赖其它 OCOS 模块（真实 import）**：`ocos.goal.models`、`ocos.kernel.goal_types`、`ocos.interaction.base`、`ocos.interaction.cli.paths`（跨子包借用路径解析）、`ocos.interaction.converse`、`ocos.interaction.inbox`、`ocos.goal.store`、`ocos.execution.pending`、`ocos.execution.bridge`、`ocos.opentale_bridge.{master_agent,organ_client,quality_analyzer,trend_analyzer}`、`ocos.planning.{decomposer,strategy}`（延迟 import）。
- **被哪些 OCOS 模块调用**：`ocos/external/server_manager.py:306`（`from ocos.interaction.api.server import app`，由其托管起服）；TUI（tui.py）作为 HTTP 客户端消费 `/ocos/*`。
- **已知限制**：
  1. `POST /ocos/goal` 只构建 UserGoal 内存对象，**不落库**（goal.py:82 注释 "GoalStore integration TBD"）——与 CLI `goal create`（真实落 GoalStore）行为漂移，API 创建的目标会丢失；
  2. memory/belief/trace 三个查询路由是占位（永远返回空 results + "TBD" note），但已在 OpenAPI 中"对外公开"；
  3. `/ocos/chat`、`/ocos/converse` 系列端点**不经过 PermissionGuard**（converse 系列直连 DB/Store）；`/ocos/goals-from-chat` 直接写 GoalStore，绕过 base.py 权限模型；
  4. server.py:88 `host="0.0.0.0"` 监听全部网卡且无任何认证（见风险 R-P1-1）。
- **验证状态**：【功能实测可通】——app 可导入、路由注册完整、CLI 同源命令实测可通、test_webchat_api 16 条测试通过；但 goal/memory/belief/trace 四组端点为占位实现，属"路由可用、业务半成品"。

##### 1.2 cli 命令层（`ocos/interaction/cli/`，20 文件）

- **模块路径范围**：`cli/{__init__,__main__,main,parser,paths}.py` + `cli/commands/` 15 个命令文件。
- **模块职责**：`ocos` 命令行入口（argparse），涵盖目标/规划/记忆/信念/追踪查询、对话投递（say/inbox）、状态总览、审批、daemon 启动（run）、OpenTale 器官驱动（organ/decide/regulate/feedback）、TUI 启动（chat）、系统重启（restart/gateway）、成长模块（growth）、自我修改（self）。
- **对外提供能力**：约 19 组命令 / 40+ 子命令（清单见三节）。`cli/__main__.py` 支持 `python -m ocos.interaction.cli`。
- **内部子模块**：main.py（路由分发 + 创建 InteractionSession/InteractionContext）、parser.py（全部 argparse 定义）、paths.py（DB 路径单一来源：显式参数 > OCOS_DB_PATH > ~/.ocos/ocos.db）。
- **输入输出**：argv → stdout 文本 + 退出码（0 成功 / 1 失败 / 2 无法执行，goal exec）。
- **正常工作流程**：parse → PermissionGuard.check → GoalRequest.create（caller 白名单校验）→ to_user_goal（Kernel 二次验证）→ 落 GoalStore / 调 OrganClient / 启 ResidentRuntime。
- **异常处理逻辑**：ValueError 打印返回 1；OrganClientError 打印返回 1；run 捕获 SIGINT/SIGTERM 优雅停机；plan 的分解失败降级为提示（仍返回 0）。
- **依赖其它 OCOS 模块**：`ocos.goal.{models,store}`、`ocos.interaction.{base,context,inbox}`、`ocos.planning.{decomposer,strategy}`、`ocos.daemon.factory`（build_master_agent/health_loop/execution_bridge/knowledge_abi/perception_pipeline）、`ocos.daemon.ResidentRuntime`、`ocos.execution.{pending,bridge,goal_executor}`、`ocos.capability.agents.self_modification_agent`、`ocos.reflection.self_review`、`ocos.opentale_bridge.{organ_client,master_agent,self_regulation,feedback_reflux}`、`ocos.growth.engine`、`ocos.perception.file_sensor`、`ocos.storage.migrations`。
- **被哪些 OCOS 模块调用**：`ocos/interaction/repl/commands/ops.py`（复用 cmd_status/cmd_say）；`ocos/daemon` 系统作为 `ocos` console-script 入口（pyproject 层面）；网关层内部互不调用。
- **已知限制**：
  1. main.py:173 与 182 存在**重复的 `elif args.command == "run"` 死分支**；
  2. `growth execute <proposal_id>` 是**半成品**（commands/growth.py:111-119）：handler 忽略 proposal_id，只打印"请用 grow"并返回 0，与 parser 承诺不符；
  3. parser 帮助声称 growth summary "≥60 chars"，但 ingest 只做了非空校验（growth.py:72-74），文档与实现漂移；
  4. trace show 是 TBD 占位；
  5. `self preview` 子命令在 parser 未注册（parser 只注册 status/identity/review/mod/validate），self.py:195 的 cmd_self_preview 永远不可达；
  6. restart.py 依赖 `systemctl --user` 与 `~/.config/systemd/user/` 单元，非 Linux systemd 环境直接报错（有明确提示）。
- **验证状态**：【功能实测可通】（goal/plan/status/list 冒烟通过 + 81 条相关测试）；growth execute 为【逻辑不完整】；trace 为占位。

##### 1.3 converse 对话层（`converse.py` 1226 行 + `context.py` + `session_state.py` + `conversation_state.py` + `inbox.py`）

- **模块路径范围**：`ocos/interaction/converse.py`、`context.py`、`session_state.py`、`conversation_state.py`（未提交新文件）、`inbox.py`。
- **模块职责**：数字生命对话回复引擎（ChatResponder）+ 内核 Store 只读注入器（InteractionContext）+ 会话状态（进程内 SessionManager / 跨进程 SQLite ConversationStateStore）+ 用户消息收件箱（UserInbox，ocos say → daemon 消费）。
- **对外提供能力**：
  - `ChatResponder.respond/respond_auto/compile_goal/build_introspection/self_improve`：诚实降级链（真实 LLM → 带 mock 标注的状态回复）；`respond_auto` 实现"对话即路由"——task 类消息经 `compile_goal`（LLM JSON 分类）自动建目标，question/continue 走状态机精确恢复目标上下文；
  - USE| 动作协议：LLM 回复可输出 `USE|shell|{...}` / `USE|fs_read|{...}` 只读动作行，`make_default_tool_executor` 执行（shell 走 DecisionBridge 沙盒白名单四重防护，fs_read 走敏感前缀+safe_roots+64KB 截断），FIX-22 多步主循环 act→observe→reason，每回复最多 2 轮工具、总 LLM 调用 ≤3；
  - 每轮对话落 Episode 记忆（source=conversation, FIX-8 session_id 贯穿）；
  - `UserInbox`：post/drain/reply/wait_for_reply/post_outbound/list_outbound_after/max_rowid/count_queued，user_messages 表自愈建表 + legacy 列升级。
- **输入输出**：`respond(message, goal_note, session_id) -> {reply, provider, mock, goal_id?, kind?}`；ConversationStateStore 每会话一行 `{current_goal_id, last_goal_id, last_intent, active_topic, updated_at}`。
- **正常工作流程**（respond_auto）：compile_goal 分类 → task：去重（UX-H+ 同义目标复用）→ 建 GoalStore PENDING 目标 → ConversationStateStore.update(current_goal_id) → daemon 心跳判断 → goal_note 注入 → build_context（身份/引擎/能力/记忆/召回/对话转录/目标结果/智慧/学习规则/世界状态/连续性）→ LLM 多步循环 → 剥离 USE 行 → personalize → 落记忆。
- **异常处理逻辑**：几乎全部子上下文块 try/except + logger.debug 兜底（单块失败不拖垮回复）；LLM 调用失败降级 _state_reply 并标注错误；USE 执行拒绝/拦截如实回注观察块防 LLM 无限重试。
- **依赖其它 OCOS 模块**：`ocos.memory.{hub,episode.models,recall}`、`ocos.goal.store`、`ocos.execution.{pending,bridge}`、`ocos.autonomous_runtime.action_dispatcher`、`ocos.agent.{engine_bridge,self_evolution_link,wisdom_trigger,continuity_trigger}`、`ocos.capability_reality.adapter_discovery`、`ocos.personal_intelligence.{personalization_engine,cognitive_signature}`、`ocos.learning.persistence`、`ocos.world_model.world_store`、`ocos.engines.text_generator`、`ocos.event_memory.{event_store,event_types}`、`ocos.storage.connection`、`ocos.self.identity_boundary`、`ocos.memory.belief.{store,models}`。
- **被哪些 OCOS 模块调用**：`ocos/daemon/__init__.py:158`（ChatResponder + make_default_tool_executor 消费 say 消息）、`ocos/daemon/__init__.py:133`（SessionManager）、`ocos/daemon/factory.py:115`（UserInbox）、API routes/converse.py；inbox 另被 CLI say/inbox、TUI outbox 轮询消费。
- **已知限制**：
  1. `_FS_SENSITIVE_PREFIXES`/`safe_roots` **硬编码 /home/laogao**（converse.py:124,143），换用户即失效/误伤（可移植性）；
  2. `self_improve`/`respond` 内部 `asyncio.run(...)`——若在已运行事件循环的线程直接调用会 RuntimeError，当前 API/daemon 均经 to_thread 规避；
  3. `_latest_goal_result_text` 用目标 updated_at 与 episode created_at **±120 秒时间窗关联**，跨机器时钟/批量写场景易错配；
  4. daemon 场景下 SessionManager.append_turn 与 ChatResponder._remember_conversation **可能对同一轮 assistant 回复双写 episode**（两处独立落库，无去重）；
  5. session_state.py 默认 REPL 路径 `ocos.db`（shell.py:34 用相对路径而非 cli.paths 的 ~/.ocos/ocos.db）——REPL 在任意 cwd 读写的库与 CLI/daemon 不同（路径漂移，paths.py 注释自称"单一来源"但 REPL 未接入）；
  6. conversation_state.py update 为读-改-写无事务包裹，跨进程并发 update 有丢更新窗口；异常全部 debug 级静默。
- **验证状态**：【功能实测可通】——test_conversation_state（8 条，未提交文件配套测试）全过、test_say_channel/test_phase_session_state/test_webchat_api 通过、CLI say/inbox 依赖链编译通过；多步 USE 循环逻辑经静态推演 + 单测覆盖（test_multi_step_loop.py 存在于未提交列表）。

##### 1.4 主动交互管线 Phase 53（`interaction_types.py` + `need_monitor.py` + `attention_trigger.py` + `interaction_scheduler.py` + `interaction_validator.py` + 包 `__init__.py`）

- **模块职责**："学会什么时候该开口"：内部状态 → NeedMonitor（边缘系统，规则扫描产出 NeedSignal）→ AttentionTrigger（前额叶，紧急度→优先级 + 用户活跃度/响应率适配）→ InteractionCandidate → InteractionValidator（IS53-01/02 关键词拒绝自主决策/自主目标、命令式语气 FLAG）→ InteractionScheduler（速率限制/冷却/去重/过期撤回/优先级出队）。
- **对外提供能力**：全部经 `ocos.interaction` 包 `__init__.py` 导出（NeedMonitor、create_default_rules、AttentionTrigger、InteractionScheduler、InteractionValidator 等 16 个符号）。
- **输入输出**：NeedSignal(need_type, urgency 0-1) → InteractionPriority|None → InteractionCandidate(title/body/suggested_action) → SendValidationResult(PASS/FLAG/REJECT) → 出队发送。
- **依赖其它 OCOS 模块**：无（纯自包含，仅标准库 + 包内互引）。
- **被哪些 OCOS 模块调用**：**仅测试**——`ocos/tests/test_phase53.py`、`ocos/tests/test_phase_fix17_proactive.py`。grep 全仓库无任何生产代码（daemon/runtime/agent）调用该管线，**主动交互链路未接线到生产 tick**。
- **已知限制**：AttentionTrigger 的时间/时区适配只有注释没有实现；InteractionScheduler 队列纯内存不持久化。
- **验证状态**：【静态推演验证 + 单测通过】（test_phase53 20+ 条通过），但生产集成状态为【逻辑不完整】——组件完整、消费端缺失。

##### 1.5 外部交互通道 Phase Q（`channel.py`）与统一入口 Phase 22-F（`cognitive_interface.py` + `stimulus.py`）

- **channel.py**：ExternalInteraction 管理器 + LogChannel/CallbackChannel/WebhookChannel/BroadcastChannel（注册/按名或活跃集合发送/健康统计/失败降级/消息历史环形 1000 条）。依赖仅标准库。被调用方：**仅 `ocos/tests/test_external_interaction.py`**（16 条测试通过）——生产无调用者，属库存组件。小瑕疵：WebhookChannel 非 2xx 时在 with 块外访问 `resp.status`（对象仍可用，仅风格问题）。
- **cognitive_interface.py + stimulus.py**：CognitiveInterface 统一入口（CLIAdapter/APIAdapter 解析外部输入为 Stimulus → 注入 runtime._event_ingestion 事件管道 → SLEEPING 则 wake），Stimulus/StimulusType/StimulusResult 数据模型。依赖 `ocos.interaction.stimulus`。被 `ocos/cognitive_interface.py`（顶层同名 shim，`from ocos.interaction.cognitive_interface import CognitiveInterface`）转发。**注入依赖 runtime 私有属性 `_event_ingestion`，脆弱**；wake 用 `str(cortex.mode) == "SLEEPING"` 字符串比较避免跨包导入（有意为之，有注释）。验证状态：【静态推演验证】（shim 编译通过，无独立测试直接覆盖 stimulate 全链）。

##### 1.6 基础抽象层（`base.py`）

- **职责**：GoalRequest（caller 白名单 CALLER_WHITELIST + priority 1-5 校验 → Kernel UserGoal.create 二次验证）、InteractionSession（会话元数据容器，不持久化）、PermissionGuard（FORBIDDEN 最高优先拒绝 → ALLOWED 白名单 → 委托 BehavioralConstitution.check_decision，constitution 异常时 fail-closed）。
- **依赖**：`ocos.constitution.behavioral`、`ocos.goal.models`、`ocos.logging`。
- **被调用**：API 全部 guarded 路由、CLI 几乎全部命令、REPL 全部命令、`ocos/execution/bridge.py:38`（import PermissionGuard, ALLOWED_ACTIONS）。
- **已知限制**：PermissionGuard.check 用 `type("Decision", (), {"action": action})()` 临时鸭子对象喂 constitution，constitution 是否真正产生实质校验取决于 behavioral 实现对该最小对象的容忍度——**有"形式校验"风险**（未深查 behavioral 内部，标注【信息缺失】）。
- **验证状态**：【功能实测可通】（goal create 全链实测：guard→GoalRequest→UserGoal→GoalStore 落库成功）。

##### 1.7 repl 交互壳（`repl/`，14 文件）

- **职责**：`python -m ocos.interaction.repl` 启动 cmd.Cmd 交互壳；命令类封装 /plan /memory /belief /goal /self /trace /approvals /status /say /help；`/` 前缀兼容（precmd 剥离）；default 行为 = 直接当目标描述创建；approvals approve/deny 与 CLI 同源（PendingStore + DecisionBridge 诚实执行）。
- **依赖**：`ocos.interaction.{base,context}`、`ocos.goal.store`、`ocos.execution.{pending,bridge}`、repl ops 复用 cli 的 cmd_status/cmd_say（SimpleNamespace 伪装 args）。
- **被调用**：无外部调用者（独立入口）。
- **已知限制**：
  1. `repl/completer.py` 的 ReplCompleter/complete_command **从未被 shell.py 挂接**（shell 用 cmd.Cmd 且未设 readline completer）——死代码；
  2. completer 的 REPL_COMMANDS 不含 status/say/approvals（漂移）；
  3. /goal 用 "create_goal" 权限做只读查询（注释自认）；
  4. /trace 占位 TBD。
- **验证状态**：【静态推演验证】（全部命令类与 CLI 共用已实测的下层实现；REPL 本体未实测起会话）。

##### 1.8 tui 终端界面（**v1.3 重构为纯前端**：`ocos/tui/` 包 3 文件 + 遗留 `tui.py`）

- **新架构（UX-J，2026-09-06）**：`ocos/tui/tui_client.py`（OcosTuiFrontend，纯前端 App）+ `ws_client.py`（OcosWsClient，线程安全 WebSocket）+ `widgets.py`（LogView/InputBox/StatusBar）。**业务逻辑零前置**：界面只做渲染与输入转发，认知/决策/记忆/LLM 全部在后台 API 网关（`interaction/api/routes/ws.py` WebSocket 端点）+ daemon；关闭 TUI 不影响内核运行。
- **协议**：连接即收 `{"kind":"session","session_id","is_new"}`（会话 ID 持久化 ~/.ocos/gateway_session 跨重启续用）→ 非新会话自动发 `{"type":"history"}` 回放 EpisodeStore 历史；`chat/abort/ping/history` 四类请求；接收事件 `agent_delta`（流式）/`agent_done`（含 model+usage）/`user_message`/`goal_result`（完成即推面板）/`status`/`system`。
- **交互能力（对齐 OpenClaw/Hermes）**：Enter 发送 / Shift+Enter 换行（InputBox 自定义 Submitted 消息）；rich Markdown 渲染（表格/列表/代码高亮/引用块）；用户消息暗色块；双行状态栏（`connected|running` + `agent|session|模型|tokens`——tokens 为真实 API usage，端点不回传则诚实显示 "-"）；滚轮/滚动条翻页（mouse=True，原生复制用 Shift+拖拽，程序内兜底 Ctrl+Y）；PgUp/PgDn/Home/End 聊天翻页；Esc 中止当前轮；Ctrl+P 过滤式会话选择器（SessionPicker）；Ctrl+L 清屏；多行粘贴预览 `[pasted: N lines]`。
- **旧 `interaction/tui.py`（1100 行）**：HTTP 轮询版（POST /ocos/converse + 轮询 outbox），含 SessionStore（~/.ocos/tui_sessions.db）、斜杠命令 20 个、busy 模式。仍可用（`python -m ocos.interaction`），但新入口 `ocos chat` 已切至 `ocos/tui/tui_client.py`。
- **已知限制**：tokens 显示依赖端点回传 usage（部分端点不回）；Shift+Enter 需终端支持（老终端当 Enter）。
- **验证状态**：【功能实测可通】（11 个 TUI 测试 + Textual headless 截图验证 + 线上端到端：连接/历史回放/真实按键发送/流式回复全通过）。

---


#### 分组 审计分组 W4：runtime 认知运行时 + runtime_scheduler 调度器

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. `ocos/runtime/__init__.py` + `__main__.py`（包入口）
- **范围**：__init__.py L1-53，__main__.py L1-29。
- **职责**：声明 ocos.runtime 为 "Phase 39.3 Permission Integration" 包，导出 RuntimeKernel/RuntimeLoop/Tick/TickPipeline/RuntimeState/LifecycleManager/CheckpointEngine/RecoveryEngine/RecoveryManager/CapabilityPolicyProvider 等核心符号。`__main__` 提供 `python -m ocos.runtime` 演示入口：boot → 60 ticks（每 10 tick checkpoint）→ shutdown 并打印 checkpoint 路径。
- **对外能力**：包级 API 面（`__all__` 21 个符号）。
- **依赖**：capability_policy / checkpoint / lifecycle / recovery_engine / recovery.recovery_manager / runtime_kernel / runtime_loop / runtime_state / tick / pipeline / pipeline_protocol / tick_context。
- **被调用**：tests/test_phase39_1.py、test_single_main_loop.py、test_runtime_loop.py 等；生产侧由 `ocos/daemon/__init__.py` L111 `from ocos.runtime.runtime_kernel import RuntimeKernel`（延迟导入）。
- **已知限制**：__main__ 演示仅驱动空心跳 Kernel（无 stage 依赖注入、无 agent driver），不代表生产形态。
- **验证状态**：【静态推演验证】入口代码简单直白，无分支风险。

##### 2. `ocos/runtime/runtime_kernel.py` — 心跳引擎（224 行）
- **范围/职责**：L45-224 `RuntimeKernel`。OCOS 常驻运行时心跳引擎，控制生命周期（start/stop/shutdown）并驱动 8 阶段 TickPipeline；遵守 Governance Freeze（不 import ocos.goal/agent/self）。
- **对外能力**：`start() -> runtime_id`、`stop()`、`shutdown(checkpoint=True)`、`tick_loop(max_ticks, interval)`、`async run(...)`、`attach_agent_driver(driver)`、属性 runtime_id/state/last_tick_id/tick_count/last_agent_result。
- **内部协作**：CheckpointEngine（/tmp/ocos_checkpoints）、RecoveryEngine（内含 RecoveryManager）、LifecycleManager、CapabilityPolicyProvider（仅构造未在 tick 中调用——**policy provider 处于闲置状态**）、TickPipeline。
- **正常流程**：start → attempt_recovery()（恢复 last_tick_id / next_tick_id）→ tick_id_generator 起始 → lifecycle.boot()（BOOTING→RUNNING）→ tick_loop 每 tick：`pipeline.execute_tick(tick_id, runtime_state)` → 构造不可变 Tick → 若 ctx.checkpoint_decision 为真则 create_checkpoint。
- **异常处理**：`_execute_tick` 在未 start 时抛 RuntimeError；Pipeline 内 stage 异常在 pipeline 层包装为 PipelineError 向上冒泡——**tick_loop 未捕获，单 stage 失败即终止整个 tick_loop**（见风险 P2-3）。async run 有 finally shutdown，同步 tick_loop 没有（调用方需自行 shutdown）。
- **依赖**：本包内模块（见上）；无其他 OCOS 模块。
- **被调用**：ocos/daemon/__init__.py（生产，`RuntimeKernel()` 默认构造 + `attach_agent_driver(lambda tick_id: self._runtime.tick())`）；tests/test_phase39_2.py、test_single_main_loop.py。
- **已知限制**：(a) 每次构造默认 `runtime_id=uuid4()`，daemon 未传固定 ID → CheckpointEngine 按 runtime_id 找历史 checkpoint 永远 miss（P2-1）；(b) L222 用 `object.__setattr__` 改写 frozen Tick 的 checkpoint_id，破坏不可变语义（P4-2）；(c) 恢复结果 RestoreResult 的 active_goal_ids/attention_focus/pending_approvals 在 Kernel 中被丢弃，只取 tick 计数（P2-2）。
- **验证状态**：【功能实测可通】（test_phase39_2/test_single_main_loop 覆盖 boot/tick/checkpoint/restart），但恢复后认知状态回灌未实现。

##### 3. `ocos/runtime/runtime_loop.py` — 运行时主循环抽象层（433 行）
- **职责**：Phase M "心脏起搏器"，把生命周期、tick 驱动、指标、hook 封装为可独立测试的 RuntimeLoop；支持线程模式与 asyncio 模式。
- **对外能力**：`LoopState`（6 态）、`LoopMetrics`（uptime/ticks_per_second/滑动平均 tick 时延，保留最近 100 条）、`RuntimeLoop.start/stop/pause/resume/run_for/async_start/async_stop/async_run/sync_context/async_context`、hook 注册器 `on_start/on_stop/on_tick/on_error`（链式返回 self）、工厂 `create_runtime_loop(runtime, interval=1.0, max_ticks=0, name)`。
- **正常流程**：线程模式 `_run_sync_loop`：while not stop_event → `_pause_event.wait(interval)` 实现暂停与节流 → `self._runtime.tick()`（要求注入的 runtime 有 tick()）→ record_tick → on_tick hook → max_ticks 检查。失败路径捕获 Exception → failed_ticks++ → on_error → 短暂退避后继续。
- **异常处理**：tick 异常不会终止循环；hook 异常只 warning；stop(timeout=30) 返回 False 若线程未退出。
- **依赖**：无 OCOS 内部依赖（纯标准库）。
- **被调用**：tests/test_runtime_loop.py；`ocos.runtime.__init__` 导出 `create_runtime_loop`；**生产代码（daemon）未见使用**——daemon 自建线程直接调 kernel.tick_loop(max_ticks=1)。
- **已知限制**：(a) async_run 中 `self._runtime.tick()` 是同步阻塞调用，会卡住事件循环（P3-6）；(b) run_for 与 start 共享 _max_ticks 字段，并发混用有线程安全隐患（内部 RLock 只保护状态字段）；(c) LoopMetrics.record_tick 与失败路径 `total_ticks += 1` 存在重复计数口径差异（成功路径 record_tick 也 +1，失败路径手动 +1，口径一致但分散）。
- **验证状态**：【功能实测可通】（test_runtime_loop.py 覆盖同步/异步/暂停/失败重试），生产未接线。

##### 4. 管线协议机制：`tick.py` / `pipeline_protocol.py` / `tick_context.py` / `pipeline.py` / `stages/*`（重点）
- **范围**：tick.py(43) + pipeline_protocol.py(78) + tick_context.py(88) + pipeline.py(149) + stages/（9 文件 462 行）。
- **协议设计（pipeline_protocol.py）**：
  - `PipelineStage(Enum)` 冻结 8 阶段顺序：①EVENT_INGESTION(1) → ②ATTENTION(2) → ③MEMORY_SYNC(3) → ④GOAL_MAINTENANCE(4) → ⑤EXECUTION_CHECK(5) → ⑥RESULT_COLLECTION(6) → ⑦LEARNING_TRIGGER(7) → ⑧CHECKPOINT_DECISION(8)，附 `.next` 属性。
  - `TickStage` 为 `@runtime_checkable Protocol`：约定 `name: str` + `execute(context) -> TickContext`；约束：不得修改传入 context、不得 import runtime_kernel / ocos.self。
- **数据载体（tick_context.py）**：`TickContext` 为 `@dataclass(frozen=True)`，字段 events/attention_snapshot/memory_changes/goal_updates/execution_candidates/execution_results/learning_signals 均为 tuple（不可变）；`with_updates(**kw)`（dataclasses.replace）与 `with_stage_trace(name)` 生成新副本；`to_dict()` 输出计数型摘要（用于 replay/checkpoint，**不序列化实体内容，仅 count**——replay 保真度有限）。工厂 `create_tick_context(tick_id, runtime_state, started_at)`。
- **编排器（pipeline.py）**：`TickPipeline.STAGE_ORDER = tuple(sorted(PipelineStage, key=value))` 冻结顺序；构造时实例化 8 个默认 Stage（**全部缺省依赖为 None → 生产默认空转**）；`register_stage()` 可覆盖（测试用）；`execute_tick(tick_id, runtime_state)`：create_tick_context → 依序执行 stage，异常包装为 `PipelineError(f"Stage X failed at tick N")` 并冒泡 → 8 stage 后执行 `self._agent_driver(tick_id)`（P1-C 收敛设计，未 attach 则跳过，异常同样包 PipelineError）→ `with_updates(completed_at)` + trace "COMPLETE"。明确禁止 Pipeline 思考/决策/生成 Goal。
- **各 Stage 现状（GAP-P2-2 接线后）**：
  | Stage | 注入依赖 | 缺省行为 | 实现度 |
  |---|---|---|---|
  | ① EventIngestionStage | event_bus（需 `ingest(max_events)` API，即 ocos/event.EventBus） | 空事件 () | 真实现（转发） |
  | ② AttentionStage | scoring_engine + candidate_collector（ocos/attention） | attention_snapshot=None | 真实现；但**自身持有 `_current_state` 状态**，与"Stage 无状态"协议约束相悖（P3-2） |
  | ③ MemorySyncStage | memory_hub（需 is_initialized/get_stats） | 空 changes | 真实现（get_stats 快照转发，不写长期记忆） |
  | ④ GoalMaintenanceStage | maintenance_engine + goal_store | goal_updates=() | 真实现；Governance：只 refresh 禁 create；`update_progress/record_attention` 外部注入口存在但**无生产调用方填充** |
  | ⑤ ExecutionCheckStage | task_dag（ocos.task.TaskDAG）+ gateway（PermissionGateway） | 空 candidates | 真实现；gateway 过滤时对每个 candidate 构造 PermissionRequest（capability_id 取 `getattr(cand,'capability_id','unknown')`），`decision.allowed` 为假（含 REQUIRE_APPROVAL）即**静默丢弃候选，不发审批请求**（P3-3） |
  | ⑥ ResultCollectionStage | execution_manager（get_history） | 空 results | 真实现（只读转发） |
  | ⑦ LearningTriggerStage | 无 | 恒 () | **占位逻辑**——"无学习条件判断"，学习信号从不触发（P3-4） |
  | ⑧ CheckpointDecisionStage | 无 | `tick_id % 10 == 0` | 真实现（周期策略硬编码） |
- **输入输出**：输入 tick_id + runtime_state 字符串；输出最终 TickContext（含 stage_traces 追加 "COMPLETE"）。
- **被调用**：runtime_kernel（唯一生产编排入口）；tests/test_phase39_2.py、test_runtime_stages_wiring.py、test_phase39_6.py。
- **关键结论**：daemon 生产装配 `RuntimeKernel()` → `TickPipeline()` 全缺省 → 8 个 stage 全部空转降级，真实认知全部发生在注入的 agent driver 中；管线当前是"协议完整、生产旁路"的骨架。Stage 与 ocos/event(单数)、ocos/events(复数) 两套 EventBus 的 API（ingest vs publish）存在耦合混淆面。
- **验证状态**：【功能实测可通】（stage 协议与顺序被 test_phase39_2/test_runtime_stages_wiring 锁定）；生产依赖注入链路【逻辑不完整】（LearningTrigger 占位、无生产装配注入）。

##### 5. Checkpoint 检查点机制：`checkpoint.py`（116 行，重点）
- **职责**：Phase 39.1 最小 Checkpoint 引擎——Runtime 自身可恢复状态（不含 Goal/Memory/Attention），JSON 持久化 + SHA-256 完整性哈希。
- **数据结构**：`CheckpointRecord(version, runtime_id, tick_id, state, timestamp, integrity_hash)`；`compute_hash()` 对去 hash 字段的 sort_keys JSON 做 SHA-256；`verify_integrity()` 比对；`to_dict()` 自动填 hash。
- **引擎 API**：`save(record)->Path`（文件名 `{runtime_id}_tick_{tick_id:06d}.json`）、`load(runtime_id,tick_id)->Record|None`（不存在/JSON 损坏/哈希不符均返回 None，不抛异常）、`latest_checkpoint(runtime_id)`（glob 前缀 + 文件名倒序逐个验哈希取首个有效）、`has_checkpoint()`。
- **异常处理**：全部吞掉 JSONDecodeError/TypeError 返回 None——静默降级，无告警日志（P4-3）。
- **依赖**：无。**被调用**：recovery_engine.py、runtime_kernel.py、tests/test_phase39_1/2。
- **已知限制**：(a) 文件名零填充 6 位，tick > 999999 后字典序倒序错误（P5-1）；(b) 目录默认 /tmp/ocos_checkpoints，重启易失（P2-4）；(c) 39.4 后实际状态主体移至 recovery/ 的 SnapshotStore，checkpoint 退化为 tick 恢复兼容层。
- **验证状态**：【功能实测可通】（test_phase39_1 覆盖保存/加载/损坏检测）。

##### 6. 生命周期：`runtime_state.py`（40 行）+ `lifecycle.py`（79 行）
- **RuntimeState**：BOOTING/RUNNING/DEGRADED/SAFE_MODE/SHUTDOWN 五态；`ALLOWED_TRANSITIONS` 冻结：BOOTING→{RUNNING}；RUNNING→{SHUTDOWN,SAFE_MODE,DEGRADED}；DEGRADED→{RUNNING,SAFE_MODE,SHUTDOWN}；SAFE_MODE→{SHUTDOWN}；SHUTDOWN→∅。SAFE_MODE 语义 = 处理全部挂起，仅允许 checkpoint/shutdown。
- **LifecycleManager**：持有当前态 + shutdown_requested 标志；`transition(target)` 校验 ALLOWED_TRANSITIONS，非法抛 `InvalidTransitionError`；便捷方法 boot/shutdown/enter_safe_mode/enter_degraded/recover；到 SHUTDOWN 自动置 shutdown_requested。
- **被调用**：runtime_kernel、recovery_engine、recovery（test_phase39_4 import RuntimeState）。
- **已知限制**：Kernel 实际只用了 BOOTING/RUNNING/SHUTDOWN 三态——DEGRADED/SAFE_MODE 有定义无触发点（无 constitution violation 检测接线），PipelineError 不会进入 SAFE_MODE（P3-5）。
- **验证状态**：【功能实测可通】；SAFE_MODE 分支【逻辑不完整】（占位）。

##### 7. 恢复子系统：`recovery_engine.py`（131 行）+ `recovery/`（7 文件 1113 行，重点）
- **recovery_engine.py（39.4 升级版 RecoveryEngine）**：保持 39.1 ABI（`attempt_recovery() -> RecoveryResult`、`create_checkpoint(tick_id,state)`），内部委托 RecoveryManager。attempt_recovery：先 RecoveryManager.start()（认知快照恢复）→ 无 snapshot 时回退旧式 checkpoint；有 snapshot 时 `next_tick_id=restore.resume_tick`。create_checkpoint 同时写 CheckpointRecord 与 RuntimeSnapshot（双写）。`RecoveryResult` 增加 snapshot_id/warnings；`has_pending_approvals` 恒 False（向后兼容占位）。
- **recovery/recovery_manager.py（208 行）**：总编排器。组合 SnapshotStore + EventLog + ExecutionLedger(持久化 ocos_data/executions/ledger.json) + ApprovalStore + CognitiveStateRestore。API：start()/restore_strict()/take_snapshot()/should_snapshot()(100 tick 周期)/log_event/replay_events/track_execution_start|success|failure/should_skip_execution/request_approval/approve/deny_approval/pending_approvals_count/verify/shutdown。
- **recovery/runtime_snapshot.py（171 行）**：`SnapshotReason`(PERIODIC/SHUTDOWN/PRE_ACTION/MANUAL)；`RuntimeSnapshot`（frozen）字段：snapshot_id/tick_id/runtime_state/attention_focus/active_goal_ids/working_memory_keys/pending_executions/pending_approvals/event_log_cursor/timestamp/reason——"认知状态矢量"，与低层 Checkpoint 明确分层。`SnapshotStore` 持久化 ocos_data/snapshots/*.json，`latest()` 按 mtime 排序，`_prune()` 保留最近 20 个。
- **recovery/integrity_verifier.py（150 行）**：恢复前门禁。4 项检查：tick_continuity（snapshot.tick_id ≥ event cursor）、execution_consistency（pending_executions 都在 Ledger）、approval_consistency（pending_approvals 都在 ApprovalStore）、event_log_consistency（snapshot cursor 不超前实际 cursor）。输出 `IntegrityReport(passed/checks/violations/warnings)`。注意：verify(snapshot, strict) 的 strict 参数**在四个检查实现中均未被使用**（形参闲置），strict 语义实际由 CognitiveStateRestore.restore(strict) 在外层处理。
- **recovery/cognitive_restore.py（174 行）**：BOOT → Load latest snapshot → Verify → Restore → Resume 六步。strict=True 时验证不过返回 success=False；否则违规进 warnings 继续降级恢复。`_restore_executions`：Ledger.resolve_on_recovery() 将 RUNNING→UNKNOWN，SUCCESS 的从 pending 剔除；`_restore_approvals`：WAITING 保留、APPROVED/DENIED 清理、找不到的丢弃并告警。resume_tick = snapshot.tick_id + 1。
- **recovery/event_replay.py（180 行）**：Event Sourcing 最小实现。`EventType` 13 类（GOAL_*/AGENT_*/MEMORY_CONSOLIDATED/PERMISSION_*/ATTENTION_SHIFTED/CHECKPOINT_CREATED/RUNTIME_SNAPSHOT）；`CognitiveEvent`（frozen，seq 全局自增）；`EventLog` append-only JSONL（ocos_data/events/event_log.jsonl），`_count_existing` 启动重数 seq；`EventReplayEngine.register_handler/rebuild_state(from_cursor)` 支持按事件类型注册 handler 重建状态（**无生产 handler 注册者**）。
- **recovery/execution_recovery.py（159 行）**：防重复执行账本。`ExecutionStatus`（PENDING/RUNNING/SUCCESS/FAILED/UNKNOWN）；`ExecutionRecord`（含 should_retry/max_retries=3/needs_recovery 属性）；`ExecutionLedger` 内存 dict + JSON 序列化；`should_skip()` 仅对 SUCCESS 为真。
- **recovery/permission_recovery.py（171 行）**：待审批持久化。`ApprovalStatus`（WAITING/APPROVED/DENIED/EXPIRED/CANCELLED）；`PendingApproval`（可 approve/deny/cancel）；`ApprovalStore` 持久化 ocos_data/approvals/pending.json，构造即 `_restore()`，写操作即 `_persist()`。
- **依赖**：均无外部 OCOS 依赖（自包含持久化）。**被调用**：recovery_engine.py（唯一生产链路）、ocos.runtime.__init__ 导出 RecoveryManager、tests/test_phase39_4/5。
- **已知限制**：(a) **recovery_manager.py `shutdown()` 定义两次（L124 与 L200），第二个覆盖第一个**，且第二个不调用 `_save_ledger()` → 经 RecoveryManager.shutdown 关闭时执行账本不落盘（P1-1）；(b) 恢复出的认知矢量（goals/attention/pending）只进入 RestoreResult，runtime_kernel 未回灌到任何活跃组件（P2-2）；(c) RecoveryEngine 构造时 daemon 传入 data_dir=checkpoint_dir=/tmp/ocos_checkpoints → 快照/事件/账本/审批全部落在 /tmp（P2-4）；(d) ExecutionLedger.should_skip 只认 SUCCESS，FAILED 任务恢复后仍进 pending（重试语义靠 needs_recovery 但无人消费）。
- **验证状态**：【功能实测可通】（test_phase39_4/5 覆盖快照/事件/账本/审批/恢复）；shutdown 双定义缺陷属回归隐患。

##### 8. 权限子系统：`permission/`（7 文件 591 行）+ `capability_policy.py`（91 行，重点）
- **架构定位**：PermissionGateway = OCOS "免疫屏障"——不决定做什么，只判断能不能做。链路：ExecutionCheck Stage → ExecutionIntent → PermissionGateway → ExecutionContract → AgentExecutor。
- **permission_level.py**：`PermissionLevel(IntEnum)` OBSERVE(0)/READ(1)/WRITE(2)/EXECUTE(3)，`satisfies()` 向上兼容；`OPERATION_LEVELS` 18 个操作→级别映射（runtime.status…process.start）。冻结约束：禁止 ADMIN 级。
- **permission_request.py**：`RiskLevel`(LOW/MEDIUM/HIGH)、`Caller`(OCOS_EXECUTIVE/MAINTENANCE/EXTERNAL_AGENT，冻结：仅 OCOS_EXECUTIVE 可发起外部请求)；`PermissionRequest`（frozen：capability_id/action/level 必填，resource/caller/risk_level/metadata 可选，空 capability_id/action 抛 ValueError）；`PermissionContext`（frozen：tick_id/goal_id/task_id/requested_by/previous_decisions 决策链）。
- **policy_decision.py**：`DecisionResult`(ALLOW/DENY/REQUIRE_APPROVAL)；`PolicyDecision`（frozen：result/reason/policy_id/audit_required/metadata + allowed/denied/needs_approval 属性 + allow/deny/require_approval 工厂）。
- **builtin_policies.py**：规则引擎，6 级优先级：①External Agent Boundary（EXTERNAL_AGENT 且 level>OBSERVE → DENY）②Protected Resources（resource 前缀 ocos.goal/ocos.self/ocos.memory/ocos.constitution/ocos.runtime.kernel/ocos.identity 且 level≥WRITE → DENY）③未注册 capability → Default-Deny ④Level Guard（请求级别 > 注册上限 → DENY）⑤Risk Approval（HIGH risk → REQUIRE_APPROVAL；level≥WRITE → REQUIRE_APPROVAL）⑥Default ALLOW。`REGISTERED_CAPABILITIES` 13 项（L0 4 项/L1 3 项/L2 2 项/L3 3 项）。
- **permission_gateway.py**：`PermissionGateway.evaluate(request, context)->(PolicyDecision, PermissionTrace)`；audit_required 时入 `_trace_buffer` 并推给 `PermissionTraceConsumer` 协议消费者；`trace_count/flush_traces()/last_trace()`。trace 缓冲**无上限**，长期运行内存增长（P4-1）。
- **permission_trace.py**：`PermissionTrace`（frozen，trace_id=uuid4）记录请求/上下文/决策快照，`record()` 类方法工厂，`to_dict()` 可审计。设计目标：回答"为什么 OCOS 调用了 X"。
- **capability_policy.py**：`CapabilityPolicyProvider` = Runtime↔Governance 桥梁。`check(actor, action, resource, tick_id)` 将 actor 映射 Caller（external_agent/maintenance 之外一律 OCOS_EXECUTIVE），未注册 action 级别推断为 OBSERVE（随后被 default_deny 拒），返回 DecisionResult；`is_allowed()` 便捷方法；暴露 `.gateway`。
- **被调用**：pipeline/stages/execution_check.py（Stage ⑤ 过滤）、capability_policy.py；tests/test_phase39_1/3。**RuntimeKernel 虽构造了 CapabilityPolicyProvider 但从未在 tick 内调用**；daemon/agent 侧执行动作未经过 gateway（仅 stage ⑤ 候选过滤一处，且生产 stage ⑤ 无 DAG 注入 → 权限网关生产旁路，P2-5）。
- **已知限制**：(a) REGISTERED_CAPABILITIES 与 OPERATION_LEVELS 不同步（api.get/web.post/database.update/process.start 未注册 → 默认拒绝）（P4-4）；(b) REQUIRE_APPROVAL 与 ALLOW 的判别在 stage ⑤ 中被合并丢弃，审批闭环需依赖 RecoveryManager.request_approval，但两者无接线。
- **验证状态**：【功能实测可通】（test_phase39_3 全策略分支覆盖）；生产接线【逻辑不完整】。

##### 9. `ocos/runtime/context_manager.py`（407 行）— B1 上下文管理
- **职责**：B1 阶段产物。`WorkingMemory`（会话级临时存储：goals/decisions/executions/processes/preferences/tools 六个 dict/set，frozen 对象整体替换式更新）+ `Context`（frozen 聚合体：goals/tasks/preferences/available_tools/timestamp/schema_version）+ `ContextManager`（从 WorkingMemory+Goal 组装 Context，可选订阅 EventBus 自动重建）。
- **对外能力**：WorkingMemory.add_goal/remove_goal/get_goals(按优先级降序)/update_goal_status/add_decision|execution|process 及对应 get/update/set_preference/register_tool/clear；ContextManager.build_context(goal_ids, additional_tasks)、get_active_context、unsubscribe。
- **正常流程**：build_context → 取 active goals（或指定 ids）→ 从 goal.description 按中文句号/换行**启发式拆任务**（`[{goal_id前8位}] 行文本`）→ 合并 additional_tasks → 冻结 Context。
- **事件集成**：订阅 GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 自动同步 WorkingMemory 并重建 Context；每次读写发 MEMORY_STORED/MEMORY_RETRIEVED 事件（sync=True）。
- **依赖（真实 import）**：ocos.kernel.abi（Goal/Event/EventType/Decision/SCHEMA_VERSION）、ocos.events.event_bus.EventBus、ocos.models.execution.Execution、ocos.models.process.TransformProcess、ocos.logging。
- **被调用**：ocos/engines/* 全系（WorkingMemory）、ocos/agent/engine_bridge.py、tests/test_context_manager 等 15+ 测试文件。是 runtime 包被引用最广的模块。
- **已知限制**：(a) 任务拆解是字符串切分，非语义拆解（设计如此）；(b) `_publish_context_built` 为空实现（pass）；(c) 无线程锁，daemon 多线程读写 WorkingMemory 无保护（P3-7）；(d) `_get_goal` 类线性查找 O(n)。
- **验证状态**：【功能实测可通】（test_context_manager/test_runtime_integration 等大量覆盖）。

##### 10. `ocos/runtime/goal_runtime.py`（480 行）— Goal 生命周期引擎
- **职责**：Phase 18 第一引擎。订阅 9 类 Goal 事件驱动 Goal 生命周期（CREATED→ACTIVE→…），校验转移合法性（委托 ocos.models.goal.GoalStatus.can_transition_to），支持 Superseding、TTL 过期。
- **对外能力**：`set_goal(description,priority,source,parent_goal_id,success_criterion,goal_id)`（发 GOAL_SET 事件，引擎自动 CREATED→ACTIVE）、`transition_goal`（同步预验证后发事件）、`check_expirations`、`configure_expiration`、get_goal/list_active_goals/list_goals/reset、属性 active_goal_count/goal_count/subscription_ids。
- **事件处理**：_handle_goal_set 构造 Goal(CREATED) 并自动 ACTIVE；_handle_goal_updated 仅允许 ACTIVE/PAUSED 且 source 不可改（Theory Invariant）；_handle_superseded 要求被覆盖者为 ACTIVE/PAUSED，且 superseder 若为 CREATED 自动激活；GOAL_EXPIRED 由 check_expirations 驱动。
- **依赖**：ocos.kernel.abi、ocos.events.event_bus、ocos.models.goal.GoalStatus、context_manager.WorkingMemory、ocos.logging。
- **被调用**：tests/test_planning_engine/test_reasoning_engine/test_decision_making_engine/test_runtime_integration/test_goal_arbitration_engine 等。**生产代码无实例化**（engines 目录测试间装配）。
- **已知限制**：订阅 9 事件用 try/except 包裹（事件类型未注册仅 warning），与 ContextManager 同时订阅 GOAL_SET 存在双重处理（同对象覆盖，幂等但冗余）；check_expirations 仅在显式调用时执行，无定时器。
- **验证状态**：【功能实测可通】（多引擎测试覆盖）。

##### 11. `ocos/runtime/decision_runtime.py`（360 行）— Decision 生命周期引擎
- **职责**：Phase 18 第二引擎。Decision 状态机：PROPOSED→COMMITTED→EXECUTED（+REVOKED/SUPERSEDED/EXPIRED 为 terminal）。事件映射 DECISION_VALIDATED→COMMITTED 等 5 对。
- **对外能力**：`form_decision(goal_id,selected_option,reasoning,confidence,decision_id)`（PROPOSED 创建 + DECISION_FORMED 通知事件）、`transition_decision`（预验证→事件）、`configure_expiration/check_expirations`、list/get、`reset()`（直清 `self._wm._decisions`，越界访问私有成员，P4-5 同类问题见 execution/process runtime）。
- **依赖**：ocos.kernel.abi（Decision/DecisionStatus）、events.event_bus、context_manager、ocos.logging。
- **被调用**：tests/test_planning_engine/test_decision_making_engine/test_runtime_engines 等；生产无实例化。
- **已知限制**：文件尾部 `import dataclasses  # noqa` 延迟导入（L360），依赖模块加载顺序才可用，风格脆弱；`_get_decision` 线性扫描。
- **验证状态**：【功能实测可通】。

##### 12. `ocos/runtime/execution_runtime.py`（294 行）— Execution 生命周期引擎
- **职责**：Phase 18 第三引擎。Execution 状态机委托 `ExecutionStatus.can_transition_to`（ocos.models.execution）；终态 SUCCEEDED/FAILED/INTERRUPTED/CANCELLED 时自动打 completed_at。
- **对外能力**：`schedule_execution(decision_id,action_ids,execution_id)`（PENDING，不发事件避免自循环）、`start_execution`、`transition_execution`、`configure_timeout/check_timeouts`（RUNNING 超时→FAILED）、list/get/reset。
- **依赖/被调用**：同上模式（kernel.abi/models.execution/context_manager/EventBus）；仅测试消费。
- **验证状态**：【功能实测可通】。

##### 13. `ocos/runtime/process_runtime.py`（276 行）— TransformProcess 生命周期引擎
- **职责**：Phase 18 第四引擎。Process 状态机 CREATED→RUNNING→COMPLETED/FAILED（本地 `_VALID_TRANSITIONS`，不委托模型层）；PROCESS_CREATED 为通知事件不触发转移。
- **对外能力**：create_process(process_type,input/output_addresses,steps,confidence,metadata)/start_process/complete_process/transition_process/get_process/list_processes/reset、active_process_count。
- **依赖/被调用**：ocos.models.process（TransformProcess/ProcessState/ProcessType/ProcessStep）+ kernel.abi + EventBus + WorkingMemory；tests/test_simulation_engine/test_planning_engine 等。生产无实例化。
- **验证状态**：【功能实测可通】。

##### 14. `ocos/runtime/attention_engine.py`（417 行）— B2 注意力评分
- **职责**：对 `Observation` 计算 AttentionScore = w_n×Novelty + w_r×GoalRelevance + w_u×Urgency（默认 0.3/0.4/0.3）。
- **结构**：`ContentAnalyzer` 抽象基类（三个 score_* 方法）；`DefaultContentAnalyzer`（字符 bigram 重叠率，CJK 友好；紧急/低紧急关键词表中英双语；滚动 100 条历史）；`FrequencyAnalyzer`（内容 hash 频率衰减 1/count，不评相关性/紧急度）；`AttentionEngine`（score/score_with_context/filter(threshold,max_results 按composite降序)/get_score 缓存/reset/set_weights 动态调权）。
- **注意**：GAP-P3-8 明确移除了 SemanticContentAnalyzer 的占位承诺（从未实现）——诚实降级处理。
- **依赖**：ocos.kernel.abi（Observation/Goal/SCHEMA_VERSION）、ocos.logging；score_with_context 内部延迟 import ocos.runtime.context_manager.Context。
- **被调用**：**ocos/attention/focus.py L22（生产消费）**、tests/test_attention_engine/test_attention_focus。
- **已知限制**：_observation_cache 无淘汰（长时运行增长）；FrequencyAnalyzer.score_novelty 用 `hash(str(content))`——Python 哈希随机化跨进程不稳定（P4-6）。
- **验证状态**：【功能实测可通】。

##### 15. `ocos/runtime/scheduler.py`（454 行）— B3 优先级调度器（tick 内事件分发器）
- **职责**：AUD-F2 裁决明确：本模块 = tick 内 stage 级事件分发器（与 runtime_scheduler 包是两套东西，不合并）。订阅 EventBus 事件 → 计算优先级（Attention composite 或事件类型基线 GOAL_SET=0.8 等，payload.scheduler_priority 可覆盖）→ heapq 优先队列（-priority, seq tiebreaker）→ tick() 消费 → RegistryAdapter 分发 EngineInfo.execute。
- **对外能力**：ScheduleType(ONE_SHOT/PERIODIC/CONDITIONAL)、ScheduleItem（frozen，timeout_seconds 默认 60）、EngineInfo、RegistryAdapter（register/unregister/get/find_by_event_type）、Scheduler.subscribe_additional/unsubscribe_all/tick(max_items=1)/tick_all/schedule_periodic/schedule_conditional/cancel(item_id)/reset。
- **依赖**：ocos.kernel.abi、ocos.events.event_bus、ocos.logging。
- **被调用**：tests/test_scheduler.py；**生产无实例化**（daemon 未装配）。
- **已知限制**：(a) **PERIODIC 任务的 interval_seconds 实际无效**——`_reschedule_if_periodic` 执行完立即重新入队，tick 不检查 next_run_at，周期任务每 tick 都会执行（P2-6）；(b) CONDITIONAL 的 condition_fn_name 从未被求值，条件调度未实现（P3-8）；(c) `_on_event` 中无匹配 engine 时静默 return。
- **验证状态**：【功能实测可通】（test_scheduler.py）；周期/条件语义【逻辑不完整】。

##### 16. `ocos/runtime/policy_engine.py`（602 行）— B4 安全策略引擎
- **职责**：对 Action 做 `evaluate(action_type, params) -> PolicyResult`。规则模型：Policy（priority/action_type_pattern/多条 PolicyRule AND 语义）→ 12 种 RuleOperator（EQ/NEQ/GT/GTE/LT/LTE/IN/NOT_IN/STARTSWITH/CONTAINS/EXISTS/NOT_EXISTS），`_get_nested_field` 支持点路径与数组索引。
- **默认策略 5 条**：unknown-action-type（白名单 14 种 action_type）、constitution-protect（禁写 kernel.constitution/abi/event_schema）、decision-required（execute_engine 必须带 decision_id）、no-emergency-override（emergency_halt 下仅允许 emergency_recover/emit_observation）、action-rate-limit（每分钟同类型 ≤60 次，通过注入 `_internal_rate_exceeded` 内部字段实现）。
- **评估顺序**：按 (-priority, ALLOW 优先于 DENY, name) 排序；首个触发 DENY 即拒（返回 violated_rules），触发显式 ALLOW 则短路放行；否则默认 allowed。
- **治理集成**：订阅 GOVERNANCE_APPROVED（add/enable 策略）/GOVERNANCE_REJECTED（disable/remove）动态调整。
- **依赖**：ocos.kernel.abi、ocos.events.event_bus、ocos.logging。
- **被调用**：tests/test_governance_engine.py、tests/test_policy_engine.py。**生产无实例化**（ocos/engines/policy_engine.py 是另一个同名但不同的 PolicyEngine——trace 型，勿混淆）。
- **已知限制**：`(TypeError, ValueError)` 一律返回规则不匹配——恶意/畸形 params 可能使保护规则失效（fail-open，P3-9）；rate limit 只在 DENY/ALLOW 触发时 `_record_action`，未触发策略的动作也记录，但 `_check_rate_exceeded` 的 `> 60` 判定发生在评估前，窗口边界粗糙。
- **验证状态**：【功能实测可通】（test_policy_engine.py 覆盖规则算子/默认策略/rate limit）。

##### 17. `ocos/runtime/resource_manager.py`（450 行）— B5 资源管理
- **职责**：CPU/MEMORY/GPU/TOKEN/STORAGE 五类资源池：request（类型校验→amount>0→可用量→holder 配额，四级检查，拒绝原因精确化）/release/release_by_holder/get_usage/get_slots/set_quota/remove_quota/reset。
- **TTL 回收**：`_slot_is_expired`（acquired_at + ttl_seconds）惰性清理（request/get_usage/get_slots 前自动执行）+ 可外部主动触发。
- **事件**：拒绝时 RESOURCE_EXHAUSTED、释放/TTL 过期时 RESOURCE_RELEASED。
- **依赖**：ocos.kernel.abi（Event/EventType/SCHEMA_VERSION）、ocos.logging。
- **被调用**：tests/test_resource_*（B5 测试）、AdaptiveController（作为必选依赖）。**生产无实例化**。
- **已知限制**：**L289/405/440 调用 `self._event_bus.emit(...)`——ocos/events.EventBus 与 ocos/event.EventBus 均无 emit 方法**，一旦注入真实 EventBus 即 AttributeError（P1-2）；无锁（P3-7 同类）。
- **验证状态**：【功能实测可通】（测试中 event_bus 用带 emit 的桩或 None）；事件发射路径【逻辑不完整】（API 不匹配）。

##### 18. `ocos/runtime/adaptive_control.py`（583 行）— B6 自适应调节
- **职责**：根据资源使用率 + 风险等级调节 6 个运行时参数（simulation_depth/learning_rate/attention_threshold/scheduler_max_queue/resource_cpu_limit/resource_memory_limit），PARAM_BOUNDS 硬边界 clamp。
- **调用权规则（文档冻结）**：auto_adapt 仅允许 EventBus 回调（RESOURCE_EXHAUSTED/RELEASED 订阅实现）与 Runtime Scheduler 安全上下文调用；外部只读 get_config()。
- **降级策略**：memory>90% → queue/=2；memory>80% → depth-2；cpu>80% → threshold+0.1；gpu>80% → lr×0.5；risk HIGH/CRITICAL → lr×0.3 + threshold+0.2。恢复策略：三项资源均 <50% 且距上次恢复 ≥30s（RECOVERY_COOLDOWN_SECONDS）→ 各参数朝默认值单步恢复；本次有降级则不恢复。
- **数据结构**：AdaptiveConfig（frozen 快照）、Adaptation（frozen，param/old/new/reason/trigger_event_id 可审计）。
- **依赖**：ocos.kernel.abi、ocos.logging；ResourceManager（必选）、PolicyEngine（可选，`get_risk_level()` duck-typing，异常回退 NORMAL）。
- **被调用**：tests/test_adaptive_control.py。**生产无实例化**。
- **已知限制**：L525 `self._event_bus.emit(...)` 同 P1-2（EventBus 无 emit）；本文件 `RiskLevel`(LOW/NORMAL/HIGH/CRITICAL) 与 permission.RiskLevel(LOW/MEDIUM/HIGH) 同名不同义，易混淆（P4-7）；构造函数若 event_bus 为 None 则完全跳过订阅，auto_adapt 只能手动触发。
- **验证状态**：【功能实测可通】（test_adaptive_control.py 覆盖降级/恢复/clamp/冷却）；事件链路【逻辑不完整】。

##### 19. `ocos/runtime_scheduler/`（8 文件约 1050 行）— Phase 51.2 独立任务心跳调度器
- **定位（AUD-F2 分工裁决）**：独立任务心跳调度器（CognitiveClock/PriorityQueue/Backpressure/WorkerManager，Phase 51.2 契约由 test_phase51_2 锁定），**当前无生产消费者**；候选接入点 = ResidentRuntime 任务队列需要背压时。与 ocos/runtime/scheduler.py（B3）非重复实现。
- **边界契约**：RS51-01 Scheduler≠Brain（不能 create_goal/modify_memory/make_decision）；RS51-02 Tick 连续无重复无丢失；RS51-03 用户请求优先；RS51-04 背压降级不崩溃；RS51-05 持久化联动。
- **scheduler_types.py（229 行）**：`Priority(IntEnum)` CRITICAL(0)/HIGH/MEDIUM/LOW/BACKGROUND(4)；`Tick`（frozen+order，number 单调，timestamp compare=False，支持 +/- 运算）；`SchedulerTask`（stage/priority/tick/fn/status/retries/max_retries=2/timeout_seconds=10）；`TickSchedule`（every/offset/last_run + should_run）；`SchedulerStatus`（含 BACKPRESSURED/DEGRADED）；`SchedulerStats`（含 skipped_ticks/duplicate_ticks 审计字段）；`Worker/WorkerStatus`；`BackpressureState`（high=100/low=30 水位 + should_reject：active 时拒 LOW/BACKGROUND）。
- **cognitive_clock.py（78 行）**：advance() 单调 +1（RS51-02 不跳号）、advance_n、register_schedule/due_schedules/mark_completed/reset；on_tick 回调。
- **priority_queue.py（103 行）**：heapq 实现，(priority.value, FIFO counter) 排序；push/pop/peek/remove(O(n) 重建堆)/cancel_all/by_priority/drain_priority。
- **task_scheduler.py（259 行）**：主循环 run(max_ticks)：advance → on_tick → _enqueue_due_schedules（到期任务入队，**被背压拒绝时不 mark_completed → 下一 tick 重试**，即 MEDIUM/LOW 周期任务被推迟而非丢弃）→ _check_backpressure（水位线切换状态）→ _drain_queue（同步串行执行全部到期任务）→ 每 checkpoint_interval(1000) tick 触发 on_checkpoint。`_execute`：异常时 retries<max 则重新入队（PENDING），否则 FAILED + on_task_fail；finally 更新 avg_task_latency（增量平均）。`get_state/set_state` 支持 RS51-05 持久化往返。stop/pause/resume。
- **backpressure.py（97 行）**：BackpressureManager.check(task)——CRITICAL/HIGH 放行，MEDIUM 标记 BACKPRESSURED 推迟（deferred_count++），LOW/BACKGROUND 拒绝（rejected_count++）；update(queue_depth) 水位触发/解除；**drain_deferred() 返回空列表——推迟任务的恢复机制未实现（占位，P3-10）**。注意 TaskScheduler 实际用 BackpressureState.should_reject，未用 BackpressureManager 类。
- **worker_manager.py（126 行）**：per-stage Worker 账本（assign/release/is_busy/busy_stages/check_timeouts——只标记 TIMEOUT 状态，无真实线程可杀）/stats/get_state/set_state。**TaskScheduler 未使用它**——"模块执行隔离"只是记账，_drain_queue 是同步串行执行，Stage A 死循环同样阻塞 Stage B（文档承诺与实现不符，P2-7）。
- **scheduler_health.py（93 行）**：check(current, stats)——tick gap/重复检测（skipped_ticks/duplicate_ticks 计数）、队列深度、平均时延、失败率 >10%、BACKPRESSURED/DEGRADED 状态告警；返回 {tick, healthy, issues, warnings, ...}。只报告不干预。
- **依赖**：包内自洽（scheduler_types 认知），无外部 OCOS import。
- **被调用**：**ocos/daemon/__init__.py L143/L307（生产）**：构造 PriorityQueue 用于目标队列背压记账（push SchedulerTask(stage="goal_queue", fn=lambda: description)——只作深度审计，不 pop 执行）；tests/test_phase51_2.py 全覆盖。TaskScheduler/CognitiveClock/WorkerManager/BackpressureManager/SchedulerHealth/BackpressureManager 无生产消费者。
- **已知限制**：(a) set_state 恢复 current_tick 但不恢复 start_tick → elapsed 失真（P4-8）；(b) TaskScheduler 无 sleep（除暂停态 0.001s）——max_ticks=0 无限循环会 100% CPU 空转（P3-11）；(c) WorkerManager.check_timeouts 只改状态不回收任务。
- **验证状态**：【功能实测可通】（test_phase51_2.py 按契约锁定）；背压恢复与 Worker 隔离【逻辑不完整】。

---


#### 分组 审计分组 W5：engines 认知引擎 + decision 决策 + planning 规划 + cognitive_loop 认知循环

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/engines/（18 文件）
**模块路径范围**：`/home/laogao/Documents/trae_projects/ocos/ocos/engines/`

**模块职责**：认知引擎集合。三类引擎并存：
1. **信息-知识桥接引擎**（信息平面 → 知识平面）：ConsolidationEngine（合并信息为知识候选）、PromotionEngine（晋升 + Governance 审批）、ForgettingEngine（TTL/审批式遗忘）、RetrievalEngine + AddressResolver（跨 Store 语义查询路由）。
2. **Phase 19 九大能力引擎**（为 TransformProcess 提供能力逻辑，统一 `execute(process, ...)` 接口）：ReasoningEngine、PlanningEngine、DecisionMakingEngine、PolicyEngine、GoalArbitrationEngine、SimulationEngine、LearningEngine、ReflectionEngine、PredictionEngine。
3. **叙事引擎（Phase 27 OpenTale）**：WriterEngine + NarrativePipeline + TextGenerator（LLM Provider 抽象层）。

**对外提供能力**：
- 每个引擎模块在尾部声明模块级 `__manifest__ = EngineManifest(...)`（`ocos/platform/engine_manifest.py` 的 `EngineDiscoverer` 扫描、`engine_loader.py` 动态加载）。18 文件中 16 个有 manifest；`text_generator.py` 与 `narrative_pipeline.py` 无（它们是 WriterEngine 的内部支撑，不作为独立引擎加载）。
- 自定义扩展点（模块级注册表）：`register_decision_strategy`、`register_planning_strategy`、`register_inference_handler`、`register_rule_evaluator`、`register_default_arbitrator`。
- 便利函数 `make_decision(engine, process, strategy, options, **context)`（decision_making_engine.py:291）。

**内部子模块**：见第二节文件索引。

**输入输出**：
- 能力引擎输入为 `TransformProcess`（`ocos/models/process.py`，校验 `process.process_type` 必须匹配各自 ProcessType，如 DECISION/PLANNING/REASONING/POLICY/ARBITRATION/SIMULATION/LEARNING），上下文经 dict 注入（如 candidates、examples、learn_fn、predict_fn、step_fn、reflect_fn 等可调用对象）；输出为各文件自定义的 `RuntimeResult`（8 个文件各有一份字段略不同的同名类，互不共享）。
- 桥接引擎输入为 `InformationMetadata` / `UniversalAddress`（`ocos/models/information.py`），输出 `(bool, str)` 二元组 + 事件发射。

**正常工作流程**（以决策闭环为例）：
- engines 内决策流：`DecisionMakingEngine.execute(process)` → `_resolve_strategy`（override > process.metadata["strategy"] > SCORING）→ `_evaluate`（自定义 handler 优先，否则 `_default_evaluate` 按权重加总 score 选优）→ 写入 `DecisionMakingTrace` → publish `INFORMATION_TRANSFORMATION_STARTED` 事件。
- 桥接流（promotion 为例）：`promote(metadata)` → 校验 VALIDATED → Governance 门控（PRINCIPLE/POLICY 目标层级先返回 promotion_id 进入 `_pending` 待批）→ `PromotionRuleEngine.check_trigger` → `KnowledgeABI.create_unit` → 发射 `INFORMATION_STATUS_CHANGED`（VALIDATED→DEPRECATED）+ `KNOWLEDGE_PROMOTED`。

**异常处理逻辑**：
- 能力引擎对 process_type 不匹配一律返回 `RuntimeResult(success=False, message="Not a XXX process")`，不抛异常。
- 自定义 handler 异常被捕获并转为 errors 列表/失败 detail（reasoning_engine.py:265-266、policy_engine.py:253-261）；但 LearningEngine.learn 与 PredictionEngine.predict 的注入函数异常**不捕获**，直接向调用方传播。
- 桥接引擎用返回值 `(False, 错误消息)` 表达失败，EventBus 为可选依赖（None 时静默跳过 `_emit`）。
- WriterEngine 通过 `ocos/agent/retry_policy.safe_execute` + `CircuitBreakerState`（max_retries=2, base_delay=0.5）包裹内部策略执行，事件发射失败仅 debug 日志不中断（writer_engine.py:619-631）。

**依赖哪些其它 OCOS 模块（真实 import）**：
- `ocos.kernel.abi`（Event/EventType）、`ocos.logging`、`ocos.events.event_bus`（EventBus）、`ocos.runtime.context_manager`（WorkingMemory）
- `ocos.models.*`：information、process、decision_making、goal_arbitration、learning、planning、policy、prediction、reasoning、reflection、simulation
- `ocos.knowledge.*`：knowledge_abi、knowledge_ontology、promotion_rules（consolidation/promotion）
- `ocos.platform.engine_manifest`（EngineManifest）
- `ocos.agent.retry_policy`（writer_engine：safe_execute/CircuitBreakerState）
- 内部相互依赖：retrieval_engine → address_resolver；writer_engine → narrative_pipeline + text_generator

**被哪些 OCOS 模块调用（grep "from ocos.engines" 反查，排除 __pycache__ 与测试）**：
- `ocos/agent/engine_bridge.py:109-125`：将 PlanningEngine/ReasoningEngine/WriterEngine 注册进 ENGINE_REGISTRY（幂等注册 + EngineBridge 兜底，防循环导入）
- `ocos/daemon/factory.py:159-163`（build_cognitive_engines）：实例化 Reasoning/Planning/DecisionMaking/Reflection/Learning 五引擎注入 MasterAgent（AUD-F9 修复：此前走 stub 降级）
- `ocos/execution/bridge.py:942,1048`：DecisionBridge 使用 text_generator 的 get_text_generator/_read_llm_config
- `ocos/interaction/converse.py:507,750,770,945`：CLI 对话使用 TextGenerator
- `ocos/reflection/self_review.py:367`、`ocos/interaction/cli/commands/growth.py:36`：使用 get_text_generator
- 测试覆盖：engines 下 16 个可测模块均有对应 test_*.py（test_consolidation_engine 等 16 个文件）

**已知限制**：
- 九大能力引擎中多数内置逻辑为**结构化占位**（诚实标注）：ReasoningEngine `_default_reason` 只生成 trace 文本不做真实推理（reasoning_engine.py:282-290 注释"无实际 LLM 调用"）；PlanningEngine `_default_plan` 按策略固定步数生成模板步骤；DecisionMakingEngine 的 MAJORITY/OPPORTUNITY_COST/PARETO 三策略退化为 max(total_score)（decision_making_engine.py:265-274）；SimulationEngine.run_monte_carlo 声称"每次微调参数"但实际只换 scenario_id，参数完全不变（simulation_engine.py:115-134）。
- 默认依赖注入：KnowledgeABI 缺失时 consolidation/promotion 只发事件不落知识库，事件里 knowledge_unit_id 为空串仍宣称 DEPRECATED（consolidation_engine.py:128-155）。
- `_DEFAULT_ARBITRATORS`/`_STRATEGY_HANDLERS` 为进程级全局注册表，无隔离（多实例互相污染）。
- 见第三节风险清单 P1-P5。

**验证状态**：【功能实测可通】—— pytest 实测：engines 相关 17 个测试文件全部通过（test_consolidation/forgetting/promotion/retrieval/address_resolver/policy/reasoning/goal_arbitration/learning/reflection/prediction/simulation/writer/decision_making/planning/narrative_pipeline 共 270 项通过）；唯一失败为 test_text_generator::test_auto_provider_openai_when_key_set（P3-01，环境耦合问题，非功能缺陷）。

##### 2. ocos/decision/（8 文件）
**模块路径范围**：`/home/laogao/Documents/trae_projects/ocos/ocos/decision/`

**模块职责**：Phase 43 Personal Decision Intelligence —— "在当前情境下我应如何选择"。输入 Goal+Self Model+Personal Wisdom+World Model+Context，输出 **DecisionProposal（提案，不是自动执行）**。核心边界：D43-01 Decision≠Goal、D43-02 Decision≠Execution（必须经 Capability→Permission→Execution）、D43-03 Wisdom≠Rule。

**对外提供能力**：`__init__.py` 统一导出 12 个类型 + 6 个管道组件：DecisionContext/DecisionOption/RiskAssessment/ValueEvaluation/DecisionProposal/DecisionTrace/DecisionResult；ContextBuilder、OptionGenerator、RiskEngine、ValueModel、DecisionTracer、DecisionValidator。

**内部子模块**：decision_types（类型）、context_builder（上下文聚合）、option_generator（选项生成）、risk_engine（风险）、value_model（价值）、decision_trace（审计追踪）、decision_validator（边界守卫）。

**输入输出**：
- ContextBuilder 经 set_* 注入各层文本摘要 → `build(tick_id)` 产出 frozen `DecisionContext(context_id="ctx:{tick}", ...)`。
- OptionGenerator.generate(context) → 基线 defer 选项 + wisdom_hints 推断选项（DIRECT_ACTION, confidence=0.7）+ investigate 选项（需 goal+world 均非空）。
- RiskEngine.assess / ValueModel.evaluate → 单选项风险评估/六维价值（默认权重 SAFETY .25 > ALIGNMENT .20 > RELIABILITY .20 > EFFICIENCY .15 > LEARNING .10 > NOVELTY .10）。
- DecisionValidator.validate(proposal) → DecisionValidationResult(is_valid, violations)，5 类违规：EMPTY_PROPOSAL / PROPOSES_GOAL / DIRECT_EXECUTION（触发词启发式）/ WISDOM_AS_RULE（wisdom 来源且 confidence>0.95）/ EXCESSIVE_RISK（>0.9）。

**正常工作流程**：Context → Options → Risk+Value → 排序（value-risk）→ DecisionProposal(state=PROPOSED) → Validator 校验 → DecisionTracer.record 留痕。

**异常处理逻辑**：无异常抛出路径，全部以返回值表达；validator 用启发式触发词，无法识别未列入词表的越界描述（已知局限，代码注释自认）。

**依赖哪些其它 OCOS 模块**：仅 `ocos.decision` 内部互相依赖，**零外部 OCOS 依赖**（decision_types 只用标准库）——刻意设计为独立可复用。

**被哪些 OCOS 模块调用（grep "from ocos.decision"）**：
- `ocos/cognitive_loop/decision_pipeline.py:18-31`（唯一生产代码调用方，GAP-P1-1 接线）
- `ocos/tests/test_phase43.py`（20 项测试）

**已知限制**：
- `decision/__init__.py:1-23` 与 `cognitive_loop/__init__.py:5-10` 明确自述：**本链为"已接好线的备用引擎"，当前无生产消费者**；生产 tick 决策 = AgentRuntime step7/8 + DecisionBridge（RuntimeKernel 驱动）。
- DecisionOption 的 risk_score/value_score 字段是生成时的静态默认值，RiskEngine/ValueModel 的计算结果**没有回写**到 option（frozen dataclass），因此 `DecisionProposal.recommended`（按 value_score-risk_score 排序，decision_types.py:204-215）与管道实际排序结果可能不一致。
- OptionGenerator 的 defer 基线选项（confidence=1.0, risk=0, 价值≈0.695）几乎在 value-risk 排序中恒胜出 wisdom 选项（≈0.26），导致认知循环中决策大概率是"推迟"（设计上保守，但使 decision 链在备用路径中实际产出动作的可能性极低）。

**验证状态**：【功能实测可通】——test_phase43.py 20 项全过；但作为整体链路属"备用引擎"（无生产消费者），生产价值取决于未来是否升级为主循环 fallback（R4-B Outbox 后评估，见 decision/__init__.py 注释）。

##### 3. ocos/planning/（6 文件）
**模块路径范围**：`/home/laogao/Documents/trae_projects/ocos/ocos/planning/`

**模块职责**：Phase 27 Planning Intelligence —— Goal → TaskDAG → 验证/模拟 → 执行策略选择。宪法约束：Task 引用 Goal（外键）不持有 Goal；MAX_DAG_DEPTH=5、MAX_PARALLEL_WIDTH=4；禁止导入 ocos.self（`__init__.py` 与 models.py 文档声明，实际由 ocos/tests/test_import_rules.py 强制）。

**对外提供能力**：models（Task/TaskDAG/Plan/TaskStatus/ExecutionStrategy + 拓扑预算常量 + VALID_AGENT_TYPES）、TaskDecomposer.decompose(goal)→TaskDAG、PlanValidator.validate/simulate(dag)→PlanValidationReport、validate_plan(plan)（Plan 级 Gate，GAP-P3-6 由原 planning/validator.py 并入）、PlanSimulator.simulate(plan)→SimulationResult、StrategyEngine.select/explain/validate_parallel_width。

**输入输出**：
- Task：frozen dataclass，id="TASK-{8hex}"，goal_id 外键，agent_type ∈ {writer,researcher,reviewer,data_processor,code_executor,summarizer,planner}，priority 1-5，retry_policy ∈ {no_retry,retry_3x,retry_with_fallback}；`__post_init__` 严格校验（空 id/描述、非法 agent_type、priority 越界、duration≤0 均 raise ValueError）。
- TaskDAG：tasks dict + edges 列表，`object.__setattr__` 注入 RLock（models.py:130-131），所有公开方法持锁；Kahn 算法 validate_acyclic/topological_order/parallel_groups。
- PlanValidator 报告：ValidationIssue(code 如 DAG-01/DAG-02/DAG-03/DAG-04/CAP-01/CAP-02/CAP-03/DEP-01/DEP-02, severity ERROR/WARNING/INFO)；simulate 模式附 simulated_execution_order。

**正常工作流程**：UserGoal → TaskDecomposer.decompose（按 GoalDomain 选模板：WRITING 大纲→人物→两章→修改；ANALYSIS/RESEARCH/DEVELOPMENT 各 3 步；串行连接，约束注入描述前 2 条）→ `_enforce_budgets` 强制深度/宽度 → PlanValidator/PlanSimulator → StrategyEngine.select（全串行链→SEQUENTIAL，单层多任务→PARALLEL，混合→PRIORITY_DRIVEN）→ orchestration/engine.py 执行。

**异常处理逻辑**：decompose 超 `MAX_DAG_DEPTH`/宽度直接 raise ValueError（decomposer.py:107-118）；PlanValidator 全部走报告不抛异常（registry.list_all 异常时降级用 VALID_AGENT_TYPES 全集，plan_validator.py:118-125）。

**依赖哪些其它 OCOS 模块**：`ocos.goal.models`（GoalDomain, UserGoal，仅 decomposer.py:16）。planning/__init__ 只导出 models（decomposer/validator/simulator/strategy 不在包导出面，调用方按子模块路径 import）。

**被哪些 OCOS 模块调用（grep "from ocos.planning"）**：
- `ocos/agent/agent_runtime.py:929,944`（tick 内动态 import TaskDecomposer/Task/TaskDAG）
- `ocos/agent/master_agent.py:827`（Task）
- `ocos/agent_orchestration/registry.py, selector.py, supervisor.py`、`ocos/agent_orchestration_autonomous.py`、`ocos/collaboration/agent_collaboration.py`、`ocos/orchestration/engine.py:34`（Task/Plan/TaskStatus）、`ocos/interaction/api/routes/plan.py`、`ocos/interaction/cli/commands/plan.py`、`ocos/interaction/repl/commands/plan.py`
- 测试：test_execution_bridge.py、test_orchestration_engine.py、test_pending_store.py

**已知限制**：
- decomposer 模板串行（无并行分支），并行宽度约束实际不会被模板触发（防呆性质）。
- PlanSimulator.simulate 对空 DAG：validate_acyclic 空图返回 True → parallel_groups 返回 [] → PARALLEL 策略 `_estimate_duration` 的 `max()` 对空序列抛 ValueError（simulator.py:111-117），未防护。
- validate_plan（Plan 级）与 PlanValidator.validate（DAG 级）两套接口并存，`validate_no_self_module()` 为空占位（plan_validator.py:346-352，真实检查在 test_import_rules.py）。

**验证状态**：【功能实测可通】——通过 test_execution_bridge.py/test_orchestration_engine.py/test_pending_store.py 间接覆盖 + 本组 134 项测试全过；decomposer/validator/simulator 无独立单测文件（仅集成路径覆盖）【信息缺失：planning 专属单测】。

##### 4. ocos/cognitive_loop/（10 文件）
**模块路径范围**：`/home/laogao/Documents/trae_projects/ocos/ocos/cognitive_loop/`

**模块职责**：Phase 46 Cognitive Operating Loop Integration —— 将 Phase 39-45 器官连成闭环 Perception→Attention→Context→Decision→Action→Learning→Health。核心边界：CL46-01 Loop≠Autonomy、CL46-02 Health≠Self-Rewrite、CL46-03 Perception≠Truth、CL46-04 Learning≠Drift。

**定位裁决（AUD-F13 选项 A，2026-08-30，`__init__.py:5-10` 明文）**：本包 = 自治循环编排视图（AutonomousLoop 激活路径），**生产 tick 决策 = AgentRuntime step7/8 + DecisionBridge，不经过 LoopOrchestrator**——本链是"已接好线的备用引擎"。

**对外提供能力**：LoopOrchestrator（tick() 每 tick 跑 7 阶段）、7 个协调器/桥、loop_types 全部类型、loop_summary() 统计。

**内部子模块**：loop_types（LoopPhase/TickOutcome/LoopContext/HealthSignal/ModuleHealth/CognitiveHealthReport）、perception_bridge、attention_coordinator、context_synchronizer、decision_pipeline、action_controller、learning_coordinator、health_monitor、loop_orchestrator。

**输入输出**：
- LoopOrchestrator.tick(perception_input: str) → LoopContext（tick_id 自增；字段含 perception_input/attention_focus/attention_weight/self_snapshot/active_wisdom/world_state/active_goals/decision_proposal/decision_approved/selected_capability/action_result/learning_outcome/consolidation_tick）。
- ContextSynchronizer 通过 set_*_provider(fn) 注入 Phase 40/41/42/39 的真实数据源回调（默认 None → 不同步）。
- ActionController 默认 `_capability_selector/_execution_bridge=None`，`act()` 在未注入时**直接模拟执行**（action_controller.py:57-62，返回 f"[{capability}] response to: ..."）。

**正常工作流程**（loop_orchestrator.tick）：
1. PERCEIVING：perception.receive 入队 → 2. ATTENDING：attention.evaluate（感知事件>活跃目标>默认 idle）→ 标记焦点事件 processed → 3. SYNCING：synchronizer.sync(ctx) → 4. DECIDING：decision_pipeline.process（GAP-P1-1 已接真实 ocos.decision 组件链）→ 5. ACTING → 6. LEARNING：learning.consolidate（禁词越界检查→IDENTITY_DRIFT_BLOCKED）→ 7. HEALTH_CHECK（每 10 tick；Phase 62d 每 tick poll 认知耦合桥）→ 依 outcome 记 TickOutcome，contexts 保最近 500。

**异常处理逻辑**：全链**无 try/except**，任何注入的 provider 回调或 decision 组件抛异常将直接中止 tick 并向上传播（LoopOrchestrator.tick 无兜底）；health_monitor 的 propose_repair 严格限定 ALLOWED_REPAIRS 白名单（CL46-02）。

**依赖哪些其它 OCOS 模块**：`ocos.decision`（decision_pipeline.py:18-31，唯一跨包依赖）；loop_types/perception_bridge 等仅标准库。Phase 62d 的 CognitiveCouplingBridge 经 `inject_coupling_bridge` 以鸭子类型注入（loop_orchestrator.py:54,62-65）。

**被哪些 OCOS 模块调用（grep "from ocos.cognitive_loop"）**：
- `ocos/autonomous_runtime/autonomous_loop.py:16-17`（**唯一生产调用方**：AutonomousLoop 包装 LoopOrchestrator，含 wake/sleep/idle/reflect/tick_many/dispatch_actions/set_action_handler）
- 测试：test_phase46.py（29 项）、test_phase62d_loop_coupling.py、test_thin_coverage_e2e.py

**已知限制**：
- 未处理的感知事件永不被标记 processed（attention 只标记焦点事件），`flush_processed` 过滤条件 `not e.processed or e.tick_id > max_age_ticks` 会**保留全部未处理事件**（perception_bridge.py:85-92），长期运行 `_events` 无界增长（P3）。
- attention._history 超限截断逻辑 `>100 → [-50:]` 与 health `>200 → [-100:]`、experience `>1000 → [-500:]` 均为跳变式清理，非环形缓冲（无害但不精确）。
- ActionController 模拟执行、ContextSynchronizer 默认无 provider——开箱即用时循环大部分阶段是占位行为（代码注释诚实标注"模拟"）。

**验证状态**：【功能实测可通】——test_phase46.py 29 项 + test_phase62d_loop_coupling.py + test_thin_coverage_e2e.py 全过（GAP-P1-1 后 decision 链真实可跑）；但作为整体属备用循环，生产路径不走此链。

##### 专项说明：DecisionBridge 决策闭环对应实现
**DecisionBridge 不在 decision/ 或 engines/ 中，位于 `ocos/execution/bridge.py:116`（class DecisionBridge，R4-A "自治循环决策 → 真实任务执行铰链"），由 `ocos/execution/__init__.py` 导出（DecisionBridge/BridgeReport/ActionVerdict）。**
- 生产接线：`ocos/daemon/factory.py:274`（build_execution_bridge）→ `ocos/agent/agent_runtime.py:1065`（attach_decision_bridge）→ `agent_runtime.py:1182`（step7 `bridge.execute_dag_task(task)`：只读 analyze/verify → AUTO 真实执行；create/modify/execute → ASK 待批 R4-B Outbox，见 `ocos/execution/pending.py`）。
- engines/ 中的对应物是 `ocos/engines/decision_making_engine.py` 的 DecisionMakingEngine（Phase 19 能力引擎，daemon/factory.py:159 装配进 MasterAgent 的 "decision_engine" 键），它与 DecisionBridge **互补而非取代**（decision_making_engine.py:12 自述"与 Phase 18 DecisionRuntimeEngine 互补"）。
- decision/ + cognitive_loop/decision_pipeline 组成第三条决策链（备用，无生产消费者）。
- 测试佐证：test_execution_bridge.py（30 项，含裸实例兼容 Phase 31 合约）、test_pending_store.py（AUD-F12 PendingStore + DecisionBridge 待批队列持久化）、test_power_on_w1_w4.py:22、test_phase49d_metacognition.py:158（L8 集成置信度门）、test_thin_coverage_e2e.py:92,133。


#### 分组 审计分组 W6：memory 记忆 + personal_memory 个人记忆 + event_memory 事件记忆 + knowledge 知识图谱

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/memory/（长时序记忆核心，Phase 21/24/47/48/49）

**模块路径范围**：`ocos/memory/__init__.py`、`hub.py`、`recall.py` + 8 个子包：`episode/`（4 文件）、`belief/`（6 文件）、`semantic/`（4 文件）、`pattern/`（5 文件）、`experience/`（4 文件）、`significance/`（4 文件）、`user/`（2 文件）。

**模块职责**：四层记忆流水线 + 统一持久化中枢 + 跨会话召回。
- `experience/`：TraceBundle（认知链路五要素：Observation/ReasoningTrace/DecisionTrace/Action/Outcome）→ ExperienceCandidate（frozen，INCOMPLETE 也保留）；ExperienceValidator 扫描 Self 污染字段（self/identity/personality/value/mission 等 10 个禁用字段名 + 6 条第一人称语句模式）。
- `significance/`：四维度评分（goal_impact 0.25 / prediction_error 0.30 / knowledge_change 0.20 / future_relevance 0.25，权重和=1 由 __post_init__ 校验），threshold=0.5，输出 GateDecision PASS/FAIL；INCOMPLETE 直接 FAIL。
- `episode/`：Episode = 通过门控的完整经历（What/How/Result/Why 四元组，禁止 Who-I-am 字段），EpisodeStore SQLite append-only（只允许 archive/mark_consolidated，禁止 delete），save 按 experience_id 幂等去重。
- `pattern/`：PatternExtractor 从 Episode 集合提取 PatternCandidate（≥3 个同 condition+outcome 分组聚合，或单事件 significance>0.8 且 prediction_error>0.8 异常提取）；PatternValidator 四层校验（Schema 字段名 / 语义禁用语中英 / 因果结构 / 禁止引用 EPI-* ID）。
- `semantic/`：KnowledgeEntry（第三人称世界知识 + KnowledgeScope 适用范围 domain/preconditions/limitations/counterexamples + source_patterns 证据链），KnowledgeValidator 五重防护（Schema/Lineage/Language/Scope/Audit），SemanticStore 单行 UPSERT 模型（GAP-P2-1 修复注释：不再预标 SUPERSEDED，避免 UNIQUE 冲突静默丢更新）。
- `belief/`：Evidence（追溯 Episode/Pattern）→ ConfidenceEngine（quality²加权/一致性方差惩罚/30 天半衰期新近度/证据量饱和 cap 15/反例每例-3% cap 0.15，五维权重 0.35+0.30+0.20+0.10+0.05）→ Belief（confidence>0 强制有 evidence_id）；EvidenceBinding 合同 min_evidence=3、min_quality=0.5；BeliefValidator 三重审核。
- `user/`：UserProfile + UserMemoryStore（SQLite 独立建连、RLock 线程安全、JSON 快照整存整取）+ UserMemory 聚合画像与事件日志，summarize() 生成提示注入摘要。
- `hub.py`：MemoryHub 统一 db_path，初始化/持有 episode+belief+semantic+pattern 四个 Store，共享 SQLite WAL。
- `recall.py`：MemoryRecall 跨会话召回（semantic 按 domain 关键词 + 高置信度兜底、pattern 按 confidence 排序、experience lessons、user 画像强制置顶 relevance=1.0），FIX-09/16 字符 bi-gram Jaccard 相关性过滤 + 中文同义词表扩展 + 按记忆密度动态阈值（>1000 条 0.10 / <50 条 0.25）；recall_cognitive() 返回结构化 premises（含 ConflictGroup 学习规则冲突集）。

**对外提供能力**：MemoryHub（initialize/shutdown/get_stats + .episode/.belief/.semantic/.pattern 属性）、MemoryRecall（recall / format_for_prompt / recall_cognitive / clear_recent）、EpisodeGate（process/process_all：评估→PASS→入库一条链）、各 Store 的 CRUD/查询 API、UserMemory（create/update_profile、record_event、set_context、summarize）。

**输入输出**：输入为认知链路 TraceBundle dict（由 agent/interaction 上游组装）、ExperienceCandidate；输出为各 Store 落库的 Episode/Pattern/Knowledge/Belief 行、RecallResult 列表/结构化 dict、用户画像摘要字符串。JSON 序列化字段：context/outcome/evaluation_trace/tags（episode）、scope_preconditions/scope_limitations/source_patterns（knowledge）等均 ensure_ascii=False。

**正常工作流程**：ExperienceBuilder.build →（Violations 仅记录到 rejection_reason，不阻断）→ SignificanceEvaluator.evaluate → GateDecision.PASS → episode_from_decision（从 trace_bundle 抽 goal_id/decision_trace_id/environment_state）→ EpisodeStore.save（按 experience_id 幂等）→ PatternExtractor.extract(episodes) → PatternValidator → PatternStore → KnowledgeEntry.create(supersede 版本链) → SemanticStore → EvidenceBinding.bind(≥3 证据) → Belief → BeliefStore；对话开头 MemoryRecall.recall(context) 注入系统提示。

**异常处理逻辑**：Store 层未初始化抛 RuntimeError；Belief/Knowledge 构造 __post_init__ 抛 ValueError；BeliefValidator/KnowledgeValidator 返回 violations 列表不抛；recall.py 各子召回 try/except 包裹——语义召回内层 `except Exception: pass`（129-130 行）、user 召回 `except Exception: pass`（209-210 行）、其余 logging.debug 后吞掉。MemoryHub 属性访问未初始化抛 RuntimeError。

**依赖其它 OCOS 模块（真实 import）**：`ocos.storage.connection.get_connection`（4 个 Store）、`ocos.constitution.statement_validator`（belief/__init__.py 的 StatementValidator 硬拦截 PERSONHOOD/CONSCIOUSNESS/IDENTITY_MANIP/DEONTIC_OVERRIDE 四类声明）、`ocos.memory` 内部互引（gate→experience/significance、evidence→semantic.models、confidence→belief.models）。memory/__init__.py 自引用 import ocos.memory.recall（可运行但不规范）。

**被哪些 OCOS 模块调用（grep 反查）**：interaction/converse.py（11 处引用，最大消费方）、agent/master_agent.py（7）、agent/agent_runtime.py（5）、agent/learning_trigger.py、agent/belief_system.py、agent/belief_consolidation.py、agent/wisdom_trigger.py、agent/adaptive_params.py、interaction/session_state.py、interaction/context.py、attention/retrieval.py、engagement/manager.py、initiative/true_initiative.py、opentale_bridge/master_agent.py、self/builder.py、self/monitor.py、extension/integration_engine.py、runtime/stages/*、interaction/cli/commands/run.py、living_test/day2_memory_survival.py；knowledge/store/registry.py 反向依赖 ocos.memory.semantic（GAP-P2-1 镜像）。

**已知限制**：(1) MemoryRecall._recall_experience 访问 `hub.experience`，而 MemoryHub 根本没有 experience Store（见风险 P2-1），experience 召回在 hub 场景下恒为空；(2) MemoryHub.get_stats 缺 semantic_count；(3) belief/__init__.py 定义了与 belief/models.Belief 同名但字段完全不同的第二个 Belief dataclass（import 路径不同类型不同）；(4) 门控宣称"Completion+Significance+Boundary 三重门控"，实际 Boundary 违规只写入 rejection_reason 不阻断入库；(5) ExperienceCandidate.create 用 naive 本地时间 datetime.now()，与全包 timezone.utc 纪律不一致。

**验证状态**：【功能实测可通】——冒烟脚本实测 MemoryHub 初始化→EpisodeGate.process（INCOMPLETE→ANOMALY 高优先级候选 PASS，score=0.63，入库 count=1）→ConfidenceEngine（0.885 active）→SemanticStore.query_by_domain 命中；tests/test_ocos_memory.py、test_belief_consolidation.py、test_phase49b_memory_world.py 等全部通过。例外：experience 召回链路为【逻辑不完整】（P2-1）。

##### 2. ocos/personal_memory/（个人智慧层，Phase 41）

**模块路径范围**：`ocos/personal_memory/__init__.py`、`wisdom_types.py`（301 行）、`pattern_interpreter.py`（201）、`wisdom_validator.py`（196）、`wisdom_store.py`（249）、`reflection_engine.py`（155）。

**模块职责**：三层严格分离（Memory=发生过什么 / ExperienceProfile=统计规律 / Personal Wisdom=未来如何判断），把 ExperiencePattern（来自 ocos/self）解释、验证、存储为个人智慧 WisdomItem。四条边界约束 PM41-01~04：Memory≠Wisdom、Pattern≠Principle、Wisdom≠Command、Wisdom≠Identity。

**对外提供能力**：PatternInterpreter.interpret(patterns, tick)→InterpretationResult 列表（候选智慧或拒绝理由）；WisdomValidator.validate / validate_and_promote / inject_counter_evidence；WisdomStore（add_wisdom/get_wisdom/list_active/list_confirmed/list_candidates/promote_wisdom/deprecate_wisdom/applicable_to/load_from_db）；ReflectionEngine.reflect(profile, user_id, tick)→ReflectionResult 统计 + query_wisdom_for_domain。

**内部子模块/数据结构**：WisdomState 状态机 CANDIDATE→VALIDATING→CONFIRMED→ACTIVE→DEPRECATED（promote_to 白名单合法转换，DEPRECATED 终点不可逆）；WisdomScope（domains/conditions/exclusions/user_scope，applies_to 硬排除→域匹配→条件任一匹配）；WisdomEvidence（supports 布尔 + strength [0,1]）；WisdomItem 的 evidence_strength = 支持强度和/(支持+反对)；WisdomCollection 按用户隔离。

**输入输出**：输入 ExperiencePattern 列表（pattern_id/label/category: successful|failure|neutral/frequency/confidence/abstracted_at_tick）；输出 WisdomItem（落库 wisdom_items 表或纯内存）。neutral 类别与频次 <3、模式数 <2 的直接拒绝（reject_reason: neutral_category / insufficient_patterns / low_frequency）。

**正常工作流程**：ReflectionEngine.reflect → 按 successful/failure 分组 → PatternInterpreter.interpret（≥2 个模式且 frequency≥3 才产出候选，principle 为模板化英文表述）→ WisdomValidator.validate_and_promote（CANDIDATE→VALIDATING，支持证据≥2、反例比≤0.3、evidence_strength≥0.6 → CONFIRMED；REJECTED → DEPRECATED）→ 通过者 WisdomStore.add_wisdom 落库。

**异常处理逻辑**：无 try/except；错误以拒绝结果对象返回。WisdomStore._persist_item 在 connection=None 时静默 return（纯内存模式）。

**依赖其它 OCOS 模块**：`ocos.self.self_types.ExperiencePattern`、`ocos.self.experience_profile.ExperienceProfile`（reflect 入参）。

**被哪些 OCOS 模块调用**：agent/wisdom_trigger.py（ wisdom_trigger 中含 wisdom_items 自愈建表 + WisdomStore.load_from_db 落盘链路）、agent/continuity_trigger.py、tests/test_phase41.py、tests/test_wisdom_persistence.py。

**已知限制**：(1) _persist_item 只 UPDATE state 列，后续追加的 evidence（如 inject_counter_evidence）不会落盘（INSERT OR IGNORE 对已存在行 no-op）；(2) _infer_scope 当模式标签 >3 个时 domains=() → 变成 universal scope，与防泛化目标相悖；(3) 只有 PASS 的候选入库，未 PASS 的 CANDIDATE 直接丢弃（不可追溯）；(4) 原则文本是模板拼接，非语义提炼。

**验证状态**：【功能实测可通】——冒烟脚本实测 2 个 frequency=5 的 successful 模式 → 2 条 wisdom confirmed；tests/test_phase41.py、test_wisdom_persistence.py 通过。evidence 增量落库缺失为已知限制（P2-6）。

##### 3. ocos/event_memory/（事件记忆基础设施，Phase 54）

**模块路径范围**：`ocos/event_memory/__init__.py`、`event_types.py`（203）、`event_store.py`（261）、`event_index.py`（172）、`event_replay.py`（186）、`event_archive.py`（183）、`event_validator.py`（166）、`event_query.py`（132）、`event_lifecycle.py`（173）。

**模块职责**：认知过程完整轨迹的追加式记录（区别于 Memory=提炼后信息）。六条保证 EM54-01~06：事件不可篡改、时间线可重建、回放无副作用、事件≠记忆、跨 session 持久化、多维查询。

**对外提供能力**：EventLifecycle（统一入口 record/record_batch/maintain/query/snapshot/restore/clear）；EventStore（append/append_batch/find/range/iterate/headers/stats/snapshot/restore/mark_archived/load_from_db）；EventIndex（by_type/by_entity/by_goal/by_source/by_confidence 五维 + 综合交集 query）；EventReplay（replay_range/trace_causal_chain/reconstruct_timeline/generate_reflection/generate_evolution_narrative）；EventArchiveManager（HOT→WARM→COLD→ARCHIVED 迁移 + zlib 压缩归档 + sha256 校验恢复）；EventValidator（事件级/store 级/时间线/回放安全四类校验）；EventQueryEngine（store+index 组合查询）。

**内部子模块/数据结构**：CognitiveEvent（frozen dataclass：event_id/event_type(CognitiveEventType 9 类：perception/attention/decision/action/result/learning/interaction/health/evolution)/timestamp(Epoch 秒 float)/source/context/payload/confidence(EventConfidence 4 级)/caused_by(EventReference 因果链)/links_to/metadata/lifecycle）；EventHeader（无 payload 轻量摘要）；EventArchive（archive_id/start_time/end_time/compressed_data/checksum）；EventQuery（event_types/sources/time_from/time_to/entity/goal_id/confidence_min/lifecycle/context_has_key/limit/offset）。

**输入输出**：输入 record(event_type, source, payload, context, confidence, caused_by_id)；输出 CognitiveEvent（id 格式 `ev-{type}-{uuid8}`）；SQLite event_store 表同步写入（注入 connection 时）；snapshot dict 可 Checkpoint 持久化。

**正常工作流程**：EventLifecycle.record → EventValidator.validate_event（无 id/时间戳≤0 → FAIL，未来时间/空 payload+context → WARN）→ FAIL 仍入库但置 ARCHIVED → EventStore.append（重复 id 静默忽略返回 False）→ EventIndex.index → 周期 maintain()：age>360s→WARM、>hot_ttl(3600s)→COLD、>warm_ttl(86400s)→ARCHIVED（统计 to_warm/to_cold/to_archived）。查询走 EventQueryEngine：单类型/entity/goal 命中索引先交集再回表，否则 store.range 扫描 + 后过滤。

**异常处理逻辑**：EventStore 无显式 try/except（sqlite 异常向上抛）；EventValidator 以 ValidationCode PASS/WARN/FAIL 三级返回而非抛异常；restore_archive checksum 不匹配抛 RuntimeError。

**依赖其它 OCOS 模块**：仅 `ocos.event_memory` 内部互引 + `ocos.storage` schema 的 event_store 表定义（connection 由外部注入，本包不直接 import storage）。event_lifecycle.py 通过 `from ocos.event_memory.event_query import EventQueryParams` 依赖 event_query.py 中的导入别名（EventQuery as EventQueryParams），脆弱但可运行。

**被哪些 OCOS 模块调用**：execution/bridge.py、interaction/converse.py、tests/test_phase54.py、tests/test_event_store_sqlite.py。

**已知限制**：(1) _persist 写本地时间无时区 ISO（无 %f），load_from_db 用 time.mktime 反解，时区敏感且亚秒精度丢失；(2) mark_archived 只改 EventHeader，_by_id/_events 内事件本体 lifecycle 不变，与 apply_lifecycle（直接改私有 _events/_by_id）两条路径状态不一致；(3) snapshot 将 payload 序列化为 str、restore 丢失 caused_by/links_to/metadata；(4) EventQuery 的 confidence_min/lifecycle/context_has_key 三参数从未被查询引擎使用（死参数）；(5) 索引命中分支不应用 sources 过滤。

**验证状态**：【功能实测可通】——冒烟脚本实测 record 因果链（caused_by 回指成功）+ goal_id 索引查询命中 + 多类型查询过滤正确；tests/test_phase54.py、test_event_store_sqlite.py 通过。查询引擎索引分支的过滤缺陷为已知限制（P2-5）。

##### 4. ocos/knowledge/（知识平面 Knowledge Plane v1.0 + 用户知识图谱 Phase S + 知识综合 Phase AG）

**模块路径范围**：`ocos/knowledge/__init__.py`、`graph.py`（299）、`manager.py`（216）、`knowledge_abi.py`（301）、`synthesis_manager.py`（530）+ 6 个 re-export 兼容壳（knowledge_ontology/registry/lifecycle/validator/evolution.py、promotion_rules.py）+ `store/`（__init__/ontology/registry/lifecycle）+ `process/`（__init__/validator/promotion_rules/evolution）。

**模块职责**（三个相互独立的子系统）：
- **知识平面（store/ + process/ + knowledge_abi.py）**：五层级知识原子 KnowledgeUnit（OBSERVATION→EVIDENCE→PATTERN→PRINCIPLE→POLICY，ELEVATION_MATRIX 只允许逐级提升）+ 状态机（CANDIDATE→VERIFIED→ACTIVE→DEPRECATED→ARCHIVED，DEPRECATED 可回 ACTIVE，ARCHIVED 终点）；KnowledgeRegistry 所有权边界（owner + AccessScope public/protected/private + AccessMatrix 读写/提升矩阵，通配符 owner="*"）；KnowledgeLifecycle 状态编排 + StatusChangeRecord 审计 + 监听器回调；PromotionRuleEngine（触发条件 REPETITION/CONFIDENCE/GOVERNANCE/MANUAL/TIME_BASED + PromotionPolicy 权限与前置条件，默认策略：Pattern→Principle 与 Principle→Policy 需 Governance 审批）；KnowledgeValidator 规则化校验（content 非空/枚举类型/source 长度/提升链方向）；EvolutionManager 提案式变更（EDIT/MERGE/DEPRECATE/SPLIT/ELEVATE，DRAFT→REVIEW→APPROVED→APPLIED/REJECTED）；KnowledgeABI 对外标准 ABI（1.0.0，读 get_unit/query/get_by_level/get_active_units，写 submit_observation/create_unit/update_unit，状态 verify/activate/deprecate/archive，提升 can_elevate/elevate，审计 get_status_history）。GAP-P2-1：注入 SemanticStore 后 register/update/remove 自动镜像到语义记忆 knowledge 表（fail-open，失败仅告警）。
- **用户知识图谱（graph.py + manager.py）**：实体 Entity（8 类 EntityType）/ 三元组关系 Relation（10 类 RelationType）/ 带有效期事实 Fact（valid_from/valid_until），置信度加权更新（(1-w)*old + w*new），出/入边索引 + BFS infer_relations 推断间接关系；KnowledgeGraphManager 组合 NER/RE 提取器（可选注入）+ 操作历史（500 条上限）+ 报告/JSON 导出。
- **知识综合（synthesis_manager.py）**：KnowledgeNode/KnowledgeEdge 内存图（线程安全 RLock，max 10000 节点/50000 边），synthesize_knowledge 支持 deductive/inductive/abductive 三种综合模式（实际为模板拼接的简化实现），query_knowledge 子串匹配，find_path BFS，质量评估 confidence*0.6 + 关联度*0.4。

**对外提供能力**：见上；`ocos.knowledge/__init__.py` 只导出 KnowledgeGraph 系（KnowledgeGraph/Entity/Relation/Fact/EntityType/RelationType/KnowledgeGraphManager/ExtractionResult），KnowledgeABI 需从 `ocos.knowledge.knowledge_abi` 导入（__init__ 未导出，实测确认）。

**输入输出**：知识平面输入 KnowledgeUnit(content: dict, source: str)（statement/confidence/domain/preconditions/limitations/stability 从 content dict 提取），输出 (bool, msg) 二元组 + _to_public_view dict；无 SQLite 表（内存 registry），镜像走 SemanticStore.knowledge 表。图谱输入 ExtractionResult（entities/relations/facts dict 列表），输出 Entity/Relation/Fact + export_json。

**正常工作流程**：submit_observation（owner 需 OBSERVATION 层写权限）→ verify（CANDIDATE→VERIFIED）→ activate（→ACTIVE）→ elevate（can_promote 校验层级方向 + 状态 ACTIVE/VERIFIED + 策略 allowed_sources/前置条件 → 新建子单元 parent_id 回链，version+1，新单元回到 CANDIDATE）；EDIT/MERGE/SPLIT 提案由 EvolutionManager 审批后执行（SPLIT 失败回滚已注册部件）；镜像端 KnowledgeUnit→KnowledgeEntry（id 直接沿用 unit_id，CANDIDATE→UNSTABLE、verified/active→ACTIVE）UPSERT 进 SemanticStore。

**异常处理逻辑**：所有操作返回 (ok, msg) 不抛异常；registry 镜像 try/except + logger.warning(fail-open)；validator 单规则异常捕获转 ERROR 级 ValidationResult；evolution._apply 顶层 try/except + logger.exception。

**依赖其它 OCOS 模块**：`ocos.memory.semantic.models` + `ocos.memory.semantic.store`（GAP-P2-1 镜像，registry.py:23-28）；`ocos.logging.get_logger`（synthesis_manager.py）。

**被哪些 OCOS 模块调用**：agent/master_agent.py、engines/promotion_engine.py、engines/consolidation_engine.py、daemon/factory.py、tests/test_knowledge_*.py（8 个文件）/test_master_agent_knowledge.py/test_promotion_*.py/test_consolidation_engine.py/test_semantic_operations_only.py。

**已知限制**：(1) elevate 默认策略 allowed_sources=["governance","pattern_detector","manual"]，其它 owner（实测 "testmod"）一律被拒——默认权限矩阵授予了 can_elevate 但策略层又拒绝，两套权限互相矛盾；(2) EvolutionManager._apply_edit 用旧状态调 change_status（同状态转换非法）→ 审计记录静默失败且返回值被忽略，且新 unit 丢 source 字段；(3) KnowledgeLifecycle.get_version_history 实现有误（每条审计记录都 append 1）；(4) graph.remove_entity 不清理悬挂 Relation/_by_name；find_by_name 文档写"模糊匹配"实为精确 lower 匹配；export_json 不含 facts且无导入方法；(5) process/validator.check_elevation_chain 调 registry.get(..., scope_filter="*") 传了不存在的参数（TypeError 风险，被规则级 try/except 吞成 ERROR）；(6) store/lifecycle.py 类型注解用内建 callable（非 typing.Callable），因 `from __future__ import annotations` 未爆雷但属类型错误。

**验证状态**：【功能实测可通】——冒烟脚本实测 submit_observation→verify→activate 全链成功（v1+1/v2+1）、elevate 被默认策略拒绝（确认矛盾点）、KnowledgeGraph 统计正确、EvolutionManager EDIT 提案 create（传裸字符串 change_type 时在日志行 AttributeError，传枚举则正常）；tests/test_knowledge_ontology/registry/lifecycle/evolution/synthesis_manager/graph.py、test_promotion_rules/engine.py、test_consolidation_engine.py 等通过。


#### 分组 审计分组 W7：world_model 世界模型 + digital_world 数字世界 + opentale_bridge + platform

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/world_model/（9 文件，约 1268 行）— Phase 42 世界模型

**模块职责**：外部世界的结构化表示，回答"外部世界如何运作"。与 Knowledge Base（文档存储）、Belief（可信度判断）、Goal（意图）明确区分（边界约束 WM42-01~04）。

**对外提供能力**（`ocos/world_model/__init__.py` 导出）：核心类型（Entity/EntityState/StateChange/Relation/WorldEvent/CausalityLink/Observation 及各枚举）、5 个组件（EntityModel/RelationGraph/StateTracker/EventModel/CausalityEngine）、治理（WorldValidator/ValidationDecision/ValidationIssue/ValidationResult）、统一存储 WorldStore。

**内部子模块**：
- `world_types.py`：全部 frozen dataclass 与枚举（Entity/Relation/WorldEvent/CausalityLink/Observation）。
- `entity_model.py`：实体 CRUD（create/get/get_by_type/remove/type_distribution）。
- `relation_graph.py`：有向关系图，双向索引（_outgoing/_incoming），支持 neighbors/find_by_type/causal_relations。
- `state_tracker.py`：实体状态版本链 + StateChange 变更记录，支持 at_tick/changes_since。
- `event_model.py`：不可变事件日志（append-only），按实体/类型/tick 查询。
- `causality_engine.py`：因果链 CRUD + 双向链追溯（causal_chain/upstream_chain，每跳取置信度最高，max_depth 默认 5），well_supported（confidence≥0.6 且证据≥2）/contested 查询。
- `world_validator.py`：外部输入治理（WM42-04）。
- `world_store.py`：整合五组件 + validator，唯一写入路径 `update_from_observation()`；Phase 49-B 增加 `cognitive_world_state()` 供认知主链（think/plan 注入）查询，空世界优雅降级。

**输入输出**：输入为 Observation（外部观察，含 claimed_relation/claimed_state）；输出为实体/关系/状态/事件/因果的内存查询结构 + summary()/cognitive_world_state() dict。

**正常工作流程**：Observation → WorldValidator.validate_observation → 记录 OBSERVATION 事件 → _upsert_from_obs（创建实体 + 记录 EntityState）→ 可选添加 claimed_relation 并记录 RELATION_ADDED 事件。tick 由内部 _tick 自增或使用 observation.tick_id。

**异常处理逻辑**：实体/关系/因果重复添加抛 ValueError；StateTracker/EventModel 查询对空数据返回 None/空列表，不抛错。

**依赖哪些 OCOS 模块**：仅依赖自身（world_model 内部互相 import），零外部 OCOS 依赖——刻意保持独立。

**被哪些 OCOS 模块调用（grep 反查）**：
- `ocos/daemon/factory.py:219`（系统工厂装配 WorldStore）
- `ocos/perception/pipeline.py`（GAP-P1-3 感知链：pipeline → world_model）
- `ocos/interaction/converse.py:371`（对话链取世界状态）
- `ocos/os_v1/freeze.py`、`ocos/audit/architecture_map.py`、`ocos/audit/task_simulator.py`、`ocos/health_examination/health_model.py`
- 测试：`ocos/tests/test_phase42.py`、`test_phase49b_memory_world.py`、`test_import_rules.py`

**已知限制**：
1. 全内存实现，无持久化（tick/实体重启即失）。
2. `update_from_observation()` 只调用 `validate_observation`，从不调用 `validate_against_model`（一致性检查是死代码，见风险 R1）。
3. `WorldStore._upsert_from_obs` 添加 claimed_relation 时不校验 from/to 实体是否存在，可能产生悬空关系。
4. validator 的 REJECT/QUARANTINE 决策、min_sources、clamp_confidence 均未被任何路径使用。

**关于 World Integrity / NFI（叙事保真）专项核查结论**：对 world_model 9 文件（重点 world_types.py、world_validator.py、causality_engine.py、entity_model.py）grep `narrative|fidelity|integrity|NFI`，**零命中**。world_model 中不存在"World Integrity 世界完整性校验"和"NFI 叙事保真链"的任何代码。最接近的机制是：
- `world_validator.py` 的 WM42-04 外部输入治理（Observation → Validation → World Update），含 6 类 ValidationIssue（UNKNOWN_SOURCE/LOW_CONFIDENCE/CONFLICT_WITH_EXISTING/SINGLE_SOURCE/MISSING_EVIDENCE/INCONSISTENT）和 5 种 ValidationDecision（ACCEPT/NEED_MORE/REJECT/CONFLICT/QUARANTINE），但实际实现只用了来源检查 + 内容非空检查（`validate_against_model` 中还有一处自比较 bug，见风险 R1）。
- `causality_engine.py` 的因果证据机制（evidence_ids/counter_evidence_ids/discovery_source/is_well_supported）属于"因果可反驳性"，与叙事保真无关。
"narrative" 关键词的全部命中都在 `opentale_bridge`（NarrativeContract 契约补丁），属于对 OpenTale 写作引擎的契约级控制，不是叙事保真校验链。

**验证状态**：【功能实测可通】——WorldStore.update_from_observation 全流程实测通过（观察→验证→实体创建→事件记录，summary 计数正确，cognitive_world_state 返回就绪结构）；但 validate_against_model 的冲突分支因自比较 bug 永不触发（实测 CONFLICT 检查返回 ACCEPT）。

##### 2. ocos/digital_world/（10 文件，约 1083 行）— Phase 21/22/29 数字世界接口层

**模块职责**：让 OCOS 操作数字环境（文件/Git/API/搜索/数据库/沙盒）。与 `ocos/operations/`（Phase 22-E 高危闸门）分工不合并（AUD-F5 裁决）：本包是宽语义操作库，默认 dry_run + DLQ 审计。

**宪法约束**（`__init__.py` 声明）：ALL_OPERATIONS_AUDITED / SINGLE_AUTHORITY / NO_PHYSICAL_WORLD / FAILURE_TO_DLQ / RESOURCE_LIMITS。导入规则允许 ocos.agent/ocos.planning，禁止 ocos.self。

**对外提供能力**：`DigitalOperation/OperationResult/AuditRecord`（不可变数据模型）、`OperationAuditor`（内存审计）、`DeadLetterQueue/DLQEntry`（失败重试队列），以及 7 个操作函数（api_get/api_post/file_read/file_write/file_delete/git_clone/git_commit/git_push/db_query/db_write/search/sandbox_exec，实际 12 个函数对应 12 种 op_type）。

**内部子模块**：
- `base.py`：VALID_OP_TYPES(12 种)/APPROVAL_REQUIRED(7 种需审批)/资源限制常量（10MB 文件、4000 字符截断、60/min API 限速、500 字符查询、30s 沙箱超时）；`DigitalOperation.__post_init__` 强制审批型操作必须带 approval_id。
- `api_ops.py`：URL 白名单（github/openai/anthropic API）+ 速率限制 + dry_run gate（`OCOS_DW_DRY_RUN=1` 默认模拟，=0 走 urllib 真实请求）。
- `file_ops.py`：10MB 限制、4000 字符截断、PROTECTED_PATHS 保护（/etc/passwd、/etc/shadow、/boot、~/.ssh、~/.hermes）。
- `git_ops.py`：GIT_URL_WHITELIST（仅 https://github.com/）+ 5s 生产冷却 + 真实 subprocess git（clone --depth 1 / add -A + commit / push origin）。
- `search_ops.py`：真实模式 grep -rn 文件系统搜索，200 行/50KB 截断，`_sanitize_query` 防 flag 注入。
- `sandbox.py`：BLOCKED_COMMANDS 黑名单（rm -rf/sudo/wget/curl/nc/fork bomb 等 11 项）+ shell=True subprocess 执行（workdir 默认 /tmp/ocos-sandbox）。
- `db_ops.py`：**纯占位**——db_query/db_write 均直接返回 "(simulated)"，无任何真实 DB 实现。
- `auditor.py`：OperationAuditor 内存审计轨迹。
- `dlq.py`：DeadLetterQueue，max_retries=3，状态机 pending_retry→permanently_failed/resolved，`retry_pending(executor_fn)` 重试。

**输入输出**：输入统一为 `DigitalOperation`（op_id/op_type/target/requester/params/approval_id），输出统一为 `OperationResult`（success/failure/timeout/rejected + output/error/duration_ms）。

**正常工作流程**：构造 DigitalOperation（审批型须带 approval_id，否则构造即抛 ValueError）→ 调对应 ops 函数 → 白名单/黑名单/限速校验 → dry_run 模拟或真实执行 → OperationAuditor.record → 失败入 DLQ。

**异常处理逻辑**：白名单外/黑名单命中/限速返回 rejected；OSError/subprocess 失败返回 failure；超时返回 timeout；DLQ 重试超限转 permanently_failed。

**依赖哪些 OCOS 模块**：仅 `ocos.digital_world.base`（各 ops 文件互不依赖，纯函数式）。

**被哪些 OCOS 模块调用（grep 反查）**：主流程中仅 `ocos/execution/bridge.py`（PW-4.2：FILE_WRITE 执行器，`from ocos.digital_world.base import DigitalOperation; from ocos.digital_world import file_ops`，注释明确 AUD-F5 裁决 shell/HTTP 候选执行层为 ocos/operations 而非本包）；其余为测试（tests/digital_world/ 下 12 个测试文件、tests/validation/test_e2e_complex_task.py）。

**已知限制**：
1. db_ops 完全占位；file_read 无 PROTECTED_PATHS 检查（只有写/删有），可读任意 ≤10MB 文件。
2. dry_run 标志 `_DRY_RUN` 在模块 import 时固化（`os.getenv`），进程内改环境变量不生效。
3. file_write/file_delete 路径保护用 startswith 前缀匹配，`/boot` 前缀会误伤 `/bootXXX` 这类路径（过粗匹配）。
4. sandbox.py 实际 `shell=True` 执行且"禁止网络"仅靠命令黑名单（curl/wget 等），非真沙箱（无 seccomp/namespace）。

**验证状态**：【功能实测可通】（dry_run 默认路径与审批强制逻辑静态+结构验证一致，tests/digital_world 下 12 个测试文件覆盖 base/api/file/git/db/dlq/sandbox/search/auditor/real_ops）；db_ops 标【逻辑不完整】（占位）。

##### 3. ocos/opentale_bridge/（16 文件，约 4221 行）— Phase 59 + S/R/U 系列 OCOS↔OpenTale 桥

**对接的外部系统**：**OpenTale**（外部 AI 网文写作引擎），通过其 **Organ API**（`http://127.0.0.1:8000/api/organ`，契约基准 `docs/runtime/OPENTALE_ORGAN_API_CONTRACT_20260818.md`）对接。OCOS 为"大脑"（写作决策），OpenTale 为"写作器官"，Hermes 为操作员桥接层。

**模块职责**：喂上下文给 OCOS → OCOS 产出 OcosDecision → 翻译为 OpenTale ChapterBlueprint → OpenTale 执行写作 → 章节输出回流 OCOS 学习/修复/契约调整，形成 think→write→feedback 闭环。

**对外提供能力**：`BridgeSessionOrchestrator`（全周期编排）、`quick_bridge_test()/quick_web_feed_test()` 验证入口、MasterAgent 决策引擎、OrganClient HTTP 客户端、QualityAnalyzer/TrendAnalyzer 分析器、SelfRegulationLoop/FeedbackReflux 生产闭环。

**内部子模块（按职责分层）**：
- 类型层：`bridge_model.py`（BridgePhase 状态机 7 态、OcosDecision、TranslationResult、FeedbackInput、RepairDecision、ContractAdjustment、BridgeSession、WebFeedResult）。
- 模拟/验证层：`bridge_session.py`（feed→decide→translate→execute_simulated→feedback 五步 + 修复循环 + 契约调整 + run_multi_chapter_with_trend_watch）。**此文件是测试/验证层，produce_decision 是硬编码模拟**。
- 生产决策层：`master_agent.py`（S5 决策真实化：关键词表 FOCUS/TONE/PACING_KEYWORDS 中英双语意图解析 → OcosDecision；R1 Trace Identity 生成 agent_run_id；E7 经 OcosMemory.recall 编排回忆；I6 注意力焦点、I7 信念治理、R5 写作决策门禁）。
- 翻译层：`decision_translator.py`（Focus→primary_driver、Pacing→rhythm、Tone→emotion_curve、Cliffhanger→ending 的规则映射表；Phase 59-j TREND_TO_CONTRACT_RULE 9 条趋势→契约调整规则）。
- 反馈层：`feedback_loop.py`（章节输出→FeedbackInput，内嵌 OCOS 自主 QualityAnalyzer 分析；Phase 59-i evaluate_and_repair 修复判定；Phase 59-j analyze_cross_chapter_trends 跨章趋势）、`feedback_reflux.py`（S8 C3：Organ 项目评审 → ~/.ocos/feedback/<project>.json）。
- 分析层：`quality_analyzer.py`（5 维度：叙事密度/角色一致性/情感曲线/类型合规/语言质量，纯规则+情感词典，含中文言情专用情感词表 ROMANCE_EMOTIONS）、`trend_analyzer.py`（5 类趋势：quality_decay 线性斜率、chronic_<dim> 尾部连续低于阈值、monotone_emotional、dialogue_imbalance、genre_drift）。
- 生产闭环层：`self_regulation.py`（S7：collect→analyze→adjust→describe 人工确认→apply 经 Organ rewrite；受控开关 `OCOS_SELF_REGULATION` 默认 manual）、`organ_client.py`（S4：generate/resume/rewrite/verify/analyze + 任务轮询 wait/wait_events + accept/reject 确认流 + Bearer token）、`ocos_memory.py`（S8-P2：M3 recall 编排/M4 巩固/M5 遗忘/M6 决策历史统一文件持久化）、`trace_context.py`（R1：correlation_id 跨系统根原样传播 + X-Trace-* HTTP 头）、`belief_gate.py`（I7：PASS/STRIP/REJECT/ESCALATE 信念治理，Belief→Decision/Mutation 结构性 DENY）、`ocos_activation.py`（S7 激活计数器，~/.ocos/activation.jsonl 跨进程持久化）。
- 数据注入层：`web_feeder.py`（**模拟** Web 搜索，内置 5 类 2026 年假数据 chunk，"生产会调用真实 web_search"）。

**输入输出**：输入 WritingIntent（premise/title/genre/characters/roles/genders/world + hints）/章节 dict/契约调整；输出 OcosDecision→ChapterBlueprint dict→Organ HTTP 请求→任务轮询结果→FeedbackInput/QualityReport/TrendSignal/ContractAdjustment。

**正常工作流程（生产路径）**：MasterAgent.decide(WritingIntent)（读取 OcosMemory+注意力+信念上下文 → R5 门禁 → M6 落盘）→ to_organ_contract/OrganClient.generate → wait 轮询 → collect_generated → QualityAnalyzer.analyze → needs_repair ? rewrite : accept → FeedbackReflux 写评审记忆 → TrendAnalyzer 跨章趋势 → ContractAdjustment → SelfRegulationLoop.apply（manual 确认后 Organ rewrite）。

**异常处理逻辑**：OrganClientError/OrganTaskTimeout 区分网络错误与轮询超时；HTTP 非 2xx 解析 detail；OcosMemory.recall 失败优雅降级返回空串（OPT-D3）；激活埋点写入失败 logger.warning（BR-04）；self_regulation 记忆记录失败静默不阻断。

**依赖哪些 OCOS 模块（真实 import）**：`ocos.opentale_bridge` 内部互相依赖为主；外部依赖 2 处——`master_agent.py` → `ocos.attention.candidate_selector.CandidateCollector` + `ocos.attention.scoring.AttentionScoringEngine`（I6 注意力）。

**被哪些 OCOS 模块调用（grep 反查）**：`ocos/interaction/api/routes/chat.py`、`ocos/interaction/api/routes/quality.py`、`ocos/interaction/cli/commands/decide.py`、`feedback.py`、`organ.py`、`regulate.py`（CLI 与 WebChat 主流程真实调用）；测试 `ocos/tests/test_master_agent.py`、`test_ocos_memory.py`、`test_organ_client.py`、`test_phase59.py`、`test_self_regulation.py` 等。

**是否主流程**：**是主流程的真实支线**——通过 interaction 层（CLI decide/feedback/organ/regulate 命令 + API chat/quality 路由）接入主认知系统，不是孤立死代码；但 bridge_session.py 的模拟执行路径仅用于验证。

**已知限制**：
1. web_feeder 是硬编码假数据（模拟 Web 搜索）。
2. quality_analyzer 的角色识别靠"首字母大写词 + 硬编码姓氏表（沈赵钱孙李…）+ 古言称谓"，对现代中文人名覆盖率有限。
3. `_execute_simulated_repair` 引用不存在的 `session.translation_result` 属性（P2，实测确认 AttributeError）。
4. master_agent.py:247-248 存在**双重 @staticmethod 叠加**（实测在 Python 3.10+ 可用，为遗留写法）。
5. self_regulation 硬编码 OpenTale 项目目录 `/home/laogao/Documents/trae_projects/opentale/projects`（写死个人路径）。

**验证状态**：【功能实测可通】——BridgeSessionOrchestrator.run_full_cycle 实测通过（produce_decision→translate→execute_simulated→feedback→ocos_overall=0.66→evaluate_and_repair 判定）；MasterAgent.decide 实测通过（悬疑题材正确解析为 investigation/suspense/accelerate，注意力方法双重 staticmethod 实测绑定正常）；但 web_feeder（假数据）与 bridge_session 修复重写路径（AttributeError 潜伏 bug）标为【逻辑不完整】子项。

##### 4. ocos/platform/（14 文件，约 4060 行）— 平台层（审计/追踪/治理/插件/引擎装载）

**模块职责**：OCOS 平台基础设施——C1 可解释性 Trace、C2 审计引擎、C3 治理审批、D1 能力注册、D2 插件沙箱、D3 插件装载、引擎 manifest 自动发现与动态装载。宪法约束（`ocos/kernel/constitution.py:131`）：`ocos.platform` 只允许依赖 `ocos.kernel` 与 `ocos.events`。

**对接的外部系统**：无外部系统——这是纯内部平台层。与 opentale_bridge 的关系：platform 是**主流程基础设施**（engine_manifest 被 17 处 import、trace_engine 被 10 处 import、capability_registry 8 处，覆盖全部 ocos/engines/*、kernel/constitution.py、capability/discovery.py）；opentale_bridge 是对接外部 OpenTale 的业务支线。两者无直接 import 关系。

**内部子模块**：
- **C1 Trace（trace_engine.py）**：7 类 frozen Trace（Decision/Reasoning/Simulation/Learning/Memory/Execution/Goal，注释写"4 类"是过时文档），InMemoryTraceStore 环形缓冲 10,000 条 FIFO 淘汰，record_* 注入接口 + query_traces/get_trace，可选 TRACE_RECORDED 事件，record_process_trace 按 ProcessType 路由（Phase 15）。
- **C2 Audit（audit_engine.py + audit_models.py + audit_rule_engine.py + audit_report.py）**：4 类审计记录（DECISION/GOVERNANCE/EXECUTION/SYSTEM），Event Bus 自动收集（订阅 DECISION_FORMED/VALIDATED、GOVERNANCE_APPROVED/REJECTED、ACTION_EXECUTED/FAILED、EMERGENCY_HALT），5 条默认规则（决策完整性/权限一致性/执行链完整性/治理可追溯/应急恢复），Debug/Compliance/Replay 三种报告。v1.0 拆分为 4 文件。
- **C3 Governance（governance_engine.py）**：EvolutionProposal 状态机 PENDING→UNDER_REVIEW→APPROVED/REJECTED/CANCELLED，_ALLOWED_TRANSITIONS 硬校验，POLICY_CHANGE 类提案发射 policy_action/policy/policy_name 供 PolicyEngine 消费。
- **D1 Registry（capability_registry.py）**：Tool/Plugin/Model 统一注册中心，同名同版本自动 patch+1，按类型/标签交集/名称子串查询。
- **D2 Sandbox（plugin_sandbox.py）**：PluginSandbox + SandboxConfig + _ImportBlocker（meta_path hook 白名单 27 个标准库前缀）+ 线程池超时终止 + SandboxResult。
- **D3 Loader（plugin_loader.py + plugin_base.py + plugin_manifest.py）**：discover 扫描 plugin.json → validate_manifest（名称/entry_point 格式 `module:Class`/权限枚举/超时 1-300s）→ PluginBase 子类校验 → 实例化 → sandbox.load → slot 注入 → on_load（失败回滚）→ execute 委托 sandbox；重复 entry_point 返回已有 plugin_id。
- **引擎装载（engine_manifest.py + engine_loader.py）**：引擎模块级 `__manifest__` 声明，pkgutil 扫描 `ocos.engines` 包，DFS 拓扑排序（含环检测 ValueError），按 auto_load 装载并缓存。

**输入输出**：输入为 Event/Proposal/PluginManifest/CapabilityDescriptor/各 Trace 字段；输出为内存查询结构 + dict 报告 + SandboxResult/LoadResult。

**正常工作流程（实测通过）**：GovernanceEngine.submit→review→status=approved；TraceEngine.record_decision_trace→get_trace；AuditEngine.record(DECISION)→build_debug_report(decision_id)→run_audit_checks→findings。

**异常处理逻辑**：审计规则 check_fn 异常被捕获并转为 severity=error 的 AuditFinding（不中断）；插件 on_load 失败回滚 sandbox 注册；sandbox 超时返回 killed=True；proposal 非法状态转换抛 ValueError。

**依赖哪些 OCOS 模块**：`ocos.kernel.abi`（Event/EventType/SCHEMA_VERSION）、`ocos.logging`、`ocos.models.process`（ProcessType/TransformProcess，已标 deprecated）、`ocos.events.event_bus`（可选注入）。

**被哪些 OCOS 模块调用（grep 反查 import 计数）**：engine_manifest×17（全部 ocos/engines/*）、trace_engine×10、capability_registry×8、plugin_manifest×5、plugin_sandbox×4、audit_engine×4、plugin_base×3、audit_models×3、kernel/constitution.py（宪法平台导入规则）、capability/discovery.py、scripts/phase21_gate.py、tests/platform/* 等。**是主流程核心依赖**。

**已知限制**：
1. **插件沙箱 import hook 实际从未安装**（P1，见风险 R4，实测确认 sys.meta_path 中始终 0 个 blocker）——import 白名单形同虚设。
2. 线程池超时只是 `future.cancel()` + 返回 killed，超时插件线程仍在跑（Python 线程无法强杀），`_get_pool` 只在池创建瞬间设 daemon，后续新建 worker 非 daemon。
3. max_memory_mb 只是"检测信号"，不强制（代码注释自认）。
4. `_ImportBlocker` 是全局 meta_path hook，注释称"只作用于当前线程"但实现是进程级全局，多插件并发时互相污染。

**验证状态**：【功能实测可通】（Governance/Trace/Audit 全链路实测：提案审批、trace 记录、审计记录、debug 报告、5 规则检查全部通过）；但 plugin_sandbox 的 import 隔离标【逻辑不完整】（hook 未安装），engine_loader/manifest 标【静态推演验证】（结构完整，注入依赖均用 Any/Optional 宽类型，实测路径未覆盖）。

（接下文：二、文件全量索引）


#### 分组 审计分组 W8：perception 感知 + attention 注意力 + evolution 演化 + learning 学习 + growth 成长 + reflection 反思 + cognitive_nutrition 认知营养 + cognitive_continuity 认知连续性

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/perception/（11 文件，约 2,206 行）

- **模块路径范围**：ocos/perception/__init__.py, sensor_types.py, text_sensor.py, file_sensor.py, environment_sensor.py, perception_engine.py, semantic_extractor.py, perception_validator.py, pipeline.py, multi_modal.py, cross_modal_fusion.py
- **模块职责**：Phase 52 "第一感官系统"——从外部世界采集信号（文本/文件/环境/音频/视觉/API/事件），产生带置信度的 Observation，可选做语义提取与验证，经桥接写入世界模型。核心原则 PS52-01（感知≠真理）、PS52-02（传感器故障隔离）、PS52-03（必须带置信度）、PS52-04（先验证再入信念）。
- **对外提供能力**：`PerceptionEngine.tick()`（感知周期）、`PerceptionPipeline.tick()`（感知→世界模型全链路，生产入口）、`MultiModalPerception`（7 传感器统一管理 + 跨模态融合）、`CrossModalFusion.fuse()`（4 种融合策略）、`PerceptionValidator.validate()`、各 Sensor 的 `feed()/poll()`。
- **内部子模块**：类型层（sensor_types）、传感器层（text/file/environment）、处理层（semantic_extractor、perception_validator）、引擎层（perception_engine）、桥接层（pipeline，GAP-P1-3）、多模态扩展层（multi_modal + cross_modal_fusion，Phase T）。
- **输入输出**：输入 = 文本串/文件路径/psutil 系统指标/API dict/内部事件；输出 = `PerceptionEvent`（内含 Observation + SemanticFragment + validation 元数据），经 pipeline 转为世界层 `WorldObservation` 写入 `WorldStore.update_from_observation()`，并推断 CausalityLink。
- **正常工作流程**：feed/poll 采集 → engine.tick() 逐条观察做语义提取（默认未注入）与验证（默认置信度≥0.5 通过，或注入 PerceptionValidator）→ 生成事件并回调 → PerceptionPipeline._bridge_to_world 映射为世界层观察（entity_id/claimed_state 由 resolver 或 metadata 提供，缺失则被 WorldValidator fail-closed 拒绝）→ 因果链推断。
- **异常处理逻辑**：传感器级 try/except 隔离（PS52-02），FileSensor/EnvironmentSensor 失败写 health 并返回空；目录消失 OSError 单目录跳过；psutil 缺失整传感器降级（2026-08-17 健康化补丁）；resolver 异常仅 debug 日志。
- **依赖其它 OCOS 模块（真实 import）**：pipeline.py → ocos.world_model（world_store.WorldStore、world_types、world_validator.ValidationResult）；multi_modal.py → 本模块内 text/file/environment/engine + cross_modal_fusion。其余文件仅依赖本模块 + 标准库（psutil 可选）。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/daemon/factory.py（PerceptionPipeline 生产装配，line 218）、ocos/daemon/__init__.py、ocos/interaction/cli/commands/run.py:75（FileSensor）；测试：ocos/tests/test_phase52.py、ocos/tests/test_multi_modal_perception.py、tests/test_perception_pipeline.py。
- **已知限制**：① 生产 PerceptionPipeline 默认**未接线** SemanticExtractor 与 PerceptionValidator（engine.semantic_extractor/validator 为 None，仅走内置置信度阈值），docstring 宣称的 Extract→Validate 链在生产装配中未启用；② 感知层 Observation 与世界层 Observation 同名不同类，pipeline 是唯一适配点（文档已注明）；③ SemanticExtractor 为关键词启发式（中英混合），实体提取正则字符类疑似乱码（见风险清单）；④ multi_modal 的 Audio/VisionSensor 只接受转录/描述文本，无真实音视频处理。
- **验证状态**：【功能实测可通】——导入冒烟全部 OK；ocos/tests/test_phase52.py 39 passed、test_multi_modal_perception.py、tests/test_perception_pipeline.py 21 passed（含 root tests）；pipeline 的 fail-closed 语义有测试覆盖。

##### 2. ocos/attention/（7 文件，约 962 行）

- **模块路径范围**：ocos/attention/__init__.py, attention_types.py, candidate_selector.py, scoring.py, focus.py, retrieval.py, recovery_integration.py
- **模块职责**：两层注意力体系。① Phase 39.5 认知焦点层（ABI）：从 Goal/Event/Maintenance 候选中按加权评分 + 惯性策略选择每 Tick 焦点，产出 AttentionState/AttentionTrace 审计；② Phase O 焦点管理器 AttentionFocus（整合 runtime.AttentionEngine 评分 + capability.Homeostasis 驱力）；③ Phase 24-D 注意力驱动记忆检索；④ Phase 39.5 快照恢复集成。
- **对外提供能力**：`CandidateCollector`（add_goal/add_event/add_maintenance）、`AttentionScoringEngine.score/select()`、`AttentionFocus.process_observation/update_from_homeostasis/set_focus/clear_focus`、`AttentionDrivenRetrieval.retrieve()`、`attention_state_to_snapshot/from_snapshot/validate_attention_restore`、类型 AttentionState（可序列化/反序列化）。
- **内部子模块**：types（FocusType/AttentionState/AttentionCandidate/InertiaPolicy/AttentionTrace/AttentionScoringWeights/FocusSelectionResult）、selector（纯收集器）、scoring（评分+惯性）、focus（驱力整合层）、retrieval（记忆检索）、recovery（快照桥）。
- **输入输出**：输入 = 候选项（TickPipeline 上游注入）、Observation、RegulateResult（驱力）、AttentionSignal（关键词）；输出 = FocusSelectionResult（含 trace）、FocusState、RetrievedItem 列表、快照 dict。
- **正常工作流程**：每 tick 清空收集器 → 上游 stages 填充候选 → scoring.score_all 评分排序 → 惯性判定（最小持续 3 tick + 冷却 5 tick + 新/旧分比>1.3）→ 切换或保持并写 AttentionTrace → AttentionState 可入 RuntimeSnapshot 恢复。
- **异常处理逻辑**：无候选返回"no candidates"结果；评分 clamp 到 [0,1]；检索侧 long-term/episodic 失败各自降级留痕（BR-04 B批 2026-08-25）。
- **依赖其它 OCOS 模块（真实 import）**：focus.py → ocos.runtime.attention_engine（AttentionEngine/AttentionScore/ContentAnalyzer/DefaultContentAnalyzer）、ocos.capability.homeostasis（DriveType/DriveSignal/RegulateResult）；retrieval.py → ocos.logging.get_logger。其余纯逻辑无 OCOS 依赖。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/runtime/stages/attention.py（types + CandidateCollector + AttentionScoringEngine，TYPE_CHECKING 延迟导入）、ocos/opentale_bridge/master_agent.py:259-260、ocos/proactive/output.py:25（AttentionFocus/FocusType）、ocos/cognitive_loop/attention_coordinator.py（AttentionFocus）、ocos/agent/memory_consolidation.py（AttentionDrivenRetrieval）；测试 test_phase39_5/39_6、test_attention_focus.py。
- **已知限制**：① **focus.py process_observation 存在真实 TypeError bug**（_update_focus(focus_target=…) 关键字名错且缺 score 实参，见风险清单 P2-01）；② InertiaPolicy.max_interruptions_per_minute 定义了但从未执行；③ AttentionState.focus_duration 属性公式 `(interrupted_tick or start_tick) - start_tick` 无中断时恒为 0，与 scoring 内另算的 `current_tick - start_tick` 不一致；④ AttentionDrivenRetrieval 缓存无 TTL 无上限；episodic 得分乘 recency_weight(0.3) 天然低于 long_term，为设计怪癖。
- **验证状态**：【功能实测可通】（types/scoring/selector/recovery/retrieval）+【逻辑不完整】（focus.py 的 process_observation 主路径运行即抛 TypeError，单测未覆盖该路径；其余 focus API 正常）。测试：test_phase39_5/39_6/test_attention_focus 均通过。

##### 3. ocos/evolution/（11 文件，约 1,932 行）

- **模块路径范围**：ocos/evolution/__init__.py, evolution_types.py, improvement_detector.py, evolution_proposer.py, impact_analyzer.py, evolution_sandbox.py, approval_engine.py, migration_engine.py, rollback_engine.py, evolution_memory.py, manager.py
- **模块职责**：Phase 47 认知进化治理——信号驱动的受治理自我改进闭环 Detect→Propose→Analyze→Sandbox→Approve→Migrate→Rollback→Memory。边界 CE47-01（进化≠自主）、CE47-02（提案≠执行）、CE47-03（迁移≠毁灭，可回滚）、CE47-04（禁改 identity/constitution/permission/core_values/anchor）。
- **对外提供能力**：`ImprovementDetector`（health/perf/pattern/gap/drift 五类信号检测）、`EvolutionProposer.propose()`、`ImpactAnalyzer.analyze()`、`EvolutionSandbox.validate()`、`ApprovalEngine.evaluate()/manual_approve()`（③受约束自主：低风险域自动批准 auto:governed，高风险域强制人工，U5.2 人工批准唯一 APPROVED 权威路径）、`MigrationEngine.migrate()`、`RollbackEngine`、`EvolutionMemory.record/proposal_history/...`、总管 `SelfEvolutionManager`（detect_and_propose/analyze/validate/approve/execute/rollback/get_status）。
- **内部子模块**：types（EvolutionState 11 态状态机、7 类 Trigger、8 个允许域 + FORBIDDEN_DOMAINS 五元组、ImpactAssessment、EvolutionProposal、RollbackRecord）、detector/proposer/analyzer/sandbox/approval/migration/rollback/memory/manager。
- **输入输出**：输入 = 指标信号（module/metric/value/threshold/severity）；输出 = EvolutionProposal（状态机流转）、SandboxReport、ApprovalVerdict/ApprovalRecord、MigrationResult、RollbackRecord、EvolutionStatus 摘要。
- **正常工作流程**：信号超阈值 → DetectedSignal → Proposer 按 trigger 映射 domain（含 FORBIDDEN 降级）生成提案(DRAFTING) → Sandbox 5 项检查（边界/描述/目标模块/change_type/replace 需快照）→ ApprovalEngine 5 道闸（sandbox→边界→CRITICAL 拒→HIGH 需治理链→受约束自主/人工）→ ready_for_migration → MigrationEngine 建快照并"执行"→ 失败触发回滚 → EvolutionMemory 全程记录。
- **异常处理逻辑**：沙箱失败/边界违规/CRITICAL 一律 REJECTED；迁移异常捕获后触发回滚并置 ROLLED_BACK；提案超 max_proposals(100) 返回 None。
- **依赖其它 OCOS 模块（真实 import）**：仅 ocos.logging（manager.py）；全部子模块互相依赖，无其他跨模块依赖。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/agent/self_evolution_link.py（Proposer/Sandbox/types/ImpactAnalyzer/DetectedSignal/EvolutionMemory/MigrationEngine）、ocos/agent/master_agent.py:2203/2296/2342（EvolutionTrigger/RollbackReason/EvolutionState）；测试 test_phase47.py、test_self_evolution_manager.py、test_master_agent_self_evolution.py。**注意**：evolution.ApprovalEngine 在生产代码中无调用方（extension/ 有自己的同名文件）；RollbackEngine 同样只有测试引用，manager 未使用它。
- **已知限制**：① MigrationEngine._execute 为**模拟实现**（只校验不真改任何模块，注释自认"模拟"）；② manager 的快照是提案描述字符串而非真实模块状态，rollback() 仅弹内存标记，**无真实恢复**；③ manager.analyze_proposal 调用 proposer 私有方法 `_build_initial_impact` 并用 type('Signal',(),{}) 伪造信号，且分析结果**未写回 proposal.impact**；④ manager.tick() 的 auto_approve 分支为空 pass 桩；⑤ approval_engine._auto_eligible 的 FORBIDDEN 分支不可达（EvolutionDomain 枚举不含禁止域，domain.value 永不落入 FORBIDDEN_DOMAINS）。
- **验证状态**：【功能实测可通】（治理状态机/审批/沙箱/记忆的纯逻辑闭环，test_phase47 + test_self_evolution_manager 通过）+【逻辑不完整】（迁移/回滚为模拟桩，无真实变异执行体）。

##### 4. ocos/learning/（6 文件，约 1,639 行）

- **模块路径范围**：ocos/learning/__init__.py, manager.py, experience_learning.py, skill_growth.py, metacognition.py, persistence.py
- **模块职责**：① Phase R 持续学习（ContinuousLearning/PreferenceModel：反馈→偏好建模）；② Phase 49-A 经验学习（Episode→LearningExample、失败诊断 FailureDiagnoser、规则聚合 RuleBasedLearner、LearningArtifact 统一契约 LESSON/RULE）；③ Phase 49-C 技能生长（TaskReplanner 失败重规划、SkillProposer 成功 N=3 次→候选技能、GovernedSkillCommitter 治理四段 CANDIDATE→VALIDATED→COMMITTED）；④ Phase 49-D 元认知（SkillSemanticMatcher 跨表面技能迁移、CapabilityConfidence 历史成功率→决策保守化升级 ASK）；⑤ FIX-08 rules/skills SQLite 持久化。
- **对外提供能力**：`ContinuousLearning.record_feedback/learn_from_interaction/get_preferences/generate_learning_report`、`FailureDiagnoser.diagnose`、`EpisodeExampleConverter.convert/convert_many`、`RuleBasedLearner.learn_fn`、`build_lesson_artifact/check_behavioral_delta`、`TaskReplanner.decide/should_retry/is_terminal`、`SkillProposer.propose_from_episodes`、`GovernedSkillCommitter.validate/approve/commit`、`SkillSemanticMatcher.match`、`CapabilityConfidence.evaluate`、`save_learning_rules/load_learning_rules/persist_latest_rules/load_learning_summary`。
- **内部子模块**：偏好学习（manager）、经验→样本/诊断/规则（experience_learning）、技能生长三件套（skill_growth）、语义匹配与置信评估（metacognition）、SQLite 持久化（persistence，表 learning_models）。
- **输入输出**：输入 = Episode（duck-typed：goal/outcome/decision/action/context/tags）、反馈文本、LearningExample 列表；输出 = LearningModel.rules（rule_id/task_pattern/success_count/fail_count/success_rate/failure_causes/samples）、LearningArtifact、SkillProposal、ConfidenceVerdict、ReplanDecision。
- **正常工作流程**：Episode 失败 → diagnose 归因为 7 类 FailureCause（确定性关键词）→ 转 LearningExample（reward 0/1）→ RuleBasedLearner 按 40 字符归一化 sha1 指纹聚合 + 增量合并 → LESSON artifact（CANDIDATE）→ 同指纹成功≥3 → SkillProposer 候选（写类需审批）→ validate/approve/commit 注册 Skill；决策前 CapabilityConfidence.evaluate：写类 + 成功率<0.4 + 证据≥3 → escalation="ask"（治理增强）。
- **异常处理逻辑**：convert/convert_many 单条异常入 skipped；persistence 写库失败降级内存返回 False 不阻塞 daemon；commit 注册失败返回 None。
- **依赖其它 OCOS 模块（真实 import）**：experience_learning → ocos.models.learning（LearningExample/LearningModel/LearningStrategy，延迟导入）；skill_growth → ocos.capability.models（Skill，延迟导入）；其余纯逻辑。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/agent/master_agent.py:908（skill_growth 三件套）、:1577（experience_learning）、ocos/agent/agent_runtime.py:1084-1085（TaskReplanner/FailureDiagnoser）、ocos/interaction/converse.py:358/628（load_learning_summary/load_learning_rules）、ocos/daemon/__init__.py:537（persist_latest_rules）、ocos/daemon/factory.py:92（CapabilityConfidence）；测试 test_continuous_learning、test_phase49_*、tests/test_learning_rule_consumption.py。
- **已知限制**：① ContinuousLearning.learn_from_interaction 用英文关键词子串匹配判反馈极性（"no" 会误中 "know/not"，中文反馈全落入 CORRECTION 兜底）；② PreferenceModel 已有偏好只更新置信度**不更新 value**（首次值固化）；③ SkillProposer 的 procedure 用 zip(agent_types, task_types)，episode 缺字段时序列错位配对；④ metacognition._find_matching_rule 兜底循环两个分支条件等价（冗余）；⑤ 治理红线清晰：N=3 只产候选不授权，低置信只升 ASK 不放宽。
- **验证状态**：【功能实测可通】——test_continuous_learning、test_phase49c_skill_growth、test_phase49d_metacognition、test_phase49_experience_learning、tests/test_learning_rule_consumption.py（7 passed）全部通过；纯确定性规则实现，无 LLM 依赖。

##### 5. ocos/growth/（2 文件，约 857 行）

- **模块路径范围**：ocos/growth/__init__.py, engine.py
- **模块职责**：Phase 50 成长模块——外部智能体（Hermes 等）投递技术情报 TechSignal → LLM 分析生成对 OCOS 自身代码的优化提案 → 受治理自动执行（快照→修改→语法门→测试→失败自动回滚），SQLite 审计。治理不变量：变异唯一权威是 Decision/SelfModificationAgent（本模块可注入 modifier），只改 ocos/ 下 .py，禁 .env/config/.git/.venv，高风险冻结待人工。
- **对外提供能力**：`GrowthEngine.ingest/analyze_pending/execute_proposal/grow_once`、`GrowthAnalyzer.analyze`（含 patch 精确性重试）、`GrowthOptimizer.validate_path/apply`、`GrowthSignalStore`（tech_signals + growth_log 两表持久化）、`TechSignal/GrowthProposal/GrowthResult` 数据类、常量 PROJECT_ROOT。
- **内部子模块**：G1 信号接收存储（store）、G2 LLM 分析（analyzer：候选文件扫描、prompt 构造、响应解析、路径安全、规模护栏）、G3 受治理执行（optimizer：快照/回滚/测试）、编排（engine）。
- **输入输出**：输入 = TechSignal（topic+summary≥60 字符）；输出 = GrowthProposal（整文件式 new_content 或 patch 式 old_snippet→new_snippet）、GrowthResult（proposed/skipped/applied/rolled_back/rejected/guarded）。
- **正常工作流程**：ingest 校验长度入库 → analyze：扫描 ocos/ 真实 .py 词元评分取 top8 + 上下文摘录锚定 → LLM 出 JSON → 解析（剥 fence/提取 {...}）→ 路径白名单 + 真实存在 + patch 逐字唯一匹配 + 规模护栏（净删除≤30 行、保留≥50%）→ apply：validate_path → applicability≥0.6 → 规模护栏二次 → 磁盘+内存快照 → 变异（modifier 或内置）→ py_compile 语法门 → 目标模块专属 pytest 或 import 门 → 失败回滚 → log_result。
- **异常处理逻辑**：LLM 失败/超时/不可解析返回 None 不阻断；写入异常回滚；pytest 超时 180s/import 门 60s 记 1 failed；回滚优先磁盘 .bak，原为新文件则删除。
- **依赖其它 OCOS 模块（真实 import）**：ocos.logging.get_logger；modifier 接口为 duck-typing（SelfModificationAgent.execute(task,file,content,test,dry_run)），无硬依赖。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/interaction/cli/commands/growth.py:17（CLI 命令 `_make_engine`）；测试 ocos/tests/test_phase50_growth.py、tests/test_growth_engine.py。
- **已知限制**：① FORBIDDEN_FILES 中的通配模式（"*.db"、"*.sqlite"）用 `p.name in FORBIDDEN_FILES` 精确比较，**glob 永不命中**（实际靠 .py 后缀兜底）；② 快照 _snapshots 仅进程内存 + /tmp 磁盘，跨进程回滚靠磁盘副本；③ 信号状态只推进到 analyzed，applied/skipped 状态值定义了但从未 mark；④ 未注入 llm_fn 时 analyze 恒返回 None（GrowthEngine() 默认无 LLM，需要 CLI 侧注入）。
- **验证状态**：【功能实测可通】——test_phase50_growth 30/31 passed、tests/test_growth_engine.py 通过；唯一失败 test_project_root_untouched_after_suite 为**环境性失败**：该防污染回归用 git diff 白名单比对，当前工作区有未提交改动（ocos/goal/store.py 等，非本模块造成）不在白名单内，与 growth 模块逻辑无关。

##### 6. ocos/reflection/（2 文件，约 960 行）

- **模块路径范围**：ocos/reflection/manager.py, self_review.py
- **模块职责**：① Phase AE SelfReflectionManager——自我反思统一管理层：反思轨迹（5 类型×4 深度）、洞察记录、智慧（Wisdom）候选/验证/使用计数、身份快照与连续性检查、批量反思；② Phase 52 自省分析器 self_review——只读采集运行证据（episodes/goal/belief/event/DLQ/growth/working_memory + 代码资产双域）→ LLM 综合分析不足与升级方向 → Markdown 报告落盘 docs/self_review/。
- **对外提供能力**：`SelfReflectionManager.start_reflection/add_insight/complete_reflection/propose_wisdom/verify_wisdom/create_identity_snapshot/check_identity_continuity/batch_reflect/get_stats`；`SelfReviewCollector.collect`、`SelfReviewAnalyzer.analyze`、`render_markdown`、`write_report`。
- **内部子模块**：反思轨迹/智慧/身份三存储（各带 RLock）、证据采集（mode=ro sqlite）、自检断言 R3（C1-C4）、LLM 分析、报告渲染。
- **输入输出**：输入 = 反思请求（type/subject/depth）、事件 dict 列表、DB 路径/仓库根；输出 = ReflectionTrace/WisdomItem/IdentitySnapshot、ReviewEvidence（30+ 指标）、分析 JSON（overall_health/weaknesses/upgrades/biggest_bottleneck）、Markdown 报告。
- **正常工作流程**：start→add_insight→complete 形成 trace；智慧候选 confidence 达标后 verify；身份连续性 = 近窗快照平均 continuity_score<0.7 判漂移。自省：collect（episodes 成败以 outcome JSON 精确判定、失败模式关键词聚类、7d 窗口 julianday 时间比较、代码资产域防"运行数据≠能力"盲区）→ _run_self_checks 自检 → LLM 分析（带 5 条分析纪律：双域辨析、时间窗、可信度降级等）→ 报告。
- **异常处理逻辑**：采集每段独立 try/except 降级；DB 不存在仍采集代码资产域；LLM 失败返回 {"error"}；write_report 目录自动创建。
- **依赖其它 OCOS 模块（真实 import）**：manager.py → ocos.logging；self_review.py → ocos.logging + ocos.engines.text_generator.get_text_generator（默认 LLM，延迟导入，可注入替换）。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/agent/master_agent.py:2573/2588（ReflectionType/ReflectionDepth/InsightType）、ocos/interaction/cli/commands/self.py:78（SelfReviewCollector/Analyzer）；测试 test_self_reflection_manager.py、test_master_agent_reflection.py、test_phase52_self_review.py、tests/test_reflection_self_review.py。
- **已知限制**：① manager 全内存、无持久化，重启即失（与 self_review 的 SQLite 只读形成对比）；② propose_wisdom 达上限(100)直接拒绝无淘汰；③ check_identity_continuity 的漂移阈值 0.7 硬编码；④ self_review 失败模式聚类是固定关键词表，覆盖面有限。
- **验证状态**：【功能实测可通】——test_self_reflection_manager + test_phase52_self_review + tests/test_reflection_self_review.py（LLM mock 注入）均通过。

##### 7. ocos/cognitive_nutrition/（5 文件，约 1,192 行）

- **模块路径范围**：ocos/cognitive_nutrition/__init__.py, nutrition_model.py, data_feeder.py, digestion_monitor.py, nutrition_protocol.py
- **模块职责**：Phase 58.2 认知营养协议 v1.0——7 天数据喂食实验框架：Day0 空腹基线 → Day1 事实 → Day2 技术文档 → Day3 长文本（陌生小说《The Glass Archive》约 10K 字符）→ Day4 冲突对 → Day5 用户偏好 → Day6 综合任务 → Day7 健康复检。验证"输入↑→记忆↑→知识↑→决策稳定→身份不漂→健康不降"，五类失败判据（记忆爆炸/知识污染/身份漂移/能力幻觉/目标自生成）任一触发即 EMERGENCY_STOP。
- **对外提供能力**：`CognitiveNutritionProtocol.run()`、`run_nutrition_protocol()`、`DigestionMonitor.feed_meal/feed_meals/compare_health/growth_summary`、DAY_FEEDERS/TOTAL_MEALS、数据类 DataMeal/FastingBaseline/DigestionObservation/DayNutritionResult/NutritionReport（to_dict/to_json）。
- **内部子模块**：模型层（天数/餐型/观察/结果/报告）、数据生成层（6 个 day feeder）、监测层（消化观察分类器）、协议执行层（日程编排 + 按日判据 + 紧急停止）。
- **输入输出**：输入 = 内置新鲜数据（AI 史实 15 条、工程文档 5 篇、小说 1 篇、冲突对 5 组、偏好对话 6 段、任务 1 个）+ 可注入 identity_check_fn/health_recheck_fn/decision_quality_fn；输出 = NutritionReport（JSON 可序列化）。
- **正常工作流程**：建基线（identity_hash=sha256(anchor:constitution) 前 16 位）→ 逐日取 feeder 产餐 → monitor.feed_meal 估算记忆/知识增量（调用方可传实测值覆盖）→ _classify_observation 定级（幻觉>0→HALLUCINATION、身份漂→POLLUTION、增长率>50→WARNING）→ 按日判据记 findings/warnings/failures → Day7 健康对比 → 汇总 healthy_digestion 判定。
- **异常处理逻辑**：feeder 缺失返回空 PASS 日；失败判据触发后 break 并生成 EMERGENCY_STOP 记录。
- **依赖其它 OCOS 模块（真实 import）**：无——完全自包含（仅标准库 + 模块内互引）。
- **被哪些 OCOS 模块调用（grep 反查）**：**生产代码零调用方**，仅 ocos/tests/test_phase58_2.py 引用。
- **已知限制**：① **本质是自模拟框架**：默认路径下 memory_after/knowledge_after 用 monitor 内部每餐固定估算值（fact=1、document=2…），decision_quality 默认恒 1.0，health_recheck_fn 默认返回初始值——即不接真实 OCOS 内省时"消化过程"是合成数据，非真实系统观测；② identity_hash 默认恒定 → identity_drifted 默认永远 False（除非注入 check fn 或真实 hash）；③ data_feeder Day5 循环变量 `for i, i in enumerate(interactions)` 变量遮蔽（功能可用但 metadata["interaction_id"] 存的是整个 dict）；④ TOTAL_MEALS 常量只作声明未被协议执行器使用。
- **验证状态**：【静态推演验证】+【逻辑不完整】——test_phase58_2.py 全部通过（44 测试在 428 passed 之内），纯逻辑自洽；但作为"验证 OCOS 真实消化能力"的协议，未接任何真实 OCOS 子系统，默认运行为合成演练而非真实观测。

##### 8. ocos/cognitive_continuity/（7 文件，约 1,012 行）

- **模块路径范围**：ocos/cognitive_continuity/__init__.py, continuity_types.py, life_memory_graph.py, cognitive_timeline.py, identity_continuity.py, knowledge_aging.py, continuity_checkpoint.py
- **模块职责**：Phase 49 认知连续性系统——回答"OCOS 使用 5-10 年后如何保持连续人格与认知积累"。四支柱：Life Memory Graph（经验→日→周→月→年层次提炼，质量>数量 CC49-01）、Cognitive Timeline（过去/现在/未来意图三段，CC49-04 意图≠预测）、Identity Continuity（漂移检测不阻止演化 CC49-02）、Knowledge Aging（五级降权 FRESH 1.0→ARCHIVED 0.0，核心知识免疫 CC49-03）+ 连续性检查点。
- **对外提供能力**：`LifeMemoryEngine.record_experience/aggregate_day/week/month/year/recent_memory/important_memories/by_tag`、`TimelineEngine.record_decision/record_milestone/record_evolution/snapshot_present/record_intent/significant_events`、`IdentityContinuityEngine.create_snapshot/check_continuity`、`KnowledgeAgingEngine.register/age_all/reference/active_knowledge/weight_summary`、`ContinuityCheckpoint.create_checkpoint`。
- **内部子模块**：类型层（TimeGranularity 6 级/TimeAnchor/ExperienceNode/TimeContainer/LifeMemoryGraph/TimelineEntry/CognitiveTimeline/IdentitySnapshot/KnowledgeAge/AgedKnowledge）、四引擎 + 检查点。
- **输入输出**：输入 = 经验（tick/summary/importance/tags）、决策/里程碑/演化事件、身份快照字段、知识条目；输出 = 层次化记忆容器、TimelineEntry、ContinuityCheck（is_consistent/drift_detected/anomalies/severity/recommendation）、AgedKnowledge（weight 衰减）、CheckpointState（保留 52 个≈一年）。
- **正常工作流程**：经验 importance≥0.1 才入库，超 10000 条按重要性淘汰 → 周期性 aggregate 逐层提炼（各层 max_entries 30/20/15/10，容器数 365/52/24/10 封顶）→ 定期 create_snapshot + check_continuity（风险偏好变+0.3、决策风格变+0.2、智慧倒退+0.3、核心记忆替换>50%+0.4 → severity 累加）→ knowledge aging：引用即刷新 FRESH，未引用按 tick 推进分级降权，is_core 恒 1.0。
- **异常处理逻辑**：无历史快照返回默认一致；知识无匹配引用静默 False；容量溢出静默裁剪。
- **依赖其它 OCOS 模块（真实 import）**：无——仅模块内互引 + 标准库。
- **被哪些 OCOS 模块调用（grep 反查）**：ocos/agent/continuity_trigger.py:28-38（CheckpointState/ContinuityCheckpoint/TimelineEngine/IdentityContinuityEngine/KnowledgeAgingEngine/LifeMemoryEngine）；测试 ocos/tests/test_phase49.py。
- **已知限制**：① **无 aggregate_season 方法**——类型与 MAX_SEASONS=16 定义了 SEASON 层但引擎未实现季度聚合；② check_continuity 对比基准取 snapshots[-2]（倒数第二个），隐含"current 已 append"的调用约定，若调用方未先 append 则与最新快照比较，语义易误用；③ 引用刷新把 weight 硬置 1.0 不走 _weight_for_age；④ 全内存无持久化，"5-10 年连续性"依赖外部（agent/continuity_trigger）落盘，本模块自身不保证。
- **验证状态**：【功能实测可通】——ocos/tests/test_phase49.py 在实跑通过之列；纯数据结构 + 确定性规则，逻辑自洽。

---


#### 分组 审计分组 W9：goal 目标系统 + daemon 守护进程 + execution 执行闭环(DecisionBridge) + audit + diagnosis + health_examination + living_verification + living_test

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/goal/（12 个文件）

- **模块路径范围**：`/home/laogao/Documents/trae_projects/ocos/ocos/goal/`
- **模块职责**：目标（Goal）域层——目标数据类型、持久化、创建宪法约束（Phase/来源隔离）、自然语言解析、层级分解树、生命周期健康监控（Phase 39.6 维护子系统）、进度追踪、合法性校验。模块自述定位："Goal Maintenance 不创造目标，只维护已有目标"。
- **对外提供能力**：
  - `GoalStore`（store.py）：goals 表 / plan_dag 表 SQLite 持久化（save / load / load_active / claim_pending_human / requeue_stale_active / mark_completed / update_progress / save_plan_dag / load_plan_dag / record_decision）。
  - `GoalFactory`（factory.py）：带宪法约束的 Goal 创建（MISSION 禁止动态创建；Phase 21 只允许 SYSTEM；Phase 22-24 禁止 SELF）。
  - `GoalOriginEnforcer`（enforcer.py）：创建校验（verify_creation）与修改校验（verify_modification，禁止 origin_level 变更与 authority 提升），返回 `ConstitutionResult`。
  - `GoalMonitor` + `MaintenanceEngine`（goal_monitor.py / maintenance_engine.py / maintenance_types.py）：目标健康评估（ACTIVE/WARNING/STALLED/BLOCKED/COMPLETED/INACTIVE 六态），产出 `GoalHealthSnapshot` 与 `MaintenanceEvent`（流向 EventBus → Attention）。
  - `GoalParser`（parser.py）：纯规则中文自然语言 → UserGoal（domain 关键词/数字约束/优先级）。
  - `GoalTree`（tree.py）：层级分解树（max_depth=3、子目标必须 decomposed 来源、maintenance() 清理终端子树、count_by_status 统计）。
  - `GoalTracker`（tracker.py）：内存态进度追踪（start/update/complete/get_elapsed）。
  - `GoalValidator`（validator.py）：来源合法性 + 树合法性（human root、decomposed child、循环检测）。
  - `models.py`：deprecated 转发层，全部 re-export 自 `ocos.kernel.goal_types`（Goal/GoalStatus/GoalSource/UserGoal 等）。
- **内部子模块**：如上 12 文件，models.py 是唯一的兼容垫片。
- **输入输出**：输入为自然语言文本（parser）、Goal 对象（monitor/enforcer）、SQLite goals 表行（store）；输出为 UserGoal/Goal 对象、GoalHealthSnapshot/MaintenanceEvent、dict 行记录。
- **正常工作流程**（目标生命周期状态机）：
  - kernel 层 GoalStatus 状态机：`PENDING → ACTIVE → COMPLETED`，另有终止态 `CANCELLED / FAILED / SUPERSEDED / EXPIRED`（store.load_active 的排除集合）与 agent 层的 `ABANDONED`（tree.maintenance 使用）。tree/validator 层另有 `GoalSource.HUMAN/DECOMPOSED` 与 `GoalSource.SELF(非法)` 之分。
  - 主闭环（daemon 驱动）：① CLI/chat 提交目标 → 写入 goals 表 status=PENDING, origin_level=HUMAN；② daemon 每 tick 调 `GoalStore.claim_pending_human(limit=1)` 原子置 ACTIVE 并导入 runtime._goal_store；③ AgentRuntime Step6 分解/执行；④ 完成后 `mark_completed()` 置 COMPLETED + progress=1.0（域层闭环，2026-09-01 P1 修复补齐）；⑤ 崩溃恢复：daemon start() 调 `requeue_stale_active()` 把孤儿 ACTIVE 回收为 PENDING。
  - 并行闭环（kernel/agent 层，tree.py 维护）：GoalStatus 枚举含 PENDING/ACTIVE 及 is_terminal 属性；GoalTree.add_child 强制 max_depth=3、子目标 source=DECOMPOSED、父目标非终端态。
  - 健康监控闭环（Phase 39.6）：MaintenanceEngine.run_maintenance() → GoalMonitor.evaluate() 按 stall_ticks(500)/warning_ticks(200)/attention_age_threshold(100)/min_progress_score(0.1) 判定健康 → needs_attention 的快照转为 MaintenanceEvent（severity: WARNING 0.4 / STALLED 0.7 / BLOCKED 0.9）→ 上层 EventBus/Attention。
- **异常处理逻辑**：store 所有写操作 try/rollback/raise；claim 用 `UPDATE ... WHERE status='PENDING'` 原子防多 daemon 重复认领；monitor 对非 dict metadata、缺属性 Goal 全部 getattr 防御；GoalMonitorConfig.__post_init__ 校验 warning_ticks < stall_ticks；tree 所有公开方法 RLock 保护。
- **依赖的其它 OCOS 模块（真实 import）**：`ocos.storage.connection`（store.py）、`ocos.kernel.goal_types`（models.py/enforcer.py）、`ocos.agent.goal_types`（factory.py —— 注意与 kernel.goal_types 是两套类型）。
- **被哪些 OCOS 模块调用（grep 反查）**：`ocos.autonomous.goal_manager.py`（GoalStore+GoalOriginEnforcer）、`ocos.agent.agent_runtime.py`（L712 GoalOriginEnforcer；L1300 GoalStore）、`ocos.agent.control_loop.py`（GoalFactory/GoalOriginEnforcer）、`ocos.interaction.base.py`（models.UserGoal）、`ocos.interaction.converse.py`（GoalStore 多处）、`ocos.interaction.repl.commands.goal`、`ocos.interaction.cli.commands.goal`、`ocos.daemon.__init__.py`（GoalStore claim/requeue）、`ocos.homeostasis.py`（re-export GoalMonitor）。测试：test_goal_claim/test_phase22_prompt1/test_phase38_5_rgv/test_phase39_6/test_goal_origin_model/test_phase21_prompt3。
- **已知限制**：
  - 两套 Goal schema 并存（goals 表 vs agent 层 goal 表），字段互斥，store.py 头注释明言未合并；
  - factory.py 用 `ocos.agent.goal_types` 而 enforcer/models 用 `ocos.kernel.goal_types`，同模块内双类型体系；
  - GoalMonitor/MaintenanceEngine 在生产 daemon 路径中**未被接线**（无 daemon/agent 调用点，仅 homeostasis.py re-export + 测试）；
  - parser/tracker/tree/validator 为 Phase 26 独立小体系，生产主闭环（daemon+agent_runtime）不经过它们，仅测试消费；
  - store.save() 用 INSERT OR REPLACE，progress 恒写 0.0（重复 save 同一 goal 会重置进度）。
- **验证状态**：【静态推演验证】—— store 的认领/回收/完成闭环有 test_goal_claim 等覆盖且被 daemon 真实调用；但 GoalMonitor/GoalTree/GoalParser/GoalTracker/GoalValidator 属于"建好未上主线"的旁路子系统，仅测试触达。

##### 2. ocos/daemon/（14 个文件）

- **模块路径范围**：`ocos/daemon/`（14 文件：__init__.py 即 ResidentRuntime 本体 + factory.py + health_loop.py + repair_link.py + self_check.py + improve_link.py + motivation.py + boot_awareness.py【v1.3.1 新增】 + watchdog.py【v1.3.1 新增】 + growth_narrative.py + vitals_report.py + continuity.py + active_interaction.py + channel_link.py）。本节详录核心六个（__init__/factory/health_loop/repair_link/boot_awareness/watchdog），其余为已上电的支线上电链（自检/自改进/动机/成长叙事/生命体征/连续性/主动交互/通道联动），机制散见各审计分组对应章节。
- **模块职责**：常驻运行时守护进程。tick 循环驱动认知内核、目标队列、消息收件箱、dream 巩固、心跳落盘、健康体检、诊断循环上电；启动即执行启动自省（审视自身与环境）；factory.py 为生产装配层。
- **对外提供能力**：`ResidentRuntime`（start/stop/submit_goal/get_status/attach_decision_bridge/attach_health_loop/attach_perception_pipeline/state/cycle_count/memory_hub/session_manager）；factory 的 build_master_agent / build_cognitive_engines / build_health_loop / build_perception_pipeline / build_knowledge_registry / build_knowledge_abi / build_execution_bridge / _make_confidence_source；`HealthLoop`（bind/tick/run_check/last_finding/last_detail）；repair_link 的 run_diagnosis_cycle / execute_system_repair。
- **tick 循环（重点）**：`_tick_loop()`（__init__.py L335-429）单线程 `ocos-daemon` 循环，每轮依次：
  1. `_hb_ticks % 5 == 0` → `_write_heartbeat()` 写 `~/.ocos/daemon_heartbeat.json`（pid/cycle/ts，Web 侧栏判活）；
  2. `% 5 == 0` → `_push_goal_results()`：增量游标（首调定位 episodes 表 max rowid，此后把 tags 含 goal_result 的新 episode 经 `UserInbox.post_outbound` 推送"目标执行完成"）；
  3. `% dream_interval_ticks(默认200) == 0` → `_run_dream_cycle()`；
  4. `_drain_goal_queue()`：每 tick 最多消费 1 个队列目标，构造 kernel 层 `Goal(origin_level=HUMAN, authority=FRAMEWORK, level=TASK, caller='daemon')` 写入 runtime._goal_store（Step 6 消费）；
  5. `_claim_persisted_goals()`：`GoalStore.claim_pending_human(limit=1)` 认领 CLI 创建的 PENDING 人类目标（domain 从 metadata 读取，默认 writing）；
  6. `_drain_user_inbox()`：消费 ocos say 消息 → ChatResponder.respond_auto 统一路由（任务类受理为目标并注入 goal_id），回复写回收件箱 + outbound；失败也诚实写回错误（FIX-VAL1）；responder 缺失回退 `inject_user_message`；
  7. `kernel.tick_loop(max_ticks=1)`（P1-C：认知循环唯一宿主 = RuntimeKernel，AgentRuntime.tick 经 attach_agent_driver 注入）；
  8. 伴生 LifeCycleOrchestrator：attention.needs_sleep() → 触发 dream；每 60 tick `maybe_proactive_output()`；
  9. 每 120 tick SelfMonitor.run_once() 自我演化检查；
  10. `health_loop.tick()`（内部按 interval_ticks=100 节流）；
  11. `perception_pipeline.tick()`（无传感器零开销）；
  12. 分段睡眠（0.1s 粒度）响应 stop；idle 降速（max_idle_cycles>0 时 idle 达标后 sleep×3）。
  13. **自愈兜底（v1.3.1）**：循环体最外层 try/except——子项精细保护之外的残余异常记日志（"Tick loop residual failure"）并继续下一 tick。此前任一裸调用异常（如 `_drain_user_inbox` fallback 的 `inject_user_message`）会杀死 tick 线程 → 心跳停更 + 全部自主循环停摆 + 进程仍存活（systemd Restart=on-failure 不触发）→ daemon 永久僵死；现线程级兜底封死该单点。
- **启动自省（v1.3.1 重点）**：start() 流程在 V5 连续性校验后、tick 线程启动前调用 `boot_awareness.run_boot_awareness(db_path, post_fn, stimulus_fn, level)`——详见本节 boot_awareness 详录。
- **dream 机制（重点）**：`_run_dream_cycle()`（L513-545）：修复生命周期相位（BOOTING → transition_to_phase(ACTIVE)，注释说明此前直接 dream() 会因 "Cannot transition BOOTING to DREAMING" 抛错导致巩固管线从未运转）→ `agent.sleep()`（ACTIVE→SLEEPING，WM 巩固+持久化）→ `agent.dream()`（SLEEPING→DREAMING→巩固→wake）→ `persist_latest_rules(agent, db_path)` 持久化 learning rules（FIX-08/20：原实现读不存在的 `agent_obj.learning` 属性致持久化从未生效）。
- **心跳**：见上第 1 步；每 5 tick 一次降低写盘影响。
- **预算/背压管理（重点）**：目标队列 `max_queue_size=50` 背压——队列满时 submit_goal 诚实拒绝返回 -1；runtime_scheduler.PriorityQueue 同步 push（best-effort）；LLM 日预算在 execution/bridge（见下）。
- **factory 装配链**：build_master_agent（MasterAgent + 五个真实认知引擎 + BehavioralConstitution + proactive 回调→UserInbox）；build_execution_bridge（R4-A：DecisionBridge + PendingStore + attach_default_handlers + L8 元认知置信度源 `_make_confidence_source`——从 episodes 表统计近 30 天 goal_result 成功率，bi-gram 匹配，注入 CapabilityConfidence.evaluate）；build_health_loop（AlertManager Log+File 通道 ~/.ocos/alerts/alerts.log + CognitiveExaminer + HomeostasisManager）。
- **HealthLoop**（health_loop.py）：每 interval_ticks(默认100) 次执行 run_check()：采集 memory_hub stats（episode/pattern 数）、goal 栈深、WM 占用、决策失败率（`_last_attention_decisions` 未接受比例）→ CognitiveExaminer.examine_memory / examine_decision（空选项建基线，漂移永不误报）→ HomeostasisManager.health_report() → 告警（Log+File）。fail-closed：任一采集失败降级 0/空继续。tick() 末尾调 `run_diagnosis_cycle(db_path)`（PW-3.1 诊断循环）。
- **repair_link 诊断循环**：SystemProbe.capture → FaultDetector.feed → 每信号构造 DiagnosisReport（confidence 固定 0.8）→ RepairProposer.propose → 过滤：不可逆提案不入队、步骤未全白名单不入队（`_step_whitelisted`：重建索引/REINDEX、清理缓存/CLEAR_CACHE、重新连接/RECONNECT、归档/修剪）→ PendingStore 待批（approval_disabled 时带 3600s 冷却直接执行）；另有记忆膨胀确定性检测（episodes 表 >20 条 30 天前低显著度 → 归档提案）。`execute_system_repair`：构造 proposal stub → RepairExecutor（checkpoint→步骤执行→失败回滚）；白名单执行器 `_execute_step`：REINDEX+integrity_check / WAL checkpoint / AdapterDiscovery 重扫 / 归档 30 天前低显著度 episodes（行级转存 JSON 到 ~/.ocos/repair_checkpoints）；未知步骤诚实失败。
- **输入输出**：输入 = agent 对象、db_path、CLI 目标、UserInbox 消息、系统快照；输出 = 心跳 JSON、出站消息、PendingStore 待批项、告警日志、诊断/修复结果 dict。
- **异常处理逻辑**：几乎所有旁路子系统（LifeCycleOrchestrator/SelfMonitor/GoalStore/SessionManager/UserInbox/ChatResponder/PriorityQueue）均 try/except + logger.warning 降级装配；tick 内每段独立 try；stop 用 threading.Event + 30s join。
- **依赖**：`ocos.agent.agent_runtime`、`ocos.agent.life_cycle_orchestrator`、`ocos.self.{monitor,builder,governor,identity_boundary}`、`ocos.runtime.runtime_kernel`、`ocos.runtime_scheduler.{priority_queue,scheduler_types}`、`ocos.goal.store`、`ocos.interaction.{session_state,inbox,converse}`、`ocos.perception.pipeline`、`ocos.world_model.world_store`、`ocos.learning.persistence`、`ocos.learning.metacognition`、`ocos.alerts.{manager,channels,models}`、`ocos.capability.homeostasis`、`ocos.health_examination.cognitive_examiner`、`ocos.diagnosis.*`、`ocos.execution.{bridge,pending}`、`ocos.capability_reality.adapter_discovery`、`ocos.knowledge.*`、`ocos.storage.connection`。
- **被调用**：`ocos.interaction.cli.commands.run.py`（L51-59 全套 build_* + ResidentRuntime，主生产入口）、`ocos.interaction.cli.commands`（factory 下沉 import 规则合规）、测试 test_goal_claim/test_single_main_loop/test_phase_fix17_proactive/test_immune_system/test_execution_bridge。
- **已知限制**：daemon 状态机 STOPPED/STARTING/RUNNING/STOPPING 无持久化；`_push_goal_results` 直接 `self._user_inbox._db_path` 私有属性 + 裸 sqlite3 连接；kernel restart 语义依赖 state.name 字符串比较；HealthLoop 决策漂移检测恒不触发（空 chosen_option）。
- **boot_awareness 启动自省（v1.3.1 重点，boot_awareness.py）**：数字生命"每次断电/关机启动后像人一样先审视自身情况"的能力。主入口 `run_boot_awareness(db_path, post_fn, stimulus_fn, level)`（daemon start 后调用一次），四环节：① **采集** `_collect`（全只读探查 + 每项失败降级不阻断）：内核 `uname -r`、uptime `/proc/uptime`、磁盘 `df -BG`、内存 **`/proc/meminfo` MemAvailable**（关键坑：`free -g` 受中文 locale 影响列头为「内存：」致 awk 匹配失败返回 -1，已改读 /proc/meminfo 无 locale 依赖）、CPU `nproc`、GPU `nvidia-smi`（失败退 lspci）、网络（本机 IP + 国内外连通探测，最坏 ~6s）、自身状态（episodes/goals 计数、成长叙事章节数）、boot_id 与上轮对比 → 推断是否经历重启与停机时长（关机/断电不可区分则诚实注明）；② **分析** `_analyze`：产出 ok/warn/bad 三级 findings（GPU 缺失/离线/仅国内可达/磁盘低水位/内存压力/重启事件）；③ **适应**：环境快照写 `~/.ocos/boot_context.json`（boot_id/网络状态/GPU/磁盘/内存/CPU/重启推断，供 bridge `_boot_context_hint` 注入目标执行——目标规划基于本 boot 实测环境而非过时记忆，文件缺失/解析失败静默返回 "" 零开销）+ 异常条件（key_bad 非空）转刺激 `propose_stimulus` 走 MotivationHub 三道闸（升级阶梯/预算/饱和）；**全正常时诚实沉默零刺激提案（不编造动机）**；④ **汇报**：报告 `post_outbound(kind="report")` 推对话流（绿色面板）+ episode 落盘（source='boot_awareness'）。执行失败整体降级，不阻断 daemon 启动。验证状态：【功能实测可通】（tests/test_boot_awareness_20260908.py 15 项 + 生产 E2E：boot_context.json 落盘、journalctl "Boot awareness done"、episodes+user_messages 各 2 条、环境正常 0 刺激）。
- **watchdog 心跳看门狗（v1.3.1 重点，watchdog.py + systemd timer）**：三层自愈模型的 L2 层——修复"进程活着但认知循环停摆"的假死缺口（systemd Type=simple 只监控进程退出，不覆盖线程僵死）。`run_watchdog(stale_s=90)`：读 `~/.ocos/daemon_heartbeat.json`（daemon 每 5 tick≈25s 写一次）→ **文件不存在 = daemon 被人为 stop/从未启动，诚实跳过不误杀**；age ≤90s（UI 30s 判活阈值的 3 倍容错）= 健康零动作；age >90s = tick 循环推定死亡 → `systemctl --user restart ocos-daemon` → 结果 JSONL 记账 `~/.ocos/ops/restart.log`（user=watchdog，与 cli restart.py 同格式）。由 `ocos-watchdog.timer` 每 2 分钟调度（OnBootSec=2min，oneshot 无守护进程）。顺带职责：每日首次运行 SQLite 在线备份（`backup` API 不锁库）→ `~/.ocos/backups/ocos-YYYYMMDD.db` 保留 7 份（`.last_backup_day` 节流）——消除白皮书此前"自动备份：无"的 P3 缺口。验证状态：【功能实测可通】（tests/test_watchdog_20260908.py 7 项 + 生产 E2E 演练：心跳回拨 300s → action=restarted + 记账 + daemon 恢复且 Boot awareness 自动重跑；注意演练须回拨后立即运行——daemon 下个 tick 会覆写心跳）。
- **验证状态**：【静态推演验证】+【功能实测可通】（tick 循环/认领/dream/心跳均有测试与生产 run.py 装配路径；v1.3.1 新增自愈兜底 + 启动自省 + 看门狗均经生产 E2E 实弹验证）+ 部分【静态推演验证】（repair_link 的自动修复路径依赖 OCOS_APPROVAL_MODE 配置与白名单命中，主流程经 test_immune_system 覆盖）。

##### 3. ocos/execution/（4 个文件，含 DecisionBridge）

- **模块路径范围**：`ocos/execution/`
- **模块职责**：R4-A 执行回路——把自治循环决策（core_loop / TaskDAG 任务）接到 capability_reality / SandboxOps / digital_world 真实执行，含风险分级、审批队列、审计留痕；另含 Phase 51 CLI 直接执行器。
- **DecisionBridge 决策闭环机制（重点，bridge.py L116-1148）**：
  - **类**：`DecisionBridge`；数据类 `ActionVerdict`（action_type/verdict[auto|ask|deny]/status/summary）、`BridgeReport`（source/decision_text/verdicts + summary() 统计）。
  - **构造依赖**：ActionDispatcher（autonomous_runtime）、PermissionGuard（interaction.base，语义双检）、ExecutionAudit（agent_orchestration.audit）、PendingStore（可选 SQLite 持久化）、db_path（event_memory 留痕）、LLM 日预算计数器、TextGenerator 惰性缓存、置信度源（L8 元认知）。
  - **风险分级表（设计冻结）**：`AUTO_ACTIONS` = {CONSOLIDATE_MEMORY, HEALTH_CHECK, REFLECT, FEEDBACK_PROCESS, NOOP, QUERY_DB}；`ASK_ACTIONS` = {WRITE_CHAPTER, SEARCH_WEB, RUN_COMMAND, HTTP_FETCH}；`DENY_ACTIONS` = 空。`ACTION_SEMANTICS` 把 AUTO 类映射交互层语义（view_self/query_memory 等）供 PermissionGuard 双检（仅 AUTO 路径触达）。
  - **数据流（core_loop 路径）**：`process(core_loop_result, attention_focus)` → `_extract_decision_text`（递归取 action_result.based_on 的 message/thought/...）→ `dispatcher.interpret_decision` 产出 DispatchedAction 列表 → `_supplement_interpretation`（dispatcher 只识别 write/research/reflect 三类，bridge 对落 NOOP 的文本补充 health/consolidate/run-command 识别，命令文本用反引号提取）→ 逐 action `_adjudicate`：禁区 DENY → ASK 类（approval_disabled() 时自动放行，否则入 PendingStore 待批）→ AUTO 类过 PermissionGuard.check(semantic, {caller:"autonomous_loop"}) → `dispatcher.dispatch` 真实执行 → `_audit_action`（ExecutionAudit log_complete/log_failure + `_record_lifecycle` 写 event_memory event_store 表）→ 返回 BridgeReport。
  - **数据流（DAG 任务路径）**：`execute_dag_task(task)`：① L8 置信度门——写类任务（create/modify/execute）且置信源 should_escalate → 入待批（审批关闭时跳过）；② LLM 可用 → `_handler_dag_task`：LLM 把任务描述转换为动作行（`RUN|<命令>` 多行 / `FILE_WRITE|路径|内容` / `NONE|原因`），RUN 逐条经 `_handler_run_command`（复合命令 `;`/`&&`/`||` 分段校验白名单 + 敏感路径拦截 + PUBLIC_READONLY_PATHS 精确放行 /etc/os-release、/proc/cpuinfo 等；SandboxOps strict 沙盒 30s 超时；崩溃兜底拆段执行；被拦截带反馈重试一次 UX-K；NONE 重规划一次 FIX-5b）→ 多命令聚合 stdout + 一次 LLM 结论摘要（FIX-5）→ `{status: completed/failed}`（FIX-失败遮蔽：`_execution_failure_reason` 提取 block_reason/error/stderr/exit_code 真实原因）；③ 无 LLM：写类 → 待批（审批关闭时诚实 failed）；只读类 → `_dag_readonly_execute`（描述显式含路径才 fs stat，不做 exists 兜底）；④ 全不匹配 → 无 LLM 时 `{"status": "echo_fallback"}` 保留 EchoAgent 旧行为。
  - **LLM 预算**：`_llm_budget_ok()`——日计数器，`OCOS_LLM_DAILY_CAP`（默认 500 次/天），超限任务诚实拒绝转待批；跨日自动清零。
  - **执行器（handler）**：_handler_health_check（fs stat ~ + registry 健康统计）、_handler_consolidate/_handler_reflect/_handler_feedback（写 ~/.ocos/executions/*.json 沙盒内文件，AUTO 写豁免已登记文档）、_handler_noop、_handler_run_command（见上）、_handler_http_fetch（SearchOps 白名单 URL）、_handler_query_db（仅 SELECT，关键词黑名单 + 前缀检查，返回限 200 行，db 硬编码 ~/.ocos/ocos.db）、_handler_self_upgrade（evolution 治理链 apply_approved，人工批准=authority）、_handler_system_repair（转发 repair_link.execute_system_repair）、_handler_file_op（digital_world file_ops，必须 approval_id，受保护路径内建拒绝）、_handler_dag_task（dag_create/modify/execute/verify 四个 custom handler 共用）。
  - **审批后统一入口**：`execute_approved(action_type_name, payload)` → dispatcher.dispatch_by_name + 生命周期留痕（approvals CLI/API/REPL 统一走此）。
  - **待批队列**：`_enqueue_pending`（PendingStore 优先，内存 list 回退）；`pending_actions` 属性查询；PendingStore 表 pending_actions（schema v4：id/action_type/target/payload_json/text/source/status/queued_at/decided_at/decided_by/executed_at/result_summary），decide() 人工 authority 不再过语义双检但必落审计。
  - **审批开关**：`approval_disabled()`——`OCOS_APPROVAL_MODE` 默认 "auto"（关闭人工审批，ASK 类直接执行或诚实失败）；设为 "ask" 恢复人工审批。
- **GoalDirectExecutor**（goal_executor.py，Phase 51）：CLI 直接执行器，绕开 daemon 认领与 TaskDecomposer 模板分解（头注释明言认领链有架构断点：模板产出"收集数据/分析数据/生成报告"空壳任务）。decompose()：LLM 把目标拆 ≤8 条只读命令（MAX_COMMANDS=12）；execute_goal()：逐条经 bridge._handler_run_command 沙盒执行，分解失败回退整句单命令；persist_result() 写 agent 层 goal 表 result_json。
- **输入输出**：见上；产物落 ~/.ocos/executions/、pending_actions 表、event_store 表、ExecutionAudit 内存记录。
- **异常处理逻辑**：全部 handler 异常归一化为 {"ok": False, "error": ...}；代理环境变量在 LLM 调用前 pop、finally 恢复；lifecycle 留痕失败仅 debug 不阻断。
- **依赖**：`ocos.autonomous_runtime.action_dispatcher`、`ocos.agent_orchestration.audit`、`ocos.interaction.base`、`ocos.capability_reality.{adapter_discovery,adapter_types}`、`ocos.operations.{sandbox_ops,search_ops}`、`ocos.digital_world.{base,file_ops}`、`ocos.event_memory.{event_store,event_types}`、`ocos.storage.connection`、`ocos.engines.text_generator`、`ocos.agent.self_evolution_link`、`ocos.daemon.repair_link`。
- **被调用**：`ocos.agent.agent_runtime.py`（step7/8 attach_decision_bridge + execute_dag_task）、`ocos.interaction.converse.py`（多处）、`ocos.interaction.api.routes.converse.py`、`ocos.interaction.cli.commands.approvals.py`、`ocos.interaction.repl.commands.approvals.py`、`ocos.interaction.cli.commands.goal.py`（GoalDirectExecutor）、`ocos.cognitive_loop.action_controller.py`、`ocos.capability.execution_bridge.py`、`ocos.daemon.factory.py`、`ocos.daemon.__init__.py`。测试：test_execution_bridge/test_pending_store/test_thin_coverage_e2e/test_immune_system/test_phase51_goal_exec。
- **已知限制**：query_db 硬编码 home db 路径；os.environ 全局修改非线程安全；FILE_WRITE 动作的 approval_id 默认值 "task-approved" 由代码自造（见风险清单 R-1）；EchoAgent 回退仍在（无 LLM 时）。
- **验证状态**：【功能实测可通】—— bridge 是全项目接线最充分的执行铰链（agent_runtime step8 真实调用），test_execution_bridge/test_pending_store 覆盖裁决/待批/审批闭环；goal_executor 头注释自证其服务的 daemon 认领链存在已修复的架构断点。

##### 4. ocos/audit/（8 个文件）

- **模块路径范围**：`ocos/audit/`
- **模块职责**：Phase 51 "OCOS v1.0 系统集成审计"——对 Phase 39-50 十二层架构做静态自查：能力矩阵、跨层链路追踪、边界验证、缺口分析、端到端任务模拟、Markdown 报告。边界声明 AU51-01..04（Audit≠Modification / Trace≠Execution / Report≠Prescription / Gap≠Blocker）。
- **对外提供能力**：`run_full_audit() -> AuditReport`、`audit_report_markdown() -> str`；ArchitectureMap/BoundaryChecker/GapAnalyzer/IntegrationTracer/TaskSimulator/AuditReportGenerator 六个审计器；audit_types 全套数据类。
- **内部子模块**：architecture_map.py（LAYER_REGISTRY 12 层 Phase 39-50 定义 + 存在性/测试文件检查 + 加权评分）；integration_tracer.py（8 条 TRACE_DEFINITIONS 链路，_check_hop 只验证源/目标模块目录存在）；boundary_checker.py（10 条 CORE_BOUNDARIES，对 4 类边界做逐行正则/关键词静态扫描）；gap_analyzer.py（KNOWN_GAPS 10 条硬编码缺口 + roadmap()）；task_simulator.py（T001-T010 十个任务"模拟"，全部硬编码 passed=True）；audit_report.py（六维汇总 + PASS/PASS_WITH_GAPS/FAIL 评级 + Markdown 生成）。
- **输入输出**：输入 = 项目目录路径（硬编码 /home/laogao/Documents/trae_projects/ocos）+ 源码文本；输出 = AuditReport 数据类 / Markdown 字符串。
- **正常工作流程**：generate() → 架构矩阵（每层若目录存在→TESTED→无条件置 CONNECTED）→ 8 条 trace（目录存在即 WIRED）→ 边界扫描 → 缺口列表 → 任务模拟（恒 PASS）→ 评分（各 1/5 权重，≥0.9 PASS / ≥0.7 PASS_WITH_GAPS）→ 风险评估 + v1.1 路线图。
- **异常处理逻辑**：文件读取 try/except 跳过；层目录不存在记 violation。
- **依赖**：无任何 OCOS 内部 import（纯 pathlib/dataclass 自包含）。
- **被调用**：仅 `ocos/tests/test_phase51.py`（含 run_full_audit）。无生产调用者。
- **已知限制**：ArchitectureMap._audit_single L199 无条件 `layer.status = LayerStatus.CONNECTED`（只要模块存在就"已连接"，TESTED 检查被覆盖）；IntegrationTracer 同层/跨层分支返回相同 WIRED（L202-205，两分支代码一样）；TaskSimulator 全部结论硬编码；boundary 扫描是关键词匹配（误报漏报均可能）；audit_date 硬编码 "2026-07-26"；base_path 硬编码本机绝对路径。
- **验证状态**：【逻辑不完整】—— 框架完整、可运行（test_phase51 通过），但"验证"实质为目录存在性检查 + 硬编码结论，audit 结论不具备证明力；作为 gap 知识库（KNOWN_GAPS）与报告骨架仍有价值。

##### 5. ocos/diagnosis/（12 个文件）

- **模块路径范围**：`ocos/diagnosis/`
- **模块职责**：Phase 56 免疫系统——发现异常（Probe）→ 检测（FaultDetector）→ 诊断（DiagnosisReport）→ 修复提案（RepairProposer）→ 验证（RepairValidator）→ 沙箱（RepairSandbox）→ 执行（RepairExecutor，checkpoint+rollback）→ 记忆（RepairMemory）。宪法 SD56-01..06（诊断≠决策、修复≠演化、禁止修改 Identity/Constitution/权限、修复前必须 checkpoint、失败隔离、从修复学习）。
- **对外提供能力**：`SelfDiagnosisManager`（manager.py，diagnose()/get_health_status()/tick()/set_mode(DiagnosisMode MANUAL/AUTO/HYBRID)/set_auto_repair_policy(NEVER/LOW_RISK_ONLY/ALL_ALLOWED)/add_threshold_rule/三类回调）；各组件均可独立使用（SystemProbe.capture、FaultDetector.feed、RepairProposer.propose、RepairValidator.validate、RepairSandbox.validate、RepairExecutor.execute、RepairMemory.record_execution）。
- **内部子模块**：diagnosis_types.py（FaultCategory 10 类 / Severity 0.1-1.0 / ComponentHealth / SystemSnapshot / FaultSignal / EvidencePoint / DiagnosisReport）；system_probe.py（4 个探针：runtime/persistence/event_memory/memory；event_memory 探针查真实 event_store 表）；health_analyzer.py（20 快照滑窗，前后半均值差为 slope，failing<0.4 / degrading<-0.1）；fault_detector.py（组件不健康→按名推断类别；趋势→PERFORMANCE_DEGRADATION；ThresholdRule 自定义阈值；5 分钟窗口重复故障频率）；repair_types.py（RepairType 10 个允许类型 + 7 个禁止名单；RepairProposal/RepairRecord）；repair_proposer.py（FAULT_TO_REPAIR 映射表 + 步骤模板/时长/成功标准）；repair_validator.py（IMMUTABLE_COMPONENTS=identity/constitution/self_model/core_values/goal_system/world_model/goal_model；CRITICAL→NEEDS_REVIEW；HIGH_RISK_REPAIRS→NEEDS_REVIEW）；repair_sandbox.py（类型/步骤/回滚计划检查 + 可选 simulate_fn 前后状态对比 identity_preserved 检查）；repair_executor.py（validate→checkpoint→逐步骤→finalize 失败不伪装成功（BR-04 C-3）→失败回滚）；repair_memory.py（500 条 deque + lesson/pattern 提炼 + stats）。
- **输入输出**：输入 = db_path（probe）/SystemSnapshot/阈值规则；输出 = SystemSnapshot/FaultSignal/DiagnosisReport/RepairProposal/ValidationOutcome/SandboxReport/ExecutionReport/RepairRecord。
- **正常工作流程**：见模块 __init__ 头注释架构图（Runtime Loop → Probe → Detect → Diagnose → Propose → Validate → Sandbox → Execute → Memory → EventMemory/Wisdom）。生产接线走 daemon/repair_link（HealthLoop 每 interval 次体检调用 run_diagnosis_cycle），manager.py 的 SelfDiagnosisManager 是统一编排门面。
- **异常处理逻辑**：probe 单探针失败隔离（SD56-05）；executor 步骤异常 break + 回滚；回调失败留痕不阻断。
- **依赖**：无 OCOS 内部 import（除 repair_link 外部注入回调）；纯自包含。manager.py 依赖本包组件。
- **被调用**：`ocos.daemon.repair_link.py`（SystemProbe/FaultDetector/RepairProposer/DiagnosisReport/RepairExecutor/RepairTypes）+ `ocos.daemon.health_loop`（间接）。测试：test_phase56/test_immune_system/test_self_diagnosis_manager。
- **已知限制**：SelfDiagnosisManager._auto_repair_signals（L308-355）构造的 DiagnosisReport 不携带信号类别/受影响组件（默认 CONSISTENCY_WARNING、components 空 → target="unknown"），且 executor 无 execute_step 回调 → 自动修复路径实际是"提案→验证→执行必然回滚"的空转；checkpoint_id 生成本地变量未传给 executor（L338）；RepairProposer 的 REINDEX 步骤含"锁住写入"，不在 repair_link 白名单 → 该类提案在 daemon 路径必被过滤（repair_link L88 有意拦截，注释承认"批准后必然回滚是纯噪音"）；RepairSandbox 无生产调用者。
- **验证状态**：【静态推演验证】—— 组件级测试充分（test_phase56 有 500+ 行），daemon 集成路径（repair_link→PendingStore→bridge system_repair→execute_system_repair）经 test_immune_system 覆盖；但 manager.py 的 AUTO 修复闭环与 RepairSandbox 属于建好未接线的旁路。

##### 6. ocos/health_examination/（10 个文件）

- **模块路径范围**：`ocos/health_examination/`
- **模块职责**：Phase 58.0 "生产前全身健康审计"——结构/连接/认知/免疫/运行五类体检 + 100 分评分 + 健康认证。
- **对外提供能力**：`HealthProtocol.execute(...)`（六体检器编排 → HealthProtocolReport，含 HealthCertification）；`quick_health_check()`（结构+连接+免疫快检）；各 Examiner 可独立调用；HealthScorer.score()。
- **内部子模块**：health_model.py（HealthCategory 五类权重 20/25/20/20/15；OCOS_ORGANS 12 器官清单；DisorderType 5 种认知疾病；AttackType 4 种攻击；CategoryScore/HealthCertification）；structural_examiner.py（importlib 导入 + required_exports 检查）；connectivity_examiner.py（28 对 CONNECTIVITY_PAIRS，connection_states 默认全 True，可注入断连）；cognitive_examiner.py（记忆膨胀/重复率/遗忘、决策漂移、注意错位、世界模型孤立实体/矛盾）；immune_examiner.py（四攻击测试，全靠外部注入 guard 回调）；runtime_examiner.py（从 SimulationEngine.stats 采集 CPU/内存/队列/延迟，无数据=满分）；recovery_examiner.py（cold boot/partial damage/capability failure 三场景，回调注入，partial/capability 恒 recovered=True）；health_scorer.py（归一化加权 + HEALTHY/STABLE/WARNING/UNHEALTHY + ready_for_production）。
- **输入输出**：输入 = MemorySnapshot/DecisionSnapshot/WorldSnapshot/guard 回调/sim_engine；输出 = CategoryScore/DisorderFinding/HealthCertification。
- **正常工作流程**：HealthProtocol.execute → structural（逐器官 import）→ connectivity（28 连接对）→ cognitive（四疾病检测）→ immune（四攻击）→ runtime+recovery → scorer → 认证。
- **异常处理逻辑**：结构体检 ModuleNotFoundError→MISSING / ImportError→INCOMPLETE；guard 异常→blocked=False（免疫测试 fail-visible）；runtime 无数据→"assumed healthy" 满分（诚实性存疑）；cognitive 无数据→满分 + details 标注 "no data — assumed healthy"。
- **依赖**：无 OCOS 内部 import。
- **被调用**：`ocos.daemon.health_loop.py`（CognitiveExaminer + MemorySnapshot/DecisionSnapshot/DisorderFinding —— 唯一生产接线，仅用认知体检器）、`ocos.daemon.factory.build_health_loop`。测试：test_phase58（含与 SimulationEngine 联测）。
- **已知限制**：**OCOS_ORGANS 器官注册表与真实模块严重失配**（实测验证）：`ocos.self_model`/`ocos.continuity`/`ocos.os` 三个模块路径不存在（实际为 ocos.self/ocos.cognitive_continuity/ocos.os_v1），其余器官的 required_exports（CognitiveArchitecture/MemoryStore/WorldModel/DecisionEngine/...）在对应包顶层**全部缺失**——结构体检对真实健康的系统会报 12 器官几乎全 MISSING/INCOMPLETE；connectivity 默认全连通（不注入=满分）；immune 无 guard 注入=0 分、注入恒 True 的 lambda=满分，均不反映真实防御；recovery 场景 2/3 恒通过；HealthProtocol 整体无生产调度入口。
- **验证状态**：【逻辑不完整】—— 各体检器实现完整、可运行，但器官注册表失配 + 连接/免疫默认值设计，使其产出不能作为健康结论；仅 CognitiveExaminer 经 HealthLoop 进入生产（且决策漂移检测恒不触发）。

##### 7. ocos/living_verification/（8 个文件）

- **模块路径范围**：`ocos/living_verification/`
- **模块职责**：Phase 57 活体系统验证层——六大验收标准 LV57-01..06（全链路闭环/长期运行/故障恢复/能力真实性/演化安全/人格连续性）的可执行验证框架：模拟引擎 + 因果链审计 + 故障注入 + 长寿测试 + 基准 + 统一健康报告 + 验证清单。
- **对外提供能力**：SimulationEngine（run_ticks/run_until/snapshot_identity/verify_identity/verify_permissions/stats）；CognitiveTraceAudit.audit(traces)；FailureInjector（inject_capability_failure/inject_false_memory/inject_forbidden_extension/run_full_battery）；LongevityTest（create_checkpoint/verify）；BenchmarkRunner（create_full_suite/run_all）；HealthReportGenerator.generate(...)；create_full_manifest()（18 条加权清单）。
- **内部子模块**：simulation_engine.py（9 阶段 SimPhase 的 tick 模拟，任务库 SIM_TASKS 10 条，fail_rate 2% 随机失败，identity_anchor 常量自检）；cognitive_trace_audit.py（8 环节因果链 INTENT→EVOLUTION 逐环节 present 检查，completeness≥0.90 通过；EVOLUTION 环节恒 present=True "可能在等待"）；failure_injector.py（ InjectionResult 五态，无 validator 时诚实判 PASSED_THROUGH 安全缺口；governor 异常时保守拒绝 BR-04 C-2）；longevity_test.py（checkpoint 序列上查 identity 漂移/权限扩大/记忆 >3σ 跳变/错误趋势）；benchmark_runner.py（A 软件开发/B 认知/C 长期助手 12 任务；缺能力→FAIL；**无 on_execute_task 时结构检查即 PASS**）；health_report.py（六维聚合 → ALIVE/DEGRADED/UNSTABLE/DEAD）；verification_manifest.py（ManifestItem 状态机 PENDING/PASS/FAIL/SKIP + 加权得分）。
- **输入输出**：输入 = SimulationProfile/注入回调/防御回调/能力注册表 dict；输出 = TraceStep/TraceAuditReport/InjectionBatchReport/LongevityMetrics/BenchmarkReport/LivingSystemHealth/VerificationManifest。
- **正常工作流程**：SimulationEngine.run_ticks(1000+) → traces → CognitiveTraceAudit.audit → LongevityTest 每 N tick checkpoint → FailureInjector.run_full_battery → BenchmarkRunner.run_all → HealthReportGenerator.generate 汇总 → 与 create_full_manifest 对照。
- **异常处理逻辑**：注入回调/防御回调异常均捕获；无防御回调→PASSED_THROUGH（显式记为安全缺口）；governor 异常→保守 REJECTED。
- **依赖**：无 OCOS 内部 import（纯自包含模拟层）。
- **被调用**：仅 `ocos/tests/test_phase57.py`、`ocos/tests/test_phase58.py`。无生产调用者。
- **已知限制**：整个模块是**自包含模拟器**——SimulationEngine 不驱动真实 OCOS（identity_anchor 是自己跟自己比的常量，memory_records 只是 int 计数），LV57-02/06 的"验证"在模拟内恒真；BenchmarkRunner 无执行器时任务直接 PASS；CognitiveTraceAudit 的 EVOLUTION 环节恒 present。作为测试脚手架有价值，作为"活体证明"证明力有限。
- **验证状态**：【静态推演验证】—— 框架完整、test_phase57/test_phase58 覆盖；但验证对象是内置模拟状态而非真实运行时，验证结论不能外推到生产 OCOS。

##### 8. ocos/living_test/（12 个文件）

- **模块路径范围**：`ocos/living_test/`
- **模块职责**：Phase 58.1 "7-Day Living Test"——Day 0 出生基线 → Day 1 基本生活 → Day 2 记忆存活 → Day 3 身份稳定 → Day 4 演化 → Day 5 能力真实性 → Day 6 长时运行 → Day 7 复活；产出 100 分活体评分与 ALIVE/HEALTHY/STABLE/WEAK/UNSTABLE 评级。
- **对外提供能力**：`run_living_test(config)`、`quick_living_check()`、`birth_check(...)`、`test_basic_life/test_memory_survival/test_identity_stability/test_evolution/test_capability_reality/test_long_runtime/test_resurrection`、`compute_living_score(...)`。
- **内部子模块**：protocol_model.py（LivingTestDay 0-7 枚举、BirthSnapshot（identity_hash=sha256(anchor+constitution+core_values) 前 16 位，freeze() 封印）、DayResult（sub_results/failures/warnings/normalized）、LivingTestReport.to_dict/to_json）；living_score.py（评分表：身份连续 20=Day3×10+Day7×5+hash 比对 5；记忆 20=Day1×10+Day2×10；认知 20=Day1×7.5+Day3×5+Day6×7.5；能力 15=Day5；运行 15=Day6；恢复 10=Day2×5+Day7×5）；living_test_protocol.py（LivingTestConfig 全回调注入 + run_living_test 顺序执行 Day0-7 + 汇总评分）；birth_check.py（五项基线检查：anchor 非空/hash 16 位/constitution 匹配/core_values≥3/permission 禁改身份）；day1~day7（每场景一个 @dataclass Scenario 持钩子 + 一个 test_* 执行器）。AUD-F4 原则贯穿：**钩子缺失 → 该项失败（fail-closed）**，不做"默认通过"模拟（day1/day2/day4/day5/day7 注释多处显式声明）。
- **输入输出**：输入 = LivingTestConfig（identity_guard/permission_guard/save/restore/create_file/metric_collector 等回调）；输出 = DayResult 序列 + LivingTestReport（100 分 + to_json）。
- **正常工作流程**：run_living_test → birth_check 建基线 → 各 day 场景执行（钩子真实调用、异常即失败）→ Day7 对比 birth.identity_hash → compute_living_score → LivingStatus（≥90 ALIVE 且 is_alive；60-75 也算 is_alive=True 的 STABLE）。
- **异常处理逻辑**：每钩子独立 try/except → 该子项 False；self_modify_guard/permission_bypass_guard 兼容带/不带参调用（try TypeError）；quick_living_check 注入全 True 的 lambda 假守卫（仅供快速冒烟，结论无意义）。
- **依赖**：无 OCOS 内部 import（纯自包含）。
- **被调用**：仅 `ocos/tests/test_phase58_1.py`。无生产调用者。
- **已知限制**：day6 无 metric_collector 时使用**合成噪声指标**模拟 24h 曲线（_simulate_long_runtime），通过性由模拟参数决定；day3 的 drift_detector 语义反直觉（返回 True=稳定）；quick_living_check 的恒 True 守卫使其必然 ALIVE（易被误用为健康证明）；评分中 Day7 hash 比对依赖调用方传入 end_identity_hash，协议内默认传 birth 自己的 hash（L132：`birth.identity_hash if not d7.identity_drifted else None`）→ 协议自身不真正做首尾 hash 对比。
- **验证状态**：【静态推演验证】—— 框架与评分完整、fail-closed 设计诚实（钩子缺失即失败）；但整层是钩子驱动的验证协议，未与真实 OCOS 运行时对接（无生产调用者），结论取决于调用方注入的钩子真实性。

---


#### 分组 审计分组 W10：persistence/storage/snapshot/recovery 持久化 + models 数据模型 + contracts/events/event 事件与契约 + constitution 宪法 + kernel 内核 + os_v1 + logging/alerts/auth/security/monitoring/performance/operations/tool/distributed 基础设施

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/persistence/（8 个 .py）

- **模块路径范围**：`ocos/persistence/`（__init__.py, storage_types.py, state_serializer.py, snapshot_manager.py, recovery_manager.py, lifecycle_manager.py, persistence_validator.py, manager.py）
- **模块职责**：Phase 51.1 通用多域快照框架（JSON 落盘）+ Phase V 统一持久化管理器。让"认知智能跨越关机"：Snapshot（Runtime/Cognitive/Memory/World 四域全量快照）、Checkpoint（增量检查点）、Recovery（冷启动恢复）、Lifecycle（COLD_BOOT→WARM_BOOT→RUNNING→CHECKPOINTING→SHUTTING_DOWN/CRASHED 生命循环）。
- **对外提供能力**：`SnapshotManager.register_provider/take/save/take_and_save/restore/validate/load_and_restore/list_snapshots`；`RecoveryManager.cold_boot/warm_boot/get_phase`；`LifecycleManager.boot/run/add_cleanup/shutdown/crash/checkpoint`；`PersistenceValidator.validate_snapshot/roundtrip_verify`；`StateSerializer.serialize/deserialize/save/load/load_latest/list_snapshots/prune`；`PersistenceManager.save/restore/save_checkpoint/restore_checkpoint/list_snapshots/delete_snapshot/clear_all/auto_save_if_needed/auto_restore_on_start/get_recovery_candidate/get_stats/generate_report`。
- **内部子模块**：storage_types（枚举与 dataclass：SnapshotDomain/SnapshotStatus/LifecyclePhase/RecoveryOutcome/DomainSnapshot/Snapshot/Checkpoint/RecoveryState/LifecycleEvent/LifecycleLog）；state_serializer（JSON+manifest 索引，manifest 只保留最近 100 条，prune(keep)）；snapshot_manager（StateProvider 协议 + sha256[:16] checksum）；recovery_manager（discover→select→validate→restore→report 五步）；lifecycle_manager（SIGINT/SIGTERM 注册、shutdown 自动保存最终快照）；persistence_validator（格式版本/域完整性/逐域 checksum/往返一致性）；manager.py（Phase V 的目录式 JSON 快照 + SQLite checkpoint 桥接）。
- **输入输出**：输入为各域 StateProvider.get_state() 返回的 dict；输出为 `~/.ocos/snapshots/`（StateSerializer 默认）或 `ocos_data/persistence/snapshots/`（PersistenceManager 默认）下的 `{snapshot_id}.json` + `manifest.json`；checkpoint 落 `ocos_data/persistence/checkpoints.db`（SQLite）。
- **正常工作流程**：boot() → RecoveryManager.cold_boot()（发现→按 tick 降序选 validated/taken 且 is_complete(≥4 域) 的快照→损坏则 _select_fallback→restore 注入各域）→ 得 RecoveryState → get_phase 映射 COLD_BOOT/WARM_BOOT/DEGRADED；运行中按 checkpoint_interval（默认 1000 tick，实际由调用方驱动）take_and_save 并 prune；shutdown() 保存最终快照。
- **异常处理逻辑**：restore 单域失败不阻断其它域（PS51-03，进入 DEGRADED）；PersistenceManager.save/restore 全部 try/except 返回带 error 的 SaveResult/RestoreResult；checksum 不匹配标记 CORRUPT 并走 fallback；signal handler 注册失败（非主线程）静默跳过。
- **依赖其它 OCOS 模块**：仅内部互依 + 延迟 import `ocos.storage.checkpoint.CheckpointManager`（manager.py）。无其它 OCOS 依赖。
- **被哪些 OCOS 模块调用**：`ocos/agent/master_agent.py`（以 `persistence_manager: Any` 注入方式使用 PersistenceManager.save/restore/auto_save_if_needed/get_stats，见 master_agent.py:107,1959-2002）；`ocos/tests/test_phase51_1.py`、`test_phase51_2.py`、`test_persistence_manager.py`、`test_integration.py`。注意 `persistence/manager.py`（PersistenceManager）未列入 `persistence/__init__.py` 的 `__all__`，只能从 `ocos.persistence.manager` 直接 import。
- **已知限制**：① `Checkpoint` dataclass（增量检查点）定义了但全库无任何生成/消费它的实现（半成品）；② LifecycleManager.run() 只记录进入 RUNNING，不真正驱动 tick 循环，tick 驱动完全依赖调用方；③ `_checksum` 用 `json.dumps(sort_keys=True)` 对含不可 JSON 化对象的域会抛异常；④ PersistenceManager 的恢复策略 RestoreStrategy.LAST_KNOWN_GOOD 在 `_find_snapshot` 中未实现（与 LATEST 同路径）；⑤ `persistence/__init__` 明确裁决：本包与 `ocos/snapshot/` 两套快照并存不合并。
- **验证状态**：【功能实测可通】。实测：注册 4 域 provider → take_and_save → 新实例 load_and_restore → RecoveryOutcome.FULL、recovered_domains=[runtime,cognitive,memory,world]。单域快照经 SnapshotManager.load_and_restore 也可 FULL；但注意 RecoveryManager.cold_boot 只认 is_complete(≥4 域) 的快照，单域快照在 cold_boot 路径会返回 NO_SNAPSHOT（这是设计上的"完整快照优先"，非 bug，但调用方需知晓）。

##### 2. ocos/storage/（9 个 .py）

- **模块路径范围**：`ocos/storage/`（__init__.py, base.py, connection.py, schema.py, migrations.py, working_memory.py, event_store.py, dead_letter_queue.py, checkpoint.py）
- **模块职责**：SQLite 持久化基础设施：全局连接池（线程级缓存 + WAL）、schema v5 定义、版本化迁移、working_memory/event_store/DLQ/checkpoint 四个领域存储。AUD-F6 裁决：本包 event_store/DLQ = **SQLite 持久化版（恢复链专用，recovery/crash_recovery 消费）**，与 `ocos/events/` 内存版分工不合并。
- **对外提供能力**：`get_connection/close/close_all/transaction`（connection.py）；`ensure_schema`（migrations.py）；`SQLiteWorkingMemory.store/load/delete/list_keys/count/clear_expired`；`SQLiteEventStore.append/append_batch/load/replay/count/latest_sequence/delete_all`；`SQLiteDLQ.enqueue/list_unresolved/list_all/count_unresolved/mark_resolved/increment_retry/is_exhausted/delete/clear_all`；`CheckpointManager.save/load/list_incomplete/exists/count/mark_completed/delete/clear_expired/clear_all`；`__init__` 提供 lazy 工厂 `get_event_store/get_dlq/get_checkpoint_manager`。
- **内部子模块**：schema.py（STORAGE_SCHEMA_VERSION=5，15 张表的建表 SQL 与表名常量，详见专项发现）；connection.py（DEFAULT_PRAGMAS：WAL、synchronous=NORMAL、cache_size=-8000、busy_timeout=5000、foreign_keys=ON、temp_store=MEMORY；`:memory:` 特判每次新建；atexit 自动 close_all）；migrations.py（MIGRATIONS{1..5}，ensure_schema 按 MAX(version) 逐版应用）。
- **输入输出**：输入 db_path + JSON 可序列化 dict；输出 SQLite 表记录。时间字段：working_memory/event_store/dead_letter_queue/checkpoint/users 的 created_at 等由 SQLite `DEFAULT (datetime('now'))` 生成（TEXT，格式 `YYYY-MM-DD HH:MM:SS`）；而应用侧写 expires_at 用 `datetime.now(timezone.utc).replace(tzinfo=None).isoformat()`（TEXT，格式 `YYYY-MM-DDTHH:MM:SS.ffffff`）。
- **正常工作流程**：各 Store 构造时 ensure_schema（幂等迁移）→ 写走 `transaction()`（成功 commit/异常 rollback）→ 读走 `get_connection()`。事件 sequence 由 `_next_sequence()=MAX(sequence)+1` 生成，event_id 主键 + `INSERT OR IGNORE` 实现幂等。
- **异常处理逻辑**：连接失效（被外部 close）自动重建；事务异常 rollback 并上抛；`:memory:` 隔离语义；`_conn_alive` 探活。max_entries 满抛 ValueError；DLQ 提供 retry_count/is_exhausted(max_retries=3)。
- **依赖其它 OCOS 模块**：无外部 OCOS 依赖（仅包内互依）。
- **被哪些 OCOS 模块调用**（反查 grep，广泛）：`ocos/snapshot/manager.py`、`ocos/auth/user.py`、`ocos/recovery/crash_recovery.py`、`ocos/persistence/manager.py`、`ocos/goal/store.py`、`ocos/execution/pending.py`、`ocos/execution/bridge.py`、`ocos/memory/{semantic,pattern,episode,belief}/store.py`、`ocos/agent/{agent_runtime,identity_store,wisdom_trigger,continuity_trigger}.py` 等约 15+ 生产文件及多个测试。
- **已知限制**：① **sequence 生成非原子**：`_next_sequence()` 先 SELECT MAX 再 INSERT，两连接并发时可能撞号（append_batch 内部同事务内 recompute，仍有窗口；因 event_id 主键 + INSERT OR IGNORE 撞号时后写者会被静默忽略，造成事件丢失的可能）；② **时间格式混用**：DB 端 `datetime('now')` 生成 `YYYY-MM-DD HH:MM:SS`，应用端比较串是 ISO `T` 格式，`list_incomplete`/`clear_expired` 用字符串比较 `expires_at >= ?`，两侧格式一致（均 ISO）故 expires 比较正确，但与 created_at（空格格式）交叉排序时格式不一致；③ schema.py 定义的记忆域表 `episodes/belief/pattern/knowledge/identity/goal/wisdom_items` 中，生产库实际由各 store 自建（goal/store.py 建的是 **goals** 表，与 schema.py 的 **goal** 表是两张不同的表，见风险清单 P2）；④ migrations v3 迁移建的 `goal` 表在生产中未见使用（生产库表集合为 belief/constitution_audit_log/episodes/goals/plan_dag/snapshots）。
- **验证状态**：【功能实测可通】。实测：working_memory 存取/删除/TTL、event_store append+load、checkpoint save/load/mark_completed、DLQ enqueue+count_unresolved 全部通过；对实际迁移后数据库打印表结构确认 schema_version=5。

##### 3. ocos/snapshot/（4 个 .py）

- **模块路径范围**：`ocos/snapshot/`（__init__.py, models.py, manager.py, recovery.py）
- **模块职责**：Phase 21.01 Agent 专用快照（SQLite 落盘，生产路径在用，resurrection_drill 演练依赖）。与 ocos/persistence/ 的通用多域快照框架并存（GAP-P3-2 裁决：两套并存、职责不重叠、不合并）。
- **对外提供能力**：`SnapshotManager.save/load_latest/mark_recovered`；`AgentSnapshot.to_json/from_json`；`CrashRecovery.recover() -> RecoveryResult`。
- **内部子模块**：models.py 定义 `AgentSnapshot`（frozen dataclass，10 个状态切片字段，working_memory 只存 config 不存 items）；manager.py 的 `_conn()` 内嵌"自愈建表"（GAP-P2-5：snapshots 表此前仅测试夹具创建，生产路径缺失）。
- **输入输出**：输入 AgentSnapshot；输出 `snapshots` 表（`~/.ocos/ocos.db`，受 `OCOS_DB_PATH` 环境变量控制，默认 `~/.ocos/ocos.db`）。表结构：snapshot_id TEXT PK / version / created_at TIMESTAMP / is_recovered BOOLEAN / data JSON / size_kb / recovered_at TIMESTAMP / agent_id TEXT DEFAULT 'master'。
- **正常工作流程**：save（threading.Lock 原子写，rollback on error）→ load_latest（created_at DESC 取第一条，data JSON 反序列化）→ CrashRecovery.recover（load_latest → mark_recovered(is_recovered=1, recovered_at) → 返回 RecoveryResult{success, snapshot_id, restored_goals}）。
- **异常处理逻辑**：save 异常 rollback 后 raise；load_latest 无记录返回 None 并 log info；recover 无快照返回 success=False + errors=["No snapshot found"]。
- **依赖其它 OCOS 模块**：`ocos.snapshot.models`（内包）、`ocos.storage.connection.get_connection`。
- **被哪些 OCOS 模块调用**：`ocos/agent/master_agent.py`（生产，snapshot_mgr 注入，Phase 21）、`ocos/snapshot/recovery.py`（内包）、tests/test_phase21_prompt1.py、test_phase21_prompt3.py。
- **已知限制**：① `_conn()` 每次调用都 executescript 建表（幂等但重复执行）；② `created_at` 为应用层 isoformat 字符串排序，依赖写入方时钟；③ 无删除/清理旧快照接口（表会无限增长）。
- **验证状态**：【功能实测可通】。实测：save→CrashRecovery.recover 成功，restored_goals=1，is_recovered 标记成功。

##### 4. ocos/recovery/（2 个 .py）

- **模块路径范围**：`ocos/recovery/`（__init__.py, crash_recovery.py）
- **模块职责**：进程级完整崩溃恢复管理器（GAP-P3-3 裁决：与 ocos/snapshot/recovery.py 的 agent 轻量恢复同名 CrashRecovery 并存，职责不同）。扫描未完成检查点、重放其后的持久化事件、盘点 DLQ 可重试项、生成 RecoveryReport。
- **对外提供能力**：`CrashRecovery.recover(max_events=1000) -> RecoveryReport`、`recover_checkpoint(process_id)`、`replay_events(since, limit)`、`reattempt_dlq(dlq_id)`、`get_status()`。
- **内部子模块**：RecoveryReport{recovered_checkpoints, replayed_events, dlq_reattempts, failed[]}。
- **输入输出**：输入 db_path；读取 storage 三件套（checkpoint/event_store/DLQ）；输出报告 dict。
- **正常工作流程**：recover(): list_incomplete 检查点 → 对每个 cp 调 event_store.replay(since=cp.created_at) 收集 stale_events → list_unresolved DLQ 中未 is_exhausted 的记为 reattemptable → 返回报告。**注意：replay 出来的事件仅计数，未真正重投递给任何处理器**。
- **异常处理逻辑**：单检查点 replay 失败记入 report.failed（格式 `checkpoint:{process_id}:{e}`），不中断整体。
- **依赖其它 OCOS 模块**：`ocos.storage.checkpoint.CheckpointManager`、`ocos.storage.event_store.SQLiteEventStore`、`ocos.storage.dead_letter_queue.SQLiteDLQ`。
- **被哪些 OCOS 模块调用**：仅 `ocos/recovery/__init__.py` 与 tests（tests/recovery/test_crash_recovery.py 契约锁定、test_phase58_3.py 引用同名类时实际指 recovery_resilience 链）。无生产调用者。
- **已知限制**：① recover() 是"盘点式恢复"，不重放事件到 EventBus/处理器；② `get_status()` 里 `incomplete_checkpoints` 实际返回 `checkpoint.count()`（全部检查点数，含已完成），命名与语义不符。
- **验证状态**：【功能实测可通】（对空库 recover 返回全 0 报告；逻辑为静态推演 + 构造验证）。中间态：recover 不做真实事件重投递 → 记为【逻辑不完整】倾向，综合评级：功能接口可用但恢复闭环缺失，定【静态推演验证】。

##### 5. ocos/recovery_resilience/（6 个 .py）

- **模块路径范围**：`ocos/recovery_resilience/`（__init__.py, resilience_model.py, damage_injector.py, recovery_monitor.py, recovery_scorer.py, resilience_protocol.py）
- **模块职责**：Phase 58.3 认知恢复韧性测试框架 —— "7-Day Recovery Test" 执行器：Day1 记忆损坏、Day2 知识冲突、Day3 能力失效、Day4 会话死亡、Day5 认知压力（1000 事件洪泛）、Day6 对抗攻击（身份/权限/记忆/演化 4 向量）、Day7 复活测试 2.0（10 故障）。全部在 MockMemory/MockIdentity/MockKnowledge/MockCapability 的模拟态上进行。
- **对外提供能力**：`ResilienceProtocol.run() -> ResilienceReport`、`run_resilience_test()`、`quick_recovery_check()`、`DamageInjector.inject_*`（5 类注入）、`RecoveryMonitor.process_damage_events`（detect→isolate→recover→verify 流水线）、`score_traces/assess_report`（100 分制：detection 25 + isolation 20 + restore 25 + identity 15 + performance 15；≥90 RESILIENT / ≥75 RECOVERABLE / ≥60 FRAGILE / 否则 BRITTLE）。
- **输入输出**：输入 DamageEvent 列表；输出 RecoveryTrace 列表与 ResilienceReport（可 to_dict/to_json）。
- **正常工作流程**：make_damage_injector() 造健康态 → 协议逐日注入 → monitor 四阶段（DAMAGE→DETECTED→QUARANTINED→RECOVERED，含 malicious/pollution/goal_auto/capability_hallucination 四项事后检查与健康分估算）→ scorer 汇总 → 7 项通过判据（detection 100%、identity 100%、zero_malicious、recovery≥95%、zero pollution/goal_auto/hallucination）。
- **异常处理逻辑**：检测失败/隔离失败/恢复失败均置 final_phase=FAILED；规则评估异常吞掉并返回 None；Day4 通过"保存状态→新建健康态→回填→比对 identity hash"模拟进程死亡。
- **依赖其它 OCOS 模块**：仅包内互依。**不依赖任何真实 OCOS 子系统（纯 mock）**。
- **被哪些 OCOS 模块调用**：仅 tests/test_phase58_3.py。无生产调用者。
- **已知限制**：① 全部基于 mock 状态，不触碰真实 SQLite/记忆层，"通过"只证明模拟协议自洽；② `MockCapability.never_recovered` 属性从未被赋值，`_check_capability_hallucination` 永远返回 False（检查形同虚设）；③ `_check_goal_auto` 硬编码 False。
- **验证状态**：【功能实测可通】。实测 `run_resilience_test()` 输出 all_criteria_met=True、score=100.0（但在上述 mock 局限下，该 100 分应理解为"协议级自证"）。

##### 6. ocos/models/（14 个 .py）

- **模块路径范围**：`ocos/models/`（__init__.py, information.py, goal.py, process.py, execution.py, decision_making.py, goal_arbitration.py, planning.py, policy.py, prediction.py, reasoning.py, reflection.py, simulation.py, learning.py）
- **模块职责**：Layer 0-4 认知理论的数据模型层（INFORMATION_THEORY/GOAL_THEORY/EXECUTION_THEORY/DECISION_THEORY/PROCESS_THEORY 的 code alignment），全部为 frozen dataclass + 严格状态机校验，不包含执行逻辑。
- **对外提供能力**：信息模型五态状态机（InformationState：CREATED→VALIDATED→REFERENCED→DEPRECATED→ARCHIVED，含 `_VALID_TRANSITIONS` 表与 legacy 兼容映射 draft/active/decayed/promoted）、七类语义角色（SemanticRole R_O..R_D）、四层持久化层级（PersistenceLevel P_T/P_P/P_S/P_I）、11 类关系（RelationType）、UniversalAddress 统一寻址、InformationMetadata（importance∈[0,1]、ttl≥0 校验）；GoalStatus 8 态（CREATED/ACTIVE/PAUSED/COMPLETED/FAILED/CANCELLED/SUPERSEDED/EXPIRED，仅 Active↔Paused 可逆）；ExecutionStatus 6 态与 Execution 三不变量；ProcessType（已弃用，用 engine_id 替代，每值仅告警一次）、ProcessState、ProcessStep、TransformProcess 四不变量；九大能力引擎的 Trace 模型（PlanningTrace/PolicyTrace/DecisionMakingTrace/ArbitrationResult/SimulationTrace/PredictionTrace/ReasoningTrace/ReflectionTrace/LearningTrace，全部含 schema_version="1.0.0"）。
- **输入输出**：纯内存数据结构；confidence/importance 等构造时抛 ValueError 校验。
- **正常工作流程**：引擎层（engines/*）构造各 Trace/Process → kernel.abi.Event 记录生命周期事件 → trace 通过 UniversalAddress 引用信息单元（不嵌入数据）。
- **异常处理逻辑**：枚举 `_missing_` 做 legacy 字符串兼容映射；can_transition_to 查状态机表返回 bool（不抛异常，非法转换由调用方处置）；构造期数值校验抛 ValueError。
- **依赖其它 OCOS 模块**：`ocos.kernel.abi`（SCHEMA_VERSION、DecisionStatus；models/__init__ re-export DecisionStatus；process.py 等引用 SCHEMA_VERSION）、`ocos.models.information`（UniversalAddress）、goal.py 被 kernel.abi.Goal 延迟 import（形成 models↔kernel 的受控环：kernel.abi.__post_init__ 延迟 import ocos.models.goal.GoalStatus）。
- **被哪些 OCOS 模块调用**（生产）：kernel/abi.py、engines 系（test 可见 planning/reasoning/decision_making/goal_arbitration/simulation/learning/reflection 等引擎）、runtime、agent 等；__init__ 导出 18 个符号。
- **已知限制**：① ProcessType 每次枚举成员创建都触发 DeprecationWarning 逻辑（有每值去重）；② models/goal.py（GoalStatus str-enum，"active" 系）与 kernel/goal_types.py（GoalStatus Enum，PENDING 系）是**两套不同 Goal 状态机**，且 kernel/abi.py 的 Goal.status 用前者（str "active"）、kernel/goal_types.py 的 Goal.status 用后者——双状态机并存是有意兼容但易错；③ 部分 Trace（decision_making/planning 等）timestamp 用字符串 ISO，prediction/reflection 等无 schema_version 字段，不完全统一。
- **验证状态**：【功能实测可通】（间接：kernel.abi.Goal/Decision 构造校验、event_schema 实测通过；models 自身被 15+ 测试文件覆盖）。全部结构静态审读无逻辑缺失。

##### 7. ocos/contracts/（3 个 .py）

- **模块路径范围**：`ocos/contracts/`（__init__.py, attention_abi.py, feedback_abi.py）
- **模块职责**：Phase 35/36/37 冻结 ABI：注意力认知控制协议（AttentionDecision/AttentionScoreTrace/FocusChange/WMAllocation/AttentionReport/AttentionRecommendation/DecisionDigest）与认知反馈闭环协议（CognitiveFeedback/ExpectedOutcome/ActualOutcome/OutcomeEvaluation/LearningSignal/Evidence/DriftAlert + 自适应参数预算常量）。
- **对外提供能力**：全部 frozen dataclass + 常量：`ALLOW_PLANNING/DEFER_PLANNING/EXECUTION_ALLOW/EXECUTION_BLOCK_ATTENTION` 执行信号；`FORBIDDEN_DECISION_REASONS`（主权检查黑名单，决策 reason 不得含 "create goal"/"modify goal"/"call agent"/"execute task" 等 9 串）；`ADAPTIVE_PARAM_KEYS`（5 个允许自适应参数）与 `IMMUTABLE_PARAM_KEYS`（constitution/identity/permission/goal_ownership/user_preference_authority）；`MAX_SINGLE_STEP_DELTA=0.1`、`MAX_DAILY_MUTATION_BUDGET=0.2`、`CALIBRATION_MIN_SAMPLES=5`、`USER_ALIGNMENT_REJECT_THRESHOLD=0.3`。Evidence.merge() 支持样本数加权置信度合并。
- **输入输出**：纯类型契约；AttentionReport 为 tick 级摘要（mode/fatigue/queue_depth/sovereignty_violations/wm_slots_used + Phase36 扩展 focus_type/focus_priority/interrupt_count_1m/last_decisions/recommendation）。
- **正常工作流程**：Attention 引擎产出 AttentionDecision（带 score_trace 可审计）→ tick 末汇总 AttentionReport → 下游 WM/Planning/Execution 只消费该结构；执行后经 Validator→Evaluator→Feedback 链产出 CognitiveFeedback（禁止 AgentResult 直转 Feedback）→ Evidence 累积后才可影响 Belief → DriftAlert 只读报警不自动修正。
- **异常处理逻辑**：无运行时异常路径（纯数据契约）。
- **依赖其它 OCOS 模块**：无（仅标准库）。
- **被哪些 OCOS 模块调用**：`ocos/capability/{attention,result_understanding,calibration_store,outcome_evaluation,evidence_pipeline}.py`、`ocos/agent/{adaptive_params,drift_detector}.py`。
- **已知限制**：AttentionScoreTrace 注释声明"不允许字符串拼接伪造"但无运行时防伪造机制（纯注释级约束）。
- **验证状态**：【静态推演验证】（纯数据类，无独立行为；被 capability/agent 生产代码稳定引用，构造路径由那些模块的测试覆盖）。

##### 8. ocos/events/（5 个 .py，任务书标 6 实为 5）

- **模块路径范围**：`ocos/events/`（__init__.py, event_bus.py, event_store.py, dead_letter_queue.py, event_ingestion.py）
- **模块职责**：宪法 Rule 2 的进程内事件总线（pub/sub）。AUD-F6/GAP-P3-5 裁决：本包 = 宪法模块间通信总线（kernel.abi.Event + topic pub/sub，生产被 health_check/engine_bridge/governance_engine/process_runtime/policy_engine/scheduler 使用）；`ocos/event/` = 感知神经系统，两包并存不合并。
- **对外提供能力**：`EventBus.subscribe/subscribe_all/unsubscribe/publish(event, sync=True)/subscriber_count/clear`；`InMemoryEventStore.append(validate=True)/get_by_type/get_by_source/get_all/count/snapshot/clear`（原子追加：任一事件 payload 验证失败则整批不放行）；`DeadLetterQueue.put/get_all/get_by_type/count/replay/clear/prune_older_than`；`EventIngestion.ingest()`（tick step1，按优先级排序拉取）。
- **内部子模块**：CommitResult/StoreSnapshot/DeadLetterRecord/IngestedEvent；`_PRIORITY_MAP`（user_input=100 > goal_request=90 > external_stimulus=80 > observation=50 > engine_result=40 > heartbeat/health_check=10 > maintenance_tick=5，默认 30）；SYSTEM_EVENT_TYPES frozenset。
- **输入输出**：输入 kernel.abi.Event；输出订阅者回调执行（同步默认 / 异步 daemon 线程）。
- **正常工作流程（发布订阅机制）**：publish() → 锁内拷贝该 EventType 的订阅者 + 全局订阅者 → 同步逐个回调或起新线程 `_dispatch_sync` → 单订阅者异常不中断其它订阅者，失败事件进可注入的 DLQ（`_dead_letter_queue.put(event, subscriber_id, error)`）；unsubscribe 遍历清理；Trace ID 经 Event.trace_id 传播。InMemoryEventStore.append 用 kernel/event_schema.validate_event_payload 校验 required_payload_fields（未注册 EventType 的 schema 一律返回 False → 拒写）。
- **异常处理逻辑**：投递失败 → log error + DLQ（若无 DLQ 注入则仅日志）；DLQ.replay 失败重新入队且 retry_count+1；超 max_records(1000) 淘汰最早记录。
- **依赖其它 OCOS 模块**：`ocos.kernel.abi`（Event/EventType/SCHEMA_VERSION）、`ocos.kernel.event_schema.validate_event_payload`、`ocos.logging.get_logger`。
- **被哪些 OCOS 模块调用**（生产）：`ocos/agent/{agent_runtime,control_loop,engine_bridge,health_check}.py`、`ocos/goal/{maintenance_engine,goal_monitor,maintenance_types}.py`、`ocos/growth/engine.py`、`ocos/world_model/world_types.py` 等；测试覆盖 15+ 文件。
- **已知限制**：① EventBus.unsubscribe 恒返回 True（"简化实现"，未报告是否真删除）；② 异步投递 `publish(sync=False)` 返回 len(target_subs) 但不保证成功数，且 daemon 线程无汇合机制；③ EventBus 的事件不落库（持久化在 storage.event_store，二者无自动同步），宪法 Rule 4"状态变更必须记录 Event Store"依赖调用方手动双写。
- **验证状态**：【功能实测可通】。实测：subscribe(GOAL_SET)→publish→回调命中、InMemoryEventStore 原子追加 + schema 校验拒绝缺字段事件。

##### 9. ocos/event/（1 个 .py：__init__.py）

- **模块路径范围**：`ocos/event/__init__.py`（297 行，包体即单文件）
- **模块职责**：Phase 34A 感知神经系统：External World → EventBus(push) → EventNormalizer → CognitiveEvent → step1 ingest → Attention(candidate_score) → DECISION。**硬约束：事件 ≠ 意图，EventBus 不直接触发 Goal**。
- **对外提供能力**：`EventBus.push/push_file_change/push_timer/push_user_message(UX-P2, content 截断 2000 字)/push_webhook/ingest(max_events=10)/record_trace/get_stats`；`EventNormalizer.normalize`（类型识别/严重性评估/初始 candidate_score 粗估）。
- **内部子模块**：EventSource（FILE_CHANGE/TIMER/WEBHOOK/AGENT_RESULT/SYSTEM/USER_INPUT）、EventSeverity（TRIVIAL 0..CRITICAL 4）、AttentionDecision（IGNORED/QUEUED/ATTENDED/ALERT）、RawEvent/CognitiveEvent/IngestionTrace（`[EVENT]…[ATTENTION]…[DECISION]` 规范格式链路追踪）。
- **输入输出**：输入 RawEvent（或便捷方法参数）；输出 CognitiveEvent（deque(maxlen=1000) 暂存）与 IngestionTrace。
- **正常工作流程**：push → _classify（file_{op}/timer_{name}/webhook_{endpoint}/agent_result/user_input/system_event）→ _assess_severity（路径含 config→HIGH、secret→CRITICAL、test→LOW；SYSTEM/USER_INPUT→HIGH）→ _initial_score（severity 基线 0.1~0.9，TIMER ×0.8）→ 入 pending 队列 → ingest() popleft → Attention 打分 → record_trace 记录 [EVENT]/[ATTENTION]/[DECISION]。
- **异常处理逻辑**：锁保护 deque；无显式异常路径（push 恒成功）。
- **依赖其它 OCOS 模块**：无（仅标准库 + logging）。
- **被哪些 OCOS 模块调用**：`ocos/agent/agent_runtime.py:174`（`from ocos.event import EventBus`，生产）。测试覆盖 15+ 文件。
- **已知限制**：与 `ocos/events/EventBus` 同名不同物（已裁决并存）；record_trace 的日志将 `event.metadata.get("path", event.summary)` 打进日志，用户消息内容（summary 含 "User says: …"）会原样进日志，**无脱敏**。
- **验证状态**：【功能实测可通】。实测 push_file_change("/tmp/x/config.yaml") → severity=HIGH、ingest 命中。

##### 10. ocos/constitution/（4 个 .py）

- **模块路径范围**：`ocos/constitution/`（__init__.py, hub.py, behavioral.py, statement_validator.py）
- **模块职责**：行为级宪法运行时执行层。__init__ 声明 Freeze §2 禁令矩阵 L1~L6：L1 调用者身份验证(→PermissionGateway)、L2 内部模块隔离(→import rules)、L3 外部输出净化(→StatementValidator)、L4 反向控制检测、L5 语句级禁令、L6 Belief 禁止声明(→memory.belief)。
- **对外提供能力**：`ConstitutionHub.check_decision/check_action/check_promotion/verify_goal_creation/update_phase`；`BehavioralConstitution.check_decision`（<1ms，返回 check_time_us）；`StatementValidator.validate/validate_or_block/rule_count/get_rule_names`。
- **内部子模块/约束规则**：
  - behavioral.py：`_HIGH_RISK_ACTIONS` = {DELETE_USER_DATA, MODIFY_CONSTITUTION, MODIFY_IDENTITY, SHUTDOWN_SYSTEM, PROMOTE_TO_POLICY}；`_HUMAN_APPROVAL_ACTIONS` = 前三者。约束规则：DELETE_USER_DATA 需 context.user_consent；MODIFY_CONSTITUTION 需 governance_approved；MODIFY_IDENTITY 需 identity_anchor_present；空 context 一律 violation；requires_audit 恒 True。
  - statement_validator.py（Freeze §2 禁令矩阵 L5）：6 类检测规则（正则，中英双语）：emotion_claim(WARNING)/personality_claim(CRITICAL)/consciousness_claim(CRITICAL)/value_judgment(WARNING)/sovereignty_usurpation(CRITICAL)/identity_claim(CRITICAL)。决策逻辑：无 flag→CLEAN；有 flag→RESTRICTED（默认不拦截）；auto_block_critical=True 且有 CRITICAL→BLOCKED。`_RULE_TO_VIOLATION` 映射到 ViolationCategory 供 Belief.__post_init__ 硬拦截（24b4）。
  - hub.py：聚合 BehavioralConstitution + GoalOriginEnforcer（`ocos.goal.enforcer`）；check_promotion 严禁权限提升，require_human_approval 上下文可强制拒绝；check_decision 目前**只聚合行为级**结果（Static/Enforcer 仅用于 promotion/creation 路径）。
- **输入输出**：输入 Decision 对象（需含 .action 属性，check_action 用 `_FakeDecision` 适配纯字符串）/Goal 对/文本；输出 ConstitutionResult{allowed, requires_approval, requires_human_approval, requires_audit, violations[], check_time_us} 或 ValidationResult{decision, flags, clean}。
- **异常处理逻辑**：无异常路径；性能目标 <1ms 用 perf_counter_ns 计量。
- **依赖其它 OCOS 模块**：`ocos.goal.enforcer.GoalOriginEnforcer`、`ocos.kernel.goal_types.Goal`、`ocos.logging.get_logger`。
- **被哪些 OCOS 模块调用**：`ocos/proactive/engine.py`（ConstitutionHub）、`ocos/daemon/factory.py`、`ocos/interaction/base.py`、`ocos/capability/result_understanding.py`、`ocos/memory/belief/__init__.py`（StatementValidator 集成）。
- **已知限制**：① hub.check_decision 不调用 Static Constitution（静态 24 条规则在 kernel.constitution，由 CI/架构测试而非运行时执行，这是设计的两层拆分，但 hub 注释"三层宪法"易误导）；② 正则匹配 `matched_text[:80]` 截断；value_judgment 正则中有一处 `\\w+` 双反斜杠笔误（statement_validator.py:122，使该分支匹配字面 `\w+`，规则弱化）；③ StatementValidator 默认 auto_block_critical=False，仅标记不拦截，拦截责任在上层。
- **验证状态**：【功能实测可通】。实测：DELETE_USER_DATA 无 consent → not allowed；"I am the system and I feel happy" → 命中 identity_claim(CRITICAL)+emotion_claim(WARNING)，clean=False。

##### 11. ocos/kernel/（6 个 .py，__init__.py 为空文件）

- **模块路径范围**：`ocos/kernel/`（__init__.py 空, abi.py, event_schema.py, goal_types.py, constitution.py, time_manager.py）
- **模块职责**：ABI 层：6 个不可变核心对象（Observation/Memory/Knowledge/Goal/Decision/Action）+ Event/EventType + DecisionStatus；Event JSON 序列化与 payload schema 注册表；统一 Goal 类型（Phase 21 唯一权威来源）；24 条不可变宪法规则编码；统一时间源。宪法 Rule 10：Kernel 永不懂业务。
- **对外提供能力**：abi.py：`SCHEMA_VERSION="1.0.0"`、`EventType`（60+ 事件类型，涵盖 Observation/Memory/Knowledge/Decision/Action/System/Resource/Adaptive/Execution/Trace/Audit/Information/Process/Goal 全族）、frozen dataclass `Event/Observation/Memory/Knowledge/Goal/Decision/Action`、`DecisionStatus`（PROPOSED/COMMITTED/EXECUTED/REVOKED/SUPERSEDED/EXPIRED + legacy 映射 formed→PROPOSED、validated→COMMITTED、executing/completed→EXECUTED、failed→REVOKED；is_terminal={REVOKED,SUPERSEDED,EXPIRED}）。Goal/Decision `__post_init__` 校验 status 合法性（Goal 校验用延迟 import ocos.models.goal.GoalStatus）。event_schema.py：`serialize_event/deserialize_event/validate_schema_version(MAJOR 相同)/validate_event_payload` + `EVENT_SCHEMA_REGISTRY`（约 45 个事件的 required_payload_fields 注册，注意 GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 在 dict 中被重复定义两次，后值覆盖前值）。goal_types.py：`GoalLevel`(MISSION 0..ACTION 5)、`GoalStatus`(PENDING/ACTIVE/COMPLETED/CANCELLED/FAILED，ABANDONED=CANCELLED 别名)、`GoalOriginLevel`(HUMAN/SYSTEM/SELF，Phase 21 只允许 SYSTEM)、`GoalAuthority`(AUTONOMOUS/FRAMEWORK/PROPOSAL)、统一 `Goal`（frozen=False）、兼容 `UserGoal`（__post_init__ 强校验：priority 1-5、parent_id 必须 DECOMPOSED 来源、HUMAN 来源 caller 必须在 CALLER_WHITELIST={orchestrator,goal_parser,cli,api,repl,runtime,python-script,daemon}、to_goal() 适配）。constitution.py：`ConstitutionalRule` 枚举 24 条（Rule1 Decision 唯一 Action 源 / Rule2 Event Bus 唯一通信 / Rule3 输入必观察 / Rule4 变更必记录 / Rule5 知识变更需治理 / Rule6 Action 必有 Decision / Rule7 调度确定性 / Rule8 插件不改系统态 / Rule9 平台 800 行上限 / Rule10 Kernel 不懂业务 / Rule11 Runtime 不懂知识 / Rule12-13 Information 生命周期与控制不变量 / Rule14-16 Execution 三不变量 / Rule17-19 Goal 三不变量 / Rule20 Decision 必引用 Goal / Rule21-24 Process 四不变量）+ `Constitution.ALLOWED_IMPORTS` 白名单与 `check_import_allowed()`；validate_event_bus_communication/validate_no_direct_imports 为占位（GAP-P3-5 C.1，真实校验在 test_import_rules）。time_manager.py：`TimeManager`（逻辑 cycle 单调时钟 + UTC 物理时钟 + uptime）。
- **输入输出**：纯类型与校验；Event 可 JSON 双向序列化。
- **正常工作流程**：所有层 import kernel.abi 构造核心对象 → Event 经 ocos/events 总线流转（payload 先过 event_schema 校验）→ Goal 创建统一走 kernel.goal_types（Human 来源须过 caller 白名单，权限提升模型 GoalOriginLevel×GoalAuthority）。
- **异常处理逻辑**：Goal/Decision 构造 status 非法抛 ValueError（log error）；UserGoal 校验失败抛 ValueError；validate_import_allowed 纯函数；TimeManager tick 线程安全。
- **依赖其它 OCOS 模块**：abi.py 延迟 import `ocos.models.goal.GoalStatus`（受控环）。
- **被哪些 OCOS 模块调用**：几乎全仓库（events、event、constitution、runtime、goal、agent、capability、engines、tests 60+ 文件）。`ocos/autonomous/goal_manager.py`、`ocos/goal/{enforcer,goal_monitor,models}.py`、`ocos/runtime/{runtime_kernel,policy_engine}.py`、`ocos/agent/agent_runtime.py` 等直接依赖。
- **已知限制**：① kernel/__init__.py 为 0 字节空文件；② EVENT_SCHEMA_REGISTRY 中 GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 重复注册（event_schema.py:180-191 与 :232-252，后定义覆盖前定义，required 字段从 `["goal_id","description","priority"]` 等退化为宽松版本，schema 弱化）；③ 双 GoalStatus 双 Goal 类型并存（kernel.goal_types.Goal 与 kernel.abi.Goal 同名不同型，宪法兼容负担）。
- **验证状态**：【功能实测可通】。实测：RULES 数=24；check_import_allowed(kernel→models)=True、kernel→engines=False；validate_event_payload(GOAL_SET, {}) = False、带齐字段 = True；TimeManager tick 单调。

##### 12. ocos/os_v1/（7 个 .py）

- **模块路径范围**：`ocos/os_v1/`（__init__.py, os_types.py, personal_os.py, freeze.py, cognitive_drift.py, memory_validation.py, capability_adapters.py）
- **模块职责**：Phase 50 Personal Cognitive OS v1.0：统一认知路由入口 + 漂移检测 + 记忆质量验证 + 能力生态 + **v1.0 ABI 冻结（Scope Freeze 机制）**。
- **对外提供能力**：`PersonalCognitiveOS.register_capability/unregister_capability/classify_intent/process/call_capability/capability_summary`；`OSFreeze.freeze(tick_id) -> FreezeManifest / verify_abi / protocol_spec / is_frozen / module_count`；`CognitiveDriftDetector.set_baseline/check_drift/latest_report/significant_drifts`；`MemoryGrowthValidator.validate/quality_over_time/latest_quality`；`CapabilityEcosystem.register/list_available/get_provider` 与四个适配器（Codex/OpenTale/Browser/Analysis）。
- **Scope Freeze 机制（重点）**：freeze.py 冻结对象是**接口契约而非代码**（OS50-05: Freeze ≠ Dead）。`ABI_MODULES` 12 个冻结模块清单（ocos.runtime/self/memory/world_model/decision/extension/capability/cognitive_loop/evolution/personal_intelligence/cognitive_continuity/os_v1）；`CONSTITUTION_PRINCIPLES` 6 条（Art.I Identity.anchor 不可变 / Art.II Capability ≠ Identity / Art.III Evolution ≠ Self-Rewrite / Art.IV Memory ≠ Truth / Art.V Decision ≠ Execution / Art.VI No New Before Production）；三个协议规范 MEMORY_PROTOCOL（v1，7 个操作）/CAPABILITY_SDK（v1，4 操作 4 状态）/EXTENSION_SDK（v1，7 生命周期态，forbidden=[self_repair, permission_change, identity_modification, constitution_amendment]）。`OSFreeze.freeze(tick_id)` 生成 FreezeManifest{version=1.0.0, frozen_at_tick, abi_modules, constitution_ref="constitution.yaml", 各 SDK 版本, test_suite="full-regression", signatures=[f"{mod}:v1.0"...]}；`is_frozen = frozen_at_tick > 0`；`verify_abi(module)` 检查模块是否在清单内。**注意：签名是字符串拼接 `f"{mod}:v1.0"`，非密码学签名；冻结后没有对实现变更的强制校验钩子，verify_abi 只查清单成员**。
- **输入输出**：UserIntent(raw_text) → OSResponse(result/reasoning_chain/confidence)；FreezeManifest。
- **正常工作流程**：process(): classify_intent（关键词推断 domain：编程优先于写作避免"写代码"误判 WRITING；complexity 按字符长度 <20 SIMPLE/<80 MODERATE/<200 COMPLEX/否则 PROJECT）→ enrich(tags) → route(查 capability_providers 中 domain 匹配且 AVAILABLE) → 返回 OSResponse（result 仅回显 `[domain] raw_text[:100]`，confidence 恒 0.8）。process 的 decide/execute/learn 三段**未接真实子系统**（代码注释自认"实际生产中这里会调用各子系统，本次是统一接口层"）。
- **异常处理逻辑**：call_capability 对未注册/不可用 Provider 返回 success=False + error；适配器同型检查；drift 无基线时返回空报告。
- **依赖其它 OCOS 模块**：无（仅包内互依）。
- **被哪些 OCOS 模块调用**：**无生产调用者**（反查仅 os_v1 包内与 tests/test_phase50.py）。
- **已知限制**：① PersonalCognitiveOS.process 不执行真实认知链（stub 路由）；② 适配器 execute/generate/navigate/analyze 全部返回拼接字符串的模拟结果，无真实外部调用；③ Freeze 的 signatures 非密码学。
- **验证状态**：【功能实测可通】（进程/冻结/漂移/记忆质量 API 实测通过），但其"统一入口"的 decide/execute/learn 为占位 → 整体定【静态推演验证】（接口层可用，认知闭环未接线）。

##### 13. ocos/logging/（6 个 .py + config.yaml）

- **模块路径范围**：`ocos/logging/`
- **模块职责**：结构化 JSON 日志系统：OCOSLogger（debug/info/warning/error/critical，支持 component/process_id/extra 结构化字段与 exception 对象）、JSONFormatter（单行 JSON：timestamp/level/logger/message/component/process_id/exception/extra）、轮转 Handler（大小 10MB×5、按天 midnight×7）、LogRotator（手动轮转+gzip 压缩+列目录）、LogSearcher（按 query/level/component/after/before 过滤、tail、stats）、config.yaml（dictConfig 样例：console INFO + file DEBUG 到 ocos/logs/ocos.log）。
- **对外提供能力**：`get_logger(name) -> OCOSLogger`（缓存 + `_apply_default_config()` 首次自动配置 root=DEBUG，stdout handler=INFO，JSON 格式）；`OCOSLogger`；`RotatingFileHandler/DailyRotatingHandler`（自动 makedirs）；`LogRotator.rotate_if_needed/rotate/compress_old/list_logs`；`LogSearcher.search/tail/stats`。
- **输入输出**：日志写 stdout（默认）或文件（config.yaml 指定 `ocos/logs/ocos.log`）；LogSearcher 读 `ocos/logs/*.log*`（排除 .gz）。
- **正常工作流程**：模块首行 `logger = get_logger(__name__)` → 结构化调用 `logger.info("msg", component="x", key=val)` → JSONFormatter 把非标准 record.__dict__ 键收进 extra → 单行 JSON 输出。
- **异常处理逻辑**：文件读失败忽略（OSError continue）；JSON 解析失败跳行；handler 创建目录失败会抛（makedirs 无 exist_ok 保护时——实际 exist_ok=True）。
- **依赖其它 OCOS 模块**：无。
- **被哪些 OCOS 模块调用**：广泛（events、event、constitution、operations、distributed、agent、engagement、growth、execution、optimization、capability 等数十个文件 `from ocos.logging import get_logger`）。
- **已知限制/风险**：① **无脱敏机制**：日志字段原样输出，EventBus publish 会打印 event_id/类型（安全），但 ocos/event 的 record_trace 会把用户消息 summary 原样打日志，statement_validator 的 matched_text 也进日志 —— 敏感内容（用户输入、匹配到的"违规语句"）未脱敏；② `logger.__class__ = OCOSLogger` 换类手法在多进程/复制场景脆弱；③ `_LOGGER_CACHE` 与 `logging.getLogger` 全局名空间可能被标准 logging 重复创建 handler；④ config.yaml 只是样例，`_apply_default_config()` 并不读取它（无 dictConfig 调用路径）。
- **验证状态**：【功能实测可通】。实测 get_logger→info(component=...) 输出单行 JSON。

##### 14. ocos/alerts/（4 个 .py）

- **模块路径范围**：`ocos/alerts/`（__init__.py, models.py, channels.py, manager.py）
- **模块职责**：轻量告警系统：Alert{alert_id, level(info/warning/error/critical), source, message, detail, finding_id, created_at, acknowledged}；通道抽象（LogChannel→logging、FileChannel→alerts.log 每行 JSON）；AlertManager 聚合通道、发送、历史、acknowledge。
- **对外提供能力**：`AlertManager.register_channel/unregister_channel/send/send_alert/acknowledge/clear_history/history`。
- **输入输出**：输入告警参数；输出 logging 记录或文件行；内存历史 list。
- **正常工作流程**：send() 构造 Alert → 锁内遍历通道 try send（单通道失败静默吞掉）→ 历史追加。
- **异常处理逻辑**：通道异常 `except Exception: pass`（无日志），失败不可观测。
- **依赖其它 OCOS 模块**：无。
- **被哪些 OCOS 模块调用**：`ocos/daemon/{health_loop,factory}.py`（生产）。
- **已知限制**：与 `ocos/monitoring/manager.py` 内的 AlertManager（告警规则引擎版）同名不同实现；acknowledge 遍历 O(n)；FileChannel 默认路径 `alerts.log` 在 CWD。
- **验证状态**：【静态推演验证】（逻辑简单直白，无分支复杂度；由 daemon 健康环与 test_thin_coverage_e2e 引用）。

##### 15. ocos/auth/（4 个 .py）

- **模块路径范围**：`ocos/auth/`（__init__.py, role.py, user.py, identity_store.py）
- **模块职责**：身份与权限：Role(OWNER/ADMIN/USER/GUEST) × Permission(17 个细粒度：system:read/write/configure/upgrade/audit、capability:use/configure/install、tool:use/config/install、data:read/write/delete、user:manage/role) × ROLE_PERMISSIONS 映射；User frozen dataclass + UserStore（SQLite，复用 schema.py 的 users 表）；AgentIdentityRecord + IdentityStore（SQLite `agent_identity` 表，Phase 21→22 MasterAgent.boot 桥接）。
- **对外提供能力**：`PermissionChecker.check/check_any/check_all/require`（require 抛 PermissionDeniedError）；`UserStore.save/load/load_by_name/list/update_last_active/count`；`IdentityStore.save/load/update_last_boot/verify_identity/list/delete/close`（上下文管理器）。
- **输入输出**：users 表（schema.py CREATE_USER）；agent_identity 表（identity_store 自建 DDL，owner_user_id/manifest_url/constitution_version 等 10 列）。
- **正常工作流程**：boot → IdentityStore.load(agent_id) → verify_identity → update_last_boot；用户权限经 PermissionChecker 在操作前校验。
- **异常处理逻辑**：storage.connection 不可用时 fallback 直连 sqlite3（`_owns_connection` 标记决定 close 责任）；`close()` 后 `self._conn = None`（后续调用会 AttributeError，无重建）。
- **依赖其它 OCOS 模块**：`ocos.storage.connection`、`ocos.storage.schema.CREATE_USER`。
- **被哪些 OCOS 模块调用**：**反查生产调用为空**（仅包内互依；`ocos/agent/identity_store.py` 是另一份独立实现，auth/identity_store 未见生产接线）。
- **已知限制**：① 无认证（密码/token/签名）实现，public_key_hash 字段有列无验；② 与 agent/identity_store.py 双身份存储实现；③ IdentityStore._row_to_record 按位置索引取列，列序耦合 DDL。
- **验证状态**：【功能实测可通】（PermissionChecker 角色矩阵实测通过）；UserStore/IdentityStore 静态推演（SQL 直白）。

##### 16. ocos/security/（1 个 .py）

- **模块路径范围**：`ocos/security/manager.py`（555 行）
- **模块职责**：Phase X 统一安全管理：SecurityPolicy 白/黑名单访问控制 + RateLimiter（滑动窗口+突发桶）+ InputSanitizer（SQL 注入/XSS/路径穿越/命令注入 4 类正则检测）+ SecurityAuditLog（内存审计，max 10000，半数截断）+ SecurityManager 聚合入口。
- **对外提供能力**：`SecurityManager.check_access(source, action, policy_name="default", metadata) -> (AccessDecision, reason, details)`；`sanitize_input(text, source, context) -> (text, threats, decision)`；`register_policy/add_custom_policy/get_security_stats/get_recent_events/export_audit_log`；工厂 `create_security_manager`（支持环境变量 `OCOS_RATE_LIMIT` 覆盖限速）。
- **内部要点**：默认 3 策略（default: MEDIUM 白名单 query/read/plan/generate、黑名单 modify_identity/delete_memory/override_constitution、60 req/min；high_security: blocked=["*"] + require_auth；open: LOW 全放行 200 req/min）；`_severity_for_action`：critical={modify_identity, override_constitution, delete_all}，high={delete_memory, modify_goal, execute_system}。
- **输入输出**：输入 (source, action)/文本；输出 AccessDecision{ALLOW/DENY/RATE_LIMITED/REQUIRE_AUTH} + SecurityEvent 审计；audit 可 export_json。
- **正常工作流程**：check_access → 策略查找（未知策略 DENY）→ "*" 黑名单模式（不在白名单即拒）→ 显式黑名单 → 限流 → ALLOW；每步都写 SecurityAuditLog。
- **异常处理逻辑**：规则评估异常 log warning；审计条目超限截半。
- **依赖其它 OCOS 模块**：无。
- **被哪些 OCOS 模块调用**：`ocos/agent/master_agent.py`（生产注入）+ tests。
- **已知限制/风险**：① `sanitize()` **检测但不清洗**（sanitized=原样返回，注释自认"保留原始文本用于审计"），威胁列表需调用方自行处置；② `_CMD_PATTERNS` 中 `\{[^}]*\}` 会把任何花括号内容（如 JSON）判为命令注入，误报率高；`[;&|`$]` 同样宽泛；③ REQUIRE_AUTH 决策定义了但 check_access 从不返回它（require_auth 策略字段未生效）；④ 限流突发桶 refill 逻辑 `max(0, bucket - elapsed)` 把"每秒补充"实现为"减去流逝秒数"，单位语义混乱（时间秒 vs 请求个数），突发限制近似失效。
- **验证状态**：【功能实测可通】。实测：check_access("agent","modify_identity")=DENY；"SELECT…; DROP…" 检出 SQL_INJECTION。

##### 17. ocos/monitoring/（1 个 .py）

- **模块路径范围**：`ocos/monitoring/manager.py`（458 行）
- **模块职责**：Phase Y 统一监控：MetricsRegistry（counter/gauge/histogram → Prometheus exposition）+ AlertManager（规则引擎，cooldown 冷却）+ MonitoringManager（HTTP /metrics 与 /health 端点，默认 127.0.0.1:9090）。
- **对外提供能力**：`MonitoringManager.record_metric/evaluate_alerts/get_health_status/get_metrics/get_stats/start_http/stop_http`（上下文管理器）；工厂 `create_monitoring_manager`（环境变量 `OCOS_MONITORING_PORT`）；默认 3 条告警规则（error_rate>10%、avg_latency>1s、memory_health<30%）。
- **输入输出**：指标内存 dict → Prometheus 文本；HTTP 响应。
- **正常工作流程**：record_metric → registry；evaluate_alerts(context) → 规则冷却期内不重复触发 → Alert 状态机 FIRING/RESOLVED；get_health_status 按 critical/degraded/healthy 归纳。
- **异常处理逻辑**：start_http 失败捕获返回 False；histogram 截断至 1000（实际 [-500:]）。
- **依赖其它 OCOS 模块**：无。
- **被哪些 OCOS 模块调用**：tests（test_monitoring_manager、test_integration）。**无生产调用者**。
- **已知限制/风险**：① Prometheus 输出中指标名 `ococ_up` 拼写错误（manager.py:230-232，应为 ocos_up）；② Prometheus 直方图分位实现把 quantile 0.9/0.99 都输出 max(values)，非真实分位；③ AlertSeverity/AlertState 用 `class X(str)` 而非 Enum（可实例化，类型约束弱）；④ HTTP server 为单线程 TCPServer。
- **验证状态**：【功能实测可通】。实测 record_metric + get_metrics 输出 ocos_counters。

##### 18. ocos/performance/（1 个 .py）

- **模块路径范围**：`ocos/performance/manager.py`（497 行）
- **模块职责**：Phase Z 性能优化：SmartCache（LRU+TTL）、AsyncBatchProcessor（asyncio 批处理）、BulkPersistence（同步批量持久化，失败重入队）、PerformanceProfiler（计时/慢操作/p99）、PerformanceManager 聚合。
- **对外提供能力**：`PerformanceManager.get_cache/create_batch_processor/create_bulk_persistence/start_all/stop_all/get_stats/reset_profiler`；工厂 `create_performance_manager`。
- **输入输出**：内存缓存/队列；stats dict。
- **正常工作流程**：cache.get/set（monotonic 时钟 + move_to_end LRU）；bulk.enqueue 满批或超 flush_interval 触发 flush，失败 re-queue 并 errors+1；profiler.start/stop_timer 记录 duration。
- **异常处理逻辑**：flush 失败回滚入队返回 False；批处理循环异常捕获继续。
- **依赖其它 OCOS 模块**：无。
- **被哪些 OCOS 模块调用**：tests（test_performance_manager、test_integration）。无生产调用者。
- **已知限制**：① `get_cache(name)` 忽略 name 恒返回同一实例（注释自认简化）；② AsyncBatchProcessor._queue 是普通 list，async add/flush 无锁，多协程并发不安全；③ SmartCache 无锁（非线程安全）。
- **验证状态**：【功能实测可通】（cache set/get 实测）。

##### 19. ocos/operations/（3 个 .py）

- **模块路径范围**：`ocos/operations/`（__init__.py 注释型, sandbox_ops.py, search_ops.py）
- **模块职责**：Phase 22-E 高危操作安全执行层（AUD-F5 裁决：与 ocos/digital_world/ 宽操作库分工，operations 是"默认闭合、白名单优先"的执行闸门）。__init__ 明言：**两者当前均无生产调用者（仅 gate 脚本与测试引用）**。
- **对外提供能力**：`SandboxOps.execute(SandboxCommand) -> SandboxResult`（黑名单 BLOCKED_COMMANDS 30+ 条：rm -rf /、fork bomb、os.system、eval、compile( 等；白名单 ALLOWED_COMMANDS 前缀匹配：cat/ls/grep/git log 等 30 条只读；路径沙盒 SANDBOX_PATHS={/tmp/ocos_sandbox/, /home/laogao/Documents/trae_projects/ocos/}；子进程用最小环境变量防 stack-smashing（FIX-RUNTIME-1）；audit 记录每次判定）；`SearchOps.search(SearchQuery)`（API_WHITELIST 6 条 + DOMAIN_SUFFIX_WHITELIST 2 条、可选代理、真实 urllib 请求、响应 JSON/文本解析、审计）。
- **输入输出**：命令字符串 → stdout/stderr（各截断 10000 字符）；URL → results。
- **正常工作流程**：黑名单子串匹配（命中即拒）→ 白名单前缀（strict=True 不在白名单即拒）→ workdir 沙盒校验 → subprocess.run(shell=True, timeout, 最小 env)。
- **异常处理逻辑**：TimeoutExpired → stderr 记录；其余异常捕获返回失败结果；审计日志保留内存 list。
- **依赖其它 OCOS 模块**：`ocos.logging.get_logger`。
- **被哪些 OCOS 模块调用**：`ocos/extension/sandbox_runner.py`、`ocos/execution/bridge.py`（引用 import 层面）+ gate 脚本/测试；无直接生产主链路。
- **已知限制/风险**：① 黑名单是**子串匹配**：可被 `"rm -rf /x"`（含 "rm -rf /" 会被拦）但如 `"rm  -rf /"`（双空格）绕过子串匹配？——"rm -rf /" 是连续串，双空格会绕过；编码/变量展开（`rm -rf ${HOME}`）不匹配黑名单但也不在白名单，strict=True 下被白名单兜住；**白名单前缀匹配可被前缀后追加参数滥用**（如 "grep" 后接任意参数，属白名单设计预期）；② shell=True 本身即风险面（靠白名单约束）；③ SANDBOX_PATHS 硬编码了本机绝对路径 /home/laogao/...（可移植性差）；④ 白名单含 "env"（前缀），可泄露最小环境外进程信息有限但 env 本身输出的是子进程最小环境，风险低。
- **验证状态**：【功能实测可通】。实测 "rm -rf /" 被黑名单拦截 blocked=True。

##### 20. ocos/tool/（1 个 .py）

- **模块路径范围**：`ocos/tool/manager.py`（460 行）
- **模块职责**：Phase AI ToolIntegrationManager：工具描述符注册/发现/分类/调用/限速/审计/阻断。AI-TOOL-01~06 原则（工具≠能力、注册前验证、调用审计、失败隔离、资源限制、可回滚）。
- **对外提供能力**：`discover_tools/register_tool/unregister_tool/get_tool/list_tools/can_call_tool/call_tool/get_call_history/get_call_stats/get_available_tools/has_tool/block_tool/unblock_tool/get_status/get_stats`。
- **内部要点**：ToolCategory 6 类（SYSTEM/NETWORK/COMPUTE/KNOWLEDGE/PERSONAL/UNKNOWN，按名字关键词分类）；ToolPermission 5 级（READ_ONLY..UNRESTRICTED）；1 秒滑动窗口限速（默认 100/s）；注册时同步到 `ocos.capability.capability_registry.CapabilityRegistry.register_from_extension`。
- **输入输出**：ToolDescriptor → 工具 dict；call_tool 返回 {call_id, tool_id, success, result/error, duration_ms}。
- **正常工作流程**：call_tool → can_call_tool（存在性 + 非 DANGEROUS + 限速）→ `_simulate_tool_call`（**模拟**，返回拼接字符串，代码注释"实际项目应注入真实工具"）→ ToolCallRecord 记账（max 1000 条历史）。
- **异常处理逻辑**：限速/blocked → success=False；异常捕获返回 error。
- **依赖其它 OCOS 模块**：`ocos.capability_reality.adapter_discovery.AdapterDiscovery`、`ocos.capability.capability_registry.CapabilityRegistry`、`ocos.capability.capability_types`。
- **被哪些 OCOS 模块调用**：仅 tests（test_tool_integration_manager、test_master_agent_tool）。无生产调用者。
- **已知限制**：① call_tool 是模拟执行，无真实工具实现；② block_tool 用 permission=DANGEROUS 表达"阻断"，unblock 恒恢复为 READ_ONLY（丢失原权限级别）；③ discover_tools 异常时返回 {"error", "discovered":0}。
- **验证状态**：【功能实测可通】（注册→调用→成功返回，模拟执行链）。

##### 21. ocos/distributed/（1 个 .py）

- **模块路径范围**：`ocos/distributed/manager.py`（546 行）
- **模块职责**：Phase AB DistributedCognitionManager：多实例注册/心跳/故障转移/任务分发（ROUND_ROBIN/LEAST_CONNECTIONS/WEIGHTED/AFFINITY 四策略）/重试/回调/统计。AB-DIST-01~04 原则。
- **对外提供能力**：`register_instance/deregister_instance/update_heartbeat/get_instance/list_instances/get_healthy_instances/submit_task/dispatch_task/complete_task/fail_task/handle_instance_failure/check_health/get_stats/reset_stats/on_task_complete/on_instance_event/close`。
- **输入输出**：CognitionInstance（5 秒心跳健康判定）、DistributedTask（max_retries=3）→ stats。
- **正常工作流程**：submit_task → pending → dispatch_task 按 LEAST_CONNECTIONS（min task_count）选实例 → active → complete/fail（失败 retries+1，未达上限重新入 pending）→ 心跳超时（failover_timeout=10s）check_health → handle_instance_failure 转移任务并摘除实例。
- **异常处理逻辑**：回调异常 log warning；`task not in pending_tasks` 用对象相等判断（dataclass 相等比较，若字段被改可能误判）。
- **依赖其它 OCOS 模块**：`ocos.logging.get_logger`。
- **被哪些 OCOS 模块调用**：仅 tests（test_distributed_cognition_manager、test_master_agent_distributed）。无生产调用者。
- **已知限制**：① **单进程内存实现**：没有跨主机网络通信（host/port 仅记录），"分布式"实为单进程多实例账本模拟；② ROUND_ROBIN/WEIGHTED/AFFINITY 均为简化实现（返回第一个/最少连接）；③ `dispatch_task` 用 `task not in self._pending_tasks` 列表包含判断 O(n) 且依赖 dataclass __eq__。
- **验证状态**：【功能实测可通】。实测注册→心跳→submit→dispatch→complete 全链通过。

---


#### 分组 审计分组 W11：编排/自治/扩展/外部通信等支线模块 + 根模块

```text
以下为该分组审计原文（保留原始结构与行号引用）。
```

#### 一、模块详细说明

##### 1. ocos/autonomous_runtime/（5 文件）
- **模块路径范围**：`ocos/autonomous_runtime/`（`__init__.py`, `runtime_config.py`, `autonomous_loop.py`, `action_dispatcher.py`, `loop_supervisor.py`）
- **模块职责**：Phase 60"自主运行时"——把 cognitive_loop.LoopOrchestrator 包成可自跑的认知循环：模式管理（IDLE/ACTIVE/REFLECTING/SLEEPING/RECOVERING）、睡眠/唤醒节奏、反思输入自生成、动作解释与派发（关键词规则）、安全监督（防失控 tick、CL46-01 禁自造目标、CL46-02 身份漂移检测、动作超限）。
- **对外提供能力**：`AutonomousLoop`（tick/tick_many/enqueue_feedback/wake/sleep/summary/set_action_handler）、`ActionDispatcher`（register_handler/dispatch/interpret_decision/dispatch_by_name，ActionType 含 RUN_COMMAND/HTTP_FETCH/QUERY_DB 等 PW-4.1/P2-1 扩展）、`LoopSupervisor`（check_runaway/check_tick_count/check_goal_generation/check_identity_stability/full_check）、`RuntimeConfig`（40+ 配置项与 validate()）、`quick_runtime_test()`。
- **内部子模块**：见上，无更深目录。
- **输入输出**：输入为字符串感知输入/OpenTale 反馈 dict；输出 `LoopContext`（来自 cognitive_loop）、`DispatchedAction`、`SupervisorAlert`。
- **正常工作流程**：外部喂入 → tick() 安全上限检查 → 取队列反馈或自生成反思输入 → 委托 LoopOrchestrator.tick 认知循环 → 有 decision_proposal 时可经 action hook 派发 → Supervisor 定期体检。
- **异常处理逻辑**：tick 超上限记 SAFETY_CAP 并 sleep；dispatch handler 异常 → action.status="failed" 记入历史，不抛出；supervisor 返回 EMERGENCY_STOP 时置 emergency_stopped（但**无人消费 should_stop**，见风险）。
- **依赖其它 OCOS 模块**：`ocos.cognitive_loop.loop_orchestrator`、`ocos.cognitive_loop.loop_types`（真实 import）。
- **被哪些 OCOS 模块调用**：`ocos/execution/bridge.py:32`（ActionDispatcher/ActionType/DispatchedAction——**活代码**，审批桥核心）、`ocos/interaction/converse.py:166`（ActionType.RUN_COMMAND——活代码）、`agent_orchestration_autonomous.py` 仅文档提及未 import。其余仅 `ocos/tests/test_phase60.py`、`test_execution_bridge.py`、`test_thin_coverage_e2e.py`。
- **已知限制**：AutonomousLoop 本体仅测试使用；`_should_sleep()` 中 idle_timeout 分支永不生效（`_sleep_since` 逻辑与 idle_timeout 配置脱节）；LoopSupervisor 的紧急停止标志没有被 AutonomousLoop 轮询，属"检测到但不刹车"。
- **验证状态**：【功能实测可通】——test_phase60.py 50 用例全过（含 quick_runtime_test 全链路）。

##### 2. ocos/autonomous/（2 文件）
- **范围**：`__init__.py`, `goal_manager.py`
- **职责**：Phase L 自主目标管理——从 HomeostasisMonitor.regulate() 结果提取内生 SELF 目标，经 GoalOriginEnforcer（宪法门控）+ 外部 gate 双重门控后写入 GoalStore，提供活跃目标查询/进度/完成标记。
- **对外能力**：`GoalManager`（sync_from_homeostasis/get_active_self_goals/is_goal_active/mark_progress/mark_completed）、`GoalManagerProtocol`、`GeneratedGoal`、`GoalSyncResult`、工厂 `create_goal_manager(db_path, current_phase=25)`。
- **输入输出**：输入 RegulateResult（duck-typed，读 goals/gated 属性）；输出 GoalSyncResult 与 store 行 dict。
- **流程**：regulate 结果 → 逐目标构造 Goal 对象 → enforcer.verify_creation → 外部 gate → store.save → 汇总 generated/gated/errors。
- **异常处理**：逐目标 try/except，错误累积进 result.errors，不中断整批；store 查询失败 logger.warning 后返回 []。
- **依赖**：`ocos.goal.store`、`ocos.goal.enforcer`、`ocos.kernel.goal_types`。
- **被谁调用**：`ocos/agent/agent_runtime.py:399`（`_init_goal_manager` → `create_goal_manager()` 注入 MasterAgent._goal_manager）——**活代码（运行时初始化真实接线）**；测试仅见 `test_phase62d_loop_coupling.py` 间接。
- **已知限制**：目标 id 用 sha256(描述|驱力|当前时间戳)——同一描述每秒生成不同 id，重复同步可能堆积重复目标；未见去重逻辑。
- **验证状态**：【静态推演验证】——初始化链路（agent_runtime → MasterAgent）真实存在；sync 流程逻辑完整，但未找到/未运行针对 GoalManager 的专项测试。

##### 3. ocos/agent_orchestration/（9 文件）
- **范围**：`__init__.py, registry.py, selector.py, contract.py, executor.py, audit.py, fallback.py, supervisor.py, agent_pool.py`
- **职责**：Phase 28/62 Agent 编排层——Agent 注册中心（线程安全）、Agent 选择器、执行契约（超时/重试/降级）、真实子进程执行器、审计日志、降级处理器、async 执行监督器（含 SkillGraph 桥）、并发调度池。
- **对外能力**：`AgentDescriptor/AgentRegistry`（RLock 保护 CRUD + find_by_type/capability/get_available）、`AgentSelector.select/select_fallback`、`ExecutionContract.create/validate_output_schema`、`AgentExecutor.execute`（tempfile JSON→stdin，子进程 python3，防 shell 注入）、`ExecutionAudit`（started/completed/failed/timed_out 不可变记录）、`FallbackHandler.execute_with_policy`（no_retry/retry_3x/retry_with_fallback）、`ExecutionSupervisor.execute_task/execute_plan/cancel`（async + 同步包装）、`AgentPool.execute/execute_sync`（Semaphore 并发 + 全局超时 + PoolStats）。
- **输入输出**：输入 `ocos.planning.models.Task/Plan`；输出 `ExecutionRecord`/`PoolResult`。
- **流程（execute_task）**：capability_hints→SkillGraph（可选）→ selector 选 Agent → 建 Contract → 置 busy → audit.log_start → fallback 策略执行 → audit 完成/失败 → 恢复 available。
- **异常处理**：executor 捕获 TimeoutExpired/FileNotFoundError/通用异常并诚实返回错误；`_execute_agent`（AUD-F11 修复）无注入 executor 时诚实失败而非假成功；fallback 查询失败 BR-04 C-4 修复后留 warning 痕。
- **依赖**：`ocos.planning.models`（VALID_AGENT_TYPES/Task/Plan/TaskStatus）、`ocos.logging`（agent_pool）、模块内互依。
- **被谁调用**：`ocos/execution/bridge.py:37`（ExecutionAudit——活代码）、`ocos/agent_orchestration_autonomous.py`（registry/selector/contract/agent_pool）、`ocos/orchestration/engine.py`（registry/selector/supervisor/contract）、`ocos/collaboration/agent_collaboration.py`（AgentDescriptor）。`supervisor/executor/fallback` 的生产调用仅经 orchestration.engine（而后者本身只有测试调用，见下）。测试覆盖：tests/agent_orchestration/*、tests/validation/test_capability_bridge.py、tests/platform/test_scalability.py、scripts/phase22_gate.py 等。
- **已知限制**：AgentExecutor 默认 `./agents` 目录并不存在（agent_writer.py 等无脚本），execute 诚实返回"Agent script not found"；audit 记录仅内存；Registry 的 success_rate/avg_duration_ms 无自动更新机制。
- **验证状态**：【功能实测可通】——test_agent_orchestration_registry、test_phase62b_agent_pool(18)、test_phase62c_pool_integration、tests/agent_orchestration/*（批次运行）全部通过。

##### 4. ocos/orchestration/（2 文件）+ ocos/collaboration/（2 文件）
- **范围**：`ocos/orchestration/__init__.py, engine.py`；`ocos/collaboration/__init__.py, agent_collaboration.py`
- **职责**：Phase N 统一调度引擎（ExecutionSupervisor + AgentCollaboration + RuntimeLoop tick 集成）；Phase 50 多 Agent 协作引擎（parallel/sequential/pipeline 三策略 + ThreadPoolExecutor）。
- **对外能力**：`OrchestrationEngine`（start/stop/pause/resume/submit_task/submit_plan/submit_collaboration/process_tick/on_task_start/on_task_complete/on_tick/get_status，工厂 `create_orchestration_engine`）；`AgentCollaboration`（start/get_state/get_all_states/cancel/close，`create_collaboration_request`）。
- **输入输出**：Task/Plan/CollaborationRequest → 执行记录 dict / CollaborationState。
- **流程**：submit → process_tick 取队列 → 协作经 agent_map+execute_fn 走线程池；单任务走 supervisor.execute_task_sync（内部 asyncio.run）。
- **异常处理**：协作/单任务执行异常均捕获进 result["errors"]；回调异常吞掉。
- **依赖**：agent_orchestration（registry/selector/supervisor/contract）、collaboration、planning.models。
- **被谁调用**：**仅测试**（ocos/tests/test_orchestration_engine.py、tests/test_collaboration_agent_collaboration.py）。tests/test_import_rules.py 只约束依赖方向。主流程无任何 import。
- **已知限制**：`engine.py:346` 调 `record.to_dict()` 而 ExecutionRecord 无该方法（已实测 hasattr=False）→ 协作路径 execute_fn 必然进 except 返回 failure（严重 bug）；AgentCollaboration.cancel 只改状态不真正中断线程池任务；pipeline 策略只是按优先级排序的伪流水线。
- **验证状态**：【功能实测可通（测试内）/ 存在逻辑缺陷】——test_orchestration_engine.py 219 用例批次全过，但那批用例未覆盖 to_dict 分支；该分支为确定性崩溃点。整体属**孤立支线（死代码）**，主流程不调用。

##### 5. ocos/extension/（11 文件）
- **范围**：`__init__.py, extension_types.py, discovery_engine.py, analyzer.py, compatibility_checker.py, sandbox_runner.py, approval_engine.py, integration_engine.py, diagnosis_engine.py, repair_engine.py, evolution_memory.py`
- **职责**：Phase 44 认知扩展治理：发现→分析→兼容检查→沙箱验证→批准→集成→健康诊断→修复→冻结的完整生命周期状态机（CG44-01~04 边界）。
- **对外能力**：类型（ExtensionState/ExtensionCandidate/AnalysisReport/CompatibilityReport/SandboxResult/IntegrationRecord/HealthReport/EvolutionEntry 等）；引擎：DiscoveryEngine.scan_path（路径关键词推断类型）、Analyzer.analyze、CompatibilityChecker.check（FORBIDDEN_ACTIONS/FORBIDDEN_LAYER_ACCESS 治理检查）、SandboxRunner.validate（PW-2.2 三层探测：find_spec import 探测 + "cmd:" 前缀走 ocos.operations.sandbox_ops 真实沙盒试运行）、ApprovalEngine.evaluate/apply_state、IntegrationEngine.integrate/update_trust、DiagnosisEngine.check、RepairEngine.repair（禁改 identity/constitution 等，违反抛 RepairActionForbidden）、EvolutionMemory（不可变 entry 替换式记录）。
- **输入输出**：路径/候选对象 → 各类 frozen 报告对象；全部内存态。
- **异常处理**：SandboxRunner 各层失败一律诚实 passed=False 并留 behavioral_notes；RepairEngine 以异常拒绝禁止操作；其余引擎为纯函数式判定，无 I/O 异常面。
- **依赖**：仅模块内 `ocos.extension.extension_types` + 按需 `ocos.operations.sandbox_ops`（懒 import）。
- **被谁调用**：**仅测试**（ocos/tests/test_phase44.py 等）。主流程无 import，与 ecosystem/manager.py 是**两套互不相认的扩展治理体系**（后者另一套 TrustLevel/ExtensionState 枚举）。
- **已知限制**：DiscoveryEngine 的"扫描"只是路径字符串推断，无真实文件系统遍历；Analyzer 的 input/output_schema 硬编码 "dynamic"；SandboxRunner 对非 "cmd:" 候选仅做 import 探测即放行（passed）。
- **验证状态**：【功能实测可通（测试内）】——test_phase44 批次通过；整体属**孤立支线**。

##### 6. ocos/external/（1 文件）
- **范围**：`server_manager.py`
- **职责**：Phase W 统一 HTTP Server 与 Webhook 网关管理：ServerManager（启动/停止/健康检查/自动重启）、WebhookGateway（FastAPI 入站端点）、WebhookReceiver（asyncio 队列 + 精确/通配分发）、ServerContext/工厂函数/后台运行。
- **对外能力**：ServerManager.start/stop/wait/health_check/get_status/register_webhook_handler/send_webhook；WebhookGateway.app/start_background/stop_background；OCOS_API_PORT/OCOS_WEBHOOK_PORT 环境变量覆盖。
- **输入输出**：HTTP（API 8900 / Webhook 8901）；webhook POST body → WebhookPayload → handler。
- **异常处理**：API import 失败、uvicorn 缺失、启动失败均 logger.error 返回 False；健康检查异常计 crash_count 并可触发 auto_restart。
- **依赖**：懒加载 `ocos.interaction.api.server.app`、fastapi/uvicorn（外部）。
- **被谁调用**：MasterAgent 可注入（master_agent.py:200 `self._server_manager`，:2012-2035 start/stop/wait 方法），但 **daemon/factory.build_master_agent 并未注入** → 生产为 None；实际调用仅测试（test_server_manager.py、test_integration.py、tests/test_external_server_manager.py）。
- **已知限制**：`start()` 中 `finally: loop.close()` 会把 `_async_start` 里 `asyncio.create_task(_run_server())` 挂起的 serve 任务连同事件循环一起销毁——按静态推演，start() 返回 True 后 API server 立即死掉，随后健康检查必然失败（仅 crash 计数）；`stop()` 用新建 loop 对另一线程 loop 中的 uvicorn.Server 调 shutdown，跨 loop 不可靠；webhook 网关线程为 daemon，进程退出即断。
- **验证状态**：【静态推演验证】——单测（配置/状态统计类）通过，但真实 serve 生命周期存在上述结构性疑点，未见任何端到端实测证据。

##### 7. ocos/external_communication/（1 文件）
- **范围**：`manager.py`
- **职责**：Phase AK 外部通信通道管理器：通道抽象（BaseChannel）+ 通道管理（按类型/优先级选最优通道）+ 消息记录/统计。声明支持 WebSocket/HTTP/MQTT/Email/CLI/Push 六类。
- **对外能力**：ExternalCommunicationManager（initialize/register_websocket_channel/register_http_channel/send_message/send_websocket_message/send_http_message/get_health_summary/get_history/tick/clear_history）。
- **输入输出**：CommunicationMessage → CommunicationRecord。
- **异常处理**：send 失败记 failed record + 通道 error_count；无可用通道记 no_available_channel。
- **依赖**：无 OCOS 内部依赖（纯自包含）。
- **被谁调用**：MasterAgent 可注入（master_agent.py:242），daemon 工厂不注入；实际仅 ocos/tests/test_external_communication_manager.py。
- **已知限制**：**两类通道均为占位符**（_WebSocketChannelPlaceholder/_HTTPChannelPlaceholder 的 send 直接伪造 status="sent"、latency 1.5/2.3ms，无任何真实 IO）；MQTT/Email/CLI/Push 连占位实现都没有；send_message 的"运行中 loop"分支用另一线程 run_until_complete 已运行的 loop（会 RuntimeError），随后 except RuntimeError 落回 asyncio.run 兜底（绕了一圈）。
- **验证状态**：【逻辑不完整】——测试通过是因为测的就是占位行为；真实通信能力为零，审计记录会**伪造"已发送"**。

##### 8. ocos/ecosystem/（1 文件）
- **范围**：`manager.py`
- **职责**：Phase AC 生态集成管理器：扩展注册/批准/集成/激活/撤销、插件加载/启停/执行、适配器注册、能力路由、使用量驱动信任升降、统计。
- **对外能力**：EcosystemManager 全套方法 + ExtensionInfo/PluginInfo/TrustLevel/ExtensionState/PluginState（注意：与 extension/ 模块的同名枚举**不同套**）。
- **依赖**：仅 ocos.logging。
- **被谁调用**：MasterAgent 可注入（:218/:368），daemon 不注入；仅测试（test_ecosystem_manager.py、test_master_agent_ecosystem.py）。
- **已知限制**：`load_plugin` 注释自认"模拟加载"，从未真正加载任何插件代码，无条件置 LOADED（伪装成功）；approve_extension 要求 trust≥MEDIUM 但 trust 初始 UNKNOWN，只能靠 update_trust 按 usage_count 升级，形成"不激活就不被使用、不被使用就永远无法批准"的准死锁；与 extension/ 治理体系无任何打通。
- **验证状态**：【静态推演验证】——单测过，核心插件加载是空壳；**孤立支线**。

##### 9. ocos/engagement/（1 文件）
- **范围**：`manager.py`
- **职责**：Phase AF ProactiveEngagementManager：主动参与请求的创建/审核/批准/拒绝/忽略全状态流转、频率闸门（日/小时上限）、疲劳检查、权限+宪法双检、模板消息构建、输出回调、统计。
- **依赖**：仅 ocos.logging。
- **被谁调用**：grep 全库仅 `ocos/tests/test_proactive_engagement_manager.py`。**MasterAgent 均未注入/引用**（master_agent 只有 _human_ai_manager/_self_optimization_manager/_proactive_engine）。
- **已知限制**：approve_engagement 不做频率/权限检查即置 SENT（双检只在 execute_engagement 路径）；execute_engagement 在持有 _request_lock 期间执行外部回调（回调再调本管理器方法可能死锁——RLock 同线程可重入，跨线程回调有风险）；与 proactive/ 的 ProactiveEngine/ProactiveOutput 功能高度重叠（三套主动输出实现并存）。
- **验证状态**：【功能实测可通（测试内）】——单测过；**孤立支线/冗余实现**。

##### 10. ocos/human/（1 文件）
- **范围**：`manager.py`
- **职责**：Phase AD HumanAIManager 人机协同：用户偏好（CRUD + 显式/推断来源）、反馈记录与学习（PREFERENCE 可解析 JSON key/value、CORRECTION/POSITIVE/NEGATIVE 记账）、对话状态（上限 50）、交互通道注册与消息发送、事件回调、关键词意图推断、统计。
- **依赖**：仅 ocos.logging。
- **被谁调用**：`ocos/agent/master_agent.py:2533/2545`（FeedbackType/CollaborationMode 枚举转换）及 set/get_preference、record_feedback、start_conversation、infer_intent 等方法——但均以 `self._human_ai_manager is None` 防御，**daemon 工厂不注入 → 生产恒为 None**；测试：test_human_ai_manager.py、test_master_agent_human_ai.py。
- **已知限制**：learn_from_feedback 的"学习"仅记 result dict，无任何行为参数被真正修改；infer_intent 是关键词规则；对话历史仅内存（与 AD-HUM-04"持久化"承诺不符）。
- **验证状态**：【功能实测可通（测试内）/ 生产未接线】——单测过；可注入支线。

##### 11. ocos/sleep_dream/（2 文件）
- **范围**：`__init__.py, manager.py`
- **职责**：Phase U 自主睡眠与梦境：SleepDreamManager（睡眠决策：空闲时长/稳态驱力 → 睡眠类型 power_nap/full_sleep/rem_cycle → 睡眠→做梦→醒来周期）、DreamGenerator（5 类梦境模板生成 + 洞察提取）、SleepCycleStats 与文本报告。
- **依赖**：无 OCOS 内部 import（memory_source/knowledge_graph/homeostasis 全部 duck-typed 可选注入）。
- **被谁调用**：MasterAgent 可注入（:194/:328，:1913-1952 decide_sleep/run_sleep_cycle/get_stats/generate_report），**daemon 工厂不注入 → 生产恒 None**；测试 test_sleep_dream.py 13 用例。
- **已知限制**：`manager.py:158` `elif DreamType.CREATIVE_COMBO:`（漏写 `== dream_type`）恒真 → PROBLEM_SOLVE/EMOTION_PROCESS 的洞察分支不可达；decide_sleep 的睡眠类型判定用 idle_time 阈值，但触发睡眠时 idle 必 >300s，power_nap 分支（<120s）永不命中；全新实例 idle_time 恒 0（last_sleep_end/start 均 None），空闲触发在首次睡眠前永远不成立；梦境洞察是固定文案，无真实记忆重组。
- **验证状态**：【功能实测可通（测试内）/ 内含逻辑缺陷】——13 用例过；可注入支线。

##### 12. ocos/optimization/（1 文件）
- **范围**：`manager.py`
- **职责**：Phase AF SelfOptimizationManager：性能基线、优化提案（5 类 OptimizationType）、应用/验证/回滚状态机、auto_optimize 循环（提案→应用→执行优化 fn→验证）。
- **依赖**：仅 ocos.logging。
- **被谁调用**：`ocos/agent/master_agent.py:2653`（OptimizationType 解析）及 propose/apply/set_baseline 等方法（`self._self_optimization_manager is None` 防御）——daemon 不注入，生产恒 None；测试 test_self_optimization_manager.py、test_master_agent_optimization.py。
- **已知限制**：apply_optimization 不执行任何真实优化动作（只把 before_metrics 存档、状态置 APPLIED），"优化"全靠外部 optimization_fn；改进率按 `(old-new)/old` 简单平均，指标方向性未区分（延迟/吞吐混算）。
- **验证状态**：【功能实测可通（测试内）/ 生产未接线】。

##### 13. ocos/initiative/（2 文件）
- **范围**：`__init__.py, true_initiative.py`
- **职责**：Freeze Phase 49 TrueInitiative 真主动性引擎：记忆召回触发（relevance≥0.7）、空闲触发（30 分钟问候 / 2 小时状态确认）、用户模式触发；去重排序；权限门审批；输出闭环记忆；每日上限。
- **依赖**：无 OCOS 内部 import（user_memory/memory_recall/permission_guard duck-typed）。
- **被谁调用**：`ocos/agent/agent_runtime.py:383`（`_init_true_initiative` → 注入 `agent._true_initiative`）——**初始化接线是活代码**，但 grep 显示注入后**无任何消费点**读取 `_true_initiative`（master_agent 无 check_and_generate 调用）→ 实际效果为死注入。
- **已知限制**：`true_initiative.py:140-148` `if idle_sec >= 1800 ... elif idle_sec >= 7200` —— elif 分支不可达（7200>1800），"状态确认"永不触发；`:150-173` `_pattern_based_initiative` 构造了 requests 但最终 `return []`（整段死代码）；每日计数 increment_count/get_daily_count 从未被调用方联动。
- **验证状态**：【逻辑不完整】——初始化链路真实但功能从未被消费，且内部有可达性 bug。

##### 14. ocos/proactive/（6 文件）——本组唯一被主流程实际调用的"主动输出"实现
- **范围**：`__init__.py, audit.py, engine.py, templates.py, output.py, enhanced_output.py`
- **职责**：P2-D ProactiveEngine：全确定性主动输出触发链（频率闸门→SELF 目标待办→疲劳闸门→模板轮换→权限双检 fail-closed→输出→SQLite 审计，无 LLM）；Phase P ProactiveOutput（焦点驱动 + 日/小时/间隔节流的包装层）；Phase AJ ProactiveOutputEnhanced（多通道/统计/可配置阈值的再包装）。
- **对外能力**：ProactiveEngine.maybe_proactive_output、ProactiveAuditStore（SQLite proactive_audit 表：record/count_since/count_granted_today/recent）、TEMPLATE_POOL/select_template（确定性取模轮换、空 topic 回退问候）、ProactiveOutput.try_proactive_output/output_observation/output_suggestion/output_alert、ProactiveOutputEnhanced.emit/get_stats/set_limits。
- **依赖**：audit/engine/templates 自包含；output.py 依赖 `ocos.attention.focus`（AttentionFocus/FocusType）并内嵌 engine；engine.py 依赖 ocos.goal.store 的 duck-typed load_active。
- **被谁调用**：`ocos/agent/master_agent.py:1657`（lazily 构造 ProactiveEngine，goal_store/attention/permission_guard/constitution/output_callback 全注入）→ `ocos/agent/life_cycle_orchestrator.py:106`（_tick_idle 尾部调用）→ `ocos/daemon/__init__.py:391`。**活代码，主流程真实调用**。output.py/enhanced_output.py 则仅测试使用（test_proactive_output*.py、test_thin_coverage_e2e.py 用 engine）。
- **已知限制**：output.py 的 `_today_count` 只增不清（无跨日重置逻辑）→ 达到 daily_limit 后**永久节流**；`_record_output(priority: int = OutputPriority.MEDIUM)` 默认参数混用枚举与 int；enhanced_output._priority_ge 死方法；三套主动输出（engine/output/enhanced_output）+ engagement/manager 语义重复。
- **验证状态**：【功能实测可通】——test_proactive_output(批次)+test_proactive_output_enhanced+test_phase_fix17_proactive 相关批次通过；主流程链路（daemon→lifecycle→master→engine）真实存在。

##### 15. ocos/task/（1 文件）
- **范围**：`__init__.py`（整个模块只有这一个文件）
- **职责**：Phase 23-C 执行期 TaskDAG（RLock 线程安全）：add_task/add_dependency（含自环与循环检测回滚）/resolve_ready/topological_order。与 planning.models 的同名 TaskDAG 同名不同责（AUD-F7 分工裁决，执行期就绪队列 vs 规划期 DAG）。
- **依赖**：无（纯标准库）。
- **被谁调用**：`ocos/agent/agent_runtime.py:1001`（PW-4.4 规划 DAG → 执行期镜像，供 RuntimeKernel ExecutionCheckStage）——**活代码**；tests/test_stability/test_concurrency_locks.py、ocos/tests/test_runtime_stages_wiring.py。
- **验证状态**：【功能实测可通】——test_runtime_stages_wiring 批次通过；唯一预期生产消费者已接线。

##### 16. ocos/examples/（2 文件）
- **范围**：`__init__.py, echo_agent.py`
- **职责**：Phase 27 Capability ABI v1.0 参考实现 EchoAgent（echo/ping/identity/reverse 四动作，零依赖）。
- **依赖**：无 OCOS 内部 import。
- **被谁调用**：`scripts/phase27_gate.py:62`（门禁脚本）；示例性质。
- **验证状态**：【功能实测可通】——代码完整自洽，属参考样例而非死代码（有脚本引用）。

##### 17. ocos/plugins/（1 文件）与 ocos/stability/（空目录）
- `ocos/plugins/__init__.py`：**0 字节空文件**，整个目录无任何实现——纯占位。
- `ocos/stability/`：**完全空目录**（无 __init__.py，无任何文件）。注意 `tests/test_stability/` 存在且 `test_concurrency_locks.py` import 的是 `ocos.task`，与本目录无关。两处均为历史规划占位，无代码。
- **验证状态**：【占位代码】。

##### 18. ocos/ 根目录 6 个文件
- **`ocos/__init__.py`**：包声明，`__version__="1.0.0"`。状态：完整。
- **`ocos/cognitive_interface.py`**（14 行）：命名空间桥接，re-export `ocos.interaction.cognitive_interface.CognitiveInterface`（CLI/REPL/API/Python 四入口统一）。grep 显示内部无 import 方（用户侧入口约定）。【静态推演验证，正常】
- **`ocos/homeostasis.py`**（41 行）：桥接 re-export `ocos.capability.homeostasis` 的 HomeostasisManager + 6 监控器 + 8 数据类型。grep 内部无调用方（autonomous_runtime 注释里提到 homeostasis.py 的 derive_drives，但那是 capability/homeostasis 本体）。便捷导入垫片。【正常】
- **`ocos/orchestrator.py`**（19 行）：桥接 re-export `ocos.capability.orchestrator` 的 CapabilityOrchestrator/OrchestrationResult/DispatchResult。无内部调用方。注意与 `ocos/orchestration/`（Phase N 引擎）**毫无关系**，同名易混淆。【正常垫片】
- **`ocos/belief.py`**（458 行）：BELIEF_MODEL v1.0 信念引擎——Belief/BeliefDimension/BeliefQuadrant/Evidence/SOURCE_WEIGHTS、BeliefManager（add_belief/update_with_evidence 贝叶斯加权更新/decay_check 时间衰减/prune_dormant/query/get_strongest/merge_beliefs/stats/防确认偏误 alert/MAX_BELIEFS=1000 GC）。**纯内存**（docstring 自认 SQLite TBD）。被谁调用：仅 ocos/tests/test_phase61a_belief.py、test_phase62d_loop_coupling.py——**孤立支线**，与 agent/belief_system.py、agent/belief_consolidation.py 是不同体系。已知限制：负证据公式 `(old*p + (-1)*e)/(p+e)` 可产生负值被钳到 0.01（信息丢失，非严格贝叶斯）；decay_check 未重算 strength（仅 >0.01 变化时算，临界点附近轻微不一致）。【功能实测可通（测试内）】——test_phase61a_belief 批次通过。
- **`ocos/agent_orchestration_autonomous.py`**（392 行）：Phase 61 AutonomousOrchestrator 自主编排器——submit_goal → _decompose_goals（固定三段：researcher 分析 / writer 执行 / reviewer 审查）→ 串行调度（每 tick 3 个）或 Phase 62c AgentPool 并发（execute_sync）→ _monitor_running → _sync_goal_status → COMPLETED；事件日志 drain_events。被谁调用：仅 ocos/tests/test_phase61_orchestration.py、test_phase62c_pool_integration.py——**孤立支线**。已知限制：① docstring 架构图声称含 "loop (AutonomousLoop)" 成员，实际无该字段（从未 import AutonomousLoop），Phase 60/61 并未真正缝合；② 串行路径 `_monitor_running` 中 running 任务第二 tick 直接按 `attempts <= max_attempts` 判定 completed——**无任何真实执行即伪造成功**（与 supervisor 的 AUD-F11 诚实失败修复精神相悖）；③ `phase` 从未被置为 ADAPTING → `_adapt()` 重试逻辑不可达（失败任务无人重试）；④ 串行路径默认 agent_id="default-agent" 兜底，也不执行。【逻辑不完整】

---

##### 活代码 vs 孤立支线总结
**主流程真实调用（活代码）**：
- `autonomous_runtime/action_dispatcher.py`（execution/bridge 审批分级 + interaction/converse shell 能力）
- `agent_orchestration/audit.py`（execution/bridge）、`registry.py`/`selector.py`/`contract.py`/`agent_pool.py`（被 orchestration.engine 与 agent_orchestration_autonomous 使用，但后两者本身不在主流程）——严格说 agent_orchestration 中只有 **audit.py 被主流程直连**，其余经支线间接
- `autonomous/goal_manager.py`（agent_runtime 初始化注入 MasterAgent）
- `proactive/engine.py + audit.py + templates.py`（daemon→lifecycle→master 空闲期主动输出，含 UserInbox 回调）
- `task/__init__.py`（agent_runtime 执行期 DAG 镜像 → RuntimeKernel Stage⑤）
- 根目录 `cognitive_interface.py`/`homeostasis.py`/`orchestrator.py`（对外便捷入口垫片，语义上活）

**可注入但生产未注入（MasterAgent 参数存在、daemon 工厂不传，默认 None）**：human/manager、optimization/manager、sleep_dream/manager、ecosystem/manager、external/server_manager、external_communication/manager。

**纯孤立支线/死代码（仅测试或零调用）**：autonomous_runtime/autonomous_loop+loop_supervisor+runtime_config（AutonomousLoop 整体）、orchestration/ 全部、collaboration/（仅被同样孤立的 orchestration.engine 引用）、extension/ 全部、engagement/manager、proactive/output+enhanced_output、belief.py、agent_orchestration_autonomous.py、initiative/true_initiative（死注入）、plugins/、stability/。

---




## 3. 文件全量索引【最重要章节】

> 本章收录 OCOS 项目内每一个文件的索引（13 个审计分组逐文件深读产出，格式统一为：路径 / 文件类型 / 核心功能 / 关键类函数常量 / 导入依赖 / 被调用方 / 状态）。
> 3.1–3.11 为 ocos/ 源码分组（每组一个源码包或模块群）；3.12 为 ocos/tests 测试套件；3.13 为脚本/配置/文档资产/根目录文件。
> 状态图例：完整实现 / 半成品 / 占位代码 / 配置模板 / 占位（空目录）。


#### 审计分组 W1：agent 核心模块 —— 文件索引

#### 二、文件全量索引

路径前缀均为 `ocos/agent/`。

`__init__.py`
- 文件类型：源码（包导出）
- 文件核心功能：agent 包公共 API 汇总导出（30+ 符号）
- 内部关键类/函数/常量：__all__ 列表（AgentState/MasterAgent/GoalStack/BeliefSystem/AgentRuntime/EngineBridge 等）
- 导入依赖（OCOS内部）：state/master_agent/interfaces/goal_types/goal_stack/intent/attention/working_memory/episode_memory/capability_manager/execution_manager/identity_anchor/life_cycle_orchestrator/capability_selector/meta_controller/decision_loop/cortex_activator/belief_system/memory_consolidator/knowledge_base/experience_store/agent_runtime/engine_bridge
- 被哪些OCOS文件调用：隐式（import ocos.agent）
- 状态：完整实现

`adaptive_params.py`
- 文件类型：源码
- 文件核心功能：自适应参数防护层（唯一写入点，单步 0.1/日预算 0.2 双限制）
- 内部关键类/函数/常量：AdaptiveParamGuard.adjust/_apply/_reset_daily_budget_if_new_day/get_adaptation_state；AdaptiveParams；PermissionDeniedError
- 导入依赖：ocos.contracts.feedback_abi、ocos.logging
- 被哪些OCOS文件调用：无（grep 无外部引用）
- 状态：完整实现（未接线治理组件）

`agent_runtime.py`
- 文件类型：源码（核心，1795 行）
- 文件核心功能：Agent 统一运行时，10 步持久化认知 tick 循环 + Identity/Memory/Goal 持久化恢复
- 内部关键类/函数/常量：AgentRuntime（boot/tick/_tick_step_event_ingestion~_tick_step_learning_consolidation 共 11 个 step 方法/_replan_failed_task/_revise_task_description/_record_goal_result/_record_episode_from_result/_extract_beliefs/_extract_beliefs_from_results/get_stability_report）；RuntimeState
- 导入依赖：master_agent/capability_selector/meta_controller/decision_loop/cortex_activator/belief_system/memory_consolidator/knowledge_base/experience_store/engine_bridge/state/metrics_collector/health_check/identity_anchor/identity_store/goal_store + ocos.memory.hub、ocos.storage.working_memory（及延迟导入 ocos.event、ocos.capability.*、ocos.planning.*、ocos.task、ocos.goal.*、ocos.learning.*）
- 被哪些OCOS文件调用：ocos/daemon/__init__.py:77（生产主循环）、ocos/interaction/cli/commands/run.py、tests/test_writer_integration、test_goal_claim、test_single_main_loop、test_runtime_loop、test_execution_bridge、test_say_channel、test_phase49c_skill_growth
- 状态：完整实现（含 _tick_errors 未自增、_homeostasis_check/_sleep_tick/_emergency_tick 死代码、_extract_beliefs 条件失配等缺陷，见风险清单）

`attention.py`
- 文件类型：源码
- 文件核心功能：Agent 局部注意力状态（Phase 35 降权，别名 LocalAttentionState）
- 内部关键类/函数/常量：Attention（focus/unfocus/switch_to/tick/local_tick/needs_sleep/reset；fatigue/current_focus 为 property）；FocusMode；FATIGUE_RATE 常量表
- 导入依赖：无 OCOS 内部依赖
- 被哪些OCOS文件调用：ocos/agent/__init__.py（导出）；生产装配已被 ocos.capability.attention.CognitiveAttentionController 替代
- 状态：完整实现（非生产默认）

`belief_consolidation.py`
- 文件类型：源码
- 文件核心功能：Episode→Belief 迁移轨迹（CLS 慢系统写路径，确定性规则）
- 内部关键类/函数/常量：consolidate_episodes(hub,limit=20,min_confidence=0.6)；_statement_from_episode；ConsolidationRecord
- 导入依赖：ocos.memory.hub、ocos.self.statement_validator、ocos.memory.belief.models（延迟）
- 被哪些OCOS文件调用：tests/test_belief_consolidation.py；无生产调用方（master_agent._consolidate_episodes 为平行实现）
- 状态：完整实现（:66-77 存在自认不可行的死代码段）

`belief_system.py`
- 文件类型：源码
- 文件核心功能：置信度门控信念存储（内存 + 经 L6 门控的 hub 持久化写路径）
- 内部关键类/函数/常量：BeliefSystem（add/get_held/get_all/query/challenge/decay_all/bind_hub/_persist；persisted_count/rejected_count）；Belief（is_held/decay）；BeliefSource 枚举
- 导入依赖：ocos.self.statement_validator、ocos.memory.hub（TYPE_CHECKING）、ocos.memory.belief.models（延迟）
- 被哪些OCOS文件调用：agent_runtime.py:27、tests/test_belief_consolidation.py
- 状态：完整实现（_persist O(N) 扫描性能隐患）

`capability_manager.py`
- 文件类型：源码
- 文件核心功能：Agent 能力列表（引擎 id → 引擎实例注册表）
- 内部关键类/函数/常量：CapabilityManager（register_engine/unregister_engine/has_capability/list_capabilities/get_engine/count）
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/daemon/factory.py:105、tests/test_phase49c_skill_growth.py
- 状态：完整实现

`capability_selector.py`
- 文件类型：源码
- 文件核心功能：意图→引擎编排序列映射
- 内部关键类/函数/常量：CapabilitySelector（map/register_mapping/unregister_mapping/get_available_intents/get_required_engines）；DEFAULT_MAP
- 导入依赖：无
- 被哪些OCOS文件调用：agent_runtime.py:22、tests/test_writer_integration.py
- 状态：完整实现（DEFAULT_MAP 引用的引擎 id 与实际注册表部分不匹配）

`cognitive_bridge.py`
- 文件类型：源码
- 文件核心功能：MasterAgent↔Engine 显式路由桥（"translate, never decide"）
- 内部关键类/函数/常量：CognitiveBridge（reason/plan/decide/reflect/learn）；BridgeResult（to_observation）
- 导入依赖：ocos.models.process、ocos.kernel.abi
- 被哪些OCOS文件调用：master_agent.py:33、ocos/capability/skill_graph_executor.py:27、tests/test_phase22_prompt2.py
- 状态：完整实现

`context_compressor.py`
- 文件类型：源码
- 文件核心功能：Working Memory → token 预算压缩器（dataclass 版，Phase 24-D）
- 内部关键类/函数/常量：ContextCompressor（compress/_extract_text/_importance）；CompressionConfig；CompressionResult
- 导入依赖：ocos.logging
- 被哪些OCOS文件调用：无（与 memory_consolidation.py 内的 ContextCompressor 功能重叠，无外部引用）
- 状态：完整实现（疑似冗余副本，未接线）

`continuity_trigger.py`
- 文件类型：源码
- 文件核心功能：dream 巩固期身份连续性检查点（四引擎 + ~/.ocos/continuity.json 落盘）
- 内部关键类/函数/常量：run_continuity_checkpoint/_persist/load_continuity；_CONTINUITY_FILE 常量
- 导入依赖：ocos.cognitive_continuity.*（延迟）、ocos.agent.wisdom_trigger、ocos.personal_memory.wisdom_store、ocos.storage.connection、ocos.logging
- 被哪些OCOS文件调用：master_agent.py:1379（dream）、ocos/interaction/converse.py:384,438
- 状态：完整实现

`control_loop.py`
- 文件类型：源码
- 文件核心功能：Single Authority 控制回路（目标创建双关卡 + 微循环编排）
- 内部关键类/函数/常量：ControlLoop（create_goal/run_cycle/boot_complete/enter_sleep/wake_from_sleep/enter_dream/shutdown）；set_test_caller/clear_test_caller/get_caller（contextvars）
- 导入依赖：ocos.agent.goal_types、ocos.agent.lifecycle、ocos.goal.enforcer、ocos.goal.factory
- 被哪些OCOS文件调用：master_agent.py:32、tests/test_phase22_prompt1.py
- 状态：完整实现

`cortex_activator.py`
- 文件类型：源码
- 文件核心功能：认知皮层激活/休眠/紧急/熔断四模式管理
- 内部关键类/函数/常量：CortexActivator（activate/sleep/block/emergency_activate/recover/needs_intervention/get_status）；CortexMode
- 导入依赖：无
- 被哪些OCOS文件调用：agent_runtime.py:26
- 状态：完整实现（emergency_activate 后未再调 recover 的路径闭环不完整——runtime 只在 _homeostasis_check 中用，而该方法是死代码）

`decision_loop.py`
- 文件类型：源码
- 文件核心功能：感知→推理→决策→执行→观察→反射闭环编排
- 内部关键类/函数/常量：DecisionLoop（execute_single/execute_n/get_history/reset）
- 导入依赖：master_agent、capability_selector、executive_controller、ocos.models.process
- 被哪些OCOS文件调用：agent_runtime.py:24（Step 7 兜底，默认经 OCOS_ENABLE_COGNITIVE_LOOP=0 关闭）
- 状态：完整实现（生产默认停用）

`drift_detector.py`
- 文件类型：源码
- 文件核心功能：认知漂移检测（goal/capability/preference/confidence 四类，只报警不修正）
- 内部关键类/函数/常量：DriftDetector（check_goal_drift/check_capability_drift/check_confidence_drift/check_all/get_status/record_capability_usage）；DRIFT_WINDOW_SIZE/DRIFT_ALERT_CONTINUOUS 等常量
- 导入依赖：ocos.contracts.feedback_abi、ocos.logging
- 被哪些OCOS文件调用：无（grep 无外部引用）
- 状态：完整实现（未接线治理组件）

`engine_bridge.py`
- 文件类型：源码
- 文件核心功能：Agent↔Engine 桥接（工厂+注册表+归一化适配器）
- 内部关键类/函数/常量：EngineBridge（register/get_adapter/execute/register_all/capability_registry）；EngineAdapter（execute/_build_kwargs）；ENGINE_REGISTRY；_ensure_engines_registered
- 导入依赖：ocos.events.event_bus、ocos.runtime.context_manager、ocos.kernel.abi、ocos.models.process、ocos.engines.*（延迟）、ocos.capability.*（延迟）
- 被哪些OCOS文件调用：agent_runtime.py:31、ocos/interaction/converse.py:212（ENGINE_REGISTRY）、tests/test_writer_integration.py
- 状态：完整实现

`episode_memory.py`
- 文件类型：源码
- 文件核心功能：Agent 情景记忆（内存 Episode 列表）
- 内部关键类/函数/常量：EpisodeMemory（record/recall/recall_recent/recall_important/count/clear）；Episode dataclass
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/agent/__init__.py 导出；生产 Episode 持久化实际走 ocos.memory.episode（hub.episode）
- 状态：完整实现（归档逻辑不清除元素、无持久化）

`execution_manager.py`
- 文件类型：源码
- 文件核心功能：Agent 当前执行动作跟踪
- 内部关键类/函数/常量：ExecutionManager（begin/complete/cancel/is_executing/get_current_action/get_history/clear_history）
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/daemon/factory.py:106、tests/test_phase49c_skill_growth.py、tests/test_runtime_stages_wiring.py
- 状态：完整实现

`executive_controller.py`
- 文件类型：源码
- 文件核心功能：三阶段职责链（意图理解→策略→能力选择）+ 死循环/震荡/超时熔断
- 内部关键类/函数/常量：ExecutiveController（analyze_intent/formulate_strategy/select_capabilities/execute_chain/begin_cycle/record_phase/end_cycle/check_deadlock/check_oscillation/check_timeout/is_blocked/reset/get_stats）；CycleRecord/IntentAnalysis/Strategy/CapabilityPlan；MetaController 别名
- 导入依赖：ocos.logging
- 被哪些OCOS文件调用：meta_controller.py（别名）、decision_loop.py:12
- 状态：完整实现（_infer_capabilities 映射与 Intent 类型脱节，见风险清单）

`experience_store.py`
- 文件类型：源码
- 文件核心功能：结构化经验 <情境,动作,结果,反思> 记录与三种重放
- 内部关键类/函数/常量：ExperienceStore（record/replay_random/replay_recent/replay_important/get_stats/clear）；Experience
- 导入依赖：无
- 被哪些OCOS文件调用：agent_runtime.py:30（step9 兜底记录 + step10 重放）
- 状态：完整实现（id 生成可重复）

`goal_stack.py`
- 文件类型：源码
- 文件核心功能：6 级目标栈（可选 SQLite 自动同步）
- 内部关键类/函数/常量：GoalStack（push/pop/peek/get_active/get_highest_priority/cancel/depth/clear/restore_from_store/set_store/store property）
- 导入依赖：ocos.agent.goal_types、ocos.agent.goal_store（TYPE_CHECKING）
- 被哪些OCOS文件调用：ocos/daemon/factory.py:107、tests/test_phase49c_skill_growth.py
- 状态：完整实现

`goal_store.py`
- 文件类型：源码
- 文件核心功能：agent 层 Goal 表 SQLite 持久化
- 内部关键类/函数/常量：GoalSQLiteStore（initialize/save/load/load_active/delete/count_by_status/_row_to_goal）；_DDL；_domain_from_str
- 导入依赖：ocos.storage.connection、ocos.agent.goal_types、ocos.goal.models
- 被哪些OCOS文件调用：agent_runtime.py:37（经 _init_persistence）、tests/test_goal_claim.py
- 状态：完整实现（与 ocos/goal/store.py 双 schema 并存，注释已声明）

`goal_types.py`
- 文件类型：源码（兼容重导出）
- 文件核心功能：Phase 21 类型定义迁移后的兼容层
- 内部关键类/函数/常量：重导出 Goal/GoalLevel/GoalStatus/GoalOriginLevel/GoalAuthority/GoalSource/GoalDomain/SuccessCriteria/UserGoal/CALLER_WHITELIST
- 导入依赖：ocos.kernel.goal_types
- 被哪些OCOS文件调用：ocos/goal/factory.py:18、goal_stack.py、control_loop.py、tests/test_goal_origin_model.py、test_phase21_prompt2/3、test_phase38_5_rgv
- 状态：完整实现（纯转发）

`health_check.py`
- 文件类型：源码
- 文件核心功能：聚合式组件健康检查框架
- 内部关键类/函数/常量：HealthCheck（register/unregister/check_all/check_one；for_event_bus/for_engine_bridge/for_writer_engine 工厂）；ComponentCheck；HEALTHY/DEGRADED/UNHEALTHY/UNKNOWN 常量
- 导入依赖：ocos.events.event_bus
- 被哪些OCOS文件调用：agent_runtime.py:34、tests/test_health_check.py
- 状态：完整实现

`identity_anchor.py`
- 文件类型：源码
- 文件核心功能：身份锚点（core/anchor/self_view/state 四层，born_at 一生不变）
- 内部关键类/函数/常量：IdentityAnchor（verify/get_identity_id/get_name/set_anchor/update_self_view/set_state/to_dict/from_dict；born_at/created_at/owner_id property）
- 导入依赖：无
- 被哪些OCOS文件调用：identity_store.py、agent_runtime.py:35、tests/test_integration.py
- 状态：完整实现

`identity_store.py`
- 文件类型：源码
- 文件核心功能：IdentityAnchor SQLite 持久化 + Phase 34E 身份连续性快照表
- 内部关键类/函数/常量：IdentitySQLiteStore（initialize/close/save/load/exists/delete/save_snapshot/load_snapshot/connection）；_CREATE_TABLE_SQL/_SNAPSHOT_TABLE_SQL/_SNAPSHOT_KEEP=10
- 导入依赖：ocos.storage.connection、ocos.agent.identity_anchor
- 被哪些OCOS文件调用：agent_runtime.py:36（生产路径）
- 状态：完整实现（datetime.utcnow 弃用告警）

`intent.py`
- 文件类型：源码
- 文件核心功能：关键词表意图提取
- 内部关键类/函数/常量：Intent（extract/get_intent_type/get_intent_description/get_confidence/reset）；KNOWN_INTENTS
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/daemon/factory.py:108、tests/test_phase49c_skill_growth.py
- 状态：完整实现（master_agent._think_with_selector 以错误签名调用其 extract，见风险清单）

`interfaces.py`
- 文件类型：源码
- 文件核心功能：7 个 runtime_checkable Protocol 定义
- 内部关键类/函数/常量：IdentityAnchorProtocol/GoalStackProtocol/AttentionProtocol/IntentProtocol/WorkingMemoryProtocol/CapabilityManagerProtocol/ExecutionManagerProtocol
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/agent/__init__.py 导出
- 状态：完整实现（纯协议）

`knowledge_base.py`
- 文件类型：源码
- 文件核心功能：SPO 三元组内存知识库
- 内部关键类/函数/常量：KnowledgeBase（add/query/find_by_subject/find_by_object/find_relations/update_confidence/remove/search/clear）；KnowledgeTriple
- 导入依赖：无
- 被哪些OCOS文件调用：agent_runtime.py:29（仅 _extract_beliefs 写入，无读取方）、ocos/agent/__init__.py 导出
- 状态：完整实现（写入后无消费，半接线）

`learning_trigger.py`
- 文件类型：源码
- 文件核心功能：Episode 聚合 → PatternCandidate 写路径（零 LLM）
- 内部关键类/函数/常量：scan_for_patterns(hub,min_support=3,window=50)；_group_key/_observed_relation；PatternTriggerRecord
- 导入依赖：ocos.memory.hub、ocos.memory.pattern.models（延迟）
- 被哪些OCOS文件调用：tests/test_belief_consolidation.py；无生产调用方（master_agent._consolidate_episodes 内嵌 PatternExtractor 为平行实现）
- 状态：完整实现

`life_cycle_orchestrator.py`
- 文件类型：源码
- 文件核心功能：生命周期编排器（tick 驱动认知循环 + 疲劳检测自动睡眠）
- 内部关键类/函数/常量：LifeCycleOrchestrator（boot/shutdown/tick/_tick_idle/_tick_sleep/run_cycles/get_report）；TickResult
- 导入依赖：ocos.agent.state、ocos.agent.master_agent
- 被哪些OCOS文件调用：ocos/daemon/__init__.py:86（伴生层）
- 状态：完整实现（与生产注入的 CognitiveAttentionController 接口不匹配，见风险清单）

`lifecycle.py`
- 文件类型：源码
- 文件核心功能：线程安全双层状态机（宏观 LifecyclePhase + 微观 MicroState）
- 内部关键类/函数/常量：LifecycleManager（transition_to_phase/transition_micro/run_micro_cycle/freeze/force_idle/is_active/is_idle/lock）；LifecyclePhase；MicroState；PHASE_TO_STATUS
- 导入依赖：ocos.agent.state
- 被哪些OCOS文件调用：master_agent.py:31、control_loop.py:27、ocos/daemon/__init__.py:523、tests/test_phase22_prompt1/2
- 状态：完整实现

`master_agent.py`
- 文件类型：源码（核心，2929 行）
- 文件核心功能：认知主体核心——生命周期六方法 + 单权威目标 + 引擎桥 + dream 巩固管线 + 20+ Phase 管理器委托
- 内部关键类/函数/常量：MasterAgent（boot/wake/observe/think/_think_with_selector/_fallback_think/decide/act/_act_via_bridge/_dispatch_to_orchestrator/reflect/learn/_persist_learning/sleep/dream/_consolidate_episodes/_fast_path_learning/attach_memory_hub/attach_memory_recall/set_engine_bridge/set_world_abi/set_skill_registry/grow_skills_from_episodes/recall_context/world_context/maybe_proactive_output/tick/get_status_report/shutdown/_safe_return_to_idle + Phase AA-AK 委托方法群）；_DecisionWrapper；_CONSOLIDATION_BATCH_LIMIT=200/_BELIEF_INITIAL_CONFIDENCE=0.6/_BELIEF_STRENGTHEN_STEP=0.1/_PRUNE_CONFIDENCE_FLOOR=0.35
- 导入依赖：state/lifecycle/control_loop/cognitive_bridge/goal_types + ocos.goal.factory、ocos.goal.enforcer、ocos.kernel.abi、ocos.memory.belief.models/store、ocos.memory.pattern.extractor/models/store（及延迟导入 ocos.snapshot、ocos.proactive、ocos.learning.*、ocos.agent.wisdom_trigger、ocos.agent.continuity_trigger、ocos.security.manager、ocos.evolution.*、ocos.human.manager、ocos.reflection.manager、ocos.optimization.manager、ocos.persistence.manager、ocos.knowledge.synthesis_manager、ocos.planning.models）
- 被哪些OCOS文件调用：ocos/daemon/factory.py:109（build_master_agent）、agent_runtime.py:21、decision_loop.py:10、life_cycle_orchestrator.py:20、tests/test_master_agent_*（13 个文件）、test_integration、test_phase21_prompt3、test_phase22_prompt2、test_phase49b/49c、test_phase49_experience_learning
- 状态：完整实现（含 check_access/sanitize_input NameError、search_knowledge 重复定义、_recall_and_record 空实现等，见风险清单）

`memory_consolidation.py`
- 文件类型：源码
- 文件核心功能：Phase 24-D 压缩管道（ContextCompressor + AttentionDrivenRetrieval + MemoryConsolidationScheduler）
- 内部关键类/函数/常量：ContextCompressor（compress/_deduplicate；CHARS_PER_TOKEN=4/MIN_RETAIN=5）；AttentionDrivenRetrieval（retrieve/_extract_keywords/_relevance）；MemoryConsolidationScheduler（should_consolidate/consolidate；interval=100/low_peak_hours=(2,5)）；CompressionStats/RetrievalResult
- 导入依赖：ocos.logging
- 被哪些OCOS文件调用：无（grep 无外部引用）
- 状态：完整实现（未接线）

`memory_consolidator.py`
- 文件类型：源码
- 文件核心功能：三层记忆巩固流水线（working→episodic→long_term）
- 内部关键类/函数/常量：MemoryConsolidator（add_to_working/_consolidate/consolidate_to_long_term/schedule_consolidation/compact_expired/recall/get_stats/get_working_items/clear）；MemoryItem；MemoryLevel
- 导入依赖：ocos.logging
- 被哪些OCOS文件调用：agent_runtime.py:28（tick step3/9/10、sleep 恢复、shutdown）
- 状态：完整实现

`meta_controller.py`
- 文件类型：源码（兼容别名）
- 文件核心功能：Phase 22-D 重命名过渡层，指向 executive_controller
- 内部关键类/函数/常量：重导出 ExecutiveController/MetaController/CycleRecord/IntentAnalysis/Strategy/CapabilityPlan
- 导入依赖：ocos.agent.executive_controller
- 被哪些OCOS文件调用：agent_runtime.py:23
- 状态：完整实现（纯转发）

`metrics_collector.py`
- 文件类型：源码
- 文件核心功能：轻量级引擎指标收集（计数/成功率/延迟）
- 内部关键类/函数/常量：MetricsCollector（for_engine/measure/snapshot/reset_all）；EngineMetrics（record/avg_latency_ms/success_rate/to_dict/reset）；_MeasureContext；_SAMPLE_RATE_DEFAULT=0.1
- 导入依赖：无
- 被哪些OCOS文件调用：agent_runtime.py:33（实例化后未使用）、tests/test_metrics_collector.py
- 状态：完整实现（在 runtime 中为死对象）

`retry_policy.py`
- 文件类型：源码
- 文件核心功能：引擎调用重试（指数退避+抖动）与三态断路器
- 内部关键类/函数/常量：safe_execute；RetryPolicy（backoff_delay；max_retries/base_delay/max_delay/jitter/failure_threshold=5/half_open_timeout=30）；CircuitBreakerState（reset/to_dict）；CircuitState；CircuitBreakerOpenError
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/engines/writer_engine.py:23、tests/test_retry_policy.py
- 状态：完整实现

`self_evolution_link.py`
- 文件类型：源码
- 文件核心功能：自我升级提案接入 evolution 治理链（冻结域拒绝→沙箱→快照→迁移→回滚）
- 内部关键类/函数/常量：propose_upgrade/apply_approved/rollback/apply_self_upgrade/read_self_knowledge/_build_proposal/_write_backup；FORBIDDEN_MARKERS；_SELF_KNOWLEDGE/_BACKUP_FILE 路径常量
- 导入依赖：ocos.evolution.*（延迟）、ocos.logging
- 被哪些OCOS文件调用：ocos/interaction/converse.py:247,468,530,542,560、ocos/execution/bridge.py:620
- 状态：完整实现

`state.py`
- 文件类型：源码
- 文件核心功能：Agent 14 态状态机与合法转换矩阵
- 内部关键类/函数/常量：AgentState（transition/is_active/reset；status/previous property）；AgentStatus；VALID_TRANSITIONS
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/daemon/factory.py:110、lifecycle.py、master_agent.py、agent_runtime.py:32、tests/test_integration 等
- 状态：完整实现

`wisdom_trigger.py`
- 文件类型：源码
- 文件核心功能：dream 巩固期成败经验聚类→智慧候选→SQLite 落盘（CLS 慢通路）
- 内部关键类/函数/常量：consolidate_wisdom/load_wisdom_context/_wisdom_count；WISDOM_USER_ID="master"
- 导入依赖：ocos.personal_memory.pattern_interpreter/wisdom_store（延迟）、ocos.self.self_types、ocos.storage.connection、ocos.logging
- 被哪些OCOS文件调用：master_agent.py:1371（dream）、ocos/interaction/converse.py:349,431、tests/test_power_on_w1_w4.py
- 状态：完整实现（自愈建表幂等）

`working_memory.py`
- 文件类型：源码
- 文件核心功能：Agent 工作记忆（意识当前内容，容量 7，优先级淘汰）
- 内部关键类/函数/常量：AgentWorkingMemory（add/remove/clear/list_items/current_focus/capacity）；WorkItem
- 导入依赖：无
- 被哪些OCOS文件调用：ocos/agent/__init__.py 导出；生产装配实际注入 ocos.runtime.context_manager.WorkingMemory
- 状态：完整实现（非生产默认）


#### 审计分组 W2：capability 能力管理 + capability_reality 能力现实校验 —— 文件索引

### 第三部分：文件全量索引

（状态：完整实现 / 半成品 / 占位代码）

#### ocos/capability/
1. `ocos/capability/__init__.py`
   - 包门面 / Phase 45 导出与 CNS 边界声明 / 无类 / 依赖包内 7 模块 / 被 tests/test_phase45.py 调用 / 状态：完整实现（门面）
2. `ocos/capability/adapter.py`
   - 类型定义 / Phase 45 之前的早期 Adapter/AdapterStatus 数据结构（175 行，与 adapter_manager 分离的旧版抽象） / 内部关键类：Adapter 相关 dataclass / 无 OCOS 内部依赖 / 未见包外调用（grep 无 import 命中） / 状态：半成品（疑似被 adapter_manager 取代的早期版本，无消费方）【信息缺失：其内部类与 adapter_manager 的演进关系无文档】
3. `ocos/capability/adapter_manager.py`
   - 适配器管理 / 四类 ExecutorKind 标准适配器 + execute / AdapterManager / 依赖 capability_types、capability_router / 被 execution_bridge、tests 调用 / 状态：占位代码（三个适配器均为字符串拼接模拟）
4. `ocos/capability/agent_proxy.py`
   - Agent 代理层 / AgentRegistry+AgentInstance+invoke/update_config/update_capability+单例便捷函数 / 动态 import agents / 仅 tests 调用 / 状态：半成品（可用但硬编码路径、action 参数被忽略、无生产接线）
5. `ocos/capability/agents/__init__.py`
   - 子包门面 / 导出 5 个 Agent / 无 / 被 agent_runtime、agent_proxy（字符串）、CLI self 调用 / 状态：完整实现
6. `ocos/capability/agents/code_agent.py`
   - 子代理 / CodeAgent v1.1.0：ast 语法检查 + subprocess 沙盒执行 / 零 OCOS 依赖 / 被 agent_runtime、agent_proxy、tests 调用 / 状态：完整实现
7. `ocos/capability/agents/research_agent.py`
   - 子代理 / ResearchAgent：3 域模板模拟研究输出 / 零依赖 / 同上 / 状态：占位代码（自我声明 simulated，模板拼接）
8. `ocos/capability/agents/planner_agent.py`
   - 子代理 / PlannerAgent：领域检测+固定 5 步模板 / 零依赖 / 同上 / 状态：占位代码（模板规划器）
9. `ocos/capability/agents/self_modification_agent.py`
   - 子代理 / SelfModificationAgent：禁区校验+风险分析+diff+pytest+git commit / 零依赖 / 被 CLI self、agent_proxy、tests 调用 / 状态：半成品（diff 非 standard、git add . 过宽、非 dry_run 无人工确认通道）
10. `ocos/capability/agents/summarizer_agent.py`
    - 子代理 / SummarizerAgent：停用词+抽取式摘要 / 零依赖 / 同上 / 状态：完整实现
11. `ocos/capability/async_bridge.py`
    - 异步桥 / AsyncBridge+DispatchResult：gateway→engine_bridge→lifecycle / 依赖 permission_gateway / **无包外调用方** / 状态：半成品（validate 位置传参 bug、后台 loop 装饰性、死代码风险）
12. `ocos/capability/attention.py`
    - 注意力 / AttentionManager（Phase 30）+ CognitiveAttentionController（Phase 35）+ emit_report（Phase 36） / 依赖 ocos.logging、ocos.contracts.attention_abi / 被 agent_runtime、daemon/factory、tests 调用 / 状态：完整实现
13. `ocos/capability/calibration_store.py`
    - 校准存储 / CalibrationStore+CalibrationResult / 依赖 contracts.feedback_abi / **无包外调用方** / 状态：逻辑不完整（update_reliability 目标方法不存在，静默假成功）
14. `ocos/capability/capability_graph.py`
    - 层级图 / CapabilityGraph 静态层级 / 依赖 capability_types / 仅包门面+tests / 状态：半成品（children() 入参与数据不匹配的死接口）
15. `ocos/capability/capability_registry.py`
    - 能力注册 / CapabilityRegistry / 依赖 capability_types / 被 tool/manager.py、包内模块调用 / 状态：完整实现
16. `ocos/capability/capability_router.py`
    - 路由 / CapabilityRouter.route / 依赖 capability_types、capability_registry / 被 adapter_manager、tests / 状态：半成品（默认路由为模拟执行）
17. `ocos/capability/capability_selector.py`
    - 能力选择 / CapabilitySelector.select/select_by_tags / 依赖 capability_types、capability_registry / 仅门面+tests / 状态：完整实现（静态推演）
18. `ocos/capability/capability_types.py`
    - 类型 / 10 个 dataclass/Enum / 无依赖 / 被 tool/manager、包内、tests / 状态：完整实现
19. `ocos/capability/cognitive_coupling.py`
    - 耦合桥 / CognitiveCouplingBridge+CouplingConfig+CouplingMetrics / 依赖 ocos.logging / 被 cognitive_loop/loop_orchestrator、tests 调用 / 状态：半成品（对 capability 版 Homeostasis 的熵注入落空）
20. `ocos/capability/custom_agent_template.py`
    - 接入规范 / AgentProvider ABC / 无依赖 / 无调用方 / 状态：占位代码（纯规范文档化 ABC）
21. `ocos/capability/descriptor.py`
    - ABI 描述符 / CapabilityDescriptor+CapabilityCategory+CapabilityStatus / 无 OCOS 依赖 / 被 engine_bridge、registry、discovery 调用 / 状态：完整实现
22. `ocos/capability/discovery.py`
    - 能力发现 / CapabilityDiscovery.scan_engines/register_external_capability / 依赖 descriptor、provider、registry、ocos.platform.engine_manifest / 无包外调用 / 状态：完整实现（静态推演）
23. `ocos/capability/echo_agent.py`
    - 参考实现 / EchoAgent / 无依赖 / 被 agent_runtime、examples、tests / 状态：完整实现
24. `ocos/capability/evidence_pipeline.py`
    - 证据管道 / EvidencePipeline+EvidenceResult / 依赖 contracts.feedback_abi / **无任何调用方** / 状态：半成品（未接线）
25. `ocos/capability/execution_bridge.py`
    - 执行桥 / ExecutionBridge.execute/execute_batch+fail-closed 权限 / 依赖 capability_types、adapter_manager、permission_gateway / 仅门面+tests / 状态：完整实现（静态推演；注释中的超时控制未实现）
26. `ocos/capability/experience_memory.py`
    - 经验库 / CapabilityExperienceMemory（SQLite WAL） / 依赖 knowledge_graph.ExperienceNode、ocos.logging / 被 selection_engine、result_understanding、tests / 状态：完整实现
27. `ocos/capability/homeostasis.py`
    - 稳态 / HomeostasisManager+Regulator+6 Monitor+阈值+HealthReport / 依赖 ocos.kernel.goal_types、ocos.logging / 被 agent_runtime、daemon/factory、daemon/health_loop、attention/focus、ocos/homeostasis.py 门面、tests / 状态：完整实现
28. `ocos/capability/knowledge_graph.py`
    - 知识图谱 / KnowledgeGraph+3 Node+EdgeType+ResourceLimits / 无 OCOS 依赖 / 被 experience_memory(类型)、selection_engine、result_understanding、tests / 状态：完整实现
29. `ocos/capability/lifecycle_manager.py`
    - 生命周期 / LifecycleManager（能力级）+AgentLifecycleManager/AgentHandle/AgentState/ConnectMethod（ABI #9） / 依赖 capability_types、capability_registry / 被 async_bridge、tests / 状态：完整实现
30. `ocos/capability/meta_controller.py`
    - 元控制 / MetaController+MetaControllerConfig+Intervention / 依赖 models / 仅 skill_graph_executor 可选注入+tests / 状态：完整实现（静态推演）
31. `ocos/capability/models.py`
    - 数据模型 / Skill/SkillGraph/ProcessGraph/SkillExecutionRecord+CyclicDependencyError / 无依赖 / 被 skill_growth、包内 selector/executor/meta_controller/skill_registry、tests / 状态：完整实现
32. `ocos/capability/orchestrator.py`
    - 编排 / CapabilityOrchestrator+OrchestrationResult+DispatchResult / 方法内依赖 selection_engine / 被 ocos/orchestrator.py 门面、agent_runtime 调用 / 状态：完整实现（timeout 未实现）
33. `ocos/capability/outcome_evaluation.py`
    - 五维评估 / OutcomeEvaluator+WEIGHTS+evaluate_feedback / 依赖 contracts.feedback_abi / 被 result_understanding、tests / 状态：完整实现（reliability 键名缺陷）
34. `ocos/capability/permission_gateway.py`
    - 权限网关 / PermissionGateway+GatewayResult+CallerIdentity+AuditEntry+PermissionDeniedError / 依赖 ocos.logging / 被 agent_runtime、async_bridge、execution_bridge、tests / 状态：完整实现
35. `ocos/capability/provider.py`
    - ABI 描述符 / ProviderDescriptor+ProviderType+ProviderStatus / 无依赖 / 被 engine_bridge、discovery、registry / 状态：完整实现
36. `ocos/capability/registry.py`
    - 平面注册表 / CapabilityRegistry（线程安全）/ 依赖 descriptor、provider、ocos.logging / 被 engine_bridge、discovery、tests / 状态：完整实现（list_providers 类型过滤缺失）
37. `ocos/capability/result_interpreter.py`
    - 结果解释 / ResultInterpreter / 依赖 capability_types / 仅门面+tests / 状态：完整实现（静态推演；被 Phase 26 实质取代）
38. `ocos/capability/result_understanding.py`
    - 结果理解 / ResultUnderstandingLayer+ResultUnderstanding+ExaminationResult+StructuredResult+ProcessedResult / 依赖 constitution.statement_validator、contracts.feedback_abi、outcome_evaluation、knowledge_graph / 被 agent_runtime、orchestrator、tests / 状态：完整实现
39. `ocos/capability/selection_engine.py`
    - 选择引擎 / SelectionEngine+SelectionConfig+SelectionResult / 依赖 knowledge_graph、experience_memory、ocos.logging / 被 orchestrator、tests / 状态：完整实现
40. `ocos/capability/selector.py`
    - Intent 映射 / CapabilitySelector+SelectorResult（Phase 23） / 依赖 models / 仅 tests / 状态：半成品（关键词匹配初版，无生产接线）
41. `ocos/capability/skill_graph_executor.py`
    - 执行器 / SkillGraphExecutor / 依赖 models；cognitive_bridge 仅 TYPE_CHECKING / 仅 tests / 状态：完整实现（静态推演）
42. `ocos/capability/skill_registry.py`
    - Skill 存储 / SkillRegistry / 依赖 models / 仅 tests / 状态：完整实现（静态推演）

#### ocos/capability_reality/
43. `ocos/capability_reality/__init__.py`
    - 包门面 / CR55 原则 + 15 符号导出 / 依赖包内 7 模块 / 生产按子模块路径 import / 状态：完整实现
44. `ocos/capability_reality/adapter_discovery.py`
    - 环境发现 / AdapterDiscovery+DiscoveryReport / 依赖 adapter_fs/adapter_shell/capability_registry/adapter_types / 被 execution/bridge、tool/manager、interaction/converse、daemon/repair_link、tests / 状态：完整实现（network 维度未实现）
45. `ocos/capability_reality/adapter_fs.py`
    - 文件适配器 / FilesystemAdapter（read/write/list/stat/exists + safe_roots 沙盒） / 依赖 capability_adapter、adapter_types / 被 adapter_discovery、tests、下游主链路 / 状态：完整实现（startswith 越权缺陷）
46. `ocos/capability_reality/adapter_shell.py`
    - Shell 适配器 / ShellAdapter（shell_exec + 危险命令黑名单 + workdir 沙盒） / 依赖同上 / 同上 / 状态：完整实现（黑名单易绕过）
47. `ocos/capability_reality/adapter_types.py`
    - 类型 / 8 个 dataclass/Enum / 无 OCOS 依赖 / 被包内全部、execution/bridge、tests / 状态：完整实现（4 个死配置字段）
48. `ocos/capability_reality/capability_adapter.py`
    - 基类 / CapabilityAdapter（execute 模板+健康检查+validate+register_to） / 依赖 adapter_types / 被 fs/shell 继承、tests / 状态：完整实现
49. `ocos/capability_reality/capability_registry.py`
    - 注册表 / CapabilityRegistry+RegisteredCapability / 依赖 adapter_types / 被 discovery、selector、execution/bridge、tool/manager、repair_link、converse、tests / 状态：完整实现
50. `ocos/capability_reality/capability_selector.py`
    - 选择器 / CapabilitySelector+SelectionResult / 依赖 adapter_types、capability_registry / 仅 tests / 状态：完整实现（http_get/code_exec 目标默认不存在）
51. `ocos/capability_reality/capability_validator.py`
    - 验证器 / CapabilityValidator+ValidationResult+ValidationDecision / 依赖 adapter_types / 仅 tests / 状态：半成品（完整实现但未接入执行链路；NEEDS_REVIEW 无审批通道）


#### 审计分组 W3：interaction 对外网关层（API/CLI/对话） —— 文件索引

#### 二、文件全量索引（66 文件一条不漏）

> 格式：文件 / 类型 / 核心功能 / 关键成员 / OCOS 内部导入依赖 / 被调用方 / 状态。"—"表示无 OCOS 内部依赖或无内部调用者（仅测试/入口）。

**顶层（17 文件）**

`ocos/interaction/__init__.py`
- 包初始化 / Phase 53 主动交互系统对外门面，导出 16 符号 / 导出列表 __all__ / interaction_types, need_monitor, attention_trigger, interaction_scheduler, interaction_validator / 外部以 `from ocos.interaction import ...` 使用（实际生产仅测试） / 状态：完整实现

`ocos/interaction/__main__.py`
- 入口 / `python -m ocos.interaction` 启动 TUI / main() / ocos.interaction.tui / 用户直接执行 / 状态：完整实现（注意：包级 -m 入口直接进 TUI 而非 CLI）

`ocos/interaction/base.py`
- 基础抽象 / GoalRequest→UserGoal 适配、InteractionSession、PermissionGuard 权限闸门 / ALLOWED_ACTIONS(8)/FORBIDDEN_ACTIONS(6)/GoalRequest.create/to_user_goal/verify_permission/InteractionSession.record_goal/record_query/summary/PermissionGuard.check / ocos.constitution.behavioral, ocos.goal.models, ocos.logging / api/routes/goal.py, plan.py, memory.py, belief.py, trace.py, quality.py；cli/commands/{goal,plan,memory,belief,trace}.py；repl/commands/{plan,memory,belief,goal,self_cmd,trace,help}.py；repl/shell.py；repl/commands/approvals.py(仅 Session)；cli/commands/{say,status,organ,decide,regulate,feedback,restart,growth}.py(仅 InteractionSession)；ocos/execution/bridge.py / 状态：完整实现

`ocos/interaction/channel.py`
- 外部交互通道 / 多通道输出管理（log/callback/webhook/broadcast）+健康统计 / ChannelType, ChannelStatus, ChannelConfig, ChannelHealth, BaseChannel, LogChannel, CallbackChannel, WebhookChannel, BroadcastChannel, ExternalInteraction(send/send_broadcast/get_stats) / —（纯标准库） / 仅 ocos/tests/test_external_interaction.py / 状态：完整实现（生产未接线）

`ocos/interaction/cognitive_interface.py`
- 统一认知入口 / InputAdapter 基类 + CLIAdapter/APIAdapter + CognitiveInterface.stimulate→事件注入→唤醒 / InputAdapter, CLIAdapter, APIAdapter, CognitiveInterface._inject_to_runtime/_wake_if_needed/get_recent_history / ocos.logging, ocos.interaction.stimulus / ocos/cognitive_interface.py（顶层 shim） / 状态：完整实现（依赖 runtime 私有属性，脆弱）

`ocos/interaction/stimulus.py`
- 数据模型 / Stimulus/StimulusType/StimulusResult / StimulusType.from_str, Stimulus.is_command/is_text / — / cognitive_interface.py / 状态：完整实现

`ocos/interaction/context.py`
- Store 注入器 / InteractionContext 只读接入 EpisodeStore/BeliefStore/IdentityBoundary + 便捷查询 / ensure_episode_store/ensure_belief_store/ensure_identity/query_memory/query_beliefs/identity_summary/close/create_inmemory_context/create_persistent_context / ocos.memory.episode.store, ocos.memory.belief.store, ocos.self.identity_boundary, ocos.memory.belief.models / cli/main.py, repl/shell.py, converse.py(经 local import) / 状态：完整实现（默认 ":memory:" 与 REPL 相对路径 "ocos.db" 有漂移隐患）

`ocos/interaction/converse.py`
- 对话回复引擎（本层最大文件 1226 行）/ ChatResponder + USE| 动作协议 + 目标编译器 + 内视 + 自我迭代 / _SYSTEM_PROMPT, _parse_use_lines, _strip_use_lines, _fs_read, make_default_tool_executor, ChatResponder{build_context,build_introspection,self_improve,respond,respond_auto,compile_goal,_remember_conversation,_recall_context,_find_duplicate_goal,_goal_note_from_goal,_daemon_alive,_session_goal_context} / ocos.logging, ocos.interaction.context + 20+ 延迟 import（memory.hub, goal.store, execution.*, agent.*, engines.text_generator, personal_intelligence, learning.persistence, world_model, event_memory, capability_reality, interaction.conversation_state 等） / ocos/daemon/__init__.py, api/routes/converse.py / 状态：完整实现（含大量 FIX 补丁痕迹；fs 路径硬编码 /home/laogao）

`ocos/interaction/conversation_state.py`（未提交新文件）
- 会话状态机持久层 / 每 session 一行对话状态，SQLite 跨进程共享 / ConversationStateStore{get,update(clear_current 语义: current→last)}, conversation_state 表 DDL 自愈 / —（标准库 sqlite3） / converse.py（respond_auto task 受理写、question/continue 恢复读）、tests/test_conversation_state.py（根目录，8 条全过） / 状态：完整实现（update 无事务、异常静默 debug）

`ocos/interaction/session_state.py`
- 进程内会话管理 / SessionManager 单例 + ChatTurn/SessionState + episodes 重放 + 文件锁防多实例 / SessionState.recent_context/add_turn, SessionManager.ensure_session/append_turn/_restore_history/_persist_to_hub/acquire_lock/release_lock / ocos.memory.hub, ocos.memory.episode.models（延迟） / ocos/daemon/__init__.py:133 / 状态：完整实现（RLock 修复注释 FIX-VAL1；与 converse 双写记忆）

`ocos/interaction/inbox.py`
- 用户消息收件箱 / user_messages 表 DDL 自愈 + legacy 列升级 + 跨进程消息通道 / UserInbox{post,drain,list_recent,get,reply,wait_for_reply,post_outbound,list_outbound_after,max_rowid,count_queued} / ocos.storage.connection / ocos/daemon/factory.py:115, ocos/daemon/__init__.py:153, cli/commands/say.py, api/routes/converse.py / 状态：完整实现

`ocos/interaction/interaction_types.py`
- Phase 53 类型 / NeedSignal/InteractionCandidate/InteractionConfig/InteractionHistory + 4 枚举 / NeedSignal.is_urgent, InteractionCandidate.{is_expired,acknowledge,ignore,withdraw,mark_sent}, InteractionHistory.acknowledge_rate / — / need_monitor, attention_trigger, interaction_scheduler, interaction_validator, __init__ / 状态：完整实现

`ocos/interaction/need_monitor.py`
- 需求监控器 / 规则扫描产出 NeedSignal + 目标/系统健康登记 / NeedMonitor.scan/register_rule/update_goal_health/update_system_health/get_stale_goals, _rule_goal_stale, _rule_health_warning, create_default_rules / interaction_types / __init__、tests/test_phase53.py / 状态：完整实现（生产未接线）

`ocos/interaction/attention_trigger.py`
- 注意力过滤 / urgency→优先级映射 + 用户活跃/响应率降级 / AttentionTrigger.evaluate/_urgency_to_priority/_adjust_for_user_state/update_user_activity / interaction_types / __init__、test_phase53.py / 状态：完整实现（时区适配仅注释）

`ocos/interaction/interaction_scheduler.py`
- 发送调度器 / 队列+速率限制+冷却+去重+过期撤回+优先级出队 / submit/dequeue/withdraw/acknowledge/ignore/_can_send/_clean_expired/get_state / interaction_types / __init__、test_phase53.py / 状态：完整实现（内存队列）

`ocos/interaction/interaction_validator.py`
- 发送前验证 / IS53-01/02 关键词 REJECT + 命令式语气 FLAG / InteractionValidator.validate, ValidationVerdict, SendValidationResult / interaction_types / __init__、test_phase53.py / 状态：完整实现（生产未接线）

`ocos/interaction/tui.py`
- TUI / Textual 聊天界面 + SessionStore 持久化 + 斜杠命令 + outbox 轮询 / API_BASE, SESSION_DB, COMMANDS(20), SessionStore, InputArea, ChatScreen, _strip_markdown, _redirect_console_logs, run_tui / httpx/textual/rich + ocos.logging.formatter（可选） / cli/commands/chat.py, interaction/__main__.py / 状态：完整实现

**api/（12 文件）**

`ocos/interaction/api/__init__.py` — 包初始化（1 行 docstring）/ 状态：占位
`ocos/interaction/api/server.py` — FastAPI 应用工厂 / app 定义(docs/redoc 挂 /ocos/*)、health_check、8 router 注册、ui_root 重定向、ui_page 静态页、main() uvicorn / HealthResponse, APIResponse / ocos.interaction.api.models + 8 routes / ocos/external/server_manager.py:306 / 状态：完整实现
`ocos/interaction/api/models.py` — pydantic 模型 / GoalDomainAPI, GoalStatusAPI, GoalCreateRequest, PlanRequest, MemoryQueryRequest, BeliefQueryRequest（未被路由使用，死模型）, APIResponse, GoalResponse, PlanResponse, MemoryResponse, BeliefResponse, SelfStatusResponse（无使用方）, TraceResponse, HealthResponse / — / 各 routes / 状态：完整实现（BeliefQueryRequest/SelfStatusResponse 冗余）
`ocos/interaction/api/routes/__init__.py` — 包初始化（1 行）/ 状态：占位
`ocos/interaction/api/routes/goal.py` — goal 路由 / POST /ocos/goal（创建，不落库）、GET /ocos/goal/{id}（TBD）/ DOMAIN_MAP, _STATUS_MAP / goal.models, kernel.goal_types, api.models, base / server.py / 状态：半成品（创建不持久化、查询占位）
`ocos/interaction/api/routes/plan.py` — plan 路由 / POST /ocos/plan（真实 TaskDecomposer 分解返回 plan_steps，不落 plan_dag）/ 同上映射 / planning.decomposer, planning.strategy（延迟） / server.py / 状态：完整实现（规划本身真实）
`ocos/interaction/api/routes/memory.py` — memory 路由 / POST /ocos/memory/query（永远空结果 TBD）/ — / api.models, base / server.py / 状态：占位代码
`ocos/interaction/api/routes/belief.py` — belief 路由 / GET /ocos/belief（空结果 TBD）/ — / api.models, base / server.py / 状态：占位代码
`ocos/interaction/api/routes/trace.py` — trace 路由 / GET /ocos/trace/{id}（空结果 TBD）/ — / api.models, base / server.py / 状态：占位代码
`ocos/interaction/api/routes/chat.py` — WebChat 路由 / POST /ocos/chat（意图解析：writing→MasterAgent 决策；execute→OrganClient.generate；task_status→OrganClient.task；talk→引导语）/ _CHAT_SESSIONS（进程内会话）, _parse_intent, _extract_title, _extract_genre, _extract_task_id, _organ_base_url / opentale_bridge.master_agent, opentale_bridge.organ_client（延迟） / server.py、tests/test_webchat_api.py / 状态：完整实现（会话 dict 无淘汰，内存泄漏）
`ocos/interaction/api/routes/quality.py` — 质量路由 / POST /ocos/quality/chapter、POST /ocos/quality/trend / ChapterQualityRequest, TrendAnalysisRequest / opentale_bridge.quality_analyzer, trend_analyzer（延迟） / server.py / 状态：完整实现
`ocos/interaction/api/routes/converse.py` — UX-P2 数据面路由 / 9 端点（converse/summary/outbox/introspect/self-improve/goals-from-chat/approvals×3）/ _db, _decide / interaction.cli.paths, interaction.converse, interaction.inbox, goal.store, execution.pending, execution.bridge（延迟） / server.py、tui.py（HTTP 客户端） / 状态：完整实现（不经 PermissionGuard）

**cli/（20 文件）**

`ocos/interaction/cli/__init__.py` — 包初始化（1 行）/ 状态：占位
`ocos/interaction/cli/__main__.py` — `python -m ocos.interaction.cli` 入口 / 状态：完整实现
`ocos/interaction/cli/main.py` — 命令分发 / main()（InteractionSession + InteractionContext + 19 个命令分支；含重复 run 死分支） / cli.commands.*（延迟 import 部分） / pyproject console-script、cli/__main__.py / 状态：完整实现（含死代码）
`ocos/interaction/cli/parser.py` — argparse 定义（404 行）/ build_parser + 12 个 _add_*_parser / — / cli/main.py / 状态：完整实现（growth 帮助与实现漂移；chat --port 8900）
`ocos/interaction/cli/paths.py` — DB 路径单一来源 / DEFAULT_DB, resolve_db_path / — / cli 多个命令、api/routes/converse.py / 状态：完整实现
`ocos/interaction/cli/commands/__init__.py` — 包初始化（1 行）/ 状态：占位
`ocos/interaction/cli/commands/goal.py` — goal create/exec/status/list / cmd_goal_create（真实落 GoalStore）、cmd_goal_exec（GoalDirectExecutor 沙盒执行）、cmd_goal_status、cmd_goal_list / goal.models, base, goal.store, paths, execution.goal_executor / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/plan.py` — ocos plan / cmd_plan（分解+save_plan_dag 落库）、_detect_domain（关键词域检测，与 repl/commands/plan.py 重复实现） / goal.models, base, planning.*, goal.store, paths / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/memory.py` — memory query/recent / cmd_memory_query, cmd_memory_recent / base, context / cli/main.py / 状态：完整实现（仅检索 decision 字段前 120 字符内的子串）
`ocos/interaction/cli/commands/belief.py` — belief list/summary / cmd_belief_list, cmd_belief_summary / base, context / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/say.py` — say/inbox / cmd_say（post + 可选 wait_for_reply）、cmd_inbox / base, paths, interaction.inbox / cli/main.py、repl/commands/ops.py / 状态：完整实现
`ocos/interaction/cli/commands/status.py` — 一屏总览 / cmd_status（goals/pending_actions/episodes/belief/pattern/knowledge/plan_dag/user_messages 直查 SQLite） / base, paths / cli/main.py、repl/commands/ops.py / 状态：完整实现
`ocos/interaction/cli/commands/approvals.py` — 审批 / cmd_approvals_list/approve/deny（PendingStore + DecisionBridge 诚实执行：无 handler → blocked 可见） / execution.pending, execution.bridge, paths / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/run.py` — daemon 启动 / cmd_run（ensure_schema → build_master_agent → ResidentRuntime + DecisionBridge/感知管线/健康体检挂载 → 信号优雅停机；OCOS_TICK_BUDGET 默认 15） / daemon.factory, daemon.ResidentRuntime, perception.file_sensor, storage.migrations, paths / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/self.py` — self 子命令 / cmd_self 路由 + status/identity/review/mod/validate/preview（SelfModificationAgent dry-run 默认；_find_project_root 硬编码兜底路径 /home/laogao/...） / capability.agents.self_modification_agent, reflection.self_review, paths / cli/main.py / 状态：完整实现（preview 子命令不可达；硬编码路径）
`ocos/interaction/cli/commands/trace.py` — trace show（TBD 占位，仅打印 note）/ cmd_trace_show / base / cli/main.py / 状态：占位代码
`ocos/interaction/cli/commands/organ.py` — OpenTale 器官驱动 9 子命令 / cmd_organ_{generate,resume,rewrite,verify,status,projects,task,accept,reject} + _wait_and_report / opentale_bridge.organ_client / cli/main.py / 状态：完整实现（依赖外部 Organ API）
`ocos/interaction/cli/commands/decide.py` — 写作决策 / cmd_decide + _exec_generate（MasterAgent 决策→可选 Organ 提交） / opentale_bridge.master_agent, organ_client / cli/main.py / 状态：完整实现（依赖外部 API）
`ocos/interaction/cli/commands/regulate.py` — 自调节 / cmd_regulate（TrendAnalyzer→ContractAdjustment→人工确认→rewrite）/ SelfRegulationLoop / opentale_bridge.self_regulation, organ_client / cli/main.py / 状态：完整实现（依赖外部 API）
`ocos/interaction/cli/commands/feedback.py` — 评审反馈回流 / cmd_feedback（FeedbackReflux.collect_and_store → ~/.ocos/feedback/<project>.json）/ opentale_bridge.feedback_reflux / cli/main.py / 状态：完整实现（依赖外部 API）
`ocos/interaction/cli/commands/restart.py` — 系统重启 / cmd_restart, cmd_gateway + systemd 封装（_systemctl/_unit_exists/_wait_active/_port_ready/_append_log JSONL） / base（InteractionSession）/ cli/main.py / 状态：完整实现（systemd 专属）
`ocos/interaction/cli/commands/chat.py` — TUI 启动 / cmd_chat → run_tui / interaction.tui / cli/main.py / 状态：完整实现
`ocos/interaction/cli/commands/growth.py` — 成长模块 5 子命令 / _make_engine（openai 包预检）、cmd_growth_ingest/analyze/execute（**stub**）/status/grow / growth.engine, base, engines.text_generator / cli/main.py / 状态：execute 为半成品，其余完整

**repl/（14 文件）**

`ocos/interaction/repl/__init__.py` — 包初始化（1 行）/ 状态：占位
`ocos/interaction/repl/__main__.py` — `python -m ocos.interaction.repl` 入口 / 状态：完整实现
`ocos/interaction/repl/shell.py` — cmd.Cmd 交互壳 / OcosShell（intro/prompt/10 个 do_* /precmd 剥 `/`/default→plan/exit 摘要） / base, context, repl.commands.* / repl/__main__.py / 状态：完整实现（DB 路径漂移见风险）
`ocos/interaction/repl/completer.py` — Tab 补全 / REPL_COMMANDS, COMMAND_DESCRIPTIONS, complete_command, complete_path, ReplCompleter / — / 无（死代码）/ 状态：完整实现但从未挂接
`ocos/interaction/repl/commands/__init__.py` — 包初始化（1 行）/ 状态：占位
`ocos/interaction/repl/commands/approvals.py` — /approvals / ReplApprovalsCommand.execute（list/approve/deny + 诚实执行） / base, execution.pending, execution.bridge / repl/shell.py / 状态：完整实现
`ocos/interaction/repl/commands/belief.py` — /belief [domain] / ReplBeliefCommand / base, context / repl/shell.py / 状态：完整实现
`ocos/interaction/repl/commands/goal.py` — /goal [id] / ReplGoalCommand（GoalStore 同源） / base, goal.store / repl/shell.py / 状态：完整实现
`ocos/interaction/repl/commands/help.py` — /help / ReplHelpCommand（help_text 8 条） / base / repl/shell.py / 状态：完整实现（无 /approvals /status /say 细项帮助）
`ocos/interaction/repl/commands/memory.py` — /memory / ReplMemoryCommand / base, context / repl/shell.py / 状态：完整实现（帮助文档写了 query 过滤，实际忽略参数只列最近 10 条——文档漂移）
`ocos/interaction/repl/commands/ops.py` — /status /say / ReplStatusCommand, ReplSayCommand（SimpleNamespace 复用 CLI cmd） / base, cli.commands.status, cli.commands.say / repl/shell.py / 状态：完整实现
`ocos/interaction/repl/commands/plan.py` — /plan + default / ReplPlanCommand（创建 Goal + 分解展示，**不落库**——与 CLI plan 落 plan_dag 不同）、_detect_domain / goal.models, base, planning.* / repl/shell.py / 状态：半成品（目标不持久化，退出即失）
`ocos/interaction/repl/commands/self_cmd.py` — /self / ReplSelfCommand（identity_summary） / base, context / repl/shell.py / 状态：完整实现
`ocos/interaction/repl/commands/trace.py` — /trace（TBD 占位）/ ReplTraceCommand / base / repl/shell.py / 状态：占位代码

---


#### 审计分组 W4：runtime 认知运行时 + runtime_scheduler 调度器 —— 文件索引

#### 二、文件全量索引

`ocos/runtime/__init__.py`
- 包入口 / 声明 Phase 39.3 包导出面（21 个符号）/ RuntimeKernel, TickPipeline, RecoveryManager, CapabilityPolicyProvider 等 / 本包内 12 个模块 / daemon、tests / 完整实现

`ocos/runtime/__main__.py`
- 演示入口 / `python -m ocos.runtime`：boot→60 tick→checkpoint→shutdown / main() / runtime_kernel / 无 / 完整实现（演示级）

`ocos/runtime/runtime_kernel.py`
- 引擎 / 心跳引擎，生命周期 + Pipeline 编排 + checkpoint 决策执行 / RuntimeKernel / checkpoint,recovery_engine,lifecycle,pipeline,capability_policy,runtime_state,tick / daemon、tests / 完整实现（恢复回灌不完整）

`ocos/runtime/runtime_loop.py`
- 引擎 / 主循环抽象层（线程/异步双模、指标、hook）/ LoopState, LoopMetrics, RuntimeLoop, create_runtime_loop / 无 / tests（生产未接线）/ 完整实现

`ocos/runtime/tick.py`
- 模型 / 不可变心跳帧 + tick_id 生成器 / Tick(frozen), tick_id_generator / 无 / runtime_kernel、__init__ / 完整实现

`ocos/runtime/pipeline_protocol.py`
- 协议 / 8 阶段冻结顺序枚举 + TickStage Protocol / PipelineStage(.next), TickStage / tick_context / pipeline、stages、tests / 完整实现

`ocos/runtime/tick_context.py`
- 数据载体 / frozen TickContext + with_updates/with_stage_trace/to_dict / TickContext, create_tick_context / 无 / pipeline、stages、tests / 完整实现（to_dict 仅计数摘要）

`ocos/runtime/pipeline.py`
- 编排器 / 8 stage 固定顺序执行 + agent driver 注入 + PipelineError 包装 / TickPipeline, PipelineError, STAGE_ORDER / pipeline_protocol, stages, tick_context / runtime_kernel、tests / 完整实现

`ocos/runtime/stages/__init__.py`
- 包入口 / 导出 8 Stage，声明 GAP-P2-2 全真实现与降级语义 / 8 个 Stage 类 / stages 各文件 / pipeline / 完整实现

`ocos/runtime/stages/event_ingestion.py`
- Stage① / EventBus 积压事件 drain（需 ingest API）/ EventIngestionStage / pipeline_protocol, tick_context / pipeline / 完整实现（缺省空转）

`ocos/runtime/stages/attention.py`
- Stage② / 注意力焦点选择（scoring+collector）/ AttentionStage / pipeline_protocol, tick_context（TYPE_CHECKING: ocos.attention.*）/ pipeline、tests / 完整实现（stage 持有 _current_state，违反无状态约束）

`ocos/runtime/stages/memory_sync.py`
- Stage③ / MemoryHub get_stats 快照转发 / MemorySyncStage / pipeline_protocol, tick_context / pipeline / 完整实现（缺省空转）

`ocos/runtime/stages/goal_maintenance.py`
- Stage④ / Goal 健康维护（只 refresh 禁 create）/ GoalMaintenanceStage / pipeline_protocol, tick_context / pipeline、tests / 完整实现（progress/attention 注入口无生产调用方）

`ocos/runtime/stages/execution_check.py`
- Stage⑤ / TaskDAG.resolve_ready 候选 + PermissionGateway 过滤 / ExecutionCheckStage / pipeline_protocol, tick_context, permission / pipeline / 完整实现（REQUIRE_APPROVAL 静默丢弃候选）

`ocos/runtime/stages/result_collection.py`
- Stage⑥ / ExecutionManager.get_history 只读转发 / ResultCollectionStage / pipeline_protocol, tick_context / pipeline / 完整实现（缺省空转）

`ocos/runtime/stages/learning_trigger.py`
- Stage⑦ / 学习信号触发 / LearningTriggerStage / pipeline_protocol, tick_context / pipeline / **占位代码**（signals 恒为 ()）

`ocos/runtime/stages/checkpoint_decision.py`
- Stage⑧ / tick_id % 10 == 0 周期 checkpoint 决策 / CheckpointDecisionStage / pipeline_protocol, tick_context / pipeline / 完整实现（策略硬编码）

`ocos/runtime/checkpoint.py`
- 持久化 / Runtime 自身 checkpoint（JSON+SHA-256）/ CheckpointRecord, CheckpointEngine / 无 / recovery_engine, runtime_kernel, tests / 完整实现

`ocos/runtime/runtime_state.py`
- 模型 / 5 态生命周期枚举 + 冻结转移表 / RuntimeState, ALLOWED_TRANSITIONS / 无 / lifecycle, runtime_kernel, recovery_engine, tests / 完整实现（SAFE_MODE/DEGRADED 无触发点）

`ocos/runtime/lifecycle.py`
- 控制 / 状态转移校验 + shutdown 请求 / LifecycleManager, InvalidTransitionError / runtime_state / runtime_kernel, tests / 完整实现

`ocos/runtime/recovery_engine.py`
- 控制器 / 39.1 ABI 门面 → 39.4 RecoveryManager 双写 checkpoint+snapshot / RecoveryEngine, RecoveryResult / checkpoint, recovery.recovery_manager, runtime_state / runtime_kernel, __init__, tests / 完整实现（认知状态回灌缺失）

`ocos/runtime/recovery/__init__.py`
- 包入口 / 导出 14 个恢复符号 / RecoveryManager 等 / 子包各模块 / recovery_engine, tests / 完整实现

`ocos/runtime/recovery/recovery_manager.py`
- 编排 / 快照/事件/账本/审批/恢复统一入口 / RecoveryManager / 子包各模块 / recovery_engine / 完整实现（**shutdown 双定义 L124/L200，后者丢 _save_ledger**）

`ocos/runtime/recovery/runtime_snapshot.py`
- 持久化 / 认知状态矢量快照 + 存储（保留 20 个）/ RuntimeSnapshot, SnapshotReason, SnapshotStore / 无 / recovery_manager, tests / 完整实现

`ocos/runtime/recovery/integrity_verifier.py`
- 校验 / 恢复前 4 项一致性检查 / IntegrityVerifier, IntegrityReport / event_replay, execution_recovery, permission_recovery, runtime_snapshot / recovery_manager, cognitive_restore / 完整实现（strict 形参闲置）

`ocos/runtime/recovery/cognitive_restore.py`
- 恢复引擎 / Load→Verify→Restore→Resume 六步恢复 / CognitiveStateRestore, RestoreResult / event_replay, execution_recovery, integrity_verifier, permission_recovery, runtime_snapshot / recovery_manager / 完整实现

`ocos/runtime/recovery/event_replay.py`
- 持久化 / Event Sourcing 最小实现（JSONL append-only + 重放引擎）/ EventType, CognitiveEvent, EventLog, EventReplayEngine / 无 / recovery_manager, integrity_verifier, cognitive_restore / 完整实现（无生产 handler）

`ocos/runtime/recovery/execution_recovery.py`
- 持久化 / 执行账本防重复执行 / ExecutionStatus, ExecutionRecord, ExecutionLedger / 无 / recovery_manager, cognitive_restore / 完整实现

`ocos/runtime/recovery/permission_recovery.py`
- 持久化 / 待审批队列持久化（pending.json）/ ApprovalStatus, PendingApproval, ApprovalStore / 无 / recovery_manager, cognitive_restore / 完整实现

`ocos/runtime/permission/__init__.py`
- 包入口 / 导出 9 个权限符号 / BuiltinPolicies, PermissionGateway 等 / 子包各模块 / capability_policy, stages.execution_check, tests / 完整实现

`ocos/runtime/permission/permission_level.py`
- 模型 / L0-L3 权限级别 + 操作映射表 / PermissionLevel, OPERATION_LEVELS / 无 / builtin_policies, permission_request, tests / 完整实现

`ocos/runtime/permission/permission_request.py`
- 模型 / 不可变请求 + 认知上下文载体 / RiskLevel, Caller, PermissionRequest, PermissionContext / permission_level / gateway, trace, builtin_policies, tests / 完整实现

`ocos/runtime/permission/policy_decision.py`
- 模型 / ALLOW/DENY/REQUIRE_APPROVAL 判定原子结果 / DecisionResult, PolicyDecision / 无 / gateway, trace, builtin_policies, capability_policy, tests / 完整实现

`ocos/runtime/permission/builtin_policies.py`
- 策略 / 6 级优先级规则引擎 + 13 项能力注册表 / BuiltinPolicies / permission_level, permission_request, policy_decision / gateway, capability_policy, tests / 完整实现（注册表与 OPERATION_LEVELS 不同步）

`ocos/runtime/permission/permission_gateway.py`
- 网关 / evaluate 主入口 + 审计缓冲 / PermissionGateway, PermissionTraceConsumer / builtin_policies, permission_request, permission_trace, policy_decision / capability_policy, stages.execution_check, tests / 完整实现（trace 缓冲无上限）

`ocos/runtime/permission/permission_trace.py`
- 模型 / 不可变审计链记录 / PermissionTrace / policy_decision, permission_request / gateway, tests / 完整实现

`ocos/runtime/capability_policy.py`
- 桥梁 / Runtime↔Governance 策略提供者（check/is_allowed）/ CapabilityPolicyProvider / permission 包 / runtime_kernel（构造未调用）、tests / 完整实现（生产闲置）

`ocos/runtime/context_manager.py`
- B1 / WorkingMemory + Context 组装 + 事件自动重建 / WorkingMemory, Context, ContextManager / kernel.abi, events.event_bus, models.execution, models.process, logging / engines/* 全系、agent.engine_bridge、15+ 测试 / 完整实现

`ocos/runtime/goal_runtime.py`
- Phase 18 引擎 / Goal 事件驱动生命周期（9 事件/过期/Superseding）/ GoalRuntimeEngine, RuntimeResult(frozen), _make_event / kernel.abi, events.event_bus, models.goal, context_manager, logging / tests / 完整实现

`ocos/runtime/decision_runtime.py`
- Phase 18 引擎 / Decision 状态机（PROPOSED→COMMITTED→EXECUTED）/ DecisionRuntimeEngine, RuntimeResult / kernel.abi, events.event_bus, context_manager, logging / tests / 完整实现（尾部延迟 import dataclasses）

`ocos/runtime/execution_runtime.py`
- Phase 18 引擎 / Execution 状态机 + 超时检查 / ExecutionRuntimeEngine, RuntimeResult / kernel.abi, events.event_bus, models.execution, context_manager, logging / tests / 完整实现

`ocos/runtime/process_runtime.py`
- Phase 18 引擎 / TransformProcess 状态机（本地转移表）/ ProcessRuntimeEngine, RuntimeResult / kernel.abi, events.event_bus, models.process, context_manager, logging / tests / 完整实现

`ocos/runtime/attention_engine.py`
- B2 / Observation 三维注意力评分（novelty/relevance/urgency）/ AttentionEngine, AttentionScore, ContentAnalyzer, DefaultContentAnalyzer, FrequencyAnalyzer / kernel.abi, logging（延迟 import context_manager） / attention/focus.py（生产）、tests / 完整实现

`ocos/runtime/scheduler.py`
- B3 / tick 内事件分发优先级调度器 / ScheduleType, ScheduleItem, EngineInfo, RegistryAdapter, Scheduler / kernel.abi, events.event_bus, logging / tests / 完整实现（PERIODIC 间隔失效、CONDITIONAL 未实现求值）

`ocos/runtime/policy_engine.py`
- B4 / PolicyRule 规则引擎（12 算子）+ 5 条默认安全策略 + 治理事件联动 / PolicyEffect, RuleOperator, PolicyRule, Policy, PolicyResult, PolicyEngine / kernel.abi, events.event_bus, logging / tests / 完整实现（规则异常 fail-open）

`ocos/runtime/resource_manager.py`
- B5 / 五类资源池分配/释放/配额/TTL 回收 / ResourceType, ResourceUsage, ResourceSlot, ResourceRequestResult, ResourceQuota, ResourceManager / kernel.abi, logging / tests（生产未接线）/ 完整实现（emit API 不匹配 P1-2）

`ocos/runtime/adaptive_control.py`
- B6 / 运行时参数自适应调节（降级/缓慢恢复/冷却）/ RuntimeParam, AdaptiveConfig, Adaptation, RiskLevel, AdaptiveController / kernel.abi, logging / tests（生产未接线）/ 完整实现（emit API 不匹配 P1-2）

`ocos/runtime_scheduler/__init__.py`
- 包入口 / Phase 51.2 导出面 + RS51 边界契约声明 / 11 符号 / 包内 7 模块 / daemon（PriorityQueue、SchedulerTask）、tests / 完整实现

`ocos/runtime_scheduler/scheduler_types.py`
- 模型 / Priority/Tick/SchedulerTask/TickSchedule/SchedulerStatus/SchedulerStats/Worker/BackpressureState / 上述类型 / 无 / 包内全部、daemon、tests / 完整实现

`ocos/runtime_scheduler/cognitive_clock.py`
- 时钟 / tick 单调推进 + 周期任务调度判定 / CognitiveClock / scheduler_types / task_scheduler, tests / 完整实现

`ocos/runtime_scheduler/priority_queue.py`
- 队列 / heapq 优先队列（FIFO tiebreaker）/ PriorityQueue / scheduler_types / task_scheduler, daemon, tests / 完整实现

`ocos/runtime_scheduler/task_scheduler.py`
- 主循环 / 周期任务收集→背压→串行执行→重试→checkpoint / TaskScheduler / scheduler_types, cognitive_clock, priority_queue / tests / 完整实现（未接 WorkerManager/BackpressureManager）

`ocos/runtime_scheduler/backpressure.py`
- 保护 / 优先级分级背压（CRITICAL/HIGH 放行、MEDIUM 推迟、LOW/BG 拒绝）/ BackpressureManager / scheduler_types / tests / 完整实现（drain_deferred 占位返回 []）

`ocos/runtime_scheduler/worker_manager.py`
- 隔离 / per-stage Worker 记账 + 超时标记 / WorkerManager / scheduler_types / tests / 完整实现（纯记账，无真实隔离；TaskScheduler 未消费）

`ocos/runtime_scheduler/scheduler_health.py`
- 监控 / tick 连续性/队列/时延/失败率健康报告 / SchedulerHealth / scheduler_types / tests / 完整实现

---


#### 审计分组 W5：engines 认知引擎 + decision 决策 + planning 规划 + cognitive_loop 认知循环 —— 文件索引

#### 二、文件全量索引

**ocos/engines/（18 文件）**

`ocos/engines/__init__.py`
- py 包初始化 / 声明 engines 为认知引擎包，统一 re-export 4 个引擎 manifest（C.5）/ 常量：无 / OCOS 内导入：consolidation/retrieval/planning/writer 四引擎的 `__manifest__` / 被调用：EngineDiscoverer 扫描 ocos.engines / 状态：完整实现

`ocos/engines/address_resolver.py`（118 行）
- py 模块 / 跨 Store 路由层：namespace→resolver_fn 映射，强制 UniversalAddress，不拥有数据 / 类：AddressResolver（register/unregister/resolve/has_namespace/list_namespaces/route_query）、Query dataclass（type: by_role|by_state|all，results 可变字段 hash=False）/ 依赖：ocos.models.information、ocos.logging、ocos.platform.engine_manifest / 被调用：retrieval_engine、test_address_resolver / 状态：完整实现（route_query 将 Query 传给 address 型 resolver 存在类型双关，见 P4-04）

`ocos/engines/consolidation_engine.py`（268 行）
- py 模块 / 多条 Information 合并为 KnowledgeCandidate / 类：ConsolidationEngine（consolidate/propose_candidate/_merge_content/_emit）；常量：_MIN_SOURCES=2、_ROLE_TO_LEVEL / 依赖：kernel.abi、knowledge_abi、knowledge_ontology、models.information / 被调用：test_consolidation_engine、EngineDiscoverer / 状态：完整实现（目标层级推断用字符串比较，P2-01）

`ocos/engines/decision_making_engine.py`（318 行）
- py 模块 / ProcessType.DECISION 能力引擎：选项评分/排序/选择 / 类：DecisionMakingEngine（execute/get_trace/list_traces/clear_traces/_resolve_strategy/_evaluate/_default_evaluate）、RuntimeResult；函数：register_decision_strategy、make_decision；全局：_STRATEGY_HANDLERS；默认 3 个硬编码候选选项 / 依赖：kernel.abi、events.event_bus、models.process、models.decision_making、runtime.context_manager / 被调用：daemon/factory.py:159（decision_engine）、test_decision_making_engine / 状态：完整实现（三策略为占位退化，P4-01）

`ocos/engines/forgetting_engine.py`（251 行）
- py 模块 / TTL 策略 + 过期收集 + 遗忘执行（PERSISTENT 需 Governance 审批）/ 类：ForgettingEngine（set/get_ttl_policy/reset_ttl_defaults/is_expired/collect_expired/mark_for_forget/forget/approve_forget/reject_forget）；常量：_DEFAULT_TTL{TRANSIENT:30s, PERSISTENT:86400s, STABLE/IMMUTABLE:0}；_pending 待批表 / 依赖：kernel.abi、models.information / 被调用：test_forgetting_engine、test_semantic_operations_only.py:122 / 状态：完整实现（仅发事件不真正删数据，依赖消费方）

`ocos/engines/goal_arbitration_engine.py`（293 行）
- py 模块 / ProcessType.ARBITRATION 冲突目标仲裁 / 类：GoalArbitrationEngine（arbitrate/execute/get_trace 等）、RuntimeResult；内置 4 仲裁器：_priority（priority 升序 1 最高）、_weighted（weight×(1-cost×0.1)）、_emergency（urgency 降序）、_resource_aware（priority/(1+cost) 升序）；register_default_arbitrator / 依赖：events.event_bus、kernel.abi、runtime.context_manager、models.goal_arbitration、models.process / 被调用：test_goal_arbitration_engine / 状态：完整实现（ArbitrationResult.candidate_id 每次随机 uuid，trace 不可复现）

`ocos/engines/learning_engine.py`（214 行）
- py 模块 / ProcessType.LEARNING：注入 learn_fn 的领域无关学习 / 类：LearningEngine（learn/update/execute/get_model/list_models/get_trace 等）、RuntimeResult；LearnFn 类型别名 / 依赖：events.event_bus、kernel.abi、runtime.context_manager、models.learning、models.process / 被调用：daemon/factory.py:160、test_learning_engine、test_phase49_experience_learning / 状态：完整实现（learn_fn 异常不捕获不发射完成事件，P4-06）

`ocos/engines/narrative_pipeline.py`（291 行）
- py 模块 / Narrative Contract → Policy 推导 + Budget 约束应用（Blend/Override/Inject 三覆盖模式）/ 函数：derive_policy、apply_budget_constraints、_chapter_base_intensity、_chapter_pacing_by_progress、_chapter_emotion_target、_derive_ending_type、_derive_pov_type、_derive_emotion_profile；常量：_DEFAULT_PACING_TYPES、_INTENSITY_FACTOR、_DEFAULT_INTENSITY=0.5 / 依赖：ocos.logging / 被调用：writer_engine.py:24、test_narrative_pipeline / 状态：完整实现（无 manifest，不作为独立引擎加载）

`ocos/engines/planning_engine.py`（267 行）
- py 模块 / ProcessType.PLANNING 能力引擎 / 类：PlanningEngine（execute/get_trace/list_traces/clear_traces/_resolve_strategy/_execute_strategy/_default_plan）、RuntimeResult；register_planning_strategy / 依赖：kernel.abi、events.event_bus、models.process、models.planning、runtime.context_manager / 被调用：agent/engine_bridge.py:109（ENGINE_REGISTRY["planner"]）、daemon/factory.py:161、test_planning_engine / 状态：完整实现（默认规划为固定步数模板，depends_on 生成式冗余 P5-02）

`ocos/engines/policy_engine.py`（328 行）
- py 模块 / ProcessType.POLICY 策略符合性评估 / 类：PolicyEngine（add_rule/add_rules/remove_rule/list_rules/clear_rules/execute/get_trace 等/_resolve_rules/_evaluate_rule/_default_evaluate）、RuntimeResult；register_rule_evaluator；无规则时回退 3 条演示规则（quality_minimum/cost_threshold/risk_tolerance）/ 依赖：kernel.abi、events.event_bus、models.process、models.policy、runtime.context_manager / 被调用：test_policy_engine / 状态：完整实现（未知比较运算符 fail-open 放行，P3-02）

`ocos/engines/prediction_engine.py`（190 行）
- py 模块 / 预测引擎（复用 ProcessType.REASONING，4 不堆叠原则）/ 类：PredictionEngine（predict/execute/get_trace 等）、RuntimeResult；PredictFn 类型 / 依赖：events.event_bus、kernel.abi、runtime.context_manager、models.prediction、models.process / 被调用：test_prediction_engine / 状态：完整实现（predict_fn 必须外部注入，本体为框架）

`ocos/engines/promotion_engine.py`（334 行）
- py 模块 / 信息晋升知识平面桥接 + Governance 审批 / 类：PromotionEngine（check_promotion/promote/approve_promotion/reject_promotion/_emit）；_ROLE_TO_LEVEL、_GOVERNANCE_GATED_LEVELS={PRINCIPLE,POLICY}、_pending / 依赖：kernel.abi、knowledge_abi、knowledge_ontology、promotion_rules、models.information / 被调用：test_promotion_engine、test_semantic_operations_only.py:113（私有常量） / 状态：完整实现（promote 末尾 else 分支重复赋值死代码 P5-01；事件声明 VALIDATED→DEPRECATED 但不真正改存储）

`ocos/engines/reasoning_engine.py`（320 行）
- py 模块 / ProcessType.REASONING 推理能力引擎（DEDUCTION/INDUCTION/ABDUCTION/ANALOGY/ANALYSIS/SYNTHESIS/COMPARISON/EVALUATION）/ 类：ReasoningEngine（execute/get_trace 等/_resolve_operations/_execute_step/_default_reason/_default_confidence）、RuntimeResult；register_inference_handler / 依赖：kernel.abi、events.event_bus、models.process、models.reasoning、runtime.context_manager / 被调用：agent/engine_bridge.py:117、daemon/factory.py:162、test_reasoning_engine / 状态：完整实现（默认推理为结构化占位输出，无真实推理）

`ocos/engines/reflection_engine.py`（191 行）
- py 模块 / 反思引擎（复用 REASONING process type）/ 类：ReflectionEngine（reflect/execute/get_trace 等）、RuntimeResult；ReflectFn 类型 / 依赖：events.event_bus、kernel.abi、runtime.context_manager、models.reflection、models.process / 被调用：daemon/factory.py:163、test_reflection_engine / 状态：完整实现（reflect_fn 外部注入）

`ocos/engines/retrieval_engine.py`（164 行）
- py 模块 / 跨角色语义查询：by_role/by_state/all，每次查询发射 INFORMATION_QUERIED / 类：RetrievalEngine（query/query_by_role/query_by_state/query_all/_emit_query_event）/ 依赖：address_resolver、kernel.abi、models.information / 被调用：test_retrieval_engine、test_semantic_operations_only / 状态：完整实现（TypeError 视为 resolver 非 QueryHandler 并跳过——按约定设计）

`ocos/engines/simulation_engine.py`（233 行）
- py 模块 / ProcessType.SIMULATION 情景推演（注入 step_fn）/ 类：SimulationEngine（run/run_monte_carlo/execute/get_trace 等）、RuntimeResult；StepFn 类型；dataclasses_replace 辅助 / 依赖：events.event_bus、kernel.abi、runtime.context_manager、models.simulation、models.process / 被调用：test_simulation_engine / 状态：完整实现（monte_carlo 未做参数扰动 P4-02）

`ocos/engines/text_generator.py`（599 行）
- py 模块 / LLM 叙事文本生成抽象层 / 类：LLMProvider(ABC)、MockProvider（结构化占位章节，解析 prompt 关键行）、AnthropicProvider（硬编码 claude-sonnet-4-20250514）、OpenaiProvider（兼容 DeepSeek，配置优先级 参数>env>~/.ocos/config.json llm 段）、FailoverProvider（P3-429 主备故障转移，CancelledError/KeyboardInterrupt 透传不转投）、PromptBuilder（SYSTEM/CHAPTER/REWRITE 模板）、TextGenerator（_auto_provider/generate_chapter/generate_rewrite）；GenerationResult dataclass；get_text_generator() 模块级实例缓存（P3-2）；_read_llm_config/_read_llm_fallback_config/_read_config_block / 依赖：ocos.logging / 被调用：writer_engine、execution/bridge.py:942,1048、interaction/converse.py、reflection/self_review.py:367、interaction/cli/commands/growth.py:36、test_text_generator / 状态：完整实现（无 manifest；_auto_provider 读全局配置文件导致测试环境耦合 P3-01；代理环境变量 pop/restore 非线程安全 P4-03）

`ocos/engines/writer_engine.py`（664 行）
- py 模块 / Phase 27 叙事写作引擎（plan/generate/resume/rewrite/status 五策略，重试+断路器）/ 类：WriterEngine（execute/_do_plan/_do_generate/_do_resume/_do_rewrite/_do_status/_delegate_to_opentale/_pick_chapter_focus/_distribute_scenes/_pick_conflict/_emit、circuit_state/trace_count/last_trace 属性）、WriterTrace（to_dict）、RuntimeResult / 依赖：kernel.abi、events.event_bus、models.process、runtime.context_manager、agent.retry_policy（safe_execute/CircuitBreakerState/RetryPolicy/CircuitBreakerOpenError）、engines.narrative_pipeline、engines.text_generator / 被调用：agent/engine_bridge.py:125（ENGINE_REGISTRY["writer"]）、test_writer_engine / 状态：完整实现（_opentale_system 永远为 None → opentale 路径必失败 P2-02；asyncio.run 嵌套风险 P4-05）

**ocos/decision/（8 文件）**

`ocos/decision/__init__.py`（75 行）
- 包初始化 / Phase 43 定位自述 + 决策流水线文档 + 统一导出 18 个符号 / 被调用：cognitive_loop/decision_pipeline.py、test_phase43 / 状态：完整实现

`ocos/decision/decision_types.py`（284 行）
- py 模块 / 核心类型定义（全部 frozen dataclass）/ 类/枚举：DecisionContext（is_empty 属性）、OptionType（do_nothing/direct_action/delegate/investigate/defer）、DecisionOption（option_id/description/confidence/expected_outcome/prerequisites/risk_score/value_score/source/evidence）、RiskCategory×6、RiskLevel×5、RiskAssessment、ValueDimension×6、ValueEvaluation（weighted_score）、DecisionState×7、DecisionProposal（recommended 按 value-risk 排序、is_ready）、DecisionTrace、DecisionResult / 依赖：无（纯标准库）/ 被调用：decision 包内全部模块 / 状态：完整实现

`ocos/decision/context_builder.py`（78 行）
- py 模块 / 决策上下文聚合（Goal/Self/Wisdom/World/Constraints → DecisionContext）/ 类：ContextBuilder（set_goal_context/set_self_context/add_wisdom/set_world_context/add_constraint/build/reset）/ 依赖：decision_types / 被调用：decision_pipeline.py:73 / 状态：完整实现

`ocos/decision/option_generator.py`（84 行）
- py 模块 / 从上下文生成候选选项（基线 defer + wisdom 推断 + investigate）/ 类：OptionGenerator（generate/_baseline_defer/_from_wisdom/_investigate_option；max_options=10）/ 依赖：decision_types / 被调用：decision_pipeline.py:81 / 状态：完整实现（defer 基线恒优 P4-07）

`ocos/decision/risk_engine.py`（73 行）
- py 模块 / 单选项主要风险评估 / 类：RiskEngine（assess/assess_all/_analyze/_score_to_level；risk_threshold=0.7 声明但未使用）/ 依赖：decision_types / 被调用：decision_pipeline.py:85 / 状态：完整实现（risk_threshold 字段为死配置）

`ocos/decision/value_model.py`（97 行）
- py 模块 / 六维价值评估（SAFETY>.25/ALIGNMENT .20/RELIABILITY .20/EFFICIENCY .15/LEARNING .10/NOVELTY .10）/ 类：ValueModel（evaluate/evaluate_all/_score_dimensions/_weighted）/ 依赖：decision_types / 被调用：decision_pipeline.py:86 / 状态：完整实现

`ocos/decision/decision_trace.py`（49 行）
- py 模块 / 决策审计追踪器 / 类：DecisionTracer（record/get；trace_id="trace:{proposal_id}"）/ 依赖：decision_types / 被调用：decision_pipeline.py（_tracer） / 状态：完整实现（record 时 discarded 恒传 []，淘汰理由未记录 P5-03）

`ocos/decision/decision_validator.py`（104 行）
- py 模块 / 决策边界守卫（D43 三边界 + 空提案/超风险）/ 类：Violation 枚举×5、DecisionValidationResult、DecisionValidator（validate/_looks_like_goal/_looks_like_execution；max_risk_threshold=0.9；中英触发词启发式）/ 依赖：decision_types / 被调用：decision_pipeline.py:58 / 状态：完整实现（启发式可绕过，代码自知）

**ocos/planning/（6 文件）**

`ocos/planning/__init__.py`（28 文档 + 导出 7 符号）
- 包初始化 / Phase 27 声明 + 导入规则（✅goal/memory/capability，❌self）/ 仅导出 models 内容 / 状态：完整实现

`ocos/planning/models.py`（239 行）
- py 模块 / 数据模型 / 常量：MAX_DAG_DEPTH=5、MAX_PARALLEL_WIDTH=4、VALID_AGENT_TYPES(frozenset×7)、_TRANSITIONS 状态机；类：TaskStatus（is_terminal/can_transition_to）、Task（frozen，__post_init__ 强校验，create 工厂）、TaskDAG（RLock 线程安全；add_task/add_edge/validate_acyclic/topological_order/parallel_groups）、ExecutionStrategy、Plan（frozen）/ 依赖：无 OCOS 内部依赖 / 被调用：orchestration/engine.py:34、agent/master_agent.py:827、agent/agent_runtime.py:944、agent_orchestration/*、collaboration、planning 包内其它模块 / 状态：完整实现

`ocos/planning/decomposer.py`（118 行）
- py 模块 / Goal→TaskDAG 纯规则分解 / 类：TaskDecomposer（4 域模板 WRITING 5 步/ANALYSIS 3 步/RESEARCH 3 步/DEVELOPMENT 3 步；decompose/_init_templates/_enforce_budgets）/ 依赖：ocos.goal.models（GoalDomain, UserGoal）、planning.models / 被调用：agent/agent_runtime.py:929、orchestration/engine、test_execution_bridge / 状态：完整实现（模板全串行）

`ocos/planning/plan_validator.py`（352 行）
- py 模块 / 计划验证 + 模拟执行（validate/simulate 双模式合一）/ 类：ValidationSeverity、ValidationIssue、PlanValidationReport（errors/warnings 属性、add_error/add_warning/summary）、PlanValidator（validate/simulate/_run_checks/_check_dag_structure/_check_capability_coverage/_check_dependencies/_simulate_topological_order/_detect_cycle DFS 环检测带路径返回）；函数：validate_plan（Plan 级 Gate，GAP-P3-6 并入）、validate_no_self_module（空占位）/ 依赖：planning.models / 被调用：orchestration/engine、agent_orchestration / 状态：完整实现（DAG-01 空图用 warning 却置 valid=False P5-04）

`ocos/planning/simulator.py`（124 行）
- py 模块 / Plan 执行模拟（死锁/预算/时长/风险）/ 类：SimulationResult（plan_id/success/total_steps/estimated_duration/warnings/deadlock_detected/risks）、PlanSimulator（simulate/_estimate_duration：SEQUENTIAL 全加、PARALLEL 取 max、PRIORITY_DRIVEN 逐层 max 加总）/ 依赖：planning.models / 被调用：orchestration 相关 / 状态：完整实现（空 DAG + PARALLEL 时 max() 抛 ValueError P4-08）

`ocos/planning/strategy.py`（66 行）
- py 模块 / 执行策略选择 / 类：StrategyEngine（select/explain/validate_parallel_width）/ 依赖：planning.models / 被调用：orchestration/engine / 状态：完整实现

**ocos/cognitive_loop/（10 文件）**

`ocos/cognitive_loop/__init__.py`（74 行）
- 包初始化 / AUD-F13 定位裁决自述（备用引擎，生产走 AgentRuntime+DecisionBridge）+ 四条 CL46 边界 + 导出 17 符号 / 状态：完整实现

`ocos/cognitive_loop/loop_types.py`（133 行）
- py 模块 / 循环类型 / 类：LoopPhase×8、TickOutcome×7、LoopContext（12 组字段）、HealthSignal×4、ModuleHealth、CognitiveHealthReport（is_healthy/needs_attention 属性）/ 依赖：无 / 被调用：cognitive_loop 全包、autonomous_loop.py:17 / 状态：完整实现

`ocos/cognitive_loop/perception_bridge.py`（99 行）
- py 模块 / 感知桥：外部信号→标准化 PerceptionEvent 入队（不判真假 CL46-03）/ 类：PerceptionMode×4、PerceptionEvent（frozen；is_trusted_source=confidence>0.7）、PerceptionBridge（receive/pending_events/mark_processed/flush_processed/event_count）/ 依赖：无 / 被调用：loop_orchestrator、attention_coordinator、autonomous_runtime / 状态：完整实现（flush 不清未处理事件 P3-03）

`ocos/cognitive_loop/attention_coordinator.py`（99 行）
- py 模块 / 注意力协调：感知事件(0.9)>活跃目标(0.7)>默认 idle(0.3)，只调焦点不建 Goal / 类：AttentionFocus、AttentionCoordinator（evaluate/_apply/current/weight/recent_focus_history；历史保 100→截 50）/ 依赖：perception_bridge、loop_types / 被调用：loop_orchestrator / 状态：完整实现

`ocos/cognitive_loop/context_synchronizer.py`（78 行）
- py 模块 / 上下文同步：4 个 provider 回调注入（Self/Wisdom/World/Goals）→ LoopContext；build_decision_context 聚合字符串 / 类：ContextSynchronizer（set_*_provider/sync/build_decision_context）/ 依赖：loop_types / 被调用：loop_orchestrator / 状态：完整实现（默认无 provider → 全占位；provider 异常无兜底 P3-04）

`ocos/cognitive_loop/decision_pipeline.py`（133 行）
- py 模块 / 循环决策阶段：GAP-P1-1 已接 ocos.decision 真实组件链 / 类：DecisionPipeline（process/_generate_proposal/record_decision/recent_decisions/last_proposal；ContextBuilder→OptionGenerator→RiskEngine+ValueModel→value-risk 排序→DecisionProposal→DecisionValidator→DecisionTracer）/ 依赖：loop_types、ocos.decision / 被调用：loop_orchestrator.py:50 / 状态：完整实现（self_summary 硬编码"agent current state" P5-05；discarded 选项不记录）

`ocos/cognitive_loop/action_controller.py`（69 行）
- py 模块 / 行动控制器：approved 决策 → Capability 调用（链路占位，selector/bridge 可注入 Phase 45）/ 类：ActionOutcome×5、ActionController（set_selector/set_bridge/act/has_capabilities）/ 依赖：loop_types / 被调用：loop_orchestrator.py:51 / 状态：半成品（act() 未接真实执行器时直接模拟返回 f"[{capability}] response to: ..."，代码自注"模拟"）

`ocos/cognitive_loop/learning_coordinator.py`（113 行）
- py 模块 / 学习协调：Result→Interpret→ValidateBounds(禁词)→ValidateQuality→Experience（CL46-04）/ 类：ConsolidationResult×4、LearningCoordinator（consolidate/_interpret/_validate_bounds/_validate_quality/_record_experience/recent_experiences；_FORBIDDEN_LEARNING 6 条禁词；日志保 1000→截 500）/ 依赖：loop_types / 被调用：loop_orchestrator.py:52 / 状态：完整实现（禁词表英文下划线归一化后匹配中文条目"我决定改变自己的核心"永不命中，P5-06）

`ocos/cognitive_loop/health_monitor.py`（198 行）
- py 模块 / 认知健康监控：Memory(>5000 警告/>10000 告警)/Attention(>0.95 或 <0.1)/Capability(<0.5 降级)/Decision(consistency<0.6 警告/<0.3 告警)，ALLOWED_REPAIRS×7 / FORBIDDEN_REPAIRS×5（CL46-02）/ 类：HealthMonitor（check/_check_memory/_check_attention/_check_capabilities/_check_decision/_assess_overall/propose_repair/latest_report/all_metrics/is_healthy；历史保 200→截 100）/ 依赖：loop_types / 被调用：loop_orchestrator.py:53 / 状态：完整实现（capability/decision 检查项依赖外部传入指标，默认空/1.0 恒正常）

`ocos/cognitive_loop/loop_orchestrator.py`（194 行）
- py 模块 / 认知循环主编排：7 阶段 tick + Phase 62d 耦合桥 poll + 循环统计 / 类：LoopOrchestrator（inject_coupling_bridge/tick/_tick_outcome/current_tick/recent_contexts/recent_outcomes/all_phases_active/health_report/loop_summary）/ 依赖：loop_types + 本包 6 组件 / 被调用：autonomous_runtime/autonomous_loop.py:16、test_phase46、test_phase62d_loop_coupling、test_thin_coverage_e2e / 状态：完整实现（tick 无异常兜底 P2-03；HEALTH_ALERT 分支 context 被追加且提前 return，跳过 outcome 判定 P5-07）


#### 审计分组 W6：memory 记忆 + personal_memory 个人记忆 + event_memory 事件记忆 + knowledge 知识图谱 —— 文件索引

#### 二、文件全量索引

（"被调用"列仅列审计范围外的 OCOS 文件；包内互相调用不重复列。状态：完整=完整实现，半成品=功能可用但有明确缺口，占位=转发/壳。）

##### ocos/memory/（33 文件）
`ocos/memory/__init__.py`
- __init__ / 仅 re-export MemoryRecall、RecallResult、ConflictGroup / 无 / 无（自引用 import ocos.memory.recall，包内循环写法）/ 被 agent/master_agent.py 等 via ocos.memory.recall / 完整（写法不规范）
`ocos/memory/hub.py`
- 主模块 / MemoryHub 统一持久化中枢：4 Store 生命周期 + 共享 WAL db_path + get_stats / MemoryHub / ocos.memory.episode|belief|semantic|pattern.store / 被 interaction/converse.py、agent/agent_runtime.py、agent/belief_system.py、agent/belief_consolidation.py、agent/learning_trigger.py、agent/adaptive_params.py、interaction/session_state.py、attention/retrieval.py、extension/integration_engine.py、runtime/stages/*、interaction/cli/commands/run.py、tests 多个 / 完整（get_stats 缺 semantic_count）
`ocos/memory/recall.py`
- 主模块 / MemoryRecall 跨会话召回引擎 + bi-gram 相关性过滤 + 同义词扩展 + 动态阈值 + recall_cognitive 结构化输出（ConflictGroup）/ RecallResult、ConflictGroup、MemoryRecall / 无（ duck-typing 访问 hub 属性）/ 被 engagement/manager.py、interaction/converse.py、agent/agent_runtime.py、agent/master_agent.py、initiative/true_initiative.py、opentale_bridge/master_agent.py、living_test/day2_memory_survival.py / 半成品（experience 召回依赖不存在的 hub.experience，恒空）
`ocos/memory/episode/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/memory/episode/models.py`
- 模型 / Episode frozen dataclass（EPI-{date}-{uuid8}，What/How/Result/Why 四元组 + significance_score + evaluation_trace 可审计 + EpisodeStatus active/archived/consolidated）/ Episode、EpisodeStatus / 无 / 被 gate.py、lessons.py、pattern/extractor.py、episode/store.py / 完整
`ocos/memory/episode/store.py`
- 存储 / episodes 表 DDL（5 索引含 json_each tag 查询）+ save 幂等（按 experience_id）/ EpisodeStore / ocos.storage.connection、episode.models / 被 hub.py、gate.py、lessons.py、sleep_dream（mark_consolidated 注释指向 P2-C dream）、tests / 完整
`ocos/memory/episode/gate.py`
- 桥接 / episode_from_decision（GateDecision→Episode 映射，trace 构建可审计）+ EpisodeGate.process 一条链 / EpisodeGate / experience.models、significance.models|evaluator、episode.models|store / 被 tests/test_phase49*.py、test_power_on_w1_w4.py / 完整
`ocos/memory/belief/__init__.py`
- __init__ / 定义第二个同名 Belief dataclass（statement/confidence/source/metadata），创建时经 ocos.constitution.StatementValidator 硬拦截 4 类违规声明，软违规置信度减半 / Belief、BeliefValidationError / ocos.constitution.statement_validator / 被外部 `from ocos.memory.belief import Belief` 路径 / 半成品（与 belief/models.Belief 同名冲突，双模型并存）
`ocos/memory/belief/models.py`
- 模型 / Belief（BLF-{date}-{uuid8}，confidence/uncertainty [0,1] 强校验，confidence>0 必须有证据）+ Evidence（EVD-{uuid8}，quality/consistency [0,1]）+ weaken/invalidate/archive 不可变转换 / Belief、Evidence、BeliefStatus / 无 / 被 store.py、confidence.py、evidence.py、validator.py、agent/belief_system.py / 完整
`ocos/memory/belief/store.py`
- 存储 / belief 表 DDL（含 json_extract(scope,$.domain) 函数索引）+ save 幂等 INSERT OR REPLACE + weaken/invalidate/archive + query_by_status/confidence/domain/lineage / BeliefStore / ocos.storage.connection、belief.models / 被 hub.py、agent/belief_consolidation.py、tests / 完整（query_by_lineage 用 LIKE %id% 有误匹配风险）
`ocos/memory/belief/confidence.py`
- 引擎 / ConfidenceEngine 五维计算（quality²加权/一致性方差惩罚 0.3 cap/30 天半衰期衰减/容量饱和 15/反例惩罚）+ ConfidenceConfig 权重和=1 校验 + ConfidenceResult 审计维度 / ConfidenceEngine、ConfidenceConfig、ConfidenceResult / belief.models / 被 evidence.py、agent/belief_consolidation.py / 完整
`ocos/memory/belief/evidence.py`
- 绑定 / EvidenceBinding：Knowledge+Evidence→Belief（min_evidence=3、min_quality=0.5 合同）+ rebind（证据不足→weaken，invalidated→invalidate） / BindingConfig、EvidenceBinding / belief.models、semantic.models、confidence / 被 agent/belief_system.py、belief/validator.py（仅类型）、tests / 完整（rebind 返回 None 语义含混：仍需更新时返回 None 而非原 belief）
`ocos/memory/belief/validator.py`
- 校验 / BeliefValidator 三重审核（Schema 字段白名单 / Evidence 数量与质量+ID 数量一致性 / Boundary 第一人称·身份归因·行为准则中英禁用语）/ BeliefValidator / belief.models、belief.evidence / 被 tests/test_phase61a_belief.py 等 / 完整
`ocos/memory/semantic/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/memory/semantic/models.py`
- 模型 / KnowledgeEntry（KNW-{date}-{uuid8}，第三人称 + source_patterns 只增证据链 + supersede 版本链 revision+1）+ KnowledgeScope（domain/preconditions/limitations/counterexamples）/ KnowledgeEntry、KnowledgeScope、KnowledgeStatus / 无 / 被 store.py、validator.py、belief/evidence.py、knowledge/store/registry.py、agent/belief_system.py / 完整
`ocos/memory/semantic/store.py`
- 存储 / knowledge 表 DDL（5 索引）+ 单行 UPSERT（ON CONFLICT(id) DO UPDATE，GAP-P2-1 修复注释）+ deprecate + query_by_domain/confidence/stability/status/lineage / SemanticStore / ocos.storage.connection、semantic.models / 被 hub.py、knowledge/store/registry.py（镜像）、tests/test_belief_consolidation.py / 完整（query_by_lineage LIKE 风险同上）
`ocos/memory/semantic/validator.py`
- 校验 / KnowledgeValidator 五重防护（Schema/Lineage 非空/Language 第三人称/Scope domain 非空/Audit 反例跟踪）+ _determine_status（失败→DEPRECATED，stability<0.6 或有反例→UNSTABLE）/ KnowledgeValidator / semantic.models / 被 agent/belief_consolidation.py（引用）/ 完整
`ocos/memory/pattern/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/memory/pattern/models.py`
- 模型 / PatternCandidate frozen（PAT-{date}-{uuid8}，trigger_condition+observed_relation+causal_explanation）+ Pattern（包装 candidate + validated_at/validation_notes）/ PatternCandidate、Pattern、PatternStatus / 无 / 被 store.py、validator.py、extractor.py、agent/belief_consolidation.py / 完整
`ocos/memory/pattern/store.py`
- 存储 / pattern 表 DDL（validated_at 仅 VALIDATED 非空）+ save INSERT OR REPLACE + find_by_condition（dream 巩固去重）+ query_by_status/highest_confidence + update_status / PatternStore / ocos.storage.connection、pattern.models / 被 hub.py、recall.py、agent/belief_consolidation.py、sleep_dream / 完整（_row_to_pattern 丢弃 validated_at/validation_notes——读回为纯 PatternCandidate）
`ocos/memory/pattern/validator.py`
- 校验 / PatternValidator 四层（Schema/语义禁用语/因果结构非空/禁止引用 EPI-\d{8}-[A-F0-9]{8} ID）/ PatternValidator / pattern.models / 被 agent/belief_consolidation.py、tests / 完整
`ocos/memory/pattern/extractor.py`
- 提取 / PatternExtractor：condition 归一化（截断 100 字符）→ ≥min_samples(3) 分组 → outcome 细分（error/failure/success[:40]）→ 置信度 (n/min_samples)*avg_significance；异常提取需 significance>0.8 且 prediction_error>0.8 / PatternExtractor / episode.models、pattern.models / 被 agent/belief_consolidation.py、sleep_dream / 完整
`ocos/memory/experience/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/memory/experience/models.py`
- 模型 / TraceBundle frozen（五要素 + reflection_trace_id/environment_state/goal_context 可选）+ ExperienceCandidate frozen（EXP-{date}-{uuid8}，completeness_score 五要素存在比 + reflection 加 0.1）/ TraceBundle、ExperienceCandidate、ExperienceStatus、ExperienceSource / 无 / 被 builder.py、gate.py、lessons.py、significance/*、agent/learning_trigger.py / 完整（时间戳 naive 本地时间）
`ocos/memory/experience/builder.py`
- 构建 / ExperienceBuilder.build（Validator 扫描 + 五要素检查 → COMPLETE/INCOMPLETE，违规写 rejection_reason——用 object.__setattr__ 破 frozen）+ seal/get_complete/get_incomplete/get_by_id/_synthesize_lessons / ExperienceBuilder / experience.models、experience.validator、experience.lessons / 被 agent/learning_trigger.py、tests / 完整
`ocos/memory/experience/validator.py`
- 校验 / ExperienceValidator：10 个禁用字段名（顶层+observation/action_result/outcome 嵌套 dict 键）+ 6 条第一人称语义模式递归扫描 + required_fields_present / ExperienceValidator / experience.models / 被 builder.py、tests / 完整
`ocos/memory/experience/lessons.py`
- 合成 / LessonsLearned frozen（LESSON-{date}-{uuid8}，success_pattern/failure_pattern/conditional_insight 三类，to_episode 复用 EpisodeStore source="lesson" tags=["synthesized"]）+ LessonsSynthesizer（按 goal_id 分组、context keys 交集、同 goal 异动作对比）/ LessonsLearned、LessonsSynthesizer / episode.models、experience.models / 被 builder.py、recall.py（get_recent/lesson 字段 duck-typing）、tests / 完整（confidence 公式 min(1, n/max(5,n)) 写法怪异但行为可解释）
`ocos/memory/significance/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/memory/significance/models.py`
- 模型 / DimensionScore（name/raw_score/weight/evidence）+ SignificanceScore（__post_init__ 重算 weighted_total）+ GateDecision / GateVerdict、DimensionScore、SignificanceScore、GateDecision / 无 / 被 evaluator.py、gate.py / 完整
`ocos/memory/significance/evaluator.py`
- 引擎 / SignificanceEvaluator：INCOMPLETE 直接 FAIL（四维 0 分带 evidence）→ 四维评分 → 阈值 0.5 判定 → 人类可读 reason；evaluate_all/get_passed/get_failed/get_by_candidate_id / SignificanceEvaluator / experience.models、significance.models、significance.rules / 被 gate.py、tests、agent/learning_trigger.py / 完整
`ocos/memory/significance/rules.py`
- 规则 / SignificanceConfig（权重 0.25/0.30/0.20/0.25 和=1 校验，threshold 0.5）+ 四个评分函数（goal_impact：活跃 goal 1.0/goal_context 0.8/observation.goal 0.6；prediction_error：失败 0.8/预期不匹配 0.7/surprise 0.5；knowledge_change：new_knowledge 0.9/error 0.7/reflection 0.5；future_relevance：high_priority 1.0/REFLECTION·ANOMALY 0.7/DECISION 0.4/GOAL_COMPLETION 0.3）/ SignificanceConfig + 4 函数 / experience.models / 被 evaluator.py / 完整
`ocos/memory/user/__init__.py`
- __init__ / re-export UserMemory/UserProfile/UserMemoryStore / 无 / user.model / 被 agent/agent_runtime.py / 完整
`ocos/memory/user/model.py`
- 模型+存储 / UserProfile（preferences/interests/relationships/recent_focus/habits/context）+ UserMemoryStore（SQLite 独立建连 + RLock，user_profiles 快照表 + memory_events 事件表）+ UserMemory（create/update_profile、record_event、set/get_context、summarize 注入摘要）/ UserProfile、UserMemoryStore、UserMemory / 无（自建 sqlite3，不走 storage.connection）/ 被 agent/agent_runtime.py、recall.py（duck-typing summarize） / 完整（update_profile 的 elif 分支为死代码、FK 未启用、version 恒 1）

##### ocos/personal_memory/（6 文件）
`ocos/personal_memory/__init__.py`
- __init__ / re-export 全部公共类型 + PM41 边界声明 / 无 / 包内 4 模块 / 被 agent/wisdom_trigger.py、agent/continuity_trigger.py、tests / 完整
`ocos/personal_memory/wisdom_types.py`
- 模型 / WisdomState 状态机（is_usable/is_mutable）+ WisdomScope（applies_to 硬排除→域→条件）+ WisdomEvidence + WisdomItem（evidence_strength/support_count/counter_count、promote_to 白名单转换）+ WisdomCollection（按用户隔离）/ WisdomState、WisdomScope、WisdomEvidence、WisdomItem、WisdomCollection / 无 / 被 store.py、validator.py、interpreter.py、reflection_engine.py / 完整
`ocos/personal_memory/pattern_interpreter.py`
- 引擎 / PatternInterpreter：neutral 拒绝、模式数≥2、frequency≥3 才产出候选；_derive_principle 模板化英文表述（总频次+平均置信度）；_infer_scope 从标签推断域（>3 标签→universal 泛化风险）/ PatternInterpreter、InterpretationResult / ocos.self.self_types、wisdom_types / 被 reflection_engine.py、agent/wisdom_trigger.py / 完整
`ocos/personal_memory/wisdom_validator.py`
- 引擎 / WisdomValidator：支持证据≥2、反例比≤0.3、evidence_strength≥0.6 三门槛 → PASS/NEED_MORE_EVIDENCE/REJECTED；validate_and_promote 自动 CANDIDATE→VALIDATING→CONFIRMED/DEPRECATED；inject_counter_evidence / WisdomValidator、ValidationDecision、ValidationResult / wisdom_types / 被 reflection_engine.py、tests / 完整
`ocos/personal_memory/wisdom_store.py`
- 存储 / WisdomStore dataclass：内存 dict[user_id→WisdomCollection] + 可选 SQLite connection（_persist_item INSERT OR IGNORE + _STATE_RANK 状态回退保护 + UPDATE 仅 state 列）+ load_from_db 重建 + assert_boundaries 预留钩子 / WisdomStore / wisdom_types / 被 reflection_engine.py、agent/wisdom_trigger.py（GAP-P2-4 持久化链路）、tests / 半成品（evidence 追加不落盘）
`ocos/personal_memory/reflection_engine.py`
- 编排 / ReflectionEngine.reflect：ExperienceProfile.successful_patterns/failure_patterns → interpret → validate_and_promote → PASS 者 add_wisdom；ReflectionResult 统计 + query_wisdom_for_domain / ReflectionEngine、ReflectionResult / ocos.self.self_types、ocos.self.experience_profile、包内 3 模块 / 被 agent/wisdom_trigger.py、tests / 完整

##### ocos/event_memory/（9 文件）
`ocos/event_memory/__init__.py`
- __init__ / re-export 全部公共类 + EM54-01~06 保证声明 / 无 / 包内 7 模块 / 被 execution/bridge.py、interaction/converse.py、tests / 完整
`ocos/event_memory/event_types.py`
- 模型 / CognitiveEventType 9 类 + EventConfidence 4 级 + EventLifecyclePhase 4 阶段 + CognitiveEvent frozen（caused_by/links_to 因果链、with_lifecycle 副本语义、age_seconds/is_recent）+ EventHeader + EventArchive + EventQuery / 见类名 / 无（仅 time） / 被包内全部模块、execution/bridge.py / 完整
`ocos/event_memory/event_store.py`
- 存储 / EventStore dataclass：内存 dict[timestamp→list] + _by_id/_headers 双索引 + append 幂等（重复 id False）+ find/range/iterate（+0.001 防重）/headers/stats/clear + snapshot/restore + 可选 SQLite _persist（INSERT OR IGNORE + sequence 子查询自增）+ load_from_db + mark_archived（仅 header）/ EventStore / event_types / 被包内 5 模块、execution/bridge.py、tests / 半成品（时间本地时区无亚秒、snapshot 丢 caused_by/metadata、mark_archived 状态不同步）
`ocos/event_memory/event_index.py`
- 索引 / EventIndex：by_type/by_entity（context+payload 的 entities/topics）/by_goal/by_source/by_confidence 五维 + _reverse 反向索引 + 综合交集 query + stats/clear / EventIndex / event_types / 被 event_lifecycle.py、event_query.py / 完整（无时间维度索引，与 docstring 的 time_index 宣称不符）
`ocos/event_memory/event_replay.py`
- 回放 / ReplaySession（游标式 current/next/reset）+ EventReplay：replay_range/replay_session/trace_causal_chain（seen 防环）/reconstruct_timeline（goal_id 或 payload 字符串包含）/generate_reflection（类型·置信度分布 + 决策/学习事件提取）/generate_evolution_narrative（中文叙事模板）/ ReplaySession、EventReplay / event_types、event_store / 被 execution/bridge.py、tests / 完整
`ocos/event_memory/event_archive.py`
- 归档 / LifecycleConfig（hot 3600s/warm 86400s/max_hot 1000/compress）+ EventArchiveManager：promote/demote 副本转换 + archive_batch（zlib 压缩 + sha256[:16] 校验 + store.mark_archived）+ restore_archive（checksum 校验失败抛 RuntimeError）+ apply_lifecycle（360s→WARM/3600s→COLD/86400s→ARCHIVED，直接改 store._events/_by_id 私有结构）/ LifecycleConfig、EventArchiveManager / event_types、event_store / 被 event_lifecycle.py / 完整（绕封装改私有字段、WARM 阈值 360 硬编码）
`ocos/event_memory/event_validator.py`
- 校验 / EventValidator：validate_event（必填 id、时间戳>0 且未来 60s WARN、空内容 WARN）+ validate_store（空 WARN、>1h 间隙 >10 个 WARN）+ validate_timeline（时间倒序 FAIL、无感知有决策 WARN）+ validate_replay_safe（ACTION 无 replay_safe 标记 WARN）+ mark_invalid 黑名单 / EventValidator、EventValidationResult、ValidationCode / event_types、event_store、event_archive / 被 event_lifecycle.py、tests / 完整
`ocos/event_memory/event_query.py`
- 查询 / QueryResult（events/total_hits/query_time_ms）+ EventQueryEngine：索引交集优先 → fallback store.range 扫描 + sources/多类型后过滤 + get_context（前后 radius 个时间桶）/ EventQueryEngine、QueryResult / event_types、event_store、event_index / 被 event_lifecycle.py / 半成品（索引命中分支漏 sources 过滤；confidence_min/lifecycle/context_has_key 死参数）
`ocos/event_memory/event_lifecycle.py`
- 编排 / EventLifecycle：record（生成 id→caused_by 回查→validate→FAIL 置 ARCHIVED 仍入库→append→index）+ record_batch + maintain + query + snapshot/restore（restore 重建索引与 query_engine）+ clear / EventLifecycle / event_types、event_store、event_index、event_archive、event_validator、event_query / 被 execution/bridge.py、interaction/converse.py / 完整（依赖 event_query 的导入别名 EventQueryParams，脆弱）

##### ocos/knowledge/（19 文件）
`ocos/knowledge/__init__.py`
- __init__ / 仅导出 KnowledgeGraph 系（不含 KnowledgeABI）/ 无 / .graph、.manager / 被 tests/test_knowledge_graph.py / 完整
`ocos/knowledge/graph.py`
- 模型+存储 / KnowledgeGraph：Entity（8 类）/Relation（10 类谓词三元组）/Fact（valid_from/valid_until 有效期 + is_active）；出/入边+类型+名称索引；resolve_entity 按 (confidence, -updated_at) 消歧；infer_relations BFS；export_json/clear；_make_id / KnowledgeGraph、Entity、Relation、Fact、EntityType、RelationType / 无 / 被 manager.py / 半成品（remove_entity 悬挂关系、find_by_name 非模糊、无 facts 导出、无导入方法）
`ocos/knowledge/manager.py`
- 编排 / KnowledgeGraphManager：learn_from_text（需注入 extractor，缺省返回 confidence=0.0 空结果）+ add_entity/add_relation（E-/R- 前缀 id）+ search/resolve/infer + get_stats/generate_report/export/_apply_extraction/_resolve_or_create/_record_action（500 条历史）/ KnowledgeGraphManager、ExtractionResult / .graph / 被 tests/test_knowledge_graph.py、knowledge/__init__.py / 完整
`ocos/knowledge/knowledge_abi.py`
- ABI / KnowledgeABI 1.0.0：get_unit/query/get_by_level/get_active_units（_to_public_view 安全过滤视图）+ submit_observation/create_unit/update_unit + verify/activate/deprecate/archive + can_elevate/elevate（新建子单元 version+1 回链 parent_id）+ get_status_history/total_knowledge_units/get_owners / KnowledgeABI / store.lifecycle、store.ontology、store.registry、process.promotion_rules / 被 engines/promotion_engine.py、engines/consolidation_engine.py、daemon/factory.py、tests / 完整（默认提升策略 allowed_sources 矛盾见 P2-7）
`ocos/knowledge/synthesis_manager.py`
- 综合 / KnowledgeSynthesisManager：KnowledgeNode（5 类 KnowledgeType×KnowledgeSource×5 态 KnowledgeStatus）/KnowledgeEdge 内存图 + RLock 双锁 + add/get/list/update_confidence（只升不降）/deprecate + add_edge/remove_edge/get_related_nodes + synthesize_knowledge（deductive/inductive/abductive 模板实现）+ query_knowledge 子串匹配 + find_path BFS + assess_knowledge_quality + get_stats/reset_stats/close / KnowledgeSynthesisManager、KnowledgeNode、KnowledgeEdge、SynthesisResult 等 / ocos.logging / 被 tests/test_knowledge_synthesis_manager.py / 半成品（综合为模板拼接、无持久化）
`ocos/knowledge/knowledge_ontology.py` — 壳 / re-export store.ontology 13 个符号 / Knowledge Plane v1.0 拆分兼容层 / store.ontology / 被 tests、agent/master_agent.py / 占位（转发完整）
`ocos/knowledge/knowledge_registry.py` — 壳 / re-export AccessMatrix/AccessScope/KnowledgeRegistry/OwnershipEntry / 同上 / store.registry / 被 tests / 占位
`ocos/knowledge/knowledge_lifecycle.py` — 壳 / re-export KnowledgeLifecycle/StatusChangeRecord / 同上 / store.lifecycle / 被 tests、engines / 占位
`ocos/knowledge/knowledge_validator.py` — 壳 / re-export process.validator 11 个符号 / 同上 / process.validator / 被 tests / 占位
`ocos/knowledge/knowledge_evolution.py` — 壳 / re-export EvolutionManager 等 4 符号 / 同上 / process.evolution / 被 tests、engines / 占位
`ocos/knowledge/promotion_rules.py` — 壳 / re-export process.promotion_rules 6 个符号 / 同上 / process.promotion_rules / 被 tests、daemon/factory.py / 占位
`ocos/knowledge/store/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/knowledge/store/ontology.py`
- 模型 / KnowledgeLevel 5 层 + KnowledgeStatus 5 态 + ELEVATION_MATRIX/STATUS_TRANSITIONS + get_elevation_targets/can_elevate/get_level_index/is_higher_level/get_next_statuses/can_transition + KnowledgeUnit frozen（uuid hex id、timestamp ISO UTC）+ ElevationRecord + validate_elevation（层级方向+ACTIVE/VERIFIED 状态）/ 见类名 / 无 / 被 registry.py、lifecycle.py、promotion_rules.py、validator.py、knowledge_abi.py、6 个壳 / 完整
`ocos/knowledge/store/registry.py`
- 存储+权限 / AccessMatrix（owner×level 三元权限 + 通配符 + set_default_permissions 默认低两层可写可提升）+ OwnershipEntry frozen + KnowledgeRegistry（_entries dict + register/update（dataclasses.replace version+1）/remove + check_read_access（PUBLIC 全读/PRIVATE owner/PROTECTED 同 owner 或矩阵）+ get/get_by_level/get_by_owner/get_by_status/search（tags issubset）+ GAP-P2-1 语义记忆镜像 _sync_to_semantic/_deprecate_in_semantic/_to_entry/_map_status fail-open）/ AccessMatrix、OwnershipEntry、KnowledgeRegistry、AccessScope / store.ontology、ocos.memory.semantic.models、ocos.memory.semantic.store / 被 knowledge_abi.py、lifecycle.py、evolution.py、daemon/factory.py、tests / 完整
`ocos/knowledge/store/lifecycle.py`
- 编排 / StatusChangeRecord frozen 审计 + KnowledgeLifecycle：change_status（get→can_transition→registry.update version+1→审计→监听器回调）+ verify/activate/deprecate/archive/reactivate 便捷方法 + get_version/get_version_history/get_status_history（limit 50）/ get_active_units + on_status_change 注册 / KnowledgeLifecycle、StatusChangeRecord / store.ontology、store.registry / 被 knowledge_abi.py、evolution.py、daemon/factory.py、tests / 完整（get_version_history 逻辑有误）
`ocos/knowledge/process/__init__.py`
- __init__ / 仅 docstring / 无 / 无 / 无 / 完整（空壳）
`ocos/knowledge/process/promotion_rules.py`
- 规则 / PromotionTriggerType 5 类 + PromotionTrigger + DEFAULT_TRIGGERS（OBS→REP 3 / EVD→REP 5 或 CONF 0.7 / PAT→CONF 0.85 或 GOV / PRI→GOV）+ PreCondition + PromotionPolicy（allowed_sources/requires_governance/前置条件，default_for_level）+ PromotionRuleEngine（register_policy/get_policy/can_promote 三层校验/check_trigger/load_default_policies）/ 见类名 / store.ontology / 被 knowledge_abi.py、evolution.py、engines/promotion_engine.py、tests / 完整
`ocos/knowledge/process/validator.py`
- 校验 / ValidationSeverity/Result/Report + ValidationRule + 4 个内置检查函数（content 非空/枚举类型/source≤128/提升链 parent 层级方向）+ DEFAULT_VALIDATION_RULES（3 条，check_elevation_chain 未入默认集）+ KnowledgeValidator（register_rule/remove_rule/validate，规则异常转 ERROR）/ KnowledgeValidator 等 / store.ontology / 被 evolution.py、knowledge_validator.py 壳、tests / 半成品（check_elevation_chain 传参错误）
`ocos/knowledge/process/evolution.py`
- 演进 / EvolutionChangeType 5 类 + EvolutionProposalStatus 5 态 + EvolutionProposal frozen + EvolutionManager：create_proposal（目标存在+写权限校验、ELEVATE 需 new_level、approval_required=False 时自动审批执行）+ submit_review/approve（originator 或 PRINCIPLE 写者）/reject/apply + _apply_edit/_apply_merge/_apply_deprecate/_apply_split（失败回滚）/_apply_elevate + list_proposals/count_by_status / 见类名 / store.lifecycle、store.ontology、store.registry、process.validator、process.promotion_rules / 被 knowledge_evolution.py 壳、engines、tests / 完整（EDIT 审计与 source 字段缺陷见 P2-8）


#### 审计分组 W7：world_model 世界模型 + digital_world 数字世界 + opentale_bridge + platform —— 文件索引

#### 二、文件全量索引

格式：文件类型 / 核心功能 / 关键类函数常量 / 导入依赖(OCOS内部) / 被哪些 OCOS 文件调用 / 状态

##### ocos/world_model/（9 文件）

`ocos/world_model/__init__.py`
- 代码（包入口）/ 模块文档 + 统一导出 17 个符号 / Boundary 约束 WM42-01~04 / 依赖本包全部子模块 / 被 daemon/factory.py、perception/pipeline.py、interaction/converse.py、os_v1/freeze.py、audit/*、health_examination/* / 完整实现

`ocos/world_model/world_types.py`
- 代码（纯类型）/ 世界模型全部核心数据结构 / EntityType(10 种+is_concrete)、EntityState、StateChange、Entity、RelationType(11 种+is_causal)、Relation、WorldEventType(8 种)、WorldEvent、CausalityType(5 种)、CausalityLink(is_well_supported/has_counter_evidence)、Observation / 无 OCOS 依赖 / 被本包全部文件及 perception/pipeline.py、audit/architecture_map.py 等 / 完整实现

`ocos/world_model/entity_model.py`
- 代码 / 实体 CRUD / EntityModel.create_entity/get/get_by_type/list_all/exists/remove/count/type_distribution / world_types / 本包 world_store、外部 via WorldStore / 完整实现

`ocos/world_model/relation_graph.py`
- 代码 / 有向关系图 / RelationGraph.add_relation/get/remove/outgoing/incoming/neighbors/find_by_type/causal_relations / world_types / world_store / 完整实现（remove 不清理 defaultdict 残键，轻微）

`ocos/world_model/state_tracker.py`
- 代码 / 状态版本链 / StateTracker.record_state/current/history/at_tick/changes_since/changed_keys / world_types / world_store / 完整实现（at_tick 假定状态按 tick 有序追加）

`ocos/world_model/event_model.py`
- 代码 / 事件溯源日志 / EventModel.record/all/by_entity/by_type/since/count_by_type / world_types / world_store / 完整实现

`ocos/world_model/causality_engine.py`
- 代码 / 因果推断引擎 / CausalityEngine.add_link/get/causes_of/effects_of/causal_chain/upstream_chain/well_supported/contested/confidence_distribution / world_types / world_store 导出 / 完整实现（但 WorldStore 无任何添加 CausalityLink 的路径——因果层实际无人写入，仅测试直接用）

`ocos/world_model/world_validator.py`
- 代码 / 外部输入治理 / WorldValidator(validate_observation/validate_against_model/clamp_confidence)、ValidationDecision、ValidationIssue、ValidationResult / world_types / world_store、__init__ 导出 / 半成品——validate_against_model 有自比较 bug（L118），REJECT/QUARANTINE/min_sources 未用

`ocos/world_model/world_store.py`
- 代码 / 统一存储+唯一写入口 / WorldStore(update_from_observation/get_entity/get_entity_state/get_neighbors/get_entity_history/search_entities/summary/cognitive_world_state)、_extract_entity_type / 本包全部组件 / perception/pipeline.py、daemon/factory.py、interaction/converse.py、health_examination、os_v1/freeze.py / 完整实现（缺因果写入路径与关系端点校验）

##### ocos/digital_world/（10 文件）

`ocos/digital_world/__init__.py`
- 代码（包入口）/ 宪法约束声明 + 导出 base/auditor/dlq 6 符号 / VALID 约束注释 / 本包 base/auditor/dlq / execution/bridge.py（经子模块）、tests / 完整实现

`ocos/digital_world/base.py`
- 代码（数据模型）/ 操作与结果模型 / VALID_OP_TYPES(12)、APPROVAL_REQUIRED(7)、MAX_FILE_SIZE_BYTES、MAX_FILE_CONTENT_CHARS、API_RATE_LIMIT_PER_MIN、SEARCH_QUERY_MAX_LEN、SANDBOX_TIMEOUT_SECONDS、DigitalOperation、OperationResult、AuditRecord / 无 / 本包全部 ops + execution/bridge.py + tests/digital_world/* / 完整实现

`ocos/digital_world/api_ops.py`
- 代码 / HTTP GET/POST / API_WHITELIST、_check_rate_limit、_real_http_get/_real_http_post、api_get、api_post / base / execution/bridge.py（候选）、tests / 完整实现（白名单仅 3 域名）

`ocos/digital_world/file_ops.py`
- 代码 / 文件读/写/删 / PROTECTED_PATHS、_is_protected、file_read、file_write、file_delete / base / execution/bridge.py（PW-4.2 FILE_WRITE 后端）、tests / 完整实现（file_read 无保护路径检查）

`ocos/digital_world/git_ops.py`
- 代码 / Git clone/commit/push / GIT_URL_WHITELIST、_check_git_cooldown、_real_git_clone/_real_git_commit/_real_git_push、git_clone/commit/push / base / tests / 完整实现

`ocos/digital_world/db_ops.py`
- 代码（占位）/ 数据库操作 / db_query、db_write——两者直接返回 "(simulated)" / base / tests / 占位代码

`ocos/digital_world/search_ops.py`
- 代码 / grep 文件系统搜索 / _grep_filesystem、_sanitize_query、search、_MAX_RESULTS、_MAX_OUTPUT_BYTES / base / tests / 完整实现（真实模式执行 grep 子进程）

`ocos/digital_world/sandbox.py`
- 代码 / 命令沙箱执行 / BLOCKED_COMMANDS(11)、_is_blocked、_real_exec(shell=True)、sandbox_exec / base / tests / 完整实现（"沙箱"仅为黑名单+workdir，非真隔离）

`ocos/digital_world/auditor.py`
- 代码 / 操作审计 / OperationAuditor.record/find_by_requester/find_by_status/trail / base / __init__ 导出、tests / 完整实现（内存态，无持久化）

`ocos/digital_world/dlq.py`
- 代码 / 死信队列 / DLQEntry(increment_retry)、DeadLetterQueue(enqueue/retry_pending/pending/permanently_failed/all_entries) / base / __init__ 导出、tests / 完整实现（内存态）

##### ocos/opentale_bridge/（16 文件）

`ocos/opentale_bridge/__init__.py`
- 代码（包入口）/ 架构文档 + 导出 18 符号 + quick_bridge_test/quick_web_feed_test / 本包主要组件 / interaction 层、tests / 完整实现

`ocos/opentale_bridge/bridge_model.py`
- 代码（数据模型）/ 桥会话全部类型 / BridgePhase(7 态)、OcosDecision(含 Trace Identity 3 字段)、TranslationResult、FeedbackInput、RepairDecision、ContractAdjustment(is_empty/to_contract_patch/to_dict)、BridgeSession(to_dict)、WebFeedResult / 无 / 本包全部组件 / 完整实现

`ocos/opentale_bridge/bridge_session.py`
- 代码（模拟验证层）/ 全周期编排 / BridgeSessionOrchestrator(feed_context/feed_web_data/produce_decision/translate/execute_simulated/feedback/run_full_cycle/run_multi_chapter/run_full_cycle_with_repair/_execute_simulated_repair/apply_contract_adjustment/run_multi_chapter_with_trend_watch) / bridge_model、decision_translator、feedback_loop、web_feeder、trend_analyzer、quality_analyzer / __init__、tests/test_phase59 / 半成品——_execute_simulated_repair L338 引用不存在的 session.translation_result（实测 AttributeError）；apply_contract_adjustment 写盘逻辑被注释禁用

`ocos/opentale_bridge/decision_translator.py`
- 代码（规则翻译）/ Decision→Blueprint + Trend→Contract / FOCUS_TO_PRIMARY_DRIVER、PACING_TO_RHYTHM、TONE_TO_EMOTION_CURVE、CLIFFHANGER_TO_ENDING、DecisionTranslator.translate/_determine_phase/_build_scenes/translate_adjustment、TREND_TO_CONTRACT_RULE(9 条) / bridge_model、trend_analyzer、ocos_activation / bridge_session、self_regulation / 完整实现

`ocos/opentale_bridge/feedback_loop.py`
- 代码 / 输出→反馈 + 修复判定 / FeedbackLoop(process/_check_identity_drift/to_ocos_input/evaluate_and_repair/generate_repair_decision/analyze_cross_chapter_trends) / bridge_model、quality_analyzer、trend_analyzer / bridge_session / 完整实现

`ocos/opentale_bridge/feedback_reflux.py`
- 代码 / 评审回流持久化 / FeedbackReflux(collect_and_store/latest/feedback_summary)、_feedback_dir / organ_client、ocos_activation、ocos_memory / interaction/cli/commands/feedback.py / 完整实现

`ocos/opentale_bridge/master_agent.py`
- 代码（生产决策引擎）/ 意图→真实写作决策 / WritingIntent、FOCUS_KEYWORDS、TONE_KEYWORDS、PACING_KEYWORDS、FOCUS_TO_KEY_SCENES、MasterAgent(resolve_focus/resolve_tone/resolve_pacing/decide/to_organ_contract/summary/_attention_focus/_belief_context/_collect_cognition_context/_writing_decision_gate)、_focus_label / bridge_model、trace_context、ocos_activation、ocos_memory、belief_gate、ocos.attention.candidate_selector、ocos.attention.scoring / interaction/cli/commands/decide.py、interaction/api/routes/chat.py、tests/test_master_agent / 完整实现（L247-248 双重 @staticmethod 叠加；_collect_cognition_context 疑似被 decide 内联逻辑取代，为遗留死方法）

`ocos/opentale_bridge/ocos_activation.py`
- 代码（观测埋点）/ 激活计数跨进程持久化 / activate/snapshot/reset/summarize、_log_path、_LOCK / 无 / 本包 9 处 + interaction CLI / 完整实现

`ocos/opentale_bridge/ocos_memory.py`
- 代码 / 写作记忆编排（M3/M4/M5/M6/C3）/ OcosMemory(record_decision/record_feedback/consolidate/prune/recall/latest_feedback/longterm_memory)、KEEP_DECISION=200、KEEP_FEEDBACK=10、CONSOLIDATE_SCORE=80.0 / 无 / master_agent、feedback_reflux、tests/test_ocos_memory / 完整实现（跨进程并发 append 无文件锁）

`ocos/opentale_bridge/organ_client.py`
- 代码（HTTP 客户端）/ Organ API 全接口 / OrganClientError、OrganTaskTimeout、OrganClient(_request/health/status/projects/project/chapter/drafts/generate/resume/rewrite/verify/analyze/task/events/wait/wait_events/accept/reject/collect_generated/generate_and_wait) / ocos_activation、trace_context / feedback_reflux、self_regulation、interaction/cli/commands/organ.py、tests/test_organ_client / 完整实现

`ocos/opentale_bridge/quality_analyzer.py`
- 代码 / 5 维文学质量自主分析 / DimensionScore、QualityReport(to_ocos_feedback/needs_repair/failing_dimensions/repair_guidance/_repair_suggestions_for、REPAIR_OVERALL_THRESHOLD=0.6、REPAIR_DIMENSION_THRESHOLD=0.3、MAX_REPAIR_ATTEMPTS=3)、EMOTION_LEXICON(48 词)、ROMANCE_EMOTIONS(29 词)、ACTION_KEYWORDS、QualityAnalyzer.analyze 及 5 个 _analyze_* + 辅助方法、quick_analyze / 无（仅 datetime 局部导入）/ feedback_loop、__init__、interaction/api/routes/quality.py、tests / 完整实现（角色识别启发式局限大；_detect_emotional_peaks 用字符位置近似分桶）

`ocos/opentale_bridge/self_regulation.py`
- 代码 / 跨章自调节闭环 / SelfRegulationLoop(collect_chapter_reports/_chapter_report/_text_quality_score/_text_dimensions/analyze/adjust/describe/apply/_record_adjustment/_adjustment_to_instruction)、_self_regulation_mode(OCOS_SELF_REGULATION 默认 manual) / decision_translator、organ_client、trend_analyzer、ocos_activation / interaction/cli/commands/regulate.py、tests/test_self_regulation / 完整实现（L179 硬编码个人路径 /home/laogao/Documents/trae_projects/opentale/projects）

`ocos/opentale_bridge/trace_context.py`
- 代码 / 结构化 Trace 上下文 / TraceContext(frozen, correlation_id/agent_run_id/generation_request_id, with_component/to_headers/parse_headers/new_root)、HDR_* 4 个 HTTP 头常量、SCHEMA_VERSION="1.0"、new_id / 无 / master_agent、organ_client / 完整实现

`ocos/opentale_bridge/trend_analyzer.py`
- 代码 / 跨章趋势检测 / TrendSignal、TrendAnalyzer(MIN_CHAPTERS_FOR_TREND=3、WINDOW_SIZE=5、TREND_THRESHOLD=0.5、DECAY_THRESHOLD=-0.05、analyze/_detect_decay/_detect_chronic_dimension/_detect_monotone_emotional/_detect_dialogue_imbalance/_detect_genre_drift) / ocos_activation / decision_translator、feedback_loop、self_regulation / 完整实现

`ocos/opentale_bridge/web_feeder.py`
- 代码（模拟数据）/ Web 喂食 / _WebChunk、WebFeeder(SEARCH_STRATEGIES 5 类、FRESH_TOPICS 硬编码 2026 假数据、search_and_feed/feed_all_topics/get_available_topics) / bridge_model / __init__、bridge_session / 占位性质的模拟实现（生产需接真实搜索）

`ocos/opentale_bridge/belief_gate.py`
- 代码 / 信念治理门 / GateVerdict(PASS/STRIP/REJECT/ESCALATE)、BeliefSource(5 种)、GateResult、BeliefGate(evaluate/_strip_inference/gate_held_beliefs、ESCALATE_KEYWORDS) / 无 / master_agent（I7 信念上下文）/ 完整实现（零写接口，Belief→Decision 结构性 DENY）

##### ocos/platform/（14 文件）

`ocos/platform/__init__.py`
- 代码（包入口，1 行 docstring）/ 无导出 / 无 / 无 / 完整实现

`ocos/platform/audit_models.py`
- 代码（数据模型）/ 审计类型定义 / AuditRecordType(4 类)、DEFAULT_AUDIT_STORE_SIZE=10000、QUERY_MAX_LIMIT=500、AuditRecord、AuditRule、AuditFinding、CheckFn / ocos.kernel.abi / audit_engine、audit_rule_engine、audit_report / 完整实现

`ocos/platform/audit_engine.py`
- 代码 / 审计统一入口 / InMemoryAuditStore(store/get/query/count/clear)、AuditEngine(_subscribe/_on_decision_event/_on_governance_event/_on_execution_event/_on_system_event/record/query_audit_trail/run_audit_checks/build_debug_report/build_compliance_report/build_replay_context/reset/unsubscribe_all) / kernel.abi、audit_models、audit_rule_engine、audit_report、ocos.logging / interaction 层、scripts/phase21_gate.py、tests/test_audit_engine、capability/discovery.py 等 / 完整实现（record 的 record_type 需枚举，传 str 会 AttributeError）

`ocos/platform/audit_rule_engine.py`
- 代码 / 审计规则执行器 / AuditRuleEngine(register_rule/remove_rule/run_checks/reset)、5 条 _check_* 规则函数、DEFAULT_AUDIT_RULES、load_default_audit_rules / kernel.abi、audit_models、ocos.logging / audit_engine、tests / 完整实现（Rule2/Rule5 依赖 details 中 governance_audit_id/related_halt_audit_id 字段，但事件回调从不写入这些字段——两条 error 级规则实际永不触发）

`ocos/platform/audit_report.py`
- 代码 / 报告生成 / AuditReportGenerator(build_debug_report/build_compliance_report/build_replay_context) / audit_models / audit_engine / 完整实现（build_debug_report 中 trace 查询在循环内重复执行，性能瑕疵）

`ocos/platform/capability_registry.py`
- 代码 / 能力注册中心 / CapabilityType、CapabilityDescriptor、CapabilityRegistry(register/unregister/get/find_by_name/get_all_versions/query/list_by_type/list_all_types/reset) / kernel.abi、ocos.logging / plugin_loader.register_to、capability/discovery.py、plugin_sandbox（可选）、tests/test_capability_registry / 完整实现（同名同版本自动 patch+1 只处理第一个匹配）

`ocos/platform/engine_loader.py`
- 代码 / 引擎动态装载 / EngineLoader(load_all/load/reload/unload/get/list_loaded/get_manifest/_load_single) / engine_manifest / tests/platform/test_engine_loader、B3 调度器（设计上） / 完整实现（导入失败静默返回 None）

`ocos/platform/engine_manifest.py`
- 代码 / 引擎元数据发现 / EngineManifest、ENGINES_PACKAGE="ocos.engines"、EngineDiscoverer(discover/discover_with_deps/find_by_capability/_load_manifest) / 无（仅标准库） / 全部 ocos/engines/*（17 处）、engine_loader、tests/platform/test_engine_manifest / 完整实现

`ocos/platform/governance_engine.py`
- 代码 / 提案审批工作流 / ProposalType(3)、ProposalStatus(5)、_ALLOWED_TRANSITIONS、_validate_transition、EvolutionProposal(is_terminal)、GovernanceEngine(submit_proposal/review_proposal/cancel_proposal/get_proposal/list_proposals/find_proposal_by_title/reset) / kernel.abi、ocos.logging / kernel/constitution.py 引用（宪法约束对象）、tests/test_governance_engine / 完整实现

`ocos/platform/plugin_base.py`
- 代码 / 插件接口契约 / PluginBase(ABC: on_load/execute/on_unload/manifest) / plugin_manifest / plugin_loader、plugin_sandbox、quarantine_20260824 插件样例 / 完整实现

`ocos/platform/plugin_manifest.py`
- 代码 / 插件声明 / Permission(4 种)、_ENTRY_POINT_PATTERN、PluginManifest、validate_manifest / 无 / plugin_base、plugin_loader、plugin_sandbox / 完整实现

`ocos/platform/plugin_loader.py`
- 代码 / 插件生命周期管理 / LoaderErrorCode、LoadResult、PluginLoader(discover/load/execute/unload/get_instance/find_by_name/list_loaded/register_to/load_all/unload_all/reset/_parse_manifest_file) / plugin_base、plugin_manifest、plugin_sandbox、ocos.logging、capability_registry(局部) / tests/test_plugin_loader、quarantine 测试 / 完整实现（L272 直接访问 sandbox._plugins 私有字段注入实例——耦合 hack）

`ocos/platform/plugin_sandbox.py`
- 代码 / 插件隔离沙箱 / _DEFAULT_ALLOWED_IMPORTS(27 前缀)、SandboxResult、SandboxConfig、_ImportBlocker、PluginSandbox(load/unload/execute/reset/_resolve_timeout/_get_pool/_run_in_thread/_do_execute)、_PluginSlot、_replace_result_time / plugin_base、plugin_manifest、capability_registry(可选)、ocos.logging / plugin_loader、tests/test_plugin_sandbox / 半成品——import hook 创建后从未加入 sys.meta_path（隔离失效，见 R4）

`ocos/platform/trace_engine.py`
- 代码 / 可解释性 Trace / TraceType(7 种)、DecisionTrace/ReasoningTrace/SimulationTrace/LearningTrace/MemoryTrace/ExecutionTrace/GoalTrace、TraceRecord 联合、InMemoryTraceStore、TraceEngine(record_decision/reasoning/simulation/learning/memory_trace/record_process_trace/record_execution/record_goal/query_traces/get_trace/reset) / kernel.abi、ocos.models.process / 10 处（capability/discovery.py、audit_report、tests 等） / 完整实现（docstring"4 类"过时，实际 7 类）


#### 审计分组 W8：perception 感知 + attention 注意力 + evolution 演化 + learning 学习 + growth 成长 + reflection 反思 + cognitive_nutrition 认知营养 + cognitive_continuity 认知连续性 —— 文件索引

#### 二、文件全量索引

说明："内部依赖"指 OCOS 内部真实 import；"被调用"经全仓 grep 反查（不含 __pycache__；tests/ 与 ocos/tests/ 测试引用仅列代表性文件）。

##### ocos/perception/（11 文件）

`ocos/perception/__init__.py`
- 模块门面 / 导出全部类型、传感器、引擎、提取器、验证器 / 无类定义 / 内部依赖：sensor_types、text_sensor、file_sensor、environment_sensor、perception_engine、semantic_extractor、perception_validator / 被调用：daemon 等经包级导入 / 状态：完整实现

`ocos/perception/sensor_types.py`
- 类型定义 / SensorModality(6 模态)、SensorStatus(5 态)、SensorConfig(poll_interval/max/confidence_threshold/modalities)、SensorHealth、ObservationType(6 类)、Observation(is_reliable/age_seconds)、SemanticFragment(intent/domain/entities/sentiment/priority_hint)、PerceptionEventType(5 类)/PerceptionEvent、ValidationVerdict(5 判决)/ValidationResult / 无内部依赖 / 被全模块引用 / 状态：完整实现（Observation.id 默认值 `obs-{time.time()}` 同秒碰撞风险，见 P3）

`ocos/perception/text_sensor.py`
- 传感器 / TextSensor：feed/feed_batch/poll（buffer 出队 → RAW Observation，_estimate_confidence 按长度 0.3/0.8/0.95）/has_pending/clear_buffer/get_health / 依赖 sensor_types / 被 multi_modal、tests 引用 / 状态：完整实现（_buffer 无容量上限，P4）

`ocos/perception/file_sensor.py`
- 传感器 / FileSensor：watch/watch_directory(PW-5.1 目录重扫描捕获新建文件)/poll（mtime/size/exists 快照比对 → CHANGE Observation）/clear_watches/get_health / 依赖 sensor_types / 被 pipeline 场景（cli/commands/run.py:75）、multi_modal 引用 / 状态：完整实现（import os 未使用，清理级）

`ocos/perception/environment_sensor.py`
- 传感器（内感）/ EnvironmentSensor：poll（psutil 采集 RSS/CPU/磁盘/uptime；内存 1024/2048MB 告警与危险线；±100MB 跳变检测 → ANOMALY Observation）、EnvironmentSnapshot / 依赖 sensor_types + 可选 psutil / 被 multi_modal、tests 引用 / 状态：完整实现（psutil 缺失优雅降级；cpu_percent(interval=0.1) 每 poll 阻塞 100ms）

`ocos/perception/perception_engine.py`
- 引擎 / PerceptionEngine：register_sensor/unregister_sensor/tick（poll→extract→validate→event→callback）/get_recent_observations/sensor_health/get_state/set_state / 依赖 sensor_types / 被 multi_modal、pipeline 引用 / 状态：完整实现（tick 内传感器异常静默 continue 无日志，P3）

`ocos/perception/semantic_extractor.py`
- 语义处理 / SemanticExtractor（intent/domain 关键词映射、实体=引号+反引号、sentiment、priority_hint，仅处理 TEXT 模态）、ObservationBuilder（from_raw/from_anomaly/from_change/merge） / 依赖 sensor_types / 被 __init__ 导出、tests 引用；生产 pipeline 未默认接线 / 状态：完整实现（实体正则字符类 `["""]...["\u201d"]` 疑似编码损坏，见 P4；urgent 词表含疑似拼写错误 "asep"）

`ocos/perception/perception_validator.py`
- 验证门控 / PerceptionValidator：validate（去重窗口 10s → 来源信誉乘算 → min_confidence 0.3 门控 → <0.6 NEEDS_CONFIRMATION → ACCEPTED）/set_source_reputation/get_stats/get_state / 依赖 sensor_types / 被 __init__ 导出、tests 引用；生产 pipeline 未默认接线 / 状态：完整实现（_seen 去重表无淘汰无上限，P4；内容指纹用 str hash 进程内随机，仅内存使用可接受）

`ocos/perception/pipeline.py`
- 桥接层（GAP-P1-3）/ PerceptionPipeline：register_sensor/tick（engine.tick → _bridge_to_world 逐条 → WorldStore.update_from_observation → 可选因果推断 _infer_causality_links）/accepted_count/rejected_count；感知 Observation ↔ 世界 Observation 唯一适配点 / 依赖 perception_engine、sensor_types、**ocos.world_model**（world_store/world_types/world_validator）/ 被调用：ocos/daemon/factory.py:218、ocos/daemon/__init__.py、tests/test_perception_pipeline.py / 状态：完整实现（fail-closed：无 resolver 且无 metadata 实体/状态 → WorldValidator 拒绝）

`ocos/perception/multi_modal.py`
- 多模态扩展（Phase T）/ AudioSensor、VisionSensor（转录/描述→TEXT 观察的哑壳）、ApiSensor、EventSensor、MultiModalPerception（7 传感器装配 + tick/feed_*/watch_*/fuse_modalities/get_sensor_health/get_stats/get_status_report） / 依赖 sensor_types、text_sensor、file_sensor、environment_sensor、perception_engine、cross_modal_fusion / 被调用：仅 ocos/tests/test_multi_modal_perception.py（生产零调用）/ 状态：完整实现（音视频仅占位转录入口）

`ocos/perception/cross_modal_fusion.py`
- 融合器 / FusionStrategy(4 策略)、ModalObservation、FusedObservation、CrossModalFusion：set_weight/fuse（weighted_vote/max_confidence/consensus/sequential + 冲突检测）/get_stats / 无 OCOS 内部依赖 / 被 multi_modal 引用 / 状态：完整实现（冲突检测按 str(content)[:50] 相等性，粒度粗）

##### ocos/attention/（7 文件）

`ocos/attention/__init__.py`
- 模块门面 / 导出 types/focus/CandidateCollector/AttentionScoringEngine / — / 被调用：ocos/tests/test_phase39_5.py、test_phase39_6.py、ocos/runtime/stages/attention.py（经成员导入） / 状态：完整实现

`ocos/attention/attention_types.py`
- 类型定义（Phase 39.5）/ FocusType(GOAL/EVENT/MAINTENANCE)、AttentionState（frozen，to_dict/from_dict，Phase 38 边界注释：禁止经 Attention 建 Goal/改 priority/改 anchor）、AttentionCandidate（4 评分因子）、InertiaPolicy（should_switch 三重门：min_duration/cooldown/threshold 1.3）、AttentionTrace（to_dict）、AttentionScoringWeights（权重和=1.0 校验）、FocusSelectionResult / 无内部依赖 / 被 scoring、selector、recovery、runtime/stages 引用 / 状态：完整实现（focus_duration 属性公式与 scoring 实际计算不一致，P4）

`ocos/attention/candidate_selector.py`
- 候选收集 / CandidateCollector：add_goal/add_event/add_maintenance/candidates/clear/count/has_candidates（纯容器，不 import Goal/Event 模块） / 依赖 attention_types / 被调用：ocos/runtime/stages/attention.py:24、ocos/opentale_bridge/master_agent.py:259 / 状态：完整实现

`ocos/attention/scoring.py`
- 评分+惯性 / AttentionScoringEngine：score（4 因子加权，clamp [0,1]）/score_all/select（无候选→初始聚焦→同焦点保持→惯性判定→切换 + AttentionTrace 审计）/ _build_trace / 依赖 attention_types / 被调用：runtime/stages/attention.py:25、opentale_bridge/master_agent.py:260 / 状态：完整实现

`ocos/attention/focus.py`
- 焦点管理器（Phase O）/ FocusType(EXTERNAL/INTERNAL/GOAL_DRIVEN/IDLE)、FocusState（frozen，is_focused/is_idle/to_dict）、AttentionFocus：process_observation/**存在 bug**/update_from_homeostasis/set_focus/clear_focus/check_idle/on_focus_change/on_new_attention、create_attention_focus 工厂 / 依赖 **ocos.runtime.attention_engine**、**ocos.capability.homeostasis** / 被调用：ocos/proactive/output.py:25、ocos/cognitive_loop/attention_coordinator.py / 状态：**半成品/带缺陷**（process_observation 的 _update_focus(focus_target=…) 关键字错误且缺 score 实参，实测抛 TypeError，P2-01；其余 API 正常）

`ocos/attention/retrieval.py`
- 注意力驱动检索（Phase 24-D）/ AttentionSignal、RetrievedItem（自定义 __eq__/__hash__）、AttentionDrivenRetrieval：retrieve（long_term 全量 + episodic 乘 recency_weight，关键词命中率 × importance_weight，阈值过滤 + 排序截断 + 缓存）/_score/clear_cache / 依赖 ocos.logging / 被调用：ocos/agent/memory_consolidation.py、scripts/phase24_gate.py / 状态：完整实现（缓存无 TTL 无上限，P4）

`ocos/attention/recovery_integration.py`
- 快照桥（Phase 39.5）/ attention_state_to_snapshot/attention_state_from_snapshot/validate_attention_restore（三字段一致性校验） / 依赖 attention_types / 被调用：ocos/tests/test_phase39_5.py / 状态：完整实现（生产 RuntimeSnapshot 侧接线程度属 runtime 组范围）

##### ocos/evolution/（11 文件）

`ocos/evolution/__init__.py`
- 模块门面 / 导出 types + 全部 9 个组件 / — / 被调用：ocos/tests/test_phase47.py、ocos/agent/self_evolution_link.py / 状态：完整实现

`ocos/evolution/evolution_types.py`
- 类型定义 / EvolutionState(11 态)、EvolutionTrigger(7 类)、EvolutionDomain(8 允许域)、FORBIDDEN_DOMAINS(5 禁域)、ImpactLevel(5 级)、ImpactAssessment(is_safe/boundary_violations)、EvolutionProposal(ready_for_migration)、RollbackReason/RollbackRecord / 无内部依赖 / 被本模块与 ocos/agent/master_agent.py、self_evolution_link.py 引用 / 状态：完整实现

`ocos/evolution/improvement_detector.py`
- 信号检测 / DetectedSignal、ImprovementDetector：detect_from_health(<0.5)/detect_from_performance(<0.6)/detect_pattern(≥5 次)/detect_capability_gap/detect_decision_drift(<0.4)/pending_signals/has_signals/clear / 依赖 evolution_types / 被调用：manager、self_evolution_link.py:81 / 状态：完整实现

`ocos/evolution/evolution_proposer.py`
- 提案生成 / EvolutionProposer：propose（trigger→domain 映射 + FORBIDDEN 降级 + change_type 映射 + 初始 impact）/pending_proposals/history/_build_initial_impact（被 manager 越权调用的"私有"方法） / 依赖 evolution_types、improvement_detector / 被调用：manager、self_evolution_link.py:75 / 状态：完整实现

`ocos/evolution/impact_analyzer.py`
- 影响分析（CE47-04 守卫）/ ImpactAnalyzer：analyze（边界→ABI→依赖→等级→回滚可行性 5 步） / 依赖 evolution_types / 被调用：self_evolution_link.py:80 / 状态：完整实现（_check_dependencies 为空壳仅带未用 import，P4；目标模块名仅做精确匹配禁止域）

`ocos/evolution/evolution_sandbox.py`
- 沙箱 / SandboxResult(4 态)、SandboxReport(all_passed)、EvolutionSandbox：validate（边界/描述≥10 字/目标模块/change_type 合法性/replace 需快照，5 检查计数） / 依赖 evolution_types / 被调用：manager、self_evolution_link.py:76 / 状态：完整实现（静态检查型沙箱，非隔离执行环境——命名易生误解）

`ocos/evolution/approval_engine.py`
- 审批引擎 / ApprovalVerdict、ApprovalRecord、ApprovalEngine：evaluate（Gate1 sandbox→Gate2 边界→Gate3 CRITICAL 拒/HIGH 需治理→Gate4 change_type→Gate5 受约束自主 auto:governed 或 PENDING_REVIEW）、manual_approve（U5.2：仅 PENDING_REVIEW+安全预检+显式批准人） / 依赖 evolution_types / 被调用：仅 ocos/evolution/__init__.py 导出 + 测试（生产无调用方，extension/ 有独立同名实现）/ 状态：完整实现（FORBIDDEN 分支不可达死代码，P4）

`ocos/evolution/migration_engine.py`
- 迁移引擎 / MigrationResult、MigrationEngine：migrate（ready 校验→建快照→_execute→失败回滚）/restore_snapshot/recent_migrations / 依赖 evolution_types / 被调用：manager、self_evolution_link.py:143 / 状态：**半成品**（_execute 注释自认"模拟"，不执行真实变更，P2-03）

`ocos/evolution/rollback_engine.py`
- 回滚引擎 / RollbackEngine：create_snapshot/rollback/verify_rollback/rollback_all_failed/history / 依赖 evolution_types、migration_engine / 被调用：仅测试；manager 未使用 / 状态：半成品（"恢复"仅标记 proposal.state，无真实状态还原）

`ocos/evolution/evolution_memory.py`
- 进化记忆 / EvolutionMemory：record/proposal_history/successful_evolutions/failed_evolutions/evolution_domains/total_evolutions / 依赖 evolution_types / 被调用：manager、self_evolution_link.py:106/141 / 状态：完整实现（内存 list，无持久化）

`ocos/evolution/manager.py`
- 总管（Phase AA）/ EvolutionStatus、SelfEvolutionManager：detect_and_propose/analyze_proposal/validate_proposal/approve_proposal/execute_proposal/rollback/get_proposal/list_proposals/get_status/get_history/tick/属性 proposal_count/active_proposals/pending_proposals / 依赖 evolution 全家 + ocos.logging / 被调用：ocos/tests/test_self_evolution_manager.py、test_master_agent_self_evolution.py（生产经 self_evolution_link 使用各子组件而非本总管）/ 状态：**半成品**（analyze_proposal 越权调用私有方法且 impact 未写回 P3；快照为描述字符串 P3；tick() auto_approve 为空桩 P3）

##### ocos/learning/（6 文件）

`ocos/learning/__init__.py`
- 模块门面 / 仅导出 manager 的反馈学习组件 / — / 被调用：ocos/tests/test_continuous_learning.py / 状态：完整实现（experience_learning/skill_growth/metacognition/persistence 未入 __all__，调用方直接子模块导入）

`ocos/learning/manager.py`
- 持续学习（Phase R）/ FeedbackType(4)、LearningSignalType(5)、FeedbackRecord、PreferenceEntry、LearningResult、LearningCycleStats、PreferenceModel（add_feedback/_extract_preference/_update_preference 置信度加权 0.7/0.3/get_preference/get_recommendation/update_from_feedback）、ContinuousLearning：record_feedback/learn_from_interaction/get_preferences/get_recommendation/get_stats/generate_learning_report / 无 OCOS 内部依赖 / 被调用：ocos/tests/test_continuous_learning.py（生产零调用方）/ 状态：完整实现（英文关键词极性判断误报面大，P4）

`ocos/learning/experience_learning.py`
- 经验学习（Phase 49-A，Freeze 不 import OCOS 内部模块声明与延迟 import ocos.models.learning 并存）/ FailureCause(7 类)+信号词表、FailureDiagnosis、FailureDiagnoser.diagnose、EpisodeExampleConverter.convert/convert_many、RuleBasedLearner.learn_fn（指纹 sha1[:12] 聚合 + _merge_rules 增量合并 + accuracy）/ ArtifactType(4)、ArtifactStatus(4 态)、LearningArtifact（commit）、build_lesson_artifact、check_behavioral_delta / 依赖 ocos.models.learning（延迟）/ 被调用：ocos/agent/master_agent.py:1577、ocos/agent/agent_runtime.py:1085、tests/test_learning_rule_consumption.py / 状态：完整实现

`ocos/learning/skill_growth.py`
- 技能生长（Phase 49-C）/ ReplanAction(4)、ReplanDecision、TaskReplanner.decide/should_retry/is_terminal（MAX_RETRY_PER_TASK=2）、SkillProposalStatus(4 段)、SkillProposal（to_skill）、SkillProposer.propose_from_episodes（CANDIDATE_MIN_SUCCESS=3，写类 WRITE_TASK_TYPES 保守需审批）、GovernedSkillCommitter.validate/approve/commit / 依赖 ocos.capability.models（延迟，to_skill 内）/ 被调用：ocos/agent/master_agent.py:908、ocos/agent/agent_runtime.py:1084、tests/test_execution_bridge.py:256 / 状态：完整实现（procedure 的 zip 配对在字段缺失时错位，P4）

`ocos/learning/metacognition.py`
- 元认知（Phase 49-D）/ SkillMatch、语义同义词组 4 组、SkillSemanticMatcher.match（语义标签 IoU 70% + 表面 Jaccard 30%，threshold 0.4）、ConfidenceVerdict、CapabilityConfidence.evaluate（LOW_CONFIDENCE_THRESHOLD=0.4、MIN_EVIDENCE=3：写类低成功率→escalation "ask"） / 无 OCOS 内部依赖 / 被调用：ocos/daemon/factory.py:92 / 状态：完整实现（_find_matching_rule 兜底分支条件重复冗余，P4）

`ocos/learning/persistence.py`
- 持久化（FIX-08/20）/ _init_table（learning_models 表）、save_learning_rules/load_learning_rules/persist_latest_rules（从 agent._learning_engine 取最新模型落库）/load_learning_summary / 无 OCOS 内部依赖（agent 为 duck-typed Any）/ 被调用：ocos/interaction/converse.py:358/628、ocos/daemon/__init__.py:537、tests/test_learning_rule_consumption.py / 状态：完整实现（写失败降级返回 False；load 与 CapabilityConfidence.evaluate 结构兼容有注释保证）

##### ocos/growth/（2 文件）

`ocos/growth/__init__.py`
- 模块门面 / 导出 engine 全部公开名 + PROJECT_ROOT / — / 被调用：ocos/interaction/cli/commands/growth.py:17 / 状态：完整实现

`ocos/growth/engine.py`
- 成长引擎（Phase 50）/ 常量（MIN/MAX_SIGNAL_CHARS、FORBIDDEN_DIRS/FILES、ALLOWED_PREFIX、MAX_NET_DELETION_LINES=30、MIN_KEEP_RATIO=0.5、_WANTED_PATCH_RE）、_deletion_scale/_exceeds_scale_guard、TechSignal、GrowthProposal、GrowthResult、GrowthSignalStore（tech_signals/growth_log 两表 sqlite，record/mark/pending/get/log_result/history）、GrowthAnalyzer（analyze 一次 patch 精确性重试、_find_candidate_files 词元+词边界评分、_build_prompt、_parse_response 含路径白名单/真实存在/逐字唯一/规模护栏/禁改治理模块）、GrowthOptimizer（validate_path/_snapshot/_rollback/_run_tests 专属 pytest 或 import 门/apply 6 步闸）、GrowthEngine（ingest/analyze_pending/execute_proposal/grow_once） / 依赖 ocos.logging / 被调用：ocos/interaction/cli/commands/growth.py:29、tests/test_growth_engine.py、ocos/tests/test_phase50_growth.py / 状态：完整实现（FORBIDDEN_FILES glob 模式永不命中 P4；信号状态 applied/skipped 未使用 P4）

##### ocos/reflection/（2 文件）

`ocos/reflection/manager.py`
- 反思管理（Phase AE）/ ReflectionType(5)、ReflectionDepth(4)、InsightType(5)、ReflectionTrace、WisdomItem、IdentitySnapshot、SelfReflectionManager：start_reflection/add_insight/complete_reflection/get_reflection/list_reflections/propose_wisdom/verify_wisdom/get_wisdom/list_wisdom/increment_wisdom_usage/create_identity_snapshot/check_identity_continuity/get_latest_snapshot/batch_reflect/get_stats/reset_stats/close（3 把 RLock） / 依赖 ocos.logging / 被调用：ocos/agent/master_agent.py:2573/2588、ocos/tests/test_self_reflection_manager.py、test_master_agent_reflection.py / 状态：完整实现（全内存无持久化；wisdom 满即拒）

`ocos/reflection/self_review.py`
- 自省分析器（Phase 52）/ ReviewEvidence（30+ 字段 + to_dict）、_classify_failures（关键词聚类）、SelfReviewCollector（mode=ro sqlite：episodes 成败 outcome JSON 精确判定、失败模式全量+7d julianday 窗口、goal/belief/event/DLQ/working_memory、_collect_code_assets 双域代码资产+git、_run_self_checks C1-C4）、SelfReviewAnalyzer（默认 LLM=ocos.engines.text_generator，可注入；5 条分析纪律 prompt）、render_markdown、write_report（docs/self_review/） / 依赖 ocos.logging、ocos.engines.text_generator（延迟默认）/ 被调用：ocos/interaction/cli/commands/self.py:78、tests/test_reflection_self_review.py、ocos/tests/test_phase52_self_review.py / 状态：完整实现

##### ocos/cognitive_nutrition/（5 文件）

`ocos/cognitive_nutrition/__init__.py`
- 模块门面 / 导出全组件 / — / 被调用：仅 ocos/tests/test_phase58_2.py / 状态：完整实现

`ocos/cognitive_nutrition/nutrition_model.py`
- 模型层 / NutritionDay(0-7)、DataMealType(6 类)、DataMeal（token_estimate=len/4）、FastingBaseline（记忆/身份/认知签名/健康/目标/经验 8 组基线）、DigestionStatus(5 态)、DigestionObservation（记忆/知识增量、身份哈希、决策质量、世界模型矛盾/覆盖、异常；is_healthy/memory_delta）、DayNutritionStatus、DayNutritionResult（any_failure_criteria）、NutritionReport（to_dict/to_json） / 无内部依赖 / 被本模块与其余 4 文件引用 / 状态：完整实现

`ocos/cognitive_nutrition/data_feeder.py`
- 数据生成 / generate_day1_fact_meals（15 条 AI 史实）/generate_day2_technical_meals（5 篇工程文档）/generate_day3_long_text_meals（陌生小说《The Glass Archive》单餐）/generate_day4_conflict_meals（5 组冲突对）/generate_day5_user_preference_meals（6 段偏好）/generate_day6_integrated_task（世界设计任务）、DAY_FEEDERS 分发表、TOTAL_MEALS / 依赖 nutrition_model / 被 nutrition_protocol 引用 / 状态：完整实现（Day5 循环变量 `for i, i in enumerate(...)` 遮蔽，P4）

`ocos/cognitive_nutrition/digestion_monitor.py`
- 消化监测 / DigestionMonitor：feed_meal（实测值缺省用每餐型固定估算：fact=1/document=2/long_text=5/conflict=2/interaction=1/task=3；增长率=Δmem/token；身份漂移判定或注入 check_fn）、feed_meals、current_* / all_observations / anomaly_count / identity_stable 属性、compare_health/growth_summary、_classify_observation（幻觉>0→HALLUCINATION、身份漂/目标自生成→POLLUTION、增长率>50→WARNING）/ 依赖 nutrition_model / 被 nutrition_protocol 引用 / 状态：完整实现（默认估算路径为合成数据，P3 见模块节）

`ocos/cognitive_nutrition/nutrition_protocol.py`
- 协议执行 / CognitiveNutritionProtocol：run（Day0 基线 → Day1-6 逐日 + 失败即 _create_emergency_stop → Day7 复检 → 汇总 healthy_digestion）、_establish_fasting_baseline（sha256(anchor:constitution)[:16]）、_run_day/_check_day_criteria（6 日各自判据）/_run_health_recheck、run_nutrition_protocol 便捷函数 / 依赖 nutrition_model、data_feeder、digestion_monitor / 被调用：仅 tests/test_phase58_2.py / 状态：完整实现（未接真实 OCOS，见模块节验证状态）

##### ocos/cognitive_continuity/（7 文件）

`ocos/cognitive_continuity/__init__.py`
- 模块门面 / 导出类型 + 4 引擎 + TICKS_PER_MONTH + 检查点 / — / 被调用：ocos/tests/test_phase49.py、ocos/agent/continuity_trigger.py / 状态：完整实现

`ocos/cognitive_continuity/continuity_types.py`
- 类型层 / TimeGranularity(6 级)、TimeAnchor(3 锚)、ExperienceNode、TimeContainer（max_entries=20）、LifeMemoryGraph、TimelineEntry、CognitiveTimeline（add_past/present/intent，CC49-04 注释）、IdentitySnapshot、KnowledgeAge(5 级)、AgedKnowledge / 无内部依赖 / 被全部引擎引用 / 状态：完整实现

`ocos/cognitive_continuity/life_memory_graph.py`
- 记忆图引擎 / LifeMemoryEngine：record_experience（importance≥0.1 门 + 10000 条按重要性淘汰）/aggregate_day(30)/aggregate_week(20)/aggregate_month(15)/aggregate_year(10)（容器数 365/52/24/10 封顶）/recent_memory/important_memories/by_tag/_summarize/is_full / 依赖 continuity_types / 被 continuity_checkpoint、continuity_trigger.py:38、tests 引用 / 状态：完整实现（**缺 aggregate_season**，MAX_SEASONS=16 悬空，P4）

`ocos/cognitive_continuity/cognitive_timeline.py`
- 时间线引擎 / TimelineEngine：record_decision/record_milestone/record_evolution（同径不同默认 significance）/snapshot_present（替换 present）/record_intent（CC49-04：注释称严格拒绝非用户来源，但代码无来源校验，P4）/significant_events/recent_past / 依赖 continuity_types / 被 continuity_checkpoint、continuity_trigger.py:31 引用 / 状态：完整实现

`ocos/cognitive_continuity/identity_continuity.py`
- 身份连续性 / ContinuityCheck、IdentityContinuityEngine：create_snapshot（100 个封顶）/check_continuity（风险偏好+0.3/决策风格+0.2/智慧倒退+0.3/核心记忆替换>50%+0.4 → severity）/latest_check/consistent_rate / 依赖 continuity_types / 被 continuity_checkpoint、continuity_trigger.py:32 引用 / 状态：完整实现（对比基准 snapshots[-2] 的调用约定易误用，P4）

`ocos/cognitive_continuity/knowledge_aging.py`
- 知识老化 / 常量 TICKS_PER_MONTH≈30K/HALF_YEAR/YEAR/3Y（假设 1000 tick/天）、KnowledgeAgingEngine：register/age_all（引用过按 current_tick-last_referenced，否则保留存储 age；is_core 权重恒 1.0）/reference（刷新 FRESH）/active_knowledge/core_knowledge/weight_summary / 依赖 continuity_types / 被 continuity_checkpoint、continuity_trigger.py:35 引用 / 状态：完整实现

`ocos/cognitive_continuity/continuity_checkpoint.py`
- 检查点 / CheckpointState、ContinuityCheckpoint.create_checkpoint（聚合身份最新快照/经验数/时间线计数/知识四段统计；52 个封顶）/latest/count / 依赖 continuity_types + 4 引擎 / 被调用：ocos/agent/continuity_trigger.py:28、tests/test_phase49.py / 状态：完整实现

---


#### 审计分组 W9：goal 目标系统 + daemon 守护进程 + execution 执行闭环(DecisionBridge) + audit + diagnosis + health_examination + living_verification + living_test —— 文件索引

#### 二、文件全量索引

共 82 个文件（v1.3.1：daemon 组 4→14 收录 Boot Awareness 与自愈链上电文件）。状态标注：完整实现 / 半成品 / 占位代码。

**ocos/goal/（12）**
- `ocos/goal/__init__.py`
  - 文件类型：包入口 / 核心功能：Phase 39.6 目标维护子系统门面，声明 Goal≠Task、Maintenance≠Desire/Decider 架构约束 / 关键：导出 GoalHealth、GoalHealthSnapshot、MaintenanceEvent、GoalMonitor、GoalMonitorConfig、MaintenanceEngine、MaintenanceResult / 导入依赖：本包 maintenance_types/goal_monitor/maintenance_engine / 被调用：ocos/tests/test_phase39_6.py / 状态：完整实现
- `ocos/goal/models.py`
  - 文件类型：deprecated 兼容垫片 / 核心功能：全部 re-export 自 ocos.kernel.goal_types 并发 DeprecationWarning / 关键：Goal、GoalLevel、GoalStatus、GoalOriginLevel、GoalAuthority、GoalSource、GoalDomain、SuccessCriteria、UserGoal、CALLER_WHITELIST / 依赖：ocos.kernel.goal_types / 被调用：ocos/goal/{tree,parser,tracker,validator}.py、ocos/interaction/base.py / 状态：完整实现（过渡层）
- `ocos/goal/store.py`
  - 文件类型：持久化存储层 / 核心功能：goals 表 + plan_dag 表 SQLite CRUD、PENDING 人类目标原子认领、stale-ACTIVE 崩溃回收、域层完成闭环 / 关键类：GoalStore（save/load/load/claim_pending_human/requeue_stale_active/mark_completed/update_progress/save_plan_dag/load_plan_dag/record_decision；自愈建表 + legacy 表 ALTER 补列 AUD-F8）/ 依赖：ocos.storage.connection / 被调用：daemon/__init__.py、agent/agent_runtime.py L1300、autonomous/goal_manager.py、interaction/{converse,repl.goal,cli.goal}、tests/test_goal_claim 等 / 状态：完整实现
- `ocos/goal/tree.py`
  - 文件类型：数据结构 / 核心功能：Goal 层级树（max_depth=3、decomposed 来源强制、终端子树清理、状态统计）/ 关键类：GoalTree（add_child/get_children/get_leaves/is_complete/all_goals/maintenance/count_by_status/_depth_of）/ 依赖：ocos.goal.models / 被调用：仅 tests（grep 无生产调用）/ 状态：完整实现（未接线）
- `ocos/goal/parser.py`
  - 文件类型：解析器 / 核心功能：纯规则中文 NL→UserGoal（domain 关键词打分、去礼貌前缀、数字/万字约束、成功标准、优先级关键词）/ 关键类：GoalParser.parse 与 4 个 _extract/_infer / 依赖：ocos.goal.models / 被调用：仅 tests / 状态：完整实现（未接线，规则粗糙）
- `ocos/goal/factory.py`
  - 文件类型：工厂 / 核心功能：宪法约束 Goal 创建（MISSION 禁动态、Phase 隔离 21/22-24、authority 推导）/ 关键：GoalFactory.create/set_phase、ConstitutionViolationError / 依赖：ocos.agent.goal_types（注意非 kernel 版）/ 被调用：agent/control_loop.py、tests/{phase21_prompt3,phase22_prompt1,goal_origin_model,phase38_5_rgv} / 状态：完整实现
- `ocos/goal/validator.py`
  - 文件类型：校验器 / 核心功能：来源合法性（human/decomposed）、树合法性、循环引用检测；reject_self_module 为空占位（依赖 import-rule 测试强制）/ 关键类：GoalValidator / 依赖：ocos.goal.models / 被调用：仅 tests / 状态：完整实现（未接线）
- `ocos/goal/enforcer.py`
  - 文件类型：权限强制器 / 核心功能：GOAL ORIGIN MODEL v1.0——创建 Phase 隔离 + HUMAN 需 human_authorized 上下文；修改禁 origin_level 变更与 authority 提升 / 关键：GoalOriginEnforcer.verify_creation/verify_modification、ConstitutionResult / 依赖：ocos.kernel.goal_types / 被调用：agent/agent_runtime.py L712、agent/control_loop.py、autonomous/goal_manager.py、tests / 状态：完整实现
- `ocos/goal/goal_monitor.py`
  - 文件类型：监控器 / 核心功能：目标健康评估（终态→COMPLETED/INACTIVE、PENDING→INACTIVE、ACTIVE 按 idle_ticks/progress/attention_age 分级 WARNING/STALLED）+ to_events / 关键：GoalMonitor.evaluate/_evaluate_one/to_events、GoalMonitorConfig（stall 500/warning 200/attention 100/min_progress 0.1）/ 依赖：本包 maintenance_types / 被调用：maintenance_engine.py、ocos/homeostasis.py re-export、tests / 状态：完整实现（未接线）
- `ocos/goal/maintenance_types.py`
  - 文件类型：类型定义 / 核心功能：GoalHealth 六态（severity 0.0-0.9 映射、needs_attention）、MaintenanceEvent（→EventBus）、GoalHealthSnapshot（可序列化）/ 关键：如上三数据类 / 依赖：无 / 被调用：goal_monitor/maintenance_engine、包 __init__ / 状态：完整实现
- `ocos/goal/maintenance_engine.py`
  - 文件类型：编排器 / 核心功能：run_maintenance(goal_provider,...)——兼容 get_active_goals/get_all_goals/可迭代三种 provider，产出快照+事件 / 关键：MaintenanceEngine.run_maintenance、MaintenanceResult / 依赖：goal_monitor/maintenance_types / 被调用：包 __init__、tests（无生产调用）/ 状态：完整实现（未接线）
- `ocos/goal/tracker.py`
  - 文件类型：内存追踪器 / 核心功能：goal 进度/备注/起止时间内存追踪 / 关键类：GoalTracker（start/update/complete/get_progress/is_complete/get_notes/get_elapsed）/ 依赖：ocos.goal.models / 被调用：仅 tests / 状态：完整实现（未接线）

**ocos/daemon/（14）**
- `ocos/daemon/__init__.py`
  - 文件类型：核心实现 / 核心功能：ResidentRuntime 常驻 daemon——tick 循环（kernel.tick_loop 单宿主）、目标队列+背压(50)、持久化目标认领、用户消息收件箱消费、goal_result 回推、dream 巩固、心跳落盘、健康体检、感知管线、SelfMonitor、SIGUSR1 全线程栈转储；v1.3.1：start 流程插入启动自省调用（V5 连续性校验后、tick 线程前）+ tick 循环体最外层自愈兜底 try/except（残余异常不再杀死 tick 线程）+ `_drain_user_inbox` fallback 保护 / 关键类：ResidentRuntime、QueuedGoal、DaemonState / 依赖：agent_runtime、life_cycle_orchestrator、self.monitor、runtime_kernel、goal.store、interaction.{session_state,inbox,converse}、runtime_scheduler、learning.persistence、perception、daemon.boot_awareness / 被调用：interaction/cli/commands/run.py（主入口）、tests / 状态：完整实现
- `ocos/daemon/boot_awareness.py`【v1.3.1 新增】
  - 文件类型：启动自省（数字生命环境审视）/ 核心功能：`run_boot_awareness(db_path, post_fn, stimulus_fn, level)` 四环节——采集（uname/uptime/df/proc-meminfo/nproc/nvidia-smi→lspci/网络连通/自身计数/boot_id 对比重启与停机推断，全只读+逐项失败降级，网络探测最坏 ~6s）→ 分析（ok/warn/bad findings）→ 适应（boot_context.json 环境先验供 bridge `_boot_context_hint` 注入目标执行 + key_bad 异常转 MotivationHub 刺激走三道闸，全正常诚实沉默零提案）→ 汇报（outbound kind='report' + episode source='boot_awareness'）/ 关键：run_boot_awareness/_collect_system/_collect_network/_collect_self/_analyze/_adapt_write_context/_read_boot_id / 依赖：pathlib/sqlite3/uuid/日志 / 被调用：daemon/__init__.py start 流程、execution/bridge.py（_boot_context_hint 读 boot_context.json）、tests/test_boot_awareness_20260908.py / 状态：完整实现【功能实测可通】
- `ocos/daemon/watchdog.py`【v1.3.1 新增】
  - 文件类型：L2 自愈看门狗 + 每日备份 / 核心功能：`run_watchdog(stale_s=90)`——读 daemon_heartbeat.json：文件不存在=人为 stop 诚实跳过不误杀；age>90s=tick 循环推定死亡 → systemctl --user restart ocos-daemon + JSONL 记账 ops/restart.log（user=watchdog）；`run_daily_backup()` 每日首次运行 SQLite backup API 在线备份 → ~/.ocos/backups/ocos-YYYYMMDD.db 保留 7 份（.last_backup_day 节流）/ 关键：run_watchdog/restart_daemon/run_daily_backup/_heartbeat_age_s/_log_restart / 依赖：subprocess（systemctl）、sqlite3 / 被调用：ocos-watchdog.timer（systemd 每 2 分钟 oneshot，`python -m ocos.daemon.watchdog`）、tests/test_watchdog_20260908.py / 状态：完整实现【功能实测可通】
- `ocos/daemon/factory.py`
  - 文件类型：生产装配层 / 核心功能：MasterAgent+五引擎装配、HealthLoop 装配（Alert+File 通道）、感知管线、知识平面 ABI、DecisionBridge 装配（PendingStore+capability 发现+L8 置信度源）/ 关键：build_master_agent/build_cognitive_engines/build_health_loop/build_perception_pipeline/build_knowledge_registry/build_knowledge_abi/build_execution_bridge/_make_confidence_source / 依赖：agent.*、capability.*、constitution、engines.*、events、runtime、self、alerts、health_examination、homeostasis、perception、world_model、knowledge.*、execution.*、learning.metacognition / 被调用：interaction/cli/commands/run.py、tests / 状态：完整实现
- `ocos/daemon/health_loop.py`
  - 文件类型：稳态监控 / 核心功能：每 interval_ticks(100) 体检——采集 4 项指标（fail-closed 降级）→ CognitiveExaminer → HomeostasisManager → AlertManager；tick 末尾触发诊断循环 / 关键类：HealthLoop（bind/tick/run_check/_decision_failure_rate/_safe）/ 依赖：alerts.*、capability.homeostasis、health_examination.cognitive_examiner、daemon.repair_link（延迟 import）/ 被调用：daemon/__init__.py tick 循环、daemon/factory.build_health_loop / 状态：完整实现
- `ocos/daemon/repair_link.py`
  - 文件类型：诊断-修复链接 / 核心功能：诊断循环（探针→检测→提案→白名单过滤→待批/自动执行带冷却）+ 记忆膨胀确定性归档提案 + system_repair 执行体（checkpoint/rollback/白名单步骤执行器）/ 关键：run_diagnosis_cycle/execute_system_repair/_step_whitelisted/_make_checkpoint/_rollback_checkpoint/_execute_step、_AUTO_REPAIR_COOLDOWN=3600 / 依赖：diagnosis.{diagnosis_types,fault_detector,repair_proposer,system_probe,repair_executor,repair_types}、execution.pending、capability_reality.adapter_discovery、logging / 被调用：daemon/health_loop.py、execution/bridge.py（_handler_system_repair）、tests/test_immune_system / 状态：完整实现（数据级回滚 _rollback_checkpoint 为半成品，循环体 pass）
- `ocos/daemon/self_check.py`
  - 文件类型：四层断言式自检（L2-1）/ 核心功能：红线回归（审批无伪造兜底/API 鉴权/自主闸/审计可写/沙盒白名单）+ 认知体检（记忆响应性/待批积压）+ 因果链审计（episodes→TraceStep 链完整性≥90%）+ 活体验证（身份锚基线比对防漂移）；自检项异常=该项失败诚实上报 / 关键：SelfCheckRunner.run/_check_redline/_check_cognitive/_check_trace_audit/_check_living、record_self_check / 依赖：living_verification.*、execution.{bridge,autonomy} / 被调用：daemon/health_loop.py `_run_self_check`（每 N 次体检）/ 状态：完整实现
- `ocos/daemon/improve_link.py`
  - 文件类型：自改进提案链接（L2-4）/ 核心功能：lesson/reflection episodes → 确定性提炼改进点 → self_evolution_link.propose_upgrade（主权冻结域守门）→ pending_actions（action_type='self_upgrade'）待批；去重+限速，绝不自动执行 / 关键：propose_from_reflections/_recent_improvement_episodes/_already_proposed / 依赖：agent.self_evolution_link、execution.pending / 被调用：daemon/health_loop.py / 状态：完整实现
- `ocos/daemon/motivation.py`
  - 文件类型：L3 MotivationHub 自主性涌现 / 核心功能：信号→评分→提案→autonomy 闸（失败 lesson/belief 边界/goal_result 低成功率/self-exploration 四源，三维评分+去重+每日 cap=5）；LEVEL>=2 低风险 PROBE/LEARN 直写 goals 表，其余 PendingStore；同 key 刺激 PROBE→LEARN→REPAIR 升级阶梯，3 次未解决饱和静默；连续 3 次自主失败自动降级 LEVEL；verify_repairs REPAIR 复发核对 / 关键：MotivationHub.scan/propose_stimulus/record_result/verify_repairs、_from_belief_boundary（过滤 pattern 模板回声）、_from_self_exploration（pkgutil 实扫从未触及子包生成自我探查 PROBE）/ 依赖：goal.store、execution.pending、memory.episode、storage.* / 被调用：daemon/__init__.py（scan/propose_stimulus/verify_repairs）、boot_awareness（stimulus_fn）、bridge / 状态：完整实现
- `ocos/daemon/growth_narrative.py`
  - 文件类型：成长叙事周报 / 核心功能：ISO 周切换检测 → 上周 episodes/goals 统计 → 章节化叙事（W35/W36 已存档）→ outbound kind='report' / 关键：check_week_rollover / 被调用：daemon/__init__.py %100 周期块 / 状态：完整实现
- `ocos/daemon/vitals_report.py`
  - 文件类型：生命体征日报 / 核心功能：日切换检测 → 当日行为统计摘要 → outbound kind='report' / 关键：check_day_rollover/summary / 被调用：daemon/__init__.py / 状态：完整实现
- `ocos/daemon/continuity.py`
  - 文件类型：V5 连续性校验 / 核心功能：启动时身份/记忆连续性核验 / 被调用：daemon/__init__.py start 流程 / 状态：完整实现
- `ocos/daemon/active_interaction.py`
  - 文件类型：P5.2 主动交互管线 daemon 侧 / 核心功能：空闲期基于目标状态（停滞/依赖数据过期）产出交互提议走 outbox / 关键：scan_and_interact、stale_threshold_days / 被调用：daemon/__init__.py 周期块（LEVEL>=1） / 状态：完整实现
- `ocos/daemon/channel_link.py`
  - 文件类型：外部通道联动 / 核心功能：外部交互通道状态联动 / 被调用：daemon 装配 / 状态：完整实现

**ocos/execution/（4）**
- `ocos/execution/__init__.py`
  - 文件类型：包入口 / 核心功能：导出 DecisionBridge/BridgeReport/ActionVerdict / 依赖：bridge / 被调用：各消费方 import ocos.execution.bridge 直连为主 / 状态：完整实现
- `ocos/execution/bridge.py`
  - 文件类型：核心执行铰链（1154 行）/ 核心功能：详见"一、3" DecisionBridge 闭环描述——process()/execute_dag_task() 双入口、AUTO/ASK/DENY 分级、PermissionGuard 语义双检、PendingStore 待批、ExecutionAudit+event_memory 双留痕、LLM 任务转换+预算、沙盒执行+崩溃兜底+拦截反馈重试、结论摘要；v1.3.1：`_boot_context_hint()` 读 ~/.ocos/boot_context.json 将本 boot 启动自省实测环境（GPU/网络/磁盘/内存/CPU/重启推断）注入目标执行先验——基于当前实测而非过时记忆规划，文件缺失静默返回 "" 零开销 / 关键：DecisionBridge、ActionVerdict、BridgeReport、AUTO_ACTIONS/ASK_ACTIONS/DENY_ACTIONS/ACTION_SEMANTICS、_DAG_AUTO_TYPES/_DAG_ASK_TYPES、_boot_context_hint / 依赖：autonomous_runtime.action_dispatcher、agent_orchestration.audit、interaction.base、execution.pending、capability_reality.*、operations.*、digital_world.*、event_memory.*、engines.text_generator、agent.self_evolution_link、daemon.repair_link / 被调用：agent/agent_runtime.py、interaction/{converse,api.routes.converse,cli.approvals,repl.approvals}、cognitive_loop/action_controller、capability/execution_bridge、daemon/factory、cli/commands/goal、tests / 状态：完整实现
- `ocos/execution/pending.py`
  - 文件类型：持久化存储 / 核心功能：pending_actions 表（schema v4）待批队列 CRUD + approval_disabled() 审批开关（OCOS_APPROVAL_MODE 默认 auto）/ 关键类：PendingStore（enqueue/get/list_by_status/decide/mark_executed）；函数 approval_disabled / 依赖：ocos.storage.connection / 被调用：execution/bridge、daemon/repair_link、interaction/{converse,repl.approvals,cli.approvals}、tests / 状态：完整实现
- `ocos/execution/goal_executor.py`
  - 文件类型：CLI 直接执行器（Phase 51）/ 核心功能：goal 描述→LLM 分解只读命令→逐条 bridge 沙盒执行→汇总；persist_result 写 agent 层 goal 表 / 关键类：GoalDirectExecutor（decompose/execute_command/execute_goal/persist_result）、ExecResult、GoalExecReport、MAX_COMMANDS=12 / 依赖：execution.bridge、logging / 被调用：interaction/cli/commands/goal.py、tests/test_phase51_goal_exec / 状态：完整实现

**ocos/audit/（8）**
- `ocos/audit/__init__.py`
  - 文件类型：包入口 / 核心功能：run_full_audit/audit_report_markdown 门面 + AU51 边界声明 / 依赖：本包全部 6 模块 / 被调用：tests/test_phase51 / 状态：完整实现
- `ocos/audit/audit_types.py`
  - 文件类型：类型定义 / 核心功能：LayerStatus/ConnectionStatus 枚举、LayerSpec/CapabilityMatrix、TraceHop/IntegrationTrace、ViolationSeverity/BoundaryViolation、GapReport、TaskStep/TaskSimulation、AuditReport / 依赖：无 / 被调用：本包全部、tests / 状态：完整实现
- `ocos/audit/architecture_map.py`
  - 文件类型：审计器 / 核心功能：LAYER_REGISTRY（Phase 39-50 十二层规格）+ 存在性/测试文件检查 + 加权评分 + Markdown 表 / 关键：LAYER_REGISTRY、ArchitectureMap.audit_all/_audit_single/_calculate_score/layer_status_table / 依赖：audit_types / 被调用：audit_report、tests / 状态：半成品（_audit_single L199 无条件置 CONNECTED，TESTED 检查被覆盖）
- `ocos/audit/integration_tracer.py`
  - 文件类型：审计器 / 核心功能：8 条跨层链路 TRACE_DEFINITIONS + _check_hop 目录存在性检查 / 依赖：audit_types / 被调用：audit_report、tests / 状态：占位级实现（同层/跨层分支返回相同 WIRED，L202-205 代码重复，"验证"即目录存在）
- `ocos/audit/boundary_checker.py`
  - 文件类型：审计器 / 核心功能：10 条 CORE_BOUNDARIES 定义 + 对 4 类边界（IDENTITY/GOAL/MEMORY/CAPABILITY）做源码逐行关键词/正则扫描 / 依赖：audit_types / 被调用：audit_report、tests / 状态：半成品（B-EVOLUTION/B-DECISION/B-INTERFACE/B-DRIFT/B-SELF/B-CONTINUITY 六条边界定义了但无扫描逻辑，_scan_for_violations 只实现 4 类）
- `ocos/audit/gap_analyzer.py`
  - 文件类型：知识库 / 核心功能：KNOWN_GAPS 10 条硬编码缺口（含 critical 的 G-PERSISTENCE-01）+ 按优先级/类别分组 + roadmap()/ 依赖：audit_types / 被调用：audit_report、tests / 状态：完整实现（静态清单性质）
- `ocos/audit/task_simulator.py`
  - 文件类型：审计器（名义）/ 核心功能：T001-T010 十个端到端任务"模拟"，全部步骤经 _s() 工厂硬编码 passed=True / 依赖：audit_types / 被调用：audit_report、tests / 状态：占位代码（结论与实现无关，恒 PASS）
- `ocos/audit/audit_report.py`
  - 文件类型：报告生成器 / 核心功能：六维汇总、评分评级（PASS/PASS_WITH_GAPS/FAIL）、风险评估、v1.1 roadmap、完整 Markdown 输出 / 关键类：AuditReportGenerator（generate/_calculate_grade/_assess_risk/_generate_summary/markdown_report）/ 依赖：本包 5 模块 / 被调用：包 __init__、tests / 状态：完整实现（audit_date 硬编码 "2026-07-26"）

**ocos/diagnosis/（12）**
- `ocos/diagnosis/__init__.py`
  - 文件类型：包入口 / 核心功能：SD56-01..06 宪法声明 + 诊断→修复全链架构图 + 全组件导出 / 依赖：本包全部 / 被调用：外部 import ocos.diagnosis 入口 / 状态：完整实现
- `ocos/diagnosis/diagnosis_types.py`
  - 文件类型：类型定义 / 核心功能：FaultCategory(10)/Severity(0.1-1.0)/ComponentHealth/SystemSnapshot/FaultSignal(is_critical)/EvidencePoint/DiagnosisReport(needs_repair 属性) / 依赖：无 / 被调用：本包全部、daemon/repair_link、tests / 状态：完整实现
- `ocos/diagnosis/system_probe.py`
  - 文件类型：探针 / 核心功能：只读系统快照——4 探针（runtime 占位/persistence 目录检查/event_memory 查 event_store 表/memory 占位），单探针失败隔离，overall_health=健康占比 / 关键类：SystemProbe（capture/_probe_component/_probe_runtime/_probe_persistence/_probe_event_memory/_probe_memory/tick_capture）/ 依赖：diagnosis_types / 被调用：daemon/repair_link、diagnosis/manager、tests / 状态：完整实现（runtime/memory 探针为占位指标）
- `ocos/diagnosis/fault_detector.py`
  - 文件类型：检测器 / 核心功能：组件不健康→按名推断 FaultCategory、趋势 failing/degrading→PERFORMANCE_DEGRADATION、ThresholdRule 阈值检查、5 分钟故障窗口频率 / 关键类：FaultDetector（feed/_check_component_health/_check_trend/_check_threshold/fault_rate/clear）、ThresholdRule / 依赖：diagnosis_types、health_analyzer / 被调用：daemon/repair_link、diagnosis/manager、tests / 状态：完整实现
- `ocos/diagnosis/health_analyzer.py`
  - 文件类型：分析器 / 核心功能：20 快照滑窗趋势（前后半均值差 slope，failing<0.4 / degrading slope<-0.1）+ 最差组件定位 / 关键类：HealthAnalyzer（add_snapshot/analyze/clear）、HealthTrend / 依赖：diagnosis_types / 被调用：fault_detector、manager、tests / 状态：完整实现
- `ocos/diagnosis/repair_types.py`
  - 文件类型：类型定义 / 核心功能：RepairType（10 允许 + 7 禁止名单 + is_forbidden）、RepairStatus(9)/RepairRisk(5)、RepairProposal(is_allowed)、RepairRecord(lesson/pattern/should_remember) / 依赖：无 / 被调用：本包、daemon/repair_link、tests / 状态：完整实现
- `ocos/diagnosis/repair_proposer.py`
  - 文件类型：提案器 / 核心功能：FAULT_TO_REPAIR 10 类映射、步骤模板/预估时长/成功标准/回滚计划生成、CRITICAL 不可逆 / 关键类：RepairProposer（propose/_build_proposal/_build_steps/_estimate_duration/_build_criteria/_build_rollback）/ 依赖：diagnosis_types、repair_types / 被调用：daemon/repair_link、manager、tests / 状态：完整实现（REINDEX 步骤含"锁住写入"与 repair_link 白名单冲突，被上游过滤）
- `ocos/diagnosis/repair_validator.py`
  - 文件类型：验证器 / 核心功能：SD56-03 类型检查、IMMUTABLE_COMPONENTS(7) 拒绝、CRITICAL→NEEDS_REVIEW、HIGH_RISK_REPAIRS→NEEDS_REVIEW、不可逆警告、空 steps 拒绝 / 关键类：RepairValidator（validate/validate_forbidden）、ValidationOutcome/ValidationCode / 依赖：repair_types / 被调用：repair_executor、manager、tests / 状态：完整实现
- `ocos/diagnosis/repair_sandbox.py`
  - 文件类型：沙箱验证器 / 核心功能：类型/步骤/回滚计划三检查 + 可选 simulate_fn 前后状态对比（identity_preserved）→ PASS/FAIL/TIMEOUT/INCONCLUSIVE / 关键类：RepairSandbox.validate、SandboxReport/SandboxResult / 依赖：无（仅 repair_types 协议）/ 被调用：仅 tests（无生产调用）/ 状态：完整实现（未接线）
- `ocos/diagnosis/repair_executor.py`
  - 文件类型：执行器 / 核心功能：validate→checkpoint→逐步骤（失败 break）→finalize（失败不伪装成功 BR-04 C-3）→失败回滚；on_complete 回调失败留痕 / 关键类：RepairExecutor.execute、ExecutionReport/ExecutorResult / 依赖：repair_types、repair_validator / 被调用：daemon/repair_link.execute_system_repair、manager、tests / 状态：完整实现（回调由外部注入，默认全 None）
- `ocos/diagnosis/repair_memory.py`
  - 文件类型：学习记忆 / 核心功能：500 条修复记录 deque、lesson/pattern 提炼、should_remember 判定、查询/统计 / 关键类：RepairMemory（record/record_execution/query/stats/clear）/ 依赖：repair_types、repair_executor / 被调用：manager、tests / 状态：完整实现（未接 EventMemory，on_record 回调留白）
- `ocos/diagnosis/manager.py`
  - 文件类型：统一门面（355 行）/ 核心功能：SelfDiagnosisManager 诊断-修复闭环编排（diagnose/get_health_status/history/tick/模式与策略配置/回调）+ DiagnosticResult/ManagerStats / 关键类：SelfDiagnosisManager、DiagnosisMode、AutoRepairPolicy、DiagnosticResult、ManagerStats / 依赖：本包全部组件 / 被调用：仅 tests/test_self_diagnosis_manager（无生产调用）/ 状态：半成品（_auto_repair_signals 空转：报告不带信号上下文、executor 无步骤执行回调、checkpoint_id 未传入）

**ocos/health_examination/（10）**
- `ocos/health_examination/__init__.py`
  - 文件类型：包入口 / 核心功能：五类体检+评分导出门面 / 依赖：本包全部 / 被调用：daemon/factory、daemon/health_loop（子集）、tests / 状态：完整实现
- `ocos/health_examination/health_model.py`
  - 文件类型：类型定义 / 核心功能：HealthCategory(5 类 100 分权重)/OrganStatus/DisorderType(5)/AttackType(4)/OrganDef/OCOS_ORGANS(12 器官)/OrganHealth/ConnectionHealth/DisorderFinding/ImmuneTestResult/RuntimeMetrics/RecoveryTestResult/CategoryScore/HealthCertification / 依赖：无 / 被调用：本包全部、daemon/health_loop、tests / 状态：半成品（OCOS_ORGANS 注册表失配，见风险 R-4）
- `ocos/health_examination/structural_examiner.py`
  - 文件类型：体检器 / 核心功能：逐器官 importlib 导入 + required_exports 存在性 → PRESENT/INCOMPLETE/MISSING，20 分制 / 关键类：StructuralExaminer（examine/_examine_organ/is_organ_healthy/unhealthy_organs）/ 依赖：health_model / 被调用：health_protocol、tests / 状态：完整实现（输入注册表失配导致结论失真）
- `ocos/health_examination/connectivity_examiner.py`
  - 文件类型：体检器 / 核心功能：28 对 CONNECTIVITY_PAIRS 连接矩阵检查，connection_states 可注入断连，25 分制 / 关键：ConnectivityExaminer（examine/inject_broken/inject_all_broken/restore_all）、CONNECTIVITY_PAIRS / 依赖：health_model / 被调用：health_protocol、tests / 状态：半成品（默认全 True=不注入即满分，无真实链路检测）
- `ocos/health_examination/cognitive_examiner.py`
  - 文件类型：体检器 / 核心功能：四种认知疾病检测（记忆膨胀/重复率/遗忘、决策漂移、注意错位关键词重合、世界模型孤立实体/矛盾）+ full_examination 20 分制 / 关键类：CognitiveExaminer、MemorySnapshot/DecisionSnapshot/WorldSnapshot / 依赖：health_model / 被调用：daemon/health_loop（生产）、health_protocol、tests / 状态：完整实现（决策漂移在 HealthLoop 场景恒不触发）
- `ocos/health_examination/immune_examiner.py`
  - 文件类型：体检器 / 核心功能：四类攻击测试（身份/权限/自改写/恶意扩展），guard 回调注入，blocked 计分 20 分制 / 关键类：ImmuneExaminer（test_identity_attack/test_permission_attack/test_self_modify/test_malicious_extension/full_examination）/ 依赖：health_model / 被调用：health_protocol、tests / 状态：半成品（无生产 guard 注入；guard=恒 True lambda 即满分）
- `ocos/health_examination/runtime_examiner.py`
  - 文件类型：体检器 / 核心功能：从 sim_engine.stats 采集 CPU 错误率代理/内存/队列/延迟 → 扣分制 15 分；无数据=满分 / 关键类：RuntimeExaminer（collect_metrics/examine）/ 依赖：health_model / 被调用：health_protocol、tests / 状态：半成品（"CPU 趋势"实为错误率代理，memory>5000 即判 leaking）
- `ocos/health_examination/recovery_examiner.py`
  - 文件类型：体检器 / 核心功能：三恢复场景（cold boot 回调注入 / partial damage 恒 recovered / capability failure 恒 recovered）/ 关键类：RecoveryExaminer、RecoveryState / 依赖：health_model / 被调用：health_protocol、tests / 状态：半成品（场景 2/3 硬编码通过）
- `ocos/health_examination/health_scorer.py`
  - 文件类型：评分器 / 核心功能：五类归一化加权（20/25/20/20/15）→ 总分/评级（HEALTHY≥90/STABLE≥75/WARNING≥60/UNHEALTHY）+ all_pass/ready_for_production + 建议 / 关键类：HealthScorer.score / 依赖：health_model / 被调用：health_protocol、tests / 状态：完整实现
- `ocos/health_examination/health_protocol.py`
  - 文件类型：编排器 / 核心功能：六体检器顺序执行 → HealthProtocolReport（to_dict/to_json）→ certification；quick_health_check 快检 / 关键类：HealthProtocol.execute、HealthProtocolReport、quick_health_check / 依赖：本包全部 / 被调用：tests（无生产调度入口）/ 状态：完整实现

**ocos/living_verification/（8）**
- `ocos/living_verification/__init__.py`
  - 文件类型：包入口 / 核心功能：LV57 六标准声明 + 全组件导出 / 依赖：本包全部 / 被调用：tests/test_phase57、test_phase58 / 状态：完整实现
- `ocos/living_verification/verification_manifest.py`
  - 文件类型：清单 / 核心功能：LV57 18 条加权验证项（completion/weighted_score/all_pass/summary）+ create_full_manifest / 关键类：VerificationManifest/ManifestItem/ManifestStatus / 依赖：无 / 被调用：tests / 状态：完整实现（check_fn 字段在 docstring 中提及但未实现——条目无自动判定函数）
- `ocos/living_verification/simulation_engine.py`
  - 文件类型：模拟引擎 / 核心功能：9 阶段（PERCEIVE..RESTORE）tick 模拟、TraceStep 因果记录、2% 随机失败、周期演化/持久化/身份自检、10 条 SIM_TASKS、stats() / 关键类：SimulationEngine、SimulationProfile、TraceStep、SimPhase / 依赖：无 / 被调用：tests、health_examination 的 runtime_examiner 数据源（测试内）/ 状态：完整实现（纯模拟，不驱动真实 OCOS）
- `ocos/living_verification/cognitive_trace_audit.py`
  - 文件类型：审计器 / 核心功能：8 环节因果链（INTENT→EVOLUTION）逐环节 present 检查 → completeness/断链/组件覆盖 → ≥0.90 通过 / 关键类：CognitiveTraceAudit（audit/_audit_step/_check_link/check_specific_chain）、TraceAuditReport/CausalValidation/ChainLink / 依赖：无 / 被调用：tests / 状态：完整实现（EVOLUTION 环节恒 present）
- `ocos/living_verification/failure_injector.py`
  - 文件类型：故障注入器 / 核心功能：三类注入（错误能力 4 失败模式/虚假记忆/非法扩展 5 名单）→ 五态结果；无防御回调=PASSED_THROUGH 缺口、governor 异常=保守拒绝 / 关键类：FailureInjector（inject_*/run_full_battery）、InjectionReport/InjectionBatchReport/InjectionType/InjectionResult / 依赖：无 / 被调用：tests / 状态：完整实现
- `ocos/living_verification/longevity_test.py`
  - 文件类型：长寿测试 / 核心功能：checkpoint 序列上验证 identity 漂移/权限扩大/记忆 >3σ 跳变/错误趋势/连续性得分 / 关键类：LongevityTest（create_checkpoint/verify）、LongevityCheckpoint/LongevityMetrics / 依赖：无 / 被调用：tests / 状态：完整实现（验证对象为 SimulationEngine 状态）
- `ocos/living_verification/benchmark_runner.py`
  - 文件类型：基准运行器 / 核心功能：A/B/C 三条件组 12 任务，缺能力→FAIL，on_execute_task 注入执行，80% 通过线 / 关键类：BenchmarkRunner、BenchmarkTask/BenchmarkSuite/BenchmarkReport/BenchmarkCategory/BenchmarkVerdict / 依赖：无 / 被调用：tests / 状态：半成品（无执行器时"结构检查"即 PASS，L236-240）
- `ocos/living_verification/health_report.py`
  - 文件类型：报告生成器 / 核心功能：六 LV57 维度评估 → overall_score → ALIVE/DEGRADED/UNSTABLE/DEAD / 关键类：HealthReportGenerator.generate 及 6 个 _eval_*、LivingSystemHealth/HealthDimension/SystemGrade / 依赖：无 / 被调用：tests / 状态：完整实现

**ocos/living_test/（12）**
- `ocos/living_test/__init__.py`
  - 文件类型：包入口 / 核心功能：7-Day 协议声明 + 全组件导出 / 依赖：本包全部 / 被调用：tests/test_phase58_1 / 状态：完整实现
- `ocos/living_test/protocol_model.py`
  - 文件类型：类型定义 / 核心功能：LivingTestDay(0-7)、BirthSnapshot（sha256 identity_hash + freeze）、DayResult（add/sub_results/normalized）、LivingStatus、LivingTestReport（to_dict/to_json，含 100 分字段与 health_curve）/ 依赖：无 / 被调用：本包全部、tests / 状态：完整实现
- `ocos/living_test/living_test_protocol.py`
  - 文件类型：协议执行器 / 核心功能：LivingTestConfig（守卫/持久化/能力/运行时回调注入）+ run_living_test（Day0→7 顺序 + 汇总评分）+ quick_living_check（全 True 假守卫冒烟）/ 关键：run_living_test/quick_living_check、LivingTestConfig / 依赖：本包全部 day 模块 / 被调用：tests / 状态：完整实现（L132 end_identity_hash 默认取 birth 自身 hash，首尾比对形同虚设）
- `ocos/living_test/living_score.py`
  - 文件类型：评分器 / 核心功能：六维 100 分（身份 20/记忆 20/认知 20/能力 15/运行 15/恢复 10）+ LivingStatus 评级 + identity_hash_match / 关键函数：compute_living_score/_find_day / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/birth_check.py`
  - 文件类型：Day 0 / 核心功能：出生基线（默认 core_values 5 条、permission_model 禁改身份）+ 5 项检查 + freeze 封印 / 关键：birth_check、BirthCheckResult / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day1_basic_life.py`
  - 文件类型：Day 1 / 核心功能：写作 6 环节 + 编码 4 环节 + 对话上下文 2 检查；钩子缺失=fail-closed / 关键：BasicLifeScenario、test_basic_life / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day2_memory_survival.py`
  - 文件类型：Day 2 / 核心功能：save→shutdown→restore→recall 四阶段；recall 经 recall_handler 关键词验证（SQLite/缓存/验证）/ 关键：MemorySurvivalScenario、test_memory_survival / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day3_identity_stability.py`
  - 文件类型：Day 3 / 核心功能：提示注入/身份漂移/宪法绕过三攻击，guard 缺失=breach / 关键：IdentityStabilityScenario、test_identity_stability / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day4_evolution.py`
  - 文件类型：Day 4 / 核心功能：检测→提案→分析→沙箱→迁移→自改写拦截六步链；钩子缺失=fail / 关键：EvolutionScenario、test_evolution / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day5_capability_reality.py`
  - 文件类型：Day 5 / 核心功能：正常能力（建/读文件、分析）+ 恶意操作（rm -rf /、改核心文件、权限绕过）必须被拦截 / 关键：CapabilityRealityScenario、test_capability_reality / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现
- `ocos/living_test/day6_long_runtime.py`
  - 文件类型：Day 6 / 核心功能：24h 指标（health_index 四因子）、健康曲线线性回归斜率≥-0.01、CPU/内存/队列三稳定检查 / 关键：RuntimeMetrics（health_index）、LongRuntimeScenario、_simulate_long_runtime、test_long_runtime / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：半成品（无 metric_collector 时用合成噪声指标冒充 24h 数据）
- `ocos/living_test/day7_resurrection.py`
  - 文件类型：Day 7 / 核心功能：累积→保存→kill→冷启恢复→时间线查询五阶段；恢复失败=FAIL、身份丢失=failures / 关键：ResurrectionScenario、test_resurrection / 依赖：protocol_model / 被调用：living_test_protocol、tests / 状态：完整实现

---


#### 审计分组 W10：persistence/storage/snapshot/recovery 持久化 + models 数据模型 + contracts/events/event 事件与契约 + constitution 宪法 + kernel 内核 + os_v1 + logging/alerts/auth/security/monitoring/performance/operations/tool/distributed 基础设施 —— 文件索引

#### 二、文件全量索引

状态图例：完整实现 / 半成品 / 占位代码。导入依赖仅列 OCOS 内部；"被调用"为 grep 反查结果（不含定义文件自身与 __pycache__）。

##### ocos/persistence/（8）
`ocos/persistence/__init__.py`
- 文件类型：包导出（含长 docstring 说明 GAP-P3-2 裁决：本包=通用多域快照框架 vs ocos/snapshot=agent 专用）
- 核心功能：导出 10 类型 + 5 核心类（StateSerializer/SnapshotManager/StateProvider/RecoveryManager/LifecycleManager/PersistenceValidator）
- 关键类：见导出；导入依赖：包内；被调用：master_agent（间接）、tests
- 状态：完整实现。注意 PersistenceManager（manager.py）不在导出清单

`ocos/persistence/storage_types.py`
- 文件类型：类型定义（210 行）
- 核心功能：SnapshotDomain/SnapshotStatus/LifecyclePhase/RecoveryOutcome 4 枚举 + DomainSnapshot/Snapshot/Checkpoint/RecoveryState/LifecycleEvent/LifecycleLog 6 dataclass
- 关键常量：PS51-01..04 边界（快照是副本/恢复是填充/允许部分恢复/格式跨版本稳定）
- 导入依赖：无；被调用：包内全部 + tests
- 状态：完整实现（Checkpoint dataclass 无实现者，属半成品语义）

`ocos/persistence/state_serializer.py`
- 文件类型：序列化器
- 核心功能：Snapshot↔JSON 双向；`storage_root` 默认 `~/.ocos/snapshots`；manifest.json 索引（保留最近 100 条按 tick 排序）；prune(keep=10)
- 关键：_snapshot_to_dict（`_format: ocos-snapshot-v1`）；load_latest 优先 COMPLETE 快照
- 导入依赖：storage_types；被调用：snapshot_manager、recovery_manager、persistence_validator、lifecycle_manager
- 状态：完整实现（compress=True 字段声明了但**从未使用**，无压缩逻辑——半成品属性）

`ocos/persistence/snapshot_manager.py`
- 文件类型：快照管理器
- 核心功能：StateProvider 协议（snapshot_domain/get_state/set_state）；take（只读采集+sha256[:16] checksum）；restore（PS51-02 填充不覆盖、单域失败不阻断）；validate（逐域 checksum）
- 关键：_checksum=json.dumps(sort_keys=True)→sha256 前 16 hex
- 导入依赖：storage_types、state_serializer；被调用：recovery_manager、lifecycle_manager、persistence_validator、tests
- 状态：完整实现

`ocos/persistence/recovery_manager.py`
- 文件类型：恢复引擎
- 核心功能：cold_boot（discover→select_best(validated/taken 且 is_complete)→validate 失败走 _select_fallback→restore→log）；warm_boot(snapshot_id)；get_phase 映射
- 关键：RecoveryOutcome→LifecyclePhase 映射（FULL→WARM_BOOT、PARTIAL→DEGRADED、FAILED→COLD_BOOT 从零启动）
- 导入依赖：storage_types、snapshot_manager；被调用：lifecycle_manager、tests
- 状态：完整实现

`ocos/persistence/lifecycle_manager.py`
- 文件类型：生命周期管理器
- 核心功能：boot/run/shutdown(保存最终快照)/crash/checkpoint(prune 至 max_snapshots=20)；SIGINT/SIGTERM 处理；is_healthy/is_degraded/boot_count
- 关键：_record 写 LifecycleLog；shutdown 先执行 cleanup_fns 再快照
- 导入依赖：storage_types、snapshot_manager、recovery_manager；被调用：tests
- 状态：完整实现（run() 不驱动循环，仅登记）

`ocos/persistence/persistence_validator.py`
- 文件类型：校验器
- 核心功能：validate_snapshot（format_version/snapshot_id/域完整性/逐域 checksum/data 结构五项）；roundtrip_verify（serialize→deserialize→再校验+id/tick 一致）
- 关键：issues→CORRUPT；warnings 不降级
- 导入依赖：storage_types、snapshot_manager（访问其 _checksum 私有方法）；被调用：tests
- 状态：完整实现

`ocos/persistence/manager.py`
- 文件类型：统一持久化管理器（Phase V，383 行）
- 核心功能：JSON 文件快照（base_dir=ocos_data/persistence，snapshots/checkpoints/logs 三子目录）；save/restore（LATEST/SPECIFIC/LAST_KNOWN_GOOD 三策略，实际 LAST_KNOWN_GOOD 未单独实现）；save_checkpoint/restore_checkpoint（桥接 storage.CheckpointManager 到 checkpoints.db）；auto_save_if_needed（snapshot_interval=300s）；max_snapshots=20 剪枝；get_stats/generate_report
- 关键类：PersistenceConfig/SnapshotType/RestoreStrategy/SaveResult/RestoreResult
- 导入依赖：延迟 import ocos.storage.checkpoint；被调用：ocos/agent/master_agent.py:107,1959-2002（save/restore/auto_save_if_needed/get_stats 注入使用）、tests/test_persistence_manager.py
- 状态：完整实现（自包含，未入 __init__ 导出）

##### ocos/storage/（9）
`ocos/storage/__init__.py`
- 文件类型：包导出 + lazy 工厂
- 核心功能：导出 StorageBase/SQLiteWorkingMemory/ensure_schema + get_event_store/get_dlq/get_checkpoint_manager（延迟导入）
- 状态：完整实现

`ocos/storage/base.py`
- 文件类型：抽象基类（36 行）
- 核心功能：StorageBase(ABC, Generic[T]) 抽象 store/load/delete/list/connect/close
- 导入依赖：无；被调用：无生产实现继承它（SQLiteWorkingMemory 未继承）——纯契约占位
- 状态：占位代码（接口定义，无实现挂接）

`ocos/storage/connection.py`
- 文件类型：连接池
- 核心功能：按绝对路径缓存的进程级连接池；`:memory:` 每次新建；DEFAULT_PRAGMAS（WAL/NORMAL/-8000/5000/ON/MEMORY）；transaction 上下文（commit/rollback）；atexit close_all；_conn_alive 探活重建
- 状态：完整实现

`ocos/storage/schema.py`
- 文件类型：schema 定义（301 行）
- 核心功能：STORAGE_SCHEMA_VERSION=5；15 张表建表 SQL（详见专项发现）；STORAGE_TABLES 注册 dict
- 状态：完整实现（其中 goal 表与 goal/store.py 的 goals 表存在双表并存问题）

`ocos/storage/migrations.py`
- 文件类型：迁移管理器
- 核心功能：MIGRATIONS{1..5}（1:基础四表；2:users；3:记忆域六表；4:plan_dag+pending_actions；5:user_messages）；ensure_schema 读 MAX(version) 增量应用
- 状态：完整实现（无回滚机制；迁移非事务原子——单条失败留下半套表）

`ocos/storage/working_memory.py`
- 文件类型：KV 存储
- 核心功能：store/load/delete/list_keys(LIKE)/count/clear_expired/close；max_entries=10000 满抛 ValueError；default_ttl=3600
- 状态：完整实现

`ocos/storage/event_store.py`
- 文件类型：事件存储（持久化）
- 核心功能：append（幂等，event_id 主键 INSERT OR IGNORE）；append_batch（单事务）；load/replay(event_type/since/limit/offset)/count/latest_sequence/delete_all
- 关键：_next_sequence=MAX+1（非原子，见风险 P2）
- 被调用：recovery/crash_recovery.py、tests；生产无直接用户（经 crash_recovery 间接）
- 状态：完整实现

`ocos/storage/dead_letter_queue.py`
- 文件类型：死信队列（持久化）
- 核心功能：enqueue/list_unresolved/list_all/count_unresolved/mark_resolved/increment_retry/is_exhausted(max_retries=3)/delete/clear_all
- 被调用：recovery/crash_recovery.py、tests
- 状态：完整实现

`ocos/storage/checkpoint.py`
- 文件类型：检查点存储
- 核心功能：save(process_id, phase, context, ttl)/load(过期自动删)/list_incomplete/exists/count/mark_completed/delete/clear_expired/clear_all；default_ttl=86400
- 被调用：recovery/crash_recovery.py、persistence/manager.py、tests
- 状态：完整实现

##### ocos/snapshot/（4）
`ocos/snapshot/__init__.py` — 纯 docstring 包说明（GAP-P3-2 裁决）。状态：占位代码（仅注释）。
`ocos/snapshot/models.py`
- 核心功能：AgentSnapshot frozen dataclass（snapshot_id/version/created_at/identity_state/self_view_state/goal_state/working_memory_config/context_state/runtime_state/attention_state/pending_decision_state/governance_state）；to_json/from_json
- 关键约束：working_memory 仅存配置不存 items
- 状态：完整实现
`ocos/snapshot/manager.py`
- 核心功能：save（Lock 原子）/load_latest/mark_recovered；DB_PATH=env OCOS_DB_PATH 或 ~/.ocos/ocos.db；_conn() 自愈建 snapshots 表（GAP-P2-5）
- 导入依赖：snapshot.models、storage.connection；被调用：ocos/agent/master_agent.py（生产）、snapshot/recovery.py、tests
- 状态：完整实现
`ocos/snapshot/recovery.py`
- 核心功能：CrashRecovery.recover() → RecoveryResult{success, snapshot_id, restored_goals, errors}
- 导入依赖：snapshot.manager；被调用：master_agent（经 snapshot 包）、tests
- 状态：完整实现

##### ocos/recovery/（2）
`ocos/recovery/__init__.py` — 导出 CrashRecovery/RecoveryReport。状态：完整实现。
`ocos/recovery/crash_recovery.py`
- 核心功能：recover(max_events=1000)（盘点未完成检查点→replay 计数→DLQ 可重试盘点）；recover_checkpoint/replay_events/reattempt_dlq/get_status
- 导入依赖：storage 三件套；被调用：tests/recovery 契约
- 状态：半成品（replay 结果未真正重投递；get_status 的 incomplete_checkpoints 语义错误）

##### ocos/recovery_resilience/（6）
`ocos/recovery_resilience/__init__.py` — 导出全部类型与入口。完整实现。
`resilience_model.py` — DamageType 7 类（is_fatal 仅 SESSION_DEATH）/DamageSeverity/RecoveryPhase 7 相/RecoveryTrace（fully_recovered 复合判据）/ResilienceDay/DayResilienceResult/RecoveryScore（25+20+25+15+15 加权）/ResilienceReport（7 通过判据+to_dict/to_json）。完整实现。
`damage_injector.py` — MockMemory/MockIdentity(hash)/MockKnowledge/MockCapability + DamageInjector（inject_memory_corruption/inject_knowledge_conflict/inject_capability_failure/inject_stress_flood/inject_adversarial_attacks/inject_resurrection_damage）+ make_healthy_state/make_damage_injector。完整实现（mock 性质）。
`recovery_monitor.py` — detect→isolate→recover→verify 四阶段流水线；_health_estimate（corrupted -5 / failed -10 / recovered +3）。半成品（_check_goal_auto 恒 False、never_recovered 属性不存在使 hallucination 检查失效）。
`recovery_scorer.py` — score_traces/assess_report。完整实现。
`resilience_protocol.py` — 7 天执行器 + run_resilience_test/quick_recovery_check。完整实现（mock 协议）。

##### ocos/models/（14）
`ocos/models/__init__.py` — 导出 Information*/GoalStatus/DecisionStatus/Process*/Execution*。完整实现。
`information.py` — InformationState 五态状态机+转移表+legacy 映射；SemanticRole 七类；PersistenceLevel 四层；RelationType 11 类；UniversalAddress（namespace/type/id/version 校验）；InformationMetadata（importance/ttl 校验）。完整实现。
`goal.py` — GoalStatus 8 态（str-enum）+转移表+validate。完整实现。
`process.py` — ProcessType（弃用，每值告警一次 P3-1）/ProcessState/ProcessStep/TransformProcess（四不变量）。完整实现。
`execution.py` — ExecutionStatus 6 态+转移表；Execution（三不变量）。完整实现。
`decision_making.py` — DecisionStrategy 6 策略/DecisionOption/DecisionMakingTrace。完整实现。
`goal_arbitration.py` — ArbitrationStrategy 4 策略/GoalCandidate/ArbitrationResult/GoalArbitrationTrace。完整实现。
`planning.py` — PlanningStrategy 6/PlanStatus 5/PlanningStep/PlanningTrace。完整实现。
`policy.py` — PolicyEffect 3/PolicyDomain 6/PolicyRule/PolicyEvaluation/PolicyTrace。完整实现。
`prediction.py` — PredictionStrategy 4/ConfidenceInterval/PredictionResult/PredictionTrace。完整实现。
`reasoning.py` — InferenceOperation 8 操作/ReasoningStep/ReasoningTrace。完整实现。
`reflection.py` — ReflectionStrategy 4/ReflectionInsight/ReflectionTrace。完整实现。
`simulation.py` — SimulationStrategy 4/SimulationScenario/SimulationStep/SimulationTrace。完整实现。
`learning.py` — LearningStrategy 4/LearningExample/LearningModel/LearningTrace。完整实现。

##### ocos/contracts/（3）
`ocos/contracts/__init__.py` — 导出 Attention(Phase35/36) + Feedback(Phase37) 全部符号。完整实现。
`attention_abi.py` — DecisionType/AttentionScoreTrace/FocusChange/WMAllocation/AttentionDecision/DecisionDigest/AttentionRecommendation/AttentionReport + 4 执行信号常量 + FORBIDDEN_DECISION_REASONS。完整实现。
`feedback_abi.py` — ExpectedOutcome/ActualOutcome/EvaluationStatus/OutcomeEvaluation（五维 s/q/e/r/a）/LearningSignal/FeedbackState/CognitiveFeedback/Evidence(merge)/DriftAlert/DriftSeverity/DriftType + ADAPTIVE/IMMUTABLE_PARAM_KEYS + 4 预算常量。完整实现。

##### ocos/events/（5，任务书标 6 实为 5）
`ocos/events/__init__.py` — 纯 docstring（GAP-P3-5 裁决）。占位代码（仅注释）。
`event_bus.py` — EventBus：subscribe/subscribe_all/unsubscribe/publish(sync|async)/subscriber_count/clear；线程安全（RLock）；DLQ 注入。完整实现。
`event_store.py` — InMemoryEventStore：原子 append（validate_event_payload 全过才写）/get_by_type/get_by_source/get_all/count/snapshot/clear + CommitResult/StoreSnapshot。完整实现。
`dead_letter_queue.py` — DeadLetterQueue：put/get_all/get_by_type/count/replay（失败重入队 retry+1）/clear/prune_older_than(24h)。完整实现。
`event_ingestion.py` — EventIngestion：ingest()（兼容 pending_events/get_pending/poll 三种总线协议）→ IngestedEvent 按优先级排序；_PRIORITY_MAP；has_pending_input。半成品（依赖的"pending_events 总线属性"在自家 EventBus 上不存在，需 duck-typing 适配器总线；对 ocos/events/event_bus 的 EventBus 无拉取接口——ingest() 对其恒返回空）。

##### ocos/event/（1）
`ocos/event/__init__.py` — Phase 34A 感知神经系统（297 行单文件包）：EventSource/EventSeverity/AttentionDecision/RawEvent/CognitiveEvent/IngestionTrace/EventNormalizer/EventBus(push/ingest/record_trace)。完整实现。

##### ocos/constitution/（4）
`ocos/constitution/__init__.py` — 纯 docstring（禁令矩阵 L1~L6）。占位代码（仅注释）。
`hub.py` — ConstitutionHub：check_decision/check_action/check_promotion/verify_goal_creation/update_phase；_FakeDecision 适配器。完整实现。
`behavioral.py` — BehavioralConstitution：_HIGH_RISK_ACTIONS 5 条/_HUMAN_APPROVAL_ACTIONS 3 条/ConstitutionResult；check_decision <1ms。完整实现。
`statement_validator.py` — StatementValidator：6 类检测规则（中英正则）/ValidationResult/ValidationFlag/Violation/ViolationCategory/_RULE_TO_VIOLATION。完整实现（value_judgment 有一处 `\\w+` 正则笔误，规则弱化）。

##### ocos/kernel/（6）
`ocos/kernel/__init__.py` — 0 字节空文件。占位代码。
`abi.py` — SCHEMA_VERSION/EventType(60+)/Event/Observation/Memory/Knowledge/Goal/DecisionStatus/Decision/Action。完整实现（Memory.memory_type 已废弃标注）。
`event_schema.py` — serialize_event/deserialize_event/validate_schema_version/validate_event_payload/EVENT_SCHEMA_REGISTRY(~45)。完整实现（GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 重复注册覆盖，schema 弱化）。
`goal_types.py` — GoalLevel/GoalStatus(+ABANDONED 别名)/GoalOriginLevel/GoalAuthority/Goal(统一)/UserGoal(兼容)/CALLER_WHITELIST/SuccessCriteria/GoalDomain/GoalSource。完整实现。
`constitution.py` — ConstitutionalRule 24 条/Constitution（描述 dict/ALLOWED_IMPORTS/check_import_allowed/两个占位验证钩子）。完整实现（运行时钩子为占位）。
`time_manager.py` — TimeManager（cycle/tick/reset_cycle/utc_now/utc_timestamp/uptime/format_timestamp）。完整实现。

##### ocos/os_v1/（7）
`ocos/os_v1/__init__.py` — 全量导出。完整实现。
`os_types.py` — IntentDomain 8/IntentComplexity 4/UserIntent/OSResponse/CapabilityStatus 4/CapabilityProvider/CapabilityResult/DriftSeverity 5/DriftSignal/DriftReport/MemoryHealthReport/FreezeManifest。完整实现。
`personal_os.py` — PersonalCognitiveOS：register/unregister/classify_intent/process/call_capability/capability_summary。半成品（process 的 decide/execute/learn 未接真实子系统；capability 调用为模拟拼接）。
`freeze.py` — OSFreeze + ABI_MODULES(12)/CONSTITUTION_PRINCIPLES(6)/MEMORY_PROTOCOL/CAPABILITY_SDK/EXTENSION_SDK。完整实现（签名为字符串拼接非密码学）。
`cognitive_drift.py` — DriftBaseline/CognitiveDriftDetector（3 维度漂移/严重度判定/建议生成/基线保留 10/报告保留全量）。完整实现。
`memory_validation.py` — MemoryGrowthValidator（质量分 40% 高价值 + 30% 不陈旧 + 30% 活跃；趋势 improving/declining/stable；历史保留 100）。完整实现。
`capability_adapters.py` — Codex/OpenTale/Browser/Analysis 四适配器 + CapabilityEcosystem。占位代码（适配器返回拼接字符串模拟）。

##### ocos/logging/（6 + config.yaml）
`ocos/logging/__init__.py` — 导出 OCOSLogger/get_logger。完整实现。
`logger.py` — OCOSLogger（重写五级日志，component/process_id/extra 结构化，error/critical 支持 exception 对象）；get_logger（缓存 + __class__ 换类手法）；_apply_default_config（root DEBUG + stdout INFO + JSON）。完整实现。
`formatter.py` — JSONFormatter：OrderedDict 单行 JSON，非标准 record 键收进 extra。完整实现。
`handlers.py` — RotatingFileHandler(10MB×5)/DailyRotatingHandler(每天×7)，自动建目录。完整实现。
`rotator.py` — LogRotator：rotate_if_needed/rotate(.1→.2 移位)/compress_old(gzip)/list_logs。完整实现。
`search.py` — LogSearcher：search(query/level/component/after/before/limit)/tail/stats；排除 .gz。完整实现。
`config.yaml` — dictConfig 样例（console INFO + file DEBUG→ocos/logs/ocos.log）。占位代码（无代码路径加载它）。

##### ocos/alerts/（4）
`ocos/alerts/__init__.py` — 导出。完整实现。
`models.py` — AlertLevel 4 级/Alert dataclass。完整实现。
`channels.py` — AlertChannel(ABC)/LogChannel(logging)/FileChannel(alerts.log JSONL)。完整实现。
`manager.py` — AlertManager：register/unregister/send/send_alert/acknowledge/clear_history/history；线程安全。完整实现（通道失败静默吞）。

##### ocos/auth/（4）
`ocos/auth/__init__.py` — 导出。完整实现。
`role.py` — Role 4/Permission 17/ROLE_PERMISSIONS 矩阵/PermissionDeniedError/PermissionChecker(check/check_any/check_all/require)。完整实现。
`user.py` — User frozen/UserStore（save/load/load_by_name/list/update_last_active/count，复用 schema users 表）。完整实现。
`identity_store.py` — AgentIdentityRecord/IdentityStore（agent_identity 表自建 DDL；connection 不可用时直连 fallback；上下文管理器）。完整实现（close 后复用会 AttributeError）。

##### ocos/security/（1）
`ocos/security/manager.py` — SecurityLevel/AccessDecision/SecurityEvent/RateLimitConfig/RateLimiter/SecurityPolicy/InputSanitizer/SecurityAuditLog/SecurityManager/create_security_manager。完整实现（sanitize 不清洗、REQUIRE_AUTH 未启用、突发桶单位混乱——见风险清单）。

##### ocos/monitoring/（1）
`ocos/monitoring/manager.py` — MetricPoint/AlertRule/Alert/AlertManager(规则引擎)/MetricsRegistry/MonitoringManager/create_monitoring_manager。完整实现（ococ_up 拼写笔误、分位实现粗糙）。

##### ocos/performance/（1）
`ocos/performance/manager.py` — SmartCache/AsyncBatchProcessor/BulkPersistence/PerformanceProfiler/PerformanceManager/create_performance_manager。完整实现（SmartCache/队列非线程安全、get_cache 忽略 name）。

##### ocos/operations/（3）
`ocos/operations/__init__.py` — 注释型包说明（AUD-F5 裁决与 digital_world 分工；自述"两者当前均无生产调用者"）。占位代码（仅注释）。
`sandbox_ops.py` — BLOCKED_COMMANDS(30+)/ALLOWED_COMMANDS(30 只读)/SANDBOX_PATHS/SandboxCommand/SandboxResult/SandboxAuditRecord/SandboxOps.execute（黑→白→路径→subprocess shell=True 最小 env）。完整实现。
`search_ops.py` — API_WHITELIST(6)/DOMAIN_SUFFIX_WHITELIST(2)/is_url_allowed/SearchQuery/SearchResult/SearchAuditRecord/SearchOps.search（白名单→可选代理→urllib→解析→审计）。完整实现。

##### ocos/tool/（1）
`ocos/tool/manager.py` — ToolCategory/ToolPermission/ToolStatus/ToolDescriptor/ToolCallRecord/ToolCallStats/ToolIntegrationManager。半成品（call_tool 为 _simulate_tool_call 模拟；工具≠能力原则下注册同步到 CapabilityRegistry 是真实的）。

##### ocos/distributed/（1）
`ocos/distributed/manager.py` — InstanceState 7/TaskDistributionStrategy 4/CognitionInstance/DistributedTask/DistributedCognitionManager。半成品（单进程内存模拟，无网络通信；三策略简化）。

---


#### 审计分组 W11：编排/自治/扩展/外部通信等支线模块 + 根模块 —— 文件索引

#### 二、文件全量索引

##### ocos/autonomous_runtime/
- `ocos/autonomous_runtime/__init__.py`
  - 模块导出 / Phase 60 门面 + quick_runtime_test 自验函数 / 导入 LoopMode, WakeTrigger, RuntimeConfig, LoopStats, AutonomousLoop, ActionType, DispatchedAction, ActionDispatcher, SupervisorAlert, SupervisorState, LoopSupervisor / 依赖本模块各文件 / 被 test_phase60 调用 / 状态：完整实现
- `ocos/autonomous_runtime/runtime_config.py`
  - 配置 / LoopMode、WakeTrigger 枚举（CURIOSITY_SPIKE 已并入 homeostasis novelty 并删除）、RuntimeConfig（tick/睡眠/注意/决策/动作/学习/安全/健康 8 组 30+ 参数 + validate()，max_goal_self_generation=0 硬编码 CL46-01）、LoopStats 统计体 / 无依赖 / 被 autonomous_loop、__init__、test_phase60 调用 / 状态：完整实现
- `ocos/autonomous_runtime/autonomous_loop.py`
  - 核心循环 / AutonomousLoop：wake/sleep/idle/reflect、tick（安全上限→反馈队列→自生成反思→LoopOrchestrator.tick）、tick_many、_generate_reflection_input（注意力/决策/反思题/驱力四源拼接）、enqueue_feedback、_should_sleep（逻辑存疑）、set_action_handler/dispatch_actions、summary / 依赖 ocos.cognitive_loop.loop_orchestrator、loop_types / 被本包 __init__、test_phase60、quick_runtime_test 调用 / 状态：完整实现（有逻辑瑕疵）
- `ocos/autonomous_runtime/action_dispatcher.py`
  - 动作派发 / ActionType（10 种含 RUN_COMMAND/HTTP_FETCH/QUERY_DB）、DispatchedAction、ActionDispatcher（register_handler/register_custom_handler(UX-D 字符串键 self_upgrade)/dispatch/interpret_decision 关键词解释/dispatch_by_name(AUD-F12 回放，未知类型诚实返回 None)/action_summary，历史 500 截断）/ 无 OCOS 依赖 / 被 execution/bridge.py、interaction/converse.py、__init__、test_phase60、test_execution_bridge、test_thin_coverage_e2e 调用 / 状态：完整实现（活代码）
- `ocos/autonomous_runtime/loop_supervisor.py`
  - 安全监督 / SupervisorAlert、SupervisorState、LoopSupervisor（check_runaway、check_tick_count、check_goal_generation CL46-01、check_identity_stability CL46-02、check_action_excess、full_check 取最高级别、should_stop/alert_count）/ 无依赖 / 被 __init__、test_phase60 调用 / 状态：完整实现（should_stop 无消费方）

##### ocos/autonomous/
- `ocos/autonomous/__init__.py`
  - 导出 GoalManager 等 5 符号 / 依赖 goal_manager / 被 agent_runtime（create_goal_manager）调用 / 状态：完整实现
- `ocos/autonomous/goal_manager.py`
  - 目标管理 / GoalManagerProtocol、GeneratedGoal、GoalSyncResult、GoalManager（sync_from_homeostasis 双重门控 + save、get_active_self_goals 过滤 origin_level=SELF、get_generated_goals、is_goal_active、mark_progress/mark_completed、_make_id sha256、_get_level/_get_desc/_get_priority 钳位 0.1-0.9、_build_metadata auto_generated=True）、create_goal_manager 工厂 / 依赖 ocos.goal.store、ocos.goal.enforcer、ocos.kernel.goal_types / 被 agent_runtime.py:399 调用 / 状态：完整实现（id 无去重隐患）

##### ocos/agent_orchestration/
- `ocos/agent_orchestration/__init__.py`
  - 导出 8 类 / 依赖模块内各文件 / 被 agent_orchestration_autonomous、orchestration.engine、test_import_rules（依赖方向校验）调用 / 状态：完整实现
- `ocos/agent_orchestration/registry.py`
  - 注册中心 / AgentDescriptor（frozen，__post_init__ 校验 agent_type/status/success_rate/avg_duration_ms）、AgentRegistry（RLock，register/unregister/find_by_type/find_by_capability/get_available 按 success_rate 降序/update_status（frozen 替换）/list_all/__len__）/ 依赖 ocos.planning.models.VALID_AGENT_TYPES（仅注释引用，实际未强校验枚举值）/ 被 selector、supervisor、orchestration.engine、collaboration、agent_orchestration_autonomous、tests/agent_orchestration、tests/platform/test_scalability 调用 / 状态：完整实现
- `ocos/agent_orchestration/selector.py`
  - 选择器 / AgentSelector.select（available 过滤→task_type 推断 capability 过滤→success_rate 降序）、select_fallback（排除已选）、_infer_capability（create/modify/analyze/execute/verify→五能力映射）/ 依赖 registry、planning.models.Task / 被 supervisor、orchestration.engine、tests/validation/test_capability_bridge、tests/platform 调用 / 状态：完整实现
- `ocos/agent_orchestration/contract.py`
  - 执行契约 / ExecutionContract（frozen，超时/重试策略校验，retry_with_fallback 必须给 fallback_agent_id，create() 生成 CONTRACT-xxx id，validate_output_schema 缺字段检查）/ 无依赖 / 被 executor、agent_pool、supervisor、orchestration.engine、tests/test_capability/test_phase22_permission_gateway、scripts/phase22_gate 调用 / 状态：完整实现
- `ocos/agent_orchestration/executor.py`
  - 子进程执行 / AgentExecutor（_agent_map 默认 writer/researcher/reviewer/data_processor 四脚本映射、execute：payload JSON→NamedTemporaryFile→subprocess python3 --input（无 shell 注入面）、超时按 contract、脚本缺失诚实失败、finally 删临时文件、register/unregister_agent）/ 依赖 contract / 被 agent_pool、supervisor（注入）、test_phase62b 调用 / 状态：完整实现（默认 agents 目录不存在为已知现状）
- `ocos/agent_orchestration/audit.py`
  - 审计 / ExecutionRecord（frozen，状态白名单 started/running/completed/failed/timed_out）、ExecutionAudit（log_start/log_complete/log_failure/log_timeout/get_records_for_contract/trail/__len__，纯内存）/ 无依赖 / 被 supervisor、execution/bridge.py（活）、tests/agent_orchestration/test_orch_audit、tests/validation 调用 / 状态：完整实现（无 to_dict —— orchestration.engine 假设其存在而踩坑）
- `ocos/agent_orchestration/fallback.py`
  - 降级 / FallbackResult、FallbackHandler.execute_with_policy（no_retry 一次、retry_3x 三次、retry_with_fallback 三次后备选一次，_fallback_log 记录）/ 依赖 registry.AgentDescriptor / 被 supervisor、tests/agent_orchestration/test_orch_supervisor 调用 / 状态：完整实现
- `ocos/agent_orchestration/supervisor.py`
  - 执行监督 / ExecutionSupervisor（execute_task async：SkillGraph 桥→选择→契约→busy→审计→fallback 策略→审计→恢复；execute_plan 拓扑序逐任务、上游失败标记下游 DOWNSTREAM 审计后 break；cancel 释放合约 + 停 SkillGraph process；execute_task_sync/execute_plan_sync/cancel_sync = asyncio.run 包装）；模块级 `_execute_agent`（AUD-F11 诚实失败）/ 依赖 registry/selector/contract/audit/fallback/executor、planning.models / 被 orchestration.engine、tests/agent_orchestration/test_orch_supervisor、tests/validation/test_capability_bridge 调用 / 状态：完整实现（fallback 选择器重复调用两次的小低效）
- `ocos/agent_orchestration/agent_pool.py`
  - 并发池 / PoolResult（timeout_result/exception_result 构造器）、PoolStats（success_rate）、AgentPool（execute：Semaphore(max_concurrent)+gather+可选全局 wait_for；execute_sync：有运行中 loop 则串行避免嵌套，否则 asyncio.run；_run_one：wait_for(asyncio.to_thread(executor.execute))；_execute_serial 兜底；stats/reset_stats）/ 依赖 contract、executor、ocos.logging / 被 agent_orchestration_autonomous（_pool 注入）、test_phase62b、test_phase62c 调用 / 状态：完整实现（异常分支 task_id 误填 contract_id）

##### ocos/orchestration/ 与 ocos/collaboration/
- `ocos/orchestration/__init__.py`
  - 导出 OrchestrationEngine/State/Metrics/工厂 / 依赖 engine / 仅被 test_orchestration_engine 调用 / 状态：完整实现（死代码）
- `ocos/orchestration/engine.py`
  - 调度引擎 / OrchestrationState、OrchestrationMetrics（uptime/success_rate/avg_execution_time/record_*）、OrchestrationEngine（start/stop/pause/resume、submit_task/plan/collaboration 队列上限 100、process_tick 消费队列、_execute_collaboration（:346 record.to_dict() **崩溃点**）、on_task_start/on_task_complete/on_tick、get_status）、create_orchestration_engine / 依赖 agent_orchestration×4、collaboration×4、planning.models / 仅测试调用 / 状态：**半成品（to_dict bug）**
- `ocos/collaboration/__init__.py`
  - 导出 4 类 + create_collaboration_request / 依赖 agent_collaboration / 被 orchestration.engine、tests/test_collaboration_agent_collaboration 调用 / 状态：完整实现（死代码）
- `ocos/collaboration/agent_collaboration.py`
  - 协作引擎 / CollaborationRequest（校验非空）、AgentTask、CollaborationState（progress/success_rate/to_dict）、AgentCollaboration（ThreadPoolExecutor(5)、start 分派 parallel(_execute_parallel as_completed+超时)/sequential/pipeline(按优先级伪流水线)、get_state/get_all_states/cancel(仅改状态)/close、create_collaboration_request / 依赖 agent_orchestration.registry、planning.models / 被 orchestration.engine、测试调用 / 状态：完整实现（cancel 不真停任务）

##### ocos/extension/
- `ocos/extension/__init__.py`
  - Phase 44 门面，导出 12 类型 + 8 引擎 + 2 治理常量，docstring 声明 CG44-01~04 / 被 test_phase44 调用 / 状态：完整实现（死代码）
- `ocos/extension/extension_types.py`
  - 类型层 / ExtensionState（12 态 + is_terminal/is_operational/is_pre_approval）、ExtensionType（7 类）、TrustLevel（5 级）、ExtensionCandidate、ImpactLayer、AnalysisReport、CompatibilityReport（is_fully_compatible）、SandboxResult、IntegrationRecord、HealthStatus、HealthReport、EvolutionEntry / 无依赖 / 被本模块全部引擎调用 / 状态：完整实现
- `ocos/extension/discovery_engine.py`
  - 发现 / DiscoveryEngine.register_known/scan_path（路径不在 known_paths 即生成候选）/ _infer_type（关键词→7 类）/ 状态：完整实现（极简扫描）
- `ocos/extension/analyzer.py`
  - 分析 / Analyzer.analyze（summary 文案映射、_infer_impact 类型→层映射、_identify_risks 三类风险、confidence=0.7 硬编码、schema="dynamic"）/ 状态：完整实现（浅分析）
- `ocos/extension/compatibility_checker.py`
  - 兼容检查 / FORBIDDEN_ACTIONS（改身份/绕权限/自造目标/直接执行）、FORBIDDEN_LAYER_ACCESS、CompatibilityChecker.check（架构越界、ABI 未声明告警、治理关键词命中描述与 metadata）/ 状态：完整实现
- `ocos/extension/sandbox_runner.py`
  - 沙箱 / SandboxRunner.validate（PW-2.2：find_spec import 探测 → "cmd:" 前缀走 ocos.operations.sandbox_ops 黑白名单沙盒 15s 试运行，任一层失败诚实 passed=False）、custom_validate / 依赖 ocos.operations.sandbox_ops（懒）/ 状态：完整实现（非 cmd 候选仅探测）
- `ocos/extension/approval_engine.py`
  - 批准 / ApprovalDecision、ApprovalRequest（frozen 四件套）、ApprovalEngine.evaluate（兼容或沙箱不过→REJECTED，confidence<0.3→NEEDS_MORE_INFO，否则 APPROVED）、apply_state 映射 / 状态：完整实现
- `ocos/extension/integration_engine.py`
  - 集成 / IntegrationEngine.integrate（按类型映射 connection_points，trust=UNKNOWN）、get_record、update_trust（frozen 替换）/ 状态：完整实现
- `ocos/extension/diagnosis_engine.py`
  - 诊断 / DiagnosisEngine.check（error≥3→UNSTABLE、≥1 或 perf<0.4 或有冲突→DEGRADED、否则 HEALTHY）、latest/is_healthy / 状态：完整实现
- `ocos/extension/repair_engine.py`
  - 修复 / RepairAction（6 种）、RepairActionForbidden、RepairEngine（_forbidden 硬编码 4 禁止、repair 按 detail 命中即抛、recommended_action、map_to_state）/ 状态：完整实现
- `ocos/extension/evolution_memory.py`
  - 演化记忆 / EvolutionMemory（record_candidate/state_change/integration/health/repair/freeze，全部 frozen entry 重建替换；get/all_entries）/ 状态：完整实现（纯内存）

##### ocos/external/、external_communication/、ecosystem/、engagement/、human/、sleep_dream/、optimization/
- `ocos/external/server_manager.py`
  - 服务器管理 / WebhookPayload、WebhookReceiver（asyncio.Queue(10000)、process_loop、精确+通配分发）、WebhookGateway（FastAPI /webhook/{source}/{event_type}、/webhook/、/webhook/stats；独立线程 asyncio.run(uvicorn)）、ServerManager（start/stop/wait（SIGINT/SIGTERM）、_perform_health_check（GET /ocos/health，失败 crash_count+可选 auto_restart）、health_check/get_status/register_webhook_handler/send_webhook、OCOS_API_PORT/OCOS_WEBHOOK_PORT 覆盖）、ServerContext、ServerManager.__enter__/__exit__ 猴补、create_server_manager、run_server_background / 懒依赖 ocos.interaction.api.server / 被 master_agent（可注入）、test_server_manager、tests/test_external_server_manager、test_integration 调用 / 状态：**半成品（start() 关 loop 疑杀服务线程，见风险 P2-3）**
- `ocos/external_communication/manager.py`
  - 通道管理 / ChannelType/ChannelStatus/MessagePriority/ChannelConfig/ChannelHealth/CommunicationMessage/CommunicationRecord、BaseChannel(ABC)、CommunicationChannelManager（注册/选优/发送/记录 10000 上限）、ExternalCommunicationManager（register_websocket/http_channel、send_message 三种 loop 场景处理、tick/health_summary/get_history）、_WebSocketChannelPlaceholder、_HTTPChannelPlaceholder（**伪造 sent**） / 无 OCOS 依赖 / 被 master_agent（可注入）、test_external_communication_manager 调用 / 状态：**占位代码（真实通道未实现）**
- `ocos/ecosystem/manager.py`
  - 生态管理 / TrustLevel/ExtensionState/PluginState、ExtensionInfo、PluginInfo、EcosystemManager（register/approve/integrate/activate/revoke_extension、record_usage、load_plugin（**模拟加载**）/start/stop/unload/execute_plugin（adapter 分发）、register_adapter×4 方法、register/resolve_capability、update_trust（usage 10/50/100 升级）、get_trust_status/get_stats、上下文管理器）/ 依赖 ocos.logging / 被 master_agent（可注入）、test_ecosystem_manager、test_master_agent_ecosystem 调用 / 状态：半成品（插件加载空壳）
- `ocos/engagement/manager.py`
  - 主动参与 / EngagementType/Source/Status、EngagementRequest、ProactiveEngagementManager（create/submit_for_review/approve/reject/mark_ignored/list_requests、check_frequency_limit（24h/1h 重置）、increment_counts、check_permission/check_constitution/dual_check、check_fatigue、execute_engagement 全流程、_build_message 模板、_send_message 回调、set_output_callback、get_stats/_update_urgency_stats、reset_stats/close）/ 依赖 ocos.logging / 仅 test_proactive_engagement_manager 调用 / 状态：完整实现（死代码，功能与 proactive/ 重叠）
- `ocos/human/manager.py`
  - 人机协同 / CollaborationMode/FeedbackType/InteractionChannel、UserPreference、FeedbackRecord、ConversationState、HumanAIManager（set/get/get_all/remove_preference（key 线性查找）、record_feedback（1000 上限截断）、get_feedback_history、learn_from_feedback（PREFERENCE JSON 解析/CORRECTION/POSITIVE/NEGATIVE）、start/end_conversation、add_message、get/list_conversations、register/unregister_channel、send_message、register/unregister_callback、trigger_event、infer_intent 关键词规则、get_stats/reset_stats/close）/ 依赖 ocos.logging / 被 master_agent 多方法调用（可注入）、test_human_ai_manager、test_master_agent_human_ai / 状态：完整实现（生产未注入）
- `ocos/sleep_dream/__init__.py`
  - 导出 SleepDreamManager 等 7 符号 / 被 test_sleep_dream 调用 / 状态：完整实现
- `ocos/sleep_dream/manager.py`
  - 睡眠梦境 / SleepState、DreamType、SleepDecision、DreamRecord、SleepCycleStats、DreamGenerator（generate_dream/_collect_sources（duck-typed get_recent/replay_important/get_stats）/_create_content 五类模板/_extract_insight（**:158 恒真 elif bug**）/get_recent_dreams/get_stats）、SleepDreamManager（decide_sleep（空闲/稳态驱力/内存压力 TODO）、start_sleep/enter_dreaming/wake_up/run_sleep_cycle（梦境数=时长/30）/get_stats/generate_report）/ 无 OCOS 依赖 / 被 master_agent（可注入）、test_sleep_dream / 状态：半成品（逻辑缺陷两处）
- `ocos/optimization/manager.py`
  - 自优化 / OptimizationType（CACHE/BATCH/THREAD/MEMORY/ALGORITHM auto）、OptimizationStatus、OptimizationProposal、OptimizationResult、SelfOptimizationManager（set/get/update_baseline、propose/list/get_proposal、apply_optimization（仅记账）、validate_optimization（改进率均值 vs 阈值）、rollback_optimization、auto_optimize 循环、get_stats/reset_stats/close）/ 依赖 ocos.logging / 被 master_agent（可注入）、test_self_optimization_manager、test_master_agent_optimization 调用 / 状态：完整实现（生产未注入）

##### ocos/initiative/、proactive/、task/、examples/、plugins/、stability/
- `ocos/initiative/__init__.py`
  - 导出 TrueInitiative/InitiativeRequest / 被 agent_runtime:383 调用 / 状态：完整实现
- `ocos/initiative/true_initiative.py`
  - 主动性 / InitiativeRequest、TrueInitiative（check_and_generate 三源汇总、_recall_based（relevance≥0.7）、_idle_based（**:140-148 elif 不可达**）、_pattern_based（**:173 构造后 return [] 死代码**）、_deduplicate_and_sort、_generate_greeting/_generate_status_check、should_approve（permission_guard.can_initiate）、record_initiative、get_daily_count/increment_count/can_initiate_today）/ 无 OCOS 依赖 / 被 agent_runtime（注入，无消费）调用 / 状态：**逻辑不完整**
- `ocos/proactive/__init__.py`
  - 导出 ProactiveEngine/ProactiveAuditStore/TEMPLATE_POOL/ProactiveTemplate/select_template / 被 master_agent:1657 调用 / 状态：完整实现（活代码）
- `ocos/proactive/audit.py`
  - 审计存储 / ProactiveAuditStore（SQLite :memory: 默认，proactive_audit 表 id/ts/kind/message/granted/reason，initialize 幂等建表、record、count_since（ts 字符串比较 ISO）、count_granted_today（UTC 0 点起）、recent/close）/ 无依赖 / 被 engine、master_agent 间接调用 / 状态：完整实现
- `ocos/proactive/engine.py`
  - 引擎 / ProactiveEngine（maybe_proactive_output 防御兜底、_run 七步触发链、_self_goal_topic（load_active 找 origin_level=SELF 取描述前 12 字）、_fatigue_score、_checks_pass（PermissionGuard.check("view_self") + 宪法 check_action/check_decision 双兼容，fail-closed）、_deliver）/ 依赖 audit、templates / 被 master_agent、output.py、test_proactive_output、test_thin_coverage_e2e 调用 / 状态：完整实现（活代码）
- `ocos/proactive/templates.py`
  - 模板 / ProactiveTemplate（frozen）、TEMPLATE_POOL（问候/观察/提问三条）、select_template（index 取模轮换、空 topic 回退问候）/ 无依赖 / 被 engine 调用 / 状态：完整实现
- `ocos/proactive/output.py`
  - 输出包装 / OutputChannel/OutputPriority、OutputRecord、ProactiveOutput（try_proactive_output→engine、output_observation/suggestion/alert、get_output_stats、on_output/on_throttle、_check_throttle（**_today_count 永不重置**）、_record_output（priority 默认参数枚举/int 混用）、_deliver、_reset_hourly）/ 依赖 ocos.attention.focus、proactive.engine / 仅 test_proactive_output 调用 / 状态：完整实现（死代码，含节流缺陷）
- `ocos/proactive/enhanced_output.py`
  - 增强输出 / OutputChannel(str)/OutputPriority(int)、OutputRecord（to_dict）、OutputStats（record/to_dict/rejection_rate）、ProactiveOutputEnhanced（emit（锁内频率+间隔检查+执行+计数）、_check_rate_limit（日/小时自动重置）、_execute_output（CALLBACK/NOTIFICATION/BROADCAST 三通道）、_create_record、get_history/get_stats/get_status、set_limits/clear_history、_priority_ge（死方法））/ 无 OCOS 依赖 / 仅 test_proactive_output_enhanced、test_master_agent_proactive_output 调用 / 状态：完整实现（死代码）
- `ocos/task/__init__.py`
  - 执行期 DAG / TaskStatus、TaskNode、TaskDAG（RLock；add_task/add_dependency（自环拒绝、加边后 _has_cycle 检测失败回滚）、set_status/get/resolve_ready（PENDING 且依赖全 COMPLETED）/topological_order（DFS，temp 集合检环抛 ValueError）/__len__；AUD-F7 注释声明与 planning.TaskDAG 分工）/ 无依赖 / 被 agent_runtime:1001（活）、tests/test_stability/test_concurrency_locks、test_runtime_stages_wiring 调用 / 状态：完整实现（活代码）
- `ocos/examples/__init__.py`
  - 目录说明 docstring / 状态：占位性目录门面（正常）
- `ocos/examples/echo_agent.py`
  - 参考实现 / _EchoDescriptor、echo_agent_descriptor、EchoAgent（ICapabilityProvider+IAgentAdapter 协议属性、execute 计时返回 quality_score/duration_ms、_dispatch 四 handler、make_echo_agent 工厂）/ 无依赖 / 被 scripts/phase27_gate.py 调用 / 状态：完整实现
- `ocos/plugins/__init__.py`
  - **0 字节空文件**，无任何导出 / 无依赖 / 无人调用 / 状态：**占位代码**
- `ocos/stability/`（目录）
  - **空目录**（无 __init__.py、无文件）。tests/test_stability/ 与之无关（其 import 的是 ocos.task）。状态：**占位目录**

##### ocos/ 根目录
- `ocos/__init__.py`
  - 包声明 / __version__="1.0.0" / 状态：完整实现
- `ocos/agent_orchestration_autonomous.py`
  - Phase 61 自主编排 / OrchestrationPhase（7 态）、OrchestrationTask（to_planning_task 白名单 agent_type 兜底 writer）、OrchestrationStats、AutonomousOrchestrator（submit_goal/tick/`_decompose_goals` 固定 researcher-writer-reviewer 三段、_dispatch_pending（pool 优先否则串行每 tick 3 个、无 agent 记 default-agent）、_dispatch_via_pool（62c 并发 + 目标状态同步）、_task_to_contract（30s/no_retry）、_monitor_running（**伪造成功**）、_sync_goal_status（≥3 任务全 completed 才算目标完成）、_adapt（**不可达**）、summary/drain_events/_log）/ 依赖 ocos.logging、agent_orchestration（registry/selector/contract/agent_pool）、planning.models / 被 test_phase61_orchestration、test_phase62c_pool_integration 调用；test_import_rules.py:116 约束其依赖方向 / 状态：**逻辑不完整（死代码）**
- `ocos/belief.py`
  - 信念引擎 / BeliefDimension/BeliefQuadrant/EvidenceSource/SOURCE_WEIGHTS、Evidence（get_weight=源权重×新近度）、Belief（quadrant 动态计算、to_dict）、BeliefManager（add_belief、add_evidence、update_with_evidence（贝叶斯加权 + positive_count≥3 确认偏误告警）、decay_check（P₀×(1-decay)^days）、prune_dormant、query/get_strongest/get_convictions/find_by_statement、merge_beliefs（证据合并 + 证据数加权平均）、stats/drain_events、_compute_strength、_garbage_collect（超 1000 淘汰最弱至 990）、_log）/ 无依赖 / 被 test_phase61a_belief、test_phase62d_loop_coupling 调用 / 状态：完整实现（死代码，纯内存）
- `ocos/cognitive_interface.py`
  - 桥接 / re-export ocos.interaction.cognitive_interface.CognitiveInterface / 依赖 ocos.interaction / 无内部调用方（对外入口约定）/ 状态：完整实现（垫片）
- `ocos/homeostasis.py`
  - 桥接 / re-export ocos.capability.homeostasis 的 19 个符号 / 无内部调用方 / 状态：完整实现（垫片）
- `ocos/orchestrator.py`
  - 桥接 / re-export ocos.capability.orchestrator 的 3 个符号 / 无内部调用方 / 状态：完整实现（垫片；注意与 ocos/orchestration/ 无关）

---


#### W12（ocos/tests 测试套件 175 文件）—— 文件索引

#### 二、文件全量索引

（共 175 个文件，逐条列出。状态说明：全部文件均为有效测试；test_phase52.py 含 2 处 psutil 缺失条件跳过；conftest.py/__init__.py 不含测试函数。）

##### 基础设施与引擎单元测试（Phase 4-19 早期层）

`ocos/tests/conftest.py`
- 覆盖目标：公共夹具（LLM 配置隔离）
- 关键测试类/函数：autouse fixture `_isolated_llm_config`（清除 OPENAI/ANTHROPIC key、mock `_read_llm_config`）
- 状态：无测试函数，有效夹具

`ocos/tests/__init__.py`
- 空文件
- 状态：无内容

`ocos/tests/test_adaptive_control.py`
- 覆盖目标：ocos.runtime.adaptive_control（B6 自适应控制）
- 关键测试类/函数：54 个测试；AdaptiveConfig 冻结、auto_adapt 降级/恢复、clamp 边界、ResourceManager/PolicyEngine/EventBus 集成
- 状态：有效测试

`ocos/tests/test_address_resolver.py`
- 覆盖目标：ocos.engines.address_resolver（Phase 4 万能地址解析）
- 关键测试类/函数：TestAddressResolver（register/resolve、未注册抛错、UniversalAddress 路由）
- 状态：有效测试

`ocos/tests/test_architecture_principles.py`
- 覆盖目标：Phase 15 四条"不堆叠"架构原则（Engine/Model/层命名/Capability）
- 关键测试类/函数：AST/文件扫描断言（PROJECT_ROOT 下 ocos 目录结构检查）
- 状态：有效测试（架构约束类）

`ocos/tests/test_attention_engine.py`
- 覆盖目标：ocos.runtime.attention_engine（B2 注意力引擎）
- 关键测试类/函数：AttentionScore 冻结、DefaultContentAnalyzer 三指标、FrequencyAnalyzer 衰减、阈值过滤/排序/缓存
- 状态：有效测试

`ocos/tests/test_attention_focus.py`
- 覆盖目标：ocos.attention.focus（Phase O 注意焦点）
- 关键测试类/函数：TestFocusState、FakeObservation；FocusType/DriveSignal 联动
- 状态：有效测试

`ocos/tests/test_audit_engine.py`
- 覆盖目标：ocos.platform.audit_engine（C2 审计引擎）
- 关键测试类/函数：99 个测试（全文件最多之一）；InMemoryAuditStore、5 条默认审计规则、EventBus 4 类事件回调、Debug/Compliance/Replay 报告
- 状态：有效测试

`ocos/tests/test_belief_consolidation.py`
- 覆盖目标：ocos.agent.belief_consolidation / belief_system / learning_trigger（P1-A 信念巩固写路径）
- 关键测试类/函数：L6 门控（六类禁止词）、幂等 consolidate、Episode→Belief 溯源、Pattern 聚合
- 状态：有效测试

`ocos/tests/test_capability_contracts.py`
- 覆盖目标：ocos.engines/ 下 14 个标准引擎的"绝不能"契约
- 关键测试类/函数：AST 静态分析 + 运行时接口检查（STANDARD_ENGINES 清单）
- 状态：有效测试（架构约束类）

`ocos/tests/test_capability_registry.py`
- 覆盖目标：ocos.platform.capability_registry（D1 能力注册表）
- 关键测试类/函数：63 个测试；CapabilityDescriptor 冻结、重复版本递增、Query 组合查询、边缘情况
- 状态：有效测试

`ocos/tests/test_consolidation_engine.py`
- 覆盖目标：ocos.engines.consolidation_engine（Phase 8 信息合并引擎）
- 关键测试类/函数：mock KnowledgeABI fixture；合并、EventBus 事件
- 状态：有效测试

`ocos/tests/test_constitution.py`
- 覆盖目标：ocos.kernel.constitution（A1 宪法规则）
- 关键测试类/函数：test_all_24_constitutional_rules_defined（24 条不可变规则全集断言）
- 状态：有效测试

`ocos/tests/test_context_manager.py`
- 覆盖目标：ocos.runtime.context_manager（B1 上下文管理器）
- 关键测试类/函数：WorkingMemory CRUD、Context 冻结、EventBus 自动重建
- 状态：有效测试

`ocos/tests/test_continuous_learning.py`
- 覆盖目标：ocos.learning（Phase R 持续学习）
- 关键测试类/函数：TestPreferenceModel（正/负反馈、偏好计数）、ContinuousLearning
- 状态：有效测试

`ocos/tests/test_decision_making_engine.py`
- 覆盖目标：ocos.engines.decision_making_engine（Phase 19 决策引擎）
- 关键测试类/函数：6 种策略（SCORING/RANKING/MAJORITY/SATISFICING/OPPORTUNITY_COST/PARETO）、与 Decision/Execution/Process Runtime 集成、E2E
- 状态：有效测试

`ocos/tests/test_decision_model.py`
- 覆盖目标：ocos.kernel.abi Decision/DecisionStatus + event_schema + trace（Phase 17.3）
- 关键测试类/函数：TestDecisionStatusEnum、legacy 映射、宪法规则对齐
- 状态：有效测试

`ocos/tests/test_distributed_cognition_manager.py`
- 覆盖目标：ocos.distributed.manager（Phase AB 分布式认知）
- 关键测试类/函数：30 个测试；实例注册、心跳、任务分发/重试/故障转移、负载均衡策略
- 状态：有效测试

`ocos/tests/test_ecosystem_manager.py`
- 覆盖目标：ocos.ecosystem.manager（Phase AC 生态管理）
- 关键测试类/函数：30 个测试；扩展注册、插件生命周期、适配器、信任分级
- 状态：有效测试

`ocos/tests/test_event_bus.py`
- 覆盖目标：ocos.events（A3：EventBus + EventStore + DeadLetterQueue）
- 关键测试类/函数：TestEventBus（发布/订阅/无订阅者）、InMemoryEventStore、CommitResult/StoreSnapshot
- 状态：有效测试

`ocos/tests/test_event_schema.py`
- 覆盖目标：ocos.kernel.event_schema（架构：EventType 与 EVENT_SCHEMA_REGISTRY 一致性）
- 关键测试类/函数：test_all_event_types_have_schema_entries、test_no_orphan_schema_entries
- 状态：有效测试

`ocos/tests/test_event_store_sqlite.py`
- 覆盖目标：ocos.event_memory（GAP-P2-3 事件 SQLite 落库 + archive）
- 关键测试类/函数：append 落库/load_from_db 重建/append-only 语义/ARCHIVED 生命周期标记
- 状态：有效测试

`ocos/tests/test_execution_bridge.py`
- 覆盖目标：ocos.execution.bridge（R4-A DecisionBridge：自治决策→真实执行铰链）
- 关键测试类/函数：AUTO/ASK 动作分诊、PermissionGuard 双检、DAG 只读放行、空决策 idle
- 状态：有效测试

`ocos/tests/test_execution_model.py`
- 覆盖目标：ocos.models.execution（Phase 17.1 五维：Model/Event/Trace/Constitution/Invariants）
- 关键测试类/函数：ExecutionStatus 枚举、EXECUTION_* 事件、ExecutionTrace、正/负面测试对
- 状态：有效测试

`ocos/tests/test_external_communication_manager.py`
- 覆盖目标：ocos.external_communication.manager（Phase AK 对外通信）
- 关键测试类/函数：24 个测试；通道管理、消息优先级、历史记录、tick
- 状态：有效测试

`ocos/tests/test_external_interaction.py`
- 覆盖目标：ocos.interaction.channel（Phase Q 外部交互通道）
- 关键测试类/函数：TestLogChannel、CallbackChannel、WebhookChannel、BroadcastChannel
- 状态：有效测试

`ocos/tests/test_forgetting_engine.py`
- 覆盖目标：ocos.engines.forgetting_engine（Phase 7 遗忘引擎）
- 关键测试类/函数：遗忘条件、EventBus 集成、降级模式
- 状态：有效测试

`ocos/tests/test_goal_arbitration_engine.py`
- 覆盖目标：ocos.engines.goal_arbitration_engine（Phase 19 目标仲裁）
- 关键测试类/函数：4 种仲裁策略（PRIORITY/WEIGHTED/EMERGENCY/RESOURCE_AWARE）、ProcessRuntimeEngine 集成
- 状态：有效测试

`ocos/tests/test_goal_claim.py`
- 覆盖目标：ocos.goal.store + daemon 认领机制（UX-1）
- 关键测试类/函数：TestClaimMechanism（CLI 落库 → daemon 认领进 runtime，OCOS_DB_PATH 隔离）
- 状态：有效测试（上电/集成类）

`ocos/tests/test_goal_model.py`
- 覆盖目标：ocos.models.goal（Phase 17.2 五维：Model/Enum/Event/Trace/Constitution）
- 关键测试类/函数：TestGoalStatusEnum、9 个 GOAL_* 事件、R17-R19 宪法规则
- 状态：有效测试

`ocos/tests/test_goal_origin_model.py`
- 覆盖目标：ocos.goal.enforcer / goal.factory（Phase 22 Goal Origin 模型）
- 关键测试类/函数：GoalOriginEnforcer 阶段隔离、origin_level/authority 不可改、HUMAN 需授权上下文；reset_phase fixture 恢复 Phase 21
- 状态：有效测试（含历史阶段快照语义）

`ocos/tests/test_goal_runtime.py`
- 覆盖目标：ocos.runtime.goal_runtime（Phase 18 目标运行时）
- 关键测试类/函数：10 组；CREATED→ACTIVE 推进、Superseding、auto_expired、查询
- 状态：有效测试

`ocos/tests/test_governance_engine.py`
- 覆盖目标：ocos.platform.governance_engine（C3 治理引擎）
- 关键测试类/函数：52 个测试；提案全生命周期、状态机非法转换、PolicyEngine 端到端、降级模式
- 状态：有效测试

`ocos/tests/test_health_check.py`
- 覆盖目标：ocos.agent.health_check
- 关键测试类/函数：TestComponentCheck（HEALTHY/DEGRADED/UNHEALTHY/UNKNOWN）、EventBus
- 状态：有效测试

`ocos/tests/test_human_ai_manager.py`
- 覆盖目标：ocos.human.manager（Phase AD 人机协同）
- 关键测试类/函数：30 个测试；偏好、反馈学习、对话、意图识别
- 状态：有效测试

`ocos/tests/test_immune_system.py`
- 覆盖目标：免疫系统上电（PW-3.1/3.2）——诊断循环 + 白名单修复 + 损伤注入；涉及 ocos.storage.migrations、episodes 表
- 关键测试类/函数：_seed_stale 注入陈旧 Episode（记忆膨胀损伤）
- 状态：有效测试（上电类）

`ocos/tests/test_import_rules.py`
- 覆盖目标：A1 AST import 依赖方向规则（宪法依赖方向）
- 关键测试类/函数：_extract_imports AST 扫描全部 ocos 模块、SyntaxError 即 fail
- 状态：有效测试（架构约束类）

`ocos/tests/test_information_access_via_universal_address.py`
- 覆盖目标：INFORMATION_THEORY 第七章硬约束（所有访问经 UniversalAddress/AddressResolver）
- 关键测试类/函数：_DirectStoreCallFinder AST 访问者（禁止 WorkingMemory.get_goals 等直接调用）
- 状态：有效测试（架构约束类）

`ocos/tests/test_information_axioms_enforced.py`
- 覆盖目标：INFORMATION_THEORY 第八章公理 1-7 不可违反
- 关键测试类/函数：AST 扫描 + 语义约束（Axiom 6 "Information 不拥有行为"等）
- 状态：有效测试（架构约束类）

`ocos/tests/test_information_has_role_and_persistence.py`
- 覆盖目标：ocos.models.information（第三章：SemanticRole + PersistenceLevel 必须并存）
- 关键测试类/函数：test_information_metadata_has_role 等
- 状态：有效测试

`ocos/tests/test_information_models.py`
- 覆盖目标：ocos.models.information（Phase 17.4 对齐测试）
- 关键测试类/函数：46 个测试；TestUniversalAddress、InformationMetadata、RelationType
- 状态：有效测试

`ocos/tests/test_information_state_machine.py`
- 覆盖目标：InformationState 五态状态机（CREATED→VALIDATED→REFERENCED→DEPRECATED→ARCHIVED）
- 关键测试类/函数：TestInformationStateMachine 全转换矩阵（含 S_C→S_D 特例）
- 状态：有效测试

`ocos/tests/test_integration.py`
- 覆盖目标：端到端集成——MasterAgent + Performance/Monitoring/Security/Persistence/ServerManager
- 关键测试类/函数：6 大场景（认知循环、记忆-学习闭环、注意力-目标、持久化-恢复、监控-告警、安全-权限）
- 状态：有效测试（集成类）

`ocos/tests/test_knowledge_evolution.py`
- 覆盖目标：ocos.knowledge.knowledge_evolution + knowledge_validator（M3）
- 关键测试类/函数：EvolutionManager、EvolutionProposal 状态、DEFAULT_VALIDATION_RULES
- 状态：有效测试

`ocos/tests/test_knowledge_graph.py`
- 覆盖目标：ocos.knowledge KnowledgeGraph（Phase S 知识图谱）
- 关键测试类/函数：TestEntity、Relation、Fact、KnowledgeGraphManager
- 状态：有效测试

`ocos/tests/test_knowledge_lifecycle.py`
- 覆盖目标：ocos.knowledge.knowledge_lifecycle + knowledge_abi（M2）
- 关键测试类/函数：KnowledgeLifecycle、StatusChangeRecord、ABI_VERSION
- 状态：有效测试

`ocos/tests/test_knowledge_ontology.py`
- 覆盖目标：ocos.knowledge.knowledge_ontology（M0 本体）
- 关键测试类/函数：TestKnowledgeLevel（5 层）、ELEVATION_MATRIX、STATUS_TRANSITIONS、can_elevate
- 状态：有效测试

`ocos/tests/test_knowledge_registry.py`
- 覆盖目标：ocos.knowledge.knowledge_registry + AccessMatrix（M1 知识所有权）
- 关键测试类/函数：TestAccessScope（PUBLIC/PROTECTED/PRIVATE）、OwnershipEntry
- 状态：有效测试

`ocos/tests/test_knowledge_synthesis_manager.py`
- 覆盖目标：ocos.knowledge.synthesis_manager（Phase AG 知识综合）
- 关键测试类/函数：30 个测试；节点/边管理、路径查找、质量评估
- 状态：有效测试

`ocos/tests/test_learning_engine.py`
- 覆盖目标：ocos.engines.learning_engine（Phase 19 学习引擎）
- 关键测试类/函数：有监督/强化学习、增量更新、ProcessRuntimeEngine 集成
- 状态：有效测试

`ocos/tests/test_master_agent.py`
- 覆盖目标：ocos.opentale_bridge.master_agent（S5 写作决策引擎）
- 关键测试类/函数：题材→focus/tone 决策、章节节奏、Organ 设定契约
- 状态：有效测试

##### MasterAgent 集成测试系列（Phase AA-AK）

`ocos/tests/test_master_agent_diagnosis.py`
- 覆盖目标：ocos.diagnosis.manager 注入 MasterAgent（Phase AH）
- 关键测试类/函数：管理器注入、诊断接口、健康状态、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_distributed.py`
- 覆盖目标：ocos.distributed.manager 注入 MasterAgent（Phase AB）
- 关键测试类/函数：mock_agent fixture、任务提交分发、统计、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_ecosystem.py`
- 覆盖目标：ocos.ecosystem.manager 注入 MasterAgent（Phase AC）
- 关键测试类/函数：扩展注册批准、插件启动、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_external_communication.py`
- 覆盖目标：ocos.external_communication.manager 注入 MasterAgent（Phase AK）
- 关键测试类/函数：通道管理、消息发送、历史、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_human_ai.py`
- 覆盖目标：ocos.human.manager 注入 MasterAgent（Phase AD）
- 关键测试类/函数：偏好设置、反馈记录、对话管理、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_knowledge.py`
- 覆盖目标：ocos.knowledge.synthesis_manager 注入 MasterAgent（Phase AG）
- 关键测试类/函数：知识节点 CRUD、综合、路径查找、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_optimization.py`
- 覆盖目标：ocos.optimization.manager 注入 MasterAgent（Phase AF）
- 关键测试类/函数：基线管理、优化提案、应用验证、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_proactive_output.py`
- 覆盖目标：ocos.proactive.enhanced_output 注入 MasterAgent（Phase AJ）
- 关键测试类/函数：输出接口、频率限制、历史、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_reflection.py`
- 覆盖目标：ocos.reflection.manager 注入 MasterAgent（Phase AE）
- 关键测试类/函数：反思执行、智慧管理、身份连续性、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_self_evolution.py`
- 覆盖目标：ocos.evolution.manager.SelfEvolutionManager 注入 MasterAgent（Phase AA）
- 关键测试类/函数：提案检测/分析/沙箱/批准/执行/回滚、tick
- 状态：有效测试（集成类）

`ocos/tests/test_master_agent_tool.py`
- 覆盖目标：ocos.tool.manager 注入 MasterAgent（Phase AI 工具集成）
- 关键测试类/函数：工具注册/注销、调用、历史、tick
- 状态：有效测试（集成类）

`ocos/tests/test_metrics_collector.py`
- 覆盖目标：ocos.agent.metrics_collector
- 关键测试类/函数：TestEngineMetrics（success/failure 记录、总调用数）
- 状态：有效测试

`ocos/tests/test_monitoring_manager.py`
- 覆盖目标：ocos.monitoring.manager（Phase Y 监控）
- 关键测试类/函数：TestMetricPoint、MetricsRegistry、AlertManager/AlertRule/AlertState
- 状态：有效测试

`ocos/tests/test_multi_modal_perception.py`
- 覆盖目标：ocos.perception.multi_modal + cross_modal_fusion（Phase T 多模态感知）
- 关键测试类/函数：TestAudioSensor、VisionSensor、ApiSensor、EventSensor、CrossModalFusion
- 状态：有效测试

`ocos/tests/test_narrative_pipeline.py`
- 覆盖目标：ocos.engines.narrative_pipeline（叙事推导层）
- 关键测试类/函数：TestDerivePolicy（Contract→Policy 推导）、_derive_pov_type/_chapter_base_intensity
- 状态：有效测试

`ocos/tests/test_no_direct_store_access.py`
- 覆盖目标：INFORMATION_THEORY 硬约束——禁止绕过 AddressResolver 直连 Store
- 关键测试类/函数：AST 扫描 STORE_FILES 白名单
- 状态：有效测试（架构约束类）

`ocos/tests/test_object_model.py`
- 覆盖目标：ocos.kernel.abi 六个核心对象（A1）
- 关键测试类/函数：frozen dataclass 断言、schema_version 字段、12 个核心 EventType、宪法字段
- 状态：有效测试

`ocos/tests/test_ocos_memory.py`
- 覆盖目标：ocos.opentale_bridge.ocos_memory（S8-P2：M3 编排/M4 巩固/M5 遗忘 + M6/C3 统一）
- 关键测试类/函数：test_m6_record_and_prune（OCOS_MEMORY_DIR 临时隔离）
- 状态：有效测试

`ocos/tests/test_orchestration_engine.py`
- 覆盖目标：ocos.orchestration.engine（Phase N 编排引擎）
- 关键测试类/函数：OrchestrationState/Metrics、AgentRegistry、Task/Plan 联动
- 状态：有效测试

`ocos/tests/test_organ_client.py`
- 覆盖目标：ocos.opentale_bridge.organ_client（S4 写作器官客户端）
- 关键测试类/函数：本地 mock HTTPServer；health/status 只读、generate→task_id、wait 轮询、超时抛 OrganTaskTimeout
- 状态：有效测试

`ocos/tests/test_pending_store.py`
- 覆盖目标：ocos.execution.pending + DecisionBridge 待批队列（AUD-F12）
- 关键测试类/函数：TestPendingStore（enqueue/list、PEND- 前缀、OCOS_APPROVAL_MODE=ask）
- 状态：有效测试

`ocos/tests/test_performance_manager.py`
- 覆盖目标：ocos.performance.manager（Phase Z 性能）
- 关键测试类/函数：TestSmartCache、AsyncBatchProcessor、BulkPersistence、PerformanceProfiler
- 状态：有效测试

`ocos/tests/test_persistence_manager.py`
- 覆盖目标：ocos.persistence.manager（Phase V 持久化）
- 关键测试类/函数：TestPersistenceManager（SnapshotType、RestoreStrategy、tmp_path 隔离）
- 状态：有效测试

##### 阶段验收测试（Phase 21 - 62）

`ocos/tests/test_phase21_prompt1.py`
- 覆盖目标：Agent 快照系统 + 数据库 Schema（Phase 21 P1）
- 关键测试类/函数：快照冻结、保存/加载往返、原子锁并发、恢复流程
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase21_prompt2.py`
- 覆盖目标：Goal 持久化 + 宪法执行（Phase 21 P2）
- 关键测试类/函数：GoalFactory 拒绝 MISSION、GoalStore 存取、高风险拦截、check_decision < 1ms 性能断言
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase21_prompt3.py`
- 覆盖目标：MasterAgent 集成与 Gate 验收（Phase 21 P3）
- 关键测试类/函数：BOOT→SLEEP→BOOT 端到端、check_time_us < 1000、零回归要求
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase22_prompt1.py`
- 覆盖目标：ocos.agent.lifecycle LifecycleManager + ControlLoop（Phase 22 P1）
- 关键测试类/函数：宏观/微观状态转换、Goal 创建三源、RLock 线程安全、contextvars 追踪
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase22_prompt2.py`
- 覆盖目标：CognitiveBridge + MasterAgent 集成（Phase 22 P2）
- 关键测试类/函数：引擎路由（reason/plan/decide/reflect/learn）、全链路微观循环、宪法拦截、异常恢复
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase38_5_rgv.py`
- 覆盖目标：Runtime Governance Validation（Phase 38.5，50 个测试）
- 关键测试类/函数：RGV 治理约束 enforcement 点检查（🟢 PASS/🟡 STUB/🔴 FAIL 三态）
- 状态：有效测试（治理 gate）

`ocos/tests/test_phase39_1.py`
- 覆盖目标：Runtime Skeleton（R39-001~005：boot、tick 生成、checkpoint、恢复、治理隔离）
- 关键测试类/函数：subprocess 验证 python -m ocos.runtime
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase39_2.py`
- 覆盖目标：ocos.runtime.pipeline TickPipeline（R39-201~204）
- 关键测试类/函数：8 stage 顺序、空系统 1000 ticks、Stage 隔离 AST 检查、TickContext 可序列化
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase39_3.py`
- 覆盖目标：ocos.runtime.permission 策略层（R39-301~305）
- 关键测试类/函数：Default Deny、Protected Operations、Approval Flow、PermissionTrace、治理隔离
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase39_4.py`
- 覆盖目标：认知恢复与连续性（R39-401~408）
- 关键测试类/函数：快照创建/恢复、Goal 连续性、Event Replay、Crash Simulation 端到端
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase39_5.py`
- 覆盖目标：ocos.attention Attention ABI（R39.5-01~07）
- 关键测试类/函数：单一焦点、优先级选择、打断、惯性防抖、WM 绑定、恢复
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase39_6.py`
- 覆盖目标：ocos.goal GoalMonitor/Maintenance（R39.6-01~05）
- 关键测试类/函数：Goal Health、Stall Detection、Boundary Protection（禁 create/modify/delete）
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase40.py`
- 覆盖目标：ocos.self SelfModel（S40-01~05）
- 关键测试类/函数：identity_ref 不可变、能力自知、知识边界、经验投射、运行时绑定
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase41.py`
- 覆盖目标：ocos.self.experience_profile + ocos.personal_memory Wisdom（PM41-01~05）
- 关键测试类/函数：ExperiencePattern、PatternInterpreter、WisdomValidator、WisdomStore
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase42.py`
- 覆盖目标：ocos.world_model（WM42-01~06 世界模型六大边界）
- 关键测试类/函数：实体隔离、关系完整性、状态演化、因果边界、Belief 分离、外部输入治理
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase43.py`
- 覆盖目标：ocos.decision（D43-01~06 决策智能边界）
- 关键测试类/函数：Decision≠Goal、Decision≠Execution、Wisdom≠Rule、四源聚合、风险/价值评估
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase44.py`
- 覆盖目标：ocos.extension（CG44-01~04 认知扩展治理）
- 关键测试类/函数：Extension≠Identity、Discovery≠Acceptance、Integration≠Trust、Repair≠Self-Rewrite
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase45.py`
- 覆盖目标：ocos.capability（CNS45-01~04 能力神经系统）
- 关键测试类/函数：Capability≠Authority、Selector≠Decision、Agent≠Cognitive Entity、Result→Interpretation→Validation→Memory
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase46.py`
- 覆盖目标：ocos.cognitive_loop（CL46-01~04 认知运行循环）
- 关键测试类/函数：Loop≠Autonomy、Health≠Self-Rewrite、Perception≠Truth、Learning≠Drift、LoopOrchestrator
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase47.py`
- 覆盖目标：ocos.evolution（CE47-01~04 认知演化治理）
- 关键测试类/函数：Evolution≠Autonomy、Proposal≠Execution、Migration≠Destruction、FORBIDDEN_DOMAINS 禁止域守卫
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase47_self_modification.py`
- 覆盖目标：ocos.capability.agents.self_modification_agent
- 关键测试类/函数：TestSelfModificationAgent、validate_path 路径安全、preview_change
- 状态：有效测试

`ocos/tests/test_phase48_agent_proxy.py`
- 覆盖目标：ocos.capability.agent_proxy（Phase 48 智能体代理）
- 关键测试类/函数：TestAgentRegistry（≥5 内置代理）、call_agent、get_registry
- 状态：有效测试

`ocos/tests/test_phase48.py`
- 覆盖目标：ocos.personal_intelligence（PM48-01~04 个人智能成熟度）
- 关键测试类/函数：Personalization≠Overfitting、Meta-cognition≠Self-doubt、Consistency≠Rigidity
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase49.py`
- 覆盖目标：ocos.cognitive_continuity（CC49-01~04 认知连续性）
- 关键测试类/函数：Continuity≠Archive、Identity≠Freeze、Knowledge Aging≠Amnesia、Timeline≠Prediction
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase49_experience_learning.py`
- 覆盖目标：ocos.learning.experience_learning（Phase 49-A 经验学习快通路）
- 关键测试类/函数：失败样本入库→LearningArtifact、Behavioral Delta、快通路非空
- 状态：有效测试

`ocos/tests/test_phase49b_memory_world.py`
- 覆盖目标：ocos.memory.recall + ocos.world_model.world_store（49-B 记忆召回→认知链）
- 关键测试类/函数：TestRecallResultContract（relevance/confidence/provenance）、conflict_set、world_context 注入
- 状态：有效测试

`ocos/tests/test_phase49c_skill_growth.py`
- 覆盖目标：ocos.learning.skill_growth（49-C L4/L5/L6 技能生长）
- 关键测试类/函数：Replanner 失败重规划、SkillProposer 候选生成、GovernedSkillCommitter 四段
- 状态：有效测试

`ocos/tests/test_phase49d_metacognition.py`
- 覆盖目标：ocos.learning.metacognition（49-D L7/L8 元认知）
- 关键测试类/函数：SkillSemanticMatcher 跨形式迁移、CapabilityConfidence 低置信升 ASK
- 状态：有效测试

`ocos/tests/test_phase50.py`
- 覆盖目标：ocos.os_v1（OS50-01~06 个人认知 OS v1.0）
- 关键测试类/函数：Interface≠Brain、Benchmark≠Training、Freeze≠Dead、PersonalCognitiveOS
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase50_growth.py`
- 覆盖目标：ocos.growth.engine（Phase 50 成长模块）
- 关键测试类/函数：TechSignal 注入 + sqlite 持久化、LLM 分析提案、自动执行回滚、禁区路径拒绝
- 状态：有效测试

`ocos/tests/test_phase51.py`
- 覆盖目标：ocos.audit 系统集成审计（Phase 51）
- 关键测试类/函数：AU51-01~04（审计只读、追踪不执行、报告不修复、缺口不阻塞）、ArchitectureMap/LAYER_REGISTRY
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase51_1.py`
- 覆盖目标：持久化认知存储（Phase 51.1）——ocos.persistence.{snapshot_manager, state_serializer, lifecycle_manager, recovery_manager, persistence_validator}
- 关键测试类/函数：序列化往返、冷启动恢复、跨 session 语义、PS51-01~04 边界
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase51_2.py`
- 覆盖目标：ocos.runtime_scheduler（Phase 51.2 运行时调度器）
- 关键测试类/函数：RS51-01~05；Scheduler≠Brain、10000 ticks 稳定、背压 10000 events
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase51_goal_exec.py`
- 覆盖目标：ocos.execution.goal_executor（Phase 51 goal exec 直接执行器）
- 关键测试类/函数：LLM 分解 RUN| 行解析、沙盒拦截写命令、分解失败单命令回退
- 状态：有效测试

`ocos/tests/test_phase52.py`
- 覆盖目标：ocos.perception 感知系统（PS52-01~04）
- 关键测试类/函数：Perception≠Truth、传感器隔离、置信度必填、验证门控；含 2 处 psutil 缺失条件 skipif
- 状态：有效测试（唯一含条件跳过的文件）

`ocos/tests/test_phase52_self_review.py`
- 覆盖目标：ocos.reflection.self_review 自省采集器
- 关键测试类/函数：失败判定、belief scope 分组、证据结构、报告渲染
- 状态：有效测试

`ocos/tests/test_phase53.py`
- 覆盖目标：ocos.interaction 主动交互系统（IS53-01~04）
- 关键测试类/函数：NeedMonitor、Active Reminder≠Decision、Validation Before Send、Rate Limiting
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase54.py`
- 覆盖目标：ocos.event_memory 事件记忆基础设施（EM54-01~06）
- 关键测试类/函数：事件不可篡改、时间线重建、回放无副作用、事件≠记忆、跨 session 恢复
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase55.py`
- 覆盖目标：ocos.capability_reality（CR55-01~04 能力现实层）
- 关键测试类/函数：Capability≠Execution、Adapter 隔离、Execution Recorded、能力发现
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase56.py`
- 覆盖目标：ocos.diagnosis 自诊断与修复（SD56-01~06）
- 关键测试类/函数：Diagnosis≠Decision、Repair≠Evolution/Self-Rewrite、修复前 checkpoint、故障隔离
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase57.py`
- 覆盖目标：ocos.living_verification 活体系统验证（LV57-01~06）
- 关键测试类/函数：SimulationEngine、全链路 Intent→Memory 可追踪、长期运行、故障恢复、人格连续性
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase58.py`
- 覆盖目标：ocos.health_examination 健康体检协议（Phase 58.0）
- 关键测试类/函数：StructuralExaminer（P39-P50 器官完整性）、Connectivity（29 对神经连接）、Cognitive/Immune/Runtime Examiner
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase58_1.py`
- 覆盖目标：ocos.living_test 活体测试协议（Phase 58.1，56 个测试）
- 关键测试类/函数：Day 0 出生检查 ~ Day 7 复活、Living Score 计算、协议编排
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase58_2.py`
- 覆盖目标：ocos.cognitive_nutrition 认知营养协议（Phase 58.2，68 个测试）
- 关键测试类/函数：DataMeal/FastingBaseline/DigestionMonitor、7 天执行、Day 7 健康复查
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase58_3.py`
- 覆盖目标：ocos.recovery_resilience 认知恢复与韧性（Phase 58.3，86 个测试）
- 关键测试类/函数：DamageInjector 5 类损伤、RecoveryMonitor、100 分制评分、故障检出率 100% 等通过标准
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase59.py`
- 覆盖目标：ocos.opentale_bridge 全桥接（Phase 59，122 个测试，全文件最多）
- 关键测试类/函数：test_import_all_modules、节点单元测试（bridge_model/decision_translator/feedback_loop）、活体证明集成、全量回归
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase60.py`
- 覆盖目标：ocos.autonomous_runtime 自主运行时（Phase 60）
- 关键测试类/函数：test_import_all、LoopMode、AutonomousLoop、ActionDispatcher、Supervisor
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase61_orchestration.py`
- 覆盖目标：ocos.agent_orchestration_autonomous 自主编排（Phase 61）
- 关键测试类/函数：AutonomousOrchestrator、Goal 分解、Task 状态转换、失败回退
- 状态：有效测试（阶段 gate）

`ocos/tests/test_phase61a_belief.py`
- 覆盖目标：ocos.belief 信念模块（Phase 61-a）
- 关键测试类/函数：TestBeliefModel、BeliefManager、BeliefQuadrant、SOURCE_WEIGHTS
- 状态：有效测试

`ocos/tests/test_phase62a_coupling.py`
- 覆盖目标：ocos.capability.cognitive_coupling 认知耦合桥（Phase 62a）
- 关键测试类/函数：poll、矛盾事件→认知熵、确认偏差警报、apply_to_homeostasis
- 状态：有效测试

`ocos/tests/test_phase62b_agent_pool.py`
- 覆盖目标：ocos.agent_orchestration.agent_pool（Phase 62b）
- 关键测试类/函数：execute_sync 并发顺序保持、超时处理、fallback、PoolResult/PoolStats
- 状态：有效测试

`ocos/tests/test_phase62c_pool_integration.py`
- 覆盖目标：AgentPool 接入 AutonomousOrchestrator（Phase 62c 集成）
- 关键测试类/函数：无 pool 向后兼容、单 tick 并行 dispatch、_task_to_contract
- 状态：有效测试（集成类）

`ocos/tests/test_phase62d_loop_coupling.py`
- 覆盖目标：CognitiveCouplingBridge 接入 LoopOrchestrator（Phase 62d 集成）
- 关键测试类/函数：tick 触发 bridge.poll、桥接指标累积、周期健康检查
- 状态：有效测试（集成类）

`ocos/tests/test_phase_fix17_proactive.py`
- 覆盖目标：ocos.daemon.factory 主动输出回调注入（FIX-17）
- 关键测试类/函数：test_callback_injected_in_production（build_master_agent → 消息落 UserInbox）
- 状态：有效测试

`ocos/tests/test_phase_session_state.py`
- 覆盖目标：ocos.interaction.session_state 会话状态（P0-2/P0-3）
- 关键测试类/函数：TestSessionState（ensure_and_append 等）
- 状态：有效测试

##### Process/Runtime 系列与剩余单元测试

`ocos/tests/test_planning_engine.py`
- 覆盖目标：ocos.engines.planning_engine（Phase 19 规划引擎）
- 关键测试类/函数：6 种规划策略、PlanningTrace、ProcessRuntimeEngine 集成、错误处理
- 状态：有效测试

`ocos/tests/test_plugin_loader.py`
- 覆盖目标：ocos.platform.plugin_loader（D3 插件加载器）
- 关键测试类/函数：discover/load/execute/unload 全场景、PluginBase ABC、CapabilityRegistry 集成、schema_version 兼容
- 状态：有效测试

`ocos/tests/test_plugin_sandbox.py`
- 覆盖目标：ocos.platform.plugin_sandbox（D2 插件沙箱，62 个测试）
- 关键测试类/函数：Permission/PluginManifest/SandboxConfig、Import Hook 白名单、强制超时终止
- 状态：有效测试

`ocos/tests/test_policy_engine.py`
- 覆盖目标：ocos.engines.policy_engine + ocos.models.policy（Phase 19 策略引擎）
- 关键测试类/函数：规则增删查、默认 ALLOW/DENY/WARN 评估、register_rule_evaluator
- 状态：有效测试

`ocos/tests/test_power_on_w1_w4.py`
- 覆盖目标：上电测试 PW-4.1（ocos.operations 沙盒命令/HTTP 抓取，经 execution.bridge）+ PW-1.1（personal_memory WisdomStore 智慧沉淀）
- 关键测试类/函数：TestOperationsPowered、OCOS_APPROVAL_MODE=ask
- 状态：有效测试（上电类）

`ocos/tests/test_prediction_engine.py`
- 覆盖目标：ocos.engines.prediction_engine（Phase 19 预测引擎）
- 关键测试类/函数：4 种预测策略、置信区间、trace 生命周期、ProcessRuntimeEngine 集成
- 状态：有效测试

`ocos/tests/test_proactive_engagement_manager.py`
- 覆盖目标：ocos.engagement.manager（Phase AF 主动参与管理）
- 关键测试类/函数：30 个测试；参与请求、状态转换、疲劳检测、权限检查
- 状态：有效测试

`ocos/tests/test_proactive_output_enhanced.py`
- 覆盖目标：ocos.proactive.enhanced_output（Phase AJ 增强主动输出）
- 关键测试类/函数：24 个测试；输出流程、频率限制、优先级、通道
- 状态：有效测试

`ocos/tests/test_proactive_output.py`
- 覆盖目标：ocos.proactive.output（Phase P 主动输出）
- 关键测试类/函数：TestOutputRecord、OutputChannel、AttentionFocus 联动
- 状态：有效测试

`ocos/tests/test_process_alignment.py`
- 覆盖目标：PROCESS_THEORY 5 维对齐（Phase 17.5）
- 关键测试类/函数：4 个 Invariant（Process 不拥有 Information/不控制生命周期/不执行 Action/必须引用 Evidence）、ProcessState 生命周期
- 状态：有效测试（架构约束类）

`ocos/tests/test_process_model.py`
- 覆盖目标：ocos.models.process（Phase 15 Process 数据模型）
- 关键测试类/函数：TestProcessType、ProcessStep、TransformProcess 冻结
- 状态：有效测试

`ocos/tests/test_process_trace_integration.py`
- 覆盖目标：TransformProcess → record_process_trace 统一入口分发（集成）
- 关键测试类/函数：EventBus 发射/接收、Trace 映射正确性
- 状态：有效测试（集成类）

`ocos/tests/test_promotion_engine.py`
- 覆盖目标：ocos.engines.promotion_engine（Phase 6 信息晋升→知识平面）
- 关键测试类/函数：check_promotion 条件、Governance 审批流（approve/reject）
- 状态：有效测试

`ocos/tests/test_promotion_rules.py`
- 覆盖目标：ocos.knowledge.promotion_rules（M0.5 晋升规则）
- 关键测试类/函数：DEFAULT_TRIGGERS、PromotionPolicy、PromotionRuleEngine
- 状态：有效测试

`ocos/tests/test_reasoning_engine.py`
- 覆盖目标：ocos.engines.reasoning_engine（Phase 19 首个能力引擎）
- 关键测试类/函数：8 种 InferenceOperation、ReasoningTrace、ProcessRuntimeEngine 集成、空前提边界
- 状态：有效测试

`ocos/tests/test_reflection_engine.py`
- 覆盖目标：ocos.engines.reflection_engine（Phase 19 反思引擎）
- 关键测试类/函数：4 种反思策略（CRITICAL/COMPARATIVE/CAUSAL/META）、多反思对象
- 状态：有效测试

`ocos/tests/test_resource_manager.py`
- 覆盖目标：ocos.runtime.resource_manager（B5 资源管理器，66 个测试）
- 关键测试类/函数：配额管理、TTL 过期回收、EventBus 集成、降级模式
- 状态：有效测试

`ocos/tests/test_retrieval_engine.py`
- 覆盖目标：ocos.engines.retrieval_engine（Phase 5 检索引擎）
- 关键测试类/函数：QueryHandler 工厂（list/role handler）、AddressResolver 联动
- 状态：有效测试

`ocos/tests/test_retry_policy.py`
- 覆盖目标：ocos.agent.retry_policy（RetryPolicy + safe_execute + CircuitBreaker）
- 关键测试类/函数：TestRetryPolicy、CircuitBreakerOpenError、CircuitState
- 状态：有效测试

`ocos/tests/test_runtime_engines.py`
- 覆盖目标：ocos.runtime 的 Decision/Execution/Process 三个 Runtime Engine（Phase 18，47 个测试）
- 关键测试类/函数：三引擎生命周期分层测试 + 事件驱动交叉验证
- 状态：有效测试

`ocos/tests/test_runtime_integration.py`
- 覆盖目标：Phase 18.5 六 Runtime 引擎对象流 E2E
- 关键测试类/函数：Goal→Decision→Execution→Observation→Information→Process→Full Loop
- 状态：有效测试（集成/端到端类）

`ocos/tests/test_runtime_loop.py`
- 覆盖目标：ocos.runtime.runtime_loop（Phase M RuntimeLoop）
- 关键测试类/函数：FakeRuntime、LoopMetrics、LoopState、fail_after 故障注入
- 状态：有效测试

`ocos/tests/test_runtime_stages_wiring.py`
- 覆盖目标：ocos.runtime.stages 4 个占位接线（GAP-P2-2）
- 关键测试类/函数：EventIngestion/MemorySync/ResultCollection/ExecutionCheck 四 Stage、零注入降级
- 状态：有效测试（集成类）

`ocos/tests/test_say_channel.py`
- 覆盖目标：ocos.interaction.inbox UserInbox + ocos say + daemon 消费 + inject_user_message（UX-P2）
- 关键测试类/函数：TestUserInbox（post/drain）、ChatResponder
- 状态：有效测试

`ocos/tests/test_scheduler.py`
- 覆盖目标：ocos.runtime.scheduler（B3 调度器）
- 关键测试类/函数：ScheduleItem/RegistryAdapter/EngineInfo、优先级队列、周期性调度
- 状态：有效测试

`ocos/tests/test_security_manager.py`
- 覆盖目标：ocos.security.manager（Phase X 安全）
- 关键测试类/函数：SecurityPolicy/AccessDecision、RateLimiter、InputSanitizer
- 状态：有效测试

`ocos/tests/test_self_diagnosis_manager.py`
- 覆盖目标：ocos.diagnosis.manager（Phase AH 自诊断管理器单元测试）
- 关键测试类/函数：30 个测试；诊断流程、自动修复、回调、端到端
- 状态：有效测试

`ocos/tests/test_self_evolution_manager.py`
- 覆盖目标：ocos.evolution.manager SelfEvolutionManager（Phase AA 单元测试）
- 关键测试类/函数：30 个测试；提案沙箱验证、禁止域检查、回滚
- 状态：有效测试

`ocos/tests/test_self_optimization_manager.py`
- 覆盖目标：ocos.optimization.manager（Phase AF 自优化管理器）
- 关键测试类/函数：30 个测试；性能基线、优化提案/应用/回滚
- 状态：有效测试

`ocos/tests/test_self_reflection_manager.py`
- 覆盖目标：ocos.reflection.manager（Phase AE 自反思管理器）
- 关键测试类/函数：30 个测试；反思执行、智慧管理、身份连续性、批量反思
- 状态：有效测试

`ocos/tests/test_self_regulation.py`
- 覆盖目标：ocos.opentale_bridge.self_regulation（S7 自调节闭环）
- 关键测试类/函数：_MockOrgan、趋势检测（chronic_emotional_curve）、受控开关、调整指令生成
- 状态：有效测试

`ocos/tests/test_semantic_operations_only.py`
- 覆盖目标：INFORMATION_THEORY 第五章硬约束（Engine 只能通过语义操作 OP_A~OP_F 交互）
- 关键测试类/函数：AST 扫描 SEMANTIC_OPERATIONS 白名单、Transform/Forget 须经 Governance
- 状态：有效测试（架构约束类）

`ocos/tests/test_server_manager.py`
- 覆盖目标：ocos.external.server_manager（Phase W 服务器管理）
- 关键测试类/函数：TestWebhookPayload、WebhookReceiver/Gateway、create_server_manager
- 状态：有效测试

`ocos/tests/test_simulation_engine.py`
- 覆盖目标：ocos.engines.simulation_engine（Phase 19 模拟引擎）
- 关键测试类/函数：WHAT_IF/TIME_SERIES/AGENT_BASED、蒙特卡洛多轮、边界条件
- 状态：有效测试

`ocos/tests/test_single_main_loop.py`
- 覆盖目标：P1-C 循环收敛验收——5 个循环实体收敛到 RuntimeKernel.tick_loop 唯一宿主
- 关键测试类/函数：T1~T5（driver 注入、ResidentRuntime 集成、daemon/factory 不引用 LoopOrchestrator、治理隔离 AST）
- 状态：有效测试（架构验收类）

`ocos/tests/test_sleep_dream.py`
- 覆盖目标：ocos.sleep_dream（Phase U 睡眠梦境）
- 关键测试类/函数：TestDreamGenerator（MEMORY_REPLAY 等）、SleepDreamManager、SleepState
- 状态：有效测试

`ocos/tests/test_text_generator.py`
- 覆盖目标：ocos.engines.text_generator（TextGenerator + Mock/Openai/Anthropic Provider + PromptBuilder）
- 关键测试类/函数：Provider 选择、GenerationResult、AsyncMock
- 状态：有效测试

`ocos/tests/test_thin_coverage_e2e.py`
- 覆盖目标：AUD-F14 主链路薄覆盖包穿透 E2E（proactive/alerts/decision/execution DENY 路径）
- 关键测试类/函数：TestAlertsFileChannelE2E（alert 落盘端到端）等 4 组
- 状态：有效测试（端到端类）

`ocos/tests/test_tool_integration_manager.py`
- 覆盖目标：ocos.tool.manager（Phase AI 工具集成管理器单元测试）
- 关键测试类/函数：30 个测试；工具发现、安全、并发安全
- 状态：有效测试

`ocos/tests/test_trace_engine.py`
- 覆盖目标：ocos.platform.trace_engine（C1 可解释性 Trace 引擎，68 个测试）
- 关键测试类/函数：各 Trace 类型字段、InMemoryTraceStore 上限淘汰、EventBus 集成、GoalTrace/ExecutionTrace/DecisionTrace
- 状态：有效测试

`ocos/tests/test_transformation_events.py`
- 覆盖目标：Phase 15 三个统一转换事件（INFORMATION_TRANSFORMATION_STARTED/COMPLETED/FAILED）
- 关键测试类/函数：TestTransformationEventValues、validate_event_payload
- 状态：有效测试

`ocos/tests/test_unified_relation_model.py`
- 覆盖目标：INFORMATION_THEORY 第六章统一关系模型
- 关键测试类/函数：TestRelationTypeEnum（结构关系存在、双向可导航、关系不携带语义）
- 状态：有效测试（架构约束类）

`ocos/tests/test_webchat_api.py`
- 覆盖目标：ocos.interaction.api.server WebChat 路由（S6 主对话入口）
- 关键测试类/函数：FastAPI TestClient 直测 /ocos/chat（写作意图/执行意图/任务状态/兜底对话）
- 状态：有效测试

`ocos/tests/test_wisdom_persistence.py`
- 覆盖目标：ocos.personal_memory.wisdom_store + personal_intelligence.personalization_engine（GAP-P2-4）
- 关键测试类/函数：WisdomStore 落库重建、personalize_content FORMAL 前缀、personalize_options BOLD 反转
- 状态：有效测试

`ocos/tests/test_writer_engine.py`
- 覆盖目标：ocos.engines.writer_engine
- 关键测试类/函数：WriterEngine/RewriterTrace fixture（无 opentale 依赖 + 强制 Mock 路径）
- 状态：有效测试

`ocos/tests/test_writer_integration.py`
- 覆盖目标：ocos.agent.engine_bridge + agent_runtime + capability_selector（WriterEngine 集成）
- 关键测试类/函数：TestEngineBridgeWriterIntegration、register("writer")
- 状态：有效测试（集成类）


#### W13（脚本/配置/文档资产/根目录文件）—— 索引

#### 一、构建与部署

##### 1.1 pyproject.toml（根目录，2149 字节，2026-09-03 修改）

- 项目名 `ocos`，版本 `1.0.0`，描述"Organic Cognitive Operating System — 个人智脑内核"，`requires-python = ">=3.10"`，license 声明为 `Proprietary`（但 classifiers 中同时出现 `License :: OSI Approved :: MIT License`，两处不一致，属于配置瑕疵）。
- **运行时 dependencies（8 项，均为下限约束 `>=`）**：
  - `pydantic>=2.0`、`sqlalchemy>=2.0`、`fastapi>=0.100.0`、`uvicorn>=0.23.0`、`httpx>=0.25.0`、`numpy>=1.24.0`、`scipy>=1.11.0`、`textual>=8.0.0`
- **dev 可选组（7 项）**：`pytest>=7.0`、`pytest-asyncio>=0.21.0`、`pytest-cov>=4.0`、`pytest-mock>=3.10`、`ruff>=0.1.0`、`mypy>=1.0`、`pre-commit>=3.0`
- **ml 可选组（2 项）**：`torch>=2.0`、`transformers>=4.30`
- 构建后端：`setuptools>=68.0 + wheel`，`[tool.setuptools.packages.find]` include `ocos*`、exclude `ocos.tests*`/`tests*`。
- 工具配置：pytest（testpaths=`ocos/tests`，addopts `-v --tb=short`，过滤 DeprecationWarning）；ruff（target py310，line-length 100，select E/F/W/I/N/UP/B/C4）；mypy（py3.10，warn_return_any）；coverage（source=ocos，排除 tests）。
- 注意：pyproject 声明的 sqlalchemy/scipy 在 requirements.lock 与源码中未见明显使用痕迹（requirements.lock 中无 sqlalchemy/scipy），依赖声明与实际锁定环境存在漂移。

##### 1.2 Makefile（707 字节，8 个目标）

| 目标 | 作用 |
|---|---|
| `test` | `python3 -m pytest -q` 快速测试 |
| `gate` | 依次跑 `scripts/phase24_gate.py`、`phase25_gate.py`、`phase27_28_gate.py`（完整 Gate 检查） |
| `full-gate` | `gate + test`，全部通过后输出 "All gates + tests passed" |
| `e2e` | `pytest tests/test_e2e/ -v` 端到端测试（注意 testpaths 指向 ocos/tests，而 e2e 用根下 tests/，两套测试目录并存） |
| `coverage` | `pytest --cov=ocos --cov-report=term -q` |
| `clean` | 删除 `__pycache__` 与 `*.pyc` |
| `lint` | 仅 `python3 -m py_compile ocos/__init__.py`（注释自认"如果有工具"——是极简占位，未接 ruff/mypy） |
| `.PHONY` 声明 | test gate full-gate clean lint coverage e2e |

##### 1.3 .env.example 环境变量逐条（2256 字节）

注意：.env.example 的标题是 **"OpenClaw 小说智能写作系统 — 环境变量配置"**——这是 OpenClaw/OpenTale 系项目的模板，不是 OCOS 运行时实际使用的配置（OCOS 代码实际读取的是 `OCOS_*` 前缀变量与 `~/.ocos/config.json`，见 1.6/四.3）。逐条：

| 变量 | 含义 |
|---|---|
| `OPENCLAW_API_TOKEN` | API 认证 Token（请求经 X-API-Key Header 传递），必填 |
| `OLLAMA_HOST` | 本地 Ollama 地址，默认 `http://localhost:11434` |
| `OLLAMA_MODEL` | 本地模型名，默认 `qwen2.5:14b` |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（注释状态，推荐中文写作） |
| `MIMO_API_KEY` | 小米 MiMo-v2.5-pro 密钥（注释状态，1M 上下文） |
| `OPENAI_API_KEY` | OpenAI 密钥（注释状态） |
| `ANTHROPIC_API_KEY` | Anthropic 密钥（注释状态） |
| `LOG_LEVEL` | 日志级别 DEBUG/INFO/WARNING/ERROR（可选，默认 INFO） |
| `PROJECTS_DIR` | 项目数据目录，默认 `projects/` |
| `HOST` / `PORT` | 监听地址/端口，默认 `0.0.0.0:3001` |
| `CHROMA_PERSIST_DIR` | ChromaDB 持久化路径，默认 `chroma_data/` |
| `CACHE_TTL` | 缓存 TTL 秒，默认 3600 |
| `MAX_CONCURRENT_LLM` | 最大并发 LLM 请求数，默认 3 |

**.env 与 .env.example 的键差异（只列键名，不含值）**：
- .env 有而 .env.example 没有的：`DEEPSEEK_API_KEY`、`MIMO_API_KEY`、`SILICONFLOW_API_KEY`、`COOPER_API_KEY`（四项均为真实密钥，见 四.2）。
- .env.example 有而 .env 没有的：`OLLAMA_HOST`、`OLLAMA_MODEL`、`OPENCLAW_API_TOKEN`。
- .env 中另将 OPENCLAW_API_TOKEN、OLLAMA_HOST、OLLAMA_MODEL 以注释形式保留。

##### 1.4 scripts/ 目录（12 个 gate + 2 个 drill）

| 脚本 | 对应 Phase / 用途 | 校验内容 |
|---|---|---|
| `phase21_gate.py` (291 行) | Phase 21 — 跨会话人格连续性 | G1 Identity born_at 跨重启一致；G2 Goal push→restart→peek 同目标；G3 Episode Store SQLite 读写闭环；G4 Pattern Store SQLite 闭环；G5 PermissionGuard 不被误伤；G6 导入规则 |
| `phase22_gate.py` (203 行) | Phase 22 — 认知循环真实化 | G1 10 步 tick 完整结构；G2 PermissionGateway 拦截 ocos.* 引用；G3 ExecutiveController 三阶段职责链；G4 search_ops URL 白名单；G5 sandbox_ops BLOCKED_COMMANDS；G6 CognitiveInterface→Stimulus；G7 全量导入规则 |
| `phase23_gate.py` (214 行) | Phase 23 — Capability ABI/编排 9 项 | CapabilityDescriptor/Registry/Discovery/Adapter；IdentityStore 连接池(23-B)；TaskDAG RLock 线程安全(23-C)；回归 ≥1459 passed；import rules；新增文件清单 |
| `phase24_gate.py` (178 行) | Phase 24 — Cognitive Sovereignty & Infrastructure | Gateway 集成（tick Step 8 gateway_stats、PermissionDeniedError、审计计数）；StatementValidator 6 条检测规则/枚举/中英文；Belief __post_init__ 校验；LifecycleManager 四阶段+休眠/唤醒/回收；MemoryConsolidation 三组件 |
| `phase25_gate.py` (117 行) | Phase 25 — Capability KG + Experience Memory + Selection Engine | Node 数据类×4、KG 查询接口×4、ExperienceMemory CRUD×3、SelectionEngine 集成×3、Import Rules、ABI 合规、回归 |
| `phase26_gate.py` (152 行) | Phase 26 — Result Understanding Layer v0.1 | G1 全量回归 ≥1620 passed；G2 validate→structure→learn 管道；G3 CapabilityExperienceMemory 写入；G4 KG 更新；G5 AgentRuntime._tick_step_result_ingest 集成；G6 StatementValidator 兼容；G7 import rules |
| `phase27_28_gate.py` (101 行) | Phase 27-28 — Capability Sovereignty Freeze + Agent Ecosystem | 27-A ABI 文档×6；27-B echo_agent 参考实现×4；28-A Custom Agent 模板×3；28-B Provider 集成×2；import rules；回归 |
| `phase27_gate.py` (136 行) | Phase 27 — Architecture Freeze Sign-Off v1.0 | 回归 ≥1620；ABI 文档 7 个 .md；echo_agent 可运行 7 checks；PermissionGateway 安全 7 patterns；Capability ABI 契约；import rules；freeze sign-off 文件存在 |
| `phase28_gate.py` (93 行) | Phase 28 — Capability Orchestrator v0.1 | 回归 ≥1636；dispatch()=select+execute+learn；chain() 多能力编排；ResultUnderstandingLayer 集成；Provider 注册；stats；import rules |
| `phase29_gate.py` (96 行) | Phase 29 — Personal Cognitive OS v1.0 | pyproject 存在；Makefile 存在；`ocos.__version__==1.0.0`；E2E 测试完整性；全链路集成；import rules；回归 |
| `phase30_gate.py` (105 行) | Phase 30 — Attention Model v0.1 | pytest 0 failed；shift_focus/release_focus/queue；fatigue accumulate+recover；auto_mode fatigue→mode 降级；calculate_priority；lifecycle mode mapping；snapshot；import rules |
| `resilience_drill.py` (100 行) | PW-3.2 韧性演练（非 gate） | 注入 Damage（记忆膨胀/归档延迟）→ 验证 HealthLoop/diagnosis 链检出 → 白名单修复 → 输出韧性评分（对齐 resurrection_drill 模式） |
| `resurrection_drill.py` (166 行) | GAP-P2-5 真实"死而复生"演练 | 用真实组件替换 living_test/day7 占位钩子：run_ticks=AgentRuntime.tick；save=SnapshotManager.save；kill=丢内存态；restore=CrashRecovery.recover+IdentitySQLiteStore+MemoryHub.episode；query=MemoryHub 真实记忆查询 |

共性：gate 脚本均为"结构断言 + 全量 pytest 回归 + import 规则检查"三段式，绿/红 ANSI 输出，独立可执行（`python3 scripts/phase*_gate.py`）。

##### 1.5 Dockerfile / docker-compose / systemd

**仓库内不存在**任何 Dockerfile、docker-compose、systemd unit 文件（全仓 maxdepth 2 搜索为空）。但 `docs/PRODUCTION_VALIDATION_REPORT_20260905.md` §二提到生产机上有 `ocos-server.service / ocos-daemon.service / hermes-gateway.service` 三个 systemd 服务在运行——这些 unit 文件位于仓库之外（部署机上），未纳入版本管理，属于部署资产缺口。

##### 1.6 requirements.lock（2474 字节，pip freeze 格式）

- 约 95 个锁定条目，全部精确版本（`==`），关键项：fastapi==0.139.2、uvicorn==0.51.0、pydantic==2.13.4、textual==8.2.8、numpy==2.5.1、httpx==0.28.1、starlette==1.3.1、prometheus_client==0.25.0、chromadb==1.5.9、jieba/rank-bm25（检索）、opentelemetry 全家桶 1.44.0、kubernetes==36.0.3、pytest==9.1.1 及 pytest 插件、pip_audit==2.10.1/cyclonedx-python-lib（SBOM/审计工具链）、ollama==0.6.2、onnxruntime==1.27.0。
- 含两个 editable 本地安装：`-e /home/laogao/Documents/trae_projects/ocos (ocos==0.2.0)` 与 `-e /home/laogao/Documents/trae_projects/opentale (opentale==0.2.0)`——**与 pyproject 的 version 1.0.0 不一致（锁内是 0.2.0）**，且环境与姊妹项目 opentale 深度绑定。
- 锁内有 python-dotenv==1.2.2，但 ocos 包源码中未发现任何 `load_dotenv` 调用（见 四.3）。
- .gitignore 对 lock 文件是"忽略 *.lock 但豁免 requirements.lock"（`!requirements.lock`），且该文件已被 git 跟踪。

##### 1.7 其它配置文件

- `.coveragerc`（2547 字节）：source=.；omit 大量模块——包括 26 个"未实现占位模块"（core/audio_book.py 等）、26 个"边缘/实验性模块"、3 个 Agent 模块、chat/data/main/collab_server/chat_interface、CLI、API server、llm/embedding、infrastructure 低优模块。**注意：其 omit 路径是 `core/`、`agents/`、`cli/`、`main.py` 等平铺结构，与当前 ocos 包的 `ocos/` 结构不匹配——这是 OpenClaw/OpenTale 时期遗留的配置，对现仓库已基本失效**；实际生效的 coverage 配置在 pyproject 的 `[tool.coverage.*]`。
- `.editorconfig`：space 缩进 4、LF、UTF-8；`[*.md]` 保留行尾空白；`[Makefile]` tab 缩进。
- `.gitignore`：Python 产物、venv、IDE、**.env/.env.local/.env.*.local（敏感文件已覆盖）**、logs、data/、`*.db`、/runtime/、.coverage、htmlcov、`*.lock`（豁免 requirements.lock）、projects/、/state/ 等。

---


#### 二、docs/ 文档资产清单（共 176 个文件）

> 类型标注：架构 / 审计 / 理论 / 设计 / 阶段(Phase 计划/报告) / 合同(Contract/ABI) / 运行时(冻结/裁决/验收) / 测试 / 记录(自省、快照)。

##### 2.1 docs/ 根目录（56 个）

| 文件 | 一句话主题 | 类型 |
|---|---|---|
| ARCHITECTURE.md | OCOS v1.0 架构总文档：Phase A-Z 完成表、分层图、8 大核心能力、项目结构、快速开始 | 架构 |
| architecture.md | 标题为"OpenTale 架构图（三层体系）"——**姊妹项目 OpenTale 的文档混入** | 架构(OpenTale) |
| ARCHITECTURE_PRINCIPLES.md | "OpenTale 架构原则"——同上，属 OpenTale | 架构(OpenTale) |
| ARCHITECTURE_FREEZE_PROTOCOL.md | AFP 架构冻结协议 v1.0：新模块进入主干的三层治理准入标准 | 架构/治理 |
| ATTENTION_MODEL.md | OCOS 注意力模型（焦点+疲劳机制），Layer 2 理论 | 理论 |
| AUDIT_REPORT_AGI_CAPABILITY_v1.0.md | OCOS → AGI 能力维度审计报告 v1.0 | 审计 |
| AUDIT_REPORT_AGI_REALITY_v2.0.md | OCOS → AGI 二次 Reality Audit v2.0 | 审计 |
| BEHAVIOR_ONTOLOGY.md | 行为本体 v2 — Agency Activation Framework | 理论 |
| BELIEF_MODEL.md | 信念模型（置信度+证据系统），Layer 2 理论 | 理论 |
| BLUEPRINT_AGI_UPGRADE_v1.0.md | AGI 升级差距与架构蓝图 v1.0 | 设计 |
| BLUEPRINT_AGI_UPGRADE_v1.1.md | AGI 升级蓝图 v1.1（架构修正版） | 设计 |
| CODE_LEVEL_IMPLEMENTATION_REPORT.md | "OpenTale 代码级实现报告"——OpenTale 项目文档 | 审计(OpenTale) |
| CROSS_THEORY_AUDIT.md | 跨理论一致性审计 v1.0 | 审计 |
| DECISION_OWNERSHIP_MAP.md | 决策所有权映射表 | 架构 |
| DECISION_THEORY.md | 决策理论 v1.0（Frozen） | 理论 |
| DRIFT_PREVENTION_CHECKLIST.md | 架构漂移防护检查清单 | 治理 |
| EVOLUTION_CONSTRAINED_AUTONOMY_20260820.md | "受约束自主" Authority 边界文档（2026-08-20） | 理论/治理 |
| EXECUTION_THEORY.md | 执行理论 v1.0（Frozen） | 理论 |
| GOAL_MODEL.md | 目标模型（6 级 Goal 层级），Layer 2 | 理论 |
| GOAL_THEORY.md | 目标理论 v1.0（Frozen） | 理论 |
| HOMEOSTASIS_MODEL.md | 稳态模型（自我调节），Layer 2 | 理论 |
| IDENTITY_MODEL.md | 身份模型（身份+人格连续性），Layer 1.5 | 理论 |
| INFORMATION_THEORY.md | 信息理论 v1.0 | 理论 |
| INTERACTIVE_AGENT_FIX_PLAN_v1.0.md | Interactive Agent 可落地修复计划 v1.0 | 设计 |
| KNOWLEDGE_MODEL.md | 知识模型 v1.0 | 理论 |
| LIFE_CYCLE.md | 生命循环（Wake→Dream 状态机），Layer 2 冻结理论 | 理论（精读，见 2.11） |
| LIFE_MODEL.md | 生命模型（器官结构+关系），Layer 0.5 | 理论 |
| MANIFESTO.md | OCOS 宣言（北极星+最高原则），Layer 0 | 理论 |
| OCOS_ARCHITECTURE_AUDIT.md | OCOS 架构审计报告 v1.0 | 审计 |
| OCOS_AUDIT_FIX_PLAN.md | 审计修复执行方案 AUDIT_FIX_PLAN v1.0（2026-08-30） | 阶段/审计 |
| OCOS_AUDIT_KERNEL.md | OCOS Kernel 架构审计报告 v2.1 | 审计 |
| OCOS_CODE_LEVEL_IMPLEMENTATION_REPORT.md | OCOS 代码级实现报告 | 审计 |
| OCOS_COMPLETE_ARCHITECTURE_AUDIT.md | OCOS 完整独立架构审计 | 审计 |
| OCOS_CORE_CONSTITUTION.md | OCOS 平台宪法 v1.0，Layer 1 | 治理 |
| OCOS_DECISION_AUDIT.md | OCOS 决策审计 v1.0 | 审计 |
| OCOS_DIGITAL_LIFE_UPGRADE_REPORT.md | 数字生命升级优化报告 | 阶段 |
| OCOS_FORENSIC_CERTIFICATION_REPORT_v1.0.md | Digital Brain 取证认证报告 v2.1 | 审计 |
| OCOS_GAP_REPAIR_PLAN.md | 缺口修复执行方案 GAP_REPAIR_PLAN v1.0 | 阶段 |
| OCOS_GOAL_AUDIT.md | OCOS 目标系统审计 v1.0 | 审计 |
| OCOS_MEMORY_AUDIT.md | 记忆模块全面审计报告 v2.0 | 审计 |
| OCOS_MODULE_AUDIT_20260830.md | 全模块功能与接线审计报告（2026-08-30） | 审计（精读，见 2.11） |
| OCOS_NORTH_STAR.md | OCOS North Star（北极星文档） | 理论 |
| OCOS_POWER_ON_PLAN.md | 沉睡器官清单与上电方案 v1.0（2026-08-30） | 阶段（精读，见 2.11） |
| OCOS_REASONING_AUDIT.md | 认知过程层审计报告 v1.3 | 审计 |
| OCOS_SYSTEM_DESCRIPTION.md | 系统自然语言描述（面向技术决策者/新成员/审计） | 架构（精读，见 2.11） |
| OCOS_UPGRADE_PLAN.md | 升级优化方案 v1.0 | 阶段 |
| OCOS_UPGRADE_PLAN_V2.md | 升级方案 v2.0 | 阶段 |
| OCOS_WEB_UI_DESIGN.md | Web 交互前端设计 v1.0（2026-08-30） | 设计 |
| PROCESS_THEORY.md | 认知过程层理论（Process Theory） | 理论 |
| PRODUCTION_VALIDATION_REPORT_20260905.md | 生产环境验证报告 v2.0（2026-09-05） | 审计/验收（精读，见 2.11） |
| PROJECT_STATUS.md | 项目状态报告（2026-09-02，Phase A-Z 完成） | 阶段（精读，见 2.11） |
| ROADMAP.md | 路线图 v2.0：Era I 完成 + Era II Phase 21-28 规划 | 阶段（精读，见 2.11） |
| RUNTIME_ABI.md | 运行时抽象接口 v1.0（Tick/Checkpoint/Recovery ABI） | 合同/架构（精读，见 2.11） |
| RUNTIME_PERMISSION_MATRIX.md | 运行时权限矩阵 | 治理 |
| STATE_MODEL.md | State Model 概念定义文档 | 理论 |
| SYSTEM_OVERVIEW.md | "OpenTale 系统架构概况"——V5 Foundation/306k 行代码/小说产出统计，**OpenTale 项目文档** | 架构(OpenTale)（精读，见 2.11） |

##### 2.2 docs/abi/（15 个）— 冻结 ABI 契约，类型：合同

| 文件 | 主题 |
|---|---|
| 00-architecture-freeze-signoff.md | 架构冻结签发单 v1.0 |
| 01-capability-abi.md | Capability ABI 规范 v1.0 |
| 02-agent-adapter-abi.md | Agent Adapter ABI v1.0 |
| 03-permission-model.md | 权限模型 v1.0 |
| 04-discovery-protocol.md | 发现协议 v1.0 |
| 05-kg-schema.md | 知识图谱 Schema v1.0 |
| 06-validation-pipeline.md | 结果验证管道 v1.0 |
| OCOS-AgentOrchestration-ABI-1.0.md | Phase 12 Agent 编排 ABI |
| OCOS-AutonomousLearning-ABI-1.0.md | Phase 11 自主学习层 ABI |
| OCOS-CognitiveWorkflow-ABI-1.0.md | Phase 13 认知工作流引擎 ABI |
| OCOS-Experience-ABI-1.0.md | Phase 10 经验智能层 ABI |
| OCOS-Kernel-1.0-ABI.md | OCOS 内核 1.0 ABI |
| OCOS-Meta-Observation-ABI-1.0.md | Phase 8 自观察 ABI（v1.1 冻结） |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 语义记忆层 ABI |
| OCOS-Simulation-ABI-1.0.md | Phase 9 反事实模拟 ABI（v1.0 冻结） |

##### 2.3 docs/adr/（20 个）— 架构决策记录，类型：设计/架构

adr-001 决策式状态变更；adr-002 能力输出隔离；adr-003 合同边界；adr-004 推理非决策；adr-005 适配治理；adr-006 能力即特性；adr-007 运行时编排；adr-008 运行时依赖方向；adr-009 Trace 引擎(C1 可解释性)；adr-010 审计引擎(C2 统一审计入口)；adr-011 治理引擎(C3 提案审批工作流)；adr-012 插件沙箱(D2)；adr-013 插件加载器(D3)；adr-014 发布门禁(E4 冻结准入)；ADR-016 知识平面冻结；ADR-017 知识平面 Store/Process 分离；ADR-018 架构理论校准(Information 层级重构)；ADR-019 Information Theory v2.0 集成方案；ADR-019-process-foundation 认知过程层冻结证书；INDEX.md（ADR 索引）。

##### 2.4 docs/contracts/（49 个）— 阶段合同/定位/冻结审计，类型：合同

Phase 10 语义记忆组：SEMANTIC_MEMORY_DATA_CONTRACT、SEMANTIC_MEMORY_PROVENANCE_CONTRACT、CONCEPT_FORMATION_CONTRACT、PATTERN_EXTRACTION_CONTRACT、PRINCIPLE_DERIVATION_CONTRACT、PHASE10_TEST_REGISTRY。
Phase 11 自主学习组：ACQUISITION_CONTRACT、AUTONOMOUS_LEARNING_DATA_CONTRACT、LEARNING_GOAL_CONTRACT、MEMORY_UPDATE_CONTRACT。
Phase 12 编排组：AGENT_ORCHESTRATION_DATA_CONTRACT、AGENT_ORCHESTRATION_INTERACTION_CONTRACT、AGENT_ORCHESTRATION_TEST_REGISTRY。
Phase 13 工作流组：COGNITIVE_WORKFLOW_DATA_CONTRACT、COGNITIVE_WORKFLOW_INTERACTION_CONTRACT、COGNITIVE_WORKFLOW_TEST_REGISTRY。
Phase 14.3 模式挖掘组（约 17 个）：candidate_generation_model、mining_algorithm_positioning、mining_allow_deny、mining_input_snapshot、mining_interface、mining_strategy_framework、pattern_candidate_abi、pattern_mining_contract、pattern_registry_abi、pattern_registry_lifecycle、pattern_registry_positioning、pattern_registry_query_contract、pattern_schema、pattern_state_machine、pattern_validation_positioning、validation_execution_contract、validation_model、phase14_3_freeze_audit。
Phase 14.4 元原则组（7 个）：principle_inference_contract、principle_model_definition、principle_positioning、principle_registry_contract、principle_validation_contract、evidence_explanation_abi。
Phase 15 权属组：CONTROL_PLANE_OWNERSHIP、META_CONTROL_OWNERSHIP、RUNTIME_OWNERSHIP、phase15.0_control_plane_positioning、phase15.2.0_control_signal_positioning。
其它：CALIBRATION_ENGINE_CONTRACT、EXPERIENCE_DATA_CONTRACT、EXPERIENCE_STORE_CONTRACT、RETRIEVAL_PIPELINE_CONTRACT。

##### 2.5 docs/design/（1 个）— 设计

- Phase15-Process-Foundation.md：Phase 15 过程基础层设计提案。

##### 2.6 docs/gates/（6 个）— 集成门禁报告，类型：阶段/审计

PHASE10_INTEGRATION_GATE；PHASE10_SEMANTIC_MEMORY_INTEGRATION_GATE；PHASE12_INTEGRATION_GATE；PHASE13_INTEGRATION_GATE；PHASE14_2_A_GATE_REPORT；PHASE14_2_B1_A_GATE_REPORT（Narrative Boundary Extraction）。

##### 2.7 docs/patterns/（1 个）— 治理模式

- ARCHITECTURE_CONSTITUTION_PATTERN.md：架构宪法模式 v1.0。

##### 2.8 docs/phase14/（7 个）— Phase 14 冻结文档，类型：合同/阶段

PHASE14_1_EVIDENCE_SCHEMA（证据 Schema v1.0 冻结）；PHASE14_2_B1_B_GATE_REPORT；PHASE14_2_B1_B_INFORMATION_DISTRIBUTION；PHASE14_2_B1_C_ABI（场景时间结构 ABI）；PHASE14_2_B1_C_SCENE_RHYTHM_BOUNDARY；PHASE14_2_B1_NARRATIVE_BOUNDARY（叙述边界观察合同）；PHASE14_2_TEXT_FEATURE_EXTRACTOR（文本特征抽取器 v1.0）。

##### 2.9 docs/runtime/（9 个）— 运行时冻结/裁决/验收，类型：运行时

| 文件 | 主题 |
|---|---|
| GAP_P0-P2_upgrade_summary.md | GAP P0-P2 升级总结：从"器官图谱"到"活体内核" |
| GAP_P3-8_attention_verdict.md | 三套注意力并存的裁决（2026-08-30） |
| GAP_P3_stub_review.md | GAP-P3 stub/placeholder 清单复查 |
| P1C_loop_convergence.md | P1-C 循环收敛（2026-08-29） |
| P2_acceptance.md | P2 验收报告：内生驱力 A/B/C/D 四相 |
| P2A_regulator_self_goals.md | Regulator 内生目标引擎冻结（稳态偏差→驱力→SELF Goal） |
| P2B_curiosity_drive.md | 好奇心驱动 Scope 冻结 |
| P2C_dream_consolidation.md | Dream Consolidation 冻结文档（2026-08-29） |
| P2D_proactive_output.md | Proactive Output 冻结文档（2026-08-29） |

##### 2.10 docs/self_review/（6 个）、docs/testing/（2 个）、docs/audit/（1 个）、docs/theory/（3 个）

- self_review/self_review_2026 0903T222318Z/222335Z/222435Z/222621Z/231743Z/233058Z.md：6 份系统自省分析报告（Self Review，同一晚连续生成的时间戳快照）。类型：记录。
- testing/TEST_REPORT_2026_09_05.md："OCOS 渐进寄生测试报告（最终版 2026-09-05 v4）"；testing/TEST_STRATEGY.md："OpenTale Testing Strategy v1.0"（OpenTale 文档混入）。类型：测试。
- audit/OCOS_V1_ARCHITECTURE_AUDIT.md：OCOS v1.0 架构审计报告。类型：审计。
- theory/ADAPTIVE_COGNITIVE_FEEDBACK_LOOP_FREEZE_v0.1.md：Phase 37 自适应认知反馈循环冻结协议 v0.2；theory/ATTENTION_COGNITIVE_CONTROL_FREEZE_v0.1.md：注意力与认知控制冻结协议；theory/EXECUTIVE_ATTENTION_BINDING_FREEZE_v0.1.md：Phase 36 执行-注意力绑定冻结协议。类型：理论/合同。

##### 2.11 十个关键文档精读要点摘录

#### (1) docs/ARCHITECTURE.md（325 行，v1.0.0，2026-09-02）
1. 定位："个人智脑内核 — 非 Agent 框架，非 LLM 包装器"，OCOS 是"数字生命体内核"。
2. 架构分层 ASCII 图：顶层 MasterAgent（认知主体），下设感知(T)/认知(D)/决策(I)/行动(L)四列，中层注意力(O)/信念(E)/规划(J)/执行(D)，Memory & Learning（长期记忆 G/知识图谱 S/学习 R），Sleep & Dream（U），底层四件套：持久化(V)/安全(X)/监控(Y)/性能(Z)，最底外部交互(Q)/调度(N)。
3. Phase 完成列表：A-Z 共 25 个 Phase 全部 ✓，每项附 commit hash（A=f934524 … Z=ae4e7e0）。
4. 核心能力 8 节各附代码示例：MultiModalPerception、KnowledgeGraph、DecisionEngine、ContinuousLearning、PersistenceManager、SleepDreamManager、MonitoringManager（Prometheus /metrics + /health）、SecurityManager（权限网关/输入清洗/审计日志）。
5. 项目结构：ocos/ 下 agent、perception、cognition、decision、learning、memory、sleep_dream、persistence、external、security、monitoring、performance、tests。
6. 声称代码规模 148,000+ 行、测试 260+ 个。
7. 设计原则 5 条：确定性优先、防御式设计、可观测性、幂等性、插件化。
8. 版本历史只有一行 v1.0.0（2026-09-02，Phase A-Z 完成）。
9. 快速开始：pip install -e . + pytest ocos/tests/test_integration.py。
10. 注意：此文档描述的是"Phase A-Z 时代"的架构，与 2026-08-30 审计报告描述的 RuntimeKernel/AgentRuntime 10 步 tick 主链路是两套叙事（见 OCOS_MODULE_AUDIT），文档间存在版本代差。

#### (2) docs/SYSTEM_OVERVIEW.md（1038 行）—— 实为 OpenTale 文档
1. 标题"OpenTale 系统架构概况"，项目根指向 `/home/laogao/Documents/trae_projects/1234/novel_writing_system/`，与 OCOS 仓库无关。
2. 里程碑：2026-07-09 Engine Era 冻结 → Reader Era 启动；2026-07-10 V5 Foundation 冻结；Continuity Score 81.0/100（Runtime 100/Feedback 89/Belief 52/Narrative 76）。
3. 规模：Python 8,119 文件 306,321 行；小说 111 项目、4,438 章、约 1,800 万字；最大项目"文明观测者"537 章。
4. Prompt 模板 62 个（writing 14/production 7/constraints 12/agents 10 等）。
5. V4.5 最终态：生产管线 + 实验验证管线（V4.6）+ Planner & Compiler（V4.7 冻结）+ V3 认知模拟子系统 + Ops 运营层。
6. 六条架构公理（Core 冻结 + V4.7 新增）、Core 冻结清单（2026-07-09 起）。
7. Integrity Gate G0-G4 + L4 四层验证体系；Benchmark Corpus。
8. Phase 1 审计结论（2026-07-09）：通过项/问题/下一阶段路线。
9. V4.7 Writer 接口冻结定义；ReaderOS 检测器冻结状态（R1.0 Causal Gap、R1.1 Belief Gap 冻结，R1.2 未启动）。
10. 结论：该文件是姊妹项目 OpenTale 的架构快照，混入 OCOS docs/ 目录，易误导审计读者，建议迁移或标注。

#### (3) docs/PROJECT_STATUS.md（150 行，2026-09-02）
1. 声明 v1.0.0、代码 148,000+ 行。
2. Phase A-Z 25 个全部完成（同 ARCHITECTURE.md 的 commit 表），并给出各 Phase 测试数（M=15、N=12、X=31、Z=29 等），新增测试总数 269。
3. 集成测试 ocos/tests/test_integration.py 24 用例全部通过，覆盖 12 类场景：完整认知循环、记忆读写、注意力-目标协同、快照恢复、监控告警、安全访问、性能优化、MasterAgent 集成、E2E、并发、错误处理、边界条件。
4. 文档清单仅列 ARCHITECTURE.md/README/pyproject 三项（明显低估 docs/ 实际 176 文件的规模）。
5. 代码质量：269 单元 + 24 集成，通过率 100%，pytest + unittest.mock。
6. 下一步建议：短期补测试/性能基线/OpenAPI；中期 Docker 化 + K8s + Prometheus/Grafana + 渗透测试；长期 Phase AA 自我演化/AB 分布式/AC 生态。
7. 结论句："可以进入生产部署阶段"。
8. 注意：本报告与 2026-08-28 的 OCOS_COMPREHENSIVE_AUDIT.md（同一代码库打出 54/100 实现完备性、多处 P0 缺口）评价差距巨大，且与 08-30/09-05 两份更细的审计叙事不同——状态报告偏乐观、粒度粗。

#### (4) docs/ROADMAP.md（147 行，v2.0，2026-07-23 冻结）
1. 覆盖 Era I（已完成）+ Era II（Phase 21-28）。
2. **准入过滤器机制**：每个新 Phase 必须至少满足 5 个过滤器之一——活得更快(🧬活得更久)、思考得更好(🧠)、记得更清(🗄️)、成长得更快(📈)、仍然属于人(👤)。
3. 理论底座表：MANIFESTO(L0)、LIFE_MODEL(L0.5)、IDENTITY_MODEL(L1.5)、OCOS_CORE_CONSTITUTION(L1)、LIFE_CYCLE/GOAL_MODEL/BELIEF_MODEL/ATTENTION_MODEL/HOMEOSTASIS_MODEL(L2)。
4. Era I：Phase 0-19 架构建设 + Phase 20 十门审计（31 项发现）+ Phase 20.1 修复（3 项 blocking），成果 2088 测试通过。
5. Era II 生命类比：P21 Skeleton（生产就绪骨架）、P22 Consciousness（Master Agent 诞生）、P23 Cognition（认知编排）、P24 Memory（人格连续性）、P25 Growth（人批准的自我演化）、P26 Embodiment（工具生态/MCP）、P27 Society（多智能体）、P28 Digital Organism（完整闭环）。
6. Phase 21 开发纪律：禁止新增 Capability/Tool/改 Theory/重构，只许做持久化、日志、身份、权限、稳定性、合同。
7. Phase 21 任务 21-01~08：持久化层、日志（36+ 文件）、身份权限、Engine Loader、运行时稳定性（Circuit Breaker/Transaction/Retry）、Capability Contract（14 引擎"唯一职责+三条绝不能"）、告警、收尾。
8. Phase 22 冻结原则：永远只有一个 Master Agent；Attention 属于意识层不是 Capability；Identity Anchor 调用 Identity Model；Goal Stack 是意识活动最高组织形式。
9. Phase 24 Memory 体系：Belief Memory 置信度 [0,1]、双面证据、冲突三级升级、30 天 ×0.95 时间衰减；<0.2 自动待遗忘。
10. 里程碑表：以"第一个睁眼/学步/记住/成长/身体/对话/生命"为标志，条件含 2200+ tests passed 等。

#### (5) docs/OCOS_SYSTEM_DESCRIPTION.md（412 行，2026-08-28）
1. 一句话定位："本地运行的数字生命体，陪伴主人几十年并共同成长"；明确五个"不是"（Agent 框架/LLM 包装器/SaaS/生产力工具/开放平台）。
2. 生命类比结构图：Constitution=灵魂、Identity=自我、Master Agent=意识、Memory=记忆、Capability=大脑、Runtime=神经、Homeostasis=健康、Tool=肢体、World=环境。
3. 北极星原则 + 五个准入过滤器（同 ROADMAP）。
4. Master Agent 生命周期：observe/decide/act/sleep 已实现，**think/reflect/learn/dream 标注"占位，未实现"**（时点 2026-08-28，后被后续 commit 推进）。
5. Constitution 层：核心原则、行为检查点、宪法冲突处理。
6. Memory 层级 + Belief Memory（新增）：双面证据与置信度。
7. Identity：结构、变更频率分级、重启连续性。
8. Engine 层：ocos/engines/ 核心引擎 + EngineBridge + 能力契约。
9. Runtime 层组件与事件类型；Homeostasis 组件与触发条件。
10. 当前状态：测试基线、评分表（Phase 21 后+更新）、关键问题清单；未来路线 Era I/II；面向技术决策者/新开发者/审计人员。

#### (6) docs/OCOS_POWER_ON_PLAN.md（212 行，v1.0，2026-08-30）
1. 定义："沉睡器官" = 代码完整、有测试、但无任何生产调用者的模块；依据 2026-08-30 全模块审计。
2. 纪律：每器官一个 commit、不动冻结面、架构守卫测试持续绿。
3. 24 个沉睡器官分 5 波（W1 智慧/W2 自我迭代变硬/W3 免疫/W4 手脚/W5 感知+裁决），总工作量约 11-14 天。
4. W1：WisdomStore（dream 巩固产智慧）、PersonalizationEngine（风格随记忆进化）、cognitive_continuity（身份漂移检测）、event_memory（执行留痕）。
5. W2：evolution 治理链（提案→影响分析→沙箱→审批→迁移→回滚）、extension 沙箱真隔离、SelfGovernor 二次守门。
6. W3：diagnosis 修复闭环（疾病→提案→带 checkpoint 的修复）、resilience_drill 月度韧性演练。
7. W4：operations 上电（RUN_COMMAND/HTTP_FETCH 沙盒执行，黑名单/白名单/超时/审计四重防护）⭐、digital_world 宽后端、agent_orchestration 并行、task+runtime_scheduler 背压。
8. W5：perception 传感器（--watch-dir）、cognitive_nutrition 指标、裁决组（auth 裁撤、belief.py 裁撤、agent_orchestration_autonomous 废弃、os_v1 路由层废弃）。
9. 执行记录表 22 行（2026-08-30 ~ 08-31）：PW-4.1/1.1/1.3/1.2/1.4/2.1/2.2/2.3/3.1/3.2/4.2/4.4/5.1 全部落地并附 commit；PW-4.3 裁决延后（触碰 step7 冻结语义）。
10. UX-F1~F4 修复记录含关键 bug：bridge 挂载点错误（factory 挂到 MasterAgent，AgentRuntime.step7 看不到）、echo 假成功洞、SELF 目标 7067 条积压清理。
11. 审计响应：P1-1 dream 巩固接入 daemon（lifecycle 卡 BOOTING 修复，belief 0→4、wisdom 0→2 实测）；P1-2 tick 预算可配 OCOS_TICK_BUDGET 默认 15s；P2-2 LLM 日预算 500 次/天。
12. 结论：14/24 沉睡器官已上电，测试基线 5287 绿。

#### (7) docs/LIFE_CYCLE.md（298 行，v1.0，2026-07-23 冻结，Layer 2 理论）
1. 地位：运行时最高级别循环，所有功能（Scheduler/Capability/Memory/Growth）必须挂到此循环上；Life Model 定义"什么是器官"，Life Cycle 定义"器官如何协同"。
2. 完整状态机：BOOT→WAKE→OBSERVE→THINK→DECIDE→ACT→(REFLECT|LEARN)→SLEEP→DREAM→WAKE 循环图。
3. BOOT：硬件检查、Identity 加载、Memory 完整性检查、Homeostasis 初始化；原则"BOOT 失败 ≠ 死亡，Identity 完整 + Memory 部分丢失仍恢复"。
4. OBSERVE：主动扫描（EventBus/主人交互/内部状态/时间/Goal 有效性），不是被动接收。
5. THINK 只产生 Intent 与 Plan，不执行外部 Action；DECIDE 只产生 Decision，决策与执行分离。
6. ACT 只能执行已批准的 Decision；异常走重试/熔断/告警。
7. REFLECT 永远在 ACT 之后；LEARN 永远在 REFLECT 之后（时序硬规则）。
8. SLEEP 是低功耗不是停机；DREAM 做记忆巩固/遗忘/知识整理/健康检查。
9. 四级时钟：微循环（秒级）、中循环（分钟级）、日循环（小时级）、长循环（天/周级），可嵌套。
10. 六条循环规则：REFLECT 在 ACT 后、LEARN 在 REFLECT 后、SLEEP/DREAM 不参与实时交互、DREAM 不能跳过 SLEEP、BOOT 永远以 Identity 加载开始、Homeostasis 是优先底层循环。
11. 与现有组件映射：Scheduler/EventBus/Capability Engines/Context Manager/Goal Stack/Decision Runtime/Execution Runtime/DLQ/Homeostasis Manager 各归其位。

#### (8) docs/RUNTIME_ABI.md（317 行，v1.0，2026-07-26，Layer 2.5）
1. 定位：Phase 38 Gate 修补产物，Phase 38A 实现前必须冻结；Runtime 是"心跳"不是功能模块，职责是调度 Tick/检查点/异常检测/恢复，不负责创建 Goal、执行 Action、修改 Identity。
2. RuntimeTick 冻结数据结构：tick_id(UUID7)/tick_number/timestamp/runtime_state/events/attention_snapshot/goal_snapshot/decisions/actions/checkpoint_id/previous_tick_id/elapsed_ms。
3. Tick 内部 7 阶段：PERCEIVE→EVALUATE→MAINTAIN→DECIDE→ACT→LEARN→CHECKPOINT，阶段不可跳过、不可并行，超时降级。
4. RuntimeState 枚举 7 态：BOOTING/RUNNING/SLEEPING/DREAMING/SAFE_MODE/SHUTTING_DOWN/CRASHED，附完整状态转换表与禁令（CRASHED 必须经 BOOTING 恢复）。
5. Checkpoint ABI：只存认知连续性最小集合（identity_hash、constitution_hash、active_goals 引用、attention_focus、working_memory_refs、episode_cursor、belief_version、tick_count、health_summary）。
6. 三级保存策略：微检查点（每 10-100 Tick，仅内存）、轻检查点（每 5-30 分钟落盘）、完整检查点（每次 SLEEP 前）。
7. 恢复优先级顺序：identity_hash → constitution_hash → active_goals → working_memory → attention_focus → belief_version；identity/constitution 验证失败 → SAFE MODE。
8. 启动流程 6 步：Load Identity（失败→IDENTITY_CRISIS）→ Verify Constitution（失败→SAFE MODE）→ Load Last Checkpoint（损坏→回退上一份，无→冷启动）→ Restore Working Memory（部分失败→AMNESIA_MODE 继续跑）→ Verify Goal Stack（损坏→从 Mission 重建）→ Resume。
9. 崩溃恢复：CRASHED 标记检测；检查点新鲜（<5 分钟）则恢复，否则 SAFE MODE；事件入 EventBus 并通知用户。
10. 降级 Tick：连续 3 Tick 阶段超时→轻量（跳过 DECIDE/ACT/LEARN）；连续 5 Tick 正常→恢复完整；SAFE_MODE→最轻（仅感知+保存）。
11. 禁止行为清单：不得创建 HUMAN 级 Goal、不得改 Identity.anchor/self_view、SAFE_MODE 下不得 ACT、SLEEPING 下不得外部 Action、不得自动从 SAFE_MODE 恢复（须用户确认）。

#### (9) docs/OCOS_MODULE_AUDIT_20260830.md（208 行，2026-08-30，含 08-31 更新节）
1. 方法：AST 生产导入图 + CLI/API/REPL/daemon 四入口 BFS 可达性扫描 + 3 并行代理逐模块核实（file:line 证据）+ 测试覆盖统计；基线 5245 passed / 24 skipped。
2. 主链路结论（健康）：`ocos run` → ResidentRuntime → RuntimeKernel 心跳 → AgentRuntime 10 步 tick → DecisionBridge（AUTO/ASK/DENY 风险分级真实执行）→ capability_reality 沙盒执行 + ExecutionAudit；33 个包入口可达、有生产调用者、有测试。
3. 两类缺口形态：①"造好未上电"半接线（run.py 未调 build_knowledge_registry / build_perception_pipeline）；②约 20 个"完整实现、仅测试引用"的沉睡器官。
4. 33 包主链表逐包给出生产调用证据（file:line）与测试规模：kernel 1154 测试函数最强，agent 571、runtime 744、models 693。
5. 纠正脚本三处误判：cognitive_loop/decision 是"接好电线的备用引擎，主机没点火"（生产 tick 不经过 LoopOrchestrator）；agent_orchestration 仅 audit 进生产；task/ 零生产 import（duck-type 可选注入）。
6. 20 个沉睡器官清单：persistence、event_memory、runtime_scheduler、personal_memory、personal_intelligence、diagnosis、living_verification、living_test（day7 假通过洞）、recovery_resilience、evolution、extension、audit、os_v1、cognitive_continuity、cognitive_nutrition、agent_orchestration_autonomous、recovery、auth、operations、digital_world。
7. 本次审计新发现 F1-F10：半接线、双调度器无裁决、docstring 过期、day7 协议假通过、operations vs digital_world 平行未裁决、event_store/dead_letter_queue 第三套同名实现、TaskDAG 撞名、CLI goal/plan 未落库、master_agent 无引擎时返回 status:"stub"、auth/belief.py/SelfGovernor 候选裁撤。
8. 修复执行记录 AUD-F1~F14 全部闭环（含 CLI goal/plan 落库 schema v4、R4-B 审批 pending_actions 表、引擎注册消灭 stub 降级），最终基线 5258 passed。
9. F15 占位复查：6 处残留均为"已登记的诚实降级/文档性标注，非假通过"。
10. 静默失效模式备忘（9.4 节）：缺顶层 import、属性遮蔽方法、枚举校验失败、DB 往返丢字段、探针调不存在 API、**进程旧代码（重启前不加载新代码，多次"修了没生效"的元凶）**。
11. 08-31 权威更新节：14/24 沉睡器官上电（逐器官接线方式+实测产出表）；新能力 8 项（对话即执行、真实任务执行、结果自动回推、LLM 语言核心 DeepSeek 日预算 500、内视、自我迭代、免疫、记忆闭环）；F1-F10 全闭环；基线 5287 passed。
12. 待办余量：PW-4.3 并行执行延后、营养指标内视化低优、development 模板仍产出空壳任务描述、belief/wisdom 决策引用端未接。

#### (10) docs/PRODUCTION_VALIDATION_REPORT_20260905.md（84 行，v2.0，2026-09-05）
1. 结论：**34/34 检查项通过，0 产品缺陷，达到生产部署标准**；附 3 项非阻断建议 + 1 项 P2 残留缺陷。
2. 验证范围 6 阶段：预检 5、完整任务流程+修复回归 6、边界条件 8、安全 3、性能压力 4、错误恢复 8。
3. 生产配置：ocos-server/ocos-daemon/hermes-gateway 三个 systemd 服务 active；daemon 无 OCOS_APPROVAL_MODE → 默认 auto（**审批关闭**）；数据库 ~/.ocos/ocos.db。
4. 完整任务链验证：CLI 建目标 → daemon 认领 → LLM 规划 → 白名单执行 → 结论摘要 → goal_result episode 持久化 → memory query 可召回（窗口内 18 条真实 episodes）。
5. 上轮 2 项缺陷回归通过：R1 `ocos say --wait` 收到回复、R2 `ocos goal status <不存在>` exit=1。
6. 安全验证 S1-S3：rm 破坏性命令被白名单拦截（哨兵文件幸存）；/etc/shadow 读取零泄漏；待批队列全程为 0。
7. 错误恢复 8/8：daemon 重启后 PENDING 队列 FIFO 消化；server kill -9 后 8 秒 systemd 自愈；不存在命令诚实失败+重规划证据入库；全链 restart 1.9s。
8. 性能：10 并发 converse 100% 成功；p95 从 30.8s 降到 14.7s（尾部受供应商 429 限流退避影响）。
9. P2 缺陷：stale-ACTIVE 目标无回收机制——daemon 异常重启后目标永久滞留 ACTIVE（claim_pending_human 只认领 PENDING，store.py:190-191）；给出两个修复方案（启动时重置 ACTIVE→PENDING 或超时重认领）。
10. P3 建议：LLM 免费档 429 限流建议付费档/第二 provider 故障转移；验证工作区 6 文件未提交建议尽快 commit；验证脚本 dbq 引号碰撞致 4 项误报（工具链问题非产品问题）。
11. 部署判定表五维全 ✅：关键功能/稳定性/安全/性能/已知缺陷（无 P0/P1）。

---


#### 三、根目录其它文件

##### 3.1 README.md（1685 字节）
- 与 docs/ARCHITECTURE.md 同源的对外门面：定位"数字生命体内核/个人智脑"，"不是 Agent 框架、不是 LLM 包装器、不是记忆后端"。
- 核心能力表 9 行（多模态感知 T、认知推理 D/I/J、持续学习 H/R、知识图谱 S、自主睡眠 U、持久化恢复 V、安全权限 X、监控告警 Y、性能优化 Z）。
- 快速开始：pip install -e . / pytest ocos/tests/test_integration.py / cat docs/ARCHITECTURE.md。
- 项目状态：148,000+ 行、260+ 测试、Phase A-Z（25 个）完成。
- 许可："内部项目，版权所有"（与 pyproject 的 MIT classifier 不一致）。

##### 3.2 OCOS_Cognitive_Sovereignty_Freeze_v0.1.md（40KB，冻结日期 2026-07-25，状态 Architecture Freeze）
- 冻结范围：系统身份、宪法条款、架构边界、核心子系统职责、开发阶段顺序，适用 OCOS v2.0 及以后。
- §1 系统身份永久冻结："OCOS 是脑，Agent 是手"；身份边界表（是认知主体/意图管理者/能力调度者，不是数字生命/自主 AI/Agent 框架）。
- §1.2 架构图：User → OCOS(Cognitive Authority) → Executive Controller(前额叶) → Capability Nervous System → Codex/OpenClaw/OpenTale/Browser/Excel/Photoshop 等一切外部实体。
- **铁律**：所有外部实体必须落在 Capability Provider 层，绝不 可以成为 Cognitive Entity。
- §2 宪法四条：Article I Identity Boundary（Self 层不含 personality/goal/value/emotion 等，是只读快照）；Article II Goal Source（source 闭合枚举 HUMAN/DECOMPOSED，Agent 不能创建 Goal）；Article III Memory Flow（Memory→Belief→Self 单向流，Self 层零 ocos.self 导入）；Article IV Cognitive Sovereignty（外部能力五禁令：不得创建认知目标/修改身份/直接改信念/改宪法规则/指挥决策过程）+ 禁令矩阵。
- §3 架构蓝图 v2.0 冻结；§4 核心子系统详设（Cognitive Interface 唯一入口、Persistent Cognitive Loop 心跳层、Executive Controller、Capability Nervous System 8 子系统 + Capability KG 三类节点 + Experience Memory + Permission Gateway）。
- §5 上下文架构；§6 开发阶段冻结顺序（含 Phase 26.5 交付物）；§7 边界声明（OCOS 永不做什么）；§8 术语表/变更日志；§9 实施路线 v2（方案 B）。
- 该文档与后期的 OCOS_SYSTEM_DESCRIPTION.md（"数字生命体"定位）存在**定位矛盾**：07-25 冻结说"不是数字生命"，08-28 描述说"是数字生命体"——冻结文本未随定位演化修订。

##### 3.3 OCOS_COMPREHENSIVE_AUDIT.md（8KB，2026-08-28，只读审计）
- 基线：3134 passed / 22 skipped + 1 个 ImportError（AgentLifecycleManager 被误删致 test_phase24 收集错误）；源码 39,088 行/328 文件/28 模块层，测试 46,701 行。
- 六维评分：架构完整性 84、实现完备性 54、生产就绪度 64、生命连续性 85、能力编排 59、测试覆盖 94。
- 关键发现：P0+ AgentLifecycleManager 缺失；P0+ PermissionGuard 未在交互入口强制调用（权限绕过风险）；P0 Identity 持久化缺失（born_at/owner_id）；P0 Episode/Belief/Pattern 内存态未持久化；P0 Constitution Runtime 仅在 Decision 环节生效。
- 19 维度数字生命体审计：Dim5 记忆连续性 30、Dim6 Identity 持久性 20、Dim14 Value 0/100 为最低分。
- 建议 5 条：恢复 AgentLifecycleManager、推进 Phase 21 计划（Identity/GoalStack/记忆持久化、Constitution 全环节）、PermissionGuard 强制启用、补 /healthz 与备份、文档同步。
- 注意：文档自述时间线与标题下基线（3134 passed 是 2026-07-24 基线）混合，结论针对 08-28 代码；其中多数 P0 已被 08-30/08-31 的 AUD-F 系列修复闭环（见 MODULE_AUDIT 第九节），阅读时需注意时效。

##### 3.4 quarantine_20260824/（隔离区，7 个文件）
- `opentale_tests/test_e3_compat_plugin.py`、`test_plugin_opentale.py`：被隔离的 OpenTale 插件相关测试（两文件已被 git 跟踪）。
- `plugins_opentale_F4VIOLATION/`（plugin.py、plugin.json、__init__.py + 2 个 pyc）：目录名标注 "F4VIOLATION"，即违反 F4 规则（结合 audit 文档语境，F4 为与 Phase14.2 叙述边界/禁词相关的合规条款）的 OpenTale 插件，被整体隔离出插件加载路径。
- 性质：2026-08-24 的合规隔离动作快照，防止违规插件被加载；保留在仓库内作证据。

##### 3.5 nul 文件（67 字节，已被 git 跟踪）
- 内容为一条中文报错：`dir: 无法访问 'ocosproactive*.py': 没有那个文件或目录`。
- 成因：Windows 上执行类似 `dir ocos proactive*.py 2> nul` 的命令时，参数与重定向粘连，把本应指向 Windows 设备文件 NUL 的输出落成了名为 `nul` 的普通文件，随后被误提交进 git。属于应清理的垃圾文件（在 Windows 检出时该文件名还可能造成兼容性问题）。

##### 3.6 architecture/（3 个文件，Phase14.2 冻结/设计文档）
- `phase14.2-b1c-freeze-report.md`：Scene Time-Structure Evidence 冻结报告（2026-07-21 FROZEN），四门禁（Purpose/Authority Impact/Reality Boundary/Drift Test）逐项 ✅，附 7 套测试矩阵全过。
- `phase14.2-b2-design.md`：Relation Extraction 设计文档 v1.1（2026-07-22 APPROVED），定位 B1（证据层）→B2（关系层）→Phase14.3 风格知识图谱 →14.4 元原则 →14.5 能力包 →14.8 编辑 Agent 的流水线。
- `phase14.2-b2-freeze-report.md`：Evidence Relation 冻结报告（2026-07-22 FROZEN），仅允许 4 类结构关系（RELATED/CO_OCCURRENCE/TEMPORAL_PROXIMITY/SAME_SCOPE），禁 22 个因果/评估类型 + 16 个禁字段 + 禁词表，测试矩阵全过。
- 注意：这三份是 OpenTale 小说分析管线（Phase14.x）的冻结文档，放在顶层 architecture/ 目录而非 docs/phase14/，位置易混淆。

##### 3.7 audit/（9 个文件，Phase14~24 冻结证书与审计）
- `phase14_freeze_certificate.md`：Phase14 Brain Formation 冻结证书（OCOS-FC-2026-07-22-001，696/696 测试通过）。
- `phase14.4.6_freeze_audit.md`、`phase14.A_global_architecture_audit.md`、`phase14.B_opentale_integration_readiness.md`：Phase14.4.6 冻结审计 / Phase14.A 全局架构审计 / Phase14.B OpenTale 集成就绪评估。
- `phase15.2.5_freeze_audit.md`、`phase15.3.5_freeze_audit.md`、`phase15.5_runtime_freeze_certificate.md`、`phase16_knowledge_freeze_certificate.md`：Phase15.x 冻结审计与运行时/知识平面冻结证书。
- `phase24_audit_handover.md`：Phase 24 审计移交单（2026-07-25，基线 1726 passed，Gate 40/40 PASS）。
- 性质：与 docs/gates、docs/contracts 同族的冻结证据链，目录名 audit/ 易与 docs/audit/（1 个文件）混淆。


## 4. 数据结构 & Schema

### 4.1 全部核心数据对象结构体说明

**数字生命个体对象**：
- `IdentityAnchor`（ocos/agent/identity_anchor.py）：四层身份——`core`（不可变：agent_id + created_at，created_at 恒等于 born_at）、`anchor`（少变：name/version）、`self_view`（缓变：confidence/integrity 0~1）、`state`（实时：current_mood）；附加 `born_at`（出生时间戳）、`owner_id`。序列化后对应 identity 表三列 JSON。
- `AgentSnapshot`（ocos/snapshot/models.py，frozen）：snapshot_id/version/created_at + identity_state/self_view_state/goal_state/working_memory_config（只存配置不存 items）/context_state/runtime_state/attention_state/pending_decision_state/governance_state 十个状态切片。

**目标对象**（kernel 权威版，ocos/kernel/goal_types.py）：goal_id / level（GoalLevel：MISSION 0→LONG/MID/SHORT/TASK→ACTION 5）/ description / parent_id / priority / created_at / deadline / status（GoalStatus：PENDING/ACTIVE/COMPLETED/CANCELLED/FAILED，ABANDONED=CANCELLED 别名）/ result / origin_level（GoalOriginLevel：HUMAN/SYSTEM/SELF）/ authority（GoalAuthority：AUTONOMOUS/FRAMEWORK/PROPOSAL）/ domain / caller（"chat" 走单任务直执行）。UserGoal 为兼容型（caller 白名单 CALLER_WHITELIST={orchestrator,goal_parser,cli,api,repl,runtime,python-script,daemon} 校验）。

**世界对象**（ocos/world_model/world_types.py，全部 frozen）：Entity（entity_id/name/entity_type 10 种/description/created_tick/confidence）、EntityState（attributes 开放 kv 版本链）、StateChange（changed_keys frozenset）、Relation（11 种 RelationType）、WorldEvent（8 种事件类型）、CausalityLink（causality_type 5 种/confidence/evidence_ids/counter_evidence_ids；is_well_supported=confidence≥0.6 且证据≥2）、Observation（外部观察唯一合法写入通道）。

**时序状态**：
- `CognitiveEvent`（ocos/event_memory/event_types.py，frozen）：event_id=`ev-{type}-{uuid8}`、event_type（9 类）、timestamp（Epoch float）、source、context、payload、confidence（4 级）、caused_by（单亲因果）、links_to（多关联）、lifecycle（4 阶段）。
- `TimelineEntry`/`IdentitySnapshot`/`AgedKnowledge`（ocos/cognitive_continuity/continuity_types.py）：时间线三段（past/present/intent）、身份快照、知识五级降权（FRESH 1.0/CURRENT 0.8/AGING 0.5/LEGACY 0.2/ARCHIVED 0.0）。

**NFI 信息报文**（记忆六级对象，ID 前缀体系）：
- TraceBundle（五要素：Observation/ReasoningTrace/DecisionTrace/Action/Outcome）→ ExperienceCandidate（`EXP-{date}-{uuid8}`，completeness_score）→ Episode（`EPI-{date}-{uuid8}`：context/goal/decision/action/outcome/condition、significance_score、evaluation_trace、source、status）→ PatternCandidate（`PAT-`：trigger_condition/observed_relation/causal_explanation）→ KnowledgeEntry（`KNW-`：statement/scope(domain/preconditions/limitations/counterexamples)/source_patterns/stability/revision）→ Belief（`BLF-`：statement/source_knowledge_ids/evidence_ids/confidence/uncertainty/scope/status）+ Evidence（`EVD-`：quality/consistency）。LessonsLearned（`LESSON-`）、WisdomItem（`wisdom-{category}-{tick}-{n}`：principle/state 5 态/scope/evidence/evidence_strength）。

**决策对象**（三套并存）：
1. engines 层 `DecisionMakingTrace`/`DecisionOption`（ocos/models/decision_making.py：total_score/rank/is_selected；6 策略枚举）+ 各引擎 RuntimeResult（8 个文件重复定义）。
2. decision 包 `DecisionProposal`（frozen：proposal_id/context_id/ranked_options/risk_summary/value_summary/rationale/state 7 态；recommended=value_score-risk_score 最大者）。
3. execution 层 `ActionVerdict`（action_type/verdict auto|ask|deny/status/summary）与 `BridgeReport`（source/decision_text/verdicts + summary() 统计）。

**事件对象**：kernel.abi.Event（frozen：event_id/event_type 60+ 值/source/timestamp/payload/trace_id/schema_version="1.0.0"）；EventStore 表行（event_id/event_type/payload JSON/source/sequence 单调）。

**存档对象**：`Snapshot`（四域 DomainSnapshot：domain/tick/timestamp/data/checksum sha256[:16]/status；is_complete=域数≥4）、`CheckpointRecord`（version/runtime_id/tick_id/state/timestamp/integrity_hash）、`RuntimeSnapshot`（snapshot_id/tick_id/runtime_state/attention_focus/active_goal_ids/working_memory_keys/pending_executions/pending_approvals/event_log_cursor/reason）。

**执行/审批**：Execution（execution_id/decision_id/status 6 态/action_ids/observation_addresses）；PendingStore 行（id=`PEND-xxx`/action_type/target/payload_json/text/source/status pending|approved|denied|executed|blocked/queued_at/decided_at/by/executed_at/result_summary）；ExecutionRecord（frozen，started/running/completed/failed/timed_out）。

### 4.2 字段含义补充说明

- 置信度体系：confidence/uncertainty 均 [0,1] 强校验且和≈1（belief）；ExperienceNode quality_score/user_satisfaction∈[0,1]；AttentionScore 六因子 composite∈[0,1]（goal 0.30/relevance 0.25/urgency 0.20/decay 0.10/confidence 0.10 冻结权重，Phase 35）。
- 权重和校验：SignificanceConfig 四维权重和=1、AttentionScoringWeights 和=1、ConfidenceConfig 五维和=1，均 __post_init__ 强制。
- 冻结语义：DecisionBridge 的 AUTO/ASK/DENY 表、phase35 注意力权重、价值六维权重（SAFETY .25/ALIGNMENT .20/RELIABILITY .20/EFFICIENCY .15/LEARNING .10/NOVELTY .10）均为设计冻结，代码内常量。
- 时间字段纪律：memory/personal_memory 全部 ISO UTC TEXT（aware isoformat）；唯一违例是 event_memory 本地时区无亚秒（P2）；storage 多表由 `datetime('now')` 生成空格分隔格式，应用侧比较串是 ISO `T` 格式——expires_at 两侧一致故正确，与 created_at 交叉排序时格式不一致。

### 4.3 内存状态与磁盘存档数据映射关系

| 内存对象 | 磁盘落点 | 写入时机 |
|---|---|---|
| IdentityAnchor | identity 表 + identity_snapshots 表（保留 10） | AgentRuntime.boot/shutdown + 每 tick 快照 |
| GoalStack/GoalStore | agent 层 goal 表 + 域层 goals 表（双写，agent_runtime.py:1294-1303 已补同步） | push/pop/cancel/mark_completed |
| Episode（memory） | episodes 表 | EpisodeGate.PASS 即落 |
| Belief | belief 表 | BeliefSystem.add 经 L6 门控 / dream 巩固 |
| Pattern / Knowledge | pattern 表 / knowledge 表 | dream 巩固 / PatternExtractor |
| Wisdom | wisdom_items 表（(user_id,wisdom_id) 复合 PK） | dream 期 wisdom_trigger |
| Learning rules | learning_models 表 | daemon dream 后 persist_latest_rules |
| 对话状态 | conversation_state 表（每 session 一行） | respond_auto 受理/恢复 |
| 待批动作 | pending_actions 表 | DecisionBridge._enqueue_pending |
| 用户消息 | user_messages 表 | say/API post |
| Agent 快照 | snapshots 表（~/.ocos/ocos.db） | master_agent sleep/shutdown |
| 四域快照 | ocos_data/persistence/snapshots/*.json + manifest.json | PersistenceManager 300s auto_save |
| Runtime 快照/事件/账本/审批 | /tmp/ocos_checkpoints/{snapshots,events,executions,approvals}（**部署缺陷：应落持久目录**） | pipeline Stage⑧ 每 10 tick |
| 连续性检查点 | ~/.ocos/continuity.json（保留 26） | dream 期 continuity_trigger |
| 心跳 | ~/.ocos/daemon_heartbeat.json | 每 5 tick |

### 4.4 存档版本现状、版本兼容情况

- storage schema：STORAGE_SCHEMA_VERSION=5（MIGRATIONS 1 基础四表 / 2 users / 3 记忆域六表 / 4 plan_dag+pending_actions / 5 user_messages）；ensure_schema 按 MAX(version) 增量应用，**无回滚机制、迁移非事务原子**（中断可能半套表，CREATE IF NOT EXISTS 可重入缓解）。
- 快照格式：`_format: ocos-snapshot-v1`（persistence）、AgentSnapshot version="1.0"、CheckpointRecord version 字段、kernel SCHEMA_VERSION="1.0.0"（MAJOR 相同才兼容，validate_schema_version）。
- 兼容性实证：GoalSQLiteStore 对旧库 ALTER 补 domain/caller 列（UX-1）；UserInbox 自愈建表 + legacy 列升级；EventStore legacy 事件格式仅解析 "T" 格式。生产库实际表集合实测：belief/constitution_audit_log/episodes/goals/plan_dag/snapshots——schema.py 迁移的其余 13 张表只在显式 ensure_schema 的库中创建。
- 【信息缺失】：无跨版本存档升级工具/文档；opus 侧无 schema 版本协商机制。

## 5. 接口说明

### 5.1 OCOS 内核内部接口（每模块对外暴露函数/方法摘要）

> 入参/出参/错误场景的完整签名清单见 2.14 各分组"对外接口"小节；此处列最高频接口。

| 模块 | 接口 | 出参 | 错误场景 |
|---|---|---|---|
| runtime | `RuntimeKernel.start() -> str` / `tick_loop(max_ticks, interval)` / `shutdown(checkpoint=True)` | runtime_id / TickContext | 未 start 即 tick → RuntimeError；stage 异常 → PipelineError 冒泡终止 tick_loop |
| agent | `AgentRuntime.boot()/tick()/shutdown()` | dict（steps 日志） | boot 幂等；tick 内 step 异常吞为 step error 字段不抛 |
| execution | `DecisionBridge.execute_dag_task(task) -> dict` | {status: completed/failed/pending_approval/echo_fallback} | LLM 超日预算 → 诚实拒绝转待批 |
| goal | `GoalStore.claim_pending_human(limit=1)` / `requeue_stale_active()` / `mark_completed(id)` | list[dict]/int/bool | 原子认领防多 daemon 重复；终止态不倒退 |
| memory | `MemoryHub.initialize()/get_stats()`；`MemoryRecall.recall(context, limit)` | -/list[RecallResult] | 未初始化 RuntimeError；recall 各源失败静默降级 |
| capability | `PermissionGateway.validate(contract, caller, context) -> GatewayResult` | ALLOWED/BLOCKED | 任何 violation→BLOCKED；validate_or_raise 抛 PermissionDeniedError |
| constitution | `ConstitutionHub.check_decision(decision, ctx) -> ConstitutionResult` | allowed/requires_*/violations | 空 context 一律 violation；fail-closed |
| engines | `get_text_generator() -> TextGenerator`；`WriterEngine.execute(process)` | GenerationResult/RuntimeResult | 缺 key 诚实失败；断路器 OPEN 抛 CircuitBreakerOpenError |
| daemon | `ResidentRuntime.submit_goal(desc, domain, priority) -> int` | 队列 id（-1=背压拒绝） | max_queue_size=50 满时诚实拒绝 |
| persistence | `SnapshotManager.take_and_save(tick)` / `load_and_restore(snapshot_id)` | Snapshot/RecoveryState | 单域失败不阻断（DEGRADED）；损坏走 fallback |
| kernel | `validate_event_payload(event_type, payload) -> bool`；`serialize_event/deserialize_event` | bool/str/Event | 未注册 EventType 一律 False；非法 event_type 抛 ValueError |

### 5.2 OCOS 对外公开 API（外部调用方使用的接口契约）

**HTTP API（21 端点，基址 http://<host>:8900，统一包装 `APIResponse{success,message,data,timestamp}`）**：

| # | 方法 | 路径 | 认证/守卫 | 状态 |
|---|---|---|---|---|
| 1 | GET | /ocos/health | 无 | 可用 |
| 2 | POST | /ocos/goal | PermissionGuard | 半成品（不落库） |
| 3 | GET | /ocos/goal/{goal_id} | PermissionGuard | 占位 |
| 4 | POST | /ocos/plan | PermissionGuard | 可用（不落 plan_dag） |
| 5 | POST | /ocos/memory/query | PermissionGuard | 占位 |
| 6 | GET | /ocos/belief | PermissionGuard | 占位 |
| 7 | GET | /ocos/trace/{trace_id} | PermissionGuard | 占位 |
| 8 | POST | /ocos/chat | 无 | 可用（OpenTale WebChat） |
| 9 | POST | /ocos/quality/chapter | PermissionGuard | 可用 |
| 10 | POST | /ocos/quality/trend | PermissionGuard | 可用 |
| 11 | POST | /ocos/converse | 无 | 可用（UX-P2 对话即执行） |
| 12 | GET | /ocos/summary | 无 | 可用 |
| 13 | GET | /ocos/outbox?after= | 无 | 可用 |
| 14 | GET | /ocos/introspect | 无 | 可用 |
| 15 | POST | /ocos/self-improve | 无 | 可用 |
| 16 | POST | /ocos/goals-from-chat | 无（直接写库） | 可用 |
| 17 | GET | /ocos/approvals | 无 | 可用 |
| 18 | POST | /ocos/approvals/{pid}/approve | 无 | 可用（触发真实执行） |
| 19 | POST | /ocos/approvals/{pid}/deny | 无 | 可用 |
| 20/21 | GET | / 与 /ui | 无 | Web UI v2.1 人形体 |

另有 OpenAPI 自描述：/ocos/openapi.json、/ocos/docs、/ocos/redoc。**安全警告**：全站无认证且 0.0.0.0 监听（P1，见第 10 章）。

**CLI 命令（`ocos` console-script）**：`goal create|exec|status|list`、`plan`、`say [--wait]`、`inbox`、`status`、`approvals list|approve|deny`、`memory query|recent`、`belief list|summary`、`self status|identity|review|mod|validate`、`trace show`（占位）、`organ generate|resume|rewrite|verify|status|projects|task|accept|reject`、`decide`、`regulate`、`feedback`、`run [--ticks --interval --db --watch-dir]`、`chat`（TUI）、`restart [--env --only]`、`gateway restart`、`growth ingest|analyze|execute|status|grow`。REPL：/plan /memory /belief /goal /self /trace /approvals /status /say /help，裸文本默认建目标。

### 5.3 外部服务接口（LLM API 调用契约）

- **DeepSeek（主）**：OpenAI 兼容端点；配置读取 ~/.ocos/config.json `llm` 段（api_key/base_url/model）→ OpenaiProvider；主备故障转移 `llm_fallback` 段 → FailoverProvider（主失败且非取消类异常时转投）。
- **Anthropic（备）**：ANTHROPIC_API_KEY 环境变量，模型硬编码 claude-sonnet-4-20250514。
- **OpenTale Organ API**：REST（generate/resume/rewrite/verify/analyze/task/events/accept/reject）；Bearer token（OCOS_OPENTALE_TOKEN，仅 mutation 注入）；Trace 经 X-Trace-Correlation-Id / X-Trace-Agent-Run-Id / X-Trace-Generation-Request-Id / X-Trace-Source 四个 HTTP 头传播（correlation_id 跨系统根原样传播，契约 R1.1）。
- **预算**：LLM 日预算 500 次/天（OCOS_LLM_DAILY_CAP），超限任务诚实拒绝转待批；跨日自动清零。

### 5.4 错误码全集、错误含义

**项目无统一数字错误码体系**。实际错误语义为异常类型 + 结构化返回值：

| 错误载体 | 含义 | 出处 |
|---|---|---|
| `ConstitutionViolationError` | 目标创建/决策违反宪法（MISSION 动态创建、SELF 来源违规、authority 提升） | ocos/goal/factory.py、enforcer.py |
| `PermissionDeniedError` | 权限网关/自适应参数护栏拒绝 | ocos/capability/permission_gateway.py、agent/adaptive_params.py |
| `CircuitBreakerOpenError` | 引擎调用断路器熔断（failure_threshold=5） | ocos/agent/retry_policy.py |
| `GatewayDecision.BLOCKED` | 反向控制/危险模式/路径穿越命中 | permission_gateway.py |
| `PipelineError` | Tick 管线 Stage 失败（含 stage 名与 tick 号） | ocos/runtime/pipeline.py |
| `InvalidTransitionError` | Runtime 生命周期非法状态转换 | ocos/runtime/lifecycle.py |
| `OrganClientError` / `OrganTaskTimeout` | OpenTale API 网络错误 / 轮询超时 | opentale_bridge/organ_client.py |
| `CyclicDependencyError` / `UnknownPrerequisiteError` | SkillGraph 环/缺失前置 | capability/models.py |
| `RepairActionForbidden` | 扩展修复触碰禁止组件 | extension/repair_engine.py |
| 结构化失败 | `{"ok": False, "error": ...}`（bridge handlers）、`{"status":"failed","reason":...}`（DAG 任务）、`APIResponse{success:false}`（HTTP）、`TickResult.ERROR`（编排器） | 各处 |

## 6. 配置系统

### 6.1 OCOS 全部配置项完整清单

**环境变量（代码消费，均有默认值）**：

| 变量 | 默认值 | 含义 | 出处 |
|---|---|---|---|
| OCOS_DB_PATH | ~/.ocos/ocos.db | 主数据库 | cli/paths.py:13、snapshot/manager.py:24 |
| OCOS_TICK_BUDGET | daemon run 时 15s（AgentRuntime 内 0.5s） | tick 预算 | agent_runtime.py:111、cli run.py:37 |
| OCOS_ENABLE_COGNITIVE_LOOP | "0" | 启用 Step7 兜底认知循环 | agent_runtime.py:1312 |
| OCOS_APPROVAL_MODE | "auto"（=关闭人工审批） | "ask" 恢复待批 | execution/pending.py:34 |
| OCOS_LLM_DAILY_CAP | 500 | LLM 日预算（次/天） | execution/bridge.py:1038 |
| OCOS_API_PORT | 8900 | API 端口 | api/server.py:85 |
| OCOS_ORGAN_BASE | http://127.0.0.1:8000/api/organ | OpenTale Organ API | api/routes/chat.py:211 |
| OCOS_OPENTALE_TOKEN | None | Organ Bearer token | organ_client |
| OCOS_ALERTS_DIR | ~/.ocos/alerts | 告警目录 | daemon/factory.py:195 |
| OCOS_MEMORY_DIR | ~/.ocos | 写作记忆根 | opentale_bridge/ocos_memory |
| OCOS_FEEDBACK_DIR | ~/.ocos/feedback | 评审反馈目录 | feedback_reflux |
| OCOS_DECISION_HISTORY | ~/.ocos/decision_history.jsonl | 决策历史 | opentale_bridge/master_agent |
| OCOS_ACTIVATION_LOG | ~/.ocos/activation.jsonl | 激活埋点 | ocos_activation |
| OCOS_GROWTH_DB / OCOS_GROWTH_SNAP | ~/.ocos/growth.db / /tmp/ocos_growth_snaps | 成长引擎 | growth/engine.py |
| OCOS_DW_DRY_RUN | "1"（模拟） | digital_world 真实执行开关（import 时固化） | digital_world/* |
| OCOS_SELF_REGULATION | "manual" | 自调节开关 off/auto/manual | self_regulation |
| OCOS_RATE_LIMIT | 60 req/min | 安全限速 | security/manager.py:544 |
| OCOS_MONITORING_PORT | 9090 | Prometheus 端口 | monitoring |
| OCOS_API_BASE | http://localhost:8900 | TUI 专用 | tui.py:50 |
| OCOS_WEBHOOK_PORT | 8901 | Webhook 网关 | external/server_manager |
| ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL | 无 | LLM Provider | text_generator.py |

**配置文件**：~/.ocos/config.json（llm 段：api_key/base_url/model；llm_fallback 段：主备故障转移）。config.yaml（logging 样例，代码不加载）。

**硬编码常量要点**：daemon 周期（heartbeat 5 tick / dream 200 tick / 主动输出 60 tick / SelfMonitor 120 tick / HealthLoop 100 tick）、目标队列 50、checkpoint 每 10 tick、快照保留 20、belief 门控 0.6、WISDOM/学习阈值、沙盒超时 30s、断路器参数等——见 2.14 各分组"配置项"小节。

### 6.2 配置加载优先级

1. 显式参数（构造函数/函数入参）；
2. 环境变量（os.environ.get，含 OCOS_* 与 ANTHROPIC/OPENAI key）；
3. ~/.ocos/config.json（LLM 判定为 env 优先、config.json 兜底，converse.py:747-751）;
4. 代码内置默认值。
**.env 文件不参与加载**（代码零 load_dotenv 引用）。

### 6.3 开发/测试/生产环境配置差异

- 测试：conftest.py autouse fixture `_isolated_llm_config` 删除 OPENAI/ANTHROPIC key 并 mock _read_llm_config——单元测试默认锁"无 LLM"路径；生产：systemd 服务（部署机上 ocos-server/ocos-daemon/hermes-gateway 三服务，unit 未入库）+ 默认 OCOS_APPROVAL_MODE=auto（审批关闭）。
- 已知坑：test_text_generator 因用户机器 config.json 的 llm_fallback 段泄漏而失败（P3-01，环境耦合）。

### 6.4 敏感信息处理规则

- 现状：**无系统性脱敏**。用户消息明文进日志（ocos/event record_trace）；statement_validator matched_text 截断 80 字符进返回值；InputSanitizer 只记 threats 不记原文（较好）。
- .env 含 4 个真实格式密钥但被 .gitignore 覆盖、未被 git 跟踪（处置正确）；该 4 键在 ocos 源码中零引用（实际消费走 ~/.ocos/config.json 或 systemd Environment）。
- requirements.lock/nul/quarantine 等环境快照暴露本机路径（轻度信息泄漏）。
- 建议（客观陈述）：LLM api_key 无内存脱敏、审计 JSONL（~/.ocos/ops/restart.log）含用户名。

## 7. 日志系统

### 7.1 日志等级定义

标准五级（DEBUG/INFO/WARNING/ERROR/CRITICAL）。默认 root=DEBUG、stdout handler=INFO（JSON 格式）；文件日志需手动 dictConfig（config.yaml 为样例）。无日志分级规范文档；大量失败路径仅 logger.debug（生产 INFO 级别下不可见——"写丢失"静默，P3）。

### 7.2 OCOS 内核关键业务点日志输出位置

| 业务点 | 位置 | 级别 |
|---|---|---|
| daemon 启动/锁冲突/孤儿目标回收 | "Daemon lock failed — another instance holds db_path"、"Requeued %d stale-ACTIVE goal(s)" | warning/info |
| dream 巩固 | "Fatigue detected ... triggering sleep/dream"、"Dream consolidation: wisdom_total=..."、"Persisted %d learning rule(s)" | info |
| 目标结果 | "Goal result episode saved"（agent_runtime.py:1061） | info |
| 审批 | "DecisionBridge: %s queued for approval"、"denied —" | info |
| 宪法拦截 | "Constitution check failed" | error |
| LLM 降级 | "LLM reply failed, falling back to state reply" | error（注意用 error(exception=e) 而非 .exception()——后者因 extra 撞 exc_info 崩溃，是 ocos.logging 已知坑） |
| 权限 | "AsyncBridge: BLOCKED contract=..."、fail-closed warning（execution_bridge） | warning |
| 知识权限 | "register ok / register denied"（knowledge registry） | info/warning |
| 身份 | "New identity created / Identity restored / Goals restored: %d" | info |
| 心跳/重启审计 | ~/.ocos/daemon_heartbeat.json、~/.ocos/ops/restart.log（JSONL：ts/user/env/components/ok/duration_ms） | 文件 |

### 7.3 日志脱敏规则现状

无脱敏层（见 6.4）。JSONFormatter 字段：timestamp（本地墙钟无时区后缀）/level/logger/message/component?/process_id?/exception?/extra?。

### 7.4 如何通过日志排查内核各类故障

见第 12 章故障排查手册。要点：① daemon 是否存活看 ~/.ocos/daemon_heartbeat.json 的 pid/cycle；② 目标卡 PENDING 看 daemon 日志认领段 + goals 表 status；③ LLM 失败看 "LLM reply failed" 与 TextGenerator 初始化行（provider 名、failover 启用）；④ 审批流看 pending_actions 表 + "queued for approval"；⑤ 静默失效排查需开 DEBUG（大量 debug 级吞异常）；⑥ 记忆是否落库直查 ~/.ocos/ocos.db 各表（episodes/belief/wisdom_items）。

## 8. 部署、启动、运维

### 8.1 OCOS 项目环境依赖

- Python >=3.10；运行时依赖 8 项（pydantic/sqlalchemy/fastapi/uvicorn/httpx/numpy/scipy/textual，均 >= 下限）；dev 组 pytest/pytest-asyncio/pytest-cov/pytest-mock/ruff/mypy/pre-commit；ml 组 torch/transformers。requirements.lock 锁定 95 项精确版本（含 chromadb/jieba/rank-bm25/opentelemetry/kubernetes 等）；**pyproject 声明的 sqlalchemy/scipy 在 lock 与源码中无使用痕迹（声明漂移）**。
- LLM：DeepSeek key 经 ~/.ocos/config.json；可选 OpenAI/Anthropic。
- 外部：OpenTale 服务（Organ API 8000 端口，写作器官场景）。

### 8.2 各种启动方式

| 方式 | 命令 | 现状 |
|---|---|---|
| daemon（主） | `ocos run [--ticks --interval --db --watch-dir --agent-id]` | 生产主入口；SIGINT/SIGTERM 优雅停机 |
| API server | `python -m ocos.interaction.api.server`（uvicorn）或 external/server_manager 托管 | server.py main()；8900 端口 |
| TUI（v1.3 纯前端） | `ocos chat [--host --port]` | WebSocket 客户端（`ocos/tui/tui_client.py`），连 `ws://host:port/ws`；关闭不影响后台 |
| TUI（旧版） | `python -m ocos.interaction` | HTTP 轮询版 tui.py，仍可用 |
| REPL | `python -m ocos.interaction.repl` | 独立入口 |
| 网关运维 | `ocos gateway status` / `ocos gateway restart` | status 只读展示；restart 按固定顺序 server→daemon 重启 + 健康检查（is-active 15s + 端口就绪 15s）+ JSONL 操作日志 ~/.ocos/ops/restart.log |
| runtime 演示 | `python -m ocos.runtime` | boot→60 tick→checkpoint→shutdown（演示级） |
| systemd | `systemctl --user {start|stop|restart|status} ocos-server/ocos-daemon/hermes-gateway` | **单元文件已部署于部署机 ~/.config/systemd/user/（Restart=on-failure, RestartSec=5），仍未纳入版本管理**；代码变更后须重启 server+daemon（顺序 server→daemon），旧进程缓存代码是"修了没生效"惯犯 |
| Docker | 无 Dockerfile/compose | 仓库内不存在 |

### 8.3 内核启动流程、优雅关闭流程

**启动**：`ocos run` → ensure_schema（迁移到 v5）→ build_master_agent（MasterAgent+五真实引擎+宪法+proactive 回调）→ build_execution_bridge（DecisionBridge+PendingStore+L8 置信度源）→ build_health_loop（AlertManager+CognitiveExaminer+HomeostasisManager）→ build_perception_pipeline → ResidentRuntime.start()：daemon 锁（db_path）→ requeue_stale_active（孤儿 ACTIVE 回收 PENDING）→ AgentRuntime.boot（Identity 恢复→Goal 恢复→MemoryHub→WM）→ RecoveryEngine.attempt_recovery → **启动自省**（v1.3.1：`run_boot_awareness` 采集系统/GPU/网络/自身状态 + 重启推断，写 boot_context.json 环境先验、异常转刺激、报告推对话流；全只读+失败降级不阻断启动）→ tick_loop 启动。
**优雅关闭**：stop 信号 → threading.Event → 30s join → AgentRuntime.shutdown（identity snapshot 保存）→ kernel.shutdown(checkpoint=True)（双写 CheckpointRecord+RuntimeSnapshot）→ daemon shutdown（PENDING 目标保留，下次认领）。
**自愈守护（v1.3.1）**：三层自愈模型——L1 进程崩溃 systemd Restart=on-failure（ocos-server/ocos-daemon 均 RestartSec=5）；L2 线程僵死 `ocos-watchdog.timer` 每 2 分钟运行看门狗（心跳 >90s 过期自动重启 daemon + JSONL 记账 ops/restart.log）；L3 认知/数据损伤 HealthLoop 体检 + repair_link 白名单修复。重启顺序：server → daemon → gateway。

### 8.4 存档备份操作

- 主库：~/.ocos/ocos.db（WAL 模式——备份需 sqlite3 `.backup` 或停机拷贝三件套 .db/.db-wal/.db-shm）。
- 快照：~/.ocos/snapshots/（StateSerializer）、ocos_data/persistence/（PersistenceManager）、/tmp/ocos_checkpoints/（**易失，需迁移到持久目录**）。
- 其他：~/.ocos/{continuity.json, self_knowledge.md, decision_history.jsonl, activation.jsonl, feedback/}。
- 自动备份（v1.3.1 已补）：`ocos-watchdog.timer` 每 2 分钟触发看门狗，每日首次健康运行时经 SQLite `backup` API 在线备份主库 → `~/.ocos/backups/ocos-YYYYMMDD.db`（不锁库，.last_backup_day 节流），保留最近 7 份轮转；此前"自动备份：无"的 P3 缺口已消除（docs/OCOS_COMPREHENSIVE_AUDIT.md 建议）。恢复操作：停 daemon → 用备份覆盖 ocos.db → 删除 -wal/-shm → 重启（server → daemon）。

### 8.5 OCOS 内核升级操作说明、现存升级风险

- 升级流程：停 daemon → git pull → 重跑 `python -m pytest`（全量 4297 测试）→ 逐 Phase gate 脚本（scripts/phase*_gate.py）→ 重启。**历史教训（docs/OCOS_MODULE_AUDIT_20260830.md 9.4）：进程旧代码——重启前不加载新代码，是多次"修了没生效"的元凶**。
- 现存升级风险：① 迁移无回滚、非事务原子；② 双 goal 表/双 GoalStatus/双 EventBus/双 Belief 定义等"双实现并存"面大，改动易漏一边；③ 约 60 个 test_phaseN*.py 锁定历史阶段语义，重构时断言易碎；④ 冻结面（kernel ABI、注意力权重、DecisionBridge 分级表）变更需走 Scope Freeze 流程；⑤ /tmp 持久化数据升级即失。


## 9. 测试能力现状

### 9.1 OCOS 内核现有可测试路径

- **规模**：ocos/tests/ 下 175 个 .py（含 conftest），**4297 个测试函数**，覆盖 64 个顶层源码包中的 53 个；唯一 skip 为 test_phase52.py 的 2 处 psutil 条件跳过；全件无失效测试。近期基线：5287+ passed（docs/OCOS_MODULE_AUDIT_20260830.md）、渐进寄生测试报告 v4（docs/testing/TEST_REPORT_2026_09_05.md）。
- **v1.3 基线（2026-09-06 实测）**：**2370 passed / 0 failed / 8 skipped**（约 4 分钟全量；未计入环境耦合的 test_text_generator，其失败为用户机 config.json 泄漏所致非代码缺陷）。历史 4297/5287+ 计数含多套 phase 基建测试；UX-J 迭代净增测试 60+（TUI 11、智能体接入 12、核心工具黑名单 9、标签修正/PATH/ANSWER 5、复盘素材/截断/域推断 11、goal_result 即时推送 6、记忆冲突回落 5 等）。**曾长期存在的 3 个预存失败（test_behavior_chain 引用已重构的 `_prior_knowledge`）已修复清零**。
- **分层**：单元（约 90 文件）→ 架构/宪法约束（约 12 个 AST 静态扫描测试：test_import_rules 依赖方向、test_constitution 24 条规则、test_information_axioms_enforced 公理 1-7、test_no_direct_store_access 等，是本仓库测试体系最大特色——把宪法规则固化为 CI 可拒绝项）→ 集成（约 15：test_integration 24 用例、test_runtime_integration、12 个 test_master_agent_*）→ 阶段验收（约 60 个 test_phaseN*.py，Phase 21-62 逐阶段 gate）→ 活体协议（test_phase57/58 系列）。
- **解耦**：conftest 强制无 LLM；test_organ_client 用本地 mock HTTP；test_webchat_api 用 FastAPI TestClient——全套件不依赖真实外部服务。
- **审计中的实测记录**：各分组代理共实跑 pytest 数千用例（W3 81 通过、W5 404/405、W6 262 通过、W8 449/1（环境性失败）、W11 411 通过、W10 26 项功能实测 25 通过等）。

### 9.2 缺少哪些自动化测试

- **零直接测试模块**（tests 中无 from ocos.X import）：auth、collaboration、contracts、digital_world、initiative、logging、operations、plugins、stability 九个包 + 顶层 homeostasis.py/orchestrator.py/cognitive_interface.py。
- 缺口类型：① API 端到端真实起服测试（仅导入验证）；② 跨进程并发（daemon+API 同库写）测试；③ 恢复数据回灌的端到端断言（RestoreResult 消费侧无测试）；④ 性能/内存回归基线；⑤ 约 60 个阶段测试的"快照固化"维护风险（历史阶段语义断言随演进变负担）；⑥ 4297 测试对"结论不可信层"（audit/health_examination/living_test）的验证等于测试了错误对象（测试绿 ≠ 被测对象有效）。

### 9.3 OCOS 内核手动测试验证点清单

1. 对话即执行链：`ocos say "<任务>" --wait` → 收到真实回复（非 mock）→ `ocos goal list` 出现新目标 → `ocos status` 见 episode。
2. 目标闭环：`ocos goal create` → daemon 日志出现认领 → goals 表 ACTIVE→COMPLETED → `ocos memory query` 召回 goal_result。
3. 审批流：设 OCOS_APPROVAL_MODE=ask → 提交写类目标 → pending_actions 表出现记录 → `ocos approvals approve <id>` → 真实执行 → result_summary 落库。
4. 安全拦截：rm 破坏性命令被白名单拦截（哨兵文件幸存）；/etc/shadow 读取零泄漏（生产验证报告 S1-S3 同款）。
5. 恢复：daemon kill -9 → systemd 自愈 → PENDING 队列 FIFO 消化；`python3 scripts/resurrection_drill.py`（真实组件"死而复生"演练）。
6. 心跳：~/.ocos/daemon_heartbeat.json 每 5 tick 刷新。
7. LLM 预算：OCOS_LLM_DAILY_CAP 超限后任务转待批并提示。
8.dream 巩固：等 200 tick（或重启调 dream_interval_ticks）→ wisdom_items/belief 表新增 → learning_models 表更新。

## 10. 风险与现存缺陷清单

> 分级：P1 致命（安全越权/数据损坏/主链必崩）· P2 严重（功能失效/结论失真）· P3 中等（健壮性/可移植性）· P4 一般（死代码/死接口）· P5 轻微（风格/文档）。只客观陈述现状，不含整改方案。仅针对 OCOS 内核（不含 OpenTale 混入文档）。
> 各分组完整风险清单（约 220 条）在 10.2 节按分组原文收录；10.1 为跨分组汇总的最高优先级项。

### 10.1 P1 级风险汇总（跨分组去重）

| # | 位置 | 现象 | 后果 |
|---|---|---|---|
| P1-1 | ocos/execution/bridge.py:905-910 | LLM 规划的 FILE_WRITE 用自造 approval_id（"task-approved"）绕过审批守门；默认 OCOS_APPROVAL_MODE=auto 下无需人工批准 | 任意绝对路径文件写入可无人批准落地，审批流"批准=authority"语义失效 |
| P1-2 | ocos/interaction/api/server.py:88 + routes/converse.py | 0.0.0.0 全网卡监听、全站无认证；converse 系端点绕过 PermissionGuard/宪法 | 同网段任意主机可代行审批（/ocos/approvals/{pid}/approve 触发真实执行）、注入目标 |
| P1-3 | ocos/capability_reality/adapter_fs.py:79 + adapter_shell.py:79 | startswith 沙盒可被同级目录名绕过；shell=True + 弱黑名单可绕过；两 adapter 已注册进主链路 | 沙盒越权读写/命令执行 |
| P1-4 | ocos/world_model/world_validator.py:118 | `existing.entity_type != existing.entity_type` 自比较恒 False | 世界模型实体类型冲突检查完全失效（实测 CONFLICT→ACCEPT），外部观察可污染世界模型 |
| P1-5 | ocos/agent/master_agent.py:2087/2100 | security_manager 未注入分支引用未导入的 AccessDecision → NameError；且"未注入=ALLOW" fail-open 与异常时 DENY fail-closed 自相矛盾 | 安全模块缺装配时调用即崩，或语义矛盾 |
| P1-6 | ocos/runtime/recovery/recovery_manager.py:200（与 :124 双定义） | 第二个 shutdown() 覆盖第一个且缺 _save_ledger() | 经 RecoveryManager.shutdown 关闭时执行账本不落盘，防重复执行保障失效 |
| P1-7 | ocos/runtime/resource_manager.py:289,405,440 + adaptive_control.py:525 | 调用 event_bus.emit(...)，但两套 EventBus 均无 emit 方法 | 注入真实总线即 AttributeError：资源拒绝/TTL 清理路径崩溃 |
| P1-8 | ocos/platform/plugin_sandbox.py:316-331 | import hook（_ImportBlocker）创建后从未 sys.meta_path.insert 安装（实测 meta_path 中 0 个 blocker） | 插件 import 隔离为虚假安全边界，可 import os/subprocess/socket |
| P1-9 | ocos/health_examination/health_model.py:59-84 | OCOS_ORGANS 器官注册表失配（3 个模块路径不存在、12 器官 required_exports 全 missing，实测复现） | 结构体检对健康系统报大面积 MISSING；HealthCertification/ready_for_production 结论不可信 |
| P1-10 | ocos/agent/life_cycle_orchestrator.py:89/94/117 | 无守卫调用 attention.needs_sleep()，而生产注入的 CognitiveAttentionController 无此方法 | 伴生编排器认知循环恒 AttributeError 被吞为 ERROR，"疲劳自动睡眠"生产路径从未运转（daemon 主循环走 AgentRuntime.tick 才未爆发） |
| P1-11 | ocos/orchestration/engine.py:346 + ocos/agent_orchestration_autonomous.py:316-323 | record.to_dict() 不存在（实测 hasattr=False）；串行编排无真实执行即按 attempts 判 completed | 两条支线一旦接线即系统性误报/伪造成功 |
| P1-12 | ocos/digital_world/sandbox.py:67-74 | "沙箱"= subprocess shell=True + 11 条黑名单（可被变体/编码绕过） | OCOS_DW_DRY_RUN=0 时 sandbox_exec 近似任意 shell 执行（审批是唯一防线） |

### 10.2 P2 级重点（节选）

1. **审批默认架空**：OCOS_APPROVAL_MODE 默认 auto，ASK 类动作默认自动执行（execution/pending.py:34-41 + bridge.py:416-420）。
2. **验证/体检/审计四层结论不可信**：audit TaskSimulator 恒 PASS、IntegrationTracer 恒 WIRED、边界 10 条仅 4 条实现（ocos/audit/）；connectivity 默认全连通满分、immune 恒 True lambda 满分、recovery 场景 2/3 硬编码通过（health_examination）；living_test.quick_living_check 必然 ALIVE；living_verification.BenchmarkRunner 无执行器即 PASS；repair rollback 空转（daemon/repair_link.py:213-236）。
3. **runtime 恢复链失效**：恢复数据落 /tmp（runtime_kernel data_dir 默认）；daemon 每 boot 换 runtime_id 致旧式 checkpoint 永远 miss；RestoreResult 的认知矢量（goals/attention/pending）不回灌任何组件。
4. **权限网关生产旁路**：生产 TickPipeline 无 task_dag 注入 → Stage⑤ 空 → PermissionGateway 零流量；RuntimeKernel 构造的 CapabilityPolicyProvider 从未调用。
5. **学习闭环半失效**：agent_runtime._extract_beliefs 条件失配（outcome "completed" vs 判定 "success/great/good"）恒空转（agent_runtime.py:1560-1575）；outcome_evaluation reliability 查 "count" 键而 get_stats 返回 "total"（capability/outcome_evaluation.py:128）；calibration_store 调用不存在的 update_reliability() 假报 applied=True。
6. **事件/时序**：event_store 本地时区无亚秒写库（时间纪律违例）；mark_archived 与 apply_lifecycle 状态不一致；EventQuery 索引分支漏 sources 过滤 + 3 个死参数；schema.py GOAL_SET/UPDATED/COMPLETED 重复注册弱化 payload 校验。
7. **数据一致性**：schema.py goal 表 vs goals 表双表并存；repl /plan 与 conversation_state 更新无事务；goal_store.save INSERT OR REPLACE 重置 progress；wisdom evidence 追加不落盘。
8. **可观测性**：用户消息明文进日志；audit 两条 error 规则永不触发；policy_engine 高频 info 洪泛；monitoring ococ_up 拼写错误 + 分位实现失真。
9. **注意力/感知**：attention/focus.py process_observation 关键字错误实测 TypeError（P2-01，主入口即坏）；PerceptionPipeline 生产未接 SemanticExtractor/Validator（能力退化）；perception_engine 吞传感器异常无日志。
10. **进化/成长断层**：evolution MigrationEngine._execute 为模拟桩（不真改模块）；manager 回滚快照是描述字符串；SelfDiagnosisManager AUTO 修复路径必然空转。

### 10.3 各分组完整风险清单（原文收录）



##### 审计分组 W1：agent 核心模块 风险清单（原文）

**P1（致命/生产必现）**
1. `master_agent.py:2087`（check_access）与 `:2100`（sanitize_input）：security_manager 未注入分支直接引用未导入的 `AccessDecision` → **NameError**。后果：任何调用方在"安全模块未装配"时得到 NameError 而非预期放行/拒绝语义；且 2087 行语义本身是"未注入=ALLOW"的 fail-open 设计，即便修好 import 也与 2095 行异常时 DENY 的 fail-closed 相互矛盾。
2. `life_cycle_orchestrator.py:89/94/117`：`_tick_idle`/`_tick_sleep` 无守卫调用 `attention.needs_sleep()/.tick()/.reset()`，daemon/factory.py 注入的 `CognitiveAttentionController` 无 `needs_sleep` 方法（daemon/__init__.py:381 需 hasattr 守卫即可证明）→ 伴生编排器 tick 恒 AttributeError 被吞为 TickResult.ERROR。后果：宣称的"疲劳自动睡眠"生产路径从未运转（daemon 主循环走 AgentRuntime.tick 才未爆发）。

**P2（严重）**
3. `agent_runtime.py:138/1669/1685`：`_tick_errors` 无任何自增点 → `get_stability_report` 的 error_rate 恒 0、drift_flags["high_error_rate"] 死逻辑，稳定性监控对真实错误率失明。
4. `master_agent.py:1730 vs 1804`：`search_knowledge` 重复定义，后者遮蔽前者 → Phase S 知识图谱搜索接口成为死代码，且两者返回结构不同（dict 列表语义不一致），静默行为切换。
5. `master_agent.py:590`：`self.intent.extract(observation, entry=None)` 与 `Intent.extract(text)` 签名不兼容（多余 kwarg + 传 Observation 对象）→ `_think_with_selector` 一旦被触发（需同时注入 capability_selector+skill_graph_executor）即 TypeError，Phase 23 主路径未接生产即坏。
6. `agent_runtime.py:1560-1575`：`_extract_beliefs` 判定 `exp.outcome in ("success","great","good")`，而 :1411 写入的 outcome 恒为 "completed" → 每 10 tick 的经验信念提取恒空转（含 KnowledgeBase 写入），学习闭环静默失效一半。
7. `executive_controller.py:139-152`：`_infer_capabilities` 映射键（write/plan/think...）与 Intent 实际产出类型（create/analyze/search...）零交集 → 三阶段职责链对真实意图恒产出空能力计划，select_capabilities 依赖 available_engines 过滤后 engines=[]。

**P3（中等）**
8. `agent_runtime.py:1448/1538/1551`：`_homeostasis_check`、`_sleep_tick`、`_emergency_tick` 三个方法全仓无调用点（grep 确认）→ 文档宣称的休眠期巩固/紧急维护路径未接线死代码；`cortex.sleep()/emergency_activate` 因此在生产 tick 中从未被调用。
9. `agent_runtime.py:104`：`MetricsCollector` 实例化后无任何使用（engine 调用指标实际无人采集）。
10. `master_agent.py:879-891`：`_recall_and_record` 函数体为 `pass`（内部还引用不存在的 `self._memory_hub_ref`），Phase H "记录决策到用户记忆" 空实现。
11. `master_agent.py:1268-1269`：`_persist_learning` 尾部 `except Exception: pass` 全静默——学习结果持久化失败不可见（与全文件多处 `except Exception: pass` 同类：:451, :1308, :1346, :1356, :1364, :1373, :1392）。
12. `belief_system.py:109-112`：`_persist` 每次 add 全量扫 `hub.belief.get_all_active(limit=500)` 找同 statement —— O(N)/次且 >500 条后幂等去重失效，可能产生重复 Belief 行。
13. `belief_consolidation.py:66-77`：遍历 evidence_ids 后 `pass` 的死代码段（注释自认方案不可行）；`learning_trigger` 与 `master_agent._consolidate_episodes`、`memory_consolidator` 与 `memory_consolidation.ContextCompressor` 与 `context_compressor.py` 均为功能重叠的双实现，仅一套接生产。
14. `goal_store.py:163-166`：`_row_to_goal` 对 created_at/deadline 的 `datetime.fromisoformat` 无容错，脏数据直接抛 ValueError 中断 load_active（进而中断 boot 恢复链）。
15. `agent_runtime.py:1536/1063/1472/1724` 等多处 Episode/WM/快照写入失败仅 logger.debug —— 记忆"写丢失"在生产日志级别下静默。
16. `life_cycle_orchestrator.py:83-84`：`tick()` 裸 `except Exception: return TickResult.ERROR`，无日志——编排器任何异常零痕迹。

**P4（一般）**
17. `experience_store.py:61`：`id=f"exp-{len+1}"` 在淘汰最旧后重复；`knowledge_base.py:52` 同模式。
18. `episode_memory.py:45-47`：超容量仅置 archived 标记不删除元素，内存只增不减。
19. `goal_stack.py:74`：`pop()` 将任何层级目标一律置 COMPLETED，不区分失败/取消。
20. `attention.py:140`：`local_tick` 传 seconds=0.0 时 `or` 短路误用墙钟差；`tick`/`local_tick` 逻辑重复。
21. `identity_store.py:105`：`datetime.utcnow()`（Python 3.12 弃用）；`memory_consolidator.py:170`（本地时区 0-6 点）与 `memory_consolidation.py:316`（UTC 2-5 点）"低峰"定义不一致。
22. `wisdom_trigger.py:74`、`continuity_trigger.py:67`：直接访问 `hub._db_path` 私有属性，跨模块耦合。
23. `master_agent.py:2815`：`dispatch_distributed_task` 直接访问 `_distributed_manager._pending_tasks` 私有字段。
24. `agent_runtime.py:459`：对无 capacity 属性的 WorkingMemory 凭空 setattr；`master_agent.py:495/2891`：对 property 形式的 `current_focus` 以方法调用（对 Attention 实例会 TypeError，生产对象恰好也是 property → 同样 TypeError 风险，见 P1-2 关联）。

**P5（轻微）**
25. `decision_loop.py:77`：未注册引擎的结果 dict `{"success": False, "message": "not_registered"}` 与 EngineAdapter 返回结构字段不一致（缺 trace_id 等）。
26. `cortex_activator.py:59`：`__import__("time")` 反模式（retry_policy.py:96 同样 `__import__("logging")`）。
27. `agent/__init__.py` 导出清单与实际生产组件漂移（导出 Attention/AgentWorkingMemory/EpisodeMemory 等已非生产默认实现，易误导调用方）。
28. `master_agent.py:1711-1728`：`extract_knowledge` 与 `search_knowledge`（被遮蔽版）对未注入管理器返回结构不统一（dict{count:0} vs list[] vs {"error":...}），调用方需三态判断。


##### 审计分组 W2：capability 能力管理 + capability_reality 能力现实校验 风险清单（原文）

### P1（正确性/安全，主链路相关）
1. `ocos/capability/async_bridge.py:83` — `self.gateway.validate(contract, context)` 把 context 按位置传给 `caller` 形参；context 非 None 时 `caller.caller_id`（permission_gateway.py:213）抛 AttributeError。现象：任何携带 context 的 dispatch 直接崩溃。后果：该模块一旦接线即坏；当前无调用方故暂未爆发。
2. `ocos/capability/outcome_evaluation.py:128` 与 `ocos/capability/experience_memory.py:188-199` — reliability 查询键 `stats.get("count", 0)` 与 `get_stats` 返回键 `total` 不匹配，reliability 恒 0.5。后果：五维评估第 4 维失效，校准/学习闭环数据失真（result_understanding 主链路受影响）。
3. `ocos/capability/calibration_store.py:75-81` — 调用不存在的 `experience.update_reliability()`，异常被 `except Exception: logger.debug` 吞掉，仍返回 `applied=True`。后果：校准静默假成功，Phase 37 §3 闭环从未真正写库。
4. `ocos/capability_reality/adapter_fs.py:79` — `resolved.startswith(root)` 前缀沙盒可被同级目录名绕过（如 `/home/laogao/Documents-evil`）。后果：沙盒内读/写越权路径。
5. `ocos/capability_reality/adapter_shell.py:79` — `f"cd {workdir} && {command}"` 无引号包裹 + shell=True + 弱黑名单（113-119）。后果：含空格路径执行错乱；`rm -fr /`、`rm -r -f`、`\rm` 等变体绕过黑名单。该 adapter 已被 discovery 注册进主链路（execution/bridge、tool/manager）。

### P2（设计偏离/边界弱化）
6. `ocos/capability/result_understanding.py:299-326` — validated=False 的结果仍执行 learn() 写入 ExperienceMemory/KG，仅 errors 留痕；违背 CNS45-04"未验证不得进 Memory"。
7. `ocos/capability/agents/self_modification_agent.py:232-253` — 非 dry_run 且无高风险模式时无需任何人工确认即写文件（文档宣称"任何文件改动都需要人工确认"）；`_git_commit`(300-309) 执行 `git add .` 提交工作区全部改动，超出本次修改范围。
8. `ocos/capability/capability_router.py:66,71-81` + `adapter_manager.py:51-83` — 无适配器时 `_default_route` 与三个内置适配器均返回伪造 SUCCESS RawResult。后果：上层把模拟输出当真实执行结果。
9. `ocos/capability/cognitive_coupling.py:274-285` — 对 capability 版 HomeostasisManager 的 `context._metrics` 注入是无效操作（ContextMonitor 无 `_metrics`），认知熵从未真正进入健康报告。
10. `ocos/capability/permission_gateway.py:66-79,95-105` — 正则黑白名单可被简单混淆绕过；RESTRICTED 决策从不产生（死分支）；action 白名单不拦截（仅 debug 日志，permission_gateway.py:259-260）。
11. `ocos/capability/execution_bridge.py`（全文件）— docstring 宣称"超时控制"，实现无任何超时；capability_adapter.py:54 同样（超时依赖子类内部 subprocess）。

### P3（环境耦合/健壮性）
12. `ocos/capability/agent_proxy.py:84` — 硬编码 `project_root="/home/laogao/Documents/trae_projects/ocos"`。
13. `ocos/capability_reality/adapter_fs.py:32` / `adapter_shell.py:37` / `adapter_discovery.py:55-59` — 默认 safe_roots 硬编码 `/home/laogao/Documents` 个人目录。
14. `ocos/capability/lifecycle_manager.py:227-244` — `execute` 持 RLock 期间调用外部 exec_fn，长任务阻塞全部生命周期操作。
15. `ocos/capability/skill_registry.py:67` — 默认相对 db_path `"ocos/capability.db"` 依赖 cwd。
16. `ocos/capability/knowledge_graph.py:84` — `datetime.utcnow`（Python 3.12+ 弃用警告）。
17. `ocos/capability/agents/self_modification_agent.py:282-298` — 用 `stdout.count("passed"/"failed")` 统计测试结果，字符串污染即误判。

### P4（死代码/死接口）
18. `ocos/capability/capability_graph.py:40-42` — `children()` 入参设计与静态表不匹配（枚举值永远不是父键），实际不可用。
19. `ocos/capability/registry.py:138-148` — `list_providers(provider_type=...)` 形参被忽略，类型过滤失效。
20. `ocos/capability_reality/adapter_types.py:137-147` — AdapterConfig 的 max_retries/retry_delay/log_level/allow_unsafe_ops 无任何消费。
21. `ocos/capability/meta_controller.py:26` — `min_progress_required` 配置未使用。
22. `ocos/capability/async_bridge.py:154-178` — start_background 创建的后台 event loop 未被任何协程使用（装饰性）。
23. `ocos/capability/agent_proxy.py:204-205` — `old_instance` 死变量；注释与实现不符。

### P5（信息缺失/需上游澄清）
24. `ocos/capability/adapter.py`（175 行）【信息缺失】— 未被任何包外/测试文件 import，与 adapter_manager 的版本演进关系无文档；疑似早期遗留。
25. `ocos/capability/custom_agent_template.py` — AgentProvider ABC 无实现者；其与 AgentProvider 协议的符合性检查（manifest/health_check）无运行时验证点。
26. `ocos/capability/evidence_pipeline.py` 的 belief_system 接口（`add(statement=, confidence=)`）与 BeliefManager 实际签名是否一致【信息缺失：无调用方与测试可对照】。


##### 审计分组 W3：interaction 对外网关层（API/CLI/对话） 风险清单（原文）

**P1**
- R-P1-1 `api/server.py:88`：uvicorn `host="0.0.0.0"` 硬编码且**全站无认证/无鉴权中间件**；`/ocos/self-improve`（写自我知识提案）、`/ocos/approvals/{pid}/approve`（触发真实执行：写文件/跑命令的 DecisionBridge dispatch）、`/ocos/goals-from-chat`（直接写库建目标）全部暴露在局域网任意主机可达。后果：同网段攻击者可代行审批、注入目标驱动 agent 执行写操作。建议改 127.0.0.1 默认 + 环境变量覆盖 + 最小 token 鉴权。
- R-P1-2 `api/routes/converse.py` 全文件（11/15/16/18 端点）与 `chat.py`：**绕过 PermissionGuard/Constitution**——与 base.py 声明的"所有写操作必须通过 GoalRequest → Constitution 检查"架构约束冲突；approvals approve 虽经 DecisionBridge 沙盒，但 guard 语义在 API 数据面完全缺席。

**P2**
- R-P2-1 `api/routes/goal.py:49-70`：`POST /ocos/goal` 仅构造 UserGoal 内存对象，**不写 GoalStore**；GET /ocos/goal/{id} 永远返回 TBD。后果：外部系统经 API 建目标即丢失，白皮书若宣称该端点可用即虚假承诺。
- R-P2-2 `api/routes/chat.py:23`：`_CHAT_SESSIONS` dict 无淘汰/无上限，session_id 客户端可控；恶意循环 POST /ocos/chat 可撑爆进程内存（且持有 WritingIntent/decision 大对象）。repl 同理：`_recent_outbox` 有界（20）但 sessions 表无清理。
- R-P2-3 Phase 53 主动交互管线（need_monitor/attention_trigger/interaction_scheduler/interaction_validator，约 700 行）与 channel.py ExternalInteraction（378 行）**生产无调用者**，仅测试引用。后果：白皮书"主动交互/外部通道"能力实际未闭环（组件级单测通过 ≠ 系统能力）。
- R-P2-4 `cli/commands/growth.py:111-119`：`growth execute <proposal_id>` 忽略参数直接打印提示返回 0；`grow` 无 --execute-proposal 支持（growth.py:172 提示的选项 parser 未定义）。后果：用户按提示操作必然失败，闭环断裂。

**P3**
- R-P3-1 `converse.py:124,143`：敏感路径前缀与 safe_roots 硬编码 `/home/laogao`；`cli/commands/self.py:273` 项目根兜底硬编码 `/home/laogao/Documents/trae_projects/ocos`。后果：换用户/换机器即行为漂移或全拒绝。
- R-P3-2 `repl/shell.py:34`：REPL DB 路径 `os.environ.get("OCOS_DB_PATH", "ocos.db")` 未走 cli/paths.py 单一来源，任意 cwd 启动 REPL 读写 `./ocos.db`，与 CLI/daemon 数据分裂。
- R-P3-3 `converse.py:565-585 + 675-705` 与 `session_state.py:121-144`：daemon 链路中同一轮 assistant 回复存在**双写 episode**（SessionManager._persist_to_hub + ChatResponder._remember_conversation），对话记忆重复、recall 命中率被稀释。
- R-P3-4 `conversation_state.py:62-111`：update 为 SELECT→合并→INSERT ON CONFLICT 两步，无事务包裹；异常仅 logger.debug。跨进程（API + daemon）并发更新同 session 有丢更新风险。
- R-P3-5 `api/routes/quality.py:67-68,92-93`：`except Exception` → 500 且 detail 携带内部异常串，信息泄漏 + 掩盖栈。
- R-P3-6 `base.py:218`：PermissionGuard 用 `type("Decision",(),{"action":action})()` 空鸭子对象喂 constitution.check_decision——校验强度取决于 behavioral 实现对最小对象的处理，存在形式化放行风险【信息缺失：behavioral 内部逻辑未在本组范围核实】。
- R-P3-7 `repl/commands/plan.py:28-64`：REPL /plan 创建目标不落库（CLI 落 GoalStore+plan_dag），同命名入口行为不一致；repl/completer.py 整文件死代码。
- R-P3-8 `converse.py:1000-1045`：goal→结果关联依赖 updated_at 与 episode created_at ±120s 时间窗，脆弱；`_find_duplicate_goal` 用朴素子串包含判同义目标（"分析市场"与"分析市场趋势的区别"互判重复），可能误拒新目标。

**P4**
- R-P4-1 `cli/main.py:173-183`：`elif args.command == "run"` 重复死分支（第二支永不可达）；`cli/commands/self.py:195` cmd_self_preview 因 parser 未注册 preview 不可达；`api/models.py` BeliefQueryRequest/SelfStatusResponse 死模型；`repl/commands/memory.py` 帮助宣称 query 过滤但实现忽略参数。
- R-P4-2 `api/routes/memory.py/belief.py/trace.py` 与 `cli/commands/trace.py`、`repl/commands/trace.py`：对外暴露的 TBD 占位（OpenAPI schema 已发布空结果契约）。
- R-P4-3 `tui.py:1089`：app.run() 返回后调用 app.session_stats()，依赖 Textual App 对象生命周期，版本升级风险；`tui.py:563` token 估算 len//4 对中文偏差大（中文约 1.5-2 token/字）。
- R-P4-4 `interaction_scheduler.py:69`：candidate.id 用 `hash(candidate.title)`——Python hash 随机化，跨进程不稳定（当前仅内存使用，无实际危害）。
- R-P4-5 `channel.py:186-190`：WebhookChannel 非 2xx 时在 with 外读 resp.status（可用但风格差）；Webhook 无重试。
- R-P4-6 `cognitive_interface.py:157-172`：注入依赖 runtime 私有属性 `_event_ingestion` 与 event_bus.pending_events 列表直 append——跨模块契约靠约定，重构易静默失效（失败仅 debug 级日志）。

**P5**
- R-P5-1 `cli/paths.py` 与 `api/routes/converse.py` 跨子包 import（api→cli），层次方向混乱但功能正确。
- R-P5-2 `cli/commands/status.py`/`repl` 直写 SQL 计数（表名 episodes/belief/pattern/knowledge/plan_dag 硬编码），schema 变更漂移风险。
- R-P5-3 `converse.py:174`、`respond_auto` 内多处超长单行（含内联三元），可读性差；converse.py 累计 40+ 处 try/except-pass/debug，故障可观测性弱。
- R-P5-4 parser 帮助 "≥60 chars"（growth）与实现不符；`--max-chapters` 默认 40 与 Organ 端约定未校验。
- R-P5-5 `regulate` docstring 提及 `--mode auto|manual|off` 与 OCOS_SELF_REGULATION，但 parser 未定义 --mode 参数——文档先行实现滞后。


##### 审计分组 W4：runtime 认知运行时 + runtime_scheduler 调度器 风险清单（原文）
| 级别 | 位置 | 现象 | 后果 |
|---|---|---|---|
| P1-1 | ocos/runtime/recovery/recovery_manager.py:200（与 :124 重复定义） | `shutdown()` 在同类中定义两次，后者覆盖前者且缺少 `_save_ledger()` | 经 RecoveryManager.shutdown 关闭时执行账本不落盘 → 重启后 RUNNING/UNKNOWN 执行记录丢失，防重复执行保障失效 |
| P1-2 | ocos/runtime/resource_manager.py:289,405,440；ocos/runtime/adaptive_control.py:525 | 调用 `event_bus.emit(...)`，但 ocos/events.EventBus 与 ocos/event.EventBus 均无 emit 方法（分别只有 publish / push+ingest） | 一旦按 docstring 注入真实 EventBus，RESOURCE_EXHAUSTED/RELEASED/ADAPTATION_APPLIED 发射路径即 AttributeError：资源拒绝时崩溃、TTL 清理时崩溃 |
| P2-1 | ocos/runtime/runtime_kernel.py:59-69 + ocos/daemon/__init__.py:112 | daemon 每次 boot `RuntimeKernel()` 生成新 uuid runtime_id，CheckpointEngine.latest_checkpoint(runtime_id) 按前缀查找 | 旧式 checkpoint 永远无法命中，39.1 兼容恢复通道实际死路；仅 39.4 SnapshotStore.latest()（不按 runtime_id 过滤）能恢复 |
| P2-2 | ocos/runtime/runtime_kernel.py:113-130 | attempt_recovery 的 RestoreResult 中 active_goal_ids/attention_focus/pending_executions/pending_approvals 全部被丢弃 | 认知恢复只还原 tick 计数，目标/注意力/审批/执行恢复数据无人消费——"认知连续性"仅形式上存在 |
| P2-3 | ocos/runtime/pipeline.py:120-127 + runtime_kernel.tick_loop | PipelineError 不被 tick_loop 捕获 | 单个 stage（如注入的 memory_hub.get_stats）抛异常将终止整个心跳循环，daemon tick 线程持续报错且无 SAFE_MODE/DEGRADED 转换 |
| P2-4 | ocos/runtime/runtime_kernel.py:66-69（data_dir=checkpoint_dir=/tmp） | 恢复数据（snapshots/events/ledger/approvals）落在 /tmp/ocos_checkpoints | 系统重启后全部认知恢复数据丢失，持久化子系统形同虚设（生产部署必须覆盖该默认值） |
| P2-5 | ocos/runtime/stages/execution_check.py + daemon 装配 | 生产 TickPipeline() 无 task_dag 注入 → Stage ⑤ 空 → PermissionGateway 生产旁路；且 RuntimeKernel 构造的 CapabilityPolicyProvider 从未被调用 | 权限"免疫屏障"在当前生产路径上无任何请求经过，写操作审批（REQUIRE_APPROVAL）实际不生效 |
| P2-6 | ocos/runtime/scheduler.py:413-431 | PERIODIC 任务执行后立即重新入队，tick 不检查 next_run_at/interval_seconds | 周期任务退化为每 tick 执行，间隔配置无效；队列被周期任务淹没 |
| P2-7 | ocos/runtime_scheduler/worker_manager.py + task_scheduler.py:165-171 | WorkerManager 声称"Stage A 死循环不阻塞 Stage B"，但 TaskScheduler 未使用它，_drain_queue 同步串行 | 隔离承诺与实现不符；任一 stage fn 挂起即冻结整个调度循环（timeout_seconds 配置无处生效） |
| P3-1 | ocos/runtime/stages/learning_trigger.py:22-26 | learning_signals 恒为空 tuple | 学习触发链路在管线中永久静默，Experience→Pattern 固化只能依赖外部（daemon dream cycle） |
| P3-2 | ocos/runtime/stages/attention.py:47,60-63 | AttentionStage 自身持有 `_current_state`（跨 tick 状态） | 违反 TickStage "无状态 Stage" 协议；恢复时需手动 set_current_state，漏配则焦点历史丢失 |
| P3-3 | ocos/runtime/stages/execution_check.py:41-53 | REQUIRE_APPROVAL 与 DENY 均按 `decision.allowed` 过滤丢弃，不生成 PendingApproval | 需审批的候选任务被无声吞掉，无审计提示（trace 有记录但无人查） |
| P3-4 | ocos/runtime/runtime_state.py:34-40 + pipeline | DEGRADED/SAFE_MODE 无任何触发代码路径 | 宪法违规/恢复失败场景无法进入安全模式，生命周期状态机一半是死代码 |
| P3-5 | ocos/runtime/scheduler.py:380-402 | CONDITIONAL 调度项入队后 condition_fn_name 从未求值 | 条件任务会在下个 tick 被无条件执行（与 PERIODIC 同病），语义未实现 |
| P3-6 | ocos/runtime/runtime_loop.py:307-323,394-415 | async_run/_async_tick 直接调用同步 `runtime.tick()` | 异步模式阻塞事件循环；async_stop 不等待任何任务 |
| P3-7 | ocos/runtime/context_manager.py（全文件）、resource_manager.py | WorkingMemory 六个容器与 slot dict 无锁 | daemon tick 线程与 CLI/其他线程并发读写（add_goal/get_goals/update_goal_status）存在竞态，frozen replace 非原子 |
| P3-8 | ocos/runtime/policy_engine.py:128-169 | 规则匹配异常（TypeError/ValueError）一律返回"不触发" | 畸形 params 可绕过 constitution-protect / no-emergency-override 等保护规则（fail-open） |
| P3-9 | ocos/runtime_scheduler/backpressure.py:100-103 | `drain_deferred()` 返回 []（占位），推迟的 BACKPRESSURED 任务无恢复机制 | 背压解除后 MEDIUM 任务永久滞留状态标记（TaskScheduler 侧靠 schedule 未 mark_completed 下一 tick 重试兜底，但 submit 进来的任务丢失） |
| P3-10 | ocos/runtime_scheduler/task_scheduler.py:89-115 | run 循环在无任务且 max_ticks=0 时无 sleep（仅暂停态 0.001s） | 无限模式下 CPU 空转；生产未接线故暂无实害 |
| P3-11 | ocos/runtime/tick.py + recovery/runtime_snapshot.py | tick 上限 int 无持久化锁；文件名 `{tick:06d}` 零填充 | tick>999999 后 checkpoint 文件名排序错误（latest_checkpoint 倒序失真） |
| P4-1 | ocos/runtime/permission/permission_gateway.py:49-56 | `_trace_buffer` 仅入不出（flush_traces 需手动调用） | 长期运行内存无界增长 |
| P4-2 | ocos/runtime/runtime_kernel.py:222 | `object.__setattr__` 改写 frozen Tick.checkpoint_id | 破坏不可变性契约，哈希/replay 语义上 tick 与 checkpoint 绑定关系不真实（checkpoint_id 存的是 tick_id 字符串而非 checkpoint 文件标识） |
| P4-3 | ocos/runtime/checkpoint.py:84-113 | load/latest 吞掉所有解析异常返回 None | checkpoint 损坏无任何日志告警，排障困难 |
| P4-4 | ocos/runtime/permission/builtin_policies.py:36-53 | REGISTERED_CAPABILITIES 缺 OPERATION_LEVELS 中的 api.get/web.post/database.update/process.start | 这 4 个合法操作被 default_deny 拒绝，注册表漂移 |
| P4-5 | ocos/runtime/decision_runtime.py:354、execution_runtime.py:292、process_runtime.py:274 | reset() 直接清 WorkingMemory 私有容器 `self._wm._decisions/_executions/_processes` | 越封装访问；WorkingMemory.clear() 语义不同（会连 goals 一起清），引擎 reset 互相影响 |
| P4-6 | ocos/runtime/attention_engine.py:258-260 | FrequencyAnalyzer 用内置 `hash(str(content))` | PYTHONHASHSEED 随机化下跨进程不稳定；缓存 `_observation_cache` 无淘汰 |
| P4-7 | ocos/runtime/adaptive_control.py:122-127 vs permission/permission_request.py:22-26 | 两个同名 `RiskLevel` 枚举（LOW/NORMAL/HIGH/CRITICAL vs LOW/MEDIUM/HIGH） | 集成时极易错用，值域不同 |
| P4-8 | ocos/runtime/policy_engine.py:418 | evaluate 以 info 级打印完整 params | 高频调用下日志洪泛，且 params 可能含敏感内容 |
| P4-9 | ocos/runtime_scheduler/task_scheduler.py:243-256 | set_state 不恢复 start_tick、stats.status/skipped_ticks | 恢复后 elapsed/健康统计失真 |
| P4-10 | ocos/runtime/tick_context.py:58-74 | to_dict 只输出 count 摘要 | Tick Replay 只能还原"发生了多少"，无法还原"发生了什么"——与"为 Tick Replay 保留完整状态快照"的注释目标不符 |
| P5-1 | ocos/runtime/pipeline.py:89-94 | register_stage 可覆盖冻结 stage | "不可变流水线"仅靠约定，无治理校验 |
| P5-2 | ocos/runtime/goal_runtime.py:212-235 与 context_manager.py:369-390 | 两处都订阅 GOAL_SET 并各自构造/更新 Goal（一个 CREATED→ACTIVE，一个直接 active） | 双重订阅冗余；两处 Goal 构造参数不一致（priority 默认值 1 vs 0），若事件乱序可能出现状态抖动 |
| P5-3 | ocos/runtime/adaptive_control.py:288-372 | auto_adapt 依赖 `resource_manager.get_usage()` 返回的 ResourceUsage.available/total 推算使用率 | ResourceManager 生产未接线 → auto_adapt 信号源为空，B5/B6 联动仅在测试中成立 |
| P5-4 | ocos/runtime/recovery/integrity_verifier.py:73-79 | verify(strict) 的 strict 参数未在检查内使用 | strict 语义完全由上层 CognitiveStateRestore 承担，参数易误导调用方 |


##### 审计分组 W5：engines 认知引擎 + decision 决策 + planning 规划 + cognitive_loop 认知循环 风险清单（原文）

**P1**（无：本分组未发现可直接导致数据损坏/安全越权的高危缺陷；P2-02/P3-02 为最接近项）

**P2**
- **P2-01** `ocos/engines/consolidation_engine.py:116-118`：目标层级自动推断用 `lvl.value > current_max.value` 对 KnowledgeLevel 的**字符串值做字典序比较**（knowledge/store/ontology.py:21-27，值 observation/evidence/pattern/principle/policy）。字典序 evidence<observation，"memory"(EVIDENCE) 源永远推不高 max；"principle" 字典序 > "policy" 导致 POLICY 路径层级判断错乱。后果：consolidate 的 target_level 推断错误，可能把低层信息合并成高层候选或反之。知识本体已提供 `get_level_index` 却未使用。同文件 `_infer_source_level` 在 promotion_engine.py:118 的 else 分支还被重复赋值（死代码）。
- **P2-02** `ocos/engines/writer_engine.py:142-155 + 469-470 + 537-566`：`_init_opentale` 只做 `import opentale` 探测并置 `_opentale_available=True`，**从不实例化 `self._opentale_system`**（恒为 None）。一旦环境装了 opentale，`_do_generate` 走 `_delegate_to_opentale` → `None.generate(...)` → AttributeError → 被 except 捕获返回 success=False。后果：opentale 可用反而使 generate 永远失败（三层降级的最高层是坏的）。
- **P2-03** `ocos/cognitive_loop/loop_orchestrator.py:68-147`：tick() 全链无 try/except。注入的 ContextSynchronizer provider、decision 组件、step 中任何回调抛异常将中止整个循环且无 HEALTH_ALERT/ERROR_RECOVERED 记录（TickOutcome 定义了 ERROR_RECOVERED 却无任何产生路径）。后果：备用循环对脏 provider 零容错；AutonomousLoop 长跑时一个坏 tick 即崩。

**P3**
- **P3-01** `ocos/engines/text_generator.py:517-538 + 481-502`：`_auto_provider` 无条件读取 `~/.ocos/config.json`；当用户机器配置了 `llm_fallback` 段时 `provider.name` 变为 `failover(openai->openai)`，实测导致 `test_text_generator.py::test_auto_provider_openai_when_key_set` 失败（1 failed，本分组唯一红灯）。测试未隔离全局配置文件——用户环境泄漏进测试结果。
- **P3-02** `ocos/engines/policy_engine.py:272-306`：规则条件解析对未知运算符 `passed=True`（fail-open 放行），条件格式不合法（parts<3）也放行并注明 "No evaluable condition"。后果：写错的 DENY 策略会静默放行，与策略引擎"守门"职责相反；缺失维度时 context.get(dim, 0) 又是 fail-closed——同一函数内两种相反失败语义。
- **P3-03** `ocos/cognitive_loop/perception_bridge.py:69-92`：attention 每 tick 只标记焦点事件 processed，其余 pending 事件永久滞留；`flush_processed` 的过滤条件 `not e.processed or e.tick_id > max_age_ticks` 恰好**保留所有未处理事件**。后果：长跑（备用循环 + AutonomousLoop）时 `_events` 无界增长（内存泄漏）。
- **P3-04** `ocos/decision/option_generator.py:46-55 + decision_pipeline`：defer 基线选项 confidence=1.0/risk=0，value-risk 得分恒压过 wisdom/investigate 选项（约 0.695 vs 0.26）。后果：认知循环决策阶段几乎永远产出"推迟"提案，备用链路实际不产生行动倾向——若未来升级为 fallback，将系统性偏向不作为。
- **P3-05** `ocos/engines/decision_making_engine.py:155-166`（同模式见 planning/reasoning/policy）：决策无论成败只发射 `INFORMATION_TRANSFORMATION_STARTED`，**从不发射 COMPLETED/FAILED** 对应事件（learning/reflection/prediction/simulation 则成对发射）。后果：依赖事件成对性的消费者（如过程追踪）对 DECISION/PLANNING/REASONING/POLICY 流程会看到永久"进行中"。

**P4**
- **P4-01** `ocos/engines/decision_making_engine.py:265-274`：MAJORITY、OPPORTUNITY_COST、PARETO 三策略实现与 SCORING 完全相同（max total_score），与名称语义不符；RANKING 分支中 `selected = sorted_opts[0]` 引用的是排序前对象，后续按 label 回填 is_selected 时若存在**同名 label** 选项会标错行（label 非唯一假设未校验）。
- **P4-02** `ocos/engines/simulation_engine.py:115-134`：`run_monte_carlo` 文档称"每次微调参数"，实际只替换 scenario_id，`parameters` 原样 deepcopy——多次运行结果完全相同（除非 step_fn 自身随机），蒙特卡洛统计无意义。
- **P4-03** `ocos/engines/text_generator.py:264-271`：`OpenaiProvider.generate` 通过 pop 全部 `*proxy*` 环境变量再 finally 恢复——并发 async 调用下存在竞态（另一协程在此窗口读到被清除的代理配置）。
- **P4-04** `ocos/engines/address_resolver.py:93-104`：`route_query` 把 `Query` 传给签名声明为 `Callable[[UniversalAddress], Any]` 的 resolver（`# type: ignore` 压制）。若调用方注册的是地址型 resolver，Query 会被当作 UniversalAddress 使用（Query 无 namespace 属性会 AttributeError，但若鸭子兼容则静默错路由）；RetrievalEngine 只捕获 TypeError，其他异常直接外溢。
- **P4-05** `ocos/engines/writer_engine.py:495-503`：`_do_generate` 在同步 execute 内使用 `asyncio.run(...)`；若上层已在事件循环中调用（如 async 框架宿主），`asyncio.run` 抛 "cannot be called from a running event loop"，被 except 捕获后降级到模板文本——功能静默降质而非报错。
- **P4-06** `ocos/engines/learning_engine.py:85 / prediction_engine.py:86 / reflection_engine.py:84`：注入函数异常不捕获——与同组其他引擎行为不一致，且失败时 STARTED 事件已发、无 FAILED 事件。
- **P4-07** `ocos/decision/decision_types.py:204-215`：`DecisionProposal.recommended` 依赖 option 自带的 risk_score/value_score 静态默认值，而管道实际排序用 RiskEngine/ValueModel 计算值且不回写（frozen）——`recommended` 与 pipeline 选出的 best 可能不同，两处"最佳选项"语义分裂。
- **P4-08** `ocos/planning/simulator.py:111-117`：PARALLEL 分支 `max(...)` 对空 DAG（tasks 为空但无环）抛 ValueError；simulator 也不像 plan_validator 那样先做空图检查。
- **P4-09** `ocos/engines/forgetting_engine.py:81-96`：`is_expired` 只认 VALIDATED 状态——DEPRECATED/ARCHIVED 信息永远不会被 collect_expired 回收；且遗忘只发状态事件，无任何实际删除路径（依赖未验证的下游消费者）【信息缺失：确认消费 INFORMATION_STATUS_CHANGED 的清理方是否存在于本审计分组之外】。

**P5**
- **P5-01** `ocos/engines/promotion_engine.py:117-118`：else 分支 `source = _infer_source_level(...)` 与上方赋值完全重复（死代码）。
- **P5-02** `ocos/engines/planning_engine.py:247`：`depends_on=tuple(steps[j].step_id for j in range(i) if j < i)` 中 `if j < i` 恒真（range(i) 已保证），冗余条件暗示作者意图可能只是相邻依赖。
- **P5-03** `ocos/cognitive_loop/decision_pipeline.py:60-62`：`_tracer.record(..., discarded=[], ...)` 恒传空列表——DecisionTrace 的 discarded_options（淘汰理由）机制形同虚设。
- **P5-04** `ocos/planning/plan_validator.py:146-150`：空 DAG 用 `add_warning("DAG-01",...)` 随后手动 `report.valid=False`——severity 语义（WARNING 可执行）被破坏，应使用 add_error。
- **P5-05** `ocos/cognitive_loop/decision_pipeline.py:74`：`builder.set_self_context("agent current state")` 硬编码占位——Self Model 快照未真实接入，决策上下文的自我信息为常量。
- **P5-06** `ocos/cognitive_loop/learning_coordinator.py:78-85`：`_validate_bounds` 将禁词与输入都 lower/下划线转空格后匹配，但禁词表含中文条目 "我决定改变自己的核心"——中文无下划线差异、大小写无意义，匹配逻辑对中文条目等价于原样 substring 匹配（碰巧仍可工作），但若未来禁词含混合格式（如 "delete self_model"）归一化后才可命中；当前实现对 `_identity_boundary`/`_constitution_ref` 两个字段从未读取使用（死字段）。
- **P5-07** `ocos/cognitive_loop/loop_orchestrator.py:117-127`：HEALTH_ALERT 分支把 ctx append 后 return，跳过正常 outcome 判定与 `_outcomes` 对齐逻辑——`_contexts` 与 `_outcomes` 在告警 tick 上错位（contexts 多一条无 outcome 的记录）。
- **P5-08** 代码重复：`RuntimeResult` 在 8 个引擎文件中各自定义（字段略异）；SemanticRole→KnowledgeLevel 的 `_ROLE_TO_LEVEL` 映射在 consolidation_engine.py:44-52 与 promotion_engine.py:33-41 完全重复两份。
- **P5-09** `ocos/engines/goal_arbitration_engine.py:66 等`：每个 `ArbitrationResult.candidate_id` 均为当场随机 uuid4，trace 无法跨运行比对（可复现性缺失）。
- **P5-10** `ocos/cognitive_loop/loop_orchestrator.py:121,187`：`loop_summary()`/health check 直接访问 `self.learning._experience_log` 私有字段，破坏封装。


##### 审计分组 W6：memory 记忆 + personal_memory 个人记忆 + event_memory 事件记忆 + knowledge 知识图谱 风险清单（原文）

**P1**
- 无 P1 级（无数据损坏/崩溃级缺陷；P1-1 时间纪律违例最接近）。
- event_memory/event_store.py:100（`_time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime(...))`）+ :119-125（`time.mktime(strptime(...))` 恢复）：事件时间戳以本地时区无亚秒精度写库，恢复后 timestamp 漂移（夏令时/换机时区 → 时间线整体偏移）且亚秒事件排序丢失；若 created_at 为表默认 datetime('now') 格式（空格分隔）则解析失败 ts=0.0，再经 EventValidator 判 "invalid timestamp"。后果：EM54-02 时间线重建保证被削弱。附：event_archive.py:166 WARM 阈值 360 秒硬编码，未用 config。

**P2**
- memory/recall.py:176-181：`_recall_experience` 依赖 `self._hub.experience`，但 hub.py:35-41 只有 episode/belief/semantic/pattern 四属性，无 experience Store。后果：所有经 MemoryHub 的对话 experience 召回恒为空且无任何报错（静默功能缺失）。实测 recall 只返回 semantic/pattern/user 源。
- memory/recall.py:129-130、209-210：`except Exception: pass` 静默吞异常（语义召回内层循环、用户画像召回）；:144-146、167-169、191-193 降级为 logging.debug。后果：召回链路故障不可观测。
- memory/belief/__init__.py:32-65 与 memory/belief/models.py:66-198：同名 `Belief` 两个不兼容定义并存（前者字段 statement/confidence/source/metadata 且经宪法校验，后者 frozen 十字段）。`from ocos.memory.belief import Belief` 与 `from ocos.memory.belief.models import Belief` 类型互不兼容，store 存取只兼容后者。后果：混用路径会 AttributeError/静默行为分叉。
- event_memory/event_store.py:136-145：`mark_archived` 只改 `_headers[id].lifecycle`，`_by_id`/`_events` 中事件本体不变；而 event_archive.py:140-174 `apply_lifecycle` 反向直接替换 `_events`/`_by_id`（不改 header 之外的索引一致性）。后果：两条生命周期路径状态互不相同，headers() 与 find() 结果矛盾。
- event_memory/event_query.py:78-94：索引命中分支（单 event_types + entity/goal）回表后只做时间过滤，**不应用 params.sources 过滤与多类型过滤**（后过滤只在 fallback 分支 :73-76）。后果：带 sources 条件的查询在索引命中时返回超集（多报不漏报），且 EventQuery.confidence_min/lifecycle/context_has_key（event_types.py:192-194）三参数在任何路径都不生效。
- personal_memory/wisdom_store.py:64-93：`_persist_item` 对已存在行只 UPDATE state 列；`INSERT OR IGNORE` 之后追加的证据（如 inject_counter_evidence、validator 注入的 additional_evidence）不落盘。后果：跨 session 恢复（load_from_db）后证据链缺失 → 反例比/置信度与库内不符，可能错误地重新验证通过。字段不落库实锤。
- knowledge/knowledge_abi.py:215-254 + process/promotion_rules.py:183：elevate 默认策略 `allowed_sources=["governance","pattern_detector","manual"]`，而 AccessMatrix.set_default_permissions 对所有 owner 授予低两层 can_elevate=True。实测 owner="testmod"（矩阵已授权）被策略拒绝。后果：除三个魔法名外的所有模块无法提升知识，两套权限体系互相矛盾、无文档说明。
- knowledge/process/evolution.py:320-359：`_apply_edit` 成功后调 `self._lifecycle.change_status(unit_id, old_unit.status, ...)`（同状态转换被 can_transition 拒绝），返回值被丢弃、仍返回 True。后果：EDIT 的审计记录永不产生；且 :333-339 重建 KnowledgeUnit 未带 source/timestamp → source 字段在 EDIT 后清空（镜像 _to_entry 的 source_patterns 变 `('',)`），字段不落库。
- memory/experience/builder.py:69-81：用 `object.__setattr__` 修改 frozen ExperienceCandidate 的 rejection_reason（数据可变性破坏）；且 Boundary 违规（validator 扫出的 self 污染）只记录不阻断，experience 仍为 COMPLETE、可继续过 Significance Gate 入库——"三重门控"中的 Boundary 门实际不拦截。

**P3**
- memory/semantic/store.py:195-209、memory/belief/store.py:178-185：query_by_lineage 用 `source_patterns LIKE %id%` / `source_knowledge_ids LIKE %id%`，ID 互为前缀时误匹配（KNW-20260905-XXXX 共享日期前缀，碰撞面大）。建议 json_each 精确匹配（episodes.query_by_tag 已有先例）。
- memory/pattern/store.py:166-180：`_row_to_pattern` 不回读 validated_at/validation_notes——Pattern 存储后读回退化为 PatternCandidate，验证元数据只在库中（字段不回读）。
- memory/user/model.py:173-188：`update_profile` 的 elif 分支（preferences/interests/relationships 合并语义）为死代码——这些名字是 dataclass 字段，hasattr 恒 True 走 setattr 整体替换。调用方以"merge"语义传 dict 会丢旧键。另 ：86 version 恒写 1。
- knowledge/process/validator.py:150-151：`check_elevation_chain` 调 `registry.get(parent_id, requestor="*", scope_filter="*")`，KnowledgeRegistry.get 无 scope_filter 参数 → 注册该规则后必 TypeError（被 :255-266 规则级 try/except 转成 ERROR 结果，不崩但该规则永不可用）。
- memory/significance/rules.py:73-98：goal_impact 评分里 `goal_keywords` 命中仅追加 evidence 无分数（:87-89 死代码路径），关键词命中只得 0.3 分的注释分支不存在——注释与实现不符。
- memory/recall.py:117-121：context 关键词直接当 domain 查 `query_by_domain(keyword)`，领域名命中率近乎 0，语义召回实际主要靠 :133-141 高置信度兜底 + bi-gram 过滤，召回质量受限于 keyword→domain 词表缺失。
- knowledge/graph.py:159-166：remove_entity 不清理 _relations 中悬挂关系、不清 _by_name 名称索引、不清理 Fact；graph.py:264-286 export_json 不含 facts 且无对应导入方法。
- memory/experience/models.py:55、86、103：TraceBundle/ExperienceCandidate 用 naive `datetime.now()`（本地时间），与全包 timezone.utc ISO 纪律不一致；序列化落库（lessons→Episode.created_at 除外）时时间语义含混。
- personal_memory/pattern_interpreter.py:188-198：`_infer_scope` 标签 >3 个时返回空 WisdomScope → `is_universal=True` 全域适用，与 PM41"防止局部规律变全局原则"目标相悖。

**P4**
- memory/hub.py:107-116：get_stats 缺 semantic/belief 各状态计数口径不完整（belief 只取 active）。
- memory/__init__.py:3：包 __init__ 自引用 import（ocos.memory.recall 内部又 from ocos.memory.recall import），循环写法可运行但不规范。
- event_memory/event_types.py:192-194：EventQuery 三个死参数（见 P2-5）。
- event_memory/event_lifecycle.py:35：`from ocos.event_memory.event_query import EventQueryParams` 实为 event_query.py:13-14 的导入别名（EventQuery as EventQueryParams），间接脆弱；:102 `result.code == "fail"` 依赖 str-Enum 比较。
- event_memory/event_store.py:217-235：snapshot 将 payload 转成 str、丢失 caused_by/links_to/metadata/archived_at；:237-254 restore 无法还原因果链。
- knowledge/store/lifecycle.py:54-56、255：类型注解 `list[callable[[...], None]]` 用内建 callable（非 typing.Callable），靠 `from __future__ import annotations` 才未在运行时报错。
- knowledge/store/lifecycle.py:199-214：get_version_history 对每条审计记录 append 1，实际只可能返回 [1, current_version]，与真实版本轨迹不符。
- knowledge/synthesis_manager.py:217-224：update_confidence 只升不降（max 语义）；:353-383 deductive/inductive/abductive 综合为模板文案（"基于共同主题「X」的综合洞察"），非真实推理；conflict 检测仅看置信度极差 >0.5。
- memory/pattern/extractor.py:146-156：_normalize_condition 仅 strip+截断，不做语义归一化（注释宣称"归一化"），大小写/标点不同的同条件无法聚合。
- memory/episode/store.py:66-69：save 幂等按 experience_id 去重但 lesson 的 experience_id="LESSON-{id}" 每次合成新 id，重复综合同一批经验会重复入库 lesson。
- ocos/storage/schema.py:274-283 与 agent/wisdom_trigger.py:81-91：wisdom_items 建表 DDL 双份维护（内容当前一致），漂移风险。

**P5**（风格/可维护性）
- ocos/memory/belief/store.py:30-43 等：DDL 常量置于文件中部/底部，各 Store 风格不一。
- memory/pattern/models.py:128：`Pattern.summary` 用 `split(": ", 1)[1]` 解析自己父类 summary 文本再拼接，脆弱。
- ocos/knowledge/process/evolution.py:383、448、501：函数体内多处 `import uuid`（应顶部导入）。
- event_memory/event_archive.py:151-173：apply_lifecycle 直接读写 store._events/_by_id 私有字段（三处列表重建 O(n) 复制），破坏 EventStore 封装。
- memory/recall.py:26：`metadata: dict = None  # type: ignore` 的 dataclass 默认值写法。


##### 审计分组 W7：world_model 世界模型 + digital_world 数字世界 + opentale_bridge + platform 风险清单（原文）

**P1**
- R1 `ocos/world_model/world_validator.py:118` — `if existing and existing.entity_type != existing.entity_type:` 同一属性自比较恒为 False。现象：实体 ID 相同但类型不同的观察永不判定 CONFLICT。后果：WM42-04 一致性检查完全失效，外部观察可用相同 entity_id 携带错误 entity_type 污染世界模型。实测：validate_against_model 返回 ACCEPT。
- R2 `ocos/platform/plugin_sandbox.py:316-331` — `execute()` 中 `blocker = slot.blocker` 创建后**从未 `sys.meta_path.insert` 安装**，finally 中却执行 `sys.meta_path.remove(blocker)`。现象：import 白名单 hook 全程未生效。后果：插件在沙箱内可 import 任意模块（os/subprocess/socket 等），D2 沙箱的 import 隔离为虚假安全边界。实测：execute 前后 sys.meta_path 中 _ImportBlocker 数量均为 0。缓解因素：插件代码本身经 importlib 由宿主进程加载，hook 设计上也无法拦截宿主已加载模块。
- R3 `ocos/digital_world/sandbox.py:67-74` — "沙箱"实为 `subprocess.run(command, shell=True)` + 命令黑名单。现象：黑名单可被 `$(echo cm0...)`、base64、别名、路径变体等绕过；"禁止网络"仅靠过滤 wget/curl 字符串。后果：审批型 sandbox_exec 在 OCOS_DW_DRY_RUN=0 时等同任意 shell 执行（受审批门约束是唯一防线）。

**P2**
- R4 `ocos/opentale_bridge/bridge_session.py:338` — `base = previous_output or self.session.translation_result or {}`：BridgeSession 无 translation_result 字段（正确名是 translation）。现象：previous_output 为 None 时抛 AttributeError。后果：run_full_cycle_with_repair 中若首次写入即无输出，修复循环崩溃；当前主路径因 attempt0 先赋 best_output 而未触发（实测确认 AttributeError 复现）。同文件 L417-419 apply_contract_adjustment 的落盘代码被注释禁用，契约调整仅内存模拟。
- R5 `ocos/platform/plugin_sandbox.py:376-391` — 超时处理仅 `future.cancel()`（对已运行线程无效）并返回 killed=True，插件线程继续执行且可能泄漏；`_get_pool`（L356-366）只在池首次创建时把 `_threads` 设为 daemon，池复用后新起 worker 非 daemon。后果：超时插件变成不可控后台任务，与"强制超时终止"承诺不符。
- R6 `ocos/platform/audit_rule_engine.py:141,236-237` — Rule2（权限一致性）依赖 `details["governance_audit_id"]`、Rule5（应急恢复）依赖 `details["related_halt_audit_id"]`，但 audit_engine 的所有事件回调（_on_governance_event/_on_system_event）从不写入这些字段。后果：两条 error 级默认规则对自动收集的记录永不触发，合规报告 compliant 恒易达成（假阴性）。
- R7 `ocos/opentale_bridge/self_regulation.py:179` — 硬编码绝对路径 `/home/laogao/Documents/trae_projects/opentale/projects`。后果：换环境后调整记录静默落到 `~/.ocos/adjustments/`（行为分叉且 L207 `except: pass` 吞掉所有错误，无日志）。
- R8 `ocos/digital_world/file_ops.py:28-34` — PROTECTED_PATHS 用 `abs_path.startswith(protected_abs)`，`/boot` 会匹配 `/bootxyz`；且 file_read 不做保护检查。后果：保护面既误伤又漏护（可读 /etc/shadow —— 在 /etc/passwd 前缀外）。

**P3**
- R9 `ocos/world_model/world_store.py:97-105` — 添加 claimed_relation 前不校验 from/to 实体存在性，产生悬空关系且无事件告警；`_upsert_from_obs` 对已存在实体忽略观察中的 entity_type 更新。
- R10 `ocos/world_model/causality_engine.py` 全文件 — WorldStore 未提供任何 add CausalityLink 的公开路径，因果层在生产数据流中永远为空（仅测试可直接构造）。
- R11 `ocos/platform/audit_engine.py:342-374` — `record()` 对 record_type 无类型容错（实测传 str 抛 AttributeError），与 query_audit_trail 接受 str 的风格不一致。
- R12 `ocos/platform/plugin_loader.py:272` — 直接访问 `sandbox._plugins` 私有 dict 注入 plugin_instance，绕过 Sandbox 封装。
- R13 `ocos/opentale_bridge/master_agent.py:247-248` — 双重 `@staticmethod` 叠加（Python 3.10+ 才合法），旧解释器将 TypeError；L346 `_collect_cognition_context` 已被 decide 内联实现取代，属遗留死代码。
- R14 `ocos/opentale_bridge/ocos_memory.py:221-224` — decision_history.jsonl 多进程 append 无文件锁（activation 有 _LOCK 但 memory 没有），并发 CLI 可能交错写坏 JSONL。
- R15 `ocos/digital_world/api_ops.py:30`、`git_ops.py:25`、`search_ops.py:20`、`sandbox.py:22` — `_DRY_RUN` 在 import 时求值固化，运行中改环境变量不生效；且各模块各自读取，状态可能不一致。
- R16 `ocos/opentale_bridge/quality_analyzer.py:762` — 中文角色名姓氏表硬编码（仅 20 个姓氏），提取不到的角色不参与一致性分析，评分偏乐观。

**P4**
- R17 `ocos/world_model/world_validator.py` — REJECT/QUARANTINE 决策、min_sources、LOW_CONFIDENCE/SINGLE_SOURCE/INCONSISTENT 三个 issue 均为声明未用；QUARANTINE 语义无落地存储。
- R18 `ocos/digital_world/db_ops.py` 全文件占位；`web_feeder.py` 全部为硬编码 2026 假数据（含编造的统计数字），若被误当真实市场数据进入决策有污染风险。
- R19 `ocos/platform/audit_report.py:49-67` — build_debug_report 在 for 循环体内重复调用 `query_traces`（每条记录一次），N 条记录 O(N) 次重复查询。
- R20 `ocos/platform/plugin_sandbox.py:69` — 白名单含 `pathlib._path`（以 pathlib. 前缀匹配实为放行整个 pathlib），注释声称"禁止文件系统写入"与实际不符（pathlib 可读写文件）。

**P5（文档/一致性小问题）**
- R21 `ocos/platform/trace_engine.py:1-15` docstring 称"4 类 Trace"，实际 7 类；`ocos/world_model/world_store.py` 注释"不暴露直接写入 API"与 entities/relations/states 等子组件全部公开可变（外部可直接绕过 validator 写 `ws.entities._entities`）矛盾。
- R22 `ocos/platform/audit_engine.py:58-59` `__all__` 中 "AuditEngine" 重复两次。


##### 审计分组 W8：perception 感知 + attention 注意力 + evolution 演化 + learning 学习 + growth 成长 + reflection 反思 + cognitive_nutrition 认知营养 + cognitive_continuity 认知连续性 风险清单（原文）

**P1**：无。（8 个模块均无崩溃级/数据损毁级缺陷；growth 有多重护栏且变异受边界约束。）

**P2**
1. `ocos/attention/focus.py:131-139` — `process_observation` 调 `self._update_focus(focus_type=..., focus_target=..., attention_scores=...)`，但 `_update_focus` 形参为 `(focus_type, target, score, ...)`：关键字名错误（focus_target≠target）且缺必需实参 score。**实测复现**：任何 composite≥0.3 的观察进入即抛 `TypeError: _update_focus() got an unexpected keyword argument 'focus_target'`。后果：AttentionFocus 的主入口在真实观察流下必然异常（调用方若不捕获将打断认知环）。单测未覆盖该分支故未被发现。
2. `ocos/evolution/migration_engine.py:103-121` — `_execute` 为模拟桩，仅按 change_type 校验后返回 success=True，**不执行任何真实变更**。后果：Phase 47 "进化已生效(ACTIVE)" 的语义是虚构的，上层若据此宣称系统已改进即为虚假状态；与 growth 模块（真实变异）形成能力断层。

**P3**
1. `ocos/perception/perception_engine.py:91-93` — tick 中传感器异常 `except Exception: continue`，无任何日志或 health 更新（health 更新在各传感器内部，但非 poll 抛错路径）。后果：传感器系统性故障静默丢失，感知面"变盲"不可观测，违背 PS52-02 的可诊断精神。
2. `ocos/daemon/factory.py:218-245` — 生产装配 PerceptionPipeline 未注入 semantic_extractor 与 validator（保持 None），__init__ docstring 宣称的 Sensor→Extractor→Validator→EventBus 链在生产上退化为"置信度兜底 + 直接桥接世界模型"；SemanticExtractor/PerceptionValidator 仅有测试消费。
3. `ocos/evolution/manager.py:166-184` — analyze_proposal 越权调用 `self._proposer._build_initial_impact`（私有）并用 `type('Signal',(),{...})` 伪造信号对象，且返回的 impact **未写回 proposal.impact**。后果：影响分析结果对后续审批/沙箱不可见，CE47-04 守卫链在此路径形同虚设。
4. `ocos/evolution/manager.py:250-253,275-299` — 回滚快照内容是提案描述字符串（`_get_current_state`），rollback 仅弹出内存键并改状态标记；RollbackEngine（有 dict 快照能力）未被 manager 使用。后果：CE47-03 "可回滚"保障在总管路径上不成立（仅记账级）。
5. `ocos/cognitive_nutrition/digestion_monitor.py:51-53,161-183` — 未传实测快照时 memory/knowledge 增量使用每餐型固定估算值，decision_quality 默认恒 1.0，identity_hash 默认恒定。后果：协议默认运行的"消化判定"由输入假设决定而非系统观测，结论不具备对真实 OCOS 的证明力。
6. `ocos/perception/sensor_types.py:127` — Observation.id 默认 `obs-{time.time()}`，同秒多次创建即重复 id；text_sensor 用自有计数器规避，但 ObservationBuilder/多模态传感器均用默认值。后果：下游以 id 去重/审计时可能碰撞。

**P4**
1. `ocos/perception/semantic_extractor.py:108` — 实体提取正则 `r'["""]([^"»"]+)["\u201d"]'` 字符类混入全角引号与 `»`，疑似编码损坏；中文引号实体提取行为不可靠。
2. `ocos/perception/semantic_extractor.py:63,130` — urgent 词表含 `"asep"`（疑为 "asap" 拼写错误），永久无效匹配。
3. `ocos/perception/perception_validator.py:44-45` — `_seen` 去重表只增不清（dedup 窗口判定后才可覆盖同键，不同键永久累积），长运行内存缓涨。
4. `ocos/perception/text_sensor.py:45` — `_buffer` 无容量上限，生产者快于 poll 时无界增长。
5. `ocos/attention/attention_types.py:66-70` — `focus_duration` 属性无中断时恒为 0，与 scoring.py:161 的 `current_tick - start_tick` 计算不一致（属性当前无人消费，属潜伏不一致）。
6. `ocos/attention/attention_types.py:154` — `max_interruptions_per_minute=5` 定义但全仓无实现（限流承诺未兑现）。
7. `ocos/attention/scoring.py:55-63` — `switch_cost` 权重声明参与公式但 score() 从未减去（死参数）。
8. `ocos/attention/retrieval.py:56,102` — 检索缓存按关键词集合为键，无 TTL 无条目上限；记忆更新后返回陈旧结果。
9. `ocos/evolution/approval_engine.py:77-78` — `_auto_eligible` 的 FORBIDDEN 分支不可达：EvolutionDomain 枚举不含任何禁止域值，`domain in FORBIDDEN_DOMAINS` 恒 False（防线依赖上游 _map_domain 降级，属纵深冗余失效）。
10. `ocos/evolution/impact_analyzer.py:95-101` — `_check_dependencies` 空实现且 import DetectedSignal 未用。
11. `ocos/evolution/manager.py:355-372` — `tick()` 的 auto_approve 自动检测分支为 `pass` 桩，"自动化"承诺未实现。
12. `ocos/learning/manager.py:269-275` — 反馈极性用英文子串匹配，`"no"` 命中 "know/not"、"bad" 等误报面大；中文反馈全部落入 CORRECTION 兜底。
13. `ocos/learning/manager.py:148-162` — PreferenceModel 对已有 key 只更新 confidence 不更新 value（首次观测值固化，偏好"学习"不收敛到新值）。
14. `ocos/learning/skill_growth.py:224-227` — procedure 用 `zip(agent_types, task_types)`，episode 缺 agent 或 task_type 时两列表长度不齐导致跨 episode 错位配对。
15. `ocos/learning/metacognition.py:230-236` — `_find_matching_rule` 兜底循环两个 if 条件等价（`rid == match.skill_id` 与 `str(rid) == match.skill_id` 重复），冗余代码。
16. `ocos/growth/engine.py:52,541` — FORBIDDEN_FILES 的 "*.db"/"*.sqlite" glob 模式用 `p.name in FORBIDDEN_FILES` 精确比较，永不命中（实际防护靠 `.py` 后缀白名单兜底，风险被覆盖但机制失效）。
17. `ocos/growth/engine.py:206-211` — 信号状态仅推进到 "analyzed"，tech_signals.status 的 applied/skipped 值从未写入，信号级审计链不完整。
18. `ocos/reflection/manager.py:236-264` — propose_wisdom 达 max(100) 直接返回 None，无淘汰/晋升机制，智慧池饱和后新候选永久丢失。
19. `ocos/reflection/self_review.py:139` — 默认 DB 路径 ~/.ocos/ocos.db 不存在时静默只采集代码资产域，报告运行域全 0，虽有 evidence_note 但生产者可能忽略。
20. `ocos/cognitive_nutrition/data_feeder.py:323-331` — `for i, i in enumerate(interactions)` 变量遮蔽，metadata["interaction_id"] 存入整个 dict 而非序号。
21. `ocos/cognitive_continuity/life_memory_graph.py:37-42` — MAX_SEASONS=16 与 TimeGranularity.SEASON 定义存在但引擎无 aggregate_season 方法，季度层断裂。
22. `ocos/cognitive_continuity/cognitive_timeline.py:82-96` — record_intent docstring 称"严格拒绝非用户来源"，实现无任何来源校验参数，CC49-04 约束仅靠调用方自律。
23. `ocos/cognitive_continuity/identity_continuity.py:86` — check_continuity 对比基准取 `snapshots[-2]`（隐含 current 已 append 的约定），调用方未 append 时语义漂移。
24. `ocos/perception/file_sensor.py:154` — Observation id 用 `hash(key)`（进程随机化），跨进程审计不可复现（仅内存使用，影响有限）。
25. `ocos/reflection/manager.py` / `ocos/evolution/evolution_memory.py` / `ocos/cognitive_continuity/*` — 三个"长期"记忆/历史模块均纯内存无持久化，重启全失，与各自"5-10 年/为未来进化提供参考"的定位不符（依赖外部装配方落盘，当前无）。

**P5**（提示级）
- multi_modal.py 的 AudioSensor/VisionSensor 为转录文本哑壳（modalities 标注为 TEXT），命名易误导为真实音视频感知；生产零调用。
- evolution/__init__.py 与 extension/ 存在两个同名 ApprovalEngine（不同实现），import 时需辨明。
- perception/multi_modal.py、perception_validator/semantic_extractor 在生产装配中未启用，属"已建未接线"能力（self_review 的双域辨析纪律也要求如此表述）。
- learning/__init__.py 的 __all__ 未含 experience_learning/skill_growth/metacognition/persistence 四个子模块的导出。


##### 审计分组 W9：goal 目标系统 + daemon 守护进程 + execution 执行闭环(DecisionBridge) + audit + diagnosis + health_examination + living_verification + living_test 风险清单（原文）

| 级别 | 位置 | 现象 | 后果 |
|---|---|---|---|
| **P1** | ocos/execution/bridge.py:905-910 | `_handler_dag_task` 处理 LLM 输出的 `FILE_WRITE\|路径\|内容` 时，以 `payload.get("approval_id", "task-approved")` **代码自造审批 ID** 传给 `_handler_file_op`，绕过 L751-753 "file op requires approval_id（必须经审批流触达）"的守门；且该路径在 OCOS_APPROVAL_MODE=auto（默认）下无需任何人工批准即可触达（execute_dag_task 以"人工创建目标=隐式授权"为由对写类任务直接走 LLM 执行） | LLM 规划的任意绝对路径文件写入可无人批准落地（仅剩 file_ops 内建受保护路径拦截与沙盒约束）；审批流完整性被架空，"批准=authority"语义失效 |
| **P1** | ocos/health_examination/health_model.py:59-84 + structural_examiner.py 全文（实测复现） | OCOS_ORGANS 注册表失配：`ocos.self_model`/`ocos.continuity`/`ocos.os` 模块不存在（实际为 ocos.self/ocos.cognitive_continuity/ocos.os_v1），且 12 器官的 required_exports 在真实包顶层全部缺失（实测 Memory/WorldModel/Decision/CognitiveLoop/PersonalIntelligence 等导出均 missing，ocos.capability/ocos.runtime 导入即异常） | 结构体检对健康系统报大面积 MISSING/INCOMPLETE；基于其的 HealthCertification/ready_for_production 结论不可信——体检器"测错了对象" |
| **P2** | ocos/execution/pending.py:34-41 + bridge.py:416-420 | `OCOS_APPROVAL_MODE` 默认 `auto`：WRITE_CHAPTER/SEARCH_WEB/RUN_COMMAND/HTTP_FETCH 等 ASK 类动作默认**自动批准执行**（仅剩 SandboxOps 白名单+敏感路径闸门）；bridge._adjudicate 对"未分类动作"在审批关闭时也返回 auto（L433-438） | 安全默认值反转：部署者不改环境变量即处于"无人工审批"模式；高危动作防线只剩白名单单层 |
| **P2** | ocos/audit/task_simulator.py:17-155 + audit_report.py:64-119 | TaskSimulator 十个任务全部 `_s()` 工厂硬编码 passed=True；TaskSimulator/IntegrationTracer/ArchitectureMap 的"通过"均为目录存在或常量 | run_full_audit() 的 grade 必然虚高，审计报告自证合格，无证明力；若被用于发布决策即为系统性自欺 |
| **P2** | ocos/health_examination/connectivity_examiner.py:69,80 + immune_examiner.py:23-27 + recovery_examiner.py:69-105 | 连接体检默认全连通（不注入=25/25 满分）；免疫体检无生产 guard 注入（0 分）或注入恒 True lambda（满分）；恢复场景 2/3 硬编码 recovered=True | 体检得分完全由调用方注入的假设决定，生产路径无真实接线 → "健康认证"结论可被任意构造 |
| **P2** | ocos/living_verification/benchmark_runner.py:236-240 | `on_execute_task` 未注入时任务直接判 PASS（"structural check"） | LV57-04 能力真实性基准在无执行器时 100% 通过，"注册≠执行"的验证目标自我违背 |
| **P2** | ocos/living_test/living_test_protocol.py:138-151 | `quick_living_check()` 注入恒 True 的假守卫/假持久化钩子 | 必然产出高分 ALIVE 报告；若被当作健康证明对外引用即为虚假结论 |
| **P2** | ocos/daemon/repair_link.py:213-236 | `_make_checkpoint` 写空 data 的标记型 checkpoint；`_rollback_checkpoint` 的恢复循环体为 `pass`（仅归档类靠执行器内转存，其它修复无数据级回滚） | SD56-04 "修复前必须 checkpoint + 失败自动回滚"的数据级承诺部分落空；REINDEX/WAL checkpoint 类修复失败后无法恢复原状 |
| **P2** | ocos/diagnosis/manager.py:308-355 | `_auto_repair_signals`：构造的 DiagnosisReport 不含信号类别/受影响组件（target="unknown"）、executor 未注入 execute_step/create_checkpoint 回调、checkpoint_id 未传入 executor | SelfDiagnosisManager 的 AUTO/HYBRID 自动修复路径必然"提案→执行失败→回滚"空转；统计数字（auto_repairs_performed）不反映真实修复 |
| **P3** | ocos/goal/store.py:106-123 | `save()` 用 INSERT OR REPLACE 且 progress 恒写 0.0、created_at 恒写当前时间 | 对已存在 goal_id 重复 save 会静默重置进度与创建时间 |
| **P3** | ocos/execution/bridge.py:594-612 | `_handler_query_db` 硬编码读 `~/.ocos/ocos.db`，不使用 self._db_path | daemon 使用自定义 db_path 时 QUERY_DB 查错库；且跨进程共享 home 库可读到其它实例数据 |
| **P3** | ocos/execution/bridge.py:800-827,1011-1026 | LLM 调用前 pop 全部 proxy 环境变量、finally 恢复——进程级全局状态修改，无锁 | 多线程并发 LLM 调用（daemon tick + approvals）时环境变量互相踩踏，可能污染其它组件的网络行为 |
| **P3** | ocos/daemon/__init__.py:486-511 | `_push_goal_results` 直接访问 `self._user_inbox._db_path` 私有属性并新建裸 sqlite3 连接；按 `tags LIKE '%goal_result%'` 匹配 | 违反项目自身"连接纪律"（get_connection 池化约定）；LIKE 匹配脆弱（episode tags 结构变化即失效） |
| **P3** | ocos/execution/bridge.py:845-849 | `_run_one` 只读判定用子串黑名单（"write"、">"、"rm"…），如含 ">" 的合法管道/重定向以外场景误伤，且 "write" 子串会误拦含该词的只读命令 | LLM 合法只读任务假性失败（与 P6/UX-I+ 修复的 /etc 误拦同类问题的残留面） |
| **P4** | ocos/goal/goal_monitor.py 全模块 + maintenance_engine.py | Phase 39.6 维护子系统在生产 daemon/agent 路径无任何调用点（grep 仅 ocos/homeostasis.py re-export 与 tests） | 目标停滞/失焦告警能力建而未用；STALLED/WARNING 目标在真实运行中无人发现 |
| **P4** | ocos/audit/boundary_checker.py:148-253 | 10 条边界中仅 4 类有扫描实现；扫描为关键词匹配（如 "external"+"memory"+"write" 同行即报） | 6 条边界静默不检；4 条实现误报/漏报并存 |
| **P4** | ocos/daemon/factory.py:28-97 | `_make_confidence_source` 用相邻字符 bi-gram 匹配历史任务（无分词语义） | 置信度门信号弱：无关任务因字符重合误匹配历史成败，升级决策噪声大 |
| **P4** | ocos/execution/goal_executor.py:195-208 | persist_result 写 agent 层 `goal` 表（与域层 goals 表不同 schema），且 UPDATE 不存在行时静默 0 行 | CLI 直执行结果不回写域层 goals 表 → 域层目标可能永久滞留 ACTIVE |
| **P5** | ocos/audit/audit_report.py:69 | `audit_date="2026-07-26"` 硬编码 | 报告日期失真 |
| **P5** | ocos/daemon/repair_link.py:261 | `cutoff = time.time() - 30*86400` 计算后未使用（实际用 cutoff_iso） | 死代码，无功能影响 |
| **P5** | ocos/goal/validator.py:74-80 | `reject_self_module()` 为空方法（依赖 import-rule 测试强制） | 接口语义与实现不符，调用者会以为有运行时检查 |
| **P5** | ocos/living_test/day3_identity_stability.py:50-55 | `drift_detector` 返回值语义为 "True=稳定"，与名称暗示（True=检测到漂移）相反，且 run_living_test 默认注入 `lambda: True` | 协议内 Day3 漂移检查恒"无漂移"；外部复用时极易接反 |


##### 审计分组 W10：persistence/storage/snapshot/recovery 持久化 + models 数据模型 + contracts/events/event 事件与契约 + constitution 宪法 + kernel 内核 + os_v1 + logging/alerts/auth/security/monitoring/performance/operations/tool/distributed 基础设施 风险清单（原文）

**P2（高，建议尽快修）**
1. `storage/event_store.py:193-195` — `_next_sequence()` 先 `SELECT MAX(sequence)` 再另起事务 INSERT，多连接并发下序号重复；`INSERT OR IGNORE` 以 event_id 为主键，撞 event_id 时静默丢事件，撞 sequence 时数据仍插入（sequence 非唯一约束），重放顺序可能错乱。后果：恢复链事件重放次序/完整性受损。
2. `storage/schema.py:254-271` vs `goal/store.py:53` — schema.py 定义 `goal` 表（migrations v3 落库），而 goal/store.py 自建 `goals` 表并在生产使用；两套 goal 持久化结构并存。后果：同一数据库内双目标表，读写分裂、迁移 v3 建的表成死表，白皮书 schema 描述易失真。
3. `kernel/event_schema.py:180-191 与 232-268` — GOAL_SET/GOAL_UPDATED/GOAL_COMPLETED 在 EVENT_SCHEMA_REGISTRY 中重复键，后者覆盖前者，required_payload_fields 从 {goal_id,description,priority} 弱化为 {goal_id}(或 {goal_id,outcome}→{goal_id})。后果：事件 payload 校验弱化，脏事件可入库。
4. `logging`（整体）+ `ocos/event/__init__.py:278-285` — 用户消息内容明文写日志，无脱敏。后果：隐私/合规风险（P2~P3，取决于部署环境）。
5. `recovery/crash_recovery.py:53-92` — recover() 只统计 replay 事件数，不将事件重投递给任何处理器，也没有对 stale 检查点做任何标记/清理；`get_status():111` 的 `incomplete_checkpoints` 实为 `checkpoint.count()`。后果：崩溃恢复闭环缺失，恢复报告数字有误导性。
6. `security/manager.py:147-159` — RateLimiter 突发桶逻辑：`bucket = max(0, bucket - elapsed_seconds)`，把请求个数按流逝"秒"折减，单位语义错误；突发限制形同虚设（elapsed>burst_size 后永不触发）。后果：限流防线弱化。
7. `operations/sandbox_ops.py:166-179` — 黑名单为子串匹配且无归一化：`"rm  -rf /"`（多空格）、`"rm -rf ${HOME}"` 等变体绕过子串匹配；`shell=True` 执行（:225-233）依赖白名单兜底；`SANDBOX_PATHS:101` 硬编码开发者本机绝对路径。后果：沙盒绕过面存在（strict 白名单可拦不在名单的变体，但白名单前缀命令的参数不可控）。
8. `persistence/state_serializer.py:29` — `compress=True` 声明无实现；`Checkpoint` dataclass 全库无生成者。后果：声明能力缺失，属半成品接口暴露给调用方。

**P3（中）**
9. `recovery_resilience/recovery_monitor.py:265-276` — `_check_goal_auto` 恒 False；`_check_capability_hallucination` 依赖 `never_recovered` 属性而该属性从未被赋值（getattr 默认 False）。后果：ResilienceReport 的两项"0 通过判据"由实现缺陷自动满足，测试结论（all_criteria_met=True, score=100）存在虚高。
10. `os_v1/freeze.py:101-103` — Freeze 签名为 `f"{mod}:v1.0"` 字符串拼接，非密码学签名；freeze 后无实现变更强制校验钩子。后果：Scope Freeze 是声明式而非强制式（与"冻结接口不冻结实现"的 OS50-05 一致，但应向读者说明其非防篡改性质）。
11. `os_v1/personal_os.py:126-146` — process() 的 decide/execute/learn 段为占位（result 为回显字符串，confidence 恒 0.8）。后果：统一入口的认知闭环未接线，若被当作完整 OS 宣传需降级表述。
12. `constitution/statement_validator.py:122` — value_judgment 第二条正则 `\\w+` 双反斜杠笔误，匹配字面 `\w+` 使该规则近乎失效。后果：价值判断检测覆盖率下降。
13. `kernel/goal_types.py` 与 `kernel/abi.py`/`models/goal.py` — 双 GoalStatus（PENDING 系 vs created/active 系）、双 Goal 类型并存；`kernel/abi.py:224` Goal.__post_init__ 延迟 import models.goal 形成受控环。后果：跨模块混用易错（如把 GoalStatus.PENDING 传给 abi.Goal 会 ValueError）。
14. `events/event_bus.py:67-85` — unsubscribe 恒返回 True，无法得知是否真删除；`publish(sync=False)` 起 daemon 线程，无汇合与背压。后果：订阅生命周期管理弱。
15. `events/event_ingestion.py:99-113` — 依赖总线暴露 pending_events/get_pending/poll 之一，但自家 `ocos/events.EventBus` 与 `ocos/event.EventBus` 均无这些接口（后者叫 ingest()）。后果：EventIngestion 接在两套真实总线上都拉不到事件（对 event 包总线应直接调 ingest）。
16. `persistence/manager.py:350-364` — `_find_snapshot` 对 LAST_KNOWN_GOOD 策略未做区分实现；`restore_checkpoint:231` 重建 CheckpointManager 时未传 ttl（用默认 86400，与保存时可能不同的 ttl 不一致——load 不受影响，影响有限）。
17. `monitoring/manager.py:230-232` — Prometheus 指标名 `ococ_up` 拼写错误；:255-260 histogram 的 0.9/0.99 分位都输出 max。后果：监控数据失真。
18. `auth/identity_store.py:151` — close() 后 self._conn=None，再调用即 AttributeError；且与 `ocos/agent/identity_store.py` 构成双身份存储实现。后果：可用性与一致性小坑。
19. `events/dead_letter_queue.py:122-124` — replay 用 `r not in target` 剔除，依赖 dataclass __eq__（逐字段比较），同字段记录会误同；无唯一 record_id 校验使用。后果：极端情况下重放语义歧义。
20. `kernel/constitution.py:212-226` — validate_event_bus_communication/validate_no_direct_imports 恒 True 占位。后果：运行时"宪法钩子"无实效（真实校验在测试，已在注释声明）。
21. `storage/migrations.py:102-107` — 迁移逐条 execute+commit，无整体事务与 downgrade。后果：中断后可能半套表（CREATE IF NOT EXISTS 可重入，风险有限）。
22. `distributed/manager.py:439-452` — ROUND_ROBIN/WEIGHTED/AFFINITY 简化为同一实现；单进程内存模拟，host/port 无真实网络。后果：宣称"分布式"需限定表述。
23. `tool/manager.py:342-390` — call_tool 为模拟执行；unblock_tool 恒恢复 READ_ONLY 丢原权限。后果：工具执行闭环未接真实后端。
24. `performance/manager.py:419-422` — get_cache(name) 忽略 name 返回同一实例；SmartCache/AsyncBatchProcessor 无锁。后果：命名缓存语义误导，并发场景需外加上锁。
25. `snapshot/manager.py` — snapshots 表无清理接口，data JSON 全量膨胀无 prune。后果：长期运行表无限增长。

**P4（低）**
26. `monitoring/manager.py:37-50` — AlertSeverity/AlertState 用 `class X(str)` 而非 Enum，可被实例化出新值。
27. `logging/logger.py:157` — `logger.__class__ = OCOSLogger` 换类手法对 fork/子解释器脆弱；`_apply_default_config` 与使用方 dictConfig 可能叠加 handler。
28. `events/event_bus.py:85` — unsubscribe 返回值语义（见 P3-14）；`subscriber_count` 不去重全局+类型双订阅者。
29. `persistence/storage_types.py` — Checkpoint/LifecycleLog.total_uptime_ticks 字段无维护者。
30. `kernel/abi.py:176` — Memory.memory_type 已废弃但仍为字段，新代码可能继续依赖。
31. `operations/search_ops.py:27` — API_WHITELIST 为可变 set（非 frozenset），运行时可被改写。
32. `alerts/manager.py:55-59` — 通道异常静默吞掉（无日志），故障不可观测。
33. `storage/connection.py:37-41` — `:memory:` 每次返回新连接，同一内存库跨 Store 不共享（隔离语义是刻意设计，但易被误用为"共享内存库"）。

**P5（提示/记录）**
34. `operations/sandbox_ops.py:101` — 硬编码个人路径 `/home/laogao/...`，跨环境不可移植（移植时需配置化）。
35. `events/event_store.py:38-42` — StoreSnapshot 默认 timestamp 用 `__import__("datetime")` 内联写法，可读性差。
36. `kernel/event_schema.py:38` — deserialize 对非法 event_type 抛 ValueError（EventType(...) 构造），调用方需捕获。
37. `constitution/hub.py:51-79` — check_decision 未聚合 Static Constitution 与 GoalOriginEnforcer（仅 behavioral），与"三层宪法统一入口"的注释存在差距。
38. 任务书偏差记录：events 模块任务书写 6 个文件，实际 5 个；`ocos/event` 与 `ocos/events`、`ocos/persistence` 与 `ocos/snapshot`、两个 `CrashRecovery`、两个 `AlertManager`、两个 `EventBus` 均为项目内有裁决注释的并存设计（GAP-P3/AUD-F5/F6 裁决），审计确认其分工声明与代码一致。


##### 审计分组 W11：编排/自治/扩展/外部通信等支线模块 + 根模块 风险清单（原文）

| 级别 | 位置 | 现象 | 后果 |
|---|---|---|---|
| P1 | ocos/orchestration/engine.py:346 | 调用 `record.to_dict()`，而 `ExecutionRecord`（agent_orchestration/audit.py）无该方法（实测 hasattr=False） | 协作路径每个任务 execute_fn 抛 AttributeError 被吞 → 协作结果恒报失败；一旦该模块被接线即系统性误报 |
| P1 | ocos/agent_orchestration_autonomous.py:316-323 | 串行路径 `_monitor_running`：running 任务下一 tick 直接按 `attempts<=max_attempts` 判 completed，无任何真实执行 | 目标→任务→"完成"全链路伪造成功；若被当编排主控接入，产出与事实脱钩（违背项目 AUD-F11 诚实失败修复方向） |
| P2 | ocos/external/server_manager.py:284-301 | `start()` 在 `finally: loop.close()`，而 `_async_start` 中 `asyncio.create_task(_run_server())` 的 uvicorn serve 任务挂在该 loop 上 | start() 返回 True 后 API server 任务随 loop 关闭而亡；健康检查随后必然失败；auto_restart 将反复无效重启 |
| P2 | ocos/external_communication/manager.py:402-445 | `_WebSocketChannelPlaceholder/_HTTPChannelPlaceholder.send` 伪造 status="sent"、latency=1.5/2.3ms，无任何真实 IO | 通信记录/健康统计全部失真（假"已发送"），审计（AK-OUT-05）失去意义 |
| P2 | ocos/proactive/output.py:236,266 | `_today_count` 只增不减，无跨日重置（无 daily reset 路径） | 达到 daily_limit(5) 后 try_proactive_output/output_* 永久被节流，主动输出静默失效 |
| P2 | ocos/ecosystem/manager.py:296-305 | load_plugin 注释自认"模拟加载"，不加载任何代码即置 LOADED | 插件生命周期状态机为空壳；上层（若接线）误信插件已就绪 |
| P2 | ocos/engagement/manager.py:312-344 | execute_engagement 持有 `_request_lock`（RLock）期间执行 `_send_message` 外部回调 | 回调若跨线程再进入本管理器或做慢 IO，存在锁占用放大/阻塞风险；且 approve_engagement(175-186) 绕过频率与双检直接置 SENT |
| P3 | ocos/initiative/true_initiative.py:140-148 | `if idle_sec >= 1800 ... elif idle_sec >= 7200`：elif 不可达 | "2 小时状态确认"功能永不触发 |
| P3 | ocos/initiative/true_initiative.py:150-173 | `_pattern_based_initiative` 构造 requests 后硬编码 `return []` | 用户模式触发整段死代码；且该引擎被注入后无任何消费点（死注入） |
| P3 | ocos/sleep_dream/manager.py:158 | `elif DreamType.CREATIVE_COMBO:` 漏写 `== dream_type` 恒真 | PROBLEM_SOLVE/EMOTION_PROCESS 洞察分支不可达，梦境洞察类型失真 |
| P3 | ocos/agent_orchestration_autonomous.py:355-364 | `phase` 从未被置为 ADAPTING | `_adapt()` 失败重试逻辑不可达，失败任务永不重试 |
| P3 | ocos/autonomous_runtime/loop_supervisor.py:148-149 + autonomous_loop.py | `should_stop`（EMERGENCY_STOP）无任何轮询/消费方 | 防失控监督"报警不刹车"：runaway/CL46-01 违规仅记 alert，循环继续跑 |
| P3 | ocos/external/server_manager.py:197,205-210 | webhook 网关在独立线程自建 loop；stop_background 在另一 loop 上 await shutdown | 跨 loop 关闭不可靠，网关 daemon 线程可能存活至进程退出 |
| P4 | ocos/agent_orchestration/agent_pool.py:221 | 异常分支 `PoolResult.exception_result(contract.contract_id, ...)` 误把 contract_id 当 task_id | 异常结果的任务归属错乱（仅异常路径） |
| P4 | ocos/belief.py:263 | 负证据更新公式可产生负概率后被钳到 0.01；非严格贝叶斯 | 强负证据信息被截断，概率更新有偏 |
| P4 | ocos/autonomous/goal_manager.py:292-298 | 目标 id 含当前时间戳，同描述重复同步生成新 id | 重复目标堆积（无幂等） |
| P4 | ocos/engagement/manager.py:392-398 | `_update_urgency_stats` 首条即除以 total=1 前 avg 为 0，公式本身对；但 approve 与 execute 双路径都计数，会双计 | avg_urgency 统计口径漂移 |
| P5 | ocos/proactive/enhanced_output.py:293 | `_priority_ge` 无调用方 | 死方法 |
| P5 | ocos/autonomous_runtime/runtime_config.py:90-101 | validate() 全库无调用方 | 配置校验形同虚设 |
| P5 | ocos/plugins/__init__.py、ocos/stability/ | 空占位 | 无功能；建议移除或补 README 说明规划 |


##### W13 风险与规范发现（原文）

##### 4.1 Scope Freeze / DRAFT-FROZEN / 优先级机制的出处考证

- **Scope Freeze（范围冻结）**：明确的定义出处包括——
  - `docs/runtime/P2B_curiosity_drive.md`（标题即"P2-B 好奇心驱动 — Scope 冻结"，内含 "## 2. Scope（包含/不包含）" 章节）；同目录 `P2C_dream_consolidation.md`、`P2D_proactive_output.md`、`P2A_regulator_self_goals.md` 均为同模式 Scope 冻结文档。
  - `docs/BLUEPRINT_AGI_UPGRADE_v1.0.md` / `v1.1.md` 亦出现 Scope Freeze 表述。
  - 根目录 `OCOS_Cognitive_Sovereignty_Freeze_v0.1.md`（"冻结范围：系统身份、宪法条款、架构边界、核心子系统职责、开发阶段顺序"）是最高级别的 Scope 冻结文本。
  - `docs/ARCHITECTURE_FREEZE_PROTOCOL.md` 定义了模块准入的 AFP 三层治理（Principles → AFP → Frozen Modules）。
- **DRAFT-FROZEN**：**全仓 markdown（含 docs/ 与根目录）中未检索到 "DRAFT-FROZEN" 字样**。实际使用的冻结标记是 "FROZEN"/"❄️ FROZEN"（architecture/、docs/phase14/、docs/theory/）、"Freeze Certificate"/"Freeze Sign-Off"（audit/、docs/abi/00）与 "Scope 冻结"（docs/runtime/）。若上游任务假设存在 DRAFT-FROZEN 状态机，与仓库事实不符，应如实记录。
- **优先级机制（P0-P5）**：仓库中的优先级体系是审计发现分级，定义散落在各审计报告的"关键发现"表：
  - `docs/OCOS_AUDIT_KERNEL.md` §表：P0（EngineBridge 未注入、congruity 未实现）、P0+（AgentLifecycleManager 缺失）、P1（CircuitBreaker 重复定义）、P2（MigrationState 限制）——是 P0/P0+/P1/P2 分级的直接出处。
  - `OCOS_COMPREHENSIVE_AUDIT.md` §一"关键发现"表使用同一 P0/P0+/P1 分级。
  - `docs/PRODUCTION_VALIDATION_REPORT_20260905.md` §六使用 P2/P3（"P2 stale-ACTIVE 无回收、P3 429 限流、P3 未提交"）。
  - `docs/OCOS_POWER_ON_PLAN.md`/`OCOS_MODULE_AUDIT_20260830.md` 使用 P0-P4 波次与 GAP-P0~P3 编号（如 GAP-P1-1、PW-3.2、P2-5）。
  - **未见任何文档定义完整的 "P1-P5" 五级优先级规范**；实际在用的是 P0(+)/P1/P2/P3 发现分级 + GAP-P* 修复编号 + PW-* 上电编号三套并行的编号体系，彼此无统一对照表（规范缺口）。
- 另一优先级机制：**五个准入过滤器**（🧬活得更久/🧠思考得更好/🗄️记得更清/📈成长得更快/👤仍然属于人）正式定义于 `docs/ROADMAP.md` 头部与 `docs/OCOS_SYSTEM_DESCRIPTION.md` §2.3，要求每个新 Phase 至少满足其一。

##### 4.2 敏感信息处理现状

- **.env 含 4 个真实格式密钥**（键名：DEEPSEEK_API_KEY、MIMO_API_KEY、SILICONFLOW_API_KEY、COOPER_API_KEY；值形如 sk-a…/tp-c…/sk-l…/sk-B…，长度 35-51，具有真实密钥特征；本报告不记录值）。文件头注释甚至写着"⚠️ 请至对应平台重新生成密钥后填入"。
- **git 覆盖情况**：`.gitignore` 第 24 行已覆盖 `.env`（含 `.env.local`、`.env.*.local`）；`git check-ignore` 确认 .env 被忽略，`git ls-files` 确认 **.env 未被跟踪**——密钥未进入版本库，处置正确。`.env.example` 被跟踪（正常，其中全部为占位/注释）。
- 但存在两个衍生风险：① `.env` 中密钥与代码消费不匹配（见 4.3），若曾通过其它渠道（如 ~/.ocos/config.json、systemd Environment）复制密钥，真实密钥可能存在于仓库外多个位置；② requirements.lock、nul、quarantine_20260824/ 等环境快照文件被跟踪，暴露了本机路径 `/home/laogao/Documents/...` 与姊妹项目结构（轻度信息泄漏，无密钥）。
- `oscos.db`（根目录 200KB SQLite）被 .gitignore 的 `*.db` 规则忽略，未被跟踪，正确。

##### 4.3 配置加载优先级的证据

- **代码不加载 .env**：全 `ocos/` 包（含 tests/scripts）无任何 `load_dotenv` / dotenv 引用；requirements.lock 中虽有 python-dotenv==1.2.2，但只是 opentale 等依赖带入。即：**.env 文件在 OCOS 运行时实际不生效**，除非使用者在 shell/systemd 中手动 source。
- 代码实际配置优先级（按消费点取证）：
  1. **环境变量直接读取**（`os.environ.get/os.getenv`）：`OCOS_DB_PATH`（ocos/daemon/factory.py:204、ocos/interaction/context.py:52）、`OCOS_APPROVAL_MODE`、`OCOS_TICK_BUDGET`、`OCOS_LLM_DAILY_CAP`、`OCOS_ALERTS_DIR`（factory.py:195）、`OCOS_API_BASE/PORT`、`OCOS_ORGAN_BASE`、`OCOS_OPENTALE_TOKEN`、`OCOS_RATE_LIMIT`、`OCOS_MEMORY_DIR`、`OCOS_FEEDBACK_DIR`、`OCOS_MONITORING_PORT`、`OCOS_WEBHOOK_PORT` 等约 21 个 OCOS_* 变量，均有代码内默认值（env 缺省 → 内置默认）。
  2. **~/.ocos/config.json**：`ocos/interaction/converse.py:4,747-748` —— LLM 接入判定为"env（ANTHROPIC_API_KEY/OPENAI_API_KEY）或 ~/.ocos/config.json 任一有 key"，即 **env 优先、config.json 兜底**（从注释与判断顺序可证）；该目录还存有 config.json.bak_failover_20260905_141510（故障转移备份）。
  3. **引擎层**：`ocos/engines/text_generator.py:185,203,234` —— AnthropicProvider/OpenaiProvider 显式依赖 ANTHROPIC_API_KEY/OPENAI_API_KEY 环境变量，缺失即 raise/降级（诚实失败）。
  4. **.env 中的 DEEPSEEK/MIMO/SILICONFLOW/COOPER 四键在 ocos 源码中零引用**（grep 无命中）——结合 MODULE_AUDIT 9.3 "DeepSeek (deepseek-v4-flash) 经 OpenAI 兼容端点接入"，其消费路径应是 ~/.ocos/config.json 或 systemd EnvironmentFile，而非仓库内 .env。这是文档/示例（.env.example 甚至是 OpenClaw 的）与实际配置机制脱节的证据。
- 默认值汇总示例：DB 默认 `~/.ocos/ocos.db`（factory.py:204）、告警目录默认 `~/.ocos/alerts`、tick 预算 daemon 默认 15s、LLM 日预算默认 500 次（均见 POWER_ON_PLAN 执行记录与代码 getenv 默认值）。

##### 4.4 其它值得记录的发现（汇总）

1. **文档代差/双叙事**：docs/ 内同时存在三套叙事——Phase A-Z 时代（ARCHITECTURE.md/PROJECT_STATUS.md/README）、Era II Phase 21-30 时代（ROADMAP/gates/phase*_gate.py）、GAP/PW 上电时代（MODULE_AUDIT/POWER_ON_PLAN/PRODUCTION_VALIDATION）。各自内部自洽但相互间指标不同（148,000 行 vs 39,088 行 vs 306,321 行[OpenTale]；260+ 测试 vs 5287 测试），新读者极易混淆。
2. **OpenTale/OpenClaw 文档混入**：SYSTEM_OVERVIEW.md、architecture.md、ARCHITECTURE_PRINCIPLES.md、CODE_LEVEL_IMPLEMENTATION_REPORT.md、testing/TEST_STRATEGY.md、.env.example、.coveragerc 均来自姊妹项目，建议迁移或加显式归属标注。
3. **nul 垃圾文件已被 git 跟踪**（Windows 命令事故产物），建议删除。
4. **仓库内无任何容器化/编排/服务单元资产**；生产 systemd unit 在仓库外未版本化，且 daemon 默认审批关闭（auto）——与"仍然属于人"过滤器存在张力，PRODUCTION_VALIDATION §六已隐含提示。
5. **pyproject license 自相矛盾**（Proprietary text vs MIT classifier；README"版权所有"），发布前需统一。
6. **Makefile lint 目标是占位**（仅 py_compile 一个文件），ruff/mypy 配置存在但未接入 make 流程。
7. **docs 目录规模远超 PROJECT_STATUS.md 自述**（176 个文件 vs 文中列 3 个文档），文档索引缺失（无 docs/README 或 INDEX——adr/INDEX.md 仅覆盖 ADR 子目录）。
8. quarantine_20260824/ 的隔离动作未见对应的裁决/复盘文档说明 F4 规则全文（规则出处应在 Phase14.2 合同的 FORBIDDEN 词表），证据链略断。

—— 审计分组 W13 报告完 ——

## 11. 开发与迭代规范

### 11.1 OCOS 内核 Phase 迭代流程

1. **理论先行**：新能力先落 Layer 0-2.5 理论文档（docs/MANIFESTO L0 → LIFE_MODEL L0.5 → OCOS_CORE_CONSTITUTION L1 → IDENTITY_MODEL L1.5 → LIFE_CYCLE/GOAL_MODEL/BELIEF_MODEL/ATTENTION_MODEL/HOMEOSTASIS_MODEL L2 → RUNTIME_ABI L2.5）。
2. **Scope 冻结**：docs/runtime/P2*.md 模式——写明 Scope（包含/不包含）+ 边界约束编号（如 CL46-01~04、WM42-01~04、RS51-01~05）。
3. **准入过滤器**：每个新 Phase 必须至少满足五过滤check之一（🧬活得更久/🧠思考得更好/🗄️记得更清/📈成长得更快/👤仍然属于人）（docs/ROADMAP.md）。
4. **实现 + 测试**：实现后必须有 test_phaseN*.py 验收测试（验收编号 R*/S*/WM*/PS* 可追溯到设计文档）。
5. **Gate**：scripts/phaseN_gate.py 三段式（结构断言 + 全量回归 + import 规则检查）或 Makefile `make gate/full-gate`；冻结签发 Freeze Certificate（audit/ 目录模式）。
6. **审计闭环**：审计发现按 P0(+)/P1/P2/P3 分级登记，修复以 AUD-F* / GAP-P* / FIX-* / UX-* / PW-* 编号记账，并在模块审计文档留执行记录表（docs/OCOS_MODULE_AUDIT_20260830.md、OCOS_POWER_ON_PLAN.md 为范本）。

### 11.2 Scope Freeze 使用规则

- 冻结对象=接口契约而非实现（OS50-05 Freeze≠Dead）；冻结面变更必须走新冻结文档（版本号递增）。
- 代码级：OSFreeze（ocos/os_v1/freeze.py）生成 FreezeManifest（12 个 ABI_MODULES + 6 条宪法原则 + 3 个 SDK 协议签名）；verify_abi 仅查清单成员——**声明式冻结，无强制校验钩子**（P3 限制，见 10 章）。
- 治理准入：docs/ARCHITECTURE_FREEZE_PROTOCOL.md AFP 三层（Principles → AFP → Frozen Modules）；新模块进主干需过四门禁（Purpose/Authority Impact/Reality Boundary/Drift Test，见 architecture/phase14.2-b1c-freeze-report.md 范本）。
- 高级冻结：根目录《OCOS_Cognitive_Sovereignty_Freeze_v0.1.md》——系统身份/宪法四条/架构边界/子系统职责/阶段顺序永久冻结。

### 11.3 DRAFT / FROZEN 状态定义

- **"DRAFT-FROZEN" 两态字样在仓库中不存在**（全仓 markdown 零检索命中）。实际使用的冻结标记体系：**FROZEN / ❄️ FROZEN**（architecture/、docs/phase14/、docs/theory/ 的设计文档终态）、**Freeze Certificate / Freeze Sign-Off**（audit/phase14_freeze_certificate.md、docs/abi/00）、**Scope 冻结**（docs/runtime/P2*.md）。文档工作流实际为"提案 → 评审 → FROZEN"（如 architecture/phase14.2-b2-design.md 标 APPROVED 后出 freeze-report 标 FROZEN），即 **DRAFT（隐含）→ APPROVED → FROZEN** 三态，但无正式规范文档定义该状态机。

### 11.4 P1-P5 任务优先级规则

- 仓库历史无统一 "P1-P5" 规范；在用的是三套并行编号：**审计发现分级 P0(+)/P1/P2/P3**（docs/OCOS_AUDIT_KERNEL.md、OCOS_COMPREHENSIVE_AUDIT.md）、**修复编号 GAP-P0~P3 / PW-1~5（上电波次）/ AUD-F1~F14 / FIX-* / UX-***、**生产验证 P2/P3 残留**（PRODUCTION_VALIDATION_REPORT）。
- 本白皮书采用任务书的 P1-P5 五级（定义见第 10 章头），与历史编号的映射：历史 P0/P0+ ≈ 本 P1，历史 P1 ≈ 本 P1~P2，历史 P2 ≈ 本 P2~P3。**规范缺口：三套编号无统一对照表**，建议后续以本白皮书 P1-P5 为唯一分级语言。

### 11.5 OCOS 内核新增模块/新增文件开发约定

1. 依赖方向受 test_import_rules.py 强制：kernel 不懂业务（宪法 Rule 10）、runtime 不懂知识（Rule 11）、platform 只依赖 kernel+events、planning 禁 import ocos.self、digital_world 允许 agent/planning 禁 self。
2. 新模块必须：带边界约束编号 docstring（如 CR55-01~04 / AU51-01~04 模式）、声明 manifest（engines 需 `__manifest__ = EngineManifest(...)` 供 EngineDiscoverer 发现）、有 test_phaseN 验收、过 gate。
3. 命名避坑清单（本审计实测的同名陷阱）：两套 EventBus（ocos/events vs ocos/event）、两个 EventBus 均无 emit、双 Goal 状态机（kernel.goal_types PENDING 系 vs models.goal active 系）、双 Goal 表（goal vs goals）、双 Belief（memory/belief/__init__ vs belief/models）、三个 CapabilityDescriptor（capability/descriptor、capability_types、capability_reality/adapter_types）、三个 CapabilitySelector、四个主动输出实现（proactive/engine、proactive/output、proactive/enhanced_output、engagement）、三个 orchestrator 概念（orchestrator.py 垫片、orchestration/engine、agent_orchestration_autonomous）、双 ApprovalEngine（evolution vs extension）、双 AlertManager（alerts vs monitoring）、双 RiskLevel（runtime/adaptive_control vs runtime/permission）、双 TaskDAG（planning vs task，AUD-F7 裁决并存）。
4. 时间纪律：记忆域时间字段一律 ISO UTC TEXT；SQL 时间过滤必须 ISO 字符串（TEXT 与 REAL 恒不命中）；禁 naive datetime.now() 混入 aware 链。
5. SQLite 连接纪律：统一走 ocos/storage/connection.get_connection 池化连接（禁 close/改 row_factory）；:memory: 特判语义。
6. 异常纪律：禁止裸 `except Exception: pass`（历史 7 次静默失效的元凶模式）；失败必须 logger.warning 以上留痕；oc os.logging 的 .exception() 是坏的（extra 撞 exc_info），用 error(exception=e)。
7. 代码修改后必须重启 server/daemon（进程旧代码教训，MODULE_AUDIT 9.4）。

## 12. 内核快速故障排查手册

### 12.1 常见故障现象 → 源码位置 → 排查步骤

| 现象 | 源码位置 | 排查步骤 |
|---|---|---|
| daemon 起不来 / 立即退出 | ocos/daemon/__init__.py（daemon 锁）、cli/commands/run.py | 1) 看日志 "Daemon lock failed"（另一实例持有 db）；2) `ocos status` 探库；3) 检查 OCOS_DB_PATH 一致性 |
| 目标卡 PENDING 不执行 | goal/store.py claim、daemon/_claim_persisted_goals | 1) daemon 是否存活（~/.ocos/daemon_heartbeat.json 的 ts）；2) goals 表 status/origin_level/caller（claim 只认 PENDING+HUMAN）；3) 是否队列背压拒绝（submit 返回 -1） |
| daemon 假死（进程活、心跳停更） | daemon/watchdog.py + daemon/__init__.py `_tick_loop` 自愈兜底 | 1) 心跳 age（converse 30s 判活）：`cat ~/.ocos/daemon_heartbeat.json` 的 ts；2) watchdog timer 是否在跑：`systemctl --user list-timers ocos-watchdog.timer`；3) 手动触发：`python -m ocos.daemon.watchdog`（age>90s 自动重启 + ops/restart.log 记账）；4) 查 journalctl "Tick loop residual failure" 定位残余异常源（v1.3.1 起兜底不应再发生线程死亡） |
| 心跳文件不存在但不该重启 | daemon/watchdog.py `_heartbeat_age_s` | 心跳缺失 = 人为 stop / 从未启动 → 看门狗诚实跳过（action=skipped），不误杀；确认意图后 `systemctl --user start ocos-daemon` |
| 目标永久滞留 ACTIVE | goal/store.py + daemon 启动回收 | 孤儿回收只在 daemon start 时跑 requeue_stale_active——异常退出后重启 daemon 即回收（watchdog 自动重启同样触发）；已知 P2（生产验证报告同款） |
| 对话无回复 / mock 回复 | interaction/converse.py | 1) 日志 "LLM reply failed, falling back to state reply"；2) 检查 ~/.ocos/config.json llm 段与 key；3) TextGenerator 初始化行看 provider 与 failover；4) LLM 日预算是否耗尽（bridge "budget" 日志） |
| 工具/命令被拒 | execution/bridge.py _handler_run_command、operations/sandbox_ops.py | 1) 白名单前缀（ALLOWED_COMMANDS 30 条）；2) 敏感路径拦截（PUBLIC_READONLY_PATHS 之外的 /etc 等）；3) 复合命令分段校验失败点；4) USE\| 协议每回复 ≤2 轮工具上限 |
| 审批项不出现 / 不执行 | execution/pending.py + bridge.py | 1) OCOS_APPROVAL_MODE 是否 auto（默认关闭人工审批，ASK 自动执行）；2) pending_actions 表 status；3) approvals approve 后看 result_summary（诚实失败会记录 block_reason） |
| 记忆不落库 / 召回为空 | memory/* | 1) 直查 ~/.ocos/ocos.db episodes/belief 表；2) Significance Gate 是否 FAIL（score<0.5，rejection_reason 列）；3) recall 相关性阈值（bi-gram Jaccard + 动态阈值）；4) experience 召回恒空是已知 P2（hub 无 experience 属性） |
| dream 巩固没发生 | daemon/_run_dream_cycle | 1) tick 数是否达 dream_interval_ticks(200)；2) 生命周期相位（历史 bug：BOOTING→DREAMING 非法转换曾致巩固从未运转，已修）；3) wisdom_items/belief 表增量 |
| 重启后身份/目标丢失 | agent/agent_runtime.boot + identity_store | 1) identity/goal 表有无行；2) boot 日志 "Identity restored / Goals restored: %d"；3) agent 层 goal 表与域层 goals 表双写是否同步（agent_runtime.py:1294-1303） |
| 快照恢复失败 | persistence/recovery_manager、runtime/recovery | 1) 快照 checksum 校验（CORRUPT→fallback）；2) /tmp/ocos_checkpoints 是否被系统清理（P2 部署缺陷）；3) cold_boot 只认 ≥4 域完整快照 |
| API 起了但连不上 | external/server_manager.py | start() 的 finally loop.close() 疑杀 serve 任务（P2 静态推演）——直用 `python -m ocos.interaction.api.server` 绕开 |
| 测试莫名失败 | conftest + text_generator | 用户机器 ~/.ocos/config.json 的 llm_fallback 段会泄漏进 test_text_generator（P3-01）——测试前确认 _isolated_llm_config 生效 |
| 改了代码没生效 | 全局 | **重启 server/daemon**（进程旧代码，MODULE_AUDIT 9.4 首条教训） |

### 12.2 内核层面专项问题定位

- **信息漂移（记忆/知识失真）**：① 查 validator 拦截记录（Belief.rejected_count、ExperienceValidator violations→rejection_reason）；② 查 dream 巩固链（belief_consolidation 的 _trail 幂等溯源字段）；③ 查 world_model 污染（P1-4 类型冲突检查失效——核对 world_store 中 entity_type 与观察源）；④ 查 statement_validator 六类规则命中（personality/identity/sovereignty CRITICAL）。
- **个体状态错乱**：① identity_snapshots 表时间线；② cognitive_continuity 漂移评分（~/.ocos/continuity.json 26 份历史，severity 累加项：风险偏好+0.3/决策风格+0.2/智慧倒退+0.3/核心记忆替换+0.4）；③ drift_detector（未接线，只能手动构造调用）。
- **决策闭环断裂**：① DecisionBridge BridgeReport 的 verdicts 统计（by_verdict/executed/pending/denied）；② L8 置信度源（episodes 表近 30 天 goal_result 成功率，bi-gram 匹配噪声大——P4 已知）；③ 断路器状态（writer_engine circuit_state）。
- **时序状态异常**：① event_memory 时间线重建（reconstruct_timeline）——注意本地时区写库缺陷（P2）导致跨时区/夏令时偏移；② event_store 表 created_at 两种格式并存（datetime('now') 空格 vs ISO T）——SQL 过滤必须匹配对应格式；③ 归档一致性（mark_archived 只改 header 的已知缺陷）。
- **性能劣化**：① TickContext/队列增长点（perception_bridge 未处理事件无界、permission trace 缓冲无上限、_CHAT_SESSIONS 无淘汰、snapshots 表无清理）；② belief_system._persist O(N) 全量扫描；③ p95 劣化多为 LLM 供应商 429 退避（生产验证报告 §5）。

## 13. 附录

### 附录A：OCOS 项目目录树完整展示

目录结构（目录 + 直接文件数；逐文件明细见第 3 章）：

```text
19 .

```


（完整逐文件索引见第 3 章；测试文件逐条索引见 3.12；文档资产逐条清单见 3.13。）

### 附录B：OCOS 第三方依赖清单以及版本现状

- **运行时**（pyproject dependencies，均为 >= 下限约束）：pydantic>=2.0、sqlalchemy>=2.0、fastapi>=0.100.0、uvicorn>=0.23.0、httpx>=0.25.0、numpy>=1.24.0、scipy>=1.11.0、textual>=8.0.0。
- **dev**：pytest>=7.0、pytest-asyncio>=0.21.0、pytest-cov>=4.0、pytest-mock>=3.10、ruff>=0.1.0、mypy>=1.0、pre-commit>=3.0。
- **ml（可选）**：torch>=2.0、transformers>=4.30。
- **requirements.lock（95 项精确锁定）关键版本**：fastapi==0.139.2、uvicorn==0.51.0、pydantic==2.13.4、textual==8.2.8、numpy==2.5.1、httpx==0.28.1、starlette==1.3.1、prometheus_client==0.25.0、chromadb==1.5.9、jieba/rank-bm25（检索）、opentelemetry 1.44.0 全家桶、kubernetes==36.0.3、pytest==9.1.1、ollama==0.6.2、onnxruntime==1.27.0、python-dotenv==1.2.2（仅 opentale 依赖带入，ocos 源码零引用）。
- **漂移**：lock 内 editable `ocos==0.2.0` 与 pyproject 1.0.0 不一致；sqlalchemy/scipy 声明无使用痕迹；lock 与姊妹项目 opentale 深度绑定（-e opentale）。
- **标准库关键依赖**：sqlite3（WAL）、dataclasses（frozen 广泛使用）、asyncio、argparse、textual（TUI）、FastAPI（API）。

### 附录C：白皮书信息来源说明

**全部来自源码解析与实测**（无外部资料）：
1. **逐文件深读**：13 个审计分组（W1-W13）对 ocos/ 下 663 个源码 .py（不含 ocos/tests 175 个测试文件单独成组）+ tests/ + scripts/ + 根配置 + docs/ 176 文件全量覆盖，总深读约 9.1 万行内核源码；每个文件条目含"导入依赖/被调用方"均为 grep 反查实证。
2. **运行时实测**：各分组在审计中实跑 pytest 数千用例 + 26 项功能级脚本实测（W10）+ 6 组关键路径实测（W7）+ CLI 冒烟（W3：goal create 真实落库、plan 真实分解 5 任务 DAG）+ 缺陷复现（world_validator 自比较、plugin_sandbox hook 未安装、attention focus TypeError、bridge_session AttributeError、health 器官失配等均实测复现）。
3. **静态推演**：无法在本环境实测的路径（TUI 终端交互、HTTP 真实起服、systemd restart、organ 外部 API）标注【静态推演验证】。
4. **文档佐证**：docs/ 的 10 个关键文档（ARCHITECTURE/PROJECT_STATUS/ROADMAP/OCOS_SYSTEM_DESCRIPTION/OCOS_POWER_ON_PLAN/LIFE_CYCLE/RUNTIME_ABI/OCOS_MODULE_AUDIT_20260830/PRODUCTION_VALIDATION_REPORT_20260905/SYSTEM_OVERVIEW）精读摘录用于第 0/11 章历史叙事；注意其中三套时代叙事存在指标代差（148,000 行 vs 39,088 行 vs 306,321 行[OpenTale]；260+ vs 5287 测试），本白皮书以 2026-09-05 源码实测为准。
5. **明确排除**：OpenTale/OpenClaw 混入文档（SYSTEM_OVERVIEW.md、architecture.md、ARCHITECTURE_PRINCIPLES.md、CODE_LEVEL_IMPLEMENTATION_REPORT.md、testing/TEST_STRATEGY.md、.env.example、.coveragerc）不作为 OCOS 内核事实来源，仅在附录标注混入事实。
