"""Alert 模型、通道和管理器测试。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from ocos.alerts.models import Alert, AlertLevel
from ocos.alerts.channels import LogChannel, FileChannel
from ocos.alerts.manager import AlertManager


class TestAlertModel:
    def test_create_alert(self):
        """创建告警。"""
        alert = Alert(level=AlertLevel.ERROR, source="test", message="test error")
        assert alert.alert_id is not None
        assert alert.level == AlertLevel.ERROR
        assert alert.source == "test"
        assert not alert.acknowledged

    def test_alert_defaults(self):
        """告警默认值。"""
        alert = Alert(source="test", message="msg")
        assert alert.level == AlertLevel.INFO
        assert alert.detail is None
        assert alert.finding_id is None

    def test_alert_level_values(self):
        """告警级别枚举值。"""
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


class TestFileChannel:
    def test_write_alert(self):
        """FileChannel 写入告警到文件。"""
        with tempfile.NamedTemporaryFile(mode="r+", suffix=".log", delete=False) as f:
            filepath = f.name

        try:
            channel = FileChannel(filepath)
            alert = Alert(level=AlertLevel.WARNING, source="test", message="warning msg")
            channel.send(alert)

            with open(filepath) as f:
                line = f.readline().strip()
            entry = json.loads(line)
            assert entry["level"] == "warning"
            assert entry["message"] == "warning msg"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_create_directory(self):
        """FileChannel 自动创建目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "subdir", "alerts.log")
            channel = FileChannel(filepath)
            alert = Alert(level=AlertLevel.INFO, source="test", message="dir test")
            channel.send(alert)
            assert os.path.exists(filepath)


class TestAlertManager:
    def test_send_alert(self):
        """send 创建并分发告警。"""
        mgr = AlertManager()
        alert = mgr.send(AlertLevel.ERROR, "test_source", "something failed")
        assert isinstance(alert, Alert)
        assert alert.source == "test_source"
        assert len(mgr.history) == 1

    def test_multiple_alerts(self):
        """多次发送增加告警历史。"""
        mgr = AlertManager()
        mgr.send(AlertLevel.INFO, "src", "msg1")
        mgr.send(AlertLevel.WARNING, "src", "msg2")
        assert len(mgr.history) == 2

    def test_acknowledge(self):
        """确认告警。"""
        mgr = AlertManager()
        alert = mgr.send(AlertLevel.ERROR, "src", "ack me")
        assert not alert.acknowledged
        result = mgr.acknowledge(alert.alert_id)
        assert result is True
        assert alert.acknowledged is True

    def test_acknowledge_nonexistent(self):
        """确认不存在的告警返回 False。"""
        mgr = AlertManager()
        assert mgr.acknowledge("nonexistent") is False

    def test_channel_integration(self):
        """通道集成：FileChannel + AlertManager。"""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            filepath = f.name

        try:
            mgr = AlertManager()
            channel = FileChannel(filepath)
            mgr.register_channel(channel)

            mgr.send(AlertLevel.CRITICAL, "integration", "critical error")

            with open(filepath) as f:
                line = f.readline().strip()
            entry = json.loads(line)
            assert entry["level"] == "critical"
            assert entry["source"] == "integration"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_unregister_channel(self):
        """注销通道后不再发送。"""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            filepath = f.name

        try:
            mgr = AlertManager()
            channel = FileChannel(filepath)
            mgr.register_channel(channel)
            mgr.unregister_channel(channel)

            mgr.send(AlertLevel.INFO, "src", "should not appear")

            # 文件应为空
            with open(filepath) as f:
                content = f.read()
            assert content == ""
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_clear_history(self):
        """清空告警历史。"""
        mgr = AlertManager()
        mgr.send(AlertLevel.INFO, "src", "msg")
        mgr.clear_history()
        assert len(mgr.history) == 0
