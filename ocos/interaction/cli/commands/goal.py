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

    # 4. 落库（AUD-F8: goal 域持久化 — goals 表, goal 域包 GoalStore）
    from ocos.goal.store import GoalStore
    from ocos.interaction.cli.paths import resolve_db_path
    store = GoalStore(db_path=resolve_db_path())
    store.save(
        goal_id=goal.id,
        level="USER",
        status=goal.status.name,  # auto() 枚举: 存名字而非数字值
        description=goal.objective,
        priority=float(goal.priority),
        source=goal.caller,
        origin_level="HUMAN",   # caller="cli" 白名单 → 人类来源目标
        authority="FRAMEWORK",
        metadata={"domain": args.domain},  # UX-1: daemon 认领时按域分解
    )
    db_path = resolve_db_path()

    # 5. 记录会话
    session.record_goal(goal.id)

    # 6. 输出
    print(f"Goal created: {goal.id}")
    print(f"  Status:   {goal.status.name}")
    print(f"  Domain:   {goal.domain.value}")
    print(f"  Priority: {goal.priority}")
    print(f"  Caller:   {goal.caller}")
    if goal.constraints:
        print(f"  Constraints:")
        for c in goal.constraints:
            print(f"    - {c}")
    print(f"  Persisted: {db_path}")
    print(f"  Next: 运行中的 daemon 将自动认领 (ocos run) | ocos goal status {goal.id}")

    return 0


def cmd_goal_exec(args, session: InteractionSession) -> int:
    """ocos goal exec \"描述\" — 直接执行 (绕过 daemon 认领与模板分解)。

    描述 → LLM 分解为只读命令 → DecisionBridge 沙盒逐条真实执行 → 汇总。
    返回 0 成功, 2 无法执行 (含沙盒全拦截), 1 系统错误。
    """
    from ocos.execution.goal_executor import GoalDirectExecutor
    from ocos.logging import get_logger
    logger = get_logger(__name__)

    description = args.input
    print(f"直接执行: {description[:120]}")
    print("  (绕过 daemon 认领 — 描述级 LLM 分解 → 沙盒只读执行)\n")

    executor = GoalDirectExecutor()
    try:
        report = executor.execute_goal(description)
    except Exception as e:
        print(f"Error: 执行失败: {e}")
        return 1

    # 输出结果表
    ok_n = 0
    for i, c in enumerate(report.commands, 1):
        status = "✓" if c.ok else ("⛔ 拦截" if c.blocked else "✗")
        print(f"[{i}] {status} $ {c.command}")
        if c.ok:
            out = (c.stdout or "").strip()
            for ln in out.splitlines()[:8]:
                print(f"      {ln}")
            ok_n += 1
        elif c.blocked:
            print(f"      → 沙盒拦截: {c.block_reason}")
        else:
            print(f"      → 失败: {c.stderr or c.block_reason}")
        print()

    print(f"== 汇总: {report.summary} ==")
    return 0 if ok_n > 0 else 2


def cmd_goal_status(args, session: InteractionSession) -> int:
    """ocos goal status <goal_id>"""
    # AUD-F8: 查询持久化 goal（goals 表）
    from ocos.goal.store import GoalStore
    from ocos.interaction.cli.paths import resolve_db_path
    store = GoalStore(db_path=resolve_db_path())
    row = store.load(args.goal_id)
    print(f"Goal ID: {args.goal_id}")
    if row is None:
        print("  Not found in persistent store.")
        print(f"  Goal ID format validated: {'GOAL-' in args.goal_id}")
        session.record_query()
        return 1   # FIX-VAL2: 未找到 = 非零退出码（脚本化使用语义）
    else:
        print(f"  Level:    {row.get('level')}")
        print(f"  Status:   {row.get('status')}")
        print(f"  Progress: {row.get('progress')}")
        print(f"  Description: {row.get('description')}")
        print(f"  Created:  {row.get('created_at')}")
    session.record_query()
    return 0

def cmd_goal_list(args, session: InteractionSession) -> int:
    """ocos goal list"""
    from ocos.goal.store import GoalStore
    from ocos.interaction.cli.paths import resolve_db_path
    store = GoalStore(db_path=resolve_db_path())
    rows = store.load_active()
    print(f"Active goals in persistent store: {len(rows)}")
    for row in rows:
        print(f"  - {row.get('id')}  [{row.get('status')}]  {str(row.get('description'))[:60]}")
    if session.goals_created:
        print(f"(session created: {', '.join(session.goals_created)})")
    session.record_query()
    return 0
