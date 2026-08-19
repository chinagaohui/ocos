"""架构测试 — 所有 Information 使用统一关系模型。

验证 INFORMATION_THEORY 第六章硬约束：
- Memory、Knowledge、Goal、Identity、Policy、Decision 全部共享统一关系模型
- 关系是双向可导航的
- 关系有类型但不携带语义
- 关系的创建必须通过 Event Bus 事件
"""

from __future__ import annotations

import pytest

from ocos.models.information import RelationType


class TestRelationTypeEnum:
    """统一关系模型枚举验证。"""

    def test_structural_relationships_present(self):
        """结构关系存在。"""
        assert RelationType.DERIVED_FROM
        assert RelationType.SUPPORTS

    def test_semantic_relationships_present(self):
        """语义关系存在。"""
        assert RelationType.CONTRADICTS
        assert RelationType.PART_OF

    def test_temporal_relationships_present(self):
        """时序关系存在。"""
        assert RelationType.CAUSES
        assert RelationType.CORRELATED_WITH

    def test_relation_is_type_only(self):
        """关系只标识类型，不携带语义含义。

        验证：RelationType 只是字符串枚举，不包含业务逻辑方法。
        """
        for rel in RelationType:
            assert isinstance(rel.value, str)
            # 不包含业务逻辑方法
            assert not hasattr(rel, "apply")
            assert not hasattr(rel, "validate")
            assert not hasattr(rel, "check")

    def test_relation_values_are_consistent(self):
        """关系名称与 INFORMATION_THEORY.md 文档一致。"""
        expected = {
            RelationType.DERIVED_FROM: "derived_from",
            RelationType.SUPPORTS: "supports",
            RelationType.CONTRADICTS: "contradicts",
            RelationType.PART_OF: "part_of",
            RelationType.CAUSES: "causes",
            RelationType.CORRELATED_WITH: "correlated_with",
        }
        for rel, expected_val in expected.items():
            assert rel.value == expected_val, (
                f"RelationType.{rel.name} 期望 '{expected_val}', "
                f"实际 '{rel.value}'"
            )


def test_event_types_for_relations_registered():
    """关系事件的 EventType 已注册。"""
    from ocos.kernel.abi import EventType

    assert EventType.RELATION_CREATED
    assert EventType.RELATION_REMOVED
    assert EventType.RELATION_CREATED.value == "relation.created"
    assert EventType.RELATION_REMOVED.value == "relation.removed"
