"""Phase 29 — Dead Letter Queue。

失败操作写入 DLQ，支持重试。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ocos.digital_world.base import DigitalOperation


@dataclass(frozen=True)
class DLQEntry:
    """DLQ 条目 — 不可变。"""
    entry_id: str
    original_op: DigitalOperation
    error: str
    failed_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    status: str = "pending_retry"  # pending_retry|permanently_failed|resolved

    def __post_init__(self):
        if self.status not in ("pending_retry", "permanently_failed", "resolved"):
            raise ValueError(f"invalid DLQ status: {self.status}")

    def increment_retry(self) -> DLQEntry:
        """增加重试计数，超出则标记永久失败。"""
        new_count = self.retry_count + 1
        new_status = (
            "permanently_failed" if new_count >= self.max_retries
            else "pending_retry"
        )
        return DLQEntry(
            entry_id=self.entry_id,
            original_op=self.original_op,
            error=self.error,
            failed_at=self.failed_at,
            retry_count=new_count,
            max_retries=self.max_retries,
            status=new_status,
        )


class DeadLetterQueue:
    """死信队列。"""

    def __init__(self, max_retries: int = 3) -> None:
        self._entries: list[DLQEntry] = []
        self._max_retries = max_retries

    def enqueue(self, op: DigitalOperation, error: str) -> DLQEntry:
        """将失败操作入队。"""
        entry = DLQEntry(
            entry_id=f"DLQ-{uuid.uuid4().hex[:8]}",
            original_op=op,
            error=error,
            failed_at=datetime.now(timezone.utc),
            max_retries=self._max_retries,
        )
        self._entries.append(entry)
        return entry

    def retry_pending(self, executor_fn) -> list[DLQEntry]:
        """重试所有 pending 条目。

        executor_fn(op) → OperationResult
        """
        updated: list[DLQEntry] = []
        for i, entry in enumerate(self._entries):
            if entry.status != "pending_retry":
                continue
            result = executor_fn(entry.original_op)
            if result.status == "success":
                self._entries[i] = DLQEntry(
                    entry_id=entry.entry_id,
                    original_op=entry.original_op,
                    error=entry.error,
                    failed_at=entry.failed_at,
                    retry_count=entry.retry_count,
                    max_retries=entry.max_retries,
                    status="resolved",
                )
            else:
                self._entries[i] = entry.increment_retry()
            updated.append(self._entries[i])
        return updated

    @property
    def pending(self) -> list[DLQEntry]:
        return [e for e in self._entries if e.status == "pending_retry"]

    @property
    def permanently_failed(self) -> list[DLQEntry]:
        return [e for e in self._entries if e.status == "permanently_failed"]

    @property
    def all_entries(self) -> list[DLQEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
