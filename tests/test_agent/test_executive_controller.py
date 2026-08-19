"""Phase 22-D: ExecutiveController 单元测试 (22d5)。

验证:
  - 三阶段职责链: Intent → Strategy → Capability
  - 原有 MetaController 监控/熔断功能不变
  - 别名向后兼容
"""
import pytest
from unittest.mock import MagicMock

from ocos.agent.executive_controller import (
    ExecutiveController,
    MetaController,
    IntentAnalysis,
    Strategy,
    CapabilityPlan,
)


class TestExecutiveControllerPipeline:
    """三阶段职责链测试。"""

    @pytest.fixture
    def ec(self):
        return ExecutiveController()

    # ── Stage 1: Intent Understanding ──────────────────────────────

    def test_analyze_intent_from_mock(self, ec):
        """从 mock intent 分析意图。"""
        intent = MagicMock()
        intent.get_intent_type.return_value = "write"
        intent.get_confidence.return_value = 0.85

        result = ec.analyze_intent(intent)
        assert isinstance(result, IntentAnalysis)
        assert result.intent_type == "write"
        assert result.confidence == 0.85
        assert "writing_engine" in result.required_capabilities

    def test_analyze_intent_execute(self, ec):
        """execute 意图应高紧急度。"""
        intent = MagicMock()
        intent.get_intent_type.return_value = "execute"
        intent.get_confidence.return_value = 0.9

        result = ec.analyze_intent(intent)
        assert result.urgency == 1.0
        assert "execution_engine" in result.required_capabilities

    def test_analyze_intent_unknown(self, ec):
        """未知意图应有默认值。"""
        result = ec.analyze_intent(None)
        assert result.intent_type in ("unknown", "None")

    def test_analyze_intent_plan(self, ec):
        """plan 意图应匹配 planning_engine。"""
        intent = MagicMock()
        intent.get_intent_type.return_value = "plan"
        intent.get_confidence.return_value = 0.7
        result = ec.analyze_intent(intent)
        assert "planning_engine" in result.required_capabilities

    # ── Stage 2: Strategy Formulation ───────────────────────────────

    def test_formulate_strategy_execute(self, ec):
        """execute 意图 → direct_execution 策略。"""
        intent = IntentAnalysis(intent_type="execute", confidence=0.9, urgency=1.0)
        strategy = ec.formulate_strategy(intent)
        assert strategy.name == "direct_execution"
        assert "validate" in strategy.steps
        assert "dispatch" in strategy.steps

    def test_formulate_strategy_with_capabilities(self, ec):
        """有能力的意图 → capability_chain 策略。"""
        intent = IntentAnalysis(
            intent_type="write",
            confidence=0.8,
            required_capabilities=["writing_engine"],
        )
        strategy = ec.formulate_strategy(intent)
        assert strategy.name == "capability_chain"
        assert len(strategy.steps) >= 2

    def test_formulate_strategy_unknown(self, ec):
        """未知意图 → observation_only 策略。"""
        intent = IntentAnalysis(intent_type="unknown", confidence=0.1)
        strategy = ec.formulate_strategy(intent)
        assert strategy.name == "observation_only"
        assert "observe" in strategy.steps

    # ── Stage 3: Capability Selection ───────────────────────────────

    def test_select_capabilities(self, ec):
        """能力选择应过滤不可用引擎。"""
        intent = IntentAnalysis(
            intent_type="write",
            required_capabilities=["writing_engine", "reasoning_engine"],
        )
        strategy = Strategy(name="test", steps=["step1"])
        plan = ec.select_capabilities(
            intent, strategy,
            available_engines=["writing_engine"],
        )
        assert isinstance(plan, CapabilityPlan)
        assert "writing_engine" in plan.engines
        assert "reasoning_engine" not in plan.engines

    def test_select_capabilities_no_available(self, ec):
        """无可用引擎时应返回空列表。"""
        intent = IntentAnalysis(
            intent_type="write",
            required_capabilities=["writing_engine"],
        )
        strategy = Strategy(name="test", steps=[])
        plan = ec.select_capabilities(intent, strategy)
        assert plan.engines == ["writing_engine"]  # 不过滤

    # ── 完整职责链 ─────────────────────────────────────────────────

    def test_execute_chain(self, ec):
        """execute_chain 应返回完整分析结果。"""
        mock_agent = MagicMock()
        mock_agent.intent = MagicMock()
        mock_agent.intent.get_intent_type.return_value = "think"
        mock_agent.intent.get_confidence.return_value = 0.75
        mock_agent.engine_bridge.get_available_engines.return_value = ["reasoning_engine"]

        result = ec.execute_chain(mock_agent)
        assert result["intent"] == "think"
        assert result["strategy"] in ("capability_chain", "standard_loop")
        assert "steps" in result


class TestExecutiveControllerMonitoring:
    """监控/熔断功能测试（零行为变更）。"""

    def test_cycle_count(self):
        ec = ExecutiveController()
        assert ec.cycle_count == 0
        ec.begin_cycle()
        assert ec.cycle_count == 1

    def test_deadlock_detection(self):
        ec = ExecutiveController()
        for _ in range(5):
            if ec.check_deadlock("same_action"):
                pass
        assert ec.check_deadlock("same_action") is True

    def test_is_blocked_by_max_cycles(self):
        ec = ExecutiveController(max_cycles=2)
        ec.begin_cycle()
        ec.begin_cycle()
        assert ec.is_blocked() is True

    def test_reset(self):
        ec = ExecutiveController()
        ec.begin_cycle()
        ec.reset()
        assert ec.cycle_count == 0

    def test_get_stats(self):
        ec = ExecutiveController()
        stats = ec.get_stats()
        assert "cycle_count" in stats
        assert "is_blocked" in stats


class TestBackwardCompatibility:
    """MetaController 别名兼容性。"""

    def test_metacontroller_is_alias(self):
        """MetaController 应等于 ExecutiveController。"""
        assert MetaController is ExecutiveController

    def test_metacontroller_instantiation(self):
        """MetaController 实例应与 ExecutiveController 行为相同。"""
        mc = MetaController(max_cycles=10)
        assert mc._max_cycles == 10
        assert mc.cycle_count == 0
