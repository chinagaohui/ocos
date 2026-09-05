"""Tests for ocos.execution.bridge - 决策执行铰链。"""
import pytest


class TestDecisionBridge:
    def test_import(self):
        from ocos.execution.bridge import DecisionBridge
        assert DecisionBridge is not None

    def test_create(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        assert bridge is not None

    def test_attach_default_handlers(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        result = bridge.attach_default_handlers()
        assert result is bridge

    def test_execute_approved_noop(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        bridge.execute_approved("NOOP", None)

    def test_execute_approved_health_check(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        bridge.execute_approved("HEALTH_CHECK", None)

    def test_process_basic(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        result = bridge.process({'decision': {'type': 'NOOP'}})
        assert result is not None

    def test_process_with_attention_focus(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        result = bridge.process(
            {'decision': {'type': 'NOOP'}},
            attention_focus='test'
        )
        assert result is not None
