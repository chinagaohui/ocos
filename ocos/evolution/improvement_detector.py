"""Phase 47: ImprovementDetector — 改进检测器。

从系统信号中检测进化机会。

信号来源:
    - Health Monitor → 健康异常
    - Experience Patterns → 重复经验形成模式
    - Performance Metrics → 退化信号
    - Decision Analysis → 决策漂移
    - World Model → 冲突

边界 CE47-01: Evolution ≠ Autonomy
    进化由系统信号触发，非自我决定。
    检测器只发现信号，不产生提案 (Proposer 负责)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionTrigger,
)


@dataclass
class DetectedSignal:
    """一个检测到的改进信号。"""
    trigger: EvolutionTrigger = EvolutionTrigger.HEALTH_ALERT
    source_tick: int = 0
    source_module: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    description: str = ""
    severity: float = 0.0  # [0, 1]


@dataclass
class ImprovementDetector:
    """改进检测器。

    从多个维度检测需要进化的信号。
    """

    _detected: list[DetectedSignal] = field(default_factory=list)

    # 阈值配置
    health_threshold: float = 0.5       # 健康度 < 此值 → 信号
    performance_threshold: float = 0.6 # 性能 < 此值 → 信号
    experience_batch: int = 5           # 重复经验次数 → 模式信号
    drift_threshold: float = 0.4        # 一致性 < 此值 → 漂移信号

    def detect_from_health(
        self, module_name: str, health_score: float, tick_id: int,
    ) -> DetectedSignal | None:
        """从健康检查中检测改进信号。"""
        if health_score < self.health_threshold:
            signal = DetectedSignal(
                trigger=EvolutionTrigger.HEALTH_ALERT,
                source_tick=tick_id,
                source_module=module_name,
                metric_name="health_score",
                metric_value=health_score,
                threshold=self.health_threshold,
                description=f"{module_name} health degraded: {health_score:.2f}",
                severity=1.0 - health_score,
            )
            self._detected.append(signal)
            return signal
        return None

    def detect_from_performance(
        self, capability: str, perf_score: float, tick_id: int,
    ) -> DetectedSignal | None:
        """从性能退化中检测。"""
        if perf_score < self.performance_threshold:
            signal = DetectedSignal(
                trigger=EvolutionTrigger.PERFORMANCE_DEGRADATION,
                source_tick=tick_id,
                source_module=capability,
                metric_name="performance",
                metric_value=perf_score,
                threshold=self.performance_threshold,
                description=f"{capability} performance degraded: {perf_score:.2f}",
                severity=1.0 - perf_score,
            )
            self._detected.append(signal)
            return signal
        return None

    def detect_pattern(
        self, experience_type: str, occurrences: int, tick_id: int,
    ) -> DetectedSignal | None:
        """检测重复经验模式。"""
        if occurrences >= self.experience_batch:
            signal = DetectedSignal(
                trigger=EvolutionTrigger.EXPERIENCE_PATTERN,
                source_tick=tick_id,
                source_module="learning",
                metric_name="experience_pattern",
                metric_value=float(occurrences),
                threshold=float(self.experience_batch),
                description=f"Pattern detected: {experience_type} ({occurrences} occurrences)",
                severity=min(1.0, occurrences / 20.0),
            )
            self._detected.append(signal)
            return signal
        return None

    def detect_capability_gap(
        self, gap_description: str, tick_id: int,
    ) -> DetectedSignal:
        """检测能力缺失。"""
        signal = DetectedSignal(
            trigger=EvolutionTrigger.CAPABILITY_GAP,
            source_tick=tick_id,
            source_module="capability",
            metric_name="capability_gap",
            description=gap_description,
            severity=0.7,
        )
        self._detected.append(signal)
        return signal

    def detect_decision_drift(
        self, consistency: float, tick_id: int,
    ) -> DetectedSignal | None:
        """检测决策漂移。"""
        if consistency < self.drift_threshold:
            signal = DetectedSignal(
                trigger=EvolutionTrigger.DECISION_CONSISTENCY_DRIFT,
                source_tick=tick_id,
                source_module="decision",
                metric_name="consistency",
                metric_value=consistency,
                threshold=self.drift_threshold,
                description=f"Decision drift: consistency={consistency:.2f}",
                severity=1.0 - consistency,
            )
            self._detected.append(signal)
            return signal
        return None

    @property
    def pending_signals(self) -> list[DetectedSignal]:
        return self._detected[-50:]

    @property
    def has_signals(self) -> bool:
        return len(self._detected) > 0

    def clear(self) -> int:
        count = len(self._detected)
        self._detected = []
        return count


__all__ = ["DetectedSignal", "ImprovementDetector"]
