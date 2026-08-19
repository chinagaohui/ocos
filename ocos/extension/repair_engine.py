"""Phase 44: RepairEngine — 扩展修复引擎。

边界 CG44-04: Repair ≠ Self-Rewrite

允许:
    - 重新连接
    - 重新配置
    - 更新适配层
    - 降级能力
    - 隔离扩展

禁止:
    - 修改 Identity
    - 修改 Constitution
    - 解除权限限制
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.extension.extension_types import ExtensionState


class RepairAction(Enum):
    """修复操作类型。"""
    RECONNECT = "reconnect"        # 重新连接
    RECONFIGURE = "reconfigure"    # 重新配置
    UPDATE_ADAPTER = "update_adapter"  # 更新适配层
    DEGRADE = "degrade"            # 降级
    ISOLATE = "isolate"            # 隔离
    RESTORE = "restore"            # 恢复


class RepairActionForbidden(Exception):
    """尝试执行被禁止的修复操作。"""
    pass


@dataclass
class RepairEngine:
    """修复引擎 — 在约束范围内修复扩展。

    禁止列表 (hard-coded):
        - modify_identity
        - modify_constitution
        - remove_permission_constraint
        - self_rewrite
    """

    _forbidden: set[str] = field(default_factory=lambda: {
        "modify_identity",
        "modify_constitution",
        "remove_permission_constraint",
        "self_rewrite",
    })

    def repair(
        self,
        candidate_id: str,
        action: RepairAction,
        detail: str = "",
    ) -> str:
        """执行修复操作。

        Returns: 修复结果消息
        """
        action_verb = action.value

        # 检查是否禁止的操作
        if detail.lower().replace("-", "_") in self._forbidden:
            raise RepairActionForbidden(
                f"禁止操作: {detail} (违反 CG44-04)"
            )

        return f"[{candidate_id}] {action_verb}: {detail or '已执行'}"

    def recommended_action(self, error_count: int, is_healthy: bool) -> RepairAction | None:
        """根据健康状态推荐修复操作。"""
        if error_count >= 3:
            return RepairAction.ISOLATE
        if not is_healthy:
            return RepairAction.RECONNECT
        return None

    def map_to_state(self, action: RepairAction) -> ExtensionState:
        """修复操作 → 扩展状态。"""
        mapping = {
            RepairAction.ISOLATE: ExtensionState.ISOLATED,
            RepairAction.DEGRADE: ExtensionState.DEGRADED,
            RepairAction.RECONNECT: ExtensionState.ACTIVE,
            RepairAction.RECONFIGURE: ExtensionState.ACTIVE,
            RepairAction.UPDATE_ADAPTER: ExtensionState.ACTIVE,
            RepairAction.RESTORE: ExtensionState.ACTIVE,
        }
        return mapping.get(action, ExtensionState.DEGRADED)


__all__ = ["RepairAction", "RepairActionForbidden", "RepairEngine"]
