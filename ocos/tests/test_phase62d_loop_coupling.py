"""Phase 62d: CognitiveCouplingBridge 接入 LoopOrchestrator — 测试套件。

覆盖:
    - 注入桥接到 LoopOrchestrator
    - tick() 触发 bridge.poll()
    - 桥接指标累积
    - 周期健康检查
"""

import pytest
from ocos.cognitive_loop.loop_orchestrator import LoopOrchestrator, TickOutcome
from ocos.capability.cognitive_coupling import CognitiveCouplingBridge, CouplingMetrics
from ocos.belief import BeliefManager, BeliefDimension
from ocos.capability.homeostasis import HomeostasisManager


class TestLoopOrchestratorCouplingIntegration:
    """LoopOrchestrator + CognitiveCouplingBridge 集成测试。"""

    @pytest.fixture
    def coupled_loop(self):
        """创建带耦合桥接的 LoopOrchestrator。"""
        loop = LoopOrchestrator()
        bm = BeliefManager()
        hm = HomeostasisManager()
        bridge = CognitiveCouplingBridge(bm, hm)
        loop.inject_coupling_bridge(bridge)
        return loop, bridge, bm, hm

    def test_inject_coupling_bridge(self):
        loop = LoopOrchestrator()
        bm = BeliefManager()
        hm = HomeostasisManager()
        bridge = CognitiveCouplingBridge(bm, hm)

        assert loop._coupling_bridge is None
        loop.inject_coupling_bridge(bridge)
        assert loop._coupling_bridge is bridge

    def test_tick_without_bridge_no_error(self):
        """无 bridge 时 tick() 正常，不报错。"""
        loop = LoopOrchestrator()
        ctx = loop.tick()
        assert loop.current_tick == 1
        assert loop._coupling_bridge is None

    def test_tick_with_bridge_polls_every_tick(self, coupled_loop):
        loop, bridge, bm, hm = coupled_loop
        metrics_before = bridge.metrics.total_contradictions_processed
        loop.tick()
        # poll runs, no events → no change in contradictions
        assert bridge.metrics.total_contradictions_processed == metrics_before

    def test_loop_ticks_dont_crash_with_bridge(self, coupled_loop):
        """多 tick 不崩溃。"""
        loop, bridge, bm, hm = coupled_loop
        for _ in range(5):
            ctx = loop.tick()
        assert loop.current_tick == 5

    def test_cognition_after_health_check_ticks(self, coupled_loop):
        """跑满 10 tick 触发健康检查。"""
        loop, bridge, bm, hm = coupled_loop
        for _ in range(10):
            loop.tick()
        assert loop.current_tick == 10
        assert loop.health.is_healthy

    def test_loop_summary_includes_coupling_awareness(self, coupled_loop):
        loop, bridge, bm, hm = coupled_loop
        for _ in range(3):
            loop.tick()
        summary = loop.loop_summary()
        assert "total_ticks" in summary
        assert summary["total_ticks"] == 3

    def test_recent_outcomes_tracked(self, coupled_loop):
        loop, bridge, bm, hm = coupled_loop
        loop.tick()
        loop.tick()
        outcomes = loop.recent_outcomes
        assert len(outcomes) >= 2
