"""
Phase 17.4 — InformationState 状态机测试
基于 INFORMATION_THEORY.md 五态：CREATED → VALIDATED → REFERENCED → DEPRECATED → ARCHIVED

状态转换矩阵:
| from \\ to    | CREATED | VALIDATED | REFERENCED | DEPRECATED | ARCHIVED |
|---------------|---------|-----------|------------|------------|----------|
| CREATED       |    —    |    ✓      |     ✗      |     ✗      |    ✗    |
| VALIDATED     |    ✗    |    —      |     ✓      |     ✓      |    ✓    |
| REFERENCED    |    ✗    |    ✗      |     —      |     ✓      |    ✓    |
| DEPRECATED    |    ✗    |    ✗      |     ✗      |     —      |    ✓    |
| ARCHIVED      |    ✗    |    ✗      |     ✗      |     ✗      |    —    |
"""

from __future__ import annotations

import pytest

from ocos.models.information import InformationState


class TestInformationStateMachine:
    """验证 Theory 五态生命周期转换规则。"""

    def test_created_to_validated(self):
        """CREATED → VALIDATED：创建后通过验证可进入活跃态。"""
        assert InformationState.CREATED.can_transition_to(InformationState.VALIDATED)

    def test_created_to_deprecated_allowed(self):
        """CREATED → DEPRECATED：验证失败或弃用时直接废弃（Theory 允许 S_C→S_D）。"""
        assert InformationState.CREATED.can_transition_to(InformationState.DEPRECATED)

    def test_created_to_archived_rejected(self):
        """CREATED → ARCHIVED：未验证不可直接归档。"""
        assert not InformationState.CREATED.can_transition_to(InformationState.ARCHIVED)

    def test_validated_to_referenced(self):
        """VALIDATED → REFERENCED：被引用时进入。"""
        assert InformationState.VALIDATED.can_transition_to(InformationState.REFERENCED)

    def test_validated_to_deprecated(self):
        """VALIDATED → DEPRECATED：过期/遗忘/晋升后废弃。"""
        assert InformationState.VALIDATED.can_transition_to(InformationState.DEPRECATED)

    def test_validated_to_archived(self):
        """VALIDATED → ARCHIVED：直接归档（跳过 REFERENCED）。"""
        assert InformationState.VALIDATED.can_transition_to(InformationState.ARCHIVED)

    def test_validated_rejects_created(self):
        """VALIDATED → CREATED：单向退化不可逆。"""
        assert not InformationState.VALIDATED.can_transition_to(InformationState.CREATED)

    def test_referenced_to_deprecated(self):
        """REFERENCED → DEPRECATED：引用消失后废弃（Theory 标准路径）。"""
        assert InformationState.REFERENCED.can_transition_to(InformationState.DEPRECATED)

    def test_referenced_to_archived_rejected(self):
        """REFERENCED → ARCHIVED：需先经 DEPRECATED（Theory 不允许直接 S_R→S_A）。"""
        assert not InformationState.REFERENCED.can_transition_to(InformationState.ARCHIVED)

    def test_referenced_rejects_created(self):
        """REFERENCED → CREATED：不可回退。"""
        assert not InformationState.REFERENCED.can_transition_to(InformationState.CREATED)

    def test_deprecated_to_archived(self):
        """DEPRECATED → ARCHIVED：最后一步归档。"""
        assert InformationState.DEPRECATED.can_transition_to(InformationState.ARCHIVED)

    def test_deprecated_is_terminal(self):
        """DEPRECATED 不是完全终态——允许前进到 ARCHIVED。"""
        assert not InformationState.DEPRECATED.can_transition_to(InformationState.CREATED)
        assert not InformationState.DEPRECATED.can_transition_to(InformationState.VALIDATED)
        # DEPRECATED can go to ARCHIVED
        assert InformationState.DEPRECATED.can_transition_to(InformationState.ARCHIVED)

    def test_archived_is_terminal(self):
        """ARCHIVED 是终态——不可转出到任何其他状态。"""
        for state in InformationState:
            if state != InformationState.ARCHIVED:
                assert not InformationState.ARCHIVED.can_transition_to(state)

    def test_all_5_states_exist(self):
        """Theory 定义 5 个状态。"""
        assert len(InformationState) == 5

    def test_state_names_match_theory(self):
        """每个状态的 value 对应 Theory 标签。"""
        assert InformationState.CREATED.value == "created"
        assert InformationState.VALIDATED.value == "validated"
        assert InformationState.REFERENCED.value == "referenced"
        assert InformationState.DEPRECATED.value == "deprecated"
        assert InformationState.ARCHIVED.value == "archived"
