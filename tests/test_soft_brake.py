"""L0-5: STOP 神经（软制动）测试。

覆盖:
  1. brake/resume 状态切换 + 幂等（重复制动不重复审计）
  2. get_status / 心跳文件暴露 braked + autonomy_level
  3. 制动通知推送 outbox（TUI 可见）
  4. 制动审计: JSONL + episode（R4 审计链）
  5. CLI 端 pid 解析（存活/死亡/缺心跳）
  6. tick 循环制动语义: braked 时跳过 kernel tick，仍消费用户消息
"""
import json
import sqlite3
from unittest.mock import MagicMock

import pytest

from ocos.daemon import ResidentRuntime
from ocos.interaction.cli.commands.stop import resolve_daemon_pid


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("OCOS_HEARTBEAT_PATH",
                       str(tmp_path / "daemon_heartbeat.json"))
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE",
                       str(tmp_path / "autonomy_level"))
    monkeypatch.delenv("OCOS_AUTONOMY_LEVEL", raising=False)
    return tmp_path


@pytest.fixture()
def daemon(isolated):
    db = str(isolated / "ocos.db")
    d = ResidentRuntime(agent=MagicMock(), db_path=db)
    d._user_inbox = MagicMock()
    return d


class TestBrakeState:
    def test_initial_not_braked(self, daemon):
        assert daemon._braked is False
        assert daemon.get_status()["braked"] is False

    def test_brake_sets_flag_and_notifies(self, daemon):
        daemon.brake()
        assert daemon._braked is True
        assert daemon.get_status()["braked"] is True
        # outbox 收到制动通知（用户可见 — 硬约束）
        texts = [str(c.args[0])
                 for c in daemon._user_inbox.post_outbound.call_args_list]
        assert any("制动" in t for t in texts)

    def test_brake_idempotent(self, daemon, isolated):
        daemon.brake()
        daemon.brake()
        audit = isolated / "audit" / "autonomy.jsonl"
        records = [json.loads(l) for l in
                   audit.read_text(encoding="utf-8").splitlines()]
        assert len([r for r in records if r["kind"] == "brake"]) == 1

    def test_resume_restores(self, daemon, isolated):
        daemon.brake()
        daemon.resume()
        assert daemon._braked is False
        records = [json.loads(l) for l in (isolated / "audit" /
                   "autonomy.jsonl").read_text().splitlines()]
        kinds = [(r["kind"], r["braked"]) for r in records
                 if r["kind"] == "brake"]
        assert kinds == [("brake", True), ("brake", False)]

    def test_toggle_brake_roundtrip(self, daemon):
        assert daemon.toggle_brake() is True
        assert daemon.toggle_brake() is False


class TestBrakeAudit:
    def test_brake_writes_episode(self, daemon, isolated):
        # 不预建表 — EpisodeStore.initialize() 自愈建全列 schema
        db = str(isolated / "ocos.db")
        daemon.brake()
        conn = sqlite3.connect(db)
        try:
            row = conn.execute("SELECT tags FROM episodes WHERE "
                               "tags LIKE '%brake%'").fetchone()
        finally:
            conn.close()
        assert row is not None


class TestHeartbeat:
    def test_heartbeat_carries_braked_and_level(self, daemon, isolated):
        daemon._autonomy_level = 2
        daemon.brake()
        daemon._write_heartbeat()
        data = json.loads(
            (isolated / "daemon_heartbeat.json").read_text(encoding="utf-8"))
        assert data["braked"] is True
        assert data["autonomy_level"] == 2
        assert "pid" in data and "ts" in data


class TestTickLoopBrakeSemantics:
    def _run_one_iteration(self, daemon):
        """跑一轮 tick 循环主体后立即退出。"""
        calls = {"kernel": 0, "inbox": 0, "goals": 0}

        daemon._kernel = MagicMock()
        daemon._kernel.tick_loop.side_effect = (
            lambda **kw: calls.__setitem__("kernel", calls["kernel"] + 1))
        daemon._drain_user_inbox = lambda: calls.__setitem__(
            "inbox", calls["inbox"] + 1)
        daemon._drain_goal_queue = lambda: calls.__setitem__(
            "goals", calls["goals"] + 1)
        daemon._claim_persisted_goals = lambda: None
        daemon._push_goal_results = lambda: None
        daemon._run_dream_cycle = lambda: None
        daemon._write_heartbeat = lambda: None
        daemon._health_loop = None
        daemon._perception_pipeline = None

        real_sleep = __import__("time").sleep

        def _stop_after_first(_s):
            daemon._stop_event.set()

        import ocos.daemon as daemon_mod
        orig_sleep = daemon_mod.time.sleep
        daemon_mod.time.sleep = _stop_after_first
        try:
            daemon._tick_loop()
        finally:
            daemon_mod.time.sleep = orig_sleep
        return calls

    def test_normal_tick_drives_kernel(self, daemon):
        calls = self._run_one_iteration(daemon)
        assert calls["kernel"] == 1
        assert calls["inbox"] == 1

    def test_braked_tick_skips_kernel_keeps_inbox(self, daemon):
        daemon.brake()
        calls = self._run_one_iteration(daemon)
        # 制动: 认知 tick 停、目标导入停 — 对话仍答（R 软制动判据）
        assert calls["kernel"] == 0
        assert calls["goals"] == 0
        assert calls["inbox"] == 1

    def test_level_zero_blocks_autonomous_proposals(self, daemon, isolated):
        """R3 红线: LEVEL=0 时自主提案路径不触发。"""
        (isolated / "autonomy_level").write_text("0", encoding="utf-8")
        active = MagicMock()
        daemon._active_interaction = active
        daemon._autonomy_level = 1  # 模拟运行中尚未检测到切换
        agent_obj = MagicMock()
        daemon._runtime = MagicMock()
        daemon._runtime.agent = agent_obj
        daemon._kernel = MagicMock()
        daemon._drain_user_inbox = lambda: None
        daemon._drain_goal_queue = lambda: None
        daemon._claim_persisted_goals = lambda: None
        daemon._push_goal_results = lambda: None
        daemon._run_dream_cycle = lambda: None
        daemon._write_heartbeat = lambda: None
        daemon._health_loop = None
        daemon._perception_pipeline = None
        daemon._self_monitor_eligible = False
        import ocos.daemon as daemon_mod
        daemon._hb_ticks = 60  # 命中 60-tick 主动交互窗口
        orig_sleep = daemon_mod.time.sleep
        daemon_mod.time.sleep = lambda _s: daemon._stop_event.set()
        try:
            daemon._tick_loop()
        finally:
            daemon_mod.time.sleep = orig_sleep
        # 切换检测: level 1 → 0（override 文件生效），主动提案零调用
        assert daemon._autonomy_level == 0
        assert active.scan_and_interact.call_count == 0
        assert agent_obj.maybe_proactive_output.call_count == 0


class TestResolvePid:
    def test_pid_from_alive_process(self, isolated, monkeypatch):
        hb = isolated / "daemon_heartbeat.json"
        hb.write_text(json.dumps({"pid": __import__("os").getpid()}))
        assert resolve_daemon_pid(hb) == __import__("os").getpid()

    def test_dead_process_returns_none(self, isolated):
        hb = isolated / "daemon_heartbeat.json"
        hb.write_text(json.dumps({"pid": 999999999}))
        assert resolve_daemon_pid(hb) is None

    def test_missing_heartbeat_returns_none(self, isolated):
        assert resolve_daemon_pid(isolated / "nope.json") is None

    def test_garbage_heartbeat_returns_none(self, isolated):
        hb = isolated / "daemon_heartbeat.json"
        hb.write_text("not json")
        assert resolve_daemon_pid(hb) is None
