"""Phase 54: Event Memory Infrastructure — Types.

EM54-01: Event Integrity — 事件不可篡改 (追加写入 + 校验)
EM54-02: Timeline Reconstruction — 支持完整时间线重建
EM54-03: Replay Isolation — 回放不触发实际动作
EM54-04: Memory Separation — Event ≠ Memory，事件是过程记录
EM54-05: Persistence — 跨 session 可恢复
EM54-06: Query — 按时间/类型/目标/实体 多维查询

核心区别:
    Memory = 有价值的提炼信息 (智慧/经验/画像)
    Event Memory = 认知过程发生的完整轨迹 (谁在何时做了什么，为什么)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time as _time


class CognitiveEventType(str, Enum):
    """认知事件类型 — 覆盖完整的认知-行动-反思过程。

    一个认知 Tick 产生多个 Event:
        Perception → Attention → Decision → Action → Result → Learning
    """
    PERCEPTION = "perception"     # 感知到输入
    ATTENTION = "attention"       # 注意力分配/转移
    DECISION = "decision"         # 决策形成
    ACTION = "action"             # 行动执行
    RESULT = "result"             # 结果反馈
    LEARNING = "learning"         # 经验提炼
    INTERACTION = "interaction"    # 与用户交互
    HEALTH = "health"            # 自身健康检查
    EVOLUTION = "evolution"      # 架构演进


class EventConfidence(str, Enum):
    """事件可信度。"""
    CERTAIN = "certain"           # 自己产生的，100%可信
    HIGH = "high"                 # 来自可靠来源
    MEDIUM = "medium"             # 需要交叉验证
    LOW = "low"                   # 可能有偏差


class EventLifecyclePhase(str, Enum):
    """事件生命周期阶段。"""
    HOT = "hot"       # 最近事件 (活跃内存)
    WARM = "warm"     # 近期历史 (磁盘可快速访问)
    COLD = "cold"     # 长期归档 (压缩/可恢复)
    ARCHIVED = "archived"  # 已归档但可解冻


@dataclass(frozen=True)
class EventReference:
    """事件引用 — 不可变的轻量指针。"""
    event_id: str
    event_type: CognitiveEventType
    timestamp: float


@dataclass(frozen=True)
class CognitiveEvent:
    """统一认知事件 — EM 的最小记录单元。

    frozen=True 保证 EM54-01: 已写入的事件不可篡改。

    一个事件记录了一个认知动作的完整上下文:
        - 谁 (source)
        - 什么时候 (timestamp)
        - 发生了什么 (event_type, payload)
        - 为什么 (context)
        - 可信度 (confidence)
        - 与之关联的其他事件 (links_to, caused_by)
    """

    event_id: str
    event_type: CognitiveEventType
    timestamp: float = field(default_factory=_time.time)

    # 来源
    source: str = ""        # 触发模块 (perception/attention/decision/...)

    # 上下文 — 为什么会发生
    context: dict = field(default_factory=dict)

    # 载荷 — 发生了什么
    payload: object = None

    # 可信度
    confidence: EventConfidence = EventConfidence.HIGH

    # 因果链
    caused_by: EventReference | None = None   # 前序事件
    links_to: list[EventReference] = field(default_factory=list)  # 关联事件

    # 元数据
    metadata: dict = field(default_factory=dict)

    # 生命周期追踪
    lifecycle: EventLifecyclePhase = EventLifecyclePhase.HOT
    archived_at: float = 0.0

    @property
    def age_seconds(self) -> float:
        return _time.time() - self.timestamp

    @property
    def is_recent(self) -> bool:
        return self.age_seconds < 3600  # 1小时内

    def to_reference(self) -> EventReference:
        return EventReference(
            event_id=self.event_id,
            event_type=self.event_type,
            timestamp=self.timestamp,
        )

    def with_lifecycle(self, phase: EventLifecyclePhase) -> CognitiveEvent:
        """创建生命周期变更的副本 (保留不可变性)。"""
        return CognitiveEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            timestamp=self.timestamp,
            source=self.source,
            context=dict(self.context),
            payload=self.payload,
            confidence=self.confidence,
            caused_by=self.caused_by,
            links_to=list(self.links_to),
            metadata=dict(self.metadata),
            lifecycle=phase,
            archived_at=_time.time() if phase == EventLifecyclePhase.ARCHIVED else self.archived_at,
        )


@dataclass
class EventHeader:
    """事件头 — 轻量摘要，用于列表和索引扫描。

    不包含 payload，只有元数据。
    """
    event_id: str
    event_type: CognitiveEventType
    timestamp: float
    source: str
    confidence: EventConfidence
    lifecycle: EventLifecyclePhase
    context_keys: list[str] = field(default_factory=list)  # 加速索引查询
    metadata_keys: list[str] = field(default_factory=list)

    @classmethod
    def from_event(cls, event: CognitiveEvent) -> "EventHeader":
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            source=event.source,
            confidence=event.confidence,
            lifecycle=event.lifecycle,
            context_keys=list(event.context.keys()),
            metadata_keys=list(event.metadata.keys()),
        )


@dataclass
class EventArchive:
    """事件归档记录 — 压缩后的批量事件。"""
    archive_id: str
    start_time: float
    end_time: float
    event_count: int
    compressed_data: bytes = b""
    checksum: str = ""
    created_at: float = field(default_factory=_time.time)

    def can_restore(self) -> bool:
        return bool(self.compressed_data) and bool(self.checksum)


@dataclass
class EventQuery:
    """事件查询参数 — 支持多维过滤。"""
    event_types: list[CognitiveEventType] | None = None
    sources: list[str] | None = None
    time_from: float | None = None
    time_to: float | None = None
    entity: str | None = None           # 提及的实体
    goal_id: str | None = None          # 关联的目标
    confidence_min: EventConfidence | None = None
    lifecycle: EventLifecyclePhase | None = None
    context_has_key: str | None = None  # context 中有关键词
    limit: int = 100
    offset: int = 0


__all__ = [
    "CognitiveEventType", "EventConfidence", "EventLifecyclePhase",
    "EventReference", "CognitiveEvent",
    "EventHeader", "EventArchive", "EventQuery",
]
