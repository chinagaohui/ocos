"""Phase 28 — AgentRegistry: Agent 注册中心。

管理所有 Agent 的生命周期: 注册/查找/状态更新/注销。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ocos.planning.models import VALID_AGENT_TYPES


@dataclass(frozen=True)
class AgentDescriptor:
    """Agent 描述符 — 不可变。"""
    agent_id: str
    agent_type: str  # 由 ocos.planning.models.VALID_AGENT_TYPES 约束
    capabilities: tuple[str, ...]  # 匹配 CapabilityState.name
    status: str = "available"     # available|busy|offline
    success_rate: float = 1.0     # 0.0-1.0
    avg_duration_ms: int = 1000   # 平均执行时长 ms

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id must not be empty")
        if not self.agent_type:
            raise ValueError("agent_type must not be empty")
        if self.success_rate < 0.0 or self.success_rate > 1.0:
            raise ValueError(f"success_rate 0.0-1.0, got {self.success_rate}")
        if self.avg_duration_ms <= 0:
            raise ValueError(f"avg_duration_ms > 0, got {self.avg_duration_ms}")
        if self.status not in ("available", "busy", "offline"):
            raise ValueError(f"status must be available|busy|offline, got {self.status}")


class AgentRegistry:
    """Agent 注册中心。
    线程安全：所有公开方法由 self._lock 保护。"""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}
        self._lock = threading.RLock()

    def register(self, descriptor: AgentDescriptor) -> None:
        """注册 Agent。"""
        with self._lock:
            if descriptor.agent_id in self._agents:
                raise ValueError(f"agent {descriptor.agent_id} already registered")
            self._agents[descriptor.agent_id] = descriptor

    def unregister(self, agent_id: str) -> None:
        """注销 Agent。"""
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"agent {agent_id} not found")
            del self._agents[agent_id]

    def find_by_type(self, agent_type: str) -> list[AgentDescriptor]:
        """按类型查找。"""
        with self._lock:
            return [a for a in self._agents.values() if a.agent_type == agent_type]

    def find_by_capability(self, capability: str) -> list[AgentDescriptor]:
        """按能力查找。"""
        with self._lock:
            return [a for a in self._agents.values() if capability in a.capabilities]

    def get_available(self, agent_type: str) -> AgentDescriptor | None:
        """获取可用的同类型 Agent（按 success_rate 降序）。"""
        with self._lock:
            candidates = [
                a for a in self._agents.values()
                if a.agent_type == agent_type and a.status == "available"
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda a: a.success_rate, reverse=True)
            return candidates[0]

    def update_status(self, agent_id: str, status: str) -> None:
        """更新 Agent 状态（busy/available/offline）。"""
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"agent {agent_id} not found")
            old = self._agents[agent_id]
            self._agents[agent_id] = AgentDescriptor(
                agent_id=old.agent_id,
                agent_type=old.agent_type,
                capabilities=old.capabilities,
                status=status,
                success_rate=old.success_rate,
                avg_duration_ms=old.avg_duration_ms,
            )

    def list_all(self) -> list[AgentDescriptor]:
        """列出所有注册 Agent。"""
        with self._lock:
            return list(self._agents.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._agents)
