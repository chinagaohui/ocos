"""OCOS REPL — belief 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession
from ocos.interaction.context import InteractionContext


class ReplBeliefCommand:
    """REPL /belief 命令 — 查看信念列表。"""

    def __init__(self, session: InteractionSession, ctx: InteractionContext):
        self._session = session
        self._ctx = ctx
        self._guard = PermissionGuard()

    def execute(self, arg: str):
        result = self._guard.check("view_belief")
        if not result.allowed:
            print(f"Permission denied: {', '.join(result.violations)}")
            return

        domain = arg.strip() or None
        beliefs = self._ctx.query_beliefs(domain=domain, limit=20)
        if not beliefs:
            label = f" in domain '{domain}'" if domain else ""
            print(f"No active beliefs{label}.")
        else:
            label = f" in domain '{domain}'" if domain else ""
            print(f"Active beliefs{label} ({len(beliefs)}):")
            for i, b in enumerate(beliefs, 1):
                bar = "█" * int(b["confidence"] * 10) + "░" * (10 - int(b["confidence"] * 10))
                print(f"  {i}. [{b['id'][:8]}] {b['statement'][:80]}")
                print(f"     Confidence: {bar} {b['confidence']:.2f}")
        self._session.record_query()
