"""BeliefSystem — 置信度门控的信念存储。

信念 = 置信度门控的知识（不是所有知识都是信念）。
只有置信度超过阈值的陈述才被视为信念。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from ocos.self.statement_validator import StatementValidator

if TYPE_CHECKING:
    from ocos.memory.hub import MemoryHub


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
    """信念系统 — 管理置信度门控的信念集合。

    P1-A 持久化写路径（经 StatementValidator L6 门控）:
        - 构造传入 MemoryHub（或事后 bind_hub）后，add() 的陈述
          通过 L6 门控（六类禁止词/长度/事实主语）才写入
          hub.belief().save()；未通过则仅保留内存，rejected_count 累加。
        - 同一 statement 重复 add 采用与内存一致的 max 置信度合并，
          持久化层 INSERT OR REPLACE 不产生重复行。
    """

    def __init__(self, default_threshold: float = 0.6,
                 hub: Optional["MemoryHub"] = None):
        self._beliefs: dict[str, Belief] = {}
        self._default_threshold = default_threshold
        self._lock = threading.RLock()
        self._hub = hub
        self._persisted = 0
        self._rejected = 0

    # ── P1-A 持久化钩子 ───────────────────────────────────────────────────

    def bind_hub(self, hub: "MemoryHub") -> None:
        """绑定 MemoryHub（可在构造后调用 — AgentRuntime 的 hub 晚于 BeliefSystem 创建）。"""
        self._hub = hub

    @property
    def persisted_count(self) -> int:
        """已成功持久化的信念数。"""
        return self._persisted

    @property
    def rejected_count(self) -> int:
        """未通过 L6 门控而被拒持久化的信念数（内存仍保留）。"""
        return self._rejected

    def _persist(self, statement: str, confidence: float,
                 source: "BeliefSource", evidence_ids: tuple[str, ...]) -> None:
        """L6 门控 → 幂等写入 hub.belief()。"""
        if self._hub is None:
            return
        hub = self._hub
        if not hub.is_initialized():
            return

        valid, _reason = StatementValidator.validate(statement)
        if not valid:
            self._rejected += 1
            return

        from ocos.memory.belief.models import Belief as PersistedBelief, BeliefStatus, Evidence

        conf = round(min(1.0, max(0.0, confidence)), 4)
        now = datetime.now(timezone.utc)

        # 幂等：同 statement 已存在的 active belief → 复用 id，置信度取 max（与内存语义一致）
        existing = next(
            (b for b in hub.belief.get_all_active(limit=500) if b.statement == statement),
            None,
        )
        if existing is not None:
            conf = max(existing.confidence, conf)

        evd = Evidence.create(
            source_episode_id=evidence_ids[0] if evidence_ids else "EPI-DIRECT",
            source_pattern_id="",
            quality=conf,
        )
        persisted = PersistedBelief(
            id=existing.id if existing is not None else
               f"BLF-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            statement=statement,
            source_knowledge_ids=(),
            evidence_ids=(evd.id,),
            confidence=conf,
            uncertainty=round(1.0 - conf, 4),
            scope={"domain": source.name.lower(), "preconditions": ""},
            status=BeliefStatus.ACTIVE if conf >= 0.6 else BeliefStatus.WEAKENED,
            created_at=now,
            last_updated=now,
        )
        hub.belief.save(persisted)
        self._persisted += 1

    @property
    def belief_count(self) -> int:
        return len(self._beliefs)

    def add(self, statement: str, confidence: float,
            source: BeliefSource = BeliefSource.OBSERVATION,
            threshold: Optional[float] = None,
            evidence_ids: tuple[str, ...] = ()) -> str:
        """添加或更新信念。如已存在则合并置信度。

        evidence_ids — 可选 Episode 溯源（迁移轨迹: Episode → Evidence → Belief）。
        绑定 hub 时经 L6 门控写入持久化层。
        """
        with self._lock:
            if statement in self._beliefs:
                belief = self._beliefs[statement]
                # 置信度取 max（新证据积累）
                belief.confidence = max(belief.confidence, confidence)
                belief.last_updated = time.time()
                belief.source = source
                self._persist(statement, belief.confidence, source, evidence_ids)
                return belief.id or statement

            belief = Belief(
                statement=statement,
                confidence=confidence,
                source=source,
                id=statement,
            )
            self._beliefs[statement] = belief
            self._persist(statement, confidence, source, evidence_ids)
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
