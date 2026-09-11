"""Phase 34A: EventBus — OCOS 的感知神经系统（S4.1: 原 ocos/event 重命名）。

架构:
  External World → EventBus → EventNormalizer → CognitiveEvent
  → Step 1 ingest → Step 2 Attention → candidate_score → DECISION

硬约束: 事件 ≠ 意图。EventBus 不直接触发 Goal。

职责分工(GAP-P3-5 裁决): 本包 = 感知神经系统 (外部事件归一化
→ Attention candidate_score, 生产: agent_runtime, Phase 34A
契约测试锁定); ocos/events/ = 宪法 Rule 2 模块间通信总线
(topic pub/sub, 生产: scheduler/policy_engine 等)。两包职责
不同、并存不合并。
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── Event Types ───────────────────────────────────────────────────────────────

class EventSource(Enum):
    """事件来源类型。"""
    FILE_CHANGE = auto()     # 文件系统变更
    TIMER = auto()           # 定时触发
    WEBHOOK = auto()         # HTTP 回调
    AGENT_RESULT = auto()    # Agent 执行结果（内部）
    SYSTEM = auto()          # 系统级事件（内存/CPU 告警）
    USER_INPUT = auto()      # UX-P2: 用户消息（ocos say / REPL /say）


class EventSeverity(Enum):
    """事件严重性 — 影响 Attention candidate_score。"""
    TRIVIAL = 0    # 无关紧要
    LOW = 1        # 低优先级
    NORMAL = 2     # 正常
    HIGH = 3       # 高优先级
    CRITICAL = 4   # 关键


class AttentionDecision(Enum):
    """感知后的认知决策。"""
    IGNORED = auto()      # 忽略：与活跃目标无关
    QUEUED = auto()       # 入队：值得关注但非紧急
    ATTENDED = auto()     # 处理：影响当前认知上下文
    ALERT = auto()        # 告警：需要立即干预


# ── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class RawEvent:
    """原始外部事件 — 在 EventNormalizer 处理之前。"""
    source: EventSource
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: f"EV-{uuid.uuid4().hex[:8]}")


@dataclass
class CognitiveEvent:
    """归一化后的认知事件 — 供 Attention Engine 评估。"""
    event_id: str
    source: EventSource
    event_type: str                      # e.g. "file_modified", "timer_elapsed", "webhook_received"
    summary: str                         # 人类可读摘要
    severity: EventSeverity
    candidate_score: float = 0.5         # 初始分数（归一化器粗估）
    relevant_goals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    normalized_at: float = field(default_factory=time.time)


@dataclass
class IngestionTrace:
    """EVENT_INGESTION_TRACE — 每个事件的完整感知链路追踪。

    格式:
      [EVENT] type=file_changed source=/project/app.py
      [ATTENTION] candidate_score=0.72
      [DECISION] ignored: no related active goal
    """
    event: CognitiveEvent
    attention_score: float
    decision: AttentionDecision
    reason: str
    trace_id: str = field(default_factory=lambda: f"TR-{uuid.uuid4().hex[:8]}")
    traced_at: float = field(default_factory=time.time)


# ── EventNormalizer ───────────────────────────────────────────────────────────

class EventNormalizer:
    """将 RawEvent 归一化为 CognitiveEvent。

    职责:
      1. 类型识别：file_modified / timer_elapsed / webhook_received
      2. 严重性评估：基于事件来源和内容
      3. 初始 relevance score 粗估
      4. 不判断是否触发 Goal — 那是 Attention 的职责
    """

    # 文件路径 → 严重性映射
    _PATH_SEVERITY: dict[str, EventSeverity] = {
        "config": EventSeverity.HIGH,
        "secret": EventSeverity.CRITICAL,
        "test": EventSeverity.LOW,
    }

    def normalize(self, raw: RawEvent) -> CognitiveEvent:
        """归一化一个原始事件。"""
        event_type = self._classify(raw)
        summary = self._summarize(raw, event_type)
        severity = self._assess_severity(raw, event_type)
        score = self._initial_score(severity, raw.source)

        return CognitiveEvent(
            event_id=raw.event_id,
            source=raw.source,
            event_type=event_type,
            summary=summary,
            severity=severity,
            candidate_score=score,
            metadata=raw.payload,
        )

    def _classify(self, raw: RawEvent) -> str:
        """识别事件子类型。"""
        if raw.source == EventSource.FILE_CHANGE:
            op = raw.payload.get("operation", "modified")
            return f"file_{op}"
        if raw.source == EventSource.TIMER:
            return f"timer_{raw.payload.get('name', 'elapsed')}"
        if raw.source == EventSource.WEBHOOK:
            return f"webhook_{raw.payload.get('endpoint', 'received')}"
        if raw.source == EventSource.AGENT_RESULT:
            return "agent_result"
        if raw.source == EventSource.USER_INPUT:
            return "user_input"
        if raw.source == EventSource.SYSTEM:
            # P5.1: Host 细粒度分类 — 读 payload 的 type/operation 字段
            # EnvironmentSensor 用 "type" (memory_critical/memory_high/memory_spike)
            # StimulusScanner 用 "operation" 或 "source"
            subtype = (raw.payload.get("operation")
                       or raw.payload.get("type")
                       or raw.payload.get("source")
                       or None)
            if subtype:
                return f"system_{subtype}"
            return "system_event"
        return "system_event"

    def _summarize(self, raw: RawEvent, event_type: str) -> str:
        """生成人类可读摘要。"""
        if raw.source == EventSource.FILE_CHANGE:
            path = raw.payload.get("path", "?")
            return f"File {event_type.replace('file_', '')}: {path}"
        if raw.source == EventSource.TIMER:
            return f"Timer triggered: {raw.payload.get('name', '?')}"
        if raw.source == EventSource.WEBHOOK:
            return f"Webhook received at {raw.payload.get('endpoint', '?')}"
        if raw.source == EventSource.USER_INPUT:
            return f"User says: {raw.payload.get('content', '?')}"
        if raw.source == EventSource.SYSTEM:
            # P5.1: Host 细粒度摘要 — 从 subtype + payload 组装
            subtype = (raw.payload.get("operation")
                       or raw.payload.get("type")
                       or None)
            if subtype == "memory_critical":
                return f"CRITICAL memory usage: {raw.payload.get('used_mb', '?')} MB"
            if subtype == "memory_high":
                return f"HIGH memory usage: {raw.payload.get('used_mb', '?')} MB"
            if subtype == "memory_spike":
                return f"Memory spike: {raw.payload.get('delta_mb', '?')} MB change"
            if subtype == "cpu_spike":
                return f"CPU spike detected"
            if subtype == "disk_low":
                return f"Low disk space"
            if subtype:
                return f"System {subtype}: {raw.payload}"
            return f"System event: {raw.payload}"
        return f"{raw.source.name}: {raw.payload}"

    def _assess_severity(self, raw: RawEvent, event_type: str) -> EventSeverity:
        """评估事件严重性。"""
        if raw.source == EventSource.FILE_CHANGE:
            path = raw.payload.get("path", "")
            for keyword, sev in self._PATH_SEVERITY.items():
                if keyword in path.lower():
                    return sev
            return EventSeverity.NORMAL
        if raw.source in (EventSource.SYSTEM, EventSource.USER_INPUT):
            return EventSeverity.HIGH
        return EventSeverity.NORMAL

    def _initial_score(self, severity: EventSeverity, source: EventSource) -> float:
        """粗估 attention candidate score。"""
        base = {
            EventSeverity.TRIVIAL: 0.1,
            EventSeverity.LOW: 0.3,
            EventSeverity.NORMAL: 0.5,
            EventSeverity.HIGH: 0.7,
            EventSeverity.CRITICAL: 0.9,
        }[severity]
        # Timer 事件天然优先级略低
        if source == EventSource.TIMER:
            base *= 0.8
        return round(base, 2)


# ── EventBus ──────────────────────────────────────────────────────────────────

class EventBus:
    """OCOS 感知神经中枢。

    职责:
      1. 接收外部事件（push）
      2. 归一化（EventNormalizer）
      3. 暂存供 step 1 拉取（ingest）
      4. 生成 IngestionTrace

    事件 ≠ 意图。EventBus 只负责感知，不负责决策。
    """

    def __init__(self, max_pending: int = 1000) -> None:
        self._normalizer = EventNormalizer()
        self._pending: deque[CognitiveEvent] = deque(maxlen=max_pending)
        self._traces: deque[IngestionTrace] = deque(maxlen=max_pending)
        self._lock = threading.RLock()
        self._total_received: int = 0
        self._total_ingested: int = 0

    # ── Push (external → internal) ──

    def push(self, raw: RawEvent) -> CognitiveEvent:
        """接收外部原始事件 → 归一化 → 入队。"""
        ce = self._normalizer.normalize(raw)
        with self._lock:
            self._pending.append(ce)
            self._total_received += 1
        # S2.9: push 的 DEBUG 日志同样脱敏（原打全文 summary——用户消息明文）
        try:
            from ocos.logging.formatter import redact_text
            _push_summary = redact_text(str(ce.summary), limit=50)
        except Exception:
            _push_summary = str(ce.summary)[:50]
        logger.debug("[EVENT] type=%s source=%s summary=%s",
                     ce.event_type, ce.source.name, _push_summary)
        return ce

    def push_file_change(self, path: str, operation: str = "modified") -> CognitiveEvent:
        """便捷方法：推送文件变更事件。"""
        return self.push(RawEvent(
            source=EventSource.FILE_CHANGE,
            payload={"path": path, "operation": operation},
        ))

    def push_timer(self, name: str, context: dict | None = None) -> CognitiveEvent:
        """便捷方法：推送定时器事件。"""
        return self.push(RawEvent(
            source=EventSource.TIMER,
            payload={"name": name, "context": context or {}},
        ))

    def push_user_message(self, content: str, sender: str = "cli") -> CognitiveEvent:
        """UX-P2: 便捷方法 — 推送用户消息事件（高关注优先级）。"""
        return self.push(RawEvent(
            source=EventSource.USER_INPUT,
            payload={"content": content[:2000], "sender": sender},
        ))

    def push_webhook(self, endpoint: str, data: dict) -> CognitiveEvent:
        """便捷方法：推送 webhook 事件。"""
        return self.push(RawEvent(
            source=EventSource.WEBHOOK,
            payload={"endpoint": endpoint, "data": data},
        ))

    def push_stimulus(self, stim: dict) -> CognitiveEvent:
        """V3 感知-反应（2026-09-07）: 推送 StimulusScanner 环境刺激。

        stim: {key, severity(low/high/critical), description, evidence}
        severity 经 payload 传入，由 EventNormalizer 评估（RawEvent 无
        severity 字段 — 严重性在归一化阶段定级）。
        """
        return self.push(RawEvent(
            source=EventSource.SYSTEM,
            payload={"stimulus": stim,
                     "severity_hint": str(stim.get("severity", "low"))}))

    # ── Ingest (step 1 pulls) ──

    def ingest(self, max_events: int = 10) -> list[CognitiveEvent]:
        """Step 1 拉取待处理事件（drain 语义 — 唯一消费者应在此）。"""
        with self._lock:
            events = []
            while self._pending and len(events) < max_events:
                events.append(self._pending.popleft())
            self._total_ingested += len(events)
            return events

    def peek(self, max_events: int = 10) -> list[CognitiveEvent]:
        """窥视待处理事件但不消费（非 drain — 供 TickPipeline 看但不抢 AgentRuntime 的消费位）。"""
        with self._lock:
            return list(self._pending)[:max_events]

    # ── Attention trace recording ──

    def record_trace(self, event: CognitiveEvent, score: float,
                     decision: AttentionDecision, reason: str) -> IngestionTrace:
        """记录一条完整的感知链路追踪。"""
        trace = IngestionTrace(
            event=event,
            attention_score=score,
            decision=decision,
            reason=reason,
        )
        with self._lock:
            self._traces.append(trace)
        # Log in canonical format
        # S2.9 (白皮书 P2): 用户消息摘要脱敏——不再明文进日志
        try:
            from ocos.logging.formatter import redact_text
            _trace_summary = redact_text(
                str(event.metadata.get("path", event.summary)), limit=50)
        except Exception:
            _trace_summary = str(event.metadata.get("path", event.summary))[:50]
        logger.info(
            "[EVENT] type=%s source=%s | [ATTENTION] candidate_score=%.2f | [DECISION] %s: %s",
            event.event_type,
            _trace_summary,
            score,
            decision.name.lower(),
            reason,
        )
        return trace

    # ── Stats ──

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "pending": len(self._pending),
                "total_received": self._total_received,
                "total_ingested": self._total_ingested,
                "traces_count": len(self._traces),
            }
