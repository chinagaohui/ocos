# ADR-011: Governance Engine (C3 — 提案审批工作流)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: Platform C3, Policy Engine, Audit Engine, Knowledge Plane

---

## 背景

Knowledge 提升、Policy 变更、系统参数修改等操作需要审批流程，否则可能绕过宪法约束直接修改系统状态。Phase 5 (Constitution) 要求 Governance 审批知识变更，但缺少具体的工作流实现。

## 决策

**建立 Governance Engine**，作为 Governance 层的唯一入口，管理 EvolutionProposal 全生命周期。

### 提案状态机

```
PENDING → UNDER_REVIEW → APPROVED | REJECTED
PENDING → CANCELLED
UNDER_REVIEW → CANCELLED
```

3 类提案类型：POLICY_CHANGE / KNOWLEDGE_PROMOTION / SYSTEM_CHANGE

### 事件集成

- 审批完成时通过 Event Bus 发射 `GOVERNANCE_APPROVED` / `GOVERNANCE_REJECTED` 事件
- PolicyEngine 通过订阅事件自动响应
- AuditEngine 通过订阅 Governance 事件自动生成审计记录
- **GovernanceEngine 不知道下游模块的存在**，事件发射即是全部

### 边界规则

- GovernanceEngine 只负责提案审批工作流
- 不执行变更操作（不变更系统状态）
- 不校验提案内容（内容校验由 KnowledgeValidator / PolicyEngine 负责）
- 审批通过后，变更由其他模块通过 Event Bus 事件驱动执行

## 后果

### 获得
- 提案审批流程标准化，所有变更经过同一管道
- 事件驱动解耦，GovernanceEngine 不依赖下游模块
- 审计自动生成，无需 Governance 额外关心

### 代价
- 提案流转有延迟（PENDING → APPROVED 需要外部 REVIEW）
- 取消操作需要额外状态管理（CANCELLED 路径）

## 相关 ADR
- ADR-010: Audit Engine (C2)
- ADR-005: Adaptation Governance
