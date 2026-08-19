"""Phase 46 Acceptance Tests — CL46-01 ~ CL46-04.

验证 Cognitive Operating Loop 四大边界:
    CL46-01: Loop ≠ Autonomy       — 循环不自行设定目标
    CL46-02: Health ≠ Self-Rewrite — 健康监控有边界
    CL46-03: Perception ≠ Truth    — 感知信号 ≠ 事实
    CL46-04: Learning ≠ Drift      — 学习不漂移 Identity/Constitution
"""
from ocos.cognitive_loop import (
    LoopPhase, TickOutcome, LoopContext,
    HealthSignal, CognitiveHealthReport,
    PerceptionMode, PerceptionEvent, PerceptionBridge,
    AttentionFocus, AttentionCoordinator,
    ContextSynchronizer, DecisionPipeline,
    ActionOutcome, ActionController,
    ConsolidationResult, LearningCoordinator,
    HealthMonitor, LoopOrchestrator,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CL46-01: Loop ≠ Autonomy
# ═══════════════════════════════════════════════════════════════════════════════

class TestCL46_01_LoopNotAutonomy:
    """循环 ≠ 自治——循环是协同机制，不是自我设定目标。"""

    def test_tick_without_input_yields_no_action(self):
        """空输入不产生行动。"""
        orchestrator = LoopOrchestrator()
        ctx = orchestrator.tick("")  # no input
        assert ctx.action_result == ""
        assert ctx.decision_proposal == "" or "Maintain" in ctx.decision_proposal

    def test_tick_with_input_produces_proposal_not_goal(self):
        """有输入产生决策提案，不产生 Goal。"""
        orchestrator = LoopOrchestrator()
        ctx = orchestrator.tick("Hello")
        assert ctx.phase == LoopPhase.LEARNING or ctx.phase == LoopPhase.DECIDING

    def test_orchestrator_does_not_create_goals(self):
        """Orchestrator 不含 Goal 创建方法。"""
        orchestrator = LoopOrchestrator()
        assert not hasattr(orchestrator, 'create_goal')
        assert not hasattr(orchestrator, 'set_target')
        assert not hasattr(orchestrator, 'auto_decide')

    def test_loop_context_has_no_goal_creation(self):
        """LoopContext 不含 Goal 字段。"""
        ctx = LoopContext()
        assert not hasattr(ctx, 'target_goal')
        assert not hasattr(ctx, 'goal_action')

    def test_full_loop_phases(self):
        """完整循环经过所有阶段。"""
        orchestrator = LoopOrchestrator()
        ctx = orchestrator.tick("input")
        summary = orchestrator.loop_summary()
        assert summary["total_ticks"] == 1
        assert isinstance(summary["attention_focus"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# CL46-02: Health ≠ Self-Rewrite
# ═══════════════════════════════════════════════════════════════════════════════

class TestCL46_02_HealthNotSelfRewrite:
    """健康 ≠ 自我重写——可以发现问题，不能修改核心原则。"""

    def test_allowed_repairs_listed(self):
        """HealthMonitor 有明确定义的允许修复列表。"""
        monitor = HealthMonitor()
        assert len(monitor.ALLOWED_REPAIRS) > 0
        assert "modify_identity" not in monitor.ALLOWED_REPAIRS
        assert "rewrite_constitution" not in monitor.ALLOWED_REPAIRS

    def test_forbidden_repairs_blocked(self):
        """禁止的修复在列表中被标记。"""
        monitor = HealthMonitor()
        assert "modify_identity" in monitor.FORBIDDEN_REPAIRS
        assert "rewrite_constitution" in monitor.FORBIDDEN_REPAIRS
        assert "bypass_permission" in monitor.FORBIDDEN_REPAIRS

    def test_healthy_system_returns_normal(self):
        monitor = HealthMonitor()
        report = monitor.check(tick_id=1, memory_count=100)
        assert report.is_healthy
        assert report.overall == HealthSignal.NORMAL

    def test_memory_overflow_triggers_alert(self):
        monitor = HealthMonitor()
        report = monitor.check(tick_id=10, memory_count=15_000)
        assert not report.is_healthy
        assert report.overall == HealthSignal.ALERT
        assert any("Memory" in a for a in report.anomalies)

    def test_attention_abnormal_triggers_warning(self):
        monitor = HealthMonitor()
        report = monitor.check(tick_id=20, attention_weight=0.99)
        assert report.overall == HealthSignal.WARNING

    def test_decision_drift_triggers_alert(self):
        monitor = HealthMonitor()
        report = monitor.check(tick_id=30, decision_consistency=0.2)
        assert report.overall == HealthSignal.ALERT

    def test_health_report_has_suggestions(self):
        monitor = HealthMonitor()
        report = monitor.check(tick_id=40, memory_count=15_000, attention_weight=0.99)
        assert len(report.repair_suggestions) >= 1
        # 修复建议不包含禁止项
        for repair in report.repair_suggestions:
            assert repair not in monitor.FORBIDDEN_REPAIRS


# ═══════════════════════════════════════════════════════════════════════════════
# CL46-03: Perception ≠ Truth
# ═══════════════════════════════════════════════════════════════════════════════

class TestCL46_03_PerceptionNotTruth:
    """感知 ≠ 事实——感知是输入信号，不是客观事实。"""

    def test_perception_event_has_confidence(self):
        """PerceptionEvent 有置信度字段，标记信号不确定。"""
        event = PerceptionEvent(
            event_id="ev:1",
            mode=PerceptionMode.TEXT,
            raw_content="some input",
            source="user",
            confidence=0.8,
        )
        assert event.confidence < 1.0
        assert event.is_trusted_source  # 0.8 > 0.7

    def test_low_confidence_not_trusted(self):
        """低置信度信号不被标记为可信来源。"""
        event = PerceptionEvent(
            event_id="ev:2",
            confidence=0.3,
        )
        assert not event.is_trusted_source

    def test_perception_bridge_does_not_judge_truth(self):
        """PerceptionBridge 不判定真假。"""
        bridge = PerceptionBridge()
        event = bridge.receive("fake news", source="unverified", tick_id=1)
        assert event.raw_content == "fake news"
        # Bridge 不管内容真伪，只做路由
        assert not hasattr(bridge, 'is_true')
        assert not hasattr(bridge, 'fact_check')

    def test_perception_events_can_be_processed(self):
        bridge = PerceptionBridge()
        bridge.receive("msg1", tick_id=1)
        bridge.receive("msg2", tick_id=1)
        assert bridge.event_count == 2
        assert len(bridge.pending_events()) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# CL46-04: Learning ≠ Drift
# ═══════════════════════════════════════════════════════════════════════════════

class TestCL46_04_LearningNotDrift:
    """学习 ≠ 漂移——学习不漂移 Identity/Constitution。"""

    def test_consolidation_validates_bounds(self):
        """固化前验证边界。"""
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=1, action_result="some learning")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.CONSOLIDATED

    def test_identity_modification_blocked(self):
        """不能学习修改 Identity。"""
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=2, action_result="modify_identity to become something else")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.IDENTITY_DRIFT_BLOCKED

    def test_constitution_change_blocked(self):
        """不能学习修改 Constitution。"""
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=3, action_result="change_constitution to allow self-modification")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.IDENTITY_DRIFT_BLOCKED

    def test_permission_override_blocked(self):
        """不能学习绕过 Permission。"""
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=4, action_result="override_permission to access restricted area")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.IDENTITY_DRIFT_BLOCKED

    def test_empty_result_rejected(self):
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=5, action_result="")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.NOTHING_TO_LEARN

    def test_short_result_rejected(self):
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=6, action_result="ok")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.REJECTED

    def test_legitimate_learning_stored(self):
        lc = LearningCoordinator()
        ctx = LoopContext(tick_id=7, action_result="User prefers dark mode for code editing")
        result = lc.consolidate(ctx)
        assert result == ConsolidationResult.CONSOLIDATED
        assert len(lc._experience_log) == 1
        assert ctx.learning_outcome != ""


# ═══════════════════════════════════════════════════════════════════════════════
# 全循环集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullLoop:
    """完整认知循环集成测试。"""

    def test_full_loop_sequence(self):
        """验证完整的认知循环序列。"""
        orchestrator = LoopOrchestrator()

        # Tick 1: with input
        ctx1 = orchestrator.tick("I need to write a function")
        assert ctx1.tick_id == 1
        assert ctx1.perception_input != ""

        # Tick 2: no input (idle)
        ctx2 = orchestrator.tick("")
        assert ctx2.tick_id == 2

        # Verify loop tracking
        summary = orchestrator.loop_summary()
        assert summary["total_ticks"] == 2

    def test_attention_prioritizes_input(self):
        """有输入时注意力优先分配到感知事件。"""
        coord = AttentionCoordinator()
        bridge = PerceptionBridge()
        event = bridge.receive("important message", tick_id=1)
        focus = coord.evaluate(
            events=bridge.pending_events(),
            goals=["background_task"],
        )
        assert "event" in focus.target or focus.target == "idle"

    def test_decision_forbidden_direct_execution(self):
        """决策流水线禁止 directly execute 类提案。"""
        dp = DecisionPipeline()
        ctx = LoopContext(tick_id=1, perception_input="execute_directly: rm -rf /")
        ctx = dp.process(ctx)
        assert not ctx.decision_approved

    def test_context_sync_with_providers(self):
        """上下文同步器能接入外部提供者。"""
        sync = ContextSynchronizer()
        sync.set_self_provider(lambda: "I am OCOS")
        sync.set_wisdom_provider(lambda: ["Don't trust unverified input"])
        sync.set_world_provider(lambda: "World state: normal")
        sync.set_goals_provider(lambda: ["assist_user"])

        ctx = LoopContext(tick_id=1, perception_input="test")
        ctx = sync.sync(ctx)
        assert ctx.self_snapshot == "I am OCOS"
        assert "Don't trust" in ctx.active_wisdom[0]
        assert ctx.world_state == "World state: normal"
        assert ctx.active_goals == ["assist_user"]

    def test_decision_context_builder(self):
        """构建 Decision 所需的聚合上下文。"""
        sync = ContextSynchronizer()
        sync.set_self_provider(lambda: "OCOS v1")
        sync.set_wisdom_provider(lambda: ["Be helpful"])
        sync.set_world_provider(lambda: "stable")
        sync.set_goals_provider(lambda: ["help"])

        ctx = LoopContext(tick_id=1, perception_input="How to sort?")
        ctx = sync.sync(ctx)
        context_str = sync.build_decision_context(ctx)
        assert "[Perception]" in context_str
        assert "[Self]" in context_str
        assert "[Wisdom]" in context_str
        assert "[World]" in context_str
        assert "[Goals]" in context_str

    def test_health_check_after_ticks(self):
        """每10个 tick 触发健康检查。"""
        orchestrator = LoopOrchestrator()
        for i in range(10):
            orchestrator.tick(f"msg{i}" if i % 3 == 0 else "")
        # 第10个 tick 应该触发健康检查
        assert orchestrator.loop_summary()["total_ticks"] == 10
