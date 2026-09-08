"""升级方案 v1.0 §3.4 — 验收 Gate 复验测试（L0–L4 各阶段出口判据）。

Gate 语义（方案 §3.4）:
    make gate（lint/类型/测试全绿，既有 Makefile 目标）
    + vitals-check（仪表盘指标达阶段阈值 — 本文件验证判定逻辑）
    + 红线 R1–R5（V8 硬性 — 出口判据复验，引用既有测试覆盖面）
    + 场景库 S1–S10（按阶段启用 — 既有场景测试映射表核对）

本文件不重复子测试断言，而是:
  1. check_thresholds 阶段判定逻辑全分支（L0–L4 阈值语义）
  2. /ocos/metrics 端点暴露（带 token 200 / 无 token 401 — R2 一致）
  3. R1–R5 红线出口判据的测试覆盖面核对（AST/文件级断言）
  4. L4 出口实弹: 真实 DB 上 vitals 全链路（聚合→判定→CLI exit code）
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ocos.monitoring.vitals import check_thresholds, compute_vitals


# ── 1. 阶段阈值判定逻辑 ──────────────────────────────────────────────


class TestThresholdLogic:
    def test_hard_redline_any_phase(self):
        for phase in ("L0", "L1", "L2", "L3", "L4"):
            v = {"redline_violation_count": 1, "identity_drift": 0,
                 "homeostasis_check_passed": True,
                 "autonomy_goal_ratio": 0.5, "autonomy_level": 2,
                 "proactive_report_count": 2}
            failures = check_thresholds(v, phase)
            assert any("redline" in f for f in failures), phase

    def test_hard_identity_drift_any_phase(self):
        v = {"redline_violation_count": 0, "identity_drift": 1,
             "homeostasis_check_passed": True, "autonomy_goal_ratio": 0.5,
             "autonomy_level": 2, "proactive_report_count": 2}
        for phase in ("L0", "L4"):
            assert any("identity_drift" in f for f in check_thresholds(v, phase))

    def test_l0_only_hard_items(self):
        v = {"redline_violation_count": 0, "identity_drift": 0}
        assert check_thresholds(v, "L0") == []

    def test_l2_self_check_failure_fails(self):
        v = {"redline_violation_count": 0, "identity_drift": 0,
             "homeostasis_check_passed": False}
        assert any("V7" in f for f in check_thresholds(v, "L2"))
        # L0/L1 不查 V7
        assert check_thresholds(v, "L0") == []

    def test_l2_self_check_missing_is_pending_not_failure(self):
        v = {"redline_violation_count": 0, "identity_drift": 0,
             "homeostasis_check_passed": None}
        failures = check_thresholds(v, "L2")
        assert any("[未点亮]" in f for f in failures)
        assert not any("✗" in f for f in failures)

    def test_l3_low_autonomy_ratio_only_at_level2(self):
        base = {"redline_violation_count": 0, "identity_drift": 0,
                "homeostasis_check_passed": True,
                "proactive_report_count": 2}
        v = dict(base, autonomy_level=2, autonomy_goal_ratio=0.1)
        assert any("autonomy_goal_ratio" in f for f in check_thresholds(v, "L3"))
        # LEVEL<2 不查比例（方案: ≥30%（LEVEL≥2 时））
        v1 = dict(base, autonomy_level=1, autonomy_goal_ratio=0.0)
        assert not any("autonomy_goal_ratio" in f
                       for f in check_thresholds(v1, "L3"))

    def test_l3_low_proactive_fails(self):
        v = {"redline_violation_count": 0, "identity_drift": 0,
             "homeostasis_check_passed": True, "autonomy_level": 2,
             "autonomy_goal_ratio": 0.5, "proactive_report_count": 0.0}
        assert any("proactive_report_count" in f
                   for f in check_thresholds(v, "L3"))

    def test_all_green_passes_l4(self):
        v = {"redline_violation_count": 0, "identity_drift": 0,
             "homeostasis_check_passed": True, "autonomy_level": 2,
             "autonomy_goal_ratio": 0.4, "proactive_report_count": 1.5}
        assert check_thresholds(v, "L4") == []


# ── 2. /ocos/metrics 端点（R2 一致：鉴权同源） ────────────────────────


@pytest.fixture()
def api_db(tmp_path, monkeypatch):
    """vitals 数据源 DB + OCOS_DB_PATH 注入。"""
    p = str(tmp_path / "gate.db")
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE episodes (id TEXT PRIMARY KEY, context TEXT, "
                 "outcome TEXT, tags TEXT, decision TEXT, action TEXT, "
                 "source TEXT, created_at TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("OCOS_DB_PATH", p)
    return p


class TestMetricsEndpoint:
    def test_metrics_with_token_ok(self, api_db, monkeypatch):
        from fastapi.testclient import TestClient
        monkeypatch.setenv("OCOS_API_TOKEN", "t-gate")
        from ocos.interaction.api.server import app
        client = TestClient(app)
        r = client.get("/ocos/metrics",
                       headers={"Authorization": "Bearer t-gate"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "vitals" in body["data"]
        assert body["data"]["phase"] == "L4"
        assert isinstance(body["data"]["threshold_violations"], list)

    def test_metrics_without_token_401(self, api_db, monkeypatch):
        """R2: /metrics 属业务端点 — 未带 token 一律 401（不设豁免）。"""
        from fastapi.testclient import TestClient
        monkeypatch.setenv("OCOS_API_TOKEN", "t-gate")
        from ocos.interaction.api.server import app
        client = TestClient(app)
        assert client.get("/ocos/metrics").status_code == 401


# ── 3. R1–R5 红线出口判据覆盖面（文件级核对） ─────────────────────────


class TestRedlineCoverage:
    @staticmethod
    def _read(*parts) -> str:
        from pathlib import Path
        root = Path(__file__).parent.parent
        return (root.joinpath(*parts)).read_text(encoding="utf-8")

    def test_r1_file_write_forced_approval(self):
        """R1: bridge 无 approval_id 兜底（伪造=拒绝）。

        行为级覆盖: tests/test_bridge_file_write_approval.py（L0-1 修复验证）。
        """
        src = self._read("ocos", "execution", "bridge.py")
        assert '"approval_id", "task-approved"' not in src
        assert "_verify_approval" in src
        from pathlib import Path
        assert (Path(__file__).parent / "test_bridge_file_write_approval.py"
                ).exists()

    def test_r2_api_auth_middleware(self):
        src = self._read("ocos", "interaction", "api", "server.py")
        assert "AuthMiddleware" in src
        assert self._read("ocos", "interaction", "api", "auth.py")

    def test_r3_level0_no_autonomous_goals(self):
        """R3: LEVEL=0 闸关闭自主提案（motivation/active_interaction 双闸）。"""
        src = self._read("ocos", "daemon", "__init__.py")
        assert "autonomy_level >= 1" in src

    def test_r4_audit_chain_replayable(self):
        """R4: 自主行为留痕（episode + audit JSONL 双通道）。"""
        src = self._read("ocos", "execution", "autonomy.py")
        assert "audit_level_change" in src
        m = self._read("ocos", "daemon", "motivation.py")
        assert "source=\"autonomous_goal_proposal\"" in m or \
               "source='autonomous_goal_proposal'" in m

    def test_r5_rate_limit_and_budget(self):
        """R5: 提案限速 + 待批队列（既有闸门存在）。"""
        src = self._read("ocos", "daemon", "motivation.py")
        assert "OCOS_AUTONOMY_GOAL_CAP" in src
        assert self._read("ocos", "execution", "pending.py")


# ── 4. L4 出口实弹: 真实 DB 全链路 ───────────────────────────────────


class TestL4GateE2E:
    def test_full_vitals_and_gate(self, tmp_path, monkeypatch):
        """注入真实行为数据 → compute_vitals → check_thresholds(L4) → CLI。"""
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        # 隔离宿主机心跳（LEVEL=2 激活 autonomy_goal_ratio 门 — 种子库无自主目标）
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(tmp_path / "hb.json"))
        override = tmp_path / "level"
        override.write_text("1")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
        p = str(tmp_path / "e2e.db")
        from ocos.memory.episode.store import EpisodeStore
        estore = EpisodeStore(db_path=p)
        estore.initialize()
        conn = sqlite3.connect(p)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS user_messages ("
            "id TEXT PRIMARY KEY, sender TEXT, content TEXT, status TEXT, "
            "created_at TEXT)")
        now = datetime.now(timezone.utc)
        # 7 次主动汇报（周窗内每天 1 次）→ proactive = 1/天（达标线）
        for i in range(7):
            conn.execute(
                "INSERT INTO user_messages VALUES (?,?,?,?,?)",
                (f"UM{i}", "ocos", "结果推送", "outbound",
                 (now - timedelta(days=i)).isoformat()))
        # L4-3 continuity 校验 OK 一次（drift=false）
        conn.execute(
            "INSERT INTO episodes (id, experience_id, created_at, session_id,"
            " context, goal, decision, action, outcome, source, status, tags)"
            " VALUES ('EPI-V5-OK', 'EXP-V5-OK', ?, 'continuity', '{}', "
            "'V5', 'OK', 'continuity_drift_alert', "
            "'{\"success\": true, \"drift\": false}', 'continuity_check', "
            "'active', '[\"v5\"]')", (now.isoformat(),))
        # L2 自检成功一次（homeostasis_check_passed=True）
        conn.execute(
            "INSERT INTO episodes (id, experience_id, created_at, session_id,"
            " context, goal, decision, action, outcome, source, status, tags)"
            " VALUES ('EPI-V7-OK', 'EXP-V7-OK', ?, 'self_check', '{}', "
            "'V7', 'OK', 'l2_self_check', "
            "'{\"success\": true}', 'self_check', "
            "'active', '[\"l2_self_check\"]')", (now.isoformat(),))
        conn.commit()
        conn.close()

        vitals = compute_vitals(p, window_days=7)
        assert vitals["proactive_report_count"] == pytest.approx(1.0, abs=0.01)
        assert vitals["identity_drift"] == 0
        assert vitals["redline_violation_count"] == 0
        assert vitals["homeostasis_check_passed"] is True
        assert check_thresholds(vitals, "L4") == []

        # 红线破坏注入 → gate 立刻变红
        conn = sqlite3.connect(p)
        conn.execute(
            "INSERT INTO episodes (id, experience_id, created_at, session_id,"
            " context, goal, decision, action, outcome, source, status, tags)"
            " VALUES ('EPI-BAD', 'EXP-BAD', ?, 'audit', '{}', 'x', 'y', 'z', "
            "'{}', 'audit', 'active', '[\"redline_violation\"]')",
            (now.isoformat(),))
        conn.commit()
        conn.close()
        vitals2 = compute_vitals(p, window_days=7)
        assert vitals2["redline_violation_count"] == 1
        assert check_thresholds(vitals2, "L4")

    def test_cli_vitals_check_exit_codes(self, tmp_path, monkeypatch, capsys):
        """ocos vitals --check: 达标 exit 0 / 红线违规 exit 2。"""
        import sqlite3 as _sq
        p = str(tmp_path / "cli.db")
        conn = _sq.connect(p)
        conn.execute("CREATE TABLE episodes (id TEXT PRIMARY KEY, tags TEXT, "
                     "decision TEXT, created_at TEXT)")
        conn.commit()
        conn.close()
        monkeypatch.setenv("OCOS_DB_PATH", p)
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH",
                           str(tmp_path / "hb.json"))

        from ocos.interaction.cli.commands.vitals import cmd_vitals
        args = type("A", (), {"db": p, "window": 7, "check": True,
                              "phase": "L4"})()
        assert cmd_vitals(args, None) == 0

        # 注入红线违规
        conn = _sq.connect(p)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO episodes (id, tags, decision, created_at) "
            "VALUES ('E1', '[\"redline_violation\"]', '', ?)", (now,))
        conn.commit()
        conn.close()
        assert cmd_vitals(args, None) == 2
