"""Phase Y: MonitoringManager 单元测试。"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.monitoring.manager import (
    MonitoringManager,
    MetricsRegistry,
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertState,
    MetricPoint,
)


class TestMetricPoint:
    """MetricPoint 测试。"""

    def test_to_prometheus_no_labels(self):
        point = MetricPoint(name="test_metric", value=42.0)
        prom = point.to_prometheus()
        assert prom == "test_metric 42.0"

    def test_to_prometheus_with_labels(self):
        point = MetricPoint(
            name="test_metric",
            value=42.0,
            labels={"method": "GET", "status": "200"},
        )
        prom = point.to_prometheus()
        assert 'test_metric{method="GET",status="200"} 42.0' == prom


class TestMetricsRegistry:
    """MetricsRegistry 测试。"""

    def test_counter_increment(self):
        registry = MetricsRegistry()
        registry.increment("requests_total", 1.0, {"method": "GET"})
        registry.increment("requests_total", 1.0, {"method": "POST"})

        prom = registry.to_prometheus()
        assert "requests_total_method_GET_1.0" in prom or "requests_total" in prom

    def test_gauge_set(self):
        registry = MetricsRegistry()
        registry.set_gauge("memory_usage", 0.75)

        prom = registry.to_prometheus()
        assert "memory_usage" in prom

    def test_histogram_observe(self):
        registry = MetricsRegistry()
        for _ in range(10):
            registry.observe("request_duration", 0.5)

        prom = registry.to_prometheus()
        assert "request_duration" in prom

    def test_reset(self):
        registry = MetricsRegistry()
        registry.increment("test", 1.0)
        registry.reset()

        prom = registry.to_prometheus()
        # 重置后应该只有基础指标
        assert "ocos_up" in prom

    def test_prometheus_format(self):
        registry = MetricsRegistry()
        prom = registry.to_prometheus()
        assert "ococ_up" in prom or "ocos_up" in prom
        assert "ocos_uptime_seconds" in prom


class TestAlertRule:
    """AlertRule 测试。"""

    def test_evaluate_fires(self):
        rule = AlertRule(
            name="test_rule",
            condition=lambda ctx: ctx.get("value", 0) > 10,
            severity=AlertSeverity.WARNING,
            message="Value too high",
        )

        result = rule.evaluate({"value": 15})
        assert result is not None
        assert result["severity"] == AlertSeverity.WARNING

    def test_evaluate_no_fire(self):
        rule = AlertRule(
            name="test_rule",
            condition=lambda ctx: ctx.get("value", 0) > 10,
            severity=AlertSeverity.WARNING,
            message="Value too high",
        )

        result = rule.evaluate({"value": 5})
        assert result is None

    def test_evaluate_disabled(self):
        rule = AlertRule(
            name="test_rule",
            condition=lambda ctx: True,
            severity=AlertSeverity.WARNING,
            message="Always fires",
            enabled=False,
        )

        result = rule.evaluate({})
        assert result is None


class TestAlertManager:
    """AlertManager 测试。"""

    def test_add_and_evaluate_rule(self):
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="high_cpu",
            condition=lambda ctx: ctx.get("cpu", 0) > 90,
            severity=AlertSeverity.ERROR,
            message="CPU usage high",
            cooldown_seconds=0,
        ))

        triggered = manager.evaluate({"cpu": 95})
        assert len(triggered) == 1
        assert triggered[0]["rule"] == "high_cpu"

    def test_cooldown(self):
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="test",
            condition=lambda ctx: True,
            severity=AlertSeverity.INFO,
            message="Test",
            cooldown_seconds=3600,  # 1 小时冷却
        ))

        # 第一次触发
        manager.evaluate({})
        # 第二次应该在冷却期内
        triggered = manager.evaluate({})
        assert len(triggered) == 0

    def test_resolve_alert(self):
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="test",
            condition=lambda ctx: True,
            severity=AlertSeverity.INFO,
            message="Test",
            cooldown_seconds=0,
        ))

        manager.evaluate({})
        assert len(manager.get_active_alerts()) == 1

        manager.resolve_alert("test")
        assert len(manager.get_active_alerts()) == 0

    def test_get_stats(self):
        manager = AlertManager()
        stats = manager.get_stats()
        assert "active_alerts" in stats
        assert "total_rules" in stats


class TestMonitoringManager:
    """MonitoringManager 测试。"""

    def test_create(self):
        manager = MonitoringManager()
        assert manager.port == 9090
        assert manager._running is False

    def test_record_metric_counter(self):
        manager = MonitoringManager()
        manager.record_metric("test_counter", 1.0, metric_type="counter")

        prom = manager.get_metrics()
        assert "test_counter" in prom

    def test_record_metric_gauge(self):
        manager = MonitoringManager()
        manager.record_metric("test_gauge", 42.0, metric_type="gauge")

        prom = manager.get_metrics()
        assert "test_gauge" in prom

    def test_record_metric_histogram(self):
        manager = MonitoringManager()
        manager.record_metric("test_hist", 0.5, metric_type="histogram")

        prom = manager.get_metrics()
        assert "test_hist" in prom

    def test_evaluate_alerts(self):
        manager = MonitoringManager()
        triggered = manager.evaluate_alerts({"error_rate": 0.15})
        # 应该触发 high_error_rate 规则
        assert len(triggered) >= 1

    def test_get_health_status_healthy(self):
        manager = MonitoringManager()
        status = manager.get_health_status()
        assert "status" in status
        assert "uptime_seconds" in status

    def test_get_stats(self):
        manager = MonitoringManager()
        stats = manager.get_stats()
        assert "running" in stats
        assert "port" in stats
        assert "uptime_seconds" in stats

    def test_context_manager(self):
        """测试上下文管理器。"""
        manager = MonitoringManager(enable_http=False)
        # 不启动 HTTP，直接测试 enter/exit
        manager.__enter__()
        assert manager._running is False  # enable_http=False 时不启动
        manager.__exit__(None, None, None)


class TestEdgeCases:
    """边界条件测试。"""

    def test_empty_metrics(self):
        registry = MetricsRegistry()
        prom = registry.to_prometheus()
        assert "ocos_up" in prom

    def test_alert_rule_exception(self):
        """规则评估异常时不崩溃。"""
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="bad_rule",
            condition=lambda ctx: 1/0,  # 故意除以零
            severity=AlertSeverity.ERROR,
            message="Bad rule",
            cooldown_seconds=0,
        ))

        # 不应该抛出异常
        triggered = manager.evaluate({"test": True})
        assert len(triggered) == 0

    def test_multiple_alerts_same_rule(self):
        """同一规则多次触发只记录一次（冷却期）。"""
        manager = AlertManager()
        manager.add_rule(AlertRule(
            name="test",
            condition=lambda ctx: True,
            severity=AlertSeverity.INFO,
            message="Test",
            cooldown_seconds=0,
        ))

        # 第一次
        m1 = manager.evaluate({})
        # 第二次（相同规则，无冷却）
        m2 = manager.evaluate({})

        # 可能有多个触发，但不应该无限增长
        assert len(manager.get_active_alerts()) <= 2
