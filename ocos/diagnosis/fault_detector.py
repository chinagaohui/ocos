"""Phase 56: FaultDetector — 异常检测器。

输入: SystemSnapshot + HealthHistory + Threshold
输出: FaultSignal

检测逻辑:
    1. 组件健康: healthy=False → CAPABILITY_FAILURE / CONNECTION_FAILURE
    2. 健康趋势: degrading/failing → PERFORMANCE_DEGRADATION
    3. 阈值检查: 自定义阈值规则
    4. 历史模式: 重复故障 → RESOURCE_PRESSURE / CONSISTENCY_WARNING

SD56-01: FaultDetector 只输出信号，不做决策。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import time as _time
import uuid

from ocos.diagnosis.diagnosis_types import (
    SystemSnapshot, FaultSignal, FaultCategory, Severity, ComponentHealth,
)
from ocos.diagnosis.health_analyzer import HealthAnalyzer, HealthTrend


@dataclass
class ThresholdRule:
    """阈值规则。"""
    metric: str
    component: str
    operator: str = ">"       # >, <, >=, <=, ==
    value: float = 0.0
    severity: Severity = Severity.MODERATE
    category: FaultCategory = FaultCategory.PERFORMANCE_DEGRADATION


@dataclass
class FaultDetector:
    """异常检测器。

    从 SystemSnapshot + 历史趋势中检测异常。
    """

    analyzer: HealthAnalyzer = field(default_factory=HealthAnalyzer)
    thresholds: list[ThresholdRule] = field(default_factory=list)

    # 重复故障追踪
    _fault_history: deque[tuple[str, float]] = field(default_factory=deque)
    _fault_window: float = 300.0       # 5分钟窗口

    # 事件回调 (产出 FaultSignal 后调用)
    on_fault: object = None            # Callable[[FaultSignal], None]

    def feed(self, snapshot: SystemSnapshot) -> list[FaultSignal]:
        """喂入快照，输出检测到的异常信号列表。"""
        self.analyzer.add_snapshot(snapshot)
        signals: list[FaultSignal] = []

        # 1. 组件健康检查
        for name, comp in snapshot.components.items():
            signal = self._check_component_health(name, comp, snapshot)
            if signal:
                signals.append(signal)

        # 2. 趋势检查
        trend = self.analyzer.analyze()
        signal = self._check_trend(trend, snapshot)
        if signal:
            signals.append(signal)

        # 3. 阈值规则
        for rule in self.thresholds:
            signal = self._check_threshold(rule, snapshot)
            if signal:
                signals.append(signal)

        # 4. 重复故障模式
        for sig in signals:
            self._track_fault(sig)

        # 5. 事件回调
        if self.on_fault:
            for sig in signals:
                try:
                    self.on_fault(sig)  # type: ignore
                except Exception:
                    pass

        return signals

    def _check_component_health(self, name: str, comp: ComponentHealth,
                                 snapshot: SystemSnapshot) -> FaultSignal | None:
        if comp.healthy:
            return None

        # 根据组件名推断类别
        if "event" in name or "store" in name:
            category = FaultCategory.STORAGE_FAILURE
        elif "capability" in name or "adapter" in name:
            category = FaultCategory.CAPABILITY_FAILURE
        elif "scheduler" in name:
            category = FaultCategory.SCHEDULER_STALL
        else:
            category = FaultCategory.CONNECTION_FAILURE

        severity = Severity.HIGH if "memory" in name or "identity" in name else Severity.MODERATE

        return FaultSignal(
            signal_id=f"fault-{uuid.uuid4().hex[:12]}",
            timestamp=_time.time(),
            category=category,
            severity=severity,
            source=name,
            indicator="component_healthy",
            observed_value=0.0,
            threshold=1.0,
            description=f"component {name} unhealthy: {comp.last_error or 'unknown'}",
            snapshot_ref=snapshot.snapshot_id,
            tick=snapshot.tick,
        )

    def _check_trend(self, trend: HealthTrend,
                      snapshot: SystemSnapshot) -> FaultSignal | None:
        if trend.direction == "failing":
            return FaultSignal(
                signal_id=f"fault-{uuid.uuid4().hex[:12]}",
                timestamp=_time.time(),
                category=FaultCategory.PERFORMANCE_DEGRADATION,
                severity=Severity.CRITICAL,
                source="health_analyzer",
                indicator="trend",
                observed_value=trend.slope,
                threshold=-0.1,
                description=f"system health trending to failure: slope={trend.slope:.3f}",
                snapshot_ref=snapshot.snapshot_id,
                tick=snapshot.tick,
            )
        elif trend.direction == "degrading" and abs(trend.slope) > 0.2:
            return FaultSignal(
                signal_id=f"fault-{uuid.uuid4().hex[:12]}",
                timestamp=_time.time(),
                category=FaultCategory.PERFORMANCE_DEGRADATION,
                severity=Severity.HIGH,
                source="health_analyzer",
                indicator="trend",
                observed_value=trend.slope,
                threshold=-0.1,
                description=f"system health degrading: slope={trend.slope:.3f}",
                snapshot_ref=snapshot.snapshot_id,
                tick=snapshot.tick,
            )
        return None

    def _check_threshold(self, rule: ThresholdRule,
                          snapshot: SystemSnapshot) -> FaultSignal | None:
        comp = snapshot.components.get(rule.component)
        if not comp:
            return None
        val = comp.metrics.get(rule.metric)
        if val is None:
            return None

        triggered = False
        if rule.operator == ">":
            triggered = val > rule.value
        elif rule.operator == "<":
            triggered = val < rule.value
        elif rule.operator == ">=":
            triggered = val >= rule.value
        elif rule.operator == "<=":
            triggered = val <= rule.value
        elif rule.operator == "==":
            triggered = val == rule.value

        if triggered:
            return FaultSignal(
                signal_id=f"fault-{uuid.uuid4().hex[:12]}",
                timestamp=_time.time(),
                category=rule.category,
                severity=rule.severity,
                source=rule.component,
                indicator=rule.metric,
                observed_value=val,
                threshold=rule.value,
                description=f"{rule.component}.{rule.metric} {rule.operator} {rule.value}: current={val}",
                snapshot_ref=snapshot.snapshot_id,
                tick=snapshot.tick,
            )
        return None

    def _track_fault(self, signal: FaultSignal) -> None:
        now = _time.time()
        cutoff = now - self._fault_window
        self._fault_history = deque(
            (t, cat) for t, cat in self._fault_history if t > cutoff
        )
        self._fault_history.append((now, signal.category.value))

    def fault_rate(self, category: str | None = None) -> float:
        """最近窗口内的故障频率 (次/秒)。"""
        now = _time.time()
        cutoff = now - self._fault_window
        recent = [t for t, cat in self._fault_history
                   if t > cutoff and (category is None or cat == category)]
        if not recent or self._fault_window <= 0:
            return 0.0
        return len(recent) / self._fault_window

    def clear(self) -> None:
        self._fault_history.clear()
        self.analyzer.clear()


__all__ = ["FaultDetector", "ThresholdRule"]
