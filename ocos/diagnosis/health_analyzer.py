"""Phase 56: HealthAnalyzer — 健康趋势分析。

输入历史 SystemSnapshot 序列，输出健康趋势。

趋势:
    improving / stable / degrading / failing

方法:
    - 滑动窗口分析
    - 健康度变化率
    - 组件间关联分析
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque

from ocos.diagnosis.diagnosis_types import SystemSnapshot


@dataclass
class HealthTrend:
    """健康趋势分析结果。"""
    direction: str = "stable"           # improving / stable / degrading / failing
    slope: float = 0.0                  # 健康度变化率 (正=改善, 负=恶化)
    confidence: float = 0.0
    most_degraded: str = ""             # 退化最严重的组件
    degradation_rate: float = 0.0       # 退化速度


@dataclass
class HealthAnalyzer:
    """健康分析器 — 从快照历史中检测趋势。"""

    window_size: int = 20
    degrade_threshold: float = 0.1      # 健康度下降 > 10% 视为退化
    failing_threshold: float = 0.4      # 健康度 < 40% 视为故障

    _history: deque[SystemSnapshot] = field(default_factory=deque)

    def add_snapshot(self, snapshot: SystemSnapshot) -> None:
        self._history.append(snapshot)
        while len(self._history) > self.window_size:
            self._history.popleft()

    def analyze(self) -> HealthTrend:
        """分析当前趋势。"""
        if len(self._history) < 2:
            return HealthTrend(direction="stable", confidence=0.0)

        snapshots = list(self._history)
        health_values = [s.overall_health for s in snapshots]

        first_half = health_values[:len(health_values) // 2]
        second_half = health_values[len(health_values) // 2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        slope = avg_second - avg_first

        latest = health_values[-1]
        trend = HealthTrend()

        if latest < self.failing_threshold:
            trend.direction = "failing"
            trend.confidence = 0.9
        elif slope < -self.degrade_threshold:
            trend.direction = "degrading"
            trend.confidence = min(0.9, abs(slope) / self.degrade_threshold * 0.5)
        elif slope > self.degrade_threshold:
            trend.direction = "improving"
            trend.confidence = min(0.9, slope / self.degrade_threshold * 0.5)
        else:
            trend.direction = "stable"
            trend.confidence = 0.7

        trend.slope = slope
        trend.degradation_rate = abs(slope) if slope < 0 else 0.0

        # 找最差的组件
        comp_health_sum = {}
        comp_health_count = {}
        for s in snapshots:
            for name, comp in s.components.items():
                comp_health_sum[name] = comp_health_sum.get(name, 0) + (1 if comp.healthy else 0)
                comp_health_count[name] = comp_health_count.get(name, 0) + 1

        if comp_health_sum:
            worst = min(comp_health_sum, key=lambda k: comp_health_sum[k] / comp_health_count[k])
            trend.most_degraded = worst

        return trend

    def clear(self) -> None:
        self._history.clear()


__all__ = ["HealthAnalyzer", "HealthTrend"]
