"""
B5 Resource Manager — 资源管理引擎。

职责：
- CPU/内存/GPU/TOKEN/STORAGE 资源池管理
- `request(resource_type, amount, holder) -> ResourceRequestResult`
- `release(slot_id) -> bool` 释放已分配的资源
- 引擎级配额控制
- TTL 自动回收（惰性 + 主动 _cleanup_expired 双模式）
- Event Bus 集成（RESOURCE_EXHAUSTED / RESOURCE_RELEASED 事件）
- 独立模块，无依赖。

与 B6 Adaptive Control 的协作方式：
当 RESOURCE_EXHAUSTED 事件发出后，Adaptive Control 可先调用 _cleanup_expired()
尝试回收过期 slot，再根据剩余可用资源决定降级策略。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.logging import get_logger

def _publish_safe(event_bus, event) -> None:
    """S1.6 (白皮书 P1-7): EventBus 的真实 API 是 publish（非 emit）。

    兼容 None 注入与异构总线；发布失败降级为 debug 日志不阻断。
    """
    publish = getattr(event_bus, "publish", None)
    if publish is None:
        return
    try:
        publish(event)
    except Exception as exc:  # 事件发射失败不阻断主流程（BR-04: 留痕不静默）
        get_logger(__name__).debug("event publish failed: %s", exc)

logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class ResourceType(str, Enum):
    """受管理的资源类型。"""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    TOKEN = "token"
    STORAGE = "storage"


# ── 默认容量 ────────────────────────────────────────────────────────────────

DEFAULT_CAPACITY: dict[str, float] = {
    "cpu": 8.0,         # 核
    "memory": 16384.0,  # MB
    "gpu": 1.0,         # 单元
    "token": 100000.0,  # tokens
    "storage": 1024.0,  # MB
}

DEFAULT_UNITS: dict[str, str] = {
    "cpu": "cores",
    "memory": "MB",
    "gpu": "units",
    "token": "tokens",
    "storage": "MB",
}


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResourceUsage:
    """某一类资源的当前使用快照（冻结、可序列化）。"""
    resource_type: str = ""
    total: float = 0.0
    reserved: float = 0.0
    available: float = 0.0
    unit: str = ""
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ResourceSlot:
    """一次成功分配的资源槽（冻结、可序列化）。"""
    slot_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    resource_type: str = ""
    amount: float = 0.0
    holder: str = ""
    priority: int = 0
    acquired_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ttl_seconds: Optional[float] = None
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ResourceRequestResult:
    """资源请求结果（冻结、可序列化）。

    allowed=False 时，slot 为 None，reason 说明拒绝原因。
    供 Adaptive Control / Audit Engine 做精确调度决策。
    """
    allowed: bool = False
    slot: Optional[ResourceSlot] = None
    reason: str = ""
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ResourceQuota:
    """引擎级别的资源配额上限。"""
    engine_id: str = ""
    quotas: dict[str, float] = field(default_factory=dict)  # {type: max_amount}
    schema_version: str = SCHEMA_VERSION


# ── 时间戳工具 ──────────────────────────────────────────────────────────────

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slot_is_expired(slot: ResourceSlot) -> bool:
    """检查 slot 是否已过期（TTL 模式）。"""
    if slot.ttl_seconds is None:
        return False
    try:
        acquired = datetime.fromisoformat(slot.acquired_at).timestamp()
    except (ValueError, TypeError):
        return True  # 无法解析视为过期
    return _now_ts() - acquired > slot.ttl_seconds


# ── ResourceManager ─────────────────────────────────────────────────────────

class ResourceManager:
    """资源管理器。

    管理多类资源的分配/释放/配额，支持 TTL 自动回收。
    可选对接 Event Bus 发送 RESOURCE_EXHAUSTED / RESOURCE_RELEASED 事件。
    """

    def __init__(
        self,
        capacities: Optional[dict[str, float]] = None,
        quotas: Optional[dict[str, dict[str, float]]] = None,
        event_bus: Any = None,
    ) -> None:
        """
        Args:
            capacities:  资源总容量，{type: total}，缺省使用 DEFAULT_CAPACITY
            quotas:      引擎配额，{engine_id: {type: max_amount}}，不设则不限制
            event_bus:   EventBus 实例，可选。缺省则不发送事件。
        """
        # 资源池
        self._capacities: dict[str, float] = dict(DEFAULT_CAPACITY)
        if capacities:
            self._capacities.update(capacities)

        # 已分配 slot（slot_id → ResourceSlot）
        self._slots: dict[str, ResourceSlot] = {}

        # 引擎配额
        self._quotas: dict[str, dict[str, float]] = {}
        if quotas:
            self._quotas.update(quotas)

        # Event Bus
        self._event_bus: Any = event_bus

        # 计数器
        self._request_count: int = 0
        self._release_count: int = 0

        logger.debug(
            "ResourceManager initialized: capacities=%s, quotas=%s, event_bus=%s",
            self._capacities, bool(self._quotas), self._event_bus is not None,
        )

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def release_count(self) -> int:
        return self._release_count

    # ── 核心接口 ────────────────────────────────────────────────────────────

    def request(
        self,
        resource_type: str,
        amount: float,
        holder: str = "",
        priority: int = 0,
        ttl: Optional[float] = None,
    ) -> ResourceRequestResult:
        """请求资源。

        分配检查顺序：
          1. resource_type 是否受管理
          2. amount 是否合法 (>0)
          3. 当前可用量是否足够
          4. holder 的引擎配额是否超限

        返回 ResourceRequestResult，携带精确拒绝原因。
        """
        self._request_count += 1
        logger.info("Resource request: type=%s amount=%s holder=%s priority=%d ttl=%s",
                     resource_type, amount, holder, priority, ttl)

        # 前置清理过期 slot
        self._cleanup_expired()

        # 1) 检查资源类型
        if resource_type not in self._capacities:
            return ResourceRequestResult(
                allowed=False,
                reason=f"unknown resource type: {resource_type}",
            )

        # 2) 检查 amount
        if amount <= 0:
            return ResourceRequestResult(
                allowed=False,
                reason=f"invalid amount: {amount} (must be > 0)",
            )

        # 3) 计算当前可用
        reserved = self._reserved_amount(resource_type)
        total = self._capacities[resource_type]
        available = total - reserved
        if amount > available:
            reason = (
                f"insufficient {resource_type}: requested {amount}, "
                f"available {available:.1f} / {total}"
            )
            self._emit_resource_exhausted(
                resource_type, requested=amount, available=available, reason=reason,
            )
            return ResourceRequestResult(allowed=False, reason=reason)

        # 4) 检查引擎配额
        if holder in self._quotas:
            quota = self._quotas[holder].get(resource_type, float("inf"))
            holder_used = self._holder_used_amount(holder, resource_type)
            if holder_used + amount > quota:
                reason = (
                    f"quota exceeded for {holder} on {resource_type}: "
                    f"used {holder_used:.1f} + requested {amount} > quota {quota}"
                )
                self._emit_resource_exhausted(
                    resource_type, requested=amount, available=available,
                    holder=holder, reason=reason,
                )
                return ResourceRequestResult(allowed=False, reason=reason)

        # 5) 分配
        slot = ResourceSlot(
            resource_type=resource_type,
            amount=amount,
            holder=holder,
            priority=priority,
            ttl_seconds=ttl,
        )
        self._slots[slot.slot_id] = slot
        logger.info("Resource allocated: slot_id=%s type=%s amount=%s holder=%s",
                     slot.slot_id, resource_type, amount, holder)
        return ResourceRequestResult(
            allowed=True,
            slot=slot,
            reason="",
        )

    def release(self, slot_id: str) -> bool:
        """释放指定 slot 的资源。重复释放返回 False。"""
        if slot_id not in self._slots:
            logger.warning("Release called on unknown slot: %s", slot_id)
            return False
        slot = self._slots.pop(slot_id)
        self._release_count += 1
        logger.info("Resource released: slot_id=%s type=%s amount=%s holder=%s",
                     slot_id, slot.resource_type, slot.amount, slot.holder)

        if self._event_bus is not None:
            _publish_safe(self._event_bus, Event(
                event_type=EventType.RESOURCE_RELEASED,
                source="resource-manager",
                payload={
                    "slot_id": slot_id,
                    "resource_type": slot.resource_type,
                    "amount": slot.amount,
                    "holder": slot.holder,
                },
            ))
        return True

    def release_by_holder(self, holder: str) -> int:
        """释放某个持有者的所有 slot。返回释放数量。"""
        to_release = [
            sid for sid, s in self._slots.items()
            if s.holder == holder
        ]
        count = 0
        for sid in to_release:
            if self.release(sid):
                count += 1
        if count:
            logger.info("Released %d slots for holder=%s", count, holder)
        return count

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get_usage(self, resource_type: Optional[str] = None) -> list[ResourceUsage]:
        """查询当前资源使用快照。type=None 返回全部。"""
        self._cleanup_expired()
        result: list[ResourceUsage] = []
        types = [resource_type] if resource_type else list(self._capacities.keys())
        for rt in types:
            if rt not in self._capacities:
                continue
            total = self._capacities[rt]
            reserved = self._reserved_amount(rt)
            result.append(ResourceUsage(
                resource_type=rt,
                total=total,
                reserved=reserved,
                available=total - reserved,
                unit=DEFAULT_UNITS.get(rt, ""),
            ))
        return result

    def get_slots(self, holder: Optional[str] = None) -> list[ResourceSlot]:
        """查询活跃 slot。holder=None 返回全部。"""
        self._cleanup_expired()
        if holder is None:
            return list(self._slots.values())
        return [s for s in self._slots.values() if s.holder == holder]

    # ── 配额管理 ────────────────────────────────────────────────────────────

    def set_quota(self, engine_id: str, quotas: dict[str, float]) -> None:
        """设置或更新某引擎的资源配额。"""
        self._quotas[engine_id] = dict(quotas)
        logger.info("Quota set: engine=%s quotas=%s", engine_id, quotas)

    def get_quota(self, engine_id: str) -> dict[str, float]:
        """查询某引擎的配额。未设置则返回空 dict。"""
        return dict(self._quotas.get(engine_id, {}))

    def remove_quota(self, engine_id: str) -> None:
        """移除某引擎的配额限制。"""
        self._quotas.pop(engine_id, None)
        logger.info("Quota removed: engine=%s", engine_id)

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """清除所有 slot 和配额，重置计数器。"""
        self._slots.clear()
        self._quotas.clear()
        self._request_count = 0
        self._release_count = 0
        logger.info("ResourceManager reset")

    # ── 内部方法 ────────────────────────────────────────────────────────────

    def _reserved_amount(self, resource_type: str) -> float:
        """计算指定类型的已分配总量。"""
        total = 0.0
        for slot in self._slots.values():
            if slot.resource_type == resource_type:
                total += slot.amount
        return total

    def _holder_used_amount(self, holder: str, resource_type: str) -> float:
        """计算某持有者在某类型上的已用量。"""
        total = 0.0
        for slot in self._slots.values():
            if slot.holder == holder and slot.resource_type == resource_type:
                total += slot.amount
        return total

    def _cleanup_expired(self) -> int:
        """清理所有过期 slot（惰性 + 主动双模式）。

        在每次 request / get_usage / get_slots 时自动调用。
        也允许外部在资源紧张时主动触发（如 Adaptive Control 收到
        RESOURCE_EXHAUSTED 后，先调用此方法再决定降级策略）。

        Returns: 清理的 slot 数量。
        """
        expired = [
            sid for sid, slot in self._slots.items()
            if _slot_is_expired(slot)
        ]
        for sid in expired:
            slot = self._slots.pop(sid)
            self._release_count += 1

            if self._event_bus is not None:
                _publish_safe(self._event_bus, Event(
                    event_type=EventType.RESOURCE_RELEASED,
                    source="resource-manager",
                    payload={
                        "slot_id": sid,
                        "resource_type": slot.resource_type,
                        "amount": slot.amount,
                        "holder": slot.holder,
                        "reason": "ttl_expired",
                    },
                ))
        if expired:
            logger.info("Cleaned up %d expired slots", len(expired))
        return len(expired)

    def _emit_resource_exhausted(
        self,
        resource_type: str,
        requested: float = 0.0,
        available: float = 0.0,
        holder: str = "",
        reason: str = "",
    ) -> None:
        """发送 RESOURCE_EXHAUSTED 事件（仅当 Event Bus 可用时）。"""
        if self._event_bus is None:
            logger.warning(
                "Resource exhausted: type=%s requested=%s available=%s holder=%s reason=%s "
                "(no event bus configured)",
                resource_type, requested, available, holder, reason,
            )
            return
        logger.warning(
            "Resource exhausted: type=%s requested=%s available=%s holder=%s reason=%s",
            resource_type, requested, available, holder, reason,
        )
        _publish_safe(self._event_bus, Event(
            event_type=EventType.RESOURCE_EXHAUSTED,
            source="resource-manager",
            payload={
                "resource_type": resource_type,
                "requested": requested,
                "available": available,
                "holder": holder,
                "reason": reason,
            },
        ))
