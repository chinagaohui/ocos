# ADR-010: Audit Engine (C2 — 统一审计入口)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: Platform C2, Trace Engine, Governance

---

## 背景

Debug / Compliance / Replay 三类场景各自需要审计数据，但数据来源分散（Trace、Event、Governance 审批记录）。如果没有统一入口，每个场景独立采集会导致数据不一致，且合规审计缺少系统性规则检查。

## 决策

**建立 Audit Engine 作为平台层统一审计入口**。

### 数据模型

```python
@dataclass(frozen=True)
class AuditRecord:
    record_id: str
    record_type: AuditRecordType  # DECISION / GOVERNANCE / EXECUTION / SYSTEM
    event_type: str
    source: str
    summary: str
    details: dict
    timestamp: datetime
    trace_ids: list[str]          # 关联 Trace ID
```

### 采集机制

- 通过 Event Bus 订阅订阅 Decision / Governance / Execution / System 类事件
- Trace Engine (C1) 是内部数据源，外部只通过 Audit Engine 查询
- 支持自动关联：同一 Event 产生的 Trace 记录自动配对

### 审计规则

- 完整性检查：事件链路是否完整（来源→决策→执行→反馈）
- 权限越界检测：Governance 审批是否符合权限矩阵
- 合规报告：周期汇总审计数据生成合规快照

### 统一入口

- Debug：查询审计记录追踪问题根因
- Compliance：导出合规报告
- Replay：根据审计记录恢复执行路径

## 后果

### 获得
- Debug/Compliance/Replay 共享同一数据源，消除不一致
- 审计规则集中管理，新增规则无需修改采集层
- Trace Engine 专注记录，Audit Engine 专注分析，分离关注点

### 代价
- 依赖 Event Bus，Event Bus 故障时审计记录延迟到达
- 额外的关联开销（Trace ID 与 Event 配对）

## 相关 ADR
- ADR-009: Trace Engine (C1)
- ADR-011: Governance Engine (C3)
