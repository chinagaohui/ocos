# ADR-009: Trace Engine (C1 — Explainability)

**状态**: 已采纳
**日期**: 2026-07-22
**决策者**: OCOS Architecture Board
**影响范围**: Platform C1, Audit Engine, Runtime

---

## 背景

Runtime 和 Control Plane 的执行过程缺乏可观察性。Decision/Reasoning/Simulation/Learning 的关键路径不可追溯，导致 Debug 困难、合规审计缺乏原始数据、重放场景缺少事件锚点。

## 决策

**建立独立的 Trace Engine**，作为平台层可解释性追踪的数据记录器。

### 数据模型

4 类 Trace 使用独立枚举 `TraceType`（DECISION / REASONING / SIMULATION / LEARNING），统一 `TraceRecord` 结构：

```python
@dataclass(frozen=True)
class TraceRecord:
    trace_id: str          # UUID
    trace_type: TraceType
    event_id: str          # 关联 Event ID（可选）
    agent_id: str          # 来源 Agent/组件
    timestamp: datetime
    content: dict          # Trace 载荷
    parent_trace_id: Optional[str]  # 调用链
    metadata: dict         # 附加元数据
```

### 存储策略

InMemory TraceStore，环形缓冲区（默认 10_000 上限），避免内存泄漏。

### 查询接口

- `record_decision_trace / record_reasoning_trace / ...` — 记录入口
- `query_traces(filter) → List[TraceRecord]` — 多条件查询
- `get_trace(trace_id) → TraceRecord` — 单条检索

### 集成策略

- 可选集成 Event Bus：记录时发射 `TRACE_RECORDED` 事件供 Audit Engine 消费
- **Trace Engine 不参与运行时决策**，即使 TraceStore 故障也不影响系统正常运行

## 后果

### 获得
- Decision/Reasoning/Simulation/Learning 四类路径可追溯
- Audit Engine 直接消费 Trace 数据，无需重复采集
- Debug 和 Replay 场景有统一数据源

### 代价
- 每次记录有内存写入开销（环形缓冲区上限控制）
- 缺少持久化存储（当前为 InMemory，后续可扩展）

## 相关 ADR
- ADR-010: Audit Engine (C2)
- ADR-007: Runtime Orchestration
