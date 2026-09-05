"""Deep tests for ocos.monitoring.manager."""
import pytest


class TestMonitoringManager:
    def test_import(self):
        from ocos.monitoring.manager import MonitoringManager
        assert MonitoringManager is not None

    def test_create(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        assert mgr is not None

    def test_get_metrics(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        metrics = mgr.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_health_status(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        status = mgr.get_health_status()
        assert status is not None

    def test_get_stats(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        stats = mgr.get_stats()
        assert isinstance(stats, dict)

    def test_record_metric(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        mgr.record_metric("test_metric", 1.0)
        assert mgr is not None

    def test_evaluate_alerts(self):
        from ocos.monitoring.manager import MonitoringManager
        mgr = MonitoringManager()
        alerts = mgr.evaluate_alerts()
        assert isinstance(alerts, list)
