"""OCOS alerts/models 测试。"""

import pytest
from ocos.alerts.models import Alert, AlertLevel


class TestAlertLevel:
    def test_values(self):
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


class TestAlert:
    def test_defaults(self):
        alert = Alert()
        assert alert.level == AlertLevel.INFO
        assert alert.source == ""
        assert alert.message == ""
        assert alert.detail is None
        assert alert.finding_id is None
        assert not alert.acknowledged

    def test_custom(self):
        alert = Alert(
            level=AlertLevel.CRITICAL,
            source="scheduler",
            message="System overload",
            detail={"cpu": 0.95},
            finding_id="f1",
            acknowledged=False,
        )
        assert alert.level == AlertLevel.CRITICAL
        assert alert.source == "scheduler"
        assert alert.message == "System overload"
        assert alert.detail == {"cpu": 0.95}
        assert alert.finding_id == "f1"

    def test_create_and_acknowledge(self):
        alert = Alert(message="Test alert")
        assert not alert.acknowledged
        alert.acknowledged = True
        assert alert.acknowledged is True

    def test_unique_id(self):
        a1 = Alert()
        a2 = Alert()
        assert a1.alert_id != a2.alert_id