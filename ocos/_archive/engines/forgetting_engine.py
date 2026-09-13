"""
Forgetting Engine — 信息遗忘引擎。

三层职责:
1. TTL 策略管理 — 按 PersistenceLevel 设置过期时间
2. 过期信息收集 — 扫描并标记可遗忘的信息
3. 遗忘执行 — 降级/归档/清除信息，发射 INFORMATION_STATUS_CHANGED 事件

执行流:
   collect_expired() → 标记 DEPRECATED
   forget() → VALIDATED→DEPRECATED 或 VALIDATED→ARCHIVED
              via INFORMATION_STATUS_CHANGED 事件
"""

from __future__ import annotations

import time
from typing import Any

from ocos.kernel.abi import Event, EventType
from ocos.models.information import (
    InformationMetadata,
    InformationState,
    PersistenceLevel,
    UniversalAddress,
)

from ocos.logging import get_logger

_SOURCE = "forgetting_engine"

logger = get_logger(__name__)

# TTL 默认值（秒）
_DEFAULT_TTL: dict[PersistenceLevel, int] = {
    PersistenceLevel.TRANSIENT: 30,       # 30 秒
    PersistenceLevel.PERSISTENT: 86400,   # 24 小时（generalized from session/workspace）
    PersistenceLevel.STABLE: 0,           # 不过期（需显式遗忘/归档）
    PersistenceLevel.IMMUTABLE: 0,        # 不过期
}


class ForgettingEngine:
    """信息遗忘引擎。

    管理 TTL 策略、收集过期信息、执行遗忘。
    EventBus 为可选依赖，Governance 审批模式与 PromotionEngine 对齐。
    """

    def __init__(
        self,
        event_bus: Any | None = None,
    ) -> None:
        self._event_bus = event_bus
        logger.debug("__init__ completed", component="forgetting_engine")
        # TTL 策略: PersistenceLevel → seconds (0 = 不过期)
        self._ttl_policies: dict[PersistenceLevel, int] = dict(_DEFAULT_TTL)
        # 待审批的遗忘请求
        self._pending: dict[str, dict[str, Any]] = {}

    # ── TTL 策略管理 ─────────────────────────────────────────────────────

    def set_ttl_policy(
        self, persistence: PersistenceLevel, ttl_seconds: int
    ) -> None:
        """设置指定持久化等级的 TTL。ttl_seconds=0 表示不过期。"""
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0")
        self._ttl_policies[persistence] = ttl_seconds

    def get_ttl_policy(self, persistence: PersistenceLevel) -> int:
        """查询指定持久化等级的 TTL。"""
        return self._ttl_policies.get(persistence, 0)

    def reset_ttl_defaults(self) -> None:
        """恢复 TTL 策略为默认值。"""
        self._ttl_policies = dict(_DEFAULT_TTL)

    # ── 过期收集 ─────────────────────────────────────────────────────────

    def is_expired(self, metadata: InformationMetadata) -> bool:
        """检查信息是否已过期（基于当前时间与 TTL）。"""
        if metadata.state != InformationState.VALIDATED:
            return False
        ttl = self._ttl_policies.get(metadata.persistence_level, 0)
        if ttl <= 0:
            return False  # 不过期
        if metadata.ttl is not None:
            ttl = metadata.ttl  # 实例级 TTL 覆盖策略级
        return time.time() - self._parse_timestamp(metadata.created_at) > ttl

    def collect_expired(
        self, items: list[InformationMetadata]
    ) -> list[InformationMetadata]:
        """从列表中收集所有过期的 Information。"""
        return [item for item in items if self.is_expired(item)]

    # ── 标记 Forgotten ────────────────────────────────────────────────────

    def mark_for_forget(
        self,
        metadata: InformationMetadata,
        reason: str = "",
    ) -> tuple[bool, str]:
        """标记信息为待遗忘（返回 governance_required 状态）。

        如果信息为 PERSISTENT 等级，需要 Governance 审批后执行 forget()。
        其他等级直接执行遗忘。
        """
        if metadata.state not in (InformationState.VALIDATED, InformationState.CREATED):
            return (False, f"信息状态 {metadata.state.value} 不可被遗忘（需 VALIDATED 或 CREATED）")

        if metadata.persistence_level == PersistenceLevel.PERSISTENT:
            # PERSISTENT 等级需要 Governance 审批
            forget_id = f"forget-{metadata.address.id}"
            self._pending[forget_id] = {
                "metadata": metadata,
                "reason": reason,
            }
            self._emit(
                EventType.GOVERNANCE_APPROVAL_REQUESTED,
                {
                    "forget_id": forget_id,
                    "unit_id": metadata.address.id,
                    "reason": reason,
                    "requestor": _SOURCE,
                },
            )
            return (False, f"需要 Governance 审批; forget_id={forget_id}")

        # 非 PERSISTENT → 直接执行
        return self.forget(metadata, governance_approved=True)

    # ── 遗忘执行 ─────────────────────────────────────────────────────────

    def forget(
        self,
        metadata: InformationMetadata,
        governance_approved: bool = False,
    ) -> tuple[bool, str]:
        """执行信息遗忘。

        流程:
        1. 校验合法性
        2. PERSISTENT 等级需要 governance_approved=True
        3. 发射 INFORMATION_STATUS_CHANGED 事件
           VALIDATED→DEPRECATED（默认）或 VALIDATED→ARCHIVED（显式归档）
        """
        if metadata.state not in (InformationState.VALIDATED, InformationState.CREATED):
            return (False, f"信息状态 {metadata.state.value} 不可遗忘")

        if (
            metadata.persistence_level == PersistenceLevel.PERSISTENT
            and not governance_approved
        ):
            return (False, "PERSISTENT 等级信息需要 Governance 审批")

        # 默认遗忘到 DEPRECATED
        to_state = InformationState.DEPRECATED

        self._emit(
            EventType.INFORMATION_STATUS_CHANGED,
            {
                "unit_id": metadata.address.id,
                "from_state": metadata.state.value,
                "to_state": to_state.value,
                "reason": "forgetting_engine",
                "persistence_level": metadata.persistence_level.value,
            },
        )
        return (True, f"forgotten:{metadata.address.id}→{to_state.value}")

    # ── Governance 回调 ────────────────────────────────────────────────────

    def approve_forget(
        self, forget_id: str, approved_by: str
    ) -> tuple[bool, str]:
        """批准待审批的遗忘申请。"""
        if forget_id not in self._pending:
            return (False, f"forget_id '{forget_id}' 不存在")

        entry = self._pending.pop(forget_id)
        ok, msg = self.forget(
            entry["metadata"],
            governance_approved=True,
        )
        if ok:
            self._emit(
                EventType.GOVERNANCE_APPROVED,
                {
                    "forget_id": forget_id,
                    "approved_by": approved_by,
                    "unit_id": entry["metadata"].address.id,
                },
            )
        return (ok, msg)

    def reject_forget(
        self, forget_id: str, rejected_by: str, reason: str = ""
    ) -> tuple[bool, str]:
        """拒绝待审批的遗忘申请。"""
        if forget_id not in self._pending:
            return (False, f"forget_id '{forget_id}' 不存在")

        self._pending.pop(forget_id)
        self._emit(
            EventType.GOVERNANCE_REJECTED,
            {
                "forget_id": forget_id,
                "rejected_by": rejected_by,
                "reason": reason,
            },
        )
        return (True, "已拒绝")

    # ── 内部方法 ──────────────────────────────────────────────────────────

    def _emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        event = Event(
            event_type=event_type,
            source=_SOURCE,
            payload=payload,
        )
        self._event_bus.publish(event, sync=True)

    @staticmethod
    def _parse_timestamp(ts: str) -> float:
        """解析 ISO 时间戳为浮点数（兼容无微秒格式）。"""
        from datetime import datetime

        try:
            dt = datetime.fromisoformat(ts)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="forgetting_engine",
    name="Forgetting Engine",
    version="1.0.0",
    engine_class="ocos.engines.forgetting_engine.ForgettingEngine",
    capabilities=['forgetting'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
