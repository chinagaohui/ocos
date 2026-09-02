"""Phase S: KnowledgeGraphManager — 知识图谱管理器。

整合：
- KnowledgeGraph: 核心图结构（已有）
- 从交互中学习实体关系（需 NER/RE 提取器）
- 知识推理和更新
- 持久化（可选）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .graph import (
    KnowledgeGraph,
    Entity,
    Relation,
    Fact,
    EntityType,
    RelationType,
    _make_id,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """NER/RE 提取结果。"""
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5


class KnowledgeGraphManager:
    """Phase S: 知识图谱管理器。

    职责：
    - 维护用户知识图谱
    - 从交互中提取实体关系（需注入提取器）
    - 知识更新和冲突解决
    - 推理和查询
    """

    def __init__(
        self,
        extractor: Optional[Callable[[str], ExtractionResult]] = None,
    ) -> None:
        self._graph = KnowledgeGraph()
        self._extractor = extractor
        self._history: list[dict[str, Any]] = []
        self._max_history = 500
        self._started_at = time.time()

    @property
    def graph(self) -> KnowledgeGraph:
        return self._graph

    # ── Public API ───────────────────────────────────────────────────────

    def learn_from_text(self, text: str) -> ExtractionResult:
        """从文本学习实体关系。"""
        if self._extractor is None:
            return ExtractionResult(confidence=0.0)
        result = self._extractor(text)
        self._apply_extraction(result)
        return result

    def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        properties: Optional[dict[str, Any]] = None,
        confidence: float = 0.8,
    ) -> str:
        """添加实体并返回 entity_id。"""
        entity_id = _make_id("E-")
        entity = Entity(
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
            properties=properties or {},
            confidence=confidence,
        )
        self._graph.add_entity(entity)
        self._record_action("add_entity", {"entity_id": entity_id, "name": name})
        return entity_id

    def add_relation(
        self,
        subject_id: str,
        predicate: RelationType,
        object_id: str,
        confidence: float = 0.7,
    ) -> str:
        """添加关系并返回 relation_id。"""
        relation_id = _make_id("R-")
        relation = Relation(
            relation_id=relation_id,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            confidence=confidence,
        )
        self._graph.add_relation(relation)
        self._record_action("add_relation", {
            "relation_id": relation_id,
            "subject": subject_id,
            "predicate": predicate.name,
            "object": object_id,
        })
        return relation_id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._graph.get_entity(entity_id)

    def get_neighbors(self, entity_id: str) -> list[tuple[str, Relation]]:
        return self._graph.neighbors(entity_id)

    def get_inferred_relations(self, entity_id: str, depth: int = 2) -> list[tuple[str, Relation]]:
        return self._graph.infer_relations(entity_id, depth)

    def search_entities(self, query: str, entity_type: Optional[EntityType] = None) -> list[Entity]:
        """搜索实体。"""
        return self._graph.find_by_name(query, entity_type)

    def resolve_entity(self, name: str, entity_type: Optional[EntityType] = None) -> Optional[str]:
        return self._graph.resolve_entity(name, entity_type)

    def get_stats(self) -> dict[str, Any]:
        stats = self._graph.get_stats()
        stats["uptime_seconds"] = time.time() - self._started_at
        stats["recent_actions"] = self._history[-10:]
        return stats

    def generate_report(self) -> str:
        """生成知识图谱报告。"""
        stats = self.get_stats()
        lines = [
            "=" * 50,
            "知识图谱报告",
            "=" * 50,
            f"实体数: {stats['entity_count']}",
            f"关系数: {stats['relation_count']}",
            f"活跃事实: {stats['active_facts']}",
            f"平均置信度: {stats['avg_confidence']:.2f}",
            "",
            "实体类型分布:",
        ]
        for type_name, count in sorted(stats["entity_types"].items()):
            lines.append(f"  {type_name}: {count}")
        lines.append("")
        lines.append(f"运行时长: {stats['uptime_seconds']:.1f}秒")
        lines.append("=" * 50)
        return "\n".join(lines)

    def export(self) -> str:
        return self._graph.export_json()

    def clear(self) -> None:
        self._graph.clear()
        self._history.clear()

    # ── Internal ────────────────────────────────────────────────────────

    def _apply_extraction(self, result: ExtractionResult) -> None:
        """应用提取结果到图谱。"""
        for ent_data in result.entities:
            name = ent_data.get("name", "")
            etype_str = ent_data.get("type", "CONCEPT")
            try:
                etype = EntityType[etype_str.upper()]
            except KeyError:
                etype = EntityType.CONCEPT
            conf = ent_data.get("confidence", 0.7)
            props = ent_data.get("properties", {})
            self.add_entity(name, etype, props, conf)

        for rel_data in result.relations:
            subj = self._resolve_or_create(rel_data.get("subject", ""))
            obj = self._resolve_or_create(rel_data.get("object", ""))
            pred_str = rel_data.get("predicate", "RELATED_TO")
            try:
                pred = RelationType[pred_str.upper()]
            except KeyError:
                pred = RelationType.RELATED_TO
            conf = rel_data.get("confidence", 0.6)
            self.add_relation(subj, pred, obj, conf)

        self._record_action("extraction", {
            "entities": len(result.entities),
            "relations": len(result.relations),
            "confidence": result.confidence,
        })

    def _resolve_or_create(self, name: str) -> str:
        """解析或创建实体。"""
        if not name:
            return _make_id("UNK-")
        existing = self.resolve_entity(name)
        if existing:
            return existing
        return self.add_entity(name, EntityType.CONCEPT)

    def _record_action(self, action: str, data: dict[str, Any]) -> None:
        self._history.append({
            "timestamp": time.time(),
            "action": action,
            **data,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
