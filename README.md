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

## 项目状态（2026-09-09 更新）

- **代码规模：** ~168,000 行 / ~825 modules / ~2,370 classes
- **测试数量：** 4,366 passed（baseline 零回归）
- **生产状态：** systemd 常驻 daemon 运行中（cycle 持续增长），行为级验收全绿
- **当前阶段：** 学习管线闭环修复完成 → 多渠道外部学习就绪
- **主链：** ResidentRuntime → RuntimeKernel → AgentRuntime.tick() → TaskDAG → DecisionBridge → Permission → Execution
- **学习链路：** EpisodeStore → PatternExtractor(condition=agent=X,success=Y) → consolidate → wisdom_trigger → wisdom_context()/belief_context() → think() premises ✅ 全链路打通

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
