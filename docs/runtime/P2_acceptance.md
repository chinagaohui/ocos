# P2 验收报告：内生驱力（A/B/C/D 四相）

日期：2026-08-29
验收方式：契约测试全量 + 真实链路 smoke 三证 + 全量回归比对
基线：实施前 1952 passed / 8 skipped / 0 failed（P2-A/B 完成后）
现状：**1971 passed / 8 skipped / 0 failed**（+19 新契约测试）

## 1. P2-A 内生 Goal 驱动引擎 — ✅

| 验收项 | 状态 | 证据 |
|---|---|---|
| Regulator 驱力引擎（驱力→目标映射） | ✅ | ocos/capability/regulator.py，P2-A 验收已确认 |
| Step 4.5 目标挂 tick 入库 | ✅ | life_cycle_orchestrator 认知循环接线，测试绿 |
| 目标入库 + 状态机 | ✅ | goal_store.py（SQLite），P2-A 契约测试全绿 |

## 2. P2-B 好奇心驱动 — ✅

| 验收项 | 状态 | 证据 |
|---|---|---|
| 好奇心（信息增益）驱力 | ✅ | homeostasis.py curiosity 通道，P2-B 验收已确认 |
| Dream 巩固（weak Belief 修剪） | ✅ | PatternStore REJECTED 语义 + 测试 |
| 双运行时共存（认知循环 + 驱力循环） | ✅ | agent_runtime.py + 1952 基线回归 |

## 3. P2-C Dream 生产触发 — ✅

| 验收项 | 状态 | 证据 |
|---|---|---|
| _consolidate_episodes()（dream 内私有方法） | ✅ | master_agent.py，Lessons 合成后调用 |
| 构造 +belief_store/pattern_store（可选） | ✅ | 惰性内存存储，注入优先 |
| 确定性规则表（无 LLM） | ✅ | 聚类键/强度/修剪阈值全确定性 |
| 200 条/夜预算 | ✅ | CONSOLIDATION_BATCH_LIMIT=200 |
| Episode 置 CONSOLIDATED 幂等 | ✅ | mark_consolidated()，二次 dream 不重放 |
| 契约测试 | ✅ | test_dream_consolidation.py 7/7 |
| 真实链路 smoke | ✅ | dream() 全链路（激活路径）产出巩固统计 |

## 4. P2-D 主动输出 — ✅

| 验收项 | 状态 | 证据 |
|---|---|---|
| ocos/proactive/ 模块（4 文件） | ✅ | templates/audit/engine/__init__ |
| 触发链四闸门 | ✅ | 频率→SELF 目标→疲劳→模板轮换 |
| 双检 fail-closed | ✅ | PermissionGuard + 宪法；缺失→missing_guard |
| 输出通道（可注入 callback） | ✅ | Telegram 留接口，本地日志兜底 |
| SQLite 审计 | ✅ | 落盘验证（granted=True + daily_limit 双条） |
| 挂 _tick_idle 尾部 | ✅ | life_cycle_orchestrator，防御式降级 |
| D4 裁决（每日 ≤1 次） | ✅ | daily_limit=1 默认，UTC 日重置 |
| 契约测试 | ✅ | test_proactive_output.py 12/12 |
| 真实链路 smoke | ✅ | 输出→审计→二次拒绝→missing_guard 四证 |

## 5. 验收发现与修复记录

**验收发现 1 项契约缺口（已修复）**：
- 现象：注入 audit_store（未 initialize）时引擎不建表 → 审计/频率闸门异常被防御吞掉 → 注入场景全链静默。
- 根因：engine.__init__ 仅默认路径 initialize，注入路径跳过。
- 修复：统一 `self.audit_store.initialize()`（幂等 CREATE TABLE IF NOT EXISTS）。
- 锁定：新增契约测试 test_injected_audit_store_auto_initialized。
- 说明：测试 fixture 显式 initialize 掩盖了该缺口；smoke 真实验证暴露。

## 6. 安全表

| 威胁 | 防护 | 证据 |
|---|---|---|
| 防越权（无护栏输出） | 双检 fail-closed：guard/宪法任一缺失→拒绝+审计 missing_guard | smoke 证：无防护→None + missing_guard 记录 |
| 防伪造（审计不可信） | SQLite 持久化审计，granted/reason 全量记录 | smoke 证：granted=True/daily_limit 双条落盘 |
| 防失控（骚扰频率） | daily_limit=1（D4 裁决）+ UTC 日重置 | smoke 证：第二次调用被拒 |
| 防静默失效 | 引擎防御降级显式 WARNING 日志 | 修复前 degraded 日志可见；修复后消除 |

## 7. 架构成熟度对比

| 维度 | 实施前 | 实施后 |
|---|---|---|
| 内生驱力 | 静态规则（P2-A 前） | Regulator + 好奇心 + 目标状态机 |
| 记忆巩固 | 无（episode 只存不处理） | dream 期确定性巩固（Belief/Pattern 演化） |
| 主动行为 | 无（纯被动响应） | 受控主动输出（四闸门 + 双检 + 审计） |
| 治理 | 部分（P1 宪法） | 主动行为纳入宪法双检，fail-closed |
| 可观测性 | 无主动行为审计 | 每次尝试全量审计（含被拒） |

## 8. 符合冻结原则声明

增量嵌入：P2-C 仅 dream() 内私有方法 + 2 构造参数 + 2 个最小 store 方法（mark_consolidated/find_by_condition）；P2-D 全部新代码进 ocos/proactive/ 新目录；零拆解、零语义覆盖；实施偏差 9 项已分别追加至 P2C/P2D 冻结文档「实施记录」章节（追加优先，不覆盖冻结期假设）。

## 9. Next Phase 提案：P3 身份（ID 相）

P3 范围（待冻结）：叙事记忆 / 关系记忆 / 值漂移 / PreferenceModel —— 4 契约项。审计后展示 scope 冻结草案，获批准后实施。
