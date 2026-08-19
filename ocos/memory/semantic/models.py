"""Phase 24.3-B — KnowledgeEntry 数据模型。

KnowledgeEntry: 稳定化后的世界知识陈述。
    冻结约束:
        - 不含 self/identity/personality/value 字段
        - statement 必须为第三人称客观描述
        - 必须包含 scope (适用范围) + source_patterns (证据链)
        - 反例可追踪 (counterexamples)

KnowledgeScope: 知识适用范围限定 — 防止泛化为 "我的一般认知"。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class KnowledgeStatus(Enum):
    ACTIVE = "active"           # 当前有效
    SUPERSEDED = "superseded"   # 被更新的 Pattern 替代
    DEPRECATED = "deprecated"   # 不再适用
    UNSTABLE = "unstable"       # 稳定性不足，观察中


@dataclass(frozen=True)
class KnowledgeScope:
    """知识适用范围 — 防止 Knowledge 泛化为绝对真理。"""

    domain: str                          # 适用领域: "resource_management"
    preconditions: tuple[str, ...] = ()  # 前置条件: ("cpu>80%", "task_type=realtime")
    limitations: tuple[str, ...] = ()    # 已知限制: ("不适用于离线任务",)
    counterexamples: int = 0             # 反例数量

    def summary(self) -> str:
        pre = ", ".join(self.preconditions) if self.preconditions else "none"
        lim = ", ".join(self.limitations) if self.limitations else "none"
        return (
            f"Scope({self.domain}) pre=[{pre}] "
            f"lim=[{lim}] counter={self.counterexamples}"
        )

    def has_counterexamples(self) -> bool:
        return self.counterexamples > 0


@dataclass(frozen=True)
class KnowledgeEntry:
    """稳定化后的世界知识陈述。

    KnowledgeEntry 是 Semantic Memory 的核心单位。
    它从 Validated Pattern 升级而来，描述世界运行规律，
    而非系统自身身份。

    禁止字段:
        NO self_attribution
        NO identity_impact
        NO personality_shift
        NO value_judgment
        NO mission_relevance
    """

    id: str
    statement: str                         # 世界规律陈述 (第三人称)
    source_patterns: tuple[str, ...]       # 源 Pattern ID (证据链，只增不删)
    confidence: float                      # 置信度 [0.0, 1.0]
    scope: KnowledgeScope                  # 适用范围
    stability: float                       # 稳定度 [0.0, 1.0] (跨时间一致性)
    revision: int = 1                      # 修订版本
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        statement: str,
        source_patterns: list[str],
        confidence: float,
        scope: KnowledgeScope,
        stability: float = 0.8,
        revision: int = 1,
    ) -> "KnowledgeEntry":
        timestamp = datetime.now(timezone.utc)
        return cls(
            id=f"KNW-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            statement=statement,
            source_patterns=tuple(source_patterns),
            confidence=round(confidence, 4),
            scope=scope,
            stability=round(stability, 4),
            revision=revision,
            status=(
                KnowledgeStatus.UNSTABLE if stability < 0.6
                else KnowledgeStatus.ACTIVE
            ),
            created_at=timestamp,
        )

    @property
    def is_active(self) -> bool:
        return self.status == KnowledgeStatus.ACTIVE

    @property
    def is_unstable(self) -> bool:
        return self.status == KnowledgeStatus.UNSTABLE

    @property
    def counterexample_count(self) -> int:
        return self.scope.counterexamples

    def supersede(self, new_pattern_ids: list[str], new_confidence: float) -> "KnowledgeEntry":
        """创建替代版本（不修改原对象）。"""
        timestamp = datetime.now(timezone.utc)
        all_patterns = set(self.source_patterns) | set(new_pattern_ids)
        return KnowledgeEntry(
            id=f"KNW-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            statement=self.statement,
            source_patterns=tuple(sorted(all_patterns)),
            confidence=round(new_confidence, 4),
            scope=self.scope,  # scope 不变，仅追加 pattern
            stability=self.stability,
            revision=self.revision + 1,
            status=KnowledgeStatus.ACTIVE,
        )

    def summary(self) -> str:
        return (
            f"Knowledge({self.id}): {self.statement[:60]}... "
            f"(conf={self.confidence:.3f}, stb={self.stability:.3f}, "
            f"rev={self.revision}, src={len(self.source_patterns)})"
        )
