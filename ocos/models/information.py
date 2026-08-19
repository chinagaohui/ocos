"""
Information Model — Layer 0 认知理论的数据模型实现。

对应 INFORMATION_THEORY.md 中的核心概念：
- 状态机（InformationState）— 五态统一生命周期 S_C→S_V→S_R→S_D→S_A
- 语义角色（SemanticRole）— 七类语义 R_O/R_M/R_K/R_G/R_I/R_P/R_D
- 持久化层级（PersistenceLevel）— 四层 P_T/P_P/P_S/P_I
- 关系类型（RelationType）— 三大类：结构/语义/时序
- 信息单元的统一寻址（UniversalAddress）
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enum: InformationState ─────────────────────────────────────────────

_INFORMATION_LEGACY_MAP: dict[str, str] = {
    "draft": "created",
    "active": "validated",
    "decayed": "deprecated",
    "promoted": "deprecated",
}


class InformationState(str, Enum):
    """信息单元统一生命周期状态（INFORMATION_THEORY 第四章）。

    Created(S_C) → Validated(S_V) → Referenced(S_R) → Deprecated(S_D) → Archived(S_A)
    ┌──────┐    ┌────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐
    │ S_C  │───→│  S_V  │───→│   S_R    │───→│   S_D    │───→│  S_A   │
    └──────┘    └────────┘    └──────────┘    └──────────┘    └────────┘
       │                            │              │
       └───→ S_D (拒绝/废弃)         └───→ S_D(遗忘) │
                                                  └───→ S_A(V→A 跳过引用)

    Legacy v1.x 映射: draft→CREATED, active→VALIDATED, decayed→DEPRECATED, promoted→DEPRECATED
    """

    CREATED = "created"      # S_C — 信息被 Acquire 进入系统
    VALIDATED = "validated"  # S_V — 信息经过验证
    REFERENCED = "referenced"  # S_R — 信息被其他信息或决策引用
    DEPRECATED = "deprecated"  # S_D — 信息不再活跃，标记为弃用
    ARCHIVED = "archived"    # S_A — 信息移出主存储，保留以备审计

    @classmethod
    def _missing_(cls, value: object) -> InformationState | None:
        """允许 Legacy 值通过兼容映射转换为标准状态。"""
        if isinstance(value, str):
            mapped = _INFORMATION_LEGACY_MAP.get(value.lower())
            if mapped:
                logger.debug("InformationState legacy mapping: %s → %s", value, mapped)
                return cls(mapped)
        return None

    def can_transition_to(self, target: InformationState) -> bool:
        """返回从当前状态到目标状态的转移是否合法（Theory 第四章转移规则）。"""
        result = target in _VALID_TRANSITIONS.get(self, set())
        logger.debug("InformationState %s → %s: %s", self.value, target.value, result)
        return result

    @property
    def is_terminal(self) -> bool:
        """ARCHIVED 是唯一终端状态（Deprecated 可 Archive）。"""
        return self == InformationState.ARCHIVED


_VALID_TRANSITIONS: dict[InformationState, set[InformationState]] = {
    InformationState.CREATED: {InformationState.VALIDATED, InformationState.DEPRECATED},
    InformationState.VALIDATED: {InformationState.REFERENCED, InformationState.DEPRECATED, InformationState.ARCHIVED},
    InformationState.REFERENCED: {InformationState.DEPRECATED},
    InformationState.DEPRECATED: {InformationState.ARCHIVED},
    InformationState.ARCHIVED: set(),  # terminal — 不可逆
}


# ── Enum: SemanticRole ─────────────────────────────────────────────────

_SEMANTIC_LEGACY_MAP: dict[str, str] = {
    "fact": "observation",
    "intent": "goal",
    "reasoning": "memory",
    "preference": "policy",
}


class SemanticRole(str, Enum):
    """信息单元的语义角色（INFORMATION_THEORY 第三章）。

    ┌──────┬───────┬────────┬──────┬──────────┬───────┬──────────┐
    │  R_O │  R_M  │  R_K   │ R_G  │   R_I   │  R_P  │   R_D   │
    │ Obs  │ Mem   │ Know   │ Goal │ Identity│Policy │ Decision │
    └──────┴───────┴────────┴──────┴──────────┴───────┴──────────┘

    Legacy v1.x 映射: fact→OBSERVATION, intent→GOAL, reasoning→MEMORY, preference→POLICY
    """

    OBSERVATION = "observation"   # R_O — 从 Reality 感知到的原始输入
    MEMORY = "memory"             # R_M — 被系统 Retain 并可 Access 的 Information
    KNOWLEDGE = "knowledge"       # R_K — 经过验证的 Stable Information
    GOAL = "goal"                 # R_G — 描述系统目标的信息
    IDENTITY = "identity"         # R_I — 描述系统自身的信息
    POLICY = "policy"             # R_P — 描述行为约束的信息
    DECISION = "decision"         # R_D — 描述已做出选择的信息

    @classmethod
    def _missing_(cls, value: object) -> SemanticRole | None:
        """允许 Legacy 值通过兼容映射转换。"""
        if isinstance(value, str):
            mapped = _SEMANTIC_LEGACY_MAP.get(value.lower())
            if mapped:
                logger.debug("SemanticRole legacy mapping: %s → %s", value, mapped)
                return cls(mapped)
        return None


# ── Enum: PersistenceLevel ─────────────────────────────────────────────

_PERSISTENCE_LEGACY_MAP: dict[str, str] = {
    "ephemeral": "transient",
    "session": "persistent",
    "workspace": "persistent",
}


class PersistenceLevel(str, Enum):
    """信息单元的持久化层级（INFORMATION_THEORY 第三章）。

    P_T(Transient) → P_P(Persistent) → P_S(Stable) → P_I(Immutable)
    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌──────────┐
    │ Transient│───→│Persistent│───→│ Stable │───→│ Immutable│
    └──────────┘    └──────────┘    └────────┘    └──────────┘

    Legacy v1.x 映射: ephemeral→TRANSIENT, session/workspace→PERSISTENT
    """

    TRANSIENT = "transient"    # P_T — 短期存在，自动衰减（秒到分钟）
    PERSISTENT = "persistent"  # P_P — 持久化存储（天到年）
    STABLE = "stable"          # P_S — 经过验证，长期有效（月到永久）
    IMMUTABLE = "immutable"    # P_I — 永久存在，不可修改

    @classmethod
    def _missing_(cls, value: object) -> PersistenceLevel | None:
        """允许 Legacy 值通过兼容映射转换。"""
        if isinstance(value, str):
            mapped = _PERSISTENCE_LEGACY_MAP.get(value.lower())
            if mapped:
                logger.debug("PersistenceLevel legacy mapping: %s → %s", value, mapped)
                return cls(mapped)
        return None


# ── Enum: RelationType ─────────────────────────────────────────────────

_RELATION_LEGACY_MAP: dict[str, str] = {
    "references": "part_of",
}


class RelationType(str, Enum):
    """信息单元间的关系类型（INFORMATION_THEORY 第六章 — 三类关系）。

    Structural（结构关系）:
      part_of, contains, derived_from, supports
    Semantic（语义关系）:
      contradicts, similar_to, refines
    Temporal（时序关系）:
      before, after, causes, correlates

    Legacy v1.x 映射: references→PART_OF
    """

    # Structural
    PART_OF = "part_of"            # A 是 B 的组成部分
    CONTAINS = "contains"          # A 包含 B
    DERIVED_FROM = "derived_from"  # A 从 B 推导而来
    SUPPORTS = "supports"          # A 支持 B 的结论

    # Semantic
    CONTRADICTS = "contradicts"    # A 与 B 矛盾
    SIMILAR_TO = "similar_to"      # A 与 B 相似
    REFINES = "refines"            # A 细化了 B

    # Temporal
    BEFORE = "before"              # A 发生在 B 之前
    AFTER = "after"                # A 发生在 B 之后
    CAUSES = "causes"              # A 导致 B
    CORRELATED_WITH = "correlated_with"  # A 与 B 相关（因果关系未确认）

    @classmethod
    def _missing_(cls, value: object) -> RelationType | None:
        """允许 Legacy 值通过兼容映射转换。"""
        if isinstance(value, str):
            mapped = _RELATION_LEGACY_MAP.get(value.lower())
            if mapped:
                logger.debug("RelationType legacy mapping: %s → %s", value, mapped)
                return cls(mapped)
        return None


# ── Dataclass: UniversalAddress ────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class UniversalAddress:
    """跨 Store 的统一寻址。

    使系统内任何信息单元都可以被唯一标识和定位。
    """
    namespace: str   # 存储空间：working | knowledge | episodic | trace
    type: str        # 实体类型：goal | memory | knowledge | decision | action
    id: str          # 唯一标识符
    version: int = 1

    def __post_init__(self) -> None:
        """基本校验。"""
        if not self.namespace:
            raise ValueError("namespace must not be empty")
        if not self.type:
            raise ValueError("type must not be empty")
        if not self.id:
            raise ValueError("id must not be empty")
        if self.version < 1:
            raise ValueError("version must be >= 1")
        logger.debug("UniversalAddress created: %s/%s/%s v%s", self.namespace, self.type, self.id, self.version)


# ── Dataclass: InformationMetadata ─────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class InformationMetadata:
    """附加到任意信息单元的元数据。

    对应 INFORMATION_THEORY 中的认知属性维度。
    """
    address: UniversalAddress
    state: InformationState = InformationState.CREATED
    semantic_role: SemanticRole = SemanticRole.OBSERVATION
    persistence_level: PersistenceLevel = PersistenceLevel.TRANSIENT
    importance: float = 0.5
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    accessed_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    ttl: int | None = None
    source: str = ""
    tags: tuple[str, ...] = dataclasses.field(default_factory=tuple)

    def __post_init__(self) -> None:
        """校验约束。"""
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be in [0.0, 1.0]")
        if self.ttl is not None and self.ttl < 0:
            raise ValueError("ttl must be non-negative or None")
        logger.debug(
            "InformationMetadata created: address=%s/%s/%s, state=%s, role=%s",
            self.address.namespace, self.address.type, self.address.id,
            self.state.value, self.semantic_role.value,
        )
