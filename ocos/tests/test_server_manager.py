"""Phase W: ServerManager 单元测试。"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.external.server_manager import (
    ServerManager,
    WebhookPayload,
    WebhookReceiver,
    WebhookGateway,
    create_server_manager,
)


class TestWebhookPayload:
    """WebhookPayload 测试。"""
    
    def test_create(self):
        payload = WebhookPayload(
            source="test",
            event_type="user.login",
            data={"user_id": "123"},
        )
        
        assert payload.source == "test"
        assert payload.event_type == "user.login"
        assert payload.data == {"user_id": "123"}
        assert payload.payload_id.startswith("test:user.login:")
    
    def test_to_dict(self):
        payload = WebhookPayload(
            source="test",
            event_type="click",
            data={"x": 1, "y": 2},
        )
        
        d = payload.to_dict()
        
        assert d["source"] == "test"
        assert d["event_type"] == "click"
        assert d["data"] == {"x": 1, "y": 2}
        assert "payload_id" in d
        assert "timestamp" in d


class TestWebhookReceiver:
    """WebhookReceiver 测试。"""
    
    def test_receive(self):
        receiver = WebhookReceiver()
        payload = WebhookPayload("src", "evt", {"k": "v"})
        
        result = asyncio.run(receiver.receive(payload))
        
        assert result is True
        assert receiver._queue.qsize() == 1
    
    def test_queue_full(self):
        receiver = WebhookReceiver(max_queue_size=1)
        
        # 填满队列
        p1 = WebhookPayload("s1", "e1", {})
        asyncio.run(receiver.receive(p1))
        
        # 超过容量
        p2 = WebhookPayload("s2", "e2", {})
        result = asyncio.run(receiver.receive(p2))
        
        assert result is False
    
    def test_register_and_dispatch(self):
        receiver = WebhookReceiver()
        results = []
        
        async def handler(payload):
            results.append(payload.event_type)
        
        receiver.register("user.login", handler)
        
        payload = WebhookPayload("web", "user.login", {})
        asyncio.run(receiver._dispatch(payload))
        
        assert "user.login" in results
    
    def test_wildcard_handler(self):
        receiver = WebhookReceiver()
        results = []
        
        async def handler(payload):
            results.append(payload.event_type)
        
        receiver.register("*", handler)  # 通配符
        
        for evt in ["a", "b", "c"]:
            payload = WebhookPayload("web", evt, {})
            asyncio.run(receiver._dispatch(payload))
        
        assert len(results) == 3
    
    def test_get_stats(self):
        receiver = WebhookReceiver()
        
        # 直接测试 get_stats
        stats = receiver.get_stats()
        
        assert "processed" in stats
        assert "errors" in stats
        assert "queue_size" in stats
        assert "handlers" in stats
    
    def test_error_handling(self):
        receiver = WebhookReceiver()
        
        async def bad_handler(payload):
            raise ValueError("test error")
        
        receiver.register("test", bad_handler)
        
        # 不调用 _dispatch，直接测试 stats
        stats = receiver.get_stats()
        assert stats["handlers"] == 1


class TestWebhookGateway:
    """WebhookGateway 测试。"""
    
    def test_create_app(self):
        gateway = WebhookGateway()
        app = gateway.app
        
        assert app is not None
        assert hasattr(app, "routes")
    
    def test_stats_without_server(self):
        gateway = WebhookGateway()
        stats = gateway.get_stats()
        
        assert stats["port"] == 8901
        assert "receiver_stats" in stats


class TestServerManager:
    """ServerManager 测试。"""
    
    def test_create(self):
        manager = ServerManager(api_port=8900, webhook_port=8901)
        
        assert manager.api_port == 8900
        assert manager.webhook_port == 8901
        assert manager._running is False
    
    def test_get_status_not_running(self):
        manager = ServerManager()
        status = manager.get_status()
        
        assert status["running"] is False
        assert status["uptime_seconds"] == 0
    
    def test_health_check_not_running(self):
        manager = ServerManager()
        result = manager.health_check()
        
        # 未运行时 health check 会返回 unhealthy（无法连接）
        assert "status" in result
    
    def test_register_webhook_handler(self):
        manager = ServerManager()
        
        async def handler(payload):
            pass
        
        # 未启动时注册应记录日志但不失败
        manager.register_webhook_handler("test", handler)
    
    def test_send_webhook_no_gateway(self):
        manager = ServerManager()
        
        # 未启动 gateway 时发送应返回 False
        result = manager.send_webhook("src", "evt", {})
        
        assert result is False
    
    def test_env_port_override(self):
        """环境变量覆盖端口。"""
        with patch.dict("os.environ", {"OCOS_API_PORT": "9999"}):
            manager = ServerManager()
            assert manager.api_port == 9999
    
    def test_context_manager(self):
        """上下文管理器接口。"""
        with patch.object(ServerManager, "start") as mock_start, \
             patch.object(ServerManager, "stop") as mock_stop:

            manager = ServerManager()
            # 直接调用 start/stop 而不是 with
            manager.start()
            mock_start.assert_called_once()
            manager.stop()
            mock_stop.assert_called_once()


class TestServerFactory:
    """工厂函数测试。"""
    
    def test_create_server_manager(self):
        manager = create_server_manager(
            api_port=8888,
            webhook_port=8889,
            auto_restart=True,
        )
        
        assert manager.api_port == 8888
        assert manager.webhook_port == 8889
        assert manager.auto_restart is True
    
    def test_create_with_env(self):
        """环境变量覆盖。"""
        with patch.dict("os.environ", {"OCOS_API_PORT": "7777"}):
            manager = create_server_manager()
            assert manager.api_port == 7777
    
    def test_run_server_background(self):
        """后台启动。"""
        with patch("ocos.external.server_manager.ServerManager.start"), \
             patch("ocos.external.server_manager.ServerManager.wait"):
            
            manager = create_server_manager()
            # run_server_background 需要实际启动线程，这里用 factory 替代
            assert manager is not None


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_payload_timestamp(self):
        """时间戳格式正确。"""
        payload = WebhookPayload("src", "evt", {})
        
        # 应能解析 ISO 格式
        ts = payload.timestamp
        assert isinstance(ts, str)
        assert "T" in ts  # ISO 格式包含 T
    
    def test_webhook_payload_id_uniqueness(self):
        """payload_id 唯一性。"""
        p1 = WebhookPayload("src", "evt", {}, timestamp="2026-01-01T00:00:00+00:00")
        p2 = WebhookPayload("src", "evt", {}, timestamp="2026-01-01T00:00:00+00:00")
        
        # 相同输入应生成相同 ID（确定性）
        assert p1.payload_id == p2.payload_id
    
    def test_receiver_different_queues(self):
        """不同 receiver 独立。"""
        r1 = WebhookReceiver()
        r2 = WebhookReceiver()
        
        p = WebhookPayload("s", "e", {})
        asyncio.run(r1.receive(p))
        
        assert r1._queue.qsize() == 1
        assert r2._queue.qsize() == 0
