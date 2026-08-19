"""
M2 测试 — Knowledge Lifecycle + Knowledge ABI。
"""

import pytest

from ocos.knowledge.knowledge_abi import ABI_VERSION, KnowledgeABI
from ocos.knowledge.knowledge_lifecycle import KnowledgeLifecycle, StatusChangeRecord
from ocos.knowledge.knowledge_ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)
from ocos.knowledge.knowledge_registry import (
    AccessMatrix,
    AccessScope,
    KnowledgeRegistry,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def registry():
    r = KnowledgeRegistry()
    r._access_matrix.set_default_permissions("sensor")
    r._access_matrix.set_default_permissions("governance")
    return r


@pytest.fixture
def lifecycle(registry):
    return KnowledgeLifecycle(registry)


@pytest.fixture
def registered_unit(registry):
    u = KnowledgeUnit(
        level=KnowledgeLevel.OBSERVATION,
        status=KnowledgeStatus.CANDIDATE,
        content={"signal": "temp_42"},
        source="sensor_1",
    )
    ok, uid = registry.register(u, owner="sensor")
    assert ok is True
    return uid


@pytest.fixture
def abi(registry, lifecycle):
    return KnowledgeABI(registry, lifecycle)


# ── StatusChangeRecord ───────────────────────────────────────────────────────


class TestStatusChangeRecord:
    def test_create_record(self):
        r = StatusChangeRecord(
            unit_id="u1",
            from_status=KnowledgeStatus.CANDIDATE,
            to_status=KnowledgeStatus.VERIFIED,
            changed_by="admin",
            reason="验证通过",
        )
        assert r.unit_id == "u1"
        assert r.from_status == KnowledgeStatus.CANDIDATE
        assert r.to_status == KnowledgeStatus.VERIFIED
        assert r.changed_by == "admin"
        assert r.reason == "验证通过"

    def test_auto_timestamp(self):
        r = StatusChangeRecord(
            unit_id="u1",
            from_status=KnowledgeStatus.CANDIDATE,
            to_status=KnowledgeStatus.VERIFIED,
            changed_by="admin",
            reason="ok",
        )
        assert "T" in r.timestamp


# ── KnowledgeLifecycle ───────────────────────────────────────────────────────


class TestKnowledgeLifecycleChangeStatus:
    def test_candidate_to_verified(self, lifecycle, registered_unit):
        ok, msg = lifecycle.change_status(
            registered_unit,
            KnowledgeStatus.VERIFIED,
            changed_by="sensor",
            reason="验证完成",
        )
        assert ok is True
        assert "candidate" in msg and "verified" in msg

    def test_verified_to_active(self, lifecycle, registered_unit):
        lifecycle.change_status(registered_unit, KnowledgeStatus.VERIFIED, "sensor")
        ok, msg = lifecycle.change_status(
            registered_unit, KnowledgeStatus.ACTIVE, "sensor"
        )
        assert ok is True

    def test_active_to_deprecated(self, lifecycle, registered_unit):
        lifecycle.change_status(registered_unit, KnowledgeStatus.VERIFIED, "sensor")
        lifecycle.change_status(registered_unit, KnowledgeStatus.ACTIVE, "sensor")
        ok, msg = lifecycle.change_status(
            registered_unit, KnowledgeStatus.DEPRECATED, "sensor"
        )
        assert ok is True

    def test_deprecated_to_archived(self, lifecycle, registered_unit):
        lifecycle.change_status(registered_unit, KnowledgeStatus.VERIFIED, "sensor")
        lifecycle.change_status(registered_unit, KnowledgeStatus.ACTIVE, "sensor")
        lifecycle.change_status(registered_unit, KnowledgeStatus.DEPRECATED, "sensor")
        ok, msg = lifecycle.change_status(
            registered_unit, KnowledgeStatus.ARCHIVED, "sensor"
        )
        assert ok is True

    def test_deprecated_to_active_reactivate(self, lifecycle, registered_unit):
        lifecycle.change_status(registered_unit, KnowledgeStatus.VERIFIED, "sensor")
        lifecycle.change_status(registered_unit, KnowledgeStatus.ACTIVE, "sensor")
        lifecycle.change_status(registered_unit, KnowledgeStatus.DEPRECATED, "sensor")
        ok, msg = lifecycle.change_status(
            registered_unit, KnowledgeStatus.ACTIVE, "sensor"
        )
        assert ok is True

    def test_invalid_transition_rejected(self, lifecycle, registered_unit):
        # CANDIDATE → ARCHIVED 是非法的
        ok, msg = lifecycle.change_status(
            registered_unit, KnowledgeStatus.ARCHIVED, "sensor"
        )
        assert ok is False
        assert "不可从" in msg

    def test_nonexistent_unit(self, lifecycle):
        ok, msg = lifecycle.change_status(
            "no_such_id", KnowledgeStatus.VERIFIED, "sensor"
        )
        assert ok is False
        assert "不存在" in msg


class TestKnowledgeLifecycleConvenience:
    def test_verify(self, lifecycle, registered_unit):
        ok, msg = lifecycle.verify(registered_unit, "sensor")
        assert ok is True

    def test_activate(self, lifecycle, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        ok, msg = lifecycle.activate(registered_unit, "sensor")
        assert ok is True

    def test_deprecate(self, lifecycle, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")
        ok, msg = lifecycle.deprecate(registered_unit, "sensor")
        assert ok is True

    def test_archive(self, lifecycle, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")
        lifecycle.deprecate(registered_unit, "sensor")
        ok, msg = lifecycle.archive(registered_unit, "sensor")
        assert ok is True

    def test_reactivate(self, lifecycle, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")
        lifecycle.deprecate(registered_unit, "sensor")
        ok, msg = lifecycle.reactivate(registered_unit, "sensor")
        assert ok is True


class TestKnowledgeLifecycleVersion:
    def test_version_increments_on_change(self, lifecycle, registered_unit):
        v1 = lifecycle.get_version(registered_unit)
        assert v1 == 1

        lifecycle.verify(registered_unit, "sensor")
        v2 = lifecycle.get_version(registered_unit)
        # update 增加版本号
        assert v2 == 2

    def test_version_none_for_missing(self, lifecycle):
        assert lifecycle.get_version("nope") is None


class TestKnowledgeLifecycleAudit:
    def test_status_history(self, lifecycle, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")

        history = lifecycle.get_status_history()
        assert len(history) == 2
        assert history[0].from_status == KnowledgeStatus.CANDIDATE
        assert history[0].to_status == KnowledgeStatus.VERIFIED

    def test_filter_by_unit(self, lifecycle, registered_unit):
        u2 = KnowledgeUnit(content={"x": "y"})
        ok, uid2 = lifecycle._registry.register(u2, owner="sensor")
        assert ok is True

        lifecycle.verify(registered_unit, "sensor")
        lifecycle.verify(uid2, "sensor")

        filtered = lifecycle.get_status_history(unit_id=registered_unit)
        assert len(filtered) == 1
        assert filtered[0].unit_id == registered_unit

    def test_on_status_change_callback(self, lifecycle, registered_unit):
        triggered: list[StatusChangeRecord] = []

        def listener(record):
            triggered.append(record)

        lifecycle.on_status_change(listener)
        lifecycle.verify(registered_unit, "sensor")

        assert len(triggered) == 1
        assert triggered[0].to_status == KnowledgeStatus.VERIFIED


class TestKnowledgeLifecycleGetActiveUnits:
    def test_get_active_units_empty(self, lifecycle):
        assert lifecycle.get_active_units() == []

    def test_get_active_units(self, lifecycle, registry, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")

        units = lifecycle.get_active_units()
        assert len(units) == 1
        unit_id, owner, level, version = units[0]
        assert owner == "sensor"
        assert level == KnowledgeLevel.OBSERVATION

    def test_get_active_units_filtered(self, lifecycle, registry, registered_unit):
        lifecycle.verify(registered_unit, "sensor")
        lifecycle.activate(registered_unit, "sensor")

        # 按层级过滤
        units = lifecycle.get_active_units(level=KnowledgeLevel.PATTERN)
        assert len(units) == 0

        units = lifecycle.get_active_units(level=KnowledgeLevel.OBSERVATION)
        assert len(units) == 1


# ── KnowledgeABI ─────────────────────────────────────────────────────────────


class TestKnowledgeABI:
    def test_abi_version(self, abi):
        assert abi.abi_version == ABI_VERSION

    def test_submit_observation(self, abi):
        ok, uid = abi.submit_observation(
            {"signal": "high"}, "sensor_1", "sensor"
        )
        assert ok is True
        assert abi.total_knowledge_units == 1

    def test_create_unit(self, abi):
        ok, uid = abi.create_unit(
            KnowledgeLevel.EVIDENCE,
            {"pattern": "freq_spike"},
            "analyzer_1",
            "sensor",
        )
        assert ok is True

    def test_create_unit_no_permission(self, abi):
        ok, msg = abi.create_unit(
            KnowledgeLevel.EVIDENCE,
            {"pattern": "x"},
            "unknown",
            "intruder",
        )
        assert ok is False
        assert "无权写入" in msg

    def test_get_unit(self, abi):
        ok, uid = abi.submit_observation({"v": 1}, "s1", "sensor")
        unit = abi.get_unit(uid, requestor="sensor")
        assert unit is not None
        assert unit["level"] == "observation"
        assert unit["owner"] == "sensor"
        assert unit["version"] == 1

    def test_get_unit_nonexistent(self, abi):
        assert abi.get_unit("nope") is None

    def test_query(self, abi):
        abi.submit_observation({"v": 1}, "s1", "sensor")
        abi.submit_observation({"v": 2}, "s2", "sensor")
        results = abi.query(level=KnowledgeLevel.OBSERVATION)
        assert len(results) == 2

    def test_get_by_level(self, abi):
        abi.create_unit(KnowledgeLevel.OBSERVATION, {"obs": "x"}, "g1", "governance")
        obs = abi.get_by_level(KnowledgeLevel.OBSERVATION)
        assert len(obs) == 1

    def test_get_active_units(self, abi):
        ok, uid = abi.submit_observation({"v": 42}, "s1", "sensor")
        abi.verify(uid, "sensor")
        abi.activate(uid, "sensor")

        active = abi.get_active_units()
        assert len(active) == 1
        assert active[0]["status"] == "active"

    def test_full_lifecycle_via_abi(self, abi):
        # CANDIDATE → VERIFIED → ACTIVE → DEPRECATED → ARCHIVED
        ok, uid = abi.submit_observation({"test": True}, "t1", "sensor")
        assert ok is True

        ok, msg = abi.verify(uid, "sensor")
        assert ok is True

        ok, msg = abi.activate(uid, "sensor")
        assert ok is True

        ok, msg = abi.deprecate(uid, "sensor")
        assert ok is True

        ok, msg = abi.archive(uid, "sensor")
        assert ok is True

        # 验证最终状态
        unit = abi.get_unit(uid, requestor="sensor")
        assert unit["status"] == "archived"

    def test_update_unit(self, abi):
        ok, uid = abi.submit_observation({"v": 1}, "s1", "sensor")
        ok, msg = abi.update_unit(uid, "sensor", content={"v": 2})
        assert ok is True
        unit = abi.get_unit(uid, requestor="sensor")
        assert unit["version"] == 2
        assert unit["content"] == {"v": 2}

    def test_get_status_history(self, abi):
        ok, uid = abi.submit_observation({"x": 1}, "s1", "sensor")
        abi.verify(uid, "sensor")
        abi.activate(uid, "sensor")

        history = abi.get_status_history()
        assert len(history) >= 2

    def test_get_owners(self, abi):
        abi.submit_observation({"a": 1}, "s1", "sensor")
        abi.create_unit(KnowledgeLevel.OBSERVATION, {"b": 2}, "g1", "governance")
        owners = abi.get_owners()
        assert "sensor" in owners
        assert "governance" in owners

    def test_elevate_via_abi(self, abi, registry):
        # 给 sensor EVIDENCE 写入权限 + 自定义提升策略
        registry._access_matrix.set_permission(
            "sensor", KnowledgeLevel.EVIDENCE, True, True
        )
        from ocos.knowledge.promotion_rules import (
            PromotionPolicy,
            PromotionRuleEngine,
        )
        policy = PromotionPolicy(
            allowed_sources=["sensor"],
        )
        abi._promotion.register_policy(
            KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE, policy
        )

        ok, uid = abi.submit_observation({"pattern": "repeated"}, "s1", "sensor")
        assert ok is True

        # 先验证并激活
        abi.verify(uid, "sensor")
        abi.activate(uid, "sensor")

        ok, msg = abi.elevate(uid, KnowledgeLevel.EVIDENCE, "sensor")
        assert ok is True, f"提升失败: {msg}"

        # 验证提升后的单元
        evidence_units = abi.get_by_level(KnowledgeLevel.EVIDENCE, requestor="sensor")
        assert len(evidence_units) == 1
        eu = evidence_units[0]
        assert eu["parent_id"] == uid
        assert eu["level"] == "evidence"
        assert eu["status"] == "candidate"

    def test_can_elevate_check(self, abi):
        ok, uid = abi.submit_observation({"p": "x"}, "s1", "sensor")
        eligible, errors = abi.can_elevate(uid, KnowledgeLevel.EVIDENCE)
        assert eligible is False  # 默认没有 elevate 权限但 can_elevate 会检查...实际上can_elevate调用的是promotion engine
        # 实际上 need to check what can_elevate does

    def test_get_unit_respects_scope(self, abi):
        ok, uid = abi.create_unit(
            KnowledgeLevel.OBSERVATION,
            {"secret": True},
            "s1",
            "sensor",
            scope=AccessScope.PRIVATE,
        )
        # sensor 自己可以
        assert abi.get_unit(uid, requestor="sensor") is not None
        # others cannot
        assert abi.get_unit(uid, requestor="other") is None
