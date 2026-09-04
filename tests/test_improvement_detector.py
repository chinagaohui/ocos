"""OCOS improvement_detector 改进检测器测试。

CE47-01: Evolution ≠ Autonomy（只检测信号，不产生提案）
"""

import pytest

from ocos.evolution.improvement_detector import ImprovementDetector, DetectedSignal
from ocos.evolution.evolution_types import EvolutionTrigger


class TestDetectedSignal:
    def test_defaults(self):
        sig = DetectedSignal()
        assert sig.trigger == EvolutionTrigger.HEALTH_ALERT
        assert sig.source_tick == 0
        assert sig.metric_value == 0.0
        assert sig.severity == 0.0

    def test_custom(self):
        sig = DetectedSignal(
            trigger=EvolutionTrigger.PERFORMANCE_DEGRADATION,
            source_tick=42,
            source_module="runtime",
            metric_name="latency",
            metric_value=0.3,
            threshold=0.6,
            description="high latency",
            severity=0.7,
        )
        assert sig.trigger == EvolutionTrigger.PERFORMANCE_DEGRADATION
        assert sig.severity == 0.7


class TestImprovementDetector:
    @pytest.fixture
    def detector(self):
        return ImprovementDetector()

    # ── 健康检测 ────────────────────────────────────────────────

    def test_health_below_threshold_generates_signal(self, detector):
        signal = detector.detect_from_health("memory", 0.3, tick_id=100)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.HEALTH_ALERT
        assert signal.metric_value == 0.3
        assert signal.severity == 0.7  # 1.0 - 0.3
        assert "memory" in signal.description

    def test_health_above_threshold_no_signal(self, detector):
        signal = detector.detect_from_health("runtime", 0.8, tick_id=100)
        assert signal is None

    def test_health_default_threshold_0_5(self, detector):
        signal = detector.detect_from_health("x", 0.49, tick_id=0)
        assert signal is not None
        signal2 = detector.detect_from_health("x", 0.5, tick_id=0)
        assert signal2 is None  # 等于阈值不触发

    # ── 性能检测 ────────────────────────────────────────────────

    def test_performance_below_threshold(self, detector):
        signal = detector.detect_from_performance("attention", 0.4, tick_id=50)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.PERFORMANCE_DEGRADATION
        assert signal.metric_value == 0.4

    def test_performance_above_threshold(self, detector):
        signal = detector.detect_from_performance("attention", 0.7, tick_id=50)
        assert signal is None

    # ── 模式检测 ────────────────────────────────────────────────

    def test_pattern_below_batch_no_signal(self, detector):
        signal = detector.detect_pattern("repeated_error", 3, tick_id=10)
        assert signal is None

    def test_pattern_at_batch_generates_signal(self, detector):
        signal = detector.detect_pattern("repeated_error", 5, tick_id=10)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.EXPERIENCE_PATTERN
        assert signal.metric_value == 5.0
        # severity = min(1.0, 5/20) = 0.25
        assert abs(signal.severity - 0.25) < 0.01

    def test_pattern_high_severity_capped(self, detector):
        signal = detector.detect_pattern("rare_pattern", 25, tick_id=10)
        assert signal is not None
        assert signal.severity == 1.0  # capped at 1.0

    # ── 能力缺口检测 ────────────────────────────────────────────

    def test_capability_gap_always_generates(self, detector):
        signal = detector.detect_capability_gap("no image support", tick_id=1)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.CAPABILITY_GAP
        assert signal.severity == 0.7
        assert "image" in signal.description

    # ── 决策漂移检测 ────────────────────────────────────────────

    def test_drift_below_threshold(self, detector):
        signal = detector.detect_decision_drift(0.3, tick_id=200)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.DECISION_CONSISTENCY_DRIFT
        assert signal.severity == 0.7  # 1.0 - 0.3

    def test_drift_above_threshold(self, detector):
        signal = detector.detect_decision_drift(0.5, tick_id=200)
        assert signal is None

    # ── 状态查询 ────────────────────────────────────────────────

    def test_pending_signals_accumulates(self, detector):
        detector.detect_from_health("mem", 0.3, tick_id=1)
        detector.detect_from_performance("att", 0.4, tick_id=2)
        signals = detector.pending_signals
        assert len(signals) == 2

    def test_has_signals_true(self, detector):
        detector.detect_from_health("x", 0.1, tick_id=0)
        assert detector.has_signals is True

    def test_has_signals_false_when_empty(self, detector):
        assert detector.has_signals is False

    def test_clear_returns_count(self, detector):
        detector.detect_from_health("a", 0.1, tick_id=1)
        detector.detect_from_health("b", 0.2, tick_id=2)
        count = detector.clear()
        assert count == 2
        assert detector.has_signals is False

    def test_pending_signals_truncated_to_50(self, detector):
        for i in range(60):
            detector.detect_from_health(f"m{i}", 0.1, tick_id=i)
        signals = detector.pending_signals
        assert len(signals) == 50
        # 只保留最近 50 条
        assert signals[0].source_tick == 10  # 60-50=10

    # ── 阈值可配置 ──────────────────────────────────────────────

    def test_custom_thresholds(self):
        det = ImprovementDetector(
            health_threshold=0.3,
            performance_threshold=0.4,
            experience_batch=3,
            drift_threshold=0.2,
        )
        assert det.health_threshold == 0.3
        assert det.performance_threshold == 0.4
        assert det.experience_batch == 3
        assert det.drift_threshold == 0.2
