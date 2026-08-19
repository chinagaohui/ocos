"""OCOS REPL — self 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession
from ocos.interaction.context import InteractionContext


class ReplSelfCommand:
    """REPL /self 命令 — 查看 SelfModel 状态。"""

    def __init__(self, session: InteractionSession, ctx: InteractionContext):
        self._session = session
        self._ctx = ctx
        self._guard = PermissionGuard()

    def execute(self, arg: str):
        result = self._guard.check("view_self")
        if not result.allowed:
            print(f"Permission denied: {', '.join(result.violations)}")
            return

        identity = self._ctx.identity_summary()
        print(f"Self: {identity['id']}")
        print(f"  Principles: {len(identity['principles'])} boundary rules")
        if identity["principles"]:
            for p in identity["principles"]:
                print(f"    - {p}")
        print(f"  Forbidden transitions: {len(identity['forbidden_transitions'])}")
        self._session.record_query()
