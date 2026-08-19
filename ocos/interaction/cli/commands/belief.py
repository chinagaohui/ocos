"""OCOS CLI — belief 命令实现。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession, PermissionGuard
from ocos.interaction.context import InteractionContext


def cmd_belief_list(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos belief list"""
    guard = PermissionGuard()
    result = guard.check("view_belief")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    beliefs = ctx.query_beliefs(limit=20)
    if not beliefs:
        print("No beliefs formed yet. Execute goals to generate belief data.")
        print("Tip: `ocos goal create \"test objective\"` to start.")
    else:
        print(f"Active beliefs ({len(beliefs)} total):")
        for i, b in enumerate(beliefs, 1):
            bar = "█" * int(b["confidence"] * 10) + "░" * (10 - int(b["confidence"] * 10))
            print(f"  {i}. [{b['id'][:8]}] {b['statement'][:80]}")
            print(f"     Confidence: {bar} {b['confidence']:.2f} | Domain: {b['domain']}")
    session.record_query()
    return 0


def cmd_belief_summary(args, session: InteractionSession, ctx: InteractionContext) -> int:
    """ocos belief summary"""
    guard = PermissionGuard()
    result = guard.check("view_belief")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    from datetime import datetime, timezone
    beliefs = ctx.query_beliefs(limit=100)
    if not beliefs:
        print("No beliefs formed yet.")
    else:
        domains: dict[str, int] = {}
        total_conf = 0.0
        for b in beliefs:
            d = b["domain"] or "unknown"
            domains[d] = domains.get(d, 0) + 1
            total_conf += b["confidence"]

        avg_conf = total_conf / len(beliefs) if beliefs else 0
        print(f"Belief Summary ({len(beliefs)} total):")
        print(f"  Average confidence: {avg_conf:.2f}")
        print(f"  Domains: {domains}")
    session.record_query()
    return 0
