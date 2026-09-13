"""S1.1: DecisionBridge FILE_WRITE 审批回归（白皮书 P1-1, 政策更新 2026-09-12）。

审批语义按模式划分（AUD-FIX 2026-09-12）：
- auto 模式（自主循环无人值守）: FILE_WRITE 直通执行, 不入待批队列;
  敏感路径（~/.ssh、/etc、/root…）由 file_ops._is_protected 拒绝落盘;
- ask 模式（人工审批）: LLM 规划的文件写入无 approval_id 时必须入待批队列;
- 伪造 / 未批准的 approval_id 在 execute_approved 与 _handler_file_op
  两层被拒（防自造 "task-approved" 绕过守门）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
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
    def test_llm_file_write_auto_mode_direct_execution(self, store, bridge,
                                                       monkeypatch, tmp_path):
        """AUD-FIX (2026-09-12) 政策更新: auto 模式 FILE_WRITE 直通执行,
        不入待批队列 (自主循环无人值守); 敏感路径仍被 file_ops._is_protected
        拒绝 (安全底线)。白皮书 S1.1 的"一律入待批"仅适用于 ask 模式。"""
        probe = tmp_path / "probe_s11.txt"
        _stub_llm(bridge, monkeypatch,
                  [f"FILE_WRITE|{probe}|hello"])
        result = bridge.execute_dag_task(_task("创建文件并写入 hello"))
        assert result["status"] == "completed", result
        assert result["result"]["ok"] is True
        assert probe.read_text(encoding="utf-8") == "hello"
        assert store.list_by_status("pending") == []

    def test_llm_file_write_auto_mode_protected_path_rejected(self, bridge,
                                                              monkeypatch,
                                                              tmp_path):
        """auto 直通的底线: ~/.ssh 等敏感路径必须拒绝且不得落盘。"""
        probe = Path.home() / ".ssh" / f"ocos_audit_{os.getpid()}.txt"
        _stub_llm(bridge, monkeypatch,
                  [f"FILE_WRITE|{probe}|evil"])
        result = bridge.execute_dag_task(_task("写入敏感路径"))
        assert probe.exists() is False, "敏感路径写入必须被拒"
        # ok=False 或 status 诚实失败均可, 但绝不能成功落盘
        if result["status"] == "completed":
            assert result["result"].get("ok") is not True, result

    def test_llm_file_write_ask_mode_goes_pending(self, store, bridge,
                                                  monkeypatch, tmp_path):
        """ask 模式（人工审批）下 FILE_WRITE 无 approval_id → 入待批,
        白皮书 S1.1 语义在 ask 模式完整保留。"""
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
        probe = tmp_path / "probe_ask.txt"
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
        """完整审批流（ask 模式）：待批 → 人工批准 → execute_approved 真实落盘。"""
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
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
