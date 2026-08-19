"""
Goal Runtime Engine — 完整测试套件。

Phase 18 Runtime Foundation 基础验证。

覆盖：
1. 初始化 & 事件订阅
2. set_goal → CREATED → ACTIVE 自动推进
3. GOAL_UPDATED — 只允许 ACTIVE/PAUSED 状态更新
4. 合法状态转移：COMPLETED, FAILED, PAUSED, RESUME, CANCELLED
5. 不合法状态转移验证
6. Superseding 逻辑（旧 Goal → SUPERSEDED，新 Goal 自动 ACTIVE）
7. 过期检查（auto_expired）
8. 查询：get_goal, list_goals, list_active_goals
9. RuntimeResult 形状
10. reset
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from ocos.kernel.abi import EventType, Event, Goal
from ocos.events.event_bus import EventBus
from ocos.models.goal import GoalStatus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.goal_runtime import (
    GoalRuntimeEngine,
    RuntimeResult,
)


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def wm() -> WorkingMemory:
    return WorkingMemory()


@pytest.fixture
def engine(event_bus, wm) -> GoalRuntimeEngine:
    return GoalRuntimeEngine(event_bus, wm)


# ══════════════════════════════════════════════════════════════════════════
# 1. 初始化 & 事件订阅
# ══════════════════════════════════════════════════════════════════════════


class TestInitialization:
    """GoalRuntimeEngine 初始化与订阅管理。"""

    def test_subscribes_to_all_goal_events(self, engine):
        """应订阅所有 9 个 Goal 事件类型。"""
        assert len(engine.subscription_ids) == 9

    def test_starts_empty(self, engine):
        """初始状态应为空。"""
        assert engine.goal_count == 0
        assert engine.active_goal_count == 0

    def test_unsubscribe_all(self, engine):
        """取消所有订阅后，事件应不再触发。"""
        engine.unsubscribe_all()
        assert len(engine.subscription_ids) == 0

        # 发布 GOAL_SET 不应创建任何 Goal
        engine.set_goal(description="should not appear")
        # 取消订阅后，set_goal 仍会发布事件，但订阅已移除，Goal 不会被创建
        assert engine.goal_count == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. set_goal → CREATED → ACTIVE 自动推进
# ══════════════════════════════════════════════════════════════════════════


class TestSetGoal:
    """set_goal：创建 + 自动推进。"""

    def test_set_goal_creates_and_activates(self, engine):
        """set_goal 后 Goal 应处于 ACTIVE 状态。"""
        result = engine.set_goal(description="测试目标", priority=2)

        assert result.success
        assert result.goal_id

        goal = engine.get_goal(result.goal_id)
        assert goal is not None
        assert goal.description == "测试目标"
        assert goal.priority == 2
        assert goal.status == GoalStatus.ACTIVE.value

    def test_set_goal_with_custom_id(self, engine):
        """支持指定 goal_id。"""
        engine.set_goal(description="指定 ID", goal_id="custom-001")
        goal = engine.get_goal("custom-001")
        assert goal is not None
        assert goal.goal_id == "custom-001"
        assert goal.status == GoalStatus.ACTIVE.value

    def test_set_goal_with_parent(self, engine):
        """支持设置 parent_goal_id。"""
        engine.set_goal(description="子目标", parent_goal_id="parent-001")
        all_goals = engine.list_goals(status=None)
        child = [g for g in all_goals if g.parent_goal_id == "parent-001"]
        assert len(child) == 1

    def test_set_goal_default_values(self, engine):
        """默认值完整性：CREATED 过渡到 ACTIVE。"""
        result = engine.set_goal(description="默认值测试")
        goal = engine.get_goal(result.goal_id)
        assert goal is not None
        assert goal.status == GoalStatus.ACTIVE.value  # 自动推进
        assert goal.source == "system"  # 默认 source
        assert goal.success_criterion == ""


# ══════════════════════════════════════════════════════════════════════════
# 3. GOAL_UPDATED — 只允许 ACTIVE/PAUSED 状态更新
# ══════════════════════════════════════════════════════════════════════════


class TestUpdateGoal:
    """Goal 更新验证。"""

    def test_update_description(self, engine):
        """更新 description。"""
        engine.set_goal(description="原始", goal_id="g-upd-1")
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_UPDATED,
            payload={"goal_id": "g-upd-1", "description": "更新后"},
        ))

        goal = engine.get_goal("g-upd-1")
        assert goal is not None
        assert goal.description == "更新后"

    def test_update_priority(self, engine):
        """更新 priority。"""
        engine.set_goal(description="优先级测试", goal_id="g-upd-2", priority=1)
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_UPDATED,
            payload={"goal_id": "g-upd-2", "priority": 3},
        ))

        goal = engine.get_goal("g-upd-2")
        assert goal is not None
        assert goal.priority == 3

    def test_cannot_update_completed_goal(self, engine):
        """COMPLETED 状态的 Goal 不可更新。"""
        engine.set_goal(description="已完成的", goal_id="g-upd-3")
        engine.transition_goal("g-upd-3", GoalStatus.COMPLETED)

        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_UPDATED,
            payload={"goal_id": "g-upd-3", "description": "不应生效"},
        ))

        goal = engine.get_goal("g-upd-3")
        assert goal is not None
        assert goal.description == "已完成的"  # 未变化

    def test_cannot_update_failed_goal(self, engine):
        """FAILED 状态的 Goal 不可更新。"""
        engine.set_goal(description="失败的", goal_id="g-upd-4")
        engine.transition_goal("g-upd-4", GoalStatus.FAILED)

        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_UPDATED,
            payload={"goal_id": "g-upd-4", "priority": 999},
        ))

        goal = engine.get_goal("g-upd-4")
        assert goal is not None
        # priority 应保持默认为 1（set_goal 中 priority=1）
        assert goal.priority == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. 合法状态转移
# ══════════════════════════════════════════════════════════════════════════


class TestStateTransitions:
    """合法状态转移验证。"""

    def test_complete_goal(self, engine):
        """ACTIVE → COMPLETED。"""
        engine.set_goal(description="待完成", goal_id="g-st-1")
        result = engine.transition_goal("g-st-1", GoalStatus.COMPLETED)

        assert result.success
        assert engine.get_goal("g-st-1").status == GoalStatus.COMPLETED.value

    def test_fail_goal(self, engine):
        """ACTIVE → FAILED。"""
        engine.set_goal(description="待失败", goal_id="g-st-2")
        result = engine.transition_goal("g-st-2", GoalStatus.FAILED)

        assert result.success
        assert engine.get_goal("g-st-2").status == GoalStatus.FAILED.value

    def test_cancel_goal(self, engine):
        """ACTIVE → CANCELLED。"""
        engine.set_goal(description="待取消", goal_id="g-st-3")
        result = engine.transition_goal("g-st-3", GoalStatus.CANCELLED)

        assert result.success
        assert engine.get_goal("g-st-3").status == GoalStatus.CANCELLED.value

    def test_pause_and_resume(self, engine):
        """ACTIVE → PAUSED → ACTIVE（暂停恢复）。"""
        engine.set_goal(description="暂停恢复", goal_id="g-st-4")

        result = engine.transition_goal("g-st-4", GoalStatus.PAUSED)
        assert result.success
        assert engine.get_goal("g-st-4").status == GoalStatus.PAUSED.value

        # 恢复
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_RESUMED,
            payload={"goal_id": "g-st-4"},
        ))
        assert engine.get_goal("g-st-4").status == GoalStatus.ACTIVE.value

    def test_active_goal_count_decreases_on_complete(self, engine):
        """COMPLETED 后 active_goal_count 应减 1。"""
        engine.set_goal(description="g1", goal_id="g-st-5")
        engine.set_goal(description="g2", goal_id="g-st-6")
        assert engine.active_goal_count == 2

        engine.transition_goal("g-st-5", GoalStatus.COMPLETED)
        assert engine.active_goal_count == 1

    def test_goal_preserved_after_terminal(self, engine):
        """进入 terminal 状态的 Goal 仍可通过 list_goals(status=None) 查询。"""
        engine.set_goal(description="保留", goal_id="g-st-7")
        engine.transition_goal("g-st-7", GoalStatus.COMPLETED)

        all_goals = engine.list_goals(status=None)
        ids = [g.goal_id for g in all_goals]
        assert "g-st-7" in ids


# ══════════════════════════════════════════════════════════════════════════
# 5. 不合法状态转移验证
# ══════════════════════════════════════════════════════════════════════════


class TestInvalidTransitions:
    """状态转移非法验证。"""

    @pytest.mark.parametrize("terminal_status", [
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.EXPIRED,
    ])
    def test_terminal_state_rejects_all_transitions(self, engine, terminal_status):
        """terminal 状态不应允许任何转移（SUPERSEDED 用 superseder_id 单独测试）。"""
        engine.set_goal(description=f"terminal {terminal_status.value}", goal_id=f"g-it-{id(terminal_status)}")
        engine.transition_goal(f"g-it-{id(terminal_status)}", terminal_status)

        # 尝试转移到 COMPLETED（应被拒绝）
        result = engine.transition_goal(f"g-it-{id(terminal_status)}", GoalStatus.COMPLETED)
        assert not result.success

    def test_cannot_resume_non_paused_goal(self, engine):
        """非 PAUSED 的 Goal 不应接受 GOAL_RESUMED。"""
        engine.set_goal(description="不可恢复", goal_id="g-it-1")
        engine.transition_goal("g-it-1", GoalStatus.COMPLETED)

        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_RESUMED,
            payload={"goal_id": "g-it-1"},
        ))
        # 应保持在 COMPLETED
        assert engine.get_goal("g-it-1").status == GoalStatus.COMPLETED.value

    def test_completed_goal_cannot_be_paused(self, engine):
        """COMPLETED 状态的 Goal 不应接受 PAUSED。"""
        engine.set_goal(description="完成态", goal_id="g-it-2")
        engine.transition_goal("g-it-2", GoalStatus.COMPLETED)

        result = engine.transition_goal("g-it-2", GoalStatus.PAUSED)
        assert not result.success

    def test_unknown_goal_returns_failure(self, engine):
        """不存在的 Goal 应返回失败。"""
        result = engine._handle_state_transition(
            "nonexistent", GoalStatus.COMPLETED, "test",
        )
        assert not result.success
        assert "not found" in result.message.lower()


# ══════════════════════════════════════════════════════════════════════════
# 6. Superseding 逻辑
# ══════════════════════════════════════════════════════════════════════════


class TestSuperseding:
    """Superseding：新 Goal 覆盖旧 Goal。"""

    def test_supersede_active_goal(self, engine):
        """ACTIVE 的 Goal 可被 supersede。"""
        engine.set_goal(description="旧目标", goal_id="g-sup-1")
        engine.set_goal(description="新目标", goal_id="g-sup-2")

        # 发出 SUPERSEDED 事件
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_SUPERSEDED,
            payload={"goal_id": "g-sup-1", "superseder_goal_id": "g-sup-2"},
        ))

        assert engine.get_goal("g-sup-1").status == GoalStatus.SUPERSEDED.value
        assert engine.get_goal("g-sup-2").status == GoalStatus.ACTIVE.value

    def test_supersede_paused_goal(self, engine):
        """PAUSED 的 Goal 也可被 supersede。"""
        engine.set_goal(description="暂停旧", goal_id="g-sup-3")
        engine.transition_goal("g-sup-3", GoalStatus.PAUSED)

        engine.set_goal(description="新", goal_id="g-sup-4")
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_SUPERSEDED,
            payload={"goal_id": "g-sup-3", "superseder_goal_id": "g-sup-4"},
        ))

        assert engine.get_goal("g-sup-3").status == GoalStatus.SUPERSEDED.value

    def test_superseder_auto_activated(self, engine):
        """Superseder 如果是 CREATED 状态，应自动激活。"""
        engine.set_goal(description="旧", goal_id="g-sup-5")
        engine.set_goal(description="新", goal_id="g-sup-6")

        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_SUPERSEDED,
            payload={"goal_id": "g-sup-5", "superseder_goal_id": "g-sup-6"},
        ))

        assert engine.get_goal("g-sup-6").status == GoalStatus.ACTIVE.value

    def test_superseded_no_superseder_id(self, engine):
        """缺少 superseder_goal_id 不应触发 superseding。"""
        engine.set_goal(description="旧", goal_id="g-sup-7")
        engine._event_bus.publish(Event(
            event_type=EventType.GOAL_SUPERSEDED,
            payload={"goal_id": "g-sup-7"},  # 无 superseder_goal_id
        ))

        # Goal 仍应为 ACTIVE（未转移）
        assert engine.get_goal("g-sup-7").status == GoalStatus.ACTIVE.value


# ══════════════════════════════════════════════════════════════════════════
# 7. 过期检查
# ══════════════════════════════════════════════════════════════════════════


class TestExpiration:
    """自动过期检查。"""

    def test_expiration_disabled_by_default(self, engine):
        """默认不启用自动过期。"""
        results = engine.check_expirations()
        assert results == []

    def test_expiration_with_ttl(self, engine, wm):
        """启用 TTL 后，旧 Goal 应过期。"""
        event_bus_local = EventBus()
        engine_local = GoalRuntimeEngine(event_bus_local, wm)
        engine_local.configure_expiration(
            check_interval_seconds=1,
            default_ttl_seconds=3600,  # 1 小时 TTL
        )

        # 手动添加一个已存在的旧 Goal（2 小时前，超过 TTL）
        old_goal = Goal(
            goal_id="g-exp-1",
            description="旧目标",
            status="active",
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        wm.add_goal(old_goal)

        # 再添加一个刚创建的 Goal（未过 TTL）
        fresh_goal = Goal(
            goal_id="g-exp-2",
            description="新目标",
            status="active",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        wm.add_goal(fresh_goal)

        results = engine_local.check_expirations()
        assert len(results) == 1
        assert results[0].goal_id == "g-exp-1"
        assert results[0].success

        # 验证状态
        assert wm.get_goals(status=None)[0].status == GoalStatus.EXPIRED.value

    def test_terminal_goals_not_expired(self, engine, wm):
        """已 terminal 的 Goal 不应被自动过期。"""
        event_bus_local = EventBus()
        engine_local = GoalRuntimeEngine(event_bus_local, wm)
        engine_local.configure_expiration(check_interval_seconds=1, default_ttl_seconds=-1)

        completed = Goal(
            goal_id="g-exp-3",
            description="已完成",
            status="completed",
            timestamp=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        )
        wm.add_goal(completed)

        results = engine_local.check_expirations()
        # terminal 状态的 Goal 不应被过期
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════════════════
# 8. 查询
# ══════════════════════════════════════════════════════════════════════════


class TestQuery:
    """查询操作验证。"""

    def test_get_goal_returns_none_for_missing(self, engine):
        """不存在的 Goal 应返回 None。"""
        assert engine.get_goal("missing") is None

    def test_list_active_goals(self, engine):
        """list_active_goals 只返回 ACTIVE 状态。"""
        engine.set_goal(description="g1", goal_id="g-q-1")
        engine.set_goal(description="g2", goal_id="g-q-2")
        engine.transition_goal("g-q-2", GoalStatus.COMPLETED)

        active = engine.list_active_goals()
        assert len(active) == 1
        assert active[0].goal_id == "g-q-1"

    def test_list_goals_status_filter(self, engine):
        """list_goals 支持状态过滤。"""
        engine.set_goal(description="g1", goal_id="g-q-3")
        engine.transition_goal("g-q-3", GoalStatus.FAILED)
        engine.set_goal(description="g2", goal_id="g-q-4")

        failed = engine.list_goals(status="failed")
        assert len(failed) == 1
        assert failed[0].goal_id == "g-q-3"

        all_goals = engine.list_goals(status=None)
        assert len(all_goals) == 2


# ══════════════════════════════════════════════════════════════════════════
# 9. RuntimeResult 形状
# ══════════════════════════════════════════════════════════════════════════


class TestRuntimeResult:
    """RuntimeResult 结构完整性。"""

    def test_success_result_shape(self, engine):
        """成功结果应包含 goal_id 和成功字段。"""
        result = engine.set_goal(description="结果测试")
        assert result.success
        assert result.goal_id
        assert result.message
        assert result.schema_version == "1.0"

    def test_failure_result_shape(self, engine):
        """失败结果应有错误信息。"""
        result = engine.transition_goal("nonexistent", GoalStatus.COMPLETED)
        assert not result.success
        assert result.goal_id == "nonexistent"
        assert result.message


# ══════════════════════════════════════════════════════════════════════════
# 10. reset
# ══════════════════════════════════════════════════════════════════════════


class TestReset:
    """reset 行为验证。"""

    def test_reset_clears_all_goals(self, engine):
        """reset 后 Goal 列表应为空。"""
        engine.set_goal(description="g1")
        engine.set_goal(description="g2")
        assert engine.goal_count == 2

        engine.reset()
        assert engine.goal_count == 0
        assert engine.active_goal_count == 0

    def test_reset_preserves_subscriptions(self, engine):
        """reset 应保留事件订阅。"""
        engine.set_goal(description="g1")
        engine.reset()

        # 仍可接收新 Goal（订阅活跃）
        engine.set_goal(description="g2")
        assert engine.goal_count == 1
