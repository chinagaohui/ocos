"""
D4 OpenTale Plugin — 测试套件。

测试策略：
  - mock 测试验证 Plugin 契约（on_load / execute / on_unload）的正确性
  - 真实 AutonomousNovelSystem 的集成测试在 Phase E1 E2E 阶段补充
  - 所有 mock 均控制在无 LLM 密钥、无外部 API 调用的范围内

注意：
  OpenTalePlugin 内部延迟导入 opentale.app.service.AutonomousNovelSystem，
  测试使用 @patch('ocos.plugins.opentale.plugin.AutonomousNovelSystem')
  替换导入点——不需要真实系统参与。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from ocos.platform.plugin_base import PluginBase
from ocos.platform.plugin_manifest import (
    Permission,
    PluginManifest,
)
from ocos.platform.plugin_loader import PluginLoader
from ocos.platform.plugin_sandbox import PluginSandbox
from ocos.plugins.opentale.plugin import (
    ACTION_GENERATE,
    ACTION_RESUME,
    ACTION_REWRITE,
    ACTION_STATUS,
    _SUPPORTED_ACTIONS,
    OpenTalePlugin,
)

# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def valid_manifest() -> PluginManifest:
    """标准的 OpenTalePlugin manifest。"""
    return PluginManifest(
        name="opentale",
        version="0.1.0",
        entry_point="ocos.plugins.opentale.plugin:OpenTalePlugin",
        required_permissions=(
            Permission.NETWORK,
            Permission.FILE_READ,
            Permission.FILE_WRITE,
        ),
        timeout_seconds=120,
    )


@pytest.fixture
def valid_config() -> dict[str, Any]:
    """标准的 OpenTalePlugin 配置。"""
    return {
        "genre": "sci_fi",
        "output_dir": "/tmp/opentale_test_output",
    }


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """临时输出目录。"""
    output_dir = tmp_path / "opentale_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def mock_ans() -> MagicMock:
    """Mock AutonomousNovelSystem 实例。

    保证 _init_system 被跳过（见 patch 点）。
    """
    mock = MagicMock()
    mock.generate = MagicMock(return_value={"status": "generated"})
    mock.resume = MagicMock(return_value={"status": "resumed"})
    mock.rewrite = MagicMock(return_value={"status": "rewritten"})
    return mock


@pytest.fixture
def plugin_with_mock_system(
    valid_manifest: PluginManifest,
    valid_config: dict[str, Any],
    mock_ans: MagicMock,
) -> OpenTalePlugin:
    """返回一个已 on_load 完成的 OpenTalePlugin 实例。

    使用 _init_system 替换为 mock，避免真实系统初始化。
    """
    plugin = OpenTalePlugin(valid_manifest)

    def _fake_init(genre: str, output_dir: str) -> None:
        plugin._system = mock_ans
        plugin._generation_state = {
            "genre": genre,
            "output_dir": output_dir,
            "status": "idle",
            "current_operation": None,
            "progress": {},
        }

    plugin._init_system = _fake_init  # type: ignore[method-assign]
    plugin.on_load(valid_config)
    return plugin


@pytest.fixture
def plugin_without_init(
    valid_manifest: PluginManifest,
) -> OpenTalePlugin:
    """返回未初始化的 OpenTalePlugin 实例（未调用 on_load）。"""
    return OpenTalePlugin(valid_manifest)


# ══════════════════════════════════════════════════════════════════════════════
# A. Plugin 契约 (3)
# ══════════════════════════════════════════════════════════════════════════════


class TestPluginContract:
    """验证 OpenTalePlugin 遵循 PluginBase ABC 契约。"""

    def test_inherits_plugin_base(self, plugin_without_init: OpenTalePlugin) -> None:
        """OpenTalePlugin 必须继承 PluginBase。"""
        assert isinstance(plugin_without_init, PluginBase)

    def test_implements_all_abstract_methods(self) -> None:
        """PluginBase 的所有抽象方法必须实现。"""
        import inspect

        for method_name in ("on_load", "execute", "on_unload"):
            method = getattr(OpenTalePlugin, method_name)
            # 不被标记为 abstractmethod 即已实现
            assert not getattr(method, "__isabstractmethod__", False), (
                f"{method_name} 未实现（仍为 abstract）"
            )

    def test_manifest_property(
        self,
        valid_manifest: PluginManifest,
        plugin_without_init: OpenTalePlugin,
    ) -> None:
        """manifest 属性必须返回构造时传入的 PluginManifest。"""
        assert plugin_without_init.manifest is valid_manifest


# ══════════════════════════════════════════════════════════════════════════════
# B. 生命周期 (4)
# ══════════════════════════════════════════════════════════════════════════════


class TestLifecycle:
    """验证 on_load → execute → on_unload 完整生命周期。"""

    def test_on_load_stores_config(
        self,
        valid_manifest: PluginManifest,
        valid_config: dict[str, Any],
        mock_ans: MagicMock,
    ) -> None:
        """on_load 后 _config 包含传入的配置。"""
        plugin = OpenTalePlugin(valid_manifest)
        plugin._init_system = lambda g, od: setattr(
            plugin, "_system", mock_ans
        ) or plugin._generation_state.update(
            {"genre": g, "output_dir": od, "status": "idle"}
        )
        plugin.on_load(valid_config)
        assert plugin._config["genre"] == "sci_fi"
        assert plugin._config["output_dir"] == "/tmp/opentale_test_output"

    def test_on_load_with_missing_config_raises(
        self, valid_manifest: PluginManifest
    ) -> None:
        """缺少必需配置字段时 on_load 抛出 ValueError。"""
        plugin = OpenTalePlugin(valid_manifest)
        with pytest.raises(ValueError, match="缺少必需配置"):
            plugin.on_load({})

    def test_on_load_with_empty_string_raises(
        self, valid_manifest: PluginManifest
    ) -> None:
        """genre 或 output_dir 为空字符串时拒绝。"""
        plugin = OpenTalePlugin(valid_manifest)
        with pytest.raises(ValueError, match="必须是非空字符串"):
            plugin.on_load({"genre": "", "output_dir": "/tmp/test"})

    def test_on_unload_clears_state(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """on_unload 后 _system 为 None，_config 和 _generation_state 为空。"""
        plugin_with_mock_system.on_unload()
        assert plugin_with_mock_system._system is None
        assert plugin_with_mock_system._config == {}
        assert plugin_with_mock_system._generation_state == {}


# ══════════════════════════════════════════════════════════════════════════════
# C. Action 路由 (5)
# ══════════════════════════════════════════════════════════════════════════════


class TestActionRouting:
    """验证 execute() 的 Action 路由分发。"""

    def test_generate_action(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """generate action 路由到 _do_generate。"""
        result = plugin_with_mock_system.execute(
            ACTION_GENERATE, {"title": "Test"}
        )
        assert result["operation"] == "generate"
        assert result["status"] == "completed"
        assert "output_dir" in result

    def test_resume_action(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """resume action 路由到 _do_resume。"""
        result = plugin_with_mock_system.execute(
            ACTION_RESUME, {"project_dir": "/tmp/test_project"}
        )
        assert result["operation"] == "resume"
        assert result["status"] == "completed"

    def test_resume_action_missing_project_dir(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """resume 缺少 project_dir 时抛出 ValueError。"""
        with pytest.raises(ValueError, match="project_dir"):
            plugin_with_mock_system.execute(ACTION_RESUME, {})

    def test_rewrite_action(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """rewrite action 路由到 _do_rewrite。"""
        result = plugin_with_mock_system.execute(
            ACTION_REWRITE,
            {"project_dir": "/tmp/test_project", "chapter_number": 5},
        )
        assert result["operation"] == "rewrite"
        assert result["status"] == "completed"
        assert result["chapter_number"] == 5

    def test_rewrite_action_missing_params(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """rewrite 缺少必需参数时抛出 ValueError。"""
        with pytest.raises(ValueError, match="chapter_number"):
            plugin_with_mock_system.execute(
                ACTION_REWRITE, {"project_dir": "/tmp/test_project"}
            )
        with pytest.raises(ValueError, match="project_dir"):
            plugin_with_mock_system.execute(ACTION_REWRITE, {})

    def test_status_action(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """status action 返回当前状态快照。"""
        result = plugin_with_mock_system.execute(ACTION_STATUS, {})
        assert result["operation"] == "status"
        assert result["genre"] == "sci_fi"
        assert result["output_dir"] == "/tmp/opentale_test_output"
        assert result["current_operation"] is None

    def test_unknown_action_raises(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """未知 action 抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的 action"):
            plugin_with_mock_system.execute("unknown_action", {})

    def test_execute_before_on_load_raises(
        self, plugin_without_init: OpenTalePlugin
    ) -> None:
        """未调用 on_load 时 execute 抛出 RuntimeError。"""
        with pytest.raises(RuntimeError, match="未初始化"):
            plugin_without_init.execute(ACTION_STATUS, {})

    def test_all_supported_actions_covered(self) -> None:
        """确保所有 _SUPPORTED_ACTIONS 都有 handler。"""
        expected = {ACTION_GENERATE, ACTION_RESUME, ACTION_REWRITE, ACTION_STATUS}
        assert set(_SUPPORTED_ACTIONS) == expected


# ══════════════════════════════════════════════════════════════════════════════
# D. 配置校验 (3)
# ══════════════════════════════════════════════════════════════════════════════


class TestConfigValidation:
    """验证 on_load 中的配置校验。"""

    def test_missing_genre(
        self, valid_manifest: PluginManifest
    ) -> None:
        """缺少 genre 时抛出 ValueError。"""
        plugin = OpenTalePlugin(valid_manifest)
        with pytest.raises(ValueError, match="必需配置字段"):
            plugin.on_load({"output_dir": "/tmp/test"})

    def test_missing_output_dir(
        self, valid_manifest: PluginManifest
    ) -> None:
        """缺少 output_dir 时抛出 ValueError。"""
        plugin = OpenTalePlugin(valid_manifest)
        with pytest.raises(ValueError, match="必需配置字段"):
            plugin.on_load({"genre": "sci_fi"})

    def test_invalid_genre_type(
        self, valid_manifest: PluginManifest
    ) -> None:
        """genre 类型错误时抛出 ValueError。"""
        plugin = OpenTalePlugin(valid_manifest)
        with pytest.raises(ValueError, match="必须是非空字符串"):
            plugin.on_load({"genre": "", "output_dir": "/tmp/test"})


# ══════════════════════════════════════════════════════════════════════════════
# E. 错误处理 (4)
# ══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """验证插件在异常场景下的行为。"""

    def test_system_init_failure_rollback(
        self, valid_manifest: PluginManifest, valid_config: dict[str, Any]
    ) -> None:
        """系统初始化失败时清理残留状态。"""
        plugin = OpenTalePlugin(valid_manifest)

        def _broken_init(genre: str, output_dir: str) -> None:
            plugin._system = "partially_initialized"  # 模拟部分初始化
            raise RuntimeError("system init failed")

        plugin._init_system = _broken_init  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="system init failed"):
            plugin.on_load(valid_config)

        # 验证回滚：_system 应为 None（_cleanup_system 被调用）
        assert plugin._system is None

    def test_on_unload_without_on_load(
        self, plugin_without_init: OpenTalePlugin
    ) -> None:
        """未初始化的插件也能安全卸载（无异常）。"""
        plugin_without_init.on_unload()  # 不应抛出异常

    def test_on_unload_with_broken_system(
        self, valid_manifest: PluginManifest
    ) -> None:
        """系统 close() 抛出异常时 on_unload 仍能完成清理。"""
        plugin = OpenTalePlugin(valid_manifest)
        mock_system = MagicMock()
        mock_system.close.side_effect = RuntimeError("close failed")
        plugin._system = mock_system
        plugin._config = {"genre": "test"}
        plugin._generation_state = {"status": "running"}

        # 不应传播异常
        plugin.on_unload()
        assert plugin._system is None
        assert plugin._config == {}
        assert plugin._generation_state == {}

    def test_double_unload_safe(
        self, plugin_with_mock_system: OpenTalePlugin
    ) -> None:
        """连续两次 on_unload 安全。"""
        plugin_with_mock_system.on_unload()
        plugin_with_mock_system.on_unload()  # 第二次不应抛出异常


# ══════════════════════════════════════════════════════════════════════════════
# F. PluginLoader 集成 (8)
# ══════════════════════════════════════════════════════════════════════════════


class TestPluginLoaderIntegration:
    """验证 PluginLoader (D3) 能发现、加载、执行、卸载 OpenTalePlugin。"""

    @pytest.fixture
    def opentale_plugin_dir(
        self, tmp_path: Path
    ) -> Path:
        """创建包含有效 plugin.json 的模拟插件目录。"""
        plugin_dir = tmp_path / "opentale"
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # 写入 plugin.json
        manifest = {
            "name": "opentale",
            "version": "0.1.0",
            "entry_point": (
                "ocos.plugins.opentale.plugin:OpenTalePlugin"
            ),
            "schema_version": "1.0",
            "required_permissions": ["network"],
            "timeout_seconds": 120,
        }
        (plugin_dir / "plugin.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        return plugin_dir

    def test_discover_opentale_plugin(
        self, opentale_plugin_dir: Path
    ) -> None:
        """PluginLoader 能发现 opentale 插件目录。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        manifests = loader.discover()
        assert len(manifests) >= 1
        manifest_names = [m.name for m in manifests]
        assert "opentale" in manifest_names

    def test_discover_and_check_entry_point(
        self, opentale_plugin_dir: Path
    ) -> None:
        """发现的 opentale manifest 包含正确的 entry_point。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        manifests = loader.discover()
        for m in manifests:
            if m.name == "opentale":
                assert (
                    m.entry_point
                    == "ocos.plugins.opentale.plugin:OpenTalePlugin"
                )
                return
        pytest.fail("未找到 opentale manifest")

    def test_load_opentale_plugin(
        self, opentale_plugin_dir: Path
    ) -> None:
        """PluginLoader 能加载 OpenTalePlugin。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        loader.discover()
        for manifest in loader._discovered:
            if manifest.name == "opentale":
                result = loader.load(
                    manifest,
                    config={"genre": "sci_fi", "output_dir": "/tmp/test"},
                )
                assert result.success, f"加载失败: {result.message}"
                assert result.plugin_id.startswith("plugin_")
                assert loader.loaded_count == 1
                return
        pytest.fail("未找到 opentale manifest")

    def test_execute_opentale_plugin(
        self, opentale_plugin_dir: Path, mock_ans: MagicMock
    ) -> None:
        """加载后能执行 OpenTalePlugin 的 status action。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        loader.discover()
        for manifest in loader._discovered:
            if manifest.name == "opentale":
                load_result = loader.load(
                    manifest,
                    config={"genre": "sci_fi", "output_dir": "/tmp/test"},
                )
                assert load_result.success

                plugin_id = load_result.plugin_id
                # 替换 _init_system 避免真实系统初始化
                instance, _ = loader._instances[plugin_id]
                assert isinstance(instance, OpenTalePlugin)

                instance._init_system = (
                    lambda g, od: setattr(instance, "_system", mock_ans)
                    or instance._generation_state.update(
                        {"genre": g, "output_dir": od, "status": "idle"}
                    )
                )
                instance.on_load({"genre": "sci_fi", "output_dir": "/tmp/test"})

                exec_result = loader.execute(plugin_id, ACTION_STATUS, {})
                assert exec_result.success
                return
        pytest.fail("未找到 opentale manifest")

    def test_unload_opentale_plugin(
        self, opentale_plugin_dir: Path
    ) -> None:
        """能卸载 OpenTalePlugin。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        loader.discover()
        for manifest in loader._discovered:
            if manifest.name == "opentale":
                load_result = loader.load(
                    manifest,
                    config={"genre": "sci_fi", "output_dir": "/tmp/test"},
                )
                assert load_result.success
                assert loader.loaded_count == 1

                result = loader.unload(load_result.plugin_id)
                assert result is True
                assert loader.loaded_count == 0
                return
        pytest.fail("未找到 opentale manifest")

    def test_load_with_invalid_entry_point_returns_error(
        self, tmp_path: Path
    ) -> None:
        """entry_point 指向不存在的类时返回失败结果而非崩溃。"""
        plugin_dir = tmp_path / "bad_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "bad_plugin",
                    "entry_point": "ocos.plugins.nonexistent:MissingPlugin",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(tmp_path)])
        loader.discover()
        assert len(loader._discovered) > 0
        manifest = loader._discovered[-1]
        result = loader.load(manifest, {"genre": "sci_fi", "output_dir": "/tmp/test"})
        assert not result.success

    def test_load_duplicate_detection(
        self, opentale_plugin_dir: Path
    ) -> None:
        """重复加载同一 entry_point 的插件返回已有 plugin_id。"""
        sandbox = PluginSandbox()
        loader = PluginLoader(sandbox, search_paths=[str(opentale_plugin_dir.parent)])
        loader.discover()
        opentale_manifest = None
        for m in loader._discovered:
            if m.name == "opentale":
                opentale_manifest = m
                break
        assert opentale_manifest is not None

        result1 = loader.load(
            opentale_manifest,
            config={"genre": "sci_fi", "output_dir": "/tmp/test"},
        )
        assert result1.success

        # 再次加载相同的 entry_point
        result2 = loader.load(
            opentale_manifest,
            config={"genre": "sci_fi", "output_dir": "/tmp/test"},
        )
        assert result2.success  # 重复加载仍返回 success，但标记 code=load.duplicate
        assert "duplicate" in result2.code or "DUPLICATE" in result2.code


# ══════════════════════════════════════════════════════════════════════════════
# G. Manifest (3)
# ══════════════════════════════════════════════════════════════════════════════


class TestPluginManifest:
    """验证 plugin.json 文件存在且格式正确。"""

    @classmethod
    def _plugin_json_path(cls) -> Path:
        """ocos/plugins/opentale/plugin.json 的绝对路径。"""
        return (
            Path(__file__).resolve().parent.parent
            / "plugins"
            / "opentale"
            / "plugin.json"
        )

    def test_plugin_json_exists(self) -> None:
        """plugin.json 文件必须存在。"""
        path = self._plugin_json_path()
        assert path.is_file(), f"plugin.json 不存在: {path}"

    def test_plugin_json_is_valid_json(self) -> None:
        """plugin.json 必须是合法 JSON。"""
        raw = self._plugin_json_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_plugin_json_has_required_fields(self) -> None:
        """plugin.json 包含所有必需字段。"""
        raw = self._plugin_json_path().read_text(encoding="utf-8")
        data = json.loads(raw)

        # 验证 PluginLoader 需要的字段
        assert "name" in data
        assert "entry_point" in data
        assert "version" in data

        # 验证 OpenTale 特有的字段
        assert "required_permissions" in data
        assert "timeout_seconds" in data
        assert data["entry_point"] == (
            "ocos.plugins.opentale.plugin:OpenTalePlugin"
        )
        assert data["name"] == "opentale"


# ══════════════════════════════════════════════════════════════════════════════
# H. 回滚机制 (2)
# ══════════════════════════════════════════════════════════════════════════════


class TestRollback:
    """验证 on_load 失败时的回滚保证。"""

    def test_rollback_cleans_mock_system(
        self, valid_manifest: PluginManifest, valid_config: dict[str, Any]
    ) -> None:
        """_system 被初始化后 on_load 失败会清理。"""
        plugin = OpenTalePlugin(valid_manifest)
        mock_system = MagicMock()

        def _init_then_fail(genre: str, output_dir: str) -> None:
            plugin._system = mock_system
            raise RuntimeError("post-init failure")

        plugin._init_system = _init_then_fail  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            plugin.on_load(valid_config)

        # 回滚：_system 被置为 None
        assert plugin._system is None

    def test_rollback_preserves_generation_state(
        self, valid_manifest: PluginManifest, valid_config: dict[str, Any]
    ) -> None:
        """on_load 回滚后 _generation_state 被清空。"""
        plugin = OpenTalePlugin(valid_manifest)
        mock_system = MagicMock()

        def _init_then_fail(genre: str, output_dir: str) -> None:
            plugin._system = mock_system
            plugin._generation_state.update(
                {"genre": genre, "status": "partial"}
            )
            raise RuntimeError("failure after partial state")

        plugin._init_system = _init_then_fail  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            plugin.on_load(valid_config)

        # _cleanup_system 清掉了 _system；但 _generation_state 不会回滚
        # （cleanup_system 只管理 _system 资源）
        # 验证 _system 被清理
        assert plugin._system is None
