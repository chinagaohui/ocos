# ADR 索引

OCOS (Open Cognitive Operating System) 架构决策记录。

| # | 标题 | 影响范围 | 核心决策 |
|---|------|----------|----------|
| 001 | [Decision-Based State Mutation](adr-001-decision-based-state-mutation.md) | Phase 0-1, 全局 | 所有状态修改必须通过 Decision |
| 002 | [Capability Output Isolation](adr-002-capability-output-isolation.md) | Phase 4-5 | LLM 输出必须经 Candidate 转换 |
| 003 | [Contract Boundary](adr-003-contract-boundary.md) | 全局 | 层间通信必须通过 Contract |
| 004 | [Reasoning as Non-Decision](adr-004-reasoning-as-non-decision.md) | Phase 4-5 | Reasoning 不做最终选择 |
| 005 | [Adaptation Governance](adr-005-adaptation-governance.md) | Phase 6 | Adaptation 只能提案，不能执行 |
| 006 | [Capability as Feature](adr-006-capability-as-feature.md) | Phase 5 | Capability 作为独立可拔插特征 |
| 007 | [Runtime Orchestration](adr-007-runtime-orchestration.md) | Phase 7 | Runtime 是纯调度层 |
| 008 | [Runtime Dependency Direction](adr-008-runtime-dependency-direction.md) | Phase 7, Service | service → runtime 禁止静态导入 |
| 009 | [Trace Engine](adr-009-trace-engine.md) | Platform C1 | Trace Engine 独立记录 4 类 Trace，不参与运行时决策 |
| 010 | [Audit Engine](adr-010-audit-engine.md) | Platform C2 | 统一审计入口，Debug/Compliance/Replay 共享数据源 |
| 011 | [Governance Engine](adr-011-governance-engine.md) | Platform C3 | 提案审批工作流，事件驱动解耦下游 |
| 012 | [Plugin Sandbox](adr-012-plugin-sandbox.md) | Platform D2 | Import Hook 白名单 + Permission + 强制超时 |
| 013 | [Plugin Loader](adr-013-plugin-loader.md) | Platform D3 | Loader 与 Sandbox 职责分离，结构化错误码 |
| 014 | [Release Gate](adr-014-release-gate.md) | 全局冻结 | AFP F1-F14 14 维准入标准，自动化审计 |
| 016 | [Knowledge Freeze](ADR-016-knowledge-freeze.md) | Phase 16 | Knowledge Plane 冻结证书 |
| 017 | [Knowledge Plane Split](ADR-017-knowledge-plane-split.md) | 冻结后 | Knowledge Plane 拆分为 Store/Process 两个子平面 |
| 018 | [Architecture Theory Calibration](ADR-018-architecture-theory-calibration.md) | 理论 | Information/Lifecycle/Trace 三层平级、Knowledge 定义、v2.0 路线 |
| 019 | [Process Foundation](ADR-019-process-foundation.md) | Phase 15 | L4 = Process Theory，统一 Process 数据模型 + 事件 + Trace，四条不堆叠原则 |

> **注**: ADR-015 保留，暂未分配。
