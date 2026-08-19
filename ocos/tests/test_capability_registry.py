"""
D1 Capability Registry — 单元测试。

覆盖维度（8 类，54 个测试）：
1. CapabilityDescriptor 冻结与默认值
2. CapabilityType 枚举值
3. Register（基本 + 重复版本递增 + 标准调用方式）
4. Unregister（存在/不存在/清除索引）
5. Get / FindByName 查询
6. Query（类型/标签/名称子串/组合）
7. 管理（count / list_by_type / list_all_types / reset）
8. 边缘情况（无效类型、空标签、空名称）
"""

import uuid

import pytest

from ocos.platform.capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry,
    CapabilityType,
    _validate_type,
)
from ocos.kernel.abi import SCHEMA_VERSION


# =========================================================================
# 1. CapabilityDescriptor 冻结与默认值
# =========================================================================

class TestDescriptorFrozen:
    """CapabilityDescriptor 必须是 frozen dataclass。"""

    def test_is_frozen(self):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            cd = CapabilityDescriptor()
            cd.name = "mutated"

    def test_default_values(self):
        cd = CapabilityDescriptor()
        assert isinstance(cd.capability_id, str) and len(cd.capability_id) == 32
        assert cd.type == CapabilityType.TOOL.value
        assert cd.name == ""
        assert cd.description == ""
        assert cd.tags == ()
        assert cd.version == "0.1.0"
        assert cd.entry_point == ""
        assert cd.metadata == {}
        assert cd.schema_version == SCHEMA_VERSION

    def test_custom_values(self):
        cd = CapabilityDescriptor(
            capability_id="custom-id-001",
            type=CapabilityType.PLUGIN.value,
            name="test-plugin",
            description="A test plugin",
            tags=("test", "plugin"),
            version="2.0.0",
            entry_point="test:Plugin",
            metadata={"author": "me"},
        )
        assert cd.capability_id == "custom-id-001"
        assert cd.type == "plugin"
        assert cd.name == "test-plugin"
        assert cd.description == "A test plugin"
        assert cd.tags == ("test", "plugin")
        assert cd.version == "2.0.0"
        assert cd.entry_point == "test:Plugin"
        assert cd.metadata == {"author": "me"}

    def test_capability_id_default_is_hex(self):
        cd = CapabilityDescriptor()
        # uuid.hex is 32 hex chars
        assert len(cd.capability_id) == 32
        assert all(c in "0123456789abcdef" for c in cd.capability_id)

    def test_tag_set_property(self):
        cd = CapabilityDescriptor(tags=("a", "b", "c"))
        assert cd.tag_set == {"a", "b", "c"}

    def test_tag_set_empty_tags(self):
        cd = CapabilityDescriptor()
        assert cd.tag_set == set()

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="无效能力类型"):
            CapabilityDescriptor(type="invalid_type")


# =========================================================================
# 2. CapabilityType 枚举值
# =========================================================================

class TestCapabilityType:
    """CapabilityType 枚举必须包含三种类型。"""

    def test_has_three_types(self):
        assert len(CapabilityType) == 3

    def test_values(self):
        assert CapabilityType.TOOL.value == "tool"
        assert CapabilityType.PLUGIN.value == "plugin"
        assert CapabilityType.MODEL.value == "model"

    def test_all_values_valid(self):
        for t in CapabilityType:
            _validate_type(t.value)  # 不抛出异常


# =========================================================================
# 3. Register
# =========================================================================

class TestRegister:
    """注册能力的基本行为。"""

    def test_register_with_descriptor(self):
        registry = CapabilityRegistry()
        cd = CapabilityDescriptor(name="test-tool", type=CapabilityType.TOOL.value)
        cid = registry.register(descriptor=cd)
        assert cid == cd.capability_id
        assert registry.count == 1

    def test_register_with_kwargs(self):
        registry = CapabilityRegistry()
        cid = registry.register(
            type=CapabilityType.PLUGIN.value,
            name="test-plugin",
            description="My plugin",
        )
        assert isinstance(cid, str) and len(cid) == 32
        assert registry.count == 1

    def test_register_default_type_is_tool(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="default-tool")
        stored = registry.get(cid)
        assert stored is not None
        assert stored.type == CapabilityType.TOOL.value

    def test_register_increments_count(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="a")
        cid2 = registry.register(name="b")
        cid3 = registry.register(name="c")
        assert registry.count == 3

    def test_register_same_name_auto_version_increment(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="same", version="1.0.0")
        cid2 = registry.register(name="same", version="1.0.0")
        assert cid1 != cid2
        d1 = registry.get(cid1)
        d2 = registry.get(cid2)
        assert d1 is not None and d2 is not None
        assert d1.version == "1.0.0"
        assert d2.version == "1.0.1"

    def test_register_same_name_different_version_no_increment(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="multi", version="1.0.0")
        cid2 = registry.register(name="multi", version="2.0.0")
        d1 = registry.get(cid1)
        d2 = registry.get(cid2)
        assert d1 is not None and d2 is not None
        assert d1.version == "1.0.0"
        assert d2.version == "2.0.0"

    def test_register_with_tags(self):
        registry = CapabilityRegistry()
        cid = registry.register(
            name="tagged",
            tags=("tag1", "tag2", "tag3"),
        )
        stored = registry.get(cid)
        assert stored is not None
        assert stored.tags == ("tag1", "tag2", "tag3")

    def test_register_with_metadata(self):
        registry = CapabilityRegistry()
        cid = registry.register(
            name="with-meta",
            metadata={"key": "value", "count": 42},
        )
        stored = registry.get(cid)
        assert stored is not None
        assert stored.metadata == {"key": "value", "count": 42}


# =========================================================================
# 4. Unregister
# =========================================================================

class TestUnregister:
    """注销能力的行为。"""

    def test_unregister_existing(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="to-remove")
        assert registry.unregister(cid) is True
        assert registry.count == 0
        assert registry.get(cid) is None

    def test_unregister_nonexistent(self):
        registry = CapabilityRegistry()
        assert registry.unregister("nonexistent") is False

    def test_unregister_clears_name_index(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="unique")
        registry.unregister(cid)
        assert registry.find_by_name("unique") is None

    def test_unregister_preserves_other_entries(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="a")
        cid2 = registry.register(name="b")
        registry.unregister(cid1)
        assert registry.count == 1
        assert registry.get(cid2) is not None

    def test_unregister_versioned_clears_only_one(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="ver", version="1.0.0")
        cid2 = registry.register(name="ver", version="1.0.0")
        registry.unregister(cid1)
        assert registry.count == 1
        assert registry.get(cid2) is not None


# =========================================================================
# 5. Get / FindByName
# =========================================================================

class TestGet:
    """按 ID 查询。"""

    def test_get_existing(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="found")
        stored = registry.get(cid)
        assert stored is not None
        assert stored.name == "found"

    def test_get_nonexistent(self):
        registry = CapabilityRegistry()
        assert registry.get("not_here") is None

    def test_get_returns_same_descriptor_values(self):
        registry = CapabilityRegistry()
        cd = CapabilityDescriptor(
            name="roundtrip",
            type=CapabilityType.MODEL.value,
            version="3.0.0",
            tags=("ml",),
        )
        cid = registry.register(descriptor=cd)
        stored = registry.get(cid)
        assert stored is not None
        assert stored.name == "roundtrip"
        assert stored.type == "model"
        assert stored.version == "3.0.0"
        assert stored.tags == ("ml",)

    def test_get_after_unregister_returns_none(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="temp")
        registry.unregister(cid)
        assert registry.get(cid) is None


class TestFindByName:
    """按名称查询。"""

    def test_find_by_name_existing(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="my-tool")
        found = registry.find_by_name("my-tool")
        assert found is not None
        assert found.capability_id == cid

    def test_find_by_name_nonexistent(self):
        registry = CapabilityRegistry()
        assert registry.find_by_name("nope") is None

    def test_find_by_name_returns_latest_version(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="latest", version="1.0.0")
        cid2 = registry.register(name="latest", version="1.0.0")
        found = registry.find_by_name("latest")
        assert found is not None
        assert found.capability_id == cid2
        assert found.version == "1.0.1"

    def test_find_by_name_empty_name(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="")
        assert registry.find_by_name("") is not None


class TestGetAllVersions:
    """获取指定名称的所有版本。"""

    def test_all_versions_empty(self):
        registry = CapabilityRegistry()
        assert registry.get_all_versions("nonexistent") == []

    def test_all_versions_single(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="single", version="1.0.0")
        versions = registry.get_all_versions("single")
        assert len(versions) == 1
        assert versions[0].capability_id == cid

    def test_all_versions_multiple(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="multi", version="1.0.0")
        cid2 = registry.register(name="multi", version="1.0.0")
        cid3 = registry.register(name="multi", version="7.0.0")
        versions = registry.get_all_versions("multi")
        assert len(versions) == 3
        vids = [v.capability_id for v in versions]
        assert cid1 in vids
        assert cid2 in vids
        assert cid3 in vids

    def test_all_versions_after_unregister(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="ver", version="1.0.0")
        cid2 = registry.register(name="ver", version="1.0.0")
        registry.unregister(cid1)
        versions = registry.get_all_versions("ver")
        assert len(versions) == 1
        assert versions[0].capability_id == cid2


# =========================================================================
# 6. Query
# =========================================================================

class TestQuery:
    """多维度查询。"""

    def test_query_no_filters_returns_all(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="a", type=CapabilityType.TOOL.value)
        cid2 = registry.register(name="b", type=CapabilityType.PLUGIN.value)
        results = registry.query()
        assert len(results) == 2

    def test_query_by_type(self):
        registry = CapabilityRegistry()
        registry.register(name="tool1", type=CapabilityType.TOOL.value)
        registry.register(name="tool2", type=CapabilityType.TOOL.value)
        registry.register(name="plug1", type=CapabilityType.PLUGIN.value)
        results = registry.query(type=CapabilityType.TOOL.value)
        assert len(results) == 2
        assert all(r.type == "tool" for r in results)

    def test_query_by_tags_intersection(self):
        registry = CapabilityRegistry()
        registry.register(name="a", tags=("tag1", "tag2"))
        registry.register(name="b", tags=("tag1",))
        registry.register(name="c", tags=("tag2", "tag3"))
        results = registry.query(tags=["tag1"])
        assert len(results) == 2  # a + b
        assert {r.name for r in results} == {"a", "b"}

    def test_query_multiple_tags_intersection(self):
        registry = CapabilityRegistry()
        registry.register(name="a", tags=("tag1", "tag2"))
        registry.register(name="b", tags=("tag1",))
        registry.register(name="c", tags=("tag1", "tag2", "tag3"))
        results = registry.query(tags=["tag1", "tag2"])
        assert len(results) == 2  # a + c
        assert {r.name for r in results} == {"a", "c"}

    def test_query_by_name_contains(self):
        registry = CapabilityRegistry()
        registry.register(name="hello-world")
        registry.register(name="hello-kit")
        registry.register(name="goodbye")
        results = registry.query(name_contains="hello")
        assert len(results) == 2
        assert {r.name for r in results} == {"hello-world", "hello-kit"}

    def test_query_combined_filters(self):
        registry = CapabilityRegistry()
        registry.register(name="tool-a", type=CapabilityType.TOOL.value, tags=("nlp",))
        registry.register(name="tool-b", type=CapabilityType.TOOL.value, tags=("vision",))
        registry.register(name="plug-a", type=CapabilityType.PLUGIN.value, tags=("nlp",))
        results = registry.query(
            type=CapabilityType.TOOL.value,
            tags=["nlp"],
            name_contains="tool",
        )
        assert len(results) == 1
        assert results[0].name == "tool-a"

    def test_query_no_match(self):
        registry = CapabilityRegistry()
        registry.register(name="tool", type=CapabilityType.TOOL.value)
        results = registry.query(type=CapabilityType.PLUGIN.value)
        assert results == []

    def test_query_empty_registry(self):
        registry = CapabilityRegistry()
        assert registry.query() == []

    def test_query_tags_nonexistent(self):
        registry = CapabilityRegistry()
        registry.register(name="x", tags=("a",))
        results = registry.query(tags=["nonexistent"])
        assert results == []


class TestListByType:
    """按类型列出的便捷方法。"""

    def test_list_by_type(self):
        registry = CapabilityRegistry()
        cid1 = registry.register(name="t1", type=CapabilityType.TOOL.value)
        cid2 = registry.register(name="t2", type=CapabilityType.TOOL.value)
        results = registry.list_by_type(CapabilityType.TOOL.value)
        assert len(results) == 2

    def test_list_by_type_empty(self):
        registry = CapabilityRegistry()
        assert registry.list_by_type(CapabilityType.PLUGIN.value) == []

    def test_list_by_type_is_same_as_query(self):
        registry = CapabilityRegistry()
        registry.register(name="tool", type=CapabilityType.TOOL.value)
        assert registry.list_by_type("tool") == registry.query(type="tool")


class TestListAllTypes:
    """列出所有能力类型。"""

    def test_list_all_types(self):
        registry = CapabilityRegistry()
        registry.register(name="tool", type=CapabilityType.TOOL.value)
        registry.register(name="plug", type=CapabilityType.PLUGIN.value)
        types = registry.list_all_types()
        assert "tool" in types
        assert "plugin" in types
        assert "model" not in types  # no model registered

    def test_list_all_types_empty(self):
        registry = CapabilityRegistry()
        assert registry.list_all_types() == []


# =========================================================================
# 7. 管理
# =========================================================================

class TestManagement:
    """管理功能（count / reset）。"""

    def test_count_starts_zero(self):
        registry = CapabilityRegistry()
        assert registry.count == 0

    def test_count_after_register(self):
        registry = CapabilityRegistry()
        registry.register(name="a")
        registry.register(name="b")
        assert registry.count == 2

    def test_count_after_unregister(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="temp")
        registry.unregister(cid)
        assert registry.count == 0

    def test_reset_clears_all(self):
        registry = CapabilityRegistry()
        registry.register(name="a")
        registry.register(name="b")
        registry.register(name="c")
        registry.reset()
        assert registry.count == 0
        assert registry.query() == []
        assert registry.find_by_name("a") is None

    def test_reset_empty_not_raises(self):
        registry = CapabilityRegistry()
        registry.reset()
        assert registry.count == 0


# =========================================================================
# 8. 边缘情况
# =========================================================================

class TestEdgeCases:
    """边缘情况测试。"""

    def test_validate_type_valid(self):
        # 不应抛出异常
        _validate_type("tool")
        _validate_type("plugin")
        _validate_type("model")

    def test_validate_type_invalid(self):
        with pytest.raises(ValueError, match="无效能力类型"):
            _validate_type("invalid")

    def test_register_duplicate_id(self):
        registry = CapabilityRegistry()
        cd1 = CapabilityDescriptor(capability_id="same-id", name="first")
        cd2 = CapabilityDescriptor(capability_id="same-id", name="second")
        cid1 = registry.register(descriptor=cd1)
        cid2 = registry.register(descriptor=cd2)
        # 同一 ID 会被覆盖（dict key 行为）
        assert cid1 == cid2 == "same-id"
        # 最后注册的保留
        stored = registry.get("same-id")
        assert stored is not None
        assert stored.name == "second"

    def test_register_empty_tags(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="no-tags", tags=())
        stored = registry.get(cid)
        assert stored is not None
        assert stored.tags == ()

    def test_register_empty_entry_point(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="no-ep", entry_point="")
        stored = registry.get(cid)
        assert stored is not None
        assert stored.entry_point == ""

    def test_register_unicode_name(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="测试插件")
        stored = registry.get(cid)
        assert stored is not None
        assert stored.name == "测试插件"

    def test_query_tags_empty_list_returns_all(self):
        registry = CapabilityRegistry()
        registry.register(name="a")
        registry.register(name="b")
        results = registry.query(tags=[])
        assert len(results) == 2

    def test_get_all_versions_empty_after_unregister_last(self):
        registry = CapabilityRegistry()
        cid = registry.register(name="last")
        registry.unregister(cid)
        assert registry.get_all_versions("last") == []

    def test_register_twice_with_metadata_preserved(self):
        """验证同名注册时 metadata 不交叉污染。"""
        registry = CapabilityRegistry()
        cid1 = registry.register(name="dup", metadata={"owner": "alice"})
        cid2 = registry.register(name="dup", metadata={"owner": "bob"})
        d1 = registry.get(cid1)
        d2 = registry.get(cid2)
        assert d1 is not None and d2 is not None
        assert d1.metadata == {"owner": "alice"}
        assert d2.metadata == {"owner": "bob"}
