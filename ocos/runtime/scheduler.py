"""
B3 Scheduler — 优先级调度器。

职责：
- 通过 Event Bus 接收事件
- 结合 Attention Score 确定执行优先级
- 从 Registry（Capability Registry / 简化实现）发现 Engine
- 分发执行请求到对应 Engine

分工裁决（AUD-F2, 2026-08-30）:
    本模块 = tick 内 stage 级事件分发器（生产在用，经 runtime.pipeline 注册）。
    ocos/runtime_scheduler/ = 独立任务心跳调度器（Phase 51.2 契约，
    test_phase51_2 锁定；CognitiveClock/PriorityQueue/Backpressure/Worker），
    当前无生产消费者，候选接入点 = ResidentRuntime 任务队列需要背压时。
    两者非重复实现，不合并。
- 支持 one-shot / periodic / conditional 调度类型

依赖：B2 Attention Engine（用于优先级排序）
后续替换：D1 Capability Registry 将取代简化 Registry
"""

from __future__ import annotations

import uuid
import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from ocos.kernel.abi import (
    Event,
    EventType,
    SCHEMA_VERSION,
    Observation,
    Goal,
)
from ocos.events.event_bus import EventBus
from ocos.logging import get_logger


logger = get_logger(__name__)


# ── 调度类型 ────────────────────────────────────────────────

class ScheduleType(Enum):
    ONE_SHOT = "one_shot"     # 单次执行
    PERIODIC = "periodic"     # 周期性执行
    CONDITIONAL = "conditional"  # 条件触发


# ── 调度项 ──────────────────────────────────────────────────

@dataclass(frozen=True)
class ScheduleItem:
    """一个可调度的执行单元。

    由 Scheduler 创建，放入优先级队列。
    """
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    engine_id: str | None = None       # 替代 engine_name（未来）
    engine_name: str = ""               # 目标 Engine 名称
    event_type: EventType | None = None  # 触发事件类型
    schedule_type: ScheduleType = ScheduleType.ONE_SHOT
    priority: float = 0.0          # 越高越优先
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    timeout_seconds: float | None = 60.0  # 单次执行超时
    schema_version: str = SCHEMA_VERSION

    # 周期性调度专用
    interval_seconds: float | None = None  # 执行间隔
    next_run_at: str | None = None          # 下次执行时间 ISO

    # 条件调度专用
    condition_fn_name: str | None = None    # 条件函数引用名


# ── Engine 接口（Registry 中的可用引擎） ─────────────────────

class EngineInfo:
    """Engine 在 Scheduler 中的注册信息。"""

    def __init__(
        self,
        name: str,
        description: str = "",
        execute_fn: Callable | None = None,
        event_types: list[EventType] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.description = description
        self._execute_fn = execute_fn
        self.supported_events: set[EventType] = set(event_types or [])
        self.metadata = metadata or {}

    def execute(self, item: ScheduleItem, event_bus: EventBus) -> None:
        """执行 Engine 逻辑。（当前为占位，D4 后由 Plugin Loader 真实注入）"""
        if self._execute_fn:
            self._execute_fn(item, event_bus)


# ── 简化 Registry ──────────────────────────────────────────

class RegistryAdapter:
    """简化 Engine Registry。

    当前为 dict 实现，D1 Capability Registry 完成后可替换。
    """

    def __init__(self):
        self._engines: dict[str, EngineInfo] = {}

    def register(self, engine: EngineInfo) -> None:
        """注册 Engine。"""
        self._engines[engine.name] = engine

    def unregister(self, name: str) -> None:
        """注销 Engine。"""
        self._engines.pop(name, None)

    def get(self, name: str) -> EngineInfo | None:
        """按名称查找 Engine。"""
        return self._engines.get(name)

    def find_by_event_type(self, event_type: EventType) -> list[EngineInfo]:
        """按支持的事件类型查找 Engine。"""
        return [
            e for e in self._engines.values()
            if event_type in e.supported_events
        ]

    def list_all(self) -> list[EngineInfo]:
        """列出所有注册的 Engine。"""
        return list(self._engines.values())

    @property
    def count(self) -> int:
        return len(self._engines)


# ── Scheduler ───────────────────────────────────────────────

class Scheduler:
    """优先级调度器：事件驱动、Attention 排序、Engine 分发。

    工作流：
        1. 订阅 Event Bus 事件
        2. 收到事件 → 计算优先级（结合 Attention Score）
        3. 入优先级队列
        4. 消费队列 → 通过 Registry 分发到 Engine
    """

    def __init__(
        self,
        event_bus: EventBus,
        registry: RegistryAdapter | None = None,
        attention_engine: Any = None,  # 可选 AttentionEngine（后续 B2 集成）
        engine_loader: Any = None,     # 可选 EngineLoader（替代硬编码引擎）
    ):
        self._event_bus = event_bus
        self._registry = registry or RegistryAdapter()
        self._attention_engine = attention_engine
        self._engine_loader = engine_loader
        self._queue: list[tuple[float, int, ScheduleItem]] = []  # (neg_priority, seq, item)
        self._seq: int = 0  # 同优先级时用序号做 tiebreaker
        self._subscription_ids: list[str] = []
        self._processed_count: int = 0
        self._is_running: bool = False

        # 订阅默认事件
        self._subscribe_default()
        logger.debug("Scheduler initialized", component="scheduler",
                      queue_size=0, processed=0)

    @property
    def registry(self) -> RegistryAdapter:
        return self._registry

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ── 订阅管理 ──────────────────────────────────────────

    def _subscribe_default(self) -> None:
        """订阅默认事件类型。"""
        subscribed = [
            EventType.GOAL_SET,
            EventType.GOAL_UPDATED,
            EventType.GOAL_COMPLETED,
            EventType.ACTION_SCHEDULED,
        ]
        for et in subscribed:
            try:
                sid = self._event_bus.subscribe(
                    et, self._on_event,
                    subscriber_id=f"scheduler-{et.value}",
                )
                self._subscription_ids.append(sid)
            except Exception:
                logger.warning(
                    "Scheduler: 订阅事件 %s 失败（事件类型可能未注册）",
                    et.value,
                )

    def subscribe_additional(self, event_type: EventType) -> str:
        """订阅额外事件类型。返回 subscription_id。"""
        sid = self._event_bus.subscribe(
            event_type, self._on_event,
            subscriber_id=f"scheduler-extra-{event_type.value}",
        )
        self._subscription_ids.append(sid)
        logger.info("Subscribed to additional event type",
                     component="scheduler", event_type=event_type.value,
                     subscription_id=sid)
        return sid

    def unsubscribe_all(self) -> None:
        """取消所有订阅。"""
        count = len(self._subscription_ids)
        for sid in self._subscription_ids:
            self._event_bus.unsubscribe(sid)
        self._subscription_ids.clear()
        logger.info("Unsubscribed from all events",
                     component="scheduler", count=count)

    # ── 事件处理 ──────────────────────────────────────────

    def _on_event(self, event: Event) -> None:
        """事件回调：创建 ScheduleItem 并入队。"""
        engine_name = event.payload.get("engine_name", "")
        if not engine_name:
            # 事件无指定 Engine — 按事件类型查找
            candidates = self._registry.find_by_event_type(event.event_type)
            if not candidates:
                return
        else:
            # 指定 Engine 名称
            engine = self._registry.get(engine_name)
            if engine is None:
                return
            candidates = [engine]

        for engine_info in candidates:
            # 计算优先级
            priority = self._compute_priority(event, engine_info)

            item = ScheduleItem(
                engine_name=engine_info.name,
                event_type=event.event_type,
                schedule_type=ScheduleType.ONE_SHOT,
                priority=priority,
                payload=event.payload,
            )
            self._enqueue(item)

    def _compute_priority(
        self,
        event: Event,
        engine: EngineInfo,
    ) -> float:
        """计算事件优先级。结合 Attention Score 和 Engine 紧急度。"""
        base_priority = 0.5  # 默认中等

        # 如果有关联的 AttentionEngine，尝试获取评分
        if self._attention_engine is not None:
            observation_id = event.payload.get("observation_id", "")
            if observation_id:
                score = self._attention_engine.get_score(observation_id)
                if score is not None:
                    return score.composite  # 直接用 composite 作为优先级

        # 基于事件类型的默认优先级
        event_base = {
            EventType.GOAL_SET: 0.8,
            EventType.GOAL_UPDATED: 0.6,
            EventType.GOAL_COMPLETED: 0.7,
            EventType.ACTION_SCHEDULED: 0.5,
        }
        base_priority = event_base.get(event.event_type, 0.5)
        # 允许 payload 覆盖
        return event.payload.get("scheduler_priority", base_priority)

    def _enqueue(self, item: ScheduleItem) -> None:
        """入队（min-heap，priority 取负实现高优先在前）。"""
        heapq.heappush(self._queue, (-item.priority, self._seq, item))
        self._seq += 1

    # ── 调度执行 ──────────────────────────────────────────

    def get_engine(self, engine_id: str) -> Any | None:
        """通过 EngineLoader 获取引擎实例。"""
        if self._engine_loader is None:
            return None
        return self._engine_loader.get(engine_id)

    def tick(self, max_items: int = 1) -> list[str]:
        """执行一次调度 tick：消费队列中最优先的 N 个条目。

        Args:
            max_items: 本 tick 最多消费条数。

        Returns:
            已执行的 engine_name 列表。
        """
        if not self._is_running:
            self._is_running = True

        executed: list[str] = []
        for _ in range(min(max_items, len(self._queue))):
            if not self._queue:
                break
            neg_priority, _seq, item = heapq.heappop(self._queue)
            self._dispatch(item)
            self._processed_count += 1
            executed.append(item.engine_name)
            # 处理周期性调度
            self._reschedule_if_periodic(item)

        if not self._queue:
            self._is_running = False

        if executed:
            logger.info("Scheduler tick executed",
                        component="scheduler",
                        executed_count=len(executed),
                        engines=executed,
                        remaining=self._processed_count)
        return executed

    def tick_all(self) -> list[str]:
        """消费队列中所有条目。"""
        result = self.tick(max_items=len(self._queue))
        logger.info("Scheduler tick_all completed",
                     component="scheduler",
                     executed_count=len(result))
        return result

    def schedule_periodic(
        self,
        engine_name: str,
        interval_seconds: float,
        payload: dict[str, Any] | None = None,
        priority: float = 0.3,
    ) -> str:
        """添加周期性调度任务。返回 item_id。"""
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=interval_seconds)

        item = ScheduleItem(
            engine_name=engine_name,
            schedule_type=ScheduleType.PERIODIC,
            priority=priority,
            payload=payload or {},
            interval_seconds=interval_seconds,
            next_run_at=next_run.isoformat(),
        )
        self._enqueue(item)
        logger.info("Periodic schedule added",
                     component="scheduler",
                     engine=engine_name,
                     interval=interval_seconds,
                     priority=priority,
                     item_id=item.item_id)
        return item.item_id

    def schedule_conditional(
        self,
        engine_name: str,
        condition_fn_name: str,
        payload: dict[str, Any] | None = None,
        priority: float = 0.4,
    ) -> str:
        """添加条件触发调度任务。返回 item_id。"""
        item = ScheduleItem(
            engine_name=engine_name,
            schedule_type=ScheduleType.CONDITIONAL,
            priority=priority,
            payload=payload or {},
            condition_fn_name=condition_fn_name,
        )
        self._enqueue(item)
        logger.info("Conditional schedule added",
                     component="scheduler",
                     engine=engine_name,
                     condition_fn=condition_fn_name,
                     priority=priority,
                     item_id=item.item_id)
        return item.item_id

    # ── 内部 ─────────────────────────────────────────────

    def _dispatch(self, item: ScheduleItem) -> None:
        """将条目分发到对应 Engine。"""
        engine = self._registry.get(item.engine_name)
        if engine is None:
            return
        engine.execute(item, self._event_bus)

    def _reschedule_if_periodic(self, item: ScheduleItem) -> None:
        """如果是周期性调度，重新入队（含新 next_run_at）。"""
        if item.schedule_type != ScheduleType.PERIODIC:
            return
        if item.interval_seconds is None:
            return

        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=item.interval_seconds)
        new_item = ScheduleItem(
            engine_name=item.engine_name,
            event_type=item.event_type,
            schedule_type=ScheduleType.PERIODIC,
            priority=item.priority,
            payload=dict(item.payload),
            interval_seconds=item.interval_seconds,
            next_run_at=next_run.isoformat(),
        )
        self._enqueue(new_item)

    def reset(self) -> None:
        """重置调度器状态。"""
        self._queue.clear()
        self._processed_count = 0
        self._is_running = False
        logger.info("Scheduler reset",
                     component="scheduler")

    def cancel(self, item_id: str) -> bool:
        """取消指定条目（标记式：重建队列剔除匹配项）。"""
        old_queue = self._queue
        self._queue = []
        found = False
        for neg_p, seq, item in old_queue:
            if item.item_id == item_id:
                found = True
                continue
            heapq.heappush(self._queue, (neg_p, seq, item))
        if found:
            logger.info("Schedule item cancelled",
                        component="scheduler", item_id=item_id)
        return found
