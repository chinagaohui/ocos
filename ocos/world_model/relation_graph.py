"""Phase 42: RelationGraph — 实体关系图。

描述实体之间的连接方式:
    - depends_on, competes_with, contains, supports, opposes, etc.
    - 支持路径查询和邻居发现
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

from ocos.world_model.world_types import Relation, RelationType


@dataclass
class RelationGraph:
    """实体间有向关系图。

    每个关系是 from —[type]→ to 的三元组。
    """

    _relations: dict[str, Relation] = field(default_factory=dict)
    # 快速索引: entity_id → [relation_ids]
    _outgoing: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    _incoming: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # ── CRUD ──

    def add_relation(self, relation: Relation) -> None:
        if relation.relation_id in self._relations:
            raise ValueError(f"Relation {relation.relation_id} already exists")
        self._relations[relation.relation_id] = relation
        self._outgoing[relation.from_entity_id].append(relation.relation_id)
        self._incoming[relation.to_entity_id].append(relation.relation_id)

    def get(self, relation_id: str) -> Optional[Relation]:
        return self._relations.get(relation_id)

    def remove(self, relation_id: str) -> Optional[Relation]:
        if relation_id not in self._relations:
            return None
        rel = self._relations.pop(relation_id)
        self._outgoing[rel.from_entity_id].remove(relation_id)
        self._incoming[rel.to_entity_id].remove(relation_id)
        return rel

    # ── 查询 ──

    def outgoing(self, entity_id: str) -> list[Relation]:
        """从该实体出发的关系。"""
        return [self._relations[rid] for rid in self._outgoing.get(entity_id, [])]

    def incoming(self, entity_id: str) -> list[Relation]:
        """指向该实体的关系。"""
        return [self._relations[rid] for rid in self._incoming.get(entity_id, [])]

    def neighbors(self, entity_id: str) -> list[tuple[str, Relation]]:
        """返回所有邻居及关系。"""
        result = []
        for rel in self.outgoing(entity_id):
            result.append((rel.to_entity_id, rel))
        for rel in self.incoming(entity_id):
            result.append((rel.from_entity_id, rel))
        return result

    def find_by_type(
        self,
        from_id: str = "",
        to_id: str = "",
        rel_type: RelationType | None = None,
    ) -> list[Relation]:
        """按条件过滤关系。"""
        results = []
        for rel in self._relations.values():
            if from_id and rel.from_entity_id != from_id:
                continue
            if to_id and rel.to_entity_id != to_id:
                continue
            if rel_type and rel.relation_type != rel_type:
                continue
            results.append(rel)
        return results

    def causal_relations(self, entity_id: str = "") -> list[Relation]:
        """查找因果/影响关系。"""
        rels = self.outgoing(entity_id) if entity_id else list(self._relations.values())
        return [r for r in rels if r.relation_type.is_causal]

    @property
    def count(self) -> int:
        return len(self._relations)

    @property
    def list_all(self) -> list[Relation]:
        return list(self._relations.values())


__all__ = ["RelationGraph"]
