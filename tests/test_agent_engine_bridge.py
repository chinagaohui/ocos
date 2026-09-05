"""Tests for ocos.engine_bridge - 引擎桥接。"""
import pytest
from unittest.mock import MagicMock


class TestEngineBridge:
    def test_import(self):
        from ocos.agent.engine_bridge import EngineBridge
        assert EngineBridge is not None

    def test_create(self):
        from ocos.agent.engine_bridge import EngineBridge
        bridge = EngineBridge()
        assert bridge is not None
