"""Phase 29 — 操作审计。

每次 DigitalOperation 执行后记录审计。
"""

from __future__ import annotations

from ocos.digital_world.base import DigitalOperation, OperationResult, AuditRecord


class OperationAuditor:
    """数字世界操作审计器。"""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(self, op: DigitalOperation, result: OperationResult) -> AuditRecord:
        """记录一次操作。"""
        record = AuditRecord.from_result(op, result)
        self._records.append(record)
        return record

    def find_by_requester(self, requester: str) -> list[AuditRecord]:
        """按操作者查找审计记录。"""
        return [r for r in self._records if r.requester == requester]

    def find_by_status(self, status: str) -> list[AuditRecord]:
        """按状态查找。"""
        return [r for r in self._records if r.status == status]

    @property
    def trail(self) -> list[AuditRecord]:
        """完整审计轨迹。"""
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)
