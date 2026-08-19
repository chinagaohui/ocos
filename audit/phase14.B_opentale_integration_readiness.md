# Phase14.B OpenTale Integration Readiness Review

**日期**: 2026-07-22
**审计范围**: OpenTale 55 模块 → OCOS Control Plane 控制入口矩阵
**前提**: Phase14.A (OCOS 内部审计) ✅ PASS, Phase15.0 (Control Plane Positioning) ✅ FROZEN
**状态**: ❄️ FROZEN

## §0 核心发现

### 0.1 现状摘要

| 维度 | 状态 | 说明 |
|------|:----:|------|
| OCOS 内部 | ✅ 稳定 | Phase14.A 6/6 PASS, Phase14 696 tests PASS |
| OpenTale → OCOS Registry | ❌ 未连接 | `opentale/` 零 import from OCOS `contracts/` 或 `reality/` |
| ConstraintBundle | ⚠️ 可扩展 | ~18 keys, 但全部来自模板/项目数据, 无 OCOS Pattern/Principle 注入 |
| Pattern/Principle 数据模型 | ✅ 已定义 | `opentale/app/contracts/pattern.py` + `principle.py` — 但仅限 dataclass, 无运行时 Registry |
| 控制入口 | ⚠️ 部分存在 | `WriterInputContract.constraint_block`, `ConstraintMatrix`, `NarrativeContract` 可承载控制信号 |

### 0.2 架构鸿沟

```
OCOS (Phase14)                              OpenTale
┌─────────────────────┐                    ┌──────────────────┐
│ PatternRegistry     │                    │ ConstraintBundle │
│ (tests/ only)       │ ──── ? ────────?──→│ +~18 keys        │
│ PrincipleRegistry   │                    │ (genre/template)  │
│ (tests/ only)       │                    └──────────────────┘
│ contracts/          │                    ┌──────────────────┐
│  - Observation      │                    │ opentale/app/    │
│  - Evidence         │                    │ contracts/       │
│  - Pattern (frozen) │                    │  - pattern.py    │
│  - Principle(frozen)│                    │  - principle.py  │
└─────────────────────┘                    └──────────────────┘

→ Phase15 Adapter 需要桥接这两个世界
```

---

## §1 完整 Mapping Matrix

### 列说明

| **列** | **含义** |
|--------|----------|
| **模块** | OpenTale 模块名 |
| **行数** | 代码量级 |
| **当前接口** | 模块暴露的公共入口 |
| **OCOS 控制能力** | Control Plane 可以投射什么类型的控制信号 |
| **控制入口点** | 控制信号可以从哪里注入 |
| **状态** | Ready = 有入口 / Gap = 需补接口 / N/A = 不需要 |
| **缺口** | 具体缺失什么 |

---

### §1.1 Pipeline 核心模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **Story Package** | 231 | `StoryPackageCreator.build_story_package()` | Principle Injection | `principle` 字段可扩展 | ⚠️ Ready | 需在 `StoryPackage` 数据模型中增加 OCOS Principle ID 锚点 |
| **Volume Package** | — | 嵌入 director pipeline | Narrative Control | `NarrativeContract` | ⚠️ Ready | `NarrativePolicyEngine` 已可消费 Narrative Contract, 但未消费 OCOS Principle |
| **Chapter Package** | (domain/) | `ChapterPackage` + `ContractEngine` | Pattern Control | `ContractEngine.preconditions` | ⚠️ Ready | ContractEngine 的 precondition 未接入 OCOS Pattern |
| **Outline** | 1,157 | `OutlineBuilder` + `OutlineDB` | Principle Coverage | `OutlineNode.theme` | ⚠️ Partial | OutlineNode 有 theme 字段, 但未映射到 Principle ID |
| **Director** | 14,319 | `DirectorPipeline.direct_chapter()` | Control Signal Hub | `ConstraintMatrix` + `RuntimeContext` | ✅ Ready | 主入口已就绪; Pattern/Principle 注入到 `constraint_bundle` 即可 |
| **ConstraintFusion** | (director/) | `ConstraintFusionEngine.fuse()` | Pattern Injection | `ConstraintMatrix` | ⚠️ Ready | 矩阵字段已定义, 但 Pattern 输入源缺失 |
| **Writer** | 8,134 | `ChapterDrafter.draft()` | Capability Control | `WriterInputContract.constraint_block` | ✅ Ready | constraint_block 字符串已承载约束; 需结构化 Pattern 通道 |

---

### §1.2 叙事引擎模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **SIE — Conflict** | (director/sie/) | `ConflictEngine` | Pattern Influence | `NarrativeStrategyPlan` | ⚠️ Ready | SIE 引擎自主运行; 需 StrategyPlan 承载 OCOS Pattern |
| **SIE — Suspense** | (director/sie/) | `SuspenseEngine` | Pattern Feedback | `SuspensePlan` | ⚠️ Ready | SuspensePoint 无 Pattern ID 引用 |
| **SIE — Emotion Curve** | (director/sie/) | `EmotionCurveEngine` | Pattern Modulation | `global_pattern` | ⚠️ Ready | 当前 genre 硬编码; 可扩展为 OCOS Pattern 驱动 |
| **SIE — Foreshadow** | (evaluation/) | `ForeshadowPayoffManager` | Pattern Feedback | `ForeshadowReport` | ⚠️ Partial | 输出报告但未反向消费 Pattern 更新 |
| **SIE — Narrative Strategy** | (director/sie/) | `SIENarrativeStrategyEngine` | Strategy Control | `NarrativeStrategyPlan` | ⚠️ Ready | plan 格式匹配, 但内容源未接 OCOS |
| **Narrative — Policy** | 1,177 | `NarrativePolicyEngine.to_policy()` | Principle→Policy | `NarrativeContract` | ✅ Ready | **最佳桥接候选**: 已可承载 OCOS Principle 作为 Policy 输入 |
| **Narrative — Council** | (narrative/) | `DirectorCouncil.decide()` | Meta-Control | `CouncilVote` | ⚠️ Partial | Vote 决策无 OCOS Principle 参考 |
| **Narrative — Contract** | (narrative/) | `NarrativeContract` | Control Signal Container | `primary_driver` + `rhythm` | ✅ Ready | **最大可复用接口**: 项目级契约文件, 可扩展 OCOS 字段 |

---

### §1.3 角色模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **Character Brain** | 507 | `CharBrainEngine.initialize()` / `tick()` | ⬜ 需补 | — | ⛔ **GAP** | 完全自主运行; 需 `apply_principle()` 或 `inject_pattern()` |
| **Character Benchmark** | (charbrain/) | `set_emotion()` / `set_goal()` | ⬜ 需补 | `set_goal()` | ⛔ **GAP** | `set_goal()` 可手工注入, 但无 OCOS Principle→Goal 通道 |
| **Emotion Director** | 1,629 | 独立调度 | Pattern Modulation | 原接口不可扩展 | ⛔ **GAP** | 需 Principle-aware 情感模板路由 |
| **Belief Engine** | (knowledge/) | `BeliefEngine.update_belief()` | Principle Injection | `Belief` | ⚠️ Ready | Belief 结构可承载 OCOS Principle, 但未连接 |
| **Relationship** | (charbrain/) | `RelationshipEntry` | Pattern Archive | 仅数据模型 | ⚠️ Partial | 关系模型无 Pattern ID 引用 |

---

### §1.4 评估 & 质量模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **Quality Gate** | (evaluation/) | `QualityGate.evaluate_and_gate()` | Validation Control | `GateLevel` | ⛔ **GAP** | 无 Principle→GateLevel 映射; 完全独立运行 |
| **Mechanical Evaluator** | (evaluation/) | `MechanicalEvaluator` | Validation ABI | 无控制入口 | ⛔ **GAP** | 机械规则独立, 不接受外部 Principle |
| **Narrative Evaluator** | (evaluation/) | `NarrativeEvaluator` | Pattern Validation | 无控制入口 | ⛔ **GAP** | 评估标准不来自 OCOS |
| **Plot Coherence** | (evaluation/) | `PlotCoherenceEvaluator` | Principle Check | `plot_issues` | ⚠️ Partial | 可对照 Principle 输出 issues, 但无主动注入 |
| **Arc Manager** | (evaluation/) | `ArcManager` | Pattern Arc | `ArcReport` | ⚠️ Partial | Arc 概念接近 OCOS Pattern, 但未映射 |
| **Golden Chapter** | (evaluation/) | `GoldenChapter` | Style Reference | `golden_chapter_block` | ✅ Ready | 已注入 ConstraintBundle; 可作为 Principle 参考示例 |

---

### §1.5 记忆 & 知识模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **Memory** | 449 | `MemoryFacade` / `MemoryCompressor` | Observation Archive | `EpisodeMemory` | ⚠️ Partial | 记忆模型不引用 OCOS Evidence/Pattern ID |
| **Knowledge** | 2,776 | `FactRegistry` / `KnowledgeSlot` | Principle Store | `KnowledgeConsumer` | ⚠️ Ready | Consumer 模式可扩展接收 OCOS 数据, 但未实现 |
| **Experience** | 388 | `Experience` 合约 | Pattern Source | 未接入 | ⛔ **GAP** | OCOS Evidence→Experience 链路未连到 OpenTale |
| **Premiselock** | 1,584 | `StateLockGuard` / `TimelineValidator` | Principle Enforcement | `SemanticAnchor` | ⚠️ Ready | SemanticAnchor 可绑定 Principle; TimelineValidator 可检查违背 |

---

### §1.6 控制 & 监控模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **ReaderOS** | 4,382 | `FeedbackContractGenerator` / `ReaderReviewGenerator` | Observation Only | `Finding` | ✅ N/A | 正确: Observation 层只输出, 不接收控制 |
| **Overseer** | 1,330 | `Overseer` | Meta-Observation | — | ✅ N/A | 高层观察, 不直接参与控制 |
| **Governance** | 792 | `PolicyRegistry` | Control Policy | `PolicyRegistry` | ⚠️ Ready | PolicyRegistry 可扩展 OCOS Principle 存储 |
| **Monitoring** | 149 | 轻量监控 | Control Telemetry | 无标准接口 | ⚠️ Partial | 可接入 Control Plane Telemetry |
| **Dashboard** | 259 | UI 数据展示 | Control Visualization | 仅前端 | ✅ N/A | 不参与控制逻辑 |
| **Audit** | (governance/) | 审计日志 | Control Trace | 日志通道 | ⚠️ Partial | 可扩展记录 Control Signal 执行历史 |

---

### §1.7 运行时 & 管道模块

| 模块 | 行数 | 当前接口 | OCOS 控制能力 | 控制入口点 | 状态 | 缺口 |
|------|:----:|----------|---------------|-----------|:----:|------|
| **Pipeline** | 1,949 | `generate_novel` / `resume_project` | Control Orchestrator | `constraint_bundle` | ⚠️ Ready | 注入点已存在 (ConstraintBundle), 但源数据无 OCOS |
| **Runtime** | 2,774 | `NovelRuntimeContext` | Runtime Control | `ContextAssembler` | ✅ Ready | RuntimeContext 已承载约束 |
| **Intent** | 3,361 | `IntentParser` / `DirectorArbitrator` | Capability Router | `resolved_directives` | ⚠️ Partial | intent 解析无 Principle→Capability 映射 |
| **Agent** | 1,011 | `WriterAgent` / `ControlAgent` | Agent Control | `AgentPayload` | ⚠️ Ready | Agent Payload 可扩展 OCOS Routing |
| **Pattern** | 307 | Pattern 发布 | Pattern Output | 未接入 OpenTale | ⛔ **GAP** | pattern.py 合约定义存在, 但无 Runtime Pattern 发布 |

---

### §1.8 OCOS 合约层

| 模块 | 行数 | 当前状态 | OCOS 控制能力 | 就绪状态 |
|------|:----:|:---------:|---------------|:--------:|
| **contracts/pattern.py** | 36 | 冻结 dataclass | Pattern 定义 | ✅ 可用 |
| **contracts/principle.py** | 30 | 冻结 dataclass | Principle 定义 | ✅ 可用 |
| **contracts/meta_signal.py** | 30 | 冻结 dataclass | Meta Signal 定义 | ✅ 可用 |
| **contracts/capability.py** | — | 存在 | Capability 定义 | ✅ 可用 |
| **contracts/recommendation.py** | — | 存在 | Recommendation | ✅ 可用 |
| **contracts/observation.py** | — | 存在 | Observer 产出 | ✅ 可用 |
| **PatternRegistry** | ❌ 不存在 | 仅有 tests/ 定义 | Pattern Registry 查询 | ⛔ 缺运行时 |
| **PrincipleRegistry** | ❌ 不存在 | 仅有 tests/ 定义 | Principle Registry 查询 | ⛔ 缺运行时 |

---

## §2 缺口汇总

### §2.1 严重缺口 (Phase15 Adapter 前必须解决)

| # | 缺口 | 影响 | 建议 |
|---|------|------|------|
| G1 | OCOS PatternRegistry / PrincipleRegistry 无 runtime 实现 | Control Plane 无法查询已发现的 Pattern/Principle | 将 tests/pattern/test_registry_abi.py 中的 `PatternRecord` + tests/principle/test_principle_registry.py 中的 `PrincipleRecord` 部署为 runtime 模块 |
| G2 | ConstraintBundle 不消费 OCOS Registry | 控制信号无法注入 OpenTale 管线 | 在 `ConstraintBundle.build_all()` 中增加 `ocos_patterns` / `ocos_principles` 参数 |
| G3 | Character Brain 无控制入口 | Control Plane 无法影响角色行为 | 增加 `CharBrainEngine.apply_principle()` / `inject_narrative_pattern()` |
| G4 | Quality Gate 不接受 Principle | 验证标准不来自 OCOS | 增加 `QualityGate.set_validation_criteria()` 接受 PrincipleList |
| G5 | Evaluation 模块独立运行 | 评估标准不溯源至 OCOS | 接入 OCOS Principle 作为评估准则的参考基准 |

### §2.2 中等缺口 (Phase15 适配层可以解决)

| # | 缺口 | 建议 |
|---|------|------|
| M1 | NarrativeContract 需扩展 OCOS Principle 字段 | 在 `NarrativeContract` 中增加 `ocos_principle_ids: list[str]` |
| M2 | SIE 引擎的 Pattern 来自 genre hardcode 而非 OCOS | `EmotionCurveEngine.build_emotion_curves()` 增加 OCOS Pattern lookup |
| M3 | OutlineNode.theme 未映射到 Principle ID | 增加 `principle_id: str | None` 字段 |
| M4 | BeliefEngine 的 Belief 未映射到 Principle | 增加 `principle_origin: str | None` 追溯字段 |
| M5 | Experience 合约未接入 OCOS Evidence | `ExperienceStore` 增加 `evidence_node_id` 引用 |
| M6 | ReaderOS Finding 不引用 OCOS Observation | `Finding.evidence` 增加 `ocos_observation_id` |

### §2.3 轻微缺口 (Phase15.5 Adapter 层解决即可)

| # | 缺口 | 建议 |
|---|------|------|
| L1 | StoryPackage 模型无 OCOS Principle ID 锚点 | `StoryPackage` 增加 `principle_ids` |
| L2 | Director's `NarrativeStrategyPlan` 无 Pattern 来源标记 | plan 元数据增加 `pattern_ids` |
| L3 | ForeshadowReport 不反馈到 Pattern Registry | `ForeshadowPayoffManager` 增加 Pattern update callback |
| L4 | Memory 的 EpisodeMemory 无 OCOS Evidence 引用 | 增加 `evidence_id` 外键 |
| L5 | PolicyRegistry 尚未接入 Principle | `PolicyRegistry.evaluate()` 增加 Principle context |

---

## §3 就绪度总分

| 维度 | 分数 | 说明 |
|------|:----:|------|
| **控制入口存在数** | 11/18 | 18 模块中有 11 个已有或可通过扩展接入 (✅ / ⚠️) |
| **严重缺口** | 5 | G1-G5: Control Plane 实现前必须解决 |
| **中等缺口** | 6 | M1-M6: 可在 Phase15 Adapter 层解决 |
| **轻微缺口** | 5 | L1-L5: 适配器自然解决 |
| **总就绪度** | **61%** | 控制基础设施已就位, 但 OCOS Registry 运行时和 Character/Quality 缺口最优先 |

---

## §4 Phase15 路线图修正建议

确认 Phase14.B 的发现后, Phase15 路线图 (用户已审批) 保持不变, 但需明确每阶段的缺口修复责任:

```
Phase15.0 Control Plane Positioning (已完成)
  ↓
Phase14.B OpenTale Integration Readiness (已完成) ← 我们在这里
  ↓
Phase15.1 Control Signal ABI
  职责: 冻结 Control Plane 输入输出契约
  处理: G1 (部署 PatternRegistry/PrincipleRegistry runtime)
  ↓
Phase15.2 Director Contract
  职责: Director 如何消费 Control Signal
  处理: M1, M2 (NarrativeContract + SIE 扩展)
  ↓
Phase15.3 Capability Resolver
  职责: Principle → Capability 映射
  处理: M3, L1 (StarPackage/Outline 锚点)
  ↓
Phase15.4 Control Execution Pipeline
  职责: 完整控制执行链
  处理: G2 (ConstraintBundle 接入 OCOS Registry)
  ↓
Phase15.5 OpenTale Adapter
  职责: 实际连接所有模块
  处理: G3-G5, M4-M6, L2-L5 (模块集成)
  ↓
Phase15.6 Quality Gate Integration
  职责: 控制执行后的验证闭环
  处理: G4-G5 深化
  ↓
Phase15.7 Meta-Control
  职责: 控制策略自身的调度与演化
  ↓
Phase15 Freeze Audit
```

---

## §5 控制信号通路图

```
OCOS 侧                              控制信号                                   OpenTale 侧
┌──────────────┐                    ┌──────────────────┐                    ┌────────────────┐
│ Observation  │──Pattern Signal──→│ Control Signal   │──→ConstraintBundle──→│ Director       │
│ Layer        │                    │ ABI (Phase15.1)  │                     │ Pipeline       │
│ (Evidence)   │──Principle Signal─→│                  │──→NarrativeContract──→│ SIE Engine     │
└──────────────┘                    │                  │                     ├────────────────┤
┌──────────────┐                    │                  │──→CharacterGoal─────→│ Character Brain│
│ Pattern      │──Control Signal──→│                  │                     ├────────────────┤
│ Registry     │                    │                  │──→ValidationCriteria→│ Quality Gate   │
│ (to deploy)  │                    │                  │                     ├────────────────┤
└──────────────┘                    │                  │──→Observation──────→│ ReaderOS       │
┌──────────────┐                    │                  │                     ├────────────────┤
│ Principle    │──Validation Signal→│                  │──→PrincipleRef──────→│ Knowledge/Fact │
│ Registry     │                    │                  │                     └────────────────┘
│ (to deploy)  │                    └──────────────────┘
└──────────────┘

核心原则:
1. OCOS 输出控制信号, OpenTale 消费控制信号
2. Control Signal 是单向的: OCOS → OpenTale
3. 反馈回路通过 ReaderOS (Observation) 回到 OCOS Evidence Layer
4. 每个 OpenTale 模块只消费与其职责相关的信号子集
```

---

## §6 结论

**Phase14.B 整体评分: ⚠️ 条件通过 (Conditional PASS)**

| 项 | 状态 |
|----|:----:|
| OCOS 内部架构 | ✅ 完全就绪 |
| OpenTale 现有控制入口 | ⚠️ 11/18 Ready/Partial |
| 严重缺口 | ⛔ 5 个 (G1-G5) |
| 总就绪度 | 61% |
| **Phase15 可进入?** | **✅ 可进入, 但 Phase15.1 必须优先解决 G1** |

**Phase15 的第一张牌**: 不是写 Control Signal ABI 的抽象定义, 而是先把 **PatternRegistry 和 PrincipleRegistry 从 tests/ 部署到 runtime/**, 让 Control Plane 有数据源可以查询。

---

*报告结束 — Phase14.B FROZEN ❄️*
