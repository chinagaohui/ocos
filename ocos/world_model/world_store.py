"""Phase 42: WorldStore — 世界模型持久化与查询中心。

整合所有 World Model 组件:
    EntityModel + RelationGraph + StateTracker + EventModel + CausalityEngine

数据流:
    External Observation
        ↓
    WorldValidator        ← WM42-04 输入治理
        ↓
    WorldStore.update()
        ↓
    Entity / Relation / State / Event / Causality

约束:
    - 不产生 Belief（WM42-02）
    - 不产生 Goal（WM42-03）
    - 不存储 knowledge documents（WM42-01）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ocos.world_model.world_types import (
    Entity, EntityType, EntityState, Relation, RelationType,
    WorldEvent, WorldEventType, CausalityLink, Observation,
)
from ocos.world_model.entity_model import EntityModel
from ocos.world_model.relation_graph import RelationGraph
from ocos.world_model.state_tracker import StateTracker
from ocos.world_model.event_model import EventModel
from ocos.world_model.causality_engine import CausalityEngine
from ocos.world_model.world_validator import (
    WorldValidator, ValidationDecision, ValidationResult,
)


@dataclass
class WorldStore:
    """世界模型统一存储 — WC 世界观查询入口。

    所有写入经过 WorldValidator 治理。
    不暴露直接写入 API — 必须通过 update_from_observation()。
    """

    entities: EntityModel = field(default_factory=EntityModel)
    relations: RelationGraph = field(default_factory=RelationGraph)
    states: StateTracker = field(default_factory=StateTracker)
    events: EventModel = field(default_factory=EventModel)
    causality: CausalityEngine = field(default_factory=CausalityEngine)
    validator: WorldValidator = field(default_factory=WorldValidator)

    # 内部 tick 计数器
    _tick: int = 0

    # ── 模型源（用于因果推断）──

    def _next_tick(self) -> int:
        self._tick += 1
        return self._tick

    # ── 观察 → 验证 → 更新 ──

    def update_from_observation(
        self,
        observation: Observation,
    ) -> ValidationResult:
        """从外部观察更新世界模型（唯一的写入路径）。

        外部 Agent 通过 Observation 提交数据，
        经过 WorldValidator 验证后才进入世界模型。
        """
        # Step 1: 验证
        result = self.validator.validate_observation(observation)
        if not result.accepted:
            return result

        # Step 2: 记录观察事件
        tick = observation.tick_id or self._next_tick()
        self.events.record(WorldEvent(
            event_id=f"obs:{observation.observation_id}",
            event_type=WorldEventType.OBSERVATION,
            entity_id=observation.entity_id,
            source="external_observation",
            tick_id=tick,
            detail=observation.raw_data or observation.source,
        ))

        # Step 3: 如果有实体信息 → 创建/更新
        if observation.entity_id:
            self._upsert_from_obs(observation, tick)

        # Step 4: 如果有关系 → 添加
        if observation.claimed_relation:
            self.relations.add_relation(observation.claimed_relation)
            self.events.record(WorldEvent(
                event_id=f"rel:{observation.claimed_relation.relation_id}",
                event_type=WorldEventType.RELATION_ADDED,
                relation_id=observation.claimed_relation.relation_id,
                source="external_observation",
                tick_id=tick,
            ))

        return result

    def _upsert_from_obs(self, observation: Observation, tick: int) -> None:
        """从观察 upsert 实体和状态。"""
        eid = observation.entity_id
        if not self.entities.exists(eid):
            entity_type = _extract_entity_type(observation)
            self.entities.create_entity(
                entity_id=eid,
                name=eid,
                entity_type=EntityType(entity_type) if isinstance(entity_type, str) else entity_type,
                tick=tick,
            )
            self.events.record(WorldEvent(
                event_id=f"ent:{eid}",
                event_type=WorldEventType.ENTITY_CREATED,
                entity_id=eid,
                source="external_observation",
                tick_id=tick,
            ))

        # 状态更新
        if observation.claimed_state:
            state = EntityState(
                state_id=f"st:{eid}:{tick}",
                entity_id=eid,
                attributes=dict(observation.claimed_state.attributes),
                tick_id=tick,
            )
            self.states.record_state(state)
            self.events.record(WorldEvent(
                event_id=f"stchg:{eid}:{tick}",
                event_type=WorldEventType.STATE_CHANGED,
                entity_id=eid,
                source="external_observation",
                tick_id=tick,
            ))

    # ── 查询 ──

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    def get_entity_state(self, entity_id: str) -> Optional[EntityState]:
        return self.states.current(entity_id)

    def get_neighbors(self, entity_id: str) -> list[tuple[str, Relation]]:
        return self.relations.neighbors(entity_id)

    def get_entity_history(self, entity_id: str) -> list[EntityState]:
        return self.states.history(entity_id)

    def search_entities(self, entity_type: EntityType) -> list[Entity]:
        return self.entities.get_by_type(entity_type)

    def summary(self) -> dict:
        """世界模型统计摘要。"""
        return {
            "entity_count": self.entities.count,
            "relation_count": self.relations.count,
            "event_count": self.events.count,
            "causality_count": self.causality.count,
            "tick": self._tick,
        }

    # ── Phase 49-B (L3-A): 面向认知的查询封装 ─────────────────────────

    def cognitive_world_state(self, entity_id: str | None = None,
                              limit: int = 10) -> dict:
        """面向认知主链的世界状态查询 (Blueprint v1.1 L3-A).

        空世界 (默认零传感器) 返回空结构 — L3-C Observation Supply
        是后续能力, 本查询保证消费就绪且优雅降级。

        返回值供 think/plan 注入 (L3-B), 不产生 Action。
        """
        state: dict = {
            "available": self.entities.count > 0,
            "entity_count": self.entities.count,
            "relation_count": self.relations.count,
            "tick": self._tick,
            "entities": [],
            "summary": self.summary(),
        }
        if not state["available"]:
            return state

        # 收集实体状态 (全部或指定实体)
        ids: list[str] = []
        if entity_id:
            ids = [entity_id]
        else:
            try:
                ids = [e.entity_id for e in
                       self.entities.list_all()][:limit]
            except AttributeError:
                ids = []
        for eid in ids[:limit]:
            ent = self.get_entity(eid)
            st = self.get_entity_state(eid)
            if ent is None:
                continue
            state["entities"].append({
                "entity_id": eid,
                "name": getattr(ent, "name", eid),
                "entity_type": getattr(getattr(ent, "entity_type", None),
                                       "value", ""),
                "state": (dict(st.attributes) if st is not None
                          else {}),
                "tick_id": getattr(st, "tick_id", None),
            })
        return state


__all__ = ["WorldStore"]


def _extract_entity_type(observation: Observation) -> EntityType:
    """从观察中提取实体类型，默认 OTHER."""
    if observation.claimed_state is not None:
        raw = observation.claimed_state.attributes.get("entity_type")
        if isinstance(raw, str):
            try:
                return EntityType(raw)
            except ValueError:
                pass
    return EntityType.OTHER
