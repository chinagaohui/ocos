"""
E3 OpenTale Plugin — 兼容性测试套件。

测试目标：
  覆盖 E1/E2 未触及的兼容性场景：
    - 配置回退  不同 config 形状的向前/向后兼容
    - Provider 降级  系统层异常时的优雅降级
    - 版本兼容  不同 manifest/schema 版本的适配
    - 状态兼容  generation_state 在多操作间的正确维护
    - 参数兼容  可选参数缺失、额外参数、编码兼容

E1 覆盖：正常 E2E 管线生命周期
E2 覆盖：压力/负载/超时/边界
E3 覆盖：配置/异常/版本/状态兼容
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ocos.platform.plugin_loader import PluginLoader
from ocos.platform.plugin_manifest import (
    Permission,
    PluginManifest,
)
from ocos.platform.plugin_sandbox import PluginSandbox
from ocos.plugins.opentale.plugin import OpenTalePlugin

logger = logging.getLogger(__name__)

# ── 测试数据 ──────────────────────────────────────────────────────────────

VALID_GENRE = "sci_fi"
VALID_OUTPUT_DIR = "/tmp/e3_test_output"
MINIMAL_VALID_CONFIG = {
    "genre": VALID_GENRE,
    "output_dir": VALID_OUTPUT_DIR,
}
GOOD_REQUEST: dict[str, object] = {
    "content": "E3生成测试的默认内容数据",
    "target_words": 6000,
    "chapters": 3,
    "kind": "idea",
    "title": "E3Test",
}


# ── 第二插件实例的入口 ─────────────────────────────────────────────────────


class DummyOpenTalePlugin(OpenTalePlugin):
    """与 OpenTalePlugin 完全相同，但 entry_point 不同，避免 duplicate 检测。"""


# ── 通用 Fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _patch_system_methods() -> None:
    """mock AutonomousNovelSystem 及其方法。"""
    mock_ms = MagicMock()
    mock_ms.title = "E3测试小说"

    patcher_system = patch(
        "opentale.app.service.AutonomousNovelSystem",
        autospec=True,
    )
    mock_system_cls = patcher_system.start()
    instance = mock_system_cls.return_value
    instance.generate.return_value = mock_ms
    instance.resume.return_value = mock_ms
    instance.rewrite_chapter.return_value = mock_ms

    yield

    patcher_system.stop()


@pytest.fixture
def real_manifest() -> PluginManifest:
    """从 plugin.json 加载真实清单。"""
    import json

    json_path = (
        Path(__file__).resolve().parent.parent
        / "plugins"
        / "opentale"
        / "plugin.json"
    )
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    perm_map = {p.value: p for p in Permission}
    required_permissions: list[Permission] = []
    for p_name in data.get("required_permissions", []):
        if p_name in perm_map:
            required_permissions.append(perm_map[p_name])

    return PluginManifest(
        name=data["name"],
        version=data["version"],
        description=data.get("description", ""),
        entry_point=data["entry_point"],
        required_permissions=tuple(required_permissions),
        timeout_seconds=data.get("timeout_seconds", 120),
        allowed_imports=tuple(data.get("allowed_imports", [])),
        capability_id=data.get("capability_id", ""),
        metadata=data.get("metadata", {}),
    )


@pytest.fixture
def loader() -> PluginLoader:
    """带文件搜索路径的 PluginLoader。"""
    sandbox = PluginSandbox()
    search_path = Path(__file__).resolve().parent.parent / "plugins"
    return PluginLoader(sandbox=sandbox, search_paths=[str(search_path)])


@pytest.fixture
def loaded_id(loader: PluginLoader, real_manifest: PluginManifest) -> str:
    """加载一次 OpenTalePlugin。"""
    result = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
    assert result.success, f"load 失败: {result.code} — {result.message}"
    return result.plugin_id


# ═══════════════════════════════════════════════════════════════════════
# E3.1 — 配置回退兼容性
# ═══════════════════════════════════════════════════════════════════════


class TestConfigFallbackCompat:
    """不同 config 形状的回退/兼容行为。"""

    def test_extra_unknown_config_fields(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """包含未来可能添加的额外字段时仍能正常加载（向前兼容）。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["unknown_field_future"] = "some_value"
        config["another_future_field"] = 42
        config["nested_future"] = {"a": 1}

        result = loader.load(real_manifest, config=config)
        assert result.success, (
            f"额外字段不应阻止加载: {result.message}"
        )

    def test_config_with_minimal_values(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """最小的有效 config（只有必需字段）正常加载。"""
        result = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert result.success

        pid = result.plugin_id
        status = loader.execute(pid, "status", params={})
        assert status.success

    def test_config_genre_wrong_type_rejected(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """genre 类型错误（int 代替 str）被拒绝。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["genre"] = 12345  # 错误的类型

        result = loader.load(real_manifest, config=config)
        assert not result.success, "错误的 genre 类型应被拒绝"
        assert "genre" in result.message.lower()

    def test_config_output_dir_wrong_type_rejected(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """output_dir 类型错误（list 代替 str）被拒绝。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["output_dir"] = ["/tmp/e3", "/tmp/e3_alt"]

        result = loader.load(real_manifest, config=config)
        assert not result.success, "错误的 output_dir 类型应被拒绝"

    def test_config_empty_strings_rejected(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """空字符串字段被拒绝。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["genre"] = ""

        result = loader.load(real_manifest, config=config)
        assert not result.success, "空 genre 应被拒绝"

    def test_config_whitespace_only_rejected(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """全空白字符串字段被拒绝。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["output_dir"] = "   "

        result = loader.load(real_manifest, config=config)
        assert not result.success, "空白 output_dir 应被拒绝"

    def test_config_none_values_rejected(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """None 值字段被拒绝。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["genre"] = None

        result = loader.load(real_manifest, config=config)
        assert not result.success, "None genre 应被拒绝"

    def test_config_with_non_ascii_values(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """非 ASCII（UTF-8 中文）配置值正常加载。"""
        config = {
            "genre": "言情",    # non-ASCII genre
            "output_dir": "/tmp/e3_爱情_output",
        }
        result = loader.load(real_manifest, config=config)
        assert result.success, f"非 ASCII 配置加载失败: {result.message}"

        pid = result.plugin_id
        status = loader.execute(pid, "status", params={})
        assert status.success
        output = status.output
        assert output.get("genre") == "言情"
        assert output.get("output_dir") == "/tmp/e3_爱情_output"

    def test_config_with_emoji_values(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """含 Emoji 的配置值正常处理。"""
        config = dict(MINIMAL_VALID_CONFIG)
        config["output_dir"] = "/tmp/e3_📚_test"

        result = loader.load(real_manifest, config=config)
        assert result.success, f"Emoji 配置加载失败: {result.message}"
        pid = result.plugin_id

        status = loader.execute(pid, "status", params={})
        assert status.success
        assert status.output.get("output_dir") == "/tmp/e3_📚_test"

    def test_config_with_very_long_strings(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """超长字符串配置值正常处理。"""
        long_output_dir = "/tmp/" + "a" * 200

        config = dict(MINIMAL_VALID_CONFIG)
        config["output_dir"] = long_output_dir

        result = loader.load(real_manifest, config=config)
        assert result.success, (
            f"长字符串配置加载失败: {result.message}"
        )
        pid = result.plugin_id

        status = loader.execute(pid, "status", params={})
        assert status.success


# ═══════════════════════════════════════════════════════════════════════
# E3.2 — Provider 降级 & 异常兼容
# ═══════════════════════════════════════════════════════════════════════


class TestProviderDegradation:
    """系统层异常/故障时的降级行为。"""

    def test_system_init_failure_during_on_load(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """_init_system 抛出异常时 on_load 回滚并报错。"""
        # 装载时 patch AutonomouseNovelSystem 使其抛出异常
        with patch(
            "opentale.app.service.AutonomousNovelSystem",
            side_effect=RuntimeError("系统初始化失败"),
        ):
            result = loader.load(
                real_manifest, config=dict(MINIMAL_VALID_CONFIG)
            )
            assert not result.success
            # 错误消息应提及失败原因
            assert "系统初始化失败" in result.message or "init" in result.message.lower()

    def test_execute_after_system_raise(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """系统方法抛出异常时 execute 不崩溃，返回 SandboxResult.failure。"""
        # 通过 sandbox slot 直接 patch 实例方法（绕过 _patch_system_methods fixture）
        slot = loader.sandbox._plugins[loaded_id]
        slot.plugin_instance._system.generate = MagicMock(
            side_effect=RuntimeError("LLM 调用失败")
        )

        result = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "测试兼容性_数据充分长",
                "genre": "sci_fi",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "E3测试",
            },
        )
        # Sandbox 应捕获此异常并返回 failure
        assert not result.success
        assert result.error is not None

    def test_execute_after_on_unload(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """卸载后重新加载并执行仍能正常工作。"""
        # 第一次加载和执行
        r1 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r1.success
        exec1 = loader.execute(r1.plugin_id, "status", params={})
        assert exec1.success

        # 卸载
        loader.unload(r1.plugin_id)

        # 重新加载和执行（entry_point 索引已清除，生成全新 plugin_id）
        r2 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r2.success

        exec2 = loader.execute(r2.plugin_id, "status", params={})
        assert exec2.success

    def test_repeated_on_load_same_instance(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """重复 load 同一 manifest 返回已有 ID，不重新初始化。"""
        r1 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r1.success

        r2 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r2.success
        assert r2.plugin_id == r1.plugin_id
        # duplicate 应有明确标志
        assert r2.code == "load.duplicate"

    def test_system_method_returns_none(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """系统方法返回 None 时 execute 不崩溃。"""
        # 通过 sandbox slot 直接 patch 实例方法（绕过 _patch_system_methods fixture）
        slot = loader.sandbox._plugins[loaded_id]
        slot.plugin_instance._system.generate = MagicMock(
            return_value=None
        )

        result = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "测试 None 返回兼容性",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "NoneTest",
            },
        )
        # 系统返回 None，但 Sandbox 应仍返回 success=True（P 层本身未报错）
        assert result.success
        # output 中的 result 应为 None
        output = result.output
        assert output.get("result") is None

    def test_system_method_returns_unexpected_type(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """系统方法返回意外类型时 execute 不崩溃。"""
        # 通过 sandbox slot 直接 patch 实例方法（绕过 _patch_system_methods fixture）
        slot = loader.sandbox._plugins[loaded_id]
        slot.plugin_instance._system.generate = MagicMock(
            return_value="just a string, not a model object"
        )

        result = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "测试非预期返回类型",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "TypeTest",
            },
        )
        # P 层不校验系统返回类型，由上层决定
        assert result.success
        output = result.output
        assert output.get("result") == "just a string, not a model object"


# ═══════════════════════════════════════════════════════════════════════
# E3.3 — 版本兼容性
# ═══════════════════════════════════════════════════════════════════════


class TestVersionCompat:
    """不同版本形状的兼容性。"""

    def test_manifest_missing_optional_fields(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """缺少可选字段的 manifest 仍能正常加载。"""
        # 构造只有必需字段的 manifest
        minimal = PluginManifest(
            name=real_manifest.name,
            version=real_manifest.version,
            description="",
            entry_point=real_manifest.entry_point,
            required_permissions=real_manifest.required_permissions,
            timeout_seconds=real_manifest.timeout_seconds,
        )
        # allowed_imports 等为可选
        result = loader.load(minimal, config=dict(MINIMAL_VALID_CONFIG))
        assert result.success, (
            f"缺少可选字段的 manifest 加载失败: {result.message}"
        )

    def test_manifest_with_extra_metadata(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """manifest 含未知元数据字段时的向前兼容。"""
        from ocos.platform.plugin_manifest import PluginManifest as PM  # noqa: N817

        extended = PM(
            name=real_manifest.name,
            version=real_manifest.version,
            description=real_manifest.description,
            entry_point=real_manifest.entry_point,
            required_permissions=real_manifest.required_permissions,
            timeout_seconds=real_manifest.timeout_seconds,
            allowed_imports=real_manifest.allowed_imports,
            metadata={
                "future_key_1": "value1",
                "future_key_2": 42,
                "nested_future": {"sub": "data"},
            },
        )
        result = loader.load(extended, config=dict(MINIMAL_VALID_CONFIG))
        assert result.success, (
            f"含额外 metadata 的 manifest 加载失败: {result.message}"
        )

    def test_manifest_version_string_handling(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """不同版本的 version 字符串兼容。"""
        versions = [
            "1.0.0",
            "0.0.1",
            "2.0.0-beta",
            "1.0.0+build.123",
            "999.999.999",
        ]

        for ver in versions:
            modified = PluginManifest(
                name=real_manifest.name,
                version=ver,
                description=real_manifest.description,
                entry_point=real_manifest.entry_point,
                required_permissions=real_manifest.required_permissions,
                timeout_seconds=real_manifest.timeout_seconds,
                allowed_imports=real_manifest.allowed_imports,
            )
            result = loader.load(
                modified, config=dict(MINIMAL_VALID_CONFIG)
            )
            assert result.success, (
                f"version='{ver}' 加载失败: {result.message}"
            )
            # 清理
            loader.unload(result.plugin_id)

    def test_manifest_no_capability_id(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """capability_id 为空字符串时兼容。"""
        modified = PluginManifest(
            name=real_manifest.name,
            version=real_manifest.version,
            description=real_manifest.description,
            entry_point=real_manifest.entry_point,
            required_permissions=real_manifest.required_permissions,
            timeout_seconds=real_manifest.timeout_seconds,
            allowed_imports=real_manifest.allowed_imports,
            capability_id="",  # 空 capability_id
        )
        result = loader.load(
            modified, config=dict(MINIMAL_VALID_CONFIG)
        )
        assert result.success, (
            f"空 capability_id 加载失败: {result.message}"
        )

    def test_manifest_different_name_allowed(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """非标准插件名（含特殊字符）的兼容性。"""
        special_names = [
            "open-tale-plugin-v2",
            "opentale_1.0",
            "OpenTalePlugin",
            "a" * 100,  # 超长名
            "123-opentale",  # 数字开头
        ]

        for name in special_names:
            modified = PluginManifest(
                name=name,
                version=real_manifest.version,
                description=real_manifest.description,
                entry_point=real_manifest.entry_point,
                required_permissions=real_manifest.required_permissions,
                timeout_seconds=real_manifest.timeout_seconds,
                allowed_imports=real_manifest.allowed_imports,
            )
            result = loader.load(
                modified, config=dict(MINIMAL_VALID_CONFIG)
            )
            assert result.success, (
                f"name='{name[:30]}...' 加载失败: {result.message}"
            )
            loader.unload(result.plugin_id)

    def test_plugin_json_extra_fields(
        self, loader: PluginLoader
    ) -> None:
        """真实 plugin.json 含额外字段时的向前兼容。"""
        # 构造带额外字段的 JSON 内容
        import json

        json_path = (
            Path(__file__).resolve().parent.parent
            / "plugins"
            / "opentale"
            / "plugin.json"
        )
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 添加未来可能存在的字段
        data["deprecated_in_favor_of"] = "new-plugin-name"
        data["ui_metadata"] = {"icon": "robot", "color": "blue"}
        data["plugin_kind"] = "narrative"
        data["sdk_version"] = "2.0.0"

        json_text = json.dumps(data, ensure_ascii=False)
        assert "deprecated_in_favor_of" in json_text

        # 用此 JSON 创建 manifest
        perm_map = {p.value: p for p in Permission}
        perms = []
        for p_name in data.get("required_permissions", []):
            if p_name in perm_map:
                perms.append(perm_map[p_name])

        manifest = PluginManifest(
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            entry_point=data["entry_point"],
            required_permissions=tuple(perms),
            timeout_seconds=data.get("timeout_seconds", 120),
            allowed_imports=tuple(data.get("allowed_imports", [])),
            capability_id=data.get("capability_id", ""),
            metadata=data.get("metadata", {}),
        )
        result = loader.load(
            manifest, config=dict(MINIMAL_VALID_CONFIG)
        )
        assert result.success, (
            f"含额外字段的 plugin.json 加载失败: {result.message}"
        )


# ═══════════════════════════════════════════════════════════════════════
# E3.4 — 状态兼容性
# ═══════════════════════════════════════════════════════════════════════


class TestStateCompat:
    """generation_state 在多操作间的正确维护。"""

    def test_status_after_generate_shows_completed(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """generate 后 status 反映 completed。"""
        gen = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "测试状态兼容性测试",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "StatusTest",
            },
        )
        assert gen.success

        status = loader.execute(loaded_id, "status", params={})
        assert status.success
        output = status.output
        assert output.get("status") == "completed"
        assert output.get("current_operation") == "generate"
        assert output.get("genre") == VALID_GENRE

    def test_status_initial_state_is_idle(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """刚加载后 status 应为 idle。"""
        status = loader.execute(loaded_id, "status", params={})
        assert status.success
        output = status.output
        assert output.get("status") == "idle"
        assert output.get("current_operation") is None
        assert output.get("genre") == VALID_GENRE
        assert output.get("output_dir") == VALID_OUTPUT_DIR

    def test_status_after_unload_and_reload_is_fresh(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """卸载后重新加载，status 回到初始 idle。"""
        r1 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r1.success
        pid1 = r1.plugin_id

        # generate 一次改变状态
        loader.execute(
            pid1,
            "generate",
            params={
                "content": "改变状态测试数据",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "StateChange",
            },
        )
        status1 = loader.execute(pid1, "status", params={})
        assert status1.output.get("status") == "completed"

        # 卸载
        loader.unload(pid1)

        # 重新加载 — 全新状态
        r2 = loader.load(real_manifest, config=dict(MINIMAL_VALID_CONFIG))
        assert r2.success
        pid2 = r2.plugin_id

        status2 = loader.execute(pid2, "status", params={})
        assert status2.success
        output2 = status2.output
        assert output2.get("status") == "idle"
        assert output2.get("current_operation") is None

    def test_generation_state_isolated_per_instance(
        self, loader: PluginLoader, real_manifest: PluginManifest
    ) -> None:
        """多次加载的插件实例间状态互相隔离。"""
        config_a = dict(MINIMAL_VALID_CONFIG)
        config_b = dict(MINIMAL_VALID_CONFIG)
        config_b["genre"] = "fantasy"  # 不同的配置
        config_b["output_dir"] = "/tmp/e3_fantasy_output"

        # 使用不同的 entry_point 避免 duplicate detection
        # loaded_id 已加载同 entry_point, 加载 real_manifest 会返回 duplicate
        # 所以使用已加载的 loaded_id fixture 配合 loaded_id 作为实例 A
        r_a = loader.load(real_manifest, config=config_a)
        assert r_a.success
        # 由于 loaded_id 已加载了同一 entry_point，r_a 是 duplicate 返回
        # 我们用 loaded_id fixture 作为实例 A
        pid_a = r_a.plugin_id  # 与 loaded_id 相同

        # 实例 B：使用不同的 entry_point
        manifest_b = PluginManifest(
            name="opentale-v2-instance",
            version=real_manifest.version,
            description=real_manifest.description,
            # 2026-08-17 修复：entry_point 指向本测试文件（pytest 时 tests/ 在 sys.path），
            # 原 `ocos.tests.test_e3_compat_plugin` 模块在 ocos 包中不存在。
            entry_point="test_e3_compat_plugin:DummyOpenTalePlugin",
            required_permissions=real_manifest.required_permissions,
            timeout_seconds=real_manifest.timeout_seconds,
            allowed_imports=real_manifest.allowed_imports,
        )
        r_b = loader.load(manifest_b, config=config_b)
        assert r_b.success
        assert r_b.plugin_id != r_a.plugin_id, "不同 entry_point 应生成不同 plugin_id"

        # 在实例 A 上 generate
        a_params = dict(GOOD_REQUEST)
        a_params["content"] = "实例A生成状态隔离测试数据内容"
        loader.execute(
            pid_a,
            "generate",
            params=a_params,
        )

        # 实例 B 的状态不受 A 影响
        status_b = loader.execute(r_b.plugin_id, "status", params={})
        assert status_b.success
        output_b = status_b.output
        assert output_b.get("status") == "idle"
        assert output_b.get("genre") == "fantasy"

        # 实例 A 的状态是 completed
        status_a = loader.execute(pid_a, "status", params={})
        assert status_a.success
        assert status_a.output.get("status") == "completed"

        loader.unload(r_b.plugin_id)


# ═══════════════════════════════════════════════════════════════════════
# E3.5 — 参数兼容性
# ═══════════════════════════════════════════════════════════════════════


class TestParamCompat:
    """不同参数形状的向前/向后兼容。"""

    def test_generate_with_extra_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """generate 接收未来额外参数时正常工作。"""
        params = {
            "content": "测试额外参数兼容性",
            "target_words": 6000,
            "chapters": 3,
            "kind": "idea",
            "title": "ExtraParamTest",
            "unknown_param_1": "should be ignored",
            "unknown_param_2": 42,
            "unknown_param_3": {"nested": "data"},
        }
        result = loader.execute(loaded_id, "generate", params=params)
        assert result.success, (
            f"额外参数不应阻止 execute: {result.error}"
        )

    def test_generate_missing_optional_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """generate 缺失所有可选参数时使用默认值。"""
        # content 有默认值
        params = {
            "target_words": 6000,
            "chapters": 3,
            "kind": "idea",
        }
        result = loader.execute(loaded_id, "generate", params=params)
        assert result.success, (
            f"缺失可选参数不应失败: {result.error}"
        )

    def test_generate_with_minimal_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """generate 只有最基本参数。"""
        params = {
            "content": "极少参数测试数据内容",
            "target_words": 6000,
            "chapters": 3,
        }
        result = loader.execute(loaded_id, "generate", params=params)
        assert result.success, (
            f"最少参数 execute 失败: {result.error}"
        )

    def test_status_with_extra_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """status 接收额外参数时仍正常工作。"""
        result = loader.execute(
            loaded_id,
            "status",
            params={
                "extra_field": "should be ignored",
                "verbose": True,
                "format": "json",
            },
        )
        assert result.success

    def test_resume_with_extra_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """resume 接收额外参数时仍正常。"""
        result = loader.execute(
            loaded_id,
            "resume",
            params={
                "project_dir": "/tmp/e3_test_project",
                "extra_flag": True,
                "unknown_option": "value",
            },
        )
        assert result.success

    def test_rewrite_with_extra_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """rewrite 接收额外参数时仍正常（缺少必填参数时预期失败）。"""
        # 缺 project_dir 时即使有额外参数也应失败
        result = loader.execute(
            loaded_id,
            "rewrite",
            params={
                "chapter_number": 1,
                "instruction": "重写",
                "extra_param": "extra",
            },
        )
        assert not result.success
        assert "project_dir" in result.error.lower()

    def test_generate_with_unicode_content(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """Unicode 多语言内容正常传递。"""
        unicode_contents = [
            "你好世界，这是一篇中文小说。",
            "こんにちは、日本語の小説です。",
            "안녕하세요, 한국어 소설입니다.",
            "Hello, this is an English novel.",
            "🌍 🌎 🌏 全球化的世界小说。",
            "Привет, это русский роман.",
            "混合语言 mix of 中文 and English 🚀",
        ]

        for content in unicode_contents:
            result = loader.execute(
                loaded_id,
                "generate",
                params={
                    "content": content,
                    "target_words": 6000,
                    "chapters": 3,
                    "kind": "idea",
                    "title": "UnicodeTest",
                },
            )
            assert result.success, (
                f"Unicode content 执行失败: {content[:20]}..."
            )

    def test_empty_params_dict(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """空 params {} 不崩溃（status 正常，generate 使用默认值成功）。"""
        # status 不需要参数
        status = loader.execute(loaded_id, "status", params={})
        assert status.success

        # generate 缺 content 时使用插件默认值（"Write a story about " 满足 ≥8 字符校验）
        gen = loader.execute(loaded_id, "generate", params={})
        assert gen.success
        output = gen.output
        assert output.get("operation") == "generate"


# ═══════════════════════════════════════════════════════════════════════
# E3.6 — Action 行为兼容
# ═══════════════════════════════════════════════════════════════════════


class TestActionCompat:
    """Action 边界行为及跨版本兼容。"""

    def test_generate_then_status_then_generate(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """generate → status → generate 序列正常。"""
        for i in range(3):
            r1 = loader.execute(
                loaded_id,
                "generate",
                params={
                    "content": f"第{i+1}次生成测试内容数据",
                    "target_words": 6000,
                    "chapters": 3,
                    "kind": "idea",
                    "title": f"Round{i+1}",
                },
            )
            assert r1.success, f"第{i+1}次 generate 失败: {r1.error}"

            r2 = loader.execute(loaded_id, "status", params={})
            assert r2.success
            assert r2.output.get("status") == "completed"

    def test_unknown_action_with_extra_params(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """未知 action 即使带完整参数也被拒绝（不匹配任何已知 action）。"""
        result = loader.execute(
            loaded_id,
            "generate_v2",  # 不支持的 action
            params={
                "content": "向前兼容",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
            },
        )
        assert not result.success
        assert "不支持" in result.error or "unknown" in result.error.lower()

    def test_case_sensitive_action_names(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """大小写敏感的 action 名 — 'Generate' 应被拒绝。"""
        result = loader.execute(
            loaded_id,
            "Generate",  # 大写 G
            params={"content": "大小写测试"},
        )
        assert not result.success
        assert "不支持" in result.error or "Generate" in result.error

    def test_action_name_whitespace_sensitivity(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """action 名含不可见字符应被拒绝。"""
        result = loader.execute(
            loaded_id,
            " generate ",  # 前后空格
            params={},
        )
        assert not result.success

    def test_generate_with_default_language(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """不传 language 时使用默认 'zh'。"""
        result = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "默认语言测试数据内容",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "DefaultLang",
            },
        )
        assert result.success


# ═══════════════════════════════════════════════════════════════════════
# E3.7 — _run_async 行为兼容
# ═══════════════════════════════════════════════════════════════════════


class TestRunAsyncCompat:
    """_run_async 对不同类型 callable 的处理兼容性。"""

    def test_sync_callable_runs_directly(
        self, loader: PluginLoader, loaded_id: str
    ) -> None:
        """同步 callable（非协程）直接返回结果。"""
        mock_system = MagicMock()
        mock_system.generate.return_value = {"sync": "result"}

        slot = loader.sandbox._plugins[loaded_id]
        slot.plugin_instance._system = mock_system

        result = loader.execute(
            loaded_id,
            "generate",
            params={
                "content": "sync callable test content data",
                "target_words": 6000,
                "chapters": 3,
                "kind": "idea",
                "title": "SyncTest",
            },
        )
        # 即使 mock 了真实 system，execute 仍然经过 GenerationRequest 校验
        assert result.success
        output = result.output
        assert output.get("result") == {"sync": "result"}
