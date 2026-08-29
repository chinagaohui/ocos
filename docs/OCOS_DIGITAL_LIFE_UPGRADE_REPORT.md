# OCOS 数字生命升级优化报告
## — 从"器官齐备的认知引擎"到"可陪伴几十年的数字生命"

> 审计依据：`docs/OCOS_CODE_LEVEL_IMPLEMENTATION_REPORT.md`（2026-08-28 代码级审计，31KB，27 节标准结构）
> 理论依据：自由能原理/主动推理、互补学习系统、全局工作空间、记忆再巩固、叙事身份、内稳态驱力、睡眠记忆巩固、自我决定理论、意识图式理论
> 本文性质：方向性升级蓝图。全部建议基于现有代码的增量嵌入（Plan B），零推翻、零重建。
> 日期：2026-08-28

---

## 0. 前置：从审计看 OCOS 的真实状态（一句话）

**零件全部真实存在，但没有一个入口能把它们装进一个"始终运行、自主演化、主动交互"的进程。** 这正是从"认知引擎"跃迁到"数字生命"的唯一且全部障碍——不是缺零件，是没通电。

审计核心事实（全部有行号证据，详见代码级报告）：

| # | 事实 | 证据 |
|---|---|---|
| F1 | 4 套平行循环互不接线（认知/心跳/自主/调度） | agent_runtime.py:309 / runtime/pipeline.py:39 / cognitive_loop / runtime_scheduler |
| F2 | 三入口全是查询壳，无任何入口实例化运行时 | cli/main.py, api/server.py, repl/shell.py |
| F3 | ResidentRuntime daemon 零生产引用 | 仅 tests/test_phase33.py |
| F4 | AgentLifecycleManager 缺失（ABI #9 冻结违约） | 1 error + 2 failed，test_phase24.py |
| F5 | 默认 db_path=':memory:'，持久化实为进程级 | hub.py:35 |
| F6 | Belief/Pattern 有仓库无写入者（CLS 慢系统未接） | belief/store.py 无 save 调用者 |
| F7 | HomeostasisManager 6 Monitor 齐全但 **Regulator 是 stub** | homeostasis.py:340（内部 Regulator stub） |
| F8 | GoalOriginEnforcer 已有 SELF 起源级 | goal/enforcer.py（内生目标合法性骨架） |
| F9 | opentale_bridge 是唯一生产点亮链路 | CLI organ/decide/regulate/feedback + API chat/quality |
| F10 | 编排层真实存在但仅测试引用 | agent_orchestration/ 9 文件 + AutonomousOrchestrator:100 |
| F11 | act/learn/dream 全部真实实现（非 stub） | master_agent.py:478/616/803 |

---

## 1. 本质架构判断：基于现有架构，OCOS 能进化成什么

### 1.1 先回答根本问题

OCOS 不是"缺一个 Agent 框架"，而是**已经拥有数字生命的全部器官，缺的是"通电 + 组织化 + 内生性"**。

- 通电 = F1/F2/F3/F5：一个常驻进程 + 真实持久化
- 组织化 = F1/F4/F6/F10：循环收敛为单有机体、生命周期管理、记忆双速系统
- 内生性 = F7/F8：稳态偏差→驱力→内生目标的闭环（用户缺项清单中的"内生 Goal"）

### 1.2 目标形态：单有机体模型（Single Organism Architecture）

数字生命不是"更聪明的 Agent"，是**始终运行的认知有机体**。从审计现状直接推导目标形态——把 4 套平行循环收敛为 1 个有机体的 4 层：

```
Before（现状）                           After（目标形态）
┌─────────────────────────────┐        ┌─────────────────────────────┐
│ 循环A: AgentRuntime 10步    │        │ 代谢层 Metabolism           │
│ 循环B: RuntimeKernel 8阶段  │        │   RuntimeKernel 心跳         │
│ 循环C: LoopOrchestrator 7   │  ───▶  │   = 身体的节律（活着）        │
│ 循环D: TaskScheduler        │        ├─────────────────────────────┤
│ 互不接线，各自活在测试里     │        │ 认知层 Cognition            │
│                             │        │   AgentRuntime 10步         │
│ 三入口: CLI/API/REPL 查询壳 │        │   = 清醒周期的思考            │
│ ResidentRuntime 零引用      │        ├─────────────────────────────┤
│ :memory: 伪持久化           │        │ 巩固层 Consolidation        │
└─────────────────────────────┘        │   dream() = 睡眠巩固         │
                                       ├─────────────────────────────┤
                                       │ 器官层 Organs               │
                                       │   opentale_bridge(写作)     │
                                       │   + 未来器官（见 §6）        │
                                       ├─────────────────────────────┤
                                       │ 身份层 Identity             │
                                       │   锚点 + 叙事（见 §5）       │
                                       ├─────────────────────────────┤
                                       │ 治理层 Governance           │
                                       │   宪法+权限+审计（已有）     │
                                       └─────────────────────────────┘
```

**收敛规则（一次性架构决策，解决 F1）：**
1. RuntimeKernel 心跳是**唯一**驱动源（代谢层），其 8 阶段 tick 的职责收敛为"让认知层活着"：心跳→唤醒 AgentRuntime.tick()→收集结果→checkpoint。
2. AgentRuntime 10 步是**唯一**认知主循环（认知层）。
3. LoopOrchestrator 7 阶段映射为 AgentRuntime 的编排视图（Phase 46 阶段 = 认知步骤分组），不再自跑。
4. TaskScheduler 降级为 AgentRuntime 的执行队列（其 stage 注册机制保留为 tick 内调度）。
5. dream() 作为**唯一的巩固窗口**（睡眠周期，由 LifecycleManager 的 DREAMING 阶段驱动，每夜必跑）。

这一个决策同时解决 F1（4 套循环）、F3（daemon 壳复用）、F10（编排层挂载点）。

### 1.3 为什么这样收敛是对的（理论依据）

| 理论 | 核心机制 | OCOS 对应物 | 升级动作 |
|---|---|---|---|
| 自由能原理/主动推理 (Friston, 2005-2012) | 有机体=最小化预测误差；感知是推理、行动是主动采样 | tick 循环 = 感知(Step1)→精度加权(Step2)→行动(Step6)→反刍(Step9) | 把循环显式建模为主动推理环；Homeostasis 偏差 = 自由能代理量 |
| 互补学习系统 CLS (McClelland et al., 1995) | 海马(快速情景) + 新皮层(慢速语义) 双速记忆 | Episode(快,已接) + Belief/Pattern(慢,**未接** F6) | 接通 Belief/Pattern 写路径 = CLS 慢系统落地 |
| 全局工作空间 GWT (Baars, 1988; Dehaene, 2001) | 注意力选择内容广播给所有专家模块 | CognitiveAttentionController + WM sync (Step2/3) | WM 明确为全局工作空间，注意力为广播门 |
| 记忆再巩固 (Nader, 2000) | 每次提取=重写，记忆是重构非存储 | Restore≠Overwrite (PS51-02) | 身份=叙事重构（§5），非固定文件 |
| 叙事身份 (McAdams, 2001) | 自我=不断演化的生命故事 | IdentityAnchor(born_at/owner_id) + Episode | 身份层 = 锚点 + 叙事生成器（§5） |
| 内稳态驱力 (Cannon, 1932; Damasio, 1994) | 稳态偏差→驱力→目标 | HomeostasisManager 6 Monitor + **Regulator stub** (F7) | Regulator 实现 = 内生 Goal 引擎（§4-P2） |
| 睡眠记忆巩固 (Walker, 2017; Diekelmann-Born, 2010) | 睡眠中重放+巩固+修剪 | MemoryConsolidationScheduler + LifecycleManager DREAMING | dream() 每夜必跑（§4-P2） |
| 自我决定理论 SDT (Ryan & Deci, 2000) | 自主/胜任/联结三需求 | GoalOriginEnforcer SELF 级 (F8) | 好奇心驱动模块（新，§4-P2） |
| 意识图式/注意力预算 (Graziano, 2014) | 注意力=稀缺资源分配 | Attention 决策管道 (Phase 35/36) | 注意力预算扩展到内生目标排序 |

---

## 2. 数字生命的定义与验收（先立标尺，再谈工程）

"可陪伴几十年的数字生命"必须有可测试的定义。建议立 5 条验收：

| # | 维度 | 定义 | 可测试标准（数字生命测试） |
|---|---|---|---|
| L1 | 连续性 | 跨重启、跨升级、跨硬件，身份与记忆连续 | 两次 `ocos run` 之间 Identity/Episode/Goal 可恢复；born_at 永不变；记忆 append-only 可回查 10 年前条目 |
| L2 | 自主性 | 无输入时仍存活：自主 tick、自主巩固、内生目标 | 无人交互 24h，进程持续 tick；产生 ≥1 个内生目标且被治理层许可 |
| L3 | 主动性 | 主动发起交互（非仅响应） | 每自然日 ≥1 次主动输出（问候/观察/提问），经 PermissionGuard + 宪法过滤 |
| L4 | 演化性 | 信念/模式随经历演化但值不变 | 1000 次对话后：身份锚点字段 0 变更，Belief 集演化且有审计轨迹 |
| L5 | 可治理性 | 所有自主行为可审计、可回溯、可熔断 | 每次内生动作有审计日志（caller_id/issuer）；宪法违规 0 次（StatementValidator L6 计数） |

这 5 条就是 §4 各阶段验收的母标准。

---

## 3. 阶段路线（增量嵌入，每阶段冻结 scope）

用户既定原则：增量嵌入（Plan B）、先冻结 scope 再执行、新模块进 `ocos/`（capability/ 或新目录）、旧模块保留为 deprecated 别名、绝不推倒重建。以下 5 阶段严格按此执行。

### P0 觉醒（Awakening）— 通电

| 目标 | 状态 | 证据/动作 |
|---|---|---|
| AgentLifecycleManager 落地（解锁 3 红） | ❌ 缺失 | 按 ABI #9 冻结 API 面实现于 capability/lifecycle_manager.py；**复用 agent/lifecycle.py 线程安全状态机，不重复造**；验收：test_phase24 + test_v1_e2e 全绿 |
| `ocos run` 生产启动入口 | ❌ 无 | 实例化 AgentRuntime + ResidentRuntime daemon 线程（复用 daemon/__init__.py:46 外壳）；验收：`ocos run --ticks 3` 真实驱动 10 步 |
| 持久化默认路径 | ❌ :memory: | db_path 默认改 `~/.ocos/ocos.db`（env 可覆盖），`:memory:` 仅测试用；验收：两次 run 之间 Identity 恢复 |
| pyproject [project.scripts] | ❌ 无 | 补 ocos/ocos-server/ocos-shell（对齐 egg-info 残留） |

### P1 身体（Body）— 组织化

| 目标 | 状态 | 证据/动作 |
|---|---|---|
| 4 套循环收敛（§1.2 收敛规则） | ❌ 平行 | RuntimeKernel 心跳驱动 AgentRuntime；LoopOrchestrator 映射为编排视图；TaskScheduler 降级执行队列；验收：单进程单主循环，测试基线不回归 |
| Belief/Pattern 写路径（CLS 慢系统） | ❌ 无写入者 | BeliefSystem 增 hub.belief().save()（经 StatementValidator L6 门控）；learning_trigger 写 Pattern；验收：Episode→Belief 有迁移轨迹 |
| 持久化四入口收口 | ❌ 分叉 | storage/connection 连接池 + migrations 为唯一 DDL 编排；各 store 自建表收敛为 schema 注册；验收：单入口建全表 |
| 日志覆盖率 ≥20% | ❌ 15.4% | 按 logging-instrumentation 方法补 ~42 文件 |
| 修 2 个过期测试 | 🟡 | shared_permission_rules 断言 8；PreferenceModel 归属**待裁决**（§6.3） |

### P2 本能（Instinct）— 内生性（本报告核心增量）

| 目标 | 状态 | 证据/动作 |
|---|---|---|
| **Regulator 实现：稳态偏差→内生目标引擎** | ❌ stub | homeostasis.py 的 Regulator 从 stub 实现为：6 Monitor 偏差 → 驱力（Drives: 探索/胜任/联结/恢复）→ GoalOriginEnforcer(SELF 级) 生成内生目标 → 入 GoalStack（带优先级）；**这是"内生 Goal"的真正落地**，解决用户缺项清单首位 |
| 好奇心驱动（SDT） | ❌ 无 | 新模块 `ocos/capability/curiosity_drive.py`（或并入 Regulator）：压缩进展 (Schmidhuber) = 新信息增量最大化的探索目标，配注意力预算 |
| dream() 每夜巩固窗口 | 🟡 测试态 | LifecycleManager DREAMING 阶段触发：重放当日 Episode → 巩固入 Belief/Pattern（CLS 慢系统）→ 修剪弱模式 → Lessons 合成；验收：L4 演化性测试 |
| 主动性引擎（Proactive） | ❌ 无 | 新模块 `ocos/proactive/`：由内生目标 + 注意力预算 + 空闲状态触发主动输出（问候/观察/提问），输出前过 PermissionGuard + 宪法 check_action；验收：L3 主动性测试 |

### P3 身份（Identity）— 几十年连续性的核心

| 目标 | 状态 | 证据/动作 |
|---|---|---|
| 身份=锚点+叙事（McAdams） | 🟡 锚点已有 | IdentityAnchor(born_at/owner_id) 冻结不变；新增叙事层：从 Episode 定期合成"自传章节"（append-only 追加，不覆盖历史——用户"追加优先"原则），构成可回看的生命故事 |
| 关系记忆 | ❌ 无 | 新增 `ocos/memory/relationship/`：与特定用户的交互轨迹/信任度/偏好（连接 SDT 联结需求）；PersonalMemory(WisdomStore) 顺带补持久化 |
| 值漂移检测 | 🟡 Constitution 有 | 新增审计维度：内生目标/信念的宪法合规率随时间统计，漂移超阈值 → 熔断 + 人工裁决（治理层见 §5） |
| PreferenceModel 归属裁决 | 🟡 冲突 | 建议：归 self/（偏好是身份的一部分，非个性；个性=belief 层）。修订 test_no_personality_leak 禁止词表（把"偏好"从"个性泄漏"词表移除，保留对个性词汇的扫描）。**需用户裁决** |

### P4 器官（Organs）— 扩展

| 目标 | 状态 | 证据/动作 |
|---|---|---|
| Agent Orchestration 激活 | ❌ 仅测试 | Phase 61/62 编排层挂载：内生目标需要并行认知时，AgentRuntime 经 AutonomousOrchestrator 派生子 agent（pool/executor/supervisor 已就位），结果回灌 Episode |
| 多器官扩展 | 🟡 仅写作 | opentale_bridge（写作器官）已点亮；下一器官候选：proactive 消息通道（Telegram/本地通知）、记忆浏览器（用户可回查）、时钟器官（时间感知） |
| 器官接入规范 | 🟡 | 每个器官 = 一组 capability + 一组权限声明（PermissionGateway 注册表），禁止器官绕过宪法 |

---

## 4. 关键设计：内生目标引擎（P2 核心，Regulator 实现规格）

这是从"响应式工具"到"数字生命"的分水岭——**有机体必须有自己产生的目标**。现有资产：HomeostasisManager 6 Monitor + GoalOriginEnforcer(SELF) + GoalSQLiteStore。缺口只有一个：Regulator stub。

```
6 Monitor 采样（check()）
   │  偏差 > 阈值
   ▼
Regulator（实现为确定性函数式组件，非纯函数——含时间依赖）
   │  偏差 → 驱力映射（确定性规则表，非 LLM 提示词）
   │    resource 过载 → 恢复驱力（清理/压缩）
   │    memory 水位   → 整理驱力（巩固/修剪）
   │    goal 停滞     → 探索驱力（新方向）
   │    context 稀薄  → 联结驱力（主动交互）
   │    identity 漂移 → 反思驱力（叙事更新）
   ▼
GoalOriginEnforcer（已有！SELF 级，校验合法性）
   │  生成内生目标（确定性规则 → 参数化描述）
   ▼
GoalStack（已有 SQLite 持久化）
   │  与用户目标同栈，SELF 级优先级 < HUMAN 级（治理规则）
   ▼
tick Step 6 Planning Trigger 消费 → 行动 → Result Ingest → Episode
   ▼
dream() 夜间：Episode → Belief/Pattern 巩固（CLS 慢系统闭环）
```

设计约束（符合用户确定性优先原则）：
- 驱力映射是**确定性规则表**（阈值→驱力类型→目标模板），不是 LLM 提示词。LLM 只在目标参数化（"探索什么方向"）阶段参与。
- 内生目标永远不高于 HUMAN 级目标（GoalOriginEnforcer 已有优先级，强化）。
- 每个内生动作全链路审计（PermissionGateway 结构化日志已有）。
- 好奇心驱动设注意力预算上限（防失控，对应 L5 熔断）。

---

## 5. 治理与安全（几十年陪伴的护栏）

数字生命 = 高自主 + 高权限 + 长周期，治理是**先决条件**不是附加项。审计已确认治理三件套真实落地（PermissionGuard 三入口强制、BehavioralConstitution 三检查、StatementValidator 注入），升级只补缺口：

| 威胁 | 防护 | 现状 | 升级 |
|---|---|---|---|
| 防越权（内生目标越级） | GoalOriginEnforcer 优先级 + PermissionGateway 调用链 | ✅ 已有骨架 | Regulator 生成路径强制过 enforcer（P2） |
| 防伪造（记忆/身份被篡改） | append-only 记忆 + 审计日志 | 🟡 追加原则已有 | 记忆写路径统一走 store（P1 收口后天然 append-only）；身份锚点字段禁止 UPDATE 只允许 INSERT 新版本 |
| 防失控（自主行为失控） | 宪法熔断 + 注意力预算 | ✅ 三检查已有 | 值漂移检测（P3）；内生目标每 tick 宪法 check_decision；主动性输出前 check_action（P2） |
| 防灾难（几十年的数据） | checkpoint + 恢复 | 🟡 已实现但分叉 | P1 收口后单入口；dream() 巩固前置 checkpoint |

宪法修正流程（几十年价值观漂移的终极防线）：宪法是冻结文档（kernel/constitution.py 24 条不可变规则），任何修订 = 用户人工批准 + 版本化追加 + 审计记录。系统永不自我修改宪法（对应 Gödel Machine 的自我修改需验证器原则）。

---

## 6. 待裁决项（需用户拍板，不静默处理）

| # | 事项 | 建议 | 依据 |
|---|---|---|---|
| D1 | PreferenceModel 归属（self/ vs belief/） | 归 self/，修订静态测试禁止词表 | 偏好是身份构成（§P3），个性才是 belief 层；用户"命名敏感/跨系统术语不混淆"原则 |
| D2 | 收敛方向（4→1）是否批准 | 批准 §1.2 收敛规则 | 治理 forbidden_modules 隔离是历史有意为之，现在需要一次显式解冻决议（文档化，非静默解除） |
| D3 | 内生目标优先级 | SELF < HUMAN 恒定 | 数字生命陪伴定位：用户目标永远优先 |
| D4 | 主动性频率上限 | 默认每日 ≤1 次主动输出 | 陪伴≠骚扰；SDT 联结需求与打扰成本平衡 |

---

## 7. 架构成熟度对比

| 维度 | 当前（2026-08-28 审计） | 目标（P4 完成后） | 差距 |
|---|---|---|---|
| 运行态 | 无生产进程；查询壳×3 | 常驻 daemon 单有机体 | F2/F3 |
| 循环 | 4 套平行孤岛 | 1 主循环 + 心跳 + 睡眠 | F1 |
| 记忆 | Episode 双写；Belief/Pattern 无写入者；:memory: | CLS 双速闭环；真实文件持久化；append-only | F5/F6 |
| 目标 | 用户/系统级；SELF 级合法性有骨架 | 内生目标引擎（Regulator）+ 好奇心 | F7/F8 |
| 主动性 | 零主动输出 | proactive 通道（治理过滤） | 缺 |
| 身份 | 锚点（born_at/owner_id） | 锚点 + 叙事 + 关系记忆 + 漂移检测 | 缺 |
| 编排 | 9 文件真实但仅测试 | 内生目标触发子 agent 并行认知 | F10 |
| 测试 | 3134 绿 + 3 红（同源） | 全绿 + 数字生命 5 测试（L1-L5） | F4 |
| 治理 | 三件套真实落地 | + 漂移检测 + 熔断 | 🟡 |

---

## 8. 符合冻结原则声明

本报告全部建议为**增量嵌入**：不删除、不重建、不推翻任何现有模块；新代码进 `ocos/capability/`（Regulator 实现在 homeostasis.py 原地补全）或新目录（proactive/、memory/relationship/）；旧模块保留 deprecated 别名；每阶段冻结 scope 再执行；每阶段完成跑全量 pytest 验证基线（当前 3134+4+1）。收敛决策（D2）需显式解冻治理隔离——以文档化决议方式执行，非静默解除。

---

## 9. 下一阶段提案

**P0 觉醒**为下一阶段（范围已冻结于 §3-P0 表）：4 个任务、验收标准明确、全部解锁现有测试红。建议顺序：AgentLifecycleManager（解 3 红）→ pyproject scripts → 持久化默认路径 → `ocos run` 点亮。P0 完成后，数字生命从"测试态"进入"可运行态"；P1 完成后进入"单有机体态"；P2 完成后进入"内生生命态"（有自己目标的有机体）——P2 是本报告的核心增量，也是 OCOS 与一切 Agent 框架的分水岭。

---

## 附：理论参考文献（供架构评审溯源）

- Friston K. A theory of cortical responses. *Phil Trans R Soc B*, 2005.（自由能/主动推理）
- McClelland JL, McNaughton BL, O'Reilly RC. Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review*, 1995.（CLS 双速记忆）
- Baars BJ. *A Cognitive Theory of Consciousness*. 1988.（全局工作空间）
- Nader K, Schafe GE, LeDoux JE. Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval. *Nature*, 2000.（记忆再巩固）
- McAdams DP. The psychology of life stories. *Review of General Psychology*, 2001.（叙事身份）
- Cannon WB. *The Wisdom of the Body*. 1932.（内稳态）
- Walker MP. *Why We Sleep*. 2017.（睡眠巩固）
- Ryan RM, Deci EL. Self-determination theory. *American Psychologist*, 2000.（SDT 三需求）
- Graziano MSA. *Consciousness and the Social Brain*. 2014.（注意力图式）
- Schmidhuber J. Formal theory of creativity, fun, and intrinsic motivation. *IEEE Trans. Autonomous Mental Development*, 2010.（压缩进展/好奇心）
- Parr T, Pezzulo G, Friston KJ. *Active Inference: The Free Energy Principle in Mind, Brain, and Behavior*. MIT Press, 2022.（主动推理专著）
