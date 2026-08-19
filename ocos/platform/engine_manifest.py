"""EngineManifest + EngineDiscoverer — 引擎元数据声明与自动发现。

每个引擎文件在模块级别设置 __manifest__ 属性。EngineDiscoverer
通过扫描 ocos/engines 目录自动加载所有 manifest。
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class EngineManifest:
    """引擎元数据声明。"""
    engine_id: str                           # "reasoning_engine"
    name: str                                # "Reasoning Engine"
    version: str = "1.0.0"                   # 语义版本
    engine_class: str = ""                   # "ocos.engines.reasoning_engine.ReasoningEngine"
    capabilities: list[str] = field(default_factory=list)  # ["reasoning"]
    dependencies: list[str] = field(default_factory=list)  # 依赖的能力列表
    singleton: bool = True                   # 是否单例
    auto_load: bool = True                   # 启动时自动加载


ENGINES_PACKAGE = "ocos.engines"


class EngineDiscoverer:
    """引擎自动发现器。

    扫描 ocos/engines 包下的所有模块，读取 __manifest__ 属性。
    """

    @staticmethod
    def discover() -> list[EngineManifest]:
        """发现所有注册的引擎，返回非拓扑排序的列表。"""
        manifests: list[EngineManifest] = []
        try:
            package = importlib.import_module(ENGINES_PACKAGE)
        except ImportError:
            return manifests

        package_path = getattr(package, "__path__", [])
        for importer, modname, ispkg in pkgutil.iter_modules(package_path):
            if ispkg or modname.startswith("_"):
                continue

            full_name = f"{ENGINES_PACKAGE}.{modname}"
            manifest = EngineDiscoverer._load_manifest(full_name)
            if manifest is not None:
                manifests.append(manifest)

        return manifests

    @staticmethod
    def discover_with_deps() -> list[EngineManifest]:
        """发现并按依赖拓扑排序。"""
        manifests = EngineDiscoverer.discover()

        # 拓扑排序（DFS 后序，依赖在前）— 含环检测
        manifest_map = {m.engine_id: m for m in manifests}
        sorted_list: list[EngineManifest] = []
        permanent_mark: set[str] = set()  # 已完成
        temporary_mark: set[str] = set()  # 遍历中（环检测）

        def visit(eid: str):
            if eid in permanent_mark:
                return
            if eid in temporary_mark:
                raise ValueError(
                    f"circular dependency detected at engine: {eid}"
                )
            temporary_mark.add(eid)
            m = manifest_map.get(eid)
            if m is not None:
                for dep in m.dependencies:
                    visit(dep)
                sorted_list.append(m)
            temporary_mark.discard(eid)
            permanent_mark.add(eid)

        for m in manifests:
            visit(m.engine_id)

        return sorted_list

    @staticmethod
    def find_by_capability(capability: str) -> list[EngineManifest]:
        """按能力查找引擎。"""
        return [
            m for m in EngineDiscoverer.discover()
            if capability in m.capabilities
        ]

    @staticmethod
    def _load_manifest(module_name: str) -> Optional[EngineManifest]:
        """从模块加载 __manifest__。"""
        try:
            module = importlib.import_module(module_name)
        except (ImportError, Exception):
            return None
        manifest = getattr(module, "__manifest__", None)
        if isinstance(manifest, EngineManifest):
            return manifest
        return None
