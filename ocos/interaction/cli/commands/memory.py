"""OCOS CLI — memory 命令实现。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession, PermissionGuard
from ocos.interaction.context import InteractionContext


def cmd_memory_query(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos memory query <keyword>"""
    guard = PermissionGuard()
    result = guard.check("query_memory")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    episodes = ctx.query_memory(limit=20)
    filtered = [e for e in episodes if hasattr(args, 'query') and args.query and args.query.lower() in e["decision"].lower()]

    if not filtered and hasattr(args, 'query') and args.query:
        print(f"No episodes matching '{args.query}'.")
    elif not episodes:
        print("No episodes found. Create a goal first to generate memories.")
    else:
        print(f"Memories matching '{args.query}' ({len(filtered)} found):")
        for ep in filtered[:10]:
            print(f"  [{ep['id'][:8]}] {ep['decision'][:100]}")
        if len(filtered) > 10:
            print(f"  ... and {len(filtered) - 10} more")
    session.record_query()
    return 0


def cmd_memory_recent(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos memory recent"""
    guard = PermissionGuard()
    result = guard.check("query_memory")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    episodes = ctx.query_memory(limit=10)
    if not episodes:
        print("No recent memories. Create a goal first to generate episodes.")
        print("Tip: `ocos goal create \"your objective\"`")
    else:
        print(f"Recent memories ({len(episodes)} total):")
        for i, ep in enumerate(episodes, 1):
            print(f"  {i}. [{ep['id'][:8]}] {ep['decision'][:100]}")
    session.record_query()
    return 0
