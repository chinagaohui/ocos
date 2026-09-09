"""Phase B 自进化指标回归测试。

覆盖 _self_evolution_metrics 的 5 项指标计算、诚实降级、Lesson 排除。
episodes schema 由 EpisodeStore.initialize() 创建（与生产一致）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ocos.memory.episode.store import EpisodeStore
from ocos.monitoring.vitals import compute_vitals


# ── Fixture: 造一个隔离的 test db ────────────────────────────────


def _make_db(tmp_path, monkeypatch):
    p = str(tmp_path / "test_se.db")
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(tmp_path / "hb.json"))
    estore = EpisodeStore(db_path=p)
    estore.initialize()
    return p


def _ins(ep_id, db_path, source, days_ago, outcome_ok,
         action="task_action", decision="decision", tags="[]"):
    """向 episodes 表插入一行（简化参数）。"""
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)
    created_at = (now - timedelta(days=days_ago, hours=1)).isoformat()
    conn.execute(
        "INSERT INTO episodes "
        "(id, experience_id, created_at, session_id, context, goal, "
        " decision, action, outcome, source, status, tags) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (ep_id, f"EXP-{ep_id}", created_at, "test", "{}", "goal",
         decision, action, json.dumps({"success": outcome_ok}),
         source, "active", tags))
    conn.commit()
    conn.close()


# ── 测试组 1: 空 DB 诚实降级 ─────────────────────────────────────


class TestEmptyDB:
    def test_all_metrics_none_on_missing_db(self, tmp_path, monkeypatch):
        """DB 文件不存在 → conn=None → 聚合器全部跳过 → 诚实降级。"""
        p = str(tmp_path / "nope.db")
        v = compute_vitals(p)
        # key 不存在（conn=None 时跳过所有聚合器）是正确行为
        # 但 c_lesson_count_7d 和 missing 应该存在（vitals 初始值）
        assert "db:" in str(v.get("missing", ""))

    def test_all_metrics_are_none_on_no_episodes(self, tmp_path, monkeypatch):
        p = _make_db(tmp_path, monkeypatch)
        v = compute_vitals(p)
        assert v["failure_rate_trend_delta"] is None
        assert v["tool_utilization_rate"] is None
        assert v["c_lesson_production_per_day"] is None
        assert v["lesson_injection_intensity"] is None


# ── 测试组 2: failure_rate_trend_delta 正确计算 ─────────────────


class TestFailureRateTrend:
    def test_delta_positive_when_success_rate_improves(self, tmp_path, monkeypatch):
        """前 7d 60% success → 近 7d 90% success → delta = +0.30。"""
        p = _make_db(tmp_path, monkeypatch)
        old_days = [12, 12, 11, 11, 10, 10, 9, 9, 8, 8]
        new_days = [5, 5, 4, 4, 3, 3, 2, 2, 1, 0]
        for i, d in enumerate(old_days):
            _ins(f"OLD{i}", p, "task", d, outcome_ok=(i < 6))
        for i, d in enumerate(new_days):
            _ins(f"NEW{i}", p, "task", d, outcome_ok=(i < 9))
        v = compute_vitals(p)
        assert v["failure_rate_trend_delta"] == pytest.approx(0.30, abs=0.001)
        assert v["recent_7d_success_rate"] == pytest.approx(0.90, abs=0.001)
        assert v["prev_7d_success_rate"] == pytest.approx(0.60, abs=0.001)

    def test_lesson_episodes_excluded_from_failure_trend(self, tmp_path, monkeypatch):
        """Lesson episodes 不计入任务成功率趋势。"""
        p = _make_db(tmp_path, monkeypatch)
        old_days = [12, 12, 11, 11, 10, 10, 9, 9, 8, 8]
        new_days = [5, 5, 4, 4, 3, 3, 2, 2, 1, 0]
        for i, d in enumerate(old_days):
            _ins(f"OLD{i}", p, "task", d, outcome_ok=(i < 6))
        for i, d in enumerate(new_days):
            _ins(f"NEW{i}", p, "task", d, outcome_ok=(i < 9))
        # 额外插 2 条 Lesson（都 success）— 不应影响 delta
        _ins("L1", p, "lesson", 3, True, action="synthesize",
             decision="【超时规避程序】")
        _ins("L2", p, "lesson", 4, True, action="synthesize",
             decision="别跑太多命令")
        v = compute_vitals(p)
        # delta 仍然是 0.30（Lesson 排除）
        assert v["failure_rate_trend_delta"] == pytest.approx(0.30, abs=0.001)

    def test_delta_none_when_insufficient_data(self, tmp_path, monkeypatch):
        """< 5 条 / 窗口 → delta = None（诚实降级）。"""
        p = _make_db(tmp_path, monkeypatch)
        for i, d in enumerate([12, 11, 10, 9]):  # 前 7d 只有 4 条
            _ins(f"OLD{i}", p, "task", d, outcome_ok=True)
        for i, d in enumerate([5, 4, 3, 2]):    # 近 7d 只有 4 条
            _ins(f"NEW{i}", p, "task", d, outcome_ok=True)
        v = compute_vitals(p)
        assert v["failure_rate_trend_delta"] is None


# ── 测试组 3: 工具利用率 ────────────────────────────────────────


class TestToolUtilization:
    def test_tool_util_rate_correct(self, tmp_path, monkeypatch):
        """20 条工具类 action（15 success）→ tool_utilization_rate = 0.75。"""
        p = _make_db(tmp_path, monkeypatch)
        tool_actions = ["fs_read", "shell", "read_file", "run_command",
                        "write_file", "edit_file", "search_files", "bash"]
        # 插 20 条工具类，其中 15 success
        for i in range(20):
            _ins(f"TOOL{i}", p, "task", days_ago=i // 4,
                 outcome_ok=(i < 15),
                 action=tool_actions[i % len(tool_actions)])
        # 插 3 条非工具类（不应计入）
        for i, act in enumerate(["reflect", "summarize", "think"]):
            _ins(f"NT{i}", p, "task", days_ago=1, outcome_ok=True, action=act)
        v = compute_vitals(p)
        assert v["tool_utilization_rate"] == pytest.approx(0.75, abs=0.001)
        assert v["tool_action_total_30d"] == 20
        assert v["tool_action_success_30d"] == 15

    def test_tool_util_none_when_few(self, tmp_path, monkeypatch):
        p = _make_db(tmp_path, monkeypatch)
        for i in range(4):
            _ins(f"TOOL{i}", p, "task", days_ago=i, outcome_ok=True,
                 action="fs_read")
        v = compute_vitals(p)
        assert v["tool_utilization_rate"] is None
        assert v["tool_action_total_30d"] == 4


# ── 测试组 4: C 类 Lesson 产出率 ────────────────────────────────


class TestCLessonProduction:
    def test_c_lesson_detected(self, tmp_path, monkeypatch):
        """decision 含 '【' 即 C 类 Lesson。"""
        p = _make_db(tmp_path, monkeypatch)
        _ins("LC1", p, "lesson", 3, True, action="synthesize",
             decision="【超时规避程序】先检查；分批；等完成。"
                      "禁止单次执行过多。成功=不超时")
        _ins("LB1", p, "lesson", 4, True, action="synthesize",
             decision="别一次性执行太多命令")  # B 类，不含【
        _ins("LB2", p, "lesson", 5, True, action="synthesize",
             decision="注意检查边界条件")      # B 类
        v = compute_vitals(p)
        assert v["c_lesson_count_7d"] == 1
        assert v["c_lesson_production_per_day"] == pytest.approx(
            1 / 7, abs=0.01)

    def test_c_lesson_zero_when_no_lessons(self, tmp_path, monkeypatch):
        p = _make_db(tmp_path, monkeypatch)
        for i in range(10):
            _ins(f"NEW{i}", p, "task", days_ago=i, outcome_ok=True)
        v = compute_vitals(p)
        assert v["c_lesson_count_7d"] == 0
        assert v["c_lesson_production_per_day"] is None
