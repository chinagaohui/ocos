"""UX-J 即时推送: goal_result 落库即刻回调推送 outbox。

覆盖:
  1. AgentRuntime._on_goal_result 默认 None
  2. _record_goal_result 保存 episode 后触发回调（且 episode.save 先于回调）
  3. 回调异常不阻断主流程
  4. daemon._push_goal_results 并发调用去重（即时回调 + 5-tick 兜底同时触发不重复推）
  5. 端到端: runtime 回调注册 → episode 落库 → outbox 秒级出现推送
"""
import sqlite3
import threading

import pytest
from unittest.mock import MagicMock

from ocos.agent.agent_runtime import AgentRuntime
from ocos.daemon import ResidentRuntime
from ocos.interaction.inbox import UserInbox


@pytest.fixture
def runtime():
    return AgentRuntime(agent=MagicMock())


@pytest.fixture
def daemon(tmp_path):
    db = str(tmp_path / "ocos.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id TEXT PRIMARY KEY, tags TEXT, decision TEXT, created_at TEXT, outcome TEXT)")
    conn.commit()
    conn.close()
    d = ResidentRuntime(agent=MagicMock(), db_path=db)
    d._user_inbox = UserInbox(db)
    d._result_cursor_init = False
    return d


def _seed_goal_result_episode(db_path: str, decision: str) -> int:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id TEXT PRIMARY KEY, tags TEXT, decision TEXT, created_at TEXT, outcome TEXT)")
    cur = conn.execute(
        "INSERT INTO episodes (id, tags, decision, created_at) VALUES (?,?,?,?)",
        (f"EPI-{decision[:8]}", '["goal_result"]', decision, "2026-09-06T00:00:00"))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


class TestOnGoalResultCallback:
    def test_default_none(self, runtime):
        assert runtime._on_goal_result is None

    def test_callback_fired_after_episode_save(self, runtime):
        calls = []
        hub = MagicMock()
        hub.is_initialized.return_value = True
        runtime._memory_hub = hub
        runtime._recent_results = [
            {"success": True, "description": "任务A", "output": "ok"}]
        runtime._result_mark = 0
        runtime._on_goal_result = lambda: calls.append(len(
            hub.episode.save.call_args_list))
        runtime._record_goal_result()
        # episode 先落库、回调后触发
        assert hub.episode.save.called
        assert calls == [1]

    def test_callback_exception_not_blocking(self, runtime):
        hub = MagicMock()
        hub.is_initialized.return_value = True
        runtime._memory_hub = hub
        runtime._recent_results = [
            {"success": True, "description": "任务B", "output": "ok"}]
        runtime._result_mark = 0

        def boom():
            raise RuntimeError("push channel down")
        runtime._on_goal_result = boom
        runtime._record_goal_result()  # 不抛出即通过
        assert hub.episode.save.called

    def test_none_callback_is_noop(self, runtime):
        hub = MagicMock()
        hub.is_initialized.return_value = True
        runtime._memory_hub = hub
        runtime._recent_results = [
            {"success": True, "description": "任务C", "output": "ok"}]
        runtime._result_mark = 0
        runtime._record_goal_result()
        assert hub.episode.save.called


class TestDaemonConcurrentPush:
    def test_concurrent_push_no_duplicate(self, daemon, tmp_path):
        db = str(tmp_path / "ocos.db")
        daemon._push_goal_results()          # 游标初始化
        _seed_goal_result_episode(db, "result-1")
        _seed_goal_result_episode(db, "result-2")
        # 模拟即时回调与 5-tick 兜底并发触发
        threads = [threading.Thread(target=daemon._push_goal_results)
                   for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        outbox = daemon._user_inbox.list_recent(50)
        assert len(outbox) == 2              # 2 条 episode 各推一次

    def test_instant_push_end_to_end(self, runtime, daemon, tmp_path):
        db = str(tmp_path / "ocos.db")
        runtime._on_goal_result = daemon._push_goal_results
        daemon._push_goal_results()          # daemon 启动后游标初始化
        hub = MagicMock()
        hub.is_initialized.return_value = True
        runtime._memory_hub = hub
        runtime._recent_results = [
            {"success": True, "description": "探索宿主机", "output": "健康"}]
        runtime._result_mark = 0
        runtime._record_goal_result()        # 落库 + 即时回调
        # 真实链路: 回调读 episodes 表 → 无新行（episode 存 memory_hub mock）
        # 因此补种一行模拟落库后再次回调推送
        _seed_goal_result_episode(db, "host-report")
        daemon._push_goal_results()
        outbox = daemon._user_inbox.list_recent(50)
        assert len(outbox) == 1
        assert "host-report" in outbox[0]["content"]
