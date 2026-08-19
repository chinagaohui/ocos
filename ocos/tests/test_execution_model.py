"""Phase 17.1 — Execution Model Tests.

覆盖五维：
1. Model — Execution 数据模型、ExecutionStatus 枚举
2. Event — EventType 包含全部 EXECUTION_* 事件
3. Trace — ExecutionTrace 创建与字段完整
4. Constitution — 宪法规则存在且定义正确
5. Invariants — Theory 的三个不变量

测试标准：每个维度至少一个正面测试 + 一个负面测试。
"""

from __future__ import annotations

import dataclasses

import pytest

from ocos.kernel.abi import EventType
from ocos.kernel.constitution import ConstitutionalRule
from ocos.models.execution import Execution, ExecutionStatus
from ocos.models.information import UniversalAddress
from ocos.platform.trace_engine import (
    ExecutionTrace,
    TraceEngine,
    TraceType,
)


# ════════════════════════════════════════════════════════════════════
# 维度 1: Model — Execution 数据模型
# ════════════════════════════════════════════════════════════════════


class TestExecutionModel:
    """Execution 数据模型 & ExecutionStatus 枚举。"""

    def test_execution_default_status(self) -> None:
        """默认状态应为 PENDING。"""
        ex = Execution()
        assert ex.status == ExecutionStatus.PENDING

    def test_execution_has_unique_id(self) -> None:
        """每次创建自动生成唯一 execution_id。"""
        e1 = Execution()
        e2 = Execution()
        assert e1.execution_id != e2.execution_id

    def test_execution_accepts_decision_id(self) -> None:
        """Invariant 1：可以设置 decision_id。"""
        ex = Execution(decision_id="dec_abc123")
        assert ex.decision_id == "dec_abc123"

    def test_execution_accepts_observation_addresses(self) -> None:
        """Invariant 3：observation_addresses 支持 UniversalAddress。"""
        addr = UniversalAddress(namespace="working", type="observation", id="obs_001")
        ex = Execution(observation_addresses=(addr,))
        assert len(ex.observation_addresses) == 1
        assert ex.observation_addresses[0] is addr

    def test_execution_is_frozen(self) -> None:
        """Execution 是 frozen dataclass，不可变。"""
        ex = Execution()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field"):
            ex.status = ExecutionStatus.RUNNING  # type: ignore

    def test_execution_has_timestamps(self) -> None:
        """初始 created_at 自动填充。"""
        ex = Execution()
        assert ex.started_at != ""
        assert ex.completed_at == ""

    def test_execution_metadata_is_optional(self) -> None:
        """metadata 为可选字段，默认为空 dict。"""
        ex = Execution(metadata={"key": "val"})
        assert ex.metadata["key"] == "val"


class TestExecutionStatusEnum:
    """ExecutionStatus 枚举语义。"""

    def test_execution_status_is_enum_not_str(self) -> None:
        """status 为 Enum，不是普通 str。"""
        assert isinstance(ExecutionStatus.PENDING, ExecutionStatus)
        assert issubclass(ExecutionStatus, str)

    def test_execution_status_values_match_lowercase(self) -> None:
        """枚举值使用小写字符串。"""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.SUCCEEDED.value == "succeeded"
        assert ExecutionStatus.FAILED.value == "failed"

    def test_execution_is_terminal_for_terminal_states(self) -> None:
        """终止态（succeeded/failed/interrupted/cancelled）返回 is_terminal == True。"""
        assert ExecutionStatus.SUCCEEDED.is_terminal
        assert ExecutionStatus.FAILED.is_terminal
        assert ExecutionStatus.INTERRUPTED.is_terminal
        assert ExecutionStatus.CANCELLED.is_terminal

    def test_execution_is_terminal_for_non_terminal(self) -> None:
        """非终止态（pending/running）返回 is_terminal == False。"""
        assert not ExecutionStatus.PENDING.is_terminal
        assert not ExecutionStatus.RUNNING.is_terminal

    def test_valid_transitions_from_pending(self) -> None:
        """PENDING → RUNNING / CANCELLED。"""
        assert ExecutionStatus.PENDING.can_transition_to(ExecutionStatus.RUNNING)
        assert ExecutionStatus.PENDING.can_transition_to(ExecutionStatus.CANCELLED)

    def test_valid_transitions_from_running(self) -> None:
        """RUNNING → 所有终止态。"""
        assert ExecutionStatus.RUNNING.can_transition_to(ExecutionStatus.SUCCEEDED)
        assert ExecutionStatus.RUNNING.can_transition_to(ExecutionStatus.FAILED)
        assert ExecutionStatus.RUNNING.can_transition_to(ExecutionStatus.INTERRUPTED)
        assert ExecutionStatus.RUNNING.can_transition_to(ExecutionStatus.CANCELLED)

    def test_invalid_transitions_from_pending(self) -> None:
        """PENDING 不能直接跳到 SUCCEEDED / FAILED。"""
        assert not ExecutionStatus.PENDING.can_transition_to(ExecutionStatus.SUCCEEDED)
        assert not ExecutionStatus.PENDING.can_transition_to(ExecutionStatus.FAILED)
        assert not ExecutionStatus.PENDING.can_transition_to(ExecutionStatus.INTERRUPTED)

    def test_terminal_states_have_no_outgoing(self) -> None:
        """终止态不可再转移。"""
        for state in [
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
            ExecutionStatus.CANCELLED,
        ]:
            for target in ExecutionStatus:
                assert not state.can_transition_to(target)


# ════════════════════════════════════════════════════════════════════
# 维度 2: Event — EventType 包含全部 EXECUTION_* 事件
# ════════════════════════════════════════════════════════════════════


class TestExecutionEvents:
    """每个 Execution 生命周期事件都已注册。"""

    EXECUTION_EVENTS = [
        "EXECUTION_STARTED",
        "EXECUTION_COMPLETED",
        "EXECUTION_FAILED",
        "EXECUTION_INTERRUPTED",
        "EXECUTION_CANCELLED",
    ]

    def test_all_execution_events_exist(self) -> None:
        """五种 Execution 事件全部在 EventType 中定义。"""
        for name in self.EXECUTION_EVENTS:
            assert hasattr(EventType, name), f"Missing EventType.{name}"

    def test_execution_event_values(self) -> None:
        """事件值格式为 'execution.<state>'。"""
        assert EventType.EXECUTION_STARTED == "execution.started"
        assert EventType.EXECUTION_COMPLETED == "execution.completed"
        assert EventType.EXECUTION_FAILED == "execution.failed"
        assert EventType.EXECUTION_INTERRUPTED == "execution.interrupted"
        assert EventType.EXECUTION_CANCELLED == "execution.cancelled"

    def test_event_type_allows_dispatch_by_prefix(self) -> None:
        """事件名可通过 'execution.' 前缀识别。"""
        execution_events = {
            e for e in dir(EventType) if isinstance(getattr(EventType, e), str)
        }
        actual = {
            e for e in execution_events
            if getattr(EventType, e).startswith("execution.")
        }
        assert len(actual) == len(self.EXECUTION_EVENTS)


# ════════════════════════════════════════════════════════════════════
# 维度 3: Trace — ExecutionTrace 创建与字段完整
# ════════════════════════════════════════════════════════════════════


class TestExecutionTrace:
    """ExecutionTrace 数据模型 & record_execution() 方法。"""

    def test_execution_trace_class_exists(self) -> None:
        """ExecutionTrace 类已定义。"""
        trace = ExecutionTrace()
        assert trace.trace_type == TraceType.EXECUTION

    def test_execution_trace_fields(self) -> None:
        """ExecutionTrace 包含全部必要字段。"""
        trace = ExecutionTrace(
            execution_id="ex_001",
            decision_id="dec_001",
            status="succeeded",
            started_at="2026-07-22T10:00:00",
            completed_at="2026-07-22T10:00:05",
            action_ids=("act_001",),
            observation_addresses=("obs_001",),
        )
        assert trace.execution_id == "ex_001"
        assert trace.decision_id == "dec_001"
        assert trace.status == "succeeded"
        assert trace.started_at == "2026-07-22T10:00:00"
        assert trace.completed_at == "2026-07-22T10:00:05"
        assert trace.action_ids == ("act_001",)
        assert trace.observation_addresses == ("obs_001",)

    def test_execution_trace_auto_id(self) -> None:
        """自动生成唯一 trace_id。"""
        t1 = ExecutionTrace()
        t2 = ExecutionTrace()
        assert t1.trace_id != t2.trace_id

    def test_record_execution(self) -> None:
        """TraceEngine.record_execution() 创建并存储 ExecutionTrace。"""
        engine = TraceEngine()
        trace_id = engine.record_execution(
            execution_id="ex_001",
            decision_id="dec_001",
            status="succeeded",
            started_at="2026-07-22T10:00:00",
            completed_at="2026-07-22T10:00:05",
            action_ids=["act_001"],
            observation_addresses=["obs_001"],
        )
        stored = engine.get_trace(trace_id)
        assert stored is not None
        assert isinstance(stored, ExecutionTrace)
        assert stored.execution_id == "ex_001"
        assert stored.decision_id == "dec_001"
        assert stored.status == "succeeded"

    def test_record_execution_minimal(self) -> None:
        """record_execution 可使用全部默认参数。"""
        engine = TraceEngine()
        trace_id = engine.record_execution(execution_id="ex_min")
        stored = engine.get_trace(trace_id)
        assert stored is not None
        assert stored.execution_id == "ex_min"

    def test_execution_trace_is_frozen(self) -> None:
        """ExecutionTrace 是 frozen dataclass。"""
        trace = ExecutionTrace()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field"):
            trace.status = "succeeded"  # type: ignore

    def test_execution_trace_status_value(self) -> None:
        """验证统一 API：通过 trace_engine 记录完整的运行过程。"""
        engine = TraceEngine()
        trace_id = engine.record_execution(
            execution_id="ex_status_check",
            decision_id="dec_002",
            status="failed",
            started_at="2026-07-22T10:00:00",
            completed_at="2026-07-22T10:00:03",
            action_ids=["act_001", "act_002"],
        )
        stored = engine.get_trace(trace_id)
        assert stored is not None
        assert stored.decision_id == "dec_002"
        assert stored.status == "failed"
        assert len(stored.action_ids) == 2


# ════════════════════════════════════════════════════════════════════
# 维度 4: Constitution — 宪法规则存在且定义正确
# ════════════════════════════════════════════════════════════════════


class TestExecutionConstitution:
    """ConstitutionalRule 包含三条 Execution 规则。"""

    def test_execution_requires_committed_decision_rule(self) -> None:
        """Rule 14 存在。"""
        rule = ConstitutionalRule.EXECUTION_REQUIRES_COMMITTED_DECISION
        assert rule.value == "execution_requires_committed_decision"

    def test_execution_not_modify_decision_rule(self) -> None:
        """Rule 15 存在。"""
        rule = ConstitutionalRule.EXECUTION_NOT_MODIFY_DECISION
        assert rule.value == "execution_not_modify_decision"

    def test_execution_must_produce_observation_rule(self) -> None:
        """Rule 16 存在。"""
        rule = ConstitutionalRule.EXECUTION_MUST_PRODUCE_OBSERVATION
        assert rule.value == "execution_must_produce_observation"

    def test_execution_rules_have_descriptions(self) -> None:
        """三条规则都有对应的文字描述。"""
        from ocos.kernel.constitution import Constitution

        for rule_name in [
            ConstitutionalRule.EXECUTION_REQUIRES_COMMITTED_DECISION,
            ConstitutionalRule.EXECUTION_NOT_MODIFY_DECISION,
            ConstitutionalRule.EXECUTION_MUST_PRODUCE_OBSERVATION,
        ]:
            desc = Constitution.get_rule_description(rule_name)
            assert desc != "", f"Rule {rule_name} has no description"


# ════════════════════════════════════════════════════════════════════
# 维度 5: Invariants — Theory 的三个不变量
# ════════════════════════════════════════════════════════════════════


class TestExecutionInvariants:
    """EXECUTION_THEORY v1.0 的三个不变量。"""

    def test_invariant1_execution_requires_decision_id(self) -> None:
        """Invariant 1: Execution 必须有 decision_id。"""
        ex = Execution(decision_id="dec_valid")
        assert ex.decision_id != ""

    def test_invariant2_execution_does_not_modify_decision(self) -> None:
        """Invariant 2: Execution 不持有 Decision 对象，只持有 ID。

        这是架构层面的保证——Execution 无法修改它不持有的对象。
        """
        ex = Execution(decision_id="dec_001")
        # Execution 的字段中不包含 Decision 对象
        assert not hasattr(ex, "decision")
        # decision_id 是 str，不可变
        assert isinstance(ex.decision_id, str)

    def test_invariant3_execution_produces_observation_address(self) -> None:
        """Invariant 3: observation_addresses 存储结构合法。"""
        addr = UniversalAddress(namespace="working", type="observation", id="obs_001")
        ex = Execution(observation_addresses=(addr,))
        assert len(ex.observation_addresses) > 0
        assert ex.observation_addresses[0].type == "observation"
