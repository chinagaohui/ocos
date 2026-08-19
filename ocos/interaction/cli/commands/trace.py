"""OCOS CLI — trace 命令实现。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession, PermissionGuard


def cmd_trace_show(args, session: InteractionSession) -> int:
    """ocos trace show <trace_id>"""
    guard = PermissionGuard()
    result = guard.check("view_trace")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    print(f"Decision Trace: {args.trace_id}")
    print(f"  Note: DecisionTrace store integration TBD.")
    session.record_query()
    return 0
