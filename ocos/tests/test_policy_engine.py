"""
Test suite for PolicyEngine.

Phase 19 — 策略引擎测试。

覆盖:
1. 规则管理（增删查）
2. 默认策略评估（ALLOW/DENY/WARN）
3. 自定义评估器
4. ProcessRuntimeEngine 集成
5. 边界与错误处理
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.policy import (
    PolicyEffect, PolicyDomain, PolicyRule, PolicyEvaluation, PolicyTrace,
)
from ocos.engines.policy_engine import PolicyEngine, register_rule_evaluator


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def working_memory(event_bus):
    return WorkingMemory(event_bus=event_bus)


@pytest.fixture
def engine(event_bus, working_memory):
    return PolicyEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(process_id: str) -> TransformProcess:
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.POLICY,
    )


SAMPLE_RULES = [
    PolicyRule(name="deny_low_quality", domain=PolicyDomain.QUALITY,
               effect=PolicyEffect.DENY, priority=10,
               condition="quality >= 4"),
    PolicyRule(name="warn_high_cost", domain=PolicyDomain.RESOURCE,
               effect=PolicyEffect.WARN, priority=5,
               condition="cost <= 8"),
    PolicyRule(name="deny_high_risk", domain=PolicyDomain.COMPLIANCE,
               effect=PolicyEffect.DENY, priority=8,
               condition="risk <= 7"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 规则管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleManagement:
    """规则增删查。"""

    def test_add_rule(self, engine):
        r = PolicyRule(name="test", effect=PolicyEffect.DENY, condition="x >= 0")
        engine.add_rule(r)
        assert len(engine.list_rules()) == 1

    def test_add_rules_batch(self, engine):
        engine.add_rules(SAMPLE_RULES)
        assert len(engine.list_rules()) == 3

    def test_remove_rule(self, engine):
        engine.add_rules(SAMPLE_RULES)
        engine.remove_rule(SAMPLE_RULES[0].rule_id)
        assert len(engine.list_rules()) == 2

    def test_remove_nonexistent(self, engine):
        assert engine.remove_rule("nonexistent") is False

    def test_clear_rules(self, engine):
        engine.add_rules(SAMPLE_RULES)
        engine.clear_rules()
        assert len(engine.list_rules()) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 策略评估
# ═══════════════════════════════════════════════════════════════════════════════

class TestPolicyEvaluation:
    """各种策略评估场景。"""

    def test_all_pass(self, engine):
        p = _make_process("p-ap")
        result = engine.execute(p, context={"quality": 8, "cost": 5, "risk": 2})
        assert result.success
        assert result.all_passed
        trace = engine.get_trace(result.trace_id)
        assert trace.all_passed

    def test_deny_violation(self, engine):
        p = _make_process("p-dv")
        result = engine.execute(p, context={"quality": 2, "cost": 5, "risk": 2})
        assert result.success
        assert not result.all_passed
        trace = engine.get_trace(result.trace_id)
        # quality=2 不满足 quality >= 4 (DENY)
        evals = [e for e in trace.evaluations if not e.passed]
        assert len(evals) >= 1

    def test_warn_does_not_block(self, engine):
        """WARN 规则的失败不应导致 all_passed=False。"""
        p = _make_process("p-wn")
        # cost=9 > 8，触发 WARN，但不应阻止
        result = engine.execute(p, context={"quality": 8, "cost": 9, "risk": 2})
        assert result.success
        # quality=8 >= 4 (PASS), cost=9 > 8 (WARN→PASS), risk=2 <= 7 (PASS)
        assert result.all_passed

    def test_multiple_deny_violations(self, engine):
        p = _make_process("p-md")
        result = engine.execute(p, context={"quality": 2, "cost": 9, "risk": 9})
        assert not result.all_passed
        trace = engine.get_trace(result.trace_id)
        failed = [e for e in trace.evaluations if not e.passed]
        assert len(failed) >= 1

    def test_default_rules_used_when_empty(self, engine):
        """引擎默认提供 3 条规则。"""
        p = _make_process("p-dr")
        result = engine.execute(p, context={"quality": 8, "cost": 5, "risk": 2})
        assert result.evaluated_count == 3

    def test_custom_rules_override_defaults(self, engine):
        engine.add_rule(PolicyRule(
            name="custom_only", effect=PolicyEffect.DENY, priority=99,
            condition="score >= 5",
        ))
        p = _make_process("p-cr")
        result = engine.execute(p, context={"score": 3})
        assert result.evaluated_count == 1  # 只有自定义规则


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 自定义评估器
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomEvaluator:
    """自定义规则评估器。"""

    def test_custom_evaluator_invoked(self, engine):
        my_rule = PolicyRule(
            name="my_rule", effect=PolicyEffect.DENY,
            condition="custom_logic",
        )
        engine.add_rule(my_rule)

        called = []

        def my_eval(rule: PolicyRule, ctx: dict) -> PolicyEvaluation:
            called.append(True)
            return PolicyEvaluation(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                effect=rule.effect,
                passed=True,
                detail="Custom logic applied",
            )

        register_rule_evaluator(my_rule.rule_id, my_eval)
        p = _make_process("p-ce")
        result = engine.execute(p, context={"x": 1})
        assert result.success
        assert called == [True]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """PolicyEngine 与 ProcessRuntimeEngine 的协作。"""

    def test_process_engine_creates_policy_process(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.POLICY)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.POLICY.value

    def test_policy_engine_executes_process(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.POLICY)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = engine.execute(p, context={"quality": 8, "cost": 5, "risk": 2})
        assert result.success
        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件和错误处理。"""

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wrong",
            process_type=ProcessType.REASONING,
        )
        result = engine.execute(p)
        assert not result.success
        assert "Not a POLICY process" in result.message

    def test_custom_evaluator_error(self, engine):
        my_rule = PolicyRule(
            name="broken", effect=PolicyEffect.DENY,
            condition="anything",
        )
        engine.add_rule(my_rule)

        def broken_eval(rule, ctx):
            raise RuntimeError("Evaluator crashed")

        register_rule_evaluator(my_rule.rule_id, broken_eval)
        p = _make_process("p-be")
        result = engine.execute(p)
        trace = engine.get_trace(result.trace_id)
        broken = [e for e in trace.evaluations if not e.passed]
        assert len(broken) >= 1
        assert "Evaluator error" in broken[0].detail

    def test_trace_lifecycle(self, engine):
        p = _make_process("p-tl")
        result = engine.execute(p, context={"quality": 8, "cost": 5, "risk": 2})
        trace = engine.get_trace(result.trace_id)
        assert trace is not None
        assert engine.list_traces() == [trace]
        engine.clear_traces()
        assert len(engine.list_traces()) == 0
