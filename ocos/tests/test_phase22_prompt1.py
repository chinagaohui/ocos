"""Phase 22 Prompt 1 测试: LifecycleManager + ControlLoop。

验证:
  1. LifecycleManager 宏观阶段转换（有效 + 非法）
  2. LifecycleManager 微观状态转换（有效 + 非法）
  3. ControlLoop Goal 创建 — SYSTEM / HUMAN / 拒绝 SELF
  4. Goal Origin Enforcer 双关卡校验
  5. Phase 21 向后兼容
  6. RLock 线程安全（基本）
  7. run_micro_cycle 异常安全回到 IDLE
  8. contextvars 测试调用方追踪
"""

from __future__ import annotations

import threading
import time

import pytest

from ocos.agent.lifecycle import LifecycleManager, LifecyclePhase, MicroState
from ocos.agent.control_loop import (
    ControlLoop,
    set_test_caller,
    clear_test_caller,
    get_caller,
)
from ocos.agent.goal_types import (
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
)
from ocos.goal.factory import ConstitutionViolationError, GoalFactory


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def lifecycle() -> LifecycleManager:
    lm = LifecycleManager()
    lm.transition_to_phase(LifecyclePhase.ACTIVE)
    return lm


@pytest.fixture
def control_loop(lifecycle: LifecycleManager) -> ControlLoop:
    return ControlLoop(lifecycle=lifecycle, current_phase=22)


# ═══════════════════════════════════════════════════════════════════
# LifecycleManager — 宏观阶段
# ═══════════════════════════════════════════════════════════════════


class TestLifecyclePhaseTransitions:
    """宏观生命周期阶段转换。"""

    def test_initial_phase_is_booting(self) -> None:
        lm = LifecycleManager()
        assert lm.phase == LifecyclePhase.BOOTING

    def test_boot_to_active(self) -> None:
        lm = LifecycleManager()
        lm.transition_to_phase(LifecyclePhase.ACTIVE)
        assert lm.phase == LifecyclePhase.ACTIVE
        assert lm.is_active()

    def test_boot_to_shutdown(self) -> None:
        lm = LifecycleManager()
        lm.transition_to_phase(LifecyclePhase.SHUTDOWN)
        assert lm.phase == LifecyclePhase.SHUTDOWN

    def test_active_to_sleep(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)
        assert lifecycle.phase == LifecyclePhase.SLEEPING
        assert lifecycle.is_sleeping()

    def test_sleep_to_active_wake(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)
        lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)
        assert lifecycle.phase == LifecyclePhase.ACTIVE
        assert lifecycle.is_active()

    def test_sleep_to_dream(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)
        lifecycle.transition_to_phase(LifecyclePhase.DREAMING)
        assert lifecycle.phase == LifecyclePhase.DREAMING

    def test_dream_to_active(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)
        lifecycle.transition_to_phase(LifecyclePhase.DREAMING)
        lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)
        assert lifecycle.phase == LifecyclePhase.ACTIVE

    def test_active_to_shutdown(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SHUTDOWN)
        assert lifecycle.phase == LifecyclePhase.SHUTDOWN

    def test_shutdown_has_no_transitions(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_to_phase(LifecyclePhase.SHUTDOWN)
        with pytest.raises(ValueError):
            lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)

    # 非法转换
    def test_cannot_jump_boot_to_sleep(self) -> None:
        lm = LifecycleManager()
        with pytest.raises(ValueError):
            lm.transition_to_phase(LifecyclePhase.SLEEPING)

    def test_cannot_jump_active_to_boot(self, lifecycle: LifecycleManager) -> None:
        with pytest.raises(ValueError):
            lifecycle.transition_to_phase(LifecyclePhase.BOOTING)


# ═══════════════════════════════════════════════════════════════════
# LifecycleManager — 微观状态
# ═══════════════════════════════════════════════════════════════════


class TestLifecycleMicroTransitions:
    """微观循环状态转换。"""

    def test_idle_to_observing(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_micro(MicroState.OBSERVING)
        assert lifecycle.micro_state == MicroState.OBSERVING

    def test_full_micro_cycle(self, lifecycle: LifecycleManager) -> None:
        for target in [
            MicroState.OBSERVING,
            MicroState.THINKING,
            MicroState.DECIDING,
            MicroState.ACTING,
            MicroState.REFLECTING,
            MicroState.LEARNING,
        ]:
            lifecycle.transition_micro(target)
            assert lifecycle.micro_state == target

    def test_learning_back_to_idle(self, lifecycle: LifecycleManager) -> None:
        for s in [MicroState.OBSERVING, MicroState.THINKING, MicroState.DECIDING,
                   MicroState.ACTING, MicroState.REFLECTING, MicroState.LEARNING]:
            lifecycle.transition_micro(s)
        lifecycle.transition_micro(MicroState.IDLE)
        assert lifecycle.micro_state == MicroState.IDLE

    def test_learning_to_observing(self, lifecycle: LifecycleManager) -> None:
        for s in [MicroState.OBSERVING, MicroState.THINKING, MicroState.DECIDING,
                   MicroState.ACTING, MicroState.REFLECTING, MicroState.LEARNING]:
            lifecycle.transition_micro(s)
        lifecycle.transition_micro(MicroState.OBSERVING)
        assert lifecycle.micro_state == MicroState.OBSERVING

    # 非法微观转换
    def test_micro_only_in_active_phase(self) -> None:
        lm = LifecycleManager()
        with pytest.raises(ValueError, match="ACTIVE"):
            lm.transition_micro(MicroState.OBSERVING)

    def test_no_skip_idle_to_thinking(self, lifecycle: LifecycleManager) -> None:
        with pytest.raises(ValueError):
            lifecycle.transition_micro(MicroState.THINKING)


# ═══════════════════════════════════════════════════════════════════
# run_micro_cycle 异常安全
# ═══════════════════════════════════════════════════════════════════


class TestMicroCycleRecovery:
    """异常后安全回到 IDLE。"""

    def test_cycle_recovers_on_error(self, lifecycle: LifecycleManager) -> None:
        called_observe = False

        def observe():
            nonlocal called_observe
            called_observe = True

        def bad_think():
            raise RuntimeError("engine failure")

        with pytest.raises(RuntimeError, match="engine failure"):
            lifecycle.run_micro_cycle(
                observe_fn=observe,
                think_fn=bad_think,
                decide_fn=lambda: None,
                act_fn=lambda: None,
                reflect_fn=lambda: None,
                learn_fn=lambda: None,
            )

        assert called_observe, "Observe should have run before failure"
        # 异常后状态应该已经重置
        assert lifecycle.micro_state in (MicroState.IDLE, MicroState.OBSERVING)

    def test_cycle_must_start_from_idle(self, lifecycle: LifecycleManager) -> None:
        lifecycle.transition_micro(MicroState.OBSERVING)
        with pytest.raises(ValueError):
            lifecycle.run_micro_cycle(
                observe_fn=lambda: None,
                think_fn=lambda: None,
                decide_fn=lambda: None,
                act_fn=lambda: None,
                reflect_fn=lambda: None,
                learn_fn=lambda: None,
            )


# ═══════════════════════════════════════════════════════════════════
# LifecycleManager — RLock 线程安全
# ═══════════════════════════════════════════════════════════════════


class TestLifecycleThreadSafety:
    """RLock 基本线程安全。"""

    def test_lock_is_rlock(self, lifecycle: LifecycleManager) -> None:
        # Python 3.12+: threading.RLock is a factory, actual type is _thread.RLock
        lock = lifecycle.lock
        assert hasattr(lock, "acquire")
        assert hasattr(lock, "release")
        # Verify re-entrant: acquiring twice should not deadlock
        lock.acquire()
        lock.acquire()
        lock.release()
        lock.release()

    def test_concurrent_phase_reads(self, lifecycle: LifecycleManager) -> None:
        results: list[LifecyclePhase] = []

        def read_phase():
            for _ in range(100):
                results.append(lifecycle.phase)

        threads = [threading.Thread(target=read_phase) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 400
        assert all(p == LifecyclePhase.ACTIVE for p in results)

    def test_freeze_is_safe(self, lifecycle: LifecycleManager) -> None:
        snapshot = lifecycle.freeze()
        assert snapshot["phase"] == "ACTIVE"
        assert snapshot["micro_state"] == "IDLE"


# ═══════════════════════════════════════════════════════════════════
# ControlLoop — Goal 创建
# ═══════════════════════════════════════════════════════════════════


class TestControlLoopGoalCreation:
    """ControlLoop Goal 创建 — 双关卡。"""

    def test_create_system_goal(self, control_loop: ControlLoop) -> None:
        goal = control_loop.create_goal(
            "checkpoint", level=GoalLevel.TASK, origin_level=GoalOriginLevel.SYSTEM
        )
        assert goal.origin_level == GoalOriginLevel.SYSTEM
        assert goal.authority == GoalAuthority.AUTONOMOUS
        assert goal.description == "checkpoint"

    def test_create_human_goal_with_context(self, control_loop: ControlLoop) -> None:
        goal = control_loop.create_goal(
            "user request",
            level=GoalLevel.SHORT,
            origin_level=GoalOriginLevel.HUMAN,
            creator_context={"human_authorized": True},
        )
        assert goal.origin_level == GoalOriginLevel.HUMAN
        assert goal.authority == GoalAuthority.FRAMEWORK

    def test_block_self_goal(self, control_loop: ControlLoop) -> None:
        with pytest.raises(ConstitutionViolationError, match="SELF"):
            control_loop.create_goal(
                "self-improve", origin_level=GoalOriginLevel.SELF
            )

    def test_block_human_without_context(self, control_loop: ControlLoop) -> None:
        with pytest.raises(ConstitutionViolationError, match="human_authorized"):
            control_loop.create_goal(
                "unsanctioned", origin_level=GoalOriginLevel.HUMAN
            )

    def test_block_mission(self, control_loop: ControlLoop) -> None:
        with pytest.raises(ConstitutionViolationError, match="[Mm]ission"):
            control_loop.create_goal(
                "become self-aware",
                level=GoalLevel.MISSION,
                origin_level=GoalOriginLevel.SYSTEM,
            )

    def test_phase22_allows_human_block_self(self) -> None:
        """使用 phase=22 的 enforcer 验证。"""
        cl = ControlLoop(lifecycle=LifecycleManager(), current_phase=22)
        cl.lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)

        # HUMAN allowed
        g = cl.create_goal("ok", origin_level=GoalOriginLevel.HUMAN,
                           creator_context={"human_authorized": True})
        assert g.origin_level == GoalOriginLevel.HUMAN

        # SELF blocked
        with pytest.raises(ConstitutionViolationError):
            cl.create_goal("bad", origin_level=GoalOriginLevel.SELF)


# ═══════════════════════════════════════════════════════════════════
# Phase 21 向后兼容
# ═══════════════════════════════════════════════════════════════════


class TestPhase21BackwardCompatibility:
    """Phase 21 GoalFactory 隔离不受影响。"""

    def test_factory_still_blocks_human_in_phase21(self) -> None:
        with pytest.raises(ConstitutionViolationError, match="Phase 21"):
            GoalFactory.create(
                level=GoalLevel.TASK,
                description="user goal",
                origin_level=GoalOriginLevel.HUMAN,
            )

    def test_factory_allows_system_in_phase21(self) -> None:
        goal = GoalFactory.create(
            level=GoalLevel.TASK,
            description="system operation",
            origin_level=GoalOriginLevel.SYSTEM,
        )
        assert goal.origin_level == GoalOriginLevel.SYSTEM


# ═══════════════════════════════════════════════════════════════════
# contextvars 测试调用方追踪
# ═══════════════════════════════════════════════════════════════════


class TestCallerContext:
    """contextvars 调用方追踪。"""

    def test_default_no_caller(self) -> None:
        assert get_caller() == ""

    def test_set_and_clear_caller(self) -> None:
        set_test_caller("unittest-runner")
        assert get_caller() == "unittest-runner"
        clear_test_caller()
        assert get_caller() == ""

    def test_caller_context_is_isolated(self) -> None:
        """确保 contextvars 在默认情况下为空。"""
        assert get_caller() == ""


# ═══════════════════════════════════════════════════════════════════
# ControlLoop 生命周期快捷方法
# ═══════════════════════════════════════════════════════════════════


class TestControlLoopLifecycle:
    """ControlLoop 包装的 LifecycleManager 快捷方法。"""

    def test_boot_complete_idempotent(self, control_loop: ControlLoop) -> None:
        control_loop.boot_complete()
        control_loop.boot_complete()  # 幂等
        assert control_loop.lifecycle.is_active()

    def test_enter_sleep(self, control_loop: ControlLoop) -> None:
        control_loop.enter_sleep()
        assert control_loop.lifecycle.phase == LifecyclePhase.SLEEPING

    def test_wake_from_sleep(self, control_loop: ControlLoop) -> None:
        control_loop.enter_sleep()
        control_loop.wake_from_sleep()
        assert control_loop.lifecycle.is_active()

    def test_enter_dream(self, control_loop: ControlLoop) -> None:
        control_loop.enter_sleep()
        control_loop.enter_dream()
        assert control_loop.lifecycle.phase == LifecyclePhase.DREAMING

    def test_shutdown(self, control_loop: ControlLoop) -> None:
        control_loop.shutdown()
        assert control_loop.lifecycle.phase == LifecyclePhase.SHUTDOWN


# ═══════════════════════════════════════════════════════════════════
# freeze 快照
# ═══════════════════════════════════════════════════════════════════


class TestFreeze:
    def test_freeze_returns_dict(self, lifecycle: LifecycleManager) -> None:
        snap = lifecycle.freeze()
        assert isinstance(snap, dict)
        assert "phase" in snap
        assert "micro_state" in snap
        assert "agent_status" in snap
