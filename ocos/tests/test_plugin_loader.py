"""
D3 Plugin Loader — 测试套件。

覆盖范围：
  - PluginBase ABC 校验
  - PluginLoader 初始化与搜索路径
  - discover() 全场景（空目录、有效、无效、多路径）
  - load() 全场景（成功、验证失败、导入失败、接口校验、on_load 异常、重复检测）
  - execute() 委托 Sandbox 隔离执行
  - unload() 生命周期清理
  - register_to() CapabilityRegistry 集成
  - 批量操作与重置
  - Edge cases（权限、schema_version 兼容）
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Generator, Optional
from unittest.mock import MagicMock, patch

import pytest

from ocos.platform.plugin_base import PluginBase
from ocos.platform.plugin_loader import LoadResult, LoaderErrorCode, PluginLoader
from ocos.platform.plugin_manifest import PluginManifest, Permission, validate_manifest
from ocos.platform.plugin_sandbox import PluginSandbox, SandboxConfig, SandboxResult


# ══════════════════════════════════════════════════════════════════════════════
# 测试用插件
# ══════════════════════════════════════════════════════════════════════════════


class GoodPlugin(PluginBase):
    """正常插件——用于成功加载测试。"""

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self._state: dict = {}
        self.load_called = False
        self.unload_called = False
        self.executed_actions: list[str] = []

    def on_load(self, config: dict[str, Any]) -> None:
        self._state.update(config)
        self.load_called = True

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        self.executed_actions.append(action)
        return {"action": action, "params": params, "state": dict(self._state)}

    def on_unload(self) -> None:
        self.unload_called = True
        self._state.clear()


class BrokenOnLoadPlugin(PluginBase):
    """on_load 会抛出异常的插件。"""

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)

    def on_load(self, config: dict[str, Any]) -> None:
        raise RuntimeError("on_load 失败: 模拟异常")

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        return {"ok": True}

    def on_unload(self) -> None:
        pass


class BrokenOnUnloadPlugin(PluginBase):
    """on_unload 会抛出异常的插件（不应阻止 unload 完成）。"""

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)

    def on_load(self, config: dict[str, Any]) -> None:
        pass

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        return {"ok": True}

    def on_unload(self) -> None:
        raise RuntimeError("on_unload 失败: 模拟异常，应被捕获")


class StateTrackingPlugin(PluginBase):
    """记录所有生命周期调用的插件。"""

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self.events: list[str] = []

    def on_load(self, config: dict[str, Any]) -> None:
        self.events.append("on_load")

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        self.events.append(f"execute:{action}")
        return {"events": list(self.events)}

    def on_unload(self) -> None:
        self.events.append("on_unload")


class NotAPlugin:
    """未继承 PluginBase 的类——用于接口校验测试。"""

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest

    def on_load(self, config: dict[str, Any]) -> None:
        pass

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        return None

    def on_unload(self) -> None:
        pass


class AnotherPlugin(PluginBase):
    """另一个简单插件，entry_point 与 GoodPlugin 不同。"""

    def __init__(self, manifest: PluginManifest) -> None:
        super().__init__(manifest)
        self._state: dict[str, Any] = {}

    def on_load(self, config: dict[str, Any]) -> None:
        self._state.update(config)

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        return {"action": action, "params": params, "state": dict(self._state)}

    def on_unload(self) -> None:
        self._state.clear()


class ThirdPlugin(PluginBase):
    """第三个插件，用于批量加载测试。"""

    def on_load(self, config: dict[str, Any]) -> None:
        pass

    def execute(self, action: str, params: dict[str, Any]) -> Any:
        return {"ok": True}

    def on_unload(self) -> None:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sandbox() -> PluginSandbox:
    """创建一个默认配置的 Sandbox。"""
    return PluginSandbox(SandboxConfig())


@pytest.fixture
def loader(sandbox: PluginSandbox) -> PluginLoader:
    """创建一个 PluginLoader 实例。"""
    return PluginLoader(sandbox)


@pytest.fixture
def valid_manifest() -> PluginManifest:
    """一个有效的 PluginManifest（指向 GoodPlugin）。"""
    return PluginManifest(
        name="test-plugin",
        version="1.0.0",
        entry_point="ocos.tests.test_plugin_loader:GoodPlugin",
        description="测试用插件",
        required_permissions=(Permission.FILE_READ,),
        timeout_seconds=10,
    )


@pytest.fixture
def temp_plugin_dir() -> Generator[Path, None, None]:
    """创建临时插件目录，含有效 plugin.json 和无效配置。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        yield base


def _write_plugin_json(dir_path: Path, data: dict) -> Path:
    """在指定目录下写入 plugin.json。"""
    dir_path.mkdir(parents=True, exist_ok=True)
    manifest_path = dir_path / "plugin.json"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return manifest_path


# ══════════════════════════════════════════════════════════════════════════════
# Test: PluginBase ABC
# ══════════════════════════════════════════════════════════════════════════════


class TestPluginBase:
    """PluginBase ABC 基础行为。"""

    def test_cannot_instantiate_abc(self) -> None:
        """不能直接实例化 PluginBase。"""
        with pytest.raises(TypeError, match="abstract"):
            PluginBase(PluginManifest(name="test"))  # type: ignore[abstract]

    def test_subclass_must_implement_execute(self) -> None:
        """子类必须实现 execute 方法。"""
        with pytest.raises(TypeError, match="execute"):

            class MissingExecute(PluginBase):  # type: ignore[abstract]
                def on_load(self, config: dict) -> None:
                    pass

                def on_unload(self) -> None:
                    pass

            MissingExecute(PluginManifest(name="test"))

    def test_good_plugin_instantiates(self) -> None:
        """GoodPlugin 能正常实例化。"""
        manifest = PluginManifest(name="good")
        plugin = GoodPlugin(manifest)
        assert isinstance(plugin, PluginBase)
        assert plugin.manifest is manifest
        assert plugin.manifest.name == "good"

    def test_full_lifecycle(self) -> None:
        """完整生命周期：on_load → execute → on_unload。"""
        manifest = PluginManifest(name="lifecycle")
        plugin = GoodPlugin(manifest)

        plugin.on_load({"key": "value"})
        assert plugin.load_called
        assert plugin._state == {"key": "value"}

        result = plugin.execute("run", {"data": 42})
        assert result == {"action": "run", "params": {"data": 42}, "state": {"key": "value"}}
        assert plugin.executed_actions == ["run"]

        plugin.on_unload()
        assert plugin.unload_called
        assert plugin._state == {}


# ══════════════════════════════════════════════════════════════════════════════
# Test: PluginLoader 初始化
# ══════════════════════════════════════════════════════════════════════════════


class TestPluginLoaderInit:
    """PluginLoader 初始化。"""

    def test_default_search_paths(self, sandbox: PluginSandbox) -> None:
        """默认搜索路径为 ['plugins', './plugins']。"""
        loader = PluginLoader(sandbox)
        assert len(loader.search_paths) == 2
        assert all(isinstance(p, Path) for p in loader.search_paths)

    def test_custom_search_paths(self, sandbox: PluginSandbox) -> None:
        """自定义搜索路径。"""
        loader = PluginLoader(sandbox, search_paths=["/tmp/plugins", "/opt/plugins"])
        assert len(loader.search_paths) == 2
        assert str(loader.search_paths[0]) == "/tmp/plugins"
        assert str(loader.search_paths[1]) == "/opt/plugins"

    def test_sandbox_property(self, sandbox: PluginSandbox) -> None:
        """sandbox 属性返回注入的实例。"""
        loader = PluginLoader(sandbox)
        assert loader.sandbox is sandbox

    def test_initial_state(self, loader: PluginLoader) -> None:
        """初始化后没有已加载的插件。"""
        assert loader.loaded_count == 0
        assert loader.list_loaded() == []


# ══════════════════════════════════════════════════════════════════════════════
# Test: discover()
# ══════════════════════════════════════════════════════════════════════════════


class TestDiscover:
    """插件发现测试。"""

    def test_discover_empty_dir(self, sandbox: PluginSandbox) -> None:
        """空目录不返回任何 Manifest。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PluginLoader(sandbox, search_paths=[tmpdir])
            manifests = loader.discover()
            assert manifests == []

    def test_discover_missing_path(self, loader: PluginLoader) -> None:
        """不存在的路径跳过，不报错。"""
        loader = PluginLoader(
            loader.sandbox,
            search_paths=["/nonexistent/path/xyz123"],
        )
        manifests = loader.discover()
        assert manifests == []

    def test_discover_single_plugin(self, temp_plugin_dir: Path) -> None:
        """发现一个有效插件。"""
        sandbox = PluginSandbox()
        plugin_dir = temp_plugin_dir / "my_plugin"
        _write_plugin_json(plugin_dir, {
            "name": "my-plugin",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
            "version": "2.0.0",
            "description": "A test plugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "my-plugin"
        assert manifests[0].version == "2.0.0"
        assert manifests[0].entry_point == "ocos.tests.test_plugin_loader:GoodPlugin"

    def test_discover_multiple_plugins(self, temp_plugin_dir: Path) -> None:
        """发现多个插件。"""
        sandbox = PluginSandbox()
        for name in ("alpha", "beta", "gamma"):
            _write_plugin_json(temp_plugin_dir / name, {
                "name": name,
                "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
            })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        manifests = loader.discover()
        assert len(manifests) == 3
        names = [m.name for m in manifests]
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" in names

    def test_discover_skips_bad_json(self, temp_plugin_dir: Path) -> None:
        """非法 JSON 被跳过并 warn。"""
        sandbox = PluginSandbox()
        bad_dir = temp_plugin_dir / "bad_plugin"
        bad_dir.mkdir()
        (bad_dir / "plugin.json").write_text("not valid json", encoding="utf-8")
        _write_plugin_json(temp_plugin_dir / "good_plugin", {
            "name": "good",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        with pytest.warns(UserWarning, match="非法|invalid|skip"):
            manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "good"

    def test_discover_skips_missing_fields(self, temp_plugin_dir: Path) -> None:
        """缺少必填字段的 plugin.json 被跳过。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "no_name", {
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        _write_plugin_json(temp_plugin_dir / "valid", {
            "name": "valid",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        with pytest.warns(UserWarning):
            manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "valid"

    def test_discover_skips_invalid_entry_point(self, temp_plugin_dir: Path) -> None:
        """无效 entry_point 格式的被跳过。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "bad_ep", {
            "name": "bad-ep",
            "entry_point": "invalid-format",
        })
        _write_plugin_json(temp_plugin_dir / "valid", {
            "name": "valid",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        with pytest.warns(UserWarning):
            manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "valid"

    def test_discover_with_permissions(self, temp_plugin_dir: Path) -> None:
        """discover 能解析 required_permissions。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "perm_plugin", {
            "name": "perm-plugin",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
            "required_permissions": ["file_read", "file_write"],
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        manifests = loader.discover()
        assert len(manifests) == 1
        perms = manifests[0].required_permissions
        assert Permission.FILE_READ in perms
        assert Permission.FILE_WRITE in perms

    def test_discover_skips_unknown_permission(self, temp_plugin_dir: Path) -> None:
        """未知 Permission 值被跳过（该插件仍可被加载但不会包含该权限）。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "unknown_perm", {
            "name": "unknown-perm",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
            "required_permissions": ["file_read", "super_admin"],
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        with pytest.warns(UserWarning):
            manifests = loader.discover()
        assert len(manifests) == 1
        assert len(manifests[0].required_permissions) == 1
        assert manifests[0].required_permissions[0] == Permission.FILE_READ

    def test_discover_schema_version_compat(self, temp_plugin_dir: Path) -> None:
        """schema_version 字段不阻塞发现，被忽略在 metadata 中。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "v2_plugin", {
            "name": "v2-plugin",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
            "schema_version": "2.0",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "v2-plugin"
        # schema_version 不在 mantiest 标准字段中，应进入 metadata
        assert manifests[0].metadata.get("schema_version") == "2.0"


# ══════════════════════════════════════════════════════════════════════════════
# Test: load()
# ══════════════════════════════════════════════════════════════════════════════


class TestLoad:
    """插件加载测试。"""

    def test_load_success(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """成功加载一个插件。"""
        result = loader.load(valid_manifest)
        assert result.success
        assert result.code == LoaderErrorCode.LOAD_OK
        assert result.plugin_id
        assert "test-plugin" in result.message
        assert loader.loaded_count == 1

        # 验证实例已创建
        instance = loader.get_instance(result.plugin_id)
        assert isinstance(instance, GoodPlugin)
        assert instance.load_called

    def test_load_returns_plugin_id(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """load 返回的 plugin_id 可用于 execute。"""
        result = loader.load(valid_manifest)
        assert result.plugin_id
        exec_result = loader.execute(result.plugin_id, "run", {"data": 1})
        assert exec_result.success
        assert exec_result.output == {
            "action": "run",
            "params": {"data": 1},
            "state": {},
        }

    def test_load_invalid_manifest(self, loader: PluginLoader) -> None:
        """无效 manifest 的加载被拒绝。"""
        bad_manifest = PluginManifest(name="")  # 空名称
        result = loader.load(bad_manifest)
        assert not result.success
        assert result.code == LoaderErrorCode.LOAD_FAILED
        assert "验证失败" in result.message or "为空" in result.message

    def test_load_import_failure(self, loader: PluginLoader) -> None:
        """不存在的模块路径。"""
        manifest = PluginManifest(
            name="ghost-plugin",
            entry_point="nonexistent.module:Plugin",
        )
        result = loader.load(manifest)
        assert not result.success
        assert result.code == LoaderErrorCode.LOAD_FAILED
        assert "导入模块失败" in result.message or "ImportError" in result.message

    def test_load_class_not_found(self, loader: PluginLoader) -> None:
        """模块中找不到入口类。"""
        manifest = PluginManifest(
            name="missing-class",
            entry_point="ocos.tests.test_plugin_loader:NonExistentClass",
        )
        result = loader.load(manifest)
        assert not result.success
        assert "未找到类" in result.message

    def test_load_not_a_plugin_base(self, loader: PluginLoader) -> None:
        """入口类未继承 PluginBase。"""
        manifest = PluginManifest(
            name="not-a-plugin",
            entry_point="ocos.tests.test_plugin_loader:NotAPlugin",
        )
        result = loader.load(manifest)
        assert not result.success
        assert "未继承 PluginBase" in result.message

    def test_load_on_load_exception(self, loader: PluginLoader) -> None:
        """on_load 抛出异常时回滚加载。"""
        manifest = PluginManifest(
            name="broken-load",
            entry_point="ocos.tests.test_plugin_loader:BrokenOnLoadPlugin",
        )
        result = loader.load(manifest)
        assert not result.success
        assert "on_load" in result.message or "回调" in result.message
        # 确认 Sandbox 中也回滚了
        assert loader.loaded_count == 0

    def test_load_duplicate_entry_point(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """相同 entry_point 重复加载返回已有 plugin_id。"""
        result1 = loader.load(valid_manifest)
        assert result1.success

        with pytest.warns(UserWarning, match="重复加载"):
            result2 = loader.load(valid_manifest)
        assert result2.success  # 返回成功（已有）
        assert result2.code == LoaderErrorCode.LOAD_DUPLICATE
        assert result2.plugin_id == result1.plugin_id  # 相同 ID

        # 不应创建新实例
        assert loader.loaded_count == 1

    def test_load_with_config(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """on_load 能接收 config。"""
        result = loader.load(valid_manifest, config={"custom": "value"})
        instance = loader.get_instance(result.plugin_id)
        assert isinstance(instance, GoodPlugin)
        assert instance._state == {"custom": "value"}

    def test_load_sandbox_integration(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """加载的插件在 Sandbox 中有 slot。"""
        result = loader.load(valid_manifest)
        pid = result.plugin_id

        # 通过 sandbox 内部检查 slot 是否有 plugin_instance
        slot = loader.sandbox._plugins.get(pid)  # type: ignore[attr-defined]
        assert slot is not None
        assert slot.plugin_instance is not None
        assert isinstance(slot.plugin_instance, GoodPlugin)

    def test_load_multiple_plugins(self, loader: PluginLoader) -> None:
        """能加载多个不同的插件。"""
        m1 = PluginManifest(
            name="plugin-a",
            entry_point="ocos.tests.test_plugin_loader:GoodPlugin",
        )
        m2 = PluginManifest(
            name="plugin-b",
            entry_point="ocos.tests.test_plugin_loader:StateTrackingPlugin",
        )
        r1 = loader.load(m1)
        r2 = loader.load(m2)
        assert r1.success
        assert r2.success
        assert r1.plugin_id != r2.plugin_id
        assert loader.loaded_count == 2

        loaded = loader.list_loaded()
        assert len(loaded) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Test: execute()
# ══════════════════════════════════════════════════════════════════════════════


class TestExecute:
    """插件执行测试。"""

    def test_execute_success(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """execute 通过 sandbox 路由到真实插件实例。"""
        result = loader.load(valid_manifest)
        pid = result.plugin_id
        exec_result = loader.execute(pid, "run", {"k": "v"})
        assert exec_result.success
        assert exec_result.output["action"] == "run"
        assert exec_result.output["params"] == {"k": "v"}

    def test_execute_without_params(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """execute 可不传 params。"""
        result = loader.load(valid_manifest)
        exec_result = loader.execute(result.plugin_id, "run")
        assert exec_result.success

    def test_execute_nonexistent_plugin(self, loader: PluginLoader) -> None:
        """不存在的 plugin_id 执行时抛出 ValueError。"""
        with pytest.raises(ValueError, match="未加载"):
            loader.execute("nonexistent", "run")

    def test_execute_tracing(self, loader: PluginLoader) -> None:
        """状态跟踪插件的 execute 结果包含事件历史。"""
        manifest = PluginManifest(
            name="tracker",
            entry_point="ocos.tests.test_plugin_loader:StateTrackingPlugin",
        )
        result = loader.load(manifest)
        pid = result.plugin_id

        r1 = loader.execute(pid, "first")
        assert r1.success
        assert r1.output["events"] == ["on_load", "execute:first"]

        r2 = loader.execute(pid, "second")
        assert r2.success
        assert r2.output["events"] == [
            "on_load", "execute:first", "execute:second",
        ]


# ══════════════════════════════════════════════════════════════════════════════
# Test: unload()
# ══════════════════════════════════════════════════════════════════════════════


class TestUnload:
    """插件卸载测试。"""

    def test_unload_success(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """成功卸载插件。"""
        result = loader.load(valid_manifest)
        pid = result.plugin_id
        assert loader.loaded_count == 1

        success = loader.unload(pid)
        assert success
        assert loader.loaded_count == 0
        assert loader.get_instance(pid) is None

    def test_unload_calls_on_unload(self, loader: PluginLoader) -> None:
        """unload 调用插件的 on_unload。"""
        manifest = PluginManifest(
            name="tracker",
            entry_point="ocos.tests.test_plugin_loader:StateTrackingPlugin",
        )
        result = loader.load(manifest)
        instance = loader.get_instance(result.plugin_id)
        assert isinstance(instance, StateTrackingPlugin)
        assert instance.events == ["on_load"]

        loader.unload(result.plugin_id)
        assert "on_unload" in instance.events

    def test_unload_nonexistent(self, loader: PluginLoader) -> None:
        """卸载不存在的插件返回 False。"""
        assert not loader.unload("nonexistent")

    def test_unload_sandbox_cleanup(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """卸载后 Sandbox 中不再有该插件。"""
        result = loader.load(valid_manifest)
        pid = result.plugin_id
        slot = loader.sandbox._plugins.get(pid)  # type: ignore[attr-defined]
        assert slot is not None

        loader.unload(pid)
        slot_after = loader.sandbox._plugins.get(pid)  # type: ignore[attr-defined]
        assert slot_after is None  # Sandbox 已移除

    def test_unload_broken_on_unload(self, loader: PluginLoader) -> None:
        """on_unload 抛出异常不应阻止卸载完成。"""
        manifest = PluginManifest(
            name="broken-unload",
            entry_point="ocos.tests.test_plugin_loader:BrokenOnUnloadPlugin",
        )
        result = loader.load(manifest)
        pid = result.plugin_id
        assert loader.loaded_count == 1

        # on_unload 异常被捕获，unload 仍成功
        success = loader.unload(pid)
        assert success
        assert loader.loaded_count == 0

    def test_unload_cleans_entry_point_index(self, loader: PluginLoader, valid_manifest: PluginManifest) -> None:
        """卸载后 entry_point 索引也被清除。"""
        result = loader.load(valid_manifest)
        pid = result.plugin_id

        loader.unload(pid)
        # 相同 entry_point 不再被判定为重复
        result2 = loader.load(valid_manifest)
        # 应成功且不是 DUPLICATE 码
        assert result2.success
        assert result2.code != LoaderErrorCode.LOAD_DUPLICATE


# ══════════════════════════════════════════════════════════════════════════════
# Test: register_to()
# ══════════════════════════════════════════════════════════════════════════════


class TestRegisterTo:
    """CapabilityRegistry 集成测试。"""

    def test_register_to_registry(self, loader: PluginLoader) -> None:
        """register_to 将 manifest 注册到 CapabilityRegistry。"""
        from ocos.platform.capability_registry import CapabilityRegistry, CapabilityType

        registry = CapabilityRegistry()
        manifest = PluginManifest(
            name="registry-test",
            version="1.0.0",
            entry_point="ocos.tests.test_plugin_loader:GoodPlugin",
            description="测试注册",
        )

        # 先 discover
        cids = loader.register_to(registry, manifests=[manifest])
        assert len(cids) == 1

        descriptor = registry.get(cids[0])
        assert descriptor is not None
        assert descriptor.type == CapabilityType.PLUGIN.value
        assert descriptor.name == "registry-test"
        assert descriptor.entry_point == "ocos.tests.test_plugin_loader:GoodPlugin"

    def test_register_to_multiple(self, loader: PluginLoader) -> None:
        """批量注册多个插件。"""
        from ocos.platform.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        manifests = [
            PluginManifest(name="a", entry_point="ocos.tests.test_plugin_loader:GoodPlugin"),
            PluginManifest(name="b", entry_point="ocos.tests.test_plugin_loader:StateTrackingPlugin"),
        ]

        cids = loader.register_to(registry, manifests=manifests)
        assert len(cids) == 2
        assert registry.count == 2

    def test_register_to_empty(self, loader: PluginLoader) -> None:
        """空列表返回空结果。"""
        from ocos.platform.capability_registry import CapabilityRegistry

        registry = CapabilityRegistry()
        cids = loader.register_to(registry, manifests=[])
        assert cids == []

    def test_register_to_uses_discovered(self, temp_plugin_dir: Path) -> None:
        """不传 manifests 时使用最近 discover() 结果。"""
        from ocos.platform.capability_registry import CapabilityRegistry

        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "auto_reg", {
            "name": "auto-reg",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        loader.discover()

        registry = CapabilityRegistry()
        cids = loader.register_to(registry)
        assert len(cids) == 1
        assert registry.find_by_name("auto-reg") is not None


# ══════════════════════════════════════════════════════════════════════════════
# Test: 批量操作与重置
# ══════════════════════════════════════════════════════════════════════════════


class TestBatchOps:
    """批量操作测试。"""

    def test_load_all(self, temp_plugin_dir: Path) -> None:
        """load_all 批量加载所有已发现的插件。"""
        sandbox = PluginSandbox()
        plugins = [
            ("a", "ocos.tests.test_plugin_loader:GoodPlugin"),
            ("b", "ocos.tests.test_plugin_loader:AnotherPlugin"),
            ("c", "ocos.tests.test_plugin_loader:ThirdPlugin"),
        ]
        for name, ep in plugins:
            _write_plugin_json(temp_plugin_dir / name, {
                "name": name,
                "entry_point": ep,
            })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        loader.discover()

        results = loader.load_all()
        assert len(results) == 3
        assert all(r.success for r in results)
        assert loader.loaded_count == 3

    def test_load_all_with_config(self, temp_plugin_dir: Path) -> None:
        """load_all 可将 config 传递给所有插件。"""
        sandbox = PluginSandbox()
        _write_plugin_json(temp_plugin_dir / "cfg_a", {
            "name": "cfg-a",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        _write_plugin_json(temp_plugin_dir / "cfg_b", {
            "name": "cfg-b",
            "entry_point": "ocos.tests.test_plugin_loader:GoodPlugin",
        })
        loader = PluginLoader(sandbox, search_paths=[str(temp_plugin_dir)])
        loader.discover()
        results = loader.load_all(config={"global": True})
        for r in results:
            instance = loader.get_instance(r.plugin_id)
            assert isinstance(instance, GoodPlugin)
            assert instance._state == {"global": True}

    def test_unload_all(self, loader: PluginLoader) -> None:
        """卸载所有已加载插件。"""
        manifests = [
            PluginManifest(name="p0", entry_point="ocos.tests.test_plugin_loader:GoodPlugin"),
            PluginManifest(name="p1", entry_point="ocos.tests.test_plugin_loader:AnotherPlugin"),
            PluginManifest(name="p2", entry_point="ocos.tests.test_plugin_loader:ThirdPlugin"),
        ]
        for m in manifests:
            loader.load(m)
        assert loader.loaded_count == 3

        count = loader.unload_all()
        assert count == 3
        assert loader.loaded_count == 0

    def test_reset(self, loader: PluginLoader) -> None:
        """reset 卸载所有插件并清空发现列表。"""
        m = PluginManifest(name="r", entry_point="ocos.tests.test_plugin_loader:GoodPlugin")
        loader.load(m)
        loader._discovered = [m]

        loader.reset()
        assert loader.loaded_count == 0
        assert loader._discovered == []


# ══════════════════════════════════════════════════════════════════════════════
# Test: find_by_name / list_loaded
# ══════════════════════════════════════════════════════════════════════════════


class TestQuery:
    """查询方法测试。"""

    def test_find_by_name(self, loader: PluginLoader) -> None:
        """按名称查找插件实例。"""
        m = PluginManifest(name="finder", entry_point="ocos.tests.test_plugin_loader:GoodPlugin")
        loader.load(m)
        instance = loader.find_by_name("finder")
        assert instance is not None
        assert isinstance(instance, GoodPlugin)

    def test_find_by_name_missing(self, loader: PluginLoader) -> None:
        """找不到返回 None。"""
        assert loader.find_by_name("ghost") is None

    def test_list_loaded(self, loader: PluginLoader) -> None:
        """list_loaded 返回所有已加载插件的元组。"""
        m1 = PluginManifest(name="list-a", version="1.0", entry_point="ocos.tests.test_plugin_loader:GoodPlugin")
        m2 = PluginManifest(name="list-b", version="2.0", entry_point="ocos.tests.test_plugin_loader:StateTrackingPlugin")
        r1 = loader.load(m1)
        r2 = loader.load(m2)

        loaded = loader.list_loaded()
        assert len(loaded) == 2
        items = {(pid, name) for pid, name, _ in loaded}
        assert (r1.plugin_id, "list-a") in items
        assert (r2.plugin_id, "list-b") in items


# ══════════════════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试。"""

    def test_execute_stub_fallback(self, sandbox: PluginSandbox) -> None:
        """未设置 plugin_instance 的 slot 诚实失败（GAP-P0-4 前 stub 假成功）。"""
        loader = PluginLoader(sandbox)
        # 直接通过 sandbox.load 注册（不通过 loader.load，不设置 plugin_instance）
        manifest = PluginManifest(
            name="stub-test",
            entry_point="ocos.tests.test_plugin_loader:GoodPlugin",
            required_permissions=(Permission.FILE_READ,),
        )
        pid = sandbox.load(manifest)

        # 此时 slot 无 plugin_instance，execute 应诚实失败（不再伪装成功）
        result = sandbox.execute(pid, "some_action", {"k": "v"})
        assert result.success is False
        assert "no plugin instance loaded" in result.error

    def test_permission_enforced_by_sandbox(self, loader: PluginLoader) -> None:
        """超出 Sandbox 允许范围的权限被拒绝。"""
        # Sandbox 默认允许 FILE_READ, FILE_WRITE, NETWORK, SYSTEM
        # 但是我们的 SandboxConfig 默认 allowed_permissions 包含了所有权限
        # 需要创建一个严格配置
        config = SandboxConfig(allowed_permissions=(Permission.FILE_READ,))
        strict_sandbox = PluginSandbox(config)
        strict_loader = PluginLoader(strict_sandbox)

        manifest = PluginManifest(
            name="over-perm",
            entry_point="ocos.tests.test_plugin_loader:GoodPlugin",
            required_permissions=(Permission.NETWORK,),  # 不在 FILE_READ 范围内
        )
        result = strict_loader.load(manifest)
        assert not result.success
        assert "权限" in result.message or "Sandbox" in result.message

    def test_file_not_found_import_fails_gracefully(self, loader: PluginLoader) -> None:
        """不存在的模块导入失败返回清晰的错误消息。"""
        manifest = PluginManifest(
            name="ghost",
            entry_point="some.random.module_that_does_not_exist:Plugin",
        )
        result = loader.load(manifest)
        assert not result.success
        assert result.code == LoaderErrorCode.LOAD_FAILED
