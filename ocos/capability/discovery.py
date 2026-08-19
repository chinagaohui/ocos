"""Phase 23-A — CapabilityDiscovery 扫描机制 (§4.4 #1)。

扩展 EngineDiscoverer：除了扫描 ocos/engines/ 的 __manifest__，
还支持从 CapabilityRegistry 声明、模块标注等多种来源发现能力。
"""

from __future__ import annotations

from typing import Optional

from ocos.capability.descriptor import (
    CapabilityDescriptor,
    CapabilityCategory,
    CapabilityStatus,
)
from ocos.capability.provider import (
    ProviderDescriptor,
    ProviderType,
    ProviderStatus,
)
from ocos.capability.registry import CapabilityRegistry
from ocos.logging import get_logger
from ocos.platform.engine_manifest import EngineDiscoverer, EngineManifest

logger = get_logger(__name__)


class CapabilityDiscovery:
    """能力发现器 — 从多种来源扫描并注册能力。

    来源:
      1. EngineManifest 扫描 (ocos/engines/)
      2. 显式注册列表 (registry)
      3. 模块标注 (__capabilities__)

    与 EngineLoader 的关系:
      CapabilityDiscovery 负责"发现"（元数据），
      EngineLoader 负责"加载"（实例化）。
      discovery → registry → loader 构成三段式流水线。
    """

    # Engine capability → CapabilityCategory 映射
    ENGINE_CATEGORY_MAP: dict[str, CapabilityCategory] = {
        "reasoning": CapabilityCategory.REASONING,
        "planning": CapabilityCategory.PLANNING,
        "decision": CapabilityCategory.DECISION,
        "execution": CapabilityCategory.EXECUTION,
        "learning": CapabilityCategory.LEARNING,
        "reflection": CapabilityCategory.REFLECTION,
        "prediction": CapabilityCategory.PREDICTION,
        "communication": CapabilityCategory.COMMUNICATION,
        "perception": CapabilityCategory.PERCEPTION,
        "creativity": CapabilityCategory.CREATIVITY,
    }

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        discoverer: EngineDiscoverer | None = None,
    ):
        self._registry = registry or CapabilityRegistry()
        self._discoverer = discoverer or EngineDiscoverer()

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    # ── 扫描 ────────────────────────────────────────────────────────────────

    def scan_all(self) -> CapabilityRegistry:
        """全量扫描：engines + 显式声明。返回注册表。"""
        self.scan_engines()
        self.scan_registry_bindings()
        return self._registry

    def scan_engines(self) -> list[CapabilityDescriptor]:
        """从引擎 manifest 扫描能力。"""
        manifests = self._discoverer.discover()
        result: list[CapabilityDescriptor] = []

        for manifest in manifests:
            # 每个 engine manifest → ProviderDescriptor
            prov = self._manifest_to_provider(manifest)
            self._registry.register_provider(prov)

            # 每个 capability → CapabilityDescriptor
            for cap_name in manifest.capabilities:
                cap_id = f"ocos.{cap_name}"
                cap_desc = CapabilityDescriptor(
                    capability_id=cap_id,
                    name=f"{manifest.name} — {cap_name}",
                    category=self.ENGINE_CATEGORY_MAP.get(cap_name, CapabilityCategory.CUSTOM),
                    description=f"Auto-discovered from engine: {manifest.engine_id}",
                    version=manifest.version,
                    tags=[manifest.engine_id, cap_name],
                    status=CapabilityStatus.DISCOVERED,
                )
                self._registry.register_capability(cap_desc)
                self._registry.bind(cap_id, prov.provider_id)
                result.append(cap_desc)

        logger.info("scan_engines: discovered %d capabilities from %d manifests",
                     len(result), len(manifests))
        return result

    def scan_registry_bindings(self) -> None:
        """扫描已注册的 provider 和 capability，自动绑定。"""
        for prov in self._registry.list_providers():
            for cap_id in prov.capabilities:
                try:
                    self._registry.bind(cap_id, prov.provider_id)
                except KeyError:
                    # capability 尚未注册，跳过
                    pass

    # ── 手动注册 ────────────────────────────────────────────────────────────

    def register_external_capability(
        self,
        capability_id: str,
        name: str,
        category: CapabilityCategory,
        provider_id: str,
        provider_name: str,
        class_path: str = "",
        **kwargs,
    ) -> CapabilityDescriptor:
        """注册一个外部（非引擎）能力。"""
        desc = CapabilityDescriptor(
            capability_id=capability_id,
            name=name,
            category=category,
            status=CapabilityStatus.DISCOVERED,
            **kwargs,
        )
        prov = ProviderDescriptor(
            provider_id=provider_id,
            name=provider_name,
            provider_type=ProviderType.EXTERNAL,
            class_path=class_path,
            capabilities=[capability_id],
        )
        self._registry.register_capability(desc)
        self._registry.register_provider(prov)
        self._registry.bind(capability_id, provider_id)
        return desc

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _manifest_to_provider(self, manifest: EngineManifest) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id=manifest.engine_id,
            name=manifest.name,
            provider_type=ProviderType.ENGINE,
            class_path=manifest.engine_class,
            capabilities=[f"ocos.{c}" for c in manifest.capabilities],
            singleton=manifest.singleton,
            auto_load=manifest.auto_load,
            version=manifest.version,
        )
