"""Phase 39.4: Permission Recovery — 待审批状态持久化。

Phase 39.3 已有 PermissionTrace；39.4 增加待审批队列持久化。
重启后恢复: "有 X 个审批等待用户决策"，而非重新发起。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ApprovalStatus(Enum):
    WAITING = "waiting"     # 等待审批
    APPROVED = "approved"   # 已批准
    DENIED = "denied"       # 已拒绝
    EXPIRED = "expired"     # 已过期
    CANCELLED = "cancelled" # 已取消


@dataclass
class PendingApproval:
    """待审批项 — 可序列化到磁盘。

    Fields:
        approval_id:    审批 ID
        permission_id:  关联的 PermissionTrace ID
        capability_id:  请求的 Capability
        action:         操作
        resource:       目标资源
        tick_requested: 请求时的 tick
        status:         审批状态
        reason:         等待原因
        created_at:     创建时间
    """

    approval_id: str
    capability_id: str
    action: str
    resource: str | None = None
    permission_trace_id: str | None = None
    tick_requested: int = 0
    status: ApprovalStatus = ApprovalStatus.WAITING
    reason: str = ""
    created_at: float = field(default_factory=time.time)

    def approve(self) -> None:
        self.status = ApprovalStatus.APPROVED

    def deny(self, reason: str = "") -> None:
        self.status = ApprovalStatus.DENIED
        if reason:
            self.reason = reason

    def cancel(self, reason: str = "") -> None:
        self.status = ApprovalStatus.CANCELLED
        if reason:
            self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "capability_id": self.capability_id,
            "action": self.action,
            "resource": self.resource,
            "permission_trace_id": self.permission_trace_id,
            "tick_requested": self.tick_requested,
            "status": self.status.value,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PendingApproval:
        return cls(
            approval_id=d["approval_id"],
            capability_id=d["capability_id"],
            action=d["action"],
            resource=d.get("resource"),
            permission_trace_id=d.get("permission_trace_id"),
            tick_requested=d.get("tick_requested", 0),
            status=ApprovalStatus(d.get("status", "waiting")),
            reason=d.get("reason", ""),
            created_at=d.get("created_at", 0),
        )


class ApprovalStore:
    """待审批持久化存储。

    存储: ocos_data/approvals/pending.json
    """

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or Path("ocos_data/approvals")
        self._base.mkdir(parents=True, exist_ok=True)
        self._store_path = self._base / "pending.json"
        self._pending: dict[str, PendingApproval] = {}
        self._restore()

    def add(self, capability_id: str, action: str,
            resource: str | None = None, tick_id: int = 0,
            permission_trace_id: str | None = None,
            reason: str = "") -> PendingApproval:
        """添加待审批项。"""
        approval = PendingApproval(
            approval_id=str(uuid.uuid4()),
            capability_id=capability_id,
            action=action,
            resource=resource,
            permission_trace_id=permission_trace_id,
            tick_requested=tick_id,
            reason=reason,
        )
        self._pending[approval.approval_id] = approval
        self._persist()
        return approval

    def approve(self, approval_id: str) -> PendingApproval | None:
        approval = self._pending.get(approval_id)
        if approval:
            approval.approve()
            self._persist()
        return approval

    def deny(self, approval_id: str, reason: str = "") -> PendingApproval | None:
        approval = self._pending.get(approval_id)
        if approval:
            approval.deny(reason)
            self._persist()
        return approval

    def get_waiting(self) -> list[PendingApproval]:
        """获取所有等待中的审批 — 恢复时用。"""
        return [a for a in self._pending.values()
                if a.status == ApprovalStatus.WAITING]

    def get(self, approval_id: str) -> PendingApproval | None:
        return self._pending.get(approval_id)

    def count_waiting(self) -> int:
        return len(self.get_waiting())

    def clear_resolved(self) -> None:
        """清理非 WAITING 状态的审批。"""
        self._pending = {
            k: v for k, v in self._pending.items()
            if v.status == ApprovalStatus.WAITING
        }
        self._persist()

    def _persist(self) -> None:
        data = [a.to_dict() for a in self._pending.values()]
        self._store_path.write_text(json.dumps(data, indent=2))

    def _restore(self) -> None:
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text())
            self._pending = {
                item["approval_id"]: PendingApproval.from_dict(item)
                for item in data
            }
        except (json.JSONDecodeError, KeyError):
            self._pending = {}
