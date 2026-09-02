"""Phase AC: EcosystemManager — 生态集成管理器。

整合 IntegrationEngine + AdapterManager + PluginSandbox，
提供统一的生态集成接口：
- 扩展发现与注册
- 适配器管理
- 插件生命周期
- 信任管理
- 能力路由

架构原则：
- AC-ECO-01: 扩展不修改核心认知链
- AC-ECO-02: 所有外部调用必须通过适配器
- AC-ECO-03: 插件必须在沙箱中执行
- AC-ECO-04: 信任度随使用动态调整
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from ocos.logging import get_logger

logger = get_logger(__name__)


class TrustLevel(Enum):
    """信任等级。"""
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    TRUSTED = "trusted"


class ExtensionState(Enum):
    """扩展状态。"""
    PENDING = "pending"
    DISCOVERED = "discovered"
    APPROVED = "approved"
    INTEGRATED = "integrated"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class PluginState(Enum):
    """插件状态。"""
    LOADING = "loading"
    LOADED = "loaded"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ExtensionInfo:
    """扩展信息。"""
    extension_id: str
    name: str
    type: str
    version: str
    state: ExtensionState = ExtensionState.PENDING
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    created_at: float = 0.0
    last_used_at: float = 0.0
    usage_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def is_active(self) -> bool:
        return self.state in (ExtensionState.APPROVED, ExtensionState.INTEGRATED, ExtensionState.ACTIVE)


@dataclass
class PluginInfo:
    """插件信息。"""
    plugin_id: str
    name: str
    version: str
    state: PluginState = PluginState.LOADING
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    entry_point: str = ""
    required_permissions: list[str] = field(default_factory=list)
    loaded_at: float = 0.0
    last_used_at: float = 0.0
    usage_count: int = 0
    error: str = ""

    def __post_init__(self):
        if self.loaded_at == 0.0:
            self.loaded_at = time.time()

    @property
    def is_ready(self) -> bool:
        return self.state == PluginState.LOADED and self.trust_level != TrustLevel.UNKNOWN


class EcosystemManager:
    """生态集成管理器。

    统一管理层：
    1. 扩展注册与发现
    2. 适配器管理
    3. 插件生命周期
    4. 信任管理
    5. 能力路由
    """

    def __init__(
        self,
        max_extensions: int = 50,
        max_plugins: int = 20,
        default_trust_threshold: TrustLevel = TrustLevel.MEDIUM,
    ):
        self._max_extensions = max_extensions
        self._max_plugins = max_plugins
        self._default_trust_threshold = default_trust_threshold
        
        # 扩展管理
        self._extensions: dict[str, ExtensionInfo] = {}
        self._extension_lock = threading.RLock()
        
        # 插件管理
        self._plugins: dict[str, PluginInfo] = {}
        self._plugin_lock = threading.RLock()
        
        # 适配器注册表
        self._adapters: dict[str, Callable] = {}
        self._adapter_lock = threading.RLock()
        
        # 能力路由
        self._capability_map: dict[str, str] = {}
        
        # 统计
        self._stats = {
            "extensions_registered": 0,
            "extensions_active": 0,
            "plugins_loaded": 0,
            "plugins_active": 0,
            "adapters_registered": 0,
            "calls_routed": 0,
            "calls_failed": 0,
        }

    # ── 扩展管理 ────────────────────────────────────────────────

    def register_extension(
        self,
        name: str,
        ext_type: str,
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
    ) -> ExtensionInfo | None:
        """注册新扩展。"""
        with self._extension_lock:
            if len(self._extensions) >= self._max_extensions:
                logger.warning("Max extensions reached (%d)", self._max_extensions)
                return None
            
            extension_id = f"ext:{uuid.uuid4().hex[:8]}"
            
            extension = ExtensionInfo(
                extension_id=extension_id,
                name=name,
                type=ext_type,
                version=version,
                state=ExtensionState.DISCOVERED,
                metadata=metadata or {},
            )
            self._extensions[extension_id] = extension
            self._stats["extensions_registered"] += 1
            
            logger.info("Extension registered: %s (%s v%s)", name, ext_type, version)
            return extension

    def approve_extension(self, extension_id: str) -> bool:
        """批准扩展（提升信任等级）。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if not ext:
                return False
            
            # 检查信任等级
            if ext.trust_level.value not in ("medium", "high", "trusted"):
                logger.warning("Extension %s trust level too low for approval", extension_id)
                return False
            
            ext.state = ExtensionState.APPROVED
            logger.info("Extension approved: %s", extension_id)
            return True

    def integrate_extension(self, extension_id: str) -> bool:
        """集成扩展（连接到 OCOS）。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if not ext:
                return False
            if ext.state != ExtensionState.APPROVED:
                logger.warning("Extension %s not approved", extension_id)
                return False
            
            ext.state = ExtensionState.INTEGRATED
            self._stats["extensions_active"] += 1
            logger.info("Extension integrated: %s", extension_id)
            return True

    def activate_extension(self, extension_id: str) -> bool:
        """激活扩展。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if not ext:
                return False
            if ext.state != ExtensionState.INTEGRATED:
                return False
            
            ext.state = ExtensionState.ACTIVE
            ext.last_used_at = time.time()
            logger.info("Extension activated: %s", extension_id)
            return True

    def revoke_extension(self, extension_id: str) -> bool:
        """撤销扩展。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if not ext:
                return False
            
            if ext.state == ExtensionState.ACTIVE:
                self._stats["extensions_active"] -= 1
            
            ext.state = ExtensionState.REVOKED
            logger.info("Extension revoked: %s", extension_id)
            return True

    def get_extension(self, extension_id: str) -> ExtensionInfo | None:
        """获取扩展信息。"""
        with self._extension_lock:
            return self._extensions.get(extension_id)

    def list_extensions(self, state: ExtensionState | None = None) -> list[ExtensionInfo]:
        """列出扩展。"""
        with self._extension_lock:
            extensions = list(self._extensions.values())
            if state:
                extensions = [e for e in extensions if e.state == state]
            return extensions

    def record_usage(self, extension_id: str) -> None:
        """记录扩展使用情况。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if ext:
                ext.usage_count += 1
                ext.last_used_at = time.time()

    # ── 插件管理 ────────────────────────────────────────────────

    def load_plugin(
        self,
        name: str,
        entry_point: str,
        required_permissions: list[str] | None = None,
        timeout: int = 30,
    ) -> PluginInfo | None:
        """加载插件到沙箱。"""
        with self._plugin_lock:
            if len(self._plugins) >= self._max_plugins:
                logger.warning("Max plugins reached (%d)", self._max_plugins)
                return None
            
            plugin_id = f"plugin:{uuid.uuid4().hex[:8]}"
            
            plugin = PluginInfo(
                plugin_id=plugin_id,
                name=name,
                version="1.0.0",
                state=PluginState.LOADING,
                entry_point=entry_point,
                required_permissions=required_permissions or [],
            )
            self._plugins[plugin_id] = plugin
            self._stats["plugins_loaded"] += 1
            
            # 模拟加载
            try:
                # 实际实现中这里会调用 PluginSandbox.load()
                plugin.state = PluginState.LOADED
                logger.info("Plugin loaded: %s (%s)", name, plugin_id)
                return plugin
            except Exception as e:
                plugin.state = PluginState.FAILED
                plugin.error = str(e)
                logger.error("Plugin load failed: %s - %s", name, e)
                return None

    def start_plugin(self, plugin_id: str) -> bool:
        """启动插件。"""
        with self._plugin_lock:
            plugin = self._plugins.get(plugin_id)
            if not plugin or plugin.state != PluginState.LOADED:
                return False
            
            plugin.state = PluginState.RUNNING
            self._stats["plugins_active"] += 1
            logger.info("Plugin started: %s", plugin_id)
            return True

    def stop_plugin(self, plugin_id: str) -> bool:
        """停止插件。"""
        with self._plugin_lock:
            plugin = self._plugins.get(plugin_id)
            if not plugin or plugin.state != PluginState.RUNNING:
                return False
            
            plugin.state = PluginState.STOPPED
            self._stats["plugins_active"] -= 1
            logger.info("Plugin stopped: %s", plugin_id)
            return True

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件。"""
        with self._plugin_lock:
            plugin = self._plugins.get(plugin_id)
            if not plugin:
                return False
            
            if plugin.state == PluginState.RUNNING:
                self._stats["plugins_active"] -= 1
            
            del self._plugins[plugin_id]
            logger.info("Plugin unloaded: %s", plugin_id)
            return True

    def execute_plugin(self, plugin_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """执行插件动作。"""
        with self._plugin_lock:
            plugin = self._plugins.get(plugin_id)
            if not plugin or plugin.state != PluginState.RUNNING:
                return {"error": "plugin not running"}
            
            # 调用适配器执行
            adapter_key = f"{plugin.name}:{action}"
            adapter = self._adapters.get(adapter_key)
            
            if adapter:
                try:
                    result = adapter(params)
                    plugin.usage_count += 1
                    plugin.last_used_at = time.time()
                    self._stats["calls_routed"] += 1
                    return {"success": True, "output": result}
                except Exception as e:
                    plugin.error = str(e)
                    self._stats["calls_failed"] += 1
                    return {"error": str(e)}
            else:
                return {"error": f"no adapter for {adapter_key}"}

    def get_plugin(self, plugin_id: str) -> PluginInfo | None:
        """获取插件信息。"""
        with self._plugin_lock:
            return self._plugins.get(plugin_id)

    def list_plugins(self, state: PluginState | None = None) -> list[PluginInfo]:
        """列出插件。"""
        with self._plugin_lock:
            plugins = list(self._plugins.values())
            if state:
                plugins = [p for p in plugins if p.state == state]
            return plugins

    # ── 适配器管理 ──────────────────────────────────────────────

    def register_adapter(self, key: str, adapter_fn: Callable) -> bool:
        """注册适配器函数。"""
        with self._adapter_lock:
            self._adapters[key] = adapter_fn
            self._stats["adapters_registered"] += 1
            logger.info("Adapter registered: %s", key)
            return True

    def unregister_adapter(self, key: str) -> bool:
        """注销适配器。"""
        with self._adapter_lock:
            if key in self._adapters:
                del self._adapters[key]
                return True
            return False

    def get_adapter(self, key: str) -> Callable | None:
        """获取适配器。"""
        with self._adapter_lock:
            return self._adapters.get(key)

    def list_adapters(self) -> list[str]:
        """列出所有适配器。"""
        with self._adapter_lock:
            return list(self._adapters.keys())

    # ── 能力路由 ────────────────────────────────────────────────

    def register_capability(self, capability_id: str, extension_id: str) -> bool:
        """注册能力到扩展的映射。"""
        with self._extension_lock:
            ext = self._extensions.get(extension_id)
            if not ext or not ext.is_active:
                return False
        
        with self._adapter_lock:
            self._capability_map[capability_id] = extension_id
            logger.debug("Capability registered: %s -> %s", capability_id, extension_id)
            return True

    def resolve_capability(self, capability_id: str) -> str | None:
        """解析能力到扩展。"""
        with self._adapter_lock:
            return self._capability_map.get(capability_id)

    # ── 信任管理 ────────────────────────────────────────────────

    def update_trust(
        self,
        extension_id: str | None = None,
        plugin_id: str | None = None,
        level: TrustLevel | None = None,
        delta: int = 0,
    ) -> bool:
        """更新信任等级。"""
        changed = False
        
        if extension_id:
            with self._extension_lock:
                ext = self._extensions.get(extension_id)
                if ext:
                    if level:
                        ext.trust_level = level
                    elif delta != 0:
                        # 基于使用次数动态调整
                        if ext.usage_count > 100:
                            ext.trust_level = TrustLevel.TRUSTED
                        elif ext.usage_count > 50:
                            ext.trust_level = TrustLevel.HIGH
                        elif ext.usage_count > 10:
                            ext.trust_level = TrustLevel.MEDIUM
                    changed = True
        
        if plugin_id:
            with self._plugin_lock:
                plugin = self._plugins.get(plugin_id)
                if plugin:
                    if level:
                        plugin.trust_level = level
                    elif delta != 0:
                        if plugin.usage_count > 100:
                            plugin.trust_level = TrustLevel.TRUSTED
                        elif plugin.usage_count > 50:
                            plugin.trust_level = TrustLevel.HIGH
                        elif plugin.usage_count > 10:
                            plugin.trust_level = TrustLevel.MEDIUM
                    changed = True
        
        return changed

    def get_trust_status(self) -> dict[str, Any]:
        """获取信任状态摘要。"""
        with self._extension_lock:
            ext_trust = {}
            for ext in self._extensions.values():
                ext_trust[ext.extension_id] = {
                    "name": ext.name,
                    "trust_level": ext.trust_level.value,
                    "usage_count": ext.usage_count,
                }
        
        with self._plugin_lock:
            plugin_trust = {}
            for plugin in self._plugins.values():
                plugin_trust[plugin.plugin_id] = {
                    "name": plugin.name,
                    "trust_level": plugin.trust_level.value,
                    "usage_count": plugin.usage_count,
                }
        
        return {
            "extensions": ext_trust,
            "plugins": plugin_trust,
        }

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        return {
            **self._stats,
            "extension_count": len(self._extensions),
            "active_extensions": sum(1 for e in self._extensions.values() if e.is_active),
            "plugin_count": len(self._plugins),
            "adapter_count": len(self._adapters),
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "extensions_registered": 0,
            "extensions_active": 0,
            "plugins_loaded": 0,
            "plugins_active": 0,
            "adapters_registered": 0,
            "calls_routed": 0,
            "calls_failed": 0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._extension_lock:
            self._extensions.clear()
        with self._plugin_lock:
            self._plugins.clear()
        with self._adapter_lock:
            self._adapters.clear()
        logger.info("EcosystemManager closed")


__all__ = [
    "EcosystemManager",
    "ExtensionInfo",
    "PluginInfo",
    "TrustLevel",
    "ExtensionState",
    "PluginState",
]
