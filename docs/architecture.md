# OpenTale 架构图（三层体系 ）

> 更新日期：2026-06-29 | 基线：1223 passed / 0 failed / 6 skipped | 验证：《铁剑守山门》 — 30章仙侠 | 总字符：74,001 CJK | 审校均分 71.0（中位数 76）| 全书审查 85.0（通过） | 新增：IssuePatternTracker + EditorBrain

---

## 一、五层纵深

```
┌─────────────────────────────────────────────────────────────────────┐
│  输 入 层                                                           │
│  idea / prompt / plot / outline  +  genre  +  style_sample  +  mode │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  编 排 层                                   GenerateNovelPipeline  │
│  23 节点串行编排 → scaffold → draft → publish                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1 — 骨架（Screenwriter — 战略层：写什么 · 11 引擎在线）      │
│                                                                     │
│  PremiseScrutiny                                                    │
│       ↓                                                             │
│  outline ✦ ──→ world ✦ ──→ characters ✦ ──→ chapter_specs ✦       │
│                                                                     │
│  ✦ = 11 引擎在线 + 14/14 约束加载（已验证）                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1.5 — 约束装配（起草前冻结）                                  │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────────────────┐                │
│  │ConstraintBundle│    │    SIE Bundle（11 引擎）     │                │
│  │              │    │                             │                │
│  │ craft_rules  │    │ story_bible · causal_graph  │                │
│  │anti_repetition│   │ surprise_plan · emotion_curve│               │
│  │cast_constraint│   │ character_arcs · conflict_arc│               │
│  │voice_profiles │    │ narrative_strategy · reader │                │
│  │scene_beats   │    │ theme_schedule · global_style│                │
│  │emotional_arc │    │ mystery_graph                │                │
│  └──────┬───────┘    └─────────────┬───────────────┘                │
│         │                          │                                │
│         ▼                          ▼                                │
│  ┌────────────────────────────────────────────┐                     │
│  │  projects/<id>/constraints/ + sie_data/    │   落盘              │
│  └────────────────────────────────────────────┘                     │
│  ✅ G2 已修复：SIE narrative_strategy / emotion_target /             │
│     info_budget / rhythm_profile / theme_target / conflict_target   │
│     6 字段现由 _format_sie_strategies() 注入 draft_prompt           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2 — 逐章起草（Director 2.0 战术层 + Writer 执行层）           │
│                                                                     │
│  ChapterDrafter（每章循环）                                          │
│       │                                                             │
│       ├── context_merge（约束 + SIE Blueprint + Director → ctx）     │
│       │                                                             │
│  ┌──────────────────────────────┐  ┌────────────────────────────┐ │
│  │ Director 2.0 (A→H)          │  │   WriterExecutor           │ │
│  │ + 4.10-4.13 核心模块        │  │                            │ │
│  │                              │  │  write_with_package() ←─── │ │
│  │ A: ContextAssembly           │  │  (读取 WriterPackage，      │ │
│  │ B: ConstraintFusion          │  │   不重新拆场景)             │ │
│  │ C: DecisionEngine            │  │                            │ │
│  │ D: StrategyEngine            │  │  SceneDecomposer → fallback│ │
│  │ E: SceneDesigner             │  │                            │ │
│  │ F: PromptCompiler            │  │  2 版本择优                 │ │
│  │ G: RuntimeValidator          │  │  (可配置 evaluation_weights)│ │
│  │ H: PackageBuilder            │  │                            │ │
│  │                              │  │  _revise_until_publishable  │ │
│  │ 4.10 CrossChapterValidator   │  │  (revised: max 4 rounds)   │ │
│  │ 4.11 StyleTracker            │  │  LinePolishService         │ │
│  │ 4.12 PacingController        │  └───────────┬────────────────┘ │
│  │ 4.13 ContextGapAnalyzer      │              │                  │
│  │                              │              │                  │
│  │ → WriterPackage              │              │                  │
│  │   (SceneCard + Beat +        │              │                  │
│  │    POV + EmotionArc)         │              │                  │
│  └──────────────────────────────┘              │                  │
│     ✅ G1：WriterPackage 通路 + ScenePlanAdapter │                 │
│                                      CanonLedger 更新               │
│                                      StoryAnalytics                  │
│                                      Checkpoint 落盘                │
│                                                                     │
│  ✅ G3 已修复：genre_boundary.txt 仅由 prompt_builder.py 注入一次    │
│                                                                     │
│                                                                     │
│  🔬 P3 情绪高潮评分（2026-06-29 新增）                              │
│     EmotionalClimaxScorer.score_chapter() → 高潮节点情感释放深度      │
│     认知回避检测（她知道/他意识到→扣分）                            │
│     情感回避检测（沉默/不说话→扣分）                                │
│     身体信号加分（眼眶红了/声音颤抖/心揪紧）                       │
│     build_revision_block() → 注入 revision prompt 尾部              │
│                                                                     │
│  🔬 P4 修订记忆（2026-06-29 新增）                                  │
│     RevisionMemory: 跨轮次 issue 跟踪 + 振荡检测（≥3轮同一 issue）  │
│     build_context_block() → 注入上一轮修订摘要                      │
│     JSON 持久化到 .revision_memory/chXXX.json                       │
│                                                                     │
│  ⚡ 优化调整（2026-06-28）                                           │
│  · 字数目标 1800→1500（降低起草压力）                                │
│  · 修订轮次上限 max 6→4（加速收敛）                                 │
│  · ContextGap 拦截阈值 0.6→0.4（减少误阻拦）                        │
│  · 修订/起草超时 45/60→75s（减少无谓 fallback 链）                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 3 — 后处理                                                    │
│                                                                     │
│  BookRepairPipeline → PublishFlowPipeline → AuditOrchestrator        │
│         → FullBookReviewer → Export (.txt + .md)                    │
│                                                                     │
│  ✅ G4 已修复：漂移章节 >50% 时 raise RuntimeError abort             │
│  ✅ G5 已修复：export 全权移交 ensure_export_ready()，仅做一次        │
│  ✅ Q4 已修复：PublishFlow.run() 接受可选 sie_data 参数，内存优先    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  产 出                                                               │
│                                                                     │
│  projects/<id>/               output/<title>/（benchmark 集）        │
│    ├── manifest.json              ├── 01-xxx.md                     │
│    ├── manuscript.json            ├── 02-xxx.md                     │
│    ├── final_manuscript.txt       ├── ...                           │
│    ├── md/01-xxx.md               └── full_manuscript.txt          │
│    ├── canon_ledger.json                                           │
│    ├── constraints/                                                 │
│    ├── sie_data/                                                    │
│    └── checkpoints/content/                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、三层角色定义

| 层 | 文件 | 职责 | 健康度 |
|---|---|---|---|
| **Screenwriter** | `screenwriter/service.py` | 战略——决定写什么（outline/world/characters/specs） | ✅ 11/11 引擎在线 |
| **Director 2.0** | `director/`（12 文件） | 战术——决定怎么讲（A→H 八阶段管线） | ✅ 56 测试全部通过 |
| **Writer** | `writer/chapter_drafter.py` + `writer/writer_executor.py` | 执行——语言实现（draft / revise / polish） | ✅ 17 测试 |

---

## 三、修复记录（全部已完成）

```
编号  类型    状态  修复内容
────────────────────────────────────────────────────────────────────
B1    Bug     ✅   screenwriter→Director genre 传递修复
B2    Bug     ✅   _scene_genre_profile 补全 historical/horror/war
B3    Bug     ✅   writer_executor loop break 修复
G1    Gap     ✅   Director→Writer 通路：WriterPackage + ScenePlanAdapter
G2    Gap     ✅   SIE 6 字段注入 draft_prompt（_format_sie_strategies）
G3    Gap     ✅   genre_boundary 约束去重
G4    Gap     ✅   GenreGate 漂移 >50% 时 abort
G5    Gap     ✅   export 去重，仅 ensure_export_ready() 执行
Q1    质量    ✅   ScenePlan 字数分配分母修正
Q2    质量    ✅   MechanicalEvaluator 权重可配置
Q3    质量    ✅   director/service.py 空操作移除（Director 2.0 重写）
Q4    质量    ✅   PublishFlow sie_data 参数，内存优先
Q5    质量    ✅   test_execution.py SQLAlchemy 依赖消除
────────────────────────────────────────────────────────────────────
P3    新增    ✅   情绪高潮评分器（emotional_climax.py, 12 tests）
P4    新增    ✅   修订历史记忆（revision_memory.py, 13 tests）
```

---

## 四、测试覆盖现状

```
组件                    状态               验证内容
────────────────────────────────────────────────────
Screenwriter          ✅                 18 tests（含 16 项质量测试）
Director 2.0          ✅                 56 tests（53 单元 + 3 集成）
Director 4.10-4.13    ✅                 4 模块 · 共计 48 新 tests
  CrossChapterValid.   ✅                 12 tests
  StyleTracker         ✅                 11 tests
  PacingController     ✅                 13 tests
  ContextGapAnalyzer   ✅                 12 tests
ConstraintBundle      ✅                 pipeline 集成测试
Compiler              ✅                 有测试
Governance            ✅                 2 套测试
SIE 各引擎            ✅                 test_sie_engines.py
PromptBuilder         ✅                 31 tests（P3-1）
WriterExecutor        ✅                 7 tests（P3-2）
ChapterDrafter        ✅                 14 tests（P3-3）
SceneBeatManager      ✅                 18 tests
VoiceProfile          ✅                 15 tests
ThemeRegistry         ✅                 14 tests
StructuralEditor      ✅                 13 tests
OutputAuditor         ✅                 49 tests
AdversarialEditor     ✅                 15 tests（P4）
EmotionalClimaxScorer ✅                 12 tests（P3 — 新增）
RevisionMemory        ✅                 13 tests（P4 — 新增）
────────────────────────────────────────────────────
全量回归基线           ✅  1193 passed / 6 skipped
PublishFlow           ❌  无独立测试
Export (.txt/.md)     ❌  无独立测试
SIE Orchestrator      ❌  无独立测试
Domain models         ❌  无独立测试
```

---

## 五、数据流全景（更新后）

```
Input
  │
  ▼
GenerateNovelPipeline.run(request)
  │
  ├─ Step 1: Screenwriter 生成骨架
  │   ├─ premise_scrutiny()
  │   ├─ generate_outline()         → LLM
  │   ├─ generate_world()           → LLM
  │   ├─ generate_characters()      → LLM
  │   └─ generate_chapter_specs()   → LLM
  │
  ├─ Step 2: 约束装配（Phase 1.5）
  │   ├─ ConstraintBundle.build_all()  → 写入 constraints/
  │   ├─ SIEOrchestrator.run_all()     → 写入 sie_data/ + 返回 bundle
  │   └─ audit_scaffhold()             → AuditOrchestrator 验证
  │
  ├─ Step 3: 全书初始化（Director 2.0 Phase A + B）
  │   ├─ ContextAssembler.assemble()
  │   └─ ConstraintFusionEngine.fuse()
  │
  ├─ Step 4: 逐章起草（Phase C→H，每章循环）
  │   ├─ NarrativeDecisionEngine.decide()
  │   ├─ NarrativeStrategyEngine.plan()
  │   ├─ SceneDesigner.design()
  │   ├─ PromptCompiler.compile()
  │   ├─ RuntimeValidator.validate()
  │   ├─ WriterPackageBuilder.build()
  │   ├─ WriterExecutor.write_with_package()
  │   │   ├─ 2 版本择优
  │   │   ├─ _revise_until_publishable()
  │   │   └─ LinePolishService.polish_pass()
  │   ├─ CanonLedger / Analytics / Checkpoint
  │   └─ DirectorMemory.save()
  │
  ├─ Step 5: 后处理
  │   ├─ BookRepairPipeline
  │   ├─ PublishFlowPipeline（sie_data 内存优先）
  │   ├─ FullBookReviewer
  │   └─ Export (txt + md — 仅一次)
  │
  └─ Output: projects/<id>/ + output/<title>/
```

---

## 七、生成验证（2026-06-29）

### 《铁剑守山门》（仙侠 · 30 章 · 74,001 CJK）

**用户评估：「最像人类写的」那篇**

| 指标 | 结果 |
|---|---|
| 总字数 | 74,001 CJK |
| 生成耗时 | ~30 分钟 |
| 审校均分 | 71.0（中位数 76） |
| 全书审查 | 85.0（通过） |
| 元叙事泄露 | **零泄漏** |
| 角色名正确率 | 100%（赵石头/林鹤年/阿七/陈伯） |
| Sandbox 安全模式 | 全程未触发 |
| 修订循环 | max 4 轮，多数 2-3 轮收敛 |
| 基准集回归 | 5 章黄金集 · avg score 82.2 · 22 违规 · 零泄漏 |

### 跨篇对比分析

| 维度 | 《曙光梦境》| 《星武溯源》| 《铁剑守山门》 |
|---|---|---|---|
| 章节数 | 30 | 100 | 30 |
| CJK 字数 | 78,989 | 227,152 | 74,001 |
| 审校均分 | — | 61.0 | 71.0 |
| 泄漏控制 | 少量 | 少量 | **零泄漏** |
| P6 信息释放 | 波动 | 中等 | **稳定** |
| P7 结构完整性 | 中 | 中 | **完整** |
| P9 意象贯穿 | 一般 | 一般 | **强** |
| 类型隔离 | — | — | ✅ |

### 优化路径总结

| 项目 | 状态 | 文件 | 收益 |
|------|------|------|------|
| P5 潜台词编辑 | ✅ | polish/subtext_editor.py | 对话质量 |
| P6 读者模型 | ✅ | evaluation/reader_model.py | 信息释放节奏 |
| P7 节奏调度表 | ✅ | kernel/story_grid.py | 结构稳定 |
| P8 叙事声线 | ✅(强化) | polish/voice_profiles.py | 角色区分度 |
| P9 意象进化弧 | ✅ | evaluation/theme_registry.py | 主题深度 |
| P10 元认知审查 | ✅(强化) | polish/meta_inspector.py | 消除 AI 味 |
| **P3 情绪高潮** | ✅ **新增** | evaluation/emotional_climax.py | 情感释放深度 |
| **P4 修订记忆** | ✅ **新增** | evaluation/revision_memory.py | 防振荡/过度修正 |

**全量回归基线：1193 passed / 0 failed / 6 skipped**

---

## 八、优化路径（P5 → P10）

从《残响》（74K字 · 零泄漏 · avg 54.5）的读者级分析，识别出的六个提升通道：

| 等级 | 项目 | 文件 | 收益 | 需 LLM 调用？ | 状态 |
|------|------|------|------|-------------|------|
| P5 | 潜台词编辑器 | `polish/subtext_editor.py` | 对话质量陡升 | 否 | ✅ 已完成 |
| P6 | 读者模型 | `evaluation/reader_model.py` | 信息释放节奏 | 每章 1 次轻量 | ✅ 已完成 |
| P7 | 节奏调度表 | `kernel/story_grid.py` | 全书结构稳定性 | 否 | ✅ 已完成 |
| P8 | 叙事声线 | `polish/narrative_voice.py` | 角色区分度 | 写作前 1 次 | ✅ 已完成 |
| P9 | 意象进化弧 | `evaluation/theme_registry.py` 增强 | 主题深度 | 否 | ✅ 已完成 |
| P10 | 元认知审查器 | `evaluation/meta_cognitive.py` | 消除 AI 味 | 否 | ✅ 已完成 |

### P5 — 潜台词编辑器

**问题**：角色说得太多。对话停留在信息交换层面，缺少潜台词碰撞。

**原理**：
- 扫描所有「」对话段落
- 标记「信息性对话」——角色之间交换事实而不涉及情感碰撞
- 检测显式情绪宣告（「我很害怕」「我还在乎你」），评估是否改为动作或省略
- 计算潜台词密度（subtext ratio = 有情感维度对话 / 总对话字符数）
- 对密度低于阈值的段落，注入修订要求

**位置**：`chapter_drafter.py` 中 `LinePolishService` 之后、声线审计之前

### P6 — 读者模型

**问题**：系统不知道读者知道什么、不知道什么、在什么时间点知道什么。信息释放时，读者可能早就猜到了，也可能完全没跟上。

**原理**：每章生成后在 LLM 中跑一次 Reader Simulation：
1. 读完全文到当前章 → 列出读者已确定的事实
2. 列出读者合理猜测（2-3 条）
3. 下一章的信息释放应该推翻哪些猜测？生成哪些新疑问？

注入下一章 prompt 作为「读者预期」指引。

**调用成本**：每章一次轻量 LLM 调用（~200 token 输入 + ~150 token 输出）

### P7 — 节奏调度表

**问题**：章节评分波动大（31~74），缺乏全书级节奏规划。

**原理**：`chapter_specs` 生成后、draft 循环前执行一次 `StoryGridGenerator`，输出全书能量网格：

```
章号 | 叙事功能 | 张力目标 | 情感弧度 | 字数目标
1    | 开局     | 8/10     | 好奇     | 2500
7    | 缓一缓   | 4/10     | 感伤     | 1800
15   | 中局转折 | 9/10     | 震惊     | 3000
```

每章 prompt 注入「本章在全书的节奏位置」。

### P8 — 叙事声线

**问题**：POV 角色共用同一 AI 叙述声线。凌寒的叙述方式和顾北的叙述方式没有差异。

**原理**：写作前用 2-3 句风格样本 + 角色性格参数，生成 Narrative Voice Sheet：
- 句长偏好
- 感官通道偏好
- 修辞倾向
- 注意力过滤

注入每章 system prompt。

### P9 — 意象进化弧

**问题**：同一意象（如「回声」）在全书中每次出现的方式一样，意象不随故事推进而「成长」。

**原理**：ThemeRegistry 增强：为每个活跃意象附加 `call_context` 列表，比较最新调用与前几次调用在意境、情感色彩上的差异。若差异不足，标记并触发修订。

### P10 — 元认知审查器

**问题**：LLM 写的 prose 有一个隐蔽但致命特征——它解释一切。每个转折、每个情感变化、每个意象都会在出现后不久被「确认」或「解释」。

**原理**：全书生成后的 StructuralEditor pass 中，增加 Explanatory Clause Detector：
1. 找到「确认前文暗示」的句子（「果然，XX 是 YY 的原因」）
2. 找到「重复前文情绪」的句子（「她终于明白了那个眼神的含义」）
3. 找到「总结段」（段落最后一句解释前文意义）
4. 有 30% 概率删除，20% 概率改写为更含蓄的表达


## 六、关键文件清单

```
opentale/
├── app/
│   ├── service.py               — 主编排器（AutonomousNovelSystem）
│   ├── pipeline/
│   │   ├── generate_novel.py    GenerateNovelPipeline
│   │   ├── publish_flow.py      PublishFlowPipeline（sie_data 参数）
│   │   ├── book_repair.py       BookRepairPipeline
│   │   └── resume_project.py    ResumeProjectPipeline
│   ├── screenwriter/service.py  — 11 引擎（Phase 1）
│   ├── director/                — Director 2.0（12 文件，全 H）
│   │   ├── models.py            NovelRuntimeContext / WriterPackage
│   │   ├── context_builder.py   Phase A
│   │   ├── constraint_fusion.py Phase B
│   │   ├── decision_engine.py   Phase C
│   │   ├── strategy_engine.py   Phase D
│   │   ├── scene_designer.py    Phase E（5 genre profiles）
│   │   ├── prompt_compiler.py   Phase F
│   │   ├── runtime_validator.py Phase G
│   │   ├── package_builder.py   Phase H
│   │   ├── director_memory.py   记忆持久化
│   │   ├── pipeline.py          A→H 编排器
│   │   └── service.py          统一入口
│   ├── writer/
│   │   ├── chapter_drafter.py   — 每章起草循环
│   │   ├── writer_executor.py   — LLM draft + revise（write_with_package）
│   │   ├── scene_decomposer.py  — fallback 场景拆分
│   │   ├── scene_plan_adapter.py— Director→Writer 桥接（活跃）
│   │   ├── contract_verifier.py — Writer 侧验证
│   │   ├── local_repair.py      — 局部修复
│   │   ├── conflict_map.py      — 冲突图
│   │   ├── pacing_budget.py     — 节奏预算
│   │   ├── voice_budget.py      — 声线预算
│   │   ├── world_budget.py      — 世界观预算
│   │   ├── scene_beat_manager.py— 场景节拍（P1）
│   │   ├── premise_scrutiny.py  — 前提预审
│   │   ├── models.py            — Writer 数据模型
│   │   └── fallback/            — 确定性兜底模板
│   ├── sie/                     — 11 引擎
│   │   ├── orchestrator.py      — SIE 编排器
│   │   ├── audit_orchestrator.py— SIE 审计
│   │   └── ...（11 引擎）
│   ├── evaluation/              — 10+ 个评估器（含 MechanicalEvaluator 可配置权重）
│   │   ├── emotional_climax.py  — P3：情绪高潮评分（2026-06-29 新增）
│   │   └── revision_memory.py   — P4：修订历史记忆（2026-06-29 新增）
│   ├── governance/              — 6 文件
│   ├── memory/compressor.py     — 三级记忆压缩
│   ├── state/                   — CanonLedger + StoryIR
│   ├── compiler/                — ContractEngine + DependencyAnalyzer
│   ├── kernel/                  — Director 4.10-4.13 运行时模块
│   │   ├── cross_chapter_validator.py — 跨章一致性验证
│   │   ├── style_tracker.py     — 文风稳定性追踪
│   │   ├── pacing_controller.py — 节奏控制系统
│   │   └── context_gap_analyzer.py — 上下文锚点检测
│   ├── checkpoint/              — 检查点
│   ├── analytics/collector.py   — 10 指标
│   ├── polish/                  — VoiceProfiles + LinePolish
│   ├── repository/              — 5 仓储
│   ├── audit/output_auditor.py  — 确定性审计器（49 tests）
│   ├── constraint_bundle.py     — 约束装配
│   └── prompt_builder.py        — Prompt 构建（含 SIE 注入）
tests/
├── pipeline/                    — 30+ 测试文件
└── test_clean_pipeline.py       — E2E 管线测试
```
