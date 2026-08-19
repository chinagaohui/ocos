"""Phase 50: CapabilityEcosystem — 能力生态适配器。

让 Phase 45 的 Capability Nervous System 接入真实外部工具。

适配器类型:
    - CodexAdapter: 代码生成
    - OpenTaleAdapter: 小说创作
    - BrowserAdapter: 网页交互
    - AnalysisAdapter: 数据分析

OS50-06: 适配器是工具提供者，不是 OCOS 的一部分。
        适配器故障不影响核心认知。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.os_v1.os_types import (
    CapabilityProvider, CapabilityResult, CapabilityStatus,
    IntentDomain,
)


@dataclass
class CodexAdapter:
    """代码生成适配器。

    接入外部代码生成工具（Claude Code / Codex / etc.）。
    """
    provider: CapabilityProvider = field(default_factory=lambda: CapabilityProvider(
        name="codex",
        domain=IntentDomain.CODING.value,
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        description="External code generation provider",
    ))

    def execute(self, task: str) -> CapabilityResult:
        if self.provider.status != CapabilityStatus.AVAILABLE:
            return CapabilityResult(provider="codex", success=False,
                                    error="Codex unavailable")
        return CapabilityResult(provider="codex", success=True,
                                output=f"[codex] {task[:80]}...", duration_ticks=1)


@dataclass
class OpenTaleAdapter:
    """小说创作适配器。

    接入 OpenTale 小说创作系统。
    """
    provider: CapabilityProvider = field(default_factory=lambda: CapabilityProvider(
        name="opentale",
        domain=IntentDomain.WRITING.value,
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        description="OpenTale novel generation provider",
    ))

    def generate(self, prompt: str, genre: str = "") -> CapabilityResult:
        if self.provider.status != CapabilityStatus.AVAILABLE:
            return CapabilityResult(provider="opentale", success=False,
                                    error="OpenTale unavailable")
        genre_tag = f"[{genre}] " if genre else ""
        return CapabilityResult(provider="opentale", success=True,
                                output=f"[opentale] {genre_tag}{prompt[:80]}...",
                                duration_ticks=1)


@dataclass
class BrowserAdapter:
    """浏览器交互适配器。

    接入浏览器自动化工具。
    """
    provider: CapabilityProvider = field(default_factory=lambda: CapabilityProvider(
        name="browser",
        domain=IntentDomain.RESEARCH.value,
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        description="Browser automation provider",
    ))

    def navigate(self, url: str) -> CapabilityResult:
        if self.provider.status != CapabilityStatus.AVAILABLE:
            return CapabilityResult(provider="browser", success=False,
                                    error="Browser unavailable")
        return CapabilityResult(provider="browser", success=True,
                                output=f"[browser] navigating to {url[:60]}...",
                                duration_ticks=1)


@dataclass
class AnalysisAdapter:
    """数据分析适配器。

    接入数据分析工具。
    """
    provider: CapabilityProvider = field(default_factory=lambda: CapabilityProvider(
        name="analysis",
        domain=IntentDomain.ANALYSIS.value,
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        description="Data analysis provider",
    ))

    def analyze(self, data_description: str) -> CapabilityResult:
        if self.provider.status != CapabilityStatus.AVAILABLE:
            return CapabilityResult(provider="analysis", success=False,
                                    error="Analysis unavailable")
        return CapabilityResult(provider="analysis", success=True,
                                output=f"[analysis] {data_description[:80]}...",
                                duration_ticks=1)


@dataclass
class CapabilityEcosystem:
    """能力生态系统——管理所有外部适配器。

    OS50-06: 适配器是可插拔的工具提供者。
    """

    adapters: dict[str, object] = field(default_factory=dict)

    def register(self, adapter: object) -> None:
        name = getattr(getattr(adapter, "provider", None), "name", str(id(adapter)))
        self.adapters[name] = adapter

    def list_available(self) -> list[str]:
        available = []
        for name, adapter in self.adapters.items():
            provider = getattr(adapter, "provider", None)
            if provider and provider.status == CapabilityStatus.AVAILABLE:
                available.append(name)
        return available

    def get_provider(self, name: str) -> CapabilityProvider | None:
        adapter = self.adapters.get(name)
        if adapter:
            return getattr(adapter, "provider", None)
        return None


__all__ = [
    "CodexAdapter", "OpenTaleAdapter",
    "BrowserAdapter", "AnalysisAdapter",
    "CapabilityEcosystem",
]
