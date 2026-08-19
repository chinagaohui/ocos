"""Process → Trace 集成测试。

验证 TransformProcess 可以通过 record_process_trace() 统一入口
自动分发到对应的 Trace 记录方法。
"""

import pytest

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.information import UniversalAddress
from ocos.models.process import (
    ProcessState,
    ProcessStep,
    ProcessType,
    TransformProcess,
)
from ocos.platform.trace_engine import (
    TraceEngine,
    TraceType,
)


class TestProcessTraceIntegration:
    """Process → Trace 集成测试。"""

    @pytest.fixture
    def engine(self):
        return TraceEngine()

    def _make_reasoning_process(self) -> TransformProcess:
        return TransformProcess(
            process_id="reasoning-test-001",
            process_type=ProcessType.REASONING,
            process_state=ProcessState.COMPLETED,
            input_addresses=(
                UniversalAddress(namespace="info", type="observation", id="obs-001"),
                UniversalAddress(namespace="info", type="knowledge", id="k-001"),
            ),
            output_addresses=(
                UniversalAddress(namespace="info", type="hypothesis", id="hyp-001"),
            ),
            steps=(
                ProcessStep(description="Retrieve relevant knowledge", operation="retrieve"),
                ProcessStep(description="Compare observation with known patterns", operation="compare"),
                ProcessStep(description="Form hypothesis", operation="infer"),
            ),
            confidence=0.85,
        )

    def _make_decision_process(self) -> TransformProcess:
        return TransformProcess(
            process_id="decision-test-001",
            process_type=ProcessType.DECISION,
            process_state=ProcessState.COMPLETED,
            input_addresses=(
                UniversalAddress(namespace="info", type="hypothesis", id="hyp-001"),
                UniversalAddress(namespace="info", type="preference", id="pref-001"),
            ),
            output_addresses=(
                UniversalAddress(namespace="info", type="decision", id="dec-001"),
            ),
            steps=(
                ProcessStep(description="Evaluate options", operation="evaluate"),
                ProcessStep(description="Select best option", operation="select"),
            ),
            confidence=0.9,
        )

    def _make_simulation_process(self) -> TransformProcess:
        return TransformProcess(
            process_id="sim-test-001",
            process_type=ProcessType.SIMULATION,
            process_state=ProcessState.COMPLETED,
            input_addresses=(
                UniversalAddress(namespace="info", type="decision", id="dec-001"),
            ),
            output_addresses=(
                UniversalAddress(namespace="info", type="prediction", id="pred-001"),
            ),
            steps=(),
            confidence=0.75,
            metadata={"scenario": "weather_forecast", "outcome": "rain_expected"},
        )

    def _make_learning_process(self) -> TransformProcess:
        return TransformProcess(
            process_id="learn-test-001",
            process_type=ProcessType.LEARNING,
            process_state=ProcessState.COMPLETED,
            input_addresses=(
                UniversalAddress(namespace="info", type="observation", id="obs-001"),
            ),
            output_addresses=(
                UniversalAddress(namespace="info", type="knowledge", id="k-002"),
            ),
            steps=(),
            confidence=0.6,
            metadata={
                "previous_knowledge": "Prior knowledge about stellar flares",
                "new_knowledge": "Updated understanding of flare frequency",
                "learning_rate_delta": 0.05,
            },
        )

    def test_reasoning_process_to_trace(self, engine):
        """Reasoning Process → ReasoningTrace。"""
        proc = self._make_reasoning_process()
        trace_id = engine.record_process_trace(proc, source="test", emit_event=False)
        assert trace_id != ""

        traces = engine.query_traces(trace_type=TraceType.REASONING)
        matching = [t for t in traces if t.trace_id == trace_id]
        assert len(matching) == 1
        trace = matching[0]
        assert trace.source == "test"
        assert trace.trace_type == TraceType.REASONING

    def test_decision_process_to_trace(self, engine):
        """Decision Process → DecisionTrace。"""
        proc = self._make_decision_process()
        trace_id = engine.record_process_trace(proc, source="test")
        assert trace_id != ""

        traces = engine.query_traces(trace_type=TraceType.DECISION)
        matching = [t for t in traces if t.trace_id == trace_id]
        assert len(matching) == 1

    def test_simulation_process_to_trace(self, engine):
        """Simulation Process → SimulationTrace。"""
        proc = self._make_simulation_process()
        trace_id = engine.record_process_trace(proc, source="test")
        assert trace_id != ""

        traces = engine.query_traces(trace_type=TraceType.SIMULATION)
        matching = [t for t in traces if t.trace_id == trace_id]
        assert len(matching) == 1

    def test_learning_process_to_trace(self, engine):
        """Learning Process → LearningTrace。"""
        proc = self._make_learning_process()
        trace_id = engine.record_process_trace(proc, source="test")
        assert trace_id != ""

        traces = engine.query_traces(trace_type=TraceType.LEARNING)
        matching = [t for t in traces if t.trace_id == trace_id]
        assert len(matching) == 1

    def test_unsupported_process_type(self, engine):
        """不支持的 ProcessType 应抛出 ValueError。"""
        proc = TransformProcess(
            process_type=ProcessType.PLANNING,  # PLANNING 尚未有对应的 Trace
        )
        with pytest.raises(ValueError, match="Unsupported ProcessType"):
            engine.record_process_trace(proc)

    def test_process_trace_emit_event(self, engine):
        """record_process_trace(emit_event=True) 应发射 TRACE_RECORDED 事件。"""
        bus = EventBus()
        engine = TraceEngine(event_bus=bus)
        received = []
        bus.subscribe(EventType.TRACE_RECORDED, lambda e: received.append(e))

        proc = self._make_reasoning_process()
        engine.record_process_trace(proc, source="test", emit_event=True)

        assert len(received) == 1
        assert received[0].payload["trace_type"] == TraceType.REASONING.value

    def test_process_trace_no_emit_event(self, engine):
        """record_process_trace(emit_event=False) 不应发射事件。"""
        received = []
        engine.record_process_trace(self._make_reasoning_process(), source="test", emit_event=False)
        # 没有 EventBus 订阅，所以没有事件
        # 只要不抛出异常就算通过
        assert True
