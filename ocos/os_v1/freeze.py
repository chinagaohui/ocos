"""Phase 50: Personal Cognitive OS v1.0 — Freeze.

最终冻结 OCOS v1.0 ABI / Constitution / 协议。

OS50-05: Freeze ≠ Dead
    ABI 稳定，但实现可继续演化 (Phase 47)。
    冻结的是接口契约，不是代码。
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import logging
import os
from dataclasses import dataclass, field

from ocos.os_v1.os_types import FreezeManifest

logger = logging.getLogger(__name__)


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

    # ── S4.4: 签名收集（真实签名 → SHA-256，替换占位 v1.0 字符串）──────────

    def _collect_signatures(self) -> list[str]:
        """对 12 个 ABI_MODULES 逐个收集公开签名并哈希。

        签名 = 模块公开可调用符号（函数/类，不含下划线开头）的名称 +
        inspect.signature 序列化；整体 SHA-256 取前 16 hex 作为模块指纹。
        任何模块收集失败 → 该模块指纹为空串（verify 时如实报告，不伪造）。
        """
        return [
            self._module_signature(mod)
            for mod in ABI_MODULES
        ]

    @staticmethod
    def _module_signature(module_name: str) -> str:
        """生成单个模块的 SHA-256 签名指纹。"""
        try:
            mod = importlib.import_module(module_name)
            members: list[str] = []
            for name, obj in inspect.getmembers(mod):
                if name.startswith("_"):
                    continue
                if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                    continue
                # 符号必须定义在本模块（跳过 re-export 的第三方符号）
                try:
                    if getattr(obj, "__module__", None) != module_name:
                        continue
                except Exception:
                    pass
                sig = ""
                try:
                    target = obj.__init__ if inspect.isclass(obj) else obj
                    sig = str(inspect.signature(target))
                except (TypeError, ValueError):
                    sig = f"<no-signature:{getattr(obj, '__qualname__', name)}>"
                members.append(f"{name}::{sig}")
            blob = "\n".join(sorted(members))
            return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
        except Exception as e:
            logger.warning("S4.4: signature collection failed for %s: %s",
                           module_name, e)
            return ""

    # ── S4.4: verify（启动校验）────────────────────────────────────────────

    def verify(self) -> list[str]:
        """校验当前签名 vs manifest 基线。

        返回违规列表；不一致 → FROZEN_VIOLATION warning（OCOS_FREEZE_STRICT=
        true 时 raise）。与 freeze() 后首次运行即基线（存量 diff 属预期，
        见 scripts/verify_freeze.py --baseline）。
        """
        violations: list[str] = []
        current = self._collect_signatures()
        baseline = list(self.manifest.signatures or [])
        if len(baseline) != len(ABI_MODULES):
            violations.append(
                f"FROZEN_VIOLATION: manifest 基线 {len(baseline)} 模块 "
                f"≠ ABI 声明 {len(ABI_MODULES)} 模块（需重新 freeze 基线化）")
        for i, mod in enumerate(ABI_MODULES):
            base = baseline[i] if i < len(baseline) else ""
            cur = current[i] if i < len(current) else ""
            if not base:
                violations.append(
                    f"FROZEN_VIOLATION: {mod} 无基线签名（需 --baseline 固化）")
            elif base != cur:
                violations.append(
                    f"FROZEN_VIOLATION: {mod} 签名漂移 {base} → {cur}")
        if violations:
            message = "; ".join(violations[:5])
            logger.warning("FROZEN_VIOLATION: %s", message)
            if os.environ.get("OCOS_FREEZE_STRICT",
                              "").strip().lower() == "true":
                raise RuntimeError(f"FROZEN_VIOLATION: {message}")
        return violations

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

