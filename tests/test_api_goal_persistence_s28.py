"""S2.8: POST /ocos/goal 持久化回归（白皮书 P2）。

- 创建目标真实落 GoalStore（原实现仅内存对象不落库，目标即丢失）
- GET /ocos/goal/{id} 真实查询（原为 TBD 占位）
- daemon 认领链可消费（PENDING + origin_level=HUMAN）
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ocos.interaction.api import auth as api_auth
from ocos.interaction.api.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("OCOS_API_AUTH_DISABLED", "true")
    api_auth.reset_token_cache()
    return TestClient(app, raise_server_exceptions=False)


class TestGoalPersistence:
    def test_create_goal_persists(self, client, tmp_path):
        resp = client.post("/ocos/goal", json={
            "goal": "分析日志错误分布", "domain": "analysis",
            "priority": 3})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        goal_id = body["data"]["goal_id"]
        assert goal_id

        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=str(tmp_path / "t.db"))
        row = store.load(goal_id)
        assert row is not None, "目标应已落库"
        assert row["status"] == "PENDING"
        assert row["origin_level"] == "HUMAN"

    def test_get_goal_real_query(self, client, tmp_path):
        create = client.post("/ocos/goal", json={
            "goal": "写周报", "domain": "writing", "priority": 2})
        goal_id = create.json()["data"]["goal_id"]
        resp = client.get(f"/ocos/goal/{goal_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "PENDING"

    def test_get_goal_missing_404(self, client):
        resp = client.get("/ocos/goal/GOAL-nonexistent")
        assert resp.status_code == 404

    def test_claimable_by_daemon(self, client, tmp_path):
        """落库目标满足 daemon 认领条件（PENDING+HUMAN 原子认领）。"""
        create = client.post("/ocos/goal", json={
            "goal": "整理会议纪要", "domain": "writing", "priority": 3})
        goal_id = create.json()["data"]["goal_id"]
        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=str(tmp_path / "t.db"))
        claimed = store.claim_pending_human(limit=1)
        assert any(c["id"] == goal_id for c in claimed)
