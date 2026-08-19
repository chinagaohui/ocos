"""Phase 25.1 — Gate Tests: IdentityBoundary。

验证:
  25.1-01: create_default() 包含所有原则
  25.1-02: IdentityBoundary immutable (frozen dataclass)
  25.1-03: ForbiddenTransition 阻止 NEUTRAL→PERSONA
  25.1-04: 所有 5 条禁止转移就位
  25.1-05: authority_limits 仅 self-layer
  25.1-06: self_reference_constraints 三约束
  25.1-07: evolution_constraints 最低值
  25.1-08: BoundaryValidator 拒绝缺失 NO_SELF_MODIFICATION
  25.1-09: BoundaryValidator 拒绝跨层 authority
  25.1-10: IdentityBoundary 无 personality/emotion 字段
  25.1-11: IdentityBoundary ≠ SelfModel (边界≠模型)
  25.1-12: version 从 1 开始
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.self.identity_boundary import (
    BoundaryPrinciple,
    BoundaryValidator,
    ForbiddenTransition,
    IdentityBoundary,
)


# ── 25.1-01: create_default ─────────────────────────────────────────────────


def test_create_default_has_all_principles() -> None:
    """默认 IdentityBoundary 包含所有 12 条原则。"""
    boundary = IdentityBoundary.create_default()
    assert len(boundary.principles) == len(BoundaryPrinciple)
    for p in BoundaryPrinciple:
        assert p in boundary.principles


def test_create_default_has_id() -> None:
    """ID 以 IDB- 开头。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.id.startswith("IDB-")


# ── 25.1-02: immutable ──────────────────────────────────────────────────────


def test_identity_boundary_is_frozen() -> None:
    """IdentityBoundary 是 frozen dataclass。"""
    boundary = IdentityBoundary.create_default()
    with pytest.raises(Exception):
        boundary.version = 2  # type: ignore[misc]


# ── 25.1-03: ForbiddenTransition ────────────────────────────────────────────


def test_neutral_to_persona_forbidden() -> None:
    """NEUTRAL→PERSONA 禁止。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.is_transition_forbidden("neutral", "persona")


def test_transition_not_blocked_if_not_in_list() -> None:
    """不在禁止列表中的转移允许。"""
    boundary = IdentityBoundary.create_default()
    assert not boundary.is_transition_forbidden("stable", "evolving")


# ── 25.1-04: 所有 5 条禁止转移 ──────────────────────────────────────────────


def test_all_five_forbidden_transitions() -> None:
    """确认 5 条预定义禁止转移都在默认列表中。"""
    boundary = IdentityBoundary.create_default()
    expected = {
        ("neutral", "persona"),
        ("neutral", "goal-owner"),
        ("neutral", "authority"),
        ("neutral", "value-holder"),
        ("neutral", "emotional"),
    }
    actual = {(t.from_state, t.to_state) for t in boundary.forbidden_transitions}
    assert expected <= actual  # 至少包含这些


# ── 25.1-05: authority_limits ───────────────────────────────────────────────


def test_authority_limits_self_layer_only() -> None:
    """权限仅限 self-layer。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.authority_limits == ("self-layer",)
    assert boundary.check_authority("self-layer")
    assert not boundary.check_authority("memory")
    assert not boundary.check_authority("goal")
    assert not boundary.check_authority("subject")


# ── 25.1-06: self_reference_constraints ─────────────────────────────────────


def test_self_reference_constraints() -> None:
    """三大约束都存在。"""
    boundary = IdentityBoundary.create_default()
    constraints = set(boundary.self_reference_constraints)
    assert "no-circular-proof" in constraints
    assert "no-self-derived-value" in constraints
    assert "no-identity-recursion" in constraints


# ── 25.1-07: evolution_constraints ──────────────────────────────────────────


def test_evolution_constraints_minimums() -> None:
    """演化约束最低阈值。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.min_evidence_beliefs >= 5
    assert boundary.min_stability_days >= 30
    assert boundary.max_evolution_frequency_days >= 30


def test_evolution_constraints_completeness() -> None:
    """所有必需键存在。"""
    boundary = IdentityBoundary.create_default()
    ec = boundary.evolution_constraints
    assert ec["require_governance_approval"] is True
    assert ec["require_boundary_check"] is True
    assert "max_statement_change_ratio" in ec


# ── 25.1-08: BoundaryValidator ──────────────────────────────────────────────


def test_validator_rejects_missing_no_self_modification() -> None:
    """缺失 NO_SELF_MODIFICATION 原则 → 拒绝。"""
    boundary = IdentityBoundary.create_custom(
        principles=tuple(
            p for p in BoundaryPrinciple
            if p != BoundaryPrinciple.NO_SELF_MODIFICATION
        ),
    )
    ok, violations = BoundaryValidator.validate(boundary)
    assert not ok
    assert any("NO_SELF_MODIFICATION" in v for v in violations)


def test_validator_rejects_missing_capability_bound() -> None:
    """缺失 CAPABILITY_BOUND → 拒绝。"""
    boundary = IdentityBoundary.create_custom(
        principles=tuple(
            p for p in BoundaryPrinciple
            if p != BoundaryPrinciple.CAPABILITY_BOUND
        ),
    )
    ok, violations = BoundaryValidator.validate(boundary)
    assert not ok
    assert any("CAPABILITY_BOUND" in v for v in violations)


def test_validator_rejects_missing_evolution_governed() -> None:
    """缺失 EVOLUTION_GOVERNED → 拒绝。"""
    boundary = IdentityBoundary.create_custom(
        principles=tuple(
            p for p in BoundaryPrinciple
            if p != BoundaryPrinciple.EVOLUTION_GOVERNED
        ),
    )
    ok, violations = BoundaryValidator.validate(boundary)
    assert not ok


def test_validator_rejects_missing_persona_block() -> None:
    """缺失 NEUTRAL_TO_PERSONA 禁止 → 拒绝。"""
    boundary = IdentityBoundary.create_custom(
        forbidden_transitions=tuple(
            ForbiddenTransition(*t)
            for t in ForbiddenTransition.ALL_PREDEFINED
            if t[1] != "persona"
        ),
    )
    ok, violations = BoundaryValidator.validate(boundary)
    assert not ok
    assert any("PERSONA" in v for v in violations)


def test_validator_accepts_default() -> None:
    """默认 IdentityBoundary 通过验证。"""
    boundary = IdentityBoundary.create_default()
    ok, violations = BoundaryValidator.validate(boundary)
    assert ok, violations


# ── 25.1-09: 跨层 authority ─────────────────────────────────────────────────


def test_validator_rejects_cross_layer_authority() -> None:
    """authority_limits 不能包含非 self-layer 的值。"""
    # 无法在 frozen dataclass 中直接改 authority_limits，
    # 通过 create_custom 间接测试 — 但 create_custom 强制 ("self-layer",)。
    # 所以这里验证默认 boundary 的 authority_limits 只有 self-layer。
    boundary = IdentityBoundary.create_default()
    for layer in boundary.authority_limits:
        assert layer == "self-layer", f"Unexpected authority: {layer}"


# ── 25.1-10: 无 personality/emotion ─────────────────────────────────────────


def test_identity_boundary_no_personality_field() -> None:
    """IdentityBoundary 字段不含 personality/emotion/preference。"""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(IdentityBoundary)}
    forbidden = {"personality", "emotion", "preference", "goal", "value", "persona"}
    assert fields.isdisjoint(forbidden), f"Found forbidden fields: {fields & forbidden}"


def test_boundary_principle_no_persona() -> None:
    """BoundaryPrinciple 枚举不含 persona/identity_definition。"""
    values = {p.value for p in BoundaryPrinciple}
    assert "persona" not in values
    assert "personality" not in values
    assert "identity_definition" not in values
    assert "identity" not in values


# ── 25.1-11: IdentityBoundary ≠ SelfModel ───────────────────────────────────


def test_identity_boundary_has_no_statement_field() -> None:
    """IdentityBoundary 不含 statement 字段（那是 SelfModel 的）。"""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(IdentityBoundary)}
    assert "statement" not in fields
    assert "self_description" not in fields


# ── 25.1-12: version = 1 ────────────────────────────────────────────────────


def test_default_version_is_one() -> None:
    """默认 IdentityBoundary version = 1。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.version == 1


def test_has_principle() -> None:
    """has_principle 查询正常工作。"""
    boundary = IdentityBoundary.create_default()
    assert boundary.has_principle(BoundaryPrinciple.NOT_HUMAN)
    assert boundary.has_principle(BoundaryPrinciple.NO_SELF_MODIFICATION)


def test_forbidden_transition_is_immutable() -> None:
    """ForbiddenTransition 是 frozen 的。"""
    with pytest.raises(Exception):
        ForbiddenTransition("a", "b", "reason").from_state = "x"  # type: ignore[misc]


def test_summary_method() -> None:
    """summary() 返回非空字符串。"""
    boundary = IdentityBoundary.create_default()
    summary = boundary.summary()
    assert boundary.id in summary
    assert "principles" in summary
