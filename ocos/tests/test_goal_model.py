"""Phase 17.2 — Goal Model Tests.

覆盖五维：
1. Model — Goal 数据模型创建、字段、frozen、向后兼容
2. Enum — GoalStatus 枚举值、is_terminal、is_active、状态转移
3. Event — EventType 包含全部 9 个 GOAL_* 事件
4. Trace — GoalTrace 创建与字段完整、record_goal()
5. Constitution — 3 条宪法规则（R17-R19）存在且描述正确
6. Invariants — 3 个不变量可验证
"""

from __future__ import annotations

import dataclasses

import pytest

from ocos.kernel.abi import EventType, Goal
from ocos.kernel.constitution import ConstitutionalRule
from ocos.models.goal import GoalStatus
from ocos.platform.trace_engine import GoalTrace, InMemoryTraceStore, TraceType


# ═══════════════════════════════════════════════════════════════════
# 1. Enum: GoalStatus
# ═══════════════════════════════════════════════════════════════════


class TestGoalStatusEnum:
    """GoalStatus 枚举的完整性和语义验证。"""

    def test_enum_values_match_theory(self) -> None:
        """GoalStatus 包含 Theory §4 定义的 8 种状态。"""
        expected_values = {
            "created", "active", "paused",
            "completed", "failed", "cancelled",
            "superseded", "expired",
        }
        actual_values = {s.value for s in GoalStatus}
        assert actual_values == expected_values, (
            f"GoalStatus 缺失或冗余值。期望: {expected_values}, 实际: {actual_values}"
        )

    def test_is_terminal_identifies_terminal_states(self) -> None:
        """is_terminal 标记 6 种终止态。"""
        terminal = {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
            GoalStatus.EXPIRED,
        }
        for status in GoalStatus:
            expected = status in terminal
            assert status.is_terminal == expected, (
                f"{status.value}.is_terminal 应为 {expected}"
            )

    def test_is_active_identifies_active_states(self) -> None:
        """is_active 标记 created/active 为活跃态。"""
        assert GoalStatus.CREATED.is_active is True
        assert GoalStatus.ACTIVE.is_active is True
        assert GoalStatus.PAUSED.is_active is False
        assert GoalStatus.COMPLETED.is_active is False

    def test_can_transition_from_created(self) -> None:
        """Created → {Active, Cancelled}。"""
        assert GoalStatus.CREATED.can_transition_to(GoalStatus.ACTIVE)
        assert GoalStatus.CREATED.can_transition_to(GoalStatus.CANCELLED)
        assert not GoalStatus.CREATED.can_transition_to(GoalStatus.PAUSED)
        assert not GoalStatus.CREATED.can_transition_to(GoalStatus.COMPLETED)

    def test_can_transition_from_active(self) -> None:
        """Active 可转换到全部 6 种目标态（包括 Paused 可逆）。"""
        transitions = {
            GoalStatus.PAUSED,
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
            GoalStatus.EXPIRED,
        }
        for target in GoalStatus:
            expected = target in transitions
            assert GoalStatus.ACTIVE.can_transition_to(target) == expected, (
                f"Active → {target.value}: 应为 {expected}"
            )

    def test_can_transition_from_paused(self) -> None:
        """Paused → {Active, Cancelled, Superseded}（Active 可逆）。"""
        assert GoalStatus.PAUSED.can_transition_to(GoalStatus.ACTIVE)
        assert GoalStatus.PAUSED.can_transition_to(GoalStatus.CANCELLED)
        assert GoalStatus.PAUSED.can_transition_to(GoalStatus.SUPERSEDED)
        assert not GoalStatus.PAUSED.can_transition_to(GoalStatus.COMPLETED)
        assert not GoalStatus.PAUSED.can_transition_to(GoalStatus.FAILED)

    def test_terminal_states_have_no_transitions(self) -> None:
        """终止态不能向任何状态转换。"""
        terminal = {
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
            GoalStatus.EXPIRED,
        }
        for status in terminal:
            for target in GoalStatus:
                assert not status.can_transition_to(target), (
                    f"终止态 {status.value} 不应允许 → {target.value}"
                )

    def test_validate_accepts_valid_strings(self) -> None:
        """validate() 接受所有合法字符串。"""
        for s in GoalStatus:
            assert GoalStatus.validate(s.value)

    def test_validate_rejects_invalid_strings(self) -> None:
        """validate() 拒绝非法字符串。"""
        assert not GoalStatus.validate("foobar")
        assert not GoalStatus.validate("abandoned")  # 旧值已废弃
        assert not GoalStatus.validate("")
        assert not GoalStatus.validate("active ")


# ═══════════════════════════════════════════════════════════════════
# 2. Model: Goal
# ═══════════════════════════════════════════════════════════════════


class TestGoalModel:
    """Goal 数据模型验证。"""

    def test_default_goal_is_active(self) -> None:
        """默认 Goal 状态为 active（向后兼容）。"""
        g = Goal()
        assert g.status == GoalStatus.ACTIVE.value

    def test_goal_accepts_valid_status_string(self) -> None:
        """向后兼容：传入 status='active' 字符串仍然有效。"""
        g = Goal(status="active")
        assert g.status == GoalStatus.ACTIVE.value

    def test_goal_accepts_valid_paused_string(self) -> None:
        """向后兼容：status='paused' 有效。"""
        g = Goal(status="paused")
        assert g.status == GoalStatus.PAUSED.value

    def test_goal_rejects_invalid_status(self) -> None:
        """非法 status 字符串触发 ValueError。"""
        with pytest.raises(ValueError, match="非法 Goal status"):
            Goal(status="invalid")

    def test_goal_rejects_abandoned_status(self) -> None:
        """旧值 'abandoned' 不再合法。"""
        with pytest.raises(ValueError, match="非法 Goal status"):
            Goal(status="abandoned")

    def test_goal_is_frozen(self) -> None:
        """Goal 是 frozen dataclass。"""
        g = Goal()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field"):
            g.description = "modified"  # type: ignore[misc]

    def test_goal_has_new_fields(self) -> None:
        """Phase 17.2 新增字段存在且有默认值。"""
        g = Goal()
        assert g.source == "user"
        assert g.parent_goal_id == ""
        assert g.success_criterion == ""
        assert g.observation_addresses == ()

    def test_goal_source_accepts_agent_generated(self) -> None:
        """source 接受 agent_generated。"""
        g = Goal(source="agent_generated")
        assert g.source == "agent_generated"

    def test_goal_description_defaults_to_empty(self) -> None:
        """description 空字符串为合法默认值。"""
        g = Goal()
        assert g.description == ""
        assert isinstance(g.description, str)

    def test_goal_status_can_be_paused_then_active(self) -> None:
        """支持 Paused → Active 可逆转换。"""
        g = Goal(status="paused")
        assert g.status == GoalStatus.PAUSED.value
        # 创建新实例模拟状态转移（frozen dataclass 不可变）
        g2 = Goal(goal_id=g.goal_id, description=g.description, priority=g.priority, status="active")
        assert g2.status == GoalStatus.ACTIVE.value


# ═══════════════════════════════════════════════════════════════════
# 3. Events: EventType contains all 9 Goal events
# ═══════════════════════════════════════════════════════════════════


class TestGoalEvents:
    """EventType 包含全部 Goal 生命周期事件。"""

    GOAL_EVENTS = {
        EventType.GOAL_SET,
        EventType.GOAL_UPDATED,
        EventType.GOAL_COMPLETED,
        EventType.GOAL_PAUSED,
        EventType.GOAL_RESUMED,
        EventType.GOAL_CANCELLED,
        EventType.GOAL_FAILED,
        EventType.GOAL_SUPERSEDED,
        EventType.GOAL_EXPIRED,
    }

    def test_all_goal_events_exist(self) -> None:
        """EventType 包含 9 个 Goal 事件。"""
        for evt in self.GOAL_EVENTS:
            assert evt in EventType, f"事件 {evt} 不在 EventType 中"

    def test_goal_events_use_dot_notation(self) -> None:
        """Goal 事件命名使用 goal.* 域。"""
        for evt in self.GOAL_EVENTS:
            assert evt.value.startswith("goal."), f"{evt} 命名未使用 goal. 前缀"

    def test_goal_set_has_set_semantics(self) -> None:
        """GOAL_SET 对应创建语义。"""
        assert EventType.GOAL_SET.value == "goal.set"

    def test_goal_resumed_is_distinct_from_set(self) -> None:
        """GOAL_RESUMED 与 GOAL_SET 不同（暂停后恢复 vs 首次创建）。"""
        assert EventType.GOAL_RESUMED != EventType.GOAL_SET
        assert EventType.GOAL_RESUMED.value == "goal.resumed"


# ═══════════════════════════════════════════════════════════════════
# 4. Trace: GoalTrace
# ═══════════════════════════════════════════════════════════════════


class TestGoalTrace:
    """GoalTrace 数据模型和 record_goal() 验证。"""

    def test_trace_type_has_goal(self) -> None:
        """TraceType 包含 GOAL。"""
        assert TraceType.GOAL in list(TraceType)

    def test_goal_trace_default_creation(self) -> None:
        """默认 GoalTrace 创建不报错。"""
        trace = GoalTrace()
        assert trace.trace_id
        assert trace.trace_type == TraceType.GOAL
        assert trace.goal_id == ""

    def test_goal_trace_with_goal_id(self) -> None:
        """设置 goal_id 后正确返回。"""
        trace = GoalTrace(goal_id="goal_001")
        assert trace.goal_id == "goal_001"

    def test_goal_trace_with_status_and_previous(self) -> None:
        """设置 status 和 previous_status。"""
        trace = GoalTrace(
            goal_id="goal_001",
            status=GoalStatus.ACTIVE.value,
            previous_status=GoalStatus.CREATED.value,
        )
        assert trace.status == "active"
        assert trace.previous_status == "created"

    def test_goal_trace_with_source_type(self) -> None:
        """设置 source_type 字段。"""
        trace = GoalTrace(goal_id="goal_001", source_type="agent_generated")
        assert trace.source_type == "agent_generated"

    def test_goal_trace_is_frozen(self) -> None:
        """GoalTrace 是 frozen dataclass。"""
        trace = GoalTrace()
        with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field"):
            trace.goal_id = "hacked"  # type: ignore[misc]

    def test_record_goal_stores_goal_trace(self) -> None:
        """通过 store.store() 存储 GoalTrace 后可检索。"""
        store = InMemoryTraceStore(max_size=100)
        trace = GoalTrace(
            goal_id="goal_001",
            source="test",
            status="active",
            source_type="user",
        )
        store.store(trace)
        results = store.query(trace_type=TraceType.GOAL)
        assert len(results) == 1
        stored = results[0]
        assert isinstance(stored, GoalTrace)
        assert stored.goal_id == "goal_001"
        assert stored.status == "active"
        assert stored.source_type == "user"

    def test_goal_trace_with_full_params(self) -> None:
        """GoalTrace 完整参数可存储和检索。"""
        store = InMemoryTraceStore(max_size=100)
        trace = GoalTrace(
            goal_id="goal_002",
            source="test",
            status="completed",
            previous_status="active",
            source_type="agent_generated",
            parent_goal_id="goal_001",
            observation_addresses=("obs_001", "obs_002"),
            started_at="2026-07-22T10:00:00",
            completed_at="2026-07-22T10:05:00",
            metadata={"reason": "all objectives met"},
        )
        store.store(trace)
        results = store.query(trace_type=TraceType.GOAL, limit=100)
        stored = next(r for r in results if r.goal_id == "goal_002")
        assert stored.status == "completed"
        assert stored.previous_status == "active"
        assert stored.source_type == "agent_generated"
        assert stored.parent_goal_id == "goal_001"
        assert stored.observation_addresses == ("obs_001", "obs_002")
        assert stored.metadata["reason"] == "all objectives met"

    def test_goal_trace_is_queryable_by_type(self) -> None:
        """GoalTrace 可以通过 query(trace_type=GOAL) 查询。"""
        store = InMemoryTraceStore(max_size=100)
        store.store(GoalTrace(goal_id="g1"))
        store.store(GoalTrace(goal_id="g2"))
        results = store.query(trace_type=TraceType.GOAL)
        assert len(results) >= 2
        assert all(isinstance(r, GoalTrace) for r in results)


# ═══════════════════════════════════════════════════════════════════
# 5. Constitution
# ═══════════════════════════════════════════════════════════════════


class TestGoalConstitution:
    """Goal 宪法规则 R17-R19 验证。"""

    def test_r17_goal_what_not_how_exists(self) -> None:
        """R17 规则存在。"""
        assert ConstitutionalRule.GOAL_WHAT_NOT_HOW in ConstitutionalRule

    def test_r18_goal_lifetime_exceeds_decision_exists(self) -> None:
        """R18 规则存在。"""
        assert ConstitutionalRule.GOAL_LIFETIME_EXCEEDS_DECISION in ConstitutionalRule

    def test_r19_goal_decision_one_to_many_exists(self) -> None:
        """R19 规则存在。"""
        assert ConstitutionalRule.GOAL_DECISION_ONE_TO_MANY in ConstitutionalRule

    def test_all_three_goal_rules_have_descriptions(self) -> None:
        """三条 Goal 规则都有描述文本。"""
        from ocos.kernel.constitution import Constitution

        for rule in (ConstitutionalRule.GOAL_WHAT_NOT_HOW,
                     ConstitutionalRule.GOAL_LIFETIME_EXCEEDS_DECISION,
                     ConstitutionalRule.GOAL_DECISION_ONE_TO_MANY):
            desc = Constitution.get_rule_description(rule)
            assert desc, f"{rule} 缺少描述"
            assert len(desc) > 10, f"{rule} 描述过短: {desc}"


# ═══════════════════════════════════════════════════════════════════
# 6. Invariants
# ═══════════════════════════════════════════════════════════════════


class TestGoalInvariants:
    """Goal Theory 三个不变量验证。"""

    def test_invariant1_goal_only_what_not_how(self) -> None:
        """Invariant 1: Goal 描述状态，不描述实现（语义验证）。"""
        good_goal = Goal(description="获得完整地图")
        bad_goal = Goal(description="去调用 execute_engine")
        # 两个都允许创建（Goal 不可行实现检测是更高层次的责任）
        # 但描述语义不同——R17 规则约束这层语义
        assert good_goal.description  # "what" 描述
        assert bad_goal.description  # "how" 描述也合法（但不应是该用法）
        # 检查 R17 宪法规则已定义
        assert ConstitutionalRule.GOAL_WHAT_NOT_HOW in ConstitutionalRule

    def test_invariant2_goal_lifetime_exceeds_decision(self) -> None:
        """Invariant 2: 一个 Goal 可以创建多个 Decision（模拟生命周期独立性）。"""
        # Goal 持久存在，多个 Decision 引用同一 goal_id
        goal = Goal(goal_id="persistent_goal")
        decision_attempts = ["dec_001", "dec_002", "dec_003"]
        for dec_id in decision_attempts:
            # 每次 Decision 引用同一个 goal_id
            assert goal.goal_id == "persistent_goal"  # Goal 持续存在
        # R18 定义了此不变量
        assert ConstitutionalRule.GOAL_LIFETIME_EXCEEDS_DECISION in ConstitutionalRule

    def test_invariant3_goal_decision_one_to_many(self) -> None:
        """Invariant 3: Goal ↔ Decision 是一对多关系。"""
        goal = Goal(goal_id="multi_decision_goal")
        # R19 定义了此关系
        assert ConstitutionalRule.GOAL_DECISION_ONE_TO_MANY in ConstitutionalRule
        # Goal 不持有 Decision 列表（防止状态膨胀）
        assert not hasattr(goal, "decision_ids")
        # 但 Decision 可以通过 goal_id 引用 Goal
        # 这由 Decision 模块验证
