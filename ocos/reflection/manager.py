"""Phase AE: SelfReflectionManager — 自我反思与元认知管理器。

整合 ReflectionEngine + EventReplay + FeedbackLoop，
提供统一的自我反思接口：
- 行为反思（回顾决策过程）
- 结果反思（评估执行效果）
- 模式识别（发现重复模式）
- 智慧积累（从经验中学习）
- 身份连续性检查

架构原则：
- AE-REF-01: 反思必须基于真实经历
- AE-REF-02: 反思结果必须可追溯
- AE-REF-03: 智慧积累需要验证
- AE-REF-04: 身份连续性是核心约束
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


class ReflectionType(Enum):
    """反思类型。"""
    BEHAVIOR = auto()      # 行为反思
    RESULT = auto()        # 结果反思
    PATTERN = auto()       # 模式反思
    IDENTITY = auto()      # 身份反思
    GOAL = auto()          # 目标反思


class ReflectionDepth(Enum):
    """反思深度。"""
    SUPERFICIAL = "superficial"   # 表面观察
    ANALYTICAL = "analytical"     # 分析推理
    DEEP = "deep"                 # 深度洞察
    WISDOM = "wisdom"             # 智慧提取


class InsightType(Enum):
    """洞察类型。"""
    SUCCESS_FACTOR = "success_factor"
    FAILURE_CAUSE = "failure_cause"
    PATTERN_RECOGNIZED = "pattern"
    IMPROVEMENT_SUGGESTION = "improvement"
    WISDOM_CANDIDATE = "wisdom"


@dataclass
class ReflectionTrace:
    """反思轨迹。"""
    trace_id: str
    reflection_type: ReflectionType
    depth: ReflectionDepth
    subject_id: str
    insights: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def duration(self) -> float:
        if self.completed_at > 0:
            return self.completed_at - self.created_at
        return time.time() - self.created_at


@dataclass
class WisdomItem:
    """智慧条目。"""
    wisdom_id: str
    content: str
    source_trace_id: str
    confidence: float
    verified: bool = False
    created_at: float = 0.0
    usage_count: int = 0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class IdentitySnapshot:
    """身份快照。"""
    snapshot_id: str
    timestamp: float
    identity_state: dict[str, Any]
    continuity_score: float  # 0.0-1.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class SelfReflectionManager:
    """自我反思管理器。

    统一管理层：
    1. 行为反思
    2. 结果评估
    3. 模式识别
    4. 智慧积累
    5. 身份连续性检查
    """

    def __init__(
        self,
        max_reflections: int = 1000,
        max_wisdom_items: int = 100,
        max_identity_snapshots: int = 500,
        min_wisdom_confidence: float = 0.7,
    ):
        self._max_reflections = max_reflections
        self._max_wisdom_items = max_wisdom_items
        self._max_identity_snapshots = max_identity_snapshots
        self._min_wisdom_confidence = min_wisdom_confidence

        # 反思轨迹
        self._reflections: dict[str, ReflectionTrace] = {}
        self._reflection_lock = threading.RLock()

        # 智慧存储
        self._wisdom: dict[str, WisdomItem] = {}
        self._wisdom_lock = threading.RLock()

        # 身份快照
        self._identity_snapshots: list[IdentitySnapshot] = []
        self._identity_lock = threading.RLock()

        # 统计
        self._stats = {
            "reflections_performed": 0,
            "insights_generated": 0,
            "wisdom_candidates": 0,
            "wisdom_confirmed": 0,
            "wisdom_rejected": 0,
            "identity_checks": 0,
        }

    # ── 反思执行 ────────────────────────────────────────────────

    def start_reflection(
        self,
        reflection_type: ReflectionType,
        subject_id: str,
        depth: ReflectionDepth = ReflectionDepth.ANALYTICAL,
    ) -> ReflectionTrace | None:
        """开始一次反思。"""
        with self._reflection_lock:
            if len(self._reflections) >= self._max_reflections:
                logger.warning("Max reflections reached (%d)", self._max_reflections)
                return None

            trace_id = f"ref:{uuid.uuid4().hex[:8]}"
            trace = ReflectionTrace(
                trace_id=trace_id,
                reflection_type=reflection_type,
                depth=depth,
                subject_id=subject_id,
            )
            self._reflections[trace_id] = trace
            self._stats["reflections_performed"] += 1
            logger.info("Reflection started: %s (type=%s, depth=%s)",
                       trace_id, reflection_type.name, depth.value)
            return trace

    def add_insight(
        self,
        trace_id: str,
        insight_type: InsightType,
        content: str,
        confidence: float = 0.5,
    ) -> bool:
        """添加反思洞察。"""
        with self._reflection_lock:
            trace = self._reflections.get(trace_id)
            if not trace:
                return False

            insight = {
                "insight_id": f"ins:{uuid.uuid4().hex[:8]}",
                "type": insight_type.value,
                "content": content,
                "confidence": confidence,
                "timestamp": time.time(),
            }
            trace.insights.append(insight)
            self._stats["insights_generated"] += 1
            return True

    def complete_reflection(self, trace_id: str) -> bool:
        """完成反思。"""
        with self._reflection_lock:
            trace = self._reflections.get(trace_id)
            if not trace:
                return False
            trace.completed_at = time.time()
            logger.info("Reflection completed: %s (duration=%.2fs, insights=%d)",
                       trace_id, trace.duration, len(trace.insights))
            return True

    def get_reflection(self, trace_id: str) -> ReflectionTrace | None:
        """获取反思轨迹。"""
        with self._reflection_lock:
            return self._reflections.get(trace_id)

    def list_reflections(
        self,
        reflection_type: ReflectionType | None = None,
        limit: int = 50,
    ) -> list[ReflectionTrace]:
        """列出反思轨迹。"""
        with self._reflection_lock:
            traces = list(self._reflections.values())
            if reflection_type:
                traces = [t for t in traces if t.reflection_type == reflection_type]
            return traces[-limit:]

    # ── 智慧管理 ────────────────────────────────────────────────

    def propose_wisdom(
        self,
        trace_id: str,
        content: str,
        confidence: float = 0.5,
    ) -> WisdomItem | None:
        """提出智慧候选。"""
        with self._reflection_lock:
            trace = self._reflections.get(trace_id)
            if not trace:
                return None

        with self._wisdom_lock:
            if len(self._wisdom) >= self._max_wisdom_items:
                logger.warning("Max wisdom items reached (%d)", self._max_wisdom_items)
                return None

            wisdom_id = f"wis:{uuid.uuid4().hex[:8]}"
            wisdom = WisdomItem(
                wisdom_id=wisdom_id,
                content=content,
                source_trace_id=trace_id,
                confidence=confidence,
            )
            self._wisdom[wisdom_id] = wisdom
            self._stats["wisdom_candidates"] += 1
            logger.info("Wisdom candidate proposed: %s (confidence=%.2f)",
                       wisdom_id, confidence)
            return wisdom

    def verify_wisdom(self, wisdom_id: str, result: bool) -> bool:
        """验证智慧候选。"""
        with self._wisdom_lock:
            wisdom = self._wisdom.get(wisdom_id)
            if not wisdom:
                return False

            wisdom.verified = result
            if result:
                self._stats["wisdom_confirmed"] += 1
                logger.info("Wisdom confirmed: %s", wisdom_id)
            else:
                self._stats["wisdom_rejected"] += 1
                logger.info("Wisdom rejected: %s", wisdom_id)
            return True

    def get_wisdom(self, wisdom_id: str) -> WisdomItem | None:
        """获取智慧条目。"""
        with self._wisdom_lock:
            return self._wisdom.get(wisdom_id)

    def list_wisdom(
        self,
        verified_only: bool = False,
        limit: int = 50,
    ) -> list[WisdomItem]:
        """列出智慧条目。"""
        with self._wisdom_lock:
            items = list(self._wisdom.values())
            if verified_only:
                items = [w for w in items if w.verified]
            return items[-limit:]

    def increment_wisdom_usage(self, wisdom_id: str) -> bool:
        """增加智慧使用次数。"""
        with self._wisdom_lock:
            wisdom = self._wisdom.get(wisdom_id)
            if wisdom:
                wisdom.usage_count += 1
                return True
            return False

    # ── 身份连续性检查 ──────────────────────────────────────────

    def create_identity_snapshot(
        self,
        identity_state: dict[str, Any],
        continuity_score: float = 1.0,
    ) -> IdentitySnapshot:
        """创建身份快照。"""
        with self._identity_lock:
            if len(self._identity_snapshots) >= self._max_identity_snapshots:
                # 移除最旧的快照
                self._identity_snapshots.pop(0)

            snapshot_id = f"snap:{uuid.uuid4().hex[:8]}"
            snapshot = IdentitySnapshot(
                snapshot_id=snapshot_id,
                timestamp=time.time(),
                identity_state=identity_state,
                continuity_score=continuity_score,
            )
            self._identity_snapshots.append(snapshot)
            self._stats["identity_checks"] += 1
            logger.debug("Identity snapshot created: %s (continuity=%.2f)",
                        snapshot_id, continuity_score)
            return snapshot

    def check_identity_continuity(
        self,
        current_state: dict[str, Any],
        window: int = 10,
    ) -> dict[str, Any]:
        """检查身份连续性。"""
        with self._identity_lock:
            recent = self._identity_snapshots[-window:] if self._identity_snapshots else []

        if not recent:
            return {
                "continuity_score": 1.0,
                "drift_detected": False,
                "recommendation": "no_history",
            }

        # 计算平均连续性分数
        avg_score = sum(s.continuity_score for s in recent) / len(recent)

        # 检测漂移
        drift = avg_score < 0.7

        return {
            "continuity_score": avg_score,
            "drift_detected": drift,
            "recommendation": "investigate" if drift else "normal",
            "snapshot_count": len(recent),
        }

    def get_latest_snapshot(self) -> IdentitySnapshot | None:
        """获取最新身份快照。"""
        with self._identity_lock:
            return self._identity_snapshots[-1] if self._identity_snapshots else None

    # ── 批量反思 ────────────────────────────────────────────────

    def batch_reflect(
        self,
        events: list[dict[str, Any]],
        reflection_type: ReflectionType = ReflectionType.RESULT,
        depth: ReflectionDepth = ReflectionDepth.ANALYTICAL,
    ) -> list[ReflectionTrace]:
        """批量反思多个事件。"""
        traces = []
        for event in events:
            trace = self.start_reflection(
                reflection_type=reflection_type,
                subject_id=event.get("subject_id", event.get("id", "unknown")),
                depth=depth,
            )
            if trace:
                # 添加洞察
                if event.get("success"):
                    self.add_insight(
                        trace.trace_id,
                        InsightType.SUCCESS_FACTOR,
                        event.get("analysis", "Success"),
                        event.get("confidence", 0.8),
                    )
                else:
                    self.add_insight(
                        trace.trace_id,
                        InsightType.FAILURE_CAUSE,
                        event.get("analysis", "Failure"),
                        event.get("confidence", 0.7),
                    )
                self.complete_reflection(trace.trace_id)
                traces.append(trace)
        return traces

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._reflection_lock:
            reflection_count = len(self._reflections)
        with self._wisdom_lock:
            wisdom_count = len(self._wisdom)
            verified_count = sum(1 for w in self._wisdom.values() if w.verified)
        with self._identity_lock:
            snapshot_count = len(self._identity_snapshots)

        return {
            **self._stats,
            "reflection_count": reflection_count,
            "wisdom_count": wisdom_count,
            "verified_wisdom_count": verified_count,
            "snapshot_count": snapshot_count,
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "reflections_performed": 0,
            "insights_generated": 0,
            "wisdom_candidates": 0,
            "wisdom_confirmed": 0,
            "wisdom_rejected": 0,
            "identity_checks": 0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._reflection_lock:
            self._reflections.clear()
        with self._wisdom_lock:
            self._wisdom.clear()
        with self._identity_lock:
            self._identity_snapshots.clear()
        logger.info("SelfReflectionManager closed")


__all__ = [
    "SelfReflectionManager",
    "ReflectionTrace",
    "WisdomItem",
    "IdentitySnapshot",
    "ReflectionType",
    "ReflectionDepth",
    "InsightType",
]
