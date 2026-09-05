"""Tests for ocos.agent_orchestration.agent_pool."""

import pytest


class TestAgentPool:

    def test_import_agentpool(self):
        from ocos.agent_orchestration.agent_pool import AgentPool
        assert AgentPool is not None

