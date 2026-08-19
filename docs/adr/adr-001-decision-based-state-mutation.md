# ADR-001: Decision-Based State Mutation

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 0 Reality, Phase 1 Experience, 全局

---

## 背景

认知系统的核心问题：状态的修改权归谁？初始设计中存在多处直接写入事件存储的路径，导致状态溯源困难。

## 决策

**所有状态修改必须通过 Decision**。Decision 是唯一的写入口。

```
External Input → Event → Intent → Decision → EventStore.append()
```

Constitution 在 Decision 层执行验证：
- `can_commit`: 检查 Decision 是否合法
- `validate`: 校验 Decision 内容
- `assert_invariant`: 确保系统不变量

## 后果

### 获得
- 所有状态变更可溯源
- 写入前有统一的验证关卡
- 审计日志自然生成

### 代价
- 读路径不能直接写状态
- 每个写入操必须构造 Decision

## 相关 ADR
- ADR-004: Reasoning as Non-Decision
