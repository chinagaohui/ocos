"""Phase 50: Personal Cognitive OS v1.0 — Freeze.

最终冻结 OCOS v1.0 ABI / Constitution / 协议。

OS50-05: Freeze ≠ Dead
    ABI 稳定，但实现可继续演化 (Phase 47)。
    冻结的是接口契约，不是代码。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.os_v1.os_types import FreezeManifest


# ═══════════════════════════════════════════════════════════════════════════════
# ABI Module List
# ═══════════════════════════════════════════════════════════════════════════════

ABI_MODULES = [
    "ocos.runtime",               # Phase 39
    "ocos.self",                  # Phase 40
    "ocos.memory",                # Phase 41
    "ocos.world_model",           # Phase 42
    "ocos.decision",              # Phase 43
    "ocos.extension",             # Phase 44
    "ocos.capability",            # Phase 45
    "ocos.cognitive_loop",        # Phase 46
    "ocos.evolution",             # Phase 47
    "ocos.personal_intelligence", # Phase 48
    "ocos.cognitive_continuity",  # Phase 49
    "ocos.os_v1",                 # Phase 50
]

# ═══════════════════════════════════════════════════════════════════════════════
# Constitution Reference
# ═══════════════════════════════════════════════════════════════════════════════

CONSTITUTION_PRINCIPLES = [
    "Art.I:  Identity.anchor immutable — 核心身份永不可变",
    "Art.II: Capability ≠ Identity — 外部工具是提供者，不是自我",
    "Art.III: Evolution ≠ Self-Rewrite — 演化需经治理审批",
    "Art.IV: Memory ≠ Truth — 记忆是内部模型，不是外部事实",
    "Art.V: Decision ≠ Execution — 决策与执行分离",
    "Art.VI: No New Before Production — 未稳定前不加新能力",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Protocols
# ═══════════════════════════════════════════════════════════════════════════════

MEMORY_PROTOCOL = {
    "version": "v1",
    "operations": ["record_experience", "aggregate_day", "aggregate_week",
                   "aggregate_month", "aggregate_year", "by_tag", "recent_memory"],
    "aging": "knowledge_aging.KnowledgeAgingEngine",
    "continuity": "cognitive_continuity.LifeMemoryEngine",
}

CAPABILITY_SDK = {
    "version": "v1",
    "interface": "CapabilityProvider",
    "operations": ["register", "unregister", "call", "health_check"],
    "status_model": ["available", "unavailable", "degraded", "unknown"],
}

EXTENSION_SDK = {
    "version": "v1",
    "lifecycle": ["DISCOVERED", "ANALYZING", "VALIDATING", "APPROVED",
                  "INTEGRATING", "ACTIVE", "FROZEN"],
    "forbidden": ["self_repair", "permission_change", "identity_modification",
                  "constitution_amendment"],
}


@dataclass
class OSFreeze:
    """OCOS v1.0 冻结管理器。"""

    manifest: FreezeManifest = field(default_factory=FreezeManifest)

    def freeze(self, tick_id: int) -> FreezeManifest:
        """执行 v1.0 冻结。

        OS50-05: 冻结 ABI，不冻结实现。
        """
        self.manifest = FreezeManifest(
            version="1.0.0",
            frozen_at_tick=tick_id,
            abi_modules=ABI_MODULES,
            constitution_ref="constitution.yaml",
            memory_protocol="v1",
            capability_sdk="v1",
            extension_sdk="v1",
            test_suite="full-regression",
            signatures=self._collect_signatures(),
        )
        return self.manifest

    def _collect_signatures(self) -> list[str]:
        """收集各模块签名。"""
        return [f"{mod}:v1.0" for mod in ABI_MODULES]

    def verify_abi(self, module_name: str) -> bool:
        """验证模块是否在 ABI 列表中。"""
        return module_name in self.manifest.abi_modules

    def protocol_spec(self, protocol: str) -> dict | None:
        """获取协议规范。"""
        if protocol == "memory":
            return MEMORY_PROTOCOL
        if protocol == "capability":
            return CAPABILITY_SDK
        if protocol == "extension":
            return EXTENSION_SDK
        return None

    @property
    def is_frozen(self) -> bool:
        return self.manifest.frozen_at_tick > 0

    @property
    def module_count(self) -> int:
        return len(self.manifest.abi_modules)


__all__ = [
    "ABI_MODULES",
    "CONSTITUTION_PRINCIPLES",
    "MEMORY_PROTOCOL",
    "CAPABILITY_SDK",
    "EXTENSION_SDK",
    "OSFreeze",
]
