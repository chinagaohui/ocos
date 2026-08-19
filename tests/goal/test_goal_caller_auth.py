"""Phase 21 — Goal 调用者身份验证测试。

验证:
  - HUMAN source goal 要求 caller 在 CALLER_WHITELIST 中
  - DECOMPOSED source goal 不要求 caller 在 whitelist 中
  - UserGoal.create() 传递 caller 参数
  - 非法 caller 被 ValueError 拒绝
  - CALLER_WHITELIST 是 frozen set（不可运行时修改）
"""

import pytest

from ocos.goal.models import (
    CALLER_WHITELIST,
    GoalDomain,
    GoalSource,
    GoalStatus,
    UserGoal,
)


# ── 白名单完整性 ──────────────────────────────────────────────────

def test_caller_whitelist_not_empty():
    """CALLER_WHITELIST 至少包含已知合法调用方。"""
    assert "orchestrator" in CALLER_WHITELIST
    assert "goal_parser" in CALLER_WHITELIST
    assert "cli" in CALLER_WHITELIST


def test_caller_whitelist_is_frozen():
    """CALLER_WHITELIST 是不可变的 frozenset。"""
    assert isinstance(CALLER_WHITELIST, frozenset)
    with pytest.raises(AttributeError):
        CALLER_WHITELIST.add("hacked")  # type: ignore


# ── HUMAN source: caller 必须在校验白名单 ───────────────────────

@pytest.mark.parametrize("caller", ["orchestrator", "goal_parser", "cli"])
def test_human_source_accepts_valid_caller(caller):
    """合法的 caller 可以创建 HUMAN source goal。"""
    g = UserGoal(
        id="G-OK",
        raw_input="test",
        objective="test",
        domain=GoalDomain.WRITING,
        source=GoalSource.HUMAN,
        caller=caller,
    )
    assert g.caller == caller
    assert g.source == GoalSource.HUMAN


def test_human_source_rejects_unknown_caller():
    """不在白名单中的 caller 创建 HUMAN goal 被拒绝。"""
    with pytest.raises(ValueError, match="caller.*CALLER_WHITELIST"):
        UserGoal(
            id="G-BAD",
            raw_input="test",
            objective="test",
            domain=GoalDomain.WRITING,
            source=GoalSource.HUMAN,
            caller="agent",  # 不在whitelist中
        )


def test_human_source_rejects_default_caller():
    """默认 caller='unknown' 创建 HUMAN goal 被拒绝。"""
    with pytest.raises(ValueError, match="caller.*CALLER_WHITELIST"):
        UserGoal(
            id="G-BAD",
            raw_input="test",
            objective="test",
            domain=GoalDomain.WRITING,
            source=GoalSource.HUMAN,
            # caller 默认 "unknown" → 不在 whitelist，应拒绝
        )


def test_human_source_rejects_empty_caller():
    """空字符串 caller 也被拒绝。"""
    with pytest.raises(ValueError, match="caller"):
        UserGoal(
            id="G-BAD",
            raw_input="test",
            objective="test",
            domain=GoalDomain.WRITING,
            source=GoalSource.HUMAN,
            caller="",
        )


# ── DECOMPOSED source: caller 不校验 ────────────────────────────

def test_decomposed_source_accepts_any_caller():
    """DECOMPOSED goal 不要求 caller 在 whitelist 中。"""
    g = UserGoal(
        id="G-DECOMPOSED",
        raw_input="sub task",
        objective="sub task",
        domain=GoalDomain.WRITING,
        source=GoalSource.DECOMPOSED,
        parent_id="G-root",
        caller="agent",  # 不在whitelist，但 DECOMPOSED 不检查
    )
    assert g.source == GoalSource.DECOMPOSED
    assert g.caller == "agent"


# ── create() 工厂方法 ───────────────────────────────────────────

def test_create_passes_caller_correctly():
    """UserGoal.create() 传递 caller 给 __init__。"""
    g = UserGoal.create(
        raw_input="write novel",
        objective="write a novel",
        domain=GoalDomain.WRITING,
        caller="orchestrator",
    )
    assert g.caller == "orchestrator"
    assert g.source == GoalSource.HUMAN


def test_create_rejects_invalid_caller():
    """UserGoal.create() 传递非法 caller 也被 __post_init__ 拒绝。"""
    with pytest.raises(ValueError, match="caller"):
        UserGoal.create(
            raw_input="write novel",
            objective="write a novel",
            domain=GoalDomain.WRITING,
            caller="agent",  # 不在whitelist
        )


# ── with_status 保留 caller ─────────────────────────────────────

def test_with_status_preserves_caller():
    """状态转换后 caller 不变。"""
    g = UserGoal(
        id="G-TRANS",
        raw_input="test",
        objective="test",
        domain=GoalDomain.WRITING,
        source=GoalSource.HUMAN,
        caller="orchestrator",
    )
    g2 = g.with_status(GoalStatus.ACTIVE)
    assert g2.caller == "orchestrator"
    assert g2.status == GoalStatus.ACTIVE
