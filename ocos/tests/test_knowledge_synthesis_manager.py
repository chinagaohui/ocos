"""Phase AG: KnowledgeSynthesisManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 知识节点管理
3. 知识边管理
4. 知识综合
5. 知识查询
6. 路径查找
7. 质量评估
8. 统计信息
9. 边界约束
10. 端到端流程
"""

from __future__ import annotations

import pytest
from ocos.knowledge.synthesis_manager import (
    KnowledgeSynthesisManager,
    KnowledgeType,
    KnowledgeSource,
    KnowledgeStatus,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = KnowledgeSynthesisManager()

        assert mgr.list_knowledge() == []
        assert mgr.get_stats()["node_count"] == 0
        assert mgr.get_stats()["edge_count"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = KnowledgeSynthesisManager(
            max_nodes=100,
            max_edges=500,
            min_confidence=0.6,
            conflict_resolution_mode="weighted",
        )

        assert mgr._max_nodes == 100
        assert mgr._max_edges == 500
        assert mgr._min_confidence == 0.6

    def test_context_manager(self):
        """上下文管理器应正确关闭。"""
        with KnowledgeSynthesisManager() as mgr:
            mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
            assert len(mgr.list_knowledge()) == 1


# =========================================================================
# 2. 知识节点管理
# =========================================================================

class TestKnowledgeNodeManagement:
    """知识节点管理测试。"""

    def test_add_knowledge(self):
        """添加知识节点。"""
        mgr = KnowledgeSynthesisManager()

        node = mgr.add_knowledge(
            content="OCOS 是数字生命体内核",
            knowledge_type=KnowledgeType.FACTUAL,
            source=KnowledgeSource.OBSERVATION,
            confidence=0.9,
        )

        assert node is not None
        assert node.content == "OCOS 是数字生命体内核"
        assert node.knowledge_type == KnowledgeType.FACTUAL
        assert node.confidence == 0.9

    def test_get_knowledge(self):
        """获取知识节点。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        retrieved = mgr.get_knowledge(node.node_id)
        assert retrieved is node

    def test_list_knowledge_by_type(self):
        """按类型列出知识。"""
        mgr = KnowledgeSynthesisManager()

        mgr.add_knowledge("fact1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_knowledge("proc1", KnowledgeType.PROCEDURAL, KnowledgeSource.LEARNING)
        mgr.add_knowledge("fact2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        factual = mgr.list_knowledge(knowledge_type=KnowledgeType.FACTUAL)
        assert len(factual) == 2
        assert all(n.knowledge_type == KnowledgeType.FACTUAL for n in factual)

    def test_update_confidence(self):
        """更新知识置信度。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.5)

        result = mgr.update_confidence(node.node_id, 0.8)
        assert result is True
        assert node.confidence == 0.8

    def test_deprecate_knowledge(self):
        """废弃知识节点。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        result = mgr.deprecate_knowledge(node.node_id)
        assert result is True
        assert node.status == KnowledgeStatus.DEPRECATED

    def test_add_knowledge_exceeds_limit(self):
        """超过最大节点数。"""
        mgr = KnowledgeSynthesisManager(max_nodes=2)

        mgr.add_knowledge("test1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_knowledge("test2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        result = mgr.add_knowledge("test3", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        assert result is None


# =========================================================================
# 3. 知识边管理
# =========================================================================

class TestKnowledgeEdgeManagement:
    """知识边管理测试。"""

    def test_add_edge(self):
        """添加知识边。"""
        mgr = KnowledgeSynthesisManager()
        node1 = mgr.add_knowledge("fact1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("fact2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        edge = mgr.add_edge(node1.node_id, node2.node_id, "supports")
        assert edge is not None
        assert edge.relation_type == "supports"

    def test_remove_edge(self):
        """移除知识边。"""
        mgr = KnowledgeSynthesisManager()
        node1 = mgr.add_knowledge("fact1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("fact2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        edge = mgr.add_edge(node1.node_id, node2.node_id, "supports")

        result = mgr.remove_edge(edge.edge_id)
        assert result is True

    def test_get_related_nodes(self):
        """获取关联知识节点。"""
        mgr = KnowledgeSynthesisManager()
        node1 = mgr.add_knowledge("fact1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("fact2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_edge(node1.node_id, node2.node_id, "supports")

        related = mgr.get_related_nodes(node1.node_id)
        assert len(related) == 1
        assert related[0].node_id == node2.node_id

    def test_add_edge_to_nonexistent_node(self):
        """向不存在的节点添加边。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.add_edge("nonexistent1", "nonexistent2", "test")
        assert result is None


# =========================================================================
# 4. 知识综合
# =========================================================================

class TestKnowledgeSynthesis:
    """知识综合测试。"""

    def test_synthesize_knowledge(self):
        """综合知识。"""
        mgr = KnowledgeSynthesisManager()

        node1 = mgr.add_knowledge("所有生命都需要水", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("OCOS 是生命体", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        result = mgr.synthesize_knowledge([node1.node_id, node2.node_id])
        assert result is not None
        assert len(result.new_knowledge) == 1
        assert result.confidence_score > 0

    def test_synthesize_invalid_nodes(self):
        """综合无效节点。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.synthesize_knowledge(["nonexistent"])
        assert result is None

    def test_synthesize_single_node(self):
        """单节点无法综合。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        result = mgr.synthesize_knowledge([node.node_id])
        assert result is None


# =========================================================================
# 5. 知识查询
# =========================================================================

class TestKnowledgeQuery:
    """知识查询测试。"""

    def test_query_by_keyword(self):
        """关键词查询。"""
        mgr = KnowledgeSynthesisManager()
        mgr.add_knowledge("OCOS 是数字生命体内核", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_knowledge("OpenTale 是小说生成系统", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        results = mgr.query_knowledge("OCOS")
        assert len(results) == 1
        assert "OCOS" in results[0].content

    def test_query_with_min_confidence(self):
        """带置信度过滤的查询。"""
        mgr = KnowledgeSynthesisManager()
        mgr.add_knowledge("high confidence", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.9)
        mgr.add_knowledge("low confidence", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.3)

        results = mgr.query_knowledge("", min_confidence=0.5)
        assert len(results) == 1
        assert results[0].confidence >= 0.5

    def test_query_no_match(self):
        """无匹配查询。"""
        mgr = KnowledgeSynthesisManager()
        results = mgr.query_knowledge("nonexistent")
        assert results == []


# =========================================================================
# 6. 路径查找
# =========================================================================

class TestPathFinding:
    """路径查找测试。"""

    def test_find_path(self):
        """查找知识路径。"""
        mgr = KnowledgeSynthesisManager()
        node1 = mgr.add_knowledge("A", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("B", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node3 = mgr.add_knowledge("C", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_edge(node1.node_id, node2.node_id, "leads_to")
        mgr.add_edge(node2.node_id, node3.node_id, "leads_to")

        path = mgr.find_path(node1.node_id, node3.node_id)
        assert path is not None
        assert path[0] == node1.node_id
        assert path[-1] == node3.node_id

    def test_find_path_no_connection(self):
        """查找无连接的路径。"""
        mgr = KnowledgeSynthesisManager()
        node1 = mgr.add_knowledge("A", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("B", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        path = mgr.find_path(node1.node_id, node2.node_id)
        assert path is None

    def test_find_path_to_nonexistent(self):
        """查找不存在的节点路径。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("A", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        path = mgr.find_path(node.node_id, "nonexistent")
        assert path is None


# =========================================================================
# 7. 质量评估
# =========================================================================

class TestKnowledgeQuality:
    """知识质量评估测试。"""

    def test_assess_quality(self):
        """评估知识质量。"""
        mgr = KnowledgeSynthesisManager()
        node = mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.8)

        quality = mgr.assess_knowledge_quality(node.node_id)
        assert "quality_score" in quality
        assert quality["confidence"] == 0.8

    def test_assess_nonexistent_knowledge(self):
        """评估不存在的知识。"""
        mgr = KnowledgeSynthesisManager()
        quality = mgr.assess_knowledge_quality("nonexistent")
        assert "error" in quality


# =========================================================================
# 8. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = KnowledgeSynthesisManager()
        stats = mgr.get_stats()

        assert "node_count" in stats
        assert "edge_count" in stats
        assert "knowledge_added" in stats

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = KnowledgeSynthesisManager()

        node1 = mgr.add_knowledge("test1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("test2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_edge(node1.node_id, node2.node_id, "related")

        stats = mgr.get_stats()
        assert stats["knowledge_added"] >= 1
        assert stats["edge_count"] >= 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = KnowledgeSynthesisManager()
        mgr.add_knowledge("test", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.reset_stats()

        stats = mgr.get_stats()
        assert stats["knowledge_added"] == 0


# =========================================================================
# 9. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_nodes_limit(self):
        """节点数量上限约束。"""
        mgr = KnowledgeSynthesisManager(max_nodes=2)

        mgr.add_knowledge("test1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_knowledge("test2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)

        result = mgr.add_knowledge("test3", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        assert result is None

    def test_max_edges_limit(self):
        """边数量上限约束。"""
        mgr = KnowledgeSynthesisManager(max_edges=1)

        node1 = mgr.add_knowledge("test1", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        node2 = mgr.add_knowledge("test2", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        mgr.add_edge(node1.node_id, node2.node_id, "related")

        node3 = mgr.add_knowledge("test3", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION)
        result = mgr.add_edge(node1.node_id, node3.node_id, "related")
        assert result is None


# =========================================================================
# 10. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_knowledge_workflow(self):
        """完整知识工作流。"""
        mgr = KnowledgeSynthesisManager()

        # 1. 添加基础知识
        fact1 = mgr.add_knowledge("所有生命都需要水", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.9)
        fact2 = mgr.add_knowledge("OCOS 是数字生命体", KnowledgeType.FACTUAL, KnowledgeSource.OBSERVATION, 0.85)

        # 2. 建立关联
        mgr.add_edge(fact1.node_id, fact2.node_id, "supports")

        # 3. 综合知识
        synthesis = mgr.synthesize_knowledge([fact1.node_id, fact2.node_id])
        assert synthesis is not None

        # 4. 查询知识
        results = mgr.query_knowledge("生命")
        assert len(results) >= 2

        # 5. 评估质量
        quality = mgr.assess_knowledge_quality(fact1.node_id)
        assert quality["quality_score"] > 0

        # 6. 查找路径
        path = mgr.find_path(fact1.node_id, fact2.node_id)
        assert path is not None

        # 7. 获取统计
        stats = mgr.get_stats()
        assert stats["node_count"] >= 2
        assert stats["edge_count"] >= 1


# =========================================================================
# 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_get_nonexistent_knowledge(self):
        """获取不存在的知识。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.get_knowledge("nonexistent")
        assert result is None

    def test_deprecate_nonexistent_knowledge(self):
        """废弃不存在的知识。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.deprecate_knowledge("nonexistent")
        assert result is False

    def test_update_nonexistent_confidence(self):
        """更新不存在的知识置信度。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.update_confidence("nonexistent", 0.8)
        assert result is False

    def test_remove_nonexistent_edge(self):
        """移除不存在的边。"""
        mgr = KnowledgeSynthesisManager()
        result = mgr.remove_edge("nonexistent")
        assert result is False
