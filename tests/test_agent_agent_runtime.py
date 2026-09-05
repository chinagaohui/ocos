"""Tests for ocos.agent.agent_runtime."""
import pytest
from unittest.mock import MagicMock


class TestAgentRuntime:
    def test_import(self):
        from ocos.agent.agent_runtime import AgentRuntime
        assert AgentRuntime is not None

    def test_create(self):
        from ocos.agent.agent_runtime import AgentRuntime
        agent = MagicMock()
        runtime = AgentRuntime(agent=agent)
        assert runtime is not None

    def test_boot(self):
        from ocos.agent.agent_runtime import AgentRuntime
        agent = MagicMock()
        runtime = AgentRuntime(agent=agent)
        runtime.boot()
        assert runtime is not None

    def test_get_full_status(self):
        from ocos.agent.agent_runtime import AgentRuntime
        agent = MagicMock()
        runtime = AgentRuntime(agent=agent)
        status = runtime.get_full_status()
        assert isinstance(status, dict)

    def test_get_stability_report(self):
        from ocos.agent.agent_runtime import AgentRuntime
        agent = MagicMock()
        runtime = AgentRuntime(agent=agent)
        report = runtime.get_stability_report()
        assert isinstance(report, dict)
