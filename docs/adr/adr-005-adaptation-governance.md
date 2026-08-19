# ADR-005: Adaptation Governance

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 6 Adaptation

---

## 背景

自优化系统容易陷入"为了改动而改动"的陷阱。没有 Governance 的 Adaptation 会成为系统中的不可控因素。

## 决策

**Adaptation 只能提案，不能执行修改。**

- Adaptation 负责采集性能信号和生成演进提案
- Governance 负责审批提案
- 提案被拒绝时保留拒绝原因供 Adaptation 参考

```
Collector → Signal → Proposal
                           ↓
                    Governance
                    /        \
               批准          拒绝
                ↓              ↓
           执行修改        记录原因
```

铁律约束：
- 铁律 37：Adaptation 提案，Governance 批准
- 铁律 35：Capability 不 mutate Kernel
- 铁律 36：Capability 输出是一次性的

## 后果

### 获得
- 系统不会自行"失控优化"
- 每次变更有明确的审查路径
- 拒绝原因可作为 Adaptation 的学习反馈

### 代价
- 适应周期变慢（需要审批步骤）
- 需要 Governance 模块实现审批策略

## 相关 ADR
- ADR-006: Capability as Feature
