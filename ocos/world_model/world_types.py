"""Phase 42: World Model Types — 世界观核心类型。

World Model 回答: "外部世界如何运作？"

不是 Knowledge Base（文档存储），而是世界的结构化表示。

三层区分:
    Knowledge    → "有哪些信息"         （事实存储）
    Belief       → "某个事实可信吗"     （判断，Phase 24/40）
    World Model  → "实体如何存在/变化/相互影响"  （结构，Phase 42）

核心边界:
    WM42-01: World Model ≠ Knowledge Base
    WM42-02: World Model ≠ Belief
    WM42-03: World Model ≠ Goal
    WM42-04: External Agent ≠ World Authority

含:
    - Entity:        世界中有什么
    - Relation:      它们如何连接
    - State/StateRecord: 实体状态 + 版本追踪
    - WorldEvent:    发生了什么变化
    - Causality:     因果链（是什么导致了什么）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 实体类型
# ═══════════════════════════════════════════════════════════════════════════════


class EntityType(Enum):
    """实体分类 — 世界中有哪些类型的实体。"""

    # 核心
    PERSON = "person"              # 人
    ORGANIZATION = "organization"  # 组织
    TECHNOLOGY = "technology"      # 技术
    PROJECT = "project"            # 项目
    CONCEPT = "concept"            # 概念
    LOCATION = "location"          # 地点
    EVENT = "event"                # 事件（作为实体时）
    PROCESS = "process"            # 过程
    RESOURCE = "resource"          # 资源
    OTHER = "other"                # 其他

    @property
    def is_concrete(self) -> bool:
        return self in (
            EntityType.PERSON, EntityType.ORGANIZATION,
            EntityType.TECHNOLOGY, EntityType.PROJECT,
            EntityType.LOCATION, EntityType.RESOURCE,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 状态类型
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EntityState:
    """实体在某时刻的状态快照。

    attributes 是开放式的 kv 字典，适应不同实体类型的动态属性。

    例如:
        Project: {"progress": 0.7, "risk": "medium", "team_size": 5}
        Technology: {"maturity": "stable", "adoption": "growing"}
    """

    state_id: str
    entity_id: str
    attributes: dict[str, float |str | bool] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tick_id: int = 0

    def get(self, key: str) -> Optional[float | str | bool]:
        return self.attributes.get(key)

    @property
    def keys(self) -> set[str]:
        return set(self.attributes.keys())


@dataclass(frozen=True)
class StateChange:
    """状态变更记录 — 从一个 EntityState 到另一个。"""

    from_state_id: str
    to_state_id: str
    entity_id: str
    changed_keys: frozenset[str]
    tick_id: int
    cause_event_id: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 核心实体
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Entity:
    """世界实体 — 不可变的结构定义，状态通过版本追踪。

    id 是唯一标识，entity_type 决定属性 schema 形状。
    """

    entity_id: str
    name: str
    entity_type: EntityType
    description: str = ""
    created_tick: int = 0
    confidence: float = 1.0  # 对此实体存在的置信度 [0, 1]

    def __repr__(self) -> str:
        return f"Entity({self.entity_id!r}, {self.entity_type.value})"


# ═══════════════════════════════════════════════════════════════════════════════
# 关系类型
# ═══════════════════════════════════════════════════════════════════════════════


class RelationType(Enum):
    """关系语义分类。"""

    CAUSES = "causes"              # A 导致 B
    DEPENDS_ON = "depends_on"      # A 依赖于 B
    COMPETES_WITH = "competes_with"  # A 与 B 竞争
    CONTAINS = "contains"          # A 包含 B
    SUPPORTS = "supports"          # A 支持 B
    OPPOSES = "opposes"            # A 反对 B
    AFFECTS = "affects"            # A 影响 B
    IS_PART_OF = "is_part_of"      # A 是 B 的一部分
    SIMILAR_TO = "similar_to"      # A 与 B 相似
    PRECEDES = "precedes"          # A 先于 B（时序）
    CUSTOM = "custom"              # 自定义关系

    @property
    def is_causal(self) -> bool:
        """是否为因果关系。"""
        return self in (RelationType.CAUSES, RelationType.AFFECTS)


@dataclass(frozen=True)
class Relation:
    """实体间关系。

    例如:
        Relation("coA", "coB", RelationType.COMPETES_WITH)
        Relation("flask", "python", RelationType.DEPENDS_ON)
    """

    relation_id: str
    from_entity_id: str
    to_entity_id: str
    relation_type: RelationType
    weight: float = 1.0  # 关系强度 [0, 1]
    evidence_tick: int = 0
    note: str = ""

    @property
    def entities(self) -> tuple[str, str]:
        return (self.from_entity_id, self.to_entity_id)

    def __repr__(self) -> str:
        return (f"{self.from_entity_id} "
                f"--[{self.relation_type.value}]--> "
                f"{self.to_entity_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# 事件
# ═══════════════════════════════════════════════════════════════════════════════


class WorldEventType(Enum):
    """世界事件类型。"""

    ENTITY_CREATED = "entity_created"
    ENTITY_CHANGED = "entity_changed"
    ENTITY_REMOVED = "entity_removed"
    RELATION_ADDED = "relation_added"
    RELATION_REMOVED = "relation_removed"
    STATE_CHANGED = "state_changed"
    OBSERVATION = "observation"  # 外部观察（未验证）
    CUSTOM = "custom"


@dataclass(frozen=True)
class WorldEvent:
    """世界事件 — 世界中发生了什么事。

    与 Phase 39 EventBus 的 Event 不同:
        EventBus Event = 系统内部通信
        WorldEvent   = 世界状态的变更记录
    """

    event_id: str
    event_type: WorldEventType
    entity_id: str = ""
    relation_id: str = ""
    source: str = "internal"  # internal | external_observation | inference
    tick_id: int = 0
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_external(self) -> bool:
        return self.source == "external_observation"


# ═══════════════════════════════════════════════════════════════════════════════
# 因果
# ═══════════════════════════════════════════════════════════════════════════════


class CausalityType(Enum):
    """因果类型。"""

    DIRECT = "direct"      # A 直接导致 B
    CONTRIBUTES = "contributes"  # A 贡献于 B（多因一果）
    ENABLES = "enables"    # A 使 B 成为可能
    PREVENTS = "prevents"  # A 阻止 B
    CORRELATED = "correlated"  # A 与 B 相关（但不声称因果）


@dataclass(frozen=True)
class CausalityLink:
    """因果链中的一个环节 — A → B。

    不是简单关联，而是声称"因为 A 所以 B"。

    约束:
        - 必须基于证据（evidence list）
        - 必须跟踪 discovery_source（观察/推理/验证）
        - 因果链可以被反驳（counter_evidence）
    """

    link_id: str
    cause_event_id: str
    effect_event_id: str
    causality_type: CausalityType
    confidence: float = 0.0  # [0, 1]
    evidence_ids: tuple[str, ...] = ()  # 支持证据的 event IDs
    counter_evidence_ids: tuple[str, ...] = ()  # 反例 event IDs
    discovery_source: str = "inference"  # observation | inference | validation
    tick_id: int = 0

    @property
    def is_well_supported(self) -> bool:
        return self.confidence >= 0.6 and len(self.evidence_ids) >= 2

    @property
    def has_counter_evidence(self) -> bool:
        return len(self.counter_evidence_ids) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 外部观察
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Observation:
    """外部观察 — 来自 External Agent 或其他数据源的未验证输入。

    约束 WM42-04:
        外部 Agent 不能直接写入 World Model。
        必须经过: Observation → Validator → World Update。
    """

    observation_id: str
    source: str  # 数据来源（agent_id / url / api）
    entity_id: str = ""
    claimed_relation: Optional[Relation] = None
    claimed_state: Optional[EntityState] = None
    raw_data: str = ""  # 原始数据（不直接使用）
    tick_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    # 实体
    "EntityType",
    "Entity",
    # 状态
    "EntityState",
    "StateChange",
    # 关系
    "RelationType",
    "Relation",
    # 事件
    "WorldEventType",
    "WorldEvent",
    # 因果
    "CausalityType",
    "CausalityLink",
    # 观察
    "Observation",
]
