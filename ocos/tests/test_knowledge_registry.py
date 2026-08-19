"""
M1 测试 — Knowledge Ownership: Registry + AccessMatrix。
"""

import pytest

from ocos.knowledge.knowledge_ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)
from ocos.knowledge.knowledge_registry import (
    AccessMatrix,
    AccessScope,
    KnowledgeRegistry,
    OwnershipEntry,
)


# ── AccessScope ─────────────────────────────────────────────────────────────


class TestAccessScope:
    def test_has_three_scopes(self):
        assert len(AccessScope) == 3

    def test_public_allows_anyone(self):
        assert AccessScope.PUBLIC.value == "public"

    def test_protected_allows_owner(self):
        assert AccessScope.PROTECTED.value == "protected"

    def test_private_restricts_to_owner(self):
        assert AccessScope.PRIVATE.value == "private"


# ── AccessMatrix ────────────────────────────────────────────────────────────


class TestAccessMatrix:
    def test_default_permissions(self):
        matrix = AccessMatrix()
        matrix.set_default_permissions("vision_sensor")
        assert matrix.can_read("vision_sensor", KnowledgeLevel.OBSERVATION) is True
        assert matrix.can_write("vision_sensor", KnowledgeLevel.OBSERVATION) is True
        assert matrix.can_write("vision_sensor", KnowledgeLevel.POLICY) is False
        assert matrix.can_elevate("vision_sensor", KnowledgeLevel.OBSERVATION) is True

    def test_default_no_write_on_high_levels(self):
        matrix = AccessMatrix()
        matrix.set_default_permissions("sensor")
        for level in [KnowledgeLevel.PATTERN, KnowledgeLevel.PRINCIPLE, KnowledgeLevel.POLICY]:
            assert matrix.can_write("sensor", level) is False

    def test_custom_permission(self):
        matrix = AccessMatrix()
        matrix.set_permission("admin", KnowledgeLevel.POLICY, True, True, True)
        assert matrix.can_read("admin", KnowledgeLevel.POLICY) is True
        assert matrix.can_write("admin", KnowledgeLevel.POLICY) is True
        assert matrix.can_elevate("admin", KnowledgeLevel.POLICY) is True

    def test_unset_permission_defaults_false(self):
        matrix = AccessMatrix()
        assert matrix.can_read("unknown", KnowledgeLevel.OBSERVATION) is False
        assert matrix.can_write("unknown", KnowledgeLevel.OBSERVATION) is False

    def test_wildcard_permission(self):
        matrix = AccessMatrix()
        matrix.set_wildcard_permission(KnowledgeLevel.OBSERVATION, can_read=True)
        assert matrix.can_read("any_module", KnowledgeLevel.OBSERVATION) is True
        assert matrix.can_write("any_module", KnowledgeLevel.OBSERVATION) is False

    def test_specific_overrides_wildcard(self):
        """具体设置优先于通配符。"""
        matrix = AccessMatrix()
        matrix.set_wildcard_permission(KnowledgeLevel.OBSERVATION, can_read=True)
        matrix.set_permission("restricted", KnowledgeLevel.OBSERVATION, can_read=False)
        assert matrix.can_read("any_module", KnowledgeLevel.OBSERVATION) is True
        assert matrix.can_read("restricted", KnowledgeLevel.OBSERVATION) is False


class TestAccessMatrixReadCheck:
    def test_public_accessible_by_anyone(self):
        matrix = AccessMatrix()
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        entry = OwnershipEntry(unit=unit, owner="mod_a", scope=AccessScope.PUBLIC)
        assert matrix.check_read_access(entry, "anyone") is True

    def test_private_only_owner(self):
        matrix = AccessMatrix()
        unit = KnowledgeUnit()
        entry = OwnershipEntry(unit=unit, owner="mod_a", scope=AccessScope.PRIVATE)
        assert matrix.check_read_access(entry, "mod_a") is True
        assert matrix.check_read_access(entry, "other") is False

    def test_protected_owner_can_read(self):
        matrix = AccessMatrix()
        unit = KnowledgeUnit()
        entry = OwnershipEntry(unit=unit, owner="mod_a", scope=AccessScope.PROTECTED)
        assert matrix.check_read_access(entry, "mod_a") is True

    def test_protected_other_can_read_if_matrix_allows(self):
        matrix = AccessMatrix()
        matrix.set_default_permissions("mod_b")
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        entry = OwnershipEntry(unit=unit, owner="mod_a", scope=AccessScope.PROTECTED)
        # mod_b 有权读取 OBSERVATION
        assert matrix.check_read_access(entry, "mod_b") is True

    def test_protected_other_blocked_by_matrix(self):
        matrix = AccessMatrix()
        unit = KnowledgeUnit(level=KnowledgeLevel.POLICY)
        entry = OwnershipEntry(unit=unit, owner="mod_a", scope=AccessScope.PROTECTED)
        # 没有设置任何权限，其他模块不能读取 POLICY
        assert matrix.check_read_access(entry, "mod_b") is False


# ── KnowledgeRegistry ──────────────────────────────────────────────────────


class TestKnowledgeRegistryRegister:
    def test_register_new_unit(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        ok, msg = registry.register(unit, owner="sensor")
        assert ok is True
        assert msg == unit.unit_id
        assert registry.total_count == 1

    def test_register_duplicate_id_rejected(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        registry.register(unit, owner="sensor")
        ok, msg = registry.register(unit, owner="sensor")
        assert ok is False
        assert "已存在" in msg

    def test_register_without_write_permission(self):
        registry = KnowledgeRegistry()
        # 未设置权限 → write 默认为 False
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        ok, msg = registry.register(unit, owner="unauthorized")
        assert ok is False
        assert "无权写入" in msg

    def test_register_with_different_owners(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("mod_a")
        registry._access_matrix.set_default_permissions("mod_b")
        u1 = KnowledgeUnit(content={"k": "v1"})
        u2 = KnowledgeUnit(content={"k": "v2"})
        registry.register(u1, owner="mod_a")
        registry.register(u2, owner="mod_b")
        assert registry.total_count == 2


class TestKnowledgeRegistryUpdate:
    def test_owner_can_update(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION, source="v1")
        registry.register(unit, owner="sensor")
        ok, msg = registry.update(unit.unit_id, "sensor", source="v2")
        assert ok is True
        updated = registry.get(unit.unit_id, requestor="sensor")
        assert updated is not None
        assert updated.unit.source == "v2"
        assert updated.unit.version == 2

    def test_non_owner_cannot_update(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("mod_a")
        unit = KnowledgeUnit()
        registry.register(unit, owner="mod_a")
        ok, msg = registry.update(unit.unit_id, "mod_b", source="v2")
        assert ok is False
        assert "无权修改" in msg

    def test_update_nonexistent_unit(self):
        registry = KnowledgeRegistry()
        ok, msg = registry.update("nonexistent", "anyone", source="v2")
        assert ok is False
        assert "不存在" in msg


class TestKnowledgeRegistryRemove:
    def test_owner_can_remove(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit()
        registry.register(unit, owner="sensor")
        ok, msg = registry.remove(unit.unit_id, "sensor")
        assert ok is True
        assert registry.total_count == 0

    def test_non_owner_cannot_remove(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("mod_a")
        unit = KnowledgeUnit()
        registry.register(unit, owner="mod_a")
        ok, msg = registry.remove(unit.unit_id, "mod_b")
        assert ok is False
        assert "无权删除" in msg


class TestKnowledgeRegistryQuery:
    def test_get_returns_entry(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit()
        registry.register(unit, owner="sensor")
        entry = registry.get(unit.unit_id)
        assert entry is not None
        assert entry.owner == "sensor"

    def test_get_nonexistent(self):
        registry = KnowledgeRegistry()
        assert registry.get("nope") is None

    def test_get_with_scope_filter_blocks_private(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        unit = KnowledgeUnit()
        registry.register(unit, owner="sensor", scope=AccessScope.PRIVATE)
        # 其他人不能读取 PRIVATE
        assert registry.get(unit.unit_id, requestor="other") is None
        # owner 可以
        assert registry.get(unit.unit_id, requestor="sensor") is not None

    def test_get_by_level(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        u1 = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        u2 = KnowledgeUnit(level=KnowledgeLevel.EVIDENCE)
        registry.register(u1, owner="sensor")
        registry.register(u2, owner="sensor")
        observations = registry.get_by_level(KnowledgeLevel.OBSERVATION)
        assert len(observations) == 1
        assert observations[0].unit.unit_id == u1.unit_id

    def test_get_by_owner(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("mod_a")
        registry._access_matrix.set_default_permissions("mod_b")
        registry.register(KnowledgeUnit(), owner="mod_a")
        registry.register(KnowledgeUnit(), owner="mod_b")
        registry.register(KnowledgeUnit(), owner="mod_a")
        assert len(registry.get_by_owner("mod_a")) == 2
        assert len(registry.get_by_owner("mod_b")) == 1

    def test_get_by_status(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        u1 = KnowledgeUnit(status=KnowledgeStatus.CANDIDATE)
        u2 = KnowledgeUnit(status=KnowledgeStatus.ACTIVE)
        registry.register(u1, owner="sensor")
        registry.register(u2, owner="sensor")
        actives = registry.get_by_status(KnowledgeStatus.ACTIVE)
        assert len(actives) == 1

    def test_search_combined(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        # 给 PATTERN 层级写权限
        registry._access_matrix.set_permission(
            "sensor", KnowledgeLevel.PATTERN, True, True
        )
        u = KnowledgeUnit(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.ACTIVE,
        )
        registry.register(u, owner="sensor", tags={"important"})
        result = registry.search(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.ACTIVE,
            tags={"important"},
        )
        assert len(result) == 1

    def test_get_owners(self):
        registry = KnowledgeRegistry()
        registry._access_matrix.set_default_permissions("sensor")
        registry._access_matrix.set_default_permissions("governance")
        registry.register(KnowledgeUnit(), owner="sensor")
        registry.register(KnowledgeUnit(), owner="governance")
        assert "sensor" in registry.get_owners()
        assert "governance" in registry.get_owners()
