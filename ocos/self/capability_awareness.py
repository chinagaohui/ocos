"""Phase 40: CapabilityAwareness — 能力认知。

回答: "我能做什么？"

不是实际能力列表，而是 OCOS 对自身能力的认知。
实际能力在 Capability Registry / ActionLayer 注册。

约束:
    - 能区分 known / unknown / uncertain
    - 每个声明带置信度
    - 来源必须是 CapabilityRegistry（SelfUpdateSource.registry）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import CapabilityStatement


@dataclass
class CapabilityAwareness:
    """SelfModel 的能力认知组件。

    声明 OCOS "认为"自己拥有的能力，不控制实际行为。
    """

    known: dict[str, CapabilityStatement] = field(default_factory=dict)
    """已知可用或不可用的能力。"""

    uncertain: dict[str, CapabilityStatement] = field(default_factory=dict)
    """不确定是否可用的能力。"""

    unavailable_since: dict[str, int] = field(default_factory=dict)
    """记录能力从哪个 tick 开始不可用。"""

    @property
    def known_count(self) -> int:
        return len(self.known)

    @property
    def available_count(self) -> int:
        return sum(1 for c in self.known.values() if c.available)

    @property
    def unavailable_count(self) -> int:
        return sum(1 for c in self.known.values() if not c.available)

    @property
    def uncertain_count(self) -> int:
        return len(self.uncertain)

    @property
    def overall_confidence(self) -> float:
        """整体能力认知置信度。"""
        confidences = [c.confidence for c in self.known.values()]
        confidences += [c.confidence for c in self.uncertain.values()]
        if not confidences:
            return 0.5
        return sum(confidences) / len(confidences)

    def register(self, stmt: CapabilityStatement) -> None:
        """注册一条能力认知声明。"""
        if stmt.confidence >= 0.6:
            target = self.known
        else:
            target = self.uncertain
        target[stmt.name] = stmt

    def get(self, name: str) -> Optional[CapabilityStatement]:
        return self.known.get(name) or self.uncertain.get(name)

    def is_capable(self, name: str) -> Optional[bool]:
        """返回能力是否可用，None = 未知。"""
        stmt = self.get(name)
        if stmt is None:
            return None
        return stmt.available

    def mark_unavailable(self, name: str, tick_id: int) -> None:
        """标记能力不可用。"""
        stmt = self.get(name)
        if stmt:
            self.known[name] = CapabilityStatement(
                name=name,
                available=False,
                confidence=stmt.confidence,
                source=stmt.source,
                last_verified_tick=tick_id,
                notes=f"became unavailable at tick {tick_id}",
            )
            self.unavailable_since.setdefault(name, tick_id)

    def summary(self) -> str:
        return (
            f"CapabilityAwareness: {self.available_count} available, "
            f"{self.unavailable_count} unavailable, "
            f"{self.uncertain_count} uncertain"
        )
