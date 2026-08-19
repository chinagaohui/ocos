"""Phase 29 — Gate Tests: DeadLetterQueue。

验证:
  29-DQ01: DLQ stores failures
  29-DQ02: retry mechanism
  29-DQ03: permanently failed after max retries
"""

from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.dlq import DeadLetterQueue, DLQEntry


def test_dlq_stores_failures():
    dlq = DeadLetterQueue()
    op = DigitalOperation.create("file_read", "/tmp/test.txt", "G1")
    entry = dlq.enqueue(op, "file not found")
    assert len(dlq) == 1
    assert entry.status == "pending_retry"
    assert entry.error == "file not found"


def test_dlq_retry_success():
    dlq = DeadLetterQueue()
    op = DigitalOperation.create("file_read", "/tmp/test.txt", "G1")
    dlq.enqueue(op, "temp error")

    # executor now succeeds
    def executor(o):
        from ocos.digital_world.base import OperationResult
        return OperationResult.success(o.op_id, "ok")

    updated = dlq.retry_pending(executor)
    assert updated[0].status == "resolved"


def test_dlq_retry_until_permanent():
    dlq = DeadLetterQueue(max_retries=2)
    op = DigitalOperation.create("file_read", "/tmp/test.txt", "G1")
    dlq.enqueue(op, "persistent error")

    def always_fail(o):
        from ocos.digital_world.base import OperationResult
        return OperationResult.failure(o.op_id, "still failing")

    # 第1次重试
    dlq.retry_pending(always_fail)
    assert dlq.all_entries[0].retry_count == 1
    assert dlq.all_entries[0].status == "pending_retry"

    # 第2次重试 → permanently_failed
    dlq.retry_pending(always_fail)
    assert dlq.all_entries[0].retry_count == 2
    assert dlq.all_entries[0].status == "permanently_failed"
