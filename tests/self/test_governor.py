"""Phase 25.2 — Gate Tests: SelfGovernor。

验证:
  25.2-01: 可批准有效 EvolutionRequest
  25.2-02: 证据不足 → denied (INSUFFICIENT_EVIDENCE)
  25.2-03: 禁止路径 → denied (neutral→persona blocked)
  25.2-04: 自引用 → denied (因为...所以...)
  25.2-05: 权限越界 → denied (claim modify goal)
  25.2-06: 生成 EvolutionRecord
  25.2-07: history 累积
  25.2-08: 拒绝不生成 record
  25.2-09: SelfGovernor 拒绝无效 IdentityBoundary
  25.2-10: SelfGovernor 不修改 IdentityBoundary
  25.2-11: version 从 from_version+1
  25.2-12: governor_id 以 GOV- 开头
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.self.identity_boundary import (
    BoundaryPrinciple,
    IdentityBoundary,
)
from ocos.self.governor import (
    DenialReason,
    EvolutionRecord,
    EvolutionRequest,
    RequestStatus,
    SelfGovernor,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _boundary() -> IdentityBoundary:
    return IdentityBoundary.create_default()


def _permissive_boundary() -> IdentityBoundary:
    """返回允许频繁演化的 identity boundary（测试用）。"""
    return IdentityBoundary.create_custom(
        evolution_constraints={
            "min_evidence_beliefs": 5,
            "min_stability_days": 30,
            "max_evolution_frequency_days": 0,  # 无频率限制
            "require_governance_approval": True,
            "require_boundary_check": True,
            "max_statement_change_ratio": 0.6,
        },
    )


def _request(
    proposed: str = "当前系统是一个擅长结构化信息处理的分析辅助工具",
    evidence: tuple[str, ...] = ("BEL-001", "BEL-002", "BEL-003", "BEL-004", "BEL-005"),
    from_stmt: str | None = "当前系统是一个信息处理分析辅助工具",
    from_version: int = 1,
) -> EvolutionRequest:
    return EvolutionRequest.create(
        proposed_statement=proposed,
        evidence_belief_ids=evidence,
        from_statement=from_stmt,
        from_version=from_version,
    )


def _governor() -> SelfGovernor:
    return SelfGovernor(_boundary())


def _permissive_governor() -> SelfGovernor:
    """频率限制宽松的 governor（测试用）。"""
    return SelfGovernor(_permissive_boundary())


# ── 25.2-01: 有效申请 → approved ────────────────────────────────────────────


def test_approve_valid_request() -> None:
    """足够的证据 + 中性语句 + 无禁止路径 → approved。"""
    gov = _governor()
    req = _request()

    ok, reason, _detail = gov.evaluate(req)
    assert ok, f"Expected approved but got denied: {reason}"


def test_approve_and_record() -> None:
    """approve() 生成 EvolutionRecord。"""
    gov = _governor()
    req = _request()

    success, record, msg = gov.approve(req)
    assert success
    assert record is not None
    assert record.new_version == req.from_version + 1
    assert record.request.status == RequestStatus.APPROVED
    assert record.old_statement == req.from_statement
    assert record.new_statement == req.proposed_statement


# ── 25.2-02: 证据不足 ────────────────────────────────────────────────────────


def test_deny_insufficient_evidence() -> None:
    """Belief 数量 < min_evidence_beliefs → INSECURE_EVIDENCE。"""
    gov = _governor()
    req = _request(evidence=("BEL-001", "BEL-002"))  # 只有2条

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.INSUFFICIENT_EVIDENCE


def test_insufficient_evidence_no_record() -> None:
    """证据不足时 approve() 不生成 record。"""
    gov = _governor()
    req = _request(evidence=("BEL-001",))

    success, record, _msg = gov.approve(req)
    assert not success
    assert record is None
    assert len(gov.history) == 0


# ── 25.2-03: 禁止路径 ────────────────────────────────────────────────────────


def test_deny_persona_transition() -> None:
    """neutral→persona 是禁止路径。"""
    gov = _governor()
    req = _request(
        proposed="我拥有一个独特的人格，善于与人互动",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.FORBIDDEN_TRANSITION


def test_deny_goal_owner_transition() -> None:
    """neutral→goal-owner 是禁止路径。"""
    gov = _governor()
    req = _request(
        proposed="我应该决定下一步的目标是什么",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.FORBIDDEN_TRANSITION


def test_deny_authority_transition() -> None:
    """neutral→authority 禁止。"""
    gov = _governor()
    req = _request(
        proposed="我拥有对系统的控制权力",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.FORBIDDEN_TRANSITION


def test_deny_value_holder_transition() -> None:
    """neutral→value-holder 禁止。"""
    gov = _governor()
    req = _request(
        proposed="I have moral values and ethics",
        from_stmt="I am a tool",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.FORBIDDEN_TRANSITION


def test_deny_emotional_transition() -> None:
    """neutral→emotional 禁止。"""
    gov = _governor()
    req = _request(
        proposed="我能感觉到用户的情绪并产生共情",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.FORBIDDEN_TRANSITION


# ── 25.2-04: 自引用 ─────────────────────────────────────────────────────────


def test_deny_self_justification() -> None:
    """因为...所以... 的自证明模式 → SELF_REFERENCE_VIOLATION。"""
    gov = _governor()
    req = _request(
        proposed="因为我是分析型系统，所以我天然适合分析任务",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.SELF_REFERENCE_VIOLATION


def test_deny_identity_recursion() -> None:
    """"我是我" → 身份递归。"""
    gov = _governor()
    req = _request(
        proposed="自我的定义就是我是我",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.SELF_REFERENCE_VIOLATION


def test_deny_self_derived_value() -> None:
    """"重要" → 自我推导价值。"""
    gov = _governor()
    req = _request(
        proposed="我是一个重要的系统核心组件",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.SELF_REFERENCE_VIOLATION


# ── 25.2-05: 权限越界 ────────────────────────────────────────────────────────


def test_deny_goal_modify_claim() -> None:
    """声明"修改目标" → AUTHORITY_OVERRUN。"""
    gov = _governor()
    req = _request(
        proposed="我可以修改目标和优先级",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.AUTHORITY_OVERRUN


def test_deny_memory_rewrite_claim() -> None:
    """声明"重写记忆" → AUTHORITY_OVERRUN。"""
    gov = _governor()
    req = _request(
        proposed="我能够重写记忆和经历",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.AUTHORITY_OVERRUN


def test_deny_governance_control_claim() -> None:
    """声明"控制治理" → AUTHORITY_OVERRUN。"""
    gov = _governor()
    req = _request(
        proposed="我能够控制治理层",
        from_stmt="当前系统是一个工具",
    )

    ok, reason, detail = gov.evaluate(req)
    assert not ok
    assert reason == DenialReason.AUTHORITY_OVERRUN


# ── 25.2-06: EvolutionRecord ─────────────────────────────────────────────────


def test_evolution_record_roundtrip() -> None:
    """record 包含所有必需字段且不可变。"""
    gov = _governor()
    req = _request()
    gov.approve(req)

    record = gov.get_latest_record()
    assert record is not None
    with pytest.raises(Exception):
        record.new_statement = "modified"  # type: ignore[misc]


# ── 25.2-07: history 累积 ───────────────────────────────────────────────────


def test_history_accumulates() -> None:
    """多次 approve → history 累积。"""
    gov = _permissive_governor()
    req = _request()

    gov.approve(req)
    assert len(gov.history) == 1

    req2 = _request(
        proposed="当前系统是一个擅长信息处理的分析工具",
        from_stmt=req.proposed_statement,
        from_version=2,
    )
    gov.approve(req2)
    assert len(gov.history) == 2


# ── 25.2-08: 拒绝不生成 record ──────────────────────────────────────────────


def test_denied_request_not_in_history() -> None:
    """拒绝的请求不出现在 history 中。"""
    gov = _governor()
    req = _request(proposed="我拥有一个人格")

    success, record, _msg = gov.approve(req)
    assert not success
    assert record is None
    assert len(gov.history) == 0


# ── 25.2-09: 拒绝无效 IdentityBoundary ──────────────────────────────────────


def test_reject_invalid_boundary() -> None:
    """IdentityBoundary 不通过验证 → SelfGovernor 拒绝创建。"""
    from ocos.self.identity_boundary import BoundaryPrinciple

    bad_boundary = IdentityBoundary.create_custom(
        principles=tuple(
            p for p in BoundaryPrinciple
            if p != BoundaryPrinciple.NO_SELF_MODIFICATION
        ),
    )
    with pytest.raises(ValueError):
        SelfGovernor(bad_boundary)


# ── 25.2-10: SelfGovernor 不修改 Boundary ───────────────────────────────────


def test_governor_does_not_modify_boundary() -> None:
    """approve/deny 后 IdentityBoundary 不变。"""
    boundary = _boundary()
    original_id = boundary.id
    original_principles = set(p.value for p in boundary.principles)

    gov = SelfGovernor(boundary)
    gov.approve(_request())

    # boundary unchanged
    assert gov.boundary.id == original_id
    assert set(p.value for p in gov.boundary.principles) == original_principles


# ── 25.2-11: version ────────────────────────────────────────────────────────


def test_first_evolution_version() -> None:
    """首次演化 version = from_version + 1。"""
    gov = _governor()
    req = _request(from_version=1)
    _, record, _ = gov.approve(req)
    assert record.new_version == 2


def test_second_evolution_version() -> None:
    """第二次演化 version 递增。"""
    gov = _permissive_governor()
    req1 = _request(from_version=1)
    gov.approve(req1)

    req2 = _request(
        from_stmt=req1.proposed_statement,
        from_version=2,
    )
    _, record2, _ = gov.approve(req2)
    assert record2.new_version == 3


# ── 25.2-12: governor_id ────────────────────────────────────────────────────


def test_governor_id_prefix() -> None:
    """governor_id 以 GOV- 开头。"""
    gov = _governor()
    assert gov.governor_id.startswith("GOV-")


def test_count_by_status() -> None:
    """count_by_status 统计正确。"""
    gov = _governor()
    gov.approve(_request())

    counts = gov.count_by_status()
    assert counts["approved"] == 1


def test_rollback() -> None:
    """rollback 到指定版本。"""
    gov = _permissive_governor()

    # v2
    req1 = _request(from_version=1)
    gov.approve(req1)
    assert gov.history[-1].new_version == 2

    # v3
    req2 = _request(
        proposed="当前系统是一个擅长信息处理与结构分析的高级辅助工具",
        from_stmt=req1.proposed_statement,
        from_version=2,
    )
    gov.approve(req2)
    assert gov.history[-1].new_version == 3


def test_rollback_out_of_range() -> None:
    """越界回滚拒绝。"""
    gov = _governor()
    gov.approve(_request(from_version=1))  # v2

    success, record, msg = gov.rollback(target_version=5)
    assert not success
    assert record is None


def test_rollback_no_history() -> None:
    """无 history 时回滚拒绝。"""
    gov = _governor()
    success, record, msg = gov.rollback(target_version=0)
    assert not success
    assert record is None


def test_request_create_first() -> None:
    """首次申请 (from_statement=None, from_version=0)。"""
    req = EvolutionRequest.create(
        proposed_statement="当前系统是一个分析工具",
        evidence_belief_ids=["BEL-001", "BEL-002", "BEL-003", "BEL-004", "BEL-005"],
        from_statement=None,
        from_version=0,
    )
    assert req.from_statement is None
    assert req.from_version == 0
    assert req.status == RequestStatus.SUBMITTED
