"""Phase 24.4-A — Belief & Evidence 数据模型。

Belief = Knowledge + Evidence → 世界假设（置信判断）。
冻结: 无 self/identity/value/goal, statement 第三人称, uncertainty 必填.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── BeliefStatus ─────────────────────────────────────────────────────────────


class BeliefStatus(Enum):
    ACTIVE = "active"           # 当前有效 (confidence >= 0.6)
    WEAKENED = "weakened"       # 可信度下降 (新反证出现)
    INVALIDATED = "invalidated" # 已失效 (反证推翻)
    ARCHIVED = "archived"       # 归档 (不再参与推理)


# ── Evidence ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Evidence:
    """Belief 的证据来源 — 从 Episode 追溯。"""

    id: str
    source_episode_id: str     # 源 Episode
    source_pattern_id: str     # 源 Pattern
    quality: float             # 证据质量 [0.0, 1.0]
    timestamp: datetime
    consistency_score: float   # 与其他证据一致性 [0.0, 1.0]

    @classmethod
    def create(
        cls,
        source_episode_id: str,
        source_pattern_id: str,
        quality: float,
        consistency_score: float = 1.0,
        timestamp: datetime | None = None,
    ) -> "Evidence":
        return cls(
            id=f"EVD-{uuid.uuid4().hex[:8].upper()}",
            source_episode_id=source_episode_id,
            source_pattern_id=source_pattern_id,
            quality=round(max(0.0, min(1.0, quality)), 4),
            timestamp=timestamp or datetime.now(timezone.utc),
            consistency_score=round(max(0.0, min(1.0, consistency_score)), 4),
        )

    @property
    def is_high_quality(self) -> bool:
        return self.quality >= 0.5


# ── Belief ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Belief:
    """Knowledge + Evidence → 世界假设 (不确定层)。

    Belief 是对世界规律的置信判断，不是身份/偏好/目标/价值。
    """

    id: str
    statement: str                             # 世界假设陈述 (第三人称)
    source_knowledge_ids: tuple[str, ...]       # 来源 KnowledgeEntry
    evidence_ids: tuple[str, ...]               # 证据链 Evidence
    confidence: float                           # 当前可信度 [0.0, 1.0]
    uncertainty: float                          # 未知程度 [0.0, 1.0] (不可 None)
    scope: dict                                 # 适用范围 {"domain":..., "preconditions":...}
    status: BeliefStatus
    created_at: datetime
    last_updated: datetime

    def __post_init__(self):
        """Belief 构造器校验 — 防御绕过工厂方法的直接构造。

        宪法约束:
            - confidence ∈ [0.0, 1.0]
            - uncertainty ∈ [0.0, 1.0]
            - confidence > 0 必须有至少一个 evidence_id
            - status 必须为有效 BeliefStatus
            - statement 不可为空
        """
        if not self.id:
            raise ValueError("Belief.id must not be empty")
        if not self.statement:
            raise ValueError("Belief.statement must not be empty")
        if not isinstance(self.status, BeliefStatus):
            raise ValueError(
                f"Belief.status must be BeliefStatus, got {type(self.status).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Belief.confidence must be [0.0, 1.0], got {self.confidence}"
            )
        if not (0.0 <= self.uncertainty <= 1.0):
            raise ValueError(
                f"Belief.uncertainty must be [0.0, 1.0], got {self.uncertainty}"
            )
        if self.confidence > 0.0 and len(self.evidence_ids) == 0:
            raise ValueError(
                "Belief with confidence > 0 must have at least one evidence_id"
            )

    @classmethod
    def create(
        cls,
        statement: str,
        source_knowledge_ids: list[str],
        evidence_ids: list[str],
        confidence: float,
        uncertainty: float,
        scope: dict | None = None,
    ) -> "Belief":
        timestamp = datetime.now(timezone.utc)
        conf = round(max(0.0, min(1.0, confidence)), 4)
        return cls(
            id=f"BLF-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            statement=statement,
            source_knowledge_ids=tuple(source_knowledge_ids),
            evidence_ids=tuple(evidence_ids),
            confidence=conf,
            uncertainty=round(max(0.0, min(1.0, uncertainty)), 4),
            scope=scope or {},
            status=BeliefStatus.ACTIVE if conf >= 0.6 else BeliefStatus.WEAKENED,
            created_at=timestamp,
            last_updated=timestamp,
        )

    @property
    def is_active(self) -> bool:
        return self.status == BeliefStatus.ACTIVE

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_ids)

    def weaken(self) -> "Belief":
        """新反证出现 → WEAKENED。返回新对象，原对象不变。"""
        return Belief(
            id=self.id,
            statement=self.statement,
            source_knowledge_ids=self.source_knowledge_ids,
            evidence_ids=self.evidence_ids,
            confidence=self.confidence,
            uncertainty=min(1.0, self.uncertainty + 0.1),
            scope=self.scope,
            status=BeliefStatus.WEAKENED,
            created_at=self.created_at,
            last_updated=datetime.now(timezone.utc),
        )

    def invalidate(self) -> "Belief":
        """反证推翻 → INVALIDATED。"""
        return Belief(
            id=self.id,
            statement=self.statement,
            source_knowledge_ids=self.source_knowledge_ids,
            evidence_ids=self.evidence_ids,
            confidence=self.confidence,
            uncertainty=min(1.0, self.uncertainty + 0.3),
            scope=self.scope,
            status=BeliefStatus.INVALIDATED,
            created_at=self.created_at,
            last_updated=datetime.now(timezone.utc),
        )

    def archive(self) -> "Belief":
        """归档 → ARCHIVED。不参与后续推理。"""
        return Belief(
            id=self.id,
            statement=self.statement,
            source_knowledge_ids=self.source_knowledge_ids,
            evidence_ids=self.evidence_ids,
            confidence=self.confidence,
            uncertainty=self.uncertainty,
            scope=self.scope,
            status=BeliefStatus.ARCHIVED,
            created_at=self.created_at,
            last_updated=datetime.now(timezone.utc),
        )

    def summary(self) -> str:
        return (
            f"Belief({self.id}): {self.statement[:60]}... "
            f"(conf={self.confidence:.3f}, unc={self.uncertainty:.3f}, "
            f"ev={self.evidence_count}, st={self.status.value})"
        )
