# OCOS Attention & Cognitive Control Freeze（注意力与认知控制冻结协议）

> **v0.1 — 2026-07-25 — Phase 35 Architecture Freeze**
> **层级：Layer 1 — 宪法（Constitution）**
> **地位：定义 OCOS 如何分配有限认知资源，但不定义 OCOS 想要什么。**
>
> 本协议冻结 Attention 系统的认知主权边界。它不引入第四套 Attention 实现，而是
> 将现有三层（A: agent/attention.py, B: runtime/attention_engine.py, C: capability/attention.py）
> 统一到一个认知控制协议下。Freeze 为宪法，代码为实现。

---

## §1 Attention ABI（对外契约）

Attention 系统的输入输出合约。任何进入注意力管道的信号必须符合此契约。

### 1.1 输入

```
Input:
  cognitive_events: CognitiveEvent[]     # Phase 34A EventBus 归一化后的事件
  active_goals: Goal[]                   # 所有 status=ACTIVE 的 Goal
  current_focus: FocusTarget | None      # 当前注意力焦点
  attention_state: {                     # 当前注意力内部状态
    mode: AttentionMode,
    fatigue: float,
    recent_switches: SwitchRecord[]      # 最近 N 次切换
  }
  confidence_context: {                  # §4.5 信号可信度上下文
    source_trust: dict[EventSource, float]
  }
```

### 1.2 输出

```
Output:
  decisions: AttentionDecision[]         # 每个事件的决策
    ├── ACCEPTED:  进入 FOCUSED，替换或竞争当前焦点
    ├── QUEUED:    进入关注队列，延迟处理
    ├── DEFERRED:  不处理但记录（低优先级但有存档价值）
    └── DISMISSED: 丢弃（噪音/重复/无关联）

  focus_update: FocusTarget | None       # 如果焦点发生变化
  suspend_target: FocusTarget | None     # 如果当前焦点被中断
  allocation_report: {                   # 资源分配报告
    focus_allocated: float,              # 分配到当前焦点的认知资源比率
    scanning_budget: float,              # 分配给环境扫描的比率
    idle_slack: float                    # 未分配资源
  }
```

### 1.3 契约约束

```
1. Attention 不创建 Goal（每个决策的 reason 不得为 "create goal"）
2. Attention 不执行任务（ACCEPTED 不等于 EXECUTE）
3. 决策必须在单 Tick 注意力预算内完成（默认 100ms）
4. 每条 AttentionDecision 携带完整 scoring trace（可审计）
5. 输出必须是确定性的（给定相同输入、相同权重 → 相同决策）
```

---

## §2 Focus Model（焦点模型）

### 2.1 核心原则

```
AttentionFocus = One

冻结:
  attention_model: single_focus
  max_active_focus: 1
  future_extension:
    multi_focus: phase 45+

原则:
  Goal 可以并存，Attention 不可以并存。
  单焦点 ≠ 单任务——可以有多个 Goal 同时存在，
  但认知中心只能选择一个。
```

### 2.2 状态机

```
  ┌─────────┐    事件/用户输入    ┌──────────┐
  │  IDLE   │ ─────────────────→ │ FOCUSED  │
  └─────────┘                    └────┬─────┘
       ↑                              │
       │ 目标完成/超时                │ 外部更高优先级
       │                              ↓
       │                        ┌──────────────┐
       │                        │ INTERRUPTED  │ ← 中断条件触发
       │                        └──────┬───────┘
       │                               │ 保存上下文到 WM
       │                               ↓
       │                        ┌──────────────┐
       │                        │  SUSPENDED   │ ← §3 中断协议
       │                        └──────┬───────┘
       │                               │ 重新 Evaluation
       │                               ↓
       │                        ┌─────────────────┐
       │                        │ RE_EVALUATION   │ ← AttentionEngine 重新评分
       │                        └──┬──────────┬───┘
       │                           │          │
       │                  resume   │          │ abandon
       │                           ↓          ↓
       │                      FOCUSED     ARCHIVED
       └─────────────────────── (新焦点)    (不再恢复)
```

### 2.3 焦点属性

```
FocusTarget:
  target_type: TargetType (GOAL / EVENT / USER_INPUT / INTERNAL_SIGNAL)
  target_id: str
  priority: float [0.0, 1.0]          # cognitive priority (§4)
  started_at: datetime
  confidence: float [0.0, 1.0]        # §4.5
  source: EventSource | None          # 如果来自 Event

焦点持续时记录:
  depth_time: 已深度关注时长
  context_footprint: 占用的 WM 槽位数量
  interrupt_count: 被中断次数
```

### 2.4 注意力模式

```
AttentionMode:
  FOCUSED:    单焦点深度关注 → 疲劳累积最快，WM 写入优先
  SCANNING:   周期性扫描事件队列 → 疲劳中等，WM 写入降权
  IDLE:       无活跃目标 → 疲劳恢复，仅监听高优先级中断
  DISTRIBUTED: 保留但 Phase 35 不激活（Phase 45+）

模式切换自动规则:
  - 有新焦点 → FOCUSED
  - 焦点完成且无候焦 → IDLE
  - 疲劳 > 0.9 → 强制 IDLE（健康中断触发）
  - 定时扫描触发 → IDLE → SCANNING（短暂）→ IDLE
```

---

## §3 Interrupt Policy（中断策略）

### 3.1 核心原则

```
Attention 可以暂停认知流，但不能承诺恢复认知流。
恢复也是一次注意力决策，不是自动回滚。

错误的自动恢复模型:
  Focus A → Interrupt B → 完成 B → 自动回 A
  （谁决定 A 仍然重要？环境可能已改变）

正确的模型:
  Focus A → Interrupt B → Suspend A → 处理 B →
  重新进入 Attention Evaluation → 决定是否 Resume A
```

### 3.2 中断条件（三个来源）

```
a) 优先级中断:
   new_priority > current_priority + HYSTERESIS_MARGIN
   HYSTERESIS_MARGIN = 0.15（防止颠簸——小幅度优势不触发中断）

b) 紧急中断:
   event.severity == CRITICAL
   AND event 的目标域与 current_focus 的目标域不重叠
   （同域 CRITICAL 事件不中断，而是提升当前焦点优先级）

c) 健康中断:
   fatigue > FATIGUE_FORCE_IDLE (0.9)
   OR HomeostasisManager 发出 OVERLOAD / RESOURCE_CRITICAL 信号
```

### 3.3 中断成本计算

```
switch_cost = BASE_COST + CONTEXT_DEPTH_COST

BASE_COST = 0.02              # 每次切换的基础认知成本
CONTEXT_DEPTH_COST = 0.01 × context_depth
  context_depth = 当前焦点在 WM 中占用的槽位数 / WM_CAPACITY

如果 switch_cost > (新焦点预期收益 - 当前焦点预期收益):
  拒绝中断（成本 > 收益）
```

### 3.4 中断执行协议

```
当中断被接受:
  1. 保存当前 FocusTarget 的上下文到 WM（标记 slot_type=SUSPENDED）
  2. 当前 FocusTarget 进入 SUSPENDED 状态
  3. 注意力切换到新焦点
  4. 新焦点处理期间的 WM 写入标记 slot_type=ACTIVE_FOCUS

当新焦点处理完毕:
  1. 新焦点进入 COMPLETED 或 ARCHIVED
  2. SUSPENDED 焦点重新进入 Attention Evaluation（§4 优先级算法）
  3. 如果 Evaluation 决定 resume → 恢复 SUSPENDED 上下文
  4. 如果 Evaluation 决定 abandon → 归档到 long-term memory
```

### 3.5 中断频率限制

```
max_interrupts_per_tick = 1    # 每个 Tick 最多 1 次焦点切换
max_interrupts_per_minute = 6  # 每分钟最多 6 次
interrupt_cooldown_ms = 500    # 两次中断之间最少间隔

如果达到频率上限:
  新中断请求 → QUEUED（不执行，排队到下一个 Tick）
```

---

## §4 Cognitive Priority Algorithm（认知优先级算法）

### 4.1 核心公式

```
composite_priority(g) = 
    w_goal       × goal_priority(g)        # Goal 自身重要性
  + w_relevance  × accumulated_relevance(g) # 事件相关性累计
  + w_urgency    × urgency_delta(g)         # 紧迫度增量
  + w_decay      × time_decay(g)            # 时间衰减
  + w_confidence × source_confidence(g)     # 信号可信度
```

### 4.2 各项定义

```
goal_priority(g):
  Goal 对象自身的 priority 字段 [0.0, 1.0]

accumulated_relevance(g):
  最近 N 个事件中与 Goal g 的 relevance score 的指数加权移动平均
  EMA 衰减因子 α = 0.3

urgency_delta(g):
  (now - last_attention_time(g)) / MAX_STALENESS
  MAX_STALENESS = 3600 秒
  刚被关注 → 0.0，1 小时未关注 → 1.0

time_decay(g):
  e^(-λ × t_since_last_focus)
  λ = 0.001（半衰期 ≈ 11.5 分钟）
  刚被关注 → 1.0，长时间未关注 → 趋近 0.0

source_confidence(g):
  source_trust[source] 的加权平均
  用户输入: 1.0, EventBus file_change: 0.8, webhook: 0.5, agent_result: 0.6
  未认证来源: 0.3
```

### 4.3 权重（v0.1 冻结）

| 权重 | 值 | 含义 |
|------|-----|------|
| `w_goal` | 0.30 | Goal 自身重要性 |
| `w_relevance` | 0.25 | 事件相关性 |
| `w_urgency` | 0.20 | 紧迫度 |
| `w_decay` | 0.10 | 时间衰减（防止饥饿） |
| `w_confidence` | 0.10 | 信号可信度（防污染） |
| `margin` | 0.05 | 剩余：保留给未来引入新因子的余量 |

总和 = 0.95，保留 0.05 余量。

### 4.4 饥防机制

```
max_time_without_attention = 3600 秒（1 小时）

如果某个 queued 项目等待超过 max_time_without_attention:
  → 强制提升其 priority 到 threshold + margin
  → 确保下次 evaluation 会被考虑

这防止低优先级项目永久饥饿。
```

### 4.5 Confidence Factor 设计理由

```
未来 EventBus 将接入:
  - webhook（外部不可控信源）
  - 外部 Agent 结果
  - 网络爬取信息
  - 第三方 API

没有 confidence factor:
  Attention 会被低可信信号污染——虚假紧急、刻意引导、注入攻击。

有 confidence:
  高可信信源（用户输入 1.0）天然优于低可信信源（webhook 0.5）
  即使低可信信源发送"紧急"信号，composite 也不会超过高可信的普通信号。
```

---

## §5 Working Memory Allocation Rules（注意力对 WM 的影响）

### 5.1 五条规则

```
规则 1: FOCUSED Slot
  只有 FOCUSED 模式下的当前焦点可以写入 WM 的 "current_focus" 槽位。
  写入内容: FocusTarget + 最近一次 tick 的 attention_score。

规则 2: SCANNING Slot
  SCANNING 模式下扫描到的事件写入 WM 的 "environmental_scan" 槽位。
  权重 = attention_weight × 0.3（低权重，易驱逐）。
  QUEUED 事件也写入此槽位。

规则 3: DISMISSED 不写入
  DISMISSED 事件不写入 WM。
  DEFERRED 事件仅写入 attention_log（可审计但不占 WM 槽位）。

规则 4: 焦点切换降级
  old_focus → SUSPENDED: 从 "current_focus" 降级到 "suspended_context" 槽位。
  保留: FocusTarget, 执行进度, 最后 attention_score。
  丢弃: 临时计算数据、agent 原始输出。

规则 5: WM 容量驱逐
  如果 WM 接近 cap（> 90%）:
    → 驱逐 slots 按优先级:
      1. environmental_scan（最低保留价值）
      2. suspended_context（过期 > 1h 的）
      3. current_focus（仅在 cap > 95% 时驱逐——这是紧急情况）
    → 每个驱逐写入 audit log
```

### 5.2 WM Slot 类型

```
SlotType:
  CURRENT_FOCUS:      当前注意力焦点（1 个槽位，最高保护级别）
  SUSPENDED_CONTEXT:  被中断的焦点上下文（最多 3 个槽位）
  ENVIRONMENTAL_SCAN: 环境扫描结果（最多 5 个槽位，最低保护级别）
  ATTENTION_HISTORY:  注意力切换记录（FIFO，最近 20 条）
```

---

## §6 Boundary with Goal System（Attention-Goal 边界）

### 6.1 权限表

| 操作 | Attention | Goal | 说明 |
|------|-----------|------|------|
| 选择关注对象 | ✅ | ❌ | Attention 的核心职责 |
| 延迟事件 | ✅ | ❌ | QUEUED / DEFERRED |
| 丢弃噪音 | ✅ | ❌ | DISMISSED |
| 请求让渡焦点 | ✅ | ❌ | yield_attention() 信号 |
| 创建 Goal | ❌ | ✅ | 事件 ≠ 意图 |
| 修改 Goal 优先级 | ❌ | ✅ | 那是 GoalManager 的权限 |
| 改变价值排序 | ❌ | ✅ | 系统价值观不可由 Attention 修改 |
| 调用 Agent | ❌ | ✅ | 注意 ≠ 执行 |
| 修改 Self | ❌ | ✅ | Identity 不可被 Attention 修改 |
| 写入 WM | ✅ | — | 按 §5 规则写入 |
| 写入 attention_log | ✅ | — | 可审计的决策记录 |

### 6.2 边界合约

```
Attention 的责任:
  "我应该关注什么？"

Goal 的责任:
  "我想要什么？"

Attention 不能替 Goal 回答 "我想要什么"。
Goal 不能替 Attention 回答 "我应该关注什么"。

冲突裁决:
  如果 Attention 选择了与 Goal 列表不匹配的焦点 → 
  Attention 胜出（这是注意力自主权）
  但 Attention 的产生物（WM 条目、attention_log）必须被审计。
```

---

## §7 Integration with EventBus（Phase 34A 接线）

### 7.1 事件流路径

```
External World
  file_change / timer / webhook
    ↓
EventBus.ingest()                         # Phase 34A
    ↓
EventNormalizer.normalize(RawEvent)
    ↓
CognitiveEvent[]                          # 标准化事件列表
    ↓
AttentionEngine.score(events, goals)      # B 层：评分
    ↓
AttentionScore[]                          # 每个事件的 Novelty/Relevance/Urgency/Confidence
    ↓
AttentionController.evaluate()            # C 层：决策
    ↓
AttentionDecision[]                       # ACCEPTED / QUEUED / DEFERRED / DISMISSED
    ↓
EVENT_INGESTION_TRACE                     # Phase 34A 格式，增加 attention_score
```

### 7.2 日志格式扩展

```
# Phase 34A 原有格式
[EVENT] type=file_modified source=/project/app.py
[ATTENTION] candidate_score=0.72
[DECISION] ignored: no related active goal

# Phase 35 扩展后
[EVENT] type=file_modified source=/project/app.py
[SCORE] novelty=0.30 relevance=0.72 urgency=0.10 confidence=0.80 composite=0.72
[DECISION] queued: moderate priority — pending evaluation slot
[WM] slot=environmental_scan weight=0.18
```

---

## §8 Integration with WorkingMemory（Phase 34B 接线）

### 8.1 焦点切换时的 WM 行为

```
Focus A (ACTIVE) → 被 B 中断:
  1. WM 写入: slot_type=CURRENT_FOCUS → slot_type=SUSPENDED_CONTEXT
     payload: {focus_target: A, progress: 0.6, last_score: 0.85, suspended_at: now}
  2. WM 写入: slot_type=CURRENT_FOCUS → B 的聚焦数据
     payload: {focus_target: B, score: 0.92, started_at: now}

恢复评估:
  1. 如果 B 完成 → B 从 CURRENT_FOCUS 移除
  2. 从 SUSPENDED_CONTEXT 读取 A
  3. AttentionEngine 重新评估 A 的 composite_priority
  4. 如果 composite > threshold → A → CURRENT_FOCUS
  5. 否则 → A → ARCHIVED (写入长期记忆但不恢复)
```

### 8.2 恢复后的连续感知

```
恢复后 WM 检查:
  ✅ 恢复: current_focus.goal_id（知道上次在做什么）
  ✅ 恢复: 未完成的任务列表
  ✅ 恢复: 上一次的 attention_score
  ❌ 不恢复: agent 的中间计算结果
  ❌ 不恢复: 临时事件流
```

---

## §9 Performance Budget（性能预算）

### 9.1 Tick 预算分配

```
AgentRuntime.tick() 总预算: 1.0 秒

分配:
  step 1: Event Ingestion    → 100ms (10%)
  step 2: Attention Scoring  → 100ms (10%)  ← 本协议
  step 3: Attention Decision → 50ms  (5%)   ← 本协议
  step 4: WM Allocation      → 50ms  (5%)   ← 本协议
  steps 5-10: 认知管道        → 700ms (70%)

超预算行为:
  评分超时 → 跳过超预算事件，标记 DEFERRED
  决策超时 → 保持当前焦点不变，新事件全部 QUEUED
  WM 分配超时 → 跳过步骤 4，WM 沿用上一 Tick 状态
```

### 9.2 中断频率硬上限

```
max_interrupts_per_tick = 1
max_interrupts_per_minute = 6
interrupt_cooldown_ms = 500

违反上限 → 新中断请求 QUEUED（不执行）
```

---

## §10 Test Scenarios（验收场景）

### 场景 1: 单一焦点不被打断
```
Given: FOCUSED on Goal A (priority=0.8)
When:  新事件 priority=0.85 (margin < 0.15)
Then:  焦点保持 A，事件 QUEUED
```

### 场景 2: 高优先级中断
```
Given: FOCUSED on Goal A (priority=0.6)
When:  CRITICAL event (severity=CRITICAL, priority=0.9)
Then:  A → SUSPENDED, 新事件 → FOCUSED
       A 的上下文保存到 WM
```

### 场景 3: 中断后不自动恢复
```
Given: Goal A was SUSPENDED while processing Event B
When:  Event B 完成
Then:  A 重新进入 Attention Evaluation
       不自动恢复——需要重新评分
```

### 场景 4: 疲劳强制 IDLE
```
Given: fatigue > 0.9
When:  Tick 开始
Then:  attention_mode → IDLE
       所有新事件 → QUEUED
       当前焦点 → SUSPENDED
```

### 场景 5: 低可信信号不触发中断
```
Given: FOCUSED on Goal A (user input, confidence=1.0, priority=0.6)
When:  webhook event (confidence=0.5, urgency=1.0)
Then:  composite_priority(webhook) = 0.30×0 + 0.25×0.3 + 0.20×1.0 + 0.10×1.0 + 0.10×0.5 = 0.375
       composite_priority(A) = 0.30×0.6 + ... = >> 0.375
       → 不中断
```

### 场景 6: WM 容量驱逐
```
Given: WM 使用率 > 90%
When:  新的 ENVIRONMENTAL_SCAN 条目到达
Then:  驱逐最旧的 environmental_scan 条目
       audit log 记录驱逐
```

### 场景 7: DISMISSED 事件不写入 WM
```
Given: 事件被 DISMISSED
Then:  WM 中无此事件条目
       attention_log 中有此决策记录
```

### 场景 8: 恢复的焦点被重新评估
```
Given: SUSPENDED 焦点 A 在 WM 中
When:  恢复评估时 A 的 composite_priority < threshold
Then:  A → ARCHIVED（不恢复）
       写入长期记忆
```

### 场景 9: 中断频率上限
```
Given: 1 分钟内已发生 6 次中断
When:  新中断请求到达
Then:  请求 QUEUED（不立即执行）
```

### 场景 10: 注意力不创建 Goal
```
Given: AttentionController 收到高优先级事件
When:  evaluate() 被调用
Then:  goal_store 的所有 Goal 不变
       attention_log 中无 "create_goal" 操作
```

---

## §11 Attention Sovereignty Principle（注意力主权原则）

### 11.1 条款正文

```
Attention controls cognitive resource allocation,
but does not control intention.

注意力持有认知资源分配权，但不持有意图创造权。

具体:
  ✅ Attribution 可以:
     - 选择关注对象
     - 延迟事件处理
     - 丢弃认知噪音
     - 请求让渡焦点（yield_attention）
     - 写入注意力评分到 WM
     - 维持可审计的决策日志

  ❌ Attention 不可以:
     - 创建 Goal（事件 ≠ 意图的宪法级约束）
     - 修改用户目标
     - 改变系统价值排序
     - 调用 Agent（注意 ≠ 执行）
     - 修改 Self（身份不可被注意力修改）
     - 修改其他 Agent 的注意力状态
```

### 11.2 与 Cognitive Sovereignty Principle 的关系

```
Cognitive Sovereignty（认知主权）:
  定义: OCOS 的 Self/Goal/Belief/Identity 不可被外部 Agent 修改
  管辖: 认知内容的完整性

Attention Sovereignty（注意力主权）:
  定义: OCOS 的注意力分配决策不可被外部事件直接控制
  管辖: 认知资源的自主分配

两者是互补的:
  认知主权保护"想什么"不受污染
  注意力主权保护"看什么"不受劫持
```

### 11.3 实施检查

```
每个 Tick 结束时检查:
  1. goal_store 的 Goal 数量未变化（除非 GoalManager 显式操作）
  2. identity 未变化
  3. Self 未变化
  4. 其他 Agent 的 attention 状态未变化

违反 → 记录到 audit log → AttentionController 降级到 SAFE_MODE（仅处理用户输入事件）
```

---

## §12 Multi-Agent Attention Isolation（多 Agent 注意力隔离）

### 12.1 前向接口（Phase 36/37 埋点）

```
本条款为 Phase 36 Capability Nervous System 和 Phase 37 External Agent Ecosystem
预留隔离接口。Phase 35 不需要实现，但冻结此接口契约。

原则:
  每个 External Agent 有自己的 LocalAttentionState（A 层），
  但只有 OCOS 的 CognitiveAttentionController（C 层）持有认知主权。
```

### 12.2 隔离契约

```
1. Agent Attention 边界:
   Agent 的 Attention.agent_local 只能管理:
     - Agent 自身的任务队列
     - Agent 自身的疲劳状态
     - Agent 自身的执行进度
   不能:
     - 向 OCOS AttentionController 写入决策
     - 抢占其他 Agent 的焦点
     - 修改 OCOS GlobalAttentionState

2. OCOS AttentionController 的跨 Agent 权限:
   - 读取所有 Agent 的 LocalAttentionState（监控用）
   - 发出 ATTENTION_YIELD 信号（请求 Agent 让渡焦点）
   - 评估 Agent 结果的 relevance 并决定是否纳入认知流
   - 不能直接修改 Agent 的 LocalAttentionState

3. 交叉关注检查:
   当 Agent A 的输出被 Agent B 的 Attention 捕获并评分:
   → 评分必须由 OCOS AttentionController 代理
   → Agent B 的 LocalAttentionState 只能接受评分结果，不能自行评分
```

### 12.3 Phase 35 实现的接口桩

```python
# Phase 35 只定义接口签名，Phase 36 实现

class AgentAttentionBridge:
    """Agent 注意力隔离桥（Phase 36 实现）。"""
    def register_agent_attention(self, agent_id: str, state: LocalAttentionState) -> None: ...
    def get_agent_attention(self, agent_id: str) -> LocalAttentionState | None: ...
    def cross_agent_score(self, source_agent: str, target_agent: str, event) -> float: ...  # 必须由 OCOS 评分
```

---

## 附录 A: 现有三层代码的角色重定义

| 层 | 当前定位 | Phase 35 重定义 | 文件 |
|----|---------|-----------------|------|
| A | Agent Local Attention | `LocalAttentionState` — Agent 内部疲劳、状态、focus 生命周期 | `ocos/agent/attention.py` |
| B | AttentionEngine | `AttentionScoringEngine` — Observation/Event/Goal → score | `ocos/runtime/attention_engine.py` |
| C | AttentionManager | `CognitiveAttentionController` — Score + Policy + Focus State Machine = Decision | `ocos/capability/attention.py` |

### 调用链

```
EventBus (Phase 34A)
    ↓ CognitiveEvent[]
B: AttentionEngine.score(events, goals)
    ↓ AttentionScore[]
C: CognitiveAttentionController.evaluate(scores, current_focus, state)
    ↓ AttentionDecision[]
A: LocalAttentionState.update(new_focus, fatigue_delta, mode_change)
    ↓
WM (Phase 34B)
```

### 代码修改原则

```
1. 不删除任何文件
2. 不新增第四套 Attention 实现
3. A 层: 重命名类 + 移除跨 Agent 影响
4. B 层: 增加 confidence scoring + Phase 35 日志格式
5. C 层: 增加中断协议 + 状态机 + WM 分配规则 + 主权检查
```

---

## 附录 B: Freeze 版本与未来演进

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-07-25 | Phase 35: 初始冻结。单焦点、中断协议、5 权重优先级、Attention Sovereignty Principle、Agent 隔离接口。 |
| v0.2 | (TBD) | Phase 36+ Capability Nervous System 集成后的调整。 |
| v1.0 | (TBD) | 24h 连续运行验证后的稳定冻结。 |

---

> **Freeze Status: DRAFT v0.1 — 待实施后根据回归测试结果升级到 v0.2**
