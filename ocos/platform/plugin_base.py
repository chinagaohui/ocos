"""
D3 Plugin Base — 插件接口契约。

所有插件必须继承 PluginBase 并实现三个生命周期方法：
  - on_load(config)    → 插件初始化，接收 Sandbox 传入的配置
  - execute(action, params) → 插件核心逻辑
  - on_unload()        → 插件清理，释放资源

架构定位：
  PluginBase 是 Plugin Framework 的接口契约。
  Plugin Loader (D3) 在 load() 时校验插件类是否继承 PluginBase，
  确保所有插件满足最小执行接口要求。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ocos.platform.plugin_manifest import PluginManifest


class PluginBase(ABC):
    """所有插件必须继承的基类。

    子类必须：
    1. 实现 on_load / execute / on_unload 三个抽象方法
    2. 在 __init__ 中接受 manifest: PluginManifest 参数
    3. 提供 manifest 属性返回 PluginManifest 实例

    用法示例：
        class MyPlugin(PluginBase):
            def __init__(self, manifest: PluginManifest) -> None:
                super().__init__(manifest)
                self._state: dict = {}

            def on_load(self, config: dict[str, Any]) -> None:
                self._state.update(config)

            def execute(self, action: str, params: dict[str, Any]) -> Any:
                return {"action": action, "result": "ok"}

            def on_unload(self) -> None:
                self._state.clear()
    """

    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest

    @property
    def manifest(self) -> PluginManifest:
        """返回插件的 Manifest 信息。"""
        return self._manifest

    @abstractmethod
    def on_load(self, config: dict[str, Any]) -> None:
        """插件初始化回调。

        在 PluginLoader.load() 过程中被调用，用于插件设置自身状态。
        config 来源于 SandboxConfig 中与插件相关的配置项。
        """
        ...

    @abstractmethod
    def execute(self, action: str, params: dict[str, Any]) -> Any:
        """插件核心执行逻辑。

        Args:
            action: 动作名称（由插件定义，如 'run', 'generate', 'analyze'）
            params: 动作参数字典

        Returns:
            任意可序列化的执行结果（被封装进 SandboxResult.output）

        Raises:
            异常会被 Sandbox 捕获并转换为 SandboxResult(error=..., traceback=...)
        """
        ...

    @abstractmethod
    def on_unload(self) -> None:
        """插件卸载清理回调。

        在 PluginLoader.unload() 或 sandbox.unload() 后被调用。
        插件应在此方法中释放文件句柄、网络连接等资源。
        """
        ...
