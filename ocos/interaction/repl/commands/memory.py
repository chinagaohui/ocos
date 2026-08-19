"""OCOS REPL — memory 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession
from ocos.interaction.context import InteractionContext


class ReplMemoryCommand:
    """REPL /memory 命令 — 查询近期记忆。"""

    def __init__(self, session: InteractionSession, ctx: InteractionContext):
        self._session = session
        self._ctx = ctx
        self._guard = PermissionGuard()

    def execute(self, arg: str):
        result = self._guard.check("query_memory")
        if not result.allowed:
            print(f"Permission denied: {', '.join(result.violations)}")
            return

        episodes = self._ctx.query_memory(limit=10)
        if not episodes:
            print("No recent memories.")
        else:
            print(f"Recent memories ({len(episodes)}):")
            for i, ep in enumerate(episodes, 1):
                print(f"  {i}. [{ep['id'][:8]}] {ep['decision'][:100]}")
        self._session.record_query()
