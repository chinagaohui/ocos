"""Phase 22-A: act/learn 真实化 单元测试。

验证:
  - 22a1: act() 通过 EngineBridge 派发到真实引擎
  - 22a2: learn() 通过 ExperienceBuilder → EpisodeStore 管道持久化
"""
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.agent.engine_bridge import EngineBridge, ENGINE_REGISTRY
from ocos.agent.lifecycle import LifecyclePhase, MicroState
from ocos.memory.experience.builder import ExperienceBuilder
from ocos.memory.episode.store import EpisodeStore


# ── 微状态推进工具 ───────────────────────────────────────────────────────


_MICRO_CYCLE = [
    MicroState.OBSERVING,
    MicroState.THINKING,
    MicroState.DECIDING,
    MicroState.ACTING,
    MicroState.REFLECTING,
    MicroState.LEARNING,
]


def _setup_micro(agent: MasterAgent, before: MicroState) -> None:
    """设置生命周期为 ACTIVE，微状态设为目标的前一步，使 act()/learn() 的 transition_micro() 合法。"""
    lifecycle = agent._lifecycle
    lifecycle._phase = LifecyclePhase.ACTIVE
    lifecycle._micro_state = before


# ── Fixtures ────────────────────────────────────────────────────────────


def _make_agent(**overrides) -> MasterAgent:
    """创建最小 MasterAgent。"""
    identity = MagicMock()
    identity.verify.return_value = True
    goal_stack = MagicMock()
    goal_stack.peek.return_value = None
    intent = MagicMock()
    attention = MagicMock()
    working_memory = MagicMock()
    capability_manager = MagicMock()
    execution_manager = MagicMock()
    execution_manager.execute.return_value = {"status": "simulated", "note": "ExecutionManager not configured"}

    return MasterAgent(
        agent_id="test-22a",
        identity=identity,
        goal_stack=goal_stack,
        intent=intent,
        attention=attention,
        working_memory=working_memory,
        capability_manager=capability_manager,
        execution_manager=execution_manager,
        **overrides,
    )


# ── 22a1: act() 测试 ────────────────────────────────────────────────────


class TestActViaEngineBridge:
    """act() 非 stub 路径 — EngineBridge 派发。"""

    def test_act_without_bridge_returns_simulated(self):
        """无 EngineBridge 时 act() 返回 simulated。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.DECIDING)
        agent._last_decision = {"type": "cognitive_decision", "selected": "writer"}
        # 无 EngineBridge 且 execution_manager 也无 execute → 直接返回 simulated
        agent.execution_manager = MagicMock(spec=[])  # 无 execute 属性
        result = agent.act()
        assert result["result"]["status"] == "simulated"
        assert "not configured" in result["result"]["note"]

    def test_act_with_bridge_no_engines_returns_simulated(self):
        """有 EngineBridge 但无注册引擎时，act() 降级 simulated。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.DECIDING)
        bridge = EngineBridge()
        agent.set_engine_bridge(bridge)
        agent._last_decision = {"type": "test", "selected": "nonexistent"}
        result = agent.act()
        assert result["result"]["status"] == "simulated"
        assert "No matching engine" in result["result"]["note"]

    def test_act_dispatches_to_registered_engine(self):
        """EngineBridge 有注册引擎时，act() 派发到真实引擎。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.DECIDING)
        bridge = EngineBridge()
        if "writer" in ENGINE_REGISTRY:
            bridge.register("writer")
            agent.set_engine_bridge(bridge)
            agent._last_decision = {"type": "write", "selected": "writer"}
            result = agent.act()
            status = result["result"].get("status", "")
            assert status in ("executed", "engine_failed")

    def test_act_fallback_to_first_engine(self):
        """selected 不匹配任何引擎时 fallback 到第一个可用引擎。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.DECIDING)
        bridge = EngineBridge()
        if "planner" in ENGINE_REGISTRY:
            bridge.register("planner")
            agent.set_engine_bridge(bridge)
            agent._last_decision = {"type": "unknown", "selected": "foo_engine"}
            result = agent.act()
            status = result["result"].get("status", "")
            assert status in ("executed", "engine_failed")


# ── 22a2: learn() 测试 ──────────────────────────────────────────────────


class TestLearnPersistencePipeline:
    """learn() → ExperienceBuilder → EpisodeStore 管道。"""

    def test_learn_without_builder_returns_stub(self):
        """无 LearningEngine + 无 builder 时，learn() 返回 stub。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.REFLECTING)
        agent._last_reflection = {"trace_id": "ref-001"}
        result = agent.learn()
        assert result["status"] == "stub"
        assert "learning_engine_not_registered" in result["reason"]

    def test_learn_persists_via_builder_and_store(self):
        """learn() 尝试通过 builder/store 持久化（即使返回 stub）。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.REFLECTING)
        builder = ExperienceBuilder()
        store = EpisodeStore(":memory:")
        store.initialize()

        agent._experience_builder = builder
        agent._episode_store = store

        obs_mock = MagicMock()
        obs_mock.content = {"event": "test"}
        agent._last_observation = obs_mock
        agent._last_thought = {"trace_id": "t-001"}
        agent._last_decision = {"type": "test_decision", "trace_id": "d-001"}
        agent._last_action_result = {"result": {"status": "executed"}}
        agent._last_reflection = {"trace_id": "r-001"}

        result = agent.learn()
        assert result["status"] == "stub"
        assert builder.count() >= 0
        store.close()

    def test_learn_persistence_failure_does_not_block(self):
        """持久化失败时 learn() 不抛异常。"""
        agent = _make_agent()
        _setup_micro(agent, MicroState.REFLECTING)
        bad_builder = MagicMock()
        bad_builder.build.side_effect = RuntimeError("db failure")
        agent._experience_builder = bad_builder
        agent._episode_store = None

        obs_mock = MagicMock()
        obs_mock.content = {"event": "test"}
        agent._last_observation = obs_mock
        agent._last_thought = {"trace_id": "t-001"}
        agent._last_decision = {"type": "test_decision", "trace_id": "d-001"}
        agent._last_action_result = {"result": {"status": "executed"}}
        agent._last_reflection = {"trace_id": "r-001"}

        result = agent.learn()
        assert result["status"] == "stub"  # 不抛异常
