"""BeliefSystem — 置信度门控的信念存储。

信念 = 置信度门控的知识（不是所有知识都是信念）。
只有置信度超过阈值的陈述才被视为信念。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class BeliefSource(Enum):
    """信念来源。"""
    OBSERVATION = auto()       # 直接观察
    INFERENCE = auto()         # 推理得出
    TESTIMONY = auto()         # 外部输入
    CONSOLIDATION = auto()     # 记忆巩固
    REFLECTION = auto()        # 自我反思


@dataclass
class Belief:
    """一条信念。"""
    statement: str
    confidence: float           # 0.0 ~ 1.0
    source: BeliefSource
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    access_count: int = 0
    id: Optional[str] = None

    def is_held(self, threshold: float = 0.6) -> bool:
        """信念是否被持有（置信度超过阈值）。"""
        return self.confidence >= threshold

    def decay(self, rate: float = 0.01) -> None:
        """自然衰减置信度。"""
        self.confidence = max(0.0, self.confidence - rate)
        self.last_updated = time.time()


class BeliefSystem:
    """信念系统 — 管理置信度门控的信念集合。"""

    def __init__(self, default_threshold: float = 0.6):
        self._beliefs: dict[str, Belief] = {}
        self._default_threshold = default_threshold
        self._lock = threading.RLock()

    @property
    def belief_count(self) -> int:
        return len(self._beliefs)

    def add(self, statement: str, confidence: float,
            source: BeliefSource = BeliefSource.OBSERVATION,
            threshold: Optional[float] = None) -> str:
        """添加或更新信念。如已存在则合并置信度。"""
        with self._lock:
            if statement in self._beliefs:
                belief = self._beliefs[statement]
                # 置信度取 max（新证据积累）
                belief.confidence = max(belief.confidence, confidence)
                belief.last_updated = time.time()
                belief.source = source
                return belief.id or statement

            belief = Belief(
                statement=statement,
                confidence=confidence,
                source=source,
                id=statement,
            )
            self._beliefs[statement] = belief
            return statement

    def get_held(self, threshold: Optional[float] = None) -> list[Belief]:
        """获取当前持有的信念（置信度 >= 阈值）。"""
        th = threshold if threshold is not None else self._default_threshold
        with self._lock:
            return [b for b in self._beliefs.values() if b.is_held(th)]

    def get_all(self) -> list[Belief]:
        """获取所有信念（包括置信度低的）。"""
        with self._lock:
            return list(self._beliefs.values())

    def query(self, statement: str,
              threshold: Optional[float] = None) -> Optional[Belief]:
        """查询特定信念。只有置信度 >= 阈值的才返回。"""
        th = threshold if threshold is not None else self._default_threshold
        with self._lock:
            belief = self._beliefs.get(statement)
            if belief and belief.is_held(th):
                belief.access_count += 1
                return belief
            return None

    def challenge(self, statement: str) -> bool:
        """质疑信念（降低置信度）。返回信念是否已被移除。"""
        with self._lock:
            belief = self._beliefs.get(statement)
            if not belief:
                return True
            belief.confidence *= 0.5  # 质疑后置信度腰斩
            if belief.confidence < self._default_threshold:
                del self._beliefs[statement]
                return True
            return False

    def decay_all(self, rate: float = 0.01) -> int:
        """对所有信念执行自然衰减。返回衰减到阈值之下的数量。"""
        with self._lock:
            removed = 0
            to_remove = []
            for key, belief in self._beliefs.items():
                belief.decay(rate)
                if not belief.is_held(self._default_threshold):
                    to_remove.append(key)
            for key in to_remove:
                del self._beliefs[key]
                removed += 1
            return removed

    def clear(self) -> None:
        """清空所有信念。"""
        with self._lock:
            self._beliefs.clear()
