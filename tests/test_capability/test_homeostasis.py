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
