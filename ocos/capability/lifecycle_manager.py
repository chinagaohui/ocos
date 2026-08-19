"""Phase 45: LifecycleManager — 能力生命周期管理。

管理能力的状态变迁:
    REGISTERED → AVAILABLE ↔ BUSY
                    ↓
              DEGRADED / UNAVAILABLE / DEPRECATED

负责任:
    - 激活/停用
    - 降级检测
    - 性能追踪
    - 废弃标记
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import CapabilityState
from ocos.capability.capability_registry import CapabilityRegistry


@dataclass
class LifecycleManager:
    """能力生命周期管理器。"""

    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)

    def activate(self, capability_id: str) -> None:
        """将能力从 REGISTERED → AVAILABLE。"""
        cap = self.registry.get(capability_id)
        if cap and cap.state == CapabilityState.REGISTERED:
            self.registry.update_state(capability_id, CapabilityState.AVAILABLE)

    def mark_busy(self, capability_id: str) -> None:
        self.registry.update_state(capability_id, CapabilityState.BUSY)

    def mark_available(self, capability_id: str) -> None:
        self.registry.update_state(capability_id, CapabilityState.AVAILABLE)

    def degrade(self, capability_id: str, reason: str = "") -> None:
        """降级能力。"""
        self.registry.update_state(capability_id, CapabilityState.DEGRADED)

    def disable(self, capability_id: str) -> None:
        """停用能力。"""
        self.registry.update_state(capability_id, CapabilityState.UNAVAILABLE)

    def deprecate(self, capability_id: str) -> None:
        """废弃能力。"""
        self.registry.update_state(capability_id, CapabilityState.DEPRECATED)

    def record_result(
        self, capability_id: str, success: bool, latency_ticks: int,
    ) -> None:
        """记录执行结果，调整性能分数。"""
        score = 1.0 if success else 0.0
        self.registry.update_performance(capability_id, score)

    def get_state(self, capability_id: str) -> CapabilityState | None:
        cap = self.registry.get(capability_id)
        return cap.state if cap else None


__all__ = ["LifecycleManager"]
