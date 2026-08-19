"""
C1 Explainability Trace 引擎 — 测试套件。

覆盖范围：
1. Dataclass 冻结 + 默认值
2. 各 Trace 类型字段正确性
3. InMemoryTraceStore 读写查询上限淘汰
4. TraceEngine 注入接口端到端
5. Event Bus 集成（发射 + 订阅）
6. 边界条件（空 store、不存在的 trace_id、上限边界）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.platform.trace_engine import (
    DEFAULT_TRACE_STORE_SIZE,
    QUERY_DEFAULT_LIMIT,
    QUERY_MAX_LIMIT,
    DecisionTrace,
    InMemoryTraceStore,
    LearningTrace,
    MemoryTrace,
    ReasoningTrace,
    SimulationTrace,
    TraceEngine,
    TraceType,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Dataclass 冻结 + 默认值
# ═══════════════════════════════════════════════════════════════════════════


class TestDataclassFrozen:
    """所有 Trace 类型不可变 + 基本默认值正确。"""

    def test_decision_trace_frozen(self):
        dt = DecisionTrace(decision_id="d1")
        with pytest.raises(AttributeError):
            dt.decision_id = "d2"  # type: ignore[misc]

    def test_reasoning_trace_frozen(self):
        rt = ReasoningTrace(reasoning_id="r1")
        with pytest.raises(AttributeError):
            rt.reasoning_id = "r2"  # type: ignore[misc]

    def test_simulation_trace_frozen(self):
        st = SimulationTrace(simulation_id="s1")
        with pytest.raises(AttributeError):
            st.simulation_id = "s2"  # type: ignore[misc]

    def test_learning_trace_frozen(self):
        lt = LearningTrace(learning_id="l1")
        with pytest.raises(AttributeError):
            lt.learning_id = "l2"  # type: ignore[misc]

    def test_decision_trace_defaults(self):
        dt = DecisionTrace()
        assert dt.trace_type == TraceType.DECISION
        assert dt.schema_version == SCHEMA_VERSION
        assert isinstance(dt.trace_id, str) and len(dt.trace_id) > 0
        assert isinstance(dt.timestamp, str)
        assert dt.metadata == {}
        assert dt.reasoning_chain == []
        assert dt.alternatives == []

    def test_reasoning_trace_defaults(self):
        rt = ReasoningTrace()
        assert rt.trace_type == TraceType.REASONING
        assert rt.schema_version == SCHEMA_VERSION
        assert rt.observation_ids == []
        assert rt.knowledge_ids_used == []
        assert rt.reasoning_steps == []

    def test_simulation_trace_defaults(self):
        st = SimulationTrace()
        assert st.trace_type == TraceType.SIMULATION
        assert st.schema_version == SCHEMA_VERSION
        assert st.state_delta == {}

    def test_learning_trace_defaults(self):
        lt = LearningTrace()
        assert lt.trace_type == TraceType.LEARNING
        assert lt.schema_version == SCHEMA_VERSION
        assert lt.learning_rate_delta == 0.0

    def test_memory_trace_frozen(self):
        mt = MemoryTrace(address="a1")
        with pytest.raises(AttributeError):
            mt.address = "a2"  # type: ignore[misc]

    def test_memory_trace_defaults(self):
        mt = MemoryTrace()
        assert mt.trace_type == TraceType.MEMORY
        assert mt.schema_version == SCHEMA_VERSION
        assert mt.address == ""
        assert mt.operation == ""
        assert mt.content_summary == ""

    def test_trace_type_is_enum(self):
        """TraceType 是枚举而非字符串。"""
        assert issubclass(TraceType, str)
        assert list(TraceType) == [
            TraceType.DECISION,
            TraceType.REASONING,
            TraceType.SIMULATION,
            TraceType.LEARNING,
            TraceType.MEMORY,
            TraceType.EXECUTION,
            TraceType.GOAL,
        ]

    def test_unique_trace_ids_default(self):
        """默认构造的 trace_id 互不相同。"""
        ids = {DecisionTrace().trace_id for _ in range(100)}
        assert len(ids) == 100


# ═══════════════════════════════════════════════════════════════════════════
# 2. 各类 Trace 字段正确性
# ═══════════════════════════════════════════════════════════════════════════


class TestDecisionTrace:
    def test_all_fields(self):
        dt = DecisionTrace(
            source="policy_engine",
            decision_id="decision-001",
            goal_id="goal-abc",
            reasoning_chain=["step1", "step2"],
            confidence=0.85,
            outcome="accepted",
            alternatives=["prop-a", "prop-b"],
            metadata={"risk_level": "low"},
        )
        assert dt.source == "policy_engine"
        assert dt.decision_id == "decision-001"
        assert dt.goal_id == "goal-abc"
        assert dt.reasoning_chain == ["step1", "step2"]
        assert dt.confidence == 0.85
        assert dt.outcome == "accepted"
        assert dt.alternatives == ["prop-a", "prop-b"]
        assert dt.metadata == {"risk_level": "low"}

    def test_confidence_range(self):
        dt0 = DecisionTrace(confidence=0.0)
        dt1 = DecisionTrace(confidence=1.0)
        assert dt0.confidence == 0.0
        assert dt1.confidence == 1.0

    def test_alternatives_list_of_strings(self):
        """alternatives 为候选方案的 proposal_type 字符串列表。"""
        alts = ["quick_assessment", "deep_evaluation", "simulation_first"]
        dt = DecisionTrace(alternatives=alts)
        assert all(isinstance(a, str) for a in dt.alternatives)
        assert len(dt.alternatives) == 3


class TestReasoningTrace:
    def test_all_fields(self):
        rt = ReasoningTrace(
            source="reasoning_engine",
            reasoning_id="reason-001",
            observation_ids=["obs-1", "obs-2"],
            knowledge_ids_used=["k-a", "k-b"],
            reasoning_steps=["apply rule X", "evaluate Y", "conclude Z"],
            conclusion="Pattern matches hypothesis H",
        )
        assert rt.source == "reasoning_engine"
        assert rt.reasoning_id == "reason-001"
        assert rt.observation_ids == ["obs-1", "obs-2"]
        assert rt.knowledge_ids_used == ["k-a", "k-b"]
        assert rt.reasoning_steps == ["apply rule X", "evaluate Y", "conclude Z"]
        assert rt.conclusion == "Pattern matches hypothesis H"


class TestSimulationTrace:
    def test_all_fields(self):
        st = SimulationTrace(
            source="simulation_engine",
            simulation_id="sim-001",
            scenario="conflict_escalation_v3",
            depth=5,
            branches_explored=12,
            outcome="success",
            state_delta={"trust_score": -0.15, "alliance_status": "fractured"},
        )
        assert st.source == "simulation_engine"
        assert st.simulation_id == "sim-001"
        assert st.scenario == "conflict_escalation_v3"
        assert st.depth == 5
        assert st.branches_explored == 12
        assert st.outcome == "success"
        assert st.state_delta == {"trust_score": -0.15, "alliance_status": "fractured"}

    def test_state_delta_is_dict_not_full_snapshot(self):
        """state_delta 记录关键差异，非完整快照。"""
        st = SimulationTrace(state_delta={"key_metric": 42})
        assert isinstance(st.state_delta, dict)
        # 无"full_state"或"snapshot"字段
        assert "full_state" not in st.state_delta

    def test_depth_non_negative(self):
        st = SimulationTrace(depth=0)
        assert st.depth == 0


class TestLearningTrace:
    def test_all_fields(self):
        lt = LearningTrace(
            source="learning_engine",
            learning_id="learn-001",
            source_observation_id="obs-42",
            previous_knowledge="Rule: A implies B",
            new_knowledge="Rule: A implies B under condition C",
            learning_rate_delta=0.02,
            metadata={"epoch": 7},
        )
        assert lt.source == "learning_engine"
        assert lt.learning_id == "learn-001"
        assert lt.source_observation_id == "obs-42"
        assert lt.previous_knowledge == "Rule: A implies B"
        assert lt.new_knowledge == "Rule: A implies B under condition C"
        assert lt.learning_rate_delta == 0.02
        assert lt.metadata == {"epoch": 7}


class TestMemoryTrace:
    def test_all_fields(self):
        mt = MemoryTrace(
            source="context_manager",
            address="working:goal:g1",
            operation="store",
            content_summary="add_goal: 分析用户输入",
            metadata={"goal_count": 3},
        )
        assert mt.source == "context_manager"
        assert mt.address == "working:goal:g1"
        assert mt.operation == "store"
        assert mt.content_summary == "add_goal: 分析用户输入"
        assert mt.metadata == {"goal_count": 3}

    def test_operation_types(self):
        for op in ("store", "retrieve", "forget", "consolidate", "clear"):
            mt = MemoryTrace(operation=op)
            assert mt.operation == op

    def test_content_summary_not_full_content(self):
        mt = MemoryTrace(content_summary="add_goal: 分析用户输入")
        assert "add_goal" in mt.content_summary
        assert len(mt.content_summary) < 50  # 必须是摘要而非全量


# ═══════════════════════════════════════════════════════════════════════════
# 3. InMemoryTraceStore
# ═══════════════════════════════════════════════════════════════════════════


class TestInMemoryTraceStore:
    def test_store_and_get(self):
        store = InMemoryTraceStore()
        dt = DecisionTrace(decision_id="d1")
        store.store(dt)
        retrieved = store.get(dt.trace_id)
        assert retrieved is dt
        assert retrieved.decision_id == "d1"  # type: ignore[union-attr]

    def test_get_nonexistent_returns_none(self):
        store = InMemoryTraceStore()
        assert store.get("nonexistent") is None

    def test_count_starts_zero(self):
        store = InMemoryTraceStore()
        assert store.count() == 0

    def test_count_increases(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace())
        store.store(ReasoningTrace())
        assert store.count() == 2

    def test_query_all(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="d1", source="engine_a"))
        store.store(ReasoningTrace(reasoning_id="r1", source="engine_b"))
        assert len(store.query()) == 2

    def test_query_by_trace_type(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="d1"))
        store.store(ReasoningTrace(reasoning_id="r1"))
        store.store(SimulationTrace(simulation_id="s1"))
        results = store.query(trace_type=TraceType.REASONING)
        assert len(results) == 1
        assert results[0].reasoning_id == "r1"  # type: ignore[union-attr]

    def test_query_by_source(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="d1", source="engine_a"))
        store.store(DecisionTrace(decision_id="d2", source="engine_b"))
        store.store(DecisionTrace(decision_id="d3", source="engine_a"))
        results = store.query(source="engine_a")
        assert len(results) == 2

    def test_query_by_decision_id(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="target", source="engine_a"))
        store.store(DecisionTrace(decision_id="other", source="engine_a"))
        store.store(ReasoningTrace(reasoning_id="r1"))
        results = store.query(decision_id="target")
        assert len(results) == 1
        assert results[0].decision_id == "target"  # type: ignore[union-attr]

    def test_query_decision_id_ignores_non_decision(self):
        """decision_id 过滤忽略非 DecisionTrace 类型。"""
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="d1"))
        store.store(ReasoningTrace(reasoning_id="r1"))
        results = store.query(decision_id="r1")  # r1 是 reasoning_id 不是 decision_id
        assert len(results) == 0

    def test_query_newest_first(self):
        store = InMemoryTraceStore()
        d1 = DecisionTrace(decision_id="d1")
        d2 = DecisionTrace(decision_id="d2")
        d3 = DecisionTrace(decision_id="d3")
        store.store(d1)
        store.store(d2)
        store.store(d3)
        results = store.query()
        assert results[0].decision_id == "d3"  # type: ignore[union-attr]

    def test_query_limit(self):
        store = InMemoryTraceStore()
        for i in range(10):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        results = store.query(limit=3)
        assert len(results) == 3

    def test_query_offset(self):
        store = InMemoryTraceStore()
        for i in range(10):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        # offset=5 跳过最新的 5 条，取接下来 5 条
        results = store.query(limit=10, offset=5)
        assert len(results) == 5
        # 最新优先，d9, d8, d7, d6, d5 被跳过
        assert results[0].decision_id == "d4"  # type: ignore[union-attr]

    def test_query_limit_capped_at_max(self):
        store = InMemoryTraceStore()
        for i in range(QUERY_MAX_LIMIT + 100):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        results = store.query(limit=QUERY_MAX_LIMIT + 50)
        assert len(results) <= QUERY_MAX_LIMIT

    def test_fifo_eviction(self):
        store = InMemoryTraceStore(max_size=3)
        traces = [DecisionTrace(decision_id=f"d{i}") for i in range(5)]
        for t in traces:
            store.store(t)
        assert store.count() == 3
        # d0, d1 被淘汰
        assert store.get(traces[0].trace_id) is None
        assert store.get(traces[1].trace_id) is None
        # d2, d3, d4 仍在
        assert store.get(traces[2].trace_id) is not None
        assert store.get(traces[3].trace_id) is not None
        assert store.get(traces[4].trace_id) is not None

    def test_clear(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace())
        store.store(DecisionTrace())
        store.clear()
        assert store.count() == 0
        assert store.query() == []

    def test_max_size_at_least_one(self):
        store = InMemoryTraceStore(max_size=0)
        assert store._max_size >= 1
        store.store(DecisionTrace())
        assert store.count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. TraceEngine 注入接口
# ═══════════════════════════════════════════════════════════════════════════


class TestTraceEngine:
    def test_init_default_store(self):
        engine = TraceEngine()
        assert engine.store is not None
        assert isinstance(engine.store, InMemoryTraceStore)

    def test_init_custom_store(self):
        store = InMemoryTraceStore(max_size=500)
        engine = TraceEngine(store=store)
        assert engine.store is store

    def test_decision_trace_returns_trace_id(self):
        engine = TraceEngine()
        tid = engine.record_decision_trace(decision_id="d1")
        assert isinstance(tid, str) and len(tid) > 0

    def test_decision_trace_stored(self):
        engine = TraceEngine()
        tid = engine.record_decision_trace(
            decision_id="d1",
            goal_id="g1",
            source="policy_engine",
            reasoning_chain=["analyze", "decide"],
            confidence=0.9,
            outcome="accepted",
            alternatives=["plan_a", "plan_b"],
        )
        trace = engine.get_trace(tid)
        assert trace is not None
        assert isinstance(trace, DecisionTrace)
        assert trace.decision_id == "d1"
        assert trace.goal_id == "g1"
        assert trace.source == "policy_engine"
        assert trace.confidence == 0.9
        assert trace.outcome == "accepted"
        assert trace.alternatives == ["plan_a", "plan_b"]

    def test_reasoning_trace_stored(self):
        engine = TraceEngine()
        tid = engine.record_reasoning_trace(
            reasoning_id="r1",
            source="reasoning_engine",
            observation_ids=["obs-1"],
            knowledge_ids_used=["k-a"],
            reasoning_steps=["step1", "step2"],
            conclusion="conclusion X",
        )
        trace = engine.get_trace(tid)
        assert isinstance(trace, ReasoningTrace)
        assert trace.reasoning_id == "r1"
        assert trace.conclusion == "conclusion X"

    def test_simulation_trace_stored(self):
        engine = TraceEngine()
        tid = engine.record_simulation_trace(
            simulation_id="s1",
            source="sim_engine",
            scenario="test_scenario",
            depth=3,
            branches_explored=7,
            outcome="failure",
            state_delta={"metric": -1},
        )
        trace = engine.get_trace(tid)
        assert isinstance(trace, SimulationTrace)
        assert trace.simulation_id == "s1"
        assert trace.state_delta == {"metric": -1}
        assert "full_state" not in trace.state_delta

    def test_learning_trace_stored(self):
        engine = TraceEngine()
        tid = engine.record_learning_trace(
            learning_id="l1",
            source="learning_engine",
            source_observation_id="obs-42",
            previous_knowledge="old rule",
            new_knowledge="new rule",
            learning_rate_delta=0.01,
        )
        trace = engine.get_trace(tid)
        assert isinstance(trace, LearningTrace)
        assert trace.learning_id == "l1"
        assert trace.learning_rate_delta == 0.01

    def test_memory_trace_stored(self):
        engine = TraceEngine()
        tid = engine.record_memory_trace(
            address="working:goal:g1",
            source="context_manager",
            operation="store",
            content_summary="add_goal: 分析用户输入",
            metadata={"goal_count": 3},
        )
        trace = engine.get_trace(tid)
        assert isinstance(trace, MemoryTrace)
        assert trace.address == "working:goal:g1"
        assert trace.operation == "store"
        assert trace.content_summary == "add_goal: 分析用户输入"
        assert trace.metadata == {"goal_count": 3}

    def test_memory_trace_defaults(self):
        engine = TraceEngine()
        tid = engine.record_memory_trace()
        trace = engine.get_trace(tid)
        assert isinstance(trace, MemoryTrace)
        assert trace.address == ""
        assert trace.operation == ""
        assert trace.content_summary == ""

    def test_emit_event_default_false(self):
        """默认不发射事件。"""
        events = []
        engine = TraceEngine(event_bus=_FakeBus(events))
        engine.record_decision_trace(decision_id="d1")
        assert len(events) == 0

    def test_emit_event_false_explicit(self):
        events = []
        engine = TraceEngine(event_bus=_FakeBus(events))
        engine.record_decision_trace(decision_id="d1", emit_event=False)
        assert len(events) == 0

    def test_emit_event_true(self):
        events = []
        engine = TraceEngine(event_bus=_FakeBus(events))
        engine.record_decision_trace(decision_id="d1", emit_event=True)
        assert len(events) == 1
        assert events[0].event_type == EventType.TRACE_RECORDED
        assert events[0].payload["trace_type"] == "decision"

    def test_emit_event_each_type(self):
        events = []
        engine = TraceEngine(event_bus=_FakeBus(events))
        engine.record_decision_trace(decision_id="d1", emit_event=True)
        engine.record_reasoning_trace(reasoning_id="r1", emit_event=True)
        engine.record_simulation_trace(simulation_id="s1", emit_event=True)
        engine.record_learning_trace(learning_id="l1", emit_event=True)
        engine.record_memory_trace(address="working:goal:g1", emit_event=True)
        assert len(events) == 5
        expected_types = {"decision", "reasoning", "simulation", "learning", "memory"}
        assert {e.payload["trace_type"] for e in events} == expected_types

    def test_query_traces(self):
        engine = TraceEngine()
        engine.record_decision_trace(decision_id="d1", source="s1")
        engine.record_decision_trace(decision_id="d2", source="s2")
        engine.record_reasoning_trace(reasoning_id="r1", source="s1")
        results = engine.query_traces(source="s1")
        assert len(results) == 2

    def test_get_trace_nonexistent(self):
        engine = TraceEngine()
        assert engine.get_trace("nope") is None

    def test_get_trace_count(self):
        engine = TraceEngine()
        assert engine.get_trace_count() == 0
        engine.record_decision_trace(decision_id="d1")
        assert engine.get_trace_count() == 1
        engine.record_decision_trace(decision_id="d2")
        assert engine.get_trace_count() == 2

    def test_reset(self):
        engine = TraceEngine()
        engine.record_decision_trace(decision_id="d1")
        engine.record_decision_trace(decision_id="d2")
        assert engine.get_trace_count() == 2
        engine.reset()
        assert engine.get_trace_count() == 0
        assert engine.query_traces() == []

    def test_decision_without_decision_id(self):
        """decision_id 非必需。"""
        engine = TraceEngine()
        tid = engine.record_decision_trace(source="test")
        trace = engine.get_trace(tid)
        assert isinstance(trace, DecisionTrace)
        assert trace.decision_id == ""

    def test_timestamp_is_iso_format(self):
        engine = TraceEngine()
        tid = engine.record_decision_trace(decision_id="d1")
        trace = engine.get_trace(tid)
        assert isinstance(trace, DecisionTrace)
        # 验证 ISO 格式可解析
        parsed = datetime.fromisoformat(trace.timestamp)
        assert parsed.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════════════
# 5. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestStoreEdgeCases:
    def test_empty_store_query_returns_empty(self):
        store = InMemoryTraceStore()
        assert store.query() == []
        assert store.query(trace_type=TraceType.DECISION) == []
        assert store.query(source="anything") == []

    def test_store_eviction_preserves_recent(self):
        """淘汰后最近写入的可查询到。"""
        store = InMemoryTraceStore(max_size=10)
        for i in range(15):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        # 只有 d5~d14 保留
        assert store.count() == 10
        assert store.get(str(uuid.uuid4())) is None
        # 验证 d14 存在
        results = store.query(limit=100)
        assert len(results) == 10
        # 最新优先
        assert results[0].decision_id == "d14"  # type: ignore[union-attr]

    def test_query_limit_one(self):
        store = InMemoryTraceStore()
        for i in range(5):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        assert len(store.query(limit=1)) == 1

    def test_query_zero_limit_defaults_to_one(self):
        """limit=0 被 clamp 为 1。"""
        store = InMemoryTraceStore()
        for i in range(5):
            store.store(DecisionTrace(decision_id=f"d{i}"))
        results = store.query(limit=0)
        assert len(results) == 1

    def test_multiple_filters(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="d1", source="a"))
        store.store(DecisionTrace(decision_id="d2", source="a"))
        store.store(DecisionTrace(decision_id="d3", source="b"))
        results = store.query(trace_type=TraceType.DECISION, source="a")
        assert len(results) == 2

    def test_mixed_filters_with_decision_id(self):
        store = InMemoryTraceStore()
        store.store(DecisionTrace(decision_id="target", source="a"))
        store.store(DecisionTrace(decision_id="other", source="b"))
        results = store.query(
            trace_type=TraceType.DECISION,
            source="a",
            decision_id="target",
        )
        assert len(results) == 1

    def test_metadata_default_empty(self):
        dt = DecisionTrace()
        assert dt.metadata == {}

    def test_record_with_metadata(self):
        engine = TraceEngine()
        tid = engine.record_decision_trace(
            decision_id="d1",
            metadata={"env": "test", "version": 2},
        )
        trace = engine.get_trace(tid)
        assert isinstance(trace, DecisionTrace)
        assert trace.metadata == {"env": "test", "version": 2}


# ═══════════════════════════════════════════════════════════════════════════
# 6. Graceful Handling — No Event Bus
# ═══════════════════════════════════════════════════════════════════════════


class TestTraceEngineNoEventBus:
    def test_no_event_bus_emit_does_not_raise(self):
        engine = TraceEngine(event_bus=None)
        engine.record_decision_trace(decision_id="d1", emit_event=True)
        assert engine.get_trace_count() == 1

    def test_no_event_bus_record_works(self):
        engine = TraceEngine()
        tid = engine.record_decision_trace(decision_id="d1", source="a")
        assert engine.get_trace(tid) is not None


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


class _FakeBus:
    """伪造的 Event Bus，将发射的事件存入列表。"""

    def __init__(self, events: list[Event]):
        self._events = events

    def publish(self, event: Event, sync: bool = True) -> None:
        self._events.append(event)
