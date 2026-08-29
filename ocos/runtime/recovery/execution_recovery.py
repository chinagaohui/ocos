"""Phase 39.4: Execution Recovery — 防止重复执行。

执行账本记录每次 Agent/Capability 调用的生命周期。
恢复时检查: 已完成 → skip, 运行中 → 检查结果, 失败 → 重试。

关键: 防止重复执行 — "下载已完成但结果未写入 → 不能重新下载"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExecutionStatus(Enum):
    """执行状态。"""

    PENDING = "pending"       # 尚未开始
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 已完成
    FAILED = "failed"         # 失败
    UNKNOWN = "unknown"       # 状态未知（崩溃）


@dataclass
class ExecutionRecord:
    """执行记录 — 可持久化。"""

    execution_id: str
    capability_id: str
    action: str
    resource: str | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    tick_started: int = 0
    tick_completed: int | None = None
    result_summary: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)

    @property
    def is_terminal(self) -> bool:
        return self.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)

    @property
    def should_retry(self) -> bool:
        return (
            self.status == ExecutionStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def needs_recovery(self) -> bool:
        return self.status in (ExecutionStatus.RUNNING, ExecutionStatus.UNKNOWN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "capability_id": self.capability_id,
            "action": self.action,
            "resource": self.resource,
            "status": self.status.value,
            "tick_started": self.tick_started,
            "tick_completed": self.tick_completed,
            "result_summary": self.result_summary,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExecutionRecord":
        return cls(
            execution_id=d["execution_id"],
            capability_id=d["capability_id"],
            action=d["action"],
            resource=d.get("resource"),
            status=ExecutionStatus(d["status"]),
            tick_started=d.get("tick_started", 0),
            tick_completed=d.get("tick_completed"),
            result_summary=d.get("result_summary"),
            retry_count=d.get("retry_count", 0),
            max_retries=d.get("max_retries", 3),
            created_at=d.get("created_at", 0),
        )


class ExecutionLedger:
    """执行账本 — 防止重复执行。"""

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or Path("ocos_data/executions")
        self._records: dict[str, ExecutionRecord] = {}

    def record_start(self, execution_id: str, capability_id: str,
                     action: str, resource: str | None = None,
                     tick_id: int = 0) -> ExecutionRecord:
        rec = ExecutionRecord(
            execution_id=execution_id,
            capability_id=capability_id,
            action=action,
            resource=resource,
            status=ExecutionStatus.RUNNING,
            tick_started=tick_id,
        )
        self._records[execution_id] = rec
        return rec

    def record_success(self, execution_id: str, tick_id: int,
                       summary: str | None = None) -> ExecutionRecord | None:
        rec = self._records.get(execution_id)
        if rec:
            rec.status = ExecutionStatus.SUCCESS
            rec.tick_completed = tick_id
            rec.result_summary = summary
        return rec

    def record_failure(self, execution_id: str, tick_id: int,
                       summary: str | None = None) -> ExecutionRecord | None:
        rec = self._records.get(execution_id)
        if rec:
            rec.status = ExecutionStatus.FAILED
            rec.tick_completed = tick_id
            rec.result_summary = summary
        return rec

    def get(self, execution_id: str) -> ExecutionRecord | None:
        return self._records.get(execution_id)

    def get_unresolved(self) -> list[ExecutionRecord]:
        return [r for r in self._records.values() if not r.is_terminal]

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._records.values()]

    @classmethod
    def from_dict_list(cls, data: list[dict[str, Any]]) -> "ExecutionLedger":
        ledger = cls()
        for d in data:
            rec = ExecutionRecord.from_dict(d)
            ledger._records[rec.execution_id] = rec
        return ledger

    def resolve_on_recovery(self) -> dict[str, ExecutionStatus]:
        resolved: dict[str, ExecutionStatus] = {}
        for rec in self._records.values():
            if rec.status == ExecutionStatus.RUNNING:
                rec.status = ExecutionStatus.UNKNOWN
                resolved[rec.execution_id] = ExecutionStatus.UNKNOWN
            elif rec.status == ExecutionStatus.UNKNOWN:
                resolved[rec.execution_id] = ExecutionStatus.UNKNOWN
        return resolved

    def should_skip(self, execution_id: str) -> bool:
        rec = self._records.get(execution_id)
        return rec is not None and rec.status == ExecutionStatus.SUCCESS
