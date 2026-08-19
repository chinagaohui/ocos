"""
B1 Context Manager — 完整测试套件。

覆盖：
- WorkingMemory CRUD
- Context 冻结性验证
- ContextManager 组装逻辑
- Event Bus 集成（自动重建）
- 边界条件
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from ocos.kernel.abi import Goal, EventType, Event
from ocos.runtime.context_manager import (
    WorkingMemory,
    Context,
    ContextManager,
)
from ocos.events.event_bus import EventBus


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_goals() -> tuple[Goal, ...]:
    return (
        Goal(goal_id="g1", description="分析用户输入", priority=2, status="active"),
        Goal(goal_id="g2", description="生成回复草稿", priority=1, status="active"),
        Goal(goal_id="g3", description="安全检查", priority=3, status="paused"),
    )


@pytest.fixture
def wm() -> WorkingMemory:
    return WorkingMemory()


@pytest.fixture
def wm_with_data(sample_goals, wm) -> WorkingMemory:
    for g in sample_goals:
        wm.add_goal(g)
    wm.set_preference("language", "zh-CN")
    wm.set_preference("verbosity", "concise")
    wm.register_tool("web_search")
    wm.register_tool("code_exec")
    return wm


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def ctxmgr(wm_with_data) -> ContextManager:
    return ContextManager(wm_with_data)


@pytest.fixture
def ctxmgr_with_bus(wm_with_data, event_bus) -> ContextManager:
    return ContextManager(wm_with_data, event_bus)


# ══════════════════════════════════════════════════════════════════════════
# WorkingMemory 测试
# ══════════════════════════════════════════════════════════════════════════

class TestWorkingMemory:

    def test_add_and_retrieve_goal(self, wm):
        g = Goal(goal_id="g1", description="测试目标", priority=1)
        wm.add_goal(g)
        goals = wm.get_goals()
        assert len(goals) == 1
        assert goals[0].goal_id == "g1"

    def test_get_goals_sorted_by_priority(self, wm):
        wm.add_goal(Goal(goal_id="low", description="低优先级", priority=0, status="active"))
        wm.add_goal(Goal(goal_id="high", description="高优先级", priority=3, status="active"))
        wm.add_goal(Goal(goal_id="mid", description="中优先级", priority=1, status="active"))
        goals = wm.get_goals()
        assert [g.goal_id for g in goals] == ["high", "mid", "low"]

    def test_get_goals_filters_by_status(self, wm):
        wm.add_goal(Goal(goal_id="a1", description="活跃", priority=1, status="active"))
        wm.add_goal(Goal(goal_id="c1", description="完成", priority=1, status="completed"))
        active = wm.get_goals(status="active")
        assert len(active) == 1
        assert active[0].goal_id == "a1"
        all_goals = wm.get_goals(status=None)
        assert len(all_goals) == 2

    def test_remove_goal(self, wm):
        wm.add_goal(Goal(goal_id="g1", description="移除测试"))
        assert wm.goal_count == 1
        wm.remove_goal("g1")
        assert wm.goal_count == 0

    def test_update_goal_status(self, wm):
        wm.add_goal(Goal(goal_id="g1", description="更新", priority=1, status="active"))
        assert wm.update_goal_status("g1", "completed") is True
        goals = wm.get_goals(status="completed")
        assert len(goals) == 1
        assert goals[0].goal_id == "g1"
        # 更新不存在的 goal
        assert wm.update_goal_status("nonexistent", "active") is False

    def test_preferences(self, wm):
        wm.set_preference("theme", "dark")
        wm.set_preference("font_size", 14)
        assert wm.get_preference("theme") == "dark"
        assert wm.get_preference("unknown", "default") == "default"
        all_prefs = wm.get_all_preferences()
        assert all_prefs == {"theme": "dark", "font_size": 14}
        wm.clear_preferences()
        assert wm.get_all_preferences() == {}

    def test_tools(self, wm):
        wm.register_tool("search")
        wm.register_tool("calc")
        assert wm.has_tool("search") is True
        assert wm.has_tool("unknown") is False
        assert wm.get_available_tools() == ["calc", "search"]
        wm.unregister_tool("search")
        assert wm.has_tool("search") is False

    def test_clear(self, wm):
        wm.add_goal(Goal(goal_id="g1", description="测试"))
        wm.set_preference("key", "val")
        wm.register_tool("hammer")
        wm.clear()
        assert wm.goal_count == 0
        assert wm.get_all_preferences() == {}
        assert wm.get_available_tools() == []

    def test_active_goal_count(self, wm):
        wm.add_goal(Goal(goal_id="g1", description="活跃1", priority=1, status="active"))
        wm.add_goal(Goal(goal_id="g2", description="活跃2", priority=2, status="active"))
        wm.add_goal(Goal(goal_id="g3", description="暂停", priority=3, status="paused"))
        assert wm.active_goal_count == 2

    def test_empty_wm(self, wm):
        assert wm.goal_count == 0
        assert wm.active_goal_count == 0
        assert wm.get_goals() == []
        assert wm.get_available_tools() == []


# ══════════════════════════════════════════════════════════════════════════
# WorkingMemory EventBus 桥接测试（Phase 2）
# ══════════════════════════════════════════════════════════════════════════

class TestWorkingMemoryEventBus:

    @pytest.fixture
    def wm_with_bus(self, event_bus) -> WorkingMemory:
        return WorkingMemory(event_bus)

    def test_no_event_bus_compatible(self, wm):
        """不传 EventBus 时所有操作正常运行。"""
        g = Goal(goal_id="g1", description="无总线测试")
        wm.add_goal(g)
        assert wm.get_goals()[0].goal_id == "g1"
        wm.set_preference("k", "v")
        assert wm.get_preference("k") == "v"
        assert wm.update_goal_status("g1", "completed") is True
        assert wm.active_goal_count == 0
        wm.clear()
        assert wm.goal_count == 0

    def test_add_goal_emits_memory_stored(self, wm_with_bus, event_bus):
        """add_goal() 发射 MEMORY_STORED 事件。"""
        received = []

        def listener(event: Event):
            received.append(event)

        event_bus.subscribe(EventType.MEMORY_STORED, listener)
        g = Goal(goal_id="g1", description="新目标")
        wm_with_bus.add_goal(g)
        assert len(received) == 1
        assert received[0].event_type == EventType.MEMORY_STORED
        assert received[0].payload["operation"] == "add_goal"
        assert received[0].payload["memory_id"] == "g1"

    def test_remove_goal_emits_memory_stored(self, wm_with_bus, event_bus):
        """remove_goal() 发射 MEMORY_STORED 事件。"""
        received = []

        def listener(event: Event):
            received.append(event)

        event_bus.subscribe(EventType.MEMORY_STORED, listener)
        wm_with_bus.add_goal(Goal(goal_id="g-rm"))
        received.clear()  # 清除 add 事件
        wm_with_bus.remove_goal("g-rm")
        assert len(received) == 1
        assert received[0].payload["operation"] == "remove_goal"
        assert received[0].payload["memory_id"] == "g-rm"

    def test_get_goals_emits_memory_retrieved(self, wm_with_bus, event_bus):
        """get_goals() 发射 MEMORY_RETRIEVED 事件。"""
        received = []

        def listener(event: Event):
            received.append(event)

        event_bus.subscribe(EventType.MEMORY_RETRIEVED, listener)
        g = Goal(goal_id="g-rd", description="读取测试")
        wm_with_bus.add_goal(g)
        # add_goal 发射了 MEMORY_STORED, 不会匹配 MEMORY_RETRIEVED
        wm_with_bus.get_goals()
        assert len(received) == 1
        assert received[0].event_type == EventType.MEMORY_RETRIEVED
        assert received[0].payload["operation"] == "get_goals"

    def test_clear_emits_memory_stored(self, wm_with_bus, event_bus):
        """clear() 发射 MEMORY_STORED + 'operation=clear'"""
        received = []

        def listener(event: Event):
            received.append(event)

        event_bus.subscribe(EventType.MEMORY_STORED, listener)
        wm_with_bus.add_goal(Goal(goal_id="g-cl"))
        received.clear()  # 清除 add 事件
        wm_with_bus.clear()
        assert any(e.payload["operation"] == "clear" for e in received)

    def test_multiple_operations_event_count(self, wm_with_bus, event_bus):
        """多次 add 操作产生相应数量的事件。"""
        received = []

        def listener(event: Event):
            received.append(event)

        event_bus.subscribe(EventType.MEMORY_STORED, listener)
        for i in range(3):
            wm_with_bus.add_goal(Goal(goal_id=f"g{i}", description=f"目标{i}"))
        assert len(received) == 3
        assert received[0].payload["memory_id"] == "g0"


# ══════════════════════════════════════════════════════════════════════════
# Context 冻结性测试
# ══════════════════════════════════════════════════════════════════════════

class TestContextIsFrozen:

    def test_context_is_frozen(self):
        ctx = Context()
        with pytest.raises(FrozenInstanceError):
            ctx.goals = []  # type: ignore[misc]

    def test_context_default_fields(self):
        ctx = Context()
        assert ctx.goals == []
        assert ctx.tasks == []
        assert ctx.preferences == {}
        assert ctx.available_tools == []
        assert ctx.schema_version == "1.0.0"
        assert len(ctx.context_id) == 32  # uuid hex

    def test_context_with_data(self, sample_goals):
        goals = list(sample_goals)
        ctx = Context(
            goals=goals,
            tasks=["任务1", "任务2"],
            preferences={"lang": "en"},
            available_tools=["search"],
        )
        assert len(ctx.goals) == 3
        assert ctx.tasks == ["任务1", "任务2"]
        assert ctx.preferences == {"lang": "en"}
        assert ctx.available_tools == ["search"]

    def test_context_goal_count(self, sample_goals):
        ctx = Context(goals=list(sample_goals))
        assert ctx.goal_count == 3

    def test_highest_priority_goal(self):
        g1 = Goal(goal_id="g1", description="普通", priority=1)
        g2 = Goal(goal_id="g2", description="紧急", priority=3)
        g3 = Goal(goal_id="g3", description="低", priority=0)
        ctx = Context(goals=[g1, g2, g3])
        assert ctx.highest_priority_goal is not None
        assert ctx.highest_priority_goal.goal_id == "g2"

    def test_highest_priority_goal_empty(self):
        ctx = Context()
        assert ctx.highest_priority_goal is None


# ══════════════════════════════════════════════════════════════════════════
# ContextManager 组装逻辑测试
# ══════════════════════════════════════════════════════════════════════════

class TestContextManager:

    def test_build_context_from_active_goals(self, ctxmgr, sample_goals):
        """默认只包含活跃目标，排除 pause/completed/abandoned。"""
        ctx = ctxmgr.build_context()
        assert len(ctx.goals) == 2  # g1(active), g2(active); g3(paused 排除)
        goal_ids = {g.goal_id for g in ctx.goals}
        assert "g1" in goal_ids
        assert "g2" in goal_ids
        assert "g3" not in goal_ids

    def test_build_context_sorts_by_priority(self, ctxmgr):
        ctx = ctxmgr.build_context()
        assert len(ctx.goals) >= 2
        prev_priority = float("inf")
        for g in ctx.goals:
            assert g.priority <= prev_priority
            prev_priority = g.priority

    def test_build_context_with_specific_goal_ids(self, ctxmgr, sample_goals):
        ctx = ctxmgr.build_context(goal_ids=["g1"])
        assert len(ctx.goals) == 1
        assert ctx.goals[0].goal_id == "g1"

    def test_build_context_with_additional_tasks(self, ctxmgr):
        ctx = ctxmgr.build_context(additional_tasks=["额外任务"])
        # g1 description -> tasks
        assert any("分析用户输入" in t for t in ctx.tasks)
        assert "额外任务" in ctx.tasks

    def test_build_context_inherits_preferences(self, ctxmgr):
        ctx = ctxmgr.build_context()
        assert ctx.preferences.get("language") == "zh-CN"

    def test_build_context_inherits_tools(self, ctxmgr):
        ctx = ctxmgr.build_context()
        assert "web_search" in ctx.available_tools
        assert "code_exec" in ctx.available_tools

    def test_get_active_context(self, ctxmgr):
        assert ctxmgr.get_active_context() is None
        ctx = ctxmgr.build_context()
        assert ctxmgr.get_active_context() is ctx  # same object

    def test_build_context_updates_active(self, ctxmgr):
        ctx1 = ctxmgr.build_context()
        ctx2 = ctxmgr.build_context()
        assert ctxmgr.get_active_context() is ctx2  # last one wins

    def test_working_memory_property(self, ctxmgr, wm_with_data):
        assert ctxmgr.working_memory is wm_with_data

    def test_empty_wm_context(self, wm):
        mgr = ContextManager(wm)
        ctx = mgr.build_context()
        assert ctx.goals == []
        assert ctx.tasks == []
        assert ctx.preferences == {}
        assert ctx.available_tools == []

    def test_build_context_task_extraction(self, wm):
        """验证任务从 Goal.description 拆解正确。"""
        wm.add_goal(Goal(
            goal_id="g1",
            description="第一步: 解析输入。第二步: 验证格式。第三步: 执行处理",
            priority=1,
            status="active",
        ))
        mgr = ContextManager(wm)
        ctx = mgr.build_context()
        assert any("第一步" in t for t in ctx.tasks)
        assert any("第二步" in t for t in ctx.tasks)
        assert any("第三步" in t for t in ctx.tasks)


# ══════════════════════════════════════════════════════════════════════════
# Event Bus 集成测试
# ══════════════════════════════════════════════════════════════════════════

class TestContextManagerEventBus:

    def test_subscribes_on_init(self, wm, event_bus):
        mgr = ContextManager(wm, event_bus)
        assert event_bus.subscriber_count(EventType.GOAL_SET) >= 1
        assert event_bus.subscriber_count(EventType.GOAL_UPDATED) >= 1
        assert event_bus.subscriber_count(EventType.GOAL_COMPLETED) >= 1

    def test_no_subscription_without_bus(self, ctxmgr):
        # 无 Event Bus 时不自动订阅（不会报错）
        pass

    def test_goal_set_auto_rebuilds_context(self, wm, event_bus):
        mgr = ContextManager(wm, event_bus)
        # 初始空 Context
        ctx_before = mgr.build_context()
        assert len(ctx_before.goals) == 0

        # 通过 Event Bus 发布 GOAL_SET
        event = Event(
            event_type=EventType.GOAL_SET,
            payload={
                "goal_id": "g-auto",
                "description": "自动触发目标",
                "priority": 5,
            },
        )
        event_bus.publish(event, sync=True)

        # 验证 Context 已自动重建并包含新目标
        ctx_after = mgr.get_active_context()
        assert ctx_after is not None
        goal_ids = {g.goal_id for g in ctx_after.goals}
        assert "g-auto" in goal_ids

    def test_goal_completed_auto_rebuild(self, wm, event_bus):
        wm.add_goal(Goal(goal_id="gc1", description="会完成的目标", priority=1))
        mgr = ContextManager(wm, event_bus)
        mgr.build_context()
        assert mgr.get_active_context() is not None
        assert wm.active_goal_count == 1

        # 发布 GOAL_COMPLETED
        event = Event(
            event_type=EventType.GOAL_COMPLETED,
            payload={"goal_id": "gc1", "outcome": "success"},
        )
        event_bus.publish(event, sync=True)

        # 验证工作记忆和 Context 已更新
        assert wm.active_goal_count == 0
        ctx = mgr.get_active_context()
        assert ctx is not None
        assert all(g.status != "active" for g in ctx.goals)

    def test_unsubscribe_cleans_up(self, wm, event_bus):
        mgr = ContextManager(wm, event_bus)
        before = event_bus.subscriber_count(EventType.GOAL_SET)
        mgr.unsubscribe()
        assert event_bus.subscriber_count(EventType.GOAL_SET) == before - 1
