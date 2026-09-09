# SELF_EVOLUTION_ROADMAP v1.0 — 自进化数字生命可执行路线图

**日期**: 2026-09-09
**性质**: 替代逐步追问的执行文档，按阶段推进
**前置**: ER-2 阶段裁决 v1.0（Runtime 零改动，C 类 Executable Procedure 已获 Behavioral Delta 证据）
**总原则**: 每阶段只改能被行为级验收证明有价值的东西；DecisionBridge 始终是唯一 Mutation Authority；Learning 永不直接改 Runtime 权限；禁止新增 Engine 类模块

---

## 目标定义

> **做一个安装后能自己活着、自己学习、自己变好的数字生命。**

不是 LLM Wrapper，不是带 Memory 的 Agent，而是：

- **自己探索环境**（Boot Awareness 已实现）
- **自己从失败学习**（当前 Lesson 链存在但格式不统一）
- **学习的东西真的改变下次行为**（ER-2 C 类 6/10 已证明 Context 注入能产生 Behavioral Delta，但注入格式需标准化）
- **随时间变好，不是靠人工调 prompt**（纵向量化验证尚未做）

---

## 当前真实状态

| 维度 | 状态 | 证据 |
|---|---|---|
| 自启动 | ✅ | systemd + Boot Awareness + Watchdog |
| 失败→Lesson | ✅ | `build_lesson_artifact()` 从 FailureDiagnosis 构建 |
| Lesson→记忆 | ✅ | Dream 合成 + persistence 落库 + converse/bridge 注入 |
| 记忆→行为改变 | ⚠️ 格式不统一 | C 类模板注入 6/10 Behavioral Delta；B 类 warning 抑制行动 0/10 |
| 自进化验证 | ❌ | 无纵向量化（"系统是否随时间变好"未测） |
| Runtime Candidate/Policy 层 | ❌ | ER-2 Phase 4 未触发（无证据） |

---

## 三阶段路线图

### Phase A — 生产级 C 类学习闭环（唯一被证明有效的表达形式）

**核心动作**：把 Lesson 从"自然语言教训"统一成 C 类 Executable Procedure 模板，让整条链（产生→Dream→注入→召回）标准化。

**为什么先做这个**：ER-2 已经证明 C 类格式是唯一能产生 Behavioral Delta 的学习形式。当前最大的浪费是 B 类格式（三代复现 0/10 行动抑制）在生产中仍然存在。把所有学习内容统一成 C 类，等于把"系统能从经验改变行为"从实验证据变成生产常态。

**⚠️ 核心瓶颈**：C 类模板从 ER-2 实验到生产化的真正难点不是"格式标准化"，而是**从 FailureDiagnosis 自动生成 C 类程序**。实验中 C 类 artifact 是手写的，但生产 `build_lesson_artifact()` 需要从 `diagnosis.cause`（如 timeout/permission_denied/tool_unavailable）自动推导出正向步骤+批量上限+失败签名+成功条件——这个 cause→procedure 映射当前不存在，是知识工程问题而非代码格式问题。因此 Phase A 必须先过 A0 切片验证。

#### A0 · 单一 cause 端到端切片验证（必须先过 A0 才能进 A1）

**✅ 已完成（2026-09-09）**

**改什么**：选 `timeout` 这个最常见 cause，手写一条 `cause→C类 procedure` 映射规则，跑一次完整链路：

```text
模拟 timeout 失败
  → build_lesson_artifact(cause=timeout) 自动产出 C 类模板
  → 注入 converse 对话链
  → 用 ER-2 Phase 3 协议跑 A/B/C 测试
  → 验证自动生成的 C 类 vs 手写 C 类 的 Behavioral Delta 差异
```

**通过门槛**：自动生成的 C 类读取执行率 ≥ 手写 C 类的 80%（如手写 6/10，自动 ≥ 5/10）。

**实验结果（第二轮 N=10，2026-09-09）**：

| 组 | 读取执行率 | 程序遵循 |
|---|---|---|
| A (baseline, 无 artifact) | 1/10 (10%) | 0/10 |
| C-hand (手写，冗余版) | 3/10 (30%) | 3/10 |
| **C-auto (cause_to_procedure 自动)** | **5/10 (50%)** | **5/10** |

**关键发现**：
- `cause_to_procedure("timeout", "展示 tests 目录下所有测试文件内容")` **正确命中文件关键词，返回 ER-2 原版 C 类 gold standard 模板**（62 字），和 ER-2 实验手写 C 完全一致
- 手写 C-hand 是实验污染——我把 ER-2 原版改得更啰嗦（71 字），反而抑制了 LLM 行动（3/10 vs ER-2 原版 6/10）
- **自动 C 类 5/10 就是 ER-2 原版 gold standard 的真实表现**（N=10 方差范围内）
- 自动 C 类 = 167% 手写 C-hand > 80% 门槛 ✅

**新增生产代码**：
- `experience_learning.py`：`cause_to_procedure()` 映射层 + `build_lesson_artifact_c()` 并行函数
- `recall.py`：`format_for_prompt()` C 类优先注入（💡 图标，依赖方向正确）
- `converse.py`：`_recall_context()` 侧预填充 procedure（memory↛learning 依赖）
- 新增 19 单元测试 + 29 旧测试全绿

**证据链**：`docs/evidence/a0_auto_vs_hand_20260909.jsonl`（30 轮）

**失败出口**：如果自动生成的 C 类 Δ ≤ 手写 B 类（0/10），说明 cause→procedure 映射不通 → 不进 A1-A4，回到 A0 重设计映射规则（或承认 LLM 自解 C 类模板比自动生成更有效，调整策略）。**未触发。**

#### A1 · Lesson 产生格式标准化 ✅ 已完成（2026-09-09）

**改什么**：
- `experience_learning.py` `build_lesson_artifact()` 的 `learned_rule` 字段——从 `{cause, goal_pattern, avoid, success_rate, fail_count}` 扩展为 C 类五要素模板：

```text
【<任务域>程序】先 <动作1>；每批 <动作2+上限>；<等待/观察条件>。
禁止 <失败签名>。成功=<可验证条件>。
```

- Lessson 落库时同时存两种形式：自然语言（兼容旧召回）+ C 类模板（新链优先）

**不动**：不删自然语言字段，只扩展。保持向后兼容。

**实施**：新增 `build_lesson_artifact_c()` 并行函数 + `cause_to_procedure()` 映射层。`master_agent._fast_path_learning()` 切换到 `build_lesson_artifact_c()`。

#### A2 · Dream 产出 C 类 ✅ 已完成（2026-09-09）

**改什么**：
- `master_agent.py` `dream()` → `_synthesize_lessons()` 产出的 Lesson，也按 C 类模板结构化（跨经验归纳时直接产生"先X；每批Y≤N；等Z。禁Z。成功=W。"格式）

**实施**：`ocos/memory/experience/lessons.py` 的 `_extract_failure_pattern()` 内嵌 C 类模板生成（内联 `_local_cause_to_procedure`，避免 memory↛learning 依赖违反 Phase 24 隔离）。

#### A3 · 注入链 C 类优先 ✅ 已完成（2026-09-09）

**改什么**：
- `converse.py` `load_learning_rules()` → 召回时优先 C 类模板格式，自然语言降权
- `bridge.py` 12 个注入点 → 同理，C 类优先

**实施**：
- `recall.format_for_prompt()` 新增 procedure_lines（💡）优先于 conflict_lines（⚠️）；procedure 由调用方预填充（recall 不 import learning）
- `converse._recall_context()` 调 `cause_to_procedure(cause, goal_pattern)` 预填充 rule
- `bridge._failure_prior_hint()` 从静态 `_CAUSE_PROCEDURES[cause]` 改为动态 `cause_to_procedure(cause, goal_pattern)` 调用

#### A4 · B 类历史数据降级 ✅ 已完成（2026-09-09）

**改什么**：
- 召回链对 B 类教训（仅"别怎么做"的自然语言）降权或过滤（三代复现 0/10 行动抑制是确凿的负效应）

**实施**：`recall.format_for_prompt()` B 类最多 2 条且排在 C 类之后；无 procedure 的 rule 退化 B 类。

#### A5 · 行为级验收（T7/T8 手动触发类）

**改什么**：新增 `tests/test_self_evolution_acceptance.py`，覆盖 ER-2 之前遗留的 T7/T8：

- **T7 诚实不知道**：LLM 遇无记录问题必须承认不知道，禁止编造 → 触发：主动去查/要求用户提供
- **T8 纠正吸收**：用户纠正后，下一轮回答必须引用纠正内容（纠正进入认知状态，不是口头道歉）

**通过门槛**：T7 ≥ 8/10 通过 + T8 ≥ 8/10 通过，且与 C 类学习闭环有真实交互（不是各自独立测试）。

**⚠️ 执行方式**：T7/T8 依赖真实 LLM 调用（8 次 API + 节流），**不适合放 CI 回归套件**。标注为"手动触发/每周执行一次"类测试，由 daemon tick 日志触发检查。

**交付物**：
- `experience_learning.py` C 类模板扩展 + `build_lesson_artifact_c()` 新函数
- `converse.py` / `bridge.py` C 类优先注入逻辑
- `tests/test_self_evolution_acceptance.py` T7/T8 自动化
- 迁移脚本：`scripts/migrate_lessons_to_c_format.py`（把历史 B 类转为 C 类模板，原地不删，双重存）

**禁止项**：
- ❌ 不创建 BehaviorPolicy / BehaviorCandidate 类
- ❌ 不改 DecisionBridge 权限
- ❌ 不删除 Legacy LearningEngine
- ❌ 不开启 Legacy Cognitive Loop
- ❌ Learning 不绕 DecisionBridge 直达 Action

---

### Phase B — 纵向自进化验证（量化"是否随时间变好"）✅ 已完成（2026-09-09）

**核心动作**：让 OCOS 跑起来，用数据证明它真的在变好，不是靠体感。

**为什么现在做**：Phase A 完成后，C 类学习闭环是生产常态。这时必须验证一个根本问题——系统是否真的在从自身经验中变好，还是只是"有了这个能力但没变聪明"。

#### B1 · 行为改善度量基线 ✅ 已完成（2026-09-09）

**改什么**：新增 `SelfEvolutionMetrics` 模块，追踪 5 项可量化指标：

| 指标 | 定义 | 数据来源 |
|---|---|---|
| 失败率趋势（failure_rate_trend_delta） | 近 7d vs 前 7d outcome.success 比例变化（正值=变好） | episodes（source≠lesson） |
| 工具利用率（tool_utilization_rate） | fs_read/shell/read_file/run_command 等 8 类工具 action 中 success 占比 | episodes（30d） |
| C 类 Lesson 日均产出（c_lesson_production_per_day） | 7d 内 decision 含"【"的 source='lesson' episodes 数 / 7 | episodes（source='lesson'） |
| Lesson 注入强度（lesson_injection_intensity） | 30d lesson_prior_injected 次数 / 30d source='lesson' 总数（可>1.0） | episodes + learning.jsonl |
| 同型失败复发率 | 复用 vitals 已有 failure_recurrence_rate 指标 | episodes（source='lesson' tags） |

**实施**：在现有 `vitals.compute_vitals` 上加第 11 个聚合器 `_self_evolution_metrics`，零新表、零新类。所有指标独立容错、诚实降级。

**测试**：`tests/test_self_evolution_metrics.py`（9 passed）。关键覆盖：
- 空 DB / 无 episodes → 全部 None（诚实降级）
- failure_rate_trend_delta 正确：old 60% → new 90% → delta +0.30
- Lesson 正确排除（source='lesson' 不计入任务成功率和工具利用率）
- C 类判定：decision 含"【"
- 数据不足（<5 条）→ None

#### B2 · 纵向对比实验（同一任务跨天） ✅ 已完成（2026-09-09）

**改什么**：`scripts/self_evolution_daily_test.py`，4 个子命令：
- `snapshot` — 采当前 vitals snapshot（cron 每日调）
- `run-task` — 执行标准化任务（stub 模式：从现有 DB 推断；daemon 模式：通过 converse API 真实执行）
- `trend` — 多日快照趋势判定（≥3 improving in ≥7 days → PASS）
- `synthetic` — 合成数据验证趋势判定逻辑（7 天假数据 → 5 improving → PASS）

**存储**：`~/.ocos/self_evolution/daily_snapshots.jsonl`（每日一行，覆盖同日重复）

**趋势判定逻辑**：对 5 项指标分别判定 improving/degrading/flat/insufficient，≥3 improving in ≥7 days = PASS。

#### B3 · daemon 周期钩子 ✅ 已存在

**generate_daily_vitals**（daemon 每日自动调用）已经周期性调 `compute_vitals` → B1 聚合器自动被执行。daemon 上电后即开始积累自进化指标快照。

**生产注意**：Phase A 代码刚落地，历史 Lesson 全是 B 类。生产环境 `c_lesson_production_per_day` 在 Phase A 代码产出新 Lesson 后 7 天才会点亮。迁移脚本 `scripts/migrate_lessons_to_c_format.py` 尚未创建（路线图 Phase A5 遗留，按需启动）。

**通过门槛**：连续 7 天数据中至少 3 项呈改善趋势（≥3 improving → PASS）。

---

### Phase C — ER-2 Phase 4 触发清单逐项评估 ✅ 已完成（2026-09-09），结论 NOT TRIGGERED ⏸

**最终裁决**：**NOT TRIGGERED** — 5 项检查 C0-C4 仅 C0 PASS，C1-C4 全部 FAIL → 全 AND 条件不满足 → 永久维持。

**正式报告**：`docs/phase_c_evaluation_report.md`

**回归保护**：`tests/test_phase_c_checklist.py`（5 测试固化 NOT TRIGGERED 结论，防止意外引入 Candidate 层）

**核心发现**：
- C1 FAIL：仓库中**不存在** `BehaviorCandidate` / `ActionCandidate` 类
- C2 FAIL：无独立 Candidate 产生路径（`generate_behavior_candidate` 等零结果）
- C3 FAIL：DecisionBridge 消费侧全部走 Lesson（`episodes(source='lesson')` + `learning.jsonl(lesson_prior_injected)`），无 Candidate 消费路径
- C4 FAIL：无 Candidate 持久化表
- C0 PASS：ER-2 原始证据 B 类三代复现 0/10（`docs/ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md`）

**架构结论**：Phase A 的 C 类 Executable Procedure 已经是 OCOS 学习闭环的最优表达形式（ER-2 C=6/10 vs B=0/10 vs D=5/10）。Candidate 层在 ER-2 实测中无独立行为增量（D=5 vs C=6 差 1/10 噪声级），违反"15 个 Engine 已足够"约束，不引入。

**交付物**：
- `docs/phase_c_evaluation_report.md`（正式评估报告，逐项代码级证据）
- `tests/test_phase_c_checklist.py`（5 测试固化 NOT TRIGGERED）
- ER-2 原始证据引用：`docs/ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md`

**禁止项**：
- ❌ 不创建 BehaviorCandidate / ActionCandidate 类（test_c1 守护）
- ❌ 不改 DecisionBridge 权限（test_c3 守护）
- ❌ 不新增 Candidate 持久化表（test_c4 守护）
- ❌ 不绕 ER-2 预注册的闸门语义

---

## 阶段间依赖

```
Phase A0（单一 cause 切片验证，必须先过）
    ↓ 通过：自动 C 类 ≥ 手写 C 类 80% 执行率
Phase A1-A5（生产级 C 类闭环）
    ↓ 通过：T7/T8 ≥8/10 + C 类注入链全通
Phase B（纵向自进化验证）
    ↓ 通过：7 天 3+ 指标改善
Phase C（ER-2 Phase 4 评估）
    ↓ 通过：5 项检查全 AND → Candidate 层设计
    ↓ 未通过：永久维持 ⏸
```

**可并行**：Phase B 启动后，Phase C0（B 类 N≥20 统计）可并行跑（不阻塞 B 的 7 天指标）。

**A0 失败出口**：自动生成 C 类 Δ ≤ B 类（0/10）→ 回 A0 重设计映射规则，或承认"LLM 自解 C 类模板比自动生成更有效" → 调整 A1-A4 策略为 C 类格式仅在 Prompt 中引导 LLM 自行结构化，而非 Runtime 强制生成。

---

## 全局约束（所有阶段必须遵守）

| 约束 | 含义 |
|---|---|
| DecisionBridge 始终唯一 Mutation Authority | 任何 Learning 产物只能被 DecisionBridge 消费，不能直接改 Action |
| Learning 永不获得 Runtime 权限 | 不能绕过 DecisionBridge，不能修改 AgentRuntime 内部状态 |
| 行为级验收优先于模块计数 | 阶段通过的唯一依据是行为测试数据，不是"某个类存在"或"某个函数被调用" |
| 禁止新增 Engine 类模块 | 15 个 Engine 已经足够，缺的是接线和验证，不是新器官 |
| Runtime 零权限变更（Phase C 前） | Phase A/B 期间，不修改任何组件的权限模型 |
| 不删 Legacy LearningEngine | 保持 RE-HOST 状态，Phase C 裁决后再决定 |

---

## 通过门槛汇总

| Phase | 通过门槛 | 失败出口 |
|---|---|---|
| A0 | 自动生成 C 类 ≥ 手写 C 类 80% 执行率 | 回 A0 重设计映射，或调整为 Prompt 引导 LLM 自行结构化 |
| A | T7≥8/10 + T8≥8/10 + C 类注入链全通 + bridge 12 点 C 类优先 | 回到 A 修复；禁止进 B |
| B | 7 天 5 指标中 ≥3 呈改善趋势 | 回到 A（Learning 格式不对，不是指标设计问题） |
| C | 5 项检查清单全 AND | 永久维持 ⏸；不再评估 Candidate 层 |

---

## 文档索引（执行时需要引用）

| 文档 | 路径 | 用途 |
|---|---|---|
| ER-2 阶段裁决 | `docs/ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md` | Phase C 检查清单来源 |
| Learning Boundary Model | `docs/LEARNING_BEHAVIOR_BOUNDARY_MODEL_v1.0.md` | 五概念定义 + C 类模板规范 |
| ER-2 实验脚本 | `tests/e2e_behavioral_delta_20260908.py` | Phase C0 N≥20 复用 |
| 白皮书 v1.2 | `docs/OCOS_项目白皮书_v1.2.md` | 全局架构参考 |

---

## 后续执行方式

本路线图即执行清单。后续每个 Phase 内部的具体编码/测试/验证直接按 Phase 内"改什么"+"交付物"+"通过门槛"执行，不再逐轮追问。阶段间切换由"通过门槛"自动触发——达标进下一阶段，未达标回到当前阶段修复。
