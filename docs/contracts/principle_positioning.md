# Phase14.4 — Meta Principle Formation Positioning

**Domain**: Cognitive (Meta Principle Formation)
**Status**: ❄️ FROZEN (2026-07-22)
**Part of**: Phase14.4.0 Meta Principle Formation Positioning Review

## 1. Purpose

定义 Phase14.4 Meta Principle Formation 的域定位——从 Observation Domain 进入 Cognitive Domain 的入口边界。

Phase14.4 回答的问题：
- 这种结构可能对应什么抽象机制？
- 为什么这种结构可能存在？
- 它描述什么叙事机制？

Phase14.4 不回答的问题：
- 这个写法好不好？
- 读者喜欢什么？
- 应该怎样写？

## 2. OCOS 架构位置

```
Reality
  ↓
Evidence (Phase14.1)          Observation Domain
  ↓
Relation (Phase14.2-B2)       Observation Domain
  ↓
Pattern (Phase14.3) ❄️        Observation Domain (已冻结)
  ↓
Principle (Phase14.4) ← 当前  Cognitive Domain (入口)
  ↓
Capability (Phase14.5)        Cognitive Domain
  ↓
Governance (Phase14.6)        Control Domain
  ↓
Edit Agent (Phase14.7)
  ↓
Adapter (Phase14.8)
  ↓
Phase15 Control Plane         Control Domain (安全层)
```

### 2.1 从 Observation 到 Cognitive

Phase14.3 完成后的 OCOS：

```
Observation System:  看见 → 记录 → 关联 → 发现重复结构 → 保存结构
                      ↑ Phase14.3 封闭于此
Cognitive System:    [尚未进入]
```

Phase14.4 要做的：

```
进入 Cognitive 的第一步：
从「什么结构稳定出现」走向「这种结构可能对应什么抽象机制」
```

### 2.2 关键区分

| | Observation (Phase14.1-14.3) | Cognitive (Phase14.4+) |
|--|------------------------------|------------------------|
| 关注 | 什么、频率、分布、稳定性 | 为什么、机制、抽象、迁移 |
| 输出 | Pattern（结构事实） | Principle（抽象机制） |
| 验证 | 统计重复性 | 抽象一致性、跨上下文存在性 |
| 态度 | 记录，不解释 | 提出假说，不认定真理 |

## 3. Principle 定义

### 3.1 Principle = Abstract Mechanism

```
Principle = 从重复观察到的结构模式中抽象出的、可迁移的叙事机制描述。
```

### 3.2 Principle 是（允许）

| 类型 | 示例 |
|------|------|
| 因果结构 | "信息隐藏 + 目标阻碍 + 时间压力 → 决策不确定性增加" |
| 动态关系 | "关系距离缩小与情感期待强度呈正相关" |
| 结构转换 | "冲突积累到阈值后触发化解结构" |
| 约束关系 | "角色选择空间与叙事张力呈非线性关系" |
| 时序模式 | "信息释放顺序影响理解路径的结构" |

所有 Principle 都是：
- **可迁移的**（跨类型/跨作品）
- **假说性的**（非确定性真理）
- **可证伪的**（有反例空间）
- **追溯的**（可回溯到 Pattern 和 Evidence）

### 3.3 Principle 不是（禁止）

| 类型 | 原因 |
|------|------|
| 写作技巧/技法 ("如何写出爽点") | 技巧属于 Phase14.5 Capability |
| 公式/模板 ("三章一章反转") | 模板太具体，不抽象 |
| 市场趋势 ("当下流行的开头") | 趋势属于市场观察，非叙事机制 |
| 风格描述 ("慢热细腻") | 风格是读者感受，非抽象机制 |
| 类型标签 ("言情经典桥段") | 类型标签锁定上下文，不迁移 |
| 规则 ("主角不能太弱") | 规则太规范，非机制描述 |
| 商业模式 ("付费点设计") | 商业模式超出叙事分析 |
| 套路 ("退婚流") | 套路是文化产物，非抽象机制 |

### 3.4 Principle 与 Pattern 的关系

```
Pattern:     Feature{信息隐藏, 目标阻碍, 时间压力}
             Occurrence: 73%
             Context: 多作品多章节

Principle:   "受限信息环境下，目标导向的不确定性增加
              会改变决策压力结构"
             Source: [Pattern-A, Pattern-C, Pattern-F]
             Evidence Chain: [E-101, E-203, E-307]
             Abstraction Level: 跨作品、跨类型
```

**Principle 是 Pattern 的抽象，不是 Pattern 的集合。**

### 3.5 Principle 命名规范

原则命名描述机制，而非评价好坏：

```
✅ "延迟满足与信息释放的结构关系"
✅ "关系距离变化与情绪期待的映射"
✅ "冲突积累触发化解的动态模型"
✅ "角色选择空间与叙事张力的非线性关系"
✅ "信息不对称下预期路径的修正机制"

❌ "爽文标准写法"
❌ "言情甜宠公式"
❌ "读者最爱的开头结构"
❌ "爆款必备元素"
❌ "黄金三章法则"
```

命名使用中性、结构性、机制性的语言。禁止使用价值性、商业性、规范性的语言。

## 4. Pattern → Principle 转换边界

### 4.1 允许输入

| 输入 | 来源 | 说明 |
|------|------|------|
| PatternReference[] | Phase14.3 Registry Query | 结构事实 |
| Evidence Chain | Phase14.1-14.3 Audit Trail | 追溯证据 |
| Relation Graph | Phase14.2-B2 | 关联上下文 |
| Observation Context | Phase14.3 Registry | 范围和条件 |
| Counter Evidence | Phase14.3 Validation | 反例记录 |

### 4.2 禁止输入

| 输入 | 禁止原因 |
|------|----------|
| Reader Score / Rating | 读者评价不描述机制 |
| Market Data (销量/订阅) | 市场数据是商业信号 |
| Popularity Metrics | 流行度是市场现象 |
| Revenue / Conversion | 收入是商业目标 |
| Author Preference | 作者偏好是主观选择 |
| Editorial Feedback | 编辑反馈包含价值判断 |
| AI 预训练知识 | 外部知識污染认知独立性 |
| Genre Trend Labels | 类型趋势是市场观察 |
| User Engagement Score | 用户参与度是商业度量 |

### 4.3 转换流程

```
PatternRegistry
     ↓ (Query)
PatternReference[]
     ↓
Pattern → Principle Inference (Phase14.4.2)
     ↓ 基于 Pattern 的统计特征和结构关系
Hypothesis Formation
     ↓ 提出抽象机制假说
PrincipleCandidate
     ↓ 包含：abstraction, evidence_chain, scope, counter_examples
Principle Validation (Phase14.4.4)
     ↓ 验证抽象一致性
Principle ✓ (注册到 Principle Registry)
```

### 4.4 转换纪律

| 纪律 | 说明 |
|------|------|
| 不自动认定 | Pattern → Principle 是提出假说，不是自动映射 |
| 保留证据链 | 每个 Principle 必须追溯到 Pattern |
| 保留反例 | 必须记录与抽象不符的情况 |
| 不跨层预测 | Principle 不预测"这个写法好不好" |
| 不添加价值 | Principle 描述机制，不判断优劣 |

## 5. ReaderOS 边界

### 5.1 ReaderOS 定位

ReaderOS 是读者行为观察系统，Phase14.4 可以有限使用 ReaderOS 数据作为 Abstract Mechanism 形成的外部信号参考。

但 ReaderOS 的数据不能直接决定 Principle 的形成。

### 5.2 允许的 ReaderOS 信号

| 信号 | 说明 | 用途 |
|------|------|------|
| attention_change | 注意力变化位置 | 辅助定位结构边界 |
| reading_pause | 停留位置和时长 | 辅助判断结构密度 |
| completion_pattern | 完成/中断分布 | 辅助理解结构连贯性 |
| question_generation | 阅读过程中自发疑问 | 辅助理解认知参与度 |
| memory_signal | 回看/重读行为 | 辅助判断信息关联 |
| re_read_indicator | 回读片段定位 | 辅助理解关键节点 |

### 5.3 禁止的 ReaderOS 信号

| 信号 | 禁止原因 |
|------|----------|
| "popular" / "trending" | 流行度不描述机制 |
| "good" / "excellent" | 价值判断不属于机制分析 |
| "successful" | 成功是外部评价 |
| "should_apply" | 应该应用超出分析层 |
| "recommended" | 推荐属于 Capability 层 |
| "high_engagement" | 参与度是商业度量 |
| "most_read" | 最多阅读不描述结构 |
| "highest_rate" | 高分不描述机制 |

### 5.4 ReaderOS 使用纪律

```
允许：  ReaderOS → Attention Signal → 帮助定位 Pattern 的边界
禁止：  ReaderOS → "用户喜欢这个 Pattern" → Principle 形成
允许：  ReaderOS → Reading Pause → 帮助理解结构密度
禁止：  ReaderOS → "读得久=好结构" → Principle 价值认定
```

ReaderOS 只能提供现象（读者行为模式），不提供意义（"读者认为这个好"）。Phase14.4 从 Pattern 的结构特征出发提出机制假说，ReaderOS 的观察信号可作为辅助参考，但不能作为机制形成的主要依据。

## 6. ReaderOS 不能替代 Evidence

```
❌ ReaderOS 信号 → Principle
   "很多读者跳过了这个段落，所以这个结构不好"

✅ Pattern 结构 + Evidence Chain → Principle Candidate
   "信息密度过高的段落与阅读阻抗同步出现，可能反映
    认知负载与阅读流畅性的结构关系"
   ReaderOS reading_pause 作为辅助支持信号
```

## 7. Principle 与 Capability 隔离

### 7.1 职责分离

| Phase | 问题 | 输出 | 责任 |
|-------|------|------|------|
| Phase14.4 | 为什么可能存在？描述什么机制？ | Principle | 认知分析 |
| Phase14.5 | 如何封装成能力？如何调用？ | Capability | 能力工程 |
| Phase14.6 | 如何治理？如何审计？ | Governance | 控制治理 |
| Phase15 | 哪些能力可以安全使用？ | Control | 安全控制 |

### 7.2 Phase14.4 不产生的输出

Phase14.4 不产生（这些全部属于 Phase14.5+）：

| 禁止输出 | 原因 |
|----------|------|
| 写作 Agent | Agent 属于能力封装（Phase14.5） |
| Prompt / Instruction | 生成指令属于 Capability |
| 写作模板 | 模板太具体，非抽象机制 |
| 生成策略 | 策略属于执行层 |
| 修改建议 | 建议属于 Phase15 |
| 风格迁移 | 迁移属于能力调用 |
| 文本生成控制参数 | 参数属于执行控制 |

### 7.3 对比：Pattern → Principle → Capability 的转化

```
Phase14.3 Pattern:
  Feature: 信息隐藏 + 目标阻碍 + 时间压力
  Occurrence: 73%

Phase14.4 Principle (Abstract Mechanism):
  "受限信息环境下不确定性增加改变决策压力结构"
  - 可跨类型迁移
  - 非确定性真理
  - 可追溯至 Evidence

Phase14.5 Capability (可调用能力):
  "SuspendResolution" capability
  - 输入：story_context, character_state
  - 输出：tension_curve, pacing_adjustment
  - 约束：使用频率限制，context_boundary

Phase15 Control:
  - 安全审查：此 Capability 在哪些 context 下允许
  - 参数范围：tension_curve 的幅度限制
```

## 8. Phase14.4 纪律总结

### 8.1 核心原则

```
Phase14.4 形成的是 Abstract Mechanism，不是写作知识库。
Phase14.4 提出的是假说，不是真理。
Phase14.4 追溯的是证据链，不是外部权威。
Phase14.4 隔离的是商业信号，不是结构信号。
```

### 8.2 观测层 vs 认知层

| | Observation (Phase14.3) | Cognitive (Phase14.4) |
|--|------------------------|----------------------|
| 数据 | Pattern + Evidence | Pattern + Evidence + ReaderOS (有限) |
| 输出 | PatternRecord | PrincipleCandidate |
| 验证 | 统计重复性 | 抽象一致性/跨上下文 |
| 状态 | 确定性 | 假说性 |
| 知识 | 结构事实 | 机制假说 |

### 8.3 永久禁止路径

```
Pattern ↓ "这个有效" ↓ "推荐使用" ↓ "生成写法模板"
```

这条路径违反 Observation / Cognitive 边界，永远禁止在任何 Phase 中实现。

### 8.4 正确路径（Phase14.4 内的合理流程）

```
PatternReference[] ↓ Evidence Chain ↓ [抽象过程] ↓ Hypothesis ↓ PrincipleCandidate ↓ [验证] ↓ Principle (注册)
```

## 9. Phase14.4 后续路线

| § | 内容 | 交付 |
|---|------|------|
| §0 | Meta Principle Positioning Review | positioning contract + 测试 |
| §1 | Principle Model Definition | PrincipleCandidate ABI + 禁止字段 |
| §2 | Pattern → Principle Inference Contract | 抽象过程契约 + 隔离 |
| §3 | Evidence Chain / Explanation ABI | 认知审计链 |
| §4 | Principle Validation | 验证维度 + 禁止项 |
| §5 | Principle Registry | 注册 + 查询 + 生命周期 |
| — | Phase14.4 Freeze Audit | 全线审计 |

## 10. Phase14.4 完成后的 OCOS 状态

```
Phase14.4 完成后：

Reality
  ↓ 可观测的事实
Evidence (事实层)
  ↓ 可关联的观察
Relation (关联层)
  ↓ 可发现的重复结构
Pattern (结构观察层)              — 已完成 ❄️
  ↓ 可形成的抽象机制 ↓ ↓
Principle (认知假说层) ← 当前目标
  ↓ 可封装的能力 ↓ ↓
Capability (执行能力层) — Phase14.5
  ↓ 可治理的控制 ↓ ↓
Phase15 Control (安全控制层)
```

届时 OCOS 将从纯粹的危险系统进入「认知系统」：

```
Phase14.3:  什么结构稳定出现？              — 观察者
Phase14.4:  这种结构可能对应什么机制？       — 假说者
Phase14.5:  如何封装成可调用的能力？         — 工程师
Phase14.6:  哪些机制值得长期观察？            — 治理者
```
