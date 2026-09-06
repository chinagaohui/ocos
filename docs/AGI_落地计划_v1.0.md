# OCOS → AGI 能力补齐落地计划 v1.0

> 依据：《AUDIT_REPORT_AGI_REALITY_v2.0.md》结构性断点 + 《BLUEPRINT_AGI_UPGRADE_v1.1.md》ER 验收框架
> 定位：OCOS 已是真实运行的有限自主 Cognitive Runtime；本计划补齐"学习经验→行为改变"的因果闭环及下游消费链
> 总门禁：**ER-2 Behavioral Delta**——学习前后同类任务行为发生可归因、可验证的变化（蓝图 v1.1 §8 定义）
> 生成日期：2026-09-06
> 进度：**P0 ✅ / P1 ✅（ER-2 机制验证通过 + 生产链路绑定生效）/ P2 ✅ / P3 ✅ / P4 ✅ / P5 ✅（P5.1 失败归因重规划 + 教训回学习管道；P5.2 Phase 53 主动交互唤醒生产接线）— 全 Phase 完成**

---

## 〇、路线总览

| Phase | 主题 | 对齐缺口 | 核心交付 | 优先级 |
|---|---|---|---|---|
| **P0** | 基座：行为基线化与可观测 | 全部 | 行为黄金链路测试 + Behavioral Delta 量化工具 | P0 |
| **P1** | 学习因果闭环（写入→注入→验证） | G1 | 信念/经验注入决策 prompt + ER-2 通过 | **P0** |
| **P2** | 世界模型消费链 | G2 | 规划前查询世界状态，感知→决策前置 | P1 |
| **P3** | 元认知回流 | G4 | confidence/反思调制决策策略 | P1 |
| **P4** | 技能习得生产化 | G1/G3 | grow_skills 生命周期接线 + 技能检索注入 | P2 |
| **P5** | 长期自主 + 主动交互 | G5/G6 | 失败归因重规划 + Phase 53 唤醒 | P2 |

依赖：P1 ⊂ P0（基线）；P2/P3 可并行于 P1；P4 依赖 P1 的注入通道；P5 依赖 P3 的置信度基础。

---

## 一、Phase 0 — 行为基线化与可观测（前置基座）

**目标**：让"学习前后行为差异"可测量。没有基线，ER-2 无法判定。

### P0.1 行为黄金链路测试（tests/integration/test_behavior_chain.py）
1. 固化 5 类代表性任务（宿主机分析/文件写入/模糊任务/敏感路径/破坏性命令）的"决策轨迹快照"：输入描述 → 动作序列 → 沙盒结果 → 最终状态。
2. 快照存 `~/.ocos/behavior/baseline.jsonl`（每次运行对比，记录 diff）。
3. 测试：`make behavior-delta` 输出 Behavioral Delta 报告（动作序列 Jaccard 相似度 + 成功率 delta）。

### P0.2 Behavioral Delta 量化工具（scripts/behavior_delta.py）
1. 输入：两次执行的决策轨迹 JSONL；输出：`{similarity, success_delta, path_changed: [动作A→动作B], attributable_to}`。
2. `attributable_to` 字段对接 P1 的注入 artifact id（学习产物的可追溯性——ER-2 要求"可归因"）。

### P0.3 学习产物可观测（learning telemetry）
1. `_extract_beliefs`/`_extract_beliefs_from_results` 每次产出打点：`belief_created{source, confidence}` 计数（复用 S3.5 全局指标钩子 `record_global`）。
2. 验收：运行一次任务后 `/metrics` 可见 belief_created 计数，且与 DB 中 beliefs 表行数一致。

**验收**：`make behavior-delta` 基线可重复生成；5 类任务轨迹快照稳定。

---

## 二、Phase 1 — 学习因果闭环（核心，P0）

**目标**：经验 → 信念/知识 → **决策上下文注入** → 行为可归因变化（ER-2 通过）。

### P1.1 学习产物检索接口确认与补强
1. 核验 `hub.belief()`/`hub.knowledge()` 查询 API（按置信度/域过滤）；缺失则补 `query_by_domain(domain, min_confidence, limit)`。
2. 新增 `agent_runtime.learning_artifacts(domain)`：聚合 beliefs + knowledge + skills（来自 `_extract_beliefs_from_results` 的 task fingerprint 模式），返回结构化注入块。

### P1.2 决策注入（执行层，对应 FIX-4 升级）
1. `bridge._prior_task_results()` 升级为 `_prior_knowledge(description, task_type)`：检索该域 beliefs/knowledge → 注入规划 prompt（含 artifact id，供 ER-2 归因）。
2. 注入模板：
   ```
   【历史经验（域: {domain}）】
   - belief: {statement} (conf={c}, artifact={id})
   - 有效动作: {action} 当 {situation}
   ```
3. 规则：仅注入**成功/高置信**产物（延续 FIX-4 教训——不注入失败史造成负反馈循环）；每次注入打点 `knowledge_injected{artifact_id}`。

### P1.3 验证闭环（ER-2 判定）
1. 构造 ER-2 场景测试（tests/integration/test_er2_behavioral_delta.py）：
   - Episode1: 任务 X（方法 A）→ 成功，沉淀 belief："当 {situation} 时 {action} 有效"
   - Episode2: 同类任务 X' → 断言决策轨迹不再走失败路径（或更优路径）且 `attributable_to` 命中该 artifact
2. 验收门：ER-2 通过 = P1 完成。**不通过 = 继续调注入权重/检索质量**，不降级验收标准。

### P1.4 学习产物治理
1. belief 淘汰：置信度 < 阈值（如 0.4）或 30 天未被检索 → 降级/归档（防注入噪声）。
2. 与 S2.3 经验边界门（STRICT）衔接：污染候选不入库 → 不注入。

**验收**：`pytest tests/integration/test_er2_behavioral_delta.py` 绿；生产重复执行同类任务 3 次，`ocos memory query` 可检索到信念，决策日志含 `knowledge_injected` 打点。

---

## 三、Phase 2 — 世界模型消费链（P1）

**目标**：WorldState → Reasoning 消费（断点修复），感知→世界模型→决策。

### P2.1 世界状态查询接入规划器
1. `world_store` 补读接口（按 entity/state/causality 查询）；`agent_runtime` 规划前查询活跃实体状态。
2. 注入格式：
   ```
   【世界状态】
   - {entity}: {state}（更新于 {ts}，causality: {links}）
   ```
3. 仅注入**目标相关**实体（按 description 关键词匹配），控制 token 开销。

### P2.2 世界模型→目标校验
1. 目标执行前用世界状态做前置校验（如"目标依赖的实体不存在 → 提前 honest failed 而非空跑"）。
2. 验收：创建依赖不存在实体的目标 → 快速失败且原因明确；查询注入在决策日志可见。

---

## 四、Phase 3 — 元认知回流（P1）

**目标**：Confidence/反思 → 决策策略调制（不再"反思不改变行为"）。

### P3.1 置信度驱动策略
1. `execute_dag_task` 元认知门升级：低置信写类 → 不直接 pending，增加"先检索经验"步骤（`_prior_knowledge` 命中高置信 artifact 才降级为可执行）。
2. 失败率阈值调制：`_tick_errors`/capability 历史成功率（S2.14 reliability 修复后可用）→ 动作级降级。

### P3.2 反思回流
1. 反思引擎输出 → `_recent_reflections` → 决策前注入"最近反思"（仅成功/建设性结论，延续 FIX-4 教训）。
2. 验收：反思产出后同类任务决策上下文含该反思；行为轨迹 diff 可见。

---

## 五、Phase 4 — 技能习得生产化（P2）

**目标**：`grow_skills_from_episodes` 生命周期接生产 + 技能检索注入。

### P4.1 生产装配
1. daemon 装配时调用 `grow_skills_from_episodes`（每 N tick 或目标完成后触发），只读候选自动验证提交、写类候选保持待批（现有四段生命周期语义保留）。
2. skill registry 查询接口 → 注入 P1.2 同一上下文块（skill 优于 belief，高置信优先）。

### P4.2 技能复用验证
1. ER-2 变体：任务 X 成功后沉淀 skill → 任务 X' 直接调用该 skill（动作序列复用）。
2. 验收：跨任务方法级复用 ≥1 个真实场景（如"宿主机分析"方法沉淀后可复用于新机器分析）。

---

## 六、Phase 5 — 长期自主 + 主动交互（P2）

### P5.1 失败归因重规划（对齐 G5）✅
1. 目标失败 → 归因分类（确定性 FailureDiagnoser：目标模糊/工具受限/执行错误/超时/权限拒绝/LLM 转换失败）→ 终态失败写入 `failure_lesson`（source="lesson" Episode）回学习管道（feed G1 统计侧，`_fast_path_learning` 下一周期重放聚合 failure_causes）。教训只进统计管道，不注入决策 prompt（延续 FIX-4 教训）。
2. 重规划策略：可修正因素（执行错误/超时 → 描述回注修正 + 有限重试，MAX_RETRY_PER_TASK=2）；不可修正（模糊目标/工具受限/重试耗尽）→ honest failed + 教训入库。实现：`agent_runtime._record_failure_lesson`，测试 `tests/test_phase49c_skill_growth.py::TestP51FailureLessonPipeline`。

### P5.2 Phase 53 主动交互唤醒（对齐 G6，沉睡器官接线）✅
1. `ActiveInteractionEngine`（`ocos/daemon/active_interaction.py`，daemon 生产装配层获准依赖 interaction+monitoring）串起 NeedMonitor → AttentionTrigger → InteractionValidator（IS53-03）→ InteractionScheduler（IS53-04）→ 权限双检（PermissionGuard + 宪法，fail-closed）→ outbox 输出；daemon heartbeat 每 60 tick 空闲期扫描。
2. 约束：交互只读化（IS53-01/02 验证器守护）+ 只读白名单通道（outbox）+ 频率/去重治理；`OCOS_INTERACTION_STALE_DAYS` 可调停滞窗口（默认 30 天）。
3. 验收：构造"目标依赖数据 5 天未更新（阈值 3 天）"→ 主动生成交互提议出现在对话流 — 测试 `tests/test_p52_active_interaction.py`。

---

## 七、执行纪律

- **提交节奏**：每 Px.y 一 commit，message 格式 `feat(P1.2): 信念注入决策上下文 — ER-2 归因（AGI 计划）`；每 Phase 结束打 tag `agi-p1-learning-loop`。
- **先测后改**：每项先写失败测试再实现；验收门（尤其 ER-2）不降级。
- **重启验证**：改代码必须 `ocos restart`（server→daemon→gateway）后手工验证（进程旧代码是头号"修了没生效"根因）。
- **回归**：每 Phase 完成跑 `pytest -q ocos/tests tests/` 全量 + `make gate` 全绿。
- **防范围蔓延（明确不做）**：多模态感知、推理模型内化（当前 LLM 外包）、记忆物理合并、WASM 插件沙箱——均不在本计划。

## 八、风险与对策

| 风险 | 对策 |
|---|---|
| 注入噪声降低决策质量 | 仅注入成功/高置信产物 + artifact 可追溯 + P1.4 淘汰机制 |
| ER-2 无法稳定复现 | P0 基线化先行，轨迹快照 diff 定位波动源 |
| token 开销上升 | 域过滤 + top-k 限制 + 注入块长度约束 |
| 主动交互打扰用户 | 交互提议只读化 + 需审批确认（复用 approval 通道） |

## 九、验收总纲

1. **ER-2 通过**（P1 完成标志）：同类任务学习前后行为可归因变化
2. **学习产物消费可观测**：决策日志含 `knowledge_injected`/`belief_created` 打点
3. **世界状态进决策**：规划前查询注入可审计
4. **主动交互闭环**：Phase 53 提议进入对话流且需审批
5. **全量回归绿**：每 Phase 结束 `pytest -q` + `make gate`
