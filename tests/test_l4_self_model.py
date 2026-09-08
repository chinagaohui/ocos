"""L4-2 (升级方案 v1.0) — 自我模型测试：实测统计 + boot 加载 + tick 校准 + prompt 注入。

覆盖:
  - 诚实性: 空库 load() → None; render → "尚未校准"
  - 能力实测: goal_result episodes 按 agent 分组成功率（方向正确）
  - registry 能力名合并: 无实测 → attempts=0, success_rate=None
  - 性格参数: 回复均长 → 响应风格; 审批比例 → 风险偏好; 无数据 → 未知
  - 当前专注: ACTIVE 目标 top3
  - content_hash: 内容不变 hash 不变; 内容变 hash 变（V5 校验输入）
  - 校准版本递增; render 含实测统计
  - prompt 注入: build_context 含自我模型块
  - daemon 接线: boot 加载 + tick 校准挂载（源码级断言）
"""

from __future__ import annotations

import sqlite3

import pytest

from ocos.self.agent_self_model import AgentSelfModel

_USER_MESSAGES_DDL = """
CREATE TABLE IF NOT EXISTS user_messages (
    id           TEXT PRIMARY KEY,
    sender       TEXT NOT NULL DEFAULT 'cli',
    content      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    created_at   TEXT NOT NULL,
    consumed_at  TEXT,
    note         TEXT DEFAULT '',
    reply        TEXT DEFAULT '',
    replied_at   TEXT
)
"""


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "l4s.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    conn = sqlite3.connect(p)
    conn.execute(_USER_MESSAGES_DDL)
    conn.commit()
    conn.close()
    return p


def _insert_goal_result(db, agent: str, success: bool) -> None:
    """插入一条 goal_result episode（实测数据源）。"""
    import uuid
    from datetime import datetime, timezone
    from ocos.memory.episode.models import Episode, EpisodeStatus
    from ocos.memory.episode.store import EpisodeStore
    estore = EpisodeStore(db_path=db)
    estore.initialize()
    estore.save(Episode(
        id=f"EPI-{uuid.uuid4().hex[:12]}",
        experience_id=f"EXP-{uuid.uuid4().hex[:10]}",
        created_at=datetime.now(timezone.utc),
        session_id="t",
        context={"agent": agent},
        goal="g",
        decision="d",
        action="goal_result",
        outcome={"success": success},
        significance_score=0.5,
        source="agent_runtime",
        status=EpisodeStatus.ACTIVE,
        tags=[],
    ))


def _insert_user_message(db, reply: str) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO user_messages (id, content, reply, created_at) "
        "VALUES (?, 'q', ?, '2026-01-01')",
        (f"UM-{reply[:10]}-{conn.total_changes}", reply))
    conn.commit()
    conn.close()


def _insert_pending(db, status: str) -> None:
    from ocos.execution.pending import PendingStore
    pid = PendingStore(db_path=db).enqueue(
        action_type="noop", payload={}, text="t")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE pending_actions SET status = ? WHERE id = ?",
                 (status, pid))
    conn.commit()
    conn.close()


def _insert_active_goal(db, description: str, priority: float) -> None:
    from ocos.goal.store import GoalStore
    GoalStore(db_path=db).save(
        goal_id=f"G-{description[:8]}-{priority}",
        level="TASK", status="ACTIVE",
        description=description, priority=priority)


# ── 诚实性 ───────────────────────────────────────────────────────────


class TestHonesty:
    def test_load_empty_returns_none(self, db):
        assert AgentSelfModel(db).load() is None

    def test_render_uncalibrated(self, db):
        assert "尚未校准" in AgentSelfModel(db).render()

    def test_no_data_stats_unknown(self, db):
        snap = AgentSelfModel(db).calibrate()
        assert snap["personality"]["reply_style"] == "未知"
        assert snap["personality"]["risk_preference"] == "未知"
        assert snap["capabilities"] == []
        assert snap["focus"] == []


# ── 能力实测 ─────────────────────────────────────────────────────────


class TestCapabilities:
    def test_success_rate_direction(self, db):
        for _ in range(3):
            _insert_goal_result(db, "executor", True)
        _insert_goal_result(db, "executor", False)
        snap = AgentSelfModel(db).calibrate()
        caps = {c["name"]: c for c in snap["capabilities"]}
        assert caps["executor"]["attempts"] == 4
        assert caps["executor"]["success_rate"] == pytest.approx(0.75)
        assert caps["executor"]["successes"] == 3

    def test_registry_names_merged(self, db):
        _insert_goal_result(db, "executor", True)
        snap = AgentSelfModel(db).calibrate(
            capability_names=["filesystem", "shell", "executor"])
        caps = {c["name"]: c for c in snap["capabilities"]}
        assert caps["executor"]["attempts"] == 1
        assert caps["filesystem"]["attempts"] == 0
        assert caps["filesystem"]["success_rate"] is None
        # 实测过排前，未实测排后
        names = [c["name"] for c in snap["capabilities"]]
        assert names.index("executor") < names.index("filesystem")


# ── 性格参数 ─────────────────────────────────────────────────────────


class TestPersonality:
    def test_reply_style_short(self, db):
        _insert_user_message(db, "好的")
        snap = AgentSelfModel(db).calibrate()
        assert snap["personality"]["reply_style"] == "简洁"
        assert snap["personality"]["reply_count"] == 1

    def test_reply_style_detailed(self, db):
        _insert_user_message(db, "x" * 300)
        snap = AgentSelfModel(db).calibrate()
        assert snap["personality"]["reply_style"] == "详细"

    def test_risk_preference_trusting(self, db):
        _insert_pending(db, "approved")
        snap = AgentSelfModel(db).calibrate()
        assert snap["personality"]["risk_preference"] == "偏信任"

    def test_risk_preference_cautious(self, db):
        _insert_pending(db, "approved")
        _insert_pending(db, "denied")
        _insert_pending(db, "denied")
        snap = AgentSelfModel(db).calibrate()
        assert snap["personality"]["risk_preference"] == "偏谨慎"


# ── 当前专注 ─────────────────────────────────────────────────────────


class TestFocus:
    def test_active_goals_top3(self, db):
        _insert_active_goal(db, "分析宿主机", 9.0)
        _insert_active_goal(db, "写周报", 5.0)
        _insert_active_goal(db, "整理记忆", 1.0)
        _insert_active_goal(db, "低优先级任务", 0.5)
        snap = AgentSelfModel(db).calibrate()
        assert snap["focus"] == ["分析宿主机", "写周报", "整理记忆"]


# ── hash 与版本 ──────────────────────────────────────────────────────


class TestHashAndVersion:
    def test_hash_stable_when_data_unchanged(self, db):
        m = AgentSelfModel(db)
        s1 = m.calibrate()
        s2 = m.calibrate()
        assert s1["content_hash"] == s2["content_hash"]
        assert s2["version"] == 2  # 版本递增但内容 hash 不变

    def test_hash_changes_when_data_changes(self, db):
        m = AgentSelfModel(db)
        s1 = m.calibrate()
        _insert_goal_result(db, "executor", True)
        s2 = m.calibrate()
        assert s1["content_hash"] != s2["content_hash"]


# ── render 与 prompt 注入 ────────────────────────────────────────────


class TestRender:
    def test_render_contains_stats(self, db):
        _insert_goal_result(db, "executor", True)
        _insert_user_message(db, "好的")
        _insert_active_goal(db, "分析宿主机", 9.0)
        AgentSelfModel(db).calibrate()
        text = AgentSelfModel(db).render()
        assert "自我模型（v1" in text
        assert "executor" in text
        assert "简洁" in text
        assert "分析宿主机" in text

    def test_render_snapshot_arg(self, db):
        snap = AgentSelfModel(db).calibrate()
        text = AgentSelfModel(db).render(snap)
        assert f"自我模型（v{snap['version']}" in text

    def test_build_context_contains_self_model(self, db, monkeypatch):
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(db + ".audit"))
        AgentSelfModel(db).calibrate()
        from ocos.interaction.converse import ChatResponder
        ctx = ChatResponder(db_path=db).build_context("", session_id="t")
        assert "自我模型（v1" in ctx


# ── daemon 接线（源码级） ────────────────────────────────────────────


class TestDaemonWiring:
    def test_daemon_boot_and_tick_wiring(self):
        import inspect
        from ocos import daemon
        src = inspect.getsource(daemon)
        assert "AgentSelfModel(db_path)" in src          # boot 装配
        assert "SelfModel boot:" in src                  # boot 加载日志
        assert "_self_model.calibrate(" in src           # tick 校准挂载
        assert "OCOS_SELF_MODEL_TICKS" in src            # 周期可调
