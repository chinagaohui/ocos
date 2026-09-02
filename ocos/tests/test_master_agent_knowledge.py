"""Phase AG: KnowledgeSynthesisManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 知识节点 CRUD
3. 知识综合
4. 知识查询
5. 路径查找
6. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.knowledge.synthesis_manager import KnowledgeSynthesisManager, KnowledgeType, KnowledgeSource


@pytest.fixture
def knowledge_mgr():
    mgr = KnowledgeSynthesisManager()
    # seed 节点
    n1 = mgr.add_knowledge("Python是编程语言", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
    n2 = mgr.add_knowledge("机器学习是AI子领域", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
    n3 = mgr.add_knowledge("神经网络是ML方法", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
    return mgr, n1.node_id, n2.node_id, n3.node_id


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
def agent_with_knowledge(mock_agent, knowledge_mgr):
    """创建带有知识综合管理器的 Agent 实例。"""
    mgr, n1, n2, n3 = knowledge_mgr
    mock_agent._knowledge_synthesis_manager = mgr
    return mock_agent, n1, n2, n3


class TestKnowledgeInjection:
    """测试知识管理器注入。"""

    def test_inject_knowledge_manager(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        assert hasattr(agent, "knowledge_synthesis_manager")
        assert agent.knowledge_synthesis_manager is not None


class TestKnowledgeCRUD:
    """测试知识节点 CRUD。"""

    def test_add_and_get_node(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        nid = agent.add_knowledge_node("测试知识", "test")
        assert nid != ""
        node = agent.get_knowledge_node(nid)
        assert node is not None
        assert "content" in node

    def test_get_unknown_node(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        result = agent.get_knowledge_node("kn:nonexist")
        assert result is None

    def test_search_knowledge(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        results = agent.search_knowledge("AI", limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5


class TestKnowledgeSynthesis:
    """测试知识综合。"""

    def test_synthesize(self, agent_with_knowledge):
        agent, n1, n2, n3 = agent_with_knowledge
        result = agent.synthesize_knowledge([n1, n2])
        assert isinstance(result, dict)
        assert "result_id" in result
        assert "new_knowledge" in result


class TestPathFinding:
    """测试路径查找。"""

    def test_find_path(self, agent_with_knowledge):
        agent, n1, n2, n3 = agent_with_knowledge
        path = agent.get_path_between(n1, n3)
        assert isinstance(path, list)


class TestAssessQuality:
    """测试知识质量评估。"""

    def test_assess_quality(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        result = agent.assess_knowledge_quality()
        assert isinstance(result, dict)


class TestStats:
    """测试统计。"""

    def test_get_stats(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        stats = agent.get_knowledge_synthesis_stats()
        assert isinstance(stats, dict)


class TestTickIntegration:
    """测试 tick 集成。"""

    def test_tick_with_knowledge(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        result = agent.tick()
        assert "tick" in result
        assert "knowledge" in result
        assert isinstance(result["knowledge"], dict)


class TestEndToEnd:
    """端到端验证。"""

    def test_full_workflow(self, agent_with_knowledge):
        agent, n1, n2, n3 = agent_with_knowledge
        # 1. 添加节点
        nid1 = agent.add_knowledge_node("OCOS是个人智脑", "ocostest")
        nid2 = agent.add_knowledge_node("知识综合是AG能力", "ocostest")
        assert nid1 != "" and nid2 != ""

        # 2. 查询节点
        node = agent.get_knowledge_node(nid1)
        assert node is not None
        assert "content" in node

        # 3. 综合知识
        result = agent.synthesize_knowledge([nid1, nid2])
        assert isinstance(result, dict)
        assert "result_id" in result

        # 4. 评估质量
        quality = agent.assess_knowledge_quality()
        assert isinstance(quality, dict)

        # 5. tick
        tick_result = agent.tick()
        assert "knowledge" in tick_result


class TestNoneManager:
    """None 管理器边界。"""

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


class TestInvalidInput:
    """非法输入处理。"""

    def test_add_invalid_node(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        result = agent.add_knowledge_node("", "invalid")
        assert result == ""

    def test_synthesize_empty_ids(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        result = agent.synthesize_knowledge([])
        assert result == {}

    def test_search_zero_limit(self, agent_with_knowledge):
        agent, _, _, _ = agent_with_knowledge
        results = agent.search_knowledge("test", limit=0)
        assert results == []
