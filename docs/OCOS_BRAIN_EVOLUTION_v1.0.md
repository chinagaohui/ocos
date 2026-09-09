# OCOS Brain Evolution v1.0 — 让 OCOS 拥有真正的脑

> 2026-09-09 · 基于 2025-2026 全球最新 Agent 研究进展
> 替代 LLM 代理思考 → OCOS 自己思考

---

## 一、Gap Analysis：OCOS vs Foundation Agent 7 组件

MetaGPT+Mila 2025 年 264 页综述《Advances and Challenges in Foundation Agents》定义了 7 个核心组件。对比 OCOS 现状：

| # | 组件 | Foundation Agent 要求 | OCOS 现状 | 成熟度 | 缺口 |
|---|---|---|---|---|---|
| **1** | **认知核心** (Cognition Core) | 符号+神经混合推理、因果推理、反思、元认知 | SymbolicReasoner（刚做的 bi-gram 相似度 + Episode 聚合）、LessonsSynthesizer（规则归纳）、ReflectionEngine（90% 自主度） | **★★☆☆☆** | SymbolicReasoner 只有相似度匹配，缺因果推理、反事实推演、不确定性量化 |
| **2** | **记忆系统** (Memory System) | 情景记忆 + 语义记忆 + 程序记忆，带自动遗忘和概念抽象 | BeliefStore（308 条）、PatternStore（10 条）、EpisodeStore、LessonsSynthesizer | **★★★☆☆** | PatternStore 只有 daemon tick 模式（n=3-4），没有真正的 agent 行为 pattern；缺概念层（ConceptStore）；Belief 提取被动（只有 _extract_beliefs_from_results） |
| **3** | **世界模型** (World Model) | 内部模拟器，能做前向推演和反事实推理 | SimulationEngine（存根） | **☆☆☆☆☆** | **完全没有**——OCOS 无法预测"如果我做 A 会怎样"，所有 planning 靠 LLM 想 |
| **4** | **价值 & 奖励** (Reward & Value) | 内在动机：好奇心驱动（信息增益）、homeostasis、目标价值评估 | MotivationHub（信号聚合 + 硬编码"探查模块 X"模板） | **★★☆☆☆** | 好奇心是假的——硬编码 `_from_self_exploration` 模板，不是信息增益驱动；缺 prediction-gap 好奇心 |
| **5** | **情绪 & 动机** (Emotion & Motivation) | 情绪调节、内在驱动力（不是只有外部 reward） | SelfMonitor（规则检查）、homeostasis.py（存根） | **★☆☆☆☆** | 没有情绪系统；homeostasis 没实现；缺内驱力架构 |
| **6** | **感知** (Perception) | 多模态感知、主动注意 | EventBus + 10 步 tick 微循环 | **★★★☆☆** | 好——但感知后没有主动好奇驱动的定向探查 |
| **7** | **行动系统** (Action) | 行动选择、工具使用、层级执行 | DecisionBridge + LLM Agent 执行 | **★★★☆☆** | 好——但行动前没有内部模拟 |

**关键差距：世界模型 + 好奇心 + 概念层**

OCOS 最大的三个缺失——正是 2025-2026 全球研究最集中的三个方向。

---

## 二、2025-2026 全球最新进展（与 OCOS 直接相关）

| 方向 | 代表工作 | 核心思想 | OCOS 能抄什么 |
|---|---|---|---|
| **Neuro-Symbolic Hybrid** | NARCES (MeTTa-NARS + NACE) 2025 Temple PhD | 符号推理（NARS）+ 子符号学习（NACE 因果探索器）统一框架 | SymbolicReasoner 扩展因果推理层 |
| | ATA (Peer et al. 2025) Otera | LLM 离线→符号知识库→在线确定性决策 | 把 LessonsSynthesizer + PatternStore 变成 ATA 的符号决策引擎 |
| | WALL-E (NeurIPS 2025) UTS+Tencent | 世界模型 + 符号知识提取 + MPC 前向推演 | 做轻量 SymbolicWorldModel，用 PatternStore 规则推演 |
| **Symbolic-First Architecture** | Orrin v3 2026 | 符号控制循环、Goal WAL、Host Awareness | SymbolicReasoner 已经是 symbolic-first；继续扩展 |
| | 1992 符号 AI 复兴 (Norvig 范式重版) | Expert System + Prolog 推理链 + Frame Representation | LessonsSynthesizer 可以加更正式的 Frame 结构 |
| **Self-Organizing Memory** | Nemori (同济 2025) | Predict-Calibrate Principle + Event Segmentation Theory | **核心启发**：预测误差 = 学习信号；误差大的地方 = 记忆重点 |
| | CogniFold (2026 arXiv) | Conceptual Bootstrapping：当 graph density 过阈值自动产生概念 | **直接可以做**：BeliefStore + PatternStore → 概念层 |
| | EverMemOS (2025) | 4 层脑启发记忆：Agentic/Memory/Index/API | OCOS 已经有多层但需要 Concept 层 |
| **Curiosity-Driven** | Genesis (2025) | Free-Energy Principle：最小化 world model gap | **最直接能做的**：SymbolicReasoner 预测 vs 实际 outcome → 误差 → 好奇心 |
| | NACE (NARCES 子组件) | Causal Explorer：数据高效因果学习 | PatternStore 自动增长就是这个方向 |
| **Neurosymbolic World Model** | NeSy-WMs (KU Leuven 2026) | Symbolic reward/continuation predictor over latent | WALL-E 的简化版就能给 OCOS 用 |

---

## 三、OCOS Brain Evolution 三阶段路线图

### Phase 1（最高杠杆）：Prediction-Gap Curiosity — 让好奇心自驱动

**核心洞见（Nemori + Genesis + Free-Energy Principle）**：

```
SymbolicReasoner.predict(task, agent)  →  expected_success
实际执行 →  actual_success
误差 = |expected - actual|  ← 这就是好奇心！

误差大的领域 → 自动成为 MotivationHub 的目标候选
（"我的世界模型在 X 领域不太准 → 主动探查 X 来补全"）
```

**改什么：**

1. **新建** `ocos/reasoning/curiosity.py`（纯逻辑组件）
   - `PredictionGapTracker`：goal_result 发生时调 SymbolicReasoner.predict → 记录 (task, agent, predicted, actual, gap)
   - `EpistemicDrive`：扫描 gap 历史 → 返回"最不确定的 top-3 领域"

2. **改** `ocos/daemon/motivation.py`
   - `_from_self_exploration()` 硬编码模板 → 替换为 `EpistemicDrive.suggest()`
   - 现在 MotivationHub propose 的 goal 不是"探查 ocos.xxx"这种模板，而是"探查 researcher 在模块探查类任务上的成功率不确定性"

3. **改** Step 10 `_tick_step_learning_consolidation`
   - goal_result 发生后 → 调 PredictionGapTracker.record()

**为什么最高杠杆：**
- 直接解决"假好奇心"问题
- 误差数据自然流入 BeliefStore → Phase 2 的 Concept Formation 有了更好的种子
- 不需要 LLM 调用，零成本

---

### Phase 2（次高杠杆）：Concept Formation — 从重复经验中抽象概念

**核心洞见（CogniFold's Conceptual Bootstrapping）**：

```
当 BeliefStore 里多个 belief 共享 scope 关键词
  AND 这些 belief 的总 confidence > 阈值
  AND PatternStore 里有对应 pattern 支持
→ 自动创建一个 Concept 节点

例子：
  belief[scope="模块探查", confidence=0.8]
  belief[scope="模块探查", confidence=0.6]  
  belief[scope="模块探查", confidence=0.7]
  pattern[trigger="模块探查", confidence=0.8]
→ 自动生成 Concept:
  {id: "CONCEPT-001", name: "fragile_probe", 
   scope: "模块探查", confidence: 0.7,
   relations: [("agent_type", "researcher"), ("outcome", "failure")]}
```

**改什么：**

1. **新建** `ocos/memory/concept/__init__.py` + `models.py` + `store.py`
   - Concept 数据类：id, name, scope, confidence, relations, birth_ts
   - ConceptStore：SQLite 表 concept + auto_create() 逻辑
   - 扩展 BeliefStore / PatternStore 关联

2. **改** `ocos/daemon/consolidation_service.py`
   - dream cycle 里 Phase 21 之后加 Phase 22：`_form_concepts()`
   - 从 BeliefStore + PatternStore 找候选 → 阈值过滤 → 生成 Concept

3. **改** `ocos/reasoning/symbolic.py`
   - SymbolicReasoner.predict() 里加 Concept 查询层：
     "如果有 concept 匹配这个 task → 用 concept 的 relations 做更强预测"

---

### Phase 3（中等杠杆）：Lightweight Symbolic World Model — 内部模拟器

**核心洞见（WALL-E + NeurIPS 2025）**：

```
给定一个 Plan [step1, step2, step3, ...]
SymbolicWorldModel.simulate(plan, agent) → {success_prob, risk_points, expected_outcome}

怎么做：
  1. 每个 step → 查 PatternStore 有没有 "X action triggers Y" 规则
  2. step 之间的依赖 → 前向推演（如果 step1 失败 → step2 会怎样）
  3. 用 Belief 的 confidence 做每个 step 的成功率估计
  4. 聚合 → 整个 plan 的成功率分布
```

**改什么：**

1. **新建** `ocos/world/simulator.py`（纯逻辑组件，零 LLM）
   - `SymbolicSimulator.simulate_plan(steps, agent, context)` → SimulationResult
   - 前向推演：PatternStore causal rules + BeliefStore statistics
   - 支持反事实："如果 step2 失败了 → 整体 plan 成功率多少"

2. **改** `ocos/engines/planning_engine.py`
   - Plan 生成后 → 先过 SymbolicSimulator → 成功率低于阈值 → 让 LLM 重规划
   - 这是 WALL-E 的 MPC 简化版

3. **改** `ocos/engines/reasoning_engine.py`
   - SymbolicReasoner 也可以调 Simulator："这个 task 如果分 3 步执行，每步成功率多少"

---

## 四、架构不变原则

所有 brain 增强都遵循同一个约束：

```
✅ 纯逻辑组件（不调 LLM）
✅ 独立模块（不依赖 Engine 基类）  
✅ 可插拔（被现有引擎按需调用，不替换现有逻辑）
❌ 不新建 Engine 类（15 Engines 够用）
❌ 不引入重依赖（PyTorch 等）
❌ 不阻塞现有 LLM 路径（symbolic 是前置增强，不是替代）
```

---

## 五、改了之后 OCOS 能做什么（以前不能的）

| 场景 | 以前 | 以后 |
|---|---|---|
| OCOS 想知道"探查模块 ocos.goal 会成功吗" | 全靠 LLM 拍脑袋 | SymbolicReasoner：相似度 0.11、历史 3 次全败 → succ=0.00 |
| OCOS 为什么今天在探查模块 | 硬编码"探查模块 ocos.xxx"模板 | PredictionGapTracker 说"我在模块探查领域误差 0.6 → 主动探查补知识" |
| OCOS 执行 plan 之前 | 直接扔给 LLM 执行 | SymbolicSimulator 先跑一遍 → 第 2 步成功率只有 0.2 → 让 LLM 加容错 |
| OCOS 为什么 writer 在复盘类任务上表现好 | 不知道 | Concept formation 自动产出 concept: "writer + 复盘 → success_pattern" → 下次直接用 |
| OCOS 有了 500 个 episode 后 | 还是靠 LLM | 形成了 10-20 个 concept + PatternStore 50+ rules → SymbolicReasoner 在简单任务上跳 LLM |

---

## 六、立即行动清单

按 leverage 排序：

- **Phase 1（Prediction-Gap Curiosity）** — 改 3 个文件，最高杠杆
- **Phase 2（Concept Formation）** — 新建 3 个文件，dream 里自动生成
- **Phase 3（Symbolic World Model）** — 新建 1 个文件 + 改 2 个引擎

每个 Phase 完成后跑全量测试 + 重启 daemon。

---

*注：本设计文档引用的研究工作详见 Phase 二表格，均可在 arXiv 或顶会 Proceedings 中找到原文。*
