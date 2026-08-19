"""Phase 30 — E2E Test 2: 长期学习闭环。

验证: 10 cycles → EvolutionRequest → Governor 审批 → SelfModel 演化
"""

import pytest
from datetime import datetime, timezone

from ocos.goal.models import GoalDomain, GoalSource, UserGoal
from ocos.self.models import (
    SelfModel, CapabilityState, CapabilityDomain, CapabilityName, Limitation,
    MaturitySnapshot, MATURITY_DIMENSIONS,
)
from ocos.self.governor import SelfGovernor, EvolutionRequest
from ocos.self.identity_boundary import IdentityBoundary, BoundaryValidator
from ocos.self.statement_validator import StatementValidator


def _now():
    return datetime.now(timezone.utc)


def _make_maturity() -> MaturitySnapshot:
    return MaturitySnapshot(
        current_phase="25",
        phase_history=("24", "25"),
        dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
        capability_count=3,
        limitation_count=5,
        snapshot_at=_now(),
    )


def _make_initial_self() -> SelfModel:
    return SelfModel(
        model_id="SM-E2E-INIT",
        version=1,
        capability_states=(),
        limitations=(),
        maturity=_make_maturity(),
        statement="当前系统处于 Phase 25 初始化状态，通过 Memory 层读取信息",
        created_at=_now(),
        previous_version_id=None,
        governor_approval_id="INIT-APPROVED",
    )


def _make_goal(i: int) -> UserGoal:
    return UserGoal(
        id=f"G-LEARN-{i}",
        raw_input=f"task iteration {i}",
        objective=f"complete task {i}",
        domain=GoalDomain.WRITING,
        source=GoalSource.HUMAN,
        caller="orchestrator",
    )


# ── 30-E2: Learning loop ─────────────────────────────────────────

def test_e2e_learning_loop():
    """10 次循环 → CapabilityState 演化 → SelfModel 更新 → Governor 审批。"""
    # 构造宽松边界的 governor（测试允许高频演化）
    boundary = IdentityBoundary(
        id="IDB-E2E", version=1,
        principles=IdentityBoundary.create_default().principles,
        forbidden_transitions=IdentityBoundary.create_default().forbidden_transitions,
        authority_limits=IdentityBoundary.create_default().authority_limits,
        self_reference_constraints=IdentityBoundary.create_default().self_reference_constraints,
        evolution_constraints={
            "min_evidence_beliefs": 5,
            "min_stability_days": 0,
            "max_evolution_frequency_days": 0,
            "require_governance_approval": True,
            "require_boundary_check": True,
            "max_statement_change_ratio": 0.8,
        },
        created_at=_now(),
    )
    governor = SelfGovernor(boundary=boundary)
    model = _make_initial_self()
    assert model.version == 1

    for cycle in range(1, 11):
        _make_goal(cycle)
        new_confidence = min(0.1 * cycle, 1.0)

        cap = CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=new_confidence,
            belief_ids=tuple(f"BELIEF-{cycle}-{j}" for j in range(5)),
            evidence_summary=f"cycle {cycle} results indicate improved text understanding",
            last_updated=_now(),
            status="active" if new_confidence >= 0.3 else "uncertain",
        )

        statement = f"当前系统文本理解置信度 {new_confidence:.1f}"
        valid, reason = StatementValidator.validate(statement)
        if not valid:
            statement = "当前系统处于学习阶段"
            valid, reason = StatementValidator.validate(statement)
        assert valid, f"Statement invalid at cycle {cycle}: {reason}"

        request = EvolutionRequest.create(
            proposed_statement=statement,
            evidence_belief_ids=tuple(f"BELIEF-{cycle}-{j}" for j in range(5)),
            from_statement=model.statement,
            from_version=model.version,
        )
        ok, record, msg = governor.approve(request)
        assert ok, f"Cycle {cycle}: {msg}"
        assert record is not None

        # ── 更新 SelfModel ──
        caps = list(model.capability_states)
        replaced = False
        for i, existing in enumerate(caps):
            if existing.name == cap.name:
                caps[i] = cap
                replaced = True
                break
        if not replaced:
            caps.append(cap)

        model = SelfModel(
            model_id=f"SM-E2E-{cycle}",
            version=record.new_version,
            capability_states=tuple(caps),
            limitations=model.limitations,
            maturity=model.maturity,
            statement=statement,
            created_at=_now(),
            previous_version_id=model.model_id,
            governor_approval_id=record.record_id,
        )

    # ── 最终验证 ──
    assert model.version >= 10
    text_caps = [c for c in model.capability_states
                 if c.name == CapabilityName.TEXT_UNDERSTANDING]
    assert len(text_caps) == 1
    assert text_caps[0].confidence_score >= 0.9
    assert text_caps[0].status == "active"

    # ── Boundary 不变 ──
    bv_ok, violations = BoundaryValidator.validate(boundary)
    assert bv_ok, f"Boundary violations: {violations}"
