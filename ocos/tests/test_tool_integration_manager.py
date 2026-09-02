"""Phase AI: ToolIntegrationManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 工具发现
3. 工具注册/注销
4. 工具调用
5. 调用历史
6. 统计信息
7. 工具安全
8. 边界约束
9. 并发安全
10. 端到端流程
"""

from __future__ import annotations

import pytest
import threading
import time
from unittest.mock import MagicMock, patch

from ocos.tool.manager import (
    ToolIntegrationManager,
    ToolCategory,
    ToolPermission,
    ToolStatus,
    ToolDescriptor,
    ToolCallRecord,
    ToolCallStats,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tool_mgr():
    return ToolIntegrationManager(
        discovery_enabled=True,
        audit_enabled=True,
        rate_limit_per_second=10,
        max_call_history=100,
    )


@pytest.fixture
def sample_tool():
    return ToolDescriptor(
        tool_id="test-tool-1",
        name="Test Tool",
        category=ToolCategory.KNOWLEDGE,
        permission=ToolPermission.READ_ONLY,
        description="A test tool",
    )


# ── 1. 初始化配置 ────────────────────────────────────────────────────────

class TestInitialization:
    def test_create_default(self):
        mgr = ToolIntegrationManager()
        assert mgr is not None

    def test_create_with_config(self):
        mgr = ToolIntegrationManager(
            discovery_enabled=False,
            audit_enabled=False,
            rate_limit_per_second=50,
            max_call_history=500,
        )
        assert mgr._discovery_enabled == False
        assert mgr._audit_enabled == False
        assert mgr._rate_limit == 50

    def test_empty_initial_state(self):
        mgr = ToolIntegrationManager()
        status = mgr.get_status()
        assert status["total_tools"] == 0
        assert status["total_calls"] == 0
        assert status["history_size"] == 0


# ── 2. 工具发现 ─────────────────────────────────────────────────────────

class TestDiscovery:
    def test_discover_tools(self, tool_mgr):
        with patch.object(tool_mgr._discovery, 'run') as mock_run:
            mock_run.return_value = (
                MagicMock(),  # registry
                MagicMock(
                    available_tools=["git", "curl", "python3"],
                    unavailable_tools=[],
                    filesystem={},
                    shell={},
                    python_modules=[],
                    network={},
                    risk_assessment={},
                )
            )
            result = tool_mgr.discover_tools()
            assert result["discovered"] == 3
            assert "git" in result["tools"]

    def test_discover_failure(self, tool_mgr):
        with patch.object(tool_mgr._discovery, 'run') as mock_run:
            mock_run.side_effect = Exception("Discovery failed")
            result = tool_mgr.discover_tools()
            assert "error" in result
            assert result["discovered"] == 0


# ── 3. 工具注册/注销 ─────────────────────────────────────────────────────

class TestRegistration:
    def test_register_tool(self, tool_mgr):
        desc = tool_mgr.register_tool(
            tool_id="my-tool",
            name="My Tool",
            category=ToolCategory.SYSTEM,
            permission=ToolPermission.WRITE_ALLOWED,
            description="A system tool",
        )
        assert desc is not None
        assert desc.tool_id == "my-tool"
        assert tool_mgr.has_tool("my-tool")

    def test_register_duplicate(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        tool_mgr.register_tool("t1", "T1 Updated", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        assert tool_mgr.has_tool("t1")

    def test_unregister_tool(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        assert tool_mgr.unregister_tool("t1") == True
        assert not tool_mgr.has_tool("t1")

    def test_unregister_nonexistent(self, tool_mgr):
        assert tool_mgr.unregister_tool("nonexistent") == False

    def test_list_tools(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        tool_mgr.register_tool("t2", "T2", ToolCategory.NETWORK, ToolPermission.READ_ONLY)
        tools = tool_mgr.list_tools()
        assert len(tools) == 2

    def test_list_tools_by_category(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        tool_mgr.register_tool("t2", "T2", ToolCategory.NETWORK, ToolPermission.READ_ONLY)
        system_tools = tool_mgr.list_tools(category=ToolCategory.SYSTEM)
        assert len(system_tools) == 1
        assert system_tools[0]["tool_id"] == "t1"


# ── 4. 工具调用 ──────────────────────────────────────────────────────────

class TestToolCall:
    def test_call_registered_tool(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        result = tool_mgr.call_tool("t1", {"x": 1})
        assert result["success"] == True
        assert "call_id" in result
        assert "duration_ms" in result

    def test_call_unregistered_tool(self, tool_mgr):
        result = tool_mgr.call_tool("nonexistent")
        assert result["success"] == False
        # 未注册的工具会被 rate limited 或 blocked
        assert "error" in result

    def test_call_dangerous_tool_blocked(self, tool_mgr):
        tool_mgr.register_tool("danger", "Danger", ToolCategory.SYSTEM, ToolPermission.DANGEROUS)
        result = tool_mgr.call_tool("danger")
        assert result["success"] == False
        assert "blocked" in result["error"]

    def test_can_call_tool(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        assert tool_mgr.can_call_tool("t1") == True
        assert tool_mgr.can_call_tool("nonexistent") == False


# ── 5. 调用历史 ─────────────────────────────────────────────────────────

class TestCallHistory:
    def test_history_records(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        tool_mgr.call_tool("t1", {"x": 1})
        tool_mgr.call_tool("t1", {"x": 2})
        history = tool_mgr.get_call_history()
        assert len(history) == 2

    def test_history_limit(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        for i in range(150):
            tool_mgr.call_tool("t1", {"i": i})
        history = tool_mgr.get_call_history(limit=50)
        assert len(history) <= 50


# ── 6. 统计信息 ─────────────────────────────────────────────────────────

class TestStatistics:
    def test_stats_after_calls(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        for _ in range(5):
            tool_mgr.call_tool("t1")
        stats = tool_mgr.get_call_stats()
        assert stats["total_calls"] == 5
        assert stats["successful_calls"] == 5
        assert stats["success_rate"] == 1.0

    def test_stats_after_failure(self, tool_mgr):
        stats = tool_mgr.get_call_stats()
        assert stats["total_calls"] == 0
        assert stats["failed_calls"] == 0


# ── 7. 工具安全 ─────────────────────────────────────────────────────────

class TestSecurity:
    def test_block_tool(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.WRITE_ALLOWED)
        assert tool_mgr.block_tool("t1") == True
        tool = tool_mgr.get_tool("t1")
        assert tool.permission == ToolPermission.DANGEROUS

    def test_unblock_tool(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.DANGEROUS)
        assert tool_mgr.unblock_tool("t1") == True
        tool = tool_mgr.get_tool("t1")
        assert tool.permission == ToolPermission.READ_ONLY


# ── 8. 边界约束 ─────────────────────────────────────────────────────────

class TestBoundary:
    def test_rate_limiting(self, tool_mgr):
        """测试速率限制。"""
        # 降低限速以便测试
        tool_mgr._rate_limit = 5
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        # 连续调用超过限制
        results = []
        for _ in range(10):
            results.append(tool_mgr.call_tool("t1"))
        # 部分调用应该被限速
        blocked = sum(1 for r in results if not r["success"])
        assert blocked > 0

    def test_max_history_cleanup(self, tool_mgr):
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        for _ in range(150):
            tool_mgr.call_tool("t1")
        history = tool_mgr.get_call_history()
        assert len(history) <= 100


# ── 9. 并发安全 ─────────────────────────────────────────────────────────

class TestConcurrency:
    def test_concurrent_tool_calls(self, tool_mgr):
        # 提高限速以避免并发测试中被误限速
        tool_mgr._rate_limit = 1000
        tool_mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        results = []

        def call():
            for _ in range(10):
                r = tool_mgr.call_tool("t1")
                results.append(r["success"])

        threads = [threading.Thread(target=call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = tool_mgr.get_call_stats()
        assert stats["total_calls"] == 50


# ── 10. 端到端流程 ──────────────────────────────────────────────────────

class TestEndToEnd:
    def test_full_workflow(self, tool_mgr):
        # 1. 注册工具
        tool_mgr.register_tool("search", "Web Search", ToolCategory.KNOWLEDGE, ToolPermission.READ_ONLY)
        tool_mgr.register_tool("exec", "Code Exec", ToolCategory.SYSTEM, ToolPermission.EXECUTE_ALLOWED)

        # 2. 调用工具
        result = tool_mgr.call_tool("search", {"query": "OCOS"})
        assert result["success"]

        # 3. 查看历史
        history = tool_mgr.get_call_history()
        assert len(history) >= 1

        # 4. 查看统计
        stats = tool_mgr.get_call_stats()
        assert stats["total_calls"] >= 1

        # 5. 获取状态
        status = tool_mgr.get_status()
        assert status["total_tools"] == 2


# ── 辅助测试 ─────────────────────────────────────────────────────────────

class TestHelpers:
    def test_tool_descriptor_to_dict(self, sample_tool):
        d = sample_tool.to_dict()
        assert d["tool_id"] == "test-tool-1"
        assert d["category"] == "knowledge"

    def test_call_record_to_dict(self):
        record = ToolCallRecord(
            call_id="c1",
            tool_id="t1",
            timestamp=time.time(),
            input_args={"x": 1},
            output_result={"ok": True},
            duration_ms=100.0,
            success=True,
        )
        d = record.to_dict()
        assert d["call_id"] == "c1"
        assert d["success"] == True

    def test_call_stats_recording(self):
        stats = ToolCallStats()
        record = ToolCallRecord(
            call_id="c1",
            tool_id="t1",
            timestamp=time.time(),
            input_args={},
            output_result={},
            duration_ms=50.0,
            success=True,
        )
        stats.record_call(record)
        assert stats.total_calls == 1
        assert stats.successful_calls == 1
        assert stats.avg_duration_ms == 50.0
