"""Phase 7 测试 — Forgetting Engine（信息遗忘引擎）。"""

from __future__ import annotations

from datetime import datetime, timezone

import time
from unittest.mock import MagicMock

import pytest

from ocos.engines.forgetting_engine import ForgettingEngine
from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.models.information import (
    InformationMetadata,
    InformationState,
    PersistenceLevel,
    SemanticRole,
    UniversalAddress,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> ForgettingEngine:
    return ForgettingEngine()


@pytest.fixture
def engine_with_bus() -> tuple[ForgettingEngine, EventBus]:
    bus = EventBus()
    engine = ForgettingEngine(event_bus=bus)
    return engine, bus


def _make_metadata(
    state: InformationState = InformationState.VALIDATED,
    persistence: PersistenceLevel = PersistenceLevel.TRANSIENT,
    ttl: int | None = None,
    created_at: str | None = None,
) -> InformationMetadata:
    return InformationMetadata(
        address=UniversalAddress(namespace="test", type="info", id="i1"),
        state=state,
        semantic_role=SemanticRole.OBSERVATION,
        persistence_level=persistence,
        importance=0.5,
        ttl=ttl,
        created_at=created_at or "2026-01-01T00:00:00",
    )


# ══════════════════════════════════════════════════════════════════════════
# TTL 策略
# ══════════════════════════════════════════════════════════════════════════


class TestTTLPolicy:
    def test_default_policies(self, engine):
        """默认 TTL 为各等级预设值。"""
        assert engine.get_ttl_policy(PersistenceLevel.TRANSIENT) == 30
        assert engine.get_ttl_policy(PersistenceLevel.PERSISTENT) == 86400
        assert engine.get_ttl_policy(PersistenceLevel.STABLE) == 0
        assert engine.get_ttl_policy(PersistenceLevel.IMMUTABLE) == 0

    def test_set_ttl_policy(self, engine):
        engine.set_ttl_policy(PersistenceLevel.TRANSIENT, 60)
        assert engine.get_ttl_policy(PersistenceLevel.TRANSIENT) == 60

    def test_set_ttl_zero_is_no_expiry(self, engine):
        engine.set_ttl_policy(PersistenceLevel.TRANSIENT, 0)
        meta = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            created_at="2020-01-01T00:00:00",
        )
        assert not engine.is_expired(meta)

    def test_set_negative_ttl_raises(self, engine):
        with pytest.raises(ValueError, match=">= 0"):
            engine.set_ttl_policy(PersistenceLevel.TRANSIENT, -1)

    def test_reset_ttl_defaults(self, engine):
        engine.set_ttl_policy(PersistenceLevel.TRANSIENT, 999)
        engine.reset_ttl_defaults()
        assert engine.get_ttl_policy(PersistenceLevel.TRANSIENT) == 30


# ══════════════════════════════════════════════════════════════════════════
# 过期检测
# ══════════════════════════════════════════════════════════════════════════


class TestExpiryDetection:
    def test_is_expired_true(self, engine):
        """超过 TTL 的信息确认为已过期。"""
        old_ts = datetime.fromtimestamp(
            time.time() - 1200, tz=timezone.utc
        ).isoformat()
        meta = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            created_at=old_ts,
        )
        assert engine.is_expired(meta)

    def test_is_expired_false_recent(self, engine):
        """未超 TTL 的信息不过期。"""
        recent_ts = datetime.fromtimestamp(
            time.time() - 60, tz=timezone.utc
        ).isoformat()
        meta = _make_metadata(
            persistence=PersistenceLevel.PERSISTENT,
            created_at=recent_ts,
        )
        assert not engine.is_expired(meta)

    def test_is_expired_false_persistent(self, engine):
        """IMMUTABLE 等级默认不过期。"""
        old_ts = datetime.fromtimestamp(
            0, tz=timezone.utc
        ).isoformat()  # epoch
        meta = _make_metadata(
            persistence=PersistenceLevel.IMMUTABLE,
            created_at=old_ts,
        )
        assert not engine.is_expired(meta)

    def test_is_expired_non_active_not_checked(self, engine):
        """非 ACTIVE 状态的信息跳过过期检查。"""
        old_ts = datetime.fromtimestamp(
            0, tz=timezone.utc
        ).isoformat()
        meta = _make_metadata(
            state=InformationState.ARCHIVED,
            persistence=PersistenceLevel.TRANSIENT,
            created_at=old_ts,
        )
        assert not engine.is_expired(meta)

    def test_instance_ttl_overrides_policy(self, engine):
        """实例级 TTL 覆盖策略级 TTL。"""
        engine.set_ttl_policy(PersistenceLevel.TRANSIENT, 86400)  # 24h
        old_ts = datetime.fromtimestamp(
            0, tz=timezone.utc
        ).isoformat()
        meta = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            ttl=30,  # 实例级 30s
            created_at=old_ts,
        )
        assert engine.is_expired(meta)

    def test_collect_expired(self, engine):
        """collect_expired 返回过期项子集。"""
        old_ts = datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
        recent_ts = datetime.fromtimestamp(
            time.time(), tz=timezone.utc
        ).isoformat()
        expired = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            created_at=old_ts,
        )
        fresh = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            created_at=recent_ts,
        )
        result = engine.collect_expired([fresh, expired])
        assert result == [expired]

    def test_collect_expired_empty(self, engine):
        """无过期项时返回空列表。"""
        recent_ts = datetime.fromtimestamp(
            time.time(), tz=timezone.utc
        ).isoformat()
        fresh = _make_metadata(
            persistence=PersistenceLevel.TRANSIENT,
            created_at=recent_ts,
        )
        assert engine.collect_expired([fresh]) == []


# ══════════════════════════════════════════════════════════════════════════
# 遗忘执行
# ══════════════════════════════════════════════════════════════════════════


class TestForget:
    def test_forget_active(self, engine):
        """ACTIVE 信息可被遗忘。"""
        meta = _make_metadata(state=InformationState.VALIDATED)
        ok, msg = engine.forget(meta, governance_approved=True)
        assert ok
        assert "forgotten" in msg

    def test_forget_draft(self, engine):
        """DRAFT 信息可被遗忘。"""
        meta = _make_metadata(state=InformationState.CREATED)
        ok, msg = engine.forget(meta, governance_approved=True)
        assert ok

    def test_forget_archived_fails(self, engine):
        """已归档的信息不能遗忘。"""
        meta = _make_metadata(state=InformationState.ARCHIVED)
        ok, msg = engine.forget(meta, governance_approved=True)
        assert not ok

    def test_forget_persistent_needs_governance(self, engine):
        """PERSISTENT 等级未审批时拒绝。"""
        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        ok, msg = engine.forget(meta, governance_approved=False)
        assert not ok
        assert "Governance" in msg

    def test_forget_persistent_with_governance(self, engine):
        """PERSISTENT 等级经审批后可遗忘。"""
        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        ok, msg = engine.forget(meta, governance_approved=True)
        assert ok

    def test_forget_emits_event(self, engine_with_bus):
        """遗忘发射 INFORMATION_STATUS_CHANGED 事件。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.INFORMATION_STATUS_CHANGED, received.append)

        meta = _make_metadata()
        engine.forget(meta, governance_approved=True)
        assert len(received) == 1
        assert received[0].event_type == EventType.INFORMATION_STATUS_CHANGED
        assert received[0].payload["unit_id"] == meta.address.id


# ══════════════════════════════════════════════════════════════════════════
# mark_for_forget
# ══════════════════════════════════════════════════════════════════════════


class TestMarkForForget:
    def test_mark_non_persistent_direct(self, engine):
        """非 PERSISTENT 等级直接遗忘。"""
        meta = _make_metadata(persistence=PersistenceLevel.TRANSIENT)
        ok, msg = engine.mark_for_forget(meta)
        assert ok

    def test_mark_persistent_governance_required(self, engine):
        """PERSISTENT 等级需要 Governance 审批。"""
        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        ok, msg = engine.mark_for_forget(meta)
        assert not ok
        assert "Governance" in msg

    def test_mark_non_active_fails(self, engine):
        """非 ACTIVE/DRAFT 状态不可标记。"""
        meta = _make_metadata(state=InformationState.ARCHIVED)
        ok, msg = engine.mark_for_forget(meta)
        assert not ok

    def test_mark_emits_governance_request(self, engine_with_bus):
        """PERSISTENT 等级发射审批请求事件。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.GOVERNANCE_APPROVAL_REQUESTED, received.append)

        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        engine.mark_for_forget(meta)
        assert len(received) == 1


# ══════════════════════════════════════════════════════════════════════════
# Governance 回调
# ══════════════════════════════════════════════════════════════════════════


class TestGovernanceCallbacks:
    def test_approve_forget(self, engine_with_bus):
        """审批后执行遗忘。"""
        engine, bus = engine_with_bus
        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        ok, msg = engine.mark_for_forget(meta)
        assert not ok  # 等待审批
        forget_id = msg.split("=")[-1]

        ok2, msg2 = engine.approve_forget(forget_id, "admin")
        assert ok2

    def test_approve_unknown_forget_id(self, engine):
        """不存在的 forget_id 返回错误。"""
        ok, msg = engine.approve_forget("nonexistent", "admin")
        assert not ok
        assert "不存在" in msg

    def test_reject_forget(self, engine_with_bus):
        """拒绝后不执行遗忘。"""
        engine, bus = engine_with_bus
        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        ok, msg = engine.mark_for_forget(meta)
        forget_id = msg.split("=")[-1]

        ok2, msg2 = engine.reject_forget(forget_id, "admin", "not needed")
        assert ok2

    def test_reject_unknown_forget_id(self, engine):
        """不存在的 forget_id 返回错误。"""
        ok, msg = engine.reject_forget("nonexistent", "admin")
        assert not ok
        assert "不存在" in msg

    def test_approve_emits_governance_approved(self, engine_with_bus):
        """审批后发射 GOVERNANCE_APPROVED 事件。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.GOVERNANCE_APPROVED, received.append)

        meta = _make_metadata(persistence=PersistenceLevel.PERSISTENT)
        _, msg = engine.mark_for_forget(meta)
        forget_id = msg.split("=")[-1]
        engine.approve_forget(forget_id, "admin")

        assert len(received) == 1
