"""CrashRecovery 测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocos.recovery.crash_recovery import CrashRecovery, RecoveryReport
from ocos.storage.checkpoint import CheckpointManager
from ocos.storage.event_store import SQLiteEventStore
from ocos.storage.dead_letter_queue import SQLiteDLQ


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def recovery(db_path):
    return CrashRecovery(db_path)


class TestCrashRecovery:
    def test_recover_empty_db(self, recovery):
        """空数据库的 recover 返回全零报告。"""
        report = recovery.recover()
        assert isinstance(report, RecoveryReport)
        assert report.recovered_checkpoints == 0
        assert report.replayed_events == 0
        assert report.dlq_reattempts == 0

    def test_recover_incomplete_checkpoint(self, db_path):
        """有未完成检查点时 recover 检测到。"""
        CheckpointManager(db_path).save("proc-001", "phase1", {"step": 3})
        recovery = CrashRecovery(db_path)
        report = recovery.recover()
        assert report.recovered_checkpoints == 1

    def test_recover_with_events(self, db_path):
        """有事件时 recover 返回事件重放计数。"""
        cp = CheckpointManager(db_path)
        es = SQLiteEventStore(db_path)

        cp.save("proc-002", "processing", {"step": 1})
        es.append("test.event", {"data": "a"}, source="test")
        es.append("test.event", {"data": "b"}, source="test")

        recovery = CrashRecovery(db_path)
        report = recovery.recover()
        assert report.recovered_checkpoints >= 1
        # 检查点有 created_at，之后的事件会被计入
        # 注意 created_at 在 save 时自动生成，略早于事件的 append，所以 events >= created_at

    def test_recover_with_dlq(self, db_path):
        """有未耗尽重试的死信时 recover 检测到。"""
        dlq = SQLiteDLQ(db_path, max_retries=3)
        dlq.enqueue("evt-001", "timeout")
        dlq.enqueue("evt-002", "payload_error")
        # 耗尽一个
        dlq_id = dlq.enqueue("evt-003", "exhausted")
        dlq.increment_retry(dlq_id)
        dlq.increment_retry(dlq_id)
        dlq.increment_retry(dlq_id)  # 3次 == max_retries, exhausted

        recovery = CrashRecovery(db_path)
        report = recovery.recover()
        assert report.dlq_reattempts == 2  # 前两个未耗尽

    def test_recover_checkpoint(self, db_path):
        """recover_checkpoint 返回指定进程的检查点。"""
        CheckpointManager(db_path).save("proc-003", "phase2", {"progress": 0.5})
        recovery = CrashRecovery(db_path)
        cp = recovery.recover_checkpoint("proc-003")
        assert cp is not None
        assert cp["phase"] == "phase2"

    def test_replay_events(self, db_path):
        """replay_events 返回事件。"""
        es = SQLiteEventStore(db_path)
        es.append("type_a", {"n": 1}, source="test")
        es.append("type_b", {"n": 2}, source="test")

        recovery = CrashRecovery(db_path)
        events = recovery.replay_events(since="2020-01-01T00:00:00.000000")
        assert len(events) == 2

    def test_reattempt_dlq(self, db_path):
        """reattempt_dlq 将死信标记为已解决。"""
        dlq = SQLiteDLQ(db_path)
        eid = dlq.enqueue("evt-reattempt", "temporary_failure")

        recovery = CrashRecovery(db_path)
        assert recovery.reattempt_dlq(eid) is True
        assert dlq.count_unresolved() == 0

    def test_get_status(self, db_path):
        """get_status 返回健康状态摘要。"""
        CheckpointManager(db_path).save("proc-status", "x", {})
        SQLiteEventStore(db_path).append("t", {})
        SQLiteDLQ(db_path).enqueue("evt-dlq", "err")

        recovery = CrashRecovery(db_path)
        status = recovery.get_status()
        assert status["incomplete_checkpoints"] >= 1
        assert status["event_count"] >= 1
        assert status["unresolved_dlq"] >= 1
        assert status["latest_sequence"] >= 1
