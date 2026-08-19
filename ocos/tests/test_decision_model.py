"""
Phase 17.3 — Decision Theory → Code Alignment
测试覆盖：Model（DecisionStatus、Decision） + Events + Trace + Constitution
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ocos.kernel.abi import (
    Decision,
    DecisionStatus,
    EventType,
    _DECISION_LEGACY_MAP as DECISION_LEGACY_MAP,
    _VALID_DECISION_STATUS_VALUES as VALID_DECISION_STATUS_VALUES,
)
from ocos.kernel.constitution import ConstitutionalRule
from ocos.kernel.event_schema import EVENT_SCHEMA_REGISTRY as EVENT_SCHEMA
from ocos.models import DecisionStatus as ImportedDecisionStatus
from ocos.platform.trace_engine import DecisionTrace


# ════════════════════════════════════════════════════════════════
# Part 1: DecisionStatus Enum
# ════════════════════════════════════════════════════════════════

class TestDecisionStatusEnum:
    """DecisionStatus Enum 核心属性与兼容映射。"""

    def test_has_expected_members(self) -> None:
        assert len(DecisionStatus) == 6
        assert DecisionStatus.PROPOSED.value == "proposed"
        assert DecisionStatus.COMMITTED.value == "committed"
        assert DecisionStatus.EXECUTED.value == "executed"
        assert DecisionStatus.REVOKED.value == "revoked"
        assert DecisionStatus.SUPERSEDED.value == "superseded"
        assert DecisionStatus.EXPIRED.value == "expired"

    def test_is_terminal(self) -> None:
        assert DecisionStatus.is_terminal("revoked") is True
        assert DecisionStatus.is_terminal("superseded") is True
        assert DecisionStatus.is_terminal("expired") is True
        assert DecisionStatus.is_terminal("proposed") is False
        assert DecisionStatus.is_terminal("committed") is False
        assert DecisionStatus.is_terminal("executed") is False

    def test_is_terminal_legacy(self) -> None:
        assert DecisionStatus.is_terminal("failed") is True
        assert DecisionStatus.is_terminal("formed") is False

    def test_is_active(self) -> None:
        assert DecisionStatus.is_active("proposed") is True
        assert DecisionStatus.is_active("committed") is True
        assert DecisionStatus.is_active("executed") is False
        assert DecisionStatus.is_active("revoked") is False

    def test_is_active_legacy(self) -> None:
        assert DecisionStatus.is_active("formed") is True
        assert DecisionStatus.is_active("validated") is True
        assert DecisionStatus.is_active("executing") is False

    def test_resolve_standard(self) -> None:
        """标准值 resolve 返回自身。"""
        assert DecisionStatus.PROPOSED.resolve() is DecisionStatus.PROPOSED

    def test_resolve_legacy(self) -> None:
        """Legacy 值 resolve 返回映射后的标准值。"""
        assert DecisionStatus("formed").resolve() == DecisionStatus.PROPOSED
        assert DecisionStatus("validated").resolve() == DecisionStatus.COMMITTED
        assert DecisionStatus("executing").resolve() == DecisionStatus.EXECUTED
        assert DecisionStatus("completed").resolve() == DecisionStatus.EXECUTED
        assert DecisionStatus("failed").resolve() == DecisionStatus.REVOKED

    def test_validate_valid(self) -> None:
        """所有标准值和 Legacy 值均通过验证。"""
        for v in ["proposed", "committed", "executed", "revoked",
                  "superseded", "expired"]:
            assert DecisionStatus.validate(v)
        for v in ["formed", "validated", "executing", "completed", "failed"]:
            assert DecisionStatus.validate(v)

    def test_validate_invalid(self) -> None:
        assert DecisionStatus.validate("") is False
        assert DecisionStatus.validate("unknown") is False
        assert DecisionStatus.validate("pending") is False

    def test_legacy_map_contains_all_legacy_values(self) -> None:
        assert "formed" in DECISION_LEGACY_MAP
        assert "validated" in DECISION_LEGACY_MAP
        assert "executing" in DECISION_LEGACY_MAP
        assert "completed" in DECISION_LEGACY_MAP
        assert "failed" in DECISION_LEGACY_MAP
        assert len(DECISION_LEGACY_MAP) == 5

    def test_valid_values_set_contains_all(self) -> None:
        assert "proposed" in VALID_DECISION_STATUS_VALUES
        assert "formed" in VALID_DECISION_STATUS_VALUES
        assert "invalid" not in VALID_DECISION_STATUS_VALUES


# ════════════════════════════════════════════════════════════════
# Part 2: Decision Model (Frozen Dataclass)
# ════════════════════════════════════════════════════════════════

class TestDecisionModel:
    """Decision dataclass 冻结、字段、验证、向后兼容。"""

    def test_is_frozen(self) -> None:
        d = Decision()
        with pytest.raises(AttributeError):
            d.status = "committed"  # type: ignore[misc]

    def test_default_status_is_formed(self) -> None:
        """默认 status='formed'（向后兼容 Legacy）。"""
        d = Decision()
        assert d.status == "formed"

    def test_accepts_valid_standard_status(self) -> None:
        d = Decision(status="proposed")
        assert d.status == "proposed"

    def test_accepts_legacy_status(self) -> None:
        d = Decision(status="validated")
        assert d.status == "validated"

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="Invalid Decision status"):
            Decision(status="invalid")

    def test_has_selected_option(self) -> None:
        d = Decision(selected_option="plan_b")
        assert d.selected_option == "plan_b"

    def test_reasoning_is_legacy_string(self) -> None:
        d = Decision(reasoning="chosen plan_b due to lower cost")
        assert isinstance(d.reasoning, str)

    def test_has_goal_id(self) -> None:
        d = Decision(goal_id="goal_123")
        assert d.goal_id == "goal_123"

    def test_confidence_default(self) -> None:
        d = Decision()
        assert d.confidence == 0.0

    def test_timestamp_auto_generated(self) -> None:
        d = Decision()
        assert isinstance(d.timestamp, str)
        assert len(d.timestamp) > 10

    def test_decision_id_auto_generated(self) -> None:
        d1, d2 = Decision(), Decision()
        assert d1.decision_id != d2.decision_id

    def test_backward_compatible_formed_to_proposed(self) -> None:
        """Legacy 'formed' → DecisionStatus('formed') → PROPOSED。"""
        ds = DecisionStatus("formed")
        assert ds == DecisionStatus.PROPOSED

    def test_serialization_roundtrip(self) -> None:
        """frozen dataclass 可 hash / 可 compare。"""
        d1 = Decision(decision_id="same", status="committed", goal_id="g1",
                       timestamp="2026-01-01T00:00:00Z")
        d2 = Decision(decision_id="same", status="committed", goal_id="g1",
                       timestamp="2026-01-01T00:00:00Z")
        assert d1 == d2
        assert hash(d1) == hash(d2)

    def test_always_has_schema_version(self) -> None:
        d = Decision()
        assert d.schema_version is not None
        assert isinstance(d.schema_version, str)

    def test_exported_from_models(self) -> None:
        """DecisionStatus 可通过 ocos.models 导出。"""
        assert ImportedDecisionStatus is DecisionStatus


# ════════════════════════════════════════════════════════════════
# Part 3: Decision Events
# ════════════════════════════════════════════════════════════════

class TestDecisionEvents:
    """Decision 事件常量和 schema。"""

    def test_existing_events_preserved(self) -> None:
        assert EventType.DECISION_FORMED.value == "decision.formed"
        assert EventType.DECISION_VALIDATED.value == "decision.validated"

    def test_new_events_added(self) -> None:
        assert EventType.DECISION_REVOKED.value == "decision.revoked"
        assert EventType.DECISION_SUPERSEDED.value == "decision.superseded"
        assert EventType.DECISION_EXPIRED.value == "decision.expired"

    def test_total_decision_events_is_five(self) -> None:
        decision_events = {
            EventType.DECISION_FORMED,
            EventType.DECISION_VALIDATED,
            EventType.DECISION_REVOKED,
            EventType.DECISION_SUPERSEDED,
            EventType.DECISION_EXPIRED,
        }
        assert len(decision_events) == 5

    def test_event_schema_formed_exists(self) -> None:
        schema = EVENT_SCHEMA.get(EventType.DECISION_FORMED)
        assert schema is not None
        assert "decision_id" in schema["required_payload_fields"]
        assert "goal_id" in schema["required_payload_fields"]

    def test_event_schema_revoked_exists(self) -> None:
        schema = EVENT_SCHEMA.get(EventType.DECISION_REVOKED)
        assert schema is not None
        assert "decision_id" in schema["required_payload_fields"]
        assert "reason" in schema["required_payload_fields"]

    def test_event_schema_superseded_exists(self) -> None:
        schema = EVENT_SCHEMA.get(EventType.DECISION_SUPERSEDED)
        assert schema is not None
        assert "superseded_by" in schema["required_payload_fields"]

    def test_event_schema_expired_exists(self) -> None:
        schema = EVENT_SCHEMA.get(EventType.DECISION_EXPIRED)
        assert schema is not None
        assert "reason" in schema["required_payload_fields"]


# ════════════════════════════════════════════════════════════════
# Part 4: Decision Trace
# ════════════════════════════════════════════════════════════════

class TestDecisionTrace:
    """DecisionTrace 承诺态变更记录。"""

    def test_trace_has_status_fields(self) -> None:
        trace = DecisionTrace(
            status="committed",
            previous_status="proposed",
        )
        assert trace.status == "committed"
        assert trace.previous_status == "proposed"

    def test_trace_default_status_is_empty(self) -> None:
        trace = DecisionTrace()
        assert trace.status == ""
        assert trace.previous_status == ""

    def test_trace_is_frozen(self) -> None:
        trace = DecisionTrace()
        with pytest.raises(AttributeError):
            trace.status = "committed"  # type: ignore[misc]

    def test_trace_has_decision_id(self) -> None:
        trace = DecisionTrace(decision_id="dec_1")
        assert trace.decision_id == "dec_1"

    def test_trace_has_goal_id(self) -> None:
        trace = DecisionTrace(goal_id="goal_1")
        assert trace.goal_id == "goal_1"

    def test_trace_has_reasoning_chain(self) -> None:
        trace = DecisionTrace(reasoning_chain=["step1", "step2"])
        assert len(trace.reasoning_chain) == 2

    def test_trace_has_confidence(self) -> None:
        trace = DecisionTrace(confidence=0.85)
        assert trace.confidence == 0.85

    def test_trace_has_outcome(self) -> None:
        trace = DecisionTrace(outcome="accepted")
        assert trace.outcome == "accepted"

    def test_trace_defaults_not_too_wide(self) -> None:
        """Trace 不包含 selected_option、confidence_history、validation_result。"""
        trace = DecisionTrace()
        assert not hasattr(trace, "selected_option")
        assert not hasattr(trace, "confidence_history")
        assert not hasattr(trace, "validation_result")
        # 仅包含 agreed fields
        assert hasattr(trace, "status")
        assert hasattr(trace, "previous_status")
        assert hasattr(trace, "reasoning_chain")
        assert hasattr(trace, "alternatives")


# ════════════════════════════════════════════════════════════════
# Part 5: Constitution — Decision Rules
# ════════════════════════════════════════════════════════════════

class TestDecisionConstitution:
    """宪法 R20 及 Decision 相关规则覆盖。"""

    def test_r20_decision_must_reference_goal_exists(self) -> None:
        assert ConstitutionalRule.DECISION_MUST_REFERENCE_GOAL.value == (
            "decision_must_reference_goal"
        )

    def test_r20_has_description(self) -> None:
        from ocos.kernel.constitution import Constitution
        desc = Constitution.get_rule_description(
            ConstitutionalRule.DECISION_MUST_REFERENCE_GOAL
        )
        assert desc
        assert "Goal" in desc
        assert "Decision" in desc

    def test_total_rules_with_r20(self) -> None:
        assert len(list(ConstitutionalRule)) == 24

    def test_existing_decision_rules_coverage(self) -> None:
        """R1+R6+R14+R15+R20 覆盖 Decision 宪法级约束。"""
        decision_scope_rules = {
            ConstitutionalRule.DECISION_IS_ONLY_ACTION_SOURCE,
            ConstitutionalRule.EVERY_ACTION_HAS_DECISION,
            ConstitutionalRule.EXECUTION_REQUIRES_COMMITTED_DECISION,
            ConstitutionalRule.EXECUTION_NOT_MODIFY_DECISION,
            ConstitutionalRule.DECISION_MUST_REFERENCE_GOAL,
        }
        assert len(decision_scope_rules) == 5
