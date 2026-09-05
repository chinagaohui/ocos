"""S4.2: 占位端点 501 化回归（白皮书 P4）。

- /ocos/memory/query、/ocos/belief、/ocos/trace/{id} 占位端点
  返回 501 + note，不再返回 200 空结果
- 认证豁免保持：正确 Token 请求仍先过 PermissionGuard
- CLI trace show 返回退出码 2（未实现）
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ocos.interaction.api import auth as api_auth
from ocos.interaction.api.server import app


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("OCOS_API_TOKEN", "test-token")
    monkeypatch.delenv("OCOS_API_AUTH_DISABLED", raising=False)
    api_auth.reset_token_cache()
    yield monkeypatch
    api_auth.reset_token_cache()


def _headers():
    return {"Authorization": "Bearer test-token"}


def test_memory_query_returns_501(env):
    with TestClient(app) as client:
        r = client.post("/ocos/memory/query",
                        json={"query": "最近目标"}, headers=_headers())
    assert r.status_code == 501
    assert "not implemented" in str(r.json()["detail"])


def test_belief_query_returns_501(env):
    with TestClient(app) as client:
        r = client.get("/ocos/belief", headers=_headers())
    assert r.status_code == 501
    assert "not implemented" in str(r.json()["detail"])


def test_trace_get_returns_501(env):
    with TestClient(app) as client:
        r = client.get("/ocos/trace/TRACE-1", headers=_headers())
    assert r.status_code == 501
    assert "not implemented" in str(r.json()["detail"])


def test_trace_show_cli_exit_code_2():
    from ocos.interaction.cli.main import main
    assert main(["trace", "show", "TRACE-001"]) == 2
