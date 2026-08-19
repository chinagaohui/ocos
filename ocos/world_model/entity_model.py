"""Phase 42: EntityModel — 实体定义与生命周期。

世界中有什么实体，它们何时被创建/更新/移除。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.world_model.world_types import Entity, EntityType, WorldEvent, WorldEventType


@dataclass
class EntityModel:
    """实体模型 — 管理世界中的所有实体。"""

    _entities: dict[str, Entity] = field(default_factory=dict)

    # ── CRUD ──

    def create_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: EntityType,
        description: str = "",
        confidence: float = 1.0,
        tick: int = 0,
    ) -> Entity:
        if entity_id in self._entities:
            raise ValueError(f"Entity {entity_id} already exists")
        entity = Entity(
            entity_id=entity_id,
            name=name,
            entity_type=entity_type,
            description=description,
            confidence=confidence,
            created_tick=tick,
        )
        self._entities[entity_id] = entity
        return entity

    def get(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def get_by_type(self, entity_type: EntityType) -> list[Entity]:
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def list_all(self) -> list[Entity]:
        return list(self._entities.values())

    def exists(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def remove(self, entity_id: str, tick: int = 0) -> Optional[Entity]:
        """移除实体，返回被移除的实体或 None。"""
        if entity_id in self._entities:
            entity = self._entities.pop(entity_id)
            return entity
        return None

    @property
    def count(self) -> int:
        return len(self._entities)

    @property
    def type_distribution(self) -> dict[EntityType, int]:
        dist: dict[EntityType, int] = {}
        for e in self._entities.values():
            dist[e.entity_type] = dist.get(e.entity_type, 0) + 1
        return dist


__all__ = ["EntityModel"]
