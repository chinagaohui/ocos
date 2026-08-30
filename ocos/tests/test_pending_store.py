"""AUD-F12: PendingStore + DecisionBridge 待批队列持久化测试。"""

from __future__ import annotations

import pytest

from ocos.execution.bridge import DecisionBridge
from ocos.execution.pending import PendingStore
from ocos.planning.models import Task


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "test.db"))
    return PendingStore(str(tmp_path / "test.db"))


class TestPendingStore:
    def test_enqueue_and_list(self, store):
        pid = store.enqueue("WRITE_CHAPTER", target="open_tale",
                            payload={"p": 1}, text="write ch1", source="test")
        assert pid.startswith("PEND-")
        rows = store.list_by_status("pending")
        assert len(rows) == 1
        assert rows[0]["action_type"] == "WRITE_CHAPTER"

    def test_decide_approve_and_deny(self, store):
        pid = store.enqueue("SEARCH_WEB", text="q")
        assert store.decide(pid, approved=True, decided_by="cli")
        assert store.get(pid)["status"] == "approved"
        assert store.get(pid)["decided_by"] == "cli"
        # 已决定 → 不可重复决定
        pid2 = store.enqueue("SEARCH_WEB", text="q2")
        assert store.decide(pid2, approved=False)
        assert not store.decide(pid2, approved=False)

    def test_mark_executed_states(self, store):
        pid = store.enqueue("dag_create", text="t")
        store.decide(pid, True)
        store.mark_executed(pid, result_summary="ok", executed=True)
        assert store.get(pid)["status"] == "executed"
        pid2 = store.enqueue("dag_modify", text="t2")
        store.decide(pid2, True)
        store.mark_executed(pid2, result_summary="no executor", executed=False)
        assert store.get(pid2)["status"] == "blocked"


class TestBridgePersistence:
    def test_ask_action_persists(self, store):
        bridge = DecisionBridge(pending_store=store)
        bridge.attach_default_handlers()
        report = bridge.process({
            "status": "completed",
            "action_result": {"based_on": {"message": "write chapter 12"}},
        })
        assert "WRITE_CHAPTER" in report.summary()["pending"]
        assert len(store.list_by_status("pending")) == 1

    def test_dag_ask_persists(self, store):
        bridge = DecisionBridge(pending_store=store)
        bridge.attach_default_handlers()
        task = Task.create(goal_id="G1", description="create file",
                           task_type="create", agent_type="writer")
        assert bridge.execute_dag_task(task)["status"] == "pending_approval"
        rows = store.list_by_status("pending")
        assert rows[0]["action_type"] == "dag_create"

    def test_memory_fallback_without_store(self):
        """无 store → 内存回退（诚实降级），pending_actions 仍可见。"""
        bridge = DecisionBridge()
        bridge.attach_default_handlers()
        bridge.process({
            "status": "completed",
            "action_result": {"based_on": {"message": "write chapter 1"}},
        })
        assert len(bridge.pending_actions) == 1
