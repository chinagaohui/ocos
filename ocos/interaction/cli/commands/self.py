"""OCOS CLI — self 命令实现。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession, PermissionGuard
from ocos.interaction.context import InteractionContext


def cmd_self_status(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos self status"""
    guard = PermissionGuard()
    result = guard.check("view_self")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    identity = ctx.identity_summary()
    print("OCOS Self Status:")
    print(f"  Session ID:   {session.session_id}")
    print(f"  Goals created: {len(session.goals_created)}")
    print(f"  Queries made:  {session.queries_made}")
    print(f"  Identity:      {identity['id']}")
    print(f"  Principles:    {len(identity['principles'])} boundary rules")
    print(f"  Forbidden:     {len(identity['forbidden_transitions'])} transitions blocked")
    session.record_query()
    return 0


def cmd_self_identity(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos self identity"""
    guard = PermissionGuard()
    result = guard.check("view_self")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    identity = ctx.identity_summary()
    print(f"Identity: {identity['id']}")
    print(f"  Principles ({len(identity['principles'])}):")
    for p in identity["principles"]:
        print(f"    - {p}")
    if identity["forbidden_transitions"]:
        print(f"  Forbidden transitions ({len(identity['forbidden_transitions'])}):")
        for ft in identity["forbidden_transitions"]:
            print(f"    - {ft}")
    if identity["evolution_constraints"]:
        print(f"  Evolution constraints:")
        for k, v in identity["evolution_constraints"].items():
            print(f"    - {k}: {v}")
    session.record_query()
    return 0
