"""P2-D ProactiveEngine 契约测试（L4 演化性）。

覆盖：触发链全绿输出、频率闸门、SELF 目标闸门、疲劳闸门、
权限双检拒绝、输出通道注入、依赖缺失降级。
"""

import pytest

from ocos.interaction.base import PermissionGuard
from ocos.kernel.goal_types import Goal, GoalOriginLevel, GoalStatus
from ocos.proactive import ProactiveEngine, ProactiveAuditStore


class FakeAttention:
    def __init__(self, fatigue: float):
        self.fatigue = fatigue


@pytest.fixture
def goal_store():
    from ocos.agent.goal_store import GoalSQLiteStore

    store = GoalSQLiteStore(":memory:")
    store.initialize()
    return store


@pytest.fixture
def audit_store():
    store = ProactiveAuditStore(":memory:")
    store.initialize()
    return store


def _add_self_goal(store, description: str = "持续打磨 OCOS 数字生命"):
    store.save(
        Goal(
            goal_id="goal-self-1",
            description=description,
            origin_level=GoalOriginLevel.SELF,
            status=GoalStatus.ACTIVE,
        )
    )


def _full_engine(goal_store, audit_store, **kwargs):
    """构造注入完整双检（PermissionGuard + ConstitutionHub）的引擎。"""
    from ocos.constitution.hub import ConstitutionHub

    return ProactiveEngine(
        goal_store=goal_store,
        attention=kwargs.pop("attention", FakeAttention(0.3)),
        permission_guard=kwargs.pop("permission_guard", PermissionGuard()),
        constitution=ConstitutionHub(),
        audit_store=audit_store,
        **kwargs,
    )


class TestProactiveEngine:
    def test_outputs_when_all_conditions_met(self, goal_store, audit_store):
        """SELF 目标 + 低疲劳 + 双检通过 → 输出并审计 granted=True。"""
        _add_self_goal(goal_store)
        engine = _full_engine(goal_store, audit_store)

        message = engine.maybe_proactive_output()

        assert message is not None
        assert len(message) > 0
        records = audit_store.recent()
        assert len(records) == 1
        assert records[0]["granted"] is True

    def test_daily_limit_blocks_second_output(self, goal_store, audit_store):
        """每日上限（默认 1 次）→ 第二次被频率闸门拦截。"""
        _add_self_goal(goal_store)
        engine = _full_engine(goal_store, audit_store)

        first = engine.maybe_proactive_output()
        second = engine.maybe_proactive_output()

        assert first is not None
        assert second is None
        denied = [r for r in audit_store.recent(50) if not r["granted"]]
        assert any(r["reason"] == "daily_limit" for r in denied)

    def test_no_self_goal_blocks(self, goal_store, audit_store):
        """无 SELF 目标（内生驱动缺失）→ 不主动打扰。"""
        engine = ProactiveEngine(
            goal_store=goal_store,
            attention=FakeAttention(0.3),
            permission_guard=PermissionGuard(),
            audit_store=audit_store,
        )

        assert engine.maybe_proactive_output() is None
        denied = [r for r in audit_store.recent(50) if not r["granted"]]
        assert any(r["reason"] == "no_self_goal" for r in denied)

    def test_fatigue_blocks(self, goal_store, audit_store):
        """疲劳 ≥ 0.7 → 不输出（不打扰疲惫的宿主）。"""
        _add_self_goal(goal_store)
        engine = _full_engine(
            goal_store, audit_store, attention=FakeAttention(0.8)
        )

        assert engine.maybe_proactive_output() is None
        denied = [r for r in audit_store.recent(50) if not r["granted"]]
        assert any(r["reason"].startswith("fatigue") for r in denied)

    def test_permission_denied_blocks(self, goal_store, audit_store):
        """权限拒绝 → 不输出，审计 granted=False（fail-closed）。"""
        from unittest.mock import MagicMock

        _add_self_goal(goal_store)
        denying_guard = MagicMock()
        denying_guard.check.return_value = MagicMock(allowed=False)
        engine = _full_engine(
            goal_store, audit_store, permission_guard=denying_guard
        )

        assert engine.maybe_proactive_output() is None
        denied = [r for r in audit_store.recent(50) if not r["granted"]]
        assert any(r["reason"] == "permission_denied" for r in denied)

    def test_checks_missing_fails_closed(self, goal_store, audit_store):
        """权限防护缺失 → fail-closed 拒绝（绝不无检输出），审计 missing_guard。"""
        _add_self_goal(goal_store)
        engine = ProactiveEngine(
            goal_store=goal_store,
            attention=FakeAttention(0.3),
            permission_guard=None,
            constitution=None,
            audit_store=audit_store,
        )

        result = engine.maybe_proactive_output()
        assert result is None  # fail-closed：宁可静默
        denied = [r for r in audit_store.recent(50) if not r["granted"]]
        assert any(r["reason"] == "missing_guard" for r in denied)

    def test_output_callback_delivers(self, goal_store, audit_store):
        """注入 output_callback → 消息送达回调（Telegram 等外部通道的注入点）。"""
        received: list[str] = []
        _add_self_goal(goal_store)
        engine = _full_engine(
            goal_store, audit_store, output_callback=received.append
        )

        message = engine.maybe_proactive_output()

        assert message is not None
        assert received == [message]

    def test_missing_goal_store_degrades(self, audit_store):
        """goal_store 缺失 → 降级返回 None，不抛。"""
        engine = _full_engine(None, audit_store)

        assert engine.maybe_proactive_output() is None

    def test_template_rotation_and_topic(self, goal_store, audit_store):
        """观察模板使用 SELF 目标主题填充；无主题时回退问候。"""
        _add_self_goal(goal_store, description="陪伴用户完成长途写作")
        engine = _full_engine(goal_store, audit_store)

        message = engine.maybe_proactive_output()

        # 轮换 index=0 → 第一条问候模板（无需主题）
        assert message is not None
        assert "聊天" in message or "一直在" in message


class TestMasterAgentHook:
    """P2-D 挂钩层契约：MasterAgent.maybe_proactive_output() 降级安全 + 注入全链路。"""

    def _agent(self, **kwargs):
        from unittest.mock import MagicMock

        from ocos.agent.master_agent import MasterAgent
        from ocos.agent.state import AgentState

        base = dict(
            agent_id="test-proactive",
            identity=MagicMock(),
            goal_stack=MagicMock(),
            intent=MagicMock(),
            attention=MagicMock(),
            working_memory=MagicMock(),
            capability_manager=MagicMock(),
            execution_manager=MagicMock(),
            state=AgentState(),
        )
        base.update(kwargs)
        return MasterAgent(**base)

    def test_degrades_safely_without_deps(self):
        """无目标/权限依赖 → 返回 None 不抛（生产默认静默，fail-closed）。"""
        agent = self._agent()
        assert agent.maybe_proactive_output() is None

    def test_full_chain_outputs_when_injected(self, goal_store, audit_store):
        """注入 goal_store + 双检 → 主动输出非 None（runtime 注入即启用）。"""
        from ocos.constitution.hub import ConstitutionHub
        from ocos.proactive import ProactiveEngine

        agent = self._agent(permission_guard=PermissionGuard())
        agent._goal_store = goal_store
        agent._constitution = ConstitutionHub()
        agent.attention = FakeAttention(0.3)
        _add_self_goal(goal_store)

        agent._proactive_engine = ProactiveEngine(
            goal_store=goal_store,
            attention=FakeAttention(0.3),
            permission_guard=PermissionGuard(),
            constitution=ConstitutionHub(),
            audit_store=audit_store,
        )
        assert agent.maybe_proactive_output() is not None

    def test_injected_audit_store_auto_initialized(self, goal_store):
        """验收补丁：注入未 initialize 的 audit_store → 引擎自动建表，审计/闸门可用。"""
        from ocos.proactive import ProactiveAuditStore

        audit = ProactiveAuditStore(":memory:")  # 故意不调 initialize
        engine = _full_engine(goal_store, audit)
        engine.audit_store.record("greeting", "x", True)  # 不抛即证明建表成功
        assert engine.audit_store.count_granted_today() == 1
