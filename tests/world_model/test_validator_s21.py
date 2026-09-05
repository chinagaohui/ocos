"""S2.1: WorldValidator 冲突检查修复回归（白皮书 P1-4）。

原 bug：world_validator.py:118 `existing.entity_type != existing.entity_type`
自比较恒 False —— 实体类型冲突检查从未触发（实测 CONFLICT→ACCEPT）。
"""

from __future__ import annotations

import pytest

from ocos.world_model.world_types import (
    Entity, EntityType, EntityState, Observation,
)
from ocos.world_model.world_validator import (
    ValidationDecision, WorldValidator,
)


def _obs(entity_id: str, claimed_type: str | None, source="probe"):
    attrs = {"entity_type": claimed_type} if claimed_type else {"progress": 0.5}
    from datetime import datetime, timezone
    return Observation(
        observation_id=f"obs-{uuid4hex()}",
        source=source,
        entity_id=entity_id,
        claimed_state=EntityState(
            state_id=f"st-{uuid4hex()}",
            entity_id=entity_id,
            attributes=attrs,
            timestamp=datetime.now(timezone.utc),
            tick_id=1,
        ),
        tick_id=1,
    )


def uuid4hex() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


class TestConflictDetection:
    def test_same_id_different_type_conflict(self):
        """同 entity_id 但观察声称不同类型 → CONFLICT（修复前恒 ACCEPT）。"""
        validator = WorldValidator()
        existing = {
            "proj-1": Entity(
                entity_id="proj-1", name="proj-1",
                entity_type=EntityType.PROJECT,
                created_tick=0, confidence=0.9),
        }
        obs = _obs("proj-1", "person")
        result = validator.validate_against_model(obs, existing, {})
        assert result.decision == ValidationDecision.CONFLICT, result.reason

    def test_same_id_same_type_accept(self):
        validator = WorldValidator()
        existing = {
            "proj-1": Entity(
                entity_id="proj-1", name="proj-1",
                entity_type=EntityType.PROJECT,
                created_tick=0, confidence=0.9),
        }
        obs = _obs("proj-1", "project")
        result = validator.validate_against_model(obs, existing, {})
        assert result.decision == ValidationDecision.ACCEPT

    def test_no_claimed_type_accept(self):
        """观察未声称类型（无法判定）→ 不产生冲突。"""
        validator = WorldValidator()
        existing = {
            "proj-1": Entity(
                entity_id="proj-1", name="proj-1",
                entity_type=EntityType.PROJECT,
                created_tick=0, confidence=0.9),
        }
        obs = _obs("proj-1", None)
        result = validator.validate_against_model(obs, existing, {})
        assert result.decision == ValidationDecision.ACCEPT

    def test_unknown_entity_accept(self):
        """新实体（无既有记录）→ 不冲突。"""
        validator = WorldValidator()
        obs = _obs("proj-new", "project")
        result = validator.validate_against_model(obs, {}, {})
        assert result.decision == ValidationDecision.ACCEPT
