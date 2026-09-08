"""EngineBridge + WriterEngine 集成测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ocos.agent.engine_bridge import EngineBridge
from ocos.agent.agent_runtime import AgentRuntime, RuntimeState
from ocos.agent.capability_selector import CapabilitySelector


@pytest.fixture
def bridge():
    """EngineBridge with WriterEngine registered."""
    b = EngineBridge()
    b.register("writer")
    return b


class TestEngineBridgeWriterIntegration:
    """EngineBridge + WriterEngine 基本集成。"""

    def test_register_writer(self, bridge):
        """注册 writer 引擎成功。"""
        adapter = bridge.get_adapter("writer")
        assert adapter is not None
        assert adapter.name == "writer"

    def test_plan_via_bridge(self, bridge):
        """通过桥接执行 plan。"""
        from ocos.models.process import ProcessType

        result = bridge.execute(
            "writer",
            ProcessType.PLANNING,
            operation="plan",
            inputs={"chapter_count": 3, "genre": "urban_romance"},
        )
        assert result["success"] is True
        assert result["count"] == 3

    def test_generate_via_bridge(self, bridge):
        """通过桥接执行 generate。"""
        from ocos.models.process import ProcessType

        # 模拟无 opentale
        adapter = bridge.get_adapter("writer")
        adapter._engine._opentale_available = False

        result = bridge.execute(
            "writer",
            ProcessType.PLANNING,
            operation="generate",
            inputs={"chapter_index": 1, "genre": "romance"},
        )
        assert result["success"] is True
        assert result["count"] == 1

    def test_status_via_bridge(self, bridge):
        """通过桥接执行 status。"""
        from ocos.models.process import ProcessType

        result = bridge.execute(
            "writer", ProcessType.PLANNING, operation="status"
        )
        assert result["success"] is True


class TestAgentRuntimeWithWriter:
    """AgentRuntime + WriterEngine 端到端集成。"""

    @pytest.fixture
    def runtime(self):
        """带 writer 引擎的完整运行时。"""
        from unittest.mock import MagicMock
        from ocos.agent.agent_runtime import AgentRuntime, RuntimeState

        agent = MagicMock()
        engine_list = ["writer"]
        bridge = EngineBridge()
        bridge.register_all()
        rt = AgentRuntime(
            agent=agent,
            engine_list=engine_list,
            engine_bridge=bridge,
        )
        return rt

    def test_runtime_boot_with_writer(self, runtime):
        """boot 后状态为 RUNNING。"""
        state = runtime.boot()
        assert state is None  # boot 返回 None
        assert runtime.state == RuntimeState.RUNNING
        assert runtime.loop is not None

    def test_bridge_writer_registered(self, runtime):
        """运行时桥接已连接 writer。"""
        runtime.boot()
        bridge = runtime.loop._engine_bridge
        assert bridge is not None
        writer = bridge.get_adapter("writer")
        if writer:
            assert writer.name == "writer"
            # 验证能通过 writer 执行 plan
            from ocos.models.process import ProcessType
            result = bridge.execute(
                "writer", ProcessType.PLANNING,
                operation="plan",
                inputs={"chapter_count": 5, "genre": "urban_romance"},
            )
            assert result["success"] is True
            assert result["count"] == 5
