"""OCOS WebChat 路由测试（S6：OCOS 主对话入口）。

用 TestClient 直测 /ocos/chat（不依赖 OpenTale 服务）：
- 写作意图 → MasterAgent 决策（focus/tone）
- 执行意图 → 无意图时报错提示
- 任务状态查询
- 普通对话兜底
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    # S1.2: 本文件测业务逻辑而非认证 — 显式关闭 Bearer Token 门
    import os
    from ocos.interaction.api.server import app

    os.environ["OCOS_API_AUTH_DISABLED"] = "true"
    try:
        yield TestClient(app)
    finally:
        os.environ.pop("OCOS_API_AUTH_DISABLED", None)


def test_health(client: TestClient) -> None:
    r = client.get("/ocos/health")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_writing_intent_returns_decision(client: TestClient) -> None:
    r = client.post("/ocos/chat", json={
        "session_id": "t1",
        "message": "我想写一部都市情感小说，讲离婚冷静期三十天里两人重新学会面对彼此",
    })
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["decision"]["focus"] == "relationship"
    assert d["decision"]["tone"] == "warmth"
    assert "开始写" in d["content"]


def test_suspense_intent_not_misjudged(client: TestClient) -> None:
    r = client.post("/ocos/chat", json={
        "session_id": "t2",
        "message": "悬疑小说：法医在解剖中发现死者体内有来自未来的证据，必须查明真相",
    })
    d = r.json()["data"]
    assert d["decision"]["focus"] == "investigation"
    assert d["decision"]["tone"] in ("suspense", "tension")


def test_execute_without_intent_returns_guidance(client: TestClient) -> None:
    r = client.post("/ocos/chat", json={"session_id": "t3", "message": "开始写"})
    d = r.json()["data"]
    assert "写作意图" in d["content"]  # 无意图时引导先描述故事


def test_talk_fallback(client: TestClient) -> None:
    r = client.post("/ocos/chat", json={"session_id": "t4", "message": "你好"})
    assert r.status_code == 200
    assert "OCOS" in r.json()["data"]["content"]


def test_empty_message_rejected(client: TestClient) -> None:
    r = client.post("/ocos/chat", json={"session_id": "t5", "message": "  "})
    assert r.status_code == 422
