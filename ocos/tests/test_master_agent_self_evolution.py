"""Phase AA: SelfEvolutionManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 提案检测与生成
3. 提案分析
4. 沙箱验证
5. 提案批准
6. 提案执行
7. 回滚机制
8. 状态查询
9. 历史查询
10. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.evolution.manager import SelfEvolutionManager
from ocos.evolution.evolution_types import (
    EvolutionState,
    EvolutionTrigger,
    EvolutionDomain,
    RollbackReason,
)


@pytest.fixture
def mock_agent():
    """创建带有模拟依赖的 Agent 实例。"""
    mock_identity = MagicMock()
    mock_goal_stack = MagicMock()
    mock_intent = MagicMock()
    mock_attention = MagicMock()
    mock_working_memory = MagicMock()
    mock_capability_manager = MagicMock()
    mock_execution_manager = MagicMock()

    agent = MasterAgent(
        agent_id="test-agent",
        identity=mock_identity,
        goal_stack=mock_goal_stack,
        intent=mock_intent,
        attention=mock_attention,
        working_memory=mock_working_memory,
        capability_manager=mock_capability_manager,
        execution_manager=mock_execution_manager,
    )
    return agent


@pytest.fixture
def agent_with_evolution(mock_agent):
    """创建带有自我演化管理器的 Agent 实例。"""
    sem = SelfEvolutionManager()
    mock_agent._self_evolution_manager = sem
    return mock_agent


# =========================================================================
# 1. 管理器注入测试
# =========================================================================

class TestMasterAgentInjection:
    """测试 SelfEvolutionManager 注入到 MasterAgent。"""

    def _create_mock_agent(self):
        """创建带有模拟依赖的 Agent 实例。"""
        mock_identity = MagicMock()
        mock_goal_stack = MagicMock()
        mock_intent = MagicMock()
        mock_attention = MagicMock()
        mock_working_memory = MagicMock()
        mock_capability_manager = MagicMock()
        mock_execution_manager = MagicMock()

        return MasterAgent(
            agent_id="test-agent",
            identity=mock_identity,
            goal_stack=mock_goal_stack,
            intent=mock_intent,
            attention=mock_attention,
            working_memory=mock_working_memory,
            capability_manager=mock_capability_manager,
            execution_manager=mock_execution_manager,
        )

    def test_inject_self_evolution_manager(self):
        """注入自我演化管理器。"""
        agent = self._create_mock_agent()
        sem = SelfEvolutionManager()
        
        agent._self_evolution_manager = sem
        
        assert agent.self_evolution_manager == sem

    def test_missing_self_evolution_manager(self):
        """未注入时应返回 None。"""
        agent = self._create_mock_agent()
        
        assert agent.self_evolution_manager is None


# =========================================================================
# 2. 提案检测与生成
# =========================================================================

class TestDetection:
    """提案检测测试。"""

    def test_detect_evolution_opportunity(self, agent_with_evolution):
        """检测进化机会。"""
        agent = agent_with_evolution

        result = agent.detect_evolution_opportunity(
            source_module="test.module",
            metric_name="performance",
            metric_value=0.6,
            threshold=0.7,
            severity=0.8,
            description="Performance degradation detected",
        )

        assert "proposal_id" in result
        # 默认 trigger="experience" 映射到 LEARNING_STRATEGY
        assert result["domain"] == EvolutionDomain.LEARNING_STRATEGY.value
        assert result["state"] == EvolutionState.DRAFTING.value

    def test_detect_with_trigger(self, agent_with_evolution):
        """指定触发器类型。"""
        agent = agent_with_evolution

        result = agent.detect_evolution_opportunity(
            source_module="test",
            metric_name="score",
            metric_value=0.5,
            threshold=0.6,
            severity=0.5,
            description="Test proposal",
            trigger="health_alert",
        )

        assert result["domain"] == EvolutionDomain.PARAMETER.value
        assert result["trigger"] == EvolutionTrigger.HEALTH_ALERT.value

    def test_detect_without_manager(self, mock_agent):
        """未注入管理器时应返回错误。"""
        result = mock_agent.detect_evolution_opportunity(
            source_module="test", metric_name="m", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Test"
        )

        assert "error" in result
        assert "not injected" in result["error"]


# =========================================================================
# 3. 提案分析
# =========================================================================

class TestAnalysis:
    """提案分析测试。"""

    def test_analyze_proposal(self, agent_with_evolution):
        """分析提案影响。"""
        agent = agent_with_evolution

        # 先创建提案
        detect_result = agent.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Analysis test"
        )
        proposal_id = detect_result["proposal_id"]

        # 分析
        result = agent.analyze_evolution_proposal(proposal_id)

        assert "impact_level" in result
        assert "is_safe" in result

    def test_analyze_nonexistent(self, agent_with_evolution):
        """分析不存在的提案。"""
        result = agent_with_evolution.analyze_evolution_proposal("nonexistent-id")

        assert "error" in result


# =========================================================================
# 4. 沙箱验证
# =========================================================================

class TestValidation:
    """沙箱验证测试。"""

    def test_validate_proposal(self, agent_with_evolution):
        """验证提案。"""
        agent = agent_with_evolution

        # 创建提案
        detect_result = agent.detect_evolution_opportunity(
            source_module="test.module", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Valid proposal for validation"
        )
        proposal_id = detect_result["proposal_id"]

        # 验证
        result = agent.validate_evolution_proposal(proposal_id)

        assert "result" in result
        assert "test_count" in result

    def test_validate_nonexistent(self, agent_with_evolution):
        """验证不存在的提案。"""
        result = agent_with_evolution.validate_evolution_proposal("nonexistent-id")

        assert "error" in result


# =========================================================================
# 5. 提案批准
# =========================================================================

class TestApproval:
    """提案批准测试。"""

    def test_approve_proposal(self, agent_with_evolution):
        """批准提案。"""
        agent = agent_with_evolution

        # 创建并验证提案
        detect_result = agent.detect_evolution_opportunity(
            source_module="test.module", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Proposal for approval"
        )
        proposal_id = detect_result["proposal_id"]
        agent.validate_evolution_proposal(proposal_id)

        # 批准
        result = agent.approve_evolution_proposal(proposal_id, "admin")

        assert result is True

    def test_approve_without_validation(self, agent_with_evolution):
        """未验证的提案不能被批准。"""
        agent = agent_with_evolution

        # 只创建不验证
        detect_result = agent.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Invalid proposal"
        )
        proposal_id = detect_result["proposal_id"]

        result = agent.approve_evolution_proposal(proposal_id)

        assert result is False

    def test_approve_nonexistent(self, agent_with_evolution):
        """批准不存在的提案。"""
        result = agent_with_evolution.approve_evolution_proposal("nonexistent-id")

        assert result is False


# =========================================================================
# 6. 提案执行
# =========================================================================

class TestExecution:
    """提案执行测试。"""

    def test_execute_proposal(self, agent_with_evolution):
        """执行批准的提案。"""
        agent = agent_with_evolution

        # 完整流程
        detect_result = agent.detect_evolution_opportunity(
            source_module="test.module", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Proposal to execute"
        )
        proposal_id = detect_result["proposal_id"]
        agent.validate_evolution_proposal(proposal_id)
        agent.approve_evolution_proposal(proposal_id)

        # 执行
        result = agent.execute_evolution_proposal(proposal_id)

        assert result["success"] is True

    def test_execute_unapproved(self, agent_with_evolution):
        """执行未批准的提案。"""
        agent = agent_with_evolution

        # 只创建不批准
        detect_result = agent.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Unapproved proposal"
        )
        proposal_id = detect_result["proposal_id"]

        result = agent.execute_evolution_proposal(proposal_id)

        # 应该失败或未就绪
        assert "error" in result or not result.get("success", True)

    def test_execute_nonexistent(self, agent_with_evolution):
        """执行不存在的提案。"""
        result = agent_with_evolution.execute_evolution_proposal("nonexistent-id")

        assert "error" in result


# =========================================================================
# 7. 回滚机制
# =========================================================================

class TestRollback:
    """回滚机制测试。"""

    def test_rollback_after_execution(self, agent_with_evolution):
        """执行后应能回滚。"""
        agent = agent_with_evolution

        # 执行进化
        detect_result = agent.detect_evolution_opportunity(
            source_module="test.module", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Proposal for rollback"
        )
        proposal_id = detect_result["proposal_id"]
        agent.validate_evolution_proposal(proposal_id)
        agent.approve_evolution_proposal(proposal_id)
        agent.execute_evolution_proposal(proposal_id)

        # 回滚
        result = agent.rollback_evolution(proposal_id, "test_failure")

        assert result is True

    def test_rollback_no_snapshot(self, agent_with_evolution):
        """无快照的提案不能回滚。"""
        agent = agent_with_evolution

        # 只创建不执行
        detect_result = agent.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="No snapshot"
        )
        proposal_id = detect_result["proposal_id"]

        result = agent.rollback_evolution(proposal_id)

        assert result is False

    def test_rollback_nonexistent(self, agent_with_evolution):
        """回滚不存在的提案。"""
        result = agent_with_evolution.rollback_evolution("nonexistent-id")

        assert result is False


# =========================================================================
# 8. 状态查询
# =========================================================================

class TestStatusQuery:
    """状态查询测试。"""

    def test_get_evolution_status(self, agent_with_evolution):
        """获取进化状态。"""
        status = agent_with_evolution.get_evolution_status()

        assert "total_proposals" in status
        assert "successful_migrations" in status

    def test_get_evolution_status_without_manager(self, mock_agent):
        """未注入时返回错误。"""
        status = mock_agent.get_evolution_status()

        assert "error" in status

    def test_get_evolution_history(self, agent_with_evolution):
        """获取进化历史。"""
        # 创建提案
        agent_with_evolution.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="History test"
        )

        history = agent_with_evolution.get_evolution_history()

        assert isinstance(history, list)
        assert len(history) > 0

    def test_get_evolution_proposals(self, agent_with_evolution):
        """列出进化提案。"""
        # 创建多个提案
        agent_with_evolution.detect_evolution_opportunity(
            source_module="test1", metric_name="m1", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Proposal 1"
        )
        agent_with_evolution.detect_evolution_opportunity(
            source_module="test2", metric_name="m2", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Proposal 2"
        )

        proposals = agent_with_evolution.get_evolution_proposals()

        assert len(proposals) == 2

    def test_get_evolution_proposals_by_state(self, agent_with_evolution):
        """按状态过滤提案。"""
        # 创建并执行一个提案
        detect_result = agent_with_evolution.detect_evolution_opportunity(
            source_module="test", metric_name="score", metric_value=0.5,
            threshold=0.6, severity=0.5, description="Active proposal"
        )
        proposal_id = detect_result["proposal_id"]
        agent_with_evolution.validate_evolution_proposal(proposal_id)
        agent_with_evolution.approve_evolution_proposal(proposal_id)
        agent_with_evolution.execute_evolution_proposal(proposal_id)

        # 列出活跃提案
        active = agent_with_evolution.get_evolution_proposals(state="active")

        assert len(active) == 1
        assert active[0]["state"] == EvolutionState.ACTIVE.value


# =========================================================================
# 9. Tick 接口
# =========================================================================

class TestTick:
    """主循环 tick 测试。"""

    def test_tick_with_manager(self, agent_with_evolution):
        """有管理器时的 tick。"""
        result = agent_with_evolution.tick()

        assert "tick" in result
        assert result["tick"] >= 0

    def test_tick_without_manager(self, mock_agent):
        """无管理器时的 tick。"""
        result = mock_agent.tick()

        assert result == {"tick": 0, "evolutions": []}


# =========================================================================
# 端到端测试
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_evolution_cycle_via_master_agent(self, agent_with_evolution):
        """通过 MasterAgent 执行完整进化周期。"""
        agent = agent_with_evolution

        # 1. 检测
        detect_result = agent.detect_evolution_opportunity(
            source_module="test.module",
            metric_name="performance",
            metric_value=0.6,
            threshold=0.7,
            severity=0.8,
            description="Performance optimization needed",
        )
        proposal_id = detect_result["proposal_id"]
        assert proposal_id is not None

        # 2. 分析
        analyze_result = agent.analyze_evolution_proposal(proposal_id)
        assert "impact_level" in analyze_result

        # 3. 验证
        validate_result = agent.validate_evolution_proposal(proposal_id)
        assert validate_result["result"] == "passed"

        # 4. 批准
        approve_result = agent.approve_evolution_proposal(proposal_id, "admin")
        assert approve_result is True

        # 5. 执行
        execute_result = agent.execute_evolution_proposal(proposal_id)
        assert execute_result["success"] is True

        # 6. 验证最终状态
        status = agent.get_evolution_status()
        assert status["active_proposals"] == 1
        assert status["successful_migrations"] == 1

        # 7. 验证历史
        history = agent.get_evolution_history()
        assert len(history) >= 5  # detected, analyzing, sandbox_passed, approved, migrated
