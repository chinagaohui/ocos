"""Phase 54: Event Memory Infrastructure.

OCOS 的经历记录系统 — 让认知过程可回放、可追溯、可学习。

核心区别:
    Memory = 提炼后的有价值信息 (智慧/经验/画像)
    Event Memory = 认知过程发生的完整轨迹 (谁在何时做了什么，为什么)

完整闭环:
    Perception → EventBus → EventLifecycle.record()
        ↓
    EventStore (append-only, immutable)
        ↓
    EventIndex (multi-dimensional)
        ↓
    EventReplay (read-only, no side effects)
        ↓
    EventArchive (HOT → WARM → COLD)
        ↓
    Personal Memory Intelligence ← Reflection

核心保证:
    EM54-01: Event Integrity — 事件不可篡改
    EM54-02: Timeline Reconstruction — 完整时间线可重建
    EM54-03: Replay Isolation — 回放不含副作用
    EM54-04: Memory Separation — 事件 ≠ 记忆
    EM54-05: Persistence — 跨 session 恢复
    EM54-06: Query — 按时间/类型/目标/实体查询

组件:
    - CognitiveEvent: 统一认知事件 (frozen)
    - EventStore: 追加存储 (immutable append-only)
    - EventIndex: 多维索引 (6 个维度)
    - EventReplay: 回放引擎 (因果链追溯)
    - EventArchiveManager: 生命周期管理 (HOT/WARM/COLD)
    - EventValidator: 完整性验证 (4 条规则)
    - EventQueryEngine: 查询引擎 (store + index)
    - EventLifecycle: 统一生命周期管理器
"""

from ocos.event_memory.event_types import (
    CognitiveEventType, EventConfidence, EventLifecyclePhase,
    EventReference, CognitiveEvent,
    EventHeader, EventArchive, EventQuery,
)
from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_index import EventIndex
from ocos.event_memory.event_replay import EventReplay, ReplaySession
from ocos.event_memory.event_archive import EventArchiveManager, LifecycleConfig
from ocos.event_memory.event_validator import (
    EventValidator, EventValidationResult, ValidationCode,
)
from ocos.event_memory.event_query import EventQueryEngine, QueryResult
from ocos.event_memory.event_lifecycle import EventLifecycle


__all__ = [
    # Types
    "CognitiveEventType", "EventConfidence", "EventLifecyclePhase",
    "EventReference", "CognitiveEvent",
    "EventHeader", "EventArchive", "EventQuery",
    # Store
    "EventStore",
    # Index
    "EventIndex",
    # Replay
    "EventReplay", "ReplaySession",
    # Archive
    "EventArchiveManager", "LifecycleConfig",
    # Validator
    "EventValidator", "EventValidationResult", "ValidationCode",
    # Query
    "EventQueryEngine", "QueryResult",
    # Lifecycle
    "EventLifecycle",
]
