"""Phase 26 — Gate Tests: Goal Models。

验证:
  26-M01: UserGoal frozen
  26-M02: source 仅 human/decomposed
  26-M03: success_criteria measurable 验证
  26-M04: goal status transitions
  26-M05: priority 范围 [1,5]
  26-M06: UserGoal.create 工厂方法
  26-M07: parent_id ← source=decomposed
  26-M08: with_status 不可变转换
  26-M09: GoalDomain 枚举
  26-M10: SuccessCriteria threshold 要求
"""

import pytest
from datetime import datetime, timezone

from ocos.goal.models import (
    GoalSource,
    GoalDomain,
    GoalStatus,
    SuccessCriteria,
    UserGoal,
)


# ── 26-M01: UserGoal frozen ──────────────────────────────────────────

def test_user_goal_frozen():
    g = UserGoal(
        id="G-1",
        raw_input="写小说",
        objective="创作小说",
        domain=GoalDomain.WRITING,
        caller="orchestrator",
    )
    with pytest.raises(Exception):
        g.raw_input = "改一下"  # type: ignore


# ── 26-M02: source is closed set ────────────────────────────────────

def test_source_human_valid():
    g = UserGoal.create(raw_input="写小说", objective="创作小说", domain=GoalDomain.WRITING, caller="orchestrator")
    assert g.source == GoalSource.HUMAN


def test_source_reject_self():
    with pytest.raises(ValueError, match="source"):
        UserGoal(
            id="G-1",
            raw_input="foo",
            objective="bar",
            domain=GoalDomain.WRITING,
            source="self",  # type: ignore
        )


def test_parent_id_requires_decomposed():
    with pytest.raises(ValueError, match="parent_id"):
        UserGoal(
            id="G-2",
            raw_input="foo",
            objective="bar",
            domain=GoalDomain.WRITING,
            parent_id="G-1",
            source=GoalSource.HUMAN,
        )


def test_decomposed_source_with_parent():
    g = UserGoal(
        id="G-3",
        raw_input="写第1章",
        objective="写第一章",
        domain=GoalDomain.WRITING,
        parent_id="G-1",
        source=GoalSource.DECOMPOSED,
    )
    assert g.parent_id == "G-1"
    assert g.source == GoalSource.DECOMPOSED


# ── 26-M03: success_criteria measurable ─────────────────────────────

def test_success_criteria_measurable_no_threshold_raises():
    with pytest.raises(ValueError, match="threshold"):
        SuccessCriteria(description="完成小说", measurable=True)


def test_success_criteria_non_measurable():
    sc = SuccessCriteria(description="好看", measurable=False)
    assert not sc.measurable
    assert sc.threshold is None


def test_success_criteria_with_threshold():
    sc = SuccessCriteria(description="字数", measurable=True, threshold="50000")
    assert sc.measurable
    assert sc.threshold == "50000"


# ── 26-M04: goal status transitions ─────────────────────────────────

def test_status_pending_to_active():
    g = UserGoal.create(
        raw_input="写小说", objective="创作", domain=GoalDomain.WRITING, caller="orchestrator"
    )
    g2 = g.with_status(GoalStatus.ACTIVE)
    assert g2.status == GoalStatus.ACTIVE


def test_status_active_to_completed():
    g = UserGoal.create(
        raw_input="写小说", objective="创作", domain=GoalDomain.WRITING, caller="orchestrator"
    )
    g2 = g.with_status(GoalStatus.ACTIVE)
    g3 = g2.with_status(GoalStatus.COMPLETED)
    assert g3.status == GoalStatus.COMPLETED
    assert g3.status.is_terminal


def test_status_invalid_transition():
    g = UserGoal.create(
        raw_input="写小说", objective="创作", domain=GoalDomain.WRITING, caller="orchestrator"
    )
    g2 = g.with_status(GoalStatus.ACTIVE)
    with pytest.raises(ValueError, match="transition"):
        g2.with_status(GoalStatus.PENDING)


# ── 26-M05: priority range ──────────────────────────────────────────

def test_priority_in_range():
    for p in range(1, 6):
        g = UserGoal(
            id=f"G-{p}",
            raw_input="foo",
            objective="bar",
            domain=GoalDomain.WRITING,
            priority=p,
            caller="orchestrator",
        )
        assert g.priority == p


def test_priority_out_of_range():
    with pytest.raises(ValueError, match="priority"):
        UserGoal(
            id="G-99",
            raw_input="foo",
            objective="bar",
            domain=GoalDomain.WRITING,
            priority=99,
            caller="orchestrator",
        )


# ── 26-M06: UserGoal.create 工厂方法 ────────────────────────────────

def test_create_factory():
    g = UserGoal.create(
        raw_input="创建科幻小说项目",
        objective="创作科幻小说",
        domain=GoalDomain.WRITING,
        caller="orchestrator",
        constraints=("5万字", "主角AI工程师"),
        success_criteria=(
            SuccessCriteria(description="完整草稿", measurable=True, threshold="50000"),
        ),
        priority=3,
    )
    assert g.id.startswith("GOAL-")
    assert g.raw_input == "创建科幻小说项目"
    assert g.objective == "创作科幻小说"
    assert g.domain == GoalDomain.WRITING
    assert g.constraints == ("5万字", "主角AI工程师")
    assert g.priority == 3
    assert g.source == GoalSource.HUMAN
    assert g.parent_id is None
    assert g.status == GoalStatus.PENDING


# ── 26-M07: with_status preserves all fields ────────────────────────

def test_with_status_preserves_data():
    g = UserGoal.create(
        raw_input="分析数据", objective="分析", domain=GoalDomain.ANALYSIS, caller="orchestrator"
    )
    g2 = g.with_status(GoalStatus.ACTIVE)
    assert g2.id == g.id
    assert g2.raw_input == g.raw_input
    assert g2.objective == g.objective
    assert g2.domain == g.domain
    assert g2.created_at == g.created_at


# ── 26-M08: empty fields rejected ───────────────────────────────────

def test_empty_id_rejected():
    with pytest.raises(ValueError, match="id"):
        UserGoal(id="", raw_input="a", objective="b", domain=GoalDomain.WRITING)


def test_empty_raw_input_rejected():
    with pytest.raises(ValueError, match="raw_input"):
        UserGoal(id="G", raw_input="", objective="b", domain=GoalDomain.WRITING)


def test_empty_objective_rejected():
    with pytest.raises(ValueError, match="objective"):
        UserGoal(id="G", raw_input="a", objective="", domain=GoalDomain.WRITING)


# ── 26-M09: GoalDomain completeness ─────────────────────────────────

def test_goal_domain_all_members():
    domains = {d.value for d in GoalDomain}
    assert "writing" in domains
    assert "analysis" in domains
    assert "research" in domains
    assert "development" in domains


# ── 26-M10: SuccessCriteria met defaults to False ───────────────────

def test_success_criteria_met_default():
    sc = SuccessCriteria(description="字数", measurable=True, threshold="50000")
    assert not sc.met
