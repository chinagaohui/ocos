# OCOS Attention Model（注意力模型）

> **v1.0 — 2026-07-23 — 冻结于架构定调会议**  
> **层级：Layer 2 — 理论**  
> **地位：Attention 是 Master Agent 的核心组件——它决定"我现在应该看哪里"。它不是 Capability（认知能力），而是 Consciousness（意识属性）。**  

---

## 核心理念

Attention ≠ Capability。

Capability 是"能做到什么"（推理、规划、学习）。  
Attention 是"注意什么"（当前焦点、优先级、方向）。

一个系统可以拥有所有 Capability，但没有 Attention 的话，它不知道**现在该用哪个**。

```
没有 Attention：
  事件 A → 所有引擎全部启动 → 资源耗尽
  事件 B → 所有引擎同时响应 → 互相干扰

有 Attention：
  事件 A → Attention 评估优先级 → 激活最相关的 1-2 个引擎
  事件 B → Attention 判断"不重要" → 排队或忽略
```

---

## Attention 的核心组成

```
Attention
├── focus（当前焦点）
│   ├── target_type        Goal / Intent / Event / UserInput / InternalSignal
│   ├── target_id          具体目标的 ID
│   ├── priority           当前焦点的优先级 [0.0, 1.0]
│   ├── started_at         开始关注的时间
│   └── duration           已持续时长
│
├── queue（关注队列）
│   ├── items[]            排队候焦的项目
│   │   ├── item           候焦对象
│   │   ├── priority       优先级
│   │   ├── urgency        紧急度
│   │   └── reason         为什么需要关注
│   └── capacity           队列容量（默认 10）
│
├── history（注意力历史）
│   ├── recent_focus[]     最近 50 个关注的切换记录
│   └── patterns           注意力模式（什么情况下切换？）
│
└── state（注意力状态）
    ├── current_mode       FOCUSED / SCANNING / IDLE / DISTRIBUTED
    ├── switch_count       注意力切换次数（今日）
    └── fatigue            注意力疲劳度 [0.0, 1.0]
```

---

## Attention 优先级算法

Attention 的焦点选择不是随机的。它基于：

### 外部触发优先级

| 触发源 | 基础优先级 | 说明 |
|--------|-----------|------|
| 用户直接指令 | 1.0 | 最高优先级——主人叫我 |
| 用户交互（非指令） | 0.8 | 主人在和我说话 |
| 异常/告警 | 0.9 | 系统出问题了 |
| 定时事件 | 0.4 | 设定的闹钟 |
| 环境变化 | 0.3 | 网站更新、文件变化 |

### 内部触发优先级

| 触发源 | 基础优先级 | 说明 |
|--------|-----------|------|
| Goal 到期 | 0.7 | 设定的目标截止 |
| Goal 阻塞 | 0.6 | 卡住了，需要决策 |
| 冲突检测 | 0.8 | 信念/Goal 冲突 |
| 健康告警 | 0.9 | 系统异常 |
| 反思触发 | 0.3 | 周期自省 |

### 动态调整

```
最终优先级 = 基础优先级 × urgency_boost × relevance_to_current_goal

urgency_boost = 1.0 + (deadline_proximity × 0.5)
  // 越是临近截止，优先级越高
  
relevance_to_current_goal = [0.0, 1.0]
  // 与当前 Goal 越相关，越应该立即处理
```

---

## Attention 模式

### FOCUSED（专注模式）

| 属性 | 值 |
|------|-----|
| 状态 | 深度关注一个目标 |
| 切换频率 | 低（> 5 分钟/次） |
| 适用场景 | 编码、推理、决策 |
| 疲劳积累 | 快（每 30 分钟 +0.1） |

### SCANNING（扫描模式）

| 属性 | 值 |
|------|-----|
| 状态 | 快速扫描多个输入源 |
| 切换频率 | 高（< 10 秒/次） |
| 适用场景 | 观察阶段、等待响应 |
| 疲劳积累 | 慢 |

### IDLE（空闲模式）

| 属性 | 值 |
|------|-----|
| 状态 | 无活跃目标，等待输入 |
| 切换频率 | 极低 |
| 适用场景 | SLEEP 阶段、用户离开 |
| 疲劳恢复 | 快（每分钟 -0.05） |

### DISTRIBUTED（分布式注意）

| 属性 | 值 |
|------|-----|
| 状态 | 同时关注 2-3 个源 |
| 切换频率 | 中 |
| 适用场景 | 后台任务 + 用户交互 |
| 疲劳积累 | 中等 |

---

## 注意力疲劳

Attention 不是无限的。和人类一样，持续专注会导致疲劳。

| 疲劳值 | 影响 | 建议行动 |
|--------|------|----------|
| 0.0 ~ 0.3 | 正常 | 继续工作 |
| 0.3 ~ 0.5 | 轻微疲劳 | 考虑切换简单任务 |
| 0.5 ~ 0.7 | 中度疲劳 | 错误率上升，建议 REFLECT |
| 0.7 ~ 0.9 | 严重疲劳 | 建议 SLEEP |
| 0.9 ~ 1.0 | 极度疲劳 | 强制 SLEEP |

### 疲劳恢复

```
在 FOCUSED 模式下：每分钟 +0.02
在 SCANNING 模式下：每分钟 +0.005
在 IDLE/SLEEP 模式下：每分钟 -0.05
```

---

## 注意力切换（Context Switch）

注意力切换有代价。每次切换会：

1. 保存当前焦点的上下文（checkpoint）
2. 加载新焦点的上下文
3. 消耗注意力残余（每次切换 +0.02 疲劳）

**原则**：切换成本 > 收益时，不切换。系统应该倾向于完成当前任务后再响应新事件，除非新事件优先级高很多。

---

## Attention 与 Life Cycle 的关系

| Life Cycle 阶段 | Attention 模式 | 说明 |
|----------------|---------------|------|
| WAKE | SCANNING | 扫描当前环境，恢复焦点 |
| OBSERVE | SCANNING → FOCUSED | 发现重要信号 → 锁定 |
| THINK | FOCUSED | 深度思考，最少切换 |
| DECIDE | FOCUSED | 决策需要专注 |
| ACT | FOCUSED / DISTRIBUTED | 执行 + 观察结果 |
| REFLECT | SCANNING | 回顾多个事件，寻找模式 |
| LEARN | FOCUSED | 提取模式需要专注 |
| SLEEP | IDLE | 全低功耗 |
| DREAM | IDLE | 内部处理，不关注外部 |

---

## Attention 的未来扩展

| 未来能力 | 说明 | 预计 Phase |
|----------|------|-----------|
| 情绪影响注意力 | 根据情绪状态调整注意力分配 | Phase 22+ |
| 注意力模式学习 | 学习用户在不同场景下的注意力期望 | Phase 24 |
| 多线程注意力 | Master Agent 同时处理多项但不降低质量 | Phase 23+ |
| 注意力报告 | 向用户解释"为什么我没注意到 X" | Phase 26 |
