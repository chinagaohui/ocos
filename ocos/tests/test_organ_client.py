"""OrganClient 单元测试（S4：OCOS → OpenTale 写作器官驱动）。

用本地 mock HTTP server 验证客户端逻辑，不依赖运行中的 OpenTale 服务：
- health/status 只读
- generate 提交 → task_id
- wait 轮询至终态
- 事件增量回收
- 超时抛 OrganTaskTimeout
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ocos.opentale_bridge.organ_client import (
    OrganClient,
    OrganClientError,
    OrganTaskTimeout,
)


@pytest.fixture(autouse=True)
def _bypass_proxy_for_loopback(monkeypatch):
    """P3 (2026-09-01): 环境代理隔离 — 测试必须直连 loopback。

    开发机 shell 常设 ALL_PROXY=http://127.0.0.1:10808 等; no_proxy 若
    写成 CIDR 格式 (127.0.0.0/8), urllib 不识别 → 127.0.0.1 请求被代理
    转发, test_network_error_raises 期望立即 refused 却走代理超时。
    显式声明 loopback 直连, 使测试在代理环境/CI 双态下行为一致。
    """
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost,::1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost,::1")


class _MockOrganHandler(BaseHTTPRequestHandler):
    """最小 Organ API mock：generate 返回 running→completed 的任务状态机。"""

    _counter = 0

    def log_message(self, *args):  # 静默
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # OrganClient 请求形如 /api/organ/tasks/... → 剥前缀后匹配
        path = self.path[len("/api/organ"):] if self.path.startswith("/api/organ") else self.path
        if path == "/health":
            return self._send(200, {"status": "ok", "service": "opentale-organ", "version": "v1"})
        if path == "/status":
            return self._send(200, {"status": "healthy", "llm_enabled": True,
                                    "tasks": {"active": 1, "pending": 1}, "projects": 3})
        if path.startswith("/tasks/task-mock/events"):
            return self._send(200, {"task_id": "task-mock", "events": [
                {"seq": 1, "type": "task_created", "payload": {}, "ts": "t"},
                {"seq": 2, "type": "task_status", "payload": {"status": "running"}, "ts": "t"},
            ], "next_since": 2})
        if path.startswith("/tasks/task-stuck"):
            return self._send(200, {"id": "task-stuck", "status": "running",
                                    "progress": {"step": 1, "total": 3, "label": "永不完成"}})
        if path.startswith("/tasks/task-mock"):
            # 前 2 次查询 running，之后 completed
            _MockOrganHandler._counter += 1
            if _MockOrganHandler._counter <= 2:
                return self._send(200, {"id": "task-mock", "status": "running",
                                        "progress": {"step": 1, "total": 3, "label": "生成中"}})
            return self._send(200, {"id": "task-mock", "status": "completed",
                                    "result": "《测试》生成完成：3 章",
                                    "progress": {"step": 3, "total": 3, "label": "完成"}})
        if path == "/projects":
            return self._send(200, [{"title": "测试书", "genre": "sci_fi", "chapters": 3}])
        return self._send(404, {"detail": "not found"})

    def do_POST(self):
        path = self.path[len("/api/organ"):] if self.path.startswith("/api/organ") else self.path
        if path == "/actions/generate":
            return self._send(200, {"task_id": "task-mock", "status": "accepted",
                                    "poll": "/api/organ/tasks/task-mock"})
        return self._send(404, {"detail": "not found"})


@pytest.fixture(scope="module")
def server() -> str:
    httpd = HTTPServer(("127.0.0.1", 0), _MockOrganHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/api/organ"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def _reset_counter():
    _MockOrganHandler._counter = 0
    yield


def test_health(server: str) -> None:
    c = OrganClient(base_url=server)
    assert c.health()["status"] == "ok"


def test_status(server: str) -> None:
    c = OrganClient(base_url=server)
    s = c.status()
    assert s["llm_enabled"] is True and s["projects"] == 3


def test_projects(server: str) -> None:
    c = OrganClient(base_url=server)
    items = c.projects()
    assert items[0]["title"] == "测试书"


def test_generate_submit(server: str) -> None:
    c = OrganClient(base_url=server)
    resp = c.generate(title="测试书", content="一段大纲内容", characters=["林澈"])
    assert resp["task_id"] == "task-mock" and resp["status"] == "accepted"


def test_wait_polls_to_terminal(server: str) -> None:
    c = OrganClient(base_url=server, poll_interval_seconds=0.05)
    t = c.wait("task-mock", timeout_seconds=5)
    assert t["status"] == "completed"
    assert "生成完成" in t["result"]


def test_events_incremental(server: str) -> None:
    c = OrganClient(base_url=server)
    page = c.events("task-mock")
    assert page["next_since"] == 2
    assert [e["type"] for e in page["events"]] == ["task_created", "task_status"]


def test_wait_timeout(server: str) -> None:
    c = OrganClient(base_url=server, poll_interval_seconds=0.01)
    with pytest.raises(OrganTaskTimeout):
        c.wait("task-stuck", timeout_seconds=0.05)


def test_network_error_raises(server: str) -> None:
    c = OrganClient(base_url="http://127.0.0.1:1/api/organ", timeout_seconds=0.5)
    with pytest.raises(OrganClientError):
        c.health()
