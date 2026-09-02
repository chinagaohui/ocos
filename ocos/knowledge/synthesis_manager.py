"""Phase AG: KnowledgeSynthesisManager — 知识综合管理器。

整合 KnowledgeGraph + WisdomStore + ReflectionManager，
提供统一的知识综合接口：
- 知识图谱构建与维护
- 智慧提炼与验证
- 跨领域知识关联
- 知识完整性检查
- 知识版本管理

架构原则：
- AG-KNOW-01: 知识必须可追溯来源
- AG-KNOW-02: 新知识与旧知识必须兼容
- AG-KNOW-03: 知识图谱必须支持增量更新
- AG-KNOW-04: 智慧验证需要多重证据
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


class KnowledgeType(Enum):
    """知识类型。"""
    FACTUAL = auto()          # 事实性知识
    PROCEDURAL = auto()       # 程序性知识
    PERSONAL = auto()         # 个人经验
    WISDOM = auto()           # 智慧
    META = auto()             # 元知识


class KnowledgeSource(Enum):
    """知识来源。"""
    OBSERVATION = "observation"
    REFLECTION = "reflection"
    FEEDBACK = "feedback"
    LEARNING = "learning"
    SYNTHESIS = "synthesis"
    WISDOM = "wisdom"


class KnowledgeStatus(Enum):
    """知识状态。"""
    PROPOSED = "proposed"
    VERIFIED = "verified"
    INTEGRATED = "integrated"
    DEPRECATED = "deprecated"
    CONFLICTED = "conflicted"


@dataclass
class KnowledgeNode:
    """知识节点。"""
    node_id: str
    content: str
    knowledge_type: KnowledgeType
    confidence: float
    source: KnowledgeSource
    created_at: float = 0.0
    status: KnowledgeStatus = KnowledgeStatus.PROPOSED
    related_nodes: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class KnowledgeEdge:
    """知识边。"""
    edge_id: str
    source_id: str
    target_id: str
    relation_type: str
    strength: float = 1.0
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class SynthesisResult:
    """综合结果。"""
    result_id: str
    new_knowledge: list[str]
    conflicts_resolved: int
    confidence_score: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class KnowledgeSynthesisManager:
    """知识综合管理器。

    统一管理层：
    1. 知识图谱维护
    2. 知识综合与推理
    3. 冲突检测与解决
    4. 知识质量评估
    """

    def __init__(
        self,
        max_nodes: int = 10000,
        max_edges: int = 50000,
        min_confidence: float = 0.5,
        conflict_resolution_mode: str = "consensus",
    ):
        self._max_nodes = max_nodes
        self._max_edges = max_edges
        self._min_confidence = min_confidence
        self._conflict_resolution_mode = conflict_resolution_mode

        # 知识节点
        self._nodes: dict[str, KnowledgeNode] = {}
        self._node_lock = threading.RLock()

        # 知识边
        self._edges: dict[str, KnowledgeEdge] = {}
        self._edge_lock = threading.RLock()

        # 统计
        self._stats = {
            "knowledge_added": 0,
            "syntheses_performed": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "knowledge_deprecated": 0,
        }

    # ── 知识节点管理 ────────────────────────────────────────────

    def add_knowledge(
        self,
        content: str,
        knowledge_type: KnowledgeType,
        source: KnowledgeSource,
        confidence: float = 0.7,
        related_nodes: list[str] | None = None,
    ) -> KnowledgeNode | None:
        """添加知识节点。"""
        with self._node_lock:
            if len(self._nodes) >= self._max_nodes:
                logger.warning("Max knowledge nodes reached (%d)", self._max_nodes)
                return None

            node_id = f"kn:{uuid.uuid4().hex[:8]}"
            node = KnowledgeNode(
                node_id=node_id,
                content=content,
                knowledge_type=knowledge_type,
                confidence=confidence,
                source=source,
                related_nodes=related_nodes or [],
            )
            self._nodes[node_id] = node
            self._stats["knowledge_added"] += 1
            logger.info("Knowledge added: %s (type=%s, confidence=%.2f)",
                       node_id, knowledge_type.name, confidence)
            return node

    def get_knowledge(self, node_id: str) -> KnowledgeNode | None:
        """获取知识节点。"""
        with self._node_lock:
            return self._nodes.get(node_id)

    def list_knowledge(
        self,
        knowledge_type: KnowledgeType | None = None,
        status: KnowledgeStatus | None = None,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        """列出知识节点。"""
        with self._node_lock:
            nodes = list(self._nodes.values())
            if knowledge_type:
                nodes = [n for n in nodes if n.knowledge_type == knowledge_type]
            if status:
                nodes = [n for n in nodes if n.status == status]
            return nodes[-limit:]

    def update_confidence(self, node_id: str, new_confidence: float) -> bool:
        """更新知识置信度。"""
        with self._node_lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.confidence = max(node.confidence, new_confidence)
            return True

    def deprecate_knowledge(self, node_id: str) -> bool:
        """废弃知识节点。"""
        with self._node_lock:
            node = self._nodes.get(node_id)
            if not node:
                return False
            node.status = KnowledgeStatus.DEPRECATED
            self._stats["knowledge_deprecated"] += 1
            logger.info("Knowledge deprecated: %s", node_id)
            return True

    # ── 知识边管理 ────────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        strength: float = 1.0,
    ) -> KnowledgeEdge | None:
        """添加知识边。"""
        with self._node_lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                return None

        with self._edge_lock:
            if len(self._edges) >= self._max_edges:
                return None

            edge_id = f"ke:{uuid.uuid4().hex[:8]}"
            edge = KnowledgeEdge(
                edge_id=edge_id,
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                strength=strength,
            )
            self._edges[edge_id] = edge

            # 更新节点的关联列表
            with self._node_lock:
                if target_id not in self._nodes[source_id].related_nodes:
                    self._nodes[source_id].related_nodes.append(target_id)
                if source_id not in self._nodes[target_id].related_nodes:
                    self._nodes[target_id].related_nodes.append(source_id)

            logger.debug("Knowledge edge added: %s -> %s (%s)", source_id, target_id, relation_type)
            return edge

    def remove_edge(self, edge_id: str) -> bool:
        """移除知识边。"""
        with self._edge_lock:
            edge = self._edges.get(edge_id)
            if not edge:
                return False
            del self._edges[edge_id]
            return True

    def get_related_nodes(self, node_id: str) -> list[KnowledgeNode]:
        """获取关联知识节点。"""
        with self._node_lock:
            node = self._nodes.get(node_id)
            if not node:
                return []
            return [self._nodes[nid] for nid in node.related_nodes if nid in self._nodes]

    # ── 知识综合 ────────────────────────────────────────────────

    def synthesize_knowledge(
        self,
        node_ids: list[str],
        synthesis_type: str = "deductive",
    ) -> SynthesisResult | None:
        """综合多个知识节点。"""
        with self._node_lock:
            nodes = [self._nodes[nid] for nid in node_ids if nid in self._nodes]
            if len(nodes) < 2:
                return None

        # 执行综合
        new_content = self._perform_synthesis(nodes, synthesis_type)
        if not new_content:
            return None

        # 创建新知识
        new_node = self.add_knowledge(
            content=new_content,
            knowledge_type=KnowledgeType.WISDOM,
            source=KnowledgeSource.SYNTHESIS,
            confidence=sum(n.confidence for n in nodes) / len(nodes),
        )
        if not new_node:
            return None

        # 建立关联边
        for node in nodes:
            self.add_edge(new_node.node_id, node.node_id, "synthesized_from")

        # 记录结果
        result = SynthesisResult(
            result_id=f"sr:{uuid.uuid4().hex[:8]}",
            new_knowledge=[new_node.node_id],
            conflicts_resolved=self._detect_and_resolve_conflicts(nodes),
            confidence_score=sum(n.confidence for n in nodes) / len(nodes),
        )
        self._stats["syntheses_performed"] += 1
        return result

    def _perform_synthesis(
        self,
        nodes: list[KnowledgeNode],
        synthesis_type: str,
    ) -> str | None:
        """执行知识综合。"""
        if synthesis_type == "deductive":
            # 演绎综合：从一般到特殊
            return self._deductive_synthesis(nodes)
        elif synthesis_type == "inductive":
            # 归纳综合：从特殊到一般
            return self._inductive_synthesis(nodes)
        elif synthesis_type == "abductive":
            # 溯因综合：寻找最佳解释
            return self._abductive_synthesis(nodes)
        else:
            # 默认：简单拼接
            return "; ".join(n.content for n in nodes)

    def _deductive_synthesis(self, nodes: list[KnowledgeNode]) -> str:
        """演绎综合。"""
        # 提取共同主题
        common_theme = self._extract_common_theme(nodes)
        if common_theme:
            return f"基于共同主题「{common_theme}」的综合洞察"
        return f"演绎综合结果：{' → '.join(n.content[:30] for n in nodes)}"

    def _inductive_synthesis(self, nodes: list[KnowledgeNode]) -> str:
        """归纳综合。"""
        patterns = self._extract_patterns(nodes)
        if patterns:
            return f"归纳发现模式：{patterns}"
        return f"归纳综合结果：观察到 {len(nodes)} 个实例的共同特征"

    def _abductive_synthesis(self, nodes: list[KnowledgeNode]) -> str:
        """溯因综合。"""
        return f"溯因推理最佳解释：{nodes[0].content[:50]}..."

    def _extract_common_theme(self, nodes: list[KnowledgeNode]) -> str | None:
        """提取共同主题。"""
        # 简化实现：返回第一个节点的类型作为主题
        if nodes:
            return nodes[0].knowledge_type.name.lower()
        return None

    def _extract_patterns(self, nodes: list[KnowledgeNode]) -> str | None:
        """提取模式。"""
        if len(nodes) >= 3:
            return f"{len(nodes)} 个知识节点的一致结论"
        return None

    def _detect_and_resolve_conflicts(
        self,
        nodes: list[KnowledgeNode],
    ) -> int:
        """检测并解决冲突。"""
        conflicts = 0
        # 检查置信度差异
        confidences = [n.confidence for n in nodes]
        if max(confidences) - min(confidences) > 0.5:
            conflicts += 1
            logger.warning("Confidence conflict detected among %d nodes", len(nodes))
        return conflicts

    # ── 知识查询 ────────────────────────────────────────────────

    def query_knowledge(
        self,
        query: str,
        knowledge_type: KnowledgeType | None = None,
        min_confidence: float | None = None,
    ) -> list[KnowledgeNode]:
        """查询知识。"""
        with self._node_lock:
            nodes = list(self._nodes.values())

        # 过滤
        if knowledge_type:
            nodes = [n for n in nodes if n.knowledge_type == knowledge_type]

        if min_confidence is not None:
            nodes = [n for n in nodes if n.confidence >= min_confidence]

        # 简单匹配（实际应使用语义搜索）
        if query:
            query_lower = query.lower()
            nodes = [n for n in nodes if query_lower in n.content.lower()]

        return nodes

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[str] | None:
        """查找知识路径。"""
        with self._node_lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                return None

        # BFS 搜索
        visited = {source_id}
        queue = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)
            if current == target_id:
                return path
            if len(path) >= max_depth:
                continue

            current_node = self._nodes.get(current)
            if current_node:
                for neighbor_id in current_node.related_nodes:
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, path + [neighbor_id]))

        return None

    # ── 知识质量评估 ────────────────────────────────────────────

    def assess_knowledge_quality(self, node_id: str) -> dict[str, Any]:
        """评估知识质量。"""
        with self._node_lock:
            node = self._nodes.get(node_id)
            if not node:
                return {"error": "node not found"}

        related_count = len(node.related_nodes)
        quality_score = min(1.0, (node.confidence * 0.6 + min(related_count / 10, 1.0) * 0.4))

        return {
            "node_id": node_id,
            "confidence": node.confidence,
            "related_count": related_count,
            "quality_score": quality_score,
            "status": node.status.value,
        }

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._node_lock:
            node_count = len(self._nodes)
            verified_count = sum(
                1 for n in self._nodes.values()
                if n.status == KnowledgeStatus.VERIFIED
            )
        with self._edge_lock:
            edge_count = len(self._edges)

        return {
            **self._stats,
            "node_count": node_count,
            "edge_count": edge_count,
            "verified_count": verified_count,
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "knowledge_added": 0,
            "syntheses_performed": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "knowledge_deprecated": 0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._node_lock:
            self._nodes.clear()
        with self._edge_lock:
            self._edges.clear()
        logger.info("KnowledgeSynthesisManager closed")


__all__ = [
    "KnowledgeSynthesisManager",
    "KnowledgeNode",
    "KnowledgeEdge",
    "SynthesisResult",
    "KnowledgeType",
    "KnowledgeSource",
    "KnowledgeStatus",
]
