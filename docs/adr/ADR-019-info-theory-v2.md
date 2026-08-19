# ADR-019: Information Theory v2.0 集成方案

| 字段 | 值 |
|------|-----|
| **状态** | ✅ 已冻结（Phase 21 补充） |
| **日期** | 2026-07-23 |
| **决策者** | Architecture Council |
| **参考** | docs/INFORMATION_THEORY.md · docs/LIFE_MODEL.md · docs/LIFE_CYCLE.md |

---

## 背景

2026-07-23 架构定调会议冻结了新的理论层（Life Model、Life Cycle、Goal Model、Belief Model、Identity Model、Attention Model、Homeostasis Model）。

现有的 `Information Theory v1.0`（基于 `PersistenceLevel × SemanticRole` 二维坐标系）与新的理论层之间存在分类冲突：

- v1.0 将 Information 分类为 `Persistent/Semantic` 二维标签（如 `OCOS_KNOWLEDGE`、`OCOS_WORKING`）
- 新的 Life Cycle 要求 Information 有生命周期阶段（Observe→Think→Decide→...）
- 新的 Belief Model 要求 Information 有置信度（Belief = Knowledge + Confidence）
- v1.0 没有「证据链」概念，而 Belief Model 依赖 SUPPORT/CONTRADICT/NEUTRAL

## 决策

1. **v1.0 二维坐标系保留为底层分类法**，不做结构性重构。
   - `PersistenceLevel`（TRANSIENT / WORKING / KNOWLEDGE / ARCHIVAL）作为数据放置策略
   - `SemanticRole`（FACT / RULE / RELATION / GOAL / INTENT / METHOD / EXPERIENCE / IDENTITY）作为语义标签
   - 现有 `Information` ABC 和 `KnowledgeInfo` / `GoalInfo` 等子类不动

2. **新增理论层作为上层概念**，不修改 v1.0 坐标系的 ABI。
   - `Life Cycle` 阶段标签 → 附加到 Information 的 `metadata.stage` 字段
   - `Belief`（置信度 + 证据链）→ 新类 `BeliefInfo`，包装 `Information` + `confidence` + `evidence_chain`
   - 不修改 `Information` 基类的 `__init__`

3. **v1.0 代码标记兼容层**：
   - `@deprecated(since="1.0", for_removal="2.0")` 标注于 `Information.__init__` 的参数签名
   - v2.0 前保持完全向后兼容

4. **新的 Information 子类逐步新增**（不修改现有子类）：
   - `BeliefInfo` — 在 Phase 24（Memory）新增
   - `EvidenceLink` — 证据链类
   - `ObservationInfo` — 生命周期阶段的输入封装

## 影响

| 方面 | 影响 |
|------|------|
| **破坏性变更** | 无 |
| **ABI 兼容** | 完全向后兼容 |
| **修改文件数** | 0（仅新增文件） |
| **新增文件** | `ocos/knowledge/belief_info.py`（Phase 24 创建） |
| **迁移成本** | 零。旧代码不受影响，新代码逐步使用新类 |

## 替代方案

| 方案 | 评估 |
|------|------|
| **完全重构 v1.0 坐标系** | 拒绝。破坏 22+ 现有模块的 ABI，收益远低于成本 |
| **新建 v2 坐标系，逐步迁移** | 拒绝。保留两个坐标系会增加 mental model 复杂度 |
| **不处理，直接使用新概念** | 拒绝。架构债务会因为技术债积累而指数级增长 |

## 后续行动

1. Phase 24：创建 `BeliefInfo` 类，包装 `Information` + 置信度 + 证据链
2. v2.0 发布时：移除 `@deprecated` 标记的旧参数，ABI 断裂一次性处理
3. 每当新增 `Information` 子类时，优先考虑 `metadata` 扩展而非修改基类
