"""Execution Model — Phase 17.1 Theory → Code Alignment.

对应 EXECUTION_THEORY v1.0（冻结）:
- Invariant 1: Execution 必须引用已提交的 Decision
- Invariant 2: Execution 不修改 Commitment
- Invariant 3: Execution 必须产生至少一个 Observation
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.kernel.abi import SCHEMA_VERSION
from ocos.models.information import UniversalAddress

logger = logging.getLogger(__name__)


# ── Enum: ExecutionStatus ───────────────────────────────────────────


class ExecutionStatus(str, Enum):
    """Execution 的生命周期状态。

    对应 EXECUTION_THEORY v1.0 §5:
    Pending → Running → Succeeded | Failed | Interrupted | Cancelled

    设计原则：
    - 使用 str Enum，避免 status: str 的技术债（vs Goal.status: str）
    - 6 种状态互斥且终止态不可逆
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """是否为终止态。"""
        return self in (
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
            ExecutionStatus.CANCELLED,
        )

    def can_transition_to(self, target: ExecutionStatus) -> bool:
        """检查从当前状态到目标状态的转移是否合法。"""
        result = target in _VALID_TRANSITIONS.get(self, set())
        logger.debug("ExecutionStatus %s → %s: %s", self.value, target.value, result)
        return result


_VALID_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.INTERRUPTED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.SUCCEEDED: set(),      # terminal
    ExecutionStatus.FAILED: set(),          # terminal
    ExecutionStatus.INTERRUPTED: set(),     # terminal
    ExecutionStatus.CANCELLED: set(),       # terminal
}


# ── Execution 主数据模型 ────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class Execution:
    """执行：将 Decision 承诺转化为世界状态变化的过程。

    Invariant 1: decision_id 必须引用一个已提交（committed）的 Decision
    Invariant 2: Execution 不修改 Decision 的状态
    Invariant 3: observation_addresses 必须非空（至少产生一个 Observation）
    """

    execution_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    decision_id: str = ""                   # Invariant 1
    status: ExecutionStatus = ExecutionStatus.PENDING
    action_ids: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    observation_addresses: tuple[UniversalAddress, ...] = dataclasses.field(
        default_factory=tuple
    )                                       # Invariant 3: 使用 Address 而非 ID
    started_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
