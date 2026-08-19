# Phase15.0 Control Plane Positioning Review

**日期**: 2026-07-22
**前置依赖**: Phase14.3 (Pattern Discovery) ❄️, Phase14.4 (Principle Abstraction) ❄️, Phase14.A (Architecture Audit) ✅ PASS
**状态**: ❄️ FROZEN — 定位合约

---

## §0 控制层定位

### 0.1 定义

Control Plane 是 OCOS 四层架构的最高层：

```
         ┌─────────────────────────────┐
         │  Control Plane (Phase15)    │  ← 你现在在这里
         │  director / overseer / agent│
         ├─────────────────────────────┤
         │  Capability (Phase14.5)     │  ← 能力执行层
         │  writer / character / world │
         ├─────────────────────────────┤
         │  Cognitive (Phase14.3+14.4) │  ← Phase14 冻结
         │  pattern / principle        │
         ├─────────────────────────────┤
         │  Observation (Phase13)      │  ← 感知层
         │  reality / readeros         │
         └─────────────────────────────┘
```

**核心职责**: Control Plane 接收 Cognitive 层产出的 Pattern 和 Principle，将其转化为具体的叙事生成控制指令。它不对文本本身负责，而是对生成过程的质量、一致性、适应性和合规性负责。

### 0.2 三问检查

按 Phase9.5 Arch Freeze 标准，控制层必须回答：

| 问题 | 答案 |
|------|------|
| **方向** — 它往哪里去？ | 从 Pattern + Principle 推导出可执行的控制信号 → 驱动 Writer 生成符合目标质量的文本 |
| **性质** — 它是什么？ | 决策与编排层，不是生成层；Control Plane 指导生成，不直接生成文本 |
| **可删除性** — 如果没有它，系统会怎样？ | 系统仍能生成文本但：无质量守恒、无适应能力、无长期记忆约束、无回测机制、无偏差检测 |

### 0.3 职责边界

| 职责 | 归 Control Plane | 非 Control Plane |
|------|------------------|------------------|
| 叙事策略制定 | ✅ Director | — |
| 约束融合 | ✅ ConstraintFusion | — |
| 上下文编排 | ✅ ContextBuilder | — |
| 质量监控 | ✅ Overseer | — |
| 偏差检测与修复 | ✅ DriftMonitor / RepairPolicy | — |
| 读者体验优化 | ✅ ReaderOS | — |
| 文本生成 | — | Writer (Capability) |
| Pattern 发现 | — | Phase14.3 |
| Principle 推导 | — | Phase14.4 |
| 证据提取 | — | Reality (Observation) |

---

## §1 Control Plane 与 Cognitive 层的关系

### 1.1 消费接口

Control Plane 从 Cognitive 层消费以下产物：

```
Pattern {                                → 用于重复模式的识别与利用
  type: PatternType,
  confidence: float,
  evidence: list[EvidenceNode],
  lifecycle: Registered | Archived
}

Principle {                              → 用于叙事规则的推导与执行
  content: str,
  strength: float,
  dimension: PrincipleDimension,
  lifecycle: Registered | SuperInformed
}
```

### 1.2 推拉模式

```
Cognitive (Phase14) ────────────────→ Control (Phase15)
                       推模式
                  PatternRegistry.query()
                  PrincipleRegistry.query()
                  (由 Control Plane 按需拉取)

Control (Phase15) ──────────────────→ Capability (Writer)
                       推模式
                  ConstraintMatrix
                  WriterPackage
                  (由 Control Plane 主动推送)
```

- Control 层 **不写入** Cognitive 层的 Registry — 只读
- Cognitive 层 **不感知** Control 层的决策 — 纯数据生产者
- 依赖方向: Cognitive → Control → Capability ✅ 单向

### 1.3 使用范围限制

| 行为 | 允许 | 不允许 |
|------|------|--------|
| 读取 Registered 的 Pattern | ✅ | — |
| 读取 Registered 的 Principle | ✅ | — |
| 修改 Pattern/Principle 状态 | — | ❌ (属 Cognitive 层职责) |
| 直接调用 Pattern Mining | — | ❌ (属 Phase14.3) |
| 直接调用 Principle Inference | — | ❌ (属 Phase14.4) |
| 绕过 Evidence Validation | — | ❌ |

---

## §2 控制层能力模块映射

OpenTale 现有控制模块 → OCOS Control Plane 能力映射：

### 2.1 Director 管线

| 模块 | OCOS 控制能力 | 输入 | 输出 | 状态 |
|------|--------------|------|------|------|
| **ContextAssembler** | 上下文编排 | StoryOutline, Pattern | NovelRuntimeContext | ✅ 运行 |
| **ConstraintFusionEngine** | 约束融合 | Pattern, Principle | ConstraintMatrix | ✅ 运行 |
| **NarrativeDecisionEngine** | 叙事决策 | ConstraintMatrix | ChapterMission | ✅ 运行 |
| **NarrativeStrategyEngine** | 策略制定 | ChapterMission | NarrativeStrategyPlan | ✅ 运行 |
| **SceneDesigner** | 场景设计 | StrategyPlan | ScenePlan | ✅ 运行 |
| **PromptCompiler** | 提示编译 | ScenePlan, ConstraintMatrix | WriterPrompt | ✅ 运行 |
| **RuntimeValidator** | 运行时验证 | WriterOutput | ValidationResult | ✅ 运行 |
| **WriterPackageBuilder** | 输出打包 | ValidationResult | WriterPackage | ✅ 运行 |

### 2.2 智能控制引擎 (SIE)

| 模块 | OCOS 控制能力 | 描述 | 状态 |
|------|--------------|------|------|
| **CausalGraph** | 因果推理 | 管理事件间因果链 | ✅ 运行 |
| **ConflictEngine** | 冲突生成 | 根据 Pattern 生成冲突 | ✅ 运行 |
| **EmotionCurve** | 情感曲线 | 读者的情感强度规划 | ✅ 运行 |
| **RespirationEngine** | 叙事呼吸 | 张弛节奏控制 | ✅ 运行 |
| **SuspenseEngine** | 悬疑控制 | 悬疑积累与释放 | ✅ 运行 |
| **SurpriseEngine** | 惊喜控制 | 反预期事件调度 | ✅ 运行 |
| **ThemeEngine** | 主题管理 | 主题一致性保障 | ✅ 运行 |
| **DriftMonitor** | 漂移检测 | 检测叙事偏离约束 | ✅ 运行 |
| **ReaderTemporal** | 时间感知 | 读者时间线管理 | ✅ 运行 |
| **ReaderExperience** | 体验追踪 | 读者状态追踪 | ✅ 运行 |

### 2.3 监控与纠正

| 模块 | OCOS 控制能力 | 描述 | 状态 |
|------|--------------|------|------|
| **OverseerAgent** | 质量监控 | 生成质量闭环评估 | ✅ 运行 |
| **NarrativeEvaluator** | 叙事评估 | 逐指标叙事质量评分 | ✅ 运行 |
| **ReaderOS** | 读者信号 | 读者反馈分析 | ✅ 运行 |
| **RepairPolicy** | 修复策略 | 偏差自动修复 | ✅ 运行 |
| **DriftMonitor** | 漂移监控 | 长期偏差趋势 | ✅ 运行 |

### 2.4 记忆与学习

| 模块 | OCOS 控制能力 | 描述 | 状态 |
|------|--------------|------|------|
| **DirectorMemory** | 导演记忆 | 决策历史记忆 | ✅ 运行 |
| **PromiseTracker** | 承诺追踪 | 叙事承诺管理 | ✅ 运行 |
| **RuntimeTelemetry** | 运行时遥测 | 运行指标收集 | ✅ 运行 |
| **ShadowCollector** | 阴影收集 | 决策路径记录 | ✅ 运行 |

---

## §3 控制层内部约束

### 3.1 不允许做的事 (Forbidden)

1. ❌ **不得直接生成文本** — 文本生成是 Writer (Capability) 的职责
2. ❌ **不得修改 Cognitive 层数据** — Pattern/Principle 只读
3. ❌ **不得绕过 Observation 层** — 所有感知数据必须经过 Reality Pipeline
4. ❌ **不得硬编码叙事规则** — 所有规则必须来自 Principle Registry
5. ❌ **不得有无限重试循环** — 必须设置 RecursionLimit
6. ❌ **不得依赖 LLM 内省能力作为主要控制信号**
7. ❌ **不允许 Director 直接调用 Writer 的内部方法** — 通过 WriterPackage 接口
8. ❌ **不允许 Overseer 自动修改文本** — 只输出评估报告
9. ❌ **不允许 ReaderOS 生成叙事决策** — ReaderOS 只提供反馈信号

### 3.2 必须做的事 (Required)

1. ✅ **所有约束融合必须经过 ConstraintMatrix** — 单入口融合
2. ✅ **所有上下文必须经过 ContextAssembler** — 单入口编排
3. ✅ **所有决策必须有 Pattern 或 Principle 依据** — 可追溯
4. ✅ **所有生成过程必须有 RuntimeValidation** — 不可跳过
5. ✅ **所有异常必须有 RecoveryPolicy** — 不可静默失败
6. ✅ **所有遥测必须记录到 RuntimeTelemetry** — 不可静默收缩
7. ✅ **所有质量评估必须通过 NarrativeEvaluator** — 不可自评

### 3.3 数据流约束

```
合法的完整数据流:

[Director] → ConstraintMatrix → [Writer] → Text
    ↑                              │
    │                              ↓
[Pattern/Principle Registry]   [RuntimeValidator]
    ↑                              │
    │                              ↓
[Cognitive Layer]              [Overseer] → Feedback Loop
                                   │
                                   ↓
                              [NarrativeEvaluator] → Evaluation
```

---

## §4 Phase15 路线图

### 4.1 当前状态

Control Plane 的核心模块已在 OpenTale 中实现并通过生产验证。Phase15.0 定位审核确认：

| 维度 | 状态 |
|------|------|
| Director 管线完整 | ✅ A→H 八阶段 |
| SIE 引擎完整 | ✅ 9 个智能模块 |
| Quality Gate 完整 | ✅ Overseer + Evaluator |
| ReaderOS 完整 | ✅ 独立感知层 |
| Runtime Telemetry 完整 | ✅ 监控+遥测 |
| Pattern/Principle 消费接口 | ✅ 通过 Registry |
| 架构层隔离 | ✅ 通过 Phase14.A Audit |

### 4.2 进入条件

| 条件 | 状态 |
|------|------|
| Phase14.3 冻结 | ✅ 426 tests |
| Phase14.4 冻结 | ✅ 270 tests |
| Phase14.A 架构审计 | ✅ 6/6 PASS |
| 0 REQUIRED FIX | ✅ |
| 全量回归 | ✅ 696 tests pass |

### 4.3 推荐下一步 (Phase15.1+)

基于当前状态，建议 Control Layer 的后续能力建设方向：

```
Phase15.1: Control Layer Contract Freeze
  → Director Contracts: ConstraintMatrix / WriterPackage / ValidationResult
  → Overseer Contracts: EvaluationReport / DriftSignal
  → ReaderOS Contracts: FeedbackEdge / ReaderState

Phase15.2: Quality Gate Integration
  → NarrativeEvaluator → Overseer → RepairPolicy 闭环
  → Quality Metric SSOT
  → Threshold Governance

Phase15.3: Pattern-Driven Control
  → Pattern → StrategyEngine 直接路由
  → Principle → ConstraintFusion 自动映射
  → 执行量化: Control usage_per_pattern

Phase15.4: Meta-Control
  → Director 对自身决策的回测
  → Overseer 对 Control Plane 自身的监控
  → 跨会话记忆的轨迹优化
```

---

## §5 签署

```
Phase15.0 Control Plane Positioning Review
=============================================
Date:     2026-07-22
Auditor:  Hermes Agent (Phase14→15 transition)
Status:   ❄️ FROZEN — Positioning Contract

Phase14 Chain: 14.3 → 14.4 → 14.4.6 Freeze Audit
              → 14 Freeze Certificate → 14.A Architecture Audit
              → 15.0 Control Positioning

Next:      Phase15.1+ (待用户确认优先级)
```
