# P2-A Freeze — Regulator 内生目标引擎（稳态偏差 → 驱力 → SELF Goal）

> 依据：docs/OCOS_DIGITAL_LIFE_UPGRADE_REPORT.md §3-P2 + §4（Regulator 实现规格）
> 日期：2026-08-29 ｜ 阶段：P2 本能（拆分 A/B/C/D，A 先行）
> 性质：增量嵌入（Plan B），零推翻、零重建、零 LLM（全确定性规则）

## 1. 审计结论（2026-08-29 fresh）

| # | 事实 | 证据 |
|---|---|---|
| F1 | recommend_actions() 已有动作枚举（Phase 29），但零执行、零内生目标 | capability/homeostasis.py:544 |
| F2 | GoalOriginLevel(HUMAN/SYSTEM/SELF) + Goal(origin_level) 模型齐备 | kernel/goal_types.py:72/144 |
| F3 | GoalOriginEnforcer Phase 25+ 放行 SELF；生产 phase="phase25" | goal/enforcer.py:75 / self/builder.py:104 |
| F4 | GoalSQLiteStore save/load_active 带 origin_level 持久化 | agent/goal_store.py:41 |
| F5 | AgentRuntime Step 6 load_active() 消费 PENDING goal——内生目标写入即被消费 | agent_runtime.py:733 |
| F6 | HomeostasisManager 生产路径零实例化（仅 docstring 示例） | capability/homeostasis.py:347 |

**缺口唯一且精确**：偏差→驱力→内生目标的生成与挂载（Regulator stub 的"执行逻辑"）。

## 2. Scope（包含）

1. **ocos/capability/homeostasis.py 原地补全**：
   - `DriveType` 枚举：EXPLORE / MASTERY / CONNECTION / RESTORE / REFLECT（报告 §4 五驱力）
   - `DriveSignal` dataclass：drive / intensity(0-1) / reason / metric
   - `Regulator` 类（确定性函数式组件，无状态、无 I/O）：
     - `derive_drives(snapshot) -> list[DriveSignal]`：确定性规则表（阈值→驱力）
     - `generate_self_goals(drives, enforcer, now) -> list[Goal]`：驱力→SELF Goal（priority 0.3–0.7 < HUMAN 1.0）
   - `RegulateResult` dataclass：drives / goals / actions
   - `HomeostasisManager.regulate(enforcer) -> RegulateResult`：check → derive → generate
2. **ocos/agent/agent_runtime.py**：tick 新增 Step 4.5 `_tick_step_homeostasis_regulation()`（Step 4 与 Step 5 之间）：
   - 构造 HomeostasisManager + GoalOriginEnforcer(current_phase=25)
   - regulate() → SELF goals 写入 `_goal_store.save()`（本 tick 即被 Step 6 消费）
   - 失败降级：异常时返回 `{"step": "4.5", "gated": True, "error": ...}`，不中断 tick
3. **tests/test_capability/test_homeostasis.py 追加** TestRegulator 类（驱力映射确定性 / SELF 门控 phase 21 vs 25 / 优先级 < HUMAN / regulate 集成 / 写库可读回）
4. **docs/runtime/P2A_regulator_self_goals.md**（本冻结文档）

## 3. 禁区（不包含）

- ❌ 好奇心驱动（P2-B，下一拆）
- ❌ dream() 每夜巩固 / LifecycleManager DREAMING（P2-C）
- ❌ proactive 主动性引擎（P2-D）
- ❌ 改 GoalOriginEnforcer / GoalFactory 默认 phase（保持 21；Regulator 显式传 25）
- ❌ 改 recommend_actions 既有动作枚举逻辑
- ❌ 任何 LLM 调用（驱力映射与目标模板全确定性）

## 4. 验收（2026-08-29 执行结果）

1. ✅ 新增 TestRegulator 15 例全绿（tests/test_capability/test_homeostasis.py，59 passed）
2. ✅ tests/ 全量 **1942 passed / 8 skipped / 0 failed**（基线 1924 → +18，零回归）
3. ✅ 冒烟（/tmp/p2a_smoke.py）：空转快照 → drives [EXPLORE, CONNECTION] → 2 个 SELF 目标入库 → load_active 可读（Step 6 消费侧证明）；Phase 21 门控全拒
4. ✅ D3：生成目标 priority 0.3–0.7，恒 < HUMAN floor 1.0
5. ✅ 伴随修复：GoalSQLiteStore.initialize() 补 executescript(_DDL)（既有缺陷：_DDL 定义后从未执行，建表缺失；对齐 memory/*/store.py 模式）；补 tests/agent/test_goal_store_persistence.py 4 例（此前 GoalSQLiteStore 真实路径零测试覆盖）

## 5. 安全表

| 威胁 | 防护 |
|---|---|
| 防越权（内生目标越级） | GoalOriginEnforcer.verify_creation 强制（SELF 合法仅在 Phase 25+）；priority 恒 < HUMAN(1.0) |
| 防失控（目标风暴） | 每 tick 至多 N 个目标（规则表上限 3）；intensity 上限 1.0 |
| 防伪造 | origin_level=SELF 硬编码于生成路径，不可由外部注入 |
| 防中断 | Step 4.5 异常降级为 gated，不打断 tick 主循环 |

## 6. 符合冻结原则声明

增量嵌入：仅补全 homeostasis.py 既有类 + AgentRuntime 加一步；旧行为（recommend_actions 枚举）原样保留；测试追加不改既有断言；验收全量回归。
