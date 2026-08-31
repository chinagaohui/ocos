"""Phase 22: Goal Origin Model v1.0 测试。

涵盖:
1. GoalOriginEnforcer Phase 隔离
2. GoalFactory Phase 隔离
3. Goal origin_level / authority 不可修改
4. HUMAN Goal 需 human_authorized 上下文
5. Phase 21 向后兼容（SYSTEM Goal 仍正常工作）
"""

from __future__ import annotations

import pytest

from ocos.agent.goal_types import (
    Goal,
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
)
from ocos.goal.enforcer import GoalOriginEnforcer, ConstitutionResult
from ocos.goal.factory import GoalFactory, ConstitutionViolationError


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_phase():
    """每个测试后恢复到 Phase 21。"""
    yield
    GoalFactory.set_phase(21)


@pytest.fixture
def enforcer_p21():
    return GoalOriginEnforcer(current_phase=21)


@pytest.fixture
def enforcer_p22():
    return GoalOriginEnforcer(current_phase=22)


@pytest.fixture
def enforcer_p25():
    return GoalOriginEnforcer(current_phase=25)


# ── Phase 21 隔离 ───────────────────────────────────────────────────

def test_p21_system_allowed(enforcer_p21):
    """Phase 21: SYSTEM Goal 通过。"""
    g = Goal(origin_level=GoalOriginLevel.SYSTEM)
    result = enforcer_p21.verify_creation(g)
    assert result.allowed


def test_p21_human_blocked(enforcer_p21):
    """Phase 21: HUMAN Goal 被拒绝。"""
    g = Goal(origin_level=GoalOriginLevel.HUMAN)
    result = enforcer_p21.verify_creation(g)
    assert not result.allowed
    assert "Phase 21 Isolation" in result.violations[0]


def test_p21_self_blocked(enforcer_p21):
    """Phase 21: SELF Goal 被拒绝。"""
    g = Goal(origin_level=GoalOriginLevel.SELF)
    result = enforcer_p21.verify_creation(g)
    assert not result.allowed


def test_factory_p21_blocks_human():
    """GoalFactory 在 Phase 21 拒绝 HUMAN。"""
    with pytest.raises(ConstitutionViolationError, match="Phase 21 Isolation"):
        GoalFactory.create(
            level=GoalLevel.TASK,
            description="User task",
            origin_level=GoalOriginLevel.HUMAN,
        )


def test_factory_p21_blocks_self():
    """GoalFactory 在 Phase 21 拒绝 SELF。"""
    with pytest.raises(ConstitutionViolationError, match="Phase 21 Isolation"):
        GoalFactory.create(
            level=GoalLevel.TASK,
            description="Self improvement",
            origin_level=GoalOriginLevel.SELF,
        )


def test_factory_p21_creates_system_ok():
    """GoalFactory 在 Phase 21 正常创建 SYSTEM Goal。"""
    g = GoalFactory.create(
        level=GoalLevel.TASK,
        description="Save snapshot",
    )
    assert g.origin_level == GoalOriginLevel.SYSTEM
    assert g.authority == GoalAuthority.AUTONOMOUS
    assert g.level == GoalLevel.TASK


# ── Phase 22-24 ─────────────────────────────────────────────────────

def test_p22_human_allowed(enforcer_p22):
    """Phase 22: HUMAN Goal 通过（有 human_authorized 上下文）。"""
    g = Goal(origin_level=GoalOriginLevel.HUMAN)
    result = enforcer_p22.verify_creation(g, {"human_authorized": True})
    assert result.allowed


def test_p22_human_no_context_blocked(enforcer_p22):
    """Phase 22: HUMAN Goal 无授权上下文被拒绝。"""
    g = Goal(origin_level=GoalOriginLevel.HUMAN)
    result = enforcer_p22.verify_creation(g)
    assert not result.allowed
    assert "human_authorized" in result.violations[0]


def test_p22_self_blocked(enforcer_p22):
    """Phase 22: SELF Goal 被拒绝。"""
    g = Goal(origin_level=GoalOriginLevel.SELF)
    result = enforcer_p22.verify_creation(g)
    assert not result.allowed
    assert "SELF" in result.violations[0]


def test_factory_p22_human_with_context():
    """GoalFactory Phase 22: HUMAN 可创建。"""
    GoalFactory.set_phase(22)
    g = GoalFactory.create(
        level=GoalLevel.TASK,
        description="Analyze report",
        origin_level=GoalOriginLevel.HUMAN,
    )
    assert g.origin_level == GoalOriginLevel.HUMAN
    assert g.authority == GoalAuthority.FRAMEWORK


def test_factory_p22_self_blocked():
    """GoalFactory Phase 22: SELF 被拒绝。"""
    GoalFactory.set_phase(22)
    with pytest.raises(ConstitutionViolationError, match="Phase 22 Isolation"):
        GoalFactory.create(
            level=GoalLevel.TASK,
            description="Self improve",
            origin_level=GoalOriginLevel.SELF,
        )


# ── Phase 25 ────────────────────────────────────────────────────────

def test_p25_self_allowed_as_proposal(enforcer_p25):
    """Phase 25: SELF Goal 允许创建（但 authority 是 PROPOSAL）。"""
    g = Goal(origin_level=GoalOriginLevel.SELF, authority=GoalAuthority.PROPOSAL)
    result = enforcer_p25.verify_creation(g)
    assert result.allowed


def test_factory_p25_self_creates_proposal():
    """GoalFactory Phase 25: SELF Goal authority 自动为 PROPOSAL。"""
    GoalFactory.set_phase(25)
    g = GoalFactory.create(
        level=GoalLevel.LONG,
        description="Improve reasoning",
        origin_level=GoalOriginLevel.SELF,
    )
    assert g.origin_level == GoalOriginLevel.SELF
    assert g.authority == GoalAuthority.PROPOSAL


# ── 权限提升拦截 ────────────────────────────────────────────────────

def test_cannot_change_origin_level(enforcer_p21):
    """origin_level 不可修改。"""
    old = Goal(origin_level=GoalOriginLevel.SYSTEM)
    new = Goal(origin_level=GoalOriginLevel.HUMAN)
    result = enforcer_p21.verify_modification(old, new)
    assert not result.allowed
    assert "origin_level cannot be changed" in result.violations[0]


def test_cannot_elevate_authority(enforcer_p22):
    """authority 不可从 FRAMEWORK 提升到 AUTONOMOUS。"""
    old = Goal(origin_level=GoalOriginLevel.HUMAN,
               authority=GoalAuthority.FRAMEWORK)
    new = Goal(origin_level=GoalOriginLevel.HUMAN,
               authority=GoalAuthority.AUTONOMOUS)
    result = enforcer_p22.verify_modification(old, new)
    assert not result.allowed
    assert "increase its own authority" in result.violations[0]


def test_same_authority_ok(enforcer_p22):
    """authority 不变时允许。"""
    old = Goal(origin_level=GoalOriginLevel.HUMAN,
               authority=GoalAuthority.FRAMEWORK)
    new = Goal(origin_level=GoalOriginLevel.HUMAN,
               authority=GoalAuthority.FRAMEWORK)
    result = enforcer_p22.verify_modification(old, new)
    assert result.allowed


def test_autonomous_to_framework_ok(enforcer_p22):
    """AUTONOMOUS 降级到 FRAMEWORK 允许。"""
    old = Goal(origin_level=GoalOriginLevel.SYSTEM,
               authority=GoalAuthority.AUTONOMOUS)
    new = Goal(origin_level=GoalOriginLevel.SYSTEM,
               authority=GoalAuthority.FRAMEWORK)
    result = enforcer_p22.verify_modification(old, new)
    assert result.allowed


# ── MISSION 禁止 ────────────────────────────────────────────────────

def test_factory_blocks_mission_all_phases():
    """MISSION 在任何 Phase 都禁止通过 GoalFactory 创建。"""
    for phase in [21, 22, 25]:
        GoalFactory.set_phase(phase)
        with pytest.raises(ConstitutionViolationError, match="Mission"):
            GoalFactory.create(level=GoalLevel.MISSION, description="Become")


# ── GoalStore 读写 origin_level ─────────────────────────────────────

def test_goalstore_save_and_load_with_origin(tmp_path):
    """GoalStore 正确读写 origin_level 和 authority。

    P4 (2026-09-01): 此前 GoalStore() 无 db_path → 写项目根 ocos.db
    （DB_PATH 默认相对路径），单测污染生产数据。改用临时 DB 隔离。
    """
    from ocos.goal.store import GoalStore
    import uuid
    gid = f"test-{uuid.uuid4().hex[:6]}"

    store = GoalStore(db_path=str(tmp_path / "origin.db"))
    store.save(
        goal_id=gid,
        level="TASK",
        status="PENDING",
        description="Test origin",
        origin_level="HUMAN",
        authority="FRAMEWORK",
    )
    active = store.load_active()
    match = [g for g in active if g["id"] == gid]
    assert len(match) == 1
    assert match[0]["origin_level"] == "HUMAN"
    assert match[0]["authority"] == "FRAMEWORK"
