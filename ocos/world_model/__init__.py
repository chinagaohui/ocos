"""Phase 42: World Model — 世界观。

World Model 回答: "外部世界如何运作？"

不是 Knowledge Base，不是 Belief，不是 Goal。
而是外部世界的结构化表示。

四层结构:
    Environment Perception → Domain Models → Causality Models → Event Patterns

核心组件:
    - Entity:     世界中有什么
    - Relation:   它们如何连接
    - State:      当前状态是什么
    - Event:      发生了什么变化
    - Causality:  为什么发生了变化

边界约束:
    WM42-01: World Model ≠ Knowledge Base
    WM42-02: World Model ≠ Belief
    WM42-03: World Model ≠ Goal
    WM42-04: External Agent ≠ World Authority
"""

from ocos.world_model.world_types import (
    EntityType,
    Entity,
    EntityState,
    StateChange,
    RelationType,
    Relation,
    WorldEventType,
    WorldEvent,
    CausalityType,
    CausalityLink,
    Observation,
)
from ocos.world_model.entity_model import EntityModel
from ocos.world_model.relation_graph import RelationGraph
from ocos.world_model.state_tracker import StateTracker
from ocos.world_model.event_model import EventModel
from ocos.world_model.causality_engine import CausalityEngine
from ocos.world_model.world_validator import (
    WorldValidator,
    ValidationDecision,
    ValidationIssue,
    ValidationResult,
)
from ocos.world_model.world_store import WorldStore

__all__ = [
    # Core Types
    "EntityType", "Entity", "EntityState", "StateChange",
    "RelationType", "Relation",
    "WorldEventType", "WorldEvent",
    "CausalityType", "CausalityLink",
    "Observation",
    # Components
    "EntityModel",
    "RelationGraph",
    "StateTracker",
    "EventModel",
    "CausalityEngine",
    # Governance
    "WorldValidator",
    "ValidationDecision",
    "ValidationIssue",
    "ValidationResult",
    # Store
    "WorldStore",
]
