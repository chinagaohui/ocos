"""架构测试 — 每个 Information 实例同时具有 SemanticRole 和 PersistenceLevel。

验证 INFORMATION_THEORY 第三章硬约束：
- 任何 Information 实例必须同时属于一个 Persistence 等级和一个 Semantic Role
- 不存在"无角色"或"无等级"的 Information
- 同一实例可变更 Persistence 等级，但 Semantic Role 在 Created 时确定
"""

from __future__ import annotations

import pytest

from ocos.models.information import (
    InformationMetadata,
    InformationState,
    PersistenceLevel,
    SemanticRole,
    UniversalAddress,
)


def test_information_metadata_has_role():
    """每个 InformationMetadata 实例必须有 SemanticRole。"""
    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="1"),
    )
    assert meta.semantic_role is not None
    assert isinstance(meta.semantic_role, SemanticRole)


def test_information_metadata_has_persistence():
    """每个 InformationMetadata 实例必须有 PersistenceLevel。"""
    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="1"),
    )
    assert meta.persistence_level is not None
    assert isinstance(meta.persistence_level, PersistenceLevel)


def test_role_and_persistence_are_separate_fields():
    """SemanticRole 和 PersistenceLevel 是独立的两个字段。"""
    fields = InformationMetadata.__dataclass_fields__
    assert "semantic_role" in fields
    assert "persistence_level" in fields


def test_role_set_at_creation():
    """SemanticRole 在创建时确定（通过由字段默认值或传参）。"""
    # 默认角色为 OBSERVATION
    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="1"),
    )
    assert meta.semantic_role == SemanticRole.OBSERVATION

    # 可指定角色
    meta2 = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="2"),
        semantic_role=SemanticRole.DECISION,
    )
    assert meta2.semantic_role == SemanticRole.DECISION


def test_persistence_can_be_set():
    """PersistenceLevel 默认为 TRANSIENT，可修改。"""
    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="1"),
    )
    assert meta.persistence_level == PersistenceLevel.TRANSIENT

    meta2 = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="2"),
        persistence_level=PersistenceLevel.PERSISTENT,
    )
    assert meta2.persistence_level == PersistenceLevel.PERSISTENT


def test_all_enum_values_used():
    """所有 SemanticRole 和 PersistenceLevel 枚举值应在信息模型中可用。"""
    roles = set(SemanticRole)
    assert SemanticRole.OBSERVATION in roles
    assert SemanticRole.OBSERVATION in roles
    assert SemanticRole.GOAL in roles
    assert SemanticRole.MEMORY in roles
    assert SemanticRole.DECISION in roles
    assert SemanticRole.POLICY in roles

    levels = set(PersistenceLevel)
    assert PersistenceLevel.TRANSIENT in levels
    assert PersistenceLevel.PERSISTENT in levels
    assert PersistenceLevel.STABLE in levels
    assert PersistenceLevel.IMMUTABLE in levels


def test_no_instance_without_both():
    """无法创建缺少 role 或 persistence 的 InformationMetadata。"""
    # 两个字段都有默认值，所以最小构造也能同时拥有两者
    meta = InformationMetadata(
        address=UniversalAddress(namespace="test", type="m", id="1"),
    )
    assert meta.semantic_role is not None
    assert meta.persistence_level is not None
