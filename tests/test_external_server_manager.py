"""Tests for ocos.external.server_manager - 服务器管理器。"""
import pytest


class TestServerManager:
    def test_import(self):
        from ocos.external.server_manager import ServerManager
        assert ServerManager is not None

    def test_create_default(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        assert mgr is not None
        assert mgr.api_port == 8900
        assert mgr.webhook_port == 8901
        assert mgr.max_restart_attempts == 3
        assert mgr.health_check_interval == 30

    def test_create_custom_port(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager(api_port=9000, webhook_port=9001)
        assert mgr.api_port == 9000
        assert mgr.webhook_port == 9001

    def test_get_status(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        status = mgr.get_status()
        assert isinstance(status, dict)

    def test_health_check(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        result = mgr.health_check()
        assert isinstance(result, dict)

    def test_register_webhook_handler(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        mgr.register_webhook_handler("test_event", lambda data: data)

    def test_send_webhook(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        result = mgr.send_webhook("source", "event_type", {"key": "value"})
        assert isinstance(result, bool)

    def test_start_stop_methods_exist(self):
        from ocos.external.server_manager import ServerManager
        mgr = ServerManager()
        assert hasattr(mgr, 'start')
        assert hasattr(mgr, 'stop')
        assert hasattr(mgr, 'wait')
        assert callable(mgr.start)
        assert callable(mgr.stop)
        assert callable(mgr.wait)

    def test_webhook_gateway_import(self):
        from ocos.external.server_manager import WebhookGateway
        assert WebhookGateway is not None

    def test_webhook_payload(self):
        from ocos.external.server_manager import WebhookPayload
        assert WebhookPayload is not None
        payload = WebhookPayload("source", "event", {"data": 1})
        d = payload.to_dict()
        assert d["source"] == "source"
        assert d["event_type"] == "event"
        assert d["data"] == {"data": 1}
        assert "payload_id" in d
        assert "timestamp" in d

    def test_webhook_receiver_import(self):
        from ocos.external.server_manager import WebhookReceiver
        assert WebhookReceiver is not None
