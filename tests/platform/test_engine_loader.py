"""EngineLoader 测试。"""
from __future__ import annotations

import pytest

from ocos.platform.engine_loader import EngineLoader
from ocos.platform.engine_manifest import EngineManifest


class TestEngineLoader:
    def test_load_all(self):
        """load_all 加载 auto_load=True 的引擎。"""
        loader = EngineLoader()
        engines = loader.load_all()
        assert isinstance(engines, dict)

    def test_load_all_returns_dict(self):
        """load_all 返回 dict[str, Any]。"""
        loader = EngineLoader()
        result = loader.load_all()
        assert isinstance(result, dict)

    def test_list_loaded(self):
        """list_loaded 返回已加载引擎列表。"""
        loader = EngineLoader()
        loader.load_all()
        loaded = loader.list_loaded()
        assert isinstance(loaded, list)

    def test_get_nonexistent(self):
        """get 不存在的引擎返回 None。"""
        loader = EngineLoader()
        assert loader.get("nonexistent_engine") is None

    def test_load_nonexistent(self):
        """load 不存在的 engine_id 返回 None。"""
        loader = EngineLoader()
        result = loader.load("__does_not_exist__")
        assert result is None

    def test_unload(self):
        """unload 卸载引擎。"""
        loader = EngineLoader()
        result = loader.unload("test_engine")
        assert result is False  # 未加载

    def test_reload(self):
        """reload 不报错。"""
        loader = EngineLoader()
        result = loader.reload("nonexistent")
        assert result is None

    def test_get_manifest(self):
        """get_manifest 返回 None（未加载）。"""
        loader = EngineLoader()
        assert loader.get_manifest("anything") is None
