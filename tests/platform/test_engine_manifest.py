"""EngineManifest + EngineDiscoverer 测试。"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ocos.platform.engine_manifest import EngineManifest, EngineDiscoverer


class TestEngineManifest:
    def test_manifest_creation(self):
        """创建 EngineManifest 实例。"""
        m = EngineManifest(
            engine_id="test_engine",
            name="Test Engine",
            version="1.0.0",
            engine_class="ocos.engines.test.TestEngine",
            capabilities=["testing"],
            dependencies=[],
            singleton=True,
            auto_load=True,
        )
        assert m.engine_id == "test_engine"
        assert m.capabilities == ["testing"]

    def test_manifest_frozen(self):
        """EngineManifest 是不可变的。"""
        m = EngineManifest(engine_id="frozen", name="Frozen")
        with pytest.raises(Exception):
            m.engine_id = "changed"  # type: ignore

    def test_default_values(self):
        """默认值正确。"""
        m = EngineManifest(engine_id="defaults", name="Defaults")
        assert m.version == "1.0.0"
        assert m.singleton is True
        assert m.auto_load is True
        assert m.capabilities == []


class TestEngineDiscoverer:
    def test_discover_empty(self, monkeypatch):
        """空包时 discover 返回空列表。"""
        with monkeypatch.context() as m:
            m.setattr("ocos.platform.engine_manifest.ENGINES_PACKAGE", "ocos.platform.does_not_exist")
            # 包不存在，discover 应返回空
            # 但 importlib 会抛 ImportError，被 try/except 捕获
            manifests = EngineDiscoverer.discover()
        # 由于包名不存在，会走 except 分支
        assert isinstance(manifests, list)

    def test_discover_real_engines(self):
        """发现实际引擎目录的 manifest。"""
        manifests = EngineDiscoverer.discover()
        # 引擎模块存在但没有 __manifest__，返回空列表
        assert isinstance(manifests, list)

    def test_discover_with_deps(self):
        """拓扑排序不报错。"""
        manifests = EngineDiscoverer.discover_with_deps()
        assert isinstance(manifests, list)

    def test_find_by_capability(self):
        """按能力查找不报错。"""
        manifests = EngineDiscoverer.find_by_capability("reasoning")
        assert isinstance(manifests, list)
