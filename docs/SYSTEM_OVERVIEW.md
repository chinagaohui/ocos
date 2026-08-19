# OpenTale 系统架构概况

> **V5 Foundation 冻结 ✅ | 优先级：Quality Improvement →**
> 更新：2026-07-11 04:02 | 当前阶段：**Foundation 完成，进入 Quality Improvement**
> 
> **里程碑时间线：**
> - 2026-07-09：Engine Era ✅ 冻结 → Reader Era 启动
> - 2026-07-10：**V5 Foundation 冻结**（V5.4 → V5.4.1 → V5.4.2）
> - 2026-07-10：**Phase C-1 Batch 2 完成** — 10 章连续运行验证通过
> - **Continuity Score 81.0/100**（Runtime 100 · Feedback 89 · Belief 52 · Narrative 76）
> - **2026-07-11：优先级路线图冻结** — 三类优先级的正式定义和排序
> 
> **V5 Foundation 层级总览：**
> 
| Layer | Status | Next |
|:------|:------:|:----:|
| V5 Foundation | ✅ 完成 | 不再改基础设施 |
| Runtime / Contract / Prompt | ✅ 冻结 | 仅做回归测试 |
| Continuity Score v1 | ✅ 建立 | 作为长期度量基线 |
| Quality Improvement | ⏳ 下一阶段 | 成为研发主线 |
> 
> 项目根：`/home/laogao/Documents/trae_projects/1234/novel_writing_system/`

---

## 一、规模

### 代码总量

| 类别 | 文件数 | 代码行数 |
|------|:------:|:--------:|
| Python 全部 | 8,119 | 306,321 |
| 核心模块 opentale/app/ | 277 | ~59,600 |
| V3 子系统 opentale/v3/ | 70 | ~37,600 |
| 测试（tests/ + v3/tests/） | 125 | ~22,700 |
| 脚本（scripts/ + opentale/scripts/ + .sh） | 43 | — |
| Markdown 文档 | 227+ | — |

### 小说产出

| 指标 | 数值 |
|------|:----:|
| 项目数 | 111（含测试/备份） |
| 实际有章节的项目 | ~30 |
| 章节总文件数 | 4,438 |
| 总字数（bytes） | ~18,033,011（约 1,800 万字） |
| 最大项目 | 文明观测者（537 章） |

### Prompt 模板

| 类别 | 数量 | 内容 |
|------|:----:|------|
| writing/ | 14 | 起草、大纲、CoT、系统提示、风格规则 |
| production/ | 7 | 章节规划、角色设计、正文、编辑评审 |
| constraints/ | 12 | 体裁边界×9 + 反重复/情感深度/现实逻辑 |
| agents/ | 10 | 对抗编辑、角色设计、评论家、伏笔等 |
| narrative_codex/ | 5 | 体裁叙事法典 |
| humanize/ | 8 | 激进/温和重写、风格克隆 |
| memory/ | 5 | 压缩摘要、记忆提取 |
| judge/ | 1 | 编辑质量评判 |
| planning/ | 2 | 跨卷规划、卷大纲 |
| archetype_maps/ | 5 | 原型图 |
| fallback/ | 7 | 降级 JSON 模板 |
| outline/ | 3 | OutlineDB 三层构建（卷→弧→章）|

**总数：约 80 个 prompt 文件**

---

## 二、整体架构（V4.5 最终态）

### 生产管线（Production Pipeline）

```
输入模式（4种）
  idea / prompt / plot / outline
    ↓
结构生成（LLM）
  StoryOutline → World + Characters → ChapterSpecs → SceneCards → SceneBeats
    ↓
约束装配（一次性）
  ConstraintBundle.build_all() → projects/<id>/constraints/
    ↓
正文生成（逐章 LLM）
  ChapterDraft → Director → Writer
    ├── 解场景节拍 / 角色声线 / 意象生命周期
    └── ChapterReview（critique + revise 循环）
    ↓
质量监控全集
  ├── FullBookReview / ArcContinuity / SuspenseEngine
  ├── ForeshadowPayoff / RepetitionDetector
  ├── AdversarialEditor / StructuralEditor / ProseSimplifier
  ├── LLM Judge / NarrativeEnergy / PlotReasoner
  └── Readability / EntityAuditor / WorldEventManager
    ↓
Export Package → projects/<id>/
```

### 实验验证管线（V4.6 新增）

```
Experiment Framework
  ├── CLI: `opentale experiment run` (--variant / --matrix / --benchmark)
  ├── 注入点: generate_novel.py → constraint_bundle["_experiment"]
  ├── Integrity Gate: G1 VariantActivated → G2 PlanConsumed → G3 PromptInjected
  ├── L4 Execution Compliance: Evidence Coverage + Timing + Narrative Cost
  └── 6 题材冻结基准: benchmark/benchmark.json
```

### Planner & Compiler（V4.7 已冻结）

**V4.7 最终结论（2026-07-09 冻结）：** Signal Encoding 是 Phase 1 的真实失败点。Planner 的 Schema 不是 Control Signal，而是 Metadata。V4.7 Phase 0 实验通过 A/B/C/D 四组 Fixture + 双题材复现验证了：具有角色认知状态迁移结构的 Narrative Control Signal，比描述性 Metadata Signal 更容易诱导 Writer 产生不同的叙事决策。

**关键发现：** D（rich_metadata, 1088B > C 的 605B, PIS=0.00）的输出 ≈ A（metadata, PIS=0.00）的事件驱动叙事，证否了"更多信息 = 更好生成"的错误假设。

**V4.7 冻结产物：**
- 新公理 5：Plan = Narrative Control Signal，而不是 Story Instructions
- 新公理 6：Writer 不负责理解剧情，Writer 负责将编码好的认知状态展开成可读文本
- Writer 接口改为 `NarrativeControlBundle`（见十）

**V4.7 冻结的架构方向（NarrativeController 输出结构）：**

```
ChapterPlan (当前 — Narrative Metadata)
  intent: "推进章节X的剧情发展"          ← 信息熵 ≈ 0

ChapterPlan (V4.7 — Narrative Control Signal)
  narrative_goal: "让林晨从相信日报转变为怀疑日报"
  belief_transition:
    before: "日报记录未来不可改变"
    after: "日报可能正在制造未来"
  conflict:
    external: "调查员追查异常报道"
    internal: "是否相信自己的记忆"
  mandatory_events: ["发现矛盾证据", "错误解释证据", "重新定义问题"]
  forbidden_resolution: ["不能提前揭露系统真相"]
```

核心变化：从字段数量（Schema 问题）转向信号强度（Control Signal 问题），重新接入 Observation→Evidence→Belief→Intent→Goal 的认知链。

Compiler（当前 — 线性编译）
  输入: Declaration Intent + Transition Feasibility
  输出: Evidence Contract (可执行约束集)
  未来: 需支持可行性分析和约束冲突检测

### V3 认知模拟子系统

```
Runtime（离线认知模拟）
  ├── simulation_kernel.py — 主循环
  ├── d1_runner.py — Benchmark 运行器
  ├── c3_loop.py — C3 实验框架
  └── 8 引擎系统

8 大引擎（总计 7,203 行）
  ├── commitment_engine.py (1,183) — 承诺生命周期
  ├── belief_engine.py (1,008) — 信念系统（D3 已冻结）
  ├── decision_engine.py (770) — 决策竞争
  ├── promotion_sync.py (621) — 信念晋升同步
  ├── promotion_engine.py (539) — 信念晋升决策
  ├── world_event_engine.py (480) — 世界事件
  ├── world_engines.py (420) — 世界引擎
  └── (...其余轻量引擎)

Bridge（V3 → Writer 接口）
  路径: v3/bridge/
  职责: V3 信念状态 → 叙事快照 → Writer prompt
  状态: C2 阶段已验证（Bridge Benchmark v1.0）

Inference Engine（V4.5 新增）
  路径: v3/engines/inference_engine.py
  职责: Evidence → Latent Model 推断
  状态: Core 冻结（只修 Bug，不加架构）
```

### Ops 运营层

```
路径: opentale/app/ops/ + ops/
  ├── agent.py — 写作工单管理
  ├── inbox/ — 任务目录（YAML）
  ├── orchestrator.py — 任务编排
  └── self_heal.py / trajectory_recorder.py / diagnostic.py
```

---

## 三、V4.5 核心模块

### 三层分裂状态模型

| 层 | 示例 | 可信度 | 写入方式 |
|----|------|--------|---------|
| WorldState | device_active=true | ~1.0 | 直接写 |
| CharacterModel | Trust=0.43±0.12 | ~0.7 | Evidence→Inference |
| ReaderModel | interest=+0.08 | ~0.3 | 预测，永不确定 |

### 六条架构公理（Core 冻结 + V4.7 新增）

1. **Evidence is immutable.** 事实不可篡改，只记录可观测事件。
2. **All latent states are inferred.** 所有高层状态都来自推断，而非直接赋值。
3. **Planning targets evidence, not hidden states.** 规划的是将产生哪些证据，而不是直接操纵隐藏状态。
4. **Every model is replaceable because the protocol is stable.** 任何模型都可以替换，因为稳定的是协议，而不是实现。
5. **Plan = Narrative Control Signal, not Story Instructions.** （V4.7 冻结）Planner 输出必须包含 Observation→Evidence→Belief Transition→Intent Shift→Goal Conflict 的认知链。
6. **Writer unpacks encoded cognition, does not infer it.** （V4.7 冻结）Writer 不负责理解剧情，只负责将编码好的认知状态展开成可读文本。输入从 ChapterPlan 改为 NarrativeControlBundle。

### V4.5 完整管线

```
StoryState (event-sourced, 三层分裂)
    ↓
Planner → Intent (声明式)
    ↓
Compiler → Evidence Contract (可执行)
    ↓
Writer → Evidence (正文)
    ↓
Inference Engine → Model Update
    ↓
Director → Commit/Rollback
```

### Core 冻结清单（2026-07-09 起）

以下模块进入维护模式，只允许修 Bug：

| 模块 | 路径 | 冻结原因 |
|------|------|----------|
| Planner | opentale/app/planner/ | 占位符级别 Intent，但不加架构 |
| Compiler | opentale/app/compiler/ | 线性编译无可行性分析 |
| Inference Engine | v3/engines/inference_engine.py | V5 架构确定但暂不实现 |
| Evidence Store | v3/engines/evidence_store.py | Schema 已冻结 |
| Replay Engine | v3/engines/replay_engine.py | 功能完整 |
| Experience Learner | v3/engines/experience_learner.py | 跨验证有效（83%） |
| Belief Engine | v3/engines/belief_engine.py | D3 已冻结 |

---

## 四、V4.6 实验验证体系

### 三个验证问题（结论性答案）

| # | 问题 | 结论 | 证据 |
|---|------|------|------|
| Q1 | Planner 是否改变小说输出 | ✅ 通过（双题材验证） | Butterfly + Echo 差异显著 |
| Q2 | Inference 收益覆盖复杂度 | ⚠️ 需 SimulationKernel | 无独立 Kernel 时不能形成信念 |
| Q3 | Experience 学的是 Pattern 还是 Prompt | ✅ 跨作品有效（83%） | 转移学习验证 |

### Integrity Gate（G0–G4 + L4 四层）

Phase 1 审计揭示了完整因果链中存在一个被默认假设跳过的变量：**Signal Informativeness**。G0 Gate 是其直接产物。

| 级别 | 名称 | 验证内容 |
|:----:|------|---------|
| G0 | Plan Informativeness (PIS) | Plan 是否携带足够叙事信息（五维评分）|
| G1 | VariantActivated | 正确管线分支 |
| G2 | PlanConsumed | 注入链完整 |
| G3 | PromptInjected | Prompt 实际注入 |
| G4 | BehaviorChanged | 输出差异检测 |
| L4.0 | Constraint Compliance | 要求元素是否出现 |
| L4.1 | Narrative Placement | 是否在正确位置出现 |
| L4.2 | Causal Compliance | 是否按照原因链出现 |
| L4.3 | Belief Transition | 角色信念状态是否真的改变 |

**执行顺序：**
```
G0 PIS (五维评分)
 |
 +-- fail → 不进入 LLM
 |
 +-- pass
       ↓
     G1 → G2 → G3 → G4
       ↓
     L4.0 → L4.1 → L4.2 → L4.3
```

G0 源于 Phase 1 审计发现的缺失变量：**Signal Informativeness**。如果 Planner 输出的 intent 信息熵接近零（"推进章节X的剧情发展"），即使 G1/G2 通过，Writer 的决策空间也没有被改变。

### L4 Execution Compliance

| 子层 | 名称 | 检测内容 |
|:----:|------|---------|
| L4.0 | Evidence Coverage | 关键词匹配（当前太容易） |
| L4.1 | Timing Placement | earliest_chapter 违例（缺数据） |
| L4.2 | Narrative Cost | 约束密度/可读性（全为 0） |

### Benchmark Corpus

冻结于 `benchmark/benchmark.json`，6 题材不可修改：

| 题材 | 类型 | 来源 |
|------|------|------|
| butterfly | 科幻 | 原创 |
| echo | 科幻·记忆 | 原创 |
| memory_seven | 科幻·记忆七层 | benchmark |
| evening_bread | 都市 | benchmark |
| frost | 末世 | benchmark |
| wanfeng | 都市·记忆 | benchmark |

---

## 五、Phase 1 审计结论（2026-07-09）

### 通过项

- 12 组运行全部完成，零错误 ✅
- 注入链正确性验证通过（G1/G2 100%）✅
- L4 基础设施可运行 ✅

### 发现的问题

**🔴 高严重性：**

1. **Planner Intent 为占位符级别** — "推进章节 X 的剧情发展"对 LLM 无信息量
2. **三变体输出一致性失败** — evening_bread/frost/wanfeng 的 baseline/planner_only/planner_compiler 完全一致（逐字），仅在 memory_seven 产生差异
3. **L4.0 100% 覆盖率不可信** — 基于关键词匹配而非语义验证

**🟡 中严重性：**

4. **Prompt Fingerprint 记录机制脆弱** — 依赖函数属性导致 3/4 domain 丢失
5. **输出含元指令泄露** — Writer 将 Planner intent 混入正文
6. **L4.1/L4.2 无数据触达** — evidence_contract 缺少时序/密度字段

### 下一阶段路线（V4.7 冻结后更新）

**V4.7 已完成：** Phase 0（Butterfly）+ Echo 跨题材复现，A/B/C/D 四组 Fixture 验证通过。
**V4.7 冻结约定：** 不继续扩大 Benchmark，不继续增加生成，转为 ReaderOS。

**当前路线：**
```
V4.7 Signal Strength ✅ 冻结
  |
  +-- V4.7 实验结论已落地 → 不扩大
  |
  └-- 下一阶段不是扩展生成，而是增加"读者模拟"
      
ReaderOS（V4.8）
  ├── 检测读者什么时候困惑
  ├── 检测读者什么时候预测失败  
  ├── 检测读者什么时候情绪断裂
  └── 反向优化 NarrativeControlBundle 的认知编码
      ↓
闭环：
  Belief Engine → NarrativeController → Writer
      ↑                                       |
      └───── ReaderOS ← Feedback ←───────────┘
```

---

## 六、模块行数排名

### Production Pipeline

| 模块 | 行数 | 功能 |
|------|:----:|------|
| evaluation/ | 13,252 | 全编辑评估体系 |
| director/ | 7,263 | 导演管线 |
| writer/ | 5,070 | 写作引擎 |
| kernel/ | 5,445 | 内核 |
| chat_agent/ | 4,905 | LLM Agent 框架 |
| sie/ | 4,391 | 故事智能引擎 |
| service/ | 3,463 | Service 层 |
| directors/ | 2,727 | 四大导演 |
| polish/ | 2,591 | 润色 |
| pipeline/ | 1,789 | 管线编排 |
| emotion_director/ | 1,627 | 情感导演 |
| domain/ | 1,339 | 领域模型 |
| overseer/ | 1,330 | 监管层 |
| design/ | 1,351 | 场景设计 |
| narrative/ | 1,279 | 叙事/认知引擎 |
| planner/ | 807 | 规划 |
| governance/ | 792 | 治理 |
| state/ | 786 | 状态管理 |
| charbrain/ | 507 | 角色大脑 |
| worldsim/ | 468 | 世界模拟 |
| outline/ | 370 | OutlineDB |
| readeros/ | 2,745 | 读者认知诊断（Causal/Belief/Motivation）+ 反馈通路（Router/Policy/Feedback） |
| experiment/（CLI）| 695 | 实验框架 |

### V3 Engines

| 引擎 | 行数 | 状态 |
|------|:----:|:----:|
| commitment_engine | 1,183 | 活跃 |
| belief_engine | 1,008 | 冻结（D3） |
| decision_engine | 770 | 活跃 |
| promotion_sync | 621 | 活跃 |
| promotion_engine | 539 | 活跃 |
| world_event_engine | 480 | 活跃 |
| world_engines | 420 | 活跃 |
| action_executor | 380 | 活跃 |
| opportunity_engine | 366 | 活跃 |
| context_association_engine | 319 | 活跃 |
| interaction_engine | 266 | 活跃 |
| need_engine | 260 | 活跃 |
| activity_engine | 214 | 活跃 |
| discovery_engine | 144 | 活跃 |
| social_engine | 138 | 活跃 |
| observation_bus_engine | 32 | 活跃 |
| **总计** | **7,203** | |

---

## 七、V4.7 关键结论与 Writer 接口冻结

### 实验结论（正式冻结）

> 在固定模型、固定故事条件下，具有角色认知状态迁移结构的 Narrative Control Signal，比描述性 Metadata Signal 更容易诱导 LLM Writer 产生不同的叙事决策。

### 两条新增公理

| # | 公理 | 来源 |
|---|------|------|
| 5 | **Plan = Narrative Control Signal**，而不是 Story Instructions。Planner 必须输出 Observation→Evidence→Belief Transition→Intent→Goal 的认知链。 | V4.7 Phase 0 |
| 6 | **Writer unpacks encoded cognition**，不负责推断角色动机或铺设认知路径。Writer 的输入从 ChapterPlan 改为 NarrativeControlBundle。 | V4.7 Phase 0 |

### Writer 接口冻结定义

旧接口（不再使用）：
```python
class ChapterPlan:
    intent: str          # "推进章节X的剧情发展" ← 信息熵≈0
    goal: str
    scene_cards: list
```

新接口（冻结）：
```python
@dataclass
class NarrativeControlBundle:
    """
    Writer 唯一接受的输入。
    Writer 不负责理解剧情——只负责将编码好的认知状态展开成可读文本。
    """
    observation: list[ObsFact]      # 可观测事实
    evidence: list[Evidence]        # 事实的意义
    belief_transition: list[BeliefShift]  # from → to
    intent_shift: list[IntentShift]       # from → to
    goal_conflict: list[GoalConflict]      # external + internal
```

### ReaderOS 检测器冻结状态

#### ✅ R1.0 Causal Gap Detector（2026-07-09 冻结）

> 跨段滑动窗口检测，已标注误报 1 边界。
> 路径：`opentale/app/readeros/detectors/causal.py`

#### ✅ R1.1 Belief Gap Detector（2026-07-09 20:43 冻结）

> 两个原型检测器：
> - **cognitive_bridge** — 角色经历意识/决策/情感跃迁时周围缺少认知动词连接
> - **entity_attribution** — 亲属称谓性别与主角代词冲突
> 验证集：晚风 ch1 + 寒潮 ch1，0 误报 ✅
> 路径：`opentale/app/readeros/detectors/belief.py`

#### ❌ R1.2 Prediction Break Detector（未启动）

#### 三基石完成 → 下一阶段：R1 → R2 桥接器（Adapter）

将 R1 Diagnostic（CausalGapDiagnostic / BeliefGapDiagnostic）转换为 R2.0 Finding Schema，
在真实章节上生成大量 Finding 验证路由稳定性。

---

### 下一阶段：ReaderOS R0（最小模型）

三个核心指标（直接对应 OpenTale 当前三个主要问题）：
| 指标 | 问题 | 对应问题 | 状态 |
|------|------|---------|:----:|
| Causal Gap | 事件 A 是否提供足够理由导致 B？| 事件突然出现 | ✅ R1.0 |
| Belief Gap | 角色变化是否有认知路径？| 人物漂移 | ✅ R1.1 |
| Prediction Break | 读者预测被合理打破还是被作者直接宣布？| 读者看不懂 | ❌ 待启动 |

完整闭环（V5 目标）：
```
Belief Engine → NarrativeController → Writer → Text
                     ↑                              |
                     └── ReaderOS R0 ← Feedback ←────┘
```

**为什么不先升级 Writer：** 已经证明 Writer 不是最大瓶颈。
Phase 1 找到了 Signal 层的缺失。下一步找 Reader 层。
否则容易回到"生成能力越来越强，但作品越来越像给分析师看的"。

### Reader Era 开发纪律

自 2026-07-09 起，OpenTale 划分两个时代：

| 时代 | 范围 | 目标 | 状态 |
|:----:|------|------|:----:|
| Engine Era | V1–V4.7 | 系统会写、会控制 | ✅ 冻结 |
| Reader Era | ReaderOS → | 普通读者愿意一直看下去 | ⬜ 启动 |

任何新模块必须回答三个问题才能立项：

1. **解决的是哪个读者问题？**（人物漂移/情节突兀/反转生硬）
2. **能否通过 ReaderOS 指标证明有效？**（Before/After 可测量）
3. **普通读者能感觉出来吗？**（AI 评分≠读者感知）

答不出任何一题→暂缓开发。

**设计草案：** `docs/READEROS_R0_DESIGN.md`（设计就绪，等待启动）
**架构原则更新：** `docs/ARCHITECTURE_PRINCIPLES.md`（新增公理 5-7、开发纪律、Reader Era 定义）

---

## 八、依赖与配置

| 依赖 | 用途 |
|------|------|
| Python 3.12 | 运行时 |
| FastAPI | HTTP 服务 |
| Pydantic | 数据模型 |
| DeepSeek / OpenAI API | LLM 调用 |
| SiliconFlow / Cooper / Ollama | LLM Provider 链 |
| config/default.yaml | 默认配置 |
| ~/.config/opentale/config.json | 用户 API keys |

CLI 入口：`opentale/cli.py` — `generate / resume / rewrite-chapter / experiment / list-projects`

---

## 九、关键文档索引

| 文档 | 内容 |
|------|------|
| 文档 | 内容 |
|------|------|
| `docs/SYSTEM_OVERVIEW.md` | 本文 |
| `docs/ARCHITECTURE_PRINCIPLES.md` | **架构原则（7 条公理 + Reader Era 开发纪律 + 新模块三道门）** |
| `docs/READEROS_R0_DESIGN.md` | **ReaderOS R0 设计（约束 + 三个断裂检测器 + Chapter Blind Test + RCR KPI）** |
| `docs/V4.7_FREEZE_MILESTONE.md` | **V4.7 冻结里程碑（Reader Era 启动宣言）** |
| `docs/V4.7_SIGNAL_STRENGTH_FINAL_REPORT.md` | V4.7 实验结项报告 |
| `docs/V4.6_EXPERIMENT_PROTOCOL.md` | 实验协议（model/seed/metrics/baseline 冻结） |
| `docs/V4.6_FREEZE_CRITERIA.md` | 冻结条件与门控规则 |
| `docs/V4.6.2_PHASE1_AUDIT.md` | Phase 1 实验审计报告 |
| `docs/V46_VALIDATION_REPORT.md` | V4.6 验证报告 |
| `docs/EVIDENCE_SCHEMA.md` | Evidence Schema 定义（冻结） |
| `benchmark/benchmark.json` | 6 题材冻结基准 |

---

## 十、V5 Foundation & Phase C（2026-07-10 冻结）

### V5 Foundation 里程碑

V5 验证链（自底向上），全部冻结：

```
Classic Pipeline Baseline  ✅  Frozen
  └── V5.4 Runtime Activation       ✅  Frozen
        └── V5.4.1 Prompt Consumption   ✅  Frozen
              └── V5.4.2 Spec Metadata  ✅  Frozen
```

| 里程碑 | Code Evidence | Runtime Evidence | 日期 |
|:-------|:-------------:|:----------------:|:----:|
| Classic Pipeline Baseline | ✅ | ✅ | 2026-07-10 |
| V5.4 Runtime Activation | ✅ | ✅ | 2026-07-10 |
| V5.4.1 Prompt Consumption | ✅ | ✅ | 2026-07-10 |
| V5.4.2 Spec Metadata Activation | ✅ | ✅(Cold Start ⚠️) | 2026-07-10 |

### 三层证据框架（验收标准）

2026-07-10 起所有功能按此三层验收：

| Layer | 证明内容 | 失败根因 |
|:-----:|----------|:--------:|
| Layer 1 | **Code Evidence** — 代码实现、接口连接、测试覆盖 | 实现问题 |
| Layer 2 | **Runtime Activation** — 运行时信号真正流动 | 接线问题 |
| Layer 3 | **Business Outcome** — 业务行为发生预期变化 | 算法/策略/模型 |

### Phase C（Continuity Validation）

**目标：** 验证 V5 Foundation 在连续长篇创作中的稳定性，而非再扩展功能。

#### Batch 1（Ch1–5，通过 resume）

| 指标 | 结果 |
|:-----|:----:|
| 完成 | 5 章 LLM 生成 ✅ |
| 问题 | Ch4 因 exec 900s 超时中断 → resume 续写完成 |
| Runtime 暴露 | 两项 P0：Review 无外层 deadline、exec budget 不足 |

**修复项（2026-07-10 21:25–21:40）：**
1. **P0-1 Review Timeout** — `chapter_drafter.py` 新增外层 `asyncio.wait_for`（max(300s, target_words//500×60)），超时 fallback 到本地 `PublishabilityReviewer.review()`
2. **P0-2 Exec Timeout** — exec timeout 900s → 1800s

#### Batch 2（Ch1–10，全新 generate）

| 指标 | 值 |
|:-----|:--:|
| 章节 | 10/10 ✅ |
| 总耗时 | 27.8 min (1668s) |
| 总字数 | 33,453 字 |
| 崩溃 | 0 |
| 超时中断 | 0 |
| Silent Fallback | 0 |
| 1800s 预算占用 | 92.7% |
| Review deadline 触发 | 0（所有 review 45–105s 内完成） |

### 三项连续性验证结论

#### 1️⃣ Runtime Continuity ✅
- 10/10 章，零故障
- Gateway diagnostics: 4 结构调用全部 ok，零失败
- Layer 2（Runtime）已从主要风险项降级为稳定状态

#### 2️⃣ Narrative Continuity ✅
| 信号 | 持续率 |
|:----|:------:|
| NCE 注入 | 10/10 (100%) |
| Foreshadow Report | 10/10 (100%) |
| Suspense Report | 10/10 (100%) |
| Emotional Direction | 10/10 (100%) |

**角色弧：** 林川属性连续 10 章演进（Fear/Trust/Anger/Loneliness/Resolve/Hope 跨章变化）
**情感弧：** shock → anticipation → sadness → burn（完整）
**读者保留率：** 60%（四导演共识）
**Canon Ledger：** 3 角色 · 23 时间线事件 · 9 线索跟踪 · 0 关系丢失

#### 3️⃣ Cognitive Continuity ✅
| 信号 | SSR | 说明 |
|:----|:---:|:-----|
| NCE 注入 | 10/10 (100%) | 每章认知信号持续注入 |
| Intent | 10/10 (100%) | Planner Intent 每章传递 |
| Belief Snapshot | 4/10 (40%) | Ch7起稳定，Cold Start 特性 |
| Evaluation Feedback | 8/10 (80%) | Ch1 首章无反馈，Ch6 零违规无反馈 |
| Contract 字段消费 | 6/6 (100%) | 零缺失 |

**Belief 累计效应（逐章）—— Cold Start 基线：**
```
Ch1–6: 0B (Cold Start ≈ 6 章) ← 基线参数
Ch7:   56B (≈1–2 Beliefs)
Ch8:   56B (≈1–2 Beliefs)
Ch9:   56B (≈1–2 Beliefs)
Ch10: 103B (≈3–4 Beliefs) ← 增长，显示累计
```

> **Cold Start 基线固定 — 不做优化目标（2026-07-10 决策）：** Cold Start ≈ 6 章是一个可测量参数。未来 Belief Engine 优化后，对比点是 Cold Start 从 6 章→3 章，而非急于提高绝对分数。不因基线较低而修改算法。

**Feedback 完整闭环链路：**
```
Ch1: 首章跳过
Ch2–5: ✅ Generated → ✅ Consumed → ✅ Writer Changed
Ch6:  ❌ (0违规, 条件性空反馈)
Ch7–10: ✅ 全链路
闭环率: 8/9 = 89%
```

### Issue Register（全部 Layer 3，不阻塞）

| # | 描述 | 章节 | 归类 |
|:-:|:-----|:----:|:----:|
| 1 | Belief Snapshot Cold Start | Ch1–6 | 延迟成熟特性，非 Bug |
| 2 | Feedback 间隙（Ch5 零违规）| Ch6 | 条件性行为，非 Bug |
| 3 | Adversarial Engine ImportError | 全程 | 已知优雅降级 |

### 关键文档

| 文档 | 路径 |
|:-----|:-----|
| V5 Foundation 冻结 | `stabilization/v5_foundation_freeze.md` |
| Phase C-1 计划 | `stabilization/c1_continuity_validation.md` |
| Batch 2 验收报告 | `stabilization/batch2_acceptance_report.md` |
| V5.4.2 冻结 | `stabilization/v542_spec_metadata_activation.md` |
| 经验记录 | `opentale_experience.yaml` |

### 阶段转换：从 Stabilization 到 Quality Improvement

2026-07-10 起，OpenTale 项目正式跨过工程分界点：

| 阶段 | 时间 | 描述 |
|:----:|:----:|:------|
| V5 Foundation | 已完成 | 所有 V5 信号链路冻结 |
| Phase C-0 | 已完成 | 真实 LLM 三章闭环可运行 |
| Phase C-1 Batch 1 | 已完成 | 暴露并定位 Runtime 瓶颈 |
| Phase C-1 Batch 2 | **已完成** | Runtime 稳定支持 10 章连续 LLM 生产 |
| **后续** | **待开始** | 重心转为**提高连续创作质量** |

后续新增能力（Belief 推理增强、ReaderOS、Director 策略进化）将建立在已验证的稳定运行时之上，并以 Continuity Score（见十一）为基线衡量改进。

### 冻结检查清单（V5 Foundation）

- [x] Classic Pipeline Baseline — 旧管线可运行
- [x] V5.4 Runtime Activation — NCE/Belief 信号注入 Writer
- [x] V5.4.1 Prompt Consumption — Writer 实际消费合约字段
- [x] V5.4.2 Spec Metadata Activation — Character Spec → active_chars → Observation Feed
- [x] Phase C-1 Batch 1 — 暴露并修复 Runtime P0
- [x] Phase C-1 Batch 2 — 10 章连续性验证四线全通过
- [x] Experience 记录 — `opentale_experience.yaml`
- [x] 冻结检查点 — `stabilization/v5_foundation_freeze.md`

---

## 十一、Continuity Score v1（2026-07-10 建立）

所有后续里程碑使用同一套指标衡量改进，禁止文字描述替换。

### 使用原则

- **Composite 用于汇报**（一句话讲清整体变化）
- **四项子分数用于研发**（定位退化发生在哪一层）
- V5.4 Baseline 不可修改——所有未来版本与此行比较

### 权重定义

| 维度 | 权重 | 子指标 | 测量方式 |
|:----:|:----:|:-------|:---------|
| Runtime | 30% | — | 章节完成率 / 故障率 / 预算占用 |
| Narrative | **拆为 Integrity + Quality** | 见下方 |
| Feedback | 20% | Generated→Consumed→Changed→**Effective** | 完整闭环率 + Quality Gate 变化 |
| Belief | 20% | NCE SSR + Snapshot SSR | NCE 100% + Snapshot SSR 加权 + Cold Start 参数 |

### Narrative 拆分为 Integrity + Quality

Narrative 现在混合了两种不同趋势，后续分别追踪：

| 子维度 | 权重(相对Narrative) | 测量 | 描述 |
|:------:|:-------------------:|:-----|:-----|
| **Integrity** | 50% | Canon 不矛盾 / Timeline 连续 / 角色状态不回退 / Foreshadow 兑现率 | **没写崩** |
| **Quality** | 50% | 四导演评分 / 读者保留率 / 情感弧完整性 | **写得好不好** |

### Feedback 四级链路

原三级链路扩展为四级：

```
Generated → Consumed → Writer Changed → Effective
                                               ├── Quality Gate 分数提高？
                                               ├── Director Score 提高？
                                               └── Violation 数减少？
```

**Effective** 验证 Feedback 不仅进入了 Prompt，而且真正产生了收益。当前 Batch 2 尚未追踪此项，计入待办。

### Batch 2 基线

```
Runtime   [30%] ████████████████████ 100/100
Feedback  [20%] ███████████████░░░░░  89/100  (Effective: 待追踪)
Belief    [20%] █████████░░░░░░░░░░░  52/100  (Cold Start ≈ 6章)
Narrative [30%] ███████████████░░░░░  76/100
  Integrity [15%] ██████████████████  95/100  (Canon 100%连续, Foreshadow 100%)
  Quality   [15%] ████████████░░░░░░  57/100  (四导演 75.98, 保留率 60%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Composite       ████████████████░░░  81.0/100
```

### 基线记录表（只追加，不修改）

| Version | Date | Runtime | Feedback | Feedback Effective | Belief | Cold Start | Narrative Integrity | Narrative Quality | **Composite** |
|:--------|:----:|:-------:|:--------:|:------------------:|:------:|:----------:|:------------------:|:----------------:|:-------------:|
| V5.4 Baseline | 07-10 | 100 | 89 | 待追踪 | 52 | ≈6章 | 95 | 57 | **81.0** |

### 计算规则

**Runtime** = 100 - 10×(failures) - 10×(timeouts) - 20×(silent_fallbacks)，下限 0
**Feedback** = (完整闭环数 / (总章节数-1)) × 100；Effective 层暂不缺省
**Belief** = (NCE_SSR% × 0.4 + Snapshot_SSR% × 0.6) × 100；Cold Start 参数单独记录，不纳入分数
**Narrative** = Integrity×0.5 + Quality×0.5（Quality = 四导演综合评分 × 0.75 + 读者保留率% × 0.25）

### 使用纪律

1. 每次架构变更后必须重算 Continuity Score（同项目、同模型、同配置）
2. 拒绝任何没有 CS 对比的 PR 评审或里程碑声明
3. Composite 波动 ±3 以内视为无明显变化，±5 视为显著变化，±10 视为方向性转变
4. 退化层必须定位到四项子分数之一才能批准修改
5. V5.4 Baseline 不可修改——只追加新行

### 验证结论

> ReaderOS 第一条反馈神经通路已验证成立，但尚未验证真实 Engine 肌肉执行能力。

R2.0 证明了一个抽象的读者认知失败，可以经过 诊断→归因→路由→有限干预→重新验证 的闭环被系统消化。

### 完整拓扑

```
Reader State Failure
        ↓
Finding (E.g. unsupported_decision, decision_acceptance=-0.42)
        ↓
AttributionRouter (ownership.layer + ownership.domain → pipeline)
        ↓         pipeline=planner, sub_pipeline=character_motivation
RepairPolicy (failure_mode → cognitive diagnosis targets)
        ↓         6 认知维度, intervention_locus, constraints
Bounded Intervention (strengthen_existing, 非 add_event)
        ↓
Reader Re-evaluation (验证前后状态变化)
        ↓
Finding Status Update: closed OR new Finding generated
```

### 两个关键分支

| 分支 | 输入 | 输出 | 验证的性质 |
|:----:|:----:|:----:|:----------:|
| **成功** | decision_acceptance = -0.42 | -0.05, failure closed | 系统可以关闭原始失败 |
| **不足** | decision_acceptance = -0.42 | -0.40, new Finding | 系统不接受"修了一点点就算完成" |

不足分支验证了 **Repair ≠ Ignore**：系统不会因为发生任何变化就宣布成功，而是继续接受 ReaderOS 验证。

### 新增组件

| 组件 | 路径 | 职责 |
|:----:|:----|:-----|
| Finding Fixture | `tests/fixtures/readeros/r2_golden_001.py`, `.json` | R2-GOLDEN-001: 回声 ch4 P194 林晨 unsupported_decision |
| AttributionRouter | `opentale/app/readeros/attribution_router.py` | (layer, domain) → Engine Pipeline; 不执行修复，只路由 |
| PlannerRepairPolicy | `opentale/app/readeros/repair_policy.py` | failure_mode → 6 认知维度 + 干预焦点 + 结构红线; 输出 RepairPlan，非文本修改 |
| 结构闭环测试 | `tests/readeros/test_attribution_router.py` (6 tests) | Router 路由正确性 |
| | `tests/readeros/test_repair_policy.py` (6 tests) | RepairPolicy 维度/约束/边界 |
| | `tests/readeros/test_closed_loop_4a.py` (5 tests) | 全链路闭环验证 |

### 路由表示例

| (layer, domain) | → pipeline | sub_pipeline |
|:----------------|:----------:|:------------:|
| planner / character_motivation | planner | character_motivation |
| planner / goal | planner | goal |
| planner / belief | planner | belief |
| writer / entity_consistency | writer | entity_consistency |
| outline / narrative_structure | outline | — |
| unknown / unknown | review | manual (fallback) |

### RepairPolicy 输出约束

| 约束 | 内容 |
|:-----|:-----|
| **preserve** | character_identity, canon, plot_direction |
| **forbidden** | main_plot_rewrite, character_replace, random_conflict_injection |
| **干预类型** | strengthen_existing, reveal_hidden, connect, intensify, clarify |
| **禁止的干预** | add_event, text_patch, replacement_text, rewrite_target |

## 十二、V5 Foundation 后路线图（2026-07-11 冻结，2026-07-11 修正）

### 修正说明

原 §十二 列有四步执行顺序，其中 Step 1「Evaluation Timeout Guard」基于一个被后续审计证伪的假设——
`chapter_evaluator.py` 和 `auto_rewrite.py` 的 LLM 调用缺 timeout 保护。

2026-07-11 04:12–04:33 的完整调用链审计证明：
- `chapter_evaluator.py` 和 `auto_rewrite.py` **不直接调用 LLM**，属于误判
- 所有生产热路径 LLM 调用最终统一经过 `GatewaySupport`，超时保护已在入口层集中实现
- `deep_editor.py` 的 `self._runtime.completion()` 并非无保护调用——在 `RuntimeSupport` 上该**方法根本不存在**，属 Dead Code Path，被 `try/except` 静默吞掉

**修正后：原 Step 1 移除，P0 关闭（No Code Change Required）。**

### 状态总览

| 层级 | 状态 | 后续动作 |
|:------|:----:|:--------|
| V5 Foundation | ✅ 完成 | 不再改基础设施 |
| Runtime / Contract / Prompt | ✅ 冻结 | 仅回归测试 |
| Continuity Score v1 | ✅ 建立 | 长期度量基线 |
| Runtime Timeout Audit | ✅ PASS | Closed（No Code Change） |
| **Quality Improvement** | ⏳ **下一阶段** | **研发主线** |

### 基线（V5.4 Baseline）

| 维度 | 分数 | 含义 |
|:----|:---:|:------|
| Runtime | 100 | 基础设施稳定 |
| Feedback | 89 | 闭环成立，缺 Effective 证据 |
| Belief | 52 | Cold Start≈6章，运行特性 |
| Narrative Integrity | 95 | 连续性可靠 |
| Narrative Quality | 57 | 提升空间最大 |
| **Composite** | **81.0** | 所有未来版本锚点 |

### 审计证据：所有生产热路径 LLM 调用已受统一保护

| 调用点 | 实际入口 | Timeout | 状态 |
|:-------|:---------|:-------:|:----:|
| writer_executor `_llm_chat` | 自有 `asyncio.wait_for` | ✅ | PASS |
| chapter_drafter review | `_llm_chat` → `asyncio.wait_for` | ✅ | PASS |
| llm_judge | `gateway.post_chat()` → GatewaySupport | ✅ | PASS |
| repair_executor | `gateway.execute()` → GatewaySupport | ✅ | PASS |
| rewrite_executor | `gateway.execute()` → GatewaySupport | ✅ | PASS |
| deep_editor | `self._runtime.completion()` | ❌ **方法不存在** | BROKEN（见 Dormant） |

### 执行顺序（2026-07-11 老高锁定，修正版）

| 步骤 | 内容 | 分类 | 耗时预期 |
|:----:|:-----|:----:|:--------:|
| **1** | Feedback Effective（补齐最后一层闭环） | 🟠 P1 | 主线 |
| **2** | Benchmark Dataset（长期评测能力） | 🟡 P2 | 中等 |
| **3** | Narrative Quality Research（有稳定评测后迭代） | 🟠 P3 | 长期 |

#### 🟠 Step 1: Feedback Effective（最重要研发任务）

**现状：**
```
Generated → Consumed → Writer Changed (闭环率 89%)
                  ↓
            ? Effective（缺数据）
```

**先定义指标，再实现统计，再讨论改进：**
- Quality Gate 分数是否提高？
- Director 综合评分是否提高？
- Reader Retention 是否提高？
- Revision 后同类问题是否减少？
- 下一章是否减少相同类型反馈？

> 如果 Feedback Effective 没完成，即使 Director、ReaderOS、Belief 全部升级了，也难以证明哪项改动真正改善了作品。

#### 🟡 Step 2: Benchmark Dataset（可与 Step 1 并行）

固定 Story Benchmark：
```
benchmark/
  mystery_small.yaml
  romance_small.yaml
  fantasy_small.yaml
  long_arc.yaml
```

任何版本（V5.5/V5.6/V6）跑同一套 Story Package → 生成 → Continuity Score → Reader Score → Composite。不同故事之间 Quality 才能横向比较。

#### 🟠 Step 3: Narrative Quality Research

不是一次性交付，是持续研发。在有稳定评测体系后迭代：
- Director Strategy v2
- ReaderOS Guidance
- Dialogue Policy
- Emotion Density
- Scene Compression
- Suspense Distribution

### 版本比较规则

| Version | Date | Runtime | Feedback | Effective | Belief | Cold Start | Integrity | Quality | **Composite** |
|:--------|:----:|:-------:|:--------:|:---------:|:------:|:----------:|:---------:|:-------:|:-------------:|
| V5.4 Baseline | 07-10 | 100 | 89 | — | 52 | ≈6章 | 95 | 57 | **81.0** |
| V5.5 | TBD | | | | | | | | **TBD** |
| V5.6 | TBD | | | | | | | | **TBD** |

每次升级后回答三个问题：
1. Composite 有没有提高？
2. 提高来自哪个子系统？
3. 有没有引入新的退化？——归因到 Layer 1（代码）/ Layer 2（信号）/ Layer 3（行为）

### 延期与休眠项

| 项 | 分类 | 状态 | 说明 |
|:---|:----:|:----:|:------|
| ReaderOS 深度介入 | Deferred | ⚪ 主动冻结 | 非待办，属独立 Phase |
| Belief Engine 算法优化 | Deferred | ⚪ 暂停投入 | 无架构问题，仅限 Algorithm Research |
| DeepEditor Runtime Integration | Dormant | 💤 静默断路 | `self._runtime.completion()` 在 `RuntimeSupport` 上不存在，被 try/except 吞掉 |

## 后记：R2.0 — ReaderOS → Engine 反馈回路验证（2026-07-09 封存）

> **此章节为历史归档。Reader Era 已主动冻结（Deferred），非待办。**
> 验证结论已写死在 §4B 测试基线中。

### 验证结论

> ReaderOS 第一条反馈神经通路已验证成立，但尚未验证真实 Engine 肌肉执行能力。

R2.0 证明了一个抽象的读者认知失败，可以经过 诊断→归因→路由→有限干预→重新验证 的闭环被系统消化。

### 完整拓扑

```
Reader State Failure
        ↓
Finding (E.g. unsupported_decision, decision_acceptance=-0.42)
        ↓
AttributionRouter (ownership.layer + ownership.domain → pipeline)
        ↓         pipeline=planner, sub_pipeline=character_motivation
RepairPolicy (failure_mode → cognitive diagnosis targets)
        ↓         6 认知维度, intervention_locus, constraints
Bounded Intervention (strengthen_existing, 非 add_event)
        ↓
Reader Re-evaluation (验证前后状态变化)
        ↓
Finding Status Update: closed OR new Finding generated
```

### 两个关键分支

| 分支 | 输入 | 输出 | 验证的性质 |
|:----:|:----:|:----:|:----------:|
| **成功** | decision_acceptance = -0.42 | -0.05, failure closed | 系统可以关闭原始失败 |
| **不足** | decision_acceptance = -0.42 | -0.40, new Finding | 系统不接受"修了一点点就算完成" |

不足分支验证了 **Repair ≠ Ignore**：系统不会因为发生任何变化就宣布成功，而是继续接受 ReaderOS 验证。

### 新增组件

| 组件 | 路径 | 职责 |
|:----:|:----|:-----|
| Finding Fixture | `tests/fixtures/readeros/r2_golden_001.py`, `.json` | R2-GOLDEN-001: 回声 ch4 P194 林晨 unsupported_decision |
| AttributionRouter | `opentale/app/readeros/attribution_router.py` | (layer, domain) → Engine Pipeline; 不执行修复，只路由 |
| PlannerRepairPolicy | `opentale/app/readeros/repair_policy.py` | failure_mode → 6 认知维度 + 干预焦点 + 结构红线; 输出 RepairPlan，非文本修改 |
| 结构闭环测试 | `tests/readeros/test_attribution_router.py` (6 tests) | Router 路由正确性 |
| | `tests/readeros/test_repair_policy.py` (6 tests) | RepairPolicy 维度/约束/边界 |
| | `tests/readeros/test_closed_loop_4a.py` (5 tests) | 全链路闭环验证 |

### 路由表示例

| (layer, domain) | → pipeline | sub_pipeline |
|:----------------|:----------:|:------------:|
| planner / character_motivation | planner | character_motivation |
| planner / goal | planner | goal |
| planner / belief | planner | belief |
| writer / entity_consistency | writer | entity_consistency |
| outline / narrative_structure | outline | — |
| unknown / unknown | review | manual (fallback) |

### RepairPolicy 输出约束

| 约束 | 内容 |
|:-----|:-----|
| **preserve** | character_identity, canon, plot_direction |
| **forbidden** | main_plot_rewrite, character_replace, random_conflict_injection |
| **干预类型** | strengthen_existing, reveal_hidden, connect, intensify, clarify |
| **禁止的干预** | add_event, text_patch, replacement_text, rewrite_target |

### R2.0 冻结声明

```
R2.0 证明了 ReaderOS 的第一条运动神经已经接入 Engine。
Phase 4B (Real Engine Integration) 不继续——
LLM 非确定性 / Revision 稳定性 / Canon 保持 / ReaderOS 重评估敏感度
应作为 R2.1 / R3 前置实验，不污染 R2.0 的第一次闭环证明。

后续进入 Phase 4B 时，问题从：
  "系统有没有反馈回路？"
变成：
  "真实 Planner/Revision Engine 能否稳定利用这条反馈回路？"
这是两个不同阶段。

R2.0 到此封存。🧠
```
