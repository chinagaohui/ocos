"""
OCOS ABI (Application Binary Interface) — 核心 dataclass 定义。

对应宪法 Part 1: Object Model 的 6 个不可变核心对象 + Event 类型枚举。
所有 dataclass 为 frozen 不可变，schema_version 管理向后兼容。
自 INFORMATION_THEORY v1.0 (2026-07-22) 扩展：新增 Information/Relation 事件类型。
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)


# ── Schema Version ──────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"


# ── Event Type Enum ─────────────────────────────────────────────────────────────

class EventType(str, Enum):
    """核心事件类型枚举（宪法 Part 2）。

    自 INFORMATION_THEORY v1.0 (2026-07-22) 扩展：
    - Information 统一状态机事件
    - Relation 统一关系模型事件
    - Query 事件
    """

    # Observation
    OBSERVATION_RECEIVED = "observation.received"
    OBSERVATION_VALIDATED = "observation.validated"

    # Memory
    MEMORY_STORED = "memory.stored"
    MEMORY_RETRIEVED = "memory.retrieved"

    # Knowledge
    KNOWLEDGE_CANDIDATE_PROPOSED = "knowledge.candidate_proposed"
    KNOWLEDGE_PROMOTED = "knowledge.promoted"
    KNOWLEDGE_DEPRECATED = "knowledge.deprecated"

    # ── Decision (Phase 17.2 — Goal Theory → Code Alignment) ──────────────
    DECISION_FORMED = "decision.formed"
    DECISION_VALIDATED = "decision.validated"
    DECISION_EXECUTED = "decision.executed"
    DECISION_REVOKED = "decision.revoked"
    DECISION_SUPERSEDED = "decision.superseded"
    DECISION_EXPIRED = "decision.expired"

    # Action
    ACTION_PROPOSED = "action.proposed"
    ACTION_SCHEDULED = "action.scheduled"
    ACTION_EXECUTED = "action.executed"
    ACTION_FAILED = "action.failed"

    # System
    SCHEDULER_TICK = "scheduler.tick"
    EMERGENCY_HALT = "emergency.halt"
    GOVERNANCE_APPROVAL_REQUESTED = "governance.approval_requested"
    GOVERNANCE_APPROVED = "governance.approved"
    GOVERNANCE_REJECTED = "governance.rejected"
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_ERROR = "plugin.error"

    # Resource
    RESOURCE_EXHAUSTED = "resource.exhausted"
    RESOURCE_RELEASED = "resource.released"

    # Adaptive Control
    ADAPTATION_APPLIED = "adaptation.applied"

    # Execution (Phase 17.1 — Execution Theory → Code Alignment)
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_INTERRUPTED = "execution.interrupted"
    EXECUTION_CANCELLED = "execution.cancelled"

    # Trace
    TRACE_RECORDED = "trace.recorded"

    # Audit
    AUDIT_CHECK_PASSED = "audit.check_passed"
    AUDIT_CHECK_FAILED = "audit.check_failed"

    # ── Information (INFORMATION_THEORY v1.0 新增) ──────────────────────────
    # 统一状态机事件
    INFORMATION_CREATED = "information.created"
    INFORMATION_VALIDATED = "information.validated"
    INFORMATION_STATUS_CHANGED = "information.status_changed"

    # 统一关系模型事件
    RELATION_CREATED = "relation.created"
    RELATION_REMOVED = "relation.removed"

    # Query（RPC 式请求-响应模式）
    INFORMATION_QUERIED = "information.queried"

    # 生命周期终态事件
    INFORMATION_DELETED = "information.deleted"

    # ── Process (Phase 15 — Process Foundation) ──────────────────────────
    INFORMATION_TRANSFORMATION_STARTED = "information.transformation_started"
    INFORMATION_TRANSFORMATION_COMPLETED = "information.transformation_completed"
    INFORMATION_TRANSFORMATION_FAILED = "information.transformation_failed"

    # ── Process Runtime (Phase 18 — Process Lifecycle) ───────────────────
    PROCESS_CREATED = "process.created"
    PROCESS_STARTED = "process.started"
    PROCESS_COMPLETED = "process.completed"
    PROCESS_FAILED = "process.failed"

    # ── Goal (Phase 17.2 — Goal Theory → Code Alignment) ─────────────────
    GOAL_SET = "goal.set"
    GOAL_UPDATED = "goal.updated"
    GOAL_COMPLETED = "goal.completed"
    GOAL_PAUSED = "goal.paused"
    GOAL_RESUMED = "goal.resumed"
    GOAL_CANCELLED = "goal.cancelled"
    GOAL_FAILED = "goal.failed"
    GOAL_SUPERSEDED = "goal.superseded"
    GOAL_EXPIRED = "goal.expired"


# ── Event ───────────────────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class Event:
    """Event Bus 的基本消息单元。"""
    event_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    event_type: EventType = EventType.SCHEDULER_TICK  # 默认 tick 类型, 调用方应显式指定 (GAP-P3-8 C.4)
    source: str = ""  # 产生事件的模块名
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)
    trace_id: str = ""  # 关联追踪链
    schema_version: str = SCHEMA_VERSION


# ── Core Objects (Frozen Dataclasses) ───────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Observation:
    """观察：系统对外部输入的统一封装。"""
    observation_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    content: dict[str, Any] = dataclasses.field(default_factory=dict)
    source: str = ""
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class Memory:
    """记忆：可检索的存储单元。

    ⚠️ memory_type 已废弃 (2026-07-22)：将逐步被 `PersistenceLevel` + `SemanticRole`
       两个正交维度替代。Working Memory = Persistence=SESSION, Role=INTENT/PREFERENCE；
       Episodic Memory = Persistence=PERSISTENT, Role=OBSERVATION。新代码应避免依赖
       memory_type 字段。
    """
    memory_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    content: dict[str, Any] = dataclasses.field(default_factory=dict)
    memory_type: str = "episodic"  # 已废弃，见 PersistenceLevel + SemanticRole
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class Knowledge:
    """知识：经过验证的模式/原则/策略。"""
    knowledge_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    content: dict[str, Any] = dataclasses.field(default_factory=dict)
    level: str = "evidence"  # observation | evidence | pattern | principle | policy
    status: str = "candidate"  # candidate | verified | active | deprecated | archived
    version: int = 1
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class Goal:
    """目标：系统行为的驱动方向。

    对应 GOAL_THEORY v1.0：
    - Invariant 1: 只回答 What，不回答 How
    - Invariant 2: 生命周期长于任何 Decision
    - Invariant 3: 一对多关系（Goal → Decision）

    status 使用 GoalStatus 枚举值字符串（向后兼容）。
    """

    goal_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    description: str = ""
    priority: int = 0  # 0=low, 1=normal, 2=high, 3=critical
    status: str = "active"  # GoalStatus 值（向后兼容 str）
    source: str = "user"  # user | agent_generated | decomposition | external_event | system
    parent_goal_id: str = ""
    success_criterion: str = ""
    observation_addresses: tuple[str, ...] = ()
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """验证 status 是否为合法 GoalStatus。（延迟 import 避免循环）"""
        from ocos.models.goal import GoalStatus  # noqa: PLC0415

        status_value = self.status
        if not GoalStatus.validate(status_value):
            logger.error(
                "Goal 状态验证失败: goal_id=%s invalid_status=%s",
                self.goal_id,
                status_value,
            )
            raise ValueError(
                f"非法 Goal status: '{status_value}'。"
                f" 合法值: {', '.join(s.value for s in GoalStatus)}"
            )
        logger.debug(
            "Goal 状态验证通过: goal_id=%s status=%s",
            self.goal_id,
            status_value,
        )


# ── DecisionStatus Enum (Phase 17.3) ─────────────────────────────────────────

_DECISION_LEGACY_MAP: dict[str, str] = {
    "formed": "proposed",
    "validated": "committed",
    "executing": "executed",
    "completed": "executed",
    "failed": "revoked",
}


class DecisionStatus(str, Enum):
    """Decision 生命周期标准状态（对应 DECISION_THEORY v1.0）。

    兼容映射（Legacy → Standard）：
        "formed"     → PROPOSED
        "validated"  → COMMITTED
        "executing"  → EXECUTED
        "completed"  → EXECUTED
        "failed"     → REVOKED

    Legacy 状态仍然可读（通过 __post_init__ 验证），新代码应使用标准值。
    """
    PROPOSED = "proposed"
    COMMITTED = "committed"
    EXECUTED = "executed"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"

    @classmethod
    def _missing_(cls, value: object) -> "DecisionStatus | None":
        """允许 Legacy 值通过兼容映射转换为标准状态。"""
        if isinstance(value, str):
            mapped = _DECISION_LEGACY_MAP.get(value)
            if mapped is not None:
                logger.debug(
                    "DecisionStatus Legacy 映射: legacy=%s → %s",
                    value,
                    mapped,
                )
                return cls(mapped)
        return None

    def resolve(self) -> "DecisionStatus":
        """返回标准化状态（Legacy → Standard）。"""
        resolved = _DECISION_LEGACY_MAP.get(self.value, self.value)
        return DecisionStatus(resolved)

    @classmethod
    def is_terminal(cls, value: str) -> bool:
        """是否为终止态：REVOKED | SUPERSEDED | EXPIRED（不含 EXECUTED）。"""
        s = _DECISION_LEGACY_MAP.get(value, value)
        return s in ("revoked", "superseded", "expired")

    @classmethod
    def is_active(cls, value: str) -> bool:
        """是否为活跃态：PROPOSED | COMMITTED。"""
        s = _DECISION_LEGACY_MAP.get(value, value)
        return s in ("proposed", "committed")

    @staticmethod
    def validate(value: str) -> bool:
        """检查字符串是否为合法 DecisionStatus 值（含 Legacy 兼容）。"""
        return value in _VALID_DECISION_STATUS_VALUES


_VALID_DECISION_STATUS_VALUES: frozenset[str] = frozenset({
    "proposed", "committed", "executed", "revoked", "superseded", "expired",
    # Legacy
    "formed", "validated", "executing", "completed", "failed",
})


# ── Decision (Phase 17.3 Enhanced) ───────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class Decision:
    """决策：Action 的唯一合法来源。

    对应 DECISION_THEORY v1.0：
    - Invariant 1: Decision 必须引用 Goal（goal_id ≠ ""）
    - Invariant 2: 一个 Decision 只能承诺一个选择（selected_option）
    - Invariant 3: Decision 是 Action 的唯一授权来源
    """
    decision_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    goal_id: str = ""
    selected_option: str = ""  # 所选方案标识（Invariant 2）
    reasoning: str = ""  # Legacy: v2.0 → UniversalAddress
    confidence: float = 0.0  # 0.0 ~ 1.0
    status: str = "formed"  # str 字段 + __post_init__ 验证（向后兼容 Legacy）
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """验证 status 是否为合法 DecisionStatus（含 Legacy 兼容）。"""
        status_value = self.status
        if not DecisionStatus.validate(status_value):
            logger.error(
                "Decision 状态验证失败: decision_id=%s goal_id=%s invalid_status=%s",
                self.decision_id,
                self.goal_id,
                status_value,
            )
            raise ValueError(
                f"Invalid Decision status: {status_value!r}. "
                f"Valid values: {sorted(_VALID_DECISION_STATUS_VALUES)}"
            )
        logger.debug(
            "Decision 状态验证通过: decision_id=%s goal_id=%s status=%s",
            self.decision_id,
            self.goal_id,
            status_value,
        )


@dataclasses.dataclass(frozen=True)
class Action:
    """动作：Decision 产生的可执行单元。"""
    action_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    decision_id: str = ""
    action_type: str = ""
    params: dict[str, Any] = dataclasses.field(default_factory=dict)
    status: str = "proposed"  # proposed | scheduled | executing | completed | failed
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
