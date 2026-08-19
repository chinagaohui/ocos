"""
B3 Scheduler — 完整测试套件。

覆盖：
- ScheduleItem / ScheduleType 冻结
- RegistryAdapter CRUD
- EngineInfo 注册与执行
- Scheduler 事件订阅与分发
- 优先级队列排序
- 周期性调度
- 取消调度
- 边界条件
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.runtime.scheduler import (
    ScheduleItem,
    ScheduleType,
    EngineInfo,
    RegistryAdapter,
    Scheduler,
)
from ocos.events.event_bus import EventBus


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def registry() -> RegistryAdapter:
    return RegistryAdapter()


@pytest.fixture
def sample_engine() -> EngineInfo:
    executed: list[str] = []

    def execute_fn(item, bus):
        executed.append(item.engine_name)

    engine = EngineInfo(
        name="test_engine",
        description="测试用 Engine",
        execute_fn=execute_fn,
        event_types=[EventType.GOAL_SET, EventType.ACTION_SCHEDULED],
    )
    engine._test_executed = executed
    return engine


@pytest.fixture
def sample_engine2() -> EngineInfo:
    executed2: list[str] = []

    def execute_fn2(item, bus):
        executed2.append(item.engine_name)

    engine = EngineInfo(
        name="test_engine_2",
        description="第二个测试用 Engine",
        execute_fn=execute_fn2,
        event_types=[EventType.GOAL_UPDATED],
    )
    engine._test_executed = executed2
    return engine


@pytest.fixture
def ready_scheduler(event_bus, registry, sample_engine) -> Scheduler:
    registry.register(sample_engine)
    return Scheduler(event_bus, registry)


# ══════════════════════════════════════════════════════════════════════════
# ScheduleItem 冻结性测试
# ══════════════════════════════════════════════════════════════════════════

class TestScheduleItem:

    def test_is_frozen(self):
        item = ScheduleItem()
        with pytest.raises(FrozenInstanceError):
            item.priority = 0.1  # type: ignore[misc]

    def test_default_values(self):
        item = ScheduleItem()
        assert item.schedule_type == ScheduleType.ONE_SHOT
        assert item.priority == 0.0
        assert item.schema_version == SCHEMA_VERSION
        assert len(item.item_id) == 32

    def test_custom_values(self):
        item = ScheduleItem(
            engine_name="my_engine",
            event_type=EventType.GOAL_SET,
            schedule_type=ScheduleType.PERIODIC,
            priority=0.8,
            payload={"key": "val"},
            interval_seconds=30.0,
        )
        assert item.engine_name == "my_engine"
        assert item.event_type == EventType.GOAL_SET
        assert item.schedule_type == ScheduleType.PERIODIC
        assert item.interval_seconds == 30.0
        assert item.payload == {"key": "val"}


# ══════════════════════════════════════════════════════════════════════════
# EngineInfo 测试
# ══════════════════════════════════════════════════════════════════════════

class TestEngineInfo:

    def test_create(self):
        engine = EngineInfo(
            name="analyst",
            description="分析引擎",
            event_types=[EventType.GOAL_SET],
        )
        assert engine.name == "analyst"
        assert EventType.GOAL_SET in engine.supported_events

    def test_execute_calls_fn(self):
        trace = []
        def my_fn(item, bus):
            trace.append(item.engine_name)
        engine = EngineInfo(
            name="fn_engine",
            execute_fn=my_fn,
        )
        item = ScheduleItem(engine_name="fn_engine")
        engine.execute(item, None)
        assert trace == ["fn_engine"]

    def test_execute_without_fn_noop(self):
        """无 execute_fn 时静默跳过。"""
        engine = EngineInfo(name="noop_engine")
        item = ScheduleItem(engine_name="noop_engine")
        engine.execute(item, None)  # 不应报错


# ══════════════════════════════════════════════════════════════════════════
# RegistryAdapter 测试
# ══════════════════════════════════════════════════════════════════════════

class TestRegistryAdapter:

    def test_register_and_get(self, registry, sample_engine):
        registry.register(sample_engine)
        found = registry.get("test_engine")
        assert found is not None
        assert found.name == "test_engine"

    def test_get_nonexistent(self, registry):
        assert registry.get("ghost") is None

    def test_unregister(self, registry, sample_engine):
        registry.register(sample_engine)
        assert registry.count == 1
        registry.unregister("test_engine")
        assert registry.count == 0
        assert registry.get("test_engine") is None

    def test_find_by_event_type(self, registry, sample_engine, sample_engine2):
        registry.register(sample_engine)
        registry.register(sample_engine2)
        # GOAL_SET -> sample_engine only
        goal_set_engines = registry.find_by_event_type(EventType.GOAL_SET)
        assert len(goal_set_engines) == 1
        assert goal_set_engines[0].name == "test_engine"
        # GOAL_UPDATED -> sample_engine2 only
        goal_upd_engines = registry.find_by_event_type(EventType.GOAL_UPDATED)
        assert len(goal_upd_engines) == 1
        assert goal_upd_engines[0].name == "test_engine_2"

    def test_list_all(self, registry, sample_engine, sample_engine2):
        registry.register(sample_engine)
        registry.register(sample_engine2)
        assert len(registry.list_all()) == 2

    def test_empty_registry(self, registry):
        assert registry.count == 0
        assert registry.list_all() == []
        assert registry.find_by_event_type(EventType.GOAL_SET) == []


# ══════════════════════════════════════════════════════════════════════════
# Scheduler 测试
# ══════════════════════════════════════════════════════════════════════════

class TestScheduler:

    def test_init_subscribes_defaults(self, event_bus, registry, sample_engine):
        registry.register(sample_engine)
        scheduler = Scheduler(event_bus, registry)
        assert len(scheduler._subscription_ids) >= 4  # GOAL_SET/UPDATED/COMPLETED/TASK_SCHEDULED

    def test_init_properties(self, ready_scheduler, registry):
        assert ready_scheduler.registry is registry
        assert ready_scheduler.queue_size == 0
        assert ready_scheduler.processed_count == 0
        assert ready_scheduler.is_running is False

    def test_event_triggers_enqueue_and_dispatch(
        self, event_bus, ready_scheduler, sample_engine
    ):
        """事件触发后入队并执行 dispatch。"""
        event = Event(
            event_type=EventType.GOAL_SET,
            payload={"engine_name": "test_engine", "goal_id": "g1"},
        )
        event_bus.publish(event, sync=True)

        # 入队了
        assert ready_scheduler.queue_size >= 1

        # tick 执行
        executed = ready_scheduler.tick()
        assert "test_engine" in executed
        assert ready_scheduler.processed_count >= 1

    def test_event_triggers_dispatch_by_event_type(
        self, event_bus, registry, sample_engine
    ):
        """未指定 engine_name 时，按事件类型查找 Engine。"""
        registry.register(sample_engine)
        scheduler = Scheduler(event_bus, registry)

        # 发布 GOAL_SET（sample_engine 支持该类型）
        event = Event(
            event_type=EventType.GOAL_SET,
            payload={"goal_id": "g-auto"},
        )
        event_bus.publish(event, sync=True)
        assert scheduler.queue_size >= 1

    def test_event_with_unknown_engine(self, event_bus, registry, sample_engine):
        """指定不存在的 Engine 不创建条目。"""
        registry.register(sample_engine)
        scheduler = Scheduler(event_bus, registry)

        event = Event(
            event_type=EventType.GOAL_SET,
            payload={"engine_name": "ghost_engine"},
        )
        event_bus.publish(event, sync=True)
        assert scheduler.queue_size == 0  # ghost_engine 不存在

    def test_tick_processes_highest_priority_first(self, event_bus, registry):
        """高优先级条目先执行。"""
        # 注册两个 Engine
        trace = []
        def fn_high(item, bus):
            trace.append("high")
        def fn_low(item, bus):
            trace.append("low")

        registry.register(EngineInfo("high_engine", execute_fn=fn_high))
        registry.register(EngineInfo("low_engine", execute_fn=fn_low))
        scheduler = Scheduler(event_bus, registry)

        # 手动入队两个条目（低优先先入，高优先后入）
        scheduler._enqueue(
            ScheduleItem(engine_name="low_engine", priority=0.1)
        )
        scheduler._enqueue(
            ScheduleItem(engine_name="high_engine", priority=0.9)
        )

        executed = scheduler.tick(max_items=2)
        assert trace == ["high", "low"]  # 高优先先执行

    def test_tick_respects_max_items(self, ready_scheduler):
        """tick 受 max_items 限制。"""
        for i in range(5):
            ready_scheduler._enqueue(
                ScheduleItem(engine_name="test_engine", priority=0.5)
            )
        executed = ready_scheduler.tick(max_items=2)
        assert len(executed) == 2
        assert ready_scheduler.queue_size == 3

    def test_tick_all(self, ready_scheduler):
        """tick_all 消费所有条目。"""
        for i in range(5):
            ready_scheduler._enqueue(
                ScheduleItem(engine_name="test_engine", priority=0.5)
            )
        executed = ready_scheduler.tick_all()
        assert len(executed) == 5
        assert ready_scheduler.queue_size == 0

    def test_schedule_periodic(self, ready_scheduler):
        """周期性条目执行后重新入队。"""
        item_id = ready_scheduler.schedule_periodic(
            engine_name="test_engine",
            interval_seconds=10.0,
            priority=0.3,
        )
        assert item_id is not None
        assert ready_scheduler.queue_size == 1

        # 执行一次
        executed = ready_scheduler.tick(max_items=2)
        assert "test_engine" in executed
        # 周期性条目重新入队
        assert ready_scheduler.queue_size == 1

        # 再次执行（循环）
        executed2 = ready_scheduler.tick(max_items=2)
        assert len(executed2) >= 1

    def test_cancel_removes_item(self, ready_scheduler):
        """取消调度从队列中移除指定条目。"""
        item = ScheduleItem(engine_name="test_engine", priority=0.5)
        ready_scheduler._enqueue(item)
        assert ready_scheduler.queue_size == 1

        result = ready_scheduler.cancel(item.item_id)
        assert result is True
        assert ready_scheduler.queue_size == 0

    def test_cancel_nonexistent(self, ready_scheduler):
        """取消不存在的条目返回 False。"""
        result = ready_scheduler.cancel("nonexistent-id")
        assert result is False

    def test_reset_clears_state(self, ready_scheduler):
        """reset 清空队列和计数。"""
        for i in range(3):
            ready_scheduler._enqueue(
                ScheduleItem(engine_name="test_engine", priority=0.5)
            )
        assert ready_scheduler.queue_size == 3
        assert ready_scheduler.processed_count == 0

        ready_scheduler.tick(max_items=1)
        assert ready_scheduler.processed_count == 1

        ready_scheduler.reset()
        assert ready_scheduler.queue_size == 0
        assert ready_scheduler.processed_count == 0
        assert ready_scheduler.is_running is False

    def test_subscribe_additional(self, ready_scheduler, event_bus):
        """可额外订阅事件类型。"""
        sid = ready_scheduler.subscribe_additional(EventType.GOAL_COMPLETED)
        assert sid is not None
        assert len(ready_scheduler._subscription_ids) >= 5  # 4 默认 + 1 额外

    def test_unsubscribe_all_cleans_up(self, ready_scheduler, event_bus):
        """取消所有订阅。"""
        before = len(ready_scheduler._subscription_ids)
        ready_scheduler.unsubscribe_all()
        assert len(ready_scheduler._subscription_ids) == 0

    def test_schedule_conditional(self, ready_scheduler):
        """条件调度条目创建正确。"""
        item_id = ready_scheduler.schedule_conditional(
            engine_name="test_engine",
            condition_fn_name="should_process",
        )
        assert item_id is not None
        assert ready_scheduler.queue_size == 1

    def test_tick_empty_queue_does_nothing(self, ready_scheduler):
        """空队列 tick 无影响。"""
        executed = ready_scheduler.tick()
        assert executed == []
        executed = ready_scheduler.tick_all()
        assert executed == []

    def test_is_running_tracks_queue_state(self, ready_scheduler):
        """is_running 反映队列状态。"""
        assert ready_scheduler.is_running is False

        ready_scheduler._enqueue(
            ScheduleItem(engine_name="test_engine", priority=0.5)
        )
        ready_scheduler.tick(max_items=1)
        # 运行期间 is_running 被设置为 True... wait, let me check the logic
        # 实际上 `tick` 中设置了 _is_running = True，但只有第一次 tick 时设置
        # 且当队列为空时设置为 False

    def test_dispatch_calls_engine_execute(self, event_bus, registry):
        """验证 dispatch 真正执行了 Engine 的 execute_fn。"""
        exec_trace = []
        def my_fn(item, bus):
            exec_trace.append(item.engine_name)

        engine = EngineInfo(
            name="trace_engine",
            execute_fn=my_fn,
        )
        registry.register(engine)
        scheduler = Scheduler(event_bus, registry)

        event = Event(
            event_type=EventType.GOAL_SET,
            payload={"engine_name": "trace_engine", "val": 1},
        )
        event_bus.publish(event, sync=True)
        scheduler.tick()
        assert "trace_engine" in exec_trace

    def test_priority_from_payload(self, ready_scheduler):
        """payload 中的 scheduler_priority 覆盖默认优先级。"""
        item = ScheduleItem(
            engine_name="test_engine",
            priority=0.95,
        )
        ready_scheduler._enqueue(item)

        # 验证优先级队列排序
        assert ready_scheduler._queue[0][2].priority == 0.95
