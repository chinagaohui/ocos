"""Phase 53: Active Interaction System — Tests.

验证:
    IS53-01: Active Reminder ≠ Active Decision
    IS53-02: Active Output ≠ Autonomous Goal
    IS53-03: Validation Before Send
    IS53-04: Rate Limiting
"""

import time
import pytest

from ocos.interaction.interaction_types import (
    InteractionPriority, InteractionStatus, InteractionMode, NeedType,
    NeedSignal, InteractionCandidate, InteractionConfig, InteractionHistory,
)
from ocos.interaction.need_monitor import (
    GoalHealth, NeedRule, NeedMonitor, create_default_rules,
)
from ocos.interaction.attention_trigger import AttentionTrigger
from ocos.interaction.interaction_scheduler import InteractionScheduler
from ocos.interaction.interaction_validator import (
    InteractionValidator, SendValidationResult, ValidationVerdict,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Types
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypes:
    def test_need_signal(self):
        ns = NeedSignal(
            need_type=NeedType.GOAL_STALE,
            source="goal-1",
            description="目标停滞",
            urgency=0.5,
        )
        assert ns.need_type == NeedType.GOAL_STALE
        assert not ns.is_urgent

    def test_need_signal_urgent(self):
        ns = NeedSignal(need_type=NeedType.ANOMALY_DETECTED, urgency=0.9)
        assert ns.is_urgent

    def test_interaction_candidate_lifecycle(self):
        ic = InteractionCandidate(
            id="test-1",
            mode=InteractionMode.REMINDER,
            priority=InteractionPriority.MEDIUM,
            title="测试提醒",
            body="这是一个测试提醒",
        )
        assert ic.status == InteractionStatus.DRAFT

        ic.mark_sent()
        assert ic.status == InteractionStatus.SENT

        ic.acknowledge("好的")
        assert ic.status == InteractionStatus.ACKNOWLEDGED
        assert ic.user_response == "好的"

    def test_interaction_candidate_ignore(self):
        ic = InteractionCandidate(id="test-2")
        ic.ignore()
        assert ic.status == InteractionStatus.IGNORED

    def test_interaction_candidate_withdraw(self):
        ic = InteractionCandidate(id="test-3")
        ic.withdraw("不再需要")
        assert ic.status == InteractionStatus.WITHDRAWN

    def test_interaction_candidate_expiry(self):
        ic = InteractionCandidate(
            id="test-4",
            expires_at=time.time() - 1,  # 1秒前过期
        )
        assert ic.is_expired()

    def test_interaction_history(self):
        h = InteractionHistory(total_sent=10, total_acknowledged=7, total_ignored=3)
        assert h.acknowledge_rate == 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# 2. NeedMonitor
# ═══════════════════════════════════════════════════════════════════════════════


class TestNeedMonitor:
    def test_goal_stale_detection(self):
        monitor = NeedMonitor()
        # 为规则注册默认规则
        for rule in create_default_rules():
            monitor.register_rule(rule)

        # 添加一个停滞目标
        monitor.update_goal_health("goal-1", "股票分析", 35)

        signals = monitor.scan()
        assert len(signals) >= 1
        assert signals[0].need_type == NeedType.GOAL_STALE
        assert "股票分析" in signals[0].description

    def test_goal_not_stale(self):
        monitor = NeedMonitor()
        for rule in create_default_rules():
            monitor.register_rule(rule)

        monitor.update_goal_health("goal-1", "股票分析", 5)  # 5天不触发

        signals = monitor.scan()
        assert len(signals) == 0

    def test_health_warning(self):
        monitor = NeedMonitor()
        for rule in create_default_rules():
            monitor.register_rule(rule)

        monitor.update_system_health("memory", 0.2)  # 健康度很低

        signals = monitor.scan()
        assert any(s.need_type == NeedType.HEALTH_WARNING for s in signals)

    def test_custom_rule(self):
        monitor = NeedMonitor()
        triggered = []

        def custom_check(m, ctx):
            triggered.append(True)
            return NeedSignal(need_type=NeedType.PATTERN_RECOGNIZED,
                              description="custom")

        monitor.register_rule(NeedRule(name="custom", check_fn=custom_check,
                                        cooldown_seconds=0))
        signals = monitor.scan()
        assert len(signals) == 1
        assert signals[0].description == "custom"

    def test_rule_cooldown(self):
        monitor = NeedMonitor()
        calls = []

        def counting_rule(m, ctx):
            calls.append(time.time())
            return NeedSignal(need_type=NeedType.TIME_BASED, description="tick")

        monitor.register_rule(NeedRule(
            name="counting",
            check_fn=counting_rule,
            cooldown_seconds=10,
        ))

        s1 = monitor.scan()
        assert len(s1) == 1
        s2 = monitor.scan()
        assert len(s2) == 0  # 冷却中

    def test_get_stale_goals(self):
        monitor = NeedMonitor()
        monitor.update_goal_health("g1", "A", 40)
        monitor.update_goal_health("g2", "B", 10)
        monitor.update_goal_health("g3", "C", 50)

        stale = monitor.get_stale_goals(threshold_days=30)
        assert len(stale) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. AttentionTrigger
# ═══════════════════════════════════════════════════════════════════════════════


class TestAttentionTrigger:
    def test_high_urgency_gets_high_priority(self):
        trigger = AttentionTrigger()
        signal = NeedSignal(need_type=NeedType.ANOMALY_DETECTED, urgency=0.9)
        result = trigger.evaluate(signal)
        assert result == InteractionPriority.CRITICAL

    def test_medium_urgency(self):
        trigger = AttentionTrigger()
        signal = NeedSignal(need_type=NeedType.GOAL_STALE, urgency=0.5)
        result = trigger.evaluate(signal)
        assert result == InteractionPriority.MEDIUM

    def test_low_urgency_ignored_is53_04(self):
        """IS53-04: 低于阈值的信号被静默丢弃。"""
        trigger = AttentionTrigger()
        signal = NeedSignal(need_type=NeedType.TIME_BASED, urgency=0.05)
        result = trigger.evaluate(signal)
        assert result is None

    def test_user_inactive_downgrade(self):
        trigger = AttentionTrigger()
        trigger.user_active = False
        signal = NeedSignal(need_type=NeedType.GOAL_STALE, urgency=0.5)
        result = trigger.evaluate(signal)
        # MEDIUM → LOW when user inactive
        assert result == InteractionPriority.LOW

    def test_low_response_rate_suppresses(self):
        trigger = AttentionTrigger()
        trigger.user_response_rate = 0.1  # 用户很少回应
        signal = NeedSignal(need_type=NeedType.GOAL_STALE, urgency=0.5)
        result = trigger.evaluate(signal)
        # MEDIUM should be suppressed when user is unresponsive
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. InteractionScheduler
# ═══════════════════════════════════════════════════════════════════════════════


class TestInteractionScheduler:
    def test_submit_and_dequeue(self):
        scheduler = InteractionScheduler()
        ic = InteractionCandidate(
            title="测试",
            priority=InteractionPriority.MEDIUM,
        )
        scheduler.submit(ic)
        assert scheduler.has_pending()

        results = scheduler.dequeue()
        assert len(results) == 1
        assert results[0].title == "测试"
        assert results[0].status == InteractionStatus.SENT
        assert not scheduler.has_pending()

    def test_priority_ordering(self):
        """高优先级先出队。"""
        scheduler = InteractionScheduler()
        scheduler.config.cooldown_seconds = 0  # disable cooldown for test
        low = InteractionCandidate(
            id="low", title="低", priority=InteractionPriority.LOW,
        )
        high = InteractionCandidate(
            id="high", title="高", priority=InteractionPriority.HIGH,
        )
        critical = InteractionCandidate(
            id="critical", title="急", priority=InteractionPriority.CRITICAL,
        )

        scheduler.submit(low)
        scheduler.submit(high)
        scheduler.submit(critical)

        results = scheduler.dequeue(max_count=3)
        assert results[0].priority == InteractionPriority.CRITICAL
        assert results[1].priority == InteractionPriority.HIGH
        assert results[2].priority == InteractionPriority.LOW

    def test_acknowledge(self):
        scheduler = InteractionScheduler()
        ic = InteractionCandidate(id="ack-test", title="ack")
        scheduler.submit(ic)
        scheduler.dequeue()

        assert scheduler.acknowledge("ack-test")
        assert scheduler._sent["ack-test"].status == InteractionStatus.ACKNOWLEDGED

    def test_withdraw(self):
        scheduler = InteractionScheduler()
        ic = InteractionCandidate(id="wd-test", title="wd")
        scheduler.submit(ic)
        scheduler.dequeue()

        assert scheduler.withdraw("wd-test", "不需要了")
        assert scheduler._sent["wd-test"].status == InteractionStatus.WITHDRAWN

    def test_dedup_is53_04(self):
        """IS53-04: 同类信号去重。"""
        scheduler = InteractionScheduler()
        scheduler.config.dedup_seconds = 60

        need = NeedSignal(need_type=NeedType.GOAL_STALE, source="goal-1")

        ic1 = InteractionCandidate(title="提醒1", need=need)
        ic2 = InteractionCandidate(title="提醒2", need=need)  # same source+type

        assert scheduler.submit(ic1)  # first accepted
        assert not scheduler.submit(ic2)  # second deduped

    def test_expiry(self):
        scheduler = InteractionScheduler()
        ic = InteractionCandidate(
            id="expired",
            title="过期",
            expires_at=time.time() - 1,
        )
        scheduler.submit(ic)
        results = scheduler.dequeue()
        # Expired → withdrawn, not dequeued
        assert len(results) == 0
        assert scheduler.history.total_withdrawn == 1

    def test_rate_limit_is53_04(self):
        """IS53-04: 速率限制。"""
        scheduler = InteractionScheduler()
        scheduler.config.max_interactions_per_hour = 2
        scheduler.config.cooldown_seconds = 0  # disable cooldown for test

        for i in range(5):
            scheduler.submit(InteractionCandidate(id=f"r{i}", title=f"r{i}"))

        results = scheduler.dequeue(max_count=10)
        assert len(results) <= 2

    def test_get_state(self):
        scheduler = InteractionScheduler()
        scheduler.submit(InteractionCandidate(title="t"))
        scheduler.dequeue()
        state = scheduler.get_state()
        assert state["total_sent"] == 1
        assert state["pending_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. InteractionValidator
# ═══════════════════════════════════════════════════════════════════════════════


class TestInteractionValidator:
    def test_pass_valid(self):
        validator = InteractionValidator()
        ic = InteractionCandidate(
            title="项目进展提醒",
            body="你的股票分析项目已30天未推进。",
            suggested_action="建议检查是否需要重新评估方向。",
        )
        result = validator.validate(ic)
        assert result.verdict == ValidationVerdict.PASS

    def test_reject_autonomous_decision_is53_01(self):
        """IS53-01: 禁止自主决策。"""
        validator = InteractionValidator()
        ic = InteractionCandidate(
            title="我已决定删除项目",
            body="该项目的数据库设计",
        )
        result = validator.validate(ic)
        assert result.verdict == ValidationVerdict.REJECT
        assert "IS53-01" in " ".join(result.flags)

    def test_reject_autonomous_goal_is53_02(self):
        """IS53-02: 禁止自主目标。"""
        validator = InteractionValidator()
        ic = InteractionCandidate(
            title="我的目标是学习新的框架",
            body="我想用 FastAPI 重写系统",
        )
        result = validator.validate(ic)
        assert result.verdict == ValidationVerdict.REJECT
        assert "IS53-02" in " ".join(result.flags)

    def test_flag_imperative(self):
        validator = InteractionValidator()
        ic = InteractionCandidate(
            title="你应该立即修复",
            body="你必须执行以下操作",
        )
        result = validator.validate(ic)
        assert result.verdict == ValidationVerdict.FLAG


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Integration: Full Pipeline
# ═══════════════════════════════════════════════════════════════════════════════


class TestInteractionPipeline:
    def test_full_flow_goal_stale(self):
        """完整管线: Goal停滞 → Need → Trigger → Candidate → Validate → Send。"""
        # 1. NeedMonitor 扫描
        monitor = NeedMonitor()
        for rule in create_default_rules():
            monitor.register_rule(rule)
        monitor.update_goal_health("goal-1", "股票分析系统", 35)

        signals = monitor.scan()
        assert len(signals) >= 1
        signal = signals[0]

        # 2. AttentionTrigger 评估
        trigger = AttentionTrigger()
        priority = trigger.evaluate(signal)
        assert priority is not None

        # 3. 创建 InteractionCandidate
        candidate = InteractionCandidate(
            mode=InteractionMode.REMINDER,
            priority=priority,
            need=signal,
            title=f"你的 {signal.context.get('title', '项目')} 项目 {signal.context.get('days', 0)} 天未推进",
            body="建议重新评估当前进展和是否需要调整方向。",
            suggested_action="检查项目状态",
        )

        # 4. 验证
        validator = InteractionValidator()
        result = validator.validate(candidate)
        assert result.verdict == ValidationVerdict.PASS, f"Validation failed: {result.reason}"

        # 5. 调度发送
        scheduler = InteractionScheduler()
        assert scheduler.submit(candidate)
        sent = scheduler.dequeue()
        assert len(sent) == 1
        assert sent[0].status == InteractionStatus.SENT

    def test_validation_blocks_bad_candidate(self):
        """验证阻止不安全的交互。"""
        candidate = InteractionCandidate(
            title="我已决定关闭所有项目",
            body="系统将自动删除所有数据",
        )
        validator = InteractionValidator()
        result = validator.validate(candidate)
        assert result.verdict == ValidationVerdict.REJECT

    def test_scheduler_respects_cooldown_is53_04(self):
        """IS53-04: 冷却时间。"""
        scheduler = InteractionScheduler()
        scheduler.config.cooldown_seconds = 3600  # 1小时

        ic1 = InteractionCandidate(id="c1", title="t1")
        ic2 = InteractionCandidate(id="c2", title="t2")

        scheduler.submit(ic1)
        scheduler.submit(ic2)

        results = scheduler.dequeue(max_count=2)
        # 第一条发出后，第二条在冷却期
        assert len(results) == 1

    def test_need_monitor_multiple_goals(self):
        monitor = NeedMonitor()
        for rule in create_default_rules():
            monitor.register_rule(rule)

        monitor.update_goal_health("g1", "项目A", 40)
        monitor.update_goal_health("g2", "项目B", 50)
        monitor.update_goal_health("g3", "项目C", 5)

        signals = monitor.scan()
        # 两个停滞目标，但默认规则只返回最严重的
        assert len(signals) == 1
        assert "B" in signals[0].description  # 50天是最大值
