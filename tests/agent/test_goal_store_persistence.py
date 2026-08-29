"""GoalSQLiteStore 真实持久化测试（P2-A 验收锚点）。

此前 GoalSQLiteStore 真实路径零测试覆盖（tests/ 内无引用）；
2026-08-29 P2-A 修复 initialize() 建表缺失后补此契约测试。
"""

from ocos.agent.goal_store import GoalSQLiteStore
from ocos.kernel.goal_types import (
    Goal,
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
    GoalStatus,
)


def _make_self_goal(description: str, priority: float) -> Goal:
    return Goal(
        goal_id=f"self-{abs(hash(description)) % 10**6}",
        level=GoalLevel.SHORT,
        description=description,
        priority=priority,
        status=GoalStatus.PENDING,
        origin_level=GoalOriginLevel.SELF,
        authority=GoalAuthority.AUTONOMOUS,
        metadata={"drive": "EXPLORE"},
    )


class TestGoalSQLiteStorePersistence:
    def test_initialize_creates_table(self, tmp_path):
        """initialize() 必须建表（P2-A 修复的回归锚点）。"""
        store = GoalSQLiteStore(str(tmp_path / "goals.db"))
        store.initialize()
        try:
            store.connection.execute("SELECT 1 FROM goal LIMIT 1")
        finally:
            store.close()

    def test_save_and_load_active_roundtrip(self, tmp_path):
        store = GoalSQLiteStore(str(tmp_path / "goals.db"))
        store.initialize()
        try:
            goal = _make_self_goal("内生目标", 0.5)
            store.save(goal)
            active = store.load_active()
            assert len(active) == 1
            assert active[0].goal_id == goal.goal_id
            assert active[0].origin_level == GoalOriginLevel.SELF
            assert active[0].priority == 0.5
        finally:
            store.close()

    def test_save_idempotent(self, tmp_path):
        store = GoalSQLiteStore(str(tmp_path / "goals.db"))
        store.initialize()
        try:
            goal = _make_self_goal("幂等目标", 0.4)
            store.save(goal)
            store.save(goal)
            assert len(store.load_active()) == 1
        finally:
            store.close()

    def test_reopen_persists(self, tmp_path):
        """跨连接重开：目标必须仍在（文件持久化语义）。"""
        path = str(tmp_path / "goals.db")
        goal = _make_self_goal("跨连接目标", 0.6)
        s1 = GoalSQLiteStore(path)
        s1.initialize()
        s1.save(goal)
        s1.close()

        s2 = GoalSQLiteStore(path)
        s2.initialize()
        try:
            active = s2.load_active()
            assert len(active) == 1
            assert active[0].description == "跨连接目标"
        finally:
            s2.close()
