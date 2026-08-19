# ADR-007: Runtime Orchestration

**状态**: 已采纳
**日期**: 2026-07-20
**决策者**: OCOS Architecture Board
**影响范围**: Phase 7 Runtime

---

## 背景

Phase 1-6 的认知模块各自独立运行，缺乏统一的编排机制。引入事件驱动循环是为了让各模块按固定顺序协调工作，而不赋予其认知决策能力。

## 决策

**Runtime 是纯调度层，不持有任何认知权力。**

铁律约束：
- 铁律 40: Orchestrator coordinates, never decides
- 铁律 41: Runtime does not persist
- 铁律 42: Runtime does not import kernel internals
- 铁律 43: Modules communicate only through Contracts

编排顺序：
```
Event → LoopController → LifecycleManager (创建会话)
                              ↓
                       Orchestrator
                         ├── Perception
                         ├── Retrieval
                         ├── Recommendation
                         ├── Capability
                         └── Reasoning
                              ↓
                       RuntimeResult (不含 Decision)
```

**删除证明**: 删除 `runtime/` 后系统回退至 Phase 6（648 passed）。

## 后果

### 获得
- 认知模块执行顺序统一管理
- 模块失败不影响整体运行（降级运行）
- 运行时层可删除，不影响核心认知

### 代价
- 需要管理 RuntimeContext 生命周期
- 编排层无法进行优化排序

## 相关 ADR
- ADR-008: Runtime Dependency Direction
