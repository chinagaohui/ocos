"""Tests for ocos.engines.policy_engine - 策略引擎。"""
import pytest
from unittest.mock import MagicMock


class TestPolicyEngine:
    def test_import(self):
        from ocos.engines.policy_engine import PolicyEngine
        assert PolicyEngine is not None

    def test_create(self):
        from ocos.engines.policy_engine import PolicyEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = PolicyEngine(event_bus, working_memory)
        assert engine is not None

    def test_list_rules(self):
        from ocos.engines.policy_engine import PolicyEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = PolicyEngine(event_bus, working_memory)
        rules = engine.list_rules()
        assert isinstance(rules, list)

    def test_list_traces(self):
        from ocos.engines.policy_engine import PolicyEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = PolicyEngine(event_bus, working_memory)
        traces = engine.list_traces()
        assert isinstance(traces, list)

    def test_clear_traces(self):
        from ocos.engines.policy_engine import PolicyEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = PolicyEngine(event_bus, working_memory)
        engine.clear_traces()
