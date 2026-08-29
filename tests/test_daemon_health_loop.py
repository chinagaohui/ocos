"""GAP-P1-2: daemon 稳态健康监控（HealthLoop）测试。

覆盖：
  1. 记忆膨胀超阈 → AlertManager WARNING + FileChannel 落盘（E2E）
  2. interval_ticks 节流门控
  3. fail-closed：采集属性缺失 → 降级 0 不中断、不误报
  4. 真实 ResidentRuntime 集成（attach_health_loop → tick 驱动）
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ocos.alerts.channels import FileChannel
from ocos.alerts.manager import AlertManager
from ocos.alerts.models import AlertLevel
from ocos.capability.homeostasis import HomeostasisManager
from ocos.daemon.health_loop import HealthLoop
from ocos.health_examination.cognitive_examiner import CognitiveExaminer


def _make_fake_runtime(stats: dict, goals: int = 0, wm: int = 0,
                       decisions: list | None = None):
    """伪造 AgentRuntime 采集面（只暴露 HealthLoop 读取的公开属性）。"""
    return SimpleNamespace(
        _memory_hub=SimpleNamespace(get_stats=lambda: dict(stats)),
        agent=SimpleNamespace(goal_stack=list(range(goals))),
        _wm_store=SimpleNamespace(count=lambda: wm),
        _cycle_count=7,
        _last_attention_decisions=decisions or [],
    )


def _make_loop(runtime, interval_ticks: int = 100, alerts_dir=None):
    alerts = AlertManager()
    if alerts_dir is not None:
        alerts.register_channel(FileChannel(str(alerts_dir / "alerts.log")))
    return HealthLoop(
        runtime=runtime,
        examiner=CognitiveExaminer(),
        alerts=alerts,
        homeostasis=HomeostasisManager(),
        interval_ticks=interval_ticks,
    )


class TestHealthLoopDetection:
    def test_interval_gating(self):
        """interval_ticks=3：前 2 次 tick 不体检，第 3 次触发。"""
        rt = _make_fake_runtime({"episode_count": 10, "pattern_count": 2})
        hl = _make_loop(rt, interval_ticks=3)

        assert hl.tick() is None
        assert hl.tick() is None
        assert hl.last_detail == {}  # 尚未触发体检
        hl.tick()
        # 第 3 次触发体检：采集项已填充（首次体检建基线，无异常 → None 是合法语义）
        assert hl.last_detail["episode_count"] == 10
        assert hl._ticks == 0  # 计数已重置

    def test_inflation_detected_and_alerted(self, tmp_path):
        """记忆膨胀超阈（10→50，growth 400% > 200%）→ WARNING + 文件落盘。"""
        stats = {"episode_count": 10, "pattern_count": 2}
        rt = _make_fake_runtime(stats)
        hl = _make_loop(rt, alerts_dir=tmp_path)

        first = hl.run_check()
        assert first is None or first.detected is False  # 基线

        stats["episode_count"] = 50
        finding = hl.run_check()
        assert finding is not None
        assert finding.detected is True
        assert "inflation" in finding.evidence

        # AlertManager 历史
        alerts = hl.alerts._history
        assert any(a.level == AlertLevel.WARNING and a.source == "health_loop"
                   for a in alerts)

        # FileChannel 落盘（每行一个 JSON）
        log_path = tmp_path / "alerts.log"
        assert log_path.exists()
        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        assert any("inflation" in e["message"] and e["source"] == "health_loop"
                   for e in lines)

    def test_decision_failure_rate_collected(self):
        """决策失败率采集：1/3 接受 → 失败率 2/3 ≈ 0.6667。"""
        d1 = SimpleNamespace(is_accepted=True)
        d2 = SimpleNamespace(is_accepted=False)
        d3 = SimpleNamespace(is_accepted=False)
        rt = _make_fake_runtime({"episode_count": 1, "pattern_count": 0},
                                decisions=[d1, d2, d3])
        hl = _make_loop(rt)
        hl.run_check()
        assert hl.last_detail["decision_failure_rate"] == 0.6667
        assert hl.last_detail["wm_usage"] == 0


class TestHealthLoopFailClosed:
    def test_missing_attrs_degrade_to_zero(self):
        """runtime 缺 _memory_hub/_wm_store → 降级 0、不中断、不误报。"""
        rt = SimpleNamespace(agent=SimpleNamespace(goal_stack=[]),
                             _last_attention_decisions=None)
        hl = _make_loop(rt)

        finding = hl.run_check()  # 不应抛异常
        assert finding is None or finding.detected is False
        detail = hl.last_detail
        assert detail["episode_count"] == 0
        assert detail["goal_depth"] == 0
        assert detail["decision_failure_rate"] == 0.0

    def test_bind_after_construction(self):
        """延迟绑定：构造后 bind(runtime) 再体检，采集面指向绑定 runtime。"""
        rt = _make_fake_runtime({"episode_count": 1, "pattern_count": 0})
        hl = _make_loop(None)
        hl.bind(rt)
        hl.run_check()  # 不抛异常（fail-closed）
        assert hl.last_detail["episode_count"] == 1  # 绑定已生效


class TestResidentRuntimeIntegration:
    def test_attach_health_loop_drives_ticks(self):
        """真实 ResidentRuntime：attach_health_loop → start → tick 驱动体检。"""
        from ocos.daemon import ResidentRuntime
        from ocos.daemon.factory import build_master_agent

        agent = build_master_agent("health-test")
        hl = _make_loop(None, interval_ticks=1)
        rt = ResidentRuntime(agent, db_path=":memory:", tick_interval=0.01,
                             max_cycles=100)
        rt.attach_health_loop(hl)

        rt.start()
        try:
            for _ in range(50):
                if hl.last_detail:
                    break
                import time
                time.sleep(0.02)
        finally:
            rt.stop()

        # 体检确已驱动：采集项已填充（至少 goal_depth/episode_count 键存在）
        assert hl.last_detail is not None
        assert set(hl.last_detail) >= {"goal_depth", "wm_usage",
                                       "decision_failure_rate"}
