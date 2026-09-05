"""OCOS Interaction Layer — 基础抽象。

Cognitive Interface Layer 的基石：
  GoalRequest    — 人类目标转换为 Kernel 可处理的 UserGoal
  InteractionSession — 一次交互会话的上下文容器
  PermissionGuard   — 入口权限强制执行器

设计原则:
  - 入口是神经输入接口，不是权力拥有者
  - 所有写操作必须通过 GoalRequest → Constitution 检查
  - 读操作不修改任何 Internal State

权限边界（来自架构规约）:
  允许: create_goal, query_memory, request_plan, view_belief, view_self, view_trace
  禁止: modify_self, modify_identity, write_memory, modify_goal, modify_constitution, approve_evolution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.constitution.behavioral import BehavioralConstitution, ConstitutionResult
from ocos.goal.models import UserGoal, GoalDomain, GoalSource, CALLER_WHITELIST
from ocos.logging import get_logger

logger = get_logger(__name__)

# ── 权限映射 ──────────────────────────────────────────────────────────

# 入口层允许的操作（读 + 写）
ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "create_goal",
    "query_memory",
    "request_plan",
    "view_belief",
    "view_self",
    "view_trace",
    # 2026-08-23: OCOS 智脑质量分析/趋势检测（OpenTale 生成流程调用）
    "analyze_quality",
    "analyze_trend",
    # S1.3 (白皮书 P1-2b): API 写面显式白名单
    # self_improve = 产出"提案"入待批队列（应用仍需人工批准，非直接改写）
    "self_improve",
    # approve_action = 对待批队列的人工审批决策（执行侧另有 S1.1 溯源校验）
    "approve_action",
})

# 入口层禁止的操作
FORBIDDEN_ACTIONS: frozenset[str] = frozenset({
    "modify_self",
    "modify_identity",
    "write_memory",
    "modify_goal",
    "modify_constitution",
    "approve_evolution",
})


# ── GoalRequest ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoalRequest:
    """人类目标请求 → Kernel UserGoal 的转换适配器。

    创建 UserGoal 前执行三重检查：
      1. caller 在校验白名单中
      2. action 在 ALLOWED_ACTIONS 中
      3. 所有参数通过 Kernel 层 UserGoal.__post_init__ 验证

    Usage:
        req = GoalRequest.create(
            raw_input="帮我分析科幻小说市场趋势",
            objective="分析科幻小说市场趋势",
            domain=GoalDomain.ANALYSIS,
            caller="cli",
        )
        goal = req.to_user_goal()  # 返回 UserGoal 或抛出
    """

    raw_input: str
    objective: str
    domain: GoalDomain
    caller: str
    constraints: tuple[str, ...] = ()
    priority: int = 1

    @classmethod
    def create(
        cls,
        raw_input: str,
        objective: str,
        domain: GoalDomain,
        caller: str,
        constraints: tuple[str, ...] = (),
        priority: int = 1,
    ) -> GoalRequest:
        """工厂方法：创建并验证 GoalRequest。

        Raises:
            ValueError: caller 不在白名单中, priority 无效, domain 无效
        """
        if caller not in CALLER_WHITELIST:
            raise ValueError(
                f"caller '{caller}' not in CALLER_WHITELIST. "
                f"Allowed: {sorted(CALLER_WHITELIST)}"
            )
        if priority < 1 or priority > 5:
            raise ValueError(f"priority must be 1-5, got {priority}")
        return cls(
            raw_input=raw_input,
            objective=objective,
            domain=domain,
            caller=caller,
            constraints=constraints,
            priority=priority,
        )

    def to_user_goal(self) -> UserGoal:
        """转换为 Kernel UserGoal。

        Kernel 层 UserGoal.__post_init__ 会执行二次验证：
          - source 必须为 HUMAN 或 DECOMPOSED
          - HUMAN source 要求 caller 在校验白名单中
          - raw_input/objective 非空

        Raises:
            ValueError: 参数不合法（来自 UserGoal.__post_init__）
        """
        return UserGoal.create(
            raw_input=self.raw_input,
            objective=self.objective,
            domain=self.domain,
            caller=self.caller,
            constraints=self.constraints,
            priority=self.priority,
        )

    def verify_permission(self) -> bool:
        """检查 create_goal 是否在允许操作列表中。"""
        return "create_goal" in ALLOWED_ACTIONS


# ── InteractionSession ──────────────────────────────────────────────────


@dataclass
class InteractionSession:
    """一次交互会话的上下文容器。

    不持久化，仅存在于单次交互生命周期内。
    记录本次会话中创建的目标、执行的查询等元数据。
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    caller: str = "unknown"        # 入口类型: cli / repl / api
    goals_created: list[str] = field(default_factory=list)  # goal IDs
    queries_made: int = 0

    def record_goal(self, goal_id: str) -> None:
        self.goals_created.append(goal_id)

    def record_query(self) -> None:
        self.queries_made += 1

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "caller": self.caller,
            "goals_created": len(self.goals_created),
            "queries_made": self.queries_made,
        }


# ── PermissionGuard ─────────────────────────────────────────────────────


@dataclass
class PermissionGuard:
    """入口权限强制执行器。

    所有来自 Interaction Layer 的请求在此执行强制检查：
      - Action 必须在 ALLOWED_ACTIONS 中
      - Action 不能在 FORBIDDEN_ACTIONS 中
      - 高风险 Action 触发 Constitution 检查
    """

    constitution: BehavioralConstitution = field(
        default_factory=BehavioralConstitution
    )

    def check(self, action: str, context: dict[str, Any] | None = None) -> ConstitutionResult:
        """执行入口权限检查。

        Args:
            action: 操作名称（如 "create_goal", "view_self"）
            context: 可选上下文（user_consent 等）

        Returns:
            ConstitutionResult（allowed=True 表示操作许可）
        """
        # 1. 操作不能在 FORBIDDEN_ACTIONS 中（最高优先级拒绝）
        if action in FORBIDDEN_ACTIONS:
            return ConstitutionResult(
                allowed=False,
                violations=[f"Action '{action}' is FORBIDDEN for Interaction Layer"],
            )

        # 2. 操作必须在 ALLOWED_ACTIONS 中
        if action not in ALLOWED_ACTIONS:
            return ConstitutionResult(
                allowed=False,
                violations=[f"Action '{action}' not in ALLOWED_ACTIONS"],
            )

        # 3. 委托 Constitution 检查
        ctx = context or {"caller": "interaction_layer", "source": "human"}
        decision = type("Decision", (), {"action": action})()

        try:
            result = self.constitution.check_decision(decision, ctx)
        except Exception as e:
            logger.error(f"Constitution check failed for action '{action}': {e}")
            return ConstitutionResult(
                allowed=False,
                violations=[f"Constitution engine error: {e}"],
            )

        return result
