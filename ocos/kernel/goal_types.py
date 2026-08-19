"""OCOS Kernel — 统一 Goal 类型定义。

Phase 21: 所有 Goal 相关类型的唯一权威来源。
迁移路径:
  - agent/goal_types.py → from ocos.kernel.goal_types import ... (ABI 层)
  - goal/models.py → 标记 deprecated，通过 UserGoal.to_goal() 兼容

类型层次:
  Goal (统一目标) + GoalLevel + GoalStatus + GoalOriginLevel + GoalAuthority
  兼容: GoalSource + GoalDomain + SuccessCriteria + UserGoal
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════
# 核心类型（来自 agent/goal_types.py — 唯一来源）
# ═══════════════════════════════════════════════════════════════════════════


class GoalLevel(Enum):
    """目标层级。值越小优先级越高。"""
    MISSION = 0
    LONG = 1
    MID = 2
    SHORT = 3
    TASK = 4
    ACTION = 5


_GOAL_STATUS_TRANSITIONS: dict[GoalStatus, set[GoalStatus]]


class GoalStatus(Enum):
    """Goal 生命周期状态。"""
    PENDING = auto()
    ACTIVE = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    FAILED = auto()
    # Phase 21 compat: alias for CANCELLED
    ABANDONED = CANCELLED

    @property
    def is_terminal(self) -> bool:
        """是否终态。"""
        return self in (GoalStatus.COMPLETED, GoalStatus.CANCELLED, GoalStatus.ABANDONED)

    def can_transition_to(self, target: GoalStatus) -> bool:
        """检查是否可以转换到目标状态。"""
        if not isinstance(target, GoalStatus):
            return False
        return target in _GOAL_STATUS_TRANSITIONS.get(self, set())


_GOAL_STATUS_TRANSITIONS = {
        GoalStatus.PENDING:   {GoalStatus.ACTIVE, GoalStatus.ABANDONED},
        GoalStatus.ACTIVE:    {GoalStatus.COMPLETED, GoalStatus.ABANDONED},
        GoalStatus.COMPLETED: set(),
        GoalStatus.CANCELLED: set(),
        GoalStatus.FAILED:    set(),
        GoalStatus.ABANDONED: set(),
        }


class GoalOriginLevel(Enum):
    """Goal 来源层级 — GOAL ORIGIN MODEL v1.0。

    Phase 边界:
      Phase 21: 只能 SYSTEM
      Phase 22-24: SYSTEM + HUMAN
      Phase 25+: 全部三种
    """
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    SELF = "SELF"


class GoalAuthority(Enum):
    """Goal 权限级别。"""
    AUTONOMOUS = "AUTONOMOUS"
    FRAMEWORK = "FRAMEWORK"
    PROPOSAL = "PROPOSAL"


# ═══════════════════════════════════════════════════════════════════════════
# 兼容类型（来自 goal/models.py — 迁移到 kernel）
# ═══════════════════════════════════════════════════════════════════════════


class GoalSource(str, Enum):
    """Goal 来源 — 闭合枚举 (deprecated, 用 GoalOriginLevel 替代)。"""
    HUMAN = "human"
    DECOMPOSED = "decomposed"


CALLER_WHITELIST: frozenset[str] = frozenset({
    "orchestrator",
    "goal_parser",
    "cli",
    "api",
    "repl",
    "runtime",
    "python-script",
    "daemon",
})


class GoalDomain(str, Enum):
    """Goal 所属领域 (保留用于兼容)。"""
    WRITING = "writing"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    DEVELOPMENT = "development"


@dataclass(frozen=True)
class SuccessCriteria:
    """可验证的成功标准 (保留用于兼容)。"""
    description: str
    measurable: bool
    threshold: str | None = None
    met: bool = False

    def __post_init__(self):
        if not self.description:
            raise ValueError("description must not be empty")
        if self.measurable and self.threshold is None:
            raise ValueError("threshold required when measurable=True")


# ═══════════════════════════════════════════════════════════════════════════
# 统一 Goal 类型
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=False)
class Goal:
    """统一目标类型 — 合并 Goal + UserGoal。

    6 级目标层级: MISSION(0) > LONG(1) > MID(2) > SHORT(3) > TASK(4) > ACTION(5)

    Goal Origin Model v1.0:
      origin_level: 来源层级
      authority: 权限级别
    """
    goal_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    level: GoalLevel = GoalLevel.TASK
    description: str = ""
    parent_id: Optional[str] = None
    priority: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: Optional[datetime] = None
    status: GoalStatus = GoalStatus.PENDING
    result: Optional[dict[str, Any]] = None

    # Goal Origin Model v1.0
    origin_level: GoalOriginLevel = GoalOriginLevel.SYSTEM
    authority: GoalAuthority = GoalAuthority.AUTONOMOUS

    # Phase 21: 兼容字段（来自 UserGoal）
    raw_input: str = ""
    objective: str = ""
    domain: GoalDomain = GoalDomain.ANALYSIS
    constraints: tuple[str, ...] = ()
    success_criteria: tuple[SuccessCriteria, ...] = ()
    source: GoalSource = GoalSource.HUMAN
    caller: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# UserGoal: 兼容过渡类型（deprecated — 建议直接使用 Goal）
# ═══════════════════════════════════════════════════════════════════════════

# Domain → Level 近似映射
_DOMAIN_TO_LEVEL: dict[GoalDomain, GoalLevel] = {
    GoalDomain.WRITING: GoalLevel.TASK,
    GoalDomain.ANALYSIS: GoalLevel.MID,
    GoalDomain.RESEARCH: GoalLevel.LONG,
    GoalDomain.DEVELOPMENT: GoalLevel.TASK,
}


@dataclass(frozen=True)
class UserGoal:
    """用户目标 — deprecated，建议使用 Goal。

    Phase 21: 保留用于向后兼容，通过 to_goal() 适配到统一 Goal。
    """

    id: str
    raw_input: str
    objective: str
    domain: GoalDomain
    constraints: tuple[str, ...] = ()
    success_criteria: tuple[SuccessCriteria, ...] = ()
    priority: int = 1
    status: GoalStatus = GoalStatus.PENDING
    parent_id: str | None = None
    source: GoalSource = GoalSource.HUMAN
    caller: str = "unknown"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id:
            raise ValueError("id must not be empty")
        if not self.raw_input:
            raise ValueError("raw_input must not be empty")
        if not self.objective:
            raise ValueError("objective must not be empty")
        if self.priority < 1 or self.priority > 5:
            raise ValueError(f"priority must be 1-5, got {self.priority}")
        if self.source not in (GoalSource.HUMAN, GoalSource.DECOMPOSED):
            raise ValueError(f"source must be human or decomposed, got {self.source}")
        if self.parent_id is not None and self.source != GoalSource.DECOMPOSED:
            raise ValueError("parent_id set but source is not decomposed")
        if self.source == GoalSource.HUMAN and self.caller not in CALLER_WHITELIST:
            raise ValueError(
                f"caller '{self.caller}' not in CALLER_WHITELIST; "
                f"only {sorted(CALLER_WHITELIST)} can create HUMAN goals"
            )

    @classmethod
    def create(
        cls,
        raw_input: str,
        objective: str,
        domain: GoalDomain,
        caller: str,
        constraints: tuple[str, ...] = (),
        success_criteria: tuple[SuccessCriteria, ...] = (),
        priority: int = 1,
    ) -> UserGoal:
        """工厂方法：创建 human-source goal。"""
        return cls(
            id=f"GOAL-{uuid.uuid4().hex[:8]}",
            raw_input=raw_input,
            objective=objective,
            domain=domain,
            constraints=constraints,
            success_criteria=success_criteria,
            priority=priority,
            source=GoalSource.HUMAN,
            caller=caller,
        )

    def with_status(self, status: GoalStatus) -> UserGoal:
        """不可变状态转换。"""
        if not self.status.can_transition_to(status):
            raise ValueError(
                f"Cannot transition from {self.status.name} to {status.name}"
            )
        return UserGoal(
            id=self.id,
            raw_input=self.raw_input,
            objective=self.objective,
            domain=self.domain,
            constraints=self.constraints,
            success_criteria=self.success_criteria,
            priority=self.priority,
            status=status,
            parent_id=self.parent_id,
            source=self.source,
            caller=self.caller,
            created_at=self.created_at,
        )

    # ── Phase 21: 适配器 ───────────────────────────────────────────────

    def to_goal(self) -> Goal:
        """转换为统一 Goal 类型。

        GoalDomain → GoalLevel 映射（近似）：
          WRITING/DEVELOPMENT → TASK, ANALYSIS → MID, RESEARCH → LONG
        """
        goal_id = self.id if self.id.startswith("GOAL-") else f"GOAL-{self.id}"
        return Goal(
            goal_id=goal_id,
            level=_DOMAIN_TO_LEVEL.get(self.domain, GoalLevel.TASK),
            description=self.objective or self.raw_input,
            parent_id=self.parent_id,
            priority=float(self.priority),
            created_at=self.created_at,
            status=self.status,
            origin_level=(
                GoalOriginLevel.HUMAN
                if self.source == GoalSource.HUMAN
                else GoalOriginLevel.SYSTEM
            ),
            authority=GoalAuthority.FRAMEWORK,
            raw_input=self.raw_input,
            objective=self.objective,
            domain=self.domain,
            constraints=self.constraints,
            success_criteria=self.success_criteria,
            source=self.source,
            caller=self.caller,
            metadata={
                "success_criteria": [
                    {
                        "description": sc.description,
                        "measurable": sc.measurable,
                        "threshold": sc.threshold,
                        "met": sc.met,
                    }
                    for sc in self.success_criteria
                ],
                "constraints": list(self.constraints),
            },
        )
