"""Phase W: ServerManager — 统一 HTTP Server 与 Webhook 网关管理。

整合现有 FastAPI 服务器，新增：
- 统一 ServerManager（启动/停止/健康检查）
- WebhookGateway（接收外部回调）
- 进程守护（后台运行 + 崩溃重启）
- 健康指标暴露

启动方式:
    from ocos.external.server_manager import ServerManager
    sm = ServerManager()
    sm.start()  # 启动 HTTP API + Webhook Gateway
    sm.wait()   # 阻塞等待
    sm.stop()   # 优雅关闭
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class WebhookPayload:
    """Webhook 入站载荷."""
    
    def __init__(self, source: str, event_type: str, data: dict[str, Any], 
                 timestamp: Optional[str] = None):
        self.source = source
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.payload_id = f"{source}:{event_type}:{int(time.time() * 1000)}"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_id": self.payload_id,
            "source": self.source,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class WebhookReceiver:
    """Webhook 接收器（线程安全队列）."""
    
    def __init__(self, max_queue_size: int = 10000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._handlers: dict[str, list[Callable]] = {}
        self._processed = 0
        self._errors = 0
    
    async def receive(self, payload: WebhookPayload) -> bool:
        """接收 webhook 载荷。"""
        try:
            self._queue.put_nowait(payload)
            logger.debug("Webhook received: %s", payload.payload_id)
            return True
        except asyncio.QueueFull:
            logger.warning("Webhook queue full, dropping: %s", payload.payload_id)
            return False
    
    async def process_loop(self) -> None:
        """处理循环（后台任务）。"""
        while True:
            try:
                payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(payload)
                self._processed += 1
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._errors += 1
                logger.error("Webhook processing error: %s", e)
    
    async def _dispatch(self, payload: WebhookPayload) -> None:
        """分发到处理器。"""
        # 精确匹配
        handlers = self._handlers.get(payload.event_type, [])
        # 通配符匹配
        wildcard_handlers = [
            h for evt, hs in self._handlers.items() 
            for h in hs if evt == "*"
        ]
        
        for handler in handlers + wildcard_handlers:
            try:
                await handler(payload)
            except Exception as e:
                logger.warning("Handler error for %s: %s", payload.payload_id, e)
    
    def register(self, event_type: str, handler: Callable) -> None:
        """注册处理器。"""
        self._handlers.setdefault(event_type, []).append(handler)
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "processed": self._processed,
            "errors": self._errors,
            "queue_size": self._queue.qsize(),
            "handlers": len([h for hs in self._handlers.values() for h in hs]),
        }


class WebhookGateway:
    """Webhook 网关（HTTP 入口 + 队列）。"""
    
    def __init__(self, port: int = 8901, host: str = "127.0.0.1",
                 receiver: Optional[WebhookReceiver] = None):
        self.port = port
        self.host = host
        self.receiver = receiver or WebhookReceiver()
        self._app = None
        self._server = None
        self._thread = None
    
    @property
    def app(self):
        """获取 FastAPI 应用（懒加载）。"""
        if self._app is None:
            self._app = self._create_app()
        return self._app
    
    def _create_app(self):
        """创建 FastAPI 应用。"""
        try:
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse
        except ImportError:
            return None
        
        app = FastAPI(title="OCOS Webhook Gateway")
        
        @app.post("/webhook/{source}/{event_type}")
        async def receive_webhook(source: str, event_type: str, body: dict[str, Any]):
            payload = WebhookPayload(
                source=source,
                event_type=event_type,
                data=body,
            )
            success = await self.receiver.receive(payload)
            return JSONResponse({
                "received": success,
                "payload_id": payload.payload_id,
            })
        
        @app.post("/webhook/")
        async def receive_webhook_root(body: dict[str, Any]):
            source = body.get("source", "unknown")
            event_type = body.get("event_type", "*")
            payload = WebhookPayload(
                source=source,
                event_type=event_type,
                data=body.get("data", body),
            )
            success = await self.receiver.receive(payload)
            return JSONResponse({
                "received": success,
                "payload_id": payload.payload_id,
            })
        
        @app.get("/webhook/stats")
        async def webhook_stats():
            return JSONResponse(self.receiver.get_stats())
        
        return app
    
    async def start_background(self) -> bool:
        """后台启动。"""
        if self._app is None:
            return False
        
        try:
            import uvicorn
            config = uvicorn.Config(
                self._app,
                host=self.host,
                port=self.port,
                log_level="warning",
            )
            self._server = uvicorn.Server(config)
            
            async def _run():
                await self._server.serve()
            
            self._thread = threading.Thread(target=lambda: asyncio.run(_run()), daemon=True)
            self._thread.start()
            logger.info("Webhook gateway started on %s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to start webhook gateway: %s", e)
            return False
    
    async def stop_background(self) -> None:
        """停止网关。"""
        if self._server:
            await self._server.shutdown()
            self._server = None
            logger.info("Webhook gateway stopped")
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "host": self.host,
            "running": self._server is not None and self._server.should_exit == False,
            "receiver_stats": self.receiver.get_stats(),
        }


class ServerManager:
    """HTTP API 服务器管理器。
    
    负责：
    1. 启动 FastAPI 服务器（主 API + Webhook Gateway）
    2. 健康检查与监控
    3. 优雅关闭
    4. 崩溃后自动重启（可选）
    """
    
    def __init__(
        self,
        api_port: int = 8900,
        webhook_port: int = 8901,
        auto_restart: bool = False,
        max_restart_attempts: int = 3,
        health_check_interval: int = 30,
    ):
        self._api_port = api_port
        self._webhook_port = webhook_port
        self.auto_restart = auto_restart
        self.max_restart_attempts = max_restart_attempts
        self.health_check_interval = health_check_interval
        
        self._api_server = None
        self._webhook_gateway: Optional[WebhookGateway] = None
        self._health_thread = None
        self._running = False
        self._start_time: Optional[datetime] = None
        self._restart_count = 0
        self._stats = {
            "start_count": 0,
            "stop_count": 0,
            "crash_count": 0,
            "health_checks": 0,
        }
    
    @property
    def api_port(self) -> int:
        """API 端口。"""
        env_port = os.getenv("OCOS_API_PORT")
        return int(env_port) if env_port else self._api_port

    @api_port.setter
    def api_port(self, value: int) -> None:
        self._api_port = value
    
    @property
    def webhook_port(self) -> int:
        """Webhook 端口。"""
        env_port = os.getenv("OCOS_WEBHOOK_PORT")
        return int(env_port) if env_port else self._webhook_port

    @webhook_port.setter
    def webhook_port(self, value: int) -> None:
        self._webhook_port = value
    
    def start(self) -> bool:
        """同步启动服务器（阻塞式）。"""
        if self._running:
            logger.warning("Server already running")
            return True
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(self._async_start())
            if success:
                self._running = True
                self._start_time = datetime.now(timezone.utc)
                self._stats["start_count"] += 1
                logger.info("Server started on port %d", self.api_port)
            
            # 启动健康检查
            if success and self.health_check_interval > 0:
                self._start_health_check()
            
            return success
        finally:
            loop.close()
    
    async def _async_start(self) -> bool:
        """异步启动。"""
        try:
            from ocos.interaction.api.server import app
        except ImportError as e:
            logger.error("Failed to import OCOS API: %s", e)
            return False
        
        try:
            import uvicorn
            
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.api_port,
                log_level="warning",
            )
            self._api_server = uvicorn.Server(config)
            
            # 启动 Webhook Gateway
            if self.webhook_port > 0:
                self._webhook_gateway = WebhookGateway(port=self.webhook_port)
                await self._webhook_gateway.start_background()
            
            # 后台运行
            async def _run_server():
                await self._api_server.serve()
            
            server_task = asyncio.create_task(_run_server())
            
            # 等待几秒确认启动
            await asyncio.sleep(2)
            
            if self._api_server.started:
                logger.info("API server ready on port %d", self.api_port)
                return True
            else:
                logger.error("API server failed to start")
                server_task.cancel()
                return False
                
        except Exception as e:
            logger.error("Failed to start server: %s", e)
            return False
    
    def stop(self) -> bool:
        """同步停止服务器。"""
        if not self._running:
            return True
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(self._async_stop())
            if success:
                self._running = False
                self._stats["stop_count"] += 1
                logger.info("Server stopped")
            return success
        finally:
            loop.close()
    
    async def _async_stop(self) -> bool:
        """异步停止。"""
        try:
            if self._api_server:
                await self._api_server.shutdown()
                self._api_server = None
            
            if self._webhook_gateway:
                await self._webhook_gateway.stop_background()
                self._webhook_gateway = None
            
            return True
        except Exception as e:
            logger.error("Error stopping server: %s", e)
            return False
    
    def wait(self) -> None:
        """阻塞等待服务器运行（用于主线程）。"""
        if not self._running:
            raise RuntimeError("Server not running")
        
        logger.info("Server running, waiting for shutdown signal...")
        
        def _shutdown(signum, frame):
            logger.info("Received signal %d, shutting down...", signum)
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        
        while self._running:
            time.sleep(1)
    
    def _start_health_check(self) -> None:
        """启动健康检查线程。"""
        def _check():
            while self._running:
                time.sleep(self.health_check_interval)
                self._perform_health_check()
        
        self._health_thread = threading.Thread(target=_check, daemon=True)
        self._health_thread.start()
    
    def _perform_health_check(self) -> None:
        """执行健康检查。"""
        self._stats["health_checks"] += 1
        
        try:
            import urllib.request
            url = f"http://127.0.0.1:{self.api_port}/ocos/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    logger.debug("Health check OK")
                else:
                    logger.warning("Health check returned %d", resp.status)
        except Exception as e:
            logger.error("Health check failed: %s", e)
            self._stats["crash_count"] += 1
            
            if self.auto_restart and self._restart_count < self.max_restart_attempts:
                logger.info("Attempting restart (%d/%d)", 
                          self._restart_count + 1, self.max_restart_attempts)
                self._restart_count += 1
                self.stop()
                time.sleep(5)
                self.start()
    
    def health_check(self) -> dict[str, Any]:
        """手动健康检查。"""
        result = {
            "status": "healthy",
            "uptime_seconds": 0,
            "stats": self._stats.copy(),
        }
        
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            result["uptime_seconds"] = uptime
        
        try:
            import urllib.request
            url = f"http://127.0.0.1:{self.api_port}/ocos/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    result["status"] = "unhealthy"
                    result["error"] = f"HTTP {resp.status}"
        except Exception as e:
            result["status"] = "unhealthy"
            result["error"] = str(e)
        
        return result
    
    def get_status(self) -> dict[str, Any]:
        """获取服务器状态。"""
        return {
            "running": self._running,
            "api_port": self.api_port,
            "webhook_port": self.webhook_port,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "stats": self._stats.copy(),
            "webhook_gateway": (
                self._webhook_gateway.get_stats() 
                if self._webhook_gateway else None
            ),
        }
    
    def register_webhook_handler(self, event_type: str, handler: Callable) -> None:
        """注册 webhook 处理器。"""
        if self._webhook_gateway:
            self._webhook_gateway.receiver.register(event_type, handler)
        else:
            logger.warning("Webhook gateway not started, handler will be registered later")
    
    def send_webhook(self, source: str, event_type: str, data: dict[str, Any]) -> bool:
        """发送 webhook（出站）。"""
        try:
            import urllib.request
            
            payload = json.dumps({
                "source": source,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).encode("utf-8")
            
            url = f"http://127.0.0.1:{self.webhook_port}/webhook/"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
                
        except Exception as e:
            logger.warning("Failed to send webhook: %s", e)
            return False


class ServerContext:
    """服务器上下文管理器（with 语句支持）。"""
    
    def __init__(self, manager: ServerManager):
        self._manager = manager
    
    def __enter__(self):
        self._manager.start()
        return self._manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._manager.stop()
        return False


# 让 ServerManager 也支持 with 语句
ServerManager.__enter__ = ServerContext.__enter__
ServerManager.__exit__ = ServerContext.__exit__


# ── 工厂函数 ─────────────────────────────────────────────────────

def create_server_manager(
    api_port: Optional[int] = None,
    webhook_port: Optional[int] = None,
    auto_restart: bool = False,
    **kwargs,
) -> ServerManager:
    """创建 ServerManager（支持环境变量覆盖）。"""
    env_api = os.getenv("OCOS_API_PORT")
    env_webhook = os.getenv("OCOS_WEBHOOK_PORT")
    
    return ServerManager(
        api_port=int(env_api) if env_api else (api_port or 8900),
        webhook_port=int(env_webhook) if env_webhook else (webhook_port or 8901),
        auto_restart=auto_restart,
        **kwargs,
    )


def run_server_background(api_port: int = 8900, **kwargs) -> ServerManager:
    """后台启动服务器（非阻塞）。"""
    manager = ServerManager(api_port=api_port, **kwargs)
    
    def _run():
        manager.start()
        manager.wait()
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    
    return manager
