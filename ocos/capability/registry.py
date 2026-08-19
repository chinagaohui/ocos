"""Phase 23-A — CapabilityRegistry 平面注册表 (§4.4 #2)。

职责:
  - 注册/注销 CapabilityDescriptor 和 ProviderDescriptor
  - 按 tag / category / capability_id 查询
  - 解析 capability_id → ProviderDescriptor 的绑定
  - 线程安全 (RLock)

设计:
  - 平面结构（非层级），避免过早抽象
  - 双向索引：能力→提供者 / 提供者→能力
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from ocos.capability.descriptor import (
    CapabilityDescriptor,
    CapabilityCategory,
    CapabilityStatus,
)
from ocos.capability.provider import ProviderDescriptor, ProviderStatus
from ocos.logging import get_logger

logger = get_logger(__name__)


class CapabilityRegistry:
    """平面能力注册表 — 线程安全。

    Usage:
        reg = CapabilityRegistry()
        reg.register_capability(desc)
        reg.register_provider(prov)
        reg.bind(desc.capability_id, prov.provider_id)
        providers = reg.resolve("ocos.reasoning.deductive")
    """

    def __init__(self):
        self._lock = threading.RLock()
        # capability_id → CapabilityDescriptor
        self._capabilities: dict[str, CapabilityDescriptor] = {}
        # provider_id → ProviderDescriptor
        self._providers: dict[str, ProviderDescriptor] = {}
        # capability_id → set of provider_ids
        self._cap_to_providers: dict[str, set[str]] = {}
        # provider_id → set of capability_ids
        self._prov_to_capabilities: dict[str, set[str]] = {}

    # ── 注册 ──────────────────────────────────────────────────────────────

    def register_capability(self, desc: CapabilityDescriptor) -> None:
        with self._lock:
            if desc.capability_id in self._capabilities:
                logger.debug("Capability already registered: %s", desc.capability_id)
                return
            self._capabilities[desc.capability_id] = desc
            self._cap_to_providers.setdefault(desc.capability_id, set())
            logger.info("Capability registered: %s", desc.capability_id)

    def register_provider(self, prov: ProviderDescriptor) -> None:
        with self._lock:
            if prov.provider_id in self._providers:
                logger.debug("Provider already registered: %s", prov.provider_id)
                return
            self._providers[prov.provider_id] = prov
            self._prov_to_capabilities.setdefault(prov.provider_id, set())
            logger.info("Provider registered: %s", prov.provider_id)

    def bind(self, capability_id: str, provider_id: str) -> None:
        """绑定能力到提供者。"""
        with self._lock:
            if capability_id not in self._capabilities:
                raise KeyError(f"Capability not found: {capability_id}")
            if provider_id not in self._providers:
                raise KeyError(f"Provider not found: {provider_id}")
            self._cap_to_providers[capability_id].add(provider_id)
            self._prov_to_capabilities[provider_id].add(capability_id)

    # ── 注销 ──────────────────────────────────────────────────────────────

    def unregister_capability(self, capability_id: str) -> bool:
        with self._lock:
            if capability_id in self._capabilities:
                del self._capabilities[capability_id]
                # 清理反向索引
                for pid in self._cap_to_providers.pop(capability_id, set()):
                    prov_set = self._prov_to_capabilities.get(pid)
                    if prov_set:
                        prov_set.discard(capability_id)
                return True
            return False

    def unregister_provider(self, provider_id: str) -> bool:
        with self._lock:
            if provider_id in self._providers:
                del self._providers[provider_id]
                for cid in self._prov_to_capabilities.pop(provider_id, set()):
                    cap_set = self._cap_to_providers.get(cid)
                    if cap_set:
                        cap_set.discard(provider_id)
                return True
            return False

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get_capability(self, capability_id: str) -> CapabilityDescriptor | None:
        return self._capabilities.get(capability_id)

    def get_provider(self, provider_id: str) -> ProviderDescriptor | None:
        return self._providers.get(provider_id)

    def resolve(self, capability_id: str) -> list[ProviderDescriptor]:
        """解析一个能力的所有提供者。"""
        provider_ids = self._cap_to_providers.get(capability_id, set())
        return [self._providers[pid] for pid in provider_ids if pid in self._providers]

    def list_capabilities(
        self,
        category: CapabilityCategory | None = None,
        tag: str | None = None,
        status: CapabilityStatus | None = None,
    ) -> list[CapabilityDescriptor]:
        """按过滤条件列出能力。"""
        result = []
        for desc in self._capabilities.values():
            if category is not None and desc.category != category:
                continue
            if tag is not None and tag not in desc.tags:
                continue
            if status is not None and desc.status != status:
                continue
            result.append(desc)
        return result

    def list_providers(
        self,
        provider_type: Any | None = None,
        status: ProviderStatus | None = None,
    ) -> list[ProviderDescriptor]:
        result = []
        for prov in self._providers.values():
            if status is not None and prov.status != status:
                continue
            result.append(prov)
        return result

    def find_by_tag(self, tag: str) -> list[CapabilityDescriptor]:
        return [d for d in self._capabilities.values() if tag in d.tags]

    # ── 统计 ──────────────────────────────────────────────────────────────

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    def clear(self) -> None:
        with self._lock:
            self._capabilities.clear()
            self._providers.clear()
            self._cap_to_providers.clear()
            self._prov_to_capabilities.clear()
