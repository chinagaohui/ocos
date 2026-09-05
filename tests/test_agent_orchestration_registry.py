"""Tests for ocos.agent_orchestration.registry."""

import pytest


class TestAgentRegistry:

    def test_import_agentregistry(self):
        from ocos.agent_orchestration.registry import AgentRegistry
        assert AgentRegistry is not None

