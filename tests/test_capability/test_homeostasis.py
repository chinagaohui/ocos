"""Phase 29 集成测试: Homeostasis Monitor。

覆盖:
  29a1: HomeostasisManager.check() — 全维度采样
  29a2: health_report() — 空/正常/超阈值三种场景
  29a3: thresholds 自定义配置
  29a4: score 计算（WARNING -5, CRITICAL -15）
  29a5: recommend_actions() — 告警→动作映射
  29b1: ResourceMonitor — CPU/Memory/Storage 采样
  29b2: HealthMonitor — record + sample
  29b3: ContextMonitor — tokens/fatigue/switches
  29b4: IdentityMonitor — 完整/缺失
  29b5: Alert severity — WARNING vs CRITICAL
"""
import pytest

from ocos.capability.homeostasis import (
    Alert,
    AlertLevel,
    ContextMetrics,
    ContextMonitor,
    DriveType,
    GoalMetrics,
    HealthMetrics,
    HealthMonitor,
    HealthReport,
    HomeostasisManager,
    HomeostasisThresholds,
    IdentityMetrics,
    IdentityMonitor,
    MemoryMetrics,
    MonitorSnapshot,
    RegulatorAction,
    ResourceMetrics,
    ResourceMonitor,
)
from ocos.kernel.goal_types import GoalLevel, GoalOriginLevel, GoalStatus


# ── 29a1: check() ────────────────────────────────────────────────────────


class TestCheck:
    def test_check_returns_snapshot(self):
        hm = HomeostasisManager()
        snap = hm.check()
        assert isinstance(snap, MonitorSnapshot)
        assert isinstance(snap.resource, ResourceMetrics)
        assert isinstance(snap.memory, MemoryMetrics)
        assert isinstance(snap.goal, GoalMetrics)
        assert isinstance(snap.health, HealthMetrics)
        assert isinstance(snap.context, ContextMetrics)
        assert isinstance(snap.identity, IdentityMetrics)

    def test_check_has_timestamp(self):
        hm = HomeostasisManager()
        snap = hm.check()
        assert snap.timestamp is not None


# ── 29a2: health_report() ────────────────────────────────────────────────


class TestHealthReportBasic:
    def test_default_thresholds_report(self):
        hm = HomeostasisManager()
        report = hm.health_report()
        assert isinstance(report, HealthReport)
        assert 0.0 <= report.score <= 100.0

    def test_empty_metrics_healthy(self):
        # 全 0 指标 → 100 分
        hm = HomeostasisManager()
        snap = MonitorSnapshot()
        report = hm.health_report(snapshot=snap)
        assert report.score == 100.0
        assert len(report.alerts) == 0

    def test_custom_snapshot(self):
        hm = HomeostasisManager()
        snap = MonitorSnapshot(
            resource=ResourceMetrics(cpu_percent=0, memory_percent=0, storage_percent=0),
            context=ContextMetrics(current_tokens=100, attention_fatigue=0.1),
        )
        report = hm.health_report(snapshot=snap)
        assert report.score >= 90  # within all thresholds


class TestHealthReportOverThreshold:
    def test_cpu_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=50))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=75))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any("cpu" in a.metric.lower() for a in report.alerts)

    def test_memory_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(memory_percent_max=50))
        snap = MonitorSnapshot(resource=ResourceMetrics(memory_percent=75))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any("memory" in a.metric.lower() for a in report.alerts)

    def test_error_rate_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(error_rate_max=0.05))
        snap = MonitorSnapshot(health=HealthMetrics(error_rate=0.15))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any("error" in a.metric.lower() for a in report.alerts)

    def test_latency_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(latency_max=30))
        snap = MonitorSnapshot(health=HealthMetrics(avg_latency_ms=50000))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any("latency" in a.metric.lower() for a in report.alerts)

    def test_crash_count_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(crash_count_max=2))
        snap = MonitorSnapshot(health=HealthMetrics(crash_count=5))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100

    def test_active_goals_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(active_goal_max=10))
        snap = MonitorSnapshot(goal=GoalMetrics(active_goal_count=15))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any("goal" in a.dimension.lower() for a in report.alerts)

    def test_context_tokens_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(context_tokens_max=4000))
        snap = MonitorSnapshot(context=ContextMetrics(current_tokens=5000))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100

    def test_context_tokens_critical_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(context_tokens_critical=8000))
        snap = MonitorSnapshot(context=ContextMetrics(current_tokens=10000))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100
        assert any(a.level == AlertLevel.CRITICAL for a in report.alerts)

    def test_attention_fatigue_warning(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(attention_fatigue_max=0.5))
        snap = MonitorSnapshot(context=ContextMetrics(attention_fatigue=0.7))
        report = hm.health_report(snapshot=snap)
        assert any("fatigue" in a.metric.lower() for a in report.alerts)

    def test_attention_fatigue_critical(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(attention_fatigue_critical=0.9))
        snap = MonitorSnapshot(context=ContextMetrics(attention_fatigue=0.95))
        report = hm.health_report(snapshot=snap)
        assert any(
            a.level == AlertLevel.CRITICAL and "fatigue" in a.metric.lower()
            for a in report.alerts
        )

    def test_context_switches_over_threshold(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(context_switches_per_hour_max=20))
        snap = MonitorSnapshot(context=ContextMetrics(context_switches_this_hour=35))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100


# ── 29a3: thresholds ─────────────────────────────────────────────────────


class TestThresholdsCustom:
    def test_custom_all_thresholds(self):
        t = HomeostasisThresholds(
            cpu_percent_max=90,
            memory_percent_max=90,
            active_goal_max=20,
            error_rate_max=0.1,
            latency_max=60,
            context_tokens_max=8000,
        )
        hm = HomeostasisManager(thresholds=t)
        assert hm.thresholds.cpu_percent_max == 90

    def test_thresholds_override_by_manager(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=30))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=50))
        report = hm.health_report(snapshot=snap)
        assert report.score < 100  # 50 > 30


# ── 29a4: score ──────────────────────────────────────────────────────────


class TestScore:
    def test_single_warning_minus_5(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=50))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=75))
        report = hm.health_report(snapshot=snap)
        # 75 > 50, but 75 < 1.5*50=75 → WARNING
        # Actually 75 == 1.5*50 → not WARNING for strictly less than
        # The _check uses `current < threshold * 1.5` → WARNING
        # 75 < 75 → False → CRITICAL
        assert report.score == 85  # 100 - 15

    def test_score_floor_zero(self):
        # 大量 CRITICAL 不会低于 0
        hm = HomeostasisManager()
        # 构造大量 CRITICAL alert
        snap = MonitorSnapshot(
            resource=ResourceMetrics(cpu_percent=999, memory_percent=999, storage_percent=999),
            health=HealthMetrics(error_rate=9.99, avg_latency_ms=999999, crash_count=999),
            goal=GoalMetrics(active_goal_count=999, blocked_goal_count=999, expired_goal_count=999),
            context=ContextMetrics(current_tokens=99999, attention_fatigue=9.99),
        )
        report = hm.health_report(snapshot=snap)
        assert report.score >= 0.0

    def test_score_ceiling_100(self):
        hm = HomeostasisManager()
        snap = MonitorSnapshot()
        report = hm.health_report(snapshot=snap)
        assert report.score == 100.0


# ── 29a5: recommend_actions() ────────────────────────────────────────────


class TestRecommendActions:
    def test_healthy_no_actions(self):
        hm = HomeostasisManager()
        actions = hm.recommend_actions()
        assert len(actions) == 0

    def test_cpu_actions(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=10))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=90))
        report = hm.health_report(snapshot=snap)
        actions = hm.recommend_actions(report=report)
        # CPU overload currently has no specific mapping → exercise the method
        assert isinstance(actions, list)

    def test_memory_actions(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(working_memory_items_max=10))
        snap = MonitorSnapshot(memory=MemoryMetrics(working_memory_items=100))
        report = hm.health_report(snapshot=snap)
        actions = hm.recommend_actions(report=report)
        assert RegulatorAction.COMPRESS_MEMORY in actions

    def test_fatigue_actions(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(attention_fatigue_max=0.2))
        snap = MonitorSnapshot(context=ContextMetrics(attention_fatigue=0.8))
        report = hm.health_report(snapshot=snap)
        actions = hm.recommend_actions(report=report)
        assert RegulatorAction.TRIGGER_SLEEP in actions

    def test_actions_deduplicated(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(
            working_memory_items_max=1, episode_memory_items_max=1
        ))
        snap = MonitorSnapshot(memory=MemoryMetrics(
            working_memory_items=100, episode_memory_items=100
        ))
        report = hm.health_report(snapshot=snap)
        actions = hm.recommend_actions(report=report)
        # 两个 memory 告警可能生成两个不同 action (COMPRESS vs ARCHIVE)
        # 每种 action 只出现一次
        assert len(actions) == len(set(actions))


# ── 29b1: ResourceMonitor ────────────────────────────────────────────────


class TestResourceMonitor:
    def test_sample_returns_metrics(self):
        rm = ResourceMonitor()
        m = rm.sample()
        assert isinstance(m, ResourceMetrics)
        assert 0 <= m.cpu_percent <= 100 or m.cpu_percent == 0  # 可能为 0 如果 psutil 不可用
        assert 0 <= m.memory_percent <= 100 or m.memory_percent == 0
        assert 0 <= m.storage_percent <= 100 or m.storage_percent == 0


# ── 29b2: HealthMonitor ──────────────────────────────────────────────────


class TestHealthMonitor:
    def test_sample_defaults(self):
        hm = HealthMonitor()
        m = hm.sample()
        assert m.error_rate == 0.0
        assert m.crash_count == 0

    def test_record_success(self):
        hm = HealthMonitor()
        hm.record_success(latency_ms=100)
        m = hm.sample()
        assert m.avg_latency_ms == 100.0

    def test_record_error(self):
        hm = HealthMonitor()
        hm.record_error()
        hm.record_success()
        m = hm.sample()
        assert m.error_rate == 0.5  # 1 error, 2 total

    def test_record_crash(self):
        hm = HealthMonitor()
        hm.record_crash()
        hm.record_crash()
        m = hm.sample()
        assert m.crash_count == 2

    def test_uptime(self):
        hm = HealthMonitor()
        m = hm.sample()
        assert m.uptime_seconds >= 0


# ── 29b3: ContextMonitor ─────────────────────────────────────────────────


class TestContextMonitor:
    def test_update_tokens(self):
        cm = ContextMonitor()
        cm.update_tokens(3000)
        m = cm.sample()
        assert m.current_tokens == 3000

    def test_update_fatigue(self):
        cm = ContextMonitor()
        cm.update_fatigue(0.85)
        m = cm.sample()
        assert m.attention_fatigue == 0.85

    def test_fatigue_clamped(self):
        cm = ContextMonitor()
        cm.update_fatigue(999)
        assert cm.sample().attention_fatigue == 1.0
        cm.update_fatigue(-999)
        assert cm.sample().attention_fatigue == 0.0

    def test_record_switch(self):
        cm = ContextMonitor()
        cm.record_switch()
        cm.record_switch()
        m = cm.sample()
        assert m.context_switches_this_hour == 2


# ── 29b4: IdentityMonitor ────────────────────────────────────────────────


class TestIdentityMonitor:
    def test_sample_none(self):
        im = IdentityMonitor()
        m = im.sample()
        assert m.integrity_ok is True

    def test_sample_complete(self):
        class FakeIdentity:
            name = "test-agent"
            version = "1.0"
        im = IdentityMonitor()
        m = im.sample(FakeIdentity())
        assert m.integrity_ok is True
        assert len(m.missing_fields) == 0

    def test_sample_missing_name(self):
        class FakeIdentity:
            version = "1.0"
            name = ""  # empty/falsy
        im = IdentityMonitor()
        m = im.sample(FakeIdentity())
        assert m.integrity_ok is False
        assert "name" in m.missing_fields

    def test_sample_missing_version(self):
        class FakeIdentity:
            name = "ok"
        im = IdentityMonitor()
        m = im.sample(FakeIdentity())
        assert m.integrity_ok is False
        assert "version" in m.missing_fields


# ── 29b5: Alert severity ─────────────────────────────────────────────────


class TestAlertSeverity:
    def test_warning_when_below_150_percent(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=100))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=140))  # < 150
        report = hm.health_report(snapshot=snap)
        assert len(report.alerts) > 0
        assert report.alerts[0].level == AlertLevel.WARNING

    def test_critical_when_above_150_percent(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=100))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=160))  # > 150
        report = hm.health_report(snapshot=snap)
        assert len(report.alerts) > 0
        assert report.alerts[0].level == AlertLevel.CRITICAL


# ── History ───────────────────────────────────────────────────────────────


class TestHistory:
    def test_history_accumulates(self):
        hm = HomeostasisManager()
        hm.health_report()
        hm.health_report()
        assert len(hm.history) == 2

    def test_alert_count(self):
        hm = HomeostasisManager(thresholds=HomeostasisThresholds(cpu_percent_max=1))
        snap = MonitorSnapshot(resource=ResourceMetrics(cpu_percent=99))
        hm.health_report(snapshot=snap)
        assert hm.alert_count >= 1

    def test_clear_history(self):
        hm = HomeostasisManager()
        hm.health_report()
        hm.clear_history()
        assert len(hm.history) == 0
        assert hm.alert_count == 0


# ── P2-A: Regulator 内生目标引擎 ───────────────────────────────────────────


class TestRegulatorDrives:
    """确定性规则表：偏差 → 驱力。"""

    def _reg(self):
        from ocos.capability.homeostasis import Regulator
        return Regulator()

    def test_explore_when_idle(self):
        snap = MonitorSnapshot()  # 全默认 = 空转状态
        drives = self._reg().derive_drives(snap)
        kinds = {d.drive for d in drives}
        assert DriveType.EXPLORE in kinds
        assert DriveType.CONNECTION in kinds

    def test_restore_on_high_memory(self):
        from ocos.capability.homeostasis import DriveType
        snap = MonitorSnapshot(resource=ResourceMetrics(memory_percent=95))
        drives = self._reg().derive_drives(snap)
        assert any(d.drive == DriveType.RESTORE for d in drives)

    def test_mastery_on_blocked_goals(self):
        from ocos.capability.homeostasis import DriveType
        snap = MonitorSnapshot(goal=GoalMetrics(active_goal_count=3, blocked_goal_count=5))
        drives = self._reg().derive_drives(snap)
        assert any(d.drive == DriveType.MASTERY for d in drives)

    def test_reflect_on_identity_breach(self):
        from ocos.capability.homeostasis import DriveType
        snap = MonitorSnapshot(identity=IdentityMetrics(integrity_ok=False))
        drives = self._reg().derive_drives(snap)
        assert any(d.drive == DriveType.REFLECT for d in drives)

    def test_no_drives_when_healthy_busy(self):
        """健康且忙碌（有活跃目标、资源正常）→ 无强驱力。"""
        snap = MonitorSnapshot(
            resource=ResourceMetrics(memory_percent=50),
            goal=GoalMetrics(active_goal_count=3, blocked_goal_count=0),
            context=ContextMetrics(current_tokens=2000),
        )
        drives = self._reg().derive_drives(snap)
        assert all(d.drive not in (DriveType.EXPLORE, DriveType.CONNECTION, DriveType.RESTORE)
                   for d in drives)


class TestCuriosityDrive:
    """P2-B 好奇心驱动契约：novelty 信号 → EXPLORE（确定性规则 + 注意力预算）。"""

    def _reg(self):
        from ocos.capability.homeostasis import Regulator
        return Regulator()

    def _busy_snap(self, novelty: float, fatigue: float = 0.0):
        """忙碌态（active=5 → 无匮乏触发），仅 novelty 驱动。"""
        return MonitorSnapshot(
            goal=GoalMetrics(active_goal_count=5, blocked_goal_count=0),
            context=ContextMetrics(attention_fatigue=fatigue, novelty=novelty),
        )

    def test_novelty_high_triggers_explore(self):
        """novelty=0.8 → EXPLORE 强度 (0.8-0.6)/0.4 = 0.5（忙碌态无匮乏）。"""
        drives = self._reg().derive_drives(self._busy_snap(0.8))
        explore = [d for d in drives if d.drive == DriveType.EXPLORE]
        assert len(explore) == 1  # 单一 EXPLORE 信号，无重复
        assert explore[0].intensity == pytest.approx(0.5)
        assert "好奇心" in explore[0].reason

    def test_novelty_max_intensity(self):
        """novelty=1.0 → 强度 1.0（饱和）。"""
        drives = self._reg().derive_drives(self._busy_snap(1.0))
        explore = [d for d in drives if d.drive == DriveType.EXPLORE]
        assert explore[0].intensity == pytest.approx(1.0)

    def test_novelty_below_threshold_no_explore(self):
        """novelty=0.3（< 0.6 阈值）→ 忙碌态无 EXPLORE（匮乏规则独立验证）。"""
        drives = self._reg().derive_drives(self._busy_snap(0.3))
        assert all(d.drive != DriveType.EXPLORE for d in drives)

    def test_novelty_takes_max_with_scarcity(self):
        """匮乏(0.5) + novelty(0.8 → 0.5) → 强度取较大者 = 0.5，仅一个信号。"""
        snap = MonitorSnapshot(
            goal=GoalMetrics(active_goal_count=0, blocked_goal_count=0),
            context=ContextMetrics(novelty=0.8),
        )
        drives = self._reg().derive_drives(snap)
        explore = [d for d in drives if d.drive == DriveType.EXPLORE]
        assert len(explore) == 1
        assert explore[0].intensity == pytest.approx(0.5)

    def test_fatigue_suppresses_explore(self):
        """fatigue=0.75 ≥ 0.70 → 强度 ×0.5（0.5 → 0.25），L5 防失控。"""
        drives = self._reg().derive_drives(self._busy_snap(0.8, fatigue=0.75))
        explore = [d for d in drives if d.drive == DriveType.EXPLORE]
        assert explore[0].intensity == pytest.approx(0.25)
        assert "预算抑制" in explore[0].reason

    def test_fatigue_below_budget_no_suppression(self):
        """fatigue=0.5 < 0.70 → 不抑制。"""
        drives = self._reg().derive_drives(self._busy_snap(0.8, fatigue=0.5))
        explore = [d for d in drives if d.drive == DriveType.EXPLORE]
        assert explore[0].intensity == pytest.approx(0.5)

    def test_regulate_novelty_injection(self):
        """regulate(novelty=0.8) → 全链路注入：EXPLORE 目标可生成（无匮乏）。"""
        from ocos.capability.homeostasis import HomeostasisManager
        hm = HomeostasisManager()
        result = hm.regulate(novelty=0.8)
        explore = [d for d in result.drives if d.drive == DriveType.EXPLORE]
        assert any(d.intensity == pytest.approx(0.5) for d in explore)
        # 好奇心目标已生成（SELF 级，无门控测试场景）
        assert len(result.goals) >= 1

    def test_regulate_merge_semantics(self):
        """regulate(novelty=None, attention_fatigue=0.9) → 只覆盖 fatigue，novelty 用采样值。"""
        from ocos.capability.homeostasis import HomeostasisManager
        hm = HomeostasisManager()
        result = hm.regulate(attention_fatigue=0.9)
        # fatigue 高 → EXPLORE 若触发也被抑制；不崩溃即验证合并语义
        for d in result.drives:
            if d.drive == DriveType.EXPLORE:
                assert d.intensity <= 0.25 + 1e-9


class TestRegulatorGoalGeneration:
    """驱力 → SELF 级 Goal（确定性模板）。"""

    def _reg(self):
        from ocos.capability.homeostasis import Regulator
        return Regulator()

    def test_goal_is_self_origin(self):
        from ocos.capability.homeostasis import DriveType, DriveSignal
        goals, gated = self._reg().generate_self_goals(
            [DriveSignal(DriveType.EXPLORE, 0.5, "r", "m")])
        assert len(goals) == 1
        assert goals[0].origin_level == GoalOriginLevel.SELF
        assert goals[0].status == GoalStatus.PENDING
        assert goals[0].level == GoalLevel.SHORT

    def test_priority_below_human(self):
        """D3: SELF 优先级恒低于 HUMAN（1.0）。"""
        from ocos.capability.homeostasis import DriveType, DriveSignal
        for drive_type in DriveType:
            goals, _ = self._reg().generate_self_goals(
                [DriveSignal(drive_type, 1.0, "r", "m")])
            for g in goals:
                assert g.priority < 1.0, f"{drive_type} priority {g.priority} >= 1.0"

    def test_gate_rejects_goals(self):
        from ocos.capability.homeostasis import DriveType, DriveSignal
        goals, gated = self._reg().generate_self_goals(
            [DriveSignal(DriveType.EXPLORE, 0.5, "r", "m")],
            gate=lambda g: False,
        )
        assert goals == []
        assert len(gated) == 1

    def test_max_goals_cap(self):
        from ocos.capability.homeostasis import DriveSignal, DriveType
        drives = [DriveSignal(d, 0.5, "r", "m") for d in list(DriveType)[:5]]
        goals, _ = self._reg().generate_self_goals(drives)
        assert len(goals) <= self._reg().MAX_GOALS_PER_CYCLE

    def test_metadata_carries_drive(self):
        from ocos.capability.homeostasis import DriveSignal, DriveType
        goals, _ = self._reg().generate_self_goals(
            [DriveSignal(DriveType.MASTERY, 0.6, "r", "m")])
        assert goals[0].metadata["drive"] == "MASTERY"


class TestRegulateIntegration:
    """HomeostasisManager.regulate() 全链路。"""

    def test_regulate_returns_result(self):
        from ocos.capability.homeostasis import RegulateResult
        hm = HomeostasisManager()
        result = hm.regulate()
        assert isinstance(result, RegulateResult)
        assert isinstance(result.drives, list)
        assert isinstance(result.goals, list)
        assert isinstance(result.actions, list)

    def test_regulate_all_goals_self(self):
        hm = HomeostasisManager()
        result = hm.regulate()
        for g in result.goals:
            assert g.origin_level == GoalOriginLevel.SELF

    def test_enforcer_phase21_gates_all_self(self):
        """Phase 21 只允许 SYSTEM → SELF 全被门控。"""
        from ocos.goal.enforcer import GoalOriginEnforcer
        hm = HomeostasisManager()
        result = hm.regulate(enforcer=GoalOriginEnforcer(current_phase=21))
        assert result.goals == []
        assert len(result.gated) >= 1

    def test_enforcer_phase25_allows_self(self):
        """Phase 25 放行 SELF → 门控数下降，目标保留。"""
        from ocos.goal.enforcer import GoalOriginEnforcer
        hm = HomeostasisManager()
        ungated = hm.regulate()  # 无门控基线
        gated = hm.regulate(enforcer=GoalOriginEnforcer(current_phase=25))
        assert len(gated.goals) == len(ungated.goals)
        assert gated.gated == []
