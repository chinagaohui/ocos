"""Phase 44: DiscoveryEngine — 扩展发现。

扫描系统中未知的模块、接口、能力，生成 ExtensionCandidate。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import (
    ExtensionCandidate, ExtensionType,
)


@dataclass
class DiscoveryEngine:
    """发现引擎 — 从文件系统/模块树中发现新扩展。

    发现策略:
        - 注册已知模块路径，扫描未知出现
        - 检查模块的 __init__.py 中声明的 __extension__ 属性
        - 生成 ExtensionCandidate
    """

    known_paths: set[str] = field(default_factory=set)
    _discovered: list[ExtensionCandidate] = field(default_factory=list)

    def register_known(self, *paths: str) -> None:
        """注册已知模块路径。不在这些路径下的即为新发现。"""
        for p in paths:
            self.known_paths.add(p)

    def scan_path(self, path: str, tick_id: int = 0) -> list[ExtensionCandidate]:
        """扫描一个路径，返回新的 ExtensionCandidate。"""
        found: list[ExtensionCandidate] = []
        if path in self.known_paths:
            return found
        # 简化: 基于路径推断扩展类型
        ext_type = self._infer_type(path)
        candidate = ExtensionCandidate(
            candidate_id=f"ext:{path}",
            name=path.split("/")[-1] if "/" in path else path,
            extension_type=ext_type,
            description=f"Discovered at {path}",
            source_path=path,
            discovered_tick=tick_id,
        )
        found.append(candidate)
        self._discovered.extend(found)
        return found

    def _infer_type(self, path: str) -> ExtensionType:
        """从路径推断扩展类型。"""
        lower = path.lower()
        if any(k in lower for k in ("audio", "vision", "sensor", "perception", "input")):
            return ExtensionType.PERCEPTION
        if any(k in lower for k in ("memory", "storage", "db")):
            return ExtensionType.MEMORY
        if any(k in lower for k in ("reason", "infer", "logic")):
            return ExtensionType.REASONING
        if any(k in lower for k in ("tool", "agent", "action", "executor")):
            return ExtensionType.CAPABILITY
        if any(k in lower for k in ("comm", "channel", "output")):
            return ExtensionType.COMMUNICATION
        if any(k in lower for k in ("knowledge", "domain", "ontology")):
            return ExtensionType.KNOWLEDGE
        return ExtensionType.META

    @property
    def discovered(self) -> list[ExtensionCandidate]:
        return list(self._discovered)


__all__ = ["DiscoveryEngine"]
