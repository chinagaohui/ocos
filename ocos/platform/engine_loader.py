"""EngineLoader — 基于 EngineDiscoverer 的动态引擎加载器。

职责：
- 按 manifest 动态加载引擎模块
- 缓存已加载的引擎实例
- 支持按需加载、卸载和重载
"""

from __future__ import annotations

import importlib
from typing import Any, Optional

from ocos.platform.engine_manifest import EngineManifest, EngineDiscoverer


class EngineLoader:
    """引擎加载器。

    根据 EngineManifest 动态加载引擎类并缓存实例。
    """

    def __init__(self, discoverer: Optional[EngineDiscoverer] = None):
        self._discoverer = discoverer or EngineDiscoverer()
        self._loaded: dict[str, tuple[EngineManifest, Any]] = {}

    # ── 加载 ───────────────────────────────────────────────────────────────────

    def load_all(self) -> dict[str, Any]:
        """加载所有 auto_load=True 的引擎。返回 {engine_id: instance}。"""
        manifests = self._discoverer.discover_with_deps()
        result: dict[str, Any] = {}
        for manifest in manifests:
            if manifest.auto_load:
                instance = self._load_single(manifest)
                if instance is not None:
                    result[manifest.engine_id] = instance
        return result

    def load(self, engine_id: str) -> Optional[Any]:
        """按 engine_id 加载单个引擎。"""
        # 检查是否已加载
        if engine_id in self._loaded:
            return self._loaded[engine_id][1]

        manifests = self._discoverer.discover()
        for manifest in manifests:
            if manifest.engine_id == engine_id:
                return self._load_single(manifest)
        return None

    def reload(self, engine_id: str) -> Optional[Any]:
        """重载引擎（卸载 + 重新加载）。"""
        self.unload(engine_id)
        return self.load(engine_id)

    # ── 卸载 ───────────────────────────────────────────────────────────────────

    def unload(self, engine_id: str) -> bool:
        """卸载引擎。返回是否卸载成功。"""
        if engine_id in self._loaded:
            del self._loaded[engine_id]
            return True
        return False

    # ── 查询 ───────────────────────────────────────────────────────────────────

    def get(self, engine_id: str) -> Optional[Any]:
        """获取已加载的引擎实例。"""
        entry = self._loaded.get(engine_id)
        return entry[1] if entry else None

    def list_loaded(self) -> list[str]:
        """列出已加载的引擎 ID。"""
        return list(self._loaded.keys())

    def get_manifest(self, engine_id: str) -> Optional[EngineManifest]:
        """获取已加载引擎的 manifest。"""
        entry = self._loaded.get(engine_id)
        return entry[0] if entry else None

    # ── 内部 ───────────────────────────────────────────────────────────────────

    def _load_single(self, manifest: EngineManifest) -> Optional[Any]:
        if manifest.engine_id in self._loaded:
            return self._loaded[manifest.engine_id][1]

        if not manifest.engine_class:
            return None

        try:
            # 解析 "ocos.engines.reasoning_engine.ReasoningEngine"
            module_path, class_name = manifest.engine_class.rsplit(".", 1)
            module = importlib.import_module(module_path)
            engine_class = getattr(module, class_name, None)
            if engine_class is None:
                return None

            # 实例化
            instance = engine_class()
            self._loaded[manifest.engine_id] = (manifest, instance)
            return instance
        except (ImportError, AttributeError, TypeError):
            return None
