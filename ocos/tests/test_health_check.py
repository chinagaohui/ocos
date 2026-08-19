"""HealthCheck 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ocos.agent.health_check import (
    HEALTHY,
    DEGRADED,
    UNHEALTHY,
    UNKNOWN,
    ComponentCheck,
    HealthCheck,
)
from ocos.events.event_bus import EventBus


class TestComponentCheck:
    """单个组件检查。"""

    def test_healthy(self):
        def check():
            return {"status": HEALTHY, "detail": "all good"}

        cc = ComponentCheck("writer", check, metadata={"type": "narrative"})
        result = cc.run()
        assert result["component"] == "writer"
        assert result["status"] == HEALTHY
        assert result["detail"] == "all good"
        assert result["type"] == "narrative"

    def test_unhealthy_exception(self):
        def check():
            raise RuntimeError("broken")

        cc = ComponentCheck("broken_engine", check)
        result = cc.run()
        assert result["status"] == UNHEALTHY
        assert "broken" in result.get("error", "")

    def test_unknown_no_status(self):
        def check():
            return {"version": "1.0"}

        cc = ComponentCheck("new_engine", check)
        result = cc.run()
        assert result["status"] == UNKNOWN  # no status key


class TestHealthCheck:
    """聚合健康检查。"""

    def test_empty_report(self):
        hc = HealthCheck()
        report = hc.check_all()
        assert report["overall"] == UNKNOWN
        assert report["total"] == 0

    def test_all_healthy(self):
        hc = HealthCheck()
        hc.register("a", lambda: {"status": HEALTHY})
        hc.register("b", lambda: {"status": HEALTHY})
        report = hc.check_all()
        assert report["overall"] == HEALTHY
        assert report["total"] == 2
        assert report["healthy"] == 2

    def test_one_degraded(self):
        hc = HealthCheck()
        hc.register("a", lambda: {"status": HEALTHY})
        hc.register("b", lambda: {"status": DEGRADED})
        hc.register("c", lambda: {"status": HEALTHY})
        report = hc.check_all()
        assert report["overall"] == DEGRADED
        assert report["healthy"] == 2
        assert report["unhealthy"] == 0

    def test_any_unhealthy_overrides(self):
        hc = HealthCheck()
        hc.register("a", lambda: {"status": HEALTHY})
        hc.register("b", lambda: {"status": UNHEALTHY})
        hc.register("c", lambda: {"status": DEGRADED})
        report = hc.check_all()
        assert report["overall"] == UNHEALTHY
        assert report["unhealthy"] == 1

    def test_check_one(self):
        hc = HealthCheck()
        hc.register("a", lambda: {"status": HEALTHY})
        result = hc.check_one("a")
        assert result is not None
        assert result["status"] == HEALTHY

    def test_check_one_missing(self):
        hc = HealthCheck()
        assert hc.check_one("nonexistent") is None

    def test_unregister(self):
        hc = HealthCheck()
        hc.register("a", lambda: {"status": HEALTHY})
        hc.unregister("a")
        report = hc.check_all()
        assert report["total"] == 0

    def test_factory_event_bus(self, monkeypatch):
        """EventBus 健康检查工厂。"""
        bus = MagicMock(spec=EventBus)
        cc = HealthCheck.for_event_bus(bus)
        result = cc.run()
        assert result["component"] == "event_bus"
        assert result["status"] == HEALTHY

    def test_factory_engine_bridge(self):
        bridge = MagicMock()
        bridge.list_engines.return_value = ["planner", "writer"]
        cc = HealthCheck.for_engine_bridge(bridge)
        result = cc.run()
        assert result["status"] == HEALTHY
        assert "planner" in result["registered_engines"]

    def test_factory_engine_bridge_empty(self):
        bridge = MagicMock()
        bridge.list_engines.return_value = []
        cc = HealthCheck.for_engine_bridge(bridge)
        result = cc.run()
        assert result["status"] == DEGRADED

    def test_factory_writer_engine(self):
        engine = MagicMock()
        engine.trace_count = 5
        engine.last_trace.success = True
        cc = HealthCheck.for_writer_engine(engine)
        result = cc.run()
        assert result["status"] == HEALTHY
        assert result["traces"] == 5
        assert result["last_success"] is True

    def test_integrated_report(self):
        """多个注册组件生成综合报告。"""
        hc = HealthCheck()
        hc.register("engine_bridge", lambda: {
            "status": HEALTHY,
            "engines": ["planner", "writer"],
        })
        hc.register("writer_engine", lambda: {
            "status": HEALTHY,
            "traces": 10,
        })
        hc.register("event_bus", lambda: {"status": HEALTHY})
        report = hc.check_all()
        assert report["overall"] == HEALTHY
        assert len(report["components"]) == 3
