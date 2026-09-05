"""S1.4: 插件沙箱静态门 + import hook 安装回归（白皮书 P1-8）。

- 高危 import（os/subprocess/socket 等）插件 → 加载被 AST 静态门拒绝
- 良性插件 → 正常加载执行
- execute() 执行期间 sys.meta_path 必须装有 _ImportBlocker（hook 真实生效）
"""

from __future__ import annotations

import sys
import textwrap

import pytest

from ocos.platform.plugin_loader import (
    PluginLoader,
    ast_forbidden_import_check,
)
from ocos.platform.plugin_sandbox import PluginSandbox, SandboxConfig
from ocos.platform.plugin_manifest import PluginManifest


def _write_plugin(tmp_path, code: str, name: str = "plug_a") -> PluginManifest:
    pkg = f"s14pkg_{name}"  # 每个插件独立包名，避免 sys.modules 缓存串扰
    mod_dir = tmp_path / pkg
    mod_dir.mkdir(exist_ok=True)
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))
    (mod_dir / f"{name}.py").write_text(
        textwrap.dedent(code), encoding="utf-8")
    (mod_dir / "__init__.py").touch()
    manifest = PluginManifest(
        name=name, version="1.0.0",
        entry_point=f"{pkg}.{name}:Plugin",
        required_permissions=[], timeout_seconds=10)
    return manifest


PLUGIN_TEMPLATE = '''
from ocos.platform.plugin_base import PluginBase

{extra_imports}

class Plugin(PluginBase):
    def manifest(self):
        return {{"name": "{name}"}}

    def on_load(self, config=None):
        return True

    def execute(self, action: str, params=None):
        return {{"ok": True}}

    def on_unload(self):
        return True
'''


class TestAstStaticGate:
    def test_malicious_import_os_rejected(self):
        v = ast_forbidden_import_check("import os\nos.system('x')")
        assert any("IMPORT: os" in x for x in v)

    def test_from_import_rejected(self):
        v = ast_forbidden_import_check("from subprocess import run")
        assert any("FROM_IMPORT: subprocess" in x for x in v)

    def test_dynamic_import_rejected(self):
        v = ast_forbidden_import_check('m = __import__("socket")')
        assert any("DYNAMIC_IMPORT: socket" in x for x in v)

    def test_benign_import_passes(self):
        assert ast_forbidden_import_check(
            "import json\nimport re\nx = json.dumps({})") == []


class TestLoaderGate:
    def test_malicious_plugin_load_rejected(self, tmp_path):
        manifest = _write_plugin(
            tmp_path, PLUGIN_TEMPLATE.format(
                name="evil", extra_imports="import os"),
            name="evil")
        loader = PluginLoader(sandbox=PluginSandbox(SandboxConfig()))
        result = loader.load(manifest)
        assert result.success is False
        assert "import" in result.message.lower()

    def test_benign_plugin_load_ok(self, tmp_path):
        manifest = _write_plugin(
            tmp_path, PLUGIN_TEMPLATE.format(
                name="good", extra_imports="import json"),
            name="good")
        loader = PluginLoader(sandbox=PluginSandbox(SandboxConfig()))
        result = loader.load(manifest)
        assert result.success is True, result.message
        pid = result.plugin_id
        sandbox_result = loader.execute(pid, "run")
        assert sandbox_result.success is True

    def test_import_hook_installed_during_execute(self, tmp_path):
        """execute() 期间 sys.meta_path 必须装有 _ImportBlocker。"""
        from ocos.platform.plugin_sandbox import _ImportBlocker

        manifest = _write_plugin(
            tmp_path, PLUGIN_TEMPLATE.format(
                name="hooked", extra_imports="import json"),
            name="hooked")
        loader = PluginLoader(sandbox=PluginSandbox(SandboxConfig()))
        result = loader.load(manifest)
        assert result.success is True
        sandbox = loader._sandbox
        slot = sandbox._plugins[result.plugin_id]
        assert slot.blocker not in sys.meta_path

        observed: list[bool] = []

        original_execute = sandbox._do_execute

        def _spy(slot_, action, params):
            observed.append(
                any(isinstance(b, _ImportBlocker) for b in sys.meta_path))
            return original_execute(slot_, action, params)

        sandbox._do_execute = staticmethod(_spy)
        sandbox.execute(result.plugin_id, "run")
        assert observed == [True], "执行期 meta_path 中应存在 _ImportBlocker"
        assert slot.blocker not in sys.meta_path  # 执行后已移除
