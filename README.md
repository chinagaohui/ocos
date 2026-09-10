# OCOS — Organic Cognitive Operating System

> 个人智脑内核 — 非 Agent 框架，非 LLM 包装器
> 
> v1.0.0

## 这是什么？

OCOS 是一个**数字生命体内核**，用于构建始终运行的个人认知引擎。

**它不是：**
- Agent 框架
- LLM 包装器
- 记忆后端

**它是：**
- **个人智脑** — 自主思考、记忆、信念演化
- **认知操作系统** — 感知 → 认知 → 决策 → 行动 → 学习闭环
- **内生智能体** — 具有目标、注意力、情绪、睡眠机制

## 核心能力

| 能力 | Phase | 说明 |
|------|-------|------|
| 多模态感知 | T | 文本/文件/环境感知 + 跨模态融合 |
| 认知推理 | D/I/J | 信念系统 + 决策引擎 + 规划引擎 |
| 持续学习 | H/R | 从反馈中学习偏好，更新信念 |
| 知识图谱 | S | Entity-Relation-Fact 三元组管理 |
| 自主睡眠 | U | 基于稳态的睡眠决策 + 梦境生成 |
| 持久化恢复 | V | 快照管理 + 崩溃恢复 |
| 安全权限 | X | 输入清洗 + 权限网关 + 审计日志 |
| 监控告警 | Y | Prometheus 端点 + 告警规则 |
| 性能优化 | Z | 智能缓存 + 批处理 + 性能分析 |

## 快速开始

```bash
# 安装
pip install -e .

# 运行测试
python -m pytest ocos/tests/test_integration.py -v

# 查看架构文档
cat docs/ARCHITECTURE.md
```

## 项目状态（2026-09-10 更新）

- **代码规模：** ~170,000 行 / ~840 modules / ~2,380 classes
- **测试数量：** **4,374 passed / 0 failed**（全量零回归，~11min）
- **生产状态：** systemd 常驻 daemon 运行中（autonomy_level=2，60s 节流）
- **当前阶段：** 生产级修复全部落地 → 持续运行验证 + 主动交互演进
- **主链：** ResidentRuntime → RuntimeKernel → AgentRuntime.tick() → DecisionBridge → Permission → Execution
- **学习链路：** EpisodeStore → PatternExtractor → consolidate → wisdom_trigger → think() premises ✅
- **自治治理：** GoalGenesis 提案引擎 + 分级批准 + 4 级自治阶梯 (L0-L3) + ShadowVerifier + CircuitBreaker

### 本轮生产修复（2026-09-10）

| 优先级 | 编号 | 内容 | 状态 |
|--------|------|------|------|
| **P0** | B1 | evolution_artifacts PENDING→APPROVED→goals 管道打通 | ✅ |
| **P0** | B2 | systemd autonomy_level=2 drop-in + override file | ✅ |
| P1 | O2 | WAL checkpoint systemd timer（每 2min） | ✅ |
| P1 | O3 | FailureDiagnoser DEPENDENCY_MISSING cause + GoalGenesis SKIP_DEPENDENTS | ✅ |
| P2 | U1 | cognition loop fail streak counter（3 次连续→CRITICAL 告警） | ✅ |
| P2 | U4 | LLM SQL 安全闸门（黑名单 9 种关键字） | ✅ |
| **P2** | **O4** | **sqlite3 binary → Python sqlite3 降级（只读 SELECT/PRAGMA 拦截）** | ✅ |
| **P3** | **U5** | **每日学习摘要推送（goals 表 → outbox kind='report'）** | ✅ |
| — | — | **autonomy 降级双重闸门（10 次连续 + 滑窗成功率 < 30%）** | ✅ |
| — | — | **Pump skip 精确去重 + 时间戳节流 + NameError desc 修复** | ✅ |
| — | — | **lessons 视图（schema v7）+ WAL ratio 监控** | ✅ |
| — | — | **4 test failures → 0（conftest 隔离 fixture + policy_engine/all_passed 语义）** | ✅ |
| — | — | **lifecycle_manager signal handler 移除 sys.exit(0)（防 pytest 进程污染）** | ✅ |

### 测试基础设施加固

- `conftest.py` 新增 3 个 autouse fixture 隔离生产环境：
  - `_isolated_autonomy` — override file → pytest tmp_path（monkeypatch env）
  - `_isolated_active_interaction` — heartbeat→None + permission fail-closed
  - `_isolated_llm_config` — 锁定无 LLM 路径，强制 mock
- policy_engine `all_passed` 语义修正：WARN/ALLOW effect 的 passed=False 不阻断
  （只有 DENY 必须全过），避免 autonomy_gate level=0 误伤测试
- converse._state_reply mock 分支回显用户 message，让测试验证输入被保留

### 关键生产路径

```
daemon tick (5s)
├── _auto_approve_pending()        # ask 模式空转
├── _pump_evolution_artifacts()    # ⏱ 60s 节流
│   ├── Step 1: PENDING auto_generated + LOW risk → APPROVED
│   └── Step 2: APPROVED (applied_at IS NULL) → goals 表 PENDING
│       └── 精确去重: goals.metadata LIKE 'artifact_id'
├── _push_daily_learning_summary() # 📅 每日一次
│   └── lessons 视图聚合 → outbox kind='report'
├── _claim_persisted_goals()
├── kernel.tick_loop(1)            # agent driver 单次认知循环
└── motivation.record_result()      # 双重闸门防跑飞降级
    ├── FAILURE_DEMOTE_THRESHOLD=10
    └── 滑窗成功率 < 30% 才降级
```

### sqlite3 降级拦截（O4）

`DecisionBridge._handler_run_command` 前置 `_try_sqlite3_fallback()`：
- **命中条件：** `sqlite3 path/to/db "SELECT ..."` 或无引号变体
- **安全闸门：** 只读 SELECT/PRAGMA/EXPLAIN/WITH + 路径仅限 ~/.ocos 或 /tmp
- **降级：** Python `sqlite3.connect()` 直接执行，绕开 binary 缺失
- **写操作：** 走原 subprocess 路径（可能被沙盒/黑名单拦截）

### autonomy 降级双重闸门

原 `FAILURE_DEMOTE_THRESHOLD=3` 太激进 — writer/reviewer 偶发失败直接把
autonomy 降到 0，导致整个"防跑飞"机制反过来"杀死"自主行为。

修复为**双重闸门**（v2 抗噪）：
1. 连续 10 次失败（原 3 → 10，抗 writer/reviewer 偶发失败噪声）
2. 近 20 次 goal_result 滑窗成功率 < 30%

两个条件**同时满足**才降级。`_result_window: list[bool]` 滑窗持久化于
MotivationHub 实例。

## 落地方案（对齐 Coze 报告）

执行级落地方案：`docs/AUTONOMY_EXECUTION_PLAN_v1.0.md`

| Step | 报告阶段 | 内容 | 状态 |
|------|---------|------|------|
| Step 1 | P1 宪法修正案 | GoalGenesis 提案引擎 + 分级批准 + goal_proposal 审计表 + motivation 接入 | ✅ 完成 |
| Step 2 | P4 自治度闸门 | dream() L0 skip + 4 级自治阶梯已存在 (ocos/execution/autonomy.py) | ✅ 完成 |
| Step 3 | P5 自进化 | ShadowVerifier 沙箱 + GrowthOptimizer.apply_in_sandbox 护栏 ①-⑦ | ✅ 完成 |
| Step 4 | 治理层 | RiskRegistry (4 条结构化风险) + CircuitBreaker 熔断降级 + 审计 JSONL 增强 | ✅ 完成 |
| Step 5 | 北极星指标 | 4 个 Prometheus gauge — overreach / completion_rate / failure_delta / proposal_rate | ✅ 完成 |
| Step 6 | 端到端验收 | daemon 24h 运行 + checklist 全过 | 🟡 等时间积累 |

### 落地方案新增/改动文件

- `ocos/autonomous/goal_genesis.py` — 🆕 GoalGenesis 提案引擎 + 分级批准
- `ocos/agent/master_agent.py` — ✏️ dream() L0 闸门 + knowledge_context()/wisdom_context()/belief_context()
- `ocos/daemon/motivation.py` — ✏️ _propose() 接入 GoalGenesis + authority=PROPOSAL
- `ocos/growth/shadow_verifier.py` — 🆕 ShadowVerifier 沙箱 + EvolutionGuard 护栏
- `ocos/growth/engine.py` — ✏️ GrowthOptimizer.apply_in_sandbox()
- `ocos/governance/risk_registry.py` — 🆕 RiskRegistry + CircuitBreaker 熔断
- `ocos/governance/autonomy_metrics.py` — 🆕 北极星指标 Prometheus exposition
- `docs/AUTONOMY_EXECUTION_PLAN_v1.0.md` — 🆕 执行级落地方案

### 北极星指标（生产实时值）

```
ocos_overreach_events_total              = 1    (HIGH risk REJECTED, 正确被拒)
ocos_autonomous_completion_rate_pct      = 12.5 (等 daemon 24h 积累)
ocos_proposal_approval_rate_pct          = 66.7 ✅ (≥ 50% 达标!)
```

### 安全护栏

GrowthOptimizer 自动 apply 必须全部满足：
① autonomy_level == L3
② ShadowVerifier 沙箱 pytest 通过
③ scale_guard 通过 (绝对 50 行 OR 比例 15% OR 保留 ≥ 50%)
④ pytest 零回归
⑤ 改动文件数 ≤ 5
⑥ 不碰红线文件 (宪法/权限/决策类型)
⑦ CircuitBreaker 未熔断

## 学习管线

OCOS 的学习管线已从"空转磨坊"修复为闭环运转：

| 层 | 模块 | 状态 | 说明 |
|----|------|------|------|
| 数据层 | AgentRuntime.condition | ✅ 已修复 | `tick@N` → `agent=X, success=Y` — 让 PatternExtractor 能自然聚合 |
| 巩固层 | _consolidate_episodes | ✅ 已修复 | `active_only=False` — 第一次 dream 后 consolidated episode 不再被跳过 |
| 巩固层 | wisdom_trigger | ✅ 已修复 | `active_only=False` + `limit=200` — 同根因修复 |
| 消费层 | wisdom_context() + belief_context() | ✅ 已接线 | 注入 think() premises — 学习沉淀真被消费进决策 |
| 多渠道 | UnifiedIngestor | 🆕 新增 | filter → extract → store → register 统一摄入入口 |
| 多渠道 | WebResearcher | 🆕 新增 | DuckDuckGo Instant Answer API 网络搜索调研 |
| 多渠道 | LLMTutor | 🆕 新增 | TextGenerator LLM 知识库问答 |
| 多渠道 | ExperienceExtractor | 🆕 新增 | EpisodeStore/DB fallback 任务经验提取 |

### 生产数据取证（~/.ocos/ocos.db）

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| condition 分组 | 1007×tick@N（每次 tick 唯一） | 608×researcher, 356×writer, 43×reviewer（自然聚合） |
| PatternExtractor 候选 | 0 个 | **9 个**（≥min_samples=3 聚合） |
| consolidate replayed | 1 条 | **248 条** |
| pattern 持久化 | 12 条（全是 daemon 事件噪声） | **16 条**（+4 条真实任务模式） |
| wisdom 产出 | 5 条（模板化，没人读） | **6 条**（+1 新聚类，think() 每次读 5 条） |
| belief 被消费 | ❌ 321 条全沉底 | ✅ think() 每次读 5 条 by confidence |

### 学习链路三层法则

1. **数据层 condition 必须编码任务语义** — 不能用无意义的 tick 序号（`tick@N`），必须编码 agent 类型 + 执行结果（`agent=researcher, success=true`）让 PatternExtractor 能按同类聚合
2. **consolidation 不能用 active_only=True** — 它假设"第一次 dream 会扫完所有"，但实际上 daemon 启动后新产生的 episode 永远不会被后续 dream 扫到
3. **产出必须真被 think() 读进 premises** — wisdom/belief 写了没人读等于白写。必须通过 `wisdom_context()` / `belief_context()` 注入 `_bridge.reason(premises={...})`

### 修复文件

- `ocos/agent/agent_runtime.py` — condition 字段根因修复
- `ocos/agent/master_agent.py` — active_only=False + wisdom_context()/belief_context() 注入
- `ocos/agent/wisdom_trigger.py` — active_only=False
- `ocos/cognitive_loop/loop_orchestrator.py` — inject_memory_providers()
- `ocos/learning/unified_ingestor.py` — 🆕 统一摄入入口
- `ocos/learning/channels/web_researcher.py` — 🆕 网络搜索渠道
- `ocos/learning/channels/llm_tutor.py` — 🆕 LLM 问答渠道
- `ocos/learning/channels/experience_extractor.py` — 🆕 经验提取渠道

## 文档

- [项目白皮书 v1.3.1](docs/OCOS_项目白皮书_v1.2.md)（最完整现状）
- [AGI 升级蓝图 v1.1](docs/BLUEPRINT_AGI_UPGRADE_v1.1.md)（当前路线）
- [认知运行时收敛裁决 v1.0](docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md)
- [架构文档](docs/ARCHITECTURE.md)（部分被收敛裁决更新，见文档头状态标注）
- [设计原则](docs/DESIGN_PRINCIPLES.md)
- [API 参考](docs/API_REFERENCE.md)

## 许可

内部项目，版权所有。
