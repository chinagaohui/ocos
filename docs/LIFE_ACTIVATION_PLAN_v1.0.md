# 数字生命激活方案 — 从空转到真活

**日期**：2026-09-09
**前置**：Phase A/B/C 全部代码落地，2681 测试通过，真实 daemon 在运行但 dream 白跑
**目标**：让 OCOS 从"架构齐全但空转"变成"有节奏地活着"

---

## 诊断根因链（从 vitals 真实数据反推）

```
vitals: failure_recurrence_rate = 100%（4/4 cause 复发）
    ↓ 为什么复发?
daemon logs: Dream consolidation 每次 beliefs_created=0, patterns_created=0
    ↓ 为什么 dream 白跑?
_synthesize_lessons → len(source) < 2 → return []
    ↓ 为什么 source 空?
builder.get_complete() → 所有 candidate 都是 INCOMPLETE
    ↓ 为什么 INCOMPLETE?
ExperienceValidator.required_fields_present 要求 5 个非空:
    observation, reasoning_trace_id, decision_trace_id, action_result, outcome
    ↓ daemon tick 构造的 TraceBundle 缺 trace_id / action_result → INCOMPLETE
    ↓ 所以 dream 白跑 → 零 C 类 Lesson → 同 cause 永远复发
```

**额外发现**：daemon 在疯狂 propose autonomous_goal（"模块 ocos.xxx 从未被触及"）→ 全部 execution_error → 写 failure_lesson → 同 goal 永远被 propose → 永远失败 → 永远写 B 类 lesson → dream 白跑 → 没有 C 类 lesson → bridge 永远只有 B 类 → 永远撞墙。

---

## 修复优先级（按影响 × 难度排序）

| # | 修复项 | 影响 | 难度 | 改动点数 |
|---|---|---|---|---|
| **1** | **Dream 产出修复**：`_synthesize_lessons` 放宽 COMPLETE 门槛 | 打通整个学习闭环 | 中 | 1 文件 ~15 行 |
| **2** | **失败 Goal 熔断**：同 goal 连续 3 fail → 不再 propose | 停止撞墙循环 | 中 | 2 文件 ~30 行 |
| **3** | **execution_error C 类模板**：cause_to_procedure 加 execution_error 映射 | 减少复发 | 低 | 1 文件 ~10 行 |
| **4** | **autonomy_level 提升**：1→2 | 解锁更深自主 | 低 | 环境变量 |

**修复 1 是核心杠杆**——Dream 一旦真的产出 C 类 Lesson，bridge 注入会有真实 procedure，execution_error 会被逐渐学会，复发率自然下降，autonomy 也不再被学习失败抑制。

---

## 修复 1: Dream 产出修复 — 放宽 COMPLETE 门槛

**根因代码**：`ocos/memory/experience/builder.py:126-129`

```python
def get_complete(self) -> list[ExperienceCandidate]:
    return [c for c in self._candidates
            if c.status == ExperienceStatus.COMPLETE]
```

**`_synthesize_lessons` 只看 COMPLETE** → 要求 5 字段非空 → daemon tick 的 TraceBundle 构造不全 → 永远零 COMPLETE → 永远空列表。

**修复方案**（不改 validator，改 synthesizer 接收源）：

`ocos/memory/experience/builder.py` — `_synthesize_lessons` 同时接受 COMPLETE + INCOMPLETE，且有降级策略：

```python
def _synthesize_lessons(
    self,
    candidates: Optional[list[ExperienceCandidate]] = None,
    require_complete: bool = False,  # 默认放宽门槛
) -> list[LessonsLearned]:
    from ocos.memory.experience.lessons import LessonsSynthesizer

    if candidates is None:
        # 放宽门槛：COMPLETE + INCOMPLETE 都进，INCOMPLETE 的 rejection_reason
        # 给 synthesizer 作为"缺什么"的提示（e.g. "missing: outcome" → 合成
        # 时标注"该经验缺少 outcome 字段，lesson 仅供参考"）
        if require_complete:
            source = self.get_complete()
        else:
            source = self._candidates  # 全部

    if len(source) < 2:
        return []

    synthesizer = LessonsSynthesizer()
    return synthesizer.synthesize(source)
```

**同时**：`ocos/agent/master_agent.py:1337-1344` — `_fast_path_learning` 也应该接受 INCOMPLETE candidate（只要有 outcome.success 字段）：

```python
# 当前: 过滤 status==COMPLETE 的
# 改为: 只要 outcome 非空就进（outcome 是 LearningEngine 的必要字段）
```

**验收标准**：daemon 下次 dream 后，journalctl 日志里：
- `beliefs_created > 0` 或 `patterns_created > 0` 或 `lessons_synthesized > 0`
- 新 episode 出现 `source='lesson' AND action='synthesize'`（不是 failure_lesson）
- 新 lesson 的 decision 含 `【`（C 类模板）

**通过门槛**：`c_lesson_count_7d ≥ 1` 在下一次 vitals 检查中。

---

## 修复 2: 失败 Goal 熔断

**根因代码**：`ocos/daemon/motivation.py` — `MotivationHub.scan()` 没有"同 goal 连续失败"熔断机制。

**修复方案**：在 GoalStore / pending_actions 中追踪 per-goal 失败计数：

1. `ocos/daemon/motivation.py` — 新增 `_get_goal_fail_count(goal_id: str) → int`：
   ```python
   # 查 pending_actions 表: 同 goal_id 的 denied 次数
   SELECT COUNT(*) FROM pending_actions WHERE goal_id = ? AND status = 'denied'
   ```
2. 在 `_propose()` 前置检查：如果同一 `goal_id` 在最近 7 天内 `denied ≥ 3` 次 → 跳过该 goal，写一条 failure_lesson 熔断 episode：
   ```python
   episode = Episode(
       source='lesson',
       action='goal_fuse',
       decision=f'【熔断机制】goal={goal_id} 连续失败 {fail_count} 次，暂停 propose',
       outcome={'success': True, 'action': 'fused'},
       tags=['goal_fuse', 'execution_error'],
   )
   ```
3. 同时给 `LessonsSynthesizer._extract_failure_pattern` 的上下文加熔断信息——下次 dream 合成的 lesson 会知道"这个 goal 反复撞墙"。

**验收标准**：新 autonomous_goal_proposal 不再重复"自我探查：模块 xxx"，或熔断 episode 出现。

---

## 修复 3: execution_error C 类模板

**根因**：`experience_learning.py:cause_to_procedure` 当前只覆盖 timeout → INCOMPLETE。

**修复**：加 2 条 execution_error 映射：

```python
# experience_learning.py _EXECUTION_ERROR_PROCEDURE_MAP:
(("模块", "从未被触及", "module", "缺失"),
 "【模块探查程序】先检查模块是否存在；分批探查函数签名；等每个探查完成。"
 "禁止一次探查所有模块。成功=找到可调用入口"),
(("命令", "失败", "command", "error"),
 "【命令执行程序】先 dry-run 预览命令；分批执行；等每批成功再继续。"
 "禁止直接一次性执行所有命令。成功=无报错完成"),
```

**验收标准**：`c_lesson_production_per_day` 在 execution_error lesson 上非零。

---

## 修复 4: autonomy_level 提升（可选，等 1-3 见效后）

```bash
echo "2" > ~/.ocos/autonomy_override
```

解除 SELF 类型 goal 禁止动态创建的限制。

---

## 执行顺序与通过门槛

```
Step 1: 修复 1 (Dream 产出修复)
  → 跑测试：tests/test_self_evolution_metrics.py 全通过 + 全量 2681 通过
  → 重启 daemon，等 200 tick (≈ 15-20 分钟)
  → 查 journalctl: "Dream consolidation" 日志里 beliefs/patterns/lessons 非零
  → 查 DB: episodes 表出现 source='lesson' AND action='synthesize'
  → 查 decision 列含 '【' → C 类 Lesson 产出 ✅

Step 2: 修复 2 (Goal 熔断) + 修复 3 (execution_error 模板)
  → 跑全量测试
  → 重启 daemon，等 200 tick
  → 查 vitals: failure_recurrence_rate 应该开始下降
  → 查 vitals: failure_rate_trend_delta 应该开始变正

Step 3 (可选): 修复 4 (autonomy_level 提升)
  → 解除 SELF goal 限制
```

---

## 完整执行命令

```bash
# Step 0: 当前状态记录（执行前快照）
ocos vitals > ~/.ocos/baseline_vitals.md 2>&1
journalctl --user -u ocos-daemon --no-pager -n 50 > ~/.ocos/baseline_daemon.log

# Step 1 实施
# 改 builder.py + master_agent.py → 跑测试 → 重启 daemon
.venv/bin/python -m pytest tests/ --timeout 30 -q
systemctl --user restart ocos-daemon

# 等 dream 周期（200 tick ≈ 15min @ 5s/tick）
sleep 900

# Step 1 验证
journalctl --user -u ocos-daemon --no-pager -n 30 | grep "Dream consolidation"
ocos vitals

# Step 2 实施 → 重启 → 验证
# Step 3 实施 → 重启 → 验证

# 最终验证（至少等 7 天积累足够数据）
.venv/bin/python scripts/self_evolution_daily_test.py trend
# verdict 应该从 INSUFFICIENT 变成 ≥3 improving
```

---

## 风险与退路

| 风险 | 影响 | 退路 |
|---|---|---|
| 放宽 INCOMPLETE 后 synthesizer 产出低质量 lesson | 误导 bridge 注入 | `LessonsSynthesizer.synthesize` 里过滤 `rejection_reason` 过长的 candidate |
| Dream 产出后 bridge 消费但 LLM 不遵循 C 类模板 | 行为无改善 | Phase A0 已经证明 C-auto=5/10 > C-hand=3/10 → LLM 会遵循 |
| 熔断后 MotivationHub 不再 propose → autonomy_goal_ratio 更低 | 被动等待用户输入 | 先修复 dream（有真实 C 类后 autonomy 自然被学习成功提升） |
| execution_error 模板写得不好导致更多失败 | 退化 | 迭代优化，每次 dream 会合成更好的模板 |

**核心退路**：所有修改加回滚开关（环境变量控制 `_synthesize_lessons(require_complete=True)`），坏了就 `systemctl --user restart ocos-daemon` + 改 env。

---

## 最终状态目标

修复后 7 天的理想 vitals：

```
[V1 自主性]
  autonomy_goal_ratio : ≥30%
[V2/V4 成长·元认知]
  failure_recurrence  : ≤20%
  self_evolve_failure : failure_rate_trend_delta ≥0（变好）
  self_evolve_c_lesson: ≥0.5/天 C 类产出
  self_evolve_inject  : ≥1× （Lesson 被高频消费）
```

这时 OCOS 才算从"在运行"变成"在活着"。
