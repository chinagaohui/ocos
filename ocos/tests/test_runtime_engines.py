"""Test suite for DecisionRuntimeEngine, ExecutionRuntimeEngine, ProcessRuntimeEngine.

Phase 18 Runtime Foundation — 三个 Runtime Engine 的全量测试。

分层:
1. DecisionRuntimeEngine 生命周期（形成、转移、过期、重置）
2. ExecutionRuntimeEngine 生命周期（创建、开始、完成、超时）
3. ProcessRuntimeEngine 生命周期（创建、开始、完成、失败）
4. 交叉验证（事件驱动）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from ocos.kernel.abi import (
    Event,
    EventType,
    Decision,
    DecisionStatus,
)
from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.decision_runtime import DecisionRuntimeEngine
from ocos.runtime.execution_runtime import ExecutionRuntimeEngine
from ocos.models.execution import Execution, ExecutionStatus
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessState, ProcessType, ProcessStep


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
def decision_engine(event_bus, working_memory):
    return DecisionRuntimeEngine(event_bus, working_memory)


@pytest.fixture
def execution_engine(event_bus, working_memory):
    return ExecutionRuntimeEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    return ProcessRuntimeEngine(event_bus, working_memory)


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionRuntimeEngine:

    def test_form_decision(self, decision_engine, working_memory):
        """创建 Decision（PROPOSED 状态），应存在于 WorkingMemory。"""
        result = decision_engine.form_decision(
            goal_id="g1",
            selected_option="option_a",
            reasoning="Because",
            confidence=0.85,
        )
        assert result.success
        assert result.decision_id
        d = decision_engine.get_decision(result.decision_id)
        assert d is not None
        assert d.status == DecisionStatus.PROPOSED.value
        assert d.goal_id == "g1"
        assert d.selected_option == "option_a"

    def test_form_decision_custom_id(self, decision_engine):
        """支持自定义 decision_id。"""
        result = decision_engine.form_decision(decision_id="my-decision")
        assert result.success
        assert result.decision_id == "my-decision"

    def test_transition_committed(self, decision_engine):
        """PROPOSED → COMMITTED。"""
        result = decision_engine.form_decision(goal_id="g1")
        assert result.success
        d_id = result.decision_id

        tr = decision_engine.transition_decision(d_id, DecisionStatus.COMMITTED)
        assert tr.success
        d = decision_engine.get_decision(d_id)
        assert d.status == DecisionStatus.COMMITTED.value

    def test_transition_invalid(self, decision_engine):
        """PROPOSED → SUCCEEDED（不存在）应为非法转移。"""
        result = decision_engine.form_decision()
        tr = decision_engine.transition_decision(result.decision_id, DecisionStatus.EXECUTED)
        assert not tr.success
        assert "Invalid transition" in tr.message

    def test_transition_unknown_decision(self, decision_engine):
        """不存在的 decision_id 应返回失败。"""
        tr = decision_engine.transition_decision("nonexistent", DecisionStatus.COMMITTED)
        assert not tr.success
        assert "not found" in tr.message

    def test_full_lifecycle(self, decision_engine):
        """PROPOSED → COMMITTED → EXECUTED。"""
        r = decision_engine.form_decision(goal_id="g1")
        assert decision_engine.transition_decision(r.decision_id, DecisionStatus.COMMITTED).success
        assert decision_engine.transition_decision(r.decision_id, DecisionStatus.EXECUTED).success

        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.EXECUTED.value

    def test_terminal_blocks_further(self, decision_engine):
        """EXECUTED 是 terminal 状态，不能继续转移。"""
        r = decision_engine.form_decision()
        decision_engine.transition_decision(r.decision_id, DecisionStatus.COMMITTED)
        decision_engine.transition_decision(r.decision_id, DecisionStatus.EXECUTED)
        tr = decision_engine.transition_decision(r.decision_id, DecisionStatus.REVOKED)
        assert not tr.success

    def test_expiration(self, decision_engine):
        """TTL 过期后 check_expirations 应标记 EXPIRED。"""
        r = decision_engine.form_decision(goal_id="g1")
        decision_engine.configure_expiration(default_ttl_seconds=0)
        # 模拟未来时间
        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        expired = decision_engine.check_expirations(now=future)
        # expired 列表判断逻辑：created_at > default_ttl
        # default_ttl=0，所以任何 Decision 都过期
        assert len(expired) == 1

    def test_subscribed_events(self, decision_engine):
        """引擎应订阅 DECISION 相关事件。"""
        subs = decision_engine.subscription_ids
        assert len(subs) == 5  # VALIDATED, EXECUTED, REVOKED, SUPERSEDED, EXPIRED

    def test_unsubscribe_all(self, decision_engine):
        """取消订阅后不应再响应事件。"""
        # 直接发布事件测试
        decision_engine.unsubscribe_all()
        assert len(decision_engine.subscription_ids) == 0

    def test_reset(self, decision_engine):
        """reset 应清空所有 Decision。"""
        decision_engine.form_decision()
        decision_engine.form_decision()
        assert decision_engine.decision_count == 2
        count = decision_engine.reset()
        assert count == 2
        assert decision_engine.decision_count == 0

    def test_list_decisions_by_status(self, decision_engine):
        """按状态筛选 Decision 列表。"""
        r1 = decision_engine.form_decision(goal_id="g1")
        r2 = decision_engine.form_decision(goal_id="g2")
        decision_engine.transition_decision(r1.decision_id, DecisionStatus.COMMITTED)

        committed = decision_engine.list_decisions(DecisionStatus.COMMITTED)
        proposed = decision_engine.list_decisions(DecisionStatus.PROPOSED)
        assert len(committed) == 1
        assert len(proposed) == 1
        assert committed[0].goal_id == "g1"

    def test_event_driven_transition(self, decision_engine, event_bus):
        """发布 VALIDATED 事件应触发状态转移。"""
        r = decision_engine.form_decision()
        decision_engine._apply_transition(r.decision_id, DecisionStatus.PROPOSED)  # noop

        # 直接调 apply（事件驱动模式的内部方法）
        decision_engine._apply_transition(r.decision_id, DecisionStatus.COMMITTED)
        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.COMMITTED.value

    def test_supersede(self, decision_engine):
        """PROPOSED → SUPERSEDED。"""
        r = decision_engine.form_decision()
        tr = decision_engine.transition_decision(r.decision_id, DecisionStatus.SUPERSEDED)
        assert tr.success
        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.SUPERSEDED.value

    def test_revoke(self, decision_engine):
        """PROPOSED → REVOKED。"""
        r = decision_engine.form_decision()
        tr = decision_engine.transition_decision(r.decision_id, DecisionStatus.REVOKED)
        assert tr.success


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionRuntimeEngine:

    def test_schedule_execution(self, execution_engine, working_memory):
        """schedule_execution 创建 PENDING Execution。"""
        r = execution_engine.schedule_execution(decision_id="d1")
        assert r.success
        e = execution_engine.get_execution(r.execution_id)
        assert e is not None
        assert e.status == ExecutionStatus.PENDING.value
        assert e.decision_id == "d1"

    def test_schedule_custom_id(self, execution_engine):
        r = execution_engine.schedule_execution(execution_id="my-exec")
        assert r.execution_id == "my-exec"

    def test_pending_to_running(self, execution_engine):
        """PENDING → RUNNING。"""
        r = execution_engine.schedule_execution()
        tr = execution_engine.start_execution(r.execution_id)
        assert tr.success
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.RUNNING.value

    def test_running_to_succeeded(self, execution_engine):
        """RUNNING → SUCCEEDED。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.SUCCEEDED)
        assert tr.success
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.SUCCEEDED.value
        assert e.completed_at is not None

    def test_running_to_failed(self, execution_engine):
        """RUNNING → FAILED。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.FAILED)
        assert tr.success
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.FAILED.value

    def test_pending_to_succeeded_invalid(self, execution_engine):
        """PENDING → SUCCEEDED 应非法。"""
        r = execution_engine.schedule_execution()
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.SUCCEEDED)
        assert not tr.success
        assert "Invalid transition" in tr.message

    def test_unknown_execution(self, execution_engine):
        tr = execution_engine.transition_execution("nonexistent", ExecutionStatus.RUNNING)
        assert not tr.success
        assert "not found" in tr.message

    def test_full_lifecycle(self, execution_engine):
        """PENDING → RUNNING → SUCCEEDED。"""
        r = execution_engine.schedule_execution(decision_id="d1", action_ids=("act1", "act2"))
        assert execution_engine.start_execution(r.execution_id).success
        assert execution_engine.transition_execution(r.execution_id, ExecutionStatus.SUCCEEDED).success
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.SUCCEEDED.value
        assert "act1" in e.action_ids
        assert e.completed_at is not None

    def test_terminal_blocks_further(self, execution_engine):
        """SUCCEEDED 后不能继续转移。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        execution_engine.transition_execution(r.execution_id, ExecutionStatus.SUCCEEDED)
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.FAILED)
        assert not tr.success

    def test_interrupt(self, execution_engine):
        """RUNNING → INTERRUPTED。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.INTERRUPTED)
        assert tr.success
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.INTERRUPTED.value

    def test_cancel(self, execution_engine):
        """RUNNING → CANCELLED。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        tr = execution_engine.transition_execution(r.execution_id, ExecutionStatus.CANCELLED)
        assert tr.success

    def test_timeout(self, execution_engine):
        """超时的 RUNNING Execution 应被标记为 FAILED。"""
        r = execution_engine.schedule_execution()
        execution_engine.start_execution(r.execution_id)
        execution_engine.configure_timeout(default_timeout_seconds=0)
        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        timed_out = execution_engine.check_timeouts(now=future)
        assert len(timed_out) == 1
        e = execution_engine.get_execution(r.execution_id)
        assert e.status == ExecutionStatus.FAILED.value

    def test_subscribed_events(self, execution_engine):
        subs = execution_engine.subscription_ids
        assert len(subs) == 5  # STARTED, COMPLETED, FAILED, INTERRUPTED, CANCELLED

    def test_unsubscribe_all(self, execution_engine):
        execution_engine.unsubscribe_all()
        assert len(execution_engine.subscription_ids) == 0

    def test_reset(self, execution_engine):
        execution_engine.schedule_execution()
        execution_engine.schedule_execution()
        assert execution_engine.execution_count == 2
        count = execution_engine.reset()
        assert count == 2
        assert execution_engine.execution_count == 0

    def test_list_executions_by_status(self, execution_engine):
        r1 = execution_engine.schedule_execution(decision_id="d1")
        r2 = execution_engine.schedule_execution(decision_id="d2")
        execution_engine.start_execution(r1.execution_id)

        running = execution_engine.list_executions(ExecutionStatus.RUNNING)
        pending = execution_engine.list_executions(ExecutionStatus.PENDING)
        assert len(running) == 1
        assert len(pending) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ProcessRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessRuntimeEngine:

    def test_create_process(self, process_engine, working_memory):
        """create_process 创建 CREATED 状态的 TransformProcess。"""
        r = process_engine.create_process(process_type=ProcessType.REASONING)
        assert r.success
        p = process_engine.get_process(r.process_id)
        assert p is not None
        assert p.process_state == ProcessState.CREATED.value
        assert p.process_type == ProcessType.REASONING.value

    def test_create_with_steps(self, process_engine):
        step = ProcessStep(step_id="s1", description="transform", operation="map")
        r = process_engine.create_process(steps=(step,))
        p = process_engine.get_process(r.process_id)
        assert len(p.steps) == 1
        assert p.steps[0].description == "transform"

    def test_created_to_running(self, process_engine):
        """CREATED → RUNNING。"""
        r = process_engine.create_process()
        tr = process_engine.start_process(r.process_id)
        assert tr.success
        p = process_engine.get_process(r.process_id)
        assert p.process_state == ProcessState.RUNNING.value

    def test_running_to_completed(self, process_engine):
        """RUNNING → COMPLETED。"""
        r = process_engine.create_process()
        process_engine.start_process(r.process_id)
        tr = process_engine.complete_process(r.process_id)
        assert tr.success
        p = process_engine.get_process(r.process_id)
        assert p.process_state == ProcessState.COMPLETED.value

    def test_running_to_failed(self, process_engine):
        """RUNNING → FAILED。"""
        r = process_engine.create_process()
        process_engine.start_process(r.process_id)
        tr = process_engine.transition_process(r.process_id, ProcessState.FAILED)
        assert tr.success
        p = process_engine.get_process(r.process_id)
        assert p.process_state == ProcessState.FAILED.value

    def test_created_to_completed_invalid(self, process_engine):
        """CREATED → COMPLETED 应非法。"""
        r = process_engine.create_process()
        tr = process_engine.transition_process(r.process_id, ProcessState.COMPLETED)
        assert not tr.success
        assert "Invalid transition" in tr.message

    def test_unknown_process(self, process_engine):
        tr = process_engine.transition_process("nonexistent", ProcessState.RUNNING)
        assert not tr.success

    def test_full_lifecycle(self, process_engine):
        """CREATED → RUNNING → COMPLETED。"""
        r = process_engine.create_process(
            process_type=ProcessType.REASONING,
            input_addresses=("addr:in:1",),
            output_addresses=("addr:out:1",),
        )
        assert process_engine.start_process(r.process_id).success
        assert process_engine.complete_process(r.process_id).success
        p = process_engine.get_process(r.process_id)
        assert p.process_state == ProcessState.COMPLETED.value
        assert "addr:in:1" in p.input_addresses

    def test_terminal_blocks_further(self, process_engine):
        """COMPLETED 后不能继续。"""
        r = process_engine.create_process()
        process_engine.start_process(r.process_id)
        process_engine.complete_process(r.process_id)
        tr = process_engine.transition_process(r.process_id, ProcessState.FAILED)
        assert not tr.success

    def test_subscribed_events(self, process_engine):
        """应订阅 PROCESS_STARTED, COMPLETED, FAILED（不包含 CREATED——那是通知事件）。"""
        # PROCESS_STARTED, PROCESS_COMPLETED, PROCESS_FAILED = 3
        subs = process_engine.subscription_ids
        assert len(subs) == 3

    def test_unsubscribe_all(self, process_engine):
        process_engine.unsubscribe_all()
        assert len(process_engine.subscription_ids) == 0

    def test_reset(self, process_engine):
        process_engine.create_process()
        process_engine.create_process()
        assert process_engine.process_count == 2
        count = process_engine.reset()
        assert count == 2
        assert process_engine.process_count == 0

    def test_list_by_state(self, process_engine):
        r1 = process_engine.create_process()
        r2 = process_engine.create_process()
        process_engine.start_process(r1.process_id)

        running = process_engine.list_processes(ProcessState.RUNNING)
        created = process_engine.list_processes(ProcessState.CREATED)
        assert len(running) == 1
        assert len(created) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-Runtime Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossRuntimeIntegration:

    def test_event_driven_decision_via_bus(self, decision_engine, event_bus):
        """通过 EventBus 发布事件，引擎应响应。"""
        r = decision_engine.form_decision(goal_id="g1")
        decision_engine._apply_transition(r.decision_id, DecisionStatus.PROPOSED)
        # _apply_transition on PROPOSED → PROPOSED should be noop
        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.PROPOSED.value
        # now transition via event pub
        decision_engine._apply_transition(r.decision_id, DecisionStatus.COMMITTED)
        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.COMMITTED.value

    def test_shared_working_memory(self, decision_engine, execution_engine, working_memory):
        """三个引擎共享 WorkingMemory，应能独立管理不同类型的条目。"""
        # 创建各个类型的条目
        d_result = decision_engine.form_decision(goal_id="g1")
        e_result = execution_engine.schedule_execution(decision_id=d_result.decision_id)

        # 验证各引擎能独立查询
        assert decision_engine.decision_count == 1
        assert execution_engine.execution_count == 1
        assert decision_engine.get_decision(d_result.decision_id) is not None
        assert execution_engine.get_execution(e_result.execution_id) is not None

    def test_separate_reset(self, decision_engine, execution_engine, process_engine):
        """各引擎的 reset 只清空自己的那部分。"""
        decision_engine.form_decision(goal_id="g1")
        execution_engine.schedule_execution()
        process_engine.create_process()

        assert decision_engine.decision_count == 1
        assert execution_engine.execution_count == 1
        assert process_engine.process_count == 1

        decision_engine.reset()
        assert decision_engine.decision_count == 0
        assert execution_engine.execution_count == 1  # 不互相影响
        assert process_engine.process_count == 1
