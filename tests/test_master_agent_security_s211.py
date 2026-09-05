"""S2.11: master_agent 安全门 NameError + fail-closed 回归（白皮书 P1-5）。"""

from __future__ import annotations

import pytest

from ocos.security.manager import AccessDecision


class _Fake:
    """最小依赖桩。"""


@pytest.fixture
def agent_no_security():
    from ocos.agent.master_agent import MasterAgent
    return MasterAgent(
        agent_id="s11-agent",
        identity=_Fake(), goal_stack=_Fake(), intent=_Fake(),
        attention=_Fake(), working_memory=_Fake(),
        capability_manager=_Fake(), execution_manager=_Fake(),
    )  # 不注入 security_manager


class TestSecurityGateFailClosed:
    def test_check_access_no_nameerror_and_deny(self, agent_no_security):
        """未注入 security_manager：不再 NameError，且 fail-closed 返回 DENY。"""
        decision, reason, details = agent_no_security.check_access("src", "query")
        assert decision == AccessDecision.DENY
        assert "not injected" in reason

    def test_sanitize_input_no_nameerror_and_deny(self, agent_no_security):
        text, threats, decision = agent_no_security.sanitize_input("hello")
        assert decision == AccessDecision.DENY
        assert "security not injected" in threats

    def test_with_security_manager_still_works(self):
        from ocos.agent.master_agent import MasterAgent
        from ocos.security.manager import create_security_manager
        agent = MasterAgent(
            agent_id="s11-agent-2",
            identity=_Fake(), goal_stack=_Fake(), intent=_Fake(),
            attention=_Fake(), working_memory=_Fake(),
            capability_manager=_Fake(), execution_manager=_Fake(),
            security_manager=create_security_manager())
        decision, reason, _ = agent.check_access("user", "query")
        assert decision in (AccessDecision.ALLOW, AccessDecision.DENY,
                            AccessDecision.RATE_LIMITED)
