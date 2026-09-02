"""Phase AH: SelfDiagnosisManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 诊断接口
3. 健康状态
4. 历史记录
5. 统计信息
6. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.diagnosis.manager import (
    SelfDiagnosisManager,
    DiagnosisMode,
    AutoRepairPolicy,
)


@pytest.fixture
def diagnosis_mgr():
    return SelfDiagnosisManager(
        mode=DiagnosisMode.MANUAL,
        auto_repair_policy=AutoRepairPolicy.NEVER,
    )


@pytest.fixture
def mock_agent():
    """创建带有模拟依赖的 Agent 实例。"""
    return MasterAgent(
        agent_id="test-agent",
        identity=MagicMock(),
        goal_stack=MagicMock(),
        intent=MagicMock(),
        attention=MagicMock(),
        working_memory=MagicMock(),
        capability_manager=MagicMock(),
        execution_manager=MagicMock(),
    )


@pytest.fixture
def agent_with_diagnosis(mock_agent, diagnosis_mgr):
    """创建带有自我诊断管理器的 Agent 实例。"""
    mock_agent._self_diagnosis_manager = diagnosis_mgr
    return mock_agent


class TestDiagnosisInjection:
    """测试诊断管理器注入。"""

    def test_inject_diagnosis_manager(self, agent_with_diagnosis):
        assert hasattr(agent_with_diagnosis, "self_diagnosis_manager")
        assert agent_with_diagnosis.self_diagnosis_manager is not None


class TestDiagnose:
    """测试诊断接口。"""

    def test_diagnose_returns_dict(self, agent_with_diagnosis):
        result = agent_with_diagnosis.diagnose()
        assert isinstance(result, dict)
        assert "snapshot_id" in result or "error" in result

    def test_diagnose_with_manager(self, agent_with_diagnosis):
        result = agent_with_diagnosis.diagnose()
        assert "snapshot_id" in result
        assert "overall_health" in result
        assert "faults_detected" in result
        assert "trend" in result

    def test_diagnose_none_manager(self, mock_agent):
        result = mock_agent.diagnose()
        assert result == {"error": "self_diagnosis_manager not injected"}


class TestHealthStatus:
    """测试健康状态。"""

    def test_get_diagnosis_status(self, agent_with_diagnosis):
        status = agent_with_diagnosis.get_diagnosis_status()
        assert isinstance(status, dict)
        assert "overall_health" in status
        assert "trend" in status
        assert "degraded_components" in status

    def test_diagnosis_status_none_manager(self, mock_agent):
        status = mock_agent.get_diagnosis_status()
        assert status == {}


class TestHistory:
    """测试历史记录。"""

    def test_get_diagnosis_history(self, agent_with_diagnosis):
        agent_with_diagnosis.diagnose()
        history = agent_with_diagnosis.get_diagnosis_history()
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_get_fault_history(self, agent_with_diagnosis):
        history = agent_with_diagnosis.get_fault_history()
        assert isinstance(history, list)

    def test_get_repair_history(self, agent_with_diagnosis):
        history = agent_with_diagnosis.get_repair_history()
        assert isinstance(history, dict)


class TestStats:
    """测试统计信息。"""

    def test_get_diagnosis_stats(self, agent_with_diagnosis):
        agent_with_diagnosis.diagnose()
        stats = agent_with_diagnosis.get_diagnosis_stats()
        assert isinstance(stats, dict)
        assert "total_snapshots" in stats

    def test_stats_none_manager(self, mock_agent):
        stats = mock_agent.get_diagnosis_stats()
        assert stats == {}


class TestTickIntegration:
    """测试 tick 集成。"""

    def test_tick_with_diagnosis(self, agent_with_diagnosis):
        result = agent_with_diagnosis.tick()
        assert "tick" in result
        assert "diagnosis" in result
        assert isinstance(result["diagnosis"], dict)


class TestEndToEnd:
    """端到端验证。"""

    def test_full_workflow(self, agent_with_diagnosis):
        # 1. 诊断
        diag_result = agent_with_diagnosis.diagnose()
        assert "snapshot_id" in diag_result

        # 2. 获取诊断状态
        status = agent_with_diagnosis.get_diagnosis_status()
        assert "overall_health" in status

        # 3. 获取历史
        history = agent_with_diagnosis.get_diagnosis_history()
        assert len(history) >= 1

        # 4. 获取统计
        stats = agent_with_diagnosis.get_diagnosis_stats()
        assert stats["total_snapshots"] >= 1

        # 5. tick
        tick_result = agent_with_diagnosis.tick()
        assert "diagnosis" in tick_result


class TestNoneManager:
    """None 管理器边界。"""

    def test_all_methods_with_none(self, mock_agent):
        assert mock_agent.diagnose() == {"error": "self_diagnosis_manager not injected"}
        assert mock_agent.get_diagnosis_status() == {}
        assert mock_agent.get_diagnosis_history() == []
        assert mock_agent.get_fault_history() == []
        assert mock_agent.get_repair_history() == {}
        assert mock_agent.get_diagnosis_stats() == {}
        result = mock_agent.tick()
        assert "tick" in result


class TestKnowledgeNoneManager:
    """知识管理器 None 边界。"""

    def test_methods_with_none(self, mock_agent):
        assert mock_agent.add_knowledge_node("x", "t") == ""
        assert mock_agent.get_knowledge_node("x") is None
        assert mock_agent.synthesize_knowledge(["x"]) == {}
        assert mock_agent.search_knowledge("x") == []
        assert mock_agent.get_path_between("a", "b") == []
        assert mock_agent.assess_knowledge_quality() == {}
        assert mock_agent.get_knowledge_synthesis_stats() == {}
        result = mock_agent.tick()
        assert "knowledge" in result
