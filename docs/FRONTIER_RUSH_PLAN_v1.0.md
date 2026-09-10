# OCOS 第一梯队冲击方案 v1.0

> 当前排位: **第二梯队上沿 / 准第一梯队**
> 目标排位: **第一梯队** (对标 Google Project Astra / Oasis by Decagon)
> 落地方案: 3 个月, 4 个阶段, 5 个优先级

---

## 当前核心瓶颈 (按致命度排序)

| # | 瓶颈 | 现状 | 为什么致命 |
|---|------|------|----------|
| **1** | 知识抽取率 1:36 | episodes=2186 → knowledge=60, 97% 经验被浪费 | 知识层是数字生命的"大脑皮层"——**没有足够知识就没有真正的智能** |
| **2** | 抽象层严重偏斜 | procedure=44 vs principle=2 (22:1) | 系统只会"怎么做"不会"为什么"——**没有 principle 就没有真正的自进化方向性** |
| **3** | 自进化实证不足 | wisdom active=1, goal_proposal n=4 | L4 架构是"设计"不是"已验证的能力" |
| **4** | 目标供给断档 | goals active=0, completed=264 | daemon 在空转——**没有目标就没有新经验, 没有新经验就没有新知识** |
| **5** | 单点依赖 | DeepSeek 单一 LLM, DuckDuckGo 单一搜索 | 模型挂了 = 思考停转 |

**关键洞察: 瓶颈是「运行规模 + 提取效率」, 不是「架构缺失」。不要再加新模块。**

---

## 阶段 1 (P0+P4, 第 1-2 周) — 止血: 让系统有活干

### P4-1: 目标供给引擎

**问题**: goals active=0 但 daemon cycle 在跑 → 空转。
**根因**: GoalGenesis 提案生成速率 < completion 速率 → active 队列耗尽。

**方案**:
- 查 GoalGenesis._propose() 频率 (motivation daemon tick 多久触发一次)
- GoalGenesis 提案优先级策略: 主动"挖坟"——从历史 completed goal 中找未覆盖的方向, 生成 follow-up goal
- 注入长期 HUMAN goal: "每日深度学习认知架构/Agent/数字生命相关主题, 沉淀知识到 knowledge 表" (已经做了, 但 active=0 说明 goal 被标记 completed 太快)
- **验收**: goals active > 3 且持续增长, daemon 不再空转

**文件**: `ocos/daemon/motivation.py` (GoalGenesis._propose 频率), `ocos/daemon/__init__.py` (HUMAN goal follow-up 注入)

### P4-2: daemon 空转检测 + 自动重启

**问题**: autonomy 被自己降级到 L0 (之前出现过, motivation consecutive_failures >= 3)
**方案**: daemon 心跳里加 `consecutive_empty_cycles` 计数, 超过阈值 → 自动 inject 新 goal + 重置 motivation failure 计数
**文件**: `ocos/daemon/__init__.py` tick_loop

---

## 阶段 2 (P1, 第 2-4 周) — 提效: 知识抽取率从 1:36 → 1:10

### P1-1: ExperienceExtractor 多级抽象

**问题**: 当前经验抽取只做 episode → pattern (表层), 不做 pattern → principle (抽象层)。
**方案**:
- ReflectionEngine 已经会给 deepen_topics (值得深入的方向), 但没人用它做抽取
- 在 consolidation pipeline 加 "Layer-2 抽象": pattern → principle, 用 LLM 把多个相关 pattern 归纳成一条 principle 知识
- 用 ReflectionEngine 的 `deepen_topics` 作为抽取种子 (ReflectionEngine 已经把 deepen_topics 写 reflection_seed_topics, 但 EpistemicDrive 只消费不用于抽取)
- **验收**: knowledge:episodes 从 1:36 → 1:15 以内, principle:procedure 从 1:22 → 1:8 以内

**文件**: `ocos/agent/master_agent.py` dream() consolidate step 3.5, `ocos/learning/unified_ingestor.py` 抽取层

### P1-2: principle 专项注入

**问题**: principle=2 太少, 系统没有"为什么"层知识。
**方案**:
- LLMTutor 渠道增加 principle 专项问答: 对每个 pattern cluster 自动问 "这个 pattern 背后的原理是什么?" → 沉淀为 principle
- 每日自进化循环里增加 principle 专项步骤
- **验收**: principle 从 2 → 15+

### P1-3: knowledge deduplication + confidence calibration

**问题**: 60 条 knowledge 里可能有重复 (同一件事被不同渠道摄入多次, 只是表述不同)
**方案**: ingestion pipeline 末尾加 deduplication (semantic similarity threshold), 重复的不存但更新已有条目的 confidence
**验收**: knowledge 增长速率稳定, 不因为重复摄入虚增

---

## 阶段 3 (P0, 第 4-10 周) — 跑量: 自进化实证

### P0-1: 让 daemon 持续运行 7-14 天

**这是 P0, 不需要写代码, 但需要保证 daemon 不 crash。**

**操作**:
```bash
systemctl --user enable ocos-daemon   # 确保开机自启
journalctl --user -u ocos-daemon -f  # 持续观察 daemon 健康
# 每天跑一次状态快照:
python3 -c "from ocos.benchmark_snapshot import daily_snapshot; daily_snapshot()"
```

**验收目标** (7 天后):
- wisdom active: 1 → 10+ (至少一个 consolidate cycle 把 candidate 升级成 active)
- goal_proposal: 4 → 30+
- knowledge: 60 → 200+
- episodes: 2186 → 5000+

**验收目标** (14 天后):
- wisdom active: 1 → 25+
- goal_proposal: 4 → 80+
- knowledge: 60 → 500+
- overreach 仍 = 1 (护栏有效, 没有越权)
- completion_rate ≥ 90%

### P0-2: wisdom 质量评估

**问题**: wisdom candidate=7 但 active=1, 说明 candidate→active 的转换条件太苛刻 (confidence 阈值?)
**方案**: 查 wisdom_trigger.py active_only 逻辑 + 放宽 candidate→active 阈值 (当前可能需要太多 pattern supporting)
**文件**: `ocos/agent/wisdom_trigger.py`

### P0-3: 进化产物质量指标

**问题**: proposal_approval 100% 但可能只是因为样本量小 (n=4)
**方案**: 建立三个量化指标:
1. `wisdom_utilization_rate` = wisdom 被后续 dream consolidation 引用次数 / wisdom 总数
2. `proposal_aftermath_rate` = proposal approved 后目标达成率
3. `knowledge_retention_rate` = knowledge 30 天后仍被引用的比例

---

## 阶段 4 (P2+P3, 第 10-12 周) — 拉满: 自治 + 去单点

### P2: 自治等级 L2 → L3

**前提**: P0 完成 (自进化实证 ≥ 14 天, wisdom active ≥ 25) + P1 完成 (knowledge:episodes ≤ 1:15)

**方案**:
- 扩展 L3 权限: 允许 GrowthOptimizer 在 ShadowVerifier + CircuitBreaker 双过闸后自动 apply 低风险代码改动
- 建立 `risk_assessment_framework`: 改动类型 × 影响范围 × 护栏通过率 → 自动决策能不能升 L3
- 回滚机制: apply 后 pytest 失败 → 自动 revert
- **验收**: L3 启动后 7 天内, GrowthOptimizer 自动 apply ≥ 3 次成功, 零 revert

### P3: 去单点依赖

**LLMTutor 多模型路由**:
```
TextGenerator.generate(prompt)
  ├─ PRIMARY: DeepSeek (当前主模型)
  ├─ FAILOVER_1: Ollama 本地模型 (qwen2.5:7b 或 deepseek-r1:8b)
  └─ FAILOVER_2: 另一个 API provider
```
**WebResearcher 多源**: DuckDuckGo + Wikipedia + arXiv

---

## 验收指标看板 (每月审计)

| 指标 | 当前 | P2 阶段末 | P4 阶段末 | 第一梯队门槛 |
|------|------|----------|----------|------------|
| knowledge 总数 | 60 | 200 | 500 | 1000+ |
| knowledge:episodes | 1:36 | 1:15 | 1:10 | 1:8 |
| principle:procedure | 1:22 | 1:8 | 1:5 | 1:3 |
| wisdom active | 1 | 10+ | 25+ | 50+ |
| goal_proposal 累计 | 4 | 30+ | 80+ | 150+ |
| overreach_events | 1 | ≤3 | ≤5 | ≤10 |
| completion_rate | 98% | ≥92% | ≥90% | ≥85% |
| proposal_approval_rate | 100% | ≥70% | ≥50% | ≥40% |
| autonomy_level | L2 | L2 | L3 | L3 |
| daemon uptime | 手动 | ≥7d | ≥14d | ≥30d |

---

## 执行清单

### 阶段 1 (第 1-2 周) — 止血

- [ ] **M1** 查 GoalGenesis 提案频率, 修复 goal 供给断档 (active=0)
- [ ] **M2** daemon 空转检测 + 自动 inject goal + 重置 failure
- [ ] **M3** 确保 daemon systemd 开机自启, 日志持久化

### 阶段 2 (第 2-4 周) — 提效

- [ ] **M4** consolidation 加 Layer-2 抽象: pattern → principle
- [ ] **M5** LLMTutor principle 专项问答, 每日自进化增加 principle 步骤
- [ ] **M6** knowledge deduplication + confidence calibration

### 阶段 3 (第 4-10 周) — 跑量

- [ ] **M7** 让 daemon 跑 7-14 天 (不用写代码, 只需要观察)
- [ ] **M8** 修 wisdom candidate→active 阈值
- [ ] **M9** 建立 3 个进化产物质量指标 + 每日快照脚本

### 阶段 4 (第 10-12 周) — 拉满

- [ ] **M10** 自治 L2→L3 升级 (风险分级 + 回滚机制)
- [ ] **M11** LLMTutor 多模型路由 + Ollama 本地兜底
- [ ] **M12** 每月审计脚本自动化

---

## 关键原则

1. **架构已经够了, 不要再加新模块** — 当前 ActionSelector + ReflectionEngine + Gap闭环 + GrowthOptimizer 三件套足以支撑第一梯队
2. **P0 跑量比 P1 提效更重要** — wisdom 需要自然生长时间, 急不来
3. **每次改代码后 pytest 零回归** — baseline 4367 passed
4. **人工审核闸门永远保留** — 就算 L3 自治, 高风险 proposal 仍需人工批准
5. **验收指标量化** — 看板里的数字就是每月要追的目标

---

*文档版本: v1.0 | 创建时间: 2026-09-10 | 执行周期: 12 周*
*上一版: AUTONOMY_EXECUTION_PLAN_v1.0.md (6 步方案, 已全部完成)*
