"""
M2 Knowledge Lifecycle — 状态机编排 + 版本管理。

KnowledgeLifecycle 提供知识单元的状态转换编排、版本追踪和生命周期审计。
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timezone
from typing import Any

from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    can_transition,
    get_next_statuses,
)
from ocos.knowledge.store.registry import (
    AccessScope,
    KnowledgeRegistry,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class StatusChangeRecord:
    """状态变更审计记录。"""
    unit_id: str
    from_status: KnowledgeStatus
    to_status: KnowledgeStatus
    changed_by: str
    reason: str
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class KnowledgeLifecycle:
    """知识生命周期管理器。

    负责：
    - 状态机转换的执行与验证
    - 版本递增管理
    - 状态变更审计追踪
    """

    def __init__(self, registry: KnowledgeRegistry):
        self._registry = registry
        self._status_history: list[StatusChangeRecord] = []
        self._on_status_change: list[
            callable[[StatusChangeRecord], None]
        ] = []

    # ── 状态转换 ──

    def change_status(
        self,
        unit_id: str,
        new_status: KnowledgeStatus,
        changed_by: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """改变知识单元的状态。

        验证转换合法性，执行转换，记录审计。
        Returns:
            (success, message)
        """
        entry = self._registry.get(unit_id, requestor=changed_by)
        if not entry:
            logger.warning("change_status failed: unit %s not found (requestor=%s)",
                           unit_id, changed_by)
            return (False, f"单元 {unit_id} 不存在或无权访问")

        current_status = entry.unit.status

        # 验证状态转换合法性
        if not can_transition(current_status, new_status):
            logger.warning("change_status invalid: %s -> %s (unit=%s)",
                           current_status.value, new_status.value, unit_id)
            return (
                False,
                f"不可从 {current_status.value} 转换到 {new_status.value}；"
                f"允许的目标: {[s.value for s in get_next_statuses(current_status)]}",
            )

        # 执行状态变更 + 版本递增
        ok, msg = self._registry.update(
            unit_id,
            requestor=changed_by,
            status=new_status,
        )
        if not ok:
            logger.error("change_status update failed: unit=%s msg=%s", unit_id, msg)
            return (False, msg)

        # 记录审计
        record = StatusChangeRecord(
            unit_id=unit_id,
            from_status=current_status,
            to_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
        self._status_history.append(record)
        logger.info("change_status: %s %s -> %s (by=%s reason=%s)",
                    unit_id, current_status.value, new_status.value, changed_by, reason)

        # 通知监听器
        for cb in self._on_status_change:
            cb(record)

        return (
            True,
            f"{current_status.value} → {new_status.value} (v{entry.unit.version}+1)",
        )

    def verify(
        self,
        unit_id: str,
        verified_by: str,
        reason: str = "验证通过",
    ) -> tuple[bool, str]:
        """将 CANDIDATE 提升为 VERIFIED。"""
        return self.change_status(
            unit_id,
            KnowledgeStatus.VERIFIED,
            changed_by=verified_by,
            reason=reason,
        )

    def activate(
        self,
        unit_id: str,
        activated_by: str,
        reason: str = "激活",
    ) -> tuple[bool, str]:
        """将 VERIFIED 提升为 ACTIVE。"""
        return self.change_status(
            unit_id,
            KnowledgeStatus.ACTIVE,
            changed_by=activated_by,
            reason=reason,
        )

    def deprecate(
        self,
        unit_id: str,
        deprecated_by: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """将当前状态标记为 DEPRECATED。"""
        return self.change_status(
            unit_id,
            KnowledgeStatus.DEPRECATED,
            changed_by=deprecated_by,
            reason=reason or "标记为已弃用",
        )

    def archive(
        self,
        unit_id: str,
        archived_by: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """将 DEPRECATED 归档为 ARCHIVED。"""
        return self.change_status(
            unit_id,
            KnowledgeStatus.ARCHIVED,
            changed_by=archived_by,
            reason=reason or "归档",
        )

    def reactivate(
        self,
        unit_id: str,
        reactivated_by: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """将 DEPRECATED 恢复为 ACTIVE。"""
        return self.change_status(
            unit_id,
            KnowledgeStatus.ACTIVE,
            changed_by=reactivated_by,
            reason=reason or "恢复激活",
        )

    # ── 版本管理 ──

    def get_version(self, unit_id: str, requestor: str = "") -> int | None:
        """获取知识单元的当前版本号。"""
        entry = self._registry.get(unit_id, requestor=requestor)
        return entry.unit.version if entry else None

    def get_version_history(
        self, unit_id: str, requestor: str = ""
    ) -> list[int]:
        """获取知识单元的所有版本号。

        当前实现通过 update 次数推断版本历史。
        """
        # 通过状态变更记录推断版本变迁
        versions = []
        for record in self._status_history:
            if record.unit_id == unit_id:
                versions.append(1)  # 初始版本
        entry = self._registry.get(unit_id, requestor=requestor)
        if entry:
            versions.append(entry.unit.version)
        return sorted(set(versions)) if versions else []

    # ── 审计追踪 ──

    def get_status_history(
        self,
        unit_id: str | None = None,
        limit: int = 50,
    ) -> list[StatusChangeRecord]:
        """获取状态变更历史。可按 unit_id 过滤。"""
        if unit_id:
            return [
                r for r in self._status_history[-limit:]
                if r.unit_id == unit_id
            ]
        return self._status_history[-limit:]

    def get_active_units(
        self, level: KnowledgeLevel | None = None
    ) -> list[tuple[str, str, KnowledgeLevel, int]]:
        """获取所有 ACTIVE 状态的单元列表。
        
        Returns:
            list of (unit_id, owner, level, version)
        """
        result: list[tuple[str, str, KnowledgeLevel, int]] = []
        entries = self._registry.get_by_status(KnowledgeStatus.ACTIVE)
        for entry in entries:
            if level and entry.unit.level != level:
                continue
            result.append((
                entry.unit.unit_id,
                entry.owner,
                entry.unit.level,
                entry.unit.version,
            ))
        return result

    # ── 事件监听 ──

    def on_status_change(
        self, callback: callable[[StatusChangeRecord], None]
    ) -> None:
        """注册状态变更监听器。"""
        self._on_status_change.append(callback)
