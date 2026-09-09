"""Phase S: KnowledgeGraph — 用户知识图谱。

与 ocos/capability/knowledge_graph.py（能力图谱）区分：
- CapabilityKG: 系统能力/提供者/经验
- UserKG: 用户世界模型（实体/关系/事实）

核心能力：
- 实体管理：创建/查询/合并/消歧
- 关系管理：三元组存储/查询/推理
- 置信度：基于证据来源的多信度融合
- 时序：事实的有效期和版本历史
- 持久化：JSON/SQLite 可选
- 学习闭环：从交互中提取实体关系（需外部提取器）
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """实体类型。"""
    PERSON = auto()
    ORGANIZATION = auto()
    LOCATION = auto()
    CONCEPT = auto()
    EVENT = auto()
    OBJECT = auto()
    PREFERENCE = auto()
    GOAL = auto()


class RelationType(Enum):
    """关系类型。"""
    IS_A = auto()
    PART_OF = auto()
    RELATED_TO = auto()
    CAUSES = auto()
    PREFER = auto()
    KNOWS = auto()
    WORKS_AT = auto()
    LIVES_IN = auto()
    BELIEVES = auto()
    HAS_GOAL = auto()


@dataclass
class Entity:
    """知识图谱实体。"""
    entity_id: str
    name: str
    entity_type: EntityType
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_count: int = 1

    def update_confidence(self, new_confidence: float, weight: float = 0.3) -> None:
        """加权更新置信度。"""
        self.confidence = (1 - weight) * self.confidence + weight * new_confidence
        self.source_count += 1
        self.updated_at = time.time()


@dataclass
class Relation:
    """知识图谱关系（三元组）。"""
    relation_id: str
    subject_id: str
    predicate: RelationType
    object_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    source_count: int = 1

    def update_confidence(self, new_confidence: float, weight: float = 0.3) -> None:
        self.confidence = (1 - weight) * self.confidence + weight * new_confidence
        self.source_count += 1
        self.created_at = min(self.created_at, time.time())


@dataclass
class Fact:
    """带时间戳的事实（支持失效）。"""
    fact_id: str
    subject_id: str
    predicate: RelationType
    object_id: str
    valid_from: float
    valid_until: Optional[float] = None
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        if self.valid_until is None:
            return True
        return time.time() <= self.valid_until


class KnowledgeGraph:
    """Phase S: 用户知识图谱。

    支持实体和关系的CRUD、查询、推理、置信度管理。
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}
        self._facts: list[Fact] = []

        # 索引
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming: dict[str, list[str]] = defaultdict(list)
        self._by_type: dict[EntityType, set[str]] = defaultdict(set)
        self._by_name: dict[str, list[str]] = defaultdict(list)

        # GAP-P2-1: 持久化支持 — 绑定 SemanticStore 后 entities/relations/facts 自动同步
        self._semantic_store: Optional[Any] = None

    def bind_semantic(self, semantic_store: Any) -> None:
        """绑定 SemanticStore — 让 KnowledgeGraph 状态能持久化到同一个 ocos.db.

        实现: 把 entities/relations/facts 序列化存为一个特殊 KnowledgeEntry
        (id="knowledge_graph_state")，下次启动能 load_from_semantic 恢复。
        """
        self._semantic_store = semantic_store
        try:
            self.load_from_semantic()
        except Exception:
            pass  # 首次启动没有持久化数据，静默跳过

    def persist_to_semantic(self) -> None:
        """把当前 Graph 状态存到 SemanticStore（一条 KnowledgeEntry）."""
        if self._semantic_store is None:
            return
        try:
            from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeScope
            import json as _json
            payload = _json.dumps({
                "entities": [
                    {"id": e.entity_id, "name": e.name, "type": e.entity_type.name,
                     "confidence": e.confidence}
                    for e in self._entities.values()
                ],
                "relations": [
                    {"id": r.relation_id, "from": r.subject_id, "to": r.object_id,
                     "type": r.predicate.name, "confidence": r.confidence}
                    for r in self._relations.values()
                ],
                "facts": [
                    {"subject": f.subject, "relation": f.relation, "obj": f.obj,
                     "confidence": f.confidence}
                    for f in self._facts
                ],
            }, ensure_ascii=False)
            # P2-4: 把 JSON payload 存 scope.limitations 里（scope 是 KnowledgeScope 对象）
            scope = KnowledgeScope(
                domain="graph_state",
                limitations=(payload[:5000],),  # limitations tuple 里塞 JSON payload（简化方案）
            )
            entry = KnowledgeEntry.create(
                statement=f"KnowledgeGraph: {len(self._entities)} entities, "
                         f"{len(self._relations)} relations, {len(self._facts)} facts",
                source_patterns=("knowledge_graph_state",),
                confidence=1.0,
                scope=scope,
                stability=0.9,
            )
            self._semantic_store.save(entry)
        except Exception:
            pass  # persist 失败不阻塞

    def load_from_semantic(self) -> None:
        """从 SemanticStore 恢复 Graph 状态（反序列化 persist_to_semantic 存的 JSON payload）."""
        if self._semantic_store is None:
            return
        try:
            from ocos.memory.semantic.models import KnowledgeStatus
            entries = self._semantic_store.query_by_lineage(
                source_patterns=("knowledge_graph_state",),
                limit=10,
            )
            if not entries:
                return
            import json as _json
            latest = entries[-1]
            # P2-4: JSON payload 存 scope.limitations[0]
            limitations = getattr(latest.scope, 'limitations', ()) if hasattr(latest, 'scope') else ()
            if not limitations:
                return
            payload_str = limitations[0]
            try:
                payload = _json.loads(payload_str)
            except Exception:
                return  # 老版本没有 JSON payload
            for ent_data in payload.get("entities", []):
                from ocos.knowledge.graph import Entity, EntityType
                try:
                    etype = EntityType(ent_data.get("type", "CONCEPT"))
                except ValueError:
                    etype = EntityType.CONCEPT
                self.add_entity(Entity(
                    entity_id=ent_data["id"], name=ent_data["name"],
                    entity_type=etype, confidence=ent_data.get("confidence", 1.0),
                ))
            for rel_data in payload.get("relations", []):
                from ocos.knowledge.graph import Relation, RelationType
                try:
                    rtype = RelationType(rel_data.get("type", "PART_OF"))
                except ValueError:
                    rtype = RelationType.PART_OF
                self.add_relation(Relation(
                    relation_id=rel_data["id"],
                    subject_id=rel_data["from"], predicate=rtype,
                    object_id=rel_data["to"], confidence=rel_data.get("confidence", 1.0),
                ))
        except Exception:
            pass  # load 失败静默跳过

    # ── Entity API ───────────────────────────────────────────────────────

    def add_entity(self, entity: Entity) -> None:
        """添加实体。"""
        self._entities[entity.entity_id] = entity
        self._by_type[entity.entity_type].add(entity.entity_id)
        self._by_name[entity.name.lower()].append(entity.entity_id)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def find_by_name(self, name: str, entity_type: Optional[EntityType] = None) -> list[Entity]:
        """按名称查找（模糊匹配）。"""
        candidates = self._by_name.get(name.lower(), [])
        if entity_type is None:
            return [self._entities[eid] for eid in candidates if eid in self._entities]
        return [
            self._entities[eid] for eid in candidates
            if eid in self._entities and self._entities[eid].entity_type == entity_type
        ]

    def resolve_entity(self, name: str, entity_type: Optional[EntityType] = None) -> Optional[str]:
        """实体消歧：返回最可能的 entity_id。"""
        matches = self.find_by_name(name, entity_type)
        if not matches:
            return None
        # 按置信度和更新频率排序
        return max(matches, key=lambda e: (e.confidence, -e.updated_at)).entity_id

    def remove_entity(self, entity_id: str) -> bool:
        if entity_id not in self._entities:
            return False
        entity = self._entities.pop(entity_id)
        self._by_type[entity.entity_type].discard(entity_id)
        self._outgoing.pop(entity_id, None)
        self._incoming.pop(entity_id, None)
        return True

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        return [self._entities[eid] for eid in self._by_type.get(entity_type, set()) if eid in self._entities]

    # ── Relation API ─────────────────────────────────────────────────────

    def add_relation(self, relation: Relation) -> None:
        """添加关系。"""
        self._relations[relation.relation_id] = relation
        self._outgoing[relation.subject_id].append(relation.relation_id)
        self._incoming[relation.object_id].append(relation.relation_id)

    def get_relation(self, relation_id: str) -> Optional[Relation]:
        return self._relations.get(relation_id)

    def outgoing(self, entity_id: str) -> list[Relation]:
        return [self._relations[rid] for rid in self._outgoing.get(entity_id, []) if rid in self._relations]

    def incoming(self, entity_id: str) -> list[Relation]:
        return [self._relations[rid] for rid in self._incoming.get(entity_id, []) if rid in self._relations]

    def neighbors(self, entity_id: str) -> list[tuple[str, Relation]]:
        result = []
        for rel in self.outgoing(entity_id):
            result.append((rel.object_id, rel))
        for rel in self.incoming(entity_id):
            result.append((rel.subject_id, rel))
        return result

    def find_relations(
        self,
        subject_id: Optional[str] = None,
        predicate: Optional[RelationType] = None,
        object_id: Optional[str] = None,
    ) -> list[Relation]:
        """按条件过滤关系。"""
        results = []
        for rel in self._relations.values():
            if subject_id and rel.subject_id != subject_id:
                continue
            if predicate and rel.predicate != predicate:
                continue
            if object_id and rel.object_id != object_id:
                continue
            results.append(rel)
        return results

    def infer_relations(self, entity_id: str, depth: int = 2) -> list[tuple[str, Relation]]:
        """BFS 推断间接关系。"""
        visited = {entity_id}
        queue = [(entity_id, 0)]
        results = []
        while queue:
            current, d = queue.pop(0)
            if d >= depth:
                continue
            for rel in self.outgoing(current):
                if rel.object_id not in visited:
                    visited.add(rel.object_id)
                    results.append((rel.object_id, rel))
                    queue.append((rel.object_id, d + 1))
        return results

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    # ── Fact API ─────────────────────────────────────────────────────────

    def add_fact(self, fact: Fact) -> None:
        self._facts.append(fact)

    def get_active_facts(self) -> list[Fact]:
        return [f for f in self._facts if f.is_active]

    def get_facts_for_entity(self, entity_id: str) -> list[Fact]:
        return [f for f in self._facts if f.subject_id == entity_id and f.is_active]

    # ── Statistics ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        type_counts = {t.name: len(eids) for t, eids in self._by_type.items()}
        active_facts = len(self.get_active_facts())
        return {
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "active_facts": active_facts,
            "entity_types": type_counts,
            "avg_confidence": (
                sum(e.confidence for e in self._entities.values()) / max(1, self.entity_count)
            ),
        }

    def export_json(self) -> str:
        return json.dumps({
            "entities": [
                {
                    "id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type.name,
                    "properties": e.properties,
                    "confidence": e.confidence,
                }
                for e in self._entities.values()
            ],
            "relations": [
                {
                    "id": r.relation_id,
                    "subject": r.subject_id,
                    "predicate": r.predicate.name,
                    "object": r.object_id,
                    "confidence": r.confidence,
                }
                for r in self._relations.values()
            ],
        }, ensure_ascii=False, indent=2)

    def clear(self) -> None:
        self._entities.clear()
        self._relations.clear()
        self._facts.clear()
        self._outgoing.clear()
        self._incoming.clear()
        self._by_type.clear()
        self._by_name.clear()


def _make_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}" if prefix else uuid.uuid4().hex[:8]
