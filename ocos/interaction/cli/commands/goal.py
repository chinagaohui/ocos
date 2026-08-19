"""OCOS CLI — goal 命令实现。"""

from __future__ import annotations

from ocos.goal.models import GoalDomain, GoalStatus
from ocos.interaction.base import GoalRequest, InteractionSession, PermissionGuard


def cmd_goal_create(args, session: InteractionSession) -> int:
    """ocos goal create "description" [--domain writing] [--priority 3]

    Returns 0 on success, 1 on failure.
    """
    # 1. 权限检查
    guard = PermissionGuard()
    result = guard.check("create_goal")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    # 2. 构建 GoalRequest
    domain = GoalDomain(args.domain)
    try:
        req = GoalRequest.create(
            raw_input=args.input,
            objective=args.input,  # 初始阶段 objective = raw_input
            domain=domain,
            caller="cli",
            constraints=tuple(args.constraint) if args.constraint else (),
            priority=args.priority,
        )
    except ValueError as e:
        print(f"Invalid goal: {e}")
        return 1

    # 3. 转换为 UserGoal（触发 Kernel 层验证）
    try:
        goal = req.to_user_goal()
    except ValueError as e:
        print(f"Goal validation failed: {e}")
        return 1

    # 4. 记录会话
    session.record_goal(goal.id)

    # 5. 输出
    print(f"Goal created: {goal.id}")
    print(f"  Status:   {goal.status.value}")
    print(f"  Domain:   {goal.domain.value}")
    print(f"  Priority: {goal.priority}")
    print(f"  Caller:   {goal.caller}")
    if goal.constraints:
        print(f"  Constraints:")
        for c in goal.constraints:
            print(f"    - {c}")

    return 0


def cmd_goal_status(args, session: InteractionSession) -> int:
    """ocos goal status <goal_id>"""
    # 目前 Kernel 没有持久化 goal store — 只能返回基本格式
    print(f"Goal ID: {args.goal_id}")
    print(f"  Note: Persistent goal store not yet implemented in Kernel.")
    print(f"  Goal ID format validated: {'GOAL-' in args.goal_id}")
    session.record_query()
    return 0


def cmd_goal_list(args, session: InteractionSession) -> int:
    """ocos goal list"""
    print("Goals listed in this session:")
    if not session.goals_created:
        print("  (none — goals are session-scoped; persistent store TBD)")
    else:
        for gid in session.goals_created:
            print(f"  - {gid}")
    session.record_query()
    return 0
