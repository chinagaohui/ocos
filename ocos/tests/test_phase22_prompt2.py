"""Phase 22 Prompt 2 测试: CognitiveBridge + MasterAgent 集成。

验证:
  1. CognitiveBridge — 各引擎路由（reason / plan / decide / reflect / learn）
  2. CognitiveBridge — 无引擎时的优雅降级
  3. CognitiveBridge — 无自动选择/优化逻辑
  4. CognitiveBridge — 异常不泄露
  5. MasterAgent — LifecycleManager + ControlLoop 集成
  6. MasterAgent — 全链路微观循环 (boot→observe→think→decide→act→reflect→learn)
  7. MasterAgent — BehavioralConstitution 决策拦截
  8. MasterAgent — 异常恢复回到 IDLE
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest

from ocos.agent.cognitive_bridge import CognitiveBridge, BridgeResult
from ocos.agent.lifecycle import (
    LifecycleManager,
    LifecyclePhase,
    MicroState,
)
from ocos.agent.control_loop import ControlLoop
from ocos.agent.goal_types import Goal, GoalLevel, GoalOriginLevel
from ocos.goal.enforcer import GoalOriginEnforcer
from ocos.goal.factory import ConstitutionViolationError
from ocos.agent.master_agent import MasterAgent
from ocos.models.process import TransformProcess, ProcessType
from ocos.kernel.abi import Observation


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


class _MockEngine:
    """模拟引擎 — 记录调用参数，可配置返回值。"""

    def __init__(self, name: str = "mock_engine") -> None:
        self.name = name
        self.calls: list[dict[str, Any]] = []
        self._result: Any = None
        self._should_crash: bool = False

    def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._result is not None:
            return self._result
        return _MockResult(success=True, message=f"{self.name}: ok")


class _MockResult:
    """模拟引擎执行结果。"""
    def __init__(self, success: bool, message: str, **kwargs: Any) -> None:
        self.success = success
        self.message = message
        self.trace_id = kwargs.pop("trace_id", f"trace-{id(self)}")
        self.process_id = kwargs.pop("process_id", f"proc-{id(self)}")
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockConstitution:
    """模拟 BehavioralConstitution — 默认允许，可配置拦截。"""
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow
        self.checks: list[dict[str, Any]] = []

    def check_decision(self, decision: Any, context: dict) -> _MockResult:
        self.checks.append({"decision": decision, "context": context})
        if self.allow:
            return _MockResult(success=True, message="allowed", allowed=True, violations=[])
        return _MockResult(
            success=False,
            message="blocked by constitution",
            allowed=False,
            violations=["test violation"],
        )


class _MockAttention:
    def current_focus(self) -> str | None:
        return "test_focus"

    def reset(self) -> None:
        pass


class _MockGoalStack:
    def peek(self) -> Goal | None:
        return None

    def to_list(self) -> list:
        return []


class _MockIntent:
    def get_intent_description(self) -> str:
        return "test intent"


class _MockWorkingMemory:
    def __init__(self) -> None:
        self.items: list[Any] = []
        self.capacity = 100

    def add(self, item: Any) -> None:
        self.items.append(item)

    def clear(self) -> None:
        self.items.clear()

    def list_items(self) -> list[Any]:
        return list(self.items)


class _MockCapabilityManager:
    def list_capabilities(self) -> list[str]:
        return ["reasoning", "planning"]


class _MockExecutionManager:
    def execute(self, _decision: Any) -> dict:
        return {"status": "done"}

    def is_executing(self) -> bool:
        return False


class _MockIdentity:
    def verify(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return {"agent_id": "test-001"}


@pytest.fixture
def reason_engine() -> _MockEngine:
    return _MockEngine("reasoning")


@pytest.fixture
def plan_engine() -> _MockEngine:
    return _MockEngine("planning")


@pytest.fixture
def decision_engine() -> _MockEngine:
    return _MockEngine("decision")


@pytest.fixture
def reflect_engine() -> _MockEngine:
    return _MockEngine("reflection")


@pytest.fixture
def learn_engine() -> _MockEngine:
    return _MockEngine("learning")


@pytest.fixture
def all_engines(
    reason_engine: _MockEngine,
    plan_engine: _MockEngine,
    decision_engine: _MockEngine,
    reflect_engine: _MockEngine,
    learn_engine: _MockEngine,
) -> dict[str, _MockEngine]:
    return {
        "reasoning": reason_engine,
        "planning": plan_engine,
        "decision": decision_engine,
        "reflection": reflect_engine,
        "learning": learn_engine,
    }


@pytest.fixture
def bridge(all_engines: dict[str, _MockEngine]) -> CognitiveBridge:
    return CognitiveBridge(
        reasoning_engine=all_engines["reasoning"],
        planning_engine=all_engines["planning"],
        decision_engine=all_engines["decision"],
        reflection_engine=all_engines["reflection"],
        learning_engine=all_engines["learning"],
    )


@pytest.fixture
def bridge_no_engines() -> CognitiveBridge:
    return CognitiveBridge()


@pytest.fixture
def constitution() -> _MockConstitution:
    return _MockConstitution(allow=True)


@pytest.fixture
def agent(bridge: CognitiveBridge, constitution: _MockConstitution) -> MasterAgent:
    """构造最小化 MasterAgent 用于集成测试。"""
    return MasterAgent(
        agent_id="test-001",
        identity=_MockIdentity(),
        goal_stack=_MockGoalStack(),
        intent=_MockIntent(),
        attention=_MockAttention(),
        working_memory=_MockWorkingMemory(),
        capability_manager=_MockCapabilityManager(),
        execution_manager=_MockExecutionManager(),
        reasoning_engine=bridge._reasoning,
        planning_engine=bridge._planning,
        decision_engine=bridge._decision,
        reflection_engine=bridge._reflection,
        learning_engine=bridge._learning,
        constitution=constitution,
        current_phase=22,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CognitiveBridge — 路由测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCognitiveBridgeRouting:
    """验证 CognitiveBridge 将显式参数正确路由到引擎。"""

    def test_reason_routes_to_engine(
        self, bridge: CognitiveBridge, reason_engine: _MockEngine
    ) -> None:
        result = bridge.reason(operation="deduction", premises={"inputs": ["test"]})
        assert result.success
        assert result.trace_id != ""
        assert len(reason_engine.calls) == 1
        call = reason_engine.calls[0]
        assert call["operation"] == "deduction"

    def test_plan_routes_to_engine(
        self, bridge: CognitiveBridge, plan_engine: _MockEngine
    ) -> None:
        result = bridge.plan(strategy="top_down", inputs={"goal": "test"})
        assert result.success
        assert len(plan_engine.calls) == 1
        call = plan_engine.calls[0]
        assert call["strategy"] == "top_down"

    def test_decide_routes_to_engine(
        self, bridge: CognitiveBridge, decision_engine: _MockEngine
    ) -> None:
        result = bridge.decide(strategy="scoring")
        assert result.success
        assert len(decision_engine.calls) == 1
        call = decision_engine.calls[0]
        assert call["strategy"] == "scoring"

    def test_reflect_routes_to_engine(
        self, bridge: CognitiveBridge, reflect_engine: _MockEngine
    ) -> None:
        result = bridge.reflect(
            subject_type="action_result",
            subject_id="test-id",
            strategy="standard",
        )
        assert result.success

    def test_learn_routes_to_engine(
        self, bridge: CognitiveBridge, learn_engine: _MockEngine
    ) -> None:
        result = bridge.learn(strategy="supervised")
        assert result.success


class TestCognitiveBridgeGracefulDegradation:
    """验证无引擎时的优雅降级。"""

    def test_reason_no_engine(self, bridge_no_engines: CognitiveBridge) -> None:
        result = bridge_no_engines.reason()
        assert not result.success
        assert "not available" in result.message.lower()

    def test_plan_no_engine(self, bridge_no_engines: CognitiveBridge) -> None:
        result = bridge_no_engines.plan()
        assert not result.success
        assert "not available" in result.message.lower()

    def test_decide_no_engine(self, bridge_no_engines: CognitiveBridge) -> None:
        result = bridge_no_engines.decide()
        assert not result.success
        assert "not available" in result.message.lower()

    def test_reflect_no_engine(self, bridge_no_engines: CognitiveBridge) -> None:
        result = bridge_no_engines.reflect()
        assert not result.success
        assert "not available" in result.message.lower()

    def test_learn_no_engine(self, bridge_no_engines: CognitiveBridge) -> None:
        result = bridge_no_engines.learn()
        assert not result.success
        assert "not available" in result.message.lower()


class TestCognitiveBridgeExceptionSafety:
    """验证引擎异常不泄露。"""

    def test_reason_engine_exception_graceful(
        self, reason_engine: _MockEngine
    ) -> None:
        """引擎异常被 Bridge 优雅捕获。"""
        reason_engine.execute = MagicMock(
            side_effect=RuntimeError("engine crash")
        )
        bridge = CognitiveBridge(reasoning_engine=reason_engine)
        result = bridge.reason(operation="deduction")
        assert not result.success
        assert "failed" in result.message.lower()
        assert len(result.errors) >= 1

    def test_bridge_does_not_auto_select(
        self, bridge: CognitiveBridge
    ) -> None:
        """验证 Bridge 不包含自动选择逻辑。"""
        # reason 不接受模糊参数
        result = bridge.reason(operation="deduction")
        assert result.success
        # to_observation 可用
        obs = result.to_observation(source="test")
        assert isinstance(obs, Observation)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MasterAgent — 集成测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestMasterAgentIntegration:
    """验证 MasterAgent 正确集成 LifecycleManager / ControlLoop / CognitiveBridge。"""

    def test_boot_transitions_to_active(self, agent: MasterAgent) -> None:
        agent.boot()
        assert agent.lifecycle.phase == LifecyclePhase.ACTIVE
        assert agent.lifecycle.is_active()

    def test_observe_creates_observation(self, agent: MasterAgent) -> None:
        agent.boot()
        obs = agent.observe()
        assert isinstance(obs, Observation)
        assert obs.source == "agent"
        assert "agent_id" in obs.content

    def test_think_calls_reasoning(
        self, agent: MasterAgent, reason_engine: _MockEngine
    ) -> None:
        agent.boot()
        agent.observe()
        thought = agent.think()
        assert thought is not None
        assert "bridge_result" in thought
        assert thought["bridge_result"].success

    def test_think_no_observation_uses_cached(self, agent: MasterAgent) -> None:
        agent.boot()
        agent.observe()  # populate _last_observation
        thought = agent.think()
        assert thought is not None

    def test_decide_calls_constitution(
        self, agent: MasterAgent, constitution: _MockConstitution
    ) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        decision = agent.decide()
        assert decision is not None
        assert len(constitution.checks) >= 1
        check = constitution.checks[0]
        assert "context" in check
        assert "decision" in check

    def test_decide_blocked_by_constitution(
        self, agent: MasterAgent, constitution: _MockConstitution
    ) -> None:
        constitution.allow = False
        agent.boot()
        agent.observe()
        agent.think()
        with pytest.raises(ConstitutionViolationError):
            agent.decide()
        # 验证回到 IDLE
        assert agent.lifecycle.micro_state == MicroState.IDLE

    def test_act_calls_execution(self, agent: MasterAgent) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        result = agent.act()
        assert result is not None
        assert "result" in result

    def test_reflect_calls_reflection(
        self, agent: MasterAgent, reflect_engine: _MockEngine
    ) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        agent.act()
        reflection = agent.reflect()
        assert reflection is not None
        assert "bridge_result" in reflection

    def test_learn_transitions_back_to_idle(self, agent: MasterAgent) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        agent.act()
        agent.reflect()
        learning = agent.learn()
        assert learning is not None
        assert agent.lifecycle.micro_state == MicroState.IDLE

    def test_full_micro_cycle(self, agent: MasterAgent) -> None:
        """全链路：boot → observe → think → decide → act → reflect → learn。"""
        agent.boot()
        assert agent.lifecycle.phase == LifecyclePhase.ACTIVE

        obs = agent.observe()
        assert agent.lifecycle.micro_state == MicroState.OBSERVING

        thought = agent.think()
        assert agent.lifecycle.micro_state == MicroState.THINKING

        decision = agent.decide()
        assert agent.lifecycle.micro_state == MicroState.DECIDING

        action = agent.act()
        assert agent.lifecycle.micro_state == MicroState.ACTING

        reflection = agent.reflect()
        assert agent.lifecycle.micro_state == MicroState.REFLECTING

        learning = agent.learn()
        assert agent.lifecycle.micro_state == MicroState.IDLE

        all_results = [obs, thought, decision, action, reflection, learning]
        assert all(r is not None for r in all_results)

    def test_sleep_wake_cycle(self, agent: MasterAgent) -> None:
        agent.boot()
        assert agent.lifecycle.is_active()

        agent.sleep()
        assert agent.lifecycle.is_sleeping()

        agent.wake()
        assert agent.lifecycle.is_active()

    def test_shutdown(self, agent: MasterAgent) -> None:
        agent.boot()
        agent.shutdown()
        assert agent.lifecycle.phase == LifecyclePhase.SHUTDOWN

    def test_get_status_report(self, agent: MasterAgent) -> None:
        agent.boot()
        report = agent.get_status_report()
        assert report["agent_id"] == "test-001"
        assert "lifecycle" in report
        assert "capabilities" in report


class TestMasterAgentExceptionRecovery:
    """验证异常恢复 — 引擎失败时优雅降级，不崩。"""

    def test_think_graceful_on_engine_failure(
        self, agent: MasterAgent, reason_engine: _MockEngine
    ) -> None:
        """引擎抛异常 → bridge 捕获 → Master 优雅降级。"""
        agent.boot()
        agent.observe()
        reason_engine.execute = MagicMock(
            side_effect=RuntimeError("testing failure")
        )
        result = agent.think()
        assert result is not None
        assert result.get("status") == "stub"
        assert result.get("source") == "bridge:fallback"
        assert result.get("reason") == "reasoning_engine_not_registered"
        assert not result["bridge_result"].success

    def test_decide_graceful_on_engine_failure(
        self, agent: MasterAgent, decision_engine: _MockEngine
    ) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        decision_engine.execute = MagicMock(
            side_effect=RuntimeError("decision failure")
        )
        result = agent.decide()
        assert result is not None
        assert result.get("status") == "stub"
        assert result.get("source") == "bridge:fallback"

    def test_act_exception_returns_to_idle(self, agent: MasterAgent) -> None:
        """ExecutionManager 异常: 直接抛（不被 bridge 包裹）。"""
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        agent.execution_manager.execute = MagicMock(
            side_effect=RuntimeError("act failure")
        )
        with pytest.raises(RuntimeError, match="Act phase failed"):
            agent.act()
        assert agent.lifecycle.micro_state == MicroState.IDLE

    def test_reflect_graceful_on_engine_failure(
        self, agent: MasterAgent, reflect_engine: _MockEngine
    ) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        agent.act()
        reflect_engine.execute = MagicMock(
            side_effect=RuntimeError("reflect failure")
        )
        result = agent.reflect()
        assert result is not None
        assert result.get("status") == "stub"
        assert result.get("source") == "bridge:fallback"

    def test_learn_graceful_on_engine_failure(
        self, agent: MasterAgent, learn_engine: _MockEngine
    ) -> None:
        agent.boot()
        agent.observe()
        agent.think()
        agent.decide()
        agent.act()
        agent.reflect()
        learn_engine.execute = MagicMock(
            side_effect=RuntimeError("learn failure")
        )
        result = agent.learn()
        assert result is not None
        assert result.get("status") == "stub"
        assert result.get("source") == "bridge:fallback"
        # 微循环正常结束
        assert agent.lifecycle.micro_state == MicroState.IDLE


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Phase Isolation — 架构隔离验证
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhaseIsolation:
    """验证 Phase 22 未引入违禁模块。"""

    def test_bridge_no_skill_graph_imports(self) -> None:
        """CognitiveBridge 不导入 SkillGraph。"""
        import inspect
        import ocos.agent.cognitive_bridge as cb

        source = inspect.getsource(cb)
        # 只检查 import 行，不检查 docstring 里的提到
        imports = [
            line for line in source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(imports).lower()
        assert "skillgraph" not in import_text
        assert "skill_graph" not in import_text

    def test_bridge_no_capability_selector(self) -> None:
        """CognitiveBridge 不导入 CapabilitySelector。"""
        import inspect
        import ocos.agent.cognitive_bridge as cb

        source = inspect.getsource(cb)
        imports = [
            line for line in source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(imports).lower()
        assert "capability_selector" not in import_text
        assert "capabilityselector" not in import_text

    def test_control_loop_private_to_agent(self, agent: MasterAgent) -> None:
        """ControlLoop 是 MasterAgent 私有成员。"""
        loop = agent.control_loop
        assert isinstance(loop, ControlLoop)
        # 验证 ControlLoop 不被注入到 engine 中
        assert not hasattr(agent.bridge, "control_loop")

    def test_bridge_private_to_agent(self, agent: MasterAgent) -> None:
        """CognitiveBridge 是 MasterAgent 私有成员。"""
        bridge = agent.bridge
        assert isinstance(bridge, CognitiveBridge)
        # Bridge 不暴露到 engine
        for eng_name in ["_reasoning", "_planning", "_decision", "_reflection", "_learning"]:
            eng = getattr(bridge, eng_name, None)
            if eng is not None:
                assert not hasattr(eng, "bridge")

    def test_engine_cannot_create_goal(
        self, bridge: CognitiveBridge
    ) -> None:
        """Engine 不能创建 Goal — 无 create_goal 方法。"""
        assert not hasattr(bridge, "create_goal")
        assert not hasattr(bridge, "goal_factory")
        assert not hasattr(bridge, "goal_enforcer")
