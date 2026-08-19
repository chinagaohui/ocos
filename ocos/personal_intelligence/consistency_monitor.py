"""Phase 48: ConsistencyMonitor — 长期一致性监控。

检查 OCOS 在长时间运行后核心属性是否保持稳定。

监控维度:
    - Identity 稳定性: Self.anchor 是否被触碰
    - Memory 健康: 记忆量/增长速度/老化
    - Wisdom 积累速率: 智慧是否在沉淀
    - Decision 模式稳定性: 决策逻辑是否漂移
    - Goal 对齐: 是否偏离用户目标
    - Personalization 深度: 个性化是否在深化

边界 PM48-04: Consistency ≠ Rigidity
    保持身份稳定，同时允许 Phase 47 治理下的演化。
    一致性是基线参照，不是阻止演化的锁。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import (
    ConsistencyMetrics, MaturityLevel,
)


@dataclass
class ConsistencyMonitor:
    """长期一致性监控——PM48-04 守卫。

    不阻止演化 (Phase 47)，但跟踪基线漂移。
    """

    _history: list[ConsistencyMetrics] = field(default_factory=list)
    _baseline: ConsistencyMetrics | None = None

    def establish_baseline(self, metrics: ConsistencyMetrics) -> None:
        """建立一致性基线。"""
        self._baseline = metrics
        self._history.append(metrics)

    def measure(
        self,
        identity_stability: float = 1.0,
        memory_health: float = 1.0,
        wisdom_rate: float = 0.0,
        decision_stability: float = 1.0,
        goal_alignment: float = 1.0,
        personalization_depth: float = 0.0,
    ) -> ConsistencyMetrics:
        """度量当前一致性。"""
        metrics = ConsistencyMetrics(
            identity_stability=identity_stability,
            memory_health=memory_health,
            wisdom_accumulation_rate=wisdom_rate,
            decision_pattern_stability=decision_stability,
            goal_alignment=goal_alignment,
            personalization_depth=personalization_depth,
        )
        self._history.append(metrics)
        # 保留最近 200 次
        if len(self._history) > 200:
            self._history = self._history[-100:]
        return metrics

    def drift_from_baseline(self) -> float | None:
        """计算当前与基线的漂移量。"""
        if not self._baseline or not self._history:
            return None
        current = self._history[-1]
        baseline = self._baseline
        return abs(current.overall_maturity - baseline.overall_maturity)

    def maturity_level(self) -> MaturityLevel:
        """根据一致性评估当前成熟度。"""
        if not self._history:
            return MaturityLevel.INITIALIZING

        current = self._history[-1]

        if current.personalization_depth < 0.2:
            return MaturityLevel.LEARNING
        if current.personalization_depth < 0.5:
            return MaturityLevel.ADAPTING
        if current.overall_maturity < 0.7:
            return MaturityLevel.MATURE
        return MaturityLevel.DEEPENING

    @property
    def latest(self) -> ConsistencyMetrics | None:
        return self._history[-1] if self._history else None

    @property
    def measurement_count(self) -> int:
        return len(self._history)


__all__ = ["ConsistencyMonitor"]
