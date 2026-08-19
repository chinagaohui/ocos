"""Phase 21 Prompt 3 测试: MasterAgent 集成与 Gate 验收。

验收条件:
1. test_factory_block_mission MUST PASS（验证 MISSION 拦截）
2. test_snapshot_atomic_lock MUST PASS（验证并发保存不丢数据）
3. test_working_memory_clear_on_sleep MUST PASS（验证 sleep 后 items 为空）
4. test_behavioral_performance: check_time_us 平均值 < 1000
5. test_boot_restore_flow: BOOT → SLEEP → BOOT 端到端一致性
6. 对已有测试集零回归
"""

import os
import tempfile

import pytest

from ocos.agent.master_agent import MasterAgent
from ocos.agent.state import AgentState
from ocos.constitution.behavioral import BehavioralConstitution
from ocos.snapshot.manager import SnapshotManager
from ocos.snapshot.models import AgentSnapshot


# ── Fake Collaborators ───────────────────────────────────────────────


class FakeIdentity:
    def __init__(self, agent_id="master", name="Test"):
        self.agent_id = agent_id
        self.name = name

    def verify(self):
        return True

    def to_dict(self):
        return {"agent_id": self.agent_id, "name": self.name}


class FakeGoalStack:
    def __init__(self):
        self._goals = []

    def peek(self):
        return self._goals[0] if self._goals else None

    def to_list(self):
        return self._goals


class FakeIntent:
    def get_intent_description(self):
        return "test intent"


class FakeAttention:
    def current_focus(self):
        return None

    def reset(self):
        pass


class FakeWorkingMemory:
    def __init__(self, capacity=100):
        self.capacity = capacity
        self._items = []

    def add(self, item):
        self._items.append(item)

    def clear(self):
        self._items = []

    def list_items(self):
        return self._items


class FakeCapabilityManager:
    def list_capabilities(self):
        return []


class FakeExecutionManager:
    def is_executing(self):
        return False


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_snapshot_db():
    """创建带有 snapshots 表的临时数据库。"""
    import sqlite3
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            is_recovered BOOLEAN DEFAULT 0,
            data JSON NOT NULL,
            size_kb INTEGER,
            recovered_at TIMESTAMP,
            agent_id TEXT DEFAULT 'master'
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON snapshots(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshots_recovered ON snapshots(is_recovered);
    """)
    conn.close()
    old_db = os.environ.get("OCOS_DB_PATH")
    os.environ["OCOS_DB_PATH"] = path
    yield path
    if old_db:
        os.environ["OCOS_DB_PATH"] = old_db
    os.unlink(path)


@pytest.fixture
def snapshot_mgr(temp_snapshot_db):
    return SnapshotManager(db_path=temp_snapshot_db)


@pytest.fixture
def constitution():
    return BehavioralConstitution()


@pytest.fixture
def master_agent(snapshot_mgr, constitution):
    """创建带有 Phase 21 能力的 MasterAgent。"""
    return MasterAgent(
        agent_id="test-agent",
        identity=FakeIdentity(agent_id="test-agent", name="Test"),
        goal_stack=FakeGoalStack(),
        intent=FakeIntent(),
        attention=FakeAttention(),
        working_memory=FakeWorkingMemory(capacity=100),
        capability_manager=FakeCapabilityManager(),
        execution_manager=FakeExecutionManager(),
        snapshot_mgr=snapshot_mgr,
        constitution=constitution,
    )


# ── Gate 1: MISSION 拦截 ────────────────────────────────────────────


def test_gate1_mission_blocked():
    """Gate 1: GoalFactory 拒绝 MISSION 级别。"""
    from ocos.agent.goal_types import GoalLevel
    from ocos.goal.factory import GoalFactory, ConstitutionViolationError

    with pytest.raises(ConstitutionViolationError, match="Mission"):
        GoalFactory.create(level=GoalLevel.MISSION, description="Become sentient")


# ── Gate 2: Snapshot 原子锁 ─────────────────────────────────────────


def test_gate2_snapshot_atomic_lock(snapshot_mgr):
    """Gate 2: 并发保存不丢数据。"""
    import threading

    errors = []
    results = []

    def save_snapshot(i):
        try:
            snap = AgentSnapshot(
                snapshot_id=f"snap-gate2-{i}",
                identity_state={"index": i},
            )
            sid = snapshot_mgr.save(snap)
            results.append(sid)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=save_snapshot, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors: {errors}"
    assert len(results) == 10


# ── Gate 3: WorkingMemory items 为空 ─────────────────────────────────


def test_gate3_working_memory_clear_on_sleep(master_agent):
    """Gate 3: sleep 后 WorkingMemory items 为空。"""
    # 1. 放一些 items 到 WorkingMemory
    master_agent.working_memory.add("item-1")
    master_agent.working_memory.add("item-2")
    assert len(master_agent.working_memory.list_items()) == 2

    # 2. boot（需要在 sleep 之前）
    master_agent.boot()

    # 3. sleep
    master_agent.sleep()

    # 4. items 为空
    assert len(master_agent.working_memory.list_items()) == 0

    # 5. Snapshot 中 items 也为空（验证最近一条快照）
    snapshot = master_agent._snapshot_mgr.load_latest()
    assert snapshot is not None
    assert snapshot.working_memory_config.get("items", ["NOT_EMPTY"]) == []


# ── Gate 4: Behavioral Performance ───────────────────────────────────


def test_gate4_behavioral_performance():
    """Gate 4: check_decision 平均耗时 < 1000us。"""
    from ocos.constitution.behavioral import BehavioralConstitution

    bc = BehavioralConstitution()

    class D:
        action = "READ_DATA"

    context = {"agent_state": "WAKE"}
    # 预热
    bc.check_decision(D, context)

    total = 0
    for _ in range(10):
        r = bc.check_decision(D, context)
        total += r.check_time_us

    avg = total // 10
    assert avg < 1000, f"Average {avg}us exceeds 1000us"


# ── Gate 5: BOOT → SLEEP → BOOT 端到端 ───────────────────────────────


def test_gate5_boot_sleep_boot_cycle(master_agent, snapshot_mgr):
    """Gate 5: BOOT → SLEEP → BOOT 生命周期中状态一致性。

    验证: sleep 后 Snapshot 被保存，重新 boot 可恢复。
    """
    # 1. 首次 boot
    master_agent.boot()
    assert master_agent.state.status.name == "IDLE"

    # 2. 设置一些状态
    master_agent.working_memory.add("observation-1")

    # 3. sleep — 应保存 Snapshot
    master_agent.sleep()
    assert master_agent.state.status.name == "SLEEP"
    assert len(master_agent.working_memory.list_items()) == 0

    # 4. Snapshot 已保存
    snapshot = snapshot_mgr.load_latest()
    assert snapshot is not None
    assert snapshot.version == "1.0"

    # 5. 创建新 Agent 模拟重启后的 boot
    new_agent = MasterAgent(
        agent_id="test-agent",
        identity=FakeIdentity(agent_id="test-agent", name="Test"),
        goal_stack=FakeGoalStack(),
        intent=FakeIntent(),
        attention=FakeAttention(),
        working_memory=FakeWorkingMemory(capacity=100),
        capability_manager=FakeCapabilityManager(),
        execution_manager=FakeExecutionManager(),
        snapshot_mgr=snapshot_mgr,
        constitution=None,
    )
    new_agent.boot()
    # 应成功恢复（Snapshot 存在）
    assert new_agent.state.status.name == "IDLE"


# ── Gate 6: 零回归 — Constitution 拦截 Decision ─────────────────────


def test_gate6_decide_with_constitution_normal(master_agent):
    """Gate 6: 正常 Decision 通过 Constitution 检查。

    遵循完整生命周期: boot → observe → think → decide。
    Phase 22 LifecycleManager 微状态映射:
      observe(OBSERVING) → agent_status=THINKING
      think(THINKING)     → agent_status=THINKING (no change)
      decide(DECIDING)    → agent_status=DECIDING
      act(ACTING)         → agent_status=ACTING
    """
    master_agent.boot()
    assert master_agent.state.status.name == "IDLE"

    master_agent.observe()
    assert master_agent.state.status.name == "THINKING"
    master_agent.think()
    result = master_agent.decide()

    assert result is not None
    assert "based_on" in result
    assert master_agent.state.status.name == "DECIDING"


def test_gate6_normal_boot_works_without_constitution(snapshot_mgr):
    """没有 constitution 也能正常 boot。"""
    agent = MasterAgent(
        agent_id="plain-agent",
        identity=FakeIdentity(),
        goal_stack=FakeGoalStack(),
        intent=FakeIntent(),
        attention=FakeAttention(),
        working_memory=FakeWorkingMemory(),
        capability_manager=FakeCapabilityManager(),
        execution_manager=FakeExecutionManager(),
        snapshot_mgr=snapshot_mgr,
        constitution=None,  # 无 constitution
    )
    agent.boot()
    assert agent.state.status.name == "IDLE"
