"""OCOS CLI — trace 命令实现。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession, PermissionGuard


def cmd_trace_show(args, session: InteractionSession) -> int:
    """ocos trace show <trace_id>

    S4.2: 决策追踪存储未接线 — 明确返回"未实现"（退出码 2），
    不再打印 200 空结果误导脚本调用方。
    """
    guard = PermissionGuard()
    result = guard.check("view_trace")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    print(f"Decision Trace: {args.trace_id}")
    print("  未实现：决策追踪存储未接线（S4.2 占位端点 501 化）")
    session.record_query()
    return 2
