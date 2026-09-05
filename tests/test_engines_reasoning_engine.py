"""Tests for ocos.engines.reasoning_engine - 推理引擎。"""
import pytest
from unittest.mock import MagicMock


class TestReasoningEngine:
    def test_import(self):
        from ocos.engines.reasoning_engine import ReasoningEngine
        assert ReasoningEngine is not None

    def test_create(self):
        from ocos.engines.reasoning_engine import ReasoningEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = ReasoningEngine(event_bus, working_memory)
        assert engine is not None

    def test_list_traces(self):
        from ocos.engines.reasoning_engine import ReasoningEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = ReasoningEngine(event_bus, working_memory)
        traces = engine.list_traces()
        assert isinstance(traces, list)

    def test_clear_traces(self):
        from ocos.engines.reasoning_engine import ReasoningEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = ReasoningEngine(event_bus, working_memory)
        engine.clear_traces()
