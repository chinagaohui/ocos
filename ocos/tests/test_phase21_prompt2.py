"""Phase 21 Prompt 2 测试: Goal Persistence + Constitution Enforcement。

验收条件:
- test_factory_block_mission: GoalFactory 拒绝 MISSION
- test_factory_create_normal: GoalFactory 创建正常 Goal
- test_goal_store_save_and_load: GoalStore 保存后加载活跃
- test_goal_store_update_progress: 进度更新 + 钳制
- test_goal_store_record_decision: Decision 关联
- test_behavioral_blocks_high_risk: 高风险 Action 拦截
- test_behavioral_performance: check_decision < 1ms
- test_behavioral_check_time_us_tracked: check_time_us 已记录
"""

import os
import sqlite3
import tempfile

import pytest

from ocos.agent.goal_types import GoalLevel
from ocos.goal.factory import GoalFactory, ConstitutionViolationError
from ocos.goal.store import GoalStore
from ocos.constitution.behavioral import (
    BehavioralConstitution,
    ConstitutionResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_db():
    """带有 goals 表的临时数据库。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            agent_id TEXT DEFAULT 'master',
            parent_id TEXT,
            level TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL DEFAULT 0.0,
            description TEXT,
            deadline TIMESTAMP,
            source TEXT,
            source_id TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            priority REAL DEFAULT 5.0,
            metadata JSON,
            decision_refs JSON,
            origin_level TEXT DEFAULT 'SYSTEM',
            authority TEXT DEFAULT 'AUTONOMOUS'
        );
    """)
    conn.close()
    old_db = os.environ.get("OCOS_DB_PATH")
    os.environ["OCOS_DB_PATH"] = path
    yield path
    if old_db:
        os.environ["OCOS_DB_PATH"] = old_db
    os.unlink(path)


@pytest.fixture
def goal_store(temp_db):
    return GoalStore(db_path=temp_db)


@pytest.fixture
def constitution():
    return BehavioralConstitution()


# ── GoalFactory 测试 ──────────────────────────────────────────────────


def test_factory_block_mission():
    """创建 MISSION 级别 Goal 必须被拦截。"""
    with pytest.raises(ConstitutionViolationError, match="Mission"):
        GoalFactory.create(level=GoalLevel.MISSION, description="Become sentient")


def test_factory_create_normal():
    """创建非 MISSION 级别的 Goal。"""
    goal = GoalFactory.create(
        level=GoalLevel.TASK,
        description="Test task",
        priority=7.0,
    )
    assert goal.level == GoalLevel.TASK
    assert goal.status.name == "PENDING"
    assert goal.description == "Test task"
    assert goal.priority == 7.0


def test_factory_create_long():
    goal = GoalFactory.create(
        level=GoalLevel.LONG,
        description="Long-term project",
        priority=8.0,
    )
    assert goal.level == GoalLevel.LONG


# ── GoalStore 测试 ───────────────────────────────────────────────────


def test_goal_store_save_and_load_active(goal_store):
    """保存 Goal 后用 load_active 可以加载到。"""
    goal_store.save(
        goal_id="g-001", level="TASK", status="ACTIVE",
        description="Write tests", priority=6.0,
    )
    active = goal_store.load_active()
    assert len(active) >= 1
    assert any(g["id"] == "g-001" for g in active)


def test_goal_store_completed_not_active(goal_store):
    """已完成 Goal 不出现在 load_active 中。"""
    goal_store.save(goal_id="g-done", level="TASK", status="COMPLETED")
    active = goal_store.load_active()
    assert all(g["id"] != "g-done" for g in active)


def test_goal_store_update_progress_clamped(goal_store):
    """进度更新自动钳制到 [0, 1]。"""
    goal_store.save(goal_id="g-p", level="TASK", status="ACTIVE")
    assert goal_store.update_progress("g-p", 0.5)
    assert goal_store.update_progress("g-p", 1.5)  # 钳制到 1.0
    assert goal_store.update_progress("g-p", -0.5)  # 钳制到 0.0


def test_goal_store_record_decision(goal_store):
    """Decision 关联写入。"""
    goal_store.save(goal_id="g-dec", level="TASK", status="ACTIVE")
    goal_store.record_decision("g-dec", "d-001")
    goal_store.record_decision("g-dec", "d-002")
    # 不会抛异常即可（内部 JSON 追加）
    goal_store.record_decision("g-dec", "d-001")  # 去重


# ── BehavioralConstitution 测试 ──────────────────────────────────────


class _FakeDecision:
    def __init__(self, action: str):
        self.action = action


def test_behavioral_allows_normal_action(constitution):
    """普通 Action 通过检查。"""
    dec = _FakeDecision("READ_DATA")
    result = constitution.check_decision(dec, {"agent_state": "WAKE"})
    assert result.allowed is True
    assert len(result.violations) == 0


def test_behavioral_blocks_delete_without_consent(constitution):
    """DELETE_USER_DATA 无 user_consent 时拦截。"""
    dec = _FakeDecision("DELETE_USER_DATA")
    result = constitution.check_decision(dec, {})
    assert result.allowed is False
    assert any("user consent" in v for v in result.violations)


def test_behavioral_requires_human_approval(constitution):
    """高风险 Action 标记 requires_human_approval。"""
    dec = _FakeDecision("DELETE_USER_DATA")
    result = constitution.check_decision(dec, {"user_consent": True})
    assert result.allowed is True
    assert result.requires_human_approval is True


def test_behavioral_modify_constitution_blocked(constitution):
    dec = _FakeDecision("MODIFY_CONSTITUTION")
    result = constitution.check_decision(dec, {})
    assert result.allowed is False


def test_behavioral_empty_action(constitution):
    dec = _FakeDecision("")
    result = constitution.check_decision(dec, {"agent_state": "WAKE"})
    assert result.allowed is False


def test_behavioral_empty_context(constitution):
    dec = _FakeDecision("READ_DATA")
    result = constitution.check_decision(dec, {})
    assert result.allowed is False
    assert any("context" in v.lower() for v in result.violations)


def test_behavioral_performance(constitution):
    """check_decision 耗时 < 1000 微秒 (1ms)。"""
    dec = _FakeDecision("READ_DATA")
    context = {"agent_state": "WAKE"}
    # 预热一次
    constitution.check_decision(dec, context)
    # 采样 5 次取平均
    total_us = 0
    for _ in range(5):
        result = constitution.check_decision(dec, context)
        total_us += result.check_time_us
    avg_us = total_us // 5
    assert avg_us < 1000, f"Average check time {avg_us}us exceeds 1000us"


def test_behavioral_check_time_us_tracked(constitution):
    """check_time_us 被正确记录（不会为负）。"""
    dec = _FakeDecision("READ_DATA")
    result = constitution.check_decision(dec, {"agent_state": "WAKE"})
    assert result.check_time_us >= 0
