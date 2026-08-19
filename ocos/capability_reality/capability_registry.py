"""Phase 55: CapabilityRegistry — 真实能力注册表。

不同于 ocos/capability/capability_registry.py 的抽象注册，
这里是可执行的真实能力 —— 每个注册项都绑定了一个可调用的适配器。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, AdapterStatus, AdapterHealth,
    CapabilityCategory,
)


@dataclass
class RegisteredCapability:
    """注册的能力 — descriptor + executor 绑定。"""
    descriptor: CapabilityDescriptor
    executor: Callable | None = None  # 实际执行函数
    status: AdapterStatus = field(default_factory=lambda: AdapterStatus(adapter_id=""))

    def __post_init__(self):
        if not self.status.adapter_id:
            self.status.adapter_id = self.descriptor.name


@dataclass
class CapabilityRegistry:
    """真实能力注册表。

    CR55-04: 只注册已验证可用的能力。
    """

    _capabilities: dict[str, RegisteredCapability] = field(default_factory=dict)
    _by_category: dict[CapabilityCategory, list[str]] = field(default_factory=dict)

    def register(self, descriptor: CapabilityDescriptor,
                 executor: Callable | None = None) -> RegisteredCapability:
        """注册一个新能力。"""
        rc = RegisteredCapability(
            descriptor=descriptor,
            executor=executor,
        )
        self._capabilities[descriptor.name] = rc

        cat = descriptor.category
        if cat not in self._by_category:
            self._by_category[cat] = []
        if descriptor.name not in self._by_category[cat]:
            self._by_category[cat].append(descriptor.name)

        return rc

    def unregister(self, name: str) -> bool:
        cap = self._capabilities.pop(name, None)
        if cap is None:
            return False
        cat = cap.descriptor.category
        if cat in self._by_category and name in self._by_category[cat]:
            self._by_category[cat].remove(name)
        return True

    def get(self, name: str) -> RegisteredCapability | None:
        return self._capabilities.get(name)

    def list_all(self) -> list[RegisteredCapability]:
        return list(self._capabilities.values())

    def list_by_category(self, category: CapabilityCategory) -> list[RegisteredCapability]:
        names = self._by_category.get(category, [])
        return [self._capabilities[n] for n in names if n in self._capabilities]

    def find_executable(self, name: str) -> RegisteredCapability | None:
        """查找一个可执行 (executor != None) 的能力。"""
        cap = self._capabilities.get(name)
        if cap and cap.executor is not None:
            return cap
        return None

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def count(self) -> int:
        return len(self._capabilities)

    def categories(self) -> list[CapabilityCategory]:
        return list(self._by_category.keys())

    def mark_health(self, name: str, status: AdapterStatus) -> None:
        cap = self._capabilities.get(name)
        if cap:
            cap.status = status

    def healthy_count(self) -> int:
        return sum(
            1 for c in self._capabilities.values()
            if c.status.health == AdapterHealth.HEALTHY
        )

    def clear(self) -> None:
        self._capabilities.clear()
        self._by_category.clear()


__all__ = ["RegisteredCapability", "CapabilityRegistry"]
