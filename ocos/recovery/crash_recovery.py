"""CrashRecovery — 崩溃恢复管理器。

职责：
- 在系统启动时扫描未完成的检查点
- 从 EventStore 重放丢失的事件
- 将未处理的死信重新入队
- 提供恢复报告

职责分工(GAP-P3-3 裁决): 本模块 = 进程级完整恢复管理器
(recover_checkpoint/replay_events/reattempt_dlq, 依赖 storage
三件套 checkpoint/event_store/dead_letter_queue, 由
tests/recovery/test_crash_recovery.py 契约锁定);
ocos/snapshot/recovery.py = agent 轻量快照恢复(CrashRecovery.
recover 从最新 AgentSnapshot 恢复, master_agent 生产路径在用)。
两套同名 CrashRecovery 职责不同、并存不合并; 命名统一留待
后续阶段。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.storage.checkpoint import CheckpointManager
from ocos.storage.event_store import SQLiteEventStore
from ocos.storage.dead_letter_queue import SQLiteDLQ


@dataclass
class RecoveryReport:
    """崩溃恢复报告。"""
    recovered_checkpoints: int = 0
    replayed_events: int = 0
    dlq_reattempts: int = 0
    failed: list[str] = field(default_factory=list)


class CrashRecovery:
    """崩溃恢复管理器。

    Args:
        db_path: SQLite 数据库文件路径。
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._checkpoint = CheckpointManager(db_path)
        self._event_store = SQLiteEventStore(db_path)
        self._dlq = SQLiteDLQ(db_path)

    # ── 主要恢复流程 ──────────────────────────────────────────────────────────

    def recover(self, max_events: int = 1000) -> RecoveryReport:
        """执行完整恢复流程。

        流程：
        1. 扫描未完成的检查点
        2. 重放未完成进程的事件
        3. 检查死信队列中是否有可重新尝试的条目

        Args:
            max_events: 重放的最大事件数。

        Returns:
            恢复报告。
        """
        report = RecoveryReport()

        # 1. 恢复未完成的检查点
        incomplete = self._checkpoint.list_incomplete()
        report.recovered_checkpoints = len(incomplete)

        stale_events = []
        for cp in incomplete:
            try:
                # 2. 重放该检查点之后的事件
                events = self._event_store.replay(
                    since=cp["created_at"],
                    limit=max_events,
                )
                stale_events.extend(events)
            except Exception as e:
                report.failed.append(f"checkpoint:{cp['process_id']}:{e}")

        report.replayed_events = len(stale_events)

        # 3. 检查死信队列
        unresolved = self._dlq.list_unresolved()
        reattemptable = [d for d in unresolved if not self._dlq.is_exhausted(d["id"])]
        report.dlq_reattempts = len(reattemptable)

        return report

    # ── 逐项恢复 ──────────────────────────────────────────────────────────────

    def recover_checkpoint(self, process_id: str) -> Optional[dict[str, Any]]:
        """恢复指定进程的检查点。"""
        return self._checkpoint.load(process_id)

    def replay_events(self, since: str, limit: int = 500) -> list[dict[str, Any]]:
        """重放指定时间之后的事件。"""
        return self._event_store.replay(since=since, limit=limit)

    def reattempt_dlq(self, dlq_id: int) -> bool:
        """将死信标记为可重新尝试。返回是否成功。"""
        return self._dlq.mark_resolved(dlq_id)

    def get_status(self) -> dict[str, Any]:
        """返回恢复层的健康状态摘要。"""
        return {
            "incomplete_checkpoints": self._checkpoint.count(),
            "unresolved_dlq": self._dlq.count_unresolved(),
            "event_count": self._event_store.count(),
            "latest_sequence": self._event_store.latest_sequence(),
        }
