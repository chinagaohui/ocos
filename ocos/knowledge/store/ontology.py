"""
M0 Knowledge Ontology — 知识的原子单元定义与提升关系。

Phase16 定义的抽象链条：Observation → Evidence → Pattern → Principle → Policy
这 5 个层级由 4 个提升关系连接：Observation→Evidence, Evidence→Pattern,
Pattern→Principle, Principle→Policy。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class KnowledgeLevel(str, Enum):
    """知识层级（从原始观察到顶层策略）。"""
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    PATTERN = "pattern"
    PRINCIPLE = "principle"
    POLICY = "policy"


class KnowledgeStatus(str, Enum):
    """知识生命周期状态。"""
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# ── 提升关系定义 ───────────────────────────────────────────────────────────

ELEVATION_MATRIX: dict[KnowledgeLevel, list[KnowledgeLevel]] = {
    # key = 源层级, value = 可提升到的目标层级
    KnowledgeLevel.OBSERVATION: [KnowledgeLevel.EVIDENCE],
    KnowledgeLevel.EVIDENCE: [KnowledgeLevel.PATTERN],
    KnowledgeLevel.PATTERN: [KnowledgeLevel.PRINCIPLE],
    KnowledgeLevel.PRINCIPLE: [KnowledgeLevel.POLICY],
    KnowledgeLevel.POLICY: [],  # 顶层不可再提升
}


def get_elevation_targets(source_level: KnowledgeLevel) -> list[KnowledgeLevel]:
    """返回给定层级可提升到的目标层级列表。"""
    targets = ELEVATION_MATRIX.get(source_level, [])
    logger.debug("get_elevation_targets: %s -> %s", source_level.value, [t.value for t in targets])
    return targets


def can_elevate(
    source_level: KnowledgeLevel,
    target_level: KnowledgeLevel,
) -> bool:
    """检查 source_level 能否直接提升到 target_level。"""
    ok = target_level in ELEVATION_MATRIX.get(source_level, [])
    logger.debug("can_elevate: %s -> %s = %s", source_level.value, target_level.value, ok)
    return ok


def get_level_index(level: KnowledgeLevel) -> int:
    """返回层级的数值索引（0=lowest, 4=highest）。"""
    index_map = {
        KnowledgeLevel.OBSERVATION: 0,
        KnowledgeLevel.EVIDENCE: 1,
        KnowledgeLevel.PATTERN: 2,
        KnowledgeLevel.PRINCIPLE: 3,
        KnowledgeLevel.POLICY: 4,
    }
    return index_map[level]


def is_higher_level(
    level_a: KnowledgeLevel,
    level_b: KnowledgeLevel,
) -> bool:
    """检查 level_a 是否在 level_b 之上。"""
    return get_level_index(level_a) > get_level_index(level_b)


# ── 状态机 ─────────────────────────────────────────────────────────────────

STATUS_TRANSITIONS: dict[KnowledgeStatus, list[KnowledgeStatus]] = {
    KnowledgeStatus.CANDIDATE: [KnowledgeStatus.VERIFIED, KnowledgeStatus.DEPRECATED],
    KnowledgeStatus.VERIFIED: [KnowledgeStatus.ACTIVE, KnowledgeStatus.DEPRECATED],
    KnowledgeStatus.ACTIVE: [KnowledgeStatus.DEPRECATED],
    KnowledgeStatus.DEPRECATED: [KnowledgeStatus.ARCHIVED, KnowledgeStatus.ACTIVE],
    KnowledgeStatus.ARCHIVED: [],
}


def get_next_statuses(current: KnowledgeStatus) -> list[KnowledgeStatus]:
    """返回从当前状态可转换到的下一状态列表。"""
    next_statuses = STATUS_TRANSITIONS.get(current, [])
    logger.debug("get_next_statuses: %s -> %s", current.value, [s.value for s in next_statuses])
    return next_statuses


def can_transition(
    current: KnowledgeStatus,
    target: KnowledgeStatus,
) -> bool:
    """检查 status 转换是否合法。"""
    ok = target in STATUS_TRANSITIONS.get(current, [])
    logger.debug("can_transition: %s -> %s = %s", current.value, target.value, ok)
    return ok


# ── 知识单元 ────────────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class KnowledgeUnit:
    """知识的原子单元。

    包含完整的层级 + 状态 + 内容，是知识流动的基本粒子。
    """
    unit_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    level: KnowledgeLevel = KnowledgeLevel.OBSERVATION
    status: KnowledgeStatus = KnowledgeStatus.CANDIDATE
    content: dict[str, Any] = dataclasses.field(default_factory=dict)
    source: str = ""
    version: int = 1
    parent_id: str = ""  # 从哪个单元提升而来
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclasses.dataclass(frozen=True)
class ElevationRecord:
    """提升记录：KnowledgeUnit 从一级升到另一级的审计信息。"""
    record_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    unit_id: str = ""
    from_level: KnowledgeLevel = KnowledgeLevel.OBSERVATION
    to_level: KnowledgeLevel = KnowledgeLevel.EVIDENCE
    reason: str = ""
    promoted_by: str = ""  # 触发源模块
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── 验证 ────────────────────────────────────────────────────────────────────


def validate_elevation(
    unit: KnowledgeUnit,
    target_level: KnowledgeLevel,
    reason: str = "",
) -> tuple[bool, list[str]]:
    """验证一个 KnowledgeUnit 是否可以提升到目标层级。

    Returns:
        (is_valid, error_messages)
    """
    errors: list[str] = []

    # 1. 检查层级提升方向
    if not can_elevate(unit.level, target_level):
        errors.append(
            f"不可从 {unit.level.value} 直接提升到 {target_level.value}"
        )

    # 2. 检查状态（只有 ACTIVE 或 VERIFIED 的知识才能提升）
    if unit.status not in (KnowledgeStatus.ACTIVE, KnowledgeStatus.VERIFIED):
        errors.append(
            f"只有 ACTIVE 或 VERIFIED 状态的知识才能提升，当前为 {unit.status.value}"
        )

    if errors:
        logger.warning("validate_elevation failed: unit=%s target=%s errors=%s",
                       unit.unit_id, target_level.value, errors)
    else:
        logger.debug("validate_elevation ok: unit=%s target=%s", unit.unit_id, target_level.value)
    return (len(errors) == 0, errors)
