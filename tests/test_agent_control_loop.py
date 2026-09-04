"""OCOS agent control_loop 控制回路测试。

ControlLoop 是 MasterAgent 的绝对私有组件，负责：
1. Goal 创建双关卡（Enforcer → Factory）
2. 微观循环编排
3. 生命周期快捷方法
"""

import pytest

from ocos.agent.control_loop import ControlLoop, set_test_caller, clear_test_caller
from ocos.agent.goal_types import GoalLevel, GoalOriginLevel, GoalAuthority
from ocos.agent.lifecycle import LifecycleManager, LifecyclePhase
from ocos.goal.factory import ConstitutionViolationError


def _make_control_loop(phase=22):
    lm = LifecycleManager()
    lm.transition_to_phase(LifecyclePhase.ACTIVE)
    return ControlLoop(lifecycle=lm, current_phase=phase)


class TestGoalCreation:
    """双关卡 Goal 创建验证。"""

    def test_create_task_goal(self):
        cl = _make_control_loop()
        goal = cl.create_goal(
            description="test task",
            level=GoalLevel.TASK,
            origin_level=GoalOriginLevel.SYSTEM,
        )
        assert goal is not None
        assert goal.description == "test task"
        assert goal.level == GoalLevel.TASK

    def test_create_short_term_goal(self):
        cl = _make_control_loop()
        goal = cl.create_goal(
            description="short goal",
            level=GoalLevel.SHORT,
        )
        assert goal.level == GoalLevel.SHORT

    def test_create_long_term_goal(self):
        cl = _make_control_loop()
        goal = cl.create_goal(
            description="long goal",
            level=GoalLevel.LONG,
        )
        assert goal.level == GoalLevel.LONG

    def test_goal_has_unique_id(self):
        cl = _make_control_loop()
        g1 = cl.create_goal("goal 1", origin_level=GoalOriginLevel.SYSTEM)
        g2 = cl.create_goal("goal 2", origin_level=GoalOriginLevel.SYSTEM)
        assert g1.goal_id != g2.goal_id

    def test_goal_with_parent_id(self):
        cl = _make_control_loop()
        parent = cl.create_goal("parent", origin_level=GoalOriginLevel.SYSTEM)
        child = cl.create_goal(
            "child", origin_level=GoalOriginLevel.SYSTEM, parent_id=parent.goal_id
        )
        assert child.parent_id == parent.goal_id


class TestGoalOriginEnforcement:
    """GoalOriginEnforcer 权限约束。"""

    def test_system_origin_allowed(self):
        cl = _make_control_loop()
        goal = cl.create_goal(
            "system goal", origin_level=GoalOriginLevel.SYSTEM
        )
        assert goal is not None

    def test_self_origin_blocked_before_phase25(self):
        """Phase 22 下 SELF 起源目标被拒绝（需要 Phase 25+）。"""
        cl = _make_control_loop(phase=22)
        with pytest.raises(ConstitutionViolationError):
            cl.create_goal(
                "self goal", origin_level=GoalOriginLevel.SELF
            )

    def test_human_origin_requires_authorization(self):
        """HUMAN origin 在 Phase 22 下需要 human_authorized context。"""
        cl = _make_control_loop()
        with pytest.raises(ConstitutionViolationError):
            cl.create_goal(
                "human goal",
                origin_level=GoalOriginLevel.HUMAN,
            )

    def test_human_origin_with_authorization(self):
        cl = _make_control_loop()
        goal = cl.create_goal(
            "human goal",
            origin_level=GoalOriginLevel.HUMAN,
            creator_context={"human_authorized": True},
        )
        assert goal is not None


class TestMicroCycleOrchestration:
    """ControlLoop.run_cycle 编排验证。"""

    def test_run_cycle_delegates_to_lifecycle(self):
        lm = LifecycleManager()
        lm.transition_to_phase(LifecyclePhase.ACTIVE)
        cl = ControlLoop(lifecycle=lm)

        recorded = []
        cl.run_cycle(
            observe_fn=lambda: recorded.append("observe"),
            think_fn=lambda: recorded.append("think"),
            decide_fn=lambda: recorded.append("decide"),
            act_fn=lambda: recorded.append("act"),
            reflect_fn=lambda: recorded.append("reflect"),
            learn_fn=lambda: recorded.append("learn"),
        )
        assert recorded == ["observe", "think", "decide", "act", "reflect", "learn"]

    def test_cycle_not_in_active_raises(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        with pytest.raises(ValueError):
            cl.run_cycle(
                observe_fn=lambda: None,
                think_fn=lambda: None,
                decide_fn=lambda: None,
                act_fn=lambda: None,
                reflect_fn=lambda: None,
                learn_fn=lambda: None,
            )


class TestLifecycleShortcuts:
    """ControlLoop 提供的生命周期快捷方法。"""

    def test_boot_complete(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        assert cl.lifecycle.phase == LifecyclePhase.ACTIVE

    def test_boot_complete_idempotent(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        cl.boot_complete()
        assert cl.lifecycle.phase == LifecyclePhase.ACTIVE

    def test_enter_sleep(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        cl.enter_sleep()
        assert cl.lifecycle.phase == LifecyclePhase.SLEEPING

    def test_wake_from_sleep(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        cl.enter_sleep()
        cl.wake_from_sleep()
        assert cl.lifecycle.phase == LifecyclePhase.ACTIVE

    def test_enter_dream(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        cl.enter_sleep()
        cl.enter_dream()
        assert cl.lifecycle.phase == LifecyclePhase.DREAMING

    def test_shutdown(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        cl.boot_complete()
        cl.shutdown()
        assert cl.lifecycle.phase == LifecyclePhase.SHUTDOWN


class TestProperties:
    """ControlLoop 属性访问。"""

    def test_lifecycle_property(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        assert cl.lifecycle is lm

    def test_enforcer_property(self):
        lm = LifecycleManager()
        cl = ControlLoop(lifecycle=lm)
        assert cl.enforcer is not None

    def test_current_phase_property(self):
        cl = ControlLoop(lifecycle=LifecycleManager(), current_phase=42)
        assert cl.current_phase == 42


class TestCallerContext:
    """测试环境 caller 上下文管理。"""

    def test_default_caller_is_empty(self):
        from ocos.agent.control_loop import get_caller
        clear_test_caller()
        assert get_caller() == ""

    def test_set_and_clear_caller(self):
        set_test_caller("test-agent")
        from ocos.agent.control_loop import get_caller
        assert get_caller() == "test-agent"
        clear_test_caller()
        assert get_caller() == ""
