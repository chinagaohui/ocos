"""S1.1: DecisionBridge FILE_WRITE 强制审批回归（白皮书 P1-1）。

FILE_WRITE 属强制审批动作：
- LLM 规划的文件写入无 approval_id 时必须入待批队列，
  不受 OCOS_APPROVAL_MODE=auto 影响；
- 伪造 / 未批准的 approval_id 在 execute_approved 与 _handler_file_op
  两层被拒（防自造 "task-approved" 绕过守门）。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ocos.execution.bridge import DecisionBridge
from ocos.execution.pending import PendingStore
from ocos.planning.models import Task


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
    # 关键: 默认 auto 模式下 FILE_WRITE 也必须强制待批
    monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")
    return PendingStore(str(tmp_path / "t.db"))


class _FakeProvider:
    """返回预设动作行的 LLM 桩。"""

    def __init__(self, lines: list[str]):
        self._lines = list(lines)

    def generate(self, prompt, system_prompt="", temperature=0.1, max_tokens=2000):
        async def _gen():
            return self._lines.pop(0) if self._lines else "NONE|stub"
        return _gen()


@pytest.fixture
def bridge(store, monkeypatch):
    b = DecisionBridge(pending_store=store)
    b.attach_default_handlers()
    monkeypatch.setattr(b, "_llm_available", lambda: True)
    monkeypatch.setattr(b, "_llm_budget_ok", lambda: (True, ""))
    return b


def _stub_llm(bridge, monkeypatch, lines):
    tg = SimpleNamespace(_provider=_FakeProvider(lines))
    monkeypatch.setattr(bridge, "_get_textgen", lambda: tg)


def _task(desc: str, task_type: str = "execute") -> Task:
    return Task.create(goal_id="g-s11", description=desc, task_type=task_type,
                       agent_type="writer")


class TestFileWriteForcedApproval:
    def test_llm_file_write_without_approval_goes_pending(self, store, bridge,
                                                          monkeypatch, tmp_path):
        """LLM 输出 FILE_WRITE 且无 approval_id → 入待批而非执行。"""
        probe = tmp_path / "probe_s11.txt"
        _stub_llm(bridge, monkeypatch,
                  [f"FILE_WRITE|{probe}|hello"])
        result = bridge.execute_dag_task(_task("创建文件并写入 hello"))
        assert result["status"] == "pending_approval", result
        rows = store.list_by_status("pending")
        assert len(rows) == 1
        assert rows[0]["action_type"] == "file_op"
        body = json.loads(rows[0]["payload_json"])
        assert body["op_type"] == "file_write"
        assert body["target"] == str(probe)
        assert not probe.exists(), "未批准的文件写入不得落盘"

    def test_forged_approval_id_rejected_in_file_op(self, store, tmp_path):
        """自造 approval_id（旧代码默认 "task-approved"）→ 拒绝执行。"""
        bridge = DecisionBridge(pending_store=store)
        bridge.attach_default_handlers()
        probe = tmp_path / "forged.txt"
        result = bridge._handler_file_op(SimpleNamespace(payload={
            "op_type": "file_write", "target": str(probe),
            "params": {"content": "x"},
            "approval_id": "task-approved"}))
        assert result["ok"] is False
        assert "approval" in result["error"].lower()
        assert not probe.exists()

    def test_approved_file_write_flow(self, store, bridge, monkeypatch, tmp_path):
        """完整审批流：待批 → 人工批准 → execute_approved 真实落盘。"""
        probe = tmp_path / "probe_approved.txt"
        _stub_llm(bridge, monkeypatch, [f"FILE_WRITE|{probe}|hello"])
        bridge.execute_dag_task(_task("创建文件并写入 hello"))
        row = store.list_by_status("pending")[0]
        assert store.decide(row["id"], approved=True, decided_by="test")
        payload = json.loads(row["payload_json"])
        payload["approval_id"] = row["id"]
        dispatched = bridge.execute_approved("file_op", payload)
        assert dispatched is not None and dispatched.status == "done", dispatched
        assert probe.read_text(encoding="utf-8") == "hello"

    def test_execute_approved_rejects_unapproved_pid(self, store):
        """execute_approved 对不存在/未批准的 approval_id 诚实拒绝。"""
        bridge = DecisionBridge(pending_store=store)
        bridge.attach_default_handlers()
        dispatched = bridge.execute_approved("file_op", {
            "op_type": "file_write", "target": "/tmp/x.txt",
            "params": {"content": "y"}, "approval_id": "PEND-nonexistent"})
        assert dispatched is None or getattr(dispatched, "status", "") != "done"
