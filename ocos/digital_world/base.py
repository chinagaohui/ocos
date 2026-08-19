"""Phase 29 — 核心数据模型: DigitalOperation, OperationResult, AuditRecord。

所有对象不可变 (frozen=True)。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── 操作类型 ──────────────────────────────────────────────────────

VALID_OP_TYPES = frozenset({
    "file_read", "file_write", "file_delete",
    "git_clone", "git_commit", "git_push",
    "api_get", "api_post",
    "search",
    "db_query", "db_write",
    "sandbox_exec",
})

APPROVAL_REQUIRED = frozenset({
    "file_write", "file_delete",
    "git_commit", "git_push",
    "api_post",
    "db_write",
    "sandbox_exec",
})

# 资源限制
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_FILE_CONTENT_CHARS = 4000           # 大文件截断
API_RATE_LIMIT_PER_MIN = 60
SEARCH_QUERY_MAX_LEN = 500
SEARCH_SKIP_MAX = 1000
SANDBOX_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class DigitalOperation:
    """数字操作 — 不可变。"""
    op_id: str
    op_type: str
    target: str
    requester: str
    params: dict = field(default_factory=dict)
    approval_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.op_id:
            raise ValueError("op_id must not be empty")
        if self.op_type not in VALID_OP_TYPES:
            raise ValueError(f"invalid op_type: {self.op_type}")
        if self.op_type in APPROVAL_REQUIRED and not self.approval_id:
            raise ValueError(
                f"operation '{self.op_type}' requires approval_id"
            )

    @classmethod
    def create(
        cls,
        op_type: str,
        target: str,
        requester: str,
        params: dict | None = None,
        approval_id: str | None = None,
    ) -> DigitalOperation:
        return cls(
            op_id=f"OP-{uuid.uuid4().hex[:8]}",
            op_type=op_type,
            target=target,
            requester=requester,
            params=params or {},
            approval_id=approval_id,
        )


@dataclass(frozen=True)
class OperationResult:
    """操作结果 — 不可变。"""
    op_id: str
    status: str          # success|failure|timeout|rejected
    output: str | None = None
    error: str | None = None
    duration_ms: int = 0
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not self.op_id:
            raise ValueError("op_id must not be empty")
        if self.status not in ("success", "failure", "timeout", "rejected"):
            raise ValueError(f"invalid status: {self.status}")

    @classmethod
    def success(cls, op_id: str, output: str | None, duration_ms: int = 0) -> OperationResult:
        return cls(op_id=op_id, status="success", output=output,
                   duration_ms=duration_ms)

    @classmethod
    def failure(cls, op_id: str, error: str, duration_ms: int = 0) -> OperationResult:
        return cls(op_id=op_id, status="failure", error=error,
                   duration_ms=duration_ms)

    @classmethod
    def timeout(cls, op_id: str) -> OperationResult:
        return cls(op_id=op_id, status="timeout", error="operation timed out")

    @classmethod
    def rejected(cls, op_id: str, reason: str) -> OperationResult:
        return cls(op_id=op_id, status="rejected", error=reason)


@dataclass(frozen=True)
class AuditRecord:
    """数字世界审计记录 — 不可变。"""
    audit_id: str
    op_id: str
    op_type: str
    target: str
    requester: str
    status: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        if not self.audit_id:
            raise ValueError("audit_id must not be empty")

    @classmethod
    def from_result(
        cls, op: DigitalOperation, result: OperationResult,
    ) -> AuditRecord:
        return cls(
            audit_id=f"AUDIT-{uuid.uuid4().hex[:8]}",
            op_id=op.op_id,
            op_type=op.op_type,
            target=op.target,
            requester=op.requester,
            status=result.status,
        )
