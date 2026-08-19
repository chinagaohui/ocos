# ADR-018: 架构理论校准 — Information 层级重构

| 属性 | 值 |
|------|-----|
| **ADR 编号** | 018 |
| **状态** | Accepted |
| **日期** | 2026-07-22 |
| **发起人** | 架构评审（用户反馈） |
| **影响范围** | INFORMATION_THEORY.md, KNOWLEDGE_MODEL.md, OCOS_CORE_CONSTITUTION.md, 全部引擎 |
| **前置依赖** | ADR-016 (Knowledge Freeze), ADR-017 (Knowledge Plane Split) |

---

## 背景

OCOS MEMORY AUDIT v2.0 完成后，架构师级别的评审指出了 7 个尚未彻底统一的理论问题：

1. **InformationState 不属于 Information** — 状态是 Lifecycle 的属性
2. **Address 没有真正统一** — 当前偏 Storage，应偏 "我要找什么"
3. **Trace 不是 Information** — 而是变化记录
4. **Knowledge 没有数学定义** — 缺少形式化定义
5. **MemoryTrace 不应绑定 WorkingMemory** — 应全局记录
6. **MemoryModel.md 是否真正需要** — 结论：不需要
7. **缺少 Information Graph** — 关系网络引擎缺失

---

## 决策

### 1. Information → LifecycleRecord → Trace 三层平级

**之前：** Trace 被视为 Semantic Role=R_M 的 Information。
**之后：**

```
Information（被操作的对象，不可变）
          │
          ├── LifecycleRecord（状态变迁记录）
          └── Trace（操作证据链记录）
```

**影响文件：** INFORMATION_THEORY.md — 添加附录 C；修正 Appendix A。

### 2. Knowledge 的定义

**之前：** Knowledge = Stable Information（过弱）。
**之后：** Knowledge = Verified + Generalizable + Stable Information。

**影响文件：** KNOWLEDGE_MODEL.md — 第一章添加此定义。

### 3. MemoryModel.md 不创建

**之前：** MEMORY_AUDIT 建议创建。
**之后：** 如果 Information Theory + Lifecycle + Knowledge Model 已完整，Memory 只是 PersistenceLevel 的投影，不需要独立文档。

### 4. 不立即变更（已记录待 v2.0）

| 项目 | 计划版本 | 备注 |
|------|----------|------|
| InformationState 从 Information 中分离 | v2.0 | 影响 WorkingMemory + 4 引擎 |
| Address 从 Storage 向 Cognitive 转型 | v2.0 | UniversalAddress → AddressIntent |
| Information Graph Engine | v2.0 | 关系网络，Phase 17 候选 |
| MemoryTrace 全局化（不绑定 WorkingMemory）| v2.0 | 所有引擎记录 Trace |
| 宪法 §1.1 Memory 指向 Information Theory | v2.0 | 宪法修订周期 |

---

## 理由

- Trace 如果被当作 Information，逻辑上可被 Promotion/Consolidation/Forgetting 消费（工程上被架构测试禁止，但理论上存在裂缝）。明确三层平级后，工程约束有了理论根基。
- Knowledge 如果没有数学定义，任何知识操作（创建、验证、提升）都没有标准判断"是否达到了 Knowledge 级别"。`Verified + Generalizable + Stable` 给出了可操作的判定条件。
- 不创建 MemoryModel.md 的原因是：如果低层理论已经完整，Memory 是 PersistenceLevel 上的投影，为"投影"再写一份独立文档会产生语义冗余和潜在的自我矛盾风险。

---

## 影响评估

| 影响 | 范围 | 严重度 |
|------|------|--------|
| INFORMATION_THEORY.md | v1.0 → v1.1（附录新增，正文不变）| 低 |
| KNOWLEDGE_MODEL.md | 新创建 | 低 |
| ADR-018 本身 | 纯记录，无代码变化 | 无 |
| 代码库（engine/*, model/*） | 无变化 | 无 |
| 1187 测试 | 全部通过 | 无 |

所有变更均为文档层面的理论校准，不破坏任何冻结协议。

---

## 参考资料

- [OCOS MEMORY AUDIT v2.0](../OCOS_MEMORY_AUDIT.md)
- [INFORMATION_THEORY v1.0 → v1.1](../INFORMATION_THEORY.md)
- [KNOWLEDGE_MODEL v1.0](../KNOWLEDGE_MODEL.md)
