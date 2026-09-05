"""Tests for ocos.execution.bridge."""
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
        assert result is bridge  # returns self

    def test_execute_approved_noop(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        # NOOP is in AUTO_ACTIONS, should not raise
        bridge.execute_approved("NOOP", {})
