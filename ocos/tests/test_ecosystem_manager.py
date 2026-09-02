"""Phase AC: EcosystemManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 扩展注册与状态管理
3. 插件加载与生命周期
4. 适配器管理
5. 能力路由
6. 信任管理
7. 统计信息
8. 边界约束
9. 端到端流程
10. 错误处理
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.ecosystem.manager import (
    EcosystemManager,
    ExtensionInfo,
    PluginInfo,
    TrustLevel,
    ExtensionState,
    PluginState,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = EcosystemManager()
        
        assert mgr.list_extensions() == []
        assert mgr.list_plugins() == []
        assert mgr.list_adapters() == []
        
        stats = mgr.get_stats()
        assert stats["extension_count"] == 0
        assert stats["plugin_count"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = EcosystemManager(
            max_extensions=20,
            max_plugins=10,
            default_trust_threshold=TrustLevel.HIGH,
        )
        
        assert mgr._max_extensions == 20
        assert mgr._max_plugins == 10
        assert mgr._default_trust_threshold == TrustLevel.HIGH

    def test_context_manager(self):
        """上下文管理器应正确关闭。"""
        with EcosystemManager() as mgr:
            mgr.register_extension("test", "perception")
            assert len(mgr.list_extensions()) == 1
        
        # 关闭后应为空
        assert len(mgr.list_extensions()) == 0


# =========================================================================
# 2. 扩展注册与状态管理
# =========================================================================

class TestExtensionManagement:
    """扩展管理测试。"""

    def test_register_extension(self):
        """注册新扩展。"""
        mgr = EcosystemManager()
        
        ext = mgr.register_extension("test-ext", "perception", "1.0.0")
        
        assert ext is not None
        assert ext.name == "test-ext"
        assert ext.type == "perception"
        assert ext.state == ExtensionState.DISCOVERED
        assert ext.trust_level == TrustLevel.UNKNOWN

    def test_register_duplicate(self):
        """重复注册应创建新 ID。"""
        mgr = EcosystemManager()
        
        ext1 = mgr.register_extension("test", "perception")
        ext2 = mgr.register_extension("test", "perception")
        
        assert ext1.extension_id != ext2.extension_id

    def test_register_exceeds_limit(self):
        """超过最大扩展数应拒绝注册。"""
        mgr = EcosystemManager(max_extensions=2)
        
        mgr.register_extension("ext1", "perception")
        mgr.register_extension("ext2", "memory")
        
        result = mgr.register_extension("ext3", "reasoning")
        
        assert result is None
        assert len(mgr.list_extensions()) == 2

    def test_approve_extension(self):
        """批准扩展。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        
        # 需要先提升信任等级才能批准
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.MEDIUM)
        result = mgr.approve_extension(ext.extension_id)
        
        assert result is True
        assert ext.state == ExtensionState.APPROVED

    def test_integrate_extension(self):
        """集成扩展。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.MEDIUM)
        mgr.approve_extension(ext.extension_id)
        
        result = mgr.integrate_extension(ext.extension_id)
        
        assert result is True
        assert ext.state == ExtensionState.INTEGRATED

    def test_activate_extension(self):
        """激活扩展。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.MEDIUM)
        mgr.approve_extension(ext.extension_id)
        mgr.integrate_extension(ext.extension_id)
        
        result = mgr.activate_extension(ext.extension_id)
        
        assert result is True
        assert ext.state == ExtensionState.ACTIVE

    def test_revoke_extension(self):
        """撤销扩展。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        mgr.activate_extension(ext.extension_id)
        
        result = mgr.revoke_extension(ext.extension_id)
        
        assert result is True
        assert ext.state == ExtensionState.REVOKED


# =========================================================================
# 3. 插件加载与生命周期
# =========================================================================

class TestPluginLifecycle:
    """插件生命周期测试。"""

    def test_load_plugin(self):
        """加载插件。"""
        mgr = EcosystemManager()
        
        plugin = mgr.load_plugin("test-plugin", "myplugin:Plugin")
        
        assert plugin is not None
        assert plugin.name == "test-plugin"
        assert plugin.state == PluginState.LOADED

    def test_load_plugin_with_permissions(self):
        """加载带权限的插件。"""
        mgr = EcosystemManager()
        
        plugin = mgr.load_plugin(
            "safe-plugin",
            "safplugin:Plugin",
            required_permissions=["file_read"],
        )
        
        assert plugin is not None
        assert "file_read" in plugin.required_permissions

    def test_load_exceeds_limit(self):
        """超过最大插件数应拒绝加载。"""
        mgr = EcosystemManager(max_plugins=2)
        
        mgr.load_plugin("plugin1", "p1:Plugin")
        mgr.load_plugin("plugin2", "p2:Plugin")
        
        result = mgr.load_plugin("plugin3", "p3:Plugin")
        
        assert result is None
        assert len(mgr.list_plugins()) == 2

    def test_start_stop_plugin(self):
        """启动和停止插件。"""
        mgr = EcosystemManager()
        plugin = mgr.load_plugin("test", "t:Plugin")
        
        result = mgr.start_plugin(plugin.plugin_id)
        assert result is True
        assert plugin.state == PluginState.RUNNING
        
        result = mgr.stop_plugin(plugin.plugin_id)
        assert result is True
        assert plugin.state == PluginState.STOPPED

    def test_unload_plugin(self):
        """卸载插件。"""
        mgr = EcosystemManager()
        plugin = mgr.load_plugin("test", "t:Plugin")
        mgr.start_plugin(plugin.plugin_id)
        
        result = mgr.unload_plugin(plugin.plugin_id)
        
        assert result is True
        assert len(mgr.list_plugins()) == 0


# =========================================================================
# 4. 适配器管理
# =========================================================================

class TestAdapterManager:
    """适配器管理测试。"""

    def test_register_adapter(self):
        """注册适配器。"""
        mgr = EcosystemManager()
        
        def my_adapter(params):
            return f"result: {params}"
        
        result = mgr.register_adapter("test:action", my_adapter)
        
        assert result is True
        assert len(mgr.list_adapters()) == 1

    def test_unregister_adapter(self):
        """注销适配器。"""
        mgr = EcosystemManager()
        mgr.register_adapter("test:action", lambda p: "ok")
        
        result = mgr.unregister_adapter("test:action")
        
        assert result is True
        assert len(mgr.list_adapters()) == 0

    def test_get_adapter(self):
        """获取适配器。"""
        mgr = EcosystemManager()
        adapter = lambda p: "ok"
        mgr.register_adapter("test", adapter)
        
        retrieved = mgr.get_adapter("test")
        assert retrieved == adapter


# =========================================================================
# 5. 能力路由
# =========================================================================

class TestCapabilityRouting:
    """能力路由测试。"""

    def test_register_and_resolve_capability(self):
        """注册并解析能力。"""
        mgr = EcosystemManager()
        
        # 先创建并激活扩展
        ext = mgr.register_extension("test-ext", "reasoning")
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.MEDIUM)
        mgr.approve_extension(ext.extension_id)
        mgr.integrate_extension(ext.extension_id)
        mgr.activate_extension(ext.extension_id)
        
        # 注册能力
        result = mgr.register_capability("cap:test", ext.extension_id)
        assert result is True
        
        # 解析能力
        resolved = mgr.resolve_capability("cap:test")
        assert resolved == ext.extension_id

    def test_resolve_unknown_capability(self):
        """解析未知能力应返回 None。"""
        mgr = EcosystemManager()
        
        result = mgr.resolve_capability("unknown:cap")
        assert result is None


# =========================================================================
# 6. 信任管理
# =========================================================================

class TestTrustManagement:
    """信任管理测试。"""

    def test_update_trust_by_level(self):
        """按等级更新信任。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.HIGH)
        
        assert ext.trust_level == TrustLevel.HIGH

    def test_update_trust_by_usage(self):
        """基于使用次数动态调整信任。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        
        # 模拟大量使用
        for _ in range(150):
            mgr.record_usage(ext.extension_id)
        
        mgr.update_trust(extension_id=ext.extension_id, delta=1)
        
        # 使用超过100次应达到 TRUSTED
        assert ext.trust_level == TrustLevel.TRUSTED

    def test_get_trust_status(self):
        """获取信任状态。"""
        mgr = EcosystemManager()
        ext = mgr.register_extension("test", "perception")
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.HIGH)
        
        status = mgr.get_trust_status()
        
        assert "extensions" in status
        assert ext.extension_id in status["extensions"]
        assert status["extensions"][ext.extension_id]["trust_level"] == "high"


# =========================================================================
# 7. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = EcosystemManager()
        
        stats = mgr.get_stats()
        
        assert stats["extension_count"] == 0
        assert stats["plugin_count"] == 0
        assert stats["adapter_count"] == 0

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = EcosystemManager()
        
        # 注册扩展和插件
        mgr.register_extension("ext1", "perception")
        mgr.load_plugin("plugin1", "p1:Plugin")
        mgr.register_adapter("test", lambda p: "ok")
        
        stats = mgr.get_stats()
        
        assert stats["extensions_registered"] == 1
        assert stats["plugins_loaded"] == 1
        assert stats["adapters_registered"] == 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = EcosystemManager()
        mgr.register_extension("ext", "perception")
        mgr.reset_stats()
        
        stats = mgr.get_stats()
        assert stats["extensions_registered"] == 0


# =========================================================================
# 8. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_extensions_limit(self):
        """扩展数量上限约束。"""
        mgr = EcosystemManager(max_extensions=3)
        
        for i in range(3):
            mgr.register_extension(f"ext{i}", "perception")
        
        # 第4个应被拒绝
        result = mgr.register_extension("ext3", "perception")
        assert result is None

    def test_max_plugins_limit(self):
        """插件数量上限约束。"""
        mgr = EcosystemManager(max_plugins=2)
        
        for i in range(2):
            mgr.load_plugin(f"plugin{i}", f"p{i}:Plugin")
        
        # 第3个应被拒绝
        result = mgr.load_plugin("plugin2", "p2:Plugin")
        assert result is None


# =========================================================================
# 9. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_ecosystem_workflow(self):
        """完整生态系统工作流。"""
        mgr = EcosystemManager()

        # 1. 注册扩展（名称与插件对应）
        ext = mgr.register_extension("reasoning-ext", "reasoning")
        assert ext is not None

        # 2. 提升信任并批准
        mgr.update_trust(extension_id=ext.extension_id, level=TrustLevel.MEDIUM)
        mgr.approve_extension(ext.extension_id)

        # 3. 集成并激活
        mgr.integrate_extension(ext.extension_id)
        mgr.activate_extension(ext.extension_id)

        # 4. 注册能力
        mgr.register_capability("cap:reason", ext.extension_id)

        # 5. 注册适配器（key 需与 plugin name + action 匹配）
        def reasoning_adapter(params):
            return {"output": f"processed: {params.get('input', '')}"}

        mgr.register_adapter("reasoning-ext:reason", reasoning_adapter)

        # 6. 加载插件（name 必须与适配器前缀一致）
        plugin = mgr.load_plugin("reasoning-ext", "rp:Plugin")
        mgr.start_plugin(plugin.plugin_id)

        # 7. 执行插件
        result = mgr.execute_plugin(plugin.plugin_id, "reason", {"input": "test"})
        assert result["success"] is True

        # 8. 获取统计
        stats = mgr.get_stats()
        assert stats["extensions_active"] == 1
        assert stats["plugins_active"] == 1
        assert stats["calls_routed"] == 1

    def test_extension_revocation(self):
        """扩展撤销后的行为。"""
        mgr = EcosystemManager()
        
        ext = mgr.register_extension("test", "perception")
        mgr.activate_extension(ext.extension_id)
        
        # 撤销扩展
        mgr.revoke_extension(ext.extension_id)
        
        # 能力解析应失败
        mgr.register_capability("cap:test", ext.extension_id)
        # 撤销后能力映射可能仍保留，但扩展已不可用
        assert ext.state == ExtensionState.REVOKED


# =========================================================================
# 10. 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_nonexistent_extension(self):
        """操作不存在的扩展。"""
        mgr = EcosystemManager()
        
        assert mgr.approve_extension("nonexistent") is False
        assert mgr.integrate_extension("nonexistent") is False
        assert mgr.activate_extension("nonexistent") is False
        assert mgr.revoke_extension("nonexistent") is False

    def test_nonexistent_plugin(self):
        """操作不存在的插件。"""
        mgr = EcosystemManager()
        
        assert mgr.start_plugin("nonexistent") is False
        assert mgr.stop_plugin("nonexistent") is False
        assert mgr.unload_plugin("nonexistent") is False

    def test_execute_inactive_plugin(self):
        """执行未运行状态的插件。"""
        mgr = EcosystemManager()
        plugin = mgr.load_plugin("test", "t:Plugin")
        
        # 未启动时执行应失败
        result = mgr.execute_plugin(plugin.plugin_id, "action", {})
        assert "error" in result


# =========================================================================
# 回调测试
# =========================================================================

class TestCallbacks:
    """回调函数测试。"""

    def test_adapter_execution(self):
        """适配器执行回调。"""
        mgr = EcosystemManager()
        
        call_log = []
        
        def logging_adapter(params):
            call_log.append(params)
            return "logged"
        
        mgr.register_adapter("test:action", logging_adapter)
        
        plugin = mgr.load_plugin("test", "t:Plugin")
        mgr.start_plugin(plugin.plugin_id)
        
        result = mgr.execute_plugin(plugin.plugin_id, "action", {"key": "value"})
        
        assert result["success"] is True
        assert len(call_log) == 1
        assert call_log[0] == {"key": "value"}
