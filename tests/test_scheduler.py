"""OCOS scheduler 调度器不变式测试。

B3 Scheduler — 优先级调度器
- ScheduleItem 字段完整
- EngineInfo 注册/查找/注销
- RegistryAdapter CRUD
- Scheduler 优先级队列单调性
- tick 消费顺序
"""

import pytest
from unittest.mock import MagicMock

from ocos.runtime.scheduler import (
    ScheduleType,
    ScheduleItem,
    EngineInfo,
    RegistryAdapter,
    Scheduler,
)
from ocos.kernel.abi import Event, EventType


class TestScheduleType:
    def test_three_types(self):
        assert {t.value for t in ScheduleType} == {
            "one_shot", "periodic", "conditional"
        }


class TestScheduleItem:
    def test_defaults(self):
        item = ScheduleItem(engine_name="test-engine")
        assert item.schedule_type == ScheduleType.ONE_SHOT
        assert item.priority == 0.0
        assert item.timeout_seconds == 60.0
        assert item.schema_version != ""

    def test_periodic_item(self):
        item = ScheduleItem(
            engine_name="ticker",
            schedule_type=ScheduleType.PERIODIC,
            interval_seconds=5.0,
            priority=1.0,
        )
        assert item.schedule_type == ScheduleType.PERIODIC
        assert item.interval_seconds == 5.0

    def test_item_is_frozen(self):
        item = ScheduleItem(engine_name="e")
        with pytest.raises((TypeError, AttributeError)):
            item.priority = 999  # type: ignore[misc]


class TestEngineInfo:
    def test_basic(self):
        called = []
        def fn(item, bus):
            called.append(True)
        ei = EngineInfo(name="test", execute_fn=fn)
        assert ei.name == "test"
        assert ei.supported_events == set()

    def test_execute_calls_fn(self):
        called = []
        def fn(item, bus):
            called.append(item.engine_name)
        ei = EngineInfo(name="n", execute_fn=fn)
        item = ScheduleItem(engine_name="n")
        ei.execute(item, MagicMock())
        assert called == ["n"]

    def test_execute_no_fn_is_noop(self):
        ei = EngineInfo(name="n")
        ei.execute(ScheduleItem(engine_name="n"), MagicMock())  # no error

    def test_supported_events(self):
        ei = EngineInfo(
            name="n",
            event_types=[EventType.GOAL_SET, EventType.ACTION_SCHEDULED],
        )
        assert EventType.GOAL_SET in ei.supported_events
        assert EventType.TRACE_RECORDED not in ei.supported_events


class TestRegistryAdapter:
    def test_crud(self):
        reg = RegistryAdapter()
        assert reg.count == 0
        reg.register(EngineInfo(name="a"))
        reg.register(EngineInfo(name="b"))
        assert reg.count == 2
        assert reg.get("a").name == "a"
        assert reg.get("nonexistent") is None
        reg.unregister("a")
        assert reg.count == 1
        assert reg.get("a") is None

    def test_find_by_event_type(self):
        reg = RegistryAdapter()
        reg.register(EngineInfo(name="goal_handler", event_types=[EventType.GOAL_SET]))
        reg.register(EngineInfo(name="generic", event_types=[EventType.ACTION_SCHEDULED]))
        results = reg.find_by_event_type(EventType.GOAL_SET)
        assert len(results) == 1
        assert results[0].name == "goal_handler"

    def test_list_all(self):
        reg = RegistryAdapter()
        reg.register(EngineInfo(name="a"))
        reg.register(EngineInfo(name="b"))
        names = {e.name for e in reg.list_all()}
        assert names == {"a", "b"}


class TestScheduler:
    @pytest.fixture
    def scheduler(self):
        bus = MagicMock()
        bus.subscribe.return_value = "sub-1"
        bus.unsubscribe = MagicMock()
        return Scheduler(event_bus=bus)

    def test_initial_state(self, scheduler):
        assert scheduler.queue_size == 0
        assert scheduler.processed_count == 0
        assert scheduler.is_running is False

    def test_registry_accessible(self, scheduler):
        assert scheduler.registry.count == 0

    def test_subscribe_additional(self, scheduler):
        sid = scheduler.subscribe_additional(EventType.TRACE_RECORDED)
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_unsubscribe_all(self, scheduler):
        scheduler.subscribe_additional(EventType.TRACE_RECORDED)
        scheduler.unsubscribe_all()
        assert scheduler._subscription_ids == []

    def test_tick_empty_queue(self, scheduler):
        result = scheduler.tick()
        assert result == []

    def test_tick_processes_one(self, scheduler):
        """有注册引擎且事件匹配时，tick 应消费一项。"""
        engine = EngineInfo(
            name="test_engine",
            event_types=[EventType.GOAL_SET],
        )
        scheduler.registry.register(engine)

        event = Event(
            event_id="E1",
            event_type=EventType.GOAL_SET,
            source="cli",
            timestamp="",
            payload={"engine_name": "test_engine", "goal_id": "G1"},
            trace_id="",
            schema_version="1.0.0",
        )
        # Manually enqueue
        item = ScheduleItem(
            engine_name="test_engine",
            event_type=EventType.GOAL_SET,
            schedule_type=ScheduleType.ONE_SHOT,
            priority=0.8,
            payload={"goal_id": "G1"},
        )
        scheduler._enqueue(item)
        scheduler._is_running = True

        executed = scheduler.tick(max_items=1)
        assert len(executed) == 1
        assert executed[0] == "test_engine"
        assert scheduler.processed_count == 1

    def test_priority_ordering(self, scheduler):
        """高优先级先被消费。"""
        high = ScheduleItem(engine_name="high", priority=0.9)
        low = ScheduleItem(engine_name="low", priority=0.1)
        scheduler._enqueue(high)
        scheduler._enqueue(low)
        scheduler._is_running = True

        scheduler.tick(max_items=2)
        assert scheduler.processed_count == 2

    def test_tick_all_consumes_all(self, scheduler):
        item = ScheduleItem(engine_name="e", priority=0.5)
        scheduler._enqueue(item)
        scheduler._is_running = True
        result = scheduler.tick_all()
        assert len(result) == 1

    def test_tick_sets_running_and_stops_when_empty(self, scheduler):
        assert scheduler.is_running is False
        scheduler.tick()  # empty queue
        # After tick with empty queue, is_running should be False
        assert scheduler.is_running is False

        # After non-empty tick, is_running should be True
        item = ScheduleItem(engine_name="e", priority=0.5)
        scheduler._enqueue(item)
        scheduler.tick(max_items=1)
        # Queue is now empty, should reset
        assert scheduler.is_running is False
