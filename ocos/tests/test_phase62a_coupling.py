"""Phase 62a: Cognitive Coupling Bridge — 测试套件。

覆盖:
    - CognitiveCouplingBridge 创建与配置
    - poll() 无事件 / 有事件
    - 矛盾事件 → 认知熵上升
    - 确认偏差 → 警报 + 认知熵
    - 信念强度变化 → 负载更新
    - 休眠信念 → 清理建议
    - apply_to_homeostasis 注入 context monitor
    - diagnostics
    - 重置
"""

import pytest
import time
from ocos.capability.cognitive_coupling import (
    CognitiveCouplingBridge,
    CouplingConfig,
    CouplingMetrics,
)


class TestCouplingConfig:
    """CouplingConfig 测试。"""

    def test_defaults(self):
        cfg = CouplingConfig()
        assert cfg.contradiction_alert_threshold == 3
        assert cfg.confirmation_bias_dimension_threshold == 5
        assert cfg.strength_shift_threshold == 0.5
        assert cfg.dormant_count_threshold == 50
        assert cfg.max_cognitive_entropy == 10.0

    def test_custom_values(self):
        cfg = CouplingConfig(
            contradiction_alert_threshold=5,
            max_cognitive_entropy=20.0,
        )
        assert cfg.contradiction_alert_threshold == 5
        assert cfg.max_cognitive_entropy == 20.0


class TestCouplingMetrics:
    """CouplingMetrics 测试。"""

    def test_defaults(self):
        m = CouplingMetrics()
        assert m.total_contradictions_processed == 0
        assert m.current_cognitive_entropy == 0.0

    def test_accumulate(self):
        m = CouplingMetrics()
        m.total_contradictions_processed += 3
        m.current_cognitive_entropy = 1.5
        assert m.total_contradictions_processed == 3
        assert m.current_cognitive_entropy == 1.5


class FakeBeliefManager:
    """模拟 BeliefManager — 提供 drain_events() 接口。"""

    def __init__(self):
        self._event_log = []

    def add_event(self, event: str, **data):
        self._event_log.append({"event": event, "timestamp": time.time(), **data})

    def drain_events(self) -> list[dict]:
        events = list(self._event_log)
        self._event_log.clear()
        return events


class FakeHomeostasisManager:
    """模拟 HomeostasisManager — 提供 context monitor。"""

    def __init__(self):
        self._metrics = {}

    @property
    def context(self):
        return self

    @property
    def _context_metrics(self):
        return self._metrics


class TestCognitiveCouplingBridge:
    """CognitiveCouplingBridge 核心测试。"""

    def test_create(self):
        bridge = CognitiveCouplingBridge()
        assert bridge.metrics.current_cognitive_entropy == 0.0
        assert bridge.config.contradiction_alert_threshold == 3

    def test_poll_no_belief_manager(self):
        bridge = CognitiveCouplingBridge()
        result = bridge.poll()
        assert result["status"] == "no_belief_manager"
        assert result["events_processed"] == 0

    def test_poll_with_empty_events(self):
        belief = FakeBeliefManager()
        bridge = CognitiveCouplingBridge(belief_manager=belief)
        result = bridge.poll()
        assert result["status"] == "no_events"

    def test_poll_contradiction_increases_entropy(self):
        belief = FakeBeliefManager()
        belief.add_event("contradiction_detected", belief_id="b1")
        bridge = CognitiveCouplingBridge(belief_manager=belief)

        result = bridge.poll()
        assert result["contradictions"] == 1
        assert bridge.metrics.current_cognitive_entropy > 0
        assert bridge.metrics.total_contradictions_processed == 1

    def test_poll_contradiction_burst_triggers_alert(self):
        belief = FakeBeliefManager()
        cfg = CouplingConfig(contradiction_alert_threshold=2)
        bridge = CognitiveCouplingBridge(belief_manager=belief, config=cfg)

        # 2 contradictions in one poll → should trigger burst alert
        belief.add_event("contradiction_detected", belief_id="b1")
        belief.add_event("contradiction_detected", belief_id="b2")
        result = bridge.poll()

        assert result["contradictions"] == 2
        assert len(bridge._pending_contradictions) == 0  # cleared after burst

    def test_poll_confirmation_bias(self):
        belief = FakeBeliefManager()
        belief.add_event("confirmation_bias_alert", dimension="identity")
        bridge = CognitiveCouplingBridge(belief_manager=belief)

        result = bridge.poll()
        assert result["bias_alerts"] == 1
        assert bridge.metrics.total_confirmation_bias_alerts == 1
        assert bridge.metrics.current_cognitive_entropy > 0

    def test_poll_strength_shift(self):
        belief = FakeBeliefManager()
        belief.add_event("belief_updated", probability_delta=0.8)
        bridge = CognitiveCouplingBridge(belief_manager=belief)

        result = bridge.poll()
        assert result["strength_shifts"] == 1
        assert bridge.metrics.total_strength_shifts == 1

    def test_poll_dormancy(self):
        belief = FakeBeliefManager()
        belief.add_event("belief_dormant", belief_id="old-belief")
        bridge = CognitiveCouplingBridge(belief_manager=belief)

        result = bridge.poll()
        assert result["dormancy_alerts"] == 1
        assert bridge.metrics.total_dormancy_alerts == 1

    def test_poll_mixed_events(self):
        belief = FakeBeliefManager()
        belief.add_event("contradiction_detected", belief_id="b1")
        belief.add_event("belief_updated", probability_delta=0.6)
        belief.add_event("confirmation_bias_alert", dimension="identity")

        bridge = CognitiveCouplingBridge(belief_manager=belief)
        result = bridge.poll()

        assert result["contradictions"] == 1
        assert result["strength_shifts"] == 1
        assert result["bias_alerts"] == 1
        assert result["events_processed"] == 3

    def test_apply_to_homeostasis(self):
        belief = FakeBeliefManager()
        belief.add_event("contradiction_detected", belief_id="b1")
        homeostasis = FakeHomeostasisManager()

        bridge = CognitiveCouplingBridge(
            belief_manager=belief,
            homeostasis_manager=homeostasis,
        )
        bridge.poll()

        # Check that cognitive_entropy was injected into context metrics
        assert "cognitive_entropy" in homeostasis._metrics
        assert homeostasis._metrics["cognitive_entropy"] > 0

    def test_diagnostics(self):
        belief = FakeBeliefManager()
        belief.add_event("contradiction_detected")
        bridge = CognitiveCouplingBridge(belief_manager=belief)
        bridge.poll()

        diag = bridge.diagnostics()
        assert "entropy" in diag
        assert "pending_contradictions" in diag
        assert "metrics" in diag
        assert diag["metrics"]["contradictions"] == 1

    def test_reset(self):
        belief = FakeBeliefManager()
        belief.add_event("contradiction_detected")
        belief.add_event("contradiction_detected")
        bridge = CognitiveCouplingBridge(belief_manager=belief)
        bridge.poll()

        assert bridge.metrics.current_cognitive_entropy > 0

        bridge.reset()
        assert bridge.metrics.current_cognitive_entropy == 0.0
        assert bridge.metrics.total_contradictions_processed == 0
        assert len(bridge._pending_contradictions) == 0

    def test_entropy_capped_at_max(self):
        belief = FakeBeliefManager()
        cfg = CouplingConfig(
            max_cognitive_entropy=1.0,
            contradiction_entropy_per_event=2.0,  # each event adds more than max
        )
        bridge = CognitiveCouplingBridge(belief_manager=belief, config=cfg)
        belief.add_event("contradiction_detected")
        bridge.poll()

        assert bridge.metrics.current_cognitive_entropy <= 1.0

    def test_entropy_never_negative(self):
        belief = FakeBeliefManager()
        bridge = CognitiveCouplingBridge(belief_manager=belief)
        bridge.metrics.current_cognitive_entropy = -0.5  # force negative

        # Use a strength shift large enough to trigger threshold
        belief.add_event("belief_updated", probability_delta=0.8)
        bridge.poll()

        assert bridge.metrics.current_cognitive_entropy >= 0.0

    def test_get_cognitive_entropy(self):
        belief = FakeBeliefManager()
        bridge = CognitiveCouplingBridge(belief_manager=belief)
        belief.add_event("contradiction_detected")
        bridge.poll()

        entropy = bridge.get_cognitive_entropy()
        assert entropy > 0
        assert entropy == bridge.metrics.current_cognitive_entropy
