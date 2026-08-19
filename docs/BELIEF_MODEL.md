# OCOS Belief Model（信念模型）

> **v1.0 — 2026-07-26 — 从 BELIEF_MODEL 理论创建核心文档**
> **层级：Layer 2 — 理论**
> **地位：Belief 是 OCOS 的认知地图。Memory 是"发生了什么"，Belief 是"我认为什么是真的"。**

---

## 核心理念

**Belief ≠ Memory。**

Memory 是事实记录（"3 天前用户说过喜欢 Python"）。
Belief 是概率判断（"用户大概率继续用 Python → 建议先准备 Python 工具"）。

没有 Belief，OCOS 只能记住过去，不能**预测未来**。
Belief 是从"记忆引擎"变成"认知引擎"的关键跃迁。

---

## Belief 四象限

```
              │ High Probability
              │
    Assumption│  Conviction
    ──────────┼──────────
    （默认假设）│  （确信信念）
              │
──────────────┼─────────────── Evidence Strength
              │
    Speculation│  Suspicion
    （推测）    │  （怀疑）
              │
              │ Low Probability
```

### Assumption（默认假设）
- P ≈ 0.5–0.7, evidence = weak
- 例："新用户默认不懂命令行" ← 无证据，默认假设
- 更新策略：快速修正（1 次反例即可翻转）

### Conviction（确信信念）
- P ≈ 0.8–1.0, evidence = strong
- 例："主人的代码风格偏好 snake_case" ← 多次观察确认
- 更新策略：慢速修正（需要多次反例）

### Speculation（推测）
- P ≈ 0.2–0.5, evidence = weak
- 例："本周可能发布新版本" ← 碎片信息推测
- 更新策略：易证实也易证伪

### Suspicion（怀疑）
- P ≈ 0.3–0.7, evidence = moderate but negative
- 例："这个 API 可能不稳定" ← 少数错误经验
- 更新策略：关注负面证据的累积效应

---

## Belief 核心属性

```python
Belief:
    belief_id: str           # 唯一标识
    statement: str           # 自然语言陈述（"Python ≥ 3.10 支持 match-case"）
    dimension: str           # 所属认知维度（WORLD_KNOWLEDGE / USER_MODEL / TOOL_MODEL / SELF_MODEL）
    probability: float       # 当前置信度（0.0 ~ 1.0）
    evidence_chain: [Evidence]  # 支撑/反对证据
    last_updated: timestamp
    source: str              # 信念来源（OBSERVATION / INFERENCE / USER_STATED）
    quadrant: Quadrant       # 四象限分类（动态计算）
    decay_rate: float        # 衰减速率（无证据时每天下降的量）
    strength: float          # 综合强度 = prob × (1 + evidence_count × 0.1)
```

---

## 更新机制

### 证据加权更新

```
new_prob = (old_prob × prior_weight + evidence_impact × evidence_weight)
           ──────────────────────────────────────────────────────────────
                               prior_weight + evidence_weight

evidence_impact = +1 (positive), -1 (negative), 0 (neutral)
evidence_weight = source_weight × recency_weight
```

### 证据来源权重

| Source | Weight | 说明 |
|--------|--------|------|
| USER_STATED | 0.9 | 用户明确陈述 |
| DIRECT_OBSERVATION | 0.7 | 自己观测到 |
| INFERRED | 0.4 | 推理所得 |
| SECOND_HAND | 0.3 | 从他人处得知 |
| DEFAULT_ASSUMPTION | 0.1 | 默认假设 |

### 时间衰减

```
decay(t) = prob × (1 - decay_rate) ^ days_since_last_update
```

### Confirmation Bias 防御

- 每接受 3 条正面证据后，主动搜寻 1 条反面证据
- 若 search_for_counter_evidence = True 且未找到反面证据，标记为 unverified_conviction

---

## 互动协议

### Belief → Goal
```python
# 信念驱动目标生成
if belief.strength > 0.7 and belief.dimension == USER_MODEL:
    suggest_goal: "基于 '主人偏好 Python' (置信度 {prob})，建议准备 Python 环境"
```

### Belief → Attention
```python
# 不一致信念触发注意力
if belief.probability_delta < -0.3:  # 最近大幅下降
    trigger_attention: "信念复检: {statement}"
```

### Belief → Identity
```python
# 关于自我的信念构成 Identity.self_view 的一部分
if belief.dimension == SELF_MODEL and belief.quadrant == CONVICTION:
    reflect_to_identity: self_view
```

---

## 存储与持久化

- 持久化到 SQLite（beliefs 表 + evidence 表）
- 启动时加载全部活跃信念
- 定期（每天）清理 decayed < 0.05 的信念
- 总数上限：1000 条（超出时按 strength 排序淘汰）

---

## 信念合并

当多个信念指向同一 statement 时：
1. 合并 evidence_chain
2. 加权平均 probability（按各自的 evidence_count 加权）
3. 保留最早的 created_at
4. 清除重复，重新计算 quadrant

---

## 约束

| 规则 | 说明 |
|------|------|
| No Belief Without Evidence | 所有信念必须有至少 1 条 evidence |
| Max Certainty < 1.0 | 最高置信度 0.99（保留可修正性） |
| Min Probability > 0.01 | 低于 0.01 的信念自动清理 |
| Decay Floor | 衰减到 0.05 以下时标记为 DORMANT，30 天后删除 |
