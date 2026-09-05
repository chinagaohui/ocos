# Phase 63 候选立项：TickPipeline 完整 Stage 化迁移

> 来源：《OCOS 升级优化修复方案》Sprint 3.1（10 步迁移进 8 Stage）
> 裁决：《OCOS 修复方案评审与落地执行版 v1.0》R4 —— 本迭代降级，仅做
> PipelineError 兜底（S3.10）与 SAFE_MODE/DEGRADED 最小接线；**完整 Stage 化
> 迁移移出本迭代，单独立项（本文件 = Phase 63 候选）**。
> 状态：候选立项（未排期），2026-09-06 登记。

---

## 一、背景

`agent_runtime.tick()` 是 10 步顺序认知循环（事件摄入 → 注意力更新 → WM 同步 →
目标维护 → 执行检查 → 规划触发 → **核心循环** → 派发 → 结果反刍 → 学习巩固），
全部在单函数内顺序硬编码，步间无独立契约、无失败隔离、无状态机语义。

并行地，`ocos/runtime/pipeline.py` 已存在 8 Stage 冻结管线
（EVENT_INGESTION→ATTENTION→MEMORY_SYNC→GOAL_MAINTENANCE→EXECUTION_CHECK→
RESULT_COLLECTION→LEARNING_TRIGGER→CHECKPOINT_DECISION），但生产装配下
**8 个 Stage 全部缺省空转**（GAP-P2-2：组件为真实现、无生产装配注入），
真实认知全部发生在注入的 `agent_driver`（= `AgentRuntime.tick()`）中。

原方案 Sprint 3.1 提议把 10 步认知 tick 迁入 8 Stage 管线，让"心跳外壳 +
认知内核"双层合流为单管线。评审裁定**触碰冻结语义，降级延后**。

## 二、延后裁决依据（R4）

1. **触碰 step7 冻结语义**：Step 7 Core Loop（observe→think→decide→act→
   reflect→learn）与上电方案 PW-4.3 的冻结裁决冲突——上电方案已裁定
   "延后，触碰 step7 冻结语义"。10 步迁 8 Stage 不可避免要重新划分
   step7，属冻结面变更。
2. **生产旁路是裁决现状而非回归**：GAP-P2-2"8 stage 全部缺省空转"为有
   裁决注释的现状（管线协议完整、认知在 driver），不是缺陷，不应在本
   迭代以迁移名义破坏。
3. **可观测性/兜底已足够**：本迭代已完成 S3.10（PipelineError 兜底 +
   DEGRADED/SAFE_MODE 最小接线），tick 不再因单 Stage 失败而整体死亡。

## 三、本迭代已完成（S3.10 / R4 范围内）

- `runtime_kernel.tick_loop` 捕获 PipelineError → 日志 + `enter_degraded()`；
  连续 3 次 → `enter_safe_mode()`（仅 checkpoint + 跳过 agent driver）；
  SAFE_MODE 连续 5 tick 正常 → `recover()`（转移表已扩 SAFE_MODE→RUNNING）。
- 生产装配仍为"8 Stage 空转 + agent_driver 承载认知"（现状不破坏）。

## 四、Phase 63 候选范围（后续立项输入，两阶段设计）

### 阶段一：Stage 职责对齐（不触碰 step7）

将 10 步中与 8 Stage 同名同语义的步骤迁入对应 Stage：
- Event Ingestion → EVENT_INGESTION
- Attention Update → ATTENTION
- WM Sync → MEMORY_SYNC
- Goal Maintenance → GOAL_MAINTENANCE
- Execution Check → EXECUTION_CHECK
- Result Ingest → RESULT_COLLECTION
- Learning Consolidation → LEARNING_TRIGGER
- Checkpoint → CHECKPOINT_DECISION

产出：`pipeline.execute_tick` 全 stage 非空转，`agent_driver` 收窄为
Step 6（Planning Trigger）+ Step 7（Core Loop）+ Step 8（Dispatch）的
聚合调用。**不划分 step7**，保持冻结语义。

### 阶段二：step7 语义重审（独立变更单）

单独立项评审 step7 Core Loop 的 Stage 归属（OBSERVE/THINK/DECIDE/ACT/
REFLECT/LEARN 六段是否需要子 Stage、失败隔离粒度、与 Governance Freeze
的交互）。该阶段须单独走宪法变更流程，不得与阶段一混排。

## 五、前置依赖与风险

| 项 | 说明 |
|---|---|
| 依赖 | S3.10 兜底已就绪（已完成）；阶段二依赖 step7 语义重审裁决 |
| 风险 1 | Stage 迁移后 context 不可变契约（TickContext frozen dataclass）与
  10 步步骤间共享可变状态（step_log/_recent_results）的适配 |
| 风险 2 | 双 EventBus（ocos/perception_bus 单数 ingest vs ocos/events 复数
  publish）API 混淆面需在迁移前厘清（S4.1 已完成 ocos/event →
  ocos/perception_bus 重命名） |
| 风险 3 | 迁移后回归面大（全量 tick 路径），需先固化 tick 黄金链路测试 |
| 验收 | 8 Stage 全非空转且 step7 语义不变；全量测试绿；生产验证报告
  tick 心跳指标（ocos_tick_total）正常累计 |

## 六、登记

- 登记时间：2026-09-06
- 来源方案：《OCOS 升级优化修复方案》Sprint 3.1（评审版 R4 降级项）
- 相关裁决：PW-4.3（延后，触碰 step7 冻结语义）
- 当前状态：**候选立项，未排期**；不进入本版本迭代范围
