"""Phase 28 — ExecutionAudit: 审计记录。

每次 Agent 调用都产生审计记录。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ExecutionRecord:
    """不可变执行记录。"""
    record_id: str
    contract_id: str
    agent_id: str
    status: str              # started→running→completed→failed→timed_out
    started_at: datetime
    completed_at: datetime | None = None
    result_summary: str | None = None
    error: str | None = None
    retry_count: int = 0

    def __post_init__(self):
        if not self.record_id:
            raise ValueError("record_id must not be empty")
        if not self.contract_id:
            raise ValueError("contract_id must not be empty")
        if self.status not in (
            "started", "running", "completed", "failed", "timed_out",
        ):
            raise ValueError(f"invalid status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        """S4.3: 序列化（orchestration 协作路径消费，原缺失导致 to_dict 崩溃）。"""
        return {
            "record_id": self.record_id,
            "contract_id": self.contract_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (self.completed_at.isoformat()
                             if self.completed_at else None),
            "result_summary": self.result_summary,
            "error": self.error,
            "retry_count": self.retry_count,
        }


class ExecutionAudit:
    """执行审计日志。"""

    def __init__(self) -> None:
        self._records: list[ExecutionRecord] = []

    def log_start(self, contract_id: str, agent_id: str) -> ExecutionRecord:
        """记录执行开始。"""
        record = ExecutionRecord(
            record_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            agent_id=agent_id,
            status="started",
            started_at=datetime.now(timezone.utc),
        )
        self._records.append(record)
        return record

    def log_complete(
        self, contract_id: str, agent_id: str, result_summary: str,
    ) -> ExecutionRecord:
        """记录执行完成。"""
        record = ExecutionRecord(
            record_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            agent_id=agent_id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result_summary=result_summary,
        )
        self._records.append(record)
        return record

    def log_failure(
        self, contract_id: str, agent_id: str, error: str,
        retry_count: int = 0,
    ) -> ExecutionRecord:
        """记录执行失败。"""
        record = ExecutionRecord(
            record_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            agent_id=agent_id,
            status="failed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error=error,
            retry_count=retry_count,
        )
        self._records.append(record)
        return record

    def log_timeout(self, contract_id: str, agent_id: str) -> ExecutionRecord:
        """记录超时。"""
        record = ExecutionRecord(
            record_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            agent_id=agent_id,
            status="timed_out",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        self._records.append(record)
        return record

    def get_records_for_contract(self, contract_id: str) -> list[ExecutionRecord]:
        """获取指定契约的所有记录。"""
        return [r for r in self._records if r.contract_id == contract_id]

    @property
    def trail(self) -> list[ExecutionRecord]:
        """完整审计轨迹。"""
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)
