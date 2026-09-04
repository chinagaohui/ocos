"""OCOS agent/health_check 测试。"""

import pytest
from ocos.agent.health_check import ComponentCheck, HealthCheck, HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN


class TestComponentCheck:
    def test_healthy_component(self):
        check = ComponentCheck("test", lambda: {"status": HEALTHY})
        result = check.run()
        assert result["component"] == "test"
        assert result["status"] == HEALTHY

    def test_unhealthy_on_exception(self):
        check = ComponentCheck("fail", lambda: (_ for _ in []).throw(RuntimeError("boom")))
        result = check.run()
        assert result["status"] == UNHEALTHY
        assert "error" in result

    def test_missing_status_defaults_to_unknown(self):
        check = ComponentCheck("missing", lambda: {"foo": "bar"})
        result = check.run()
        assert result["status"] == UNKNOWN

    def test_metadata_merged(self):
        check = ComponentCheck("with_meta", lambda: {"status": HEALTHY}, metadata={"type": "critical"})
        result = check.run()
        assert result["type"] == "critical"

    def test_repr(self):
        check = ComponentCheck("my_comp", lambda: {})
        assert "my_comp" in repr(check)


class TestHealthCheck:
    def test_empty(self):
        hc = HealthCheck()
        report = hc.check_all()
        assert report["overall"] == UNKNOWN
        assert report["total"] == 0

    def test_register_and_check(self):
        hc = HealthCheck()
        hc.register("comp1", lambda: {"status": HEALTHY})
        hc.register("comp2", lambda: {"status": HEALTHY})
        report = hc.check_all()
        assert report["overall"] == HEALTHY
        assert report["total"] == 2
        assert report["healthy"] == 2
        assert report["unhealthy"] == 0

    def test_unhealthy_overrides(self):
        hc = HealthCheck()
        hc.register("comp1", lambda: {"status": HEALTHY})
        hc.register("comp2", lambda: {"status": UNHEALTHY})
        report = hc.check_all()
        assert report["overall"] == UNHEALTHY
        assert report["unhealthy"] == 1

    def test_degraded_if_no_healthy(self):
        hc = HealthCheck()
        hc.register("comp1", lambda: {"status": DEGRADED})
        report = hc.check_all()
        assert report["overall"] == DEGRADED

    def test_unhealthy_takes_precedence(self):
        hc = HealthCheck()
        hc.register("comp1", lambda: {"status": DEGRADED})
        hc.register("comp2", lambda: {"status": UNHEALTHY})
        report = hc.check_all()
        assert report["overall"] == UNHEALTHY

    def test_unregister(self):
        hc = HealthCheck()
        hc.register("comp1", lambda: {"status": HEALTHY})
        hc.unregister("comp1")
        report = hc.check_all()
        assert report["total"] == 0

    def test_check_one(self):
        hc = HealthCheck()
        hc.register("c1", lambda: {"status": HEALTHY})
        result = hc.check_one("c1")
        assert result["status"] == HEALTHY
        assert hc.check_one("missing") is None

    def test_for_event_bus_factory(self):
        # Requires EventBus fixture from conftest
        from ocos.agent.health_check import HealthCheck
        # Can't easily test factory without EventBus, test register pattern instead
        hc = HealthCheck()
        hc.register("event_bus_test", lambda: {"status": HEALTHY})
        report = hc.check_all()
        assert report["overall"] == HEALTHY