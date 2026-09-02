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

from ocos.knowledge.synthesis_manager import KnowledgeSynthesisManager


@pytest.fixture
def knowledge_mgr():
    mgr = KnowledgeSynthesisManager()
    # seed 节点
    n1 = mgr.add_knowledge_node("Python是编程语言", "python基础", tags=["编程", "语言"])
    n2 = mgr.add_knowledge_node("机器学习是AI子领域", "机器学习", tags=["AI", "ML"])
    n3 = mgr.add_knowledge_node("神经网络是ML方法", "神经网络", tags=["AI", "DL"])
    return mgr, n1.node_id, n2.node_id, n3.node_id


@pytest.fixture
def mock_agent(knowledge_mgr):
    mgr, n1, n2, n3 = knowledge_mgr
    agent = MagicMock()
    agent.agent_id = "test-agent"
    agent._knowledge_synthesis_manager = mgr
    agent._self_evolution_manager = None
    agent._distributed_manager = None
    agent._ecosystem_manager = None
    agent._human_ai_manager = None
    agent._self_reflection_manager = None
    agent._self_optimization_manager = None
    return agent


class TestKnowledgeInjection:
    """测试知识管理器注入。"""

    def test_inject_knowledge_manager(self, mock_agent):
        assert hasattr(mock_agent, "knowledge_synthesis_manager")
        assert mock_agent.knowledge_synthesis_manager is not None


class TestKnowledgeCRUD:
    """测试知识节点 CRUD。"""

    def test_add_and_get_node(self, mock_agent):
        nid = mock_agent.add_knowledge_node("测试知识", "test")
        assert nid != ""
        node = mock_agent.get_knowledge_node(nid)
        assert node is not None
        assert "content" in node

    def test_get_unknown_node(self, mock_agent):
        result = mock_agent.get_knowledge_node("kn:nonexist")
        assert result is None

    def test_search_knowledge(self, mock_agent, knowledge_mgr):
        _, n1, n2, n3 = knowledge_mgr
        results = mock_agent.search_knowledge("AI", limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5


class TestKnowledgeSynthesis:
    """测试知识综合。"""

    def test_synthesize(self, mock_agent, knowledge_mgr):
        _, n1, n2, n3 = knowledge_mgr
        result = mock_agent.synthesize_knowledge([n1.node_id, n2.node_id])
        assert isinstance(result, dict)
        assert "result_id" in result
        assert "new_knowledge" in result


class TestPathFinding:
    """测试路径查找。"""

    def test_find_path(self, mock_agent, knowledge_mgr):
        _, n1, n2, n3 = knowledge_mgr
        path = mock_agent.get_path_between(n1.node_id, n3.node_id)
        assert isinstance(path, list)


class TestAssessQuality:
    """测试知识质量评估。"""

    def test_assess_quality(self, mock_agent, knowledge_mgr):
        result = mock_agent.assess_knowledge_quality()
        assert isinstance(result, dict)
        assert "overall_score" in result


class TestStats:
    """测试统计。"""

    def test_get_stats(self, mock_agent, knowledge_mgr):
        stats = mock_agent.get_knowledge_stats()
        assert isinstance(stats, dict)
        assert "total_nodes" in stats


class TestTickIntegration:
    """测试 tick 集成。"""

    def test_tick_with_knowledge(self, mock_agent):
        result = mock_agent.tick()
        assert "tick" in result
        assert "knowledge" in result
        assert isinstance(result["knowledge"], dict)


class TestEndToEnd:
    """端到端验证。"""

    def test_full_workflow(self, mock_agent):
        # 1. 添加节点
        n1 = mock_agent.add_knowledge_node("OCOS是个人智脑", "ocostest")
        n2 = mock_agent.add_knowledge_node("知识综合是AG能力", "ocostest")
        assert n1 != "" and n2 != ""

        # 2. 查询节点
        node = mock_agent.get_knowledge_node(n1)
        assert node is not None
        assert "content" in node

        # 3. 综合知识
        result = mock_agent.synthesize_knowledge([n1, n2])
        assert isinstance(result, dict)
        assert "result_id" in result

        # 4. 评估质量
        quality = mock_agent.assess_knowledge_quality()
        assert isinstance(quality, dict)

        # 5. tick
        tick_result = mock_agent.tick()
        assert "knowledge" in tick_result


class TestNoneManager:
    """None 管理器边界。"""

    def test_methods_with_none(self):
        from ocos.agent.master_agent import MasterAgent
        from ocos.identity import AgentIdentity
        agent = MasterAgent(AgentIdentity(agent_id="test"))
        assert agent.add_knowledge_node("x", "t") == ""
        assert agent.get_knowledge_node("x") is None
        assert agent.synthesize_knowledge(["x"]) == {}
        assert agent.search_knowledge("x") == []
        assert agent.get_path_between("a", "b") == []
        assert agent.assess_knowledge_quality() == {}
        assert agent.get_knowledge_stats() == {}
        result = agent.tick()
        assert "knowledge" in result


class TestInvalidInput:
    """非法输入处理。"""

    def test_add_invalid_node(self, mock_agent):
        result = mock_agent.add_knowledge_node("", "invalid")
        assert result == ""

    def test_synthesize_empty_ids(self, mock_agent):
        result = mock_agent.synthesize_knowledge([])
        assert result == {}

    def test_search_zero_limit(self, mock_agent):
        results = mock_agent.search_knowledge("test", limit=0)
        assert results == []
